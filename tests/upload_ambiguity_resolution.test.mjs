import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { uploadAmbiguityResolutionRequest as uploadPhotoBindingRequest, UPLOAD_AMBIGUITY_RESOLUTION_ROUTES as UPLOAD_PHOTO_BINDING_ROUTES, UPLOAD_AMBIGUITY_RESOLUTION_RELEASE_METADATA as UPLOAD_PHOTO_BINDING_RELEASE_METADATA } from '../src/upload_ambiguity_resolution.ts';
import { commitBinding } from '../src/flickr_reads.ts';

const auth = { installationId: 'install', credentialDigest: 'd'.repeat(64) };
const grant = { userId: 'user', ownerNsid: 'owner', revision: '1', generation: 'gen' };
const secrets = { FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'app', consumerSecret: 'secret' }) },
  FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'token', tokenSecret: 'token-secret' }) } };
const info = (id = 'photo', visibility = '1') => ({ stat: 'ok', photo: { id, owner: { nsid: 'owner' }, visibility: { ispublic: visibility },
  title: { _content: 'Must not persist' }, description: { _content: 'Private metadata' } } });
async function fixture(t) {
  const db = sqlStore(); t.after(() => db.raw.close());
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(auth.credentialDigest),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('user','linked','available')"),
    db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us) VALUES('authorization','install','user',1)"),
  ]);
  const env = { DB: db, ...secrets, FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '1' };
  return { db, env, call: (fetcher = async () => Response.json(info()), photoId = 'photo', id = 'authorization', value) =>
    uploadPhotoBindingRequest(env, auth, id, value ?? { schemaVersion: 1, flickrPhotoId: photoId }, fetcher) };
}
const rows = db => ({ authorization: db.raw.prepare('SELECT * FROM upload_authorizations').all(),
  bindings: db.raw.prepare('SELECT * FROM photo_bindings').all(), events: db.raw.prepare('SELECT * FROM upload_photo_binding_events').all(),
  resolutions: db.raw.prepare('SELECT * FROM upload_ambiguity_resolution_events').all(),
  guards: db.raw.prepare('SELECT * FROM transaction_guards').all() });
const noProof = db => { const state = rows(db); assert.equal(state.authorization[0].photo_id, null); assert.equal(state.bindings.length, 0); assert.equal(state.events.length, 0); assert.equal(state.resolutions.length, 0); assert.equal(state.guards.length, 0); };

test('closed dedicated PUT contract defaults disabled and supports ordinary zero-group proof', async t => {
  const route = UPLOAD_PHOTO_BINDING_ROUTES[0];
  assert.equal(route.method, 'PUT'); assert.equal(route.allowPending, false); assert.deepEqual(route.successStatuses, [200, 201]);
  assert.equal(route.request.additionalProperties, false); assert.equal(route.response.additionalProperties, false);
  assert.equal(UPLOAD_PHOTO_BINDING_RELEASE_METADATA.defaultValue, '0');
  const f = await fixture(t); delete f.env.FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED;
  const original = f.db.prepare; f.db.prepare = () => assert.fail('disabled operation must not query');
  assert.equal((await f.call(async () => assert.fail('disabled operation must not fetch'))).status, 503);
  f.db.prepare = original; f.env.FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED = '1';
  const first = await f.call(async request => {
    const u = new URL(request.url); assert.equal(request.method, 'GET'); assert.equal(request.redirect, 'manual');
    assert.deepEqual(Object.fromEntries(u.searchParams), { method: 'flickr.photos.getInfo', format: 'json', nojsoncallback: '1', photo_id: 'photo' });
    assert.match(request.headers.get('Authorization'), /^OAuth /); return Response.json(info());
  });
  assert.equal(first.status, 201); assert.equal(first.headers.get('Location'), '/api/v001/upload-authorizations/authorization/ambiguity-resolution');
  assert.equal(first.headers.get('Cache-Control'), 'no-store');
  const body = await first.json(); assert.equal(body.sourceKind, 'photographer_reconciled_ambiguous_upload'); assert.equal(body.verificationRevision, 1);
  assert.match(body.verifiedAt, /^\d{4}-\d{2}-\d{2}T.*\.\d{6}Z$/);
  const repeat = await f.call(async () => assert.fail('matching committed replay must not fetch'));
  assert.equal(repeat.status, 200); assert.deepEqual(await repeat.json(), body);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n, 0);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM group_partitions').get().n, 0);
  const state = rows(f.db); assert.equal(state.events.length, 1); assert.equal(state.events[0].observed_public, 1);
  assert.equal(state.authorization[0].photo_id, 'photo');
  assert(!JSON.stringify(state).includes('Must not persist')); assert(!JSON.stringify(state).includes('token-secret'));
});

