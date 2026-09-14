// Node is required by Miniflare; Python owns the kill/restart sequence and assertions.
// Bounded process-loss adapter proof, not the full production release runner.
import {readFile} from "node:fs/promises";
import path from "node:path";
import {Miniflare} from "miniflare";
const config=JSON.parse(await readFile(process.argv[2],"utf8"));
let ownOrigin="";
const mf=new Miniflare({modules:true,script:await readFile(config.bundle,"utf8"),
 compatibilityDate:"2026-07-30",host:"127.0.0.1",port:0,cf:false,logRequests:false,
 telemetry:{enabled:false},d1Databases:["DB"],d1Persist:path.join(config.persist,"d1"),
 durableObjects:{COORD:{className:"ProbePartitionWake",useSQLite:true}},
 durableObjectsPersist:path.join(config.persist,"do"),
 bindings:{...config.vars,PROOF_TOKEN:process.env.FGA_COORDINATION_TOKEN},
 async outboundService(request){
  if(new URL(request.url).origin!==ownOrigin||new URL(request.url).pathname!=="/fake")
   throw new Error("external_network_forbidden");
  return fetch(request.url,{method:request.method,headers:Object.fromEntries(request.headers),
   body:request.method==="GET"?undefined:await request.arrayBuffer()});
 }});
try {
 const db=await mf.getD1Database("DB");
 if(!config.resume)for(const migration of config.statements)
  await db.batch(migration.map(sql=>db.prepare(sql)));
 ownOrigin=new URL(String(await mf.ready)).origin;
 console.log(JSON.stringify({url:String(await mf.ready),pid:process.pid}));
 process.stdin.resume();await new Promise(resolve=>process.stdin.once("end",resolve));
} finally {await mf.dispose();}
