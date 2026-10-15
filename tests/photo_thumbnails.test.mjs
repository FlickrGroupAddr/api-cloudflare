import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { credentialDigest } from '../src/installations.ts';
import { createWorker } from '../src/worker.ts';
import { photoThumbnailRequest, thumbnailBody, thumbnailQuery, boundedThumbnail,
  THUMBNAIL_LIMITS, THUMBNAIL_HOST_QUALIFIED } from '../src/photo_thumbnails.ts';

const secrets = { FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'app', consumerSecret: 'secret' }) },
  FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'token', tokenSecret: 'token-secret' }) } };
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
const image = () => new Response(png, { headers: { 'Content-Type': 'image/png', 'Content-Length': String(png.length) } });
const url = q => new URL('https://flickrgroupaddr.com/api/v001/existing-public-photos/photo/thumbnail?' + q);
const query = 'page=1&page_size=1&linked_flickr_revision=1';
const token = Array(13).fill('0000').join('-');
const discovery = () => ({ stat: 'ok', photos: { page: 1, perpage: 1, pages: 1, total: 1, photo: [{
  id: 'photo', owner: 'owner', ispublic: '1', media: 'photo', title: 'Title', dateupload: '1770000000',
  datetaken: '2026-02-01 14:30:00', url_q: 'https://live.staticflickr.com/1/photo_key_q.jpg' }] } });
async function fixture() {
  const db = sqlStore(), digest = await credentialDigest(token);
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('user','linked','available')"),
  ]);
  return { db, auth: { installationId: 'install', credentialDigest: digest } };
}
const read = (f, page = async () => Response.json(discovery()), cdn = image, q = query, signal, now) =>
  photoThumbnailRequest(f.db, f.auth, 'photo', url(q), secrets, page, cdn, signal, now);
const revoke = "BEGIN; UPDATE installation_credential_versions SET state='revoked'; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1; COMMIT";

