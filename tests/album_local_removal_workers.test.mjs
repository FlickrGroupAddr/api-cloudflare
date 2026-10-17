import test from 'node:test';
import assert from 'node:assert/strict';
import { titleFixture, titleClock, SET as TITLE_SET, ORIGINAL } from './album_title_fixture.mjs';
import { attachmentFixture, SET as ATTACHMENT_SET } from './album_attachment_fixture.mjs';
import { materializationFixture, contexts, SET as CREATE_SET } from './album_materialization_worker_fixture.mjs';
import { consumeAlbumTitle } from '../src/album_title_worker.ts';
import { consumeAlbumAttachment } from '../src/album_attachment_worker.ts';
import { createSyntheticAlbumTitleTransport } from '../src/album_title_transport.ts';
import { createSyntheticAlbumAttachmentTransport } from '../src/album_attachment_transport.ts';
import { putAlbumLocalRemoval, putAlbumPhotoLocalRemoval } from '../src/album_local_removal_store.ts';
import { readAlbumStatus } from '../src/album_create_repair_store.ts';

const INFO = 'flickr.photosets.getInfo', EDIT = 'flickr.photosets.editMeta';
const CONTEXT = 'flickr.photos.getAllContexts', ADD = 'flickr.photosets.addPhoto', CREATE = 'flickr.photosets.create';
const ARCHIVED = 'local_collection_removed_remote_preserved';
const bindingId = f => f.bindingId ?? f.binding;
const binding = f => f.db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(bindingId(f)).first();
async function archive(f, acknowledgedCreateAttemptId = null) {
  const row = await binding(f);
  return putAlbumLocalRemoval(f.db, f.auth, bindingId(f), { schemaVersion: 1,
    expectedBindingRevision: row.binding_revision, acknowledgedCreateAttemptId });
}
const attempts = (f, table) => f.db.prepare('SELECT * FROM ' + table + ' WHERE binding_id=? ORDER BY rowid').bind(bindingId(f)).all().then(r => r.results);
const writes = f => f.calls.filter(c => c.request.method === 'POST');
function permitted(f, allowed) {
  for (const call of f.calls) {
    assert(allowed.includes(call.method), 'Only the exact lifecycle-authorized Flickr methods may be requested');
    assert.equal(new URL(call.request.url).pathname, '/services/rest/');
  }
}
function transport(f, kind) {
  f.calls = []; f.hooks = {}; f.responses = {}; f.remoteTitle = ORIGINAL;
  const set = kind === 'title' ? TITLE_SET : ATTACHMENT_SET;
  const create = kind === 'title' ? createSyntheticAlbumTitleTransport : createSyntheticAlbumAttachmentTransport;
  return (identity, assertCurrent, execution) => create(identity, {
    assertCurrent, beforeRequest: async () => {}, ...(execution ? { execution } : {}),
    sign(method, data, post = method === EDIT || method === ADD) {
      const url = new URL('https://www.flickr.com/services/rest/');
      for (const [key, value] of Object.entries({ method, format: 'json', nojsoncallback: '1', ...data })) url.searchParams.set(key, value);
      const body = post ? url.searchParams.toString() : undefined;
      if (post) url.search = '';
      return new Request(url, { method: post ? 'POST' : 'GET', redirect: 'manual', ...(post ? { body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } } : {}) });
    },
    async fetcher(request) {
      const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : new URL(request.url).searchParams;
      const method = params.get('method'), call = { request, params, method }; f.calls.push(call);
      const count = f.calls.filter(c => c.method === method && c.params.get('photo_id') === params.get('photo_id')).length;
      await f.hooks[method]?.(call, count);
      let body = typeof f.responses[method] === 'function' ? await f.responses[method](call, count) : f.responses[method];
      if (body === undefined) {
        if (method === EDIT) { f.remoteTitle = params.get('title'); body = { stat: 'ok' }; }
        else if (method === ADD) body = { stat: 'ok' };
        else if (method === INFO) body = { stat: 'ok', photoset: { id: set, owner: 'owner', primary: 'primary-remote', title: { _content: f.remoteTitle } } };
        else if (method === CONTEXT) body = contexts(params.get('photo_id') === 'primary-remote' || count > 1 ? [set] : []);
        else assert.fail('Unexpected Flickr method');
      }
      return body instanceof Response ? body : Response.json(body);
    },
  });
}
async function title(t) {
  const f = await titleFixture(t, { desiredTitle: 'Pending local title' });
  const factory = transport(f, 'title');
  f.run = () => consumeAlbumTitle({ DB: f.db, FGA_ALBUM_TITLE_SYNC_ENABLED: '1' }, f.bindingId, factory);
  return f;
}
async function attachment(t) {
  const f = await attachmentFixture(t); f.auth = { installationId: 'install', credentialDigest: 'a'.repeat(64) };
  const factory = transport(f, 'attachment');
  f.run = () => consumeAlbumAttachment({ DB: f.db, FGA_ALBUM_ATTACHMENT_ENABLED: '1' }, f.obligationId, factory);
  return f;
}

