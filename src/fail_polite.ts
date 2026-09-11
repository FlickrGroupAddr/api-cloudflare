import { preflightIsFresh } from "./dispatch_freshness.ts";
// Internal candidate adapter. No production route or real Flickr transport is enabled.
import type { SqlStore } from "./admission.ts";
import { NOW_US_SQL } from "./installations.ts";
import { claimPartition, type Lease, type LeasePolicy } from "./scheduling.ts";
export type FaultPoint = "before_membership"|"after_membership"|"membership_committed"|"before_preflight"|"after_preflight"|"preflight_committed"|"marker_committed"|"response_received"|"result_committed";
export type Outcome = "added"|"moderation_submitted"|"delivery_uncertain"|"retrying";
export interface Reservation { consume(operation:"membership"|"preflight"|"add"):void; releaseUnused():void; }
export interface AttemptContext { attemptId:string;photoId:string;groupId:string; }
export interface Transport {
 membership(context:AttemptContext):Promise<boolean>; // true means exact target present; invalid response must throw
 preflight(context:AttemptContext):Promise<0|1>;
 add(context:AttemptContext):Promise<"ok"|number>; // exception or unrecognized response is ambiguous
}
export interface Dependencies {
 db:SqlStore; transport:Transport; monotonicUs:()=>number;
 reserve:(context:AttemptContext)=>Promise<Reservation|null>;
 fault?:(point:FaultPoint)=>Promise<void>;
}
interface Attempt extends AttemptContext { intentId:string;marked:number; }
const HEAD = `(SELECT intent_id FROM submission_intents WHERE partition_id=?1 AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1)`;
const OWNED = `p.partition_id=?1 AND p.lease_id=?2 AND p.lease_generation=CAST(?3 AS INTEGER) AND ${HEAD}=?4`;
const LIVE = `p.lease_expires_at_us>${NOW_US_SQL} AND p.invocation_deadline_at_us>${NOW_US_SQL}`;
const ENABLED = `EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*' AND enabled=1)
 AND EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='user' AND scope_id=p.user_id AND enabled=1)
 AND EXISTS(SELECT 1 FROM flickr_links WHERE user_id=p.user_id AND state='linked')`;
