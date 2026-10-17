import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { Miniflare } from 'miniflare';
import { titleFixture,titleSqlStore,titleSnapshot,titleProof,titleClock,pauseBatch,ORIGINAL } from './album_title_fixture.mjs';
import * as api from '../src/album_title_store.ts';
import { claimAlbumMaterialization,markAlbumCreateDispatch } from '../src/album_materialization_store.ts';

async function claimed(t) { const f=await titleFixture(t,{desiredTitle:'Latest title'}); const claim=await api.claimAlbumTitle(f.db,f.bindingId); assert(claim); return {...f,claim}; }
async function marked(t) { const f=await claimed(t); const read=await api.beginAlbumTitleRead(f.db,f.claim); assert(read); const claim=await api.markAlbumTitleDispatch(f.db,read,titleProof(ORIGINAL)); assert(claim); return {...f,claim}; }
const request=(b,title)=>({schemaVersion:1,expectedBindingRevision:b.binding_revision,expectedTitleRevision:b.title_revision,desiredTitle:title});
const attempts=f=>f.db.raw.prepare('SELECT * FROM album_title_attempts WHERE binding_id=? ORDER BY rowid').all(f.bindingId);
async function reclaimMarked(f){const original=attempts(f)[0],clock=titleClock(f.db);clock.set(Math.max(original.lease_expires_at_us,original.next_read_at_us));const claim=await api.claimAlbumTitle(f.db,f.bindingId);assert(claim);assert.equal(claim.attemptId,original.attempt_id);assert.equal(claim.dispatchCount,1);assert(claim.epoch>original.epoch);assert.equal(claim.bindingRevision,(await f.binding()).binding_revision);assert.equal(attempts(f)[0].binding_revision,original.binding_revision);return claim;}

test('same text is a deliberate new revision; old exact receipt replays without mutating work after supersession',async t=>{
 const f=await titleFixture(t), b=await f.binding(), body=request(b,ORIGINAL);
 const first=await api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,body); assert.equal(first.created,true);
 assert.equal(first.receipt.acceptedTitleRevision,2);assert.equal(first.receipt.acceptedDesiredTitle,ORIGINAL);
 assert.equal(first.receipt.acceptedBindingRevision,b.binding_revision+1);
 await f.rename('A later deliberate name');const before=await titleSnapshot(f.db);
 const replay=await api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,body);assert.equal(replay.created,false);
 for(const key of ['acceptedAt','acceptedTitleRevision','acceptedBindingRevision','acceptedDesiredTitle']) assert.deepEqual(replay.receipt[key],first.receipt[key]);
 assert.equal(replay.receipt.current.binding.titleRevision,3);assert.deepEqual(await titleSnapshot(f.db),before);
 await assert.rejects(api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,{...body,desiredTitle:'Different'}),/title_intent_conflict/);
 assert.deepEqual(await titleSnapshot(f.db),before);
});

test('concurrent distinct rename requests have one winner and never silently upgrade a stale request',async t=>{
 const f=await titleFixture(t),b=await f.binding(),gate=pauseBatch(f.db);
 const delayed=api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,request(b,'Losing rename')); await gate.pending;
 const winner=await api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,request(b,'Winning rename'));gate.release();
 await assert.rejects(delayed,/title_intent_conflict|stale_binding_revision/);assert.equal(winner.created,true);
 assert.equal((await f.binding()).desired_title,'Winning rename');
 assert.equal((await titleSnapshot(f.db)).album_title_receipts.length,1);
});

