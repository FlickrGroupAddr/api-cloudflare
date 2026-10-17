import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createSyntheticAlbumCreateRepairReader, AlbumRepairReadError } from '../src/album_create_repair_discovery.ts';
import { signedAlbumRest } from '../src/flickr_reads.ts';

const identity = { bindingId: '11111111-1111-4111-8111-111111111111', bindingRevision: 7,
  createAttemptId: '22222222-2222-4222-8222-222222222222', firstPhotoId: 'immutable-first',
  ownerNsid: 'owner@N00', preContextIds: ['before'] };
const pair = { token: 'synthetic', tokenSecret: 'synthetic-secret' };
const app = { consumerKey: 'synthetic-app', consumerSecret: 'synthetic-app-secret' };
const observedAt = () => '2026-10-17T12:00:00.000001Z';
const contexts = ids => ({ stat: 'ok', set: ids.map(id => ({ id, title: 'Same title' })), pool: [] });
const info = id => ({ stat: 'ok', photoset: { id, owner: identity.ownerNsid,
  primary: 'changed-primary', title: { _content: 'Same title' } } });
const code = value => error => error instanceof AlbumRepairReadError && error.code === value;
function fixture(options = {}, input = identity) {
  const requests = [], reservations = [];
  const deps = {
    sign: (method, parameters) => signedAlbumRest(method, parameters, pair, app), observedAt,
    assertCurrent: async () => {}, reserveReads: async count => { reservations.push(count); },
    fetcher: async request => {
      const query = new URL(request.url).searchParams;
      requests.push({ request, method: query.get('method'), id: query.get('photoset_id'), photo: query.get('photo_id') });
      return Response.json(query.get('method') === 'flickr.photos.getAllContexts'
        ? contexts(['before', 'z', 'a', 'b']) : info(query.get('photoset_id')));
    }, ...options,
  };
  return { requests, reservations, reader: createSyntheticAlbumCreateRepairReader(input, deps) };
}

test('dormant reader requires explicit dependencies and validates complete retained evidence', () => {
  assert.throws(() => createSyntheticAlbumCreateRepairReader(identity), code('candidate_evidence_unavailable'));
  for (const change of [{ bindingId: 'bad' }, { createAttemptId: 'bad' }, { bindingRevision: 0 },
    { preContextIds: null }, { preContextIds: ['a', 'a'] }, { preContextIds: ['bad id'] },
    { preContextIds: Array.from({ length: 1001 }, (_, n) => `set-${n}`) }, { ownerNsid: '\ud800' }]) {
    assert.throws(() => fixture({}, { ...identity, ...change }), code('candidate_evidence_unavailable'));
  }
});

test('zero sentinel IDs refuse constructor and proof inputs before work and invalidate complete pages', async () => {
  for (const change of [{ firstPhotoId: '0' }, { ownerNsid: '0' }, { preContextIds: ['0'] }]) {
    assert.throws(() => fixture({ sign: assert.fail, fetcher: assert.fail,
      assertCurrent: assert.fail, reserveReads: assert.fail }, { ...identity, ...change }), code('candidate_evidence_unavailable'));
  }
  const f = fixture({ sign: assert.fail, fetcher: assert.fail, assertCurrent: assert.fail, reserveReads: assert.fail });
  await assert.rejects(f.reader.prove('0'), code('invalid_request'));
  for (const value of [contexts(['0']), { stat: 'ok', photoset: { ...info('a').photoset, primary: '0' } }]) {
    const page = fixture({ fetcher: async request => Response.json(new URL(request.url).searchParams.get('method') === 'flickr.photos.getAllContexts'
      ? value.set ? value : contexts(['a']) : value) });
    await assert.rejects(page.reader.discover(1, 1), code('candidate_evidence_unavailable'));
  }
});

test('advisory difference uses full context and lexical finite pages, only slice gets info', async () => {
  const f = fixture(), page = await f.reader.discover(2, 2);
  assert.equal(page.total, 3); assert.equal(page.pages, 2);
  assert.equal(page.bindingRevision, 7); assert.equal(page.createAttemptId, identity.createAttemptId);
  assert.deepEqual(page.candidates.map(row => row.flickrPhotosetId), ['z']);
  assert.equal(page.candidates[0].primaryPhotoId, 'changed-primary');
  assert.equal(page.candidates[0].thumbnail, null); assert.equal(page.candidates[0].createdAt, null);
  assert.equal(page.candidates[0].navigationUrl, 'https://www.flickr.com/photos/owner%40N00/albums/z/');
  assert.deepEqual(f.reservations, [3]); assert.equal(f.requests.length, 2);
  assert.ok(f.requests.every(row => row.request.method === 'GET'));
  assert.equal(f.requests[0].photo, identity.firstPhotoId);
  await assert.rejects(f.reader.discover(3, 2), code('page_out_of_range'));
  for (const args of [[0, 2], [1001, 1], [1, 21], [1, 1.1]]) await assert.rejects(f.reader.discover(...args), code('invalid_request'));
});

