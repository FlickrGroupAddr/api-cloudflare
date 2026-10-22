import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import {
 AUTH_CREDIT_CAPACITY_US, AUTH_CREDIT_CHARGE_US, STATUS_CREDIT_CAPACITY_US,
 STATUS_CREDIT_CHARGE_US, AUTH_CREDIT_REFILL_SQL, STATUS_CREDIT_REFILL_SQL,
 INTEGER_QUOTA_SCHEMA_VERSION, INTEGER_QUOTA_FIXTURE_SHA2_256, QUOTA_CLOCK_SQL,
 beginQuotaClock, authenticationCreditStatements, statusCreditStatements,
 finishQuotaClock, quotaCreditFailure
} from '../src/quota_credit.ts';

const fixture = readFileSync(new URL('./integer_quota_fixture.sql', import.meta.url), 'utf8');
const MAX = 9223372036854775807n, source = 'a'.repeat(64);
const kinds = [
 {kind:'auth', C:BigInt(AUTH_CREDIT_CAPACITY_US), P:BigInt(AUTH_CREDIT_CHARGE_US), table:'auth_source_buckets',
  args:[source], keys:'source_key', where:'source_key=?', expression:AUTH_CREDIT_REFILL_SQL,
  statements:(db,id)=>authenticationCreditStatements(db,id,source)},
 {kind:'status', C:BigInt(STATUS_CREDIT_CAPACITY_US), P:BigInt(STATUS_CREDIT_CHARGE_US), table:'status_read_buckets',
  args:['installation','subject'], keys:'family,subject_id', where:'family=? AND subject_id=?', expression:STATUS_CREDIT_REFILL_SQL,
  statements:(db,id)=>statusCreditStatements(db,id,'installation','subject')}
];

function store(t) {
 const raw = new DatabaseSync(':memory:');
 raw.exec('PRAGMA foreign_keys=ON');
 raw.exec(fixture);
 raw.exec('CREATE TABLE synthetic_events(id TEXT PRIMARY KEY,created_at_us INTEGER NOT NULL) STRICT');
 t.after(()=>raw.close());
 return {raw, prepare(sql) {return {sql,args:[],bind(...args){this.args=args;return this;}};},
  async batch(statements) {
   raw.exec('BEGIN');
   try { for(const s of statements) raw.prepare(s.sql).run(...s.args); raw.exec('COMMIT'); }
   catch(error) {raw.exec('ROLLBACK');throw error;}
  }};
}
function row(db,sql,args=[]) {const s=db.raw.prepare(sql);s.setReadBigInts(true);return s.get(...args);}
function seed(db,k,q,s) {
 db.raw.prepare(`INSERT INTO ${k.table}(${k.keys},credit_us,updated_at_us) VALUES(${[...k.args,q,s].map(()=>'?').join(',')})`).run(...k.args,q,s);
}
function current(db,k) {return row(db,`SELECT rowid AS identity,credit_us,updated_at_us,typeof(credit_us) AS qt,typeof(updated_at_us) AS st FROM ${k.table} WHERE ${k.where}`,k.args);}
function at(db,id,clock) { // Synthetic source oracle clock, never a production override.
 db.raw.function('synthetic_clock',()=>clock);
 return db.prepare('INSERT INTO quota_credit_clocks(batch_id,now_us) SELECT ?,synthetic_clock()').bind(id);
}
function admission(db,k,id,clock,extra=[]) {
 return [at(db,id,clock),...k.statements(db,id),
  db.prepare('INSERT INTO synthetic_events SELECT batch_id,now_us FROM quota_credit_clocks WHERE batch_id=?').bind(id),
  ...extra,...finishQuotaClock(db,id)];
}
function snapshot(db) {
 return ['auth_source_buckets','status_read_buckets','quota_credit_clocks','quota_credit_guards','synthetic_events'].map(table=>{
  const s=db.raw.prepare(`SELECT rowid,* FROM ${table} ORDER BY rowid`);s.setReadBigInts(true);return s.all();
 });
}

