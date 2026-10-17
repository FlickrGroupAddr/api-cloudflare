import { createWorker, type Env } from '../../src/worker.ts';
import { credentialDigest } from '../../src/installations.ts';
import { consumeAlbumMaterialization } from '../../src/album_materialization_worker.ts';
import { createSyntheticAlbumMaterializationTransport } from '../../src/album_materialization_transport.ts';
import { consumeAlbumAttachment } from '../../src/album_attachment_worker.ts';
import { createSyntheticAlbumAttachmentTransport } from '../../src/album_attachment_transport.ts';
import { consumeAlbumTitle } from '../../src/album_title_worker.ts';
import { createSyntheticAlbumTitleTransport } from '../../src/album_title_transport.ts';
import { signedAlbumRest } from '../../src/flickr_reads.ts';
import { reserveFlickrCapacity } from '../../src/flickr_rate.ts';
import { createAlbumFlickrAdmission, createAlbumWorkerFaultGate } from '../../src/album_flickr_admission.ts';
import { runUploadChecks } from './upload_checks.ts';
import { runCreateRepairChecks } from './repair_checks.ts';

// Qualification-only composition. No production registry/scheduler registration.
export const PHASES = ['seed', 'http', 'materialize', 'attach', 'title', 'remove', 'finish'] as const;
export type Phase = typeof PHASES[number];
export const SCENARIOS = ['happy','create_lost','attachment_lost','title_lost'] as const;
export type Scenario = typeof SCENARIOS[number];
const SCOPE = 'publisher-disposable-v1';
const TOKEN = Array(13).fill('0000').join('-');
const OWNER = 'synthetic-owner', SET = 'synthetic-set', FIRST = 'synthetic-upload-first', LATER = 'synthetic-upload-later';
const APP = { consumerKey: 'synthetic-key', consumerSecret: 'synthetic-secret' };
const GRANT = { token: 'synthetic-token', tokenSecret: 'synthetic-secret' };
const check = (value: unknown): void => { if (!value) throw Error('qualification_assertion'); };
const response = (body: object, status = 200) => Response.json(body, {status, headers: {'Cache-Control': 'no-store'}});

interface Data { binding: string; service: string; obligation: string; }
async function bounded<T>(operation: Promise<T>, milliseconds: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {return await Promise.race([operation,new Promise<never>((_,reject) => {
    timer=setTimeout(()=>reject(Error('qualification_wait_expired')),Math.max(1,milliseconds));
  })]);} finally {if(timer)clearTimeout(timer);}
}
function guardedDatabase(db: D1Database, assertRun: () => void,
  remainingMs: () => number = () => 60_000): D1Database {
  let operations = 0;
  const originals = new WeakMap<object,D1PreparedStatement>();
  const before = () => { assertRun(); check(++operations <= 256); };
  const wrap = (statement: D1PreparedStatement): D1PreparedStatement => {
    const proxy = new Proxy(statement, {get(target, key) {
      if (key === 'bind') return (...values: unknown[]) => { assertRun(); return wrap(target.bind(...values)); };
      if (['first','all','run','raw'].includes(String(key))) return async (...args: unknown[]) => {
        before();
        const value = await bounded((Reflect.get(target,key) as (...args:unknown[])=>Promise<unknown>).apply(target,args),remainingMs());
        assertRun(); return value;
      };
      throw Error('qualification_database_method_forbidden');
    }});
    originals.set(proxy,statement); return proxy;
  };
  return new Proxy(db, {get(target,key) {
    if (key === 'prepare') return (sql: string) => { assertRun(); return wrap(target.prepare(sql)); };
    if (key === 'batch') return async (statements: D1PreparedStatement[]) => {
      before(); check(statements.length <= 128);
      const value = await bounded(target.batch(statements.map(statement => originals.get(statement) ?? statement)),remainingMs());
      assertRun(); return value;
    };
    throw Error('qualification_database_method_forbidden');
  }});
}
async function data(db: D1Database): Promise<Data> {
  const row = await db.prepare('SELECT payload FROM publisher_probe_data WHERE id=1').first<{payload: string}>();
  check(row); return JSON.parse(row!.payload) as Data;
}
async function save(db: D1Database, value: Data): Promise<void> {
  await db.prepare('INSERT INTO publisher_probe_data(id,payload) VALUES(1,?)').bind(JSON.stringify(value)).run();
}

