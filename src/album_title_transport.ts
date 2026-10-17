import { readJson, type FlickrFetch } from './flickr_reads.ts';
import { strictFlickrJson } from './flickr_strict_json.ts';
import { ProvenNotDispatched } from './dispatch_policy.ts';

export type AlbumTitleMethod = 'flickr.photosets.getInfo' | 'flickr.photosets.editMeta';
export interface AlbumTitleIdentity { photosetId: string; ownerNsid: string; title: string; }
export interface AlbumTitleObservation { photosetId: string; ownerNsid: string; title: string; }
export interface PreparedAlbumTitleEdit { handoff(): Promise<void>; dispose(): void; }
export interface AlbumTitleTransport {
  read(): Promise<AlbumTitleObservation>;
  prepareEdit(): Promise<PreparedAlbumTitleEdit>;
}
export class AlbumTitleTransportError extends Error {
  constructor() { super('album_title_upstream_unavailable'); }
}
export class AlbumTitleMissingError extends AlbumTitleTransportError {}
const invalid = (): never => { throw new AlbumTitleTransportError(); };
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
const keys = (v: Record<string, unknown>, names: string[]): boolean => Object.keys(v).length === names.length && names.every(name => Object.hasOwn(v, name));
const id = (v: unknown): v is string => typeof v === 'string' && v !== '0' && /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(v) && !/[\r\n]/.test(v);
const text = (v: unknown, bytes: number): v is string => typeof v === 'string' && !/[\p{Cc}\p{Cs}]/u.test(v) && new TextEncoder().encode(v).length <= bytes;

/** Complete exact-resource evidence, without truncation or normalization. */
export function albumTitleObservation(value: Record<string, unknown>, photosetId: string, ownerNsid: string): AlbumTitleObservation {
  if (value.stat === 'fail' && keys(value, ['stat', 'code', 'message']) && value.code === 1 && text(value.message, 4096)) throw new AlbumTitleMissingError();
  if (value.stat !== 'ok' || !keys(value, ['stat', 'photoset']) || !object(value.photoset)) return invalid();
  const set = value.photoset;
  if (set.id !== photosetId || set.owner !== ownerNsid || !id(set.primary) || !object(set.title) || !keys(set.title, ['_content']) || !text(set.title._content, 4096)) return invalid();
  const scalarFields = new Set(['id', 'owner', 'primary', 'secret', 'server', 'farm', 'photos',
    'count_views', 'count_comments', 'count_photos', 'count_videos', 'can_comment',
    'date_create', 'date_update', 'ownername', 'username', 'iconserver', 'iconfarm',
    'needs_interstitial', 'visibility_can_see_set']);
  for (const [key, field] of Object.entries(set)) {
    if (key === 'title') continue;
    if (key === 'description') {
      if (!object(field) || !keys(field, ['_content']) || typeof field._content !== 'string' || /\p{Cs}/u.test(field._content)) return invalid();
    } else if (!scalarFields.has(key) || !(typeof field === 'string' && !/[\p{Cc}\p{Cs}]/u.test(field) || typeof field === 'number' && Number.isSafeInteger(field) && field >= 0)) return invalid();
  }
  return { photosetId, ownerNsid, title: set.title._content };
}
export interface SyntheticAlbumTitleDependencies {
  sign(method: AlbumTitleMethod, data: Record<string, string>, post: boolean): Request;
  fetcher: FlickrFetch;
  assertCurrent(): Promise<void>;
  /** Explicit admission through the shared Flickr fault/rate gates. */
  beforeRequest(method: AlbumTitleMethod): Promise<void>;
  execution: { signal: AbortSignal; remainingMs(): number; };
  deadlineMs?: number;
}

/** Dormant injected seam, one edit handoff, no credentials or hidden retries.
 * Worker commits the marker after preparation, and owns reconciliation priority.
 */
