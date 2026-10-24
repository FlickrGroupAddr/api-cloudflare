// MIT License; copyright 2026 Terry Ott.
// Invented private operator facts only; zero actual provider/credential access.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Miniflare,Log,LogLevel} from 'miniflare';
import {setupLedger} from './fixture.mjs';
import {publishReviewedEvidence} from './publisher.ts';

function authority(f,overrides={}){
  return {schema:'pmb1-qualified-native-d1-operator-publication-v1',databaseId:f.reference.databaseId,
    envelopeId:f.reference.envelopeId,operationId:crypto.randomUUID(),qualificationRecord:'a'.repeat(64),
    operatorEnvironmentRecord:'b'.repeat(64),bindingHolderRecord:'c'.repeat(64),credentialCustodyRecord:'d'.repeat(64),
    publisherSourceDigest:f.provenance.publisherSourceDigest,rootRecord:f.header.provenance.rootRecord,
    reviewRecord:f.header.provenance.reviewRecord,retainedEnvelopeDigest:f.handoff.retainedEnvelopeDigest,
    attemptLedgerRecord:f.provenance.operatorAttemptLedgerRecord,attemptState:'allocated-unused',
    fromMs:f.header.fromMs,throughMs:f.header.throughMs,
    allocation:{maxRequests:4,maxStatements:23,maxAcquiredBytes:f.header.payloadBytes*6+65536,maxAggregateBytes:67108864},...overrides};
}
const execute=(f,grant=authority(f),prepared=f.prepared)=>publishReviewedEvidence(f.db,prepared,grant,()=>f.clock.now);

