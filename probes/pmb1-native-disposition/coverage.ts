// MIT License; copyright 2026 Terry Ott.
import type { MainEntryBinding } from '../../src/main_entry_maintenance.ts';
import type { PartitionCapture } from '../../src/partition_maintenance.ts';
import { DispositionUnavailable } from './observer.ts';

export interface WriterFact {
  id: string; version: string; sourceSha2_256: string;
  authority: 'main-journal-fenced' | 'partition-generation-fenced' | 'external-embargo';
  admissionRecord: string; mutationFenceRecord: string;
}
export interface CustodyFact { resource: string; holder: string; fromMs: number; throughMs: number; record: string }
export interface RetiredExecution extends PartitionCapture {
  version: string; instance: string; retirementRecord: string;
  operations: { id: string; kind: 'd1' | 'provider' | 'body' | 'cancellation'; terminalRecord: string }[];
}
export interface CoverageExpectation {
  binding: MainEntryBinding; profile: 'pmb1-private-application-no-real-v1';
  objectBoundary: 'pmb1-private-object-kv-interface-v1';
  d1Operation: 'fixed_update_with_exact_count_positional_v1';
  journalDatabaseId: string; domainDatabaseId: string;
  resources: { id: string; kind: 'd1' | 'object' | 'native-secret' | 'asset' | 'external-journal' }[];
  writers: { id: string; version: string; sourceSha2_256: string; authority: WriterFact['authority'] }[];
}
export interface AuthenticatedCoverage {
  reviewer: string; authenticationRecord: string; censusRecord: string;
  binding: MainEntryBinding; writers: WriterFact[]; custody: CustodyFact[];
  retiredExecutions: RetiredExecution[];
}
const fail = (reason: string): never => { throw new DispositionUnavailable(reason); };
const text = (s: unknown): s is string => typeof s === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$/.test(s);
const pin = (s: unknown): s is string => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);
const gen = (s: unknown): s is string => typeof s === 'string' && /^[1-9][0-9]{0,18}$/.test(s) && BigInt(s) <= 9223372036854775807n;
const stable = (v: unknown) => JSON.stringify(v);
export const freezeEvidence = <T>(v: T): T => {
  if (v && typeof v === 'object') { for (const item of Object.values(v)) freezeEvidence(item); Object.freeze(v); }
  return v;
};

/** TRUSTED PRIMARY/INDEPENDENT REVIEWER boundary, like ReviewedAdmission in the
 * native D1 source. Construct only after authenticating the complete separately
 * retained actual census, source/fence meaning, native terminal records and
 * resource custody. This class verifies binding and record reconciliation; it
 * cannot authenticate facts by hashing them. There is intentionally no JSON,
 * environment, HTTP, packet-owned loader, default, PASS callback or self-review.
 * Synthetic tests construct invented records and qualify no actual native fact.
 */