export function createSyntheticAlbumTitleTransport(input: AlbumTitleIdentity, deps?: SyntheticAlbumTitleDependencies): AlbumTitleTransport {
  if (!deps || typeof deps.sign !== 'function' || typeof deps.fetcher !== 'function' || typeof deps.assertCurrent !== 'function' || typeof deps.beforeRequest !== 'function' ||
      !deps.execution || !(deps.execution.signal instanceof AbortSignal) || typeof deps.execution.remainingMs !== 'function' ||
      !id(input.photosetId) || !id(input.ownerNsid) || !text(input.title, 4000) || [...input.title].length < 1 || [...input.title].length > 1000) return invalid();
  const identity = Object.freeze({ ...input });
  const duration = deps.deadlineMs ?? 10_000;
  if (!Number.isSafeInteger(duration) || duration < 1 || duration > 10_000) return invalid();
  let busy = false, preparedOnce = false, observed = false;
  const invocationDeadline = performance.now() + 10_000;
  async function bounded<T>(operation: (signal: AbortSignal, deadline: number) => Promise<T>): Promise<T> {
    if (busy) return invalid();
    const left = deps!.execution.remainingMs();
    const remaining = Math.min(duration, left, invocationDeadline - performance.now());
    if (!Number.isFinite(left) || remaining <= 0 || deps!.execution.signal.aborted) return invalid();
    busy = true;
    const abort = new AbortController(), deadline = performance.now() + remaining;
    const signal = AbortSignal.any([abort.signal, deps!.execution.signal]);
    let timer: ReturnType<typeof setTimeout> | undefined;
    let onAbort: (() => void) | undefined;
    try {
      const result = await Promise.race([operation(signal, deadline), new Promise<never>((_, reject) => {
        onAbort = () => reject(new AlbumTitleTransportError());
        signal.addEventListener('abort', onAbort, { once: true });
        if (signal.aborted) onAbort();
        timer = setTimeout(() => { abort.abort(); reject(new AlbumTitleTransportError()); }, remaining);
      })]);
      if (signal.aborted || performance.now() >= deadline || deps!.execution.remainingMs() <= 0) return invalid();
      return result;
    } catch (error) {
      if (error instanceof AlbumTitleMissingError || error instanceof ProvenNotDispatched) throw error;
      return invalid();
    } finally { busy = false; if (onAbort) signal.removeEventListener('abort', onAbort); abort.abort(); if (timer !== undefined) clearTimeout(timer); }
  }
  async function request(method: AlbumTitleMethod): Promise<Request> {
    const post = method === 'flickr.photosets.editMeta';
    const data: Record<string, string> = post ? { photoset_id: identity.photosetId, title: identity.title } : { photoset_id: identity.photosetId };
    const signed = deps!.sign(method, { ...data }, post), url = new URL(signed.url);
    if (url.origin !== 'https://www.flickr.com' || url.pathname !== '/services/rest/' || url.username || url.password || url.hash || signed.method !== (post ? 'POST' : 'GET') || signed.redirect !== 'manual') return invalid();
    if (post && (url.search || signed.headers.get('Content-Type') !== 'application/x-www-form-urlencoded')) return invalid();
    const params = post ? new URLSearchParams(await signed.clone().text()) : url.searchParams;
    const expected = { method, format: 'json', nojsoncallback: '1', ...data };
    if ([...params].length !== Object.keys(expected).length || Object.entries(expected).some(([key, value]) => params.getAll(key).length !== 1 || params.get(key) !== value)) return invalid();
    return signed;
  }
  const json = (req: Request, signal: AbortSignal, deadline: number) => readJson(req, next => {
    if (signal.aborted || performance.now() >= deadline) return Promise.reject(new AlbumTitleTransportError());
    return deps!.fetcher(new Request(next, { signal: AbortSignal.any([signal, next.signal]) }));
  }, raw => strictFlickrJson(raw, 1_048_576), { maxBytes: 1_048_576, signal });
  return {
    async read() {
      observed = false;
      const result = await bounded(async (signal, deadline) => {
        await deps!.beforeRequest('flickr.photosets.getInfo');
        await deps!.assertCurrent();
        const req = await request('flickr.photosets.getInfo');
        return albumTitleObservation(await json(req, signal, deadline), identity.photosetId, identity.ownerNsid);
      });
      observed = true;
      return result;
    },
    async prepareEdit() {
      if (!observed || preparedOnce) return invalid();
      preparedOnce = true;
      const req = await bounded(async () => {
        await deps!.beforeRequest('flickr.photosets.editMeta');
        await deps!.assertCurrent();
        return request('flickr.photosets.editMeta');
      });
      let disposed = false, sent = false;
      const expiresAt = performance.now() + duration;
      return {
        handoff() {
          if (sent) return Promise.reject(new AlbumTitleTransportError());
          sent = true;
          if (disposed || performance.now() >= expiresAt) return Promise.reject(new ProvenNotDispatched());
          // Enter HTTP synchronously after the worker's durable dispatch marker.
          return bounded(async (signal, deadline) => {
            const value = await json(req, signal, deadline);
            if (value.stat !== 'ok' || !keys(value, ['stat'])) return invalid();
          });
        },
        dispose() { disposed = true; },
      };
    },
  };
}
