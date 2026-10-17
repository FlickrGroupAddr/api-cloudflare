import test from 'node:test';
import assert from 'node:assert/strict';
import { materializationFixture, contexts, PHOTO, OWNER } from './album_materialization_worker_fixture.mjs';
import { albumCreateRepairRequest } from '../src/album_create_repair.ts';
import { createSyntheticAlbumCreateRepairReader } from '../src/album_create_repair_discovery.ts';
import { assertAlbumRepairContext } from '../src/album_create_repair_store.ts';
import { NOW_US_SQL, credentialDigest } from '../src/installations.ts';
import { createWorker } from '../src/worker.ts';
import { digest } from '../src/browser_sessions.ts';

const CONTEXT = 'flickr.photos.getAllContexts', INFO = 'flickr.photosets.getInfo';
const ABSENT = '99999999-9999-4999-8999-999999999999';
const keys = (value, expected) => assert.deepEqual(Object.keys(value).sort(), expected.split(' ').sort());
function statusShape(value) {
  keys(value, 'schemaVersion binding localLifecycle materialization catalogRepair membershipCounts');
  keys(value.binding, 'schemaVersion fgaAlbumBindingId fgaPublishServiceId localCollectionIdentifier linkedFlickrRevision bindingRevision titleRevision desiredTitle firstPhotoBindingId flickrPhotosetId');
  keys(value.materialization, 'state createAttemptId repairSurface resolvedPhotosetId resolutionProvenance');
  keys(value.catalogRepair, 'flickrPhotosetId navigationUrl identityVerifiedAt');
  keys(value.membershipCounts, 'waitingForAlbum attachmentPending membershipVerified reconciliationPending needsAttention');
  assert.equal(value.schemaVersion, 1);
  assert.equal(value.catalogRepair.flickrPhotosetId, value.binding.flickrPhotosetId);
}
async function body(response, code = 200) {
  assert.equal(response.status, code, response.status === code ? undefined : await response.clone().text());
  assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.equal(response.headers.get('Referrer-Policy'), 'no-referrer');
  assert.equal(response.headers.get('Location'), null);
  return response.json();
}
async function failure(response, status, code) {
  const value = await body(response, status);
  keys(value, 'schemaVersion error'); keys(value.error, 'code message retryable correlationId');
  assert.equal(value.error.code, code); assert.equal(value.error.retryable, status === 503 || status === 429);
  assert.match(value.error.correlationId, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.ok(value.error.message.length > 0 && value.error.message.length <= 256);
  if (status === 503) assert.equal(response.headers.get('Retry-After'), '5');
  return value;
}
const domain = f => Object.fromEntries(['album_bindings', 'album_photo_obligations', 'album_binding_events',
  'album_materialization_attempts', 'album_materialization_events', 'album_obligation_events', 'album_create_repair_receipts']
  .map(table => [table, f.db.raw.prepare(`SELECT * FROM ${table} ORDER BY rowid`).all()]));

async function fixture(t) {
  const f = await materializationFixture(t);
  f.responses['flickr.photosets.create'] = new Response('synthetic lost acknowledgement', { status: 502 });
  f.responses[CONTEXT] = contexts(['preexisting']);
  assert.equal(await f.run(), 'create_outcome_unknown');
  // D1 batches are serialized transactions. The synchronous SQLite adapter's
  // async statement loop needs an explicit queue to reproduce that boundary.
  const batch = f.db.batch.bind(f.db); let tail = Promise.resolve();
  f.db.batch = statements => { const next = tail.then(() => batch(statements)); tail = next.catch(() => {}); return next; };
  f.calls.length = 0;
  f.currentIds = ['preexisting', 'selected', 'other']; f.proofHooks = {}; f.reads = [];
  f.repairAuth = { kind: 'installation', ...f.auth };
  f.adminToken = 'A'.repeat(43);
  f.adminAuth = { kind: 'admin', sessionId: 'repair-session', tokenDigest: digest(f.adminToken), ownerSub: 'synthetic-google-sub' };
  await f.db.batch([
    f.db.prepare("INSERT INTO admin_principals(user_id,google_issuer,google_sub) VALUES('user','https://accounts.google.com','synthetic-google-sub')"),
    f.db.prepare(`INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id)
      VALUES(?,?,'user',?,${NOW_US_SQL}-600000000,${NOW_US_SQL}-600000000,${NOW_US_SQL}+85800000000,${NOW_US_SQL},'synthetic-correlation')`)
      .bind(f.adminAuth.sessionId, f.adminAuth.tokenDigest, 'c'.repeat(43)),
  ]);
  f.reader = context => createSyntheticAlbumCreateRepairReader({ ...context, createAttemptId: context.attemptId }, {
    observedAt: () => new Date().toISOString().replace('Z', '000Z'),
    assertCurrent: () => assertAlbumRepairContext(f.db, f.activeAuth ?? f.repairAuth, context),
    reserveReads: async count => { f.reserved = (f.reserved ?? 0) + count; },
    sign(method, data) {
      const url = new URL('https://www.flickr.com/services/rest/'); url.searchParams.set('method', method);
      url.searchParams.set('format', 'json'); url.searchParams.set('nojsoncallback', '1');
      for (const [key, value] of Object.entries(data)) url.searchParams.set(key, String(value));
      return new Request(url, { redirect: 'manual' });
    },
    async fetcher(request) {
      assert.equal(request.method, 'GET'); const params = new URL(request.url).searchParams;
      const method = params.get('method'); f.reads.push({ method, photo: params.get('photo_id'), set: params.get('photoset_id') });
      await f.proofHooks[method]?.();
      if (method === CONTEXT) return Response.json(contexts(f.currentIds));
      assert.equal(method, INFO);
      return Response.json({ stat: 'ok', photoset: { id: params.get('photoset_id'), owner: OWNER,
        primary: 'a-different-current-primary', title: { _content: 'Synthetic selected album' } } });
    },
  });
  f.call = (operation = 'status', options = {}) => {
    const admin = options.admin ?? false;
    const id = options.binding ?? f.binding;
    const target = operation === 'repairs' ? '/api/v001/admin/album-create-repairs'
      : `/api/v001/${admin ? 'admin/' : ''}album-bindings/${id}/${operation}`;
    const query = ['photo-association-status', 'create-repair-candidates', 'repairs'].includes(operation)
      ? `?page=${options.page ?? 1}&page_size=${options.size ?? 20}` : '';
    const request = new Request('https://flickrgroupaddr.com' + target + query,
      options.value ? { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(options.value) } : {});
    f.activeAuth = options.auth ?? f.repairAuth;
    return albumCreateRepairRequest({ DB: f.db, FGA_ALBUM_CREATE_REPAIR_ENABLED: '1' }, f.activeAuth,
      request, operation === 'repairs' ? undefined : id, { reader: f.reader });
  };
  f.initial = await body(await f.call());
  f.selection = (id = 'selected') => ({ schemaVersion: 1, expectedBindingRevision: f.initial.binding.bindingRevision,
    createAttemptId: f.initial.materialization.createAttemptId, selectedPhotosetId: id });
  return f;
}

test('stored status and complete obligation page are closed coherent snapshots without upstream reads or mutation', async t => {
  const f = await fixture(t), before = domain(f), value = f.initial;
  statusShape(value); assert.equal(value.materialization.state, 'create_outcome_unknown');
  assert.equal(value.materialization.repairSurface, 'plugin_or_admin');
  assert.equal(value.catalogRepair.navigationUrl, null); assert.equal(value.catalogRepair.identityVerifiedAt, null);
  assert.equal(value.membershipCounts.waitingForAlbum, 1);
  const page = await body(await f.call('photo-association-status'));
  keys(page, 'schemaVersion fgaAlbumBindingId bindingRevision page pageSize pages total obligations');
  assert.equal(page.bindingRevision, value.binding.bindingRevision); assert.equal(page.total, 1); assert.equal(page.pages, 1);
  assert.equal(page.obligations.length, 1); keys(page.obligations[0], 'obligation state membershipObservedAt localRelationship');
  keys(page.obligations[0].obligation, 'fgaAlbumObligationId fgaAlbumBindingId fgaPhotoBindingId obligationRevision');
  assert.equal(page.obligations[0].state, 'waiting_for_album'); assert.equal(page.obligations[0].membershipObservedAt, null);
  assert.equal(f.reads.length, 0); assert.deepEqual(domain(f), before);
  await failure(await f.call('photo-association-status', { page: 2 }), 400, 'page_out_of_range');
});

test('candidate pages subtract complete pre-context lexically and remain advisory even with one or zero rows', async t => {
  const f = await fixture(t), before = domain(f);
  f.currentIds = ['selected', 'preexisting', 'other'];
  const page = await body(await f.call('create-repair-candidates', { size: 1 }));
  keys(page, 'schemaVersion fgaAlbumBindingId bindingRevision createAttemptId observedAt page pageSize pages total candidates');
  assert.equal(page.total, 2); assert.equal(page.pages, 2); assert.equal(page.candidates[0].flickrPhotosetId, 'other');
  keys(page.candidates[0], 'flickrPhotosetId title ownerNsid primaryPhotoId createdAt updatedAt navigationUrl thumbnail');
  assert.equal(page.candidates[0].createdAt, null); assert.equal(page.candidates[0].updatedAt, null); assert.equal(page.candidates[0].thumbnail, null);
  assert.equal(f.reads.length, 2); assert.equal(f.reads[0].photo, PHOTO);
  f.currentIds = ['preexisting', 'selected'];
  assert.equal((await body(await f.call('create-repair-candidates'))).total, 1);
  f.currentIds = ['preexisting'];
  const empty = await body(await f.call('create-repair-candidates')); assert.equal(empty.pages, 0); assert.equal(empty.total, 0); assert.deepEqual(empty.candidates, []);
  await failure(await f.call('create-repair-candidates', { page: 2 }), 400, 'page_out_of_range');
  assert.deepEqual(domain(f), before); assert.equal(f.calls.length, 0);
});

test('manual exact ID fresh proof commits membership despite different current primary and exact replay returns current status without reads', async t => {
  const f = await fixture(t); f.currentIds = ['manual-id'];
  const value = await body(await f.call('create-repair-resolution', { value: f.selection('manual-id') }));
  statusShape(value); assert.equal(value.binding.flickrPhotosetId, 'manual-id');
  assert.equal(value.materialization.resolutionProvenance, 'owner_reconciled_ambiguous_album_create');
  assert.equal(value.materialization.resolvedPhotosetId, 'manual-id'); assert.equal(value.membershipCounts.membershipVerified, 1);
  assert.equal(value.materialization.createAttemptId, f.initial.materialization.createAttemptId);
  assert.equal(value.binding.titleRevision, f.initial.binding.titleRevision);
  assert.equal(value.binding.bindingRevision, f.initial.binding.bindingRevision + 1);
  assert.deepEqual(f.reads.map(row => row.method).sort(), [CONTEXT, INFO].sort());
  assert.equal(f.reads.find(row => row.method === CONTEXT).photo, PHOTO);
  const before = domain(f); f.reads.length = 0;
  const replay = await body(await f.call('create-repair-resolution', { value: f.selection('manual-id') }));
  assert.deepEqual(replay, value); assert.equal(f.reads.length, 0); assert.deepEqual(domain(f), before);
  await failure(await f.call('create-repair-resolution', { value: f.selection('other') }), 409, 'resolution_conflict');
  assert.deepEqual(domain(f), before); assert.equal(f.calls.length, 0);
});

test('fresh selected membership absence commits nothing; old discovery evidence never substitutes', async t => {
  const f = await fixture(t); await body(await f.call('create-repair-candidates')); const before = domain(f);
  f.reads.length = 0; f.currentIds = [];
  await failure(await f.call('create-repair-resolution', { value: f.selection() }), 409, 'selected_album_not_verified');
  assert.deepEqual(domain(f), before); assert.equal(f.reads.length, 2); assert.equal(f.calls.length, 0);
});

test('stale revision and wrong original attempt refuse before proof and default-off composition makes no request', async t => {
  const f = await fixture(t), before = domain(f);
  await failure(await f.call('create-repair-resolution', { value: { ...f.selection(), expectedBindingRevision: 1 } }), 409, 'stale_binding_revision');
  await failure(await f.call('create-repair-resolution', { value: { ...f.selection(), createAttemptId: ABSENT } }), 409, 'resolution_conflict');
  assert.equal(f.reads.length, 0); assert.deepEqual(domain(f), before);
  const request = new Request(`https://flickrgroupaddr.com/api/v001/album-bindings/${f.binding}/status`);
  for (const flag of [undefined, '0', 'true']) await failure(await albumCreateRepairRequest({ DB: f.db,
    FGA_ALBUM_CREATE_REPAIR_ENABLED: flag }, f.repairAuth, request, f.binding, { reader: () => assert.fail('disabled reader') }), 503, 'service_unavailable');
});

test('foreign and absent binding are the same sanitized non-oracle refusal without upstream access', async t => {
  const f = await fixture(t);
  await f.db.batch([
    f.db.prepare("INSERT INTO fga_users VALUES('foreign')"),
    f.db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('foreign','foreign','lrc_plugin','active',1,'foreign-version')"),
    f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('foreign-version','foreign',?,'current',1)").bind('f'.repeat(64)),
  ]);
  const auth = { kind: 'installation', installationId: 'foreign', credentialDigest: 'f'.repeat(64) };
  const foreign = await failure(await f.call('status', { auth }), 404, 'resource_not_found');
  const absent = await failure(await f.call('status', { binding: ABSENT }), 404, 'resource_not_found');
  assert.equal(foreign.error.message, absent.error.message); assert.equal(f.reads.length, 0);
});

for (const operation of ['create-repair-candidates', 'create-repair-resolution']) {
  for (const [label, mutation] of [
    ['link revision', "UPDATE flickr_links SET link_revision=2"],
    ['grant generation', "UPDATE flickr_native_credentials SET active_generation='replacement-generation'"],
    ['pause generation', "UPDATE flickr_write_gates SET revision=revision+1,enabled=0 WHERE scope='user'"],
    ['credential revocation', "BEGIN; UPDATE installation_credential_versions SET state='revoked' WHERE installation_id='install'; UPDATE installations SET state='revoked',current_version_id=NULL,revision=revision+1 WHERE installation_id='install'; COMMIT"],
  ]) test(`${operation} refuses ${label} changed during actual upstream proof`, async t => {
    const f = await fixture(t), before = domain(f); let changed = false;
    f.proofHooks[CONTEXT] = () => { if (!changed) { changed = true; f.db.raw.exec(mutation); } };
    const response = await f.call(operation, operation.endsWith('resolution') ? { value: f.selection() } : {});
    assert.ok([401, 409].includes(response.status), `changed authority returned ${response.status}`);
    const value = await response.json();
    assert.ok(['invalid_token', 'flickr_link_unavailable'].includes(value.error.code));
    assert.deepEqual(domain(f), before); assert.equal(f.calls.length, 0);
  });
}

test('parallel equal selections converge and different selections retain exactly one immutable winner', { timeout: 5000 }, async t => {
  for (const same of [true, false]) {
    const f = await fixture(t); let arrivals = 0, release;
    const barrier = new Promise(resolve => { release = resolve; });
    f.proofHooks[CONTEXT] = async () => { if (++arrivals === 2) release(); await barrier; };
    const responses = await Promise.all([
      f.call('create-repair-resolution', { value: f.selection() }),
      f.call('create-repair-resolution', { value: f.selection(same ? 'selected' : 'other') }),
    ]);
    assert.equal(responses.filter(response => response.status === 200).length, same ? 2 : 1);
    if (!same) await failure(responses.find(response => response.status !== 200), 409, 'resolution_conflict');
    const winner = await body(await f.call());
    assert.equal(winner.binding.bindingRevision, f.initial.binding.bindingRevision + 1);
    assert.equal(winner.membershipCounts.membershipVerified, 1);
    assert.ok(['selected', 'other'].includes(winner.binding.flickrPhotosetId));
    assert.equal(f.db.raw.prepare('SELECT dispatch_count FROM album_materialization_attempts WHERE binding_id=?').get(f.binding).dispatch_count, 1);
    assert.equal(f.calls.length, 0);
  }
});

test('old status during pending selection does not authorize another create and later exact replay recovers lost acknowledgement', { timeout: 5000 }, async t => {
  const f = await fixture(t); let started, finish;
  const begun = new Promise(resolve => { started = resolve; }); const blocked = new Promise(resolve => { finish = resolve; });
  f.proofHooks[CONTEXT] = async () => { started(); await blocked; };
  const pending = f.call('create-repair-resolution', { value: f.selection() }); await begun;
  const old = await body(await f.call()); assert.equal(old.materialization.state, 'create_outcome_unknown');
  assert.equal(old.binding.flickrPhotosetId, null);
  finish(); assert.equal((await pending).status, 200); // The client loses the success body.
  f.reads.length = 0;
  const recovered = await body(await f.call('create-repair-resolution', { value: f.selection() }));
  assert.equal(recovered.binding.flickrPhotosetId, 'selected');
  assert.ok(recovered.binding.bindingRevision > old.binding.bindingRevision);
  assert.equal(f.reads.length, 0); assert.equal(f.calls.length, 0);
});

test('retained removed binding remains readable, discoverable and reparable through admin only without catalog or new work', async t => {
  const f = await fixture(t);
  f.db.raw.prepare("UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=binding_revision+1 WHERE binding_id=?").run(f.binding);
  const removed = await body(await f.call()); statusShape(removed);
  assert.equal(removed.localLifecycle, 'local_collection_removed_remote_preserved');
  assert.equal(removed.materialization.repairSurface, 'admin_only');
  assert.equal(removed.materialization.createAttemptId, f.initial.materialization.createAttemptId);
  await failure(await f.call('create-repair-candidates'), 409, 'administrative_repair_required');
  await failure(await f.call('create-repair-resolution', { value: f.selection() }), 409, 'administrative_repair_required');
  const admin = { admin: true, auth: f.adminAuth };
  const listing = await body(await f.call('repairs', admin));
  keys(listing, 'schemaVersion page pageSize pages total repairs'); assert.equal(listing.total, 1);
  keys(listing.repairs[0], 'fgaAlbumBindingId bindingRevision fgaPublishServiceId localCollectionIdentifier desiredTitle localLifecycle createAttemptId');
  assert.equal(listing.repairs[0].fgaAlbumBindingId, f.binding);
  assert.equal(listing.repairs[0].bindingRevision, removed.binding.bindingRevision);
  const candidates = await body(await f.call('create-repair-candidates', admin)); assert.equal(candidates.total, 2);
  const selection = { ...f.selection(), expectedBindingRevision: removed.binding.bindingRevision };
  const resolved = await body(await f.call('create-repair-resolution', { ...admin, value: selection }));
  assert.equal(resolved.localLifecycle, removed.localLifecycle); assert.equal(resolved.binding.flickrPhotosetId, 'selected');
  assert.equal(resolved.binding.titleRevision, removed.binding.titleRevision);
  const page = await body(await f.call('photo-association-status', admin));
  assert.equal(page.obligations[0].localRelationship, 'archived'); assert.equal(page.obligations[0].state, 'membership_verified');
  const empty = await body(await f.call('repairs', admin)); assert.equal(empty.total, 0); assert.equal(empty.pages, 0); assert.deepEqual(empty.repairs, []);
  assert.deepEqual(await body(await f.call('create-repair-resolution', { ...admin, value: selection })), resolved);
  await failure(await f.call('create-repair-resolution', { value: selection }), 409, 'administrative_repair_required');
  assert.equal(f.calls.length, 0);
});

test('actual Worker gates and authenticates all installation routes before resource lookup', async t => {
  const f = await fixture(t), worker = createWorker(() => assert.fail('unexpected provider request'), { reader: f.reader });
  const code = Array(13).fill('0000').join('-'), pending = Array(12).fill('0000').concat('000G').join('-');
  await f.db.batch([
    f.db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id,pending_version_id) VALUES('routed','user','lrc_plugin','active',1,'routed-version','pending-version')"),
    f.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('routed-version','routed',?,'current',1)").bind(await credentialDigest(code)),
    f.db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending-version','routed',?,'pending_rotation',2,${NOW_US_SQL}+600000000)`).bind(await credentialDigest(pending)),
  ]);
  for (const operation of ['status', 'photo-association-status?page=1&page_size=20', 'create-repair-candidates?page=1&page_size=20', 'create-repair-resolution']) {
    const put = operation.endsWith('resolution');
    const request = token => new Request(`https://flickrgroupaddr.com/api/v001/album-bindings/${f.binding}/${operation}`, {
      method: put ? 'PUT' : 'GET', headers: { ...(token ? { Authorization: 'Bearer ' + token } : {}), ...(put ? { 'Content-Type': 'application/json' } : {}) },
      ...(put ? { body: JSON.stringify(f.selection()) } : {}),
    });
    const disabled = await worker.fetch(request(null), { DB: f.db });
    assert.equal(disabled.status, 503); assert.equal(disabled.headers.get('Cache-Control'), 'private, no-store'); assert.equal(disabled.headers.get('Retry-After'), '5');
    const env = { DB: f.db, FGA_ALBUM_CREATE_REPAIR_ENABLED: '1' };
    const missing = await worker.fetch(request(null), env); assert.equal(missing.status, 401); assert.equal(await missing.text(), '');
    assert.equal(missing.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
    const refused = await worker.fetch(request(pending), env); assert.equal(refused.status, 403);
    assert.match(refused.headers.get('WWW-Authenticate'), /insufficient_scope/);
    if (operation === 'status') { const value = await body(await worker.fetch(request(code), env)); statusShape(value); }
  }
  assert.equal(f.reads.length, 0);
});

test('actual admin routing requires session and exact Origin CSRF while repair adds no recent-authentication ceremony', async t => {
  const f = await fixture(t), worker = createWorker(() => assert.fail('unexpected provider request'), { reader: f.reader });
  const env = { DB: f.db, FGA_ADMIN_ENABLED: '1', FGA_ALBUM_CREATE_REPAIR_ENABLED: '1', GOOGLE_OWNER_SUB: 'synthetic-google-sub', GOOGLE_CLIENT_ID: 'synthetic-client' };
  const target = `https://flickrgroupaddr.com/api/v001/admin/album-bindings/${f.binding}/create-repair-resolution`;
  const request = headers => new Request(target, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(f.selection()) });
  const unauthenticated = await worker.fetch(request({ Authorization: 'Bearer ' + Array(13).fill('0000').join('-') }), env);
  assert.equal(unauthenticated.status, 401); assert.equal(unauthenticated.headers.get('WWW-Authenticate'), null);
  const cookie = '__Host-fga_admin=' + f.adminToken;
  for (const extra of [{}, { Origin: 'https://evil.example', 'X-CSRF-Token': 'c'.repeat(43) }, { Origin: 'https://flickrgroupaddr.com' }]) {
    const response = await worker.fetch(request({ Cookie: cookie, ...extra }), env);
    assert.equal(response.status, 403); assert.equal((await response.json()).error.code, 'forbidden');
  }
  // The retained session was created ten minutes ago, beyond the five-minute
  // recent-authentication interval required for unrelated administrative work.
  f.activeAuth = f.adminAuth;
  const resolved = await body(await worker.fetch(request({ Cookie: cookie, Origin: 'https://flickrgroupaddr.com', 'X-CSRF-Token': 'c'.repeat(43) }), env));
  assert.equal(resolved.binding.flickrPhotosetId, 'selected');
});

