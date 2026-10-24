// MIT License; copyright 2026 Terry Ott.
// LOCAL SOURCE FIXTURE ONLY. Never the retained production entry or public route.
import { DurableObject } from 'cloudflare:workers';
import { PartitionWorker } from '../owning-partition.ts';
import { createQualifiedRuntimeAuthority, type NativeAuthorityEnvironment } from '../authority.ts';
import type {EvidencePurpose} from '../authority.ts';
import { consumeRuntimeFacts } from '../../pmb1-retained-integration/runtime_facts.ts';
import { createFreshRetainedCandidate, type FreshRetainedEnvironment } from '../../pmb1-retained-integration/fresh_composition.ts';
import { createFreshNativeSource } from '../source.ts';
import { captureSupportedBoundary } from '../../pmb1-native-object-reader/object-kv-interface.ts';
import { validatePartitionCapture } from '../partition.ts';
import ddl from './ddl.json' with { type: 'json' };
import {schemaSQL,storageSQL,columnsSQL} from '../../pmb1-no-real-object-reader/reader.ts';
import {PrivateMainMaintenance} from '../main-private.ts';

// Deliberately invented SOURCE qualification. No actual data or positive provider
// gate is asserted. No caller can choose these anchors or supply SQL/truth.
const qualification = Object.freeze({namespace:'b'.repeat(32),operation:'native-preservation',channel:{
  databaseId:'aaaaaaaa-0000-4000-8000-000000000000',schema:'pmb1-evidence-schema-v1',
  publisherSourceDigest:'1'.repeat(64),provenancePathDigest:'a'.repeat(64),holderPolicyDigest:'b'.repeat(64),nativeGetterQualificationRecord:'c'.repeat(64)}});
export class SyntheticPrivateMainMaintenance extends PrivateMainMaintenance{
  protected override runtimeAuthority(purpose:EvidencePurpose){return createQualifiedRuntimeAuthority(this.env,qualification,purpose);}
  override async assessStopped(target:Parameters<PrivateMainMaintenance['assessStopped']>[0],operationId:string){
    try{return await super.assessStopped(target,operationId);}catch(error){
      const reason=(error as {reason?:unknown})?.reason;
      throw new Error('synthetic_assess_refused_'+(typeof reason==='string'&&/^[a-z_]{1,128}$/.test(reason)?reason:'main_entry_unavailable'));
    }
  }
}
export class SyntheticCaptureOwner extends PartitionWorker {
  protected override runtimeAuthority(purpose:EvidencePurpose='raw-capture') { return createQualifiedRuntimeAuthority(this.env,qualification,purpose); }
  // Fixed SOURCE fixture provisioning only; no argument/SQL/bootstrap in actual
  // FreshNativeCaptureOwner. This export is confined to this synthetic bundle.
  async seedSynthetic() {
    if(this.ctx.storage.sql.exec("SELECT name FROM sqlite_schema WHERE name='maintenance_control'").toArray().length) throw Error('synthetic_once');
    this.ctx.storage.sql.exec(ddl.schema);this.ctx.storage.sql.exec(ddl.guards);
    await this.ctx.storage.put({'pmb1:admission':false,'pmb1:wake-admission-sequence':'0','pmb1:wake-revision':'0'});
  }
  async seedOpenSynthetic(){
    await this.seedSynthetic();
    this.ctx.storage.sql.exec("UPDATE maintenance_control SET generation=2,state='open' WHERE singleton_id=1");
    await this.ctx.storage.put('pmb1:admission',true);
  }
  async controlStateSynthetic(){return {control:this.ctx.storage.sql.exec('SELECT CAST(generation AS TEXT) generation,state FROM maintenance_control').toArray(),admission:await this.ctx.storage.get('pmb1:admission')};}
}
export class SyntheticOracleOwner extends SyntheticCaptureOwner {
  oracleMetadataSynthetic() {
    return {schema:this.ctx.storage.sql.exec(schemaSQL(512)).toArray(),
      tableList:this.ctx.storage.sql.exec(storageSQL(512)).toArray(),
      columns:this.ctx.storage.sql.exec(columnsSQL('__cf_kv',64)).toArray()};
  }
}
export class SyntheticSourceDriver extends DurableObject<NativeAuthorityEnvironment & FreshRetainedEnvironment> {
  nativeVersionSynthetic() { return this.env.PMB1_VERSION_METADATA!.id; }
  async observeSynthetic() {
    const authority=createQualifiedRuntimeAuthority(this.env,qualification),facts=await consumeRuntimeFacts(authority);
    const runtime=createFreshRetainedCandidate(this.env,facts.configuration,facts.trusted,authority.ledger,facts.envelope);
    const main=await runtime.maintenance.stop(5000);
    const source=await createFreshNativeSource(facts.trusted.source(),{[qualification.namespace]:this.env.COORD},authority.ledger,facts.envelope);
    const captured=await captureSupportedBoundary(source,facts.trusted.source().request),target=facts.native.request.expectedObjects[0];
    validatePartitionCapture(captured,'1',target.namespace,target.id);
    return {status:main.status,objects:captured.objects.length,tables:Object.keys(runtime.observer.retainedEvidence()!.domain.tables).length,
      nativeVersion:this.env.PMB1_VERSION_METADATA!.id,actualQualification:false};
  }
}
export default {fetch(){return new Response(null,{status:503});}};
