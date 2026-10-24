// MIT License; copyright 2026 Terry Ott.
// The sole serialized delivery exception is the accepted protected D1 protocol.
import { AssembledFreshInputs } from './trusted.ts';
import type { FreshNativeSourceInput } from './source.ts';
import type { FreshRetainedConfiguration } from '../pmb1-retained-integration/fresh_composition.ts';
import type { AuthenticatedCoverage, CoverageExpectation } from '../pmb1-native-disposition/coverage.ts';
import type { RuntimeEvidencePacket } from '../pmb1-runtime-evidence/types.ts';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';

export interface RuntimePayload {
  schema: 'pmb1-retained-runtime-input-v1';
  configuration: FreshRetainedConfiguration;
  coverage: { expected: CoverageExpectation; authenticated: AuthenticatedCoverage };
  native: FreshNativeSourceInput;
  partitionNamespace: string;
}
const need = (value: unknown): void => { if (!value) throw new MainEntryUnavailable(); };
export async function validateRuntimePayload(envelope: RuntimeEvidencePacket): Promise<RuntimePayload> {
  // Only a ledger-verified packet may enter this module. Semantic provenance is
  // independently authenticated before constructing the ledger, never inferred
  // from these labels, hashes, a native binding or a reviewer string.
  const payload = structuredClone(envelope.payload) as RuntimePayload;
  need(payload && canonical(Object.keys(payload).sort()) === canonical([
    'schema', 'configuration', 'coverage', 'native', 'partitionNamespace'].sort()));
  need(payload.schema === 'pmb1-retained-runtime-input-v1');
  const wireSources = payload.native.request.sourceBytes as unknown as Record<string, unknown>;
  need(wireSources && typeof wireSources === 'object' && !Array.isArray(wireSources));
  let decodedBytes = 0;
  const sources: Record<string, Uint8Array> = {};
  for (const [name, encoded] of Object.entries(wireSources)) {
    need(typeof encoded === 'string' && /^(?:[a-f0-9]{2})+$/.test(encoded as string));
    decodedBytes += (encoded as string).length / 2;
    need(decodedBytes <= envelope.header.allocation.maxDecodedBytes);
    Object.defineProperty(sources, name, { enumerable: true, value:
      Uint8Array.from((encoded as string).match(/../g)!, value => parseInt(value, 16)) });
  }
  payload.native.request.sourceBytes = sources;
  const binding = envelope.header.binding;
  need(payload.configuration.binding.candidate === binding.sourceContext
    && payload.configuration.binding.lifecycle === binding.lifecycle
    && payload.configuration.binding.generation === binding.generation
    && payload.configuration.journalDatabaseId === envelope.reference.databaseId
    && payload.configuration.domainControl.databaseId === payload.configuration.domainDatabaseId
    && canonical(payload.native.control) === canonical(envelope.reference)
    && canonical(payload.coverage.expected.binding) === canonical(payload.configuration.binding)
    && payload.coverage.expected.journalDatabaseId === envelope.reference.databaseId);
  need(Number(payload.native.request.closure.start) >= envelope.header.fromMs
    && Number(payload.native.request.closure.end) <= envelope.header.throughMs);
  const objects = payload.native.request.expectedObjects.map(o => o.namespace + '/' + o.id).sort();
  need((envelope.header.mode==='raw-capture'?canonical(objects) === canonical([...envelope.header.captureKeys].sort()):envelope.header.captureKeys.length===0)
    && (envelope.header.mode!=='raw-capture'||(Number.isSafeInteger(payload.native.request.limits.bytes * objects.length)
    && payload.native.request.limits.bytes * objects.length <= envelope.header.allocation.maxNativeBytes))
    && Object.keys(payload.native.expectedPopulation.objects).length === 1
    && payload.partitionNamespace === Object.keys(payload.native.expectedPopulation.objects)[0]
    && payload.native.request.expectedSources['fresh-source.ts'] === binding.nativeSourceDigest
    && payload.native.request.expectedSources['owning-partition.ts'] === binding.ownerSourceDigest);
  // Complete validators run before any capability resolution or class granting
  // positive maintenance. This invokes no native acquisition.
  await AssembledFreshInputs.assemble(payload.coverage.expected,
    payload.coverage.authenticated, payload.native, envelope);
  return payload;
}
