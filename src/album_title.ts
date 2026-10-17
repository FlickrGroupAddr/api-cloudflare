import type { AdmissionAuth, SqlStore } from './admission.ts';
import { SERVICE_ID } from './publish_services.ts';
import { ALBUM_BINDING_RESPONSE_SCHEMA, bindingProjection, parseStrictAlbumJson, readStrictAlbumJson } from './album_bindings.ts';
import { AlbumTitleStoreError, readAlbumLifecycle, putAlbumTitleIntent,
  type AlbumTitleRequest, type AlbumLifecycle, type AlbumTitleReceipt } from './album_title_store.ts';

export interface AlbumTitleEnv { DB: SqlStore; FGA_ALBUM_TITLE_ENABLED?: string; }
const SECURITY = { 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
const UUID = { type: 'string', pattern: SERVICE_ID.source } as const;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
const TITLE = { type: 'string', minLength: 1, maxLength: 1000 } as const;
const TIMESTAMP = { type: 'string', pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$' } as const;
const nullable = <T>(schema: T) => ({ anyOf: [{ type: 'null' }, schema] });
const closed = <T extends Record<string, unknown>>(properties: T) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });
const TITLE_STATES = ['waiting_for_materialization', 'pending', 'reconciliation_pending', 'synced', 'conflict', 'needs_attention',
  'local_removed_reconciliation_pending', 'local_removed'] as const;
export const ALBUM_TITLE_REQUEST_SCHEMA = closed({ schemaVersion: { const: 1 }, expectedBindingRevision: REVISION,
  expectedTitleRevision: REVISION, desiredTitle: TITLE });
export const ALBUM_TITLE_VIEW_SCHEMA = closed({ state: { enum: TITLE_STATES }, observedTitle: nullable({ type: 'string', maxLength: 4096 }),
  observedAt: nullable(TIMESTAMP), dispatchTitleRevision: nullable(REVISION), dispatchAttemptId: nullable(UUID) });
export const ALBUM_REPAIR_HANDOFF_SCHEMA = closed({ destination: { enum: ['none', 'administrative_album_create_repair'] },
  fgaAlbumBindingId: UUID, createAttemptId: nullable(UUID), acknowledgedAt: nullable(TIMESTAMP) });
export const ALBUM_LIFECYCLE_SCHEMA = closed({ schemaVersion: { const: 1 }, binding: ALBUM_BINDING_RESPONSE_SCHEMA,
  localLifecycle: { enum: ['active', 'local_collection_removed_remote_preserved'] }, title: ALBUM_TITLE_VIEW_SCHEMA,
  unresolvedCreateAttemptId: nullable(UUID), repairHandoff: ALBUM_REPAIR_HANDOFF_SCHEMA });
export const ALBUM_TITLE_LIFECYCLE_SCHEMA = ALBUM_LIFECYCLE_SCHEMA;
export const ALBUM_TITLE_RECEIPT_SCHEMA = closed({ schemaVersion: { const: 1 }, fgaAlbumBindingId: UUID, acceptedTitleRevision: REVISION,
  acceptedDesiredTitle: TITLE, acceptedBindingRevision: REVISION, acceptedAt: TIMESTAMP, current: ALBUM_LIFECYCLE_SCHEMA });
const ERRORS: Record<string, readonly [number, string]> = {
  invalid_request: [400, 'Invalid album lifecycle request.'], invalid_token: [401, 'Invalid installation credential.'],
  insufficient_scope: [403, 'Credential cannot perform this operation.'], resource_not_found: [404, 'Resource not found.'],
  stale_binding_revision: [409, 'Album binding revision changed.'], stale_title_revision: [409, 'Album title revision changed.'],
  stale_obligation_revision: [409, 'Album obligation revision changed.'], title_intent_conflict: [409, 'Title intent conflicts with its receipt.'],
  album_closed: [409, 'Album is closed.'], flickr_link_unavailable: [409, 'The Flickr connection is unavailable.'],
  removal_acknowledgement_required: [409, 'Album removal acknowledgement is required.'],
  removal_acknowledgement_conflict: [409, 'Album removal acknowledgement conflicts with its receipt.'],
  revision_exhausted: [409, 'Album revision is exhausted.'], rate_limited: [429, 'Too many requests.'],
  service_unavailable: [503, 'Service unavailable.'],
};
export const ALBUM_TITLE_ERROR_SCHEMA = closed({ schemaVersion: { const: 1 }, error: closed({ code: { enum: Object.keys(ERRORS) },
  message: { type: 'string', minLength: 1, maxLength: 256 }, retryable: { type: 'boolean' }, correlationId: UUID }) });