test('exact receipt replay after archive and remote authority loss preserves original acceptance without reopening work',async t=>{
 const f=await titleFixture(t),b=await f.binding(),body=request(b,'Retained desired');const accepted=await api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,body);
 f.db.raw.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?").run(f.bindingId);
 f.db.raw.exec("UPDATE flickr_links SET state='paused' WHERE user_id='user'");const before=await titleSnapshot(f.db);
 const replay=await api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,2,body);assert.equal(replay.created,false);assert.equal(replay.receipt.acceptedAt,accepted.receipt.acceptedAt);assert.equal(replay.receipt.acceptedDesiredTitle,'Retained desired');assert.equal(replay.receipt.current.localLifecycle,'local_collection_removed_remote_preserved');assert.deepEqual(await titleSnapshot(f.db),before);
 await assert.rejects(f.rename('Forbidden after archive'),/album_closed/);assert.deepEqual(await titleSnapshot(f.db),before);
});

test('stale binding takes precedence over stale title and failed new-intent fences retain every row',async t=>{
 const f=await titleFixture(t),b=await f.binding();await f.rename('New revision');const before=await titleSnapshot(f.db);
 await assert.rejects(api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,3,request(b,'Stale')),/stale_binding_revision/);
 const current=await f.binding();await assert.rejects(api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,3,{...request(current,'Stale title'),expectedTitleRevision:1}),/stale_title_revision/);
 assert.deepEqual(await titleSnapshot(f.db),before);
});

// Counters cannot be advanced quadrillions of times in a finite test. Only this
// fixture setup suspends and restores the exact production guard; every tested
// operation below executes with that original SQL guard installed.
function setBoundaryFixture(db,guard,sql,args=[]){const definition=db.raw.prepare("SELECT sql FROM sqlite_schema WHERE type='trigger' AND name=?").get(guard).sql;db.raw.exec('DROP TRIGGER '+guard);try{db.raw.prepare(sql).run(...args);}finally{db.raw.exec(definition);}}
test('maximum safe binding/title revisions refuse a new intent without changing acceptance or work',async t=>{
 for(const which of ['binding','title']){const f=await titleFixture(t);setBoundaryFixture(f.db,'album_binding_revision',which==='binding'?'UPDATE album_bindings SET binding_revision=9007199254740991 WHERE binding_id=?':'UPDATE album_bindings SET binding_revision=binding_revision+1,title_revision=9007199254740991 WHERE binding_id=?',[f.bindingId]);const b=await f.binding(),before=await titleSnapshot(f.db);
  await assert.rejects(api.putAlbumTitleIntent(f.db,f.auth,f.bindingId,which==='title'?Number.MAX_SAFE_INTEGER:b.title_revision+1,request(b,'Exhausted rename')),/revision_exhausted/);assert.deepEqual(await titleSnapshot(f.db),before);
 }
});

test('maximum safe claim epoch cannot wrap, take over or allocate a competing attempt',async t=>{
 const f=await marked(t);setBoundaryFixture(f.db,'album_title_attempt_update','UPDATE album_title_attempts SET epoch=9007199254740991 WHERE attempt_id=?',[f.claim.attemptId]);const clock=titleClock(f.db);clock.set(attempts(f)[0].lease_expires_at_us);const before=await titleSnapshot(f.db);assert.equal(await api.claimAlbumTitle(f.db,f.bindingId),null);assert.deepEqual(await titleSnapshot(f.db),before);
});

test('rename before create marker changes its frozen title; rename after marker cannot change dispatched metadata',async t=>{
 const f=await titleFixture(t,{materialized:false});const old=await claimAlbumMaterialization(f.db,f.bindingId);assert(old);
 await f.rename('Before create');assert.equal(await markAlbumCreateDispatch(f.db,old,[]),null);
 const g=await titleFixture(t,{materialized:false});const claimed=await claimAlbumMaterialization(g.db,g.bindingId);
 const marked=await markAlbumCreateDispatch(g.db,claimed,[]);assert(marked);await g.rename('After create');
 assert.equal(marked.desiredTitle,ORIGINAL);assert.equal(marked.titleRevision,1);
 const row=g.db.raw.prepare('SELECT * FROM album_materialization_attempts WHERE attempt_id=?').get(marked.attemptId);
 assert.equal(row.desired_title,ORIGINAL);assert.equal(row.title_revision,1);assert.equal(row.dispatch_count,1);
 assert.equal(await api.claimAlbumTitle(g.db,g.bindingId),null,'unresolved create has no metadata write authority');
});

