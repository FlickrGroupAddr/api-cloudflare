// MIT License; copyright 2026 Terry Ott. Synthetic SOURCE, actual local SQL only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { freshFixture,prepareModelEvidenceUse } from './fixture.mjs';
import { acquireFreshNativeFacts } from './owner-core.ts';
import { createFreshNativeSource } from './source.ts';
import { captureSupportedBoundary } from '../pmb1-native-object-reader/object-kv-interface.ts';
import { setupLedger } from '../pmb1-runtime-evidence/fixture.mjs';
import { requiredCharge } from '../pmb1-runtime-evidence/ledger.ts';
import { consumeRuntimeFacts } from '../pmb1-retained-integration/runtime_facts.ts';
import { createFreshRetainedCandidate } from '../pmb1-retained-integration/fresh_composition.ts';
import { LocalD1, assertNoOutbound } from '../pmb1-native-disposition/fixture.mjs';
import { createQualifiedRuntimeAuthority, qualifiedRuntimeAuthority } from './authority.ts';
import { validateNativeDomainPlan } from './domain-plan.ts';
const contract=JSON.parse(readFileSync(new URL('../pmb1-retained-integration/source-contract.json',import.meta.url)));
const snapshot=db=>JSON.stringify(db.prepare("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all().map(r=>r.type==='table'?[r,db.prepare('SELECT * FROM "'+r.name+'"').all()]:r),(_,v)=>typeof v==='bigint'?v.toString():v);
async function setup(t,change=()=>{},allocationOverride={}) {
  const reference={databaseId:'aaaaaaaa-0000-4000-8000-000000000000',envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:'native-preservation'};
  const f=freshFixture(reference,contract.sourceContextSha2_256); t.after(()=>f.close());
  change(f);
  const keys=f.objects.map(o=>o.namespace+'/'+o.id),nativeBytes=f.input.request.limits.bytes*keys.length;
  const size=JSON.stringify(f.wire).length,charge=requiredCharge(size,keys.length,nativeBytes);
  const state=await setupLedger(f.wire,keys,{now:Date.now(),reference,
    binding:{databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,
      lifecycle:f.f.config.binding.lifecycle,generation:f.f.config.binding.generation,
      nativeSourceDigest:f.input.request.expectedSources['fresh-source.ts'],ownerSourceDigest:f.input.request.expectedSources['owning-partition.ts']},
    header:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},
    review:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},
    allocation:{maxNativeBytes:nativeBytes,maxAggregateBytes:charge.aggregate,...allocationOverride}});
  t.after(()=>state.close());
  let nativeAcquisitions=0;
  const bindings={[f.objects[0].namespace]:{idFromString:id=>id,get:id=>({async acquireFresh(ref,pin){
    const core={ledger:state.ledger(),operation:reference.operation,namespace:f.objects[0].namespace};
    const storage=f.stores.get(id); const guarded={...storage,transaction:async fn=>{nativeAcquisitions++;return storage.transaction(fn);}};
    return acquireFreshNativeFacts(core,guarded,id,ref,pin);
  }})}};
  const assessment=await prepareModelEvidenceUse(state,f,'main-assess');
  const ledger=state.ledger(),authority={ledger,operation:reference.operation,namespace:f.objects[0].namespace};
  return {f,state,bindings,ledger,authority,assessment,useFactory:async purpose=>{assert.equal(purpose,'main-assess');return assessment.load();},counts:()=>nativeAcquisitions};
}

