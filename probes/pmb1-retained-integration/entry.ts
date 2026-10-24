// MIT License; copyright 2026 Terry Ott.
import { createRetainedCandidate, type RetainedEnvironment } from './composition.ts';
import { reviewedFacts } from './reviewed_facts.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';
import { errorResponse } from '../../src/installations.ts';
import { safePath } from '../../src/worker.ts';
import { closedRestorationCheck } from './ordinary.ts';
export { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
export { NativeCaptureControl } from '../pmb1-native-object-reader/native-control.ts';
export { restorationRequest } from '../pmb1-integer-candidate/candidate.ts';

async function candidate(env: RetainedEnvironment) {
  const facts = await reviewedFacts();
  if (!facts) throw new MainEntryUnavailable();
  return { facts, candidate: createRetainedCandidate(env, facts.configuration, facts.trusted) };
}
export default {
  async fetch(request: Request, env: RetainedEnvironment): Promise<Response> {
    // Exact retained bytes can serve this read after finite maintenance facts
    // expire. The ordinary registry/authentication/lookup stays read-only.
    if (request.method === 'GET' && safePath(request.url) === '/api/v001/installations/current'
      && new URL(request.url).pathname === '/api/v001/installations/current')
      return closedRestorationCheck(request, env.DB, env.FGA_READ_ENABLED);
    try { return await (await candidate(env)).candidate.handler.fetch(request, env); }
    catch (error) {
      if (!(error instanceof MainEntryUnavailable)) throw error;
      const reply = errorResponse(503, 'service_unavailable', 'Service unavailable.');
      reply.headers.set('Retry-After', '5'); return reply;
    }
  },
  async scheduled(event: ScheduledController, env: RetainedEnvironment): Promise<void> {
    await (await candidate(env)).candidate.handler.scheduled(event, env);
  },
} satisfies ExportedHandler<RetainedEnvironment>;

// Durable Object construction is asynchronous only through the native lifetime
// gate. No initialization, automatic repair or schema installation is performed.
export class PartitionWorker {
  private readonly ordinary: Promise<ReturnType<ReturnType<typeof createRetainedCandidate>['partition']>['worker']>;
  constructor(ctx: DurableObjectState, env: RetainedEnvironment) {
    this.ordinary = candidate(env).then(({ facts, candidate: runtime }) =>
      runtime.partition(ctx, facts.partitionNamespace, ctx.id.toString()).worker);
    ctx.blockConcurrencyWhile(async () => { await this.ordinary; });
  }
  async fetch(request: Request) { return (await this.ordinary).fetch(request); }
  async alarm() { return (await this.ordinary).alarm(); }
}
