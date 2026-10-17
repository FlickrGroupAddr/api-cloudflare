import type { SqlStore } from './admission.ts';
import { NOW_US_SQL } from './installations.ts';

/** Internal owning-D1 lease. No client request may supply this authority. */
export interface AlbumMaterializationClaim {
  attemptId: string; bindingId: string; leaseId: string; epoch: number;
  userId: string; ownerNsid: string; photoBindingId: string; photoId: string;
  linkRevision: number; grantGeneration: string; desiredTitle: string; titleRevision: number;
  deploymentGateRevision: number; userGateRevision: number; dispatchCount: number;
}
export interface AlbumMaterializationProof {
  photosetId: string; url: string; ownerNsid: string;
  /** Exact photo used for the membership read, not the current album primary role. */
  primaryPhotoId: string; contextIds: string[];
}
const OPAQUE = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const COLUMNS = `attempt_id attemptId,binding_id bindingId,lease_id leaseId,epoch,user_id userId,
 owner_nsid ownerNsid,photo_binding_id photoBindingId,photo_id photoId,link_revision linkRevision,
 grant_generation grantGeneration,desired_title desiredTitle,title_revision titleRevision,
 deployment_gate_revision deploymentGateRevision,user_gate_revision userGateRevision,dispatch_count dispatchCount`;
const FENCE = `attempt_id=?1 AND binding_id=?2 AND lease_id=?3 AND epoch=?4
 AND user_id=?5 AND owner_nsid=?6 AND photo_binding_id=?7 AND photo_id=?8
 AND link_revision=?9 AND grant_generation=?10 AND desired_title=?11 AND title_revision=?12
 AND deployment_gate_revision=?13 AND user_gate_revision=?14
 AND completed_at_us IS NULL AND NOT EXISTS(SELECT 1 FROM album_materialization_attempts newer
  WHERE newer.binding_id=album_materialization_attempts.binding_id AND newer.epoch>album_materialization_attempts.epoch)`;
const AUTHORITY = `EXISTS(SELECT 1 FROM album_materialization_authority v
 WHERE v.binding_id=album_materialization_attempts.binding_id AND v.user_id=?5 AND v.owner_nsid=?6
 AND v.photo_binding_id=?7 AND v.photo_id=?8 AND v.link_revision=?9 AND v.grant_generation=?10
 AND v.deployment_gate_revision=?13 AND v.user_gate_revision=?14 AND v.flickr_photoset_id IS NULL)`;
function args(c: AlbumMaterializationClaim): (string | number)[] {
 return [c.attemptId,c.bindingId,c.leaseId,c.epoch,c.userId,c.ownerNsid,c.photoBindingId,c.photoId,
 c.linkRevision,c.grantGeneration,c.desiredTitle,c.titleRevision,c.deploymentGateRevision,c.userGateRevision];
}
function validClaim(c: AlbumMaterializationClaim): boolean {
 return UUID.test(c.attemptId) && UUID.test(c.bindingId) && UUID.test(c.leaseId)
 && [c.epoch,c.linkRevision,c.titleRevision,c.deploymentGateRevision,c.userGateRevision].every(n=>Number.isSafeInteger(n)&&n>0)
 && [c.userId,c.ownerNsid,c.photoBindingId,c.photoId,c.grantGeneration].every(s=>typeof s==='string'&&OPAQUE.test(s))
 && typeof c.desiredTitle==='string' && [...c.desiredTitle].length>=1 && [...c.desiredTitle].length<=1000;
}
function contexts(ids: string[]): string | null {
 if(!Array.isArray(ids)||ids.length>1000||ids.some(id=>typeof id!=='string'||id==='0'||!OPAQUE.test(id))||new Set(ids).size!==ids.length)return null;
 const value=JSON.stringify([...ids].sort());return value.length<=1048576?value:null;
}

/** Expired marked attempts become unknown even if gates/grants have changed.
 * This is safety recovery only: it cannot authorize another claim or dispatch.
 * Unmarked attempts close before a successor receives a strictly newer epoch. */
