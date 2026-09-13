import test from "node:test";
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {mkdtemp,readFile,writeFile,rm} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {Miniflare} from "miniflare";
import {generateKeyPair,exportJWK,SignJWT} from "jose";

const origin="https://flickrgroupaddr.com";
const confirmations=Object.fromEntries(["ownerControlledWorkstation","privateBrowser","clipboardHistoryOff","clipboardSyncOff","noObserversOrRecording","pluginReady"].map(key=>[key,true]));
test("optimized production routes authenticate browser issuance and serialize native D1 credential rotation",async t=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),"fga-plugin-codes-runtime-"));
 const config=path.join(directory,"wrangler.json");await writeFile(config,JSON.stringify({name:"codes-native",main:path.resolve("src/worker.ts"),compatibility_date:"2026-09-11",compatibility_flags:["nodejs_compat"],workers_dev:false}));
 execFileSync(process.execPath,["node_modules/wrangler/bin/wrangler.js","deploy","--dry-run","--minify","--config",config,"--outdir",path.join(directory,"bundle")],{env:{...process.env,WRANGLER_WRITE_LOGS:"false",WRANGLER_SEND_METRICS:"false",CI:"true"},stdio:"pipe"});
 const migrations=JSON.parse(execFileSync("uv",["run","--frozen","python","-c","import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))"],{encoding:"utf8"}));
 const keys=await generateKeyPair("RS256"),jwk={...await exportJWK(keys.publicKey),kid:"key",alg:"RS256",use:"sig"};let external=0;
 const mf=new Miniflare({modules:true,script:await readFile(path.join(directory,"bundle/worker.js"),"utf8"),compatibilityDate:"2026-07-30",compatibilityFlags:["nodejs_compat"],cf:{colo:"LOCAL"},telemetry:{enabled:false},d1Databases:["DB"],bindings:{FGA_ADMIN_ENABLED:"1",FGA_READ_ENABLED:"1",FGA_INTAKE_ENABLED:"1",GOOGLE_CLIENT_ID:"client",GOOGLE_OWNER_SUB:"owner-subject"},secretsStoreSecrets:{AUTH_LIMITER_KEY:{store_id:"local",secret_name:"limiter"}},outboundService:async request=>{external++;assert.equal(request.url,"https://www.googleapis.com/oauth2/v3/certs");return Response.json({keys:[jwk]},{headers:{"Cache-Control":"public, max-age=3600"}});}});
 try{
  const db=await mf.getD1Database("DB");for(const batch of migrations)await db.batch(batch.map(sql=>db.prepare(sql)));
  await(await mf.getSecretsStoreSecretAPI("AUTH_LIMITER_KEY"))().create("synthetic-limiter-key-at-least-32-characters");
  const start=await mf.dispatchFetch(origin+"/admin/login",{headers:{"CF-Connecting-IP":"192.0.2.10"}});assert.equal(start.status,200);
  const page=await start.text(),nonce=/data-nonce="([^"]+)"/.exec(page)?.[1],state=/data-state="([^"]+)"/.exec(page)?.[1];assert(nonce&&state);
  const now=Math.floor(Date.now()/1000),credential=await new SignJWT({iss:"https://accounts.google.com",aud:"client",sub:"owner-subject",nonce,iat:now,exp:now+3600}).setProtectedHeader({alg:"RS256",kid:"key"}).sign(keys.privateKey);
  const login=await mf.dispatchFetch(origin+"/admin/google-login",{method:"POST",redirect:"manual",headers:{"CF-Connecting-IP":"192.0.2.10","Content-Type":"application/x-www-form-urlencoded",Cookie:"g_csrf_token=csrf"},body:new URLSearchParams({credential,state,g_csrf_token:"csrf"}).toString()});assert.equal(login.status,303);
  const cookie=login.headers.get("Set-Cookie").split(";")[0];
  const session=await(await mf.dispatchFetch(origin+"/api/v001/admin/session",{headers:{Cookie:cookie}})).json();
  const call=(path,method="GET",body,etag)=>mf.dispatchFetch(origin+path,{method,headers:{Cookie:cookie,...(method==="GET"?{}:{Origin:origin,"X-CSRF-Token":session.csrfToken,"Content-Type":"application/json"}),...(etag?{"If-Match":etag}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const created=await call("/api/v001/plugin-codes","POST",{schemaVersion:1,installationLabel:"Native test",transferConfirmations:confirmations});assert.equal(created.status,201);
  const first=await created.json(),id=first.pluginCodeId;assert(typeof first.pluginCode==="string");
  await db.prepare("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('retained-photo','retained-group','flickr_code_7','retained-attempt')").run();
  const detail=await call("/api/v001/plugin-codes/"+id),etag=detail.headers.get("ETag");assert(etag);
  const outcomes=await Promise.all([0,1].map(()=>call(`/api/v001/plugin-codes/${id}/rotation-candidates`,"POST",{schemaVersion:1,transferConfirmations:confirmations},etag)));
  assert.deepEqual(outcomes.map(x=>x.status).sort(),[201,412]);
  const candidate=await outcomes.find(x=>x.status===201).json();
  const current=await call("/api/v001/plugin-codes/"+id),parent=current.headers.get("ETag");
  const complete={schemaVersion:1,state:"current",pluginValidationConfirmed:true};
  const path=`/api/v001/plugin-codes/${id}/rotation-candidates/${candidate.rotationCandidateId}`;
  const completed=await Promise.all([0,1].map(()=>call(path,"PATCH",complete,parent)));assert(completed.every(x=>x.status===200));
  const rows=await db.prepare("SELECT state,COUNT(*) n FROM installation_credential_versions GROUP BY state").all();
  assert.equal(rows.results.find(x=>x.state==="current").n,1);assert.equal(rows.results.find(x=>x.state==="replaced").n,1);
  assert.equal((await mf.dispatchFetch(origin+"/api/v001/installations/current",{headers:{Authorization:"Bearer "+first.pluginCode}})).status,401);
  assert.equal((await mf.dispatchFetch(origin+"/api/v001/installations/current",{headers:{Authorization:"Bearer "+candidate.pluginCode}})).status,200);
  assert.equal((await db.prepare("SELECT first_reason FROM submission_blocks").first()).first_reason,"flickr_code_7");
  assert.equal((await db.prepare("SELECT COUNT(*) n FROM installation_lifecycle_events WHERE kind='rotation_completed'").first()).n,1);
  assert.equal(external,1,"only synthetic Google key fetch may occur; lifecycle makes no Flickr call");
  const list=await(await call("/api/v001/plugin-codes")).json();assert(!JSON.stringify(list).includes(candidate.pluginCode));
 }finally{await mf.dispose();await rm(directory,{recursive:true,force:true});}
});
