// MIT License; copyright 2026 Terry Ott.
// Synthetic SQLite adapter: real fixed SQL and guards, NOT managed D1 proof.
import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Worker } from 'node:worker_threads';
import { D1MainEntryJournal, PMB1_JOURNAL_SQL } from './journal.ts';
import { MainEntryMaintenance } from '../../src/main_entry_maintenance.ts';

const BINDING = Object.freeze({candidate:'a'.repeat(64),lifecycle:'synthetic-only',generation:'9007199254740993'});
const ID = 'aaaaaaaa-0000-4000-8000-000000000000', COMPARED = 'bbbbbbbb-0000-4000-8000-000000000000';
const config = {binding:BINDING,journalDatabaseId:ID,comparedDatabaseIds:[COMPARED]};
const window = () => ({deadlineMs:performance.now()+10_000});
const deferred = () => {let resolve; const promise = new Promise(r=>{resolve=r;});return {promise,resolve};};
const tick = () => new Promise(resolve=>setImmediate(resolve));

class LocalD1 {
  constructor(path=':memory:') { this.raw=new DatabaseSync(path);this.raw.exec('PRAGMA foreign_keys=ON');this.calls=[]; }
  initialize(seed=true,schema=readFileSync(new URL('./schema.sql',import.meta.url),'utf8')) {
    this.raw.exec('PRAGMA recursive_triggers=OFF');
    this.raw.exec(schema);
    if(seed)this.raw.prepare(readFileSync(new URL('./provision.sql',import.meta.url),'utf8')).run(ID,BINDING.candidate,BINDING.lifecycle,BINDING.generation);
    return this;
  }
  prepare(sql) {
    const self=this;
    return {sql,args:[],bind(...args){this.args=args;return this;},async all(){
      self.calls.push(sql);
      if(self.before){const fn=self.before;self.before=null;await fn(sql);}
      const rows=self.raw.prepare(sql).all(...this.args);
      if(self.after){const fn=self.after;self.after=null;await fn(sql);}
      return {success:true,results:rows};
    }};
  }
  async batch(statements) {
    this.raw.exec('BEGIN IMMEDIATE');
    const results=[];
    try {for (const statement of statements) results.push(await statement.all());this.raw.exec('COMMIT');}
    catch(error){this.raw.exec('ROLLBACK');throw error;}
    if(this.afterBatch){const fn=this.afterBatch;this.afterBatch=null;await fn();}
    return results;
  }
  withSession(mode){assert.equal(mode,'first-primary');return this;}
  journal(options=config,now){return new D1MainEntryJournal({PMB1_MAIN_JOURNAL:this},options,now);}
}

test('construction is inert; missing schema/seed, mismatched inventory and binding refuse',async()=>{
  const db=new LocalD1();const journal=db.journal();assert.equal(db.calls.length,0);
  await assert.rejects(journal.admit(BINDING,crypto.randomUUID(),'fetch'));
  db.initialize(false);assert.equal(await journal.admit(BINDING,crypto.randomUUID(),'fetch'),null);
  await assert.rejects(journal.stop(BINDING,window()));
  assert.throws(()=>db.journal({...config,journalDatabaseId:COMPARED}));
  assert.throws(()=>db.journal({...config,comparedDatabaseIds:[]}));
  assert.throws(()=>db.journal({...config,binding:{...BINDING,generation:'092'}}));
  await assert.rejects(journal.admit({...BINDING,generation:'1'},crypto.randomUUID(),'fetch'));
  db.raw.close();
});

test('fixed exact binding and int64 generation; admission/effect/return holds and once-only outcomes',async()=>{
  const db=new LocalD1().initialize(),journal=db.journal(),invocation=crypto.randomUUID(),effect=crypto.randomUUID();
  const lease=await journal.admit(BINDING,invocation,'scheduled');assert.equal(lease.generation,'9007199254740993');
  await assert.rejects(journal.admit(BINDING,invocation,'scheduled'));
  assert.equal(await journal.effect(lease,effect,'provider-body'),true);
  await assert.rejects(journal.effect(lease,effect,'provider-body'));
  assert.equal(await journal.effect({...lease,invocation:crypto.randomUUID()},crypto.randomUUID(),'d1'),false);
  assert.equal(await journal.effect({...lease,entry:'fetch'},crypto.randomUUID(),'d1'),false);
  await assert.rejects(journal.effect({...lease,generation:'9007199254740992'},crypto.randomUUID(),'d1'));
  await assert.rejects(journal.returned(lease,'fulfilled'));
  await assert.rejects(journal.settled({...lease,entry:'fetch'},effect,'fulfilled'));
  await journal.settled(lease,effect,'rejected');
  await assert.rejects(journal.settled(lease,effect,'fulfilled'));
  await journal.returned(lease,'fulfilled');
  await assert.rejects(journal.returned(lease,'rejected'));
  assert.equal(await journal.effect(lease,crypto.randomUUID(),'d1'),false);
  const page=await journal.page('effects','',10,window());assert.equal(page.rows[0].settled,'rejected');
  assert.equal(page.control.revision,'4');assert.equal(page.next,null);db.raw.close();
});

