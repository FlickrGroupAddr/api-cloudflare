import ipaddr from "ipaddr.js";
import {createHmac,createHash} from "node:crypto";
import {NOW_US_SQL as NOW} from "./installations.ts";
import type {SqlStore} from "./admission.ts";
export class AuthAdmissionError extends Error {}
export function sourceKey(address:string,key:string):string {
 if(!key || key.length<32 || !ipaddr.isValid(address))throw new AuthAdmissionError("admission_unavailable");
 const parsed=ipaddr.process(address),bytes=parsed.toByteArray();
 const normalized=parsed.kind()==="ipv6"?bytes.slice(0,8):bytes;
 return createHmac("sha256",key).update(parsed.kind()+":"+normalized.join(".")).digest("hex");
}
// Charge possible invalid work while it is in flight. Failure/response loss cannot refund it.
export async function admitAuthentication(db:SqlStore,source:string,route:"login"|"start"|"callback"):Promise<string> {
 const id=crypto.randomUUID(),window=600_000_000;
 const bucket=route==="start"?createHash("sha256").update("login-start:"+source).digest("hex"):source;
 try {
  await db.batch([
   db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,
    (SELECT COUNT(*) FROM auth_cost_events WHERE created_at_us>${NOW}-? AND invalid_or_inflight=1)<120
    AND (SELECT COUNT(*) FROM auth_cost_events WHERE source_key=? AND created_at_us>${NOW}-? AND invalid_or_inflight=1)<20
    AND (?='callback' OR ((SELECT COUNT(*) FROM auth_cost_events WHERE route=? AND created_at_us>${NOW}-?)<30
     AND COALESCE((SELECT MIN(2,tokens+MAX(0,${NOW}-updated_at_us)/120000000.0) FROM auth_source_buckets WHERE source_key=?),2)>=1))`).bind(id,window,source,window,route,route,window,bucket),
   db.prepare(`INSERT INTO auth_source_buckets(source_key,tokens,updated_at_us) SELECT ?,1,${NOW} WHERE ?<>'callback'
    ON CONFLICT(source_key) DO UPDATE SET tokens=MIN(2,auth_source_buckets.tokens+MAX(0,${NOW}-auth_source_buckets.updated_at_us)/120000000.0)-1,updated_at_us=${NOW}`).bind(bucket,route),
   db.prepare(`INSERT INTO auth_cost_events(event_id,source_key,route,created_at_us,invalid_or_inflight) VALUES(?,?,?,${NOW},?)`).bind(id,source,route,route==="start"?0:1),
   db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(id)
  ]);
 }catch(error){if(String(error).includes("CHECK constraint failed"))throw new AuthAdmissionError("rate_limited");throw new AuthAdmissionError("admission_unavailable");}
 return id;
}
export async function finishAuthentication(db:SqlStore,id:string):Promise<void> {
 await db.prepare("UPDATE auth_cost_events SET invalid_or_inflight=0 WHERE event_id=?").bind(id).run();
}
export async function cleanupAuthentication(db:SqlStore):Promise<void> {
 await db.batch([
 db.prepare(`DELETE FROM auth_cost_events WHERE event_id IN(SELECT event_id FROM auth_cost_events WHERE created_at_us<=${NOW}-86400000000 LIMIT 500)`),
 db.prepare(`DELETE FROM auth_source_buckets WHERE source_key IN(SELECT source_key FROM auth_source_buckets WHERE updated_at_us<=${NOW}-86400000000 LIMIT 500)`),
 db.prepare(`DELETE FROM google_login_transactions WHERE state_digest IN(SELECT state_digest FROM google_login_transactions WHERE COALESCE(consumed_at_us,expires_at_us)<${NOW}-86400000000 LIMIT 500)`),
 db.prepare(`DELETE FROM admin_sessions WHERE session_id IN(SELECT session_id FROM admin_sessions WHERE MAX(expires_at_us,COALESCE(revoked_at_us,0))<${NOW}-2592000000000 AND NOT EXISTS(SELECT 1 FROM google_login_transactions t WHERE t.bound_session_id=admin_sessions.session_id) LIMIT 500)`)
 ]);
}
