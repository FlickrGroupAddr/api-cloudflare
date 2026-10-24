// MIT License; copyright 2026 Terry Ott. Local workerd SOURCE fixture only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync,writeFileSync } from 'node:fs';
import { resolve,join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { Miniflare,Log,LogLevel,kCurrentWorker } from 'miniflare';
import { PrivatePartitionController } from '../controller.ts';
const sha=value=>createHash('sha256').update(value).digest('hex');
const build=resolve(process.env.PMB1_ARTIFACT_DIRECTORY),receipt=resolve(process.env.PMB1_SYNTHETIC_RECEIPT);
const manifest=JSON.parse(readFileSync(join(build,'artifact-manifest.json')));
for(const [name,pin]of Object.entries(manifest.sourceInputs))assert.equal(sha(readFileSync(new URL('../../../'+name,import.meta.url))),pin,name);
test('exact emitted private-RPC refuses unsupported pinned native metadata before target acquisition',async()=>{
  for(const [name,pin] of Object.entries(manifest.moduleSha2_256)){assert.equal(sha(readFileSync(join(build,'emitted',name))),pin);assert.equal(sha(readFileSync(join(build,'retained/modules',name))),pin);}
  let outbound=0;
  const nativePath=resolve(process.env.PMB1_NATIVE_FIXTURE_ROOT);
  const options={modules:true,modulesRoot:join(build,'emitted'),scriptPath:join(build,'emitted/entry.js'),
    compatibilityDate:'2026-08-06',compatibilityFlags:['nodejs_compat'],versionMetadata:'PMB1_VERSION_METADATA',
    log:new Log(LogLevel.ERROR),cf:false,port:0,inspectorPort:0,host:'127.0.0.1',
    durableObjectsPersist:join(nativePath,'do'),d1Persist:join(nativePath,'d1'),
    d1Databases:{DB:'bbbbbbbb-0000-4000-8000-000000000000',PMB1_MAIN_JOURNAL:'aaaaaaaa-0000-4000-8000-000000000000',ORACLE_DB:'ffffffff-0000-4000-8000-000000000000'},
    durableObjects:{COORD:{className:'SyntheticCaptureOwner',useSQLite:true},DRIVER:{className:'SyntheticSourceDriver',useSQLite:true},ORACLE_OWNERS:{className:'SyntheticOracleOwner',useSQLite:true}},
    outboundService:()=>{outbound++;throw Error('outbound_forbidden');}};
  const mf=new Miniflare(options);
  try{
    const driverNamespace=await mf.getDurableObjectNamespace('DRIVER'),driver=driverNamespace.get(driverNamespace.idFromName('fixed-synthetic-driver'));
    const nativeVersion=await driver.nativeVersionSynthetic();
    const input=join(receipt,'metadata.json'),fixturePath=join(receipt,'fixture.json');
    const allocatedOwners=await mf.getDurableObjectNamespace('COORD'),objectIds=['fixed-synthetic-a','fixed-synthetic-b'].map(name=>allocatedOwners.idFromName(name).toString());
    writeFileSync(input,JSON.stringify({nativeVersion,objectIds,moduleDigest:sha(JSON.stringify(manifest.moduleSha2_256)),
      configurationDigest:manifest.configurationSha2_256,resourceInventoryDigest:manifest.bindingManifestSha2_256}));
    execFileSync(process.execPath,[new URL('./prepare.mjs',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'),input,fixturePath],{stdio:'pipe'});
    const preliminary=JSON.parse(readFileSync(fixturePath)),oracleDb=await mf.getD1Database('ORACLE_DB');
    const canonicalStatements=preliminary.domain.filter(s=>s.sql!=='CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID');
    for(const s of canonicalStatements)await oracleDb.prepare(s.sql).bind(...s.args).run();
    const domainOracle=(await oracleDb.prepare('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name').all()).results;
    const oracleNamespace=await mf.getDurableObjectNamespace('ORACLE_OWNERS'),oracle=oracleNamespace.get(oracleNamespace.idFromName('fixed-independent-native-oracle'));
    await oracle.seedSynthetic();const nativeOracle=await oracle.oracleMetadataSynthetic();
    const metadata=JSON.parse(readFileSync(input));
    Object.assign(metadata,{domainOracle,nativeOracle,runtimeSourceSha2_256:Object.entries(manifest.toolchain).find(([n])=>n.includes('workerd.exe'))[1],
      applicationSourceSha2_256:sha(Buffer.concat(['d1-schema.sql','d1-guards.sql'].map(n=>readFileSync(new URL('../../pmb1-integer-candidate/'+n,import.meta.url)))))});
    writeFileSync(join(receipt,'INDEPENDENT-ORACLE-FREEZE.json'),JSON.stringify({domainOracle,nativeOracle,sha2_256:sha(JSON.stringify({domainOracle,nativeOracle})),frozenBeforeTargetAcquisition:true}));
    writeFileSync(input,JSON.stringify(metadata));
    if(nativeOracle.schema.some(row=>row.name==='_cf_KV')&&!nativeOracle.schema.some(row=>row.name==='__cf_kv')){
      assert.throws(()=>execFileSync(process.execPath,[new URL('./prepare.mjs',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'),input,fixturePath],{stdio:'pipe'}),/independent_oracle_application_source_mismatch/);
      writeFileSync(join(receipt,'native-fit.json'),JSON.stringify({outcome:'expected-refusal-before-target-acquisition',
        normativeObjectAutomaticTable:'__cf_kv',pinnedEmulatorAutomaticTable:'_cf_KV',targetAcquisitions:0,
        positiveNativeRpc:false,configuredDate:'2026-10-16',emulatorDate:'2026-08-06',configuredDateFit:false,actualQualification:false}));
      assert.equal(outbound,0);return;
    }
    execFileSync(process.execPath,[new URL('./prepare.mjs',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'),input,fixturePath],{stdio:'pipe'});
    const fixture=JSON.parse(readFileSync(fixturePath)),db=await mf.getD1Database('DB'),journal=await mf.getD1Database('PMB1_MAIN_JOURNAL');
    for(const [database,statements] of [[db,fixture.domain.filter(s=>s.sql!=='CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID')],[journal,fixture.journal]])for(const s of statements)
      try{await database.prepare(s.sql).bind(...s.args).run();}catch(error){throw new Error('synthetic schema install '+s.sql.slice(0,100),{cause:error});}
    const owners=await mf.getDurableObjectNamespace('COORD');
    for(const id of fixture.objects)await owners.get(owners.idFromString(id.id)).seedSynthetic();
    const result=await driver.observeSynthetic();
    assert.equal(result.status,'complete-supported');assert.equal(result.objects,2);assert.equal(result.tables,65);
    assert.equal(result.nativeVersion,nativeVersion);assert.equal(result.actualQualification,false);
    assert.equal(outbound,0);
  }finally{await mf.dispose();}
});

test('native private controller stops and closes two same-context owning partitions without raw-capture authority',async()=>{
  let outbound=0;const nativePath=join(resolve(process.env.PMB1_NATIVE_FIXTURE_ROOT),'control');
  const mf=new Miniflare({modules:true,modulesRoot:join(build,'emitted'),scriptPath:join(build,'emitted/entry.js'),
    compatibilityDate:'2026-08-06',compatibilityFlags:['nodejs_compat'],versionMetadata:'PMB1_VERSION_METADATA',
    log:new Log(LogLevel.ERROR),cf:false,port:0,inspectorPort:0,host:'127.0.0.1',
    durableObjectsPersist:join(nativePath,'do'),d1Persist:join(nativePath,'d1'),
    d1Databases:{DB:'bbbbbbbb-0000-4000-8000-000000000000',PMB1_MAIN_JOURNAL:'aaaaaaaa-0000-4000-8000-000000000000'},
    durableObjects:{COORD:{className:'SyntheticCaptureOwner',useSQLite:true}},
    outboundService:()=>{outbound++;throw Error('outbound_forbidden');}});
  try{
    const ns=await mf.getDurableObjectNamespace('COORD');let calls=0;
    for(const name of ['source-control-a','source-control-b']){
      const objectId=ns.idFromName(name).toString(),owner=ns.get(ns.idFromString(objectId));await owner.seedOpenSynthetic();
      const allocation=operation=>({operationId:crypto.randomUUID(),namespace:'b'.repeat(32),objectId,generation:'2',operation,
        fromMs:Date.now()-100,throughMs:Date.now()+10000,calls:1,operatorLedgerRecord:'synthetic-outer-reserved',independentSourceReviewRecord:'synthetic-source-reviewed'});
      for(const operation of ['stop','close']){
        const controller=new PrivatePartitionController(ns,'b'.repeat(32),allocation(operation));await controller.run();calls++;await assert.rejects(controller.run());
      }
      const observed=await owner.controlStateSynthetic();assert.deepEqual(observed.control,[{generation:'3',state:'closed'}]);assert.equal(observed.admission,false);
      // A missing raw reservation refuses before local snapshot acquisition;
      // control operation IDs never create or substitute capture authority.
      await assert.rejects(owner.snapshotFresh({databaseId:'aaaaaaaa-0000-4000-8000-000000000000',envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:'native-preservation'},'a'.repeat(64)));
      const after=await owner.controlStateSynthetic();assert.deepEqual(after.control,observed.control);assert.equal(after.admission,observed.admission);
    }
    assert.equal(calls,4);assert.equal(outbound,0);
    writeFileSync(join(receipt,'private-control-rpc.json'),JSON.stringify({objects:2,allocatedControlCalls:4,
      sameOwningContext:true,controlAuthority:'synthetic outer operator ledger precondition',rawCaptureAuthorityCreated:false,
      actualQualification:false,positiveNativeRawSnapshot:false}));
  }finally{await mf.dispose();}
});

test('same emitted Worker private main RPC stops and strictly refuses unsupported provider metadata',async()=>{
  let outbound=0;const nativePath=join(resolve(process.env.PMB1_NATIVE_FIXTURE_ROOT),'main');
  const mf=new Miniflare({name:'synthetic-same-main',modules:true,modulesRoot:join(build,'emitted'),scriptPath:join(build,'emitted/entry.js'),
    compatibilityDate:'2026-08-06',compatibilityFlags:['nodejs_compat'],versionMetadata:'PMB1_VERSION_METADATA',
    log:new Log(LogLevel.ERROR),cf:false,port:0,inspectorPort:0,host:'127.0.0.1',durableObjectsPersist:join(nativePath,'do'),d1Persist:join(nativePath,'d1'),
    d1Databases:{DB:'bbbbbbbb-0000-4000-8000-000000000000',PMB1_MAIN_JOURNAL:'aaaaaaaa-0000-4000-8000-000000000000',ORACLE_DB:'ffffffff-0000-4000-8000-000000000000'},
    durableObjects:{COORD:{className:'SyntheticCaptureOwner',useSQLite:true}},
    serviceBindings:{PMB1_PRIVATE_MAIN:{name:kCurrentWorker,entrypoint:'SyntheticPrivateMainMaintenance'}},
    outboundService:()=>{outbound++;throw Error('outbound_forbidden');}});
  try{
    const prepare=new URL('./prepare.mjs',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'),input=join(receipt,'main-metadata.json'),file=join(receipt,'main-fixture.json');
    const metadata={nativeVersion:'synthetic-preparation-only',moduleDigest:sha(JSON.stringify(manifest.moduleSha2_256)),configurationDigest:manifest.configurationSha2_256,resourceInventoryDigest:manifest.bindingManifestSha2_256};
    writeFileSync(input,JSON.stringify(metadata));execFileSync(process.execPath,[prepare,input,file],{stdio:'pipe'});
    const preliminary=JSON.parse(readFileSync(file)),domain=await mf.getD1Database('DB'),journal=await mf.getD1Database('PMB1_MAIN_JOURNAL'),oracle=await mf.getD1Database('ORACLE_DB');
    const application=preliminary.domain.filter(s=>s.sql!=='CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID');
    for(const s of application)await oracle.prepare(s.sql).bind(...s.args).run();
    const domainOracle=(await oracle.prepare('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name').all()).results;
    writeFileSync(join(receipt,'MAIN-INDEPENDENT-ORACLE.json'),JSON.stringify({domainOracle,frozenBeforeTargetAcquisition:true}));
    let metadataReadable=true;
    if(domainOracle.some(row=>row.name==='_cf_METADATA')){
      try{await oracle.prepare("SELECT CAST(key AS TEXT) k,typeof(value) t,CASE typeof(value) WHEN 'integer' THEN CAST(value AS TEXT) WHEN 'blob' THEN hex(value) WHEN 'text' THEN hex(CAST(value AS BLOB)) ELSE NULL END v FROM main._cf_METADATA ORDER BY key LIMIT 17").all();}
      catch(error){if(!/SQLITE_AUTH|not authorized/.test(String(error)))throw error;metadataReadable=false;}
      writeFileSync(join(receipt,'D1-ORACLE-ACCESS.json'),JSON.stringify({table:'_cf_METADATA',metadataReadable,independentOracle:true,completePreservationRequired:true,exclusionAdded:false}));
    }
    for(const s of application)await domain.prepare(s.sql).bind(...s.args).run();
    for(const s of preliminary.journal){
      if(s.sql.startsWith('INSERT INTO "pmb1_evidence_'))continue;
      const args=[...s.args];if(s.sql.startsWith('INSERT INTO "pmb1_journal_control"')){args[6]='open';args[7]=null;args[8]=0;}
      await journal.prepare(s.sql).bind(...args).run();
    }
    const service=(await mf.getBindings()).PMB1_PRIVATE_MAIN,current=await service.currentMain('bbbbbbbb-0000-4000-8000-000000000000',crypto.randomUUID()),
      target={databaseId:current.target.databaseId,domainDatabaseId:current.target.domainDatabaseId,candidate:current.target.candidate,lifecycle:current.target.lifecycle,generation:current.target.generation,versionId:current.target.versionId};
    assert.equal(current.state,'open');
    await assert.rejects(async()=>await service.stopAdmission({...target,versionId:'foreign-version'},crypto.randomUUID()));
    assert.equal((await service.stopAdmission(target,crypto.randomUUID())).admission,'stopped');
    Object.assign(metadata,{nativeVersion:target.versionId,mode:'evidence-use',purpose:'main-assess',custodyMs:120000,observationMilliseconds:60000,domainOracle,
      runtimeSourceSha2_256:Object.entries(manifest.toolchain).find(([n])=>n.includes('workerd.exe'))[1],
      applicationSourceSha2_256:sha(Buffer.concat(['d1-schema.sql','d1-guards.sql'].map(n=>readFileSync(new URL('../../pmb1-integer-candidate/'+n,import.meta.url)))))});
    let first;
    for(let interval=0;interval<2;interval++){
      if(first)await new Promise(resolve=>setTimeout(resolve,Math.max(1,first.throughMs-Date.now()+10)));
      writeFileSync(input,JSON.stringify(metadata));execFileSync(process.execPath,[prepare,input,file],{stdio:'pipe'});
      const next=JSON.parse(readFileSync(file));await journal.batch(next.prepared.statements.map(s=>journal.prepare(s.sql).bind(...s.args)));
      if(!metadataReadable){
        await assert.rejects(async()=>await service.assessStopped(target,crypto.randomUUID()),/native_domain_oracle/);
        writeFileSync(join(receipt,'private-main-rpc.json'),JSON.stringify({sameWorkerArtifact:true,currentAndStopAdmission:true,
          assessment:'expected-strict-refusal-inaccessible-unselected-provider-metadata',actualQualification:false,positiveNativeDomainAssessment:false}));
        assert.equal(outbound,0);return;
      }
      const began=Date.now();let disposition;
      try{disposition=await service.assessStopped(target,crypto.randomUUID());}catch(error){
        writeFileSync(join(receipt,'main-refusal.json'),JSON.stringify({began,failedAt:Date.now(),fromMs:next.prepared.header.fromMs,throughMs:next.prepared.header.throughMs,
          events:(await journal.prepare('SELECT kind FROM pmb1_evidence_events WHERE envelope_id=? ORDER BY revision').bind(next.reference.envelopeId).all()).results}));throw error;
      }
      assert.equal(disposition.status,'complete-supported');writeFileSync(join(receipt,'main-interval-'+interval+'.json'),JSON.stringify({began,completedAt:Date.now(),fromMs:next.prepared.header.fromMs,throughMs:next.prepared.header.throughMs}));
      const events=(await journal.prepare('SELECT kind,capture_key FROM pmb1_evidence_events WHERE envelope_id=? ORDER BY revision').bind(next.reference.envelopeId).all()).results;
      assert.deepEqual(events.map(e=>e.kind),['publish','use-reserved','terminal']);assert(events.every(e=>e.capture_key===''));
      if(!first)first={envelope:next.reference.envelopeId,headerRaw:(await journal.prepare('SELECT header_json FROM pmb1_evidence_envelopes WHERE envelope_id=?').bind(next.reference.envelopeId).first()).header_json,throughMs:next.prepared.header.throughMs};
      else assert.equal((await journal.prepare('SELECT header_json FROM pmb1_evidence_envelopes WHERE envelope_id=?').bind(first.envelope).first()).header_json,first.headerRaw);
    }
    assert.equal(outbound,0);writeFileSync(join(receipt,'private-main-rpc.json'),JSON.stringify({sameWorkerArtifact:true,sameJournalAndConfiguration:true,intervals:2,
      qualifiedSourceModelOnly:true,full65Domain:true,rawAcquisitions:0,actualQualification:false}));
  }finally{await mf.dispose();}
});
