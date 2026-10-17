// Closed qualification-only actual-handler dependencies. Web APIs only.
// Explicit synthetic DB injection; never accepts a production environment.
import { png } from '../fixed-origin-isolation/edge_png.mjs';

export const HANDLER_CASES = Object.freeze({
  png: 200, jpeg: 200, 'exact-limit': 200, 'declared-excess': 503,
  'undeclared-excess': 503, 'upstream-error': 503, truncation: 503,
  'wrong-media': 503, 'wrong-signature': 503, redirect: 503, stall: 503,
  'missing-auth': 401, 'bad-auth': 401, 'bad-query': 400,
  'final-installation': 401, 'final-link': 409, 'final-grant': 409,
  'foreign-identity': 503, 'private-photo': 503, 'foreign-destination': 503,
});
const ALIASES = Object.freeze({ ok: 'png', 'invalid-auth': 'bad-auth' });
const ORIGIN = 'https://flickrgroupaddr.com';
export const HANDLER_PATHS = Object.freeze([
  '/api/v001/installations/current',
  '/api/v001/existing-public-photos?page=1&page_size=1',
  '/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1',
]);
export const BROWSER_PATHS = Object.freeze([
  '/api/v001/existing-public-photos?page=1&page_size=2',
  '/api/v001/existing-public-photos?page=2&page_size=2',
  '/api/v001/existing-public-photos/photo1/thumbnail?page=1&page_size=2&linked_flickr_revision=1',
  '/api/v001/existing-public-photos/photo2/thumbnail?page=1&page_size=2&linked_flickr_revision=1',
  '/api/v001/existing-public-photos/photo3/thumbnail?page=2&page_size=2&linked_flickr_revision=1',
]);
export function canonicalHandlerCase(value) {
  const scenario = Object.hasOwn(ALIASES, value) ? ALIASES[value] : value;
  if (!Object.hasOwn(HANDLER_CASES, scenario)) throw Error('unknown_handler_case');
  return scenario;
}
export function handlerCaseIdentity(value) {
  const scenario = canonicalHandlerCase(value);
  const group = String(Object.keys(HANDLER_CASES).indexOf(scenario) + 1).padStart(4, '0');
  return Object.freeze({ userId: `qualification-${scenario}-user`,
    installationId: `qualification-${scenario}-install`, versionId: `qualification-${scenario}-version`,
    token: [...Array(12).fill(group), '0000'].join('-') });
}

// Run exactly once against a new disposable synthetic DB after candidate migrations.
// One transaction provisions every case before admission. Duplicate calls fail;
// there is deliberately no reset, replace, cleanup or production migration.
export async function initializeHandlerCaseNamespaces(db) {
  const statements = [];
  for (const scenario of Object.keys(HANDLER_CASES)) {
    const id = handlerCaseIdentity(scenario);
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(id.token)))]
      .map(byte => byte.toString(16).padStart(2, '0')).join('');
    const sql = (query, ...args) => db.prepare(query).bind(...args);
    statements.push(
      sql('INSERT INTO fga_users(user_id) VALUES(?)', id.userId),
      sql("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES(?,?,'lrc_plugin','active',1,?)", id.installationId, id.userId, id.versionId),
      sql("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES(?,?,?,'current',1)", id.versionId, id.installationId, digest),
      sql("INSERT INTO flickr_links(user_id,owner_nsid,link_revision,state) VALUES(?,'synthetic-owner',1,'linked')", id.userId),
      sql("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES(?,'gen',1,'synthetic-owner','write')", id.userId),
      sql("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES(?,'linked','available')", id.userId),
    );
  }
  await db.batch(statements);
}

// Same generated solid-color 2x2 JPEG as #0039; contains no photograph metadata.
export const HANDLER_JPEG_BASE64 = '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDwSiiiv2U/Lz//2Q==';
const imageUrl = id => `https://live.staticflickr.com/1/${id}_key_q.png`;
const bump = (counters, key) => { counters[key] = (counters[key] ?? 0) + 1; };
const check = condition => { if (!condition) throw Error('handler_dependency_refused'); };

async function mutateFinalAuthority(scenario, db, identity) {
  const sql = (query, ...args) => db.prepare(query).bind(...args);
  let statements;
  if (scenario === 'final-installation') statements = [
    sql("UPDATE installation_credential_versions SET state='revoked' WHERE version_id=? AND installation_id=? AND state='current'", identity.versionId, identity.installationId),
    sql("UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id=? AND user_id=? AND state='active'", identity.installationId, identity.userId),
  ];
  if (scenario === 'final-link') statements = [sql('UPDATE flickr_links SET link_revision=link_revision+1 WHERE user_id=? AND link_revision=1', identity.userId)];
  if (scenario === 'final-grant') statements = [sql("UPDATE flickr_native_credentials SET active_generation='changed' WHERE user_id=? AND active_generation='gen'", identity.userId)];
  if (statements) {
    const results = await db.batch(statements);
    check(results.length === statements.length && results.every(result => result.meta?.changes === 1));
  }
}

