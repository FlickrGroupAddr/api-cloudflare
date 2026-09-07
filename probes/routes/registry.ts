// Routing proof only: registrations bind real dispatch to safe fixture handlers.
export type Method = "GET" | "HEAD" | "POST";
export type Handler = "bearer" | "session" | "google" | "callback" | "login" | "logout" | "health";
export interface Route {
  id: string;
  method: Method;
  pathPattern: string;
  owner: "fga_api_backend" | "fga_oauth_handler";
  routingClass: "worker_first";
  authBoundary: Handler;
  probe: string;
  expectedStatus: number;
}
function route(id: string, method: Method, pathPattern: string, authBoundary: Handler): Route {
  const statuses = { bearer: 401, session: 401, google: 400, callback: 400, login: 503, logout: 204, health: 200 };
  return { id, method, pathPattern, owner: authBoundary === "callback" ? "fga_oauth_handler" : "fga_api_backend",
    routingClass: "worker_first", authBoundary, probe: `${id}_safe`, expectedStatus: statuses[authBoundary] };
}
export const ROUTES: readonly Route[] = [
  route("installation_current", "GET", "/api/v001/installations/current", "bearer"),
  route("groups", "GET", "/api/v001/groups", "bearer"),
  route("existing_photos", "GET", "/api/v001/existing-public-photos", "bearer"),
  route("existing_bindings", "POST", "/api/v001/existing-public-photo-bindings", "bearer"),
  route("memberships", "GET", "/api/v001/photo-bindings/{binding_id}/group-memberships", "bearer"),
  route("upload_authorizations", "POST", "/api/v001/upload-authorizations", "bearer"),
  route("batch_admission", "POST", "/api/v001/group-submission-batches", "bearer"),
  route("intents", "GET", "/api/v001/group-submission-intents", "bearer"),
  route("intent", "GET", "/api/v001/group-submission-intents/{intent_id}", "bearer"),
  route("admin_session", "GET", "/api/v001/admin/session", "session"),
  route("admin_logout", "POST", "/api/v001/admin/session/logout", "logout"),
  route("admin_reauthentication", "POST", "/api/v001/admin/session/reauthentication", "session"),
  route("admin_deployment", "GET", "/api/v001/admin/deployment", "session"),
  route("admin_intents", "GET", "/api/v001/admin/group-submission-intents", "session"),
  route("login_start", "GET", "/admin/login", "login"),
  route("google_login", "POST", "/admin/google-login", "google"),
  route("flickr_callback", "GET", "/admin/flickr-oauth/callback", "callback"),
  route("startup_get", "GET", "/healthz/startup", "health"),
  route("startup_head", "HEAD", "/healthz/startup", "health"),
  route("live_get", "GET", "/healthz/live", "health"),
  route("live_head", "HEAD", "/healthz/live", "health"),
];
export const GUARDS = [{ path: "/api", match: "exact" }, { path: "/api/", match: "prefix" },
  { path: "/healthz/", match: "prefix" }] as const;
export const SHELL_PATHS = ["/admin/"] as const;
export const ASSET_PREFIX = "/admin/assets/";
export const ASSET_CONFIG = { binding: "ASSETS", run_worker_first: true,
  html_handling: "none", not_found_handling: "none" } as const;
export function matches(pattern: string, pathname: string): boolean {
  const parts = pattern.split("/");
  const actual = pathname.split("/");
  return parts.length === actual.length && parts.every((part, i) =>
    /^\{[a-z_]+\}$/.test(part) ? actual[i].length > 0 : part === actual[i]);
}
export function validateRegistry(routes: readonly Route[] = ROUTES): void {
  const ids = new Set<string>(), tuples = new Set<string>();
  for (const r of routes) {
    const key = r.method + " " + r.pathPattern.replace(/\{[^}]+\}/g, "{}");
    if (ids.has(r.id) || tuples.has(key) || !r.probe || !r.owner ||
        r.routingClass !== "worker_first" || !["GET", "HEAD", "POST"].includes(r.method) ||
        !/^\/(?:api\/v001\/|admin\/|healthz\/)/.test(r.pathPattern) ||
        !["bearer", "session", "google", "callback", "login", "logout", "health"].includes(r.authBoundary)) {
      throw new Error("invalid_route_registry");
    }
    ids.add(r.id); tuples.add(key);
  }
}
