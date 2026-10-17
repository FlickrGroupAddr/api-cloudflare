import test from "node:test";
import assert from "node:assert/strict";
import {createHmac} from "node:crypto";
import {sqlStore} from "./sql_store.mjs";
import {credentialDigest} from "../src/installations.ts";
import {uploadAuthorizationRequest,FLICKR_UPLOAD_URL} from "../src/upload_authorization.ts";

const CODE=Array(13).fill("0000").join("-");
const APP={schemaVersion:1,consumerKey:"synthetic-app-key",consumerSecret:"app-secret-do-not-persist"};
const GRANT={schemaVersion:1,generation:"generation",token:"synthetic-token",tokenSecret:"token-secret-do-not-persist"};
const metadata=()=>({title:"Exact !*'() + % / café 雪",description:"line one\nline two",tags:"",is_public:"0",is_friend:"1",is_family:"0",safety_level:"1",content_type:"1",hidden:"2"});
const input=()=>({schemaVersion:1,flickrMetadata:metadata()});
const count=db=>db.raw.prepare("SELECT COUNT(*) n FROM upload_authorizations").get().n;
const enc=value=>encodeURIComponent(value).replace(/[!'()*]/g,char=>"%"+char.charCodeAt(0).toString(16).toUpperCase());

async function fixture(t){
 const db=sqlStore();t.after(()=>db.raw.close());
 const digest=await credentialDigest(CODE);
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('owner'),('foreign')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','owner','lrc_plugin','active',1,'version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
  db.prepare("INSERT INTO flickr_links VALUES('owner','owner-nsid',1,'linked')"),
  db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('owner','linked','available','write',1)"),
  db.prepare("INSERT INTO flickr_native_credentials VALUES('owner','generation',1,'owner-nsid','write',NULL)"),
  db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','owner',1,1)"),
 ]);
 const env={DB:db,FGA_UPLOAD_AUTHORIZATION_ENABLED:"1",
  FLICKR_APPLICATION:{get:async()=>JSON.stringify(APP)},FLICKR_GRANT:{get:async()=>JSON.stringify(GRANT)}};
 const auth={installationId:"install",credentialDigest:digest};
 return {db,env,auth,call:(value=input())=>uploadAuthorizationRequest(env,auth,value)};
}

function oauthFields(header){
 assert.match(header,/^OAuth /);
 const entries=[...header.slice(6).matchAll(/([a-z_]+)="([^"]*)"/g)].map(([,key,value])=>[key,decodeURIComponent(value)]);
 assert.equal(new Set(entries.map(([key])=>key)).size,entries.length);
 return Object.fromEntries(entries);
}

function independentSignature(body){
 const oauth=oauthFields(body.authorizationHeader);
 const pairs=[...Object.entries(body.flickrMetadata),...Object.entries(oauth).filter(([key])=>key!=="oauth_signature"&&key!=="realm")]
  .map(([key,value])=>[enc(key),enc(value)]).sort(([ak,av],[bk,bv])=>ak<bk?-1:ak>bk?1:av<bv?-1:av>bv?1:0);
 const normalized=pairs.map(([key,value])=>key+"="+value).join("&");
 const base="POST&"+enc(FLICKR_UPLOAD_URL)+"&"+enc(normalized);
 return createHmac("sha1",enc(APP.consumerSecret)+"&"+enc(GRANT.tokenSecret)).update(base).digest("base64");
}

test("actual upload envelope independently verifies RFC5849 HMAC over exact Unicode metadata",async t=>{
 const f=await fixture(t),response=await f.call();assert.equal(response.status,200);
 assert.equal(response.headers.get("Cache-Control"),"no-store");
 const body=await response.json();
 assert.deepEqual(Object.keys(body).sort(),["schemaVersion","fgaUploadAuthorizationId","issuedAt","uploadUrl","authorizationHeader","flickrMetadata"].sort());
 assert.equal(body.schemaVersion,1);assert.equal(body.uploadUrl,"https://up.flickr.com/services/upload/");
 assert.equal(body.uploadUrl,FLICKR_UPLOAD_URL);assert(Number.isFinite(Date.parse(body.issuedAt)));
 assert.deepEqual(body.flickrMetadata,{...metadata(),api_key:APP.consumerKey});
 const oauth=oauthFields(body.authorizationHeader);
 assert.equal(oauth.oauth_signature_method,"HMAC-SHA1");assert.equal(oauth.oauth_token,GRANT.token);
 assert.equal(oauth.oauth_consumer_key,APP.consumerKey);assert.match(oauth.oauth_nonce,/^[a-f0-9]{64}$/);
 assert.equal(oauth.oauth_signature,independentSignature(body));
 const tampered=structuredClone(body);tampered.flickrMetadata.title+="!";
 assert.notEqual(oauth.oauth_signature,independentSignature(tampered));
 const row=f.db.raw.prepare("SELECT * FROM upload_authorizations").get();
 assert.deepEqual(Object.keys(row).sort(),["authorization_id","installation_id","user_id","issued_at_us","photo_id","owner_nsid","link_revision"].sort());
 assert.equal(row.authorization_id,body.fgaUploadAuthorizationId);assert.equal(row.installation_id,"install");
 assert.equal(row.user_id,"owner");assert.equal(row.photo_id,null);assert.equal(row.owner_nsid,"owner-nsid");assert.equal(row.link_revision,1);
 const persisted=f.db.raw.prepare("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'").all()
  .map(({name})=>JSON.stringify(f.db.raw.prepare('SELECT * FROM "'+name+'"').all())).join("\n");
 for(const secret of [APP.consumerSecret,GRANT.tokenSecret,body.authorizationHeader,body.uploadUrl,metadata().title,metadata().description])assert(!persisted.includes(secret));
 assert(!JSON.stringify(body).includes(APP.consumerSecret));assert(!JSON.stringify(body).includes(GRANT.tokenSecret));
 assert(f.db.raw.prepare("SELECT COUNT(*) n FROM audit_events").get().n>=1);
});