test('single or empty candidates remain advisory observations and never produce selection proof', async () => {
  for (const ids of [[], ['singleton']]) {
    const f = fixture({ fetcher: async request => {
      const query = new URL(request.url).searchParams;
      return Response.json(query.get('method') === 'flickr.photos.getAllContexts' ? contexts(ids) : info(query.get('photoset_id')));
    } });
    const result = await f.reader.discover(1, 20);
    assert.equal(result.total, ids.length); assert.equal(result.pages, ids.length ? 1 : 0);
    assert.deepEqual(Object.keys(result).sort(), ['schemaVersion', 'fgaAlbumBindingId', 'bindingRevision', 'createAttemptId', 'observedAt', 'page', 'pageSize', 'pages', 'total', 'candidates'].sort());
    if (!ids.length) await assert.rejects(f.reader.discover(2, 20), code('page_out_of_range'));
  }
});

test('manual selection does fresh exact info and first-photo contexts without discovery or primary matching', async () => {
  const f = fixture({ fetcher: async request => {
    const query = new URL(request.url).searchParams;
    f.requests.push({ method: query.get('method'), id: query.get('photoset_id'), photo: query.get('photo_id') });
    return Response.json(query.get('method') === 'flickr.photos.getAllContexts' ? contexts(['manual-exact']) : info('manual-exact'));
  } });
  const result = await f.reader.prove('manual-exact');
  assert.equal(result.photosetId, 'manual-exact'); assert.equal(result.firstPhotoId, identity.firstPhotoId);
  assert.deepEqual(result.contextIds, ['manual-exact']); assert.deepEqual(f.reservations, [2]);
  assert.deepEqual(f.requests.map(row => row.method), ['flickr.photosets.getInfo', 'flickr.photos.getAllContexts']);
  assert.equal(f.requests[1].photo, identity.firstPhotoId);
});

test('whole context completeness, duplicate JSON, malformed metadata and wrong-owner pages refuse wholly', async () => {
  const badContexts = [contexts(['duplicate', 'duplicate']), { ...contexts(['valid']), unexpected: 1 },
    { stat: 'ok', set: [], pool: [{ id: 'pool', title: '\u0000' }] },
    contexts(Array.from({ length: 1001 }, (_, n) => `id-${n}`)), contexts(['bad id'])];
  for (const value of badContexts) {
    const f = fixture({ fetcher: async () => Response.json(value) });
    await assert.rejects(f.reader.discover(1, 20), code('candidate_evidence_unavailable'));
  }
  const badInfo = [ { ...info('a'), extra: 1 }, { ...info('a'), stat: 'fail' },
    { stat: 'ok', photoset: { ...info('a').photoset, owner: 'other' } },
    { stat: 'ok', photoset: { ...info('a').photoset, title: { _content: '\ud800' } } },
    { stat: 'ok', photoset: { ...info('a').photoset, date_create: 'garbage' } },
    { stat: 'ok', photoset: { ...info('a').photoset, description: { _content: 'okay', extra: 1 } } } ];
  for (const value of badInfo) {
    const f = fixture({ fetcher: async request => Response.json(new URL(request.url).searchParams.get('method') === 'flickr.photos.getAllContexts' ? contexts(['a']) : value) });
    await assert.rejects(f.reader.discover(1, 20), code('candidate_evidence_unavailable'));
  }
  const duplicate = fixture({ fetcher: async () => new Response('{"stat":"ok","stat":"ok","set":[],"pool":[]}', { headers: { 'Content-Type': 'application/json' } }) });
  await assert.rejects(duplicate.reader.discover(1, 1), code('candidate_evidence_unavailable'));
});

test('fresh selection distinguishes complete negative proof from unavailable malformed evidence', async () => {
  for (const [value, expected] of [[{ stat: 'fail', code: 1, message: 'Missing' }, 'selected_album_not_verified'],
    [{ stat: 'ok', photoset: { ...info('selected').photoset, owner: 'other' } }, 'selected_album_not_verified'],
    [info('wrong-id'), 'resolution_evidence_unavailable']]) {
    const f = fixture({ fetcher: async () => Response.json(value) });
    await assert.rejects(f.reader.prove('selected'), code(expected));
  }
  const f = fixture({ fetcher: async request => Response.json(new URL(request.url).searchParams.get('method') === 'flickr.photos.getAllContexts' ? contexts([]) : info('selected')) });
  await assert.rejects(f.reader.prove('selected'), code('selected_album_not_verified'));
});

