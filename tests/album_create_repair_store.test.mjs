import test from 'node:test';
import assert from 'node:assert/strict';
import * as api from '../src/album_create_repair_store.ts';
import * as materialization from '../src/album_materialization_store.ts';
import * as attachment from '../src/album_attachment_store.ts';
import * as title from '../src/album_title_store.ts';
import { putAlbumLocalRemoval } from '../src/album_local_removal_store.ts';
import { NOW_US_SQL } from '../src/installations.ts';
import { INSTALL, ADMIN, sqliteDatabase, nativeDatabase, applyRemaining, splitMigrations, unknownFixture,
  rows, retained, firstBinding, delayFirstBatch } from './album_create_repair_fixture.mjs';

const proof = (extra = {}) => ({ photosetId: 'selected-set', url: 'https://www.flickr.com/photos/owner/albums/selected-set',
  ownerNsid: 'owner', firstPhotoId: 'primary-remote', contextIds: ['before-set', 'selected-set'], observedAt: null, ...extra });
async function prepared(f, auth = INSTALL, extra = {}) {
  const value = { schemaVersion: 1, expectedBindingRevision: (await firstBinding(f)).binding_revision,
    createAttemptId: f.claim.attemptId, selectedPhotosetId: 'selected-set', ...extra };
  const result = await api.prepareAlbumResolution(f.db, auth, f.bindingId, value);
  return { value, ...result };
}
const commit = async (f, p, auth = INSTALL, evidence = proof()) => {
  // Use one database clock in storage tests; wall-clock rounding belongs to
  // the separate orchestration tests and must not make race fixtures flaky.
  if (evidence.observedAt === null) {
    const { now } = await f.db.prepare('SELECT ' + NOW_US_SQL + ' now').first();
    evidence = { ...evidence, observedAt: new Date(now / 1000).toISOString().replace(/(\.\d{3})Z$/, '$1000Z') };
  }
  return api.commitAlbumResolution(f.db, auth, p.context, p.value, evidence);
};
const obligation = async (f, photo = 'primary-photo') => f.db.prepare('SELECT * FROM album_photo_obligations WHERE album_binding_id=? AND photo_binding_id=?')
  .bind(f.bindingId, photo).first();
const rejected = (operation, code) => assert.rejects(operation, error => error instanceof Error && error.message.includes(code));
const revokeInstallation = db => db.batch([
  db.prepare("UPDATE installation_credential_versions SET state='revoked' WHERE version_id='version'"),
  db.prepare("UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='install'"),
]);

test('status and retained repair discovery are read-only snapshots with exact partitioned obligations', async t => {
  const f = await unknownFixture(t), before = await retained(f.db);
  const status = await api.readAlbumStatus(f.db, INSTALL, f.bindingId);
  assert.equal(status.materialization.state, 'create_outcome_unknown');
  assert.equal(status.materialization.createAttemptId, f.claim.attemptId);
  assert.equal(status.binding.flickrPhotosetId, null);
  assert.equal(status.materialization.repairSurface, 'plugin_or_admin');
  assert.deepEqual(status.membershipCounts, { waitingForAlbum: 2, attachmentPending: 0, membershipVerified: 0, reconciliationPending: 0, needsAttention: 0 });
  const page = await api.readAlbumObligationPage(f.db, INSTALL, f.bindingId, 1, 100);
  assert.equal(page.bindingRevision, status.binding.bindingRevision); assert.equal(page.total, 2); assert.equal(page.obligations.length, 2);
  const list = await api.readAlbumRepairPage(f.db, ADMIN, 1, 100);
  assert.equal(list.repairs[0].fgaAlbumBindingId, f.bindingId);
  await api.readAlbumRepairContext(f.db, INSTALL, f.bindingId);
  assert.deepEqual(await retained(f.db), before);
});

