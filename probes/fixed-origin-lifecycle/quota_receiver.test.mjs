import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Worker } from 'node:worker_threads';
import { CASES, LIMITS, initializeQuota, createQuotaGuard, createReceiver } from './quota_receiver.mjs';

const run = 'a'.repeat(32), capability = 'b'.repeat(64), canary = 'c'.repeat(64);
const origin = `https://fga-fixed-origin-recv-${run}.fixture.workers.dev`;
const receivePath = `/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${run}/302`;
const schema = readFileSync(new URL('./schema.sql', import.meta.url), 'utf8');
function adapter(raw) {
  return { prepare(sql) { return { args: [], bind(...args) { this.args=args; return this; },
    async first() { return raw.prepare(sql).get(...this.args) ?? null; },
    async run() { return raw.prepare(sql).run(...this.args); } }; } };
}
async function setup(file = ':memory:') {
  const raw = new DatabaseSync(file); raw.exec(schema);
  const db = adapter(raw); await initializeQuota({db,run,startsAt:100});
  let time = 100; const guard = createQuotaGuard({db,run,clock:()=>time});
  return {raw,db,guard,setTime(value) {time=value;}};
}
function receiver(guard) { return createReceiver({guard,run,origin,capability,canary}); }
function request(path='receive',headers={}) { return new Request(origin + (path === 'receive' ? receivePath : `/report/${run}`), {headers}); }

test('exact immutable proposal limits, singleton cannot reset, closed selectors',async()=>{
  const {raw,db,guard}=await setup();
  assert.deepEqual(LIMITS,{fga:96,receiver:16,lifetimeMs:1200000});
  await assert.rejects(initializeQuota({db,run,startsAt:101}));
  assert.throws(()=>createQuotaGuard({db,run:'a'.repeat(24)}));
  assert.throws(()=>raw.exec('UPDATE qualification_run SET expires_at=expires_at+1'));
  assert.throws(()=>raw.exec('DELETE FROM qualification_run'));
  for (const args of [['fga','unknown'],['other','png'],['receiver','unknown'],['receiver','receive',{authorizationPresent:true,canaryMatch:true,raw:'secret'}]])
    assert.equal(await guard.admit(...args),false);
  assert.equal((await guard.inspect()).fga,0); raw.close();
});

test('FGA quota durable across reconstructed guards and independent receiver budget',async()=>{
  const {raw,db,guard}=await setup();
  for(let n=0;n<96;n++) assert.equal(await createQuotaGuard({db,run,clock:()=>100}).admit('fga',CASES[n%CASES.length]),true);
  assert.equal(await guard.admit('fga','png'),false);
  assert.equal(await guard.admit('receiver','report'),true);
  assert.equal((await guard.inspect()).fga,96);
  assert.throws(()=>raw.exec('UPDATE qualification_run SET fga_count=0')); raw.close();
});

test('ordinary replacement cannot reset exhausted or disabled scope with default SQLite trigger behavior',async()=>{
  const {raw,guard}=await setup();
  raw.exec('PRAGMA recursive_triggers=OFF');
  assert.equal(raw.prepare('PRAGMA recursive_triggers').get().recursive_triggers,0);
  for(let n=0;n<96;n++) assert.equal(await guard.admit('fga','png'),true);
  const replace=raw.prepare('INSERT OR REPLACE INTO qualification_run(singleton,run,starts_at,expires_at) VALUES(1,?,?,?)');
  for(const scope of [[run,100,1200100],[run,200,1200200],['d'.repeat(32),100,1200100]])
    assert.throws(()=>replace.run(...scope),/qualification_no_replace/);
  assert.equal((await guard.inspect()).fga,96);
  assert.equal(await guard.admit('fga','png'),false);
  await guard.disable();
  assert.throws(()=>replace.run(run,100,1200100),/qualification_no_replace/);
  const receipt=await guard.inspect();
  assert.equal(receipt.enabled,false);assert.equal(receipt.fga,96);assert.equal(receipt.expiresAt,1200100);
  assert.equal(await guard.canPublish(),false);raw.close();
});

