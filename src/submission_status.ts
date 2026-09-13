import type {SqlStore} from "./admission.ts";
import {NOW_US_SQL as NOW,errorResponse} from "./installations.ts";
export interface StatusAuth {family:"installation"|"admin";userId:string;subjectId:string;proof:string;}
export interface StatusQuery {view:"active"|"attention"|"history";size:number;binding:string|null;beforeUs:string|null;beforeId:string|null;}
export class StatusError extends Error {readonly status:number;readonly retryAfter:number|null;constructor(code:string,status=400,retryAfter:number|null=null){super(code);this.status=status;this.retryAfter=retryAfter;}}
const ID=/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const STATES=["queued","attempting","retrying","throttled","added","moderation_submitted","delivery_uncertain","needs_attention","cancelled"];
const ACTIVE=["queued","attempting","retrying","throttled"];
export function statusTimestamp(value:unknown):string|null{
 if(value===null)return null;
 if(typeof value!=="string"||! /^-?\d+$/.test(value))throw new StatusError("status_projection_invalid",500);
 const us=BigInt(value),ms=us>=0n?us/1000n:(us-999n)/1000n;
 try{return new Date(Number(ms)).toISOString().replace("Z",(us-ms*1000n).toString().padStart(3,"0")+"Z");}
 catch{throw new StatusError("status_projection_invalid",500);}
}
function parseTimestamp(value:string):string{
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value))throw new StatusError("invalid_status_continuation");
 const date=new Date(value.slice(0,23)+"Z");
 if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,23)!==value.slice(0,23))throw new StatusError("invalid_status_continuation");
 return (BigInt(date.getTime())*1000n+BigInt(value.slice(23,26))).toString();
}
export function parseStatusQuery(url:URL,item=false):StatusQuery{
 const p=url.searchParams;
 if(url.search.length>2048||item&&url.search||[...p.keys()].some(key=>!["view","page_size","photo_binding_id","before_created_at","before_intent_id"].includes(key))||[...new Set(p.keys())].some(key=>p.getAll(key).length!==1))throw new StatusError("invalid_status_query");
 const view=p.get("view")??"active",size=p.get("page_size")??"50",binding=p.get("photo_binding_id");
 if(!["active","attention","history"].includes(view)||! /^[1-9]\d{0,2}$/.test(size)||Number(size)>100||binding!==null&&!ID.test(binding))throw new StatusError("invalid_status_query");
 if(p.has("before_created_at")!==p.has("before_intent_id"))throw new StatusError("invalid_status_continuation");
 let beforeUs:string|null=null,beforeId:string|null=null;
 if(p.has("before_created_at")){beforeUs=parseTimestamp(p.get("before_created_at")!);beforeId=p.get("before_intent_id")!;if(!ID.test(beforeId))throw new StatusError("invalid_status_continuation");}
 return {view:view as StatusQuery['view'],size:Number(size),binding,beforeUs,beforeId};
}
export async function admitStatusRead(db:SqlStore,auth:StatusAuth):Promise<void>{
 const tx=crypto.randomUUID(),event=crypto.randomUUID();
 const clock="(SELECT now_us FROM transaction_guards WHERE transaction_id=?3)";
 const values=[auth.family,auth.subjectId,tx,event];
 const sql=(text:string)=>db.prepare("WITH input AS(SELECT ?1 f,?2 s,?3 t,?4 e) "+text).bind(...values);
 try{await db.batch([
  sql(`INSERT INTO transaction_guards(transaction_id,approved,now_us) VALUES(?3,1,${NOW})`),
  sql(`INSERT INTO status_read_buckets(family,subject_id,tokens,updated_at_us) VALUES(?1,?2,20,${clock})
   ON CONFLICT(family,subject_id) DO UPDATE SET tokens=MIN(20,status_read_buckets.tokens+MAX(0,${clock}-status_read_buckets.updated_at_us)/5000000.0),updated_at_us=MAX(status_read_buckets.updated_at_us,${clock})`),
  sql(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?4,
   EXISTS(SELECT 1 FROM status_read_buckets WHERE family=?1 AND subject_id=?2 AND tokens>=1)
   AND (SELECT COUNT(*) FROM status_read_events WHERE created_at_us>${clock}-600000000)<600)`),
  sql("UPDATE status_read_buckets SET tokens=tokens-1 WHERE family=?1 AND subject_id=?2"),
  sql(`INSERT INTO status_read_events(event_id,created_at_us) VALUES(?4,${clock})`),
  sql("DELETE FROM transaction_guards WHERE transaction_id IN (?3,?4)"),
 ]);}catch(error){if(!String(error).includes("CHECK constraint failed"))throw new StatusError("status_unavailable",503,5);throw new StatusError("status_rate_limited",429,5);}
}
function integer(value:unknown,min=0):number{const n=Number(value);if(value===null||!Number.isSafeInteger(n)||n<min)throw new StatusError("status_projection_invalid",500);return n;}
function record(value:unknown):Record<string,unknown>{if(!value||typeof value!=="object"||Array.isArray(value))throw new StatusError("status_projection_invalid",500);return value as Record<string,unknown>;}
function reason(internal:unknown,code:unknown):string{
 if(typeof internal!=="string")throw new StatusError("status_projection_invalid",500);
 if(["pre_add_membership_observation"].includes(internal))return "membership_already_present";
 if(["flickr_added","flickr_code_3"].includes(internal))return "added";
 if(["flickr_code_6","flickr_code_7"].includes(internal))return "moderation_submission_recorded";
 if(["unknown_code","unresolved_dispatch"].includes(internal))return "post_dispatch_result_unavailable";
 if(["flickr_code_105","flickr_code_106"].includes(internal))return "temporary_flickr_failure";
 if(internal==="flickr_code_5")return "flickr_group_limit";
 if(internal==="flickr_code_1")return "photo_unavailable_or_ineligible";
 if(["flickr_code_2","flickr_code_8","flickr_code_10","flickr_code_11"].includes(internal))return "group_unavailable_or_ineligible";
 if(["flickr_code_4","flickr_code_116"].includes(internal))return "request_policy_rejected";
 if(["flickr_code_98","flickr_code_99"].includes(internal)||internal==="flickr_read_failure"&&[98,99].includes(Number(code)))return "user_flickr_reauthorization_required";
 if(["flickr_code_95","flickr_code_96","flickr_code_97","flickr_code_100","flickr_code_111","flickr_code_112","flickr_code_114","flickr_code_115"].includes(internal))return "deployment_repair_required";
 if(["safe_read_unavailable","flickr_read_failure","abandoned_before_dispatch","not_dispatched_preflight_expired"].includes(internal))return "safe_transport_failure";
 if(internal==="cancelled")return "cancelled";
 throw new StatusError("status_projection_invalid",500);
}
function gates(values:unknown,count:number){
 if(!Array.isArray(values)||values.length!==2)throw new StatusError("status_projection_invalid",500);
 return ["user","deployment"].map(scope=>{
  const row=values.map(record).find(row=>row.scope===scope);if(!row||![0,1].includes(Number(row.enabled)))throw new StatusError("status_projection_invalid",500);
  const paused=Number(row.enabled)===0,revision=integer(row.revision,1);
  let reasonCode:string|null=null,pausedAt:string|null=null;
  if(paused){pausedAt=statusTimestamp(row.at);if(!pausedAt)throw new StatusError("status_projection_invalid",500);
   if(["gate_paused","initially_paused","migration_snapshot"].includes(String(row.reason)))reasonCode="operator_review_required";
   else if(row.reason==="unknown_code"||row.reason==="flickr_read_failure"||/^flickr_code_(95|96|97|98|99|100|111|112|114|115)$/.test(String(row.reason)))reasonCode=scope==="user"?"user_flickr_reauthorization_required":"deployment_repair_required";
   else throw new StatusError("status_projection_invalid",500);
  }
  return {scope,state:paused?"paused":"enabled",revision,pausedAt,reasonCode,affectedActiveIntentCount:paused?count:0};
 });
}
function intent(value:unknown,writeGates:ReturnType<typeof gates>){
 const row=record(value),state=String(row.state);
 for(const key of ["id","binding","photo","group"])if(typeof row[key]!=="string"||!ID.test(row[key] as string))throw new StatusError("status_projection_invalid",500);
 if(!STATES.includes(state))throw new StatusError("status_projection_invalid",500);
 const active=ACTIVE.includes(state),terminalAt=statusTimestamp(row.terminal),ahead=integer(row.ahead);
 if(active!==(Number(row.active)===1)||active!==(terminalAt===null))throw new StatusError("status_projection_invalid",500);
 let permanentSubmissionBlock:{reasonCode:string;createdAt:string}|null=null;
 if(row.block!==null){const block=record(row.block);if(!['flickr_code_6','flickr_code_7','delivery_uncertain'].includes(String(block.reason))||typeof block.at!=="string")throw new StatusError("status_projection_invalid",500);
  permanentSubmissionBlock={reasonCode:block.reason==="delivery_uncertain"?"delivery_uncertain":"moderation_submission_recorded",createdAt:block.at};
 }
 if(state==="moderation_submitted"?permanentSubmissionBlock?.reasonCode!=="moderation_submission_recorded":state==="delivery_uncertain"?permanentSubmissionBlock?.reasonCode!=="delivery_uncertain":permanentSubmissionBlock!==null)throw new StatusError("status_projection_invalid",500);
 let lastOutcome:{reasonCode:string;flickrResultCode:number|null;observedAt:string;correlationId:string}|null=null;
 if(row.outcome!==null){const outcome=record(row.outcome),observedAt=statusTimestamp(outcome.at);
  if(!observedAt||typeof outcome.id!=="string"||!ID.test(outcome.id)||outcome.code!==null&&!Number.isSafeInteger(outcome.code))throw new StatusError("status_projection_invalid",500);
  lastOutcome={reasonCode:reason(outcome.reason,outcome.code),flickrResultCode:outcome.code as number|null,observedAt,correlationId:outcome.id};
 }
 if(state==="moderation_submitted"&&lastOutcome?.reasonCode!=="moderation_submission_recorded"||state==="delivery_uncertain"&&lastOutcome?.reasonCode!=="post_dispatch_result_unavailable"||state==="added"&&!["added","membership_already_present"].includes(lastOutcome?.reasonCode??""))throw new StatusError("status_projection_invalid",500);
 let attention:unknown=null;
 if(state==="needs_attention"||state==="delivery_uncertain"){
  if(!lastOutcome)throw new StatusError("status_projection_invalid",500);
  const operatorAction=state==="delivery_uncertain"?"inspect_flickr_no_fga_resubmit":lastOutcome.reasonCode==="user_flickr_reauthorization_required"?"reauthorize_flickr":lastOutcome.reasonCode==="deployment_repair_required"?"repair_deployment":["photo_unavailable_or_ineligible","group_unavailable_or_ineligible","request_policy_rejected"].includes(lastOutcome.reasonCode)?"correct_future_selection":null;
  if(!operatorAction)throw new StatusError("status_projection_invalid",500);
  attention={kind:state,reasonCode:lastOutcome.reasonCode,occurredAt:terminalAt,operatorAction,fgaResubmissionAllowed:false};
 }
 const holds=writeGates.filter(g=>g.state==="paused").map(g=>g.scope+"_flickr_write_gate_paused").sort();
 const isHead=row.head===row.id;
 if(active&&isHead!==(ahead===0))throw new StatusError("status_projection_invalid",500);
 const due=isHead&&state!=="attempting"?statusTimestamp(row.due):null;
 if(active&&isHead&&state!=="attempting"&&!due)throw new StatusError("status_projection_invalid",500);
 return {fgaSubmissionIntentId:row.id,fgaPhotoBindingId:row.binding,flickrPhotoId:row.photo,flickrGroupId:row.group,
  groupDisplayName:null,groupDisplayNameObservedAt:null,state,stateRevision:integer(row.revision,1),createdAt:statusTimestamp(row.created),stateChangedAt:statusTimestamp(row.changed),terminalAt,attemptCount:integer(row.attempts),
  queue:active?{isPartitionHead:isHead,activeAheadInPartition:ahead,nextWorkNotBefore:due,holds}:null,lastOutcome,permanentSubmissionBlock,attention};
}
export async function readSubmissionStatus(db:SqlStore,auth:StatusAuth,url:URL,itemId?:string):Promise<unknown>{
 const query=parseStatusQuery(url,itemId!==undefined);if(itemId!==undefined&&!ID.test(itemId))throw new StatusError("not_found",404);
 await admitStatusRead(db,auth);
 const authorized=auth.family==="installation"?`EXISTS(SELECT 1 FROM installations a JOIN installation_credential_versions v ON v.version_id=a.current_version_id AND v.installation_id=a.installation_id WHERE a.installation_id=?2 AND a.user_id=?1 AND a.state='active' AND a.credential_class='lrc_plugin' AND v.state='current' AND v.credential_digest=?3)`:`EXISTS(SELECT 1 FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id WHERE s.session_id=?2 AND s.user_id=?1 AND p.google_sub=?3 AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW})`;
 const base=`i.user_id=?1 AND (?4 IS NULL OR i.binding_id=?4) AND ${authorized}`;
 const view=itemId||query.view==="history"?"1":query.view==="active"?"i.active_fifo_member=1":"i.state IN ('needs_attention','delivery_uncertain')";
 const scope=base+` AND ${view} AND (?8 IS NULL OR i.intent_id=?8) AND (?5 IS NULL OR i.created_at_us<CAST(?5 AS INTEGER) OR (i.created_at_us=CAST(?5 AS INTEGER) AND i.intent_id<?6))`;
 const rows=`SELECT json_object('id',i.intent_id,'binding',i.binding_id,'photo',i.photo_id,'group',i.group_id,'state',i.state,'revision',CAST(i.state_version AS TEXT),'active',i.active_fifo_member,
  'created',CAST(i.created_at_us AS TEXT),'changed',CAST(i.state_changed_at_us AS TEXT),'terminal',CAST(i.terminal_at_us AS TEXT),'due',CAST(p.next_work_not_before_us AS TEXT),
  'ahead',(SELECT COUNT(*) FROM submission_intents x WHERE x.partition_id=i.partition_id AND x.active_fifo_member=1 AND x.enqueue_ordinal<i.enqueue_ordinal),
  'head',(SELECT intent_id FROM submission_intents x WHERE x.partition_id=i.partition_id AND x.active_fifo_member=1 ORDER BY enqueue_ordinal LIMIT 1),
  'attempts',(SELECT COUNT(*) FROM submission_attempts a WHERE a.intent_id=i.intent_id),
  'outcome',(SELECT json_object('id',a.attempt_id,'reason',r.reason,'code',r.flickr_code,'at',CAST(r.completed_at_us AS TEXT)) FROM submission_attempts a JOIN attempt_resolutions r ON r.attempt_id=a.attempt_id WHERE a.intent_id=i.intent_id AND r.reason<>'rate_capacity_unavailable' ORDER BY a.ordinal DESC LIMIT 1),
  'block',(SELECT json_object('reason',b.first_reason,'at',b.created_at_utc) FROM submission_blocks b WHERE b.photo_id=i.photo_id AND b.group_id=i.group_id)) value
  FROM submission_intents i JOIN group_partitions p ON p.partition_id=i.partition_id WHERE ${scope} ORDER BY i.created_at_us DESC,i.intent_id DESC LIMIT ?7`;
 const sql=`SELECT json_object('authorized',${authorized},'observed',CAST(${NOW} AS TEXT),
  'bindingExists',(?4 IS NULL OR EXISTS(SELECT 1 FROM photo_bindings WHERE binding_id=?4 AND user_id=?1)),
  'invalidState',EXISTS(SELECT 1 FROM submission_intents i WHERE ${base} AND i.state NOT IN ('queued','attempting','retrying','throttled','added','moderation_submitted','delivery_uncertain','needs_attention','cancelled')),
  'active',(SELECT COUNT(*) FROM submission_intents i WHERE ${base} AND i.active_fifo_member=1),
  'partitions',(SELECT COUNT(DISTINCT i.partition_id) FROM submission_intents i WHERE ${base} AND i.active_fifo_member=1),
  'attention',(SELECT COUNT(*) FROM submission_intents i WHERE ${base} AND i.state IN ('needs_attention','delivery_uncertain')),
  'oldest',(SELECT CAST(MIN(i.created_at_us) AS TEXT) FROM submission_intents i WHERE ${base} AND i.active_fifo_member=1),
  'rows',(SELECT json_group_array(json(value)) FROM (${rows})),
  'gates',(SELECT json_group_array(json_object('scope',g.scope,'enabled',g.enabled,'revision',CAST(g.revision AS TEXT),
   'at',(SELECT CAST(created_at_us AS TEXT) FROM flickr_write_gate_events e WHERE e.scope=g.scope AND e.scope_id=g.scope_id AND e.revision=g.revision ORDER BY created_at_us LIMIT 1),
   'reason',(SELECT reason FROM flickr_write_gate_events e WHERE e.scope=g.scope AND e.scope_id=g.scope_id AND e.revision=g.revision ORDER BY created_at_us LIMIT 1))) FROM flickr_write_gates g WHERE (g.scope='user' AND g.scope_id=?1) OR (g.scope='deployment' AND g.scope_id='*'))) snapshot`;
 let raw;try{raw=await db.prepare(sql).bind(auth.userId,auth.subjectId,auth.proof,query.binding,query.beforeUs,query.beforeId,itemId?1:query.size+1,itemId??null).first<{snapshot:string}>();}catch{throw new StatusError("status_unavailable",503,5);}
 if(!raw)throw new StatusError("status_unavailable",503,5);
 const snapshot=record(JSON.parse(raw.snapshot));
 if(snapshot.authorized!==1)throw new StatusError(auth.family==="installation"?"invalid_token":"unauthorized",401);
 if(snapshot.bindingExists!==1)throw new StatusError("not_found",404);
 if(snapshot.invalidState!==0)throw new StatusError("status_projection_invalid",500);
 const active=integer(snapshot.active),writeGates=gates(snapshot.gates,active),observedAt=statusTimestamp(snapshot.observed);
 if(!observedAt||!Array.isArray(snapshot.rows))throw new StatusError("status_projection_invalid",500);
 const items=snapshot.rows.map(row=>intent(row,writeGates));
 const poll=(hasActive:boolean)=>!hasActive?null:writeGates.some(g=>g.state==="paused")?60:15;
 if(itemId){if(!items.length)throw new StatusError("not_found",404);return {schemaVersion:1,observedAt,intent:items[0],writeGates:writeGates.filter(g=>g.state==="paused"),recommendedPollAfterSeconds:poll(ACTIVE.includes(items[0].state))};}
 const page=items.slice(0,query.size),last=page.at(-1);
 return {schemaVersion:1,observedAt,view:query.view,pageSize:query.size,photoBindingId:query.binding,
  summary:{activeIntentCount:active,activePartitionCount:integer(snapshot.partitions),attentionIntentCount:integer(snapshot.attention),oldestActiveEnqueuedAt:statusTimestamp(snapshot.oldest),writeGates},
  intents:page,nextPage:items.length>query.size?{beforeCreatedAt:last!.createdAt,beforeIntentId:last!.fgaSubmissionIntentId}:null,recommendedPollAfterSeconds:poll(active>0)};
}
export function statusFailure(error:unknown,bearer=false):Response{
 const known=error instanceof StatusError,response=errorResponse(known?error.status:503,known?error.message:"status_unavailable","Submission status is unavailable.",known&&error.status===401&&bearer);
 if(known&&error.retryAfter!==null)response.headers.set("Retry-After",String(error.retryAfter));else if(!known)response.headers.set("Retry-After","5");return response;
}
export async function cleanupStatusReads(db:SqlStore):Promise<void>{
 await db.prepare(`DELETE FROM status_read_events WHERE event_id IN (SELECT event_id FROM status_read_events WHERE created_at_us<${NOW}-600000000 LIMIT 1000)`).run();
}