test('real album archival cancels undispatched title without constructing a provider transport', async t => {
  const f = await title(t), before = await binding(f);
  await archive(f);
  assert.equal(await consumeAlbumTitle({ DB: f.db, FGA_ALBUM_TITLE_SYNC_ENABLED: '1' }, f.bindingId, () => assert.fail('Canceled title must not construct transport')), 'no_work');
  assert.equal((await binding(f)).flickr_photoset_id, before.flickr_photoset_id);
  assert.equal((await binding(f)).state, ARCHIVED);
  assert.deepEqual(f.calls, []);
});

test('archive during actual title pre-read fences the prepared edit and future claims', async t => {
  const f = await title(t); f.hooks[INFO] = async (_call, count) => { if (count === 1) await archive(f); };
  assert.equal(await f.run(), 'not_dispatched'); assert.equal(writes(f).length, 0);
  assert.equal(await f.run(), 'no_work'); permitted(f, [INFO]);
  assert.equal((await attempts(f, 'album_title_attempts'))[0].dispatch_count, 0);
});

for (const observed of ['Pending local title', ORIGINAL, 'External third title']) {
  test(`archive after title dispatch reconciles ${observed} read-only without retry`, async t => {
    const f = await title(t), clock = titleClock(f.db);
    f.hooks[EDIT] = async () => { await archive(f); };
    f.responses[EDIT] = () => { f.remoteTitle = observed; throw new Error('Synthetic lost title reply'); };
    await f.run(); assert.equal(writes(f).length, 1);
    for (let n = 0; n < 3; n++) { clock.advance(600000); await f.run(); }
    assert.equal(writes(f).length, 1); permitted(f, [INFO, EDIT]);
    assert.equal((await binding(f)).state, ARCHIVED);
    assert.equal((await binding(f)).flickr_photoset_id, TITLE_SET);
    assert.equal((await attempts(f, 'album_title_attempts'))[0].dispatch_count, 1);
    assert(f.calls.filter(c => c.method === INFO).length >= 2, 'A fresh read must reconcile the retained dispatch');
    assert((await attempts(f, 'album_title_attempts'))[0].completed_at_us !== null);
    assert.equal(await f.run(), 'no_work');
  });
}

for (const timing of ['before claim', 'during pre-context']) {
  test(`archive ${timing} permits only original accepted first-photo materialization with frozen title`, async t => {
    const f = await materializationFixture(t), before = f.album(), obligation = f.obligation();
    if (timing === 'before claim') await archive(f);
    else f.hooks[CONTEXT] = async (_request, count) => { if (count === 1) await archive(f); };
    assert.equal(await f.run(), 'materialized'); assert.equal(await f.run(), 'no_work');
    assert.equal(writes(f).length, 1); permitted(f, [CONTEXT, CREATE, INFO]);
    assert.equal(writes(f)[0].params.get('primary_photo_id'), 'synthetic-first');
    assert.equal(writes(f)[0].params.get('title'), before.desired_title);
    assert.equal(f.album().title_revision, before.title_revision);
    assert.equal(f.album().first_photo_binding_id, before.first_photo_binding_id);
    assert.equal(f.album().flickr_photoset_id, CREATE_SET); assert.equal(f.album().state, ARCHIVED);
    assert.equal(f.obligation().obligation_id, obligation.obligation_id);
    assert.equal(f.obligation().photo_binding_id, obligation.photo_binding_id);
    assert.equal(f.obligation().state, 'membership_verified');
  });
}