test('every new-intent transaction statement failure rolls back revision, exact receipt and sanitized event together',async t=>{
 const base=await titleFixture(t),original=base.db.batch.bind(base.db);let length=0;base.db.batch=s=>{length=s.length;return original(s);};await base.rename('Fault baseline');assert(length>0);
 for(let fault=0;fault<length;fault++){const f=await titleFixture(t),before=await titleSnapshot(f.db);f.db.fault=fault;await assert.rejects(f.rename('Failed rename'));f.db.fault=-1;assert.deepEqual(await titleSnapshot(f.db),before,'statement '+fault);}
});

test('marker and result transactions reject a changed link, grant, write gate or stale lease without clearing dispatch evidence',async t=>{
 for(const sql of ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'","UPDATE flickr_native_credentials SET active_generation='new-generation' WHERE user_id='user'","UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'"]){
  for(const phase of ['marker','result']){const f=phase==='marker'?await claimed(t):await marked(t);let claim=f.claim;
   if(phase==='marker'){claim=await api.beginAlbumTitleRead(f.db,claim);assert(claim);}f.db.raw.exec(sql);const before=await titleSnapshot(f.db);
   const value=phase==='marker'?await api.markAlbumTitleDispatch(f.db,claim,titleProof(ORIGINAL)):await api.reconcileAlbumTitle(f.db,claim,titleProof('Latest title'));
   assert(!value||value==='stale');assert.deepEqual(await titleSnapshot(f.db),before,phase+': '+sql);
  }
 }
});

test('every claim, read charge, marker, result and reconciliation statement failure rolls back its audit atomically',async t=>{
 const fixtureFor=async phase=>{const f=phase==='claim'?await titleFixture(t,{desiredTitle:'Latest title'}):phase==='read'||phase==='marker'?await claimed(t):await marked(t);if(phase==='marker'||phase==='reconcile')f.claim=await api.beginAlbumTitleRead(f.db,f.claim);return f;};
 const operations={claim:f=>api.claimAlbumTitle(f.db,f.bindingId),read:f=>api.beginAlbumTitleRead(f.db,f.claim),marker:f=>api.markAlbumTitleDispatch(f.db,f.claim,titleProof(ORIGINAL)),result:f=>api.recordAlbumTitleResult(f.db,f.claim,'success'),reconcile:f=>api.reconcileAlbumTitle(f.db,f.claim,titleProof('Latest title'))};
 for(const [phase,operation]of Object.entries(operations)){const base=await fixtureFor(phase),batch=base.db.batch.bind(base.db);let count=0;base.db.batch=s=>{count=Math.max(count,s.length);return batch(s);};await operation(base);assert(count>0,phase);
  for(let fault=0;fault<count;fault++){const f=await fixtureFor(phase),before=await titleSnapshot(f.db);f.db.fault=fault;try{await operation(f);}catch{}f.db.fault=-1;assert.deepEqual(await titleSnapshot(f.db),before,phase+' statement '+fault);}
 }
});

test('event failure rolls back observed success and keeps the unresolved marker',async t=>{
 const f=await marked(t);f.claim=await api.beginAlbumTitleRead(f.db,f.claim);const before=await titleSnapshot(f.db);f.db.raw.exec("CREATE TRIGGER injected_title_event BEFORE INSERT ON album_title_events WHEN NEW.state='synced' BEGIN SELECT RAISE(ABORT,'injected_title_audit_failure'); END");await assert.rejects(api.reconcileAlbumTitle(f.db,f.claim,titleProof('Latest title')));assert.deepEqual(await titleSnapshot(f.db),before);
});

