import nodeTest from 'node:test';
import assert from 'node:assert/strict';
import * as removal from '../src/album_local_removal_store.ts';
import * as title from '../src/album_title_store.ts';
import * as repair from '../src/album_create_repair_store.ts';
import * as materialization from '../src/album_materialization_store.ts';
import { NOW_US_SQL } from '../src/installations.ts';
import { removalFixture, nativeDatabase, rows, retained, AUTH, SET } from './album_local_removal_fixture.mjs';
import { unknownFixture, ADMIN } from './album_create_repair_fixture.mjs';

const test = (name, run) => nodeTest(name, { timeout: 120000 }, run);

const albumBody = (binding, attempt = null) => ({ schemaVersion: 1,
  expectedBindingRevision: binding.binding_revision, acknowledgedCreateAttemptId: attempt });
const pairBody = (binding, obligation) => ({ schemaVersion: 1,
  expectedBindingRevision: binding.binding_revision, expectedObligationRevision: obligation.obligation_revision });
const renameBody = (binding, desiredTitle = 'A deliberate competing rename') => ({ schemaVersion: 1,
  expectedBindingRevision: binding.binding_revision, expectedTitleRevision: binding.title_revision, desiredTitle });
const binding = f => f.db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
const archive = (f, body) => removal.putAlbumLocalRemoval(f.db, AUTH, f.bindingId, body);
const archivePair = (f, body, photo = 'later-photo') => removal.putAlbumPhotoLocalRemoval(f.db, AUTH, f.bindingId, photo, body);
async function nativeStore(t) {
  const db = await nativeDatabase(t);
  // Miniflare's RPC proxy ignores assigned properties. Interpose only this
  // ordinary adapter; all statements and transactions still execute in D1.
  return { prepare: sql => db.prepare(sql), batch: statements => db.batch(statements) };
}
const nativeFixture = async t => removalFixture(t, { db: await nativeStore(t) });
const obligations = f => f.db.prepare('SELECT * FROM album_photo_obligations WHERE album_binding_id=? ORDER BY rowid').bind(f.bindingId).all().then(r => r.results);

// Suspend only the first transaction after all of its application pre-reads.
// The competing transaction executes against the same actual D1 authority.
function firstBatchGate(db) {
  const batch = db.batch.bind(db); let reached, release, first = true;
  const pending = new Promise(resolve => reached = resolve), permit = new Promise(resolve => release = resolve);
  db.batch = async statements => { if (first) { first = false; reached(); await permit; } return batch(statements); };
  return { pending, release, restore: () => { db.batch = batch; } };
}
function immutableAlbumReceipt(receipt) { const { current, ...accepted } = receipt; return accepted; }
function immutablePairReceipt(receipt) { const { current, ...accepted } = receipt; return accepted; }

test('actual D1 duplicate album and pair archives return one immutable acceptance with no second mutation', async t => {
  for (const kind of ['album', 'pair']) {
    const f = await nativeFixture(t), beforeBinding = await binding(f), beforePairs = await obligations(f);
    const body = kind === 'album' ? albumBody(beforeBinding) : pairBody(beforeBinding, await f.obligation());
    const operation = () => kind === 'album' ? archive(f, body) : archivePair(f, body);
    const gate = firstBatchGate(f.db), delayed = operation(); await gate.pending;
    const winner = await operation(), snapshot = await retained(f.db); gate.release(); const replay = await delayed;
    assert.equal(winner.created, true); assert.equal(replay.created, false);
    assert.deepEqual(kind === 'album' ? immutableAlbumReceipt(replay.receipt) : immutablePairReceipt(replay.receipt),
      kind === 'album' ? immutableAlbumReceipt(winner.receipt) : immutablePairReceipt(winner.receipt));
    assert.deepEqual(await retained(f.db), snapshot);
    assert.equal((await binding(f)).binding_revision, beforeBinding.binding_revision + 1);
    for (const pair of await obligations(f)) {
      const old = beforePairs.find(row => row.obligation_id === pair.obligation_id);
      assert.equal(pair.obligation_revision, old.obligation_revision + (kind === 'album' || pair.photo_binding_id === 'later-photo' ? 1 : 0));
    }
  }
});

