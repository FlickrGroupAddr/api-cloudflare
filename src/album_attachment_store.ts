import type { SqlStore } from './admission.ts';
import { NOW_US_SQL } from './installations.ts';

/** Owning D1 authority, never supplied by a client or queue message. */
export interface AlbumAttachmentClaim {
 attemptId:string; obligationId:string; bindingId:string; leaseId:string; epoch:number;
 userId:string; ownerNsid:string; photoBindingId:string; photoId:string; photosetId:string; primaryPhotoId:string;
 linkRevision:number; grantGeneration:string; bindingRevision:number; obligationRevision:number; verificationRevision:number;
 deploymentGateRevision:number; userGateRevision:number; dispatchCount:number; dispatchAttempts:number; reconciliationOnly:boolean; archivedAfterFulfillment:boolean;
}
export interface AlbumAttachmentProof { ownerNsid:string; photoId:string; contextIds:string[] }
export type AlbumAttachmentAttentionReason='wrong_owner'|'missing_album'|'missing_photo'|'binding_conflict'|'retry_exhausted'|'archived_drift_unresolved';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const OPAQUE=/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const DISPATCH_COUNT=`(SELECT COUNT(*) FROM album_attachment_attempts history
 WHERE history.obligation_id=album_attachment_attempts.obligation_id AND history.dispatch_count=1
 AND history.epoch>COALESCE((SELECT MAX(done.epoch) FROM album_attachment_attempts done
 WHERE done.obligation_id=history.obligation_id AND done.state='membership_verified'),0))`;
const ARCHIVED_FULFILLED=`EXISTS(SELECT 1 FROM album_photo_obligations archived
 WHERE archived.obligation_id=album_attachment_attempts.obligation_id AND archived.local_relationship='archived'
 AND EXISTS(SELECT 1 FROM album_obligation_events fulfilled WHERE fulfilled.obligation_id=archived.obligation_id AND fulfilled.state='membership_verified'))`;
const COLUMNS=`attempt_id attemptId,obligation_id obligationId,binding_id bindingId,lease_id leaseId,epoch,
 user_id userId,owner_nsid ownerNsid,photo_binding_id photoBindingId,photo_id photoId,photoset_id photosetId,primary_photo_id primaryPhotoId,
 link_revision linkRevision,grant_generation grantGeneration,binding_revision bindingRevision,obligation_revision obligationRevision,
 verification_revision verificationRevision,deployment_gate_revision deploymentGateRevision,user_gate_revision userGateRevision,
 dispatch_count dispatchCount,reconciliation_only reconciliationOnly,
 ${DISPATCH_COUNT} dispatchAttempts,${ARCHIVED_FULFILLED} archivedAfterFulfillment`;
const FENCE=`attempt_id=?1 AND obligation_id=?2 AND binding_id=?3 AND lease_id=?4 AND epoch=?5
 AND user_id=?6 AND owner_nsid=?7 AND photo_binding_id=?8 AND photo_id=?9 AND photoset_id=?10 AND primary_photo_id=?11
 AND link_revision=?12 AND grant_generation=?13 AND binding_revision=?14 AND obligation_revision=?15
 AND verification_revision=?16 AND deployment_gate_revision=?17 AND user_gate_revision=?18
 AND reconciliation_only=?19 AND completed_at_us IS NULL
 AND NOT EXISTS(SELECT 1 FROM album_attachment_attempts newer WHERE newer.obligation_id=album_attachment_attempts.obligation_id
 AND newer.epoch>album_attachment_attempts.epoch)`;
const AUTHORITY=`EXISTS(SELECT 1 FROM album_attachment_authority v WHERE v.obligation_id=?2 AND v.binding_id=?3
 AND v.user_id=?6 AND v.owner_nsid=?7 AND v.photo_binding_id=?8 AND v.photo_id=?9 AND v.photoset_id=?10 AND v.primary_photo_id=?11
 AND v.link_revision=?12 AND v.grant_generation=?13
 AND v.binding_revision=?14+(SELECT COUNT(*) FROM album_attachment_semantic_events se WHERE se.attempt_id=?1)
 AND v.obligation_revision=?15+(SELECT COUNT(*) FROM album_attachment_semantic_events se WHERE se.attempt_id=?1)
 AND v.verification_revision=?16 AND v.deployment_gate_revision=?17 AND v.user_gate_revision=?18)`;
