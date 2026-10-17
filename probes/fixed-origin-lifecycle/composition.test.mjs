import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { loadOfflineModule } from '../fixed-origin-isolation/offline_modules.mjs';
import { createSyntheticStore } from '../fixed-origin-isolation/offline_sqlite.mjs';
import { ORIGIN, PATHS } from '../fixed-origin-isolation/wrapper.mjs';
import { png } from '../fixed-origin-isolation/edge_png.mjs';
import { png as nodePng } from '../fixed-origin-isolation/fault_matrix.mjs';
import { COMPOSITION_CASES, createQualificationComposition } from './composition.mjs';
import { initializeQuota, createQuotaGuard, createReceiver } from './quota_receiver.mjs';

assert.equal(process.version, 'v24.22.0');
const fixture = process.env.FGA_OFFLINE_FIXTURE;
assert.ok(fixture, 'pinned private fixture required');
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
assert.equal(hash(join(fixture, 'captured.mjs')), 'f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d');
assert.equal(hash(join(fixture, 'candidate.mjs')), 'c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36');
const manifest = JSON.parse(readFileSync(join(fixture, 'manifest.json')));
assert.equal(manifest.candidateCommit, 'b599ca828d2a645b686aca0354d6c8ee2c2a0250');
for (const [file, digest] of Object.entries(manifest.candidateSourceFiles)) assert.equal(hash(join(fixture, 'candidate', file)), digest);
const run = 'a'.repeat(32), capability = 'b'.repeat(64), canary = 'c'.repeat(64);
const schema = readFileSync(new URL('./schema.sql', import.meta.url), 'utf8');
const counters = () => Object.fromEntries(['hostIo','globalFetch','dynamicImport','normal','synthetic','syntheticSql','application','grant','memoryFetch','pages','images'].map(key=>[key,0]));
const forbidden = new Proxy({}, { get() { throw Error('production_env_access'); }, ownKeys() { throw Error('production_env_access'); } });
function adapter(raw) { return { prepare(sql) { return { args: [], bind(...args) {this.args=args;return this;}, async first() {return raw.prepare(sql).get(...this.args)??null;}, async run() {return raw.prepare(sql).run(...this.args);} }; } }; }
async function setup({ afterHandler, quotaFailure = false } = {}) {
  const count=counters(); const captured=await loadOfflineModule(join(fixture,'captured.mjs'),count);
  const actual=await loadOfflineModule(join(fixture,'candidate.mjs'),count);
  const db=createSyntheticStore(join(fixture,'candidate/migrations'),count);
  const raw=new DatabaseSync(':memory:');raw.exec(schema);const quotaDb=adapter(raw);
  await initializeQuota({db:quotaDb,run,startsAt:1000}); let now=1000, forwarded=0;
  const clock=()=>now, guard=createQuotaGuard({db:quotaDb,run,clock});
  const receiver=createReceiver({guard,run,origin:ORIGIN,capability,canary});
  const candidate=afterHandler ? {createWorker(fetch) {const worker=actual.createWorker(fetch);return {async fetch(...args) {const response=await worker.fetch(...args);await afterHandler({setTime:v=>now=v,guard});return response;}};}} : actual;
  const options={captured,candidate,syntheticDb:db,quotaDb:quotaFailure?{prepare(){throw Error('storage_unavailable');}}:quotaDb,
    receiverBinding:{async fetch(req){forwarded++;return receiver.fetch(req);}},run,capability,startsAt:1000,expiresAt:601000,clock,counters:count};
  const worker=createQualificationComposition(options);
  return {worker,count,guard,options,setTime:v=>now=v,forwarded:()=>forwarded,close(){db.raw.close();raw.close();}};
}
const request=(scenario='ok',path=PATHS[0])=>new Request(ORIGIN+path,{headers:{Authorization:`FGA-Qualification ${capability}`,'X-FGA-Qualification-Run':run,'X-FGA-Qualification-Case':scenario}});