export async function claimAlbumMaterialization(db: SqlStore, bindingId: string): Promise<AlbumMaterializationClaim | null> {
 if(!UUID.test(bindingId))return null;
 const attemptId=crypto.randomUUID(),leaseId=crypto.randomUUID();
 const result=await db.batch([
  db.prepare(`UPDATE album_materialization_attempts SET state=CASE WHEN dispatch_count=1 THEN 'create_outcome_unknown' ELSE 'abandoned_before_dispatch' END,
   completed_at_us=${NOW_US_SQL} WHERE binding_id=? AND completed_at_us IS NULL AND lease_expires_at_us<=${NOW_US_SQL}`).bind(bindingId),
  db.prepare(`INSERT INTO album_materialization_attempts(attempt_id,binding_id,lease_id,epoch,user_id,owner_nsid,
   photo_binding_id,photo_id,link_revision,grant_generation,desired_title,title_revision,deployment_gate_revision,user_gate_revision)
   SELECT ?1,v.binding_id,?2,COALESCE((SELECT MAX(epoch)+1 FROM album_materialization_attempts WHERE binding_id=v.binding_id),1),
   v.user_id,v.owner_nsid,v.photo_binding_id,v.photo_id,v.link_revision,v.grant_generation,v.desired_title,v.title_revision,
   v.deployment_gate_revision,v.user_gate_revision FROM album_materialization_authority v
   WHERE v.binding_id=?3 AND v.materialization_state='pending' AND v.flickr_photoset_id IS NULL
   AND NOT EXISTS(SELECT 1 FROM album_materialization_attempts a WHERE a.binding_id=v.binding_id AND (a.completed_at_us IS NULL OR a.dispatch_count=1))
   AND COALESCE((SELECT MAX(epoch) FROM album_materialization_attempts WHERE binding_id=v.binding_id),0)<9007199254740991`).bind(attemptId,leaseId,bindingId),
  db.prepare(`SELECT ${COLUMNS} FROM album_materialization_attempts WHERE attempt_id=?`).bind(attemptId),
 ]);
 const row=result[2].results[0] as unknown as AlbumMaterializationClaim|undefined;
 return row&&validClaim(row)?row:null;
}

export async function currentAlbumMaterialization(db: SqlStore,c: AlbumMaterializationClaim,minRemainingUs=0): Promise<boolean> {
 if(!validClaim(c)||!Number.isSafeInteger(minRemainingUs)||minRemainingUs<0)return false;
 return !!await db.prepare(`SELECT 1 ok FROM album_materialization_attempts WHERE ${FENCE}
  AND lease_expires_at_us-${NOW_US_SQL}>?15 AND invocation_deadline_at_us-${NOW_US_SQL}>?15
  AND ${AUTHORITY}`).bind(...args(c),minRemainingUs).first();
}

/** The prepared request must already contain this claim's title and first photo.
 * A title race refuses the marker so the next invocation can prepare afresh. */
export async function markAlbumCreateDispatch(db:SqlStore,c:AlbumMaterializationClaim,preContextIds:string[]):Promise<AlbumMaterializationClaim|null>{
 const ids=contexts(preContextIds);if(!validClaim(c)||ids===null)return null;
 const result=await db.batch([
  db.prepare(`UPDATE album_materialization_attempts SET state='dispatched',dispatch_count=1,
   dispatch_started_at_us=${NOW_US_SQL},pre_context_observed_at_us=${NOW_US_SQL},pre_context_ids=?15
   WHERE ${FENCE} AND state='claimed' AND dispatch_count=0 AND lease_expires_at_us-${NOW_US_SQL}>15000000
   AND invocation_deadline_at_us-${NOW_US_SQL}>15000000
   AND ${AUTHORITY} AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=?2 AND b.desired_title=?11 AND b.title_revision=?12) RETURNING attempt_id`)
   .bind(...args(c),ids),
  db.prepare(`SELECT ${COLUMNS} FROM album_materialization_attempts WHERE ${FENCE} AND state='dispatched' AND dispatch_count=1`).bind(...args(c)),
 ]);
 // Only the transaction that changed the row receives dispatch authority. Reading
 // a retained marker on an idempotent retry must never grant another POST.
 // D1 meta.changes includes trigger writes, so only UPDATE RETURNING proves
 // that this statement changed the exact attempt; affected-row metadata cannot.
 if(result[0].results.length!==1 || (result[0].results[0] as {attempt_id?:unknown}|undefined)?.attempt_id!==c.attemptId)return null;
 const row=result[1].results[0] as unknown as AlbumMaterializationClaim|undefined;
 return row&&validClaim(row)?row:null;
}

/** Retain the strict successful create response before read-after-write proof.
 * This receipt never binds an album or satisfies membership on its own. */
