// MIT License; copyright 2026 Terry Ott.
// Accepted #0251 SOURCE successor; D1 ledger owns all NEW capture attempts.
// Legacy source/control/owner and spent attempts are preserved unchanged.
import { canonical, sha2_256, type SupportedSource, type ObjectId, type ReadSession,
  type Closure, type Page } from '../pmb1-no-real-object-reader/reader.ts';
import { captureSupportedBoundary, BOUNDARY, type BoundaryRequest } from '../pmb1-native-object-reader/object-kv-interface.ts';
import { readLocalSupportedBoundary, type NativeBounds } from '../pmb1-native-object-reader/native.ts';
import type { DurableObject } from 'cloudflare:workers';
import type { EvidenceReference as OwnerReference } from '../pmb1-runtime-evidence/types.ts';
export type FreshNativeOwner = DurableObject & { acquireFresh(reference: OwnerReference, pin: string): Promise<Carrier> };
import type { EvidenceReference, RuntimeEvidencePacket } from '../pmb1-runtime-evidence/types.ts';
import type { RuntimeEvidenceLedger } from '../pmb1-runtime-evidence/ledger.ts';

const encoder = new TextEncoder();
const key = (id: ObjectId) => canonical([id.namespace, id.id]);
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
export class NativeSourceRefused extends Error {}
const need = (ok: unknown, reason: string): void => { if (!ok) throw new NativeSourceRefused(reason); };
const digest = (value: unknown) => sha2_256(encoder.encode(canonical(value)));
const exact = (value: object, keys: string[]) => need(same(Object.keys(value).sort(), keys.sort()), 'native_source_shape');
const hex = (value: string) => Uint8Array.from(value.match(/../g) ?? [], n => parseInt(n, 16));

export interface Namespace { id: string; class: string; name: string; script: string; use_sqlite: boolean }
export interface Population {
  accountId: string;
  accountNamespaces: Namespace[];
  objects: Record<string, { id: string; hasStoredData: boolean }[]>;
}
export interface OwnerPacket {
  schema: 'pmb1-private-native-owner-packet-v1';
  // Every query is frozen in the independently reviewed packet before dispatch.
  approvedReads: string[];
  maximumEvents: number;
  request: Omit<BoundaryRequest, 'sourceBytes'>;
  sourceHex: Record<string, string>;
}
type Event = { kind: 'query'; index: number; value: unknown }
  | { kind: 'kv'; value: Page<[string, unknown]> }
  | { kind: 'alarm'; value: number | null }
  | { kind: 'fence'; value: Awaited<ReturnType<ReadSession['fence']>> };
export interface Carrier {
  schema: 'pmb1-native-acquired-facts-v1'; packetSha2_256: string;
  object: ObjectId; events: Event[]; actualQualification: false;
}
export interface FreshNativeSourceInput {
  control: EvidenceReference;
  request: BoundaryRequest;
  expectedPopulation: Population;
  // These are separately retained input pins, not an assertion of independence.
  expectedPopulationSha2_256: string;
  inventoryProvenanceSha2_256: string;
  census: Population & { schema: 'pmb1-native-census-observation-v1'; completeSnapshot: false;
    actualQualification: false; calls: number; bytes: number };
  censusSha2_256: string;
  packets: { packet: OwnerPacket; sha2_256: string }[];
}

function ids(population: Population): ObjectId[] {
  exact(population, ['accountId', 'accountNamespaces', 'objects']);
  need(/^[a-f0-9]{32}$/.test(population.accountId), 'native_account_identity');
  need(Array.isArray(population.accountNamespaces) && population.accountNamespaces.length <= 128, 'native_namespace_bound');
  const namespaces = new Set<string>();
  for (const row of population.accountNamespaces) {
    exact(row, ['id', 'class', 'name', 'script', 'use_sqlite']);
    need(/^[a-f0-9]{32}$/.test(row.id) && !namespaces.has(row.id)
      && typeof row.use_sqlite === 'boolean'
      && [row.class, row.name, row.script].every(v => typeof v === 'string' && encoder.encode(v).length >= 1
        && encoder.encode(v).length <= 4096), 'native_namespace_identity');
    namespaces.add(row.id);
  }
  const result: ObjectId[] = [];
  for (const [namespace, objects] of Object.entries(population.objects)) {
    need(population.accountNamespaces.some(n => n.id === namespace && n.use_sqlite)
      && Array.isArray(objects), 'native_selected_namespace');
    const seen = new Set<string>();
    for (const object of objects) {
      exact(object, ['id', 'hasStoredData']);
      need(/^[a-f0-9]{64}$/.test(object.id) && typeof object.hasStoredData === 'boolean'
        && !seen.has(object.id), 'native_object_identity');
      seen.add(object.id); result.push({ namespace, id: object.id });
      need(result.length <= 128, 'native_object_bound');
    }
  }
  need(Object.keys(population.objects).length > 0, 'native_empty_selection');
  return result.sort((a, b) => key(a) < key(b) ? -1 : key(a) === key(b) ? 0 : 1);
}

