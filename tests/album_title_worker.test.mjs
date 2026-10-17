import test from 'node:test';
import assert from 'node:assert/strict';
import { titleFixture,titleClock,SET,OWNER,ORIGINAL } from './album_title_fixture.mjs';
import { consumeAlbumTitle } from '../src/album_title_worker.ts';
import { createSyntheticAlbumTitleTransport } from '../src/album_title_transport.ts';
import * as api from '../src/album_title_store.ts';

const INFO='flickr.photosets.getInfo',EDIT='flickr.photosets.editMeta';
const information=title=>({stat:'ok',photoset:{id:SET,owner:OWNER,primary:'primary-remote',title:{_content:title}}});
const attempts=f=>f.db.raw.prepare('SELECT * FROM album_title_attempts WHERE binding_id=? ORDER BY rowid').all(f.bindingId);
const writes=f=>f.calls.filter(c=>c.method===EDIT);
async function fixture(t){
 const f=await titleFixture(t,{desiredTitle:'Desired title'});Object.assign(f,{calls:[],hooks:{},responses:{},gates:[],remoteTitle:ORIGINAL});
 f.factory=(identity,assertCurrent,execution)=>createSyntheticAlbumTitleTransport(identity,{
  assertCurrent,execution,deadlineMs:f.deadlineMs,beforeRequest:async method=>{f.gates.push(method);await f.beforeRequest?.(method);},
  sign(method,data,post){const u=new URL('https://www.flickr.com/services/rest/');for(const [key,value]of Object.entries({method,format:'json',nojsoncallback:'1',...data}))u.searchParams.set(key,value);const body=post?u.searchParams.toString():undefined;if(post)u.search='';return new Request(u,{method:post?'POST':'GET',redirect:'manual',...(post?{body,headers:{'Content-Type':'application/x-www-form-urlencoded'}}:{})});},
  async fetcher(request){const params=request.method==='POST'?new URLSearchParams(await request.clone().text()):new URL(request.url).searchParams,method=params.get('method');f.calls.push({request,params,method});const count=f.calls.filter(c=>c.method===method).length;await f.hooks[method]?.(request,count);
   let response=typeof f.responses[method]==='function'?await f.responses[method](request,count):f.responses[method];
   if(response===undefined){if(method===EDIT){f.remoteTitle=params.get('title');response={stat:'ok'};}else response=information(f.remoteTitle);}
   return response instanceof Response?response:Response.json(response);
  }
 });f.run=hooks=>consumeAlbumTitle({DB:f.db,FGA_ALBUM_TITLE_SYNC_ENABLED:'1'},f.bindingId,f.factory,hooks);
 f.lifecycle=()=>api.readAlbumLifecycle(f.db,f.auth,f.bindingId);return f;
}

test('title consumer is dormant unless explicitly enabled, without claims or transport construction',async t=>{
 const f=await fixture(t);for(const flag of [undefined,'0','true',''])assert.equal(await consumeAlbumTitle({DB:f.db,FGA_ALBUM_TITLE_SYNC_ENABLED:flag},f.bindingId,()=>assert.fail('disabled transport')),'disabled');assert.equal(attempts(f).length,0);assert.equal(f.calls.length,0);
});

test('actual worker, store and strict transport require a durable marker then verify title by a fresh exact read',async t=>{
 const f=await fixture(t);f.hooks[EDIT]=()=>{const a=attempts(f)[0];assert.equal(a.dispatch_count,1);assert(a.dispatch_started_at_us>0);assert.equal(a.pre_dispatch_title,ORIGINAL);const p=f.calls.at(-1).params;assert.equal(p.get('photoset_id'),SET);assert.equal(p.get('title'),'Desired title');assert.equal(p.has('description'),false);};
 assert.equal(await f.run(),'synced');assert.deepEqual(f.calls.map(c=>c.method),[INFO,EDIT,INFO]);assert.equal((await f.lifecycle()).title.state,'synced');assert.equal(await f.run(),'no_work');assert.equal(writes(f).length,1);
 assert.deepEqual(f.gates,[INFO,EDIT,INFO]);
});

