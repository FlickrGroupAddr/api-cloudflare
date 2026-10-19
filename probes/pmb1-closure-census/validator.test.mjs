import test from 'node:test';
import assert from 'node:assert/strict';
import {validate,expectationsDigest} from './validator.ts';
function fixture(){
 const plan={candidate:'a'.repeat(64),stores:[{id:'d1',generation:'9007199254740993',writers:['main','schedule'],operations:['mandatory-result']}],externalCustodians:['secret-deploy-operators'],interval:{start:'20',end:'80'},captures:['baseline','preflight','restored'],restoration:'retained-target',ordinary:'current-installation',equality:'typed-full-state',cleanup:'authorized-cleanup',reopen:'separate-authority'};
 const specs=[['census','all-effective-stores-and-writers','1',0,1],['closure','d1','9007199254740993',5,6],['readback','d1','9007199254740993',7,8],['order','d1','9007199254740993',6,90],['drain','d1/main','9007199254740993',2,3],['stale','d1/main','9007199254740993',3,100],['drain','d1/schedule','9007199254740993',2,3],['stale','d1/schedule','9007199254740993',3,100],['drain','d1/operation/mandatory-result','9007199254740993',2,4],['embargo','secret-deploy-operators','1',1,100],['capture','baseline','1',21,25],['capture','preflight','1',30,35],['restore','retained-target','1',40,45],['ordinary','current-installation','1',50,55],['capture','restored','1',60,70],['equality','typed-full-state','1',81,82],['cleanup','authorized-cleanup','1',83,84],['reopen','separate-authority','1',90,91]];
 const receipts=specs.map(([kind,subject,generation,start,end],i)=>({id:`r${i}`,kind,subject,candidate:plan.candidate,generation,start:String(start),end:String(end),evidence:(i+1).toString(16).padStart(64,'0')}));
 const assessments=new Map(receipts.map(r=>[r.evidence,{...r,expectationsDigest:expectationsDigest(plan),conclusion:'complete-supported'}]));
 const observer={assess:key=>assessments.get(key)};
 const change=(kind,subject,field,value)=>{const r=receipts.find(r=>r.kind===kind&&r.subject===subject);r[field]=value;assessments.get(r.evidence)[field]=value;};
 return {plan,receipts,observer,assessments,change};
}
test('synthetic consistent interval, exact >safe-int generation; never actual qualification',()=>{const f=fixture();assert.deepEqual(validate(f.plan,f.receipts,f.observer),{consistent:true,actualQualification:false,reasons:[]});});
const cases={
 'missing store closure':f=>f.receipts.splice(1,1),
 'unknown receipt':f=>f.receipts.push({...f.receipts[0],id:'unknown',subject:'unknown-store',evidence:'f'.repeat(64)}),
 'duplicate receipt':f=>f.receipts.push({...f.receipts[0]}),
 'no independent assessment':f=>f.assessments.clear(),
 'wrong retained expectation':f=>f.plan.stores[0].writers.push('unseen-writer'),
 'unknown operation disposition':f=>f.plan.stores[0].operations.push('unsettled-dispatch'),
 'writer evidence not complete':f=>f.assessments.get(f.receipts[0].evidence).conclusion='writer-assertion',
 'late closure':f=>f.change('closure','d1','end','20'),
 'incomplete interval':f=>f.change('order','d1','start','21'),
 'embargo gap':f=>f.change('embargo','secret-deploy-operators','end','79'),
 'mandatory result after close':f=>f.change('drain','d1/operation/mandatory-result','end','6'),
 'readback before close':f=>f.change('readback','d1','start','5'),
 'stale authority at reopen':f=>f.change('stale','d1/main','end','90'),
 'wrong artifact':f=>f.change('closure','d1','candidate','b'.repeat(64)),
 'rounded generation':f=>f.change('closure','d1','generation','9007199254740992'),
 'overflow generation':f=>f.change('closure','d1','generation','9223372036854775808'),
 'noncanonical time':f=>f.change('closure','d1','start','05'),
 'ordinary check after capture':f=>f.change('ordinary','current-installation','end','61'),
 'reopen during comparison':f=>f.change('reopen','separate-authority','start','79'),
 'early cleanup':f=>f.change('cleanup','authorized-cleanup','start','82'),
 'schema extra field':f=>f.receipts[0].writerSaysClosed=true,
 'unknown expectation field':f=>f.plan.ignoreUnknownStores=true,
 'malformed scalar':f=>f.receipts[0].start=0,
 'throwing observer':f=>f.observer.assess=()=>{throw Error('observer unavailable');},
};
for(const [name,mutate] of Object.entries(cases))test(name,()=>{const f=fixture();mutate(f);const verdict=validate(f.plan,f.receipts,f.observer);assert.equal(verdict.consistent,false);assert.equal(verdict.actualQualification,false);});
test('equality alone never closure',()=>{const f=fixture();assert.equal(validate(f.plan,f.receipts.filter(r=>r.kind==='equality'),f.observer).consistent,false);});
test('second independently listed store requires its own closure, no global drain substitution',()=>{
 const f=fixture();f.plan.stores.push({id:'object-1',generation:'7',writers:['alarm'],operations:[]});
 for(const assessment of f.assessments.values())assessment.expectationsDigest=expectationsDigest(f.plan);
 assert.match(validate(f.plan,f.receipts,f.observer).reasons[0],/missing\/duplicate closure:object-1/);
});
test('new admitted operation remains required with correctly rebound independent plan',()=>{
 const f=fixture();f.plan.stores[0].operations.push('late-result');
 for(const a of f.assessments.values())a.expectationsDigest=expectationsDigest(f.plan);
 assert.match(validate(f.plan,f.receipts,f.observer).reasons[0],/drain:d1\/operation\/late-result/);
});
test('null reopen records consistency without implying reopen authority',()=>{
 const f=fixture();f.plan.reopen=null;f.receipts=f.receipts.filter(r=>r.kind!=='reopen');
 for(const a of f.assessments.values())a.expectationsDigest=expectationsDigest(f.plan);
 assert.equal(validate(f.plan,f.receipts,f.observer).consistent,true);
});
test('ambiguous slash identity refuses',()=>{const f=fixture();f.plan.stores[0].writers=['main/other'];assert.equal(validate(f.plan,f.receipts,f.observer).consistent,false);});
test('receipt cannot borrow identical evidence bytes for another obligation',()=>{const f=fixture();f.receipts[1].evidence=f.receipts[0].evidence;assert.equal(validate(f.plan,f.receipts,f.observer).consistent,false);});
// PMB-1 receipt boundaries are closed intervals. Equal endpoints establish no
// strict predecessor order; an operator embargo must predate every closure.
for(const [name,kind,subject,field,value] of [
 ['embargo begins after closure/readback','embargo','secret-deploy-operators','start','20'],
 ['embargo shares first closure endpoint','embargo','secret-deploy-operators','start','5'],
 ['readback shares closure endpoint','readback','d1','start','6'],
 ['writer settlement shares closure endpoint','drain','d1/main','end','5'],
 ['operation settlement shares closure endpoint','drain','d1/operation/mandatory-result','end','5'],
])test(name,()=>{const f=fixture();f.change(kind,subject,field,value);assert.equal(validate(f.plan,f.receipts,f.observer).consistent,false);});
function twoStores(){
 const f=fixture();f.plan.stores.push({id:'object-1',generation:'7',writers:['alarm'],operations:[]});
 for(const [kind,subject,start,end] of [['closure','object-1',3,4],['readback','object-1',5,6],['order','object-1',4,90],['drain','object-1/alarm',1,2],['stale','object-1/alarm',2,100]]){
  const i=f.receipts.length;
  const r={id:`r${i}`,kind,subject,candidate:f.plan.candidate,generation:'7',start:String(start),end:String(end),evidence:(i+1).toString(16).padStart(64,'0')};
  f.receipts.push(r);f.assessments.set(r.evidence,{...r,conclusion:'complete-supported'});
 }
 for(const a of f.assessments.values())a.expectationsDigest=expectationsDigest(f.plan);
 return f;
}
test('multiple stores independently closed with custody predating earliest closure',()=>{const f=twoStores();assert.equal(validate(f.plan,f.receipts,f.observer).consistent,true);});
test('custody before later store but after earlier store refuses regardless receipt/plan order',()=>{
 for(const reverse of [false,true]){const f=twoStores();f.change('embargo','secret-deploy-operators','start','4');
  if(reverse){f.plan.stores.reverse();f.receipts.reverse();for(const a of f.assessments.values())a.expectationsDigest=expectationsDigest(f.plan);}
  assert.match(validate(f.plan,f.receipts,f.observer).reasons[0],/embargo not established/);
 }
});
