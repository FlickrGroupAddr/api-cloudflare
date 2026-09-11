// Miniflare requires Node. Python owns fixture orchestration and assertions.
import { readFile } from "node:fs/promises";
import { Miniflare } from "miniflare";
const config=JSON.parse(await readFile(process.argv[2],"utf8"));
let outboundCalls=0,fixtureCalls=0,ownOrigin="";
const mf=new Miniflare({modules:true,script:await readFile(config.bundle,"utf8"),compatibilityDate:"2026-07-30",
 host:"127.0.0.1",port:0,cf:false,logRequests:false,telemetry:{enabled:false},d1Databases:["DB"],
 durableObjects:{COORD:{className:"ProbePartitionWake",useSQLite:true}},
 bindings:{...config.vars,PROOF_TOKEN:process.env.FGA_COORDINATION_TOKEN},
 async outboundService(request){if(config.vars.PROOF_MODE==="fail-polite" && new URL(request.url).origin===ownOrigin && new URL(request.url).pathname==="/fake") {fixtureCalls++;return fetch(request.url,{method:request.method,headers:Object.fromEntries(request.headers),body:request.method==="GET"?undefined:await request.arrayBuffer()});}outboundCalls++;throw new Error("external_network_forbidden");}});
try {
 const db=await mf.getD1Database("DB");
 for(const migration of config.statements) await db.batch(migration.map(sql=>db.prepare(sql)));
 ownOrigin=new URL(String(await mf.ready)).origin;console.log(JSON.stringify({url:String(await mf.ready)}));
 process.stdin.resume();await new Promise(resolve=>process.stdin.once("end",resolve));
 console.log(JSON.stringify({outboundCalls,fixtureCalls}));
} finally {await mf.dispose();}
