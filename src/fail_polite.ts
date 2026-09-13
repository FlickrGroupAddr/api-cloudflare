import { classifyAdd, FlickrFailure, retryDelayMs, THROTTLE_DELAY_MS, type DispatchOutcome } from "./dispatch_policy.ts";
import { preflightIsFresh } from "./dispatch_freshness.ts";
// Shared fenced attempt path. Deployment remains subject to the full release gate.
import type { SqlStore } from "./admission.ts";
import { NOW_US_SQL } from "./installations.ts";
import { claimPartition, type Lease, type LeasePolicy } from "./scheduling.ts";
export type FaultPoint = "before_membership"|"after_membership"|"membership_committed"|"before_preflight"|"after_preflight"|"preflight_committed"|"marker_committed"|"response_received"|"result_committed";
export type Outcome = DispatchOutcome;
export interface Reservation { id?:string; check(context:AttemptContext):Promise<boolean>; consume(operation:"membership"|"preflight"|"add"):void; releaseUnused():void|Promise<void>; }
export interface AttemptContext { attemptId:string;photoId:string;groupId:string; }
export interface Transport {
 membership(context:AttemptContext):Promise<boolean>; // true means exact target present; invalid response must throw
 preflight(context:AttemptContext):Promise<0|1>;
 prepareAdd(context:AttemptContext):Promise<PreparedAdd>;
}
export interface PreparedAdd {
 handoff():Promise<"ok"|number>; // already signed and materialized; no retries
 dispose():void;
}
export interface Dependencies {
 db:SqlStore; transport:Transport; monotonicUs:()=>number;
 reserve:(context:AttemptContext)=>Promise<Reservation|null>;
 fault?:(point:FaultPoint)=>Promise<void>;
 retryDelayMs?:(count:number)=>number;
 rateRetryDelayMs?:()=>Promise<number>;
 beforePreflight?:(lease:Lease)=>Promise<boolean>;
 onFlickrCode?:(code:number)=>Promise<void>;
 artifactSha2_256?:string;
}
interface Attempt extends AttemptContext { intentId:string;marked:number; }
const HEAD = `(SELECT intent_id FROM submission_intents WHERE partition_id=?1 AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1)`;
const OWNED = `p.partition_id=?1 AND p.lease_id=?2 AND p.lease_generation=CAST(?3 AS INTEGER) AND ${HEAD}=?4`;
const LIVE = `p.lease_expires_at_us>${NOW_US_SQL} AND p.invocation_deadline_at_us>${NOW_US_SQL}`;
const ENABLED = `EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*' AND enabled=1)
 AND EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='user' AND scope_id=p.user_id AND enabled=1)
 AND EXISTS(SELECT 1 FROM flickr_links WHERE user_id=p.user_id AND state='linked')`;
