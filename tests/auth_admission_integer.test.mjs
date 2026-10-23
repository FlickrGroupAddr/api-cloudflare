import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {sqlStore} from './sql_store.mjs';
import {admitAuthentication,finishAuthentication,cleanupAuthentication,sourceKey} from '../src/auth_admission.ts';
import {createAdmin} from '../src/admin_api.ts';
import {QUOTA_CLOCK_SQL,INTEGER_QUOTA_FIXTURE_SHA2_256} from '../src/quota_credit.ts';

const fixture=readFileSync(new URL('./integer_quota_fixture.sql',import.meta.url),'utf8');
const source='a'.repeat(64),other='b'.repeat(64),P=120000000n,C=240000000n;
const window=600000000n,day=86400000000n,MAX=9223372036854775807n;
function store(t,now=100000000000n){
 const db=sqlStore();t.after(()=>db.raw.close());
 db.raw.exec('DROP TABLE auth_source_buckets;DROP TABLE status_read_buckets;');db.raw.exec(fixture);
 db.now=now;db.clockSamples=0;db.batches=0;
 db.raw.function('synthetic_auth_clock',()=>{db.clockSamples++;return db.now;});
 const prepare=db.prepare.bind(db),batch=db.batch.bind(db);
 // Replace only the fixed sampling statement with an independently controlled
 // database-clock oracle. Every production check/charge/event SQL is unchanged.
 db.prepare=sql=>prepare(sql===QUOTA_CLOCK_SQL?'INSERT INTO quota_credit_clocks(batch_id,now_us) SELECT ?,synthetic_auth_clock()':sql);
 db.batch=async statements=>{db.batches++;const result=await batch(statements);if(db.ackLost)throw new Error('acknowledgement lost');return result;};
 return db;
}
function rows(db,sql,args=[]){const s=db.raw.prepare(sql);s.setReadBigInts(true);return s.all(...args).map(x=>({...x}));}
function bucket(db,key=source){return rows(db,'SELECT rowid,credit_us,updated_at_us,typeof(credit_us) qt,typeof(updated_at_us) st FROM auth_source_buckets WHERE source_key=?',[key])[0];}
function seed(db,q,s,key=source){db.raw.prepare('INSERT INTO auth_source_buckets VALUES(?,?,?)').run(key,q,s);}
function event(db,id,key=source,route='login',at=db.now,invalid=1){db.raw.prepare('INSERT INTO auth_cost_events VALUES(?,?,?,?,?)').run(id,key,route,at,invalid);}
function snapshot(db){return ['auth_source_buckets','auth_cost_events','quota_credit_guards','quota_credit_clocks'].map(table=>rows(db,`SELECT rowid,* FROM ${table} ORDER BY rowid`));}
function noScratch(db){assert.equal(rows(db,'SELECT * FROM quota_credit_clocks').length,0);assert.equal(rows(db,'SELECT * FROM quota_credit_guards').length,0);}

test('authentication uses the pinned prospective fixture and one complete sampled batch',async t=>{
 assert.equal(createHash('sha256').update(fixture).digest('hex'),INTEGER_QUOTA_FIXTURE_SHA2_256);
 const db=store(t);await admitAuthentication(db,source,'login');
 assert.equal(db.batches,1);assert.equal(db.clockSamples,1);
 assert.deepEqual(bucket(db),{rowid:1n,credit_us:P,updated_at_us:db.now,qt:'integer',st:'integer'});
 assert.equal(rows(db,'SELECT created_at_us FROM auth_cost_events')[0].created_at_us,db.now);noScratch(db);
 await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,0n);
 const before=snapshot(db);await assert.rejects(admitAuthentication(db,source,'login'),/rate_limited/);assert.deepEqual(snapshot(db),before);
});

test('one credit below charge refuses; exact and fractional refill preserve all credits',async t=>{
 const db=store(t,1000000000n);seed(db,P-1n,db.now);
 const before=snapshot(db);await assert.rejects(admitAuthentication(db,source,'login'),/rate_limited/);assert.deepEqual(snapshot(db),before);
 db.now++;await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,0n);
 db.now+=P+17n;await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,17n);assert.equal(bucket(db).updated_at_us,db.now);
});

test('equal/backward clocks spend existing credits without rewinding; int64 maximum saturates safely',async t=>{
 const db=store(t,1000000000n);seed(db,C,db.now+100n);
 await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,P);assert.equal(bucket(db).updated_at_us,1000000100n);
 db.now=1000000100n;await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,0n);
 db.now=MAX;await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,P);assert.equal(bucket(db).updated_at_us,MAX);assert.equal(bucket(db).qt,'integer');
});

