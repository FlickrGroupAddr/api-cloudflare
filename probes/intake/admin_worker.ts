// LOCAL ONLY: wraps real routing with synthetic edge metadata and provider transport.
import {createWorker,type Env} from "../../src/worker.ts";
export default {fetch(request:Request,env:Env&{PEER:Fetcher}){Object.defineProperty(request,"cf",{value:{colo:"LOCAL"}});return createWorker(r=>env.PEER.fetch(r)).fetch(request,env);}};