test('shared 1MiB/body and 4MiB aggregate limits apply without hidden retry or truncated success', async () => {
  for (const length of [300000, 1048576]) {
    let count = 0;
    const f = fixture({ fetcher: async request => {
      count++; const query = new URL(request.url).searchParams;
      return Response.json(query.get('method') === 'flickr.photos.getAllContexts' ? contexts(['one'])
        : { stat: 'ok', photoset: { ...info('one').photoset, description: { _content: 'x'.repeat(length) } } });
    } });
    if (length === 300000) assert.equal((await f.reader.discover(1, 20)).candidates.length, 1);
    else await assert.rejects(f.reader.discover(1, 20), code('candidate_evidence_unavailable'));
    assert.equal(count, 2);
  }
  let count = 0;
  const f = fixture({ fetcher: async request => {
    count++; const query = new URL(request.url).searchParams;
    return Response.json(query.get('method') === 'flickr.photos.getAllContexts' ? contexts(['a', 'b', 'c', 'd', 'e'])
      : { stat: 'ok', photoset: { ...info(query.get('photoset_id')).photoset, description: { _content: 'x'.repeat(900000) } } });
  } });
  await assert.rejects(f.reader.discover(1, 20), code('candidate_evidence_unavailable'));
  assert.equal(count, 6);
});

test('authority and rate refusal stop reads; final authority reread fences disclosure', async () => {
  const authorityError = new Error('stale_binding_revision');
  let calls = 0;
  const f = fixture({ assertCurrent: async () => { if (++calls === 5) throw authorityError; } });
  await assert.rejects(f.reader.discover(1, 1), error => error === authorityError);
  assert.equal(f.requests.length, 2);
  const rateError = new Error('rate_limited'), rate = fixture({ reserveReads: async () => { throw rateError; } });
  await assert.rejects(rate.reader.discover(1, 20), error => error === rateError); assert.equal(rate.requests.length, 0);
});

test('whole-operation deadline bounds fetch and aborts its injected request', async () => {
  // Warm the signer/request path so cold crypto initialization cannot consume the test budget.
  await fixture().reader.discover(1, 1);
  let signal, finish, calls = 0, cancelled = false;
  const pending = new Promise(resolve => { finish = resolve; });
  const f = fixture({ deadlineMs: 100, fetcher: request => { calls++; signal = request.signal; return pending; } });
  await assert.rejects(f.reader.discover(1, 1), code('candidate_evidence_unavailable'));
  assert.ok(signal, 'fetch was entered before the deadline');
  assert.equal(signal.aborted, true);
  finish(new Response(new ReadableStream({ cancel() { cancelled = true; } }), { headers: { 'Content-Type': 'application/json' } }));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(cancelled, true, 'late upstream body was canceled');
  assert.equal(calls, 1, 'no info read continued after the deadline');
});
test('whole-operation cancellation survives forced garbage collection', { timeout: 20_000 }, async () => {
  if (typeof globalThis.gc !== 'function') {
    execFileSync(process.execPath, ['--expose-gc', '--test',
      '--test-name-pattern=^whole-operation cancellation survives forced garbage collection$', fileURLToPath(import.meta.url)],
    { timeout: 15_000, stdio: 'pipe' });
    return;
  }
  await fixture().reader.discover(1, 1);
  let signal, expire, finish, entered, calls = 0, cancelled = false;
  const pending = new Promise(resolve => { finish = resolve; });
  const started = new Promise(resolve => { entered = resolve; });
  const schedule = globalThis.setTimeout;
  // Trigger the real operation deadline callback after GC without racing wall-clock scheduling.
  globalThis.setTimeout = (callback, delay, ...args) => delay === 100
    ? (expire = () => callback(...args), schedule(() => {}, 10_000)) : schedule(callback, delay, ...args);
  try {
    const f = fixture({ deadlineMs: 100, fetcher: request => {
      calls++; signal = request.signal; entered(); return pending;
    } });
    const rejected = assert.rejects(f.reader.discover(1, 1), code('candidate_evidence_unavailable'));
    await started;
    for (let n = 0; n < 8; n++) {
      await new Promise(resolve => setImmediate(resolve));
      globalThis.gc();
    }
    assert.equal(typeof expire, 'function');
    expire();
    await rejected;
    assert.equal(signal.aborted, true, 'request cancellation must survive collection of intermediate followers');
    finish(new Response(new ReadableStream({ cancel() { cancelled = true; } }), { headers: { 'Content-Type': 'application/json' } }));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(cancelled, true, 'late upstream body was canceled after GC');
    assert.equal(calls, 1, 'no info read continued after the deadline');
  } finally { globalThis.setTimeout = schedule; }
});
