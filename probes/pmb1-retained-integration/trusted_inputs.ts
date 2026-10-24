// MIT License; copyright 2026 Terry Ott.
// Source-local trusted-primary/reviewer composition; no wire/configuration loader.
import type { MainEntryBinding } from '../../src/main_entry_maintenance.ts';
import { ReviewedCoverage, type CoverageExpectation, type AuthenticatedCoverage } from '../pmb1-native-disposition/coverage.ts';
import { DispositionUnavailable } from '../pmb1-native-disposition/observer.ts';
import { createNativeSource, type NativeSourceInput } from '../pmb1-native-object-reader/native-source.ts';
import type { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';

export interface TrustedInputConfiguration {
  binding: MainEntryBinding; journalDatabaseId: string; domainDatabaseId: string;
}
const instances = new WeakSet<object>();
const construction = Symbol('trusted-input-construction');
const fail = (reason: string): never => { throw new DispositionUnavailable(reason); };
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
const ids = (values: readonly string[]) => [...values].sort();

/** Reconstructed inside each isolate from a private reviewed SOURCE module.
 * The primary and an independent reviewer must authenticate the semantic facts
 * and their provenance BEFORE authoring that module. Record names, digests,
 * census counts and this in-process brand do not establish that authentication.
 * Bind that module and all its imports to the exact later retained artifact.
 * No implementation here obtains facts or claims actual qualification.
 */
export class AssembledTrustedInputs {
  readonly coverage: ReviewedCoverage;
  readonly #native: NativeSourceInput;
  private constructor(token: symbol, coverage: ReviewedCoverage, native: NativeSourceInput) {
    if (token !== construction) fail('trusted_input_not_assembled');
    this.coverage = coverage; this.#native = structuredClone(native);
    instances.add(this); Object.freeze(this);
  }
  static async assemble(expected: CoverageExpectation, authenticated: AuthenticatedCoverage,
    nativeInput: NativeSourceInput): Promise<AssembledTrustedInputs> {
    // Copy before the first await; a later source-module mutation has no authority.
    const e = structuredClone(expected), a = structuredClone(authenticated), native = structuredClone(nativeInput);
    const coverage = new ReviewedCoverage(e, a);
    coverage.check(e.binding, e.journalDatabaseId, e.domainDatabaseId);
    if (native.request.profile !== e.profile || native.request.boundary !== e.objectBoundary
      || !same(ids(e.resources.filter(r => r.kind === 'object').map(r => r.id)),
        ids(native.request.expectedObjects.map(o => o.namespace + '/' + o.id)))
      || native.request.expectedWriterIds.some(id => !e.writers.some(w => w.id === id))
      || e.resources.some(r => r.id === native.control.namespace + '/' + native.control.id)) fail('trusted_input_population_binding');
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
      [namespace, { idFromString: forbidden, get: forbidden }])) as unknown as Record<string, DurableObjectNamespace<NativeCaptureOwner>>;
    await createNativeSource(native, bindings, { idFromString: forbidden, get: forbidden } as never);
    coverage.check(e.binding, e.journalDatabaseId, e.domainDatabaseId);
    return new AssembledTrustedInputs(construction, coverage, native);
  }
  source(): NativeSourceInput {
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

export const assembleTrustedInputs = AssembledTrustedInputs.assemble;
export function assertAssembledTrustedInputs(value: unknown,
  config: TrustedInputConfiguration): asserts value is AssembledTrustedInputs {
  if (!value || typeof value !== 'object' || !instances.has(value)) fail('trusted_input_not_assembled');
  (value as AssembledTrustedInputs).assertConfiguration(config);
}
