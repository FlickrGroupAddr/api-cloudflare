// MIT License; copyright 2026 Terry Ott.
// This source contract supplies no actual qualification or operator authority.
export interface EvidenceReference {
  databaseId: string; envelopeId: string; attemptId: string; operation: string;
}
export interface EvidenceBinding {
  contract: 'pmb1-runtime-evidence-v1'; profile: string; boundary: string; schema: string;
  databaseId: string; sourceContext: string; lifecycle: string; generation: string;
  moduleDigest: string; configurationDigest: string; resourceInventoryDigest: string;
  immutableVersion: string; nativeSourceDigest: string; ownerSourceDigest: string;
  controlReference: string;
}
/** Lifecycle/generation are read from the existing qualified journal control,
 * never renewed by editing a packet or compiled evidence constants. */
export type EvidenceExecutionAnchors = Omit<EvidenceBinding, 'lifecycle' | 'generation'>;
export interface NativeExecutionSelector {
  databaseId: string; sourceContext: string; immutableVersion: string;
}
/** Reviewed source anchors known before the retained Worker version exists.
 * These identify an already qualified publication/getter/containment path;
 * protected rows cannot supply or enable that qualification themselves. */
export interface StableChannelQualification {
  databaseId: string; schema: string; publisherSourceDigest: string;
  provenancePathDigest: string; holderPolicyDigest: string; nativeGetterQualificationRecord: string;
}
/** Facts must already have genuine Root + fresh non-author semantic authentication.
 * Record labels and digests identify that external work; they do not perform it.
 * Construct only in independently reviewed source composition, never from a
 * request, environment packet or the evidence database being authenticated.
 */
export interface QualifiedEvidenceProvenance {
  binding: EvidenceExecutionAnchors;
  publisherSourceDigest: string; holderInventoryDigest: string; writerInventoryDigest: string;
  executionAttributionRecord: string; historyContinuityRecord: string;
  operatorAttemptLedgerRecord: string;
  provenancePathDigest: string; holderPolicyDigest: string; nativeGetterQualificationRecord: string;
}
export interface EvidencePublicationReview extends QualifiedEvidenceProvenance {
  reviewRecord: string; rootRecord: string; reviewer: string; author: string;
  fromMs: number; throughMs: number;
}
export interface EvidenceReadAllocation {
  maxPayloadBytes: number; maxAcquiredBytes: number; maxDecodedBytes: number;
  maxNativeBytes: number; maxAggregateBytes: number;
  /** Exactly allocated protocol charges, not a claim about VM heap accounting. */
  maxRequests: number; maxStatements: number;
  maxTotalRequests: number; maxTotalStatements: number;
}
export interface EvidenceHeader {
  mode: 'raw-capture' | 'evidence-use';
  reference: EvidenceReference; binding: EvidenceBinding;
  provenance: EvidencePublicationReview; allocation: EvidenceReadAllocation;
  fromMs: number; throughMs: number; payloadDigest: string; payloadBytes: number;
  chunkCount: number; captureKeys: readonly string[];
  captureAttempts: readonly { captureKey: string; attemptId: string }[];
}
export interface RuntimeEvidencePacket {
  readonly reference: EvidenceReference; readonly header: EvidenceHeader;
  readonly payload: unknown; readonly revision: number;
}
export type TerminalOutcome = 'complete' | 'refused' | 'unknown';
export class EvidenceUnavailable extends Error {
  readonly reason: string;
  constructor(reason = 'runtime_evidence_unavailable') { super(reason); this.reason = reason; }
}
