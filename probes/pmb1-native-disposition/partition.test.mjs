// MIT License; copyright 2026 Terry Ott. Source/synthetic evidence only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { NativePartitionDisposition, validatePartitionCapture } from './partition.ts';
import { D1DomainReader } from './domain.ts';
import { LocalD1, coverage, BINDING, BOUNDS, JOURNAL, DOMAIN, assertNoOutbound } from './fixture.mjs';
import { nativeFixture } from './native-fixture.mjs';
import { LocalStorage } from '../pmb1-native-alarm/local-storage.mjs';
import { PartitionMaintenance, bootstrapPartitionMaintenance } from '../../src/partition_maintenance.ts';
import { PartitionWorker } from '../../src/dispatch_worker.ts';
const reason=value=>error=>error.reason===value;
const deadline=()=>performance.now()+10000;
const reader=db=>new D1DomainReader(db,BOUNDS,{databaseId:DOMAIN,generation:'1',state:'closed'});
const config=f=>({binding:BINDING,journalDatabaseId:JOURNAL,domainDatabaseId:DOMAIN,namespace:f.id.namespace,id:f.id.id,deadlineMs:deadline(),bounds:BOUNDS,source:f.input});
const setup=async()=>{const f=nativeFixture(),db=new LocalD1(),storage=new LocalStorage();await bootstrapPartitionMaintenance(storage);
  // Initial synthetic bootstrap only. The tested verifier never calls this.
  const bridge=new PartitionMaintenance(storage,async generation=>({generation,preCloseExecutionsDisposed:true,temporaryExecutionsDisposed:true,oldVersionsFenced:true,queuedAndAlarmCallbacksDisposed:true}));
  await bridge.reopen('1');return {f,db,storage,bridge,close(){f.close();db.close();storage.db.close();}};};

