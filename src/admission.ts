import { NOW_US_SQL } from "./installations.ts";
export type SqlStore = Pick<D1Database,"prepare"|"batch">;
export const MAX_GROUP_IDS = 60;
export const EXISTING_PROOF_MAX_AGE_US = 15_000_000;
export interface AdmissionRequest {
 schemaVersion: 2;
 photoBinding: { fgaPhotoBindingId: string; expectedVerificationRevision: number };
 flickrGroupIds: string[];
}
export interface AdmissionAuth { installationId: string; credentialDigest: string; }
export interface WakeHint { partitionId: string; wakeRevision: string; }
export interface AdmissionItem {
 intentId: string; groupId: string; state: string; created: boolean;
 ordinal: string; blockReason: string|null;
}
export interface AdmissionResult { bindingId: string; photoId: string; items: AdmissionItem[]; hint: WakeHint|null; }
export class AdmissionError extends Error {}
const TOKEN = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
export function validateAdmission(value: unknown): asserts value is AdmissionRequest {
 const object=(x:unknown): x is Record<string,unknown> => typeof x==="object" && x!==null && !Array.isArray(x);
 if(!object(value) || Object.keys(value).sort().join()!=="flickrGroupIds,photoBinding,schemaVersion" ||
 value.schemaVersion!==2 || !object(value.photoBinding) ||
 Object.keys(value.photoBinding).sort().join()!=="expectedVerificationRevision,fgaPhotoBindingId" ||
 typeof value.photoBinding.fgaPhotoBindingId!=="string" || !TOKEN.test(value.photoBinding.fgaPhotoBindingId) ||
 !Number.isSafeInteger(value.photoBinding.expectedVerificationRevision) || (value.photoBinding.expectedVerificationRevision as number)<1 ||
 !Array.isArray(value.flickrGroupIds) || value.flickrGroupIds.length<1 || value.flickrGroupIds.length>MAX_GROUP_IDS ||
 value.flickrGroupIds.some(g=>typeof g!=="string" || !TOKEN.test(g)) || new Set(value.flickrGroupIds).size!==value.flickrGroupIds.length) {
  throw new AdmissionError("invalid_request");
 }
}
// One clock/guard row makes a fixed D1 batch conditional without a callback,
// retained request receipt or cross-service transaction. It never survives commit.
const PREFIX = `WITH input AS (SELECT ?1 AS request_id,?2 AS digest,?3 AS installation_id,
 ?4 AS binding_id,?5 AS revision,?6 AS groups),
 requested AS (SELECT CAST(key AS INTEGER) AS position,json_extract(value,'$.group') AS group_id,
 json_extract(value,'$.partition') AS partition_id,json_extract(value,'$.intent') AS intent_id FROM input,json_each(input.groups)),
 binding AS (SELECT b.* FROM photo_bindings b JOIN input ON input.binding_id=b.binding_id
 JOIN installations i ON i.installation_id=input.installation_id AND i.user_id=b.user_id
 JOIN installation_credential_versions v ON v.version_id=i.current_version_id AND v.installation_id=i.installation_id
 JOIN flickr_links l ON l.user_id=b.user_id
 WHERE i.state='active' AND i.credential_class='lrc_plugin' AND v.state='current' AND v.credential_digest=input.digest
 AND b.verification_revision=input.revision AND b.link_revision=l.link_revision AND b.owner_nsid=l.owner_nsid AND l.state IN ('linked','paused')) `;
const VALID = `EXISTS(SELECT 1 FROM binding b WHERE b.verified_at_us<=${NOW_US_SQL}
 AND (b.source_kind='upload' OR ${NOW_US_SQL}-b.verified_at_us<=${EXISTING_PROOF_MAX_AGE_US}
 OR NOT EXISTS(SELECT 1 FROM requested r WHERE NOT EXISTS(SELECT 1 FROM submission_intents i WHERE i.photo_id=b.photo_id AND i.group_id=r.group_id)))
 AND NOT EXISTS(SELECT 1 FROM requested r JOIN submission_blocks k ON k.photo_id=b.photo_id AND k.group_id=r.group_id
 LEFT JOIN submission_intents i ON i.photo_id=k.photo_id AND i.group_id=k.group_id WHERE i.intent_id IS NULL OR i.active_fifo_member=1)
 AND NOT EXISTS(SELECT 1 FROM requested r JOIN submission_intents i ON i.photo_id=b.photo_id AND i.group_id=r.group_id
 LEFT JOIN submission_blocks k ON k.photo_id=i.photo_id AND k.group_id=i.group_id
 WHERE i.binding_id<>b.binding_id OR i.user_id<>b.user_id OR (i.state='delivery_uncertain' AND k.photo_id IS NULL)))`;
