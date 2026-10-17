import test from 'node:test';
import assert from 'node:assert/strict';
import { createSyntheticAlbumMaterializationTransport, albumContextIds, albumCreateResult,
  albumNavigationUrl, AlbumCreateRejected, AlbumMaterializationTransportError } from '../src/album_materialization_transport.ts';
import { signedAlbumRest } from '../src/flickr_reads.ts';

const identity = { attemptId: 'attempt', photoId: 'first-photo', ownerNsid: 'owner@N00', title: 'A title & plus+' };
const pair = { token: 'synthetic-token', tokenSecret: 'synthetic-token-secret' };
const app = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' };
const url = 'https://www.flickr.com/photos/alias/albums/set-id/';
const contexts = ids => ({ stat: 'ok', set: ids.map(id => ({ id, title: 'Album' })), pool: [] });
const success = { stat: 'ok', photoset: { id: 'set-id', url } };
const info = { stat: 'ok', photoset: { id: 'set-id', owner: identity.ownerNsid, primary: 'changed-current-primary', title: { _content: 'Album' } } };
const sign = (method, data) => signedAlbumRest(method, data, pair, app);

function fixture(options = {}) {
  const requests = [];
  let contextCount = 0;
  const deps = {
    sign,
    assertCurrent: async () => {},
    fetcher: async request => {
      const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : new URL(request.url).searchParams;
      const method = params.get('method');
      requests.push({ request, params, method });
      if (method === 'flickr.photos.getAllContexts') return Response.json(contexts(contextCount++ ? ['set-id'] : []));
      if (method === 'flickr.photosets.getInfo') return Response.json(info);
      if (method === 'flickr.photosets.create') return Response.json(success);
      assert.fail('unexpected method');
    },
    ...options,
  };
  return { requests, transport: createSyntheticAlbumMaterializationTransport(identity, deps) };
}
async function created(f) {
  await f.transport.contexts();
  const prepared = await f.transport.prepareCreate();
  const result = await prepared.handoff();
  return { prepared, result };
}

test('dormant factory refuses missing dependencies and validates identity before any HTTP call', () => {
  assert.throws(() => createSyntheticAlbumMaterializationTransport(identity), AlbumMaterializationTransportError);
  for (const bad of [{ ...identity, photoId: 'bad photo' }, { ...identity, ownerNsid: '' }, { ...identity, title: '\u0000' }, { ...identity, title: '\ud800' }, { ...identity, title: 'x'.repeat(1001) }])
    assert.throws(() => createSyntheticAlbumMaterializationTransport(bad, { sign, fetcher: assert.fail, assertCurrent: assert.fail }));
});

test('whole context set refuses mixed/duplicate/malformed/oversize rows without partial filtering', () => {
  assert.deepEqual(albumContextIds(contexts([])), []);
  assert.deepEqual(albumContextIds(contexts(['first', 'second'])), ['first', 'second']);
  for (const value of [{ stat: 'ok' }, { stat: 'ok', set: [], pool: {} }, { ...contexts([]), code: 1 },
    contexts(['duplicate', 'duplicate']), contexts(['valid', 'bad id']), contexts(['0']), contexts(['id\n']), contexts(Array.from({ length: 1001 }, (_, n) => `id-${n}`)),
    { ...contexts([]), pool: [{ id: 'pool', title: 'bad\n' }] }, { ...contexts([]), set: [{ id: 'id', title: 1 }] }])
    assert.throws(() => albumContextIds(value), AlbumMaterializationTransportError);
});

test('create accepts only exact ID and bounded resource URL; documented auth/argument failures alone reject', () => {
  assert.deepEqual(albumCreateResult(success), { photosetId: 'set-id', url });
  for (const code of [1, 2, 3, 95, 96, 97, 98, 99, 100])
    assert.throws(() => albumCreateResult({ stat: 'fail', code, message: 'Documented rejection' }), error => error instanceof AlbumCreateRejected && error.code === code);
  for (const value of [{ stat: 'ok' }, { ...success, code: 1 }, { stat: 'ok', photoset: { id: 12, url } },
    { stat: 'fail', code: 105, message: 'Unavailable' }, { stat: 'fail', code: 106, message: 'Write failed' },
    { stat: 'fail', code: 111, message: 'Format unavailable' }, { stat: 'fail', code: 9999, message: 'Unknown' },
    { stat: 'fail', code: 1, message: 'Bad', photoset: success.photoset },
    { stat: 'ok', photoset: { id: '0', url: 'https://www.flickr.com/photos/alias/albums/0/' } },
    { stat: 'ok', photoset: { id: 'set-id\n', url } }])
    assert.throws(() => albumCreateResult(value), error => error instanceof AlbumMaterializationTransportError && !(error instanceof AlbumCreateRejected));
});

