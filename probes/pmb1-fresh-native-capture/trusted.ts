// MIT License; copyright 2026 Terry Ott.
// Source-local trusted-primary/reviewer composition; no wire/configuration loader.
import type { RuntimeEvidencePacket } from '../pmb1-runtime-evidence/types.ts';
import type { RuntimeEvidenceLedger } from '../pmb1-runtime-evidence/ledger.ts';
import type { MainEntryBinding } from '../../src/main_entry_maintenance.ts';
import { ReviewedCoverage, type CoverageExpectation, type AuthenticatedCoverage } from '../pmb1-native-disposition/coverage.ts';
import { DispositionUnavailable } from '../pmb1-native-disposition/observer.ts';
import { createFreshNativeSource, type FreshNativeSourceInput } from './source.ts';
import type { FreshNativeOwner } from './source.ts';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';

export interface TrustedInputConfiguration {
  binding: MainEntryBinding; journalDatabaseId: string; domainDatabaseId: string;
}
const instances = new WeakSet<object>();
const construction = Symbol('trusted-input-construction');
const fail = (reason: string): never => { throw new DispositionUnavailable(reason); };
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
const ids = (values: readonly string[]) => [...values].sort();

/** Accepted #0251 protected delivery boundary. Construct only AFTER the fixed
 * qualified operator publisher and fresh non-author review authenticated complete
 * semantic facts. The ledger establishes exact protected delivery and finite use;
 * these validators establish shape, population and binding, never semantic truth.
 * Labels, digests and this in-process brand supply no independent authentication.
 */
export class AssembledFreshInputs {
  readonly coverage: ReviewedCoverage;
  readonly #native: FreshNativeSourceInput;
  private constructor(token: symbol, coverage: ReviewedCoverage, native: FreshNativeSourceInput) {
    if (token !== construction) fail('trusted_input_not_assembled');
    this.coverage = coverage; this.#native = structuredClone(native);
    instances.add(this); Object.freeze(this);
  }
  static async assemble(expected: CoverageExpectation, authenticated: AuthenticatedCoverage,
    nativeInput: FreshNativeSourceInput, envelope: RuntimeEvidencePacket): Promise<AssembledFreshInputs> {
    // Copy before the first await; a later source-module mutation has no authority.
    const e = structuredClone(expected), a = structuredClone(authenticated), native = structuredClone(nativeInput);
    const coverage = new ReviewedCoverage(e, a);
    coverage.check(e.binding, e.journalDatabaseId, e.domainDatabaseId);
    if (native.request.profile !== e.profile || native.request.boundary !== e.objectBoundary
      || !same(ids(e.resources.filter(r => r.kind === 'object').map(r => r.id)),
        ids(native.request.expectedObjects.map(o => o.namespace + '/' + o.id)))
      || native.request.expectedWriterIds.some(id => !e.writers.some(w => w.id === id))
) fail('trusted_input_population_binding');
    const closure = native.request.closure;
    if (!/^(0|[1-9][0-9]{0,15})$/.test(closure.start) || !/^(0|[1-9][0-9]{0,15})$/.test(closure.end)) fail('trusted_input_closed_interval');
    const start = Number(closure.start), end = Number(closure.end), now = Date.now();
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > now || end <= now
      || end <= start || end - start > 600000 || end - now < native.request.limits.milliseconds
      || a.custody.some(c => c.fromMs > start || c.throughMs < end)) fail('trusted_input_closed_interval');
    // Existing source validators reconcile the complete census, packets, source
    // bytes, approved SQL and manifests BEFORE any binding resolution. These
    // deliberately unusable bindings prove assembly itself acquires nothing.
    const forbidden = () => fail('trusted_input_assembly_io');
    const bindings = Object.fromEntries(Object.keys(native.expectedPopulation.objects).map(namespace =>
      [namespace, { idFromString: forbidden, get: forbidden }])) as unknown as Record<string, DurableObjectNamespace<FreshNativeOwner>>;
    await createFreshNativeSource(native, bindings, {} as RuntimeEvidenceLedger, envelope);
    coverage.check(e.binding, e.journalDatabaseId, e.domainDatabaseId);
    return new AssembledFreshInputs(construction, coverage, native);
  }
  source(): FreshNativeSourceInput {
    this.assertConfiguration(this.coverage.records().expected);
    return structuredClone(this.#native);
  }
  assertConfiguration(config: TrustedInputConfiguration): void {
    const expected = this.coverage.records().expected;
    if (!same(config.binding, expected.binding) || config.journalDatabaseId !== expected.journalDatabaseId
      || config.domainDatabaseId !== expected.domainDatabaseId) fail('trusted_input_configuration_binding');
    this.coverage.check(config.binding, config.journalDatabaseId, config.domainDatabaseId);
    const now = Date.now(), closure = this.#native.request.closure;
    if (Number(closure.start) > now || Number(closure.end) <= now
      || Number(closure.end) - now < this.#native.request.limits.milliseconds) fail('trusted_input_closed_interval');
  }
}

export const assembleFreshInputs = AssembledFreshInputs.assemble;
export function assertAssembledFreshInputs(value: unknown,
  config: TrustedInputConfiguration): asserts value is AssembledFreshInputs {
  if (!value || typeof value !== 'object' || !instances.has(value)) fail('trusted_input_not_assembled');
  (value as AssembledFreshInputs).assertConfiguration(config);
}
