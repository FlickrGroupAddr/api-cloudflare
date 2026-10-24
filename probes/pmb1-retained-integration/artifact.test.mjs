// MIT License; copyright 2026 Terry Ott. Exact emitted artifact; synthetic only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve,join } from 'node:path';
import { createHash } from 'node:crypto';
import { Miniflare,Log,LogLevel } from 'miniflare';
import { DatabaseSync } from 'node:sqlite';
const build=resolve(process.env.PMB1_ARTIFACT_DIRECTORY);
const manifest=JSON.parse(readFileSync(join(build,'artifact-manifest.json')));
const sha=raw=>createHash('sha256').update(raw).digest('hex');
test('complete retained modules/configuration and all source/toolchain/runtime inputs match exact pins',()=>{
 for(const [name,pin] of Object.entries(manifest.moduleSha2_256)){
  assert.equal(sha(readFileSync(join(build,'emitted',name))),pin);assert.equal(sha(readFileSync(join(build,'retained/modules',name))),pin);
 }
 const root=new URL('../../',import.meta.url);
 for(const [name,pin] of Object.entries(manifest.sourceInputs))assert.equal(sha(readFileSync(new URL(name,root))),pin,name);
 for(const name of ['composition.ts','trusted_inputs.ts','reviewed_facts.ts','entry.ts'])assert(manifest.sourceInputs['probes/pmb1-retained-integration/'+name]);
 assert.equal(sha(readFileSync(join(build,'retained/configuration.json'))),manifest.configurationSha2_256);
 assert.equal(manifest.actualQualification,false);assert.equal(manifest.actualImmutableVersion,null);
 assert.equal(manifest.restore.force,false);assert.equal(manifest.restore.rebuildAllowed,false);
 const config=JSON.parse(readFileSync(join(build,'retained/configuration.json')));assert.equal(config.compatibility_date,'2026-10-16');
 const map=JSON.parse(readFileSync(join(build,'emitted/entry.js.map'))),virtual=new Map(map.sources.map((n,i)=>[n,map.sourcesContent[i]]));
 for(const [name,input] of Object.entries(manifest.runtimeGraph))assert.equal(sha(input.virtual?Buffer.from(virtual.get(name)):readFileSync(new URL(name,root))),input.sha2_256,name);
 for(const [name,pin] of Object.entries(manifest.toolchain))assert.equal(sha(readFileSync(name==='portable-node.exe'?process.execPath:new URL(name,root))),pin,name);
});
test('missing trusted facts and arbitrary HTTP/environment truth cannot admit maintenance, including restart/race',async()=>{
 let outbound=0;
 const options={modules:true,modulesRoot:join(build,'emitted'),scriptPath:join(build,'emitted/entry.js'),compatibilityDate:'2026-08-06',compatibilityFlags:['nodejs_compat'],
  log:new Log(LogLevel.ERROR),cf:false,port:0,inspectorPort:0,host:'127.0.0.1',
  d1Databases:{DB:'bbbbbbbb-0000-4000-8000-000000000000',PMB1_MAIN_JOURNAL:'aaaaaaaa-0000-4000-8000-000000000000'},
  durableObjects:{COORD:{className:'PartitionWorker',useSQLite:true},PMB1_OWNERS:{className:'NativeCaptureOwner',useSQLite:true},PMB1_CAPTURE_CONTROL:{className:'NativeCaptureControl',useSQLite:true}},
  bindings:{PMB1_CONFIGURATION:JSON.stringify({coverage:{complete:true},actualQualification:true}),PMB1_TRUSTED_INPUTS:'{"trusted":true}',FGA_READ_ENABLED:'1'},outboundService:()=>{outbound++;throw Error('outbound_forbidden');}};
 const mf=new Miniflare(options);try{
  const db=await mf.getD1Database('DB'),raw=new DatabaseSync(':memory:');
  try {
   raw.exec(readFileSync(new URL('../pmb1-integer-candidate/d1-schema.sql',import.meta.url),'utf8'));
   const token=Array(13).fill('0000').join('-');
   raw.exec("BEGIN;INSERT INTO fga_users VALUES('user');INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('installation','user','lrc_plugin','active',7,'version');");
   raw.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','installation',?,'current',1)").run(sha(token));raw.exec('COMMIT');
   raw.exec(readFileSync(new URL('../pmb1-integer-candidate/d1-guards.sql',import.meta.url),'utf8'));
   const schema=raw.prepare('SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY rowid').all();
   for(const row of schema.filter(r=>r.type==='table'))await db.prepare(row.sql).run();
   const inserts=[];
   for(const {name} of schema.filter(r=>r.type==='table')){
    const columns=raw.prepare('PRAGMA table_info("'+name+'")').all().map(r=>r.name);
    for(const row of raw.prepare('SELECT * FROM "'+name+'"').all())inserts.push(db.prepare('INSERT INTO "'+name+'"('+columns.map(c=>'"'+c+'"').join(',')+') VALUES('+columns.map(()=>'?').join(',')+')').bind(...columns.map(c=>row[c])));
   }
   await db.batch(inserts);
   for(const row of schema.filter(r=>r.type!=='table'))await db.prepare(row.sql).run();
   const request=()=>mf.dispatchFetch('https://synthetic.invalid/api/v001/installations/current',{headers:{Authorization:'Bearer '+token}});
   const response=await request();assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');
   assert.deepEqual(await response.json(),{schemaVersion:1,installationId:'installation',installationRevision:7,installationState:'active',presentedCredentialState:'current'});
   assert.equal((await db.prepare('SELECT state FROM maintenance_control').first()).state,'closed');
   await assert.rejects(db.prepare("UPDATE installations SET label='forbidden'").run(),/maintenance_closed/);
   await mf.setOptions(options);assert.equal((await request()).status,200);
  }finally{raw.close();}
  for(const path of ['/admin/login','/maintenance','/other'])assert.equal((await mf.dispatchFetch('https://synthetic.invalid'+path)).status,503);
  await mf.setOptions(options);
  const race=await Promise.all(Array.from({length:8},()=>mf.dispatchFetch('https://synthetic.invalid/admin/login')));assert(race.every(r=>r.status===503));
  const scheduled=await (await mf.getWorker()).scheduled();assert.equal(scheduled.outcome,'exception');assert.equal(outbound,0);
 }finally{await mf.dispose();}
});
