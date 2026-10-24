// MIT License; copyright 2026 Terry Ott.
// Same-context ordinary/control/snapshot delegation. No RPC carries capabilities,
// callbacks, SQL or asserted verifier truth.
import { PartitionMaintenance, type PartitionCapture } from '../../src/partition_maintenance.ts';
import { NativePartitionDisposition } from '../pmb1-native-disposition/partition.ts';
import { createFreshRetainedCandidate, type FreshRetainedEnvironment } from '../pmb1-retained-integration/fresh_composition.ts';
import { consumeRuntimeFacts } from '../pmb1-retained-integration/runtime_facts.ts';
import { acquireFreshNativeFacts } from './owner-core.ts';
import { NativeSourceRefused } from './source.ts';
import type { QualifiedRuntimeAuthority,EvidencePurpose } from './authority.ts';
import type { EvidenceReference } from '../pmb1-runtime-evidence/types.ts';
const fail=():never=>{throw new NativeSourceRefused('private_partition_control_refused');};
const generation=(v:unknown):v is string=>typeof v==='string'&&/^[1-9][0-9]{0,18}$/.test(v)&&BigInt(v)<=9223372036854775807n;

/** The namespace's independently qualified holder/source policy is the native
 * capability boundary. The external operator control ledger authorizes each
 * exact operation and owns its unknown/replay accounting. operationId is only a
 * reference, never a grant. This class does not create that ledger or substitute
 * a raw-capture event for control authorization. */
export class OwningPartitionRuntime {
  readonly #ctx: DurableObjectState; readonly #env: FreshRetainedEnvironment;
  readonly #authority:(purpose?:EvidencePurpose)=>QualifiedRuntimeAuthority|undefined;
  readonly #controls=new Set<string>();
  #ordinary:Promise<ReturnType<ReturnType<typeof createFreshRetainedCandidate>['partition']>>|undefined;
  #local:PartitionMaintenance|undefined;
  constructor(ctx:DurableObjectState,env:FreshRetainedEnvironment,authority:(purpose?:EvidencePurpose)=>QualifiedRuntimeAuthority|undefined){
    this.#ctx=ctx;this.#env=env;this.#authority=authority;
  }
  private authority(purpose:EvidencePurpose='raw-capture'){const a=this.#authority(purpose);if(!a||!/^[a-f0-9]{64}$/.test(this.#ctx.id.toString()))fail();return a!;}
  private control(operationId:string,expected:string){
    this.authority();
    if(!/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(operationId)||!generation(expected)||this.#controls.has(operationId))fail();
    this.#controls.add(operationId); // Unknown/lost ACK is never retried here.
  }
  private local(){
    const absent=new NativePartitionDisposition();
    return this.#local??=new PartitionMaintenance(this.#ctx.storage,absent.verify,Date.now,absent.reconcile);
  }
  private createRuntime(purpose:EvidencePurpose){
    return (async()=>{
      const authority=this.authority(purpose),facts=await consumeRuntimeFacts(authority);
      if(facts.partitionNamespace!==authority.namespace)fail();
      const runtime=createFreshRetainedCandidate(this.#env,facts.configuration,facts.trusted,authority.ledger,facts.envelope,
        async use=>consumeRuntimeFacts(this.authority(use)));
      // The owning object's snapshot port stays local for itself, preventing an
      // RPC-to-self dependency. Other objects use the exact qualified COORD cap.
      return runtime.partition(this.#ctx,authority.namespace,this.#ctx.id.toString(),{
        acquireFresh:(reference,pin)=>this.acquireFresh(reference,pin)});
    })();
  }
  private runtime(){return this.#ordinary??=this.createRuntime('raw-capture');}
  async acquireFresh(reference:EvidenceReference,pin:string){
    const authority=this.authority();
    // No local constructor or SQL/KV/alarm read precedes the D1 capture consume.
    return acquireFreshNativeFacts(authority,this.#ctx.storage,this.#ctx.id.toString(),reference,pin);
  }
  async snapshotFresh(reference:EvidenceReference,pin:string){return this.acquireFresh(reference,pin);}
  async maintenanceStop(expected:string,operationId:string){this.control(operationId,expected);await this.local().stop(expected);}
  async maintenanceClose(expected:string,operationId:string){this.control(operationId,expected);await this.local().close(expected);}
  async maintenanceReconcile(token:PartitionCapture,operationId:string){
    if(!token||!/^[a-f0-9-]{36}$/.test(token.id)||!['fetch','alarm'].includes(token.entry))fail();
    this.control(operationId,token.generation);
    await (await this.createRuntime('partition-reconcile')).reconcileNative(Object.freeze({...token}));
  }
  async maintenanceReopen(expected:string,operationId:string){
    this.control(operationId,expected);await (await this.runtime()).maintenance.reopen(expected);
  }
  async fetch(request:Request){return (await this.runtime()).worker.fetch(request);}
  async alarm(){return (await this.runtime()).worker.alarm();}
}
