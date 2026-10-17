import test from 'node:test';
import assert from 'node:assert/strict';
import { removalFixture, nativeDatabase, retained, rows, splitMigrations, AUTH } from './album_local_removal_fixture.mjs';
import * as api from '../src/album_local_removal_store.ts';
import * as title from '../src/album_title_store.ts';
import * as materialization from '../src/album_materialization_store.ts';
import { associateAlbumPhoto } from '../src/album_obligation_store.ts';

const albumBody = (binding, acknowledgement = null) => ({ schemaVersion: 1, expectedBindingRevision: binding.binding_revision, acknowledgedCreateAttemptId: acknowledgement });
const photoBody = (binding, obligation) => ({ schemaVersion: 1, expectedBindingRevision: binding.binding_revision, expectedObligationRevision: obligation.obligation_revision });
const archive = async (f, acknowledgement = null) => api.putAlbumLocalRemoval(f.db, AUTH, f.bindingId, albumBody(await f.binding(), acknowledgement));
const rename = async f => { const b = await f.binding(); return title.putAlbumTitleIntent(f.db, AUTH, f.bindingId, b.title_revision + 1, { schemaVersion: 1, expectedBindingRevision: b.binding_revision, expectedTitleRevision: b.title_revision, desiredTitle: 'Retained last title' }); };

function originalRowsRemain(before, after, tables) {
  for (const table of tables) for (const row of before[table]) assert(after[table].some(candidate => JSON.stringify(candidate) === JSON.stringify(row)), table + ' retains original row');
}

test('photo archive preserves membership and exact natural-key receipt while new removals never create obligations', async t => {
  const f = await removalFixture(t), b = await f.binding(), obligation = await f.obligation();
  const body = photoBody(b, obligation), first = await api.putAlbumPhotoLocalRemoval(f.db, AUTH, f.bindingId, 'later-photo', body);
  assert.equal(first.created, true); assert.equal(first.receipt.localRelationship, 'archived');
  assert.equal(first.receipt.acceptedBindingRevision, b.binding_revision + 1);
  assert.equal(first.receipt.obligation.obligationRevision, obligation.obligation_revision + 1);
  const current = await f.obligation(); assert.equal(current.state, obligation.state); assert.equal(current.photo_id, obligation.photo_id);
  assert.equal(current.local_relationship, 'archived'); assert.equal(current.obligation_id, obligation.obligation_id);
  const before = await retained(f.db), replay = await api.putAlbumPhotoLocalRemoval(f.db, AUTH, f.bindingId, 'later-photo', body);
  assert.equal(replay.created, false); assert.deepEqual(replay.receipt, first.receipt); assert.deepEqual(await retained(f.db), before);
  await assert.rejects(api.putAlbumPhotoLocalRemoval(f.db, AUTH, f.bindingId, 'third-photo', photoBody(await f.binding(), current)), /resource_not_found/);
  assert.deepEqual(await retained(f.db), before);
});

