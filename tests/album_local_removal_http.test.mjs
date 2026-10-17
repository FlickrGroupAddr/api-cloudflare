import test from 'node:test';
import assert from 'node:assert/strict';
import { titleFixture } from './album_title_fixture.mjs';
import { createWorker, ROUTES } from '../src/worker.ts';
import { credentialDigest, NOW_US_SQL } from '../src/installations.ts';
import { digest } from '../src/browser_sessions.ts';
import { createSyntheticAlbumCreateRepairReader } from '../src/album_create_repair_discovery.ts';
import { assertAlbumRepairContext } from '../src/album_create_repair_store.ts';
import { claimAlbumMaterialization, markAlbumCreateDispatch, unknownAlbumMaterialization } from '../src/album_materialization_store.ts';

const ORIGIN = 'https://flickrgroupaddr.com', CODE = Array(13).fill('0000').join('-');
const PENDING = Array(12).fill('0000').concat('000G').join('-');
const FOREIGN = Array(12).fill('0000').concat('0010').join('-');
const ABSENT = '99999999-9999-4999-8999-999999999999';
const albumPath = id => `/api/v001/album-bindings/${id}/local-removal`;
const photoPath = (id, photo = 'primary-photo') => `/api/v001/album-bindings/${id}/photo-associations/${encodeURIComponent(photo)}/local-removal`;
const albumInput = revision => ({ schemaVersion: 1, expectedBindingRevision: revision, acknowledgedCreateAttemptId: null });
const photoInput = (binding = 1, obligation = 1) => ({ schemaVersion: 1, expectedBindingRevision: binding, expectedObligationRevision: obligation });
const request = (path, value, { credential = CODE, headers = {}, method = 'PUT', raw } = {}) => new Request(ORIGIN + path, {
  method, headers: { ...(credential === null ? {} : { Authorization: 'Bearer ' + credential }),
    ...(['GET', 'HEAD'].includes(method) ? {} : { 'Content-Type': 'application/json' }), ...headers },
  ...(['GET', 'HEAD'].includes(method) ? {} : { body: raw ?? JSON.stringify(value) }),
});
async function body(response, status) {
  assert.equal(response.status, status, response.status === status ? undefined : await response.clone().text());
  assert.equal(response.headers.get('Cache-Control'), 'private, no-store'); assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.equal(response.headers.get('Referrer-Policy'), 'no-referrer'); assert.match(response.headers.get('Content-Type'), /^application\/json/);
  const raw = await response.text(); assert(Buffer.byteLength(raw) <= (status < 400 ? 32768 : 1024)); return JSON.parse(raw);
}
async function failure(response, status, code) { const value = await body(response, status); assert.equal(value.error.code, code); return value; }
const domain = db => Object.fromEntries(db.raw.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'album_%' ORDER BY name").all()
  .map(({ name }) => [name, db.raw.prepare('SELECT * FROM ' + name + ' ORDER BY rowid').all()]));
async function fixture(t) {
  const f = await titleFixture(t, { materialized: false });
  await f.db.batch([
    f.db.prepare("INSERT INTO fga_users VALUES('foreign-user')"),
    f.db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id,pending_version_id) VALUES('routed','user','lrc_plugin','active',1,'routed-version','pending-version'),('foreign','foreign-user','lrc_plugin','active',1,'foreign-version',NULL)"),
    f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('routed-version','routed',?,'current',1),('foreign-version','foreign',?,'current',1)").bind(await credentialDigest(CODE), await credentialDigest(FOREIGN)),
    f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending-version','routed',?,'pending_rotation',2,${NOW_US_SQL}+600000000)`).bind(await credentialDigest(PENDING)),
  ]);
  f.env = { DB: f.db, FGA_ALBUM_LOCAL_REMOVAL_ENABLED: '1', FGA_ALBUM_TITLE_ENABLED: '1', FGA_ALBUM_CREATE_REPAIR_ENABLED: '1' };
  f.worker = createWorker(() => assert.fail('local lifecycle must never contact a provider'));
  f.call = (path, value, options) => f.worker.fetch(request(path, value, options), f.env);
  return f;
}

