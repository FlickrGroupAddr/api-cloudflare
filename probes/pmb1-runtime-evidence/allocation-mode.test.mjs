// MIT License; copyright 2026 Terry Ott.
// Mode-specific fixed cost and materialization allocation; synthetic states only.
import test from 'node:test';
import assert from 'node:assert/strict';
import {setupLedger} from './fixture.mjs';
import {RuntimeEvidenceLedger,encoded,sha2_256} from './ledger.ts';
import {preparePublication} from './publisher.ts';

const fixture=(mode,count,options={})=>setupLedger({bytes:'quote"slash\\\u00e9'.repeat(100)},
  Array.from({length:count},(_,i)=>'namespace/object-'+i),{...options,
    reference:{operation:mode==='raw-capture'?'native-preservation':'main-assess',...options.reference},
    header:{mode,...options.header}});

test('raw per-attempt15 statement reserve covers actual14 at1,2and16keys; larger totals never substitute for it',async()=>{
  for(const count of [1,2,16]){
    for(const maxStatements of [8,14])await assert.rejects(fixture('raw-capture',count,{allocation:{maxStatements}}));
    const f=await fixture('raw-capture',count,{allocation:{maxStatements:15}});try{
      const source=f.ledger(),packet=await source.reserve(f.reference);
      for(const key of f.header.captureKeys){await f.ledger().consume(f.reference,key);await source.complete(f.reference,key,'complete');}
      await source.revalidate(packet);
      assert.equal(f.db.requests,4+4*count);assert.equal(f.db.statements,7+7*count);
      assert.equal(f.allocation.maxStatements,15);assert.equal(f.allocation.maxRequests,8);
      assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,count);
    }finally{f.close();}
  }
});
test('evidence-only8 statement reserve remains sufficient; its lowered minimum cannot authorize raw work',async()=>{
  const f=await fixture('evidence-use',0,{allocation:{maxStatements:8}});try{
    const source=f.ledger(),packet=await source.reserve(f.reference);await source.finishEvidenceUse(packet);
    assert.equal(f.db.requests,5);assert.equal(f.db.statements,8);
    assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='native-consumed'").get().n,0);
  }finally{f.close();}
  await assert.rejects(fixture('evidence-use',0,{allocation:{maxStatements:7}}));
  await assert.rejects(fixture('raw-capture',1,{allocation:{maxStatements:8,maxTotalStatements:136}}));
});
test('per-mode request/statement/serialized/private-copy/native ceiling matrix rejects before publication or chunk acquisition',async()=>{
  for(const [mode,count] of [['raw-capture',1],['raw-capture',2],['raw-capture',16],['evidence-use',0]]){
    const reference=await fixture(mode,count,{publish:false});
    const fields={maxRequests:mode==='raw-capture'?7:4,maxStatements:mode==='raw-capture'?14:7,
      maxPayloadBytes:reference.header.payloadBytes-1,maxAcquiredBytes:reference.allocation.maxAcquiredBytes-1,
      maxDecodedBytes:reference.allocation.maxDecodedBytes-1,maxAggregateBytes:reference.allocation.maxAggregateBytes-1,
      maxNativeBytes:0,maxTotalRequests:reference.allocation.maxTotalRequests-1,maxTotalStatements:reference.allocation.maxTotalStatements-1};
    reference.close();
    for(const [field,value] of Object.entries(fields)){
      const f=await fixture(mode,count,{publish:false});try{
        const allocation={...f.allocation,[field]:value},header={...f.header,allocation};
        const handoff={...f.handoff,header,retainedEnvelopeDigest:await sha2_256(encoded(header)+'\n'+f.payloadText)};
        await assert.rejects(preparePublication(handoff,f.binding,f.provenance,allocation,f.clock.now),mode+'/'+count+'/'+field);
        assert.equal(f.db.requests,0);
        const malformed=structuredClone(f.prepared.statements);malformed[0].args[2]=encoded(header);
        // Invented malformed protected rows deliberately bypass the rejecting
        // preparer, proving the reader's independent BEFORE-chunks check.
        await f.db.batch(malformed.map(s=>f.db.prepare(s.sql).bind(...s.args)));f.db.requests=0;f.db.statements=0;
        await assert.rejects(async()=>new RuntimeEvidenceLedger(f.db,f.binding,f.provenance,allocation,()=>f.clock.now).reserve(f.reference));
        assert.ok(f.db.requests<=1,mode+'/'+count+'/'+field);assert.ok(f.db.statements<=1);
        assert.equal(f.db.raw.prepare("SELECT COUNT(*) AS n FROM pmb1_evidence_events WHERE kind='use-reserved'").get().n,0);
      }finally{f.close();}
    }
  }
});
