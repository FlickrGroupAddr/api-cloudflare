// MIT License; copyright 2026 Terry Ott.
// Invented SOURCE-only qualification and publication fixtures. Actual remains NO-GO.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {freshFixture} from './fixture.mjs';
import {PrivateMainRuntime} from './main-private-core.ts';
import {createQualifiedRuntimeAuthority,qualifiedRuntimeAuthority} from './authority.ts';
import {setupLedger,SyntheticD1} from '../pmb1-runtime-evidence/fixture.mjs';
import {requiredCharge} from '../pmb1-runtime-evidence/ledger.ts';
import {LocalD1,assertNoOutbound} from '../pmb1-native-disposition/fixture.mjs';
const file=p=>readFileSync(new URL(p,import.meta.url),'utf8');
const contract=JSON.parse(file('../pmb1-retained-integration/source-contract.json'));
const snapshot=db=>JSON.stringify(db.prepare("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all().map(r=>r.type==='table'?[r,db.prepare('SELECT * FROM "'+r.name+'"').all()]:r),(_,v)=>typeof v==='bigint'?v.toString():v);
const id=()=>crypto.randomUUID();
async function setup(t){
 const reference={databaseId:'aaaaaaaa-0000-4000-8000-000000000000',envelopeId:id(),attemptId:id(),operation:'main-assess'};
 const f=freshFixture(reference,contract.sourceContextSha2_256),db=new SyntheticD1(),domain=new LocalD1();
 t.after(()=>{f.close();db.close();domain.close();assertNoOutbound();});
 db.raw.exec(file('../pmb1-native-journal/schema.sql'));
 db.raw.prepare(file('../pmb1-native-journal/provision.sql')).run(reference.databaseId,contract.sourceContextSha2_256,f.f.config.binding.lifecycle,f.f.config.binding.generation);
 // Complete the existing SQLite D1 adapter's direct-query surface, preserving
 // actual SQL and the original batch implementation; no runtime/verifier port is replaced.
 const prepare=db.prepare.bind(db);db.direct=[];
 db.prepare=sql=>{const statement=prepare(sql);statement.all=async()=>{db.requests++;db.statements++;db.direct.push(sql);return{success:true,results:db.raw.prepare(sql).all(...statement.args)};};return statement;};
 const env={DB:domain,PMB1_MAIN_JOURNAL:db,PMB1_VERSION_METADATA:{id:'synthetic-immutable-version'},COORD:{idFromString(){assert.fail('owner lookup');},get(){assert.fail('owner acquisition');}}};
 const q={namespace:f.objects[0].namespace,operation:'native-preservation',channel:{databaseId:reference.databaseId,schema:'pmb1-evidence-schema-v1',publisherSourceDigest:'1'.repeat(64),provenancePathDigest:'a'.repeat(64),holderPolicyDigest:'b'.repeat(64),nativeGetterQualificationRecord:'c'.repeat(64)}};
 let override;
 const authority=purpose=>override?override(purpose):createQualifiedRuntimeAuthority(env,q,purpose);
 const core=()=>new PrivateMainRuntime(env,authority);
 async function publish(change=()=>{},options={}){
  const wire=structuredClone(f.wire);change(wire);
  const keys=options.raw?f.objects.map(o=>o.namespace+'/'+o.id):[],nativeBytes=f.input.request.limits.bytes*keys.length;
  const ref=options.raw?{...reference,operation:'native-preservation'}:reference;wire.native.control=ref;
  return setupLedger(wire,keys,{db,now:Date.now(),reference:ref,binding:{databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,lifecycle:f.f.config.binding.lifecycle,generation:f.f.config.binding.generation,nativeSourceDigest:f.input.request.expectedSources['fresh-source.ts'],ownerSourceDigest:f.input.request.expectedSources['owning-partition.ts']},header:{mode:options.raw?'raw-capture':'evidence-use',fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end),...options.header},review:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},allocation:{maxNativeBytes:Math.max(1,nativeBytes),maxAggregateBytes:requiredCharge(JSON.stringify(wire).length,keys.length,Math.max(1,nativeBytes)).aggregate}});
 }
 return{f,db,domain,env,q,core,publish,reference,override:fn=>{override=fn;},target:{databaseId:reference.databaseId,domainDatabaseId:f.f.config.domainDatabaseId,candidate:contract.sourceContextSha2_256,lifecycle:f.f.config.binding.lifecycle,generation:f.f.config.binding.generation,versionId:env.PMB1_VERSION_METADATA.id}};
}

