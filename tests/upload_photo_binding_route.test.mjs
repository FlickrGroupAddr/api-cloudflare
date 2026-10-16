import test from 'node:test';
import assert from 'node:assert/strict';
import {sqlStore} from './sql_store.mjs';
import {createWorker, ROUTES} from '../src/worker.ts';
import {credentialDigest, NOW_US_SQL} from '../src/installations.ts';

const CODE=Array(13).fill('0000').join('-');
const PENDING=Array(12).fill('0000').concat('000G').join('-');
const PATH='/api/v001/upload-authorizations/authorization/photo-binding';
const value={schemaVersion:1,flickrPhotoId:'photo'};

async function fixture(t){
 const db=sqlStore();t.after(()=>db.raw.close());
 await db.batch([
  db.prepare("INSERT INTO fga_users VALUES('user')"),
  db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
  db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(await credentialDigest(CODE)),
  db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
  db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
  db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('user','linked','available')"),
  db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us) VALUES('authorization','install','user',1)"),
 ]);
 let calls=0;
 const worker=createWorker(async request=>{
  calls++; assert.equal(new URL(request.url).searchParams.get('method'),'flickr.photos.getInfo');
  return Response.json({stat:'ok',photo:{id:'photo',owner:{nsid:'owner'},visibility:{ispublic:0}}});
 });
 const env={DB:db,FGA_UPLOAD_PHOTO_BINDING_ENABLED:'1',FGA_READ_ENABLED:'0',FGA_INTAKE_ENABLED:'0',FGA_DISPATCH_ENABLED:'0',
  FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'app',consumerSecret:'app-secret'})},
  FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'gen',token:'token',tokenSecret:'token-secret'})}};
 const call=({path=PATH,method='PUT',body=JSON.stringify(value),credential=CODE,headers={}}={})=>worker.fetch(new Request('https://flickrgroupaddr.com'+path,{
  method,headers:{...(credential===null?{}:{Authorization:'Bearer '+credential}),'Content-Type':'application/json',...headers},
  ...(['GET','HEAD'].includes(method)||body===null?{}:{body})}),env);
 return {db,env,call,calls:()=>calls};
}

test('disabled upload binding stops before authentication, provider or DB access',async t=>{
 const f=await fixture(t);delete f.env.FGA_UPLOAD_PHOTO_BINDING_ENABLED;
 f.db.prepare=()=>assert.fail('disabled route must not access DB');
 const response=await f.call({credential:null});assert.equal(response.status,503);
 assert.equal(response.headers.get('Cache-Control'),'no-store');assert.equal(f.calls(),0);
});

test('registered PUT dispatches private upload proof and stable repeat with all write features off',async t=>{
 const f=await fixture(t), route=ROUTES.find(r=>r.handler==='upload_photo_binding');
 assert(route);assert.equal(route.method,'PUT');assert.equal(route.allowPending,false);
 const first=await f.call();assert.equal(first.status,201);assert.equal(first.headers.get('Location'),PATH);
 const body=await first.json();assert.equal(body.sourceKind,'fga_direct_upload');assert.equal(f.calls(),1);
 const repeat=await f.call();assert.equal(repeat.status,200);assert.deepEqual(await repeat.json(),body);assert.equal(f.calls(),1);
 assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n,0);
 assert.equal(f.db.raw.prepare('SELECT observed_public v FROM upload_photo_binding_events').get().v,0);
});

test('upload binding retains bearer, query, method and closed JSON framing boundaries',async t=>{
 const f=await fixture(t);
 for(const [options,status] of [
  [{credential:null},401],[{credential:null,headers:{Cookie:'__Host-fga_admin=synthetic'}},401],
  [{credential:'bad-code'},401],[{path:PATH+'?credential=synthetic'},400],
  [{method:'POST'},405],[{headers:{'Content-Type':'text/plain'}},415],
  [{headers:{'Content-Encoding':'gzip'}},415],[{body:'{'},400],
  [{body:JSON.stringify({...value,userId:'foreign'})},400],
 ]){const response=await f.call(options);assert.equal(response.status,status);assert.equal(response.headers.get('Cache-Control'),'no-store');}
 assert.equal(f.calls(),0);assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n,0);
});

test('pending installation credential cannot use upload proof',async t=>{
 const f=await fixture(t);
 await f.db.batch([
  f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install',?,'pending_rotation',2,${NOW_US_SQL}+300000000)`).bind(await credentialDigest(PENDING)),
  f.db.prepare("UPDATE installations SET pending_version_id='pending',revision=revision+1 WHERE installation_id='install'"),
 ]);
 const response=await f.call({credential:PENDING});assert.equal(response.status,403);
 assert.match(response.headers.get('WWW-Authenticate'),/insufficient_scope/);assert.equal(f.calls(),0);
});
