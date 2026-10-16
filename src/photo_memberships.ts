import type { AdmissionAuth, SqlStore } from './admission.ts';
import { NOW_US_SQL, errorResponse } from './installations.ts';
import { linkedGrant, sameGrant, withGrant, type GrantSnapshot, type SecretReads, type FlickrFetch } from './flickr_reads.ts';
import { PHOTO_ID, PHOTO_READ_LIMITS, photoObject, photoTitle, photoInteger, photoJson, photoUnavailable,
  photoAuthLive, signedPhotoRead, boundedPhotoRead, photoReadBody, rejectPhotoGrant } from './existing_photo_discovery.ts';

// ADR0060 accepts the private observed-time profile; exact hosted/native qualification remains required.
export const MEMBERSHIP_HOST_QUALIFIED = false;
interface Query { size: number; revision: number | null; after: string; }
interface Binding { binding_id: string; photo_id: string; owner_nsid: string; link_revision: number; verification_revision: number; }
interface Observation { revision: number; link_revision: number; generation: string; valid: number; observedAt: string; }
interface Group { flickrGroupId: string; displayName: string; }

export function membershipQuery(url: URL): Query {
  const q = url.searchParams;
  for (const name of q.keys()) if (!['page_size', 'observation_revision', 'after_group_id'].includes(name) || q.getAll(name).length !== 1) throw new Error('invalid_request');
  const size = q.get('page_size'), revision = q.get('observation_revision'), after = q.get('after_group_id');
  if (!size || !/^[1-9][0-9]*$/.test(size) || Number(size) > 100 || (revision === null) !== (after === null)
    || revision !== null && (!/^[1-9][0-9]*$/.test(revision) || !Number.isSafeInteger(Number(revision)))
    || after !== null && !PHOTO_ID.test(after)) throw new Error('invalid_request');
  return { size: Number(size), revision: revision === null ? null : Number(revision), after: after ?? '' };
}
export function validateMembership(value: unknown): Group[] {
  if (!photoObject(value) || value.stat !== 'ok' || !Array.isArray(value.pool)
    || value.set !== undefined && !Array.isArray(value.set)) throw new Error('shape');
  const sets = value.set as unknown[] | undefined;
  if (value.pool.length + (sets?.length ?? 0) > PHOTO_READ_LIMITS.contexts) throw new Error('entry_limit');
  // Discarded collections still require their documented object/ID/title shape.
  const setIds = new Set<string>();
  for (const row of sets ?? []) {
    if (!photoObject(row) || typeof row.id !== 'string' || !PHOTO_ID.test(row.id) || setIds.has(row.id) || !photoTitle(row.title)) throw new Error('shape');
    setIds.add(row.id);
  }
  const seen = new Set<string>();
  return value.pool.map(row => {
    if (!photoObject(row) || typeof row.id !== 'string' || !PHOTO_ID.test(row.id) || seen.has(row.id) || !photoTitle(row.title)) throw new Error('shape');
    seen.add(row.id); return { flickrGroupId: row.id, displayName: row.title };
  });
}
async function loadBinding(db: SqlStore, auth: AdmissionAuth, bindingId: string): Promise<Binding | null> {
  return db.prepare(`SELECT b.* FROM photo_bindings b JOIN installations i ON i.user_id=b.user_id
    WHERE i.installation_id=? AND b.binding_id=?`).bind(auth.installationId, bindingId).first<Binding>();
}
function authorityGuard(db: SqlStore, auth: AdmissionAuth, grant: GrantSnapshot, binding: Binding, tx: string) {
  return db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(
    SELECT 1 FROM installations i JOIN installation_credential_versions v ON v.version_id=i.current_version_id
      AND v.installation_id=i.installation_id JOIN flickr_links l ON l.user_id=i.user_id
      JOIN flickr_native_credentials n ON n.user_id=i.user_id JOIN photo_bindings b ON b.user_id=i.user_id
    WHERE i.installation_id=? AND i.user_id=? AND i.state='active' AND i.credential_class='lrc_plugin'
      AND v.state='current' AND v.credential_digest=? AND l.state='linked' AND l.owner_nsid=?
      AND l.link_revision=CAST(? AS INTEGER) AND n.link_revision=l.link_revision AND n.active_generation=?
      AND n.operation_id IS NULL AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete')
      AND b.binding_id=? AND b.photo_id=? AND b.owner_nsid=l.owner_nsid AND b.link_revision=l.link_revision
      AND b.verification_revision=?)`)
    .bind(tx, auth.installationId, grant.userId, auth.credentialDigest, grant.ownerNsid, grant.revision,
      grant.generation, binding.binding_id, binding.photo_id, binding.verification_revision);
}
async function replaceObservation(db: SqlStore, auth: AdmissionAuth, grant: GrantSnapshot, binding: Binding, groups: Group[]): Promise<void> {
  const tx = crypto.randomUUID();
  await db.batch([
    authorityGuard(db, auth, grant, binding, tx),
    db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,NOT EXISTS(
      SELECT 1 FROM photo_membership_observations WHERE binding_id=? AND revision>=9007199254740991)`)
      .bind(tx + ':revision', binding.binding_id),
    db.prepare(`INSERT INTO photo_membership_observations(binding_id,revision,link_revision,generation,observed_at_us)
      VALUES(?,1,CAST(? AS INTEGER),?,${NOW_US_SQL}) ON CONFLICT(binding_id) DO UPDATE SET
      revision=photo_membership_observations.revision+1,link_revision=excluded.link_revision,
      generation=excluded.generation,observed_at_us=excluded.observed_at_us,valid=1`)
      .bind(binding.binding_id, grant.revision, grant.generation),
    db.prepare('DELETE FROM photo_membership_rows WHERE binding_id=?').bind(binding.binding_id),
    db.prepare(`INSERT INTO photo_membership_rows(binding_id,group_id,display_name)
      SELECT ?,json_extract(value,'$.flickrGroupId'),json_extract(value,'$.displayName') FROM json_each(?)`)
      .bind(binding.binding_id, JSON.stringify(groups)),
    db.prepare('DELETE FROM transaction_guards WHERE transaction_id IN (?,?)').bind(tx, tx + ':revision'),
  ]);
}
async function readPage(db: SqlStore, auth: AdmissionAuth, grant: GrantSnapshot, binding: Binding, query: Query): Promise<Response> {
  const tx = crypto.randomUUID();
  const page = await db.batch([
    authorityGuard(db, auth, grant, binding, tx),
    db.prepare(`SELECT revision,link_revision,generation,valid,
      strftime('%Y-%m-%dT%H:%M:',observed_at_us/1000000,'unixepoch')||printf('%09.6f',(observed_at_us%60000000)/1000000.0)||'Z' observedAt
      FROM photo_membership_observations WHERE binding_id=?`).bind(binding.binding_id),
    db.prepare(`SELECT group_id flickrGroupId,display_name displayName FROM photo_membership_rows
      WHERE binding_id=? AND group_id COLLATE BINARY>? ORDER BY group_id COLLATE BINARY LIMIT ?`)
      .bind(binding.binding_id, query.after, query.size + 1),
    db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
  ]);
  const observation = page[1].results[0] as unknown as Observation | undefined;
  if (!observation || observation.valid !== 1 || observation.link_revision !== Number(grant.revision) || observation.generation !== grant.generation
    || query.revision !== null && observation.revision !== query.revision)
    return errorResponse(409, 'membership_observation_changed', 'Restart membership discovery at the first page.');
  const groups = page[2].results.slice(0, query.size) as unknown as Group[];
  return photoJson({ schemaVersion: 1, fgaPhotoBindingId: binding.binding_id, flickrPhotoId: binding.photo_id,
    observationRevision: observation.revision, observedAt: observation.observedAt, groups,
    nextAfterGroupId: page[2].results.length > query.size ? groups.at(-1)!.flickrGroupId : null });
}
export async function photoMembershipsRequest(db: SqlStore, auth: AdmissionAuth, bindingId: string, url: URL,
  secrets: SecretReads, fetcher: FlickrFetch, now?: () => number): Promise<Response> {
  let grant: GrantSnapshot | null = null;
  try {
    const query = membershipQuery(url);
    if (!PHOTO_ID.test(bindingId)) throw new Error('invalid_request');
    if (!await photoAuthLive(db, auth)) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
    const binding = await loadBinding(db, auth, bindingId);
    if (!binding) return errorResponse(404, 'not_found', 'Resource not found.');
    grant = await linkedGrant(db, auth);
    if (!grant || binding.owner_nsid !== grant.ownerNsid || binding.link_revision !== Number(grant.revision))
      return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
    if (query.revision === null) {
      // Opening a selector retires the preceding paging view before any provider wait.
      // A failed read leaves its audit timing/rows intact but cannot make them current again.
      // A concurrent later successful replacement may publish a new complete observation.
      const tx = crypto.randomUUID();
      await db.batch([
        authorityGuard(db, auth, grant, binding, tx),
        db.prepare('UPDATE photo_membership_observations SET valid=0 WHERE binding_id=?').bind(binding.binding_id),
        db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
      ]);
      const snapshot = grant;
      const groups = await boundedPhotoRead(signal => withGrant(db, auth, secrets, snapshot, async (pair, app) => {
        const value = await photoReadBody(signedPhotoRead('flickr.photos.getAllContexts', { photo_id: binding.photo_id }, pair, app), fetcher, signal);
        await rejectPhotoGrant(db, auth, snapshot, value);
        return validateMembership(value);
      }), now);
      await replaceObservation(db, auth, grant, binding, groups);
    }
    return await readPage(db, auth, grant, binding, query);
  } catch (error) {
    if (error instanceof Error && error.message === 'invalid_request') return errorResponse(400, 'invalid_request', 'Invalid membership query.');
    try {
      if (!await photoAuthLive(db, auth)) return errorResponse(401, 'invalid_token', 'Invalid installation credential.', true);
      if (grant && !sameGrant(grant, await linkedGrant(db, auth))) return errorResponse(409, 'flickr_link_changed', 'The Flickr connection changed.');
    } catch { /* Database failure is unavailable, never an empty observation. */ }
    return photoUnavailable('membership_observation_unavailable');
  }
}
