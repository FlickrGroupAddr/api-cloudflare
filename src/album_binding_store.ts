import type { AdmissionAuth, SqlStore } from './admission.ts';
import { NOW_US_SQL } from './installations.ts';

export interface AlbumBinding {
  schemaVersion: 1;
  fgaAlbumBindingId: string;
  fgaPublishServiceId: string;
  localCollectionIdentifier: string;
  linkedFlickrRevision: number;
  bindingRevision: number;
  titleRevision: number;
  desiredTitle: string;
  firstPhotoBindingId: string;
  flickrPhotosetId: string | null;
}
export interface AlbumObligation {
  fgaAlbumObligationId: string;
  fgaAlbumBindingId: string;
  fgaPhotoBindingId: string;
  obligationRevision: number;
}
export interface AlbumEnsureRequest {
  schemaVersion: 1;
  desiredTitle: string;
  candidate: { fgaPhotoBindingId: string; expectedVerificationRevision: number };
}
export class AlbumBindingStoreError extends Error {}

// Every admission predicate and the returned snapshot run inside one D1 batch.
// No preliminary authority read can authorize the conditional INSERT. The
// current credential version, installation revision and native generation are
// selected here from the same owning database at its serial transaction point.
const CONTEXT = `WITH context AS (
 SELECT i.user_id,i.revision installation_revision,v.version_id,n.active_generation,
  s.service_id,s.link_revision,s.owner_nsid,
  COALESCE(l.state='linked' AND l.link_revision BETWEEN 1 AND 9007199254740991
   AND l.link_revision=s.link_revision AND l.owner_nsid=s.owner_nsid
   AND n.link_revision=l.link_revision AND n.verified_owner_nsid=l.owner_nsid
   AND n.operation_id IS NULL AND length(n.active_generation) BETWEEN 1 AND 128
   AND n.verified_permission IN ('write','delete')
   AND c.state='linked' AND c.local_state='available' AND c.operation_id IS NULL
   AND c.verified_permission IN ('write','delete') AND c.external_removal=0,0) link_ready,
  p.binding_id photo_binding_id,p.photo_id,p.verification_revision,
  COALESCE(p.owner_nsid=s.owner_nsid AND p.link_revision=s.link_revision
   AND p.binding_id<>'0' AND p.photo_id<>'0'
   AND p.verification_revision BETWEEN 1 AND 9007199254740991
   AND p.verified_at_us BETWEEN 0 AND ${NOW_US_SQL}
   AND (EXISTS(SELECT 1 FROM photo_binding_events e WHERE e.binding_id=p.binding_id
     AND e.verification_revision=p.verification_revision AND e.kind='existing_public_verified')
    OR EXISTS(SELECT 1 FROM upload_photo_binding_events e WHERE e.binding_id=p.binding_id
     AND e.verification_revision=p.verification_revision AND e.link_revision=p.link_revision
     AND e.verified_at_us=p.verified_at_us)),0) photo_ready,
  b.binding_id,b.first_photo_binding_id,b.binding_revision,b.title_revision,b.desired_title,
  b.flickr_photoset_id,b.state,b.local_collection_id,
  o.obligation_id,o.photo_binding_id obligation_photo_binding_id,o.obligation_revision
 FROM installations i JOIN installation_credential_versions v
  ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
 LEFT JOIN publish_service_identities s ON s.service_id=?3 AND s.user_id=i.user_id
 LEFT JOIN flickr_links l ON l.user_id=i.user_id
 LEFT JOIN flickr_native_credentials n ON n.user_id=i.user_id
 LEFT JOIN flickr_connection_state c ON c.user_id=i.user_id
 LEFT JOIN photo_bindings p ON p.binding_id=?5 AND p.user_id=i.user_id
 LEFT JOIN album_bindings b ON b.user_id=i.user_id AND b.service_id=s.service_id AND b.local_collection_id=?4
 LEFT JOIN album_photo_obligations o ON o.obligation_id=b.first_obligation_id
  AND o.album_binding_id=b.binding_id AND o.photo_binding_id=b.first_photo_binding_id AND o.photo_id=b.first_photo_id
 WHERE i.installation_id=?1 AND v.credential_digest=?2 AND i.state='active'
  AND i.credential_class='lrc_plugin' AND i.revision BETWEEN 1 AND 9007199254740991
  AND v.state='current' AND v.expires_at_us IS NULL
) `;
const PROJECTION = `SELECT service_id fgaPublishServiceId,local_collection_id localCollectionIdentifier,
 link_revision linkedFlickrRevision,binding_id fgaAlbumBindingId,binding_revision bindingRevision,
 title_revision titleRevision,desired_title desiredTitle,first_photo_binding_id firstPhotoBindingId,
 flickr_photoset_id flickrPhotosetId,obligation_id fgaAlbumObligationId,
 obligation_photo_binding_id fgaPhotoBindingId,obligation_revision obligationRevision,`;
const ENSURE_ERROR = `CASE
 WHEN service_id IS NULL OR photo_binding_id IS NULL THEN 'resource_not_found'
 WHEN link_ready<>1 THEN 'flickr_link_unavailable'
 WHEN photo_ready<>1 THEN 'photo_not_ready'
 WHEN binding_id IS NOT NULL AND first_photo_binding_id<>?5 THEN 'album_binding_exists'
 WHEN binding_id IS NULL AND verification_revision<>?6 THEN 'stale_photo_revision'
 WHEN binding_id IS NOT NULL AND obligation_id IS NULL THEN 'service_unavailable'
 ELSE NULL END`;
