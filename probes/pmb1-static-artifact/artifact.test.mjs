// MIT License; copyright 2026 Terry Ott. Exact emitted artifact, synthetic only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, join } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { Miniflare, Log, LogLevel, Request } from 'miniflare';
const build=resolve(process.env.PMB1_ARTIFACT_DIRECTORY);
const manifest=JSON.parse(readFileSync(join(build,'artifact-manifest.json')));
const token=Array(13).fill('0000').join('-');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const file=name=>readFileSync(new URL(name,import.meta.url),'utf8');
const JOURNAL='aaaaaaaa-0000-4000-8000-000000000000',DOMAIN='bbbbbbbb-0000-4000-8000-000000000000';
const config={profile:manifest.profile,objectBoundary:manifest.objectBoundary,d1Operation:manifest.d1Operation,
 binding:{candidate:manifest.sourceContextSha2_256,lifecycle:'synthetic',generation:'1'},
 journalDatabaseId:JOURNAL,domainDatabaseId:DOMAIN,bounds:{pages:256,rows:10000,bytes:4194304,milliseconds:10000}};
let outbound=0;
// Exact emitted bytes; existing emulator max date only. Candidate config stays
// 2026-10-16. This deliberate local override proves no configured-date/native fit.
function options(configuration=JSON.stringify(config)) {
 return {modules:true,modulesRoot:join(build,'emitted'),scriptPath:join(build,'emitted/entry.js'),compatibilityDate:'2026-08-06',compatibilityFlags:['nodejs_compat'],
  log:new Log(LogLevel.ERROR),cf:false,port:0,inspectorPort:0,host:'127.0.0.1',
  d1Databases:{DB:DOMAIN,PMB1_MAIN_JOURNAL:JOURNAL},
  durableObjects:{COORD:{className:'PartitionWorker',useSQLite:true},PMB1_OWNERS:{className:'NativeCaptureOwner',useSQLite:true},PMB1_CAPTURE_CONTROL:{className:'NativeCaptureControl',useSQLite:true}},
  bindings:{PMB1_CONFIGURATION:configuration,FGA_READ_ENABLED:'1',FGA_DISPATCH_ENABLED:'0',FGA_ADMIN_ENABLED:'0'},
  outboundService:()=>{outbound++;throw Error('outbound_forbidden');}};
}
const req=(path='/api/v001/installations/current',init={})=>new Request('https://synthetic.invalid'+path,{headers:{Authorization:'Bearer '+token},...init});
async function install(db,raw) {
 const schema=raw.prepare("SELECT type,sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY rowid").all();
 for(const s of schema.filter(s=>s.type==='table'))await db.prepare(s.sql).run();
 const inserts=[];
 for(const {name} of raw.prepare("SELECT name FROM sqlite_schema WHERE type='table'").all()) {
  const rows=raw.prepare('SELECT * FROM "'+name+'"').all();
  for(const row of rows){const ordinary=new Set(raw.prepare('PRAGMA table_info("'+name+'")').all().map(c=>c.name));const columns=Object.keys(row).filter(n=>ordinary.has(n));inserts.push(db.prepare('INSERT INTO "'+name+'"('+columns.map(n=>'"'+n+'"').join(',')+') VALUES('+columns.map(()=>'?').join(',')+')').bind(...columns.map(n=>row[n])));}
 }
 if(inserts.length)await db.batch(inserts);
 for(const s of schema.filter(s=>s.type!=='table'))await db.prepare(s.sql).run();
}
async function setup(t,configuration) {
 const mf=new Miniflare(options(configuration));t.after(async()=>{await mf.dispose();assert.equal(outbound,0);});await mf.ready;
 const db=await mf.getD1Database('DB'),journal=await mf.getD1Database('PMB1_MAIN_JOURNAL');
 const raw=new DatabaseSync(':memory:');t.after(()=>raw.close());raw.exec(file('../pmb1-integer-candidate/d1-schema.sql'));
 raw.exec("BEGIN;INSERT INTO fga_users VALUES('user');INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','user','lrc_plugin','active',7,'version');");
 raw.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)").run(sha(Buffer.from(token)));raw.exec('COMMIT');
 raw.exec(file('../pmb1-integer-candidate/d1-guards.sql'));await install(db,raw);
 const jr=new DatabaseSync(':memory:');jr.exec(file('../pmb1-native-journal/schema.sql'));
 jr.prepare(file('../pmb1-native-journal/provision.sql')).run(JOURNAL,config.binding.candidate,config.binding.lifecycle,'1');
 await install(journal,jr);jr.close();
 return {mf,db,journal};
}
test('manifest pins exact emitted/retained bytes and complete locked runtime graph',()=>{
 for(const [name,pin] of Object.entries(manifest.moduleSha2_256)){
  assert.equal(sha(readFileSync(join(build,'emitted',name))),pin);
  assert.equal(sha(readFileSync(join(build,'retained/modules',name))),pin);
 }
 assert.equal(sha(readFileSync(join(build,'retained/configuration.json'))),manifest.configurationSha2_256);
 assert.equal(manifest.actualQualification,false);assert.equal(manifest.actualImmutableVersion,null);
 assert.equal(manifest.restore.force,false);assert.equal(manifest.restore.rebuildAllowed,false);
 const sourceRoot=fileURLToPath(new URL('../../',import.meta.url));
 for(const [name,pin] of Object.entries(manifest.sourceInputs))assert.equal(sha(readFileSync(join(sourceRoot,name))),pin,name);
 const map=JSON.parse(readFileSync(join(build,'emitted/entry.js.map')));
 const virtual=new Map(map.sources.map((name,i)=>[name,map.sourcesContent[i]]));
 for(const [name,input] of Object.entries(manifest.runtimeGraph)){
  const bytes=input.virtual?Buffer.from(virtual.get(name)):readFileSync(join(sourceRoot,name));
  assert.equal(bytes.byteLength,input.bytes,name);assert.equal(sha(bytes),input.sha2_256,name);
 }
 for(const [name,pin] of Object.entries(manifest.toolchain))assert.equal(sha(readFileSync(name==='portable-node.exe'?process.execPath:join(sourceRoot,name))),pin,name);
 assert(Object.keys(manifest.runtimeGraph).some(p=>p.includes('node_modules/google-auth-library')));
 assert(Object.keys(manifest.runtimeGraph).some(p=>p.includes('node_modules/hono')));
 assert.equal(Object.keys(manifest.runtimeGraph).some(p=>p.includes('isolate.cjs')),false);
});
test('emitted ordinary authenticated closed GET succeeds with real lookup and security headers',async t=>{
 const {mf,db,journal}=await setup(t);const response=await mf.dispatchFetch(req());
 assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');
 assert.equal(response.headers.get('x-content-type-options'),'nosniff');assert.equal(response.headers.get('referrer-policy'),'no-referrer');
 assert.deepEqual(await response.json(),{schemaVersion:1,installationId:'installation',installationRevision:7,installationState:'active',presentedCredentialState:'current'});
 assert.equal((await db.prepare('SELECT state FROM maintenance_control').first()).state,'closed');
 assert.equal((await journal.prepare('SELECT count(*) n FROM pmb1_journal_invocations').first()).n,0);
 await assert.rejects(db.prepare("UPDATE installations SET label='late'").run(),/maintenance_closed/);
});
test('emitted hostile credentials/query/body/method and all other routes remain gated after durable stop/restart',async t=>{
 const {mf,journal}=await setup(t);
 await journal.prepare("INSERT INTO pmb1_journal_invocations(invocation,candidate,lifecycle,generation,entry) VALUES(?,?,?,?,?)").bind('cccccccc-0000-4000-8000-000000000000',config.binding.candidate,'synthetic','1','fetch').run();
 await journal.prepare("INSERT INTO pmb1_journal_effects(effect,invocation,kind) VALUES(?,?,'provider-body')").bind('dddddddd-0000-4000-8000-000000000000','cccccccc-0000-4000-8000-000000000000').run();
 await journal.prepare("UPDATE pmb1_journal_control SET state='stopped',stop_evidence=?,revision=revision+1 WHERE id=1").bind('f'.repeat(64)).run();
 for(const r of [req(undefined,{headers:{}}),req(undefined,{headers:{Authorization:'Bearer broken'}}),req('/api/v001/installations/current?unexpected=1'),req(undefined,{method:'POST',body:'{}'}),req('/admin/login'),req('/api/v001/installations/current/'),req('/api/v001/installations/%63urrent'),req('/other')]){
  const response=await mf.dispatchFetch(r);assert([400,401,503].includes(response.status));assert.notEqual(response.status,200);
 }
 assert.equal((await mf.dispatchFetch(req())).status,200);
 const scheduled=await (await mf.getWorker()).scheduled();assert.equal(scheduled.outcome,'exception');
 await mf.setOptions(options());const restartedJournal=await mf.getD1Database('PMB1_MAIN_JOURNAL');assert.equal((await mf.dispatchFetch(req('/admin/login'))).status,503);
 assert.equal((await restartedJournal.prepare('SELECT state FROM pmb1_journal_control').first()).state,'stopped');
 assert.equal((await restartedJournal.prepare('SELECT count(*) n FROM pmb1_journal_invocations').first()).n,1);
 assert.equal((await restartedJournal.prepare('SELECT returned FROM pmb1_journal_invocations').first()).returned,null);
 assert.equal((await restartedJournal.prepare('SELECT settled FROM pmb1_journal_effects').first()).settled,null);
 const races=await Promise.all(Array.from({length:8},()=>mf.dispatchFetch(req('/admin/login'))));assert(races.every(r=>r.status===503));
 assert.equal((await restartedJournal.prepare('SELECT count(*) n FROM pmb1_journal_invocations').first()).n,1);
});
test('unconfigured, selector/candidate/resource/extra-field corruption refuses before storage',async t=>{
 for(const c of ['UNCONFIGURED',JSON.stringify({...config,profile:'historical'}),JSON.stringify({...config,d1Operation:'fixed_update_with_exact_count_named_v1'}),JSON.stringify({...config,binding:{...config.binding,candidate:'0'.repeat(64)}}),JSON.stringify({...config,journalDatabaseId:DOMAIN}),JSON.stringify({...config,coverage:{complete:true}})]){
  const mf=new Miniflare(options(c));try{assert.equal((await mf.dispatchFetch(req())).status,503);}finally{await mf.dispose();}
 }
 assert.equal(outbound,0);
});
