import test from 'node:test';
import { NOW_US_SQL } from '../src/installations.ts';
import assert from 'node:assert/strict';
import { materializationFixture, migrateMaterialization, through0021, retainedState, rows, databaseClock } from './album_materialization_sqlite.mjs';

const storage = () => import('../src/album_materialization_store.ts');
const result = (extra = {}) => ({ photosetId: 'created-set', url: 'https://www.flickr.com/photos/owner/albums/created-set',
  ownerNsid: 'owner', primaryPhotoId: 'primary-remote', contextIds: ['created-set'], ...extra });
const obligation = (f, photo = 'primary-photo') => f.db.raw.prepare('SELECT * FROM album_photo_obligations WHERE album_binding_id=? AND photo_binding_id=?').get(f.bindingId, photo);
const binding = f => f.db.raw.prepare('SELECT * FROM album_bindings WHERE binding_id=?').get(f.bindingId);
async function claimed(t) {
  const f = await materializationFixture(t), api = await storage();
  const claim = await api.claimAlbumMaterialization(f.db, f.bindingId);
  assert(claim, 'eligible production album must yield one claim');
  return { ...f, api, claim };
}
async function marked(t) {
  const f = await claimed(t), claim = await f.api.markAlbumCreateDispatch(f.db, f.claim, ['pre-existing-set']);
  assert(claim, 'strict pre-context evidence must commit the create marker');
  assert.equal(claim.dispatchCount, 1);
  return { ...f, claim };
}
async function received(t) {
  const f = await marked(t);
  assert.equal(await f.api.recordAlbumCreateResult(f.db, f.claim, result()), true);
  return f;
}
function delayFirstBatch(db) {
  const original = db.batch.bind(db); let reached, release, calls = 0;
  const pending = new Promise(resolve => reached = resolve), permit = new Promise(resolve => release = resolve);
  db.batch = async statements => { if (++calls === 1) { reached(); await permit; } return original(statements); };
  return { pending, release };
}

test('0022 preserves populated 0021 bindings, obligations and original event timestamps verbatim', async t => {
  const f = await materializationFixture(t, through0021());
  await f.associate();
  const other = await f.ensure('third-photo', 'ArchivedAlbum');
  f.db.raw.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?")
    .run(other.binding.fgaAlbumBindingId);
  const bound = await f.ensure('later-photo', 'KnownAlbum');
  f.db.raw.prepare("UPDATE album_bindings SET flickr_photoset_id='retained-set',binding_revision=binding_revision+1 WHERE binding_id=?").run(bound.binding.fgaAlbumBindingId);
  const tables = ['album_bindings', 'album_photo_obligations', 'album_binding_events', 'album_obligation_events'];
  const before = Object.fromEntries(tables.map(table => [table, rows(f.db, table).map(row => ({ ...row }))]));
  assert(before.album_obligation_events.some(event => event.kind === 'relationship_archived'));
  migrateMaterialization(f.db);
  for (const table of tables) assert.deepEqual(rows(f.db, table).map(row => Object.fromEntries(Object.keys(before[table][0]).map(key => [key, row[key]]))), before[table], table + ' migration preservation');
  assert.deepEqual(f.db.raw.prepare('PRAGMA foreign_key_check').all(), []);
  assert.equal(f.db.raw.prepare('SELECT materialization_state FROM album_bindings WHERE binding_id=?').get(bound.binding.fgaAlbumBindingId).materialization_state, 'materialized');
  assert.equal(rows(f.db, 'album_materialization_attempts').length, 0);
  assert.equal(rows(f.db, 'album_materialization_events').length, 0);
  const api = await storage();
  assert(await api.claimAlbumMaterialization(f.db, other.binding.fgaAlbumBindingId), 'accepted archived obligations continue');
  assert(await api.claimAlbumMaterialization(f.db, f.bindingId));
  assert.equal(await api.claimAlbumMaterialization(f.db, bound.binding.fgaAlbumBindingId), null);
});