for(const [label,body]of [['wrong owner',{stat:'ok',photoset:{id:SET,owner:'foreign',primary:'primary-remote',title:{_content:ORIGINAL}}}],['wrong ID',{stat:'ok',photoset:{id:'other-set',owner:OWNER,primary:'primary-remote',title:{_content:ORIGINAL}}}],['missing title',{stat:'ok',photoset:{id:SET,owner:OWNER,primary:'primary-remote'}}],['duplicate title',new Response('{"stat":"ok","photoset":{"id":"title-set","owner":"owner","primary":"primary-remote","title":{"_content":"a","_content":"b"}}}')]])test(`strict pre-read ${label} consumes a read but sends no edit`,async t=>{
 const f=await fixture(t);f.responses[INFO]=body;await f.run();assert.equal(writes(f).length,0);assert.equal(attempts(f).reduce((n,a)=>n+a.dispatch_count,0),0);assert(attempts(f).some(a=>a.read_count>=1));assert.notEqual((await f.lifecycle()).title.state,'synced');
});

test('lost edit reply is resolved by a fresh desired-title read without a second dispatch',async t=>{
 const f=await fixture(t);f.hooks[EDIT]=()=>{f.remoteTitle='Desired title';throw new Error('Synthetic lost edit reply');};assert.equal(await f.run(),'synced');assert.equal(writes(f).length,1);assert.equal(await f.run(),'no_work');
});

test('explicit same-text intent is satisfied by observation without a redundant edit',async t=>{
 const f=await fixture(t);await f.rename(ORIGINAL);assert.equal(await f.run(),'synced');assert.equal(writes(f).length,0);assert.equal((await f.lifecycle()).binding.titleRevision,3);
});

test('missing remote album retains immutable photoset identity and never creates a replacement',async t=>{
 const f=await fixture(t);f.responses[INFO]={stat:'fail',code:1,message:'Synthetic missing album'};assert.equal(await f.run(),'needs_attention');assert.equal(writes(f).length,0);assert.equal((await f.binding()).flickr_photoset_id,SET);assert.equal(attempts(f)[0].remote_missing,1);assert.equal(f.db.raw.prepare('SELECT materialization_state FROM album_binding_remote_status WHERE binding_id=?').get(f.bindingId).materialization_state,'remote_album_missing_needs_attention');assert.equal((await f.lifecycle()).title.state,'needs_attention');assert.equal(await f.run(),'no_work');
});

test('a third title after successful edit becomes conflict and no later invocation overwrites it',async t=>{
 const f=await fixture(t);f.responses[EDIT]={stat:'ok'};f.responses[INFO]=(_r,n)=>information(n===1?ORIGINAL:'External third title');assert.equal(await f.run(),'conflict');assert.equal((await f.lifecycle()).title.observedTitle,'External third title');assert.equal(await f.run(),'no_work');assert.equal(writes(f).length,1);
});

test('newer desired text equal to the old pre-dispatch title wins equality priority and prevents retry',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[EDIT]={stat:'ok'};f.hooks[EDIT]=()=>f.rename(ORIGINAL);assert.equal(await f.run(),'reconciliation_pending');assert.equal((await f.lifecycle()).binding.titleRevision,3);assert.equal(f.calls.filter(c=>c.method===INFO).length,1);assert.equal(writes(f).length,1);
 const row=attempts(f)[0];clock.set(Math.max(row.lease_expires_at_us,row.next_read_at_us));assert.equal(await f.run(),'synced');assert.equal((await f.lifecycle()).title.state,'synced');assert.equal(await f.run(),'no_work');assert.equal(writes(f).length,1);assert.equal(attempts(f).length,1);assert.equal(attempts(f)[0].attempt_id,row.attempt_id);
});

test('observing the dispatched old title safely resolves it before separate newer intent can dispatch',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.hooks[EDIT]=(_r,n)=>n===1?f.rename('Newer desired'):undefined;
 assert.equal(await f.run(),'reconciliation_pending');assert.equal(writes(f).length,1);assert.equal((await f.binding()).desired_title,'Newer desired');assert.equal(f.calls.filter(c=>c.method===INFO).length,1);
 const row=attempts(f)[0];clock.set(Math.max(row.lease_expires_at_us,row.next_read_at_us));const before=f.calls.length;assert.equal(await f.run(),'superseded');assert.deepEqual(f.calls.slice(before).map(c=>c.method),[INFO]);assert.equal(writes(f).length,1);assert.equal(attempts(f)[0].attempt_id,row.attempt_id);
 assert.equal(await f.run(),'synced');assert.equal(writes(f).length,2);assert.equal(f.remoteTitle,'Newer desired');assert.equal((await f.lifecycle()).title.state,'synced');
});

