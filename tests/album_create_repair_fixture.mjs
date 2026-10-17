import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { Miniflare } from 'miniflare';
import { materializationFixture, AUTH } from './album_materialization_sqlite.mjs';
import * as materialization from '../src/album_materialization_store.ts';
import { NOW_US_SQL } from '../src/installations.ts';

export const INSTALL = { kind: 'installation', ...AUTH };
export const ADMIN = { kind: 'admin', sessionId: 'repair-session', tokenDigest: 'b'.repeat(64), ownerSub: 'synthetic-google-sub' };
export const migrationNames = () => readdirSync('migrations').filter(name => name.endsWith('.sql')).sort();
export function sqliteDatabase(through = '9999') {
  const raw = new DatabaseSync(':memory:'); raw.exec('PRAGMA foreign_keys=ON');
  for (const name of migrationNames().filter(name => name < through)) raw.exec(readFileSync('migrations/' + name, 'utf8'));
  const db = { raw, fault: -1,
    prepare(sql) { return { sql, args: [], bind(...args) { this.args = args; return this; },
      async first() { return raw.prepare(sql).get(...this.args) ?? null; },
      async all() { return { results: raw.prepare(sql).all(...this.args) }; },
      async run() { return { results: raw.prepare(sql).all(...this.args), meta: { changes: raw.prepare('SELECT changes() n').get().n } }; },
    }; },
    async batch(statements) { raw.exec('BEGIN'); try { const results = []; for (let i = 0; i < statements.length; i++) {
      if (i === db.fault) throw new Error('injected_repair_statement_failure');
      results.push(await statements[i].run());
    } raw.exec('COMMIT'); return results; } catch (error) { raw.exec('ROLLBACK'); throw error; } },
  };
  return db;
}
let nativeMigrations;
export function splitMigrations() {
  return nativeMigrations ??= JSON.parse(execFileSync('uv', ['tool', 'run', '--from', 'uv==0.12.5', 'uv', 'run', '--frozen', 'python', '-c',
    "import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([{'name':p.name,'sql':statements(p.read_text(encoding='utf-8'))} for p in sorted(Path('migrations').glob('*.sql'))]))"], { encoding: 'utf8' }));
}
export async function nativeDatabase(t, through = '9999') {
  const mf = new Miniflare({ modules: true, script: 'export default {fetch(){return new Response("synthetic local proof")}}',
    compatibilityDate: '2026-07-30', cf: false, telemetry: { enabled: false }, d1Databases: ['DB'],
    outboundService() { throw new Error('No live network'); } });
  t.after(() => mf.dispose());
  const db = await mf.getD1Database('DB');
  for (const item of splitMigrations().filter(item => item.name < through)) await db.batch(item.sql.map(sql => db.prepare(sql)));
  return db;
}
export async function applyRemaining(db, from = '0023_') {
  for (const item of splitMigrations().filter(item => item.name >= from)) await db.batch(item.sql.map(sql => db.prepare(sql)));
}
export const rows = async (db, table) => (await db.prepare('SELECT * FROM ' + table + ' ORDER BY rowid').all()).results;
export async function retained(db) {
  const tables = (await db.prepare("SELECT name FROM sqlite_schema WHERE type='table' AND (name LIKE 'album_%' OR name IN ('transaction_guards','audit_events')) ORDER BY name").all()).results;
  return Object.fromEntries(await Promise.all(tables.map(async ({ name }) => [name, await rows(db, name)])));
}
export const firstBinding = async f => f.db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
export async function unknownFixture(t, options = {}) {
  const db = options.db ?? sqliteDatabase();
  if (db.raw) t.after(() => db.raw.close());
  const f = await materializationFixture({ after() {} }, db);
  await db.batch([
    db.prepare("INSERT INTO admin_principals(user_id,google_issuer,google_sub) VALUES('user','https://accounts.google.com','synthetic-google-sub')"),
    db.prepare(`INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id)
      VALUES(?,?,'user',?,${NOW_US_SQL},${NOW_US_SQL},${NOW_US_SQL}+86400000000,${NOW_US_SQL},'repair-correlation')`)
      .bind(ADMIN.sessionId, ADMIN.tokenDigest, 'c'.repeat(43)),
  ]);
  if (options.later !== false) await f.associate('later-photo');
  const claimed = await materialization.claimAlbumMaterialization(db, f.bindingId);
  if (!claimed) throw new Error('fixture_materialization_not_claimed');
  const claim = await materialization.markAlbumCreateDispatch(db, claimed, ['before-set']);
  if (!claim) throw new Error('fixture_materialization_not_marked');
  if (options.received) await materialization.recordAlbumCreateResult(db, claim,
    { photosetId: 'uncertain-returned-set', url: 'https://www.flickr.com/photos/owner/albums/uncertain-returned-set' });
  if (!await materialization.unknownAlbumMaterialization(db, claim)) throw new Error('fixture_materialization_not_unknown');
  return { ...f, claim };
}
export function delayFirstBatch(db) {
  const original = db.batch.bind(db); let reached, release, calls = 0;
  const pending = new Promise(resolve => reached = resolve), permit = new Promise(resolve => release = resolve);
  db.batch = async statements => { if (++calls === 1) { reached(); await permit; } return original(statements); };
  return { pending, release };
}