test('marked reconciliation retains exact latest-title priority when latest, dispatched and pre-dispatch text overlap',async t=>{
 const f=await marked(t);await f.rename(ORIGINAL);const before=await titleSnapshot(f.db);assert.equal(await api.currentAlbumTitle(f.db,f.claim),false);assert.equal(await api.beginAlbumTitleRead(f.db,f.claim),null);assert.equal(await api.reconcileAlbumTitle(f.db,f.claim,titleProof(ORIGINAL)),null);assert.deepEqual(await titleSnapshot(f.db),before);
 const recovered=await reclaimMarked(f),read=await api.beginAlbumTitleRead(f.db,recovered);assert(read);
 await api.reconcileAlbumTitle(f.db,read,titleProof(ORIGINAL));
 const lifecycle=await api.readAlbumLifecycle(f.db,f.auth,f.bindingId);assert.equal(lifecycle.binding.titleRevision,3);assert.equal(lifecycle.title.state,'synced');
 assert.equal(await api.claimAlbumTitle(f.db,f.bindingId),null);assert.equal(attempts(f).reduce((n,a)=>n+a.dispatch_count,0),1);
});

test('unavailable marked observation preserves marker and cannot authorize a newer revision to bypass it',async t=>{
 const f=await marked(t);await f.rename('Newer intent');const before=await titleSnapshot(f.db);assert.equal(await api.recordAlbumTitleResult(f.db,f.claim,'success'),false);assert.equal(await api.beginAlbumTitleRead(f.db,f.claim),null);assert.equal(await api.reconcileAlbumTitle(f.db,f.claim,titleProof('Latest title')),null);assert.deepEqual(await titleSnapshot(f.db),before);
 const recovered=await reclaimMarked(f),read=await api.beginAlbumTitleRead(f.db,recovered);assert(read);await api.reconcileAlbumTitle(f.db,read,null);
 const life=await api.readAlbumLifecycle(f.db,f.auth,f.bindingId);assert.equal(life.title.state,'reconciliation_pending');
 assert.equal(attempts(f)[0].dispatch_count,1);assert.equal((await f.binding()).desired_title,'Newer intent');
 const next=await api.claimAlbumTitle(f.db,f.bindingId);if(next)assert.equal(next.titleRevision,2,'new revision cannot bypass an unresolved old marker');
});

test('title semantic changes advance binding exactly once while claim, reads, receipt and lease bookkeeping do not',async t=>{
 const f=await claimed(t),base=(await f.binding()).binding_revision,titleRevision=(await f.binding()).title_revision;
 const read=await api.beginAlbumTitleRead(f.db,f.claim);assert(read);assert.equal((await f.binding()).binding_revision,base);
 const marked=await api.markAlbumTitleDispatch(f.db,read,titleProof(ORIGINAL));assert(marked);assert.equal((await f.binding()).binding_revision,base+1);assert.equal((await f.binding()).title_revision,titleRevision);
 assert.equal(await api.recordAlbumTitleResult(f.db,marked,'success'),true);assert.equal((await f.binding()).binding_revision,base+1);
 const post=await api.beginAlbumTitleRead(f.db,marked);assert(post);assert.equal((await f.binding()).binding_revision,base+1);
 assert.equal(await api.reconcileAlbumTitle(f.db,post,titleProof('Latest title')),'synced');assert.equal((await f.binding()).binding_revision,base+2);assert.equal((await f.binding()).title_revision,titleRevision);
 const before=await titleSnapshot(f.db);await api.readAlbumLifecycle(f.db,f.auth,f.bindingId);assert.equal(await api.reconcileAlbumTitle(f.db,post,titleProof('Latest title')),null);assert.deepEqual(await titleSnapshot(f.db),before);
 const events=before.album_title_semantic_events;assert.equal(events.length,2);assert.deepEqual(events.map(e=>[e.binding_revision_before,e.binding_revision_after]),[[base,base+1],[base+1,base+2]]);
 const g=await claimed(t),gbase=(await g.binding()).binding_revision,clock=titleClock(g.db),charged=await api.beginAlbumTitleRead(g.db,g.claim);assert(charged);assert.equal(await api.releaseAlbumTitle(g.db,charged),true);let row=attempts(g)[0];clock.set(Math.max(row.next_read_at_us,row.lease_expires_at_us));const next=await api.claimAlbumTitle(g.db,g.bindingId);assert(next);assert(next.epoch>g.claim.epoch);assert.equal((await g.binding()).binding_revision,gbase);
});

