// Isolated fixture wrapper. None of these endpoints are exported by src/worker.ts.
import { createWorker,type Env as ApiEnv } from "../../src/worker.ts";
import { credentialDigest,NOW_US_SQL } from "../../src/installations.ts";
import { claimPartition } from "../../src/scheduling.ts";
interface Env extends ApiEnv {PROOF_TOKEN:string;PROOF_BUILD:string;}
const CODE="0000-".repeat(12)+"0000",PENDING="2222-".repeat(12)+"2220";
export class ProbePartitionWake {
 private env:Env;
 constructor(_ctx:DurableObjectState,env:Env){this.env=env;}
 async fetch(request:Request):Promise<Response> {
  const hint=await request.json() as {partitionId:string;wakeRevision:string};
  await this.env.DB.prepare("INSERT INTO intake_probe_hints(partition_id,wake_revision) VALUES(?,?)").bind(hint.partitionId,hint.wakeRevision).run();
  const control=await this.env.DB.prepare("SELECT lose_hint FROM intake_probe_control WHERE id=1").first<{lose_hint:number}>();
  if(control?.lose_hint)return new Response(null,{status:503});
  const lease=await claimPartition(this.env.DB,hint.partitionId,"native-wake-"+crypto.randomUUID(),hint.wakeRevision);
  return Response.json({claimed:lease!==null});
 }
}
async function seed(env:Env):Promise<void> {
 await env.DB.batch([
 env.DB.prepare("INSERT INTO fga_users VALUES('owner-a'),('owner-b')"),
 env.DB.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id,pending_version_id) VALUES('installation-a','owner-a','lrc_plugin','active',1,'current-a','pending-a')"),
 env.DB.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('current-a','installation-a',?,'current',1,NULL),('pending-a','installation-a',?,'pending_rotation',2,${NOW_US_SQL}+900000000)`).bind(await credentialDigest(CODE),await credentialDigest(PENDING)),
 env.DB.prepare("INSERT INTO flickr_links VALUES('owner-a','synthetic-owner',1,'linked'),('owner-b','other-owner',1,'linked')"),
 env.DB.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('owner-a','generation-a',1,'synthetic-owner','write')"),
 env.DB.prepare("INSERT INTO flickr_write_gates(scope,scope_id,enabled) VALUES('deployment','*',1),('user','owner-a',1),('user','owner-b',1)"),
 env.DB.prepare("INSERT INTO intake_probe_control(id) VALUES(1)")]);
}
const TABLES=["photo_bindings","photo_binding_events","submission_intents","group_partitions","submission_intent_events","submission_blocks","transaction_guards","partition_lease_events","intake_probe_hints","intake_probe_calls"];
export default {
 async fetch(request:Request,env:Env):Promise<Response> {
  const url=new URL(request.url);
  if(url.pathname.startsWith("/probe/")) {
   if(request.headers.get("Authorization")!=="Bearer "+env.PROOF_TOKEN)return new Response(null,{status:401});
   const reply=(result:unknown)=>Response.json({build:env.PROOF_BUILD,result});
   if(url.pathname==="/probe/seed"){await seed(env);return reply({seeded:true});}
   if(url.pathname==="/probe/state"){
    const result:Record<string,unknown>={};for(const table of TABLES)result[table]=(await env.DB.prepare("SELECT * FROM "+table+" ORDER BY rowid").all()).results;return reply(result);
   }
   if(url.pathname==="/probe/control") {
    const v=await request.json() as {fault?:number;loseHint?:number;mode?:string;limit?:string;futureClass?:number};
    await env.DB.prepare("UPDATE intake_probe_control SET fault_stage=?,lose_hint=?,mode=?,configured_limit=?,future_class=? WHERE id=1").bind(v.fault??-1,v.loseHint??0,v.mode??"public",v.limit??"60",v.futureClass??0).run();return reply({set:true});
   }
   if(url.pathname==="/probe/age"){
    const v=await request.json() as {bindingId:string};await env.DB.prepare(`UPDATE photo_bindings SET verified_at_us=${NOW_US_SQL}-16000000 WHERE binding_id=?`).bind(v.bindingId).run();return reply({aged:true});
   }
   if(url.pathname==="/probe/sweep"){await api(env,url.origin).scheduled?.({} as ScheduledController,env);return reply({swept:true});}
   if(url.pathname==="/probe/pause"){await env.DB.prepare("UPDATE flickr_links SET state='paused',link_revision=link_revision+1 WHERE user_id='owner-a'").run();return reply({paused:true});}
   if(url.pathname==="/probe/peer")return peer(request,env);
   return new Response(null,{status:404});
  }
  const control=await env.DB.prepare("SELECT * FROM intake_probe_control WHERE id=1").first<{fault_stage:number;future_class:number;configured_limit:string}>();
  const prepared=new WeakMap<D1PreparedStatement,string>();
  const db={prepare:(sql:string)=>{
   if(control?.future_class&&sql.includes("SELECT i.installation_id,i.credential_class"))sql=sql.replace("i.credential_class","'future_class' AS credential_class");
   const statement=env.DB.prepare(sql);prepared.set(statement,sql);const bind=statement.bind.bind(statement);
   statement.bind=(...values)=>{const bound=bind(...values);prepared.set(bound,sql);return bound;};return statement;
  },batch:async(statements:D1PreparedStatement[])=>{
   if(control&&control.fault_stage>=0&&statements.some(s=>prepared.get(s)?.includes("INSERT INTO submission_intents"))) {
    const at=control.fault_stage;return env.DB.batch([...statements.slice(0,at),env.DB.prepare("INSERT INTO transaction_guards(transaction_id,approved) VALUES('injected',0)"),...statements.slice(at)]);
   }return env.DB.batch(statements);
  }} as D1Database;
  return api(env,url.origin).fetch(request,{...env,DB:db,FGA_MAX_GROUP_IDS_PER_BATCH:control?.configured_limit??"60"});
 },
 async scheduled(event:ScheduledController,env:Env,ctx:ExecutionContext){await api(env,"").scheduled?.(event,env);}
} satisfies ExportedHandler<Env>;
function api(env:Env,origin:string){return createWorker(async upstream=>{
 const url=new URL(upstream.url);if(url.origin!=="https://www.flickr.com"||url.pathname!=="/services/rest/")throw new Error("unexpected_upstream");
 return fetch(origin+"/probe/peer",{method:"POST",headers:{Authorization:"Bearer "+env.PROOF_TOKEN,"X-FGA-Synthetic-OAuth":upstream.headers.get("Authorization")!,"Content-Type":"application/json"},body:JSON.stringify({method:url.searchParams.get("method"),photoId:url.searchParams.get("photo_id")}),redirect:"manual"});
});}
async function peer(request:Request,env:Env):Promise<Response> {
 const input=await request.json() as {method:string;photoId:string};
 const auth=request.headers.get("X-FGA-Synthetic-OAuth")??"";
 if(!await validSignature(auth,input))return new Response(null,{status:401});
 await env.DB.prepare("INSERT INTO intake_probe_calls(method,photo_id) VALUES(?,?)").bind(input.method,input.photoId).run();
 const control=await env.DB.prepare("SELECT mode FROM intake_probe_control WHERE id=1").first<{mode:string}>();
 if(control?.mode==="link-race")await env.DB.prepare("UPDATE flickr_links SET link_revision=link_revision+1 WHERE user_id='owner-a'").run();
 if(control?.mode==="missing")return Response.json({stat:"fail",code:1});
 if(control?.mode==="malformed")return Response.json({stat:"ok",photo:{id:input.photoId}});
 return Response.json({stat:"ok",photo:{id:control?.mode==="wrong-id"?"different-photo":input.photoId,owner:{nsid:control?.mode==="wrong-owner"?"other-owner":"synthetic-owner"},visibility:{ispublic:control?.mode==="private"?0:1},media:"photo",title:{_content:"Must not persist"},secret:"Must not persist"}});
}

async function validSignature(header:string,input:{method:string;photoId:string}):Promise<boolean> {
 try {
  if(!header.startsWith("OAuth "))return false;
  const pairs=header.slice(6).split(/,\s*/).map(part=>{const match=/^([a-z_]+)="([^"]*)"$/.exec(part);if(!match)throw new Error("shape");return [match[1],decodeURIComponent(match[2])] as const;});
  const auth=Object.fromEntries(pairs);
  if(pairs.length!==7||Object.keys(auth).length!==7||auth.oauth_consumer_key!=="synthetic-app-key"||auth.oauth_token!=="synthetic-token"||auth.oauth_signature_method!=="HMAC-SHA1"||auth.oauth_version!=="1.0"||!/^\d+$/.test(auth.oauth_timestamp)||!/^[a-f0-9]{64}$/.test(auth.oauth_nonce))return false;
  const encode=(v:string)=>encodeURIComponent(v).replace(/[!'()*]/g,c=>"%"+c.charCodeAt(0).toString(16).toUpperCase());
  const params=[...pairs.filter(([name])=>name!=="oauth_signature"),["format","json"],["nojsoncallback","1"],["method",input.method],["photo_id",input.photoId]];
  const normalized=params.map(([k,v])=>[encode(k),encode(v)]).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:a[1]<b[1]?-1:a[1]>b[1]?1:0).map(([k,v])=>k+"="+v).join("&");
  const base="GET&"+encode("https://www.flickr.com/services/rest/")+"&"+encode(normalized);
  const key=await crypto.subtle.importKey("raw",new TextEncoder().encode("synthetic-app-secret&synthetic-token-secret"),{name:"HMAC",hash:"SHA-1"},false,["verify"]);
  const signature=Uint8Array.from(atob(auth.oauth_signature),c=>c.charCodeAt(0));
  return crypto.subtle.verify("HMAC",key,signature,new TextEncoder().encode(base));
 }catch{return false;}
}
