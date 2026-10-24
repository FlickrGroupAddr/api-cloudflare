// MIT License; copyright 2026 Terry Ott.
// Trusted Root SOURCE seam. No JSON/env/request loader or qualification factory.
import {createHash} from 'node:crypto';
import {publishReviewedEvidence, type OperatorPublicationAuthority} from '../pmb1-runtime-evidence/operator.ts';
import type {PreparedPublication} from '../pmb1-runtime-evidence/publication-plan.ts';
import {createFreshNativeSource, type FreshNativeSourceInput, type FreshNativeOwner} from '../pmb1-fresh-native-capture/source.ts';
import {captureSupportedBoundary} from '../pmb1-native-object-reader/object-kv-interface.ts';
import {closedRestorationCheck} from '../pmb1-retained-integration/ordinary.ts';
import type {PrivateMainRuntime, PrivateMainTarget} from '../pmb1-fresh-native-capture/main-private-core.ts';
import type {OwningPartitionRuntime} from '../pmb1-fresh-native-capture/owning-core.ts';
import type {RuntimeEvidenceLedger, RuntimeEvidencePacket, EvidenceReference} from '../pmb1-runtime-evidence/ledger.ts';
import type {PartitionCapture} from '../../src/partition_maintenance.ts';
import type {PartitionMaintenance} from '../../src/partition_maintenance.ts';
import {Pmb1NativeWakeup} from '../pmb1-native-wakeup/candidate.ts';
import {NativePartitionDisposition} from '../pmb1-native-disposition/partition.ts';

export interface NativeCost {
  requests:number;reader_queries:number;receipt_reads:number;metadata_reads:number;authenticated_checks:number;
  mutations:number;creates:number;deletes:number;sql_statements:number;effects:number;outbound_bytes:number;
  inbound_bytes:number;artifact_bytes:number;challenges:number;captures:number;
}
export interface QualifiedNativeLeaf {
  ordinal:number;identity:string;source_path:string;source_pin:string;method:string;resource:string;
  request_digest:string;cost:NativeCost|null;
}
export interface NativeLease {
  key:string;context_digest:string;source_pin:string;profile:string;object_profile:string;
  leaves:readonly QualifiedNativeLeaf[];
}
/** Same exact API as native_journal.SQLiteNativeBroker. Root owns the concrete
 * process/SDK capability: this interface neither constructs one nor authorizes
 * adoption of a cold journal. Python/Node ownership remains explicit. */
export interface NativeJournal {
  reserve_tree(lease:NativeLease):Promise<void>;
  begin_subtree(lease:NativeLease,first:number,through:number,identity:string,requestDigest:string):Promise<void>;
  finish_subtree(lease:NativeLease,first:number,through:number,receipts:readonly {
    ordinal:number;identity:string;request_digest:string;actual_cost:NativeCost;evidence:Uint8Array;
  }[]):Promise<void>;
  mark_unknown(lease:NativeLease,reason:string):Promise<void>;
}
export type NativeStep =
  | {kind:'main-current';domainDatabaseId:string;operationId:string}
  | {kind:'main-stop'|'main-assess';target:PrivateMainTarget;operationId:string}
  | {kind:'owner-stop'|'owner-close'|'owner-reopen';resource:string;generation:string;operationId:string}
  | {kind:'owner-reconcile';resource:string;capture:PartitionCapture;operationId:string}
  | {kind:'owner-acquire';resource:string;reference:EvidenceReference;packetPin:string}
  | {kind:'owner-control-readback';resource:string;generation:string}
  | {kind:'publication';database:D1Database;prepared:PreparedPublication;authority:OperatorPublicationAuthority;now:()=>number}
  | {kind:'capture';input:FreshNativeSourceInput;namespaces:Record<string,DurableObjectNamespace<FreshNativeOwner>>;
      ledger:RuntimeEvidenceLedger;envelope:RuntimeEvidencePacket}
  | {kind:'ordinary';request:Request;database:D1Database;readEnabled:string}
  | {kind:'operator-create-version';identity:object;module:Uint8Array;sha2:string;metadata:object;accessToken:string;key:string}
  | {kind:'operator-inspect-version'|'operator-deploy-version';identity:object;version:object;key:string}
  | {kind:'operator-inspect-deployment';identity:object;version:object;deployment:object;key:string}
  | {kind:'operator-disable'|'operator-endpoint'|'operator-delete'|'operator-inspect-worker';identity:object;key:string}
  | {kind:'operator-restore';identity:object;version:object;preflight:object;key:string}
  | {kind:'operator-assert-endpoint';identity:object;endpoint:string;key:string}
  | {kind:'case-challenge';caseNumber:number;phase?:'guard'|'post-restore'}
  | {kind:'declared-interruption';reason:'partial_output'|'timeout'|'unknown_restore'|'unknown_cleanup'};
