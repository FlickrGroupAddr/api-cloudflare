// MIT License; copyright 2026 Terry Ott. Synthetic private-holder/source models.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {freshFixture,prepareModelEvidenceUse} from './fixture.mjs';
import {OwningPartitionRuntime} from './owning-core.ts';
import {PrivatePartitionController} from './controller.ts';
import {setupLedger} from '../pmb1-runtime-evidence/fixture.mjs';
import {requiredCharge} from '../pmb1-runtime-evidence/ledger.ts';
import {consumeRuntimeFacts} from '../pmb1-retained-integration/runtime_facts.ts';
import {createFreshNativeSource} from './source.ts';
import {captureSupportedBoundary} from '../pmb1-native-object-reader/object-kv-interface.ts';
import {PartitionMaintenance} from '../../src/partition_maintenance.ts';
import {LocalD1} from '../pmb1-native-disposition/fixture.mjs';
const contract=JSON.parse(readFileSync(new URL('../pmb1-retained-integration/source-contract.json',import.meta.url)));
async function setup(t,beforePublish=async()=>{}){
 const reference={databaseId:'aaaaaaaa-0000-4000-8000-000000000000',envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:'native-preservation'};
 const f=freshFixture(reference,contract.sourceContextSha2_256);t.after(()=>f.close());
 await beforePublish(f);
 const keys=f.objects.map(o=>o.namespace+'/'+o.id),native=f.input.request.limits.bytes*keys.length,
   charge=requiredCharge(JSON.stringify(f.wire).length,keys.length,native);
 const s=await setupLedger(f.wire,keys,{now:Date.now(),reference,binding:{databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,
   lifecycle:f.f.config.binding.lifecycle,generation:f.f.config.binding.generation,nativeSourceDigest:f.input.request.expectedSources['fresh-source.ts'],ownerSourceDigest:f.input.request.expectedSources['owning-partition.ts']},
   header:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},review:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},allocation:{maxNativeBytes:native,maxAggregateBytes:charge.aggregate}});
 t.after(()=>s.close());const cores=new Map(),namespace=f.objects[0].namespace;
 const binding={idFromString:id=>id,get:id=>cores.get(id)},env={COORD:binding,PMB1_MAIN_JOURNAL:s.db};
 for(const object of f.objects)cores.set(object.id,new OwningPartitionRuntime({id:{toString:()=>object.id},storage:f.stores.get(object.id)},env,
   ()=>({ledger:s.ledger(),namespace,operation:reference.operation})));
 return{f,s,cores,binding,namespace,env};
}
test('owning-context snapshot RPC core consumes before first SQL and captures exact two owned stores',async t=>{
 const s=await setup(t),first=s.f.objects[0],core=s.cores.get(first.id),packet=s.f.input.packets[0];
 assert.equal(s.f.f.native.counts().sqlCalls,0);
 await assert.rejects(core.snapshotFresh(s.s.reference,packet.sha2_256));assert.equal(s.f.f.native.counts().sqlCalls,0);
 const authority={ledger:s.s.ledger(),namespace:s.namespace,operation:s.s.reference.operation},facts=await consumeRuntimeFacts(authority);
 const source=await createFreshNativeSource(facts.trusted.source(),{[s.namespace]:s.binding},authority.ledger,facts.envelope);
 assert.equal((await captureSupportedBoundary(source,facts.trusted.source().request)).objects.length,2);
 assert(s.f.f.native.counts().sqlCalls>0);assert(s.f.second.counts().sqlCalls>0);
 await assert.rejects(core.acquireFresh(s.s.reference,packet.sha2_256));
});

