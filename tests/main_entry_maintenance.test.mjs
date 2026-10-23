import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import { MainEntryMaintenance, MAIN_ENTRY_FAMILIES } from '../src/main_entry_maintenance.ts';
import { createMaintenanceWorker, createWorker, ROUTES } from '../src/worker.ts';
import { credentialDigest, NOW_US_SQL } from '../src/installations.ts';
import { beginLifecycle } from '../src/native_lifecycle.ts';
import { startLogin, finishLogin, digest, authenticateBrowser } from '../src/browser_sessions.ts';
import { startFlickrOAuth } from '../src/flickr_oauth.ts';
import { materializationFixture, contexts } from './album_materialization_worker_fixture.mjs';
import { thumbnailBody } from '../src/photo_thumbnails.ts';
import { sqlStore } from './sql_store.mjs';

const binding = { candidate: 'a'.repeat(64), lifecycle: 'synthetic-only', generation: '9007199254740993' };
const token = Array(13).fill('0000').join('-');
const request = path => new Request('https://flickrgroupaddr.com'+path, { headers: { Authorization: 'Bearer '+token } });
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;});return {promise,resolve,reject}; };
const tick = () => new Promise(resolve => setImmediate(resolve));

// Deliberately synthetic durable/independent ports. They qualify no runtime.
function fixture(db, options={}) {
  const retained = options.retained ?? { stopped: false, generation: binding.generation, leases: new Map(), effects: new Map(), returned: new Set() };
  const kinds = [], admissions = []; let assessments=0;
  const journal = {
    async admit(b, id, entry) {
      admissions.push(entry);
      if (retained.stopped) return null;
      const lease={...b,invocation:id,entry}; retained.leases.set(id,lease);
      await options.admit?.(lease); return lease;
    },
    async effect(lease,id,kind) {
      kinds.push(kind);
      await options.effect?.(lease,id,kind);
      if (lease.generation!==retained.generation || retained.returned.has(lease.invocation)) return false;
      retained.effects.set(id,{lease,kind}); return true;
    },
    async settled(lease,id,outcome) { await options.settled?.(lease,id,outcome); retained.effects.delete(id); },
    async returned(lease,outcome) { await options.returned?.(lease,outcome);retained.returned.add(lease.invocation); },
    async stop(b) { retained.stopped=true; await options.stop?.();return {...b,admission:'stopped',evidence:'b'.repeat(64)}; },
  };
  const observer = { async assess(b,stop,families) {
    assessments++;
    assert(retained.stopped);
    assert.equal(retained.effects.size,0);
    assert.equal(retained.returned.size,retained.leases.size);
    if (db) {
      // Independent synthetic handle; not the wrapped handler/journal handle.
      assert.deepEqual(db.raw.prepare("SELECT operation_id,phase FROM flickr_lifecycle_operations WHERE phase<>'complete'").all(),[]);
      assert.deepEqual(db.raw.prepare("SELECT transaction_id,phase FROM flickr_oauth_transactions WHERE phase<>'retired'").all(),[]);
      assert.deepEqual(db.raw.prepare('SELECT refresh_owner FROM google_jwks_cache WHERE refresh_owner IS NOT NULL').all(),[]);
      assert.deepEqual(db.raw.prepare("SELECT job_id,state FROM group_refresh WHERE state='running'").all(),[]);
    }
    await options.assess?.();
    return {...b,status:'complete-supported',evidence:'c'.repeat(64),families:[...families],
      admittedHandlers:'settled',externalResults:'settled',requiredDomainResults:'settled',oldCallbacks:'fenced',restartedInvocations:'accounted',...options.disposition};
  } };
  const bridge=new MainEntryMaintenance(binding,journal,observer,options.now);
  return {bridge,journal,observer,retained,kinds,admissions,assessments:()=>assessments};
}
async function database(t) {
  const db=sqlStore();t.after(()=>db.raw.close());
  // NEW in-memory source fixture only. Current accepted authentication writers
  // require the prospective integer schema; historical migrations stay intact.
  db.raw.exec('DROP TABLE auth_source_buckets;DROP TABLE status_read_buckets;');
  db.raw.exec(readFileSync(new URL('./integer_quota_fixture.sql',import.meta.url),'utf8'));
  return db;
}
async function install(db) {
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','user','lrc_plugin','active',7,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)").bind(await credentialDigest(token)),
  ]);
}
async function lifecycle(t) {
  const db=await database(t);await install(db);
  await db.batch([
    db.prepare("INSERT INTO admin_principals(user_id,google_issuer,google_sub) VALUES('user','https://accounts.google.com','subject')"),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('user','old',1,'owner','write',NULL)"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
    db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)"),
  ]);
  const op=await beginLifecycle(db,'user',1,'retire');let grant='';
  const ids=['1','2','3','4','5'].map(x=>x.repeat(32));
  const env={DB:db,FGA_READ_ENABLED:'1',FGA_ADMIN_ENABLED:'1',GOOGLE_OWNER_SUB:'subject',GOOGLE_CLIENT_ID:'synthetic-client',
    CF_ACCOUNT_ID:'a'.repeat(32),CF_SECRET_STORE_ID:'b'.repeat(32),CF_GRANT_SLOT_ID:'c'.repeat(32),CF_OAUTH_SLOT_IDS:JSON.stringify(ids),
    NATIVE_WRITER_TOKEN:{get:async()=>'synthetic-token'},FLICKR_GRANT:{get:async()=>grant},
    FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'synthetic',consumerSecret:'synthetic'})}};
  for(let i=0;i<5;i++)env['FLICKR_TEMP_'+i]={get:async()=>''};
  let patches=0; const onPatch=deferred(),release=deferred();
  const fetcher=async req=>{
    if(new URL(req.url).hostname==='www.googleapis.com')return Response.json({keys:[]},{headers:{'Cache-Control':'max-age=3600'}});
    assert.equal(req.method,'PATCH'); patches++;grant=JSON.parse(await req.text()).value;onPatch.resolve();await release.promise;
    return new Response('{}');
  };
  return {db,env,op,fetcher,onPatch,release,patches:()=>patches};
}

