// Miniflare and Wrangler need Node; Python controls fixtures, assertions and resources.
import {readFile} from "node:fs/promises";
import path from "node:path";
import https from "node:https";
import {Miniflare} from "miniflare";
import {maybeStartOrUpdateRemoteProxySession} from "wrangler";
const config=JSON.parse(await readFile(process.argv[2],"utf8"));
let remote,mf;let localIds={};
const localSlots=Object.fromEntries(["FLICKR_GRANT",...Array.from({length:5},(_,i)=>"FLICKR_TEMP_"+i)].map((name,i)=>["c".repeat(31)+i,name]));
try {
 if(config.remote){remote=await maybeStartOrUpdateRemoteProxySession({path:config.wrangler});await remote.session.ready;}
 const modules=[{type:"ESModule",path:path.join(config.directory,"driver.mjs"),contents:await readFile(config.driver,"utf8")},
                {type:"ESModule",path:path.join(config.directory,"production.mjs"),contents:await readFile(config.artifact,"utf8")}];
 const ca=await readFile(config.certificate);
 mf=new Miniflare({modules,modulesRoot:config.directory,compatibilityDate:"2026-07-30",compatibilityFlags:["nodejs_compat"],
  host:"127.0.0.1",port:0,cf:false,logRequests:false,telemetry:{enabled:false},
  d1Databases:config.remote?{DB:{id:config.databaseId,remoteProxyConnectionString:remote.session.remoteProxyConnectionString}}:["DB"],
  d1Persist:path.join(config.directory,"d1"),durableObjects:{COORD:{className:"PartitionWorker",useSQLite:true}},
  durableObjectsPersist:path.join(config.directory,"objects"),secretsStorePersist:path.join(config.directory,"secrets"),bindings:{...config.bindings,MATRIX_TOKEN:process.env.FGA_MATRIX_TOKEN},
  secretsStoreSecrets:{FLICKR_APPLICATION:{store_id:"matrix",secret_name:"application"},AUTH_LIMITER_KEY:{store_id:"matrix",secret_name:"limiter"},...(!config.native?{FLICKR_GRANT:{store_id:"matrix",secret_name:"grant"},NATIVE_WRITER_TOKEN:{store_id:"matrix",secret_name:"writer"},...Object.fromEntries(Array.from({length:5},(_,i)=>["FLICKR_TEMP_"+i,{store_id:"matrix",secret_name:"temp-"+i}]))}:{})},
  serviceBindings:{ASSETS:async request=>{
   const pathname=new URL(request.url).pathname;
   if(!pathname.startsWith("/admin/")||pathname.includes(".."))return new Response(null,{status:404});
   const file=path.join(config.assetDirectory,pathname.slice(1));
   try{return new Response(await readFile(file),{headers:{"Content-Type":file.endsWith(".html")?"text/html; charset=utf-8":file.endsWith(".css")?"text/css":"text/javascript"}});}
   catch{return new Response(null,{status:404});}
  },...(config.native?Object.fromEntries(config.native.services.map(x=>[x.binding,{name:x.service,entrypoint:x.entrypoint,remoteProxyConnectionString:remote.session.remoteProxyConnectionString}])):{})},
  async outboundService(request){
   const url=new URL(request.url);
   if(!config.native&&url.origin==="https://api.cloudflare.com"){
    const prefix="/client/v4/accounts/"+"a".repeat(32)+"/secrets_store/stores/"+"b".repeat(32)+"/secrets/";
    const binding=localSlots[url.pathname.slice(prefix.length)];
    if(request.method!=="PATCH"||!url.pathname.startsWith(prefix)||!binding||request.headers.get("Authorization")!=="Bearer matrix-writer-credential-for-fixtures")
      return new Response(null,{status:403});
    const payload=await request.json();
    await(await mf.getSecretsStoreSecretAPI(binding))().create(payload.value,localIds[binding]);
    return Response.json({success:true});
   }
   if(config.native&&url.origin==="https://api.cloudflare.com"){
    const prefix="/client/v4/accounts/"+config.native.variables.CF_ACCOUNT_ID+"/secrets_store/stores/"+config.native.variables.CF_SECRET_STORE_ID+"/secrets/";
    if(request.method!=="PATCH"||!url.pathname.startsWith(prefix)||!config.native.slots.includes(url.pathname.slice(prefix.length)))
      throw new Error("matrix_native_write_outside_owned_slots");
    return fetch(request.url,{method:request.method,headers:Object.fromEntries(request.headers),body:await request.arrayBuffer(),redirect:"manual"});
   }
   if(url.origin!=="https://www.flickr.com")throw new Error("matrix_external_egress_forbidden");
   const body=request.method==="GET"?null:Buffer.from(await request.arrayBuffer());
   return new Promise((resolve,reject)=>{
    const outgoing=https.request({hostname:"127.0.0.1",servername:"localhost",port:config.peerPort,path:url.pathname+url.search,
     method:request.method,headers:{...Object.fromEntries(request.headers),host:"www.flickr.com",...(body?{"content-length":String(body.length)}:{})},ca},response=>{
      const parts=[];response.on("data",x=>parts.push(x));response.on("error",reject);
      response.on("end",()=>resolve(new Response(Buffer.concat(parts),{status:response.statusCode,headers:response.headers})));
    });outgoing.on("error",error=>{console.error("matrix_peer_connection_failed",error.code);reject(error);});if(body)outgoing.write(body);outgoing.end();
   });
  }});
 const db=await mf.getD1Database("DB");
 if(!config.resume){
  if(!config.remote)for(const statements of config.migrations)await db.batch(statements.map(sql=>db.prepare(sql)));
  await(await mf.getSecretsStoreSecretAPI("FLICKR_APPLICATION"))().create(JSON.stringify({schemaVersion:1,consumerKey:"matrix-key",consumerSecret:"matrix-secret"}));
  await(await mf.getSecretsStoreSecretAPI("AUTH_LIMITER_KEY"))().create("matrix-auth-limiter-key-with-at-least-32-characters");
  if(!config.native){
   localIds.FLICKR_GRANT=await(await mf.getSecretsStoreSecretAPI("FLICKR_GRANT"))().create(JSON.stringify({schemaVersion:1,generation:"matrix-generation",token:"matrix-token",tokenSecret:"matrix-token-secret"}));
   await(await mf.getSecretsStoreSecretAPI("NATIVE_WRITER_TOKEN"))().create("matrix-writer-credential-for-fixtures");
   for(let i=0;i<5;i++)localIds["FLICKR_TEMP_"+i]=await(await mf.getSecretsStoreSecretAPI("FLICKR_TEMP_"+i))().create(JSON.stringify({schemaVersion:1,generation:"initial",retired:true}));
   const {writeFile}=await import("node:fs/promises");await writeFile(path.join(config.directory,"local-secret-ids.json"),JSON.stringify(localIds));
  }
 }
 if(config.resume&&!config.native)localIds=JSON.parse(await readFile(path.join(config.directory,"local-secret-ids.json"),"utf8"));
 console.log("MATRIX_READY "+JSON.stringify({url:String(await mf.ready),pid:process.pid}));
 process.stdin.resume();await new Promise(resolve=>process.stdin.once("end",resolve));
}finally{await mf?.dispose();await remote?.session.dispose();}
