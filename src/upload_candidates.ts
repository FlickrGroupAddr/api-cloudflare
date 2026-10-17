import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse, NOW_US_SQL } from './installations.ts';
import { linkedGrant, sameGrant, withGrant, type SecretReads, type FlickrFetch } from './flickr_reads.ts';
import { PHOTO_ID, photoObject, photoInteger, signedPhotoRead } from './existing_photo_discovery.ts';

export interface UploadCandidatesEnv extends SecretReads { DB: SqlStore; FGA_UPLOAD_CANDIDATES_ENABLED?: string; }
export const UPLOAD_CANDIDATE_LIMITS = { elapsedMs: 10_000, upstreamBytes: 1048576, responseBytes: 524288 } as const;
export const UPLOAD_CANDIDATES_RELEASE_METADATA = { enabledFlag: 'FGA_UPLOAD_CANDIDATES_ENABLED', defaultValue: '0', hostQualified: false } as const;
const idSchema = { type: 'string', minLength: 1, maxLength: 128, pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' } as const;
const secondsSchema = { type: 'string', pattern: '^(0|[1-9][0-9]{0,11})$' } as const;
export const UPLOAD_CANDIDATES_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'fgaUploadAuthorizationId', 'linkedFlickrRevision', 'observedAt', 'minUploadDate', 'maxUploadDate', 'page', 'pageSize', 'pages', 'total', 'photos'],
  properties: { schemaVersion: { const: 1 }, fgaUploadAuthorizationId: idSchema,
    linkedFlickrRevision: { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER }, observedAt: { type: 'string', format: 'date-time', pattern: '\\.[0-9]{6}Z$' },
    minUploadDate: secondsSchema, maxUploadDate: secondsSchema, page: { type: 'integer', minimum: 1, maximum: 1000 }, pageSize: { type: 'integer', minimum: 1, maximum: 100 },
    pages: { type: 'integer', minimum: 0, maximum: 2147483647 }, total: { type: 'integer', minimum: 0, maximum: 2147483647 },
    photos: { type: 'array', maxItems: 100, items: { type: 'object', additionalProperties: false,
      required: ['flickrPhotoId', 'title', 'dateUploaded', 'thumbnail', 'photopageUrl'], properties: {
        flickrPhotoId: idSchema, title: { type: 'string', maxLength: 4096 }, dateUploaded: secondsSchema,
        thumbnail: { type: 'object', additionalProperties: false, required: ['url', 'sizeClass'], properties: { url: { type: 'string', format: 'uri', maxLength: 2048 }, sizeClass: { const: 'q' } } },
        photopageUrl: { type: 'string', format: 'uri' } } } } } } as const;
export const UPLOAD_CANDIDATES_ROUTES = [{ id: 'uploadAmbiguityCandidates', method: 'GET',
  pathPattern: '/api/v001/upload-authorizations/{uploadAuthorizationId}/ambiguity-candidates', owner: 'fga_api_backend', routingClass: 'worker_first',
  probe: 'missing_authentication', expectedStatus: 401, expectedChallenge: 'Bearer realm="fga-api"', handler: 'upload_candidates', auth: 'installation_bearer', allowPending: false,
  response: UPLOAD_CANDIDATES_RESPONSE_SCHEMA, successStatuses: [200], request: null }] as const;
