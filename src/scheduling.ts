import { NOW_US_SQL } from "./installations.ts";
import type { SqlStore, WakeHint } from "./admission.ts";
export const DEFAULT_LEASE_POLICY = { leaseMs:60_000, invocationMs:45_000 } as const;
export interface LeasePolicy { leaseMs:number; invocationMs:number; }
export interface Lease { partitionId:string; leaseId:string; generation:string; headId:string; expiresUs:string; invocationId:string; }
const HEAD = `(SELECT intent_id FROM submission_intents WHERE partition_id=group_partitions.partition_id
 AND active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1)`;
const GATES = `EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*' AND enabled=1)
 AND EXISTS(SELECT 1 FROM flickr_write_gates WHERE scope='user' AND scope_id=group_partitions.user_id AND enabled=1)
 AND EXISTS(SELECT 1 FROM flickr_links WHERE user_id=group_partitions.user_id AND state='linked')`;
const ELIGIBLE = `lease_generation<9223372036854775807 AND next_work_not_before_us IS NOT NULL AND next_work_not_before_us<=${NOW_US_SQL}
 AND (lease_id IS NULL OR lease_expires_at_us<=${NOW_US_SQL}) AND ${GATES}
 AND EXISTS(SELECT 1 FROM submission_intents h WHERE h.intent_id=${HEAD}
  AND (h.state='queued' OR (h.state='retrying' AND h.next_attempt_not_before_us<=${NOW_US_SQL})
   OR (h.state='throttled' AND group_partitions.next_probe_not_before_us<=${NOW_US_SQL}))
  AND NOT EXISTS(SELECT 1 FROM submission_blocks b WHERE b.photo_id=h.photo_id AND b.group_id=h.group_id))`;
