import type { SqlStore } from './admission.ts';
import {
  claimAlbumTitle, currentAlbumTitle, beginAlbumTitleRead, markAlbumTitleDispatch,
  recordAlbumTitleResult, reconcileAlbumTitle, releaseAlbumTitle, missingAlbumTitle,
  type AlbumTitleClaim,
} from './album_title_store.ts';
import {
  AlbumTitleMissingError, type AlbumTitleIdentity, type AlbumTitleTransport,
} from './album_title_transport.ts';

export interface AlbumTitleEnv {
  DB: SqlStore;
  FGA_ALBUM_TITLE_SYNC_ENABLED?: string;
}

/** Explicit internal construction only: no network, credential or scheduler default. */
export type AlbumTitleTransportFactory = (
  identity: AlbumTitleIdentity,
  assertCurrent: () => Promise<void>,
  execution: { signal: AbortSignal; remainingMs: () => number },
) => AlbumTitleTransport | Promise<AlbumTitleTransport>;
export interface AlbumTitleHooks { monotonicMs?: () => number; }
export const ALBUM_TITLE_INVOCATION_MS = 10_000;
const CALL_AND_COMMIT_MS = 3_000;
const COMMIT_MS = 1_000;
export type AlbumTitleOutcome = 'disabled' | 'no_work' | 'not_dispatched'
  | 'synced' | 'superseded' | 'retry_pending' | 'conflict' | 'reconciliation_pending'
  | 'needs_attention' | 'local_removed' | 'service_unavailable';

/** One fenced execution. Durable storage owns the three-dispatch/five-read caps,
 * retry deadlines and unresolved-marker ordering; this function never loops or
 * sleeps into a retry. An existing marker is always reconciled before new work. */
export async function consumeAlbumTitle(
  env: AlbumTitleEnv, bindingId: string, transportFactory: AlbumTitleTransportFactory,
  hooks: AlbumTitleHooks = {},
): Promise<AlbumTitleOutcome> {
  if (env.FGA_ALBUM_TITLE_SYNC_ENABLED !== '1') return 'disabled';
  const monotonicMs = hooks.monotonicMs ?? (() => performance.now());
  const started = monotonicMs();
  const remainingMs = (): number => {
    const elapsed = monotonicMs() - started;
    if (!Number.isFinite(elapsed) || elapsed < 0) throw new Error('album_title_clock_invalid');
    return ALBUM_TITLE_INVOCATION_MS - elapsed;
  };
  const bounded = async <T>(operation: () => Promise<T>): Promise<T> => {
    const remaining = remainingMs();
    if (remaining <= 0) throw new Error('album_title_invocation_expired');
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const result = await Promise.race([operation(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error('album_title_invocation_expired')), remaining);
      })]);
      if (remainingMs() <= 0) throw new Error('album_title_invocation_expired');
      return result;
    } finally { if (timer !== undefined) clearTimeout(timer); }
  };
  const executionAbort = new AbortController();
  const executionTimer = setTimeout(() => executionAbort.abort(), ALBUM_TITLE_INVOCATION_MS);
  let claim: AlbumTitleClaim | null;
  try { claim = await bounded(() => claimAlbumTitle(env.DB, bindingId)); }
  catch { clearTimeout(executionTimer); executionAbort.abort(); return 'service_unavailable'; }
  if (!claim) { clearTimeout(executionTimer); executionAbort.abort(); return 'no_work'; }
  let requiredMs = CALL_AND_COMMIT_MS;
  let prepared: Awaited<ReturnType<AlbumTitleTransport['prepareEdit']>> | undefined;
  let executingRead = false;
  const assertCurrent = async (): Promise<void> => {
    if (remainingMs() <= requiredMs || !await bounded(() => currentAlbumTitle(env.DB, claim!, requiredMs * 1000)))
      throw new Error('album_title_claim_changed');
    if (remainingMs() <= requiredMs) throw new Error('album_title_invocation_expired');
  };
  const reconcile = async (proof: Awaited<ReturnType<AlbumTitleTransport['read']>> | null): Promise<AlbumTitleOutcome> => {
    requiredMs = COMMIT_MS;
    await assertCurrent();
    return await bounded(() => reconcileAlbumTitle(env.DB, claim!, proof)) ?? 'reconciliation_pending';
  };
  const read = async (transport: AlbumTitleTransport) => {
    requiredMs = CALL_AND_COMMIT_MS;
    await assertCurrent();
    const next = await bounded(() => beginAlbumTitleRead(env.DB, claim!));
    if (!next) throw new Error('album_title_read_not_admitted');
    claim = next;
    executingRead = true;
    await assertCurrent();
    const proof = await bounded(() => transport.read());
    executingRead = false;
    return proof;
  };
  try {
    await assertCurrent();
    const transport = await bounded(async () => transportFactory({ photosetId: claim!.photosetId,
      ownerNsid: claim!.ownerNsid, title: claim!.desiredTitle }, assertCurrent,
      { signal: executionAbort.signal, remainingMs }));
    const proof = await read(transport);
    if (claim.dispatchCount > 0 || claim.archived || proof.title === claim.desiredTitle)
      return await reconcile(proof);
    // Preparation fixes the body. The marker atomically refuses a changed title,
    // archive or authority snapshot; no subsequent intent mutates this body.
    await assertCurrent();
    prepared = await bounded(() => transport.prepareEdit());
    await assertCurrent();
    const marked = await bounded(() => markAlbumTitleDispatch(env.DB, claim!, proof));
    if (!marked) {
      await bounded(() => releaseAlbumTitle(env.DB, claim!));
      return 'not_dispatched';
    }
    claim = marked;
    // A result body never proves the title. Both success and uncertain handoff
    // take the same fresh observation path, retaining the marker on any failure.
    let result: 'success' | 'uncertain' = 'success';
    try {
      await assertCurrent();
      await bounded(() => prepared!.handoff());
    } catch { result = 'uncertain'; }
    requiredMs = COMMIT_MS;
    await assertCurrent();
    if (!await bounded(() => recordAlbumTitleResult(env.DB, claim!, result)))
      throw new Error('album_title_result_not_recorded');
    return await reconcile(await read(transport));
  } catch (error) {
    if (executingRead && error instanceof AlbumTitleMissingError) {
      try {
        requiredMs = COMMIT_MS;
        await assertCurrent();
        if (await bounded(() => missingAlbumTitle(env.DB, claim!))) return 'needs_attention';
      } catch { /* Retain the attempt and immutable photoset identity. */ }
    } else if (executingRead) {
      try { return await reconcile(null); }
      catch { /* Retained read charge and marker survive uncertain persistence. */ }
    }
    try { await bounded(() => releaseAlbumTitle(env.DB, claim!)); }
    catch { /* Lease recovery cannot erase a marker or refund an execution. */ }
    return claim.dispatchCount > 0 ? 'reconciliation_pending' : 'not_dispatched';
  } finally {
    clearTimeout(executionTimer); executionAbort.abort();
    try { prepared?.dispose(); } catch { /* Local cleanup has no durable effect. */ }
  }
}