function args(c:AlbumAttachmentClaim):(string|number)[]{return [c.attemptId,c.obligationId,c.bindingId,c.leaseId,c.epoch,c.userId,c.ownerNsid,
 c.photoBindingId,c.photoId,c.photosetId,c.primaryPhotoId,c.linkRevision,c.grantGeneration,c.bindingRevision,c.obligationRevision,
 c.verificationRevision,c.deploymentGateRevision,c.userGateRevision,Number(c.reconciliationOnly)];}
function valid(c:AlbumAttachmentClaim):boolean{return [c.attemptId,c.obligationId,c.bindingId,c.leaseId].every(s=>typeof s==='string'&&UUID.test(s))
 && [c.userId,c.ownerNsid,c.photoBindingId,c.photoId,c.photosetId,c.primaryPhotoId,c.grantGeneration].every(s=>typeof s==='string'&&s!=='0'&&OPAQUE.test(s))
 && [c.epoch,c.linkRevision,c.bindingRevision,c.obligationRevision,c.verificationRevision,c.deploymentGateRevision,c.userGateRevision].every(n=>Number.isSafeInteger(n)&&n>0)
 && typeof c.reconciliationOnly==='boolean' && (c.dispatchCount===0||c.dispatchCount===1)
 && typeof c.archivedAfterFulfillment==='boolean'
 && Number.isSafeInteger(c.dispatchAttempts)&&c.dispatchAttempts>=0&&c.dispatchAttempts<=8;}
function row(value:unknown):AlbumAttachmentClaim|null {
 if(!value||typeof value!=='object')return null;
 const r=value as Omit<AlbumAttachmentClaim,'reconciliationOnly'|'archivedAfterFulfillment'> & {reconciliationOnly:number;archivedAfterFulfillment:number};
 if((r.reconciliationOnly!==0&&r.reconciliationOnly!==1)||(r.archivedAfterFulfillment!==0&&r.archivedAfterFulfillment!==1))return null;
 const claim={...r,reconciliationOnly:r.reconciliationOnly===1,archivedAfterFulfillment:r.archivedAfterFulfillment===1};return valid(claim)?claim:null;
}
function contexts(ids:string[]):string|null {
 if(!Array.isArray(ids)||ids.length>1000||ids.some(id=>typeof id!=='string'||id==='0'||!OPAQUE.test(id))||new Set(ids).size!==ids.length)return null;
 const json=JSON.stringify([...ids].sort());return json.length<=1048576?json:null;
}
/** Recover expired authority without resending a marked write. A successor of
 * uncertain dispatch starts in read-only reconciliation; absence schedules a
 * separate bounded retry, never an add in that same claim. */