test('one resolution atomically retains original ambiguity and verifies only the first obligation', async t => {
  const f = await unknownFixture(t, { received: true }), p = await prepared(f);
  assert.equal(p.replay, false);
  const beforeBinding = await firstBinding(f), first = await obligation(f), later = await obligation(f, 'later-photo');
  const beforeAttempt = (await rows(f.db, 'album_materialization_attempts'))[0];
  const status = await commit(f, p);
  assert.equal(status.binding.flickrPhotosetId, 'selected-set');
  assert.equal(status.binding.bindingRevision, beforeBinding.binding_revision + 1);
  assert.equal(status.binding.titleRevision, beforeBinding.title_revision);
  assert.equal(status.materialization.state, 'materialized');
  assert.equal(status.materialization.resolvedPhotosetId, 'selected-set');
  assert.equal(status.materialization.resolutionProvenance, 'owner_reconciled_ambiguous_album_create');
  assert.equal((await obligation(f)).state, 'membership_verified');
  assert.equal((await obligation(f)).obligation_revision, first.obligation_revision + 1);
  assert.deepEqual(await obligation(f, 'later-photo'), later);
  assert.deepEqual((await rows(f.db, 'album_materialization_attempts'))[0], beforeAttempt,
    'original unknown marker, count, pre-context, returned identity and timestamps stay retained');
  assert.equal(beforeAttempt.dispatch_count, 1); assert.equal(beforeAttempt.state, 'create_outcome_unknown');
  assert.equal(beforeAttempt.received_photoset_id, 'uncertain-returned-set');
  assert.equal(await materialization.claimAlbumMaterialization(f.db, f.bindingId), null);
  assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
});

test('exact same selected ID and original attempt replay ignores stale expected revision without writes', async t => {
  const f = await unknownFixture(t), p = await prepared(f); await commit(f, p);
  const before = await retained(f.db), replay = await api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, p.value);
  assert.equal(replay.replay, true); assert.equal(replay.status.binding.flickrPhotosetId, 'selected-set');
  assert.deepEqual(await retained(f.db), before);
  for (const value of [{ ...p.value, selectedPhotosetId: 'different-set' }, { ...p.value, createAttemptId: crypto.randomUUID() }])
    await rejected(api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, value), 'resolution_conflict');
  assert.deepEqual(await retained(f.db), before);
});

test('normal worker identity cannot become an owner-selection receipt', async t => {
  const db = sqliteDatabase(); t.after(() => db.raw.close());
  const { materializationFixture } = await import('./album_materialization_sqlite.mjs');
  const f = await materializationFixture({ after() {} }, db);
  const c = await materialization.claimAlbumMaterialization(db, f.bindingId), marked = await materialization.markAlbumCreateDispatch(db, c, []);
  const result = { photosetId: 'worker-set', url: 'https://www.flickr.com/photos/owner/albums/worker-set', ownerNsid: 'owner', primaryPhotoId: 'primary-remote', contextIds: ['worker-set'] };
  assert.equal(await materialization.recordAlbumCreateResult(db, marked, result), true);
  assert.equal(await materialization.finishAlbumMaterialization(db, marked, result), true);
  const before = await retained(db);
  await rejected(api.prepareAlbumResolution(db, INSTALL, f.bindingId, { schemaVersion: 1,
    expectedBindingRevision: (await firstBinding(f)).binding_revision, createAttemptId: c.attemptId, selectedPhotosetId: 'worker-set' }), 'resolution_conflict');
  assert.deepEqual(await retained(db), before);
});

test('foreign and absent bindings share refusal, and current authentication still governs receipt replay', async t => {
  const f = await unknownFixture(t), p = await prepared(f); await commit(f, p);
  const before = await retained(f.db);
  await f.db.batch([
    f.db.prepare("INSERT INTO fga_users VALUES('foreign-user')"),
    f.db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('foreign-install','foreign-user','lrc_plugin','active',1,'foreign-version')"),
    f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('foreign-version','foreign-install',?,'current',1)").bind('e'.repeat(64)),
  ]);
  const foreign = { kind: 'installation', installationId: 'foreign-install', credentialDigest: 'e'.repeat(64) };
  await rejected(api.readAlbumStatus(f.db, INSTALL, crypto.randomUUID()), 'resource_not_found');
  await rejected(api.readAlbumStatus(f.db, foreign, f.bindingId), 'resource_not_found');
  for (const auth of [{ ...INSTALL, credentialDigest: 'd'.repeat(64) }, { ...ADMIN, tokenDigest: 'd'.repeat(64) }])
    await assert.rejects(api.prepareAlbumResolution(f.db, auth, f.bindingId, p.value));
  await revokeInstallation(f.db);
  await rejected(api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, p.value), 'invalid_token');
  assert.deepEqual(await retained(f.db), before);
});

