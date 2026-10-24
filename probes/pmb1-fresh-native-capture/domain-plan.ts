// MIT License; copyright 2026 Terry Ott.
import application from '../pmb1-native-disposition/domain-plan.json' with { type: 'json' };
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';
import { DispositionUnavailable } from '../pmb1-native-disposition/observer.ts';
export interface QualifiedNativeDomainPlan {
  schema: Record<string, unknown>[];
  oracle: { record: string; runtimeSourceSha2_256: string; applicationSourceSha2_256: string; independent: true };
}
/** Metadata expectations are frozen from an independently initialized oracle,
 * never from the acquired target. All 65 application tables and every canonical
 * guard remain literal. Only the provider-owned excluded metadata declaration
 * comes from the qualified platform oracle; its contents remain unobserved.
 */
export function validateNativeDomainPlan(input: QualifiedNativeDomainPlan) {
  const plan=structuredClone(input),fail=():never=>{throw new DispositionUnavailable('native_domain_oracle');};
  if(!plan || !plan.oracle || plan.oracle.independent!==true || typeof plan.oracle.record!=='string'
    || !/^[A-Za-z0-9._:/-]{1,256}$/.test(plan.oracle.record)
    || ![plan.oracle.runtimeSourceSha2_256,plan.oracle.applicationSourceSha2_256].every(p=>/^[a-f0-9]{64}$/.test(p))
    || !Array.isArray(plan.schema) || plan.schema.length>2000)fail();
  const native=plan.schema.filter(r=>r.name==='_cf_KV'),expected=application.schema.filter(r=>r.name!=='_cf_KV');
  if(native.length>1 || native.some(r=>r.type!=='table'||r.tbl_name!=='_cf_KV'||typeof r.sql!=='string'||r.sql.length>16384)
    || canonical(plan.schema.filter(r=>r.name!=='_cf_KV'))!==canonical(expected))fail();
  return Object.freeze({schema:plan.schema,tables:application.tables});
}
