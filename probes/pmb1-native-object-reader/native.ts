// MIT License; copyright 2026 Terry Ott.
// Local storage bridge only. No Worker, RPC, provider call or closure assertion.
import type { ReadSession, Fence, Page } from '../pmb1-no-real-object-reader/reader.ts';
import { canonical, sha2_256, columnsSQL, PROFILE } from '../pmb1-no-real-object-reader/reader.ts';
import { BOUNDARY, REVISION, type BoundaryManifest } from './object-kv-interface.ts';

export class NativeReadRefused extends Error {}
const fail = (reason: string): never => { throw new NativeReadRefused(reason); };
const bytes = (s: string) => new TextEncoder().encode(s).byteLength;
const quote = (s: string) => '"' + s.replaceAll('"', '""') + '"';
// Capture trusted intrinsic getters once. Binary values may carry hostile own
// accessors shadowing ordinary byteLength/buffer/byteOffset/resizable reads.
const typedArrayPrototype = Object.getPrototypeOf(Uint8Array.prototype);
const typedLength = Object.getOwnPropertyDescriptor(typedArrayPrototype, 'length')!.get!;
const typedBytes = Object.getOwnPropertyDescriptor(typedArrayPrototype, 'byteLength')!.get!;
const typedOffset = Object.getOwnPropertyDescriptor(typedArrayPrototype, 'byteOffset')!.get!;
const typedBuffer = Object.getOwnPropertyDescriptor(typedArrayPrototype, 'buffer')!.get!;
const bufferBytes = Object.getOwnPropertyDescriptor(ArrayBuffer.prototype, 'byteLength')!.get!;
const bufferResizable = Object.getOwnPropertyDescriptor(ArrayBuffer.prototype, 'resizable')?.get;
const scalarOrder = (a: string, b: string) => {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
};
export interface NativeBounds {
  calls: number; rows: number; bytes: number; milliseconds: number;
  // Conservative pre-acquisition reserve for ONE SQLite-backed KV item. This
  // bounds serialized source bytes, not JS heap usage or structured-clone size.
  kvAcquisitionBytes: number;
}
// Conservative size of the original reader's supported typed-KV encoding, without
// constructing that encoding. This is serialized-fact accounting, not JS heap.
function retainedKVSize(key: string, value: unknown, cap: number, check: () => void): number {
  let total = 64, nodes = 0;
  const seen = new Set<object>();
  function add(n: number) { total += n; if (!Number.isSafeInteger(total) || total > cap) fail('native_acquisition_byte_bound'); }
  function string(s: string) {
    add(2);
    for (let i = 0; i < s.length; i++) {
      if ((i & 1023) === 0) check();
      const c = s.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff) {
        const next = s.charCodeAt(++i);
        if (!(next >= 0xdc00 && next <= 0xdfff)) fail('native_kv_value');
        add(12);
      } else {
        if (c >= 0xdc00 && c <= 0xdfff) fail('native_kv_value');
        add(c >= 127 ? 6 : c < 32 ? 6 : c === 34 || c === 92 ? 2 : 1);
      }
    }
  }
  function visit(v: unknown, depth: number) {
    if (++nodes > 320000 || depth > 16) fail('native_kv_work_bound');
    check(); add(64);
    if (v === null || typeof v === 'boolean') return;
    if (typeof v === 'string') { string(v); return; }
    if (typeof v === 'number') { if (!Number.isFinite(v)) fail('native_kv_value'); add(16); return; }
    if (typeof v === 'bigint') {
      if (v < -9223372036854775808n || v > 9223372036854775807n) fail('native_kv_value');
      add(v.toString().length); return;
    }
    if (typeof v !== 'object' || seen.has(v)) fail('native_kv_value');
    seen.add(v as object);
    if (ArrayBuffer.isView(v)) {
      if (Object.getPrototypeOf(v) !== Uint8Array.prototype) fail('native_kv_value');
      const length = typedLength.call(v) as number, own = Reflect.ownKeys(v);
      if (own.length !== length || !own.every((name, i) => name === String(i))) fail('native_kv_value');
      const backing = typedBuffer.call(v) as ArrayBuffer;
      // Reject properties on the backing buffer before reading any buffer
      // fields, including a shadowed resizable accessor. All size/brand reads
      // below use captured intrinsic getters, never ordinary value properties.
      if (Object.getPrototypeOf(backing) !== ArrayBuffer.prototype
        || Reflect.ownKeys(backing).length !== 0 || seen.has(backing)) fail('native_kv_value');
      const lengthBytes = typedBytes.call(v) as number;
      add(lengthBytes * 2);
      if (typedOffset.call(v) !== 0 || lengthBytes !== bufferBytes.call(backing)
        || bufferResizable?.call(backing)) fail('native_kv_value');
      seen.add(backing); return;
    }
    if (v instanceof ArrayBuffer && Object.getPrototypeOf(v) === ArrayBuffer.prototype) {
      if (Reflect.ownKeys(v).length !== 0) fail('native_kv_value');
      add((bufferBytes.call(v) as number) * 2);
      if (bufferResizable?.call(v)) fail('native_kv_value');
      return;
    }
    const keys = Reflect.ownKeys(v as object);
    if (Array.isArray(v)) {
      if (Object.getPrototypeOf(v) !== Array.prototype || keys.length !== v.length + 1
        || !keys.every((k, i) => i === v.length ? k === 'length' : k === String(i))) fail('native_kv_value');
      for (let i = 0; i < v.length; i++) {
        const d = Object.getOwnPropertyDescriptor(v, String(i))!;
        if (!d.enumerable || !d.writable || !d.configurable || !('value' in d)) fail('native_kv_value');
        visit(d.value, depth + 1);
      }
      return;
    }
    if (Object.getPrototypeOf(v) !== Object.prototype || !keys.every(k => typeof k === 'string')) fail('native_kv_value');
    for (const k of keys as string[]) {
      string(k);
      const d = Object.getOwnPropertyDescriptor(v, k)!;
      if (!d.enumerable || !d.writable || !d.configurable || !('value' in d)) fail('native_kv_value');
      visit(d.value, depth + 1);
    }
  }
  string(key); visit(value, 0); return total;
}
export interface LocalCustody {
  generation: string; writerEpoch: string; custody: string; interval: string;
}
export interface BoundaryReadAuthorization {
  manifest: BoundaryManifest;
  manifestSha2_256: string;
  sourceBytes: Record<string, Uint8Array>;
  columns: number;
}
type Storage = Pick<DurableObjectStorage, 'sql' | 'transaction'>;
const FENCE = `SELECT CAST(generation AS TEXT) generation,state,typeof(generation) gt,
  typeof(state) st FROM maintenance_control WHERE singleton_id=1`;