interface Row extends Omit<AlbumBinding, 'schemaVersion'> {
  fgaAlbumObligationId: string | null;
  fgaPhotoBindingId: string | null;
  obligationRevision: number | null;
  error: string | null;
}
const OPAQUE = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function reject(code: string): never { throw new AlbumBindingStoreError(code); }
function checked(row: Row | undefined | null): Row {
  if (!row) reject('invalid_token');
  if (row.error) reject(row.error);
  if (!UUID.test(row.fgaAlbumBindingId) || !UUID.test(row.fgaPublishServiceId)
    || !OPAQUE.test(row.localCollectionIdentifier) || !OPAQUE.test(row.firstPhotoBindingId)
    || ![row.linkedFlickrRevision, row.bindingRevision, row.titleRevision].every(x => Number.isSafeInteger(x) && x >= 1)
    || typeof row.desiredTitle !== 'string' || [...row.desiredTitle].length < 1 || [...row.desiredTitle].length > 1000
    || row.flickrPhotosetId !== null && !OPAQUE.test(row.flickrPhotosetId)) reject('service_unavailable');
  return row;
}
function binding(row: Row): AlbumBinding {
  return { schemaVersion: 1, fgaAlbumBindingId: row.fgaAlbumBindingId, fgaPublishServiceId: row.fgaPublishServiceId,
    localCollectionIdentifier: row.localCollectionIdentifier, linkedFlickrRevision: row.linkedFlickrRevision,
    bindingRevision: row.bindingRevision, titleRevision: row.titleRevision, desiredTitle: row.desiredTitle,
    firstPhotoBindingId: row.firstPhotoBindingId, flickrPhotosetId: row.flickrPhotosetId };
}
function authority(auth: AdmissionAuth, serviceId: string, localId: string): void {
  if (!OPAQUE.test(auth.installationId) || !/^[0-9a-f]{64}$/.test(auth.credentialDigest)) reject('invalid_token');
  if (!UUID.test(serviceId) || !OPAQUE.test(localId)) reject('invalid_request');
}

/** Snapshot only: no row allocation, revision change or work scheduling. */
export async function readAlbumBinding(db: SqlStore, auth: AdmissionAuth, serviceId: string, localId: string): Promise<AlbumBinding> {
  authority(auth, serviceId, localId);
  try {
    const row = await db.prepare(CONTEXT + PROJECTION + `CASE
      WHEN service_id IS NULL OR binding_id IS NULL THEN 'resource_not_found'
      WHEN link_ready<>1 THEN 'flickr_link_unavailable'
      WHEN obligation_id IS NULL THEN 'service_unavailable' ELSE NULL END error FROM context`)
      .bind(auth.installationId, auth.credentialDigest, serviceId, localId, '').first<Row>();
    return binding(checked(row));
  } catch (error) {
    if (error instanceof AlbumBindingStoreError) throw error;
    reject('service_unavailable');
  }
}

/** The first committed natural key wins. Its trigger inserts its receipt and
 * event atomically. Matching replay ignores the incoming title/proof revision,
 * including after local archival, and performs no write. */
export async function ensureAlbumBinding(db: SqlStore, auth: AdmissionAuth, serviceId: string, localId: string,
  value: AlbumEnsureRequest): Promise<{ created: boolean; binding: AlbumBinding; obligation: AlbumObligation }> {
  authority(auth, serviceId, localId);
  if (value.schemaVersion !== 1 || !OPAQUE.test(value.candidate.fgaPhotoBindingId)
    || !Number.isSafeInteger(value.candidate.expectedVerificationRevision) || value.candidate.expectedVerificationRevision < 1
    || typeof value.desiredTitle !== 'string' || [...value.desiredTitle].length < 1 || [...value.desiredTitle].length > 1000
    || /[\p{Cc}\p{Cs}]/u.test(value.desiredTitle)) reject('invalid_request');
  const id = crypto.randomUUID(), obligationId = crypto.randomUUID();
  try {
    const result = await db.batch([
      db.prepare(CONTEXT + `INSERT INTO album_bindings(binding_id,user_id,service_id,local_collection_id,
        link_revision,owner_nsid,first_photo_binding_id,first_photo_id,first_obligation_id,desired_title)
        SELECT ?8,user_id,service_id,?4,link_revision,owner_nsid,photo_binding_id,photo_id,?9,?7 FROM context
        WHERE binding_id IS NULL AND (${ENSURE_ERROR}) IS NULL`)
        .bind(auth.installationId, auth.credentialDigest, serviceId, localId,
          value.candidate.fgaPhotoBindingId, value.candidate.expectedVerificationRevision, value.desiredTitle, id, obligationId),
      db.prepare(CONTEXT + PROJECTION + ENSURE_ERROR + ' error FROM context')
        .bind(auth.installationId, auth.credentialDigest, serviceId, localId,
          value.candidate.fgaPhotoBindingId, value.candidate.expectedVerificationRevision),
    ]);
    const row = checked(result[1].results[0] as unknown as Row | undefined);
    if (!row.fgaAlbumObligationId || !UUID.test(row.fgaAlbumObligationId) || row.fgaPhotoBindingId !== row.firstPhotoBindingId
      || !Number.isSafeInteger(row.obligationRevision) || row.obligationRevision! < 1) reject('service_unavailable');
    return { created: row.fgaAlbumBindingId === id, binding: binding(row), obligation: {
      fgaAlbumObligationId: row.fgaAlbumObligationId, fgaAlbumBindingId: row.fgaAlbumBindingId,
      fgaPhotoBindingId: row.fgaPhotoBindingId, obligationRevision: row.obligationRevision! } };
  } catch (error) {
    if (error instanceof AlbumBindingStoreError) throw error;
    reject('service_unavailable');
  }
}
