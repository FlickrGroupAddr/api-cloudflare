import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {sqlStore} from './sql_store.mjs';
import {groupsRequest,refreshGroups,groupQuery,validateGroupPage,groupPageBody} from '../src/group_discovery.ts';
import {credentialDigest,NOW_US_SQL} from '../src/installations.ts';
import {createWorker} from '../src/worker.ts';

const CODE='0000-'.repeat(12)+'0000';
const secrets={FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'app',consumerSecret:'secret'})},
  FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'gen',token:'token',tokenSecret:'token-secret'})}};
async function fixture(){
 const db=sqlStore(),digest=await credentialDigest(CODE);
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('user')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
  db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
  db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
 ]);
 return {db,auth:{installationId:'install',credentialDigest:digest}};
}
const url=(q='page_size=100')=>new URL('https://example.test/api/v001/groups?'+q);
function body(total=3,page=1){return {stat:'ok',groups:{page,pages:Math.ceil(total/400),per_page:400,total,
 group:Array.from({length:Math.min(400,Math.max(0,total-(page-1)*400))},(_,i)=>({nsid:'g'+String((page-1)*400+i).padStart(5,'0'),name:'Group '+i,ignored:'do-not-store'}))}};}
const peer=async request=>Response.json(body(3,Number(new URL(request.url).searchParams.get('page'))));
const read=(f,q)=>groupsRequest(f.db,f.auth,url(q));
const age=f=>f.db.raw.exec(`UPDATE group_snapshots SET refreshed_at_us=${NOW_US_SQL}-901000000; UPDATE group_refresh SET admitted_at_us=${NOW_US_SQL}-61000000`);

