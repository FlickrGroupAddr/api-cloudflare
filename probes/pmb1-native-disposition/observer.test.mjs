// MIT License; copyright 2026 Terry Ott.
// Synthetic SQLite only; no managed/native qualification or outbound transport.
import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import net from 'node:net';
import dns from 'node:dns';
import { D1MainEntryJournal } from '../pmb1-native-journal/journal.ts';
import { MAIN_ENTRY_FAMILIES } from '../../src/main_entry_maintenance.ts';
import { observeJournal, NativeMainEntryObserver, NativePartitionDisposition } from './observer.ts';

let networkAttempts = 0;
const blocked = () => { networkAttempts++; throw Error('outbound_forbidden'); };
globalThis.fetch = blocked;
net.Socket.prototype.connect = blocked;
dns.lookup = blocked;
const binding = Object.freeze({ candidate:'a'.repeat(64), lifecycle:'synthetic', generation:'9007199254740993' });
const database = 'aaaaaaaa-0000-4000-8000-000000000000';
const compared = 'bbbbbbbb-0000-4000-8000-000000000000';
const bounds = Object.freeze({ pages:128, rows:10000, bytes:4*1024*1024, milliseconds:10000 });
const window = () => ({ deadlineMs:performance.now()+5000 });
const failReason = reason => error => error.reason === reason;
const deferred = () => { let resolve; const promise = new Promise(r => { resolve=r; }); return {promise,resolve}; };

