// MIT License; copyright 2026 Terry Ott.
import {WorkerEntrypoint} from 'cloudflare:workers';
import {PrivateMainRuntime,type PrivateMainTarget} from './main-private-core.ts';
import {qualifiedRuntimeAuthority,type EvidencePurpose} from './authority.ts';
import type {FreshRetainedEnvironment} from '../pmb1-retained-integration/fresh_composition.ts';
/** Same Worker resource, named PRIVATE native RPC entrypoint. No HTTP handler,
 * secret, new service, bootstrap or automatic control invocation is introduced. */
export class PrivateMainMaintenance extends WorkerEntrypoint<FreshRetainedEnvironment>{
 protected runtimeAuthority(purpose:EvidencePurpose){return qualifiedRuntimeAuthority(this.env,purpose);}
 private runtime(){return new PrivateMainRuntime(this.env,purpose=>this.runtimeAuthority(purpose));}
 async currentMain(domainDatabaseId:string,operationId:string){return this.runtime().currentMain(domainDatabaseId,operationId);}
 async stopAdmission(target:PrivateMainTarget,operationId:string){return this.runtime().stopAdmission(target,operationId);}
 async assessStopped(target:PrivateMainTarget,operationId:string){return this.runtime().assessStopped(target,operationId);}
}
