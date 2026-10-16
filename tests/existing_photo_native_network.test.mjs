import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createNetworkProbe, CASES, LIMITS } from '../probes/existing-photo-native-network/worker.ts';

function fixture() {
  const raw = new DatabaseSync(':memory:');
  raw.exec(readFileSync('probes/existing-photo-native-network/schema.sql', 'utf8'));
  const expiry = Math.floor(Date.now() / 1000) + 600;
  const env = { ROLE: 'source', RUN_ID: '1234567890abcdef12345678', WORKERS_DEV_SUBDOMAIN: 'synthetic',
    EXPIRES_AT_UNIX: String(expiry), ACCESS_TOKEN: 'a'.repeat(64), CANARY_TOKEN: 'SYNTHETIC-' + 'b'.repeat(32),
    DB: { prepare(sql) { return { bind(...values) { return { async first() { return raw.prepare(sql).get(...values) ?? null; } }; } }; } } };
  for (const role of ['source', 'receiver']) raw.prepare('INSERT INTO network_probe_budget(run_id,role,expires_at_unix) VALUES(?,?,?)').run(env.RUN_ID, role, expiry);
  const url = (path, role = 'source') => `https://fga-native-network-${role === 'source' ? 'src' : 'recv'}-${env.RUN_ID}.synthetic.workers.dev${path}`;
  const request = (path, role = 'source', supplied = {}) => new Request(url(path, role), { headers: {
    'X-FGA-Network-Access': env.ACCESS_TOKEN, ...(role === 'source' ? { Authorization: 'Bearer ' + env.CANARY_TOKEN } : {}), ...supplied } });
  return { raw, env, url, request };
}

test('finite payloads, status and delay; redirects use only the two derived origins', async () => {
  const f = fixture(), delays = [], worker = createNetworkProbe(async ms => { delays.push(ms); });
  try {
    assert.equal(CASES.length, 8);
    for (const name of CASES) {
      const response = await worker.fetch(f.request('/v1/cases/' + name), f.env);
      const body = new Uint8Array(await response.arrayBuffer());
      assert.equal(response.headers.get('X-FGA-Network-Probe'), 'fga-native-network-v1');
      assert.equal(response.headers.get('Cache-Control'), 'no-store');
      if (name.startsWith('redirect-')) {
        assert.equal(response.status, 302); assert.equal(body.length, 0);
        assert.equal(response.headers.get('Location'), name === 'redirect-same' ? f.url('/v1/cases/png') : f.url('/v1/receive/' + f.env.RUN_ID, 'receiver'));
      } else {
        assert.equal(response.status, name === 'oversize-error' ? 503 : 200);
        const length = name === 'jpeg' ? 634 : name === 'boundary-image' ? 262144 : name.startsWith('oversize-') ? LIMITS.bytes : 68;
        assert.equal(body.length, length); assert.equal(response.headers.get('Content-Length'), String(length));
      }
    }
    assert.deepEqual(delays, [16000]);
  } finally { f.raw.close(); }
});

test('closed request surface rejects URLs, extra query, wrong origins, methods, real-looking credentials and missing gate', async () => {
  const f = fixture(), worker = createNetworkProbe();
  try {
    const requests = [f.request('/v1/cases/png?url=https://evil.invalid'), f.request('/v1/cases/unknown'),
      new Request('https://evil.invalid/v1/cases/png'),
      new Request(f.url('/v1/cases/png'), { method: 'POST' }),
      f.request('/v1/cases/png', 'source', { Authorization: 'Bearer actual-looking-credential' }),
      f.request('/v1/cases/png', 'source', { 'X-FGA-Network-Access': 'wrong' })];
    for (const request of requests) {
      const response = await worker.fetch(request, f.env);
      assert.equal(response.status, 404); assert.equal(response.headers.get('X-FGA-Network-Probe'), 'fga-native-network-v1');
    }
    assert.equal(f.raw.prepare("SELECT requests FROM network_probe_budget WHERE role='source'").get().requests, 0);
  } finally { f.raw.close(); }
});

test('receiver stores only aggregate canary booleans; report never counts itself as redirect receipt', async () => {
  const f = fixture(), worker = createNetworkProbe(), env = { ...f.env, ROLE: 'receiver' };
  try {
    const baseline = await worker.fetch(f.request('/v1/report', 'receiver'), env);
    assert.deepEqual(await baseline.json(), { schemaVersion: 1, receiverRequests: 0, authorizationObserved: false, canaryObserved: false });
    const target = f.url('/v1/receive/' + f.env.RUN_ID, 'receiver');
    const received = await worker.fetch(new Request(target, { headers: { Authorization: 'Bearer ' + env.CANARY_TOKEN } }), env);
    assert.deepEqual(await received.json(), { schemaVersion: 1, receiverReached: true, authorizationPresent: true, canaryMatched: true });
    const report = await worker.fetch(f.request('/v1/report', 'receiver'), env);
    const body = await report.text();
    assert.deepEqual(JSON.parse(body), { schemaVersion: 1, receiverRequests: 1, authorizationObserved: true, canaryObserved: true });
    assert(!body.includes(env.CANARY_TOKEN)); assert(!body.includes(env.ACCESS_TOKEN));
    assert.equal((await worker.fetch(f.request('/v1/report', 'receiver', { Authorization: 'Bearer ' + env.CANARY_TOKEN }), env)).status, 404);
    const row = f.raw.prepare("SELECT * FROM network_probe_budget WHERE role='receiver'").get();
    assert.equal(row.requests, 3); assert.equal(row.receiver_requests, 1);
    assert.equal(Object.keys(row).length, 7);
  } finally { f.raw.close(); }
});

test('single conditional SQL caps each independent role at32 across concurrent calls', async () => {
  const f = fixture(), worker = createNetworkProbe();
  try {
    const responses = await Promise.all(Array.from({ length: 64 }, () => worker.fetch(f.request('/v1/cases/png'), f.env)));
    assert.equal(responses.filter(r => r.status === 200).length, 32);
    assert.equal(responses.filter(r => r.status === 429).length, 32);
    assert.equal(f.raw.prepare("SELECT requests FROM network_probe_budget WHERE role='receiver'").get().requests, 0);
    assert.equal(f.raw.prepare("SELECT requests FROM network_probe_budget WHERE role='source'").get().requests, 32);
  } finally { f.raw.close(); }
});

test('expiry is enforced by config, authoritative SQL and after delayed response', async () => {
  const f = fixture(), worker = createNetworkProbe();
  try {
    assert.equal((await worker.fetch(f.request('/v1/cases/png'), { ...f.env, EXPIRES_AT_UNIX: '1' })).status, 410);
    assert.equal((await worker.fetch(f.request('/v1/cases/png'), { ...f.env, EXPIRES_AT_UNIX: String(Math.floor(Date.now() / 1000) + 1201) })).status, 410);
    f.raw.prepare("UPDATE network_probe_budget SET expires_at_unix=1 WHERE role='source'").run();
    assert.equal((await worker.fetch(f.request('/v1/cases/png'), f.env)).status, 429);
    const start = Math.floor(Date.now() / 1000), expiry = start + 10;
    f.raw.prepare("UPDATE network_probe_budget SET expires_at_unix=? WHERE role='source'").run(expiry);
    let now = start;
    const delayed = createNetworkProbe(async () => { now += 16; }, () => now);
    assert.equal((await delayed.fetch(f.request('/v1/cases/slow-response'), { ...f.env, EXPIRES_AT_UNIX: String(expiry) })).status, 410);
  } finally { f.raw.close(); }
});
