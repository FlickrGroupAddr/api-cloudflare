import { readJson, type FlickrFetch } from './flickr_reads.ts';
import { ProvenNotDispatched } from './dispatch_policy.ts';
import { strictFlickrJson } from './flickr_strict_json.ts';

export type AlbumMaterializationMethod = 'flickr.photos.getAllContexts' | 'flickr.photosets.create' | 'flickr.photosets.getInfo';
export interface AlbumMaterializationIdentity { attemptId: string; photoId: string; ownerNsid: string; title: string; }
export interface AlbumCreateResult { photosetId: string; url: string; }
export interface AlbumMaterializationProof extends AlbumCreateResult {
  ownerNsid: string;
  /** The immutable original first photo, not the album's mutable current primary. */
  primaryPhotoId: string;
  contextIds: string[];
}
export interface PreparedAlbumCreate { handoff(): Promise<AlbumCreateResult>; dispose(): void; }
export interface AlbumMaterializationTransport {
  contexts(): Promise<string[]>;
  prepareCreate(): Promise<PreparedAlbumCreate>;
  verify(photosetId: string): Promise<AlbumMaterializationProof>;
}
export class AlbumMaterializationTransportError extends Error {
  constructor() { super('album_materialization_upstream_unavailable'); }
}
/** Only documented validation/authentication rejections establish no creation. */
export class AlbumCreateRejected extends AlbumMaterializationTransportError {
  readonly code: number;
  constructor(code: number) { super(); this.code = code; }
}
const ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const MAX_CONTEXTS = 1000;
const NO_CREATE = new Set([1, 2, 3, 95, 96, 97, 98, 99, 100]);
const invalid = (): never => { throw new AlbumMaterializationTransportError(); };
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
const id = (v: unknown): v is string => typeof v === 'string' && v !== '0' && ID.test(v) && !/[\r\n]/.test(v);
const text = (v: unknown, bytes: number): v is string => typeof v === 'string' && !/[\p{Cc}\p{Cs}]/u.test(v) && new TextEncoder().encode(v).length <= bytes;
const keys = (v: Record<string, unknown>, names: string[]): boolean => Object.keys(v).length === names.length && names.every(name => Object.hasOwn(v, name));

export function albumNavigationUrl(value: unknown, photosetId: string): string {
  if (!text(value, 2048) || value.length === 0 || /[\s\\]/u.test(value)) return invalid();
  let url: URL;
  try { url = new URL(value); } catch { return invalid(); }
  if (url.protocol !== 'https:' || !['www.flickr.com', 'flickr.com'].includes(url.hostname) || url.port || url.username || url.password || url.search || url.hash) return invalid();
  const path = /^\/photos\/([^/]+)\/(?:sets|albums)\/([^/]+)\/?$/.exec(url.pathname);
  if (!path) return invalid();
  try { if (!id(decodeURIComponent(path[1]!)) || decodeURIComponent(path[2]!) !== photosetId) return invalid(); }
  catch { return invalid(); }
  return value;
}

/** Validate the entire nonpaginated response; never filter malformed/duplicate rows. */
export function albumContextIds(value: Record<string, unknown>): string[] {
  if (value.stat !== 'ok' || !keys(value, ['stat', 'set', 'pool'])) return invalid();
  const read = (rows: unknown): string[] => {
    if (!Array.isArray(rows) || rows.length > MAX_CONTEXTS) return invalid();
    const ids = new Set<string>();
    for (const row of rows) {
      if (!object(row) || !keys(row, ['id', 'title']) || !id(row.id) || !text(row.title, 4096) || ids.has(row.id)) return invalid();
      ids.add(row.id);
    }
    return [...ids];
  };
  const sets = read(value.set);
  read(value.pool);
  return sets;
}

export function albumCreateResult(value: Record<string, unknown>): AlbumCreateResult {
  if (value.stat === 'fail' && keys(value, ['stat', 'code', 'message']) && Number.isSafeInteger(value.code) && text(value.message, 4096) && NO_CREATE.has(value.code as number))
    throw new AlbumCreateRejected(value.code as number);
  if (value.stat !== 'ok' || !keys(value, ['stat', 'photoset']) || !object(value.photoset) || !keys(value.photoset, ['id', 'url']) || !id(value.photoset.id)) return invalid();
  return { photosetId: value.photoset.id, url: albumNavigationUrl(value.photoset.url, value.photoset.id) };
}

export function verifyInfo(value: Record<string, unknown>, photosetId: string, ownerNsid: string): void {
  if (value.stat !== 'ok' || !keys(value, ['stat', 'photoset']) || !object(value.photoset)) return invalid();
  const set = value.photoset;
  if (set.id !== photosetId || set.owner !== ownerNsid || !id(set.primary) || !object(set.title) || !keys(set.title, ['_content']) || !text(set.title._content, 4096)) return invalid();
  // Validate metadata containers too; unrelated malformed nested data is not a
  // complete photoset response. Metadata never establishes membership/identity.
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
}

export interface SyntheticAlbumMaterializationDependencies {
  sign(method: AlbumMaterializationMethod, data: Record<string, string>, post: boolean): Request;
  /** Inject the shared budgetedFlickrFetch wrapper for any future runtime binding. */
  fetcher: FlickrFetch;
  assertCurrent(): Promise<void>;
  deadlineMs?: number;
}

/** Dormant test seam: no credential reads, runtime factory, network default or retry.
 * Worker owns the durable marker and must call prepared handoff only after commit.
 */
