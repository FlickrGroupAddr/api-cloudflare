// Disposable hosted integration fixture. Never bind a production Flickr grant here.
import {timingSafeEqual} from "node:crypto";
import fixture,{controlledEnv} from "./worker.ts";
export {ProbePartitionWake} from "./worker.ts";
import {createWorker,type Env as ApiEnv} from "../../src/worker.ts";
import {NOW_US_SQL} from "../../src/installations.ts";
interface Env extends ApiEnv {PROOF_TOKEN:string;PROOF_BUILD:string;PROOF_EXPIRES:string;PROOF_GOOGLE_KEYS:string;}
const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{"Cache-Control":"no-store"}});
function authorized(request:Request,env:Env):boolean{const supplied=request.headers.get("X-FGA-Proof")??"",expiry=Number(env.PROOF_EXPIRES);return supplied.length===43&&typeof env.PROOF_TOKEN==="string"&&env.PROOF_TOKEN.length===43&&timingSafeEqual(Buffer.from(supplied),Buffer.from(env.PROOF_TOKEN))&&Number.isSafeInteger(expiry)&&Date.now()<expiry&&expiry-Date.now()<3600000;}
async function signature(request:Request):Promise<Record<string,string>|null>{try{
 const header=request.headers.get("Authorization")??"";if(!header.startsWith("OAuth "))return null;
 const pairs=header.slice(6).split(/,\s*/).map(part=>{const m=/^([a-z_]+)="([^"]*)"$/.exec(part);if(!m)throw new Error();return [m[1],decodeURIComponent(m[2])];});const auth=Object.fromEntries(pairs),url=new URL(request.url);
 if(Object.keys(auth).length!==pairs.length||auth.oauth_consumer_key!=="synthetic-app-key"||auth.oauth_signature_method!=="HMAC-SHA1"||auth.oauth_version!=="1.0"||!/^\d+$/.test(auth.oauth_timestamp)||!/^[a-f0-9]{64}$/.test(auth.oauth_nonce))return null;
 const secret=!auth.oauth_token?"":auth.oauth_token==="synthetic-token"?"synthetic-token-secret":auth.oauth_token.startsWith("temporary-")?"temporary-secret":auth.oauth_token.startsWith("active-")?"active-secret":null;if(secret===null)return null;
 const encode=(value:string)=>encodeURIComponent(value).replace(/[!'()*]/g,c=>"%"+c.charCodeAt(0).toString(16).toUpperCase());
 const params=[...pairs.filter(([key])=>key!=="oauth_signature"),...url.searchParams];const body=await request.clone().text();if(body)params.push(...new URLSearchParams(body));
 const normalized=params.map(([key,value])=>[encode(key),encode(value)]).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:a[1]<b[1]?-1:a[1]>b[1]?1:0).map(pair=>pair.join("=")).join("&");
 const key=await crypto.subtle.importKey("raw",new TextEncoder().encode("synthetic-app-secret&"+encode(secret)),{name:"HMAC",hash:"SHA-1"},false,["verify"]);
 if(!await crypto.subtle.verify("HMAC",key,Uint8Array.from(atob(auth.oauth_signature),c=>c.charCodeAt(0)),new TextEncoder().encode(request.method+"&"+encode(url.origin+url.pathname)+"&"+encode(normalized))))return null;return auth;
 }catch{return null;}}
async function provider(request:Request,env:Env):Promise<Response>{const url=new URL(request.url);
 if(url.origin==="https://api.cloudflare.com"){
  const ids=[env.CF_GRANT_SLOT_ID,...JSON.parse(env.CF_OAUTH_SLOT_IDS??"[]")];const allowed=ids.map(id=>`/client/v4/accounts/${env.CF_ACCOUNT_ID}/secrets_store/stores/${env.CF_SECRET_STORE_ID}/secrets/${id}`);
  if(request.method!=="PATCH"||!allowed.includes(url.pathname))throw new Error("fixed_fixture_provider_boundary");const response=await fetch(request);try{await env.DB.prepare("INSERT INTO intake_proof_events(kind,status) VALUES('native_patch',?)").bind(response.status).run();}catch{}return response;
 }
 if(request.url==="https://www.googleapis.com/oauth2/v3/certs")return new Response(env.PROOF_GOOGLE_KEYS,{headers:{"Content-Type":"application/json","Cache-Control":"public, max-age=3600"}});
 if(url.origin!=="https://www.flickr.com")throw new Error("real_external_traffic_prohibited");await env.DB.prepare("INSERT INTO intake_probe_calls(method,photo_id) VALUES(?,?)").bind(url.searchParams.get("method")??url.pathname,url.searchParams.get("photo_id")).run();const auth=await signature(request);await env.DB.prepare("INSERT INTO intake_proof_events(kind,status) VALUES('flickr_signature',?)").bind(auth?200:401).run();if(!auth)return new Response(null,{status:401});
 if(url.pathname==="/services/oauth/request_token"){
  const callback=new URL(auth.oauth_callback),state=callback.searchParams.get("state");if(callback.origin!=="https://flickrgroupaddr.com"||callback.pathname!=="/admin/flickr-oauth/callback"||!state||!/^[A-Za-z0-9_-]{43}$/.test(state))return new Response(null,{status:400});return new Response("oauth_callback_confirmed=true&oauth_token=temporary-"+state+"&oauth_token_secret=temporary-secret");
 }
 if(url.pathname==="/services/oauth/access_token"){
  if(!auth.oauth_token?.startsWith("temporary-")||auth.oauth_verifier!=="synthetic-verifier")return new Response(null,{status:400});return new Response("oauth_token=active-"+auth.oauth_token.slice(10)+"&oauth_token_secret=active-secret");
 }
 if(url.pathname!=="/services/rest/")throw new Error("unsupported_synthetic_flickr_method");const method=url.searchParams.get("method"),photo=url.searchParams.get("photo_id");
 const control=await env.DB.prepare("SELECT mode FROM intake_probe_control WHERE id=1").first<{mode:string}>();
 if(method==="flickr.auth.oauth.checkToken")return json({stat:"ok",oauth:{token:{_content:auth.oauth_token},perms:{_content:"write"},user:{nsid:control?.mode==="wrong-owner"?"other-owner":"synthetic-owner"}}});
 if(method!=="flickr.photos.getInfo")throw new Error("flickr_writes_prohibited");
 if(control?.mode==="link-race")await env.DB.prepare("UPDATE flickr_links SET link_revision=link_revision+1 WHERE user_id='owner-a'").run();
 if(control?.mode==="missing")return json({stat:"fail",code:1});if(control?.mode==="revoked")return json({stat:"fail",code:98});if(control?.mode==="malformed")return json({stat:"ok",photo:{id:photo}});
 return json({stat:"ok",photo:{id:control?.mode==="wrong-id"?"different-photo":photo,owner:{nsid:control?.mode==="wrong-owner"?"other-owner":"synthetic-owner"},visibility:{ispublic:control?.mode==="private"?0:1},media:"photo"}});
}
export default {async fetch(request:Request,env:Env):Promise<Response>{
 if(!authorized(request,env))return json({error:"not_found"},404);
 const budget=await env.DB.prepare("UPDATE intake_proof_budget SET used=used+1 WHERE id=1 AND used<1000 RETURNING used").first();if(!budget)return json({error:"proof_budget_exhausted"},503);
 const url=new URL(request.url);
 if(url.pathname==="/proof/ready"){
  const reads=[env.FLICKR_APPLICATION,env.FLICKR_GRANT,env.AUTH_LIMITER_KEY,env.NATIVE_WRITER_TOKEN,env.FLICKR_TEMP_0,env.FLICKR_TEMP_1,env.FLICKR_TEMP_2,env.FLICKR_TEMP_3,env.FLICKR_TEMP_4];
  try{for(const value of reads)if(!value||!(await value.get()))throw new Error();return json({build:env.PROOF_BUILD,ready:true});}catch{return json({build:env.PROOF_BUILD,ready:false},503);}
 }
 if(url.pathname==="/proof/duplicate-hint"){
  const input=await request.json() as {group:string};const row=await env.DB.prepare("SELECT partition_id id,wake_revision revision FROM group_partitions WHERE user_id='owner-a' AND group_id=?").bind(input.group).first<{id:string;revision:number}>();if(!row||!env.COORD)return json({error:"missing"},400);
  const stub=env.COORD.get(env.COORD.idFromName(row.id));for(let i=0;i<2;i++)await stub.fetch("https://internal.invalid/wake",{method:"POST",body:JSON.stringify({partitionId:row.id,wakeRevision:String(row.revision)})});return json({delivered:true});
 }
 if(url.pathname==="/proof/observation"){
  let grant:Record<string,unknown>|null=null;try{grant=JSON.parse(await env.FLICKR_GRANT.get());}catch{}
  const ops=await env.DB.prepare("SELECT generation,kind FROM flickr_lifecycle_operations WHERE phase IN ('dispatched','repair_required')").all<{generation:string;kind:string}>();
  const txs=await env.DB.prepare("SELECT slot,generation,retirement_generation,phase FROM flickr_oauth_transactions WHERE phase<>'retired'").all<{slot:number;generation:string;retirement_generation:string|null;phase:string}>();
  const reads=[env.FLICKR_TEMP_0,env.FLICKR_TEMP_1,env.FLICKR_TEMP_2,env.FLICKR_TEMP_3,env.FLICKR_TEMP_4];const temporary=[];
  for(const tx of txs.results){let value:Record<string,unknown>|null=null;try{value=JSON.parse(await reads[tx.slot]!.get());}catch{}temporary.push(tx.phase==="retiring"?value?.generation===tx.retirement_generation&&value?.retired===true:value?.generation===tx.generation);}
  return json({grantObserved:ops.results.every(op=>grant?.generation===op.generation&&(op.kind!=="retire"||grant?.retired===true)),temporaryObserved:temporary.every(Boolean)});
 }
 if(url.pathname==="/proof/maintenance"){await createWorker(r=>provider(r,env)).scheduled({} as ScheduledController,env);return json({maintained:true});}
 if(url.pathname==="/proof/admin-state"){
  const txs=await env.DB.prepare("SELECT slot,phase,generation FROM flickr_oauth_transactions ORDER BY created_at_us").all<{slot:number;phase:string;generation:string}>();const reads=[env.FLICKR_TEMP_0,env.FLICKR_TEMP_1,env.FLICKR_TEMP_2,env.FLICKR_TEMP_3,env.FLICKR_TEMP_4];const transactions=[];for(const tx of txs.results){let observed=false;try{observed=JSON.parse(await reads[tx.slot]!.get()).generation===tx.generation;}catch{}transactions.push({phase:tx.phase,observed});}
  return json({operations:(await env.DB.prepare("SELECT kind,phase,preserve_relink FROM flickr_lifecycle_operations ORDER BY created_at_us").all()).results,transactions,providerStatuses:(await env.DB.prepare("SELECT kind,status FROM intake_proof_events ORDER BY rowid").all()).results});
 }
 if(url.pathname==="/probe/sweep"){await createWorker(r=>provider(r,env)).scheduled({} as ScheduledController,env);return json({build:env.PROOF_BUILD,result:{swept:true}});}

 if(url.pathname.startsWith("/probe/")){
  const headers=new Headers(request.headers);headers.set("Authorization","Bearer "+env.PROOF_TOKEN);
  const response=await fixture.fetch(new Request(request,{headers}),env);
  if(url.pathname==="/probe/seed"&&response.ok)await env.DB.batch([env.DB.prepare("INSERT INTO admin_principals(user_id,google_issuer,google_sub) VALUES('owner-a','https://accounts.google.com','synthetic-sub')"),env.DB.prepare(`INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('owner-a','linked','available','write',${NOW_US_SQL})`)]);
  return response;
 }
 const canonical=new URL(request.url);canonical.protocol="https:";canonical.host="flickrgroupaddr.com";
 const adapted=new Request(canonical,request);Object.defineProperty(adapted,"cf",{value:request.cf});
 return createWorker(r=>provider(r,env)).fetch(adapted,await controlledEnv(env));
 }} satisfies ExportedHandler<Env>;
