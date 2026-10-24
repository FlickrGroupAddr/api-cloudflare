// MIT License; copyright 2026 Terry Ott.
// Synthetic node:sqlite D1 adapter. Never claims managed/runtime qualification.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {RuntimeEvidenceLedger,encoded,sha2_256,requiredCharge,executionAnchors} from './ledger.ts';
import {preparePublication} from './publisher.ts';
export class SyntheticD1 {
  constructor(path=':memory:',initialize=true) {
    this.raw=new DatabaseSync(path);this.raw.exec('PRAGMA foreign_keys=ON');this.raw.exec('PRAGMA recursive_triggers=OFF');
    if(initialize)this.raw.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
    this.requests=0;this.statements=0;this.primarySessions=0;
  }
  withSession(mode){assert.equal(mode,'first-primary');this.primarySessions++;return this;}
  prepare(sql){return {sql,args:[],bind(...args){this.args=args;return this;}};}
  async batch(statements){
    const index=++this.requests;this.statements+=statements.length;
    if(this.beforeBatch)await this.beforeBatch(index,statements);
    this.raw.exec('BEGIN IMMEDIATE');let results;
    try {results=statements.map(s=>({success:true,results:this.raw.prepare(s.sql).all(...s.args)}));this.raw.exec('COMMIT');}
    catch(error){this.raw.exec('ROLLBACK');throw error;}
    if(this.afterBatch)await this.afterBatch(index,statements,results);
    return results;
  }
  close(){this.raw.close();}
}
export async function setupLedger(payload={synthetic:true},captureKeys=['namespace/object-a'],options={}) {
  const clock={now:options.now??100000};
  const binding={contract:'pmb1-runtime-evidence-v1',profile:'pmb1-private-application-no-real-v1',
    boundary:'pmb1-private-object-kv-interface-v1',schema:'pmb1-evidence-schema-v1',
    databaseId:'aaaaaaaa-0000-4000-8000-000000000001',sourceContext:'a'.repeat(64),lifecycle:'synthetic-lifecycle',generation:'1',
    moduleDigest:'b'.repeat(64),configurationDigest:'c'.repeat(64),resourceInventoryDigest:'d'.repeat(64),
    immutableVersion:'synthetic-immutable-version',nativeSourceDigest:'e'.repeat(64),ownerSourceDigest:'f'.repeat(64),
    controlReference:'synthetic-external-control',...options.binding};
  const provenance={binding:executionAnchors(binding),publisherSourceDigest:'1'.repeat(64),holderInventoryDigest:'2'.repeat(64),writerInventoryDigest:'3'.repeat(64),
    executionAttributionRecord:'4'.repeat(64),historyContinuityRecord:'5'.repeat(64),operatorAttemptLedgerRecord:'6'.repeat(64),
    provenancePathDigest:'a'.repeat(64),holderPolicyDigest:'b'.repeat(64),nativeGetterQualificationRecord:'c'.repeat(64),...options.provenance};
  const reference={databaseId:binding.databaseId,envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:'native-preservation',...options.reference};
  const payloadText=encoded(payload),charge=requiredCharge(payloadText.length,captureKeys.length,1000000);
  const allocation={maxPayloadBytes:payloadText.length,maxAcquiredBytes:charge.acquired,maxDecodedBytes:charge.decoded,
    maxNativeBytes:1000000,maxAggregateBytes:charge.aggregate,maxRequests:8,maxStatements:32,
    maxTotalRequests:charge.requests,maxTotalStatements:charge.statements,...options.allocation};
  const header={mode:'raw-capture',reference,binding,provenance:{...provenance,rootRecord:'7'.repeat(64),reviewRecord:'8'.repeat(64),
    reviewer:'synthetic-fresh-nonauthor',author:'synthetic-Root',fromMs:clock.now-100,throughMs:clock.now+10000,...options.review},
    allocation,fromMs:clock.now-100,throughMs:clock.now+10000,payloadDigest:await sha2_256(payloadText),payloadBytes:payloadText.length,
    chunkCount:Math.ceil(payloadText.length/262144),captureKeys,captureAttempts:captureKeys.map(captureKey=>({captureKey,attemptId:crypto.randomUUID()})),...options.header};
  const handoff={header,payloadText,retainedEnvelopeDigest:await sha2_256(encoded(header)+'\n'+payloadText),
    retainedRootRecord:header.provenance.rootRecord,retainedReviewRecord:header.provenance.reviewRecord};
  const prepared=await preparePublication(handoff,binding,provenance,allocation,clock.now);
  const db=options.db??new SyntheticD1();
  if(!db.raw.prepare("SELECT name FROM sqlite_schema WHERE name='pmb1_journal_control'").get()) {
    db.raw.exec(readFileSync(new URL('../pmb1-native-journal/schema.sql',import.meta.url),'utf8'));
    db.raw.prepare(readFileSync(new URL('../pmb1-native-journal/provision.sql',import.meta.url),'utf8'))
      .run(binding.databaseId,binding.sourceContext,binding.lifecycle,binding.generation);
    db.raw.prepare("UPDATE pmb1_journal_control SET state='stopped',stop_evidence=?,revision=revision+1 WHERE id=1").run('9'.repeat(64));
  }
  if(options.publish!==false)await db.batch(prepared.statements.map(s=>db.prepare(s.sql).bind(...s.args)));
  db.requests=0;db.statements=0;db.primarySessions=0;
  const ledger=()=>new RuntimeEvidenceLedger(db,binding,provenance,allocation,()=>clock.now);
  const retire=()=>db.raw.prepare(`INSERT INTO pmb1_evidence_events
    SELECT ?,1+MAX(revision),'retire','',?,'',? FROM pmb1_evidence_events WHERE envelope_id=?`)
    .run(reference.envelopeId,reference.attemptId,clock.now,reference.envelopeId);
  return {db,binding,provenance,reference,allocation,header,payloadText,prepared,handoff,clock,ledger,retire,close:()=>db.close()};
}
