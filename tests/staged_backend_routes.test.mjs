import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createWorker} from '../src/worker.ts';
import {credentialDigest} from '../src/installations.ts';
import {sqlStore} from './sql_store.mjs';

const CODE=Array(13).fill('0000').join('-');
const SERVICE='/api/v001/publish-services';
const CANDIDATES='/api/v001/upload-authorizations/authorization/ambiguity-candidates';
async function fixture(t){
 const db=sqlStore();t.after(()=>db.raw.close());
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('user')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(await credentialDigest(CODE)),
  db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
  db.prepare("INSERT INTO flickr_native_credentials VALUES('user','gen',1,'owner','write',NULL)"),
  db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
  db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('authorization','install','user',1700000000000000,'owner',1)"),
 ]);
 let calls=0;
 const worker=createWorker(async request=>{
  calls++;assert.equal(new URL(request.url).searchParams.get('method'),'flickr.people.getPhotos');
  return Response.json({stat:'ok',photos:{page:1,perpage:10,pages:0,total:'0',photo:[]}});
 });
 const env={DB:db,FGA_PUBLISH_SERVICE_ENABLED:'1',FGA_UPLOAD_CANDIDATES_ENABLED:'1',
  FGA_INTAKE_ENABLED:'0',FGA_DISPATCH_ENABLED:'0',FGA_READ_ENABLED:'0',
  FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'app',consumerSecret:'synthetic'})},
  FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'gen',token:'synthetic',tokenSecret:'synthetic'})}};
 const call=(path,options={})=>{
  const {credential=CODE,headers={},...rest}=options;
  return worker.fetch(new Request('https://example.test'+path,{
   ...rest,headers:{...(credential===null?{}:{Authorization:'Bearer '+credential}),...headers},
  }),env);
 };
 return {db,env,call,calls:()=>calls};
}
const create={method:'POST',headers:{'Content-Type':'application/json'},body:'{"schemaVersion":1}'};

test('new feature flags refuse before auth/store/provider and preserve contract headers',async t=>{
 const f=await fixture(t);delete f.env.FGA_PUBLISH_SERVICE_ENABLED;delete f.env.FGA_UPLOAD_CANDIDATES_ENABLED;
 f.db.prepare=()=>assert.fail('disabled storage access');
 for(const path of [SERVICE,SERVICE+'/00000000-0000-4000-8000-000000000000']){
  const response=await f.call(path,{...(path===SERVICE?create:{}),credential:null});
  assert.equal(response.status,503);assert.equal(response.headers.get('Retry-After'),'5');
 }
 const candidate=await f.call(CANDIDATES+'?page=1&page_size=10',{credential:null});
 assert.equal(candidate.status,503);assert.equal(candidate.headers.get('Cache-Control'),'private, no-store');
 assert.equal(f.calls(),0);
});

test('new routes preserve missing auth, method and GET envelope rules',async t=>{
 const f=await fixture(t);
 for(const [path,options,status] of [
  [SERVICE,{...create,credential:null},401],
  [CANDIDATES+'?page=1&page_size=10',{credential:null},401],
  [CANDIDATES+'?page=1&page_size=10',{headers:{'Content-Length':'1'}},400],
  [CANDIDATES,{method:'POST'},405],
  [SERVICE+'/00000000-0000-4000-8000-000000000000?extra=1',{},400],
 ]){
  const response=await f.call(path,options);assert.equal(response.status,status);
  if(path.startsWith(CANDIDATES))assert.equal(response.headers.get('Cache-Control'),'private, no-store');
  if(status===401){assert.equal(await response.text(),'');assert.equal(response.headers.get('WWW-Authenticate'),'Bearer realm="fga-api"');}
  if(status===405)assert.equal(response.headers.get('Allow'),'GET');
 }
 assert.equal(f.calls(),0);
});

test('service raw body parser remains active through real Worker dispatch',async t=>{
 const f=await fixture(t);
 for(const body of ['{"schemaVersion":1,"schemaVersion":1}','{"schemaVersion":1,"extra":0}',' '.repeat(1024)+'{"schemaVersion":1}']){
  assert.equal((await f.call(SERVICE,{...create,body})).status,400);
 }
 assert.equal(f.db.raw.prepare('SELECT count(*) n FROM publish_service_identities').get().n,0);
 assert.equal(f.calls(),0);
});

test('service identity create/read is wired without enabling upload or Flickr writes',async t=>{
 const f=await fixture(t),first=await f.call(SERVICE,create);assert.equal(first.status,201);
 const a=await first.json(),second=await f.call(SERVICE,create),b=await second.json();
 assert.notEqual(a.fgaPublishServiceId,b.fgaPublishServiceId);
 assert.equal(first.headers.get('Location'),SERVICE+'/'+a.fgaPublishServiceId);
 const read=await f.call(SERVICE+'/'+a.fgaPublishServiceId);assert.equal(read.status,200);
 assert.deepEqual(await read.json(),a);assert.equal(f.calls(),0);
 assert.equal(f.db.raw.prepare('SELECT count(*) n FROM photo_bindings').get().n,0);
});

test('candidate page is a private advisory GET through real Worker',async t=>{
 const f=await fixture(t),response=await f.call(CANDIDATES+'?page=1&page_size=10');
 assert.equal(response.status,200);assert.equal(response.headers.get('Cache-Control'),'private, no-store');
 const body=await response.json();assert.deepEqual(body.photos,[]);assert.equal(body.fgaUploadAuthorizationId,'authorization');
 assert.equal(f.calls(),1);assert.equal(f.db.raw.prepare('SELECT count(*) n FROM photo_bindings').get().n,0);
 assert.equal((await f.call(CANDIDATES+'?page=1&page=1&page_size=10')).status,400);
 assert.equal(f.calls(),1);
});

test('service auth-store failure includes required retry guidance',async t=>{
 const f=await fixture(t);f.db.prepare=()=>{throw new Error('synthetic_store_failure')};
 const response=await f.call(SERVICE,create);assert.equal(response.status,503);
 assert.equal(response.headers.get('Retry-After'),'5');assert.equal(f.calls(),0);
});

test('generated service paths and errors match closed accepted wire',()=>{
 const api=JSON.parse(readFileSync('generated/openapi.json','utf8'));
 for(const route of [api.paths[SERVICE].post,api.paths[SERVICE+'/{fgaPublishServiceId}'].get]){
  for(const status of ['412','413','415','422','428','500'])assert.equal(route.responses[status],undefined);
  for(const [status,code,retryable] of [[400,'invalid_request',false],[401,'invalid_token',false],[403,'insufficient_scope',false],
   [404,'publish_service_not_found',false],[409,'flickr_link_unavailable',false],[429,'rate_limited',true],[503,'service_unavailable',true]]){
   const schema=route.responses[status].content['application/json'].schema.properties.error.properties;
   assert.deepEqual(schema.code.enum,[code]);assert.equal(schema.retryable.const,retryable);
   assert(schema.correlationId.pattern.includes('-4'));
  }
  assert.equal(route.responses[503].headers['Retry-After'].schema.const,'5');
 }
 const parameter=api.paths[SERVICE+'/{fgaPublishServiceId}'].get.parameters.find(p=>p.name==='fgaPublishServiceId');
 assert(parameter.schema.pattern.includes('-4'));assert.equal(new RegExp(parameter.schema.pattern).test('opaque'),false);
 const candidate=api.paths[CANDIDATES.replace('/authorization/','/{uploadAuthorizationId}/')].get;
 assert.deepEqual(candidate.parameters.filter(p=>p.in==='query').map(p=>p.name),['page','page_size']);
});
