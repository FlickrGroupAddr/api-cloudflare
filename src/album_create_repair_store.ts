import type { SqlStore } from './admission.ts';
import type { AlbumBinding, AlbumObligation } from './album_binding_store.ts';
import { NOW_US_SQL } from './installations.ts';

export type RepairAuth = { kind: 'installation'; installationId: string; credentialDigest: string }
 | { kind: 'admin'; sessionId: string; tokenDigest: string; ownerSub: string };
export interface ResolveRequest { schemaVersion: 1; expectedBindingRevision: number; createAttemptId: string; selectedPhotosetId: string; }
export interface Status {
 schemaVersion: 1; binding: AlbumBinding;
 localLifecycle: 'active' | 'local_collection_removed_remote_preserved';
 materialization: { state: 'materialization_pending' | 'create_rejected' | 'create_outcome_unknown' | 'materialized' | 'remote_album_missing_needs_attention' | 'album_identity_conflict';
  createAttemptId: string | null; repairSurface: 'none' | 'plugin_or_admin' | 'admin_only'; resolvedPhotosetId: string | null;
  resolutionProvenance: 'owner_reconciled_ambiguous_album_create' | null };
 catalogRepair: { flickrPhotosetId: string | null; navigationUrl: string | null; identityVerifiedAt: string | null };
 membershipCounts: { waitingForAlbum: number; attachmentPending: number; membershipVerified: number; reconciliationPending: number; needsAttention: number };
}
export interface ObligationStatus { obligation: AlbumObligation; state: 'waiting_for_album' | 'attachment_pending' | 'membership_verified' | 'membership_reconciliation_pending' | 'album_attachment_needs_attention'; membershipObservedAt: string | null; localRelationship: 'active' | 'archived'; }
export interface ObligationPage { schemaVersion: 1; fgaAlbumBindingId: string; bindingRevision: number; page: number; pageSize: number; pages: number; total: number; obligations: ObligationStatus[]; }
export interface RepairSummary { fgaAlbumBindingId: string; bindingRevision: number; fgaPublishServiceId: string; localCollectionIdentifier: string; desiredTitle: string; localLifecycle: 'active' | 'local_collection_removed_remote_preserved'; createAttemptId: string; }
export interface RepairPage { schemaVersion: 1; page: number; pageSize: number; pages: number; total: number; repairs: RepairSummary[]; }
export interface RepairContext {
 bindingId: string; bindingRevision: number; userId: string; attemptId: string; ownerNsid: string;
 firstPhotoId: string; firstPhotoBindingId: string; linkRevision: number; grantGeneration: string;
 deploymentGateRevision: number; userGateRevision: number;
 lifecycle: 'materialization_pending' | 'local_collection_removed_remote_preserved'; preContextIds: string[];
 authorityRevision: number; principalRevision: number; authorityId: string; observedAtUs: number; deadlineAtUs: number;
}
export interface AlbumResolutionProof { photosetId: string; url: string; ownerNsid: string; firstPhotoId: string; contextIds: string[]; observedAt: string; }
export class AlbumCreateRepairStoreError extends Error {}
const ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const revision = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n > 0;
function fail(code: string): never { throw new AlbumCreateRepairStoreError(code); }
function identity(auth: RepairAuth): [string, string, string] {
 const values: [string,string] = auth.kind === 'installation' ? [auth.installationId,auth.credentialDigest] : [auth.sessionId,auth.tokenDigest];
 if (!ID.test(values[0]) || !/^[0-9a-f]{64}$/.test(values[1])) fail(auth.kind === 'installation' ? 'invalid_token' : 'unauthorized');
 if(auth.kind==='admin'&&(!ID.test(auth.ownerSub)))fail('unauthorized');
 return [...values,auth.kind==='admin'?auth.ownerSub:''];
}
function authority(auth: RepairAuth): string {
 return auth.kind === 'installation' ? `SELECT i.user_id,i.revision authority_revision,0 principal_revision,i.installation_id authority_id
 FROM installations i JOIN installation_credential_versions c ON c.installation_id=i.installation_id AND c.version_id=i.current_version_id
 WHERE i.installation_id=?1 AND c.credential_digest=?2 AND i.state='active' AND i.credential_class='lrc_plugin'
 AND i.revision BETWEEN 1 AND 9007199254740991 AND c.state='current' AND c.expires_at_us IS NULL`
 : `SELECT s.user_id,s.revision authority_revision,p.session_set_revision principal_revision,s.session_id authority_id FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id
 WHERE s.session_id=?1 AND s.token_digest=?2 AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW_US_SQL}
 AND p.google_issuer='https://accounts.google.com' AND p.google_sub=?3`;
}
function contextSql(auth: RepairAuth): string {
 return `WITH auth AS (${authority(auth)}), context AS (
 SELECT auth.user_id,auth.authority_revision,auth.principal_revision,auth.authority_id,b.*,
 a.attempt_id,a.state attempt_state,a.dispatch_count,a.pre_context_ids,a.pre_context_observed_at_us,
 a.link_revision attempt_link_revision,a.grant_generation attempt_grant_generation,
 a.deployment_gate_revision attempt_deployment_gate_revision,a.user_gate_revision attempt_user_gate_revision,
 a.owner_nsid attempt_owner_nsid,a.photo_id attempt_photo_id,a.photo_binding_id attempt_photo_binding_id,
 a.proof_observed_at_us materialization_proof_at,
 rs.materialization_state projected_materialization_state,
 r.attempt_id resolved_attempt_id,r.selected_photoset_id,r.proof_observed_at_us resolution_proof_at,
 v.grant_generation,v.deployment_gate_revision,v.user_gate_revision,
 COALESCE(v.binding_id IS NOT NULL AND a.link_revision=v.link_revision AND a.grant_generation=v.grant_generation
 AND a.deployment_gate_revision=v.deployment_gate_revision AND a.user_gate_revision=v.user_gate_revision
 AND a.owner_nsid=v.owner_nsid AND a.photo_id=v.photo_id AND a.photo_binding_id=v.photo_binding_id,0) repair_ready,
 ${NOW_US_SQL} observed_at_us,
 (SELECT json_object('waitingForAlbum',SUM(state='waiting_for_album'),'attachmentPending',SUM(state='attachment_pending'),
 'membershipVerified',SUM(state='membership_verified'),'reconciliationPending',SUM(state='membership_reconciliation_pending'),
 'needsAttention',SUM(state='album_attachment_needs_attention')) FROM album_obligation_status WHERE album_binding_id=b.binding_id) counts
 FROM auth LEFT JOIN album_bindings b ON b.binding_id=?4 AND b.user_id=auth.user_id
 AND EXISTS(SELECT 1 FROM publish_service_identities s WHERE s.service_id=b.service_id AND s.user_id=auth.user_id)
 LEFT JOIN album_materialization_attempts a ON a.attempt_id=(SELECT attempt_id FROM album_materialization_attempts
  WHERE binding_id=b.binding_id ORDER BY epoch DESC LIMIT 1)
 LEFT JOIN album_create_repair_receipts r ON r.binding_id=b.binding_id
 LEFT JOIN album_materialization_authority v ON v.binding_id=b.binding_id
 LEFT JOIN album_binding_remote_status rs ON rs.binding_id=b.binding_id
 ) `;
}
type Row = Record<string, unknown>;
async function row(db: SqlStore, auth: RepairAuth, bindingId: string): Promise<Row> {
 if (!UUID.test(bindingId)) fail('invalid_request');
 const value = await db.prepare(contextSql(auth)+'SELECT * FROM context').bind(...identity(auth),bindingId).first<Row>();
 return checked(value,auth);
}
function checked(value: Row | null | undefined,auth: RepairAuth): Row {
 if (!value) fail(auth.kind === 'installation' ? 'invalid_token' : 'unauthorized');
 if (value.binding_id === null) fail('resource_not_found');
 if (!UUID.test(String(value.binding_id)) || !UUID.test(String(value.service_id)) || !ID.test(String(value.local_collection_id))
  || !ID.test(String(value.first_photo_binding_id)) || !ID.test(String(value.first_photo_id))
  || ![value.binding_revision,value.title_revision,value.link_revision].every(revision)) fail('service_unavailable');
 return value;
}
function timestamp(us: unknown): string | null {
 if (us === null || us === undefined) return null;
 if (typeof us !== 'number' || !Number.isSafeInteger(us) || us < 0) fail('service_unavailable');
 return new Date(Math.floor(us/1000)).toISOString().replace(/\.[0-9]{3}Z$/,'.'+String(us%1000000).padStart(6,'0')+'Z');
}
function status(value: Row): Status {
 const lifecycle = value.state === 'local_collection_removed_remote_preserved' ? 'local_collection_removed_remote_preserved' : 'active';
 const source = String(value.projected_materialization_state);
 const state: Status['materialization']['state'] = source === 'pending' || source === 'creating' ? 'materialization_pending'
  : ['materialized','create_outcome_unknown','create_rejected','remote_album_missing_needs_attention','album_identity_conflict'].includes(source)
   ? source as Status['materialization']['state'] : fail('service_unavailable');
 const photosetId = value.flickr_photoset_id as string|null, selected = value.selected_photoset_id as string|null;
 const rawCounts = JSON.parse(String(value.counts)) as Record<string,unknown>;
 const counts = Object.fromEntries(Object.entries(rawCounts).map(([key,n])=>[key,n??0])) as unknown as Status['membershipCounts'];
 if (Object.values(counts).some(n=>!Number.isSafeInteger(n)||n<0) || (state === 'materialized' && photosetId === null)
  || (['materialization_pending','create_rejected','create_outcome_unknown'].includes(state) && photosetId !== null)
  || selected !== null && selected !== photosetId || state === 'create_outcome_unknown' && !UUID.test(String(value.attempt_id))) fail('service_unavailable');
 const proofAt = value.resolution_proof_at ?? value.materialization_proof_at;
 const showProof = state === 'materialized' && proofAt != null && value.navigation_url != null;
 if (showProof && !validUrl(String(value.navigation_url),String(photosetId))) fail('service_unavailable');
 return { schemaVersion:1,binding:{schemaVersion:1,fgaAlbumBindingId:String(value.binding_id),fgaPublishServiceId:String(value.service_id),
  localCollectionIdentifier:String(value.local_collection_id),linkedFlickrRevision:Number(value.link_revision),bindingRevision:Number(value.binding_revision),
  titleRevision:Number(value.title_revision),desiredTitle:String(value.desired_title),firstPhotoBindingId:String(value.first_photo_binding_id),flickrPhotosetId:photosetId},
  localLifecycle:lifecycle,materialization:{state,createAttemptId:value.attempt_id as string|null,
   repairSurface:state === 'create_outcome_unknown' ? lifecycle === 'active' ? 'plugin_or_admin' : 'admin_only' : 'none',
   resolvedPhotosetId:selected,resolutionProvenance:selected===null?null:'owner_reconciled_ambiguous_album_create'},
  catalogRepair:{flickrPhotosetId:photosetId,navigationUrl:showProof?String(value.navigation_url):null,identityVerifiedAt:showProof?timestamp(proofAt):null},membershipCounts:counts };
}
async function safe<T>(work:()=>Promise<T>):Promise<T>{try{return await work();}catch(error){if(error instanceof AlbumCreateRepairStoreError)throw error;return fail('service_unavailable');}}
export async function readAlbumStatus(db:SqlStore,auth:RepairAuth,bindingId:string):Promise<Status>{return safe(async()=>status(await row(db,auth,bindingId)));}
function contexts(value:unknown):string[]{
 const parsed = typeof value === 'string' ? JSON.parse(value) as unknown : value;
 if(!Array.isArray(parsed)||parsed.length>1000||parsed.some(id=>typeof id!=='string'||!ID.test(id)||id==='0')
  ||new Set(parsed).size!==parsed.length||new TextEncoder().encode(JSON.stringify(parsed)).length>1048576)fail('candidate_evidence_unavailable');
 return parsed as string[];
}
function repair(value:Row,auth:RepairAuth):RepairContext {
 if(auth.kind==='installation'&&value.state==='local_collection_removed_remote_preserved')fail('administrative_repair_required');
 if(value.repair_ready!==1)fail('flickr_link_unavailable');
 if(value.materialization_state!=='create_outcome_unknown'||value.flickr_photoset_id!==null||value.attempt_state!=='create_outcome_unknown'||value.dispatch_count!==1)fail('create_repair_not_pending');
 if(!UUID.test(String(value.attempt_id))||value.pre_context_ids===null||value.pre_context_observed_at_us===null)fail('candidate_evidence_unavailable');
 const observedAtUs=Number(value.observed_at_us);
 return {bindingId:String(value.binding_id),bindingRevision:Number(value.binding_revision),userId:String(value.user_id),attemptId:String(value.attempt_id),ownerNsid:String(value.owner_nsid),
  firstPhotoId:String(value.first_photo_id),firstPhotoBindingId:String(value.first_photo_binding_id),linkRevision:Number(value.link_revision),grantGeneration:String(value.grant_generation),
  deploymentGateRevision:Number(value.deployment_gate_revision),userGateRevision:Number(value.user_gate_revision),lifecycle:value.state as RepairContext['lifecycle'],
  preContextIds:contexts(value.pre_context_ids),authorityRevision:Number(value.authority_revision),principalRevision:Number(value.principal_revision),authorityId:String(value.authority_id),observedAtUs,deadlineAtUs:observedAtUs+10000000};
}
export async function readAlbumRepairContext(db:SqlStore,auth:RepairAuth,bindingId:string):Promise<RepairContext>{return safe(async()=>repair(await row(db,auth,bindingId),auth));}
function sameContext(current:RepairContext,prior:RepairContext):void{
 for(const key of ['bindingId','bindingRevision','userId','attemptId','ownerNsid','firstPhotoId','firstPhotoBindingId','linkRevision','grantGeneration','deploymentGateRevision','userGateRevision','lifecycle','authorityRevision','principalRevision','authorityId'] as const)
  if(current[key]!==prior[key])fail(key==='bindingRevision'?'stale_binding_revision':'flickr_link_unavailable');
 if(current.observedAtUs>=prior.deadlineAtUs)fail('resolution_evidence_unavailable');
 if(JSON.stringify(current.preContextIds)!==JSON.stringify(prior.preContextIds))fail('service_unavailable');
}
export async function assertAlbumRepairContext(db:SqlStore,auth:RepairAuth,value:RepairContext):Promise<void>{return safe(async()=>sameContext(await readAlbumRepairContext(db,auth,value.bindingId),value));}
function request(value:ResolveRequest):void {if(value.schemaVersion!==1||!revision(value.expectedBindingRevision)||!UUID.test(value.createAttemptId)||!ID.test(value.selectedPhotosetId)||value.selectedPhotosetId==='0')fail('invalid_request');}
function replay(value:Row,auth:RepairAuth,input:ResolveRequest):Status|null{
 if(auth.kind==='installation'&&value.state==='local_collection_removed_remote_preserved')fail('administrative_repair_required');
 // Link/generation/pause fences still govern an exact receipt replay.
 if(value.repair_ready!==1)fail('flickr_link_unavailable');
 if(value.selected_photoset_id!==null){if(value.selected_photoset_id===input.selectedPhotosetId&&value.resolved_attempt_id===input.createAttemptId)return status(value);fail('resolution_conflict');}
 if(value.flickr_photoset_id!==null||value.attempt_id!==input.createAttemptId)fail('resolution_conflict');
 return null;
}
export async function prepareAlbumResolution(db:SqlStore,auth:RepairAuth,bindingId:string,input:ResolveRequest):Promise<{replay:true;status:Status}|{replay:false;context:RepairContext}>{return safe(async()=>{
 request(input);const value=await row(db,auth,bindingId),prior=replay(value,auth,input);if(prior)return{replay:true,status:prior};
 if(value.binding_revision!==input.expectedBindingRevision)fail('stale_binding_revision');return{replay:false,context:repair(value,auth)};
});}
function validUrl(value:string,photosetId:string):boolean{
 if(typeof value!=='string'||new TextEncoder().encode(value).length>2048||/[\s\\]/u.test(value))return false;
 try{const url=new URL(value),path=/^\/photos\/([^/]+)\/(?:sets|albums)\/([^/]+)\/?$/.exec(url.pathname);
 return url.protocol==='https:'&&['flickr.com','www.flickr.com'].includes(url.hostname)&&!url.port&&!url.username&&!url.password&&!url.search&&!url.hash
  &&!!path&&ID.test(decodeURIComponent(path[1]!))&&decodeURIComponent(path[1]!)!=='0'&&decodeURIComponent(path[2]!)===photosetId;
 }catch{return false;}
}
export async function commitAlbumResolution(db:SqlStore,auth:RepairAuth,c:RepairContext,input:ResolveRequest,proof:AlbumResolutionProof):Promise<Status>{return safe(async()=>{
 request(input);
 let ids:string[];try{ids=contexts(proof.contextIds);}catch{fail('resolution_evidence_unavailable');}
 const proofUs=Date.parse(proof.observedAt)*1000;
 if(proof.photosetId!==input.selectedPhotosetId||proof.ownerNsid!==c.ownerNsid||proof.firstPhotoId!==c.firstPhotoId||!ids.includes(proof.photosetId)||!validUrl(proof.url,proof.photosetId))fail('selected_album_not_verified');
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.(?:\d{3}|\d{6})Z$/.test(proof.observedAt)||!Number.isSafeInteger(proofUs)||proofUs<c.observedAtUs-1000||proofUs>=c.deadlineAtUs)fail('resolution_evidence_unavailable');
 const [authId,digest,ownerSub]=identity(auth);
 const result=await db.batch([
  db.prepare(contextSql(auth)+`INSERT INTO album_create_repair_receipts(binding_id,attempt_id,expected_binding_revision,selected_photoset_id,navigation_url,
   owner_nsid,first_photo_binding_id,first_photo_id,link_revision,grant_generation,deployment_gate_revision,user_gate_revision,lifecycle,
   authority_kind,authority_id,authority_digest,authority_revision,context_observed_at_us,deadline_at_us,proof_context_ids,proof_observed_at_us,owner_sub,principal_revision,request_correlation_id)
  SELECT binding_id,attempt_id,binding_revision,?5,?6,owner_nsid,first_photo_binding_id,first_photo_id,link_revision,grant_generation,
   deployment_gate_revision,user_gate_revision,state,?7,authority_id,?2,authority_revision,?8,?9,?10,${NOW_US_SQL},?27,?28,?29 FROM context
  WHERE binding_id=?4 AND binding_revision=?12 AND attempt_id=?13 AND selected_photoset_id IS NULL AND flickr_photoset_id IS NULL
   AND materialization_state='create_outcome_unknown' AND repair_ready=1 AND authority_id=?14 AND authority_revision=?15
   AND user_id=?16 AND owner_nsid=?17 AND first_photo_binding_id=?18 AND first_photo_id=?19 AND link_revision=?20
   AND grant_generation=?21 AND deployment_gate_revision=?22 AND user_gate_revision=?23 AND state=?24
   AND observed_at_us<?9 AND ?11<=observed_at_us+1000 AND ?12=?25 AND ?13=?26 AND principal_revision=?28
   AND NOT EXISTS(SELECT 1 FROM album_bindings other WHERE other.owner_nsid=context.owner_nsid AND other.flickr_photoset_id=?5)
  RETURNING binding_id`).bind(authId,digest,ownerSub,c.bindingId,proof.photosetId,proof.url,auth.kind,c.observedAtUs,c.deadlineAtUs,JSON.stringify(ids),proofUs,
   c.bindingRevision,c.attemptId,c.authorityId,c.authorityRevision,c.userId,c.ownerNsid,c.firstPhotoBindingId,c.firstPhotoId,c.linkRevision,
   c.grantGeneration,c.deploymentGateRevision,c.userGateRevision,c.lifecycle,input.expectedBindingRevision,input.createAttemptId,ownerSub,c.principalRevision,crypto.randomUUID()),
  db.prepare(contextSql(auth)+'SELECT * FROM context').bind(authId,digest,ownerSub,c.bindingId),
  db.prepare(`SELECT 1 conflict FROM album_bindings WHERE owner_nsid=? AND flickr_photoset_id=? AND binding_id<>?`).bind(c.ownerNsid,input.selectedPhotosetId,c.bindingId),
 ]);
 const value=checked(result[1].results[0] as Row|undefined,auth);
 if(result[0].results.length>1 || result[0].results.length===1 && (result[0].results[0] as Row).binding_id!==c.bindingId)fail('service_unavailable');
 const prior=replay(value,auth,input);if(prior)return prior;
 if(result[2].results.length)fail('resolution_conflict');
 if(value.binding_revision!==c.bindingRevision)fail('stale_binding_revision');
 sameContext(repair(value,auth),c);fail('resolution_evidence_unavailable');
});}
function pageBounds(page:number,pageSize:number):void{if(!Number.isInteger(page)||page<1||page>1000||!Number.isInteger(pageSize)||pageSize<1||pageSize>100)fail('invalid_request');}
function pageResult(total:number,page:number,pageSize:number):{pages:number}{const pages=Math.ceil(total/pageSize);if(page>Math.max(1,pages))fail('page_out_of_range');return{pages};}
export async function readAlbumObligationPage(db:SqlStore,auth:RepairAuth,bindingId:string,page:number,pageSize:number):Promise<ObligationPage>{return safe(async()=>{
 pageBounds(page,pageSize);identity(auth);if(!UUID.test(bindingId))fail('invalid_request');
 const value=checked(await db.prepare(contextSql(auth)+`SELECT context.*,
  (SELECT COUNT(*) FROM album_obligation_status WHERE album_binding_id=binding_id) total,
  (SELECT json_group_array(json_object('id',obligation_id,'photo',photo_binding_id,'revision',obligation_revision,'state',state,'relationship',local_relationship,
   'observed',membership_observed_at_us))
  FROM (SELECT * FROM album_obligation_status WHERE album_binding_id=context.binding_id ORDER BY obligation_id LIMIT ?5 OFFSET ?6)) rows
  FROM context`).bind(...identity(auth),bindingId,pageSize,(page-1)*pageSize).first<Row>(),auth);
 const total=Number(value.total),items=JSON.parse(String(value.rows)) as Row[];
 const obligations=items.map(item=>({obligation:{fgaAlbumObligationId:String(item.id),fgaAlbumBindingId:bindingId,fgaPhotoBindingId:String(item.photo),obligationRevision:Number(item.revision)},
  state:item.state as ObligationStatus['state'],membershipObservedAt:timestamp(item.observed),localRelationship:item.relationship as 'active'|'archived'}));
 if(obligations.some(o=>o.state==='membership_verified'&&o.membershipObservedAt===null))fail('service_unavailable');
 return{schemaVersion:1,fgaAlbumBindingId:bindingId,bindingRevision:Number(value.binding_revision),page,pageSize,...pageResult(total,page,pageSize),total,obligations};
});}
export async function readAlbumRepairPage(db:SqlStore,auth:RepairAuth,page:number,pageSize:number):Promise<RepairPage>{return safe(async()=>{
 if(auth.kind!=='admin')fail('forbidden');pageBounds(page,pageSize);
 const value=await db.prepare(`WITH auth AS (${authority(auth)}), repairs AS (SELECT b.*,a.attempt_id FROM auth JOIN album_bindings b ON b.user_id=auth.user_id
  JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=auth.user_id
  JOIN album_materialization_attempts a ON a.binding_id=b.binding_id AND a.dispatch_count=1 AND a.state='create_outcome_unknown'
  WHERE b.materialization_state='create_outcome_unknown' AND b.flickr_photoset_id IS NULL)
  SELECT (SELECT COUNT(*) FROM repairs) total,(SELECT json_group_array(json_object('fgaAlbumBindingId',binding_id,'bindingRevision',binding_revision,
  'fgaPublishServiceId',service_id,'localCollectionIdentifier',local_collection_id,'desiredTitle',desired_title,
  'localLifecycle',CASE WHEN state='materialization_pending' THEN 'active' ELSE state END,'createAttemptId',attempt_id))
  FROM (SELECT * FROM repairs ORDER BY binding_id LIMIT ?4 OFFSET ?5)) rows FROM auth`)
  .bind(...identity(auth),pageSize,(page-1)*pageSize).first<Row>();
 if(!value)fail('unauthorized');const total=Number(value.total);return{schemaVersion:1,page,pageSize,...pageResult(total,page,pageSize),total,repairs:JSON.parse(String(value.rows)) as RepairSummary[]};
});}
