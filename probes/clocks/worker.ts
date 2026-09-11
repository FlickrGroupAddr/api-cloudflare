// Disposable timing diagnostics. This Worker has no Flickr credential or real Flickr route.
import { preflightIsFresh } from "../../src/dispatch_freshness.ts";
import { NOW_US_SQL } from "../../src/installations.ts";
interface Env { DB:D1Database; COORD:DurableObjectNamespace; PROOF_TOKEN:string; PROOF_BUILD:string; PROOF_EXPIRES:string; }
interface Trial { id:string;target:"worker"|"object";beforeMarkerIterations?:number;afterMarkerIterations?:number;afterRefreshIterations?:number;markerDelayMs?:number;afterMarkerWaitMs?:number;refreshBeforeDispatch?:boolean;clockShiftMs?:number;wallOnlyShiftMs?:number;origin?:string; }
interface Clocks { wallMs:number;perfMs:number;hrNs:string|null; }
function clocks():Clocks {
 const process=(globalThis as unknown as {process?:{hrtime?:{bigint?:()=>bigint}}}).process;
 return {wallMs:Date.now(),perfMs:performance.now(),hrNs:process?.hrtime?.bigint?.().toString()??null};
}
function burn(iterations=0):number {
 if(!Number.isSafeInteger(iterations)||iterations<0||iterations>800_000_000) throw new Error("invalid_cpu_bound");
 let value=0x12345678;
 for(let i=0;i<iterations;i++) {value=Math.imul(value^(value>>>13),1597334677);value^=value>>>17;value=(value+2654435769)|0;}
 return value;
}
function boundedMs(value=0):number {if(!Number.isInteger(value)||value<0||value>2000)throw new Error("invalid_wait");return value;}
function hrDelta(a:Clocks,b:Clocks):number|null {return a.hrNs===null||b.hrNs===null?null:Number(BigInt(b.hrNs)-BigInt(a.hrNs))/1e6;}
async function peerFetch(env:Env,origin:string,path:string,input:unknown):Promise<Record<string,number>> {
 const response=await fetch(origin+path,{method:"POST",headers:{Authorization:"Bearer "+env.PROOF_TOKEN,"Content-Type":"application/json"},body:JSON.stringify(input),redirect:"manual"});
 if(!response.ok)throw new Error("peer_unavailable");return response.json();
}
async function trial(env:Env,input:Trial):Promise<unknown> {
 if(!/^[a-z0-9-]{1,64}$/.test(input.id))throw new Error("invalid_trial");
 const origin=input.origin!;
 if(Number(await env.DB.prepare("SELECT count(*) n FROM clock_trials").first("n"))>=100)throw new Error("trial_budget_exhausted");
 await peerFetch(env,origin,"/peer/preflight",{id:input.id});
 const received=clocks();
 await env.DB.prepare("INSERT INTO clock_trials(id,target,receipt_wall_ms,receipt_perf_ms) VALUES(?,?,?,?)").bind(input.id,input.target,received.wallMs,received.perfMs).run();
 const beforeCpu=clocks();const beforeDigest=burn(input.beforeMarkerIterations);const afterBeforeCpu=clocks();
 if(input.markerDelayMs)await peerFetch(env,origin,"/peer/delay",{delayMs:boundedMs(input.markerDelayMs)});
 await env.DB.batch([env.DB.prepare(`UPDATE clock_trials SET marker_us=${NOW_US_SQL} WHERE id=?`).bind(input.id)]);
 const markerCommitted=clocks();
 const afterDigest=burn(input.afterMarkerIterations);const afterCpu=clocks();
 if(input.afterMarkerWaitMs)await scheduler.wait(boundedMs(input.afterMarkerWaitMs));
 if(input.refreshBeforeDispatch)await env.DB.prepare("SELECT 1").first();
 const refreshed=clocks();const residualDigest=burn(input.afterRefreshIterations);
 const handoff=clocks();
 const shift=input.clockShiftMs??0,wallShift=input.wallOnlyShiftMs??0;
 if(!Number.isFinite(shift)||Math.abs(shift)>10_000||!Number.isFinite(wallShift)||Math.abs(wallShift)>600_000)throw new Error("invalid_clock_injection");
 const eligible=preflightIsFresh(Math.trunc(received.perfMs*1000),Math.trunc((handoff.perfMs+shift)*1000));
 // Deliberately no await or clock-refreshing operation between the check and fetch.
 const response=eligible?await peerFetch(env,origin,"/peer/post",{id:input.id}):null;
 const row=await env.DB.prepare("SELECT CAST(marker_us AS TEXT) markerUs,peer_post_count postCount,peer_post_wall_ms peerPostWallMs FROM clock_trials WHERE id=?").bind(input.id).first<{markerUs:string;postCount:number;peerPostWallMs:number|null}>();
 return {id:input.id,target:input.target,eligible,postCount:row?.postCount,markerCommitted:row?.markerUs!==null,
  cpuBeforeMarkerPerfMs:afterBeforeCpu.perfMs-beforeCpu.perfMs,cpuBeforeMarkerHrMs:hrDelta(beforeCpu,afterBeforeCpu),
  cpuAfterMarkerPerfMs:afterCpu.perfMs-markerCommitted.perfMs,cpuAfterMarkerHrMs:hrDelta(markerCommitted,afterCpu),
  cpuAfterRefreshPerfMs:handoff.perfMs-refreshed.perfMs,cpuAfterRefreshHrMs:hrDelta(refreshed,handoff),
  observedAgeMs:handoff.perfMs-received.perfMs,ageAtMarkerMs:markerCommitted.perfMs-received.perfMs,
  peerReceiptGapMs:response?response.wallMs-received.wallMs:null,
  peerMarkerVisible:response?.markerVisible??null,performanceEqualsDate:handoff.perfMs===handoff.wallMs,
  injectedWallAgeMs:handoff.wallMs+wallShift-received.wallMs,hrtimeAvailable:received.hrNs!==null,
  fingerprints:[beforeDigest,afterDigest,residualDigest]};
}
export class ProbePartitionWake {
 private env:Env;
 constructor(_ctx:DurableObjectState,env:Env){this.env=env;}
 async fetch(request:Request):Promise<Response>{
  if(Date.now()>Number(this.env.PROOF_EXPIRES))return new Response(null,{status:410});
  return Response.json(await trial(this.env,await request.json() as Trial));
 }
}
export default {
 async fetch(request:Request,env:Env):Promise<Response> {
  const path=new URL(request.url).pathname;
  if(Date.now()>Number(env.PROOF_EXPIRES)||request.headers.get("Authorization")!=="Bearer "+env.PROOF_TOKEN)return new Response(null,{status:401});
  const reply=(result:unknown)=>Response.json({build:env.PROOF_BUILD,result},{headers:{"Cache-Control":"no-store"}});
  if(path==="/status"){await env.DB.prepare("SELECT 1").first();return reply({ready:true});}
  if(request.method!=="POST")return new Response(null,{status:405});
  try {
   if(path==="/peer/preflight")return Response.json({wallMs:Date.now(),moderated:0});
   if(path==="/peer/delay") {const input=await request.json() as {delayMs:number};await scheduler.wait(boundedMs(input.delayMs));return Response.json({wallMs:Date.now()});}
   if(path==="/peer/post") {
    const wallMs=Date.now();const input=await request.json() as {id:string};
    const row=await env.DB.prepare("UPDATE clock_trials SET peer_post_count=peer_post_count+1,peer_post_wall_ms=? WHERE id=? AND peer_post_count=0 RETURNING marker_us IS NOT NULL AS markerVisible").bind(wallMs,input.id).first<{markerVisible:number}>();
    if(!row)return new Response(null,{status:409});return Response.json({wallMs,markerVisible:row.markerVisible});
   }
   if(path!=="/proof")return new Response(null,{status:404});
   const input=await request.json() as Trial;input.origin=new URL(request.url).origin;
   if(input.target==="object") {
    const response=await env.COORD.get(env.COORD.idFromName("clock-proof")).fetch("https://internal.invalid/trial",{method:"POST",body:JSON.stringify(input)});
    if(!response.ok)throw new Error("actor_unavailable");return reply(await response.json());
   }
   if(input.target!=="worker")throw new Error("invalid_target");return reply(await trial(env,input));
  }catch{return new Response(null,{status:409,headers:{"Cache-Control":"no-store"}});}
 }
} satisfies ExportedHandler<Env>;
