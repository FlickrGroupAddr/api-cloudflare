import {sessionInventory,revokeSession,revokeOtherSessions} from "./session_inventory.ts";
import {startFlickrOAuth,completeFlickrOAuth,retireOAuthSlot,observeOAuthRetirement,type OAuthSlots,FlickrOAuthError} from "./flickr_oauth.ts";
import {Hono} from "hono";
import {html} from "hono/html";
import {parse} from "cookie-es";
import {timingSafeEqual} from "node:crypto";
import {authenticateBrowser,enforceUnsafe,startLogin,finishLogin,logoutBrowser,digest,ADMIN_ORIGIN,BrowserAuthError} from "./browser_sessions.ts";
import {admitAuthentication,finishAuthentication,sourceKey,AuthAdmissionError} from "./auth_admission.ts";
import {validateGoogle} from "./google_identity.ts";
import {connectionView,resumeWriteGate,beginLifecycle,dispatchLifecycle,reconcileLifecycle,LifecycleError} from "./native_lifecycle.ts";
import {nativeWriter} from "./native_writer.ts";
import {NOW_US_SQL as NOW,errorResponse} from "./installations.ts";
import {jsonBody} from "./intake_api.ts";
import type {FlickrFetch,SecretReads} from "./flickr_reads.ts";
export interface AdminEnv extends SecretReads {ASSETS?:Fetcher;DB:D1Database;FGA_ADMIN_ENABLED?:string;GOOGLE_CLIENT_ID?:string;GOOGLE_OWNER_SUB?:string;FGA_FLICKR_OWNER_NSID?:string;AUTH_LIMITER_KEY?:Pick<SecretsStoreSecret,"get">;NATIVE_WRITER_TOKEN?:Pick<SecretsStoreSecret,"get">;CF_ACCOUNT_ID?:string;CF_SECRET_STORE_ID?:string;CF_GRANT_SLOT_ID?:string;CF_OAUTH_SLOT_IDS?:string;FLICKR_TEMP_0?:Pick<SecretsStoreSecret,"get">;FLICKR_TEMP_1?:Pick<SecretsStoreSecret,"get">;FLICKR_TEMP_2?:Pick<SecretsStoreSecret,"get">;FLICKR_TEMP_3?:Pick<SecretsStoreSecret,"get">;FLICKR_TEMP_4?:Pick<SecretsStoreSecret,"get">;}
export const ADMIN_PATHS=["/admin/login","/admin/google-login","/admin/flickr-oauth/callback","/api/v001/admin/session","/api/v001/admin/session/reauthentication","/api/v001/admin/session/logout","/api/v001/admin/flickr-connection","/api/v001/admin/flickr-connection/disconnection"] as const;
const timestamp=(us:number)=>new Date(us/1000).toISOString().replace("Z","000Z");
export function createAdmin(fetcher:FlickrFetch=request=>fetch(request)){
 const app=new Hono<{Bindings:AdminEnv}>();
 app.use("*",async(c,next)=>{
  c.header("Cache-Control","no-store");c.header("X-Content-Type-Options","nosniff");c.header("Referrer-Policy","no-referrer");
  if(c.env.FGA_ADMIN_ENABLED!=="1"||!c.env.GOOGLE_OWNER_SUB||!c.env.GOOGLE_CLIENT_ID)return errorResponse(503,"service_unavailable","Service unavailable.");
  if(new URL(c.req.url).origin!==ADMIN_ORIGIN)return errorResponse(400,"invalid_request","Invalid request origin.");
  await next();
 });
 app.onError((error)=>{
  const code=error instanceof BrowserAuthError||error instanceof AuthAdmissionError||error instanceof LifecycleError||error instanceof FlickrOAuthError?error.message:"service_unavailable";
  const statuses:Record<string,number>={unauthorized:401,invalid_origin:403,invalid_csrf:403,recent_authentication_required:403,invalid_google_assertion:401,rate_limited:429,invalid_request:400,stale_connection:409,stale_session_revision:409,stale_session_set:409,current_session_requires_logout:409};
  const response=errorResponse(statuses[code]??503,code,"The request could not be completed.");if(code==="rate_limited")response.headers.set("Retry-After","120");return response;
 });
 async function admission(request:Request,env:AdminEnv,route:"login"|"start"|"callback"){
  // CF-Connecting-IP is trusted only on an actual Cloudflare edge request, never forwarding headers.
  if(!request.cf||!env.AUTH_LIMITER_KEY)throw new AuthAdmissionError("admission_unavailable");
  const source=sourceKey(request.headers.get("CF-Connecting-IP")??"",await env.AUTH_LIMITER_KEY.get());return admitAuthentication(env.DB,source,route);
 }
 app.get("/admin/login",async c=>{
  if(new URL(c.req.url).search)return errorResponse(400,"invalid_request","Invalid request.");
  await admission(c.req.raw,c.env,"start");const tx=await startLogin(c.env.DB);
  c.header("Content-Security-Policy","default-src 'none'; script-src https://accounts.google.com/gsi/client; frame-src https://accounts.google.com; connect-src https://accounts.google.com; style-src 'self' https://accounts.google.com/gsi/style; form-action https://flickrgroupaddr.com/admin/google-login; base-uri 'none'; frame-ancestors 'none'");
  return c.html(html`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Sign in to FGA</title><link rel="stylesheet" href="/admin/styles.css"><main class="login-page"><section class="login-card"><h1>Sign in to FGA</h1><p>Use your configured Google Account to manage your Flickr connection.</p><div id="g_id_onload" data-client_id="${c.env.GOOGLE_CLIENT_ID}" data-login_uri="https://flickrgroupaddr.com/admin/google-login" data-ux_mode="redirect" data-auto_prompt="false" data-auto_select="false" data-nonce="${tx.nonce}"></div><div class="g_id_signin" data-type="standard" data-state="${tx.state}"></div><script src="https://accounts.google.com/gsi/client" async defer></script></section></main></html>`);
 });
 app.post("/admin/google-login",async c=>{
  const cost=await admission(c.req.raw,c.env,"login");
  if(!/^application\/x-www-form-urlencoded(?:;\s*charset=utf-8)?$/i.test(c.req.header("Content-Type")??""))return errorResponse(415,"unsupported_media_type","Use form content.");
  // Bounded streaming parse before invoking any JWT library.
  const reader=c.req.raw.body?.getReader();if(!reader)throw new BrowserAuthError("invalid_google_assertion");let size=0;const parts:Uint8Array[]=[];
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>20000){await reader.cancel();throw new BrowserAuthError("invalid_google_assertion");}parts.push(value);}
  const all=new Uint8Array(size);let offset=0;for(const p of parts){all.set(p,offset);offset+=p.length;}
  const form=new URLSearchParams(new TextDecoder("utf-8",{fatal:true,ignoreBOM:false}).decode(all));
  for(const key of ["credential","state","g_csrf_token"])if(form.getAll(key).length!==1||!form.get(key))throw new BrowserAuthError("invalid_google_assertion");
  const rawCookie=c.req.header("Cookie")??"";if(rawCookie.split(";").filter(x=>x.trim().startsWith("g_csrf_token=")).length!==1)throw new BrowserAuthError("invalid_google_assertion");
  const expected=parse(rawCookie).g_csrf_token,supplied=form.get("g_csrf_token")!;
  if(!expected||expected.length>256||supplied.length>256||expected.length!==supplied.length||!timingSafeEqual(Buffer.from(expected),Buffer.from(supplied)))throw new BrowserAuthError("invalid_google_assertion");
  const state=form.get("state")!;if(!/^[A-Za-z0-9_-]{43}$/.test(state))throw new BrowserAuthError("invalid_google_assertion");
  const tx=await c.env.DB.prepare(`SELECT nonce_digest FROM google_login_transactions WHERE state_digest=? AND consumed_at_us IS NULL AND expires_at_us>${NOW}`).bind(digest(state)).first<{nonce_digest:string}>();if(!tx)throw new BrowserAuthError("invalid_google_assertion");
  const sub=await validateGoogle(c.env.DB,form.get("credential")!,c.env.GOOGLE_CLIENT_ID!,tx.nonce_digest,fetcher);
  if(sub!==c.env.GOOGLE_OWNER_SUB)throw new BrowserAuthError("unauthorized");
  const cookie=await finishLogin(c.env.DB,{stateDigest:digest(state),nonceDigest:tx.nonce_digest,googleSub:sub,ownerSub:c.env.GOOGLE_OWNER_SUB!,ownerNsid:c.env.FGA_FLICKR_OWNER_NSID});
  try{await finishAuthentication(c.env.DB,cost);}catch{/* Conservatively retain the cost charge. */}
  c.header("Set-Cookie",cookie);return c.redirect("/admin/",303);
 });
 app.get("/api/v001/admin/session",async c=>{const s=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);return c.json({schemaVersion:1,sessionId:s.sessionId,revision:s.revision,sessionSetRevision:s.sessionSetRevision,createdAt:timestamp(s.createdAtUs),recentAuthenticationAt:timestamp(s.recentAtUs),lastActivityAt:timestamp(s.lastActivityUs),expiresAt:timestamp(s.expiresAtUs),csrfToken:s.csrfToken});});
 app.post("/api/v001/admin/session/reauthentication",async c=>{const s=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);enforceUnsafe(c.req.raw,s);await admission(c.req.raw,c.env,"start");return c.json({schemaVersion:1,...await startLogin(c.env.DB,s)},201);});
 app.post("/api/v001/admin/session/logout",async c=>{const cookie=await logoutBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);c.header("Set-Cookie",cookie);return c.body(null,204);});
 app.get("/api/v001/admin/flickr-connection",async c=>{const s=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);return c.json(await connectionView(c.env.DB,s.userId) as object);});
 app.post("/api/v001/admin/flickr-connection/disconnection",async c=>{
  const s=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);enforceUnsafe(c.req.raw,s,true);
  const body=await jsonBody(c.req.raw);if(body instanceof Response)return body;
  if(!body||typeof body!=="object"||Object.keys(body).sort().join()!=="expectedFlickrOwnerNsid,expectedRevision,schemaVersion")return errorResponse(400,"invalid_request","Invalid confirmation.");
  const value=body as {schemaVersion:number;expectedRevision:number;expectedFlickrOwnerNsid:string};const view=await connectionView(c.env.DB,s.userId) as {flickrOwnerNsid:string};
  if(value.schemaVersion!==1||value.expectedFlickrOwnerNsid!==view.flickrOwnerNsid)return errorResponse(400,"invalid_request","Invalid confirmation.");
  if(!c.env.NATIVE_WRITER_TOKEN)throw new LifecycleError("writer_configuration_unavailable");
  const writer=nativeWriter(c.env.CF_ACCOUNT_ID??"",c.env.CF_SECRET_STORE_ID??"",c.env.CF_GRANT_SLOT_ID??"",c.env.NATIVE_WRITER_TOKEN,fetcher);
  const op=await beginLifecycle(c.env.DB,s.userId,value.expectedRevision,"retire",{sessionId:s.sessionId,googleSub:c.env.GOOGLE_OWNER_SUB!});await dispatchLifecycle(c.env.DB,op.operationId,writer);
  const retired=await reconcileLifecycle(c.env.DB,op.operationId,c.env,fetcher);return c.json(await connectionView(c.env.DB,s.userId) as object,retired?200:202);
 });

 app.post("/api/v001/admin/flickr-connection/authorization",async c=>{
  const session=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);enforceUnsafe(c.req.raw,session,true);
  const value=await jsonBody(c.req.raw);if(value instanceof Response)return value;
  if(!value||typeof value!=="object"||Object.keys(value).sort().join()!=="expectedRevision,schemaVersion"||(value as {schemaVersion:unknown}).schemaVersion!==1)return errorResponse(400,"invalid_request","Invalid authorization request.");
  const config=oauthInfrastructure(c.env,fetcher);return c.json(await startFlickrOAuth(c.env.DB,session,(value as {expectedRevision:number}).expectedRevision,c.env,config.slots,fetcher) as object,201);
 });
 app.get("/admin/flickr-oauth/callback",async c=>{
  const cost=await admission(c.req.raw,c.env,"callback");
  const query=new URL(c.req.url).searchParams;const keys=[...query.keys()].sort();
  if(keys.join()!=="oauth_token,oauth_verifier,state")return c.redirect("/admin/?flickr=unconfirmed",303);
  const allowed=await c.env.DB.prepare("SELECT 1 FROM flickr_oauth_transactions t JOIN admin_principals p ON p.user_id=t.user_id WHERE t.state_digest=? AND p.google_sub=?").bind(digest(query.get("state")??""),c.env.GOOGLE_OWNER_SUB).first();
  if(!allowed)return c.redirect("/admin/?flickr=unconfirmed",303);
  const config=oauthInfrastructure(c.env,fetcher);const success=await completeFlickrOAuth(c.env.DB,query.get("state")!,query.get("oauth_token")!,query.get("oauth_verifier")!,c.env,config.slots,config.grant,fetcher,c.env.GOOGLE_OWNER_SUB);
  if(success){try{await finishAuthentication(c.env.DB,cost);}catch{}}
  return c.redirect(success?"/admin/?flickr=linked":"/admin/?flickr=unconfirmed",303);
 });


 app.get("/api/v001/admin/sessions",async c=>{const session=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);const query=new URL(c.req.url).searchParams;if([...query.keys()].some(x=>!["pageSize","pageToken"].includes(x))||query.getAll("pageSize").length>1||query.getAll("pageToken").length>1)throw new BrowserAuthError("invalid_request");return c.json(await sessionInventory(c.env.DB,session,query.has("pageSize")?Number(query.get("pageSize")):50,query.get("pageToken")) as object);});
 app.post("/api/v001/admin/sessions/:sessionId/revocation",async c=>{const session=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);enforceUnsafe(c.req.raw,session,true);const value=await jsonBody(c.req.raw);if(value instanceof Response)return value;if(!value||typeof value!=="object"||Object.keys(value).sort().join()!=="expectedRevision,schemaVersion"||(value as {schemaVersion:unknown}).schemaVersion!==1)throw new BrowserAuthError("invalid_request");await revokeSession(c.env.DB,session,c.req.param("sessionId"),(value as {expectedRevision:number}).expectedRevision);return c.body(null,204);});
 app.post("/api/v001/admin/sessions/revoke-others",async c=>{const session=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);enforceUnsafe(c.req.raw,session,true);const value=await jsonBody(c.req.raw);if(value instanceof Response)return value;if(!value||typeof value!=="object"||Object.keys(value).sort().join()!=="expectedActiveOtherSessionCount,expectedSessionSetRevision,schemaVersion"||(value as {schemaVersion:unknown}).schemaVersion!==1)throw new BrowserAuthError("invalid_request");const input=value as {expectedSessionSetRevision:number;expectedActiveOtherSessionCount:number};await revokeOtherSessions(c.env.DB,session,input.expectedSessionSetRevision,input.expectedActiveOtherSessionCount);return c.body(null,204);});
 app.get("/admin/signed-out",c=>{c.header("Content-Security-Policy","default-src 'none'; base-uri 'none'; frame-ancestors 'none'");return c.html(html`<!doctype html><html lang="en"><meta charset="utf-8"><title>Signed out of FGA</title><h1>Signed out of this FGA administrative session</h1><p>Your Google Account session, Flickr grant and installation credentials were not revoked.</p><a href="/admin/login">Sign in again</a></html>`);});
 app.get("/admin/google-client.json",async c=>{await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);return c.json({clientId:c.env.GOOGLE_CLIENT_ID});});
 app.get("/admin/",async c=>{
  try{await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);}catch{return c.redirect("/admin/login",303);}
  if(!c.env.ASSETS)return errorResponse(503,"service_unavailable","Administration assets unavailable.");
  const response=await c.env.ASSETS.fetch(new Request(ADMIN_ORIGIN+"/admin/index.html"));
  const headers=new Headers(response.headers);headers.set("Cache-Control","no-store");headers.set("Referrer-Policy","no-referrer");headers.set("Content-Security-Policy","default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; style-src 'self' https://accounts.google.com/gsi/style; frame-src https://accounts.google.com; connect-src 'self' https://accounts.google.com; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'");return new Response(response.body,{status:response.status,headers});
 });
 for(const gate of ["user","deployment"] as const)app.post("/api/v001/admin/flickr-write-gates/"+gate+"/resume",async c=>{const session=await authenticateBrowser(c.req.raw,c.env.DB,c.env.GOOGLE_OWNER_SUB!);enforceUnsafe(c.req.raw,session,true);const value=await jsonBody(c.req.raw);if(value instanceof Response)return value;if(!value||typeof value!=="object"||Object.keys(value).sort().join()!=="expectedRevision,schemaVersion"||(value as {schemaVersion:unknown}).schemaVersion!==1)return errorResponse(400,"invalid_request","Invalid resume request.");return c.json(await resumeWriteGate(c.env.DB,session.userId,gate,(value as {expectedRevision:number}).expectedRevision,c.env,fetcher) as object);});
 app.notFound(()=>errorResponse(404,"not_found","Resource not found."));return app;
}

