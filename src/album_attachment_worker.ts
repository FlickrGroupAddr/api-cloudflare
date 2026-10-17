import type { SqlStore } from './admission.ts';
import {
  claimAlbumAttachment, currentAlbumAttachment, markAlbumAttachmentDispatch,
  finishAlbumAttachment, unknownAlbumAttachment, deferAlbumAttachment,
  failAlbumAttachmentBeforeDispatch, attentionAlbumAttachment,
  recordAlbumAttachmentResult,
  type AlbumAttachmentClaim,
} from './album_attachment_store.ts';
import {
  AlbumAttachmentNeedsAttention,
  type AlbumAttachmentIdentity, type AlbumAttachmentTransport,
} from './album_attachment_transport.ts';

export interface AlbumAttachmentEnv { DB: SqlStore; FGA_ALBUM_ATTACHMENT_ENABLED?: string; }
/** Internal composition only: no default provider, credentials, scheduler or HTTP entry. */
export type AlbumAttachmentTransportFactory = (
  identity: AlbumAttachmentIdentity, assertCurrent: () => Promise<void>,
) => AlbumAttachmentTransport | Promise<AlbumAttachmentTransport>;
export interface AlbumAttachmentHooks { monotonicMs?: () => number; }
export const ALBUM_ATTACHMENT_INVOCATION_MS = 45_000;
const CALL_AND_COMMIT_MS = 15_000;
const COMMIT_MS = 5_000;
const MAX_DISPATCH_ATTEMPTS = 8;
export type AlbumAttachmentOutcome = 'disabled' | 'no_work' | 'not_dispatched'
  | 'membership_verified' | 'membership_reconciliation_pending' | 'retry_scheduled'
  | 'album_attachment_needs_attention' | 'service_unavailable';

/** One durable lease and at most one marked add per invocation. A prior ambiguous
 * marker is read-only: absence schedules a later bounded attempt, never a replay
 * in this pass. All identifiers originate in the hosted claim, not HTTP input. */