// Independent arbitrary-precision rational token oracle: add elapsed/P tokens,
// cap at C/P tokens, then spend one token. No bounded SQL credit branches.
function fraction(n,d=1n) {return {n,d};}
function plus(a,b) {return fraction(a.n*b.d+b.n*a.d,a.d*b.d);}
function compare(a,b) {return a.n*b.d-b.n*a.d;}
function oracle(k,q,s,t) {
 const elapsed=t>s?t-s:0n;
 const replenished=plus(fraction(q,k.P),fraction(elapsed,k.P));
 const capacity=fraction(k.C,k.P);
 const tokens=compare(replenished,capacity)>0n?capacity:replenished;
 if(compare(tokens,fraction(1n))<0n) return null;
 return {q:(tokens.n-tokens.d)*k.P/tokens.d,s:t>s?t:s};
}

test('prospective isolated schema has an exact version/hash and keeps ordinary rowids', t=>{
 assert(fixture.includes(INTEGER_QUOTA_SCHEMA_VERSION));
 assert(!fixture.includes('\r'), 'the exact fixture pin owns UTF-8/LF bytes');
 assert.equal(createHash('sha256').update(fixture).digest('hex'),INTEGER_QUOTA_FIXTURE_SHA2_256);
 assert.doesNotMatch(fixture,/WITHOUT ROWID|ALTER TABLE|\btokens\b/);
 const db=store(t);
 for(const k of kinds) {seed(db,k,k.P,0n);assert.equal(current(db,k).identity,1n);}
});

test('STRICT prospective columns enforce bounded INTEGER state after affinity', t=>{
 const db=store(t);
 for(const k of kinds) {
  for(const [q,s] of [[-1n,0n],[k.C+1n,0n],[1.5,0n],[k.P,-1n],[k.P,0.5],[null,0n],[k.P,null]])assert.throws(()=>seed(db,k,q,s));
  // Integral REAL inputs may become actual INTEGER under INTEGER affinity;
  // the accepted profile protects actual persisted state, not input spelling.
  db.raw.exec(`INSERT INTO ${k.table}(${k.keys},credit_us,updated_at_us) VALUES(${k.args.map(x=>`'${x}'`).join(',')},1.0,0.0)`);
  assert.equal(current(db,k).qt,'integer');assert.equal(current(db,k).st,'integer');
 }
});