test('required constructor refuses absent ports and noncanonical exact generations',()=>{
  for(const value of [undefined,null,{}])assert.throws(()=>createMaintenanceWorker(value),/main_entry_unavailable/);
  for(const generation of ['0','01','9223372036854775808',9007199254740993])assert.throws(()=>new MainEntryMaintenance({...binding,generation},{},{}));
  assert.throws(()=>new MainEntryMaintenance(binding,null,null));
});

test('ordinary default route remains ordinary; maintenance route uses actual auth and lookup',async t=>{
  const db=await database(t);await install(db);const f=fixture(db);
  for(const worker of [createWorker(),createMaintenanceWorker(f.bridge)]) {
    const response=await worker.fetch(request('/api/v001/installations/current'),{DB:db,FGA_READ_ENABLED:'1'});
    assert.equal(response.status,200);assert.deepEqual(await response.json(),{schemaVersion:1,installationId:'installation',installationRevision:7,installationState:'active',presentedCredentialState:'current'});
    for(const [key,value] of [['Cache-Control','no-store'],['X-Content-Type-Options','nosniff'],['Referrer-Policy','no-referrer']])assert.equal(response.headers.get(key),value);
  }
  assert(f.kinds.includes('d1'));const receipt=await f.bridge.stop(1000);assert.equal(receipt.generation,binding.generation);
  assert.deepEqual(receipt.families,MAIN_ENTRY_FAMILIES);
});

