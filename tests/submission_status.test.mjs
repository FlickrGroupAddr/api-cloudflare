import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,rmSync,realpathSync} from "node:fs";
import {tmpdir} from "node:os";
import {join,dirname} from "node:path";
import {sqlStore} from "./sql_store.mjs";
import {createWorker} from "../src/worker.ts";
import {digest} from "../src/browser_sessions.ts";
import {NOW_US_SQL} from "../src/installations.ts";
import {admitStatusRead,parseStatusQuery,statusTimestamp} from "../src/submission_status.ts";
const origin="https://flickrgroupaddr.com",code=Array(13).fill("0000").join("-");
function fixture(t){
 const base=realpathSync(tmpdir()),directory=mkdtempSync(join(base,"fga-status-")),db=sqlStore(join(directory,"db.sqlite"));
 t.after(()=>{db.raw.close();assert.equal(dirname(realpathSync(directory)),base);rmSync(directory,{recursive:true,force:true});});
 const token="C".repeat(42)+"A",csrf="A".repeat(43),now=Date.now()*1000;
 db.raw.exec("INSERT INTO fga_users VALUES('owner'),('foreign');INSERT INTO admin_principals VALUES('owner','https://accounts.google.com','owner-sub',1);");
 db.raw.prepare("INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id) VALUES('session',?,'owner',?,?,?,?,?,'correlation')").run(digest(token),csrf,now,now,now+86400000000,now);
 db.raw.exec("BEGIN;INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','owner','lrc_plugin','active',1,'version');");
 db.raw.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)").run(digest(code));db.raw.exec("COMMIT;");
 db.raw.exec("INSERT INTO flickr_links VALUES('owner','owner-nsid',1,'linked'),('foreign','foreign-nsid',1,'linked');INSERT INTO flickr_write_gates VALUES('user','owner',1,1),('deployment','*',1,1);");
 const seed=(id,state="queued",reason=null,user="owner",created=now)=>{
  const binding=id+"-binding",group=id+"@N00";
  db.raw.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES(?,?,?,?||'-nsid',1,1,'upload')").run(binding,user,id,user);
  db.raw.prepare("INSERT INTO group_partitions(partition_id,user_id,group_id) VALUES(?,?,?)").run(id,user,group);
  const active=["queued","attempting","retrying","throttled"].includes(state);
  db.raw.prepare("INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id,created_at_us,terminal_at_us,next_attempt_not_before_us) VALUES(?,?,?,?,?,?,1,?,'request',?,?,?)").run(id,binding,user,id,group,id,state,created,active?null:created,state==="retrying"?created+1000000:null);
  if(reason){db.raw.prepare("INSERT INTO submission_attempts(attempt_id,intent_id,ordinal,lease_id,lease_generation,deployment_revision,user_revision,link_revision) VALUES(?,?,1,'lease',1,1,1,1)").run(id+"-attempt",id);
   db.raw.prepare("INSERT INTO attempt_resolutions(attempt_id,outcome,reason,flickr_code) VALUES(?,?,?,?)").run(id+"-attempt",state,reason,reason==="flickr_code_6"?6:null);
  }
  if(state==="moderation_submitted"||state==="delivery_uncertain")db.raw.prepare("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES(?,?,?,?)").run(id,group,state==="moderation_submitted"?"flickr_code_6":"delivery_uncertain",id+"-attempt");
  return id;
 };
 seed("active");seed("moderated","moderation_submitted","flickr_code_6","owner",now+1000);seed("uncertain","delivery_uncertain","unresolved_dispatch","owner",now+2000);seed("other","queued",null,"foreign",now+3000);
 const worker=createWorker(async()=>assert.fail("Status must not contact any provider"));
 const env={DB:db,FGA_READ_ENABLED:"1",FGA_ADMIN_ENABLED:"1",FGA_INTAKE_ENABLED:"0",GOOGLE_OWNER_SUB:"owner-sub",GOOGLE_CLIENT_ID:"client",COORD:{get(){assert.fail("Status must not wake a worker");}}};
 const call=(path,admin=false,method="GET")=>worker.fetch(new Request(origin+path,{method,headers:admin?{Cookie:"__Host-fga_admin="+token}:{Authorization:"Bearer "+code}}),env);
 return {db,seed,call,env,worker,token,now};
}
function domain(db){return JSON.stringify(["submission_intents","submission_blocks","group_partitions","submission_attempts","attempt_dispatches","flickr_links","flickr_write_gates"].map(table=>db.raw.prepare("SELECT * FROM "+table+" ORDER BY 1").all()));}

