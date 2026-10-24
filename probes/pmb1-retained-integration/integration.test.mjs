// MIT License; copyright 2026 Terry Ott. Invented source/synthetic facts only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { createRetainedCandidate } from './composition.ts';
import { restorationRequest } from '../pmb1-integer-candidate/candidate.ts';
import { setupTrustedFixture } from './trusted_inputs_fixture.mjs';
import { LocalD1, assertNoOutbound } from '../pmb1-native-disposition/fixture.mjs';
import { MAIN_ENTRY_FAMILIES } from '../../src/main_entry_maintenance.ts';
import { closedRestorationCheck } from './ordinary.ts';
import { reviewedFacts } from './reviewed_facts.ts';
const file = name => readFileSync(new URL(name,import.meta.url),'utf8');
const contract=JSON.parse(file('source-contract.json'));
const token=Array(13).fill('0000').join('-');
const hash=raw=>createHash('sha256').update(raw).digest('hex');
const req=(path='/api/v001/installations/current',init={})=>new Request('https://synthetic.invalid'+path,{headers:{Authorization:'Bearer '+token},...init});
const snapshot=db=>JSON.stringify(db.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").all().map(r=>r.type==='table'?[r,db.prepare('SELECT * FROM "'+r.name+'"').all()]:r),(_,v)=>typeof v==='bigint'?v.toString():v);
async function setup(t) {
 const f=setupTrustedFixture();t.after(()=>f.close());
 const binding={candidate:contract.sourceContextSha2_256,lifecycle:'synthetic',generation:'1'};
 f.expected.binding=binding;f.authenticated.binding=binding;f.config.binding=binding;
 const trusted=await f.assemble(),db=new LocalD1(),journal=new LocalD1('journal');
 db.db.close();journal.db.close();db.db=new DatabaseSync(':memory:');journal.db=new DatabaseSync(':memory:');
 db.db.exec(file('../pmb1-integer-candidate/d1-schema.sql'));
 db.db.exec("BEGIN;INSERT INTO fga_users VALUES('user');INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','user','lrc_plugin','active',7,'version');");
 db.db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)").run(hash(token));db.db.exec('COMMIT');
 db.db.exec(file('../pmb1-integer-candidate/d1-guards.sql'));db.db.exec('CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID;');
 journal.db.exec(file('../pmb1-native-journal/schema.sql'));
 journal.db.prepare(file('../pmb1-native-journal/provision.sql')).run(f.config.journalDatabaseId,binding.candidate,binding.lifecycle,binding.generation);
 t.after(()=>{db.close();journal.close();assertNoOutbound();});
 const env={DB:db,PMB1_MAIN_JOURNAL:journal,PMB1_OWNERS:f.native.bindings[f.native.id.namespace],PMB1_CAPTURE_CONTROL:f.native.control,FGA_READ_ENABLED:'1',FGA_ADMIN_ENABLED:'0',FGA_DISPATCH_ENABLED:'0'};
 const runtime=createRetainedCandidate(env,f.config,trusted);
 return {f,db,journal,trusted,env,runtime,binding};
}
test('real trusted assembly preserves all closed D1/object facts through ordinary authenticated success and negatives',async t=>{
 const s=await setup(t),before=snapshot(s.db.db),objects=snapshot(s.f.native.db),kv=structuredClone(s.f.native.kv);
 const response=await s.runtime.handler.fetch(req(),s.env);
 assert.equal(response.status,200);for(const [name,value] of Object.entries({'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'no-referrer'}))assert.equal(response.headers.get(name),value);
 assert.deepEqual(await response.json(),{schemaVersion:1,installationId:'installation',installationRevision:7,installationState:'active',presentedCredentialState:'current'});
 assert.equal(s.journal.db.prepare('SELECT count(*) n FROM pmb1_journal_invocations').get().n,0);
 for(const request of [req(undefined,{headers:{}}),req(undefined,{headers:{Authorization:'Bearer broken'}}),req('/api/v001/installations/current?x=1'),req(undefined,{method:'POST',body:'{}'}),req('/admin/login')])assert.notEqual((await s.runtime.handler.fetch(request,s.env)).status,200);
 await new Promise(resolve=>setImmediate(resolve));assert.equal(snapshot(s.db.db),before);assert.equal(snapshot(s.f.native.db),objects);assert.deepEqual(s.f.native.kv,kv);
 assert.equal(s.f.native.counts().acquisitions,0);
 assert.throws(()=>s.db.db.exec("UPDATE installations SET label='forbidden'"),/maintenance_closed/);
});
test('integrated observer closes complete65-table domain; unknown operations and cold reconstruction refuse',async t=>{
 const positive=await setup(t),result=await positive.runtime.maintenance.stop(5000);
 assert.equal(result.status,'complete-supported');assert.equal(Object.keys(positive.runtime.observer.retainedEvidence().domain.tables).length,65);
 const s=await setup(t);
 const inv='cccccccc-0000-4000-8000-000000000000';
 // Test-only fault injection into the external journal; compared stores remain closed.
 s.journal.db.prepare("INSERT INTO pmb1_journal_invocations(invocation,candidate,lifecycle,generation,entry) VALUES(?,?,?,?,'fetch')").run(inv,s.binding.candidate,s.binding.lifecycle,'1');
 await assert.rejects(s.runtime.maintenance.stop(5000));
 const restarted=createRetainedCandidate(s.env,s.f.config,s.trusted);
 const stop={...s.binding,admission:'stopped',evidence:s.journal.db.prepare('SELECT stop_evidence FROM pmb1_journal_control').get().stop_evidence};
 await assert.rejects(restarted.observer.assess(s.binding,stop,MAIN_ENTRY_FAMILIES,{deadlineMs:performance.now()+5000}));
 const races=await Promise.all(Array.from({length:8},()=>restarted.handler.fetch(req('/admin/login'),s.env)));
 assert(races.every(r=>r.status===503));assert.equal(s.journal.db.prepare('SELECT count(*) n FROM pmb1_journal_invocations').get().n,1);
 assert.equal((await restarted.handler.fetch(req(),s.env)).status,200);
});
test('forged assembly, source/facts substitution, wrong binding and foreign runtime are rejected',async t=>{
 const s=await setup(t);
 assert.throws(()=>createRetainedCandidate(s.env,s.f.config,{coverage:s.trusted.coverage,source:()=>s.trusted.source()}));
 assert.throws(()=>createRetainedCandidate(s.env,{...s.f.config,binding:{...s.binding,candidate:'f'.repeat(64)}},s.trusted));
 await assert.rejects(s.runtime.handler.fetch(req(),{...s.env}));
 assert.throws(()=>s.runtime.partition({storage:s.f.native.storage},'0'.repeat(32),s.f.native.id.id));
 const original=s.trusted.source();original.request.expectedSources['native.ts']='0'.repeat(64);
 assert.notDeepEqual(original.request.expectedSources,s.trusted.source().request.expectedSources);
});
test('retained-target request is exact, immutable, nonforced and has no discovery or rebuild fallback',()=>{
 const target={profile:contract.profile,candidateSha2_256:contract.sourceContextSha2_256,immutableVersion:'synthetic-immutable-version',configurationSha2_256:'b'.repeat(64),resourcesSha2_256:'c'.repeat(64)};
 assert.deepEqual(restorationRequest(target,structuredClone(target)),{versionId:target.immutableVersion,force:false});
 for(const field of ['candidateSha2_256','immutableVersion','configurationSha2_256','resourcesSha2_256'])assert.throws(()=>restorationRequest({...target,[field]:field==='immutableVersion'?'different':'d'.repeat(64)},target));
 assert.throws(()=>restorationRequest({...target,force:true},target));assert(Object.isFrozen(restorationRequest(target,target)));
});
test('ordinary helper body matches reviewed helper exactly and retained GET outlives absent maintenance facts',async t=>{
 const body=raw=>raw.slice(raw.indexOf('function closedRestorationCheck('),raw.indexOf('\n}',raw.indexOf('function closedRestorationCheck('))+2).replace(/^function /,'');
 assert.equal(body(file('ordinary.ts')),body(file('../pmb1-integer-candidate/candidate.ts')));
 const s=await setup(t),before=snapshot(s.db.db);
 assert.equal(await reviewedFacts(),undefined);
 assert.equal((await closedRestorationCheck(req(),s.env.DB,s.env.FGA_READ_ENABLED)).status,200);
 assert.equal(snapshot(s.db.db),before);
});
test('actual partition composition invokes complete native source and domain, once only, with closed state unchanged',async t=>{
 const s=await setup(t),before=snapshot(s.f.native.db),domain=snapshot(s.db.db),kv=structuredClone(s.f.native.kv);
 // Completed read-only fixture has no bound-parameter implementation; local
 // worker construction uses the same native database with the actual SQL API's
 // parameter signature. No production storage method or verifier is replaced.
 const storage={...s.f.native.storage,sql:{exec(sql,...args){const statement=s.f.native.db.prepare(sql);return {toArray:()=>statement.all(...args)};}}};
 const p=s.runtime.partition({storage,waitUntil:()=>assert.fail('deferred')},s.f.native.id.namespace,s.f.native.id.id);
 const proof=await p.disposition.verify('1');assert.equal(proof.oldVersionsFenced,true);
 assert.equal(Object.keys(p.disposition.retainedEvidence().domain.tables).length,65);
 assert.equal(p.disposition.retainedEvidence().captured.objects.length,1);
 assert.equal(s.f.native.counts().acquisitions,1);await assert.rejects(p.disposition.verify('1'));
 assert.equal(snapshot(s.f.native.db),before);assert.equal(snapshot(s.db.db),domain);assert.deepEqual(s.f.native.kv,kv);
 assert.equal((await p.worker.fetch(new Request('https://synthetic.invalid/wake',{method:'POST',body:'{}'}))).status,503);
});