const fences = [
  ["UPDATE installations SET revision=revision+1 WHERE installation_id='install'", 'installation revision'],
  ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'", 'link revision'],
  ["UPDATE flickr_links SET state='paused' WHERE user_id='user'", 'link pause'],
  ["UPDATE flickr_native_credentials SET verified_owner_nsid='other-owner' WHERE user_id='user'", 'owner identity'],
  ["UPDATE flickr_native_credentials SET active_generation='new-gen' WHERE user_id='user'", 'grant generation'],
  ["UPDATE flickr_connection_state SET verified_permission=NULL,verified_at_us=NULL WHERE user_id='user'", 'grant permission'],
  ["UPDATE flickr_connection_state SET local_state='unknown' WHERE user_id='user'", 'link availability'],
  ["UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'", 'deployment pause'],
  ["UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='user'", 'pause generation'],
  ["UPDATE photo_bindings SET link_revision=2 WHERE binding_id='primary-photo'", 'first photo link'],
];
test('commit fences exact current authentication, owner/link/grant, pause and first-photo authority after proof', async t => {
  for (const [sql, label] of fences) {
    const f = await unknownFixture(t), p = await prepared(f); await f.db.prepare(sql).run();
    const before = await retained(f.db); await assert.rejects(commit(f, p), undefined, label);
    assert.deepEqual(await retained(f.db), before, label); assert.equal((await firstBinding(f)).flickr_photoset_id, null);
  }
  {
    const f = await unknownFixture(t), p = await prepared(f); await revokeInstallation(f.db);
    const before = await retained(f.db); await rejected(commit(f, p), 'invalid_token'); assert.deepEqual(await retained(f.db), before);
  }
  for (const sql of ["UPDATE admin_sessions SET revoked_at_us=" + NOW_US_SQL + ",revocation_reason='logout',revision=revision+1 WHERE session_id='repair-session'",
    "UPDATE admin_sessions SET revision=revision+1 WHERE session_id='repair-session'",
    "UPDATE admin_principals SET session_set_revision=session_set_revision+1 WHERE user_id='user'"]) {
    const f = await unknownFixture(t), p = await prepared(f, ADMIN); await f.db.prepare(sql).run();
    const before = await retained(f.db); await assert.rejects(commit(f, p, ADMIN)); assert.deepEqual(await retained(f.db), before);
  }
});

test('stale binding revision and malformed or mismatched fresh proof commit nothing', async t => {
  const f = await unknownFixture(t), p = await prepared(f);
  await rejected(api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, { ...p.value, expectedBindingRevision: 1 }), 'stale_binding_revision');
  for (const evidence of [proof({ ownerNsid: 'other-owner' }), proof({ firstPhotoId: 'later-remote' }), proof({ contextIds: [] }),
    proof({ photosetId: 'different-set' }), proof({ contextIds: ['selected-set', 'selected-set'] }), proof({ contextIds: ['0'] }),
    proof({ url: 'https://example.invalid/selected-set' }), proof({ observedAt: 'not-a-timestamp' })]) {
    const before = await retained(f.db); await assert.rejects(commit(f, p, INSTALL, evidence)); assert.deepEqual(await retained(f.db), before);
  }
});

