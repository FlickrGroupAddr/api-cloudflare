import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse, NOW_US_SQL } from './installations.ts';
import { linkedGrant, sameGrant, withGrant, signedRead, rejectCurrentGrant,
  type GrantSnapshot, type SecretReads, type FlickrFetch } from './flickr_reads.ts';
import { PHOTO_ID, photoObject, boundedPhotoRead, photoReadBody } from './existing_photo_discovery.ts';

export interface UploadPhotoBindingEnv extends SecretReads { DB: SqlStore; FGA_UPLOAD_PHOTO_BINDING_ENABLED?: string; }
interface Credential { userId: string; versionId: string; revision: string; }
interface Authorization { photoId: string | null; }
interface Binding { fgaPhotoBindingId: string; flickrPhotoId: string; source_kind: string;
  linkedFlickrRevision: number; verificationRevision: number; verifiedAt: string; }
class BindingError extends Error {}
const SECURITY = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
const ID_SCHEMA = { type: 'string', minLength: 1, maxLength: 128, pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' } as const;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
export const UPLOAD_PHOTO_BINDING_REQUEST_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'flickrPhotoId'], properties: { schemaVersion: { const: 1 }, flickrPhotoId: ID_SCHEMA } } as const;
export const UPLOAD_PHOTO_BINDING_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'fgaPhotoBindingId', 'sourceKind', 'flickrPhotoId', 'linkedFlickrRevision', 'verificationRevision', 'verifiedAt'],
  properties: { schemaVersion: { const: 1 }, fgaPhotoBindingId: ID_SCHEMA,
    sourceKind: { type: 'string', enum: ['fga_direct_upload', 'existing_public_flickr_photo'] }, flickrPhotoId: ID_SCHEMA,
    linkedFlickrRevision: REVISION, verificationRevision: REVISION, verifiedAt: { type: 'string', format: 'date-time' } } } as const;
export const UPLOAD_PHOTO_BINDING_ROUTES = [{ id: 'uploadPhotoBinding', method: 'PUT',
  pathPattern: '/api/v001/upload-authorizations/{uploadAuthorizationId}/photo-binding', owner: 'fga_api_backend',
  routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
  expectedChallenge: 'Bearer realm="fga-api"', handler: 'upload_photo_binding', auth: 'installation_bearer', allowPending: false,
  response: UPLOAD_PHOTO_BINDING_RESPONSE_SCHEMA, successStatuses: [200, 201], request: UPLOAD_PHOTO_BINDING_REQUEST_SCHEMA }] as const;
export const UPLOAD_PHOTO_BINDING_RELEASE_METADATA = { enabledFlag: 'FGA_UPLOAD_PHOTO_BINDING_ENABLED', defaultValue: '0', hostQualified: false } as const;

async function credential(db: SqlStore, auth: AdmissionAuth): Promise<Credential | null> {
  return db.prepare(`SELECT i.user_id userId,v.version_id versionId,CAST(i.revision AS TEXT) revision
    FROM installations i JOIN installation_credential_versions v ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
    WHERE i.installation_id=? AND i.state='active' AND i.credential_class='lrc_plugin' AND v.state='current' AND v.credential_digest=?`)
    .bind(auth.installationId, auth.credentialDigest).first<Credential>();
}
function sameCredential(a: Credential, b: Credential | null): boolean {
  return b !== null && a.userId === b.userId && a.versionId === b.versionId && a.revision === b.revision;
}
async function authorization(db: SqlStore, auth: AdmissionAuth, userId: string, id: string): Promise<Authorization | null> {
  return db.prepare(`SELECT photo_id photoId FROM upload_authorizations WHERE authorization_id=? AND installation_id=? AND user_id=?`)
    .bind(id, auth.installationId, userId).first<Authorization>();
}
const PROJECTION = `SELECT b.binding_id fgaPhotoBindingId,b.photo_id flickrPhotoId,b.source_kind,
  b.link_revision linkedFlickrRevision,b.verification_revision verificationRevision,
  strftime('%Y-%m-%dT%H:%M:',b.verified_at_us/1000000,'unixepoch')||printf('%09.6f',(b.verified_at_us%60000000)/1000000.0)||'Z' verifiedAt
  FROM upload_photo_binding_events e JOIN photo_bindings b ON b.binding_id=e.binding_id`;