/** Named methods match the concrete Python owner in native_program.py and
 * native_operator.py. A Root-held cross-runtime SDK adapter supplies these exact
 * capabilities; no aggregate maintain/upload/deploy callback is accepted. */
export interface OperatorSDKBindings {
  create_version(identity:object,module:Uint8Array,sha2:string,metadata:object,accessToken:string,key:string):Promise<unknown>;
  inspect_version(identity:object,version:object,key:string):Promise<unknown>;
  deploy_version(identity:object,version:object,key:string):Promise<unknown>;
  inspect_deployment(identity:object,version:object,deployment:object,key:string):Promise<unknown>;
  disable_worker(identity:object,key:string):Promise<unknown>;
  inspect_endpoint(identity:object,key:string):Promise<unknown>;
  delete_worker(identity:object,key:string):Promise<unknown>;
  inspect_worker(identity:object,key:string):Promise<unknown>;
  restore_retained_version(identity:object,version:object,preflight:object,key:string):Promise<unknown>;
  assert_endpoint(identity:object,endpoint:string,key:string):Promise<unknown>;
}
export interface NativeBindings {
  main?:Pick<PrivateMainRuntime,'currentMain'|'stopAdmission'|'assessStopped'>;
  owners:ReadonlyMap<string,Pick<OwningPartitionRuntime,'maintenanceStop'|'maintenanceClose'|'maintenanceReopen'|'maintenanceReconcile'|'acquireFresh'>>;
  operator?:OperatorSDKBindings;
  challenge?:NativeCaseBindings;
  ownerStorage?:ReadonlyMap<string,Pick<DurableObjectStorage,'sql'|'transaction'>>;
}
/** Execute only in the qualified owning context; no SQL/storage capability is
 * sent over an RPC and no unsupported owner readback endpoint is invented. */
export async function readClosedOwnerControl(storage:Pick<DurableObjectStorage,'sql'|'transaction'>,generation:string):Promise<unknown>{
  if(!/^[1-9][0-9]{0,18}$/.test(generation)||BigInt(generation)>9223372036854775807n)throw Error('native_readback_generation');
  return storage.transaction(async tx=>{
    const rows=storage.sql.exec("SELECT singleton_id,typeof(singleton_id) kt,CAST(generation AS TEXT) generation,typeof(generation) gt,state,typeof(state) st FROM maintenance_control LIMIT 2").toArray();
    const admission=await tx.get('pmb1:admission'),row=rows[0];
    if(rows.length!==1||row.singleton_id!==1||row.kt!=='integer'||row.gt!=='integer'||row.st!=='text'
      ||row.generation!==generation||row.state!=='closed'||admission!==false)throw Error('native_closed_owner_readback_refused');
    return{generation:row.generation,state:row.state,admission};
  });
}
export interface NativeCaseBindings {
  domain:D1Database;storage:Pick<DurableObjectStorage,'sql'|'transaction'>;
  owner:Pick<OwningPartitionRuntime,'maintenanceStop'>;bridge:PartitionMaintenance;
  originalGeneration:string;temporaryGeneration:string;admitted?:PartitionCapture;
  ledger:RuntimeEvidenceLedger;expiredReference:EvidenceReference;
  /** Independently frozen SOURCE guard DDL, never discovered from the target
   * as an expected oracle. Missing entries refuse rather than restoring guesses. */
  expectedGuards:Readonly<Record<string,string>>;
}
/** Named, fixed challenge source shared by a qualified Root case and controlled
 * fixtures. SQL is source-owned; no supplied SQL or operation callback exists. */
