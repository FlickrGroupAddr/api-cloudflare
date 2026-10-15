import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from '../tests/sql_store.mjs';
import { createWorker } from '../src/worker.ts';
import { photoThumbnailRequest, thumbnailBody, thumbnailDestination, boundedThumbnail } from '../src/photo_thumbnails.ts';

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
const image = bytes => new Response(bytes ?? png, { headers: {'Content-Type':'image/png'} });
const secrets = { FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'app',consumerSecret:'secret'})},
  FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'gen',token:'token',tokenSecret:'secret'})} };
const requestUrl = new URL('https://flickrgroupaddr.com/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1');
const page = () => Response.json({stat:'ok',photos:{page:1,perpage:1,pages:1,total:1,photo:[{id:'photo',owner:'owner',ispublic:1,media:'photo',title:'Fixture',dateupload:'1770000000',datetaken:'2026-02-01 14:30:00',url_q:'https://live.staticflickr.com/1/photo_secret_q.png'}]}});
async function fixture() {
  const db=sqlStore();
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind('d'.repeat(64)),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('user','linked','available')"),
  ]);
  return {db,auth:{installationId:'install',credentialDigest:'d'.repeat(64)}};
}
test('identity allowlist rejects sibling ID and encoded/underscore filename confusion', () => {
  assert.equal(thumbnailDestination('https://live.staticflickr.com/1/photo_secret_q.png','photo').hostname,'live.staticflickr.com');
  for(const filename of ['other_secret_q.png','photo_extra_secret_q.png','photo%5Fsecret_q.png'])
    assert.throws(()=>thumbnailDestination('https://live.staticflickr.com/1/'+filename,'photo'));
});
test('incomplete PNG header or missing end rejects before publication', async () => {
  for(const bytes of [png.subarray(0,33),Buffer.concat([png.subarray(0,8),png.subarray(-12)]),png.subarray(0,-12)])
    await assert.rejects(thumbnailBody('https://live.staticflickr.com/1/photo_secret_q.png',async()=>image(bytes),new AbortController().signal,'photo'));
});
test('request cancellation during final combined authority read never returns image', async () => {
  const f=await fixture(),controller=new AbortController();
  const prepare=f.db.prepare.bind(f.db); let reads=0,enter,release;
  const entered=new Promise(resolve=>enter=resolve),wait=new Promise(resolve=>release=resolve);
  f.db.prepare=sql=>{const statement=prepare(sql); if(sql.includes('active_generation generation')) {
    const first=statement.first; statement.first=async()=>{reads++; if(reads===3){enter();await wait;} return first.call(statement);};
  } return statement;};
  try {
    const pending=photoThumbnailRequest(f.db,f.auth,'photo',requestUrl,secrets,page,async()=>image(),controller.signal);
    await entered; controller.abort(); const response=await pending; release();
    assert.equal(response.status,503);assert.match(response.headers.get('Content-Type'),/json/);await response.json();
  } finally {release();await new Promise(resolve=>setTimeout(resolve,0));f.db.raw.close();}
});
test('credential changes at final combined authority read reject image bytes', async () => {
  const f=await fixture(),prepare=f.db.prepare.bind(f.db);let reads=0;
  f.db.prepare=sql=>{const statement=prepare(sql);if(sql.includes('active_generation generation')) {
    const first=statement.first;statement.first=async()=>{reads++;if(reads===3)f.db.raw.exec("BEGIN; UPDATE installation_credential_versions SET state='revoked'; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1; COMMIT");return first.call(statement);};
  }return statement;};
  try {const response=await photoThumbnailRequest(f.db,f.auth,'photo',requestUrl,secrets,page,async()=>image());
    assert([401,409].includes(response.status));assert.match(response.headers.get('Content-Type'),/json/);await response.json();
  }finally {f.db.raw.close();}
});
test('observed deadline boundary is exact and rejects non-finite and backward clocks', async () => {
  for(const [clock,passes] of [[[0,14999],true],[[0,15000],false],[[0,Infinity],false],[[5,4],false]]) {
    let i=0;const result=boundedThumbnail(async()=>42,undefined,()=>clock[i++]);
    if(passes)assert.equal(await result,42);else await assert.rejects(result);
  }
});
test('enabled worker rejects invalid framing before credential lookup/provider call', async () => {
  const worker=createWorker(async()=>{throw Error('provider must not run');});
  const env={DB:{prepare(){throw Error('DB must not run');}},FGA_READ_ENABLED:'1',FGA_EXISTING_PHOTOS_ENABLED:'1',FGA_PHOTO_THUMBNAILS_ENABLED:'1'};
  for(const headers of [{'Content-Length':'1'},{'Transfer-Encoding':'chunked'},{Authorization:'Bearer a, Bearer b'}]) {
    const response=await worker.fetch(new Request(requestUrl,{headers}),env);
    assert.equal(response.status,400);assert.equal(response.headers.get('Cache-Control'),'no-store');
  }
});