test('removed collection requires administrative repair and retains its archived obligations after selection and replay', async t => {
  const f = await unknownFixture(t);
  const removal = await putAlbumLocalRemoval(f.db, INSTALL, f.bindingId, { schemaVersion: 1,
    expectedBindingRevision: (await firstBinding(f)).binding_revision, acknowledgedCreateAttemptId: f.claim.attemptId });
  assert.equal(removal.created, true);
  assert.equal(removal.receipt.repairHandoff.createAttemptId, f.claim.attemptId);
  assert.equal((await api.readAlbumStatus(f.db, INSTALL, f.bindingId)).materialization.repairSurface, 'admin_only');
  await rejected(api.readAlbumRepairContext(f.db, INSTALL, f.bindingId), 'administrative_repair_required');
  const p = await prepared(f, ADMIN), status = await commit(f, p, ADMIN);
  assert.equal(status.localLifecycle, 'local_collection_removed_remote_preserved');
  for (const row of await rows(f.db, 'album_photo_obligations')) assert.equal(row.local_relationship, 'archived');
  const before = await retained(f.db);
  await rejected(api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, p.value), 'administrative_repair_required');
  assert.equal((await api.prepareAlbumResolution(f.db, ADMIN, f.bindingId, p.value)).replay, true);
  assert.deepEqual(await retained(f.db), before);
  assert.equal((await api.readAlbumRepairPage(f.db, ADMIN, 1, 100)).total, 0);
});

test('competing equal selections replay and different selections have only one atomic winner', async t => {
  for (const same of [true, false]) {
    const f = await unknownFixture(t), a = await prepared(f), b = await prepared(f, INSTALL, same ? {} : { selectedPhotosetId: 'loser-set' });
    const gate = delayFirstBatch(f.db), pending = commit(f, b, INSTALL, same ? proof() : proof({ photosetId: 'loser-set', contextIds: ['loser-set'], url: 'https://www.flickr.com/photos/owner/albums/loser-set' }));
    await gate.pending; await commit(f, a); const before = await retained(f.db); gate.release();
    if (same) assert.equal((await pending).binding.flickrPhotosetId, 'selected-set');
    else await rejected(pending, 'resolution_conflict');
    assert.deepEqual(await retained(f.db), before);
    assert.equal((await rows(f.db, 'album_create_repair_receipts')).length, 1);
  }
});

test('owner-scoped photoset uniqueness includes archived bindings and cannot orphan the losing first obligation', async t => {
  const f = await unknownFixture(t), p = await prepared(f); await commit(f, p);
  const removal = await putAlbumLocalRemoval(f.db, INSTALL, f.bindingId, { schemaVersion: 1,
    expectedBindingRevision: (await firstBinding(f)).binding_revision, acknowledgedCreateAttemptId: null });
  assert.equal(removal.created, true);
  assert.equal(removal.receipt.repairHandoff.destination, 'none');
  const other = await f.ensure('third-photo', 'Different:Repair'), id = other.binding.fgaAlbumBindingId;
  const c = await materialization.claimAlbumMaterialization(f.db, id), marker = await materialization.markAlbumCreateDispatch(f.db, c, []);
  assert.equal(await materialization.unknownAlbumMaterialization(f.db, marker), true);
  const losing = { ...f, bindingId: id, claim: marker }, before = await retained(f.db);
  try {
    const next = await prepared(losing);
    await rejected(commit(losing, next, INSTALL, proof({ firstPhotoId: 'third-remote' })), 'resolution_conflict');
  } catch (error) { assert.match(error.message, /resolution_conflict/); }
  assert.deepEqual(await retained(f.db), before);
  assert.equal((await obligation(losing, 'third-photo')).state, 'waiting_for_album');
});

