// SOURCE/synthetic only. Expected metadata is retained separately from adapter.
import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {BOUNDARY,REVISION,captureSupportedBoundary,BoundaryRefused} from './object-kv-interface.ts';
import {readLocalSupportedBoundary,NativeReadRefused} from './native.ts';
import {PROFILE,canonical,capture,schemaSQL,storageSQL,columnsSQL,ENCODING_SQL} from '../pmb1-no-real-object-reader/reader.ts';

const bytes = path => new Uint8Array(readFileSync(new URL(path,import.meta.url)));
const hash = value => createHash('sha256').update(value).digest('hex');
const fixture=JSON.parse(readFileSync(new URL('./expected-observable.json',import.meta.url),'utf8'));
const sourceBytes={'reader.ts':bytes('../pmb1-no-real-object-reader/reader.ts'),
  'object-kv-interface.ts':bytes('./object-kv-interface.ts'),
  'native.ts':bytes('./native.ts'),
  'expected-observable.json':bytes('./expected-observable.json'),
  'ADR0066.md':new Uint8Array(readFileSync('C:/Projects/FGA/architecture-design/docs/decisions/0066-scope-prospective-object-preservation-to-supported-state.md'))};
const sourcePins=Object.fromEntries(Object.entries(sourceBytes).map(([name,value])=>[name,hash(value)]));
const id={namespace:'synthetic-native',id:'object-one'},objectKey=canonical([id.namespace,id.id]);
const closure={interval:'synthetic-closed',start:'1',end:'99',custody:'independent-synthetic',writers:[{id:'application',epoch:'synthetic-epoch',disposition:'settled'}]};
const binding={generation:'9223372036854775807',state:'closed',writerEpoch:'synthetic-epoch',custody:closure.custody,interval:closure.interval};
const alarmKeys={invocation:'pmb1:unused-closed-alarm',sequence:'pmb1:wake-admission-sequence'};
const limits={objects:2,schema:128,tables:16,columns:64,rows:100,kv:100,bytes:4194304,calls:1000,page:2,milliseconds:30000};
const literalRows=[
  {identity:'-9223372036854775808',cells:[['integer','9223372036854775807'],['blob','00ff'],['text','nul\0é😀']]},
  {identity:'9223372036854775807',cells:[['integer','-9223372036854775808'],['blob','80'],['text','second']]},
];
async function setup() {
  const db=new DatabaseSync(':memory:');db.exec(fixture.appDDL);db.exec(fixture.automaticDDL);
  for(const guard of fixture.application.guards)db.exec(guard.sql);
  db.exec("INSERT INTO facts(rowid,value,payload,note) VALUES(-9223372036854775808,9223372036854775807,x'00ff','nul'||char(0)||'é😀'),(9223372036854775807,-9223372036854775808,x'80','second')");
  db.exec("INSERT INTO maintenance_control VALUES(1,9223372036854775807,'closed')");
  // Native hidden SQL contents are deliberately populated but inaccessible.
  db.exec("INSERT INTO __cf_kv VALUES(x'01',x'02')");
  const kv=new Map([['binary',new Uint8Array([0,255])],['exact',9223372036854775807n],
    ['pmb1:wake-admission-sequence','0'],['structured',{nested:[null,false,-0,1.5,'é']}]]);
  let fenceTime=10,hiddenReads=0,alarm=null;
  const queryLog=[], hooks={query:null,closure:null,kv:null};
  const manifest={boundary:BOUNDARY,revision:REVISION,profile:PROFILE,object:structuredClone(id),
    automatic:{name:'__cf_kv',origin:'provider-automatic-sqlite-kv',applicationDependsOnRaw:false},
    observable:structuredClone(fixture.observable),application:structuredClone(fixture.application),sourcePins:structuredClone(sourcePins)};
  const expected={...id,manifest,manifestSha2_256:hash(Buffer.from(canonical(manifest))),alarmKeys};
  const request={boundary:BOUNDARY,profile:PROFILE,expectedObjects:[expected],closure:structuredClone(closure),expectedWriterIds:['application'],
    expectedSources:structuredClone(sourcePins),sourceBytes:structuredClone(sourceBytes),fences:{[objectKey]:binding},limits:structuredClone(limits)};
  const source={
    async closure(){return hooks.closure?hooks.closure():structuredClone(closure);},
    async listObjects(after){return after===null?{entries:[id],next:objectKey}:{entries:[],next:null};},
    async readObject(_,read){db.exec('BEGIN');try{return await read({
      async query(sql){
        queryLog.push(sql);
        if(/FROM main\."__cf_kv"/i.test(sql)){hiddenReads++;throw new Error('synthetic native hidden table denial');}
        const rows=db.prepare(sql).all().map(row=>({...row}));return hooks.query?hooks.query(rows,sql):rows;
      },
      async listKV(after,limit){const entries=[...kv].sort(([a],[b])=>Buffer.compare(Buffer.from(a),Buffer.from(b))).filter(([key])=>after===null||Buffer.compare(Buffer.from(key),Buffer.from(after))>0).slice(0,limit);
        return hooks.kv?hooks.kv({entries,next:entries.at(-1)?.[0]??null}):{entries,next:entries.at(-1)?.[0]??null};},
      async getAlarm(){return alarm;},async fence(){return {...binding,observedAt:String(fenceTime++)};}
    });}finally{db.exec('ROLLBACK');}},
  };
  return {db,kv,source,request,hooks,queryLog,hiddenReads:()=>hiddenReads,setAlarm:x=>{alarm=x;},close:()=>db.close()};
}
async function run(fn=()=>{}) {const f=await setup();try{await fn(f);return await captureSupportedBoundary(f.source,f.request);}finally{f.close();}}
async function refuses(fn,reason){await assert.rejects(run(fn),error=>error instanceof BoundaryRefused&&(!reason||error.message===reason));}
function repin(object){object.manifestSha2_256=hash(Buffer.from(canonical(object.manifest)));}
function plannedReads() {
  // Fixed query plan from retained fixture columns and literal row populations;
  // never learned from the observed adapter or used as the expected state oracle.
  const reads=[schemaSQL(limits.schema),storageSQL(limits.schema),ENCODING_SQL,columnsSQL('__cf_kv',limits.columns)];
  const counts={facts:2,maintenance_control:1}, quote=name=>'"'+name.replaceAll('"','""')+'"';
  for(const [table,count] of Object.entries(counts)) {
    const columns=fixture.application.columns[table].map(row=>row.name);
    reads.push(columnsSQL(table,limits.columns));
    reads.push('SELECT '+[...columns,'rowid'].map(column=>'typeof('+quote(column)+')').join(',')+' FROM main.'+quote(table)+' LIMIT 0');
    reads.push('SELECT CAST(count(*) AS TEXT) AS row_count FROM main.'+quote(table));
    const expressions=['CAST("rowid" AS TEXT) AS row_identity'];
    columns.forEach((column,i)=>{const c=quote(column);expressions.push(`typeof(${c}) AS c${i}_type`,`CASE typeof(${c}) WHEN 'integer' THEN CAST(${c} AS TEXT) WHEN 'text' THEN hex(CAST(${c} AS BLOB)) WHEN 'blob' THEN hex(${c}) ELSE NULL END AS c${i}_value`);});
    for(let offset=0;offset<=count;){
      const n=Math.min(limits.page,count-offset);
      reads.push('SELECT '+expressions.join(',')+' FROM main.'+quote(table)+' ORDER BY "rowid"'+` LIMIT ${n===0?1:limits.page} OFFSET ${offset}`);
      if(n===0)break;offset+=n;
    }
  }
  return reads;
}
function nativeModel(f) {
  let rawHidden=0;
  const storage={sql:{exec(sql){
    if(/FROM main\."__cf_kv"/i.test(sql)){rawHidden++;throw new Error('raw hidden access');}
    const statement=f.db.prepare(sql);
    return {columnNames:statement.columns().map(c=>c.name),one(){const rows=statement.all();assert.equal(rows.length,1);return {...rows[0]};},
      *[Symbol.iterator](){for(const row of statement.iterate())yield {...row};}};
  }},async transaction(fn){f.db.exec('BEGIN');try{return await fn({async getAlarm(){return null;},
    async list(options){return new Map([...f.kv].sort(([a],[b])=>Buffer.compare(Buffer.from(a),Buffer.from(b))).filter(([key])=>!options.startAfter||Buffer.compare(Buffer.from(key),Buffer.from(options.startAfter))>0).slice(0,options.limit));}
  });}finally{f.db.exec('ROLLBACK');}}};
  return {storage,rawHidden:()=>rawHidden};
}

