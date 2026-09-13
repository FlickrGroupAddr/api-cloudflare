import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {sqlStore} from "./sql_store.mjs";
import {createWorker} from "../src/worker.ts";
import {digest} from "../src/browser_sessions.ts";
import {CREDENTIAL,NOW_US_SQL} from "../src/installations.ts";
import {encodePluginCode,expirePluginCodeCandidates} from "../src/plugin_codes.ts";

const ORIGIN="https://flickrgroupaddr.com";
const confirmations=Object.fromEntries(["ownerControlledWorkstation","privateBrowser","clipboardHistoryOff","clipboardSyncOff","noObserversOrRecording","pluginReady"].map(key=>[key,true]));
function fixture(t){
 const directory=mkdtempSync(join(tmpdir(),"fga-code-")),db=sqlStore(join(directory,"db.sqlite"));
 t.after(()=>{db.raw.close();rmSync(directory,{recursive:true,force:true});});
 const token="A".repeat(43),csrf="B".repeat(42)+"A",now=Date.now()*1000;
 db.raw.exec("INSERT INTO fga_users VALUES('owner'),('other');INSERT INTO admin_principals VALUES('owner','https://accounts.google.com','subject',1),('other','https://accounts.google.com','other-subject',1);");
 db.raw.prepare("INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id) VALUES('session',?,'owner',?,?,?,?,?,'correlation')").run(digest(token),csrf,now,now,now+86400000000,now);
 const env={DB:db,FGA_ADMIN_ENABLED:"1",FGA_READ_ENABLED:"1",FGA_INTAKE_ENABLED:"1",GOOGLE_CLIENT_ID:"client",GOOGLE_OWNER_SUB:"subject",AUTH_LIMITER_KEY:{get:async()=>"synthetic-cursor-key-at-least-32-characters"}};
 const worker=createWorker(async()=>assert.fail("Plugin Code routes must not call an upstream provider"));
 const call=async(path,method="GET",body,etag,options={})=>{
  const headers={Cookie:"__Host-fga_admin="+token,...(method==="GET"?{}:{Origin:ORIGIN,"X-CSRF-Token":csrf,"Content-Type":options.media??"application/json"}),...(etag?{"If-Match":etag}:{}),...options.headers};
  return worker.fetch(new Request(ORIGIN+path,{method,headers,...(body===undefined?{}:{body:JSON.stringify(body)})}),env);
 };
 const create=async(label="Workstation")=>{const response=await call("/api/v001/plugin-codes","POST",{schemaVersion:1,installationLabel:label,transferConfirmations:confirmations});assert.equal(response.status,201);assert.equal(response.headers.get("Pragma"),"no-cache");const body=await response.json();assert(CREDENTIAL.test(body.pluginCode),"canonical code required");assert.deepEqual(Object.keys(body).sort(),["pluginCode","pluginCodeId","schemaVersion"]);return body;};
 const detail=async id=>{const response=await call("/api/v001/plugin-codes/"+id);assert.equal(response.status,200);return {body:await response.json(),etag:response.headers.get("ETag")};};
 const bearer=async code=>worker.fetch(new Request(ORIGIN+"/api/v001/installations/current",{headers:{Authorization:"Bearer "+code}}),env);
 return {db,call,create,detail,bearer,env,worker};
}

test("canonical encoding retains all 256 bits and the required final padding",()=>{
 const zero=encodePluginCode(new Uint8Array(32));assert(CREDENTIAL.test(zero));assert.equal(zero,"0000-0000-0000-0000-0000-0000-0000-0000-0000-0000-0000-0000-0000");
 assert.equal(encodePluginCode(new Uint8Array(32).fill(255)),"ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZG");
 assert.throws(()=>encodePluginCode(new Uint8Array(31)));
});

test("real routes rotate one candidate, retain blocks, reject old credentials and replay no plaintext",async t=>{
 const f=fixture(t),first=await f.create(),id=first.pluginCodeId;
 assert.equal((await f.bearer(first.pluginCode)).status,200);
 f.db.raw.exec("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('photo','group','flickr_code_6','attempt')");
 let detail=await f.detail(id);
 assert(!JSON.stringify(detail.body).includes(first.pluginCode),"metadata must omit plaintext");
 const candidateResponse=await f.call(`/api/v001/plugin-codes/${id}/rotation-candidates`,"POST",{schemaVersion:1,transferConfirmations:confirmations},detail.etag);
 assert.equal(candidateResponse.status,201);const candidate=await candidateResponse.json();assert(CREDENTIAL.test(candidate.pluginCode));assert(candidate.pluginCode!==first.pluginCode);
 const pending=await f.bearer(candidate.pluginCode);assert.equal(pending.status,200);assert.equal((await pending.json()).presentedCredentialState,"pending_rotation");
 const wrongScope=await f.worker.fetch(new Request(ORIGIN+"/api/v001/group-submission-batches",{method:"POST",headers:{Authorization:"Bearer "+candidate.pluginCode,"Content-Type":"application/json"},body:"{}"}),f.env);assert.equal(wrongScope.status,403);
 detail=await f.detail(id);
 assert.equal((await f.call(`/api/v001/plugin-codes/${id}/rotation-candidates`,"POST",{schemaVersion:1,transferConfirmations:confirmations},detail.etag)).status,409);
 const path=`/api/v001/plugin-codes/${id}/rotation-candidates/${candidate.rotationCandidateId}`;
 const complete={schemaVersion:1,state:"current",pluginValidationConfirmed:true};
 const completed=await f.call(path,"PATCH",complete,detail.etag);assert.equal(completed.status,200);
 assert.equal((await f.bearer(first.pluginCode)).status,401);
 assert.equal((await (await f.bearer(candidate.pluginCode)).json()).presentedCredentialState,"current");
 const replay=await f.call(path,"PATCH",complete,detail.etag);assert.equal(replay.status,200);
 const replayBody=await replay.json();assert(!JSON.stringify(replayBody).includes(candidate.pluginCode));
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM installation_lifecycle_events WHERE kind='rotation_completed'").get().n,1);
 assert.equal(f.db.raw.prepare("SELECT first_reason FROM submission_blocks").get().first_reason,"flickr_code_6");
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM installation_credential_versions WHERE state='current'").get().n,1);
});