const CONTROL_COUNT = 'SELECT CAST(count(*) AS TEXT) n FROM maintenance_control';

/** The caller must independently establish all-writer closure and possess this
 * object's storage. A transaction is local isolation, not external custody.
 * Exact SQL is frozen before acquisition; unlisted SQL cannot execute. Extra
 * SELECT-only preflights measure source response bytes before materialization.
 * No returned object may be used after the transaction callback has returned.
 */
export async function readLocal<T>(storage: Storage, approvedReads: readonly string[],
  custodyInput: LocalCustody, boundsInput: NativeBounds,
  read: (session: ReadSession) => Promise<T>): Promise<T> {
  return readLocalInternal(storage, approvedReads, custodyInput, boundsInput, read);
}

/** Explicit ADR0066 successor only. Admit one fixed metadata pragma, never raw
 * hidden contents. The same exact manifest and source bytes must be supplied to
 * captureSupportedBoundary; this validates their integrity, not actual custody.
 * readLocal's original/default raw boundary remains unchanged.
 */
export async function readLocalSupportedBoundary<T>(storage: Storage, approvedReads: readonly string[],
  custody: LocalCustody, bounds: NativeBounds, authorization: BoundaryReadAuthorization,
  read: (session: ReadSession) => Promise<T>): Promise<T> {
  const auth = structuredClone(authorization), manifest = auth.manifest;
  if (manifest.boundary !== BOUNDARY || manifest.revision !== REVISION || manifest.profile !== PROFILE
    || canonical(manifest.automatic) !== canonical({ name: '__cf_kv', origin: 'provider-automatic-sqlite-kv', applicationDependsOnRaw: false })
    || !/^[a-f0-9]{64}$/.test(auth.manifestSha2_256)
    || await sha2_256(new TextEncoder().encode(canonical(manifest))) !== auth.manifestSha2_256
    || !Number.isSafeInteger(auth.columns) || auth.columns < 1 || auth.columns > 256
    || !Array.isArray(manifest.observable.columns.__cf_kv)
    || manifest.observable.columns.__cf_kv.length > auth.columns) fail('native_boundary_binding');
  const names = Object.keys(manifest.sourcePins).sort();
  if (!['reader.ts', 'object-kv-interface.ts', 'native.ts', 'ADR0066.md'].every(name => names.includes(name))
    || canonical(names) !== canonical(Object.keys(auth.sourceBytes).sort())) fail('native_boundary_source_binding');
  let sourceSize = 0;
  for (const name of names) {
    const value = auth.sourceBytes[name];
    if (!(value instanceof Uint8Array) || !/^[a-f0-9]{64}$/.test(manifest.sourcePins[name])) fail('native_boundary_source_binding');
    sourceSize += value.byteLength;
    if (sourceSize > bounds.bytes || await sha2_256(value) !== manifest.sourcePins[name]) fail('native_boundary_source_binding');
  }
  return readLocalInternal(storage, approvedReads, custody, bounds, read, columnsSQL('__cf_kv', auth.columns),
    sourceSize + new TextEncoder().encode(canonical(manifest)).byteLength);
}

