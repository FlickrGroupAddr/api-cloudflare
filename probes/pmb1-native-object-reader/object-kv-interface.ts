// MIT License; copyright 2026 Terry Ott.
// Explicit ADR0066 source successor. No native transport or qualification claim.
import { capture as captureApplication, canonical, columnsSQL, schemaSQL, storageSQL,
  sha2_256, PROFILE, type Census, type GuardManifest, type ObjectId, type Request,
  type SupportedSource, type CapturedObject, type Capture, type Limits,
  type ReadSession } from '../pmb1-no-real-object-reader/reader.ts';

export const BOUNDARY = 'pmb1-private-object-kv-interface-v1';
export const REVISION = 'adr0066-object-kv-interface-source-v1';
const AUTOMATIC = '__cf_kv';
const encoder = new TextEncoder();
type Row = Record<string, unknown>;
export class BoundaryRefused extends Error {}
const need = (ok: unknown, reason: string): void => { if (!ok) throw new BoundaryRefused(reason); };
const equal = (a: unknown, b: unknown) => canonical(a) === canonical(b);
const size = (a: unknown) => encoder.encode(canonical(a)).byteLength;
const exactKeys = (value: unknown, keys: string[]) => {
  need(value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype
    && Reflect.ownKeys(value).every(k => typeof k === 'string')
    && equal(Object.keys(value as Row).sort(), keys.sort()), 'boundary_shape');
};

export interface BoundaryManifest {
  boundary: typeof BOUNDARY;
  revision: typeof REVISION;
  profile: typeof PROFILE;
  object: ObjectId;
  automatic: { name: '__cf_kv'; origin: 'provider-automatic-sqlite-kv'; applicationDependsOnRaw: false };
  // Full independently retained observable metadata, including automatic table.
  observable: Census;
  // Only application SQL is subjected to the original all-cell guard contract.
  application: GuardManifest;
  sourcePins: Record<string, string>;
}
export interface BoundaryExpectedObject extends ObjectId {
  manifest: BoundaryManifest;
  manifestSha2_256: string;
  alarmKeys: { invocation: string; sequence: string };
}
export interface BoundaryRequest extends Omit<Request, 'expectedObjects'> {
  boundary: typeof BOUNDARY;
  expectedObjects: BoundaryExpectedObject[];
}
export interface BoundaryObject extends Omit<CapturedObject, 'census' | 'guardManifestSha256'> {
  manifestSha2_256: string;
  observable: { before: Census; after: Census };
  applicationCensus: Census;
  excluded: { name: '__cf_kv'; rawSqlContents: 'unobserved-unfrozen-unverified'; rowids: 'unobserved-unfrozen-unverified' };
}
export interface BoundaryCapture extends Omit<Capture, 'objects'> {
  boundary: typeof BOUNDARY;
  revision: typeof REVISION;
  objects: BoundaryObject[];
}