test('navigation validates exact resource path and rejects arbitrary destinations or URL confusion', () => {
  assert.equal(albumNavigationUrl(url, 'set-id'), url);
  assert.equal(albumNavigationUrl('https://flickr.com/photos/owner@N00/sets/set-id/', 'set-id'), 'https://flickr.com/photos/owner@N00/sets/set-id/');
  for (const value of ['http://www.flickr.com/photos/x/sets/set-id/', 'https://www.flickr.com.evil/photos/x/sets/set-id/',
    'https://user@www.flickr.com/photos/x/sets/set-id/', `${url}#fragment`, `${url}?target=other`,
    'https://www.flickr.com/photos/x/sets/other/', 'https://www.flickr.com/photos/x%2Fy/sets/set-id/',
    'https://www.flickr.com/photos/x/sets/set-id/%2e%2e/', 'https://www.flickr.com:444/photos/x/sets/set-id/', 'x'.repeat(2049)])
    assert.throws(() => albumNavigationUrl(value, 'set-id'));
});

test('actual shared signer plus adapter preserves original title/photo and one-shot prepared handoff', async () => {
  const f = fixture();
  assert.deepEqual(await f.transport.contexts(), []);
  const prepared = await f.transport.prepareCreate();
  assert.equal(f.requests.length, 1);
  const result = await prepared.handoff();
  assert.deepEqual(result, { photosetId: 'set-id', url });
  await assert.rejects(prepared.handoff());
  assert.equal(f.requests.length, 2);
  const create = f.requests[1];
  assert.equal(create.method, 'flickr.photosets.create');
  assert.equal(create.params.get('primary_photo_id'), identity.photoId);
  assert.equal(create.params.get('title'), identity.title);
  assert.match(create.request.headers.get('Authorization'), /^OAuth /);
  assert.equal(create.request.redirect, 'manual');
  const proof = await f.transport.verify('set-id');
  assert.deepEqual(proof, { photosetId: 'set-id', url, ownerNsid: identity.ownerNsid, primaryPhotoId: identity.photoId, contextIds: ['set-id'] });
  assert.deepEqual(f.requests.map(x => x.method), ['flickr.photos.getAllContexts', 'flickr.photosets.create', 'flickr.photosets.getInfo', 'flickr.photos.getAllContexts']);
  assert.equal(f.requests.at(-1).params.get('photo_id'), identity.photoId);
  await assert.rejects(f.transport.verify('set-id'));
});

test('changed current primary is allowed, but wrong owner/ID or absent original-first membership cannot prove completion', async () => {
  for (const mutation of ['owner', 'id', 'primary', 'title', 'absent']) {
    let count = 0;
    const f = fixture({ fetcher: async request => {
      const method = request.method === 'POST' ? 'create' : new URL(request.url).searchParams.get('method');
      if (method === 'create') return Response.json(success);
      if (method === 'flickr.photos.getAllContexts') return Response.json(contexts(count++ && mutation !== 'absent' ? ['set-id'] : []));
      const value = structuredClone(info);
      if (mutation !== 'absent') value.photoset[mutation] = mutation === 'title' ? { _content: [] } : 'bad id';
      return Response.json(value);
    } });
    await created(f);
    await assert.rejects(f.transport.verify('set-id'), AlbumMaterializationTransportError);
  }
});

test('wrong phase, stale authority and malformed pre-read prevent every POST', async () => {
  for (const deps of [{ assertCurrent: async () => { throw Error('stale'); } }, { fetcher: async () => Response.json({ stat: 'ok', set: [null], pool: [] }) }]) {
    const f = fixture(deps);
    await assert.rejects(f.transport.prepareCreate());
    await assert.rejects(f.transport.contexts());
    await assert.rejects(f.transport.prepareCreate());
    assert.equal(f.requests.length, 0);
  }
});

test('disposed prepared request never reaches HTTP and cannot be reused', async () => {
  const f = fixture();
  await f.transport.contexts();
  const prepared = await f.transport.prepareCreate();
  prepared.dispose();
  await assert.rejects(prepared.handoff());
  await assert.rejects(prepared.handoff());
  assert.equal(f.requests.length, 1);
});

