import test from 'node:test';
import assert from 'node:assert/strict';
import { readJson, signedAlbumRest, FlickrReadError } from '../src/flickr_reads.ts';
import { strictFlickrJson } from '../src/flickr_strict_json.ts';
import { verifyInfo } from '../src/album_materialization_transport.ts';

const KiB = 1024, MiB = 1024 * KiB;
const request = () => new Request('https://www.flickr.com/services/rest/');
const jsonResponse = body => new Response(body, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
const pair = { token: 'synthetic-token', tokenSecret: 'synthetic-token-secret' };
const app = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' };
const bytes = text => new TextEncoder().encode(text);
const flush = () => new Promise(resolve => setImmediate(resolve));

test('shared Album signer closes title and attachment POST methods over exact parameter sets', async () => {
  for (const [method, data] of [
    ['flickr.photosets.editMeta', { photoset_id: 'set-id', title: 'Title & + 日本語' }],
    ['flickr.photosets.addPhoto', { photoset_id: 'set-id', photo_id: 'photo-id' }],
  ]) {
    const signed = signedAlbumRest(method, data, pair, app);
    assert.equal(signed.url, 'https://www.flickr.com/services/rest/');
    assert.equal(signed.method, 'POST');
    assert.equal(signed.redirect, 'manual');
    assert.equal(signed.headers.get('Content-Type'), 'application/x-www-form-urlencoded');
    assert.match(signed.headers.get('Authorization'), /oauth_signature="[^"\s]+"/);
    const body = new URLSearchParams(await signed.text());
    assert.deepEqual(Object.fromEntries(body), { method, format: 'json', nojsoncallback: '1', ...data });
    assert.equal([...body].length, Object.keys(data).length + 3);
    for (const bad of [{ ...data, description: 'Forbidden' }, { ...data, extra: 'Forbidden' }, {}, { ...data, photoset_id: '' }])
      assert.throws(() => signedAlbumRest(method, bad, pair, app), FlickrReadError);
  }
  assert.throws(() => signedAlbumRest('flickr.photosets.delete', { photoset_id: 'set-id' }, pair, app), FlickrReadError);
});

test('bounded JSON readers retain 256 KiB default and permit explicit bodies through 1 MiB only', async () => {
  const body = JSON.stringify({ title: 'x'.repeat(300 * KiB) });
  assert.throws(() => strictFlickrJson(body));
  await assert.rejects(readJson(request(), async () => jsonResponse(body)), FlickrReadError);
  const value = await readJson(request(), async () => jsonResponse(body), raw => strictFlickrJson(raw, MiB), { maxBytes: MiB });
  assert.equal(value.title.length, 300 * KiB);
  const exact = JSON.stringify({ x: 'x'.repeat(MiB - 8) });
  assert.equal(bytes(exact).length, MiB);
  assert.equal(strictFlickrJson(exact, MiB).x.length, MiB - 8);
  await readJson(request(), async () => jsonResponse(exact), raw => strictFlickrJson(raw, MiB), { maxBytes: MiB });
  assert.throws(() => strictFlickrJson(exact + ' ', MiB));
  await assert.rejects(readJson(request(), async () => jsonResponse(exact + ' '), undefined, { maxBytes: MiB }), FlickrReadError);
  for (const maxBytes of [0, -1, 1.5, NaN, Infinity, MiB + 1]) {
    assert.throws(() => strictFlickrJson('{}', maxBytes));
    await assert.rejects(readJson(request(), assert.fail, undefined, { maxBytes }), FlickrReadError);
  }
});

test('larger strict parser preserves duplicate, exact numeric, Unicode and byte guards', () => {
  for (const raw of ['{"stat":"ok","stat":"fail"}', '{"a":1.00000000000000001}', '{"a":9007199254740992}', '{"a":1e999}', '{"a":"\\ud800"}', '{"\\udc00":1}', '\ufeff{}'])
    assert.throws(() => strictFlickrJson(raw, MiB));
  assert.throws(() => strictFlickrJson(JSON.stringify({ a: 'é'.repeat(140 * KiB) })));
  assert.equal(strictFlickrJson('{"a":1.00,"b":"\\ud83d\\ude00"}', MiB).a, 1);
});

test('default decoder still accepts UTF8 BOM and custom strict decoder rejects it', async () => {
  assert.deepEqual(await readJson(request(), async () => jsonResponse('\ufeff{"stat":"ok"}')), { stat: 'ok' });
  await assert.rejects(readJson(request(), async () => jsonResponse('\ufeff{"stat":"ok"}'), strictFlickrJson), FlickrReadError);
  await assert.rejects(readJson(request(), async () => jsonResponse(new Uint8Array([255]))), FlickrReadError);
});

test('incremental byte callback counts chunks and can enforce aggregate budget while cancelling body', async () => {
  const seen = [];
  const chunks = [bytes('{"stat":'), bytes('"ok"}')];
  const stream = new ReadableStream({ start(controller) { for (const part of chunks) controller.enqueue(part); controller.close(); } });
  await readJson(request(), async () => jsonResponse(stream), strictFlickrJson, { onBytes: n => seen.push(n) });
  assert.deepEqual(seen, chunks.map(part => part.byteLength));
  let cancelled = 0, received = 0;
  const over = new ReadableStream({ start(controller) { controller.enqueue(bytes('{} ')); }, cancel() { cancelled++; } });
  await assert.rejects(readJson(request(), async () => jsonResponse(over), undefined, { onBytes: n => { received += n; if (received > 2) throw new Error('aggregate_budget'); } }), FlickrReadError);
  assert.equal(received, 3);
  assert.equal(cancelled, 1);
});

test('preaborted request or option signal prevents fetch and byte callbacks', async () => {
  const controller = new AbortController(); controller.abort();
  for (const [req, options] of [[new Request(request(), { signal: controller.signal }), {}], [request(), { signal: controller.signal }]])
    await assert.rejects(readJson(req, assert.fail, undefined, { ...options, onBytes: assert.fail }), FlickrReadError);
});

test('request and option abort cancel stalled readers promptly without later byte callbacks', async () => {
  for (const throughRequest of [false, true]) {
    const controller = new AbortController();
    let cancelled = 0, seen = 0;
    const stream = new ReadableStream({ start(c) { c.enqueue(bytes('{')); }, cancel() { cancelled++; } });
    const req = throughRequest ? new Request(request(), { signal: controller.signal }) : request();
    const pending = readJson(req, async () => jsonResponse(stream), undefined, { ...(throughRequest ? {} : { signal: controller.signal }), onBytes: n => seen += n });
    await flush();
    assert.equal(seen, 1);
    controller.abort();
    await assert.rejects(pending, FlickrReadError);
    await flush();
    assert.equal(cancelled, 1);
    assert.equal(seen, 1);
  }
});

test('whole-read deadline rejects signal-ignoring fetch and cancels any late response', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let resolveFetch, sentSignal, cancelled = 0;
  const pending = readJson(request(), async req => { sentSignal = req.signal; return new Promise(resolve => resolveFetch = resolve); }, undefined, { onBytes: assert.fail });
  t.mock.timers.tick(10_000);
  await assert.rejects(pending, FlickrReadError);
  assert.equal(sentSignal.aborted, true);
  resolveFetch(jsonResponse(new ReadableStream({ cancel() { cancelled++; } })));
  await flush();
  assert.equal(cancelled, 1);
});

