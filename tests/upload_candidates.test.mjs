import test from 'node:test';
import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { uploadCandidatesRequest, uploadCandidatesQuery, validateUploadCandidatePage, UPLOAD_CANDIDATES_RELEASE_METADATA } from '../src/upload_candidates.ts';
const auth = { installationId: 'install', credentialDigest: 'd'.repeat(64) };
const issued = 1700000000;
const secrets = { FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'app', consumerSecret: 'secret' }) },
  FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'token', tokenSecret: 'secret' }) } };
const row = (id = 'p1') => ({ id, owner: 'owner', media: 'photo', title: 'Private title', dateupload: String(issued), url_q: `https://live.staticflickr.com/1/${id}_secret_q.jpg`, ispublic: 0, content_type: 3 });
const root = (rows = [row()], page = 1, size = 100, total = rows.length) => ({ stat: 'ok', photos: { page, perpage: size, pages: Math.ceil(total / size), total: String(total), photo: rows } });
async function fixture(t, legacy = false) {
  const db = sqlStore(); t.after(() => db.raw.close());
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(auth.credentialDigest),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
    db.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('authorization','install','user',?,?,?)").bind(issued * 1e6 + 999999, legacy ? null : 'owner', legacy ? null : 1),
  ]);
  const env = { DB: db, ...secrets, FGA_UPLOAD_CANDIDATES_ENABLED: '1' };
  return { db, env, call: (fetcher = async () => Response.json(root()), query = 'page=1&page_size=100', id = 'authorization', clock) =>
    uploadCandidatesRequest(env, auth, id, new URL('https://example.test/?' + query), fetcher, clock) };
}
async function error(response, status, code) {
  assert.equal(response.status, status); assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
  assert.equal((await response.json()).error.code, code);
}
test('query is closed and bounded, page cap does not truncate provider metadata', () => {
  for (const q of ['', 'page=1', 'page=01&page_size=1', 'page=1&page_size=0', 'page=1001&page_size=1', 'page=1&page_size=101',
    'page=1&page=1&page_size=1', 'page=1&page_size=1&owner=x', 'page=1.0&page_size=1', 'page=+1&page_size=1'])
    assert.throws(() => uploadCandidatesQuery(new URL('https://example.test/?' + q)));
  assert.deepEqual(uploadCandidatesQuery(new URL('https://example.test/?page=1000&page_size=100')), { page: 1000, size: 100 });
  const result = validateUploadCandidatePage(root([row()], 1, 1, 2147483647), { page: 1, size: 1 }, 'owner', issued, issued);
  assert.equal(result.pages, 2147483647);
});
test('private observations retain order, closed display subset, old fixed time window and no writes', async t => {
  const f = await fixture(t), before = f.db.raw.prepare('SELECT * FROM upload_authorizations').all();
  let calls = 0;
  const response = await f.call(async request => {
    calls++; const params = Object.fromEntries(new URL(request.url).searchParams);
    assert.deepEqual(params, { method: 'flickr.people.getPhotos', user_id: 'owner', content_types: '0,1,2,3', extras: 'date_upload,media,url_q',
      min_upload_date: String(issued - 120), max_upload_date: String(issued + 86400), page: '1', per_page: '100', format: 'json', nojsoncallback: '1' });
    assert.equal(request.redirect, 'manual'); assert.match(request.headers.get('Authorization'), /^OAuth /);
    return Response.json(root([row('z'), row('a')]));
  });
  assert.equal(response.status, 200); assert.equal(calls, 1); assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
  const body = await response.json(); assert.match(body.observedAt, /\.\d{6}Z$/);
  assert.deepEqual(body.photos.map(r => r.flickrPhotoId), ['z', 'a']);
  assert.deepEqual(Object.keys(body.photos[0]).sort(), ['dateUploaded', 'flickrPhotoId', 'photopageUrl', 'thumbnail', 'title']);
  assert.equal(body.photos[0].photopageUrl, 'https://www.flickr.com/photos/owner/z/');
  assert.deepEqual(f.db.raw.prepare('SELECT * FROM upload_authorizations').all(), before);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n, 0);
});
test('default disabled does not touch storage or secrets', async t => {
  const f = await fixture(t); assert.equal(UPLOAD_CANDIDATES_RELEASE_METADATA.defaultValue, '0'); delete f.env.FGA_UPLOAD_CANDIDATES_ENABLED;
  f.db.prepare = () => assert.fail('disabled'); await error(await f.call(), 503, 'ambiguity_candidates_unavailable');
});
test('current credential and exact installation ownership precede upstream read; legacy context is unavailable', async t => {
  const f = await fixture(t), noRead = async () => assert.fail('unauthorized read');
  await error(await f.call(noRead, undefined, 'missing'), 404, 'not_found');
  await error(await f.call(noRead, undefined, '../authorization'), 404, 'not_found');
  f.db.raw.exec("BEGIN;UPDATE installation_credential_versions SET state='revoked';UPDATE installations SET state='revoked',revision=2,current_version_id=NULL,pending_version_id=NULL;COMMIT");
  await error(await f.call(noRead), 401, 'invalid_token');
  const old = await fixture(t, true); await error(await old.call(noRead), 503, 'ambiguity_candidates_unavailable');
});
test('changed original link and bound authorizations never fetch', async t => {
  const f = await fixture(t), noRead = async () => assert.fail('changed link');
  f.db.raw.exec("UPDATE flickr_links SET link_revision=2");
  await error(await f.call(noRead), 409, 'flickr_link_changed');
  f.db.raw.exec("UPDATE upload_authorizations SET photo_id='bound'");
  await error(await f.call(noRead), 409, 'upload_already_bound');
});
test('credential, link and committed binding races discard the complete page', async t => {
  for (const [sql, status, code] of [["UPDATE installations SET revision=2", 401, 'invalid_token'],
    ["UPDATE flickr_links SET link_revision=2", 409, 'flickr_link_changed'], ["UPDATE upload_authorizations SET photo_id='bound'", 409, 'upload_already_bound']]) {
    const f = await fixture(t); await error(await f.call(async () => { f.db.raw.exec(sql); return Response.json(root()); }), status, code);
  }
});
test('empty normalization and exact continuation/out-of-range contract', async t => {
  const f = await fixture(t);
  for (const pages of [0, 1]) { const value = root([]); value.photos.pages = pages; const r = await f.call(async () => Response.json(value)); assert.equal(r.status, 200); assert.equal((await r.json()).pages, 0); }
  await error(await f.call(async () => Response.json(root([], 2, 100, 0)), 'page=2&page_size=100'), 400, 'candidate_page_out_of_range');
  const response = await f.call(async () => Response.json(root([row('tail')], 2, 1, 2)), 'page=2&page_size=1');
  assert.equal(response.status, 200); assert.equal((await response.json()).photos[0].flickrPhotoId, 'tail');
  await error(await f.call(async () => Response.json(root([], 3, 1, 2)), 'page=3&page_size=1'), 400, 'candidate_page_out_of_range');
});
test('every malformed/duplicate/incomplete row or metadata invalidates the page', async t => {
  const f = await fixture(t), invalid = [];
  for (const change of [r => r.owner = 'foreign', r => r.media = 'video', r => delete r.url_q, r => r.dateupload = String(issued - 121),
    r => r.dateupload = String(issued + 86401), r => r.title = 'x\0', r => r.title = '雪'.repeat(1366), r => r.id = 'bad id']) {
    const value = root(); change(value.photos.photo[0]); invalid.push(value);
  }
  invalid.push(root([row(), row()]));
  for (const change of [v => v.stat = 'fail', v => v.photos.page = 2, v => v.photos.perpage = 1, v => v.photos.pages = 2,
    v => v.photos.total = 2, v => v.photos.per_page = 99, v => v.photos.total = 2147483648]) { const v = root(); change(v); invalid.push(v); }
  for (const value of invalid) await error(await f.call(async () => Response.json(value)), 503, 'ambiguity_candidates_unavailable');
});
test('unsafe raw thumbnail representations are rejected without fetching thumbnail bytes', async t => {
  const f = await fixture(t);
  for (const url of ['http://live.staticflickr.com/1/p_q.jpg', 'https://evil.test/1/p_q.jpg', 'https://live.staticflickr.com:443/1/p_q.jpg',
    'https://u@live.staticflickr.com/1/p_q.jpg', 'https://live.staticflickr.com/1/p_q.jpg?secret=x', 'https://live.staticflickr.com/1/p_q.jpg#x',
    'https://live.staticflickr.com/2/../1/p_q.jpg', 'https://live.staticflickr.com/1/p_o.jpg', 'https://live.staticflickr.com/1/p_q.jpg\n']) {
    const value = root(); value.photos.photo[0].url_q = url;
    await error(await f.call(async () => Response.json(value)), 503, 'ambiguity_candidates_unavailable');
  }
});
test('UTF-8 title boundary accepts tabs/newlines and rejects aggregate serialized response budget', async t => {
  const f = await fixture(t), small = root(); small.photos.photo[0].title = 'é'.repeat(2048);
  assert.equal((await f.call(async () => Response.json(small))).status, 200);
  const large = root(Array.from({ length: 100 }, (_, i) => ({ ...row('p' + i), title: '\t'.repeat(4096) })));
  assert(Buffer.byteLength(JSON.stringify(large)) < 1048576);
  await error(await f.call(async () => Response.json(large)), 503, 'ambiguity_candidate_page_budget_exceeded');
  const restarted = await f.call(async () => Response.json(root([row()], 1, 50)), 'page=1&page_size=50'); assert.equal(restarted.status, 200);
});
test('stream budget, malformed UTF-8, redirect, partial body and transport failure remain unknown', async t => {
  const f = await fixture(t);
  await error(await f.call(async () => new Response(' '.repeat(1048577), { headers: { 'Content-Type': 'application/json' } })), 503, 'ambiguity_candidate_page_budget_exceeded');
  for (const fetcher of [async () => new Response(new Uint8Array([0xff]), { headers: { 'Content-Type': 'application/json' } }),
    async () => new Response('{"stat":', { headers: { 'Content-Type': 'application/json' } }), async () => new Response(null, { status: 302, headers: { Location: 'https://evil.test/' } }),
    async () => { throw new Error('secret must not escape'); }]) {
    const r = await f.call(fetcher); assert.equal(r.headers.get('Retry-After'), '5'); await error(r, 503, 'ambiguity_candidates_unavailable');
  }
});
test('monotonic total deadline rejects elapsed or regressing observations', async t => {
  const f = await fixture(t);
  for (const elapsed of [10000, -1, NaN]) { let n = 0; await error(await f.call(undefined, undefined, undefined, () => n++ ? elapsed : 0), 503, 'ambiguity_candidates_unavailable'); }
});
test('hard deadline completes even when fetch ignores AbortSignal', async t => {
  const f = await fixture(t), start = performance.now();
  await error(await f.call(async () => new Promise(() => {})), 503, 'ambiguity_candidates_unavailable');
  assert(performance.now() - start < 12000);
});
test('issuance snapshot fields reject mutation and wrong current owner or revision', async t => {
  const f = await fixture(t);
  for (const sql of ["UPDATE upload_authorizations SET owner_nsid='other'", "UPDATE upload_authorizations SET link_revision=2",
    "INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('bad','install','user',1,'foreign',1)",
    "INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('bad','install','user',1,'owner',NULL)"])
    assert.throws(() => f.db.raw.exec(sql));
});