export async function claimAlbumAttachment(db:SqlStore,obligationId:string):Promise<AlbumAttachmentClaim|null>{
 if(!UUID.test(obligationId))return null;const attemptId=crypto.randomUUID(),leaseId=crypto.randomUUID();
 const result=await db.batch([
  db.prepare(`UPDATE album_attachment_attempts SET state=CASE WHEN dispatch_count=1 OR reconciliation_only=1
   THEN 'membership_reconciliation_pending' ELSE 'abandoned_before_dispatch' END,completed_at_us=${NOW_US_SQL},
   received_result=CASE WHEN dispatch_count=1 THEN COALESCE(received_result,'uncertain') ELSE received_result END,
   received_at_us=CASE WHEN dispatch_count=1 THEN COALESCE(received_at_us,${NOW_US_SQL}) ELSE received_at_us END,
   retry_after_us=${NOW_US_SQL}+MIN(60000000,1000000*(1 << MIN(epoch-1,6))) WHERE obligation_id=? AND completed_at_us IS NULL AND lease_expires_at_us<=${NOW_US_SQL}`).bind(obligationId),
  db.prepare(`INSERT INTO album_attachment_attempts(attempt_id,obligation_id,binding_id,lease_id,epoch,user_id,owner_nsid,
   photo_binding_id,photo_id,photoset_id,primary_photo_id,link_revision,grant_generation,binding_revision,obligation_revision,
   verification_revision,deployment_gate_revision,user_gate_revision,reconciliation_only)
   SELECT ?1,v.obligation_id,v.binding_id,?2,COALESCE((SELECT MAX(epoch)+1 FROM album_attachment_attempts WHERE obligation_id=v.obligation_id),1),
   v.user_id,v.owner_nsid,v.photo_binding_id,v.photo_id,v.photoset_id,v.primary_photo_id,v.link_revision,v.grant_generation,v.binding_revision,
   v.obligation_revision,v.verification_revision,v.deployment_gate_revision,v.user_gate_revision,
   COALESCE((SELECT state='membership_reconciliation_pending' FROM album_attachment_attempts WHERE obligation_id=v.obligation_id ORDER BY epoch DESC LIMIT 1),0)
   FROM album_attachment_authority v WHERE v.obligation_id=?3
   AND NOT EXISTS(SELECT 1 FROM album_attachment_attempts a WHERE a.obligation_id=v.obligation_id AND (a.completed_at_us IS NULL OR a.state='album_attachment_needs_attention'))
   AND COALESCE((SELECT retry_after_us FROM album_attachment_attempts WHERE obligation_id=v.obligation_id ORDER BY epoch DESC LIMIT 1),0)<=${NOW_US_SQL}
   AND COALESCE((SELECT MAX(epoch) FROM album_attachment_attempts WHERE obligation_id=v.obligation_id),0)<9007199254740991
   RETURNING ${COLUMNS}`).bind(attemptId,leaseId,obligationId),
 ]);return row(result[1].results[0]);
}
export async function currentAlbumAttachment(db:SqlStore,c:AlbumAttachmentClaim,minRemainingUs=0):Promise<boolean>{
 if(!valid(c)||!Number.isSafeInteger(minRemainingUs)||minRemainingUs<0)return false;
 return !!await db.prepare(`SELECT 1 ok FROM album_attachment_attempts WHERE ${FENCE}
  AND lease_expires_at_us-${NOW_US_SQL}>?20 AND invocation_deadline_at_us-${NOW_US_SQL}>?20 AND ${AUTHORITY}`)
  .bind(...args(c),minRemainingUs).first();
}
export async function markAlbumAttachmentDispatch(db:SqlStore,c:AlbumAttachmentClaim,contextIds:string[]):Promise<AlbumAttachmentClaim|null>{
 const ids=contexts(contextIds);if(!valid(c)||ids===null||contextIds.includes(c.photosetId)||c.reconciliationOnly)return null;
 const result=await db.batch([db.prepare(`UPDATE album_attachment_attempts SET state='dispatched',dispatch_count=1,
  dispatch_started_at_us=${NOW_US_SQL},pre_context_ids=?20,pre_observed_at_us=${NOW_US_SQL}
  WHERE ${FENCE} AND state='claimed' AND dispatch_count=0 AND reconciliation_only=0 AND ${AUTHORITY}
  AND ${DISPATCH_COUNT}<8
  AND lease_expires_at_us-${NOW_US_SQL}>15000000 AND invocation_deadline_at_us-${NOW_US_SQL}>15000000 RETURNING attempt_id`)
  .bind(...args(c),ids),db.prepare(`SELECT ${COLUMNS} FROM album_attachment_attempts WHERE ${FENCE} AND state='dispatched' AND dispatch_count=1`).bind(...args(c))]);
 // D1 changes includes trigger writes. Only this exact RETURNING row grants POST.
 return result[0].results.length===1&&(result[0].results[0] as {attempt_id?:unknown}|undefined)?.attempt_id===c.attemptId?row(result[1].results[0]):null;
}
async function change(db:SqlStore,c:AlbumAttachmentClaim,set:string,where:string,extra:(string|number)[]=[]):Promise<boolean>{
 if(!valid(c))return false;
 const result=await db.batch([db.prepare(`UPDATE album_attachment_attempts SET ${set} WHERE ${FENCE} AND ${where} RETURNING attempt_id`).bind(...args(c),...extra)]);
 return result[0].results.length===1&&(result[0].results[0] as {attempt_id?:unknown}|undefined)?.attempt_id===c.attemptId;
}
function proof(c:AlbumAttachmentClaim,p:AlbumAttachmentProof,present:boolean):string|null {
 const ids=contexts(p.contextIds);if(ids===null||p.ownerNsid!==c.ownerNsid||p.photoId!==c.photoId||p.contextIds.includes(c.photosetId)!==present)return null;return ids;
}
const LIVE=`lease_expires_at_us-${NOW_US_SQL}>5000000 AND invocation_deadline_at_us-${NOW_US_SQL}>5000000 AND ${AUTHORITY}`;
const RESULT_FALLBACK=`received_result=CASE WHEN dispatch_count=1 THEN COALESCE(received_result,'uncertain') ELSE received_result END,
 received_at_us=CASE WHEN dispatch_count=1 THEN COALESCE(received_at_us,${NOW_US_SQL}) ELSE received_at_us END`;