test('private upload proof is valid and stores only its minimal visibility observation', async t => {
  const f = await fixture(t), response = await f.call(async () => Response.json(info('photo', 0)));
  assert.equal(response.status, 201); assert.equal(rows(f.db).events[0].observed_public, 0);
});

test('authorization ownership is installation-specific and absent/foreign tuples make no Flickr read', async t => {
  const f = await fixture(t); const peer = async () => assert.fail('not visible');
  assert.equal((await f.call(peer, 'photo', 'missing')).status, 404);
  assert.equal((await f.call(peer, 'photo', '../authorization')).status, 404);
  await f.db.batch([
    f.db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('peer','user','lrc_plugin','active',1,'peer-version')"),
    f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('peer-version','peer','eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','current',1)"),
    f.db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us) VALUES('peer-auth','peer','user',1)"),
  ]);
  assert.equal((await f.call(peer, 'photo', 'peer-auth')).status, 404); noProof(f.db);
});

test('unknown JSON fields, identity fields, malformed IDs and wrong schema fail before reads/writes', async t => {
  const f = await fixture(t), peer = async () => assert.fail('invalid request');
  for (const value of [{ schemaVersion: 2, flickrPhotoId: 'photo' }, { schemaVersion: 1, flickrPhotoId: 'photo', owner: 'owner' },
    { schemaVersion: 1, flickrPhotoId: 'photo', flickrGroupIds: [] }, { flickrPhotoId: 'photo' }, []])
    assert.equal((await f.call(peer, 'photo', 'authorization', value)).status, 400);
  for (const flickrPhotoId of ['', 'photo with space', null, 1, 'p'.repeat(129)])
    assert.equal((await f.call(peer, 'photo', 'authorization', { schemaVersion: 1, flickrPhotoId })).status, 422);
  noProof(f.db);
});

test('wrong-owner is forbidden; missing/partial/mismatched/malformed observations remain retryable unknown', async t => {
  const f = await fixture(t), wrong = info(); wrong.photo.owner.nsid = 'different';
  assert.equal((await f.call(async () => Response.json(wrong))).status, 403); noProof(f.db);
  const missing = await f.call(async () => Response.json({ stat: 'fail', code: 1, message: 'Photo not found' }));
  assert.equal(missing.status, 503); assert.equal(missing.headers.get('Retry-After'), '5');
  assert.equal((await missing.json()).error.retryable, true); noProof(f.db);
  for (const body of [{ stat: 'ok' }, { stat: 'fail', code: 1 }, { stat: 'ok', photo: { id: 'photo' } }, info('different'),
    { ...info(), photo: { ...info().photo, visibility: {} } }, { ...info(), photo: { ...info().photo, media: 'video' } }]) {
    const response = await f.call(async () => Response.json(body)); assert.equal(response.status, 503);
    assert.equal(response.headers.get('Retry-After'), '5'); assert.equal((await response.json()).error.retryable, true); noProof(f.db);
  }
  for (const peer of [async () => { throw new Error('secret metadata'); }, async () => new Response('{', { headers: { 'Content-Type': 'application/json' } }),
    async () => new Response('{}', { status: 302, headers: { 'Content-Type': 'application/json', Location: 'https://evil.test' } }),
    async () => new Response('{}', { headers: { 'Content-Type': 'application/json;charset=iso-8859-1' } })]) {
    const response = await f.call(peer); assert.equal(response.status, 503); assert(!(await response.text()).includes('secret metadata')); noProof(f.db);
  }
});

