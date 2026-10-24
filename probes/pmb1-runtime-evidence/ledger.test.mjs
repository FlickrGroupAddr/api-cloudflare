// MIT License; copyright 2026 Terry Ott.
// Synthetic SQLite/transport/failure tests; no actual evidence or qualification.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setupLedger,SyntheticD1} from './fixture.mjs';
import {RuntimeEvidenceLedger,encoded,EVIDENCE_SQL,executionAnchors,validateAllocation} from './ledger.ts';
import {preparePublication,publishReviewedEvidence,publicationReadback} from './publisher.ts';

async function finish(f,keys=f.header.captureKeys){
  const source=f.ledger(),packet=await source.reserveSelected(f.reference.operation);
  for(const key of keys){const owner=f.ledger();const acquired=await owner.consume(f.reference,key);
    assert.deepEqual(acquired.payload,JSON.parse(f.payloadText));await source.complete(f.reference,key,'complete');}
  await source.revalidate(packet);return packet;
}
test('two complete objects use distinct durable raw attempts, finite exact allocation and fresh primary each call',async()=>{
  const keys=['namespace/object-a','namespace/object-b'],f=await setupLedger({semantic:'synthetic complete two-object population'},keys);
  try{const before=f.db.raw.prepare('SELECT * FROM pmb1_journal_control').get();const packet=await finish(f);
    assert.equal(f.db.requests,12);assert.equal(f.db.statements,21);assert.equal(f.db.primarySessions,12);
    assert.ok(f.db.requests<=f.allocation.maxTotalRequests);assert.ok(f.db.statements<=f.allocation.maxTotalStatements);
    const events=f.db.raw.prepare('SELECT * FROM pmb1_evidence_events ORDER BY revision').all();
    assert.equal(events.length,6);assert.equal(new Set(events.filter(e=>e.kind==='native-consumed').map(e=>e.attempt_id)).size,2);
    assert.deepEqual(f.db.raw.prepare('SELECT * FROM pmb1_journal_control').get(),before);
    assert.ok(Object.isFrozen(packet));assert.ok(Object.isFrozen(packet.header));
    await assert.rejects(f.ledger().reserve(f.reference));
    await assert.rejects(f.ledger().consume(f.reference,keys[0]));
  }finally{f.close();}
});
test('operator publisher without qualified authority is disabled; pure preparation binds exact retained artifacts',async()=>{
  const f=await setupLedger();try{
    const before=f.db.requests;
    await assert.rejects(publishReviewedEvidence(f.db,f.prepared),/execution_disabled/);assert.equal(f.db.requests,before);
    assert.equal(f.prepared.statements.length,3);assert.equal(publicationReadback(f.prepared).length,4);
    for(const name of ['retainedRootRecord','retainedReviewRecord','retainedEnvelopeDigest']){
      await assert.rejects(preparePublication({...f.handoff,[name]:'0'.repeat(64)},f.binding,f.provenance,f.allocation,f.clock.now));
    }
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) AS n FROM pmb1_evidence_envelopes').get().n,1);
  }finally{f.close();}
});
test('publication header/chunks/publish is one transaction: incomplete, wrong ordinal and excessive chunks roll back',async()=>{
  for(const change of ['missing','ordinal','oversize']){
    const f=await setupLedger({body:'x'.repeat(300000)},['namespace/object-a'],{publish:false});try{
      const statements=structuredClone(f.prepared.statements);
      if(change==='missing')statements.splice(1,1);
      if(change==='ordinal')statements[1].args[1]=15;
      if(change==='oversize')statements[1].args[2]='x'.repeat(262145);
      await assert.rejects(f.db.batch(statements.map(s=>f.db.prepare(s.sql).bind(...s.args))));
      assert.equal(f.db.raw.prepare('SELECT COUNT(*) AS n FROM pmb1_evidence_envelopes').get().n,0);
      await assert.rejects(f.ledger().reserve(f.reference));
    }finally{f.close();}
  }
});
test('ordinary UPDATE DELETE REPLACE UPSERT and parent deletion cannot change protected history',async()=>{
  const f=await setupLedger();try{
    for(const table of ['pmb1_evidence_envelopes','pmb1_evidence_chunks','pmb1_evidence_events']){
      await assert.rejects(f.db.batch([f.db.prepare(`DELETE FROM ${table}`)]));
      const column=table.endsWith('envelopes')?'payload_bytes':table.endsWith('chunks')?'ordinal':'observed_ms';
      assert.throws(()=>f.db.raw.exec(`UPDATE ${table} SET ${column}=${column}`));
      assert.throws(()=>f.db.raw.exec(`INSERT OR REPLACE INTO ${table} SELECT * FROM ${table}`));
    }
    assert.throws(()=>f.db.raw.prepare(`INSERT INTO pmb1_evidence_chunks VALUES(?,?,?)
      ON CONFLICT(envelope_id,ordinal) DO UPDATE SET payload=excluded.payload`).run(f.reference.envelopeId,0,'x'));
    assert.equal((await f.ledger().reserve(f.reference)).revision,2);
  }finally{f.close();}
});
test('guards reject out-of-order, duplicate, unreserved, substituted capture and invented terminal events',async()=>{
  const f=await setupLedger();try{
    const insert=(kind,key='',attempt=f.reference.attemptId,outcome='')=>()=>f.db.raw.prepare(`INSERT INTO pmb1_evidence_events
      VALUES(?,2,?,?,?,?,?)`).run(f.reference.envelopeId,kind,key,attempt,outcome,f.clock.now);
    assert.throws(insert('native-consumed',f.header.captureKeys[0],f.header.captureAttempts[0].attemptId));
    assert.throws(insert('terminal',f.header.captureKeys[0],f.header.captureAttempts[0].attemptId,'complete'));
    assert.throws(insert('publish'));
    const source=f.ledger();await source.reserve(f.reference);
    await assert.rejects(f.ledger().consume(f.reference,'namespace/not-allocated'));
    await assert.rejects(source.complete(f.reference,f.header.captureKeys[0],'complete'));
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
  }finally{f.close();}
});
test('exact independent source-context/module/config/resources/version/holder/writer/provenance substitutions refuse',async()=>{
  const f=await setupLedger();try{
    for(const field of ['sourceContext','moduleDigest','configurationDigest','resourceInventoryDigest','immutableVersion','nativeSourceDigest','ownerSourceDigest','controlReference']){
      const binding={...executionAnchors(f.binding),[field]:field==='immutableVersion'?'wrong-version':field==='controlReference'?'wrong-control':'0'.repeat(64)};
      const provenance={...f.provenance,binding};
      await assert.rejects(new RuntimeEvidenceLedger(f.db,binding,provenance,f.allocation,()=>f.clock.now).reserve(f.reference));
    }
    for(const field of ['publisherSourceDigest','holderInventoryDigest','writerInventoryDigest','historyContinuityRecord','executionAttributionRecord','operatorAttemptLedgerRecord']){
      await assert.rejects(new RuntimeEvidenceLedger(f.db,f.binding,{...f.provenance,[field]:'0'.repeat(64)},f.allocation,()=>f.clock.now).reserve(f.reference));
    }
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,0);
  }finally{f.close();}
});
test('full chunks are read only after byte/row/copy reservation, including escaped source bytes and aggregate population charge',async()=>{
  const f=await setupLedger({body:'"\\\u0000\u00e9'.repeat(30000)},['namespace/a','namespace/b']);try{
    const source=f.ledger();await source.reserve(f.reference);assert.ok(f.header.chunkCount>1);
    assert.ok(f.allocation.maxAcquiredBytes>=f.header.payloadBytes*6);
    for(const field of ['maxPayloadBytes','maxAcquiredBytes','maxDecodedBytes','maxAggregateBytes','maxTotalRequests','maxTotalStatements']){
      const allocation={...f.allocation,[field]:1};
      const reader=new RuntimeEvidenceLedger(f.db,f.binding,f.provenance,allocation,()=>f.clock.now);
      const calls=f.db.requests;await assert.rejects(reader.reserve(f.reference));
      assert.ok(f.db.requests-calls<=1,'must refuse before chunk acquisition');
    }
  }finally{f.close();}
});
test('retirement between preflight/claim and claim/final-read refuses and never reclaims',async()=>{
  for(const target of [1,2]){
    const f=await setupLedger();try{
      f.db.afterBatch=(n)=>{if(n===target)f.retire();};
      await assert.rejects(f.ledger().reserve(f.reference));f.db.afterBatch=null;
      await assert.rejects(f.ledger().reserve(f.reference));
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='retire'").get().n,1);
    }finally{f.close();}
  }
});
test('expiration and backward/future clocks refuse before and after awaits, without timestamp renewal',async()=>{
  for(const n of [0,1,2,3]){
    const f=await setupLedger();try{
      if(n===0)f.clock.now=f.header.throughMs;
      else f.db.afterBatch=(index)=>{if(index===n)f.clock.now=f.header.throughMs;};
      await assert.rejects(f.ledger().reserve(f.reference));
    }finally{f.close();}
  }
  const f=await setupLedger();try{
    f.db.afterBatch=()=>{f.clock.now--;};await assert.rejects(f.ledger().reserve(f.reference));
    await assert.rejects(f.ledger().read({...f.reference,databaseId:'not-a-uuid'}));
  }finally{f.close();}
});
test('lost mutation ACK is unknown, consumes durable authority and cannot replay after restart',async()=>{
  const folder=mkdtempSync(join(tmpdir(),'pmb1-evidence-'));
  try{
    const path=join(folder,'synthetic.sqlite'),f=await setupLedger({},['namespace/object-a'],{db:new SyntheticD1(path)});
    const source=f.ledger();f.db.afterBatch=(n)=>{if(n===2)throw Error('synthetic_lost_commit_ack');};
    await assert.rejects(source.reserve(f.reference),/unknown/);
    f.db.afterBatch=null;await assert.rejects(source.reserve(f.reference),/no_replay|unknown|role_already_spent/);
    const state={binding:f.binding,provenance:f.provenance,allocation:f.allocation,reference:f.reference,now:f.clock.now};f.close();
    const db=new SyntheticD1(path,false);try{
      const restarted=new RuntimeEvidenceLedger(db,state.binding,state.provenance,state.allocation,()=>state.now);
      const requests=db.requests;await assert.rejects(restarted.read(state.reference),/standalone_read_not_allocated/);
      assert.equal(db.requests,requests);
      // Synthetic verifier's separately allocated direct status observation;
      // this is neither a production payload reader nor positive authority.
      assert.equal(db.raw.prepare('SELECT MAX(revision) AS revision FROM pmb1_evidence_events WHERE envelope_id=?')
        .get(state.reference.envelopeId).revision,2);
      await assert.rejects(restarted.reserve(state.reference));
      assert.equal(db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,1);
    }finally{db.close();}
  }finally{rmSync(folder,{recursive:true,force:true});}
});
test('lost consume or terminal ACK remains unknown; no retry/revival and final positive refuses unknown completion',async()=>{
  for(const phase of ['consume','terminal']){
    const f=await setupLedger();try{
      const source=f.ledger(),packet=await source.reserve(f.reference),owner=f.ledger(),key=f.header.captureKeys[0];
      if(phase==='consume'){
        f.db.afterBatch=(n)=>{if(n===5)throw Error('synthetic_consumption_ack_lost');};
        await assert.rejects(owner.consume(f.reference,key));f.db.afterBatch=null;
        await assert.rejects(f.ledger().consume(f.reference,key));await source.complete(f.reference,key,'unknown');
        await assert.rejects(source.revalidate(packet));
      }else{
        await owner.consume(f.reference,key);f.db.afterBatch=(n)=>{if(n===7)throw Error('synthetic_terminal_ack_lost');};
        await assert.rejects(source.complete(f.reference,key,'complete'));f.db.afterBatch=null;
        await assert.rejects(source.complete(f.reference,key,'complete'));
        await assert.rejects(source.revalidate(packet));
      }
    }finally{f.close();}
  }
});
test('two competing reservations race atomically; exactly one wins and neither can spend twice',async()=>{
  const f=await setupLedger();try{
    const a=f.ledger(),b=f.ledger();const results=await Promise.allSettled([a.reserve(f.reference),b.reserve(f.reference)]);
    assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,1);
  }finally{f.close();}
});
test('corrupt/missing history or malformed ACK refuses; trusted-code guard removal is explicitly not privilege isolation',async()=>{
  for(const mode of ['history','chunk','malformed']){
    const f=await setupLedger();try{
      if(mode==='history'){f.db.raw.exec('DROP TRIGGER pmb1_evidence_event_delete');f.db.raw.exec('DELETE FROM pmb1_evidence_events');}
      if(mode==='chunk'){f.db.raw.exec('DROP TRIGGER pmb1_evidence_chunk_update');
        f.db.raw.prepare('UPDATE pmb1_evidence_chunks SET payload=?').run('x'.repeat(f.payloadText.length));}
      if(mode==='malformed')f.db.afterBatch=(_n,_s,results)=>{results[0].success=false;};
      await assert.rejects(f.ledger().reserve(f.reference));
    }finally{f.close();}
  }
});
test('same resource, same stable code/anchors, cold restart accepts only fresh separately reviewed later interval and attempts',async()=>{
  const f=await setupLedger({interval:1},['namespace/a','namespace/b']);try{
    await finish(f);f.retire();const journalBefore=f.db.raw.prepare('SELECT * FROM pmb1_journal_control').get();
    const next=await setupLedger({interval:2},['namespace/a','namespace/b'],{db:f.db,now:f.header.throughMs+1000});
    const second=await finish(next);assert.equal(second.payload.interval,2);
    assert.deepEqual(f.db.raw.prepare('SELECT * FROM pmb1_journal_control').get(),journalBefore);
    assert.deepEqual(next.binding,f.binding);assert.deepEqual(next.provenance,f.provenance);
    await assert.rejects(next.ledger().reserve(f.reference));
    const differentGeneration=await setupLedger({interval:3},['namespace/a'],{db:f.db,now:next.header.throughMs+1000,
      binding:{generation:'2'}});
    await assert.rejects(differentGeneration.ledger().reserve(differentGeneration.reference));
  }finally{f.close();}
});
test('publication cannot reuse a spent raw attempt, reuse envelope identity, or overlap conflicting custody interval',async()=>{
  const f=await setupLedger();try{
    await assert.rejects(f.db.batch(f.prepared.statements.map(s=>f.db.prepare(s.sql).bind(...s.args))));
    await assert.rejects(setupLedger({second:true},f.header.captureKeys,{db:f.db}));
    f.retire();await assert.rejects(setupLedger({replay:true},f.header.captureKeys,{db:f.db,now:f.header.throughMs+1,
      header:{captureAttempts:f.header.captureAttempts}}));
  }finally{f.close();}
});