/** A documented write response is a retained receipt, never membership proof. */
export async function recordAlbumAttachmentResult(db:SqlStore,c:AlbumAttachmentClaim,result:'added'|'already_present'):Promise<boolean>{
 if(result!=='added'&&result!=='already_present')return false;
 return change(db,c,`state='result_received',received_result=?20,received_at_us=${NOW_US_SQL}`,
  `state='dispatched' AND ${LIVE}`,[result]);
}
export async function finishAlbumAttachment(db:SqlStore,c:AlbumAttachmentClaim,p:AlbumAttachmentProof):Promise<boolean>{
 const ids=proof(c,p,true);if(ids===null)return false;
 return change(db,c,`state='membership_verified',completed_at_us=${NOW_US_SQL},retry_after_us=0,proof_context_ids=?20,
  proof_owner_nsid=?21,proof_photo_id=?22,proof_observed_at_us=${NOW_US_SQL},${RESULT_FALLBACK}`,`state IN ('claimed','dispatched','result_received') AND ${LIVE}`,[ids,p.ownerNsid,p.photoId]);
}
export async function deferAlbumAttachment(db:SqlStore,c:AlbumAttachmentClaim,p:AlbumAttachmentProof):Promise<boolean>{
 const ids=proof(c,p,false);if(ids===null)return false;
 return change(db,c,`state='retry_scheduled',completed_at_us=${NOW_US_SQL},retry_after_us=${NOW_US_SQL}+MIN(60000000,1000000*(1 << MIN(epoch-1,6))),
  proof_context_ids=?20,proof_owner_nsid=?21,proof_photo_id=?22,proof_observed_at_us=${NOW_US_SQL},${RESULT_FALLBACK}`,
  `state IN ('claimed','dispatched','result_received') AND ${LIVE}
   AND ${DISPATCH_COUNT}<8 AND NOT ${ARCHIVED_FULFILLED}`,[ids,p.ownerNsid,p.photoId]);
}
export async function unknownAlbumAttachment(db:SqlStore,c:AlbumAttachmentClaim):Promise<boolean>{
 return change(db,c,`state='membership_reconciliation_pending',completed_at_us=${NOW_US_SQL},retry_after_us=${NOW_US_SQL}+MIN(60000000,1000000*(1 << MIN(epoch-1,6))),
  received_result=CASE WHEN dispatch_count=1 THEN COALESCE(received_result,'uncertain') ELSE received_result END,
  received_at_us=CASE WHEN dispatch_count=1 THEN COALESCE(received_at_us,${NOW_US_SQL}) ELSE received_at_us END`,
  `state IN ('dispatched','result_received') OR (state='claimed' AND reconciliation_only=1)`);
}
export async function failAlbumAttachmentBeforeDispatch(db:SqlStore,c:AlbumAttachmentClaim):Promise<boolean>{
 return change(db,c,`state=CASE WHEN reconciliation_only=1 THEN 'membership_reconciliation_pending' ELSE 'abandoned_before_dispatch' END,
  completed_at_us=${NOW_US_SQL},retry_after_us=${NOW_US_SQL}+MIN(60000000,1000000*(1 << MIN(epoch-1,6)))`,`state='claimed'`);
}
export async function attentionAlbumAttachment(db:SqlStore,c:AlbumAttachmentClaim,reason:AlbumAttachmentAttentionReason,p?:AlbumAttachmentProof):Promise<boolean>{
 if(!['wrong_owner','missing_album','missing_photo','binding_conflict','retry_exhausted','archived_drift_unresolved'].includes(reason))return false;
 if(reason==='retry_exhausted'||reason==='archived_drift_unresolved'){
  if(!p)return false;const ids=proof(c,p,false);if(ids===null)return false;
  return change(db,c,`state='album_attachment_needs_attention',attention_reason=?20,completed_at_us=${NOW_US_SQL},retry_after_us=0,
   proof_context_ids=?21,proof_owner_nsid=?22,proof_photo_id=?23,proof_observed_at_us=${NOW_US_SQL},${RESULT_FALLBACK}`,
   `state IN ('claimed','dispatched','result_received') AND ${LIVE}`,[reason,ids,p.ownerNsid,p.photoId]);
 }
 return change(db,c,`state='album_attachment_needs_attention',attention_reason=?20,completed_at_us=${NOW_US_SQL},retry_after_us=0,${RESULT_FALLBACK}`,
  `state IN ('claimed','dispatched','result_received') AND ${LIVE}`,[reason]);
}