export class ReviewedCoverage {
  private readonly expected: Readonly<CoverageExpectation>;
  private readonly observed: Readonly<AuthenticatedCoverage>;
  constructor(expectation: CoverageExpectation, authenticated: AuthenticatedCoverage) {
    const e = structuredClone(expectation), a = structuredClone(authenticated);
    if (!e || !a || !text(a.reviewer) || !text(a.authenticationRecord) || !text(a.censusRecord)
      || !pin(e.binding?.candidate) || !text(e.binding.lifecycle) || !gen(e.binding.generation)
      || stable(e.binding) !== stable(a.binding) || e.profile !== 'pmb1-private-application-no-real-v1'
      || e.objectBoundary !== 'pmb1-private-object-kv-interface-v1'
      || e.d1Operation !== 'fixed_update_with_exact_count_positional_v1'
      || !text(e.journalDatabaseId) || !text(e.domainDatabaseId) || e.journalDatabaseId === e.domainDatabaseId
      || !Array.isArray(e.resources) || !e.resources.length || e.resources.length > 256
      || new Set(e.resources.map(r => r.id)).size !== e.resources.length
      || !e.resources.some(r => r.id === e.journalDatabaseId && r.kind === 'external-journal')
      || !e.resources.some(r => r.id === e.domainDatabaseId && r.kind === 'd1')
      || !Array.isArray(e.writers) || !e.writers.length || e.writers.length > 256
      || !Array.isArray(a.writers) || a.writers.length !== e.writers.length
      || new Set(e.writers.map(w => w.id)).size !== e.writers.length
      || new Set(a.writers.map(w => w.id)).size !== a.writers.length) fail('coverage_shape');
    for (const expected of e.writers) {
      const found = a.writers.find(w => w.id === expected.id);
      if (!text(expected.id) || !text(expected.version) || !pin(expected.sourceSha2_256)
        || !['main-journal-fenced', 'partition-generation-fenced', 'external-embargo'].includes(expected.authority)
        || !found || found.version !== expected.version || found.sourceSha2_256 !== expected.sourceSha2_256
        || found.authority !== expected.authority || !text(found.admissionRecord) || !text(found.mutationFenceRecord)) fail('coverage_writer_missing');
    }
    if (!Array.isArray(a.custody) || a.custody.length !== e.resources.length
      || new Set(a.custody.map(c => c.resource)).size !== a.custody.length) fail('coverage_custody_missing');
    for (const resource of e.resources) {
      const c = a.custody.find(c => c.resource === resource.id);
      if (!text(resource.id) || !['d1', 'object', 'native-secret', 'asset', 'external-journal'].includes(resource.kind)
        || !c || !text(c.holder) || !text(c.record) || !Number.isSafeInteger(c.fromMs)
        || !Number.isSafeInteger(c.throughMs) || c.fromMs < 0 || c.throughMs <= c.fromMs
        || c.throughMs - c.fromMs > 600000) fail('coverage_custody_interval');
    }
    if (!Array.isArray(a.retiredExecutions) || a.retiredExecutions.length > 10000
      || new Set(a.retiredExecutions.map(r => r.id)).size !== a.retiredExecutions.length) fail('coverage_retirement_shape');
    for (const r of a.retiredExecutions) {
      if (!text(r.id) || !gen(r.generation) || !['fetch', 'alarm'].includes(r.entry)
        || !text(r.version) || !text(r.instance) || !text(r.retirementRecord)
        || !e.writers.some(w => w.version === r.version && w.authority === 'partition-generation-fenced')
        || !Array.isArray(r.operations) || r.operations.length > 10000
        || new Set(r.operations.map(o => o.id)).size !== r.operations.length
        || r.operations.some(o => !text(o.id) || !['d1', 'provider', 'body', 'cancellation'].includes(o.kind) || !text(o.terminalRecord))) fail('coverage_retirement_shape');
    }
    this.expected = freezeEvidence(e); this.observed = freezeEvidence(a);
  }
  check(binding: MainEntryBinding, journalId: string, domainId: string, nowMs = Date.now()): void {
    if (stable(binding) !== stable(this.expected.binding) || journalId !== this.expected.journalDatabaseId
      || domainId !== this.expected.domainDatabaseId || !Number.isSafeInteger(nowMs)
      || this.observed.custody.some(c => c.fromMs > nowMs || c.throughMs <= nowMs)) fail('coverage_outside_interval');
  }
  retired(capture: Readonly<PartitionCapture>): Readonly<RetiredExecution> {
    const row = this.observed.retiredExecutions.find(r => r.id === capture.id);
    if (!row || row.generation !== capture.generation || row.entry !== capture.entry) return fail('partition_old_execution_unobserved');
    return row;
  }
  records(): Readonly<{ expected: Readonly<CoverageExpectation>; observed: Readonly<AuthenticatedCoverage> }> {
    return Object.freeze({ expected: this.expected, observed: this.observed });
  }
}