export async function invokeInheritedNativeChallenge(caseNumber:number,c:NativeCaseBindings):Promise<unknown>{
  const denied=async(fn:()=>unknown)=>{try{await fn();}catch(e){
    if(e instanceof Error&&/maintenance_closed|fenced|invalid_control|evidence_(header|review)/.test(e.message))return;
    throw e;}throw Error('native_guard_unexpectedly_allowed');};
  const query=(sql:string)=>c.domain.withSession('first-primary').prepare(sql).all();
  if(caseNumber===1){await denied(()=>c.storage.sql.exec("INSERT INTO pmb1_partition_binding VALUES(1,'forbidden')").toArray());}
  else if(caseNumber===2){if(!c.admitted)throw Error('native_before_close_admission_missing');await denied(()=>c.bridge.admit(c.admitted!));}
  else if(caseNumber===3){
    await denied(()=>c.storage.sql.exec("INSERT INTO pmb1_partition_binding VALUES(1,'stale') ON CONFLICT(id) DO UPDATE SET partition_id='stale'").toArray());
    await denied(()=>c.storage.sql.exec("INSERT OR REPLACE INTO pmb1_partition_binding VALUES(1,'stale')").toArray());
    await denied(()=>query("DELETE FROM fga_users WHERE user_id='synthetic-parent'"));
  }else if(caseNumber===5){await denied(()=>c.owner.maintenanceStop(c.temporaryGeneration,crypto.randomUUID()));}
  else if(caseNumber===6){await denied(()=>c.ledger.reserve(c.expiredReference));}
  else if(caseNumber===7){
    for(const generation of [c.originalGeneration,c.temporaryGeneration])await denied(()=>c.owner.maintenanceStop(generation,crypto.randomUUID()));
  }else if(caseNumber===8){
    for(const sql of ["INSERT INTO audit_events(event_id,action,request_correlation_id,outcome,reason) VALUES('scheduled','scheduled','correlation','failed','source')",
      "INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id) VALUES('session','"+'a'.repeat(64)+"','user','"+'b'.repeat(43)+"',1,1,2,1,'source')",
      "INSERT INTO audit_events(event_id,action,request_correlation_id,outcome,reason) VALUES('auth-failure','authentication','correlation','failed','source')",
      "INSERT INTO status_read_buckets VALUES('installation','synthetic',100000000,1)"])await denied(()=>query(sql));
  }else if(caseNumber===9){
    const absent=new NativePartitionDisposition(),wake=new Pmb1NativeWakeup(c.storage,absent.verify);
    await denied(()=>wake.schedule(c.temporaryGeneration,'service-entry',1));await denied(()=>wake.admitCurrentDue());await denied(()=>wake.alarm());
  }else if(caseNumber===10||caseNumber===11){
    const insert=c.expectedGuards.pmb1_wake_work_insert,del=c.expectedGuards.pmb1_wake_work_delete;
    if(!insert||!del)throw Error('native_independent_guard_source_missing');
    c.storage.sql.exec('DROP TRIGGER pmb1_wake_work_insert');
    c.storage.sql.exec("INSERT INTO pmb1_wake_work VALUES(1,'1','operator-bypass',NULL)");
    if(caseNumber===11){c.storage.sql.exec('DROP TRIGGER pmb1_wake_work_delete');c.storage.sql.exec('DELETE FROM pmb1_wake_work');
      c.storage.sql.exec(insert);c.storage.sql.exec(del);}
    throw Error('native_known_preservation_violation');
  }else throw Error('native_challenge_case_requires_declared_terminal_stage');
  return{outcome:'expected-source-denial',caseNumber};
}

/** The SAME direct inherited call body is used by qualified Root composition
 * and the fixed SOURCE harness. It accepts named SDK references, never a caller
 * callback called operation(), and creates no transport/namespace/resource. */