test('closed query validation and paired continuation',()=>{
 for(const q of ['', 'page_size=0','page_size=101','page_size=01','page_size=1&page_size=2',
 'page_size=1&force=1','page_size=1&snapshot_revision=1','page_size=1&after_group_id=a',
 'page_size=1&snapshot_revision=9007199254740992&after_group_id=a','page_size=1&snapshot_revision=1&after_group_id=bad%20id'])
 assert.throws(()=>groupQuery(url(q)),/invalid_request/);
 assert.deepEqual(groupQuery(url('page_size=2&snapshot_revision=7&after_group_id=g')), {size:2,revision:7,after:'g'});
});
test('one admission, cron refresh, atomic snapshot and idempotent keyset reads',async()=>{
 const f=await fixture();
 try{
  const first=await read(f);assert.equal(first.status,202);assert.equal(first.headers.get('Retry-After'),'60');assert(!('groups' in await first.json()));
  const job=f.db.raw.prepare('SELECT job_id FROM group_refresh').get().job_id;
  for(let i=0;i<4;i++)assert.equal((await read(f)).status,202);
  assert.equal(f.db.raw.prepare('SELECT job_id FROM group_refresh').get().job_id,job);
  await refreshGroups(f.db,secrets,peer);
  const page=await (await read(f,'page_size=2')).json();assert.equal(page.snapshotStatus,'fresh');assert.equal(page.snapshotRevision,1);assert.equal(page.groups.length,2);assert.equal(page.nextAfterGroupId,'g00001');
  const query='page_size=2&snapshot_revision=1&after_group_id=g00001';
  const last=await (await read(f,query)).json();assert.equal(last.groups.length,1);assert.equal(last.nextAfterGroupId,null);
  assert.deepEqual(await (await read(f,query)).json(),last);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM group_refresh_rows').get().n,0);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM transaction_guards').get().n,0);
  assert(!JSON.stringify(f.db.raw.prepare('SELECT * FROM group_snapshot_rows').all()).includes('do-not-store'));
 }finally{f.db.raw.close();}
});
test('each upstream page is independently OAuth signed and complete before publication',async()=>{
 const f=await fixture();const nonces=[];
 try{
  await read(f);
  await refreshGroups(f.db,secrets,async request=>{
   const u=new URL(request.url);assert.equal(u.searchParams.get('method'),'flickr.groups.pools.getGroups');assert.equal(u.searchParams.get('per_page'),'400');assert.equal(request.redirect,'manual');
   const params=Object.fromEntries(request.headers.get('Authorization').slice(6).split(/,\s*/).map(x=>{const m=/^(\w+)="([^"]*)"$/.exec(x);return [m[1],decodeURIComponent(m[2])];}));
   nonces.push(params.oauth_nonce);
   const enc=x=>encodeURIComponent(x).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase());
   const pairs=[...u.searchParams,...Object.entries(params).filter(([k])=>k!=='oauth_signature')].map(([k,v])=>[enc(k),enc(v)]).sort((a,b)=>a[0].localeCompare(b[0]));
   const base='GET&'+enc(u.origin+u.pathname)+'&'+enc(pairs.map(x=>x.join('=')).join('&'));
   assert.equal(params.oauth_signature,createHmac('sha1','secret&token-secret').update(base).digest('base64'));
   assert.equal(f.db.raw.prepare('SELECT revision FROM group_snapshots').get().revision,0);
   return Response.json(body(401,Number(u.searchParams.get('page'))));
  });
  assert.equal(nonces.length,2);assert.notEqual(nonces[0],nonces[1]);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM group_snapshot_rows').get().n,401);
 }finally{f.db.raw.close();}
});
test('empty success differs from first refresh failure; cooldown prevents another attempt',async()=>{
 const f=await fixture();try{
  await read(f);await refreshGroups(f.db,secrets,async()=>Response.json({stat:'fail'}));
  const job=f.db.raw.prepare('SELECT job_id FROM group_refresh').get().job_id;
  assert.equal((await read(f)).status,503);assert.equal(f.db.raw.prepare('SELECT job_id FROM group_refresh').get().job_id,job);
  age(f);assert.equal((await read(f)).status,202);
  await refreshGroups(f.db,secrets,async()=>Response.json(body(0)));
  const out=await (await read(f)).json();assert.equal(out.snapshotStatus,'fresh');assert.deepEqual(out.groups,[]);
 }finally{f.db.raw.close();}
});
test('malformed, duplicate, oversized and drifting pages retain last good snapshot',async()=>{
 for(const mode of ['malformed','duplicate','bytes','drift','pages','rows']){
  const f=await fixture();try{
   await read(f);await refreshGroups(f.db,secrets,peer);age(f);
   assert.equal((await (await read(f)).json()).snapshotStatus,'stale_refreshing');
   await refreshGroups(f.db,secrets,async request=>{
    const page=Number(new URL(request.url).searchParams.get('page'));let b=body(401,page);
    if(mode==='malformed')b.groups.group[0].name=null;
    if(mode==='duplicate'&&page===2)b.groups.group[0].nsid='g00000';
    if(mode==='bytes')return Response.json({padding:'x'.repeat(2097152)});
    if(mode==='drift'&&page===2)b=body(402,2);
    if(mode==='pages')b.groups.pages=26;
    if(mode==='rows')b.groups.total=10001;
    return Response.json(b);
   });
   const out=await (await read(f)).json();assert.equal(out.snapshotStatus,'stale_refresh_failed',mode);assert.equal(out.snapshotRevision,1);assert.equal(out.groups.length,3);assert(out.refreshFailedAt);
  }finally{f.db.raw.close();}
 }
});
test('new revision rejects old continuation and relink never serves old grant snapshot',async()=>{
 const f=await fixture();try{
  await read(f);await refreshGroups(f.db,secrets,peer);age(f);await read(f);await refreshGroups(f.db,secrets,peer);
  assert.equal((await read(f,'page_size=1&snapshot_revision=1&after_group_id=g00000')).status,409);
  f.db.raw.exec("UPDATE flickr_links SET link_revision=link_revision+1 WHERE user_id='user'");
  assert.equal((await read(f)).status,409);
 }finally{f.db.raw.close();}
});
test('clock expiry/backward movement and authority change prevent publish',async()=>{
 for(const mode of ['expiry','backward','relink']){
  const f=await fixture();let clock=100;try{
   await read(f);
   await refreshGroups(f.db,secrets,async()=>{
    if(mode==='expiry')clock+=60000;if(mode==='backward')clock-=1;
    if(mode==='relink')f.db.raw.exec("UPDATE flickr_links SET link_revision=link_revision+1 WHERE user_id='user'");
    return Response.json(body());
   },()=>clock);
   assert.equal(f.db.raw.prepare('SELECT revision FROM group_snapshots').get().revision,0,mode);
   assert.equal(f.db.raw.prepare('SELECT state FROM group_refresh').get().state,'failed');
  }finally{f.db.raw.close();}
 }
});
test('revoked installation cannot refresh or read cache',async()=>{
 const f=await fixture();try{
  await read(f);
  f.db.raw.exec("BEGIN; UPDATE installation_credential_versions SET state='revoked' WHERE version_id='version'; UPDATE installations SET state='revoked',current_version_id=NULL,revision=2 WHERE installation_id='install'; COMMIT;");
  let calls=0;await refreshGroups(f.db,secrets,async()=>{calls++;return Response.json(body());});
  assert.equal(calls,0);assert.equal((await read(f)).status,409);
 }finally{f.db.raw.close();}
});
test('expired/crashed job is fenced from publication by a replacement',async()=>{
 const f=await fixture();let unblock,entered;
 const started=new Promise(r=>entered=r),wait=new Promise(r=>unblock=r);
 try{
  await read(f);
  const old=refreshGroups(f.db,secrets,async()=>{entered();await wait;return Response.json(body());});
  await started;
  f.db.raw.exec(`UPDATE group_refresh SET deadline_at_us=${NOW_US_SQL}-1,admitted_at_us=${NOW_US_SQL}-61000000`);
  await read(f);await refreshGroups(f.db,secrets,async()=>Response.json(body(1)));
  unblock();await old;
  const out=await (await read(f)).json();assert.equal(out.groups.length,1);assert.equal(out.snapshotRevision,1);assert.equal(out.snapshotStatus,'fresh');
 }finally{unblock?.();f.db.raw.close();}
});
test('production routing uses read flag independently of intake and never calls Flickr in GET',async()=>{
 const f=await fixture();try{
  const env={DB:f.db,...secrets,FGA_READ_ENABLED:'1',FGA_GROUPS_ENABLED:'1',FGA_INTAKE_ENABLED:'0',FGA_DISPATCH_ENABLED:'0'};
  const worker=createWorker(async()=>assert.fail('no upstream in API GET'));
  const request=token=>new Request(url(),{headers:token?{Authorization:'Bearer '+token}:{}});
  assert.equal((await worker.fetch(request(null),env)).status,401);
  assert.equal((await worker.fetch(request(CODE),env)).status,202);
  assert.equal((await worker.fetch(request(CODE),{...env,FGA_GROUPS_ENABLED:'0'})).status,503);
  assert.equal((await worker.fetch(new Request('https://example.test/api/v001/group-submission-batches',{method:'POST'}),env)).status,503);
 }finally{f.db.raw.close();}
});
test('exact page/row ceiling succeeds without truncation',async()=>{
 const f=await fixture();let calls=0;try{
  await read(f);await refreshGroups(f.db,secrets,async r=>{calls++;return Response.json(body(10000,Number(new URL(r.url).searchParams.get('page'))));});
  assert.equal(calls,25);assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM group_snapshot_rows').get().n,10000);
 }finally{f.db.raw.close();}
});
test('publication transaction failure preserves the previous complete rows and revision',async()=>{
 const f=await fixture();try{
  await read(f);await refreshGroups(f.db,secrets,peer);age(f);await read(f);
  const batch=f.db.batch;
  f.db.batch=async statements=>{f.db.fault=statements.some(s=>s.sql.includes('UPDATE group_snapshots SET revision'))?3:-1;try{return await batch(statements);}finally{f.db.fault=-1;}};
  await refreshGroups(f.db,secrets,async()=>Response.json(body(1)));
  const out=await (await read(f)).json();assert.equal(out.snapshotRevision,1);assert.equal(out.groups.length,3);assert.equal(out.snapshotStatus,'stale_refresh_failed');
 }finally{f.db.raw.close();}
});
test('duplicate scheduler invocation cannot run a second page walk',async()=>{
 const f=await fixture();let release,enter,calls=0;
 const entered=new Promise(r=>enter=r),wait=new Promise(r=>release=r);
 try{
  await read(f);const first=refreshGroups(f.db,secrets,async()=>{calls++;enter();await wait;return Response.json(body());});
  await entered;await refreshGroups(f.db,secrets,async()=>{calls++;return Response.json(body());});release();await first;assert.equal(calls,1);
 }finally{release?.();f.db.raw.close();}
});
test('fetch and body stalls are cancelled even if the dependency ignores its signal',async()=>{
 const req=new Request('https://www.flickr.com/services/rest/');
 for(const fetcher of [async()=>new Promise(()=>{}),async()=>new Response(new ReadableStream({pull(){return new Promise(()=>{});}}),{headers:{'Content-Type':'application/json'}})]){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),10);
  try{await assert.rejects(groupPageBody(req,fetcher,controller.signal),/deadline/);}finally{clearTimeout(timer);}
 }
 for(const response of [new Response('<html>'),new Response(null,{status:302}),new Response(new Uint8Array([255]),{headers:{'Content-Type':'application/json'}})])
  await assert.rejects(groupPageBody(req,async()=>response,new AbortController().signal));
});
test('scheduled production handler refreshes while intake is off and charges shared Flickr budget',async()=>{
 const f=await fixture();try{
  const env={DB:f.db,...secrets,FGA_READ_ENABLED:'1',FGA_GROUPS_ENABLED:'1',FGA_INTAKE_ENABLED:'0',FGA_DISPATCH_ENABLED:'0'};
  let calls=0;const worker=createWorker(async request=>{calls++;return peer(request);});
  const request=()=>new Request(url(),{headers:{Authorization:'Bearer '+CODE}});
  assert.equal((await worker.fetch(request(),env)).status,202);
  await worker.scheduled({},env);
  assert.equal(calls,1);assert.equal((await worker.fetch(request(),env)).status,200);
  assert.equal(f.db.raw.prepare('SELECT reserved_slots FROM flickr_rate_window').get().reserved_slots,1);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM attempt_dispatches').get().n,0);
 }finally{f.db.raw.close();}
});
