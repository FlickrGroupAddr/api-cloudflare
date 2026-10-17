import type { AdmissionAuth, SqlStore } from './admission.ts';
import { SERVICE_ID } from './publish_services.ts';
import { ALBUM_OBLIGATION_RESPONSE_SCHEMA, parseStrictAlbumJson } from './album_bindings.ts';
import { ALBUM_LIFECYCLE_SCHEMA, ALBUM_REPAIR_HANDOFF_SCHEMA, ALBUM_TITLE_ERROR_SCHEMA,
  albumLifecycleProjection, albumTitleFailure } from './album_title.ts';
import { AlbumLocalRemovalStoreError, putAlbumLocalRemoval, putAlbumPhotoLocalRemoval,
  type AlbumRemovalRequest, type PhotoRemovalRequest, type AlbumRemovalReceipt, type PhotoRemovalReceipt } from './album_local_removal_store.ts';

export interface AlbumLocalRemovalEnv { DB: SqlStore; FGA_ALBUM_LOCAL_REMOVAL_ENABLED?: string; }
const SECURITY = { 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
const UUID = { type: 'string', pattern: SERVICE_ID.source } as const;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
const TIMESTAMP = { type: 'string', pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$' } as const;
const closed = <T extends Record<string, unknown>>(properties: T) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });
export const PHOTO_LOCAL_REMOVAL_REQUEST_SCHEMA = closed({ schemaVersion: { const: 1 }, expectedBindingRevision: REVISION, expectedObligationRevision: REVISION });
export const ALBUM_LOCAL_REMOVAL_REQUEST_SCHEMA = closed({ schemaVersion: { const: 1 }, expectedBindingRevision: REVISION,
  acknowledgedCreateAttemptId: { anyOf: [{ type: 'null' }, UUID] } });
export const PHOTO_LOCAL_REMOVAL_RECEIPT_SCHEMA = closed({ schemaVersion: { const: 1 }, obligation: ALBUM_OBLIGATION_RESPONSE_SCHEMA,
  localRelationship: { const: 'archived' }, archivedAt: TIMESTAMP, acceptedBindingRevision: REVISION, current: ALBUM_LIFECYCLE_SCHEMA });
export const ALBUM_LOCAL_REMOVAL_RECEIPT_SCHEMA = closed({ schemaVersion: { const: 1 }, fgaAlbumBindingId: UUID,
  localLifecycle: { const: 'local_collection_removed_remote_preserved' }, archivedAt: TIMESTAMP, acceptedBindingRevision: REVISION,
  repairHandoff: ALBUM_REPAIR_HANDOFF_SCHEMA, current: ALBUM_LIFECYCLE_SCHEMA });
export const ALBUM_LOCAL_REMOVAL_ERROR_SCHEMA = ALBUM_TITLE_ERROR_SCHEMA;
const ROUTE_BASE = { owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
  expectedChallenge: 'Bearer realm="fga-api"', auth: 'installation_bearer', allowPending: false, method: 'PUT', successStatuses: [200, 201] } as const;
export const ALBUM_LOCAL_REMOVAL_ROUTES = [
  { ...ROUTE_BASE, id: 'album_photo_local_removal', handler: 'album_photo_local_removal',
    pathPattern: '/api/v001/album-bindings/{bindingId}/photo-associations/{photoBindingId}/local-removal',
    request: PHOTO_LOCAL_REMOVAL_REQUEST_SCHEMA, response: PHOTO_LOCAL_REMOVAL_RECEIPT_SCHEMA },
  { ...ROUTE_BASE, id: 'album_local_removal', handler: 'album_local_removal', pathPattern: '/api/v001/album-bindings/{bindingId}/local-removal',
    request: ALBUM_LOCAL_REMOVAL_REQUEST_SCHEMA, response: ALBUM_LOCAL_REMOVAL_RECEIPT_SCHEMA },
] as const;
export const ALBUM_LOCAL_REMOVAL_SCHEMAS = { albumRequest: ALBUM_LOCAL_REMOVAL_REQUEST_SCHEMA, photoRequest: PHOTO_LOCAL_REMOVAL_REQUEST_SCHEMA,
  albumReceipt: ALBUM_LOCAL_REMOVAL_RECEIPT_SCHEMA, photoReceipt: PHOTO_LOCAL_REMOVAL_RECEIPT_SCHEMA, error: ALBUM_LOCAL_REMOVAL_ERROR_SCHEMA } as const;
export const ALBUM_LOCAL_REMOVAL_RELEASE_METADATA = { enabledFlag: 'FGA_ALBUM_LOCAL_REMOVAL_ENABLED', defaultValue: '0', hostQualified: false } as const;
export const albumLocalRemovalFailure = albumTitleFailure;