test('actual D1 album winning a pair race establishes the pair receipt at the same accepted revision', async t => {
  const f = await nativeFixture(t), b = await binding(f), body = pairBody(b, await f.obligation());
  const gate = firstBatchGate(f.db), delayed = archivePair(f, body); await gate.pending;
  const winner = await archive(f, albumBody(b)), snapshot = await retained(f.db); gate.release(); const replay = await delayed;
  assert.equal(replay.created, false); assert.equal(replay.receipt.acceptedBindingRevision, winner.receipt.acceptedBindingRevision);
  assert.equal(replay.receipt.archivedAt, winner.receipt.archivedAt); assert.deepEqual(await retained(f.db), snapshot);
});

test('actual D1 pair winning the album race forces fresh confirmation and never advances that pair twice', async t => {
  const f = await nativeFixture(t), b = await binding(f), gate = firstBatchGate(f.db);
  const delayed = archive(f, albumBody(b)); await gate.pending;
  const pair = await archivePair(f, pairBody(b, await f.obligation())), snapshot = await retained(f.db); gate.release();
  await assert.rejects(delayed, /stale_binding_revision/); assert.deepEqual(await retained(f.db), snapshot);
  const before = await f.obligation(), removed = await archive(f, albumBody(await binding(f)));
  assert.equal(removed.receipt.acceptedBindingRevision, b.binding_revision + 2);
  assert.deepEqual(await f.obligation(), before);
  const replay = await archivePair(f, pairBody(b, before));
  assert.deepEqual(immutablePairReceipt(replay.receipt), immutablePairReceipt(pair.receipt));
});

test('actual D1 distinct pair removals cannot both accept a stale shared binding revision', async t => {
  const f = await nativeFixture(t), b = await binding(f), first = await f.obligation('primary-photo');
  const gate = firstBatchGate(f.db), delayed = archivePair(f, pairBody(b, first), 'primary-photo'); await gate.pending;
  await archivePair(f, pairBody(b, await f.obligation())); const snapshot = await retained(f.db); gate.release();
  await assert.rejects(delayed, /stale_binding_revision/); assert.deepEqual(await retained(f.db), snapshot);
  assert.equal((await f.obligation('primary-photo')).local_relationship, 'active');
});

test('actual D1 title acceptance and album removal serialize in both orders without upgrading stale intent', async t => {
  for (const first of ['archive', 'rename']) {
    const f = await nativeFixture(t), b = await binding(f), body = renameBody(b), gate = firstBatchGate(f.db);
    const delayed = first === 'archive' ? archive(f, albumBody(b)) : title.putAlbumTitleIntent(f.db, AUTH, f.bindingId, b.title_revision + 1, body);
    await gate.pending;
    if (first === 'archive') await title.putAlbumTitleIntent(f.db, AUTH, f.bindingId, b.title_revision + 1, body);
    else await archive(f, albumBody(b));
    const snapshot = await retained(f.db); gate.release();
    await assert.rejects(delayed, /stale_binding_revision|album_closed/); assert.deepEqual(await retained(f.db), snapshot);
    const current = await binding(f);
    assert.equal(current.title_revision, b.title_revision + (first === 'archive' ? 1 : 0));
    assert.equal(current.state, first === 'archive' ? b.state : 'local_collection_removed_remote_preserved');
  }
});

test('actual D1 archive winning a title marker race prevents dispatch and retains the canceled exact title receipt', async t => {
  const f = await nativeFixture(t), initial = await binding(f), body = renameBody(initial, 'Retained exact title');
  const accepted = await title.putAlbumTitleIntent(f.db, AUTH, f.bindingId, initial.title_revision + 1, body);
  const claim = await title.claimAlbumTitle(f.db, f.bindingId); assert(claim);
  const read = await title.beginAlbumTitleRead(f.db, claim); assert(read);
  const gate = firstBatchGate(f.db), delayed = title.markAlbumTitleDispatch(f.db, read, { photosetId: SET, ownerNsid: 'owner', title: 'Synthetic album' });
  await gate.pending; await archive(f, albumBody(await binding(f))); const snapshot = await retained(f.db); gate.release();
  assert.equal(await delayed, null); assert.deepEqual(await retained(f.db), snapshot);
  assert.equal((await rows(f.db, 'album_title_attempts')).reduce((n, row) => n + row.dispatch_count, 0), 0);
  const replay = await title.putAlbumTitleIntent(f.db, AUTH, f.bindingId, initial.title_revision + 1, body);
  assert.equal(replay.created, false); assert.equal(replay.receipt.acceptedAt, accepted.receipt.acceptedAt);
  assert.equal(replay.receipt.current.title.state, 'local_removed'); assert.deepEqual(await retained(f.db), snapshot);
});