export function createSyntheticAlbumMaterializationTransport(
  input: AlbumMaterializationIdentity, deps?: SyntheticAlbumMaterializationDependencies,
): AlbumMaterializationTransport {
  if (!deps || typeof deps.fetcher !== 'function' || typeof deps.sign !== 'function' || typeof deps.assertCurrent !== 'function' ||
      ![input.attemptId, input.photoId, input.ownerNsid].every(id) || !text(input.title, 4000) || [...input.title].length < 1 || [...input.title].length > 1000) return invalid();
  const identity = Object.freeze({ ...input });
  const duration = deps.deadlineMs ?? 10_000;
  if (!Number.isSafeInteger(duration) || duration < 1 || duration > 10_000) return invalid();
  const invocationDeadline = performance.now() + 45_000;
  const operationDeadlines = new WeakMap<AbortSignal, number>();
  let phase: 'new' | 'reading' | 'observed' | 'prepared' | 'sent' | 'created' | 'verified' | 'failed' = 'new';
  let created: AlbumCreateResult | undefined;
  async function bounded<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const remaining = Math.min(duration, invocationDeadline - performance.now());
      if (remaining <= 0) return invalid();
      const operationDeadline = performance.now() + remaining;
      operationDeadlines.set(abort.signal, operationDeadline);
      const result = await Promise.race([operation(abort.signal), new Promise<never>((_, reject) => {
        timer = setTimeout(() => { abort.abort(); reject(new AlbumMaterializationTransportError()); }, remaining);
      })]);
      if (performance.now() >= operationDeadline || performance.now() >= invocationDeadline) return invalid();
      return result;
    } catch (error) {
      if (error instanceof AlbumCreateRejected) throw error;
      return invalid();
    } finally { if (timer !== undefined) clearTimeout(timer); abort.abort(); }
  }
  async function request(method: AlbumMaterializationMethod, data: Record<string, string>): Promise<Request> {
    const post = method === 'flickr.photosets.create';
    const signed = deps!.sign(method, { ...data }, post);
    const url = new URL(signed.url);
    if (url.origin !== 'https://www.flickr.com' || url.pathname !== '/services/rest/' || url.username || url.password || url.hash || signed.method !== (post ? 'POST' : 'GET') || signed.redirect !== 'manual') return invalid();
    if (post && (url.search || signed.headers.get('Content-Type') !== 'application/x-www-form-urlencoded')) return invalid();
    const params = post ? new URLSearchParams(await signed.clone().text()) : url.searchParams;
    const expected = { method, format: 'json', nojsoncallback: '1', ...data };
    if ([...params].length !== Object.keys(expected).length || Object.entries(expected).some(([key, value]) => params.getAll(key).length !== 1 || params.get(key) !== value)) return invalid();
    return signed;
  }
  const json = (req: Request, signal: AbortSignal) => readJson(req, (next, lifetime) => {
    if (signal.aborted || performance.now() >= invocationDeadline || performance.now() >= (operationDeadlines.get(signal) ?? 0)) return Promise.reject(new AlbumMaterializationTransportError());
    return deps!.fetcher(next, lifetime);
  }, strictFlickrJson, { signal });
  return {
    async contexts() {
      if (phase !== 'new') return invalid();
      phase = 'reading';
      try {
        const result = await bounded(async signal => {
          await deps!.assertCurrent();
          return albumContextIds(await json(await request('flickr.photos.getAllContexts', { photo_id: identity.photoId }), signal));
        });
        phase = 'observed'; return result;
      } catch (error) { phase = 'failed'; throw error; }
    },
    async prepareCreate() {
      if (phase !== 'observed') return invalid();
      phase = 'prepared';
      let req: Request;
      try {
        req = await bounded(async () => {
          await deps!.assertCurrent();
          return request('flickr.photosets.create', { title: identity.title, primary_photo_id: identity.photoId });
        });
      } catch (error) { phase = 'failed'; throw error; }
      let disposed = false;
      const expiresAt = Math.min(performance.now() + duration, invocationDeadline);
      return {
        handoff() {
          if (phase !== 'prepared') return Promise.reject(new AlbumMaterializationTransportError());
          if (disposed || performance.now() >= expiresAt) { phase = 'failed'; return Promise.reject(new ProvenNotDispatched()); }
          phase = 'sent';
          // Invocation enters the injected HTTP stack synchronously, before yielding.
          const pending = bounded(async signal => albumCreateResult(await json(req, signal)));
          return pending.then(value => { created = value; phase = 'created'; return { ...value }; }, error => { phase = 'failed'; throw error; });
        },
        dispose() { disposed = true; },
      };
    },
    async verify(photosetId) {
      if (phase !== 'created' || !created || photosetId !== created.photosetId) return invalid();
      phase = 'reading';
      try {
        const contextIds = await bounded(async signal => {
          await deps!.assertCurrent();
          verifyInfo(await json(await request('flickr.photosets.getInfo', { photoset_id: photosetId }), signal), photosetId, identity.ownerNsid);
          await deps!.assertCurrent();
          const ids = albumContextIds(await json(await request('flickr.photos.getAllContexts', { photo_id: identity.photoId }), signal));
          if (!ids.includes(photosetId)) return invalid();
          return ids;
        });
        phase = 'verified';
        return { ...created, ownerNsid: identity.ownerNsid, primaryPhotoId: identity.photoId, contextIds };
      } catch (error) { phase = 'failed'; throw error; }
    },
  };
}
