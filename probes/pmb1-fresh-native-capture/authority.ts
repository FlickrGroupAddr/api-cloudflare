// MIT License; copyright 2026 Terry Ott.
import { RuntimeEvidenceLedger } from '../pmb1-runtime-evidence/ledger.ts';
import { sourceQualification, type NativeAuthorityQualification } from './qualification.ts';
import { NativeSourceRefused } from './source.ts';
import contract from '../pmb1-retained-integration/source-contract.json' with { type: 'json' };
export interface NativeAuthorityEnvironment {
  PMB1_MAIN_JOURNAL: D1Database;
  /** Provider native binding; actual semantics and attribution must qualify. */
  PMB1_VERSION_METADATA?: WorkerVersionMetadata;
}
export interface QualifiedRuntimeAuthority {
  ledger: RuntimeEvidenceLedger;
  operation: string;
  namespace: string;
  databaseId:string;sourceContext:string;immutableVersion:string;
}
export type EvidencePurpose = 'raw-capture' | 'main-assess' | 'partition-reconcile';
/** Protocol refusal ceilings are not a campaign grant. Protected reviewed
 * envelopes and the independent operator ledger allocate actual finite work. */
export const PROTOCOL_CEILINGS = Object.freeze({maxPayloadBytes:4194304,maxAcquiredBytes:33554432,
  maxDecodedBytes:16777216,maxNativeBytes:16777216,maxAggregateBytes:67108864,
  maxRequests:8,maxStatements:32,maxTotalRequests:68,maxTotalStatements:136});
/** Concrete native attribution path. SOURCE qualification anchors only the
 * publisher/provenance path, holder policy, exact journal and native getter.
 * Actual version ID plus compiled context constrain protected unique selection.
 * No own final digest/version, finite custody or capture attempt is compiled. */
export function createQualifiedRuntimeAuthority(env: NativeAuthorityEnvironment,
  qualification: NativeAuthorityQualification, purpose:EvidencePurpose='raw-capture'): QualifiedRuntimeAuthority {
  const q = structuredClone(qualification), metadata = env.PMB1_VERSION_METADATA;
  if (!q || !/^[a-f0-9]{32}$/.test(q.namespace) || !/^[A-Za-z0-9_-]{1,80}$/.test(q.operation)
    || !metadata || typeof metadata.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(metadata.id))
    throw new NativeSourceRefused('native_execution_attribution_unqualified');
  const ledger = RuntimeEvidenceLedger.fromNativeExecution(env.PMB1_MAIN_JOURNAL,
    {databaseId:q.channel.databaseId,sourceContext:contract.sourceContextSha2_256,immutableVersion:metadata.id},
    q.channel, PROTOCOL_CEILINGS);
  return Object.freeze({ledger,operation:purpose==='raw-capture'?q.operation:purpose,namespace:q.namespace,
    databaseId:q.channel.databaseId,sourceContext:contract.sourceContextSha2_256,immutableVersion:metadata.id});
}
export function qualifiedRuntimeAuthority(env: NativeAuthorityEnvironment,purpose:EvidencePurpose='raw-capture'): QualifiedRuntimeAuthority | undefined {
  const qualification = sourceQualification();
  return qualification ? createQualifiedRuntimeAuthority(env, qualification,purpose) : undefined;
}
