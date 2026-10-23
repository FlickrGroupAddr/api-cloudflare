// MIT License; copyright 2026 Terry Ott.
// Inert, caller-owned source seam. No Worker, RPC, provider binding or writer.
export const PROFILE = "pmb1-private-application-no-real-v1";
const GUARD_CONTRACT = "adr0065-no-real-sql-guards-v1";
const MIN = -(1n << 63n), MAX = (1n << 63n) - 1n;
export class Refused extends Error { constructor(category: string) { super(category); } }
function need(value: unknown, category: string): asserts value { if (!value) throw new Refused(category); }
type Row = Record<string, unknown>;
export interface Census { schema: Row[]; tableList: Row[]; columns: Record<string, Row[]> }
export interface GuardManifest extends Census {
  profile: string; contractRevision: string; baseSchema: Row[];
  cells: Record<string, string[]>; guards: Row[];
}
export interface ObjectId { namespace: string; id: string }
export interface ExpectedObject extends ObjectId {
  guardManifest: GuardManifest; guardManifestSha256: string;
  // Existing pmb1-object candidate keys; this adds no persisted marker protocol.
  alarmKeys: { invocation: string; sequence: string };
}
export interface Limits {
  objects: number; schema: number; tables: number; columns: number; rows: number;
  kv: number; bytes: number; calls: number; page: number; milliseconds: number;
}
export interface Fence {
  generation: string; state: "closed"; writerEpoch: string; custody: string;
  interval: string; observedAt: string;
}
export interface Writer { id: string; epoch: string; disposition: "retired" | "settled" }
export interface Closure {
  interval: string; start: string; end: string; custody: string;
  writers: Writer[];
}
export interface Page<T> { entries: T[]; next: string | null }
export interface ReadSession {
  // Adapter MUST bound responses/time BEFORE materialization, reject truncation,
  // execute these exact SQL reads, and maintain the caller's all-writer embargo.
  query(sql: string): Promise<unknown>;
  listKV(after: string | null, limit: number): Promise<Page<[string, unknown]>>;
  getAlarm(): Promise<number | null>;
  fence(): Promise<Fence>;
}
export interface SupportedSource {
  // Terminal empty page is mandatory. Enumeration is independently reconciled
  // with expected objects, never used to manufacture its own expected population.
  listObjects(after: string | null, limit: number): Promise<Page<ObjectId>>;
  readObject<T>(id: ObjectId, read: (session: ReadSession) => Promise<T>): Promise<T>;
  closure(): Promise<Closure>;
}
export interface Request {
  profile: typeof PROFILE;
  expectedObjects: ExpectedObject[];
  closure: Closure;
  // Both sets originate in separately reviewed custody, not the observed adapter.
  expectedWriterIds: string[];
  expectedSources: Record<string, string>;
  sourceBytes: Record<string, Uint8Array>;
  fences: Record<string, Omit<Fence, "observedAt">>;
  limits: Limits;
}
export type Cell = ["null", null] | ["integer", string] | ["text", string] | ["blob", string];
export type KVCell = ["null", null] | ["text", string] | ["bigint", string]
  | ["boolean", boolean] | ["number-binary64", string] | ["uint8array", string]
  | ["arraybuffer", string] | ["array", KVCell[]] | ["object", [string, KVCell][]];
