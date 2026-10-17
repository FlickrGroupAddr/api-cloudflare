// Actual Worker/VM/SQLite tests require Node; Python owns fixture preparation.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { loadOfflineModule } from './offline_modules.mjs';
import { createSyntheticStore } from './offline_sqlite.mjs';
import { createQualificationWrapper, PATHS, ORIGIN, CASES } from './wrapper.mjs';
import { HANDLER_CASES, BROWSER_PATHS, initializeHandlerCaseNamespaces,
  handlerCaseIdentity } from '../fixed-origin-lifecycle/handler_cases.mjs';

assert.equal(process.version, 'v24.22.0');
const fixture = process.env.FGA_OFFLINE_FIXTURE;
assert.ok(fixture, 'private fixture path required');
const manifest = JSON.parse(readFileSync(join(fixture, 'manifest.json'), 'utf8'));
assert.equal(manifest.candidateCommit, 'b599ca828d2a645b686aca0354d6c8ee2c2a0250');
const hash = filename => createHash('sha256').update(readFileSync(filename)).digest('hex');
assert.equal(hash(join(fixture, 'captured.mjs')), 'f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d');
assert.equal(hash(join(fixture, 'candidate.mjs')), 'c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36');
assert.equal(manifest.candidateBundleSha2_256, hash(join(fixture, 'candidate.mjs')));
for (const [filename, digest] of Object.entries(manifest.candidateSourceFiles)) {
  assert.equal(hash(join(fixture, 'candidate', filename)), digest);
}
const counters = { hostIo: 0, globalFetch: 0, dynamicImport: 0, normal: 0, synthetic: 0,
  syntheticSql: 0, application: 0, grant: 0, memoryFetch: 0, pages: 0, images: 0,
  productionReads: 0, productionSql: 0, normalIdentity: 0 };
const captured = await loadOfflineModule(join(fixture, 'captured.mjs'), counters);
const candidate = await loadOfflineModule(join(fixture, 'candidate.mjs'), counters);
const db = createSyntheticStore(join(fixture, 'candidate/migrations'), counters);
await initializeHandlerCaseNamespaces(db);
const scope = { run: 'a'.repeat(32), capability: 'b'.repeat(64), startsAt: 1000, expiresAt: 601000 };
let now = 2000;
const forbiddenProduction = new Proxy({}, { get() { counters.productionReads++; throw Error('production_env_denied'); },
  ownKeys() { counters.productionReads++; throw Error('production_env_denied'); } });
const productionDb = new Proxy({}, { get() { counters.productionSql++; throw Error('production_database_denied'); } });
const ordinaryEnv = Object.freeze({ DB: productionDb, FGA_READ_ENABLED: '1' });
let expectedRequest, expectedEnv;
const normalSpy = { default: { fetch(request, env) {
  assert.equal(request, expectedRequest); assert.equal(env, expectedEnv); counters.normalIdentity++;
  return captured.default.fetch(request, env);
} } };
const wrapper = createQualificationWrapper({ captured: normalSpy, candidate, syntheticDb: db,
  ...scope, clock: () => now, counters });
const qualificationHeaders = (scenario = 'ok') => ({ Authorization: 'FGA-Qualification ' + scope.capability,
  'X-FGA-Qualification-Run': scope.run, 'X-FGA-Qualification-Case': scenario });
const request = (path = PATHS[0], headers = qualificationHeaders(), method = 'GET', origin = ORIGIN) =>
  new Request(origin + path, { method, headers });

test('pinned candidate contains the three handlers; capture remains unchanged baseline', () => {
  assert.equal(captured.ROUTES.length, 25);
  assert.ok(candidate.ROUTES.some(route => route.handler === 'existing_photos'));
  assert.ok(candidate.ROUTES.some(route => route.handler === 'photo_thumbnail'));
  assert.ok(!captured.ROUTES.some(route => route.handler === 'photo_thumbnail'));
});

for (const scenario of ['ok', 'missing-auth', 'invalid-auth']) for (const [index, path] of PATHS.entries()) {
  test(`actual candidate route ${index + 1} case ${scenario}`, async () => {
    const before = { ...counters };
    const response = await wrapper.fetch(request(path, qualificationHeaders(scenario)), forbiddenProduction);
    assert.equal(response.status, scenario === 'ok' ? 200 : 401);
    assert.equal(counters.normal, before.normal);
    assert.equal(counters.productionReads, 0);
    if (scenario === 'ok') {
      if (index === 0) assert.equal((await response.json()).installationId, handlerCaseIdentity('ok').installationId);
      if (index === 1) {
        const body = await response.json();
        assert.equal(body.linkedFlickrRevision, 1); assert.equal(body.photos[0].flickrPhotoId, 'photo');
      }
      if (index === 2) {
        assert.equal(response.headers.get('Content-Type'), 'image/png');
        assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
        assert.ok((await response.arrayBuffer()).byteLength > 45);
        assert.equal(counters.images, before.images + 1);
      }
    } else {
      assert.equal(counters.syntheticSql, before.syntheticSql);
      assert.equal(counters.memoryFetch, before.memoryFetch);
      assert.equal(counters.application, before.application);
      assert.equal(counters.grant, before.grant);
      assert.match(response.headers.get('WWW-Authenticate'), /^Bearer realm="fga-api"/);
      await response.arrayBuffer();
    }
  });
}

