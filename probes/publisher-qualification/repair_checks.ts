import { createWorker, type Env } from '../../src/worker.ts';
import { credentialDigest } from '../../src/installations.ts';
import { signedAlbumRest, type FlickrFetch } from '../../src/flickr_reads.ts';
import { createSyntheticAlbumCreateRepairReader } from '../../src/album_create_repair_discovery.ts';
import { assertAlbumRepairContext, readAlbumRepairContext, type RepairAuth, type RepairContext,
  type Status } from '../../src/album_create_repair_store.ts';
import { createAlbumFlickrAdmission, createAlbumWorkerFaultGate } from '../../src/album_flickr_admission.ts';

// Qualification-only composition. Every signed read terminates at the fixed
// in-memory peer; neither a secret lookup nor an ambient fetch is available.
const TOKEN = Array(13).fill('0000').join('-');
const OWNER = 'synthetic-owner', SET = 'synthetic-set', FIRST = 'synthetic-upload-first';
const APP = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' };
const GRANT = { token: 'synthetic-token', tokenSecret: 'synthetic-secret' };
const check = (value: unknown): void => { if (!value) throw Error('qualification_repair_assertion'); };
type Json = Record<string, unknown>;
const object = (value: unknown): value is Json => value !== null && typeof value === 'object' && !Array.isArray(value);

export interface RepairCheckCounters { providerCalls: number; syntheticPosts: number; }
export interface RepairCheckResult { repairStatus: 'materialized'; repairRequests: number; }

