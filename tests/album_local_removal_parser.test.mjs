import test from 'node:test';
import assert from 'node:assert/strict';
import { parsePhotoLocalRemoval, parseAlbumLocalRemoval, albumLocalRemovalRequest, albumLocalRemovalFailure,
  ALBUM_LOCAL_REMOVAL_ROUTES, ALBUM_LOCAL_REMOVAL_RELEASE_METADATA, photoLocalRemovalReceiptProjection, albumLocalRemovalReceiptProjection } from '../src/album_local_removal.ts';

const ID = '11111111-1111-4111-8111-111111111111';
const ATTEMPT = '22222222-2222-4222-8222-222222222222';
const photo = { schemaVersion: 1, expectedBindingRevision: 1, expectedObligationRevision: 2 };
const album = { schemaVersion: 1, expectedBindingRevision: 1, acknowledgedCreateAttemptId: null };
const path = pair => `/api/v001/album-bindings/${ID}/${pair ? 'photo-associations/primary-photo/' : ''}local-removal`;
const request = (target, raw, options = {}) => new Request('https://flickrgroupaddr.com' + target, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: raw, ...options,
});
async function failure(response, status, code) {
  assert.equal(response.status, status); assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff'); assert.equal(response.headers.get('Referrer-Policy'), 'no-referrer');
  const raw = await response.text(); assert(Buffer.byteLength(raw) <= 1024); const body = JSON.parse(raw);
  assert.deepEqual(Object.keys(body).sort(), ['error', 'schemaVersion']);
  assert.deepEqual(Object.keys(body.error).sort(), ['code', 'correlationId', 'message', 'retryable']);
  assert.equal(body.schemaVersion, 1); assert.equal(body.error.code, code); assert.equal(body.error.retryable, status === 429 || status === 503);
  assert.match(body.error.correlationId, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  return body;
}

test('closed removal parsers require every exact member and positive safe integer fences', () => {
  for (const [parse, input] of [[parsePhotoLocalRemoval, photo], [parseAlbumLocalRemoval, album]]) {
    assert.deepEqual(parse(JSON.stringify(input)), input);
    for (const key of Object.keys(input)) {
      const missing = { ...input }; delete missing[key]; assert.throws(() => parse(JSON.stringify(missing)), /invalid_request/);
      if (key !== 'acknowledgedCreateAttemptId') assert.throws(() => parse(JSON.stringify({ ...input, [key]: null })), /invalid_request/);
    }
    for (const value of [{ ...input, extra: 1 }, { ...input, schemaVersion: 2 }, { ...input, expectedBindingRevision: 0 },
      { ...input, expectedBindingRevision: -1 }, { ...input, expectedBindingRevision: 1.5 },
      { ...input, expectedBindingRevision: '1' }, { ...input, expectedBindingRevision: Number.MAX_SAFE_INTEGER + 1 }, [], null])
      assert.throws(() => parse(JSON.stringify(value)), /invalid_request/);
    assert.equal(parse(JSON.stringify({ ...input, expectedBindingRevision: Number.MAX_SAFE_INTEGER })).expectedBindingRevision, Number.MAX_SAFE_INTEGER);
    assert.equal(parse(JSON.stringify(input).replace('"expectedBindingRevision":1', '"expectedBindingRevision":1e0')).expectedBindingRevision, 1);
    for (const raw of [JSON.stringify(input).replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1'),
      JSON.stringify(input).replace('"schemaVersion":1', '"schemaVersion":1,"schema\\u0056ersion":1'),
      JSON.stringify(input).replace('"expectedBindingRevision":1', '"expectedBindingRevision":1.00000000000000001'),
      JSON.stringify(input).replace('"expectedBindingRevision":1', '"expectedBindingRevision":9007199254740993'),
      '\ufeff' + JSON.stringify(input), ' '.repeat(4097), '{', 'true']) assert.throws(() => parse(raw), /invalid_request/);
  }
  assert.equal(parseAlbumLocalRemoval(JSON.stringify({ ...album, acknowledgedCreateAttemptId: ATTEMPT })).acknowledgedCreateAttemptId, ATTEMPT);
  for (const value of ['', 1, false, [], 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', 'not-a-uuid']) {
    if (value === ATTEMPT) continue;
    assert.throws(() => parseAlbumLocalRemoval(JSON.stringify({ ...album, acknowledgedCreateAttemptId: value })), /invalid_request/);
  }
  for (const value of [0, -1, 1.1, '1', Number.MAX_SAFE_INTEGER + 1])
    assert.throws(() => parsePhotoLocalRemoval(JSON.stringify({ ...photo, expectedObligationRevision: value })), /invalid_request/);
});

test('default-off and malformed removal framing cannot touch storage', async () => {
  const db = new Proxy({}, { get() { assert.fail('malformed/default-off request touched database'); } });
  const auth = { installationId: 'install', credentialDigest: 'a'.repeat(64) }, env = { DB: db, FGA_ALBUM_LOCAL_REMOVAL_ENABLED: '1' };
  await failure(await albumLocalRemovalRequest({ DB: db }, auth, request(path(false), JSON.stringify(album)), ID), 503, 'service_unavailable');
  assert.equal(ALBUM_LOCAL_REMOVAL_RELEASE_METADATA.defaultValue, '0'); assert.equal(ALBUM_LOCAL_REMOVAL_ROUTES.length, 2);
  for (const route of ALBUM_LOCAL_REMOVAL_ROUTES) { assert.equal(route.auth, 'installation_bearer'); assert.equal(route.allowPending, false); assert.equal(route.method, 'PUT'); }
  for (const pair of [false, true]) {
    const raw = JSON.stringify(pair ? photo : album), target = path(pair);
    for (const [url, body, options] of [[target + '?x=1', raw, {}], [target + '/', raw, {}],
      [target.replace(ID, '%31' + ID.slice(1)), raw, {}], [target, raw, { method: 'POST' }],
      [target, raw, { headers: { 'Content-Type': 'text/plain' } }],
      [target, raw, { headers: { 'Content-Type': 'application/json; charset=latin1' } }],
      [target, raw, { headers: { 'Content-Type': 'application/json', 'Content-Encoding': 'gzip' } }],
      [target, raw, { headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } }],
      [target, raw, { headers: { 'Content-Type': 'application/json', 'Transfer-Encoding': 'chunked' } }],
      [target, ' '.repeat(4097), {}], [target, Uint8Array.of(0xff), {}], [target, '\ufeff' + raw, {}]])
      await failure(await albumLocalRemovalRequest(env, auth, request(url, body, options), ID, pair ? 'primary-photo' : undefined), 400, 'invalid_request');
    if (pair) await failure(await albumLocalRemovalRequest(env, auth, request(target.replace('primary-photo', '%70rimary-photo'), raw), ID, 'primary-photo'), 400, 'invalid_request');
  }
});

test('removal errors use finite sanitized no-store envelopes and retry policy', async () => {
  for (const [code, status] of [['invalid_request', 400], ['invalid_token', 401], ['insufficient_scope', 403],
    ['resource_not_found', 404], ['stale_binding_revision', 409], ['stale_obligation_revision', 409],
    ['removal_acknowledgement_required', 409], ['removal_acknowledgement_conflict', 409], ['revision_exhausted', 409],
    ['rate_limited', 429], ['service_unavailable', 503]]) {
    const response = albumLocalRemovalFailure(code); await failure(response, status, code);
    if (status === 401 || status === 403) assert.match(response.headers.get('WWW-Authenticate'), new RegExp(code));
    if (status === 429 || status === 503) assert.equal(response.headers.get('Retry-After'), '5');
  }
  await failure(albumLocalRemovalFailure('private upstream text'), 503, 'service_unavailable');
});

const NOW = '2026-10-17T12:00:00.000000Z';
function current(archived = false) {
  return { schemaVersion: 1, binding: { schemaVersion: 1, fgaAlbumBindingId: ID, fgaPublishServiceId: ATTEMPT,
    localCollectionIdentifier: 'Album', linkedFlickrRevision: 1, bindingRevision: 3, titleRevision: 1,
    desiredTitle: 'Exact title', firstPhotoBindingId: 'primary-photo', flickrPhotosetId: null },
    localLifecycle: archived ? 'local_collection_removed_remote_preserved' : 'active',
    title: { state: archived ? 'local_removed' : 'waiting_for_materialization', observedTitle: null, observedAt: null, dispatchTitleRevision: null, dispatchAttemptId: null },
    unresolvedCreateAttemptId: null, repairHandoff: { destination: 'none', fgaAlbumBindingId: ID, createAttemptId: null, acknowledgedAt: null } };
}
const pairReceipt = () => ({ schemaVersion: 1, obligation: { fgaAlbumObligationId: ATTEMPT, fgaAlbumBindingId: ID,
  fgaPhotoBindingId: 'primary-photo', obligationRevision: 2 }, localRelationship: 'archived', archivedAt: NOW, acceptedBindingRevision: 2, current: current() });
const albumReceipt = () => ({ schemaVersion: 1, fgaAlbumBindingId: ID, localLifecycle: 'local_collection_removed_remote_preserved',
  archivedAt: NOW, acceptedBindingRevision: 2, repairHandoff: { destination: 'none', fgaAlbumBindingId: ID, createAttemptId: null, acknowledgedAt: null }, current: current(true) });

test('removal projections close every object and retain exact requested pair identities', () => {
  assert.deepEqual(photoLocalRemovalReceiptProjection(pairReceipt(), ID, 'primary-photo'), pairReceipt());
  assert.deepEqual(albumLocalRemovalReceiptProjection(albumReceipt(), ID), albumReceipt());
  for (const [make, project] of [[pairReceipt, value => photoLocalRemovalReceiptProjection(value, ID, 'primary-photo')],
    [albumReceipt, value => albumLocalRemovalReceiptProjection(value, ID)]]) {
    for (const mutate of [v => v.extra = 1, v => v.schemaVersion = 2, v => v.current.extra = 1,
      v => v.current.binding.extra = 1, v => v.current.title.extra = 1, v => v.current.repairHandoff.extra = 1,
      v => v.archivedAt = '2026-02-30T12:00:00.000000Z', v => v.archivedAt = '2026-10-17T12:00:00.000Z',
      v => v.acceptedBindingRevision = 4, v => v.current.binding.fgaAlbumBindingId = ATTEMPT,
      v => v.current.title.observedAt = NOW, v => v.current.repairHandoff.fgaAlbumBindingId = ATTEMPT,
      v => { v.current.title.observedTitle = '🏊'.repeat(1025); v.current.title.observedAt = NOW; }]) {
      const value = make(); mutate(value); assert.throws(() => project(value), /integrity/);
    }
    for (const key of Object.keys(make())) { const value = make(); delete value[key]; assert.throws(() => project(value), /integrity/); }
  }
  for (const mutate of [v => v.obligation.extra = 1, v => v.obligation.fgaPhotoBindingId = 'foreign-photo',
    v => v.obligation.fgaAlbumBindingId = ATTEMPT, v => v.obligation.obligationRevision = 0, v => v.localRelationship = 'active']) {
    const value = pairReceipt(); mutate(value); assert.throws(() => photoLocalRemovalReceiptProjection(value, ID, 'primary-photo'), /integrity/);
  }
  for (const mutate of [v => v.fgaAlbumBindingId = ATTEMPT, v => v.repairHandoff.extra = 1,
    v => v.repairHandoff.createAttemptId = ATTEMPT, v => v.repairHandoff.acknowledgedAt = NOW,
    v => v.current = current(), v => v.repairHandoff.fgaAlbumBindingId = ATTEMPT]) {
    const value = albumReceipt(); mutate(value); assert.throws(() => albumLocalRemovalReceiptProjection(value, ID), /integrity/);
  }
  const receipt = albumReceipt(); receipt.repairHandoff = { destination: 'administrative_album_create_repair', fgaAlbumBindingId: ID, createAttemptId: ATTEMPT, acknowledgedAt: NOW };
  assert.deepEqual(albumLocalRemovalReceiptProjection(receipt, ID), receipt);
  receipt.repairHandoff.acknowledgedAt = '2026-10-17T12:00:01.000000Z'; assert.throws(() => albumLocalRemovalReceiptProjection(receipt, ID), /integrity/);
});