function adminRoute(f, { binding = f.binding, operation = 'create-repair-resolution', headers = {}, value = f.selection(), token = f.adminToken } = {}) {
  const put = operation === 'create-repair-resolution';
  return new Request(`https://flickrgroupaddr.com/api/v001/admin/album-bindings/${binding}/${operation}`, {
    method: put ? 'PUT' : 'GET', headers: { Cookie: '__Host-fga_admin=' + token,
      Origin: 'https://flickrgroupaddr.com', ...(put ? { 'Content-Type': 'application/json', 'X-CSRF-Token': 'c'.repeat(43) } : {}), ...headers },
    ...(put ? { body: JSON.stringify(value) } : {}),
  });
}
function adminWorker(f) {
  f.activeAuth = f.adminAuth;
  const worker = createWorker(() => assert.fail('unexpected provider request'), { reader: f.reader });
  const env = { DB: f.db, FGA_ADMIN_ENABLED: '1', FGA_ALBUM_CREATE_REPAIR_ENABLED: '1',
    GOOGLE_OWNER_SUB: 'synthetic-google-sub', GOOGLE_CLIENT_ID: 'synthetic-client' };
  return request => worker.fetch(request, env);
}
const audit = f => f.db.raw.prepare('SELECT * FROM audit_events ORDER BY rowid').all();
function sanitizedAudit(f, event) {
  assert.equal(event.user_id, 'user');
  assert.ok(['succeeded', 'failed', 'refused'].includes(event.outcome));
  assert.ok(event.action.startsWith('album_create_repair.'));
  assert.ok(event.request_correlation_id); assert.ok(event.session_correlation_id);
  const serialized = JSON.stringify(event);
  for (const privateValue of [f.adminToken, f.adminAuth.tokenDigest, 'c'.repeat(43), 'Synthetic album', 'selected']) assert.equal(serialized.includes(privateValue), false);
}