function pages(objects: ObjectId[], after: string | null, limit: number): Page<ObjectId> {
  need(Number.isSafeInteger(limit) && limit >= 1 && limit <= 256
    && (after === null || typeof after === 'string'), 'native_page_bound');
  const entries = objects.filter(id => after === null || key(id) > after).slice(0, limit);
  return { entries: structuredClone(entries), next: entries.length ? key(entries[entries.length - 1]) : null };
}

// Exercise the existing validators with retained inputs before resolving a native
// object binding. This has no observed storage and cannot be a source oracle.
async function validateRequest(request: BoundaryRequest): Promise<void> {
  let reached = false;
  const objects = request.expectedObjects.map(({ namespace, id }) => ({ namespace, id }));
  try {
    await captureSupportedBoundary({ closure: async () => request.closure,
      listObjects: async (after, limit) => pages(objects, after, limit),
      async readObject() { reached = true; throw new Error('validation_stop'); } }, request);
  } catch { need(reached, 'native_packet_request_invalid'); return; }
  throw new NativeSourceRefused('native_packet_request_invalid');
}

export async function unpackOwnerPacket(input: OwnerPacket, expectedHash: string): Promise<BoundaryRequest> {
  const packet = structuredClone(input);
  exact(packet, ['schema', 'approvedReads', 'maximumEvents', 'request', 'sourceHex']);
  need(packet.schema === 'pmb1-private-native-owner-packet-v1' && /^[a-f0-9]{64}$/.test(expectedHash)
    && encoder.encode(canonical(packet)).length <= 4 * 1024 * 1024
    && await digest(packet) === expectedHash, 'native_packet_pin');
  const sourceBytes: Record<string, Uint8Array> = {};
  let sourceSize = 0;
  for (const [name, value] of Object.entries(packet.sourceHex)) {
    need(typeof value === 'string' && /^(?:[a-f0-9]{2})+$/.test(value), 'native_packet_source');
    sourceSize += value.length / 2;
    need(sourceSize <= packet.request.limits.bytes, 'native_packet_source_bound');
    Object.defineProperty(sourceBytes, name, { enumerable: true, value: hex(value) });
  }
  need(['evidence-use.ts', 'owning-partition.ts', 'owning-core.ts', 'private-controller.ts', 'fresh-source.ts', 'fresh-owner.ts', 'fresh-owner-core.ts', 'fresh-payload.ts', 'fresh-trusted.ts', 'fresh-partition.ts', 'fresh-authority.ts', 'fresh-qualification.ts', 'runtime-ledger.ts', 'runtime-types.ts', 'native-source.ts', 'native-owner.ts', 'native-control.ts', 'native.ts', 'reader.ts', 'object-kv-interface.ts', 'ADR0066.md']
    .every(name => name in sourceBytes), 'native_factory_source_binding');
  need(Array.isArray(packet.approvedReads) && packet.approvedReads.length > 0
    && new Set(packet.approvedReads).size === packet.approvedReads.length
    && packet.approvedReads.every(sql => typeof sql === 'string' && sql.startsWith('SELECT ')
      && !/[;\u0000]|--|\/\*/.test(sql) && encoder.encode(sql).length <= 100000)
    && encoder.encode(canonical(packet.approvedReads)).length <= packet.request.limits.bytes, 'native_read_plan');
  need(Number.isSafeInteger(packet.maximumEvents) && packet.maximumEvents >= 1
    && packet.maximumEvents <= packet.request.limits.calls
    && packet.request.expectedObjects.length === 1, 'native_owner_population');
  const request = { ...packet.request, sourceBytes };
  await validateRequest(request);
  return request;
}

/** Called by the concrete storage-owning class, never a new reader namespace.
 * The consumer runs locally. Only bounded acquired values cross the RPC boundary;
 * no ReadSession, storage handle, callback or arbitrary SQL parameter crosses it.
 */