function success(row: Binding, created: boolean, authorizationId: string): Response {
  if (!Number.isSafeInteger(row.linkedFlickrRevision) || row.linkedFlickrRevision < 1
    || !Number.isSafeInteger(row.verificationRevision) || row.verificationRevision < 1) throw new BindingError('upstream_unavailable');
  const { source_kind, ...body } = row;
  return Response.json({ schemaVersion: 1, ...body,
    sourceKind: source_kind === 'existing_public' ? 'existing_public_flickr_photo' : 'fga_direct_upload' },
  { status: created ? 201 : 200, headers: { ...SECURITY,
    ...(created ? { Location: `/api/v001/upload-authorizations/${encodeURIComponent(authorizationId)}/photo-binding` } : {}) } });
}
function failure(code: string): Response {
  if (code === 'invalid_token') return errorResponse(401, code, 'Invalid installation credential.', true);
  if (code === 'authorization_not_found') return errorResponse(404, code, 'Upload authorization not found.');
  if (code === 'invalid_request') return errorResponse(400, code, 'Invalid photo proof request.');
  if (code === 'invalid_photo') return errorResponse(422, code, 'Invalid Flickr photo ID.');
  if (code === 'photo_owner_mismatch') return errorResponse(403, code, 'The linked account does not own this photo.');
  if (code === 'photo_binding_conflict' || code === 'flickr_link_changed') return errorResponse(409, code, 'The photo binding or Flickr connection changed.');
  const response = errorResponse(503, 'upload_photo_binding_unavailable', 'Photo verification is unavailable.');
  response.headers.set('Retry-After', '5'); return response;
}

/** A complete exact-photo observation. Private uploads remain valid under ADR0011. */
async function observe(env: UploadPhotoBindingEnv, auth: AdmissionAuth, grant: GrantSnapshot, photoId: string, fetcher: FlickrFetch): Promise<number> {
  return boundedPhotoRead(async signal => {
    const result = await withGrant(env.DB, auth, env, grant,
      (pair, app) => photoReadBody(signedRead('flickr.photos.getInfo', photoId, pair, app), fetcher, signal));
    if (!photoObject(result)) throw new BindingError('upstream_unavailable');
    if (result.stat === 'fail' && typeof result.message === 'string' && result.message.length > 0) {
      if (result.code === 98 || result.code === 99) {
        await rejectCurrentGrant(env.DB, auth, grant); throw new BindingError('flickr_link_changed');
      }
    }
    if (result.stat !== 'ok' || !photoObject(result.photo)) throw new BindingError('upstream_unavailable');
    const photo = result.photo;
    if (photo.id !== photoId || !photoObject(photo.owner) || typeof photo.owner.nsid !== 'string'
      || !PHOTO_ID.test(photo.owner.nsid) || !photoObject(photo.visibility)
      || ![0, 1, '0', '1'].includes(photo.visibility.ispublic as number | string)
      || photo.media !== undefined && photo.media !== 'photo') throw new BindingError('upstream_unavailable');
    if (photo.owner.nsid !== grant.ownerNsid) throw new BindingError('photo_owner_mismatch');
    return Number(photo.visibility.ispublic);
  });
}