test('competing committed photos keep one first candidate and one current materialization claim', async t => {
  const f = await materializationFixture(t), race = delayFirstBatch(f.db);
  const delayed = f.ensure('later-photo', 'RaceAlbum'); await race.pending;
  const winner = await f.ensure('third-photo', 'RaceAlbum'); race.release();
  await assert.rejects(delayed, /album_binding_exists/);
  const api = await storage(), gate = delayFirstBatch(f.db);
  const delayedClaim = api.claimAlbumMaterialization(f.db, winner.binding.fgaAlbumBindingId); await gate.pending;
  const firstClaim = await api.claimAlbumMaterialization(f.db, winner.binding.fgaAlbumBindingId); assert(firstClaim);
  gate.release(); assert.equal(await delayedClaim, null);
  assert.equal(firstClaim.photoBindingId, 'third-photo'); assert.equal(firstClaim.photoId, 'third-remote');
  assert.equal(rows(f.db, 'album_materialization_attempts').length, 1);
  assert.equal(binding(f).first_photo_binding_id, 'primary-photo');
});

test('a pre-marker failure releases only its own claim and permits a fresh fenced epoch', async t => {
  const f = await claimed(t);
  assert.equal(await f.api.failAlbumMaterializationBeforeDispatch(f.db, f.claim), true);
  const next = await f.api.claimAlbumMaterialization(f.db, f.bindingId); assert(next);
  assert(next.epoch > f.claim.epoch); assert.notEqual(next.leaseId, f.claim.leaseId);
  const before = retainedState(f.db);
  assert.equal(await f.api.currentAlbumMaterialization(f.db, f.claim), false);
  assert.equal(await f.api.markAlbumCreateDispatch(f.db, f.claim, []), null);
  assert.equal(await f.api.failAlbumMaterializationBeforeDispatch(f.db, f.claim), false);
  assert.equal(await f.api.unknownAlbumMaterialization(f.db, f.claim), false);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result()), false);
  assert.deepEqual(retainedState(f.db), before);
  assert(await f.api.currentAlbumMaterialization(f.db, next));
});

test('post-marker recovery cannot clear or replay create, including through pre-dispatch failure or a forged claim', async t => {
  const f = await marked(t), before = retainedState(f.db);
  assert.equal(await f.api.failAlbumMaterializationBeforeDispatch(f.db, f.claim), false);
  assert.equal(await f.api.markAlbumCreateDispatch(f.db, f.claim, []), null);
  assert.equal(await f.api.markAlbumCreateDispatch(f.db, { ...f.claim, dispatchCount: 0 }, []), null);
  assert.deepEqual(retainedState(f.db), before);
  assert.equal(await f.api.unknownAlbumMaterialization(f.db, f.claim), true);
  const unknown = retainedState(f.db);
  for (let retry = 0; retry < 3; retry++) assert.equal(await f.api.claimAlbumMaterialization(f.db, f.bindingId), null);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result()), false);
  assert.deepEqual(retainedState(f.db), unknown);
  assert.equal(binding(f).flickr_photoset_id, null);
  assert.equal(obligation(f).state, 'waiting_for_album');
});

test('only fresh exact owner, first photo and same returned photoset membership can complete the primary pair', async t => {
  const f = await received(t);
  await f.associate('later-photo', binding(f).binding_revision);
  for (const bad of [result({ ownerNsid: 'foreign-owner' }), result({ primaryPhotoId: 'later-remote' }),
    result({ contextIds: [] }), result({ contextIds: ['different-set'] }), result({ photosetId: 'bad id' }),
    result({ url: 'javascript:synthetic' })]) {
    const before = retainedState(f.db);
    assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, bad), false);
    assert.deepEqual(retainedState(f.db), before);
  }
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result()), true);
  assert.equal(binding(f).flickr_photoset_id, 'created-set');
  assert.equal(obligation(f).state, 'membership_verified');
  assert.equal(obligation(f, 'later-photo').state, 'waiting_for_album');
  assert.equal(rows(f.db, 'album_materialization_attempts').length, 1);
  assert.equal(rows(f.db, 'album_materialization_attempts')[0].dispatch_count, 1);
  const completed = retainedState(f.db);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result({ photosetId: 'different-set' })), false);
  assert.equal(await f.api.claimAlbumMaterialization(f.db, f.bindingId), null);
  assert.deepEqual(retainedState(f.db), completed);
});

