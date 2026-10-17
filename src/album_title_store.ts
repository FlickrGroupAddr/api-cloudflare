import type { AdmissionAuth, SqlStore } from './admission.ts';
import type { AlbumBinding } from './album_binding_store.ts';
import { NOW_US_SQL as NOW } from './installations.ts';

export interface AlbumTitleRequest { schemaVersion: 1; expectedBindingRevision: number; expectedTitleRevision: number; desiredTitle: string; }
export interface AlbumTitleView {
 state: 'waiting_for_materialization'|'pending'|'reconciliation_pending'|'synced'|'conflict'|'needs_attention'|'local_removed_reconciliation_pending'|'local_removed';
 observedTitle: string|null; observedAt: string|null; dispatchTitleRevision: number|null; dispatchAttemptId: string|null;
}
export interface AlbumLifecycle {
 schemaVersion: 1; binding: AlbumBinding;
 localLifecycle: 'active'|'local_collection_removed_remote_preserved'; title: AlbumTitleView;
 unresolvedCreateAttemptId: string|null;
 repairHandoff: { destination: 'none'|'administrative_album_create_repair'; fgaAlbumBindingId: string; createAttemptId: string|null; acknowledgedAt: string|null };
}
export interface AlbumTitleReceipt {
 schemaVersion: 1; fgaAlbumBindingId: string; acceptedTitleRevision: number; acceptedDesiredTitle: string;
 acceptedBindingRevision: number; acceptedAt: string; current: AlbumLifecycle;
}
export class AlbumTitleStoreError extends Error {}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const OPAQUE=/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const revision=(v:unknown):v is number=>Number.isSafeInteger(v)&&(v as number)>=1;
const title=(v:unknown):v is string=>typeof v==='string'&&[...v].length>=1&&[...v].length<=1000&&!/[\p{Cc}\p{Cs}]/u.test(v);
const display=(v:unknown):v is string=>typeof v==='string'&&new TextEncoder().encode(v).length<=4096&&!/[\p{Cc}\p{Cs}]/u.test(v);
function fail(code:string):never { throw new AlbumTitleStoreError(code); }
function stamp(us:unknown):string {
 if(!Number.isSafeInteger(us)||(us as number)<0)fail('service_unavailable');
 return new Date(Math.floor((us as number)/1000)).toISOString().replace(/\.(\d{3})Z$/,'.$1000Z');
}
function input(auth:AdmissionAuth,id:string):void {
 if(!OPAQUE.test(auth.installationId)||!/^[a-f0-9]{64}$/.test(auth.credentialDigest))fail('invalid_token');
 if(!UUID.test(id))fail('invalid_request');
}
// Every acceptance/replay snapshot uses current authentication in the same owning
// transaction. Reads do not depend on current remote grant usability.
const CONTEXT=`WITH context AS (SELECT b.*,i.installation_id auth_installation,
 a.binding_id link_ready FROM installations i JOIN installation_credential_versions v
 ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
 LEFT JOIN album_bindings b ON b.binding_id=?3 AND b.user_id=i.user_id
 LEFT JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=i.user_id
 LEFT JOIN album_title_link_authority a ON a.binding_id=b.binding_id
 WHERE i.installation_id=?1 AND v.credential_digest=?2 AND i.state='active' AND i.credential_class='lrc_plugin'
 AND i.revision BETWEEN 1 AND 9007199254740991 AND v.state='current' AND v.expires_at_us IS NULL
 AND (b.binding_id IS NULL OR s.service_id IS NOT NULL)) `;
