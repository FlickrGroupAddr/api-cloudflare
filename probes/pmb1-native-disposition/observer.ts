// MIT License; copyright 2026 Terry Ott.
// Observation only. No mutation, discovery, drain, close or reopen operation.
import { MAIN_ENTRY_FAMILIES, MainEntryUnavailable, type MainEntryBinding,
  type MainEntryDrainWindow, type MainEntryObserver, type MainEntryStop,
  type MainEntryDisposition } from '../../src/main_entry_maintenance.ts';
import { D1MainEntryJournal, type Pmb1JournalPage } from '../pmb1-native-journal/journal.ts';
import { D1DomainReader, validateDomain, type DomainFacts } from './domain.ts';
import { ReviewedCoverage } from './coverage.ts';

export const DISPOSITION_GAPS = Object.freeze([
  'complete_domain_lifecycle_results_unobserved',
  'native_old_version_callback_population_unobserved',
  'native_pending_body_cancellation_disposition_unobserved',
  'native_population_and_external_custody_unestablished',
] as const);
export type DispositionGap = typeof DISPOSITION_GAPS[number];
export class DispositionUnavailable extends MainEntryUnavailable {
  readonly reason: string;
  constructor(reason: string) { super(); this.reason = reason; }
}
const refuse = (reason: string): never => { throw new DispositionUnavailable(reason); };
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(v);
const integer = (v: unknown): v is string => typeof v === 'string' && /^(0|[1-9][0-9]{0,18})$/.test(v) && BigInt(v) <= 9223372036854775807n;
const bindingValid = (b: MainEntryBinding): boolean => !!b && /^[a-f0-9]{64}$/.test(b.candidate)
  && typeof b.lifecycle === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(b.lifecycle)
  && integer(b.generation) && b.generation !== '0';
const same = (a: MainEntryBinding, b: MainEntryBinding) => bindingValid(a)
  && a.candidate === b.candidate && a.lifecycle === b.lifecycle && a.generation === b.generation;
const outcome = (v: unknown) => v === 'fulfilled' || v === 'rejected';
const kinds = new Set(['d1', 'provider', 'provider-body', 'provider-cancel', 'secret-read', 'wake', 'asset', 'repair-reader']);
const encodedSize = (v: unknown) => new TextEncoder().encode(JSON.stringify(v)).byteLength;

export interface ObservationBounds { pages: number; rows: number; bytes: number; milliseconds: number }
export interface JournalObservation {
  readonly control: Pmb1JournalPage['control'];
  readonly invocations: readonly Readonly<Record<string, unknown>>[];
  readonly effects: readonly Readonly<Record<string, unknown>>[];
  readonly pages: number;
  readonly bytes: number;
  readonly meaning: 'external-journal-only';
  readonly actualQualification: false;
}

/** Collect BOTH complete relations, under one unchanged stopped revision, with
 * an explicit final empty page for each table and a final control reread.
 * This reconciles retained journal obligations only. It does not prove the
 * journal observed every native execution or any required domain safety result.
 * A failed/late read is not retried; late callbacks lose collection authority.
 */
