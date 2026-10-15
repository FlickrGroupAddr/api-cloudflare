import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { existingPhotosRequest, discoveryQuery, validateDiscovery, photoReadBody, boundedPhotoRead } from '../src/existing_photo_discovery.ts';
import { photoMembershipsRequest, membershipQuery, validateMembership, MEMBERSHIP_HOST_QUALIFIED } from '../src/photo_memberships.ts';

const secrets = { FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'app', consumerSecret: 'secret' }) },
  FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'token', tokenSecret: 'token-secret' }) } };
async function fixture() {
  const db = sqlStore();
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind('d'.repeat(64)),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('user','linked','available')"),
    db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES('binding','user','photo','owner',1,1,'existing_public')"),
  ]);
  return { db, auth: { installationId: 'install', credentialDigest: 'd'.repeat(64) } };
}
const url = q => new URL('https://example.test/?' + q);
const photo = () => ({ id: 'opaque-photo', owner: 'owner', ispublic: '1', media: 'photo', title: 'Public title',
  dateupload: '1770000000', datetaken: '2026-02-01 14:30:00', url_q: 'https://live.staticflickr.com/1/photo_key_q.jpg' });
const discovery = () => ({ stat: 'ok', photos: { page: 1, perpage: 1, pages: 1, total: '1', photo: [photo()] } });
const contexts = () => ({ stat: 'ok', set: [{ id: 'album', title: 'discarded' }], pool: [{ id: 'g2', title: 'Second' }, { id: 'g1', title: 'First' }] });
const member = (f, fetcher = async () => Response.json(contexts()), q = 'page_size=1', now) => photoMembershipsRequest(f.db, f.auth, 'binding', url(q), secrets, fetcher, now);
const REVOKE = "BEGIN; UPDATE installation_credential_versions SET state='revoked'; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1; COMMIT";
const ROTATE = "BEGIN; UPDATE installation_credential_versions SET state='replaced'; INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('new-version','install','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','current',2); UPDATE installations SET current_version_id='new-version',revision=revision+1; COMMIT";