export async function acquireNativeFacts(storage: Pick<DurableObjectStorage, 'sql' | 'transaction'>,
  namespace: string, objectId: string, packetInput: OwnerPacket, packetHash: string): Promise<Carrier> {
  const packet = structuredClone(packetInput), request = await unpackOwnerPacket(packet, packetHash);
  const object = request.expectedObjects[0], id = { namespace, id: objectId };
  need(same({ namespace: object.namespace, id: object.id }, id), 'native_owner_identity');
  const fence = request.fences[key(id)], events: Event[] = [];
  // Reserve carrier framing and both custody-bearing fences BEFORE acquisition.
  // Native helper separately bounds all acquired/retained serialized facts. This
  // does not claim a Workers RPC wire/engine/JS heap bound or interruptible SQL.
  const overhead = packet.maximumEvents * 128 + 1024 + 2 * encoder.encode(canonical(fence)).length;
  const bounds: NativeBounds = { calls: request.limits.calls, rows: Math.max(request.limits.rows,
    request.limits.schema + 1, request.limits.columns + 1), bytes: request.limits.bytes - overhead,
    milliseconds: request.limits.milliseconds, kvAcquisitionBytes: 2 * 1024 * 1024 };
  need(bounds.bytes > bounds.kvAcquisitionBytes, 'native_carrier_reserve');
  function record(event: Event) {
    need(events.length < packet.maximumEvents, 'native_carrier_event_bound'); events.push(event);
  }
  const source: SupportedSource = {
    closure: async () => structuredClone(request.closure),
    listObjects: async (after, limit) => pages([id], after, limit),
    async readObject(selected, read) {
      need(same(selected, id), 'native_owner_identity');
      return readLocalSupportedBoundary(storage, packet.approvedReads, fence, bounds,
        { manifest: object.manifest, manifestSha2_256: object.manifestSha2_256,
          sourceBytes: request.sourceBytes, columns: request.limits.columns }, async session => {
          const gate = () => need(events.length < packet.maximumEvents, 'native_carrier_event_bound');
          return read({
            async query(sql) { gate(); const index = packet.approvedReads.indexOf(sql);
              need(index >= 0, 'native_unplanned_query'); const value = await session.query(sql);
              record({ kind: 'query', index, value }); return value; },
            async listKV(after, limit) { gate(); const value = await session.listKV(after, limit);
              record({ kind: 'kv', value }); return value; },
            async getAlarm() { gate(); const value = await session.getAlarm(); record({ kind: 'alarm', value }); return value; },
            async fence() { gate(); const value = await session.fence(); record({ kind: 'fence', value }); return value; },
          });
        });
    },
  };
  await captureSupportedBoundary(source, request);
  return { schema: 'pmb1-native-acquired-facts-v1', packetSha2_256: packetHash, object: id,
    events, actualQualification: false };
}

/** A source instance is a single consumer attempt, including unknown outcomes.
 * It consumes the exact independently reconciled census, never invents expected
 * population from observed objects, and never treats pagination as a snapshot.
 */
