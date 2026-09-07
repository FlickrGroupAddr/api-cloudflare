import { ASSET_PREFIX, GUARDS, matches, ROUTES, SHELL_PATHS, validateRegistry } from "./registry.ts";

interface Env { ASSETS: Fetcher; ROUTING_PROOF: string }
const SECURITY = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'" };
const EXPIRE = "__Host-fga_admin=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; HttpOnly; SameSite=Strict";
validateRegistry();
export function safePath(rawUrl: string): string | null {
  // Validate before WHATWG parsing can erase backslashes/control characters.
  if (/[\\\x00-\x20\x7f]/.test(rawUrl) || /%(?![0-9a-f]{2})/i.test(rawUrl)) return null;
  const url = new URL(rawUrl);
  const path = url.pathname;
  // Reject nested escapes too: no second decoder may create a different owner.
  if (/%(?:2f|5c|25|0[0-9a-f]|1[0-9a-f]|7f)/i.test(path)) return null;
  try { decodeURIComponent(path); } catch { return null; }
  return path;
}
function json(status: number, error: string, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ error }), { status,
    headers: { ...SECURITY, "Content-Type": "application/json", ...extra } });
}
async function dispatch(request: Request, env: Env): Promise<Response> {
  if (env.ROUTING_PROOF !== "isolated-fixture") return json(503, "routing_proof_disabled");
  const pathname = safePath(request.url);
  if (pathname === null) return json(400, "invalid_request_target");
  const candidates = ROUTES.filter(r => matches(r.pathPattern, pathname));
  if (candidates.length) {
    const route = candidates.find(r => r.method === request.method);
    if (!route) return json(405, "method_not_allowed", { Allow: candidates.map(r => r.method).sort().join(", ") });
    switch (route.authBoundary) {
      case "bearer": return json(401, "unauthorized", { "WWW-Authenticate": "Bearer" });
      case "session": return json(401, "unauthorized");
      case "google": case "callback": return json(400, "invalid_request");
      case "login": return json(503, "not_implemented");
      case "logout":
        if (request.headers.get("Origin") !== new URL(request.url).origin) return json(403, "forbidden");
        return new Response(null, { status: 204, headers: { ...SECURITY, "Set-Cookie": EXPIRE } });
      case "health": return new Response('{"schemaVersion":1,"status":"ok"}', {
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
    }
  }
  if (GUARDS.some(g => g.match === "exact" ? pathname === g.path : pathname.startsWith(g.path))) {
    return json(404, "not_found");
  }
  const shell = SHELL_PATHS.some(p => p === pathname);
  const asset = pathname.startsWith(ASSET_PREFIX);
  if (shell || asset) {
    if (!["GET", "HEAD"].includes(request.method)) return json(405, "method_not_allowed", { Allow: "GET, HEAD" });
    const target = new URL(request.url);
    target.search = "";
    if (shell) target.pathname = "/admin/index.html";
    const reply = await env.ASSETS.fetch(new Request(target, { method: request.method }));
    if (reply.status !== 200) return json(404, "not_found");
    const headers = new Headers(reply.headers);
    for (const [name, value] of Object.entries(SECURITY)) headers.set(name, value);
    return new Response(reply.body, { status: reply.status, headers });
  }
  return json(404, "not_found");
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const reply = await dispatch(request, env);
    return request.method === "HEAD" ? new Response(null, { status: reply.status, headers: reply.headers }) : reply;
  },
} satisfies ExportedHandler<Env>;