test('finite handler selectors and normal browser paths have closed route compatibility', async () => {
  assert.deepEqual(new Set(CASES), new Set(['ok', 'invalid-auth', ...Object.keys(HANDLER_CASES)]));
  for (const scenario of Object.keys(HANDLER_CASES).filter(value => !['png', 'missing-auth', 'bad-auth'].includes(value))) {
    for (const path of [PATHS[0], PATHS[1], ...BROWSER_PATHS]) {
      const before = { ...counters };
      assert.equal((await wrapper.fetch(request(path, qualificationHeaders(scenario)), forbiddenProduction)).status, 404);
      assert.deepEqual(counters, before);
    }
  }
});

const malformed = [
  ['production bearer with selectors', PATHS[0], { Authorization: 'Bearer ' + Array(13).fill('1111').join('-') }],
  ['production bearer plus capability', PATHS[0], { Authorization: 'Bearer production, FGA-Qualification ' + scope.capability }],
  ['missing capability', PATHS[0], { Authorization: null }],
  ['foreign capability', PATHS[0], { Authorization: 'FGA-Qualification ' + 'c'.repeat(64) }],
  ['wrong scheme case', PATHS[0], { Authorization: 'fga-qualification ' + scope.capability }],
  ['missing run', PATHS[0], { 'X-FGA-Qualification-Run': null }],
  ['foreign run', PATHS[0], { 'X-FGA-Qualification-Run': 'c'.repeat(32) }],
  ['duplicate run', PATHS[0], { 'X-FGA-Qualification-Run': scope.run + ', ' + scope.run }],
  ['unknown case', PATHS[0], { 'X-FGA-Qualification-Case': 'arbitrary' }],
  ['missing case', PATHS[0], { 'X-FGA-Qualification-Case': null }],
  ['duplicate case', PATHS[0], { 'X-FGA-Qualification-Case': 'ok, ok' }],
  ['unknown control', PATHS[0], { 'X-FGA-Qualification-Url': 'https://example.invalid' }],
  ['malformed control name', PATHS[0], { 'X-FGA-Qualification': 'unknown' }],
  ['current query', PATHS[0] + '?page=1', {}],
  ['empty current query delimiter', PATHS[0] + '?', {}],
  ['empty current fragment delimiter', PATHS[0] + '#', {}],
  ['empty current query and fragment', PATHS[0] + '?#', {}],
  ['empty discovery fragment delimiter', PATHS[1] + '#', {}],
  ['empty thumbnail fragment delimiter', PATHS[2] + '#', {}],
  ['duplicate page', PATHS[1] + '&page=1', {}],
  ['reordered query', '/api/v001/existing-public-photos?page_size=1&page=1', {}],
  ['foreign photo', PATHS[2].replace('/photo/', '/foreign/'), {}],
  ['encoded photo', PATHS[2].replace('/photo/', '/%70hoto/'), {}],
  ['foreign revision', PATHS[2].replace('revision=1', 'revision=2'), {}],
  ['arbitrary URL', PATHS[2] + '&url=https://example.invalid', {}],
  ['missing query', '/api/v001/existing-public-photos', {}],
  ['public seed', '/__probe/seed', {}],
  ['write route', '/api/v001/group-submission-batches', {}],
  ['trailing slash', PATHS[0] + '/', {}],
  ['fragment', PATHS[0] + '#x', {}],
  ['nonzero content length', PATHS[0], { 'Content-Length': '1' }],
  ['transfer encoding', PATHS[0], { 'Transfer-Encoding': 'chunked' }],
];
for (const [label, path, changes] of malformed) {
  test(`closed selector: ${label}`, async () => {
    const headers = new Headers(qualificationHeaders());
    for (const [name, value] of Object.entries(changes)) {
      if (value === null) headers.delete(name); else headers.set(name, value);
    }
    const before = { ...counters };
    const response = await wrapper.fetch(request(path, headers), forbiddenProduction);
    assert.equal(response.status, 404); assert.equal(await response.text(), '');
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
    assert.deepEqual(counters, before);
  });
}
for (const method of ['POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS']) {
  test(`closed method ${method}`, async () => {
    const before = { ...counters };
    assert.equal((await wrapper.fetch(request(PATHS[0], qualificationHeaders(), method), forbiddenProduction)).status, 404);
    assert.deepEqual(counters, before);
  });
}
for (const origin of ['http://flickrgroupaddr.com', 'https://other.invalid', 'https://flickrgroupaddr.com:444']) {
  test(`closed origin ${origin}`, async () => {
    const before = { ...counters };
    assert.equal((await wrapper.fetch(request(PATHS[0], qualificationHeaders(), 'GET', origin), forbiddenProduction)).status, 404);
    assert.deepEqual(counters, before);
  });
}
for (const time of [999, 601000, 601001, NaN]) {
  test(`closed lifetime ${time}`, async () => {
    now = time;
    const before = { ...counters };
    assert.equal((await wrapper.fetch(request(), forbiddenProduction)).status, 404);
    assert.deepEqual(counters, before); now = 2000;
  });
}
test('ordinary requests preserve exact captured request/environment and behavior', async () => {
  for (const [path, status] of [[PATHS[0], 401], [PATHS[1], 404], [PATHS[2], 404], ['/unknown', 404]]) {
    const req = request(path, {});
    expectedRequest = req; expectedEnv = ordinaryEnv;
    const before = { ...counters };
    const response = await wrapper.fetch(req, ordinaryEnv);
    const direct = await captured.default.fetch(req, ordinaryEnv);
    assert.equal(response.status, status); assert.equal(response.status, direct.status);
    assert.deepEqual([...response.headers], [...direct.headers]);
    assert.equal(counters.normal, before.normal + 1);
    assert.equal(counters.synthetic, before.synthetic);
    assert.equal(counters.syntheticSql, before.syntheticSql);
    await response.arrayBuffer(); await direct.arrayBuffer();
  }
});
test('a production-shaped bearer alone selects only captured ordinary dispatch', async () => {
  // Synthetic representation only: no live credential is read or required.
  const req = request(PATHS[1], { Authorization: 'Bearer ' + Array(13).fill('1111').join('-') });
  expectedRequest = req; expectedEnv = ordinaryEnv;
  const before = { ...counters };
  assert.equal((await wrapper.fetch(req, ordinaryEnv)).status, 404);
  assert.equal(counters.normal, before.normal + 1); assert.equal(counters.synthetic, before.synthetic);
});
test('constructor rejects malformed or unbounded scope', () => {
  for (const change of [{ run: 'invalid' }, { capability: 'short' }, { expiresAt: 601001 },
    { startsAt: NaN }, { expiresAt: 1000 }, { expiresAt: 'later' }]) {
    assert.throws(() => createQualificationWrapper({ captured, candidate, syntheticDb: db,
      ...scope, ...change, counters }), /invalid_scope/);
  }
});
test('aborted qualification request is refused before dispatch', async () => {
  const controller = new AbortController(); controller.abort();
  const req = new Request(ORIGIN + PATHS[0], { headers: qualificationHeaders(), signal: controller.signal });
  const before = { ...counters };
  assert.equal((await wrapper.fetch(req, forbiddenProduction)).status, 404);
  assert.deepEqual(counters, before);
});
test('final isolation and no protected mutations', () => {
  assert.equal(counters.productionReads, 0); assert.equal(counters.productionSql, 0);
  assert.equal(counters.globalFetch, 0); assert.equal(counters.hostIo, 0); assert.equal(counters.dynamicImport, 0);
  assert.equal(counters.application, 2); assert.equal(counters.grant, 2);
  assert.equal(counters.pages, 2); assert.equal(counters.images, 1);
  assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n, 0);
  assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n, 0);
  console.log(JSON.stringify({ schemaVersion: 1, kind: 'offline_split_wrapper_isolation',
    candidateCommit: manifest.candidateCommit, candidateBundleSha2_256: manifest.candidateBundleSha2_256,
    capturedModuleSha2_256: manifest.capturedModuleSha2_256,
    actualHandlerCases: 9, syntheticBranchCalls: counters.synthetic, normalDispatchCalls: counters.normal,
    productionEnvironmentReads: counters.productionReads, productionDatabaseCalls: counters.productionSql,
    realFetchCalls: counters.globalFetch, hostIoCalls: counters.hostIo, dynamicImportCalls: counters.dynamicImport,
    memoryProviderPages: counters.pages, memoryImages: counters.images,
    wrapperIsolationProvedOffline: true, hostedQualified: false, nativeQualified: false }));
  db.raw.close();
});
