// MIT License; copyright 2026 Terry Ott.
// Fixed private native RPC caller. No HTTP/service/signing/provisioning surface.
import type { PartitionWorker } from './owning-partition.ts';
import type { PartitionCapture } from '../../src/partition_maintenance.ts';
export interface RetainedControlAllocation {
  operationId:string; namespace:string; objectId:string; generation:string;
  operation:'stop'|'close'|'reconcile'|'reopen'; capture?:PartitionCapture;
  fromMs:number; throughMs:number; calls:1;
  operatorLedgerRecord:string; independentSourceReviewRecord:string;
}
export class ControlOutcomeUnknown extends Error { constructor(){super('private_control_outcome_unknown');} }
/** TRUSTED outer operator/native-holder source boundary. Construct only AFTER
 * the already selected external operator ledger authorizes this exact operation
 * and records its reservation. Records identify that work; they cannot prove it.
 * No database/control envelope is introduced. The existing ledger must retain
 * outcome/unknown state across restart; this helper never grants/retries it.
 */
export class PrivatePartitionController {
  readonly #namespace:DurableObjectNamespace<PartitionWorker>;
  readonly #namespaceId:string;
  readonly #allocation:RetainedControlAllocation;#spent=false;
  constructor(namespace:DurableObjectNamespace<PartitionWorker>,qualifiedNamespaceId:string,allocation:RetainedControlAllocation){
    this.#namespace=namespace;this.#namespaceId=qualifiedNamespaceId;this.#allocation=structuredClone(allocation);
  }
  async run():Promise<void>{
    if(this.#spent)throw new ControlOutcomeUnknown();this.#spent=true;
    const a=this.#allocation,now=Date.now();
    if(!a||a.calls!==1||!/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(a.operationId)
      ||!/^[a-f0-9]{32}$/.test(a.namespace)||a.namespace!==this.#namespaceId||!/^[a-f0-9]{64}$/.test(a.objectId)
      ||!/^[1-9][0-9]{0,18}$/.test(a.generation)||BigInt(a.generation)>9223372036854775807n
      ||![a.operatorLedgerRecord,a.independentSourceReviewRecord].every(v=>typeof v==='string'&&/^[A-Za-z0-9._:/-]{1,256}$/.test(v))
      ||!Number.isSafeInteger(a.fromMs)||a.fromMs<0||!Number.isSafeInteger(a.throughMs)||a.fromMs>now||a.throughMs<=now
      ||a.throughMs-a.fromMs>600000||!['stop','close','reconcile','reopen'].includes(a.operation))throw new ControlOutcomeUnknown();
    if(a.operation==='reconcile'&&(!a.capture||Object.keys(a.capture).sort().join()!=='entry,generation,id'
      ||!/^[a-f0-9-]{36}$/.test(a.capture.id)||!['fetch','alarm'].includes(a.capture.entry)||a.capture.generation!==a.generation))throw new ControlOutcomeUnknown();
    // Capability resolution occurs only after the exact finite SOURCE allocation.
    const stub=this.#namespace.get(this.#namespace.idFromString(a.objectId));
    try{
      if(a.operation==='stop')await stub.maintenanceStop(a.generation,a.operationId);
      else if(a.operation==='close')await stub.maintenanceClose(a.generation,a.operationId);
      else if(a.operation==='reopen')await stub.maintenanceReopen(a.generation,a.operationId);
      else{
        if(!a.capture||a.capture.generation!==a.generation)throw new ControlOutcomeUnknown();
        await stub.maintenanceReconcile(a.capture,a.operationId);
      }
      if(Date.now()>=a.throughMs)throw new ControlOutcomeUnknown();
    }catch{throw new ControlOutcomeUnknown();}
  }
}