function project(manifest: BoundaryManifest, limits: Limits): Census {
  const full = manifest.observable;
  exactKeys(full, ['schema', 'tableList', 'columns']);
  need(Array.isArray(full.schema) && full.schema.length <= limits.schema
    && Array.isArray(full.tableList) && full.tableList.length <= limits.schema, 'boundary_metadata_bound');
  const automatic = full.schema.filter(row => row.name === AUTOMATIC);
  need(automatic.length === 1, 'automatic_metadata_identity');
  const table = automatic[0];
  exactKeys(table, ['type', 'name', 'tbl_name', 'sql']);
  need(table.type === 'table' && table.tbl_name === AUTOMATIC
    && (table.sql === null || typeof table.sql === 'string'), 'automatic_metadata_identity');
  // No prefix exemption, related trigger/index exception or metadata suppression.
  // An unfamiliar extra provider object must get its own reviewed support.
  need(full.schema.every(row => row === table || (row.tbl_name !== AUTOMATIC
    && (typeof row.sql !== 'string' || !/\b__cf_kv\b/i.test(row.sql)))), 'application_hidden_dependence');
  const storage = full.tableList.filter(row => row.name === AUTOMATIC);
  need(storage.length === 1, 'automatic_metadata_identity');
  exactKeys(storage[0], ['schema', 'name', 'type', 'ncol', 'wr', 'strict']);
  need(storage[0].schema === 'main' && storage[0].type === 'table'
    && Number.isSafeInteger(storage[0].ncol) && Number(storage[0].ncol) > 0
    && Number(storage[0].ncol) <= limits.columns
    && [0, 1].includes(storage[0].wr as number) && [0, 1].includes(storage[0].strict as number), 'automatic_metadata_shape');
  const columns = full.columns[AUTOMATIC];
  need(Array.isArray(columns) && columns.length === storage[0].ncol, 'automatic_metadata_shape');
  const names = new Set<string>();
  columns.forEach((column, i) => {
    exactKeys(column, ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk', 'hidden']);
    need(column.cid === i && typeof column.name === 'string' && /^[\x01-\x7f]{1,4096}$/.test(column.name)
      && !names.has(column.name.toLowerCase()) && typeof column.type === 'string'
      && [0, 1].includes(column.notnull as number) && (column.dflt_value === null || typeof column.dflt_value === 'string')
      && Number.isSafeInteger(column.pk) && Number(column.pk) >= 0 && Number(column.pk) <= columns.length
      && [0, 2, 3].includes(column.hidden as number), 'automatic_metadata_shape');
    names.add((column.name as string).toLowerCase());
  });
  const application: Census = {
    schema: full.schema.filter(row => row !== table),
    tableList: full.tableList.filter(row => row.name !== AUTOMATIC),
    columns: Object.fromEntries(Object.entries(full.columns).filter(([name]) => name !== AUTOMATIC)),
  };
  need(equal(application, { schema: manifest.application.schema,
    tableList: manifest.application.tableList, columns: manifest.application.columns }), 'application_metadata_projection');
  return application;
}

/** Retain full observed metadata and compare it independently of the application
 * projection. The unchanged complete reader is used ONLY for application SQL,
 * supported typed KV/alarm/fence and common source/population/closure checks.
 * No result from the old reader is returned as a complete original capture.
 */
export async function captureSupportedBoundary(source: SupportedSource, input: BoundaryRequest): Promise<BoundaryCapture> {
  try { return await captureBounded(source, input); }
  catch (error) { if (error instanceof BoundaryRefused) throw error; throw new BoundaryRefused('boundary_capture_refused'); }
}
async function captureBounded(source: SupportedSource, input: BoundaryRequest): Promise<BoundaryCapture> {
  const request = structuredClone(input), limits = request.limits;
  exactKeys(request, ['boundary', 'profile', 'expectedObjects', 'closure', 'expectedWriterIds', 'expectedSources', 'sourceBytes', 'fences', 'limits']);
  need(request.boundary === BOUNDARY && request.profile === PROFILE, 'explicit_boundary_required');
  const ceiling: Limits = { objects: 128, schema: 2048, tables: 128, columns: 256, rows: 10000,
    kv: 10000, bytes: 4 * 1024 * 1024, calls: 50000, page: 256, milliseconds: 600000 };
  exactKeys(limits, Object.keys(ceiling));
  for (const key of Object.keys(ceiling) as (keyof Limits)[]) need(Number.isSafeInteger(limits[key])
    && limits[key] >= 1 && limits[key] <= ceiling[key], 'boundary_limits');
  need(Array.isArray(request.expectedObjects) && request.expectedObjects.length > 0
    && request.expectedObjects.length <= limits.objects, 'boundary_object_bound');
  need(['reader.ts', 'object-kv-interface.ts', 'ADR0066.md'].every(name => name in request.expectedSources), 'boundary_source_binding');
  const deadline = performance.now() + limits.milliseconds;
  const expected = new Map<string, BoundaryExpectedObject>();
  let metadataReserve = 0, calls = 0, totalSchema = 0, totalTables = 0, totalColumns = 0;
  const key = (id: ObjectId) => canonical([id.namespace, id.id]);
  for (const object of request.expectedObjects) {
    exactKeys(object, ['namespace', 'id', 'manifest', 'manifestSha2_256', 'alarmKeys']);
    const manifest = object.manifest;
    exactKeys(manifest, ['boundary', 'revision', 'profile', 'object', 'automatic', 'observable', 'application', 'sourcePins']);
    exactKeys(manifest.object, ['namespace', 'id']);
    exactKeys(manifest.automatic, ['name', 'origin', 'applicationDependsOnRaw']);
    need(manifest.boundary === BOUNDARY && manifest.revision === REVISION && manifest.profile === PROFILE
      && equal(manifest.object, { namespace: object.namespace, id: object.id })
      && equal(manifest.automatic, { name: AUTOMATIC, origin: 'provider-automatic-sqlite-kv', applicationDependsOnRaw: false })
      && equal(manifest.sourcePins, request.expectedSources), 'boundary_manifest_binding');
    need(/^[a-f0-9]{64}$/.test(object.manifestSha2_256)
      && await sha2_256(encoder.encode(canonical(manifest))) === object.manifestSha2_256, 'boundary_manifest_pin');
    project(manifest, limits);
    totalSchema += manifest.observable.schema.length;
    totalTables += manifest.observable.schema.filter(row => row.type === 'table').length;
    totalColumns += Object.values(manifest.observable.columns).reduce((n, rows) => n + rows.length, 0);
    need(totalSchema <= limits.schema && totalTables <= limits.tables
      && totalColumns <= limits.columns, 'boundary_full_census_bound');
    need(!expected.has(key(object)), 'boundary_object_duplicate'); expected.set(key(object), object);
    // Charge both full before/after metadata reads AND retained full metadata.
    metadataReserve += 2 * (size(manifest.observable.schema) + size(manifest.observable.tableList)
      + Object.values(manifest.observable.columns).reduce((n, rows) => n + size(rows), 0)
      + size(manifest.observable) + size(manifest));
  }
  need(metadataReserve < limits.bytes, 'boundary_metadata_byte_bound');
  async function call<T>(fn: () => Promise<T>): Promise<T> {
    need(++calls <= limits.calls && performance.now() <= deadline, 'boundary_acquisition_bound');
    const value = await fn(); need(performance.now() <= deadline, 'boundary_elapsed_bound'); return value;
  }
  const observations = new Map<string, Census[]>();
  let boundaryFailure: BoundaryRefused | undefined;
  const wrapped: SupportedSource = {
    closure: () => call(() => source.closure()),
    listObjects: (after, limit) => call(() => source.listObjects(after, limit)),
    readObject: (id, read) => call(() => source.readObject(id, async session => {
      const object = expected.get(key(id)); need(!!object, 'boundary_unknown_object');
      const observed: Census[] = []; observations.set(key(id), observed);
      let projected: Census | undefined;
      const metadataQuery = async (sql: string, max: number): Promise<Row[]> => {
        const rows = await call(() => session.query(sql));
        need(Array.isArray(rows) && rows.length <= max, 'boundary_metadata_bound');
        return rows as Row[];
      };
      async function fullMetadata(): Promise<Census> {
        need(observed.length < 2, 'boundary_metadata_repeated');
        const schema = await metadataQuery(schemaSQL(limits.schema), limits.schema);
        const tableList = await metadataQuery(storageSQL(limits.schema), limits.schema);
        need(equal(schema, object!.manifest.observable.schema) && equal(tableList, object!.manifest.observable.tableList), 'observable_metadata_drift');
        const columns: Record<string, Row[]> = {};
        for (const name of Object.keys(object!.manifest.observable.columns).sort())
          Object.defineProperty(columns, name, { enumerable: true, value: await metadataQuery(columnsSQL(name, limits.columns), limits.columns) });
        const full = { schema, tableList, columns };
        need(equal(full, object!.manifest.observable), 'observable_metadata_drift');
        observed.push(structuredClone(full)); return project({ ...object!.manifest, observable: full }, limits);
      }
      const applicationSession: ReadSession = {
        async query(sql) {
          try {
            if (sql === schemaSQL(limits.schema)) { projected = await fullMetadata(); return projected.schema; }
            if (sql === storageSQL(limits.schema)) { need(!!projected, 'metadata_read_order'); return projected!.tableList; }
            // Ordinary application metadata/data reads are unchanged. Hidden SQL
            // count/cell/rowid reads are never substituted with a typed KV guess.
            need(!/\b__cf_kv\b/i.test(sql), 'hidden_sql_content_requested');
            return await call(() => session.query(sql));
          } catch (error) {
            if (error instanceof BoundaryRefused) boundaryFailure = error;
            throw error;
          }
        },
        listKV: (after, limit) => call(() => session.listKV(after, limit)),
        getAlarm: () => call(() => session.getAlarm()),
        fence: () => call(() => session.fence()),
      };
      return read(applicationSession);
    })),
  };
  const { boundary: _boundary, expectedObjects: _expected, ...base } = request;
  // The guard pin is derived from the independently pinned boundary manifest,
  // not from observed output. It retains the original guard reconstruction gate.
  let inner: Capture;
  try {
    inner = await captureApplication(wrapped, { ...base, ...await applicationPins(request.expectedObjects),
      limits: { ...limits, bytes: limits.bytes - metadataReserve } });
  } catch (error) { if (boundaryFailure) throw boundaryFailure; throw error; }
  const result: BoundaryCapture = { profile: PROFILE, boundary: BOUNDARY, revision: REVISION,
    actualQualification: false, sources: inner.sources, closure: inner.closure,
    objects: inner.objects.map(object => {
      const manifest = expected.get(key(object))!;
      const observable = observations.get(key(object)); need(observable?.length === 2, 'observable_metadata_incomplete');
      const { census, guardManifestSha256: _guard, ...facts } = object;
      return { ...facts, manifestSha2_256: manifest.manifestSha2_256,
        observable: { before: observable![0], after: observable![1] }, applicationCensus: census,
        excluded: { name: AUTOMATIC, rawSqlContents: 'unobserved-unfrozen-unverified', rowids: 'unobserved-unfrozen-unverified' } };
    }) };
  need(size(result) <= limits.bytes && performance.now() <= deadline, 'boundary_artifact_bound');
  return result;
}
async function applicationPins(objects: BoundaryExpectedObject[]) {
  return { expectedObjects: await Promise.all(objects.map(async object => ({ namespace: object.namespace, id: object.id,
    guardManifest: object.manifest.application,
    guardManifestSha256: await sha2_256(encoder.encode(canonical(object.manifest.application))), alarmKeys: object.alarmKeys }))) };
}
