// MIT License; copyright 2026 Terry Ott.
import {D1MainEntryJournal} from '../pmb1-native-journal/journal.ts';
import {createFreshRetainedCandidate,type FreshRetainedEnvironment} from '../pmb1-retained-integration/fresh_composition.ts';
import {consumeRuntimeFacts} from '../pmb1-retained-integration/runtime_facts.ts';
import {MainEntryUnavailable} from '../../src/main_entry_maintenance.ts';
import type {EvidencePurpose,QualifiedRuntimeAuthority} from './authority.ts';
import {canonical} from '../pmb1-no-real-object-reader/reader.ts';
export interface PrivateMainTarget{databaseId:string;domainDatabaseId:string;candidate:string;lifecycle:string;generation:string;versionId:string;}
const uuid=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(v);
/** Native service-binding capability + qualified holder/source policy protects
 * this metadata-only interface. The existing outer operator control ledger must
 * reserve each exact call and retain unknown outcomes. IDs/labels are not grants.
 * Admission stop is distinct from later independently reviewed disposition. */
export class PrivateMainRuntime{
 readonly #env:FreshRetainedEnvironment;readonly #authority:(purpose:EvidencePurpose)=>QualifiedRuntimeAuthority|undefined;readonly #spent=new Set<string>();
 constructor(env:FreshRetainedEnvironment,authority:(purpose:EvidencePurpose)=>QualifiedRuntimeAuthority|undefined){this.#env=env;this.#authority=authority;}
 private authorize(operationId:string,purpose:EvidencePurpose){
  if(!uuid(operationId)||this.#spent.has(operationId))throw new MainEntryUnavailable();this.#spent.add(operationId);
  const a=this.#authority(purpose);if(!a)throw new MainEntryUnavailable();return a;
 }
 private target(t:PrivateMainTarget,a:QualifiedRuntimeAuthority){
  if(!t||canonical(Object.keys(t).sort())!==canonical(['databaseId','domainDatabaseId','candidate','lifecycle','generation','versionId'].sort())
   ||t.databaseId!==a.databaseId||t.candidate!==a.sourceContext||t.versionId!==a.immutableVersion
   ||!uuid(t.domainDatabaseId)||t.domainDatabaseId===t.databaseId||!/^[A-Za-z0-9_-]{1,80}$/.test(t.lifecycle)
   ||!/^[1-9][0-9]{0,18}$/.test(t.generation)||BigInt(t.generation)>9223372036854775807n)throw new MainEntryUnavailable();
 }
 async currentMain(domainDatabaseId:string,operationId:string){
  const a=this.authorize(operationId,'main-assess');if(!uuid(domainDatabaseId)||domainDatabaseId===a.databaseId)throw new MainEntryUnavailable();
  const session=this.#env.PMB1_MAIN_JOURNAL.withSession('first-primary'),result=await session.prepare(
   "SELECT candidate,lifecycle,generation,state,CAST(revision AS TEXT) revision FROM pmb1_journal_control WHERE id=1 AND database_id=? AND candidate=? AND schema_version='pmb1-main-journal-v1' LIMIT 1").bind(a.databaseId,a.sourceContext).all<Record<string,unknown>>();
  if(!result.success||result.results.length!==1)throw new MainEntryUnavailable();const r=result.results[0];
  const target={databaseId:a.databaseId,domainDatabaseId,candidate:a.sourceContext,lifecycle:r.lifecycle as string,generation:r.generation as string,versionId:a.immutableVersion};this.target(target,a);
  if(!['open','stopped'].includes(String(r.state))||typeof r.revision!=='string'||!/^[0-9]{1,19}$/.test(r.revision))throw new MainEntryUnavailable();
  return {target,state:r.state,revision:r.revision}; // Metadata only; no disposition/qualification.
 }
 async stopAdmission(target:PrivateMainTarget,operationId:string){
  const a=this.authorize(operationId,'main-assess');this.target(target,a);
  const journal=new D1MainEntryJournal(this.#env,{binding:{candidate:target.candidate,lifecycle:target.lifecycle,generation:target.generation},
   journalDatabaseId:target.databaseId,comparedDatabaseIds:[target.domainDatabaseId]});
  return journal.stop(journal.binding,{deadlineMs:performance.now()+300000});
 }
 async assessStopped(target:PrivateMainTarget,operationId:string){
  const a=this.authorize(operationId,'main-assess');this.target(target,a);
  const facts=await consumeRuntimeFacts(a),c=facts.configuration;
  if(c.binding.candidate!==target.candidate||c.binding.lifecycle!==target.lifecycle||c.binding.generation!==target.generation
   ||c.journalDatabaseId!==target.databaseId||c.domainDatabaseId!==target.domainDatabaseId)throw new MainEntryUnavailable();
  const runtime=createFreshRetainedCandidate(this.#env,c,facts.trusted,a.ledger,facts.envelope,async purpose=>{
   if(purpose!=='main-assess')throw new MainEntryUnavailable();return facts;
  });
  return runtime.maintenance.stop(Math.min(c.bounds.milliseconds,300000));
 }
}
