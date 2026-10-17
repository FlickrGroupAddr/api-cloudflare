import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { albumBindingRequest, ALBUM_BINDINGS_RELEASE_METADATA, ALBUM_BINDINGS_ROUTES } from '../src/album_bindings.ts';
import { createWorker, ROUTES } from '../src/worker.ts';
import { credentialDigest, NOW_US_SQL } from '../src/installations.ts';

const CODE = Array(13).fill('0000').join('-');
const PENDING = Array(12).fill('0000').concat('000G').join('-');
const SERVICE = '11111111-1111-4111-8111-111111111111';
const SECOND_SERVICE = '22222222-2222-4222-8222-222222222222';
const FOREIGN_SERVICE = '33333333-3333-4333-8333-333333333333';
const ABSENT_SERVICE = '44444444-4444-4444-8444-444444444444';
const LOCAL = '0007:Album@A._-';
const path = (service = SERVICE, local = LOCAL) => `/api/v001/publish-services/${service}/album-bindings/${encodeURIComponent(local)}`;
const ensure = (photo = 'proved-upload', title = 'Album title', revision = 1) => ({
  schemaVersion: 1, desiredTitle: title, candidate: { fgaPhotoBindingId: photo, expectedVerificationRevision: revision },
});
const request = (value = ensure(), { method = 'PUT', service = SERVICE, local = LOCAL, target = path(service, local), headers = {}, raw } = {}) =>
  new Request('https://flickrgroupaddr.com' + target, { method, headers: { 'Content-Type': 'application/json', ...headers },
    ...(['GET', 'HEAD'].includes(method) ? {} : { body: raw ?? JSON.stringify(value) }) });

async function fixture(t) {
  const db = sqlStore(); t.after(() => db.raw.close());
  const auth = { installationId: 'install', credentialDigest: await credentialDigest(CODE) };
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user'),('foreign')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version'),('second','user','lrc_plugin','active',1,'second-version'),('foreign','foreign','lrc_plugin','active',1,'foreign-version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1),('second-version','second',?,'current',1),('foreign-version','foreign',?,'current',1)").bind(auth.credentialDigest, 'e'.repeat(64), 'f'.repeat(64)),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked'),('foreign','foreign-owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('user','gen',1,'owner','write',NULL),('foreign','foreign-gen',1,'foreign-owner','write',NULL)"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1),('foreign','linked','available','write',1)"),
    db.prepare("INSERT INTO publish_service_identities(service_id,user_id,issuing_installation_id,link_revision,owner_nsid) VALUES(?,'user','install',1,'owner'),(?,'user','install',1,'owner'),(?,'foreign','foreign',1,'foreign-owner')").bind(SERVICE, SECOND_SERVICE, FOREIGN_SERVICE),
    db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('upload-auth','install','user',1,'owner',1),('ambiguous-upload','install','user',2,'owner',1),('failed-upload','install','user',3,'owner',1)"),
    db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES('proved-upload','user','upload-photo','owner',1,1,'upload',1),('proved-existing','user','existing-photo','owner',1,1,'existing_public',1),('bare-upload','user','bare-upload-photo','owner',1,1,'upload',1),('bare-existing','user','bare-existing-photo','owner',1,1,'existing_public',1),('foreign-photo','foreign','foreign-photo-id','foreign-owner',1,1,'existing_public',1),('wrong-owner','user','wrong-owner-photo','other-owner',1,1,'existing_public',1),('old-link','user','old-link-photo','owner',2,1,'existing_public',1)"),
    db.prepare("UPDATE upload_authorizations SET photo_id='upload-photo' WHERE authorization_id='upload-auth'"),
    db.prepare("INSERT INTO upload_photo_binding_events(authorization_id,binding_id,link_revision,verification_revision,observed_public,verified_at_us) VALUES('upload-auth','proved-upload',1,1,0,1)"),
    db.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('existing-event','proved-existing',1,'existing_public_verified'),('foreign-event','foreign-photo',1,'existing_public_verified'),('owner-event','wrong-owner',1,'existing_public_verified'),('old-event','old-link',1,'existing_public_verified')"),
  ]);
  const env = { DB: db, FGA_ALBUM_BINDINGS_ENABLED: '1', FGA_READ_ENABLED: '0', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0' };
  const worker = createWorker(async () => assert.fail('album admission must make no external request'));
  return { db, env, auth,
    call: (value = ensure(), options = {}, presented = auth) => albumBindingRequest(env, presented, request(value, options), options.service ?? SERVICE, options.local ?? LOCAL),
    routed: (options = {}) => worker.fetch(new Request(request(options.value ?? ensure(), options), { headers: {
      'Content-Type': 'application/json', ...(options.credential === null ? {} : { Authorization: 'Bearer ' + (options.credential ?? CODE) }), ...options.headers,
    } }), env),
  };
}
const albumState = db => Object.fromEntries(['album_bindings', 'album_photo_obligations', 'album_binding_events', 'transaction_guards']
  .map(table => [table, db.raw.prepare(`SELECT * FROM ${table} ORDER BY rowid`).all()]));