test('untrusted injected signer cannot change host/method/query/body or duplicate exact parameters', async () => {
  for (const change of ['host', 'query', 'duplicate', 'method', 'photo', 'redirect']) {
    let calls = 0;
    const f = fixture({ sign: (method, data) => {
      const original = sign(method, data);
      const u = new URL(original.url);
      if (change === 'host') u.hostname = 'example.com';
      if (change === 'query') u.searchParams.set('extra', 'unsupported');
      if (change === 'duplicate') u.searchParams.append('photo_id', identity.photoId);
      if (change === 'photo') u.searchParams.set('photo_id', 'other-photo');
      return new Request(u, { method: change === 'method' ? 'POST' : 'GET', redirect: change === 'redirect' ? 'follow' : 'manual' });
    }, fetcher: async () => { calls++; return Response.json(contexts([])); } });
    await assert.rejects(f.transport.contexts());
    assert.equal(calls, 0);
  }
});

test('HTTP failure, redirect, non-JSON, invalid UTF-8 and over-bound bodies remain uncertain with no retry', async () => {
  for (const response of [() => new Response('', { status: 302 }), () => new Response('{}', { status: 503 }),
    () => new Response('{}'), () => new Response(new Uint8Array([0xff]), { headers: { 'Content-Type': 'application/json' } }),
    () => new Response(' '.repeat(262145), { headers: { 'Content-Type': 'application/json' } })]) {
    let calls = 0;
    const f = fixture({ fetcher: async () => { calls++; return response(); } });
    await assert.rejects(f.transport.contexts());
    assert.equal(calls, 1);
  }
});

test('whole-operation deadline settles ignored fetch and ignored body without hidden retry', async () => {
  for (const stall of ['fetch', 'body']) {
    let calls = 0;
    const f = fixture({ deadlineMs: 15, fetcher: async () => {
      calls++;
      if (stall === 'fetch') return new Promise(() => {});
      return new Response(new ReadableStream({ pull() { return new Promise(() => {}); } }), { headers: { 'Content-Type': 'application/json' } });
    } });
    await assert.rejects(f.transport.contexts(), AlbumMaterializationTransportError);
    assert.equal(calls, 1);
  }
});

test('shared strict decoder refuses duplicate JSON fields and rounded rejection codes after one POST', async () => {
  for (const raw of ['{"stat":"ok","stat":"ok","photoset":{"id":"set-id","url":"' + url + '"}}',
    '{"stat":"ok","photoset":{"id":"different","id":"set-id","url":"' + url + '"}}',
    '{"stat":"fail","code":98.000000000000000001,"message":"rounded"}']) {
    let writes = 0;
    const f = fixture({ fetcher: async request => {
      if (request.method !== 'POST') return Response.json(contexts([]));
      writes++;
      return new Response(raw, { headers: { 'Content-Type': 'application/json' } });
    } });
    await f.transport.contexts();
    const prepared = await f.transport.prepareCreate();
    await assert.rejects(prepared.handoff(), error => error instanceof AlbumMaterializationTransportError && !(error instanceof AlbumCreateRejected));
    await assert.rejects(prepared.handoff());
    assert.equal(writes, 1);
  }
});

test('modified signed create body fails before POST dispatch', async () => {
  let writes = 0;
  const f = fixture({ sign: (method, data) => {
    if (method !== 'flickr.photosets.create') return sign(method, data);
    return sign(method, { ...data, primary_photo_id: 'another-photo' });
  }, fetcher: async request => { if (request.method === 'POST') writes++; return Response.json(contexts([])); } });
  await f.transport.contexts();
  await assert.rejects(f.transport.prepareCreate());
  assert.equal(writes, 0);
});

test('zero sentinel and terminal newline context IDs prevent preparation on actual adapter', async () => {
  for (const invalidId of ['0', 'set-id\n', 'set-id\r']) {
    let calls = 0;
    const f = fixture({ fetcher: async request => {
      calls++;
      assert.equal(request.method, 'GET');
      return Response.json(contexts([invalidId]));
    } });
    await assert.rejects(f.transport.contexts());
    await assert.rejects(f.transport.prepareCreate());
    assert.equal(calls, 1);
  }
});

test('45-second invocation bound refuses work and discards late evidence across stage deadlines', async t => {
  let now = 0;
  t.mock.method(performance, 'now', () => now);
  let calls = 0;
  const f = fixture({ fetcher: async () => { calls++; return Response.json(contexts([])); } });
  now = 45_001;
  await assert.rejects(f.transport.contexts());
  assert.equal(calls, 0);
  now = 0;
  const late = fixture({ fetcher: async () => { calls++; now = 45_001; return Response.json(contexts([])); } });
  await assert.rejects(late.transport.contexts());
  await assert.rejects(late.transport.prepareCreate());
  assert.equal(calls, 1);
});
