import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readJson } from '../src/flickr_reads.ts';
import { Miniflare } from 'miniflare';
import { sqlStore } from './sql_store.mjs';
import { budgetedFlickrFetch, reserveFlickrCapacity } from '../src/flickr_rate.ts';
import { createAlbumFlickrAdmission, createAlbumWorkerFaultGate } from '../src/album_flickr_admission.ts';
import { createSyntheticAlbumAttachmentTransport } from '../src/album_attachment_transport.ts';

const readMethod = 'flickr.photosets.getInfo';
const addMethod = 'flickr.photosets.addPhoto';
function request(method = readMethod, signal) {
  const post = method === addMethod || method === 'flickr.photosets.editMeta';
  const params = new URLSearchParams({ method, format: 'json', nojsoncallback: '1', photoset_id: 'album' });
  return new Request('https://www.flickr.com/services/rest/' + (post ? '' : '?' + params), {
    method: post ? 'POST' : 'GET', redirect: 'manual', signal,
    ...(post ? { body: params, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } } : {}),
  });
}
function setup(t) {
  const db = sqlStore();
  t.after(() => db.raw.close());
  db.raw.exec("INSERT INTO fga_users VALUES('user'); INSERT INTO flickr_links VALUES('user','owner',1,'linked'); INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1);");
  let calls = 0;
  const assertCurrent = async () => {
    const row = await db.prepare("SELECT 1 valid FROM flickr_links WHERE user_id='user' AND owner_nsid='owner' AND link_revision=1 AND state='linked'").first();
    if (!row) throw new Error('stale_current_authority');
  };
  const deps = { db, assertCurrent,
    assertFaultAllowed: createAlbumWorkerFaultGate(db, { userId: 'user', deploymentGateRevision: 1, userGateRevision: 1 }),
    fetcher: async () => { calls++; return Response.json({ stat: 'ok' }); } };
  return { db, deps, calls: () => calls };
}

test('construction fails closed without explicit network/current/fault dependencies', t => {
  const { deps } = setup(t);
  for (const key of ['db', 'fetcher', 'assertCurrent', 'assertFaultAllowed']) assert.throws(() => createAlbumFlickrAdmission({ ...deps, [key]: undefined }));
  assert.throws(() => createAlbumWorkerFaultGate(deps.db, { userId: 'user', deploymentGateRevision: 0, userGateRevision: 1 }));
});

test('candidate bulk reads and ordinary API calls share the key-wide capacity; capacity is not authority', async t => {
  const f = setup(t), admission = createAlbumFlickrAdmission(f.deps);
  await admission.reserveReads(21);
  for (let i = 0; i < 21; i++) await admission.fetcher(request(i === 0 ? 'flickr.photos.getAllContexts' : readMethod));
  await assert.rejects(admission.fetcher(request()));
  await assert.rejects(admission.fetcher(request(addMethod)));
  await budgetedFlickrFetch(f.db, f.deps.fetcher)(request());
  assert.equal(f.calls(), 22);
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 22);
  await f.db.prepare('UPDATE flickr_rate_window SET reserved_slots=40').run();
  const saturated = createAlbumFlickrAdmission(f.deps);
  await assert.rejects(saturated.reserveReads(21));
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 40);
  assert.equal(f.calls(), 22);
});

test('bulk bounds, unsupported methods and POST without matching credit cannot sign or send', async t => {
  const f = setup(t), admission = createAlbumFlickrAdmission(f.deps);
  for (const count of [0, -1, 22, 1.5, NaN]) await assert.rejects(admission.reserveReads(count));
  await assert.rejects(admission.beforeRequest('flickr.photos.delete'));
  assert.equal((await f.db.prepare('SELECT COUNT(*) n FROM flickr_rate_window').first()).n, 0);
  await admission.reserveReads(2);
  await assert.rejects(admission.fetcher(request(addMethod)));
  await assert.rejects(admission.fetcher(new Request('https://fixture.invalid/')));
  assert.equal(f.calls(), 0);
});

test('one-slot pre-sign hooks and private method credit prevent request replay', async t => {
  const f = setup(t), admission = createAlbumFlickrAdmission(f.deps);
  await admission.beforeRequest(addMethod);
  await assert.rejects(admission.fetcher(request(readMethod)));
  const req = request(addMethod), replay = req.clone();
  await admission.fetcher(req);
  await assert.rejects(admission.fetcher(replay));
  assert.equal(f.calls(), 1);
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 1);
});

test('window expiration and rotation invalidate charged credit without refund', async t => {
  const f = setup(t), admission = createAlbumFlickrAdmission(f.deps);
  await admission.reserveReads(2);
  await f.db.prepare('UPDATE flickr_rate_window SET expires_at_us=0').run();
  await assert.rejects(admission.fetcher(request()));
  await reserveFlickrCapacity(f.db);
  await assert.rejects(admission.fetcher(request()));
  assert.equal(f.calls(), 0);
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 1);
});