export async function invokeInheritedNativeStep(bindings:NativeBindings,step:NativeStep):Promise<unknown>{
  if(step.kind==='case-challenge'){
    if(!bindings.challenge)throw Error('native_exact_challenge_sdk_bindings_missing');
    return invokeInheritedNativeChallenge(step.caseNumber===7&&step.phase==='guard'?1:step.caseNumber,bindings.challenge);
  }
  if(step.kind==='owner-control-readback'){
    const storage=bindings.ownerStorage?.get(step.resource);if(!storage)throw Error('native_qualified_owning_context_required');
    return readClosedOwnerControl(storage,step.generation);
  }
  if(step.kind==='main-current'||step.kind==='main-stop'||step.kind==='main-assess'){
    if(!bindings.main)throw Error('native_exact_main_binding_missing');
    if(step.kind==='main-current')return bindings.main.currentMain(step.domainDatabaseId,step.operationId);
    if(step.kind==='main-stop')return bindings.main.stopAdmission(step.target,step.operationId);
    return bindings.main.assessStopped(step.target,step.operationId);
  }
  if(step.kind==='publication')return publishReviewedEvidence(step.database,step.prepared,step.authority,step.now);
  if(step.kind==='capture'){
    const source=await createFreshNativeSource(step.input,step.namespaces,step.ledger,step.envelope);
    return captureSupportedBoundary(source,step.input.request);
  }
  if(step.kind==='ordinary')return closedRestorationCheck(step.request,step.database,step.readEnabled);
  if(step.kind==='declared-interruption')throw Error('native_declared_'+step.reason);
  if(step.kind.startsWith('operator-')){
    const sdk=bindings.operator;if(!sdk)throw Error('native_exact_operator_sdk_binding_missing');
    if(step.kind==='operator-create-version')return sdk.create_version(step.identity,step.module,step.sha2,step.metadata,step.accessToken,step.key);
    if(step.kind==='operator-inspect-version')return sdk.inspect_version(step.identity,step.version,step.key);
    if(step.kind==='operator-deploy-version')return sdk.deploy_version(step.identity,step.version,step.key);
    if(step.kind==='operator-inspect-deployment')return sdk.inspect_deployment(step.identity,step.version,step.deployment,step.key);
    if(step.kind==='operator-disable')return sdk.disable_worker(step.identity,step.key);
    if(step.kind==='operator-endpoint')return sdk.inspect_endpoint(step.identity,step.key);
    if(step.kind==='operator-delete')return sdk.delete_worker(step.identity,step.key);
    if(step.kind==='operator-inspect-worker')return sdk.inspect_worker(step.identity,step.key);
    if(step.kind==='operator-restore')return sdk.restore_retained_version(step.identity,step.version,step.preflight,step.key);
    if(step.kind==='operator-assert-endpoint')return sdk.assert_endpoint(step.identity,step.endpoint,step.key);
    throw Error('native_unknown_operator_step');
  }
  if(!('resource' in step))throw Error('native_unknown_step');
  const owner=bindings.owners.get(step.resource);
  if(!owner)throw Error('native_exact_owner_binding_missing');
  if(step.kind==='owner-stop')return owner.maintenanceStop(step.generation,step.operationId);
  if(step.kind==='owner-close')return owner.maintenanceClose(step.generation,step.operationId);
  if(step.kind==='owner-reopen')return owner.maintenanceReopen(step.generation,step.operationId);
  if(step.kind==='owner-reconcile')return owner.maintenanceReconcile(step.capture,step.operationId);
  if(step.kind==='owner-acquire')return owner.acquireFresh(step.reference,step.packetPin);
  throw Error('native_unknown_owner_step');
}

export interface ReviewedNativeCall {
  stage:string;step:NativeStep;
  /** Contiguous, exact expanded subtree. First leaf is the physical outer call
   * dispatch marker; every descendant was reserved before that opaque call. */
  firstLeaf:number;throughLeaf:number;
}
export interface NativeObservedLeaf {identity:string;requestDigest:string;cost:NativeCost;evidence:Uint8Array;}
export interface RootNativeAuthority {
  /** Root externally authenticates meaning, source/holder attribution, current
   * genuine packet, SDK/meter capabilities and independent review. Returning
   * labels/hashes from an unqualified object does not perform that work. */
  assertCurrent(facts:ReviewedNativeFacts):void;
  /** Qualified instrumented SDK holder installs a synchronous before-EVERY-leaf
   * identity/order/counter fence against the already reserved subtree. Missing
   * source attribution, unknown wire/effects or unobservable RPC internals must
   * throw here, BEFORE the outer invocation. This is not a success flag. */
  armPhysicalFence(call:ReviewedNativeCall,leaves:readonly QualifiedNativeLeaf[]):void;
  /** Independent exact receipt/complete-oracle checks return all observed
   * leaves, including SQL preflights, KV/alarm, effects and bookkeeping. */
  verifyPhysicalReceipt(call:ReviewedNativeCall,result:unknown):readonly NativeObservedLeaf[];
}
/** A typed trusted SOURCE carrier, not an authentication mechanism. No actual
 * instance exists in this package. Only genuine Root composition may provide
 * actual SDK/journal/oracle references and independently qualified facts. */
