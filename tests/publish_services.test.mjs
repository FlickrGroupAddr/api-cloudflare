import test from 'node:test';
import assert from 'node:assert/strict';
import {sqlStore} from './sql_store.mjs';
import {publishServiceRequest, PUBLISH_SERVICE_RELEASE_METADATA} from '../src/publish_services.ts';
const auth={installationId:'install',credentialDigest:'d'.repeat(64)};
const create=(body='{"schemaVersion":1}',headers={})=>new Request('https://example.test/api/v001/publish-services',{method:'POST',headers:{'Content-Type':'application/json',...headers},body});
const read=id=>new Request('https://example.test/api/v001/publish-services/'+id);
async function fixture(t){
 const db=sqlStore();t.after(()=>db.raw.close());
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('user'),('foreign')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version'),('second','user','lrc_plugin','active',1,'second-version'),('foreign','foreign','lrc_plugin','active',1,'foreign-version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1),('second-version','second',?,'current',1),('foreign-version','foreign',?,'current',1)").bind(auth.credentialDigest,'e'.repeat(64),'f'.repeat(64)),
  db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
  db.prepare("INSERT INTO flickr_native_credentials VALUES('user','gen',1,'owner','write',NULL)"),
  db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
 ]);
 const env={DB:db,FGA_PUBLISH_SERVICE_ENABLED:'1'};
 return {db,env,call:(req,id,a=auth)=>publishServiceRequest(env,a,req,id)};
}
test('create assigns distinct retained immutable identities; same user resumes with fresh link status',async t=>{
 const f=await fixture(t), first=await f.call(create());assert.equal(first.status,201);const a=await first.json();
 assert.equal(first.headers.get('Location'),'/api/v001/publish-services/'+a.fgaPublishServiceId);
 const b=await (await f.call(create())).json();assert.notEqual(a.fgaPublishServiceId,b.fgaPublishServiceId);
 assert.equal((await f.call(read(a.fgaPublishServiceId),a.fgaPublishServiceId,{installationId:'second',credentialDigest:'e'.repeat(64)})).status,200);
 for(const sql of ["UPDATE publish_service_identities SET service_revision=1","DELETE FROM publish_service_identities",`INSERT OR REPLACE INTO publish_service_identities SELECT * FROM publish_service_identities`]) assert.throws(()=>f.db.raw.exec(sql));
 f.db.raw.exec("UPDATE flickr_links SET link_revision=2; UPDATE flickr_native_credentials SET link_revision=2");
 const changed=await (await f.call(read(a.fgaPublishServiceId),a.fgaPublishServiceId)).json();assert.equal(changed.linkStatus,'link_changed');assert.equal(changed.linkedFlickrRevision,1);
 f.db.raw.exec("UPDATE flickr_links SET state='paused'");
 assert.equal((await (await f.call(read(a.fgaPublishServiceId),a.fgaPublishServiceId)).json()).linkStatus,'link_unavailable');
 assert.equal((await f.call(create())).status,409);
});
test('foreign and absent IDs are indistinguishable; stale credential refused',async t=>{
 const f=await fixture(t), a=await (await f.call(create())).json();
 for(const id of [a.fgaPublishServiceId,'00000000-0000-4000-8000-000000000000']) {
  const r=await f.call(read(id),id,{installationId:'foreign',credentialDigest:'f'.repeat(64)});assert.equal(r.status,404);assert.equal((await r.json()).error.code,'publish_service_not_found');
 }
 assert.equal((await f.call(create(),undefined,{...auth,credentialDigest:'0'.repeat(64)})).status,401);
});
test('closed bounded raw envelopes reject duplicates/extra/null/path/body/query',async t=>{
 const f=await fixture(t);
 for(const body of ['{"schemaVersion":1,"schemaVersion":1}','{"schemaVersion":1,"schema\\u0056ersion":1}','{"schemaVersion":null}','{"schemaVersion":1,"x":0}',' '.repeat(1024)+'{"schemaVersion":1}']) assert.equal((await f.call(create(body))).status,400);
 assert.equal((await f.call(create('{"schema\\u0056ersion":1.0}'))).status,201);
 assert.equal((await f.call(create('{}',{'Content-Type':'text/plain'}))).status,400);
 assert.equal((await f.call(new Request('https://example.test/api/v001/publish-services?x=1',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"schemaVersion":1}'}))).status,400);
 assert.equal((await f.call(read('bad'),'bad')).status,400);
});
test('pause/rotation immediately before committing INSERT cannot authorize old snapshot; batch failure rolls back',async t=>{
 const f=await fixture(t), original=f.db.batch.bind(f.db);
 f.db.batch=async statements=>{f.db.raw.exec("UPDATE flickr_native_credentials SET operation_id='transition'");return original(statements)};
 assert.equal((await f.call(create())).status,409);assert.equal(f.db.raw.prepare('SELECT count(*) n FROM publish_service_identities').get().n,0);
 f.db.batch=original;f.db.raw.exec('UPDATE flickr_native_credentials SET operation_id=NULL');f.db.fault=1;
 const r=await f.call(create());assert.equal(r.status,503);assert.equal(r.headers.get('Retry-After'),'5');assert.equal(f.db.raw.prepare('SELECT count(*) n FROM publish_service_identities').get().n,0);
});
test('disabled by default; no external operation dependencies',async t=>{
 const f=await fixture(t);delete f.env.FGA_PUBLISH_SERVICE_ENABLED;
 assert.equal((await f.call(create())).status,503);assert.equal(PUBLISH_SERVICE_RELEASE_METADATA.hostQualified,false);
});
test('pending version is not current; revocation before committing refuses create and read',async t=>{
 const f=await fixture(t), id=(await (await f.call(create())).json()).fgaPublishServiceId;
 await f.db.batch([
  f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install',?,'pending_rotation',2,9000000000000000)").bind('a'.repeat(64)),
  f.db.prepare("UPDATE installations SET pending_version_id='pending',revision=revision+1 WHERE installation_id='install'")
 ]);
 assert.equal((await f.call(create(),undefined,{...auth,credentialDigest:'a'.repeat(64)})).status,401);
 const original=f.db.batch.bind(f.db);let mutate=true;
 f.db.batch=async statements=>{
  if(mutate){mutate=false;await original([
   f.db.prepare("UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='install'"),
   f.db.prepare("UPDATE installation_credential_versions SET state='revoked' WHERE installation_id='install' AND state IN ('current','pending_rotation')")
  ])}return original(statements)
 };
 assert.equal((await f.call(create())).status,401);
 assert.equal((await f.call(read(id),id)).status,401);
 assert.equal(f.db.raw.prepare('SELECT count(*) n FROM publish_service_identities').get().n,1);
});
