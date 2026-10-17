import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { legacyAlbumStore, migrateAlbumObligations } from './album_migration_fixture.mjs';
import { albumBindingRequest } from '../src/album_bindings.ts';
const obligations = () => import('../src/album_obligations.ts');
import { createWorker, ROUTES } from '../src/worker.ts';
import { credentialDigest, NOW_US_SQL } from '../src/installations.ts';

const CODE = Array(13).fill('0000').join('-');
const PENDING = Array(12).fill('0000').concat('000G').join('-');
const SERVICE = '11111111-1111-4111-8111-111111111111';
const FOREIGN_SERVICE = '33333333-3333-4333-8333-333333333333';
const ABSENT = '44444444-4444-4444-8444-444444444444';
const ensurePath = (service = SERVICE, local = 'Album:007') => `/api/v001/publish-services/${service}/album-bindings/${encodeURIComponent(local)}`;
const associationPath = (binding, photo = 'later-photo') => `/api/v001/album-bindings/${binding}/photo-associations/${encodeURIComponent(photo)}`;
const associate = (bindingRevision = 1, verificationRevision = 1) => ({ schemaVersion: 1, expectedBindingRevision: bindingRevision, expectedVerificationRevision: verificationRevision });
const ensure = (photo = 'primary-photo') => ({ schemaVersion: 1, desiredTitle: 'Synthetic album', candidate: { fgaPhotoBindingId: photo, expectedVerificationRevision: 1 } });
const jsonRequest = (target, value, { method = 'PUT', headers = {}, raw } = {}) => new Request('https://flickrgroupaddr.com' + target, {
  method, headers: { 'Content-Type': 'application/json', ...headers }, ...(['GET', 'HEAD'].includes(method) ? {} : { body: raw ?? JSON.stringify(value) }),
});

async function fixture(t, db = sqlStore()) {
  t.after(() => db.raw.close());
  const auth = { installationId: 'install', credentialDigest: await credentialDigest(CODE) };
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user'),('foreign')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version'),('second','user','lrc_plugin','active',1,'second-version'),('foreign','foreign','lrc_plugin','active',1,'foreign-version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1),('second-version','second',?,'current',1),('foreign-version','foreign',?,'current',1)").bind(auth.credentialDigest, 'e'.repeat(64), 'f'.repeat(64)),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked'),('foreign','foreign-owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('user','gen',1,'owner','write',NULL),('foreign','foreign-gen',1,'foreign-owner','write',NULL)"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1),('foreign','linked','available','write',1)"),
    db.prepare("INSERT INTO publish_service_identities(service_id,user_id,issuing_installation_id,link_revision,owner_nsid) VALUES(?,'user','install',1,'owner'),(?,'foreign','foreign',1,'foreign-owner')").bind(SERVICE, FOREIGN_SERVICE),
    db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('upload-auth','install','user',1,'owner',1),('ambiguous-upload','install','user',2,'owner',1),('failed-upload','install','user',3,'owner',1)"),
    db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES('primary-photo','user','primary-remote','owner',1,1,'upload',1),('later-photo','user','later-remote','owner',1,1,'existing_public',1),('third-photo','user','third-remote','owner',1,1,'existing_public',1),('foreign-photo','foreign','foreign-remote','foreign-owner',1,1,'existing_public',1),('bare-photo','user','bare-remote','owner',1,1,'existing_public',1),('wrong-owner','user','wrong-remote','other-owner',1,1,'existing_public',1),('old-link','user','old-remote','owner',2,1,'existing_public',1)"),
    db.prepare("UPDATE upload_authorizations SET photo_id='primary-remote' WHERE authorization_id='upload-auth'"),
    db.prepare("INSERT INTO upload_photo_binding_events(authorization_id,binding_id,link_revision,verification_revision,observed_public,verified_at_us) VALUES('upload-auth','primary-photo',1,1,0,1)"),
    db.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('later-proof','later-photo',1,'existing_public_verified'),('third-proof','third-photo',1,'existing_public_verified'),('foreign-proof','foreign-photo',1,'existing_public_verified'),('wrong-proof','wrong-owner',1,'existing_public_verified'),('old-proof','old-link',1,'existing_public_verified')"),
  ]);
  const env = { DB: db, FGA_ALBUM_BINDINGS_ENABLED: '1', FGA_ALBUM_OBLIGATIONS_ENABLED: '1', FGA_READ_ENABLED: '0', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0' };
  const worker = createWorker(async () => assert.fail('album obligation admission must never dispatch external HTTP'));
  const initial = await albumBindingRequest(env, auth, jsonRequest(ensurePath(), ensure()), SERVICE, 'Album:007');
  assert.equal(initial.status, 201); const first = await initial.json(), binding = first.binding.fgaAlbumBindingId;
  return { db, auth, env, first, binding,
    call: async (value = associate(), options = {}, presented = auth) => (await obligations()).albumObligationRequest(env, presented,
      jsonRequest(options.target ?? associationPath(options.binding ?? binding, options.photo ?? 'later-photo'), value, options),
      options.binding ?? binding, options.photo ?? 'later-photo'),
    ensure: (photo = 'primary-photo', local = 'Album:007') => albumBindingRequest(env, auth, jsonRequest(ensurePath(SERVICE, local), ensure(photo)), SERVICE, local),
    routed: (options = {}) => worker.fetch(jsonRequest(options.target ?? associationPath(options.binding ?? binding, options.photo ?? 'later-photo'), options.value ?? associate(), {
      ...options, headers: { ...(options.credential === null ? {} : { Authorization: 'Bearer ' + (options.credential ?? CODE) }), ...options.headers },
    }), env),
  };
}
const albumState = db => Object.fromEntries(['album_bindings', 'album_photo_obligations', 'album_binding_events', 'album_obligation_events', 'transaction_guards']
  .map(table => [table, db.raw.prepare(`SELECT * FROM ${table} ORDER BY rowid`).all()]));
