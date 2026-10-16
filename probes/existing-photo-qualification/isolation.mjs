// Offline Node-isolate regression. No seed, database, provider fetch or shared module cache.
import assert from 'node:assert/strict';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import worker, { HARNESS_MARKER } from './worker.ts';

const gate = 'synthetic-isolation-gate-0000000000000000000000';
if (!isMainThread) {
  let databaseAccesses = 0;
  const db = new Proxy({}, { get() { databaseAccesses++; throw Error('unexpected_database_access'); } });
  const headers = { 'X-Probe-Case': 'missing-auth' };
  if (workerData.case === 'missing-auth') headers['X-Probe-Access'] = gate;
  if (workerData.case === 'wrong-gate') headers['X-Probe-Access'] = 'wrong';
  const request = new Request('https://probe.invalid/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1', { headers });
  const response = await worker.fetch(request, { DB: db, PROBE_ACCESS_TOKEN: gate });
  parentPort.postMessage({ case: workerData.case, status: response.status,
    bodyBytes: (await response.arrayBuffer()).byteLength, databaseAccesses,
    pages: response.headers.get('X-Probe-Pages'), images: response.headers.get('X-Probe-Images'),
    markerMatches: response.headers.get('X-FGA-Probe') === HARNESS_MARKER,
    noStore: response.headers.get('Cache-Control') === 'no-store',
    challenge: response.headers.get('WWW-Authenticate') === 'Bearer realm="fga-api"' });
} else {
  const results = [];
  for (const scenario of ['missing-auth', 'missing-gate', 'wrong-gate']) {
    const result = await new Promise((resolve, reject) => {
      const child = new Worker(new URL(import.meta.url), { workerData: { case: scenario } });
      child.once('message', resolve); child.once('error', reject);
      child.once('exit', code => { if (code !== 0) reject(Error('isolate_failed')); });
    });
    assert.equal(result.status, scenario === 'missing-auth' ? 401 : 404);
    assert.equal(result.bodyBytes, 0); assert.equal(result.databaseAccesses, 0);
    assert.equal(result.noStore, true);
    assert.equal(result.markerMatches, true);
    if (scenario === 'missing-auth') {
      assert.equal(result.pages, '0'); assert.equal(result.images, '0'); assert.equal(result.challenge, true);
    }
    results.push(result);
  }
  process.stdout.write(JSON.stringify(results));
}