export function oauthInfrastructure(env:AdminEnv,fetcher:FlickrFetch){
  const ids=JSON.parse(env.CF_OAUTH_SLOT_IDS??"null");
  if(!Array.isArray(ids)||ids.length!==5||new Set(ids).size!==5||ids.includes(env.CF_GRANT_SLOT_ID)||!env.NATIVE_WRITER_TOKEN)throw new FlickrOAuthError("oauth_configuration_unavailable");
  const reads=[env.FLICKR_TEMP_0,env.FLICKR_TEMP_1,env.FLICKR_TEMP_2,env.FLICKR_TEMP_3,env.FLICKR_TEMP_4];if(reads.some(x=>!x))throw new FlickrOAuthError("oauth_configuration_unavailable");
  const configured=ids.map(slot=>nativeWriter(env.CF_ACCOUNT_ID??"",env.CF_SECRET_STORE_ID??"",slot,env.NATIVE_WRITER_TOKEN!,fetcher));
  const slots:OAuthSlots={read:index=>{if(!Number.isInteger(index)||index<0||index>4)throw new Error("invalid_slot");return reads[index]!.get();},writer:index=>{if(!Number.isInteger(index)||index<0||index>4)throw new Error("invalid_slot");return configured[index];}};
  return {slots,grant:nativeWriter(env.CF_ACCOUNT_ID??"",env.CF_SECRET_STORE_ID??"",env.CF_GRANT_SLOT_ID??"",env.NATIVE_WRITER_TOKEN,fetcher)};
 }