test('administrative accepted selection and successful audit are atomic, with no extra success audit on exact replay', async t => {
  const f = await fixture(t), call = adminWorker(f), before = domain(f), originalAudit = audit(f);
  f.db.raw.exec("CREATE TRIGGER synthetic_refuse_resolution_audit BEFORE INSERT ON audit_events WHEN NEW.action='album_create_repair.resolved' BEGIN SELECT RAISE(ABORT,'synthetic_audit_failure'); END");
  await failure(await call(adminRoute(f)), 503, 'service_unavailable');
  assert.deepEqual(domain(f), before);
  assert.equal(audit(f).filter(event => event.outcome === 'succeeded').length, originalAudit.filter(event => event.outcome === 'succeeded').length);
  f.db.raw.exec('DROP TRIGGER synthetic_refuse_resolution_audit');
  const resolved = await body(await call(adminRoute(f))); assert.equal(resolved.binding.flickrPhotosetId, 'selected');
  const successes = audit(f).filter(event => event.action === 'album_create_repair.resolved');
  assert.equal(successes.length, 1); const event = successes[0]; sanitizedAudit(f, event);
  assert.equal(event.outcome, 'succeeded'); assert.equal(event.target_id, f.binding);
  assert.equal(event.reason, 'owner_reconciled_ambiguous_album_create');
  assert.equal(event.session_correlation_id, 'synthetic-correlation');
  const after = domain(f); f.reads.length = 0;
  assert.deepEqual(await body(await call(adminRoute(f))), resolved);
  assert.deepEqual(domain(f), after); assert.equal(f.reads.length, 0);
  assert.equal(audit(f).filter(row => row.action === 'album_create_repair.resolved').length, 1);
});

