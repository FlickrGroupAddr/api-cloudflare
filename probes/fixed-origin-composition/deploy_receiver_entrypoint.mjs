// Explicit private scope and bindings only; this receiver cannot discover targets.
import scope from '../../scope.json' with { type: 'json' };
import { createQuotaGuard, createReceiver } from '../fixed-origin-lifecycle/quota_receiver.mjs';
import { ORIGIN } from '../fixed-origin-isolation/wrapper.mjs';

export default {
  async fetch(request, env) {
    try {
      const guard = createQuotaGuard({ db: env[scope.bindingKeys.quotaDb], run: scope.run });
      const receipt = await guard.inspect();
      if (!receipt || receipt.startsAt !== scope.startsAt
          || receipt.expiresAt !== scope.startsAt + 1200000) {
        return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
      }
      const receiver = createReceiver({ guard, run: scope.run, origin: ORIGIN,
        capability: env[scope.bindingKeys.capability], canary: scope.canary });
      return await receiver.fetch(request);
    } catch {
      return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
    }
  },
};
