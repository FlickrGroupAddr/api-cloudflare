import { readJson, type FlickrFetch } from './flickr_reads.ts';
import { strictFlickrJson } from './flickr_strict_json.ts';
import { albumContextIds, verifyInfo } from './album_materialization_transport.ts';
import { ProvenNotDispatched } from './dispatch_policy.ts';

export type AlbumAttachmentMethod = 'flickr.photosets.getInfo' | 'flickr.photos.getAllContexts' | 'flickr.photosets.addPhoto';
export interface AlbumAttachmentIdentity {
  attemptId: string; ownerNsid: string; photosetId: string; photoId: string; primaryPhotoId: string;
}
export interface AlbumAttachmentProof { ownerNsid: string; photoId: string; photosetId: string; contextIds: string[]; }
export interface PreparedAlbumAdd { handoff(): Promise<'added' | 'already_present'>; dispose(): void; }
export interface AlbumAttachmentTransport { read(): Promise<AlbumAttachmentProof>; prepareAdd(): Promise<PreparedAlbumAdd>; }
export class AlbumAttachmentTransportError extends Error {
  constructor() { super('album_attachment_upstream_unavailable'); }
}
export class AlbumAttachmentNeedsAttention extends AlbumAttachmentTransportError {
  readonly reason: 'wrong_owner' | 'missing_album' | 'missing_photo' | 'binding_conflict';
  constructor(reason: AlbumAttachmentNeedsAttention['reason']) { super(); this.reason = reason; }
}
export interface SyntheticAlbumAttachmentDependencies {
  sign(method: AlbumAttachmentMethod, data: Record<string, string>, post: boolean): Request;
  /** Runtime composition must inject the shared rate-budgeted Flickr fetch wrapper. */
  fetcher: FlickrFetch;
  assertCurrent(): Promise<void>;
  beforeRequest(method: AlbumAttachmentMethod): Promise<void>;
  deadlineMs?: number;
}
const id = (v: unknown): v is string => typeof v === 'string' && v !== '0' && /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(v) && !/[\r\n]/.test(v);
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
const keys = (v: Record<string, unknown>, names: string[]) => Object.keys(v).length === names.length && names.every(name => Object.hasOwn(v, name));
const text = (v: unknown): v is string => typeof v === 'string' && !/[\p{Cc}\p{Cs}]/u.test(v) && new TextEncoder().encode(v).length <= 4096;
const invalid = (): never => { throw new AlbumAttachmentTransportError(); };
function failure(value: Record<string, unknown>): number | null {
  if (value.stat !== 'fail') return null;
  if (!keys(value, ['stat', 'code', 'message']) || !Number.isSafeInteger(value.code) || !text(value.message)) return invalid();
  return value.code as number;
}
function info(value: Record<string, unknown>, identity: AlbumAttachmentIdentity): void {
  const code = failure(value);
  if (code === 1) throw new AlbumAttachmentNeedsAttention('missing_album');
  if (code !== null || value.stat !== 'ok' || !keys(value, ['stat', 'photoset']) || !object(value.photoset)) return invalid();
  const set = value.photoset;
  if (!id(set.id) || !id(set.owner)) return invalid();
  // Shared full-response validator checks all metadata before attention classification.
  verifyInfo(value, set.id, set.owner);
  if (set.id !== identity.photosetId) throw new AlbumAttachmentNeedsAttention('binding_conflict');
  if (set.owner !== identity.ownerNsid) throw new AlbumAttachmentNeedsAttention('wrong_owner');
}
function contexts(value: Record<string, unknown>): string[] {
  const code = failure(value);
  if (code === 1) throw new AlbumAttachmentNeedsAttention('missing_photo');
  if (code !== null) return invalid();
  return albumContextIds(value);
}
function added(value: Record<string, unknown>): 'added' | 'already_present' {
  if (value.stat === 'ok' && keys(value, ['stat'])) return 'added';
  const code = failure(value);
  if (code === 3) return 'already_present';
  if (code === 1) throw new AlbumAttachmentNeedsAttention('missing_album');
  if (code === 2) throw new AlbumAttachmentNeedsAttention('missing_photo');
  return invalid();
}

/** Dormant synthetic seam. No provider default, credentials, retry or durable marker.
 * Worker commits the one-use send authority before invoking prepared handoff.
 */