const row = (f, photo = 'later-photo') => f.db.raw.prepare('SELECT * FROM album_photo_obligations WHERE album_binding_id=? AND photo_binding_id=?').get(f.binding, photo);
async function error(response, status, code) {
  assert.equal(response.status, status);
  for (const [name, value] of Object.entries({ 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' })) assert.equal(response.headers.get(name), value);
  const body = await response.json(); assert.equal(body.schemaVersion, 1); assert.equal(body.error.code, code);
  assert.equal(body.error.retryable, status === 503 || status === 429);
  assert.match(body.error.correlationId, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  if (status === 503) assert.equal(response.headers.get('Retry-After'), '5');
  assert(!JSON.stringify(body).includes('synthetic_private')); return body;
}
function refresh(f, photo, revision = 2) {
  f.db.raw.prepare('UPDATE photo_bindings SET verification_revision=? WHERE binding_id=?').run(revision, photo);
  f.db.raw.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES(?,?,?,'existing_public_verified')").run(crypto.randomUUID(), photo, revision);
}

test('additional handoff uses hosted identity, advances binding once and preserves the primary receipt', async t => {
  const f = await fixture(t), primary = row(f, 'primary-photo');
  const response = await f.call(); assert.equal(response.status, 201); assert.equal(response.headers.get('Location'), null);
  const body = await response.json();
  assert.deepEqual(Object.keys(body).sort(), ['binding', 'obligation', 'schemaVersion']);
  assert.deepEqual(Object.keys(body.obligation).sort(), ['fgaAlbumBindingId', 'fgaAlbumObligationId', 'fgaPhotoBindingId', 'obligationRevision']);
  assert.deepEqual(body.binding, { ...f.first.binding, bindingRevision: 2 });
  assert.equal(body.obligation.fgaAlbumBindingId, f.binding); assert.equal(body.obligation.fgaPhotoBindingId, 'later-photo'); assert.equal(body.obligation.obligationRevision, 1);
  assert.notEqual(body.obligation.fgaAlbumObligationId, f.first.obligation.fgaAlbumObligationId);
  assert.equal(row(f).photo_id, 'later-remote'); assert.equal(row(f).state, 'waiting_for_album'); assert.equal(row(f).local_relationship, 'active');
  assert.deepEqual(row(f, 'primary-photo'), primary); assert.equal(primary.state, 'waiting_for_album');
  assert.equal(albumState(f.db).album_binding_events.length, 2); assert.equal(albumState(f.db).transaction_guards.length, 0);
  for (const table of ['submission_intents', 'group_partitions']) assert.equal(f.db.raw.prepare(`SELECT count(*) n FROM ${table}`).get().n, 0);
  const before = albumState(f.db), primaryReplay = await f.ensure(); assert.equal(primaryReplay.status, 200);
  const receipt = await primaryReplay.json(); assert.deepEqual(receipt.obligation, f.first.obligation); assert.equal(receipt.binding.bindingRevision, 2);
  assert.deepEqual(albumState(f.db), before);
});

test('matching natural-key replay ignores stale submitted revisions and changes no receipt, title or audit', async t => {
  const f = await fixture(t), created = await (await f.call()).json(); refresh(f, 'later-photo');
  const before = albumState(f.db), response = await f.call(associate(1, 1)); assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), created); assert.deepEqual(albumState(f.db), before);
  const primary = await f.call(associate(1, 1), { photo: 'primary-photo' }); assert.equal(primary.status, 200);
  assert.deepEqual((await primary.json()).obligation, f.first.obligation); assert.deepEqual(albumState(f.db), before);
});

test('new association uses current binding and photo revisions; stale failures allocate nothing', async t => {
  const f = await fixture(t); refresh(f, 'later-photo'); const before = albumState(f.db);
  await error(await f.call(associate(1, 1)), 409, 'stale_photo_revision'); assert.deepEqual(albumState(f.db), before);
  const first = await f.call(associate(1, 2)); assert.equal(first.status, 201);
  const admitted = albumState(f.db);
  await error(await f.call(associate(1, 1), { photo: 'third-photo' }), 409, 'stale_binding_revision'); assert.deepEqual(albumState(f.db), admitted);
  const reconciled = await f.ensure(); assert.equal(reconciled.status, 200); assert.equal((await reconciled.json()).binding.bindingRevision, 2);
  const next = await f.call(associate(2, 1), { photo: 'third-photo' }); assert.equal(next.status, 201); assert.equal((await next.json()).binding.bindingRevision, 3);
  assert.equal(albumState(f.db).album_photo_obligations.length, 3); assert.equal(albumState(f.db).album_binding_events.length, 3);
});

test('unknown, foreign, unproven and upload-ambiguous photos retain no obligation or acceptance event', async t => {
  const f = await fixture(t), before = albumState(f.db);
  for (const [photo, status, code] of [['absent-photo', 404, 'resource_not_found'], ['foreign-photo', 404, 'resource_not_found'],
    ['ambiguous-upload', 404, 'resource_not_found'], ['failed-upload', 404, 'resource_not_found'], ['bare-photo', 409, 'photo_not_ready'],
    ['wrong-owner', 409, 'photo_not_ready'], ['old-link', 409, 'photo_not_ready']]) {
    await error(await f.call(undefined, { photo }), status, code); assert.deepEqual(albumState(f.db), before);
  }
  for (const [id, remote, timestamp] of [['0', 'zero-binding-remote', 1], ['zero-photo', '0', 1], ['future-photo', 'future-remote', 9000000000000000]]) {
    f.db.raw.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES(?,'user',?,'owner',1,1,'existing_public',?)").run(id, remote, timestamp);
    f.db.raw.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES(?,?,1,'existing_public_verified')").run(crypto.randomUUID(), id);
    await error(await f.call(undefined, { photo: id }), 409, 'photo_not_ready'); assert.deepEqual(albumState(f.db), before);
  }
});

test('current same-user installations may associate; absent and foreign bindings share one refusal', async t => {
  const f = await fixture(t);
  assert.equal((await f.call(undefined, {}, { installationId: 'second', credentialDigest: 'e'.repeat(64) })).status, 201);
  const foreign = await albumBindingRequest(f.env, { installationId: 'foreign', credentialDigest: 'f'.repeat(64) },
    jsonRequest(ensurePath(FOREIGN_SERVICE, 'Foreign'), ensure('foreign-photo')), FOREIGN_SERVICE, 'Foreign');
  assert.equal(foreign.status, 201); const foreignBinding = (await foreign.json()).binding.fgaAlbumBindingId, before = albumState(f.db);
  for (const binding of [ABSENT, foreignBinding]) await error(await f.call(undefined, { binding }), 404, 'resource_not_found');
  await error(await f.call(undefined, {}, { installationId: 'foreign', credentialDigest: 'f'.repeat(64) }), 404, 'resource_not_found');
  assert.deepEqual(albumState(f.db), before);
});

test('one photo may have separate explicit obligations in two albums without altering the first', async t => {
  const f = await fixture(t); assert.equal((await f.call()).status, 201);
  const first = row(f), other = await f.ensure('third-photo', 'SecondAlbum'); assert.equal(other.status, 201);
  const binding = (await other.json()).binding.fgaAlbumBindingId;
  const response = await f.call(associate(), { binding }); assert.equal(response.status, 201);
  assert.notEqual((await response.json()).obligation.fgaAlbumObligationId, first.obligation_id); assert.deepEqual(row(f), first);
  assert.equal(f.db.raw.prepare("SELECT count(*) n FROM album_photo_obligations WHERE photo_binding_id='later-photo'").get().n, 2);
});

test('same-pair concurrent handoffs converge; distinct new photos must reconcile the winning revision', async t => {
  for (const same of [true, false]) {
    const f = await fixture(t), batch = f.db.batch.bind(f.db); let firstReached, releaseFirst;
    const reached = new Promise(resolve => firstReached = resolve), release = new Promise(resolve => releaseFirst = resolve);
    let calls = 0; f.db.batch = async statements => { if (++calls === 1) { firstReached(); await release; } return batch(statements); };
    const delayedRequest = f.call(); await reached;
    const winner = await f.call(associate(), { photo: same ? 'later-photo' : 'third-photo' }); assert.equal(winner.status, 201);
    releaseFirst(); const delayed = await delayedRequest;
    if (same) { assert.equal(delayed.status, 200); assert.deepEqual(await delayed.json(), await winner.json()); }
    else {
      await error(delayed, 409, 'stale_binding_revision'); assert.equal(row(f), undefined);
      assert.equal((await f.call(associate(2))).status, 201);
    }
    const state = albumState(f.db); assert.equal(state.album_photo_obligations.length, same ? 2 : 3);
    assert.equal(state.album_bindings[0].binding_revision, same ? 2 : 3); assert.equal(state.album_binding_events.length, same ? 2 : 3);
  }
});

const ROTATE = "BEGIN; UPDATE installation_credential_versions SET state='replaced' WHERE version_id='version'; INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('replacement','install','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','current',2); UPDATE installations SET current_version_id='replacement',revision=revision+1 WHERE installation_id='install'; COMMIT";
test('admission rechecks credential, installation, link, pause, owner and exact proof at the commit boundary', async t => {
  for (const [mutation, code] of [[ROTATE, 'invalid_token'],
    ["BEGIN; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='install'; UPDATE installation_credential_versions SET state='revoked' WHERE installation_id='install' AND state='current'; COMMIT", 'invalid_token'],
    ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_native_credentials SET link_revision=2 WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_native_credentials SET operation_id='pause' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_connection_state SET local_state='retirement_pending' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_native_credentials SET verified_owner_nsid='other' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE photo_bindings SET verification_revision=2 WHERE binding_id='later-photo'; INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('new-proof','later-photo',2,'existing_public_verified')", 'stale_photo_revision']]) {
    const f = await fixture(t), before = albumState(f.db), batch = f.db.batch.bind(f.db); let changed = false;
    f.db.batch = async statements => { if (!changed) { changed = true; f.db.raw.exec(mutation); } return batch(statements); };
    await error(await f.call(), code === 'invalid_token' ? 401 : 409, code); assert.deepEqual(albumState(f.db), before);
  }
});

test('matching receipt replay still requires current authentication, service snapshot and eligible exact photo proof', async t => {
  for (const [mutation, code] of [[ROTATE, 'invalid_token'],
    ["UPDATE flickr_links SET state='paused' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'; UPDATE flickr_native_credentials SET link_revision=2 WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE photo_bindings SET verification_revision=2 WHERE binding_id='later-photo'", 'photo_not_ready']]) {
    const f = await fixture(t); assert.equal((await f.call()).status, 201); const before = albumState(f.db); f.db.raw.exec(mutation);
    await error(await f.call(), code === 'invalid_token' ? 401 : 409, code); assert.deepEqual(albumState(f.db), before);
  }
});

test('every injected batch-step or audit-trigger failure rolls back the new obligation and binding increment', async t => {
  const probe = await fixture(t), original = probe.db.batch.bind(probe.db); let length;
  probe.db.batch = statements => { length = statements.length; return original(statements); };
  assert.equal((await probe.call()).status, 201); assert(length > 0);
  for (let index = 0; index < length; index++) {
    const f = await fixture(t), before = albumState(f.db); f.db.fault = index;
    await error(await f.call(), 503, 'service_unavailable'); assert.deepEqual(albumState(f.db), before);
  }
  for (const table of ['album_photo_obligations', 'album_binding_events', 'album_obligation_events']) {
    const f = await fixture(t), before = albumState(f.db);
    f.db.raw.exec(`CREATE TRIGGER synthetic_test_abort BEFORE INSERT ON ${table} BEGIN SELECT RAISE(ABORT,'synthetic_private_failure'); END`);
    await error(await f.call(), 503, 'service_unavailable'); assert.deepEqual(albumState(f.db), before);
  }
});

test('a lost commit acknowledgement recovers the same receipt without repeating admission or external dispatch', async t => {
  const f = await fixture(t), batch = f.db.batch.bind(f.db); let lost = true;
  f.db.batch = async statements => { const result = await batch(statements); if (lost) { lost = false; throw new Error('synthetic_private_lost_ack'); } return result; };
  await error(await f.call(), 503, 'service_unavailable'); const committed = albumState(f.db);
  assert.equal(committed.album_photo_obligations.length, 2); assert.equal(committed.album_binding_events.length, 2);
  const retry = await f.call(); assert.equal(retry.status, 200); assert.equal((await retry.json()).obligation.fgaAlbumObligationId, row(f).obligation_id);
  assert.deepEqual(albumState(f.db), committed);
});

test('database authority failure stays sanitized unavailable and cannot become an absent resource', async t => {
  const f = await fixture(t), before = albumState(f.db), prepare = f.db.prepare.bind(f.db);
  f.db.prepare = () => { throw new Error('synthetic_private_authority_failure'); };
  await error(await f.call(), 503, 'service_unavailable'); f.db.prepare = prepare; assert.deepEqual(albumState(f.db), before);
});

test('strict closed envelopes reject duplicates, rounded integer values, untrusted identifiers and bad encodings before database access', async t => {
  const f = await fixture(t), before = albumState(f.db), prepare = f.db.prepare.bind(f.db);
  f.db.prepare = () => assert.fail('invalid association envelope must not query authority'); const valid = JSON.stringify(associate());
  for (const raw of ['{', valid.replace('"schemaVersion":1', '"schemaVersion":1,"schema\\u0056ersion":1'),
    valid.replace('"expectedBindingRevision":1', '"expectedBindingRevision":1.00000000000000000001'),
    valid.replace('"expectedVerificationRevision":1', '"expectedVerificationRevision":1.00000000000000000001'),
    JSON.stringify({ ...associate(), flickrPhotoId: 'later-remote' }), JSON.stringify({ ...associate(), ownerNsid: 'owner' }),
    ...[0, -1, 1.5, 9007199254740992, null, '1'].map(expectedBindingRevision => JSON.stringify({ ...associate(), expectedBindingRevision })),
    ...[0, null, 1.5, '1'].map(expectedVerificationRevision => JSON.stringify({ ...associate(), expectedVerificationRevision })),
    ...[null, [], { ...associate(), schemaVersion: 2 }].map(JSON.stringify), ' '.repeat(4096) + valid])
    await error(await f.call(undefined, { raw }), 400, 'invalid_request');
  for (const headers of [{ 'Content-Type': 'text/plain' }, { 'Content-Type': 'application/json;charset=iso-8859-1' }, { 'Content-Encoding': 'gzip' }, { 'Content-Length': '4097' }, { 'Content-Length': '0' }, { 'Content-Length': '1' }, { 'Content-Length': '4096' }, { 'Content-Length': '0001' }, { 'Content-Length': '+1' }, { 'Transfer-Encoding': 'chunked' }])
    await error(await f.call(undefined, { headers }), 400, 'invalid_request');
  await error(await f.call(undefined, { raw: new Uint8Array([0xc3, 0x28]) }), 400, 'invalid_request');
  await error(await f.call(undefined, { raw: '\ufeff' + valid }), 400, 'invalid_request');
  f.db.prepare = prepare; assert.deepEqual(albumState(f.db), before);
});

test('canonical path validation rejects aliases and query parameters while exact integer syntax remains accepted', async t => {
  const f = await fixture(t), before = albumState(f.db);
  for (const target of [associationPath(f.binding) + '?x=1', associationPath(f.binding).replace('later-photo', '%6Cater-photo'),
    associationPath(f.binding).replace('later-photo', 'later%252Dphoto'), associationPath(f.binding).replace(f.binding, ABSENT)])
    await error(await f.call(undefined, { target }), 400, 'invalid_request');
  for (const photo of ['', '..', 'bad/id', 'bad id', 'a'.repeat(129)]) await error(await f.call(undefined, { photo }), 400, 'invalid_request');
  assert.deepEqual(albumState(f.db), before);
  const raw = JSON.stringify(associate()).replace('"schemaVersion":1', '"schema\\u0056ersion":1.0e0').replace('"expectedBindingRevision":1', '"expectedBindingRevision":10e-1');
  assert.equal((await f.call(undefined, { raw })).status, 201);
});

test('production route is default-disabled and authenticates each call before resource lookup', async t => {
  const { ALBUM_OBLIGATIONS_RELEASE_METADATA, ALBUM_OBLIGATIONS_ROUTES } = await obligations();
  const f = await fixture(t);
  assert.equal(ALBUM_OBLIGATIONS_RELEASE_METADATA.defaultValue, '0'); assert.equal(ALBUM_OBLIGATIONS_RELEASE_METADATA.hostQualified, false);
  assert.equal(ALBUM_OBLIGATIONS_ROUTES.length, 1); const route = ALBUM_OBLIGATIONS_ROUTES[0];
  assert.equal(route.method, 'PUT'); assert.equal(route.allowPending, false); assert(ROUTES.some(r => r.id === route.id));
  delete f.env.FGA_ALBUM_OBLIGATIONS_ENABLED; const prepare = f.db.prepare.bind(f.db); f.db.prepare = () => assert.fail('disabled route must not query');
  await error(await f.routed({ credential: null }), 503, 'service_unavailable'); f.db.prepare = prepare; f.env.FGA_ALBUM_OBLIGATIONS_ENABLED = '1';
  const missing = await f.routed({ credential: null }); assert.equal(missing.status, 401); assert.equal(await missing.text(), ''); assert.equal(missing.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
  await error(await f.routed({ credential: 'invalid' }), 401, 'invalid_token');
  await f.db.batch([
    f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install',?,'pending_rotation',2,${NOW_US_SQL}+300000000)`).bind(await credentialDigest(PENDING)),
    f.db.prepare("UPDATE installations SET pending_version_id='pending',revision=revision+1 WHERE installation_id='install'"),
  ]);
  const pending = await f.routed({ credential: PENDING }); await error(pending, 403, 'insufficient_scope'); assert.match(pending.headers.get('WWW-Authenticate'), /insufficient_scope/);
  assert.equal((await f.routed()).status, 201); assert.equal((await f.routed()).status, 200); assert.equal((await f.routed({ method: 'POST' })).status, 405);
});

test('committed photoset selects attachment-pending for later photos without changing the first receipt', async t => {
  const f = await fixture(t), primary = row(f, 'primary-photo');
  f.db.raw.prepare("UPDATE album_bindings SET flickr_photoset_id='retained-photoset',binding_revision=binding_revision+1 WHERE binding_id=?").run(f.binding);
  const response = await f.call(associate(2)); assert.equal(response.status, 201);
  const body = await response.json(); assert.equal(body.binding.flickrPhotosetId, 'retained-photoset'); assert.equal(body.binding.bindingRevision, 3);
  assert.equal(row(f).state, 'attachment_pending'); assert.deepEqual(row(f, 'primary-photo'), primary);
});

test('local collection removal archives retained primary/later obligations; replay never resurrects or admits new work', async t => {
  const f = await fixture(t); assert.equal((await f.call()).status, 201);
  const admitted = albumState(f.db);
  // Exercise accepted storage lifecycle semantics only; #0094 lifecycle HTTP remains unaccepted.
  f.db.raw.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?").run(f.binding);
  const archived = albumState(f.db); assert.equal(archived.album_bindings[0].binding_revision, 3);
  for (const obligation of archived.album_photo_obligations) {
    const original = admitted.album_photo_obligations.find(item => item.obligation_id === obligation.obligation_id);
    assert.equal(obligation.local_relationship, 'archived'); assert.equal(obligation.obligation_revision, original.obligation_revision + 1);
    assert.equal(obligation.state, original.state); assert.equal(obligation.photo_id, original.photo_id);
  }
  assert.equal(archived.album_photo_obligations.length, 2); assert.equal(archived.album_obligation_events.length, 4);
  for (const photo of ['primary-photo', 'later-photo']) {
    const response = await f.call(associate(1, 1), { photo }); assert.equal(response.status, 200);
    const receipt = await response.json(); assert.equal(receipt.obligation.fgaAlbumObligationId, row(f, photo).obligation_id);
    assert.equal(receipt.obligation.obligationRevision, 2); assert.equal(receipt.binding.bindingRevision, 3);
  }
  const primaryReplay = await f.ensure(); assert.equal(primaryReplay.status, 200); assert.equal((await primaryReplay.json()).obligation.obligationRevision, 2);
  await error(await f.call(associate(3), { photo: 'third-photo' }), 409, 'album_closed'); assert.deepEqual(albumState(f.db), archived);
  for (const sql of ["DELETE FROM album_photo_obligations", "DELETE FROM album_obligation_events", "UPDATE album_photo_obligations SET local_relationship='active',obligation_revision=obligation_revision+1",
    "UPDATE album_obligation_events SET local_relationship='active'", "INSERT OR REPLACE INTO album_photo_obligations SELECT * FROM album_photo_obligations",
    "INSERT OR REPLACE INTO album_obligation_events SELECT * FROM album_obligation_events"]) {
    assert.throws(() => f.db.raw.exec(sql), sql); assert.deepEqual(albumState(f.db), archived);
  }
});

test('ordinary SQL rejects mismatched owner/photo proofs, identity rewrites and unaudited binding increments', async t => {
  const f = await fixture(t); assert.equal((await f.call()).status, 201); const before = albumState(f.db), original = row(f);
  for (const sql of ["UPDATE album_photo_obligations SET photo_binding_id='third-photo',photo_id='third-remote'", "UPDATE album_photo_obligations SET obligation_revision=obligation_revision+1",
    "UPDATE album_photo_obligations SET local_relationship='archived',obligation_revision=obligation_revision+1", "UPDATE album_bindings SET binding_revision=binding_revision+1",
    "DELETE FROM album_photo_obligations", "DELETE FROM album_obligation_events", "UPDATE album_obligation_events SET state='attachment_pending'",
    "INSERT OR REPLACE INTO album_photo_obligations SELECT * FROM album_photo_obligations", "INSERT OR REPLACE INTO album_obligation_events SELECT * FROM album_obligation_events"]) {
    assert.throws(() => f.db.raw.exec(sql), sql); assert.deepEqual(albumState(f.db), before);
  }
  for (const change of [{ photo_binding_id: 'foreign-photo', photo_id: 'foreign-remote' }, { photo_binding_id: 'bare-photo', photo_id: 'bare-remote' },
    { photo_binding_id: 'wrong-owner', photo_id: 'wrong-remote' }, { photo_binding_id: 'old-link', photo_id: 'old-remote' },
    { photo_binding_id: 'third-photo', photo_id: 'forged-remote' }, { photo_binding_id: 'third-photo', photo_id: 'third-remote', admission_binding_revision: 99 }]) {
    const hostile = { ...original, obligation_id: crypto.randomUUID(), admission_binding_revision: 3, ...change }, columns = Object.keys(hostile);
    assert.throws(() => f.db.raw.prepare(`INSERT INTO album_photo_obligations(${columns.join(',')}) VALUES(${columns.map(() => '?').join(',')})`).run(...Object.values(hostile)));
    assert.deepEqual(albumState(f.db), before);
  }
});

test('production migration preserves nonempty #0108 receipts, immutable first photo, photosets and archived history', async t => {
  const f = await fixture(t, legacyAlbumStore());
  assert.equal(row(f, 'primary-photo').state, 'materialization_pending');
  assert.equal((await f.ensure('later-photo', 'Materialized')).status, 201);
  assert.equal((await f.ensure('third-photo', 'Archived')).status, 201);
  f.db.raw.exec("UPDATE album_bindings SET flickr_photoset_id='existing-photoset',binding_revision=binding_revision+1 WHERE local_collection_id='Materialized'; UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE local_collection_id='Archived'");
  const bindings = f.db.raw.prepare('SELECT * FROM album_bindings ORDER BY rowid').all();
  const events = f.db.raw.prepare('SELECT * FROM album_binding_events ORDER BY rowid').all();
  const receipts = f.db.raw.prepare('SELECT * FROM album_photo_obligations ORDER BY rowid').all();
  migrateAlbumObligations(f.db);
  assert.deepEqual(f.db.raw.prepare('SELECT * FROM album_bindings ORDER BY rowid').all(), bindings);
  assert.deepEqual(f.db.raw.prepare('SELECT * FROM album_binding_events ORDER BY rowid').all(), events);
  assert.deepEqual(f.db.raw.prepare('PRAGMA foreign_key_check').all(), []);
  const migrated = f.db.raw.prepare('SELECT * FROM album_photo_obligations ORDER BY rowid').all();
  assert.equal(migrated.length, receipts.length);
  for (const item of migrated) {
    const old = receipts.find(receipt => receipt.obligation_id === item.obligation_id), binding = bindings.find(binding => binding.binding_id === item.album_binding_id);
    for (const key of ['obligation_id', 'album_binding_id', 'photo_binding_id', 'photo_id', 'obligation_revision']) assert.equal(item[key], old[key]);
    assert.equal(item.state, binding.flickr_photoset_id ? 'attachment_pending' : 'waiting_for_album');
    assert.equal(item.local_relationship, binding.state === 'local_collection_removed_remote_preserved' ? 'archived' : 'active');
  }
  assert.equal(f.db.raw.prepare("SELECT count(*) n FROM album_obligation_events WHERE kind='receipt_migrated'").get().n, 3);
  const before = albumState(f.db), replay = await f.ensure(); assert.equal(replay.status, 200); assert.deepEqual((await replay.json()).obligation, f.first.obligation);
  assert.deepEqual(albumState(f.db), before); assert.equal((await f.call()).status, 201);
});

test('archival racing the handoff commits only retained archival facts and refuses the new association', async t => {
  const f = await fixture(t), batch = f.db.batch.bind(f.db); let archived;
  f.db.batch = async statements => {
    if (!archived) {
      f.db.raw.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?").run(f.binding);
      archived = albumState(f.db);
    }
    return batch(statements);
  };
  await error(await f.call(), 409, 'album_closed'); assert.equal(row(f), undefined); assert.deepEqual(albumState(f.db), archived);
});

test('a failed populated migration rolls back schema rebuild and all retained #0108 rows', async t => {
  const f = await fixture(t, legacyAlbumStore());
  const tables = ['album_bindings', 'album_photo_obligations', 'album_binding_events'];
  const before = Object.fromEntries(tables.map(table => [table, f.db.raw.prepare(`SELECT * FROM ${table} ORDER BY rowid`).all()]));
  // A pre-existing conflicting schema object fails the real migration after its
  // receipt-table rebuild, proving the enclosing transaction restores old guards.
  f.db.raw.exec('CREATE TABLE album_obligation_events(collision TEXT)');
  const schema = f.db.raw.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name LIKE 'album_%' ORDER BY type,name").all();
  assert.throws(() => migrateAlbumObligations(f.db));
  assert.deepEqual(f.db.raw.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name LIKE 'album_%' ORDER BY type,name").all(), schema);
  for (const table of tables) assert.deepEqual(f.db.raw.prepare(`SELECT * FROM ${table} ORDER BY rowid`).all(), before[table]);
  assert.deepEqual(f.db.raw.prepare('PRAGMA foreign_key_check').all(), []);
  assert.equal((await f.ensure('later-photo', 'AfterRollback')).status, 201);
});
