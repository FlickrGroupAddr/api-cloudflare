// Source/synthetic integration only. Complete declared domain, no account client.
import assert from 'node:assert/strict';
import test from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { compose, restorationRequest, capture, PROFILE } from './candidate.ts';
import { createWorker, ROUTES } from '../../src/worker.ts';
import { credentialDigest, LOOKUP_SQL } from '../../src/installations.ts';
import { bootstrapPartitionMaintenance } from '../../src/partition_maintenance.ts';
import { LocalStorage } from '../pmb1-native-alarm/local-storage.mjs';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';

const file = name => readFileSync(new URL(name, import.meta.url), 'utf8');
const manifest = JSON.parse(file('source-manifest.json'));
const stores = JSON.parse(file('store-manifest.json'));
const token = Array(13).fill('0000').join('-');
const binding = { candidate: manifest.candidateSourceSha2_256, lifecycle: 'synthetic-only', generation: '1' };
const req = (path='/api/v001/installations/current', init={}) => new Request('https://synthetic.invalid'+path,
  { headers: { Authorization: 'Bearer '+token }, ...init });
const hash = raw => createHash('sha256').update(raw).digest('hex');
const quote = name => '"'+name.replaceAll('"','""')+'"';

test('complete source and artifact pins verify independently and include all runtime import inputs',()=>{
  for(const [path,pin] of Object.entries(manifest.inputs))assert.equal(hash(readFileSync(new URL('../../'+path,import.meta.url))),pin,path);
  for(const [path,pin] of Object.entries(manifest.artifacts))assert.equal(hash(readFileSync(new URL(path,import.meta.url))),pin,path);
  for(const path of ['src/worker.ts','src/installations.ts','src/partition_maintenance.ts','src/quota_credit.ts',
    'scripts/private_d1_snapshot_reader.py','scripts/private_d1_snapshot_profile.py','scripts/private_no_real_guards.py',
    'probes/pmb1-no-real-object-reader/reader.ts','package-lock.json'])assert(manifest.inputs[path]);
  assert.equal(Object.keys(manifest.inputs).some(n=>n.includes('historical_child_recovery')),false);
});
function snapshot(db) {
  const schema = db.prepare('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name').all();
  const data = schema.filter(r=>r.type==='table').map(({name})=>{
    const statement=db.prepare('SELECT rowid AS _independent_rowid_,* FROM '+quote(name)+' ORDER BY rowid');
    statement.setReadBigInts(true);return [name,statement.all()];
  });
  return JSON.stringify({schema,data},(_,v)=>typeof v==='bigint'?['bigint',v.toString()]:v);
}
async function setup(t) {
  const raw=new DatabaseSync(':memory:');t.after(()=>raw.close());raw.exec('PRAGMA foreign_keys=ON');
  raw.exec(file('d1-schema.sql'));
  raw.exec("BEGIN;INSERT INTO fga_users VALUES('user');INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','user','lrc_plugin','active',7,'version');");
  raw.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)").run(await credentialDigest(token));raw.exec('COMMIT');
  raw.exec(file('d1-guards.sql'));
  const reads=[];
  const db={prepare(sql){return {bind(...values){return {async first(){reads.push({sql,values});return raw.prepare(sql).get(...values)??null;}};}};}};
  const events=[];
  const candidate=compose({profile:PROFILE,binding,
    journal:{async admit(){events.push('admit');return null;},effect(){assert.fail('effect');},settled(){assert.fail('settled');},returned(){assert.fail('returned');},stop(){assert.fail('stop');}},
    observer:{assess(){assert.fail('observer');}},flickr:async()=>assert.fail('network'),
    verifyObjectDisposition:async()=>assert.fail('reopen'),verifyPartitionReconciliation:async()=>assert.fail('reconcile')});
  return {raw,db,reads,events,candidate,env:{DB:db,FGA_READ_ENABLED:'1'}};
}

test('one candidate entry uses actual ordinary registry/authentication/lookup while full D1 remains closed',async t=>{
  const f=await setup(t),before=snapshot(f.raw);
  assert(ROUTES.some(r=>r.method==='GET'&&r.pathPattern==='/api/v001/installations/current'&&r.handler==='current'));
  const response=await f.candidate.handler.fetch(req(),f.env);
  assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');
  assert.equal(response.headers.get('x-content-type-options'),'nosniff');assert.equal(response.headers.get('referrer-policy'),'no-referrer');
  assert.deepEqual(await response.json(),{schemaVersion:1,installationId:'installation',installationRevision:7,installationState:'active',presentedCredentialState:'current'});
  assert.deepEqual(f.reads,[{sql:LOOKUP_SQL,values:[await credentialDigest(token)]}]);
  assert.deepEqual(f.events,[]);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(snapshot(f.raw),before);
  assert.equal(f.raw.prepare('SELECT state FROM maintenance_control').get().state,'closed');
  assert.equal(stores.domains.d1.tables.length,65);assert.equal(stores.domains.object.tables.length,6);
  assert.equal(Object.keys(manifest.inputs).filter(n=>n.startsWith('migrations/')).length,26);
});

