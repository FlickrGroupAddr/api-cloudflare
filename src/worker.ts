import { authenticate, credentialDigest, d1Lookup, errorResponse, jsonCurrent } from "./installations.ts";
import { ROUTES } from "./registry.ts";
import {batchRequest,bindingRequest,configured,jsonBody,publishNativeHint,type IntakeEnv} from "./intake_api.ts";
import {duePartitions} from "./scheduling.ts";
export interface Env extends IntakeEnv { ASSETS?: Fetcher; FGA_READ_ENABLED?: string; }
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
    const route = ROUTES.find(r => r.pathPattern === path);
    if (route) {
      if (request.method !== route.method) {
        const reply=errorResponse(405,"method_not_allowed","Method not allowed."); reply.headers.set("Allow",route.method); return reply;
      }
      if (route.handler==="current" ? env.FGA_READ_ENABLED !== "1" : !configured(env)) return errorResponse(503,"service_unavailable","Service unavailable.");
      const result=await authenticate(request,d1Lookup(env.DB),route.allowPending,undefined,route.handler==="current"?"empty":"json");
      if(result instanceof Response)return result;
      if(route.handler==="current")return jsonCurrent(result);
      const value=await jsonBody(request);if(value instanceof Response)return value;
      const auth={installationId:result.installationId,credentialDigest:await credentialDigest(request.headers.get("Authorization")!.slice(7))};
      return route.handler==="batch"?batchRequest(env,auth,value,hint=>publishNativeHint(env,hint)):bindingRequest(env,auth,value,flickrFetch);
    }
    if (path === "/admin/" && ["GET","HEAD"].includes(request.method) && env.ASSETS) {
      const url=new URL(request.url); url.pathname="/admin/index.html"; url.search="";
      const asset=await env.ASSETS.fetch(new Request(url,{method:request.method}));
      if (asset.status===200) {
        const headers=new Headers(asset.headers); headers.set("Cache-Control","no-store");
        headers.set("Content-Security-Policy","default-src 'none'; frame-ancestors 'none'; base-uri 'none'");
        headers.set("Referrer-Policy","no-referrer"); headers.set("X-Content-Type-Options","nosniff");
        return new Response(asset.body,{status:200,headers});
      }
    }
    // No API, health, unknown path, or method falls back to an asset shell.
    return errorResponse(404,"not_found","Resource not found.");
  },
  async scheduled(_event:ScheduledController,env:Env):Promise<void> {
    if(!configured(env)||!env.COORD)return;
    for(const hint of await duePartitions(env.DB)){try{await publishNativeHint(env,hint);}catch{/* Durable due work remains authoritative. */}}
  },
} satisfies ExportedHandler<Env>;}
export default createWorker();
