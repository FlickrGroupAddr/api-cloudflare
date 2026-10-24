// MIT License; copyright 2026 Terry Ott.
// Complete prospective D1 facts through the native D1 binding, no writes.
import applicationPlan from '../pmb1-native-disposition/domain-plan.json' with { type: 'json' };
import { D1DomainReader as LegacyD1DomainReader } from '../pmb1-native-disposition/domain.ts';
import { validateNativeDomainPlan, type QualifiedNativeDomainPlan } from './domain-plan.ts';
import { DispositionUnavailable, type ObservationBounds } from '../pmb1-native-disposition/observer.ts';

export type Cell = readonly ['null', null] | readonly ['integer', string] | readonly ['text', string] | readonly ['blob', string];
export interface DomainFacts {
  readonly schema: readonly Record<string, unknown>[];
  readonly tables: Readonly<Record<string, readonly Readonly<Record<string, Cell>>[]>>;
  readonly actualQualification: false;
}
const fail = (reason: string): never => { throw new DispositionUnavailable(reason); };
const quote = (name: string) => '"' + name.replaceAll('"', '""') + '"';
const canonical = (value: unknown): string => JSON.stringify(value, (_key, item) =>
  item && !Array.isArray(item) && typeof item === 'object' ? Object.fromEntries(Object.keys(item).sort().map(k => [k, item[k]])) : item);
const hex = (value: string) => Uint8Array.from(value.match(/../g) ?? [], b => parseInt(b, 16));
const text = (value: Cell | undefined): string | null => {
  if (!value || value[0] === 'null') return null;
  if (value[0] !== 'text') fail('domain_text_type');
  try { return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(hex(value[1]!)); }
  catch { return fail('domain_invalid_text'); }
};
const integer = (value: Cell | undefined): string | null => {
  if (!value || value[0] === 'null') return null;
  if (value[0] !== 'integer') fail('domain_integer_type'); return value[1];
};
export { text as domainText, integer as domainInteger };
const expr = (column: string) => `json_array(typeof(${quote(column)}),CASE typeof(${quote(column)}) WHEN 'null' THEN NULL WHEN 'integer' THEN CAST(${quote(column)} AS TEXT) WHEN 'text' THEN hex(CAST(${quote(column)} AS BLOB)) WHEN 'blob' THEN hex(${quote(column)}) ELSE 'UNSUPPORTED' END)`;
const schemaSQL = "SELECT json_array(type,name,tbl_name,sql) v FROM main.sqlite_schema ORDER BY type,name,tbl_name";
const tables = Object.entries(applicationPlan.tables).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
const sqlFor = (name: string, spec: { rowid: boolean; columns: string[] }) =>
  `SELECT json_array(${(spec.rowid ? ['rowid', ...spec.columns] : spec.columns).map(expr).join(',')}) v FROM ${quote(name)} LIMIT 10001`;
const payloadBytes = (value: unknown) => new TextEncoder().encode(canonical(value)).byteLength;

/** The whole schema (including excluded provider metadata) and ALL 65 included
 * tables are read. Every stored INTEGER is CAST to exact TEXT at the SQL source;
 * TEXT/BLOB payloads retain source bytes. REAL and unknown types refuse.
 * Fixed preflights reserve data size BEFORE materialization; the separately
 * authenticated all-writer custody interval must already cover these reads.
 * No retry/repair/close/reopen or token/provider access is implemented.
 */
