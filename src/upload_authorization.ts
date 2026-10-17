import OAuth from 'oauth-1.0a';
import type { AdmissionAuth, SqlStore } from './admission.ts';
import { errorResponse } from './installations.ts';
import { hmac, linkedGrant, sameGrant, withGrant, type GrantSnapshot,
  type SecretReads, type Pair, type Application } from './flickr_reads.ts';

export const FLICKR_UPLOAD_URL = 'https://up.flickr.com/services/upload/';
export const UPLOAD_AUTHORIZATION_MAX_JSON_BYTES = 16_384;
export interface UploadAuthorizationEnv extends SecretReads {
  DB: SqlStore;
  FGA_UPLOAD_AUTHORIZATION_ENABLED?: string;
}
export interface UploadAuthorizationRequest { schemaVersion: 1; flickrMetadata: Record<string, string>; }
interface Credential { userId: string; versionId: string; revision: string; }
interface Gates { deploymentRevision: string; userRevision: string; }
interface Authority { credential: Credential; grant: GrantSnapshot; gates: Gates; }
class UploadAuthorizationError extends Error {}
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const required = ['is_public', 'is_friend', 'is_family', 'safety_level', 'content_type', 'hidden'] as const;
const optional = ['title', 'description', 'tags'] as const;
const allowed = new Set<string>([...required, ...optional]);
const enumValues: Record<string, readonly string[]> = { is_public: ['0', '1'], is_friend: ['0', '1'],
  is_family: ['0', '1'], safety_level: ['1', '2', '3'], content_type: ['1', '2', '3'], hidden: ['1', '2'] };

/** Return a fresh metadata object so the exact validated values own the signature. */
export function validateUploadAuthorization(value: unknown): Record<string, string> {
  if (!object(value) || Object.keys(value).sort().join() !== 'flickrMetadata,schemaVersion'
    || value.schemaVersion !== 1 || !object(value.flickrMetadata)) throw new UploadAuthorizationError('invalid_request');
  const metadata = value.flickrMetadata;
  if (required.some(key => !Object.hasOwn(metadata, key)) || Object.keys(metadata).some(key => !allowed.has(key))
    || Object.entries(metadata).some(([key, item]) => typeof item !== 'string' || enumValues[key] && !enumValues[key].includes(item)))
    throw new UploadAuthorizationError('invalid_request');
  // Match the established bounded JSON request framing without inventing Flickr field maxima.
  if (new TextEncoder().encode(JSON.stringify(value)).length > UPLOAD_AUTHORIZATION_MAX_JSON_BYTES)
    throw new UploadAuthorizationError('request_too_large');
  return Object.fromEntries(Object.entries(metadata)) as Record<string, string>;
}

export function signedUploadAuthorization(metadata: Record<string, string>, pair: Pair, app: Application): {
  authorizationHeader: string; flickrMetadata: Record<string, string>;
} {
  const flickrMetadata = { api_key: app.consumerKey, ...metadata };
  const oauth = new OAuth({ consumer: { key: app.consumerKey, secret: app.consumerSecret },
    signature_method: 'HMAC-SHA1', hash_function: hmac });
  oauth.getNonce = () => Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join('');
  const authorizationHeader = oauth.toHeader(oauth.authorize({ url: FLICKR_UPLOAD_URL, method: 'POST', data: flickrMetadata },
    { key: pair.token, secret: pair.tokenSecret })).Authorization;
  if (typeof authorizationHeader !== 'string' || !authorizationHeader.startsWith('OAuth ') || /[\r\n]/.test(authorizationHeader))
    throw new UploadAuthorizationError('signing_unavailable');
  return { authorizationHeader, flickrMetadata };
}

