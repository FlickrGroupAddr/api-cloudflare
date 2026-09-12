import {createSessionStorage,type Cookie} from "react-router";
import {parse,serialize} from "cookie-es";
import {createHash,randomBytes,timingSafeEqual} from "node:crypto";
import {csrfSync} from "csrf-sync";
import type {SqlStore} from "./admission.ts";
import {NOW_US_SQL as NOW} from "./installations.ts";
export const ADMIN_ORIGIN="https://flickrgroupaddr.com";
const encode=(bytes:Uint8Array)=>btoa(String.fromCharCode(...bytes)).replace(/=/g,"").replace(/\+/g,"-").replace(/\//g,"_");
export const randomToken=()=>encode(randomBytes(32));
export const digest=(value:string)=>createHash("sha256").update(value).digest("hex");
export class BrowserAuthError extends Error {}
const valid=(value:unknown):value is string=>typeof value==="string"&&/^[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$/.test(value);
const cookie:Cookie={name:"__Host-fga_admin",isSigned:false,
 async parse(header){if(!header)return null;const occurrences=header.split(";").filter(s=>s.trim().startsWith("__Host-fga_admin="));if(occurrences.length!==1)return null;const value=parse(header)["__Host-fga_admin"];return valid(value)?value:null;},
 async serialize(value,options){if(value!==""&&!valid(value))throw new BrowserAuthError("invalid_session");return serialize("__Host-fga_admin",value,{path:"/",secure:true,httpOnly:true,sameSite:"strict",maxAge:value===""?0:86400,...(options?.expires?{expires:options.expires}:{})});}
};
export interface AdminSession {sessionId:string;userId:string;csrfToken:string;revision:number;createdAtUs:number;recentAtUs:number;expiresAtUs:number;nowUs:number;sessionSetRevision:number;lastActivityUs:number;}
interface LoginCommit {stateDigest:string;nonceDigest:string;googleSub:string;ownerSub:string;ownerNsid?:string;}
function storage(db:SqlStore,ownerSub:string,commit?:LoginCommit){return createSessionStorage<{authority:AdminSession}>({cookie,
 async readData(token){if(!valid(token)||!ownerSub)return null;
  const row=await db.prepare(`SELECT s.session_id sessionId,s.user_id userId,s.csrf_token csrfToken,s.revision,p.session_set_revision sessionSetRevision,s.last_activity_at_us lastActivityUs,s.created_at_us createdAtUs,s.recent_authentication_at_us recentAtUs,s.expires_at_us expiresAtUs,${NOW} nowUs FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id WHERE s.token_digest=? AND p.google_issuer='https://accounts.google.com' AND p.google_sub=? AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW}`).bind(digest(token),ownerSub).first<AdminSession>();return row?{authority:row}:null;},
 async createData(){if(!commit||commit.googleSub!==ownerSub)throw new BrowserAuthError("unauthorized");return createLogin(db,commit);},
 async updateData(){throw new BrowserAuthError("session_rotation_required");},
 async deleteData(token){await revokeCurrent(db,token,ownerSub);}
 });}
export async function authenticateBrowser(request:Request,db:SqlStore,ownerSub:string):Promise<AdminSession>{
 const session=await storage(db,ownerSub).getSession(request.headers.get("Cookie"));const row=session.get("authority");if(!row)throw new BrowserAuthError("unauthorized");try{await db.prepare(`UPDATE admin_sessions SET last_activity_at_us=${NOW} WHERE session_id=? AND revoked_at_us IS NULL AND expires_at_us>${NOW} AND last_activity_at_us<=${NOW}-300000000`).bind(row.sessionId).run();}catch{console.warn("session_activity_update_unavailable");}return row;
}
const csrf=csrfSync({size:32});
type CsrfRequest=Parameters<typeof csrf.isRequestValid>[0];
export function enforceUnsafe(request:Request,session:AdminSession,recent=false):void {
 if(request.headers.get("Origin")!==ADMIN_ORIGIN)throw new BrowserAuthError("invalid_origin");
 const supplied=request.headers.get("X-CSRF-Token");
 if(!valid(supplied)||!valid(session.csrfToken)||!timingSafeEqual(Buffer.from(supplied),Buffer.from(session.csrfToken)))throw new BrowserAuthError("invalid_csrf");
 const adapted={method:request.method,headers:{"x-csrf-token":supplied},session:{csrfToken:session.csrfToken}} as unknown as CsrfRequest;
 if(!csrf.isRequestValid(adapted))throw new BrowserAuthError("invalid_csrf");
 if(recent&&(session.nowUs-session.recentAtUs<0||session.nowUs-session.recentAtUs>300_000_000))throw new BrowserAuthError("recent_authentication_required");
}
export async function startLogin(db:SqlStore,bound?:AdminSession):Promise<{state:string;nonce:string;expiresAt:string}>{
 const state=randomToken(),nonce=randomToken();
 const rows=await db.prepare(`INSERT INTO google_login_transactions(state_digest,nonce_digest,purpose,bound_session_id,user_id,created_at_us,expires_at_us) SELECT ?,?,?,?,?,${NOW},${NOW}+300000000 WHERE ? IS NULL OR EXISTS(SELECT 1 FROM admin_sessions WHERE session_id=? AND user_id=? AND revoked_at_us IS NULL AND expires_at_us>${NOW}) RETURNING expires_at_us expiry`).bind(digest(state),digest(nonce),bound?"reauthentication":"initial_login",bound?.sessionId??null,bound?.userId??null,bound?.sessionId??null,bound?.sessionId??null,bound?.userId??null).first<{expiry:number}>();
 if(!rows)throw new BrowserAuthError("unauthorized");return {state,nonce,expiresAt:new Date(rows.expiry/1000).toISOString().replace("Z","000Z")};
}
async function createLogin(db:SqlStore,input:LoginCommit):Promise<string>{
 const token=randomToken(),sessionId=crypto.randomUUID(),userId=crypto.randomUUID(),tx=crypto.randomUUID();
 const adapted={session:{}} as CsrfRequest;const csrfToken=encode(Buffer.from(csrf.generateToken(adapted,true),"hex"));
 const params=[input.stateDigest,input.nonceDigest,input.googleSub,userId,sessionId,digest(token),csrfToken,tx,input.ownerNsid??null];
 const q=(sql:string)=>db.prepare("WITH inputs AS(SELECT ?1 state,?2 nonce,?3 sub,?4 user,?5 session,?6 digest,?7 csrf,?8 tx,?9 owner) "+sql).bind(...params);
 await db.batch([
 q(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?8,EXISTS(SELECT 1 FROM google_login_transactions t WHERE t.state_digest=?1 AND t.nonce_digest=?2 AND t.consumed_at_us IS NULL AND t.expires_at_us>${NOW} AND (t.purpose='initial_login' OR EXISTS(SELECT 1 FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id WHERE s.session_id=t.bound_session_id AND s.user_id=t.user_id AND p.google_sub=?3 AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW})))`),
 q("INSERT INTO fga_users(user_id) SELECT ?4 WHERE NOT EXISTS(SELECT 1 FROM admin_principals WHERE google_sub=?3)"),
 q("INSERT INTO admin_principals(user_id,google_issuer,google_sub) SELECT ?4,'https://accounts.google.com',?3 WHERE NOT EXISTS(SELECT 1 FROM admin_principals WHERE google_sub=?3)"),
 q("INSERT INTO flickr_links(user_id,owner_nsid,link_revision,state) SELECT user_id,?9,1,'paused' FROM admin_principals WHERE google_sub=?3 AND ?9 IS NOT NULL AND NOT EXISTS(SELECT 1 FROM flickr_links l WHERE l.user_id=admin_principals.user_id)"),
 q("INSERT INTO flickr_connection_state(user_id,state,local_state) SELECT user_id,'unlinked','absent' FROM admin_principals WHERE google_sub=?3 AND ?9 IS NOT NULL AND NOT EXISTS(SELECT 1 FROM flickr_connection_state c WHERE c.user_id=admin_principals.user_id)"),
 q("INSERT INTO flickr_write_gates(scope,scope_id,enabled,revision) SELECT 'user',user_id,0,1 FROM admin_principals WHERE google_sub=?3 AND ?9 IS NOT NULL AND NOT EXISTS(SELECT 1 FROM flickr_write_gates g WHERE g.scope='user' AND g.scope_id=admin_principals.user_id)"),
 q("INSERT INTO flickr_write_gates(scope,scope_id,enabled,revision) SELECT 'deployment','*',0,1 WHERE ?9 IS NOT NULL AND NOT EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*')"),
 q(`UPDATE admin_sessions SET revoked_at_us=${NOW},revocation_reason='reauthenticated',revision=revision+1 WHERE session_id=(SELECT bound_session_id FROM google_login_transactions WHERE state_digest=?1) AND revoked_at_us IS NULL`),
 q(`INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id) SELECT ?5,?6,user_id,?7,${NOW},${NOW},${NOW}+86400000000,${NOW},?8 FROM admin_principals WHERE google_sub=?3`),
 q("UPDATE admin_principals SET session_set_revision=session_set_revision+1 WHERE google_sub=?3"),
 q(`UPDATE google_login_transactions SET consumed_at_us=${NOW} WHERE state_digest=?1`),
 q("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id) SELECT lower(hex(randomblob(16))),user_id,'authentication.login_succeeded',?8,?5,'succeeded','validated_google_assertion',?5 FROM admin_principals WHERE google_sub=?3"),
 q("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id) SELECT lower(hex(randomblob(16))),user_id,'authentication.session_rotated',?8,?5,'succeeded','reauthenticated',bound_session_id FROM google_login_transactions WHERE state_digest=?1 AND purpose='reauthentication'"),
 q("DELETE FROM transaction_guards WHERE transaction_id=?8")
 ]);return token;
}
export async function finishLogin(db:SqlStore,input:LoginCommit):Promise<string>{const adapter=storage(db,input.ownerSub,input);return adapter.commitSession(await adapter.getSession());}
async function revokeCurrent(db:SqlStore,token:string,ownerSub:string):Promise<void>{
 if(token==="")return;
 if(!valid(token))throw new BrowserAuthError("unauthorized");
 const tx=crypto.randomUUID();await db.batch([
 db.prepare("INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,1").bind(tx),
 db.prepare("UPDATE admin_principals SET session_set_revision=session_set_revision+1 WHERE user_id IN(SELECT user_id FROM admin_sessions WHERE token_digest=? AND revoked_at_us IS NULL)").bind(digest(token)),
 db.prepare("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id) SELECT ?,user_id,'authentication.logout_succeeded',?,session_id,'succeeded','user_logout',session_id FROM admin_sessions WHERE token_digest=? AND revoked_at_us IS NULL").bind(crypto.randomUUID(),tx,digest(token)),
 db.prepare(`UPDATE admin_sessions SET revoked_at_us=${NOW},revocation_reason='user_logout',revision=revision+1 WHERE token_digest=? AND revoked_at_us IS NULL`).bind(digest(token)),
 db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)
 ]);
}
export async function logoutBrowser(request:Request,db:SqlStore,ownerSub:string):Promise<string>{
 if(request.headers.get("Origin")!==ADMIN_ORIGIN)throw new BrowserAuthError("invalid_origin");
 try{
  const token=await cookie.parse(request.headers.get("Cookie"));
  const row=await db.prepare(`SELECT s.session_id sessionId,s.user_id userId,s.csrf_token csrfToken,s.revision,s.created_at_us createdAtUs,s.recent_authentication_at_us recentAtUs,s.expires_at_us expiresAtUs,${NOW} nowUs,s.revoked_at_us revoked FROM admin_sessions s WHERE s.token_digest=?`).bind(token?digest(token):"").first<AdminSession&{revoked:number|null}>();
  if(row&&row.revoked===null&&row.expiresAtUs>row.nowUs)enforceUnsafe(request,row);
  const adapter=storage(db,ownerSub);return await adapter.destroySession(await adapter.getSession(request.headers.get("Cookie")));
 }catch(error){if(error instanceof BrowserAuthError)throw error;throw new BrowserAuthError(String(error).includes("constraint failed")?"logout_unavailable":"logout_outcome_unknown");}
}