export async function seed(db: D1Database): Promise<void> {
  // Refuse a nonempty resource instead of overwriting/reusing any existing owner.
  check((await db.prepare('SELECT count(*) n FROM fga_users').first<{n: number}>())?.n === 0);
  const digest = await credentialDigest(TOKEN);
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('probe-user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('probe-install','probe-user','lrc_plugin','active',1,'probe-version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('probe-version','probe-install',?,'current',1)").bind(digest),
    db.prepare("INSERT INTO flickr_links VALUES('probe-user',?,1,'linked')").bind(OWNER),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('probe-user','synthetic-generation',1,?,'write',NULL)").bind(OWNER),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('probe-user','linked','available','write',1)"),
    db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','probe-user',1,1)"),
  ]);
}

export interface Counters {providerCalls:number;syntheticPosts:number;}
export async function runPhase(db: D1Database, phase: Phase, assertRun: () => void = () => {},
  counters: Counters = {providerCalls:0,syntheticPosts:0},scenario: Scenario = 'happy'): Promise<object> {
  assertRun();
  check(SCENARIOS.includes(scenario));
  db = guardedDatabase(db,assertRun);
  await db.prepare('CREATE TABLE IF NOT EXISTS publisher_probe_data(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL)').run();
  if (phase === 'seed') { await seed(db); return {phase, outcome: 'synthetic_seeded'}; }
  const census = await db.prepare("SELECT count(*) n,sum(user_id='probe-user') own FROM fga_users").first<{n:number;own:number}>();
  check(census?.n === 1 && census.own === 1);
  let calls = 0, posts = 0, reconciliationReads = 0, remoteTitle = 'Synthetic album';
  const details: Record<string,unknown> = {};
  let created = phase !== 'materialize', attached = false;
  const contexts = (ids: string[]) => ({stat: 'ok', set: ids.map(id => ({id, title: 'Synthetic album'})), pool: []});
  const fetcher = async (request: Request): Promise<Response> => {
    assertRun(); check(++calls <= 16); counters.providerCalls++;
    const url = new URL(request.url);
    check(url.origin === 'https://www.flickr.com' && url.pathname === '/services/rest/' && request.redirect === 'manual');
    const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : url.searchParams;
    const method = params.get('method');
    if (request.method === 'POST') {check(++posts <= 1);counters.syntheticPosts++;}
    else if(posts>0)reconciliationReads++;
    switch (method) {
      case 'flickr.photos.getAllContexts':
        check([FIRST, LATER].includes(params.get('photo_id') ?? ''));
        return response(contexts(params.get('photo_id') === FIRST ? (created ? [SET] : []) : (attached ? [SET] : [])));
      case 'flickr.photosets.create':
        check(phase === 'materialize' && request.method === 'POST' && params.get('primary_photo_id') === FIRST);
        created = true;
        if(scenario==='create_lost')throw Error('synthetic_lost_create_reply');
        return response({stat: 'ok', photoset: {id: SET, url: `https://www.flickr.com/photos/${OWNER}/albums/${SET}/`}});
      case 'flickr.photosets.getInfo':
        check(params.get('photoset_id') === SET);
        return response({stat: 'ok', photoset: {id: SET, owner: OWNER, primary: FIRST, title: {_content: remoteTitle}}});
      case 'flickr.photosets.addPhoto':
        check(phase === 'attach' && request.method === 'POST' && params.get('photoset_id') === SET && params.get('photo_id') === LATER);
        attached = true;
        if(scenario==='attachment_lost')throw Error('synthetic_lost_attachment_reply');
        return response({stat: 'ok'});
      case 'flickr.photosets.editMeta':
        check(phase === 'title' && request.method === 'POST' && params.get('photoset_id') === SET && params.get('title') === 'Desired synthetic title');
        remoteTitle = 'Desired synthetic title';
        if(scenario==='title_lost')throw Error('synthetic_lost_title_reply');
        return response({stat: 'ok'});
      default: throw Error('qualification_upstream_forbidden');
    }
  };
  const fault = createAlbumWorkerFaultGate(db,{userId:'probe-user',deploymentGateRevision:1,userGateRevision:1});
  const worker = createWorker(fetcher);
  const env = {DB: db, FGA_PUBLISH_SERVICE_ENABLED: '1', FGA_ALBUM_BINDINGS_ENABLED: '1',
    FGA_ALBUM_OBLIGATIONS_ENABLED: '1', FGA_ALBUM_TITLE_ENABLED: '1', FGA_ALBUM_LOCAL_REMOVAL_ENABLED: '1'} as Env;
  async function http(method: string, path: string, body?: object): Promise<Record<string, any>> {
    assertRun();
    const reply = await worker.fetch(new Request(`https://publisher.invalid/api/v001${path}`, {
      method, headers: {'Authorization': `Bearer ${TOKEN}`, 'Content-Type': 'application/json'},
      ...(body ? {body: JSON.stringify(body)} : {}),
    }), env);
    check(reply.status >= 200 && reply.status < 300); return await reply.json() as Record<string, any>;
  }
  if (phase === 'http') {
    const uploads = await runUploadChecks(db,assertRun,counters);
    const service = await http('POST', '/publish-services', {schemaVersion: 1});
    const serviceId = service.fgaPublishServiceId as string;
    const ensured = await http('PUT', `/publish-services/${serviceId}/album-bindings/SyntheticAlbum`, {
      schemaVersion: 1, desiredTitle: 'Synthetic album', candidate: {fgaPhotoBindingId: uploads.firstPhotoBindingId, expectedVerificationRevision: 1},
    });
    const binding = ensured.binding.fgaAlbumBindingId as string;
    const associated = await http('PUT', `/album-bindings/${binding}/photo-associations/${uploads.laterPhotoBindingId}`, {
      schemaVersion: 1, expectedBindingRevision: ensured.binding.bindingRevision, expectedVerificationRevision: 1,
    });
    await save(db, {binding, service: serviceId, obligation: associated.obligation.fgaAlbumObligationId as string});
    check(calls === 0); return {phase, outcome: 'actual_handler_admission', albumRequests: 3,
      providerCalls:uploads.providerCalls,syntheticPosts:uploads.syntheticPosts,uploadProofs:2};
  }
  const ids = await data(db);
  const sign = (method: string, fields: Record<string,string>, _post: boolean) => signedAlbumRest(method as Parameters<typeof signedAlbumRest>[0], fields, GRANT, APP);
  let outcome: string;
  if (phase === 'materialize') {
    outcome = await consumeAlbumMaterialization({DB: db, FGA_ALBUM_MATERIALIZATION_ENABLED:'1'}, ids.binding,
      (identity, assertCurrent) => {
        const current = async () => { assertRun(); await assertCurrent(); assertRun(); };
        const provider = async (request:Request) => {
          await fault(); await current();
          const reservation = await reserveFlickrCapacity(db,1);
          check(await reservation.check());
          await fault(); await current();
          assertRun(); check(reservation.unexpired() && !request.signal.aborted);
          return fetcher(request);
        };
        return createSyntheticAlbumMaterializationTransport(identity, {assertCurrent:current, sign, fetcher: provider});
      });
    if(scenario==='create_lost') {
      check(outcome==='create_outcome_unknown' && posts===1);
      const attempt = await db.prepare('SELECT state,dispatch_count FROM album_materialization_attempts WHERE binding_id=?').bind(ids.binding).first<{state:string;dispatch_count:number}>();
      check(attempt?.state==='create_outcome_unknown' && attempt.dispatch_count===1);
      const replay = await consumeAlbumMaterialization({DB:db,FGA_ALBUM_MATERIALIZATION_ENABLED:'1'},ids.binding,
        ()=>{throw Error('create_replay_transport_forbidden');});
      check(replay==='no_work' && posts===1);
      const repair = await runCreateRepairChecks(db,ids.binding,assertRun,counters);
      check(repair.repairStatus==='materialized' && posts===1);
      Object.assign(details,{createReplayOutcome:replay,...repair});
      outcome='create_reconciled_no_replay';
    } else check(outcome === 'materialized' && posts === 1);
  } else if (phase === 'attach') {
    outcome = await consumeAlbumAttachment({DB: db, FGA_ALBUM_ATTACHMENT_ENABLED:'1'}, ids.obligation,
      (identity, assertCurrent) => {
        const current = async () => { assertRun(); await assertCurrent(); assertRun(); };
        const admission = createAlbumFlickrAdmission({db,fetcher,assertCurrent:current,assertFaultAllowed:fault});
        return createSyntheticAlbumAttachmentTransport(identity, {assertCurrent:current, sign,
          fetcher:admission.fetcher,beforeRequest:admission.beforeRequest});
      });
    check(outcome === 'membership_verified' && posts === 1);
    if(scenario==='attachment_lost')Object.assign(details,{lostReplyRecovered:true,reconciliationReads});
  } else if (phase === 'title') {
    const binding = await db.prepare('SELECT binding_revision,title_revision FROM album_bindings WHERE binding_id=?').bind(ids.binding).first<{binding_revision:number;title_revision:number}>();
    check(binding);
    await http('PUT', `/album-bindings/${ids.binding}/title-intents/${binding!.title_revision + 1}`, {
      schemaVersion: 1, expectedBindingRevision: binding!.binding_revision,
      expectedTitleRevision: binding!.title_revision, desiredTitle:'Desired synthetic title',
    });
    outcome = await consumeAlbumTitle({DB: db, FGA_ALBUM_TITLE_SYNC_ENABLED:'1'}, ids.binding,
      (identity, assertCurrent, execution) => {
        const current = async () => { assertRun(); await assertCurrent(); assertRun(); };
        const admission = createAlbumFlickrAdmission({db,fetcher,assertCurrent:current,assertFaultAllowed:fault,signal:execution.signal});
        return createSyntheticAlbumTitleTransport(identity, {assertCurrent:current, execution, sign,
          fetcher:admission.fetcher,beforeRequest:admission.beforeRequest});
      });
    check(outcome === 'synced' && posts === 1);
    if(scenario==='title_lost')Object.assign(details,{lostReplyRecovered:true,reconciliationReads});
  } else if (phase === 'remove') {
    const binding = await db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(ids.binding).first<{binding_revision:number}>();
    await http('PUT', `/album-bindings/${ids.binding}/local-removal`, {schemaVersion: 1,
      expectedBindingRevision: binding!.binding_revision, acknowledgedCreateAttemptId: null});
    check(calls === 0); outcome = 'local_removed_without_upstream';
  } else {
    check(phase === 'finish');
    const row = await db.prepare('SELECT flickr_photoset_id FROM album_bindings WHERE binding_id=?').bind(ids.binding).first<{flickr_photoset_id:string}>();
    check(row?.flickr_photoset_id === SET);
    const obligations = await db.prepare("SELECT count(*) n FROM album_photo_obligations WHERE album_binding_id=? AND state='membership_verified'").bind(ids.binding).first<{n:number}>();
    check(obligations?.n === 2); outcome = 'finite_synthetic_sequence_complete';
  }
  assertRun(); check(counters.providerCalls<=16 && counters.syntheticPosts<=1);
  return {phase, outcome, providerCalls:counters.providerCalls,syntheticPosts:counters.syntheticPosts,...details};
}