export async function consumeAlbumAttachment(
  env: AlbumAttachmentEnv, obligationId: string,
  transportFactory: AlbumAttachmentTransportFactory,
  hooks: AlbumAttachmentHooks = {},
): Promise<AlbumAttachmentOutcome> {
  if (env.FGA_ALBUM_ATTACHMENT_ENABLED !== '1') return 'disabled';
  const monotonicMs = hooks.monotonicMs ?? (() => performance.now());
  const started = monotonicMs();
  const remainingMs = (): number => {
    const elapsed = monotonicMs() - started;
    if (!Number.isFinite(elapsed) || elapsed < 0) throw new Error('album_invocation_clock_invalid');
    return ALBUM_ATTACHMENT_INVOCATION_MS - elapsed;
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
  let claim: AlbumAttachmentClaim | null;
  try { claim = await bounded(() => claimAlbumAttachment(env.DB, obligationId)); }
  catch { return 'service_unavailable'; }
  if (!claim) return 'no_work';

  let marked: AlbumAttachmentClaim | null = null;
  let requiredMs = CALL_AND_COMMIT_MS;
  let prepared: Awaited<ReturnType<AlbumAttachmentTransport['prepareAdd']>> | undefined;
  const assertCurrent = async (): Promise<void> => {
    if (remainingMs() <= requiredMs || !await bounded(() => currentAlbumAttachment(env.DB, marked ?? claim!, requiredMs * 1000)))
      throw new Error('album_claim_changed');
    if (remainingMs() <= requiredMs) throw new Error('album_invocation_expired');
  };
  const completeRead = async (transport: AlbumAttachmentTransport): Promise<AlbumAttachmentOutcome> => {
    requiredMs = CALL_AND_COMMIT_MS;
    await assertCurrent();
    const proof = await bounded(() => transport.read());
    requiredMs = COMMIT_MS;
    await assertCurrent();
    if (proof.contextIds.includes(claim!.photosetId)) {
      if (!await bounded(() => finishAlbumAttachment(env.DB, marked ?? claim!, proof))) throw new Error('album_membership_not_committed');
      return 'membership_verified';
    }
    if ((marked ?? claim!).archivedAfterFulfillment) {
      if (!await bounded(() => attentionAlbumAttachment(env.DB, marked ?? claim!, 'archived_drift_unresolved', proof)))
        throw new Error('album_archived_drift_not_committed');
      return 'album_attachment_needs_attention';
    }
    if ((marked ?? claim!).dispatchAttempts >= MAX_DISPATCH_ATTEMPTS) {
      if (!await bounded(() => attentionAlbumAttachment(env.DB, marked ?? claim!, 'retry_exhausted', proof)))
        throw new Error('album_exhaustion_not_committed');
      return 'album_attachment_needs_attention';
    }
    if (!await bounded(() => deferAlbumAttachment(env.DB, marked ?? claim!, proof))) throw new Error('album_retry_not_committed');
    return 'retry_scheduled';
  };
  try {
    await assertCurrent();
    const transport = await bounded(async () => transportFactory({
      attemptId: claim!.attemptId, photosetId: claim!.photosetId,
      photoId: claim!.photoId, primaryPhotoId: claim!.primaryPhotoId, ownerNsid: claim!.ownerNsid,
    }, assertCurrent));
    await assertCurrent();
    const proof = await bounded(() => transport.read());
    requiredMs = COMMIT_MS;
    await assertCurrent();
    if (proof.contextIds.includes(claim.photosetId)) {
      if (!await bounded(() => finishAlbumAttachment(env.DB, claim!, proof))) throw new Error('album_membership_not_committed');
      return 'membership_verified';
    }
    if (claim.archivedAfterFulfillment) {
      if (!await bounded(() => attentionAlbumAttachment(env.DB, claim!, 'archived_drift_unresolved', proof)))
        throw new Error('album_archived_drift_not_committed');
      return 'album_attachment_needs_attention';
    }
    if (claim.dispatchAttempts >= MAX_DISPATCH_ATTEMPTS) {
      if (!await bounded(() => attentionAlbumAttachment(env.DB, claim!, 'retry_exhausted', proof)))
        throw new Error('album_exhaustion_not_committed');
      return 'album_attachment_needs_attention';
    }
    if (claim.reconciliationOnly) {
      if (!await bounded(() => deferAlbumAttachment(env.DB, claim!, proof))) throw new Error('album_retry_not_committed');
      return 'retry_scheduled';
    }

    requiredMs = CALL_AND_COMMIT_MS;
    await assertCurrent();
    prepared = await bounded(() => transport.prepareAdd());
    await assertCurrent();
    marked = await bounded(() => markAlbumAttachmentDispatch(env.DB, claim!, proof.contextIds));
    if (!marked) throw new Error('album_dispatch_not_marked');
    // Revalidate after the marker as well as before it. A failed current check
    // leaves a conservative marker for read-only recovery and sends no write.
    await assertCurrent();
    let addResult: Awaited<ReturnType<NonNullable<typeof prepared>['handoff']>> | undefined;
    try { addResult = await bounded(() => prepared!.handoff()); }
    catch {
      // Exceptions, code classes and timeout are never absence/zero-byte proof.
      // The only permitted next provider operation is another complete read.
    }
    if (addResult !== undefined) {
      requiredMs = COMMIT_MS;
      await assertCurrent();
      if (!await bounded(() => recordAlbumAttachmentResult(env.DB, marked!, addResult!)))
        throw new Error('album_add_result_not_recorded');
    }
    return await completeRead(transport);
  } catch (error) {
    if (error instanceof AlbumAttachmentNeedsAttention) {
      try {
        if (await bounded(() => attentionAlbumAttachment(env.DB, marked ?? claim!, error.reason)))
          return 'album_attachment_needs_attention';
      } catch { /* Stale/failed attention cannot replace retained evidence. */ }
    }
    if (marked || claim.reconciliationOnly) {
      try { await bounded(() => unknownAlbumAttachment(env.DB, marked ?? claim!)); }
      catch { /* Lease takeover retains the marker and read-only recovery. */ }
      return 'membership_reconciliation_pending';
    }
    try { await bounded(() => failAlbumAttachmentBeforeDispatch(env.DB, claim!)); }
    catch { /* Unmarked lease expiry can be recovered without a provider write. */ }
    return 'not_dispatched';
  } finally {
    try { prepared?.dispose(); } catch { /* Local cleanup is not durable evidence. */ }
  }
}
