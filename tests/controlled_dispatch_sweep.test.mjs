import test from "node:test";
import assert from "node:assert/strict";
import {sqlStore} from "./sql_store.mjs";
import {createWorker} from "../src/worker.ts";
import {consumePartition} from "../src/dispatch_worker.ts";
import {credentialDigest} from "../src/installations.ts";

const code=Array(13).fill("0000").join("-");
async function fixture(t){
 const db=sqlStore();t.after(()=>db.raw.close());
 const digest=await credentialDigest(code);
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('user')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
  db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
  db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
  db.prepare("INSERT INTO flickr_native_credentials VALUES('user','generation',1,'owner','write',NULL)"),
  db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',0,1),('user','user',0,1)"),
  db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES('binding','user','photo','owner',1,1,'existing_public')"),
 ]);
 const calls=[],wakes=[];
 const peer=async request=>{
  const params=request.method==="POST"?new URLSearchParams(await request.text()):new URL(request.url).searchParams;
  const method=params.get("method");calls.push(method);
  if(method==="flickr.photos.getAllContexts")return Response.json({stat:"ok",pool:[]});
  if(method==="flickr.groups.getInfo")return Response.json({stat:"ok",group:{id:"group",ispoolmoderated:"0"}});
  assert.equal(method,"flickr.groups.pools.add");assert.equal(request.method,"POST");
  assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,1);
  return Response.json({stat:"ok"});
 };
 const env={DB:db,FGA_READ_ENABLED:"0",FGA_ADMIN_ENABLED:"0",FGA_INTAKE_ENABLED:"1",FGA_DISPATCH_ENABLED:"0",
  FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:"synthetic-key",consumerSecret:"synthetic-secret"})},
  FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:"generation",token:"synthetic-token",tokenSecret:"synthetic-token-secret"})}};
 env.COORD={idFromName:id=>id,get:()=>({fetch:async(_url,init)=>{
  const hint=JSON.parse(init.body);wakes.push(hint);
  // Exercise the real normal consumer; this local namespace adapter does not
  // claim to prove platform alarm delivery or deployment propagation.
  await consumePartition(env,hint.partitionId,hint.wakeRevision,hint.source,peer);
  return new Response(null,{status:204});
 }})};
 const worker=createWorker(peer);
 const admit=()=>worker.fetch(new Request("https://flickrgroupaddr.com/api/v001/group-submission-batches",{
  method:"POST",headers:{Authorization:"Bearer "+code,"Content-Type":"application/json"},
  body:JSON.stringify({schemaVersion:2,photoBinding:{fgaPhotoBindingId:"binding",expectedVerificationRevision:1},flickrGroupIds:["group"]})}),env);
 return {db,worker,env,calls,wakes,admit};
}

test("one normal admitted pair dispatches through cron with intake closed and remains terminal",async t=>{
 const f=await fixture(t);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM submission_intents").get().n,0);
 const result=await f.admit();assert.equal(result.status,202);assert.equal((await result.json()).submissions.length,1);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM submission_intents WHERE active_fifo_member=1").get().n,1);
 assert.deepEqual(f.calls,[]);
 f.env.FGA_INTAKE_ENABLED="0";
 assert.equal((await f.admit()).status,503);
 // Fixture-only stand-in for separately tested owner-authenticated CAS resume.
 f.db.raw.exec("UPDATE flickr_write_gates SET enabled=1,revision=revision+1");
 f.env.FGA_DISPATCH_ENABLED="1";
 await f.worker.scheduled({},f.env);
 assert.deepEqual(f.calls,["flickr.photos.getAllContexts","flickr.groups.getInfo","flickr.groups.pools.add"]);
 assert.equal(f.db.raw.prepare("SELECT state FROM submission_intents").get().state,"added");
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,1);
 assert.equal(f.wakes.at(-1).source,"sweep");
 await f.worker.scheduled({},f.env);
 assert.equal(f.calls.length,3);assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM submission_intents").get().n,1);
});

test("closed intake plus disabled dispatch never wakes or posts",async t=>{
 const f=await fixture(t);assert.equal((await f.admit()).status,202);
 f.env.FGA_INTAKE_ENABLED="0";f.db.raw.exec("UPDATE flickr_write_gates SET enabled=1,revision=revision+1");
 const before=f.wakes.length;await f.worker.scheduled({},f.env);
 assert.equal(f.wakes.length,before);assert.deepEqual(f.calls,[]);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,0);
});

for(const scope of ["deployment","user"]){
 test("closed intake and paused "+scope+" gate prevent POST despite enabled dispatch",async t=>{
  const f=await fixture(t);assert.equal((await f.admit()).status,202);
  f.env.FGA_INTAKE_ENABLED="0";f.env.FGA_DISPATCH_ENABLED="1";
  f.db.raw.prepare("UPDATE flickr_write_gates SET enabled=1,revision=revision+1 WHERE scope<>?").run(scope);
  const before=f.wakes.length;await f.worker.scheduled({},f.env);
  assert.equal(f.wakes.length,before);assert.deepEqual(f.calls,[]);
  assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,0);
 });
}