interface ProbeEnv { DB: D1Database; PROBE_ENABLED?:string; PROBE_SCOPE?:string;
  PROBE_ACCESS_TOKEN?:string; PROBE_ARTIFACT_SHA2_256?:string; PROBE_RESOURCE_ID?:string;
  PROBE_RUN_ID?:string; PROBE_EXPIRES_AT?:string; PROBE_SCENARIO?:string; }
const HEX = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export default {
  async fetch(request: Request, env: ProbeEnv): Promise<Response> {
    const deny = () => new Response(null, {status:404, headers:{'Cache-Control':'no-store'}});
    const url = new URL(request.url), phase = url.pathname.slice('/__publisher/'.length) as Phase;
    const scenario = (env.PROBE_SCENARIO ?? 'happy') as Scenario;
    const expires = Date.parse(env.PROBE_EXPIRES_AT ?? '');
    if (env.PROBE_ENABLED !== '1' || env.PROBE_SCOPE !== SCOPE || !env.PROBE_ACCESS_TOKEN || !HEX.test(env.PROBE_ACCESS_TOKEN)
      || !SCENARIOS.includes(scenario) || (request.headers.get('X-Probe-Scenario') ?? 'happy') !== scenario
      || !env.PROBE_ARTIFACT_SHA2_256 || !HEX.test(env.PROBE_ARTIFACT_SHA2_256) || !env.PROBE_RUN_ID || !HEX.test(env.PROBE_RUN_ID)
      || !env.PROBE_RESOURCE_ID || !UUID.test(env.PROBE_RESOURCE_ID) || /^0{8}-0{4}-0{4}-0{4}-0{12}$/.test(env.PROBE_RESOURCE_ID)
      || request.headers.get('X-Probe-Access') !== env.PROBE_ACCESS_TOKEN || request.headers.get('X-Probe-Artifact') !== env.PROBE_ARTIFACT_SHA2_256
      || request.headers.get('X-Probe-Resource') !== env.PROBE_RESOURCE_ID || request.headers.get('X-Probe-Run') !== env.PROBE_RUN_ID
      || !Number.isFinite(expires) || expires <= Date.now() || expires - Date.now() > 1_800_000
      || request.method !== 'POST' || !url.pathname.startsWith('/__publisher/') || !PHASES.includes(phase)
      || url.search) return deny();
    if (request.body) {
      const reader = request.body.getReader();
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        const empty = await Promise.race([reader.read(),new Promise<never>((_,reject) => {
          timer=setTimeout(()=>reject(Error('body_timeout')),500);
        })]);
        if (!empty.done) return deny();
      } catch { return deny(); }
      finally { if(timer)clearTimeout(timer);void reader.cancel().catch(()=>{}); }
    }
    const started = performance.now();
    let terminal = false;
    const assertRun = () => { check(!terminal && Date.now() < expires && performance.now() - started < 60_000 && !request.signal.aborted); };
    let timer: ReturnType<typeof setTimeout> | undefined;
    const counters: Counters = {providerCalls:0,syntheticPosts:0};
    try {
      assertRun();
      const control = guardedDatabase(env.DB,assertRun,()=>Math.min(expires-Date.now(),60_000-(performance.now()-started)));
      await control.prepare('CREATE TABLE IF NOT EXISTS publisher_probe_control(id INTEGER PRIMARY KEY CHECK(id=1),run TEXT NOT NULL,artifact TEXT NOT NULL,resource TEXT NOT NULL,expires INTEGER NOT NULL,scenario TEXT NOT NULL,cursor INTEGER NOT NULL,busy INTEGER NOT NULL DEFAULT 0,failed INTEGER NOT NULL DEFAULT 0)').run();
      if (phase === 'seed') await control.prepare('INSERT INTO publisher_probe_control(id,run,artifact,resource,expires,scenario,cursor) VALUES(1,?,?,?,?,?,0) ON CONFLICT(id) DO NOTHING').bind(env.PROBE_RUN_ID,env.PROBE_ARTIFACT_SHA2_256,env.PROBE_RESOURCE_ID,expires,scenario).run();
      const index = PHASES.indexOf(phase);
      const reserved = await control.prepare('UPDATE publisher_probe_control SET busy=1 WHERE id=1 AND run=? AND artifact=? AND resource=? AND expires=? AND scenario=? AND cursor=? AND busy=0 AND failed=0 RETURNING cursor').bind(env.PROBE_RUN_ID,env.PROBE_ARTIFACT_SHA2_256,env.PROBE_RESOURCE_ID,expires,scenario,index).first();
      if (!reserved) return response({status:'NO-GO', error:'phase_refused'},409);
      const result = await Promise.race([runPhase(env.DB, phase, assertRun,counters,scenario),new Promise<never>((_,reject) => {
        timer=setTimeout(()=>{terminal=true;reject(Error('phase_timeout'));},Math.max(1,Math.min(60_000-(performance.now()-started),expires-Date.now())));
      })]);
      assertRun();
      const committed = await control.prepare('UPDATE publisher_probe_control SET cursor=cursor+1,busy=0 WHERE id=1 AND run=? AND cursor=? AND busy=1 AND failed=0 RETURNING cursor').bind(env.PROBE_RUN_ID,index).first();
      check(committed);
      return response({schemaVersion:1,...result,scenario,status:'NO-GO',productionSchedulerQualified:false});
    } catch {
      terminal = true;
      try { await bounded(env.DB.prepare('UPDATE publisher_probe_control SET failed=1 WHERE id=1').run(),500); } catch { /* Submitted SQL may finish later; busy never grants replay. */ }
      return response({status:'NO-GO',error:'qualification_failed',...counters},500);
    } finally {if(timer)clearTimeout(timer);}
  },
} satisfies ExportedHandler<ProbeEnv>;