test('explicit successor retains full observable metadata and exact application/typed KV facts; never reads hidden SQL',async()=>{
  const f=await setup();try {
    const observed=await captureSupportedBoundary(f.source,f.request),object=observed.objects[0];
    assert.equal(observed.boundary,BOUNDARY);assert.equal(observed.revision,REVISION);assert.equal(observed.actualQualification,false);
    assert.deepEqual(object.observable,{before:fixture.observable,after:fixture.observable});
    assert.deepEqual(object.applicationCensus,{schema:fixture.application.schema,tableList:fixture.application.tableList,columns:fixture.application.columns});
    assert.deepEqual(object.tables.facts.rows,literalRows);
    assert.deepEqual(object.kv,[['binary',['uint8array','00ff']],['exact',['bigint','9223372036854775807']],
      ['pmb1:wake-admission-sequence',['text','0']],['structured',['object',[['nested',['array',[
        ['null',null],['boolean',false],['number-binary64','8000000000000000'],['number-binary64','3ff8000000000000'],['text','é']]]]]]]]);
    assert.deepEqual(Object.keys(object.tables),['facts','maintenance_control']);
    assert.equal(object.alarm.timeMs,null);assert.equal(object.alarm.sequence,'0');assert.equal(object.alarm.dispatch,null);
    assert.deepEqual(object.excluded,{name:'__cf_kv',rawSqlContents:'unobserved-unfrozen-unverified',rowids:'unobserved-unfrozen-unverified'});
    assert.equal(f.hiddenReads(),0);
    assert.ok(f.queryLog.some(sql=>sql.includes("pragma_table_xinfo('__cf_kv')")));
  }finally{f.close();}
});

