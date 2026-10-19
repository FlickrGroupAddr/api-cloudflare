// Synthetic actual source handlers plus real SQLite domain transactions. No provider calls.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import { sqlStore } from './sql_store.mjs';
import { LocalStorage, deferred } from '../probes/pmb1-native-alarm/local-storage.mjs';
import { PartitionMaintenance, bootstrapPartitionMaintenance } from '../src/partition_maintenance.ts';
import { PartitionWorker } from '../src/dispatch_worker.ts';

const disposition = async generation => ({ generation,preCloseExecutionsDisposed:true,
  temporaryExecutionsDisposed:true,oldVersionsFenced:true,queuedAndAlarmCallbacksDisposed:true });
const reconciled = async c => ({id:c.id,generation:c.generation,oldExecutionStopped:true,pendingD1Settled:true,evidence:'a'.repeat(64)});
const row = (s,id) => s.sql.exec('SELECT * FROM pmb1_partition_invocations WHERE id=?',id).toArray()[0];
const rows = s => s.sql.exec('SELECT * FROM pmb1_partition_invocations').toArray();
test('reviewed positive native-wakeup prerequisite remains immutable',()=>{
  assert.equal(createHash('sha256').update(readFileSync(new URL('../probes/pmb1-native-wakeup/candidate.ts',import.meta.url))).digest('hex'),
    '55f0a2c43b3974cbcb0f569c651cd8c7671e1d0f67d8adcb923b4999f27cc47c');
  assert.equal(PartitionWorker.prototype.alarm.length,0);
});
async function fixture(t, options={}) {
  const db=sqlStore(),storage=new LocalStorage(); t.after(()=>{db.raw.close();storage.db.close();});
  // D1 serializes database batches; this Node SQLite fixture does so explicitly.
  const batch=db.batch.bind(db);let tail=Promise.resolve();
  db.batch=statements=>{const result=tail.then(()=>batch(statements));tail=result.catch(()=>{});return result;};
  let now=Date.now();
  await bootstrapPartitionMaintenance(storage);
  let bridge=new PartitionMaintenance(storage,disposition,()=>now,reconciled);
  await bridge.reopen('1');
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('user','generation',1,'owner','write',NULL)"),
    db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)"),
    db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES('binding','user','photo','owner',1,1,'upload')"),
    db.prepare("INSERT INTO group_partitions(partition_id,user_id,group_id) VALUES('partition','user','group')"),
    db.prepare("INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id) VALUES('intent','binding','user','photo','group','partition',1,'queued','request')"),
  ]);
  const pending=[],calls=[];
  const env={DB:db,FGA_DISPATCH_ENABLED:'1',FGA_PARTITION_MAINTENANCE:()=>bridge,
    FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'synthetic-key',consumerSecret:'synthetic-secret'})},
    FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'generation',token:'synthetic-token',tokenSecret:'synthetic-token-secret'})}};
  const fetcher=async request=>{
    const params=request.method==='POST'?new URLSearchParams(await request.text()):new URL(request.url).searchParams;
    const method=params.get('method');calls.push(method);
    if(method==='flickr.photos.getAllContexts')return Response.json({stat:'ok',pool:[]});
    if(method==='flickr.groups.getInfo')return Response.json({stat:'ok',group:{id:'group',ispoolmoderated:'0'}});
    assert.equal(method,'flickr.groups.pools.add');
    assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM attempt_dispatches').get().n,1);
    await options.post?.({db,storage,bridge});
    const code=options.code??6;return Response.json(code==='ok'?{stat:'ok'}:{stat:'fail',code});
  };
  const ctx={storage,waitUntil:p=>{pending.push(p);void p.catch(()=>{});}};
  let worker=new PartitionWorker(ctx,env,{fetcher,hooks:options.hooks});
  const wake=()=>worker.fetch(new Request('https://internal.invalid/wake',{method:'POST',body:JSON.stringify({partitionId:'partition',wakeRevision:String(db.raw.prepare('SELECT wake_revision r FROM group_partitions').get().r),source:'admission'})}));
  const drain=async()=>{const out=await Promise.allSettled(pending.splice(0));return out;};
  const restart=()=>{bridge=new PartitionMaintenance(storage,disposition,()=>now,reconciled);worker=new PartitionWorker(ctx,env,{fetcher,hooks:options.hooks});return {bridge,worker};};
  return {db,storage,bridge,worker,env,calls,wake,drain,restart,clock:n=>now=n};
}