const ROUTE_BASE = { owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
  expectedChallenge: 'Bearer realm="fga-api"', auth: 'installation_bearer', allowPending: false } as const;
export const ALBUM_TITLE_ROUTES = [
  { ...ROUTE_BASE, id: 'album_lifecycle_read', handler: 'album_lifecycle_read', method: 'GET', pathPattern: '/api/v001/album-bindings/{bindingId}/lifecycle',
    request: null, response: ALBUM_LIFECYCLE_SCHEMA, successStatuses: [200] },
  { ...ROUTE_BASE, id: 'album_title_intent', handler: 'album_title_intent', method: 'PUT', pathPattern: '/api/v001/album-bindings/{bindingId}/title-intents/{titleRevision}',
    request: ALBUM_TITLE_REQUEST_SCHEMA, response: ALBUM_TITLE_RECEIPT_SCHEMA, successStatuses: [200, 201] },
] as const;
export const ALBUM_TITLE_SCHEMAS = { request: ALBUM_TITLE_REQUEST_SCHEMA, lifecycle: ALBUM_LIFECYCLE_SCHEMA,
  receipt: ALBUM_TITLE_RECEIPT_SCHEMA, error: ALBUM_TITLE_ERROR_SCHEMA } as const;
export const ALBUM_TITLE_RELEASE_METADATA = { enabledFlag: 'FGA_ALBUM_TITLE_ENABLED', defaultValue: '0', hostQualified: false } as const;

function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function exact(value: unknown, names: string[]): value is Record<string, unknown> {
  return object(value) && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
}
function revision(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1; }
function text(value: unknown, min: number, max: number): value is string {
  return typeof value === 'string' && [...value].length >= min && [...value].length <= max && !/[\p{Cc}\p{Cs}]/u.test(value);
}
function uuid(value: unknown): value is string { return typeof value === 'string' && SERVICE_ID.test(value); }
function timestamp(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value)) return false;
  const instant = Date.parse(value); return Number.isFinite(instant) && new Date(instant).toISOString() === value.slice(0, 23) + 'Z';
}
function titleRequest(value: unknown): AlbumTitleRequest {
  if (!exact(value, ['schemaVersion', 'expectedBindingRevision', 'expectedTitleRevision', 'desiredTitle']) || value.schemaVersion !== 1
    || !revision(value.expectedBindingRevision) || !revision(value.expectedTitleRevision) || !text(value.desiredTitle, 1, 1000)) throw new Error('invalid_request');
  return { schemaVersion: 1, expectedBindingRevision: value.expectedBindingRevision, expectedTitleRevision: value.expectedTitleRevision, desiredTitle: value.desiredTitle };
}
export function parseAlbumTitleIntent(raw: string): AlbumTitleRequest {
  if (new TextEncoder().encode(raw).length > 4096) throw new Error('invalid_request');
  return titleRequest(parseStrictAlbumJson(raw));
}
export function parseAlbumTitleRevision(raw: string): number {
  if (!/^[1-9][0-9]{0,15}$/.test(raw) || !revision(Number(raw))) throw new Error('invalid_request'); return Number(raw);
}

