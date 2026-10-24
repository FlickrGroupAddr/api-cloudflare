// MIT License; copyright 2026 Terry Ott.
// SOURCE-only native composition. No caller-supplied runtime, credential,
// binding, endpoint, fixture path, adapter or qualification toggle is accepted.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {URL,fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {publishReviewedEvidence, type OperatorPublicationAuthority} from '../pmb1-runtime-evidence/operator.ts';
import {preparePublication, publicationReadback, type FixedStatement} from '../pmb1-runtime-evidence/publication-plan.ts';
import {encoded, requiredCharge, type EvidenceReference} from '../pmb1-runtime-evidence/ledger.ts';
import {consumeRuntimeFacts} from '../pmb1-retained-integration/runtime_facts.ts';
import {createFreshNativeSource} from '../pmb1-fresh-native-capture/source.ts';
import {OwningPartitionRuntime} from '../pmb1-fresh-native-capture/owning-core.ts';
import {PrivateMainRuntime} from '../pmb1-fresh-native-capture/main-private-core.ts';
import {closedRestorationCheck} from '../pmb1-retained-integration/ordinary.ts';
import {PartitionMaintenance} from '../../src/partition_maintenance.ts';
import {NativePartitionDisposition} from '../pmb1-native-disposition/partition.ts';
import {Pmb1NativeWakeup} from '../pmb1-native-wakeup/candidate.ts';
import {invokeInheritedNativeStep,executeReviewedNativeProgram,nativeProgramDigest,nativePacketDigest,
  type ReviewedNativeFacts,type NativeCost,type NativeObservedLeaf} from './native_dispatch.ts';
import {captureSupportedBoundary} from '../pmb1-native-object-reader/object-kv-interface.ts';
import type {FreshRetainedEnvironment} from '../pmb1-retained-integration/fresh_composition.ts';

export const actualDispatchEnabled = false as const;
const hash = (value:string) => createHash('sha256').update(value).digest('hex');
const fail = (reason:string):never => {throw Error(reason);};
export interface SourceTraceLeaf {
  ordinal:number; parent:string; method:string; resource:string; requestDigest:string;
  statements:number; effectEvents:number; retainedRequestBytes:number; retainedResponseBytes:number;
  // Serialized synthetic facts are measurable; actual SDK wire/framing is not.
  wireBytes:'UNKNOWN'; status:'confirmed'|'unknown';
}
interface Trace {leaves:SourceTraceLeaf[]; active:string; spent:Set<string>;}
function syntheticText(value:unknown):string{
  // SOURCE fixture cursors use SQLite null-prototype rows. Normalize only the
  // fixed harness's retained facts before the inherited canonical JSON codec.
  return encoded(JSON.parse(JSON.stringify(value,(_key,v)=>typeof v==='bigint'
    ?{sourceType:'bigint',decimal:v.toString()}:v instanceof Map?{sourceType:'map',entries:[...v]}:v)));
}
function reserve(trace:Trace,method:string,resource:string,request:unknown,statements=0):SourceTraceLeaf{
  const text=syntheticText(request),ordinal=trace.leaves.length+1,key=trace.active+'/'+ordinal;
  if(trace.spent.has(key))fail('source_leaf_no_replay');trace.spent.add(key);
  const leaf:SourceTraceLeaf={ordinal,parent:trace.active,method,resource,requestDigest:hash(text),statements,
    effectEvents:0,retainedRequestBytes:Buffer.byteLength(text),retainedResponseBytes:0,wireBytes:'UNKNOWN',status:'unknown'};
  trace.leaves.push(leaf);return leaf;
}
function finish(leaf:SourceTraceLeaf,response:unknown,effects=0){
  leaf.retainedResponseBytes=Buffer.byteLength(syntheticText(response));leaf.effectEvents=effects;leaf.status='confirmed';
}
function sqliteChanges(trace:Trace,raw:any,resource:string):number{
  const leaf=reserve(trace,'metering.sql.exec',resource,{sql:'SELECT total_changes() n'},1);
  const value=Number(raw.prepare('SELECT total_changes() n').get().n);finish(leaf,{n:String(value)});return value;
}

/** Actual public inherited pure preparation, not caller-retained SQL. This
 * four-batch plan is also used to fence the synthetic execution BEFORE each
 * inherited operator call crosses its native D1 batch boundary. */
export async function publicationBatches(...args:Parameters<typeof preparePublication>):Promise<readonly (readonly FixedStatement[])[]>{
  const prepared=await preparePublication(...args),readback=publicationReadback(prepared);
  return Object.freeze([prepared.statements,Object.freeze([readback[0]!]),Object.freeze(readback.slice(1)),Object.freeze([readback[3]!])]);
}

/** Strictly default-disabled actual entry. A future SOURCE revision must supply
 * genuine exact-packet qualification; caller arguments cannot switch this on. */
export function executeNative():never{return fail('provider_dispatch_disabled');}

/** Execute existing inherited code against ONLY the existing controlled
 * in-memory SQLite synthetic harness. That harness denies fetch, socket connect
 * and DNS. No external port is accepted. This measures SOURCE leaf wiring and
 * native-like typed SQL/KV/alarm observation; it never passes actual fit/custody.
 * One call creates one fresh invented fixture and destroys only that fixture.
 */
