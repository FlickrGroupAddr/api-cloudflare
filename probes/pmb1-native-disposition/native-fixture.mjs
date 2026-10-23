// Synthetic native storage-shaped adapter. Expected metadata comes from retained
// source manifests, never discovered from the database under observation.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { acquireNativeFacts } from '../pmb1-native-object-reader/native-source.ts';
import { canonical, PROFILE, schemaSQL, storageSQL, columnsSQL, ENCODING_SQL } from '../pmb1-no-real-object-reader/reader.ts';
const hash=v=>createHash('sha256').update(v).digest('hex'),pin=v=>hash(Buffer.from(canonical(v)));
export function nativeFixture() {
  const application=JSON.parse(readFileSync(new URL('../pmb1-integer-candidate/object-guard-manifest.json',import.meta.url)));
  const old=JSON.parse(readFileSync(new URL('../pmb1-native-object-reader/expected-observable.json',import.meta.url)));
  const automatic=old.observable.schema.find(row=>row.name==='__cf_kv');
  const compare=(a,b)=>canonical([a.type,a.name,a.tbl_name])<canonical([b.type,b.name,b.tbl_name])?-1:1;
  const observable={schema:[...application.schema,automatic].sort(compare),
    tableList:[...application.tableList,old.observable.tableList.find(row=>row.name==='__cf_kv')].sort((a,b)=>a.name<b.name?-1:a.name>b.name?1:0),
    columns:{...application.columns,__cf_kv:old.observable.columns.__cf_kv}};
  const db=new DatabaseSync(':memory:');db.exec(readFileSync(new URL('../pmb1-integer-candidate/object-schema.sql',import.meta.url),'utf8'));
  db.exec(readFileSync(new URL('../pmb1-integer-candidate/object-guards.sql',import.meta.url),'utf8'));db.exec(old.automaticDDL);
  const kv=new Map([['pmb1:admission',false],['pmb1:wake-admission-sequence','0'],['pmb1:wake-revision','0']]);
  let sqlCalls=0,acquisitions=0,reservations=0,completions=0;
  const storage={sql:{exec(sql){sqlCalls++;const statement=db.prepare(sql);return {columnNames:statement.columns().map(c=>c.name),
    one(){return {...statement.get()};},*[Symbol.iterator](){for(const row of statement.iterate())yield {...row};},toArray(){return statement.all();}};}},
    async transaction(fn){db.exec('BEGIN');try{return await fn({getAlarm:async()=>null,list:async options=>new Map([...kv]
      .sort(([a],[b])=>Buffer.compare(Buffer.from(a),Buffer.from(b))).filter(([key])=>!options.startAfter||key>options.startAfter).slice(0,options.limit))});}finally{db.exec('ROLLBACK');}}};
  const id={namespace:'b'.repeat(32),id:'c'.repeat(64)},objectKey=canonical([id.namespace,id.id]);
  const sourceBytes=Object.fromEntries(['native-source.ts','native-owner.ts','native-control.ts','native.ts','object-kv-interface.ts'].map(name=>[name,new Uint8Array(readFileSync(new URL('../pmb1-native-object-reader/'+name,import.meta.url)))]));
  sourceBytes['reader.ts']=new Uint8Array(readFileSync(new URL('../pmb1-no-real-object-reader/reader.ts',import.meta.url)));
  sourceBytes['ADR0066.md']=new Uint8Array(readFileSync('C:/Projects/FGA/architecture-design/docs/decisions/0066-scope-prospective-object-preservation-to-supported-state.md'));
  const sourcePins=Object.fromEntries(Object.entries(sourceBytes).map(([name,value])=>[name,hash(value)]));
  const now=Date.now(),closure={interval:'synthetic-closed',start:String(now-1000),end:String(now+30000),custody:'independent-synthetic',writers:[{id:'application',epoch:'synthetic-epoch',disposition:'settled'}]};
  const limits={objects:2,schema:512,tables:16,columns:64,rows:100,kv:100,bytes:4194304,calls:2000,page:2,milliseconds:1000};
  const manifest={boundary:'pmb1-private-object-kv-interface-v1',revision:'adr0066-object-kv-interface-source-v1',profile:PROFILE,object:id,
    automatic:{name:'__cf_kv',origin:'provider-automatic-sqlite-kv',applicationDependsOnRaw:false},observable,application,sourcePins};
  const request={boundary:manifest.boundary,profile:PROFILE,expectedObjects:[{...id,manifest,manifestSha2_256:pin(manifest),alarmKeys:{invocation:'pmb1:unused',sequence:'pmb1:wake-admission-sequence'}}],
    closure,expectedWriterIds:['application'],expectedSources:sourcePins,sourceBytes,fences:{[objectKey]:{generation:'1',state:'closed',writerEpoch:'synthetic-epoch',custody:closure.custody,interval:closure.interval}},limits};
  const approvedReads=[schemaSQL(limits.schema),storageSQL(limits.schema),ENCODING_SQL,columnsSQL('__cf_kv',limits.columns)];
  const quote=s=>'"'+s.replaceAll('"','""')+'"';
  for(const table of Object.keys(application.cells).sort()) {
    const cols=application.columns[table].map(c=>c.name),count=table==='maintenance_control'?1:0;
    approvedReads.push(columnsSQL(table,limits.columns));
    approvedReads.push('SELECT '+[...cols,'rowid'].map(c=>'typeof('+quote(c)+')').join(',')+' FROM main.'+quote(table)+' LIMIT 0');
    approvedReads.push('SELECT CAST(count(*) AS TEXT) AS row_count FROM main.'+quote(table));
    const expressions=['CAST("rowid" AS TEXT) AS row_identity'];
    cols.forEach((c,i)=>{const q=quote(c);expressions.push(`typeof(${q}) AS c${i}_type`,`CASE typeof(${q}) WHEN 'integer' THEN CAST(${q} AS TEXT) WHEN 'text' THEN hex(CAST(${q} AS BLOB)) WHEN 'blob' THEN hex(${q}) ELSE NULL END AS c${i}_value`);});
    for(let offset=0;offset<=count;){const n=Math.min(limits.page,count-offset);approvedReads.push('SELECT '+expressions.join(',')+' FROM main.'+quote(table)+' ORDER BY "rowid"'+` LIMIT ${n===0?1:limits.page} OFFSET ${offset}`);if(!n)break;offset+=n;}
  }
  const {sourceBytes:ignored,...wireRequest}=request;
  const packet={schema:'pmb1-private-native-owner-packet-v1',approvedReads,maximumEvents:256,request:wireRequest,
    sourceHex:Object.fromEntries(Object.entries(sourceBytes).map(([name,value])=>[name,Buffer.from(value).toString('hex')]))};
  const population={accountId:'a'.repeat(32),accountNamespaces:[{id:id.namespace,class:'NativeCaptureOwner',name:'synthetic',script:'synthetic',use_sqlite:true},
    {id:'e'.repeat(32),class:'NativeCaptureControl',name:'external-control',script:'synthetic',use_sqlite:true}],objects:{[id.namespace]:[{id:id.id,hasStoredData:true}]}};
  const census={schema:'pmb1-native-census-observation-v1',completeSnapshot:false,actualQualification:false,...population,calls:2,bytes:1024};
  const input={control:{namespace:'e'.repeat(32),id:'f'.repeat(64),packetSha2_256:'2'.repeat(64)},request,expectedPopulation:population,
    expectedPopulationSha2_256:pin(population),inventoryProvenanceSha2_256:'1'.repeat(64),census,censusSha2_256:pin(census),packets:[{packet,sha2_256:pin(packet)}]};
  const control={idFromString:id=>id,get:()=>({reserve:async(controlSha2_256,namespace,id,packetSha2_256)=>{reservations++;return {controlSha2_256,namespace,id,packetSha2_256};},complete:async()=>{completions++;}})};
  const bindings={[id.namespace]:{idFromString:id=>id,get:()=>({acquire:async expected=>{acquisitions++;return acquireNativeFacts(storage,id.namespace,id.id,packet,expected);}})}};
  return {id,input,bindings,control,storage,kv,db,counts:()=>({sqlCalls,acquisitions,reservations,completions}),close:()=>db.close()};
}