export async function observeJournal(journal: D1MainEntryJournal, binding: MainEntryBinding,
  stop: MainEntryStop, window: MainEntryDrainWindow, bounds: ObservationBounds,
  now: () => number = () => performance.now()): Promise<JournalObservation> {
  const b = Object.freeze({ ...binding }), s = Object.freeze({ ...stop });
  const limits = Object.freeze({ ...bounds }), deadline = window?.deadlineMs;
  if (!(journal instanceof D1MainEntryJournal) || !same(b, journal.binding) || !same(s, b)
    || s.admission !== 'stopped' || !/^[a-f0-9]{64}$/.test(s.evidence)) refuse('journal_binding');
  for (const [name, max] of Object.entries({ pages: 256, rows: 10000, bytes: 4 * 1024 * 1024, milliseconds: 600000 })) {
    const value = limits[name as keyof ObservationBounds];
    if (!Number.isSafeInteger(value) || value < 1 || value > max) refuse('journal_bounds');
  }
  const start = now();
  if (!Number.isFinite(start) || !Number.isFinite(deadline) || deadline <= start
    || deadline - start > limits.milliseconds) refuse('journal_window');
  let previous = start, active = true, pages = 0, rows = 0, bytes = 0;
  let control: Pmb1JournalPage['control'] | undefined;
  const gate = () => {
    const tick = now();
    if (!active || !Number.isFinite(tick) || tick < previous || tick >= deadline) refuse('journal_deadline');
    previous = tick;
  };
  const page = async (table: Pmb1JournalPage['table'], after: string) => {
    gate(); if (++pages > limits.pages) refuse('journal_page_bound');
    // #0243's fixed schema bounds every source field (UUID, binding, enum).
    // Reserve a conservative 1 KiB/row plus 4 KiB control BEFORE its native
    // page materializes, even when a caller asks for a tiny total byte budget.
    if (bytes + 4096 + 128 * 1024 > limits.bytes) refuse('journal_acquisition_bound');
    const value = await journal.page(table, after, 128, { deadlineMs: deadline });
    gate();
    // The native class validates pages; freeze a separate retained copy before
    // yielding again so caller mutation cannot change the reconciled facts.
    const p = structuredClone(value);
    if (p.table !== table || !same(p.control, b) || p.control.database_id !== journal.journalDatabaseId
      || p.control.schema_version !== 'pmb1-main-journal-v1' || p.control.state !== 'stopped'
      || p.control.stop_evidence !== s.evidence || !integer(p.control.revision)
      || !Array.isArray(p.rows) || p.rows.length > 128) refuse('journal_page');
    if (control && JSON.stringify(p.control) !== JSON.stringify(control)) refuse('journal_revision_drift');
    control ??= Object.freeze({ ...p.control });
    bytes += encodedSize(p); rows += p.rows.length;
    if (bytes > limits.bytes || rows > limits.rows) refuse('journal_retained_bound');
    const key = table === 'invocations' ? 'invocation' : 'effect';
    let cursor = after;
    for (const row of p.rows) {
      if (!uuid(row[key]) || row[key] <= cursor) refuse('journal_order');
      cursor = row[key] as string;
      if (table === 'invocations') {
        if (!same(row as unknown as MainEntryBinding, b) || !['fetch', 'scheduled'].includes(String(row.entry))
          || !(row.returned === null || outcome(row.returned))) refuse('journal_invocation');
      } else if (!uuid(row.invocation) || !kinds.has(String(row.kind))
        || !(row.settled === null || outcome(row.settled))) refuse('journal_effect');
    }
    if (p.next !== (p.rows.length === 128 ? cursor : null)) refuse('journal_cursor');
    return p.rows.map(row => Object.freeze({ ...row }));
  };
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([(async () => {
      const complete = async (table: Pmb1JournalPage['table']) => {
        const result: Readonly<Record<string, unknown>>[] = [];
        let after = '';
        for (;;) {
          const current = await page(table, after);
          if (!current.length) return Object.freeze(result);
          result.push(...current);
          after = current[current.length - 1][table === 'invocations' ? 'invocation' : 'effect'] as string;
        }
      };
      const invocations = await complete('invocations'), effects = await complete('effects');
      // This final page must remain empty under the original stopped revision.
      const after = invocations.at(-1)?.invocation as string | undefined;
      if ((await page('invocations', after ?? '')).length) refuse('journal_population_drift');
      const ids = new Set(invocations.map(row => row.invocation));
      for (const row of effects) if (!ids.has(row.invocation)) refuse('journal_orphan_effect');
      if (invocations.some(row => row.returned === null) || effects.some(row => row.settled === null)) refuse('journal_obligation_pending');
      gate();
      return Object.freeze({ control: control!, invocations, effects, pages, bytes,
        meaning: 'external-journal-only' as const, actualQualification: false as const });
    })(), new Promise<never>((_, reject) => {
      timer = setTimeout(() => { active = false; reject(new DispositionUnavailable('journal_deadline')); }, deadline - start);
    })]);
  } catch (error) {
    if (error instanceof DispositionUnavailable) throw error;
    return refuse('journal_read_unknown');
  } finally { active = false; if (timer !== undefined) clearTimeout(timer); }
}