function policy(value:LeasePolicy): void {
 if(!Number.isSafeInteger(value.leaseMs) || value.leaseMs<1 || value.leaseMs>60_000 ||
 !Number.isSafeInteger(value.invocationMs) || value.invocationMs<1 || value.invocationMs>45_000) throw new Error("invalid_lease_policy");
}
export async function claimPartition(db:SqlStore, partitionId:string, invocationId:string,
 expectedWakeRevision:string|null=null, config:LeasePolicy=DEFAULT_LEASE_POLICY): Promise<Lease|null> {
 policy(config);
 if(expectedWakeRevision!==null && (typeof expectedWakeRevision!=="string" || !/^(0|[1-9][0-9]*)$/.test(expectedWakeRevision) || BigInt(expectedWakeRevision)>9223372036854775807n)) return null;
 const leaseId=crypto.randomUUID();
 const results=await db.batch([
  db.prepare(`UPDATE group_partitions SET lease_generation=lease_generation+1,lease_id=?,
   lease_started_at_us=${NOW_US_SQL},lease_expires_at_us=${NOW_US_SQL}+?,
   invocation_deadline_at_us=${NOW_US_SQL}+?,last_claim_at_us=${NOW_US_SQL}
   WHERE partition_id=? AND (? IS NULL OR wake_revision=CAST(? AS INTEGER)) AND ${ELIGIBLE}
   RETURNING partition_id AS partitionId,lease_id AS leaseId,CAST(lease_generation AS TEXT) AS generation,
   CAST(lease_expires_at_us AS TEXT) AS expiresUs,${HEAD} AS headId`).bind(
    leaseId,config.leaseMs*1000,config.invocationMs*1000,partitionId,expectedWakeRevision,expectedWakeRevision),
  db.prepare(`INSERT INTO partition_lease_events(event_id,partition_id,lease_id,lease_generation,kind,invocation_id)
   SELECT lower(hex(randomblob(16))),partition_id,lease_id,lease_generation,'claim',?
   FROM group_partitions WHERE partition_id=? AND lease_id=?`).bind(invocationId,partitionId,leaseId),
 ]);
 const row=results[0].results[0] as unknown as Omit<Lease,"invocationId">|undefined;
 return row?{...row,invocationId}:null;
}
const OWNED = `partition_id=?1 AND lease_id=?2 AND lease_generation=CAST(?3 AS INTEGER)`;
async function changeLease(db:SqlStore, lease:Lease, kind:"renew"|"release"|"defer", amountMs=0): Promise<boolean> {
 if(typeof lease.generation!=="string" || !/^[1-9][0-9]*$/.test(lease.generation) || BigInt(lease.generation)>9223372036854775807n) return false;
 const transactionId=crypto.randomUUID();
 const params=[lease.partitionId,lease.leaseId,lease.generation,lease.headId,transactionId,amountMs*1000,lease.invocationId];
 const prefix=`WITH input AS(SELECT ?1 p,?2 l,?3 g,?4 h,?5 t,?6 a,?7 i) `;
 const sql=(text:string)=>db.prepare(prefix+text).bind(...params);
 const live=kind==="release"?"":` AND lease_expires_at_us>${NOW_US_SQL} AND invocation_deadline_at_us>${NOW_US_SQL}`;
 const head=kind==="defer"?` AND ${HEAD}=?4 AND EXISTS(SELECT 1 FROM submission_intents WHERE intent_id=?4 AND state IN ('queued','retrying'))`:"";
 const statements=[sql(`INSERT INTO transaction_guards(transaction_id,approved)
  VALUES(?5,EXISTS(SELECT 1 FROM group_partitions WHERE ${OWNED}${live}${head}))`)];
 if(kind==="defer") {
  statements.push(sql(`UPDATE submission_intents SET state='retrying',state_version=state_version+1,
   next_attempt_not_before_us=(SELECT now_us+?6 FROM transaction_guards WHERE transaction_id=?5) WHERE intent_id=?4`));
  statements.push(sql(`INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id)
   VALUES(lower(hex(randomblob(16))),?4,'safe_no_dispatch_deferral',?7)`));
 }
 statements.push(sql(`INSERT INTO partition_lease_events(event_id,partition_id,lease_id,lease_generation,kind,invocation_id)
  VALUES(lower(hex(randomblob(16))),?1,?2,CAST(?3 AS INTEGER),'${kind}',?7)`));
 if(kind==="renew") statements.push(sql(`UPDATE group_partitions
  SET lease_expires_at_us=(SELECT now_us+?6 FROM transaction_guards WHERE transaction_id=?5) WHERE ${OWNED}`));
 else statements.push(sql(`UPDATE group_partitions SET lease_id=NULL,lease_expires_at_us=NULL,
  lease_started_at_us=NULL,invocation_deadline_at_us=NULL
  ${kind==="defer"?",next_work_not_before_us=(SELECT next_attempt_not_before_us FROM submission_intents WHERE intent_id=?4),wake_revision=wake_revision+1":""}
  WHERE ${OWNED}`));
 statements.push(sql(`DELETE FROM transaction_guards WHERE transaction_id=?5`));
 try { await db.batch(statements); return true; } catch { return false; }
 // False is unconfirmed, including a dependency error; no mutation is replayed.
}
export function renewLease(db:SqlStore,lease:Lease,config:LeasePolicy=DEFAULT_LEASE_POLICY):Promise<boolean> {
 policy(config); return changeLease(db,lease,"renew",config.leaseMs);
}
export function releaseLease(db:SqlStore,lease:Lease):Promise<boolean> { return changeLease(db,lease,"release"); }
// Safe queued/read-only deferral only. Attempt/dispatch recovery belongs to the fail-polite adapter.
export function deferHead(db:SqlStore,lease:Lease,delayMs:number):Promise<boolean> {
 if(!Number.isSafeInteger(delayMs) || delayMs<1 || delayMs>86_400_000) throw new Error("invalid_due_delay");
 return changeLease(db,lease,"defer",delayMs);
}
export async function duePartitions(db:SqlStore,limit=64):Promise<WakeHint[]> {
 if(!Number.isInteger(limit) || limit<1 || limit>64) throw new Error("invalid_sweep_bound");
 return (await db.prepare(`SELECT partition_id AS partitionId,CAST(wake_revision AS TEXT) AS wakeRevision
  FROM group_partitions WHERE ${ELIGIBLE} ORDER BY next_work_not_before_us,COALESCE(last_claim_at_us,0),partition_id LIMIT ?`).bind(limit).all<WakeHint>()).results;
}
export interface ScheduleView { partitionId:string; wakeRevision:string; dueUs:string|null; leaseId:string|null;
 generation:string; leaseExpiresUs:string|null; invocationDeadlineUs:string|null; nowUs:string; wakeAfterUs:string|null; gatesEnabled:number; headId:string|null; }
export async function scheduleView(db:SqlStore,partitionId:string):Promise<ScheduleView|null> {
 return db.prepare(`SELECT partition_id AS partitionId,CAST(wake_revision AS TEXT) AS wakeRevision,
 CAST(next_work_not_before_us AS TEXT) AS dueUs,lease_id AS leaseId,CAST(lease_generation AS TEXT) AS generation,
 CAST(lease_expires_at_us AS TEXT) AS leaseExpiresUs,CAST(invocation_deadline_at_us AS TEXT) AS invocationDeadlineUs,CAST(${NOW_US_SQL} AS TEXT) AS nowUs,
 CAST(CASE WHEN lease_id IS NOT NULL AND lease_expires_at_us>${NOW_US_SQL} THEN lease_expires_at_us ELSE next_work_not_before_us END AS TEXT) AS wakeAfterUs,
 (${GATES}) AS gatesEnabled,${HEAD} AS headId FROM group_partitions WHERE partition_id=?`).bind(partitionId).first<ScheduleView>();
}