/** Continues only a genuine consumer-created unknown outcome, never a new create. */
export async function runCreateRepairChecks(db: D1Database, bindingId: string, assertRun: () => void,
  counters: RepairCheckCounters): Promise<RepairCheckResult> {
  assertRun();
  const auth: RepairAuth = { kind: 'installation', installationId: 'probe-install', credentialDigest: await credentialDigest(TOKEN) };
  assertRun();
  const original = await readAlbumRepairContext(db, auth, bindingId);
  assertRun();
  check(original.userId === 'probe-user' && original.ownerNsid === OWNER && original.firstPhotoId === FIRST
    && original.linkRevision === 1 && original.grantGeneration === 'synthetic-generation'
    && original.authorityId === 'probe-install' && original.authorityRevision === 1
    && original.deploymentGateRevision === 1 && original.userGateRevision === 1
    && original.lifecycle === 'materialization_pending' && original.preContextIds.length === 0);
  const postsBefore = counters.syntheticPosts, callsBefore = counters.providerCalls;
  let peerCalls = 0, repairRequests = 0;
  const sequence = ['flickr.photos.getAllContexts', 'flickr.photosets.getInfo',
    'flickr.photosets.getInfo', 'flickr.photos.getAllContexts'];
  const peer: FlickrFetch = async request => {
    // Count each actual handoff before validation, including failed requests.
    counters.providerCalls++;
    if (request.method === 'POST') counters.syntheticPosts++;
    const methodExpected = sequence[peerCalls++];
    assertRun();
    const url = new URL(request.url), params = url.searchParams;
    const method = params.get('method');
    check(methodExpected !== undefined && method === methodExpected && request.method === 'GET'
      && request.body === null && request.redirect === 'manual' && !request.signal.aborted
      && url.origin === 'https://www.flickr.com' && url.pathname === '/services/rest/'
      && !url.username && !url.password && !url.hash
      && request.headers.get('Accept') === 'application/json'
      && request.headers.get('Authorization')?.startsWith('OAuth ')
      && params.get('format') === 'json' && params.get('nojsoncallback') === '1'
      && [...params.keys()].every(key => params.getAll(key).length === 1));
    let body: object;
    if (method === 'flickr.photos.getAllContexts') {
      check([...params.keys()].sort().join() === 'format,method,nojsoncallback,photo_id' && params.get('photo_id') === original.firstPhotoId);
      body = { stat: 'ok', set: [{ id: SET, title: 'Synthetic album' }], pool: [] };
    } else {
      check(method === 'flickr.photosets.getInfo'
        && [...params.keys()].sort().join() === 'format,method,nojsoncallback,photoset_id' && params.get('photoset_id') === SET);
      body = { stat: 'ok', photoset: { id: SET, owner: OWNER, primary: original.firstPhotoId, title: { _content: 'Synthetic album' } } };
    }
    assertRun();
    return Response.json(body);
  };
  function reader(context: RepairContext) {
    check(context.bindingId === original.bindingId && context.bindingRevision === original.bindingRevision
      && context.attemptId === original.attemptId && context.firstPhotoBindingId === original.firstPhotoBindingId
      && context.firstPhotoId === original.firstPhotoId && context.ownerNsid === original.ownerNsid);
    const snapshot: RepairContext = Object.freeze({ ...context, preContextIds: [...context.preContextIds] });
    const current = async () => { assertRun(); await assertAlbumRepairContext(db, auth, snapshot); assertRun(); };
    const fault = createAlbumWorkerFaultGate(db, { userId: snapshot.userId,
      deploymentGateRevision: snapshot.deploymentGateRevision, userGateRevision: snapshot.userGateRevision });
    const admission = createAlbumFlickrAdmission({ db, fetcher: peer, assertCurrent: current, assertFaultAllowed: fault });
    return createSyntheticAlbumCreateRepairReader({ bindingId: snapshot.bindingId, bindingRevision: snapshot.bindingRevision,
      createAttemptId: snapshot.attemptId, firstPhotoId: snapshot.firstPhotoId, ownerNsid: snapshot.ownerNsid,
      preContextIds: snapshot.preContextIds }, {
      assertCurrent: current, reserveReads: admission.reserveReads, fetcher: admission.fetcher,
      sign: (method, fields) => { assertRun(); return signedAlbumRest(method, fields, GRANT, APP); },
      observedAt: () => { assertRun(); return new Date().toISOString().replace('Z', '000Z'); },
    });
  }
  const worker = createWorker(peer, { reader });
  const env = { DB: db, FGA_ALBUM_CREATE_REPAIR_ENABLED: '1' } as Env;
  async function http(method: 'GET' | 'PUT', suffix: string, body?: object): Promise<Json> {
    assertRun(); check(++repairRequests <= 3);
    const reply = await worker.fetch(new Request(`https://publisher.invalid/api/v001/album-bindings/${bindingId}/${suffix}`, {
      method, headers: { Authorization: `Bearer ${TOKEN}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}), redirect: 'manual',
    }), env);
    assertRun(); check(reply.status === 200 && reply.headers.get('Cache-Control') === 'private, no-store');
    const value: unknown = await reply.json();
    assertRun(); check(object(value)); return value as Json;
  }
  async function evidence() {
    assertRun();
    const value = await db.prepare(`SELECT b.binding_revision,b.materialization_state,b.flickr_photoset_id,
      (SELECT count(*) FROM album_materialization_attempts WHERE binding_id=b.binding_id) attempts,
      a.attempt_id,a.state attempt_state,a.dispatch_count,
      (SELECT count(*) FROM album_create_repair_receipts WHERE binding_id=b.binding_id) receipts
      FROM album_bindings b JOIN album_materialization_attempts a ON a.attempt_id=? WHERE b.binding_id=?`)
      .bind(original.attemptId, bindingId).first<{ binding_revision: number; materialization_state: string;
        flickr_photoset_id: string | null; attempts: number; attempt_id: string; attempt_state: string; dispatch_count: number; receipts: number }>();
    assertRun(); check(value && value.attempts === 1 && value.attempt_id === original.attemptId
      && value.attempt_state === 'create_outcome_unknown' && value.dispatch_count === 1);
    return value!;
  }
  const initial = await evidence();
  check(initial.binding_revision === original.bindingRevision && initial.materialization_state === 'create_outcome_unknown'
    && initial.flickr_photoset_id === null && initial.receipts === 0);
  const candidates = await http('GET', 'create-repair-candidates?page=1&page_size=1');
  check(candidates.schemaVersion === 1 && candidates.fgaAlbumBindingId === bindingId
    && candidates.bindingRevision === original.bindingRevision && candidates.createAttemptId === original.attemptId
    && candidates.page === 1 && candidates.pageSize === 1 && candidates.pages === 1 && candidates.total === 1
    && Array.isArray(candidates.candidates) && candidates.candidates.length === 1
    && object(candidates.candidates[0]) && candidates.candidates[0].flickrPhotosetId === SET
    && candidates.candidates[0].ownerNsid === OWNER && candidates.candidates[0].primaryPhotoId === original.firstPhotoId
    && peerCalls === 2);
  // Advisory discovery cannot bind or record a photographer decision.
  check(JSON.stringify(await evidence()) === JSON.stringify(initial));
  const selection = { schemaVersion: 1, expectedBindingRevision: original.bindingRevision,
    createAttemptId: original.attemptId, selectedPhotosetId: SET };
  const resolved = await http('PUT', 'create-repair-resolution', selection) as unknown as Status;
  check(resolved.schemaVersion === 1 && resolved.binding.fgaAlbumBindingId === bindingId
    && resolved.binding.bindingRevision === original.bindingRevision + 1 && resolved.binding.flickrPhotosetId === SET
    && resolved.materialization.state === 'materialized' && resolved.materialization.createAttemptId === original.attemptId
    && resolved.materialization.resolvedPhotosetId === SET
    && resolved.materialization.resolutionProvenance === 'owner_reconciled_ambiguous_album_create'
    && resolved.catalogRepair.flickrPhotosetId === SET
    && resolved.catalogRepair.navigationUrl === `https://www.flickr.com/photos/${OWNER}/albums/${SET}/`
    && typeof resolved.catalogRepair.identityVerifiedAt === 'string' && peerCalls === 4);
  const committed = await evidence();
  check(committed.binding_revision === original.bindingRevision + 1 && committed.materialization_state === 'materialized'
    && committed.flickr_photoset_id === SET && committed.receipts === 1);
  const replay = await http('PUT', 'create-repair-resolution', selection);
  check(JSON.stringify(replay) === JSON.stringify(resolved) && JSON.stringify(await evidence()) === JSON.stringify(committed)
    && peerCalls === 4 && counters.providerCalls === callsBefore + 4 && counters.syntheticPosts === postsBefore);
  assertRun();
  return { repairStatus: 'materialized', repairRequests };
}