test('ordinary negative semantics and read feature gate remain exact without bypassing authentication',async t=>{
  const f=await setup(t),before=snapshot(f.raw);
  const cases=[req(undefined,{headers:{}}),req(undefined,{headers:{Authorization:'Bearer broken'}}),
    req(undefined,{headers:{Authorization:'Basic x'}}),req('/api/v001/installations/current?extra=1'),
    req(undefined,{headers:{Authorization:'Bearer '+token,'Content-Length':'1'}})];
  for(const request of cases){
    const a=await f.candidate.handler.fetch(request.clone(),f.env),b=await createWorker(async()=>assert.fail('provider')).fetch(request.clone(),f.env);
    assert.equal(a.status,b.status);assert.equal(a.headers.get('www-authenticate'),b.headers.get('www-authenticate'));
    assert.equal(a.headers.get('cache-control'),b.headers.get('cache-control'));
    const normalize=async r=>{const body=await r.text();return body?JSON.parse(body,(k,v)=>k==='correlationId'?'synthetic-correlation':v):body;};
    assert.deepEqual(await normalize(a),await normalize(b));
  }
  const prior=f.reads.length;
  assert.equal((await f.candidate.handler.fetch(req(),{...f.env,FGA_READ_ENABLED:'0'})).status,503);
  assert.equal(f.reads.length,prior);assert.equal(snapshot(f.raw),before);
});

test('unknown/revoked credentials, storage faults and immutable read-only capability fail ordinarily',async t=>{
  const f=await setup(t),before=snapshot(f.raw);
  const unknown=token.replace('0000','0001');assert.equal((await f.candidate.handler.fetch(req(undefined,{headers:{Authorization:'Bearer '+unknown}}),f.env)).status,401);
  const rejected=await f.candidate.handler.fetch(req(),{...f.env,DB:{prepare(){throw new Error('synthetic read failure');}}});
  assert.equal(rejected.status,503);assert.equal((await rejected.json()).error.code,'service_unavailable');
  // Change only the synthetic lookup result; underlying frozen state remains exact.
  const revoked={prepare(sql){assert.equal(sql,LOOKUP_SQL);return {bind(digest){return {async first(){const row=await f.db.prepare(sql).bind(digest).first();return {...row,installation_state:'revoked'};}};}};}};
  assert.equal((await f.candidate.handler.fetch(req(),{...f.env,DB:revoked})).status,401);
  assert.equal(snapshot(f.raw),before);
});

test('methods/path aliases/other routes and scheduled callbacks remain behind stopped admission',async t=>{
  const f=await setup(t),before=snapshot(f.raw);
  const paths=['/api/v001/installations/current/','/api/v001/installations/%63urrent','/api%2fv001/installations/current',
    '/api/v001/submission-status','/admin/login','/anything'];
  for(const path of paths)assert.equal((await f.candidate.handler.fetch(req(path),f.env)).status,503);
  for(const method of ['HEAD','POST','PUT','OPTIONS'])assert.equal((await f.candidate.handler.fetch(req(undefined,{method}),f.env)).status,503);
  await assert.rejects(f.candidate.handler.scheduled({},f.env),/main_entry_unavailable/);
  assert.equal(f.reads.length,0);assert.equal(snapshot(f.raw),before);
});

test('complete declared SQL domain retains ordinary guards, closed mutation refusal and schema drift visibility',async t=>{
  const f=await setup(t),before=snapshot(f.raw);
  for(const table of stores.domains.d1.tables.filter(n=>n!=='maintenance_control')){
    for(const event of ['insert','update','delete'])assert(f.raw.prepare('SELECT sql FROM sqlite_schema WHERE name=?').get('pmb1_'+table+'_'+event)?.sql.includes('maintenance_closed'));
  }
  assert.throws(()=>f.raw.exec("INSERT INTO fga_users VALUES('late')"),/maintenance_closed/);
  assert.throws(()=>f.raw.exec("UPDATE installations SET label='late' WHERE installation_id='installation'"),/maintenance_closed/);
  assert.throws(()=>f.raw.exec("DELETE FROM fga_users WHERE user_id='user'"),/maintenance_closed/);
  assert.throws(()=>f.raw.exec('DELETE FROM maintenance_control'),/maintenance_control_delete_denied/);
  assert.equal(snapshot(f.raw),before);
  assert(f.raw.prepare("SELECT sql FROM sqlite_schema WHERE name='version_identity_immutable'").get());
  assert(f.raw.prepare("SELECT sql FROM sqlite_schema WHERE name='pmb1_no_real_'||?||'_insert'").get(hash(Buffer.from('installations'))));
});

