// MIT License; copyright 2026 Terry Ott. Exact source binding projection checks.
import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const json=name=>JSON.parse(readFileSync(new URL(name,import.meta.url)));
test('declared legacy and active same-owner bindings match exact retained configuration',()=>{
 const config=json('wrangler.json'),manifest=json('binding-manifest.json');
 for(const binding of config.durable_objects.bindings)assert.equal(manifest.bindings[binding.name].class,binding.class_name,binding.name);
 assert.deepEqual(manifest.activeFreshPath,{binding:'COORD',class:'PartitionWorker',sameOrdinaryControlSnapshotStorage:true,rawCaptureAuthority:'PMB1_MAIN_JOURNAL'});
 assert.equal(manifest.bindings.PMB1_OWNERS.class,'NativeCaptureOwner');assert.equal(manifest.bindings.PMB1_OWNERS.freshSuccessorUses,false);
 assert.equal(config.exports.FreshNativeCaptureOwner,undefined);assert.equal(config.version_metadata.binding,'PMB1_VERSION_METADATA');
 assert.deepEqual(config.exports.PrivateMainMaintenance,{type:'worker'});
 const service=config.services.find(s=>s.binding==='PMB1_PRIVATE_MAIN');assert.equal(service.service,config.name);assert.equal(service.entrypoint,'PrivateMainMaintenance');
 assert.equal(manifest.bindings.PMB1_PRIVATE_MAIN.service,service.service);assert.equal(manifest.bindings.PMB1_PRIVATE_MAIN.entrypoint,service.entrypoint);
 assert.equal(manifest.actualResourceMapping,null);assert.equal(manifest.actualQualification,false);
});