test("strict metadata contract rejects injection, missing fields, unknown fields and numeric booleans",async t=>{
 const f=await fixture(t);
 const invalid=[null,[],{}, {schemaVersion:"1",flickrMetadata:metadata()}, {...input(),extra:true},
  {schemaVersion:1,flickrMetadata:[]}, {schemaVersion:1,flickrMetadata:null}];
 for(const key of ["is_public","is_friend","is_family","safety_level","content_type","hidden"]){
  const missing=input();delete missing.flickrMetadata[key];invalid.push(missing);
  const numeric=input();numeric.flickrMetadata[key]=1;invalid.push(numeric);
  const outOfRange=input();outOfRange.flickrMetadata[key]="9";invalid.push(outOfRange);
 }
 for(const key of ["photo","api_key","oauth_token","oauth_signature","unknown"]){const value=input();value.flickrMetadata[key]="injected";invalid.push(value);}
 for(const key of ["title","description","tags"]){const value=input();value.flickrMetadata[key]=false;invalid.push(value);}
 for(const value of invalid){const response=await f.call(value);assert.equal(response.status,400,JSON.stringify(value));assert.equal(response.headers.get("Cache-Control"),"no-store");}
 assert.equal(count(f.db),0);
});

test("disabled issuance and each paused gate return no bearer envelope or retry timer",async t=>{
 const f=await fixture(t);f.env.FGA_UPLOAD_AUTHORIZATION_ENABLED="0";
 assert.equal((await f.call()).status,503);assert.equal(count(f.db),0);
 f.env.FGA_UPLOAD_AUTHORIZATION_ENABLED="1";
 for(const scope of ["deployment","user"]){
  f.db.raw.prepare("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope=?").run(scope);
  const response=await f.call(),body=await response.json();
  assert.equal(response.status,503);assert.equal(body.error.code,"flickr_writes_paused");
  assert.equal(body.error.retryable,false);assert.equal(response.headers.get("Retry-After"),null);
  assert.equal(response.headers.get("Cache-Control"),"no-store");assert(!JSON.stringify(body).includes("OAuth "));
  assert.equal(count(f.db),0);
  f.db.raw.prepare("UPDATE flickr_write_gates SET enabled=1,revision=revision+1 WHERE scope=?").run(scope);
 }
});

test("current installation, generation and owner authority cannot be forged",async t=>{
 const f=await fixture(t);
 for(const auth of [{installationId:"foreign",credentialDigest:f.auth.credentialDigest},{...f.auth,credentialDigest:"a".repeat(64)}]){
  const response=await uploadAuthorizationRequest(f.env,auth,input());assert.notEqual(response.status,200);assert.equal(count(f.db),0);
 }
 f.env.FLICKR_GRANT.get=async()=>JSON.stringify({...GRANT,generation:"wrong-generation"});
 let response=await f.call();assert.notEqual(response.status,200);assert.equal(count(f.db),0);
 f.env.FLICKR_GRANT.get=async()=>JSON.stringify(GRANT);
 f.db.raw.exec("UPDATE flickr_native_credentials SET verified_owner_nsid='foreign-nsid'");
 response=await f.call();assert.notEqual(response.status,200);assert.equal(count(f.db),0);
});

const races={
 installationRevision:"UPDATE installations SET revision=revision+1",
 installationRevoked:"BEGIN;UPDATE installation_credential_versions SET state='revoked';UPDATE installations SET state='revoked',revision=revision+1,current_version_id=NULL,pending_version_id=NULL,revoked_at_utc=strftime('%Y-%m-%dT%H:%M:%f','now')||'000Z';COMMIT;",
 linkRevision:"UPDATE flickr_links SET link_revision=link_revision+1",
 generation:"UPDATE flickr_native_credentials SET active_generation='successor-generation'",
 owner:"UPDATE flickr_native_credentials SET verified_owner_nsid='foreign-nsid'",
 lifecycle:"UPDATE flickr_native_credentials SET operation_id='pending-operation'",
 connectionState:"UPDATE flickr_connection_state SET state='relink_required'",
 connectionOperation:"UPDATE flickr_connection_state SET operation_id='pending-operation'",
 connectionLocalState:"UPDATE flickr_connection_state SET local_state='replacement_pending'",
 deploymentPause:"UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'",
 userPause:"UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='user'",
 deploymentRevision:"UPDATE flickr_write_gates SET revision=revision+1 WHERE scope='deployment'",
};
for(const [name,mutation] of Object.entries(races))test("secret-resolution race fences "+name,async t=>{
 const f=await fixture(t);let changed=false;
 f.env.FLICKR_GRANT.get=async()=>{if(!changed){f.db.raw.exec(mutation);changed=true;}return JSON.stringify(GRANT);};
 const response=await f.call();assert(changed);assert.notEqual(response.status,200);assert.equal(count(f.db),0);
 assert(!JSON.stringify(await response.json()).includes("OAuth "));
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM transaction_guards").get().n,0);
});

