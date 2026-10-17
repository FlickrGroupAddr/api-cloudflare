import type { AdmissionAuth, SqlStore } from './admission.ts';
import type { AlbumObligation } from './album_binding_store.ts';
import { ALBUM_LIFECYCLE_CONTEXT as CONTEXT, ALBUM_LIFECYCLE_SNAPSHOT as SNAPSHOT,
 albumLifecycleFromRow, type AlbumLifecycle } from './album_title_store.ts';

export interface AlbumRemovalRequest { schemaVersion: 1; expectedBindingRevision: number; acknowledgedCreateAttemptId: string|null; }
export interface PhotoRemovalRequest { schemaVersion: 1; expectedBindingRevision: number; expectedObligationRevision: number; }
export interface AlbumRemovalReceipt {
 schemaVersion: 1; fgaAlbumBindingId: string; localLifecycle: 'local_collection_removed_remote_preserved';
 archivedAt: string; acceptedBindingRevision: number; repairHandoff: AlbumLifecycle['repairHandoff']; current: AlbumLifecycle;
}
export interface PhotoRemovalReceipt {
 schemaVersion: 1; obligation: AlbumObligation; localRelationship: 'archived'; archivedAt: string;
 acceptedBindingRevision: number; current: AlbumLifecycle;
}
export class AlbumLocalRemovalStoreError extends Error {}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const OPAQUE=/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const revision=(v:unknown):v is number=>Number.isSafeInteger(v)&&(v as number)>=1;
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
function fail(code:string):never { throw new AlbumLocalRemovalStoreError(code); }
function stamp(us:unknown):string {
 if(!Number.isSafeInteger(us)||(us as number)<0)fail('service_unavailable');
 return new Date(Math.floor((us as number)/1000)).toISOString().replace(/\.(\d{3})Z$/,'.$1000Z');
}
function input(auth:AdmissionAuth,id:string):void {
 if(!auth||!OPAQUE.test(auth.installationId)||!/^[a-f0-9]{64}$/.test(auth.credentialDigest))fail('invalid_token');
 if(!UUID.test(id))fail('invalid_request');
}
interface AlbumRow { binding_id:string; acknowledged_create_attempt_id:string|null; archived_at_us:number; accepted_binding_revision:number; }
interface PhotoRow { obligation_id:string; binding_id:string; photo_binding_id:string; archived_obligation_revision:number; archived_at_us:number; accepted_binding_revision:number; }
function albumRow(row:AlbumRow|undefined,bindingId:string):AlbumRow {
 if(!row||row.binding_id!==bindingId||!revision(row.accepted_binding_revision)
 ||row.acknowledged_create_attempt_id!==null&&!UUID.test(row.acknowledged_create_attempt_id))fail('service_unavailable');
 stamp(row.archived_at_us);return row;
}
function photoRow(row:PhotoRow|undefined,bindingId:string,photoId:string):PhotoRow {
 if(!row||row.binding_id!==bindingId||row.photo_binding_id!==photoId||!UUID.test(row.obligation_id)
 ||![row.archived_obligation_revision,row.accepted_binding_revision].every(revision))fail('service_unavailable');
 stamp(row.archived_at_us);return row;
}
function current(row:unknown):AlbumLifecycle {
 try{return albumLifecycleFromRow(row as Parameters<typeof albumLifecycleFromRow>[0]);}
 catch {fail('service_unavailable');}
}
function decision(row:unknown):void {
 const r=row as {error:string|null}|undefined;
 if(!r)fail('invalid_token');if(r.error)fail(r.error);
}
// Both acceptance and exact natural-key replay authenticate at the same owning
// D1 batch point as the immutable receipt/current lifecycle snapshot. No remote
// grant is needed to archive locally. SQL triggers apply every dependent fact.
export async function putAlbumLocalRemoval(db:SqlStore,auth:AdmissionAuth,bindingId:string,value:AlbumRemovalRequest):Promise<{created:boolean;receipt:AlbumRemovalReceipt}> {
 input(auth,bindingId);
 if(!object(value)||Object.keys(value).sort().join()!=='acknowledgedCreateAttemptId,expectedBindingRevision,schemaVersion'
 ||value.schemaVersion!==1||!revision(value.expectedBindingRevision)
 ||value.acknowledgedCreateAttemptId!==null&&(typeof value.acknowledgedCreateAttemptId!=='string'||!UUID.test(value.acknowledgedCreateAttemptId)))fail('invalid_request');
 const args=[auth.installationId,auth.credentialDigest,bindingId,value.expectedBindingRevision,value.acknowledgedCreateAttemptId];
 const unknown=`(SELECT a.attempt_id FROM album_materialization_attempts a WHERE a.binding_id=c.binding_id AND a.state='create_outcome_unknown' AND c.materialization_state='create_outcome_unknown' AND c.flickr_photoset_id IS NULL ORDER BY a.epoch DESC LIMIT 1)`;
 const exhausted=`EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.album_binding_id=c.binding_id AND o.local_relationship='active' AND o.obligation_revision=9007199254740991)`;
 try {
 const result=await db.batch([
 db.prepare(CONTEXT+`INSERT INTO album_local_removal_receipts(binding_id,expected_binding_revision,accepted_binding_revision,acknowledged_create_attempt_id,installation_id,credential_digest)
 SELECT c.binding_id,?4,?4+1,?5,?1,?2 FROM context c WHERE c.binding_id IS NOT NULL
 AND c.binding_revision=?4 AND ?4<9007199254740991 AND c.state='materialization_pending'
 AND ?5 IS ${unknown} AND NOT ${exhausted}
 AND NOT EXISTS(SELECT 1 FROM album_local_removal_receipts r WHERE r.binding_id=c.binding_id)
 RETURNING binding_id,accepted_binding_revision`).bind(...args),
 db.prepare(CONTEXT+`SELECT CASE WHEN c.binding_id IS NULL THEN 'resource_not_found'
 WHEN r.binding_id IS NOT NULL THEN CASE WHEN r.acknowledged_create_attempt_id IS ?5 THEN NULL ELSE 'removal_acknowledgement_conflict' END
 WHEN c.binding_revision<>?4 THEN 'stale_binding_revision'
 WHEN ?5 IS NOT ${unknown} THEN 'removal_acknowledgement_required'
 WHEN c.binding_revision=9007199254740991 OR ${exhausted} THEN 'revision_exhausted'
 ELSE 'service_unavailable' END error FROM context c LEFT JOIN album_local_removal_receipts r ON r.binding_id=c.binding_id`).bind(...args),
 db.prepare(CONTEXT+SNAPSHOT).bind(...args.slice(0,3)),
 db.prepare(CONTEXT+`SELECT r.* FROM context c JOIN album_local_removal_receipts r ON r.binding_id=c.binding_id`).bind(...args.slice(0,3)),
 ]);
 decision(result[1].results[0]);
 const r=albumRow(result[3].results[0] as unknown as AlbumRow|undefined,bindingId);
 const inserted=result[0].results as unknown as {binding_id:string;accepted_binding_revision:number}[];
 if(inserted.length>1||inserted.length===1&&(inserted[0].binding_id!==bindingId||inserted[0].accepted_binding_revision!==r.accepted_binding_revision))fail('service_unavailable');
 return {created:inserted.length===1,receipt:{schemaVersion:1,fgaAlbumBindingId:bindingId,
 localLifecycle:'local_collection_removed_remote_preserved',archivedAt:stamp(r.archived_at_us),acceptedBindingRevision:r.accepted_binding_revision,
 repairHandoff:{destination:r.acknowledged_create_attempt_id===null?'none':'administrative_album_create_repair',fgaAlbumBindingId:bindingId,
 createAttemptId:r.acknowledged_create_attempt_id,acknowledgedAt:r.acknowledged_create_attempt_id===null?null:stamp(r.archived_at_us)},current:current(result[2].results[0])}};
 }catch(e){if(e instanceof AlbumLocalRemovalStoreError)throw e;fail('service_unavailable');}
}
export async function putAlbumPhotoLocalRemoval(db:SqlStore,auth:AdmissionAuth,bindingId:string,photoBindingId:string,value:PhotoRemovalRequest):Promise<{created:boolean;receipt:PhotoRemovalReceipt}> {
 input(auth,bindingId);
 if(!OPAQUE.test(photoBindingId)||!object(value)||Object.keys(value).sort().join()!=='expectedBindingRevision,expectedObligationRevision,schemaVersion'
 ||value.schemaVersion!==1||!revision(value.expectedBindingRevision)||!revision(value.expectedObligationRevision))fail('invalid_request');
 const args=[auth.installationId,auth.credentialDigest,bindingId,photoBindingId,value.expectedBindingRevision,value.expectedObligationRevision];
 const pair=` FROM context c LEFT JOIN album_photo_obligations o ON o.album_binding_id=c.binding_id AND o.photo_binding_id=?4
 LEFT JOIN album_photo_local_removal_receipts r ON r.obligation_id=o.obligation_id`;
 try {
 const result=await db.batch([
 db.prepare(CONTEXT+`INSERT INTO album_photo_local_removal_receipts(obligation_id,binding_id,photo_binding_id,expected_binding_revision,expected_obligation_revision,
 accepted_binding_revision,archived_obligation_revision,source,installation_id,credential_digest)
 SELECT o.obligation_id,c.binding_id,?4,?5,?6,?5+1,?6+1,'photo',?1,?2`+pair+`
 WHERE c.binding_id IS NOT NULL AND o.obligation_id IS NOT NULL AND r.obligation_id IS NULL AND o.local_relationship='active'
 AND c.binding_revision=?5 AND o.obligation_revision=?6 AND ?5<9007199254740991 AND ?6<9007199254740991
 RETURNING obligation_id,archived_obligation_revision,accepted_binding_revision`).bind(...args),
 db.prepare(CONTEXT+`SELECT CASE WHEN c.binding_id IS NULL OR o.obligation_id IS NULL THEN 'resource_not_found'
 WHEN r.obligation_id IS NOT NULL THEN NULL
 WHEN c.binding_revision<>?5 THEN 'stale_binding_revision'
 WHEN o.obligation_revision<>?6 THEN 'stale_obligation_revision'
 WHEN c.binding_revision=9007199254740991 OR o.obligation_revision=9007199254740991 THEN 'revision_exhausted'
 ELSE 'service_unavailable' END error`+pair).bind(...args),
 db.prepare(CONTEXT+SNAPSHOT).bind(...args.slice(0,3)),
 db.prepare(CONTEXT+`SELECT r.*`+pair).bind(...args.slice(0,4)),
 ]);
 decision(result[1].results[0]);
 const r=photoRow(result[3].results[0] as unknown as PhotoRow|undefined,bindingId,photoBindingId);
 const inserted=result[0].results as unknown as {obligation_id:string;archived_obligation_revision:number;accepted_binding_revision:number}[];
 if(inserted.length>1||inserted.length===1&&(inserted[0].obligation_id!==r.obligation_id||inserted[0].archived_obligation_revision!==r.archived_obligation_revision
 ||inserted[0].accepted_binding_revision!==r.accepted_binding_revision))fail('service_unavailable');
 return {created:inserted.length===1,receipt:{schemaVersion:1,obligation:{fgaAlbumObligationId:r.obligation_id,fgaAlbumBindingId:bindingId,
 fgaPhotoBindingId:photoBindingId,obligationRevision:r.archived_obligation_revision},localRelationship:'archived',archivedAt:stamp(r.archived_at_us),
 acceptedBindingRevision:r.accepted_binding_revision,current:current(result[2].results[0])}};
 }catch(e){if(e instanceof AlbumLocalRemovalStoreError)throw e;fail('service_unavailable');}
}
export const putPhotoLocalRemoval=putAlbumPhotoLocalRemoval;