const FENCES = [
  ["UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'", 'deployment pause'],
  ["UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='user'", 'user gate revision'],
  ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'", 'link revision'],
  ["UPDATE flickr_links SET state='paused' WHERE user_id='user'", 'link pause'],
  ["UPDATE flickr_native_credentials SET active_generation='new-gen' WHERE user_id='user'", 'grant generation'],
  ["UPDATE flickr_connection_state SET verified_permission=NULL,verified_at_us=NULL WHERE user_id='user'", 'grant proof'],
  ["UPDATE flickr_connection_state SET local_state='unknown' WHERE user_id='user'", 'connection availability'],
  ["UPDATE photo_bindings SET link_revision=2 WHERE binding_id='primary-photo'", 'first photo link'],
];
test('current authority fences are rechecked in marker, receipt and successful-result transactions', async t => {
  for (const [sql, label] of FENCES) {
    for (const phase of ['marker', 'receipt', 'result']) {
      const f = phase === 'marker' ? await claimed(t) : phase === 'receipt' ? await marked(t) : await received(t);
      const batch = f.db.batch.bind(f.db); let mutated = false;
      f.db.batch = async statements => {
        if (!mutated) { mutated = true; f.db.raw.exec(sql); }
        return batch(statements);
      };
      const value = phase === 'marker'
        ? await f.api.markAlbumCreateDispatch(f.db, f.claim, [])
        : phase === 'receipt' ? await f.api.recordAlbumCreateResult(f.db, f.claim, result()) : await f.api.finishAlbumMaterialization(f.db, f.claim, result());
      assert.equal(value, phase === 'marker' ? null : false, label + ' at ' + phase);
      assert.equal(binding(f).flickr_photoset_id, null, label);
      assert.notEqual(obligation(f).state, 'membership_verified', label);
      const attempt = rows(f.db, 'album_materialization_attempts')[0];
      assert.equal(attempt.dispatch_count, phase === 'marker' ? 0 : 1, label);
    }
  }
});

test('every statement failure rolls back claim, marker, receipt and result including trigger-owned events and obligations', async t => {
  const api = await storage();
  const operations = {
    claim: f => api.claimAlbumMaterialization(f.db, f.bindingId),
    marker: f => api.markAlbumCreateDispatch(f.db, f.claim, []),
    receipt: f => api.recordAlbumCreateResult(f.db, f.claim, result()),
    result: f => api.finishAlbumMaterialization(f.db, f.claim, result()),
  };
  for (const [phase, operation] of Object.entries(operations)) {
    const baseline = phase === 'claim' ? await materializationFixture(t) : phase === 'marker' ? await claimed(t) : phase === 'receipt' ? await marked(t) : await received(t);
    const batch = baseline.db.batch.bind(baseline.db); let length = 0;
    baseline.db.batch = statements => { length = Math.max(length, statements.length); return batch(statements); };
    await operation(baseline); assert(length > 0, phase + ' must use an atomic batch');
    for (let fault = 0; fault < length; fault++) {
      const f = phase === 'claim' ? await materializationFixture(t) : phase === 'marker' ? await claimed(t) : phase === 'receipt' ? await marked(t) : await received(t);
      const before = retainedState(f.db); f.db.fault = fault;
      try { await operation(f); } catch {}
      f.db.fault = -1;
      assert.deepEqual(retainedState(f.db), before, phase + ' statement ' + fault);
      assert.deepEqual(f.db.raw.prepare('PRAGMA foreign_key_check').all(), []);
    }
  }
});

