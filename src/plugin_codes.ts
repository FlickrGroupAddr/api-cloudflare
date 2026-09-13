import {createHmac,randomBytes,timingSafeEqual} from "node:crypto";
import type {SqlStore} from "./admission.ts";
import type {AdminSession} from "./browser_sessions.ts";
import {digest} from "./browser_sessions.ts";
import {NOW_US_SQL as NOW,CREDENTIAL} from "./installations.ts";

const ID=/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const UTC="strftime('%Y-%m-%dT%H:%M:%f','now')||'000Z'";
const CONFIRMATIONS=["ownerControlledWorkstation","privateBrowser","clipboardHistoryOff","clipboardSyncOff","noObserversOrRecording","pluginReady"];
export class PluginCodeError extends Error {
 readonly status:number;
 constructor(code:string,status=400){super(code);this.status=status;}
}
export function encodePluginCode(bytes:Uint8Array):string{
 if(bytes.length!==32)throw new Error("plugin_code_entropy_size");
 const alphabet="0123456789ABCDEFGHJKMNPQRSTVWXYZ";
 let bits=0,accumulator=0,text="";
 for(const byte of bytes){accumulator=(accumulator<<8)|byte;bits+=8;
  while(bits>=5){bits-=5;text+=alphabet[(accumulator>>>bits)&31];}
  accumulator&=(1<<bits)-1;
 }
 if(bits)text+=alphabet[(accumulator<<(5-bits))&31];
 return text.match(/.{4}/g)!.join("-");
}
function object(value:unknown,keys:string[]):Record<string,unknown>{
 if(!value||typeof value!=="object"||Array.isArray(value)||Object.keys(value).sort().join()!==[...keys].sort().join())throw new PluginCodeError("invalid_plugin_code_request");
 return value as Record<string,unknown>;
}
export function creationRequest(value:unknown,initial:boolean):string|null{
 const input=object(value,initial?["schemaVersion","installationLabel","transferConfirmations"]:["schemaVersion","transferConfirmations"]);
 if(input.schemaVersion!==1)throw new PluginCodeError("invalid_plugin_code_request");
 const confirmations=object(input.transferConfirmations,CONFIRMATIONS);
 if(CONFIRMATIONS.some(key=>confirmations[key]!==true))throw new PluginCodeError("transfer_preconditions_required");
 if(initial){if(typeof input.installationLabel!=="string"||![...input.installationLabel].length||[...input.installationLabel].length>120||/[\x00-\x1f\x7f]/.test(input.installationLabel))throw new PluginCodeError("invalid_plugin_code_request");return input.installationLabel;}
 return null;
}
export function candidateRequest(value:unknown):"current"|"revoked"{
 if(!value||typeof value!=="object")throw new PluginCodeError("invalid_plugin_code_request");
 const state=(value as {state?:unknown}).state;
 const input=object(value,state==="current"?["schemaVersion","state","pluginValidationConfirmed"]:["schemaVersion","state"]);
 if(input.schemaVersion!==1||!["current","revoked"].includes(String(state))||state==="current"&&input.pluginValidationConfirmed!==true)throw new PluginCodeError("invalid_plugin_code_request");
 return state as "current"|"revoked";
}
export function revocationRequest(value:unknown):void{
 if(object(value,["state"]).state!=="revoked")throw new PluginCodeError("invalid_plugin_code_request");
}
export function pluginCodeEtag(id:string,revision:number):string{return `"pc:${id}:${revision}"`;}
function expectedRevision(id:string,header:string|null):number{
 if(header===null)throw new PluginCodeError("precondition_required",428);
 const revision=Number(/:([1-9][0-9]*)"$/.exec(header)?.[1]);
 if(!Number.isSafeInteger(revision)||revision<1||revision>=Number.MAX_SAFE_INTEGER||header!==pluginCodeEtag(id,revision))throw new PluginCodeError("precondition_failed",412);
 return revision;
}
export interface PluginCodeDetail {
 schemaVersion:1;pluginCodeId:string;installationLabel:string;state:"active"|"revoked";revision:number;
 createdAt:string;revokedAt:string|null;lastAuthenticatedAt:string|null;rotationDueAt:string;
 currentVersion:unknown;pendingCandidate:unknown;lastLifecycleOutcome:unknown;
}
const DETAIL_SQL=`SELECT i.installation_id pluginCodeId,i.label installationLabel,i.state,i.revision,
 i.created_at_utc createdAt,i.revoked_at_utc revokedAt,i.last_authenticated_at_utc lastAuthenticatedAt,
 i.rotation_due_at_utc rotationDueAt,
 (SELECT json_object('versionId',v.version_id,'state',v.state,'createdAt',v.created_at_utc,'expiresAt',CASE WHEN v.expires_at_us IS NULL THEN NULL ELSE strftime('%Y-%m-%dT%H:%M:',v.expires_at_us/1000000,'unixepoch')||printf('%09.6f',(v.expires_at_us%60000000)/1000000.0)||'Z' END) FROM installation_credential_versions v WHERE v.version_id=i.current_version_id) currentVersion,
 (SELECT json_object('versionId',v.version_id,'state',v.state,'createdAt',v.created_at_utc,'expiresAt',CASE WHEN v.expires_at_us IS NULL THEN NULL ELSE strftime('%Y-%m-%dT%H:%M:',v.expires_at_us/1000000,'unixepoch')||printf('%09.6f',(v.expires_at_us%60000000)/1000000.0)||'Z' END) FROM installation_credential_versions v WHERE v.version_id=i.pending_version_id) pendingCandidate,
 (SELECT json_object('kind',e.kind,'versionId',e.version_id,'occurredAt',e.created_at_utc) FROM installation_lifecycle_events e WHERE e.installation_id=i.installation_id ORDER BY e.to_revision DESC,e.event_id DESC LIMIT 1) lastLifecycleOutcome
 FROM installations i WHERE i.user_id=?1`;
const SESSION=`EXISTS(SELECT 1 FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id WHERE s.session_id=?3 AND s.user_id=?2 AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW} AND ${NOW}-s.recent_authentication_at_us BETWEEN 0 AND 300000000)`;
function metadata(raw:unknown):PluginCodeDetail{
 if(!raw||typeof raw!=="object"||Array.isArray(raw))throw new PluginCodeError("plugin_code_state_unavailable",503);
 const row=raw as Record<string,unknown>;
 if(!ID.test(String(row.pluginCodeId))||!Number.isSafeInteger(row.revision)||Number(row.revision)<1||!['active','revoked'].includes(String(row.state))||typeof row.rotationDueAt!=="string")throw new PluginCodeError("plugin_code_state_unavailable",503);
 const parse=(value:unknown)=>value===null?null:JSON.parse(String(value));
 return {schemaVersion:1,...row,currentVersion:parse(row.currentVersion),pendingCandidate:parse(row.pendingCandidate),lastLifecycleOutcome:parse(row.lastLifecycleOutcome)} as unknown as PluginCodeDetail;
}
function audit(db:SqlStore,session:AdminSession,action:string,target:string|null,reason="confirmed_operation"){
 return db.prepare(`INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id)
 VALUES(?,?,?,?,?,'succeeded',?,?)`).bind(crypto.randomUUID(),session.userId,action,crypto.randomUUID(),session.sessionId,reason,target);
}
async function owned(db:SqlStore,session:AdminSession,id:string):Promise<Record<string,unknown>>{
 if(!ID.test(id))throw new PluginCodeError("not_found",404);
 const row=await db.prepare(DETAIL_SQL+" AND i.installation_id=?2").bind(session.userId,id).first<Record<string,unknown>>();
 if(!row)throw new PluginCodeError("not_found",404);return row;
}
export async function getPluginCode(db:SqlStore,session:AdminSession,id:string,auditRead=true):Promise<PluginCodeDetail>{
 if(!auditRead)return metadata(await owned(db,session,id));
 if(!ID.test(id))throw new PluginCodeError("not_found",404);
 const result=await db.batch([
  db.prepare(DETAIL_SQL+" AND i.installation_id=?2").bind(session.userId,id),
  audit(db,session,"plugin_code.detail_read",id),
 ]);
 const row=result[0].results[0];if(!row)throw new PluginCodeError("not_found",404);return metadata(row);
}
function mac(value:string,key:string):string{return createHmac("sha256",key).update("fga-plugin-code-page-v1\0"+value).digest("base64url");}
export async function listPluginCodes(db:SqlStore,session:AdminSession,url:URL,cursorKey:string):Promise<unknown>{
 if(typeof cursorKey!=="string"||cursorKey.length<32)throw new PluginCodeError("plugin_code_unavailable",503);
 const query=url.searchParams;
 if([...query.keys()].some(key=>!["page_size","page_token"].includes(key))||[...new Set(query.keys())].some(key=>query.getAll(key).length!==1||query.get(key)===""))throw new PluginCodeError("invalid_plugin_code_query");
 const raw=query.get("page_size")??"50";if(!/^[1-9][0-9]{0,2}$/.test(raw)||Number(raw)>100)throw new PluginCodeError("invalid_plugin_code_query");
 const size=Number(raw);let before:string|null=null,beforeId:string|null=null;
 if(query.has("page_token")){
  try{
   const token=query.get("page_token")!;if(token.length>2048)throw Error();
   const [payload,signature,...extra]=token.split(".");if(extra.length||!payload||!signature)throw Error();
   const expected=mac(payload,cursorKey);if(signature.length!==expected.length||!timingSafeEqual(Buffer.from(signature),Buffer.from(expected)))throw Error();
   const value=JSON.parse(Buffer.from(payload,"base64url").toString("utf8"));
   if(value.owner!==session.userId||value.size!==size||typeof value.before!=="string"||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value.before)||!ID.test(value.id))throw Error();before=value.before;beforeId=value.id;
  }catch{throw new PluginCodeError("invalid_plugin_code_query");}
 }
 const results=await db.batch([
  db.prepare(DETAIL_SQL+" AND (?2 IS NULL OR i.created_at_utc<?2 OR(i.created_at_utc=?2 AND i.installation_id<?3)) ORDER BY i.created_at_utc DESC,i.installation_id DESC LIMIT ?4").bind(session.userId,before,beforeId,size+1),
  audit(db,session,"plugin_code.list_read",null),
 ]);
 const rows=results[0].results,more=rows.length>size,items=rows.slice(0,size).map(metadata);
 let nextPageToken:string|undefined;
 if(more){const last=items.at(-1)!;const payload=Buffer.from(JSON.stringify({owner:session.userId,size,before:last.createdAt,id:last.pluginCodeId})).toString("base64url");nextPageToken=payload+"."+mac(payload,cursorKey);}
 return {schemaVersion:1,pluginCodes:items,...(nextPageToken?{nextPageToken}:{})};
}
export async function createPluginCode(db:SqlStore,session:AdminSession,value:unknown,id?:string,ifMatch:string|null=null):Promise<unknown>{
 const label=creationRequest(value,id===undefined);
 let revision=0;
 if(id!==undefined){const row=await owned(db,session,id);revision=expectedRevision(id,ifMatch);if(row.revision!==revision)throw new PluginCodeError("precondition_failed",412);if(row.state!=="active"||row.pendingCandidate!==null)throw new PluginCodeError("rotation_conflict",409);}
 const installation=id??crypto.randomUUID(),version=crypto.randomUUID(),token=encodePluginCode(randomBytes(32)),tx=crypto.randomUUID();
 if(!CREDENTIAL.test(token))throw new Error("invalid_generated_plugin_code");
 const values=[installation,session.userId,session.sessionId,revision,version,digest(token),tx,label];
 const sql=(text:string)=>db.prepare("WITH input AS(SELECT ?1 i,?2 u,?3 s,?4 r,?5 v,?6 d,?7 t,?8 l) "+text).bind(...values);
 const condition=id===undefined?"1":`EXISTS(SELECT 1 FROM installations WHERE installation_id=?1 AND user_id=?2 AND revision=?4 AND state='active' AND pending_version_id IS NULL)`;
 const statements=[sql(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?7,${SESSION} AND ${condition})`)];
 if(id===undefined)statements.push(sql(`INSERT INTO installations(installation_id,user_id,credential_class,label,state,revision,current_version_id,rotation_due_at_utc)
 VALUES(?1,?2,'lrc_plugin',?8,'active',1,?5,strftime('%Y-%m-%dT%H:%M:%f','now','+1 year')||'000Z')`));
 statements.push(sql(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us)
 VALUES(?5,?1,?6,'${id===undefined?'current':'pending_rotation'}',COALESCE((SELECT MAX(ordinal) FROM installation_credential_versions WHERE installation_id=?1),0)+1,${id===undefined?'NULL':NOW+'+900000000'})`));
 if(id!==undefined)statements.push(sql("UPDATE installations SET pending_version_id=?5,revision=revision+1 WHERE installation_id=?1"));
 statements.push(sql(`INSERT INTO installation_lifecycle_events(event_id,installation_id,version_id,from_revision,to_revision,kind)
 VALUES(lower(hex(randomblob(16))),?1,?5,?4,?4+1,'${id===undefined?'created':'rotation_created'}')`));
 statements.push(audit(db,session,id===undefined?"plugin_code.created":"plugin_code.rotation_created",installation,"owner_confirmed_transfer_preconditions"));
 statements.push(sql("SELECT expires_at_us expiry FROM installation_credential_versions WHERE version_id=?5"),sql("DELETE FROM transaction_guards WHERE transaction_id=?7"));
 let results;try{results=await db.batch(statements);}catch(error){
  if(id&&String(error).includes("CHECK constraint failed")){
   const latest=await owned(db,session,id);
   if(latest.revision!==revision)throw new PluginCodeError("precondition_failed",412);
   if(latest.state!=="active"||latest.pendingCandidate!==null)throw new PluginCodeError("rotation_conflict",409);
  }
  throw new PluginCodeError("plugin_code_creation_unconfirmed",503);
 }
 const expiry=(results.at(-2)!.results[0] as {expiry:number|null}|undefined)?.expiry;
 return {schemaVersion:1,pluginCodeId:installation,...(id?{rotationCandidateId:version}:{}),pluginCode:token,...(id?{expiresAt:new Date(Number(expiry)/1000).toISOString().replace("Z","000Z")}: {})};
}
export async function changePluginCode(db:SqlStore,session:AdminSession,id:string,ifMatch:string|null,value:unknown,candidateId?:string):Promise<PluginCodeDetail>{
 const row=await owned(db,session,id),revision=expectedRevision(id,ifMatch);
 const target=candidateId?candidateRequest(value):"revoked";
 if(!candidateId)revocationRequest(value);else if(!ID.test(candidateId))throw new PluginCodeError("not_found",404);
 const kind=candidateId?(target==="current"?"rotation_completed":"rotation_cancelled"):"revoked";
 if(candidateId){const exists=await db.prepare("SELECT 1 FROM installation_credential_versions WHERE installation_id=? AND version_id=?").bind(id,candidateId).first();if(!exists)throw new PluginCodeError("not_found",404);}
 if(row.revision!==revision){
  const replay=await db.prepare(`SELECT 1 FROM installation_lifecycle_events e JOIN installations i ON i.installation_id=e.installation_id
   JOIN installation_credential_versions v ON v.version_id=e.version_id WHERE e.installation_id=? AND e.from_revision=? AND e.to_revision=i.revision
   AND e.kind=? AND e.version_id=? AND v.state=?`).bind(id,revision,kind,candidateId??null,target).first();
  if(replay)return getPluginCode(db,session,id);throw new PluginCodeError("precondition_failed",412);
 }
 if(!candidateId&&row.state==="revoked")return getPluginCode(db,session,id);
 if(row.state!=="active")throw new PluginCodeError("rotation_conflict",409);
 const tx=crypto.randomUUID(),values=[id,session.userId,session.sessionId,revision,candidateId??null,tx];
 const sql=(text:string)=>db.prepare("WITH input AS(SELECT ?1 i,?2 u,?3 s,?4 r,?5 v,?6 t) "+text).bind(...values);
 const candidate=candidateId?`AND pending_version_id=?5 AND EXISTS(SELECT 1 FROM installation_credential_versions WHERE version_id=?5 AND installation_id=?1 AND state='pending_rotation' ${target==='current'?`AND expires_at_us>${NOW}`:''})`:"";
 const statements=[sql(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?6,${SESSION} AND EXISTS(SELECT 1 FROM installations WHERE installation_id=?1 AND user_id=?2 AND state='active' AND revision=?4 ${candidate}))`)];
 if(candidateId&&target==="current")statements.push(sql("UPDATE installation_credential_versions SET state='replaced' WHERE installation_id=?1 AND state='current'"));
 statements.push(sql(candidateId?`UPDATE installation_credential_versions SET state='${target}',expires_at_us=${target==='current'?'NULL':'expires_at_us'} WHERE installation_id=?1 AND version_id=?5 AND state='pending_rotation'`:"UPDATE installation_credential_versions SET state='revoked' WHERE installation_id=?1 AND state IN ('current','pending_rotation')"));
 statements.push(sql(candidateId?`UPDATE installations SET ${target==='current'?"current_version_id=?5,rotation_due_at_utc=strftime('%Y-%m-%dT%H:%M:%f','now','+1 year')||'000Z',":""}pending_version_id=NULL,revision=revision+1 WHERE installation_id=?1`:`UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1,revoked_at_utc=${UTC} WHERE installation_id=?1`));
 statements.push(sql(`INSERT INTO installation_lifecycle_events(event_id,installation_id,version_id,from_revision,to_revision,kind) VALUES(lower(hex(randomblob(16))),?1,?5,?4,?4+1,'${kind}')`));
 statements.push(audit(db,session,"plugin_code."+kind,id),sql("DELETE FROM transaction_guards WHERE transaction_id=?6"));
 try{await db.batch(statements);}catch(error){
  if(String(error).includes("CHECK constraint failed")){
   const latest=await owned(db,session,id);
   if(candidateId&&latest.revision!==revision){
    const replay=await db.prepare(`SELECT 1 FROM installation_lifecycle_events e JOIN installations i ON i.installation_id=e.installation_id
     JOIN installation_credential_versions v ON v.version_id=e.version_id WHERE e.installation_id=? AND e.from_revision=? AND e.to_revision=i.revision
     AND e.kind=? AND e.version_id=? AND v.state=?`).bind(id,revision,kind,candidateId,target).first();
    if(replay)return getPluginCode(db,session,id);
   }
   throw new PluginCodeError(latest.revision!==revision?"precondition_failed":"rotation_conflict",latest.revision!==revision?412:409);
  }
  throw new PluginCodeError("plugin_code_change_unconfirmed",503);
 }
 return getPluginCode(db,session,id,false);
}
export async function expirePluginCodeCandidates(db:SqlStore):Promise<void>{
 const rows=await db.prepare(`SELECT i.installation_id id,i.user_id userId,i.pending_version_id candidate,i.revision FROM installations i JOIN installation_credential_versions v ON v.version_id=i.pending_version_id WHERE i.state='active' AND v.state='pending_rotation' AND v.expires_at_us<=${NOW} ORDER BY v.expires_at_us LIMIT 50`).all<{id:string;userId:string;candidate:string;revision:number}>();
 for(const row of rows.results){const tx=crypto.randomUUID();try{await db.batch([
  db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM installations i JOIN installation_credential_versions v ON v.version_id=i.pending_version_id WHERE i.installation_id=? AND i.revision=? AND i.pending_version_id=? AND v.state='pending_rotation' AND v.expires_at_us<=${NOW})`).bind(tx,row.id,row.revision,row.candidate),
  db.prepare("UPDATE installation_credential_versions SET state='expired_unactivated' WHERE version_id=? AND state='pending_rotation'").bind(row.candidate),
  db.prepare("UPDATE installations SET pending_version_id=NULL,revision=revision+1 WHERE installation_id=?").bind(row.id),
  db.prepare("INSERT INTO installation_lifecycle_events(event_id,installation_id,version_id,from_revision,to_revision,kind) VALUES(?,?,?,?,?,'rotation_expired')").bind(crypto.randomUUID(),row.id,row.candidate,row.revision,row.revision+1),
  db.prepare("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason,target_id) VALUES(?,?,'plugin_code.rotation_expired',?,'succeeded','database_expiry',?)").bind(crypto.randomUUID(),row.userId,tx,row.id),
  db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx),
 ]);}catch{/* Concurrent completion/revocation or an unavailable store wins; no replay. */}}
}