test('album archive preserves IDs, accepted pending attachments and history and closes new admission', async t => {
  const f = await removalFixture(t), b = await f.binding(), before = await retained(f.db);
  const first = await archive(f); assert.equal(first.created, true); assert.equal(first.receipt.acceptedBindingRevision, b.binding_revision + 1);
  const current = await f.binding();
  for (const key of ['binding_id', 'service_id', 'local_collection_id', 'first_photo_binding_id', 'flickr_photoset_id', 'desired_title', 'title_revision']) assert.equal(current[key], b[key], key);
  assert.equal(current.state, 'local_collection_removed_remote_preserved');
  const after = await retained(f.db);
  assert.equal(after.album_photo_obligations.length, before.album_photo_obligations.length);
  for (const original of before.album_photo_obligations) {
    const archived = after.album_photo_obligations.find(row => row.obligation_id === original.obligation_id);
    assert.equal(archived.local_relationship, 'archived'); assert.equal(archived.obligation_revision, original.obligation_revision + 1);
    for (const key of ['state', 'photo_id', 'photo_binding_id', 'album_binding_id', 'admission_binding_revision']) assert.equal(archived[key], original[key], key);
  }
  originalRowsRemain(before, after, ['album_binding_events', 'album_obligation_events', 'album_materialization_attempts', 'album_materialization_events']);
  await assert.rejects(associateAlbumPhoto(f.db, AUTH, f.bindingId, 'third-photo', { schemaVersion: 1, expectedBindingRevision: current.binding_revision, expectedVerificationRevision: 1 }), /album_closed/);
  assert.deepEqual(await retained(f.db), after);
  const replay = await api.putAlbumLocalRemoval(f.db, AUTH, f.bindingId, albumBody(b)); assert.equal(replay.created, false); assert.deepEqual(replay.receipt, first.receipt);
  const pairReplay = await api.putAlbumPhotoLocalRemoval(f.db, AUTH, f.bindingId, 'later-photo', { schemaVersion: 1, expectedBindingRevision: 1, expectedObligationRevision: 1 });
  assert.equal(pairReplay.created, false); assert.equal(pairReplay.receipt.archivedAt, first.receipt.archivedAt); assert.equal(pairReplay.receipt.acceptedBindingRevision, first.receipt.acceptedBindingRevision);
  assert.deepEqual(await retained(f.db), after);
});

test('archive receipts replay when Flickr grant is unavailable and never resurrect an accepted local relationship', async t => {
  const f = await removalFixture(t), body = albumBody(await f.binding()), accepted = await api.putAlbumLocalRemoval(f.db, AUTH, f.bindingId, body);
  await f.db.prepare("UPDATE flickr_links SET state='paused' WHERE user_id='user'").run();
  const before = await retained(f.db), replay = await api.putAlbumLocalRemoval(f.db, AUTH, f.bindingId, body);
  assert.equal(replay.created, false); assert.equal(replay.receipt.archivedAt, accepted.receipt.archivedAt);
  assert.equal(replay.receipt.acceptedBindingRevision, accepted.receipt.acceptedBindingRevision); assert.deepEqual(await retained(f.db), before);
});

test('archive cancels undispatched title work and retains a marked title only for reconciliation', async t => {
  for (const dispatched of [false, true]) {
    const f = await removalFixture(t); await rename(f); let claim = await title.claimAlbumTitle(f.db, f.bindingId); assert(claim);
    if (dispatched) { const read = await title.beginAlbumTitleRead(f.db, claim); assert(read); claim = await title.markAlbumTitleDispatch(f.db, read, { photosetId: 'removal-set', ownerNsid: 'owner', title: 'Synthetic album' }); assert(claim); }
    const revision = (await f.binding()).title_revision, before = await retained(f.db); await archive(f);
    const life = await title.readAlbumLifecycle(f.db, AUTH, f.bindingId); assert.equal(life.title.state, dispatched ? 'local_removed_reconciliation_pending' : 'local_removed');
    assert.equal((await f.binding()).title_revision, revision);
    const attempts = await rows(f.db, 'album_title_attempts'); assert.equal(attempts.length, before.album_title_attempts.length);
    assert.equal(attempts[0].dispatch_count, dispatched ? 1 : 0);
    if (dispatched) { assert.equal(attempts[0].attempt_id, claim.attemptId); assert.equal(attempts[0].completed_at_us, null); }
    else { assert.equal(await title.claimAlbumTitle(f.db, f.bindingId), null); assert(attempts[0].completed_at_us !== null); }
  }
});