test('inclusive start exclusive 20min expiry, invalid clocks, disable fence publication',async()=>{
  const {raw,guard,setTime}=await setup();
  for(const time of [99,1200100,NaN,Infinity,-1,1.5]) { setTime(time); assert.equal(await guard.admit('fga','png'),false); assert.equal(await guard.canPublish(),false); }
  setTime(100); assert.equal(await guard.admit('fga','png'),true);
  setTime(1200099); assert.equal(await guard.canPublish(),true);
  setTime(1200100); assert.equal(await guard.canPublish(),false);
  setTime(100); assert.equal(await guard.disable(),true); assert.equal(await guard.canPublish(),false);
  assert.equal(await guard.admit('receiver','report'),false);
  assert.equal((await guard.inspect()).enabled,false);
  assert.throws(()=>raw.exec('UPDATE qualification_run SET enabled=1')); raw.close();
});

test('receiver exact URL/method/report gate rejects before counter or body work',async()=>{
  const {raw,guard}=await setup(); const worker=receiver(guard);
  const invalid=[new Request(`${origin}${receivePath}?`),new Request(`${origin}${receivePath}?x=1`),
    new Request(`${origin}${receivePath}/`),new Request(`${origin}${receivePath}`,{method:'POST',body:'DO_NOT_READ'}),
    request('report'),request('report',{Authorization:'Bearer '+capability}),new Request(`https://other.invalid${receivePath}`),
    new Request(`${origin}/receive/${run}`),new Request(`${origin}${receivePath.replace('/302','/304')}`)];
  for(const req of invalid) assert.equal((await worker.fetch(req)).status,404);
  assert.equal((await guard.inspect()).receiver,0); raw.close();
});

test('receiver persists only aggregate counts and boolean observations; report shares quota',async()=>{
  const {raw,guard}=await setup(); const worker=receiver(guard);
  assert.equal((await worker.fetch(request('receive',{Authorization:'SECRET_NOT_STORED','X-FGA-Canary':canary,'X-Unrelated':'SECRET_NOT_STORED'}))).status,204);
  const response=await worker.fetch(request('report',{Authorization:'FGA-Qualification '+capability}));
  assert.deepEqual(await response.json(),{receiverRequests:2,arrivals:1,authorizationPresent:true,canaryMatch:true});
  assert.equal(response.headers.get('Cache-Control'),'no-store');
  for(let n=2;n<16;n++) assert.equal((await worker.fetch(request())).status,204);
  assert.equal((await worker.fetch(request('report',{Authorization:'FGA-Qualification '+capability}))).status,404);
  const fields=raw.prepare('PRAGMA table_info(qualification_run)').all().map(row=>row.name);
  assert.deepEqual(fields,['singleton','run','starts_at','expires_at','enabled','fga_count','receiver_count','arrivals','authorization_present','canary_match']);
  assert.equal(JSON.stringify(raw.prepare('SELECT * FROM qualification_run').get()).includes('SECRET_NOT_STORED'),false); raw.close();
});

test('all five exact redirect receive paths observe stripped headers and reject production Bearer before storage',async()=>{
  let accesses=0;
  const inaccessible={async admit(){accesses++;throw Error('unexpected_storage_access');},async inspect(){accesses++;},async canPublish(){accesses++;}};
  for(const value of ['Bearer real-looking-production-token','bearer real-looking-production-token','BEARER','Bearer\tproduction']) {
    assert.equal((await receiver(inaccessible).fetch(request('receive',{Authorization:value}))).status,404);
  }
  assert.equal(accesses,0);
  const {raw,guard}=await setup(); const worker=receiver(guard);
  for(const code of [301,302,303,307,308]) {
    assert.equal((await worker.fetch(new Request(origin+receivePath.replace('/302',`/${code}`)))).status,204);
  }
  const receipt=await guard.inspect();
  assert.equal(receipt.arrivals,5); assert.equal(receipt.authorizationPresent,false); assert.equal(receipt.canaryMatch,false);
  raw.close();
});