test('cancellation after reservation and during final authority check never enters network', async t => {
  const f = setup(t), abort = new AbortController();
  const admission = createAlbumFlickrAdmission({ ...f.deps, signal: abort.signal });
  await admission.beforeRequest(addMethod);
  abort.abort();
  await assert.rejects(admission.fetcher(request(addMethod)));
  const abort2 = new AbortController();
  let shouldAbort = false;
  const next = createAlbumFlickrAdmission({ ...f.deps, assertCurrent: async () => { if (shouldAbort) abort2.abort(); } });
  await next.beforeRequest(addMethod); shouldAbort = true;
  await assert.rejects(next.fetcher(request(addMethod, abort2.signal)));
  assert.equal(f.calls(), 0);
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 2);
});

test('committed-but-unknown allocation stays charged, poisons admission and never retries', async t => {
  const f = setup(t), originalBatch = f.db.batch.bind(f.db);
  let allocations = 0;
  f.db.batch = async statements => { allocations++; await originalBatch(statements); throw new Error('lost_commit_response'); };
  const admission = createAlbumFlickrAdmission(f.deps);
  await assert.rejects(admission.reserveReads(3));
  await assert.rejects(admission.reserveReads(3));
  await assert.rejects(admission.fetcher(request()));
  assert.equal(allocations, 1);
  assert.equal(f.calls(), 0);
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 3);
});

test('fault/link mutations during reservation stop before signing in actual attachment composition', async t => {
  for (const mutation of ["UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'", "UPDATE flickr_links SET state='paused',link_revision=link_revision+1 WHERE user_id='user'"]) {
    const f = setup(t), originalBatch = f.db.batch.bind(f.db);
    f.db.batch = async statements => { const result = await originalBatch(statements); await f.db.prepare(mutation).run(); return result; };
    let signs = 0;
    const admission = createAlbumFlickrAdmission(f.deps);
    const transport = createSyntheticAlbumAttachmentTransport({ attemptId: 'attempt', ownerNsid: 'owner', photosetId: 'album', photoId: 'photo', primaryPhotoId: 'primary' }, {
      ...admission, assertCurrent: f.deps.assertCurrent,
      sign() { signs++; throw new Error('unexpected_signing'); },
    });
    await assert.rejects(transport.read());
    assert.equal(signs, 0); assert.equal(f.calls(), 0);
    assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 1);
  }
});

test('final current assertion runs after credit admission and refuses a stale POST', async t => {
  const f = setup(t), admission = createAlbumFlickrAdmission(f.deps);
  await admission.beforeRequest(addMethod);
  const originalPrepare = f.db.prepare.bind(f.db);
  let mutated = false;
  f.db.prepare = sql => {
    const statement = originalPrepare(sql);
    if (sql.includes('remaining_us')) {
      const first = statement.first.bind(statement);
      statement.first = async () => { const row = await first(); mutated = true; await originalPrepare("UPDATE flickr_links SET state='paused',link_revision=2 WHERE user_id='user'").run(); return row; };
    }
    return statement;
  };
  await assert.rejects(admission.fetcher(request(addMethod)));
  assert.equal(mutated, true); assert.equal(f.calls(), 0);
});

test('expiry while the final authority await is pending stops the POST', async t => {
  const f = setup(t); let delay = false;
  const admission = createAlbumFlickrAdmission({ ...f.deps, assertCurrent: async () => {
    await f.deps.assertCurrent();
    if (delay) await new Promise(resolve => setTimeout(resolve, 10));
  } });
  await admission.beforeRequest(addMethod);
  const originalPrepare = f.db.prepare.bind(f.db);
  f.db.prepare = sql => {
    const statement = originalPrepare(sql);
    if (sql.includes('remaining_us')) {
      const first = statement.first.bind(statement);
      statement.first = async () => { const row = await first(); return row ? { ...row, remaining_us: 1000 } : row; };
    }
    return statement;
  };
  delay = true;
  await assert.rejects(admission.fetcher(request(addMethod)));
  assert.equal(f.calls(), 0);
});

test('concurrent replay cannot consume a one-slot POST credit twice', async t => {
  const f = setup(t), admission = createAlbumFlickrAdmission(f.deps);
  await admission.beforeRequest(addMethod);
  const outcomes = await Promise.allSettled([admission.fetcher(request(addMethod)), admission.fetcher(request(addMethod))]);
  assert.equal(outcomes.filter(item => item.status === 'fulfilled').length, 1);
  assert.equal(f.calls(), 1);
});

