import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse } from './installations.ts';

export interface PublishServiceEnv { DB: SqlStore; FGA_PUBLISH_SERVICE_ENABLED?: string; }
const SECURITY = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
export const SERVICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const ID = { type: 'string', pattern: SERVICE_ID.source } as const;
export const PUBLISH_SERVICE_REQUEST_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion'], properties: { schemaVersion: { const: 1 } } } as const;
export const PUBLISH_SERVICE_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'fgaPublishServiceId', 'issuingInstallationId', 'linkedFlickrRevision', 'serviceRevision', 'linkStatus'],
  properties: { schemaVersion: { const: 1 }, fgaPublishServiceId: ID,
    issuingInstallationId: { type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' },
    linkedFlickrRevision: { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER },
    serviceRevision: { const: 1 }, linkStatus: { enum: ['ready', 'link_changed', 'link_unavailable'] } } } as const;
export const PUBLISH_SERVICE_ROUTES = [
  { id: 'publish_service_create', method: 'POST', pathPattern: '/api/v001/publish-services', owner: 'fga_api_backend',
    routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401, expectedChallenge: 'Bearer realm="fga-api"',
    handler: 'publish_service_create', auth: 'installation_bearer', allowPending: false,
    request: PUBLISH_SERVICE_REQUEST_SCHEMA, response: PUBLISH_SERVICE_RESPONSE_SCHEMA, successStatuses: [201] },
  { id: 'publish_service_read', method: 'GET', pathPattern: '/api/v001/publish-services/{fgaPublishServiceId}', owner: 'fga_api_backend',
    routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401, expectedChallenge: 'Bearer realm="fga-api"',
    handler: 'publish_service_read', auth: 'installation_bearer', allowPending: false,
    request: null, response: PUBLISH_SERVICE_RESPONSE_SCHEMA, successStatuses: [200] },
] as const;
export const PUBLISH_SERVICE_RELEASE_METADATA = { enabledFlag: 'FGA_PUBLISH_SERVICE_ENABLED', defaultValue: '0', hostQualified: false } as const;

const AUTH = `FROM installations i JOIN installation_credential_versions v
 ON v.version_id=i.current_version_id AND v.installation_id=i.installation_id
 WHERE i.installation_id=? AND v.credential_digest=? AND i.state='active'
 AND i.credential_class='lrc_plugin' AND v.state='current' AND v.expires_at_us IS NULL`;
const LINKS = `LEFT JOIN flickr_links l ON l.user_id=i.user_id
 LEFT JOIN flickr_native_credentials n ON n.user_id=i.user_id
 LEFT JOIN flickr_connection_state c ON c.user_id=i.user_id`;
const USABLE = `l.state='linked' AND l.link_revision BETWEEN 1 AND 9007199254740991
 AND n.link_revision=l.link_revision AND n.verified_owner_nsid=l.owner_nsid
 AND n.operation_id IS NULL AND n.verified_permission IN ('write','delete')
 AND c.state='linked' AND c.local_state='available' AND c.operation_id IS NULL
 AND c.verified_permission IN ('write','delete') AND c.external_removal=0`;
// An auth row remains present even for absent/foreign resources: existence is never disclosed.
const SNAPSHOT = `SELECT s.service_id fgaPublishServiceId,s.issuing_installation_id issuingInstallationId,
 s.link_revision linkedFlickrRevision,s.service_revision serviceRevision,
 CASE WHEN NOT COALESCE((${USABLE}),0) THEN 'link_unavailable'
 WHEN s.link_revision<>l.link_revision OR s.owner_nsid<>l.owner_nsid THEN 'link_changed' ELSE 'ready' END linkStatus
 ${AUTH.replace(' WHERE', ` LEFT JOIN publish_service_identities s ON s.user_id=i.user_id AND s.service_id=? ${LINKS} WHERE`)}`;
interface ServiceRow { fgaPublishServiceId: string | null; issuingInstallationId: string; linkedFlickrRevision: number;
  serviceRevision: number; linkStatus: string; }