test('production native factory reads complete partition SQL/KV/alarm and complete domain before positive reopen disposition',async()=>{
  const f=nativeFixture(),db=new LocalD1();try{
    const observer=new NativePartitionDisposition(config(f),f.storage,reader(db),coverage(),f.bindings,f.control);
    const proof=await observer.verify('1');assert.equal(proof.generation,'1');assert.equal(proof.oldVersionsFenced,true);
    assert.equal(f.counts().acquisitions,1);assert.equal(f.counts().completions,1);
    const facts=observer.retainedEvidence();assert.equal(facts.captured.actualQualification,false);
    assert.equal(Object.keys(facts.domain.tables).length,65);
    for(const edit of [x=>x.objects[0].kv.push(['pmb1:wake-value',['text','stale']]),
      x=>{x.objects[0].alarm.timeMs='100';},x=>{x.objects[0].before.generation='2';},
      x=>{x.objects[0].tables.pmb1_partition_invocations.rows.push({identity:'1',cells:x.objects[0].tables.pmb1_partition_invocations.columns.map(column=>['text',column==='state'?'active':'synthetic'])});},
      x=>{delete x.objects[0].tables.pmb1_wake_executions;}]){
      const bad=structuredClone(facts.captured);edit(bad);assert.throws(()=>validatePartitionCapture(bad,'1',f.id.namespace,f.id.id));
    }
    const extra=structuredClone(facts.captured),other=structuredClone(extra.objects[0]);other.id='d'.repeat(64);
    other.kv.push(['pmb1:wake-value',['text','other-object-pending']]);extra.objects.push(other);
    assert.throws(()=>validatePartitionCapture(extra,'1',f.id.namespace,f.id.id),reason('partition_scheduled_value'));
    await assert.rejects(observer.verify('1'),reason('partition_native_read_spent'));
  }finally{f.close();db.close();}
});
test('actual native acquisition refuses retained scheduled value without cleanup or reopening',async()=>{
  const f=nativeFixture(),db=new LocalD1();try{
    f.kv.set('pmb1:wake-value','pending');
    const observer=new NativePartitionDisposition(config(f),f.storage,reader(db),coverage(),f.bindings,f.control);
    await assert.rejects(observer.verify('1'),reason('partition_scheduled_value'));
    assert.equal(f.kv.get('pmb1:wake-value'),'pending');assert.equal(f.counts().acquisitions,1);
  }finally{f.close();db.close();}
});
test('restart exact unbound invocation reconciles only authenticated old execution and complete settled D1 facts',async()=>{
  const s=await setup();try{
    const capture=s.bridge.capture('fetch');await s.bridge.admit(capture);
    const retired={...capture,version:'current-partition',instance:'old-native-instance',retirementRecord:'synthetic/native-retired',operations:[]};
    const observed=new NativePartitionDisposition(config(s.f),s.storage,reader(s.db),coverage([retired]),s.f.bindings,s.f.control);
    const proof=await observed.reconcile(capture);assert.equal(proof.oldExecutionStopped,true);assert.equal(proof.pendingD1Settled,true);
    assert.match(proof.evidence,/^[a-f0-9]{64}$/);assert.equal(s.f.counts().acquisitions,0);
    const restarted=new PartitionMaintenance(s.storage,async()=>{throw Error('no reopen');},Date.now,observed.reconcile);
    // Existing reconciliation records only local disposition; no result, claim,
    // release, provider or domain-operation replay is introduced by the observer.
    await restarted.reconcile(capture,s.db);
    assert.equal(s.storage.sql.exec('SELECT state FROM pmb1_partition_invocations WHERE id=?',capture.id).toArray()[0].state,'settled');
    assert.equal(s.db.calls.some(sql=>!sql.startsWith('SELECT ')),false);
    const noRetirement=new NativePartitionDisposition(config(s.f),s.storage,reader(s.db),coverage(),s.f.bindings,s.f.control);
    await assert.rejects(noRetirement.reconcile(capture),reason('partition_old_execution_unobserved'));
    await assert.rejects(observed.reconcile({...capture,generation:'3'}),reason('partition_old_execution_unobserved'));
  }finally{s.close();}
});
test('exact original lease/attempt/result and grant safety evidence validate; substitutions refuse',async()=>{
  const s=await setup();try{
    const o=new NativePartitionDisposition(config(s.f),s.storage,reader(s.db),coverage(),s.f.bindings,s.f.control);
    const base=await reader(s.db).capture(deadline());
    const t=v=>['text',Buffer.from(v).toString('hex').toUpperCase()],i=v=>['integer',v];
    const facts=structuredClone(base);
    facts.tables.submission_attempts=[{attempt_id:t('attempt'),intent_id:t('intent'),lease_id:t('lease'),lease_generation:i('9007199254740993')}];
    facts.tables.attempt_resolutions=[{attempt_id:t('attempt'),outcome:t('delivery_uncertain'),flickr_code:i('6')}];
    facts.tables.submission_intents=[{intent_id:t('intent'),state:t('delivery_uncertain'),partition_id:t('partition'),photo_id:t('photo'),group_id:t('group'),user_id:t('user')}];
    facts.tables.submission_blocks=[{photo_id:t('photo'),group_id:t('group')}];
    facts.tables.attempt_dispatches=[{attempt_id:t('attempt')}];
    const row={id:crypto.randomUUID(),generation:'2',entry:'fetch',partition_id:'partition',claim_id:'claim',lease:JSON.stringify({headId:'intent',partitionId:'partition',invocationId:'claim',leaseId:'lease',generation:'9007199254740993'}),
      attempt_id:'attempt',attempt_binding:JSON.stringify({attemptId:'attempt',intentId:'intent',leaseId:'lease',generation:'9007199254740993'}),grant_binding:null,dispatch:1,state:'active',receipt:null,due_token:null};
    o.validateOriginal(row,facts);
    for(const edit of [r=>{r.attempt_binding=JSON.stringify({attemptId:'attempt',leaseId:'different',generation:'9007199254740993'});},
      r=>{r.lease=JSON.stringify({headId:'other'});},r=>{r.attempt_id='other';},r=>{r.partition_id='other';}]){
      const bad=structuredClone(row);edit(bad);assert.throws(()=>o.validateOriginal(bad,facts),reason('partition_domain_original_unsettled'));
    }
    facts.tables.attempt_resolutions[0].flickr_code=i('98');
    assert.throws(()=>o.validateOriginal(row,facts),reason('partition_grant_result_unsettled'));
    row.grant_binding=JSON.stringify({generation:'old-grant',revision:'4'});
    facts.tables.flickr_native_credentials=[{user_id:t('user'),active_generation:t('replacement')}];
    facts.tables.flickr_links=[{user_id:t('user'),link_revision:i('5')}];o.validateOriginal(row,facts);
  }finally{s.close();}
});
test('public restart refuses a substituted settled receipt after genuine admit and finish',async()=>{
  const s=await setup();try{
    const token=s.bridge.capture('fetch');await s.bridge.admit(token);await s.bridge.finish(token,s.db,'returned');
    const retired={...token,version:'current-partition',instance:'old-native-instance',retirementRecord:'synthetic/native-retired',operations:[]};
    const observer=new NativePartitionDisposition(config(s.f),s.storage,reader(s.db),coverage([retired]),s.f.bindings,s.f.control);
    assert.equal((await observer.reconcile(token)).pendingD1Settled,true);
    const restarted=new PartitionMaintenance(s.storage,async()=>{throw Error('no reopen');},Date.now,observer.reconcile);
    for(const receipt of ['not-json','null','[]',JSON.stringify({result:'returned',attempt:'substituted'})]){
      s.storage.sql.exec('UPDATE pmb1_partition_invocations SET receipt=? WHERE id=?',receipt,token.id);
      await assert.rejects(observer.reconcile(token));
      await assert.rejects(restarted.reconcile(token,s.db));
      assert.equal(s.storage.sql.exec('SELECT receipt FROM pmb1_partition_invocations WHERE id=?',token.id).toArray()[0].receipt,receipt);
    }
  }finally{s.close();}
});
test('public valid bound restart checks genuine dispatch/domain receipt and active first-receipt recovery without replay',async()=>{
  const s=await setup();try{
    // Exercise the actual worker, admission/lease/attempt, provider-shaped result,
    // mandatory suppression/release and original local finish implementation.
    s.db.db.exec("UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");
    await s.db.batch([
      s.db.prepare("INSERT INTO fga_users VALUES('user')"),
      s.db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
      s.db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
      s.db.prepare("INSERT INTO flickr_native_credentials VALUES('user','generation',1,'owner','write',NULL)"),
      s.db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)"),
      s.db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES('binding','user','photo','owner',1,1,'upload')"),
      s.db.prepare("INSERT INTO group_partitions(partition_id,user_id,group_id) VALUES('partition','user','group')"),
      s.db.prepare("INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id) VALUES('intent','binding','user','photo','group','partition',1,'queued','request')"),
    ]);
    const pending=[],providerCalls=[];
    const env={DB:s.db,FGA_DISPATCH_ENABLED:'1',FGA_PARTITION_MAINTENANCE:()=>s.bridge,
      FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'synthetic-key',consumerSecret:'synthetic-secret'})},
      FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'generation',token:'synthetic-token',tokenSecret:'synthetic-token-secret'})}};
    const fetcher=async request=>{
      const params=request.method==='POST'?new URLSearchParams(await request.text()):new URL(request.url).searchParams;
      const method=params.get('method');providerCalls.push(method);
      if(method==='flickr.photos.getAllContexts')return Response.json({stat:'ok',pool:[]});
      if(method==='flickr.groups.getInfo')return Response.json({stat:'ok',group:{id:'group',ispoolmoderated:'0'}});
      assert.equal(method,'flickr.groups.pools.add');return Response.json({stat:'fail',code:6});
    };
    const worker=new PartitionWorker({storage:s.storage,waitUntil:p=>{pending.push(p);void p.catch(()=>{});}},env,{fetcher});
    const response=await worker.fetch(new Request('https://internal.invalid/wake',{method:'POST',body:JSON.stringify({partitionId:'partition',wakeRevision:'1',source:'admission'})}));
    assert.equal(response.status,204);assert.equal((await Promise.allSettled(pending))[0].status,'fulfilled');
    const row=s.storage.sql.exec('SELECT * FROM pmb1_partition_invocations').toArray()[0];
    assert.equal(row.state,'settled');assert(row.lease);assert(row.attempt_id);assert.equal(row.dispatch,1);
    const token={id:row.id,generation:row.generation,entry:row.entry},retired={...token,version:'current-partition',instance:'old-native-instance',retirementRecord:'synthetic/native-retired',operations:[]};
    const boundReader=new D1DomainReader(s.db,BOUNDS,{databaseId:DOMAIN,generation:'2',state:'open'});
    const observer=new NativePartitionDisposition(config(s.f),s.storage,boundReader,coverage([retired]),s.f.bindings,s.f.control);
    const restarted=new PartitionMaintenance(s.storage,async()=>{throw Error('no reopen');},Date.now,observer.reconcile);
    const writes=s.db.calls.filter(sql=>!sql.startsWith('SELECT ')).length,dispatches=providerCalls.length;
    assert.equal((await observer.reconcile(token)).pendingD1Settled,true);await restarted.reconcile(token,s.db);
    const genuine=JSON.parse(row.receipt);
    const substitutions={attemptId:'other',intentId:'other',leaseId:'other',generation:'9007199254740993',outcome:'added',intentState:'added',
      reason:'substituted',code:98,marked:0,blocked:0,pendingReservations:1,grantRetired:1,grantSuperseded:1};
    for(const receipt of ['not-json',...Object.entries(substitutions).map(([field,value])=>JSON.stringify({...genuine,[field]:value}))]){
      s.storage.sql.exec('UPDATE pmb1_partition_invocations SET receipt=? WHERE id=?',receipt,token.id);
      await assert.rejects(observer.reconcile(token));await assert.rejects(restarted.reconcile(token,s.db));
    }
    s.storage.sql.exec("UPDATE pmb1_partition_invocations SET state='active',receipt='ambiguous' WHERE id=?",token.id);
    await assert.rejects(observer.reconcile(token),reason('partition_receipt_state'));
    // A lost local receipt remains recoverable after all original D1 facts settled.
    s.storage.sql.exec("UPDATE pmb1_partition_invocations SET state='active',receipt=NULL WHERE id=?",token.id);
    assert.equal((await observer.reconcile(token)).oldExecutionStopped,true);await restarted.reconcile(token,s.db);
    const recovered=s.storage.sql.exec('SELECT state,receipt FROM pmb1_partition_invocations WHERE id=?',token.id).toArray()[0];
    assert.equal(recovered.state,'settled');assert.equal(JSON.parse(recovered.receipt).attemptId,row.attempt_id);
    assert.equal(providerCalls.length,dispatches);assert.equal(s.db.calls.filter(sql=>!sql.startsWith('SELECT ')).length,writes);
  }finally{s.close();}
});
test.after(assertNoOutbound);