test('stop is irreversible in stale/new instances and restart; admitted fixed results retain authority',async()=>{
  const folder=mkdtempSync(join(tmpdir(),'pmb1-journal-')),path=join(folder,'synthetic.sqlite');
  try {
    let db=new LocalD1(path).initialize();const stale=db.journal(),other=db.journal();
    const lease=await stale.admit(BINDING,crypto.randomUUID(),'fetch');
    const stop=await other.stop(BINDING,window());assert.equal(stop.admission,'stopped');
    assert.equal(await stale.admit(BINDING,crypto.randomUUID(),'fetch'),null);
    const effect=crypto.randomUUID();assert.equal(await stale.effect(lease,effect,'d1'),true);
    db.raw.close();db=new LocalD1(path);const restarted=db.journal();
    assert.equal(await restarted.admit(BINDING,crypto.randomUUID(),'fetch'),null);
    await restarted.settled(lease,effect,'fulfilled');await restarted.returned(lease,'fulfilled');
    assert.deepEqual(await restarted.stop(BINDING,window()),stop);
    const snapshot=await restarted.page('invocations','',10,window());assert.equal(snapshot.rows[0].returned,'fulfilled');
    assert.equal(snapshot.control.state,'stopped');db.raw.close();
  } finally {rmSync(folder,{recursive:true,force:true});}
});

test('admit/stop race linearizes before commit; late permit remains an admitted obligation',async()=>{
  const db=new LocalD1().initialize(),a=db.journal(),b=db.journal(),blocked=deferred(),entered=deferred();
  db.after=async sql=>{assert.equal(sql,PMB1_JOURNAL_SQL.admit);entered.resolve();await blocked.promise;};
  const pending=a.admit(BINDING,crypto.randomUUID(),'fetch');await entered.promise;
  await b.stop(BINDING,window());blocked.resolve();const lease=await pending;
  assert.ok(lease);assert.equal(await a.admit(BINDING,crypto.randomUUID(),'fetch'),null);
  const rows=await a.page('invocations','',10,window());assert.equal(rows.rows[0].returned,null);
  await a.returned(lease,'fulfilled');db.raw.close();
});

test('stop/admit reverse race refuses dispatch ordered after stop',async()=>{
  const db=new LocalD1().initialize(),a=db.journal(),gate=deferred(),entered=deferred();
  db.before=async sql=>{assert.equal(sql,PMB1_JOURNAL_SQL.admit);entered.resolve();await gate.promise;};
  const pending=a.admit(BINDING,crypto.randomUUID(),'fetch');await entered.promise;
  await db.journal().stop(BINDING,window());gate.resolve();assert.equal(await pending,null);db.raw.close();
});

test('independent SQLite connections race atomic admission versus stop without reopening',async()=>{
  const folder=mkdtempSync(join(tmpdir(),'pmb1-journal-race-'));
  try {
    for(let attempt=0;attempt<8;attempt++) {
      const path=join(folder,`${attempt}.sqlite`),db=new LocalD1(path).initialize(),signal=new SharedArrayBuffer(8),flags=new Int32Array(signal);
      const invocation=crypto.randomUUID(),params=[BINDING.candidate,BINDING.lifecycle,BINDING.generation,ID];
      const run=(sql,args)=>new Promise((resolve,reject)=>{
        const worker=new Worker(new URL('./sql-race-worker.mjs',import.meta.url),{workerData:{path,signal,sql,args}});
        worker.once('message',resolve);worker.once('error',reject);
      });
      const admitted=run(PMB1_JOURNAL_SQL.admit,[invocation,'fetch',...params]);
      const stopped=run(PMB1_JOURNAL_SQL.stop,['f'.repeat(64),...params]);
      const deadline=performance.now()+5000;
      while(Atomics.load(flags,0)<2&&performance.now()<deadline)await tick();
      Atomics.store(flags,1,1);Atomics.notify(flags,1,2);
      const [a,s]=await Promise.all([admitted,stopped]);assert.equal(a.error,undefined);assert.equal(s.error,undefined);
      assert.ok(a.rows.length===0||a.rows.length===1);assert.equal(db.raw.prepare('SELECT state FROM pmb1_journal_control').get().state,'stopped');
      const rows=db.raw.prepare('SELECT invocation,returned FROM pmb1_journal_invocations').all();
      assert.equal(rows.length,a.rows.length);if(rows.length)assert.equal(rows[0].returned,null);
      assert.equal(await db.journal().admit(BINDING,crypto.randomUUID(),'fetch'),null);db.raw.close();
    }
  } finally {rmSync(folder,{recursive:true,force:true});}
});