test('each atomic batch statement failure and each semantic/event trigger failure restores all retained facts', async t => {
  const baseline = await unknownFixture(t), p = await prepared(baseline), batch = baseline.db.batch.bind(baseline.db); let length = 0;
  baseline.db.batch = statements => { length = Math.max(length, statements.length); return batch(statements); };
  await commit(baseline, p); assert(length > 0);
  for (let fault = 0; fault < length; fault++) {
    const f = await unknownFixture(t), value = await prepared(f), before = await retained(f.db); f.db.fault = fault;
    await assert.rejects(commit(f, value)); f.db.fault = -1; assert.deepEqual(await retained(f.db), before, 'statement ' + fault);
  }
  for (const [table, timing, condition] of [['album_create_repair_receipts', 'INSERT', '1'],
    ['album_bindings', 'UPDATE', 'NEW.flickr_photoset_id IS NOT NULL'],
    ['album_photo_obligations', 'UPDATE', "NEW.state='membership_verified'"],
    ['album_binding_events', 'INSERT', 'NEW.flickr_photoset_id IS NOT NULL'],
    ['album_obligation_events', 'INSERT', "NEW.state='membership_verified'"]]) {
    const f = await unknownFixture(t), value = await prepared(f), before = await retained(f.db);
    f.db.raw.exec(`CREATE TRIGGER test_resolution_fault BEFORE ${timing} ON ${table} WHEN ${condition} BEGIN SELECT RAISE(ABORT,'injected_semantic_failure'); END`);
    await assert.rejects(commit(f, value)); assert.deepEqual(await retained(f.db), before, table);
  }
});

test('actual local D1 applies every current migration over populated0022 unknown/archive history and resolves via RETURNING', async t => {
  const db = await nativeDatabase(t, '0023_'), f = await unknownFixture(t, { db, received: true });
  const archived = await f.ensure('third-photo', 'Archived:Repair');
  // Deliberate historical0022 fixture:0026 receipts and guards do not exist yet.
  // Current-schema removals above use the guarded operation instead.
  await db.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?")
    .bind(archived.binding.fgaAlbumBindingId).run();
  const before = await retained(db); await applyRemaining(db);
  const after = await retained(db);
  for (const [table, previous] of Object.entries(before)) for (let i = 0; i < previous.length; i++)
    for (const [key, value] of Object.entries(previous[i])) assert.deepEqual(after[table][i][key], value, table + ':' + key);
  const original = db.batch.bind(db); let returned = false, inflated = false;
  f.db = { prepare: db.prepare.bind(db), batch: async statements => { const result = await original(statements); for (const value of result) {
    if (value.results?.length === 1 && Object.keys(value.results[0]).length === 1 && value.results[0].binding_id === f.bindingId) returned = true;
    if (value.meta?.changes > 1) inflated = true;
  } return result; } };
  const p = await prepared(f), status = await commit(f, p);
  assert.equal(status.binding.flickrPhotosetId, 'selected-set');
  assert(returned, 'conditional write returns its exact authority row');
  assert(inflated, 'actual D1 metadata includes trigger changes and cannot own success');
  const resolved = await retained(db); assert.equal((await api.prepareAlbumResolution(db, INSTALL, f.bindingId, p.value)).replay, true);
  assert.deepEqual(await retained(db), resolved);
  await assert.rejects(db.prepare('DELETE FROM album_create_repair_receipts').run());
  assert.deepEqual((await db.prepare('PRAGMA foreign_key_check').all()).results, []);
});

test('actual local D1 resolution event failure rolls back receipt, immutable ID and primary membership', async t => {
  const f = await unknownFixture(t, { db: await nativeDatabase(t) }), before = await retained(f.db);
  for (const [table, operation, condition] of [['album_create_repair_receipts', 'INSERT', '1'],
    ['album_bindings', 'UPDATE', 'NEW.flickr_photoset_id IS NOT NULL'],
    ['album_photo_obligations', 'UPDATE', "NEW.state='membership_verified'"],
    ['album_binding_events', 'INSERT', 'NEW.flickr_photoset_id IS NOT NULL'],
    ['album_obligation_events', 'INSERT', "NEW.state='membership_verified'"]]) {
    const p = await prepared(f);
    await f.db.prepare(`CREATE TRIGGER test_native_repair_fault BEFORE ${operation} ON ${table} WHEN ${condition} BEGIN SELECT RAISE(ABORT,'native_semantic_failure'); END`).run();
    await assert.rejects(commit(f, p)); assert.deepEqual(await retained(f.db), before, table);
    await f.db.prepare('DROP TRIGGER test_native_repair_fault').run();
  }
});