export async function rehearseInheritedSource():Promise<{
  scope:'SOURCE_SYNTHETIC_WIRING_ONLY';qualification:'NO_GO';actualDispatchEnabled:false;
  publicationBatches:number;publicationStatements:number;objects:number;domainTables:number;
  mainSequence:readonly string[];ownerControls:readonly string[];trace:readonly SourceTraceLeaf[];
  closedSourcePreflight:Readonly<Record<string,unknown>>;
  actualWire:'UNKNOWN';actualEffects:'UNKNOWN';actualHeadroom:'UNKNOWN';
}>{
  // Fixed public SOURCE modules; dynamic import is needed because inherited
  // fixtures are JavaScript rather than a separately typed runtime package.
  const fixtureModule=await import(new URL('../pmb1-native-disposition/fixture.mjs',import.meta.url).href);
  const freshModule=await import(new URL('../pmb1-fresh-native-capture/fixture.mjs',import.meta.url).href);
  const ledgerModule=await import(new URL('../pmb1-runtime-evidence/fixture.mjs',import.meta.url).href);
  const contract=JSON.parse(readFileSync(new URL('../pmb1-retained-integration/source-contract.json',import.meta.url),'utf8'));
  const reference:EvidenceReference={databaseId:'aaaaaaaa-0000-4000-8000-000000000000',envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:'native-preservation'};
  const f=freshModule.freshFixture(reference,contract.sourceContextSha2_256);
  let state:any,domain:any;
  const trace:Trace={leaves:[],active:'publication',spent:new Set()};
  try{
    const keys:string[]=f.objects.map((o:{namespace:string;id:string})=>o.namespace+'/'+o.id);
    const nativeBytes=f.input.request.limits.bytes*keys.length;
    state=await ledgerModule.setupLedger(f.wire,keys,{publish:false,now:Date.now(),reference,
      binding:{databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,
        lifecycle:f.f.config.binding.lifecycle,generation:f.f.config.binding.generation,
        nativeSourceDigest:f.input.request.expectedSources['fresh-source.ts'],ownerSourceDigest:f.input.request.expectedSources['owning-partition.ts']},
      header:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},
      review:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},
      allocation:{maxNativeBytes:nativeBytes,maxAggregateBytes:requiredCharge(encoded(f.wire).length,keys.length,nativeBytes).aggregate}});
    const expected=await publicationBatches(state.handoff,state.binding,state.provenance,state.allocation,state.clock.now);
    let batchIndex=0,pending:SourceTraceLeaf|undefined,effectStart=0;
    const changes=()=>sqliteChanges(trace,state.db.raw,'evidence-d1');
    state.db.beforeBatch=async(_index:number,statements:FixedStatement[])=>{
      const fixed=statements.map(({sql,args})=>({sql,args}));
      // Exact immutable SQL AND argument identity; even a correctly sized
      // substituted batch refuses before the inherited fixture executes it.
      if(trace.active==='publication' && encoded(fixed)!==encoded(expected[batchIndex++]))fail('source_publication_tree_drift');
      pending=reserve(trace,'D1.session.batch','evidence-d1',fixed,fixed.length);effectStart=changes();
    };
    state.db.afterBatch=async(_index:number,_statements:FixedStatement[],results:unknown)=>{
      if(!pending)fail('source_unreserved_batch');finish(pending!,results,changes()-effectStart);pending=undefined;
    };
    const authority:OperatorPublicationAuthority={schema:'pmb1-qualified-native-d1-operator-publication-v1',databaseId:reference.databaseId,
      envelopeId:reference.envelopeId,operationId:crypto.randomUUID(),qualificationRecord:'a'.repeat(64),
      operatorEnvironmentRecord:'b'.repeat(64),bindingHolderRecord:'c'.repeat(64),credentialCustodyRecord:'d'.repeat(64),
      publisherSourceDigest:state.provenance.publisherSourceDigest,rootRecord:state.header.provenance.rootRecord,
      reviewRecord:state.header.provenance.reviewRecord,retainedEnvelopeDigest:state.handoff.retainedEnvelopeDigest,
      attemptLedgerRecord:state.provenance.operatorAttemptLedgerRecord,attemptState:'allocated-unused',
      fromMs:state.header.fromMs,throughMs:state.header.throughMs,
      allocation:{maxRequests:4,maxStatements:23,maxAcquiredBytes:state.header.payloadBytes*6+65536,maxAggregateBytes:67108864}};
    const published=await invokeInheritedNativeStep({owners:new Map()},
      {kind:'publication',database:state.db,prepared:state.prepared,authority,now:()=>state.clock.now}) as Awaited<ReturnType<typeof publishReviewedEvidence>>;
    if(published.outcome!=='published'||batchIndex!==4)fail('source_publication_trace_incomplete');
    const publicationStatements=trace.leaves.filter(l=>l.method==='D1.session.batch').reduce((n,l)=>n+l.statements,0);
    const cores=new Map<string,OwningPartitionRuntime>();
    const namespace=f.objects[0].namespace;
    const binding={idFromString:(id:string)=>id,get:(id:string)=>{
      const core=cores.get(id);if(!core)fail('source_population_lookup');
      return {acquireFresh:async(ref:EvidenceReference,pin:string)=>{
        const leaf=reserve(trace,'PartitionWorker.acquireFresh',namespace+'/'+id,{ref,pin});
        const result=await core!.acquireFresh(ref,pin);finish(leaf,result);return result;
      }};
    }};
    domain=new fixtureModule.LocalD1();
    const originalDomainPrepare=domain.prepare.bind(domain);
    domain.prepare=(sql:string)=>{
      const statement=originalDomainPrepare(sql);
      const originalAll=statement.all.bind(statement);
      statement.all=async()=>{
        const leaf=reserve(trace,'D1.prepare.all','domain-d1',{sql,args:statement.args},1);
        const result=await originalAll();finish(leaf,result);return result;
      };return statement;
    };
    const originalPrepare=state.db.prepare.bind(state.db);
    state.db.prepare=(sql:string)=>{
      const statement=originalPrepare(sql);
      statement.all=async()=>{
        const leaf=reserve(trace,'D1.prepare.all','main-journal',{sql,args:statement.args},1);
        const before=changes(),rows=state.db.raw.prepare(sql).all(...statement.args);
        const result={success:true,results:rows};finish(leaf,result,changes()-before);return result;
      };return statement;
    };
    const env={COORD:binding,PMB1_MAIN_JOURNAL:state.db,DB:domain,
      PMB1_VERSION_METADATA:{id:state.binding.immutableVersion}} as unknown as FreshRetainedEnvironment;
    for(const object of f.objects){
      const original=f.stores.get(object.id),native=f.f.native.id.id===object.id?f.f.native:f.second;
      const sql={exec(statement:string,...args:unknown[]){
        const leaf=reserve(trace,'storage.sql.exec',namespace+'/'+object.id,{statement,args},1);
        const before=sqliteChanges(trace,native.db,namespace+'/'+object.id);
        const result=original.sql.exec(statement,...args);
        // The inherited synthetic cursor re-executes on every view. Materialize
        // ONCE, then provide the native cursor's retained views from these rows;
        // trace observation must never introduce an uncounted second SQL read.
        const rows=result.toArray(),columnNames=result.columnNames;
        finish(leaf,{columnNames,rows},sqliteChanges(trace,native.db,namespace+'/'+object.id)-before);
        return {columnNames,toArray:()=>rows,one:()=>{if(rows.length!==1)fail('source_cursor_not_one');return rows[0];},
          *[Symbol.iterator](){yield* rows;}};
      }};
      const storage={sql,transaction:async(fn:(tx:DurableObjectTransaction)=>Promise<unknown>)=>{
        const transaction=reserve(trace,'storage.transaction',namespace+'/'+object.id,{});
        const value=await original.transaction(async(tx:Record<string,Function>)=>{
          const observed:Record<string,Function>={};
          for(const method of ['get','put','delete','list','getAlarm','setAlarm','deleteAlarm']){
            observed[method]=async(...args:unknown[])=>{
              const leaf=reserve(trace,'transaction.'+method,namespace+'/'+object.id,args);
              if(typeof tx[method]!=='function')fail('source_unsupported_storage_method');
              const result=await tx[method](...args);
              finish(leaf,result===undefined?null:result instanceof Map?[...result]:result,
                ['put','delete','setAlarm','deleteAlarm'].includes(method)?1:0);return result;
            };
          }
          return fn(observed as unknown as DurableObjectTransaction);
        });finish(transaction,null);return value;
      }} as unknown as DurableObjectStorage;
      cores.set(object.id,new OwningPartitionRuntime({id:{toString:()=>object.id},storage} as DurableObjectState,env,
        ()=>({ledger:state.ledger(),namespace,operation:reference.operation,
          databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,immutableVersion:state.binding.immutableVersion})));
    }
    trace.active='source-reservation';
    const ledger=state.ledger(),facts=await consumeRuntimeFacts({ledger,namespace,operation:reference.operation,
      databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,immutableVersion:state.binding.immutableVersion});
    trace.active='complete-two-object-capture';
    const capture=await invokeInheritedNativeStep({owners:cores},
      {kind:'capture',input:facts.trusted.source(),namespaces:{[namespace]:binding} as never,ledger,envelope:facts.envelope}) as Awaited<ReturnType<typeof captureSupportedBoundary>>;
    if(capture.objects.length!==keys.length||trace.leaves.some(l=>l.status!=='confirmed'))fail('source_native_trace_incomplete');
    // Private main uses the actual completed native SOURCE runtime, an exact
    // target read, admission stop, a DISTINCT protected evidence-use publication
    // and complete 65-table assessment. Raw capture slots cannot stand in for it.
    trace.active='main-current';
    const mainAuthority=(operation:string,selectedLedger=state.ledger())=>({ledger:selectedLedger,namespace,operation,
      databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,immutableVersion:state.binding.immutableVersion});
    const mainSequence:string[]=[];
    const currentCore=new PrivateMainRuntime(env,()=>mainAuthority('main-assess'));
    const current=await invokeInheritedNativeStep({main:currentCore,owners:cores},
      {kind:'main-current',domainDatabaseId:f.f.config.domainDatabaseId,operationId:crypto.randomUUID()}) as Awaited<ReturnType<PrivateMainRuntime['currentMain']>>;
    mainSequence.push('currentMain');trace.active='main-stop';
    await invokeInheritedNativeStep({main:currentCore,owners:cores},{kind:'main-stop',target:current.target,operationId:crypto.randomUUID()});mainSequence.push('stopAdmission');
    trace.active='main-evidence-use-publication';
    const use=await freshModule.prepareModelEvidenceUse(state,f,'main-assess');
    trace.active='main-assess';
    const main=new PrivateMainRuntime(env,()=>mainAuthority('main-assess',use.state.ledger()));
    const assessment=await invokeInheritedNativeStep({main,owners:cores},{kind:'main-assess',target:current.target,operationId:crypto.randomUUID()}) as Awaited<ReturnType<PrivateMainRuntime['assessStopped']>>;mainSequence.push('assessStopped');
    if(assessment.status!=='complete-supported')fail('source_main_assessment_incomplete');
    const domainTables=new Set<string>((domain.calls as string[]).flatMap(sql=>[...sql.matchAll(/FROM "([^"]+)" LIMIT 10001/g)].map(m=>m[1]!))).size;
    if(domainTables!==65)fail('source_domain_truncated');
    // Separate same-owner control fixture transition. This is invented setup,
    // counted explicitly, and is never a live maintenance normalization path.
    const first=f.objects[0],native=f.f.native,kv=native.kv;
    trace.active='synthetic-control-fixture-setup';
    const setup=reserve(trace,'synthetic-fixture.sql','first-owned-object',
      {sql:"UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1"},1);
    native.db.exec("UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");finish(setup,null,1);
    const setupKV=reserve(trace,'synthetic-fixture.kv','first-owned-object',{key:'pmb1:admission',value:true});kv.set('pmb1:admission',true);finish(setupKV,null,1);
    const storage={sql:{exec(sql:string,...args:unknown[]){
      const leaf=reserve(trace,'storage.sql.exec',namespace+'/'+first.id,{sql,args},1),before=sqliteChanges(trace,native.db,namespace+'/'+first.id);
      const statement=native.db.prepare(sql),columnNames=statement.columns().map((c:{name:string})=>c.name),rows=statement.all(...args);
      finish(leaf,{columnNames,rows},sqliteChanges(trace,native.db,namespace+'/'+first.id)-before);
      return{columnNames,toArray:()=>rows,one:()=>rows[0],*[Symbol.iterator](){yield* rows;}};
    }},transaction:async(fn:(tx:DurableObjectTransaction)=>Promise<unknown>)=>{
      const leaf=reserve(trace,'storage.transaction',namespace+'/'+first.id,{}),old=structuredClone(kv);
      native.db.exec('BEGIN');
      const tx={get:async(key:string)=>{const l=reserve(trace,'transaction.get',first.id,{key}),v=kv.get(key);finish(l,v??null);return v;},
        put:async(key:string,value:unknown)=>{const l=reserve(trace,'transaction.put',first.id,{key,value});kv.set(key,value);finish(l,null,1);},
        delete:async(key:string)=>{const l=reserve(trace,'transaction.delete',first.id,{key}),v=kv.delete(key);finish(l,v,v?1:0);return v;},
        getAlarm:async()=>{const l=reserve(trace,'transaction.getAlarm',first.id,{});finish(l,null);return null;},
        deleteAlarm:async()=>{const l=reserve(trace,'transaction.deleteAlarm',first.id,{});finish(l,null,1);}};
      try{const value=await fn(tx as unknown as DurableObjectTransaction);native.db.exec('COMMIT');finish(leaf,null);return value;}
      catch(error){native.db.exec('ROLLBACK');kv.clear();for(const[k,v]of old)kv.set(k,v);throw error;}
    }} as unknown as DurableObjectStorage;
    const owned=new OwningPartitionRuntime({id:{toString:()=>first.id},storage} as DurableObjectState,env,()=>mainAuthority(reference.operation));
    const ownerControls:string[]=[];trace.active='owner-stop';
    const ownedBindings={main,owners:new Map([[namespace+'/'+first.id,owned]])};
    await invokeInheritedNativeStep(ownedBindings,{kind:'owner-stop',resource:namespace+'/'+first.id,generation:'2',operationId:crypto.randomUUID()});ownerControls.push('maintenanceStop');
    trace.active='owner-close';await invokeInheritedNativeStep(ownedBindings,{kind:'owner-close',resource:namespace+'/'+first.id,generation:'2',operationId:crypto.randomUUID()});ownerControls.push('maintenanceClose');
    trace.active='closed-source-preflight';
    const mainReadback=await invokeInheritedNativeStep({main:currentCore,owners:cores},{kind:'main-current',domainDatabaseId:f.f.config.domainDatabaseId,operationId:crypto.randomUUID()});
    const ownerReadback=await storage.transaction(async tx=>({
      rows:storage.sql.exec('SELECT CAST(generation AS TEXT) generation,state FROM maintenance_control').toArray().map(r=>({...r})),
      admission:await tx.get('pmb1:admission')}));
    const closedReadback=encoded({main:mainReadback,owner:ownerReadback});
    const observedAtMs=Date.now();
    const closedSourcePreflight=Object.freeze({scope:'SOURCE_SYNTHETIC_WIRING_ONLY',actualQualification:false,
      sourceContext:contract.sourceContextSha2_256,moduleSourceSha2_256:hash(readFileSync(new URL(import.meta.url),'utf8')),
      resource:namespace+'/'+first.id,retainedVersion:state.binding.immutableVersion,
      observedAtMs,throughMs:Math.min(observedAtMs+60000,Number(f.input.request.closure.end)),
      readbackText:closedReadback,readbackSha2_256:hash(closedReadback),custody:'UNKNOWN',allWriterQualification:'UNKNOWN'});
    fixtureModule.assertNoOutbound();
    return Object.freeze({scope:'SOURCE_SYNTHETIC_WIRING_ONLY',qualification:'NO_GO',actualDispatchEnabled:false,
      publicationBatches:batchIndex,publicationStatements,objects:capture.objects.length,domainTables,
      mainSequence:Object.freeze(mainSequence),ownerControls:Object.freeze(ownerControls),
      closedSourcePreflight,
      trace:Object.freeze(trace.leaves.map(l=>Object.freeze({...l}))),actualWire:'UNKNOWN',actualEffects:'UNKNOWN',actualHeadroom:'UNKNOWN'});
  }finally{domain?.close();state?.close();f.close();fixtureModule.assertNoOutbound();}
}