/** Validate the complete stored snapshot before exposing any private state. */
export function albumLifecycleProjection(value: unknown, bindingId: string): AlbumLifecycle {
  const fail = (): never => { throw new Error('integrity'); };
  if (!exact(value, ['schemaVersion', 'binding', 'localLifecycle', 'title', 'unresolvedCreateAttemptId', 'repairHandoff']) || value.schemaVersion !== 1
    || !exact(value.binding, Object.keys(ALBUM_BINDING_RESPONSE_SCHEMA.properties)) || value.binding.fgaAlbumBindingId !== bindingId
    || !uuid(value.binding.fgaPublishServiceId) || typeof value.binding.localCollectionIdentifier !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(value.binding.localCollectionIdentifier)) return fail();
  const binding = bindingProjection(value.binding as unknown as AlbumLifecycle['binding'], value.binding.fgaPublishServiceId, value.binding.localCollectionIdentifier);
  if (!exact(value.title, ['state', 'observedTitle', 'observedAt', 'dispatchTitleRevision', 'dispatchAttemptId'])
    || !TITLE_STATES.includes(value.title.state as typeof TITLE_STATES[number])) return fail();
  const title = value.title;
  if (title.observedTitle === null ? title.observedAt !== null : !text(title.observedTitle, 0, 4096)
    || new TextEncoder().encode(title.observedTitle).length > 4096 || !timestamp(title.observedAt)) return fail();
  if (title.dispatchTitleRevision === null ? title.dispatchAttemptId !== null : !revision(title.dispatchTitleRevision)
    || title.dispatchTitleRevision > binding.titleRevision || !uuid(title.dispatchAttemptId)) return fail();
  const removed = value.localLifecycle === 'local_collection_removed_remote_preserved';
  if ((!removed && value.localLifecycle !== 'active') || removed !== String(title.state).startsWith('local_removed')
    || title.state === 'synced' && (title.observedTitle === null || title.observedTitle !== binding.desiredTitle)
    || title.state === 'conflict' && (title.observedTitle === null || title.observedTitle === binding.desiredTitle)
    || title.state === 'local_removed_reconciliation_pending' && title.dispatchAttemptId === null
    || value.unresolvedCreateAttemptId !== null && !uuid(value.unresolvedCreateAttemptId)) return fail();
  if (!exact(value.repairHandoff, ['destination', 'fgaAlbumBindingId', 'createAttemptId', 'acknowledgedAt'])) return fail();
  const handoff = value.repairHandoff;
  if (handoff.fgaAlbumBindingId !== bindingId) return fail();
  if (handoff.destination === 'none') {
    if (handoff.createAttemptId !== null || handoff.acknowledgedAt !== null || removed && value.unresolvedCreateAttemptId !== null) return fail();
  } else if (handoff.destination !== 'administrative_album_create_repair' || !removed || !uuid(handoff.createAttemptId)
    || !timestamp(handoff.acknowledgedAt) || value.unresolvedCreateAttemptId !== null && handoff.createAttemptId !== value.unresolvedCreateAttemptId) return fail();
  return { schemaVersion: 1, binding, localLifecycle: value.localLifecycle as AlbumLifecycle['localLifecycle'],
    title: { state: title.state as AlbumLifecycle['title']['state'], observedTitle: title.observedTitle as string | null,
      observedAt: title.observedAt as string | null, dispatchTitleRevision: title.dispatchTitleRevision as number | null,
      dispatchAttemptId: title.dispatchAttemptId as string | null }, unresolvedCreateAttemptId: value.unresolvedCreateAttemptId,
    repairHandoff: { destination: handoff.destination as AlbumLifecycle['repairHandoff']['destination'], fgaAlbumBindingId: bindingId,
      createAttemptId: handoff.createAttemptId as string | null, acknowledgedAt: handoff.acknowledgedAt as string | null } };
}
export function albumTitleReceiptProjection(value: unknown, bindingId: string, pathRevision: number, input: AlbumTitleRequest): AlbumTitleReceipt {
  if (!exact(value, ['schemaVersion', 'fgaAlbumBindingId', 'acceptedTitleRevision', 'acceptedDesiredTitle', 'acceptedBindingRevision', 'acceptedAt', 'current'])
    || value.schemaVersion !== 1 || value.fgaAlbumBindingId !== bindingId || value.acceptedTitleRevision !== pathRevision
    || value.acceptedDesiredTitle !== input.desiredTitle || !revision(value.acceptedBindingRevision)
    || value.acceptedBindingRevision !== input.expectedBindingRevision + 1 || !timestamp(value.acceptedAt)) throw new Error('integrity');
  const current = albumLifecycleProjection(value.current, bindingId);
  if (current.binding.titleRevision < pathRevision || current.binding.bindingRevision < value.acceptedBindingRevision) throw new Error('integrity');
  return { schemaVersion: 1, fgaAlbumBindingId: bindingId, acceptedTitleRevision: pathRevision, acceptedDesiredTitle: input.desiredTitle,
    acceptedBindingRevision: value.acceptedBindingRevision, acceptedAt: value.acceptedAt, current };
}
export function albumTitleFailure(code: string): Response {
  const safe = Object.hasOwn(ERRORS, code) ? code : 'service_unavailable', [status, message] = ERRORS[safe]!;
  return Response.json({ schemaVersion: 1, error: { code: safe, message, retryable: status === 429 || status === 503, correlationId: crypto.randomUUID() } },
    { status, headers: { ...SECURITY, ...(status === 401 || status === 403 ? { 'WWW-Authenticate': `Bearer realm="fga-api", error="${safe}"` } : {}),
      ...(status === 429 || status === 503 ? { 'Retry-After': '5' } : {}) } });
}
function boundedResponse(value: unknown, status: number, location?: string): Response {
  const body = JSON.stringify(value);
  if (new TextEncoder().encode(body).length > 32768) throw new Error('integrity');
  return new Response(body, { status, headers: { ...SECURITY, 'Content-Type': 'application/json', ...(location ? { Location: location } : {}) } });
}
/** Worker authenticates the current installation with allowPending=false first.
 * Both operations read only owning D1 facts; they never perform a provider request. */