test('an event insert failure rolls back the successful result and never strands a verified obligation', async t => {
  const f = await received(t), before = retainedState(f.db);
  f.db.raw.exec("CREATE TRIGGER test_event_commit_failure BEFORE INSERT ON album_materialization_events BEGIN SELECT RAISE(ABORT,'injected_event_commit_failure'); END");
  try { await f.api.finishAlbumMaterialization(f.db, f.claim, result()); } catch {}
  assert.deepEqual(retainedState(f.db), before);
});

test('ordinary SQL cannot erase marker or retained creation and membership evidence', async t => {
  const f = await received(t);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result()), true);
  for (const sql of [
    'DELETE FROM album_materialization_attempts',
    'DELETE FROM album_materialization_events',
    "UPDATE album_materialization_attempts SET dispatch_count=0",
    "UPDATE album_bindings SET flickr_photoset_id='replacement-set',binding_revision=binding_revision+1",
    "UPDATE album_photo_obligations SET state='waiting_for_album',obligation_revision=obligation_revision+1",
    'DELETE FROM album_obligation_events',
    "INSERT OR REPLACE INTO album_materialization_events SELECT * FROM album_materialization_events",
  ]) {
    const before = retainedState(f.db);
    assert.throws(() => f.db.raw.exec(sql), undefined, sql);
    assert.deepEqual(retainedState(f.db), before, sql);
  }
});

test('database-clock lease expiry permits only a newer unmarked epoch and conservatively terminalizes marked expiry', async t => {
  const api = await storage();
  for (const dispatched of [false, true]) {
    const f = await materializationFixture(t), clock = databaseClock(f.db);
    const original = await api.claimAlbumMaterialization(f.db, f.bindingId); assert(original);
    const claim = dispatched ? await api.markAlbumCreateDispatch(f.db, original, []) : original; assert(claim);
    const expiry = rows(f.db, 'album_materialization_attempts')[0].lease_expires_at_us;
    clock.set(expiry - 1000);
    assert.equal(await api.claimAlbumMaterialization(f.db, f.bindingId), null);
    assert.equal(await api.currentAlbumMaterialization(f.db, claim), false, 'invocation expired before lease');
    clock.set(expiry);
    assert.equal(await api.currentAlbumMaterialization(f.db, claim), false);
    if (dispatched) {
      f.db.raw.exec("UPDATE flickr_write_gates SET enabled=0,revision=revision+1; UPDATE flickr_native_credentials SET active_generation='new-gen'");
      assert.equal(await api.claimAlbumMaterialization(f.db, f.bindingId), null);
      const attempt = rows(f.db, 'album_materialization_attempts')[0];
      assert.equal(attempt.state, 'create_outcome_unknown'); assert.equal(attempt.dispatch_count, 1);
      assert.equal(binding(f).materialization_state, 'create_outcome_unknown');
    } else {
      const next = await api.claimAlbumMaterialization(f.db, f.bindingId); assert(next);
      assert.equal(next.epoch, claim.epoch + 1); assert.notEqual(next.leaseId, claim.leaseId);
      assert.equal(rows(f.db, 'album_materialization_attempts')[0].state, 'abandoned_before_dispatch');
    }
    const before = retainedState(f.db);
    assert.equal(await api.markAlbumCreateDispatch(f.db, claim, []), null);
    assert.equal(await api.finishAlbumMaterialization(f.db, claim, result()), false);
    assert.equal(await api.failAlbumMaterializationBeforeDispatch(f.db, claim), false);
    assert.equal(await api.unknownAlbumMaterialization(f.db, claim), false);
    assert.deepEqual(retainedState(f.db), before);
  }
});

