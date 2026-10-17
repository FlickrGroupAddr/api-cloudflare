import type { AdmissionAuth, SqlStore } from './admission.ts';
import { SERVICE_ID } from './publish_services.ts';
import { ALBUM_BINDING_ADMISSION_RESPONSE_SCHEMA, parseStrictAlbumJson, readStrictAlbumJson,
  bindingProjection, albumBindingFailure } from './album_bindings.ts';
import { associateAlbumPhoto, AlbumObligationStoreError, type AlbumAssociateRequest } from './album_obligation_store.ts';
import type { AlbumBinding, AlbumObligation } from './album_binding_store.ts';

export interface AlbumObligationsEnv { DB: SqlStore; FGA_ALBUM_OBLIGATIONS_ENABLED?: string; }
const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
const SECURITY = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
export const ALBUM_ASSOCIATE_REQUEST_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'expectedBindingRevision', 'expectedVerificationRevision'],
  properties: { schemaVersion: { const: 1 }, expectedBindingRevision: REVISION, expectedVerificationRevision: REVISION } } as const;
export const ALBUM_OBLIGATIONS_ROUTES = [
  { id: 'album_photo_association', method: 'PUT', pathPattern: '/api/v001/album-bindings/{bindingId}/photo-associations/{photoBindingId}',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'album_photo_association', auth: 'installation_bearer', allowPending: false,
    request: ALBUM_ASSOCIATE_REQUEST_SCHEMA, response: ALBUM_BINDING_ADMISSION_RESPONSE_SCHEMA, successStatuses: [200, 201] },
] as const;
export const ALBUM_OBLIGATIONS_RELEASE_METADATA = { enabledFlag: 'FGA_ALBUM_OBLIGATIONS_ENABLED', defaultValue: '0', hostQualified: false } as const;

function revision(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1; }
function associate(value: unknown): AlbumAssociateRequest {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid_request');
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== 3 || !Object.hasOwn(row, 'schemaVersion') || !Object.hasOwn(row, 'expectedBindingRevision')
    || !Object.hasOwn(row, 'expectedVerificationRevision') || row.schemaVersion !== 1
    || !revision(row.expectedBindingRevision) || !revision(row.expectedVerificationRevision)) throw new Error('invalid_request');
  return { schemaVersion: 1, expectedBindingRevision: row.expectedBindingRevision, expectedVerificationRevision: row.expectedVerificationRevision };
}

/** Preserve raw duplicate names and exact numeric tokens before closed-schema validation. */
export function parseAlbumAssociate(raw: string): AlbumAssociateRequest { return associate(parseStrictAlbumJson(raw)); }

function receipt(row: AlbumObligation, binding: AlbumBinding, photoBindingId: string): AlbumObligation {
  if (!SERVICE_ID.test(row.fgaAlbumObligationId) || row.fgaAlbumBindingId !== binding.fgaAlbumBindingId
    || row.fgaPhotoBindingId !== photoBindingId || !revision(row.obligationRevision)) throw new Error('integrity');
  return { fgaAlbumObligationId: row.fgaAlbumObligationId, fgaAlbumBindingId: row.fgaAlbumBindingId,
    fgaPhotoBindingId: row.fgaPhotoBindingId, obligationRevision: row.obligationRevision };
}

/** The Worker authenticates the current non-pending credential before resource checks.
 * This boundary admits a durable natural-key obligation only; it performs no provider I/O. */
export async function albumObligationRequest(env: AlbumObligationsEnv, auth: AdmissionAuth, request: Request,
  bindingId: string, photoBindingId: string): Promise<Response> {
  if (env.FGA_ALBUM_OBLIGATIONS_ENABLED !== '1') return albumBindingFailure('service_unavailable');
  const url = new URL(request.url);
  const path = `/api/v001/album-bindings/${encodeURIComponent(bindingId)}/photo-associations/${encodeURIComponent(photoBindingId)}`;
  if (!SERVICE_ID.test(bindingId) || !OPAQUE_ID.test(photoBindingId) || url.pathname !== path || url.search
    || request.method !== 'PUT') return albumBindingFailure('invalid_request');
  let input: AlbumAssociateRequest;
  try { input = associate(await readStrictAlbumJson(request)); }
  catch { return albumBindingFailure('invalid_request'); }
  try {
    const result = await associateAlbumPhoto(env.DB, auth, bindingId, photoBindingId, input);
    if (result.binding.fgaAlbumBindingId !== bindingId || !SERVICE_ID.test(result.binding.fgaPublishServiceId)
      || !OPAQUE_ID.test(result.binding.localCollectionIdentifier) || typeof result.created !== 'boolean') throw new Error('integrity');
    const binding = bindingProjection(result.binding, result.binding.fgaPublishServiceId, result.binding.localCollectionIdentifier);
    return Response.json({ schemaVersion: 1, binding, obligation: receipt(result.obligation, binding, photoBindingId) },
      { status: result.created ? 201 : 200, headers: SECURITY });
  } catch (error) { return albumBindingFailure(error instanceof AlbumObligationStoreError ? error.message : 'service_unavailable'); }
}
