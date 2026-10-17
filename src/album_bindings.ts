import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse } from './installations.ts';
import { SERVICE_ID } from './publish_services.ts';
import { readAlbumBinding, ensureAlbumBinding, AlbumBindingStoreError,
  type AlbumBinding, type AlbumObligation, type AlbumEnsureRequest } from './album_binding_store.ts';

export interface AlbumBindingsEnv { DB: SqlStore; FGA_ALBUM_BINDINGS_ENABLED?: string; }
const SECURITY = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const UUID_SCHEMA = { type: 'string', pattern: SERVICE_ID.source } as const;
const OPAQUE_SCHEMA = { type: 'string', pattern: OPAQUE_ID.source } as const;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
const TITLE = { type: 'string', minLength: 1, maxLength: 1000 } as const;
export const ALBUM_BINDING_ENSURE_REQUEST_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'desiredTitle', 'candidate'], properties: { schemaVersion: { const: 1 }, desiredTitle: TITLE,
    candidate: { type: 'object', additionalProperties: false, required: ['fgaPhotoBindingId', 'expectedVerificationRevision'],
      properties: { fgaPhotoBindingId: OPAQUE_SCHEMA, expectedVerificationRevision: REVISION } } } } as const;
export const ALBUM_BINDING_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'fgaAlbumBindingId', 'fgaPublishServiceId', 'localCollectionIdentifier', 'linkedFlickrRevision',
    'bindingRevision', 'titleRevision', 'desiredTitle', 'firstPhotoBindingId', 'flickrPhotosetId'],
  properties: { schemaVersion: { const: 1 }, fgaAlbumBindingId: UUID_SCHEMA, fgaPublishServiceId: UUID_SCHEMA,
    localCollectionIdentifier: OPAQUE_SCHEMA, linkedFlickrRevision: REVISION, bindingRevision: REVISION, titleRevision: REVISION,
    desiredTitle: TITLE, firstPhotoBindingId: OPAQUE_SCHEMA, flickrPhotosetId: { anyOf: [{ type: 'null' }, OPAQUE_SCHEMA] } } } as const;
export const ALBUM_OBLIGATION_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['fgaAlbumObligationId', 'fgaAlbumBindingId', 'fgaPhotoBindingId', 'obligationRevision'],
  properties: { fgaAlbumObligationId: UUID_SCHEMA, fgaAlbumBindingId: UUID_SCHEMA, fgaPhotoBindingId: OPAQUE_SCHEMA, obligationRevision: REVISION } } as const;
export const ALBUM_BINDING_ADMISSION_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'binding', 'obligation'], properties: { schemaVersion: { const: 1 },
    binding: ALBUM_BINDING_RESPONSE_SCHEMA, obligation: ALBUM_OBLIGATION_RESPONSE_SCHEMA } } as const;
export const ALBUM_BINDING_ERROR_SCHEMA = { type: 'object', additionalProperties: false, required: ['schemaVersion', 'error'],
  properties: { schemaVersion: { const: 1 }, error: { type: 'object', additionalProperties: false,
    required: ['code', 'message', 'retryable', 'correlationId'], properties: {
      code: { enum: ['invalid_request', 'invalid_token', 'insufficient_scope', 'resource_not_found', 'album_binding_exists',
        'stale_binding_revision', 'stale_photo_revision', 'flickr_link_unavailable', 'album_closed', 'photo_not_ready', 'rate_limited', 'service_unavailable'] },
      message: { type: 'string', minLength: 1, maxLength: 256 }, retryable: { type: 'boolean' }, correlationId: UUID_SCHEMA } } } } as const;
export const ALBUM_BINDINGS_ROUTES = [
  { id: 'album_binding_ensure', method: 'PUT', pathPattern: '/api/v001/publish-services/{serviceId}/album-bindings/{localId}',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_binding_ensure', auth: 'installation_bearer', allowPending: false,
    request: ALBUM_BINDING_ENSURE_REQUEST_SCHEMA, response: ALBUM_BINDING_ADMISSION_RESPONSE_SCHEMA, successStatuses: [200, 201] },
  { id: 'album_binding_read', method: 'GET', pathPattern: '/api/v001/publish-services/{serviceId}/album-bindings/{localId}',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_binding_read', auth: 'installation_bearer', allowPending: false,
    request: null, response: ALBUM_BINDING_RESPONSE_SCHEMA, successStatuses: [200] },
] as const;
export const ALBUM_BINDINGS_RELEASE_METADATA = { enabledFlag: 'FGA_ALBUM_BINDINGS_ENABLED', defaultValue: '0', hostQualified: false } as const;