function exact(value: unknown, names: readonly string[]): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === names.length
    && names.every(name => Object.hasOwn(value, name));
}
function revision(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1; }
function uuid(value: unknown): value is string { return typeof value === 'string' && SERVICE_ID.test(value); }
function timestamp(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value)) return false;
  const instant = Date.parse(value); return Number.isFinite(instant) && new Date(instant).toISOString() === value.slice(0, 23) + 'Z';
}
// Removal requests are flat closed objects. Scan names before JSON.parse can erase
// duplicates, and use the admission parser for exact safe-integer number semantics.
function removalJson(raw: string): Record<string, unknown> {
  if (new TextEncoder().encode(raw).length > 4096) throw new Error('invalid_request');
  let offset = 0;
  const invalid = (): never => { throw new Error('invalid_request'); };
  const space = () => { while (offset < raw.length && /[\x20\t\r\n]/.test(raw[offset]!)) offset++; };
  const string = (): string => {
    const start = offset++;
    while (offset < raw.length) {
      const c = raw[offset++];
      if (c === '"') return JSON.parse(raw.slice(start, offset)) as string;
      if (c === '\\') offset++;
    }
    return invalid();
  };
  space(); if (raw[offset++] !== '{') return invalid(); space();
  const result: Record<string, unknown> = Object.create(null);
  if (raw[offset] === '}') { offset++; } else for (;;) {
    space(); if (raw[offset] !== '"') return invalid(); const name = string();
    if (Object.hasOwn(result, name)) return invalid(); space(); if (raw[offset++] !== ':') return invalid(); space();
    if (raw[offset] === '"') result[name] = string();
    else if (raw.slice(offset, offset + 4) === 'null') { result[name] = null; offset += 4; }
    else {
      const start = offset; while (offset < raw.length && !/[,}\x20\t\r\n]/.test(raw[offset]!)) offset++;
      result[name] = parseStrictAlbumJson(raw.slice(start, offset));
    }
    space(); const end = raw[offset++]; if (end === '}') break; if (end !== ',') return invalid();
  }
  space(); if (offset !== raw.length) return invalid(); return result;
}
export function parsePhotoLocalRemoval(raw: string): PhotoRemovalRequest {
  const value = removalJson(raw);
  if (!exact(value, ['schemaVersion', 'expectedBindingRevision', 'expectedObligationRevision']) || value.schemaVersion !== 1
    || !revision(value.expectedBindingRevision) || !revision(value.expectedObligationRevision)) throw new Error('invalid_request');
  return { schemaVersion: 1, expectedBindingRevision: value.expectedBindingRevision, expectedObligationRevision: value.expectedObligationRevision };
}
export function parseAlbumLocalRemoval(raw: string): AlbumRemovalRequest {
  const value = removalJson(raw);
  if (!exact(value, ['schemaVersion', 'expectedBindingRevision', 'acknowledgedCreateAttemptId']) || value.schemaVersion !== 1
    || !revision(value.expectedBindingRevision) || value.acknowledgedCreateAttemptId !== null && !uuid(value.acknowledgedCreateAttemptId)) throw new Error('invalid_request');
  return { schemaVersion: 1, expectedBindingRevision: value.expectedBindingRevision, acknowledgedCreateAttemptId: value.acknowledgedCreateAttemptId };
}
async function body(request: Request): Promise<string> {
  if (!/^application\/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*$/i.test(request.headers.get('Content-Type') ?? '')
    || request.headers.has('Content-Encoding') && request.headers.get('Content-Encoding') !== 'identity'
    || request.headers.has('Transfer-Encoding') || request.headers.has('Content-Length') && !/^(?:0|[1-9][0-9]{0,3})$/.test(request.headers.get('Content-Length')!)
    || Number(request.headers.get('Content-Length')) > 4096 || !request.body) throw new Error('invalid_request');
  const reader = request.body.getReader(), parts: Uint8Array[] = []; let size = 0;
  try {
    for (;;) { const { done, value } = await reader.read(); if (done) break;
      size += value.length; if (size > 4096) { await reader.cancel(); throw new Error('invalid_request'); } parts.push(value); }
    if (request.headers.has('Content-Length') && Number(request.headers.get('Content-Length')) !== size) throw new Error('invalid_request');
    const bytes = new Uint8Array(size); let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.length; }
    return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  } finally { reader.releaseLock(); }
}

