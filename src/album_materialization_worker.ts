import type { SqlStore } from './admission.ts';
import {
  claimAlbumMaterialization, currentAlbumMaterialization, markAlbumCreateDispatch,
  finishAlbumMaterialization, failAlbumMaterializationBeforeDispatch,
  unknownAlbumMaterialization, rejectAlbumMaterialization, recordAlbumCreateResult,
  type AlbumMaterializationClaim,
} from './album_materialization_store.ts';
import {
  AlbumCreateRejected,
  type AlbumMaterializationIdentity, type AlbumMaterializationTransport,
} from './album_materialization_transport.ts';

export interface AlbumMaterializationEnv {
  DB: SqlStore;
  FGA_ALBUM_MATERIALIZATION_ENABLED?: string;
}

/** Internal construction seam only. There is deliberately no default network,
 * credential reader, scheduler registration or HTTP entry point. */
export type AlbumMaterializationTransportFactory = (
  identity: AlbumMaterializationIdentity,
  assertCurrent: () => Promise<void>,
) => AlbumMaterializationTransport | Promise<AlbumMaterializationTransport>;

export const ALBUM_MATERIALIZATION_INVOCATION_MS = 45_000;
const CALL_AND_COMMIT_MS = 15_000;
const COMMIT_MS = 5_000;
/** Internal deterministic clock seam; never supplied by HTTP input. */
export interface AlbumMaterializationHooks { monotonicMs?: () => number; }

export type AlbumMaterializationOutcome = 'disabled' | 'no_work' | 'not_dispatched'
  | 'materialized' | 'create_rejected' | 'create_outcome_unknown' | 'service_unavailable';

/** One invocation, one fenced claim, at most one create handoff. The database
 * owns recovery: an abandoned marker is retained as unknown, never reclaimed
 * as permission to create. The exact first pair is completed by reads only. */
export async function consumeAlbumMaterialization(
  env: AlbumMaterializationEnv,
  bindingId: string,
  transportFactory: AlbumMaterializationTransportFactory,
  hooks: AlbumMaterializationHooks = {},
): Promise<AlbumMaterializationOutcome> {
  if (env.FGA_ALBUM_MATERIALIZATION_ENABLED !== '1') return 'disabled';
  const monotonicMs = hooks.monotonicMs ?? (() => performance.now());
  const started = monotonicMs();
  let requiredMs = CALL_AND_COMMIT_MS;
  const remainingMs = (): number => {
    const elapsed = monotonicMs() - started;
    if (!Number.isFinite(elapsed) || elapsed < 0) throw new Error('album_invocation_clock_invalid');
    return ALBUM_MATERIALIZATION_INVOCATION_MS - elapsed;
  };
  const bounded = async <T>(operation: () => Promise<T>): Promise<T> => {
    const remaining = remainingMs();
    if (remaining <= 0) throw new Error('album_invocation_expired');
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const result = await Promise.race([operation(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error('album_invocation_expired')), remaining);
      })]);
      if (remainingMs() <= 0) throw new Error('album_invocation_expired');
      return result;
    } finally { if (timer !== undefined) clearTimeout(timer); }
  };
  let claim: AlbumMaterializationClaim | null;
  try { claim = await bounded(() => claimAlbumMaterialization(env.DB, bindingId)); }
  catch { return 'service_unavailable'; }
  if (!claim) return 'no_work';

  let marked: AlbumMaterializationClaim | null = null;
  let createReturned = false;
  let prepared: Awaited<ReturnType<AlbumMaterializationTransport['prepareCreate']>> | undefined;
  const assertCurrent = async (): Promise<void> => {
    if (remainingMs() <= requiredMs || !await bounded(() => currentAlbumMaterialization(env.DB, marked ?? claim!, requiredMs * 1000)))
      throw new Error('album_claim_changed');
    if (remainingMs() <= requiredMs) throw new Error('album_invocation_expired');
  };
  try {
    await assertCurrent();
    const transport = await bounded(async () => transportFactory({ attemptId: claim!.attemptId, photoId: claim!.photoId,
      ownerNsid: claim!.ownerNsid, title: claim!.desiredTitle }, assertCurrent));
    // This fresh complete read is the sole source for the retained pre-context
    // set. A failed read cannot reach preparation or the dispatch transaction.
    const preContextIds = await bounded(() => transport.contexts());
    await assertCurrent();
    prepared = await bounded(() => transport.prepareCreate());
    // Preparation fixes the exact title/photo before the marker. The marker
    // refuses changed title revisions and every other stale authority fence.
    await assertCurrent();
    marked = await bounded(() => markAlbumCreateDispatch(env.DB, claim!, [...preContextIds]));
    if (!marked) {
      await bounded(() => failAlbumMaterializationBeforeDispatch(env.DB, claim!));
      return 'not_dispatched';
    }
    if (remainingMs() <= CALL_AND_COMMIT_MS) throw new Error('album_invocation_expired');
    const created = await bounded(() => prepared!.handoff());
    createReturned = true;
    requiredMs = COMMIT_MS;
    await assertCurrent();
    if (!await bounded(() => recordAlbumCreateResult(env.DB, marked!, created))) throw new Error('album_result_not_recorded');
    requiredMs = CALL_AND_COMMIT_MS;
    await assertCurrent();
    const proof = await bounded(() => transport.verify(created.photosetId));
    requiredMs = COMMIT_MS;
    await assertCurrent();
    if (!await bounded(() => finishAlbumMaterialization(env.DB, marked!, proof))) throw new Error('album_result_not_committed');
    return 'materialized';
  } catch (error) {
    if (marked) {
      // Only the strict adapter's documented no-create response can reject.
      // Exception types, timeouts and missing durable results are never proof
      // that bytes could not leave; this slice offers no zero-byte replay path.
      if (!createReturned && error instanceof AlbumCreateRejected) {
        try {
          if (await bounded(() => rejectAlbumMaterialization(env.DB, marked!, error.code))) return 'create_rejected';
        } catch { /* Unknown or stale durable rejection cannot authorize replay. */ }
      }
      try { await bounded(() => unknownAlbumMaterialization(env.DB, marked!)); }
      catch { /* The marker survives; database recovery retains unknown. */ }
      return 'create_outcome_unknown';
    }
    try { await bounded(() => failAlbumMaterializationBeforeDispatch(env.DB, claim!)); }
    catch { /* No handoff occurred; an unmarked claim may expire safely. */ }
    return 'not_dispatched';
  } finally {
    // Disposal is local cleanup only and must never affect durable outcome.
    try { prepared?.dispose(); } catch { /* No network or durable retry here. */ }
  }
}
