import test from 'node:test';
import assert from 'node:assert/strict';
import { attachmentFixture, nativeDatabase, retained, rows, databaseClock, SET } from './album_attachment_fixture.mjs';
import { splitMigrations } from './album_create_repair_fixture.mjs';
import { AUTH } from './album_materialization_sqlite.mjs';
import { NOW_US_SQL } from '../src/installations.ts';
import * as materialization from '../src/album_materialization_store.ts';
import * as repair from '../src/album_create_repair_store.ts';
import * as title from '../src/album_title_store.ts';

const api = () => import('../src/album_attachment_store.ts');
const migration = () => splitMigrations().find(item => item.name === '0025_album_attachment.sql').sql;
const schema = async db => (await db.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").all()).results;
const present = extra => ({ ownerNsid: 'owner', photoId: 'later-remote', contextIds: [SET], ...extra });
const absent = () => present({ contextIds: [] });
async function claimed(t, options) {
  const f = await attachmentFixture(t, options), storage = await api();
  const claim = await storage.claimAlbumAttachment(f.db, f.obligationId);
  assert(claim); return { ...f, storage, claim };
}
async function marked(t, options) {
  const f = await claimed(t, options);
  const claim = await f.storage.markAlbumAttachmentDispatch(f.db, f.claim, []);
  assert(claim); return { ...f, claim };
}
async function semanticSnapshot(f) {
  const binding = await f.db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
  const obligation = await f.obligation();
  const facts = (await f.db.prepare('SELECT * FROM album_attachment_semantic_events WHERE obligation_id=? ORDER BY obligation_revision_after').bind(f.obligationId).all()).results;
  const status = await f.db.prepare('SELECT state,membership_observed_at_us FROM album_obligation_status WHERE obligation_id=?').bind(f.obligationId).first();
  return { binding: binding.binding_revision, obligation: obligation.obligation_revision, facts, status };
}
function semanticStep(before, after, state, delta) {
  assert.equal(after.binding, before.binding + delta);
  assert.equal(after.obligation, before.obligation + delta);
  assert.equal(after.facts.length, before.facts.length + delta);
  assert.deepEqual(after.facts.slice(0, before.facts.length), before.facts);
  assert.equal(after.status.state, state);
  if (delta) {
    const fact = after.facts.at(-1);
    assert.equal(fact.binding_revision_before, before.binding); assert.equal(fact.binding_revision_after, after.binding);
    assert.equal(fact.obligation_revision_before, before.obligation); assert.equal(fact.obligation_revision_after, after.obligation);
  }
}
async function preceding(t) {
  const db = await nativeDatabase(t, '0023_');
  const f = await attachmentFixture(t, { db });
  const archived = await f.ensure('third-photo', 'Archived:prior');
  // This fixture intentionally remains on migration0022, where raw archival was permitted.
  await db.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?").bind(archived.binding.fgaAlbumBindingId).run();
  for (const item of splitMigrations().filter(item => item.name >= '0023_' && item.name < '0025_'))
    await db.batch(item.sql.map(sql => db.prepare(sql)));
  const repairAlbum = await f.ensure('third-photo', 'Repair:prior'), repairId = repairAlbum.binding.fgaAlbumBindingId;
  const repairClaim = await materialization.claimAlbumMaterialization(db, repairId); assert(repairClaim);
  const repairMarked = await materialization.markAlbumCreateDispatch(db, repairClaim, []); assert(repairMarked);
  assert(await materialization.unknownAlbumMaterialization(db, repairMarked));
  const binding = await db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(repairId).first();
  const request = { schemaVersion: 1, expectedBindingRevision: binding.binding_revision, createAttemptId: repairMarked.attemptId, selectedPhotosetId: 'prior-repaired-set' };
  const auth = { kind: 'installation', ...AUTH }, prepared = await repair.prepareAlbumResolution(db, auth, repairId, request);
  const { now } = await db.prepare('SELECT ' + NOW_US_SQL + ' now').first();
  await repair.commitAlbumResolution(db, auth, prepared.context, request,
    { photosetId: request.selectedPhotosetId, url: 'https://www.flickr.com/photos/owner/albums/' + request.selectedPhotosetId,
      ownerNsid: 'owner', firstPhotoId: 'third-remote', contextIds: [request.selectedPhotosetId],
      observedAt: new Date(now / 1000).toISOString().replace(/(\.\d{3})Z$/, '$1000Z') });
  const original = await db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
  // Seed the guarded0024 receipt directly: the current title response snapshot requires0026.
  // Applying0026 here would invalidate the0025 predecessor migration proof.
  await db.prepare(`INSERT INTO album_title_receipts(binding_id,title_revision,expected_binding_revision,
    expected_title_revision,desired_title,accepted_binding_revision,installation_id,credential_digest)
    VALUES(?,?,?,?,?,?,?,?)`).bind(f.bindingId, original.title_revision + 1, original.binding_revision,
      original.title_revision, 'Prior retained desired title', original.binding_revision + 1,
      AUTH.installationId, AUTH.credentialDigest).run();
  assert(await title.claimAlbumTitle(db, f.bindingId));
  return f;
}

test('actual local D1 migration0025 preserves populated 0022/0023/0024 bindings, fulfilled and pending obligations and append-only histories', async t => {
  const f = await preceding(t), before = await retained(f.db);
  assert(before.album_materialization_events.length > 0);
  assert(before.album_create_repair_receipts.length > 0);
  assert(before.album_title_receipts.length > 0);
  assert(before.album_title_attempts.length > 0);
  assert(before.album_obligation_events.some(row => row.kind === 'relationship_archived'));
  await f.db.batch(migration().map(sql => f.db.prepare(sql)));
  const after = await retained(f.db);
  for (const [table, expected] of Object.entries(before)) assert.deepEqual(after[table], expected, table);
  assert.deepEqual(after.album_attachment_attempts, []);
  assert.deepEqual(after.album_attachment_events, []);
  assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
  const storage = await api(), claim = await storage.claimAlbumAttachment(f.db, f.obligationId);
  assert(claim, 'actual D1 conditional claim must use returned rows despite trigger-inflated changes');
  assert.equal((await f.attempts()).length, 1);
});

test('actual local D1 failed migration0025 batch rolls back schema, histories and guards before a clean retry', async t => {
  const f = await preceding(t), before = await retained(f.db), beforeSchema = await schema(f.db);
  const statements = migration();
  const failed = [...statements.slice(0, Math.max(1, Math.floor(statements.length / 2))), 'INSERT INTO missing_attachment_migration_target VALUES(1)', ...statements.slice(Math.max(1, Math.floor(statements.length / 2)))];
  await assert.rejects(f.db.batch(failed.map(sql => f.db.prepare(sql))));
  assert.deepEqual(await retained(f.db), before);
  assert.deepEqual(await schema(f.db), beforeSchema);
  await assert.rejects(f.db.prepare('DELETE FROM album_obligation_events').run());
  await assert.rejects(f.db.prepare('DELETE FROM album_materialization_attempts').run());
  await f.db.batch(statements.map(sql => f.db.prepare(sql)));
  assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
});

test('one exact pair has one active lease and no attachment work exists before materialization', async t => {
  const f = await claimed(t, { native: true });
  assert.equal(await f.storage.claimAlbumAttachment(f.db, f.obligationId), null);
  assert.equal((await f.attempts()).length, 1);
  const pending = await attachmentFixture(t, { materialize: false });
  assert.equal(await f.storage.claimAlbumAttachment(pending.db, pending.obligationId), null);
  assert.deepEqual(await pending.attempts(), []);
});

test('competing actual local D1 claims return one durable attempt and never share HTTP authority', async t => {
  const f = await attachmentFixture(t, { native: true }), storage = await api();
  const outcomes = await Promise.all(Array.from({ length: 4 }, () => storage.claimAlbumAttachment(f.db, f.obligationId)));
  assert.equal(outcomes.filter(Boolean).length, 1);
  assert.equal((await f.attempts()).length, 1);
  assert.equal((await f.events()).length, 1);
});

test('invalid absence or membership proof cannot allocate a marker or finish the exact pair', async t => {
  const f = await claimed(t), before = await retained(f.db);
  for (const ids of [[SET], ['duplicate', 'duplicate'], ['bad id'], ['0'], [null], null, Array.from({ length: 1001 }, (_, i) => 'set-' + i)])
    assert.equal(await f.storage.markAlbumAttachmentDispatch(f.db, f.claim, ids), null);
  for (const proof of [absent(), present({ ownerNsid: 'foreign-owner' }), present({ photoId: 'primary-remote' }), present({ contextIds: [SET, SET] }), present({ contextIds: [SET, 'bad id'] })])
    assert.equal(await f.storage.finishAlbumAttachment(f.db, f.claim, proof), false);
  assert.deepEqual(await retained(f.db), before);
  assert.equal(await f.storage.finishAlbumAttachment(f.db, f.claim, present()), true);
  assert.equal((await f.obligation()).state, 'membership_verified');
});

test('stale owner, revision, lease and epoch claims have no marker, result or retry authority', async t => {
  const f = await claimed(t), before = await retained(f.db);
  for (const change of [{ leaseId: crypto.randomUUID() }, { epoch: f.claim.epoch + 1 }, { ownerNsid: 'foreign' }, { photoId: 'primary-remote' }, { photosetId: 'other-set' }, { bindingRevision: f.claim.bindingRevision + 1 }, { obligationRevision: f.claim.obligationRevision + 1 }, { verificationRevision: f.claim.verificationRevision + 1 }, { linkRevision: f.claim.linkRevision + 1 }, { grantGeneration: 'new-generation' }, { deploymentGateRevision: f.claim.deploymentGateRevision + 1 }]) {
    const stale = { ...f.claim, ...change };
    assert.equal(await f.storage.currentAlbumAttachment(f.db, stale), false);
    assert.equal(await f.storage.markAlbumAttachmentDispatch(f.db, stale, []), null);
    assert.equal(await f.storage.finishAlbumAttachment(f.db, stale, present()), false);
    assert.equal(await f.storage.deferAlbumAttachment(f.db, stale, absent()), false);
  }
  assert.deepEqual(await retained(f.db), before);
});

test('a gate or link revision change inside the committing batch defeats marker and result', async t => {
  const fences = ["UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'", "UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='user'", "UPDATE flickr_links SET link_revision=2 WHERE user_id='user'", "UPDATE flickr_native_credentials SET active_generation='changed-generation' WHERE user_id='user'"];
  for (const sql of fences) for (const phase of ['marker', 'result']) {
    const f = phase === 'marker' ? await claimed(t) : await marked(t);
    const original = f.db.batch.bind(f.db); let once = false;
    f.db.batch = async statements => { if (!once) { once = true; f.db.raw.exec(sql); } return original(statements); };
    const result = phase === 'marker' ? await f.storage.markAlbumAttachmentDispatch(f.db, f.claim, []) : await f.storage.finishAlbumAttachment(f.db, f.claim, present());
    assert.equal(result, phase === 'marker' ? null : false, sql + ' ' + phase);
    assert.notEqual((await f.obligation()).state, 'membership_verified');
    assert.equal((await f.attempts()).at(-1).dispatch_count, phase === 'marker' ? 0 : 1);
  }
});

test('unknown marked outcome recovers through a read-only successor then a separately scheduled bounded add claim', async t => {
  const f = await marked(t), clock = databaseClock(f.db);
  assert(await f.storage.unknownAlbumAttachment(f.db, f.claim));
  const unknown = (await f.attempts()).at(-1);
  assert.equal(await f.storage.claimAlbumAttachment(f.db, f.obligationId), null);
  clock.set(unknown.retry_after_us);
  const readOnly = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(readOnly);
  assert.equal(readOnly.reconciliationOnly, true);
  assert.equal(await f.storage.markAlbumAttachmentDispatch(f.db, readOnly, []), null);
  assert.equal(await f.storage.deferAlbumAttachment(f.db, readOnly, absent()), true);
  const deferred = (await f.attempts()).at(-1);
  assert.equal(deferred.retry_after_us - deferred.completed_at_us, 2_000_000);
  clock.set(deferred.retry_after_us);
  const retry = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(retry);
  assert.equal(retry.reconciliationOnly, false);
  assert.equal(retry.epoch, f.claim.epoch + 2);
  const retainedBefore = await retained(f.db);
  assert.equal(await f.storage.finishAlbumAttachment(f.db, f.claim, present()), false);
  assert.equal(await f.storage.unknownAlbumAttachment(f.db, readOnly), false);
  assert.deepEqual(await retained(f.db), retainedBefore);
});

test('database deadlines preserve 15 second dispatch and 5 second commit margins and marked expiry', async t => {
  for (const phase of ['marker', 'result']) {
    const f = phase === 'marker' ? await claimed(t) : await marked(t), clock = databaseClock(f.db);
    const attempt = (await f.attempts()).at(-1);
    clock.set(attempt.invocation_deadline_at_us - (phase === 'marker' ? 15_000_000 : 5_000_000));
    assert.equal(await f.storage.currentAlbumAttachment(f.db, f.claim, phase === 'marker' ? 15_000_000 : 5_000_000), false);
    assert.equal(phase === 'marker' ? await f.storage.markAlbumAttachmentDispatch(f.db, f.claim, []) : await f.storage.finishAlbumAttachment(f.db, f.claim, present()), phase === 'marker' ? null : false);
    clock.set(attempt.lease_expires_at_us);
    assert.equal(await f.storage.claimAlbumAttachment(f.db, f.obligationId), null, 'recovery first respects durable backoff');
    const expired = (await f.attempts()).at(-1);
    assert.equal(expired.state, phase === 'marker' ? 'abandoned_before_dispatch' : 'membership_reconciliation_pending');
    clock.set(expired.retry_after_us);
    const next = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(next);
    assert.equal(next.reconciliationOnly, phase === 'result');
  }
});

test('raw SQL cannot erase/replay marker, forge malformed proof, alter leases or replace append-only events', async t => {
  const f = await marked(t, { native: true });
  for (const sql of [
    'DELETE FROM album_attachment_attempts', 'DELETE FROM album_attachment_events',
    'UPDATE album_attachment_attempts SET dispatch_count=0',
    'UPDATE album_attachment_attempts SET epoch=epoch+1',
    'UPDATE album_attachment_attempts SET lease_expires_at_us=lease_expires_at_us+1',
    "UPDATE album_attachment_attempts SET pre_context_ids='[\"duplicate\",\"duplicate\"]'",
    'INSERT OR REPLACE INTO album_attachment_events SELECT * FROM album_attachment_events',
    "UPDATE album_photo_obligations SET state='membership_verified',obligation_revision=obligation_revision+1 WHERE photo_binding_id='later-photo'",
    `UPDATE album_attachment_attempts SET state='membership_verified',completed_at_us=${NOW_US_SQL},proof_context_ids='["${SET}","${SET}"]',proof_owner_nsid='owner',proof_photo_id='later-remote',proof_observed_at_us=${NOW_US_SQL}`,
    `UPDATE album_attachment_attempts SET state='membership_verified',completed_at_us=${NOW_US_SQL},proof_context_ids='["${SET}"]',proof_owner_nsid='foreign-owner',proof_photo_id='later-remote',proof_observed_at_us=${NOW_US_SQL}`,
  ]) {
    const before = await retained(f.db);
    await assert.rejects(f.db.prepare(sql).run(), undefined, sql);
    assert.deepEqual(await retained(f.db), before, sql);
  }
  assert(await f.storage.finishAlbumAttachment(f.db, f.claim, present()));
  const before = await retained(f.db);
  assert.equal(await f.storage.markAlbumAttachmentDispatch(f.db, f.claim, []), null);
  assert.equal(await f.storage.finishAlbumAttachment(f.db, f.claim, present()), false);
  assert.deepEqual(await retained(f.db), before);
});

test('actual local D1 event failure rolls back successful proof, obligation revision and all evidence', async t => {
  const f = await marked(t, { native: true }), before = await retained(f.db);
  await f.db.prepare("CREATE TRIGGER attachment_test_event_failure BEFORE INSERT ON album_attachment_events BEGIN SELECT RAISE(ABORT,'synthetic_event_failure'); END").run();
  await assert.rejects(f.storage.finishAlbumAttachment(f.db, f.claim, present()));
  assert.deepEqual(await retained(f.db), before);
  assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
});

test('statement failures leave claim, marker, proof and append-only obligation evidence atomic', async t => {
  for (const phase of ['claim', 'marker', 'receipt', 'result']) {
    const create = () => phase === 'claim' ? attachmentFixture(t) : phase === 'marker' ? claimed(t) : marked(t);
    const storage = await api(), operation = f => phase === 'claim' ? storage.claimAlbumAttachment(f.db, f.obligationId) : phase === 'marker' ? storage.markAlbumAttachmentDispatch(f.db, f.claim, []) : phase === 'receipt' ? storage.recordAlbumAttachmentResult(f.db, f.claim, 'added') : storage.finishAlbumAttachment(f.db, f.claim, present());
    const baseline = await create(); let count = 0; const original = baseline.db.batch.bind(baseline.db);
    baseline.db.batch = statements => { count = statements.length; return original(statements); };
    await operation(baseline); assert(count > 0);
    for (let index = 0; index < count; index++) {
      const f = await create(), before = await retained(f.db); f.db.fault = index;
      await assert.rejects(operation(f)); f.db.fault = -1;
      assert.deepEqual(await retained(f.db), before, phase + ' statement ' + index);
    }
  }
});

test('retained dispatch history bounds add retries at eight with exponential backoff capped at sixty seconds', async t => {
  const f = await attachmentFixture(t), storage = await api(), clock = databaseClock(f.db);
  for (let count = 0; count < 8; count++) {
    const claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
    assert.equal(claim.dispatchAttempts, count);
    const marker = await storage.markAlbumAttachmentDispatch(f.db, claim, []); assert(marker);
    assert.equal(await storage.markAlbumAttachmentDispatch(f.db, marker, []), null);
    assert.equal(count === 7 ? await storage.unknownAlbumAttachment(f.db, marker) : await storage.deferAlbumAttachment(f.db, marker, absent()), true);
    const row = (await f.attempts()).at(-1);
    assert.equal(row.retry_after_us - row.completed_at_us, Math.min(60_000_000, 1_000_000 * 2 ** count));
    assert.equal(await storage.claimAlbumAttachment(f.db, f.obligationId), null);
    clock.set(row.retry_after_us);
  }
  const exhausted = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(exhausted);
  assert.equal(exhausted.dispatchAttempts, 8);
  const before = await retained(f.db);
  assert.equal(await storage.markAlbumAttachmentDispatch(f.db, exhausted, []), null);
  assert.deepEqual(await retained(f.db), before);
  assert.equal((await f.attempts()).filter(row => row.dispatch_count === 1).length, 8);
  assert.equal(await storage.finishAlbumAttachment(f.db, exhausted, present()), true, 'retry exhaustion still permits read-only successful reconciliation');
});

test('actual local D1 durably retains documented add responses without satisfying membership and refuses receipt replay or erasure', async t => {
  for (const result of ['added', 'already_present']) {
    const f = await marked(t, { native: true });
    assert.equal(await f.storage.recordAlbumAttachmentResult(f.db, f.claim, 'unknown'), false);
    assert.equal(await f.storage.recordAlbumAttachmentResult(f.db, f.claim, result), true);
    const receipt = (await f.attempts()).at(-1);
    assert.equal(receipt.state, 'result_received'); assert.equal(receipt.received_result, result);
    assert(receipt.received_at_us > 0); assert.notEqual((await f.obligation()).state, 'membership_verified');
    assert.equal(await f.storage.recordAlbumAttachmentResult(f.db, f.claim, result), false);
    for (const sql of ["UPDATE album_attachment_attempts SET received_result=NULL,received_at_us=NULL", "UPDATE album_attachment_attempts SET received_result='added',received_at_us=received_at_us+1"])
      await assert.rejects(f.db.prepare(sql).run());
    assert.equal(await f.storage.unknownAlbumAttachment(f.db, f.claim), true);
    const unknown = (await f.attempts()).at(-1);
    assert.equal(unknown.received_result, receipt.received_result);
    assert.equal(unknown.received_at_us, receipt.received_at_us);
    assert.equal(unknown.dispatch_count, 1);
  }
});

test('actual local D1 album-wide remote conflicts project through status and prevent another pair bypassing the fence', async t => {
  for (const reason of ['wrong_owner', 'binding_conflict', 'missing_album', 'missing_photo']) {
    const f = await attachmentFixture(t, { native: true }), storage = await api();
    const binding = await f.db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
    const other = await f.associate('third-photo', binding.binding_revision);
    const claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
    assert(await storage.attentionAlbumAttachment(f.db, claim, reason));
    const status = await repair.readAlbumStatus(f.db, { kind: 'installation', ...AUTH }, f.bindingId);
    assert.equal(status.materialization.state, reason === 'missing_album' ? 'remote_album_missing_needs_attention' : reason === 'missing_photo' ? 'materialized' : 'album_identity_conflict');
    const next = await storage.claimAlbumAttachment(f.db, other.obligation.fgaAlbumObligationId);
    assert.equal(Boolean(next), reason === 'missing_photo', reason + ' cross-pair authority');
    assert.equal(status.membershipCounts.needsAttention, 1);
  }
});

test('semantic state and every fresh proof advance both physical revisions exactly once; claims, receipts and housekeeping do not', async t => {
  const f = await attachmentFixture(t), storage = await api(), clock = databaseClock(f.db);
  let before = await semanticSnapshot(f);
  let claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
  semanticStep(before, await semanticSnapshot(f), 'attachment_pending', 0);
  let marker = await storage.markAlbumAttachmentDispatch(f.db, claim, []); assert(marker);
  semanticStep(before, await semanticSnapshot(f), 'attachment_pending', 0);
  assert(await storage.recordAlbumAttachmentResult(f.db, marker, 'added'));
  semanticStep(before, await semanticSnapshot(f), 'attachment_pending', 0);
  assert(await storage.unknownAlbumAttachment(f.db, marker));
  let after = await semanticSnapshot(f); semanticStep(before, after, 'membership_reconciliation_pending', 1); before = after;
  assert.equal(await storage.claimAlbumAttachment(f.db, f.obligationId), null);
  semanticStep(before, await semanticSnapshot(f), 'membership_reconciliation_pending', 0);
  clock.set((await f.attempts()).at(-1).retry_after_us);
  claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim?.reconciliationOnly);
  assert(await storage.unknownAlbumAttachment(f.db, claim));
  semanticStep(before, await semanticSnapshot(f), 'membership_reconciliation_pending', 0);
  clock.set((await f.attempts()).at(-1).retry_after_us);
  claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim?.reconciliationOnly);
  assert(await storage.deferAlbumAttachment(f.db, claim, absent()));
  after = await semanticSnapshot(f); semanticStep(before, after, 'attachment_pending', 1); before = after;
  clock.set((await f.attempts()).at(-1).retry_after_us);
  claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
  assert(await storage.deferAlbumAttachment(f.db, claim, absent()));
  after = await semanticSnapshot(f); semanticStep(before, after, 'attachment_pending', 1); before = after;
  clock.set((await f.attempts()).at(-1).retry_after_us);
  claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
  assert(await storage.finishAlbumAttachment(f.db, claim, present()));
  after = await semanticSnapshot(f); semanticStep(before, after, 'membership_verified', 1); before = after;
  const exactTime = after.status.membership_observed_at_us;
  claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
  semanticStep(before, await semanticSnapshot(f), 'membership_verified', 0);
  assert(await storage.finishAlbumAttachment(f.db, claim, present()));
  after = await semanticSnapshot(f); semanticStep(before, after, 'membership_verified', 1); before = after;
  assert.equal(after.status.membership_observed_at_us, exactTime, 'same-millisecond proof still has a new revision');
  claim = await storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
  marker = await storage.markAlbumAttachmentDispatch(f.db, claim, []); assert(marker);
  after = await semanticSnapshot(f); semanticStep(before, after, 'attachment_pending', 1); before = after;
  assert(await storage.currentAlbumAttachment(f.db, marker), 'own semantic progress retains immutable claim authority');
  assert(await storage.attentionAlbumAttachment(f.db, marker, 'missing_photo'));
  after = await semanticSnapshot(f); semanticStep(before, after, 'album_attachment_needs_attention', 1);
});

