// Actual local D1/HTTP proof of synthetic upload checks; never hosted qualification.
import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {Miniflare} from 'miniflare';
import {credentialDigest} from '../../src/installations.ts';
import {createWorker} from '../../src/worker.ts';
import {runUploadChecks} from './upload_checks.ts';

const TOKEN = Array(13).fill('0000').join('-');
const metadata = {schemaVersion:1,flickrMetadata:{title:'Synthetic upload',is_public:'0',
  is_friend:'0',is_family:'0',safety_level:'1',content_type:'1',hidden:'2'}};
let migrations, outbound = 0;
test.before(() => {
  const migrationProgram = `import json,sqlite3,sys
from pathlib import Path
assert sys.version_info[:3] == (3,14,7), 'Pinned Python 3.14.7 required'
def statements(source):
    result,pending=[],''
    for line in source.splitlines(keepends=True):
        pending+=line
        if sqlite3.complete_statement(pending):
            result.append(pending.strip());pending=''
    if pending.strip(): raise ValueError('Incomplete migration')
    return result
print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))`;
  const interpreter = process.env.FGA_QUALIFICATION_PYTHON;
  migrations = JSON.parse(execFileSync(interpreter || 'uv', [
    ...(interpreter ? [] : ['run','--frozen','--offline','--no-sync','python']), '-c', migrationProgram,
  ], {encoding:'utf8'}));
  assert.equal(migrations.length,26);
});
async function fixture(t) {
  const mf = new Miniflare({modules:true,script:'export default {fetch(){return new Response("local D1 only")}}',
    compatibilityDate:'2026-07-30',cf:false,telemetry:{enabled:false},d1Databases:['DB'],
    outboundService(){outbound++;throw Error('external_access_forbidden');}});
  t.after(() => mf.dispose());
  const db = await mf.getD1Database('DB');
  for (const statements of migrations) await db.batch(statements.map(sql => db.prepare(sql)));
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('probe-user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('probe-install','probe-user','lrc_plugin','active',1,'probe-version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('probe-version','probe-install',?,'current',1)").bind(await credentialDigest(TOKEN)),
    db.prepare("INSERT INTO flickr_links VALUES('probe-user','synthetic-owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('probe-user','synthetic-generation',1,'synthetic-owner','write',NULL)"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('probe-user','linked','available','write',1)"),
    db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','probe-user',1,1)"),
  ]);
  return {db};
}
const count = async (db, table) => (await db.prepare(`SELECT count(*) n FROM ${table}`).first()).n;

test('upload helper executes actual HTTP authorization, proof, advisory, explicit resolution and replay on all 26 local D1 migrations',async t => {
  const {db} = await fixture(t);
  let fallbackCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {fallbackCalls++;throw Error('external_access_forbidden');};
  t.after(() => {globalThis.fetch = originalFetch;});
  let checks = 0;
  const result = await runUploadChecks(db,() => {checks++;});
  assert(checks > 0);
  assert.equal(result.providerCalls,3);
  assert.equal(result.syntheticPosts,0);
  assert.notEqual(result.firstPhotoBindingId,result.laterPhotoBindingId);
  const rows = (await db.prepare(`SELECT b.binding_id,b.photo_id,b.source_kind,b.verification_revision,
    e.observed_public,r.provenance,r.binding_origin FROM photo_bindings b
    JOIN upload_photo_binding_events e ON e.binding_id=b.binding_id
    LEFT JOIN upload_ambiguity_resolution_events r ON r.authorization_id=e.authorization_id
    ORDER BY b.binding_id`).all()).results;
  assert.equal(rows.length,2);
  for (const id of [result.firstPhotoBindingId,result.laterPhotoBindingId]) {
    const row = rows.find(value => value.binding_id === id);
    assert(row);assert.equal(row.source_kind,'upload');assert.equal(row.verification_revision,1);
    assert.equal(row.observed_public,0);
    if (id === result.firstPhotoBindingId) assert.equal(row.provenance,null);
    else {assert.equal(row.provenance,'photographer_reconciled_ambiguous_upload');assert.equal(row.binding_origin,1);}
  }
  assert.equal(await count(db,'upload_authorizations'),2);
  assert.equal(await count(db,'upload_photo_binding_events'),2);
  assert.equal(await count(db,'upload_ambiguity_resolution_events'),1);
  assert.equal(await count(db,'submission_intents'),0);
  assert.equal(await count(db,'transaction_guards'),0);
  assert.deepEqual((await db.prepare('PRAGMA foreign_key_check').all()).results,[]);
  assert.equal(outbound,0);assert.equal(fallbackCalls,0);
});