test('actual local D1 competing proof snapshots commit one winner and fence a changed pause generation', async t => {
  const f = await unknownFixture(t, { db: await nativeDatabase(t) }), same = await prepared(f), different = await prepared(f, INSTALL, { selectedPhotosetId: 'loser-set' });
  await commit(f, same); const before = await retained(f.db);
  assert.equal((await commit(f, same)).binding.flickrPhotosetId, 'selected-set');
  await rejected(commit(f, different, INSTALL, proof({ photosetId: 'loser-set', contextIds: ['loser-set'], url: 'https://www.flickr.com/photos/owner/albums/loser-set' })), 'resolution_conflict');
  assert.deepEqual(await retained(f.db), before);
  await f.db.prepare("UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='user'").run();
  await rejected(api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, same.value), 'flickr_link_unavailable');
  assert.deepEqual(await retained(f.db), before);
});

test('actual local D1 migration0023 rolls back at each partial statement without weakening populated0022 guards', async t => {
  const db = await nativeDatabase(t, '0023_'), f = await unknownFixture(t, { db }), before = await retained(db);
  const schema = (await db.prepare("SELECT type,name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").all()).results;
  const migration = splitMigrations().find(item => item.name === '0023_album_create_repair.sql');
  assert(migration, 'production0023 must exist');
  for (let i = 0; i <= migration.sql.length; i++) {
    const failing = [...migration.sql.slice(0, i), 'INSERT INTO nonexistent_repair_fault_table VALUES(1)', ...migration.sql.slice(i)];
    await assert.rejects(db.batch(failing.map(sql => db.prepare(sql))));
    assert.deepEqual(await retained(db), before, 'migration statement ' + i);
    assert.deepEqual((await db.prepare("SELECT type,name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").all()).results, schema);
  }
  await assert.rejects(db.prepare('DELETE FROM album_photo_obligations').run());
  await assert.rejects(db.prepare('DELETE FROM album_materialization_attempts').run());
  assert.equal((await firstBinding(f)).materialization_state, 'create_outcome_unknown');
  await applyRemaining(db); assert.deepEqual((await db.prepare('PRAGMA foreign_key_check').all()).results, []);
});

