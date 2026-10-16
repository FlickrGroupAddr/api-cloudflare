import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {Miniflare} from 'miniflare';
import {uploadAmbiguityResolutionRequest as resolve} from '../src/upload_ambiguity_resolution.ts';

test('actual local D1 atomic batches elect one conflicting resolution and retain append-only provenance', async t => {
  const mf = new Miniflare({modules: true, script: 'export default {fetch(){return new Response("local proof")}}',
    compatibilityDate: '2026-07-30', cf: false, telemetry: {enabled: false}, d1Databases: ['DB'],
    outboundService() { throw new Error('No live network'); }});
  t.after(() => mf.dispose());
  const db = await mf.getD1Database('DB');
  const migrations = JSON.parse(execFileSync('uv', ['tool', 'run', '--from', 'uv==0.12.5', 'uv', 'run', '--frozen', 'python', '-c',
    "import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))"], {encoding: 'utf8'}));
  for (const sql of migrations) await db.batch(sql.map(s => db.prepare(s)));
  const auth = {installationId: 'install', credentialDigest: 'd'.repeat(64)};
  await db.batch(["INSERT INTO fga_users VALUES('user')",
    "INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')",
    `INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install','${auth.credentialDigest}','current',1)`,
    "INSERT INTO flickr_links VALUES('user','owner',1,'linked')",
    "INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')",
    "INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('user','linked','available')",
    "INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us) VALUES('authorization','install','user',1)"].map(sql => db.prepare(sql)));

  const env = {DB: db, FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '1',
    FLICKR_APPLICATION: {get: async () => JSON.stringify({schemaVersion: 1, consumerKey: 'app', consumerSecret: 'secret'})},
    FLICKR_GRANT: {get: async () => JSON.stringify({schemaVersion: 1, generation: 'gen', token: 'token', tokenSecret: 'secret'})}};
  let arrivals = 0, release; const both = new Promise(r => release = r);
  const fetcher = async request => { if (++arrivals === 2) release(); await both;
    return Response.json({stat: 'ok', photo: {id: new URL(request.url).searchParams.get('photo_id'), owner: {nsid: 'owner'}, visibility: {ispublic: 0}}}); };
  const call = photoId => resolve(env, auth, 'authorization', {schemaVersion: 1, flickrPhotoId: photoId}, fetcher);
  const responses = await Promise.all([call('photo'), call('other')]);
  assert.deepEqual(responses.map(r => r.status).sort(), [201, 409]);
  const winner = await responses.find(r => r.status === 201).json();
  assert.equal(winner.sourceKind, 'photographer_reconciled_ambiguous_upload');
  const repeat = await call(winner.flickrPhotoId); assert.equal(repeat.status, 200); assert.deepEqual(await repeat.json(), winner);
  assert.equal((await db.prepare('SELECT COUNT(*) n FROM photo_bindings').first()).n, 1);
  assert.equal((await db.prepare('SELECT COUNT(*) n FROM upload_ambiguity_resolution_events').first()).n, 1);
  assert.equal((await db.prepare('SELECT COUNT(*) n FROM transaction_guards').first()).n, 0);
  for (const sql of ['DELETE FROM upload_ambiguity_resolution_events', 'UPDATE upload_ambiguity_resolution_events SET binding_origin=0',
    'INSERT OR REPLACE INTO upload_ambiguity_resolution_events SELECT * FROM upload_ambiguity_resolution_events'])
    await assert.rejects(db.prepare(sql).run());
  await db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us) VALUES('rollback','install','user',2)").run();
  const before = await db.prepare('SELECT verification_revision FROM photo_bindings').first();
  await db.prepare("CREATE TRIGGER synthetic_resolution_failure BEFORE INSERT ON upload_ambiguity_resolution_events WHEN NEW.authorization_id='rollback' BEGIN SELECT RAISE(ABORT,'synthetic_resolution_failure'); END").run();
  const failed = await resolve(env, auth, 'rollback', {schemaVersion: 1, flickrPhotoId: winner.flickrPhotoId}, fetcher);
  assert.equal(failed.status, 503);
  assert.equal((await db.prepare("SELECT photo_id FROM upload_authorizations WHERE authorization_id='rollback'").first()).photo_id, null);
  assert.equal((await db.prepare("SELECT COUNT(*) n FROM upload_photo_binding_events WHERE authorization_id='rollback'").first()).n, 0);
  assert.equal((await db.prepare('SELECT verification_revision FROM photo_bindings').first()).verification_revision, before.verification_revision);
  assert.equal((await db.prepare('SELECT COUNT(*) n FROM transaction_guards').first()).n, 0);

});