test('changed title or malformed complete context evidence allocates no dispatch marker', async t => {
  for (const contexts of [['same', 'same'], ['bad id'], [null], ['0'], null, Array.from({ length: 1001 }, (_, i) => 'set-' + i)]) {
    const f = await claimed(t), before = retainedState(f.db);
    assert.equal(await f.api.markAlbumCreateDispatch(f.db, f.claim, contexts), null);
    assert.deepEqual(retainedState(f.db), before);
  }
  const f = await claimed(t);
  f.db.raw.exec("UPDATE album_bindings SET desired_title='New synthetic title',title_revision=title_revision+1,binding_revision=binding_revision+1");
  const before = retainedState(f.db);
  assert.equal(await f.api.markAlbumCreateDispatch(f.db, f.claim, []), null);
  assert.deepEqual(retainedState(f.db), before);
  assert.equal(rows(f.db, 'album_materialization_attempts')[0].dispatch_count, 0);
});

test('archived accepted first-photo obligations complete through the original marker and keep archived history', async t => {
  const f = await claimed(t);
  f.db.raw.exec("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1");
  const archived = rows(f.db, 'album_obligation_events');
  const claim = await f.api.markAlbumCreateDispatch(f.db, f.claim, []); assert(claim);
  assert.equal(await f.api.recordAlbumCreateResult(f.db, claim, result()), true);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, claim, result()), true);
  assert.equal(obligation(f).local_relationship, 'archived');
  assert.equal(obligation(f).state, 'membership_verified');
  assert.deepEqual(rows(f.db, 'album_obligation_events').slice(0, archived.length), archived);
  assert.equal(binding(f).state, 'local_collection_removed_remote_preserved');
});

test('a claimed but unmarked result cannot bind, and two album bindings cannot claim one remote photoset', async t => {
  const f = await claimed(t), before = retainedState(f.db);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result()), false);
  assert.deepEqual(retainedState(f.db), before);
  const first = await f.api.markAlbumCreateDispatch(f.db, f.claim, []); assert(first);
  assert.equal(await f.api.recordAlbumCreateResult(f.db, first, result()), true);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, first, result()), true);
  const other = await f.ensure('third-photo', 'DifferentAlbum');
  const next = await f.api.claimAlbumMaterialization(f.db, other.binding.fgaAlbumBindingId); assert(next);
  const markedOther = await f.api.markAlbumCreateDispatch(f.db, next, []); assert(markedOther);
  assert.equal(await f.api.recordAlbumCreateResult(f.db, markedOther, result()), true);
  const completedFirst = retainedState(f.db);
  await assert.rejects(f.api.finishAlbumMaterialization(f.db, markedOther, result({ primaryPhotoId: 'third-remote' })));
  assert.deepEqual(retainedState(f.db), completedFirst);
});