interface ResultRow { intent_id:string;group_id:string;state:string;ordinal:string;created:number;block_reason:string|null;photo_id:string; }
export async function admit(db: SqlStore, auth: AdmissionAuth, value: unknown,
 publishHint: (hint:WakeHint)=>Promise<void> = async()=>{}): Promise<AdmissionResult> {
 validateAdmission(value);
 if(!TOKEN.test(auth.installationId) || !/^[a-f0-9]{64}$/.test(auth.credentialDigest)) throw new AdmissionError("invalid_authority");
 const requestId=crypto.randomUUID();
 const groups=JSON.stringify(value.flickrGroupIds.map(group=>({group,partition:crypto.randomUUID(),intent:crypto.randomUUID()})));
 const params=[requestId,auth.credentialDigest,auth.installationId,value.photoBinding.fgaPhotoBindingId,value.photoBinding.expectedVerificationRevision,groups];
 const statement=(sql:string)=>db.prepare(PREFIX+sql).bind(...params);
 const valid=await statement(`SELECT ${VALID} AS ok`).first<{ok:number}>();
 if(valid?.ok!==1) throw new AdmissionError("admission_rejected");
 const statements=[
  statement(`INSERT INTO transaction_guards(transaction_id,approved) SELECT request_id,${VALID} FROM input`),
  statement(`INSERT INTO group_partitions(partition_id,user_id,group_id)
   SELECT r.partition_id,b.user_id,r.group_id FROM requested r CROSS JOIN binding b ORDER BY b.user_id,r.group_id
   ON CONFLICT(user_id,group_id) DO NOTHING`),
  statement(`INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_at_us,created_request_id)
   SELECT r.intent_id,b.binding_id,b.user_id,b.photo_id,r.group_id,p.partition_id,p.next_enqueue_ordinal,'queued',g.now_us,input.request_id
   FROM requested r CROSS JOIN binding b JOIN group_partitions p ON p.user_id=b.user_id AND p.group_id=r.group_id
   CROSS JOIN input JOIN transaction_guards g ON g.transaction_id=input.request_id
   WHERE NOT EXISTS(SELECT 1 FROM submission_intents old WHERE old.photo_id=b.photo_id AND old.group_id=r.group_id)
   ORDER BY b.user_id,r.group_id`),
  statement(`UPDATE photo_bindings SET last_admission_at_us=(SELECT now_us FROM transaction_guards WHERE transaction_id=?1)
   WHERE binding_id=?4 AND EXISTS(SELECT 1 FROM submission_intents WHERE created_request_id=?1)`),
  statement(`SELECT i.intent_id,i.group_id,i.state,CAST(i.enqueue_ordinal AS TEXT) AS ordinal,
   i.created_request_id=?1 AS created,k.first_reason AS block_reason,i.photo_id
   FROM requested r CROSS JOIN binding b JOIN submission_intents i ON i.photo_id=b.photo_id AND i.group_id=r.group_id
   LEFT JOIN submission_blocks k ON k.photo_id=i.photo_id AND k.group_id=i.group_id ORDER BY r.position`),
  statement(`SELECT p.partition_id AS partitionId,CAST(p.wake_revision AS TEXT) AS wakeRevision
   FROM submission_intents i JOIN group_partitions p ON p.partition_id=i.partition_id WHERE i.created_request_id=?1
   AND i.active_fifo_member=1 AND (SELECT COUNT(*) FROM submission_intents x WHERE x.partition_id=p.partition_id AND x.active_fifo_member=1)=1
   ORDER BY p.user_id,p.group_id LIMIT 1`),
  statement(`DELETE FROM transaction_guards WHERE transaction_id=?1`),
 ];
 let results:D1Result[];
 try { results=await db.batch(statements); } catch { throw new AdmissionError("transaction_not_confirmed"); }
 const rows=results[4].results as unknown as ResultRow[];
 if(rows.length!==value.flickrGroupIds.length) throw new AdmissionError("committed_snapshot_inconsistent");
 const hint=(results[5].results[0] as unknown as WakeHint|undefined)??null;
 if(hint) { try { await publishHint(hint); } catch { /* D1 due rows recover a lost best-effort hint. */ } }
 return {bindingId:value.photoBinding.fgaPhotoBindingId,photoId:rows[0].photo_id,
  items:rows.map(r=>({intentId:r.intent_id,groupId:r.group_id,state:r.state,created:r.created===1,ordinal:r.ordinal,blockReason:r.block_reason})),hint};
}