test('authenticated CSRF and absent resource refusals append sanitized failure audit without domain change', async t => {
  const f = await fixture(t), call = adminWorker(f), before = domain(f);
  for (const [request, expectedStatus, expectedCode] of [
    [adminRoute(f, { headers: { 'X-CSRF-Token': '' } }), 403, 'forbidden'],
    [adminRoute(f, { binding: ABSENT, operation: 'status' }), 404, 'resource_not_found'],
  ]) {
    const previous = audit(f).length, response = await call(request); assert.equal(response.status, expectedStatus);
    const added = audit(f).slice(previous); assert.equal(added.length, 1); sanitizedAudit(f, added[0]);
    assert.equal(added[0].outcome, 'failed'); assert.equal(added[0].action, 'album_create_repair.request_failed');
    assert.equal(added[0].reason, expectedCode); assert.equal(added[0].session_correlation_id, 'synthetic-correlation');
    assert.deepEqual(domain(f), before);
  }
  assert.equal(f.reads.length, 0);
});

test('revoked and expired admin sessions clear the host-only session cookie only for exact-origin requests', async t => {
  for (const expired of [false, true]) {
    const f = await fixture(t), call = adminWorker(f), before = domain(f);
    if (expired) {
      await f.db.batch([f.db.prepare(`INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id)
        VALUES('expired-session',?,'user',?,${NOW_US_SQL}-90000000000,${NOW_US_SQL}-90000000000,${NOW_US_SQL}-3600000000,${NOW_US_SQL}-90000000000,'expired-correlation')`)
        .bind(digest('B'.repeat(42) + 'A'), 'c'.repeat(43))]);
    } else f.db.raw.exec(`UPDATE admin_sessions SET revoked_at_us=${NOW_US_SQL},revocation_reason='synthetic-revocation',revision=revision+1 WHERE session_id='repair-session'`);
    const token = expired ? 'B'.repeat(42) + 'A' : f.adminToken;
    for (const origin of ['https://evil.example', 'https://flickrgroupaddr.com']) {
      const response = await call(adminRoute(f, { operation: 'status', token, headers: { Origin: origin } }));
      assert.equal(response.status, 401); assert.equal(response.headers.get('WWW-Authenticate'), null);
      const cookies = response.headers.getSetCookie();
      if (origin === 'https://evil.example') assert.deepEqual(cookies, []);
      else {
        assert.equal(cookies.length, 1);
        assert.ok(cookies.some(cookie => cookie.startsWith('__Host-fga_admin=')));
        for (const cookie of cookies) {
          assert.match(cookie, /(?:^|;\s*)Max-Age=0(?:;|$)/i); assert.match(cookie, /(?:^|;\s*)Path=\/(?:;|$)/i);
          assert.match(cookie, /(?:^|;\s*)Secure(?:;|$)/i); assert.match(cookie, /(?:^|;\s*)SameSite=Strict(?:;|$)/i);
          assert.doesNotMatch(cookie, /(?:^|;\s*)Domain=/i);
        }
      }
    }
    assert.deepEqual(domain(f), before); assert.equal(f.reads.length, 0);
  }
});
