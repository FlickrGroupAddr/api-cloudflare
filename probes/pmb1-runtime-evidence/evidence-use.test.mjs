// MIT License; copyright 2026 Terry Ott.
// Separate synthetic evidence-only allocations; no native acquisition/budget.
import test from 'node:test';
import assert from 'node:assert/strict';
import {setupLedger} from './fixture.mjs';
const evidence=(operation='main-assess',options={})=>setupLedger({reviewed:'synthetic coverage only'},[],
  {...options,reference:{operation,...options.reference},header:{mode:'evidence-use',...options.header}});

test('each fixed noncapture operation owns a distinct evidence-use attempt and finishes after await with5requests8statements',async()=>{
  for(const operation of ['main-assess','partition-reconcile']){
    const f=await evidence(operation);try{
      const control=f.db.raw.prepare('SELECT * FROM pmb1_journal_control').get(),ledger=f.ledger();
      const packet=await ledger.reserveSelected(operation);assert.equal(f.db.requests,3);
      await Promise.resolve('synthetic protected assessment/reconciliation');
      await ledger.finishEvidenceUse(packet);
      assert.equal(f.db.requests,5);assert.equal(f.db.statements,8);assert.equal(f.db.primarySessions,5);
      assert.equal(f.allocation.maxTotalRequests,5);assert.equal(f.allocation.maxTotalStatements,8);
      assert.equal(f.allocation.maxRequests,8);assert.equal(f.allocation.maxStatements,32);
      const events=f.db.raw.prepare('SELECT kind,capture_key,attempt_id FROM pmb1_evidence_events ORDER BY revision').all();
      assert.deepEqual(events.map(e=>e.kind),['publish','use-reserved','terminal']);
      assert.ok(events.every(e=>e.capture_key===''&&e.attempt_id===f.reference.attemptId));
      assert.deepEqual(f.header.captureKeys,[]);assert.deepEqual(f.header.captureAttempts,[]);
      assert.deepEqual(f.db.raw.prepare('SELECT * FROM pmb1_journal_control').get(),control);
      const calls=f.db.requests;await assert.rejects(ledger.finishEvidenceUse(packet));
      await assert.rejects(ledger.revalidate(packet));assert.equal(f.db.requests,calls);
    }finally{f.close();}
  }
});
test('mode explicitly separates raw captures, exact noncapture operations and zero-capture authority',async()=>{
  for(const options of [{header:{mode:'raw-capture'}},{header:{mode:'unknown'}},
    {reference:{operation:'native-preservation'}},{reference:{operation:'main-reconcile'}},
    {header:{captureKeys:['invented/object'],captureAttempts:[{captureKey:'invented/object',attemptId:crypto.randomUUID()}]}}]){
    await assert.rejects(evidence('main-assess',options));
  }
  const f=await evidence();try{
    const source=f.ledger(),packet=await source.reserve(f.reference);
    await assert.rejects(f.ledger().consume(f.reference,'invented/object'));
    const calls=f.db.requests;await assert.rejects(source.complete(f.reference,'invented/object','complete'));
    await assert.rejects(source.revalidate(packet));assert.equal(f.db.requests,calls);
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
    const raw=await setupLedger();try{
      const rawSource=raw.ledger(),rawPacket=await rawSource.reserve(raw.reference),before=raw.db.requests;
      await assert.rejects(rawSource.finishEvidenceUse(rawPacket));assert.equal(raw.db.requests,before);
    }finally{raw.close();}
  }finally{f.close();}
});
test('generic terminal cannot precede reservation, fake native consumption or use another operation attempt',async()=>{
  const f=await evidence();try{
    const sql='INSERT INTO pmb1_evidence_events VALUES(?,2,?,?,?,?,?)';
    assert.throws(()=>f.db.raw.prepare(sql).run(f.reference.envelopeId,'terminal','',f.reference.attemptId,'complete',f.clock.now));
    const ledger=f.ledger(),packet=await ledger.reserve(f.reference);
    assert.throws(()=>f.db.raw.prepare('INSERT INTO pmb1_evidence_events VALUES(?,3,?,?,?,?,?)')
      .run(f.reference.envelopeId,'native-consumed','invented/object',crypto.randomUUID(),'',f.clock.now));
    assert.throws(()=>f.db.raw.prepare('INSERT INTO pmb1_evidence_events VALUES(?,3,?,?,?,?,?)')
      .run(f.reference.envelopeId,'terminal','',crypto.randomUUID(),'complete',f.clock.now));
    const before=f.db.requests;await assert.rejects(f.ledger().finishEvidenceUse(packet));assert.equal(f.db.requests,before);
    await ledger.finishEvidenceUse(packet);assert.equal(f.db.requests,5);
  }finally{f.close();}
});
test('retirement racing the protected await or final evidence-only read refuses positive completion within its own finite calls',async()=>{
  for(const phase of ['protected-await','after-terminal']){
    const f=await evidence();try{
      const ledger=f.ledger(),packet=await ledger.reserve(f.reference);
      await Promise.resolve();
      if(phase==='protected-await')f.retire();else f.db.afterBatch=n=>{if(n===4)f.retire();};
      await assert.rejects(ledger.finishEvidenceUse(packet));assert.ok(f.db.requests<=5);
      const before=f.db.requests;await assert.rejects(ledger.finishEvidenceUse(packet));assert.equal(f.db.requests,before);
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
    }finally{f.close();}
  }
});
test('expiry before/after final awaits and lost terminal ACK remain no-go with no completion replay or cold restart renewal',async()=>{
  for(const phase of ['before-finish','terminal-await','final-await','lost-terminal-ack']){
    const f=await evidence();try{
      const ledger=f.ledger(),packet=await ledger.reserve(f.reference);
      if(phase==='before-finish')f.clock.now=f.header.throughMs;
      else f.db.afterBatch=n=>{if(n===(phase==='final-await'?5:4)){
        if(phase==='lost-terminal-ack')throw Error('synthetic_lost_evidence_use_terminal_ack');
        f.clock.now=f.header.throughMs;}};
      await assert.rejects(ledger.finishEvidenceUse(packet));
      const before=f.db.requests;await assert.rejects(ledger.finishEvidenceUse(packet));
      await assert.rejects(f.ledger().read(f.reference));assert.equal(f.db.requests,before);
      f.db.afterBatch=null;f.clock.now=100000;await assert.rejects(f.ledger().reserve(f.reference));
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,1);
    }finally{f.close();}
  }
});
test('evidence-only attempt identity stays spent across retired later intervals and cannot borrow a raw attempt',async()=>{
  const f=await evidence();try{
    const ledger=f.ledger(),packet=await ledger.reserve(f.reference);await ledger.finishEvidenceUse(packet);f.retire();
    await assert.rejects(evidence('partition-reconcile',{db:f.db,now:f.header.throughMs+1000,reference:{attemptId:f.reference.attemptId}}));
    await assert.rejects(setupLedger({},['namespace/raw'],{db:f.db,now:f.header.throughMs+1000,
      header:{captureAttempts:[{captureKey:'namespace/raw',attemptId:f.reference.attemptId}]}}));
    const next=await evidence('main-assess',{db:f.db,now:f.header.throughMs+1000});
    const cold=next.ledger(),fresh=await cold.reserveSelected('main-assess');await cold.finishEvidenceUse(fresh);
    assert.notEqual(next.reference.attemptId,f.reference.attemptId);assert.equal(next.db.requests,5);
  }finally{f.close();}
});
test('malformed evidence terminal acknowledgement remains unknown despite a durable complete row',async()=>{
  for(const field of ['revision','observed_ms']){
    const f=await evidence();try{
      const ledger=f.ledger(),packet=await ledger.reserve(f.reference);
      f.db.afterBatch=(n,_s,results)=>{if(n===4)delete results[0].results[0][field];};
      await assert.rejects(ledger.finishEvidenceUse(packet));assert.equal(f.db.requests,4);
      const before=f.db.requests;await assert.rejects(ledger.finishEvidenceUse(packet));assert.equal(f.db.requests,before);
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='terminal'").get().n,1);
    }finally{f.close();}
  }
});
