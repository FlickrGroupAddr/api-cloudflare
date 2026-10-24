// MIT License; copyright 2026 Terry Ott.
// Accepted protected-delivery composition. No public truth loader or bootstrap.
import { compose } from '../pmb1-integer-candidate/candidate.ts';
import { D1MainEntryJournal } from '../pmb1-native-journal/journal.ts';
import { NativeD1DomainReader } from '../pmb1-fresh-native-capture/domain.ts';
import type { QualifiedNativeDomainPlan } from '../pmb1-fresh-native-capture/domain-plan.ts';
import { NativeMainEntryObserver, type ObservationBounds } from '../pmb1-native-disposition/observer.ts';
import { FreshNativePartitionDisposition } from '../pmb1-fresh-native-capture/partition.ts';
import { PartitionMaintenance } from '../../src/partition_maintenance.ts';
import { PartitionWorker as OrdinaryPartitionWorker } from '../../src/dispatch_worker.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';
import { assertAssembledFreshInputs, type AssembledFreshInputs, type TrustedInputConfiguration } from '../pmb1-fresh-native-capture/trusted.ts';
import type { FreshNativeOwner } from '../pmb1-fresh-native-capture/source.ts';
import type { Carrier } from '../pmb1-fresh-native-capture/source.ts';
import type { EvidenceReference } from '../pmb1-runtime-evidence/types.ts';
import type { RuntimeEvidenceLedger } from '../pmb1-runtime-evidence/ledger.ts';
import type { RuntimeEvidencePacket } from '../pmb1-runtime-evidence/types.ts';
import type { Env } from '../../src/worker.ts';
import contract from './source-contract.json' with { type: 'json' };
import type { PartitionWorker } from './entry.ts';
import {EvidenceMainEntryObserver,loadEvidenceUse,assertEvidenceUse,type EvidenceUseFactory} from '../pmb1-fresh-native-capture/evidence-use.ts';
import type {PartitionCapture} from '../../src/partition_maintenance.ts';

export interface FreshRetainedEnvironment extends Env {
  PMB1_MAIN_JOURNAL: D1Database;
  PMB1_VERSION_METADATA?: WorkerVersionMetadata;
  COORD: DurableObjectNamespace<PartitionWorker>;
}
export interface FreshRetainedConfiguration extends TrustedInputConfiguration {
  bounds: ObservationBounds;
  domainControl: { databaseId: string; generation: string; state: 'open' | 'closed' };
  domainPlan: QualifiedNativeDomainPlan;
}

/** Only the existing trusted-primary/reviewer source boundary can construct the
 * assembly. Environment bindings supply native capabilities, never truth facts.
 * The source module is compiled and retained with its exact reviewed artifact.
 */