test('new intent supersedes an unmarked old claim and becomes eligible without waiting for a dead old worker',async t=>{
 const f=await fixture(t);f.hooks[INFO]=async(_r,n)=>{if(n===1)await f.rename('Latest before marker');};assert.equal(await f.run(),'not_dispatched');assert.equal(writes(f).length,0);
 assert.equal(await f.run(),'synced');assert.equal(writes(f).length,1);assert.equal(writes(f)[0].params.get('title'),'Latest before marker');
});

test('pre-dispatch equality permits only three marked same-revision edits with durable 5 then 30 second backoff',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[EDIT]={stat:'ok'};
 assert.equal(await f.run(),'retry_pending');assert.equal(writes(f).length,1);assert.equal(await f.run(),'no_work');
 clock.advance(4999);assert.equal(await f.run(),'no_work');clock.advance(1);await f.run();assert.equal(writes(f).length,2);
 clock.advance(29999);assert.equal(await f.run(),'no_work');clock.advance(1);await f.run();assert.equal(writes(f).length,3);
 clock.advance(600000);await f.run();assert.equal(writes(f).length,3);assert.equal((await f.lifecycle()).title.state,'needs_attention');
 assert(attempts(f).at(-1).completed_at_us!==null,'fresh pre-title evidence safely resolves the third marker');await f.rename('Deliberate intent after resolved exhaustion');delete f.responses[EDIT];assert.equal(await f.run(),'synced');assert.equal(writes(f).length,4);
});

test('unavailable marked reads exhaust at five executions per attempt and preserve the unresolved dispatch',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[INFO]=(_r,n)=>{if(n>1)throw new Error('Synthetic unavailable read');return information(ORIGINAL);};
 await f.run();for(let n=0;n<8;n++){clock.advance(600000);await f.run();}
 assert.equal(writes(f).length,1);assert(attempts(f).every(a=>a.read_count<=5));assert.equal((await f.lifecycle()).title.state,'needs_attention');
 await f.rename('A newer blocked intent');clock.advance(600000);await f.run();assert.equal(writes(f).length,1,'new revision cannot bypass retained unresolved marker');
});

test('a failed unmarked read recovers through a later admitted pre-read and edit instead of wedging reconciliation',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[INFO]=(_r,n)=>{if(n===1)throw new Error('Synthetic first pre-read failure');return information(f.remoteTitle);};
 await f.run();assert.equal(writes(f).length,0);clock.advance(5000);assert.equal(await f.run(),'synced');assert.equal(writes(f).length,1);assert.equal((await f.lifecycle()).title.state,'synced');
});

test('five failed unmarked reads exhaust visibly without allocating a dispatch',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[INFO]=()=>{throw new Error('Synthetic unavailable pre-read');};for(let n=0;n<7;n++){await f.run();clock.advance(600000);}
 assert.equal(writes(f).length,0);assert.equal(f.calls.length,5);assert.equal(attempts(f)[0].read_count,5);assert.equal((await f.lifecycle()).title.state,'needs_attention');
});

test('a successful fifth pre-read cannot dispatch an edit without capacity for its required post-read',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[INFO]=(_r,n)=>{if(n<5)throw new Error('Synthetic unavailable earlier pre-read');return information(ORIGINAL);};
 for(let n=0;n<5;n++){await f.run();if(n<4)clock.advance(600000);}assert.equal(f.calls.length,5);assert.equal(writes(f).length,0);assert.equal(attempts(f)[0].read_count,5);assert.equal(attempts(f)[0].dispatch_count,0);
 clock.advance(600000);await f.run();assert.equal((await f.lifecycle()).title.state,'needs_attention');assert.equal(writes(f).length,0);
});