async function currentCredential(db: SqlStore, auth: AdmissionAuth): Promise<Credential | null> {
  return db.prepare(`SELECT i.user_id userId,v.version_id versionId,CAST(i.revision AS TEXT) revision
    FROM installations i JOIN installation_credential_versions v ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
    WHERE i.installation_id=? AND i.state='active' AND i.credential_class='lrc_plugin'
      AND v.state='current' AND v.credential_digest=?`).bind(auth.installationId, auth.credentialDigest).first<Credential>();
}
async function currentGates(db: SqlStore, userId: string): Promise<Gates | null> {
  return db.prepare(`SELECT CAST(d.revision AS TEXT) deploymentRevision,CAST(u.revision AS TEXT) userRevision
    FROM flickr_write_gates d CROSS JOIN flickr_write_gates u
    WHERE d.scope='deployment' AND d.scope_id='*' AND d.enabled=1
      AND u.scope='user' AND u.scope_id=? AND u.enabled=1`).bind(userId).first<Gates>();
}
async function currentUploadGrant(db: SqlStore, auth: AdmissionAuth): Promise<GrantSnapshot | null> {
  const grant = await linkedGrant(db, auth);
  if (!grant || !await db.prepare(`SELECT 1 FROM flickr_connection_state
    WHERE user_id=? AND state='linked' AND local_state='available' AND operation_id IS NULL`).bind(grant.userId).first()) return null;
  return grant;
}
function sameCredential(a: Credential, b: Credential | null): boolean {
  return b !== null && a.userId === b.userId && a.versionId === b.versionId && a.revision === b.revision;
}
async function recheck(db: SqlStore, auth: AdmissionAuth, authority: Authority): Promise<void> {
  if (!sameCredential(authority.credential, await currentCredential(db, auth))) throw new UploadAuthorizationError('invalid_token');
  if (!sameGrant(authority.grant, await currentUploadGrant(db, auth))) throw new UploadAuthorizationError('flickr_link_changed');
  const gates = await currentGates(db, authority.credential.userId);
  if (!gates || gates.deploymentRevision !== authority.gates.deploymentRevision || gates.userRevision !== authority.gates.userRevision)
    throw new UploadAuthorizationError('flickr_writes_paused');
}
function guard(db: SqlStore, auth: AdmissionAuth, authority: Authority, tx: string) {
  const { credential, grant, gates } = authority;
  return db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(
    SELECT 1 FROM installations i JOIN installation_credential_versions v ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
      JOIN flickr_links l ON l.user_id=i.user_id JOIN flickr_native_credentials n ON n.user_id=i.user_id
      JOIN flickr_connection_state c ON c.user_id=i.user_id
      JOIN flickr_write_gates d ON d.scope='deployment' AND d.scope_id='*'
      JOIN flickr_write_gates u ON u.scope='user' AND u.scope_id=i.user_id
    WHERE i.installation_id=? AND i.user_id=? AND i.state='active' AND i.credential_class='lrc_plugin'
      AND i.revision=CAST(? AS INTEGER) AND v.version_id=? AND v.state='current' AND v.credential_digest=?
      AND l.state='linked' AND l.owner_nsid=? AND l.link_revision=CAST(? AS INTEGER)
      AND c.state='linked' AND c.local_state='available' AND c.operation_id IS NULL
      AND n.link_revision=l.link_revision AND n.active_generation=? AND n.operation_id IS NULL
      AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete')
      AND d.enabled=1 AND d.revision=CAST(? AS INTEGER) AND u.enabled=1 AND u.revision=CAST(? AS INTEGER))`)
    .bind(tx, auth.installationId, credential.userId, credential.revision, credential.versionId, auth.credentialDigest,
      grant.ownerNsid, grant.revision, grant.generation, gates.deploymentRevision, gates.userRevision);
}
function paused(): Response {
  return Response.json({ schemaVersion: 1, error: { code: 'flickr_writes_paused', message: 'Flickr writes require repair.',
    retryable: false, correlationId: crypto.randomUUID() } }, { status: 503,
    headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' } });
}
function failure(error: unknown): Response {
  const code = error instanceof UploadAuthorizationError ? error.message : '';
  if (code === 'flickr_writes_paused') return paused();
  if (code === 'invalid_token') return errorResponse(401, code, 'Invalid installation credential.', true);
  if (code === 'flickr_link_changed') return errorResponse(409, code, 'The Flickr connection changed.');
  if (code === 'invalid_request') return errorResponse(400, code, 'Invalid upload metadata.');
  if (code === 'request_too_large') return errorResponse(413, code, 'Request is too large.');
  return errorResponse(503, 'upload_authorization_unavailable', 'Upload authorization is unavailable.');
}
async function failedResponse(env: UploadAuthorizationEnv, auth: AdmissionAuth, error: unknown, authority?: Authority): Promise<Response> {
  const response = failure(error);
  const body = await response.clone().json() as { error: { code: string; correlationId: string } };
  try {
    const credential = authority?.credential ?? await currentCredential(env.DB, auth);
    if (credential) await env.DB.prepare(`INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason,target_id)
      VALUES(?,?,'upload_authorization.issue',?,'failed',?,?)`)
      .bind(crypto.randomUUID(), credential.userId, body.error.correlationId, body.error.code, auth.installationId).run();
    return response;
  } catch {
    // Only a fixed reason and opaque correlation survive an unavailable audit database.
    console.warn('fga_upload_authorization_audit_unavailable', { correlationId: body.error.correlationId });
    return errorResponse(503, 'upload_authorization_unavailable', 'Upload authorization is unavailable.');
  }
}

/** Metadata only. This operation makes no network request to Flickr and never receives image bytes. */
export async function uploadAuthorizationRequest(env: UploadAuthorizationEnv, auth: AdmissionAuth, value: unknown): Promise<Response> {
  if (env.FGA_UPLOAD_AUTHORIZATION_ENABLED !== '1') return errorResponse(503, 'service_unavailable', 'Service unavailable.');
  let authority: Authority | undefined;
  try {
    const metadata = validateUploadAuthorization(value), db = env.DB;
    const credential = await currentCredential(db, auth);
    if (!credential) throw new UploadAuthorizationError('invalid_token');
    const grant = await currentUploadGrant(db, auth);
    if (!grant) throw new UploadAuthorizationError('flickr_link_changed');
    const gates = await currentGates(db, credential.userId);
    if (!gates) throw new UploadAuthorizationError('flickr_writes_paused');
    authority = { credential, grant, gates };
    const snapshot = authority;
    const envelope = await withGrant(db, auth, env, grant, async (pair, app) => {
      // Secret resolution can wait. A pause or rotation completed while waiting must defeat signing.
      await recheck(db, auth, snapshot);
      return signedUploadAuthorization(metadata, pair, app);
    });
    const authorizationId = crypto.randomUUID(), tx = crypto.randomUUID();
    const committed = await db.batch([
      guard(db, auth, authority, tx),
      db.prepare(`INSERT INTO upload_authorizations(authorization_id,installation_id,user_id,issued_at_us,photo_id,owner_nsid,link_revision)
        SELECT ?,?,?,now_us,NULL,?,CAST(? AS INTEGER) FROM transaction_guards WHERE transaction_id=?`)
        .bind(authorizationId, auth.installationId, credential.userId, grant.ownerNsid, grant.revision, tx),
      db.prepare(`INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason,target_id)
        VALUES(?,?,'upload_authorization.issued',?,'succeeded','current_grant_and_gates_verified',?)`)
        .bind(crypto.randomUUID(), credential.userId, tx, authorizationId),
      db.prepare(`SELECT strftime('%Y-%m-%dT%H:%M:',issued_at_us/1000000,'unixepoch')||printf('%09.6f',(issued_at_us%60000000)/1000000.0)||'Z' issuedAt
        FROM upload_authorizations WHERE authorization_id=?`).bind(authorizationId),
      db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
    ]);
    const row = committed[3].results[0] as unknown as { issuedAt: string } | undefined;
    if (!row || typeof row.issuedAt !== 'string') throw new UploadAuthorizationError('commit_unconfirmed');
    // The envelope exists only in this response. The association transaction receives none of it.
    return Response.json({ schemaVersion: 1, fgaUploadAuthorizationId: authorizationId, issuedAt: row.issuedAt,
      uploadUrl: FLICKR_UPLOAD_URL, ...envelope }, { headers: { 'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' } });
  } catch (error) {
    if (authority) {
      try { await recheck(env.DB, auth, authority); }
      catch (changed) { return failedResponse(env, auth, changed, authority); }
    }
    // Never include request metadata, the signed header, secret material, or arbitrary exception text.
    return failedResponse(env, auth, error, authority);
  }
}