test('admin resolution appends exactly one sanitized success audit and installation resolution appends none', async t => {
  for (const auth of [ADMIN, INSTALL]) {
    const f = await unknownFixture(t), p = await prepared(f, auth), before = await rows(f.db, 'audit_events');
    await commit(f, p, auth);
    const after = await rows(f.db, 'audit_events');
    assert.equal(after.length, before.length + (auth.kind === 'admin' ? 1 : 0));
    if (auth.kind === 'admin') {
      const audit = after.at(-1), receipt = (await rows(f.db, 'album_create_repair_receipts'))[0];
      assert.equal(audit.user_id, 'user'); assert.equal(audit.action, 'album_create_repair.resolved');
      assert.equal(audit.outcome, 'succeeded'); assert.equal(audit.reason, 'owner_reconciled_ambiguous_album_create');
      assert.equal(audit.target_id, f.bindingId); assert.equal(audit.session_correlation_id, 'repair-correlation');
      assert.equal(audit.request_correlation_id, receipt.request_correlation_id);
      assert.match(audit.request_correlation_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    }
    const retainedSuccess = await retained(f.db);
    assert.equal((await api.prepareAlbumResolution(f.db, auth, f.bindingId, p.value)).replay, true);
    assert.deepEqual(await retained(f.db), retainedSuccess);
  }
});

test('actual local D1 admin audit insert failure rolls back every receipt, event, binding and membership fact', async t => {
  const f = await unknownFixture(t, { db: await nativeDatabase(t) }), p = await prepared(f, ADMIN), before = await retained(f.db);
  await f.db.prepare("CREATE TRIGGER test_admin_audit_fault BEFORE INSERT ON audit_events WHEN NEW.action='album_create_repair.resolved' BEGIN SELECT RAISE(ABORT,'synthetic_audit_failure'); END").run();
  await rejected(commit(f, p, ADMIN), 'service_unavailable');
  assert.deepEqual(await retained(f.db), before);
  assert.equal((await firstBinding(f)).flickr_photoset_id, null); assert.equal((await obligation(f)).state, 'waiting_for_album');
  await f.db.prepare('DROP TRIGGER test_admin_audit_fault').run();
  const status = await commit(f, p, ADMIN); assert.equal(status.binding.flickrPhotosetId, 'selected-set');
  assert.equal((await rows(f.db, 'audit_events')).length, 1);
  const success = await retained(f.db);
  assert.equal((await api.prepareAlbumResolution(f.db, ADMIN, f.bindingId, p.value)).replay, true);
  assert.deepEqual(await retained(f.db), success);
});

async function assertRetainedAttention(f, p, state, previousRevision) {
  const before = await retained(f.db), status = await api.readAlbumStatus(f.db, INSTALL, f.bindingId);
  assert.equal(status.materialization.state, state);
  assert.equal(status.binding.flickrPhotosetId, 'selected-set');
  assert.equal(status.materialization.createAttemptId, p.value.createAttemptId);
  assert.equal(status.materialization.resolvedPhotosetId, 'selected-set');
  assert.equal(status.materialization.resolutionProvenance, 'owner_reconciled_ambiguous_album_create');
  assert.equal(status.catalogRepair.flickrPhotosetId, 'selected-set');
  assert.equal(status.catalogRepair.navigationUrl, null); assert.equal(status.catalogRepair.identityVerifiedAt, null);
  assert.equal(status.binding.bindingRevision, previousRevision + 1, 'semantic remote status transition advances its binding revision once');
  const replay = await api.prepareAlbumResolution(f.db, INSTALL, f.bindingId, p.value);
  assert.equal(replay.replay, true); assert.deepEqual(replay.status, status);
  assert.deepEqual(await retained(f.db), before, 'status and exact replay preserve attention evidence');
}

test('actual local D1 attachment missing/conflict observations retain resolution identity and suppress obsolete catalog proof', async t => {
  for (const [reason, state] of [['missing_album', 'remote_album_missing_needs_attention'], ['wrong_owner', 'album_identity_conflict'], ['binding_conflict', 'album_identity_conflict']]) {
    await t.test(reason, async subtest => {
      const f = await unknownFixture(subtest, { db: await nativeDatabase(subtest) }), p = await prepared(f); await commit(f, p);
      const later = await obligation(f, 'later-photo'), claim = await attachment.claimAlbumAttachment(f.db, later.obligation_id); assert(claim);
      const before = await api.readAlbumStatus(f.db, INSTALL, f.bindingId);
      assert.equal(await attachment.attentionAlbumAttachment(f.db, claim, reason), true);
      await assertRetainedAttention(f, p, state, before.binding.bindingRevision);
    });
  }
});

test('actual local D1 title missing observation retains resolution identity and suppresses obsolete catalog proof', async t => {
  const f = await unknownFixture(t, { db: await nativeDatabase(t) }), p = await prepared(f); await commit(f, p);
  const binding = await firstBinding(f);
  await title.putAlbumTitleIntent(f.db, INSTALL, f.bindingId, binding.title_revision + 1, { schemaVersion: 1,
    expectedBindingRevision: binding.binding_revision, expectedTitleRevision: binding.title_revision, desiredTitle: 'Synthetic new title' });
  const claim = await title.claimAlbumTitle(f.db, f.bindingId); assert(claim);
  const reading = await title.beginAlbumTitleRead(f.db, claim); assert(reading);
  const before = await api.readAlbumStatus(f.db, INSTALL, f.bindingId);
  assert.equal(await title.missingAlbumTitle(f.db, reading), true);
  await assertRetainedAttention(f, p, 'remote_album_missing_needs_attention', before.binding.bindingRevision);
});