for(const k of kinds) {
 test(`${k.kind}: absent bucket starts full and charges atomically`,async t=>{
  const db=store(t);await db.batch(admission(db,k,'new',43n));
  assert.deepEqual({...current(db,k)},{identity:1n,credit_us:k.C-k.P,updated_at_us:43n,qt:'integer',st:'integer'});
  assert.equal(row(db,'SELECT count(*) AS n FROM quota_credit_clocks').n,0n);
  assert.equal(row(db,'SELECT count(*) AS n FROM quota_credit_guards').n,0n);
  assert.equal(row(db,'SELECT created_at_us FROM synthetic_events').created_at_us,43n);
 });

 test(`${k.kind}: SQL versus independent rational oracle at boundaries and signed64 extremes`,async t=>{
  const db=store(t);
  const cases=[
   [k.P-1n,10n,10n],[k.P,10n,10n],[0n,10n,10n],[k.C,10n,9n],
   [k.P-1n,10n,11n],[k.P-2n,10n,11n],[k.C-1n,10n,11n],
   [0n,0n,MAX],[k.C,0n,MAX],[k.P,MAX,0n],[k.P,MAX,MAX],
   [k.P-1n,MAX-1n,MAX],[0n,MAX-k.C,MAX],[1n,MAX-1n,MAX]
  ];
  let rng=0x123456789n;
  function random() {rng=(rng*6364136223846793005n+1442695040888963407n)&MAX;return rng;}
  for(let i=0;i<160;i++) {const s=random(),delta=random()%(k.C*3n);cases.push([random()%(k.C+1n),s,i%3===0?s-delta<0n?0n:s-delta:s+delta>MAX?MAX:s+delta]);}
  for(const [q,s,clock] of cases) {
   db.raw.exec(`DELETE FROM ${k.table};DELETE FROM synthetic_events`);
   seed(db,k,q,s);const before=current(db,k),expected=oracle(k,q,s,clock);
   // Inspect the actual SQLite result type even for rejected one-credit cases.
   const probe=row(db,`SELECT (${k.expression}) AS r,typeof((${k.expression})) AS rt FROM ${k.table} b CROSS JOIN (SELECT ? AS now_us) c`,[clock]);
   assert.equal(probe.rt,'integer');assert(probe.r>=0n&&probe.r<=k.C);
   if(expected) {
    await db.batch(admission(db,k,'case',clock));
    const actual=current(db,k);assert.equal(actual.credit_us,expected.q);assert.equal(actual.updated_at_us,expected.s);
    assert.equal(actual.identity,before.identity);assert.equal(actual.qt,'integer');assert.equal(actual.st,'integer');
   } else {
    await assert.rejects(db.batch(admission(db,k,'case',clock)),error=>quotaCreditFailure(error)==='exhausted');
    assert.deepEqual(current(db,k),before);assert.equal(row(db,'SELECT count(*) AS n FROM synthetic_events').n,0n);
   }
  }
 });

 test(`${k.kind}: tiny accrual survives frequent successful requests and reversed clocks do not mint refill`,async t=>{
  const db=store(t);seed(db,k,k.C,100n);let expected={q:k.C,s:100n};
  const times=[101n,102n,101n,102n,k.P+102n,k.P+103n,k.P+104n,2n*k.P+104n];
  for(let i=0;i<times.length;i++) {
   const next=oracle(k,expected.q,expected.s,times[i]);
   if(next) {await db.batch(admission(db,k,`tiny-${i}`,times[i]));expected=next;}
   else await assert.rejects(db.batch(admission(db,k,`tiny-${i}`,times[i])),/quota_credit_exhausted/);
   assert.equal(current(db,k).credit_us,expected.q);assert.equal(current(db,k).updated_at_us,expected.s);
  }
 });

 test(`${k.kind}: final-statement fault rolls back charge, refill, watermark, insert, event and cleanup`,async t=>{
  const db=store(t);
  for(const initial of [null,[k.P,0n],[k.C-1n,10n]]) {
   db.raw.exec(`DELETE FROM ${k.table}`);if(initial)seed(db,k,...initial);
   const before=snapshot(db),statements=admission(db,k,'rollback',MAX);
   statements.push(db.prepare('INSERT INTO synthetic_events(id,created_at_us) VALUES(NULL,0)'));
   await assert.rejects(db.batch(statements));assert.deepEqual(snapshot(db),before);
  }
 });

 test(`${k.kind}: corrupt persisted types/ranges refuse as unavailable before exhaustion`,async t=>{
  const db=store(t);
  // Deliberately malformed schema simulates an old/corrupt source. Strict fixture
  // checks alone cannot substitute for operation-level actual-type checks.
  db.raw.exec(`DROP TABLE ${k.table};CREATE TABLE ${k.table}(${k.keys.split(',').map(c=>`${c} TEXT`).join(',')},credit_us ANY,updated_at_us ANY,UNIQUE(${k.keys})) STRICT`);
  for(const [q,s] of [[1.5,0n],[Number(k.P),0.5],[null,0n],[k.P,null],[-1n,0n],[k.C+1n,0n],[k.P,-1n],['120000000',0n],[k.P,'0']]) {
   db.raw.exec(`DELETE FROM ${k.table}`);seed(db,k,q,s);const before=snapshot(db);
   await assert.rejects(db.batch(admission(db,k,'corrupt',0n)),error=>quotaCreditFailure(error)==='unavailable');
   assert.deepEqual(snapshot(db),before);
  }
 });
}

