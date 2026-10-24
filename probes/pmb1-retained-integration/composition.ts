// MIT License; copyright 2026 Terry Ott.
// Trusted source composition only. No loader, bootstrap, discovery or control RPC.
import { compose } from '../pmb1-integer-candidate/candidate.ts';
import { D1MainEntryJournal } from '../pmb1-native-journal/journal.ts';
import { D1DomainReader } from '../pmb1-native-disposition/domain.ts';
import { NativeMainEntryObserver, type ObservationBounds } from '../pmb1-native-disposition/observer.ts';
import { NativePartitionDisposition } from '../pmb1-native-disposition/partition.ts';
import { PartitionMaintenance } from '../../src/partition_maintenance.ts';
import { PartitionWorker as OrdinaryPartitionWorker } from '../../src/dispatch_worker.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';
import { assertAssembledTrustedInputs, type AssembledTrustedInputs, type TrustedInputConfiguration } from './trusted_inputs.ts';
import type { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
import type { NativeCaptureControl } from '../pmb1-native-object-reader/native-control.ts';
import type { Env } from '../../src/worker.ts';
import contract from './source-contract.json' with { type: 'json' };

export interface RetainedEnvironment extends Env {
  PMB1_MAIN_JOURNAL: D1Database;
  PMB1_OWNERS: DurableObjectNamespace<NativeCaptureOwner>;
  PMB1_CAPTURE_CONTROL: DurableObjectNamespace<NativeCaptureControl>;
}
export interface RetainedConfiguration extends TrustedInputConfiguration {
  bounds: ObservationBounds;
}

/** Only the existing trusted-primary/reviewer source boundary can construct the
 * assembly. Environment bindings supply native capabilities, never truth facts.
 * The source module is compiled and retained with its exact reviewed artifact.
 */
export function createRetainedCandidate(env: RetainedEnvironment, configuration: RetainedConfiguration,
  trusted: AssembledTrustedInputs) {
  const config = structuredClone(configuration);
  assertAssembledTrustedInputs(trusted, config);
  if (config.binding.candidate !== contract.sourceContextSha2_256) throw new MainEntryUnavailable();
  const source = trusted.source();
  const journal = new D1MainEntryJournal(env, { binding: config.binding,
    journalDatabaseId: config.journalDatabaseId, comparedDatabaseIds: [config.domainDatabaseId] });
  const domain = new D1DomainReader(env.DB, config.bounds,
    { databaseId: config.domainDatabaseId, generation: config.binding.generation, state: 'closed' });
  const observer = new NativeMainEntryObserver(journal, config.bounds, domain, trusted.coverage, config.domainDatabaseId);
  const bindings: Record<string, DurableObjectNamespace<NativeCaptureOwner>> = {};
  // A single native owner binding must mean one exact reviewed namespace.
  const namespaces = Object.keys(source.expectedPopulation.objects);
  if (namespaces.length !== 1) throw new MainEntryUnavailable();
  bindings[namespaces[0]] = env.PMB1_OWNERS;
  // compose's generated CandidatePartitionWorker is intentionally not exported.
  // Only partition() below owns local storage and supplies native disposition.
  // Main-entry dispatch never invokes these partition-only ports.
  const absent = new NativePartitionDisposition();
  const candidate = compose({ profile: 'pmb1-private-application-no-real-v1', binding: config.binding,
    journal, observer, flickr: request => fetch(request),
    verifyObjectDisposition: absent.verify, verifyPartitionReconciliation: absent.reconcile });
  const handler = {
    async fetch(request: Request, runtime: RetainedEnvironment) {
      assertAssembledTrustedInputs(trusted, config);
      // Prevent callers mixing a reviewed assembly and another native authority.
      if (runtime !== env) throw new MainEntryUnavailable();
      return candidate.handler.fetch(request, runtime);
    },
    async scheduled(event: ScheduledController, runtime: RetainedEnvironment) {
      assertAssembledTrustedInputs(trusted, config);
      if (runtime !== env) throw new MainEntryUnavailable();
      return candidate.handler.scheduled(event, runtime);
    },
  };
  function partition(ctx: DurableObjectState, namespace: string, id: string) {
    assertAssembledTrustedInputs(trusted, config);
    if (namespace !== namespaces[0] || !source.request.expectedObjects.some(o => o.namespace === namespace && o.id === id))
      throw new MainEntryUnavailable();
    const disposition = new NativePartitionDisposition({ ...config, namespace, id,
      deadlineMs: performance.now() + config.bounds.milliseconds, source: trusted.source() },
    ctx.storage, domain, trusted.coverage, bindings, env.PMB1_CAPTURE_CONTROL);
    const maintenance = new PartitionMaintenance(ctx.storage, disposition.verify, Date.now, disposition.reconcile);
    const worker = new OrdinaryPartitionWorker(ctx, { ...env, FGA_PARTITION_MAINTENANCE: () => maintenance });
    return Object.freeze({ worker, maintenance, disposition });
  }
  return Object.freeze({ handler, maintenance: candidate.maintenance, observer, domain, partition });
}