function batchParts(db:SqlStore,lease:Lease,attemptId:string,reservationId:string|null=null) {
 const transaction=crypto.randomUUID();
 const params=[lease.partitionId,lease.leaseId,lease.generation,lease.headId,attemptId,transaction,reservationId];
 const statement=(sql:string)=>db.prepare(`WITH input AS(SELECT ?1 p,?2 l,?3 g,?4 h,?5 a,?6 t,?7 r) `+sql).bind(...params);
 const guard=(condition:string)=>statement(`INSERT INTO transaction_guards(transaction_id,approved)
 VALUES(?6,EXISTS(SELECT 1 FROM group_partitions p WHERE ${OWNED} AND ${condition}))`);
 const done=()=>statement("DELETE FROM transaction_guards WHERE transaction_id=?6");
 return {statement,guard,done};
}
async function unfinished(db:SqlStore,lease:Lease):Promise<Attempt|null> {
 return db.prepare(`SELECT a.attempt_id attemptId,a.intent_id intentId,i.photo_id photoId,i.group_id groupId,
 EXISTS(SELECT 1 FROM attempt_dispatches d WHERE d.attempt_id=a.attempt_id) marked
 FROM submission_attempts a JOIN submission_intents i ON i.intent_id=a.intent_id
 WHERE a.intent_id=? AND NOT EXISTS(SELECT 1 FROM attempt_resolutions r WHERE r.attempt_id=a.attempt_id)
 ORDER BY a.ordinal DESC LIMIT 1`).bind(lease.headId).first<Attempt>();
}
async function begin(db:SqlStore,lease:Lease):Promise<Attempt> {
 const id=crypto.randomUUID(),b=batchParts(db,lease,id);
 const result=await db.batch([
  b.guard(`${LIVE} AND ${ENABLED}
   AND EXISTS(SELECT 1 FROM submission_intents i JOIN photo_bindings b ON b.binding_id=i.binding_id
    JOIN flickr_links l ON l.user_id=i.user_id WHERE i.intent_id=?4 AND i.state IN ('queued','retrying','throttled')
    AND l.owner_nsid=b.owner_nsid AND l.link_revision=b.link_revision AND l.state='linked'
    AND NOT EXISTS(SELECT 1 FROM submission_blocks WHERE photo_id=i.photo_id AND group_id=i.group_id))
   AND NOT EXISTS(SELECT 1 FROM submission_attempts a WHERE a.intent_id=?4
    AND NOT EXISTS(SELECT 1 FROM attempt_resolutions r WHERE r.attempt_id=a.attempt_id))`),
  b.statement(`INSERT INTO submission_attempts(attempt_id,intent_id,ordinal,lease_id,lease_generation,deployment_revision,user_revision,link_revision)
   SELECT ?5,?4,COALESCE((SELECT MAX(ordinal) FROM submission_attempts WHERE intent_id=?4),0)+1,?2,CAST(?3 AS INTEGER),
   (SELECT revision FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*'),
   (SELECT revision FROM flickr_write_gates WHERE scope='user' AND scope_id=p.user_id),
   (SELECT link_revision FROM flickr_links WHERE user_id=p.user_id) FROM group_partitions p WHERE partition_id=?1`),
  b.statement("UPDATE submission_intents SET state='attempting',next_attempt_not_before_us=NULL,state_version=state_version+1 WHERE intent_id=?4"),
  b.statement("INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id) VALUES(lower(hex(randomblob(16))),?4,'attempt_started',?5)"),
  b.statement("SELECT ?5 attemptId,?4 intentId,photo_id photoId,group_id groupId,0 marked FROM submission_intents WHERE intent_id=?4"),b.done()
 ]);
 return result[4].results[0] as unknown as Attempt;
}
async function record(db:SqlStore,lease:Lease,attempt:Attempt,kind:"membership"|"preflight"|"marker",value=0,reservationId:string|null=null):Promise<void> {
 const b=batchParts(db,lease,attempt.attemptId,reservationId);
 let condition=`${LIVE} AND ${ENABLED}
 AND EXISTS(SELECT 1 FROM submission_attempts a WHERE a.attempt_id=?5 AND a.intent_id=?4 AND a.lease_id=?2 AND a.lease_generation=CAST(?3 AS INTEGER)
  AND a.deployment_revision=(SELECT revision FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*')
  AND a.user_revision=(SELECT revision FROM flickr_write_gates WHERE scope='user' AND scope_id=p.user_id)
  AND a.link_revision=(SELECT link_revision FROM flickr_links WHERE user_id=p.user_id))
 AND NOT EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=?5)
 AND NOT EXISTS(SELECT 1 FROM attempt_dispatches WHERE attempt_id=?5)
 AND NOT EXISTS(SELECT 1 FROM submission_blocks b JOIN submission_intents i ON b.photo_id=i.photo_id AND b.group_id=i.group_id WHERE i.intent_id=?4)`;
 if(kind!=="membership") condition+=" AND EXISTS(SELECT 1 FROM attempt_membership WHERE attempt_id=?5 AND target_absent=1)";
 if(kind==="marker") condition+=" AND EXISTS(SELECT 1 FROM attempt_preflights WHERE attempt_id=?5)";
 if(reservationId!==null) condition+=` AND EXISTS(SELECT 1 FROM flickr_rate_reservations r
 JOIN flickr_rate_window w ON w.window_id=r.window_id
 WHERE r.reservation_id=?7 AND r.attempt_id=?5 AND r.released=0 AND r.expires_at_us>${NOW_US_SQL})`;
 const statements=[b.guard(condition)];
 if(kind==="membership") statements.push(b.statement(`INSERT INTO attempt_membership(attempt_id,target_absent) VALUES(?5,${value===1?1:0})`));
 if(kind==="preflight") statements.push(b.statement(`INSERT INTO attempt_preflights(attempt_id,moderated) VALUES(?5,${value===1?1:0})`));
 if(kind==="marker") {
  statements.push(b.statement("INSERT INTO attempt_dispatches(attempt_id) VALUES(?5)"));
  statements.push(b.statement("UPDATE submission_intents SET add_dispatch_count=add_dispatch_count+1,state_version=state_version+1 WHERE intent_id=?4"));
 }
 statements.push(b.statement(`INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id) VALUES(lower(hex(randomblob(16))),?4,'${kind}_committed',?5)`),b.done());
 await db.batch(statements);
}
export interface ResolutionOptions {
 code?:number; pause?:"deployment"|"user"|null; delayMs?:number; observedAgeUs?:number;
 retryDelayMs?:(count:number)=>number; artifactSha2_256?:string;
}
export async function resolveAttempt(db:SqlStore,lease:Lease,attemptId:string,outcome:Outcome,reason:string,options:ResolutionOptions={}):Promise<Outcome> {
 if(!/^[a-z][a-z0-9_]{0,95}$/.test(reason))throw new Error("invalid_resolution_reason");
 const counts=await db.prepare("SELECT safe_read_failure_count reads,add_dispatch_count adds FROM submission_intents WHERE intent_id=?")
  .bind(lease.headId).first<{reads:number;adds:number}>();
 if(!counts)throw new Error("missing_intent");
 const readFailure=reason==="safe_read_unavailable"||reason==="flickr_read_failure";
 const terminal=!["retrying","throttled"].includes(outcome);
 const blocked=outcome==="moderation_submitted"||outcome==="delivery_uncertain";
 const delay=terminal?0:outcome==="throttled"?THROTTLE_DELAY_MS:options.delayMs??
  (options.retryDelayMs??retryDelayMs)(Math.max(0,readFailure?counts.reads:counts.adds-1));
 if(!Number.isSafeInteger(delay)||delay<0||delay>THROTTLE_DELAY_MS)throw new Error("invalid_resolution_delay");
 const tx=crypto.randomUUID();
 const params=[lease.partitionId,lease.leaseId,lease.generation,lease.headId,attemptId,tx,
  outcome,reason,delay*1000,options.code??null,options.observedAgeUs??null,options.artifactSha2_256??null];
 const sql=(text:string)=>db.prepare("WITH input AS(SELECT ?1 p,?2 l,?3 g,?4 h,?5 a,?6 t,?7 o,?8 r,?9 d,?10 c,?11 m,?12 b) "+text).bind(...params);
 const statements=[sql(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?6,
  EXISTS(SELECT 1 FROM group_partitions p WHERE ${OWNED}
   AND EXISTS(SELECT 1 FROM submission_attempts WHERE attempt_id=?5 AND intent_id=?4)
   AND NOT EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=?5)))`)];
 if(blocked) statements.push(sql(`INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id)
  SELECT photo_id,group_id,CASE WHEN ?8 IN ('flickr_code_6','flickr_code_7') THEN ?8 ELSE 'delivery_uncertain' END,?5
  FROM submission_intents i WHERE intent_id=?4 AND NOT EXISTS(
   SELECT 1 FROM submission_blocks b WHERE b.photo_id=i.photo_id AND b.group_id=i.group_id)`));
 statements.push(sql("INSERT INTO attempt_resolutions(attempt_id,outcome,reason,flickr_code,observed_age_us) VALUES(?5,?7,?8,?10,?11)"));
 statements.push(sql(`UPDATE submission_intents SET state=?7,state_version=state_version+1,
  terminal_at_us=${terminal?NOW_US_SQL:"NULL"},next_attempt_not_before_us=${outcome==="retrying"?NOW_US_SQL+"+?9":"NULL"},
  add_dispatch_count=add_dispatch_count-${reason==="not_dispatched_preflight_expired"?"(SELECT COUNT(*) FROM attempt_dispatches WHERE attempt_id=?5)":"0"},
  safe_read_failure_count=${readFailure?"safe_read_failure_count+1":reason==="rate_capacity_unavailable"?"safe_read_failure_count":"0"} WHERE intent_id=?4`));
 statements.push(sql("INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id) VALUES(lower(hex(randomblob(16))),?4,?8,?5)"));
 if(reason==="flickr_code_6")statements.push(sql(`INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id)
  SELECT lower(hex(randomblob(16))),?4,'moderation_changed_or_inconsistent',?5 FROM attempt_preflights WHERE attempt_id=?5 AND moderated=0`));
 if(outcome==="throttled")statements.push(sql(`UPDATE group_partitions SET next_probe_not_before_us=${NOW_US_SQL}+?9 WHERE partition_id=?1`));
 const pause=options.pause??(reason==="unknown_code"?"deployment":null);
 if(pause) {
  const target=pause==="deployment"?"scope='deployment' AND scope_id='*'":"scope='user' AND scope_id=(SELECT user_id FROM group_partitions WHERE partition_id=?1)";
  statements.push(sql(`INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason,flickr_code,attempt_id,artifact_sha2_256)
   SELECT lower(hex(randomblob(16))),scope,scope_id,revision+1,?8,?10,?5,?12 FROM flickr_write_gates WHERE ${target} AND enabled=1`));
  statements.push(sql(`UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE ${target} AND enabled=1`));
 }
 statements.push(sql(`UPDATE group_partitions SET lease_id=NULL,lease_started_at_us=NULL,lease_expires_at_us=NULL,invocation_deadline_at_us=NULL,
  next_work_not_before_us=(SELECT CASE WHEN state='throttled' THEN group_partitions.next_probe_not_before_us ELSE COALESCE(next_attempt_not_before_us,created_at_us) END
   FROM submission_intents WHERE intent_id=${HEAD}),wake_revision=wake_revision+1 WHERE partition_id=?1`));
 statements.push(sql("DELETE FROM transaction_guards WHERE transaction_id=?6"));
 await db.batch(statements);return outcome;
}
export async function runPartition(deps:Dependencies,partitionId:string,source:string,revision:string|null=null,policy?:LeasePolicy):Promise<string> {
 const {db}=deps,lease=await claimPartition(db,partitionId,source+"-"+crypto.randomUUID(),revision,policy);
 if(!lease) return "no_claim";
 const old=await unfinished(db,lease);
 if(old) {
  await resolveAttempt(db,lease,old.attemptId,old.marked?"delivery_uncertain":"retrying",old.marked?"unresolved_dispatch":"abandoned_before_dispatch");
  return "recovered"; // Recovery never hands off POST. Later work begins a fresh attempt.
 }
 const attempt=await begin(db,lease),reservation=await deps.reserve(attempt);
 if(!reservation) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","rate_capacity_unavailable",{delayMs:await deps.rateRetryDelayMs?.()??1000});return "deferred";}
 const fault=async(point:FaultPoint)=>{await deps.fault?.(point);};
 const unavailable=async(error?:unknown)=>{
  const code=error instanceof FlickrFailure?error.code:undefined;
  const pause=code===undefined?null:classifyAdd(code).pause;
  const resolved=await resolveAttempt(db,lease,attempt.attemptId,"retrying",code===undefined?"safe_read_unavailable":"flickr_read_failure",
   {code,pause,retryDelayMs:deps.retryDelayMs,artifactSha2_256:deps.artifactSha2_256});
  if(code!==undefined)await deps.onFlickrCode?.(code);
  return resolved==="needs_attention"?resolved:"deferred";
 };
 const rateUnavailable=async()=>{
  await resolveAttempt(db,lease,attempt.attemptId,"retrying","rate_capacity_unavailable",{delayMs:await deps.rateRetryDelayMs?.()??1000});return "deferred";
 };
 try {
  await fault("before_membership");
  if(!await reservation.check(attempt))return await rateUnavailable();
  let present:boolean;
  try {reservation.consume("membership");present=await deps.transport.membership(attempt);}
  catch(error) {return await unavailable(error);}
  await fault("after_membership");await record(db,lease,attempt,"membership",present?0:1);await fault("membership_committed");
  if(present) {await resolveAttempt(db,lease,attempt.attemptId,"added","pre_add_membership_observation");return "added";}
  await fault("before_preflight");
  if(!await reservation.check(attempt))return await rateUnavailable();
  if(deps.beforePreflight&&!await deps.beforePreflight(lease))return await unavailable();
  let moderated:0|1,received:number;
  try {reservation.consume("preflight");moderated=await deps.transport.preflight(attempt);received=deps.monotonicUs();}
  catch(error) {return await unavailable(error);}
  await fault("after_preflight");await record(db,lease,attempt,"preflight",moderated);await fault("preflight_committed");
  const fresh=()=>preflightIsFresh(received,deps.monotonicUs());
  if(!fresh()) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","not_dispatched_preflight_expired");return "expired";}
  // Resolve credentials, sign and materialize before the last marker I/O (ADR 0056).
  let prepared:PreparedAdd;
  try {prepared=await deps.transport.prepareAdd(attempt);}
  catch(error) {return await unavailable(error);}
  try {
  const handoff=()=>{reservation.consume("add");return prepared.handoff();};
  if(!fresh()) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","not_dispatched_preflight_expired");return "expired";}
  await record(db,lease,attempt,"marker",0,reservation.id??null);
  if(deps.fault) await deps.fault("marker_committed");
  // No await between this live zero-handoff check and the call into the adapter.
  if(!fresh()) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","not_dispatched_preflight_expired");return "expired";}
  let result:"ok"|number;
  try {result=await handoff();}
  catch {await resolveAttempt(db,lease,attempt.attemptId,"delivery_uncertain","unresolved_dispatch");return "uncertain";}
  await fault("response_received");
  const classified=classifyAdd(result);
  const outcome=await resolveAttempt(db,lease,attempt.attemptId,classified.outcome,classified.reason,
   {code:result==="ok"?undefined:result,pause:classified.pause,retryDelayMs:deps.retryDelayMs,artifactSha2_256:deps.artifactSha2_256});
  await fault("result_committed");
  if(result!=="ok")await deps.onFlickrCode?.(result);
  return outcome;
  } finally {prepared.dispose();}
 } finally {await reservation.releaseUnused();}
}