test('stopped main entry blocks every registry family, pre-registry admin and schedule before any capability',async()=>{
  const f=fixture();await f.bridge.stop(1000);let effects=0;
  const env=new Proxy({FGA_READ_ENABLED:'1',FGA_DISPATCH_ENABLED:'0'},{get(){effects++;assert.fail('closed entry touched env');}});
  const worker=createMaintenanceWorker(f.bridge,async()=>assert.fail('provider'));
  for(const route of ROUTES){const path=route.pathPattern.replace(/\{[^}]+\}/g,'synthetic');assert.equal((await worker.fetch(new Request('https://flickrgroupaddr.com'+path,{method:route.method}),env)).status,503);}
  for(const path of ['/admin/login','/admin/google-login','/admin/flickr-oauth/callback','/admin/','/admin/app.mjs','/unknown'])assert.equal((await worker.fetch(request(path),env)).status,503);
  await assert.rejects(worker.scheduled({},env),/main_entry_unavailable/);assert.equal(effects,0);
});

test('stop waits actual admitted current-lookup completion and blocks new requests',async t=>{
  const db=await database(t);await install(db);const entered=deferred(),release=deferred();
  const f=fixture(db,{effect:async(_lease,_id,kind)=>{if(kind==='d1'){entered.resolve();await release.promise;}}});
  const worker=createMaintenanceWorker(f.bridge),env={DB:db,FGA_READ_ENABLED:'1'};
  const old=worker.fetch(request('/api/v001/installations/current'),env);await entered.promise;
  let stopped=false;const close=f.bridge.stop(1000).then(value=>{stopped=true;return value;});await tick();assert(!stopped);
  assert.equal((await worker.fetch(request('/api/v001/installations/current'),env)).status,503);
  release.resolve();assert.equal((await old).status,200);await close;assert(stopped);
});

test('whole schedule performs real cleanup with dispatch disabled, and a restarted schedule is refused',async t=>{
  const db=await database(t);const f=fixture(db),worker=createMaintenanceWorker(f.bridge);
  await worker.scheduled({},{DB:db,FGA_READ_ENABLED:'1',FGA_DISPATCH_ENABLED:'0'});
  assert(f.kinds.includes('d1'));await f.bridge.stop(1000);
  const restarted=fixture(db,{retained:f.retained});
  await assert.rejects(createMaintenanceWorker(restarted.bridge).scheduled({},{DB:db,FGA_READ_ENABLED:'1'}));
});

test('native PATCH result and existing lifecycle result transactions finish BEFORE admission disposition',async t=>{
  const n=await lifecycle(t),f=fixture(n.db),worker=createMaintenanceWorker(f.bridge,n.fetcher);
  const running=worker.scheduled({},n.env);await n.onPatch.promise;
  assert.equal(n.db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'dispatched');
  let stopped=false;const close=f.bridge.stop(1000).then(x=>{stopped=true;return x;});await tick();assert(!stopped);
  n.release.resolve();await running;await close;
  assert.equal(n.patches(),1);assert.equal(n.db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'complete');
  assert.equal(n.db.raw.prepare('SELECT state,local_state FROM flickr_connection_state').get().local_state,'retired');
  assert(f.kinds.includes('provider-body'));assert(f.kinds.includes('secret-read'));
  assert.equal(n.db.raw.prepare("SELECT count(*) n FROM audit_events WHERE action='flickr.payload_retired'").get().n,1);
});

test('pending native result times out irreversibly without aborting mandatory domain settlement',async t=>{
  const n=await lifecycle(t),f=fixture(n.db),worker=createMaintenanceWorker(f.bridge,n.fetcher);
  const running=worker.scheduled({},n.env);await n.onPatch.promise;await assert.rejects(f.bridge.stop(10));
  assert.equal(n.db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'dispatched');
  n.release.resolve();await running;
  assert.equal(n.db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'complete');
  await assert.rejects(f.bridge.stop(1000));assert.equal((await worker.fetch(request('/api/v001/installations/current'),n.env)).status,503);
});