test('durable returned identity is required before proof and survives unknown without binding or replay', async t => {
  const f = await marked(t), unreceived = retainedState(f.db);
  assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, result()), false);
  assert.deepEqual(retainedState(f.db), unreceived);
  assert.equal(await f.api.recordAlbumCreateResult(f.db, f.claim, result()), true);
  const receivedAttempt = { ...rows(f.db, 'album_materialization_attempts')[0] };
  assert.equal(receivedAttempt.state, 'result_received');
  assert.equal(receivedAttempt.received_photoset_id, 'created-set');
  assert.equal(receivedAttempt.received_navigation_url, result().url);
  assert.equal(binding(f).flickr_photoset_id, null);
  assert.equal(obligation(f).state, 'waiting_for_album');
  for (const proof of [
    result({ photosetId: 'other-set', url: 'https://www.flickr.com/photos/owner/albums/other-set', contextIds: ['other-set'] }),
    result({ url: 'https://www.flickr.com/photos/owner/sets/created-set' }),
    result({ ownerNsid: 'other-owner' }), result({ contextIds: [] }),
  ]) {
    const before = retainedState(f.db);
    assert.equal(await f.api.finishAlbumMaterialization(f.db, f.claim, proof), false);
    assert.deepEqual(retainedState(f.db), before);
  }
  assert.equal(await f.api.unknownAlbumMaterialization(f.db, f.claim), true);
  const unknown = rows(f.db, 'album_materialization_attempts')[0];
  for (const key of ['received_photoset_id', 'received_navigation_url', 'received_at_us']) assert.equal(unknown[key], receivedAttempt[key]);
  assert.equal(binding(f).flickr_photoset_id, null);
  assert.equal(obligation(f).state, 'waiting_for_album');
  assert.equal(await f.api.claimAlbumMaterialization(f.db, f.bindingId), null);
  for (const sql of ["UPDATE album_materialization_attempts SET received_photoset_id='other-set'",
    'UPDATE album_materialization_attempts SET received_photoset_id=NULL,received_navigation_url=NULL,received_at_us=NULL']) {
    const before = retainedState(f.db);
    assert.throws(() => f.db.raw.exec(sql));
    assert.deepEqual(retainedState(f.db), before);
  }
});

const phaseFixture = (t, phase) => phase === 'marker' ? claimed(t) : phase === 'finish' ? received(t) : marked(t);
const phaseOperation = (f, phase) => phase === 'marker' ? f.api.markAlbumCreateDispatch(f.db, f.claim, [])
  : phase === 'receipt' ? f.api.recordAlbumCreateResult(f.db, f.claim, result())
  : phase === 'finish' ? f.api.finishAlbumMaterialization(f.db, f.claim, result())
  : f.api.rejectAlbumMaterialization(f.db, f.claim, 3);
const rawPhase = (phase, contexts = '[]') => phase === 'marker'
  ? "UPDATE album_materialization_attempts SET state='dispatched',dispatch_count=1,dispatch_started_at_us=" + NOW_US_SQL + ",pre_context_observed_at_us=" + NOW_US_SQL + ",pre_context_ids='" + contexts + "'"
  : phase === 'receipt' ? "UPDATE album_materialization_attempts SET state='result_received',received_photoset_id='created-set',received_navigation_url='" + result().url + "',received_at_us=" + NOW_US_SQL
  : phase === 'finish' ? "UPDATE album_materialization_attempts SET state='verified',completed_at_us=" + NOW_US_SQL + ",photoset_id='created-set',navigation_url='" + result().url + "',proof_context_ids='[\"created-set\"]',proof_owner_nsid='owner',proof_photo_id='primary-remote',proof_observed_at_us=" + NOW_US_SQL
  : "UPDATE album_materialization_attempts SET state='create_rejected',flickr_code=3,completed_at_us=" + NOW_US_SQL;

test('database invocation margins are strict for current checks, marker, receipt, proof and rejection including direct SQL', async t => {
  for (const phase of ['marker', 'receipt', 'finish', 'reject']) {
    const margin = phase === 'marker' ? 15000000 : 5000000;
    for (const remaining of [margin + 1000, margin, margin - 1000]) {
      const f = await phaseFixture(t, phase), clock = databaseClock(f.db);
      const attempt = rows(f.db, 'album_materialization_attempts')[0];
      assert.equal(attempt.invocation_deadline_at_us - attempt.started_at_us, 45000000);
      assert.equal(attempt.lease_expires_at_us - attempt.started_at_us, 60000000);
      clock.set(attempt.invocation_deadline_at_us - remaining);
      assert.equal(await f.api.currentAlbumMaterialization(f.db, f.claim, margin), remaining > margin);
      const before = retainedState(f.db), value = await phaseOperation(f, phase);
      if (remaining > margin) assert(value, phase + ' should retain its required margin');
      else {
        assert.equal(value, phase === 'marker' ? null : false, phase);
        assert.deepEqual(retainedState(f.db), before, phase);
        assert.throws(() => f.db.raw.exec(rawPhase(phase)), undefined, phase + ' SQL cannot bypass deadline');
        assert.deepEqual(retainedState(f.db), before, phase);
      }
    }
  }
});