export function createSyntheticAlbumAttachmentTransport(input: AlbumAttachmentIdentity, deps?: SyntheticAlbumAttachmentDependencies): AlbumAttachmentTransport {
  if (!deps || typeof deps.sign !== 'function' || typeof deps.fetcher !== 'function' || typeof deps.assertCurrent !== 'function' || typeof deps.beforeRequest !== 'function' || ![input.attemptId, input.ownerNsid, input.photosetId, input.photoId, input.primaryPhotoId].every(id)) return invalid();
  const identity = Object.freeze({ ...input });
  const duration = deps.deadlineMs ?? 10_000;
  if (!Number.isSafeInteger(duration) || duration < 1 || duration > 10_000) return invalid();
  const invocationDeadline = performance.now() + 45_000;
  let phase: 'readable' | 'reading' | 'present' | 'absent' | 'prepared' | 'sent' = 'readable';
  let hasPrepared = false;
  async function bounded<T>(run: (signal: AbortSignal, deadline: number) => Promise<T>): Promise<T> {
    const controller = new AbortController();
    const remaining = Math.min(duration, invocationDeadline - performance.now());
    if (remaining <= 0) return invalid();
    const deadline = performance.now() + remaining;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const result = await Promise.race([run(controller.signal, deadline), new Promise<never>((_, reject) => {
        timer = setTimeout(() => { controller.abort(); reject(new AlbumAttachmentTransportError()); }, remaining);
      })]);
      if (performance.now() >= deadline || controller.signal.aborted) return invalid();
      return result;
    } catch (error) {
      if (error instanceof AlbumAttachmentNeedsAttention) throw error;
      return invalid();
    } finally { if (timer !== undefined) clearTimeout(timer); controller.abort(); }
  }
  async function request(method: AlbumAttachmentMethod, data: Record<string, string>): Promise<Request> {
    await deps!.beforeRequest(method);
    await deps!.assertCurrent();
    const post = method === 'flickr.photosets.addPhoto';
    const signed = deps!.sign(method, { ...data }, post);
    const url = new URL(signed.url);
    if (url.origin !== 'https://www.flickr.com' || url.pathname !== '/services/rest/' || url.username || url.password || url.hash || signed.method !== (post ? 'POST' : 'GET') || signed.redirect !== 'manual') return invalid();
    if (post && (url.search || signed.headers.get('Content-Type') !== 'application/x-www-form-urlencoded')) return invalid();
    const parameters = post ? new URLSearchParams(await signed.clone().text()) : url.searchParams;
    const expected = { method, format: 'json', nojsoncallback: '1', ...data };
    if ([...parameters].length !== Object.keys(expected).length || Object.entries(expected).some(([key, value]) => parameters.getAll(key).length !== 1 || parameters.get(key) !== value)) return invalid();
    return signed;
  }
  async function json(request: Request, signal: AbortSignal, deadline: number) {
    if (signal.aborted || performance.now() >= deadline) return invalid();
    return readJson(request, next => {
      if (signal.aborted || performance.now() >= deadline) return Promise.reject(new AlbumAttachmentTransportError());
      return deps!.fetcher(new Request(next, { signal: AbortSignal.any([signal, next.signal]) }));
    }, strictFlickrJson, { signal });
  }
  return {
    async read() {
      if (phase === 'reading' || phase === 'prepared' || phase === 'sent') return invalid();
      phase = 'reading';
      try {
        const proof = await bounded(async (signal, deadline) => {
          await deps!.assertCurrent();
          info(await json(await request('flickr.photosets.getInfo', { photoset_id: identity.photosetId }), signal, deadline), identity);
          await deps!.assertCurrent();
          const original = contexts(await json(await request('flickr.photos.getAllContexts', { photo_id: identity.primaryPhotoId }), signal, deadline));
          if (!original.includes(identity.photosetId)) throw new AlbumAttachmentNeedsAttention('binding_conflict');
          let contextIds = original;
          if (identity.photoId !== identity.primaryPhotoId) {
            await deps!.assertCurrent();
            contextIds = contexts(await json(await request('flickr.photos.getAllContexts', { photo_id: identity.photoId }), signal, deadline));
          }
          await deps!.assertCurrent();
          return { ownerNsid: identity.ownerNsid, photoId: identity.photoId, photosetId: identity.photosetId, contextIds };
        });
        phase = proof.contextIds.includes(identity.photosetId) ? 'present' : 'absent';
        return proof;
      } catch (error) { phase = 'readable'; throw error; }
    },
    async prepareAdd() {
      if (phase !== 'absent' || hasPrepared || identity.photoId === identity.primaryPhotoId) return invalid();
      hasPrepared = true;
      phase = 'prepared';
      let req: Request;
      try { req = await bounded(async () => { await deps!.assertCurrent(); return request('flickr.photosets.addPhoto', { photoset_id: identity.photosetId, photo_id: identity.photoId }); }); }
      catch (error) { phase = 'readable'; throw error; }
      const expiresAt = Math.min(performance.now() + duration, invocationDeadline);
      let disposed = false;
      return {
        handoff() {
          if (phase !== 'prepared') return Promise.reject(new AlbumAttachmentTransportError());
          if (disposed || performance.now() >= expiresAt) { phase = 'readable'; return Promise.reject(new ProvenNotDispatched()); }
          phase = 'sent';
          // Enter injected transport synchronously; durable marker belongs to worker.
          return bounded(async (signal, deadline) => added(await json(req, signal, deadline)))
            .finally(() => { phase = 'readable'; });
        },
        dispose() { disposed = true; },
      };
    },
  };
}
