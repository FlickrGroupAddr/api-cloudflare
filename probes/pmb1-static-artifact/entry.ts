// MIT License; copyright 2026 Terry Ott.
// Unregistered static Worker. No automatic initialization or repair. Partition construction verifies its installed schema.
import { compose, restorationRequest } from '../pmb1-integer-candidate/candidate.ts';
import { D1MainEntryJournal } from '../pmb1-native-journal/journal.ts';
import { D1DomainReader } from '../pmb1-native-disposition/domain.ts';
import { NativeMainEntryObserver } from '../pmb1-native-disposition/observer.ts';
import { NativePartitionDisposition } from '../pmb1-native-disposition/partition.ts';
import { PartitionMaintenance } from '../../src/partition_maintenance.ts';
import { PartitionWorker as OrdinaryPartitionWorker } from '../../src/dispatch_worker.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';
import { errorResponse } from '../../src/installations.ts';
import type { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
import type { NativeCaptureControl } from '../pmb1-native-object-reader/native-control.ts';
import type { Env } from '../../src/worker.ts';
import contract from './source-contract.json' with { type: 'json' };
export { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
export { NativeCaptureControl } from '../pmb1-native-object-reader/native-control.ts';
export { restorationRequest };

export interface StaticEnvironment extends Env {
  PMB1_CONFIGURATION: string;
  PMB1_MAIN_JOURNAL: D1Database;
  PMB1_OWNERS: DurableObjectNamespace<NativeCaptureOwner>;
  PMB1_CAPTURE_CONTROL: DurableObjectNamespace<NativeCaptureControl>;
  PMB1_READ_NAMESPACE?: string;
}
const keys = ['profile', 'objectBoundary', 'd1Operation', 'binding', 'journalDatabaseId', 'domainDatabaseId', 'bounds'];
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(v);
function configuration(env: StaticEnvironment) {
  if (!env || typeof env.PMB1_CONFIGURATION !== 'string' || env.PMB1_CONFIGURATION.length > 4096) throw new MainEntryUnavailable();
  let c;
  try { c = JSON.parse(env.PMB1_CONFIGURATION); } catch { throw new MainEntryUnavailable(); }
  if (!c || Object.keys(c).sort().join() !== [...keys].sort().join()
    || c.profile !== contract.profile || c.objectBoundary !== contract.objectBoundary || c.d1Operation !== contract.d1Operation
    || !c.binding || Object.keys(c.binding).sort().join() !== 'candidate,generation,lifecycle'
    || c.binding.candidate !== contract.sourceContextSha2_256
    || typeof c.binding.lifecycle !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(c.binding.lifecycle)
    || typeof c.binding.generation !== 'string' || !/^[1-9][0-9]{0,18}$/.test(c.binding.generation)
    || BigInt(c.binding.generation) > 9223372036854775807n
    || !uuid(c.journalDatabaseId) || !uuid(c.domainDatabaseId) || c.journalDatabaseId === c.domainDatabaseId
    || !c.bounds || Object.keys(c.bounds).sort().join() !== 'bytes,milliseconds,pages,rows') throw new MainEntryUnavailable();
  // These are local observation ceilings, never a later campaign allocation.
  for (const [key, max] of Object.entries({pages:256,rows:10000,bytes:4194304,milliseconds:600000}))
    if (!Number.isSafeInteger(c.bounds[key]) || c.bounds[key] < 1 || c.bounds[key] > max) throw new MainEntryUnavailable();
  return c;
}
function adapters(env: StaticEnvironment) {
  const c = configuration(env);
  const journal = new D1MainEntryJournal(env, { binding: c.binding,
    journalDatabaseId: c.journalDatabaseId, comparedDatabaseIds: [c.domainDatabaseId] });
  const domain = new D1DomainReader(env.DB, c.bounds,
    {databaseId:c.domainDatabaseId,generation:c.binding.generation,state:'closed'});
  // ReviewedCoverage is an independent trusted input with NO environment/JSON
  // loader. Source packaging cannot authenticate factual custody or inventory.
  // These concrete adapters preserve their explicit missing-coverage refusals.
  const observer = new NativeMainEntryObserver(journal, c.bounds, domain, undefined, c.domainDatabaseId);
  return {c,journal,domain,observer};
}
// Exact native source/custody inputs are deliberately absent. Binding wiring
// is concrete, but no environment string can create ReviewedCoverage or certify
// a complete population. NativePartitionDisposition.gate refuses before reads.
function objectDisposition(env: StaticEnvironment, domain: D1DomainReader,
  storage?: Pick<DurableObjectStorage, 'sql' | 'transaction'>) {
  const namespace = env.PMB1_READ_NAMESPACE;
  const bindings = typeof namespace === 'string' && /^[a-f0-9]{32}$/.test(namespace)
    ? {[namespace]:env.PMB1_OWNERS} : {};
  return new NativePartitionDisposition(undefined, storage, domain, undefined, bindings, env.PMB1_CAPTURE_CONTROL);
}
function worker(env: StaticEnvironment) {
  const {c,journal,domain,observer} = adapters(env);
  const disposition = objectDisposition(env, domain);
  return compose({profile:'pmb1-private-application-no-real-v1',binding:c.binding,journal,observer,
    flickr:request=>fetch(request),verifyObjectDisposition:disposition.verify,
    verifyPartitionReconciliation:disposition.reconcile});
}
export default {
  async fetch(request: Request, env: StaticEnvironment): Promise<Response> {
    try { return await worker(env).handler.fetch(request, env); }
    catch(error) { if (!(error instanceof MainEntryUnavailable)) throw error;
      const reply = errorResponse(503,'service_unavailable','Service unavailable.'); reply.headers.set('Retry-After','5'); return reply; }
  },
  async scheduled(event: ScheduledController, env: StaticEnvironment): Promise<void> {
    await worker(env).handler.scheduled(event, env);
  },
} satisfies ExportedHandler<StaticEnvironment>;

export class PartitionWorker extends OrdinaryPartitionWorker {
  constructor(ctx: DurableObjectState, env: StaticEnvironment) {
    const {domain} = adapters(env);
    const disposition = objectDisposition(env, domain, ctx.storage);
    const maintenance = new PartitionMaintenance(ctx.storage, disposition.verify, Date.now, disposition.reconcile);
    super(ctx, {...env,FGA_PARTITION_MAINTENANCE:()=>maintenance});
  }
}
