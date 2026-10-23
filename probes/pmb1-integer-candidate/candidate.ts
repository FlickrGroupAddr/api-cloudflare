// MIT License; copyright 2026 Terry Ott.
// Unregistered composition. Trusted ports are explicit; no network defaults.
import { createMaintenanceWorker, createWorker, safePath, type Env } from '../../src/worker.ts';
import { LOOKUP_SQL } from '../../src/installations.ts';
import { MainEntryMaintenance, MainEntryUnavailable, type MainEntryBinding,
  type MainEntryJournal, type MainEntryObserver } from '../../src/main_entry_maintenance.ts';
import { PartitionMaintenance, type VerifyPartitionReconciliation } from '../../src/partition_maintenance.ts';
import { PartitionWorker } from '../../src/dispatch_worker.ts';
import type { VerifyDisposition } from '../pmb1-object/candidate.ts';
import type { FlickrFetch } from '../../src/flickr_reads.ts';
import type { AlbumCreateRepairDependencies } from '../../src/album_create_repair.ts';
import { PROFILE } from '../pmb1-no-real-object-reader/reader.ts';
export { capture, PROFILE } from '../pmb1-no-real-object-reader/reader.ts';

export interface Ports {
  profile: typeof PROFILE;
  binding: MainEntryBinding;
  journal: MainEntryJournal;
  observer: MainEntryObserver;
  flickr: FlickrFetch;
  verifyObjectDisposition: VerifyDisposition;
  verifyPartitionReconciliation: VerifyPartitionReconciliation;
  repair?: AlbumCreateRepairDependencies;
}
/** Open operation composition; durable journal/observation implementations must
 * reside OUTSIDE compared stores. Source ports alone qualify no actual runtime.
 * No constructor bootstraps, installs guards, closes, reopens or discovers state.
 */
export function compose(ports: Ports) {
  if (!ports || ports.profile !== PROFILE || typeof ports.flickr !== 'function' || typeof ports.verifyObjectDisposition !== 'function'
      || typeof ports.verifyPartitionReconciliation !== 'function') throw new MainEntryUnavailable();
  const maintenance = new MainEntryMaintenance(ports.binding, ports.journal, ports.observer);
  const ordinary = createMaintenanceWorker(maintenance, ports.flickr, ports.repair);
  const handler = {
    async fetch(request: Request, env: Env): Promise<Response> {
      // The existing current-installation GET has no required write. Keep its
      // actual registry/authentication/lookup path available inside closure.
      // Query/body/authentication refusals remain the ordinary handler's job.
      if (request.method === 'GET' && safePath(request.url) === '/api/v001/installations/current'
          && new URL(request.url).pathname === '/api/v001/installations/current')
        return closedRestorationCheck(request, env.DB, env.FGA_READ_ENABLED);
      return ordinary.fetch(request, env);
    },
    scheduled: ordinary.scheduled,
  };
  class CandidatePartitionWorker extends PartitionWorker {
    constructor(ctx: DurableObjectState, env: Env) {
      const partition = new PartitionMaintenance(ctx.storage, ports.verifyObjectDisposition,
        Date.now, ports.verifyPartitionReconciliation);
      super(ctx, { ...env, FGA_PARTITION_MAINTENANCE: () => partition }, { fetcher: ports.flickr });
    }
  }
  return Object.freeze({ handler, maintenance, CandidatePartitionWorker });
}

/** Ordinary closed restoration observation, using the existing registry and
 * authentication/lookup implementation. This capability is not a replacement
 * for the normal mutation handler or its mandatory settlement. Call only inside
 * the independently established complete closed interval. No closure assertion,
 * deployment, restore, disposition, receipt or PASS is manufactured here.
 * The complete lookup text is pinned: a future required write fails visibly.
 */
function closedRestorationCheck(request: Request, db: D1Database, readEnabled?: string): Promise<Response> {
  const unavailable = (): never => { throw new MainEntryUnavailable(); };
  const lookupOnly = {
    prepare(sql: string) {
      if (sql !== LOOKUP_SQL) return unavailable();
      return { bind(digest: string) {
        return { first: () => db.prepare(sql).bind(digest).first() };
      } };
    },
  } as D1Database;
  // Same ordinary worker code and feature gate as a deployed read. No success
  // body is fabricated, no authentication is skipped and no error is rewritten.
  return createWorker(async () => unavailable()).fetch(request,
    { DB: lookupOnly, FGA_READ_ENABLED: readEnabled } as Env);
}

export interface RetainedTarget {
  profile: 'pmb1-private-application-no-real-v1';
  candidateSha2_256: string;
  immutableVersion: string;
  configurationSha2_256: string;
  resourcesSha2_256: string;
}
/** Pure exact-target request construction, no provider client/call or retry.
 * Target pins must be independently retained, never learned from current output.
 */
export function restorationRequest(target: RetainedTarget, expected: RetainedTarget) {
  const names = ['profile', 'candidateSha2_256', 'immutableVersion', 'configurationSha2_256', 'resourcesSha2_256'] as const;
  const valid = (value: RetainedTarget) => value && Object.keys(value).sort().join() === [...names].sort().join()
    && value.profile === 'pmb1-private-application-no-real-v1'
    && /^[A-Za-z0-9_-]{1,128}$/.test(value.immutableVersion)
    && [value.candidateSha2_256, value.configurationSha2_256, value.resourcesSha2_256].every(x => /^[a-f0-9]{64}$/.test(x));
  if (!valid(target) || !valid(expected) || names.some(name => target[name] !== expected[name]))
    throw new MainEntryUnavailable();
  return Object.freeze({ versionId: target.immutableVersion, force: false as const });
}
