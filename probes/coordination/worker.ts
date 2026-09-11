import * as failPolite from "./fail_polite.ts";
// Disposable provider fixture. No proof route or actor is registered in the public API.
import { admit, type AdmissionAuth, type SqlStore, type WakeHint } from "../../src/admission.ts";
import { claimPartition,deferHead,duePartitions,releaseLease,renewLease,scheduleView,type Lease,type LeasePolicy } from "../../src/scheduling.ts";
import { credentialDigest,NOW_US_SQL } from "../../src/installations.ts";
interface Env { DB:D1Database; COORD?:DurableObjectNamespace; PROOF_TOKEN:string; PROOF_BUILD:string; PROOF_EXPIRES:string; PROOF_MODE:string; }
const AUTH:AdmissionAuth={installationId:"installation-a",credentialDigest:"a".repeat(64)};
function reply(env:Env,result:unknown,status=200):Response { return Response.json({build:env.PROOF_BUILD,result},{status,headers:{"Cache-Control":"no-store"}}); }
async function event(env:Env,kind:string,partition:string|null=null,instance:string|null=null,detail:string|null=null):Promise<void> {
 await env.DB.prepare("INSERT INTO probe_events(id,kind,partition_id,instance_id,detail) VALUES(?,?,?,?,?)").bind(crypto.randomUUID(),kind,partition,instance,detail).run();
}
async function seed(env:Env):Promise<void> {
 if((await env.DB.prepare("SELECT initialized FROM probe_control WHERE id=1").first<{initialized:number}>())?.initialized===1) return;
 const bindings=Array.from({length:100},(_,i)=>({id:`binding-${i}`,photo:`photo-${i}`,source:i>=80?"existing_public":"upload",user:i===99?"owner-b":"owner-a"}));
 const list=[
  env.DB.prepare("INSERT INTO fga_users VALUES('owner-a'),('owner-b')"),
  env.DB.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id,pending_version_id) VALUES('installation-a','owner-a','lrc_plugin','active',1,'version-a','pending-a'),('installation-b','owner-b','lrc_plugin','active',1,'version-b',NULL)"),
  env.DB.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version-a','installation-a',?,'current',1),('version-b','installation-b',?,'current',1)").bind("a".repeat(64),"b".repeat(64)),
  env.DB.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending-a','installation-a',?,'pending_rotation',2,${NOW_US_SQL}+900000000)`).bind("c".repeat(64)),
  env.DB.prepare("INSERT INTO flickr_links VALUES('owner-a','synthetic-owner-a',1,'linked'),('owner-b','synthetic-owner-b',1,'linked')"),
  env.DB.prepare("INSERT INTO flickr_write_gates(scope,scope_id,enabled) VALUES('deployment','*',1),('user','owner-a',1),('user','owner-b',1)"),
  env.DB.prepare(`INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind)
   SELECT json_extract(value,'$.id'),json_extract(value,'$.user'),json_extract(value,'$.photo'),
    'synthetic-'||json_extract(value,'$.user'),1,1,json_extract(value,'$.source') FROM json_each(?)`).bind(JSON.stringify(bindings)),
  env.DB.prepare("INSERT INTO probe_control(id,initialized) VALUES(1,1)"),
 ];
 try { await env.DB.batch(list); } catch(error) {
  if((await env.DB.prepare("SELECT initialized FROM probe_control WHERE id=1").first<{initialized:number}>())?.initialized!==1) throw error;
 }
}
const STATE_SQL:Record<string,string>={
 bindings:"SELECT binding_id,user_id,photo_id,CAST(link_revision AS TEXT) link_revision,CAST(verification_revision AS TEXT) verification_revision,CAST(verified_at_us AS TEXT) verified_at_us,CAST(last_admission_at_us AS TEXT) last_admission_at_us FROM photo_bindings ORDER BY binding_id",
 partitions:"SELECT partition_id,user_id,group_id,CAST(next_enqueue_ordinal AS TEXT) next_ordinal,CAST(next_work_not_before_us AS TEXT) due_us,CAST(wake_revision AS TEXT) wake_revision,lease_id,CAST(lease_generation AS TEXT) generation,CAST(lease_expires_at_us AS TEXT) expires_us,CAST(last_claim_at_us AS TEXT) last_claim_us FROM group_partitions ORDER BY user_id,group_id",
 intents:"SELECT intent_id,binding_id,photo_id,group_id,partition_id,CAST(enqueue_ordinal AS TEXT) ordinal,state,active_fifo_member,CAST(state_version AS TEXT) state_version,CAST(created_at_us AS TEXT) created_us,CAST(next_attempt_not_before_us AS TEXT) retry_us,created_request_id FROM submission_intents ORDER BY photo_id,group_id",
 events:"SELECT event_id,intent_id,kind,correlation_id,CAST(created_at_us AS TEXT) created_us FROM submission_intent_events ORDER BY event_id",
 leases:"SELECT event_id,partition_id,lease_id,CAST(lease_generation AS TEXT) generation,kind,invocation_id,CAST(created_at_us AS TEXT) created_us FROM partition_lease_events ORDER BY event_id",
 guards:"SELECT transaction_id,approved,CAST(now_us AS TEXT) now_us FROM transaction_guards ORDER BY transaction_id",
 blocks:"SELECT * FROM submission_blocks ORDER BY photo_id,group_id",
};
async function state(env:Env):Promise<Record<string,unknown>> {
 const result:Record<string,unknown>={};
 for(const [key,sql] of Object.entries(env.PROOF_MODE==="fail-polite"?{...STATE_SQL,...failPolite.ATTEMPT_STATE}:STATE_SQL)) result[key]=(await env.DB.prepare(sql).all()).results;
 return result;
}
async function wake(env:Env,hint:WakeHint,source:string):Promise<unknown> {
 if(!env.COORD) throw new Error("no_coordinator");
 const stub=env.COORD.get(env.COORD.idFromName(hint.partitionId));
 const response=await stub.fetch("https://internal.invalid/wake",{method:"POST",body:JSON.stringify({...hint,source})});
 if(!response.ok) throw new Error("coordinator_unavailable");
 return response.json();
}
async function sweep(env:Env,source:string):Promise<number> {
 const due=await duePartitions(env.DB);
 await Promise.all(due.map(h=>wake(env,h,source)));
 await event(env,source+"_sweep",null,null,String(due.length));
 return due.length;
}
export class ProbePartitionWake {
 private ctx:DurableObjectState; private env:Env; private instance=crypto.randomUUID();
 constructor(ctx:DurableObjectState,env:Env) { this.ctx=ctx;this.env=env; }
 private async arm(partitionId:string):Promise<void> {
  const view=await scheduleView(this.env.DB,partitionId);
  if(!view?.wakeAfterUs || !view.headId || view.gatesEnabled!==1) return;
  const delta=BigInt(view.wakeAfterUs)-BigInt(view.nowUs);
  if(delta<=0n) return; // A refused due claim relies on the sweep, never a hot alarm loop.
  // Worker wall time chooses only an advisory alarm. D1 rechecks all authority.
  const delay=Number(delta>0n?delta/1000n:0n);
  const desired=Date.now()+Math.min(Math.max(delay,50),86_400_000);
  await this.ctx.storage.transaction(async tx=>{const old=await tx.getAlarm();if(old===null || desired<old) await tx.setAlarm(desired);});
 }
 private async consume(partitionId:string,revision:string|null,source:string):Promise<unknown> {
  const before=await scheduleView(this.env.DB,partitionId);
  if(!before || (revision!==null && before.wakeRevision!==revision)) return {instance:this.instance,lease:null,stale:true};
  if(this.env.PROOF_MODE==="fail-polite") return {instance:this.instance,outcome:await failPolite.consume(this.env,this.ctx,partitionId,revision,source)};
  const lease=await claimPartition(this.env.DB,partitionId,source+"-"+crypto.randomUUID(),revision);
  await event(this.env,"wake_"+source,partitionId,this.instance,lease?"claimed":"no_claim");
  await this.arm(partitionId);
  return {instance:this.instance,lease};
 }
 async fetch(request:Request):Promise<Response> {
  if(Date.now()>Number(this.env.PROOF_EXPIRES)) return new Response(null,{status:410});
  const path=new URL(request.url).pathname;
  if(path==="/status") return Response.json({instance:this.instance,partitionId:await this.ctx.storage.get("partitionId"),alarm:await this.ctx.storage.getAlarm()});
  if(path==="/evict") {this.ctx.abort("synthetic_coordination_eviction");throw new Error("unreachable");}
  if(path==="/forget") {await this.ctx.storage.deleteAlarm();return Response.json({forgotten:true});}
  if(path==="/clear") {await this.ctx.storage.deleteAlarm();await this.ctx.storage.deleteAll();return Response.json({cleared:true});}
  if(path!=="/wake") return new Response(null,{status:404});
  const input=await request.json() as WakeHint & {source:string};
  const old=await this.ctx.storage.get<string>("partitionId");
  if(old!==undefined && old!==input.partitionId) return new Response(null,{status:409});
  await this.ctx.storage.put("partitionId",input.partitionId);
  return Response.json(await this.consume(input.partitionId,input.wakeRevision,input.source));
 }
 async alarm():Promise<void> {
  if(Date.now()>Number(this.env.PROOF_EXPIRES)) return;
  const partitionId=await this.ctx.storage.get<string>("partitionId");
  if(partitionId) await this.consume(partitionId,null,"alarm");
 }
}
export default {
 async fetch(request:Request,env:Env):Promise<Response> {
  if(Date.now()>Number(env.PROOF_EXPIRES) || request.headers.get("Authorization")!==`Bearer ${env.PROOF_TOKEN}`) return new Response(null,{status:401});
  const path=new URL(request.url).pathname;
  if(path==="/status") return reply(env,{ready:true});
  if(path==="/fake" && env.PROOF_MODE==="fail-polite") return failPolite.peer(request,env);
  if(path!=="/proof" || request.method!=="POST") return new Response(null,{status:404});
  try {
   const input=await request.json() as {action:string; request?:unknown; auth?:AdmissionAuth;operation?:string;
    partitionId?:string; revision?:string;lease?:Lease;policy?:LeasePolicy;delayMs?:number;faultStage?:number;raceBinding?:boolean;
    bindingId?:string;value?:string|number;scope?:string;kind?:string;hint?:WakeHint;failure?:boolean};
   let result:unknown;
   switch(input.action) {
    case "fail-config": await failPolite.configure(env,input as unknown as Record<string,unknown>,new URL(request.url).origin);result={configured:true};break;
    case "seed": await seed(env);result={seeded:true};break;
    case "state": result=await state(env);break;
    case "snapshot": result={digest:await credentialDigest(JSON.stringify(await state(env)))};break;
    case "admit": {
     const db:SqlStore=input.faultStage===undefined && !input.raceBinding?env.DB:{prepare:sql=>env.DB.prepare(sql),batch:async statements=>{
      if(input.raceBinding) {await env.DB.prepare("UPDATE photo_bindings SET verification_revision=verification_revision+1 WHERE binding_id=?").bind(input.bindingId!).run();return env.DB.batch(statements);}
      const stage=input.faultStage!;if(!Number.isInteger(stage)||stage<0||stage>statements.length) throw new Error("bad_fault_stage");
      return env.DB.batch([...statements.slice(0,stage),env.DB.prepare("INSERT INTO transaction_guards VALUES('injected',0,0)"),...statements.slice(stage)]);
     }};
     result=await admit(db,input.auth??AUTH,input.request,async hint=>{
      const view=await scheduleView(env.DB,hint.partitionId);
      if(!view || view.wakeRevision!==hint.wakeRevision) throw new Error("hint_before_commit");
      await event(env,"hint",hint.partitionId,null,input.operation??"fixture");
      if(input.failure) throw new Error("injected_lost_hint");
     });break;
    }
    case "probe-events": result=(await env.DB.prepare("SELECT kind,partition_id,instance_id,detail,CAST(created_us AS TEXT) created_us FROM probe_events ORDER BY created_us,id").all()).results;break;
    case "fail-group": await env.DB.prepare("UPDATE probe_control SET fail_group=? WHERE id=1").bind(input.value??null).run();result={set:true};break;
    case "age-binding": await env.DB.prepare(`UPDATE photo_bindings SET verified_at_us=${NOW_US_SQL}-? WHERE binding_id=?`).bind(Number(input.value)*1000,input.bindingId!).run();result={set:true};break;
    case "binding-revision": await env.DB.prepare("UPDATE photo_bindings SET verification_revision=verification_revision+1 WHERE binding_id=?").bind(input.bindingId!).run();result={set:true};break;
    case "counter": await env.DB.prepare("UPDATE group_partitions SET next_enqueue_ordinal=CAST(? AS INTEGER) WHERE partition_id=?").bind(input.value!,input.partitionId!).run();result={set:true};break;
    case "generation": await env.DB.prepare("UPDATE group_partitions SET lease_generation=CAST(? AS INTEGER) WHERE partition_id=?").bind(input.value!,input.partitionId!).run();result={set:true};break;
    case "gate": await env.DB.prepare("UPDATE flickr_write_gates SET enabled=?,revision=revision+1 WHERE scope=? AND scope_id=?").bind(Number(input.value),input.scope??"deployment",input.scope==="user"?"owner-a":"*").run();result={set:true};break;
    case "terminal": {
     const id=input.partitionId!;
     await env.DB.batch([
      env.DB.prepare(`UPDATE submission_intents SET state='added',terminal_at_us=${NOW_US_SQL},state_version=state_version+1 WHERE intent_id=(SELECT intent_id FROM submission_intents WHERE partition_id=? AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1)`).bind(id),
      env.DB.prepare(`UPDATE group_partitions SET next_work_not_before_us=(SELECT created_at_us FROM submission_intents WHERE partition_id=? AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1),wake_revision=wake_revision+1 WHERE partition_id=?`).bind(id,id),
     ]);result={set:true};break;
    }
    case "block": {
     const id=input.partitionId!;
     await env.DB.batch([
      env.DB.prepare("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) SELECT photo_id,group_id,'delivery_uncertain','synthetic-attempt' FROM submission_intents WHERE partition_id=? AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1").bind(id),
      env.DB.prepare(`UPDATE submission_intents SET state='delivery_uncertain',terminal_at_us=${NOW_US_SQL},state_version=state_version+1 WHERE intent_id=(SELECT intent_id FROM submission_intents WHERE partition_id=? AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1)`).bind(id),
      env.DB.prepare(`UPDATE group_partitions SET next_work_not_before_us=(SELECT created_at_us FROM submission_intents WHERE partition_id=? AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1),wake_revision=wake_revision+1 WHERE partition_id=?`).bind(id,id),
     ]);result={set:true};break;
    }
    case "attempt-guard": {
     const tables=["submission_attempts","attempt_membership","attempt_preflights","attempt_dispatches","attempt_resolutions"];
     const table=input.kind!;if(!tables.includes(table)) throw new Error("unknown_guard");
     const operation=input.operation;
     const sql=operation==="delete"?`DELETE FROM ${table}`:operation==="update"?`UPDATE ${table} SET attempt_id=attempt_id`:operation==="replace"?`INSERT OR REPLACE INTO ${table} SELECT * FROM ${table}`:null;
     if(!sql)throw new Error("unknown_operation");await env.DB.prepare(sql).run();result={changed:true};break;
    }
    case "guard-write": {
     const checks:Record<string,string>={intent:"DELETE FROM submission_intents",ordinal:"UPDATE submission_intents SET enqueue_ordinal=enqueue_ordinal+1",event:"DELETE FROM submission_intent_events",lease:"DELETE FROM partition_lease_events",block:"DELETE FROM submission_blocks"};
     const sql=checks[input.kind??""];if(!sql) throw new Error("unknown_guard");await env.DB.prepare(sql).run();result={changed:true};break;
    }
    case "claim": result=await claimPartition(env.DB,input.partitionId!,input.operation??crypto.randomUUID(),input.revision??null,input.policy);if(input.failure && result) throw new Error("injected_lost_claim_response");break;
    case "renew": result=await renewLease(env.DB,input.lease!,input.policy);break;
    case "release": result=await releaseLease(env.DB,input.lease!);break;
    case "defer": result=await deferHead(env.DB,input.lease!,input.delayMs!);break;
    case "view": result=await scheduleView(env.DB,input.partitionId!);break;
    case "due": result=await duePartitions(env.DB);break;
    case "wake": result=await wake(env,input.hint!,"hint");break;
    case "sweep": result=await sweep(env,"manual");break;
    case "cron-enable": await env.DB.prepare("UPDATE probe_control SET cron_enabled=? WHERE id=1").bind(Number(input.value)).run();result={set:true};break;
    case "object-status": case "evict": case "forget": case "clear": {
     if(!env.COORD) throw new Error("no_coordinator");
     const stub=env.COORD.get(env.COORD.idFromName(input.partitionId!));
     const response=await stub.fetch("https://internal.invalid/"+(input.action==="object-status"?"status":input.action),{method:"POST"});
     result=await response.json();break;
    }
    default:return reply(env,{error:"unknown_action"},400);
   }
   return reply(env,result);
  } catch { return reply(env,{error:"operation_not_confirmed"},409); }
 },
 async scheduled(_controller:ScheduledController,env:Env):Promise<void> {
  if(!["scheduling","fail-polite"].includes(env.PROOF_MODE) || Date.now()>Number(env.PROOF_EXPIRES)) return;
  const enabled=await env.DB.prepare("SELECT cron_enabled FROM probe_control WHERE id=1").first<{cron_enabled:number}>();
  await event(env,"cron_tick",null,null,String(_controller.scheduledTime));
  if(enabled?.cron_enabled===1) await sweep(env,"cron");
 },
} satisfies ExportedHandler<Env>;
