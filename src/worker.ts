import {readSubmissionStatus,statusFailure,cleanupStatusReads} from "./submission_status.ts";
import {expirePluginCodeCandidates} from "./plugin_codes.ts";
export {PartitionWorker} from "./dispatch_worker.ts";
import {createAdmin,maintainNativeCredentials,type AdminEnv} from "./admin_api.ts";
import {refreshGoogleKeys} from "./google_identity.ts";
import {cleanupAuthentication} from "./auth_admission.ts";
import { authenticate, credentialDigest, d1Lookup, errorResponse, jsonCurrent } from "./installations.ts";
import { ROUTES } from "./registry.ts";
import {batchRequest,bindingRequest,configured,jsonBody,publishNativeHint,type IntakeEnv} from "./intake_api.ts";
import {duePartitions} from "./scheduling.ts";
export interface Env extends IntakeEnv,AdminEnv { ASSETS?: Fetcher; FGA_READ_ENABLED?: string; FGA_DISPATCH_ENABLED?:string; }
// Same request-target policy proved by probes/routes; duplicated here to keep production imports out of probes.
export function safePath(raw: string): string | null {
  if (/[\\\x00-\x20\x7f]/.test(raw) || /%(?![0-9a-f]{2})/i.test(raw)) return null;
  const path = new URL(raw).pathname;
  if (/%(?:2f|5c|25|0[0-9a-f]|1[0-9a-f]|7f)/i.test(path)) return null;
  try { decodeURIComponent(path); } catch { return null; }
  return path;
}
import type {FlickrFetch} from "./flickr_reads.ts";
export function createWorker(flickrFetch:FlickrFetch=request=>fetch(request)) {return {
  async fetch(request: Request, env: Env): Promise<Response> {
    const path = safePath(request.url);
    if (path === null) return errorResponse(400,"invalid_request","Invalid request target.");
    if(path==="/admin/login"||path==="/admin/google-login"||path==="/admin/flickr-oauth/callback")return createAdmin(flickrFetch).fetch(request,env);
    const candidates=ROUTES.filter(route=>{
      const pattern=route.pathPattern.split("/").map(part=>part.startsWith("{")?"[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}":part).join("/");
      return new RegExp("^"+pattern+"$").test(path);
    });
    const route=candidates.find(route=>route.method===request.method)??candidates[0];
    if (route) {
      if (request.method !== route.method) {
        const reply=errorResponse(405,"method_not_allowed","Method not allowed."); reply.headers.set("Allow",[...new Set(candidates.map(r=>r.method))].sort().join(", ")); return reply;
      }
      if(route.handler==="admin"||route.handler==="plugin_code"||route.handler==="status_admin")return createAdmin(flickrFetch).fetch(request,env);
      if ((route.handler==="current"||route.handler==="status") ? env.FGA_READ_ENABLED !== "1" : !configured(env)) return errorResponse(503,"service_unavailable","Service unavailable.");
      const result=await authenticate(request,d1Lookup(env.DB),route.allowPending,undefined,route.handler==="current"?"empty":route.handler==="status"?"query":"json");
      if(result instanceof Response)return result;
      if(route.handler==="current")return jsonCurrent(result);
      if(route.handler==="status"){
        try{
          const owner=await env.DB.prepare("SELECT user_id userId FROM installations WHERE installation_id=?").bind(result.installationId).first<{userId:string}>();
          if(!owner)return errorResponse(401,"invalid_token","Invalid installation credential.",true);
          const body=await readSubmissionStatus(env.DB,{family:"installation",userId:owner.userId,subjectId:result.installationId,proof:await credentialDigest(request.headers.get("Authorization")!.slice(7))},new URL(request.url),route.pathPattern.includes("{")?path.split("/").at(-1):undefined);
          return Response.json(body,{headers:{"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"}});
        }catch(error){return statusFailure(error,true);}
      }
      const value=await jsonBody(request);if(value instanceof Response)return value;
      const auth={installationId:result.installationId,credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))};
      return route.handler==="batch"?batchRequest(env,auth,value,hint=>publishNativeHint(env,hint)):bindingRequest(env,auth,value,flickrFetch);
    }
    if(path==="/admin/"||path==="/admin/google-client.json"||path==="/admin/signed-out")return createAdmin(flickrFetch).fetch(request,env);
    if(["/admin/app.mjs","/admin/model.mjs","/admin/styles.css","/admin/plugin-codes-ui.mjs","/admin/plugin-code-transfer.mjs","/admin/submission-status-ui.mjs","/admin/submission-status-model.mjs"].includes(path)&&request.method==="GET"&&env.FGA_ADMIN_ENABLED==="1"&&env.ASSETS){const response=await env.ASSETS.fetch(new Request(new URL(path,request.url)));const headers=new Headers(response.headers);headers.set("Cache-Control","no-store");headers.set("X-Content-Type-Options","nosniff");return new Response(response.body,{status:response.status,headers});}
    // No API, health, unknown path, or method falls back to an asset shell.
    return errorResponse(404,"not_found","Resource not found.");
  },
  async scheduled(_event:ScheduledController,env:Env):Promise<void> {
    const maintenance:Array<()=>Promise<unknown>>=[];
    if(env.FGA_READ_ENABLED==="1"||env.FGA_ADMIN_ENABLED==="1")maintenance.push(()=>cleanupStatusReads(env.DB));
    if(env.FGA_ADMIN_ENABLED==="1")maintenance.push(()=>refreshGoogleKeys(env.DB,flickrFetch),()=>cleanupAuthentication(env.DB),()=>expirePluginCodeCandidates(env.DB),()=>maintainNativeCredentials(env,flickrFetch));
    for(const job of maintenance){try{await job();}catch{console.warn("fga_maintenance_unavailable");}}

    if(!configured(env)||!env.COORD)return;
    for(const hint of await duePartitions(env.DB)){try{await publishNativeHint(env,hint,"sweep");}catch{/* Durable due work remains authoritative. */}}
  },
} satisfies ExportedHandler<Env>;}
export default createWorker();
