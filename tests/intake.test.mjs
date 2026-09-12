import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { Miniflare } from "miniflare";
const CODE="0000-".repeat(12)+"0000";
test("real native bindings verify photos and admit one authenticated batch",async(t)=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),"fga-intake-"));
 const config=path.join(directory,"wrangler.json");
 await writeFile(config,JSON.stringify({name:"intake-local",main:path.resolve("probes/intake/worker.ts"),compatibility_date:"2026-09-11",compatibility_flags:["nodejs_compat","global_fetch_strictly_public"],workers_dev:false}));
 execFileSync(process.execPath,["node_modules/typescript/bin/tsc","--noEmit"]);
 execFileSync(process.execPath,["node_modules/wrangler/bin/wrangler.js","deploy","--dry-run","--config",config,"--outdir",path.join(directory,"bundle")],{env:{...process.env,WRANGLER_WRITE_LOGS:"false",WRANGLER_SEND_METRICS:"false",CI:"true"},stdio:"pipe"});
 const migrations=JSON.parse(execFileSync("uv",["run","--frozen","python","-c","import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]+[statements(Path('probes/intake/schema.sql').read_text())]))"],{encoding:"utf8"}));
 let base="",external=0;
 const mf=new Miniflare({modules:true,script:await readFile(path.join(directory,"bundle/worker.js"),"utf8"),compatibilityDate:"2026-07-30",compatibilityFlags:["nodejs_compat","global_fetch_strictly_public"],host:"127.0.0.1",port:0,cf:false,logRequests:false,telemetry:{enabled:false},d1Databases:["DB"],durableObjects:{COORD:{className:"ProbePartitionWake",useSQLite:true}},
 secretsStoreSecrets:{FLICKR_APPLICATION:{store_id:"intake-store",secret_name:"application"},FLICKR_GRANT:{store_id:"intake-store",secret_name:"grant"}},
 bindings:{PROOF_TOKEN:"synthetic-control",PROOF_BUILD:"local",FGA_READ_ENABLED:"1",FGA_INTAKE_ENABLED:"1",FGA_MAX_GROUP_IDS_PER_BATCH:"60"},
 async outboundService(request){if(new URL(request.url).origin!==base||new URL(request.url).pathname!=="/probe/peer"){external++;throw new Error("unexpected_external_request");}return fetch(request.url,{method:request.method,headers:Object.fromEntries(request.headers),body:await request.arrayBuffer()});}});
 try {
  base=String(await mf.ready).replace(/\/$/,"");const db=await mf.getD1Database("DB");
  for(const statements of migrations)await db.batch(statements.map(sql=>db.prepare(sql)));
  await (await mf.getSecretsStoreSecretAPI("FLICKR_APPLICATION"))().create(JSON.stringify({schemaVersion:1,consumerKey:"synthetic-app-key",consumerSecret:"synthetic-app-secret"}));
  const grantApi=(await mf.getSecretsStoreSecretAPI("FLICKR_GRANT"))();const grantId=await grantApi.create(JSON.stringify({schemaVersion:1,generation:"generation-a",token:"synthetic-token",tokenSecret:"synthetic-token-secret"}));
  const control=async(name,body={})=>{const response=await mf.dispatchFetch(base+"/probe/"+name,{method:"POST",headers:{Authorization:"Bearer synthetic-control","Content-Type":"application/json"},body:JSON.stringify(body)});assert.equal(response.status,200);return (await response.json()).result;};
  await control("seed");
  const api=async(url,body,credential=CODE,extra={})=>{const response=await mf.dispatchFetch(base+url,{method:"POST",headers:{...(credential?{Authorization:"Bearer "+credential}:{}),"Content-Type":"application/json",...extra},body:JSON.stringify(body)});const text=await response.text();return {status:response.status,body:text?JSON.parse(text):null,headers:response.headers};};
  const proof=await api("/api/v001/existing-public-photo-bindings",{schemaVersion:1,flickrPhotoId:"photo-a",expectedLinkedFlickrRevision:1});
  assert.equal(proof.status,201,JSON.stringify(proof.body));assert.equal(proof.body.sourceKind,"existing_public_flickr_photo");
  const input={schemaVersion:2,photoBinding:{fgaPhotoBindingId:proof.body.fgaPhotoBindingId,expectedVerificationRevision:proof.body.verificationRevision},flickrGroupIds:["group-z","group-a","group-b"]};
  const first=await api("/api/v001/group-submission-batches",input);assert.equal(first.status,202,JSON.stringify(first.body));
  assert.deepEqual(Object.keys(first.body).sort(),["fgaPhotoBindingId","flickrPhotoId","schemaVersion","submissions"]);
  assert.deepEqual(first.body.submissions.map(x=>x.flickrGroupId),input.flickrGroupIds);
  assert(first.body.submissions.every(x=>x.created));
  let state=await control("state");assert.equal(state.intake_probe_calls.length,1);assert.equal(state.intake_probe_hints.length,1);assert.equal(state.submission_intents.length,3);
  assert(!JSON.stringify(state).includes("Must not persist"));
  const again=await api("/api/v001/group-submission-batches",input);assert.equal(again.status,202);assert(again.body.submissions.every(x=>!x.created));
  state=await control("state");assert.equal(state.intake_probe_hints.length,1);assert.equal(state.intake_probe_calls.length,1);
  const batchPath="/api/v001/group-submission-batches",bindingPath="/api/v001/existing-public-photo-bindings";
  let serial=0;
  const fresh=async(groups)=>{await control("control");const r=await api(bindingPath,{schemaVersion:1,flickrPhotoId:"case-photo-"+(++serial),expectedLinkedFlickrRevision:1});assert.equal(r.status,201,JSON.stringify(r.body));return {schemaVersion:2,photoBinding:{fgaPhotoBindingId:r.body.fgaPhotoBindingId,expectedVerificationRevision:r.body.verificationRevision},flickrGroupIds:groups};};
  const snapshot=async()=>JSON.stringify(await control("state"));
  await t.test("CBA-ROUTE-003 aliases never reach a handler or shell",async()=>{
   for(const route of ["/api/v001/group-submission","/api/v001/group-submissions","/api/v001/photos/photo-a/groups","/api/v001/group-submission-batches/group-a"]){const r=await api(route,{});assert([404,405].includes(r.status));assert.equal(r.body.error.code,"not_found");}
  });
  await t.test("CBA-ROUTE-004 unknown stored credential class fails closed",async()=>{
   const v=await fresh(["future-class"]);await control("control",{futureClass:1});const before=await snapshot();const r=await api(batchPath,v);assert.equal(r.status,401);assert.equal(await snapshot(),before);await control("control");
  });
  await t.test("CBA-VALID-001 whole request validation precedes mutation",async()=>{
   const v=await fresh(["valid"]);
   for(const groups of [[],["duplicate","duplicate"],["valid","bad group"],Array.from({length:61},(_,i)=>"g"+i)]){const before=await snapshot();const r=await api(batchPath,{...v,flickrGroupIds:groups});assert.equal(r.status,400);assert.equal(await snapshot(),before);}
   const before=await snapshot();assert.equal((await api(batchPath,{...v,force:true})).status,400);assert.equal(await snapshot(),before);
  });
  await t.test("CBA-VALID-002 compiled schema validator and configuration share 60",async()=>{
   const v=await fresh(Array.from({length:60},(_,i)=>"limit-"+i));
   const generated=JSON.parse(await readFile("generated/openapi.json","utf8"));assert.equal(generated.paths[batchPath].post.requestBody.content["application/json"].schema.properties.flickrGroupIds.maxItems,60);
   await control("control",{limit:"61"});const before=await snapshot();assert.equal((await api(batchPath,v)).status,503);assert.equal(await snapshot(),before);
   await control("control");assert.equal((await api(batchPath,v)).status,202);
  });
  await t.test("CBA-TXN-001 complete missing selections commit before 202",async()=>{
   const v=await fresh(["new-c","new-a","new-b"]);const r=await api(batchPath,v);assert.equal(r.status,202);assert(r.body.submissions.every(x=>x.created));const st=await control("state");assert.equal(st.submission_intents.filter(x=>x.binding_id===v.photoBinding.fgaPhotoBindingId).length,3);assert.equal(st.transaction_guards.length,0);
  });
  await t.test("CBA-TXN-002 mixed existing/new keys preserve ordered snapshots",async()=>{
   const v=await fresh(["mix-a","mix-b"]);const first=await api(batchPath,v);const r=await api(batchPath,{...v,flickrGroupIds:["mix-b","mix-c","mix-a"]});assert.deepEqual(r.body.submissions.map(x=>x.created),[false,true,false]);assert.equal(r.body.submissions[0].fgaSubmissionIntentId,first.body.submissions[1].fgaSubmissionIntentId);
  });
  await t.test("CBA-TXN-003 every transaction boundary rolls back without a hint",async()=>{
   for(let fault=0;fault<=7;fault++){const v=await fresh(["rollback-a-"+fault,"rollback-b-"+fault]);await control("control",{fault});const before=await snapshot();const r=await api(batchPath,v);assert.equal(r.status,503);assert.equal(await snapshot(),before);}
   await control("control");
  });
  await t.test("CBA-TXN-004 overlapping concurrency converges",async()=>{
   const v=await fresh(["overlap-a","overlap-b"]);const results=await Promise.all([api(batchPath,v),api(batchPath,{...v,flickrGroupIds:["overlap-b","overlap-c"]})]);assert(results.every(r=>r.status===202));const st=await control("state");const intents=st.submission_intents.filter(x=>x.binding_id===v.photoBinding.fgaPhotoBindingId);assert.equal(intents.length,3);assert.equal(new Set(intents.map(x=>x.photo_id+":"+x.group_id)).size,3);
  });
  await t.test("CBA-TXN-005 batch processing makes no Flickr call",async()=>{
   const v=await fresh(["no-flickr-a","no-flickr-b"]);const before=(await control("state")).intake_probe_calls.length;assert.equal((await api(batchPath,v)).status,202);assert.equal((await control("state")).intake_probe_calls.length,before);
  });
  await t.test("CBA-HINT-001 many new heads emit one canonical hint",async()=>{
   const v=await fresh(["canonical-z","canonical-a","canonical-b"]);const before=(await control("state")).intake_probe_hints.length;await api(batchPath,v);const st=await control("state");const hints=st.intake_probe_hints.slice(before);assert.equal(hints.length,1);assert.equal(st.group_partitions.find(p=>p.partition_id===hints[0].partition_id).group_id,"canonical-a");
  });
  await t.test("CBA-HINT-002 work behind an active head emits none",async()=>{
   const v=await fresh(["behind-head"]);await api(batchPath,v);const other=await fresh(["behind-head"]);const before=(await control("state")).intake_probe_hints.length;await api(batchPath,other);assert.equal((await control("state")).intake_probe_hints.length,before);
  });
  await t.test("CBA-HINT-003 lost response retry is a durable no-op",async()=>{
   const v=await fresh(["retry-a","retry-b"]);await api(batchPath,v);const before=await snapshot();const again=await api(batchPath,v);assert.equal(again.status,202);assert(again.body.submissions.every(x=>!x.created));assert.equal(await snapshot(),before);
  });
  await t.test("CBA-HINT-004 mixed selection hints only a newly eligible partition",async()=>{
   const v=await fresh(["mixed-existing"]);await api(batchPath,v);const before=(await control("state")).intake_probe_hints.length;await api(batchPath,{...v,flickrGroupIds:["mixed-existing","mixed-new-z","mixed-new-a"]});const st=await control("state"),hints=st.intake_probe_hints.slice(before);assert.equal(hints.length,1);assert.equal(st.group_partitions.find(p=>p.partition_id===hints[0].partition_id).group_id,"mixed-new-a");
  });
  await t.test("CBA-HINT-005 lost hint leaves every partition claimable by sweep",async()=>{
   // Earlier cases leave legitimate unhinted work; isolate this case from the 64-partition sweep budget.
   await control("sweep");await control("sweep");
   const v=await fresh(["lost-a","lost-b","lost-c"]);await control("control",{loseHint:1});assert.equal((await api(batchPath,v)).status,202);let st=await control("state");const ids=st.submission_intents.filter(i=>i.binding_id===v.photoBinding.fgaPhotoBindingId).map(i=>i.partition_id);assert(ids.every(id=>st.group_partitions.find(p=>p.partition_id===id).lease_id===null));await control("control");await control("sweep");st=await control("state");assert(ids.every(id=>st.group_partitions.find(p=>p.partition_id===id).lease_id!==null));
  });
  await t.test("CBA-HINT-006 duplicate delivery cannot grant another lease",async()=>{
   const v=await fresh(["duplicate-hint"]);await api(batchPath,v);let st=await control("state");const partition=st.group_partitions.find(p=>p.group_id==="duplicate-hint");const object=await mf.getDurableObjectNamespace("COORD");const stub=object.get(object.idFromName(partition.partition_id));
   for(const revision of [String(partition.wake_revision),"0"]){const response=await stub.fetch("https://internal.invalid/wake",{method:"POST",body:JSON.stringify({partitionId:partition.partition_id,wakeRevision:revision})});assert.equal(response.status,200);}
   st=await control("state");assert.equal(st.group_partitions.find(p=>p.partition_id===partition.partition_id).lease_generation,partition.lease_generation);
  });
  await t.test("expired proof permits only fully idempotent retry",async()=>{
   const v=await fresh(["expiry-existing"]);await api(batchPath,v);await control("age",{bindingId:v.photoBinding.fgaPhotoBindingId});assert.equal((await api(batchPath,v)).status,202);const before=await snapshot();const r=await api(batchPath,{...v,flickrGroupIds:["expiry-existing","expiry-new"]});assert.equal(r.status,409);assert.equal(r.body.error.code,"existing_photo_reverification_required");assert.equal(await snapshot(),before);
  });
  await t.test("permanent block projection retains first evidence and never hints",async()=>{
   const v=await fresh(["protected-pair"]);const result=await api(batchPath,v);const id=result.body.submissions[0].fgaSubmissionIntentId;
   await db.batch([db.prepare("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) SELECT photo_id,group_id,'delivery_uncertain','synthetic-attempt' FROM submission_intents WHERE intent_id=?").bind(id),db.prepare("UPDATE submission_intents SET state='delivery_uncertain',terminal_at_us=created_at_us,state_version=state_version+1 WHERE intent_id=?").bind(id)]);
   const before=await snapshot();const retry=await api(batchPath,v);assert.equal(retry.status,202);const item=retry.body.submissions[0];assert.equal(item.created,false);assert.deepEqual(Object.keys(item).sort(),["created","fgaSubmissionIntentId","flickrGroupId","permanentSubmissionBlock","state"]);assert.equal(item.permanentSubmissionBlock.reasonCode,"delivery_uncertain");assert.match(item.permanentSubmissionBlock.createdAt,/\.\d{6}Z$/);assert.equal(await snapshot(),before);
  });
  await t.test("authentication precedes body use and rejects pending scope",async()=>{
   const v=await fresh(["auth-test"]);const before=await snapshot();assert.equal((await api(batchPath,v,null)).status,401);const pending=await api(batchPath,v,"2222-".repeat(12)+"2220");assert.equal(pending.status,403);assert.match(pending.headers.get("WWW-Authenticate"),/insufficient_scope/);assert.equal((await api(batchPath,v,CODE,{"Content-Type":"text/plain"})).status,415);assert.equal(await snapshot(),before);
  });
  await t.test("binding refresh preserves identity and increments revision",async()=>{
   const first=await api(bindingPath,{schemaVersion:1,flickrPhotoId:"refresh-photo",expectedLinkedFlickrRevision:1});const next=await api(bindingPath,{schemaVersion:1,flickrPhotoId:"refresh-photo",expectedLinkedFlickrRevision:1});assert.equal(first.status,201);assert.equal(next.status,200);assert.equal(next.body.fgaPhotoBindingId,first.body.fgaPhotoBindingId);assert.equal(next.body.verificationRevision,2);assert.match(next.body.verifiedAt,/\.\d{6}Z$/);
  });
  await t.test("wrong owner private missing malformed and mismatched IDs never create bindings",async()=>{
   for(const [mode,status] of [["wrong-owner",403],["private",422],["missing",422],["wrong-id",422],["malformed",503]]){await control("control",{mode});const before=(await control("state")).photo_bindings.length;const r=await api(bindingPath,{schemaVersion:1,flickrPhotoId:"invalid-"+mode,expectedLinkedFlickrRevision:1});assert.equal(r.status,status);assert.equal((await control("state")).photo_bindings.length,before);}
   await control("control");
  });
  await t.test("native generation mismatch prevents all upstream calls",async()=>{
   await grantApi.update(JSON.stringify({schemaVersion:1,generation:"wrong-generation",token:"synthetic-token",tokenSecret:"synthetic-token-secret"}),grantId);const before=await snapshot();assert.equal((await api(bindingPath,{schemaVersion:1,flickrPhotoId:"mismatch",expectedLinkedFlickrRevision:1})).status,503);assert.equal(await snapshot(),before);await grantApi.update(JSON.stringify({schemaVersion:1,generation:"generation-a",token:"synthetic-token",tokenSecret:"synthetic-token-secret"}),grantId);
  });
  await t.test("link race rolls back verified-photo authority",async()=>{
   await control("control",{mode:"link-race"});const before=(await control("state")).photo_bindings.length;const r=await api(bindingPath,{schemaVersion:1,flickrPhotoId:"raced",expectedLinkedFlickrRevision:1});assert.equal(r.status,409);assert.equal(r.body.error.code,"flickr_link_changed");assert.equal((await control("state")).photo_bindings.length,before);
  });
  assert.equal(external,0);
 }finally {await mf.dispose();}
});