export interface ReviewedNativeFacts {
  scope:'QUALIFIED_ROOT'|'SOURCE_KNOWN_MODEL_ONLY';caseNumber:number;
  tableCount:number;schemaObjects:number;programDigest:string;packetDigest:string;
  population:readonly string[];generations:readonly string[];
  rootRecord:string;reviewRecord:string;author:string;reviewer:string;
  starts:number;deadline:number;baselineFreshness:number;baselineAt:number|null;restoredAt:number|null;
  lease:NativeLease;calls:readonly ReviewedNativeCall[];bindings:NativeBindings;journal:NativeJournal;
  root:RootNativeAuthority;clock:()=>number;sourceCheck:()=>string;
}
const limits:NativeCost={requests:160,reader_queries:96,receipt_reads:20,metadata_reads:4,authenticated_checks:4,
  mutations:32,creates:2,deletes:2,sql_statements:256,effects:2048,outbound_bytes:4194304,
  inbound_bytes:16777216,artifact_bytes:8388608,challenges:12,captures:3};
const digest=(v:string)=>/^[a-f0-9]{64}$/.test(v);
function canonical(value:unknown):string{
  if(value instanceof Uint8Array)return JSON.stringify({sourceBytes:Buffer.from(value).toString('hex')});
  if(value===null||typeof value!=='object')return JSON.stringify(value);
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}';
}
const sha=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
function stepProjection(step:NativeStep):unknown{
  if(step.kind==='publication')return{kind:step.kind,header:step.prepared.header,
    payloadDigest:sha(step.prepared.payloadText),authority:step.authority};
  if(step.kind==='capture')return{kind:step.kind,input:step.input,envelope:step.envelope};
  if(step.kind==='ordinary')return{kind:step.kind,url:step.request.url,method:step.request.method,
    headersDigest:sha([...step.request.headers]),readEnabled:step.readEnabled};
  return step;
}
function copyStep(step:NativeStep):NativeStep{
  if(step.kind==='publication')return Object.freeze({...step,prepared:structuredClone(step.prepared)});
  if(step.kind==='capture')return Object.freeze({...step,input:structuredClone(step.input)});
  if(step.kind==='ordinary')return Object.freeze({...step,request:step.request.clone()});
  return Object.freeze(structuredClone(step));
}
/** Byte identities, never authentication. Root independently authenticates this
 * exact derived program against its frozen SOURCE-owned NativeProgram and
 * qualified resources/cost tree. Echoing this digest does not do that work. */
export function nativeProgramDigest(f:ReviewedNativeFacts):string{
  return sha({caseNumber:f.caseNumber,population:f.population,generations:f.generations,
    lease:f.lease,calls:f.calls.map(c=>({stage:c.stage,firstLeaf:c.firstLeaf,throughLeaf:c.throughLeaf,step:stepProjection(c.step)}))});
}
export function nativePacketDigest(f:ReviewedNativeFacts):string{
  return sha({programDigest:nativeProgramDigest(f),scope:f.scope,rootRecord:f.rootRecord,reviewRecord:f.reviewRecord,
    author:f.author,reviewer:f.reviewer,starts:f.starts,deadline:f.deadline,baselineFreshness:f.baselineFreshness,
    baselineAt:f.baselineAt,restoredAt:f.restoredAt,tableCount:f.tableCount,schemaObjects:f.schemaObjects});
}
function cost(value:NativeCost|null):asserts value is NativeCost{
  if(!value||Object.keys(value).sort().join()!==Object.keys(limits).sort().join()
    ||Object.entries(value).some(([key,v])=>!Number.isSafeInteger(v)||v<0||v>limits[key as keyof NativeCost])
    ||value.requests>1||value.sql_statements>8||value.outbound_bytes>65536||value.inbound_bytes>262144
    ||(value.reader_queries>0&&value.outbound_bytes>32768)
    ||value.reader_queries+value.receipt_reads+value.metadata_reads+value.authenticated_checks+value.mutations+value.creates+value.deletes!==value.requests)
    throw Error('native_unknown_or_invalid_cost');
}
/** Concrete disabled-by-default SOURCE execution body. No credential, provider,
 * deployment or actual qualification is obtained by constructing facts or by
 * passing execute=true. The genuine Root external premise still must hold. */
