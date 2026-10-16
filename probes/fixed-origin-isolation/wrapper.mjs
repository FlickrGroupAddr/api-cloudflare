// Temporary composition only. No handler, router or authentication implementation.
// JavaScript composes the exact captured and pinned candidate Worker exports.
export const ORIGIN = 'https://flickrgroupaddr.com';
export const PATHS = Object.freeze([
  '/api/v001/installations/current',
  '/api/v001/existing-public-photos?page=1&page_size=1',
  '/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1',
]);
export const CASES = Object.freeze(['ok', 'missing-auth', 'invalid-auth']);
const TOKEN = Array(13).fill('0000').join('-');
const PREFIX = 'FGA-Qualification ';
const IMAGE = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='), c => c.charCodeAt(0));

export function createQualificationWrapper({ captured, candidate, syntheticDb,
  run, capability, startsAt, expiresAt, clock = Date.now, counters }) {
  if (!/^[a-f0-9]{32}$/.test(run) || !/^[a-f0-9]{64}$/.test(capability)
      || !Number.isSafeInteger(startsAt) || !Number.isSafeInteger(expiresAt)
      || expiresAt <= startsAt || expiresAt - startsAt > 600_000) throw Error('invalid_scope');
  const syntheticEnv = Object.freeze({ DB: syntheticDb,
    FLICKR_APPLICATION: Object.freeze({ get: async () => {
      counters.application++; return JSON.stringify({ schemaVersion: 1, consumerKey: 'synthetic', consumerSecret: 'synthetic' });
    } }),
    FLICKR_GRANT: Object.freeze({ get: async () => {
      counters.grant++; return JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'synthetic', tokenSecret: 'synthetic' });
    } }),
    FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1', FGA_PHOTO_THUMBNAILS_ENABLED: '1',
    FGA_ADMIN_ENABLED: '0', FGA_GROUPS_ENABLED: '0', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0',
    FGA_UPLOAD_AUTHORIZATION_ENABLED: '0', FGA_UPLOAD_PHOTO_BINDING_ENABLED: '0',
    FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '0',
  });
  const syntheticFetch = async request => {
    counters.memoryFetch++;
    const url = new URL(request.url);
    if (request.method !== 'GET' || request.redirect !== 'manual') throw Error('synthetic_fetch_refused');
    if (url.origin === 'https://www.flickr.com' && url.pathname === '/services/rest/'
        && [...url.searchParams.keys()].sort().join(',') === 'content_types,extras,format,method,nojsoncallback,page,per_page,privacy_filter,user_id'
        && url.searchParams.get('method') === 'flickr.people.getPhotos'
        && url.searchParams.get('user_id') === 'synthetic-owner'
        && url.searchParams.get('content_types') === '0' && url.searchParams.get('privacy_filter') === '1'
        && url.searchParams.get('extras') === 'date_upload,date_taken,media,url_q'
        && url.searchParams.get('format') === 'json' && url.searchParams.get('nojsoncallback') === '1'
        && url.searchParams.get('page') === '1' && url.searchParams.get('per_page') === '1'
        && request.headers.get('Authorization')?.startsWith('OAuth ')) {
      counters.pages++;
      return Response.json({ stat: 'ok', photos: { page: 1, perpage: 1, pages: 1, total: 1,
        photo: [{ id: 'photo', owner: 'synthetic-owner', ispublic: '1', media: 'photo', title: 'Synthetic',
          dateupload: '1770000000', datetaken: '2026-02-01 14:30:00',
          url_q: 'https://live.staticflickr.com/1/photo_key_q.png' }] } });
    }
    if (url.href === 'https://live.staticflickr.com/1/photo_key_q.png'
        && !['Authorization', 'Cookie', 'Referer'].some(header => request.headers.has(header))) {
      counters.images++;
      return new Response(IMAGE, { headers: { 'Content-Type': 'image/png', 'Content-Length': String(IMAGE.length) } });
    }
    throw Error('synthetic_fetch_refused');
  };
  const syntheticWorker = candidate.createWorker(syntheticFetch);
  const refuse = () => new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
  return Object.freeze({ async fetch(request, productionEnv) {
    const auth = request.headers.get('Authorization');
    const controlHeaders = [...request.headers.keys()].filter(name => name.startsWith('x-fga-qualification'));
    const selected = controlHeaders.length > 0 || /^fga-qualification/i.test(auth ?? '');
    if (!selected) {
      counters.normal++;
      return captured.default.fetch(request, productionEnv);
    }
    const now = clock();
    const url = new URL(request.url);
    const scenario = request.headers.get('X-FGA-Qualification-Case');
    if (auth !== PREFIX + capability || request.headers.get('X-FGA-Qualification-Run') !== run
        || controlHeaders.some(name => !['x-fga-qualification-run', 'x-fga-qualification-case'].includes(name))
        || !CASES.includes(scenario) || !Number.isSafeInteger(now) || now < startsAt || now >= expiresAt
        || request.method !== 'GET' || url.origin !== ORIGIN || url.username || url.password || url.hash
        // Full observable URL retains empty '?'/'#' delimiters lost by the
        // pathname/search/hash getters. The host may already normalize wire input.
        || !PATHS.some(path => request.url === ORIGIN + path) || request.body !== null || request.signal.aborted
        || (request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')
        || request.headers.has('Transfer-Encoding')) return refuse();
    // Only the synthetic bearer crosses the candidate seam. Client selectors,
    // cookies, credentials and arbitrary headers do not enter the synthetic app.
    const headers = new Headers();
    headers.set('Authorization', 'Bearer ' + (scenario === 'invalid-auth' ? 'invalid' : TOKEN));
    if (scenario === 'missing-auth') headers.delete('Authorization');
    counters.synthetic++;
    return syntheticWorker.fetch(new Request(request, { headers }), syntheticEnv);
  } });
}
