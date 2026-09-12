import type { CurrentInstallation } from "./registry.ts";
export const CREDENTIAL = /^[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){11}-[0-9A-HJKMNP-TV-Z]{3}[0G]$/;
export const NOW_US_SQL = "(CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)";
export interface CredentialRow {
  installation_id: unknown; credential_class: unknown; installation_state: unknown; revision: unknown;
  version_id: unknown; version_state: unknown; current_version_id: unknown; pending_version_id: unknown;
  expires_at_us: unknown; now_us: unknown; current_count: unknown; pending_count: unknown;
}
export type Lookup = (digest: string) => Promise<CredentialRow | null>;
export const LOOKUP_SQL = `SELECT i.installation_id,i.credential_class,i.state AS installation_state,
 CAST(i.revision AS TEXT) AS revision,v.version_id,v.state AS version_state,
 i.current_version_id,i.pending_version_id,CAST(v.expires_at_us AS TEXT) AS expires_at_us,
 CAST(${NOW_US_SQL} AS TEXT) AS now_us,
 (SELECT COUNT(*) FROM installation_credential_versions x WHERE x.installation_id=i.installation_id AND x.state='current') AS current_count,
 (SELECT COUNT(*) FROM installation_credential_versions x WHERE x.installation_id=i.installation_id AND x.state='pending_rotation') AS pending_count
 FROM installation_credential_versions v JOIN installations i ON i.installation_id=v.installation_id
 WHERE v.credential_digest=?`;
const SECURITY = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" };
export function errorResponse(status: number, code: string, message: string, bearer = false): Response {
  const headers: Record<string,string> = { ...SECURITY };
  if (bearer) headers["WWW-Authenticate"] = `Bearer realm="fga-api", error="${code}"`;
  return Response.json({ schemaVersion: 1, error: { code, message, retryable: status >= 500,
    correlationId: crypto.randomUUID() } }, { status, headers });
}
export function invalidToken(): Response { return errorResponse(401,"invalid_token","Invalid installation credential.",true); }
export function missingAuthentication(): Response {
  return new Response(null, { status: 401, headers: { ...SECURITY, "WWW-Authenticate": 'Bearer realm="fga-api"' } });
}
export async function credentialDigest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,"0")).join("");
}
export function representation(row: CredentialRow, allowPending: boolean,
  alert: () => void): CurrentInstallation | Response {
  const validStates = ["current","pending_rotation","replaced","revoked","expired_unactivated"];
  const decimal = (value: unknown): value is string => typeof value === "string" && /^(?:0|[1-9][0-9]*)$/.test(value);
  const integrity = typeof row.installation_id === "string" && row.installation_id.length > 0 &&
    row.credential_class === "lrc_plugin" && ["active","revoked"].includes(row.installation_state as string) &&
    decimal(row.revision) && BigInt(row.revision)>0n && BigInt(row.revision)<=BigInt(Number.MAX_SAFE_INTEGER) &&
    typeof row.version_id === "string" && validStates.includes(row.version_state as string) &&
    decimal(row.now_us) && (row.expires_at_us === null || decimal(row.expires_at_us));
  if (!integrity) { alert(); return invalidToken(); }
  if (row.installation_state !== "active" || !["current","pending_rotation"].includes(row.version_state as string)) return invalidToken();
  if (row.current_count !== 1 || ![0,1].includes(row.pending_count as number) ||
      typeof row.current_version_id !== "string" || row.current_version_id.length === 0 ||
      (row.pending_count === 0 ? row.pending_version_id !== null : typeof row.pending_version_id !== "string" || row.pending_version_id.length === 0) ||
      (row.version_state === "current" && (row.current_version_id !== row.version_id || row.expires_at_us !== null)) ||
      (row.version_state === "pending_rotation" && (row.pending_version_id !== row.version_id || row.expires_at_us === null))) {
    alert(); return invalidToken();
  }
  if (row.expires_at_us !== null && BigInt(row.expires_at_us as string) <= BigInt(row.now_us as string)) return invalidToken();
  if (row.version_state === "pending_rotation" && !allowPending) {
    return errorResponse(403,"insufficient_scope","Credential does not authorize this operation.",true);
  }
  return { schemaVersion: 1, installationId: row.installation_id as string,
    installationRevision: Number(row.revision), installationState: "active",
    presentedCredentialState: row.version_state as "current" | "pending_rotation" };
}
export async function authenticate(request: Request, lookup: Lookup, allowPending: boolean,
  alert: () => void = () => console.warn("fga_installation_integrity_failure"),
  envelope: "empty" | "json" = "empty"): Promise<CurrentInstallation | Response> {
  const url = new URL(request.url);
  const auth = request.headers.get("Authorization");
  if (url.search || (envelope === "empty" && (request.body !== null ||
      (request.headers.has("Content-Length") && request.headers.get("Content-Length") !== "0") ||
      request.headers.has("Transfer-Encoding"))) || auth?.includes(",")) {
    return errorResponse(400,"invalid_request","Invalid authentication request.",true);
  }
  if (auth === null || !/^Bearer(?: |$)/i.test(auth)) return missingAuthentication();
  if (!/^Bearer /i.test(auth)) return errorResponse(400,"invalid_request","Invalid authentication request.",true);
  const value = auth.slice(7);
  if (!CREDENTIAL.test(value)) return invalidToken();
  try {
    const row = await lookup(await credentialDigest(value));
    return row ? representation(row,allowPending,alert) : invalidToken();
  } catch { return errorResponse(503,"service_unavailable","Service unavailable."); }
}
export function d1Lookup(db: D1Database): Lookup {
  return digest => db.prepare(LOOKUP_SQL).bind(digest).first<CredentialRow>();
}
export function jsonCurrent(value: CurrentInstallation): Response { return Response.json(value,{headers:SECURITY}); }
