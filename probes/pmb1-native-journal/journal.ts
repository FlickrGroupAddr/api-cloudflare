// MIT License; copyright 2026 Terry Ott.
// Separately owned D1 main-entry journal. Never install this in a compared store.
import { MainEntryUnavailable, type MainEntryBinding, type MainEntryDrainWindow,
  type MainEntryJournal, type MainEntryLease, type MainEntryStop, type MainEffect } from '../../src/main_entry_maintenance.ts';

function unavailable(): never { throw new MainEntryUnavailable(); }
const digest = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(v);
const integer = (v: unknown): v is string => typeof v === 'string' && /^(0|[1-9][0-9]{0,18})$/.test(v) && BigInt(v) <= 9223372036854775807n;
const kinds = new Set<MainEffect>(['d1', 'provider', 'provider-body', 'provider-cancel', 'secret-read', 'wake', 'asset', 'repair-reader']);
const outcome = (v: unknown) => v === 'fulfilled' || v === 'rejected';
function binding(v: MainEntryBinding): boolean {
  return !!v && digest(v.candidate) && typeof v.lifecycle === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(v.lifecycle)
    && integer(v.generation) && v.generation !== '0';
}
function equal(a: MainEntryBinding, b: MainEntryBinding): boolean {
  return binding(a) && a.candidate === b.candidate && a.lifecycle === b.lifecycle && a.generation === b.generation;
}
export interface Pmb1JournalConfiguration {
  binding: MainEntryBinding;
  /** Actual D1 UUID from the separately reviewed resource/binding inventory. */
  journalDatabaseId: string;
  comparedDatabaseIds: readonly string[];
}
export interface Pmb1JournalEnvironment { PMB1_MAIN_JOURNAL: D1Database }
export interface Pmb1JournalPage {
  control: { candidate: string; lifecycle: string; generation: string; database_id: string;
    schema_version: string; state: 'open' | 'stopped'; stop_evidence: string | null; revision: string };
  table: 'invocations' | 'effects';
  rows: readonly Record<string, unknown>[];
  /** null only after an empty/short page; caller must retain finite total bounds. */
  next: string | null;
}

const MATCH = 'candidate=? AND lifecycle=? AND generation=? AND database_id=? AND schema_version=\'pmb1-main-journal-v1\'';
const CONTROL = `SELECT candidate,lifecycle,generation,database_id,schema_version,state,stop_evidence,CAST(revision AS TEXT) AS revision FROM pmb1_journal_control WHERE id=1 AND ${MATCH}`;
export const PMB1_JOURNAL_SQL = Object.freeze({
  admit: `INSERT INTO pmb1_journal_invocations(invocation,candidate,lifecycle,generation,entry) SELECT ?,candidate,lifecycle,generation,? FROM pmb1_journal_control WHERE id=1 AND ${MATCH} AND state='open' RETURNING invocation,entry`,
  effect: `INSERT INTO pmb1_journal_effects(effect,invocation,kind) SELECT ?,invocation,? FROM pmb1_journal_invocations WHERE invocation=? AND entry=? AND candidate=? AND lifecycle=? AND generation=? AND returned IS NULL AND EXISTS(SELECT 1 FROM pmb1_journal_control WHERE id=1 AND ${MATCH}) RETURNING effect,invocation,kind`,
  settled: `UPDATE pmb1_journal_effects SET settled=? WHERE effect=? AND invocation=? AND settled IS NULL AND EXISTS(SELECT 1 FROM pmb1_journal_invocations WHERE invocation=? AND entry=? AND candidate=? AND lifecycle=? AND generation=? AND returned IS NULL) AND EXISTS(SELECT 1 FROM pmb1_journal_control WHERE id=1 AND ${MATCH}) RETURNING effect,invocation,settled`,
  returned: `UPDATE pmb1_journal_invocations SET returned=? WHERE invocation=? AND entry=? AND candidate=? AND lifecycle=? AND generation=? AND returned IS NULL AND NOT EXISTS(SELECT 1 FROM pmb1_journal_effects e WHERE e.invocation=pmb1_journal_invocations.invocation AND e.settled IS NULL) AND EXISTS(SELECT 1 FROM pmb1_journal_control WHERE id=1 AND ${MATCH}) RETURNING invocation,returned`,
  stop: `UPDATE pmb1_journal_control SET state='stopped',stop_evidence=?,revision=revision+1 WHERE id=1 AND ${MATCH} AND state='open'`,
  control: CONTROL,
  invocations: 'SELECT invocation,candidate,lifecycle,generation,entry,returned FROM pmb1_journal_invocations WHERE invocation>? ORDER BY invocation LIMIT ?',
  effects: 'SELECT effect,invocation,kind,settled FROM pmb1_journal_effects WHERE effect>? ORDER BY effect LIMIT ?',
});

