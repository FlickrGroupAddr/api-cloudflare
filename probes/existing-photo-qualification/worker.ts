import { createWorker, type Env } from '../../src/worker.ts';
import { credentialDigest } from '../../src/installations.ts';

// Disposable synthetic harness. Never bind production data or real Flickr secrets.
export const TOKEN = Array(13).fill('0000').join('-');
export const HARNESS_MARKER = 'fga-existing-photo-qualification-v1';
export const CASES = ['ok', 'jpeg', 'discovery', 'missing-auth', 'bad-auth', 'bad-query',
  'wrong-revision', 'foreign-owner', 'private-photo', 'missing-photo', 'bad-destination',
  'redirect', 'error-large', 'declared-large', 'stream-large', 'truncated', 'bad-mime',
  'bad-signature', 'timeout', 'link-change', 'generation-change', 'revoke'] as const;
export type Case = typeof CASES[number];
const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='), c => c.charCodeAt(0));
const jpeg = new Uint8Array([255, 216, 255, 224, 255, 217]); // Signature fixture only.
const secrets = {
  FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'synthetic', consumerSecret: 'synthetic' }) },
  FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'synthetic', tokenSecret: 'synthetic' }) },
};
export async function seed(db: D1Database) {
  const digest = await credentialDigest(TOKEN);
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('probe-user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('probe-install','probe-user','lrc_plugin','active',1,'probe-version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('probe-version','probe-install',?,'current',1)").bind(digest),
    db.prepare("INSERT INTO flickr_links VALUES('probe-user','synthetic-owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('probe-user','gen',1,'synthetic-owner','write')"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('probe-user','linked','available')"),
  ]);
}
export async function runCase(request: Request, db: D1Database, scenario: Case): Promise<Response> {
  let pages = 0, images = 0, cancelled = false;
  const fetcher = async (upstream: Request): Promise<Response> => {
    const target = new URL(upstream.url);
    if (upstream.redirect !== 'manual') throw Error('redirect_policy');
    if (target.origin === 'https://www.flickr.com') {
      pages++;
      if (target.searchParams.get('method') !== 'flickr.people.getPhotos'
        || target.searchParams.get('user_id') !== 'synthetic-owner'
        || !upstream.headers.get('Authorization')?.startsWith('OAuth ')) throw Error('discovery_contract');
      return Response.json({ stat: 'ok', photos: { page: 1, perpage: 1, pages: 1, total: 1, photo: [{
        id: scenario === 'missing-photo' ? 'other' : 'photo',
        owner: scenario === 'foreign-owner' ? 'foreign' : 'synthetic-owner',
        ispublic: scenario === 'private-photo' ? '0' : '1', media: 'photo', title: 'Synthetic',
        dateupload: '1770000000', datetaken: '2026-02-01 14:30:00',
        url_q: scenario === 'bad-destination' ? 'https://example.invalid/image.jpg' : 'https://live.staticflickr.com/1/photo_key_q.jpg',
      }] } });
    }
    images++;
    if (target.href !== 'https://live.staticflickr.com/1/photo_key_q.jpg'
      || ['Authorization', 'Cookie', 'Referer'].some(name => upstream.headers.has(name))) throw Error('image_contract');
    if (scenario === 'link-change') await db.prepare("UPDATE flickr_links SET link_revision=2 WHERE user_id='probe-user'").run();
    if (scenario === 'generation-change') await db.prepare("UPDATE flickr_native_credentials SET active_generation='changed' WHERE user_id='probe-user'").run();
    if (scenario === 'revoke') await db.batch([
      db.prepare("UPDATE installation_credential_versions SET state='revoked' WHERE version_id='probe-version'"),
      db.prepare("UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1 WHERE installation_id='probe-install'"),
    ]);
    if (scenario === 'redirect') return new Response(null, { status: 302, headers: { Location: 'https://example.invalid/never-follow' } });
    if (scenario === 'timeout' || scenario === 'stream-large') return new Response(new ReadableStream({
      start(c) { if (scenario === 'stream-large') c.enqueue(new Uint8Array(262145)); },
      cancel() { cancelled = true; },
    }), { headers: { 'Content-Type': 'image/png' } });
    const body = scenario === 'jpeg' ? jpeg : scenario === 'bad-signature' ? new Uint8Array(70) : png;
    return new Response(scenario === 'error-large' ? new Uint8Array(300000) : body, {
      status: scenario === 'error-large' ? 500 : 200,
      headers: { 'Content-Type': scenario === 'jpeg' ? 'image/jpeg' : scenario === 'bad-mime' ? 'text/html' : 'image/png',
        'Content-Length': scenario === 'declared-large' ? '262145' : scenario === 'truncated' ? '999' : String(body.length) },
    });
  };
  try {
    const response = await createWorker(fetcher).fetch(request, {
      ...secrets, DB: db, FGA_READ_ENABLED: '1', FGA_EXISTING_PHOTOS_ENABLED: '1',
      FGA_PHOTO_THUMBNAILS_ENABLED: '1', FGA_INTAKE_ENABLED: '0', FGA_DISPATCH_ENABLED: '0',
    } as Env);
    const headers = new Headers(response.headers);
    headers.set('X-Probe-Pages', String(pages)); headers.set('X-Probe-Images', String(images));
    headers.set('X-Probe-Cancelled', String(cancelled));
    return new Response(response.body, { status: response.status, headers });
  } finally {
    // Preserve the monotonic revision guard; later cases explicitly use revision 2.
    if (scenario === 'link-change') await db.prepare("UPDATE flickr_native_credentials SET link_revision=2 WHERE user_id='probe-user'").run();
    if (scenario === 'generation-change') await db.prepare("UPDATE flickr_native_credentials SET active_generation='gen' WHERE user_id='probe-user'").run();
  }
}
interface ProbeEnv { DB: D1Database; PROBE_ACCESS_TOKEN?: string; }
const probe = {
  async fetch(request: Request, env: ProbeEnv): Promise<Response> {
    const deny = () => new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
    if (!env.PROBE_ACCESS_TOKEN || env.PROBE_ACCESS_TOKEN.length < 32
      || request.headers.get('X-Probe-Access') !== env.PROBE_ACCESS_TOKEN) return deny();
    const url = new URL(request.url), scenario = request.headers.get('X-Probe-Case');
    if (request.method !== 'GET') return deny();
    if (url.pathname === '/__probe/seed' && !url.search) {
      await seed(env.DB); return new Response(null, { status: 204, headers: { 'Cache-Control': 'no-store' } });
    }
    if (!CASES.includes(scenario as Case) || !['/api/v001/existing-public-photos',
      '/api/v001/existing-public-photos/photo/thumbnail'].includes(url.pathname)) return deny();
    return runCase(request, env.DB, scenario as Case);
  },
} satisfies ExportedHandler<ProbeEnv>;

export default {
  async fetch(request: Request, env: ProbeEnv): Promise<Response> {
    const response = await probe.fetch(request, env);
    const headers = new Headers(response.headers);
    headers.set('X-FGA-Probe', HARNESS_MARKER);
    return new Response(response.body, { status: response.status, headers });
  },
} satisfies ExportedHandler<ProbeEnv>;