test('login and hashed start namespaces separate; callback bypasses both credits and route windows',async t=>{
 const db=store(t);await admitAuthentication(db,source,'login');await admitAuthentication(db,source,'login');
 await admitAuthentication(db,source,'start');await admitAuthentication(db,source,'start');
 const start=createHash('sha256').update('login-start:'+source).digest('hex');assert.equal(bucket(db).credit_us,0n);assert.equal(bucket(db,start).credit_us,0n);
 assert.deepEqual(rows(db,"SELECT invalid_or_inflight FROM auth_cost_events WHERE route='start'"),[{invalid_or_inflight:0n},{invalid_or_inflight:0n}]);
 for(let i=0;i<30;i++)event(db,'window'+i,other,'login',db.now,0);
 const before=rows(db,'SELECT * FROM auth_source_buckets ORDER BY source_key');await admitAuthentication(db,source,'callback');
 assert.deepEqual(rows(db,'SELECT * FROM auth_source_buckets ORDER BY source_key'),before);
});

test('each independent budget refusal rolls back new buckets, refill, charge, events and scratch',async t=>{
 for(const budget of ['source_invalid','global_invalid','login_window','start_window']){
  const db=store(t);const route=budget==='start_window'?'start':'login';
  const count=budget==='source_invalid'?20:budget==='global_invalid'?120:30;
  for(let i=0;i<count;i++)event(db,'seed'+i,budget==='source_invalid'?source:other,budget.endsWith('window')?route:'callback',db.now,budget.endsWith('window')?0:1);
  const before=snapshot(db);await assert.rejects(admitAuthentication(db,source,route),/rate_limited/);assert.deepEqual(snapshot(db),before);
  seed(db,0n,db.now-C,route==='start'?createHash('sha256').update('login-start:'+source).digest('hex'):source);
  const charged=snapshot(db);await assert.rejects(admitAuthentication(db,source,route),/rate_limited/);assert.deepEqual(snapshot(db),charged);
 }
});

test('invalid/inflight accounting is conservative, completion releases only that event',async t=>{
 const db=store(t),ids=[];for(let i=0;i<20;i++)ids.push(await admitAuthentication(db,source,'callback'));
 await assert.rejects(admitAuthentication(db,source,'callback'),/rate_limited/);
 const created=rows(db,'SELECT created_at_us FROM auth_cost_events WHERE event_id=?',[ids[0]])[0].created_at_us;
 await finishAuthentication(db,ids[0]);await finishAuthentication(db,ids[0]);await finishAuthentication(db,'unknown');
 assert.equal(rows(db,'SELECT created_at_us FROM auth_cost_events WHERE event_id=?',[ids[0]])[0].created_at_us,created);
 await admitAuthentication(db,source,'callback');await assert.rejects(admitAuthentication(db,source,'callback'),/rate_limited/);
 assert.equal(rows(db,'SELECT COUNT(*) n FROM auth_source_buckets')[0].n,0n);
});

test('sliding windows use strict boundary, retain future events and handle time zero',async t=>{
 const db=store(t);for(let i=0;i<20;i++)event(db,'edge'+i,source,'callback',db.now-window,1);
 await admitAuthentication(db,source,'callback');
 db.raw.exec('DELETE FROM auth_cost_events');for(let i=0;i<20;i++)event(db,'future'+i,source,'callback',db.now+1n,1);
 await assert.rejects(admitAuthentication(db,source,'callback'),/rate_limited/);
 db.raw.exec('DELETE FROM auth_cost_events');db.now=0n;await admitAuthentication(db,other,'login');assert.equal(bucket(db,other).updated_at_us,0n);
});

test('statement failures roll back the complete batch and unknown acknowledgement never retries/refunds',async t=>{
 for(let fault=0;fault<8;fault++){
  const db=store(t);seed(db,0n,db.now-C);const before=snapshot(db);db.fault=fault;
  await assert.rejects(admitAuthentication(db,source,'login'),/admission_unavailable/);assert.deepEqual(snapshot(db),before);assert.equal(db.batches,1);
 }
 const db=store(t);db.ackLost=true;await assert.rejects(admitAuthentication(db,source,'login'),/admission_unavailable/);
 assert.equal(db.batches,1);assert.equal(bucket(db).credit_us,P);assert.equal(rows(db,'SELECT invalid_or_inflight FROM auth_cost_events')[0].invalid_or_inflight,1n);noScratch(db);
});

test('corrupt clock/state and unrelated constraint failures are unavailable, never exhaustion',async t=>{
 for(const now of [-1n,1.5,null]){const db=store(t,now);await assert.rejects(admitAuthentication(db,source,'callback'),/admission_unavailable/);noScratch(db);}
 for(const [q,s] of [[-1n,0n],[C+1n,0n],[P,-1n]]){
  const db=store(t);db.raw.exec('PRAGMA ignore_check_constraints=ON');seed(db,q,s);db.raw.exec('PRAGMA ignore_check_constraints=OFF');const before=snapshot(db);
  await assert.rejects(admitAuthentication(db,source,'login'),/admission_unavailable/);assert.deepEqual(snapshot(db),before);
 }
 const db=store(t);db.raw.exec("CREATE TRIGGER unrelated BEFORE INSERT ON auth_cost_events BEGIN SELECT RAISE(ABORT,'CHECK constraint failed: unrelated');END");
 await assert.rejects(admitAuthentication(db,source,'login'),/admission_unavailable/);assert.equal(bucket(db),undefined);noScratch(db);
});