const noReservation = db => { for (const rows of Object.values(albumState(db))) assert.equal(rows.length, 0); };
async function error(response, status, code) {
  assert.equal(response.status, status);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.equal(response.headers.get('Referrer-Policy'), 'no-referrer');
  const body = await response.json();
  assert.equal(body.schemaVersion, 1); assert.equal(body.error.code, code);
  assert.equal(body.error.retryable, status === 503 || status === 429);
  assert.match(body.error.correlationId, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  return body;
}

test('initial handoff atomically commits binding, first obligation and audit with exact hosted identities', async t => {
  const f = await fixture(t); noReservation(f.db); // Public proof by itself creates no Album publication.
  const response = await f.call(ensure('proved-upload', '  Album 🏊  '));
  assert.equal(response.status, 201); assert.equal(response.headers.get('Location'), path());
  const body = await response.json();
  assert.deepEqual(Object.keys(body).sort(), ['binding', 'obligation', 'schemaVersion']);
  assert.deepEqual(Object.keys(body.binding).sort(), ['schemaVersion', 'fgaAlbumBindingId', 'fgaPublishServiceId', 'localCollectionIdentifier',
    'linkedFlickrRevision', 'bindingRevision', 'titleRevision', 'desiredTitle', 'firstPhotoBindingId', 'flickrPhotosetId'].sort());
  assert.equal(body.binding.localCollectionIdentifier, LOCAL); assert.equal(body.binding.fgaPublishServiceId, SERVICE);
  assert.equal(body.binding.desiredTitle, '  Album 🏊  '); assert.equal(body.binding.bindingRevision, 1); assert.equal(body.binding.titleRevision, 1);
  assert.equal(body.binding.linkedFlickrRevision, 1); assert.equal(body.binding.flickrPhotosetId, null);
  assert.equal(body.binding.firstPhotoBindingId, 'proved-upload');
  assert.equal(body.obligation.fgaAlbumBindingId, body.binding.fgaAlbumBindingId);
  assert.equal(body.obligation.fgaPhotoBindingId, 'proved-upload'); assert.equal(body.obligation.obligationRevision, 1);
  const state = albumState(f.db); assert.equal(state.album_bindings.length, 1); assert.equal(state.album_photo_obligations.length, 1);
  assert.equal(state.album_binding_events.length, 1); assert.equal(state.transaction_guards.length, 0);
  assert.equal(state.album_bindings[0].owner_nsid, 'owner'); assert.equal(state.album_bindings[0].first_photo_id, 'upload-photo');
  assert.equal(state.album_bindings[0].state, 'materialization_pending'); assert.equal(state.album_photo_obligations[0].state, 'materialization_pending');
  for (const table of ['submission_intents', 'group_partitions']) assert.equal(f.db.raw.prepare(`SELECT count(*) n FROM ${table}`).get().n, 0);
  const before = albumState(f.db), read = await f.call(undefined, { method: 'GET' });
  assert.equal(read.status, 200); assert.deepEqual(await read.json(), body.binding); assert.deepEqual(albumState(f.db), before);
});

test('exact natural keys preserve case, leading zeroes and distinct service namespaces', async t => {
  const f = await fixture(t), ids = new Set();
  for (const [service, local] of [[SERVICE, '007'], [SERVICE, '7'], [SERVICE, 'Album'], [SERVICE, 'album'], [SECOND_SERVICE, 'Album']]) {
    const response = await f.call(ensure('proved-existing', 'Repeated title'), { service, local }); assert.equal(response.status, 201);
    ids.add((await response.json()).binding.fgaAlbumBindingId);
  }
  assert.equal(ids.size, 5); assert.equal(albumState(f.db).album_photo_obligations.length, 5);
});

test('same candidate receipt replay ignores new title and old proof revision, including archived relationships', async t => {
  const f = await fixture(t), first = await (await f.call()).json();
  f.db.raw.exec("UPDATE photo_bindings SET verification_revision=2 WHERE binding_id='proved-upload'; INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('refresh-event','proved-upload',2,'existing_public_verified')");
  let before = albumState(f.db), repeat = await f.call(ensure('proved-upload', 'Ignored rename'));
  assert.equal(repeat.status, 200); assert.deepEqual(await repeat.json(), first); assert.deepEqual(albumState(f.db), before);
  // Lifecycle mutation is a fixture for accepted replay semantics; no lifecycle endpoint is introduced here.
  f.db.raw.exec("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1");
  before = albumState(f.db); repeat = await f.call(ensure('proved-upload', 'Ignored restored-catalog title'));
  assert.equal(repeat.status, 200); assert.equal((await repeat.json()).binding.bindingRevision, 2); assert.deepEqual(albumState(f.db), before);
  await error(await f.call(ensure('proved-existing')), 409, 'album_binding_exists'); assert.deepEqual(albumState(f.db), before);
});

test('same-user installations resume service but foreign/absent service and photo IDs are indistinguishable', async t => {
  const f = await fixture(t);
  assert.equal((await f.call(ensure(), {}, { installationId: 'second', credentialDigest: 'e'.repeat(64) })).status, 201);
  const before = albumState(f.db);
  for (const service of [FOREIGN_SERVICE, ABSENT_SERVICE]) await error(await f.call(ensure(), { service }), 404, 'resource_not_found');
  for (const photo of ['foreign-photo', 'absent-photo']) await error(await f.call(ensure(photo), { local: 'new-key' }), 404, 'resource_not_found');
  for (const method of ['GET', 'PUT']) await error(await f.call(ensure(), { method }, { installationId: 'foreign', credentialDigest: 'f'.repeat(64) }), 404, 'resource_not_found');
  assert.deepEqual(albumState(f.db), before);
});

test('unknown, unproved, failed and ambiguous upload candidates reserve no key; later proved candidate can win', async t => {
  const f = await fixture(t);
  for (const [photo, code] of [['absent-photo', 'resource_not_found'], ['ambiguous-upload', 'resource_not_found'], ['failed-upload', 'resource_not_found'],
    ['bare-upload', 'photo_not_ready'], ['bare-existing', 'photo_not_ready'], ['wrong-owner', 'photo_not_ready'], ['old-link', 'photo_not_ready']]) {
    await error(await f.call(ensure(photo)), code === 'resource_not_found' ? 404 : 409, code); noReservation(f.db);
  }
  await error(await f.call(ensure('proved-upload', 'Stale proof', 2)), 409, 'stale_photo_revision'); noReservation(f.db);
  const response = await f.call(ensure('proved-existing')); assert.equal(response.status, 201);
  assert.equal((await response.json()).binding.firstPhotoBindingId, 'proved-existing');
});

test('zero and future-dated hosted photo identities cannot reserve the collection', async t => {
  for (const [binding, photo, timestamp] of [['0', 'zero-binding-photo', 1], ['zero-photo', '0', 1], ['future-photo', 'future-photo-id', 9000000000000000]]) {
    const f = await fixture(t);
    f.db.raw.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES(?,'user',?,'owner',1,1,'existing_public',?)").run(binding, photo, timestamp);
    f.db.raw.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('zero-or-future-event',?,1,'existing_public_verified')").run(binding);
    await error(await f.call(ensure(binding)), 409, 'photo_not_ready'); noReservation(f.db);
  }
});

test('first committed candidate wins even when the other request arrives first; same-candidate races converge', async t => {
  for (const same of [false, true]) {
    const f = await fixture(t), batch = f.db.batch.bind(f.db); let firstReached, releaseFirst;
    const reached = new Promise(resolve => firstReached = resolve), release = new Promise(resolve => releaseFirst = resolve);
    let calls = 0; f.db.batch = async statements => { if (++calls === 1) { firstReached(); await release; } return batch(statements); };
    const first = f.call(ensure('proved-upload', 'Arrived first')); await reached;
    const second = await f.call(ensure(same ? 'proved-upload' : 'proved-existing', 'Committed first'));
    releaseFirst(); const delayed = await first;
    assert.equal(second.status, 201); assert.equal(delayed.status, same ? 200 : 409);
    if (same) assert.deepEqual(await delayed.json(), await second.json());
    else await error(delayed, 409, 'album_binding_exists');
    const state = albumState(f.db); assert.equal(state.album_bindings.length, 1); assert.equal(state.album_photo_obligations.length, 1); assert.equal(state.album_binding_events.length, 1);
    assert.equal(state.album_bindings[0].desired_title, 'Committed first'); assert.equal(state.album_bindings[0].first_photo_binding_id, same ? 'proved-upload' : 'proved-existing');
  }
});

const ROTATE = "BEGIN; UPDATE installation_credential_versions SET state='replaced' WHERE version_id='version'; INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('replacement','install','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','current',2); UPDATE installations SET current_version_id='replacement',revision=revision+1 WHERE installation_id='install'; COMMIT";
test('transaction checks current credential, installation, link, pause, owner and proof at commit boundary', async t => {
  for (const [mutation, code] of [[ROTATE, 'invalid_token'],
    ["BEGIN; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='install'; UPDATE installation_credential_versions SET state='revoked' WHERE installation_id='install' AND state='current'; COMMIT", 'invalid_token'],
    ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_native_credentials SET link_revision=2 WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_native_credentials SET operation_id='pause' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_connection_state SET local_state='retirement_pending' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_native_credentials SET verified_owner_nsid='other' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE photo_bindings SET verification_revision=verification_revision+1 WHERE binding_id='proved-upload'; INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('concurrent-proof','proved-upload',2,'existing_public_verified')", 'stale_photo_revision']]) {
    const f = await fixture(t), batch = f.db.batch.bind(f.db); let changed = false;
    f.db.batch = async statements => { if (!changed) { changed = true; f.db.raw.exec(mutation); } return batch(statements); };
    await error(await f.call(), code === 'invalid_token' ? 401 : 409, code); noReservation(f.db);
  }
});

test('matching receipt replay still rechecks current credential and current service/link authority', async t => {
  for (const [mutation, code] of [[ROTATE, 'invalid_token'], ["UPDATE flickr_links SET state='paused' WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE flickr_links SET link_revision=2 WHERE user_id='user'; UPDATE flickr_native_credentials SET link_revision=2 WHERE user_id='user'", 'flickr_link_unavailable'],
    ["UPDATE photo_bindings SET verification_revision=2 WHERE binding_id='proved-upload'", 'photo_not_ready']]) {
    const f = await fixture(t); await f.call(); const before = albumState(f.db); f.db.raw.exec(mutation);
    await error(await f.call(), code === 'invalid_token' ? 401 : 409, code); assert.deepEqual(albumState(f.db), before);
  }
});

test('each injected batch failure rolls back binding, initial obligation, event and guard', async t => {
  const probe = await fixture(t), original = probe.db.batch.bind(probe.db); let length;
  probe.db.batch = statements => { length = statements.length; return original(statements); };
  assert.equal((await probe.call()).status, 201); assert(length > 0);
  for (let index = 0; index < length; index++) {
    const f = await fixture(t); f.db.fault = index; const response = await f.call();
    await error(response, 503, 'service_unavailable'); assert.equal(response.headers.get('Retry-After'), '5'); noReservation(f.db);
  }
  for (const table of ['album_photo_obligations', 'album_binding_events']) {
    const f = await fixture(t); f.db.raw.exec(`CREATE TRIGGER test_abort BEFORE INSERT ON ${table} BEGIN SELECT RAISE(ABORT,'synthetic_private_failure'); END`);
    const response = await f.call(); await error(response, 503, 'service_unavailable'); noReservation(f.db);
  }
});

test('authority read failure remains sanitized 503 and allocates no durable admission', async t => {
  const f = await fixture(t), prepare = f.db.prepare.bind(f.db);
  f.db.prepare = () => { throw new Error('synthetic_private_failure'); };
  const response = await f.call(); const body = await error(response, 503, 'service_unavailable');
  assert(!JSON.stringify(body).includes('synthetic_private_failure')); f.db.prepare = prepare; noReservation(f.db);
});

test('uncertain response after actual commit recovers through the same natural key without duplicate work', async t => {
  const f = await fixture(t), batch = f.db.batch.bind(f.db); let loseResponse = true;
  f.db.batch = async statements => {
    const result = await batch(statements);
    if (loseResponse) { loseResponse = false; throw new Error('synthetic_lost_commit_reply'); }
    return result;
  };
  await error(await f.call(), 503, 'service_unavailable');
  const committed = albumState(f.db); assert.equal(committed.album_bindings.length, 1); assert.equal(committed.album_photo_obligations.length, 1);
  assert.equal(committed.album_binding_events.length, 1);
  const retry = await f.call(); assert.equal(retry.status, 200);
  assert.equal((await retry.json()).binding.fgaAlbumBindingId, committed.album_bindings[0].binding_id);
  assert.deepEqual(albumState(f.db), committed);
});

test('ordinary SQL cannot rewrite first identity, delete/replace history or reuse a committed photoset', async t => {
  const f = await fixture(t); await f.call();
  for (const sql of ["UPDATE album_bindings SET first_photo_binding_id='proved-existing',first_photo_id='existing-photo'", "UPDATE album_bindings SET local_collection_id='other'",
    "UPDATE album_bindings SET binding_revision=binding_revision+1", "UPDATE album_bindings SET desired_title='unaudited-title'", "UPDATE album_bindings SET title_revision=title_revision+1",
    "UPDATE album_bindings SET owner_nsid='other'", "DELETE FROM album_bindings", "INSERT OR REPLACE INTO album_bindings SELECT * FROM album_bindings",
    "UPDATE album_photo_obligations SET photo_binding_id='proved-existing',photo_id='existing-photo'", "DELETE FROM album_photo_obligations", "INSERT OR REPLACE INTO album_photo_obligations SELECT * FROM album_photo_obligations",
    "DELETE FROM album_binding_events", "UPDATE album_binding_events SET state='materialization_pending'", "INSERT OR REPLACE INTO album_binding_events SELECT * FROM album_binding_events"]) {
    const before = albumState(f.db); assert.throws(() => f.db.raw.exec(sql), sql); assert.deepEqual(albumState(f.db), before);
  }
  f.db.raw.exec("UPDATE album_bindings SET flickr_photoset_id='photoset',binding_revision=binding_revision+1");
  for (const id of ["NULL", "'replacement'"]) assert.throws(() => f.db.raw.exec(`UPDATE album_bindings SET flickr_photoset_id=${id},binding_revision=binding_revision+1`));
  assert.equal((await f.call(ensure(), { local: 'second-album' })).status, 201);
  assert.throws(() => f.db.raw.exec("UPDATE album_bindings SET flickr_photoset_id='photoset',binding_revision=binding_revision+1 WHERE local_collection_id='second-album'"));
});

test('SQL guards reject cross-user service/photo tuples and missing exact proof without leaving dependent facts', async t => {
  const f = await fixture(t); await f.call();
  const original = albumState(f.db).album_bindings[0];
  for (const change of [{ service_id: FOREIGN_SERVICE }, { first_photo_binding_id: 'foreign-photo', first_photo_id: 'foreign-photo-id' },
    { first_photo_binding_id: 'bare-upload', first_photo_id: 'bare-upload-photo' }, { owner_nsid: 'foreign-owner' }, { link_revision: 2 }]) {
    const row = { ...original, binding_id: crypto.randomUUID(), first_obligation_id: crypto.randomUUID(), local_collection_id: 'hostile-key', ...change };
    const columns = Object.keys(row), before = albumState(f.db);
    assert.throws(() => f.db.raw.prepare(`INSERT INTO album_bindings(${columns.join(',')}) VALUES(${columns.map(() => '?').join(',')})`).run(...Object.values(row)));
    assert.deepEqual(albumState(f.db), before);
  }
});

test('strict raw envelope rejects duplicate decoded members, untrusted authority fields and invalid title/revision values before reads', async t => {
  const f = await fixture(t), prepare = f.db.prepare.bind(f.db); f.db.prepare = () => assert.fail('invalid envelope must not query');
  const valid = JSON.stringify(ensure());
  for (const raw of ['{', valid.replace('"schemaVersion":1', '"schemaVersion":1,"schema\\u0056ersion":1'),
    valid.replace('"fgaPhotoBindingId":"proved-upload"', '"fgaPhotoBindingId":"proved-upload","fgaPhoto\\u0042indingId":"proved-upload"'),
    valid.replace('"schemaVersion":1', '"schemaVersion":1.00000000000000000001'),
    valid.replace('"expectedVerificationRevision":1', '"expectedVerificationRevision":1.00000000000000000001'),
    JSON.stringify({ ...ensure(), ownerNsid: 'owner' }), JSON.stringify({ ...ensure(), candidate: { ...ensure().candidate, flickrPhotoId: 'upload-photo' } }),
    ...['', '\u0000', '\u007f', '\ud800', 'x'.repeat(1001)].map(desiredTitle => JSON.stringify({ ...ensure(), desiredTitle })),
    ...[0, -1, 1.5, 9007199254740992, null, '1'].map(expectedVerificationRevision => JSON.stringify({ ...ensure(), candidate: { ...ensure().candidate, expectedVerificationRevision } })),
    ...[null, [], { ...ensure(), schemaVersion: 2 }, { ...ensure(), candidate: null }].map(JSON.stringify), ' '.repeat(4096) + valid])
    await error(await f.call(undefined, { raw }), 400, 'invalid_request');
  for (const headers of [{ 'Content-Type': 'text/plain' }, { 'Content-Type': 'application/json;charset=iso-8859-1' }, { 'Content-Encoding': 'gzip' }, { 'Content-Length': '4097' }])
    await error(await f.call(undefined, { headers }), 400, 'invalid_request');
  await error(await f.call(undefined, { raw: new Uint8Array([0xc3, 0x28]) }), 400, 'invalid_request');
  f.db.prepare = prepare; noReservation(f.db);
});

test('valid equivalent exact integer syntax and maximum code-point title remain lossless', async t => {
  const f = await fixture(t), desiredTitle = 'a'.repeat(999) + '🏊';
  const raw = JSON.stringify(ensure('proved-upload', desiredTitle)).replace('"schemaVersion":1', '"schema\\u0056ersion":1.0e0')
    .replace('"expectedVerificationRevision":1', '"expectedVerificationRevision":10e-1');
  const response = await f.call(undefined, { raw }); assert.equal(response.status, 201);
  assert.equal((await response.json()).binding.desiredTitle, desiredTitle);
});

test('canonical single-segment paths and read envelope reject aliases, mismatched IDs and query parameters', async t => {
  const f = await fixture(t);
  for (const target of [path() + '?x=1', path().replace('%3A', '%3a'), path().replace('0007', '%30' + '007'),
    path().replace('%3A', '%253A'), path(SERVICE, 'bad/id'), path(SERVICE, 'bad id'), path().replace(SERVICE, ABSENT_SERVICE)])
    await error(await f.call(undefined, { target }), 400, 'invalid_request');
  for (const local of ['', ' ', 'A'.repeat(129), '..', 'album/title']) await error(await f.call(undefined, { local }), 400, 'invalid_request');
  await error(await f.call(undefined, { method: 'GET', headers: { 'Content-Length': '1' } }), 400, 'invalid_request');
  noReservation(f.db);
});

test('registered production routes default disabled and authenticate each request before exposing resources', async t => {
  const f = await fixture(t);
  assert.equal(ALBUM_BINDINGS_RELEASE_METADATA.defaultValue, '0'); assert.equal(ALBUM_BINDINGS_RELEASE_METADATA.hostQualified, false);
  assert.deepEqual(ALBUM_BINDINGS_ROUTES.map(r => r.method).sort(), ['GET', 'PUT']);
  for (const route of ALBUM_BINDINGS_ROUTES) { assert.equal(route.allowPending, false); assert(ROUTES.some(r => r.id === route.id)); }
  delete f.env.FGA_ALBUM_BINDINGS_ENABLED; const prepare = f.db.prepare.bind(f.db); f.db.prepare = () => assert.fail('disabled route must not query');
  await error(await f.routed({ credential: null }), 503, 'service_unavailable'); f.db.prepare = prepare; f.env.FGA_ALBUM_BINDINGS_ENABLED = '1';
  const missing = await f.routed({ credential: null }); assert.equal(missing.status, 401); assert.equal(await missing.text(), ''); assert.equal(missing.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
  await error(await f.routed({ credential: 'bad-code' }), 401, 'invalid_token');
  await f.db.batch([
    f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install',?,'pending_rotation',2,${NOW_US_SQL}+300000000)`).bind(await credentialDigest(PENDING)),
    f.db.prepare("UPDATE installations SET pending_version_id='pending',revision=revision+1 WHERE installation_id='install'"),
  ]);
  const pending = await f.routed({ credential: PENDING }); await error(pending, 403, 'insufficient_scope'); assert.match(pending.headers.get('WWW-Authenticate'), /insufficient_scope/);
  const first = await f.routed(); assert.equal(first.status, 201);
  assert.equal((await f.routed({ method: 'GET' })).status, 200);
  assert.equal((await f.routed({ method: 'POST' })).status, 405);
});