function unavailable(): Response {
  const response = errorResponse(503, 'service_unavailable', 'Service unavailable.');
  response.headers.set('Retry-After', '5'); return response;
}
function success(row: ServiceRow, status: number): Response {
  if (!row.fgaPublishServiceId || !SERVICE_ID.test(row.fgaPublishServiceId)
    || !/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(row.issuingInstallationId)
    || !Number.isSafeInteger(row.linkedFlickrRevision) || row.linkedFlickrRevision < 1 || row.serviceRevision !== 1
    || !['ready', 'link_changed', 'link_unavailable'].includes(row.linkStatus)) throw new Error('integrity');
  return Response.json({ schemaVersion: 1, ...row }, { status, headers: { ...SECURITY,
    ...(status === 201 ? { Location: `/api/v001/publish-services/${row.fgaPublishServiceId}` } : {}) } });
}
async function createEnvelope(request: Request): Promise<boolean> {
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get('Content-Type') ?? '')
    || request.headers.has('Content-Encoding') && request.headers.get('Content-Encoding') !== 'identity'
    || request.headers.has('Content-Length') && !/^(?:0|[1-9][0-9]{0,3})$/.test(request.headers.get('Content-Length')!)) return false;
  if (Number(request.headers.get('Content-Length')) > 1024 || !request.body) return false;
  const reader = request.body.getReader(); const parts: Uint8Array[] = []; let size = 0;
  try {
    for (;;) { const { done, value } = await reader.read(); if (done) break;
      size += value.length; if (size > 1024) { await reader.cancel(); return false; } parts.push(value); }
    const bytes = new Uint8Array(size); let offset = 0; for (const part of parts) { bytes.set(part, offset); offset += part.length; }
    const raw = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
    // This one-field grammar rejects duplicates (including escaped duplicate keys) before JSON.parse.
    if (!/^\s*\{\s*"(?:[^"\\]|\\.)*"\s*:\s*-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\s*\}\s*$/s.test(raw)) return false;
    const value = JSON.parse(raw) as Record<string, unknown>;
    return Object.keys(value).length === 1 && value.schemaVersion === 1;
  } catch { return false; }
  finally { reader.releaseLock(); }
}

/** Caller independently authenticates first with allowPending=false and preserves the raw body. */
export async function publishServiceRequest(env: PublishServiceEnv, auth: AdmissionAuth, request: Request, id?: string): Promise<Response> {
  if (env.FGA_PUBLISH_SERVICE_ENABLED !== '1') return unavailable();
  const invalid = () => errorResponse(400, 'invalid_request', 'Invalid publish service request.');
  if (new URL(request.url).search || (id === undefined ? request.method !== 'POST' : request.method !== 'GET' || !SERVICE_ID.test(id)
    || request.body !== null || request.headers.has('Transfer-Encoding') || request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')) return invalid();
  if (id === undefined && !await createEnvelope(request)) return invalid();
  try {
    if (id !== undefined) {
      const row = await env.DB.prepare(SNAPSHOT).bind(id, auth.installationId, auth.credentialDigest).first<ServiceRow>();
      if (!row) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
      return row.fgaPublishServiceId ? success(row, 200) : errorResponse(404, 'publish_service_not_found', 'Publish service not found.');
    }
    const serviceId = crypto.randomUUID();
    const results = await env.DB.batch([
      env.DB.prepare(`INSERT INTO publish_service_identities(service_id,user_id,issuing_installation_id,link_revision,owner_nsid)
        SELECT ?,i.user_id,i.installation_id,l.link_revision,l.owner_nsid
        ${AUTH.replace(' WHERE', ` ${LINKS} WHERE`)} AND ${USABLE}`)
        .bind(serviceId, auth.installationId, auth.credentialDigest),
      env.DB.prepare(SNAPSHOT).bind(serviceId, auth.installationId, auth.credentialDigest),
    ]);
    const row = results[1].results[0] as unknown as ServiceRow | undefined;
    if (!row) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
    return row.fgaPublishServiceId ? success(row, 201) : errorResponse(409, 'flickr_link_unavailable', 'The Flickr connection is unavailable.');
  } catch { return unavailable(); }
}
