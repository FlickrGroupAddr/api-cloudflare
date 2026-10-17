import test from 'node:test';
import assert from 'node:assert/strict';
import { consumeAlbumMaterialization } from '../src/album_materialization_worker.ts';
import { ProvenNotDispatched } from '../src/dispatch_policy.ts';
import { AlbumCreateRejected } from '../src/album_materialization_transport.ts';
import { materializationFixture, contexts, created, info, PHOTO, SET, OWNER, URL as SET_URL } from './album_materialization_worker_fixture.mjs';

const CREATE = 'flickr.photosets.create', CONTEXT = 'flickr.photos.getAllContexts', INFO = 'flickr.photosets.getInfo';
const writes = f => f.calls.filter(call => call.request.method === 'POST');
const attempts = f => f.db.raw.prepare('SELECT * FROM album_materialization_attempts WHERE binding_id=? ORDER BY rowid').all(f.binding);

test('materialization is explicitly dormant before any claim, adapter or HTTP work', async t => {
  const f = await materializationFixture(t);
  for (const value of [undefined, '0', 'true', '']) {
    assert.equal(await consumeAlbumMaterialization({ DB: f.db, FGA_ALBUM_MATERIALIZATION_ENABLED: value }, f.binding, () => assert.fail('disabled adapter construction')), 'disabled');
  }
  assert.equal(f.calls.length, 0);
  assert.equal(attempts(f).length, 0);
});

