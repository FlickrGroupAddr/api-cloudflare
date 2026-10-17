import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import { materializationFixture, databaseClock } from './album_materialization_sqlite.mjs';
import { claimAlbumMaterialization, markAlbumCreateDispatch, recordAlbumCreateResult, finishAlbumMaterialization } from '../src/album_materialization_store.ts';

export const SET = 'title-set', OWNER = 'owner', ORIGINAL = 'Synthetic album';
export function titleSqlStore(before = null) {
  const raw = new DatabaseSync(':memory:'); raw.exec('PRAGMA foreign_keys=ON');
  for (const name of readdirSync('migrations').filter(name => name.endsWith('.sql') && (!before || name < before)).sort()) raw.exec(readFileSync('migrations/' + name, 'utf8'));
  const db = { raw, fault: -1, prepare(sql) { return { args: [], bind(...args) { this.args=args; return this; },
    async first() { return raw.prepare(sql).get(...this.args) ?? null; },
    async all() { return { results: raw.prepare(sql).all(...this.args) }; },
    async run() { const results=raw.prepare(sql).all(...this.args); return { results, meta: { changes: raw.prepare('SELECT changes() n').get().n } }; },
  }; }, async batch(statements) { raw.exec('BEGIN'); try { const out=[]; for(let i=0;i<statements.length;i++) { if(i===db.fault) throw new Error('injected_title_transaction_failure'); out.push(await statements[i].run()); } raw.exec('COMMIT'); return out; } catch(error) { raw.exec('ROLLBACK'); throw error; } } };
  return db;
}
export async function titleFixture(t, { db = titleSqlStore(), materialized = true, desiredTitle = null } = {}) {
  const f=await materializationFixture(t, db);
  f.auth={ installationId: 'install', credentialDigest: 'a'.repeat(64) };
  if(materialized) {
    const claimed=await claimAlbumMaterialization(db,f.bindingId); assert(claimed);
    const marked=await markAlbumCreateDispatch(db,claimed,[]); assert(marked);
    const result={photosetId:SET,url:'https://www.flickr.com/photos/owner/albums/title-set/',ownerNsid:OWNER,primaryPhotoId:'primary-remote',contextIds:[SET]};
    assert.equal(await recordAlbumCreateResult(db,marked,result),true);
    assert.equal(await finishAlbumMaterialization(db,marked,result),true);
  }
  f.binding=async()=>db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
  f.rename=async title=>{ const b=await f.binding(); const api=await import('../src/album_title_store.ts'); return api.putAlbumTitleIntent(db,f.auth,f.bindingId,b.title_revision+1,{schemaVersion:1,expectedBindingRevision:b.binding_revision,expectedTitleRevision:b.title_revision,desiredTitle:title}); };
  if(desiredTitle!==null) await f.rename(desiredTitle);
  return f;
}
export const titleTables=['album_bindings','album_binding_events','album_photo_obligations','album_obligation_events','album_materialization_attempts','album_materialization_events','album_title_receipts','album_title_attempts','album_title_events','album_title_semantic_events','transaction_guards'];
export async function titleSnapshot(db, tables=titleTables) { return Object.fromEntries(await Promise.all(tables.map(async table=>[table,(await db.prepare('SELECT * FROM '+table+' ORDER BY rowid').all()).results]))); }
export const titleProof = title => ({photosetId:SET,ownerNsid:OWNER,title});
export function titleClock(db) { const c=databaseClock(db); let now=Date.now()*1000; c.set(now); return { advance:ms=>{now+=ms*1000;c.set(now);},set:us=>{now=us;c.set(now);} }; }
export function pauseBatch(db, match = () => true) { const batch=db.batch.bind(db); let enter,release,paused=false; const pending=new Promise(resolve=>enter=resolve),permit=new Promise(resolve=>release=resolve); db.batch=async statements=>{if(!paused&&match(statements)){paused=true;enter();await permit;}return batch(statements);};return {pending,release}; }
