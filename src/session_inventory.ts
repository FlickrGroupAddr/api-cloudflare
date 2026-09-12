import type {SqlStore} from "./admission.ts";
import {NOW_US_SQL as NOW} from "./installations.ts";
import {BrowserAuthError,type AdminSession} from "./browser_sessions.ts";
const timestamp=(value:number)=>new Date(value/1000).toISOString().replace("Z","000Z");
export async function sessionInventory(db:SqlStore,current:AdminSession,pageSize=50,pageToken:string|null=null):Promise<unknown>{
 if(!Number.isInteger(pageSize)||pageSize<1||pageSize>50)throw new BrowserAuthError("invalid_request");
 let cursor:{created:number;id:string}|null=null;
 if(pageToken){try{if(pageToken.length>512)throw new Error();cursor=JSON.parse(atob(pageToken.replace(/-/g,"+").replace(/_/g,"/")));if(!cursor||!Number.isSafeInteger(cursor.created)||cursor.created<0||typeof cursor.id!=="string"||cursor.id.length>128)throw new Error();}catch{throw new BrowserAuthError("invalid_request");}}
 const results=await db.batch([
 db.prepare("SELECT session_set_revision revision FROM admin_principals WHERE user_id=?").bind(current.userId),
 db.prepare(`SELECT session_id,revision,created_at_us,recent_authentication_at_us,last_activity_at_us,expires_at_us,revoked_at_us,CASE WHEN revoked_at_us IS NOT NULL THEN 'revoked' WHEN expires_at_us<=${NOW} THEN 'expired' ELSE 'active' END state FROM admin_sessions WHERE user_id=? AND (? IS NULL OR created_at_us<? OR (created_at_us=? AND session_id<?)) ORDER BY created_at_us DESC,session_id DESC LIMIT ?`).bind(current.userId,cursor?.created??null,cursor?.created??null,cursor?.created??null,cursor?.id??null,pageSize+1)
 ]);
 const rows=results[1].results as Record<string,unknown>[],hasMore=rows.length>pageSize;rows.splice(pageSize);const last=rows.at(-1);
 const next=hasMore&&last?btoa(JSON.stringify({created:last.created_at_us,id:last.session_id})).replace(/=/g,"").replace(/\+/g,"-").replace(/\//g,"_"):null;
 return {schemaVersion:1,sessionSetRevision:(results[0].results[0] as {revision:number}).revision,sessions:rows.map(r=>({sessionId:r.session_id,revision:r.revision,createdAt:timestamp(Number(r.created_at_us)),recentAuthenticationAt:timestamp(Number(r.recent_authentication_at_us)),lastActivityAt:timestamp(Number(r.last_activity_at_us)),expiresAt:timestamp(Number(r.expires_at_us)),state:r.state,revokedAt:r.revoked_at_us===null?null:timestamp(Number(r.revoked_at_us)),isCurrent:r.session_id===current.sessionId})),nextPageToken:next};
}
export async function revokeSession(db:SqlStore,current:AdminSession,target:string,revision:number):Promise<void>{
 if(target===current.sessionId)throw new BrowserAuthError("current_session_requires_logout");
 if(!Number.isSafeInteger(revision)||revision<1||target.length>128)throw new BrowserAuthError("invalid_request");
 const tx=crypto.randomUUID();
 try{await db.batch([
 db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,NOT EXISTS(SELECT 1 FROM admin_sessions WHERE user_id=? AND session_id=? AND revoked_at_us IS NULL AND expires_at_us>${NOW} AND revision<>?)`).bind(tx,current.userId,target,revision),
 db.prepare(`UPDATE admin_principals SET session_set_revision=session_set_revision+1 WHERE user_id=? AND EXISTS(SELECT 1 FROM admin_sessions WHERE user_id=? AND session_id=? AND revoked_at_us IS NULL AND expires_at_us>${NOW})`).bind(current.userId,current.userId,target),
 db.prepare(`INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id) SELECT ?,user_id,'authentication.session_revoked',?,?,'succeeded','user_revoked',session_id FROM admin_sessions WHERE user_id=? AND session_id=? AND revoked_at_us IS NULL AND expires_at_us>${NOW}`).bind(crypto.randomUUID(),tx,current.sessionId,current.userId,target),
 db.prepare(`UPDATE admin_sessions SET revoked_at_us=${NOW},revocation_reason='user_revoked',revision=revision+1 WHERE user_id=? AND session_id=? AND revoked_at_us IS NULL AND expires_at_us>${NOW}`).bind(current.userId,target),
 db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)]);}catch(error){throw new BrowserAuthError(String(error).includes("CHECK constraint failed")?"stale_session_revision":"service_unavailable");}
}
export async function revokeOtherSessions(db:SqlStore,current:AdminSession,revision:number,count:number):Promise<void>{
 if(!Number.isSafeInteger(revision)||revision<1||!Number.isSafeInteger(count)||count<0)throw new BrowserAuthError("invalid_request");
 const tx=crypto.randomUUID();
 try{await db.batch([
 db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM admin_principals WHERE user_id=? AND session_set_revision=?) AND (SELECT COUNT(*) FROM admin_sessions WHERE user_id=? AND session_id<>? AND revoked_at_us IS NULL AND expires_at_us>${NOW})=?`).bind(tx,current.userId,revision,current.userId,current.sessionId,count),
 db.prepare("UPDATE admin_principals SET session_set_revision=session_set_revision+1 WHERE user_id=? AND ?>0").bind(current.userId,count),
 db.prepare("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id) SELECT ?,?,'authentication.other_sessions_revoked',?,?,'succeeded','user_revoked_others',? WHERE ?>0").bind(crypto.randomUUID(),current.userId,tx,current.sessionId,current.userId,count),
 db.prepare(`UPDATE admin_sessions SET revoked_at_us=${NOW},revocation_reason='user_revoked_others',revision=revision+1 WHERE user_id=? AND session_id<>? AND revoked_at_us IS NULL AND expires_at_us>${NOW}`).bind(current.userId,current.sessionId),
 db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)]);}catch(error){throw new BrowserAuthError(String(error).includes("CHECK constraint failed")?"stale_session_set":"service_unavailable");}
}