test('SOURCE-only current → existing-journal stop → later protected publication → full65 assessment',async t=>{
 const s=await setup(t),core=s.core(),before=snapshot(s.domain.db),native=[snapshot(s.f.f.native.db),snapshot(s.f.second.db)];
 assert.equal(qualifiedRuntimeAuthority(s.env),undefined);
 const current=await core.currentMain(s.target.domainDatabaseId,id());assert.deepEqual(current,{target:s.target,state:'open',revision:'0'});
 assert.equal(s.db.raw.prepare('SELECT count(*) n FROM pmb1_evidence_events').get().n,0);
 const stopped=await core.stopAdmission(current.target,id());assert.equal(stopped.admission,'stopped');
 const journalBefore=s.db.raw.prepare('SELECT * FROM pmb1_journal_control').get();
 assert.equal(journalBefore.revision,1);assert.equal(s.domain.calls.length,0);
 await assert.rejects(core.assessStopped(current.target,id())); // no published facts yet
 const publication=await s.publish();assert.equal(publication.db,s.db);
 assert.deepEqual(s.db.raw.prepare('SELECT * FROM pmb1_journal_control').get(),journalBefore);
 const counts={requests:0,statements:0};s.db.beforeBatch=async(_i,statements)=>{if(statements.some(x=>x.sql.includes('pmb1_evidence_'))){counts.requests++;counts.statements+=statements.length;}};
 const result=await s.core().assessStopped(current.target,id());assert.equal(result.status,'complete-supported');
 assert.deepEqual(counts,{requests:5,statements:8});
 const domainTables=new Set(s.domain.calls.flatMap(sql=>[...sql.matchAll(/FROM "([^"]+)" LIMIT 10001/g)].map(m=>m[1])));
 assert.equal(domainTables.size,65);
 assert.equal(snapshot(s.domain.db),before);assert.deepEqual([snapshot(s.f.f.native.db),snapshot(s.f.second.db)],native);
 assert.deepEqual(s.db.raw.prepare('SELECT * FROM pmb1_journal_control').get(),journalBefore);
 assert.equal(s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
 assert.equal(s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='terminal' AND outcome='complete'").get().n,1);
 await assert.rejects(s.core().assessStopped(current.target,id()));
});

test('private control refuses unqualified SOURCE, malformed/reused operation and exact target substitutions',async t=>{
 const s=await setup(t),core=s.core(),op=id();
 await assert.rejects(core.currentMain(s.target.domainDatabaseId,'not-uuid'));
 await core.currentMain(s.target.domainDatabaseId,op);await assert.rejects(core.currentMain(s.target.domainDatabaseId,op));
 for(const [key,value] of Object.entries({databaseId:id(),domainDatabaseId:s.target.databaseId,candidate:'0'.repeat(64),lifecycle:'wrong',generation:'2',versionId:'wrong-version',extra:'unknown'})){
  const target={...s.target,[key]:value};await assert.rejects(core.stopAdmission(target,id()));
 }
 s.override(()=>undefined);const before=s.db.requests;await assert.rejects(s.core().currentMain(s.target.domainDatabaseId,id()));assert.equal(s.db.requests,before);
 assert.throws(()=>createQualifiedRuntimeAuthority({...s.env,PMB1_VERSION_METADATA:undefined},s.q));
});

for(const scenario of ['wrong-version','wrong-context','wrong-database','wrong-holder','raw-mode','malformed','reordered','stale','retired','retire-await'])test('SOURCE-only assessment refuses '+scenario,async t=>{
 const s=await setup(t);await s.core().stopAdmission(s.target,id());
 if(scenario==='raw-mode'){await s.publish(()=>{},{raw:true});s.override(()=>createQualifiedRuntimeAuthority(s.env,s.q,'raw-capture'));await assert.rejects(s.core().assessStopped(s.target,id()));assert.equal(s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);return;}
 const publication=await s.publish(wire=>{if(scenario==='malformed')wire.native.packets[0].sha2_256='0'.repeat(64);});
 if(scenario==='reordered')s.db.afterBatch=async(_i,statements,results)=>{for(let i=0;i<statements.length;i++)if(statements[i].sql.includes('SELECT c.ordinal,c.payload')){assert(results[i].results.length>1);results[i].results.reverse();}};
 if(scenario==='retired')publication.retire();
 if(scenario==='stale')t.mock.timers.enable({apis:['Date'],now:publication.header.throughMs});
 if(scenario==='wrong-version')s.env.PMB1_VERSION_METADATA.id='wrong-version';
 if(scenario==='wrong-context'||scenario==='wrong-database'||scenario==='wrong-holder'){
  const q=structuredClone(s.q);if(scenario==='wrong-database')q.channel.databaseId=id();if(scenario==='wrong-holder')q.channel.holderPolicyDigest='0'.repeat(64);
  s.override(purpose=>{const a=createQualifiedRuntimeAuthority(s.env,q,purpose);return scenario==='wrong-context'?{...a,sourceContext:'0'.repeat(64)}:a;});
 }
 if(scenario==='retire-await'){let retired=false;s.domain.before=async()=>{if(!retired){retired=true;publication.retire();}};}
 await assert.rejects(s.core().assessStopped(s.target,id()));
 assert.equal(s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
 if(scenario==='retire-await')assert.equal(s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='retire'").get().n,1);
 else assert.equal(s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='terminal' AND outcome='complete'").get().n,0);
});
