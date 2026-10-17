import type { SqlStore } from './admission.ts';
import { reserveFlickrCapacity, type FlickrCapacityReservation } from './flickr_rate.ts';
import type { FlickrFetch } from './flickr_reads.ts';

export type AlbumAdmittedMethod = 'flickr.photos.getAllContexts' | 'flickr.photosets.getInfo'
  | 'flickr.photosets.addPhoto' | 'flickr.photosets.editMeta';
export interface AlbumFlickrAdmissionDependencies {
  db: SqlStore;
  /** Required innermost network boundary; never wrap this with another rate allocator. */
  fetcher: FlickrFetch;
  /** Exact request/worker authority, including current link, grant, pause and lifecycle. */
  assertCurrent(): Promise<void>;
  /** Inject the existing shared Flickr fault gate; no implicit allow/default policy. */
  assertFaultAllowed(): Promise<void>;
  signal?: AbortSignal;
}
export interface AlbumFlickrAdmission {
  reserveReads(count: number): Promise<void>;
  beforeRequest(method: AlbumAdmittedMethod): Promise<void>;
  fetcher: FlickrFetch;
}
const READS = new Set<AlbumAdmittedMethod>(['flickr.photos.getAllContexts', 'flickr.photosets.getInfo']);
const METHODS = new Set<AlbumAdmittedMethod>([...READS, 'flickr.photosets.addPhoto', 'flickr.photosets.editMeta']);
const unavailable = (): never => { throw new Error('album_flickr_admission_unavailable'); };

/** Explicit dormant composition. Charged private credits grant capacity only.
 * Hooks run before signing; guarded fetch repeats authority after all admission awaits.
 * No allocation/refund/network retry is possible after an ambiguous allocation.
 */
export function createAlbumFlickrAdmission(dependencies: AlbumFlickrAdmissionDependencies): AlbumFlickrAdmission {
  if (!dependencies || !dependencies.db || ![dependencies.fetcher, dependencies.assertCurrent, dependencies.assertFaultAllowed].every(fn => typeof fn === 'function')
      || dependencies.signal !== undefined && !(dependencies.signal instanceof AbortSignal)) return unavailable();
  const deps = Object.freeze({ ...dependencies });
  type Credit = { method: AlbumAdmittedMethod | null; reservation: FlickrCapacityReservation; remaining: number };
  const credits: Credit[] = [];
  let allocating = false, failed = false;
  const checkAbort = (request?: Request) => {
    if (failed || deps.signal?.aborted || request?.signal.aborted) return unavailable();
  };
  async function current(request?: Request) {
    checkAbort(request);
    await deps.assertFaultAllowed();
    await deps.assertCurrent();
    checkAbort(request);
  }
  async function allocate(count: number, method: AlbumAdmittedMethod | null) {
    checkAbort();
    if (allocating) return unavailable();
    allocating = true;
    try {
      await current();
      const reservation = await reserveFlickrCapacity(deps.db, count);
      await current();
      if (!await reservation.check()) return unavailable();
      // The SQL await can change authority: hooks must refuse before signing too.
      await current();
      credits.push({ method, reservation, remaining: count });
    } catch (error) {
      failed = true;
      credits.length = 0;
      throw error;
    } finally { allocating = false; }
  }
  return Object.freeze({
    async reserveReads(count: number) {
      if (!Number.isSafeInteger(count) || count < 1 || count > 21) return unavailable();
      // Each fresh observation discards unused older read capacity without refund.
      for (const credit of credits) if (credit.method === null) credit.remaining = 0;
      await allocate(count, null);
    },
    async beforeRequest(method: AlbumAdmittedMethod) {
      if (!METHODS.has(method)) return unavailable();
      await allocate(1, method);
    },
    async fetcher(request: Request) {
      checkAbort(request);
      if (allocating) return unavailable();
      const url = new URL(request.url);
      if (url.origin !== 'https://www.flickr.com' || url.pathname !== '/services/rest/' || url.username || url.password || url.hash
          || request.redirect !== 'manual' || !['GET', 'POST'].includes(request.method)) return unavailable();
      if (request.method === 'POST' && (url.search || request.headers.get('Content-Type') !== 'application/x-www-form-urlencoded')) return unavailable();
      const parameters = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : url.searchParams;
      const method = parameters.get('method') as AlbumAdmittedMethod;
      if (parameters.getAll('method').length !== 1 || !METHODS.has(method)
          || (READS.has(method) ? request.method !== 'GET' || request.body !== null : request.method !== 'POST')) return unavailable();
      const credit = credits.find(item => item.remaining > 0 && (item.method === method || item.method === null && READS.has(method)));
      if (!credit) return unavailable();
      // Burn before yielding; failure and replay never replenish capacity.
      credit.remaining--;
      if (!await credit.reservation.check()) return unavailable();
      // Last authority await is inside the innermost boundary, after rate admission.
      await deps.assertFaultAllowed();
      await deps.assertCurrent();
      checkAbort(request);
      if (!credit.reservation.unexpired()) return unavailable();
      const signal = deps.signal ? AbortSignal.any([deps.signal, request.signal]) : request.signal;
      if (signal.aborted) return unavailable();
      return deps.fetcher(new Request(request, { signal }));
    },
  });
}

export interface AlbumWorkerFaultGateSnapshot {
  userId: string; deploymentGateRevision: number; userGateRevision: number;
}
/** Worker claims already pin these shared gate revisions. Reader policy remains caller-owned. */
export function createAlbumWorkerFaultGate(db: SqlStore, snapshot: AlbumWorkerFaultGateSnapshot): () => Promise<void> {
  if (!db || !snapshot || typeof snapshot.userId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(snapshot.userId)
      || ![snapshot.deploymentGateRevision, snapshot.userGateRevision].every(value => Number.isSafeInteger(value) && value > 0)) return unavailable();
  const identity = Object.freeze({ ...snapshot });
  return async () => {
    const row = await db.prepare(`SELECT 1 valid FROM flickr_write_gates d JOIN flickr_write_gates u
      ON u.scope='user' AND u.scope_id=? WHERE d.scope='deployment' AND d.scope_id='*'
      AND d.enabled=1 AND u.enabled=1 AND d.revision=? AND u.revision=?`)
      .bind(identity.userId, identity.deploymentGateRevision, identity.userGateRevision).first();
    if (!row) return unavailable();
  };
}
