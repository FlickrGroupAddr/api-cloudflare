import test from "node:test";
import assert from "node:assert/strict";
import {sqlStore} from "./sql_store.mjs";
import {createWorker,ROUTES} from "../src/worker.ts";
import {credentialDigest,NOW_US_SQL} from "../src/installations.ts";

const CODE=Array(13).fill("0000").join("-"),PENDING=Array(12).fill("0000").concat("000G").join("-");
const PATH="/api/v001/upload-authorizations";
const value=()=>({schemaVersion:1,flickrMetadata:{title:"synthetic route metadata",is_public:"0",is_friend:"0",is_family:"0",safety_level:"1",content_type:"1",hidden:"2"}});
const count=db=>db.raw.prepare("SELECT COUNT(*) n FROM upload_authorizations").get().n;

async function fixture(t){
 const db=sqlStore();t.after(()=>db.raw.close());
 const digest=await credentialDigest(CODE);
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('owner')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','owner','lrc_plugin','active',1,'version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
  db.prepare("INSERT INTO flickr_links VALUES('owner','owner-nsid',1,'linked')"),
  db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('owner','linked','available','write',1)"),
  db.prepare("INSERT INTO flickr_native_credentials VALUES('owner','generation',1,'owner-nsid','write',NULL)"),
  db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','owner',1,1)"),
 ]);
 let providers=0;
 const worker=createWorker(async()=>{providers++;assert.fail("authorization issuance must not invoke Flickr transport");});
 const env={DB:db,FGA_UPLOAD_AUTHORIZATION_ENABLED:"1",FGA_INTAKE_ENABLED:"0",FGA_DISPATCH_ENABLED:"0",FGA_READ_ENABLED:"0",FGA_ADMIN_ENABLED:"0",
  FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:"synthetic-key",consumerSecret:"app-secret"})},
  FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:"generation",token:"synthetic-token",tokenSecret:"token-secret"})}};
 const call=({path=PATH,method="POST",body=JSON.stringify(value()),headers={},credential=CODE}={})=>worker.fetch(new Request("https://flickrgroupaddr.com"+path,{
  method,headers:{...(credential===null?{}:{Authorization:"Bearer "+credential}),"Content-Type":"application/json",...headers},...(method==="GET"||method==="HEAD"||body===null?{}:{body})}),env);
 return {db,env,call,providers:()=>providers};
}

async function denied(f,options,status){
 const response=await f.call(options);assert.equal(response.status,status,JSON.stringify(options));
 assert.equal(response.headers.get("Cache-Control"),"no-store");
 const body=await response.text();assert(!body.includes("OAuth "));assert(!body.includes("app-secret"));assert(!body.includes("token-secret"));
 assert.equal(count(f.db),0);assert.equal(f.providers(),0);
 return response;
}

test("registered upload route uses current installation bearer policy with intake/dispatch disabled",async t=>{
 const f=await fixture(t),route=ROUTES.find(item=>item.pathPattern===PATH);
 assert(route);assert.equal(route.method,"POST");assert.equal(route.auth,"installation_bearer");assert.equal(route.allowPending,false);
 const response=await f.call();assert.equal(response.status,200);assert.equal(response.headers.get("Cache-Control"),"no-store");
 const body=await response.json();assert.equal(body.uploadUrl,"https://up.flickr.com/services/upload/");assert.match(body.authorizationHeader,/^OAuth /);
 assert.equal(count(f.db),1);assert.equal(f.providers(),0);
});

test("disabled dedicated flag stops before credential lookup and leaves upload authority absent",async t=>{
 const f=await fixture(t);f.env.FGA_UPLOAD_AUTHORIZATION_ENABLED="0";
 f.db.prepare=()=>assert.fail("disabled upload route must not look up credentials");
 await denied(f,{credential:null},503);
});

test("missing, cookie-only, malformed, duplicate and revoked credentials cannot obtain an envelope",async t=>{
 const f=await fixture(t);
 const missing=await denied(f,{credential:null},401);assert.equal(missing.headers.get("WWW-Authenticate"),'Bearer realm="fga-api"');
 await denied(f,{credential:null,headers:{Cookie:"__Host-fga_admin=synthetic-browser-session"}},401);
 await denied(f,{credential:"not-a-plugin-code"},401);
 await denied(f,{credential:PENDING},401);
 await denied(f,{headers:{Authorization:"Bearer "+CODE+", Bearer "+CODE}},400);
 f.db.raw.exec("BEGIN;UPDATE installation_credential_versions SET state='revoked';UPDATE installations SET state='revoked',revision=revision+1,current_version_id=NULL,pending_version_id=NULL,revoked_at_utc=strftime('%Y-%m-%dT%H:%M:%f','now')||'000Z';COMMIT;");
 const revoked=await denied(f,{},401);assert.match(revoked.headers.get("WWW-Authenticate"),/invalid_token/);
});

test("pending rotation credential retains insufficient-scope boundary on the real Worker",async t=>{
 const f=await fixture(t),digest=await credentialDigest(PENDING);
 await f.db.batch([
  f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install',?,'pending_rotation',2,${NOW_US_SQL}+300000000)`).bind(digest),
  f.db.prepare("UPDATE installations SET pending_version_id='pending',revision=revision+1 WHERE installation_id='install'"),
 ]);
 const response=await denied(f,{credential:PENDING},403);assert.match(response.headers.get("WWW-Authenticate"),/insufficient_scope/);
});

test("normal authentication framing rejects query credentials and method/path bypass attempts",async t=>{
 const f=await fixture(t);
 await denied(f,{path:PATH+"?debug=1"},400);
 await denied(f,{path:PATH+"?access_token=synthetic",credential:null},400);
 const wrongMethod=await denied(f,{method:"GET",body:null},405);assert.equal(wrongMethod.headers.get("Allow"),"POST");
 await denied(f,{path:PATH+"/force"},404);
 await denied(f,{path:"/api/v001/upload%2fauthorizations"},400);
});

test("HTTP JSON/media/body limits fail before signing or durable correlation",async t=>{
 const f=await fixture(t);
 for(const media of ["text/plain","multipart/form-data; boundary=synthetic","application/x-www-form-urlencoded"])
  await denied(f,{headers:{"Content-Type":media}},415);
 await denied(f,{headers:{"Content-Encoding":"gzip"}},415);
 await denied(f,{body:"{"},400);
 await denied(f,{body:null},400);
 await denied(f,{headers:{"Content-Length":"invalid"}},413);
 await denied(f,{headers:{"Content-Length":"16385"}},413);
 const oversized=value();oversized.flickrMetadata.title="x".repeat(16384);
 await denied(f,{body:JSON.stringify(oversized)},413);
 await denied(f,{body:JSON.stringify({...value(),installationId:"foreign"})},400);
});

for(const scope of ["deployment","user"])test("HTTP paused "+scope+" gate preserves nonretryable repair response",async t=>{
 const f=await fixture(t);f.db.raw.prepare("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope=?").run(scope);
 const response=await f.call();assert.equal(response.status,503);assert.equal(response.headers.get("Retry-After"),null);assert.equal(response.headers.get("Cache-Control"),"no-store");
 const body=await response.json();assert.equal(body.error.code,"flickr_writes_paused");assert.equal(body.error.retryable,false);assert.equal(typeof body.error.correlationId,"string");
 assert.equal(count(f.db),0);assert.equal(f.providers(),0);
});