test('caught failed lifecycle settlement remains pending and independent assessment refuses',async t=>{
  const n=await lifecycle(t),f=fixture(n.db),worker=createMaintenanceWorker(f.bridge,n.fetcher);
  const batch=n.db.batch.bind(n.db);
  n.db.batch=async statements=>{if(statements.some(s=>s.sql.includes("SET phase='complete'")))throw new Error('synthetic mandatory-result failure');return batch(statements);};
  const running=worker.scheduled({},n.env);await n.onPatch.promise;n.release.resolve();await running;
  assert.equal(n.db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'dispatched');
  await assert.rejects(f.bridge.stop(1000));assert.equal(f.assessments(),1);
});

test('response body still pending is not a settled provider result, late result stays owned',async()=>{
  const f=fixture(),header=deferred(),release=deferred();let late;
  await f.bridge.run('fetch',async scope=>{
    const fetcher=scope.fetcher(async()=>{header.resolve();return new Response(new ReadableStream({async pull(controller){await release.promise;controller.enqueue(new Uint8Array([1]));controller.close();}}));});
    const response=await fetcher(new Request('https://synthetic.invalid'));
    late=response.arrayBuffer(); // Model an existing handler's deadline race.
    await header.promise;
  });
  await assert.rejects(f.bridge.stop(1000));release.resolve();await late;await tick();
  await assert.rejects(f.bridge.stop(1000));
});

test('returned callback authority cannot revive after simulated generation advancement',async()=>{
  const f=fixture();let db;
  await f.bridge.run('fetch',async scope=>{db=scope.database({prepare(){return {bind(){return this;},async run(){assert.fail('old callback mutated');}};}});});
  await f.bridge.stop(1000);f.retained.generation='9007199254740995';f.retained.stopped=false;
  assert.throws(()=>db.prepare('UPDATE anything').run(),/main_entry_unavailable/);
});

test('orphaned old callback retains fixed settlement only under original durable lease; new generation refuses it',async()=>{
  const f=fixture(),release=deferred();let callback,mutated=false;
  await f.bridge.run('fetch',async scope=>{
    const db=scope.database({prepare(){return {async run(){mutated=true;}};}});
    callback=scope.effect('repair-reader',async()=>{await release.promise;await db.prepare('fixed-result').run();});
    void callback.catch(()=>{});
  });
  await assert.rejects(f.bridge.stop(1000));f.retained.generation='9007199254740995';release.resolve();
  await assert.rejects(callback);assert(!mutated);
});

test('throwing/pending journal settlement and incomplete independent coverage cannot authorize closure',async()=>{
  for(const options of [
    {settled:async()=>{throw new Error('unknown journal receipt');}},
    {disposition:{requiredDomainResults:'unknown'}},
    {disposition:{families:MAIN_ENTRY_FAMILIES.slice(1)}},
    {disposition:{generation:'1'}},
    {assess:async()=>{throw new Error('unreadable pending state');}},
  ]){
    const f=fixture(undefined,options);await f.bridge.run('fetch',scope=>scope.effect('d1',async()=>1));await assert.rejects(f.bridge.stop(100));
  }
  const waiting=deferred(),f=fixture(undefined,{returned:()=>waiting.promise});
  const running=f.bridge.run('scheduled',async()=>1);await assert.rejects(f.bridge.stop(10));waiting.resolve();await running;
  await assert.rejects(f.bridge.stop(100));
});

test('admit/stop race remains included; missing durable state on restart is not a local drain proof',async()=>{
  const entered=deferred(),release=deferred(),f=fixture(undefined,{admit:async()=>{entered.resolve();await release.promise;}});
  let ran=false;const running=f.bridge.run('scheduled',async()=>{ran=true;});await entered.promise;
  const close=f.bridge.stop(1000);release.resolve();await running;await close;assert(ran);
  const restarted=fixture(undefined,{retained:{stopped:false,generation:binding.generation,leases:new Map([['unknown-old',{}]]),effects:new Map(),returned:new Set()}});
  await assert.rejects(restarted.bridge.stop(100));
});

