// MIT License; copyright 2026 Terry Ott.
// OPERATOR ONLY. Never import this module into any Worker/ordinary call graph.
import { encoded, sha2_256, same, validateHeader, validateAllocation, EVIDENCE_SQL, executionAnchors } from './ledger.ts';
import { EvidenceUnavailable, type EvidenceHeader, type EvidenceBinding,
  type QualifiedEvidenceProvenance, type EvidenceReadAllocation } from './types.ts';

export interface ReviewedPublicationHandoff {
  header: EvidenceHeader; payloadText: string;
  /** Exact independently retained artifacts, already semantically authenticated
   * by Root and a fresh non-author reviewer. A matching hash proves bytes only. */
  retainedEnvelopeDigest: string;
  retainedRootRecord: string; retainedReviewRecord: string;
}
export interface FixedStatement { sql: string; args: (string | number)[] }
export interface PreparedPublication {
  header: EvidenceHeader; payloadText: string; statements: readonly FixedStatement[];
}
/** Pure finite preparation. No publication authority is created by this result. */
export async function preparePublication(handoff: ReviewedPublicationHandoff, binding: EvidenceBinding,
  provenance: QualifiedEvidenceProvenance, allocation: EvidenceReadAllocation, now: number): Promise<PreparedPublication> {
  validateAllocation(allocation); validateAllocation(handoff?.header?.allocation);
  const input = structuredClone(handoff), header = input.header;
  validateHeader(header, binding, provenance, allocation, now);
  if (typeof input.payloadText !== 'string' || input.payloadText.length !== header.payloadBytes
    || !/^[\x20-\x7e]+$/.test(input.payloadText) || await sha2_256(input.payloadText) !== header.payloadDigest
    || input.retainedEnvelopeDigest !== await sha2_256(encoded(header) + '\n' + input.payloadText)
    || input.retainedRootRecord !== header.provenance.rootRecord || input.retainedReviewRecord !== header.provenance.reviewRecord)
    throw new EvidenceUnavailable('operator_reviewed_artifact_binding');
  let payload: unknown; try { payload = JSON.parse(input.payloadText); } catch { throw new EvidenceUnavailable('operator_payload_json'); }
  if (encoded(payload) !== input.payloadText) throw new EvidenceUnavailable('operator_payload_noncanonical');
  const statements: FixedStatement[] = [{ sql: `INSERT INTO pmb1_evidence_envelopes
    (envelope_id,binding_json,header_json,payload_bytes,chunk_count) VALUES(?,?,?,?,?)`,
    args: [header.reference.envelopeId, encoded(binding), encoded(header), header.payloadBytes, header.chunkCount] }];
  for (let ordinal = 0; ordinal < header.chunkCount; ++ordinal) statements.push({
    sql: 'INSERT INTO pmb1_evidence_chunks(envelope_id,ordinal,payload) VALUES(?,?,?)',
    args: [header.reference.envelopeId, ordinal, input.payloadText.slice(ordinal * 262144, (ordinal + 1) * 262144)] });
  statements.push({ sql: `INSERT INTO pmb1_evidence_events
    (envelope_id,revision,kind,capture_key,attempt_id,outcome,observed_ms) VALUES(?,1,'publish','',?,'',?)`,
    args: [header.reference.envelopeId, header.reference.attemptId, now] });
  if (statements.length > 18 || statements.some(s => s.sql.length > 100000 || s.args.length > 100))
    throw new EvidenceUnavailable('operator_publication_limit');
  return { header, payloadText: input.payloadText, statements };
}

/** Fixed separately allocated independent-primary publication readback plan.
 * A qualified operator executor must run it after the ONE atomic publication
 * batch; timeout/lost ACK stays UNKNOWN and may only read back, never republish.
 * The ordinary Worker reader also validates every exact header/chunk/event.
 */
export function publicationReadback(prepared: PreparedPublication): readonly FixedStatement[] {
  const header = prepared.header, args = [header.reference.envelopeId, encoded(executionAnchors(header.binding))];
  if (!same(header.reference.databaseId, header.binding.databaseId)) throw new EvidenceUnavailable('operator_database_binding');
  return [{ sql: EVIDENCE_SQL.preflight, args }, { sql: EVIDENCE_SQL.header, args },
    { sql: EVIDENCE_SQL.chunks, args: [...args, header.payloadBytes, header.chunkCount] }, { sql: EVIDENCE_SQL.events, args }];
}

/** Operator-only append plan. Retirement is permanent and has no cancellation,
 * callback-death or custody-shortening meaning. This is a plan only; no default
 * retirement execution grant is supplied. Its ACK must never cause a retry.
 */
export function prepareRetirement(header: EvidenceHeader, observedMs: number): FixedStatement {
  if (!Number.isSafeInteger(observedMs) || observedMs < 0) throw new EvidenceUnavailable('operator_retirement_clock');
  return { sql: `INSERT INTO pmb1_evidence_events(envelope_id,revision,kind,capture_key,attempt_id,outcome,observed_ms)
    SELECT e.envelope_id,1+(SELECT MAX(revision) FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id),
      'retire','',?,'',? FROM pmb1_evidence_envelopes e WHERE e.envelope_id=? AND e.binding_json=?
    RETURNING revision,kind,attempt_id,observed_ms`,
    args: [header.reference.attemptId, observedMs, header.reference.envelopeId, encoded(header.binding)] };
}