test('HTTP malformed, oversized, paused and revoked upload requests cannot create authority or invoke an external fallback',async t => {
  const {db} = await fixture(t);
  let providerCalls = 0, secretReads = 0;
  const failNetwork = async () => {providerCalls++;throw Error('external_access_forbidden');};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = failNetwork;
  t.after(() => {globalThis.fetch = originalFetch;});
  const worker = createWorker(failNetwork);
  const neverSecret = {get:async () => {secretReads++;throw Error('unexpected_secret_access');}};
  const env = {DB:db,FGA_UPLOAD_AUTHORIZATION_ENABLED:'1',FGA_UPLOAD_PHOTO_BINDING_ENABLED:'1',
    FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED:'1',FGA_UPLOAD_CANDIDATES_ENABLED:'1',
    FLICKR_APPLICATION:neverSecret,FLICKR_GRANT:neverSecret};
  const call = (body,headers={},path='/upload-authorizations',method='POST') => worker.fetch(new Request(
    'https://publisher.invalid/api/v001'+path,{method,headers:{Authorization:'Bearer '+TOKEN,
      'Content-Type':'application/json',...headers},body}),env);
  for (const [body,headers,status] of [
    ['{',{},400],[JSON.stringify({...metadata,foreign:true}),{},400],
    [JSON.stringify(metadata),{'Content-Type':'text/plain'},415],
    [JSON.stringify(metadata),{'Content-Encoding':'gzip'},415],
    [JSON.stringify(metadata),{'Content-Length':'16385'},413],
    [JSON.stringify({...metadata,flickrMetadata:{...metadata.flickrMetadata,title:'x'.repeat(16384)}}),{},413],
    [JSON.stringify(metadata),{Authorization:'Bearer malformed'},401],
  ]) {
    const response = await call(body,headers);assert.equal(response.status,status);
    assert.match(response.headers.get('Cache-Control'),/no-store/);
    assert.equal(await count(db,'upload_authorizations'),0);
  }
  // Malformed proof/resolution and invalid candidate queries stop before grant reads.
  for (const suffix of ['photo-binding','ambiguity-resolution']) {
    assert.equal((await call('{',{},'/upload-authorizations/synthetic/'+suffix,'PUT')).status,400);
  }
  const badCandidates = await worker.fetch(new Request('https://publisher.invalid/api/v001/upload-authorizations/synthetic/ambiguity-candidates?page=1&page_size=101',
    {headers:{Authorization:'Bearer '+TOKEN}}),env);
  assert.equal(badCandidates.status,400);
  await db.prepare("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'").run();
  const paused = await call(JSON.stringify(metadata));assert.equal(paused.status,503);
  const pausedBody = await paused.json();assert.equal(pausedBody.error.code,'flickr_writes_paused');
  assert.equal(pausedBody.error.retryable,false);
  await db.batch([
    db.prepare("UPDATE installation_credential_versions SET state='revoked' WHERE version_id='probe-version'"),
    db.prepare("UPDATE installations SET state='revoked',revision=revision+1,current_version_id=NULL,pending_version_id=NULL WHERE installation_id='probe-install'"),
  ]);
  assert.equal((await call(JSON.stringify(metadata))).status,401);
  assert.equal(await count(db,'upload_authorizations'),0);
  assert.equal(await count(db,'photo_bindings'),0);
  assert.equal(providerCalls,0);assert.equal(secretReads,0);assert.equal(outbound,0);
});

test('helper abort fence refuses all work before issuing an authorization',async t => {
  const {db} = await fixture(t);
  await assert.rejects(runUploadChecks(db,() => {throw Error('synthetic_abort');}));
  assert.equal(await count(db,'upload_authorizations'),0);
  assert.equal(await count(db,'photo_bindings'),0);assert.equal(outbound,0);
});

test('failed helper retains the first provider GET in its shared counter sink',async t => {
  const {db} = await fixture(t);
  const counters = {providerCalls:0,syntheticPosts:0};
  let fallbackCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {fallbackCalls++;throw Error('external_access_forbidden');};
  t.after(() => {globalThis.fetch = originalFetch;});
  await assert.rejects(runUploadChecks(db,() => {
    if (counters.providerCalls > 0) throw Error('synthetic_abort_after_get');
  },counters));
  assert.deepEqual(counters,{providerCalls:1,syntheticPosts:0});
  assert.equal(await count(db,'photo_bindings'),0);
  assert.equal(await count(db,'upload_photo_binding_events'),0);
  assert.equal(await count(db,'upload_ambiguity_resolution_events'),0);
  assert.equal(fallbackCalls,0);assert.equal(outbound,0);
});
