import test from 'node:test';
import assert from 'node:assert/strict';
import { putAlbumLocalRemoval } from '../src/album_local_removal_store.ts';
import { albumTitleRequest, parseAlbumTitleIntent, parseAlbumTitleRevision, albumLifecycleProjection,
  albumTitleReceiptProjection, albumTitleFailure, ALBUM_TITLE_ROUTES, ALBUM_TITLE_RELEASE_METADATA } from '../src/album_title.ts';
import { titleFixture, titleSnapshot } from './album_title_fixture.mjs';

const ID = '11111111-1111-4111-8111-111111111111', SERVICE = '22222222-2222-4222-8222-222222222222';
const NOW = '2026-10-17T12:00:00.000000Z';
const input = (title = '  Exact e\u0301 🏊  ') => ({schemaVersion:1,expectedBindingRevision:1,expectedTitleRevision:1,desiredTitle:title});
const lifecycle = () => ({schemaVersion:1,binding:{schemaVersion:1,fgaAlbumBindingId:ID,fgaPublishServiceId:SERVICE,
  localCollectionIdentifier:'Album',linkedFlickrRevision:1,bindingRevision:2,titleRevision:2,desiredTitle:'Desired',firstPhotoBindingId:'photo',flickrPhotosetId:'set'},
  localLifecycle:'active',title:{state:'pending',observedTitle:null,observedAt:null,dispatchTitleRevision:null,dispatchAttemptId:null},
  unresolvedCreateAttemptId:null,repairHandoff:{destination:'none',fgaAlbumBindingId:ID,createAttemptId:null,acknowledgedAt:null}});
const path = (id=ID,revision) => `/api/v001/album-bindings/${id}/${revision === undefined ? 'lifecycle' : 'title-intents/'+revision}`;
const request = (target=path(),value,options={}) => new Request('https://flickrgroupaddr.com'+target,
  {method:value===undefined?'GET':'PUT',headers:value===undefined?{}:{'Content-Type':'application/json'},...(value===undefined?{}:{body:JSON.stringify(value)}),...options});