function revision(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1; }
function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function keys(value: Record<string, unknown>, expected: string[]): boolean {
  return Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key));
}
function title(value: unknown): value is string {
  return typeof value === 'string' && [...value].length >= 1 && [...value].length <= 1000
    && !/[\p{Cc}\p{Cs}]/u.test(value);
}
function id(value: unknown): value is string { return typeof value === 'string' && OPAQUE_ID.test(value); }
function uuid(value: unknown): value is string { return typeof value === 'string' && SERVICE_ID.test(value); }

// Retain decoded member names before JSON.parse can erase duplicates. Album request
// values use objects, strings and exact nonnegative safe integers, including exponent form.
export function parseStrictAlbumJson(raw: string): unknown {
  let offset = 0;
  const invalid = (): never => { throw new Error('invalid_request'); };
  const space = () => { while (/[\x20\t\r\n]/.test(raw[offset] ?? '') && offset < raw.length) offset++; };
  function string(): string {
    const start = offset++;
    while (offset < raw.length) {
      const c = raw[offset++];
      if (c === '"') return JSON.parse(raw.slice(start, offset)) as string;
      if (c === '\\') offset++;
    }
    return invalid();
  }
  function value(depth: number): unknown {
    space(); if (depth > 3) return invalid();
    if (raw[offset] === '"') return string();
    if (raw[offset] === '{') {
      offset++; space(); const result: Record<string, unknown> = Object.create(null);
      if (raw[offset] === '}') { offset++; return result; }
      for (;;) {
        space(); if (raw[offset] !== '"') return invalid(); const name = string();
        if (Object.hasOwn(result, name)) return invalid(); space(); if (raw[offset++] !== ':') return invalid();
        result[name] = value(depth + 1); space(); const end = raw[offset++];
        if (end === '}') return result; if (end !== ',') return invalid();
      }
    }
    const match = /^(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?/.exec(raw.slice(offset));
    if (!match) return invalid(); offset += match[0].length;
    const exponent = Number(match[4] ?? 0) - (match[3]?.length ?? 0);
    if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 4096) return invalid();
    const digits = BigInt(match[2]! + (match[3] ?? ''));
    const divisor = 10n ** BigInt(Math.abs(exponent));
    if (exponent < 0 && digits % divisor !== 0n) return invalid();
    const integer = (exponent < 0 ? digits / divisor : digits * divisor) * (match[1] ? -1n : 1n);
    if (integer < 0n || integer > BigInt(Number.MAX_SAFE_INTEGER)) return invalid();
    return Number(integer);
  }
  const parsed = value(0); space();
  if (offset !== raw.length) return invalid();
  return parsed;
}

function ensureRequest(parsed: unknown): AlbumEnsureRequest {
  if (!object(parsed) || !keys(parsed, ['schemaVersion', 'desiredTitle', 'candidate'])
    || parsed.schemaVersion !== 1 || !title(parsed.desiredTitle) || !object(parsed.candidate)
    || !keys(parsed.candidate, ['fgaPhotoBindingId', 'expectedVerificationRevision'])
    || !id(parsed.candidate.fgaPhotoBindingId) || !revision(parsed.candidate.expectedVerificationRevision)) throw new Error('invalid_request');
  return { schemaVersion: 1, desiredTitle: parsed.desiredTitle,
    candidate: { fgaPhotoBindingId: parsed.candidate.fgaPhotoBindingId, expectedVerificationRevision: parsed.candidate.expectedVerificationRevision } };
}

export function parseAlbumBindingEnsure(raw: string): AlbumEnsureRequest {
  return ensureRequest(parseStrictAlbumJson(raw));
}

