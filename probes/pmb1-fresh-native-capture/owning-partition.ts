// MIT License; copyright 2026 Terry Ott.
import { DurableObject } from 'cloudflare:workers';
import { OwningPartitionRuntime } from './owning-core.ts';
import { qualifiedRuntimeAuthority, type QualifiedRuntimeAuthority,type EvidencePurpose } from './authority.ts';
import type { FreshRetainedEnvironment } from '../pmb1-retained-integration/fresh_composition.ts';
import type { EvidenceReference } from '../pmb1-runtime-evidence/types.ts';
import type { PartitionCapture } from '../../src/partition_maintenance.ts';

/** Existing owning namespace/class revision. Construction acquires no storage.
 * All methods delegate to one core carrying this exact native ctx/storage. */
export class PartitionWorker extends DurableObject<FreshRetainedEnvironment> {
  readonly #runtime:OwningPartitionRuntime;
  constructor(ctx:DurableObjectState,env:FreshRetainedEnvironment){
    super(ctx,env);this.#runtime=new OwningPartitionRuntime(ctx,env,purpose=>this.runtimeAuthority(purpose));
  }
  protected runtimeAuthority(purpose:EvidencePurpose='raw-capture'):QualifiedRuntimeAuthority|undefined{return qualifiedRuntimeAuthority(this.env,purpose);}
  async acquireFresh(reference:EvidenceReference,pin:string){return this.#runtime.acquireFresh(reference,pin);}
  async snapshotFresh(reference:EvidenceReference,pin:string){return this.#runtime.snapshotFresh(reference,pin);}
  async maintenanceStop(expected:string,operationId:string){return this.#runtime.maintenanceStop(expected,operationId);}
  async maintenanceClose(expected:string,operationId:string){return this.#runtime.maintenanceClose(expected,operationId);}
  async maintenanceReconcile(token:PartitionCapture,operationId:string){return this.#runtime.maintenanceReconcile(token,operationId);}
  async maintenanceReopen(expected:string,operationId:string){return this.#runtime.maintenanceReopen(expected,operationId);}
  async fetch(request:Request){return this.#runtime.fetch(request);}
  async alarm(){return this.#runtime.alarm();}
}
