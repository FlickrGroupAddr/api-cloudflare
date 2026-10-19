import {createHash} from 'node:crypto';
/** Inert PMB-1 evidence consistency checker. It performs no I/O or action. */
export type Kind = 'census'|'closure'|'drain'|'order'|'readback'|'embargo'|'stale'|'capture'|'restore'|'ordinary'|'equality'|'cleanup'|'reopen';
export interface Receipt {
  id:string; kind:Kind; subject:string; candidate:string; generation:string;
  start:string; end:string; evidence:string;
}
export interface Store { id:string; generation:string; writers:string[]; operations:string[]; }
/** This plan is independently retained by the reviewer, never derived from receipts. */
export interface Expectations {
  candidate:string; stores:Store[]; externalCustodians:string[];
  interval:{start:string;end:string}; captures:string[];
  restoration:string; ordinary:string; equality:string; cleanup:string;
  reopen:string|null;
}
export interface Assessment {
  expectationsDigest:string;
  candidate:string; kind:Kind; subject:string; generation:string; start:string; end:string;
  // Fixed positive semantics are established by an external evidence adapter/reviewer.
  conclusion:'complete-supported';
}
/** Resolve retained evidence outside receipt JSON. No default verifier exists.
 * Implementers must authenticate observer independence, actual census completeness,
 * settled mandatory results, mutation linearization, full typed equality, custody,
 * bounds and stale-work authority. A boolean or writer acknowledgment is insufficient.
 */
export interface IndependentEvidence { assess(evidence:string):Assessment|undefined; }
export interface Verdict { consistent:boolean; actualQualification:false; reasons:string[]; }
const kinds:Kind[]=['census','closure','drain','order','readback','embargo','stale','capture','restore','ordinary','equality','cleanup','reopen'];
const decimal=/^(0|[1-9][0-9]*)$/;
const generation=/^[1-9][0-9]*$/;
const digest=/^[a-f0-9]{64}$/;
function record(v:unknown, keys:string[]):Record<string,unknown> {
  if(typeof v!=='object'||v===null||Array.isArray(v)||Object.getPrototypeOf(v)!==Object.prototype)throw Error('object');
  const r=v as Record<string,unknown>;
  if(Object.keys(r).sort().join('|')!==keys.slice().sort().join('|'))throw Error('fields');
  return r;
}
function text(v:unknown):string {if(typeof v!=='string'||!v.length||v.length>256)throw Error('string');return v;}
function identity(v:unknown):string{const s=text(v);if(!/^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$/.test(s))throw Error('identity');return s;}
function strings(v:unknown):string[]{if(!Array.isArray(v)||v.length>4096)throw Error('array');const a=v.map(identity);if(new Set(a).size!==a.length)throw Error('duplicate');return a;}
function tick(v:unknown):string{const s=text(v);if(!decimal.test(s)||s.length>32)throw Error('time');return s;}
function gen(v:unknown):string{const s=text(v);if(!generation.test(s)||BigInt(s)>9223372036854775807n)throw Error('generation');return s;}
function sha(v:unknown):string{const s=text(v);if(!digest.test(s))throw Error('digest');return s;}
function parsePlan(v:unknown):Expectations {
  const r=record(v,['candidate','stores','externalCustodians','interval','captures','restoration','ordinary','equality','cleanup','reopen']);
  if(!Array.isArray(r.stores)||!r.stores.length||r.stores.length>4096)throw Error('stores');
  const stores=r.stores.map(v=>{const s=record(v,['id','generation','writers','operations']);return {id:identity(s.id),generation:gen(s.generation),writers:strings(s.writers),operations:strings(s.operations)};});
  if(new Set(stores.map(s=>s.id)).size!==stores.length||stores.some(s=>!s.writers.length))throw Error('store census');
  const interval=record(r.interval,['start','end']);
  const result={candidate:sha(r.candidate),stores,externalCustodians:strings(r.externalCustodians),interval:{start:tick(interval.start),end:tick(interval.end)},captures:strings(r.captures),restoration:identity(r.restoration),ordinary:identity(r.ordinary),equality:identity(r.equality),cleanup:identity(r.cleanup),reopen:r.reopen===null?null:identity(r.reopen)};
  if(BigInt(result.interval.start)>=BigInt(result.interval.end)||result.captures.length!==3||!result.externalCustodians.length)throw Error('interval/captures/custody');
  return result;
}
function parseReceipt(v:unknown):Receipt {
  const r=record(v,['id','kind','subject','candidate','generation','start','end','evidence']);
  const kind=text(r.kind) as Kind;if(!kinds.includes(kind))throw Error('kind');
  const value={id:text(r.id),kind,subject:text(r.subject),candidate:sha(r.candidate),generation:gen(r.generation),start:tick(r.start),end:tick(r.end),evidence:sha(r.evidence)};
  if(BigInt(value.start)>BigInt(value.end))throw Error('backwards');return value;
}
/** Time values are exact nonnegative integer ticks in one independently qualified
 * ordering domain. Adapter must refuse unrelated clocks or unsupported ordering.
 * start/end are supported closed coverage boundaries, not client send timestamps.
 */