test('actual fetch/waitUntil commits code 6 permanent suppression and exact D1 receipt; duplicate wake is inert',async t=>{
  const f=await fixture(t);assert.equal((await f.wake()).status,204);
  assert.equal((await f.drain())[0].status,'fulfilled');
  assert.equal(f.db.raw.prepare('SELECT state FROM submission_intents').get().state,'moderation_submitted');
  assert.equal(f.db.raw.prepare('SELECT first_reason FROM submission_blocks').get().first_reason,'flickr_code_6');
  const receipt=JSON.parse(rows(f.storage)[0].receipt);assert.equal(receipt.reason,'flickr_code_6');assert.equal(receipt.blocked,1);assert.equal(receipt.pendingReservations,0);
  await f.wake();await f.drain();assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,1);
  await f.bridge.stop('2');await f.bridge.close('2');
});

test('actual in-flight POST settles all mandatory domain effects during stop and close waits for it',async t=>{
  const entered=deferred(),release=deferred();
  const f=await fixture(t,{code:9001,post:async()=>{entered.resolve();await release.promise;}});
  await f.wake();await entered.promise;await f.bridge.stop('2');
  await assert.rejects(f.bridge.close('2'),/partition_drain_incomplete/);
  release.resolve();assert.equal((await f.drain())[0].status,'fulfilled');
  assert.equal(f.db.raw.prepare('SELECT state FROM submission_intents').get().state,'delivery_uncertain');
  assert.equal(f.db.raw.prepare("SELECT enabled FROM flickr_write_gates WHERE scope='deployment'").get().enabled,0);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM submission_blocks').get().n,1);
  await f.bridge.close('2');assert.throws(()=>f.bridge.capture('alarm'),/fenced/);
});

test('D1 result rollback retains exact invocation and marked attempt across restart; close/reconcile refuse',async t=>{
  const f=await fixture(t,{hooks:{fault:async point=>{if(point==='response_received')f.db.fault=0;}}});
  await f.wake();assert.equal((await f.drain())[0].status,'rejected');
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM attempt_resolutions').get().n,0);
  const old=rows(f.storage)[0];assert.equal(old.state,'active');assert.equal(old.dispatch,1);
  f.db.fault=-1;const restarted=f.restart();await restarted.bridge.stop('2');
  await assert.rejects(restarted.bridge.reconcile({id:old.id,generation:old.generation,entry:old.entry},f.db),/domain_unsettled/);
  await assert.rejects(restarted.bridge.close('2'),/drain_incomplete/);
  assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,1);
});

test('DO receipt failure after real D1 suppression is reconciled by exact restart read without effect replay',async t=>{
  const f=await fixture(t);
  const original=f.storage.sql.exec;
  let fail=true;
  f.storage.sql.exec=(sql,...args)=>{if(fail&&sql.includes("SET state='settled',receipt=")){fail=false;throw Error('receipt_storage_fault');}return original(sql,...args);};
  await f.wake();assert.equal((await f.drain())[0].status,'rejected');
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM submission_blocks').get().n,1);
  const old=rows(f.storage)[0];const restarted=f.restart();await restarted.bridge.stop('2');
  await restarted.bridge.reconcile({id:old.id,generation:old.generation,entry:old.entry},f.db);
  await restarted.bridge.close('2');assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,1);
});

test('stop before POST fences further handoff while retaining unresolved D1 state',async t=>{
  const f=await fixture(t,{hooks:{fault:async point=>{if(point==='marker_committed')await f.bridge.stop('2');}}});
  await f.wake();assert.equal((await f.drain())[0].status,'rejected');
  assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,0);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM attempt_dispatches').get().n,1);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM flickr_rate_reservations WHERE released=0').get().n,0);
  await assert.rejects(f.bridge.close('2'),/drain_incomplete/);
});

test('synchronous fetch capture cannot cross close/reopen; restarted constructor writes nothing',async t=>{
  const f=await fixture(t);
  const captured=f.bridge.capture('fetch');await f.bridge.stop('2');await f.bridge.close('2');await f.bridge.reopen('3');
  await assert.rejects(f.bridge.admit(captured),/fenced/);
  const before=JSON.stringify(rows(f.storage));f.restart();assert.equal(JSON.stringify(rows(f.storage)),before);
  await assert.rejects(f.bridge.reconcile(captured,f.db),/fenced/);
});