export async function executeReviewedNativeProgram(facts?:ReviewedNativeFacts,execute=false):Promise<{
  scope:ReviewedNativeFacts['scope'];qualification:'NO_GO';status:'source_execution_complete';
}>{
  if(!execute||!facts)throw Error('native_dispatch_disabled');
  const f=facts,lease=f.lease;
  const positive=(n:number)=>Number.isSafeInteger(n)&&n>0;
  const finite=(n:number)=>typeof n==='number'&&Number.isFinite(n)&&n>=0;
  if(!positive(f.tableCount)||!positive(f.schemaObjects))throw Error('native_schema_inventory_invalid');
  if(f.tableCount>8||f.schemaObjects>64)throw Error('selected_candidate_exceeds_accepted_miniature_allocation');
  if(!digest(f.programDigest)||!digest(f.packetDigest)||!digest(f.rootRecord)||!digest(f.reviewRecord)
    ||typeof f.author!=='string'||typeof f.reviewer!=='string'||!f.author.trim()||!f.reviewer.trim()
    ||!/^[\x20-\x7e]+$/.test(f.author)||!/^[\x20-\x7e]+$/.test(f.reviewer)
    ||f.author.trim().toLocaleLowerCase('en-US')===f.reviewer.trim().toLocaleLowerCase('en-US')
    ||!Array.isArray(f.population)||f.population.length===0||f.population.length>16||new Set(f.population).size!==f.population.length
    ||f.population.some(r=>typeof r!=='string'||!r||r!==r.trim())||!Array.isArray(f.generations)||f.population.length!==f.generations.length
    ||f.generations.some(g=>typeof g!=='string'||!/^[1-9][0-9]{0,18}$/.test(g)||BigInt(g)>9223372036854775807n)
    ||!['QUALIFIED_ROOT','SOURCE_KNOWN_MODEL_ONLY'].includes(f.scope)
    ||lease.profile!=='pmb1-private-application-no-real-v1'||lease.object_profile!=='pmb1-private-object-kv-interface-v1'
    ||!positive(f.caseNumber)||f.caseNumber>12||!finite(f.starts)||!finite(f.deadline)||f.deadline<=f.starts||f.deadline-f.starts>1200
    ||!finite(f.baselineFreshness)||f.baselineFreshness<=0||f.baselineFreshness>60
    ||(f.baselineAt!==null&&(!finite(f.baselineAt)||f.baselineAt<f.starts||f.baselineAt>=f.deadline))
    ||(f.restoredAt!==null&&(!finite(f.restoredAt)||f.restoredAt<f.starts||f.restoredAt>=f.deadline))
    ||!Array.isArray(lease.leaves)||!lease.leaves.length||!Array.isArray(f.calls)||!f.calls.length)
    throw Error('native_reviewed_context_binding');
  if(!digest(lease.context_digest)||!digest(lease.source_pin)||typeof lease.key!=='string'||!lease.key.trim())throw Error('native_lease_binding');
  const stages=['settle','close','closure_readback','baseline','challenge','challenge_readback','temporary_install','preflight',
    'admission_off','restore','restore_readback','restored','cleanup','cleanup_readback'];
  const expectedStages=f.caseNumber===12?[...stages.slice(0,4),'interruption']:stages;
  if(f.scope==='QUALIFIED_ROOT'){
    const observed=f.calls.map(c=>c.stage).filter((s,i,a)=>i===0||s!==a[i-1]);
    if(canonical(observed)!==canonical(expectedStages))throw Error('native_source_case_stage_inventory');
  }
  if(f.calls.some(c=>!expectedStages.includes(c.stage)||c.step.kind==='owner-reopen'))throw Error('native_source_case_call_not_permitted');
  const allowed:Record<string,readonly string[]>={
    settle:['main-current','main-stop','main-assess','publication','operator-inspect-version'],
    close:['owner-stop','owner-close'],closure_readback:['main-current','owner-control-readback'],baseline:['publication','capture'],
    challenge:['case-challenge'],
    challenge_readback:['main-current','owner-control-readback'],
    temporary_install:['operator-create-version','operator-inspect-version','operator-deploy-version','operator-inspect-deployment'],
    preflight:['publication','capture'],admission_off:['owner-stop','operator-disable','operator-endpoint'],
    restore:['operator-restore'],restore_readback:['operator-inspect-version','operator-inspect-deployment','operator-endpoint','operator-assert-endpoint','ordinary','main-current'],
    restored:['publication','capture','case-challenge'],cleanup:['operator-delete'],cleanup_readback:['operator-inspect-worker'],interruption:['declared-interruption']};
  if(f.calls.some(c=>!allowed[c.stage]?.includes(c.step.kind)))throw Error('native_source_stage_method_mismatch');
  if(f.calls.some(c=>(c.step.kind==='case-challenge'&&c.step.caseNumber!==f.caseNumber)
    ||(c.step.kind==='declared-interruption'&&c.step.reason!=='partial_output')))throw Error('native_source_case_method_identity');
  if(f.caseNumber===7&&f.scope==='QUALIFIED_ROOT'){
    if(f.calls.some(c=>c.step.kind==='case-challenge'&&((c.stage==='challenge'&&c.step.phase!=='guard')
      ||(c.stage==='restored'&&c.step.phase!=='post-restore')))
      ||!f.calls.some(c=>c.stage==='restored'&&c.step.kind==='case-challenge'&&c.step.phase==='post-restore'))throw Error('native_both_generations_require_post_restore_check');
  }
  if(f.scope==='QUALIFIED_ROOT'){
    const sequence=(stage:string)=>f.calls.filter(c=>c.stage===stage).map(c=>c.step.kind);
    for(const [stage,required]of Object.entries({temporary_install:['operator-create-version','operator-inspect-version','operator-deploy-version','operator-inspect-deployment'],
      restore:['operator-restore'],restore_readback:['operator-inspect-version','operator-inspect-deployment','operator-endpoint','operator-assert-endpoint','ordinary'],
      cleanup:['operator-delete'],cleanup_readback:['operator-inspect-worker']})){
      if(!expectedStages.includes(stage))continue;
      if(canonical(sequence(stage))!==canonical(required))throw Error('native_exact_operator_stage_order');
    }
  }
  if(nativeProgramDigest(f)!==f.programDigest||nativePacketDigest(f)!==f.packetDigest)throw Error('native_program_or_packet_digest_drift');
  const callPlan=f.calls.map(call=>Object.freeze({...call,step:copyStep(call.step)}));
  if(nativeProgramDigest({...f,calls:callPlan})!==f.programDigest)throw Error('native_descriptor_snapshot_drift');
  const total={...limits};for(const key of Object.keys(total) as (keyof NativeCost)[])total[key]=0;
  const identities=new Set<string>();
  lease.leaves.forEach((leaf:QualifiedNativeLeaf,index:number)=>{
    if(leaf.ordinal!==index||!digest(leaf.source_pin)||!digest(leaf.request_digest)||!leaf.identity||identities.has(leaf.identity)
      ||!leaf.method||!leaf.resource||typeof leaf.source_path!=='string'||leaf.source_path.includes('\\')||leaf.source_path.includes(':')
      ||leaf.source_path.split('/').some((p:string)=>!p||p==='.'||p==='..'))throw Error('native_exact_leaf_identity');
    identities.add(leaf.identity);
    cost(leaf.cost);for(const key of Object.keys(total) as (keyof NativeCost)[])total[key]+=leaf.cost[key];
  });
  if(Object.entries(total).some(([key,v])=>v>limits[key as keyof NativeCost]))throw Error('native_tree_budget');
  let previous=f.starts,expectedLeaf=0,latched=false,baselineAt=f.baselineAt,restoredAt=f.restoredAt,completedRestore=false;
  const originalProgram=f.programDigest,originalPacket=f.packetDigest,originalLease=sha(lease);
  const bound={bindings:f.bindings,journal:f.journal,root:f.root,clock:f.clock,sourceCheck:f.sourceCheck};
  const check=(end=f.deadline)=>{
    const n=f.clock();if(!Number.isFinite(n)||n<previous||n<f.starts||n>=Math.min(end,f.deadline))throw Error('native_clock_or_deadline');previous=n;
    if(f.sourceCheck()!==lease.source_pin)throw Error('native_source_drift');
    const rootResult=f.root.assertCurrent(f);if(rootResult!==undefined)throw Error('native_root_assertion_must_complete_synchronously');
    if(f.sourceCheck()!==lease.source_pin)throw Error('native_post_root_source_drift');
    if(f.programDigest!==originalProgram||f.packetDigest!==originalPacket||f.lease!==lease||sha(lease)!==originalLease
      ||nativeProgramDigest(f)!==originalProgram||nativePacketDigest(f)!==originalPacket
      ||nativeProgramDigest({...f,calls:callPlan})!==originalProgram
      ||f.bindings!==bound.bindings||f.journal!==bound.journal||f.root!==bound.root||f.clock!==bound.clock||f.sourceCheck!==bound.sourceCheck)
      throw Error('native_current_context_identity_drift');
    const after=f.clock();if(!Number.isFinite(after)||after<previous||after>=Math.min(end,f.deadline))throw Error('native_post_root_deadline');previous=after;
  };
  try{
    check();
    if((baselineAt!==null&&baselineAt>previous)||(restoredAt!==null&&restoredAt>previous))throw Error('native_future_observation_anchor');
    const reserveEnd=Math.min(previous+60,f.deadline);
    await f.journal.reserve_tree(lease);latched=true;check(reserveEnd);
    for(const call of callPlan){
      check();const start=previous;
      if((call.stage==='preflight'&&baselineAt===null)||(call.stage==='restored'&&restoredAt===null))throw Error('native_fresh_observation_missing');
      const end=Math.min(start+60,f.deadline,call.stage==='preflight'?baselineAt!+f.baselineFreshness:f.deadline,
        call.stage==='restored'?restoredAt!+f.baselineFreshness:f.deadline);
      check(end);
      if(call.step.kind==='case-challenge'&&f.caseNumber===7&&call.step.phase==='post-restore'&&!completedRestore)throw Error('native_post_restore_stage_not_completed');
      if(call.firstLeaf!==expectedLeaf||call.throughLeaf<call.firstLeaf||call.throughLeaf>=lease.leaves.length)throw Error('native_subtree_order');
      const subtree=lease.leaves.slice(call.firstLeaf,call.throughLeaf+1);
      const armed=f.root.armPhysicalFence(call,subtree);if(armed!==undefined)throw Error('native_physical_fence_must_complete_synchronously');check(end);
      const outer=subtree[0]!;
      await f.journal.begin_subtree(lease,call.firstLeaf,call.throughLeaf,outer.identity,outer.request_digest);check(end);
      const result=await invokeInheritedNativeStep(f.bindings,call.step);check(end);
      if(f.caseNumber===4&&call.step.kind==='owner-close')throw Error('native_declared_close_ack_unknown');
      if(call.step.kind==='case-challenge'&&[5,6].includes(f.caseNumber))throw Error('native_declared_shared_reuse_refusal');
      const observed=f.root.verifyPhysicalReceipt(call,result);check(end);
      if(!Array.isArray(observed))throw Error('native_synchronous_physical_receipt_required');
      const observations=observed.map((o:NativeObservedLeaf)=>Object.freeze({...o,cost:Object.freeze({...o.cost}),evidence:o.evidence.slice()}));
      if(observations.length!==subtree.length)throw Error('native_incomplete_physical_trace');
      for(let i=0;i<subtree.length;i++){
        const leaf=subtree[i]!,observed=observations[i]!;cost(observed.cost);
        if(observed.identity!==leaf.identity||observed.requestDigest!==leaf.request_digest
          ||Object.entries(observed.cost).some(([key,v])=>v>leaf.cost![key as keyof NativeCost]))throw Error('native_physical_receipt_drift_or_overrun');
      }
      await f.journal.finish_subtree(lease,call.firstLeaf,call.throughLeaf,observations.map((observed,i)=>({
        ordinal:subtree[i]!.ordinal,identity:observed.identity,request_digest:observed.requestDigest,
        actual_cost:observed.cost,evidence:observed.evidence})));check(end);
      expectedLeaf=call.throughLeaf+1;
      if(call.stage==='baseline')baselineAt=start;
      if(call.stage==='restore_readback')restoredAt=previous;
      if(call.stage==='restore_readback'&&call.step.kind==='ordinary')completedRestore=true;
    }
    check();if(expectedLeaf!==lease.leaves.length)throw Error('native_unconsumed_tree');
    return{scope:f.scope,qualification:'NO_GO',status:'source_execution_complete'};
  }catch(error){if(latched){try{await f.journal.mark_unknown(lease,'native_source_receipt_or_journal_unknown');}catch{throw Error('native_terminal_ack_unknown');}}throw error;}
}