test('clock construction validates native source before CAST and samples exactly once per batch',async t=>{
 const db=store(t);let secondsCalls=0,fractionCalls=0;
 db.raw.function('unixepoch',(_now)=>{secondsCalls++;return 123n;});
 db.raw.function('strftime',(_format,_now)=>{fractionCalls++;return '03.007';});
 await db.batch([beginQuotaClock(db,'shared'),...kinds[0].statements(db,'shared'),...kinds[1].statements(db,'shared'),
  db.prepare('INSERT INTO synthetic_events SELECT batch_id,now_us FROM quota_credit_clocks WHERE batch_id=?').bind('shared'),
  ...finishQuotaClock(db,'shared')]);
 assert.equal(secondsCalls,1);assert.equal(fractionCalls,1);
 for(const k of kinds)assert.equal(current(db,k).updated_at_us,123007000n);
 assert.equal(row(db,'SELECT created_at_us FROM synthetic_events').created_at_us,123007000n);
 assert.match(QUOTA_CLOCK_SQL,/CASE WHEN typeof\(seconds\)='integer'/);
 assert.doesNotMatch(QUOTA_CLOCK_SQL,/CAST\(seconds|CAST\(.* AS REAL|Date\.now/);
});

test('clock constructor rejects REAL/text/negative/overflow/invalid fractions without masked evidence',async t=>{
 const db=store(t);
 for(const [seconds,fraction] of [[1.5,'01.000'],['1','01.000'],[-1n,'00.000'],[253402300800n,'00.000'],[MAX,'00.000'],[1n,'00.0x0'],[1n,'60.000'],[1n,null],[null,'00.000']]) {
  db.raw.function('unixepoch',(_now)=>seconds);db.raw.function('strftime',(_format,_now)=>fraction);
  const before=snapshot(db);
  await assert.rejects(db.batch([beginQuotaClock(db,'bad'),...kinds[0].statements(db,'bad'),...finishQuotaClock(db,'bad')]),e=>quotaCreditFailure(e)==='unavailable');
  assert.deepEqual(snapshot(db),before);
 }
 db.raw.function('unixepoch',(_now)=>253402300799n);db.raw.function('strftime',(_format,_now)=> '59.999');
 await db.batch([beginQuotaClock(db,'upper'),...kinds[0].statements(db,'upper'),...finishQuotaClock(db,'upper')]);
 assert.equal(current(db,kinds[0]).updated_at_us,253402300799999000n);
});

test('unmodified database clock produces a validated INTEGER with millisecond source resolution',async t=>{
 const db=store(t);
 await db.batch([beginQuotaClock(db,'native-clock'),...kinds[0].statements(db,'native-clock'),...finishQuotaClock(db,'native-clock')]);
 const actual=current(db,kinds[0]);assert.equal(actual.st,'integer');assert.equal(actual.updated_at_us%1000n,0n);
 assert(actual.updated_at_us>=0n&&actual.updated_at_us<=253402300799999000n);
});

test('clock fraction rejects NUL suffixes, embedded NUL and ordinary trailing text atomically',async t=>{
 const db=store(t);
 for(const fraction of ['00.000\u0000','00.000\u0000junk','00.0\u000000','\u000000.000','00.000junk','00.000 ']) {
  let secondsCalls=0,fractionCalls=0;
  db.raw.function('unixepoch',(_now)=>{secondsCalls++;return 1n;});
  db.raw.function('strftime',(_format,_now)=>{fractionCalls++;return fraction;});
  const before=snapshot(db);
  await assert.rejects(db.batch([beginQuotaClock(db,'bad-fraction'),...kinds[0].statements(db,'bad-fraction'),...finishQuotaClock(db,'bad-fraction')]),e=>quotaCreditFailure(e)==='unavailable');
  assert.equal(secondsCalls,1);assert.equal(fractionCalls,1);assert.deepEqual(snapshot(db),before);
 }
});

test('scratch clock rejects actual REAL/integer-looking REAL and missing/malformed clocks are unavailable',async t=>{
 const db=store(t);
 for(const value of [1.0,1.5,-1n,'1',null]) {
  // A bound JS 1 is INTEGER in node:sqlite; force actual REAL source explicitly.
  const s=value===1.0?db.prepare("INSERT INTO quota_credit_clocks VALUES('bad',1.0)"):at(db,'bad',value);
  await assert.rejects(db.batch([s]),e=>quotaCreditFailure(e)==='unavailable');
 }
 await assert.rejects(db.batch(kinds[0].statements(db,'missing')),e=>quotaCreditFailure(e)==='unavailable');
 db.raw.exec('PRAGMA ignore_check_constraints=ON');
 db.raw.exec("INSERT INTO quota_credit_clocks VALUES('bad',1.0)");
 db.raw.exec('PRAGMA ignore_check_constraints=OFF');
 const before=snapshot(db);
 await assert.rejects(db.batch(kinds[0].statements(db,'bad')),e=>quotaCreditFailure(e)==='unavailable');
 assert.deepEqual(snapshot(db),before);
});

test('all budgets share one transaction: a later quota refusal restores earlier charge and new bucket',async t=>{
 const db=store(t);seed(db,kinds[1],0n,10n);const before=snapshot(db);
 await assert.rejects(db.batch([at(db,'both',10n),...kinds[0].statements(db,'both'),...kinds[1].statements(db,'both'),...finishQuotaClock(db,'both')]),e=>quotaCreditFailure(e)==='exhausted');
 assert.deepEqual(snapshot(db),before);
});

test('status family/subject keys remain separate and UPSERT preserves each hidden rowid',async t=>{
 const db=store(t);
 for(const [id,family,subject] of [['i','installation','same'],['a','admin','same'],['b','admin','other']]) {
  await db.batch([at(db,id,0n),...statusCreditStatements(db,id,family,subject),...finishQuotaClock(db,id)]);
 }
 assert.equal(row(db,'SELECT count(*) AS n FROM status_read_buckets').n,3n);
});

test('local serialized last-credit attempts admit once; no claim of hosted D1 concurrency qualification',async t=>{
 const db=store(t),k=kinds[0];seed(db,k,k.P,0n);
 const attempts=[admission(db,k,'one',0n),admission(db,k,'two',0n)];
 const result=await Promise.allSettled(attempts.map(statements=>db.batch(statements)));
 assert.equal(result.filter(x=>x.status==='fulfilled').length,1);
 assert.equal(current(db,k).credit_us,0n);assert.equal(row(db,'SELECT count(*) AS n FROM synthetic_events').n,1n);
 // Builders never run a separate preliminary read/batch or create a grant.
 const code=readFileSync(new URL('../src/quota_credit.ts',import.meta.url),'utf8');
 assert.doesNotMatch(code,/\.batch\(|\.first\(|\.run\(|fetch\(|Date\.now\(/);
 assert.doesNotMatch(AUTH_CREDIT_REFILL_SQL+STATUS_CREDIT_REFILL_SQL,/\bCAST\b|\bREAL\b|\d+\.\d+|\//);
});

test('only the named exhaustion fault maps to rate refusal; invariant/schema/unknown outcomes are unavailable',()=>{
 for(const error of [new Error('CHECK constraint failed: quota_credit_exhausted'),new Error('D1_ERROR: CHECK constraint failed: quota_credit_exhausted: SQLITE_CONSTRAINT')])assert.equal(quotaCreditFailure(error),'exhausted');
 for(const error of [new Error('CHECK constraint failed: quota_credit_invariant'),new Error('CHECK constraint failed: approved'),new Error('CHECK constraint failed: quota_credit_exhausted_extra'),new Error('lost acknowledgement'),null])assert.equal(quotaCreditFailure(error),'unavailable');
});
