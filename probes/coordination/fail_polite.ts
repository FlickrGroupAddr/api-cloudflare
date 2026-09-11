// Controllable HTTPS fixture adapter; never accepts a real Flickr host or credential.
import { runPartition, type AttemptContext, type FaultPoint, type Transport } from "../../src/fail_polite.ts";
import type { SqlStore } from "../../src/admission.ts";
interface Fixture { DB:D1Database;PROOF_TOKEN:string; }
interface Settings { partition_id:string;peer_origin:string;fault:string;response_code:number;present:number;before_age:number;after_age:number;rollback_result:number; }
export const ATTEMPT_STATE:Record<string,string>={
 attempts:"SELECT * FROM submission_attempts ORDER BY intent_id,ordinal",
 membership:"SELECT * FROM attempt_membership ORDER BY attempt_id",
 preflights:"SELECT * FROM attempt_preflights ORDER BY attempt_id",
 dispatches:"SELECT * FROM attempt_dispatches ORDER BY attempt_id",
 resolutions:"SELECT * FROM attempt_resolutions ORDER BY attempt_id",
 peer:"SELECT * FROM probe_peer_operations ORDER BY sequence",
};
export async function configure(env:Fixture,input:Record<string,unknown>,origin:string):Promise<void> {
 await env.DB.prepare(`INSERT INTO probe_fail_config(partition_id,peer_origin,fault,response_code,present,before_age,after_age,rollback_result)
 VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(partition_id) DO UPDATE SET peer_origin=excluded.peer_origin,fault=excluded.fault,response_code=excluded.response_code,
 present=excluded.present,before_age=excluded.before_age,after_age=excluded.after_age,rollback_result=excluded.rollback_result`).bind(
 input.partitionId as string,origin,String(input.fault??""),Number(input.responseCode??6),Number(input.present??0),Number(input.beforeAge??0),Number(input.afterAge??0),Number(input.rollbackResult??0)).run();
}
export async function peer(request:Request,env:Fixture):Promise<Response> {
 const params=request.method==="POST"?new URLSearchParams(await request.text()):new URL(request.url).searchParams;
 const attempt=params.get("attempt_id"),method=params.get("method"),photo=params.get("photo_id"),group=params.get("group_id");
 const config=await env.DB.prepare(`SELECT c.* FROM probe_fail_config c JOIN submission_intents i ON i.partition_id=c.partition_id JOIN submission_attempts a ON a.intent_id=i.intent_id
 WHERE a.attempt_id=? AND i.photo_id=? AND i.group_id=?`).bind(attempt,photo,group).first<Settings>();
 if(!config||!method||!['flickr.photos.getAllContexts','flickr.groups.getInfo','flickr.groups.pools.add'].includes(method)) return new Response(null,{status:400});
 if((method==='flickr.groups.pools.add')!==(request.method==='POST')) return new Response(null,{status:400});
 await env.DB.prepare(`INSERT INTO probe_peer_operations(attempt_id,photo_id,group_id,method,marker_visible)
 VALUES(?,?,?,?,EXISTS(SELECT 1 FROM attempt_dispatches WHERE attempt_id=?))`).bind(attempt,photo,group,method,attempt).run();
 if(method==='flickr.photos.getAllContexts') return Response.json({stat:'ok',pool:config.present?[{id:group}]:[]});
 if(method==='flickr.groups.getInfo') return Response.json({stat:'ok',group:{id:group,ispoolmoderated:'0'}});
 if(config.fault==='handoff') await new Promise(resolve=>setTimeout(resolve,15_000));
 if(config.response_code===-1) return new Response('synthetic truncated response',{headers:{'Content-Type':'text/plain'}});
 return Response.json(config.response_code===0?{stat:'ok'}:{stat:'fail',code:config.response_code});
}
function transport(env:Fixture,origin:string):Transport {
 const base=new URL(origin);
 if(base.pathname!=="/"||base.search||base.hash||base.username||base.password||
  !(base.protocol==='https:'&&base.hostname.endsWith('.workers.dev')||base.protocol==='http:'&&base.hostname==='127.0.0.1')) throw new Error('invalid_fixture_origin');
 const operation=async(context:AttemptContext,method:string,post=false):Promise<Record<string,unknown>>=>{
  const params=new URLSearchParams({method,attempt_id:context.attemptId,photo_id:context.photoId,group_id:context.groupId,format:'json',nojsoncallback:'1'});
  const response=await fetch(origin+'/fake'+(post?'':'?'+params),{method:post?'POST':'GET',headers:{Authorization:'Bearer '+env.PROOF_TOKEN,'Content-Type':'application/x-www-form-urlencoded'},body:post?params:undefined,redirect:'manual'});
  if(!response.ok||!response.headers.get('Content-Type')?.startsWith('application/json')) throw new Error('unavailable');
  const text=await response.text();if(text.length>16_384) throw new Error('over_budget');
  const value:unknown=JSON.parse(text);if(!value||typeof value!=='object'||Array.isArray(value)) throw new Error('malformed');
  return value as Record<string,unknown>;
 };
 return {
  async membership(context) {
   const value=await operation(context,'flickr.photos.getAllContexts');
   if(value.stat!=='ok'||!Array.isArray(value.pool)||value.pool.length>256) throw new Error('malformed');
   const ids=new Set<string>();for(const p of value.pool) {
    if(!p||typeof p!=='object'||typeof p.id!=='string'||!p.id||ids.has(p.id)) throw new Error('malformed');ids.add(p.id);
   }return ids.has(context.groupId);
  },
  async preflight(context) {
   const value=await operation(context,'flickr.groups.getInfo'),group=value.group as Record<string,unknown>|undefined;
   if(value.stat!=='ok'||!group||group.id!==context.groupId||!['0','1',0,1].includes(group.ispoolmoderated as string|number)) throw new Error('malformed');
   return Number(group.ispoolmoderated) as 0|1;
  },
  async add(context) {
   const value=await operation(context,'flickr.groups.pools.add',true);
   if(value.stat==='ok') return 'ok';
   if(value.stat==='fail'&&typeof value.code==='number'&&Number.isSafeInteger(value.code)) return value.code;
   throw new Error('ambiguous');
  }
 };
}
export async function consume(env:Fixture,ctx:DurableObjectState,partition:string,revision:string|null,source:string):Promise<string> {
 const config=await env.DB.prepare('SELECT * FROM probe_fail_config WHERE partition_id=?').bind(partition).first<Settings>();
 if(!config) throw new Error('unconfigured_partition');
 let mono=0;
 const prepared=new WeakMap<D1PreparedStatement,string>();
 const db:SqlStore=config.rollback_result?{prepare:sql=>{const s=env.DB.prepare(sql);prepared.set(s,sql);const bind=s.bind.bind(s);s.bind=(...values)=>{const bound=bind(...values);prepared.set(bound,sql);return bound;};return s;},batch:statements=>{
  if(statements.some(s=>prepared.get(s)?.includes('INSERT INTO attempt_resolutions'))) {
   return env.DB.batch([...statements.slice(0,2),env.DB.prepare("INSERT INTO transaction_guards(transaction_id,approved) VALUES('rollback',0)"),...statements.slice(2)]);
  }return env.DB.batch(statements);
 }}:env.DB;
 return runPartition({db,transport:transport(env,config.peer_origin),monotonicUs:()=>mono,
  async reserve(context) {
   await env.DB.prepare("INSERT INTO probe_reservations(attempt_id,slots) VALUES(?,3)").bind(context.attemptId).run();
   const consumed=new Set<string>();let released=false;
   return {consume(operation){if(released||consumed.has(operation))throw new Error('invalid_reservation');consumed.add(operation);},
    releaseUnused(){if(released)throw new Error('double_release');released=true;}};
  },
  async fault(point:FaultPoint) {
   if(point==='preflight_committed')mono=config.before_age;
   if(point==='preflight_committed' && config.fault==='gate_changed') await env.DB.prepare("UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='deployment'").run();
   if(point==='marker_committed')mono=config.after_age;
   if(config.fault===point) {ctx.abort('synthetic_fail_polite_crash');throw new Error('unreachable');}
  }
 },partition,source,revision,{leaseMs:config.peer_origin.startsWith("https:")?10_000:1000,invocationMs:config.peer_origin.startsWith("https:")?10_000:1000});
}