test('actual local D1 fresh proof and attention update status counters with atomic retained semantic history', async t => {
  const f = await claimed(t, { native: true }), before = await semanticSnapshot(f);
  assert(await f.storage.finishAlbumAttachment(f.db, f.claim, present()));
  const verified = await semanticSnapshot(f); semanticStep(before, verified, 'membership_verified', 1);
  const claim = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
  semanticStep(verified, await semanticSnapshot(f), 'membership_verified', 0);
  const marker = await f.storage.markAlbumAttachmentDispatch(f.db, claim, []); assert(marker);
  const pending = await semanticSnapshot(f); semanticStep(verified, pending, 'attachment_pending', 1);
  assert(await f.storage.attentionAlbumAttachment(f.db, marker, 'missing_photo'));
  semanticStep(pending, await semanticSnapshot(f), 'album_attachment_needs_attention', 1);
  for (const sql of ['DELETE FROM album_attachment_semantic_events', 'UPDATE album_attachment_semantic_events SET state=state', 'INSERT OR REPLACE INTO album_attachment_semantic_events SELECT * FROM album_attachment_semantic_events'])
    await assert.rejects(f.db.prepare(sql).run());
});

test('a stale epoch cannot replay a semantic fact after newer reconciliation changes state', async t => {
  const f = await marked(t), clock = databaseClock(f.db);
  assert(await f.storage.unknownAlbumAttachment(f.db, f.claim));
  clock.set((await f.attempts()).at(-1).retry_after_us);
  const old = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(old?.reconciliationOnly);
  assert(await f.storage.unknownAlbumAttachment(f.db, old));
  clock.set((await f.attempts()).at(-1).retry_after_us);
  const next = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(next?.reconciliationOnly);
  assert(await f.storage.deferAlbumAttachment(f.db, next, absent()));
  const before = await retained(f.db), snapshot = await semanticSnapshot(f);
  const event = await f.db.prepare('SELECT MAX(event_ordinal) ordinal FROM album_attachment_events WHERE attempt_id=?').bind(old.attemptId).first();
  await assert.rejects(f.db.prepare(`INSERT INTO album_attachment_semantic_events(attempt_id,event_ordinal,obligation_id,binding_id,binding_revision_before,binding_revision_after,obligation_revision_before,obligation_revision_after,state,membership_observed_at_us)
    VALUES(?,?,?,?,?,?,?,?,'membership_reconciliation_pending',NULL)`).bind(old.attemptId,event.ordinal,f.obligationId,f.bindingId,snapshot.binding,snapshot.binding+1,snapshot.obligation,snapshot.obligation+1).run());
  assert.deepEqual(await retained(f.db), before);
});

