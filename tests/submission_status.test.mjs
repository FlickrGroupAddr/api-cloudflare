import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,rmSync,realpathSync,readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {tmpdir} from "node:os";
import {join,dirname} from "node:path";
import {sqlStore} from "./sql_store.mjs";
import {createWorker} from "../src/worker.ts";
import {digest} from "../src/browser_sessions.ts";
import {QUOTA_CLOCK_SQL,INTEGER_QUOTA_FIXTURE_SHA2_256} from "../src/quota_credit.ts";
import {admitStatusRead,cleanupStatusReads,readSubmissionStatus,statusFailure,parseStatusQuery,statusTimestamp} from "../src/submission_status.ts";
const origin="https://flickrgroupaddr.com",code=Array(13).fill("0000").join("-");
const integerFixture=readFileSync(new URL("./integer_quota_fixture.sql",import.meta.url),"utf8");
function fixture(t,prospective=true){
 const base=realpathSync(tmpdir()),directory=mkdtempSync(join(base,"fga-status-")),db=sqlStore(join(directory,"db.sqlite"));
 t.after(()=>{db.raw.close();assert.equal(dirname(realpathSync(directory)),base);rmSync(directory,{recursive:true,force:true});});
 // Explicit synthetic selection only: historical migrations remain unchanged.
 if(prospective){assert.equal(createHash("sha256").update(integerFixture).digest("hex"),INTEGER_QUOTA_FIXTURE_SHA2_256);db.raw.exec("DROP TABLE auth_source_buckets;DROP TABLE status_read_buckets;"+integerFixture);}
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

const auth={family:"installation",userId:"owner",subjectId:"installation",proof:digest(code)};
function scalar(db,sql){const statement=db.raw.prepare(sql);statement.setReadBigInts(true);return statement.get();}
function bucket(db,family=auth.family,subject=auth.subjectId){const statement=db.raw.prepare("SELECT rowid,credit_us,updated_at_us,typeof(credit_us) qt,typeof(updated_at_us) st FROM status_read_buckets WHERE family=? AND subject_id=?");statement.setReadBigInts(true);return statement.get(family,subject);}
function quotaSnapshot(db){return ["status_read_buckets","status_read_events","quota_credit_clocks","quota_credit_guards"].map(table=>{const statement=db.raw.prepare("SELECT rowid,* FROM "+table+" ORDER BY rowid");statement.setReadBigInts(true);return statement.all();});}
function clockStore(db,now){ // Exact synthetic source clock; never a runtime override.
 db.raw.function("status_test_clock",()=>now.value);
 return {...db,prepare:sql=>db.prepare(sql===QUOTA_CLOCK_SQL?"INSERT INTO quota_credit_clocks(batch_id,now_us) SELECT ?,status_test_clock()":sql)};
}
function seedBucket(db,q,s,family=auth.family,subject=auth.subjectId){db.raw.prepare("INSERT INTO status_read_buckets(family,subject_id,credit_us,updated_at_us) VALUES(?,?,?,?)").run(family,subject,q,s);}
function unavailable(error){assert.equal(error.status,503);assert.equal(error.message,"status_unavailable");const response=statusFailure(error);assert.equal(response.headers.get("Cache-Control"),"no-store");assert.equal(response.headers.get("Retry-After"),"5");return true;}
function exhausted(error){assert.equal(error.status,429);assert.equal(error.message,"status_rate_limited");const response=statusFailure(error);assert.equal(response.headers.get("Cache-Control"),"no-store");assert.equal(response.headers.get("Retry-After"),"5");return true;}

test("integer polling burst20, one-credit edge and exact refill roll back refused work",async t=>{
 const {db}=fixture(t),now={value:100n},clock=clockStore(db,now);
 for(let n=0;n<20;n++)await admitStatusRead(clock,auth);
 assert.equal(bucket(db).credit_us,0n);const before=quotaSnapshot(db);
 await assert.rejects(admitStatusRead(clock,auth),exhausted);assert.deepEqual(quotaSnapshot(db),before);
 now.value+=4_999_999n;await assert.rejects(admitStatusRead(clock,auth),exhausted);assert.deepEqual(quotaSnapshot(db),before);
 now.value++;await admitStatusRead(clock,auth);
 assert.equal(bucket(db).credit_us,0n);assert.equal(bucket(db).updated_at_us,now.value);
 assert.equal(scalar(db,"SELECT COUNT(*) n FROM status_read_events").n,21n);
 assert.equal(bucket(db).qt,"integer");assert.equal(bucket(db).st,"integer");
 assert.equal(scalar(db,"SELECT COUNT(*) n FROM quota_credit_clocks").n,0n);
 assert.equal(scalar(db,"SELECT COUNT(*) n FROM quota_credit_guards").n,0n);
});

test("tiny accrual, equal/backward clocks and saturation preserve exact credits and watermark",async t=>{
 const {db}=fixture(t),now={value:101n},clock=clockStore(db,now);seedBucket(db,100_000_000n,100n);
 await admitStatusRead(clock,auth);assert.equal(bucket(db).credit_us,95_000_000n);
 now.value=102n;await admitStatusRead(clock,auth);assert.equal(bucket(db).credit_us,90_000_001n);
 for(const value of [102n,101n,0n]){now.value=value;await admitStatusRead(clock,auth);}
 assert.equal(bucket(db).credit_us,75_000_001n);assert.equal(bucket(db).updated_at_us,102n);
 now.value=103n;await admitStatusRead(clock,auth);assert.equal(bucket(db).credit_us,70_000_002n);
 now.value=9223372036854775807n;await admitStatusRead(clock,auth);
 assert.equal(bucket(db).credit_us,95_000_000n);assert.equal(bucket(db).updated_at_us,now.value);assert.equal(bucket(db).qt,"integer");
 const identity=bucket(db).rowid;now.value=0n;await admitStatusRead(clock,auth);
 assert.equal(bucket(db).credit_us,90_000_000n);assert.equal(bucket(db).updated_at_us,9223372036854775807n);assert.equal(bucket(db).rowid,identity);
});

test("family and subject identities have independent buckets and one deployment window",async t=>{
 const {db}=fixture(t),now={value:0n},clock=clockStore(db,now);
 for(let n=0;n<20;n++)await admitStatusRead(clock,auth);
 await assert.rejects(admitStatusRead(clock,auth),exhausted);
 for(const identity of [{...auth,family:"admin"},{...auth,subjectId:"other"}])await admitStatusRead(clock,identity);
 assert.equal(bucket(db,"admin","installation").credit_us,95_000_000n);assert.equal(bucket(db,"installation","other").credit_us,95_000_000n);
 assert.equal(scalar(db,"SELECT COUNT(*) n FROM status_read_buckets").n,3n);
});

test("deployment600 window uses strict boundary and rolls back new/existing subject changes",async t=>{
 const {db}=fixture(t),now={value:600_000_000n},clock=clockStore(db,now);
 const insert=db.raw.prepare("INSERT INTO status_read_events VALUES(?,?)");
 for(let n=0;n<599;n++)insert.run("prior-"+n,1n);
 // Future-dated entries remain conservatively counted.
 insert.run("future",9223372036854775807n);seedBucket(db,1n,0n);
 for(const identity of [auth,{...auth,subjectId:"absent"}]){const before=quotaSnapshot(db);await assert.rejects(admitStatusRead(clock,identity),exhausted);assert.deepEqual(quotaSnapshot(db),before);}
 db.raw.exec("DELETE FROM status_read_events WHERE event_id='prior-0'");await admitStatusRead(clock,auth);
 assert.equal(bucket(db).credit_us,95_000_000n);const full=quotaSnapshot(db);
 await assert.rejects(admitStatusRead(clock,auth),exhausted);assert.deepEqual(quotaSnapshot(db),full);
 now.value=600_000_001n;await admitStatusRead(clock,auth);
 assert.equal(bucket(db).credit_us,90_000_001n);assert.equal(bucket(db).updated_at_us,now.value);
});

test("invalid clock and malformed persisted state fail unavailable before ordinary exhaustion",async t=>{
 const {db}=fixture(t),now={value:0n},clock=clockStore(db,now);
 for(const value of [-1n,1.5,"0",null]){now.value=value;const before=quotaSnapshot(db);await assert.rejects(admitStatusRead(clock,auth),unavailable);assert.deepEqual(quotaSnapshot(db),before);}
 now.value=0n;
 db.raw.exec("DROP TABLE status_read_buckets;CREATE TABLE status_read_buckets(family TEXT,subject_id TEXT,credit_us ANY,updated_at_us ANY,UNIQUE(family,subject_id)) STRICT");
 for(const [q,s] of [[1.5,0n],["5000000",0n],[null,0n],[-1n,0n],[100_000_001n,0n],[5_000_000n,-1n],[5_000_000n,0.5],[5_000_000n,"0"],[5_000_000n,null]]){
  db.raw.exec("DELETE FROM status_read_buckets");seedBucket(db,q,s);const before=quotaSnapshot(db);
  await assert.rejects(admitStatusRead(clock,auth),unavailable);assert.deepEqual(quotaSnapshot(db),before);
 }
});

test("native clock is sampled once, validated before CAST and reused for subject and event",async t=>{
 const {db}=fixture(t);let seconds=0,fractions=0;
 db.raw.function("unixepoch",(_now)=>{seconds++;return 123n;});db.raw.function("strftime",(_format,_now)=>{fractions++;return "03.007";});
 await admitStatusRead(db,auth);assert.equal(seconds,1);assert.equal(fractions,1);
 assert.equal(bucket(db).updated_at_us,123007000n);assert.equal(scalar(db,"SELECT created_at_us FROM status_read_events").created_at_us,123007000n);
 for(const [second,fraction] of [[1.5,"01.000"],["1","01.000"],[-1n,"00.000"],[253402300800n,"00.000"],[1n,"00.000\u0000junk"],[1n,null]]){
  db.raw.function("unixepoch",(_now)=>second);db.raw.function("strftime",(_format,_now)=>fraction);const before=quotaSnapshot(db);
  await assert.rejects(admitStatusRead(db,auth),unavailable);assert.deepEqual(quotaSnapshot(db),before);
 }
});

test("every later statement fault rolls back absent/existing charge, refill, watermark and event",async t=>{
 const {db}=fixture(t),now={value:9223372036854775807n},clock=clockStore(db,now);
 for(const initial of [null,[5_000_000n,0n]]){
  db.raw.exec("DELETE FROM status_read_buckets");if(initial)seedBucket(db,...initial);
  for(const fault of [4,5,6,7]){db.fault=fault;const before=quotaSnapshot(db);await assert.rejects(admitStatusRead(clock,auth),unavailable);assert.deepEqual(quotaSnapshot(db),before);}
 }
 db.fault=-1;
});

test("lost success acknowledgement charges once but authorizes no projection or retry/refund",async t=>{
 const {db}=fixture(t),now={value:0n},clock=clockStore(db,now);let batches=0,projections=0;
 const lost={...clock,prepare:sql=>{if(sql.startsWith("SELECT json_object('authorized'"))projections++;return clock.prepare(sql);},batch:async statements=>{batches++;await db.batch(statements);throw Error("lost acknowledgement");}};
 await assert.rejects(readSubmissionStatus(lost,auth,new URL(origin+"/")),unavailable);
 assert.equal(batches,1);assert.equal(projections,0);assert.equal(bucket(db).credit_us,95_000_000n);
 assert.equal(scalar(db,"SELECT COUNT(*) n FROM status_read_events").n,1n);
});

test("unrelated CHECK/schema/guard failures stay unavailable and historical schema is incompatible",async t=>{
 const {db}=fixture(t),clock=clockStore(db,{value:0n});
 db.raw.exec("CREATE TRIGGER unrelated_status_failure BEFORE INSERT ON status_read_events BEGIN SELECT RAISE(ABORT,'CHECK constraint failed: unrelated_invariant');END");
 const before=quotaSnapshot(db);await assert.rejects(admitStatusRead(clock,auth),unavailable);assert.deepEqual(quotaSnapshot(db),before);
 db.raw.exec("DROP TRIGGER unrelated_status_failure;INSERT INTO quota_credit_clocks VALUES('occupied',0);INSERT INTO quota_credit_guards VALUES('occupied','status',1,1)");
 // A malformed/missing guard table cannot be mistaken for quota exhaustion.
 db.raw.exec("DROP TABLE quota_credit_guards");await assert.rejects(admitStatusRead(clock,auth),unavailable);
 const legacy=fixture(t,false);await assert.rejects(admitStatusRead(legacy.db,auth),unavailable);
 assert.equal(scalar(legacy.db,"SELECT COUNT(*) n FROM status_read_buckets").n,0n);
 assert.equal(scalar(legacy.db,"SELECT COUNT(*) n FROM status_read_events").n,0n);
});

test("event cleanup retains buckets and boundary, is bounded and rolls back on failure",async t=>{
 const {db}=fixture(t),now={value:86_400_000_000n},clock=clockStore(db,now);seedBucket(db,0n,0n);
 const insert=db.raw.prepare("INSERT INTO status_read_events VALUES(?,?)"),boundary=now.value-600_000_000n;
 for(let n=0;n<1001;n++)insert.run("old-"+n,0n);
 insert.run("boundary",boundary);insert.run("future",now.value+1n);
 const before=quotaSnapshot(db);db.fault=2;await assert.rejects(cleanupStatusReads(clock));assert.deepEqual(quotaSnapshot(db),before);db.fault=-1;
 await cleanupStatusReads(clock);assert.equal(scalar(db,"SELECT COUNT(*) n FROM status_read_events").n,3n);assert.equal(bucket(db).updated_at_us,0n);assert.equal(bucket(db).credit_us,0n);
 await cleanupStatusReads(clock);assert.equal(scalar(db,"SELECT COUNT(*) n FROM status_read_events").n,2n);
 assert.equal(scalar(db,"SELECT COUNT(*) n FROM quota_credit_clocks").n,0n);assert.equal(scalar(db,"SELECT COUNT(*) n FROM quota_credit_guards").n,0n);
 now.value=-1n;const retained=quotaSnapshot(db);await assert.rejects(cleanupStatusReads(clock));assert.deepEqual(quotaSnapshot(db),retained);
});

test("an active row with a permanent block is rejected rather than rendered eligible",async t=>{
 const f=fixture(t);f.db.raw.exec("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('active','active@N00','flickr_code_6','external-fixture')");
 const response=await f.call("/api/v001/group-submission-intents");assert.equal(response.status,500);assert(!Object.hasOwn(await response.json(),"intents"));
});

test("failed status bookkeeping cleanup cannot starve the durable work sweep",async t=>{
 const f=fixture(t),prepare=f.db.prepare;let wakes=0;
 f.db.prepare=sql=>{if(sql.startsWith("DELETE FROM status_read_events"))throw Error("synthetic maintenance failure");return prepare(sql);};
 f.env.FGA_ADMIN_ENABLED="0";f.env.FGA_INTAKE_ENABLED="1";f.env.FGA_DISPATCH_ENABLED="1";
 f.env.COORD={idFromName:id=>id,get:()=>({fetch:async(_url,init)=>{assert.equal(JSON.parse(init.body).source,"sweep");wakes++;return new Response(null,{status:204});}})};
 await f.worker.scheduled({},f.env);assert.equal(wakes,1);
});
