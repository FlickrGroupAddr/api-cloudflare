import test from 'node:test';
import assert from 'node:assert/strict';
import { attachmentFixture, rows, retained, databaseClock, SET } from './album_attachment_fixture.mjs';
import { consumeAlbumAttachment } from '../src/album_attachment_worker.ts';
import { createSyntheticAlbumAttachmentTransport } from '../src/album_attachment_transport.ts';
import { signedAlbumRest } from '../src/flickr_reads.ts';
import * as attachment from '../src/album_attachment_store.ts';

const contexts = ids => ({ stat: 'ok', set: ids.map(id => ({ id, title: 'Synthetic album' })), pool: [] });
async function workerFixture(t, options = {}) {
  const f = await attachmentFixture(t, options);
  f.calls = []; f.responses = {}; f.hooks = {}; f.signs = []; f.admissions = []; let photoReads = 0;
  f.env = { DB: f.db, FGA_ALBUM_ATTACHMENT_ENABLED: '1' };
  f.factory = (identity, assertCurrent) => createSyntheticAlbumAttachmentTransport(identity, {
    assertCurrent,
    async beforeRequest(method) { f.admissions.push(method); await f.beforeRequest?.(method); },
    sign: (method, data) => { f.signs.push(method); return signedAlbumRest(method, data,
      { token: 'synthetic-token', tokenSecret: 'synthetic-secret' },
      { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' }); },
    async fetcher(request) {
      const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : new URL(request.url).searchParams;
      const method = params.get('method');
      const call = { method, params, request }; f.calls.push(call);
      if (request.method === 'POST') {
        assert.equal(method, 'flickr.photosets.addPhoto');
        const attempts = await f.attempts();
        assert.equal(attempts.at(-1).dispatch_count, 1, 'committed exact attempt marker precedes HTTP handoff');
        assert(attempts.at(-1).dispatch_started_at_us > 0);
      }
      const count = method === 'flickr.photos.getAllContexts' && params.get('photo_id') === 'later-remote' ? ++photoReads : f.calls.filter(c => c.method === method).length;
      await f.hooks[method]?.(call, count);
      let body = typeof f.responses[method] === 'function' ? await f.responses[method](call, count) : f.responses[method];
      body ??= method === 'flickr.photosets.getInfo'
        ? { stat: 'ok', photoset: { id: SET, owner: 'owner', primary: 'primary-remote', title: { _content: 'Synthetic album' } } }
        : method === 'flickr.photos.getAllContexts'
          ? contexts(params.get('photo_id') === 'primary-remote' || count > 1 ? [SET] : [])
          : { stat: 'ok' };
      return body instanceof Response ? body : Response.json(body);
    },
  });
  f.run = hooks => consumeAlbumAttachment(f.env, f.obligationId, f.factory, hooks);
  f.adds = () => f.calls.filter(call => call.method === 'flickr.photosets.addPhoto');
  return f;
}

test('default-off and pending materialization perform no provider work or attachment claim', async t => {
  const f = await workerFixture(t, { materialize: false });
  assert.equal(await consumeAlbumAttachment({ DB: f.db }, f.obligationId, assert.fail), 'disabled');
  assert.equal(await f.run(), 'no_work');
  assert.deepEqual(f.calls, []); assert.deepEqual(await f.attempts(), []);
});

test('actual local D1 worker completes strict existing membership without add and preserves primary create evidence', async t => {
  const f = await workerFixture(t, { native: true });
  f.responses['flickr.photos.getAllContexts'] = contexts([SET]);
  const primaryBefore = await f.db.prepare('SELECT * FROM album_photo_obligations WHERE obligation_id=?').bind(f.first.obligation.fgaAlbumObligationId).first();
  assert.equal(await f.run(), 'membership_verified');
  assert.equal(f.adds().length, 0);
  assert.equal((await f.obligation()).state, 'membership_verified');
  assert.deepEqual(await f.db.prepare('SELECT * FROM album_photo_obligations WHERE obligation_id=?').bind(f.first.obligation.fgaAlbumObligationId).first(), primaryBefore);
});

test('absent membership permits one committed add and success/code3 both require a later strict present read', async t => {
  for (const response of [{ stat: 'ok' }, { stat: 'fail', code: 3, message: 'Photo already in set' }]) {
    const f = await workerFixture(t); f.responses['flickr.photosets.addPhoto'] = response;
    assert.equal(await f.run(), 'membership_verified');
    assert.equal(f.adds().length, 1);
    assert.equal(f.adds()[0].params.get('photoset_id'), SET);
    assert.equal(f.adds()[0].params.get('photo_id'), 'later-remote');
    assert.equal(f.calls.at(-1).method, 'flickr.photos.getAllContexts');
    assert.equal((await f.obligation()).state, 'membership_verified');
    assert.equal((await f.attempts()).at(-1).dispatch_count, 1);
    assert.equal((await f.attempts()).at(-1).received_result, response.stat === 'ok' ? 'added' : 'already_present');
    assert((await f.attempts()).at(-1).received_at_us > 0);
  }
});

test('success and code3 with fresh absence schedule bounded retry instead of asserting membership', async t => {
  for (const response of [{ stat: 'ok' }, { stat: 'fail', code: 3, message: 'Already present' }]) {
    const f = await workerFixture(t); f.responses['flickr.photosets.addPhoto'] = response;
    f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' ? [SET] : []);
    assert.equal(await f.run(), 'retry_scheduled');
    assert.equal(f.adds().length, 1); assert.notEqual((await f.obligation()).state, 'membership_verified');
    const count = f.calls.length;
    assert.equal(await f.run(), 'no_work', 'persisted backoff blocks immediate retry');
    assert.equal(f.calls.length, count);
  }
});

test('ambiguous add recovers only through a complete fresh read and never retries in that invocation', async t => {
  for (const result of ['present', 'absent', 'unavailable']) {
    const f = await workerFixture(t);
    f.responses['flickr.photosets.addPhoto'] = () => { throw new Error('synthetic transport loss'); };
    f.responses['flickr.photos.getAllContexts'] = (call, count) => {
      if (call.params.get('photo_id') === 'primary-remote') return contexts([SET]);
      if (count === 1 || result === 'absent') return contexts([]);
      if (result === 'unavailable') return new Response('not JSON');
      return contexts([SET]);
    };
    assert.equal(await f.run(), result === 'present' ? 'membership_verified' : result === 'absent' ? 'retry_scheduled' : 'membership_reconciliation_pending');
    assert.equal(f.adds().length, 1);
    assert.equal((await f.obligation()).state === 'membership_verified', result === 'present');
  }
});

test('malformed/mixed/duplicate/incomplete preflight cannot authorize any add', async t => {
  for (const body of [{ stat: 'ok' }, contexts([SET, SET]), contexts(['bad id']), { stat: 'ok', set: [], pool: {} }, { stat: 'fail', code: 9999, message: 'Unknown' }]) {
    const f = await workerFixture(t); f.responses['flickr.photos.getAllContexts'] = call => call.params.get('photo_id') === 'primary-remote' ? contexts([SET]) : body;
    assert.equal(await f.run(), 'not_dispatched'); assert.equal(f.adds().length, 0);
    assert((await f.attempts()).every(attempt => attempt.dispatch_count === 0));
  }
});

test('wrong owner, missing album/photo and lost primary identity evidence stop in attention with no add', async t => {
  for (const kind of ['owner', 'album', 'photo', 'primary']) {
    const f = await workerFixture(t);
    if (kind === 'owner') f.responses['flickr.photosets.getInfo'] = { stat: 'ok', photoset: { id: SET, owner: 'foreign-owner', primary: 'primary-remote', title: { _content: 'Album' } } };
    if (kind === 'album') f.responses['flickr.photosets.getInfo'] = { stat: 'fail', code: 1, message: 'Album missing' };
    if (kind === 'photo') f.responses['flickr.photos.getAllContexts'] = call => call.params.get('photo_id') === 'primary-remote' ? contexts([SET]) : { stat: 'fail', code: 1, message: 'Photo missing' };
    if (kind === 'primary') f.responses['flickr.photos.getAllContexts'] = contexts([]);
    assert.equal(await f.run(), 'album_attachment_needs_attention', kind);
    assert.equal(f.adds().length, 0);
  }
});

test('archived accepted pending pair finishes once and later invocations cannot restore external drift', async t => {
  const f = await workerFixture(t); await f.archive();
  assert.equal(await f.run(), 'membership_verified'); assert.equal(f.adds().length, 1);
  const fulfilled = await retained(f.db), calls = f.calls.length;
  assert.equal((await f.obligation()).local_relationship, 'archived');
  f.responses['flickr.photos.getAllContexts'] = contexts([]);
  assert.equal(await f.run(), 'no_work');
  assert.equal(f.calls.length, calls); assert.deepEqual(await retained(f.db), fulfilled);
});

test('45 second invocation guard keeps final commit margin and refuses negative/nonfinite clocks', async t => {
  for (const time of [30_000, 40_000, 45_000, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
    const f = await workerFixture(t); let now = 0;
    f.hooks['flickr.photos.getAllContexts'] = call => { if (call.params.get('photo_id') === 'later-remote') now = time; };
    const outcome = await f.run({ monotonicMs: () => now });
    assert.equal(f.adds().length, 0, String(time));
    assert.notEqual(outcome, 'membership_verified');
    assert((await f.attempts()).every(attempt => attempt.dispatch_count === 0));
  }
});

test('per-request rate denial prevents signing, HTTP and dispatch before an add', async t => {
  for (const denied of ['flickr.photosets.getInfo', 'flickr.photosets.addPhoto']) {
    const f = await workerFixture(t);
    f.beforeRequest = method => { if (method === denied) throw new Error('synthetic_rate_capacity_denied'); };
    assert.equal(await f.run(), 'not_dispatched');
    assert(f.admissions.includes(denied));
    assert(!f.signs.includes(denied)); assert(!f.calls.some(call => call.method === denied));
    assert.equal(f.adds().length, 0);
    assert((await f.attempts()).every(attempt => attempt.dispatch_count === 0));
  }
});

test('post-dispatch rate denial preserves marker as pending and stops provider work', async t => {
  const f = await workerFixture(t); let infos = 0;
  f.beforeRequest = method => { if (method === 'flickr.photosets.getInfo' && ++infos === 2) throw new Error('synthetic_rate_capacity_denied'); };
  assert.equal(await f.run(), 'membership_reconciliation_pending');
  assert.equal(f.adds().length, 1);
  assert.equal(f.calls.filter(call => call.method === 'flickr.photosets.getInfo').length, 1);
  assert.equal((await f.attempts()).at(-1).dispatch_count, 1);
  assert.notEqual((await f.obligation()).state, 'membership_verified');
});

test('a recovered ambiguous claim performs reads only and requires a separate later invocation for another add', async t => {
  const f = await workerFixture(t), clock = databaseClock(f.db);
  f.responses['flickr.photosets.addPhoto'] = () => { throw new Error('synthetic transport loss'); };
  f.responses['flickr.photos.getAllContexts'] = (call, count) => {
    if (call.params.get('photo_id') === 'primary-remote') return contexts([SET]);
    if (count === 1) return contexts([]);
    throw new Error('synthetic read unavailable');
  };
  assert.equal(await f.run(), 'membership_reconciliation_pending');
  assert.equal(f.adds().length, 1);
  clock.set((await f.attempts()).at(-1).retry_after_us);
  f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' ? [SET] : []);
  assert.equal(await f.run(), 'retry_scheduled');
  assert.equal(f.adds().length, 1, 'fresh absent recovery does not resend in read-only claim');
  assert.equal((await f.attempts()).at(-1).reconciliation_only, 1);
  clock.set((await f.attempts()).at(-1).retry_after_us);
  f.responses['flickr.photosets.addPhoto'] = { stat: 'ok' };
  f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' || f.adds().length > 1 ? [SET] : []);
  assert.equal(await f.run(), 'membership_verified'); assert.equal(f.adds().length, 2);
});

test('active verified relationship may restore later external drift through a fresh distinct marked attempt', async t => {
  const f = await workerFixture(t);
  assert.equal(await f.run(), 'membership_verified');
  const eventsBefore = await f.events(), obligationsBefore = await rows(f.db, 'album_obligation_events');
  const before = await f.obligation(), bindingBefore = await f.db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
  f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' || f.adds().length > 1 ? [SET] : []);
  assert.equal(await f.run(), 'membership_verified');
  assert.equal(f.adds().length, 2);
  assert.equal((await f.attempts()).length, 2);
  assert.deepEqual((await f.events()).slice(0, eventsBefore.length), eventsBefore);
  const obligationsAfter = await rows(f.db, 'album_obligation_events');
  assert.deepEqual(obligationsAfter.slice(0, obligationsBefore.length), obligationsBefore);
  assert.equal(obligationsAfter.length, obligationsBefore.length + 2, 'drift marker and fresh presence each append one semantic event');
  assert.equal((await f.obligation()).obligation_revision, before.obligation_revision + 2);
  assert.equal((await f.db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first()).binding_revision, bindingBefore.binding_revision + 2);
});

test('authority change after preparation or committed marker prevents HTTP handoff', async t => {
  for (const phase of ['prepared', 'marked']) {
    const f = await workerFixture(t), original = f.factory;
    if (phase === 'prepared') f.factory = async (...args) => {
      const transport = await original(...args), prepare = transport.prepareAdd.bind(transport);
      transport.prepareAdd = async () => { const prepared = await prepare(); f.db.raw.exec("UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='user'"); return prepared; };
      return transport;
    };
    else {
      const batch = f.db.batch.bind(f.db);
      f.db.batch = async statements => {
        const results = await batch(statements);
        if ((await f.attempts()).some(row => row.dispatch_count === 1)) f.db.raw.exec("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'");
        return results;
      };
    }
    assert.equal(await f.run(), phase === 'prepared' ? 'not_dispatched' : 'membership_reconciliation_pending');
    assert.equal(f.adds().length, 0, phase);
    assert.equal((await f.attempts()).at(-1).dispatch_count, phase === 'prepared' ? 0 : 1);
  }
});

async function sevenDispatches(f) {
  const clock = databaseClock(f.db);
  for (let i = 0; i < 7; i++) {
    const claim = await attachment.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
    const marked = await attachment.markAlbumAttachmentDispatch(f.db, claim, []); assert(marked);
    assert(await attachment.deferAlbumAttachment(f.db, marked, { ownerNsid: 'owner', photoId: 'later-remote', contextIds: [] }));
    clock.set((await f.attempts()).at(-1).retry_after_us);
  }
  return clock;
}

test('eighth add followed by fresh absence terminalizes retry exhaustion and later work remains quiet', async t => {
  const f = await workerFixture(t); await sevenDispatches(f);
  f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' ? [SET] : []);
  assert.equal(await f.run(), 'album_attachment_needs_attention');
  assert.equal(f.adds().length, 1, 'seven retained markers plus this one exhaust eight dispatches');
  assert.equal((await f.attempts()).at(-1).attention_reason, 'retry_exhausted');
  const count = f.calls.length;
  assert.equal(await f.run(), 'no_work'); assert.equal(f.calls.length, count);
});

test('eighth ambiguous add stays read-only: later absent proof exhausts while present proof still verifies', async t => {
  for (const found of [false, true]) {
    const f = await workerFixture(t), clock = await sevenDispatches(f);
    f.responses['flickr.photosets.addPhoto'] = () => { throw new Error('synthetic transport loss'); };
    let targetReads = 0;
    f.responses['flickr.photos.getAllContexts'] = call => {
      if (call.params.get('photo_id') === 'primary-remote') return contexts([SET]);
      if (++targetReads > 1) throw new Error('synthetic read unavailable');
      return contexts([]);
    };
    assert.equal(await f.run(), 'membership_reconciliation_pending');
    clock.set((await f.attempts()).at(-1).retry_after_us);
    f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' || found ? [SET] : []);
    assert.equal(await f.run(), found ? 'membership_verified' : 'album_attachment_needs_attention');
    assert.equal(f.adds().length, 1);
    assert.equal((await f.attempts()).filter(row => row.dispatch_count === 1).length, 8);
  }
});

test('failure to commit an add response retains uncertainty and a later claim can only reconcile by reads', async t => {
  const f = await workerFixture(t), clock = databaseClock(f.db);
  f.db.raw.exec("CREATE TRIGGER attachment_test_receipt_failure BEFORE UPDATE ON album_attachment_attempts WHEN NEW.state='result_received' BEGIN SELECT RAISE(ABORT,'synthetic_receipt_commit_failure'); END");
  assert.equal(await f.run(), 'membership_reconciliation_pending');
  assert.equal(f.adds().length, 1);
  const unknown = (await f.attempts()).at(-1);
  assert.equal(unknown.state, 'membership_reconciliation_pending'); assert.equal(unknown.received_result, 'uncertain');
  assert.notEqual((await f.obligation()).state, 'membership_verified');
  f.db.raw.exec('DROP TRIGGER attachment_test_receipt_failure'); clock.set(unknown.retry_after_us);
  f.responses['flickr.photos.getAllContexts'] = contexts([SET]);
  assert.equal(await f.run(), 'membership_verified');
  assert.equal(f.adds().length, 1);
  assert.equal((await f.attempts()).at(-1).reconciliation_only, 1);
});

test('archiving marked active drift permits only read-only recovery: present resolves, absent needs attention, unavailable stays pending', async t => {
  for (const outcome of ['present', 'absent', 'unavailable']) {
    const f = await workerFixture(t), clock = databaseClock(f.db);
    assert.equal(await f.run(), 'membership_verified');
    let archived = false;
    f.hooks['flickr.photosets.addPhoto'] = async () => { if (!archived) { archived = true; await f.archive(); } };
    f.responses['flickr.photos.getAllContexts'] = call => contexts(call.params.get('photo_id') === 'primary-remote' ? [SET] : []);
    assert.equal(await f.run(), 'membership_reconciliation_pending', 'archive fences the in-flight proof commit while retaining the marked drift');
    assert.equal(f.adds().length, 2);
    const unknown = (await f.attempts()).at(-1); assert.equal(unknown.received_result, 'uncertain');
    clock.set(unknown.retry_after_us);
    f.responses['flickr.photos.getAllContexts'] = call => {
      if (call.params.get('photo_id') === 'primary-remote') return contexts([SET]);
      if (outcome === 'unavailable') throw new Error('synthetic read unavailable');
      return contexts(outcome === 'present' ? [SET] : []);
    };
    assert.equal(await f.run(), outcome === 'present' ? 'membership_verified' : outcome === 'absent' ? 'album_attachment_needs_attention' : 'membership_reconciliation_pending');
    const recovered = (await f.attempts()).at(-1);
    assert.equal(recovered.reconciliation_only, 1);
    assert.equal(recovered.dispatch_count, 0);
    if (outcome === 'absent') assert.equal(recovered.attention_reason, 'archived_drift_unresolved');
    assert.equal(f.adds().length, 2, 'no further add after archive');
    if (outcome !== 'unavailable') { const calls = f.calls.length; assert.equal(await f.run(), 'no_work'); assert.equal(f.calls.length, calls); }
    else { clock.set(recovered.retry_after_us); assert.equal(await f.run(), 'membership_reconciliation_pending'); assert.equal(f.adds().length, 2); }
  }
});