test('attachment missing-album evidence racing the pre-read fences title dispatch and later title work',async t=>{
 const f=await fixture(t),attachment=await import('../src/album_attachment_store.ts');const admitted=await f.associate('later-photo',(await f.binding()).binding_revision);const obligationId=admitted.obligation?.fgaAlbumObligationId??admitted.fgaAlbumObligationId;assert(obligationId);const claim=await attachment.claimAlbumAttachment(f.db,obligationId);assert(claim);
 f.hooks[INFO]=async()=>{assert.equal(await attachment.attentionAlbumAttachment(f.db,claim,'missing_album'),true);};await f.run();assert.equal(writes(f).length,0);assert.equal(attempts(f)[0].dispatch_count,0);assert.equal(f.db.raw.prepare('SELECT materialization_state FROM album_binding_remote_status WHERE binding_id=?').get(f.bindingId).materialization_state,'remote_album_missing_needs_attention');
 const clock=titleClock(f.db);clock.advance(600000);delete f.hooks[INFO];await f.run();assert.equal(writes(f).length,0);
});

test('archive during a marked write allows read-only reconciliation and never a retry',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.responses[EDIT]={stat:'ok'};f.hooks[EDIT]=()=>f.db.raw.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?").run(f.bindingId);
 assert.equal(await f.run(),'reconciliation_pending');assert.equal((await f.lifecycle()).title.state,'local_removed_reconciliation_pending');assert.equal(writes(f).length,1);assert.equal(f.calls.filter(c=>c.method===INFO).length,1);
 const row=attempts(f)[0];clock.set(Math.max(row.lease_expires_at_us,row.next_read_at_us));assert.equal(await f.run(),'local_removed');assert.equal((await f.lifecycle()).title.state,'local_removed');assert.equal(writes(f).length,1);assert.equal(f.calls.filter(c=>c.method===INFO).length,2);assert.equal(attempts(f)[0].attempt_id,row.attempt_id);
 clock.advance(600000);await f.run();assert.equal(writes(f).length,1);assert.equal((await f.binding()).flickr_photoset_id,SET);
});

test('shared fault/rate gate refusal sends no edit and bounded unavailable read is charged',async t=>{
 const f=await fixture(t);f.beforeRequest=method=>{if(method===EDIT)throw new Error('Synthetic longer rate gate');};await f.run();assert.equal(writes(f).length,0);assert.equal(attempts(f).reduce((n,a)=>n+a.dispatch_count,0),0);assert.equal(f.calls.length,1);
});

test('lost result and unknown-state commits retain a marked attempt; lease takeover performs reads before any write',async t=>{
 const f=await fixture(t),clock=titleClock(f.db);f.hooks[EDIT]=()=>{f.db.fault=0;throw new Error('Synthetic lost reply');};assert.equal(await f.run(),'reconciliation_pending');assert.equal(writes(f).length,1);assert.equal(attempts(f)[0].dispatch_count,1);
 f.db.fault=-1;delete f.hooks[EDIT];clock.advance(61000);const before=f.calls.length;await f.run();assert.equal(f.calls[before]?.method,INFO);assert.equal(writes(f).length,1);assert.equal((await f.binding()).flickr_photoset_id,SET);
});

for(const elapsed of [6999,7000])test(`outbound monotonic margin at ${10000-elapsed}ms is strict`,async t=>{
 const f=await fixture(t);let now=0;f.hooks[INFO]=(_r,n)=>{if(n===1)now=elapsed;};await f.run({monotonicMs:()=>now});assert.equal(writes(f).length,elapsed===6999?1:0);
});
for(const elapsed of [8999,9000])test(`final monotonic commit margin at ${10000-elapsed}ms is strict`,async t=>{
 const f=await fixture(t);let now=0;f.hooks[INFO]=(_r,n)=>{if(n===2)now=elapsed;};const result=await f.run({monotonicMs:()=>now});assert.equal(result,elapsed===8999?'synced':'reconciliation_pending');assert.equal(writes(f).length,1);
});

test('timed out read never continues into a late edit after its response arrives',async t=>{
 const f=await fixture(t);f.deadlineMs=1;f.hooks[INFO]=()=>new Promise(resolve=>setTimeout(resolve,15));await f.run();await new Promise(resolve=>setTimeout(resolve,25));assert.equal(writes(f).length,0);assert.equal(attempts(f).reduce((n,a)=>n+a.dispatch_count,0),0);
});
