import OAuth from "oauth-1.0a";
import type { AdmissionAuth, SqlStore } from "./admission.ts";
import { NOW_US_SQL, errorResponse } from "./installations.ts";
import { hmac, linkedGrant, sameGrant, withGrant, rejectCurrentGrant, type GrantSnapshot, type Pair,
  type Application, type SecretReads, type FlickrFetch } from "./flickr_reads.ts";

export const GROUP_LIMITS = { pages: 25, rows: 10_000, bytes: 2 * 1024 * 1024,
  elapsedMs: 60_000, freshnessUs: 900_000_000, intervalUs: 60_000_000 } as const;
const ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
const SECURITY = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer" };
interface PageQuery { size: number; revision: number | null; after: string; }
interface Group { flickrGroupId: string; displayName: string; }
interface Job { user_id: string; job_id: string; installation_id: string; version_id: string;
  link_revision: number; generation: string; }
interface Snapshot { revision: number; refreshed_at_us: number | null; link_revision: number | null;
  generation: string | null; state: string | null; failed_at_us: number | null; now_us: number; }
class GroupError extends Error {}
// r is always a group_refresh row. Revalidate both the installation and linked grant.
const LIVE_JOB = `EXISTS(SELECT 1 FROM installations i
 JOIN installation_credential_versions v ON v.version_id=i.current_version_id AND v.installation_id=i.installation_id
 JOIN flickr_links l ON l.user_id=i.user_id JOIN flickr_native_credentials n ON n.user_id=i.user_id
 WHERE i.installation_id=r.installation_id AND i.user_id=r.user_id AND i.state='active'
 AND i.credential_class='lrc_plugin' AND v.version_id=r.version_id AND v.state='current'
 AND l.state='linked' AND l.link_revision=r.link_revision AND n.link_revision=l.link_revision
 AND n.active_generation=r.generation AND n.operation_id IS NULL
 AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete'))`;