test('actual fetch body pending is a durable drain obligation; stop cannot hide the callback',async t=>{
  const f=await fixture(t),entered=deferred(),release=deferred();
  const request=new Request('https://internal.invalid/wake',{method:'POST',body:'{}'});
  request.text=async()=>{entered.resolve();await release.promise;return '{}';};
  const response=f.worker.fetch(request);await entered.promise;await f.bridge.stop('2');
  await assert.rejects(f.bridge.close('2'),/drain_incomplete/);
  release.resolve();assert.equal((await response).status,400);await f.bridge.close('2');assert.deepEqual(f.calls,[]);
});

test('reconciliation without independent stopped-callback and settled-D1 evidence cannot dispose active work',async t=>{
  const f=await fixture(t),c=await f.bridge.admit(f.bridge.capture('fetch'));
  const restarted=new PartitionMaintenance(f.storage,disposition);
  await assert.rejects(restarted.reconcile(c,f.db),/reconciliation_unconfirmed/);
  assert.equal(row(f.storage,c.id).state,'active');
});

test('stale definitive rejection never retires a changed successor grant',async t=>{
  const f=await fixture(t,{code:98,post:async({db})=>{
    await db.batch([db.prepare("UPDATE flickr_links SET link_revision=2 WHERE user_id='user'"),
      db.prepare("UPDATE flickr_native_credentials SET active_generation='successor',link_revision=2 WHERE user_id='user'")]);
  }});
  await f.wake();assert.equal((await f.drain())[0].status,'fulfilled');
  assert.equal(f.db.raw.prepare('SELECT state FROM flickr_links').get().state,'linked');
  assert.equal(f.db.raw.prepare('SELECT active_generation generation FROM flickr_native_credentials').get().generation,'successor');
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM flickr_lifecycle_operations').get().n,0);
  assert.equal(JSON.parse(rows(f.storage)[0].receipt).grantSuperseded,1);
});

test('native ledger receipt rollback after confirmed domain result requires exact reconciliation and no POST replay',async t=>{
  const f=await fixture(t,{code:7});
  const c=await f.bridge.admit(f.bridge.capture('fetch'));await f.bridge.bind(c,'partition');
  await f.bridge.arm(c,'partition',Date.now()+50);await f.bridge.finish(c,f.db,'armed');
  const original=f.storage.sql.exec;let fail=true;
  f.storage.sql.exec=(sql,...args)=>{if(fail&&sql==='INSERT INTO pmb1_wake_results VALUES(?,?)'){fail=false;throw Error('native_result_fault');}return original(sql,...args);};
  f.clock(Date.now()+1000);const restarted=f.restart();await assert.rejects(restarted.worker.alarm(),/native_result_fault/);
  const old=rows(f.storage).at(-1);assert.equal(old.state,'settled');assert(old.due_token);
  await restarted.bridge.stop('2');await assert.rejects(restarted.bridge.close('2'),/drain_incomplete/);
  await restarted.bridge.reconcile({id:old.id,generation:old.generation,entry:old.entry},f.db);
  await restarted.bridge.close('2');assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,1);
});

test('eight actual concurrent hints preserve a single POST and immutable D1 attempt binding',async t=>{
  const f=await fixture(t);const replies=await Promise.all(Array.from({length:8},()=>f.wake()));assert(replies.every(x=>x.status===204));
  const results=await f.drain();assert(results.every(x=>x.status==='fulfilled'));
  assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,1);
  assert.equal(rows(f.storage).filter(x=>x.attempt_id!==null).length,1);
});

test('actual alarm consumes durable native due wake, commits D1 code 7 and keeps native ledger distinct',async t=>{
  const f=await fixture(t,{code:7});
  const c=await f.bridge.admit(f.bridge.capture('fetch'));await f.bridge.bind(c,'partition');
  await f.bridge.arm(c,'partition',Date.now()+50);await f.bridge.finish(c,f.db,'armed');
  f.clock(Date.now()+1000);const restarted=f.restart();await restarted.worker.alarm();
  assert.equal(f.db.raw.prepare('SELECT first_reason FROM submission_blocks').get().first_reason,'flickr_code_7');
  const local=f.storage.sql.exec('SELECT * FROM pmb1_wake_results').toArray();assert.equal(local[0].result,'confirmed_success');
  const domain=JSON.parse(rows(f.storage).at(-1).receipt);assert.equal(domain.reason,'flickr_code_7');
  await restarted.worker.alarm();assert.equal(f.calls.filter(x=>x==='flickr.groups.pools.add').length,1);
  await restarted.bridge.stop('2');await restarted.bridge.close('2');
});