test('unknown mutation acknowledgement is never replayed; durable holds remain on restart',async()=>{
  const folder=mkdtempSync(join(tmpdir(),'pmb1-journal-')),path=join(folder,'synthetic.sqlite');
  try {
    let db=new LocalD1(path).initialize(),journal=db.journal();
    db.after=async()=>{throw Error('synthetic_lost_ack');};
    await assert.rejects(journal.admit(BINDING,crypto.randomUUID(),'fetch'));
    assert.equal(db.calls.length,1);db.raw.close();db=new LocalD1(path);journal=db.journal();
    const first=await journal.page('invocations','',10,window());assert.equal(first.rows.length,1);assert.equal(first.rows[0].returned,null);
    const lease=await journal.admit(BINDING,crypto.randomUUID(),'fetch'),id=crypto.randomUUID();
    db.after=async()=>{throw Error('synthetic_lost_effect_ack');};
    await assert.rejects(journal.effect(lease,id,'provider'));
    await assert.rejects(journal.returned(lease,'fulfilled'));
    db.raw.close();db=new LocalD1(path);journal=db.journal();
    const effects=await journal.page('effects','',10,window());assert.equal(effects.rows.length,1);assert.equal(effects.rows[0].settled,null);
    db.afterBatch=async()=>{throw Error('synthetic_lost_stop_ack');};
    await assert.rejects(journal.stop(BINDING,window()));db.raw.close();db=new LocalD1(path);
    assert.equal(await db.journal().admit(BINDING,crypto.randomUUID(),'fetch'),null);db.raw.close();
  } finally {rmSync(folder,{recursive:true,force:true});}
});

test('unknown settlement/return acknowledgement retains the exact persisted outcome',async()=>{
  const db=new LocalD1().initialize(),journal=db.journal();const lease=await journal.admit(BINDING,crypto.randomUUID(),'fetch'),id=crypto.randomUUID();
  await journal.effect(lease,id,'d1');db.after=async()=>{throw Error('lost_settled');};
  await assert.rejects(journal.settled(lease,id,'rejected'));
  assert.equal((await db.journal().page('effects','',10,window())).rows[0].settled,'rejected');
  db.after=async()=>{throw Error('lost_returned');};await assert.rejects(journal.returned(lease,'rejected'));
  assert.equal((await db.journal().page('invocations','',10,window())).rows[0].returned,'rejected');db.raw.close();
});

test('SQL guards preserve history against deletion, replace, rebind, forged settlement and stop reset',async()=>{
  const db=new LocalD1().initialize(),journal=db.journal(),lease=await journal.admit(BINDING,crypto.randomUUID(),'fetch'),id=crypto.randomUUID();
  await journal.effect(lease,id,'provider-body');
  const attacks=[
    ['DELETE FROM pmb1_journal_control',[]],['DELETE FROM pmb1_journal_invocations',[]],['DELETE FROM pmb1_journal_effects',[]],
    ["UPDATE pmb1_journal_control SET generation='2',revision=revision+1",[]],
    ["UPDATE pmb1_journal_invocations SET returned='fulfilled'",[]],
    ["UPDATE pmb1_journal_effects SET invocation=?",[crypto.randomUUID()]],
    ["INSERT OR REPLACE INTO pmb1_journal_control SELECT * FROM pmb1_journal_control",[]],
    ["INSERT OR REPLACE INTO pmb1_journal_invocations SELECT * FROM pmb1_journal_invocations",[]],
    ["INSERT OR REPLACE INTO pmb1_journal_effects SELECT * FROM pmb1_journal_effects",[]],
    ["UPDATE pmb1_journal_control SET state='stopped',stop_evidence=NULL,revision=revision+1",[]],
    ["INSERT INTO pmb1_journal_effects VALUES(?,?,?,'fulfilled')",[crypto.randomUUID(),lease.invocation,'d1']],
  ];
  for(const [sql,args]of attacks)assert.throws(()=>db.raw.prepare(sql).run(...args));
  await journal.settled(lease,id,'fulfilled');await journal.returned(lease,'fulfilled');await journal.stop(BINDING,window());
  assert.throws(()=>db.raw.exec("UPDATE pmb1_journal_control SET state='open',stop_evidence=NULL,revision=revision+1"));
  assert.throws(()=>db.raw.exec("UPDATE pmb1_journal_effects SET settled='rejected'"));
  assert.throws(()=>db.raw.exec("UPDATE pmb1_journal_invocations SET returned='rejected'"));db.raw.close();
});