test('injected repair factory and method share admitted effect; old returned readers cannot run',async()=>{
  const f=fixture();let factory=0,method=0,reader;
  await f.bridge.run('fetch',async scope=>{
    reader=scope.repair({reader(){factory++;return {async discover(){method++;return {};},async prove(){return {};}};}}).reader({});
    await reader.discover(1,20);
  });
  await f.bridge.stop(1000);assert.throws(()=>reader.discover(1,20));assert.equal(factory,1);assert.equal(method,1);
});

test('late or backwards monotonic drain readings refuse even when timer delivery is delayed',async()=>{
  for(const readings of [[0,0,1,2,101],[10,9]]){
    let n=0;const f=fixture(undefined,{now:()=>readings[Math.min(n++,readings.length-1)]});
    await assert.rejects(f.bridge.stop(100));await assert.rejects(f.bridge.stop(100));
  }
});

test('unexpected handler throw is retained as unresolved even if its caller catches it',async()=>{
  const f=fixture();await assert.rejects(f.bridge.run('fetch',async()=>{throw new Error('unexpected handler failure');}));
  await assert.rejects(f.bridge.stop(100));assert.equal(f.assessments(),0);
});

test('pre-registry admin login performs actual bounded authentication admission under the bridge',async t=>{
  const db=await database(t),f=fixture(db),worker=createMaintenanceWorker(f.bridge);
  const req=new Request('https://flickrgroupaddr.com/admin/login',{headers:{'CF-Connecting-IP':'192.0.2.1'}});
  Object.defineProperty(req,'cf',{value:{}});
  const env={DB:db,FGA_ADMIN_ENABLED:'1',GOOGLE_CLIENT_ID:'synthetic',GOOGLE_OWNER_SUB:'subject',AUTH_LIMITER_KEY:{get:async()=>'synthetic-limiter-key-32-bytes-minimum'}};
  const response=await worker.fetch(req,env);assert.equal(response.status,200);
  assert.equal(db.raw.prepare('SELECT count(*) n FROM google_login_transactions').get().n,1);
  assert(f.kinds.includes('secret-read'));assert(f.kinds.includes('d1'));await f.bridge.stop(1000);
});

test('actual main album create-repair admin route tracks the injected factory, reader and its pending return',async t=>{
  const a=await materializationFixture(t);
  a.responses['flickr.photosets.create']=new Response('synthetic lost acknowledgement',{status:502});
  a.responses['flickr.photos.getAllContexts']=contexts(['preexisting']);assert.equal(await a.run(),'create_outcome_unknown');
  const adminToken='A'.repeat(43);
  a.db.raw.prepare("INSERT INTO admin_principals(user_id,google_issuer,google_sub) VALUES('user','https://accounts.google.com','subject')").run();
  a.db.raw.prepare(`INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id) VALUES('repair-session',?,'user',?,${NOW_US_SQL},${NOW_US_SQL},${NOW_US_SQL}+86400000000,${NOW_US_SQL},'correlation')`).run(digest(adminToken),'c'.repeat(43));
  const entered=deferred(),release=deferred(),f=fixture(a.db);let factories=0;
  const worker=createMaintenanceWorker(f.bridge,async()=>assert.fail('unexpected provider'),{reader(){factories++;return {async discover(){entered.resolve();await release.promise;throw new Error('synthetic unknown reader result');},async prove(){assert.fail('unexpected proof');}};}});
  const running=worker.fetch(new Request(`https://flickrgroupaddr.com/api/v001/admin/album-bindings/${a.binding}/create-repair-candidates?page=1&page_size=20`,{headers:{Cookie:'__Host-fga_admin='+adminToken}}),{DB:a.db,FGA_ADMIN_ENABLED:'1',GOOGLE_CLIENT_ID:'synthetic',GOOGLE_OWNER_SUB:'subject',FGA_ALBUM_CREATE_REPAIR_ENABLED:'1'});
  // The actual route authenticates before it obtains the injected reader.
  const begun=await Promise.race([entered.promise.then(()=>true),running.then(async response=>{assert.equal(response.status,200,await response.text());return false;})]);
  assert(begun);let stopped=false;const close=f.bridge.stop(1000).then(x=>{stopped=true;return x;});await tick();assert(!stopped);
  release.resolve();assert.equal((await running).status,503);await close;assert.equal(factories,1);assert(f.kinds.includes('repair-reader'));
});