test('missing evidence advances binding once and unavailable post-read retains timestamped pre-title evidence',async t=>{
 const f=await marked(t),before=await api.readAlbumLifecycle(f.db,f.auth,f.bindingId),base=(await f.binding()).binding_revision;assert.equal(before.title.observedTitle,ORIGINAL);assert(before.title.observedAt);
 const read=await api.beginAlbumTitleRead(f.db,f.claim);assert(read);await api.reconcileAlbumTitle(f.db,read,null);const pending=await api.readAlbumLifecycle(f.db,f.auth,f.bindingId);assert.equal(pending.title.observedTitle,ORIGINAL);assert.equal(pending.title.observedAt,before.title.observedAt);assert.equal((await f.binding()).binding_revision,base);
 const g=await claimed(t),gb=(await g.binding()).binding_revision,charged=await api.beginAlbumTitleRead(g.db,g.claim);assert(charged);assert.equal(await api.missingAlbumTitle(g.db,charged),true);assert.equal((await g.binding()).binding_revision,gb+1);const snapshot=await titleSnapshot(g.db);assert.equal(await api.missingAlbumTitle(g.db,charged),false);assert.deepEqual(await titleSnapshot(g.db),snapshot);
});

test('expired lease can only resume with a new epoch and stale claims cannot dispatch or complete',async t=>{
 const f=await marked(t),clock=titleClock(f.db),expiry=attempts(f)[0].lease_expires_at_us;clock.set(expiry);
 assert.equal(await api.currentAlbumTitle(f.db,f.claim),false);const next=await api.claimAlbumTitle(f.db,f.bindingId);
 if(next){assert(next.epoch>f.claim.epoch);assert.notEqual(next.leaseId,f.claim.leaseId);assert.equal(next.dispatchCount,1);}
 const before=await titleSnapshot(f.db);assert.equal(await api.markAlbumTitleDispatch(f.db,f.claim,titleProof(ORIGINAL)),null);
 await api.reconcileAlbumTitle(f.db,f.claim,titleProof('Latest title'));assert.deepEqual(await titleSnapshot(f.db),before);
});

test('crash after the fifth reserved read becomes durable attention on expiry even if remote authority changed',async t=>{
 for(const dispatched of [false,true]){const f=dispatched?await marked(t):await claimed(t),clock=titleClock(f.db);let c=f.claim;while(c.readCount<5){const read=await api.beginAlbumTitleRead(f.db,c);if(read){c=read;}else{const row=attempts(f)[0];clock.set(Math.max(row.lease_expires_at_us,row.next_read_at_us));c=await api.claimAlbumTitle(f.db,f.bindingId);assert(c);}}clock.set(attempts(f)[0].lease_expires_at_us);f.db.raw.exec("UPDATE flickr_links SET state='paused' WHERE user_id='user'");
  assert.equal(await api.claimAlbumTitle(f.db,f.bindingId),null);const row=attempts(f)[0];assert.equal(row.state,'needs_attention');assert.equal(row.read_count,5);assert.equal(row.dispatch_count,dispatched?1:0);assert.equal((await api.readAlbumLifecycle(f.db,f.auth,f.bindingId)).title.state,'needs_attention');assert.equal(await api.beginAlbumTitleRead(f.db,c),null);
 }
});

test('ordinary SQL cannot erase immutable title receipts, attempt markers or append-only title history',async t=>{
 const f=await marked(t);
 for(const sql of ['DELETE FROM album_title_receipts','DELETE FROM album_title_attempts','DELETE FROM album_title_events','DELETE FROM album_title_semantic_events',"UPDATE album_title_receipts SET desired_title='Replacement'",'UPDATE album_title_attempts SET dispatch_count=0']){
  const before=await titleSnapshot(f.db);assert.throws(()=>f.db.raw.exec(sql),undefined,sql);assert.deepEqual(await titleSnapshot(f.db),before);
 }
});