async function readLocalInternal<T>(storage: Storage, approvedReads: readonly string[],
  custodyInput: LocalCustody, boundsInput: NativeBounds,
  read: (session: ReadSession) => Promise<T>, hiddenMetadataSQL?: string, initialRetainedBytes = 0): Promise<T> {
  const custody = structuredClone(custodyInput), bounds = structuredClone(boundsInput);
  for (const [key, max] of Object.entries({ calls: 50000, rows: 10001, bytes: 4 * 1024 * 1024,
    milliseconds: 600000, kvAcquisitionBytes: 4 * 1024 * 1024 })) {
    const n = bounds[key as keyof NativeBounds];
    if (!Number.isSafeInteger(n) || n < 1 || n > max) fail('invalid_native_bounds');
  }
  // Vendor says 2 MB, use 2 MiB conservatively. Reserve cannot be set smaller
  // from a fixture's observed size; no supported length-only KV read exists.
  if (bounds.kvAcquisitionBytes < 2 * 1024 * 1024) fail('kv_acquisition_reserve');
  if (!/^[1-9][0-9]{0,18}$/.test(custody.generation)
    || BigInt(custody.generation) > 9223372036854775807n
    || [custody.writerEpoch, custody.custody, custody.interval].some(v => typeof v !== 'string' || !v.length || bytes(v) > 4096)) fail('invalid_native_custody');
  const approved = new Set(approvedReads);
  for (const sql of approved) {
    // These are pinned generated read statements, not a SQL sandbox or parser.
    if (!sql.startsWith('SELECT ') || /[;\u0000]|--|\/\*/.test(sql) || bytes(sql) > 100000) fail('unapproved_native_sql');
  }
  if (!Number.isSafeInteger(initialRetainedBytes) || initialRetainedBytes < 0
    || initialRetainedBytes > bounds.bytes) fail('native_acquisition_byte_bound');
  let used = initialRetainedBytes, calls = 0, active = true, entered = 0, failure: NativeReadRefused | undefined;
  const deadline = performance.now() + bounds.milliseconds;
  function gate() {
    if (failure) throw failure;
    if (!active) fail('native_session_expired');
    if (++calls > bounds.calls) fail('native_call_bound');
    if (performance.now() > deadline) fail('native_elapsed_bound');
  }
  async function guarded<V>(fn: () => Promise<V>): Promise<V> {
    try { return await fn(); }
    catch (error) {
      failure = error instanceof NativeReadRefused ? error : new NativeReadRefused('native_read_unknown');
      throw failure;
    }
  }
  function reserve(n: number) {
    if (!Number.isSafeInteger(n) || n < 0 || used + n > bounds.bytes) fail('native_acquisition_byte_bound');
    used += n;
  }
  function query(sql: string): Record<string, unknown>[] {
    gate();
    if (!approved.has(sql) && sql !== FENCE && sql !== CONTROL_COUNT) fail('unapproved_native_sql');
    // Refuse the actual provider table explicitly. Never strip it from census,
    // invent its schema/rowids or read a made-up SQL-visible replacement.
    if (/\b__cf_kv\b/i.test(sql) && sql !== hiddenMetadataSQL) fail('native_internal_sql_unavailable');
    gate();
    const columns = storage.sql.exec('SELECT * FROM (' + sql + ') LIMIT 0').columnNames;
    if (!Array.isArray(columns) || columns.length > 256 || new Set(columns).size !== columns.length
      || columns.some(c => typeof c !== 'string' || bytes(c) > 4096)) fail('native_column_bound');
    // Each returned cell is NULL, a number, TEXT or BLOB. Six times source
    // bytes plus fixed JSON/column overhead bounds canonical UTF-8 encoding.
    // The aggregate is kept entirely inside SQL until one tiny decimal result.
    const rowCost = '32' + columns.map(c => '+32+' + (6 * bytes(c))
      + '+6*coalesce(length(CAST(' + quote(c) + ' AS BLOB)),0)').join('');
    gate();
    const p = storage.sql.exec(`SELECT CAST(count(*) AS TEXT) n,CAST(coalesce(sum(${rowCost}),0) AS TEXT) b FROM (${sql})`).one();
    if (typeof p.n !== 'string' || !/^(0|[1-9][0-9]*)$/.test(p.n)
      || typeof p.b !== 'string' || !/^(0|[1-9][0-9]*)$/.test(p.b)
      || BigInt(p.n) > BigInt(bounds.rows) || BigInt(p.b) > BigInt(bounds.bytes)) fail('native_response_bound');
    reserve(Number(p.b));
    gate();
    const out: Record<string, unknown>[] = [];
    // Exact original read, inside the same native transaction as the preflight.
    for (const row of storage.sql.exec(sql)) {
      if (out.length >= Number(p.n)) fail('native_snapshot_drift');
      for (const value of Object.values(row)) if (typeof value === 'number' && !Number.isSafeInteger(value)) fail('native_lossy_number');
      out.push({ ...row });
    }
    if (out.length !== Number(p.n)) fail('native_snapshot_drift');
    if (performance.now() > deadline) fail('native_elapsed_bound');
    return out;
  }
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([storage.transaction(async tx => {
      // Vendor transaction implementations may rerun a callback. ReadSession's
      // consumer callback must never repeat, including after unknown failures.
      if (++entered !== 1) fail('native_transaction_reentered');
      // The native transaction may begin after our timeout already returned.
      // Expired work cannot newly invoke even a consumer that reads no methods.
      gate();
      const session: ReadSession = {
        query: sql => guarded(async () => query(sql)),
        listKV: (after, limit): Promise<Page<[string, unknown]>> => guarded(async () => {
          gate();
          if (!Number.isSafeInteger(limit) || limit < 1 || limit > 256 || (after !== null && typeof after !== 'string')) fail('native_kv_page_bound');
          // Native list materializes values. Acquire exactly ONE item and
          // reserve the documented maximum BEFORE calling the native API.
          reserve(bounds.kvAcquisitionBytes);
          const page = await tx.list({ ...(after === null ? {} : { startAfter: after }), limit: 1 });
          gate();
          if (!(page instanceof Map) || page.size > 1) fail('native_kv_page_bound');
          const entries: [string, unknown][] = [];
          let retained = 64;
          for (const [key, value] of page) {
            if (typeof key !== 'string' || (after !== null && scalarOrder(after, key) >= 0)) fail('native_kv_order');
            retained += retainedKVSize(key, value, bounds.bytes, () => {
              if (performance.now() > deadline) fail('native_elapsed_bound');
            });
            entries.push([key, value]);
          }
          // The native read has completed. Keep the measured conservative typed
          // fact charge and release the unused in-flight worst-case reservation.
          used -= bounds.kvAcquisitionBytes;
          reserve(retained);
          return { entries, next: entries.length ? entries[0][0] : null };
        }),
        getAlarm: () => guarded(async () => {
          gate(); reserve(32);
          const alarm = await tx.getAlarm(); gate();
          if (alarm !== null && (!Number.isSafeInteger(alarm) || alarm < 0 || Object.is(alarm, -0))) fail('native_alarm_value');
          // Null reports scheduled state only; never handler disposition.
          return alarm;
        }),
        fence: (): Promise<Fence> => guarded(async () => {
          if (query(CONTROL_COUNT)[0]?.n !== '1') fail('native_fence_population');
          const row = query(FENCE);
          if (row.length !== 1 || row[0].gt !== 'integer' || row[0].st !== 'text'
            || row[0].state !== 'closed' || row[0].generation !== custody.generation) fail('native_fence_drift');
          const now = Date.now();
          if (!Number.isSafeInteger(now) || now < 0) fail('native_clock');
          return { ...custody, state: 'closed', observedAt: String(now) };
        }),
      };
      try { gate(); const result = await read(session); gate(); return result; }
      finally { active = false; }
    }), new Promise<never>((_, reject) => {
      timer = setTimeout(() => { active = false; reject(new NativeReadRefused('native_elapsed_bound')); }, bounds.milliseconds);
    })]);
  } catch (error) {
    active = false;
    if (error instanceof NativeReadRefused) throw error;
    return fail('native_read_unknown');
  } finally { active = false; if (timer !== undefined) clearTimeout(timer); }
}
