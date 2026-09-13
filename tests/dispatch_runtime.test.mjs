import test from "node:test";
import assert from "node:assert/strict";
import {createHash,createHmac} from "node:crypto";
import OAuth from "oauth-1.0a";
import {execFileSync} from "node:child_process";
import {mkdtemp,readFile,writeFile,rm} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {Miniflare} from "miniflare";

// The actual optimized production Worker/class, native bindings and D1 engine.
// Outbound interception prevents any real Flickr request; it only supplies transport responses.
test("production coordinator dispatches signed requests once with D1 reservations and recovers durable work",async t=>{
  const directory=await mkdtemp(path.join(os.tmpdir(),"fga-production-dispatch-"));
  const config=path.join(directory,"wrangler.json");
  await writeFile(config,JSON.stringify({name:"production-dispatch-local",main:path.resolve("src/worker.ts"),compatibility_date:"2026-09-11",compatibility_flags:["nodejs_compat"],workers_dev:false}));
  execFileSync(process.execPath,["node_modules/wrangler/bin/wrangler.js","deploy","--dry-run","--minify","--config",config,"--outdir",path.join(directory,"bundle")],{env:{...process.env,WRANGLER_WRITE_LOGS:"false",WRANGLER_SEND_METRICS:"false",CI:"true"},stdio:"pipe"});
  const migrations=JSON.parse(execFileSync("uv",["run","--frozen","python","-c","import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))"],{encoding:"utf8"}));
  const calls=[],responses=new Map();
  let db;
  const mf=new Miniflare({modules:true,script:await readFile(path.join(directory,"bundle/worker.js"),"utf8"),compatibilityDate:"2026-07-30",compatibilityFlags:["nodejs_compat"],cf:false,telemetry:{enabled:false},d1Databases:["DB"],durableObjects:{COORD:{className:"PartitionWorker",useSQLite:true}},bindings:{FGA_DISPATCH_ENABLED:"1",FGA_ADMIN_ENABLED:"0",FGA_READ_ENABLED:"1",FGA_INTAKE_ENABLED:"1",FGA_MAX_GROUP_IDS_PER_BATCH:"60"},secretsStoreSecrets:{FLICKR_APPLICATION:{store_id:"local",secret_name:"application"},FLICKR_GRANT:{store_id:"local",secret_name:"grant"}},outboundService:async request=>{
    assert.equal(new URL(request.url).origin,"https://www.flickr.com");
    assert.match(request.headers.get("Authorization"),/^OAuth /);
    const params=request.method==="POST"?new URLSearchParams(await request.text()):new URL(request.url).searchParams;
    const method=params.get("method"),group=params.get("group_id"),photo=params.get("photo_id");
    const authorization=Object.fromEntries(request.headers.get("Authorization").slice(6).split(/,\s*/).map(field=>{
      const match=/^([a-z_]+)="([^"]*)"$/.exec(field);assert(match);return [match[1],decodeURIComponent(match[2])];
    }));
    const verifier=new OAuth({consumer:{key:"synthetic-key",secret:"synthetic-secret"},signature_method:"HMAC-SHA1",
      hash_function:(base,key)=>createHmac("sha1",key).update(base).digest("base64")});
    verifier.getNonce=()=>authorization.oauth_nonce;
    verifier.getTimeStamp=()=>Number(authorization.oauth_timestamp);
    const verified=verifier.authorize({url:request.url,method:request.method,...(request.method==="POST"?{data:Object.fromEntries(params)}:{})},
      {key:"synthetic-token",secret:"synthetic-token-secret"});
    assert.equal(authorization.oauth_signature,verified.oauth_signature,"OAuth signature covers the actual wire request");

    calls.push({method,group,photo});
    if(method==="flickr.photos.getAllContexts")return Response.json({stat:"ok",pool:[]});
    if(method==="flickr.groups.getInfo")return Response.json({stat:"ok",group:{id:group,ispoolmoderated:"0"}});
    assert.equal(method,"flickr.groups.pools.add");assert.equal(request.method,"POST");
    const marker=await db.prepare("SELECT COUNT(*) n FROM attempt_dispatches d JOIN submission_attempts a ON a.attempt_id=d.attempt_id JOIN submission_intents i ON i.intent_id=a.intent_id WHERE i.photo_id=? AND i.group_id=?").bind(photo,group).first();
    assert.equal(marker.n,1);
    const code=responses.get(group)??6;
    return Response.json(code==="ok"?{stat:"ok"}:{stat:"fail",code});
  }});
  try{
    db=await mf.getD1Database("DB");
    for(const statements of migrations)await db.batch(statements.map(sql=>db.prepare(sql)));
    await(await mf.getSecretsStoreSecretAPI("FLICKR_APPLICATION"))().create(JSON.stringify({schemaVersion:1,consumerKey:"synthetic-key",consumerSecret:"synthetic-secret"}));
    await(await mf.getSecretsStoreSecretAPI("FLICKR_GRANT"))().create(JSON.stringify({schemaVersion:1,generation:"generation",token:"synthetic-token",tokenSecret:"synthetic-token-secret"}));
    await db.batch([
      db.prepare("INSERT INTO fga_users VALUES('user')"),
      db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
      db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
      db.prepare("INSERT INTO flickr_native_credentials VALUES('user','generation',1,'owner','write',NULL)"),
      db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)"),
    ]);
    const statusCode=Array(13).fill("0000").join("-");
    await db.batch([
      db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('status-installation','user','lrc_plugin','active',1,'status-version')"),
      db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('status-version','status-installation',?,'current',1)").bind(createHash("sha256").update(statusCode).digest("hex")),
    ]);
    const namespace=await mf.getDurableObjectNamespace("COORD");
    const enqueue=async(name,code=6)=>{
      const group=name+"@N00";responses.set(group,code);
      await db.batch([
        db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES(?,'user',?,'owner',1,1,'upload')").bind(name,name),
        db.prepare("INSERT INTO group_partitions(partition_id,user_id,group_id) VALUES(?,'user',?)").bind(name,group),
        db.prepare("INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id) VALUES(?,?,'user',?,?,?,1,'queued',?)").bind(name,name,name,group,name,name),
      ]);
      return namespace.get(namespace.idFromName(name));
    };
    const wake=async(stub,name,source="admission")=>{
      const revision=(await db.prepare("SELECT CAST(wake_revision AS TEXT) revision FROM group_partitions WHERE partition_id=?").bind(name).first()).revision;
      assert.equal((await stub.fetch("https://internal.invalid/wake",{method:"POST",body:JSON.stringify({partitionId:name,wakeRevision:revision,source})})).status,204);
    };
    const settled=async(name)=>{
      for(let n=0;n<100;n++){
        const row=await db.prepare("SELECT state FROM submission_intents WHERE intent_id=?").bind(name).first();
        if(!["queued","attempting"].includes(row.state))return row.state;
        await new Promise(resolve=>setTimeout(resolve,30));
      }
      throw Error("production dispatcher did not settle: "+name);
    };
    await t.test("hint path: native signed moderated result is permanently suppressed",async()=>{
      const stub=await enqueue("moderated");await wake(stub,"moderated");assert.equal(await settled("moderated"),"moderation_submitted");
      assert.equal((await db.prepare("SELECT first_reason FROM submission_blocks WHERE photo_id='moderated'").first()).first_reason,"flickr_code_6");
      await wake(stub,"moderated");await stub.fetch("https://internal.invalid/unknown");
      assert.equal(calls.filter(x=>x.method==="flickr.groups.pools.add"&&x.photo==="moderated").length,1);
    });
    await t.test("sweep path: temporary result retains FIFO with bounded due time",async()=>{
      const stub=await enqueue("temporary",105);await wake(stub,"temporary","sweep");assert.equal(await settled("temporary"),"retrying");
      const row=await db.prepare("SELECT next_attempt_not_before_us due,terminal_at_us terminal FROM submission_intents WHERE intent_id='temporary'").first();
      assert(row.due>Date.now()*1000);assert.equal(row.terminal,null);
      // Isolate later scenarios from this verified retry's real advisory alarm.
      const later=Date.now()*1000+600_000_000;
      await db.batch([db.prepare("UPDATE submission_intents SET next_attempt_not_before_us=? WHERE intent_id='temporary'").bind(later),
        db.prepare("UPDATE group_partitions SET next_work_not_before_us=? WHERE partition_id='temporary'").bind(later)]);
      assert.equal((await db.prepare("SELECT COUNT(*) n FROM submission_blocks WHERE photo_id='temporary'").first()).n,0);
    });
    await t.test("known permanent request errors become needs attention without an uncertainty block",async()=>{
      const stub=await enqueue("invalidphoto",1);await wake(stub,"invalidphoto");assert.equal(await settled("invalidphoto"),"needs_attention");
      assert.equal((await db.prepare("SELECT COUNT(*) n FROM submission_blocks WHERE photo_id='invalidphoto'").first()).n,0);
    });
    await t.test("rate allocation is a shared three-operation charge with one final accounting record",async()=>{
      const row=await db.prepare("SELECT reserved_slots FROM flickr_rate_window").first();assert.equal(row.reserved_slots,9);
      let rows=(await db.prepare("SELECT released,consumed_slots FROM flickr_rate_reservations").all()).results;
      for(let n=0;n<50&&rows.some(x=>!x.released);n++){await new Promise(resolve=>setTimeout(resolve,20));rows=(await db.prepare("SELECT released,consumed_slots FROM flickr_rate_reservations").all()).results;}
      assert.equal(rows.length,3);assert(rows.every(x=>x.consumed_slots===3&&x.released===1));
    });
    await t.test("unknown result blocks exact pair and pauses the deployment atomically",async()=>{
      const stub=await enqueue("unknown",9001);await wake(stub,"unknown");assert.equal(await settled("unknown"),"delivery_uncertain");
      assert.equal((await db.prepare("SELECT enabled FROM flickr_write_gates WHERE scope='deployment'").first()).enabled,0);
      assert.equal((await db.prepare("SELECT COUNT(*) n FROM flickr_write_gate_events WHERE flickr_code=9001").first()).n,1);
    });
    await t.test("concurrent partitions cannot split or overdraw the remaining shared reservation budget",async()=>{
      await db.batch([db.prepare("UPDATE flickr_write_gates SET enabled=1,revision=revision+1 WHERE scope='deployment'"),
        db.prepare("UPDATE flickr_rate_window SET reserved_slots=54")]);
      const names=["quota-a","quota-b","quota-c"],stubs=[];
      for(const name of names)stubs.push(await enqueue(name));
      await Promise.all(stubs.map((stub,i)=>wake(stub,names[i])));
      const states=await Promise.all(names.map(settled));
      assert.equal(states.filter(x=>x==="moderation_submitted").length,2);
      assert.equal(states.filter(x=>x==="retrying").length,1);
      const rejected=names[states.indexOf("retrying")];
      assert.equal(calls.filter(x=>x.photo===rejected).length,0);
      assert.equal((await db.prepare("SELECT reserved_slots FROM flickr_rate_window").first()).reserved_slots,60);
    });
    await t.test("group limits retain a throttled head and exact durable partition due time",async()=>{
      await db.prepare("UPDATE flickr_rate_window SET reserved_slots=0").run();
      const stub=await enqueue("grouplimit",5);await wake(stub,"grouplimit");assert.equal(await settled("grouplimit"),"throttled");
      const row=await db.prepare("SELECT p.next_work_not_before_us due,p.next_probe_not_before_us probe,i.active_fifo_member active FROM group_partitions p JOIN submission_intents i ON i.partition_id=p.partition_id WHERE p.partition_id='grouplimit'").first();
      assert.equal(row.due,row.probe);assert(row.due>Date.now()*1000);assert.equal(row.active,1);
    });
    await t.test("definitive grant rejection terminalizes the intent and schedules only matching native retirement",async()=>{
      const stub=await enqueue("rejectedgrant",98);await wake(stub,"rejectedgrant");assert.equal(await settled("rejectedgrant"),"needs_attention");
      let connection;
      for(let n=0;n<100;n++){connection=await db.prepare("SELECT state,operation_id FROM flickr_connection_state WHERE user_id='user'").first();if(connection.state==="relink_required")break;await new Promise(resolve=>setTimeout(resolve,30));}
      assert.equal(connection.state,"relink_required");assert(connection.operation_id);
      assert.equal((await db.prepare("SELECT source_component FROM audit_events WHERE action='flickr.grant_rejected'").first()).source_component,"fga_group_submission_worker");
      assert.equal((await db.prepare("SELECT enabled FROM flickr_write_gates WHERE scope='user'").first()).enabled,0);
      assert.equal((await db.prepare("SELECT enabled FROM flickr_write_gates WHERE scope='deployment'").first()).enabled,1);
      assert.equal((await db.prepare("SELECT retiring_generation FROM flickr_lifecycle_operations WHERE operation_id=?").bind(connection.operation_id).first()).retiring_generation,"generation");
      assert.equal((await db.prepare("SELECT COUNT(*) n FROM submission_blocks WHERE photo_id='rejectedgrant'").first()).n,0);
    });
    await t.test("native status reads expose protected outcomes without another provider operation",async()=>{
      const before=calls.length;
      const response=await mf.dispatchFetch("https://flickrgroupaddr.com/api/v001/group-submission-intents?view=history",{headers:{Authorization:"Bearer "+statusCode}});
      assert.equal(response.status,200);const page=await response.json();
      const protectedIntent=page.intents.find(x=>x.flickrPhotoId==="moderated");
      assert.equal(protectedIntent.permanentSubmissionBlock.reasonCode,"moderation_submission_recorded");
      assert.equal(page.intents.find(x=>x.flickrPhotoId==="unknown").attention.fgaResubmissionAllowed,false);
      assert.equal(page.summary.writeGates[0].state,"paused");assert.equal(calls.length,before);
    });
    assert.equal((await mf.dispatchFetch("https://flickrgroupaddr.com/api/v001/force-retry",{method:"POST"})).status,404);
    if(process.env.FGA_DISPATCH_REPORT){
      const reportPath=path.resolve(process.env.FGA_DISPATCH_REPORT);
      assert(reportPath.startsWith(path.resolve(".coordination-runs")+path.sep));
      let sqliteVersion=null,versionObservation="not_exposed";
      try{sqliteVersion=(await db.prepare("SELECT sqlite_version() version").first()).version;versionObservation="reported_by_engine";}
      catch(error){if(!String(error).includes("not authorized to use function: sqlite_version"))throw error;versionObservation="D1_API_denies_sqlite_version";}
      const miniflareVersion=JSON.parse(await readFile("node_modules/miniflare/package.json","utf8")).version;
      const artifact=await readFile(path.join(directory,"bundle/worker.js"));
      await writeFile(reportPath,JSON.stringify({schemaVersion:1,scope:"local compiled production artifact provenance",productionConformance:false,
        workerArtifactSha2_256:createHash("sha256").update(artifact).digest("hex"),databaseEngine:{provider:"local-workerd-d1",version:sqliteVersion,versionObservation,miniflareVersion},
        requestedCompatibilityDate:"2026-09-11",emulatedCompatibilityDate:"2026-07-30",nodeVersion:process.versions.node,
        liveFlickrCalls:0,outboundBoundary:"controlled Miniflare outbound service",dispatchEnabledInFixture:true},null,2)+"\n");
    }

  }finally{await mf.dispose();await rm(directory,{recursive:true,force:true});}
});