test('another pair semantic change fences a concurrent immutable claim while preserving safe unknown closure', async t => {
  const f = await attachmentFixture(t), storage = await api();
  const binding = await f.db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
  const other = await f.associate('third-photo', binding.binding_revision);
  const claim = await storage.claimAlbumAttachment(f.db, f.obligationId), second = await storage.claimAlbumAttachment(f.db, other.obligation.fgaAlbumObligationId); assert(claim && second);
  const marker = await storage.markAlbumAttachmentDispatch(f.db, claim, []); assert(marker);
  assert(await storage.finishAlbumAttachment(f.db, second, { ownerNsid:'owner',photoId:'third-remote',contextIds:[SET] }));
  assert.equal(await storage.currentAlbumAttachment(f.db, marker), false);
  assert.equal(await storage.finishAlbumAttachment(f.db, marker, present()), false);
  assert.equal(await storage.markAlbumAttachmentDispatch(f.db, claim, []), null);
  assert(await storage.unknownAlbumAttachment(f.db, marker));
  assert.equal((await semanticSnapshot(f)).status.state, 'membership_reconciliation_pending');
});

test('actual local D1 archived marked drift has read-only recovery and strict absence cannot schedule another add', async t => {
  for (const found of [false, true]) {
    const f = await claimed(t, { native: true });
    assert(await f.storage.finishAlbumAttachment(f.db, f.claim, present()));
    const claim = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(claim);
    const marker = await f.storage.markAlbumAttachmentDispatch(f.db, claim, []); assert(marker);
    await f.archive(); assert(await f.storage.unknownAlbumAttachment(f.db, marker));
    const due = (await f.attempts()).at(-1).retry_after_us;
    const { now } = await f.db.prepare('SELECT ' + NOW_US_SQL + ' now').first();
    await new Promise(resolve => setTimeout(resolve, Math.max(0, Math.ceil((due-now)/1000))+10));
    const recovery = await f.storage.claimAlbumAttachment(f.db, f.obligationId); assert(recovery?.reconciliationOnly && recovery.archivedAfterFulfillment);
    assert.equal(await f.storage.markAlbumAttachmentDispatch(f.db, recovery, []), null);
    assert.equal(await f.storage.deferAlbumAttachment(f.db, recovery, absent()), false);
    assert.equal(found ? await f.storage.finishAlbumAttachment(f.db, recovery, present()) : await f.storage.attentionAlbumAttachment(f.db, recovery, 'archived_drift_unresolved', absent()), true);
    assert.equal((await f.attempts()).filter(row => row.dispatch_count === 1).length, 1);
    assert.equal(await f.storage.claimAlbumAttachment(f.db, f.obligationId), null);
  }
});