test('unknown original create requires exact acknowledgement and archive retains its complete ambiguous evidence', async t => {
  const f = await removalFixture(t, { materialized: false }), claimed = await materialization.claimAlbumMaterialization(f.db, f.bindingId);
  assert(claimed); const marked = await materialization.markAlbumCreateDispatch(f.db, claimed, ['before-set']); assert(marked);
  assert(await materialization.unknownAlbumMaterialization(f.db, marked));
  const before = await retained(f.db); await assert.rejects(archive(f), /acknowledgement/); assert.deepEqual(await retained(f.db), before);
  const accepted = await archive(f, marked.attemptId); assert.equal(accepted.receipt.repairHandoff.destination, 'administrative_album_create_repair');
  assert.equal(accepted.receipt.repairHandoff.createAttemptId, marked.attemptId); assert(accepted.receipt.repairHandoff.acknowledgedAt);
  const after = await retained(f.db); originalRowsRemain(before, after, ['album_materialization_attempts', 'album_materialization_events']);
  assert.equal((await f.binding()).flickr_photoset_id, null); assert.equal(await materialization.claimAlbumMaterialization(f.db, f.bindingId), null);
  await assert.rejects(archive(f), /removal_acknowledgement_conflict/);
});

test('each archive transaction statement failure rolls back receipt, revisions and audit as one unit', async t => {
  for (const photo of [false, true]) {
    const operation = async f => photo ? api.putAlbumPhotoLocalRemoval(f.db, AUTH, f.bindingId, 'later-photo', photoBody(await f.binding(), await f.obligation())) : archive(f);
    const baseline = await removalFixture(t), batch = baseline.db.batch.bind(baseline.db); let count = 0;
    baseline.db.batch = statements => { count = Math.max(count, statements.length); return batch(statements); }; await operation(baseline); assert(count > 0);
    for (let fault = 0; fault < count; fault++) { const f = await removalFixture(t), before = await retained(f.db); f.db.fault = fault; await assert.rejects(operation(f)); f.db.fault = -1; assert.deepEqual(await retained(f.db), before, 'statement ' + fault); }
  }
});

test('actual local D1 populated migration and archive failures preserve all prior evidence atomically', async t => {
  const db = await nativeDatabase(t, '0026_'), f = await removalFixture(t, { db }), before = await retained(db);
  const migration = splitMigrations().find(item => item.name.startsWith('0026_')); assert(migration);
  await assert.rejects(db.batch([...migration.sql, "SELECT json_extract('synthetic-invalid-json','$')"].map(sql => db.prepare(sql))));
  assert.deepEqual(await retained(db), before);
  await db.batch(migration.sql.map(sql => db.prepare(sql))); const migrated = await retained(db);
  originalRowsRemain(before, migrated, Object.keys(before)); assert.deepEqual((await db.prepare('PRAGMA foreign_key_check').all()).results, []);
  const batch = db.batch.bind(db); let failing = true;
  f.db = { prepare: sql => db.prepare(sql), batch: statements => batch(failing ? [...statements, db.prepare("SELECT json_extract('synthetic-invalid-json','$')")] : statements) };
  const snapshot = await retained(db); await assert.rejects(archive(f)); assert.deepEqual(await retained(db), snapshot);
  failing = false; const accepted = await archive(f); assert.equal(accepted.created, true); assert.equal((await f.binding()).state, 'local_collection_removed_remote_preserved');
  const after = await retained(db), replay = await archive(f); assert.equal(replay.created, false); assert.equal(replay.receipt.archivedAt, accepted.receipt.archivedAt); assert.deepEqual(await retained(db), after);
});

test('ordinary SQL cannot erase immutable archive receipts or reopen archived relationships', async t => {
  const f = await removalFixture(t); await archive(f);
  for (const sql of [
    'DELETE FROM album_local_removal_receipts',
    'DELETE FROM album_photo_local_removal_receipts',
    'UPDATE album_local_removal_receipts SET archived_at_us=archived_at_us+1000',
    'UPDATE album_photo_local_removal_receipts SET archived_obligation_revision=archived_obligation_revision+1',
    "UPDATE album_bindings SET state='materialization_pending',binding_revision=binding_revision+1",
    "UPDATE album_photo_obligations SET local_relationship='active',obligation_revision=obligation_revision+1",
  ]) { const before = await retained(f.db); assert.throws(() => f.db.raw.exec(sql), undefined, sql); assert.deepEqual(await retained(f.db), before); }
});