test('actual worker removal routes retain exact registry authentication and default-off gates', async t => {
  const f = await fixture(t), before = domain(f.db);
  for (const [path, input] of [[albumPath(f.bindingId), albumInput(1)], [photoPath(f.bindingId), photoInput()]]) {
    const route = ROUTES.find(route => route.pathPattern === path.replace(f.bindingId, '{bindingId}').replace('primary-photo', '{photoBindingId}'));
    assert(route); assert.equal(route.auth, 'installation_bearer'); assert.equal(route.allowPending, false);
    const missing = await f.call(path, input, { credential: null }); assert.equal(missing.status, 401); assert.equal(await missing.text(), '');
    assert.equal(missing.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
    const pending = await f.call(path, input, { credential: PENDING }); assert.equal(pending.status, 403); assert.match(pending.headers.get('WWW-Authenticate'), /insufficient_scope/);
    await failure(await f.call(path, input, { credential: FOREIGN }), 404, 'resource_not_found');
    await failure(await f.worker.fetch(request(path, input), { ...f.env, FGA_ALBUM_LOCAL_REMOVAL_ENABLED: '0' }), 503, 'service_unavailable');
    const browserOnly = await f.call(path, input, { credential: null, headers: { Cookie: '__Host-fga_admin=' + 'A'.repeat(43) } }); assert.equal(browserOnly.status, 401);
  }
  assert.deepEqual(domain(f.db), before);
});

test('actual worker framing, absent resources and stale fences preserve all domain state', async t => {
  const f = await fixture(t), before = domain(f.db);
  for (const [path, input, options] of [[albumPath(f.bindingId) + '?x=1', albumInput(1), {}],
    [photoPath(f.bindingId), { ...photoInput(), extra: true }, {}],
    [albumPath(f.bindingId), albumInput(1), { headers: { 'Content-Type': 'text/plain' } }],
    [albumPath(f.bindingId), albumInput(1), { raw: '{"schemaVersion":1,"schemaVersion":1}' }],
    [photoPath(f.bindingId), photoInput(), { raw: Uint8Array.of(0xff) }],
    [albumPath(f.bindingId), albumInput(1), { raw: ' '.repeat(4097) }]])
    await failure(await f.call(path, input, options), 400, 'invalid_request');
  await failure(await f.call(albumPath(ABSENT), albumInput(1)), 404, 'resource_not_found');
  await failure(await f.call(photoPath(f.bindingId, 'absent-photo'), photoInput()), 404, 'resource_not_found');
  await failure(await f.call(photoPath(f.bindingId), photoInput(2, 2)), 409, 'stale_binding_revision');
  await failure(await f.call(photoPath(f.bindingId), photoInput(1, 2)), 409, 'stale_obligation_revision');
  assert.deepEqual(domain(f.db), before);
});

test('actual worker photo and album receipts preserve immutable acceptance facts and replay with current state', async t => {
  const f = await fixture(t);
  const target = photoPath(f.bindingId), acceptedResponse = await f.call(target, photoInput());
  assert.equal(acceptedResponse.headers.get('Location'), target); const pair = await body(acceptedResponse, 201);
  assert.equal(pair.localRelationship, 'archived'); assert.equal(pair.obligation.obligationRevision, 2); assert.equal(pair.acceptedBindingRevision, 2);
  const pairState = domain(f.db); const pairReplayResponse = await f.call(target, photoInput(88, 99));
  assert.equal(pairReplayResponse.headers.get('Location'), null); assert.deepEqual(await body(pairReplayResponse, 200), pair); assert.deepEqual(domain(f.db), pairState);
  const albumTarget = albumPath(f.bindingId), archivedResponse = await f.call(albumTarget, albumInput(2));
  assert.equal(archivedResponse.headers.get('Location'), albumTarget); const album = await body(archivedResponse, 201);
  assert.equal(album.acceptedBindingRevision, 3); assert.equal(album.localLifecycle, 'local_collection_removed_remote_preserved');
  assert.equal(album.current.title.state, 'local_removed'); assert.equal(album.current.binding.titleRevision, 1);
  assert.equal(album.current.binding.firstPhotoBindingId, 'primary-photo'); assert.equal(album.current.binding.flickrPhotosetId, null);
  f.db.raw.exec("UPDATE flickr_links SET state='paused' WHERE user_id='user'");
  const archivedState = domain(f.db), replayResponse = await f.call(albumTarget, albumInput(1));
  assert.equal(replayResponse.headers.get('Location'), null); assert.deepEqual(await body(replayResponse, 200), album);
  const pairAgain = await body(await f.call(target, photoInput()), 200);
  assert.deepEqual(pairAgain.obligation, pair.obligation); assert.equal(pairAgain.archivedAt, pair.archivedAt);
  assert.equal(pairAgain.acceptedBindingRevision, pair.acceptedBindingRevision); assert.deepEqual(pairAgain.current, album.current);
  const lifecycle = await body(await f.call(`/api/v001/album-bindings/${f.bindingId}/lifecycle`, undefined, { method: 'GET' }), 200);
  assert.deepEqual(lifecycle, album.current); assert.deepEqual(domain(f.db), archivedState);
});

test('new local archive is allowed while Flickr authority is paused and never makes provider calls', async t => {
  const f = await fixture(t); f.db.raw.exec("UPDATE flickr_links SET state='paused' WHERE user_id='user'");
  const archived = await body(await f.call(albumPath(f.bindingId), albumInput(1)), 201);
  assert.equal(archived.localLifecycle, 'local_collection_removed_remote_preserved');
  const pair = await body(await f.call(photoPath(f.bindingId), photoInput()), 200);
  assert.equal(pair.acceptedBindingRevision, archived.acceptedBindingRevision);
});

test('removed unknown create remains discoverable and only browser session with exact Origin and CSRF can repair', async t => {
  const f = await fixture(t), claim = await claimAlbumMaterialization(f.db, f.bindingId); assert(claim);
  const marked = await markAlbumCreateDispatch(f.db, claim, ['preexisting']); assert(marked);
  assert.equal(await unknownAlbumMaterialization(f.db, marked), true);
  const pendingLifecycle = await body(await f.call(`/api/v001/album-bindings/${f.bindingId}/lifecycle`, undefined, { method: 'GET' }), 200);
  const attempt = pendingLifecycle.unresolvedCreateAttemptId; assert(attempt);
  const removal = { ...albumInput(pendingLifecycle.binding.bindingRevision), acknowledgedCreateAttemptId: attempt };
  const before = domain(f.db);
  await failure(await f.call(albumPath(f.bindingId), { ...removal, acknowledgedCreateAttemptId: null }), 409, 'removal_acknowledgement_required');
  assert.deepEqual(domain(f.db), before);
  const receipt = await body(await f.call(albumPath(f.bindingId), removal), 201);
  assert.equal(receipt.repairHandoff.destination, 'administrative_album_create_repair'); assert.equal(receipt.repairHandoff.createAttemptId, attempt);
  assert.equal(receipt.repairHandoff.acknowledgedAt, receipt.archivedAt);
  await failure(await f.call(albumPath(f.bindingId), { ...removal, acknowledgedCreateAttemptId: null }), 409, 'removal_acknowledgement_conflict');
  const token = 'A'.repeat(43), csrf = 'c'.repeat(43), ownerSub = 'synthetic-google-sub';
  const adminAuth = { kind: 'admin', sessionId: 'repair-session', tokenDigest: digest(token), ownerSub };
  await f.db.batch([
    f.db.prepare("INSERT INTO admin_principals(user_id,google_issuer,google_sub) VALUES('user','https://accounts.google.com',?)").bind(ownerSub),
    f.db.prepare(`INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id)
      VALUES(?,?,'user',?,${NOW_US_SQL}-600000000,${NOW_US_SQL}-600000000,${NOW_US_SQL}+85800000000,${NOW_US_SQL},'synthetic-correlation')`)
      .bind(adminAuth.sessionId, adminAuth.tokenDigest, csrf),
  ]);
  let readCount = 0;
  const reader = context => createSyntheticAlbumCreateRepairReader({ ...context, createAttemptId: context.attemptId }, {
    observedAt: () => new Date().toISOString().replace('Z', '000Z'),
    assertCurrent: () => assertAlbumRepairContext(f.db, adminAuth, context), reserveReads: async () => {},
    sign(method, params) { const url = new URL('https://www.flickr.com/services/rest/'); url.searchParams.set('method', method); url.searchParams.set('format', 'json'); url.searchParams.set('nojsoncallback', '1');
      for (const [key, value] of Object.entries(params)) url.searchParams.set(key, String(value)); return new Request(url, { redirect: 'manual' }); },
    async fetcher(request) { assert.equal(request.method, 'GET'); readCount++; const url = new URL(request.url);
      if (url.searchParams.get('method') === 'flickr.photos.getAllContexts') return Response.json({ stat: 'ok', set: [{ id: 'selected', title: 'Synthetic selected album' }], pool: [] });
      assert.equal(url.searchParams.get('method'), 'flickr.photosets.getInfo');
      return Response.json({ stat: 'ok', photoset: { id: 'selected', owner: 'owner', primary: 'primary-remote', title: { _content: 'Synthetic selected album' } } }); },
  });
  const worker = createWorker(() => assert.fail('unexpected real provider request'), { reader });
  const env = { ...f.env, FGA_ADMIN_ENABLED: '1', GOOGLE_OWNER_SUB: ownerSub, GOOGLE_CLIENT_ID: 'synthetic-client' };
  const adminCall = (path, value, options = {}) => worker.fetch(request('/api/v001/admin/' + path, value, {
    credential: null, method: value === undefined ? 'GET' : 'PUT', ...options,
    headers: { Cookie: '__Host-fga_admin=' + token, ...options.headers },
  }), env);
  const repairs = await body(await adminCall('album-create-repairs?page=1&page_size=20'), 200);
  const found = repairs.repairs.find(value => value.fgaAlbumBindingId === f.bindingId); assert(found);
  assert.equal(found.createAttemptId, attempt); assert.equal(found.localLifecycle, 'local_collection_removed_remote_preserved');
  const status = await body(await adminCall(`album-bindings/${f.bindingId}/status`), 200);
  assert.equal(status.materialization.repairSurface, 'admin_only'); assert.equal(status.materialization.createAttemptId, attempt);
  const selection = { schemaVersion: 1, expectedBindingRevision: status.binding.bindingRevision, createAttemptId: attempt, selectedPhotosetId: 'selected' };
  const repairPath = `album-bindings/${f.bindingId}/create-repair-resolution`;
  const stateBeforeRepair = domain(f.db);
  await failure(await f.call('/api/v001/' + repairPath, selection), 409, 'administrative_repair_required');
  const bearerOnly = await worker.fetch(request('/api/v001/admin/' + repairPath, selection), env);
  assert.equal(bearerOnly.status, 401); assert.equal(bearerOnly.headers.get('WWW-Authenticate'), null);
  for (const headers of [{}, { Origin: ORIGIN }, { Origin: 'https://evil.example', 'X-CSRF-Token': csrf }, { Origin: ORIGIN, 'X-CSRF-Token': 'wrong' }]) {
    const response = await adminCall(repairPath, selection, { headers }); assert.equal(response.status, 403);
    assert.equal((await response.json()).error.code, 'forbidden');
  }
  assert.deepEqual(domain(f.db), stateBeforeRepair); assert.equal(readCount, 0);
  const resolved = await body(await adminCall(repairPath, selection, { headers: { Origin: ORIGIN, 'X-CSRF-Token': csrf } }), 200);
  assert.equal(resolved.binding.flickrPhotosetId, 'selected'); assert.equal(resolved.localLifecycle, 'local_collection_removed_remote_preserved'); assert(readCount > 0);
  const repairedState = domain(f.db), replay = await body(await f.call(albumPath(f.bindingId), removal), 200);
  assert.equal(replay.archivedAt, receipt.archivedAt); assert.equal(replay.acceptedBindingRevision, receipt.acceptedBindingRevision);
  assert.deepEqual(replay.repairHandoff, receipt.repairHandoff); assert.equal(replay.current.unresolvedCreateAttemptId, null);
  assert.equal(replay.current.binding.flickrPhotosetId, 'selected'); assert.equal(replay.current.title.state, 'local_removed');
  assert.deepEqual(domain(f.db), repairedState);
});

test('exact 4 KiB UTF-8 body is accepted and retained receipt still requires current credentials', async t => {
  const f = await fixture(t), target = albumPath(f.bindingId), raw = JSON.stringify(albumInput(1));
  const padded = raw + ' '.repeat(4096 - Buffer.byteLength(raw)); assert.equal(Buffer.byteLength(padded), 4096);
  const response = await f.call(target, albumInput(1), { raw: padded }); await body(response, 201);
  assert.equal(response.headers.get('Location'), target); assert.equal(response.headers.get('Refresh'), null);
  const archived = domain(f.db);
  f.db.raw.exec("BEGIN; UPDATE installation_credential_versions SET state='revoked' WHERE installation_id='routed'; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='routed'; COMMIT");
  const refused = await f.call(target, albumInput(1)); assert.equal(refused.status, 401); assert.match(refused.headers.get('WWW-Authenticate'), /invalid_token/);
  assert.deepEqual(domain(f.db), archived);
});

test('actual Worker accepts canonical single-segment opaque photo IDs with colon and at-sign', async t => {
  const f = await fixture(t), photo = '0007:photo@A._-';
  await f.db.batch([
    f.db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES(?,'user','opaque-remote','owner',1,1,'existing_public',1)").bind(photo),
    f.db.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('opaque-proof',?,1,'existing_public_verified')").bind(photo),
  ]);
  const associated = await f.associate(photo, 1), target = photoPath(f.bindingId, photo);
  const accepted = await body(await f.call(target, photoInput(associated.binding.bindingRevision, associated.obligation.obligationRevision)), 201);
  assert.equal(accepted.obligation.fgaPhotoBindingId, photo);
  const snapshot = domain(f.db), replay = await body(await f.call(target, photoInput()), 200);
  assert.equal(replay.obligation.fgaPhotoBindingId, photo); assert.deepEqual(domain(f.db), snapshot);
  for (const alternate of [target.replace('%3A', '%3a'), target.replace('%40', '@'), target.replace('%3A', ':'), target.replace('%40', '%2540'), target.replace('/0007', '/%30007'), target.replace(f.bindingId, '%'+f.bindingId.charCodeAt(0).toString(16)+f.bindingId.slice(1))]) {
    const response = await f.call(alternate, photoInput()); assert(response.status === 400 || response.status === 404);
  }
  assert.deepEqual(domain(f.db), snapshot);
});