test('missing/wrong boundary, manifest revision/source pin and application-dependence declaration refuse',async()=>{
  await refuses(f=>{delete f.request.boundary;},'boundary_shape');
  await refuses(f=>{f.request.boundary='pmb1-private-application-no-real-v1';},'explicit_boundary_required');
  for(const change of [m=>{m.revision='old';},m=>{m.automatic.applicationDependsOnRaw=true;},m=>{m.automatic.name='__cf_kv_other';},m=>{m.sourcePins['reader.ts']='0'.repeat(64);}])
    await refuses(f=>{change(f.request.expectedObjects[0].manifest);repin(f.request.expectedObjects[0]);},'boundary_manifest_binding');
  await refuses(f=>{f.request.expectedObjects[0].manifestSha2_256='0'.repeat(64);},'boundary_manifest_pin');
  await refuses(f=>{f.request.sourceBytes['object-kv-interface.ts'][0]^=1;});
});

test('full automatic schema/table/column metadata drift refuses before application data reads',async()=>{
  await refuses(f=>{f.hooks.query=(rows,sql)=>sql.includes('FROM main.sqlite_schema')?rows.map(r=>r.name==='__cf_kv'?{...r,sql:'changed'}:r):rows;},'observable_metadata_drift');
  await refuses(f=>{f.hooks.query=(rows,sql)=>sql.includes("pragma_table_xinfo('__cf_kv')")?rows.map(r=>({...r,type:'changed'})):rows;},'observable_metadata_drift');
  await refuses(f=>{f.hooks.query=(rows,sql)=>sql.includes('pragma_table_list')?rows.filter(r=>r.name!=='__cf_kv'):rows;},'observable_metadata_drift');
});

test('unknown automatic names and inaccessible application data do not inherit the exclusion',async()=>{
  await refuses(f=>f.db.exec('CREATE TABLE __cf_kv_new(value BLOB)'), 'observable_metadata_drift');
  await refuses(f=>{f.hooks.query=(rows,sql)=>{if(sql.includes('FROM main."facts"'))throw new Error('unavailable');return rows;};});
  await refuses(f=>{const object=f.request.expectedObjects[0];object.manifest.observable.schema.push({type:'view',name:'dependent',tbl_name:'dependent',sql:'CREATE VIEW dependent AS SELECT * FROM __cf_kv'});repin(object);},'application_hidden_dependence');
});

test('second full metadata observation detects a race after initial accepted metadata',async()=>{
  let schemas=0;
  await refuses(f=>{f.hooks.query=(rows,sql)=>sql.includes('FROM main.sqlite_schema')&&++schemas===2?rows.map(r=>r.name==='__cf_kv'?{...r,sql:'late'}:r):rows;},'observable_metadata_drift');
});

test('no-REAL guards, unsupported typed KV, native alarm order and closure gates remain unchanged',async()=>{
  await refuses(f=>{f.hooks.query=(rows,sql)=>sql.includes('AS c0_type')?rows.map(row=>({...row,c0_type:'real',c0_value:null})):rows;});
  await refuses(f=>f.kv.set('unsupported',new Date(0)));
  await refuses(f=>f.setAlarm(1700000000000));
  await refuses(f=>{f.hooks.closure=()=>({...closure,custody:'changed'});});
});

test('metadata byte/call limits and source identity remain finite/refusing',async()=>{
  await refuses(f=>{f.request.limits.bytes=128;},'boundary_metadata_byte_bound');
  await refuses(f=>{f.request.limits.calls=3;});
  await refuses(f=>{f.request.limits.tables=1;},'boundary_full_census_bound');
  await refuses(f=>{f.request.limits.columns=3;},'boundary_full_census_bound');
  await refuses(f=>{f.request.expectedObjects[0].manifest.object.id='other';repin(f.request.expectedObjects[0]);},'boundary_manifest_binding');
});

