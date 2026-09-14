// Private test infrastructure: Private service binding only, with fixed native bindings and no public secret route.
import {WorkerEntrypoint} from "cloudflare:workers";
class NativeSecret extends WorkerEntrypoint {
 async get(){throw new Error("missing_native_binding");}
 async fetch(request){
  if(request.method!=="GET"||new URL(request.url).pathname!=="/read")return new Response(null,{status:404});
  return new Response(await this.get(),{headers:{"Content-Type":"text/plain; charset=utf-8","Cache-Control":"no-store"}});
 }
}

export class Grant extends NativeSecret {get(){return this.env.GRANT.get();}}
export class Temp0 extends NativeSecret {get(){return this.env.TEMP_0.get();}}
export class Temp1 extends NativeSecret {get(){return this.env.TEMP_1.get();}}
export class Temp2 extends NativeSecret {get(){return this.env.TEMP_2.get();}}
export class Temp3 extends NativeSecret {get(){return this.env.TEMP_3.get();}}
export class Temp4 extends NativeSecret {get(){return this.env.TEMP_4.get();}}
export class Writer extends NativeSecret {get(){return this.env.WRITER.get();}}
export default {fetch(){return new Response(null,{status:404});}};