export function createFreshRetainedCandidate(env: FreshRetainedEnvironment, configuration: FreshRetainedConfiguration,
  trusted: AssembledFreshInputs, ledger: RuntimeEvidenceLedger, envelope: RuntimeEvidencePacket,
  evidenceUseFactory:EvidenceUseFactory=purpose=>loadEvidenceUse(env,purpose)) {
  const config = structuredClone(configuration);
  assertAssembledFreshInputs(trusted, config);
  if (config.binding.candidate !== contract.sourceContextSha2_256) throw new MainEntryUnavailable();
  if (config.domainControl.databaseId !== config.domainDatabaseId) throw new MainEntryUnavailable();
  const source = trusted.source();
  const journal = new D1MainEntryJournal(env, { binding: config.binding,
    journalDatabaseId: config.journalDatabaseId, comparedDatabaseIds: [config.domainDatabaseId] });
  const domain = new NativeD1DomainReader(env.DB, config.bounds,
    config.domainControl, config.domainPlan);
  const observer = new EvidenceMainEntryObserver(env,config,evidenceUseFactory);
  const bindings: Record<string, DurableObjectNamespace<FreshNativeOwner>> = {};
  // A single native owner binding must mean one exact reviewed namespace.
  const namespaces = Object.keys(source.expectedPopulation.objects);
  if (namespaces.length !== 1) throw new MainEntryUnavailable();
  bindings[namespaces[0]] = env.COORD;
  // compose's generated CandidatePartitionWorker is intentionally not exported.
  // Only partition() below owns local storage and supplies native disposition.
  // Main-entry dispatch never invokes these partition-only ports.
  const absent = new FreshNativePartitionDisposition();
  const candidate = compose({ profile: 'pmb1-private-application-no-real-v1', binding: config.binding,
    journal, observer, flickr: request => fetch(request),
    verifyObjectDisposition: absent.verify, verifyPartitionReconciliation: absent.reconcile });
  const handler = {
    async fetch(request: Request, runtime: FreshRetainedEnvironment) {
      assertAssembledFreshInputs(trusted, config);
      // Prevent callers mixing a reviewed assembly and another native authority.
      if (runtime !== env) throw new MainEntryUnavailable();
      return candidate.handler.fetch(request, runtime);
    },
    async scheduled(event: ScheduledController, runtime: FreshRetainedEnvironment) {
      assertAssembledFreshInputs(trusted, config);
      if (runtime !== env) throw new MainEntryUnavailable();
      return candidate.handler.scheduled(event, runtime);
    },
  };
  function partition(ctx: DurableObjectState, namespace: string, id: string,
    localOwner?: {acquireFresh(reference:EvidenceReference,pin:string):Promise<Carrier>}) {
    assertAssembledFreshInputs(trusted, config);
    if (namespace !== namespaces[0] || !source.request.expectedObjects.some(o => o.namespace === namespace && o.id === id))
      throw new MainEntryUnavailable();
    const partitionBindings={...bindings};
    if(localOwner){
      const native=bindings[namespace];
      // Local port never crosses RPC. All other IDs resolve the original cap.
      partitionBindings[namespace]={idFromString:(value:string)=>native.idFromString(value),
        get:(selected:DurableObjectId)=>selected.toString()===id?localOwner:native.get(selected)} as unknown as DurableObjectNamespace<FreshNativeOwner>;
    }
    const disposition = new FreshNativePartitionDisposition({ ...config, namespace, id,
      deadlineMs: performance.now() + config.bounds.milliseconds, source: trusted.source() },
    ctx.storage, domain, trusted.coverage, partitionBindings, ledger, envelope);
    const maintenance = new PartitionMaintenance(ctx.storage, disposition.verify, Date.now, disposition.reconcile);
    const worker = new OrdinaryPartitionWorker(ctx, { ...env, FGA_PARTITION_MAINTENANCE: () => maintenance });
    async function reconcileNative(token:PartitionCapture){
      const use=envelope.header.mode==='evidence-use'&&envelope.reference.operation==='partition-reconcile'
        ?{configuration:config,trusted,ledger,envelope}:await evidenceUseFactory('partition-reconcile');
      assertEvidenceUse(use as Awaited<ReturnType<typeof loadEvidenceUse>>,'partition-reconcile',config);
      const c=use.configuration,useDomain=new NativeD1DomainReader(env.DB,c.bounds,c.domainControl,c.domainPlan),
        reconciler=new FreshNativePartitionDisposition({...c,namespace,id,deadlineMs:performance.now()+c.bounds.milliseconds,
          source:use.trusted.source()},ctx.storage,useDomain,use.trusted.coverage,partitionBindings,use.ledger,use.envelope,true),
        bridge=new PartitionMaintenance(ctx.storage,reconciler.verify,Date.now,reconciler.reconcile);
      await bridge.reconcile(token,env.DB);
      await use.ledger.finishEvidenceUse(use.envelope);use.trusted.assertConfiguration(c);
    }
    return Object.freeze({ worker, maintenance, disposition, reconcileNative });
  }
  return Object.freeze({ handler, maintenance: candidate.maintenance, observer, domain, partition });
}