class LocalD1 {
  constructor(path=':memory:', seed=true) {
    this.db = new DatabaseSync(path); this.calls = 0; this.hooks = [];
    this.db.exec('PRAGMA foreign_keys=ON');
    if (seed) {
      this.db.exec(readFileSync(new URL('../pmb1-native-journal/schema.sql', import.meta.url),'utf8'));
      this.db.prepare(readFileSync(new URL('../pmb1-native-journal/provision.sql', import.meta.url),'utf8'))
        .run(database,binding.candidate,binding.lifecycle,binding.generation);
    }
  }
  prepare(sql) {
    const owner = this;
    return { sql, args:[], bind(...args) { this.args=args; return this; }, async all() {
      owner.calls++; return { success:true, results:owner.db.prepare(sql).all(...this.args) };
    } };
  }
  async batch(statements) {
    const hook = this.hooks.shift();
    if (hook) await hook();
    this.db.exec('BEGIN');
    try { const values=[]; for (const s of statements) values.push(await s.all()); this.db.exec('COMMIT'); return values; }
    catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  withSession(mode) { assert.equal(mode,'first-primary'); return this; }
  journal() { return new D1MainEntryJournal({ PMB1_MAIN_JOURNAL:this },
    { binding, journalDatabaseId:database, comparedDatabaseIds:[compared] }); }
  close() { this.db.close(); }
}
async function settled(journal, kind='d1', rejected=false) {
  const lease=await journal.admit(binding,crypto.randomUUID(),'fetch');
  const id=crypto.randomUUID(); await journal.effect(lease,id,kind);
  await journal.settled(lease,id,rejected?'rejected':'fulfilled');
  await journal.returned(lease,'fulfilled'); return lease;
}

test('empty complete journal is retained facts, never positive disposition',async()=>{
  const db=new LocalD1(); try {
    const j=db.journal(),stop=await j.stop(binding,window());
    const result=await observeJournal(j,binding,stop,window(),bounds);
    assert.equal(result.meaning,'external-journal-only'); assert.equal(result.actualQualification,false);
    assert.equal(result.pages,3); assert.deepEqual(result.invocations,[]); assert.deepEqual(result.effects,[]);
    assert(Object.isFrozen(result)); assert(Object.isFrozen(result.control));
    const observer=new NativeMainEntryObserver(j,bounds);
    await assert.rejects(observer.assess(binding,stop,MAIN_ENTRY_FAMILIES,window()),failReason('complete_domain_lifecycle_results_unobserved'));
  } finally { db.close(); }
});
test('all pages and both full relations reconcile above JS-safe generation, including rejected effects',async()=>{
  const db=new LocalD1(); try {
    const j=db.journal();
    for(let i=0;i<130;i++) await settled(j,['provider','provider-body','provider-cancel','secret-read'][i%4],i%3===0);
    const stop=await j.stop(binding,window()); const result=await observeJournal(j,binding,stop,window(),bounds);
    assert.equal(result.invocations.length,130); assert.equal(result.effects.length,130); assert.equal(result.pages,7);
    assert.equal(result.control.generation,binding.generation); assert(Object.isFrozen(result.effects[0]));
  } finally { db.close(); }
});
for(const kind of ['provider','provider-body','provider-cancel','secret-read','d1','repair-reader','wake','asset']) {
  test(`unsettled ${kind} remains an obligation`,async()=>{
    const db=new LocalD1(); try {
      const j=db.journal(),lease=await j.admit(binding,crypto.randomUUID(),'scheduled');
      await j.effect(lease,crypto.randomUUID(),kind);const stop=await j.stop(binding,window());
      await assert.rejects(observeJournal(j,binding,stop,window(),bounds),failReason('journal_obligation_pending'));
    } finally { db.close(); }
  });
}
test('restart retains outstanding handler and a new observer cannot infer old termination',async()=>{
  const folder=mkdtempSync(join(tmpdir(),'pmb1-observer-')),path=join(folder,'synthetic.sqlite');
  let db=new LocalD1(path);
  try {
    const j=db.journal();await j.admit(binding,crypto.randomUUID(),'fetch');const stop=await j.stop(binding,window());
    db.close();db=new LocalD1(path,false);
    await assert.rejects(observeJournal(db.journal(),binding,stop,window(),bounds),failReason('journal_obligation_pending'));
    const partition=new NativePartitionDisposition();
    await assert.rejects(partition.verify(binding.generation),failReason('partition_capabilities_unobserved'));
    await assert.rejects(partition.reconcile({id:crypto.randomUUID(),generation:binding.generation,entry:'alarm'}),
      failReason('partition_capabilities_unobserved'));
  } finally { db.close();rmSync(folder,{recursive:true,force:true}); }
});
test('settlement between pages invalidates the retained revision rather than resnapshot or retry',async()=>{
  const db=new LocalD1();try {
    const j=db.journal(),lease=await j.admit(binding,crypto.randomUUID(),'fetch'),stop=await j.stop(binding,window());
    db.hooks.push(null,async()=>j.returned(lease,'fulfilled'));
    await assert.rejects(observeJournal(j,binding,stop,window(),bounds),failReason('journal_revision_drift'));
  } finally { db.close(); }
});
test('binding, stop, family, row and byte bounds refuse with no implicit recovery',async()=>{
  const db=new LocalD1();try {
    const j=db.journal();await settled(j);const stop=await j.stop(binding,window()),before=db.calls;
    await assert.rejects(observeJournal(j,{...binding,lifecycle:'other'},stop,window(),bounds),failReason('journal_binding'));
    await assert.rejects(observeJournal(j,binding,{...stop,evidence:'b'.repeat(64)},window(),bounds),failReason('journal_page'));
    const after=db.calls;
    await assert.rejects(new NativeMainEntryObserver(j,bounds).assess(binding,stop,MAIN_ENTRY_FAMILIES.slice(1),window()),failReason('main_family_coverage'));
    assert.equal(db.calls,after);assert(after>before);
    await assert.rejects(observeJournal(j,binding,stop,window(),{...bounds,rows:1}),failReason('journal_retained_bound'));
    await assert.rejects(observeJournal(j,binding,stop,window(),{...bounds,bytes:1}),failReason('journal_acquisition_bound'));
    await assert.rejects(observeJournal(j,binding,stop,window(),{...bounds,pages:1}),failReason('journal_page_bound'));
  } finally { db.close(); }
});
test('lost read stays unknown and a late page cannot start another read after timeout',async()=>{
  const db=new LocalD1();try {
    const j=db.journal(),stop=await j.stop(binding,window());
    db.hooks.push(async()=>{throw Error('lost response');}); const before=db.calls;
    await assert.rejects(observeJournal(j,binding,stop,window(),bounds),failReason('journal_read_unknown'));
    assert.equal(db.calls,before);
    const held=deferred();db.hooks.push(()=>held.promise);
    await assert.rejects(observeJournal(j,binding,stop,{deadlineMs:performance.now()+25},bounds),failReason('journal_deadline'));
    held.resolve();await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));
    assert.equal(db.calls,before+2); // only the previously admitted one native page
  } finally { db.close(); }
});
test('clock rewind refuses; invalid partition captures cannot become reconciliation evidence',async()=>{
  const db=new LocalD1();try {
    const j=db.journal(),stop=await j.stop(binding,window());let calls=0;
    await assert.rejects(observeJournal(j,binding,stop,{deadlineMs:100},bounds,()=>++calls===1?50:49),failReason('journal_deadline'));
    const p=new NativePartitionDisposition();
    await assert.rejects(p.verify('090'),failReason('partition_generation'));
    await assert.rejects(p.reconcile({id:'new-current',generation:'1',entry:'fetch'}),failReason('partition_capture'));
  }finally{db.close();}
});
test.after(()=>assert.equal(networkAttempts,0));