test('actual D1 title marker winning removal forces fresh confirmation while its immutable dispatch survives archive', async t => {
  const f = await nativeFixture(t), initial = await binding(f);
  await title.putAlbumTitleIntent(f.db, AUTH, f.bindingId, initial.title_revision + 1, renameBody(initial));
  const claim = await title.claimAlbumTitle(f.db, f.bindingId); assert(claim);
  const read = await title.beginAlbumTitleRead(f.db, claim); assert(read);
  const b = await binding(f), gate = firstBatchGate(f.db), delayed = archive(f, albumBody(b)); await gate.pending;
  const marker = await title.markAlbumTitleDispatch(f.db, read, { photosetId: SET, ownerNsid: 'owner', title: 'Synthetic album' }); assert(marker);
  const marked = await rows(f.db, 'album_title_attempts'), snapshot = await retained(f.db); gate.release();
  await assert.rejects(delayed, /stale_binding_revision/); assert.deepEqual(await retained(f.db), snapshot);
  const accepted = await archive(f, albumBody(await binding(f)));
  assert.equal(accepted.receipt.current.title.state, 'local_removed_reconciliation_pending');
  const preserved = (await rows(f.db, 'album_title_attempts'))[0];
  for (const key of ['attempt_id', 'binding_revision', 'title_revision', 'desired_title', 'photoset_id', 'dispatch_count', 'dispatched_at_us', 'pre_observed_title'])
    assert.deepEqual(preserved[key], marked[0][key], key);
  assert.equal(preserved.dispatch_count, 1); assert.equal(preserved.completed_at_us, null);
  const before = await retained(f.db);
  assert.equal(await title.markAlbumTitleDispatch(f.db, read, { photosetId: SET, ownerNsid: 'owner', title: 'Synthetic album' }), null);
  assert.deepEqual(await retained(f.db), before);
});

test('actual D1 current installation revocation wins before archive and receipt replay authority is checked again', async t => {
  for (const replay of [false, true]) {
    const f = await nativeFixture(t), body = albumBody(await binding(f));
    if (replay) await archive(f, body);
    const before = await retained(f.db), gate = firstBatchGate(f.db), delayed = archive(f, body); await gate.pending;
    await f.db.batch([
      f.db.prepare("UPDATE installation_credential_versions SET state='revoked' WHERE version_id='version'"),
      f.db.prepare("UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='install'"),
    ]);
    gate.release(); await assert.rejects(delayed, /invalid_token/); assert.deepEqual(await retained(f.db), before);
  }
});

async function unknownNative(t) { return unknownFixture(t, { db: await nativeStore(t), received: true }); }
async function prepareResolution(f) {
  const value = { schemaVersion: 1, expectedBindingRevision: (await binding(f)).binding_revision,
    createAttemptId: f.claim.attemptId, selectedPhotosetId: 'selected-set' };
  return { value, ...await repair.prepareAlbumResolution(f.db, ADMIN, f.bindingId, value) };
}
async function commitResolution(f, prepared) {
  const { now } = await f.db.prepare('SELECT ' + NOW_US_SQL + ' now').first();
  return repair.commitAlbumResolution(f.db, ADMIN, prepared.context, prepared.value, { photosetId: 'selected-set',
    url: 'https://www.flickr.com/photos/owner/albums/selected-set', ownerNsid: 'owner', firstPhotoId: 'primary-remote',
    contextIds: ['before-set', 'selected-set'], observedAt: new Date(now / 1000).toISOString().replace(/(\.\d{3})Z$/, '$1000Z') });
}