function batchParts(db:SqlStore,lease:Lease,attemptId:string) {
 const transaction=crypto.randomUUID();
 const params=[lease.partitionId,lease.leaseId,lease.generation,lease.headId,attemptId,transaction];
 const statement=(sql:string)=>db.prepare(`WITH input AS(SELECT ?1 p,?2 l,?3 g,?4 h,?5 a,?6 t) `+sql).bind(...params);
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
async function record(db:SqlStore,lease:Lease,attempt:Attempt,kind:"membership"|"preflight"|"marker",value=0):Promise<void> {
 const b=batchParts(db,lease,attempt.attemptId);
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
type Reason="pre_add_membership_observation"|"flickr_added"|"flickr_code_3"|"flickr_code_6"|"flickr_code_7"|"unknown_code"|"unresolved_dispatch"|"safe_read_unavailable"|"flickr_code_105"|"flickr_code_106"|"abandoned_before_dispatch"|"not_dispatched_preflight_expired";
export async function resolveAttempt(db:SqlStore,lease:Lease,attemptId:string,outcome:Outcome,reason:Reason):Promise<void> {
 const b=batchParts(db,lease,attemptId),terminal=outcome!=="retrying";
 const blocked=outcome==="moderation_submitted"||outcome==="delivery_uncertain";
 const blockReason=reason==="flickr_code_6"||reason==="flickr_code_7"?reason:"delivery_uncertain";
 // Completion is allowed after expiry only if no successor has changed ID/generation.
 const statements=[b.guard(`EXISTS(SELECT 1 FROM submission_attempts WHERE attempt_id=?5 AND intent_id=?4)
  AND NOT EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=?5)` )];
 if(blocked) statements.push(b.statement(`INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id)
  SELECT photo_id,group_id,'${blockReason}',?5 FROM submission_intents i WHERE intent_id=?4
  AND NOT EXISTS(SELECT 1 FROM submission_blocks b WHERE b.photo_id=i.photo_id AND b.group_id=i.group_id)`));
 statements.push(b.statement(`INSERT INTO attempt_resolutions(attempt_id,outcome,reason) VALUES(?5,'${outcome}','${reason}')`));
 statements.push(b.statement(`UPDATE submission_intents SET state='${outcome}',state_version=state_version+1,
  terminal_at_us=${terminal?NOW_US_SQL:"NULL"},next_attempt_not_before_us=${terminal?"NULL":NOW_US_SQL+"+1000000"},
  safe_read_failure_count=safe_read_failure_count+${reason==="safe_read_unavailable"?1:0} WHERE intent_id=?4`));
 statements.push(b.statement(`INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id) VALUES(lower(hex(randomblob(16))),?4,'${reason}',?5)`));
 statements.push(b.statement(`UPDATE group_partitions SET lease_id=NULL,lease_started_at_us=NULL,lease_expires_at_us=NULL,invocation_deadline_at_us=NULL,
  next_work_not_before_us=(SELECT COALESCE(next_attempt_not_before_us,created_at_us) FROM submission_intents WHERE intent_id=${HEAD}),wake_revision=wake_revision+1 WHERE partition_id=?1`));
 if(reason==="unknown_code") statements.push(b.statement("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment' AND scope_id='*'"));
 statements.push(b.done());
 await db.batch(statements);
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
 if(!reservation) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","safe_read_unavailable");return "deferred";}
 const fault=async(point:FaultPoint)=>{await deps.fault?.(point);};
 try {
  await fault("before_membership");
  let present:boolean;
  try {reservation.consume("membership");present=await deps.transport.membership(attempt);}
  catch {await resolveAttempt(db,lease,attempt.attemptId,"retrying","safe_read_unavailable");return "deferred";}
  await fault("after_membership");await record(db,lease,attempt,"membership",present?0:1);await fault("membership_committed");
  if(present) {await resolveAttempt(db,lease,attempt.attemptId,"added","pre_add_membership_observation");return "added";}
  await fault("before_preflight");
  let moderated:0|1,received:number;
  try {reservation.consume("preflight");moderated=await deps.transport.preflight(attempt);received=deps.monotonicUs();}
  catch {await resolveAttempt(db,lease,attempt.attemptId,"retrying","safe_read_unavailable");return "deferred";}
  await fault("after_preflight");await record(db,lease,attempt,"preflight",moderated);await fault("preflight_committed");
  const fresh=()=>preflightIsFresh(received,deps.monotonicUs());
  if(!fresh()) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","not_dispatched_preflight_expired");return "expired";}
  await record(db,lease,attempt,"marker");await fault("marker_committed");
  // No await between this live zero-handoff check and the call into the adapter.
  if(!fresh()) {await resolveAttempt(db,lease,attempt.attemptId,"retrying","not_dispatched_preflight_expired");return "expired";}
  let result:"ok"|number;
  try {reservation.consume("add");result=await deps.transport.add(attempt);}
  catch {await resolveAttempt(db,lease,attempt.attemptId,"delivery_uncertain","unresolved_dispatch");return "uncertain";}
  await fault("response_received");
  let outcome:Outcome,reason:Reason;
  if(result==="ok"||result===3) {outcome="added";reason=result==="ok"?"flickr_added":"flickr_code_3";}
  else if(result===6||result===7) {outcome="moderation_submitted";reason=result===6?"flickr_code_6":"flickr_code_7";}
  else if(result===105||result===106) {outcome="retrying";reason=result===105?"flickr_code_105":"flickr_code_106";}
  else {outcome="delivery_uncertain";reason="unknown_code";}
  await resolveAttempt(db,lease,attempt.attemptId,outcome,reason);await fault("result_committed");return outcome;
 } finally {reservation.releaseUnused();}
}