function nativeParameters(f){
  const selector={databaseId:f.binding.databaseId,sourceContext:f.binding.sourceContext,immutableVersion:f.binding.immutableVersion};
  const qualification={databaseId:f.binding.databaseId,schema:f.binding.schema,publisherSourceDigest:f.provenance.publisherSourceDigest,
    provenancePathDigest:f.provenance.provenancePathDigest,holderPolicyDigest:f.provenance.holderPolicyDigest,
    nativeGetterQualificationRecord:f.provenance.nativeGetterQualificationRecord};
  const ceilings={...f.allocation,maxPayloadBytes:4194304,maxAcquiredBytes:33554432,maxDecodedBytes:16777216,
    maxNativeBytes:16777216,maxAggregateBytes:67108864,maxTotalRequests:68,maxTotalStatements:136};
  return {selector,qualification,ceilings};
}
test('native execution selectors need no own final digest, fixed envelope or interval; publisher expected mapping remains complete',async()=>{
  const f=await setupLedger({first:'synthetic protected management mapping'},['namespace/a','namespace/b']);try{
    const p=nativeParameters(f);
    const make=()=>RuntimeEvidenceLedger.fromNativeExecution(f.db,p.selector,p.qualification,p.ceilings,()=>f.clock.now);
    const source=make(),packet=await source.reserveSelected(f.reference.operation);
    assert.equal(packet.header.binding.moduleDigest,f.binding.moduleDigest);
    for(const key of f.header.captureKeys){await make().consume(f.reference,key);await source.complete(f.reference,key,'complete');}
    await source.revalidate(packet);assert.equal(f.db.requests,12);f.retire();
    const next=await setupLedger({second:'new actual reviewed interval with different payload size'},f.header.captureKeys,
      {db:f.db,now:f.header.throughMs+1000,review:{rootRecord:'d'.repeat(64),reviewRecord:'e'.repeat(64)}});
    f.clock.now=next.clock.now;
    const cold=make(),fresh=await cold.reserveSelected(f.reference.operation);
    assert.notEqual(fresh.reference.envelopeId,packet.reference.envelopeId);
    assert.notEqual(fresh.header.payloadBytes,packet.header.payloadBytes);
    assert.notEqual(fresh.header.provenance.reviewRecord,packet.header.provenance.reviewRecord);
    for(const key of next.header.captureKeys){await make().consume(next.reference,key);await cold.complete(next.reference,key,'complete');}
    await cold.revalidate(fresh);
    assert.deepEqual(nativeParameters(next),p,'unchanged selectors, qualification and source ceilings across intervals');
  }finally{f.close();}
});
test('native mode refuses rows supplying substituted version/context/DB or their own publisher/getter/containment authority',async()=>{
  const f=await setupLedger();try{
    const p=nativeParameters(f);
    for(const [field,value] of [['immutableVersion','unobserved-version'],['sourceContext','0'.repeat(64)],
      ['databaseId','bbbbbbbb-0000-4000-8000-000000000002']]){
      const selector={...p.selector,[field]:value},qualification={...p.qualification,databaseId:selector.databaseId};
      await assert.rejects(RuntimeEvidenceLedger.fromNativeExecution(f.db,selector,qualification,p.ceilings,()=>f.clock.now)
        .reserveSelected(f.reference.operation));
    }
    for(const field of ['publisherSourceDigest','provenancePathDigest','holderPolicyDigest','nativeGetterQualificationRecord']){
      await assert.rejects(RuntimeEvidenceLedger.fromNativeExecution(f.db,p.selector,{...p.qualification,[field]:'0'.repeat(64)},p.ceilings,()=>f.clock.now)
        .reserveSelected(f.reference.operation));
    }
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,0);
  }finally{f.close();}
});