test('deployable module graph links without Node, Buffer, process or global fetch',async()=>{
  const context=vm.createContext({Request,Response,Headers,URL,TextEncoder,Uint8Array,DataView,Number,Object,Array,Date,atob});
  const modules=new Map();
  async function load(url){if(modules.has(url.href))return modules.get(url.href);assert.ok(url.href.startsWith(new URL('../',import.meta.url).href));const source=readFileSync(url,'utf8');assert.doesNotMatch(source,/\bBuffer\b|node:|from ['"]\.\/fault_matrix/);const mod=new vm.SourceTextModule(source,{context,identifier:url.href});modules.set(url.href,mod);await mod.link(specifier=>load(new URL(specifier,url)));return mod;}
  const mod=await load(new URL('./composition.mjs',import.meta.url));await mod.evaluate();assert.equal(typeof mod.namespace.createQualificationComposition,'function');
  for(const size of [undefined,262144,262145])assert.deepEqual(Buffer.from(png(size)),nodePng(size));
});

test('actual three routes, core and finite edge stimuli consume durable admission',async()=>{
  const s=await setup();try{
    for(const scenario of ['ok','missing-auth','invalid-auth'])for(const path of PATHS){const res=await s.worker.fetch(request(scenario,path),forbidden);assert.equal(res.status,scenario==='ok'?200:401);await res.arrayBuffer();}
    for(const scenario of COMPOSITION_CASES.filter(c=>c.startsWith('edge-'))){const res=await s.worker.fetch(request(scenario,PATHS[2]),forbidden);assert.equal(res.status,scenario.startsWith('edge-redirect-')?Number(scenario.slice(-3)):200);await res.arrayBuffer();}
    assert.equal((await s.guard.inspect()).fga,19);assert.equal(s.count.synthetic,19);assert.equal(s.count.hostIo+s.count.globalFetch+s.count.dynamicImport,0);
  }finally{s.close();}
});

test('ordinary dispatch preserves exact Request/env and never accesses quota/receiver',async()=>{
  const s=await setup();try{let expectedRequest,expectedEnv,calls=0;const worker=createQualificationComposition({...s.options,quotaDb:{prepare(){throw Error('quota_touched');}},receiverBinding:{fetch(){throw Error('receiver_touched');}},captured:{default:{fetch(req,env){assert.equal(req,expectedRequest);assert.equal(env,expectedEnv);calls++;return new Response(null,{status:204});}}}});
    for(const path of PATHS){expectedRequest=new Request(ORIGIN+path,{headers:{Authorization:'Bearer production'}});expectedEnv=forbidden;assert.equal((await worker.fetch(expectedRequest,expectedEnv)).status,204);}assert.equal(calls,3);assert.equal((await s.guard.inspect()).fga,0);
  }finally{s.close();}
});

test('invalid selectors and unsupported #39 cases do no candidate or durable work',async()=>{
  const s=await setup();try{for(const scenario of ['png','jpeg','stall','bad-query','unknown','fixed-origin-receive','fixed-origin-report'])assert.equal((await s.worker.fetch(request(scenario,PATHS[2]),forbidden)).status,404);
    for(const req of [request('ok',PATHS[0]+'?'),request('edge-wrong-media',PATHS[0]),new Request(ORIGIN+PATHS[0],{headers:{Authorization:'Bearer production','X-FGA-Qualification-Run':run}})])assert.equal((await s.worker.fetch(req,forbidden)).status,404);
    assert.equal(s.count.synthetic,0);assert.equal((await s.guard.inspect()).fga,0);
  }finally{s.close();}
});

test('96 durable actual route admissions; reconstruction and exhausted refusal precede handler',async()=>{
  const s=await setup();try{for(let n=0;n<96;n++)assert.equal((await s.worker.fetch(request('missing-auth',PATHS[n%3]),forbidden)).status,401);const before=s.count.synthetic;
    const restarted=createQualificationComposition(s.options);assert.equal((await restarted.fetch(request(),forbidden)).status,404);assert.equal(s.count.synthetic,before);assert.equal((await s.guard.inspect()).fga,96);
  }finally{s.close();}
});

test('constructor limits and durable outer start mismatch cannot run candidate work',async()=>{
  const s=await setup();try{
    assert.throws(()=>createQualificationComposition({...s.options,expiresAt:601001}),/invalid_scope/);
    assert.throws(()=>createQualificationComposition({...s.options,run:'a'.repeat(24)}),/invalid_scope/);
    const mismatched=createQualificationComposition({...s.options,startsAt:999,expiresAt:600999});
    assert.equal((await mismatched.fetch(request(),forbidden)).status,404);assert.equal(s.count.synthetic,0);
    assert.equal((await mismatched.fetch(new Request(`${ORIGIN}/report/${run}`,{headers:{Authorization:`FGA-Qualification ${capability}`}}),forbidden)).status,404);assert.equal(s.forwarded(),0);
    await s.guard.disable();assert.equal((await s.worker.fetch(request(),forbidden)).status,404);assert.equal(s.count.synthetic,0);
  }finally{s.close();}
});

test('inner/outer expiry, disabled/storage failure refuse before candidate; post-handler fences suppress',async()=>{
  for(const time of [999,601000,1201000]){const s=await setup();try{s.setTime(time);assert.equal((await s.worker.fetch(request(),forbidden)).status,404);assert.equal(s.count.synthetic,0);}finally{s.close();}}
  for(const action of ['inner','outer','disable']){const s=await setup({afterHandler:async({setTime,guard})=>action==='disable'?guard.disable():setTime(action==='inner'?601000:1201000)});try{assert.equal((await s.worker.fetch(request('edge-redirect-302',PATHS[2]),forbidden)).status,404);assert.equal(s.count.images,1);assert.equal((await s.guard.inspect()).fga,1);}finally{s.close();}}
  const s=await setup({quotaFailure:true});try{assert.equal((await s.worker.fetch(request(),forbidden)).status,404);assert.equal(s.count.synthetic,0);}finally{s.close();}
});

test('real receiver handles retained/stripped redirect auth, rejects production Bearer before forwarding, bounded report',async()=>{
  const s=await setup();try{
    const redirect=await s.worker.fetch(request('edge-redirect-302',PATHS[2]),forbidden);const location=redirect.headers.get('Location');
    for(const headers of [{Authorization:`FGA-Qualification ${capability}`,'X-FGA-Canary':canary},{}])assert.equal((await s.worker.fetch(new Request(location,{headers}),forbidden)).status,204);
    assert.equal(s.forwarded(),2);
    assert.equal((await s.worker.fetch(new Request(location,{headers:{Authorization:'Bearer production'}}),forbidden)).status,404);assert.equal(s.forwarded(),2);
    for(const url of [location+'?',location+'/','https://other.invalid'+new URL(location).pathname]){const req=new Request(url,{headers:{'X-FGA-Qualification-Run':run}});assert.equal((await s.worker.fetch(req,forbidden)).status,404);}
    const report=()=>new Request(`${ORIGIN}/report/${run}`,{headers:{Authorization:`FGA-Qualification ${capability}`}});
    const body=await(await s.worker.fetch(report(),forbidden)).json();assert.deepEqual(body,{receiverRequests:3,arrivals:2,authorizationPresent:true,canaryMatch:true});
    for(let n=3;n<16;n++)assert.equal((await s.worker.fetch(report(),forbidden)).status,200);
    assert.equal((await s.worker.fetch(report(),forbidden)).status,404);assert.equal((await s.guard.inspect()).receiver,16);
  }finally{s.close();}
});

function withSqlCompletionHook(s, predicate, hook, receiverBinding = s.options.receiverBinding) {
  const quotaDb = { prepare(sql) {
    const statement = s.options.quotaDb.prepare(sql);
    return { bind(...args) { statement.bind(...args); return this; },
      async first() { const value = await statement.first(); if (predicate(sql)) hook(); return value; },
      async run() { return statement.run(); } };
  } };
  return createQualificationComposition({ ...s.options, quotaDb, receiverBinding });
}

for (const finalPath of [`/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${run}/302`, `/report/${run}`]) {
  test(`same-origin ${finalPath.includes('/report/') ? 'report' : 'receive'} uses final FGA admission; exhaustion never forwards`,async()=>{
    const s=await setup();try{
      for(let n=0;n<95;n++)assert.equal((await s.worker.fetch(request('missing-auth'),forbidden)).status,401);
      const headers={Authorization:`FGA-Qualification ${capability}`};
      assert.equal((await s.worker.fetch(new Request(ORIGIN+finalPath,{headers}),forbidden)).status,finalPath.includes('/report/')?200:204);
      assert.equal((await s.guard.inspect()).fga,96);assert.equal((await s.guard.inspect()).receiver,1);assert.equal(s.forwarded(),1);
      for(const path of [`/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${run}/302`,`/report/${run}`])
        assert.equal((await s.worker.fetch(new Request(ORIGIN+path,{headers}),forbidden)).status,404);
      assert.equal(s.forwarded(),1);assert.equal((await s.guard.inspect()).receiver,1);assert.equal((await s.guard.inspect()).fga,96);
    }finally{s.close();}
  });
}

for(const branch of ['handler','receive','report'])for(const phase of ['scope','admission','publication'])for(const event of ['expiry','abort']) {
  test(`${branch}: ${event} during awaited ${phase} prevents effects/publication`,async()=>{
    const s=await setup();try{
      const controller=new AbortController();let boundRequest;
      const predicate=sql=>phase==='scope'?sql.includes('starts_at AS startsAt')
        :phase==='admission'?sql.startsWith('UPDATE qualification_run SET fga_count=')
        :sql.startsWith('SELECT singleton');
      const worker=withSqlCompletionHook(s,predicate,()=>event==='expiry'?s.setTime(601000):controller.abort(),{
        async fetch(req){boundRequest=req;return s.options.receiverBinding.fetch(req);}
      });
      const original=branch==='handler'?request('edge-redirect-302',PATHS[2])
        :new Request(ORIGIN+(branch==='report'?`/report/${run}`:`/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${run}/302`),
          {headers:branch==='report'?{Authorization:`FGA-Qualification ${capability}`}:{}});
      const response=await worker.fetch(new Request(original,{signal:controller.signal}),forbidden);
      assert.equal(response.status,404);assert.equal(response.headers.has('Location'),false);
      if(phase!=='publication'){
        assert.equal(s.count.synthetic,0);assert.equal(s.forwarded(),0);assert.equal((await s.guard.inspect()).receiver,0);
      }else if(branch==='handler')assert.equal(s.count.images,1);
      else {
        assert.equal(s.forwarded(),1);assert.equal((await s.guard.inspect()).receiver,1);
        if(event==='abort')assert.equal(boundRequest.signal.aborted,true);
      }
    }finally{s.close();}
  });
}
