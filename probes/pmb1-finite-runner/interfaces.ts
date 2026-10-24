// MIT License; copyright 2026 Terry Ott.
// Exact inherited SDK signatures. native_composition.ts supplies the concrete
// fixed SOURCE harness; actual dispatch stays disabled in both language layers.
import type {PrivateMainRuntime} from '../pmb1-fresh-native-capture/main-private-core.ts';
import type {PartitionWorker} from '../pmb1-fresh-native-capture/owning-partition.ts';
import type {createFreshNativeSource} from '../pmb1-fresh-native-capture/source.ts';
import type {publishReviewedEvidence} from '../pmb1-runtime-evidence/operator.ts';
import type {preparePublication, publicationReadback} from '../pmb1-runtime-evidence/publication-plan.ts';
import type {RuntimeEvidenceLedger} from '../pmb1-runtime-evidence/ledger.ts';
import type {SupportedSource, ReadSession} from '../pmb1-no-real-object-reader/reader.ts';

export type MainPrivatePort = Pick<PrivateMainRuntime,
  'currentMain' | 'stopAdmission' | 'assessStopped'>;
export type OwningPartitionPort = Pick<PartitionWorker,
  'maintenanceStop' | 'maintenanceClose' | 'maintenanceReconcile' | 'maintenanceReopen' |
  'acquireFresh'>;
export type EvidenceOperatorPort = typeof publishReviewedEvidence;
export type PublicationPreparationPort = typeof preparePublication;
export type PublicationReadbackPort = typeof publicationReadback;
export type FreshNativeSourcePort = typeof createFreshNativeSource;
export type ProtectedLedgerPort = RuntimeEvidenceLedger;
export type CompleteObjectSourcePort = SupportedSource;
export type IncludedObjectObservationPort = ReadSession;

/** Real call trees, not a single synthetic "maintain/upload/deploy" endpoint.
 * Each native RPC plus every nested D1 query/batch, payload read, consume,
 * terminal/final check and SQL/KV/alarm observation needs its own reserved leaf.
 * Allocation/evidence-use/raw scopes remain separate. These type aliases do not
 * turn a native method into one HTTP/SQL/effect allowance. The actual trace and
 * wire/effect measurement origin must qualify separately before execution.
 */
export interface InheritedSourcePorts {
  main: MainPrivatePort;
  partitions: ReadonlyMap<string, OwningPartitionPort>;
  publication: EvidenceOperatorPort;
  preparation: PublicationPreparationPort;
  readback: PublicationReadbackPort;
  freshSource: FreshNativeSourcePort;
  ledger: ProtectedLedgerPort;
  completeSource: CompleteObjectSourcePort;
}

// Provider upload/deployment/retained restoration, ordinary closed GET and
// resource deletion are separate operator HTTP calls. No implementation or
// aggregate endpoint is supplied by these native SDK types. The finite packet
// must select their actual existing transport, method, route, target/version,
// response/wire accounting, grants and independently retained artifact first.
export const actualDispatchEnabled = false as const;