interface SnapshotRow { snapshot:string; error:string|null; }
const SNAPSHOT=`SELECT CASE WHEN c.binding_id IS NULL THEN NULL ELSE json_object(
 'binding',json_object('schemaVersion',1,'fgaAlbumBindingId',c.binding_id,'fgaPublishServiceId',c.service_id,
 'localCollectionIdentifier',c.local_collection_id,'linkedFlickrRevision',c.link_revision,
 'bindingRevision',c.binding_revision,'titleRevision',c.title_revision,'desiredTitle',c.desired_title,
 'firstPhotoBindingId',c.first_photo_binding_id,'flickrPhotosetId',c.flickr_photoset_id),
 'localLifecycle',CASE WHEN c.state='local_collection_removed_remote_preserved' THEN c.state ELSE 'active' END,
 'unresolvedCreateAttemptId',(SELECT attempt_id FROM album_materialization_attempts WHERE binding_id=c.binding_id AND state='create_outcome_unknown' AND c.materialization_state='create_outcome_unknown' AND c.flickr_photoset_id IS NULL ORDER BY epoch DESC LIMIT 1),
 'attempt',json((SELECT json_object('state',t.state,'titleRevision',t.title_revision,'desiredTitle',t.desired_title,
 'dispatchCount',t.dispatch_count,'completed',t.completed_at_us,'remoteMissing',t.remote_missing,'satisfiedRevision',t.satisfied_title_revision)
 FROM album_title_attempts t WHERE t.binding_id=c.binding_id ORDER BY epoch DESC LIMIT 1)),
 'observation',json((SELECT json_object('title',t.observed_title,'at',t.observed_at_us)
 FROM album_title_attempts t WHERE t.binding_id=c.binding_id AND t.observed_at_us IS NOT NULL ORDER BY t.observed_at_us DESC,t.epoch DESC LIMIT 1)),
 'dispatch',json((SELECT json_object('revision',t.title_revision,'id',t.attempt_id,'open',t.completed_at_us IS NULL)
 FROM album_title_attempts t WHERE t.binding_id=c.binding_id AND t.dispatch_count=1 ORDER BY t.epoch DESC LIMIT 1)),
 'removalAcknowledgedAt',(SELECT archived_at_us FROM album_local_removal_receipts r WHERE r.binding_id=c.binding_id),
 'materializationState',c.materialization_state) END snapshot,
 CASE WHEN c.binding_id IS NULL THEN 'resource_not_found' ELSE NULL END error FROM context c`;