test('abort triggered inside a byte callback prevents decode and further callbacks', async () => {
  const controller = new AbortController();
  let count = 0, cancelled = 0;
  const stream = new ReadableStream({ start(c) { c.enqueue(bytes('{')); c.enqueue(bytes('}')); }, cancel() { cancelled++; } });
  await assert.rejects(readJson(request(), async () => jsonResponse(stream), assert.fail, { signal: controller.signal, onBytes: () => { count++; controller.abort(); } }), FlickrReadError);
  assert.equal(count, 1);
  assert.equal(cancelled, 1);
});

test('exported getInfo validator retains complete schema and exact identity checks', () => {
  const info = { stat: 'ok', photoset: { id: 'set-id', owner: 'owner@N00', primary: 'changed-primary', title: { _content: 'Title' }, description: { _content: '' } } };
  verifyInfo(info, 'set-id', 'owner@N00');
  for (const bad of [
    { ...info, stat: 'fail' }, { ...info, extra: true },
    { ...info, photoset: { ...info.photoset, id: 'other' } },
    { ...info, photoset: { ...info.photoset, owner: 'other' } },
    { ...info, photoset: { ...info.photoset, title: { _content: 'Title', extra: true } } },
    { ...info, photoset: { ...info.photoset, description: { _content: '\ud800' } } },
  ]) assert.throws(() => verifyInfo(bad, 'set-id', 'owner@N00'));
});