function dependency(scenario, db, counters) {
  const identity = handlerCaseIdentity(scenario);
  return async request => {
    try {
      bump(counters, 'memoryFetch');
      check(request.method === 'GET' && request.redirect === 'manual');
      const url = new URL(request.url);
      if (url.origin === 'https://www.flickr.com' && url.pathname === '/services/rest/') {
        const fields = Object.fromEntries(url.searchParams);
        check([...url.searchParams].length === 9
          && Object.keys(fields).sort().join(',') === 'content_types,extras,format,method,nojsoncallback,page,per_page,privacy_filter,user_id'
          && fields.method === 'flickr.people.getPhotos' && fields.user_id === 'synthetic-owner'
          && fields.privacy_filter === '1' && fields.content_types === '0'
          && fields.extras === 'date_upload,date_taken,media,url_q' && fields.format === 'json' && fields.nojsoncallback === '1'
          && ((fields.per_page === '1' && fields.page === '1') || (scenario === 'png' && fields.per_page === '2' && ['1','2'].includes(fields.page)))
          && request.headers.get('Authorization')?.startsWith('OAuth '));
        bump(counters, 'pages');
        const browser = fields.per_page === '2';
        const ids = browser ? (fields.page === '1' ? ['photo1', 'photo2'] : ['photo3']) : ['photo'];
        return Response.json({ stat: 'ok', photos: { page: Number(fields.page), perpage: Number(fields.per_page), pages: browser ? 2 : 1, total: browser ? 3 : 1,
          photo: ids.map(id => ({ id: scenario === 'foreign-identity' ? 'foreign' : id,
            owner: 'synthetic-owner', ispublic: scenario === 'private-photo' ? '0' : '1', media: 'photo', title: `Synthetic ${id}`,
            dateupload: '1770000000', datetaken: '2026-02-01 14:30:00',
            url_q: scenario === 'foreign-destination' ? 'https://other.invalid/1/photo_key_q.png' : imageUrl(id) })) } });
      }
      check(['photo', ...(scenario === 'png' ? ['photo1','photo2','photo3'] : [])].some(id => request.url === imageUrl(id))
        && !['Authorization','Cookie','Referer'].some(name => request.headers.has(name)));
      bump(counters, 'images');
      await mutateFinalAuthority(scenario, db, identity);
      if (scenario === 'redirect') return new Response('UPSTREAM_REJECTED_BODY', { status: 302, headers: { Location: 'https://other.invalid/' } });
      if (scenario === 'upstream-error') return new Response('UPSTREAM_REJECTED_BODY', { status: 502 });
      if (scenario === 'stall') return new Response(new ReadableStream({
        start(controller) { bump(counters, 'stalls'); this.timer = setTimeout(() => { bump(counters, 'stallCompleted'); controller.enqueue(png()); controller.close(); }, 16000); },
        cancel() { clearTimeout(this.timer); bump(counters, 'cancelled'); },
      }), { headers: { 'Content-Type': 'image/png' } });
      const bytes = scenario === 'jpeg' ? Uint8Array.from(atob(HANDLER_JPEG_BASE64), c => c.charCodeAt(0))
        : scenario === 'exact-limit' ? png(262144)
        : ['declared-excess','undeclared-excess'].includes(scenario) ? png(262145)
        : scenario === 'wrong-signature' ? new Uint8Array(70).fill(120) : png();
      const headers = { 'Content-Type': scenario === 'jpeg' ? 'image/jpeg' : scenario === 'wrong-media' ? 'text/html' : 'image/png' };
      if (scenario !== 'undeclared-excess') headers['Content-Length'] = String(bytes.length + (scenario === 'truncation' ? 1 : 0));
      return new Response(bytes, { headers });
    } catch (error) { bump(counters, 'responderFailures'); throw error; }
  };
}

export function createHandlerCaseProvider({ candidate, syntheticDb, counters }) {
  const workers = new Map(Object.keys(HANDLER_CASES).map(scenario => [scenario, candidate.createWorker(dependency(scenario, syntheticDb, counters))]));
  const env = Object.freeze({ DB: syntheticDb,
    FLICKR_APPLICATION: Object.freeze({ get: async () => { bump(counters, 'application'); return JSON.stringify({ schemaVersion: 1, consumerKey: 'synthetic', consumerSecret: 'synthetic' }); } }),
    FLICKR_GRANT: Object.freeze({ get: async () => { bump(counters, 'grant'); return JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'synthetic', tokenSecret: 'synthetic' }); } }),
    FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1', FGA_PHOTO_THUMBNAILS_ENABLED: '1',
    FGA_ADMIN_ENABLED: '0', FGA_GROUPS_ENABLED: '0', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0',
    FGA_UPLOAD_AUTHORIZATION_ENABLED: '0', FGA_UPLOAD_PHOTO_BINDING_ENABLED: '0', FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '0',
  });
  return Object.freeze({ async fetch(request, value) {
    const deny = () => new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
    let scenario;
    try { scenario = canonicalHandlerCase(value); } catch { return deny(); }
    const allowed = scenario === 'png' ? [...HANDLER_PATHS, ...BROWSER_PATHS]
      : ['missing-auth','bad-auth'].includes(scenario) ? HANDLER_PATHS : [HANDLER_PATHS[2]];
    if (request.method !== 'GET' || request.body !== null || request.signal.aborted
        || request.headers.has('Transfer-Encoding')
        || (request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')
        || !allowed.some(path => request.url === ORIGIN + path)) return deny();
    const headers = new Headers();
    if (scenario !== 'missing-auth') headers.set('Authorization', 'Bearer ' + (scenario === 'bad-auth' ? 'invalid' : handlerCaseIdentity(scenario).token));
    // Deliberately malformed input is constructed internally from the exact closed path.
    const url = request.url + (scenario === 'bad-query' ? '&unexpected=1' : '');
    bump(counters, 'synthetic');
    return workers.get(scenario).fetch(new Request(url, { method: 'GET', headers, signal: request.signal }), env);
  } });
}