function lifecycle(row:SnapshotRow|undefined|null):AlbumLifecycle {
 if(!row)fail('invalid_token'); if(row.error)fail(row.error);
 const data=JSON.parse(row.snapshot) as {binding:AlbumBinding;localLifecycle:AlbumLifecycle['localLifecycle'];unresolvedCreateAttemptId:string|null;
 attempt:{state:string;titleRevision:number;desiredTitle:string;dispatchCount:number;completed:number|null;remoteMissing:number;satisfiedRevision:number|null}|null;
 observation:{title:string;at:number}|null;dispatch:{revision:number;id:string;open:number}|null;materializationState:string;removalAcknowledgedAt:number|null};
 const b=data.binding;
 if(!b||!UUID.test(b.fgaAlbumBindingId)||!UUID.test(b.fgaPublishServiceId)||!OPAQUE.test(b.localCollectionIdentifier)
 ||!OPAQUE.test(b.firstPhotoBindingId)||![b.bindingRevision,b.titleRevision,b.linkedFlickrRevision].every(revision)||!title(b.desiredTitle)
 ||b.flickrPhotosetId!==null&&!OPAQUE.test(b.flickrPhotosetId))fail('service_unavailable');
 const observation=data.observation;
 if(observation&&!display(observation.title))fail('service_unavailable');
 let state:AlbumTitleView['state'];
 const t=data.attempt;
 if(data.localLifecycle!=='active')state=data.dispatch?.open?'local_removed_reconciliation_pending':'local_removed';
 else if(t?.remoteMissing)state='needs_attention';
 else if(t?.completed===null&&t.dispatchCount===1)state=t.state==='needs_attention'?'needs_attention':'reconciliation_pending';
 else if(t?.state==='synced'&&t.satisfiedRevision===b.titleRevision&&observation?.title===b.desiredTitle)state='synced';
 else if(t?.titleRevision===b.titleRevision&&t.state==='conflict')state='conflict';
 else if(t?.titleRevision===b.titleRevision&&t.state==='needs_attention')state='needs_attention';
 else if(b.flickrPhotosetId===null)state='waiting_for_materialization';
 else if(!t&&observation?.title===b.desiredTitle)state='synced';
 else state='pending';
 return {schemaVersion:1,binding:b,localLifecycle:data.localLifecycle,title:{state,observedTitle:observation?.title??null,
 observedAt:observation?stamp(observation.at):null,dispatchTitleRevision:data.dispatch?.revision??null,dispatchAttemptId:data.dispatch?.id??null},
 unresolvedCreateAttemptId:data.unresolvedCreateAttemptId,repairHandoff:data.localLifecycle!=='active'&&data.unresolvedCreateAttemptId!==null
 ?{destination:'administrative_album_create_repair',fgaAlbumBindingId:b.fgaAlbumBindingId,createAttemptId:data.unresolvedCreateAttemptId,acknowledgedAt:stamp(data.removalAcknowledgedAt)}
 :{destination:'none',fgaAlbumBindingId:b.fgaAlbumBindingId,createAttemptId:null,acknowledgedAt:null}};
}
export async function readAlbumLifecycle(db:SqlStore,auth:AdmissionAuth,bindingId:string):Promise<AlbumLifecycle> {
 input(auth,bindingId);
 try{return lifecycle(await db.prepare(CONTEXT+SNAPSHOT).bind(auth.installationId,auth.credentialDigest,bindingId).first<SnapshotRow>());}
 catch(e){if(e instanceof AlbumTitleStoreError)throw e;fail('service_unavailable');}
}
export async function putAlbumTitleIntent(db:SqlStore,auth:AdmissionAuth,bindingId:string,pathRevision:number,value:AlbumTitleRequest):Promise<{created:boolean;receipt:AlbumTitleReceipt}> {
 input(auth,bindingId);
 if(!value||Object.keys(value).sort().join()!=='desiredTitle,expectedBindingRevision,expectedTitleRevision,schemaVersion'
 ||value.schemaVersion!==1||!revision(pathRevision)||!revision(value.expectedBindingRevision)||!revision(value.expectedTitleRevision)||!title(value.desiredTitle))fail('invalid_request');
 const args=[auth.installationId,auth.credentialDigest,bindingId,pathRevision,value.expectedBindingRevision,value.expectedTitleRevision,value.desiredTitle];
 const decision=CONTEXT+`SELECT CASE WHEN c.binding_id IS NULL THEN 'resource_not_found'
 WHEN r.title_revision IS NOT NULL THEN CASE WHEN r.expected_binding_revision=?5 AND r.expected_title_revision=?6 AND r.desired_title=?7 THEN NULL ELSE 'title_intent_conflict' END
 WHEN c.binding_revision<>?5 THEN 'stale_binding_revision'
 WHEN c.title_revision<>?6 OR (?6<9007199254740991 AND ?4<>?6+1) THEN 'stale_title_revision'
 WHEN c.binding_revision=9007199254740991 OR c.title_revision=9007199254740991 THEN 'revision_exhausted'
 WHEN c.state='local_collection_removed_remote_preserved' THEN 'album_closed'
 WHEN c.link_ready IS NULL THEN 'flickr_link_unavailable' ELSE NULL END error
 FROM context c LEFT JOIN album_title_receipts r ON r.binding_id=c.binding_id AND r.title_revision=?4`;
 try {
 const result=await db.batch([
 db.prepare(CONTEXT+`INSERT INTO album_title_receipts(binding_id,title_revision,expected_binding_revision,expected_title_revision,desired_title,accepted_binding_revision,installation_id,credential_digest)
 SELECT c.binding_id,?4,?5,?6,?7,?5+1,?1,?2 FROM context c
 WHERE c.binding_id IS NOT NULL AND c.binding_revision=?5 AND c.title_revision=?6 AND ?4=?6+1
 AND ?5<9007199254740991 AND ?6<9007199254740991 AND c.state='materialization_pending' AND c.link_ready IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM album_title_receipts r WHERE r.binding_id=c.binding_id AND r.title_revision=?4) RETURNING title_revision`).bind(...args),
 db.prepare(decision).bind(...args),
 db.prepare(CONTEXT+SNAPSHOT).bind(...args.slice(0,3)),
 db.prepare(CONTEXT+`SELECT r.* FROM context c JOIN album_title_receipts r ON r.binding_id=c.binding_id AND r.title_revision=?4`).bind(...args.slice(0,4)),
 ]);
 const d=result[1].results[0] as {error:string|null}|undefined;if(!d)fail('invalid_token');if(d.error)fail(d.error);
 const r=result[3].results[0] as {title_revision:number;desired_title:string;accepted_binding_revision:number;accepted_at_us:number}|undefined;
 if(!r)fail('service_unavailable');
 return {created:result[0].results.length===1,receipt:{schemaVersion:1,fgaAlbumBindingId:bindingId,acceptedTitleRevision:r.title_revision,
 acceptedDesiredTitle:r.desired_title,acceptedBindingRevision:r.accepted_binding_revision,acceptedAt:stamp(r.accepted_at_us),current:lifecycle(result[2].results[0] as unknown as SnapshotRow)}};
 }catch(e){if(e instanceof AlbumTitleStoreError)throw e;fail('service_unavailable');}
}