test('expiry after work but before report publication refuses final response',async()=>{
  const {raw,guard,setTime}=await setup();
  const wrapped={...guard,async inspect(){const receipt=await guard.inspect();setTime(1200100);return receipt;}};
  const response=await receiver(wrapped).fetch(request('report',{Authorization:'FGA-Qualification '+capability}));
  assert.equal(response.status,404); assert.equal(await response.text(),''); raw.close();
});

test('fixed-origin service-binding receiver accepts exact redirect paths with retained or stripped synthetic headers',async()=>{
  const {raw,guard}=await setup();
  const fixedOrigin='https://flickrgroupaddr.com';
  const worker=createReceiver({guard,run,origin:fixedOrigin,capability,canary});
  for(const headers of [{},{Authorization:'FGA-Qualification '+capability,'X-FGA-Canary':canary}])
    assert.equal((await worker.fetch(new Request(fixedOrigin+receivePath,{headers}))).status,204);
  assert.equal((await worker.fetch(new Request(fixedOrigin+receivePath,{headers:{Authorization:'Bearer production'}}))).status,404);
  const receipt=await guard.inspect();
  assert.equal(receipt.receiver,2);assert.equal(receipt.arrivals,2);assert.equal(receipt.authorizationPresent,true);assert.equal(receipt.canaryMatch,true);
  assert.equal((await worker.fetch(new Request(fixedOrigin+receivePath+'?extra=1'))).status,404);
  assert.throws(()=>createReceiver({guard,run,origin:'https://other.invalid',capability,canary}));raw.close();
});

test('storage failure and wrong run fail closed; absent state cannot publish',async()=>{
  const {raw,db}=await setup();
  const wrong=createQuotaGuard({db,run:'d'.repeat(32),clock:()=>100});
  assert.equal(await wrong.admit('fga','png'),false); assert.equal(await wrong.canPublish(),false); assert.equal(await wrong.disable(),false);
  raw.close(); assert.equal(await wrong.admit('fga','png'),false); assert.equal(await wrong.canPublish(),false); assert.equal(await wrong.inspect(),null);
});

test('real concurrent SQLite connections cannot overshoot either role quota',async()=>{
  const directory=mkdtempSync(join(tmpdir(),'fga-quota-')),file=join(directory,'synthetic.sqlite');
  const {raw}=await setup(file); raw.exec('PRAGMA journal_mode=WAL');
  const workerCode=`const {parentPort,workerData}=require('node:worker_threads');
    const {DatabaseSync}=require('node:sqlite');
    (async()=>{ const {createQuotaGuard}=await import(workerData.module);
      const raw=new DatabaseSync(workerData.file);raw.exec('PRAGMA busy_timeout=5000');
      const db={prepare(sql){return {args:[],bind(...args){this.args=args;return this},async first(){return raw.prepare(sql).get(...this.args)??null}}}};
      const guard=createQuotaGuard({db,run:workerData.run,clock:()=>100});let fga=0,receiver=0;
      for(let i=0;i<40;i++){fga+=await guard.admit('fga','png');receiver+=await guard.admit('receiver','report');}
      raw.close();parentPort.postMessage({fga,receiver});})().catch(()=>process.exit(1));`;
  try {
    const results=await Promise.all(Array.from({length:4},()=>new Promise((resolve,reject)=>{
      const worker=new Worker(workerCode,{eval:true,workerData:{file,run,module:new URL('./quota_receiver.mjs',import.meta.url).href}});
      worker.once('message',resolve);worker.once('error',reject);worker.once('exit',code=>{if(code)reject(Error('worker_failed'));});
    })));
    assert.equal(results.reduce((n,r)=>n+r.fga,0),96); assert.equal(results.reduce((n,r)=>n+r.receiver,0),16);
    assert.equal(raw.prepare('SELECT fga_count n FROM qualification_run').get().n,96);
  } finally {raw.close();rmSync(directory,{recursive:true,force:true});}
});
