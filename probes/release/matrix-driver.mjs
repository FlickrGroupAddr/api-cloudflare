// External test driver imports the unchanged optimized production module bytes.
// This driver is never deployed as the live application.
import production, {consumePartition, PartitionWorker, ROUTES} from "./production.mjs";
export {PartitionWorker};
const phases=new Map();
let protectedWrites=0;
function observeDatabase(db) {
 return {prepare(sql){
  if(/\b(?:DELETE\s+FROM|UPDATE)\s+submission_blocks\b/i.test(sql))protectedWrites++;
  return db.prepare(sql);
 },batch(statements){return db.batch(statements);}};
}
export default {
 async fetch(request, env) {
  if(env.MATRIX_NATIVE_PROXY==="1"){
   const original=env;env={...env};
   for(const name of ["FLICKR_GRANT","NATIVE_WRITER_TOKEN",...Array.from({length:5},(_,i)=>"FLICKR_TEMP_"+i)]){
    env[name]={async get(){
     for(let attempt=0;;attempt++){
      try{return await original[name].get();}
      catch(error){if(attempt>=3||!String(error).includes("Network connection lost"))throw error;await new Promise(resolve=>setTimeout(resolve,100*(2**attempt)));}
     }
    }};
   }
  }
  const url=new URL(request.url);
  // The fixture can drop the advisory admission hint; D1 still commits through the real route.
  if(url.pathname!=="/__matrix")return production.fetch(request,{...env,COORD:undefined});
  if(request.headers.get("Authorization")!=="Bearer "+env.MATRIX_TOKEN)
   return new Response(null,{status:401});
  const input=await request.json();
  if(input.action==="guard-sql"){
   try{await env.DB.prepare(input.sql).bind(...(input.params??[])).run();return Response.json({denied:false});}
   catch(error){const text=String(error);return Response.json({denied:/immutable|retained|FOREIGN KEY constraint/i.test(text)});}
  }
  if(input.action==="protected-writes")return Response.json({count:protectedWrites});
  if(["api","native-maintenance","scheduled","run"].includes(input.action))env={...env,DB:observeDatabase(env.DB)};
  if(input.action==="migration-proof"){
   const create="CREATE INDEX matrix_rollback_probe ON submission_blocks(group_id,photo_id)";
   let rejected=false;
   try{await env.DB.batch([env.DB.prepare(create),env.DB.prepare("DELETE FROM submission_blocks WHERE photo_id=?").bind(input.photoId)]);}
   catch(error){rejected=/immutable|retained/i.test(String(error));}
   const rolledBack=!(await env.DB.prepare("SELECT 1 FROM sqlite_master WHERE name='matrix_rollback_probe'").first());
   if(!rejected||!rolledBack)return Response.json({passed:false});
   await env.DB.prepare(create).run();
   await env.DB.prepare("DROP INDEX matrix_rollback_probe").run();
   const restored=!(await env.DB.prepare("SELECT 1 FROM sqlite_master WHERE name='matrix_rollback_probe'").first());
   return Response.json({passed:restored,failedMigrationRolledBack:rolledBack});
  }
  if(input.action==="routes")return Response.json({routes:ROUTES.map(x=>({path:x.pathPattern,method:x.method}))});
  if(input.action==="fixture-reset-grant"){
   if(env.MATRIX_NATIVE_PROXY==="1")return new Response(null,{status:403});
   const response=await fetch("https://api.cloudflare.com/client/v4/accounts/"+env.CF_ACCOUNT_ID+"/secrets_store/stores/"+env.CF_SECRET_STORE_ID+"/secrets/"+env.CF_GRANT_SLOT_ID,
    {method:"PATCH",headers:{Authorization:"Bearer matrix-writer-credential-for-fixtures","Content-Type":"application/json"},body:JSON.stringify({value:JSON.stringify({schemaVersion:1,generation:"matrix-generation",token:"matrix-token",tokenSecret:"matrix-token-secret"}),scopes:["workers"]})});
   return Response.json({reset:response.ok});
  }
  if(input.action==="grant-status"){
   try{const value=JSON.parse(await env.FLICKR_GRANT.get());return Response.json({readable:true,generation:value.generation,retired:value.retired===true,credentialPresent:typeof value.token==="string"});}
   catch{return Response.json({readable:false});}
  }
  if(input.action==="grant-ready"){
   try{const value=JSON.parse(await env.FLICKR_GRANT.get());return Response.json({ready:value.generation==="matrix-generation"&&value.token==="matrix-token"});}
   catch{return Response.json({ready:false});}
  }
  if(input.action==="api"){
   const url=new URL(input.path,"https://flickrgroupaddr.com");
   if(url.origin!=="https://flickrgroupaddr.com")return new Response(null,{status:400});
   const req=new Request(url,{method:input.method??"GET",headers:input.headers??{},...(input.body===undefined?{}:{body:typeof input.body==="string"?input.body:JSON.stringify(input.body)})});
   Object.defineProperty(req,"cf",{value:{colo:"MATRIX"}});
   const db=input.rollbackAdmission?{prepare:sql=>env.DB.prepare(sql),batch:statements=>env.DB.batch([...statements,env.DB.prepare("INSERT INTO transaction_guards VALUES('admission-rollback',0)")])}:env.DB;
   const response=await production.fetch(req,{...env,DB:db,FGA_ADMIN_ENABLED:"1",GOOGLE_OWNER_SUB:input.ownerSub,GOOGLE_CLIENT_ID:"matrix-client",FGA_FLICKR_OWNER_NSID:"matrix-owner",...(input.artifact?{FGA_ARTIFACT_SHA2_256:input.artifact}:{}),...(input.suppressHint?{COORD:undefined}:{})});
   const text=await response.text();let body;try{body=JSON.parse(text);}catch{body=text;}
   return Response.json({status:response.status,headers:Object.fromEntries(response.headers),body});
  }
  if(input.action==="native-maintenance"){
   await production.scheduled({scheduledTime:Date.now(),cron:"* * * * *"},{...env,FGA_ADMIN_ENABLED:"1",GOOGLE_OWNER_SUB:input.ownerSub,GOOGLE_CLIENT_ID:"matrix-client",FGA_FLICKR_OWNER_NSID:"matrix-owner",...(input.artifact?{FGA_ARTIFACT_SHA2_256:input.artifact}:{}),...(input.suppressHint?{COORD:undefined}:{})});
   return Response.json({completed:true});
  }
  if(input.action==="native-wake"){
   const stub=env.COORD.get(env.COORD.idFromName(input.partitionId));
   const response=await stub.fetch("https://internal.invalid/wake",{method:"POST",body:JSON.stringify({partitionId:input.partitionId,wakeRevision:input.revision,source:input.source??"admission"})});
   return Response.json({status:response.status});
  }
  if(input.action==="phases")return Response.json({phases:Object.fromEntries(phases)});
  if(input.action==="sql")return Response.json(await env.DB.batch(input.statements.map(x=>env.DB.prepare(x.sql).bind(...(x.params??[])))));
  if(input.action==="run"){
   let clock=0,postMarkerAuthorityReads=0;const seen=[];const underlying=env.DB;
   const original={prepare(sql){
    if(phases.get(input.partitionId)==="marker_committed"&&sql.includes("FROM flickr_links l JOIN flickr_native_credentials"))postMarkerAuthorityReads++;
    return underlying.prepare(sql);
   },batch(statements){return underlying.batch(statements);}};
   const prepared=new WeakMap();
   const database=input.rollbackResult?{prepare(sql){const s=original.prepare(sql);prepared.set(s,sql);const bind=s.bind.bind(s);s.bind=(...args)=>{const r=bind(...args);prepared.set(r,sql);return r;};return s;},
    batch(statements){if(statements.some(s=>prepared.get(s)?.includes("INSERT INTO attempt_resolutions")))
      return original.batch([...statements.slice(0,2),original.prepare("INSERT INTO transaction_guards VALUES('matrix-rollback',0)"),...statements.slice(2)]).catch(async error=>{if(input.holdRollback){phases.set(input.partitionId,"result_rolled_back");await new Promise(()=>{});}throw error;});
     return original.batch(statements);}}:original;
   const fault=async point=>{
    seen.push(point);phases.set(input.partitionId,point);
    if(point==="preflight_committed")clock=input.beforeAge??0;
    if(point==="marker_committed")clock=input.afterAge??input.beforeAge??0;
    if(input.gateChange===point)await original.prepare("UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='deployment'").run();
    if(input.stop===point)throw new Error("matrix_boundary_stop");
    if(input.hold===point)await new Promise(()=>{});
   };
   try{
    const result=await consumePartition({...env,DB:database,FGA_DISPATCH_ENABLED:"1"},input.partitionId,input.revision??null,input.source??"hint",
      req=>{phases.set(input.partitionId,"provider_handoff");return fetch(req);},{fault,monotonicUs:()=>clock,
       transport:original=>({...original,
        async preflight(context){const value=await original.preflight(context);if(input.intervene)await original.membership(context);return value;},
        async prepareAdd(context){const prepared=await original.prepareAdd(context);if(input.proveNotSent)prepared.dispose();return prepared;}}),
       reservation:original=>{let checks=0;return !original?null:{...original,
        check(context){checks++;return original.check(input.scopeMismatch&&checks===2?{...context,groupId:"wrong-scope"}:context);}}}
      });
    return Response.json({result,seen,postMarkerAuthorityReads});
   }catch{return Response.json({result:"boundary_stopped",seen,postMarkerAuthorityReads},{status:409});}
  }
  if(input.action==="scheduled"){
   await production.scheduled({scheduledTime:Date.now(),cron:"* * * * *"},env);
   return Response.json({scheduled:true});
  }
  return new Response(null,{status:404});
 }
};