test('every finite allocation field is an exact own safe positive data property before construction/publication',async()=>{
  const f=await setupLedger();try{
    const invalid=[{},Object.create(f.allocation),Object.assign(Object.create(null),f.allocation),
      {...f.allocation,unexpected:1},{...f.allocation,[Symbol('hidden-allocation')]:1}];
    for(const field of Object.keys(f.allocation)){
      const missing={...f.allocation};delete missing[field];invalid.push(missing);
      for(const value of [undefined,null,NaN,Infinity,-Infinity,0,-1,1.5,Number.MAX_SAFE_INTEGER+1,'8'])invalid.push({...f.allocation,[field]:value});
      const inherited=Object.create({[field]:f.allocation[field]});Object.assign(inherited,missing);invalid.push(inherited);
      const accessor={...f.allocation};Object.defineProperty(accessor,field,{enumerable:true,get(){throw Error('must not evaluate accessor');}});invalid.push(accessor);
      const hidden={...f.allocation};Object.defineProperty(hidden,field,{enumerable:false,value:f.allocation[field]});invalid.push(hidden);
    }
    const before=f.db.requests;
    for(const allocation of invalid){
      assert.throws(()=>validateAllocation(allocation));
      assert.throws(()=>new RuntimeEvidenceLedger(f.db,f.binding,f.provenance,allocation,()=>f.clock.now));
      await assert.rejects(preparePublication(f.handoff,f.binding,f.provenance,allocation,f.clock.now));
      await assert.rejects(preparePublication({...f.handoff,header:{...f.header,allocation}},f.binding,f.provenance,f.allocation,f.clock.now));
    }
    assert.equal(f.db.requests,before);
  }finally{f.close();}
});
test('native protected missing allocation fields refuse at bounded header preflight before chunks or claim',async()=>{
  for(const field of [null,...Object.keys((await setupForFields()).allocation)]){
    const f=await setupLedger({},['namespace/object-a'],{publish:false});try{
      const allocation=field===null?{}:{...f.allocation};if(field!==null)delete allocation[field];
      const corrupt=structuredClone(f.prepared.statements);corrupt[0].args[2]=encoded({...f.header,allocation});
      // Synthetic malformed protected row: direct fixed SQL bypasses the now
      // rejecting operator preparer. No actual trusted publication is asserted.
      await f.db.batch(corrupt.map(s=>f.db.prepare(s.sql).bind(...s.args)));f.db.requests=0;f.db.statements=0;
      const p=nativeParameters(f),reader=RuntimeEvidenceLedger.fromNativeExecution(f.db,p.selector,p.qualification,p.ceilings,()=>f.clock.now);
      await assert.rejects(reader.reserveSelected(f.reference.operation));
      assert.equal(f.db.requests,1);assert.equal(f.db.statements,1);
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,0);
    }finally{f.close();}
  }
});
async function setupForFields(){const f=await setupLedger();try{return {allocation:{...f.allocation}};}finally{f.close();}}
test('standalone payload reads always refuse before I/O, including before/after source reservation and cold restart',async()=>{
  const f=await setupLedger();try{
    const source=f.ledger();await assert.rejects(source.read(f.reference),/standalone_read_not_allocated/);assert.equal(f.db.requests,0);
    const packet=await source.reserve(f.reference),key=f.header.captureKeys[0];
    await assert.rejects(source.read(f.reference));await assert.rejects(f.ledger().read(f.reference));assert.equal(f.db.requests,3);
    await f.ledger().consume(f.reference,key);await source.complete(f.reference,key,'complete');await source.revalidate(packet);
    assert.equal(f.db.requests,8);assert.equal(f.db.statements,14);
    const before=f.db.requests;await assert.rejects(source.revalidate(packet));await assert.rejects(source.complete(f.reference,key,'complete'));
    await assert.rejects(f.ledger().read(f.reference));assert.equal(f.db.requests,before);
  }finally{f.close();}
});
test('one lifetime role cannot borrow source/owner/envelope/key materialization slots or replay final validation',async()=>{
  const f=await setupLedger({},['namespace/a','namespace/b']);try{
    const source=f.ledger(),packet=await source.reserve(f.reference),owner=f.ledger();
    let before=f.db.requests;
    await assert.rejects(source.consume(f.reference,'namespace/a'));await assert.rejects(source.reserveSelected('different-operation'));
    assert.equal(f.db.requests,before);
    await owner.consume(f.reference,'namespace/a');before=f.db.requests;
    await assert.rejects(owner.consume(f.reference,'namespace/b'));await assert.rejects(owner.reserve(f.reference));
    await assert.rejects(owner.complete(f.reference,'namespace/a','complete'));assert.equal(f.db.requests,before);
    await source.complete(f.reference,'namespace/a','complete');await f.ledger().consume(f.reference,'namespace/b');
    await source.complete(f.reference,'namespace/b','complete');await source.revalidate(packet);
    assert.equal(f.db.requests,12);assert.equal(f.db.statements,21);before=f.db.requests;
    await assert.rejects(source.revalidate(packet));assert.equal(f.db.requests,before);
  }finally{f.close();}
});
test('cross-instance/concurrent duplicate consumes grant exactly one positive owner copy per protected raw attempt',async()=>{
  const f=await setupLedger();try{
    const source=f.ledger(),packet=await source.reserve(f.reference),key=f.header.captureKeys[0];
    const outcomes=await Promise.allSettled([f.ledger().consume(f.reference,key),f.ledger().consume(f.reference,key)]);
    assert.equal(outcomes.filter(r=>r.status==='fulfilled').length,1);
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,1);
    await source.complete(f.reference,key,'unknown');await assert.rejects(source.revalidate(packet));
    // Duplicate denied invocations are explicit NO-GO and cannot obtain a third
    // successful payload/native acquisition or contribute positive authority.
    assert.equal(outcomes.filter(r=>r.status==='fulfilled').length,1);
  }finally{f.close();}
});