export async function recordAlbumCreateResult(db:SqlStore,c:AlbumMaterializationClaim,result:{photosetId:string;url:string}):Promise<boolean>{
 if(!OPAQUE.test(result.photosetId)||result.photosetId==='0'||!validUrl(result.url,result.photosetId))return false;
 return change(db,c,`state='result_received',received_photoset_id=?15,received_navigation_url=?16,received_at_us=${NOW_US_SQL}`,
  `state='dispatched' AND lease_expires_at_us-${NOW_US_SQL}>5000000 AND invocation_deadline_at_us-${NOW_US_SQL}>5000000 AND ${AUTHORITY}`,[result.photosetId,result.url]);
}
function validUrl(value:string,photosetId:string):boolean {
 if(typeof value!=='string'||value.length<1||new TextEncoder().encode(value).length>2048||/[\s\\]/u.test(value))return false;
 try {
  const url=new URL(value);
  if(url.protocol!=='https:'||!['www.flickr.com','flickr.com'].includes(url.hostname)
   ||url.port||url.username||url.password||url.search||url.hash)return false;
  const path=/^\/photos\/([^/]+)\/(?:sets|albums)\/([^/]+)\/?$/.exec(url.pathname);
  return !!path&&OPAQUE.test(decodeURIComponent(path[1]!))&&decodeURIComponent(path[1]!)!=='0'
   &&decodeURIComponent(path[2]!)===photosetId;
 } catch{return false;}
}

export async function finishAlbumMaterialization(db:SqlStore,c:AlbumMaterializationClaim,proof:AlbumMaterializationProof):Promise<boolean>{
 const ids=contexts(proof.contextIds);
 if(!validClaim(c)||ids===null||!OPAQUE.test(proof.photosetId)||proof.photosetId==='0'||proof.ownerNsid!==c.ownerNsid
 ||proof.primaryPhotoId!==c.photoId||!proof.contextIds.includes(proof.photosetId)
 ||!validUrl(proof.url,proof.photosetId))return false;
 return change(db,c,`state='verified',completed_at_us=${NOW_US_SQL},photoset_id=?15,navigation_url=?16,
  proof_context_ids=?17,proof_owner_nsid=?18,proof_photo_id=?19,proof_observed_at_us=${NOW_US_SQL}`,
  `state='result_received' AND received_photoset_id=?15 AND received_navigation_url=?16
   AND lease_expires_at_us-${NOW_US_SQL}>5000000 AND invocation_deadline_at_us-${NOW_US_SQL}>5000000 AND ${AUTHORITY}`,[proof.photosetId,proof.url,ids,proof.ownerNsid,proof.primaryPhotoId]);
}
async function change(db:SqlStore,c:AlbumMaterializationClaim,set:string,condition:string,extra:(string|number)[]=[]):Promise<boolean>{
 if(!validClaim(c))return false;
 const result=await db.batch([db.prepare(`UPDATE album_materialization_attempts SET ${set} WHERE ${FENCE} AND ${condition} RETURNING attempt_id`).bind(...args(c),...extra)]);
 return result[0].results.length===1 && (result[0].results[0] as {attempt_id?:unknown}|undefined)?.attempt_id===c.attemptId;
}
export async function failAlbumMaterializationBeforeDispatch(db:SqlStore,c:AlbumMaterializationClaim):Promise<boolean>{
 return change(db,c,`state='abandoned_before_dispatch',completed_at_us=${NOW_US_SQL}`,`state='claimed'`);
}
export async function unknownAlbumMaterialization(db:SqlStore,c:AlbumMaterializationClaim):Promise<boolean>{
 return change(db,c,`state='create_outcome_unknown',completed_at_us=${NOW_US_SQL}`,`state IN ('dispatched','result_received')`);
}
/** Only the worker's strict documented no-creation classifier calls this method.
 * A rejection is terminal in this slice; no retry or administration bypass exists. */
export async function rejectAlbumMaterialization(db:SqlStore,c:AlbumMaterializationClaim,flickrCode:number):Promise<boolean>{
 if(!new Set([1,2,3,95,96,97,98,99,100]).has(flickrCode))return false;
 return change(db,c,`state='create_rejected',completed_at_us=${NOW_US_SQL},flickr_code=?15`,
  `state='dispatched' AND lease_expires_at_us-${NOW_US_SQL}>5000000 AND invocation_deadline_at_us-${NOW_US_SQL}>5000000 AND ${AUTHORITY}`,[flickrCode]);
}