/** Invoke the exact inherited ordinary closed authenticated request handler
 * against a separately created, normally guarded, synthetic closed D1 fixture.
 * This is local handler wiring, not an HTTPS edge/client qualification. */
export async function rehearseClosedRestorationCheck():Promise<{
  scope:'SOURCE_SYNTHETIC_WIRING_ONLY';qualification:'NO_GO';status:number;
  bodyText:string;headers:Readonly<Record<string,string|null>>;bodyDigest:string;trace:readonly SourceTraceLeaf[];actualEdge:'UNKNOWN';
}>{
  const fixture=await import(new URL('../pmb1-native-disposition/fixture.mjs',import.meta.url).href);
  const domain=new fixture.LocalD1(),trace:Trace={leaves:[],active:'closed-authenticated-restoration',spent:new Set()};
  const token=Array(13).fill('0000').join('-');
  try{
    const seed=["UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1",
      "BEGIN","INSERT INTO fga_users VALUES('user')",
      "INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','user','lrc_plugin','active',7,'version')",
      "INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)",
      "COMMIT","UPDATE maintenance_control SET generation=3,state='closed' WHERE singleton_id=1"];
    for(const sql of seed){
      const args=sql.includes('credential_digest')?[hash(token)]:[],leaf=reserve(trace,'synthetic-fixture.sql','closed-auth-domain',{sql,args},1);
      domain.db.prepare(sql).run(...args);finish(leaf,null,sql.startsWith('INSERT')||sql.startsWith('UPDATE')?1:0);
    }
    const prepare=domain.prepare.bind(domain);
    domain.prepare=(sql:string)=>{
      const statement=prepare(sql),all=statement.all.bind(statement);
      statement.all=async()=>{const leaf=reserve(trace,'D1.prepare.all','closed-auth-domain',{sql,args:statement.args},1);
        const result=await all();finish(leaf,result);return result;};return statement;
    };
    const request=new Request('https://synthetic.invalid/api/v001/installations/current',{headers:{Authorization:'Bearer '+token}});
    const response=await invokeInheritedNativeStep({owners:new Map()},{kind:'ordinary',request,database:domain,readEnabled:'1'}) as Response;
    const body=await response.text();
    if(response.status!==200||response.headers.get('cache-control')!=='no-store'
      ||response.headers.get('x-content-type-options')!=='nosniff'||response.headers.get('referrer-policy')!=='no-referrer')fail('source_closed_auth_failed');
    const expected={schemaVersion:1,installationId:'installation',installationRevision:7,installationState:'active',presentedCredentialState:'current'};
    if(encoded(JSON.parse(body))!==encoded(expected))fail('source_closed_auth_body');
    fixture.assertNoOutbound();
    return Object.freeze({scope:'SOURCE_SYNTHETIC_WIRING_ONLY',qualification:'NO_GO',status:response.status,
      bodyText:body,headers:Object.freeze({'cache-control':response.headers.get('cache-control'),
        'x-content-type-options':response.headers.get('x-content-type-options'),'referrer-policy':response.headers.get('referrer-policy'),
        'content-type':response.headers.get('content-type')}),
      bodyDigest:hash(body),trace:Object.freeze(trace.leaves.map(l=>Object.freeze({...l}))),actualEdge:'UNKNOWN'});
  }finally{domain.close();fixture.assertNoOutbound();}
}

