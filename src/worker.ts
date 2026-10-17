import {uploadCandidatesRequest} from "./upload_candidates.ts";
import {publishServiceRequest} from "./publish_services.ts";
import {budgetedFlickrFetch} from "./flickr_rate.ts";
import {groupsRequest,refreshGroups} from "./group_discovery.ts";
import {existingPhotosRequest} from "./existing_photo_discovery.ts";
import {photoThumbnailRequest} from "./photo_thumbnails.ts";
import {photoMembershipsRequest} from "./photo_memberships.ts";
import {uploadAuthorizationRequest} from "./upload_authorization.ts";
import {uploadPhotoBindingRequest} from "./upload_photo_binding.ts";
import {uploadAmbiguityResolutionRequest} from "./upload_ambiguity_resolution.ts";
import {readSubmissionStatus,statusFailure,cleanupStatusReads} from "./submission_status.ts";
import {expirePluginCodeCandidates} from "./plugin_codes.ts";
// Module exports permit adapter-boundary tests of this exact optimized artifact; no new routes.
export {PartitionWorker,consumePartition} from "./dispatch_worker.ts";
import {createAdmin,maintainNativeCredentials,type AdminEnv} from "./admin_api.ts";
import {refreshGoogleKeys} from "./google_identity.ts";
import {cleanupAuthentication} from "./auth_admission.ts";
import { authenticate, credentialDigest, d1Lookup, errorResponse, jsonCurrent } from "./installations.ts";
import { ROUTES } from "./registry.ts";
export {ROUTES};
import {batchRequest,bindingRequest,configured,jsonBody,publishNativeHint,type IntakeEnv} from "./intake_api.ts";
import {duePartitions} from "./scheduling.ts";
export interface Env extends IntakeEnv,AdminEnv { FGA_UPLOAD_CANDIDATES_ENABLED?:string; FGA_PUBLISH_SERVICE_ENABLED?:string; ASSETS?: Fetcher; FGA_READ_ENABLED?: string; FGA_DISPATCH_ENABLED?:string; FGA_GROUPS_ENABLED?:string; FGA_EXISTING_PHOTOS_ENABLED?:string; FGA_PHOTO_THUMBNAILS_ENABLED?:string; FGA_UPLOAD_AUTHORIZATION_ENABLED?:string; FGA_UPLOAD_PHOTO_BINDING_ENABLED?:string; FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED?:string; }
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
    const providerFetch=budgetedFlickrFetch(env.DB,flickrFetch);
    const path = safePath(request.url);
    if (path === null) return errorResponse(400,"invalid_request","Invalid request target.");
    if(path==="/admin/login"||path==="/admin/google-login"||path==="/admin/flickr-oauth/callback")return createAdmin(providerFetch).fetch(request,env);
    const candidates=ROUTES.filter(route=>{
      const pattern=route.pathPattern.split("/").map(part=>part.startsWith("{")?"[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}":part).join("/");
      const routePath=route.handler==="photo_thumbnail"?decodeURIComponent(path):path;
      return new RegExp("^"+pattern+"$").test(routePath);
    });
    const route=candidates.find(route=>route.method===request.method)??candidates[0];
    if (route) {
      const routeReply=(response:Response):Response=>{
        if(route.handler==="upload_candidates")response.headers.set("Cache-Control","private, no-store");
        if((route.handler==="publish_service_create"||route.handler==="publish_service_read")&&response.status===503)response.headers.set("Retry-After","5");
        return response;
      };
      if (request.method !== route.method) {
        const reply=errorResponse(405,"method_not_allowed","Method not allowed."); reply.headers.set("Allow",[...new Set(candidates.map(r=>r.method))].sort().join(", ")); return routeReply(reply);
      }
      if(route.handler==="admin"||route.handler==="plugin_code"||route.handler==="status_admin")return createAdmin(providerFetch).fetch(request,env);
      const photosEnabled=env.FGA_READ_ENABLED==="1"&&env.FGA_EXISTING_PHOTOS_ENABLED==="1";
      const enabled=route.handler==="upload_candidates" ? env.FGA_UPLOAD_CANDIDATES_ENABLED==="1" :
        (route.handler==="publish_service_create"||route.handler==="publish_service_read") ? env.FGA_PUBLISH_SERVICE_ENABLED==="1" :
        route.handler==="groups" ? env.FGA_READ_ENABLED==="1"&&env.FGA_GROUPS_ENABLED==="1" :
        route.handler==="photo_thumbnail" ? photosEnabled&&env.FGA_PHOTO_THUMBNAILS_ENABLED==="1" :
        route.handler==="upload_authorization" ? env.FGA_UPLOAD_AUTHORIZATION_ENABLED==="1" :
        route.handler==="upload_photo_binding" ? env.FGA_UPLOAD_PHOTO_BINDING_ENABLED==="1" :
        route.handler==="upload_ambiguity_resolution" ? env.FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED==="1" :
        (route.handler==="existing_photos"||route.handler==="photo_memberships") ? photosEnabled :
        (route.handler==="current"||route.handler==="status") ? env.FGA_READ_ENABLED==="1" :
        route.handler==="binding" ? photosEnabled||configured(env) : configured(env);
      if(!enabled)return routeReply(errorResponse(503,"service_unavailable","Service unavailable."));
      const result=await authenticate(request,d1Lookup(env.DB),route.allowPending,undefined,(route.handler==="current"||route.handler==="publish_service_read")?"empty":["status","groups","existing_photos","photo_memberships","photo_thumbnail","upload_candidates"].includes(route.handler)?"query":"json");
      if(result instanceof Response)return routeReply(result);
      if(route.handler==="current")return jsonCurrent(result);
      if(route.handler==="publish_service_create"||route.handler==="publish_service_read")return publishServiceRequest(env,
        {installationId:result.installationId,credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))},
        request,route.handler==="publish_service_read"?path.split("/")[4]!:undefined);
      if(route.handler==="upload_candidates")return uploadCandidatesRequest(env,
        {installationId:result.installationId,credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))},
        path.split("/")[4]!,new URL(request.url),providerFetch);
      if(route.handler==="photo_thumbnail")return photoThumbnailRequest(env.DB,{installationId:result.installationId,
        credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))},decodeURIComponent(path.split("/")[4]!),new URL(request.url),env,providerFetch,flickrFetch,request.signal);
      if(route.handler==="groups")return groupsRequest(env.DB,{installationId:result.installationId,
        credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))},new URL(request.url));
      if(route.handler==="existing_photos"||route.handler==="photo_memberships"){
        const auth={installationId:result.installationId,credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))};
        return route.handler==="existing_photos" ? existingPhotosRequest(env.DB,auth,new URL(request.url),env,providerFetch) :
          photoMembershipsRequest(env.DB,auth,path.split("/")[4]!,new URL(request.url),env,providerFetch);
      }
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
      if(route.handler==="upload_authorization")return uploadAuthorizationRequest(env,auth,value);
      if(route.handler==="upload_photo_binding")return uploadPhotoBindingRequest(env,auth,path.split("/")[4]!,value,providerFetch);
      if(route.handler==="upload_ambiguity_resolution")return uploadAmbiguityResolutionRequest(env,auth,path.split("/")[4]!,value,providerFetch);
      return route.handler==="batch"?batchRequest(env,auth,value,hint=>publishNativeHint(env,hint)):bindingRequest(env,auth,value,providerFetch);
    }
    if(path==="/admin/"||path==="/admin/google-client.json"||path==="/admin/signed-out")return createAdmin(providerFetch).fetch(request,env);
    if(["/admin/connection-polling.mjs","/admin/login-complete.mjs","/admin/app.mjs","/admin/model.mjs","/admin/styles.css","/admin/plugin-codes-ui.mjs","/admin/plugin-code-transfer.mjs","/admin/submission-status-ui.mjs","/admin/submission-status-model.mjs"].includes(path)&&request.method==="GET"&&env.FGA_ADMIN_ENABLED==="1"&&env.ASSETS){const response=await env.ASSETS.fetch(new Request(new URL(path,request.url)));const headers=new Headers(response.headers);headers.set("Cache-Control","no-store");headers.set("X-Content-Type-Options","nosniff");return new Response(response.body,{status:response.status,headers});}
    // No API, health, unknown path, or method falls back to an asset shell.
    return errorResponse(404,"not_found","Resource not found.");
  },
  async scheduled(_event:ScheduledController,env:Env):Promise<void> {
    const providerFetch=budgetedFlickrFetch(env.DB,flickrFetch);
    const maintenance:Array<()=>Promise<unknown>>=[];
    if(env.FGA_READ_ENABLED==="1"||env.FGA_ADMIN_ENABLED==="1")maintenance.push(()=>cleanupStatusReads(env.DB));
    if(env.FGA_ADMIN_ENABLED==="1")maintenance.push(()=>refreshGoogleKeys(env.DB,providerFetch),()=>cleanupAuthentication(env.DB),()=>expirePluginCodeCandidates(env.DB),()=>maintainNativeCredentials(env,providerFetch));
    for(const job of maintenance){try{await job();}catch{console.warn("fga_maintenance_unavailable");}}

    if(env.FGA_READ_ENABLED==="1"&&env.FGA_GROUPS_ENABLED==="1"){
      try{await refreshGroups(env.DB,env,providerFetch);}catch{console.warn("fga_group_refresh_unavailable");}
    }

    if(env.FGA_DISPATCH_ENABLED!=="1"||!env.COORD)return;
    for(const hint of await duePartitions(env.DB)){try{await publishNativeHint(env,hint,"sweep");}catch{/* Durable due work remains authoritative. */}}
  },
} satisfies ExportedHandler<Env>;}
export default createWorker();
