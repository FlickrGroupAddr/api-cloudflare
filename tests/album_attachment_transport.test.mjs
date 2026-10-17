import test from 'node:test';
import assert from 'node:assert/strict';
import { createSyntheticAlbumAttachmentTransport, AlbumAttachmentTransportError, AlbumAttachmentNeedsAttention } from '../src/album_attachment_transport.ts';
import { ProvenNotDispatched } from '../src/dispatch_policy.ts';
import { signedAlbumRest } from '../src/flickr_reads.ts';

const identity = { attemptId: 'attempt', ownerNsid: 'owner@N00', photosetId: 'album', photoId: 'later', primaryPhotoId: 'original' };
const pair = { token: 'synthetic-token', tokenSecret: 'synthetic-secret' };
const app = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' };
const sign = (method, data) => signedAlbumRest(method, data, pair, app);
const contexts = ids => ({ stat: 'ok', set: ids.map(id => ({ id, title: 'Album' })), pool: [] });
const info = { stat: 'ok', photoset: { id: 'album', owner: identity.ownerNsid, primary: 'mutable-current', title: { _content: 'Album' } } };
function fixture(options = {}, input = identity) {
  const calls = [];
  let targetReads = 0;
  const transport = createSyntheticAlbumAttachmentTransport(input, {
    sign, assertCurrent: async () => {}, beforeRequest: async () => {},
    fetcher: async request => {
      const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : new URL(request.url).searchParams;
      calls.push({ request, params });
      if (params.get('method') === 'flickr.photosets.getInfo') return Response.json(info);
      if (params.get('method') === 'flickr.photosets.addPhoto') return Response.json({ stat: 'ok' });
      return Response.json(contexts(params.get('photo_id') === 'original' || targetReads++ > 0 ? ['album'] : []));
    }, ...options,
  });
  return { transport, calls };
}
test('default off and closed finite identity/deadline requirements', () => {
  assert.throws(() => createSyntheticAlbumAttachmentTransport(identity), AlbumAttachmentTransportError);
  for (const invalid of [0, -1, 10_001, NaN, Infinity]) assert.throws(() => fixture({ deadlineMs: invalid }));
  assert.throws(() => fixture({}, { ...identity, primaryPhotoId: '' }));
});
test('fresh read/add/read checks immutable first photo, exact signer and once-only send', async () => {
  const { transport, calls } = fixture();
  assert.deepEqual((await transport.read()).contextIds, []);
  const prepared = await transport.prepareAdd();
  assert.equal(calls.length, 3);
  assert.equal(await prepared.handoff(), 'added');
  await assert.rejects(prepared.handoff());
  assert.deepEqual((await transport.read()).contextIds, ['album']);
  await assert.rejects(transport.prepareAdd());
  const posts = calls.filter(call => call.request.method === 'POST');
  assert.equal(posts.length, 1);
  assert.deepEqual(Object.fromEntries(posts[0].params), { method: 'flickr.photosets.addPhoto', format: 'json', nojsoncallback: '1', photoset_id: 'album', photo_id: 'later' });
  assert.match(posts[0].request.headers.get('Authorization'), /^OAuth /);
});
test('present membership and original first-photo pair never prepare an add', async () => {
  const f = fixture({}, { ...identity, photoId: 'original' });
  assert.deepEqual((await f.transport.read()).contextIds, ['album']);
  await assert.rejects(f.transport.prepareAdd());
  assert.equal(f.calls.length, 2);
});
test('code3 needs fresh read and a lost result permits only reread', async () => {
  for (const response of [() => Response.json({ stat: 'fail', code: 3, message: 'Already in set' }), () => { throw new Error('Lost'); }]) {
    let targetReads = 0;
    let posts = 0;
    const f = fixture({ fetcher: async request => {
      const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : new URL(request.url).searchParams;
      if (request.method === 'POST') { posts++; return response(); }
      if (params.get('method').endsWith('getInfo')) return Response.json(info);
      return Response.json(contexts(params.get('photo_id') === 'original' || targetReads++ > 0 ? ['album'] : []));
    } });
    await f.transport.read();
    const prepared = await f.transport.prepareAdd();
    try { assert.equal(await prepared.handoff(), 'already_present'); } catch (error) { assert.ok(error instanceof AlbumAttachmentTransportError); }
    assert.deepEqual((await f.transport.read()).contextIds, ['album']);
    await assert.rejects(f.transport.prepareAdd());
    assert.equal(posts, 1);
  }
});
test('complete wrong-owner/missing/conflicting evidence needs attention; incomplete evidence stays uncertain', async () => {
  for (const [value, reason] of [
    [{ ...info, photoset: { ...info.photoset, owner: 'other@N00' } }, 'wrong_owner'],
    [{ ...info, photoset: { ...info.photoset, id: 'other' } }, 'binding_conflict'],
    [{ stat: 'fail', code: 1, message: 'Missing' }, 'missing_album'],
  ]) {
    const f = fixture({ fetcher: async () => Response.json(value) });
    await assert.rejects(f.transport.read(), error => error instanceof AlbumAttachmentNeedsAttention && error.reason === reason);
    await assert.rejects(f.transport.prepareAdd());
  }
  for (const value of [{ stat: 'ok' }, { ...info, photoset: { ...info.photoset, extra: {} } }, { stat: 'fail', code: 105, message: 'Unavailable' }]) {
    const f = fixture({ fetcher: async () => Response.json(value) });
    await assert.rejects(f.transport.read(), error => error instanceof AlbumAttachmentTransportError && !(error instanceof AlbumAttachmentNeedsAttention));
    await assert.rejects(f.transport.prepareAdd());
  }
});
test('first-photo absence, missing photo, duplicates and partial contexts never authorize add', async () => {
  for (const [value, attention] of [[contexts([]), true], [{ stat: 'fail', code: 1, message: 'Missing' }, true], [contexts(['album', 'album']), false], [{ stat: 'ok', set: [{ id: 'album', title: 'Album' }] }, false]]) {
    const f = fixture({ fetcher: async request => Response.json(new URL(request.url).searchParams.get('method').endsWith('getInfo') ? info : value) });
    await assert.rejects(f.transport.read(), error => error instanceof AlbumAttachmentTransportError && (error instanceof AlbumAttachmentNeedsAttention) === attention);
    await assert.rejects(f.transport.prepareAdd());
  }
});
test('strict bytes/JSON/redirect bounds fail closed without writes', async () => {
  for (const response of [
    () => new Response('{"stat":"ok","stat":"ok"}', { headers: { 'Content-Type': 'application/json' } }),
    () => new Response(new Uint8Array([0xff]), { headers: { 'Content-Type': 'application/json' } }),
    () => Response.json({ stat: 'ok', payload: 'x'.repeat(262144) }),
    () => new Response('', { status: 302, headers: { location: 'https://other.invalid' } }),
  ]) {
    const f = fixture({ fetcher: async () => response() });
    await assert.rejects(f.transport.read());
    await assert.rejects(f.transport.prepareAdd());
  }
});
test('deadline, current authority and disposed preparation prevent sending', async () => {
  const hung = fixture({ deadlineMs: 5, fetcher: async () => new Promise(() => {}) });
  await assert.rejects(hung.transport.read());
  const stale = fixture({ assertCurrent: async () => { throw new Error('stale'); } });
  await assert.rejects(stale.transport.read());
  assert.equal(stale.calls.length, 0);
  const f = fixture();
  await f.transport.read();
  const prepared = await f.transport.prepareAdd();
  prepared.dispose();
  await assert.rejects(prepared.handoff(), ProvenNotDispatched);
  assert.equal(f.calls.length, 3);
});
test('signed target/method/parameter tampering never reaches HTTP', async () => {
  for (const forged of [new Request('https://other.invalid/', { redirect: 'manual' }), new Request('https://www.flickr.com/services/rest/?method=flickr.photosets.getInfo&photoset_id=album&format=json&nojsoncallback=1&extra=x', { redirect: 'manual' })]) {
    const f = fixture({ sign: () => forged });
    await assert.rejects(f.transport.read());
    assert.equal(f.calls.length, 0);
  }
});

test('denied rate admission prevents signing and fetching', async () => {
  let signed = 0;
  const f = fixture({ beforeRequest: async () => { throw new Error('rate denied'); }, sign: (...args) => { signed++; return sign(...args); } });
  await assert.rejects(f.transport.read());
  assert.equal(signed, 0);
  assert.equal(f.calls.length, 0);
});
