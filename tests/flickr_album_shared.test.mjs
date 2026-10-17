import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { signedAlbumRest, signedRead, readJson } from '../src/flickr_reads.ts';
import { strictFlickrJson } from '../src/flickr_strict_json.ts';

const pair = { token: 'synthetic-token', tokenSecret: 'synthetic-secret&+' };
const app = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-app-secret/' };
const endpoint = 'https://www.flickr.com/services/rest/';
const encode = value => encodeURIComponent(value).replace(/[!'()*]/g, char => `%${char.charCodeAt(0).toString(16).toUpperCase()}`);
const response = raw => new Response(raw, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
const jsonRequest = () => new Request(endpoint);

async function verifySignature(request, expected) {
  assert.equal(request.redirect, 'manual');
  assert.equal(request.headers.get('Accept'), 'application/json');
  const url = new URL(request.url);
  assert.equal(`${url.origin}${url.pathname}`, endpoint);
  const params = request.method === 'POST' ? new URLSearchParams(await request.text()) : url.searchParams;
  if (request.method === 'POST') {
    assert.equal(url.search, '');
    assert.equal(request.headers.get('Content-Type'), 'application/x-www-form-urlencoded');
  } else assert.equal(request.body, null);
  assert.deepEqual(Object.fromEntries(params), { method: expected.method, format: 'json', nojsoncallback: '1', ...expected.data });
  const authorization = request.headers.get('Authorization');
  assert.match(authorization, /^OAuth /);
  const oauth = Object.fromEntries([...authorization.matchAll(/(oauth_[a-z_]+)="([^"]*)"/g)].map(([, key, value]) => [key, decodeURIComponent(value)]));
  assert.match(oauth.oauth_nonce, /^[a-f0-9]{64}$/);
  assert.equal(oauth.oauth_consumer_key, app.consumerKey);
  assert.equal(oauth.oauth_token, pair.token);
  assert.equal(oauth.oauth_signature_method, 'HMAC-SHA1');
  const signature = oauth.oauth_signature;
  delete oauth.oauth_signature;
  const normalized = [...params, ...Object.entries(oauth)].map(([key, value]) => [encode(key), encode(value)])
    .sort(([ak, av], [bk, bv]) => ak < bk ? -1 : ak > bk ? 1 : av < bv ? -1 : av > bv ? 1 : 0)
    .map(([key, value]) => `${key}=${value}`).join('&');
  const base = `${request.method}&${encode(endpoint)}&${encode(normalized)}`;
  assert.equal(signature, createHmac('sha1', `${encode(app.consumerSecret)}&${encode(pair.tokenSecret)}`).update(base).digest('base64'));
  return oauth.oauth_nonce;
}

test('actual fixed-operation signer binds exact GET query and POST form into OAuth signature', async () => {
  const nonces = [];
  for (const expected of [
    { method: 'flickr.photos.getAllContexts', data: { photo_id: 'opaque-photo' } },
    { method: 'flickr.photosets.getInfo', data: { photoset_id: 'opaque-set' } },
    { method: 'flickr.photosets.create', data: { title: "A title & plus+ / café 😀 !'()*", primary_photo_id: 'opaque-photo' } },
  ]) {
    const request = signedAlbumRest(expected.method, expected.data, pair, app);
    assert.equal(request.method, expected.method.endsWith('.create') ? 'POST' : 'GET');
    nonces.push(await verifySignature(request, expected));
  }
  assert.equal(new Set(nonces).size, nonces.length);
});

test('signer refuses method/key expansion and malformed values', () => {
  for (const [method, data] of [
    ['flickr.photos.delete', { photo_id: 'photo' }], ['flickr.photosets.create', { title: 'x' }],
    ['flickr.photosets.create', { title: 'x', primary_photo_id: 'photo', description: 'extra' }],
    ['flickr.photosets.getInfo', { photoset_id: 'set', photo_id: 'photo' }],
    ['flickr.photos.getAllContexts', { photo_id: 1 }], ['flickr.photos.getAllContexts', { photo_id: '' }],
    ['flickr.photosets.create', { title: '\ud800', primary_photo_id: 'photo' }],
  ]) assert.throws(() => signedAlbumRest(method, data, pair, app), /upstream_unavailable/);
  const read = signedRead('flickr.photos.getInfo', 'photo', pair, app);
  assert.equal(read.method, 'GET');
  assert.equal(new URL(read.url).searchParams.get('photo_id'), 'photo');
});

test('strict provider grammar decodes complete nested JSON and prototype-named keys', () => {
  const raw = '{"stat":"ok","set":[{"id":"set","title":"café \\ud83d\\ude00"}],"pool":[],"metadata":{"__proto__":null,"constructor":true,"fraction":-0.125,"false":false}}';
  const decoded = strictFlickrJson(raw);
  assert.deepEqual(JSON.parse(JSON.stringify(decoded)), JSON.parse(raw));
  assert.equal(Object.getPrototypeOf(decoded.metadata), null);
  for (const literal of ['1', '98.000', '9.8e1', '980e-1', '9007199254740991', '-98', '0', '-0', '1.25', '1e-5'])
    assert.equal(strictFlickrJson(literal), JSON.parse(literal));
});

test('strict provider grammar refuses decoded duplicates at every nesting level', () => {
  for (const raw of ['{"stat":"ok","stat":"fail"}', '{"stat":"ok","\\u0073tat":"fail"}',
    '{"set":[{"id":"first","\\u0069d":"second"}]}', '{"set":[[{"title":"a","title":"b"}]]}',
    '{"metadata":{"__proto__":1,"\\u005f_proto__":2}}']) assert.throws(() => strictFlickrJson(raw));
});

test('strict provider grammar refuses BOM, invalid Unicode, malformed grammar and resource excess', () => {
  for (const raw of ['\ufeff{}', '{"x":"\\ud800"}', '{"x":"\\udc00"}', '{"x":"\ud800"}',
    '{"x":"\\uZZZZ"}', '{"x":"a\nb"}', '{"x":01}', '{"x":+1}', '{"x":.1}', '{"x":1.}',
    '{"x":true,}', '[1,]', '{}{}', '{"x":undefined}', 'NaN', 'Infinity', '1e999',
    '['.repeat(66) + 'null' + ']'.repeat(66), ' '.repeat(262145), `"${'😀'.repeat(65536)}"`])
    assert.throws(() => strictFlickrJson(raw));
});

test('rounded numeric tokens cannot establish recognized integer rejection/status evidence', () => {
  for (const token of ['98.000000000000000001', '97.999999999999999999', '98000000000000000001e-18',
    '9007199254740992', '9007199254740993', '1e-999', '0.999999999999999999999999'])
    assert.throws(() => strictFlickrJson(`{"code":${token}}`));
});

test('readJson strict decoder keeps byte/UTF-8/root guards and default reader behavior', async () => {
  const duplicate = '{"stat":"ok","stat":"fail"}';
  assert.equal((await readJson(jsonRequest(), async () => response(duplicate))).stat, 'fail');
  assert.deepEqual(await readJson(jsonRequest(), async () => response('\ufeff{}')), {});
  for (const raw of [duplicate, '\ufeff{}', '[]', 'null', '{"x":"\\ud800"}', '{"code":98.000000000000000001}'])
    await assert.rejects(readJson(jsonRequest(), async () => response(raw), strictFlickrJson), /upstream_unavailable/);
  for (const bytes of [new Uint8Array([0xff]), new Uint8Array([0xed, 0xa0, 0x80]), new Uint8Array(262145)])
    await assert.rejects(readJson(jsonRequest(), async () => response(bytes), strictFlickrJson), /upstream_unavailable/);
  const good = await readJson(jsonRequest(), async () => response('{"stat":"ok","set":[],"pool":[]}'), strictFlickrJson);
  assert.equal(good.stat, 'ok');
  assert.deepEqual(good.set, []);
});