test('existing-public and upload proofs converge in both directions while retaining first source and appending provenance', async t => {
  const f = await fixture(t);
  const before = await commitBinding(f.db, auth, grant, 'photo');
  const uploaded = await f.call(); assert.equal(uploaded.status, 201); const body = await uploaded.json();
  assert.equal(body.fgaPhotoBindingId, before.body.fgaPhotoBindingId); assert.equal(body.sourceKind, 'existing_public_flickr_photo');
  assert.equal(body.verificationRevision, 2); assert.equal(rows(f.db).events.length, 1);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_binding_events').get().n, 1);
  await commitBinding(f.db, auth, grant, 'photo');
  const repeat = await f.call(async () => assert.fail('replay')); assert.equal(repeat.status, 200);
  assert.equal((await repeat.json()).verificationRevision, 3); assert.equal(rows(f.db).events[0].verification_revision, 2);
  const g = await fixture(t); const initial = await (await g.call()).json(); const existing = await commitBinding(g.db, auth, grant, 'photo');
  assert.equal(existing.body.fgaPhotoBindingId, initial.fgaPhotoBindingId); assert.equal(existing.body.sourceKind, 'photographer_reconciled_ambiguous_upload');
  assert.equal(rows(g.db).events[0].verification_revision, 1);
});

test('same authorization different tuple conflicts without reads or changing immutable proof', async t => {
  const f = await fixture(t); await f.call(); const before = rows(f.db);
  assert.equal((await f.call(async () => assert.fail('conflict must not fetch'), 'other')).status, 409);
  assert.deepEqual(rows(f.db), before);
});

test('racing same tuples converge 201/200 and different tuples permit only one 201 winner', async t => {
  for (const same of [true, false]) {
    const f = await fixture(t); let arrivals = 0, release; const both = new Promise(resolve => release = resolve);
    const batch = f.db.batch.bind(f.db); let pending = Promise.resolve();
    f.db.batch = statements => { const result = pending.then(() => batch(statements)); pending = result.catch(() => {}); return result; };
    const peer = async request => { if (++arrivals === 2) release(); await both; return Response.json(info(new URL(request.url).searchParams.get('photo_id'))); };
    const responses = await Promise.all([f.call(peer), f.call(peer, same ? 'photo' : 'other')]);
    assert.deepEqual(responses.map(r => r.status).sort(), same ? [200, 201] : [201, 409]);
    const state = rows(f.db); assert.equal(state.bindings.length, 1); assert.equal(state.events.length, 1);
    assert.equal(state.bindings[0].verification_revision, 1); assert.equal(state.authorization[0].photo_id, state.bindings[0].photo_id);
  }
});

const REVOKE = "BEGIN; UPDATE installation_credential_versions SET state='revoked'; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1; COMMIT";
const ROTATE = "BEGIN; UPDATE installation_credential_versions SET state='replaced'; INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('new-version','install','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','current',2); UPDATE installations SET current_version_id='new-version',revision=revision+1; COMMIT";
test('credential rotation/revocation, link revision and native generation changes fence proof commit', async t => {
  for (const mutation of [REVOKE, ROTATE, "UPDATE installations SET revision=revision+1", "UPDATE flickr_links SET link_revision=2",
    "UPDATE flickr_native_credentials SET active_generation='other'", "UPDATE flickr_native_credentials SET operation_id='pending'"]) {
    const f = await fixture(t); const response = await f.call(async () => { f.db.raw.exec(mutation); return Response.json(info()); });
    assert([401, 409].includes(response.status)); noProof(f.db);
  }
});

test('atomic guards reject authority mutation after observation and before the SQL batch', async t => {
  for (const mutation of ["UPDATE flickr_links SET link_revision=2", "UPDATE flickr_native_credentials SET active_generation='other'", ROTATE]) {
    const f = await fixture(t), original = f.db.batch.bind(f.db);
    f.db.batch = async statements => { f.db.raw.exec(mutation); return original(statements); };
    const response = await f.call(); assert([401, 409].includes(response.status)); noProof(f.db);
  }
});

test('every injected transactional failure rolls back upload association, shared proof and provenance', async t => {
  for (let index = 0; index < 8; index++) {
    const f = await fixture(t); f.db.fault = index;
    assert.equal((await f.call()).status, 503); noProof(f.db);
  }
  const f = await fixture(t); await commitBinding(f.db, auth, grant, 'photo'); const before = rows(f.db);
  f.db.fault = 5; assert.equal((await f.call()).status, 503); assert.deepEqual(rows(f.db), before);
});

test('upload provenance resists update/delete/replace and keeps its original proof after common refresh', async t => {
  const f = await fixture(t); await f.call(); const event = rows(f.db).events[0];
  for (const sql of ["UPDATE upload_photo_binding_events SET observed_public=0", "DELETE FROM upload_photo_binding_events",
    "INSERT OR REPLACE INTO upload_photo_binding_events SELECT * FROM upload_photo_binding_events"])
    assert.throws(() => f.db.raw.exec(sql));
  await commitBinding(f.db, auth, grant, 'photo'); assert.deepEqual(rows(f.db).events[0], event);
  assert.throws(() => f.db.raw.exec("UPDATE upload_authorizations SET photo_id='other'"));
});