test('actual D1 archive fences an admin selection prepared before removal; fresh admin repair retains original archive receipt', async t => {
  const f = await unknownNative(t), prepared = await prepareResolution(f), b = await binding(f), attempts = await rows(f.db, 'album_materialization_attempts');
  const gate = firstBatchGate(f.db), delayed = commitResolution(f, prepared); await gate.pending;
  const archived = await archive(f, albumBody(b, f.claim.attemptId)), snapshot = await retained(f.db); gate.release();
  await assert.rejects(delayed, /stale_binding_revision|resolution_conflict/); assert.deepEqual(await retained(f.db), snapshot);
  const resolved = await commitResolution(f, await prepareResolution(f));
  assert.equal(resolved.binding.flickrPhotosetId, 'selected-set'); assert.equal((await binding(f)).state, 'local_collection_removed_remote_preserved');
  assert.deepEqual(await rows(f.db, 'album_materialization_attempts'), attempts);
  assert((await obligations(f)).every(row => row.local_relationship === 'archived'));
  const beforeReplay = await retained(f.db), replay = await archive(f, albumBody(b, f.claim.attemptId));
  assert.deepEqual(immutableAlbumReceipt(replay.receipt), immutableAlbumReceipt(archived.receipt));
  assert.equal(replay.receipt.current.unresolvedCreateAttemptId, null); assert.deepEqual(await retained(f.db), beforeReplay);
  await assert.rejects(archive(f, albumBody(b)), /removal_acknowledgement_conflict/);
});

test('actual D1 admin resolution winning removal race refuses the old acknowledgement and requires fresh facts', async t => {
  const f = await unknownNative(t), prepared = await prepareResolution(f), b = await binding(f), gate = firstBatchGate(f.db);
  const delayed = archive(f, albumBody(b, f.claim.attemptId)); await gate.pending;
  await commitResolution(f, prepared); const snapshot = await retained(f.db); gate.release();
  await assert.rejects(delayed, /stale_binding_revision/); assert.deepEqual(await retained(f.db), snapshot);
  await assert.rejects(archive(f, albumBody(await binding(f), f.claim.attemptId)), /removal_acknowledgement_conflict|removal_acknowledgement_required/);
  assert.deepEqual(await retained(f.db), snapshot);
  const accepted = await archive(f, albumBody(await binding(f)));
  assert.equal(accepted.receipt.repairHandoff.destination, 'none');
  assert.equal(accepted.receipt.current.binding.flickrPhotosetId, 'selected-set');
});

test('actual D1 stale original-create confirmation cannot acknowledge ambiguity discovered after its pre-read', async t => {
  const f = await removalFixture(t, { db: await nativeStore(t), materialized: false }), b = await binding(f);
  const claim = await materialization.claimAlbumMaterialization(f.db, f.bindingId); assert(claim);
  const marker = await materialization.markAlbumCreateDispatch(f.db, claim, []); assert(marker);
  const current = await binding(f), gate = firstBatchGate(f.db), delayed = archive(f, albumBody(current)); await gate.pending;
  assert(await materialization.unknownAlbumMaterialization(f.db, marker)); const snapshot = await retained(f.db); gate.release();
  await assert.rejects(delayed, /stale_binding_revision|removal_acknowledgement_conflict/); assert.deepEqual(await retained(f.db), snapshot);
  const accepted = await archive(f, albumBody(await binding(f), marker.attemptId));
  assert.equal(accepted.receipt.repairHandoff.createAttemptId, marker.attemptId);
  assert.equal(accepted.receipt.repairHandoff.acknowledgedAt, accepted.receipt.archivedAt);
  assert((await binding(f)).binding_revision > b.binding_revision);
});

test('actual D1 later-statement failure rolls back each archive revision, receipt and event together', async t => {
  for (const kind of ['album', 'pair']) {
    const f = await nativeFixture(t), b = await binding(f), body = kind === 'album' ? albumBody(b) : pairBody(b, await f.obligation());
    const operation = () => kind === 'album' ? archive(f, body) : archivePair(f, body);
    const original = f.db.batch.bind(f.db); let captured;
    f.db.batch = statements => { captured = statements; return original([...statements, f.db.prepare("SELECT json_extract('synthetic-invalid-json','$')")]); };
    const before = await retained(f.db); await assert.rejects(operation()); assert(captured?.length > 0);
    assert.deepEqual(await retained(f.db), before);
    f.db.batch = original; assert.equal((await operation()).created, true);
    const committed = await retained(f.db); await original(captured);
    assert.deepEqual(await retained(f.db), committed, 'captured stale transaction cannot advance revisions or rewrite acceptance');
    assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
  }
});