test('actual worker/store/strict adapter commit a pre-context and marker before exactly one create, then satisfy primary by reads', async t => {
  const f = await materializationFixture(t);
  f.responses[CONTEXT] = (_request, count) => contexts(count === 1 ? ['existing-context'] : ['existing-context', SET]);
  f.hooks[CONTEXT] = (_request, count) => {
    if (count === 1) assert.equal(attempts(f)[0].dispatch_started_at_us, null);
  };
  f.hooks[CREATE] = request => {
    const attempt = attempts(f)[0];
    assert.ok(attempt.dispatch_started_at_us > 0);
    assert.equal(attempt.dispatch_count, 1);
    assert.match(JSON.stringify(attempt), /existing-context/);
    const query = f.calls.at(-1).params;
    assert.equal(query.get('primary_photo_id'), PHOTO);
    assert.equal(query.get('title'), 'Synthetic album');
  };
  assert.equal(await f.run(), 'materialized');
  assert.deepEqual(f.calls.map(call => call.method), [CONTEXT, CREATE, INFO, CONTEXT]);
  assert.equal(writes(f).length, 1);
  assert.equal(f.album().flickr_photoset_id, SET);
  assert.equal(f.obligation().state, 'membership_verified');
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

for (const [label, body] of [
  ['missing context arrays', { stat: 'ok' }],
  ['duplicate IDs', contexts(['duplicate', 'duplicate'])],
  ['mixed valid/invalid contexts', { stat: 'ok', set: [{ id: 'valid', title: 'x' }, { id: '', title: 'x' }], pool: [] }],
  ['failed response', { stat: 'fail', code: 1, message: 'Synthetic failure' }],
]) test(`strict pre-context ${label} prevents durable dispatch and POST`, async t => {
  const f = await materializationFixture(t); f.responses[CONTEXT] = body;
  assert.equal(await f.run(), 'not_dispatched');
  assert.equal(writes(f).length, 0);
  assert.equal(attempts(f)[0].dispatch_started_at_us, null);
  assert.equal(f.album().flickr_photoset_id, null);
});

test('link revocation during the fresh pre-context read prevents create', async t => {
  const f = await materializationFixture(t);
  f.hooks[CONTEXT] = () => f.db.raw.prepare("UPDATE flickr_links SET state='unlinked' WHERE user_id='user'").run();
  assert.equal(await f.run(), 'not_dispatched');
  assert.equal(writes(f).length, 0);
  assert.equal(f.album().flickr_photoset_id, null);
});

test('competing photo admission cannot replace immutable hosted primary', async t => {
  const f = await materializationFixture(t);
  f.hooks[CONTEXT] = async (_request, count) => {
    if (count === 1) await assert.rejects(f.ensure('competing-photo'), /album_binding_exists/);
  };
  assert.equal(await f.run(), 'materialized');
  assert.equal(writes(f)[0].params.get('primary_photo_id'), PHOTO);
  assert.equal(f.album().first_photo_binding_id, 'first-photo');
});

for (const [label, response] of [
  ['malformed success', { stat: 'ok', photoset: { id: SET } }],
  ['unknown application code', { stat: 'fail', code: 999999, message: 'Synthetic unknown' }],
  ['empty response', new Response('')],
]) test(`marked ${label} becomes unknown and a later invocation never creates again`, async t => {
  const f = await materializationFixture(t); f.responses[CREATE] = response;
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(f.obligation().state, 'waiting_for_album');
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
  assert.equal(attempts(f)[0].dispatch_count, 1);
});

for (const [label, failure] of [['transport exception', new Error('Synthetic lost result')], ['untrusted no-byte exception', new ProvenNotDispatched()]]) {
  test(`${label} after marker retains uncertainty and cannot authorize another create`, async t => {
    const f = await materializationFixture(t); f.hooks[CREATE] = () => { throw failure; };
    assert.equal(await f.run(), 'create_outcome_unknown');
    assert.equal(await f.run(), 'no_work');
    assert.equal(writes(f).length, 1);
    assert.equal(f.album().flickr_photoset_id, null);
  });
}

for (const [label, override] of [
  ['wrong owner', { [INFO]: info('foreign-owner') }],
  ['missing exact membership', { [CONTEXT]: (_request, count) => contexts(count === 1 ? [] : ['other-album']) }],
  ['malformed info', { [INFO]: { stat: 'ok', photoset: { id: SET, owner: OWNER } } }],
]) test(`${label} after create cannot commit album identity or primary membership`, async t => {
  const f = await materializationFixture(t); Object.assign(f.responses, override);
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(f.obligation().state, 'waiting_for_album');
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

test('external primary reordering still proves exact original photo membership', async t => {
  const f = await materializationFixture(t); f.responses[INFO] = info(OWNER, 'different-current-primary');
  assert.equal(await f.run(), 'materialized');
  assert.equal(f.obligation().state, 'membership_verified');
  assert.equal(writes(f).length, 1);
});

test('aborted pre-context HTTP never crosses the dispatch boundary', async t => {
  const f = await materializationFixture(t);
  f.hooks[CONTEXT] = () => { throw new DOMException('Synthetic abort', 'AbortError'); };
  assert.equal(await f.run(), 'not_dispatched');
  assert.equal(writes(f).length, 0);
  assert.equal(attempts(f)[0].dispatch_started_at_us, null);
});

test('a documented no-create rejection is terminal and records its classified code', async t => {
  const f = await materializationFixture(t); f.responses[CREATE] = { stat: 'fail', code: 1, message: 'Synthetic missing photo' };
  assert.equal(await f.run(), 'create_rejected');
  assert.equal(attempts(f)[0].flickr_code, 1);
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

for (const stage of ['pre-context', 'post-create']) test(`a fresh deployment fence changed at ${stage} prevents stale continuation`, async t => {
  const f = await materializationFixture(t);
  f.hooks[stage === 'pre-context' ? CONTEXT : CREATE] = () => f.db.raw.prepare("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'").run();
  assert.equal(await f.run(), stage === 'pre-context' ? 'not_dispatched' : 'create_outcome_unknown');
  assert.equal(writes(f).length, stage === 'pre-context' ? 0 : 1);
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(f.obligation().state, 'waiting_for_album');
});

function controlledClock(db) {
  let now = Date.now();
  db.raw.function('strftime', (format, _time) => {
    if (format === '%s') return String(Math.floor(now / 1000));
    if (format === '%f') return ((now % 60000) / 1000).toFixed(3).padStart(6, '0');
    throw new Error('Unexpected synthetic clock format');
  });
  return (milliseconds = 61000) => { now += milliseconds; };
}

test('expired pre-marker lease sends no create and a fresh invocation claims a newer epoch', async t => {
  const f = await materializationFixture(t), expire = controlledClock(f.db);
  f.hooks[CONTEXT] = () => { expire(); delete f.hooks[CONTEXT]; };
  assert.equal(await f.run(), 'not_dispatched');
  assert.equal(writes(f).length, 0);
  assert.equal(await f.run(), 'materialized');
  assert.equal(writes(f).length, 1);
  assert.equal(attempts(f).length, 2);
  assert.ok(attempts(f)[1].epoch > attempts(f)[0].epoch);
});

test('expired marked lease keeps unknown identity and never creates a successor', async t => {
  const f = await materializationFixture(t), expire = controlledClock(f.db);
  f.hooks[CREATE] = () => expire();
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
  assert.equal(attempts(f).length, 1);
  assert.equal(f.album().flickr_photoset_id, null);
});

test('lost result commit and lost unknown commit retain marker; expiry recovery cannot replay create', async t => {
  const f = await materializationFixture(t), expire = controlledClock(f.db);
  f.hooks[CONTEXT] = (_request, count) => { if (count === 2) f.db.fault = 0; };
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(attempts(f)[0].state, 'result_received');
  assert.equal(attempts(f)[0].received_photoset_id, SET);
  assert.equal(attempts(f)[0].received_navigation_url, SET_URL);
  assert.equal(attempts(f)[0].dispatch_count, 1);
  assert.equal(f.album().flickr_photoset_id, null);
  f.db.fault = -1; expire();
  assert.equal(await f.run(), 'no_work');
  assert.equal(attempts(f)[0].state, 'create_outcome_unknown');
  assert.equal(writes(f).length, 1);
  assert.equal(f.obligation().state, 'waiting_for_album');
});

test('actual disposed prepared request proves no HTTP handoff but cannot clear its durable marker', async t => {
  const f = await materializationFixture(t), actualFactory = f.factory;
  const outcome = await consumeAlbumMaterialization(f.env, f.binding, async (identity, assertCurrent) => {
    const transport = await actualFactory(identity, assertCurrent), prepare = transport.prepareCreate;
    return { ...transport, async prepareCreate() { const prepared = await prepare(); prepared.dispose(); return prepared; } };
  });
  assert.equal(outcome, 'create_outcome_unknown');
  assert.equal(writes(f).length, 0);
  assert.equal(attempts(f)[0].dispatch_count, 1);
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 0);
});

test('a rejection-shaped exception during post-create verification cannot classify an already successful create as rejected', async t => {
  const f = await materializationFixture(t);
  f.hooks[INFO] = () => { throw new AlbumCreateRejected(1); };
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(attempts(f)[0].flickr_code, null);
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

test('duplicate raw pre-context JSON member cannot become complete read evidence', async t => {
  const f = await materializationFixture(t);
  f.responses[CONTEXT] = new Response('{"stat":"ok","set":[],"set":[{"id":"hidden","title":"x"}],"pool":[]}', { headers: { 'Content-Type': 'application/json' } });
  assert.equal(await f.run(), 'not_dispatched');
  assert.equal(writes(f).length, 0);
});

test('duplicate raw create identity JSON member remains unknown after one dispatch', async t => {
  const f = await materializationFixture(t);
  f.responses[CREATE] = new Response('{"stat":"ok","photoset":{"id":"hidden","id":"synthetic-set","url":"https://www.flickr.com/photos/synthetic-owner/albums/synthetic-set/"}}', { headers: { 'Content-Type': 'application/json' } });
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

for (const elapsed of [29999, 30000]) test(`monotonic outbound budget at ${45000 - elapsed}ms requires strictly more than 15 seconds`, async t => {
  const f = await materializationFixture(t); let now = 0;
  f.hooks[CONTEXT] = (_request, count) => { if (count === 1) now = elapsed; };
  assert.equal(await f.run({ monotonicMs: () => now }), elapsed === 29999 ? 'materialized' : 'not_dispatched');
  assert.equal(writes(f).length, elapsed === 29999 ? 1 : 0);
});

for (const elapsed of [29999, 30000]) test(`owning database outbound budget at ${45000 - elapsed}ms requires strictly more than 15 seconds`, async t => {
  const f = await materializationFixture(t), advance = controlledClock(f.db);
  f.hooks[CONTEXT] = (_request, count) => { if (count === 1) advance(elapsed); };
  assert.equal(await f.run(), elapsed === 29999 ? 'materialized' : 'not_dispatched');
  assert.equal(writes(f).length, elapsed === 29999 ? 1 : 0);
});

test('a complete create result survives a post-create outbound margin refusal as candidate evidence only', async t => {
  const f = await materializationFixture(t); let now = 0;
  f.hooks[CREATE] = () => { now = 30000; };
  assert.equal(await f.run({ monotonicMs: () => now }), 'create_outcome_unknown');
  assert.equal(attempts(f)[0].received_photoset_id, SET);
  assert.equal(attempts(f)[0].received_navigation_url, SET_URL);
  assert.equal(f.calls.filter(call => call.method === INFO).length, 0);
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(f.obligation().state, 'waiting_for_album');
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

for (const elapsed of [39999, 40000]) test(`monotonic final commit budget at ${45000 - elapsed}ms requires strictly more than five seconds`, async t => {
  const f = await materializationFixture(t); let now = 0;
  f.hooks[CONTEXT] = (_request, count) => { if (count === 2) now = elapsed; };
  assert.equal(await f.run({ monotonicMs: () => now }), elapsed === 39999 ? 'materialized' : 'create_outcome_unknown');
  assert.equal(attempts(f)[0].received_photoset_id, SET);
  assert.equal(f.album().flickr_photoset_id, elapsed === 39999 ? SET : null);
  assert.equal(writes(f).length, 1);
});

for (const elapsed of [39999, 40000]) test(`owning database final commit budget at ${45000 - elapsed}ms requires strictly more than five seconds`, async t => {
  const f = await materializationFixture(t), advance = controlledClock(f.db);
  f.hooks[CONTEXT] = (_request, count) => { if (count === 2) advance(elapsed); };
  assert.equal(await f.run(), elapsed === 39999 ? 'materialized' : 'create_outcome_unknown');
  assert.equal(attempts(f)[0].received_photoset_id, SET);
  assert.equal(f.album().flickr_photoset_id, elapsed === 39999 ? SET : null);
  assert.equal(writes(f).length, 1);
});

test('durably received exact candidate is visible before owner proof and retained when proof fails', async t => {
  const f = await materializationFixture(t);
  f.hooks[INFO] = () => {
    const candidate = attempts(f)[0];
    assert.equal(candidate.state, 'result_received');
    assert.equal(candidate.received_photoset_id, SET);
    assert.equal(candidate.received_navigation_url, SET_URL);
    assert.ok(candidate.received_at_us > candidate.dispatch_started_at_us - 1);
    assert.equal(f.album().flickr_photoset_id, null);
    assert.equal(f.obligation().state, 'waiting_for_album');
  };
  f.responses[INFO] = info('foreign-owner');
  assert.equal(await f.run(), 'create_outcome_unknown');
  assert.equal(attempts(f)[0].received_photoset_id, SET);
  assert.equal(attempts(f)[0].received_navigation_url, SET_URL);
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

test('global 45-second expiry after create refuses candidate/result commits and never replays the marked call', async t => {
  const f = await materializationFixture(t); let now = 0;
  f.hooks[CREATE] = () => { now = 45000; };
  assert.equal(await f.run({ monotonicMs: () => now }), 'create_outcome_unknown');
  assert.equal(attempts(f)[0].state, 'dispatched');
  assert.equal(attempts(f)[0].received_photoset_id, null);
  assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(await f.run(), 'no_work');
  assert.equal(writes(f).length, 1);
});

test('timed-out pre-context does not continue to create when its late read eventually completes', async t => {
  const f = await materializationFixture(t); f.deadlineMs = 1;
  f.hooks[CONTEXT] = () => new Promise(resolve => setTimeout(resolve, 15));
  assert.equal(await f.run(), 'not_dispatched');
  await new Promise(resolve => setTimeout(resolve, 25));
  assert.equal(writes(f).length, 0);
  assert.equal(attempts(f)[0].dispatch_count, 0);
  assert.equal(f.album().flickr_photoset_id, null);
});