export function photoLocalRemovalReceiptProjection(value: unknown, bindingId: string, photoBindingId: string): PhotoRemovalReceipt {
  if (!exact(value, ['schemaVersion', 'obligation', 'localRelationship', 'archivedAt', 'acceptedBindingRevision', 'current']) || value.schemaVersion !== 1
    || !exact(value.obligation, Object.keys(ALBUM_OBLIGATION_RESPONSE_SCHEMA.properties)) || !uuid(value.obligation.fgaAlbumObligationId)
    || value.obligation.fgaAlbumBindingId !== bindingId || value.obligation.fgaPhotoBindingId !== photoBindingId
    || !revision(value.obligation.obligationRevision) || value.localRelationship !== 'archived' || !timestamp(value.archivedAt)
    || !revision(value.acceptedBindingRevision)) throw new Error('integrity');
  const current = albumLifecycleProjection(value.current, bindingId);
  if (current.binding.bindingRevision < value.acceptedBindingRevision) throw new Error('integrity');
  return { schemaVersion: 1, obligation: { fgaAlbumObligationId: value.obligation.fgaAlbumObligationId, fgaAlbumBindingId: bindingId,
    fgaPhotoBindingId: photoBindingId, obligationRevision: value.obligation.obligationRevision }, localRelationship: 'archived',
    archivedAt: value.archivedAt, acceptedBindingRevision: value.acceptedBindingRevision, current };
}
export function albumLocalRemovalReceiptProjection(value: unknown, bindingId: string): AlbumRemovalReceipt {
  if (!exact(value, ['schemaVersion', 'fgaAlbumBindingId', 'localLifecycle', 'archivedAt', 'acceptedBindingRevision', 'repairHandoff', 'current'])
    || value.schemaVersion !== 1 || value.fgaAlbumBindingId !== bindingId || value.localLifecycle !== 'local_collection_removed_remote_preserved'
    || !timestamp(value.archivedAt) || !revision(value.acceptedBindingRevision)
    || !exact(value.repairHandoff, ['destination', 'fgaAlbumBindingId', 'createAttemptId', 'acknowledgedAt'])) throw new Error('integrity');
  const current = albumLifecycleProjection(value.current, bindingId), handoff = value.repairHandoff;
  if (current.localLifecycle !== 'local_collection_removed_remote_preserved' || current.binding.bindingRevision < value.acceptedBindingRevision
    || handoff.fgaAlbumBindingId !== bindingId) throw new Error('integrity');
  if (handoff.destination === 'none') {
    if (handoff.createAttemptId !== null || handoff.acknowledgedAt !== null) throw new Error('integrity');
  } else if (handoff.destination !== 'administrative_album_create_repair' || !uuid(handoff.createAttemptId)
    || !timestamp(handoff.acknowledgedAt) || handoff.acknowledgedAt !== value.archivedAt) throw new Error('integrity');
  return { schemaVersion: 1, fgaAlbumBindingId: bindingId, localLifecycle: 'local_collection_removed_remote_preserved', archivedAt: value.archivedAt,
    acceptedBindingRevision: value.acceptedBindingRevision, repairHandoff: { destination: handoff.destination as AlbumRemovalReceipt['repairHandoff']['destination'],
      fgaAlbumBindingId: bindingId, createAttemptId: handoff.createAttemptId as string | null, acknowledgedAt: handoff.acknowledgedAt as string | null }, current };
}
/** Caller authenticates the current installation with allowPending=false first.
 * The accepted administrative repair surface retains server-side browser sessions;
 * installation credentials never gain administrative authority through this route. */
export async function albumLocalRemovalRequest(env: AlbumLocalRemovalEnv, auth: AdmissionAuth, request: Request,
  bindingId: string, photoBindingId?: string): Promise<Response> {
  if (env.FGA_ALBUM_LOCAL_REMOVAL_ENABLED !== '1') return albumLocalRemovalFailure('service_unavailable');
  const base = `/api/v001/album-bindings/${encodeURIComponent(bindingId)}`;
  const path = photoBindingId === undefined ? base + '/local-removal'
    : base + '/photo-associations/' + encodeURIComponent(photoBindingId) + '/local-removal';
  let input: AlbumRemovalRequest | PhotoRemovalRequest;
  try {
    const url = new URL(request.url);
    if (!uuid(bindingId) || photoBindingId !== undefined && !/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(photoBindingId)
      || request.method !== 'PUT' || url.pathname !== path || url.search) throw new Error('invalid_request');
    const raw = await body(request); input = photoBindingId === undefined ? parseAlbumLocalRemoval(raw) : parsePhotoLocalRemoval(raw);
  } catch { return albumLocalRemovalFailure('invalid_request'); }
  try {
    const result = photoBindingId === undefined
      ? await putAlbumLocalRemoval(env.DB, auth, bindingId, input as AlbumRemovalRequest)
      : await putAlbumPhotoLocalRemoval(env.DB, auth, bindingId, photoBindingId, input as PhotoRemovalRequest);
    if (typeof result.created !== 'boolean') throw new Error('integrity');
    const receipt = photoBindingId === undefined ? albumLocalRemovalReceiptProjection(result.receipt, bindingId)
      : photoLocalRemovalReceiptProjection(result.receipt, bindingId, photoBindingId);
    if (result.created && (receipt.acceptedBindingRevision !== input.expectedBindingRevision + 1
      || photoBindingId !== undefined && (receipt as PhotoRemovalReceipt).obligation.obligationRevision !== (input as PhotoRemovalRequest).expectedObligationRevision + 1
      || photoBindingId === undefined && (receipt as AlbumRemovalReceipt).repairHandoff.createAttemptId !== (input as AlbumRemovalRequest).acknowledgedCreateAttemptId)) throw new Error('integrity');
    const json = JSON.stringify(receipt); if (new TextEncoder().encode(json).length > 32768) throw new Error('integrity');
    return new Response(json, { status: result.created ? 201 : 200, headers: { ...SECURITY, 'Content-Type': 'application/json',
      ...(result.created ? { Location: path } : {}) } });
  } catch (error) { return albumLocalRemovalFailure(error instanceof AlbumLocalRemovalStoreError ? error.message : 'service_unavailable'); }
}