for(const [name,mutation] of Object.entries(races))test("final issuance transaction fences "+name,async t=>{
 const f=await fixture(t),batch=f.db.batch;let changed=false;
 f.db.batch=async statements=>{if(!changed){f.db.raw.exec(mutation);changed=true;}return batch(statements);};
 const response=await f.call();assert(changed);assert.notEqual(response.status,200);assert.equal(count(f.db),0);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM audit_events WHERE outcome='succeeded'").get().n,0);
 assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM transaction_guards").get().n,0);
 assert(!JSON.stringify(await response.json()).includes("OAuth "));
});

test("every issuance transaction statement including audit rolls back without releasing an envelope",async t=>{
 const probe=await fixture(t);let size=0;
 const original=probe.db.batch;
 probe.db.batch=async statements=>{size=Math.max(size,statements.length);return original(statements);};
 assert.equal((await probe.call()).status,200);assert(size>=3);
 for(let index=0;index<size;index++){
  const f=await fixture(t),before=count(f.db),audit=f.db.raw.prepare("SELECT COUNT(*) n FROM audit_events WHERE outcome='succeeded'").get().n;
  f.db.fault=index;
  const response=await f.call();assert.notEqual(response.status,200,"batch index "+index);
  assert.equal(count(f.db),before);assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM audit_events WHERE outcome='succeeded'").get().n,audit);
  assert.equal(f.db.raw.prepare("SELECT COUNT(*) n FROM transaction_guards").get().n,0);
  assert(!JSON.stringify(await response.json()).includes("OAuth "));
 }
});

test("new envelopes use fresh nonces and correlation IDs without claiming provider single use or expiry",async t=>{
 const f=await fixture(t),a=await(await f.call()).json(),b=await(await f.call()).json();
 assert.notEqual(a.fgaUploadAuthorizationId,b.fgaUploadAuthorizationId);
 assert.notEqual(oauthFields(a.authorizationHeader).oauth_nonce,oauthFields(b.authorizationHeader).oauth_nonce);
 assert.equal(count(f.db),2);
 for(const value of [a,b])for(const key of ["expiresAt","expiresIn","singleUse","single_use","photo"])assert(!Object.hasOwn(value,key));
});

test("storage guards reject foreign ownership and retain correlation identity through ordinary SQL",async t=>{
 const f=await fixture(t),body=await(await f.call()).json();
 const insert=f.db.raw.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,photo_id) VALUES(?,'install',?,1,?)");
 assert.throws(()=>insert.run("foreign-record","foreign",null));
 assert.throws(()=>insert.run("prebound-record","owner","unverified-photo"));
 assert.throws(()=>f.db.raw.prepare("DELETE FROM upload_authorizations WHERE authorization_id=?").run(body.fgaUploadAuthorizationId));
 assert.throws(()=>f.db.raw.prepare("UPDATE upload_authorizations SET user_id='foreign' WHERE authorization_id=?").run(body.fgaUploadAuthorizationId));
 assert.throws(()=>f.db.raw.prepare("INSERT OR REPLACE INTO upload_authorizations SELECT * FROM upload_authorizations WHERE authorization_id=?").run(body.fgaUploadAuthorizationId));
 assert.equal(count(f.db),1);assert.equal(f.db.raw.prepare("SELECT photo_id FROM upload_authorizations").get().photo_id,null);
});

test("oversized metadata and internal failures never return or log bearer material",async t=>{
 const f=await fixture(t),oversized=input();oversized.flickrMetadata.description="x".repeat(16_384);
 let response=await f.call(oversized);assert.equal(response.status,413);assert.equal(count(f.db),0);
 const messages=[],old={log:console.log,warn:console.warn,error:console.error};
 for(const key of Object.keys(old))console[key]=(...args)=>messages.push(args.join(" "));
 f.db.batch=async()=>{throw Error(APP.consumerSecret+GRANT.tokenSecret+metadata().title);};
 try {response=await f.call();} finally {Object.assign(console,old);}
 assert.equal(response.status,503);assert.equal(response.headers.get("Cache-Control"),"no-store");
 const exposed=JSON.stringify(await response.json())+messages.join("\n");
 for(const secret of [APP.consumerSecret,GRANT.tokenSecret,metadata().title,"OAuth "])assert(!exposed.includes(secret));
 assert.equal(count(f.db),0);
});