async function commit(env: UploadPhotoBindingEnv, auth: AdmissionAuth, current: Credential, grant: GrantSnapshot,
  authorizationId: string, photoId: string, isPublic: number): Promise<Response> {
  const db = env.DB, bindingId = crypto.randomUUID(), tx = crypto.randomUUID();
  const params = [auth.installationId, auth.credentialDigest, current.userId, current.versionId, current.revision,
    grant.ownerNsid, grant.revision, grant.generation, authorizationId, photoId, bindingId, tx, isPublic];
  const sql = (text: string) => db.prepare(`WITH input AS(SELECT ?1 i,?2 d,?3 u,?4 v,?5 r,?6 o,?7 l,?8 g,?9 a,?10 p,?11 b,?12 t,?13 public) ${text}`).bind(...params);
  const pending = `NOT EXISTS(SELECT 1 FROM upload_photo_binding_events WHERE authorization_id=?9)`;
  const results = await db.batch([
    sql(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?12,EXISTS(
      SELECT 1 FROM installations i JOIN installation_credential_versions v ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
      JOIN flickr_links l ON l.user_id=i.user_id JOIN flickr_native_credentials n ON n.user_id=l.user_id
      JOIN upload_authorizations a ON a.installation_id=i.installation_id AND a.user_id=i.user_id
      WHERE i.installation_id=?1 AND i.user_id=?3 AND i.state='active' AND i.credential_class='lrc_plugin'
        AND i.revision=CAST(?5 AS INTEGER) AND v.version_id=?4 AND v.state='current' AND v.credential_digest=?2
        AND l.state='linked' AND l.owner_nsid=?6 AND l.link_revision=CAST(?7 AS INTEGER)
        AND n.link_revision=l.link_revision AND n.active_generation=?8 AND n.operation_id IS NULL
        AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete')
        AND a.authorization_id=?9 AND (a.photo_id IS NULL OR a.photo_id=?10))
      AND NOT EXISTS(SELECT 1 FROM photo_bindings WHERE photo_id=?10 AND (user_id<>?3 OR owner_nsid<>?6
        OR (verification_revision>=9007199254740991 AND ${pending})))
      AND NOT EXISTS(SELECT 1 FROM upload_photo_binding_events WHERE authorization_id=?9 AND link_revision<>CAST(?7 AS INTEGER))`),
    sql(`UPDATE upload_authorizations SET photo_id=?10 WHERE authorization_id=?9 AND photo_id IS NULL`),
    sql(`INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind)
      SELECT ?11,?3,?10,?6,CAST(?7 AS INTEGER),1,'upload' WHERE NOT EXISTS(SELECT 1 FROM photo_bindings WHERE photo_id=?10)`),
    sql(`UPDATE photo_bindings SET link_revision=CAST(?7 AS INTEGER),verification_revision=verification_revision+1,verified_at_us=${NOW_US_SQL}
      WHERE photo_id=?10 AND binding_id<>?11 AND ${pending}`),
    sql(`INSERT INTO upload_photo_binding_events(authorization_id,binding_id,link_revision,verification_revision,observed_public,verified_at_us)
      SELECT ?9,binding_id,link_revision,verification_revision,?13,verified_at_us FROM photo_bindings WHERE photo_id=?10 AND ${pending}`),
    sql(`${PROJECTION} WHERE e.authorization_id=?9`),
    sql('DELETE FROM transaction_guards WHERE transaction_id=?12'),
  ]);
  const row = results[5].results[0] as unknown as Binding | undefined;
  if (!row) throw new BindingError('commit_unconfirmed');
  return success(row, results[1].meta.changes === 1, authorizationId);
}

/** Does not create group/Album work or replay the Flickr upload. */
export async function uploadPhotoBindingRequest(env: UploadPhotoBindingEnv, auth: AdmissionAuth, authorizationId: string,
  value: unknown, fetcher: FlickrFetch): Promise<Response> {
  if (env.FGA_UPLOAD_PHOTO_BINDING_ENABLED !== '1') return errorResponse(503, 'service_unavailable', 'Service unavailable.');
  let current: Credential | undefined, grant: GrantSnapshot | undefined, photoId: string | undefined;
  try {
    if (!photoObject(value) || Object.keys(value).sort().join() !== 'flickrPhotoId,schemaVersion' || value.schemaVersion !== 1)
      throw new BindingError('invalid_request');
    if (typeof value.flickrPhotoId !== 'string' || !PHOTO_ID.test(value.flickrPhotoId)) throw new BindingError('invalid_photo');
    photoId = value.flickrPhotoId;
    const found = await credential(env.DB, auth); if (!found) throw new BindingError('invalid_token'); current = found;
    const issued = PHOTO_ID.test(authorizationId) ? await authorization(env.DB, auth, current.userId, authorizationId) : null;
    if (!issued) throw new BindingError('authorization_not_found');
    if (issued.photoId !== null && issued.photoId !== photoId) throw new BindingError('photo_binding_conflict');
    const linked = await linkedGrant(env.DB, auth);
    if (!linked || !/^[1-9][0-9]*$/.test(linked.revision) || BigInt(linked.revision) > BigInt(Number.MAX_SAFE_INTEGER))
      throw new BindingError('flickr_link_changed');
    grant = linked;
    if (issued.photoId === photoId) {
      const row = await env.DB.prepare(`${PROJECTION} WHERE e.authorization_id=? AND e.link_revision=? AND b.link_revision=?`)
        .bind(authorizationId, Number(grant.revision), Number(grant.revision)).first<Binding>();
      if (!row) throw new BindingError('flickr_link_changed');
      if (!sameCredential(current, await credential(env.DB, auth))) throw new BindingError('invalid_token');
      if (!sameGrant(grant, await linkedGrant(env.DB, auth))) throw new BindingError('flickr_link_changed');
      return success(row, false, authorizationId);
    }
    const isPublic = await observe(env, auth, grant, photoId, fetcher);
    return await commit(env, auth, current, grant, authorizationId, photoId, isPublic);
  } catch (error) {
    // Resolve races from current durable authority; never expose exception or Flickr metadata.
    try {
      if (current && !sameCredential(current, await credential(env.DB, auth))) return failure('invalid_token');
      if (grant && !sameGrant(grant, await linkedGrant(env.DB, auth))) return failure('flickr_link_changed');
      if (current && photoId) {
        const latest = await authorization(env.DB, auth, current.userId, authorizationId);
        if (latest && latest.photoId !== null && latest.photoId !== photoId) return failure('photo_binding_conflict');
      }
    } catch { return failure('upstream_unavailable'); }
    return failure(error instanceof BindingError ? error.message : 'upstream_unavailable');
  }
}
