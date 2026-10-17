import { createWorker, type Env } from '../../src/worker.ts';
import type { FlickrFetch, SecretReads } from '../../src/flickr_reads.ts';

// Qualification-only in-memory credentials and provider. No image bytes are
// uploaded: actual HTTP authorization signs an envelope, then synthetic Flickr
// ownership observations exercise the current binding/reconciliation handlers.
const TOKEN = Array(13).fill('0000').join('-');
const OWNER = 'synthetic-owner';
const FIRST = 'synthetic-upload-first', LATER = 'synthetic-upload-later';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const check = (value: unknown): void => { if (!value) throw Error('qualification_upload_assertion'); };
type Json = Record<string, unknown>;
const object = (value: unknown): value is Json => value !== null && typeof value === 'object' && !Array.isArray(value);
const metadata = { title: 'Synthetic upload', is_public: '0', is_friend: '0', is_family: '0',
  safety_level: '1', content_type: '1', hidden: '2' };

export interface UploadCheckResult {
  firstPhotoBindingId: string; laterPhotoBindingId: string; providerCalls: number; syntheticPosts: number;
}

export async function runUploadChecks(db: D1Database, assertRun: () => void,
  counters?: {providerCalls:number;syntheticPosts:number}): Promise<UploadCheckResult> {
  assertRun();
  let providerCalls = 0, syntheticPosts = 0;
  let expectedRead: 'none' | 'first' | 'candidates' | 'later' = 'none';
  const readConsumed = () => expectedRead === 'none';
  const syntheticSecrets: SecretReads = {
    FLICKR_APPLICATION: { get: async () => {
      assertRun();
      return JSON.stringify({ schemaVersion: 1, consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' });
    } },
    FLICKR_GRANT: { get: async () => {
      assertRun();
      return JSON.stringify({ schemaVersion: 1, generation: 'synthetic-generation', token: 'synthetic-token', tokenSecret: 'synthetic-secret' });
    } },
  };
  // Every request reaches this fixed peer; no real fetch or fallback exists.
  const strictFlickrFetch: FlickrFetch = async request => {
    assertRun();
    providerCalls++;
    if(counters)counters.providerCalls++;
    if (request.method === 'POST') {syntheticPosts++;if(counters)counters.syntheticPosts++;}
    check(providerCalls <= 3 && syntheticPosts === 0);
    const url = new URL(request.url), params = url.searchParams;
    check(request.method === 'GET' && request.body === null && request.redirect === 'manual' && !request.signal.aborted
      && url.origin === 'https://www.flickr.com' && url.pathname === '/services/rest/'
      && !url.username && !url.password && !url.hash && request.headers.get('Accept') === 'application/json'
      && request.headers.get('Authorization')?.startsWith('OAuth ')
      && params.get('format') === 'json' && params.get('nojsoncallback') === '1');
    const keys = [...params.keys()].sort();
    check(keys.every(key => params.getAll(key).length === 1));
    let reply: object;
    if (expectedRead === 'first' || expectedRead === 'later') {
      const photo = expectedRead === 'first' ? FIRST : LATER;
      check(keys.join() === 'format,method,nojsoncallback,photo_id'
        && params.get('method') === 'flickr.photos.getInfo' && params.get('photo_id') === photo);
      reply = { stat: 'ok', photo: { id: photo, owner: { nsid: OWNER }, visibility: { ispublic: 0 }, media: 'photo' } };
    } else {
      check(expectedRead === 'candidates' && keys.join() === 'content_types,extras,format,max_upload_date,method,min_upload_date,nojsoncallback,page,per_page,user_id'
        && params.get('method') === 'flickr.people.getPhotos' && params.get('user_id') === OWNER
        && params.get('content_types') === '0,1,2,3' && params.get('extras') === 'date_upload,media,url_q'
        && params.get('page') === '1' && params.get('per_page') === '10');
      const min = params.get('min_upload_date'), max = params.get('max_upload_date');
      check(min !== null && max !== null && /^(0|[1-9][0-9]{0,11})$/.test(min!)
        && /^(0|[1-9][0-9]{0,11})$/.test(max!) && Number(min) <= Number(max));
      reply = { stat: 'ok', photos: { page: 1, perpage: 10, pages: 1, total: '1', photo: [{
        id: LATER, owner: OWNER, media: 'photo', title: 'Synthetic candidate', dateupload: max,
        url_q: 'https://live.staticflickr.com/1/synthetic_candidate_q.jpg',
      }] } };
    }
    expectedRead = 'none';
    assertRun();
    return Response.json(reply);
  };
  const worker = createWorker(strictFlickrFetch);
  const env = { DB: db, ...syntheticSecrets, FGA_UPLOAD_AUTHORIZATION_ENABLED: '1', FGA_UPLOAD_PHOTO_BINDING_ENABLED: '1',
    FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED: '1', FGA_UPLOAD_CANDIDATES_ENABLED: '1' } as Env;
  async function http(method: 'POST' | 'PUT' | 'GET', path: string, status: number, body?: object): Promise<Json> {
    assertRun();
    const reply = await worker.fetch(new Request(`https://publisher.invalid/api/v001${path}`, {
      method, headers: { Authorization: `Bearer ${TOKEN}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}), redirect: 'manual',
    }), env);
    assertRun();
    check(reply.status === status && reply.headers.get('Cache-Control') === (method === 'GET' ? 'private, no-store' : 'no-store'));
    const value: unknown = await reply.json();
    assertRun(); check(object(value)); return value as Json;
  }
  async function count(table: 'photo_bindings' | 'upload_authorizations' | 'upload_photo_binding_events' | 'upload_ambiguity_resolution_events' | 'submission_intents'): Promise<number> {
    assertRun();
    const row = await db.prepare(`SELECT count(*) n FROM ${table}`).first<{ n: number }>();
    assertRun(); check(row); return row!.n;
  }
  check(await count('photo_bindings') === 0 && await count('upload_authorizations') === 0);
  async function authorize(): Promise<string> {
    const calls = providerCalls;
    const value = await http('POST', '/upload-authorizations', 200, { schemaVersion: 1, flickrMetadata: metadata });
    check(value.schemaVersion === 1 && typeof value.fgaUploadAuthorizationId === 'string' && UUID.test(value.fgaUploadAuthorizationId)
      && value.uploadUrl === 'https://up.flickr.com/services/upload/' && typeof value.authorizationHeader === 'string'
      && value.authorizationHeader.startsWith('OAuth ') && typeof value.issuedAt === 'string'
      && Number.isFinite(Date.parse(value.issuedAt)) && object(value.flickrMetadata)
      && JSON.stringify(value.flickrMetadata) === JSON.stringify({ api_key: 'synthetic-key', ...metadata }) && providerCalls === calls);
    // Discard the synthetic envelope: this proof never performs the upload POST.
    return value.fgaUploadAuthorizationId as string;
  }
  async function prove(authorization: string, photo: string, resolution: boolean): Promise<string> {
    const path = `/upload-authorizations/${authorization}/${resolution ? 'ambiguity-resolution' : 'photo-binding'}`;
    expectedRead = resolution ? 'later' : 'first';
    const value = await http('PUT', path, 201, { schemaVersion: 1, flickrPhotoId: photo });
    check(readConsumed() && value.schemaVersion === 1 && value.flickrPhotoId === photo
      && typeof value.fgaPhotoBindingId === 'string' && UUID.test(value.fgaPhotoBindingId)
      && value.sourceKind === (resolution ? 'photographer_reconciled_ambiguous_upload' : 'fga_direct_upload')
      && value.verificationRevision === 1 && value.linkedFlickrRevision === 1);
    const calls = providerCalls, repeat = await http('PUT', path, 200, { schemaVersion: 1, flickrPhotoId: photo });
    check(JSON.stringify(repeat) === JSON.stringify(value) && providerCalls === calls);
    return value.fgaPhotoBindingId as string;
  }
  const firstAuthorization = await authorize();
  const firstPhotoBindingId = await prove(firstAuthorization, FIRST, false);
  const laterAuthorization = await authorize();
  check(firstAuthorization !== laterAuthorization && await count('photo_bindings') === 1);
  expectedRead = 'candidates';
  const advisory = await http('GET', `/upload-authorizations/${laterAuthorization}/ambiguity-candidates?page=1&page_size=10`, 200);
  check(readConsumed() && advisory.schemaVersion === 1 && advisory.fgaUploadAuthorizationId === laterAuthorization
    && advisory.linkedFlickrRevision === 1 && advisory.page === 1 && advisory.pageSize === 10
    && advisory.pages === 1 && advisory.total === 1 && Array.isArray(advisory.photos) && advisory.photos.length === 1
    && object(advisory.photos[0]) && advisory.photos[0].flickrPhotoId === LATER);
  // An advisory page cannot itself bind or record photographer resolution.
  check(await count('photo_bindings') === 1 && await count('upload_photo_binding_events') === 1
    && await count('upload_ambiguity_resolution_events') === 0);
  assertRun();
  const unbound = await db.prepare('SELECT photo_id FROM upload_authorizations WHERE authorization_id=?').bind(laterAuthorization).first<{ photo_id: string | null }>();
  assertRun(); check(unbound?.photo_id === null);
  const laterPhotoBindingId = await prove(laterAuthorization, LATER, true);
  check(firstPhotoBindingId !== laterPhotoBindingId && providerCalls === 3 && syntheticPosts === 0
    && await count('photo_bindings') === 2 && await count('upload_authorizations') === 2
    && await count('upload_photo_binding_events') === 2 && await count('upload_ambiguity_resolution_events') === 1
    && await count('submission_intents') === 0);
  assertRun();
  const evidence = await db.prepare(`SELECT b.binding_id,b.source_kind,e.observed_public,r.provenance,r.binding_origin
    FROM photo_bindings b JOIN upload_photo_binding_events e ON e.binding_id=b.binding_id
    LEFT JOIN upload_ambiguity_resolution_events r ON r.authorization_id=e.authorization_id
    WHERE e.authorization_id IN (?,?) ORDER BY b.photo_id`).bind(firstAuthorization, laterAuthorization)
    .all<{ binding_id: string; source_kind: string; observed_public: number; provenance: string | null; binding_origin: number | null }>();
  assertRun();
  const first = evidence.results.find(row => row.binding_id === firstPhotoBindingId);
  const later = evidence.results.find(row => row.binding_id === laterPhotoBindingId);
  check(evidence.results.length === 2 && first?.source_kind === 'upload' && first.observed_public === 0 && first.provenance === null
    && later?.source_kind === 'upload' && later.observed_public === 0
    && later.provenance === 'photographer_reconciled_ambiguous_upload' && later.binding_origin === 1);
  assertRun();
  return { firstPhotoBindingId, laterPhotoBindingId, providerCalls, syntheticPosts };
}
