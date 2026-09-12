import type {SqlStore} from "./admission.ts";
import {NOW_US_SQL as NOW} from "./installations.ts";
import {verifyCandidateCredential,type FlickrFetch,type SecretReads} from "./flickr_reads.ts";
export class LifecycleError extends Error {}
export interface LifecycleOperation {operationId:string;userId:string;kind:"replace"|"retire";phase:string;generation:string;expectedRevision:number;preserveRelink:number;}
export interface NativeWriter {replace(value:string):Promise<void>;}
const audit=(db:SqlStore,user:string,action:string,id:string)=>db.prepare("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason,target_id) VALUES(?,?,?,?,'succeeded','guarded_transition',?)").bind(crypto.randomUUID(),user,action,id,id);
export async function operation(db:SqlStore,id:string):Promise<LifecycleOperation|null>{return db.prepare("SELECT operation_id operationId,user_id userId,kind,phase,generation,expected_revision expectedRevision,preserve_relink preserveRelink FROM flickr_lifecycle_operations WHERE operation_id=?").bind(id).first<LifecycleOperation>();}
// Caller must already hold current administrator, Origin, CSRF and recent-auth authority.
export async function beginLifecycle(db:SqlStore,userId:string,revision:number,kind:"replace"|"retire",authority?:{sessionId:string;googleSub:string}):Promise<LifecycleOperation>{
 if(!Number.isSafeInteger(revision)||revision<1||revision>=9007199254740991)throw new LifecycleError("stale_connection");
 const id=crypto.randomUUID(),generation=crypto.randomUUID();
 try {await db.batch([
 db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM flickr_links l JOIN flickr_connection_state c ON c.user_id=l.user_id WHERE l.user_id=? AND l.link_revision=? AND c.operation_id IS NULL AND c.state NOT IN ('replacing','disconnecting','repair_required') AND NOT EXISTS(SELECT 1 FROM flickr_lifecycle_operations o WHERE o.user_id=l.user_id AND o.phase<>'complete')) AND (? IS NULL OR EXISTS(SELECT 1 FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id WHERE s.session_id=? AND s.user_id=? AND p.google_sub=? AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW}))`).bind(id,userId,revision,authority?.sessionId??null,authority?.sessionId??null,userId,authority?.googleSub??null),
 db.prepare("INSERT INTO flickr_lifecycle_operations(operation_id,user_id,kind,phase,generation,retiring_generation,expected_revision) VALUES(?,?,?,'prepared',?,(SELECT active_generation FROM flickr_native_credentials WHERE user_id=?),?)").bind(id,userId,kind,generation,userId,revision),
 db.prepare("UPDATE flickr_links SET state='paused',link_revision=link_revision+1 WHERE user_id=?").bind(userId),
 db.prepare("UPDATE flickr_connection_state SET state=?,local_state=?,operation_id=?,external_removal=? WHERE user_id=?").bind(kind==="replace"?"replacing":"disconnecting",kind==="replace"?"replacement_pending":"retirement_pending",id,kind==="retire"?1:0,userId),
 db.prepare("UPDATE flickr_native_credentials SET operation_id=? WHERE user_id=?").bind(id,userId),
 db.prepare("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='user' AND scope_id=? AND enabled=1").bind(userId),
 audit(db,userId,"flickr.lifecycle_started",id),
 db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(id)
 ]);}catch(error){throw new LifecycleError(String(error).includes("CHECK constraint failed")?"stale_connection":"lifecycle_unavailable");}
 return {operationId:id,userId,kind,phase:"prepared",generation,expectedRevision:revision,preserveRelink:0};
}
async function markUncertain(db:SqlStore,op:LifecycleOperation):Promise<void>{
 const id=crypto.randomUUID();await db.batch([
 db.prepare("INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM flickr_lifecycle_operations o JOIN flickr_connection_state c ON c.operation_id=o.operation_id WHERE o.operation_id=? AND o.phase='dispatched')").bind(id,op.operationId),
 db.prepare("UPDATE flickr_lifecycle_operations SET phase='repair_required' WHERE operation_id=?").bind(op.operationId),
 db.prepare("UPDATE flickr_connection_state SET state='repair_required',local_state='unknown' WHERE operation_id=?").bind(op.operationId),
 audit(db,op.userId,"flickr.lifecycle_uncertain",op.operationId),db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(id)]);
}
export async function dispatchLifecycle(db:SqlStore,id:string,writer:NativeWriter,candidate?:{token:string;tokenSecret:string}):Promise<boolean>{
 const op=await operation(db,id);if(!op||op.phase!=="prepared")return false;
 if(op.kind==="replace"&&(!candidate||!candidate.token||!candidate.tokenSecret||candidate.token.length>2048||candidate.tokenSecret.length>2048||/[\x00-\x20\x7f]/.test(candidate.token+candidate.tokenSecret)))throw new LifecycleError("invalid_candidate");
 // Fully prepare the fixed payload before claiming the only mutation attempt.
 const payload=JSON.stringify(op.kind==="replace"?{schemaVersion:1,generation:op.generation,token:candidate!.token,tokenSecret:candidate!.tokenSecret}:{schemaVersion:1,generation:op.generation,retired:true});
 const tx=crypto.randomUUID();
 try {await db.batch([
 db.prepare("INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM flickr_lifecycle_operations o JOIN flickr_connection_state c ON c.operation_id=o.operation_id JOIN flickr_links l ON l.user_id=o.user_id WHERE o.operation_id=? AND o.phase='prepared' AND l.state='paused' AND l.link_revision=o.expected_revision+1)").bind(tx,id),
 db.prepare("UPDATE flickr_lifecycle_operations SET phase='dispatched' WHERE operation_id=? AND phase='prepared'").bind(id),audit(db,op.userId,"flickr.lifecycle_dispatch_started",id),db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)
 ]);}catch{return false;}
 try {await writer.replace(payload);return true;}catch{try{await markUncertain(db,op);}catch{/* Persisted dispatched ownership still prevents retry. */}return false;}
}
// Reconciliation reads the fixed binding. It never reissues the mutation or accepts browser evidence.
export async function reconcileLifecycle(db:SqlStore,id:string,secrets:SecretReads,fetcher:FlickrFetch):Promise<boolean>{
 const op=await operation(db,id);if(!op||!["dispatched","repair_required"].includes(op.phase))return false;
 const row=await db.prepare("SELECT owner_nsid owner FROM flickr_links WHERE user_id=?").bind(op.userId).first<{owner:string}>();if(!row)return false;
 let permission:"write"|"delete"|null=null;
 try {
  const raw=await secrets.FLICKR_GRANT.get();
  if(op.kind==="retire"){
   const value=JSON.parse(raw);if(Object.keys(value).sort().join()!=="generation,retired,schemaVersion"||value.schemaVersion!==1||value.generation!==op.generation||value.retired!==true)return false;
  }else{const app=await secrets.FLICKR_APPLICATION.get();permission=(await verifyCandidateCredential(raw,app,op.generation,row.owner,fetcher)).permission;}
 }catch{return false;}
 const tx=crypto.randomUUID();
 try {await db.batch([
 db.prepare("INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM flickr_lifecycle_operations o JOIN flickr_connection_state c ON c.operation_id=o.operation_id JOIN flickr_links l ON l.user_id=o.user_id WHERE o.operation_id=? AND o.phase IN ('dispatched','repair_required') AND l.state='paused' AND l.link_revision=o.expected_revision+1 AND o.generation=?)").bind(tx,id,op.generation),
 db.prepare("UPDATE flickr_links SET state=?,link_revision=link_revision+1 WHERE user_id=?").bind(op.kind==="replace"?"linked":op.preserveRelink===1?"paused":"disconnected",op.userId),
 db.prepare(`UPDATE flickr_connection_state SET state=?,local_state=?,operation_id=NULL,verified_permission=?,verified_at_us=CASE WHEN ? IS NULL THEN NULL ELSE ${NOW} END WHERE user_id=?`).bind(op.kind==="replace"?"linked":op.preserveRelink===1?"relink_required":"disconnected",op.kind==="replace"?"available":"retired",permission,permission,op.userId),
 db.prepare("DELETE FROM flickr_native_credentials WHERE user_id=?").bind(op.userId),
 db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) SELECT user_id,?,link_revision,owner_nsid,? FROM flickr_links WHERE user_id=? AND ?='replace'").bind(op.generation,permission,op.userId,op.kind),
 db.prepare(`UPDATE flickr_lifecycle_operations SET phase='complete',completed_at_us=${NOW} WHERE operation_id=?`).bind(id),
 audit(db,op.userId,op.kind==="replace"?"flickr.connection_activated":"flickr.payload_retired",id),db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)
 ]);return true;}catch{return false;}
}
export async function connectionView(db:SqlStore,userId:string):Promise<unknown>{
 const row=await db.prepare(`SELECT l.link_revision revision,l.owner_nsid owner,l.state coarse,c.*,
 (SELECT enabled FROM flickr_write_gates WHERE scope='user' AND scope_id=l.user_id) user_gate,
 (SELECT revision FROM flickr_write_gates WHERE scope='user' AND scope_id=l.user_id) user_revision,
 (SELECT enabled FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*') deployment_gate,
 (SELECT revision FROM flickr_write_gates WHERE scope='deployment' AND scope_id='*') deployment_revision
 FROM flickr_links l JOIN flickr_connection_state c ON c.user_id=l.user_id WHERE l.user_id=?`).bind(userId).first<Record<string,unknown>>();
 if(!row||![row.revision,row.user_revision,row.deployment_revision].every(x=>Number.isSafeInteger(x)&&Number(x)>0)||![0,1].includes(Number(row.user_gate))||![0,1].includes(Number(row.deployment_gate)))throw new LifecycleError("connection_unavailable");
 const active=row.state==="linked"&&row.local_state==="available"&&row.coarse==="linked"&&row.operation_id===null;
 if(row.state==="linked"&&!active)throw new LifecycleError("connection_unavailable");
 const gate=(enabled:unknown,revision:unknown)=>({state:enabled===1?"enabled":"paused",revision});
 return {schemaVersion:1,revision:row.revision,state:row.state,flickrOwnerNsid:row.owner,verifiedPermission:row.verified_permission,verifiedAt:row.verified_at_us===null?null:new Date(Number(row.verified_at_us)/1000).toISOString().replace("Z","000Z"),localCredentialState:row.local_state,fgaOperationState:active?(row.user_gate===1&&row.deployment_gate===1?"enabled":"read_only"):"stopped",flickrPermissionState:row.external_removal===1?"owner_action_required":"not_requested",userWriteGate:gate(row.user_gate,row.user_revision),deploymentWriteGate:gate(row.deployment_gate,row.deployment_revision)};
}

export async function resumeWriteGate(db:SqlStore,userId:string,scope:"user"|"deployment",revision:number,secrets:SecretReads,fetcher:FlickrFetch):Promise<unknown>{
 if(!Number.isSafeInteger(revision)||revision<1||revision>=Number.MAX_SAFE_INTEGER)throw new LifecycleError("stale_connection");
 const current=await db.prepare("SELECT l.owner_nsid owner,l.link_revision revision,n.active_generation generation FROM flickr_links l JOIN flickr_native_credentials n ON n.user_id=l.user_id JOIN flickr_connection_state c ON c.user_id=l.user_id WHERE l.user_id=? AND l.state='linked' AND c.state='linked' AND c.operation_id IS NULL AND n.operation_id IS NULL AND n.link_revision=l.link_revision").bind(userId).first<{owner:string;revision:number;generation:string}>();if(!current)throw new LifecycleError("connection_unavailable");
 await verifyCandidateCredential(await secrets.FLICKR_GRANT.get(),await secrets.FLICKR_APPLICATION.get(),current.generation,current.owner,fetcher);
 const tx=crypto.randomUUID(),scopeId=scope==="user"?userId:"*";
 try{await db.batch([
 db.prepare("INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM flickr_write_gates g WHERE g.scope=? AND g.scope_id=? AND g.revision=? AND g.enabled=0) AND EXISTS(SELECT 1 FROM flickr_links l JOIN flickr_native_credentials n ON n.user_id=l.user_id JOIN flickr_connection_state c ON c.user_id=l.user_id WHERE l.user_id=? AND l.state='linked' AND l.link_revision=? AND n.link_revision=l.link_revision AND n.active_generation=? AND n.operation_id IS NULL AND c.operation_id IS NULL AND c.state='linked')").bind(tx,scope,scopeId,revision,userId,current.revision,current.generation),
 db.prepare("UPDATE flickr_write_gates SET enabled=1,revision=revision+1 WHERE scope=? AND scope_id=?").bind(scope,scopeId),audit(db,userId,"flickr.write_gate_resumed",tx),db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)]);}catch(error){throw new LifecycleError(String(error).includes("CHECK constraint failed")?"stale_connection":"lifecycle_unavailable");}
 return connectionView(db,userId);
}