export interface NativeFailureTrace {
  caseNumber:number;scope:'SOURCE_SYNTHETIC_WIRING_ONLY';qualification:'NO_GO';
  outcome:'closed-refusal'|'known-violation-detected';reason:string;
  trace:readonly SourceTraceLeaf[];actualWire:'UNKNOWN';actualCustody:'UNKNOWN';
  controlAttempts:readonly Readonly<{method:string;generation:string;outcome:'refused'}>[];
  restoration?:Readonly<Record<string,unknown>>;
}
export interface SourceTestTools {uvExecutable:string;cacheDirectory:string;}
function sourceProviderRestore(tools:SourceTestTools):Record<string,unknown>{
  const version=spawnSync(tools.uvExecutable,['--version'],{encoding:'utf8',windowsHide:true});
  if(version.status!==0||!/^uv 0\.12\.5(?: \([^\r\n]*\))?$/.test(version.stdout.trim()))throw Error('source_pinned_uv_required');
  // Fixed SOURCE-only script. Capture the existing invented provider object to
  // independently inspect its actual model deployment/readback after SAME real
  // SDK code ran; no live provider/credential/transport can be passed to it.
  const script=`import json,sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path('probes/pmb1-finite-runner').resolve()))\nimport native_operator as op\nheld=[]\noriginal=op.InventedProviderIO.__init__\ndef fixture_init(self,*args,**kwargs):\n original(self,*args,**kwargs)\n held.append(self)\nop.InventedProviderIO.__init__=fixture_init\nr=op.exercise_synthetic('restore')\nio=held[0]\nx=io.inputs\nprint(json.dumps({'scope':'SOURCE_PROVIDER_RESTORE_ONLY','outcome':r.outcome,'requests':r.requests,'mutationRequests':r.mutation_requests,'keys':r.keys,'expectedRetainedVersion':x.retained_version_id,'deployment':io.deployments,'deploymentPosts':io.deployment_posts,'worker':io.workers[x.worker_id],'actualQualification':False},sort_keys=True))\n`;
  const result=spawnSync(tools.uvExecutable,['--cache-dir',tools.cacheDirectory,'run','--frozen','--no-sync','python','-B','-c',script],{
    cwd:fileURLToPath(new URL('../../',import.meta.url)),encoding:'utf8',windowsHide:true,timeout:60000,maxBuffer:1048576});
  if(result.status!==0)throw Error('source_provider_restore_unknown');
  let report:any;try{report=JSON.parse(result.stdout);}catch{throw Error('source_provider_restore_malformed');}
  if(report.scope!=='SOURCE_PROVIDER_RESTORE_ONLY'||report.actualQualification!==false||report.outcome!=='synthetic_complete'
    ||report.deploymentPosts!==2||report.deployment?.versions?.length!==1
    ||report.deployment.versions[0].version_id!==report.expectedRetainedVersion||report.deployment.versions[0].percentage!==100
    ||report.worker?.subdomain?.enabled!==false||!Array.isArray(report.keys)
    ||!['restore:deploy','restore:deployment:current','restore:version','restore:origin:subdomain'].every(k=>report.keys.includes(k)))
    throw Error('source_exact_retained_restore_readback_refused');
  return report;
}

/** Source-owned case branches use actual inherited control/guard/ledger code.
 * There is no fault callback, supplied receipt flag or replaceable adapter. Each
 * case gets a fresh existing in-memory fixture; these are not campaign slots.
 * All native writes below are explicit invented fixture/control/challenge work.
 */