test('hidden rowid replacement cannot erase an admitted invocation; old rowid negative control reproduces finding',async()=>{
  const schema=readFileSync(new URL('./schema.sql',import.meta.url),'utf8');
  for(const protectedSchema of [false,true]) {
    const db=new LocalD1().initialize(true,protectedSchema?schema:schema.replaceAll('STRICT, WITHOUT ROWID','STRICT'));
    try {
      const journal=db.journal(),lease=await journal.admit(BINDING,crypto.randomUUID(),'fetch'),replacement=crypto.randomUUID();
      const replace=()=>db.raw.prepare('INSERT OR REPLACE INTO pmb1_journal_invocations(rowid,invocation,candidate,lifecycle,generation,entry) VALUES(?,?,?,?,?,?)').run(1,replacement,BINDING.candidate,BINDING.lifecycle,BINDING.generation,'scheduled');
      if(protectedSchema)assert.throws(replace);else replace();
      const rows=(await journal.page('invocations','',10,window())).rows;
      assert.equal(rows.length,1);assert.equal(rows[0].invocation,protectedSchema?lease.invocation:replacement);assert.equal(rows[0].returned,null);
    } finally {db.raw.close();}
  }
});

test('hidden rowid replacement cannot erase a pending effect; old rowid negative control reproduces finding',async()=>{
  const schema=readFileSync(new URL('./schema.sql',import.meta.url),'utf8');
  for(const protectedSchema of [false,true]) {
    const db=new LocalD1().initialize(true,protectedSchema?schema:schema.replaceAll('STRICT, WITHOUT ROWID','STRICT'));
    try {
      const journal=db.journal(),lease=await journal.admit(BINDING,crypto.randomUUID(),'fetch'),effect=crypto.randomUUID(),replacement=crypto.randomUUID();
      await journal.effect(lease,effect,'provider');
      const replace=()=>db.raw.prepare('INSERT OR REPLACE INTO pmb1_journal_effects(rowid,effect,invocation,kind) VALUES(?,?,?,?)').run(1,replacement,lease.invocation,'d1');
      if(protectedSchema)assert.throws(replace);else replace();
      const rows=(await journal.page('effects','',10,window())).rows;
      assert.equal(rows.length,1);assert.equal(rows[0].effect,protectedSchema?effect:replacement);assert.equal(rows[0].settled,null);
    } finally {db.raw.close();}
  }
});

test('all protected tables have only their explicit primary identity; rowid aliases and control-id changes refuse',async()=>{
  const db=new LocalD1().initialize(),journal=db.journal(),lease=await journal.admit(BINDING,crypto.randomUUID(),'fetch'),effect=crypto.randomUUID();
  await journal.effect(lease,effect,'provider-body');
  const beforeControl=await journal.page('invocations','',10,window()),beforeEffect=await journal.page('effects','',10,window());
  const tables=['pmb1_journal_control','pmb1_journal_invocations','pmb1_journal_effects'];
  for(const table of tables) {
    const metadata=db.raw.prepare('SELECT wr,strict FROM pragma_table_list WHERE name=?').get(table);assert.equal(metadata.wr,1);assert.equal(metadata.strict,1);
    for(const alias of ['rowid','oid','_rowid_']) {
      assert.throws(()=>db.raw.prepare(`SELECT ${alias} FROM ${table}`).all());
      assert.throws(()=>db.raw.prepare(`UPDATE OR REPLACE ${table} SET ${alias}=2`).run());
    }
  }
  assert.throws(()=>db.raw.exec('UPDATE OR REPLACE pmb1_journal_control SET id=2,revision=revision+1'));
  assert.throws(()=>db.raw.exec("INSERT OR REPLACE INTO pmb1_journal_control SELECT 1,schema_version,database_id,candidate,lifecycle,generation,state,stop_evidence,0 FROM pmb1_journal_control"));
  assert.throws(()=>db.raw.exec('INSERT OR REPLACE INTO pmb1_journal_control(rowid,id) VALUES(1,1)'));
  assert.deepEqual(await journal.page('invocations','',10,window()),beforeControl);
  assert.deepEqual(await journal.page('effects','',10,window()),beforeEffect);db.raw.close();
});