export interface AlbumTitleClaim {
 attemptId:string;bindingId:string;leaseId:string;epoch:number;userId:string;ownerNsid:string;photosetId:string;
 linkRevision:number;grantGeneration:string;desiredTitle:string;titleRevision:number;deploymentGateRevision:number;userGateRevision:number;
 dispatchCount:number;readCount:number;attemptNumber:number;preDispatchTitle:string|null;archived:boolean;bindingRevision:number;
}
export interface AlbumTitleProof {photosetId:string;ownerNsid:string;title:string;}
export type AlbumTitleOutcome='synced'|'superseded'|'retry_pending'|'conflict'|'reconciliation_pending'|'needs_attention'|'local_removed';
const COLUMNS=`t.attempt_id attemptId,t.binding_id bindingId,t.lease_id leaseId,t.epoch,t.user_id userId,t.owner_nsid ownerNsid,t.photoset_id photosetId,
 t.link_revision linkRevision,t.grant_generation grantGeneration,t.desired_title desiredTitle,t.title_revision titleRevision,
 t.deployment_gate_revision deploymentGateRevision,t.user_gate_revision userGateRevision,t.dispatch_count dispatchCount,
 t.read_count readCount,t.attempt_number attemptNumber,t.pre_dispatch_title preDispatchTitle,t.lease_binding_revision bindingRevision,
 (SELECT state='local_collection_removed_remote_preserved' FROM album_bindings b WHERE b.binding_id=t.binding_id) archived`;
const FENCE=`t.attempt_id=?1 AND t.binding_id=?2 AND t.lease_id=?3 AND t.epoch=?4
 AND t.user_id=?5 AND t.owner_nsid=?6 AND t.photoset_id=?7 AND t.link_revision=?8 AND t.grant_generation=?9
 AND t.desired_title=?10 AND t.title_revision=?11 AND t.deployment_gate_revision=?12 AND t.user_gate_revision=?13
 AND t.dispatch_count=?14 AND t.read_count=?15 AND t.attempt_number=?16 AND t.lease_binding_revision=?17 AND t.completed_at_us IS NULL`;
const IDENTITY_AUTH=`EXISTS(SELECT 1 FROM album_title_worker_authority a WHERE a.binding_id=t.binding_id AND a.user_id=t.user_id
 AND a.owner_nsid=t.owner_nsid AND a.flickr_photoset_id=t.photoset_id AND a.link_revision=t.link_revision
 AND a.grant_generation=t.grant_generation AND a.deployment_gate_revision=t.deployment_gate_revision AND a.user_gate_revision=t.user_gate_revision)`;
const FRONT=`EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.binding_revision<9007199254740991
 AND b.binding_revision=COALESCE((SELECT MAX(e.binding_revision_after) FROM album_title_semantic_events e WHERE e.attempt_id=t.attempt_id AND e.epoch=t.epoch),t.lease_binding_revision))`;
const AUTH=`${IDENTITY_AUTH} AND ${FRONT}`;
function params(c:AlbumTitleClaim):(string|number)[]{return [c.attemptId,c.bindingId,c.leaseId,c.epoch,c.userId,c.ownerNsid,c.photosetId,c.linkRevision,c.grantGeneration,c.desiredTitle,c.titleRevision,c.deploymentGateRevision,c.userGateRevision,c.dispatchCount,c.readCount,c.attemptNumber,c.bindingRevision];}
function valid(c:AlbumTitleClaim):boolean{return !!c&&[c.attemptId,c.bindingId,c.leaseId].every(x=>UUID.test(x))
 &&[c.epoch,c.linkRevision,c.titleRevision,c.deploymentGateRevision,c.userGateRevision,c.bindingRevision].every(revision)
 &&[c.userId,c.ownerNsid,c.photosetId,c.grantGeneration].every(x=>OPAQUE.test(x))&&title(c.desiredTitle)
 &&[0,1].includes(c.dispatchCount)&&Number.isInteger(c.readCount)&&c.readCount>=0&&c.readCount<=5&&[1,2,3].includes(c.attemptNumber);}
