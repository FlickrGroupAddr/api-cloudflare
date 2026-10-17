import type { AdmissionAuth, SqlStore } from './admission.ts';
import type { AlbumBinding, AlbumObligation } from './album_binding_store.ts';
import { NOW_US_SQL } from './installations.ts';

export interface AlbumAssociateRequest {
  schemaVersion: 1;
  expectedBindingRevision: number;
  expectedVerificationRevision: number;
}
export class AlbumObligationStoreError extends Error {}

// Authentication and every admission fence are selected at the same owning D1
// transaction point as the conditional INSERT, never from a preliminary read.
const CONTEXT = `WITH context AS (
 SELECT i.user_id,b.binding_id,b.service_id,b.local_collection_id,b.link_revision,
  b.binding_revision,b.title_revision,b.desired_title,b.first_photo_binding_id,b.flickr_photoset_id,b.state,
  s.service_id owned_service_id,p.binding_id photo_binding_id,p.photo_id,p.verification_revision,
  COALESCE(l.state='linked' AND l.link_revision BETWEEN 1 AND 9007199254740991
   AND l.link_revision=s.link_revision AND l.owner_nsid=s.owner_nsid
   AND b.link_revision=s.link_revision AND b.owner_nsid=s.owner_nsid
   AND n.link_revision=l.link_revision AND n.verified_owner_nsid=l.owner_nsid
   AND n.operation_id IS NULL AND length(n.active_generation) BETWEEN 1 AND 128
   AND n.verified_permission IN ('write','delete')
   AND c.state='linked' AND c.local_state='available' AND c.operation_id IS NULL
   AND c.verified_permission IN ('write','delete') AND c.external_removal=0,0) link_ready,
  COALESCE(p.owner_nsid=b.owner_nsid AND p.link_revision=b.link_revision
   AND p.binding_id<>'0' AND p.photo_id<>'0'
   AND p.verification_revision BETWEEN 1 AND 9007199254740991
   AND p.verified_at_us BETWEEN 0 AND ${NOW_US_SQL}
   AND (EXISTS(SELECT 1 FROM photo_binding_events e WHERE e.binding_id=p.binding_id
     AND e.verification_revision=p.verification_revision AND e.kind='existing_public_verified')
    OR EXISTS(SELECT 1 FROM upload_photo_binding_events e WHERE e.binding_id=p.binding_id
     AND e.verification_revision=p.verification_revision AND e.link_revision=p.link_revision
     AND e.verified_at_us=p.verified_at_us)),0) photo_ready,
  o.obligation_id,o.obligation_revision,o.photo_id obligation_photo_id,
  o.admission_binding_revision,o.state obligation_state,o.local_relationship,
  COALESCE(EXISTS(SELECT 1 FROM album_obligation_events e WHERE e.obligation_id=o.obligation_id
   AND e.obligation_revision=o.obligation_revision AND e.state=o.state
   AND e.local_relationship=o.local_relationship),0) obligation_audited
 FROM installations i JOIN installation_credential_versions v
  ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
 LEFT JOIN album_bindings b ON b.binding_id=?3 AND b.user_id=i.user_id
 LEFT JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=i.user_id
 LEFT JOIN flickr_links l ON l.user_id=i.user_id
 LEFT JOIN flickr_native_credentials n ON n.user_id=i.user_id
 LEFT JOIN flickr_connection_state c ON c.user_id=i.user_id
 LEFT JOIN photo_bindings p ON p.binding_id=?4 AND p.user_id=i.user_id
 LEFT JOIN album_photo_obligations o ON o.album_binding_id=b.binding_id AND o.photo_binding_id=p.binding_id
 WHERE i.installation_id=?1 AND v.credential_digest=?2 AND i.state='active'
  AND i.credential_class='lrc_plugin' AND i.revision BETWEEN 1 AND 9007199254740991
  AND v.state='current' AND v.expires_at_us IS NULL
) `;
const ERROR = `CASE
 WHEN binding_id IS NULL OR owned_service_id IS NULL OR photo_binding_id IS NULL THEN 'resource_not_found'
 WHEN link_ready<>1 THEN 'flickr_link_unavailable'
 WHEN photo_ready<>1 THEN 'photo_not_ready'
 WHEN obligation_id IS NOT NULL AND (obligation_photo_id<>photo_id OR obligation_audited<>1
  OR admission_binding_revision>binding_revision
  OR (state='local_collection_removed_remote_preserved' AND local_relationship<>'archived')) THEN 'service_unavailable'
 WHEN obligation_id IS NOT NULL THEN NULL
 WHEN state='local_collection_removed_remote_preserved' THEN 'album_closed'
 WHEN binding_revision<>?5 THEN 'stale_binding_revision'
 WHEN verification_revision<>?6 THEN 'stale_photo_revision'
 WHEN binding_revision>=9007199254740991 THEN 'service_unavailable'
 ELSE NULL END`;