export class NativeD1DomainReader extends LegacyD1DomainReader {
  private readonly nativeBounds: Readonly<ObservationBounds>;
  readonly databaseId: string;
  private readonly nativeControl: Readonly<{ databaseId: string; generation: string; state: 'open' | 'closed' }>;
  constructor(privateDatabase: D1Database, bounds: ObservationBounds,
    control: { databaseId: string; generation: string; state: 'open' | 'closed' }, expectedPlan: QualifiedNativeDomainPlan) {
    super(privateDatabase,bounds,control);
    this.nativePlan=validateNativeDomainPlan(expectedPlan);
    this.nativeDb = privateDatabase; this.nativeBounds = Object.freeze({ ...bounds });
    this.nativeControl = Object.freeze({ ...control }); this.databaseId = control?.databaseId;
    if (!control || typeof control.databaseId !== 'string' || !control.databaseId.length
      || !/^[1-9][0-9]{0,18}$/.test(control.generation) || BigInt(control.generation) > 9223372036854775807n
      || !['open', 'closed'].includes(control.state)) fail('domain_control_binding');
    if (!privateDatabase || typeof privateDatabase.withSession !== 'function') fail('domain_binding');
    for (const [key, max] of Object.entries({ pages: 512, rows: 10000, bytes: 4 * 1024 * 1024, milliseconds: 600000 })) {
      const v = bounds[key as keyof ObservationBounds];
      if (!Number.isSafeInteger(v) || v < 1 || v > max) fail('domain_bounds');
    }
  }
  private readonly nativeDb: D1Database;
  private readonly nativePlan: ReturnType<typeof validateNativeDomainPlan>;
  override async capture(deadlineMs: number): Promise<DomainFacts> {
    const start = performance.now(), limit = this.nativeBounds;
    if (!Number.isFinite(deadlineMs) || deadlineMs <= start || deadlineMs - start > limit.milliseconds) fail('domain_window');
    let active = true, used = 0, retainedRows = 0, calls = 0, previous = start;
    const gate = () => { const now = performance.now();
      if (!active || now < previous || now >= deadlineMs) fail('domain_deadline'); previous = now; };
    const session = this.nativeDb.withSession('first-primary');
    const query = async (sql: string) => {
      gate(); if (++calls > limit.pages) fail('domain_call_bound');
      const result = await session.prepare(sql).all<Record<string, unknown>>(); gate();
      if (result.success !== true || !Array.isArray(result.results)) fail('domain_response_unknown');
      return result.results;
    };
    const acquire = async (sql: string) => {
      const before = await query(`SELECT CAST(count(*) AS TEXT) n,CAST(32+coalesce(sum(2*length(CAST(v AS BLOB))+64),0) AS TEXT) b FROM (${sql})`);
      if (before.length !== 1 || typeof before[0].n !== 'string' || !/^(0|[1-9][0-9]*)$/.test(before[0].n)
        || typeof before[0].b !== 'string' || !/^(0|[1-9][0-9]*)$/.test(before[0].b)) fail('domain_preflight');
      const n = BigInt(before[0].n as string), b = BigInt(before[0].b as string);
      if (n > BigInt(limit.rows - retainedRows) || b > BigInt(limit.bytes - used)) fail('domain_acquisition_bound');
      used += Number(b); retainedRows += Number(n);
      const rows = await query(sql);
      if (rows.length !== Number(n) || payloadBytes(rows) > Number(b)) fail('domain_snapshot_drift');
      return rows.map(row => {
        if (Object.keys(row).join() !== 'v' || typeof row.v !== 'string') fail('domain_result_shape');
        let value: unknown; try { value = JSON.parse(row.v as string); } catch { return fail('domain_result_json'); }
        return value;
      });
    };
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([(async () => {
        const schemaRaw = await acquire(schemaSQL);
        const schema = schemaRaw.map(row => {
          if (!Array.isArray(row) || row.length !== 4 || row.slice(0, 3).some(v => typeof v !== 'string')
            || !(row[3] === null || typeof row[3] === 'string')) fail('domain_schema_shape');
          const value = row as unknown[];
          return Object.freeze({ type: value[0], name: value[1], tbl_name: value[2], sql: value[3] });
        });
        if (canonical(schema) !== canonical(this.nativePlan.schema)) fail('domain_schema_mismatch');
        const facts: Record<string, readonly Readonly<Record<string, Cell>>[]> = {};
        for (const [name, spec] of tables) {
          const columns = spec.rowid ? ['rowid', ...spec.columns] : spec.columns;
          const raw = await acquire(sqlFor(name, spec));
          facts[name] = Object.freeze(raw.map(row => {
            if (!Array.isArray(row) || row.length !== columns.length) fail('domain_columns');
            const record: Record<string, Cell> = {};
            (row as unknown[]).forEach((cell: unknown, i: number) => {
              if (!Array.isArray(cell) || cell.length !== 2) fail('domain_cell');
              const [tag, value] = cell as unknown[];
              if (tag === 'null' ? value !== null : tag === 'integer' ? typeof value !== 'string'
                || !/^(0|[1-9][0-9]*|-[1-9][0-9]*)$/.test(value) || BigInt(value) < -9223372036854775808n || BigInt(value) > 9223372036854775807n
                : !['text', 'blob'].includes(String(tag)) || typeof value !== 'string' || !/^(?:[A-F0-9]{2})*$/.test(value)) fail('domain_cell');
              record[columns[i]] = Object.freeze([tag, value]) as Cell;
            });
            return Object.freeze(record);
          }));
        }
        const after = await acquire(schemaSQL);
        if (canonical(after) !== canonical(schemaRaw)) fail('domain_schema_drift');
        const control = facts.maintenance_control;
        if (control.length !== 1 || integer(control[0].singleton_id) !== '1'
          || integer(control[0].generation) !== this.nativeControl.generation || text(control[0].state) !== this.nativeControl.state) fail('domain_control_drift');
        gate(); return Object.freeze({ schema: Object.freeze(schema), tables: Object.freeze(facts), actualQualification: false as const });
      })(), new Promise<never>((_, reject) => { timer = setTimeout(() => {
        active = false; reject(new DispositionUnavailable('domain_deadline'));
      }, deadlineMs - start); })]);
    } catch (error) { if (error instanceof DispositionUnavailable) throw error; return fail('domain_read_unknown'); }
    finally { active = false; if (timer !== undefined) clearTimeout(timer); }
  }
}

