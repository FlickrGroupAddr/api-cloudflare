import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAlbumCreateRepairResolve, parseAlbumCreateRepairPage, albumCreateRepairFailure,
  albumCreateRepairRequest, ALBUM_CREATE_REPAIR_ROUTES, ALBUM_CREATE_REPAIR_RELEASE_METADATA } from '../src/album_create_repair.ts';
const binding = '11111111-1111-4111-8111-111111111111';
const attempt = '22222222-2222-4222-8222-222222222222';
const input = { schemaVersion: 1, expectedBindingRevision: 2, createAttemptId: attempt, selectedPhotosetId: '0007:album@id' };
const path = `/api/v001/album-bindings/${binding}`;
const request = (tail, init = {}) => new Request('https://flickrgroupaddr.com' + path + tail, init);
const auth = { kind: 'installation', installationId: 'synthetic', credentialDigest: 'a'.repeat(64) };
const env = { DB: { prepare() { assert.fail('invalid request must not touch authority storage'); } }, FGA_ALBUM_CREATE_REPAIR_ENABLED: '1' };
async function expectError(response, status, code) {
  assert.equal(response.status, status);
  assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.equal(response.headers.get('Referrer-Policy'), 'no-referrer');
  const value = await response.json(); assert.equal(value.error.code, code);
  assert.deepEqual(Object.keys(value).sort(), ['error', 'schemaVersion']);
  assert.deepEqual(Object.keys(value.error).sort(), ['code', 'correlationId', 'message', 'retryable']);
  assert.match(value.error.correlationId, /^[0-9a-f-]{36}$/);
  assert.equal(value.error.retryable, status === 429 || status === 503);
}
test('resolve parser rejects erased duplicate names and nonexact integer values', () => {
  assert.deepEqual(parseAlbumCreateRepairResolve(JSON.stringify(input)), Object.assign(Object.create(null), input));
  for (const raw of [
    JSON.stringify(input).replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1'),
    JSON.stringify(input).replace('"schemaVersion":1', '"schemaVersion":1,"schema\\u0056ersion":1'),
    JSON.stringify(input).replace('"expectedBindingRevision":2', '"expectedBindingRevision":2.00000000000000001'),
    JSON.stringify(input).replace('"expectedBindingRevision":2', '"expectedBindingRevision":9007199254740993'),
    JSON.stringify({ ...input, selectedPhotosetId: null }), JSON.stringify({ ...input, extra: 'x' }),
    JSON.stringify({ ...input, schemaVersion: 2 }), JSON.stringify({ ...input, createAttemptId: attempt.replace('2', 'A') }),
    JSON.stringify({ ...input, selectedPhotosetId: '../album' }), '[]', 'null', '\ufeff' + JSON.stringify(input),
  ]) assert.throws(() => parseAlbumCreateRepairResolve(raw), /invalid_request/);
  assert.equal(parseAlbumCreateRepairResolve(JSON.stringify(input).replace('"expectedBindingRevision":2', '"expectedBindingRevision":2e0')).expectedBindingRevision, 2);
});
test('page parser accepts only both exact canonical required query members', () => {
  assert.deepEqual(parseAlbumCreateRepairPage(new URL('https://x/?page=1000&page_size=20'), 20), { page: 1000, pageSize: 20 });
  assert.deepEqual(parseAlbumCreateRepairPage(new URL('https://x/?page_size=1&page=1'), 20), { page: 1, pageSize: 1 });
  for (const query of ['', '?page=1', '?page=1&page_size=21', '?page=1001&page_size=1', '?page=01&page_size=1',
    '?page=0&page_size=1', '?page=1&page_size=0', '?page=1&page_size=1&page=1', '?page=%31&page_size=1',
    '?page=1&page_size=%31', '?page=+1&page_size=1', '?page=1e0&page_size=1', '?page=1&page_size=1&',
    '?page=1&page_size=1&extra=1', '?page=9007199254740993&page_size=1'])
    assert.throws(() => parseAlbumCreateRepairPage(new URL('https://x/' + query), 20), /invalid_request/);
});
test('all route variants remain default-off and distinguish administrative authority', async () => {
  assert.equal(ALBUM_CREATE_REPAIR_ROUTES.length, 9); assert.equal(ALBUM_CREATE_REPAIR_RELEASE_METADATA.defaultValue, '0');
  for (const route of ALBUM_CREATE_REPAIR_ROUTES) {
    assert.equal(route.allowPending, false);
    assert.equal(route.auth, route.pathPattern.includes('/admin/') ? 'browser_session' : 'installation_bearer');
  }
  await expectError(await albumCreateRepairRequest({ DB: env.DB }, auth, request('/status'), binding), 503, 'service_unavailable');
  await expectError(await albumCreateRepairRequest(env, { kind: 'admin', sessionId: 's', tokenDigest: 'd', ownerSub: 'sub' }, request('/status'), binding), 401, 'invalid_token');
  await expectError(await albumCreateRepairRequest(env, auth, new Request(`https://flickrgroupaddr.com/api/v001/admin/album-bindings/${binding}/status`), binding), 401, 'unauthorized');
});
test('request framing rejects alternate paths, unexpected queries, methods and GET bodies before DB', async () => {
  for (const [tail, init, id = binding] of [
    ['/status?extra=1', {}], ['/status?', { method: 'HEAD' }], ['/status', { headers: { 'Content-Length': '1' } }],
    ['/status', { headers: { 'Transfer-Encoding': 'chunked' } }], ['/status/', {}], ['/create-repair-resolution', {}],
    ['/create-repair-candidates?page=1&page_size=21', {}], ['/photo-association-status?page=1&page_size=101', {}],
    ['/photo-association-status', {}], ['/status', {}, binding.replace('1', 'A')],
  ]) await expectError(await albumCreateRepairRequest(env, auth, request(tail, init), id), 400, 'invalid_request');
  const alternate = new Request(`https://flickrgroupaddr.com/api/v001/album-bindings/%31${binding.slice(1)}/status`);
  await expectError(await albumCreateRepairRequest(env, auth, alternate, binding), 400, 'invalid_request');
});
test('PUT framing rejects wrong content, duplicate fields, UTF8, size and declared-length mismatch', async () => {
  const valid = JSON.stringify(input);
  const cases = [
    { body: valid, headers: { 'Content-Type': 'text/plain' } },
    { body: valid, headers: { 'Content-Type': 'application/json; charset=latin1' } },
    { body: valid, headers: { 'Content-Type': 'application/json', 'Content-Encoding': 'gzip' } },
    { body: valid, headers: { 'Content-Type': 'application/json', 'Transfer-Encoding': 'chunked' } },
    { body: valid, headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } },
    { body: valid, headers: { 'Content-Type': 'application/json', 'Content-Length': '040' } },
    { body: ' '.repeat(4097), headers: { 'Content-Type': 'application/json' } },
    { body: Uint8Array.of(0xff), headers: { 'Content-Type': 'application/json' } },
    { body: '\ufeff' + valid, headers: { 'Content-Type': 'application/json' } },
    { body: valid.replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1'), headers: { 'Content-Type': 'application/json' } },
  ];
  for (const init of cases) await expectError(await albumCreateRepairRequest(env, auth, request('/create-repair-resolution', { method: 'PUT', ...init }), binding), 400, 'invalid_request');
});
test('closed sanitized errors preserve retry and Bearer distinctions', async () => {
  for (const code of ['candidate_evidence_unavailable', 'resolution_evidence_unavailable', 'service_unavailable']) {
    const response = albumCreateRepairFailure(code); assert.equal(response.headers.get('Retry-After'), '5'); await expectError(response, 503, code);
  }
  const rate = albumCreateRepairFailure('rate_limited', 7); assert.equal(rate.headers.get('Retry-After'), '7'); await expectError(rate, 429, 'rate_limited');
  assert.equal(albumCreateRepairFailure('rate_limited', 0).headers.get('Retry-After'), '5');
  assert.match(albumCreateRepairFailure('invalid_token').headers.get('WWW-Authenticate'), /error="invalid_token"/);
  assert.equal(albumCreateRepairFailure('unauthorized').headers.get('WWW-Authenticate'), null);
  await expectError(albumCreateRepairFailure('raw provider secret'), 503, 'service_unavailable');
});