test('cleanup retains original 24-hour basis and uses one clock atomically',async t=>{
 const db=store(t);seed(db,P,db.now-day);seed(db,P,db.now-day+1n,other);event(db,'old',source,'callback',db.now-day);event(db,'recent',other,'callback',db.now-day+1n);
 // Completion changes only invalid/inflight; it never re-ages an event or bucket.
 await finishAuthentication(db,'old');await cleanupAuthentication(db);
 assert.equal(db.clockSamples,1);assert.equal(bucket(db),undefined);assert.equal(bucket(db,other).updated_at_us,db.now-day+1n);assert.deepEqual(rows(db,'SELECT event_id FROM auth_cost_events'),[{event_id:'recent'}]);noScratch(db);
 const failed=store(t);seed(failed,P,failed.now-day);event(failed,'old',source,'callback',failed.now-day);const before=snapshot(failed);failed.fault=3;
 await assert.rejects(cleanupAuthentication(failed));assert.deepEqual(snapshot(failed),before);
});

test('denied stale bucket is not refreshed and ordinary successful use advances its watermark',async t=>{
 const db=store(t);seed(db,0n,db.now-day);for(let i=0;i<20;i++)event(db,'invalid'+i,source,'callback');const before=bucket(db);
 await assert.rejects(admitAuthentication(db,source,'login'),/rate_limited/);assert.deepEqual(bucket(db),before);
 await cleanupAuthentication(db);assert.equal(bucket(db),undefined);
 await finishAuthentication(db,'invalid0');await admitAuthentication(db,source,'login');assert.equal(bucket(db).credit_us,P);assert.equal(bucket(db).updated_at_us,db.now);
});

test('untransitioned historical schema refuses without changing quota facts',async t=>{
 const db=sqlStore();t.after(()=>db.raw.close());
 await assert.rejects(admitAuthentication(db,source,'login'),/admission_unavailable/);
 assert.equal(rows(db,'SELECT COUNT(*) n FROM auth_cost_events')[0].n,0n);
 assert.equal(rows(db,'SELECT COUNT(*) n FROM auth_source_buckets')[0].n,0n);
});

test('HTTP exhaustion, invariant failure and lost acknowledgement precede parser/JWKS work',async t=>{
 for(const mode of ['exhausted','invariant','lost_ack']){
  const db=store(t),key='synthetic-private-limiter-key-32-bytes';
  const hashed=sourceKey('192.0.2.1',key);
  if(mode==='exhausted')seed(db,0n,db.now,hashed);
  if(mode==='invariant')db.now=-1n;
  if(mode==='lost_ack')db.ackLost=true;
  let reads=0,fetches=0;
  const request=new Request('https://flickrgroupaddr.com/admin/google-login',{method:'POST',headers:{'CF-Connecting-IP':'192.0.2.1','Content-Type':'application/x-www-form-urlencoded'},body:'credential=untrusted'});
  Object.defineProperty(request,'cf',{value:{}});
  Object.defineProperty(request,'body',{get(){reads++;throw new Error('parser must remain closed');}});
  const app=createAdmin(async()=>{fetches++;throw new Error('JWKS must remain closed');});
  const response=await app.fetch(request,{DB:db,FGA_ADMIN_ENABLED:'1',GOOGLE_OWNER_SUB:'synthetic-owner',GOOGLE_CLIENT_ID:'synthetic-client',AUTH_LIMITER_KEY:{get:async()=>key}});
  assert.equal(response.status,mode==='exhausted'?429:503);assert.equal(response.headers.get('Cache-Control'),'no-store');
  assert.equal(response.headers.get('Retry-After'),mode==='exhausted'?'120':null);assert.equal(reads,0);assert.equal(fetches,0);
  const body=await response.json();assert.equal(body.error.code,mode==='exhausted'?'rate_limited':'admission_unavailable');
  assert.equal(body.error.message,'The request could not be completed.');assert(!JSON.stringify(body).includes(hashed));
  assert.equal(rows(db,'SELECT COUNT(*) n FROM admin_sessions')[0].n,0n);assert.equal(rows(db,'SELECT COUNT(*) n FROM google_login_transactions')[0].n,0n);
  if(mode==='lost_ack'){assert.equal(bucket(db,hashed).credit_us,P);assert.equal(rows(db,'SELECT invalid_or_inflight FROM auth_cost_events')[0].invalid_or_inflight,1n);}
 }
});