const encoder = new TextEncoder();
const fail = (code = 'ambiguity_candidates_unavailable'): never => { throw new Error(code); };
function failure(code: string): Response {
  const status = code === 'invalid_token' ? 401 : code === 'not_found' ? 404 : ['invalid_request', 'candidate_page_out_of_range'].includes(code) ? 400
    : ['flickr_link_changed', 'upload_already_bound'].includes(code) ? 409 : 503;
  const safe = status === 503 && code !== 'ambiguity_candidate_page_budget_exceeded' ? 'ambiguity_candidates_unavailable' : code;
  const response = errorResponse(status, safe, 'Upload candidate read unavailable.', status === 401);
  response.headers.set('Cache-Control', 'private, no-store');
  if (status === 503 && safe === 'ambiguity_candidates_unavailable') response.headers.set('Retry-After', '5');
  return response;
}
export function uploadCandidatesQuery(url: URL): { page: number; size: number } {
  const q = url.searchParams;
  if ([...q.keys()].some(k => !['page', 'page_size'].includes(k)) || q.getAll('page').length !== 1 || q.getAll('page_size').length !== 1) fail('invalid_request');
  const page = q.get('page')!, size = q.get('page_size')!;
  if (!/^[1-9][0-9]{0,3}$/.test(page) || !/^[1-9][0-9]{0,2}$/.test(size) || Number(page) > 1000 || Number(size) > 100) fail('invalid_request');
  return { page: Number(page), size: Number(size) };
}
interface Credential { userId: string; versionId: string; revision: string; }
interface Retained { photoId: string | null; issuedAt: number; ownerNsid: string | null; linkRevision: number | null; observedAtUs: number; }
async function credential(db: SqlStore, auth: AdmissionAuth): Promise<Credential | null> {
  return db.prepare(`SELECT i.user_id userId,v.version_id versionId,CAST(i.revision AS TEXT) revision FROM installations i
    JOIN installation_credential_versions v ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
    WHERE i.installation_id=? AND i.state='active' AND i.credential_class='lrc_plugin' AND v.state='current' AND v.credential_digest=?`)
    .bind(auth.installationId, auth.credentialDigest).first<Credential>();
}
async function retained(db: SqlStore, auth: AdmissionAuth, user: string, id: string): Promise<Retained | null> {
  return db.prepare(`SELECT photo_id photoId,issued_at_us issuedAt,owner_nsid ownerNsid,link_revision linkRevision,${NOW_US_SQL} observedAtUs
    FROM upload_authorizations WHERE authorization_id=? AND installation_id=? AND user_id=?`).bind(id, auth.installationId, user).first<Retained>();
}
function seconds(v: unknown): v is string { return typeof v === 'string' && /^(0|[1-9][0-9]{0,11})$/.test(v); }
function thumbnail(value: unknown): string {
  if (typeof value !== 'string' || value.length > 2048 || !/^[\x21-\x7e]+$/.test(value)) fail();
  const raw = value as string;
  // Match the raw representation too: URL parsing normalizes credentials, ports and dot paths.
  if (!/^https:\/\/live\.staticflickr\.com\/[0-9]+\/[A-Za-z0-9_-]+_q\.(?:jpg|jpeg|png)$/i.test(raw)) fail();
  const url = new URL(raw);
  if (url.hostname !== 'live.staticflickr.com' || url.protocol !== 'https:' || url.port || url.username || url.password || url.search || url.hash) fail();
  return raw;
}
export function validateUploadCandidatePage(value: unknown, query: { page: number; size: number }, owner: string, min: number, max: number) {
  if (!photoObject(value) || value.stat !== 'ok' || !photoObject(value.photos)) return fail();
  const root = value.photos, page = photoInteger(root.page), pages = photoInteger(root.pages), total = photoInteger(root.total);
  const size = photoInteger(root.perpage ?? root.per_page);
  if (root.perpage !== undefined && root.per_page !== undefined && photoInteger(root.perpage) !== photoInteger(root.per_page)) fail();
  if (page !== query.page || size !== query.size || total > 2147483647 || pages > 2147483647 || !Array.isArray(root.photo)) return fail();
  if (total === 0) {
    if (![0, 1].includes(pages) || root.photo.length) fail();
    if (page !== 1) fail('candidate_page_out_of_range');
    return { page, pageSize: size, pages: 0, total, photos: [] };
  }
  if (pages !== Math.ceil(total / size)) fail();
  if (page > pages) { if (root.photo.length) fail(); fail('candidate_page_out_of_range'); }
  if (root.photo.length !== Math.min(size, total - (page - 1) * size)) fail();
  const seen = new Set<string>();
  const photos = root.photo.map(row => {
    if (!photoObject(row) || typeof row.id !== 'string' || !PHOTO_ID.test(row.id) || seen.has(row.id) || row.owner !== owner || row.media !== 'photo'
      || typeof row.title !== 'string' || row.title.includes('\0') || encoder.encode(row.title).length > 4096 || !seconds(row.dateupload)
      || Number(row.dateupload) < min || Number(row.dateupload) > max) return fail();
    seen.add(row.id);
    return { flickrPhotoId: row.id, title: row.title, dateUploaded: row.dateupload, thumbnail: { url: thumbnail(row.url_q), sizeClass: 'q' },
      photopageUrl: `https://www.flickr.com/photos/${encodeURIComponent(owner)}/${encodeURIComponent(row.id)}/` };
  });
  return { page, pageSize: size, pages, total, photos };
}
async function body(request: Request, fetcher: FlickrFetch, signal: AbortSignal): Promise<unknown> {
  const response = await fetcher(new Request(request, { signal }));
  if (signal.aborted || !response.ok || !response.body || !/^application\/json\s*(?:;\s*charset\s*=\s*(?:utf-8|"utf-8")\s*)?$/i.test(response.headers.get('Content-Type') ?? '')) fail();
  const reader = response.body!.getReader(), chunks: Uint8Array[] = []; let size = 0;
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    for (;;) {
      if (signal.aborted) fail();
      const { done, value } = await reader.read();
      if (signal.aborted) fail();
      if (done) break;
      size += value.length;
      if (size > UPLOAD_CANDIDATE_LIMITS.upstreamBytes) fail('ambiguity_candidate_page_budget_exceeded');
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes));
  } catch (error) { cancel(); throw error; }
  finally { signal.removeEventListener('abort', cancel); }
}
/** One advisory owner page; no binding, resolution, authorization refresh or persistence. */
export async function uploadCandidatesRequest(env: UploadCandidatesEnv, auth: AdmissionAuth, authorizationId: string, url: URL,
  fetcher: FlickrFetch, now: () => number = () => performance.now()): Promise<Response> {
  if (env.FGA_UPLOAD_CANDIDATES_ENABLED !== '1') return failure('ambiguity_candidates_unavailable');
  const start = now(), controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    if (!Number.isFinite(start)) fail();
    return await Promise.race([(async () => {
      const query = uploadCandidatesQuery(url);
      const current = await credential(env.DB, auth); if (!current) return failure('invalid_token');
      if (!PHOTO_ID.test(authorizationId)) return failure('not_found');
      const record = await retained(env.DB, auth, current.userId, authorizationId); if (!record) return failure('not_found');
      if (record.photoId !== null) return failure('upload_already_bound');
      if (record.ownerNsid === null || record.linkRevision === null) fail();
      const grant = await linkedGrant(env.DB, auth);
      if (!grant || grant.userId !== current.userId || record.ownerNsid !== grant.ownerNsid || record.linkRevision !== Number(grant.revision)) return failure('flickr_link_changed');
      if (!PHOTO_ID.test(grant.ownerNsid) || !Number.isSafeInteger(record.linkRevision) || record.linkRevision! < 1) fail();
      if (!Number.isSafeInteger(record.issuedAt) || record.issuedAt < 0 || !Number.isSafeInteger(record.observedAtUs) || record.observedAtUs < record.issuedAt) fail();
      const issued = Math.floor(record.issuedAt / 1_000_000), observed = Math.floor(record.observedAtUs / 1_000_000);
      const min = Math.max(0, issued - 120), max = Math.min(observed, issued + 86400);
      if (min > max || !seconds(String(min)) || !seconds(String(max))) fail();
      const page = await withGrant(env.DB, auth, env, grant, async (pair, app) => {
        if (controller.signal.aborted) fail();
        const beforeRead = await credential(env.DB, auth);
        if (!beforeRead || JSON.stringify(current) !== JSON.stringify(beforeRead)) fail('invalid_token');
        if (controller.signal.aborted) fail();
        const value = await body(signedPhotoRead('flickr.people.getPhotos', { user_id: grant.ownerNsid, content_types: '0,1,2,3', extras: 'date_upload,media,url_q',
          min_upload_date: String(min), max_upload_date: String(max), page: String(query.page), per_page: String(query.size) }, pair, app), fetcher, controller.signal);
        return validateUploadCandidatePage(value, query, grant.ownerNsid, min, max);
      }).catch(async error => {
        if (controller.signal.aborted) throw error;
        const latest = await credential(env.DB, auth);
        if (!latest || JSON.stringify(current) !== JSON.stringify(latest)) fail('invalid_token');
        throw error;
      });
      const after = await credential(env.DB, auth);
      if (!after || JSON.stringify(current) !== JSON.stringify(after)) return failure('invalid_token');
      if (!sameGrant(grant, await linkedGrant(env.DB, auth))) return failure('flickr_link_changed');
      const finalRecord = await retained(env.DB, auth, current.userId, authorizationId);
      if (!finalRecord) return failure('not_found');
      if (finalRecord.photoId !== null) return failure('upload_already_bound');
      if (finalRecord.ownerNsid !== record.ownerNsid || finalRecord.linkRevision !== record.linkRevision || finalRecord.issuedAt !== record.issuedAt) fail();
      const stamp = new Date(Math.floor(record.observedAtUs / 1000)).toISOString().replace(/\.(\d{3})Z$/, (_, ms: string) => `.${ms}${String(record.observedAtUs % 1000).padStart(3, '0')}Z`);
      const serialized = JSON.stringify({ schemaVersion: 1, fgaUploadAuthorizationId: authorizationId, linkedFlickrRevision: record.linkRevision, observedAt: stamp,
        minUploadDate: String(min), maxUploadDate: String(max), ...page });
      if (encoder.encode(serialized).length > UPLOAD_CANDIDATE_LIMITS.responseBytes) fail('ambiguity_candidate_page_budget_exceeded');
      const elapsed = now() - start;
      if (controller.signal.aborted || !Number.isFinite(elapsed) || elapsed < 0 || elapsed >= UPLOAD_CANDIDATE_LIMITS.elapsedMs) fail();
      return new Response(serialized, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' } });
    })(), new Promise<never>((_, reject) => { timer = setTimeout(() => { controller.abort(); reject(new Error('deadline')); }, UPLOAD_CANDIDATE_LIMITS.elapsedMs); })]);
  } catch (error) { return failure(error instanceof Error ? error.message : 'ambiguity_candidates_unavailable'); }
  finally { if (timer !== undefined) clearTimeout(timer); controller.abort(); }
}
