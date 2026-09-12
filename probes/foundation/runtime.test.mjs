// Node is required for the Miniflare API; operational orchestration remains Python.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { Miniflare } from "miniflare";
const credentials=Array.from({length:7},(_,i)=>Array(12).fill("0000").concat(`00${i}0`).join("-"));
test("local workerd/D1 schema guards and read-only current-installation slice",async()=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),"fga-foundation-"));
 const config=path.join(directory,"wrangler.json");
 await writeFile(config,JSON.stringify({name:"fga-foundation-local",main:path.resolve("probes/foundation/worker.ts"),compatibility_date:"2026-09-11",compatibility_flags:["nodejs_compat"],workers_dev:false}));
 execFileSync(process.execPath,["node_modules/typescript/bin/tsc","--noEmit"]);
 execFileSync(process.execPath,["node_modules/wrangler/bin/wrangler.js","deploy","--dry-run","--config",config,"--outdir",path.join(directory,"bundle")],{env:{...process.env,CI:"true",WRANGLER_WRITE_LOGS:"false",WRANGLER_SEND_METRICS:"false"},stdio:"pipe"});
 const script=await readFile(path.join(directory,"bundle/worker.js"),"utf8");let outbound=0;
 for(const mode of ["guards","read"]) {
  const mf=new Miniflare({modules:true,script,compatibilityDate:"2026-07-30",compatibilityFlags:["nodejs_compat"],host:"127.0.0.1",port:0,cf:false,logRequests:false,telemetry:{enabled:false},d1Databases:["DB"],
   bindings:{FGA_READ_ENABLED:"1",PROOF_TOKEN:"fixture-proof",PROOF_MODE:mode,PROOF_BUILD:"local",PROOF_EXPIRES:String(Date.now()+120000)},
   outboundService(){outbound++;throw new Error("No external network allowed");}});
  const call=async(action,body)=>mf.dispatchFetch("http://fixture.invalid/__proof/"+action,{method:body?"POST":"GET",headers:{Authorization:"Bearer fixture-proof"},...(body?{body:JSON.stringify(body)}:{})});
  try {
   const db=await mf.getD1Database("DB");
   for(const migration of ["0001_foundation.sql","0002_audit_component.sql"]) {
    const sql=(await readFile("migrations/"+migration,"utf8")).replace(/^--.*$/mg,"");
    await db.batch(sql.split(/(?=^CREATE |^ALTER )/m).filter(x=>x.trim()).map(s=>db.prepare(s)));
   }
   const seedRace=await Promise.all([call("seed",{credentials}),call("seed",{credentials})]);
   assert(seedRace.every(r=>r.status===200));
   assert.equal((await call("seed",{credentials})).status,200);
   assert.equal((await call("seed",{credentials:[...credentials.slice(1),credentials[0]]})).status,409);
   const initial=(await (await call("status")).json()).result.snapshot;
   if(mode==="guards") { const r=await (await call("guards",{})).json();assert.equal(r.result.cases.length,22);for(const c of r.result.cases) assert.equal(c.passed,true,c.id); }
   else {
    for(const [index,status,state] of [[0,200,"current"],[1,200,"pending_rotation"],[2,200,"current"],[3,401,null],[4,401,null],[5,401,null],[6,401,null]]) {
     const r=await mf.dispatchFetch("http://fixture.invalid/api/v001/installations/current",{headers:{Authorization:"Bearer "+credentials[index]}});
     assert.equal(r.status,status);assert.equal(r.headers.get("X-FGA-Proof-Build"),"local");assert.equal(r.headers.get("Cache-Control"),"no-store");const body=await r.json();
     if(status===200) {assert.equal(body.presentedCredentialState,state);assert.equal(Object.keys(body).length,5);} else assert.equal(body.error.code,"invalid_token");
    }
    assert.equal((await mf.dispatchFetch("http://fixture.invalid/__proof/ordinary",{headers:{Authorization:"Bearer fixture-proof","X-Fixture-Credential":"Bearer "+credentials[1]}})).status,403);
    assert.equal((await call("guards",{})).status,404);
   }
   assert.equal((await (await call("status")).json()).result.snapshot,initial);
   assert.equal((await db.prepare("PRAGMA foreign_key_check").all()).results.length,0);
  } finally {await mf.dispose();}
 }
 assert.equal(outbound,0);
});