test('actual D1 ordinary SQL cannot erase, replace, rewrite or resurrect archive acceptance and relationships', async t => {
  const f = await nativeFixture(t); await archive(f, albumBody(await binding(f)));
  for (const table of ['album_local_removal_receipts', 'album_photo_local_removal_receipts']) {
    for (const sql of ['DELETE FROM ' + table, 'UPDATE ' + table + ' SET accepted_binding_revision=accepted_binding_revision',
      'INSERT OR REPLACE INTO ' + table + ' SELECT * FROM ' + table]) {
      const before = await retained(f.db); await assert.rejects(f.db.prepare(sql).run()); assert.deepEqual(await retained(f.db), before);
    }
  }
  for (const sql of ["UPDATE album_bindings SET state='active',binding_revision=binding_revision+1 WHERE binding_id=?",
    "UPDATE album_photo_obligations SET local_relationship='active',obligation_revision=obligation_revision+1 WHERE album_binding_id=?"]) {
    const before = await retained(f.db); await assert.rejects(f.db.prepare(sql).bind(f.bindingId).run()); assert.deepEqual(await retained(f.db), before);
  }
});

test('actual D1 raw archive requires a receipt and receipt insertion rejects forged, foreign and pending authority', async t => {
  const f = await nativeFixture(t), forged = 'd'.repeat(64), foreignDigest = 'e'.repeat(64), pendingDigest = 'f'.repeat(64);
  await f.db.batch([
    f.db.prepare("INSERT INTO fga_users VALUES('foreign-user')"),
    f.db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('foreign-install','foreign-user','lrc_plugin','active',1,'foreign-version')"),
    f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('foreign-version','foreign-install',?,'current',1)").bind(foreignDigest),
    f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install',?,'pending_rotation',2,${NOW_US_SQL}+300000000)`).bind(pendingDigest),
    f.db.prepare("UPDATE installations SET pending_version_id='pending',revision=revision+1 WHERE installation_id='install'"),
  ]);
  const b = await binding(f), pair = await f.obligation(), before = await retained(f.db);
  for (const sql of ["UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?",
    "UPDATE album_photo_obligations SET local_relationship='archived',obligation_revision=obligation_revision+1 WHERE album_binding_id=?"]) {
    await assert.rejects(f.db.prepare(sql).bind(f.bindingId).run()); assert.deepEqual(await retained(f.db), before);
  }
  for (const [installation, digest] of [['install', forged], ['foreign-install', foreignDigest], ['install', pendingDigest]]) {
    await assert.rejects(f.db.prepare(`INSERT INTO album_local_removal_receipts(binding_id,expected_binding_revision,accepted_binding_revision,
      acknowledged_create_attempt_id,installation_id,credential_digest) VALUES(?,?,?,NULL,?,?)`)
      .bind(f.bindingId, b.binding_revision, b.binding_revision + 1, installation, digest).run());
    assert.deepEqual(await retained(f.db), before);
    await assert.rejects(f.db.prepare(`INSERT INTO album_photo_local_removal_receipts(obligation_id,binding_id,photo_binding_id,
      expected_binding_revision,expected_obligation_revision,accepted_binding_revision,archived_obligation_revision,source,installation_id,credential_digest)
      VALUES(?,?,?,?,?,?,?,'photo',?,?)`).bind(pair.obligation_id, f.bindingId, pair.photo_binding_id,
      b.binding_revision, pair.obligation_revision, b.binding_revision + 1, pair.obligation_revision + 1, installation, digest).run());
    assert.deepEqual(await retained(f.db), before);
  }
  assert.equal((await archive(f, albumBody(b))).created, true, 'valid current credential remains authorized beside a pending version');
});