function claimRow(row:unknown):AlbumTitleClaim|null {if(!row)return null;const c=row as AlbumTitleClaim;return valid(c)?{...c,archived:!!c.archived}:null;}
export async function claimAlbumTitle(db:SqlStore,bindingId:string):Promise<AlbumTitleClaim|null> {
 if(!UUID.test(bindingId))return null;const attemptId=crypto.randomUUID(),leaseId=crypto.randomUUID();
 const r=await db.batch([
 db.prepare(`UPDATE album_title_attempts SET state='needs_attention' WHERE binding_id=?1 AND completed_at_us IS NULL
 AND state<>'needs_attention' AND read_count=5 AND lease_expires_at_us<=${NOW}
 AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=album_title_attempts.binding_id AND b.binding_revision<9007199254740991)`).bind(bindingId),
 db.prepare(`UPDATE album_title_attempts AS t SET lease_id=?1,epoch=epoch+1,lease_expires_at_us=${NOW}+11000000,invocation_deadline_at_us=${NOW}+10000000,
 lease_binding_revision=(SELECT binding_revision FROM album_bindings b WHERE b.binding_id=t.binding_id)
 WHERE binding_id=?2 AND completed_at_us IS NULL AND state<>'needs_attention' AND read_count<5 AND next_read_at_us<=${NOW}
 AND lease_expires_at_us<=${NOW} AND epoch<9007199254740991 AND ${IDENTITY_AUTH}
 AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.binding_revision<9007199254740991) RETURNING attempt_id`).bind(leaseId,bindingId),
 db.prepare(`INSERT INTO album_title_attempts(attempt_id,binding_id,lease_id,epoch,user_id,owner_nsid,photoset_id,link_revision,grant_generation,desired_title,title_revision,deployment_gate_revision,user_gate_revision,attempt_number,binding_revision,lease_binding_revision)
 SELECT ?1,a.binding_id,?2,COALESCE((SELECT MAX(epoch)+1 FROM album_title_attempts WHERE binding_id=a.binding_id),1),a.user_id,a.owner_nsid,a.flickr_photoset_id,
 a.link_revision,a.grant_generation,a.desired_title,a.title_revision,a.deployment_gate_revision,a.user_gate_revision,
 COALESCE((SELECT MAX(attempt_number)+1 FROM album_title_attempts WHERE binding_id=a.binding_id AND title_revision=a.title_revision),1),a.binding_revision,a.binding_revision
 FROM album_title_worker_authority a WHERE a.binding_id=?3 AND a.lifecycle_state='materialization_pending' AND a.binding_revision<9007199254740991
 AND EXISTS(SELECT 1 FROM album_binding_remote_status s WHERE s.binding_id=a.binding_id AND s.materialization_state='materialized')
 AND NOT EXISTS(SELECT 1 FROM album_title_attempts t WHERE t.binding_id=a.binding_id AND (t.completed_at_us IS NULL OR t.remote_missing=1))
 AND COALESCE((SELECT MAX(epoch) FROM album_title_attempts WHERE binding_id=a.binding_id),0)<9007199254740991
 AND COALESCE((SELECT MAX(attempt_number) FROM album_title_attempts WHERE binding_id=a.binding_id AND title_revision=a.title_revision),0)<3
 AND NOT EXISTS(SELECT 1 FROM album_title_attempts t WHERE t.binding_id=a.binding_id AND t.title_revision=a.title_revision AND (t.state<>'retry_pending' OR t.next_read_at_us>${NOW}))
 AND NOT EXISTS(SELECT 1 FROM album_title_attempts t WHERE t.binding_id=a.binding_id AND t.state='synced' AND t.observed_title=a.desired_title
 AND t.satisfied_title_revision=a.title_revision)`).bind(attemptId,leaseId,bindingId),
 db.prepare(`SELECT ${COLUMNS} FROM album_title_attempts t WHERE t.lease_id=?1 AND t.binding_id=?2`).bind(leaseId,bindingId),
 ]);return claimRow(r[3].results[0]);
}
export async function currentAlbumTitle(db:SqlStore,c:AlbumTitleClaim,minRemainingUs=0):Promise<boolean>{
 if(!valid(c)||!Number.isSafeInteger(minRemainingUs)||minRemainingUs<0)return false;
 return !!await db.prepare(`SELECT 1 FROM album_title_attempts t WHERE ${FENCE} AND t.state<>'needs_attention'
 AND t.lease_expires_at_us-${NOW}>?18 AND t.invocation_deadline_at_us-${NOW}>?18 AND ${AUTH}
 AND (t.dispatch_count=1 OR (EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.state='materialization_pending' AND b.title_revision=t.title_revision)
 AND EXISTS(SELECT 1 FROM album_binding_remote_status s WHERE s.binding_id=t.binding_id AND s.materialization_state='materialized')))` ).bind(...params(c),minRemainingUs).first();
}
async function update(db:SqlStore,c:AlbumTitleClaim,set:string,condition:string,extra:(string|number|null)[]=[]):Promise<AlbumTitleClaim|null>{
 if(!valid(c))return null;
 const r=await db.batch([
 db.prepare(`UPDATE album_title_attempts AS t SET ${set} WHERE ${FENCE} AND ${condition} RETURNING attempt_id`).bind(...params(c),...extra),
 db.prepare(`SELECT ${COLUMNS} FROM album_title_attempts t WHERE t.attempt_id=?1 AND t.lease_id=?3 AND t.epoch=?4`).bind(...params(c).slice(0,4)),
 ]);
 return r[0].results.length===1&&(r[0].results[0] as {attempt_id:string}).attempt_id===c.attemptId?claimRow(r[1].results[0]):null;
}
const LIVE=`t.lease_expires_at_us>${NOW} AND t.invocation_deadline_at_us>${NOW} AND ${AUTH}`;
export async function beginAlbumTitleRead(db:SqlStore,c:AlbumTitleClaim):Promise<AlbumTitleClaim|null>{
 return update(db,c,`read_count=read_count+1,state=CASE WHEN t.dispatch_count=0 THEN 'claimed' ELSE t.state END,
 next_read_at_us=${NOW}+CASE WHEN (t.dispatch_count=1 AND t.read_count+1<=2) OR (t.dispatch_count=0 AND t.read_count+1<2) THEN 5000000 ELSE 30000000 END`,`${LIVE} AND t.read_count<5 AND t.state<>'needs_attention' AND t.next_read_at_us<=${NOW}`);
}
export async function markAlbumTitleDispatch(db:SqlStore,c:AlbumTitleClaim,proof:AlbumTitleProof):Promise<AlbumTitleClaim|null>{
 if(!proof||proof.photosetId!==c.photosetId||proof.ownerNsid!==c.ownerNsid||!display(proof.title)||proof.title===c.desiredTitle)return null;
 return update(db,c,`state='dispatched',dispatch_count=1,pre_dispatch_title=?18,dispatch_started_at_us=${NOW},next_read_at_us=0,observed_title=?18,observed_at_us=${NOW}`,
 `${LIVE} AND t.state='claimed' AND t.dispatch_count=0 AND t.read_count>0 AND t.read_count<5 AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id
 AND b.state='materialization_pending' AND b.title_revision=t.title_revision AND b.desired_title=t.desired_title)
 AND EXISTS(SELECT 1 FROM album_binding_remote_status s WHERE s.binding_id=t.binding_id AND s.materialization_state='materialized')`,[proof.title]);
}
export async function recordAlbumTitleResult(db:SqlStore,c:AlbumTitleClaim,resultClass:'success'|'uncertain'|'rejected'):Promise<boolean>{
 if(!['success','uncertain','rejected'].includes(resultClass))return false;
 return !!await update(db,c,`state='result_received',result_class=?18`,`${LIVE} AND t.state='dispatched' AND t.result_class IS NULL`,[resultClass]);
}
export async function reconcileAlbumTitle(db:SqlStore,c:AlbumTitleClaim,proof:AlbumTitleProof|null):Promise<AlbumTitleOutcome|null>{
 if(proof&&(proof.photosetId!==c.photosetId||proof.ownerNsid!==c.ownerNsid||!display(proof.title)))proof=null;
 if(!valid(c)||c.readCount<1)return null;
 // Classification is SQL-side against the latest committed desired revision.
 // A new intent never bypasses a retained unresolved older marker.
 const observed=proof?.title??null;
 const state=`CASE WHEN ?18 IS NULL THEN CASE WHEN t.read_count>=5 THEN 'needs_attention' ELSE 'reconciliation_pending' END
 WHEN EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.state='local_collection_removed_remote_preserved') THEN 'local_removed'
 WHEN EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.desired_title=?18) THEN 'synced'
 WHEN t.dispatch_count=1 AND ?18=t.desired_title THEN 'superseded'
 WHEN t.dispatch_count=0 AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.title_revision>t.title_revision) THEN 'superseded'
 WHEN t.dispatch_count=1 AND ?18=t.pre_dispatch_title THEN CASE
 WHEN EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=t.binding_id AND b.title_revision>t.title_revision) THEN 'superseded'
 WHEN t.attempt_number>=3 THEN 'needs_attention' ELSE 'retry_pending' END
 WHEN t.dispatch_count=0 THEN CASE WHEN t.read_count>=5 THEN 'needs_attention' ELSE 'claimed' END
 ELSE 'conflict' END`;
 const r=await db.batch([
 db.prepare(`UPDATE album_title_attempts AS t SET state=${state},
 observed_title=CASE WHEN ?18 IS NULL THEN observed_title ELSE ?18 END,observed_at_us=CASE WHEN ?18 IS NULL THEN observed_at_us ELSE ${NOW} END,
 completed_at_us=CASE WHEN (${state}) IN ('synced','superseded','retry_pending','conflict','local_removed')
 OR ((${state})='needs_attention' AND ?18 IS NOT NULL AND t.dispatch_count=1 AND t.attempt_number=3 AND ?18=t.pre_dispatch_title) THEN ${NOW} ELSE NULL END,
 satisfied_title_revision=CASE WHEN (${state})='synced' THEN (SELECT title_revision FROM album_bindings b WHERE b.binding_id=t.binding_id) ELSE satisfied_title_revision END,
 next_read_at_us=CASE WHEN (${state})='retry_pending' THEN ${NOW}+CASE WHEN t.attempt_number=1 THEN 5000000 ELSE 30000000 END ELSE MAX(next_read_at_us,${NOW}+CASE WHEN (t.dispatch_count=1 AND t.read_count<=2) OR (t.dispatch_count=0 AND t.read_count<2) THEN 5000000 ELSE 30000000 END) END,
 lease_expires_at_us=${NOW}
 WHERE ${FENCE} AND ${LIVE} RETURNING attempt_id,state`).bind(...params(c),observed),
 ]);
 const row=r[0].results[0] as {attempt_id:string;state:AlbumTitleOutcome}|undefined;
 return row?.attempt_id===c.attemptId?row.state:null;
}
export async function releaseAlbumTitle(db:SqlStore,c:AlbumTitleClaim,notBeforeUs=0):Promise<boolean>{
 if(!Number.isSafeInteger(notBeforeUs)||notBeforeUs<0)return false;
 return !!await update(db,c,`lease_expires_at_us=${NOW},next_read_at_us=MAX(next_read_at_us,?18,${NOW}+5000000)`,LIVE,[notBeforeUs]);
}
export async function missingAlbumTitle(db:SqlStore,c:AlbumTitleClaim):Promise<boolean>{
 return !!await update(db,c,`state='needs_attention',remote_missing=1,lease_expires_at_us=${NOW}`,`${LIVE} AND t.read_count>0`);
}

// Shared projection for lifecycle mutations: callers include this read in the
// same owning D1 batch as the receipt rather than a later independent read.
export { CONTEXT as ALBUM_LIFECYCLE_CONTEXT, SNAPSHOT as ALBUM_LIFECYCLE_SNAPSHOT, lifecycle as albumLifecycleFromRow };
