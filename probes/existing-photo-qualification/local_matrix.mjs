// Node integration adapter only; the hosted artifact imports no test adapter.
import { sqlStore } from '../../tests/sql_store.mjs';
import worker, { CASES, TOKEN } from './worker.ts';
const db = sqlStore();
const env = { DB: db, PROBE_ACCESS_TOKEN: 'synthetic-local-access-000000000000000000' };
const snapshots = [];
const request = (path, headers = {}) => new Request('https://probe.invalid' + path, { headers });
const thumbnail = '/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1';
try {
  const denied = await worker.fetch(request(thumbnail), env);
  if (denied.status !== 404 || (await denied.text()) !== '') throw Error('gate_failure');
  const unknown = await worker.fetch(request('/arbitrary', { 'X-Probe-Access': env.PROBE_ACCESS_TOKEN }), env);
  if (unknown.status !== 404) throw Error('route_gate');
  await worker.fetch(request('/__probe/seed', { 'X-Probe-Access': env.PROBE_ACCESS_TOKEN }), env);
  for (const scenario of CASES) {
    let path = thumbnail;
    const headers = { Authorization: 'Bearer ' + TOKEN, 'X-Probe-Access': env.PROBE_ACCESS_TOKEN, 'X-Probe-Case': scenario };
    if (scenario === 'discovery') path = '/api/v001/existing-public-photos?page=1&page_size=1';
    if (scenario === 'missing-auth') delete headers.Authorization;
    if (scenario === 'bad-auth') headers.Authorization = 'Bearer ' + TOKEN.slice(0, -1) + 'G';
    if (scenario === 'bad-query') path += '&url=https://example.invalid/';
    if (scenario === 'wrong-revision') path = path.replace('revision=1', 'revision=2');
    if (scenario === 'generation-change' || scenario === 'revoke') path = path.replace('revision=1', 'revision=2');
    const started = performance.now();
    const response = await worker.fetch(request(path, headers), env);
    snapshots.push({ scenario, status: response.status, headers: Object.fromEntries(response.headers),
      body: Buffer.from(await response.arrayBuffer()).toString('base64'), elapsedMs: Math.round(performance.now() - started) });
  }
  if (db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n !== 0) throw Error('binding_created');
  if (db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n !== 0) throw Error('intent_created');
  process.stdout.write(JSON.stringify(snapshots));
} finally { db.raw.close(); }
