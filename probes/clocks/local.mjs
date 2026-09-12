// Miniflare's Node API owns the local runtime; Python owns cases and resource lifecycle.
import { readFile } from "node:fs/promises";
import { Miniflare } from "miniflare";
const config=JSON.parse(await readFile(process.argv[2],"utf8"));
let origin="",externalCalls=0,peerCalls=0;
const mf=new Miniflare({modules:true,script:await readFile(config.bundle,"utf8"),compatibilityDate:"2026-07-30",compatibilityFlags:["nodejs_compat","global_fetch_strictly_public"],host:"127.0.0.1",port:0,cf:false,logRequests:false,telemetry:{enabled:false},d1Databases:["DB"],durableObjects:{COORD:{className:"ProbePartitionWake",useSQLite:true}},bindings:{...config.vars,PROOF_TOKEN:process.env.FGA_CLOCK_TOKEN},
 async outboundService(request){const url=new URL(request.url);if(url.origin!==origin||!url.pathname.startsWith("/peer/")){externalCalls++;throw new Error("external_request_forbidden");}peerCalls++;return fetch(request.url,{method:request.method,headers:Object.fromEntries(request.headers),body:await request.arrayBuffer()});}});
try {
 const db=await mf.getD1Database("DB");await db.batch(config.statements.map(sql=>db.prepare(sql)));
 origin=new URL(String(await mf.ready)).origin;console.log(JSON.stringify({url:origin}));
 process.stdin.resume();await new Promise(resolve=>process.stdin.once("end",resolve));
 console.log(JSON.stringify({externalCalls,peerCalls}));
}finally {await mf.dispose();}
