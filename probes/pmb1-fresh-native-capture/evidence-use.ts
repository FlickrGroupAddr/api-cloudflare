// MIT License; copyright 2026 Terry Ott.
import { qualifiedRuntimeAuthority, type EvidencePurpose } from './authority.ts';
import { consumeRuntimeFacts } from '../pmb1-retained-integration/runtime_facts.ts';
import type { FreshRetainedEnvironment,FreshRetainedConfiguration } from '../pmb1-retained-integration/fresh_composition.ts';
import { NativeMainEntryObserver } from '../pmb1-native-disposition/observer.ts';
import { NativeD1DomainReader } from './domain.ts';
import { MainEntryUnavailable, type MainEntryObserver, type MainEntryBinding, type MainEntryStop, type MainEntryDrainWindow } from '../../src/main_entry_maintenance.ts';
import { D1MainEntryJournal } from '../pmb1-native-journal/journal.ts';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';
export type EvidenceFacts=Awaited<ReturnType<typeof consumeRuntimeFacts>>;
export type EvidenceUseFactory=(purpose:Exclude<EvidencePurpose,'raw-capture'>)=>Promise<EvidenceFacts>;
export async function loadEvidenceUse(env:FreshRetainedEnvironment,purpose:Exclude<EvidencePurpose,'raw-capture'>){
  const authority=qualifiedRuntimeAuthority(env,purpose);if(!authority)throw new MainEntryUnavailable();
  return consumeRuntimeFacts(authority);
}
export function assertEvidenceUse(facts:EvidenceFacts,purpose:string,config:FreshRetainedConfiguration){
  if(facts.envelope.header.mode!=='evidence-use'||facts.envelope.reference.operation!==purpose
    ||canonical(facts.configuration.binding)!==canonical(config.binding)
    ||facts.configuration.journalDatabaseId!==config.journalDatabaseId||facts.configuration.domainDatabaseId!==config.domainDatabaseId)
    throw new MainEntryUnavailable();
  facts.trusted.assertConfiguration(facts.configuration);
}
/** Every assessment uses its own explicitly allocated noncapture evidence
 * attempt. Terminal + fresh primary/source/time/retire validation follows ALL
 * awaited observation work; it cannot spend an owner's raw capture slot. */
export class EvidenceMainEntryObserver implements MainEntryObserver {
  readonly #env:FreshRetainedEnvironment;readonly #config:FreshRetainedConfiguration;
  readonly #factory:EvidenceUseFactory;#record:unknown;
  constructor(env:FreshRetainedEnvironment,config:FreshRetainedConfiguration,factory:EvidenceUseFactory){this.#env=env;this.#config=structuredClone(config);this.#factory=factory;}
  async assess(binding:MainEntryBinding,stop:MainEntryStop,families:readonly string[],window:MainEntryDrainWindow){
    const use=await this.#factory('main-assess');assertEvidenceUse(use,'main-assess',this.#config);
    const c=use.configuration,journal=new D1MainEntryJournal(this.#env,{binding:c.binding,journalDatabaseId:c.journalDatabaseId,comparedDatabaseIds:[c.domainDatabaseId]}),
      domain=new NativeD1DomainReader(this.#env.DB,c.bounds,c.domainControl,c.domainPlan),
      observer=new NativeMainEntryObserver(journal,c.bounds,domain,use.trusted.coverage,c.domainDatabaseId);
    const result=await observer.assess(binding,stop,families,window);
    await use.ledger.finishEvidenceUse(use.envelope);use.trusted.assertConfiguration(c);
    this.#record=observer.retainedEvidence();return result;
  }
  retainedEvidence(){return this.#record as ReturnType<NativeMainEntryObserver['retainedEvidence']>;}
}
