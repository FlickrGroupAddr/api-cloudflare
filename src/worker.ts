import { authenticate, d1Lookup, errorResponse, jsonCurrent } from "./installations.ts";
import { ROUTES } from "./registry.ts";
export interface Env { DB: D1Database; ASSETS?: Fetcher; FGA_READ_ENABLED?: string; }
// Same request-target policy proved by probes/routes; duplicated here to keep production imports out of probes.
export function safePath(raw: string): string | null {
  if (/[\\\x00-\x20\x7f]/.test(raw) || /%(?![0-9a-f]{2})/i.test(raw)) return null;
  const path = new URL(raw).pathname;
  if (/%(?:2f|5c|25|0[0-9a-f]|1[0-9a-f]|7f)/i.test(path)) return null;
  try { decodeURIComponent(path); } catch { return null; }
  return path;
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const path = safePath(request.url);
    if (path === null) return errorResponse(400,"invalid_request","Invalid request target.");
    const route = ROUTES.find(r => r.pathPattern === path);
    if (route) {
      if (request.method !== route.method) {
        const reply=errorResponse(405,"method_not_allowed","Method not allowed."); reply.headers.set("Allow",route.method); return reply;
      }
      if (env.FGA_READ_ENABLED !== "1") return errorResponse(503,"service_unavailable","Service unavailable.");
      const result=await authenticate(request,d1Lookup(env.DB),route.allowPending);
      return result instanceof Response ? result : jsonCurrent(result);
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
} satisfies ExportedHandler<Env>;