test('network ambiguity consumes credit once with no refund or retry', async t => {
  const f = setup(t); let sends = 0;
  const admission = createAlbumFlickrAdmission({ ...f.deps, fetcher: async () => { sends++; throw new Error('ambiguous_network'); } });
  await admission.beforeRequest(addMethod);
  await assert.rejects(admission.fetcher(request(addMethod)));
  await assert.rejects(admission.fetcher(request(addMethod)));
  assert.equal(sends, 1);
  assert.equal((await f.db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 1);
});

test('native local D1 enforces shared saturation, rollback, and final gate mutation without outbound traffic', async () => {
  let outbound = 0;
  const mf = new Miniflare({ modules: true, script: 'export default {fetch(){return new Response(null,{status:404})}}',
    compatibilityDate: '2026-07-30', compatibilityFlags: ['nodejs_compat'], cf: false, telemetry: { enabled: false },
    d1Databases: ['DB'], outboundService() { outbound++; throw new Error('no_external_traffic'); } });
  const source = sqlStore();
  try {
    const db = await mf.getD1Database('DB');
    const schema = source.raw.prepare("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 1 WHEN 'index' THEN 2 ELSE 3 END,rowid").all();
    await db.batch(schema.map(row => db.prepare(row.sql)));
    await db.batch([db.prepare("INSERT INTO fga_users VALUES('user')"), db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)")]);
    let calls = 0;
    const deps = { db, assertCurrent: async () => {}, assertFaultAllowed: createAlbumWorkerFaultGate(db, { userId: 'user', deploymentGateRevision: 1, userGateRevision: 1 }),
      fetcher: async () => { calls++; return new Response(); } };
    const admission = createAlbumFlickrAdmission(deps);
    await admission.reserveReads(21);
    await admission.fetcher(request());
    await budgetedFlickrFetch(db, deps.fetcher)(request());
    assert.equal((await db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 22);
    await db.prepare('UPDATE flickr_rate_window SET reserved_slots=59').run();
    const final = createAlbumFlickrAdmission(deps);
    await final.beforeRequest(addMethod);
    await assert.rejects(createAlbumFlickrAdmission(deps).reserveReads(2));
    assert.equal((await db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 60);
    await db.prepare("UPDATE flickr_write_gates SET enabled=0,revision=2 WHERE scope='deployment'").run();
    await assert.rejects(final.fetcher(request(addMethod)));
    assert.equal(calls, 2);
    await db.prepare("UPDATE flickr_write_gates SET enabled=1,revision=3 WHERE scope='deployment'").run();
    const mutatingDb = { prepare: db.prepare.bind(db), batch: async statements => {
      const result = await db.batch(statements);
      await db.prepare("UPDATE flickr_write_gates SET enabled=0,revision=4 WHERE scope='deployment'").run();
      return result;
    } };
    const mutated = createAlbumFlickrAdmission({ ...deps, db: mutatingDb,
      assertFaultAllowed: createAlbumWorkerFaultGate(db, { userId: 'user', deploymentGateRevision: 3, userGateRevision: 1 }) });
    await db.prepare('UPDATE flickr_rate_window SET reserved_slots=0').run();
    let signs = 0;
    await assert.rejects(mutated.beforeRequest(addMethod).then(() => { signs++; }));
    assert.equal(signs, 0); assert.equal(calls, 2);
    assert.equal((await db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 1);
    assert.equal((await db.prepare('SELECT COUNT(*) n FROM transaction_guards').first()).n, 0);
    assert.equal((await db.prepare('PRAGMA foreign_key_check').all()).results.length, 0);
    assert.equal(outbound, 0);
  } finally { source.raw.close(); await mf.dispose(); }
});
test('admitted shared reader cancellation survives forced GC through response bodies', { timeout: 20_000 }, async t => {
  if (typeof globalThis.gc !== 'function') {
    execFileSync(process.execPath, ['--expose-gc', '--test',
      '--test-name-pattern=^admitted shared reader cancellation survives forced GC through response bodies$', fileURLToPath(import.meta.url)],
    { timeout: 15_000, stdio: 'pipe' });
    return;
  }
  const f = setup(t);
  for (const headersReceived of [false, true]) for (const useRequestSignal of [false, true]) {
    const root = new AbortController();
    let signal, entered, finish, cancelled = false;
    const started = new Promise(resolve => { entered = resolve; });
    const pending = new Promise(resolve => { finish = resolve; });
    const response = () => new Response(new ReadableStream({
      pull() { if (headersReceived) entered(); }, cancel() { cancelled = true; },
    }), { headers: { 'Content-Type': 'application/json' } });
    const admission = createAlbumFlickrAdmission({ ...f.deps, signal: useRequestSignal ? undefined : root.signal,
      fetcher: next => {
        signal = next.signal;
        if (headersReceived) return Promise.resolve(response());
        entered(); return pending;
      } });
    await admission.reserveReads(1);
    const rejected = assert.rejects(readJson(request(readMethod, useRequestSignal ? root.signal : undefined),
      admission.fetcher, undefined, useRequestSignal ? {} : { signal: root.signal }), /upstream_unavailable/);
    await started;
    for (let n = 0; n < 8; n++) {
      await new Promise(resolve => setImmediate(resolve));
      globalThis.gc();
    }
    root.abort();
    await rejected;
    assert.equal(signal.aborted, true, 'innermost admitted request must abort after GC');
    if (!headersReceived) finish(response());
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(cancelled, true, 'admitted late/stalled response body must cancel');
  }
});
