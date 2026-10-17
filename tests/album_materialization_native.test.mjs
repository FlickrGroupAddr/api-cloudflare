import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { Miniflare } from 'miniflare';
import { materializationFixture } from './album_materialization_sqlite.mjs';
import { claimAlbumMaterialization, markAlbumCreateDispatch, recordAlbumCreateResult, finishAlbumMaterialization } from '../src/album_materialization_store.ts';

const migrations = JSON.parse(execFileSync('uv', ['tool', 'run', '--from', 'uv==0.12.5', 'uv', 'run', '--frozen', 'python', '-c',
  "import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([{'name':p.name,'sql':statements(p.read_text(encoding='utf-8'))} for p in sorted(Path('migrations').glob('*.sql'))]))"], { encoding: 'utf8' }));
const migration = migrations.find(item => item.name === '0022_album_materialization.sql').sql;
async function nativeFixture(t) {
  const mf = new Miniflare({ modules: true, script: 'export default {fetch(){return new Response("local proof")}}',
    compatibilityDate: '2026-07-30', cf: false, telemetry: { enabled: false }, d1Databases: ['DB'],
    outboundService() { throw new Error('No live network'); } });
  t.after(() => mf.dispose());
  const db = await mf.getD1Database('DB');
  for (const item of migrations.filter(item => item.name < '0022_')) await db.batch(item.sql.map(sql => db.prepare(sql)));
  const f = await materializationFixture({ after() {} }, db);
  await f.associate('later-photo');
  const archived = await f.ensure('third-photo', 'Archived:009');
  await db.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?")
    .bind(archived.binding.fgaAlbumBindingId).run();
  return f;
}
const tables = ['album_bindings', 'album_photo_obligations', 'album_binding_events', 'album_obligation_events'];
async function snapshot(db) {
  return Object.fromEntries(await Promise.all(tables.map(async table => [table, (await db.prepare('SELECT * FROM ' + table + ' ORDER BY rowid').all()).results])));
}
async function assertNoScratch(db) {
  assert.deepEqual((await db.prepare("SELECT name FROM sqlite_schema WHERE name LIKE 'retained_album_%' OR name='album_materialization_migration_guard'").all()).results, []);
}

test('actual local D1 migration0022 preserves populated active/archive history and supports guarded materialization', async t => {
  const f = await nativeFixture(t), before = await snapshot(f.db);
  // The former production statement is rejected by D1's actual authorizer.
  await assert.rejects(f.db.prepare('CREATE TEMP TABLE retained_album_obligations AS SELECT * FROM album_photo_obligations').run(), /SQLITE_AUTH|not authorized/i);
  await f.db.batch(migration.map(sql => f.db.prepare(sql)));
  const after = await snapshot(f.db);
  for (const table of tables) {
    assert.equal(after[table].length, before[table].length);
    for (let i = 0; i < before[table].length; i++)
      for (const [key, value] of Object.entries(before[table][i])) assert.deepEqual(after[table][i][key], value, table + ':' + key);
  }
  await assertNoScratch(f.db);
  assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
  const claim = await claimAlbumMaterialization(f.db, f.bindingId);
  assert(claim);
  const marked = await markAlbumCreateDispatch(f.db, claim, ['older-set']);
  assert(marked);
  assert.equal(await markAlbumCreateDispatch(f.db, claim, ['older-set']), null);
  const result = { photosetId: 'native-set', url: 'https://www.flickr.com/photos/owner/sets/native-set/' };
  assert.equal(await recordAlbumCreateResult(f.db, marked, result), true);
  assert.equal(await recordAlbumCreateResult(f.db, marked, result), false);
  assert.equal(await finishAlbumMaterialization(f.db, marked, { ...result, ownerNsid: 'owner', primaryPhotoId: 'primary-remote', contextIds: ['older-set', 'native-set'] }), true);
  assert.equal((await f.db.prepare('SELECT state FROM album_photo_obligations WHERE obligation_id=?').bind(f.first.obligation.fgaAlbumObligationId).first()).state, 'membership_verified');
  assert.equal(await claimAlbumMaterialization(f.db, f.bindingId), null);
  await assert.rejects(f.db.prepare('DELETE FROM album_materialization_attempts').run());
});

test('actual local D1 migration0022 failure rolls back rebuilt tables, history, guards and scratch rows atomically', async t => {
  const f = await nativeFixture(t), before = await snapshot(f.db);
  const failed = migration.map(sql => sql.startsWith('INSERT INTO album_materialization_migration_guard ')
    ? 'INSERT INTO album_materialization_migration_guard VALUES(0)' : sql);
  await assert.rejects(f.db.batch(failed.map(sql => f.db.prepare(sql))), /CHECK constraint failed/i);
  assert.deepEqual(await snapshot(f.db), before);
  await assertNoScratch(f.db);
  await assert.rejects(f.db.prepare('DELETE FROM album_photo_obligations').run());
  await assert.rejects(f.db.prepare('UPDATE album_obligation_events SET created_at_us=0').run());
  assert.deepEqual((await f.db.prepare('PRAGMA foreign_key_check').all()).results, []);
  await f.db.batch(migration.map(sql => f.db.prepare(sql)));
  await assertNoScratch(f.db);
});