test('actual protected SQL→fresh owner consume→complete two-object native source and full65 domain',async t=>{
  const s=await setup(t),facts=await consumeRuntimeFacts(s.authority);
  const reservationRequests=s.state.db.requests,reservationStatements=s.state.db.statements;
  const domain=new LocalD1();t.after(()=>domain.close());
  const before=[snapshot(s.f.f.native.db),snapshot(s.f.second.db),snapshot(domain.db)];
  const env={DB:domain,PMB1_MAIN_JOURNAL:s.state.db,COORD:s.bindings[s.f.objects[0].namespace],FGA_READ_ENABLED:'1'};
  const runtime=createFreshRetainedCandidate(env,facts.configuration,facts.trusted,s.ledger,facts.envelope,s.useFactory);
  assert.equal((await runtime.maintenance.stop(5000)).status,'complete-supported');
  assert.equal(Object.keys(runtime.observer.retainedEvidence().domain.tables).length,65);
  const storage={...s.f.f.native.storage,sql:{exec(sql,...args){const statement=s.f.f.native.db.prepare(sql);return {toArray:()=>statement.all(...args)};}}};
  const id=s.f.objects[0],partition=runtime.partition({storage},id.namespace,id.id);
  const beforeNativeRequests=s.state.db.requests,beforeNativeStatements=s.state.db.statements;
  const proof=await partition.disposition.verify('1');assert.equal(proof.oldVersionsFenced,true);
  assert.equal(partition.disposition.retainedEvidence().captured.objects.length,2);
  assert.equal(s.counts(),2);assert.equal(reservationRequests+s.state.db.requests-beforeNativeRequests,12);assert(reservationStatements+s.state.db.statements-beforeNativeStatements<=s.state.allocation.maxTotalStatements);
  assert.deepEqual([snapshot(s.f.f.native.db),snapshot(s.f.second.db),snapshot(domain.db)],before);
  assert.equal(s.state.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,2);
  assert.equal(s.state.db.raw.prepare("SELECT count(DISTINCT attempt_id) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,2);
  await assert.rejects(partition.disposition.verify('1'));assertNoOutbound();
});

test('source never acquires after packet substitution, cold replay, expiry or lost consume acknowledgement',async t=>{
  const bad=await setup(t,f=>{f.wire.native.packets[1].sha2_256='0'.repeat(64);});
  await assert.rejects(consumeRuntimeFacts(bad.authority));assert.equal(bad.counts(),0);
  const replay=await setup(t),facts=await consumeRuntimeFacts(replay.authority);
  await assert.rejects(consumeRuntimeFacts({...replay.authority,ledger:replay.state.ledger()}));assert.equal(replay.counts(),0);
  const expired=await setup(t);expired.state.clock.now=expired.state.header.throughMs;
  await assert.rejects(consumeRuntimeFacts(expired.authority));assert.equal(expired.counts(),0);
  const lost=await setup(t),reserved=await consumeRuntimeFacts(lost.authority);
  lost.state.db.afterBatch=async(_i,statements)=>{if(statements.some(s=>s.args?.includes('native-consumed')))throw Error('lost_ack');};
  const source=await createFreshNativeSource(reserved.trusted.source(),lost.bindings,lost.ledger,reserved.envelope);
  await assert.rejects(captureSupportedBoundary(source,reserved.trusted.source().request));assert.equal(lost.counts(),0);
  assert.equal(lost.state.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,1);
  lost.state.db.afterBatch=undefined;
  const key=lost.f.objects[0].namespace+'/'+lost.f.objects[0].id;
  await assert.rejects(lost.state.ledger().consume(reserved.envelope.reference,key));assert.equal(lost.counts(),0);
  void facts;
});

test('retirement between native owner acquisitions prevents positive result and cannot borrow the next capture',async t=>{
  const s=await setup(t),facts=await consumeRuntimeFacts(s.authority),namespace=s.f.objects[0].namespace;
  const base=s.bindings[namespace],binding={idFromString:id=>id,get:id=>({async acquireFresh(ref,pin){
    const value=await base.get(id).acquireFresh(ref,pin);s.state.retire();return value;
  }})};
  const source=await createFreshNativeSource(facts.trusted.source(),{[namespace]:binding},s.ledger,facts.envelope);
  await assert.rejects(captureSupportedBoundary(source,facts.trusted.source().request));
  assert.equal(s.counts(),1);
  assert.equal(s.state.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,1);
});

test('same source, journal, objects and binding accept separately reviewed fresh interval after expiry and cold restart',async t=>{
  const s=await setup(t),first=await consumeRuntimeFacts(s.authority);
  const source=await createFreshNativeSource(first.trusted.source(),s.bindings,s.ledger,first.envelope);
  await captureSupportedBoundary(source,first.trusted.source().request);
  const original=s.state.db.raw.prepare('SELECT header_json FROM pmb1_evidence_envelopes WHERE envelope_id=?').get(s.state.reference.envelopeId).header_json;
  s.state.retire();
  t.mock.timers.enable({apis:['Date'],now:s.state.header.throughMs+1001});
  const reference={...s.state.reference,envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID()};
  const fresh=freshFixture(reference,contract.sourceContextSha2_256);t.after(()=>fresh.close());
  const keys=fresh.objects.map(o=>o.namespace+'/'+o.id),nativeBytes=fresh.input.request.limits.bytes*keys.length;
  const charge=requiredCharge(JSON.stringify(fresh.wire).length,keys.length,nativeBytes);
  const second=await setupLedger(fresh.wire,keys,{db:s.state.db,now:Date.now(),reference,binding:s.state.binding,
    provenance:s.state.provenance,
    header:{fromMs:Number(fresh.input.request.closure.start),throughMs:Number(fresh.input.request.closure.end)},
    review:{fromMs:Number(fresh.input.request.closure.start),throughMs:Number(fresh.input.request.closure.end),rootRecord:'a'.repeat(64),reviewRecord:'b'.repeat(64)},
    allocation:{maxNativeBytes:nativeBytes,maxAggregateBytes:charge.aggregate}});
  const ledger=second.ledger(),authority={ledger,operation:reference.operation,namespace:fresh.objects[0].namespace};
  const next=await consumeRuntimeFacts(authority),namespace=fresh.objects[0].namespace;
  const bindings={[namespace]:{idFromString:id=>id,get:id=>({acquireFresh:(ref,pin)=>
    acquireFreshNativeFacts({...authority,ledger:second.ledger()},s.f.stores.get(id),id,ref,pin)})}};
  const nextSource=await createFreshNativeSource(next.trusted.source(),bindings,ledger,next.envelope);
  const capture=await captureSupportedBoundary(nextSource,next.trusted.source().request);
  assert.equal(capture.objects.length,2);
  assert.deepEqual(second.binding,s.state.binding);assert.equal(second.db,s.state.db);
  assert.equal(second.db.raw.prepare('SELECT header_json FROM pmb1_evidence_envelopes WHERE envelope_id=?').get(s.state.reference.envelopeId).header_json,original);
  assert.equal(second.db.raw.prepare("SELECT count(DISTINCT attempt_id) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,4);
  await assert.rejects(second.ledger().consume(first.envelope.reference,keys[0]));
});

test('concrete native VERSION_METADATA selection works with qualified SOURCE anchors and refuses native substitution',async t=>{
  const s=await setup(t),p=s.state.provenance;
  const qualification={namespace:s.f.objects[0].namespace,operation:s.state.reference.operation,
    channel:{databaseId:s.state.binding.databaseId,schema:s.state.binding.schema,publisherSourceDigest:p.publisherSourceDigest,
      provenancePathDigest:p.provenancePathDigest,holderPolicyDigest:p.holderPolicyDigest,
      nativeGetterQualificationRecord:p.nativeGetterQualificationRecord}};
  const env={PMB1_MAIN_JOURNAL:s.state.db,PMB1_VERSION_METADATA:{id:s.state.binding.immutableVersion,tag:'synthetic',timestamp:'synthetic'}};
  assert.equal(qualifiedRuntimeAuthority(env),undefined);
  assert.throws(()=>createQualifiedRuntimeAuthority({...env,PMB1_VERSION_METADATA:undefined},qualification));
  const wrong=createQualifiedRuntimeAuthority({...env,PMB1_VERSION_METADATA:{...env.PMB1_VERSION_METADATA,id:'wrong-version'}},qualification);
  await assert.rejects(consumeRuntimeFacts(wrong));assert.equal(s.counts(),0);
  const authority=createQualifiedRuntimeAuthority(env,qualification),facts=await consumeRuntimeFacts(authority);
  const namespace=s.f.objects[0].namespace,bindings={[namespace]:{idFromString:id=>id,get:id=>({acquireFresh:(ref,pin)=>
    acquireFreshNativeFacts(createQualifiedRuntimeAuthority(env,qualification),s.f.stores.get(id),id,ref,pin)})}};
  const source=await createFreshNativeSource(facts.trusted.source(),bindings,authority.ledger,facts.envelope);
  assert.equal((await captureSupportedBoundary(source,facts.trusted.source().request)).objects.length,2);
});

test('fresh native D1 plan keeps every canonical guard and binds open-phase store generation independently',async t=>{
  const s=await setup(t,f=>{f.wire.configuration.domainControl.generation='2';f.wire.configuration.domainControl.state='open';});
  const plan=s.f.payload.configuration.domainPlan;
  assert.equal(Object.keys(validateNativeDomainPlan(plan).tables).length,65);
  for(const change of [p=>p.schema.pop(),p=>{p.schema.find(r=>r.type==='trigger').sql+=' ';},
    p=>p.schema.push({type:'table',name:'extra',tbl_name:'extra',sql:'CREATE TABLE extra(x)'})]){
    const bad=structuredClone(plan);change(bad);assert.throws(()=>validateNativeDomainPlan(bad));
  }
  const facts=await consumeRuntimeFacts(s.authority),domain=new LocalD1();t.after(()=>domain.close());
  domain.db.exec("UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");
  const before=snapshot(domain.db),env={DB:domain,PMB1_MAIN_JOURNAL:s.state.db,COORD:s.bindings[s.f.objects[0].namespace]};
  const runtime=createFreshRetainedCandidate(env,facts.configuration,facts.trusted,s.ledger,facts.envelope,s.useFactory);
  assert.notEqual(facts.configuration.binding.generation,facts.configuration.domainControl.generation);
  assert.equal((await runtime.maintenance.stop(5000)).status,'complete-supported');
  assert.equal(Object.keys(runtime.observer.retainedEvidence().domain.tables).length,65);assert.equal(snapshot(domain.db),before);
});

test('separate assessment use and deferred raw final checks refuse retirement during awaited domain reads',async t=>{
  const assessment=await setup(t),domain=new LocalD1();t.after(()=>domain.close());
  const facts=await consumeRuntimeFacts(assessment.authority),env={DB:domain,PMB1_MAIN_JOURNAL:assessment.state.db,COORD:assessment.bindings[assessment.f.objects[0].namespace]};
  let retired=false;domain.before=async()=>{if(!retired){retired=true;assessment.assessment.state.retire();}};
  const runtime=createFreshRetainedCandidate(env,facts.configuration,facts.trusted,assessment.ledger,facts.envelope,assessment.useFactory);
  await assert.rejects(runtime.maintenance.stop(5000));assert.equal(assessment.counts(),0);
  assert.equal(assessment.state.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE envelope_id=? AND kind='native-consumed'").get(assessment.assessment.state.reference.envelopeId).n,0);
  const raw=await setup(t),rawDomain=new LocalD1();t.after(()=>rawDomain.close());
  const rawFacts=await consumeRuntimeFacts(raw.authority),rawEnv={DB:rawDomain,PMB1_MAIN_JOURNAL:raw.state.db,COORD:raw.bindings[raw.f.objects[0].namespace]},
    current=createFreshRetainedCandidate(rawEnv,rawFacts.configuration,rawFacts.trusted,raw.ledger,rawFacts.envelope,raw.useFactory);
  const storage={...raw.f.f.native.storage,sql:{exec(sql,...args){const statement=raw.f.f.native.db.prepare(sql);return{toArray:()=>statement.all(...args)};}}};
  let rawRetired=false;rawDomain.before=async()=>{if(!rawRetired){rawRetired=true;raw.state.retire();}};
  const id=raw.f.objects[0],partition=current.partition({storage},id.namespace,id.id);
  await assert.rejects(partition.disposition.verify('1'));assert.equal(raw.counts(),2);
});

test('complete native byte allocation is checked before capability resolution and noncapture use cannot borrow it',async t=>{
  const s=await setup(t,()=>{},{maxNativeBytes:2*4194304-1});
  await assert.rejects(consumeRuntimeFacts(s.authority));assert.equal(s.counts(),0);
  assert.equal(s.f.f.native.counts().sqlCalls,0);assert.equal(s.f.second.counts().sqlCalls,0);
  const use=await s.assessment.load();assert.equal(use.envelope.header.mode,'evidence-use');
  const source=await createFreshNativeSource(use.trusted.source(),s.bindings,use.ledger,use.envelope);
  await assert.rejects(captureSupportedBoundary(source,use.trusted.source().request));assert.equal(s.counts(),0);
});