test('closed request queries reject unknown, duplicate, malformed, unsafe and unpaired fields', () => {
  for (const q of ['', 'page=1', 'page=1&page_size=0', 'page=1&page_size=101', 'page=01&page_size=1',
    'page=1&page_size=1&user_id=other', 'page=1&page=2&page_size=1', 'page=9007199254740992&page_size=1']) assert.throws(() => discoveryQuery(url(q)));
  for (const q of ['', 'page_size=01', 'page_size=101', 'page_size=1&observation_revision=1', 'page_size=1&after_group_id=g',
    'page_size=1&observation_revision=1&after_group_id=bad%20id', 'page_size=1&observation_revision=9007199254740992&after_group_id=g',
    'page_size=1&photo_id=other', 'page_size=1&page_size=2']) assert.throws(() => membershipQuery(url(q)));
});
test('discovery fixes exact owner, visibility, media and signed upstream method, exposes only reduced rows', async () => {
  const f = await fixture();
  try {
    const response = await existingPhotosRequest(f.db, f.auth, url('page=1&page_size=1'), secrets, async request => {
      const u = new URL(request.url);
      assert.deepEqual(Object.fromEntries(u.searchParams), { method: 'flickr.people.getPhotos', user_id: 'owner', privacy_filter: '1', content_types: '0',
        extras: 'date_upload,date_taken,media,url_q', page: '1', per_page: '1', format: 'json', nojsoncallback: '1' });
      assert.match(request.headers.get('Authorization'), /^OAuth /); assert.equal(request.redirect, 'manual');
      return Response.json(discovery());
    });
    assert.equal(response.status, 200); const body = await response.json();
    assert.equal(body.linkedFlickrRevision, 1); assert.equal(body.photos[0].flickrPhotoId, 'opaque-photo');
    assert.equal(body.photos[0].thumbnail.sizeClass, 'q'); assert(!('owner' in body.photos[0]));
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_binding_events').get().n, 0);
  } finally { f.db.raw.close(); }
});
test('one bad discovery row rejects entire page, including duplicate, mixed, missing extras and unsafe thumbnail', () => {
  for (const change of [p => p.owner = 'other', p => p.ispublic = 0, p => p.media = 'video', p => delete p.dateupload,
    p => p.title = null, p => p.datetaken = 'bad', p => p.datetaken = '2026-99-99 99:99:99',
    p => p.datetaken = '2026-02-30 12:00:00', p => p.dateupload = '99999999999999999999',
    p => p.url_q = 'https://evil.test/1/photo_q.jpg', p => p.url_q += '?secret=x']) {
    const value = discovery(); change(value.photos.photo[0]); assert.throws(() => validateDiscovery(value, { page: 1, size: 1 }, 'owner'));
  }
  const value = discovery(); value.photos.photo.push(photo()); value.photos.total = 2; value.photos.perpage = 2;
  assert.throws(() => validateDiscovery(value, { page: 1, size: 2 }, 'owner'));
  assert.throws(() => validateDiscovery({ stat: 'ok', photos: { page: 1, pages: 0, total: 0, perpage: 1 } }, { page: 1, size: 1 }, 'owner'));
});
test('strict complete membership shape never salvages bad entries or coerces missing pools', () => {
  for (const pool of [undefined, null, {}, 'pool', 0, false, [null], [{ id: 'g' }], [{ id: 'g', title: 'one' }, { id: 'g', title: 'two' }]])
    assert.throws(() => validateMembership({ stat: 'ok', pool }));
  for (const set of [null, {}, ['bad'], [{ id: 'album' }]]) assert.throws(() => validateMembership({ stat: 'ok', pool: [], set }));
  assert.throws(() => validateMembership({ stat: 'fail', pool: [] }));
  assert.deepEqual(validateMembership({ stat: 'ok', pool: [], set: [], extra: 'allowed' }), []);
  assert.throws(() => validateMembership({ stat: 'ok', pool: [], set: Array.from({ length: 10001 }, (_, i) => ({ id: 's' + i, title: '' })) }));
});
test('fresh reads replace one revision; continuations are stable ordered keyset pages without Flickr calls', async () => {
  const f = await fixture(); let calls = 0;
  const peer = async request => { calls++; const u = new URL(request.url); assert.equal(u.searchParams.get('method'), 'flickr.photos.getAllContexts'); assert.equal(u.searchParams.get('photo_id'), 'photo'); assert.equal(u.searchParams.size, 4); return Response.json(contexts()); };
  try {
    const first = await (await member(f, peer)).json();
    assert.equal(calls, 1); assert.equal(first.observationRevision, 1); assert.equal(first.nextAfterGroupId, 'g1'); assert.deepEqual(first.groups, [{ flickrGroupId: 'g1', displayName: 'First' }]);
    const q = 'page_size=1&observation_revision=1&after_group_id=g1';
    const last = await (await member(f, peer, q)).json(); assert.equal(calls, 1); assert.equal(last.nextAfterGroupId, null); assert.equal(last.observedAt, first.observedAt);
    assert.deepEqual(await (await member(f, peer, q)).json(), last);
    await member(f, peer); assert.equal(calls, 2);
    const conflict = await member(f, peer, q); assert.equal(conflict.status, 409); assert.equal((await conflict.json()).error.code, 'membership_observation_changed');
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_membership_observations').get().n, 1);
    assert(!JSON.stringify(f.db.raw.prepare('SELECT * FROM photo_membership_rows').all()).includes('discarded'));
  } finally { f.db.raw.close(); }
});
test('failed new initial read retains DB timing but never serves prior groups; explicit empty success advances revision', async () => {
  const f = await fixture(); try {
    await member(f);
    const failed = await member(f, async () => Response.json({ stat: 'ok' }));
    assert.equal(failed.status, 503); assert.equal(failed.headers.get('Retry-After'), '5'); const body = await failed.json();
    assert.equal(body.error.code, 'membership_observation_unavailable'); assert.equal(body.error.retryable, true);
    for (const key of ['groups', 'observedAt', 'observationRevision', 'nextAfterGroupId']) assert(!(key in body));
    assert.equal(f.db.raw.prepare('SELECT revision FROM photo_membership_observations').get().revision, 1);
    const retired = await member(f, async () => { throw new Error('must not fetch'); }, 'page_size=1&observation_revision=1&after_group_id=g1');
    assert.equal(retired.status, 409); assert(!('groups' in await retired.json()));
    const empty = await (await member(f, async () => Response.json({ stat: 'ok', pool: [] }))).json();
    assert.deepEqual(empty.groups, []); assert.equal(empty.observationRevision, 2);
  } finally { f.db.raw.close(); }
});
test('missing/foreign bindings and revoked installations make zero Flickr calls', async () => {
  const f = await fixture(); let calls = 0; const peer = async () => { calls++; return Response.json(contexts()); };
  try {
    assert.equal((await photoMembershipsRequest(f.db, f.auth, 'missing', url('page_size=1'), secrets, peer)).status, 404);
    f.db.raw.exec("INSERT INTO fga_users VALUES('other'); INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES('foreign','other','other-photo','owner',1,1,'upload')");
    assert.equal((await photoMembershipsRequest(f.db, f.auth, 'foreign', url('page_size=1'), secrets, peer)).status, 404);
    f.db.raw.exec(REVOKE);
    assert.equal((await member(f, peer)).status, 401); assert.equal(calls, 0);
  } finally { f.db.raw.close(); }
});
test('relink/generation and installation-version races fence commits and all continuation reads', async () => {
  for (const mutation of ["UPDATE flickr_links SET link_revision=2", "UPDATE flickr_native_credentials SET active_generation='other'",
    REVOKE, ROTATE]) {
    const f = await fixture(); try {
      const response = await member(f, async () => { f.db.raw.exec(mutation); return Response.json(contexts()); });
      assert([401, 409].includes(response.status)); assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_membership_observations').get().n, 0);
    } finally { f.db.raw.close(); }
    const g = await fixture(); try {
      await member(g); g.db.raw.exec(mutation);
      const response = await member(g, async () => { throw new Error('must not fetch'); }, 'page_size=1&observation_revision=1&after_group_id=g1');
      assert([401, 409].includes(response.status)); assert(!('groups' in await response.json()));
    } finally { g.db.raw.close(); }
  }
});
test('transaction failure rolls back all snapshot rows and revision', async () => {
  const f = await fixture(); try {
    await member(f); f.db.fault = 4;
    assert.equal((await member(f, async () => Response.json({ stat: 'ok', pool: [] }))).status, 503);
    assert.equal(f.db.raw.prepare('SELECT revision FROM photo_membership_observations').get().revision, 1);
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_membership_rows').get().n, 2);
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM transaction_guards').get().n, 0);
  } finally { f.db.raw.close(); }
});
test('response bytes, charset, truncation, redirect and elapsed budgets fail the complete observation', async () => {
  const peers = [async () => Response.json({ padding: 'x'.repeat(2097152) }),
    async () => new Response('{"stat":"ok","pool":[]}', { headers: { 'Content-Type': 'application/json; charset=iso-8859-1' } }),
    async () => new Response('{"stat":"ok","pool":[', { headers: { 'Content-Type': 'application/json' } }),
    async () => new Response(null, { status: 302, headers: { Location: 'https://evil.test' } })];
  for (const peer of peers) { const f = await fixture(); try { assert.equal((await member(f, peer)).status, 503); assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_membership_observations').get().n, 0); } finally { f.db.raw.close(); } }
  for (const values of [[0, 15000], [100, 99], [0, NaN]]) {
    let i = 0; await assert.rejects(boundedPhotoRead(async () => 'complete', () => values[i++]));
  }
  const controller = new AbortController(); controller.abort();
  await assert.rejects(photoReadBody(new Request('https://example.test'), async () => Response.json({}), controller.signal));
  assert.equal(MEMBERSHIP_HOST_QUALIFIED, false);
});
test('discovery failure and link-race are unavailable/conflict without rows', async () => {
  const f = await fixture(); try {
    const response = await existingPhotosRequest(f.db, f.auth, url('page=1&page_size=1'), secrets, async () => { const b = discovery(); b.photos.photo[0].owner = 'other'; return Response.json(b); });
    assert.equal(response.status, 503); assert(!('photos' in await response.json()));
    const race = await existingPhotosRequest(f.db, f.auth, url('page=1&page_size=1'), secrets, async () => { f.db.raw.exec('UPDATE flickr_links SET link_revision=2'); return Response.json(discovery()); });
    assert.equal(race.status, 409); assert(!('photos' in await race.json()));
  } finally { f.db.raw.close(); }
});
test('malformed failure envelopes cannot retire the grant; complete definitive rejection is fenced', async () => {
  for (const failure of [{ stat: 'fail', code: 98 }, { stat: 'fail', code: 99, message: null },
    { stat: 'fail', code: 98, message: '' }, { stat: 'fail', code: 99, message: 'Invalid auth token' }]) {
    const f = await fixture(); try {
      const complete = failure.message === 'Invalid auth token';
      const response = await member(f, async () => Response.json(failure));
      assert.equal(response.status, complete ? 409 : 503);
      assert.equal(f.db.raw.prepare('SELECT state FROM flickr_links').get().state, complete ? 'paused' : 'linked');
      assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM flickr_lifecycle_operations').get().n, complete ? 1 : 0);
      assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_membership_observations').get().n, 0);
    } finally { f.db.raw.close(); }
  }
});
test('a delayed failed initial request cannot retire a concurrent newer successful observation', async () => {
  const f = await fixture(); let enter, release;
  const entered = new Promise(resolve => { enter = resolve; }), wait = new Promise(resolve => { release = resolve; });
  try {
    await member(f);
    const older = member(f, async () => { enter(); await wait; return Response.json({ stat: 'ok' }); });
    await entered;
    const newer = await member(f); assert.equal(newer.status, 200); const current = await newer.json();
    assert.equal(current.observationRevision, 2);
    release(); assert.equal((await older).status, 503);
    const continued = await member(f, async () => { throw new Error('must not fetch'); }, 'page_size=1&observation_revision=2&after_group_id=g1');
    assert.equal(continued.status, 200); assert.equal((await continued.json()).groups[0].flickrGroupId, 'g2');
  } finally { release?.(); f.db.raw.close(); }
});
