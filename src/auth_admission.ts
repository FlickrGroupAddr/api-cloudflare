import ipaddr from "ipaddr.js";
import {createHmac,createHash} from "node:crypto";
import type {SqlStore} from "./admission.ts";
import {beginQuotaClock,authenticationCreditStatements,finishQuotaClock,quotaCreditFailure} from "./quota_credit.ts";
export class AuthAdmissionError extends Error {}
export function sourceKey(address:string,key:string):string {
 if(!key || key.length<32 || !ipaddr.isValid(address))throw new AuthAdmissionError("admission_unavailable");
 const parsed=ipaddr.process(address),bytes=parsed.toByteArray();
 const normalized=parsed.kind()==="ipv6"?bytes.slice(0,8):bytes;
 return createHmac("sha256",key).update(parsed.kind()+":"+normalized.join(".")).digest("hex");
}
// Prospective ADR0065 source: requires the reviewed integer schema transition
// before release. Historical REAL schemas deliberately fail closed.
// Charge possible invalid work while it is in flight. Failure/response loss cannot refund it.
export async function admitAuthentication(db:SqlStore,source:string,route:"login"|"start"|"callback"):Promise<string> {
 const id=crypto.randomUUID(),window=600_000_000;
 const bucket=route==="start"?createHash("sha256").update("login-start:"+source).digest("hex"):source;
 const clock="(SELECT now_us FROM quota_credit_clocks WHERE batch_id=?1)";
 try {
  await db.batch([
   beginQuotaClock(db,id),
   // Callback traffic shares invalid/inflight limits but never spends source
   // credits or the login/start deployment windows. The sampled clock is still
   // validated by its invariant constraint before any window arithmetic.
   ...(route==="callback"?[db.prepare("INSERT INTO quota_credit_guards(batch_id,kind,invariant_ok,admitted) VALUES(?,'auth',1,1)").bind(id)]:authenticationCreditStatements(db,id,bucket)),
   db.prepare(`UPDATE quota_credit_guards SET admitted=
    (SELECT COUNT(*) FROM auth_cost_events WHERE created_at_us>${clock}-?2 AND invalid_or_inflight=1)<120
    AND (SELECT COUNT(*) FROM auth_cost_events WHERE source_key=?3 AND created_at_us>${clock}-?2 AND invalid_or_inflight=1)<20
    AND (?4='callback' OR (SELECT COUNT(*) FROM auth_cost_events WHERE route=?4 AND created_at_us>${clock}-?2)<30)
    WHERE batch_id=?1 AND kind='auth'`).bind(id,window,source,route),
   db.prepare(`INSERT INTO auth_cost_events(event_id,source_key,route,created_at_us,invalid_or_inflight)
    SELECT ?1,?2,?3,now_us,?4 FROM quota_credit_clocks WHERE batch_id=?1`).bind(id,source,route,route==="start"?0:1),
   ...finishQuotaClock(db,id)
  ]);
 }catch(error){throw new AuthAdmissionError(quotaCreditFailure(error)==="exhausted"?"rate_limited":"admission_unavailable");}
 return id;
}
export async function finishAuthentication(db:SqlStore,id:string):Promise<void> {
 await db.prepare("UPDATE auth_cost_events SET invalid_or_inflight=0 WHERE event_id=?").bind(id).run();
}
export async function cleanupAuthentication(db:SqlStore):Promise<void> {
 const id=crypto.randomUUID(),clock="(SELECT now_us FROM quota_credit_clocks WHERE batch_id=?)";
 await db.batch([
 beginQuotaClock(db,id),
 db.prepare(`DELETE FROM auth_cost_events WHERE event_id IN(SELECT event_id FROM auth_cost_events WHERE created_at_us<=${clock}-86400000000 LIMIT 500)`).bind(id),
 db.prepare(`DELETE FROM auth_source_buckets WHERE source_key IN(SELECT source_key FROM auth_source_buckets WHERE updated_at_us<=${clock}-86400000000 LIMIT 500)`).bind(id),
 db.prepare(`DELETE FROM google_login_transactions WHERE state_digest IN(SELECT state_digest FROM google_login_transactions WHERE COALESCE(consumed_at_us,expires_at_us)<${clock}-86400000000 LIMIT 500)`).bind(id),
 db.prepare(`DELETE FROM admin_sessions WHERE session_id IN(SELECT session_id FROM admin_sessions WHERE MAX(expires_at_us,COALESCE(revoked_at_us,0))<${clock}-2592000000000 AND NOT EXISTS(SELECT 1 FROM google_login_transactions t WHERE t.bound_session_id=admin_sessions.session_id) LIMIT 500)`).bind(id),
 ...finishQuotaClock(db,id)
 ]);
}