test('actual complete partition source construction and stale fetch/alarm refuse while closed without KV/SQL/alarm change',async t=>{
  const f=await setup(t),storage=new LocalStorage();t.after(()=>storage.db.close());
  await bootstrapPartitionMaintenance(storage);storage.db.exec(file('object-guards.sql'));
  const original={sql:snapshot(storage.db),kv:structuredClone([...storage.kv]),alarm:storage.alarm};
  const worker=new f.candidate.CandidatePartitionWorker({storage,waitUntil(){assert.fail('deferred work');}},f.env);
  assert.equal((await worker.fetch(new Request('https://internal.invalid/wake',{method:'POST',body:'{}'}))).status,503);
  await assert.rejects(worker.alarm(),/partition_maintenance_fenced/);
  assert.equal(snapshot(storage.db),original.sql);assert.deepEqual([...storage.kv],original.kv);assert.equal(storage.alarm,original.alarm);
});

test('complete no-REAL reader consumes real six-table partition schema and actual bootstrap KV without new markers',async t=>{
  const storage=new LocalStorage();t.after(()=>storage.db.close());await bootstrapPartitionMaintenance(storage);storage.db.exec(file('object-guards.sql'));
  const id={namespace:'synthetic-only',id:'one'},key=canonical([id.namespace,id.id]);
  const closure={interval:'synthetic-only',start:'1',end:'9',custody:'synthetic-only',writers:[{id:'application',epoch:'synthetic-1',disposition:'settled'}]};
  const fence={generation:'1',state:'closed',writerEpoch:'synthetic-1',custody:closure.custody,interval:closure.interval};
  const readerBytes=new Uint8Array(readFileSync(new URL('../pmb1-no-real-object-reader/reader.ts',import.meta.url)));
  const request={profile:PROFILE,expectedObjects:[{...id,guardManifest:JSON.parse(file('object-guard-manifest.json')),
    guardManifestSha256:stores.domains.object.guardManifestSha256,alarmKeys:stores.domains.object.readerClosedAlarmKeys}],
    closure,expectedWriterIds:['application'],expectedSources:{'reader.ts':hash(readerBytes)},sourceBytes:{'reader.ts':readerBytes},fences:{[key]:fence},
    limits:{objects:2,schema:128,tables:16,columns:128,rows:100,kv:100,bytes:1024*1024,calls:1000,page:10,milliseconds:30000}};
  let time=2;
  const adapter={async closure(){return structuredClone(closure);},async listObjects(after){return after===null?{entries:[id],next:key}:{entries:[],next:null};},
    async readObject(_,read){return read({async query(sql){return storage.db.prepare(sql).all().map(r=>({...r}));},
      async listKV(after,limit){const entries=[...storage.kv].sort((a,b)=>a[0].localeCompare(b[0])).filter(e=>after===null||e[0]>after).slice(0,limit);return {entries,next:entries.at(-1)?.[0]??null};},
      async getAlarm(){return storage.alarm;},async fence(){return {...fence,observedAt:String(time++)};}});}};
  const result=await capture(adapter,request);assert.equal(result.actualQualification,false);
  assert.deepEqual(Object.keys(result.objects[0].tables).sort(),stores.domains.object.tables);
  assert.deepEqual(result.objects[0].kv,[['pmb1:admission',['boolean',false]],['pmb1:wake-admission-sequence',['text','0']],['pmb1:wake-revision',['text','0']]]);
  assert.equal(result.objects[0].alarm.timeMs,null);
  // Native-wakeup close admits only null alarm. A pending alarm cannot be made
  // readable by inventing legacy marker keys or omitting its real SQL/KV facts.
  storage.alarm=123;time=2;await assert.rejects(capture(adapter,request),/alarm_order_identity/);
});

test('exact immutable target and force=false request; every pin/mixed profile/extra option refuses',()=>{
  const expected={profile:PROFILE,candidateSha2_256:binding.candidate,immutableVersion:'synthetic-immutable',configurationSha2_256:'b'.repeat(64),resourcesSha2_256:'c'.repeat(64)};
  assert.deepEqual(restorationRequest({...expected},expected),{versionId:'synthetic-immutable',force:false});
  for(const key of Object.keys(expected))assert.throws(()=>restorationRequest({...expected,[key]:'changed'},expected),/main_entry_unavailable/);
  assert.throws(()=>restorationRequest({...expected,force:true},expected),/main_entry_unavailable/);
  assert.throws(()=>compose({}),/main_entry_unavailable/);
});