/** Concrete, callable production seam. Complete journal and domain facts plus
 * independently authenticated all-writer/native custody are all mandatory.
 * A missing capability has an explicit NO-GO, without a fallback success path.
 */
export class NativeMainEntryObserver implements MainEntryObserver {
  private readonly journal: D1MainEntryJournal;
  private readonly bounds: ObservationBounds;
  private readonly domain: D1DomainReader | undefined;
  private readonly coverage: ReviewedCoverage | undefined;
  private readonly domainId: string | undefined;
  private evidenceRecord: Readonly<{ journal: JournalObservation; domain: DomainFacts; coverage: unknown }> | undefined;
  constructor(journal: D1MainEntryJournal, bounds: ObservationBounds,
    domain?: D1DomainReader, coverage?: ReviewedCoverage, domainDatabaseId?: string) {
    this.journal = journal;
    this.bounds = Object.freeze({ ...bounds });
    this.domain = domain; this.coverage = coverage; this.domainId = domainDatabaseId;
  }
  async observe(binding: MainEntryBinding, stop: MainEntryStop, window: MainEntryDrainWindow): Promise<JournalObservation> {
    return observeJournal(this.journal, binding, stop, window, this.bounds);
  }
  async assess(binding: MainEntryBinding, stop: MainEntryStop, families: readonly string[], window: MainEntryDrainWindow): Promise<MainEntryDisposition> {
    if (!Array.isArray(families) || JSON.stringify(families) !== JSON.stringify(MAIN_ENTRY_FAMILIES)) refuse('main_family_coverage');
    if (!(this.domain instanceof D1DomainReader) || !(this.coverage instanceof ReviewedCoverage) || !this.domainId) refuse(DISPOSITION_GAPS[0]);
    const domainReader = this.domain!, coverage = this.coverage!, domainId = this.domainId!;
    if (domainReader.databaseId !== domainId) refuse('main_domain_target');
    const frozen = Object.freeze({ ...binding }), deadline = window?.deadlineMs;
    coverage.check(frozen, this.journal.journalDatabaseId, domainId);
    const journal = await this.observe(frozen, stop, { deadlineMs: deadline });
    // Local rejection alone cannot establish a remote outcome or fixed safety
    // result. Conservative refusal remains after restart, even if caught.
    if (journal.invocations.some(r => r.returned !== 'fulfilled')
      || journal.effects.some(r => r.settled !== 'fulfilled')) refuse('main_unknown_outcome');
    const domain = await domainReader.capture(deadline); validateDomain(domain);
    const after = await this.observe(frozen, stop, { deadlineMs: deadline });
    if (JSON.stringify(journal.control) !== JSON.stringify(after.control)
      || JSON.stringify(journal.invocations) !== JSON.stringify(after.invocations)
      || JSON.stringify(journal.effects) !== JSON.stringify(after.effects)) refuse('main_journal_drift');
    coverage.check(frozen, this.journal.journalDatabaseId, domainId);
    const record = Object.freeze({ journal, domain, coverage: coverage.records() });
    const encoded = new TextEncoder().encode(JSON.stringify(record));
    if (encoded.byteLength > this.bounds.bytes) refuse('main_total_evidence_bound');
    const evidence = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', encoded)), b => b.toString(16).padStart(2, '0')).join('');
    if (performance.now() >= deadline) refuse('main_deadline');
    this.evidenceRecord = record;
    return Object.freeze({ ...frozen, status: 'complete-supported', evidence, families: Object.freeze([...MAIN_ENTRY_FAMILIES]),
      admittedHandlers: 'settled', externalResults: 'settled', requiredDomainResults: 'settled', oldCallbacks: 'fenced', restartedInvocations: 'accounted' });
  }
  /** Private evidence custody is the caller's responsibility. Never log this. */
  retainedEvidence() { return this.evidenceRecord; }
}

export { NativePartitionDisposition } from './partition.ts';