test('complete keyset paging exposes revision changes and does not infer disposition',async()=>{
  const db=new LocalD1().initialize(),journal=db.journal(),leases=[];
  for(let i=0;i<5;i++)leases.push(await journal.admit(BINDING,crypto.randomUUID(),'fetch'));
  let cursor='',all=[];do{const p=await journal.page('invocations',cursor,2,window());all.push(...p.rows);cursor=p.next;}while(cursor!==null);
  assert.equal(new Set(all.map(r=>r.invocation)).size,5);
  const first=await journal.page('invocations','',2,window());await journal.returned(leases[0],'fulfilled');
  const second=await journal.page('invocations',first.next,2,window());assert.notEqual(first.control.revision,second.control.revision);
  for(const args of [['effects','',257],['effects','unsafe',1],['unknown','',1]])await assert.rejects(journal.page(...args,window()));db.raw.close();
});

test('deadline/lost stop response does not reopen or claim native query cancellation',async()=>{
  const db=new LocalD1().initialize();let now=0;const journal=db.journal(config,()=>now);
  db.afterBatch=async()=>{now=11;};await assert.rejects(journal.stop(BINDING,{deadlineMs:10}));
  assert.equal(db.raw.prepare('SELECT state FROM pmb1_journal_control').get().state,'stopped');
  assert.equal(await db.journal().admit(BINDING,crypto.randomUUID(),'fetch'),null);
  const calls=db.calls.length;await assert.rejects(journal.stop(BINDING,{deadlineMs:10}));assert.equal(db.calls.length,calls);db.raw.close();
});

test('caller mutation cannot extend an already dispatched stop deadline',async()=>{
  const db=new LocalD1().initialize();let now=0;const supplied={deadlineMs:10},journal=db.journal(config,()=>now);
  db.afterBatch=async()=>{now=11;supplied.deadlineMs=100;};
  await assert.rejects(journal.stop(BINDING,supplied));assert.equal(db.raw.prepare('SELECT state FROM pmb1_journal_control').get().state,'stopped');db.raw.close();
});

test('main-entry body hold remains until completion; delayed durable receipt retains conservative invocation hold',async()=>{
  const db=new LocalD1().initialize(),journal=db.journal();let body;const release=deferred();
  const bridge=new MainEntryMaintenance(BINDING,journal,{assess(){assert.fail('not an observer proof');}});
  const pending=bridge.run('fetch',async scope=>{
    const response=await scope.fetcher(async()=>new Response(new ReadableStream({start(c){body=c;}})))(new Request('https://example.invalid'));
    await release.promise;return await response.text();
  });
  for(let i=0;i<6;i++)await tick();
  const page=await journal.page('effects','',20,window());assert.equal(page.rows.filter(r=>r.kind==='provider-body'&&r.settled===null).length,1);
  await journal.stop(BINDING,window());release.resolve();body.enqueue(new TextEncoder().encode('synthetic'));body.close();
  assert.equal(await pending,'synthetic');
  // Existing seam refuses drain if handler return races its durable body receipt.
  // The journal must retain this unresolved invocation, never infer it returned.
  assert.equal((await journal.page('invocations','',20,window())).rows[0].returned,null);
  for(let i=0;i<4;i++)await tick();
  assert.equal((await journal.page('effects','',20,window())).rows.every(r=>r.settled==='fulfilled'),true);db.raw.close();
});

test('malformed native acknowledgement refuses without mutation replay',async()=>{
  const db=new LocalD1().initialize(),original=db.prepare.bind(db);let attempts=0;
  db.prepare=sql=>{const statement=original(sql);statement.all=async()=>{attempts++;return {success:true,results:[null]};};return statement;};
  await assert.rejects(db.journal().admit(BINDING,crypto.randomUUID(),'fetch'));assert.equal(attempts,1);db.raw.close();
});