test('private same-owner reconciliation uses distinct noncapture attempt and refuses retirement after awaits',async t=>{
 for(const retire of [false,true]){
  let storage,token,domain;
  const s=await setup(t,async f=>{
    domain=new LocalD1();t.after(()=>domain.close());storage=writable(f.f.native);
    f.f.native.db.exec("UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");f.f.native.kv.set('pmb1:admission',true);
    const bridge=new PartitionMaintenance(storage,async()=>null);
    token=bridge.capture('fetch');await bridge.admit(token);await bridge.finish(token,domain,'returned');
    const retired={...token,version:'current-partition',instance:'synthetic-native-retired',retirementRecord:'synthetic-independent-native-retirement',operations:[]};
    f.wire.coverage.authenticated.retiredExecutions=[retired];f.payload.coverage.authenticated.retiredExecutions=[retired];
  });
  const use=await prepareModelEvidenceUse(s.s,s.f,'partition-reconcile'),id=s.f.objects[0].id;
  const env={...s.env,DB:domain},core=new OwningPartitionRuntime({id:{toString:()=>id},storage},env,purpose=>({
    ledger:purpose==='partition-reconcile'?use.state.ledger():s.s.ledger(),namespace:s.namespace,operation:purpose==='partition-reconcile'?purpose:s.s.reference.operation}));
  let retired=false;if(retire)domain.before=async()=>{if(!retired){retired=true;use.state.retire();}};
  if(retire)await assert.rejects(core.maintenanceReconcile(token,crypto.randomUUID()));
  else await core.maintenanceReconcile(token,crypto.randomUUID());
  assert.equal(use.state.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE envelope_id=? AND kind='native-consumed'").get(use.state.reference.envelopeId).n,0);
  const row=s.f.f.native.db.prepare('SELECT state,receipt FROM pmb1_partition_invocations WHERE id=?').get(token.id);assert.equal(row.state,'settled');assert(row.receipt);
 }
});
function writable(native){
 const db=native.db,kv=native.kv;
 const storage={sql:{exec(sql,...args){const statement=db.prepare(sql),names=statement.columns().map(c=>c.name),rows=statement.all(...args);return{columnNames:names,toArray:()=>rows,one:()=>rows[0],*[Symbol.iterator](){yield*rows;}};}},
 async transaction(fn){const old=structuredClone(kv);db.exec('BEGIN');try{const result=await fn({get:async key=>kv.get(key),put:async(key,value)=>kv.set(key,value),delete:async key=>kv.delete(key),getAlarm:async()=>null,deleteAlarm:async()=>{},
 list:async o=>new Map([...kv].filter(([key])=>!o.startAfter||key>o.startAfter).slice(0,o.limit))});db.exec('COMMIT');return result;}catch(e){db.exec('ROLLBACK');kv.clear();for(const[k,v]of old)kv.set(k,v);throw e;}}};
 return storage;
}
test('finite private controller delegates same-context stop/close, refuses substitution and never retries unknown',async t=>{
 const s=await setup(t),id=s.f.objects[0].id,native=s.f.f.native,storage=writable(native);
 native.db.exec("UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");native.kv.set('pmb1:admission',true);
 const core=new OwningPartitionRuntime({id:{toString:()=>id},storage},s.env,()=>({ledger:s.s.ledger(),namespace:s.namespace,operation:s.s.reference.operation}));
 let calls=0;const namespace={idFromString:value=>value,get:selected=>{assert.equal(selected,id);return{maintenanceStop:async(...args)=>{calls++;await core.maintenanceStop(...args);},maintenanceClose:async(...args)=>{calls++;await core.maintenanceClose(...args);}};}};
 const allocation=operation=>({operationId:crypto.randomUUID(),namespace:s.namespace,objectId:id,generation:'2',operation,fromMs:Date.now()-100,throughMs:Date.now()+10000,calls:1,operatorLedgerRecord:'synthetic-externally-reserved',independentSourceReviewRecord:'synthetic-source-reviewed'});
 const wrong=new PrivatePartitionController(namespace,'e'.repeat(32),allocation('stop'));await assert.rejects(wrong.run());assert.equal(calls,0);
 const stop=new PrivatePartitionController(namespace,s.namespace,allocation('stop'));await stop.run();assert.equal(native.kv.get('pmb1:admission'),false);await assert.rejects(stop.run());assert.equal(calls,1);
 const close=new PrivatePartitionController(namespace,s.namespace,allocation('close'));await close.run();assert.deepEqual(native.db.prepare('SELECT CAST(generation AS TEXT) generation,state FROM maintenance_control').get(),Object.assign(Object.create(null),{generation:'3',state:'closed'}));assert.equal(calls,2);
 assert.equal(s.s.db.raw.prepare("SELECT count(*) n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
 const lost=new PrivatePartitionController({idFromString:x=>x,get:()=>({maintenanceStop:async()=>{calls++;throw Error('lost_ack');}})},s.namespace,allocation('stop'));
 await assert.rejects(lost.run(),/outcome_unknown/);await assert.rejects(lost.run(),/outcome_unknown/);assert.equal(calls,3);
});