export async function maintainNativeCredentials(env:AdminEnv,fetcher:FlickrFetch):Promise<void>{
 if(!env.NATIVE_WRITER_TOKEN||!env.CF_OAUTH_SLOT_IDS)return;
 const config=oauthInfrastructure(env,fetcher);
 const operations=await env.DB.prepare("SELECT o.operation_id,o.phase,o.kind FROM flickr_lifecycle_operations o JOIN admin_principals p ON p.user_id=o.user_id WHERE (o.phase IN ('dispatched','repair_required') OR (o.phase='prepared' AND o.kind='retire')) AND p.google_sub=? LIMIT 5").bind(env.GOOGLE_OWNER_SUB).all<{operation_id:string;phase:string;kind:string}>();
 for(const op of operations.results){if(op.phase==="prepared"&&op.kind==="retire")await dispatchLifecycle(env.DB,op.operation_id,config.grant);await reconcileLifecycle(env.DB,op.operation_id,env,fetcher);}
 const transactions=await env.DB.prepare(`SELECT t.transaction_id,t.phase FROM flickr_oauth_transactions t JOIN admin_principals p ON p.user_id=t.user_id WHERE p.google_sub=? AND (t.phase IN ('consumed','retiring') OR (t.phase='ready' AND t.expires_at_us<=${NOW})) LIMIT 5`).bind(env.GOOGLE_OWNER_SUB).all<{transaction_id:string;phase:string}>();
 for(const tx of transactions.results){if(tx.phase==="retiring")await observeOAuthRetirement(env.DB,tx.transaction_id,config.slots);else await retireOAuthSlot(env.DB,tx.transaction_id,config.slots);}
}
