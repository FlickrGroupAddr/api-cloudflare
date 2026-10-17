import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { loadOfflineModule } from './offline_modules.mjs';
import { createSyntheticStore } from './offline_sqlite.mjs';
import { ORIGIN, PATHS } from './wrapper.mjs';
import { createFaultFetch, png } from './fault_matrix.mjs';
import { collectResponse } from './collector.mjs';
import { EDGE_FAULT_CASES, EDGE_REDIRECT_CODES, MAX_EDGE_STIMULUS_BYTES, edgeReceiverPath, injectEdgeFault } from './edge_faults.mjs';

assert.equal(process.version, 'v24.22.0');
const fixture = process.env.FGA_OFFLINE_FIXTURE;
assert.ok(fixture, 'private fixture required');
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const manifest = JSON.parse(readFileSync(join(fixture, 'manifest.json'), 'utf8'));
assert.equal(manifest.candidateCommit, 'b599ca828d2a645b686aca0354d6c8ee2c2a0250');
assert.equal(hash(join(fixture, 'candidate.mjs')), 'c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36');
assert.equal(hash(join(fixture, 'captured.mjs')), 'f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d');
for (const [path, digest] of Object.entries(manifest.candidateSourceFiles)) assert.equal(hash(join(fixture, 'candidate', path)), digest);
const run = '1'.repeat(32);
const counters = { hostIo: 0, globalFetch: 0, dynamicImport: 0, syntheticSql: 0, pages: 0, images: 0, responderFailures: 0 };
const candidate = await loadOfflineModule(join(fixture, 'candidate.mjs'), counters);
const receipts = [];
for (const scenario of EDGE_FAULT_CASES) {
  test(`actual handler then post-handler stimulus: ${scenario}`, async () => {
    const db = createSyntheticStore(join(fixture, 'candidate/migrations'), counters);
    const before = { ...counters };
    const env = Object.freeze({ DB: db,
      FLICKR_APPLICATION: Object.freeze({ get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'synthetic', consumerSecret: 'synthetic' }) }),
      FLICKR_GRANT: Object.freeze({ get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'synthetic', tokenSecret: 'synthetic' }) }),
      FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1', FGA_PHOTO_THUMBNAILS_ENABLED: '1',
      FGA_ADMIN_ENABLED: '0', FGA_GROUPS_ENABLED: '0', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0',
      FGA_UPLOAD_AUTHORIZATION_ENABLED: '0', FGA_UPLOAD_PHOTO_BINDING_ENABLED: '0', FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '0' });
    try {
      const requestUrl = ORIGIN + PATHS[2];
      const worker = candidate.createWorker(createFaultFetch('png', db, counters));
      const response = await worker.fetch(new Request(requestUrl, { headers: { Authorization: 'Bearer ' + Array(13).fill('0000').join('-') } }), env);
      assert.equal(response.status, 200);
      assert.deepEqual(Buffer.from(await response.clone().arrayBuffer()), png());
      assert.equal(counters.responderFailures, 0);
      assert.equal(counters.pages, before.pages + 1);
      assert.equal(counters.images, before.images + 1);
      const final = await injectEdgeFault(response, { scenario, run, requestUrl });
      const bytes = Buffer.from(await final.clone().arrayBuffer());
      assert.ok(bytes.length <= MAX_EDGE_STIMULUS_BYTES);
      assert.equal(final.headers.get('Cache-Control'), 'private, no-store');
      if (scenario.startsWith('edge-redirect-')) {
        const code = Number(scenario.slice('edge-redirect-'.length));
        assert.equal(final.status, code);
        assert.equal(final.headers.get('Location'), ORIGIN + edgeReceiverPath(run, code));
        assert.equal(bytes.length, 0);
      } else {
        assert.equal(final.status, 200);
        assert.equal(final.headers.has('Location'), false);
        if (scenario === 'edge-wrong-media') assert.equal(final.headers.get('Content-Type'), 'text/html');
        if (scenario === 'edge-malformed-png') assert.equal(bytes.length, 12);
        if (scenario === 'edge-truncated-png') assert.equal(Number(final.headers.get('Content-Length')), bytes.length + 12);
        if (scenario.endsWith('excess')) assert.equal(bytes.length, 262145);
        if (scenario === 'edge-undeclared-excess') assert.equal(final.headers.has('Content-Length'), false);
      }
      const measured = await collectResponse(final);
      assert.equal(measured.accepted, !scenario.endsWith('excess'));
      assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n, 0);
      assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n, 0);
      receipts.push({ scenario, compliantHandlerStatus: 200, injectedStatus: measured.status, observedBytes: measured.observedBytes });
    } finally { db.raw.close(); }
  });
}
test('closed fault and receiver inputs reject arbitrary choices', async () => {
  for (const change of [{ scenario: 'edge-redirect-300' }, { scenario: 'png' }, { run: 'A'.repeat(32) }, { size: 262145 }, { destination: ORIGIN }, { delay: 1 },
    { requestUrl: ORIGIN + PATHS[1] }, { requestUrl: ORIGIN + PATHS[2] + '&size=1' }]) {
    await assert.rejects(injectEdgeFault(new Response(png()), { scenario: EDGE_FAULT_CASES[0], run, requestUrl: ORIGIN + PATHS[2], ...change }), /invalid_edge_fault_scope/);
  }
  for (const code of [300, 304, 305, 306, 309, '302']) assert.throws(() => edgeReceiverPath(run, code));
  await assert.rejects(injectEdgeFault(new Response(null, { status: 503 }), { scenario: EDGE_FAULT_CASES[0], run, requestUrl: ORIGIN + PATHS[2] }), /requires_compliant_handler/);
  assert.deepEqual(EDGE_REDIRECT_CODES, [301, 302, 303, 307, 308]);
});
test('nonprimitive run rejected without coercion or response consumption', async () => {
  let coercions = 0;
  const stateful = { toString() { return coercions++ === 0 ? run : 'different?query=1'; } };
  const values = [stateful, [run], new String(run), null, undefined, 123, true, Symbol('run')];
  for (const badRun of values) {
    assert.throws(() => edgeReceiverPath(badRun, 302), /invalid_edge_receiver/);
    const response = new Response(png(), { headers: { 'Content-Type': 'image/png',
      'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff' } });
    await assert.rejects(injectEdgeFault(response, { scenario: EDGE_FAULT_CASES[0], run: badRun,
      requestUrl: ORIGIN + PATHS[2] }), /invalid_edge_fault_scope/);
    assert.equal(response.bodyUsed, false);
    await response.body.cancel();
  }
  assert.equal(coercions, 0);
});
test('sanitized offline edge receipt keeps method unresolved', () => {
  assert.equal(receipts.length, 10);
  for (const key of ['hostIo', 'globalFetch', 'dynamicImport']) assert.equal(counters[key], 0);
  console.log(JSON.stringify({ schemaVersion: 1, kind: 'offline_post_handler_edge_stimuli', cases: receipts,
    hostedQualified: false, nativeQualified: false, supportedMethodResolved: false, receiverRequestsObserved: false }));
});