test('actual OAuth callback replaces native grant once and schedule retires its real temporary lifecycle',async t=>{
  const db=await database(t),login=await startLogin(db);
  const cookie=await finishLogin(db,{stateDigest:digest(login.state),nonceDigest:digest(login.nonce),googleSub:'subject',ownerSub:'subject'});
  const session=await authenticateBrowser(new Request('https://flickrgroupaddr.com/',{headers:{Cookie:cookie.split(';')[0]}}),db,'subject');
  db.raw.prepare("INSERT INTO flickr_links VALUES(?,'owner',1,'paused')").run(session.userId);
  db.raw.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES(?,'unlinked','absent')").run(session.userId);
  db.raw.prepare("INSERT INTO flickr_write_gates VALUES('user',?,0,1),('deployment','*',0,1)").run(session.userId);
  const ids=['1','2','3','4','5'].map(x=>x.repeat(32)),values=Array(5).fill('');let grant='',callback;
  const grantId='c'.repeat(32),onPatch=deferred(),release=deferred();let patches=0;
  const secrets={FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'app',consumerSecret:'secret'})},FLICKR_GRANT:{get:async()=>grant}};
  const fetcher=async req=>{
    const url=new URL(req.url);
    if(url.pathname.endsWith('request_token')){
      const raw=/oauth_callback="([^"]*)"/.exec(req.headers.get('Authorization'))[1];callback=new URL(decodeURIComponent(raw));
      return new Response('oauth_callback_confirmed=true&oauth_token=temp&oauth_token_secret=temp-secret');
    }
    if(url.pathname.endsWith('access_token'))return new Response('oauth_token=active-token&oauth_token_secret=active-secret');
    if(req.method==='PATCH'){
      patches++;const value=JSON.parse(await req.text()).value;
      if(url.pathname.endsWith(grantId)){grant=value;onPatch.resolve();await release.promise;}else values[ids.findIndex(id=>url.pathname.endsWith(id))]=value;
      return new Response('{}');
    }
    if(url.hostname==='www.googleapis.com')return Response.json({keys:[]},{headers:{'Cache-Control':'max-age=3600'}});
    assert.equal(url.searchParams.get('method'),'flickr.auth.oauth.checkToken');
    return Response.json({stat:'ok',oauth:{token:{_content:'active-token'},perms:{_content:'write'},user:{nsid:'owner'}}});
  };
  await startFlickrOAuth(db,session,1,secrets,{read:async i=>values[i],writer:i=>({replace:async value=>{values[i]=value;}})},fetcher);
  const env={DB:db,...secrets,FGA_ADMIN_ENABLED:'1',GOOGLE_CLIENT_ID:'synthetic',GOOGLE_OWNER_SUB:'subject',AUTH_LIMITER_KEY:{get:async()=>'synthetic-limiter-key-32-bytes-minimum'},NATIVE_WRITER_TOKEN:{get:async()=>'synthetic-token'},CF_ACCOUNT_ID:'a'.repeat(32),CF_SECRET_STORE_ID:'b'.repeat(32),CF_GRANT_SLOT_ID:grantId,CF_OAUTH_SLOT_IDS:JSON.stringify(ids)};
  for(let i=0;i<5;i++)env['FLICKR_TEMP_'+i]={get:async()=>values[i]};
  const f=fixture(db),worker=createMaintenanceWorker(f.bridge,fetcher);
  callback.searchParams.set('oauth_token','temp');callback.searchParams.set('oauth_verifier','verifier');
  const req=new Request(callback,{headers:{'CF-Connecting-IP':'192.0.2.1'}});Object.defineProperty(req,'cf',{value:{}});
  const running=worker.fetch(req,env);
  await Promise.race([onPatch.promise,running.then(async response=>assert.fail('OAuth ended before PATCH: '+response.status+' '+await response.text()))]);
  assert.equal(db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'dispatched');
  release.resolve();assert.equal((await running).status,200);
  assert.equal(db.raw.prepare('SELECT phase FROM flickr_lifecycle_operations').get().phase,'complete');
  assert.equal(db.raw.prepare('SELECT phase FROM flickr_oauth_transactions').get().phase,'consumed');
  await worker.scheduled({},env);
  assert.equal(db.raw.prepare('SELECT phase FROM flickr_oauth_transactions').get().phase,'retired');
  await f.bridge.stop(1000);assert.equal(patches,2);
});

