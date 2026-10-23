// MIT License; copyright 2026 Terry Ott.
import test from 'node:test';
import assert from 'node:assert/strict';
import { D1DomainReader, validateDomain, domainInteger } from './domain.ts';
import { NativeMainEntryObserver } from './observer.ts';
import { D1MainEntryJournal } from '../pmb1-native-journal/journal.ts';
import { MAIN_ENTRY_FAMILIES } from '../../src/main_entry_maintenance.ts';
import { LocalD1, coverage, BINDING, BOUNDS, JOURNAL, DOMAIN, assertNoOutbound } from './fixture.mjs';
const window=()=>({deadlineMs:performance.now()+5000});
const reader=(db,extra={})=>new D1DomainReader(db,BOUNDS,{databaseId:DOMAIN,generation:'1',state:'closed',...extra});
const reason=value=>error=>error.reason===value;

test('complete production D1 SDK reader covers exact717 schema rows and65 typed relations',async()=>{
  const db=new LocalD1();try{
    const facts=await reader(db).capture(window().deadlineMs);validateDomain(facts);
    assert.equal(facts.schema.length,717);assert.equal(Object.keys(facts.tables).length,65);
    assert.equal(domainInteger(facts.tables.maintenance_control[0].generation),'1');
    assert.equal(facts.actualQualification,false);assert(Object.isFrozen(facts.tables.google_jwks_cache[0]));
  }finally{db.close();}
});
test('positive complete main source disposition requires full independent coverage and both journal brackets',async()=>{
  const db=new LocalD1(),external=new LocalD1('journal');try{
    const journal=new D1MainEntryJournal({PMB1_MAIN_JOURNAL:external},{binding:BINDING,journalDatabaseId:JOURNAL,comparedDatabaseIds:[DOMAIN]});
    const stop=await journal.stop(BINDING,window());
    const observer=new NativeMainEntryObserver(journal,BOUNDS,reader(db),coverage(),DOMAIN);
    const result=await observer.assess(BINDING,stop,MAIN_ENTRY_FAMILIES,window());
    assert.equal(result.status,'complete-supported');assert.equal(result.oldCallbacks,'fenced');
    assert.equal(observer.retainedEvidence().domain.tables.google_jwks_cache.length,1);
    assert.equal(observer.retainedEvidence().coverage.observed.writers.length,3);
  }finally{db.close();external.close();}
});
test('exact signed-int64 source values and blobs remain typed, and source schema drift refuses',async()=>{
  const db=new LocalD1();try{
    const trigger=db.db.prepare("SELECT sql FROM sqlite_schema WHERE name='maintenance_control_transition'").get().sql;
    db.db.exec('DROP TRIGGER maintenance_control_transition; UPDATE maintenance_control SET generation=9223372036854775807 WHERE singleton_id=1');
    db.db.exec(trigger);
    const facts=await reader(db,{generation:'9223372036854775807'}).capture(window().deadlineMs);
    assert.equal(domainInteger(facts.tables.maintenance_control[0].generation),'9223372036854775807');
    db.db.exec('CREATE TABLE unexpected(x TEXT)');
    await assert.rejects(reader(db).capture(window().deadlineMs),reason('domain_schema_mismatch'));
  }finally{db.close();}
});
test('source preflight rejects oversized acquisition before full data and control drift refuses',async()=>{
  const db=new LocalD1();try{
    const tiny=new D1DomainReader(db,{...BOUNDS,bytes:1},{databaseId:DOMAIN,generation:'1',state:'closed'});
    await assert.rejects(tiny.capture(window().deadlineMs),reason('domain_acquisition_bound'));
    assert.equal(db.calls.length,1);
    await assert.rejects(reader(db,{generation:'2'}).capture(window().deadlineMs),reason('domain_control_drift'));
  }finally{db.close();}
});
test('native/OAuth/JWKS/group/rate/transaction/attempt/album pending facts refuse without mutation',async()=>{
  const db=new LocalD1();try{
    const original=await reader(db).capture(window().deadlineMs);
    const t=value=>['text',Buffer.from(value).toString('hex').toUpperCase()],i=value=>['integer',value],n=['null',null];
    for(const [table,row,expected] of [
      ['flickr_lifecycle_operations',{phase:t('repair_required')},'domain_pending_flickr_lifecycle_operations'],
      ['flickr_oauth_transactions',{phase:t('exchanging')},'domain_pending_flickr_oauth_transactions'],
      ['google_jwks_cache',{singleton:i('1'),refresh_owner:t('owner')},'domain_jwks_owned'],
      ['group_refresh',{state:t('running')},'domain_pending_group_refresh'],
      ['flickr_rate_reservations',{released:i('0')},'domain_rate_reservation_owned'],
      ['transaction_guards',{approved:i('1')},'domain_transaction_owned'],
      ['submission_attempts',{attempt_id:t('orphan'),intent_id:t('missing')},'domain_attempt_unsettled'],
      ['album_title_attempts',{state:t('dispatched')},'domain_pending_album_title_attempts'],
      ['flickr_native_credentials',{operation_id:t('pending')},'domain_native_generation_owned'],
      ['flickr_connection_state',{state:t('linked'),operation_id:t('pending')},'domain_native_operation_owned'],
    ]){
      const facts=structuredClone(original);facts.tables[table]=[row];assert.throws(()=>validateDomain(facts),reason(expected));
    }
    const absent=structuredClone(original);delete absent.tables.audit_events;
    assert.throws(()=>validateDomain(absent),reason('domain_incomplete'));
  }finally{db.close();}
});
test('authenticated source writer/version/custody omission and expiry refuse',()=>{
  assert.throws(()=>coverage([],({actual})=>actual.writers.pop()),reason('coverage_shape'));
  assert.throws(()=>coverage([],({actual})=>actual.custody.pop()),reason('coverage_custody_missing'));
  assert.throws(()=>coverage([],({actual})=>actual.writers[0].sourceSha2_256='f'.repeat(64)),reason('coverage_writer_missing'));
  const c=coverage([],({actual})=>actual.custody.forEach(row=>{row.fromMs=Date.now()-2000;row.throughMs=Date.now()-1;}));
  assert.throws(()=>c.check(BINDING,JOURNAL,DOMAIN),reason('coverage_outside_interval'));
});
test('late native D1 preflight loses authority and cannot start the data read after deadline',async()=>{
  const db=new LocalD1();let release;const held=new Promise(resolve=>{release=resolve;});
  try{
    db.before=()=>held;
    await assert.rejects(reader(db).capture(performance.now()+25),reason('domain_deadline'));
    release();await new Promise(resolve=>setImmediate(resolve));await new Promise(resolve=>setImmediate(resolve));
    assert.equal(db.calls.length,1);
  }finally{release();db.close();}
});
test.after(assertNoOutbound);
