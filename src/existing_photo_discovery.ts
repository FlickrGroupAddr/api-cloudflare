import OAuth from 'oauth-1.0a';
import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse } from './installations.ts';
import { hmac, linkedGrant, sameGrant, withGrant, rejectCurrentGrant,
  type GrantSnapshot, type Pair, type Application, type SecretReads, type FlickrFetch } from './flickr_reads.ts';

export const PHOTO_READ_LIMITS = { bytes: 2 * 1024 * 1024, elapsedMs: 15_000, contexts: 10_000 } as const;
export const PHOTO_ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
export const photoObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
export function photoInteger(v: unknown): number {
  if (typeof v !== 'number' && (typeof v !== 'string' || !/^(0|[1-9][0-9]*)$/.test(v))) throw new Error('shape');
  const n = Number(v);
  if (!Number.isSafeInteger(n) || n < 0) throw new Error('shape');
  return n;
}
export function photoTitle(v: unknown): v is string {
  return typeof v === 'string' && v.length <= 1024 && !/[\x00-\x1f\x7f]/.test(v);
}
export function photoJson(body: unknown): Response {
  return Response.json(body, { headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' } });
}
export function photoUnavailable(code: string): Response {
  const correlationId = crypto.randomUUID();
  console.warn('fga_photo_read_unavailable', { reason: code, correlationId });
  const response = photoJson({ schemaVersion: 1, error: { code, message: 'The Flickr observation is unavailable.', retryable: true, correlationId } });
  response.headers.set('Retry-After', '5');
  return new Response(response.body, { status: 503, headers: response.headers });
}
function uploadDate(value: unknown): value is string {
  return typeof value === 'string' && /^(0|[1-9][0-9]{0,12})$/.test(value)
    && Number.isFinite(new Date(Number(value) * 1000).getTime());
}
function takenDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)) return false;
  const date = new Date(value.replace(' ', 'T') + 'Z');
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 19).replace('T', ' ') === value;
}
export async function photoAuthLive(db: SqlStore, auth: AdmissionAuth): Promise<boolean> {
  return !!await db.prepare(`SELECT 1 FROM installations i JOIN installation_credential_versions v
    ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
    WHERE i.installation_id=? AND i.state='active' AND i.credential_class='lrc_plugin'
    AND v.state='current' AND v.credential_digest=?`).bind(auth.installationId, auth.credentialDigest).first();
}
export function signedPhotoRead(method: 'flickr.people.getPhotos' | 'flickr.photos.getAllContexts',
  params: Record<string, string>, pair: Pair, app: Application): Request {
  const url = new URL('https://www.flickr.com/services/rest/');
  for (const [key, value] of Object.entries({ method, ...params, format: 'json', nojsoncallback: '1' })) url.searchParams.set(key, value);
  const oauth = new OAuth({ consumer: { key: app.consumerKey, secret: app.consumerSecret }, signature_method: 'HMAC-SHA1', hash_function: hmac });
  oauth.getNonce = () => Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join('');
  return new Request(url, { redirect: 'manual', headers: { Accept: 'application/json',
    ...oauth.toHeader(oauth.authorize({ url: String(url), method: 'GET' }, { key: pair.token, secret: pair.tokenSecret })) } });
}
/** Includes secret resolution, fetch, streaming body consumption and complete validation. */
export async function boundedPhotoRead<T>(operation: (signal: AbortSignal) => Promise<T>, now: () => number = () => performance.now()): Promise<T> {
  const start = now(), controller = new AbortController();
  if (!Number.isFinite(start)) throw new Error('deadline');
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const result = await Promise.race([operation(controller.signal), new Promise<never>((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new Error('deadline')); }, PHOTO_READ_LIMITS.elapsedMs);
    })]);
    const elapsed = now() - start;
    if (!Number.isFinite(elapsed) || elapsed < 0 || elapsed >= PHOTO_READ_LIMITS.elapsedMs) throw new Error('deadline');
    return result;
  } finally { if (timer !== undefined) clearTimeout(timer); controller.abort(); }
}
export async function photoReadBody(request: Request, fetcher: FlickrFetch, signal: AbortSignal): Promise<unknown> {
  if (signal.aborted) throw new Error('deadline');
  const response = await fetcher(new Request(request, { signal }));
  if (signal.aborted || !response.ok || !response.body || !/^application\/json\s*(?:;\s*charset\s*=\s*(?:utf-8|"utf-8")\s*)?$/i.test(response.headers.get('Content-Type') ?? '')) throw new Error('upstream');
  const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    for (;;) {
      if (signal.aborted) throw new Error('deadline');
      const { done, value } = await reader.read();
      if (signal.aborted) throw new Error('deadline');
      if (done) break;
      size += value.length;
      if (size > PHOTO_READ_LIMITS.bytes) throw new Error('byte_limit');
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes));
  } catch (error) { cancel(); throw error; }
  finally { signal.removeEventListener('abort', cancel); }
}
export function discoveryQuery(url: URL): { page: number; size: number } {
  const q = url.searchParams;
  for (const name of q.keys()) if (!['page', 'page_size'].includes(name) || q.getAll(name).length !== 1) throw new Error('invalid_request');
  const page = q.get('page'), size = q.get('page_size');
  if (!page || !size || !/^[1-9][0-9]*$/.test(page) || !/^[1-9][0-9]*$/.test(size)
    || !Number.isSafeInteger(Number(page)) || Number(size) > 100) throw new Error('invalid_request');
  return { page: Number(page), size: Number(size) };
}
export function validateDiscovery(value: unknown, query: { page: number; size: number }, owner: string) {
  if (!photoObject(value) || value.stat !== 'ok' || !photoObject(value.photos)) throw new Error('shape');
  const root = value.photos, page = photoInteger(root.page), pages = photoInteger(root.pages), total = photoInteger(root.total);
  const size = photoInteger(root.perpage ?? root.per_page);
  if (root.perpage !== undefined && root.per_page !== undefined && photoInteger(root.perpage) !== photoInteger(root.per_page)) throw new Error('shape');
  if (page !== query.page || size !== query.size || pages !== Math.ceil(total / size) && !(total === 0 && pages === 1)
    || !Array.isArray(root.photo) || root.photo.length !== Math.min(size, Math.max(0, total - (page - 1) * size))) throw new Error('shape');
  const seen = new Set<string>();
  const photos = root.photo.map(row => {
    if (!photoObject(row) || typeof row.id !== 'string' || !PHOTO_ID.test(row.id) || seen.has(row.id)
      || row.owner !== owner || ![1, '1'].includes(row.ispublic as number | string) || row.media !== 'photo'
      || !photoTitle(row.title) || !uploadDate(row.dateupload) || !takenDate(row.datetaken)
      || typeof row.url_q !== 'string' || row.url_q.length > 2048) throw new Error('shape');
    const thumbnail = new URL(row.url_q);
    if (thumbnail.protocol !== 'https:' || thumbnail.hostname !== 'live.staticflickr.com' || thumbnail.port || thumbnail.username || thumbnail.password
      || thumbnail.search || thumbnail.hash || !/^\/[0-9]+\/[A-Za-z0-9_-]+_q\.(?:jpg|jpeg|png)$/i.test(thumbnail.pathname)) throw new Error('shape');
    seen.add(row.id);
    return { flickrPhotoId: row.id, title: row.title, dateUploaded: row.dateupload, dateTaken: row.datetaken, thumbnail: { url: row.url_q, sizeClass: 'q' } };
  });
  return { page, pageSize: size, pages, total, photos };
}
export async function rejectPhotoGrant(db: SqlStore, auth: AdmissionAuth, grant: GrantSnapshot, value: unknown): Promise<void> {
  if (photoObject(value) && value.stat === 'fail' && typeof value.code === 'number'
    && Number.isSafeInteger(value.code) && typeof value.message === 'string' && value.message.length > 0
    && photoTitle(value.message) && [98, 99].includes(value.code)) {
    await rejectCurrentGrant(db, auth, grant); throw new Error('flickr_link_changed');
  }
}
export async function existingPhotosRequest(db: SqlStore, auth: AdmissionAuth, url: URL, secrets: SecretReads,
  fetcher: FlickrFetch, now?: () => number): Promise<Response> {
  try {
    const query = discoveryQuery(url);
    if (!await photoAuthLive(db, auth)) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
    const grant = await linkedGrant(db, auth);
    if (!grant) return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
    const page = await boundedPhotoRead(signal => withGrant(db, auth, secrets, grant, async (pair, app) => {
      const value = await photoReadBody(signedPhotoRead('flickr.people.getPhotos', { user_id: grant.ownerNsid,
        privacy_filter: '1', content_types: '0', extras: 'date_upload,date_taken,media,url_q', page: String(query.page), per_page: String(query.size) }, pair, app), fetcher, signal);
      await rejectPhotoGrant(db, auth, grant, value);
      return validateDiscovery(value, query, grant.ownerNsid);
    }), now);
    if (!await photoAuthLive(db, auth)) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
    if (!sameGrant(grant, await linkedGrant(db, auth))) return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
    return photoJson({ schemaVersion: 1, linkedFlickrRevision: Number(grant.revision), observedAt: new Date().toISOString(), ...page });
  } catch (error) {
    if (error instanceof Error && error.message === 'invalid_request') return errorResponse(400, 'invalid_request', 'Invalid public photo query.');
    if (error instanceof Error && error.message === 'flickr_link_changed') return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
    return photoUnavailable('existing_photo_discovery_unavailable');
  }
}