test("status routes return one owner snapshot, authoritative blocks and no domain mutation",async t=>{
 const f=fixture(t),before=domain(f.db);let snapshots=0;const prepare=f.db.prepare;
 f.db.prepare=sql=>{if(sql.startsWith("SELECT json_object('authorized'"))snapshots++;return prepare(sql);};
 const response=await f.call("/api/v001/group-submission-intents?view=history");assert.equal(response.status,200);
 const page=await response.json();assert.equal(page.intents.length,3);assert.equal(page.summary.activeIntentCount,1);assert.equal(page.summary.attentionIntentCount,1);assert.equal(page.recommendedPollAfterSeconds,15);
 assert.deepEqual(page.summary.writeGates.map(x=>x.scope),["user","deployment"]);
 const mod=page.intents.find(x=>x.state==="moderation_submitted");assert.equal(mod.permanentSubmissionBlock.reasonCode,"moderation_submission_recorded");assert.equal(mod.attention,null);
 const uncertain=page.intents.find(x=>x.state==="delivery_uncertain");assert.equal(uncertain.attention.operatorAction,"inspect_flickr_no_fga_resubmit");assert.equal(uncertain.attention.fgaResubmissionAllowed,false);
 assert.equal(snapshots,1);assert.equal(domain(f.db),before);assert.equal(response.headers.get("Cache-Control"),"no-store");
 assert.equal((await f.call("/api/v001/group-submission-intents/other")).status,404);
 assert.equal((await f.call("/api/v001/group-submission-intents/missing")).status,404);
 const admin=await f.call("/api/v001/admin/group-submission-intents?view=attention",true);assert.equal(admin.status,200);assert.equal((await admin.json()).intents.length,1);
 assert.equal((await f.call("/api/v001/admin/group-submission-intents")).status,401);
 assert.equal((await f.call("/api/v001/group-submission-intents",true)).status,401);
});

test("descending keyset pagination uses exact timestamps and rejects malformed continuation",async t=>{
 const f=fixture(t),first=await(await f.call("/api/v001/group-submission-intents?view=history&page_size=1")).json();
 const p=new URLSearchParams({view:"history",page_size:"1",before_created_at:first.nextPage.beforeCreatedAt,before_intent_id:first.nextPage.beforeIntentId});
 const second=await(await f.call("/api/v001/group-submission-intents?"+p)).json();assert.equal(second.intents.length,1);assert.notEqual(first.intents[0].fgaSubmissionIntentId,second.intents[0].fgaSubmissionIntentId);
 for(const query of ["view=bogus","view=active&view=history","debug=1","page_size=101","photo_binding_id=","before_intent_id=one","before_created_at=2026-02-30T00:00:00.000000Z&before_intent_id=one"]){const response=await f.call("/api/v001/group-submission-intents?"+query);assert.equal(response.status,400,query);}
 assert.equal((await f.call("/api/v001/group-submission-intents?photo_binding_id=other-binding")).status,404);
 assert.equal((await f.call("/api/v001/group-submission-intents/active?view=history")).status,400);
 assert.equal(statusTimestamp("-1"),"1969-12-31T23:59:59.999999Z");
 assert.equal(parseStatusQuery(new URL(origin+"/?before_created_at=2026-09-13T00:00:00.123456Z&before_intent_id=id")).beforeUs,"1789257600123456");
});

test("gate pause changes holds and polling, preserves the queue and offers no bypass route",async t=>{
 const f=fixture(t);f.db.raw.exec("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'");
 const before=domain(f.db),response=await f.call("/api/v001/group-submission-intents/active"),body=await response.json();assert.equal(response.status,200);
 assert.equal(body.intent.state,"queued");assert.deepEqual(body.intent.queue.holds,["deployment_flickr_write_gate_paused"]);assert.equal(body.recommendedPollAfterSeconds,60);assert.equal(body.writeGates.length,1);assert(body.writeGates[0].pausedAt);
 for(const suffix of ["retry","retry-now","reopen","force","clear-block","cancel"])assert.equal((await f.call("/api/v001/group-submission-intents/active/"+suffix,false,"POST")).status,404);
 assert.equal((await f.call("/api/v001/group-submission-intents/active",false,"DELETE")).status,405);assert.equal(domain(f.db),before);
});

test("unknown outcome or block contradiction rejects the entire page instead of a prefix",async t=>{
 const f=fixture(t);f.seed("bad","needs_attention","not_in_the_public_vocabulary","owner",f.now+5000);
 const response=await f.call("/api/v001/group-submission-intents?view=history");assert.equal(response.status,500);const body=await response.json();assert.equal(body.error.code,"status_projection_invalid");assert(!Object.hasOwn(body,"intents"));
});

test("polling quota allows one burst, rejects overdraw atomically and admits after refill",async t=>{
 const f=fixture(t);let now=f.now;const clock={...f.db,prepare:sql=>f.db.prepare(sql.replaceAll(NOW_US_SQL,String(now)))};
 const auth={family:"installation",userId:"owner",subjectId:"installation",proof:digest(code)};
 for(let n=0;n<20;n++)await admitStatusRead(clock,auth);
 await assert.rejects(admitStatusRead(clock,auth),error=>error.status===429);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM status_read_events").get().n,20);
 now+=5_000_000;await admitStatusRead(clock,auth);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM status_read_events").get().n,21);
});

test("an active row with a permanent block is rejected rather than rendered eligible",async t=>{
 const f=fixture(t);f.db.raw.exec("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('active','active@N00','flickr_code_6','external-fixture')");
 const response=await f.call("/api/v001/group-submission-intents");assert.equal(response.status,500);assert(!Object.hasOwn(await response.json(),"intents"));
});

test("failed status bookkeeping cleanup cannot starve the durable work sweep",async t=>{
 const f=fixture(t),prepare=f.db.prepare;let wakes=0;
 f.db.prepare=sql=>{if(sql.startsWith("DELETE FROM status_read_events"))throw Error("synthetic maintenance failure");return prepare(sql);};
 f.env.FGA_ADMIN_ENABLED="0";f.env.FGA_INTAKE_ENABLED="1";
 f.env.COORD={idFromName:id=>id,get:()=>({fetch:async(_url,init)=>{assert.equal(JSON.parse(init.body).source,"sweep");wakes++;return new Response(null,{status:204});}})};
 await f.worker.scheduled({},f.env);assert.equal(wakes,1);
});
