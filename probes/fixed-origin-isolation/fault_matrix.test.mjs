import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { loadOfflineModule } from './offline_modules.mjs';
import { createSyntheticStore } from './offline_sqlite.mjs';
import { PATHS, ORIGIN } from './wrapper.mjs';
import { FAULT_CASES, createFaultFetch, png, JPEG_BASE64 } from './fault_matrix.mjs';
import { collectResponse } from './collector.mjs';

assert.equal(process.version, 'v24.22.0');
const fixture = process.env.FGA_OFFLINE_FIXTURE;
assert.ok(fixture, 'private fixture required');
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const manifest = JSON.parse(readFileSync(join(fixture, 'manifest.json'), 'utf8'));
assert.equal(manifest.candidateCommit, 'b599ca828d2a645b686aca0354d6c8ee2c2a0250');
assert.equal(hash(join(fixture, 'candidate.mjs')), 'c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36');
assert.equal(hash(join(fixture, 'captured.mjs')), 'f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d');
for (const [path, digest] of Object.entries(manifest.candidateSourceFiles)) assert.equal(hash(join(fixture, 'candidate', path)), digest);
const counters = { hostIo: 0, globalFetch: 0, dynamicImport: 0, syntheticSql: 0, pages: 0, images: 0, stalls: 0, stallCompleted: 0, cancelled: 0, responderFailures: 0 };
const candidate = await loadOfflineModule(join(fixture, 'candidate.mjs'), counters);
const receipts = [];
for (const [scenario, expected] of Object.entries(FAULT_CASES)) {
  test(`actual pinned thumbnail handler: ${scenario}`, async () => {
    const db = createSyntheticStore(join(fixture, 'candidate/migrations'), counters);
    const before = { ...counters };
    const env = Object.freeze({ DB: db,
      FLICKR_APPLICATION: Object.freeze({ get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'synthetic', consumerSecret: 'synthetic' }) }),
      FLICKR_GRANT: Object.freeze({ get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'synthetic', tokenSecret: 'synthetic' }) }),
      FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1', FGA_PHOTO_THUMBNAILS_ENABLED: '1',
      FGA_ADMIN_ENABLED: '0', FGA_GROUPS_ENABLED: '0', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0',
      FGA_UPLOAD_AUTHORIZATION_ENABLED: '0', FGA_UPLOAD_PHOTO_BINDING_ENABLED: '0', FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '0' });
    const worker = candidate.createWorker(createFaultFetch(scenario, db, counters));
    const headers = scenario === 'missing-auth' ? {} : { Authorization: 'Bearer ' + (scenario === 'bad-auth' ? 'invalid' : Array(13).fill('0000').join('-')) };
    const path = scenario === 'bad-query' ? PATHS[2] + '&unexpected=1' : PATHS[2];
    const started = performance.now();
    try {
      const response = await worker.fetch(new Request(ORIGIN + path, { headers }), env);
      assert.equal(response.status, expected);
      assert.equal(counters.responderFailures, 0, 'responder assertion/mutation errors must never count as fault passes');
      const elapsedMs = Math.round(performance.now() - started);
      const copy = response.clone();
      const receipt = await collectResponse(response);
      assert.equal(receipt.accepted, true);
      if (expected === 200) {
        const expectedBytes = scenario === 'jpeg' ? Buffer.from(JPEG_BASE64, 'base64') : png(scenario === 'exact-limit' ? 262144 : undefined);
        assert.deepEqual(Buffer.from(await copy.arrayBuffer()), expectedBytes);
        assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
        assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
      } else if (scenario === 'missing-auth') {
        assert.equal(receipt.observedBytes, 0);
        assert.equal(response.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
        await copy.arrayBuffer();
      } else {
        assert.match(response.headers.get('Content-Type'), /^application\/json/);
        assert.ok(receipt.observedBytes <= 4096);
        const error = await copy.text();
        assert.equal(error.includes('UPSTREAM_REJECTED_BODY'), false);
        assert.equal(error.includes('Synthetic'), false);
        assert.equal(JSON.parse(error).error !== undefined, true);
      }
      if (['missing-auth', 'bad-auth', 'bad-query'].includes(scenario)) {
        assert.equal(counters.pages, before.pages); assert.equal(counters.images, before.images);
      } else if (['foreign-identity', 'private-photo', 'foreign-destination'].includes(scenario)) {
        assert.equal(counters.pages, before.pages + 1); assert.equal(counters.images, before.images);
      } else { assert.equal(counters.pages, before.pages + 1); assert.equal(counters.images, before.images + 1); }
      if (scenario === 'stall') {
        assert.equal(counters.stalls, 1); assert.equal(counters.stallCompleted, 0); assert.equal(counters.cancelled, 1);
        assert.ok(elapsedMs >= 14900 && elapsedMs < 16000, 'actual 15000-ms deadline must beat single 16000-ms stall');
      }
      assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n, 0);
      assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n, 0);
      receipts.push(Object.freeze({ scenario, ...receipt, elapsedMs }));
    } finally { db.raw.close(); }
  });
}
test('sanitized finite collector rejects oversized denial with length-only evidence', async () => {
  const result = await collectResponse(new Response('PRIVATE_ERROR_BODY'.repeat(300), { status: 503 }));
  assert.deepEqual(Object.keys(result).sort(), ['accepted', 'limit', 'observedBytes', 'status']);
  assert.equal(result.accepted, false); assert.equal(result.limit, 4096); assert.ok(result.observedBytes > 4096);
  assert.equal(JSON.stringify(result).includes('PRIVATE_ERROR_BODY'), false);
  assert.equal((await collectResponse(new Response(new Uint8Array(4096), { status: 401 }))).accepted, true);
  assert.equal((await collectResponse(new Response(new Uint8Array(4097), { status: 401 }))).accepted, false);
});
test('offline receipt excludes qualification claims and host access', () => {
  assert.equal(receipts.length, Object.keys(FAULT_CASES).length);
  for (const counter of ['hostIo', 'globalFetch', 'dynamicImport']) assert.equal(counters[counter], 0);
  console.log(JSON.stringify({ schemaVersion: 1, kind: 'offline_actual_handler_fault_matrix',
    candidateCommit: manifest.candidateCommit, cases: receipts, realFetchCalls: counters.globalFetch,
    hostIoCalls: counters.hostIo, dynamicImportCalls: counters.dynamicImport,
    hostedQualified: false, nativeQualified: false, feasibilityVerdictChanged: false }));
});