export async function rehearseNativeFailure(caseNumber:number,sourceTools?:SourceTestTools):Promise<NativeFailureTrace>{
  if(!Number.isSafeInteger(caseNumber)||caseNumber<2||caseNumber>12)fail('source_failure_case_inventory');
  const fixtures=await import(new URL('../pmb1-native-disposition/fixture.mjs',import.meta.url).href);
  const nativeModule=await import(new URL('../pmb1-native-disposition/native-fixture.mjs',import.meta.url).href);
  const ledgerModule=await import(new URL('../pmb1-runtime-evidence/fixture.mjs',import.meta.url).href);
  const native=nativeModule.nativeFixture(),domain=new fixtures.LocalD1();
  const state=await ledgerModule.setupLedger({},['namespace/object-a']);
  const trace:Trace={leaves:[],active:'case'+caseNumber+'.fixture',spent:new Set()};
  let pendingBatch:SourceTraceLeaf|undefined;
  state.db.beforeBatch=async(_index:number,statements:FixedStatement[])=>{
    pendingBatch=reserve(trace,'D1.session.batch','evidence-d1',statements.map(({sql,args})=>({sql,args})),statements.length);
  };
  state.db.afterBatch=async(_index:number,_statements:FixedStatement[],results:unknown)=>{
    if(!pendingBatch)fail('source_unreserved_batch');finish(pendingBatch!,results);pendingBatch=undefined;
  };
  let reason='',outcome:NativeFailureTrace['outcome']='closed-refusal';
  let restoration:Readonly<Record<string,unknown>>|undefined;
  const controlAttempts:{method:string;generation:string;outcome:'refused'}[]=[];
  function sql(raw:any,resource:string,statement:string,args:unknown[]=[],denied=false){
    const leaf=reserve(trace,'storage.sql.exec',resource,{sql:statement,args},1),before=sqliteChanges(trace,raw,resource);
    try{const prepared=raw.prepare(statement),rows=prepared.all(...args),effects=sqliteChanges(trace,raw,resource)-before;
      finish(leaf,rows,effects);if(denied)fail('source_guard_unexpectedly_allowed');return rows;}
    catch(error){
      if(denied&&error instanceof Error&&/maintenance_closed|fenced|closed/.test(error.message)){
        finish(leaf,{sourceRefusal:'closed'},sqliteChanges(trace,raw,resource)-before);return [];
      }throw error;
    }
  }
  const resource=native.id.namespace+'/'+native.id.id,kv=native.kv;
  const storage={sql:{exec(statement:string,...args:unknown[]){
    const rows=sql(native.db,resource,statement,args),columnNames=native.db.prepare(statement).columns().map((c:{name:string})=>c.name);
    return{columnNames,toArray:()=>rows,one:()=>{if(rows.length!==1)fail('source_cursor_not_one');return rows[0];},*[Symbol.iterator](){yield* rows;}};
  }},transaction:async(fn:(tx:DurableObjectTransaction)=>Promise<unknown>)=>{
    const leaf=reserve(trace,'storage.transaction',resource,{}),old=structuredClone(kv);native.db.exec('BEGIN');
    const tx={get:async(key:string)=>{const l=reserve(trace,'transaction.get',resource,{key}),v=kv.get(key);finish(l,v??null);return v;},
      put:async(key:string,value:unknown)=>{const l=reserve(trace,'transaction.put',resource,{key,value});kv.set(key,value);finish(l,null,1);},
      delete:async(key:string)=>{const l=reserve(trace,'transaction.delete',resource,{key}),v=kv.delete(key);finish(l,v,v?1:0);return v;},
      getAlarm:async()=>{const l=reserve(trace,'transaction.getAlarm',resource,{});finish(l,null);return null;},
      deleteAlarm:async()=>{const l=reserve(trace,'transaction.deleteAlarm',resource,{});finish(l,null,1);}};
    try{const value=await fn(tx as unknown as DurableObjectTransaction);native.db.exec('COMMIT');finish(leaf,null);return value;}
    catch(error){native.db.exec('ROLLBACK');kv.clear();for(const[k,v]of old)kv.set(k,v);finish(leaf,{sourceRefusal:'transaction-rolled-back'});throw error;}
  }} as unknown as DurableObjectStorage;
  const authority=()=>({ledger:state.ledger(),namespace:native.id.namespace,operation:state.reference.operation,
    databaseId:state.binding.databaseId,sourceContext:state.binding.sourceContext,immutableVersion:state.binding.immutableVersion});
  const owner=new OwningPartitionRuntime({id:{toString:()=>native.id.id},storage} as DurableObjectState,
    {PMB1_MAIN_JOURNAL:state.db} as FreshRetainedEnvironment,authority);
  const originalOwner=new OwningPartitionRuntime({id:{toString:()=>native.id.id},storage} as DurableObjectState,
    {PMB1_MAIN_JOURNAL:state.db} as FreshRetainedEnvironment,authority);
  const absent=new NativePartitionDisposition(),bridge=new PartitionMaintenance(storage,absent.verify,Date.now,absent.reconcile);
  try{
    sql(native.db,resource,"UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");
    const admission=reserve(trace,'synthetic-fixture.kv',resource,{key:'pmb1:admission',value:true});kv.set('pmb1:admission',true);finish(admission,null,1);
    let admitted:ReturnType<PartitionMaintenance['capture']>|undefined;
    if(caseNumber===2){
      trace.active='case2.admitted-before-close';admitted=bridge.capture('fetch');
      await bridge.admit(admitted);await bridge.finish(admitted,domain,'returned');
    }
    if(caseNumber===3){
      sql(native.db,resource,"INSERT INTO pmb1_partition_binding VALUES(1,'synthetic-existing')");
      sql(domain.db,'domain-d1',"UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");
      sql(domain.db,'domain-d1',"INSERT INTO fga_users VALUES('synthetic-parent')");
      sql(domain.db,'domain-d1',"UPDATE maintenance_control SET generation=3,state='closed' WHERE singleton_id=1");
    }
    const ownerBindings={owners:new Map([[resource,owner]])};
    trace.active='case'+caseNumber+'.stop';await invokeInheritedNativeStep(ownerBindings,{kind:'owner-stop',resource,generation:'2',operationId:crypto.randomUUID()});
    trace.active='case'+caseNumber+'.close';await invokeInheritedNativeStep(ownerBindings,{kind:'owner-close',resource,generation:'2',operationId:crypto.randomUUID()});
    if(caseNumber===4){
      const lost=reserve(trace,'source-fault.lost-close-ack',resource,{operation:'maintenanceClose',generation:'2'});
      finish(lost,{outcome:'unknown'});
      fixtures.assertNoOutbound();
      return Object.freeze({caseNumber,scope:'SOURCE_SYNTHETIC_WIRING_ONLY',qualification:'NO_GO',outcome:'closed-refusal',
        reason:'committed-close-lost-ack-no-replay',trace:Object.freeze(trace.leaves.map(l=>Object.freeze({...l}))),
        controlAttempts:Object.freeze(controlAttempts.map(a=>Object.freeze({...a}))),actualWire:'UNKNOWN',actualCustody:'UNKNOWN'});
    }
    const control=sql(native.db,resource,'SELECT CAST(generation AS TEXT) generation,state FROM maintenance_control');
    if(control.length!==1||control[0].generation!=='3'||control[0].state!=='closed'||kv.get('pmb1:admission')!==false)fail('source_close_not_confirmed');
    trace.active='case'+caseNumber+'.challenge';
    const expectRefusal=async(action:()=>Promise<unknown>,label:string)=>{
      try{await action();}catch(error){
        if(!(error instanceof Error)||!/fenced|invalid_control|admission|closed|evidence_(header|review)/.test(error.message))throw error;
        reason=label;return;
      }fail('source_challenge_did_not_refuse');
    };
    if(caseNumber===2){
      await expectRefusal(()=>bridge.admit(admitted!), 'admitted-before-close-stale-admission-refused');
    }else if(caseNumber===3){
      sql(native.db,resource,"INSERT INTO pmb1_partition_binding VALUES(1,'stale') ON CONFLICT(id) DO UPDATE SET partition_id='stale'",[],true);
      sql(native.db,resource,"INSERT OR REPLACE INTO pmb1_partition_binding VALUES(1,'stale')",[],true);
      sql(domain.db,'domain-d1',"DELETE FROM fga_users WHERE user_id='synthetic-parent'",[],true);
      reason='native-upsert-replace-parent-delete-denied;selected-schema-has-no-cascade';
    }else if(caseNumber===5){
      sql(native.db,resource,'DROP TRIGGER pmb1_control_no_delete');
      sql(native.db,resource,'DELETE FROM maintenance_control');
      const cold=new OwningPartitionRuntime({id:{toString:()=>native.id.id},storage} as DurableObjectState,
        {PMB1_MAIN_JOURNAL:state.db} as FreshRetainedEnvironment,authority);
      await expectRefusal(()=>cold.maintenanceStop('3',crypto.randomUUID()),'cold-malformed-control-refused');
    }else if(caseNumber===6){
      state.clock.now=state.header.throughMs;
      const leaf=reserve(trace,'RuntimeEvidenceLedger.reserve', 'evidence-d1',{reference:state.reference});
      await expectRefusal(()=>state.ledger().reserve(state.reference),'expired-envelope-refused-before-native-acquisition');finish(leaf,{sourceRefusal:'expired'});
      // One bounded D1 header observation is needed to learn the protected
      // finite envelope window. No payload, consume or native read follows it.
      if(state.db.requests!==1)fail('source_expired_envelope_acquired_payload');
    }else if(caseNumber===7){
      const tools=sourceTools??(process.env.PMB1_SOURCE_TEST_UV&&process.env.PMB1_SOURCE_TEST_UV_CACHE
        ?{uvExecutable:process.env.PMB1_SOURCE_TEST_UV,cacheDirectory:process.env.PMB1_SOURCE_TEST_UV_CACHE}:undefined);
      if(!tools)throw Error('source_case7_pinned_tools_descriptor_required');
      const snapshot=async()=>syntheticText({schema:sql(native.db,resource,'SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name'),
        tables:['maintenance_control','pmb1_partition_binding','pmb1_partition_invocations','pmb1_wake_executions','pmb1_wake_results','pmb1_wake_work'].map(table=>[
          table,sql(native.db,resource,'SELECT rowid,* FROM "'+table+'"')]),kv:[...kv].sort(),alarm:await storage.transaction(tx=>tx.getAlarm())});
      const before=await snapshot();trace.active='case7.exact-retained-provider-restore';
      const restoreLeaf=reserve(trace,'ProspectiveRestoreProgram.restore_retained_version','source-provider',{scope:'SOURCE_PROVIDER_RESTORE_ONLY'});
      const report=sourceProviderRestore(tools);finish(restoreLeaf,report,Number(report.mutationRequests));
      trace.active='case7.exact-retained-provider-readback';
      const after=await snapshot();if(after!==before)throw Error('source_case7_native_state_changed_during_restore');
      const readback=reserve(trace,'BetaPublisherProvider.inspect_deployment','source-provider',{keys:report.keys});
      finish(readback,{deployment:report.deployment,nativeStateSha2_256:hash(after)});
      restoration=Object.freeze({expectedRetainedVersion:report.expectedRetainedVersion,deployment:report.deployment,
        keys:report.keys,requests:report.requests,nativeBeforeSha2_256:hash(before),nativeAfterSha2_256:hash(after),actualQualification:false});
      trace.active='case7.post-restore-delayed-generations';
      for(const [generation,heldOwner]of [['1',originalOwner],['2',owner]] as const){
        const operationId=crypto.randomUUID(),leaf=reserve(trace,'OwningPartitionRuntime.maintenanceStop',resource,{generation,operationId});
        await expectRefusal(()=>invokeInheritedNativeStep({owners:new Map([[resource,heldOwner]])},{kind:'owner-stop',resource,generation,operationId}),'both-original-and-temporary-delayed-generations-refused');
        finish(leaf,{sourceRefusal:'fenced'});controlAttempts.push({method:'maintenanceStop',generation,outcome:'refused'});
      }
    }else if(caseNumber===8){
      for(const statement of ["INSERT INTO audit_events(event_id,action,request_correlation_id,outcome,reason) VALUES('scheduled','scheduled','correlation','failed','source')",
        "INSERT INTO admin_sessions(session_id,token_digest,user_id,csrf_token,created_at_us,recent_authentication_at_us,expires_at_us,last_activity_at_us,correlation_id) VALUES('session','"+'a'.repeat(64)+"','user','"+'b'.repeat(43)+"',1,1,2,1,'source')",
        "INSERT INTO audit_events(event_id,action,request_correlation_id,outcome,reason) VALUES('auth-failure','authentication','correlation','failed','source')",
        "INSERT INTO status_read_buckets VALUES('installation','synthetic',100000000,1)"]){sql(domain.db,'domain-d1',statement,[],true);}
      reason='scheduled-session-auth-audit-status-writes-denied';
    }else if(caseNumber===9){
      const wake=new Pmb1NativeWakeup(storage,absent.verify);
      await expectRefusal(()=>wake.schedule('2','service-entry',1),'service-wake-schedule-refused');
      await expectRefusal(()=>wake.admitCurrentDue(),'queue-hint-current-due-refused');
      await expectRefusal(()=>wake.alarm(),'alarm-callback-fenced');
      reason='service-queue-hint-alarm-closed-native-entries-refused';
    }else if(caseNumber===10||caseNumber===11){
      const snapshot=()=>{
        const schema=sql(native.db,resource,'SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name');
        const tables=schema.filter((r:any)=>r.type==='table'&&r.name!=='__cf_kv').map((r:any)=>[
          r.name,sql(native.db,resource,'SELECT * FROM "'+String(r.name).replaceAll('"','""')+'"')]);
        return syntheticText({schema,tables});
      };
      const before=caseNumber===11?snapshot():'';
      const guard=sql(native.db,resource,"SELECT sql FROM sqlite_schema WHERE name='pmb1_wake_work_insert'")[0].sql;
      sql(native.db,resource,'DROP TRIGGER pmb1_wake_work_insert');
      sql(native.db,resource,"INSERT INTO pmb1_wake_work VALUES(1,'1','operator-bypass',NULL)");
      if(caseNumber===11){
        const deleteGuard=sql(native.db,resource,"SELECT sql FROM sqlite_schema WHERE name='pmb1_wake_work_delete'")[0].sql;
        sql(native.db,resource,'DROP TRIGGER pmb1_wake_work_delete');
        sql(native.db,resource,'DELETE FROM pmb1_wake_work');
        sql(native.db,resource,String(guard));
        sql(native.db,resource,String(deleteGuard));
        if(snapshot()!==before)fail('source_mutate_revert_fixture_not_equal');
      }
      const changes=trace.leaves.filter(l=>l.parent===trace.active&&l.method==='storage.sql.exec').reduce((n,l)=>n+l.effectEvents,0);
      if(changes<1)fail('source_fault_did_not_mutate');
      outcome='known-violation-detected';reason=caseNumber===10?'trusted-operator-guard-bypass-detected':'committed-mutate-revert-history-detected';
    }else if(caseNumber===12){
      const leaf=reserve(trace,'source-fault.partial-output',resource,{prefix:'declared-partial'});finish(leaf,{partial:'retained-source-prefix',outcome:'unknown'});
      reason='declared-partial-output-retained-no-later-work';
    }
    if(!reason)fail('source_failure_case_unimplemented');fixtures.assertNoOutbound();
    return Object.freeze({caseNumber,scope:'SOURCE_SYNTHETIC_WIRING_ONLY',qualification:'NO_GO',outcome,reason,
      trace:Object.freeze(trace.leaves.map(l=>Object.freeze({...l}))),
      restoration,
      controlAttempts:Object.freeze(controlAttempts.map(a=>Object.freeze({...a}))),actualWire:'UNKNOWN',actualCustody:'UNKNOWN'});
  }finally{state.close();domain.close();native.close();fixtures.assertNoOutbound();}
}