export async function createFreshNativeSource(incoming: FreshNativeSourceInput,
  bindings: Record<string, DurableObjectNamespace<FreshNativeOwner>>,
  ledger: RuntimeEvidenceLedger, envelope: RuntimeEvidencePacket, deferFinalValidation=false): Promise<SupportedSource> {
  const input = structuredClone(incoming), request = input.request;
  exact(input, ['control', 'request', 'expectedPopulation', 'expectedPopulationSha2_256', 'inventoryProvenanceSha2_256',
    'census', 'censusSha2_256', 'packets']);
  need(request.boundary === BOUNDARY && /^[a-f0-9]{64}$/.test(input.inventoryProvenanceSha2_256)
    && await digest(input.expectedPopulation) === input.expectedPopulationSha2_256
    && await digest(input.census) === input.censusSha2_256, 'native_population_pin');
  exact(input.census, ['schema', 'completeSnapshot', 'actualQualification', 'accountId', 'accountNamespaces', 'objects', 'calls', 'bytes']);
  need(input.census.schema === 'pmb1-native-census-observation-v1' && input.census.completeSnapshot === false
    && input.census.actualQualification === false && Number.isSafeInteger(input.census.calls)
    && input.census.calls > 0 && input.census.calls <= 64 && Number.isSafeInteger(input.census.bytes)
    && input.census.bytes >= 0 && input.census.bytes <= 4 * 1024 * 1024, 'native_census_observation');
  const observed = { accountId: input.census.accountId, accountNamespaces: input.census.accountNamespaces, objects: input.census.objects };
  const objects = ids(input.expectedPopulation); ids(observed);
  exact(input.control, ['databaseId', 'envelopeId', 'attemptId', 'operation']);
  need(same(input.control, envelope.reference), 'fresh_native_control_binding');
  // One complete included object is the supported finite ledger allocation.
  // Never truncate a larger census to fit it.
  need(objects.length >= 1 && objects.length <= 16, 'fresh_native_capture_allocation');
  need(same(input.expectedPopulation, observed)
    && same(objects, request.expectedObjects.map(({ namespace, id }) => ({ namespace, id })))
    && same(Object.keys(bindings).sort(), Object.keys(observed.objects).sort()), 'native_population_reconciliation');
  await validateRequest(request);
  const packets = new Map<string, { packet: OwnerPacket; sha2_256: string }>();
  need(input.packets.length === objects.length, 'native_packet_population');
  for (const entry of input.packets) {
    exact(entry, ['packet', 'sha2_256']); const local = await unpackOwnerPacket(entry.packet, entry.sha2_256);
    const id = key(local.expectedObjects[0]);
    const expected = request.expectedObjects.find(o => key(o) === id);
    need(expected && !packets.has(id) && same(local.expectedObjects, [expected])
      && same(local.fences, { [id]: request.fences[id] })
      && same(local.expectedSources, request.expectedSources) && same(local.closure, request.closure)
      && same(local.limits, request.limits) && same(local.expectedWriterIds, request.expectedWriterIds), 'native_packet_binding');
    packets.set(id, entry);
  }
  let active = true, failure: NativeSourceRefused | undefined, closureReads = 0, populationDone = false;
  let cursor: string | null = null, busy = false;
  const spent = new Set<string>(), deadline = performance.now() + request.limits.milliseconds;
  const gate = () => { if (failure) throw failure; need(active && performance.now() <= deadline && Number(request.closure.start) <= Date.now()
      && Date.now() < Number(request.closure.end), 'native_source_closed'); };
  const poison = (error: unknown): never => {
    active = false; failure = error instanceof NativeSourceRefused ? error : new NativeSourceRefused('native_acquisition_unknown');
    throw failure;
  };
  return {
    async closure(): Promise<Closure> {
      try { gate(); need(++closureReads <= 2, 'native_source_once_only');
        if (closureReads === 2) { need(spent.size === objects.length, 'native_source_incomplete');
          if(!deferFinalValidation)await ledger.revalidate(envelope); gate(); active = false; }
        return structuredClone(request.closure);
      } catch (e) { return poison(e); }
    },
    async listObjects(after, limit) {
      try { gate(); need(closureReads === 1 && !populationDone && after === cursor, 'native_population_session');
        const page = pages(objects, after, limit); cursor = page.next;
        if (!page.entries.length) populationDone = true;
        return page;
      } catch (e) { return poison(e); }
    },
    async readObject(id, read) {
      try {
        gate(); need(envelope.header.mode==='raw-capture'&&envelope.header.captureKeys.includes(id.namespace+'/'+id.id),'native_source_capture_unallocated');
        const k = key(id), entry = packets.get(k);
        need(populationDone && entry && !spent.has(k) && !busy, 'native_object_once_only'); spent.add(k); busy = true;
        // idFromString/get are used only after every source/population/packet gate.
        // No newUniqueId, idFromName, bootstrap, discovery or retry exists here.
        const binding = bindings[id.namespace];
        const stub = binding.get(binding.idFromString(id.id));
        const carrier: Carrier = await stub.acquireFresh(input.control, entry!.sha2_256);
        gate();
        need(carrier.schema === 'pmb1-native-acquired-facts-v1' && carrier.actualQualification === false
          && carrier.packetSha2_256 === entry!.sha2_256 && same(carrier.object, id)
          && Array.isArray(carrier.events) && carrier.events.length <= entry!.packet.maximumEvents, 'native_carrier_binding');
        let index = 0, open = true, kvAfter: string | null = null;
        const take = (kind: Event['kind']): Event => {
          gate(); need(open && index < carrier.events.length, 'native_session_closed');
          const event = carrier.events[index++]; need(event.kind === kind, 'native_carrier_order'); return event;
        };
        const guarded = async <T>(fn: () => T): Promise<T> => {
          try { return fn(); } catch (error) { return poison(error); }
        };
        try {
          const result = await read({
            query: sql => guarded(() => { const event = take('query') as Extract<Event, { kind: 'query' }>;
              need(entry!.packet.approvedReads[event.index] === sql, 'native_carrier_query'); return structuredClone(event.value); }),
            listKV: (after, limit) => guarded(() => { need(after === kvAfter && limit === request.limits.page, 'native_carrier_kv_cursor');
              const event = take('kv') as Extract<Event, { kind: 'kv' }>;
              kvAfter = event.value.next; return structuredClone(event.value); }),
            getAlarm: () => guarded(() => (take('alarm') as Extract<Event, { kind: 'alarm' }>).value),
            fence: () => guarded(() => structuredClone((take('fence') as Extract<Event, { kind: 'fence' }>).value)),
          });
          need(index === carrier.events.length, 'native_carrier_incomplete');
          await ledger.complete(input.control, id.namespace + '/' + id.id, 'complete');
          gate(); return result;
        } finally { open = false; busy = false; }
      } catch (e) { return poison(e); }
    },
  };
}