interface Table { name: string; columns: string[]; rowid: string | null; keys: number[] }
export interface CapturedTable { columns: string[]; rows: { identity: string | Cell[]; cells: Cell[] }[] }
export interface CapturedObject extends ObjectId {
  census: Census; guardManifestSha256: string; tables: Record<string, CapturedTable>;
  kv: [string, KVCell][];
  alarm: { timeMs: string | null; generation: string; sequence: string;
    dispatch: { id: string; generation: string; alarmGeneration: string } | null };
  before: Fence; after: Fence;
}
export interface Capture {
  profile: typeof PROFILE; actualQualification: false; sources: Record<string, string>;
  closure: Closure; objects: CapturedObject[];
}
const encoder = new TextEncoder();
function text(value: unknown): value is string {
  return typeof value === "string" && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value);
}
function name(value: unknown): value is string { return text(value) && value.length > 0 && value.length <= 4096 && !value.includes("\0"); }
// Match #0237's casefold collision refusals without inventing a second Unicode
// casefold implementation. Non-ASCII SQL identifiers are a supported refusal;
// UTF-8 SQL literals, cell text, KV values and object identities stay supported.
function sqlName(value: unknown): value is string { return name(value) && /^[\x01-\x7f]+$/.test(value); }
function keys(value: unknown, names: string[], category = "invalid_shape"): asserts value is Row {
  need(value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype
    && Reflect.ownKeys(value).every(k => typeof k === "string")
    && Object.keys(value).sort().join("\0") === [...names].sort().join("\0"), category);
}
// Canonical JSON matches fixed_origin_preservation._json: UTF-8, sorted keys,
// no whitespace, finite JSON scalars, no surrogate repair or undefined coercion.
export function canonical(value: unknown): string {
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string") { need(text(value), "invalid_text"); return JSON.stringify(value).replace(/[\u007f-\uffff]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0")); }
  if (typeof value === "number") { need(Number.isSafeInteger(value) && !Object.is(value, -0), "invalid_json_number"); return String(value); }
  if (Array.isArray(value)) {
    need(Reflect.ownKeys(value).length === value.length + 1, "invalid_json_array");
    return "[" + Array.from({ length: value.length }, (_, i) => {
      const d = Object.getOwnPropertyDescriptor(value, String(i));
      need(d !== undefined && d.enumerable && "value" in d, "invalid_json_array"); return canonical(d.value);
    }).join(",") + "]";
  }
  need(value !== null && typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype, "invalid_json");
  need(Reflect.ownKeys(value).every(k => typeof k === "string" && Object.getOwnPropertyDescriptor(value, k)?.enumerable), "invalid_json");
  return "{" + Object.keys(value).sort(compare).map(k => {
    const d = Object.getOwnPropertyDescriptor(value, k)!; need("value" in d, "invalid_json");
    return canonical(k) + ":" + canonical(d.value);
  }).join(",") + "}";
}
// Unicode scalar order, matching Python rather than UTF-16 code-unit order.
function compare(a: string, b: string): number {
  const aa = Array.from(a, c => c.codePointAt(0)!), bb = Array.from(b, c => c.codePointAt(0)!);
  for (let i = 0; i < Math.min(aa.length, bb.length); i++) if (aa[i] !== bb[i]) return aa[i] < bb[i] ? -1 : 1;
  return Math.sign(aa.length - bb.length);
}
function same(a: unknown, b: unknown): boolean { return canonical(a) === canonical(b); }
function schemaCompare(a: Row, b: Row): number {
  for (const k of ["type", "name", "tbl_name"]) { const c = compare(a[k] as string, b[k] as string); if (c !== 0) return c; }
  return 0;
}
export async function sha2_256(bytes: Uint8Array): Promise<string> {
  return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", new Uint8Array(bytes))));
}
function hex(value: Uint8Array): string { return Array.from(value, b => b.toString(16).padStart(2, "0")).join(""); }
function decimal(value: unknown, nonnegative = false): string {
  need(typeof value === "string" && value.length <= 20 && /^(0|[1-9][0-9]*|-[1-9][0-9]*)$/.test(value), "invalid_integer_wire");
  const integer = BigInt(value);
  need(integer.toString() === value, "invalid_integer_wire");
  need(integer >= (nonnegative ? 0n : MIN) && integer <= MAX, "integer_range");
  return integer.toString();
}
function identifier(value: string): string { need(sqlName(value), "unsupported_sql_identifier"); return '"' + value.replaceAll('"', '""') + '"'; }
function objectKey(id: ObjectId): string { need(name(id.namespace) && name(id.id), "invalid_object_identity"); return canonical([id.namespace, id.id]); }
function sortedUnique(values: string[], category: string): void {
  need(values.every((v, i) => i === 0 || compare(values[i - 1], v) < 0), category);
}
function bounded(value: unknown, maximum: number, category: string): asserts value is unknown[] {
  need(Array.isArray(value) && value.length <= maximum, category);
}
function plan(census: Census, limits: Limits): Table[] {
  keys(census, ["schema", "tableList", "columns"]);
  bounded(census.schema, limits.schema, "schema_bound"); bounded(census.tableList, limits.schema, "schema_bound");
  need(census.columns !== null && typeof census.columns === "object" && Object.getPrototypeOf(census.columns) === Object.prototype, "invalid_columns");
  const tableNames: string[] = [], views: string[] = [], identities: string[] = [];
  for (const r of census.schema) {
    keys(r, ["type", "name", "tbl_name", "sql"]);
    need(["table", "index", "view", "trigger"].includes(r.type as string) && sqlName(r.name) && sqlName(r.tbl_name)
      && (r.sql === null || text(r.sql)), "invalid_schema");
    const identity = canonical([r.type, r.name]); need(!identities.includes(identity), "duplicate_schema"); identities.push(identity);
    if (r.type === "table") { need(r.name === r.tbl_name, "table_identity"); tableNames.push(r.name); }
    if (r.type === "view") views.push(r.name);
  }
  need(census.schema.every((r, i) => i === 0 || schemaCompare(census.schema[i - 1], r) < 0), "schema_order"); tableNames.sort(compare);
  need(tableNames.length > 0 && tableNames.length <= limits.tables, "table_bound");
  need(new Set(tableNames.map(n => n.toLowerCase())).size === tableNames.length, "duplicate_casefold_table");
  need(same(Object.keys(census.columns).sort(compare), tableNames), "column_census");
  const storage = new Map<string, Row>();
  for (const r of census.tableList) {
    keys(r, ["schema", "name", "type", "ncol", "wr", "strict"]);
    need(r.schema === "main" && sqlName(r.name) && ["table", "view"].includes(r.type as string)
      && Number.isInteger(r.ncol) && Number(r.ncol) > 0 && Number(r.ncol) <= limits.columns
      && (r.wr === 0 || r.wr === 1) && (r.strict === 0 || r.strict === 1), "unsupported_storage");
    need(!storage.has(r.name), "duplicate_storage"); storage.set(r.name, r);
  }
  sortedUnique(census.tableList.map(r => r.name as string), "storage_order");
  need(same([...storage.keys()].sort(compare), [...tableNames, ...views, "sqlite_schema"].sort(compare)), "storage_census");
  need(storage.get("sqlite_schema")?.type === "table" && views.every(n => storage.get(n)?.type === "view"), "storage_kind");
  return tableNames.map(n => {
    const info = storage.get(n)!; need(info.type === "table", "storage_kind");
    const columns = census.columns[n]; bounded(columns, limits.columns, "column_bound");
    need(columns.length > 0 && columns.length === info.ncol, "column_census");
    const names: string[] = [], primary = new Map<number, number>();
    columns.forEach((c, i) => {
      keys(c, ["cid", "name", "type", "notnull", "dflt_value", "pk", "hidden"]);
      need(c.cid === i && sqlName(c.name) && text(c.type) && (c.notnull === 0 || c.notnull === 1)
        && (c.dflt_value === null || text(c.dflt_value)) && Number.isInteger(c.pk)
        && Number(c.pk) >= 0 && Number(c.pk) <= columns.length && [0, 2, 3].includes(c.hidden as number), "unsupported_column");
      need(!names.some(v => v.toLowerCase() === (c.name as string).toLowerCase()), "duplicate_column"); names.push(c.name);
      if (c.pk !== 0) { need(!primary.has(c.pk as number), "invalid_primary_key"); primary.set(c.pk as number, i); }
    });
    if (info.wr === 0) {
      const alias = ["rowid", "_rowid_", "oid"].find(a => !names.map(v => v.toLowerCase()).includes(a));
      need(alias !== undefined, "hidden_rowid_inaccessible"); return { name: n, columns: names, rowid: alias, keys: [] };
    }
    const positions = [...primary.keys()].sort((a, b) => a - b);
    need(positions.length > 0 && positions.every((p, i) => p === i + 1), "invalid_primary_key");
    return { name: n, columns: names, rowid: null, keys: positions.map(p => primary.get(p)!) };
  });
}
export async function buildGuardManifest(base: Census, limits: Limits): Promise<GuardManifest> {
  const tables = plan(base, limits), guards: Row[] = [], cells: Record<string, string[]> = {};
  const names = new Set(base.schema.map(r => (r.name as string).toLowerCase()));
  for (const r of base.schema) if (r.type === "trigger") {
    // Python #0237 casefold also matches non-ASCII spellings such as long-s in
    // literals/comments. Keep its conservative refusal policy without parsing
    // SQL or implementing Unicode folding; non-trigger SQL remains UTF-8.
    need(text(r.sql) && r.sql.length > 0 && /^[\x00-\x7f]*$/.test(r.sql)
      && !(/raise/i.test(r.sql) && /ignore|fail/i.test(r.sql)), "unsupported_base_trigger");
  }
  for (const t of tables) {
    need(!t.name.toLowerCase().startsWith("sqlite_") && base.schema.some(r => r.type === "table" && r.name === t.name && !!r.sql), "unguardable_table");
    const cover = [...t.columns, ...(t.rowid === null ? [] : [t.rowid])];
    Object.defineProperty(cells, t.name, { value: cover, enumerable: true });
    const suffix = await sha2_256(encoder.encode(t.name));
    for (const event of ["INSERT", "UPDATE"]) {
      const n = "pmb1_no_real_" + suffix + "_" + event.toLowerCase(); need(!names.has(n.toLowerCase()), "guard_name_collision"); names.add(n.toLowerCase());
      const sql = "CREATE TRIGGER " + identifier(n) + " AFTER " + event + " ON " + identifier(t.name)
        + " WHEN " + cover.map(c => "typeof(NEW." + identifier(c) + ")='real'").join(" OR ")
        + " BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END";
      guards.push({ name: n, table: t.name, event, sql });
    }
  }
  const schema = [...base.schema, ...guards.map(g => ({ type: "trigger", name: g.name, tbl_name: g.table, sql: g.sql }))];
  schema.sort(schemaCompare);
  const result = { profile: PROFILE, contractRevision: GUARD_CONTRACT, baseSchema: base.schema,
    schema, tableList: base.tableList, columns: base.columns, cells, guards };
  plan({ schema, tableList: base.tableList, columns: base.columns }, limits); return result;
}
export const ENCODING_SQL = "SELECT hex(CAST('A' AS BLOB)) AS encoding_probe";
export function schemaSQL(limit: number): string { return "SELECT type,name,tbl_name,sql FROM main.sqlite_schema ORDER BY type,name,tbl_name LIMIT " + (limit + 1); }
export function storageSQL(limit: number): string { return 'SELECT schema,name,type,ncol,wr,"strict" FROM pragma_table_list WHERE schema=\'main\' ORDER BY name LIMIT ' + (limit + 1); }
export function columnsSQL(n: string, limit: number): string {
  need(name(n), "invalid_identifier"); return 'SELECT cid,name,type,"notnull",dflt_value,pk,hidden FROM pragma_table_xinfo(\'' + n.replaceAll("'", "''") + "') ORDER BY cid LIMIT " + (limit + 1);
}
function pageSQL(t: Table, offset: number, limit: number): string {
  const expressions = t.rowid === null ? [] : ["CAST(" + identifier(t.rowid) + " AS TEXT) AS row_identity"];
  t.columns.forEach((n, i) => {
    const c = identifier(n);
    expressions.push(`typeof(${c}) AS c${i}_type`, `CASE typeof(${c}) WHEN 'integer' THEN CAST(${c} AS TEXT) WHEN 'text' THEN hex(CAST(${c} AS BLOB)) WHEN 'blob' THEN hex(${c}) ELSE NULL END AS c${i}_value`);
  });
  return "SELECT " + expressions.join(",") + " FROM main." + identifier(t.name) + " ORDER BY "
    + (t.rowid === null ? t.keys.map(k => identifier(t.columns[k]) + " COLLATE BINARY").join(",") : identifier(t.rowid))
    + ` LIMIT ${limit} OFFSET ${offset}`;
}
function decode(tag: unknown, value: unknown): Cell {
  if (tag === "null") { need(value === null, "invalid_null_wire"); return ["null", null]; }
  if (tag === "integer") return ["integer", decimal(value)];
  need(tag !== "real", "actual_real_refused");
  need((tag === "text" || tag === "blob") && typeof value === "string" && /^(?:[0-9A-F]{2})*$/.test(value), "invalid_typed_wire");
  const bytes = Uint8Array.from(value.match(/../g) ?? [], pair => parseInt(pair, 16));
  need(hex(bytes).toUpperCase() === value, "invalid_typed_wire");
  if (tag === "blob") return ["blob", hex(bytes)];
  let decoded: string;
  try { decoded = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes); } catch { throw new Refused("invalid_utf8"); }
  need(hex(encoder.encode(decoded)) === value.toLowerCase(), "invalid_utf8"); return ["text", decoded];
}
function kvCell(value: unknown, node: () => void, ancestors = new Set<object>(), depth = 0): KVCell {
  node(); need(depth <= 16, "kv_depth_bound");
  if (value === null) return ["null", null];
  if (typeof value === "boolean") return ["boolean", value];
  if (typeof value === "string") { need(text(value), "invalid_kv_text"); return ["text", value]; }
  if (typeof value === "bigint") return ["bigint", decimal(value.toString())];
  if (typeof value === "number") {
    need(Number.isFinite(value), "unsupported_kv_number");
    const bytes = new Uint8Array(8); new DataView(bytes.buffer).setFloat64(0, value, false); return ["number-binary64", hex(bytes)];
  }
  if (value !== null && typeof value === "object") {
    need(!ancestors.has(value), "cyclic_or_shared_kv_value"); ancestors.add(value);
  }
  if (value instanceof Uint8Array && Object.getPrototypeOf(value) === Uint8Array.prototype) {
    need(value.buffer instanceof ArrayBuffer && value.byteOffset === 0 && value.byteLength === value.buffer.byteLength
      && !(value.buffer as ArrayBuffer & { resizable?: boolean }).resizable && Reflect.ownKeys(value).length === value.length
      && !ancestors.has(value.buffer), "unsupported_kv_view");
    ancestors.add(value.buffer);
    return ["uint8array", hex(value)];
  }
  if (value instanceof ArrayBuffer && Object.getPrototypeOf(value) === ArrayBuffer.prototype) {
    need(!(value as ArrayBuffer & { resizable?: boolean }).resizable && Reflect.ownKeys(value).length === 0, "unsupported_kv_buffer"); return ["arraybuffer", hex(new Uint8Array(value))];
  }
  if (value !== null && typeof value === "object") {
    // Repeated/shared references need an identity-preserving structured-clone
    // codec, not JSON tree expansion. Conservatively refuse them too.
    const own = Reflect.ownKeys(value);
    if (Array.isArray(value)) {
      need(Object.getPrototypeOf(value) === Array.prototype && own.length === value.length + 1
        && own.every((k, i) => i === value.length ? k === "length" : k === String(i)), "unsupported_kv_array");
      const length = Object.getOwnPropertyDescriptor(value, "length")!;
      need(length.writable && !length.enumerable && !length.configurable, "unsupported_kv_property");
      return ["array", Array.from({ length: value.length }, (_, i) => {
        const d = Object.getOwnPropertyDescriptor(value, String(i))!;
        need(d.enumerable && d.writable && d.configurable && "value" in d, "unsupported_kv_property");
        return kvCell(d.value, node, ancestors, depth + 1);
      })];
    }
    need(Object.getPrototypeOf(value) === Object.prototype && own.every(k => typeof k === "string"), "unsupported_kv_value");
    const entries: [string, KVCell][] = [];
    for (const k of own as string[]) {
      need(text(k), "invalid_kv_text"); const descriptor = Object.getOwnPropertyDescriptor(value, k)!;
      need(descriptor.enumerable && descriptor.writable && descriptor.configurable && "value" in descriptor, "unsupported_kv_property");
      entries.push([k, kvCell(descriptor.value, node, ancestors, depth + 1)]);
    }
    return ["object", entries];
  }
  throw new Refused("unsupported_kv_value");
}
function validateClosure(value: Closure, ids: string[]): void {
  keys(value, ["interval", "start", "end", "custody", "writers"]);
  need(name(value.interval) && name(value.custody), "invalid_closure"); decimal(value.start, true); decimal(value.end, true);
  need(BigInt(value.start) <= BigInt(value.end) && Array.isArray(value.writers), "invalid_interval");
  sortedUnique(ids, "writer_population");
  for (const w of value.writers) { keys(w, ["id", "epoch", "disposition"]); need(name(w.id) && name(w.epoch) && ["retired", "settled"].includes(w.disposition), "writer_unsettled"); }
  need(same(value.writers.map(w => w.id), ids), "writer_population");
}
function validateFence(value: Fence, expected: Omit<Fence, "observedAt">, closure: Closure): void {
  keys(value, ["generation", "state", "writerEpoch", "custody", "interval", "observedAt"]);
  decimal(value.generation, true); decimal(value.observedAt, true);
  const { observedAt, ...binding } = value;
  need(value.state === "closed" && name(value.writerEpoch) && same(binding, expected)
    && value.custody === closure.custody && value.interval === closure.interval
    && BigInt(observedAt) >= BigInt(closure.start) && BigInt(observedAt) <= BigInt(closure.end), "fence_or_interval_drift");
}
// Returns canonical wire values: SQL integer decimal strings are never Numbers.
// Successful capture means complete supported SOURCE observation, not qualification.
export async function capture(source: SupportedSource, incoming: Request): Promise<Capture> {
  try { return await captureBounded(source, incoming); }
  catch (e) { if (e instanceof Refused) throw e; throw new Refused("invalid_input_or_source"); }
}
async function captureBounded(source: SupportedSource, incoming: Request): Promise<Capture> {
  // Caller cannot mutate the approved request during an awaited adapter operation.
  const request = structuredClone(incoming), l = request.limits;
  keys(request, ["profile", "expectedObjects", "closure", "expectedWriterIds", "expectedSources", "sourceBytes", "fences", "limits"]);
  keys(l, ["objects", "schema", "tables", "columns", "rows", "kv", "bytes", "calls", "page", "milliseconds"]);
  const ceilings: Limits = { objects: 128, schema: 2048, tables: 128, columns: 256, rows: 10000, kv: 10000, bytes: 4 * 1024 * 1024, calls: 50000, page: 256, milliseconds: 600000 };
  for (const key of Object.keys(ceilings) as (keyof Limits)[]) need(Number.isSafeInteger(l[key]) && l[key] >= 1 && l[key] <= ceilings[key], "invalid_limits");
  need(request.profile === PROFILE, "explicit_profile_required");
  let calls = 0, bytes = 0, totalRows = 0, totalKV = 0, totalKVNodes = 0, totalSchema = 0, totalTables = 0, totalColumns = 0;
  const deadline = performance.now() + l.milliseconds;
  function charge(value: unknown): void { bytes += encoder.encode(canonical(value)).byteLength; need(bytes <= l.bytes, "aggregate_byte_bound"); }
  async function call<T>(fn: () => Promise<T>): Promise<T> {
    need(++calls <= l.calls, "aggregate_call_bound");
    const remaining = deadline - performance.now(); need(remaining > 0, "elapsed_bound");
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const result = await Promise.race([fn(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Refused("elapsed_bound")), remaining);
      })]);
      need(performance.now() <= deadline, "elapsed_bound"); return result;
    } catch (e) { if (e instanceof Refused) throw e; throw new Refused("source_read_failed"); }
    finally { if (timer !== undefined) clearTimeout(timer); }
  }
  validateClosure(request.closure, request.expectedWriterIds); charge(request.closure);
  const sources = Object.keys(request.expectedSources).sort(compare);
  need(sources.includes("reader.ts") && same(sources, Object.keys(request.sourceBytes).sort(compare)), "source_population");
  for (const n of sources) {
    need(name(n) && /^[a-f0-9]{64}$/.test(request.expectedSources[n]) && request.sourceBytes[n] instanceof Uint8Array, "source_binding");
    bytes += request.sourceBytes[n].byteLength; need(bytes <= l.bytes, "aggregate_byte_bound");
    need(await sha2_256(request.sourceBytes[n]) === request.expectedSources[n], "source_binding");
  }
  bounded(request.expectedObjects, l.objects, "object_bound"); need(request.expectedObjects.length > 0, "empty_population");
  const expectedKeys = request.expectedObjects.map(o => objectKey(o)); sortedUnique(expectedKeys, "object_population_order");
  need(same(Object.keys(request.fences).sort(compare), [...expectedKeys].sort(compare)), "fence_population");
  for (const o of request.expectedObjects) {
    keys(o, ["namespace", "id", "guardManifest", "guardManifestSha256", "alarmKeys"]);
    keys(o.alarmKeys, ["invocation", "sequence"]);
    const order = Object.values(o.alarmKeys); need(order.every(name) && new Set(order).size === 2, "alarm_order_keys");
    keys(o.guardManifest, ["profile", "contractRevision", "baseSchema", "schema", "tableList", "columns", "cells", "guards"]);
    const m = o.guardManifest;
    charge(m);
    need(/^[a-f0-9]{64}$/.test(o.guardManifestSha256) && await sha2_256(encoder.encode(canonical(m))) === o.guardManifestSha256, "manifest_pin");
    const rebuilt = await buildGuardManifest({ schema: m.baseSchema, tableList: m.tableList, columns: m.columns }, l);
    need(same(m, rebuilt), "fixed_guard_definition");
  }
  const closureBefore = await call(() => source.closure()); charge(closureBefore); need(same(closureBefore, request.closure), "closure_drift");
  const observed: ObjectId[] = []; let cursor: string | null = null;
  for (;;) {
    const p = await call(() => source.listObjects(cursor, l.page)); keys(p, ["entries", "next"]); bounded(p.entries, l.page, "object_page_bound"); charge(p);
    for (const id of p.entries) { keys(id, ["namespace", "id"]); const k = objectKey(id); need(cursor === null || compare(cursor, k) < 0, "object_order"); cursor = k; observed.push(id); need(observed.length <= l.objects, "object_bound"); }
    if (p.entries.length === 0) { need(p.next === null, "invalid_terminal_page"); break; }
    need(p.next === cursor, "invalid_object_cursor");
  }
  need(same(observed.map(objectKey), expectedKeys), "incomplete_object_population");
  const objects: CapturedObject[] = [];
  for (const expected of request.expectedObjects) {
    let invocations = 0; let assembled: CapturedObject | undefined;
    const result = await call(() => source.readObject({ namespace: expected.namespace, id: expected.id }, async session => {
      need(++invocations === 1, "read_session_repeated");
      async function query(sql: string): Promise<Row[]> {
        const r = await call(() => session.query(sql)); bounded(r, Math.max(l.schema + 1, l.columns + 1, l.page), "query_response_bound"); charge(r); return r as Row[];
      }
      const fenceExpected = request.fences[objectKey(expected)];
      const before = await call(() => session.fence()); charge(before); validateFence(before, fenceExpected, request.closure);
      const schema = await query(schemaSQL(l.schema)), tableList = await query(storageSQL(l.schema));
      need(same(await query(ENCODING_SQL), [{ encoding_probe: "41" }]), "unsupported_database_encoding");
      const names = schema.filter(r => r.type === "table").map(r => r.name);
      need(names.every(name) && names.length <= l.tables && new Set(names).size === names.length, "table_census");
      const columns: Record<string, Row[]> = {};
      for (const n of (names as string[]).sort(compare)) Object.defineProperty(columns, n, { value: await query(columnsSQL(n, l.columns)), enumerable: true });
      const census = { schema, tableList, columns }, tables = plan(census, l);
      totalSchema += schema.length; totalTables += tables.length; totalColumns += tables.reduce((sum, t) => sum + t.columns.length, 0);
      need(totalSchema <= l.schema && totalTables <= l.tables && totalColumns <= l.columns, "aggregate_census_bound");
      need(same(census, { schema: expected.guardManifest.schema, tableList: expected.guardManifest.tableList, columns: expected.guardManifest.columns }), "schema_or_guard_drift");
      for (const t of tables) {
        const cells = expected.guardManifest.cells[t.name];
        need((await query("SELECT " + cells.map(c => "typeof(" + identifier(c) + ")").join(",") + " FROM main." + identifier(t.name) + " LIMIT 0")).length === 0, "cell_access_unavailable");
      }
      const captured: Record<string, CapturedTable> = {};
      for (const t of tables) {
        const countRows = await query("SELECT CAST(count(*) AS TEXT) AS row_count FROM main." + identifier(t.name));
        need(countRows.length === 1, "invalid_row_count"); keys(countRows[0], ["row_count"]);
        const countBig = BigInt(decimal(countRows[0].row_count, true)); need(countBig <= BigInt(l.rows), "row_bound");
        const count = Number(countBig); totalRows += count; need(totalRows <= l.rows, "aggregate_row_bound");
        const rows: CapturedTable["rows"] = []; let lastRowid: bigint | null = null, lastKey: Cell[] | null = null;
        for (let offset = 0; offset <= count;) {
          const expectedCount = Math.min(l.page, count - offset), page = await query(pageSQL(t, offset, expectedCount === 0 ? 1 : l.page));
          need(page.length === expectedCount, "incomplete_table_page");
          for (const r of page) {
            keys(r, [...t.columns.flatMap((_, i) => [`c${i}_type`, `c${i}_value`]), ...(t.rowid === null ? [] : ["row_identity"])]);
            const cells = t.columns.map((_, i) => decode(r[`c${i}_type`], r[`c${i}_value`]));
            let identity: string | Cell[];
            if (t.rowid !== null) {
              identity = decimal(r.row_identity); const current = BigInt(identity); need(lastRowid === null || lastRowid < current, "row_identity_order"); lastRowid = current;
            } else {
              identity = t.keys.map(k => cells[k]); need(identity.every(c => c[0] !== "null"), "null_primary_key");
              need(lastKey === null || compareKeys(lastKey, identity) < 0, "key_identity_order"); lastKey = identity;
            }
            rows.push({ identity, cells });
          }
          if (expectedCount === 0) break; offset += expectedCount;
        }
        Object.defineProperty(captured, t.name, { value: { columns: t.columns, rows }, enumerable: true });
      }
      const kv: [string, KVCell][] = []; let after: string | null = null;
      for (;;) {
        const p = await call(() => session.listKV(after, l.page)); keys(p, ["entries", "next"]); bounded(p.entries, l.page, "kv_page_bound");
        for (const entry of p.entries) {
          need(Array.isArray(entry) && entry.length === 2 && name(entry[0]), "invalid_kv_entry");
          need(after === null || compare(after, entry[0]) < 0, "kv_order"); after = entry[0];
          const cell = kvCell(entry[1], () => need(++totalKVNodes <= l.kv * 32, "aggregate_kv_node_bound"));
          charge([entry[0], cell]); kv.push([entry[0], cell]); need(++totalKV <= l.kv, "aggregate_kv_bound");
        }
        if (p.entries.length === 0) { need(p.next === null, "invalid_terminal_page"); break; }
        need(p.next === after, "invalid_kv_cursor");
      }
      const alarmValue = await call(() => session.getAlarm());
      need(alarmValue === null || (typeof alarmValue === "number" && Number.isSafeInteger(alarmValue) && alarmValue >= 0 && !Object.is(alarmValue, -0)), "unsupported_alarm");
      const map = new Map(kv), order = expected.alarmKeys, seq = map.get(order.sequence), dispatch = map.get(order.invocation);
      need(seq !== undefined, "missing_alarm_order"); need(seq[0] === "text", "alarm_order_type"); decimal(seq[1], true);
      let invocation: CapturedObject["alarm"]["dispatch"] = null;
      if (alarmValue === null) need(dispatch === undefined, "alarm_order_identity");
      else {
        need(dispatch !== undefined && dispatch[0] === "object", "alarm_order_identity");
        const entries = new Map(dispatch[1]); need(entries.size === 3 && ["id", "generation", "alarmGeneration"].every(k => entries.has(k)), "alarm_order_identity");
        const id = entries.get("id")!, gen = entries.get("generation")!, alarmGen = entries.get("alarmGeneration")!;
        need(id[0] === "text" && name(id[1]) && gen[0] === "text" && alarmGen[0] === "text", "alarm_order_type");
        decimal(gen[1], true); decimal(alarmGen[1], true);
        need(BigInt(gen[1]) > 0n && BigInt(alarmGen[1]) > 0n && gen[1] === before.generation && alarmGen[1] === seq[1], "alarm_order_identity");
        invocation = { id: id[1], generation: gen[1], alarmGeneration: alarmGen[1] };
      }
      const alarm = { timeMs: alarmValue === null ? null : String(alarmValue), generation: before.generation, sequence: seq[1], dispatch: invocation };
      charge(alarm);
      // Exact metadata and terminal rechecks detect observable mid-read drift;
      // mutate-and-revert and a lying adapter still require external qualification.
      need(same(await query(schemaSQL(l.schema)), schema) && same(await query(storageSQL(l.schema)), tableList), "census_drift");
      need(await call(() => session.getAlarm()) === alarmValue, "alarm_drift");
      const afterFence = await call(() => session.fence()); charge(afterFence); validateFence(afterFence, fenceExpected, request.closure);
      need(BigInt(before.observedAt) <= BigInt(afterFence.observedAt), "observation_order");
      assembled = { namespace: expected.namespace, id: expected.id, census, guardManifestSha256: expected.guardManifestSha256,
        tables: captured, kv, alarm, before, after: afterFence };
      return assembled;
    }));
    need(invocations === 1 && result === assembled, "invalid_read_session_result");
    objects.push(result);
  }
  const closureAfter = await call(() => source.closure()); charge(closureAfter); need(same(closureAfter, request.closure), "closure_drift");
  const result: Capture = { profile: PROFILE, actualQualification: false, sources: request.expectedSources, closure: request.closure, objects };
  // Bound the complete canonical artifact as well as cumulative read traffic.
  need(encoder.encode(canonical(result)).byteLength <= l.bytes, "artifact_byte_bound");
  need(performance.now() <= deadline, "elapsed_bound"); return result;
}
function compareKeys(a: Cell[], b: Cell[]): number {
  for (let i = 0; i < a.length; i++) {
    const left = a[i], right = b[i];
    const rank = (c: Cell): number => c[0] === "null" ? 0 : c[0] === "integer" ? 1 : c[0] === "text" ? 2 : 3;
    if (rank(left) !== rank(right)) return rank(left) < rank(right) ? -1 : 1;
    if (left[0] === "integer" && right[0] === "integer") {
      const x = BigInt(left[1]), y = BigInt(right[1]); if (x !== y) return x < y ? -1 : 1;
    } else {
      const x = left[0] === "text" ? hex(encoder.encode(left[1])) : String(left[1]);
      const y = right[0] === "text" ? hex(encoder.encode(right[1])) : String(right[1]);
      if (x !== y) return x < y ? -1 : 1;
    }
  }
  return 0;
}
