import { readJson, type FlickrFetch } from './flickr_reads.ts';
import { strictFlickrJson } from './flickr_strict_json.ts';
import { albumContextIds, albumNavigationUrl, verifyInfo } from './album_materialization_transport.ts';
import { SERVICE_ID } from './publish_services.ts';

export type AlbumRepairReadMethod = 'flickr.photos.getAllContexts' | 'flickr.photosets.getInfo';
export interface AlbumRepairReadIdentity {
  bindingId: string; bindingRevision: number; createAttemptId: string;
  firstPhotoId: string; ownerNsid: string; preContextIds: string[];
}
export interface AlbumRepairCandidate {
  flickrPhotosetId: string; title: string; ownerNsid: string; primaryPhotoId: string;
  createdAt: null; updatedAt: null; navigationUrl: string; thumbnail: null;
}
export interface AlbumRepairCandidatePage {
  schemaVersion: 1; fgaAlbumBindingId: string; bindingRevision: number; createAttemptId: string;
  observedAt: string; page: number; pageSize: number; pages: number; total: number;
  candidates: AlbumRepairCandidate[];
}
export interface AlbumRepairSelectionProof {
  photosetId: string; url: string; ownerNsid: string; firstPhotoId: string;
  contextIds: string[]; observedAt: string;
}
export type AlbumRepairReadErrorCode = 'candidate_evidence_unavailable' | 'resolution_evidence_unavailable'
  | 'selected_album_not_verified' | 'page_out_of_range' | 'invalid_request' | 'service_unavailable';
export class AlbumRepairReadError extends Error {
  readonly code: AlbumRepairReadErrorCode;
  constructor(code: AlbumRepairReadErrorCode) { super(code); this.code = code; }
}
export interface AlbumRepairReadDependencies {
  /** Inject signedAlbumRest with an already verified synthetic pair; never a credential lookup. */
  sign(method: AlbumRepairReadMethod, parameters: Record<string, string>): Request;
  /** Future composition must inject the existing shared rate/fault guarded fetch wrapper. */
  fetcher: FlickrFetch;
  /** Recheck exact request, user/service, original owner/link/grant/pause, binding, attempt and lifecycle. */
  assertCurrent(): Promise<void>;
  /** Reserve shared read rate capacity before any upstream work; no retry is performed here. */
  reserveReads(count: number): Promise<void>;
  observedAt(): string;
  deadlineMs?: number;
}
const MiB = 1024 * 1024;
const id = (v: unknown): v is string => typeof v === 'string' && v !== '0' && /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(v) && !/[\r\n]/.test(v);
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
const fail = (code: AlbumRepairReadErrorCode): never => { throw new AlbumRepairReadError(code); };
function timestamp(v: unknown): v is string {
  if (typeof v !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$/.test(v)) return false;
  const millis = v.slice(0, 23) + 'Z', date = new Date(millis);
  return Number.isFinite(date.getTime()) && date.toISOString() === millis;
}
function contextInput(ids: unknown): ids is string[] {
  return Array.isArray(ids) && ids.length <= 1000 && ids.every(id) && new Set(ids).size === ids.length
    && new TextEncoder().encode(JSON.stringify(ids)).length <= MiB;
}
function candidate(value: Record<string, unknown>, photosetId: string, ownerNsid: string,
  unavailable: 'candidate_evidence_unavailable' | 'resolution_evidence_unavailable'): AlbumRepairCandidate {
  // Reuse the complete provider shape validator; do not turn partial metadata into a row.
  const set = value.photoset;
  if (!object(set) || !id(set.owner)) return fail(unavailable);
  try { verifyInfo(value, photosetId, set.owner); } catch { return fail(unavailable); }
  if (set.owner !== ownerNsid) return fail(unavailable === 'resolution_evidence_unavailable' ? 'selected_album_not_verified' : unavailable);
  for (const name of ['date_create', 'date_update']) {
    if (Object.hasOwn(set, name) && !(typeof set[name] === 'string' && /^(?:0|[1-9][0-9]{0,15})$/.test(set[name] as string)
      && Number.isSafeInteger(Number(set[name])) || typeof set[name] === 'number' && Number.isSafeInteger(set[name]) && (set[name] as number) >= 0)) return fail(unavailable);
  }
  // getInfo does not promise representative-image URLs or RFC3339 times. Do not invent either.
  const navigationUrl = albumNavigationUrl(`https://www.flickr.com/photos/${encodeURIComponent(ownerNsid)}/albums/${encodeURIComponent(photosetId)}/`, photosetId);
  return { flickrPhotosetId: photosetId, title: (set.title as { _content: string })._content,
    ownerNsid, primaryPhotoId: set.primary as string, createdAt: null, updatedAt: null, navigationUrl, thumbnail: null };
}