export function groupQuery(url: URL): PageQuery {
  const q = url.searchParams;
  for (const name of q.keys()) if (!['page_size','snapshot_revision','after_group_id'].includes(name)
    || q.getAll(name).length !== 1) throw new GroupError('invalid_request');
  const size = q.get('page_size'), revision = q.get('snapshot_revision'), after = q.get('after_group_id');
  if (size === null || !/^[1-9][0-9]*$/.test(size) || Number(size) > 100
    || (revision === null) !== (after === null)
    || revision !== null && (!/^[1-9][0-9]*$/.test(revision) || !Number.isSafeInteger(Number(revision)))
    || after !== null && !ID.test(after)) throw new GroupError('invalid_request');
  return { size: Number(size), revision: revision === null ? null : Number(revision), after: after ?? '' };
}
function iso(us: number): string { return new Date(Math.floor(us / 1000)).toISOString(); }
function json(value: unknown, status = 200): Response {
  return Response.json(value, { status, headers: SECURITY });
}
async function expire(db: SqlStore): Promise<void> {
  await db.batch([
    db.prepare(`UPDATE group_refresh SET state='failed',failed_at_us=${NOW_US_SQL}
      WHERE state IN ('queued','running') AND deadline_at_us<=${NOW_US_SQL}`),
    db.prepare(`DELETE FROM group_refresh_rows WHERE NOT EXISTS(SELECT 1 FROM group_refresh r
      WHERE r.user_id=group_refresh_rows.user_id AND r.job_id=group_refresh_rows.job_id
      AND r.state='running' AND r.deadline_at_us>${NOW_US_SQL})`),
  ]);
}
function authorityGuard(db: SqlStore, auth: AdmissionAuth, grant: GrantSnapshot, tx: string) {
  return db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(
    SELECT 1 FROM installations i JOIN installation_credential_versions v ON v.version_id=i.current_version_id
    AND v.installation_id=i.installation_id JOIN flickr_links l ON l.user_id=i.user_id
    JOIN flickr_native_credentials n ON n.user_id=i.user_id
    WHERE i.installation_id=? AND i.user_id=? AND i.state='active' AND i.credential_class='lrc_plugin'
    AND v.state='current' AND v.credential_digest=? AND l.state='linked' AND l.link_revision=CAST(? AS INTEGER)
    AND n.link_revision=l.link_revision AND n.active_generation=? AND n.operation_id IS NULL
    AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete'))`)
    .bind(tx, auth.installationId, grant.userId, auth.credentialDigest, grant.revision, grant.generation);
}
async function admitRefresh(db: SqlStore, auth: AdmissionAuth, grant: GrantSnapshot): Promise<void> {
  const tx = crypto.randomUUID();
  await db.batch([
    authorityGuard(db, auth, grant, tx),
    db.prepare('INSERT INTO group_snapshots(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING').bind(grant.userId),
    db.prepare(`INSERT INTO group_refresh(user_id,job_id,installation_id,version_id,link_revision,generation,
      state,admitted_at_us,deadline_at_us)
      SELECT ?,?,?,current_version_id,CAST(? AS INTEGER),?,'queued',${NOW_US_SQL},${NOW_US_SQL}+120000000
      FROM installations WHERE installation_id=? AND EXISTS(SELECT 1 FROM group_snapshots s WHERE s.user_id=?
        AND (s.refreshed_at_us IS NULL OR s.refreshed_at_us<${NOW_US_SQL}-${GROUP_LIMITS.freshnessUs}
        OR s.link_revision<>CAST(? AS INTEGER) OR s.generation<>?))
      ON CONFLICT(user_id) DO UPDATE SET job_id=excluded.job_id,installation_id=excluded.installation_id,
      version_id=excluded.version_id,link_revision=excluded.link_revision,generation=excluded.generation,
      state='queued',admitted_at_us=excluded.admitted_at_us,deadline_at_us=excluded.deadline_at_us,failed_at_us=NULL
      WHERE group_refresh.state NOT IN ('queued','running')
      AND group_refresh.admitted_at_us<=${NOW_US_SQL}-${GROUP_LIMITS.intervalUs}`)
      .bind(grant.userId, crypto.randomUUID(), auth.installationId, grant.revision, grant.generation,
        auth.installationId, grant.userId, grant.revision, grant.generation),
    db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
  ]);
}
export async function groupsRequest(db: SqlStore, auth: AdmissionAuth, url: URL): Promise<Response> {
  try {
    const query = groupQuery(url), grant = await linkedGrant(db, auth);
    if (!grant) return errorResponse(409, 'flickr_link_changed', 'The Flickr connection is unavailable.');
    await expire(db);
    if (query.revision === null) await admitRefresh(db, auth, grant);
    const tx = crypto.randomUUID();
    // D1 batch gives the metadata and rows one transactional read boundary.
    const page = await db.batch([
      authorityGuard(db, auth, grant, tx),
      db.prepare(`SELECT s.*,r.state,r.failed_at_us,${NOW_US_SQL} now_us FROM group_snapshots s
        LEFT JOIN group_refresh r ON r.user_id=s.user_id WHERE s.user_id=?`).bind(grant.userId),
      db.prepare(`SELECT group_id AS flickrGroupId,display_name AS displayName FROM group_snapshot_rows
        WHERE user_id=? AND group_id COLLATE BINARY>? ORDER BY group_id COLLATE BINARY LIMIT ?`)
        .bind(grant.userId, query.after, query.size + 1),
      db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
    ]);
    const snapshot = page[1].results[0] as unknown as Snapshot | undefined;
    const usable = snapshot && snapshot.refreshed_at_us !== null
      && snapshot.link_revision === Number(grant.revision) && snapshot.generation === grant.generation;
    if (query.revision !== null && (!usable || query.revision !== snapshot.revision))
      return errorResponse(409, 'snapshot_changed', 'Restart group discovery at the first page.');
    if (!usable) {
      if (snapshot && ['queued','running'].includes(snapshot.state ?? '')) {
        const response = json({ schemaVersion: 1, status: 'refreshing' }, 202);
        response.headers.set('Retry-After', '60');
        return response;
      }
      return errorResponse(503, 'group_refresh_unavailable', 'Group discovery is unavailable.');
    }
    const age = snapshot.now_us - snapshot.refreshed_at_us!;
    const fresh = age >= 0 && age <= GROUP_LIMITS.freshnessUs;
    const status = fresh ? 'fresh' : snapshot.state === 'failed' ? 'stale_refresh_failed' : 'stale_refreshing';
    const groups = page[2].results.slice(0, query.size) as unknown as Group[];
    return json({ schemaVersion: 1, snapshotRevision: snapshot.revision,
      refreshedAt: iso(snapshot.refreshed_at_us!), snapshotStatus: status,
      ...(status === 'stale_refresh_failed' ? { refreshFailedAt: iso(snapshot.failed_at_us!) } : {}),
      groups, nextAfterGroupId: page[2].results.length > query.size ? groups.at(-1)!.flickrGroupId : null });
  } catch (error) {
    if (error instanceof GroupError && error.message === 'invalid_request')
      return errorResponse(400, 'invalid_request', 'Invalid group discovery query.');
    return errorResponse(503, 'group_refresh_unavailable', 'Group discovery is unavailable.');
  }
}

export function signedGroupPage(page: number, pair: Pair, app: Application): Request {
  const url = new URL('https://www.flickr.com/services/rest/');
  for (const [key,value] of Object.entries({ method: 'flickr.groups.pools.getGroups', page: String(page),
    per_page: '400', format: 'json', nojsoncallback: '1' })) url.searchParams.set(key,value);
  const oauth = new OAuth({ consumer: { key: app.consumerKey, secret: app.consumerSecret },
    signature_method: 'HMAC-SHA1', hash_function: hmac });
  oauth.getNonce = () => Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2,'0')).join('');
  return new Request(url, { redirect: 'manual', headers: { Accept: 'application/json',
    ...oauth.toHeader(oauth.authorize({ url: String(url), method: 'GET' }, { key: pair.token, secret: pair.tokenSecret })) } });
}
const object = (v: unknown): v is Record<string,unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
function integer(v: unknown): number {
  if (typeof v !== 'number' && (typeof v !== 'string' || !/^(0|[1-9][0-9]*)$/.test(v))) throw new GroupError('page_shape');
  const n = Number(v);
  if (!Number.isSafeInteger(n) || n < 0) throw new GroupError('page_shape');
  return n;
}
export function validateGroupPage(value: unknown, expectedPage: number): { groups: Group[]; pages: number; total: number } {
  if (!object(value) || value.stat !== 'ok' || !object(value.groups)) throw new GroupError('page_shape');
  const root = value.groups, page = integer(root.page), pages = integer(root.pages), total = integer(root.total);
  const perPage = integer(root.per_page ?? root.perpage);
  if (root.per_page !== undefined && root.perpage !== undefined && integer(root.per_page) !== integer(root.perpage))
    throw new GroupError('page_shape');
  if (page !== expectedPage || perPage !== 400 || pages > GROUP_LIMITS.pages || total > GROUP_LIMITS.rows
    || pages !== Math.ceil(total / 400) && !(total === 0 && pages === 1)
    || !Array.isArray(root.group) || root.group.length !== Math.min(400, Math.max(0,total-(page-1)*400)))
    throw new GroupError('page_shape');
  const seen = new Set<string>();
  const groups = root.group.map(row => {
    if (!object(row) || typeof row.nsid !== 'string' || !ID.test(row.nsid) || seen.has(row.nsid)
      || typeof row.name !== 'string' || row.name.length < 1 || row.name.length > 1024
      || /[\x00-\x1f\x7f]/.test(row.name)) throw new GroupError('page_shape');
    seen.add(row.nsid);
    return { flickrGroupId: row.nsid, displayName: row.name };
  });
  return { groups, pages: Math.max(1,pages), total };
}
async function abortable<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) throw new GroupError('deadline');
  let stop: () => void = () => {};
  try {
    return await Promise.race([operation, new Promise<never>((_,reject) => {
      stop = () => reject(new GroupError('deadline'));
      signal.addEventListener('abort',stop,{once:true});
    })]);
  } finally { signal.removeEventListener('abort',stop); }
}
export async function groupPageBody(request: Request, fetcher: FlickrFetch, signal: AbortSignal): Promise<unknown> {
  const response = await abortable(fetcher(new Request(request, { signal })),signal);
  if (signal.aborted || !response.ok || !response.body
    || !/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type') ?? '')) throw new GroupError('upstream');
  const reader = response.body.getReader(), chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done,value } = await abortable(reader.read(),signal);
      if (signal.aborted) throw new GroupError('deadline');
      if (done) break;
      size += value.length;
      if (size > GROUP_LIMITS.bytes) throw new GroupError('byte_limit');
      chunks.push(value);
    }
  } catch (error) { void reader.cancel().catch(() => {}); throw error; }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk,offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes));
}
function runningGuard(db: SqlStore, job: Job, tx: string) {
  return db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(
    SELECT 1 FROM group_refresh r WHERE r.user_id=? AND r.job_id=? AND r.state='running'
    AND r.deadline_at_us>${NOW_US_SQL} AND ${LIVE_JOB})`).bind(tx,job.user_id,job.job_id);
}
async function fail(db: SqlStore, job: Job): Promise<void> {
  await db.batch([
    db.prepare(`UPDATE group_refresh SET state='failed',failed_at_us=${NOW_US_SQL}
      WHERE user_id=? AND job_id=? AND state IN ('queued','running')`).bind(job.user_id,job.job_id),
    db.prepare('DELETE FROM group_refresh_rows WHERE user_id=? AND job_id=?').bind(job.user_id,job.job_id),
  ]);
}
/** One cron invocation owns one complete refresh; retries never resume a page. */
export async function refreshGroups(db: SqlStore, secrets: SecretReads, fetcher: FlickrFetch,
  now: () => number = () => performance.now()): Promise<void> {
  await expire(db);
  const job = await db.prepare("SELECT * FROM group_refresh WHERE state='queued' ORDER BY admitted_at_us LIMIT 1").first<Job>();
  if (!job) return;
  const claim = crypto.randomUUID();
  try {
    await db.batch([
      db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(
        SELECT 1 FROM group_refresh r WHERE r.user_id=? AND r.job_id=? AND r.state='queued'
        AND r.deadline_at_us>${NOW_US_SQL} AND ${LIVE_JOB})`).bind(claim,job.user_id,job.job_id),
      db.prepare(`UPDATE group_refresh SET state='running',deadline_at_us=${NOW_US_SQL}+60000000
        WHERE user_id=? AND job_id=?`).bind(job.user_id,job.job_id),
      db.prepare('DELETE FROM group_refresh_rows WHERE user_id=?').bind(job.user_id),
      db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(claim),
    ]);
  } catch { return; } // Another invocation owns it, or its authority is no longer valid.
  const start = now(), controller = new AbortController();
  const timer = setTimeout(() => controller.abort(),GROUP_LIMITS.elapsedMs);
  const check = () => {
    const elapsed = now() - start;
    if (controller.signal.aborted || !Number.isFinite(elapsed) || elapsed < 0 || elapsed >= GROUP_LIMITS.elapsedMs)
      throw new GroupError('deadline');
  };
  try {
    const version = await db.prepare('SELECT credential_digest FROM installation_credential_versions WHERE version_id=?')
      .bind(job.version_id).first<{ credential_digest: string }>();
    if (!version) throw new GroupError('authority');
    const auth = { installationId: job.installation_id, credentialDigest: version.credential_digest };
    const grant = await linkedGrant(db,auth);
    if (!grant || grant.userId !== job.user_id || grant.revision !== String(job.link_revision)
      || grant.generation !== job.generation) throw new GroupError('authority');
    let pages = 1, total = -1, count = 0;
    for (let page = 1; page <= pages; page++) {
      check();
      const value = await withGrant(db,auth,secrets,grant,(pair,app) =>
        groupPageBody(signedGroupPage(page,pair,app),fetcher,controller.signal));
      check();
      if (object(value) && value.stat === 'fail' && (value.code === 98 || value.code === 99)) {
        await rejectCurrentGrant(db,auth,grant);
        throw new GroupError('authority');
      }
      const parsed = validateGroupPage(value,page);
      if (page > 1 && (pages !== parsed.pages || total !== parsed.total)) throw new GroupError('page_drift');
      pages = parsed.pages; total = parsed.total; count += parsed.groups.length;
      if (count > GROUP_LIMITS.rows || !sameGrant(grant,await linkedGrant(db,auth))) throw new GroupError('authority');
      const tx = crypto.randomUUID();
      await db.batch([
        runningGuard(db,job,tx),
        db.prepare(`INSERT INTO group_refresh_rows(user_id,job_id,group_id,display_name)
          SELECT ?,?,json_extract(value,'$.flickrGroupId'),json_extract(value,'$.displayName') FROM json_each(?)`)
          .bind(job.user_id,job.job_id,JSON.stringify(parsed.groups)),
        db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
      ]);
    }
    check();
    if (count !== total) throw new GroupError('page_count');
    const tx = crypto.randomUUID();
    await db.batch([
      runningGuard(db,job,tx),
      db.prepare(`UPDATE group_snapshots SET revision=revision+1,refreshed_at_us=${NOW_US_SQL},
        link_revision=?,generation=? WHERE user_id=?`).bind(job.link_revision,job.generation,job.user_id),
      db.prepare('DELETE FROM group_snapshot_rows WHERE user_id=?').bind(job.user_id),
      db.prepare(`INSERT INTO group_snapshot_rows SELECT user_id,group_id,display_name FROM group_refresh_rows
        WHERE user_id=? AND job_id=?`).bind(job.user_id,job.job_id),
      db.prepare("UPDATE group_refresh SET state='succeeded',failed_at_us=NULL WHERE user_id=? AND job_id=?")
        .bind(job.user_id,job.job_id),
      db.prepare('DELETE FROM group_refresh_rows WHERE user_id=? AND job_id=?').bind(job.user_id,job.job_id),
      db.prepare('DELETE FROM transaction_guards WHERE transaction_id=?').bind(tx),
    ]);
  } catch { await fail(db,job); }
  finally { clearTimeout(timer); }
}