/** No retries, recovery initialization, expiry unlock, close, reopen or deletion.
 * Each mutator is one atomic primary statement; stop is one primary transaction.
 * SDK rejection/lost acknowledgement is UNKNOWN, never evidence of rollback.
 */
export class D1MainEntryJournal implements MainEntryJournal {
  readonly binding: Readonly<MainEntryBinding>;
  readonly journalDatabaseId: string;
  private readonly db: D1Database;
  private readonly now: () => number;
  constructor(env: Pmb1JournalEnvironment, config: Pmb1JournalConfiguration, now = () => performance.now()) {
    if (!env?.PMB1_MAIN_JOURNAL || typeof env.PMB1_MAIN_JOURNAL.prepare !== 'function'
      || typeof env.PMB1_MAIN_JOURNAL.batch !== 'function' || typeof env.PMB1_MAIN_JOURNAL.withSession !== 'function'
      || !config || !binding(config.binding) || !uuid(config.journalDatabaseId)
      || !Array.isArray(config.comparedDatabaseIds) || config.comparedDatabaseIds.length < 1
      || config.comparedDatabaseIds.some(id => !uuid(id) || id === config.journalDatabaseId)
      || new Set(config.comparedDatabaseIds).size !== config.comparedDatabaseIds.length) unavailable();
    this.db = env.PMB1_MAIN_JOURNAL; this.binding = Object.freeze({ ...config.binding });
    this.journalDatabaseId = config.journalDatabaseId; this.now = now;
  }
  private args(): string[] { return [this.binding.candidate, this.binding.lifecycle, this.binding.generation, this.journalDatabaseId]; }
  private check(v: MainEntryBinding): void { if (!equal(v, this.binding)) unavailable(); }
  private lease(v: MainEntryLease): void { this.check(v); if (!uuid(v.invocation) || !['fetch', 'scheduled'].includes(v.entry)) unavailable(); }
  private rows(result: D1Result): Record<string, unknown>[] {
    if (!result || result.success !== true || !Array.isArray(result.results)
      || result.results.some(row => !row || typeof row !== 'object' || Array.isArray(row))) unavailable();
    return result.results as Record<string, unknown>[];
  }
  private async one(sql: string, args: (string | number)[]): Promise<Record<string, unknown> | null> {
    const rows = this.rows(await this.db.prepare(sql).bind(...args).all());
    if (rows.length > 1) unavailable();
    return rows[0] ?? null;
  }
  async admit(v: MainEntryBinding, invocation: string, entry: MainEntryLease['entry']): Promise<MainEntryLease | null> {
    this.check(v); if (!uuid(invocation) || !['fetch', 'scheduled'].includes(entry)) unavailable();
    const row = await this.one(PMB1_JOURNAL_SQL.admit, [invocation, entry, ...this.args()]);
    if (!row) return null;
    if (row.invocation !== invocation || row.entry !== entry) unavailable();
    return Object.freeze({ ...this.binding, invocation, entry });
  }
  async effect(v: MainEntryLease, effect: string, kind: MainEffect): Promise<boolean> {
    this.lease(v); if (!uuid(effect) || !kinds.has(kind)) unavailable();
    const row = await this.one(PMB1_JOURNAL_SQL.effect, [effect, kind, v.invocation, v.entry, v.candidate, v.lifecycle, v.generation, ...this.args()]);
    if (!row) return false;
    if (row.effect !== effect || row.invocation !== v.invocation || row.kind !== kind) unavailable();
    return true;
  }
  async settled(v: MainEntryLease, effect: string, result: 'fulfilled' | 'rejected'): Promise<void> {
    this.lease(v); if (!uuid(effect) || !outcome(result)) unavailable();
    const row = await this.one(PMB1_JOURNAL_SQL.settled, [result, effect, v.invocation, v.invocation, v.entry, v.candidate, v.lifecycle, v.generation, ...this.args()]);
    if (!row || row.effect !== effect || row.invocation !== v.invocation || row.settled !== result) unavailable();
  }
  async returned(v: MainEntryLease, result: 'fulfilled' | 'rejected'): Promise<void> {
    this.lease(v); if (!outcome(result)) unavailable();
    const row = await this.one(PMB1_JOURNAL_SQL.returned, [result, v.invocation, v.entry, v.candidate, v.lifecycle, v.generation, ...this.args()]);
    if (!row || row.invocation !== v.invocation || row.returned !== result) unavailable();
  }
  private time(window: MainEntryDrainWindow, previous?: number): number {
    const time = this.now();
    if (!window || !Number.isFinite(window.deadlineMs) || !Number.isFinite(time)
      || time >= window.deadlineMs || (previous !== undefined && time < previous)) unavailable();
    return time;
  }
  private control(rows: Record<string, unknown>[]): Pmb1JournalPage['control'] {
    const row = rows[0];
    if (rows.length !== 1 || !row || !equal(row as unknown as MainEntryBinding, this.binding)
      || row.database_id !== this.journalDatabaseId || row.schema_version !== 'pmb1-main-journal-v1'
      || !integer(row.revision) || !['open', 'stopped'].includes(String(row.state))
      || (row.state === 'open' ? row.stop_evidence !== null : !digest(row.stop_evidence))) unavailable();
    return Object.freeze({ ...row }) as Pmb1JournalPage['control'];
  }
  async stop(v: MainEntryBinding, window: MainEntryDrainWindow): Promise<MainEntryStop> {
    window = Object.freeze({ deadlineMs: window?.deadlineMs });
    this.check(v); let before = this.time(window);
    const bytes = new TextEncoder().encode(JSON.stringify([this.binding, this.journalDatabaseId, crypto.randomUUID()]));
    const evidence = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
    before = this.time(window, before);
    const results = await this.db.batch([
      this.db.prepare(PMB1_JOURNAL_SQL.stop).bind(evidence, ...this.args()),
      this.db.prepare(CONTROL).bind(...this.args()),
    ]);
    this.time(window, before);
    if (!Array.isArray(results) || results.length !== 2) unavailable();
    this.rows(results[0]); const control = this.control(this.rows(results[1]));
    if (control.state !== 'stopped' || !digest(control.stop_evidence)) unavailable();
    return Object.freeze({ ...this.binding, admission: 'stopped', evidence: control.stop_evidence });
  }
  /** Observation substrate, NOT independent disposition. Restart consumers must
   * enumerate both complete tables under unchanged revision and fixed total caps.
   * Every page starts on primary; batch makes control + rows one SQL transaction.
   */
  async page(table: Pmb1JournalPage['table'], after: string, limit: number, window: MainEntryDrainWindow): Promise<Pmb1JournalPage> {
    window = Object.freeze({ deadlineMs: window?.deadlineMs });
    if (!['invocations', 'effects'].includes(table) || (after !== '' && !uuid(after))
      || !Number.isSafeInteger(limit) || limit < 1 || limit > 256) unavailable();
    const before = this.time(window);
    const session = this.db.withSession('first-primary');
    const results = await session.batch([session.prepare(CONTROL).bind(...this.args()),
      session.prepare(PMB1_JOURNAL_SQL[table]).bind(after, limit)]);
    this.time(window, before);
    if (!Array.isArray(results) || results.length !== 2) unavailable();
    const control = this.control(this.rows(results[0])), rows = this.rows(results[1]);
    if (rows.length > limit) unavailable();
    const key = table === 'invocations' ? 'invocation' : 'effect';
    let previous = after;
    for (const row of rows) {
      const id = row[key]; if (!uuid(id) || id <= previous) unavailable(); previous = id;
      if (table === 'invocations') {
        if (!equal(row as unknown as MainEntryBinding, this.binding) || !['fetch', 'scheduled'].includes(String(row.entry))
          || !(row.returned === null || outcome(row.returned))) unavailable();
      } else if (!uuid(row.invocation) || !kinds.has(row.kind as MainEffect) || !(row.settled === null || outcome(row.settled))) unavailable();
    }
    return Object.freeze({ control, table, rows: Object.freeze(rows.map(row => Object.freeze({ ...row }))), next: rows.length === limit ? previous : null });
  }
}
