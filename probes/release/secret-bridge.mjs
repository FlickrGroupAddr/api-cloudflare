// Private test infrastructure: RPC only, with fixed native bindings and no public secret route.
import {WorkerEntrypoint} from "cloudflare:workers";
export class Grant extends WorkerEntrypoint {get(){return this.env.GRANT.get();}}
export class Temp0 extends WorkerEntrypoint {get(){return this.env.TEMP_0.get();}}
export class Temp1 extends WorkerEntrypoint {get(){return this.env.TEMP_1.get();}}
export class Temp2 extends WorkerEntrypoint {get(){return this.env.TEMP_2.get();}}
export class Temp3 extends WorkerEntrypoint {get(){return this.env.TEMP_3.get();}}
export class Temp4 extends WorkerEntrypoint {get(){return this.env.TEMP_4.get();}}
export class Writer extends WorkerEntrypoint {get(){return this.env.WRITER.get();}}
export default {fetch(){return new Response(null,{status:404});}};