/** Dormant, read-only factory. Every method is a new observation; no candidate is ever selected or bound. */
export function createSyntheticAlbumCreateRepairReader(input: AlbumRepairReadIdentity, deps?: AlbumRepairReadDependencies) {
  if (!deps || ![deps.sign, deps.fetcher, deps.assertCurrent, deps.reserveReads, deps.observedAt].every(fn => typeof fn === 'function')
    || !input || !SERVICE_ID.test(input.bindingId) || !SERVICE_ID.test(input.createAttemptId)
    || !Number.isSafeInteger(input.bindingRevision) || input.bindingRevision < 1 || !id(input.firstPhotoId)
    || !id(input.ownerNsid) || !contextInput(input.preContextIds)) return fail('candidate_evidence_unavailable');
  const identity = Object.freeze({ ...input, preContextIds: Object.freeze([...input.preContextIds]) });
  const duration = deps.deadlineMs ?? 10_000;
  if (!Number.isSafeInteger(duration) || duration < 1 || duration > 10_000) return fail('candidate_evidence_unavailable');
  async function operation<T>(kind: 'candidate_evidence_unavailable' | 'resolution_evidence_unavailable', reserve: number,
    maxBytes: number, task: (read: (method: AlbumRepairReadMethod, parameters: Record<string, string>) => Promise<Record<string, unknown>>) => Promise<T>): Promise<T> {
    const abort = new AbortController(), deadline = performance.now() + duration;
    let timer: ReturnType<typeof setTimeout> | undefined, consumed = 0;
    const authorityErrors = new Set<unknown>();
    const current = async () => {
      if (abort.signal.aborted || performance.now() >= deadline) return fail(kind);
      try { await deps!.assertCurrent(); } catch (error) { authorityErrors.add(error); throw error; }
      if (abort.signal.aborted || performance.now() >= deadline) return fail(kind);
    };
    const run = async () => {
      await current();
      try { await deps!.reserveReads(reserve); } catch (error) { authorityErrors.add(error); throw error; }
      await current();
      let reads = 0;
      const result = await task(async (method, parameters) => {
        if (++reads > reserve) return fail(kind);
        await current();
        const signed = deps!.sign(method, { ...parameters }), url = new URL(signed.url);
        const expected = { method, format: 'json', nojsoncallback: '1', ...parameters };
        if (url.origin !== 'https://www.flickr.com' || url.pathname !== '/services/rest/' || url.username || url.password || url.hash
          || signed.method !== 'GET' || signed.redirect !== 'manual' || signed.body !== null
          || [...url.searchParams].length !== Object.keys(expected).length
          || Object.entries(expected).some(([key, value]) => url.searchParams.getAll(key).length !== 1 || url.searchParams.get(key) !== value)) return fail(kind);
        return readJson(signed, request => {
          if (abort.signal.aborted || performance.now() >= deadline) return Promise.reject(new AlbumRepairReadError(kind));
          return deps!.fetcher(new Request(request, { signal: AbortSignal.any([abort.signal, request.signal]) }));
        }, raw => strictFlickrJson(raw, MiB), { maxBytes: MiB, signal: abort.signal, onBytes: count => {
          consumed += count; if (consumed > maxBytes) return fail(kind);
        } });
      });
      await current();
      return result;
    };
    try {
      const result = await Promise.race([run(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => { abort.abort(); reject(new AlbumRepairReadError(kind)); }, duration);
      })]);
      if (performance.now() >= deadline) return fail(kind);
      return result;
    } catch (error) {
      if (authorityErrors.has(error) || error instanceof AlbumRepairReadError) throw error;
      return fail(kind);
    } finally { if (timer !== undefined) clearTimeout(timer); abort.abort(); }
  }
  const observedAt = (): string => { const value = deps!.observedAt(); if (!timestamp(value)) return fail('service_unavailable'); return value; };
  return {
    async discover(page: number, pageSize: number): Promise<AlbumRepairCandidatePage> {
      if (!Number.isSafeInteger(page) || page < 1 || page > 1000 || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 20) return fail('invalid_request');
      return operation('candidate_evidence_unavailable', pageSize + 1, 4 * MiB, async read => {
        const ids = albumContextIds(await read('flickr.photos.getAllContexts', { photo_id: identity.firstPhotoId }));
        const before = new Set(identity.preContextIds), difference = ids.filter(value => !before.has(value)).sort();
        const total = difference.length, pages = Math.ceil(total / pageSize);
        if (total === 0 ? page !== 1 : page > pages) return fail('page_out_of_range');
        const candidates: AlbumRepairCandidate[] = [];
        for (const photosetId of difference.slice((page - 1) * pageSize, page * pageSize)) {
          candidates.push(candidate(await read('flickr.photosets.getInfo', { photoset_id: photosetId }), photosetId, identity.ownerNsid, 'candidate_evidence_unavailable'));
        }
        const result: AlbumRepairCandidatePage = { schemaVersion: 1, fgaAlbumBindingId: identity.bindingId,
          bindingRevision: identity.bindingRevision, createAttemptId: identity.createAttemptId, observedAt: observedAt(),
          page, pageSize, pages, total, candidates };
        if (new TextEncoder().encode(JSON.stringify(result)).length > 512 * 1024) return fail('service_unavailable');
        return result;
      });
    },
    async prove(photosetId: string): Promise<AlbumRepairSelectionProof> {
      if (!id(photosetId)) return fail('invalid_request');
      return operation('resolution_evidence_unavailable', 2, 2 * MiB, async read => {
        const info = await read('flickr.photosets.getInfo', { photoset_id: photosetId });
        if (info.stat === 'fail' && Object.keys(info).length === 3 && Object.hasOwn(info, 'code') && Object.hasOwn(info, 'message')
          && info.code === 1 && typeof info.message === 'string' && !/[\p{Cc}\p{Cs}]/u.test(info.message)
          && new TextEncoder().encode(info.message).length <= 4096) return fail('selected_album_not_verified');
        const selected = candidate(info, photosetId, identity.ownerNsid, 'resolution_evidence_unavailable');
        const contextIds = albumContextIds(await read('flickr.photos.getAllContexts', { photo_id: identity.firstPhotoId }));
        if (!contextIds.includes(photosetId)) return fail('selected_album_not_verified');
        return { photosetId, url: selected.navigationUrl, ownerNsid: identity.ownerNsid,
          firstPhotoId: identity.firstPhotoId, contextIds, observedAt: observedAt() };
      });
    },
  };
}