test('thumbnail reference has a closed canonical page and revision query; arbitrary URLs never fetch', async () => {
  for (const q of ['', 'page=1&page_size=1', query + '&url=https://evil.test', query + '&linked_flickr_revision=1',
    query.replace('revision=1', 'revision=01'), query.replace('revision=1', 'revision=9007199254740992'), query + '&page=1'])
    assert.throws(() => thumbnailQuery(url(q)));
  let calls = 0;
  for (const target of ['http://live.staticflickr.com/1/photo_q.jpg', 'https://evil.test/1/photo_q.jpg',
    'https://live.staticflickr.com.evil.test/1/photo_q.jpg', 'https://live.staticflickr.com:444/1/photo_q.jpg',
    'https://user@live.staticflickr.com/1/photo_q.jpg', 'https://live.staticflickr.com/1/photo_q.jpg?x=1',
    'https://live.staticflickr.com/1/photo_q.svg', 'https://live.staticflickr.com/../photo_q.jpg'])
    await assert.rejects(thumbnailBody(target, async () => { calls++; return image(); }, new AbortController().signal));
  assert.equal(calls, 0);
});
test('fresh complete owner page selects exact reference; CDN carries no credentials and private response is complete', async () => {
  const f = await fixture(); let pages = 0, thumbnails = 0;
  try {
    const response = await read(f, async request => {
      pages++; assert.equal(request.redirect, 'manual'); assert.match(request.headers.get('Authorization'), /^OAuth /);
      assert.equal(new URL(request.url).searchParams.get('user_id'), 'owner'); return Response.json(discovery());
    }, async request => {
      thumbnails++; assert.equal(request.url, 'https://live.staticflickr.com/1/photo_key_q.jpg');
      assert.equal(request.redirect, 'manual'); assert.equal(request.headers.get('Authorization'), null);
      assert.equal(request.headers.get('Cookie'), null); assert.equal(request.headers.get('Referer'), null); return image();
    });
    assert.equal(response.status, 200); assert.equal(pages, 1); assert.equal(thumbnails, 1);
    assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
    assert.equal(response.headers.get('Cross-Origin-Resource-Policy'), 'same-origin');
    assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), png);
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n, 0);
  } finally { f.db.raw.close(); }
});
test('mismatched reference and malformed/mixed page fail before CDN, never salvage another row', async () => {
  for (const change of [b => b.photos.photo[0].id = 'other', b => b.photos.photo[0].owner = 'other',
    b => b.photos.photo[0].ispublic = 0, b => delete b.photos.photo[0].datetaken,
    b => b.photos.photo[0].url_q = 'https://live.staticflickr.com/1/other_key_q.jpg',
    b => { b.photos.photo.push({ ...b.photos.photo[0], id: 'other', owner: 'foreign' }); b.photos.total = 2; b.photos.perpage = 2; }]) {
    const f = await fixture(); let calls = 0;
    try {
      const response = await read(f, async () => { const b = discovery(); change(b); return Response.json(b); }, async () => { calls++; return image(); });
      assert.equal(response.status, 503); assert.equal(calls, 0); assert.equal((await response.json()).error.code, 'photo_thumbnail_unavailable');
    } finally { f.db.raw.close(); }
  }
});
test('wrong revision and revoked credential do not fetch; publication rejects concurrent authority changes', async () => {
  const mutations = ["UPDATE flickr_links SET link_revision=2", "UPDATE flickr_native_credentials SET active_generation='other'", revoke,
    "BEGIN; UPDATE installation_credential_versions SET state='replaced'; INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('next','install','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','current',2); UPDATE installations SET current_version_id='next',revision=2; COMMIT"];
  for (const mutation of mutations) for (const phase of ['page', 'image']) {
    const f = await fixture();
    try {
      const response = await read(f, async () => { if (phase === 'page') f.db.raw.exec(mutation); return Response.json(discovery()); }, async () => { if (phase === 'image') f.db.raw.exec(mutation); return image(); });
      assert([401, 409].includes(response.status)); assert.match(response.headers.get('Content-Type'), /json/);
    } finally { f.db.raw.close(); }
  }
  const f = await fixture(); let calls = 0;
  try {
    const peer = async () => { calls++; return image(); };
    assert.equal((await read(f, peer, peer, query.replace('revision=1', 'revision=2'))).status, 409);
    f.db.raw.exec(revoke); assert.equal((await read(f, peer, peer)).status, 401); assert.equal(calls, 0);
  } finally { f.db.raw.close(); }
});
test('redirects, mime mismatch, signatures, truncated bodies and stream byte excess reject and cancel', async () => {
  const peers = [() => new Response(null, { status: 302, headers: { Location: 'https://evil.test' } }),
    () => new Response(png, { headers: { 'Content-Type': 'text/html' } }),
    () => new Response(png, { headers: { 'Content-Type': 'image/jpeg' } }),
    () => new Response(png.subarray(0, 33), { headers: { 'Content-Type': 'image/png' } }),
    () => new Response(png, { headers: { 'Content-Type': 'image/png', 'Content-Length': '999' } }),
    () => new Response(png, { headers: { 'Content-Type': 'image/png', 'Content-Length': '262145' } }),
    () => new Response(png, { headers: { 'Content-Type': 'image/png', 'Content-Length': 'bad' } })];
  for (const peer of peers) await assert.rejects(thumbnailBody('https://live.staticflickr.com/1/photo_q.jpg', peer, new AbortController().signal));
  let cancelled = false;
  const stream = new ReadableStream({ start(c) { c.enqueue(new Uint8Array(THUMBNAIL_LIMITS.bytes + 1)); }, cancel() { cancelled = true; } });
  await assert.rejects(thumbnailBody('https://live.staticflickr.com/1/photo_q.jpg', async () => new Response(stream, { headers: { 'Content-Type': 'image/png' } }), new AbortController().signal));
  assert.equal(cancelled, true);
});
test('request abort interrupts a blocked stream; elapsed deadline including final fences cannot publish bytes', async () => {
  const f = await fixture(), controller = new AbortController(); let entered, cancelled = false;
  const ready = new Promise(resolve => { entered = resolve; });
  try {
    const result = read(f, undefined, async () => new Response(new ReadableStream({ start() { entered(); }, cancel() { cancelled = true; } }), { headers: { 'Content-Type': 'image/png' } }), query, controller.signal);
    await ready; controller.abort(); const response = await result;
    assert.equal(response.status, 503); assert.equal(cancelled, true); assert.match(response.headers.get('Content-Type'), /json/);
    let i = 0; const expired = await read(f, undefined, undefined, query, undefined, () => [0, 15000][i++]);
    assert.equal(expired.status, 503);
    for (const values of [[100, 99], [0, NaN]]) { let n = 0; await assert.rejects(boundedThumbnail(async () => 'done', undefined, () => values[n++])); }
    const aborted = new AbortController(); aborted.abort(); let calls = 0;
    await assert.rejects(boundedThumbnail(async () => { calls++; }, aborted.signal)); assert.equal(calls, 0);
  } finally { f.db.raw.close(); }
});
test('route is independently disabled by default and missing authentication never reaches provider', async () => {
  assert.equal(THUMBNAIL_HOST_QUALIFIED, false);
  const worker = createWorker(async () => { throw new Error('must not fetch'); });
  const env = { DB: { prepare() { throw new Error('must not access DB'); } }, FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1' };
  const request = () => new Request(url(query));
  assert.equal((await worker.fetch(request(), env)).status, 503);
  const enabled = { ...env, FGA_PHOTO_THUMBNAILS_ENABLED: '1' };
  const missing = await worker.fetch(request(), enabled); assert.equal(missing.status, 401);
  assert.equal(missing.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
  assert.equal((await worker.fetch(request(), { ...enabled, FGA_EXISTING_PHOTOS_ENABLED: '0' })).status, 503);
  assert.equal((await worker.fetch(request(), { ...enabled, FGA_READ_ENABLED: '0' })).status, 503);
  assert.equal((await worker.fetch(new Request(url(query), { method: 'POST' }), enabled)).status, 405);
});
test('HTTP route rejects pending/revoked/envelope credentials and accepts transformed opaque ID with same-origin binary headers', async () => {
  const f = await fixture(); let calls = 0;
  const worker = createWorker(async request => { calls++; return new URL(request.url).hostname === 'www.flickr.com' ? Response.json(discovery()) : image(); });
  const env = { ...secrets, DB: f.db, FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1', FGA_PHOTO_THUMBNAILS_ENABLED: '1' };
  const request = (headers = {}, target = url(query)) => new Request(target, { headers: { Authorization: 'Bearer ' + token, ...headers } });
  try {
    for (const headers of [{ 'Content-Length': '1' }, { 'Transfer-Encoding': 'chunked' }, { Authorization: 'Bearer ' + token + ', Bearer ' + token }])
      assert.equal((await worker.fetch(request(headers), env)).status, 400);
    assert.equal(calls, 0);
    const success = await worker.fetch(request({}, url(query).href.replace('/photo/', '/%70hoto/')), env);
    assert.equal(success.status, 200); assert.equal(success.headers.get('Content-Type'), 'image/png');
    assert.equal(success.headers.get('Cache-Control'), 'private, no-store');
    assert.equal(success.headers.get('Cross-Origin-Resource-Policy'), 'same-origin');
    assert.equal(Number(success.headers.get('Content-Length')), png.length); assert.equal(calls, 2);
    f.db.raw.exec("BEGIN; INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES('pending','install','" + await credentialDigest(token.replace(/0$/, 'G')) + "','pending_rotation',2,9000000000000000); UPDATE installations SET pending_version_id='pending',revision=revision+1; COMMIT");
    assert.equal((await worker.fetch(request({ Authorization: 'Bearer ' + token.replace(/0$/, 'G') }), env)).status, 403);
    assert.equal(calls, 2);
    f.db.raw.exec(revoke); assert.equal((await worker.fetch(request(), env)).status, 401); assert.equal(calls, 2);
  } finally { f.db.raw.close(); }
});