test('foreign installation authorization is indistinguishable from missing and pending digest cannot read', async t => {
  const f = await fixture(t), noRead = async () => assert.fail('foreign read');
  f.db.raw.exec("BEGIN;INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('peer','user','lrc_plugin','active',1,'peer-version'); INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('peer-version','peer','eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','current',1); INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('peer-auth','peer','user',1,'owner',1);COMMIT");
  await error(await f.call(noRead, undefined, 'peer-auth'), 404, 'not_found');
  const response = await uploadCandidatesRequest(f.env, { ...auth, credentialDigest: 'e'.repeat(64) }, 'authorization', new URL('https://example.test/?page=1&page_size=100'), noRead);
  await error(response, 401, 'invalid_token');
});
test('future issuance is unavailable and recent observations use database whole-second bounds', async t => {
  const f = await fixture(t), noRead = async () => assert.fail('future read');
  f.db.raw.exec("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('future','install','user',9000000000000000,'owner',1)");
  await error(await f.call(noRead, undefined, 'future'), 503, 'ambiguity_candidates_unavailable');
  const issue = Date.now() * 1000 - 120000000;
  f.db.raw.prepare("INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,owner_nsid,link_revision) VALUES('recent','install','user',?,'owner',1)").run(issue);
  const response = await f.call(async request => {
    const q = new URL(request.url).searchParams; const value = root(); value.photos.photo[0].dateupload = q.get('max_upload_date');
    return Response.json(value);
  }, undefined, 'recent');
  assert.equal(response.status, 200); const value = await response.json();
  assert.equal(value.minUploadDate, String(Math.floor(issue / 1e6) - 120));
  assert.equal(value.maxUploadDate, String(Math.floor(Date.parse(value.observedAt) / 1000)));
});


test('credential replacement during secret resolution is an authentication refusal before provider read', async t => {
  const f = await fixture(t);
  f.env.FLICKR_GRANT = { get: async () => {
    f.db.raw.exec('UPDATE installations SET revision=revision+1');
    return secrets.FLICKR_GRANT.get();
  } };
  let calls = 0;
  await error(await f.call(async () => { calls++; return Response.json(root()); }), 401, 'invalid_token');
  assert.equal(calls, 0);
});