test('operator default absent qualification is inert; wrong authority/handoff/custody cannot issue a request',async()=>{
  const f=await setupLedger({},['namespace/a'],{publish:false});try{
    await assert.rejects(publishReviewedEvidence(f.db,f.prepared),/execution_disabled/);
    for(const change of [{databaseId:crypto.randomUUID()},{envelopeId:crypto.randomUUID()},{operationId:'bad'},
      {qualificationRecord:''},{operatorEnvironmentRecord:''},{bindingHolderRecord:''},{credentialCustodyRecord:''},
      {publisherSourceDigest:'0'.repeat(64)},{rootRecord:'0'.repeat(64)},{reviewRecord:'0'.repeat(64)},
      {attemptLedgerRecord:'0'.repeat(64)},{attemptState:'unknown'},{attemptState:'spent'},
      {fromMs:f.clock.now+1},{throughMs:f.clock.now},{allocation:{}}]){
      await assert.rejects(execute(f,authority(f,change)));
    }
    await assert.rejects(execute(f,authority(f,{retainedEnvelopeDigest:'0'.repeat(64)})));
    assert.equal(f.db.requests,0);
  }finally{f.close();}
});
test('fixed operator executor rebuilds SQL, publishes once atomically and independently primary reads complete bytes',async()=>{
  const f=await setupLedger({body:'exact full synthetic protected source bytes'},['namespace/a','namespace/b'],{publish:false});try{
    const grant=authority(f),hostile={...f.prepared,statements:[{sql:'DROP TABLE pmb1_evidence_envelopes',args:[]}]};
    const result=await execute(f,grant,hostile);
    assert.deepEqual(result,{outcome:'published',publicationAcknowledged:true,readback:'exact',envelopeId:f.reference.envelopeId});
    assert.equal(f.db.requests,4);assert.equal(f.db.statements,8);assert.equal(f.db.primarySessions,4);
    assert.equal(f.db.raw.prepare('SELECT COUNT(*) AS n FROM pmb1_evidence_envelopes').get().n,1);
    const before=f.db.requests;await assert.rejects(execute(f,grant),/no_replay/);
    await assert.rejects(execute(f,authority(f)),/no_replay/);assert.equal(f.db.requests,before);
  }finally{f.close();}
});
test('operator finite byte/copy and exact call allocation refuse before publication; source consumption allocation unchanged',async()=>{
  const f=await setupLedger({bytes:'"\\\u00e9'.repeat(10000)},['namespace/a'],{publish:false});try{
    for(const change of [{maxRequests:3},{maxStatements:7},{maxAcquiredBytes:1},{maxAggregateBytes:1}]){
      const grant=authority(f);Object.assign(grant.allocation,change);await assert.rejects(execute(f,grant));
    }
    for(const field of ['maxRequests','maxStatements','maxAcquiredBytes','maxAggregateBytes']){
      const grant=authority(f);delete grant.allocation[field];await assert.rejects(execute(f,grant));
    }
    assert.equal(f.db.requests,0);assert.equal(f.allocation.maxRequests,8);assert.equal(f.allocation.maxStatements,32);
  }finally{f.close();}
});
test('mid-batch native SQL failure rolls back header and all chunks; outcome unknown never retries',async()=>{
  const f=await setupLedger({bytes:'x'.repeat(300000)},['namespace/a'],{publish:false});try{
    f.db.raw.exec("CREATE TRIGGER synthetic_fail_second_chunk BEFORE INSERT ON pmb1_evidence_chunks WHEN NEW.ordinal=1 BEGIN SELECT RAISE(ABORT,'synthetic publication failure'); END");
    const grant=authority(f),result=await execute(f,grant);
    assert.equal(result.outcome,'unknown');assert.equal(result.publicationAcknowledged,false);assert.equal(result.readback,'unknown');
    for(const table of ['pmb1_evidence_envelopes','pmb1_evidence_chunks','pmb1_evidence_events'])
      assert.equal(f.db.raw.prepare('SELECT COUNT(*) AS n FROM '+table).get().n,0);
    const before=f.db.requests;await assert.rejects(execute(f,grant),/no_replay/);assert.equal(f.db.requests,before);
  }finally{f.close();}
});
test('lost/malformed publication ACK remains UNKNOWN even when allocated primary readback sees exact committed rows',async()=>{
  for(const mode of ['lost','malformed']){
    const f=await setupLedger({},['namespace/a'],{publish:false});try{
      f.db.afterBatch=(index,_statements,results)=>{if(index===1){if(mode==='lost')throw Error('synthetic lost publication ACK');results[0].success=false;}};
      const grant=authority(f),result=await execute(f,grant);
      assert.equal(result.outcome,'unknown');assert.equal(result.publicationAcknowledged,false);assert.equal(result.readback,'exact');
      assert.equal(f.db.requests,4);assert.equal(f.db.statements,8);
      const before=f.db.requests;await assert.rejects(execute(f,grant),/no_replay/);assert.equal(f.db.requests,before);
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='publish'").get().n,1);
    }finally{f.close();}
  }
});
test('retirement/clock expiry/readback corruption cannot be reported as a positive publication',async()=>{
  for(const mode of ['retire','expiry','corrupt']){
    const f=await setupLedger({},['namespace/a'],{publish:false});try{
      f.db.afterBatch=(index,_statements,results)=>{if(index===1&&mode==='retire')f.retire();
        if(index===2&&mode==='expiry')f.clock.now=f.header.throughMs;
        if(index===3&&mode==='corrupt')results[1].results[0].payload='substituted';};
      const result=await execute(f);assert.equal(result.outcome,'unknown');assert.equal(result.readback,'unknown');
    }finally{f.close();}
  }
});
test('concrete local Miniflare D1 SDK path publishes full chunks and checks independent primary readback with external access denied',async()=>{
  const f=await setupLedger({body:'x'.repeat(300000)},['namespace/a','namespace/b'],{publish:false});
  let outbound=0,requests=0,statements=0,sessions=0;
  const mf=new Miniflare({modules:true,script:'export default {fetch(){throw Error("operator_has_no_http_route")}}',
    compatibilityDate:'2026-08-06',compatibilityFlags:['nodejs_compat'],log:new Log(LogLevel.ERROR),
    cf:false,port:0,inspectorPort:0,host:'127.0.0.1',d1Databases:{OPERATOR_D1:f.reference.databaseId},
    outboundService:()=>{outbound++;throw Error('outbound_forbidden');}});
  try{
    const native=await mf.getD1Database('OPERATOR_D1');
    const schema=f.db.raw.prepare('SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY rowid').all();
    for(const row of schema)await native.prepare(row.sql).run();
    await native.prepare(readFileSync(new URL('../pmb1-native-journal/provision.sql',import.meta.url),'utf8'))
      .bind(f.binding.databaseId,f.binding.sourceContext,f.binding.lifecycle,f.binding.generation).run();
    await native.prepare("UPDATE pmb1_journal_control SET state='stopped',stop_evidence=?,revision=revision+1 WHERE id=1").bind('9'.repeat(64)).run();
    const observed={withSession(mode){assert.equal(mode,'first-primary');sessions++;const session=native.withSession(mode);
      return {prepare:sql=>session.prepare(sql),batch:async plan=>{requests++;statements+=plan.length;return session.batch(plan);}};}};
    const result=await publishReviewedEvidence(observed,f.prepared,authority(f),()=>f.clock.now);
    assert.equal(result.outcome,'published');assert.equal(result.readback,'exact');assert.equal(requests,4);
    assert.equal(statements,9);assert.equal(sessions,4);assert.equal(outbound,0);
    assert.equal((await native.prepare('SELECT COUNT(*) AS n FROM pmb1_evidence_chunks').first()).n,2);
    // A cold new wrapper cannot replay a spent/unknown externally retained grant.
    const before=requests;await assert.rejects(publishReviewedEvidence(observed,f.prepared,authority(f,{attemptState:'unknown'}),()=>f.clock.now));
    assert.equal(requests,before);
    // A later independently allocated synthetic publication proves the actual
    // local D1 SDK's mid-batch rollback as well as its successful batch path.
    const next=await setupLedger({body:'y'.repeat(300000)},['namespace/a','namespace/b'],
      {db:f.db,publish:false,now:f.header.throughMs+1000});
    await native.prepare("CREATE TRIGGER synthetic_fail_later_chunk BEFORE INSERT ON pmb1_evidence_chunks WHEN NEW.ordinal=1 BEGIN SELECT RAISE(ABORT,'synthetic local D1 atomic failure'); END").run();
    const failed=await publishReviewedEvidence(observed,next.prepared,authority(next),()=>next.clock.now);
    assert.equal(failed.outcome,'unknown');assert.equal(failed.publicationAcknowledged,false);
    assert.equal((await native.prepare('SELECT COUNT(*) AS n FROM pmb1_evidence_envelopes WHERE envelope_id=?')
      .bind(next.reference.envelopeId).first()).n,0);
    assert.equal((await native.prepare('SELECT COUNT(*) AS n FROM pmb1_evidence_chunks WHERE envelope_id=?')
      .bind(next.reference.envelopeId).first()).n,0);
  }finally{await mf.dispose();f.close();assert.equal(outbound,0);}
});
