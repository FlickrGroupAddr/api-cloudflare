// SOURCE-only fixture materializer, separate process so native test isolation
// remains in place. No provider/native/private reads; all semantic facts invented.
import { readFileSync,writeFileSync } from 'node:fs';
import { freshFixture,applyIndependentNativeOracle,reframeSyntheticInterval } from '../fixture.mjs';
import { setupLedger } from '../../pmb1-runtime-evidence/fixture.mjs';
import { requiredCharge } from '../../pmb1-runtime-evidence/ledger.ts';
import { LocalD1 } from '../../pmb1-native-disposition/fixture.mjs';
const options=JSON.parse(readFileSync(process.argv[2],'utf8'));
const contract=JSON.parse(readFileSync(new URL('../../pmb1-retained-integration/source-contract.json',import.meta.url)));
const reference={databaseId:'aaaaaaaa-0000-4000-8000-000000000000',envelopeId:crypto.randomUUID(),attemptId:crypto.randomUUID(),operation:options.purpose??'native-preservation'};
const f=freshFixture(reference,contract.sourceContextSha2_256,options.objectIds),keys=f.objects.map(o=>o.namespace+'/'+o.id);
if(options.custodyMs)reframeSyntheticInterval(f,Date.now(),Date.now()+options.custodyMs,'synthetic-'+reference.envelopeId);
if(options.nativeOracle)applyIndependentNativeOracle(f,options.nativeOracle);
if(options.domainOracle){
 f.payload.configuration.domainPlan={schema:options.domainOracle,oracle:{record:'synthetic-independent-native-d1-oracle',
   runtimeSourceSha2_256:options.runtimeSourceSha2_256,applicationSourceSha2_256:options.applicationSourceSha2_256,independent:true}};
 f.wire.configuration=f.payload.configuration;
}
if(options.observationMilliseconds){f.payload.configuration.bounds.milliseconds=options.observationMilliseconds;f.wire.configuration=f.payload.configuration;}
const nativeBytes=f.input.request.limits.bytes*keys.length,charge=requiredCharge(JSON.stringify(f.wire).length,keys.length,nativeBytes);
const s=await setupLedger(f.wire,options.mode==='evidence-use'?[]:keys,{now:Date.now(),reference,
  binding:{databaseId:reference.databaseId,sourceContext:contract.sourceContextSha2_256,lifecycle:f.f.config.binding.lifecycle,generation:f.f.config.binding.generation,
    immutableVersion:options.nativeVersion,moduleDigest:options.moduleDigest,configurationDigest:options.configurationDigest,
    resourceInventoryDigest:options.resourceInventoryDigest,nativeSourceDigest:f.input.request.expectedSources['fresh-source.ts'],ownerSourceDigest:f.input.request.expectedSources['owning-partition.ts']},
  provenance:{provenancePathDigest:'a'.repeat(64),holderPolicyDigest:'b'.repeat(64),nativeGetterQualificationRecord:'c'.repeat(64)},
  header:{mode:options.mode??'raw-capture',fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},
  review:{fromMs:Number(f.input.request.closure.start),throughMs:Number(f.input.request.closure.end)},allocation:{maxNativeBytes:nativeBytes,maxAggregateBytes:charge.aggregate}});
const d=new LocalD1();
function statements(db){
 const schema=db.prepare('SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY rowid').all();
 const result=schema.filter(r=>r.type==='table').map(r=>({sql:r.sql,args:[]}));
 for(const {name} of schema.filter(r=>r.type==='table')){
  const cols=db.prepare('PRAGMA table_info("'+name+'")').all().map(r=>r.name);
  for(const row of db.prepare('SELECT * FROM "'+name+'"').all())result.push({sql:'INSERT INTO "'+name+'"('+cols.map(c=>'"'+c+'"').join(',')+') VALUES('+cols.map(()=>'?').join(',')+')',args:cols.map(c=>row[c])});
 }
 return [...result,...schema.filter(r=>r.type!=='table').map(r=>({sql:r.sql,args:[]}))];
}
writeFileSync(process.argv[3],JSON.stringify({reference,objects:f.objects,domain:statements(d.db),journal:statements(s.db.raw),prepared:s.prepared}));
d.close();s.close();f.close();