test('ambiguous create remains retained and moves to admin repair after real archival', async t => {
  const f = await materializationFixture(t); f.responses[CREATE] = new Response('synthetic lost result', { status: 502 });
  assert.equal(await f.run(), 'create_outcome_unknown');
  const before = (await attempts(f, 'album_materialization_attempts'))[0];
  await archive(f, before.attempt_id);
  const status = await readAlbumStatus(f.db, { kind: 'installation', ...f.auth }, f.binding);
  assert.equal(status.materialization.repairSurface, 'admin_only');
  assert.equal(status.materialization.createAttemptId, before.attempt_id);
  assert.equal(await f.run(), 'no_work');
  const after = (await attempts(f, 'album_materialization_attempts'))[0];
  assert.equal(after.dispatch_started_at_us, before.dispatch_started_at_us);
  assert.equal(after.dispatch_count, 1); assert.equal(writes(f).length, 1);
  permitted(f, [CONTEXT, CREATE]); assert.equal(f.album().flickr_photoset_id, null);
});

for (const removal of ['album', 'photo']) {
  test(`accepted attachment continues after actual ${removal} archival with exact IDs and one marked add`, async t => {
    const f = await attachment(t), before = await f.obligation();
    if (removal === 'album') await archive(f);
    else await putAlbumPhotoLocalRemoval(f.db, f.auth, f.bindingId, 'later-photo', { schemaVersion: 1,
      expectedBindingRevision: (await binding(f)).binding_revision, expectedObligationRevision: before.obligation_revision });
    assert.equal(await f.run(), 'membership_verified'); assert.equal(await f.run(), 'no_work');
    const after = await f.obligation(); assert.equal(after.obligation_id, before.obligation_id);
    assert.equal(after.photo_binding_id, before.photo_binding_id); assert.equal(after.state, 'membership_verified');
    assert.equal((await binding(f)).flickr_photoset_id, ATTACHMENT_SET);
    assert.equal(writes(f).length, 1); assert.equal(writes(f)[0].params.get('photoset_id'), ATTACHMENT_SET);
    assert.equal(writes(f)[0].params.get('photo_id'), 'later-remote');
    permitted(f, [INFO, CONTEXT, ADD]);
  });
}
test('create ambiguity arising after archive retains original evidence and becomes immediately admin repairable', async t => {
  const f = await materializationFixture(t); await archive(f);
  f.responses[CREATE] = new Response('synthetic lost acknowledgement', { status: 502 });
  assert.equal(await f.run(), 'create_outcome_unknown');
  const attempt = (await attempts(f, 'album_materialization_attempts'))[0];
  const status = await readAlbumStatus(f.db, { kind: 'installation', ...f.auth }, f.binding);
  assert.equal(status.materialization.repairSurface, 'admin_only');
  assert.equal(status.materialization.createAttemptId, attempt.attempt_id);
  assert.equal(status.materialization.state, 'create_outcome_unknown');
  assert.equal(f.album().state, ARCHIVED); assert.equal(f.album().flickr_photoset_id, null);
  assert.equal(f.album().first_photo_binding_id, 'first-photo');
  assert.equal(attempt.dispatch_count, 1); assert(attempt.dispatch_started_at_us > 0);
  assert.equal(await f.run(), 'no_work'); assert.equal(writes(f).length, 1);
  permitted(f, [CONTEXT, CREATE]);
});