for(const rejection of [false,true])test(`actual thumbnail helper reader EOF cannot settle ${rejection?'rejected':'pending'} underlying cancellation`,async()=>{
  const f=fixture(),release=deferred(),readerStarted=deferred(),control=new AbortController();
  let cancelStarted=false,cancelFinished=false;
  await f.bridge.run('fetch',async scope=>{
    const fetcher=scope.fetcher(async()=>new Response(new ReadableStream({
      pull(){readerStarted.resolve();},
      async cancel(){cancelStarted=true;await release.promise;cancelFinished=true;},
    }),{headers:{'Content-Type':'image/jpeg'}}));
    const operation=thumbnailBody('https://live.staticflickr.com/1/123_secret_q.jpg',fetcher,control.signal,'123');
    // Attach rejection handling before abort; the actual helper cancels twice
    // without awaiting either cancellation when the pending read becomes EOF.
    const failed=assert.rejects(operation,/cancelled/);
    await readerStarted.promise;await tick();control.abort();await failed;
    await tick();assert(cancelStarted);assert(!cancelFinished);
    if(rejection){release.reject(new Error('synthetic underlying cancellation failure'));await tick();}
  });
  assert(f.kinds.includes('provider-cancel'));
  await assert.rejects(f.bridge.stop(100));assert.equal(f.assessments(),0);
  if(!rejection){release.resolve();await tick();assert(cancelFinished);}
  // Neither a late completion nor a swallowed rejection revives this drain.
  await assert.rejects(f.bridge.stop(100));
});

test('actual thumbnail invalid-response body cancellation is a separately retained obligation',async()=>{
  const f=fixture(),release=deferred();let cancelStarted=false,cancelFinished=false;
  await f.bridge.run('fetch',async scope=>{
    const fetcher=scope.fetcher(async()=>new Response(new ReadableStream({
      async cancel(){cancelStarted=true;await release.promise;cancelFinished=true;},
    }),{headers:{'Content-Type':'text/plain'}}));
    await assert.rejects(thumbnailBody('https://live.staticflickr.com/1/123_secret_q.jpg',fetcher,new AbortController().signal,'123'),/upstream/);
    await tick();assert(cancelStarted);assert(!cancelFinished);
  });
  assert(f.kinds.includes('provider-cancel'));await assert.rejects(f.bridge.stop(100));
  release.resolve();await tick();assert(cancelFinished);assert.equal(f.assessments(),0);
});

test('fully settled actual thumbnail cancellation preserves synchronous reader disposal without a releaseLock race',async()=>{
  const f=fixture(),readerStarted=deferred(),control=new AbortController();let cancellations=0;
  await f.bridge.run('fetch',async scope=>{
    const fetcher=scope.fetcher(async()=>new Response(new ReadableStream({
      pull(){readerStarted.resolve();},cancel(){cancellations++;},
    }),{headers:{'Content-Type':'image/jpeg'}}));
    const failed=assert.rejects(thumbnailBody('https://live.staticflickr.com/1/123_secret_q.jpg',fetcher,control.signal,'123'),/cancelled/);
    await readerStarted.promise;await tick();control.abort();await failed;await tick();
  });
  assert.equal(cancellations,1);assert(f.kinds.filter(kind=>kind==='provider-cancel').length>=2);
  await f.bridge.stop(1000);assert.equal(f.assessments(),1);
});