test('grant rejection retains actual retirement and user pause before invocation settles',async t=>{
  const f=await fixture(t,{code:98});await f.wake();assert.equal((await f.drain())[0].status,'fulfilled');
  assert.equal(f.db.raw.prepare('SELECT state FROM flickr_connection_state').get().state,'relink_required');
  assert.equal(f.db.raw.prepare("SELECT enabled FROM flickr_write_gates WHERE scope='user'").get().enabled,0);
  assert.equal(JSON.parse(rows(f.storage)[0].receipt).grantRetired,1);
});

test('closed ordinary SQL guards and absent independent disposition fail closed',async t=>{
  const f=await fixture(t);const c=await f.bridge.admit(f.bridge.capture('fetch'));await f.bridge.bind(c,'partition');await f.bridge.finish(c,f.db,'bound');
  await f.bridge.stop('2');await f.bridge.close('2');
  for(const sql of ["INSERT INTO pmb1_partition_binding VALUES(1,'other')","UPDATE pmb1_partition_binding SET partition_id='other'","DELETE FROM pmb1_partition_invocations"])
    assert.throws(()=>f.storage.sql.exec(sql),/maintenance_closed/);
  const refused=new PartitionMaintenance(f.storage,async()=>null);
  await assert.rejects(refused.reopen('3'),/disposition_unconfirmed/);
});

test('unknown D1 claim acknowledgment preserves pre-dispatch claim identity and cannot be reconciled as empty',async t=>{
  const f=await fixture(t),batch=f.db.batch;
  f.db.batch=async statements=>{
    const result=await batch(statements);
    if(statements[0].sql.startsWith('UPDATE group_partitions SET lease_generation'))throw Error('claim_acknowledgment_lost');
    return result;
  };
  await f.wake();assert.equal((await f.drain())[0].status,'rejected');
  const old=rows(f.storage)[0];assert(old.claim_id);assert.equal(old.lease,null);
  await f.bridge.stop('2');await assert.rejects(f.bridge.reconcile({id:old.id,generation:old.generation,entry:old.entry},f.db),/claim_unbound/);
  await assert.rejects(f.bridge.close('2'),/drain_incomplete/);assert.deepEqual(f.calls,[]);
});

test('committed code 98 resolution without its required retirement is not domain settlement',async t=>{
  const f=await fixture(t,{code:98,hooks:{fault:async point=>{if(point==='result_committed')throw Error('before_grant_callback');}}});
  await f.wake();assert.equal((await f.drain())[0].status,'rejected');
  const old=rows(f.storage)[0];assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM attempt_resolutions').get().n,1);
  assert.equal(f.db.raw.prepare('SELECT state FROM flickr_links').get().state,'linked');
  await f.bridge.stop('2');await assert.rejects(f.bridge.reconcile({id:old.id,generation:old.generation,entry:old.entry},f.db),/domain_unsettled/);
  await assert.rejects(f.bridge.close('2'),/drain_incomplete/);
});

test('committed suppression without mandatory reservation release remains unresolved',async t=>{
  const f=await fixture(t,{hooks:{reservation:r=>r&&({...r,releaseUnused:async()=>{throw Error('release_failed');}})}});
  await f.wake();assert.equal((await f.drain())[0].status,'rejected');
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM submission_blocks').get().n,1);
  assert.equal(f.db.raw.prepare('SELECT COUNT(*) n FROM flickr_rate_reservations WHERE released=0').get().n,1);
  const old=rows(f.storage)[0];await f.bridge.stop('2');
  await assert.rejects(f.bridge.reconcile({id:old.id,generation:old.generation,entry:old.entry},f.db),/domain_unsettled/);
  await assert.rejects(f.bridge.close('2'),/drain_incomplete/);
});

test('missing bridge guard refuses both restarted composition and explicit reopen',async t=>{
  const f=await fixture(t);await f.bridge.stop('2');await f.bridge.close('2');
  f.storage.sql.exec('DROP TRIGGER pmb1_partition_binding_insert');
  assert.throws(()=>new PartitionMaintenance(f.storage,disposition),/schema_unconfirmed/);
  await assert.rejects(f.bridge.reopen('3'),/schema_unconfirmed/);
});
