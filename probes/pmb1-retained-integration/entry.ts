// MIT License; copyright 2026 Terry Ott.
import { createFreshRetainedCandidate, type FreshRetainedEnvironment } from './fresh_composition.ts';
import { runtimeFacts } from './runtime_facts.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';
import { errorResponse } from '../../src/installations.ts';
import { safePath } from '../../src/worker.ts';
import { closedRestorationCheck } from './ordinary.ts';
import { EvidenceUnavailable } from '../pmb1-runtime-evidence/types.ts';
import { NativeSourceRefused } from '../pmb1-fresh-native-capture/source.ts';
export { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
export { NativeCaptureControl } from '../pmb1-native-object-reader/native-control.ts';
export { restorationRequest } from '../pmb1-integer-candidate/candidate.ts';

async function candidate(env: FreshRetainedEnvironment) {
  const facts = await runtimeFacts(env);
  if (!facts) throw new MainEntryUnavailable();
  return { facts, candidate: createFreshRetainedCandidate(env, facts.configuration, facts.trusted, facts.ledger, facts.envelope) };
}
export default {
  async fetch(request: Request, env: FreshRetainedEnvironment): Promise<Response> {
    // Exact retained bytes can serve this read after finite maintenance facts
    // expire. The ordinary registry/authentication/lookup stays read-only.
    if (request.method === 'GET' && safePath(request.url) === '/api/v001/installations/current'
      && new URL(request.url).pathname === '/api/v001/installations/current')
      return closedRestorationCheck(request, env.DB, env.FGA_READ_ENABLED);
    try { return await (await candidate(env)).candidate.handler.fetch(request, env); }
    catch (error) {
      if (!(error instanceof MainEntryUnavailable) && !(error instanceof EvidenceUnavailable)
        && !(error instanceof NativeSourceRefused)) throw error;
      const reply = errorResponse(503, 'service_unavailable', 'Service unavailable.');
      reply.headers.set('Retry-After', '5'); return reply;
    }
  },
  async scheduled(event: ScheduledController, env: FreshRetainedEnvironment): Promise<void> {
    await (await candidate(env)).candidate.handler.scheduled(event, env);
  },
} satisfies ExportedHandler<FreshRetainedEnvironment>;

export { PartitionWorker } from '../pmb1-fresh-native-capture/owning-partition.ts';
export { PrivateMainMaintenance } from '../pmb1-fresh-native-capture/main-private.ts';