async function failure(response,status,code) {
  assert.equal(response.status,status);assert.equal(response.headers.get('Cache-Control'),'private, no-store');
  assert.equal(response.headers.get('Referrer-Policy'),'no-referrer'); assert.equal(response.headers.get('X-Content-Type-Options'),'nosniff');
  const raw=await response.text();assert(new TextEncoder().encode(raw).length<=1024);
  const body=JSON.parse(raw);assert.equal(body.error.code,code);assert.equal(body.error.retryable,status===503||status===429);return body;
}
test('title parser preserves exact Unicode and rejects closed-schema, duplicate and rounded values',()=>{
  assert.deepEqual(parseAlbumTitleIntent(JSON.stringify(input())),input());
  assert.equal(parseAlbumTitleIntent('{"schemaVersion":1e0,"expectedBindingRevision":1.0,"expectedTitleRevision":1,"desiredTitle":"x"}').expectedBindingRevision,1);
  for(const value of [{...input(),extra:1},{...input(),schemaVersion:2},{...input(),desiredTitle:null},{...input(),desiredTitle:''},
    {...input(),desiredTitle:'x'.repeat(1001)},{...input(),desiredTitle:'bad\n'},{...input(),desiredTitle:'\ud800'},
    {...input(),expectedBindingRevision:0},{...input(),expectedTitleRevision:Number.MAX_SAFE_INTEGER+1}]) assert.throws(()=>parseAlbumTitleIntent(JSON.stringify(value)));
  for(const raw of ['{"schemaVersion":1,"schemaVersion":1,"expectedBindingRevision":1,"expectedTitleRevision":1,"desiredTitle":"x"}',
    '{"schemaVersion":1,"expectedBindingRevision":1.00000000000000001,"expectedTitleRevision":1,"desiredTitle":"x"}',
    '{"schemaVersion":1,"expectedBindingRevision":1,"expectedTitleRevision":1,"desiredTitle":"x","desired\\u0054itle":"x"}']) assert.throws(()=>parseAlbumTitleIntent(raw));
});
test('revision path is canonical positive safe integer only',()=>{
  assert.equal(parseAlbumTitleRevision('9007199254740991'),Number.MAX_SAFE_INTEGER);
  for(const value of ['0','02','+2','-2','2.0','2e0',' 2','2 ','9007199254740992','%32','2/'])assert.throws(()=>parseAlbumTitleRevision(value));
});
test('complete lifecycle projection rejects unknown fields, inconsistent pairs, foreign IDs and invalid times',()=>{
  assert.deepEqual(albumLifecycleProjection(lifecycle(),ID),lifecycle());
  const mutations=[v=>v.extra=1,v=>v.binding.extra=1,v=>v.title.extra=1,v=>v.repairHandoff.extra=1,
    v=>v.binding.fgaAlbumBindingId=SERVICE,v=>v.repairHandoff.fgaAlbumBindingId=SERVICE,
    v=>v.title.observedAt=NOW,v=>v.title.dispatchAttemptId=ID,v=>v.title.state='synced',
    v=>{v.title.observedTitle='x';v.title.observedAt='2026-02-30T12:00:00.000000Z';},
    v=>{v.title.observedTitle='🏊'.repeat(1025);v.title.observedAt=NOW;},v=>v.localLifecycle='local_collection_removed_remote_preserved',
    v=>{v.title.dispatchTitleRevision=3;v.title.dispatchAttemptId=ID;},v=>{v.repairHandoff.destination='administrative_album_create_repair';v.repairHandoff.createAttemptId=ID;v.repairHandoff.acknowledgedAt=NOW;}];
  for(const mutate of mutations){const value=lifecycle();mutate(value);assert.throws(()=>albumLifecycleProjection(value,ID));}
  const observed=lifecycle();observed.title.observedTitle='';observed.title.observedAt=NOW;assert.equal(albumLifecycleProjection(observed,ID).title.observedTitle,'');
});
test('receipt projection keeps immutable acceptance facts after supersession and archive',()=>{
  const current=lifecycle();current.binding.titleRevision=3;current.binding.bindingRevision=4;
  current.localLifecycle='local_collection_removed_remote_preserved';current.title.state='local_removed';
  const receipt={schemaVersion:1,fgaAlbumBindingId:ID,acceptedTitleRevision:2,acceptedDesiredTitle:'Old',acceptedBindingRevision:2,acceptedAt:NOW,current};
  assert.deepEqual(albumTitleReceiptProjection(receipt,ID,2,input('Old')),receipt);
  for(const key of ['acceptedTitleRevision','acceptedDesiredTitle','acceptedBindingRevision','acceptedAt']){
    const bad=structuredClone(receipt);bad[key]=null;assert.throws(()=>albumTitleReceiptProjection(bad,ID,2,input('Old')));
  }
});
test('default-off and malformed raw requests perform no database access',async()=>{
  const db=new Proxy({}, {get(){assert.fail('request must not access database');}}),auth={installationId:'x',credentialDigest:'x'};
  await failure(await albumTitleRequest({DB:db},auth,request(),ID),503,'service_unavailable');
  const env={DB:db,FGA_ALBUM_TITLE_ENABLED:'1'};
  for(const [target,revision,body,options] of [[path()+'?x=1',undefined,undefined,{}],[path(ID, '02'),'02',input(),{}],
    [path(ID,2),'2',{...input(),extra:1},{}],[path(ID,2),'2',input(),{headers:{'Content-Type':'text/plain'}}],
    [path(ID,2),'2',input(),{body:'{"schemaVersion":1,"schemaVersion":1}'}],
    [path(ID,2),'2',input(),{body:' '.repeat(4097)}],[path(ID,2),'2',input(),{body:new Uint8Array([0xff])}],
    [path(ID,2)+'?x=1','2',input(),{}],[path().replace(ID, '%31'+ID.slice(1)),undefined,undefined,{}]]) {
    await failure(await albumTitleRequest(env,auth,request(target,body,options),ID,revision),400,'invalid_request');
  }
  assert.equal(ALBUM_TITLE_RELEASE_METADATA.defaultValue,'0');assert.equal(ALBUM_TITLE_ROUTES.length,2);
});
test('finite application errors are sanitized and unknown failures become retryable unavailable',async()=>{
  for(const [code,status] of [['invalid_token',401],['insufficient_scope',403],['resource_not_found',404],['stale_binding_revision',409],
    ['title_intent_conflict',409],['album_closed',409],['flickr_link_unavailable',409],['revision_exhausted',409],['rate_limited',429]]){
    const response=albumTitleFailure(code);if(status===401||status===403)assert.match(response.headers.get('WWW-Authenticate'),new RegExp(code));
    await failure(response,status,code);
  }
  await failure(albumTitleFailure('private upstream payload'),503,'service_unavailable');
});
test('HTTP acceptance and exact replay expose immutable receipt with fresh current state and no read mutation',async t=>{
  const f=await titleFixture(t),env={DB:f.db,FGA_ALBUM_TITLE_ENABLED:'1'};
  let b=await f.binding();const value={schemaVersion:1,expectedBindingRevision:b.binding_revision,expectedTitleRevision:b.title_revision,desiredTitle:'Deliberate title'};
  const rev=String(b.title_revision+1),target=path(f.bindingId,rev),before=await titleSnapshot(f.db);
  const created=await albumTitleRequest(env,f.auth,request(target,value),f.bindingId,rev);assert.equal(created.status,201);
  assert.equal(created.headers.get('Location'),target);assert.equal(created.headers.get('Cache-Control'),'private, no-store');
  const receipt=await created.json();assert.equal(receipt.acceptedDesiredTitle,value.desiredTitle);assert.equal(receipt.acceptedTitleRevision,Number(rev));
  const accepted=await titleSnapshot(f.db);assert.notDeepEqual(accepted,before);
  const get=await albumTitleRequest(env,f.auth,request(path(f.bindingId)),f.bindingId);assert.equal(get.status,200);assert.deepEqual(await get.json(),receipt.current);
  assert.deepEqual(await titleSnapshot(f.db),accepted);
  await f.rename('New deliberate title');const superseded=await titleSnapshot(f.db);
  const replay=await albumTitleRequest(env,f.auth,request(target,value),f.bindingId,rev);assert.equal(replay.status,200);assert.equal(replay.headers.get('Location'),null);
  const replayed=await replay.json();assert.equal(replayed.acceptedAt,receipt.acceptedAt);assert.equal(replayed.acceptedBindingRevision,receipt.acceptedBindingRevision);
  assert.equal(replayed.acceptedDesiredTitle,value.desiredTitle);assert.equal(replayed.current.binding.desiredTitle,'New deliberate title');
  assert.deepEqual(await titleSnapshot(f.db),superseded);
  await failure(await albumTitleRequest(env,f.auth,request(target,{...value,desiredTitle:'Conflicting text'}),f.bindingId,rev),409,'title_intent_conflict');
  await failure(await albumTitleRequest(env,f.auth,request(target,{...value,expectedTitleRevision:value.expectedTitleRevision+1}),f.bindingId,rev),409,'title_intent_conflict');
  await failure(await albumTitleRequest(env,f.auth,request(target,{...value,expectedBindingRevision:value.expectedBindingRevision+1}),f.bindingId,rev),409,'title_intent_conflict');
  await putAlbumLocalRemoval(f.db,f.auth,f.bindingId,{schemaVersion:1,expectedBindingRevision:(await f.binding()).binding_revision,acknowledgedCreateAttemptId:null});
  f.db.raw.exec("UPDATE flickr_links SET state='paused' WHERE user_id='user'");
  const archived=await titleSnapshot(f.db),archivedReplay=await albumTitleRequest(env,f.auth,request(target,value),f.bindingId,rev);
  assert.equal(archivedReplay.status,200);const retained=await archivedReplay.json();assert.equal(retained.acceptedAt,receipt.acceptedAt);
  assert.equal(retained.acceptedDesiredTitle,value.desiredTitle);assert.equal(retained.current.localLifecycle,'local_collection_removed_remote_preserved');
  assert.equal(retained.current.title.state,'local_removed');assert.deepEqual(await titleSnapshot(f.db),archived);
});