export async function albumTitleRequest(env: AlbumTitleEnv, auth: AdmissionAuth, request: Request,
  bindingId: string, titleRevision?: string): Promise<Response> {
  if (env.FGA_ALBUM_TITLE_ENABLED !== '1') return albumTitleFailure('service_unavailable');
  const url = new URL(request.url), base = `/api/v001/album-bindings/${encodeURIComponent(bindingId)}`;
  let input: AlbumTitleRequest | undefined, pathRevision: number | undefined;
  try {
    if (!uuid(bindingId) || url.search) throw new Error('invalid_request');
    if (titleRevision === undefined) {
      if (request.method !== 'GET' || url.pathname !== base + '/lifecycle' || request.body !== null || request.headers.has('Transfer-Encoding')
        || request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0') throw new Error('invalid_request');
    } else {
      pathRevision = parseAlbumTitleRevision(titleRevision);
      if (request.method !== 'PUT' || url.pathname !== base + '/title-intents/' + titleRevision) throw new Error('invalid_request');
      input = titleRequest(await readStrictAlbumJson(request));
    }
  } catch { return albumTitleFailure('invalid_request'); }
  try {
    if (!input) return boundedResponse(albumLifecycleProjection(await readAlbumLifecycle(env.DB, auth, bindingId), bindingId), 200);
    const result = await putAlbumTitleIntent(env.DB, auth, bindingId, pathRevision!, input);
    if (typeof result.created !== 'boolean') throw new Error('integrity');
    return boundedResponse(albumTitleReceiptProjection(result.receipt, bindingId, pathRevision!, input), result.created ? 201 : 200,
      result.created ? base + '/title-intents/' + titleRevision : undefined);
  } catch (error) { return albumTitleFailure(error instanceof AlbumTitleStoreError ? error.message : 'service_unavailable'); }
}
