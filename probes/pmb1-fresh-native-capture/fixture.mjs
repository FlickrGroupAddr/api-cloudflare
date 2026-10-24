// MIT License; copyright 2026 Terry Ott. Invented synthetic SOURCE only.
import { nativeFixture } from '../pmb1-native-disposition/native-fixture.mjs';
import { setupTrustedFixture } from '../pmb1-retained-integration/trusted_inputs_fixture.mjs';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';
import {setupLedger} from '../pmb1-runtime-evidence/fixture.mjs';
import {consumeRuntimeFacts} from '../pmb1-retained-integration/runtime_facts.ts';
const hash = value => createHash('sha256').update(value).digest('hex');
const pin = value => hash(Buffer.from(canonical(value)));
export function applyIndependentNativeOracle(f,oracle) {
  for(const object of f.input.request.expectedObjects){
    const observable=object.manifest.observable;
    assertCanonical(oracle.schema.filter(r=>r.name!=='__cf_kv'),object.manifest.application.schema);
    observable.schema=structuredClone(oracle.schema);observable.tableList=structuredClone(oracle.tableList);
    observable.columns.__cf_kv=structuredClone(oracle.columns);
    object.manifestSha2_256=pin(object.manifest);
  }
  f.input.packets=f.input.request.expectedObjects.map(object=>{
    const original=f.input.packets.find(p=>p.packet.request.expectedObjects[0].id===object.id),packet=structuredClone(original.packet);
    packet.request.expectedObjects=[structuredClone(object)];return {packet,sha2_256:pin(packet)};
  });
  f.payload.native=f.input;f.wire=structuredClone(f.payload);
  f.wire.native.request.sourceBytes=Object.fromEntries(Object.entries(f.input.request.sourceBytes).map(([n,b])=>[n,Buffer.from(b).toString('hex')]));
}
function assertCanonical(a,b){if(canonical(a)!==canonical(b))throw Error('independent_oracle_application_source_mismatch');}
export async function prepareModelEvidenceUse(state,fixture,purpose){
 const wire=structuredClone(fixture.wire),reference={...state.reference,envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:purpose};
 wire.native.control=reference;
 const use=await setupLedger(wire,[],{db:state.db,now:state.clock.now,reference,binding:state.binding,provenance:state.provenance,
   header:{mode:'evidence-use',fromMs:Number(wire.native.request.closure.start),throughMs:Number(wire.native.request.closure.end)},
   review:{fromMs:Number(wire.native.request.closure.start),throughMs:Number(wire.native.request.closure.end),rootRecord:pin(reference),reviewRecord:pin({independent:reference})}});
 return {state:use,load:()=>consumeRuntimeFacts({ledger:use.ledger(),namespace:fixture.objects[0].namespace,operation:purpose})};
}
export function reframeSyntheticInterval(f,fromMs,throughMs,interval){
 const closure=f.input.request.closure;Object.assign(closure,{start:String(fromMs),end:String(throughMs),interval});
 for(const fence of Object.values(f.input.request.fences))fence.interval=interval;
 for(const entry of f.input.packets){entry.packet.request.closure=structuredClone(closure);
   for(const fence of Object.values(entry.packet.request.fences))fence.interval=interval;entry.sha2_256=pin(entry.packet);}
 for(const custody of f.payload.coverage.authenticated.custody){custody.fromMs=fromMs;custody.throughMs=throughMs;}
 f.payload.native=f.input;f.wire=structuredClone(f.payload);
 f.wire.native.request.sourceBytes=Object.fromEntries(Object.entries(f.input.request.sourceBytes).map(([n,b])=>[n,Buffer.from(b).toString('hex')]));
}
export function freshFixture(reference, sourceContext, allocatedIds) {
  const f = setupTrustedFixture(), second = nativeFixture(), input = structuredClone(f.native.input);
  const templateId=f.native.id,oldId={...templateId,id:allocatedIds?.[0]??templateId.id},secondId={...templateId,id:allocatedIds?.[1]??'d'.repeat(64)};
  const originalKey=canonical([templateId.namespace,templateId.id]),newKey=canonical([oldId.namespace,oldId.id]);
  input.request.expectedObjects[0].id=oldId.id;input.request.expectedObjects[0].manifest.object=oldId;
  if(newKey!==originalKey){input.request.fences[newKey]=input.request.fences[originalKey];delete input.request.fences[originalKey];}
  input.expectedPopulation.objects[oldId.namespace][0].id=oldId.id;
  for(const resource of f.expected.resources)if(resource.id===templateId.namespace+'/'+templateId.id)resource.id=oldId.namespace+'/'+oldId.id;
  for(const custody of f.authenticated.custody)if(custody.resource===templateId.namespace+'/'+templateId.id)custody.resource=oldId.namespace+'/'+oldId.id;
  const sources = input.request.sourceBytes;
  for (const [name,path] of Object.entries({
    'fresh-source.ts':'source.ts','fresh-owner.ts':'owner.ts','fresh-owner-core.ts':'owner-core.ts',
    'fresh-payload.ts':'payload.ts','fresh-trusted.ts':'trusted.ts','fresh-partition.ts':'partition.ts',
    'fresh-authority.ts':'authority.ts','fresh-qualification.ts':'qualification.ts','owning-partition.ts':'owning-partition.ts','owning-core.ts':'owning-core.ts','private-controller.ts':'controller.ts','evidence-use.ts':'evidence-use.ts','runtime-ledger.ts':'../pmb1-runtime-evidence/ledger.ts',
    'runtime-types.ts':'../pmb1-runtime-evidence/types.ts'})) sources[name] = new Uint8Array(readFileSync(new URL(path,import.meta.url)));
  input.request.expectedSources = Object.fromEntries(Object.entries(sources).map(([n,b])=>[n,hash(b)]));
  const first = input.request.expectedObjects[0];
  first.manifest.sourcePins = input.request.expectedSources;
  first.manifestSha2_256 = pin(first.manifest);
  const secondObject = structuredClone(first);
  secondObject.id = secondId.id; secondObject.manifest.object = secondId;
  secondObject.manifestSha2_256 = pin(secondObject.manifest);
  input.request.expectedObjects.push(secondObject);
  input.request.fences[canonical([secondId.namespace,secondId.id])] = structuredClone(input.request.fences[canonical([oldId.namespace,oldId.id])]);
  input.expectedPopulation.objects[oldId.namespace].push({id:secondId.id,hasStoredData:true});
  input.expectedPopulation.accountNamespaces[0].class = 'PartitionWorker';
  input.expectedPopulationSha2_256 = pin(input.expectedPopulation);
  input.census = {...input.census,...input.expectedPopulation}; input.censusSha2_256 = pin(input.census);
  input.control = reference;
  const sourceHex = Object.fromEntries(Object.entries(sources).map(([name,value])=>[name,Buffer.from(value).toString('hex')]));
  input.packets = input.request.expectedObjects.map(object=>{
    const {sourceBytes:ignored,...request} = structuredClone(input.request);
    request.expectedObjects=[object]; request.fences={[canonical([object.namespace,object.id])]:input.request.fences[canonical([object.namespace,object.id])]};
    const packet={...input.packets[0].packet,request,sourceHex}; return {packet,sha2_256:pin(packet)};
  });
  const binding={...f.config.binding,candidate:sourceContext};
  f.config.domainPlan={schema:JSON.parse(readFileSync(new URL('../pmb1-native-disposition/domain-plan.json',import.meta.url))).schema,oracle:{record:'synthetic-independent-oracle',runtimeSourceSha2_256:'a'.repeat(64),applicationSourceSha2_256:'b'.repeat(64),independent:true}};
  f.config.domainControl={databaseId:f.config.domainDatabaseId,generation:'1',state:'closed'};
  f.config.binding=binding; f.expected.binding=binding; f.authenticated.binding=binding;
  f.expected.resources.push({id:secondId.namespace+'/'+secondId.id,kind:'object'});
  f.authenticated.custody.push({...f.authenticated.custody.find(c=>c.resource===oldId.namespace+'/'+oldId.id),resource:secondId.namespace+'/'+secondId.id});
  const writer=f.expected.writers.find(w=>w.id==='application');writer.sourceSha2_256=input.request.expectedSources['owning-partition.ts'];
  f.authenticated.writers.find(w=>w.id==='application').sourceSha2_256=writer.sourceSha2_256;
  const payload={schema:'pmb1-retained-runtime-input-v1',configuration:f.config,coverage:{expected:f.expected,authenticated:f.authenticated},native:input,partitionNamespace:oldId.namespace};
  const wire=structuredClone(payload);wire.native.request.sourceBytes=sourceHex;
  return {f,second,input,payload,wire,objects:[oldId,secondId],sources,
    stores:new Map([[oldId.id,f.native.storage],[secondId.id,second.storage]]),
    close(){f.close();second.close();}};
}