test('unknown and null Flickr rejection codes cannot bypass closed no-creation classification in API or SQL', async t => {
  const f = await marked(t);
  for (const code of [999999, 0, -1, null, '1', NaN]) {
    const before = retainedState(f.db);
    assert.equal(await f.api.rejectAlbumMaterialization(f.db, f.claim, code), false);
    assert.deepEqual(retainedState(f.db), before);
  }
  for (const code of [999999, null]) {
    const before = retainedState(f.db);
    assert.throws(() => f.db.raw.prepare('UPDATE album_materialization_attempts SET state=\'create_rejected\',flickr_code=?,completed_at_us=' + NOW_US_SQL).run(code));
    assert.deepEqual(retainedState(f.db), before);
  }
  for (const code of [1, 3, 95, 100]) {
    const accepted = await marked(t);
    assert.equal(await accepted.api.rejectAlbumMaterialization(accepted.db, accepted.claim, code), true);
    assert.equal(rows(accepted.db, 'album_materialization_attempts')[0].flickr_code, code);
    assert.equal(await accepted.api.claimAlbumMaterialization(accepted.db, accepted.bindingId), null);
    assert.equal(binding(accepted).flickr_photoset_id, null);
  }
});

test('ordinary SQL cannot skip result receipt, change the returned identity or substitute null proof', async t => {
  const unreceived = await marked(t), before = retainedState(unreceived.db);
  assert.throws(() => unreceived.db.raw.exec(rawPhase('finish')), undefined, 'receipt cannot be skipped');
  assert.deepEqual(retainedState(unreceived.db), before);
  for (const phase of ['receipt', 'finish']) {
    const f = await phaseFixture(t, phase), original = retainedState(f.db);
    const sql = rawPhase(phase);
    for (const mutation of phase === 'receipt'
      ? [sql.replace("received_photoset_id='created-set'", 'received_photoset_id=NULL'),
        sql.replace("received_navigation_url='" + result().url + "'", 'received_navigation_url=NULL'),
        sql.replace('received_at_us=' + NOW_US_SQL, 'received_at_us=NULL')]
      : [sql.replace("photoset_id='created-set'", "photoset_id='different-set'"),
        sql.replace("proof_owner_nsid='owner'", 'proof_owner_nsid=NULL'),
        sql.replace("proof_photo_id='primary-remote'", 'proof_photo_id=NULL'),
        sql.replace('proof_observed_at_us=' + NOW_US_SQL, 'proof_observed_at_us=NULL')]) {
      assert.throws(() => f.db.raw.exec(mutation));
      assert.deepEqual(retainedState(f.db), original);
    }
  }
});

test('raw SQL complete-context guards reject null, zero, duplicate and over-budget sets before a marker', async t => {
  for (const contexts of ['null', '[null]', '["0"]', '["same","same"]', JSON.stringify(Array.from({ length: 1001 }, (_, i) => 'set-' + i))]) {
    const f = await claimed(t), before = retainedState(f.db);
    assert.throws(() => f.db.raw.exec(rawPhase('marker', contexts)));
    assert.deepEqual(retainedState(f.db), before);
  }
});

test('result-receipt event failure rolls back candidate evidence and its audit together', async t => {
  const f = await marked(t), before = retainedState(f.db);
  f.db.raw.exec("CREATE TRIGGER test_received_event_failure BEFORE INSERT ON album_materialization_events WHEN NEW.state='result_received' BEGIN SELECT RAISE(ABORT,'injected_receipt_event_failure'); END");
  await assert.rejects(f.api.recordAlbumCreateResult(f.db, f.claim, result()));
  assert.deepEqual(retainedState(f.db), before);
});
