// Private assembly supplies only these fixed local modules; no provider discovery.
import * as captured from '../../captured.mjs';
import * as candidate from '../../candidate.mjs';
import scope from '../../scope.json' with { type: 'json' };
import { createTemporaryComposition } from './entrypoint.mjs';
import { ORIGIN } from '../fixed-origin-isolation/wrapper.mjs';
export * from '../../captured.mjs';

const counters = Object.create(null);
const receiverPrefix = `/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${scope.run}/`;
const reportPath = `/report/${scope.run}`;
export default {
  ...captured.default,
  fetch(request, env, context) {
    const url = new URL(request.url);
    const selected = [...request.headers.keys()].some(name => name.startsWith('x-fga-qualification'))
      || /^fga-qualification/i.test(request.headers.get('Authorization') ?? '')
      || (url.origin === ORIGIN && (url.pathname.startsWith(receiverPrefix) || url.pathname === reportPath));
    if (!selected) return captured.default.fetch(request, env, context);
    try {
      const keys = scope.bindingKeys;
      return createTemporaryComposition({ captured, candidate,
        syntheticDb: env[keys.syntheticDb], quotaDb: env[keys.quotaDb],
        receiverBinding: env[keys.receiver], capability: env[keys.capability],
        run: scope.run, startsAt: scope.startsAt, expiresAt: scope.expiresAt, counters,
      }).fetch(request, env);
    } catch {
      return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
    }
  },
};