export function expectationsDigest(expectations:unknown):string { return createHash('sha256').update(JSON.stringify(parsePlan(expectations))).digest('hex'); }
export function validate(expectations:unknown,input:unknown,observer:IndependentEvidence):Verdict {
  const reasons:string[]=[];
  const refuse=(reason:string)=>{reasons.push(reason);};
  try {
    const plan=parsePlan(expectations);
    if(!Array.isArray(input)||input.length>65536)throw Error('receipts');
    const receipts=input.map(parseReceipt);
    if(new Set(receipts.map(r=>r.id)).size!==receipts.length||new Set(receipts.map(r=>r.evidence)).size!==receipts.length)throw Error('duplicate receipt/evidence');
    const used=new Set<string>();
    const take=(kind:Kind,subject:string,generation:string):Receipt=>{
      const found=receipts.filter(r=>r.kind===kind&&r.subject===subject);
      if(found.length!==1)throw Error(`missing/duplicate ${kind}:${subject}`);
      const r=found[0]!;used.add(r.id);
      if(r.candidate!==plan.candidate||r.generation!==generation)throw Error(`binding ${kind}:${subject}`);
      const a=observer.assess(r.evidence);
      if(!a||a.expectationsDigest!==expectationsDigest(plan)||a.conclusion!=='complete-supported'||a.candidate!==r.candidate||a.kind!==r.kind||a.subject!==r.subject||a.generation!==r.generation||a.start!==r.start||a.end!==r.end)throw Error(`independent evidence ${kind}:${subject}`);
      return r;
    };
    const start=BigInt(plan.interval.start),end=BigInt(plan.interval.end);
    const byStart=(r:Receipt)=>{if(BigInt(r.end)>=start)throw Error(`not before interval ${r.id}`);};
    const covering=(r:Receipt)=>{if(BigInt(r.start)>start||BigInt(r.end)<end)throw Error(`interval gap ${r.id}`);};
    const inside=(r:Receipt)=>{if(BigInt(r.start)<start||BigInt(r.end)>end)throw Error(`outside interval ${r.id}`);};
    const census=take('census','all-effective-stores-and-writers','1');byStart(census);
    // Census assessment must match this entire independently retained plan, including
    // unknown/unsupported/hidden stores, provider metadata, writer identities and pending work.
    let earliestClosure=start;
    for(const store of plan.stores){
      const closure=take('closure',store.id,store.generation);byStart(closure);
      if(BigInt(closure.start)<earliestClosure)earliestClosure=BigInt(closure.start);
      const readback=take('readback',store.id,store.generation);byStart(readback);
      if(BigInt(readback.start)<=BigInt(closure.end))throw Error('readback precedes closure');
      const order=take('order',store.id,store.generation);covering(order);
      for(const writer of store.writers){
        const drain=take('drain',`${store.id}/${writer}`,store.generation);byStart(drain);
        if(BigInt(drain.end)>=BigInt(closure.start))throw Error('closure before drain');
        covering(take('stale',`${store.id}/${writer}`,store.generation));
      }
      for(const operation of store.operations){
        const drain=take('drain',`${store.id}/operation/${operation}`,store.generation);byStart(drain);
        if(BigInt(drain.end)>=BigInt(closure.start))throw Error('mandatory result not settled before closure');
      }
    }
    for(const custodian of plan.externalCustodians){
      const embargo=take('embargo',custodian,'1');covering(embargo);
      if(BigInt(embargo.start)>=earliestClosure)throw Error('embargo not established before closing');
    }
    const captures=plan.captures.map(id=>take('capture',id,'1'));captures.forEach(inside);
    for(let i=1;i<captures.length;i++)if(BigInt(captures[i]!.start)<=BigInt(captures[i-1]!.end))throw Error('capture order');
    const restore=take('restore',plan.restoration,'1');inside(restore);
    const ordinary=take('ordinary',plan.ordinary,'1');inside(ordinary);
    if(BigInt(restore.start)<=BigInt(captures[1]!.end)||BigInt(ordinary.start)<=BigInt(restore.end)||BigInt(captures[2]!.start)<=BigInt(ordinary.end))throw Error('restore/check/capture order');
    const equality=take('equality',plan.equality,'1');
    if(BigInt(equality.start)<=BigInt(captures[2]!.end))throw Error('early equality');
    const cleanup=take('cleanup',plan.cleanup,'1');
    if(BigInt(cleanup.start)<=BigInt(equality.end))throw Error('early cleanup');
    if(plan.reopen!==null){
      const reopen=take('reopen',plan.reopen,'1');
      if(BigInt(reopen.start)<=end||BigInt(reopen.start)<=BigInt(cleanup.end))throw Error('early reopen');
      // Independent stale dispositions must cover the reopen boundary too.
      for(const s of plan.stores)for(const w of s.writers){const stale=receipts.find(r=>r.kind==='stale'&&r.subject===`${s.id}/${w}`)!;if(BigInt(stale.end)<BigInt(reopen.end))throw Error('stale-work uncertainty at reopen');}
    }
    if(used.size!==receipts.length)throw Error('unknown store/writer/receipt');
  }catch(error){refuse(error instanceof Error?error.message:'unreadable evidence');}
  return {consistent:reasons.length===0,actualQualification:false,reasons};
}