export async function readStrictAlbumJson(request: Request): Promise<unknown> {
  if (!/^application\/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*$/i.test(request.headers.get('Content-Type') ?? '')
    || request.headers.has('Content-Encoding') && request.headers.get('Content-Encoding') !== 'identity'
    || request.headers.has('Transfer-Encoding')
    || request.headers.has('Content-Length') && !/^(?:0|[1-9][0-9]{0,3})$/.test(request.headers.get('Content-Length')!)
    || Number(request.headers.get('Content-Length')) > 4096 || !request.body) throw new Error('invalid_request');
  const reader = request.body.getReader(), parts: Uint8Array[] = []; let size = 0;
  try {
    for (;;) { const { done, value } = await reader.read(); if (done) break;
      size += value.length; if (size > 4096) { await reader.cancel(); throw new Error('invalid_request'); } parts.push(value); }
    if (request.headers.has('Content-Length') && Number(request.headers.get('Content-Length')) !== size) throw new Error('invalid_request');
    const bytes = new Uint8Array(size); let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.length; }
    return parseStrictAlbumJson(new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes));
  } finally { reader.releaseLock(); }
}
export function bindingProjection(row: AlbumBinding, serviceId: string, localId: string): AlbumBinding {
  if (row.schemaVersion !== 1 || !uuid(row.fgaAlbumBindingId) || row.fgaPublishServiceId !== serviceId
    || row.localCollectionIdentifier !== localId || !revision(row.linkedFlickrRevision) || !revision(row.bindingRevision)
    || !revision(row.titleRevision) || !title(row.desiredTitle) || !id(row.firstPhotoBindingId)
    || row.flickrPhotosetId !== null && !id(row.flickrPhotosetId)) throw new Error('integrity');
  return { schemaVersion: 1, fgaAlbumBindingId: row.fgaAlbumBindingId, fgaPublishServiceId: serviceId,
    localCollectionIdentifier: localId, linkedFlickrRevision: row.linkedFlickrRevision, bindingRevision: row.bindingRevision,
    titleRevision: row.titleRevision, desiredTitle: row.desiredTitle, firstPhotoBindingId: row.firstPhotoBindingId, flickrPhotosetId: row.flickrPhotosetId };
}
function obligationProjection(row: AlbumObligation, binding: AlbumBinding): AlbumObligation {
  if (!uuid(row.fgaAlbumObligationId) || row.fgaAlbumBindingId !== binding.fgaAlbumBindingId
    || row.fgaPhotoBindingId !== binding.firstPhotoBindingId || !revision(row.obligationRevision)) throw new Error('integrity');
  return { fgaAlbumObligationId: row.fgaAlbumObligationId, fgaAlbumBindingId: row.fgaAlbumBindingId,
    fgaPhotoBindingId: row.fgaPhotoBindingId, obligationRevision: row.obligationRevision };
}
export function albumBindingFailure(code: string): Response {
  const messages: Record<string, [number, string]> = {
    invalid_request: [400, 'Invalid album binding request.'], invalid_token: [401, 'Invalid installation credential.'],
    resource_not_found: [404, 'Resource not found.'], album_binding_exists: [409, 'Album binding already exists.'],
    stale_binding_revision: [409, 'Album binding revision changed.'],
    stale_photo_revision: [409, 'Photo verification revision changed.'], flickr_link_unavailable: [409, 'The Flickr connection is unavailable.'],
    photo_not_ready: [409, 'Photo proof is not ready.'], album_closed: [409, 'Album is closed.'],
    service_unavailable: [503, 'Service unavailable.'],
  };
  const [status, message] = messages[code] ?? messages.service_unavailable!;
  const safeCode = Object.hasOwn(messages, code) ? code : 'service_unavailable';
  const response = errorResponse(status, safeCode, message, status === 401);
  if (status === 503) response.headers.set('Retry-After', '5'); return response;
}

/** Caller authenticates the current credential with allowPending=false before resource checks. */
export async function albumBindingRequest(env: AlbumBindingsEnv, auth: AdmissionAuth, request: Request,
  serviceId: string, localId: string): Promise<Response> {
  if (env.FGA_ALBUM_BINDINGS_ENABLED !== '1') return albumBindingFailure('service_unavailable');
  const url = new URL(request.url);
  const path = `/api/v001/publish-services/${encodeURIComponent(serviceId)}/album-bindings/${encodeURIComponent(localId)}`;
  if (!SERVICE_ID.test(serviceId) || !OPAQUE_ID.test(localId) || url.pathname !== path || url.search
    || !['GET', 'PUT'].includes(request.method)) return albumBindingFailure('invalid_request');
  let input: AlbumEnsureRequest | undefined;
  try {
    if (request.method === 'GET') {
      if (request.body !== null || request.headers.has('Transfer-Encoding')
        || request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0') return albumBindingFailure('invalid_request');
    } else input = ensureRequest(await readStrictAlbumJson(request));
  } catch { return albumBindingFailure('invalid_request'); }
  try {
    if (!input) return Response.json(bindingProjection(await readAlbumBinding(env.DB, auth, serviceId, localId), serviceId, localId), { headers: SECURITY });
    const result = await ensureAlbumBinding(env.DB, auth, serviceId, localId, input);
    const binding = bindingProjection(result.binding, serviceId, localId);
    return Response.json({ schemaVersion: 1, binding, obligation: obligationProjection(result.obligation, binding) },
      { status: result.created ? 201 : 200, headers: { ...SECURITY, ...(result.created ? { Location: path } : {}) } });
  } catch (error) { return albumBindingFailure(error instanceof AlbumBindingStoreError ? error.message : 'service_unavailable'); }
}