test('hidden raw content changes remain expressly outside proof, while supported KV changes remain exact',async()=>{
  const baseline=await run();
  const hidden=await run(f=>f.db.exec("UPDATE __cf_kv SET value=x'ffff'"));
  assert.deepEqual(hidden,baseline);
  const typed=await run(f=>f.kv.set('binary',new Uint8Array([255,0])));
  assert.notDeepEqual(typed.objects[0].kv,baseline.objects[0].kv);
});

test('original complete reader/default remains separate and refuses native inaccessible raw table',async()=>{
  const f=await setup();try{
    // This explicit old-domain request cannot use the amended manifest or claim
    // that its own raw hidden table/rowid requirement was fulfilled.
    const request={...f.request};delete request.boundary;
    request.expectedObjects=[{...id,guardManifest:fixture.application,guardManifestSha256:hash(Buffer.from(canonical(fixture.application))),alarmKeys}];
    await assert.rejects(capture(f.source,request));
  }finally{f.close();}
});

test('composed explicit successor and native helper retain metadata/typed facts within original 4MiB and never read hidden raw SQL',async()=>{
  const f=await setup();try{
    const native=nativeModel(f),now=Date.now();
    const closed={...closure,start:String(now-1000),end:String(now+30000)};
    f.request.closure=closed;f.source.closure=async()=>structuredClone(closed);
    const custody={generation:binding.generation,writerEpoch:binding.writerEpoch,custody:binding.custody,interval:binding.interval};
    const nativeBounds={calls:1000,rows:129,bytes:4194304,milliseconds:30000,kvAcquisitionBytes:2097152};
    const expected=f.request.expectedObjects[0];
    f.source.readObject=(_,read)=>readLocalSupportedBoundary(native.storage,plannedReads(),custody,nativeBounds,
      {manifest:expected.manifest,manifestSha2_256:expected.manifestSha2_256,sourceBytes:f.request.sourceBytes,columns:limits.columns},read);
    const result=await captureSupportedBoundary(f.source,f.request);
    assert.deepEqual(result.objects[0].observable,{before:fixture.observable,after:fixture.observable});
    assert.deepEqual(result.objects[0].tables.facts.rows,literalRows);
    assert.deepEqual(result.objects[0].kv.find(([key])=>key==='binary'),['binary',['uint8array','00ff']]);
    assert.equal(result.actualQualification,false);assert.equal(native.rawHidden(),0);
  }finally{f.close();}
});

test('native metadata successor requires exact source/manifest selector and still refuses raw hidden reads',async()=>{
  const f=await setup();try{
    const native=nativeModel(f),expected=f.request.expectedObjects[0];
    const custody={generation:binding.generation,writerEpoch:binding.writerEpoch,custody:binding.custody,interval:binding.interval};
    const nativeBounds={calls:100,rows:129,bytes:4194304,milliseconds:30000,kvAcquisitionBytes:2097152};
    const auth={manifest:expected.manifest,manifestSha2_256:expected.manifestSha2_256,sourceBytes:f.request.sourceBytes,columns:limits.columns};
    const raw='SELECT CAST(count(*) AS TEXT) n FROM main."__cf_kv"';
    await assert.rejects(readLocalSupportedBoundary(native.storage,[raw],custody,nativeBounds,auth,s=>s.query(raw)),
      e=>e instanceof NativeReadRefused&&e.message==='native_internal_sql_unavailable');
    const bad=structuredClone(auth);bad.sourceBytes['native.ts'][0]^=1;
    await assert.rejects(readLocalSupportedBoundary(native.storage,plannedReads(),custody,nativeBounds,bad,async()=>null),
      e=>e instanceof NativeReadRefused&&e.message==='native_boundary_source_binding');
    assert.equal(native.rawHidden(),0);
  }finally{f.close();}
});

test('exact separately named source manifest pins the successor and inherited contract inputs',()=>{
  const manifest=JSON.parse(readFileSync(new URL('./boundary-source-manifest.json',import.meta.url),'utf8'));
  assert.equal(manifest.boundary,BOUNDARY);assert.equal(manifest.revision,REVISION);
  assert.equal(manifest.completeNativeSource,false);assert.equal(manifest.actualQualification,false);
  for(const [path,pin] of Object.entries(manifest.inputs))
    assert.equal(hash(readFileSync(new URL('../../'+path,import.meta.url))),pin,path);
  for(const path of ['probes/pmb1-native-object-reader/object-kv-interface.ts','probes/pmb1-native-object-reader/expected-observable.json',
    'probes/pmb1-no-real-object-reader/reader.ts','../architecture-design/docs/decisions/0066-scope-prospective-object-preservation-to-supported-state.md'])
    assert.ok(manifest.inputs[path]);
});