test('stale-link committed replay fails closed and makes no Flickr request', async t => {
  const f = await fixture(t); await f.call();
  f.db.raw.exec("UPDATE flickr_links SET link_revision=2; UPDATE flickr_native_credentials SET link_revision=2");
  const response = await f.call(async () => assert.fail('stale replay')); assert.equal(response.status, 409);
});

test('separate authorizations for the same photo append distinct immutable provenance without duplicating identity', async t => {
  const f = await fixture(t); const first = await (await f.call()).json();
  f.db.raw.exec("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us) VALUES('second','install','user',2)");
  const response = await f.call(undefined, 'photo', 'second'); assert.equal(response.status, 201);
  const second = await response.json(); assert.equal(second.fgaPhotoBindingId, first.fgaPhotoBindingId);
  assert.equal(second.verificationRevision, 2); assert.equal(rows(f.db).bindings.length, 1); assert.equal(rows(f.db).events.length, 2);
  assert.deepEqual(rows(f.db).events.map(e => e.verification_revision), [1, 2]);
});

test('secret-resolution races fail before network reads, and unsafe linked revisions fail closed', async t => {
  for (const mutation of [ROTATE, "UPDATE flickr_native_credentials SET active_generation='changed'", "UPDATE flickr_links SET link_revision=2"]) {
    const f = await fixture(t);
    f.env.FLICKR_GRANT = { get: async () => { f.db.raw.exec(mutation); return secrets.FLICKR_GRANT.get(); } };
    const response = await f.call(async () => assert.fail('stale secret resolution must not fetch'));
    assert([401, 409].includes(response.status)); noProof(f.db);
  }
  const f = await fixture(t);
  f.db.raw.exec('UPDATE flickr_links SET link_revision=9007199254740992; UPDATE flickr_native_credentials SET link_revision=9007199254740992');
  assert.equal((await f.call(async () => assert.fail('unsafe revision must not fetch'))).status, 409); noProof(f.db);
});

test('resolution marker is immutable, minimal and keeps existing common origins', async t => {
  const f = await fixture(t); await f.call();
  assert.deepEqual(rows(f.db).resolutions.map(r => ({...r})), [{ authorization_id: 'authorization',
    provenance: 'photographer_reconciled_ambiguous_upload', binding_origin: 1 }]);
  for (const sql of ["UPDATE upload_ambiguity_resolution_events SET binding_origin=0",
    "DELETE FROM upload_ambiguity_resolution_events",
    "INSERT OR REPLACE INTO upload_ambiguity_resolution_events SELECT * FROM upload_ambiguity_resolution_events"])
    assert.throws(() => f.db.raw.exec(sql));
  const g = await fixture(t); await commitBinding(g.db, auth, grant, 'photo'); await g.call();
  assert.equal(rows(g.db).resolutions[0].binding_origin, 0);
  const response = await g.call(async () => assert.fail('repeat must not fetch'));
  assert.equal((await response.json()).sourceKind, 'existing_public_flickr_photo');
});

test('normal and reconciled resources share immutable same-tuple semantics without inventing provenance', async t => {
  const { uploadPhotoBindingRequest: normal } = await import('../src/upload_photo_binding.ts');
  for (const resolutionFirst of [true, false]) {
    const f = await fixture(t); f.env.FGA_UPLOAD_PHOTO_BINDING_ENABLED = '1';
    const normalCall = (id = 'photo') => normal(f.env, auth, 'authorization', { schemaVersion: 1, flickrPhotoId: id }, async () => Response.json(info(id)));
    const first = await (resolutionFirst ? f.call() : normalCall()); assert.equal(first.status, 201);
    const before = rows(f.db);
    const repeat = await (resolutionFirst ? normalCall() : f.call(async () => assert.fail('same tuple must not fetch')));
    assert.equal(repeat.status, 200);
    assert.equal((await repeat.json()).sourceKind, resolutionFirst ? 'photographer_reconciled_ambiguous_upload' : 'fga_direct_upload');
    assert.deepEqual(rows(f.db), before);
    assert.equal(rows(f.db).resolutions.length, resolutionFirst ? 1 : 0);
    assert.equal((await normalCall('other')).status, 409); assert.deepEqual(rows(f.db), before);
  }
});
