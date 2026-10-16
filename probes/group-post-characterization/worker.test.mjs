import assert from 'node:assert/strict';
import {test} from 'node:test';
import {CASES,LIMITS,PROOF,batch,origins,createProbe} from './worker.mjs';
function fixture(role='source') {
 const env={ROLE:role,RUN_ID:'a'.repeat(24),SUBDOMAIN:'synthetic',ACCESS:'b'.repeat(64),CANARY:'SYNTHETIC-'+'c'.repeat(32),EXPIRES:'1800001200'};
 const state={count:0,rows:[]};
 env.DB={prepare(sql){return{bind(...args){return{
  async first(){return state.count++<64?{requests:state.count}:null;},
  async all(){return {results:state.rows};},
  async run(){state.rows.push({sql,args});return{success:true};}
 };}};}};
 let clock=1800000000,delays=[];
 const probe=createProbe({now:()=>clock,sleep:async ms=>{delays.push(ms);}});
 function request(id,options={}) {
  const headers={'Authorization':'Bearer '+env.CANARY,'Content-Type':'application/json','X-FGA-Post-Access':env.ACCESS,...options.headers};
  return new Request(origins(env)[role]+(options.path??'/v1/cases/'+id),{method:options.method??'POST',body:options.method==='GET'?undefined:options.body??(id==='proof'?PROOF:batch(id==='batch-sixty'?60:1)),headers});
 }
 return {env,state,probe,request,delays,setClock:t=>{clock=t;}};
}
test('all exact scenarios and fixed headers, statuses, byte and delay limits',async()=>{
 const f=fixture();assert.equal(CASES.length,23);
 for(const id of CASES){const r=await f.probe.fetch(f.request(id),f.env);
  const expected=id.startsWith('status-')?+id.slice(7):id.startsWith('same-')||id.startsWith('cross-')?+id.split('-')[1]:id==='proof'?200:id==='oversize-error'?503:202;
  assert.equal(r.status,expected,id);assert.equal(r.headers.get('Cache-Control'),'no-store');
  if(id.startsWith('oversize'))assert.equal((await r.arrayBuffer()).byteLength,LIMITS.responseBytes);
  if(id.startsWith('same-'))assert.equal(new URL(r.headers.get('Location')).origin,origins(f.env).source);
  if(id.startsWith('cross-'))assert.equal(new URL(r.headers.get('Location')).origin,origins(f.env).receiver);
  if(id==='status-429')assert.equal(r.headers.get('Retry-After'),'2');
 }
 assert.deepEqual(f.delays,[16000,16000,16000]);assert.equal(f.state.count,23);
 assert.ok(f.state.rows.every(r=>r.args[5]===1&&r.args[8]===1));
});
test('reject arbitrary origin, path, methods, missing gate, real-looking header, malformed/oversized body',async()=>{
 const f=fixture();
 for(const req of [new Request('https://example.com/v1/cases/proof'),f.request('proof',{method:'GET'}),f.request('proof',{headers:{'X-FGA-Post-Access':'wrong'}}),f.request('proof',{headers:{Authorization:'Bearer real'}}),f.request('proof',{path:'/v1/other/proof'})])assert.equal((await f.probe.fetch(req,f.env)).status,404);
 assert.equal(f.state.count,0);
 assert.equal((await f.probe.fetch(f.request('proof',{body:'wrong'}),f.env)).status,400);
 assert.equal((await f.probe.fetch(f.request('proof',{body:'x'.repeat(16385)}),f.env)).status,413);
 assert.equal(f.state.rows.length,1); // Oversize request bytes never persisted.
});
test('redirect receiver records GET/POST body and canary independently without echoing them',async()=>{
 for(const method of ['GET','POST']){
  const f=fixture('receiver');const req=f.request('cross-307',{method,path:'/v1/receive/cross-307',headers:{Authorization:'Bearer forwarded-marker'}});
  const result=await f.probe.fetch(req,f.env);assert.equal(result.status,200);
  const row=f.state.rows[0].args;assert.equal(row[3],method);assert.equal(row[6],1);assert.equal(row[7],0);
  assert.ok(!(await result.text()).includes('forwarded-marker'));
 }
});
test('atomic shared cap and expiry fail closed; report requires no Authorization',async()=>{
 const f=fixture();for(let i=0;i<64;i++)await f.probe.fetch(f.request('proof'),f.env);
 assert.equal((await f.probe.fetch(f.request('proof'),f.env)).status,429);
 f.setClock(1800001200);assert.equal((await f.probe.fetch(f.request('proof'),f.env)).status,410);
 const g=fixture();assert.equal((await g.probe.fetch(g.request('proof',{method:'GET',path:'/v1/report'}),g.env)).status,404);
 const req=new Request(origins(g.env).source+'/v1/report',{headers:{'X-FGA-Post-Access':g.env.ACCESS}});
 assert.equal((await g.probe.fetch(req,g.env)).status,200);
});
