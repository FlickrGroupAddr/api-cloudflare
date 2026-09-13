import {FGA_FAIL_POLITE_CONTRACT_SHA2_256} from "../src/release_contract.ts";
import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,rmSync,realpathSync} from "node:fs";
import {tmpdir} from "node:os";
import {join,dirname} from "node:path";
import {sqlStore} from "./sql_store.mjs";
import {resumeWriteGate} from "../src/native_lifecycle.ts";

test("protocol repair requires a different validated artifact and still verifies the actual grant",async t=>{
 const base=realpathSync(tmpdir()),directory=mkdtempSync(join(base,"fga-protocol-repair-")),db=sqlStore(join(directory,"db.sqlite"));
 t.after(()=>{db.raw.close();assert.equal(dirname(realpathSync(directory)),base);rmSync(directory,{recursive:true,force:true});});
 db.raw.exec("INSERT INTO fga_users VALUES('owner');INSERT INTO flickr_links VALUES('owner','nsid',1,'linked');INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('owner','linked','available','write',1);INSERT INTO flickr_native_credentials VALUES('owner','generation',1,'nsid','write',NULL);INSERT INTO flickr_write_gates VALUES('user','owner',1,1),('deployment','*',1,1);");
 db.raw.prepare("INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason,flickr_code,artifact_sha2_256) VALUES('trip','deployment','*',2,'unknown_code',9001,?)").run("a".repeat(64));
 db.raw.exec("UPDATE flickr_write_gates SET enabled=0,revision=2 WHERE scope='deployment'");
 const secrets={FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:"synthetic",consumerSecret:"synthetic-secret"})},FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:"generation",token:"synthetic-token",tokenSecret:"synthetic-token-secret"})}};
 let calls=0;
 const fetcher=async request=>{calls++;assert.equal(new URL(request.url).searchParams.get("method"),"flickr.auth.oauth.checkToken");return Response.json({stat:"ok",oauth:{token:{_content:"synthetic-token"},perms:{_content:"write"},user:{nsid:"nsid"}}});};
 for(const artifact of [undefined,"a".repeat(64),"b".repeat(64)])await assert.rejects(resumeWriteGate(db,"owner","deployment",2,secrets,fetcher,artifact),error=>error.message==="deployment_conformance_required");
 assert.equal(calls,0);assert.equal(db.raw.prepare("SELECT enabled FROM flickr_write_gates WHERE scope='deployment'").get().enabled,0);
 // Synthetic fixture receipt; production receipts may only follow the full release verifier.
 db.raw.prepare("INSERT INTO deployment_conformance(artifact_sha2_256,contract_sha2_256,evidence_sha2_256) VALUES(?,?,?)").run("b".repeat(64),FGA_FAIL_POLITE_CONTRACT_SHA2_256,"d".repeat(64));
 const view=await resumeWriteGate(db,"owner","deployment",2,secrets,fetcher,"b".repeat(64));
 assert.equal(calls,1);assert.equal(view.deploymentWriteGate.state,"enabled");
 assert.throws(()=>db.raw.exec("DELETE FROM deployment_conformance"));
});
