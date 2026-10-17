import type { SqlStore } from './admission.ts';
import { SERVICE_ID } from './publish_services.ts';
import { ALBUM_BINDING_RESPONSE_SCHEMA, ALBUM_OBLIGATION_RESPONSE_SCHEMA, readStrictAlbumJson,
  parseStrictAlbumJson } from './album_bindings.ts';
import { readAlbumStatus, readAlbumObligationPage, readAlbumRepairPage, readAlbumRepairContext,
  assertAlbumRepairContext, prepareAlbumResolution, commitAlbumResolution,
  AlbumCreateRepairStoreError, type RepairAuth, type RepairContext, type ResolveRequest } from './album_create_repair_store.ts';
import type { AlbumRepairCandidatePage as CandidatePage, AlbumRepairSelectionProof as SelectionProof } from './album_create_repair_discovery.ts';

export interface AlbumCreateRepairEnv { DB: SqlStore; FGA_ALBUM_CREATE_REPAIR_ENABLED?: string; }
export interface AlbumCreateRepairDependencies {
  /** Explicit synthetic or qualified transport composition; no implicit network or credentials. */
  reader(context: RepairContext): {
    discover(page: number, pageSize: number): Promise<CandidatePage>;
    prove(selectedPhotosetId: string): Promise<SelectionProof>;
  };
}
const SECURITY = { 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
const UUID = { type: 'string', pattern: SERVICE_ID.source } as const;
const OPAQUE = { type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' } as const;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
const COUNT = { type: 'integer', minimum: 0, maximum: Number.MAX_SAFE_INTEGER } as const;
const PAGE = { type: 'integer', minimum: 1, maximum: 1000 } as const;
const SIZE = { type: 'integer', minimum: 1, maximum: 100 } as const;
const TIMESTAMP = { type: 'string', pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$' } as const;
const URL_SCHEMA = { type: 'string', minLength: 1, maxLength: 2048 } as const;
const LIFECYCLE = { enum: ['active', 'local_collection_removed_remote_preserved'] } as const;
const nullable = (schema: object) => ({ anyOf: [{ type: 'null' }, schema] });
const closed = (properties: Record<string, object>) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });
const array = (items: object, maxItems: number) => ({ type: 'array', items, maxItems });
const envelope = { schemaVersion: { const: 1 } };
export const ALBUM_CREATE_REPAIR_STATUS_SCHEMA = closed({ ...envelope, binding: ALBUM_BINDING_RESPONSE_SCHEMA,
  localLifecycle: LIFECYCLE, materialization: closed({ state: { enum: ['materialization_pending', 'create_rejected', 'create_outcome_unknown',
    'materialized', 'remote_album_missing_needs_attention', 'album_identity_conflict'] }, createAttemptId: nullable(UUID),
    repairSurface: { enum: ['none', 'plugin_or_admin', 'admin_only'] }, resolvedPhotosetId: nullable(OPAQUE),
    resolutionProvenance: nullable({ const: 'owner_reconciled_ambiguous_album_create' }) }),
  catalogRepair: closed({ flickrPhotosetId: nullable(OPAQUE), navigationUrl: nullable(URL_SCHEMA), identityVerifiedAt: nullable(TIMESTAMP) }),
  membershipCounts: closed({ waitingForAlbum: COUNT, attachmentPending: COUNT, membershipVerified: COUNT, reconciliationPending: COUNT, needsAttention: COUNT }) });
const OBLIGATION_STATUS = closed({ obligation: ALBUM_OBLIGATION_RESPONSE_SCHEMA,
  state: { enum: ['waiting_for_album', 'attachment_pending', 'membership_verified', 'membership_reconciliation_pending', 'album_attachment_needs_attention'] },
  membershipObservedAt: nullable(TIMESTAMP), localRelationship: { enum: ['active', 'archived'] } });
const PAGE_FIELDS = { ...envelope, page: PAGE, pageSize: SIZE, pages: COUNT, total: COUNT };
export const ALBUM_CREATE_REPAIR_OBLIGATION_PAGE_SCHEMA = closed({ ...PAGE_FIELDS, fgaAlbumBindingId: UUID,
  bindingRevision: REVISION, obligations: array(OBLIGATION_STATUS, 100) });
const CANDIDATE = closed({ flickrPhotosetId: OPAQUE, title: { type: 'string', maxLength: 4096 }, ownerNsid: OPAQUE,
  primaryPhotoId: OPAQUE, createdAt: nullable(TIMESTAMP), updatedAt: nullable(TIMESTAMP), navigationUrl: URL_SCHEMA,
  thumbnail: nullable(closed({ url: URL_SCHEMA })) });
export const ALBUM_CREATE_REPAIR_CANDIDATE_PAGE_SCHEMA = closed({ ...PAGE_FIELDS, pageSize: { ...SIZE, maximum: 20 },
  fgaAlbumBindingId: UUID, bindingRevision: REVISION, createAttemptId: UUID, observedAt: TIMESTAMP, candidates: array(CANDIDATE, 20) });
export const ALBUM_CREATE_REPAIR_RESOLVE_REQUEST_SCHEMA = closed({ ...envelope, expectedBindingRevision: REVISION,
  createAttemptId: UUID, selectedPhotosetId: OPAQUE });
const REPAIR_SUMMARY = closed({ fgaAlbumBindingId: UUID, bindingRevision: REVISION, fgaPublishServiceId: UUID,
  localCollectionIdentifier: OPAQUE, desiredTitle: ALBUM_BINDING_RESPONSE_SCHEMA.properties.desiredTitle,
  localLifecycle: LIFECYCLE, createAttemptId: UUID });
export const ALBUM_CREATE_REPAIR_REPAIR_PAGE_SCHEMA = closed({ ...PAGE_FIELDS, repairs: array(REPAIR_SUMMARY, 100) });
const ERRORS = {
  invalid_request: [400, 'Invalid album repair request.'], page_out_of_range: [400, 'Page is out of range.'],
  invalid_token: [401, 'Invalid installation credential.'], unauthorized: [401, 'Administrative session required.'],
  insufficient_scope: [403, 'Current installation credential required.'], forbidden: [403, 'Operation forbidden.'],
  resource_not_found: [404, 'Resource not found.'], stale_binding_revision: [409, 'Album binding revision changed.'],
  flickr_link_unavailable: [409, 'The Flickr connection is unavailable.'], administrative_repair_required: [409, 'Administrative repair required.'],
  create_repair_not_pending: [409, 'Album create repair is not pending.'], resolution_conflict: [409, 'Album resolution conflicts.'],
  selected_album_not_verified: [409, 'Selected album could not be verified.'], rate_limited: [429, 'Read capacity is unavailable.'],
  candidate_evidence_unavailable: [503, 'Candidate evidence is unavailable.'], resolution_evidence_unavailable: [503, 'Resolution evidence is unavailable.'],
  service_unavailable: [503, 'Service unavailable.'],
} as const;
export const ALBUM_CREATE_REPAIR_ERROR_SCHEMA = closed({ ...envelope, error: closed({ code: { enum: Object.keys(ERRORS) },
  message: { type: 'string', minLength: 1, maxLength: 256 }, retryable: { type: 'boolean' }, correlationId: UUID }) });
export const ALBUM_CREATE_REPAIR_RELEASE_METADATA = { enabledFlag: 'FGA_ALBUM_CREATE_REPAIR_ENABLED', defaultValue: '0', hostQualified: false } as const;

export function albumCreateRepairFailure(code: string, retryAfter = 5): Response {
  const safe = Object.hasOwn(ERRORS, code) ? code as keyof typeof ERRORS : 'service_unavailable';
  const [status, message] = ERRORS[safe];
  const headers: Record<string, string> = { ...SECURITY };
  if (safe === 'invalid_token' || safe === 'insufficient_scope') headers['WWW-Authenticate'] = `Bearer realm="fga-api", error="${safe}"`;
  if (status === 503 || status === 429) headers['Retry-After'] = status === 429 && Number.isSafeInteger(retryAfter) && retryAfter > 0 ? String(retryAfter) : '5';
  return Response.json({ schemaVersion: 1, error: { code: safe, message, retryable: status === 429 || status === 503,
    correlationId: crypto.randomUUID() } }, { status, headers });
}

// Small closed-schema validator also rejects malformed trusted dependency responses.
function valid(value: unknown, schema: any): boolean {
  if (schema.anyOf) return schema.anyOf.some((item: object) => valid(value, item));
  if (Object.hasOwn(schema, 'const') && value !== schema.const || schema.enum && !schema.enum.includes(value)) return false;
  if (!schema.type) return true;
  if (schema.type === 'null') return value === null;
  if (schema.type === 'integer') return typeof value === 'number' && Number.isSafeInteger(value) && value >= schema.minimum && value <= schema.maximum;
  if (schema.type === 'boolean') return typeof value === 'boolean';
  if (schema.type === 'string') return typeof value === 'string' && (!schema.pattern || new RegExp(schema.pattern).test(value))
    && (schema.minLength === undefined || [...value].length >= schema.minLength) && (schema.maxLength === undefined || [...value].length <= schema.maxLength);
  if (schema.type === 'array') return Array.isArray(value) && value.length <= schema.maxItems && value.every(item => valid(item, schema.items));
  if (schema.type === 'object') return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === schema.required.length && schema.required.every((key: string) => Object.hasOwn(value, key)
      && valid((value as Record<string, unknown>)[key], schema.properties[key]));
  return false;
}
function resolve(value: unknown): ResolveRequest {
  if (!valid(value, ALBUM_CREATE_REPAIR_RESOLVE_REQUEST_SCHEMA)) throw new Error('invalid_request');
  return value as ResolveRequest;
}
export function parseAlbumCreateRepairResolve(raw: string): ResolveRequest { return resolve(parseStrictAlbumJson(raw)); }
export function parseAlbumCreateRepairPage(url: URL, maxSize: number): { page: number; pageSize: number } {
  // Compare the raw query: URLSearchParams alone accepts percent/plus aliases.
  if (!/^\?(?:page=[1-9][0-9]*&page_size=[1-9][0-9]*|page_size=[1-9][0-9]*&page=[1-9][0-9]*)$/.test(url.search)) throw new Error('invalid_request');
  const page = Number(url.searchParams.get('page')), pageSize = Number(url.searchParams.get('page_size'));
  if (!Number.isSafeInteger(page) || page > 1000 || !Number.isSafeInteger(pageSize) || pageSize > maxSize) throw new Error('invalid_request');
  return { page, pageSize };
}
function noBody(request: Request): boolean {
  return request.body === null && !request.headers.has('Transfer-Encoding')
    && (!request.headers.has('Content-Length') || request.headers.get('Content-Length') === '0');
}
function text(value: string, bytes: number, empty = true): boolean {
  return (empty || value.length > 0) && !/[\p{Cc}\p{Cs}]/u.test(value) && new TextEncoder().encode(value).length <= bytes;
}
function timestamp(value: string): boolean {
  const date = new Date(value);
  return Number.isFinite(date.valueOf()) && date.toISOString().replace(/\.\d{3}Z$/, '') === value.slice(0, 19);
}
function nav(value: string, photosetId: string): boolean {
  try { const url = new URL(value); return text(value, 2048, false) && url.protocol === 'https:' && !url.username && !url.password && !url.hash
    && !url.port && ['www.flickr.com', 'flickr.com'].includes(url.hostname)
    && new RegExp(`^/photos/[^/]+/(?:albums|sets)/${photosetId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/?$`).test(url.pathname) && !url.search; } catch { return false; }
}
function responseBody(value: any, schema: object, bindingId: string | undefined, limit: number): Response {
  if (!valid(value, schema)) throw new Error('integrity');
  if (schema === ALBUM_CREATE_REPAIR_STATUS_SCHEMA) {
    const { binding: b, materialization: m, catalogRepair: c } = value;
    if (b.fgaAlbumBindingId !== bindingId || !text(b.desiredTitle, 4000, false)) throw new Error('integrity');
    if (m.state === 'materialized' && b.flickrPhotosetId === null || ['materialization_pending', 'create_rejected', 'create_outcome_unknown'].includes(m.state) && b.flickrPhotosetId !== null
      || m.state === 'create_outcome_unknown' && m.createAttemptId === null || (m.resolvedPhotosetId === null) !== (m.resolutionProvenance === null)
      || m.resolvedPhotosetId !== null && m.resolvedPhotosetId !== b.flickrPhotosetId || c.flickrPhotosetId !== b.flickrPhotosetId
      || (c.navigationUrl === null) !== (c.identityVerifiedAt === null) || c.navigationUrl !== null && (!b.flickrPhotosetId || !nav(c.navigationUrl, b.flickrPhotosetId) || !timestamp(c.identityVerifiedAt))
      || ['remote_album_missing_needs_attention', 'album_identity_conflict'].includes(m.state) && c.navigationUrl !== null
      || m.repairSurface !== (m.state === 'create_outcome_unknown' ? value.localLifecycle === 'active' ? 'plugin_or_admin' : 'admin_only' : 'none')) throw new Error('integrity');
  } else {
    const rows = value.obligations ?? value.candidates ?? value.repairs;
    const ids = rows.map((row: any) => row.obligation?.fgaAlbumObligationId ?? row.flickrPhotosetId ?? row.fgaAlbumBindingId);
    if (ids.some((id: string, i: number) => i > 0 && ids[i - 1] >= id)) throw new Error('integrity');
    if (bindingId !== undefined && value.fgaAlbumBindingId !== bindingId || value.pages !== Math.ceil(value.total / value.pageSize)
      || value.page > Math.max(1, value.pages) || rows.length !== Math.min(value.pageSize, Math.max(0, value.total - (value.page - 1) * value.pageSize))) throw new Error('integrity');
    for (const row of rows) {
      if (row.obligation && (row.obligation.fgaAlbumBindingId !== bindingId || row.state === 'membership_verified' && row.membershipObservedAt === null
        || row.membershipObservedAt !== null && !timestamp(row.membershipObservedAt))) throw new Error('integrity');
      if (row.desiredTitle !== undefined && !text(row.desiredTitle, 4000, false)) throw new Error('integrity');
      if (row.title !== undefined) {
        if (!text(row.title, 4096) || !nav(row.navigationUrl, row.flickrPhotosetId) || [row.createdAt, row.updatedAt].some(t => t !== null && !timestamp(t))) throw new Error('integrity');
        if (row.thumbnail !== null) { const url = new URL(row.thumbnail.url);
          if (!text(row.thumbnail.url, 2048, false) || url.protocol !== 'https:' || url.username || url.password || url.hash || url.port
            || !/^(?:live\.staticflickr\.com|farm[0-9]+\.staticflickr\.com)$/.test(url.hostname)
            || !new RegExp(`^/[^/]+/${row.primaryPhotoId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}_`).test(url.pathname)) throw new Error('integrity'); }
      }
    }
    if (value.observedAt !== undefined && !timestamp(value.observedAt)) throw new Error('integrity');
  }
  const body = JSON.stringify(value);
  if (new TextEncoder().encode(body).length > limit) throw new Error('integrity');
  return new Response(body, { headers: { ...SECURITY, 'Content-Type': 'application/json; charset=utf-8' } });
}

/** Caller performs accepted current Bearer or server-session/Origin/CSRF authentication first.
 * The store independently rechecks current durable authority before every disclosure/commit. */
export async function albumCreateRepairRequest(env: AlbumCreateRepairEnv, auth: RepairAuth, request: Request,
  bindingId?: string, deps?: AlbumCreateRepairDependencies): Promise<Response> {
  const url = new URL(request.url), admin = url.pathname.startsWith('/api/v001/admin/');
  if (admin !== (auth.kind === 'admin')) return albumCreateRepairFailure(admin ? 'unauthorized' : 'invalid_token');
  if (env.FGA_ALBUM_CREATE_REPAIR_ENABLED !== '1') return albumCreateRepairFailure('service_unavailable');
  const base = `/api/v001/${admin ? 'admin/' : ''}`;
  const list = bindingId === undefined && admin && url.pathname === `${base}album-create-repairs`;
  const suffix = bindingId === undefined ? '' : url.pathname.slice(`${base}album-bindings/${bindingId}/`.length);
  if (!list && (!bindingId || !SERVICE_ID.test(bindingId) || url.pathname !== `${base}album-bindings/${bindingId}/${suffix}`
    || !['status', 'photo-association-status', 'create-repair-candidates', 'create-repair-resolution'].includes(suffix))) return albumCreateRepairFailure('invalid_request');
  const selection = suffix === 'create-repair-resolution';
  if (request.method !== (selection ? 'PUT' : 'GET')) return albumCreateRepairFailure('invalid_request');
  let input: ResolveRequest | undefined, page = { page: 1, pageSize: 1 };
  try {
    if (!selection && !noBody(request)) throw new Error('invalid_request');
    if (selection || suffix === 'status') { if (url.search) throw new Error('invalid_request'); }
    else page = parseAlbumCreateRepairPage(url, suffix === 'create-repair-candidates' ? 20 : 100);
    if (selection) input = resolve(await readStrictAlbumJson(request));
  } catch { return albumCreateRepairFailure('invalid_request'); }
  try {
    if (list) return responseBody(await readAlbumRepairPage(env.DB, auth, page.page, page.pageSize), ALBUM_CREATE_REPAIR_REPAIR_PAGE_SCHEMA, undefined, 512 * 1024);
    if (suffix === 'status') return responseBody(await readAlbumStatus(env.DB, auth, bindingId!), ALBUM_CREATE_REPAIR_STATUS_SCHEMA, bindingId, 32 * 1024);
    if (suffix === 'photo-association-status') return responseBody(await readAlbumObligationPage(env.DB, auth, bindingId!, page.page, page.pageSize), ALBUM_CREATE_REPAIR_OBLIGATION_PAGE_SCHEMA, bindingId, 512 * 1024);
    if (!input) {
      const context = await readAlbumRepairContext(env.DB, auth, bindingId!);
      if (!deps) return albumCreateRepairFailure('candidate_evidence_unavailable');
      const result = await deps.reader(context).discover(page.page, page.pageSize);
      await assertAlbumRepairContext(env.DB, auth, context);
      if (result.page !== page.page || result.pageSize !== page.pageSize || result.bindingRevision !== context.bindingRevision || result.createAttemptId !== context.attemptId
        || result.candidates.some(candidate => candidate.ownerNsid !== context.ownerNsid || context.preContextIds.includes(candidate.flickrPhotosetId))) throw new Error('integrity');
      return responseBody(result, ALBUM_CREATE_REPAIR_CANDIDATE_PAGE_SCHEMA, bindingId, 512 * 1024);
    }
    const prepared = await prepareAlbumResolution(env.DB, auth, bindingId!, input);
    if (prepared.replay) return responseBody(prepared.status, ALBUM_CREATE_REPAIR_STATUS_SCHEMA, bindingId, 32 * 1024);
    if (!deps) return albumCreateRepairFailure('resolution_evidence_unavailable');
    const proof = await deps.reader(prepared.context).prove(input.selectedPhotosetId);
    return responseBody(await commitAlbumResolution(env.DB, auth, prepared.context, input, proof), ALBUM_CREATE_REPAIR_STATUS_SCHEMA, bindingId, 32 * 1024);
  } catch (error) {
    const code = error instanceof AlbumCreateRepairStoreError ? error.message
      : error !== null && typeof error === 'object' && 'code' in error && typeof error.code === 'string' ? error.code : 'service_unavailable';
    const retryAfter = error !== null && typeof error === 'object' && 'retryAfter' in error && typeof error.retryAfter === 'number' ? error.retryAfter : 5;
    return albumCreateRepairFailure(code, retryAfter);
  }
}

export const ALBUM_CREATE_REPAIR_ROUTES = [
  { id: 'album_binding_status', method: 'GET', pathPattern: '/api/v001/album-bindings/{bindingId}/status',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_binding_status', auth: 'installation_bearer', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_STATUS_SCHEMA, successStatuses: [200] },
  { id: 'album_photo_association_status', method: 'GET', pathPattern: '/api/v001/album-bindings/{bindingId}/photo-association-status',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_photo_association_status', auth: 'installation_bearer', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_OBLIGATION_PAGE_SCHEMA, successStatuses: [200] },
  { id: 'album_create_repair_candidates', method: 'GET', pathPattern: '/api/v001/album-bindings/{bindingId}/create-repair-candidates',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_create_repair_candidates', auth: 'installation_bearer', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_CANDIDATE_PAGE_SCHEMA, successStatuses: [200] },
  { id: 'album_create_repair_resolution', method: 'PUT', pathPattern: '/api/v001/album-bindings/{bindingId}/create-repair-resolution',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_create_repair_resolution', auth: 'installation_bearer', allowPending: false,
    request: ALBUM_CREATE_REPAIR_RESOLVE_REQUEST_SCHEMA, response: ALBUM_CREATE_REPAIR_STATUS_SCHEMA, successStatuses: [200] },
  { id: 'admin_album_create_repairs', method: 'GET', pathPattern: '/api/v001/admin/album-create-repairs',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: null, handler: 'album_create_repair_admin', auth: 'browser_session', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_REPAIR_PAGE_SCHEMA, successStatuses: [200] },
  { id: 'admin_album_binding_status', method: 'GET', pathPattern: '/api/v001/admin/album-bindings/{bindingId}/status',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: null, handler: 'album_create_repair_admin', auth: 'browser_session', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_STATUS_SCHEMA, successStatuses: [200] },
  { id: 'admin_album_photo_association_status', method: 'GET', pathPattern: '/api/v001/admin/album-bindings/{bindingId}/photo-association-status',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: null, handler: 'album_create_repair_admin', auth: 'browser_session', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_OBLIGATION_PAGE_SCHEMA, successStatuses: [200] },
  { id: 'admin_album_create_repair_candidates', method: 'GET', pathPattern: '/api/v001/admin/album-bindings/{bindingId}/create-repair-candidates',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: null, handler: 'album_create_repair_admin', auth: 'browser_session', allowPending: false,
    request: null, response: ALBUM_CREATE_REPAIR_CANDIDATE_PAGE_SCHEMA, successStatuses: [200] },
  { id: 'admin_album_create_repair_resolution', method: 'PUT', pathPattern: '/api/v001/admin/album-bindings/{bindingId}/create-repair-resolution',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: null, handler: 'album_create_repair_admin', auth: 'browser_session', allowPending: false,
    request: ALBUM_CREATE_REPAIR_RESOLVE_REQUEST_SCHEMA, response: ALBUM_CREATE_REPAIR_STATUS_SCHEMA, successStatuses: [200] },
] as const;
