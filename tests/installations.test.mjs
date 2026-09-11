import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { authenticate, CREDENTIAL, credentialDigest, representation } from "../src/installations.ts";
import api from "../src/worker.ts";
const token=Array(13).fill("0000").join("-");
const row={installation_id:"i",credential_class:"lrc_plugin",installation_state:"active",revision:"7",version_id:"v1",version_state:"current",current_version_id:"v1",pending_version_id:null,expires_at_us:null,now_us:"1900000000000000",current_count:1,pending_count:0};
const req=(auth=`Bearer ${token}`,url="https://test.invalid/api/v001/installations/current",headers={})=>new Request(url,{headers:{...(auth===null?{}:{Authorization:auth}),...headers}});
const checkError=async(r,status,code)=>{assert.equal(r.status,status);assert.equal(r.headers.get("cache-control"),"no-store");const body=await r.json();assert.equal(body.error.code,code);assert.match(body.error.correlationId,/^[a-f0-9-]{36}$/);assert.equal(JSON.stringify(body).includes(token),false);return body;};
test("canonical 64-character credential hashes complete ASCII including hyphens",async()=>{
 assert.equal(token.length,64); assert(CREDENTIAL.test(token));
 assert.equal(await credentialDigest(token),createHash("sha256").update(token,"ascii").digest("hex"));
 for(const bad of [token.toLowerCase().replace("0","a"),token.replace("0","O"),token.slice(1),token.replaceAll("-",""),token.slice(0,-1)+"1"," "+token,token+" "]) assert.equal(CREDENTIAL.test(bad),false);
});
test("envelope rejection and malformed/unknown credentials never leak or query unnecessarily",async()=>{
 let calls=0;const lookup=async()=>{calls++;return null;};
 for (const request of [req(null),req("Basic abc")]) { const r=await authenticate(request,lookup,true);assert.equal(r.status,401);assert.equal(await r.text(),"");assert.equal(r.headers.get("www-authenticate"),'Bearer realm="fga-api"'); }
 for(const request of [req("Bearer"),req(`Bearer ${token}, Bearer ${token}`),req(`Bearer ${token}`,"https://test.invalid/?x=1"),req(`Bearer ${token}`,undefined,{"Content-Length":"1"})]) await checkError(await authenticate(request,lookup,true),400,"invalid_request");
 for(const value of ["broken",token+"x"," "+token,token.slice(0,-1)+"1"]) await checkError(await authenticate(req("Bearer "+value),lookup,true),401,"invalid_token");
 assert.equal(calls,0);await checkError(await authenticate(req(),lookup,true),401,"invalid_token");assert.equal(calls,1);
});
test("all credential states, DB expiry boundary, scope and response shape",async()=>{
 const current=representation(row,true,()=>assert.fail("integrity"));assert.deepEqual(current,{schemaVersion:1,installationId:"i",installationRevision:7,installationState:"active",presentedCredentialState:"current"});
 const pending={...row,version_id:"v2",version_state:"pending_rotation",pending_version_id:"v2",pending_count:1,expires_at_us:"1900000000000001"};
 assert.equal(representation(pending,true,()=>{}).presentedCredentialState,"pending_rotation");
 await checkError(representation(pending,false,()=>{}),403,"insufficient_scope");
 for (const delta of ["1900000000000000","1899999999999999"]) await checkError(representation({...pending,expires_at_us:delta},true,()=>{}),401,"invalid_token");
 for (const state of ["replaced","revoked","expired_unactivated"]) await checkError(representation({...row,version_state:state},true,()=>{}),401,"invalid_token");
 await checkError(representation({...row,installation_state:"revoked"},true,()=>{}),401,"invalid_token");
});
test("unknown and inconsistent storage states fail closed with sanitized alert",async()=>{
 for (const patch of [{credential_class:"unknown"},{installation_state:"unknown"},{version_state:"unknown"},{revision:"9007199254740992"},{revision:"0"},{revision:7},{current_count:2},{pending_count:2},{pending_count:1},{current_version_id:"wrong"},{expires_at_us:"123"},{installation_id:null},{now_us:"bad"}]) {
  let alerts=0;await checkError(representation({...row,...patch},true,()=>alerts++),401,"invalid_token");assert.equal(alerts,1);
 }
});
test("fresh lookup each request and generic unavailable response",async()=>{
 let calls=0; const lookup=async()=>{calls++;return calls===1?row:null;};
 assert.equal((await authenticate(req(),lookup,true)).installationId,"i");await checkError(await authenticate(req(),lookup,true),401,"invalid_token");assert.equal(calls,2);
 await checkError(await authenticate(req(),async()=>{throw new Error(token);},true),503,"service_unavailable");
});
test("routing and external maintenance gate do not touch storage or leak assets",async()=>{
 const env={DB:{prepare(){assert.fail("unexpected DB read");}},ASSETS:{fetch(){assert.fail("unexpected asset fallback");}}};
 await checkError(await api.fetch(req(),env),503,"service_unavailable");
 const wrong=await api.fetch(new Request("https://test.invalid/api/v001/installations/current",{method:"POST"}),env);assert.equal(wrong.status,405);assert.equal(wrong.headers.get("allow"),"GET");
 for(const path of ["/api","/api/","/api/v001/installations/token-check","/api/v001/unknown","/healthz/unknown","/anything","/api%2fv001/installations/current","/api/%ZZ"]) {
 const r=await api.fetch(new Request("https://test.invalid"+path),env);assert([400,404].includes(r.status));assert.equal(r.headers.get("cache-control"),"no-store");
 }
});