async function nativeMigrations(){return JSON.parse(execFileSync('uv',['tool','run','--from','uv==0.12.5','uv','run','--frozen','python','-c',"import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([{'name':p.name,'sql':statements(p.read_text(encoding='utf-8'))} for p in sorted(Path('migrations').glob('*.sql'))]))"],{encoding:'utf8'}));}
test('actual local D1 migration0024 preserves populated bindings, primary membership and prior append-only history; failed migration rolls back',async t=>{
 const migrations=await nativeMigrations(),mf=new Miniflare({modules:true,script:'export default {fetch(){return new Response("local title proof")}}',compatibilityDate:'2026-07-30',cf:false,telemetry:{enabled:false},d1Databases:['DB'],outboundService(){throw new Error('No live network');}});t.after(()=>mf.dispose());
 const db=await mf.getD1Database('DB');for(const migration of migrations.filter(m=>m.name<'0024_'))await db.batch(migration.sql.map(sql=>db.prepare(sql)));
 const f=await titleFixture({after(){}},{db}),tables=['album_bindings','album_binding_events','album_photo_obligations','album_obligation_events','album_materialization_attempts','album_materialization_events'];const before=await titleSnapshot(db,tables);
 const migration=migrations.find(m=>m.name==='0024_album_title_sync.sql');assert(migration);
 const failed=[...migration.sql,"SELECT json_extract('synthetic-invalid-json','$')"];await assert.rejects(db.batch(failed.map(sql=>db.prepare(sql))));assert.deepEqual(await titleSnapshot(db,tables),before);
 await db.batch(migration.sql.map(sql=>db.prepare(sql)));const after=await titleSnapshot(db,tables);
 for(const table of tables)for(let i=0;i<before[table].length;i++)for(const [key,value]of Object.entries(before[table][i]))assert.deepEqual(after[table][i][key],value,table+':'+key);
 assert.deepEqual((await db.prepare('PRAGMA foreign_key_check').all()).results,[]);
 await f.rename('Native title');const revisionBefore=(await f.binding()).binding_revision;let c=await api.claimAlbumTitle(db,f.bindingId);assert(c);const failedRead=await api.beginAlbumTitleRead(db,c);assert(failedRead);await api.reconcileAlbumTitle(db,failedRead,null);await new Promise(resolve=>setTimeout(resolve,5100));c=await api.claimAlbumTitle(db,f.bindingId);assert(c);assert.equal(c.dispatchCount,0);const r=await api.beginAlbumTitleRead(db,c);assert(r);assert.equal((await f.binding()).binding_revision,revisionBefore);const marked=await api.markAlbumTitleDispatch(db,r,titleProof(ORIGINAL));assert(marked);assert.equal((await f.binding()).binding_revision,revisionBefore+1);
 const post=await api.beginAlbumTitleRead(db,marked);assert(post);assert.equal((await f.binding()).binding_revision,revisionBefore+1);await api.reconcileAlbumTitle(db,post,titleProof('Native title'));assert.equal((await api.readAlbumLifecycle(db,f.auth,f.bindingId)).title.state,'synced');assert.equal((await f.binding()).binding_revision,revisionBefore+2);const semantic=(await db.prepare('SELECT binding_revision_before,binding_revision_after FROM album_title_semantic_events WHERE binding_id=? ORDER BY binding_revision_after').bind(f.bindingId).all()).results;assert.deepEqual(semantic.map(e=>[e.binding_revision_before,e.binding_revision_after]),[[revisionBefore,revisionBefore+1],[revisionBefore+1,revisionBefore+2]]);
 await assert.rejects(db.prepare('DELETE FROM album_title_attempts').run());
});
