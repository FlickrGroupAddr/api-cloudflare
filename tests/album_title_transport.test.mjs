import test from 'node:test';
import assert from 'node:assert/strict';
import { albumTitleObservation, createSyntheticAlbumTitleTransport, AlbumTitleMissingError, AlbumTitleTransportError } from '../src/album_title_transport.ts';
import { signedAlbumRest } from '../src/flickr_reads.ts';

const identity = { photosetId: 'set-id', ownerNsid: 'owner@N00', title: 'Exact 🏊 &+ e\u0301' };
const pair = { token: 'synthetic-token', tokenSecret: 'synthetic-token-secret' };
const app = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' };
const info = title => ({ stat: 'ok', photoset: { id: identity.photosetId, owner: identity.ownerNsid,
  primary: 'photo-id', title: { _content: title }, description: { _content: 'Remote\nmaintained description' } } });
const sign = (method, data) => signedAlbumRest(method, data, pair, app);
function fixture(overrides = {}, input = identity) {
  const requests = [], gates = [];
  const deps = { sign, assertCurrent: async () => {}, beforeRequest: async method => { gates.push(method); },
    execution: { signal: new AbortController().signal, remainingMs: () => 10_000 },
    fetcher: async request => { requests.push(request); return Response.json(request.method === 'POST' ? { stat: 'ok' } : info('Original')); }, ...overrides };
  return { transport: createSyntheticAlbumTitleTransport(input, deps), requests, gates };
}
test('factory is dormant and validates fixed identity and bounded Unicode desired title', () => {
  assert.throws(() => createSyntheticAlbumTitleTransport(identity));
  for (const bad of [{ ...identity, photosetId: '0' }, { ...identity, ownerNsid: 'owner\n' }, { ...identity, title: '' },
    { ...identity, title: '\ud800' }, { ...identity, title: '\u0000' }, { ...identity, title: 'x'.repeat(1001) }])
    assert.throws(() => fixture({}, bad));
  assert.throws(() => fixture({ beforeRequest: undefined }));
  assert.throws(() => fixture({ deadlineMs: 10001 }));
});
test('complete evidence preserves exact Unicode and empty remote title, refuses owner/id/root/nested defects', () => {
  for (const title of ['', identity.title, '界'.repeat(1365) + 'x'])
    assert.deepEqual(albumTitleObservation(info(title), identity.photosetId, identity.ownerNsid), { ...identity, title });
  for (const title of ['界'.repeat(1366), '\udfff', 'bad\n']) assert.throws(() => albumTitleObservation(info(title), identity.photosetId, identity.ownerNsid));
  for (const mutate of [v => { v.photoset.owner = 'other'; }, v => { v.photoset.id = 'other'; },
    v => { delete v.photoset.primary; }, v => { v.extra = 1; }, v => { v.photoset.title.extra = 1; },
    v => { v.photoset.description = null; }, v => { v.photoset.unknown = {}; }]) {
    const value = info('Original'); mutate(value); assert.throws(() => albumTitleObservation(value, identity.photosetId, identity.ownerNsid));
  }
});
test('only exact documented missing response is classified missing', () => {
  assert.throws(() => albumTitleObservation({ stat: 'fail', code: 1, message: 'Missing' }, identity.photosetId, identity.ownerNsid), AlbumTitleMissingError);
  for (const value of [{ stat: 'fail', code: '1', message: 'Missing' }, { stat: 'fail', code: 1, message: 'Missing', photoset: {} }, { stat: 'fail', code: 105, message: 'Unavailable' }])
    assert.throws(() => albumTitleObservation(value, identity.photosetId, identity.ownerNsid), error => error instanceof AlbumTitleTransportError && !(error instanceof AlbumTitleMissingError));
});
test('actual signer and one-shot prepared edit preserve immutable exact identity and omit description', async () => {
  const original = { ...identity }, f = fixture({}, original);
  original.title = 'Mutated'; original.photosetId = 'other';
  assert.equal((await f.transport.read()).title, 'Original');
  const prepared = await f.transport.prepareEdit();
  assert.equal(f.requests.length, 1);
  await prepared.handoff();
  await assert.rejects(prepared.handoff());
  await assert.rejects(f.transport.prepareEdit());
  assert.equal(f.requests.length, 2);
  const req = f.requests[1], data = new URLSearchParams(await req.clone().text());
  assert.equal(req.method, 'POST'); assert.equal(req.redirect, 'manual');
  assert.match(req.headers.get('Authorization'), /^OAuth /);
  assert.deepEqual(Object.fromEntries(data), { method: 'flickr.photosets.editMeta', format: 'json', nojsoncallback: '1', photoset_id: identity.photosetId, title: identity.title });
  assert.equal((await f.transport.read()).title, 'Original');
  assert.deepEqual(f.gates, ['flickr.photosets.getInfo', 'flickr.photosets.editMeta', 'flickr.photosets.getInfo']);
});
test('pre-read failure, current/grant fence, fault/rate denial and disposed request prevent POST', async () => {
  for (const overrides of [{ assertCurrent: async () => { throw Error('stale'); } }, { beforeRequest: async () => { throw Error('rate'); } },
    { fetcher: async () => Response.json({ stat: 'ok' }) }]) {
    const f = fixture(overrides); await assert.rejects(f.transport.prepareEdit()); await assert.rejects(f.transport.read()); await assert.rejects(f.transport.prepareEdit()); assert.equal(f.requests.length, 0);
  }
  const f = fixture(); await f.transport.read(); const prepared = await f.transport.prepareEdit(); prepared.dispose(); await assert.rejects(prepared.handoff()); assert.equal(f.requests.length, 1);
});
test('untrusted signer cannot add description, duplicate title, redirect or change method/identity/endpoint', async () => {
  for (const change of ['description', 'duplicate', 'id', 'host', 'redirect', 'method']) {
    let calls = 0;
    const f = fixture({ sign: (method, data) => {
      if (method !== 'flickr.photosets.editMeta') return sign(method, data);
      const params = new URLSearchParams({ method, format: 'json', nojsoncallback: '1', ...data });
      if (change === 'description') params.set('description', '');
      if (change === 'duplicate') params.append('title', data.title);
      if (change === 'id') params.set('photoset_id', 'other');
      return new Request(change === 'host' ? 'https://example.com/services/rest/' : 'https://www.flickr.com/services/rest/', {
        method: change === 'method' ? 'PUT' : 'POST', body: params.toString(), redirect: change === 'redirect' ? 'follow' : 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
    }, fetcher: async () => { calls++; return Response.json(info('Original')); } });
    await f.transport.read(); await assert.rejects(f.transport.prepareEdit()); assert.equal(calls, 1);
  }
});
test('strict body parsing rejects duplicates, trailing data, invalid UTF8 and >1MiB; accepts complete larger body', async () => {
  const validLarge = JSON.stringify(info('Original')).replace('Remote\\nmaintained description', 'x'.repeat(300_000));
  assert.equal((await fixture({ fetcher: async () => new Response(validLarge, { headers: { 'Content-Type': 'application/json' } }) }).transport.read()).title, 'Original');
  for (const raw of ['{"stat":"ok","stat":"ok","photoset":{}}', JSON.stringify(info('x')) + '{}',
    new Uint8Array([255]), ' '.repeat(1_048_577)]) {
    let calls = 0; const f = fixture({ fetcher: async () => { calls++; return new Response(raw, { headers: { 'Content-Type': 'application/json' } }); } });
    await assert.rejects(f.transport.read()); assert.equal(calls, 1);
  }
});
test('POST ambiguity retains a read-only reconciliation path without a second write', async () => {
  for (const body of ['', '{"stat":"fail","code":105,"message":"Unavailable"}', '{"stat":"ok","extra":1}']) {
    let posts = 0;
    const f = fixture({ fetcher: async req => { if (req.method === 'POST') { posts++; return new Response(body, { headers: { 'Content-Type': 'application/json' } }); } return Response.json(info('After')); } });
    await f.transport.read(); const prepared = await f.transport.prepareEdit(); await assert.rejects(prepared.handoff());
    assert.equal((await f.transport.read()).title, 'After'); await assert.rejects(prepared.handoff()); assert.equal(posts, 1);
  }
});
test('whole execution deadline settles ignored fetch/body/gate and never retries', async () => {
  for (const stall of ['fetch', 'body', 'gate']) {
    let calls = 0;
    const f = fixture({ deadlineMs: 15, ...(stall === 'gate' ? { beforeRequest: async () => new Promise(() => {}) } : {}),
      fetcher: async () => { calls++; return stall === 'fetch' ? new Promise(() => {}) : new Response(new ReadableStream({ start() {} }), { headers: { 'Content-Type': 'application/json' } }); } });
    await assert.rejects(f.transport.read()); assert.equal(calls, stall === 'gate' ? 0 : 1);
  }
});
test('worker execution abort and remaining budget constrain every call and prevent late network entry', async () => {
  const controller = new AbortController();
  let calls = 0, resume;
  const f = fixture({ execution: { signal: controller.signal, remainingMs: () => 1000 },
    beforeRequest: async () => new Promise(resolve => { resume = resolve; }),
    fetcher: async () => { calls++; return Response.json(info('Late')); } });
  const pending = f.transport.read();
  controller.abort(); await assert.rejects(pending); resume();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 0);
  for (const remaining of [0, -1, NaN, Infinity]) {
    const expired = fixture({ execution: { signal: new AbortController().signal, remainingMs: () => remaining } });
    await assert.rejects(expired.transport.read()); assert.equal(expired.requests.length, 0);
  }
  const bounded = fixture({ deadlineMs: 1000, execution: { signal: new AbortController().signal, remainingMs: () => 10 },
    fetcher: async () => new Promise(() => {}) });
  await assert.rejects(bounded.transport.read());
});
test('exact one-MiB complete response is evidence and HTTP failures remain unavailable', async () => {
  const small = JSON.stringify(info('Complete'));
  const exact = small + ' '.repeat(1_048_576 - Buffer.byteLength(small));
  assert.equal((await fixture({ fetcher: async () => new Response(exact, { headers: { 'Content-Type': 'application/json' } }) }).transport.read()).title, 'Complete');
  for (const response of [() => new Response('{}', { status: 302 }), () => new Response('{}', { status: 503 }), () => new Response('{}')]) {
    let calls = 0; const f = fixture({ fetcher: async () => { calls++; return response(); } });
    await assert.rejects(f.transport.read()); assert.equal(calls, 1);
  }
});