/** Fixed Root-body SOURCE unit: actual PrivateMainRuntime + existing SQLite D1
 * fixture, one known logical leaf. The journal here is an explicitly invented
 * synchronous ownership model for yield tests; real external SQLite durability
 * is separately tested through native_journal and rehearse_durable_operator.
 * It supplies no genuine Root authority, actual native wire or campaign fit. */
export async function rehearseReviewedNativeProgram(fault:string='none'):Promise<{
  scope:'SOURCE_KNOWN_MODEL_ONLY';qualification:'NO_GO';outcome:string;reason:string;
  sdkCalls:number;journalStatus:string;dispatchBeforeSDK:boolean;actualWire:'UNKNOWN';
  executedStages:readonly string[];
}>{
  if(!['none','root-delay','reserve-delay','begin-delay','oracle-delay','finish-delay','source-drift','descriptor-drift',
    'unknown-cost','full-fit','future-baseline','case12'].includes(fault))throw Error('source_root_rehearsal_fault');
  const blocked=await import(new URL('../pmb1-native-disposition/fixture.mjs',import.meta.url).href);
  const fixtures=await import(new URL('../pmb1-runtime-evidence/fixture.mjs',import.meta.url).href);
  const state=await fixtures.setupLedger({},['namespace/object-a'],{publish:fault!=='case12'});
  let now=10,pin='a'.repeat(64),status='unreserved',sdkCalls=0,armed=false,rootChecks=0,dispatchBeforeSDK=true;
  let nextLeaf=0,activeThrough=0;const executedStages:string[]=[];
  let observation:NativeObservedLeaf|undefined;
  let activeLeaves:any[]=[],collected:NativeObservedLeaf[]=[];
  const cost:NativeCost={requests:1,reader_queries:0,receipt_reads:0,metadata_reads:1,authenticated_checks:0,
    mutations:0,creates:0,deletes:0,sql_statements:1,effects:0,outbound_bytes:32768,inbound_bytes:262144,
    artifact_bytes:16384,challenges:0,captures:0};
  const sql="SELECT candidate,lifecycle,generation,state,CAST(revision AS TEXT) revision FROM pmb1_journal_control WHERE id=1 AND database_id=? AND candidate=? AND schema_version='pmb1-main-journal-v1' LIMIT 1";
  const request={sql,args:[state.binding.databaseId,state.binding.sourceContext]},requestDigest=hash(encoded(request));
  const originalPrepare=state.db.prepare.bind(state.db);
  const record=(request:unknown,response:unknown)=>{
    if(!armed||status!=='subtree_dispatching')throw Error('source_unreserved_sdk_effect');
    const leaf=activeLeaves[collected.length],actualDigest=hash(encoded(request));
    if(!leaf||leaf.request_digest!==actualDigest)throw Error('source_actual_sdk_statement_drift');
    const seen={identity:leaf.identity,requestDigest:actualDigest,cost:{...leaf.cost},evidence:new TextEncoder().encode(syntheticText(response))};
    collected.push(seen);return seen;
  };
  state.db.prepare=(statement:string)=>{const prepared=originalPrepare(statement);prepared.all=async()=>{
    if(!armed||status!=='subtree_dispatching')throw Error('source_unreserved_sdk_effect');
    if(hash(encoded({sql:statement,args:prepared.args}))!==requestDigest)throw Error('source_actual_sdk_statement_drift');
    dispatchBeforeSDK=dispatchBeforeSDK&&status==='subtree_dispatching';sdkCalls++;
    const result={success:true,results:state.db.raw.prepare(statement).all(...prepared.args)};
    observation=record({sql:statement,args:prepared.args},result);return result;
  };return prepared;};
  const main=new PrivateMainRuntime({PMB1_MAIN_JOURNAL:state.db} as FreshRetainedEnvironment,()=>({ledger:state.ledger(),
    namespace:'b'.repeat(32),operation:'main-assess',databaseId:state.binding.databaseId,
    sourceContext:state.binding.sourceContext,immutableVersion:state.binding.immutableVersion}));
  let facts:ReviewedNativeFacts;
  facts={scope:'SOURCE_KNOWN_MODEL_ONLY',caseNumber:1,tableCount:fault==='full-fit'?66:1,schemaObjects:fault==='full-fit'?717:1,
    programDigest:'0'.repeat(64),packetDigest:'0'.repeat(64),population:['source-model-object'],generations:['1'],
    rootRecord:'b'.repeat(64),reviewRecord:'c'.repeat(64),author:'source-author',reviewer:'source-independent-reviewer',
    starts:0,deadline:100,baselineFreshness:60,baselineAt:fault==='future-baseline'?50:null,restoredAt:null,
    lease:{key:'source-current-main-subtree',context_digest:'d'.repeat(64),source_pin:pin,
      profile:'pmb1-private-application-no-real-v1',object_profile:'pmb1-private-object-kv-interface-v1',
      leaves:[{ordinal:0,identity:'source-main-current-leaf',source_path:'probes/pmb1-fresh-native-capture/main-private-core.ts',
        source_pin:hash(readFileSync(new URL('../pmb1-fresh-native-capture/main-private-core.ts',import.meta.url),'utf8')),
        method:'D1.prepare.all',resource:'source-main-journal',request_digest:requestDigest,cost:fault==='unknown-cost'?null:cost}]},
    calls:[{stage:'settle',firstLeaf:0,throughLeaf:0,step:{kind:'main-current',
      domainDatabaseId:'bbbbbbbb-0000-4000-8000-000000000000',operationId:crypto.randomUUID()}}],
    bindings:{main,owners:new Map()},clock:()=>now,sourceCheck:()=>pin,
    root:{assertCurrent(){rootChecks++;if(fault==='root-delay'&&rootChecks===4)now=80;
        if(fault==='source-drift'&&rootChecks===2)pin='0'.repeat(64);},
      armPhysicalFence(_call,leaves){activeLeaves=[...leaves];collected=[];armed=true;},
      verifyPhysicalReceipt(){if(fault==='oracle-delay')now=80;if(!collected.length)throw Error('source_actual_receipt_missing');return collected;}},
    journal:{async reserve_tree(){if(status!=='unreserved')throw Error('source_no_replay');status='reserved';if(fault==='reserve-delay')now=80;},
      async begin_subtree(_lease,first,through){if(status!=='reserved'||first!==nextLeaf)throw Error('source_no_replay');status='subtree_dispatching';activeThrough=through;
        executedStages.push(facts.calls.find(c=>c.firstLeaf===first)?.stage??'invalid');
        if(fault==='begin-delay')now=80;if(fault==='descriptor-drift'){
          const step=facts.calls[0]!.step;if(step.kind==='main-current')step.operationId=crypto.randomUUID();
          facts.programDigest=nativeProgramDigest(facts);facts.packetDigest=nativePacketDigest(facts);}},
      async finish_subtree(){if(status!=='subtree_dispatching')throw Error('source_no_dispatch');nextLeaf=activeThrough+1;
        status=nextLeaf===facts.lease.leaves.length?'complete':'reserved';if(fault==='finish-delay')now=80;},
      async mark_unknown(){status='unknown';}}};
  if(fault==='case12'){
    // Shape-only QUALIFIED_ROOT branch is deliberately simulated here. These
    // fixed fake SDK/model references are NOT a genuine Root grant; the factory
    // returns SOURCE_KNOWN_MODEL_ONLY/NO_GO and reaches a mandatory interruption.
    const emptyCost:NativeCost={...cost,requests:0,metadata_reads:0,sql_statements:0,outbound_bytes:0,inbound_bytes:0};
    const makeLeaf=(ordinal:number,identity:string,request:unknown,c:NativeCost)=>({ordinal,identity,
      source_path:'probes/pmb1-finite-runner/native_composition.ts',source_pin:hash(readFileSync(new URL(import.meta.url),'utf8')),
      method:'SOURCE_MODEL',resource:'source-prefix',request_digest:hash(encoded(request)),cost:c});
    const plans=await publicationBatches(state.handoff,state.binding,state.provenance,state.allocation,state.clock.now);
    const publicationAuthority:OperatorPublicationAuthority={schema:'pmb1-qualified-native-d1-operator-publication-v1',databaseId:state.reference.databaseId,
      envelopeId:state.reference.envelopeId,operationId:crypto.randomUUID(),qualificationRecord:'a'.repeat(64),operatorEnvironmentRecord:'b'.repeat(64),
      bindingHolderRecord:'c'.repeat(64),credentialCustodyRecord:'d'.repeat(64),publisherSourceDigest:state.provenance.publisherSourceDigest,
      rootRecord:state.header.provenance.rootRecord,reviewRecord:state.header.provenance.reviewRecord,retainedEnvelopeDigest:state.handoff.retainedEnvelopeDigest,
      attemptLedgerRecord:state.provenance.operatorAttemptLedgerRecord,attemptState:'allocated-unused',fromMs:state.header.fromMs,throughMs:state.header.throughMs,
      allocation:{maxRequests:4,maxStatements:23,maxAcquiredBytes:state.header.payloadBytes*6+65536,maxAggregateBytes:67108864}};
    const modelOwner={async maintenanceStop(){sdkCalls++;record({model:'stop'},{admission:false});},
      async maintenanceClose(){sdkCalls++;record({model:'close'},{state:'closed'});}};
    facts.scope='QUALIFIED_ROOT';facts.caseNumber=12;
    facts.bindings={main,owners:new Map([['source-owner',modelOwner as unknown as OwningPartitionRuntime]])};
    const makeCurrent=(stage:string,first:number)=>({stage,firstLeaf:first,throughLeaf:first,step:{kind:'main-current' as const,
      domainDatabaseId:'bbbbbbbb-0000-4000-8000-000000000000',operationId:crypto.randomUUID()}});
    facts.calls=[makeCurrent('settle',0),{stage:'close',firstLeaf:1,throughLeaf:1,step:{kind:'owner-stop',resource:'source-owner',generation:'1',operationId:crypto.randomUUID()}},
      {stage:'close',firstLeaf:2,throughLeaf:2,step:{kind:'owner-close',resource:'source-owner',generation:'1',operationId:crypto.randomUUID()}},
      makeCurrent('closure_readback',3),{stage:'baseline',firstLeaf:4,throughLeaf:7,step:{kind:'publication',database:state.db,prepared:state.prepared,authority:publicationAuthority,now:()=>state.clock.now}},
      {stage:'interruption',firstLeaf:8,throughLeaf:8,step:{kind:'declared-interruption',reason:'partial_output'}}];
    facts.lease={...facts.lease,leaves:[makeLeaf(0,'source-main-prefix',request,cost),makeLeaf(1,'source-stop',{model:'stop'},emptyCost),
      makeLeaf(2,'source-close',{model:'close'},emptyCost),makeLeaf(3,'source-main-readback',request,cost),
      ...plans.map((plan,index)=>makeLeaf(4+index,'source-publication-'+index,plan,{...cost,metadata_reads:0,receipt_reads:1,sql_statements:plan.length})),
      makeLeaf(8,'source-declared-partial',{reason:'partial_output'},emptyCost)]};
    state.db.beforeBatch=async(_index:number,statements:FixedStatement[])=>{
      const fixed=statements.map(({sql,args})=>({sql,args}));if(!armed||status!=='subtree_dispatching')throw Error('source_unreserved_publication');
      const leaf=activeLeaves[collected.length];if(!leaf||leaf.request_digest!==hash(encoded(fixed)))throw Error('source_publication_identity');
      dispatchBeforeSDK=dispatchBeforeSDK&&status==='subtree_dispatching';sdkCalls++;
    };
    state.db.afterBatch=async(_index:number,statements:FixedStatement[],results:unknown)=>{record(statements.map(({sql,args})=>({sql,args})),results);};
  }
  facts.programDigest=nativeProgramDigest(facts);facts.packetDigest=nativePacketDigest(facts);
  let outcome='source_execution_complete',reason='';
  try{await executeReviewedNativeProgram(facts,true);}
  catch(error){outcome=status==='unreserved'?'refused':'unknown';reason=error instanceof Error?error.message:'source_unknown';}
  finally{state.close();blocked.assertNoOutbound();}
  return{scope:'SOURCE_KNOWN_MODEL_ONLY',qualification:'NO_GO',outcome,reason,sdkCalls,journalStatus:status,dispatchBeforeSDK,
    actualWire:'UNKNOWN',executedStages:Object.freeze(executedStages)};
}