const PROJECTION = `SELECT service_id fgaPublishServiceId,local_collection_id localCollectionIdentifier,
 link_revision linkedFlickrRevision,binding_id fgaAlbumBindingId,binding_revision bindingRevision,
 title_revision titleRevision,desired_title desiredTitle,first_photo_binding_id firstPhotoBindingId,
 flickr_photoset_id flickrPhotosetId,photo_binding_id fgaPhotoBindingId,
 obligation_id fgaAlbumObligationId,obligation_revision obligationRevision,`;
interface Row extends Omit<AlbumBinding, 'schemaVersion'> {
  fgaAlbumObligationId: string | null;
  fgaPhotoBindingId: string | null;
  obligationRevision: number | null;
  error: string | null;
}
const OPAQUE = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function reject(code: string): never { throw new AlbumObligationStoreError(code); }
function revision(value: number): boolean { return Number.isSafeInteger(value) && value >= 1; }

/** One natural-key receipt per exact binding/photo. A replay rechecks current
 * authority and proof, ignores old expected revisions and performs no write. */
export async function associateAlbumPhoto(db: SqlStore, auth: AdmissionAuth, bindingId: string, photoBindingId: string,
  value: AlbumAssociateRequest): Promise<{ created: boolean; binding: AlbumBinding; obligation: AlbumObligation }> {
  if (!OPAQUE.test(auth.installationId) || !/^[0-9a-f]{64}$/.test(auth.credentialDigest)) reject('invalid_token');
  if (!UUID.test(bindingId) || !OPAQUE.test(photoBindingId) || value.schemaVersion !== 1
    || !revision(value.expectedBindingRevision) || !revision(value.expectedVerificationRevision)) reject('invalid_request');
  const id = crypto.randomUUID();
  const args = [auth.installationId, auth.credentialDigest, bindingId, photoBindingId,
    value.expectedBindingRevision, value.expectedVerificationRevision];
  try {
    const result = await db.batch([
      db.prepare(CONTEXT + `INSERT INTO album_photo_obligations
        (obligation_id,album_binding_id,photo_binding_id,photo_id,admission_binding_revision,state)
        SELECT ?7,binding_id,photo_binding_id,photo_id,binding_revision+1,
         CASE WHEN flickr_photoset_id IS NULL THEN 'waiting_for_album' ELSE 'attachment_pending' END
        FROM context WHERE obligation_id IS NULL AND (${ERROR}) IS NULL`).bind(...args, id),
      db.prepare(CONTEXT + PROJECTION + ERROR + ' error FROM context').bind(...args),
    ]);
    const row = result[1].results[0] as unknown as Row | undefined;
    if (!row) reject('invalid_token');
    if (row.error) reject(row.error);
    if (row.fgaAlbumBindingId !== bindingId || row.fgaPhotoBindingId !== photoBindingId
      || !UUID.test(row.fgaPublishServiceId) || !OPAQUE.test(row.localCollectionIdentifier)
      || !OPAQUE.test(row.firstPhotoBindingId) || !row.fgaAlbumObligationId || !UUID.test(row.fgaAlbumObligationId)
      || ![row.linkedFlickrRevision,row.bindingRevision,row.titleRevision].every(revision)
      || row.obligationRevision === null || !revision(row.obligationRevision)
      || typeof row.desiredTitle !== 'string' || [...row.desiredTitle].length < 1 || [...row.desiredTitle].length > 1000
      || /[\p{Cc}\p{Cs}]/u.test(row.desiredTitle)
      || row.flickrPhotosetId !== null && !OPAQUE.test(row.flickrPhotosetId)) reject('service_unavailable');
    return { created: row.fgaAlbumObligationId === id, binding: {
      schemaVersion: 1, fgaAlbumBindingId: row.fgaAlbumBindingId, fgaPublishServiceId: row.fgaPublishServiceId,
      localCollectionIdentifier: row.localCollectionIdentifier, linkedFlickrRevision: row.linkedFlickrRevision,
      bindingRevision: row.bindingRevision, titleRevision: row.titleRevision, desiredTitle: row.desiredTitle,
      firstPhotoBindingId: row.firstPhotoBindingId, flickrPhotosetId: row.flickrPhotosetId,
    }, obligation: { fgaAlbumObligationId: row.fgaAlbumObligationId, fgaAlbumBindingId: row.fgaAlbumBindingId,
      fgaPhotoBindingId: row.fgaPhotoBindingId, obligationRevision: row.obligationRevision } };
  } catch (error) {
    if (error instanceof AlbumObligationStoreError) throw error;
    reject('service_unavailable');
  }
}
