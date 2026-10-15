import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse } from './installations.ts';
import { linkedGrant, sameGrant, withGrant, type FlickrFetch, type SecretReads } from './flickr_reads.ts';
import { discoveryQuery, PHOTO_ID, photoAuthLive, photoReadBody, photoUnavailable,
  rejectPhotoGrant, signedPhotoRead, validateDiscovery } from './existing_photo_discovery.ts';

// Candidate only. Production enablement requires the separate hosted and LrC gates.
export const THUMBNAIL_HOST_QUALIFIED = false;
export const THUMBNAIL_LIMITS = { bytes: 256 * 1024, elapsedMs: 15_000 } as const;
export function thumbnailQuery(url: URL) {
  const revision = url.searchParams.get('linked_flickr_revision');
  if (url.searchParams.getAll('linked_flickr_revision').length !== 1 || !revision
    || !/^[1-9][0-9]*$/.test(revision) || !Number.isSafeInteger(Number(revision))) throw new Error('invalid_request');
  const pageUrl = new URL(url); pageUrl.searchParams.delete('linked_flickr_revision');
  return { ...discoveryQuery(pageUrl), revision };
}
export function thumbnailDestination(raw: string, photoId?: string): URL {
  const url = new URL(raw);
  if (raw.length > 2048 || url.protocol !== 'https:' || url.hostname !== 'live.staticflickr.com'
    || url.port || url.username || url.password || url.search || url.hash
    || !/^\/[0-9]+\/[A-Za-z0-9_-]+_q\.(?:jpg|jpeg|png)$/i.test(url.pathname)) throw new Error('destination');
  // Flickr documents /{server-id}/{id}_{secret}_{size-suffix}.jpg. Compare
  // the opaque ID verbatim; never infer its identity from another URL.
  const filename = url.pathname.split('/')[2]!;
  if (photoId !== undefined && (!filename.startsWith(photoId + '_')
    || !/^[A-Za-z0-9-]+_q\.(?:jpg|jpeg|png)$/i.test(filename.slice(photoId.length + 1)))) throw new Error('destination');
  return url;
}
export function thumbnailSignature(bytes: Uint8Array, type: string): boolean {
  return type === 'image/jpeg' ? bytes.length >= 5 && bytes[0] === 0xff && bytes[1] === 0xd8
    && bytes[2] === 0xff && bytes.at(-2) === 0xff && bytes.at(-1) === 0xd9 :
    type === 'image/png' && bytes.length >= 45 && [137, 80, 78, 71, 13, 10, 26, 10].every((v, i) => bytes[i] === v)
      && [0, 0, 0, 13, 73, 72, 68, 82].every((v, i) => bytes[i + 8] === v)
      && [0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130].every((v, i) => bytes[bytes.length - 12 + i] === v);
}
/** No credentials, referrer, client headers, redirects, or streamed response publication. */
export async function thumbnailBody(raw: string, fetcher: FlickrFetch, signal: AbortSignal, photoId?: string) {
  const destination = thumbnailDestination(raw, photoId);
  if (signal.aborted) throw new Error('cancelled');
  const response = await fetcher(new Request(destination, { redirect: 'manual', signal,
    headers: { Accept: 'image/jpeg, image/png' } }));
  const cancelBody = () => { void response.body?.cancel().catch(() => {}); };
  const type = response.headers.get('Content-Type')?.toLowerCase();
  const length = response.headers.get('Content-Length');
  if (signal.aborted || response.status !== 200 || response.redirected || !response.body
    || !['image/jpeg', 'image/png'].includes(type ?? '')
    || (length !== null && (!/^(0|[1-9][0-9]*)$/.test(length) || Number(length) > THUMBNAIL_LIMITS.bytes))) {
    cancelBody(); throw new Error('upstream');
  }
  const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    for (;;) {
      if (signal.aborted) throw new Error('cancelled');
      const { done, value } = await reader.read();
      if (signal.aborted) throw new Error('cancelled');
      if (done) break;
      size += value.byteLength;
      if (size > THUMBNAIL_LIMITS.bytes) throw new Error('byte_limit');
      chunks.push(value);
    }
    if (length !== null && size !== Number(length)) throw new Error('truncated');
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    if (!thumbnailSignature(bytes, type!)) throw new Error('signature');
    return { bytes, type: type! };
  } catch (error) { cancel(); throw error; }
  finally { signal.removeEventListener('abort', cancel); reader.releaseLock(); }
}
/** Bounds the whole operation, including authority reads and final publication fencing. */
export async function boundedThumbnail<T>(operation: (signal: AbortSignal) => Promise<T>, requestSignal?: AbortSignal,
  now: () => number = () => performance.now()): Promise<T> {
  const controller = new AbortController(), start = now(); let timer: ReturnType<typeof setTimeout> | undefined;
  let rejectAbort: (error: Error) => void = () => {};
  const abort = () => { controller.abort(); rejectAbort(new Error('cancelled')); };
  try {
    if (!Number.isFinite(start) || requestSignal?.aborted) throw new Error('cancelled');
    const cancelled = new Promise<never>((_, reject) => { rejectAbort = reject; });
    requestSignal?.addEventListener('abort', abort, { once: true });
    timer = setTimeout(abort, THUMBNAIL_LIMITS.elapsedMs);
    const result = await Promise.race([operation(controller.signal), cancelled]);
    const elapsed = now() - start;
    if (controller.signal.aborted || !Number.isFinite(elapsed) || elapsed < 0 || elapsed >= THUMBNAIL_LIMITS.elapsedMs) throw new Error('deadline');
    return result;
  } finally { if (timer !== undefined) clearTimeout(timer); requestSignal?.removeEventListener('abort', abort); controller.abort(); }
}
export async function photoThumbnailRequest(db: SqlStore, auth: AdmissionAuth, photoId: string, url: URL,
  secrets: SecretReads, fetcher: FlickrFetch, thumbnailFetcher: FlickrFetch, requestSignal?: AbortSignal, now?: () => number): Promise<Response> {
  try {
    if (!PHOTO_ID.test(photoId)) throw new Error('invalid_request');
    const query = thumbnailQuery(url);
    return await boundedThumbnail(async signal => {
      const check = () => { if (signal.aborted) throw new Error('cancelled'); };
      if (!await photoAuthLive(db, auth)) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
      check(); const grant = await linkedGrant(db, auth); check();
      if (!grant || grant.revision !== query.revision) return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
      const page = await withGrant(db, auth, secrets, grant, async (pair, app) => {
        check(); const value = await photoReadBody(signedPhotoRead('flickr.people.getPhotos', { user_id: grant.ownerNsid,
          privacy_filter: '1', content_types: '0', extras: 'date_upload,date_taken,media,url_q', page: String(query.page),
          per_page: String(query.size) }, pair, app), fetcher, signal);
        check(); await rejectPhotoGrant(db, auth, grant, value); check();
        return validateDiscovery(value, query, grant.ownerNsid);
      });
      check(); const photo = page.photos.find(row => row.flickrPhotoId === photoId);
      if (!photo) throw new Error('photo_missing');
      const { bytes, type } = await thumbnailBody(photo.thumbnail.url, thumbnailFetcher, signal, photoId); check();
      if (!await photoAuthLive(db, auth)) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
      check(); if (!sameGrant(grant, await linkedGrant(db, auth))) return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
      check(); return new Response(bytes, { headers: { 'Content-Type': type, 'Content-Length': String(bytes.byteLength),
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
        'Cross-Origin-Resource-Policy': 'same-origin' } });
    }, requestSignal, now);
  } catch (error) {
    if (error instanceof Error && error.message === 'invalid_request') return errorResponse(400, 'invalid_request', 'Invalid photo thumbnail reference.');
    if (error instanceof Error && error.message === 'flickr_link_changed') return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
    return photoUnavailable('photo_thumbnail_unavailable');
  }
}