test("cancel and expiry preserve the old current; whole revocation invalidates every version",async t=>{
 const f=fixture(t),first=await f.create(),id=first.pluginCodeId;
 const candidate=async()=>{const d=await f.detail(id);const response=await f.call(`/api/v001/plugin-codes/${id}/rotation-candidates`,"POST",{schemaVersion:1,transferConfirmations:confirmations},d.etag);assert.equal(response.status,201);return response.json();};
 const a=await candidate();let d=await f.detail(id);
 const cancel=await f.call(`/api/v001/plugin-codes/${id}/rotation-candidates/${a.rotationCandidateId}`,"PATCH",{schemaVersion:1,state:"revoked"},d.etag);assert.equal(cancel.status,200);
 assert.equal((await f.bearer(first.pluginCode)).status,200);assert.equal((await f.bearer(a.pluginCode)).status,401);
 const b=await candidate();
 const expiryClock={...f.db,prepare:sql=>f.db.prepare(sql.replaceAll(NOW_US_SQL,String(Date.now()*1000+901_000_000)))};
 await expirePluginCodeCandidates(expiryClock);assert.equal((await f.bearer(b.pluginCode)).status,401);assert.equal((await f.bearer(first.pluginCode)).status,200);
 assert.equal((await f.detail(id)).body.lastLifecycleOutcome.kind,"rotation_expired");
 const c=await candidate();d=await f.detail(id);
 const revoked=await f.call(`/api/v001/plugin-codes/${id}`,"PATCH",{state:"revoked"},d.etag,{media:"application/merge-patch+json"});assert.equal(revoked.status,200);
 assert.equal((await f.bearer(first.pluginCode)).status,401);assert.equal((await f.bearer(c.pluginCode)).status,401);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM installation_credential_versions").get().n,4);
 assert.equal((await f.call(`/api/v001/plugin-codes/${id}/rotation-candidates/${c.rotationCandidateId}`,"PATCH",{schemaVersion:1,state:"current",pluginValidationConfirmed:true},d.etag)).status,412);
});

test("browser boundary, transfer confirmations, validators and unknown routes fail without mutation",async t=>{
 const f=fixture(t),body={schemaVersion:1,installationLabel:"Workstation",transferConfirmations:confirmations};
 assert.equal((await f.call("/api/v001/plugin-codes","POST",body,undefined,{headers:{Origin:"https://wrong.example"}})).status,403);
 assert.equal((await f.call("/api/v001/plugin-codes","POST",{...body,transferConfirmations:{...confirmations,privateBrowser:false}})).status,400);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM installations").get().n,0);
 const first=await f.create(),id=first.pluginCodeId,path=`/api/v001/plugin-codes/${id}/rotation-candidates`;
 assert.equal((await f.call(path,"POST",{schemaVersion:1,transferConfirmations:confirmations})).status,428);
 for(const tag of ['*','W/"pc:'+id+':1"','"pc:'+id+':99"'])assert.equal((await f.call(path,"POST",{schemaVersion:1,transferConfirmations:confirmations},tag)).status,412);
 assert.equal((await f.call("/api/v001/plugin-codes/foreign")).status,404);
 assert.equal((await f.call(`/api/v001/plugin-codes/${id}/complete`,"POST",{})).status,404);
 assert.equal((await f.call(path,"DELETE",{})).status,405);
 assert.equal((await f.call("/api/v001/plugin-codes?debug=1")).status,400);
 f.db.raw.prepare("UPDATE admin_sessions SET revoked_at_us=?,revocation_reason='owner' WHERE session_id='session'").run(Date.now()*1000);
 assert.equal((await f.call("/api/v001/plugin-codes")).status,401);
});

test("audit failure rolls back issuance and list data is not released without its audit",async t=>{
 const f=fixture(t);f.db.raw.exec("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT,'synthetic_audit_failure'); END;");
 const response=await f.call("/api/v001/plugin-codes","POST",{schemaVersion:1,installationLabel:"Workstation",transferConfirmations:confirmations});assert.equal(response.status,503);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM installations").get().n,0);
 const list=await f.call("/api/v001/plugin-codes");assert.equal(list.status,503);assert(!Object.hasOwn(await list.json(),"pluginCodes"));
});

test("list cursors are owner/query bound and never return digests or plaintext",async t=>{
 const f=fixture(t);await f.create("one");await f.create("two");
 const first=await f.call("/api/v001/plugin-codes?page_size=1"),page=await first.json();assert.equal(first.status,200);assert.equal(page.pluginCodes.length,1);assert(page.nextPageToken);
 const second=await (await f.call("/api/v001/plugin-codes?page_size=1&page_token="+encodeURIComponent(page.nextPageToken))).json();
 assert.equal(second.pluginCodes.length,1);assert(second.pluginCodes[0].pluginCodeId!==page.pluginCodes[0].pluginCodeId);assert(!Object.hasOwn(second,"nextPageToken"));
 assert.equal((await f.call("/api/v001/plugin-codes?page_size=2&page_token="+encodeURIComponent(page.nextPageToken))).status,400);
 assert(!JSON.stringify(page).includes("credential_digest"));
});
