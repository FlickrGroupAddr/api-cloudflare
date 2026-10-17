// Temporary closed Worker composition. Full #0039 handler cases await #0041.
import { createQualificationWrapper, ORIGIN, PATHS, CASES } from '../fixed-origin-isolation/wrapper.mjs';
import { EDGE_FAULT_CASES, EDGE_REDIRECT_CODES, edgeReceiverPath, injectEdgeFault } from '../fixed-origin-isolation/edge_faults.mjs';
import { createQuotaGuard, LIMITS } from './quota_receiver.mjs';

export const COMPOSITION_CASES = Object.freeze([...CASES, ...EDGE_FAULT_CASES]);
const deny = () => new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });

// FIXED_ORIGIN_RECEIVER is a constructor-injected Worker service binding. No URL
// fetch, production env lookup, or client-selected destination is available.
export function createQualificationComposition({ captured, candidate, syntheticDb,
  quotaDb, receiverBinding, run, capability, startsAt, expiresAt, clock = Date.now, counters }) {
  if (!receiverBinding || typeof receiverBinding.fetch !== 'function') throw Error('invalid_receiver_binding');
  const guard = createQuotaGuard({ db: quotaDb, run, clock });
  const wrapper = createQualificationWrapper({ captured, candidate, syntheticDb,
    run, capability, startsAt, expiresAt, clock, counters });
  const live = () => { const now = clock(); return Number.isSafeInteger(now) && now >= startsAt && now < expiresAt; };
  const matchingScope = async () => {
    const receipt = await guard.inspect();
    return !!receipt && receipt.startsAt === startsAt && receipt.expiresAt === startsAt + LIMITS.lifetimeMs;
  };
  const receiveUrls = EDGE_REDIRECT_CODES.map(code => ORIGIN + edgeReceiverPath(run, code));
  const reportUrl = `${ORIGIN}/report/${run}`;
  return Object.freeze({ async fetch(request, productionEnv) {
    const active = () => !request.signal.aborted && live();
    const url = new URL(request.url);
    const auth = request.headers.get('Authorization');
    // Reserve these exact paths even for stripped redirect arrivals. Ordinary
    // paths continue through the unchanged captured dispatcher.
    const receiverPath = url.origin === ORIGIN && [...receiveUrls, reportUrl]
      .some(target => new URL(target).pathname === url.pathname);
    if (receiverPath) {
      if (/^Bearer(?:\s|$)/i.test(auth ?? '') || !live()
          || (!receiveUrls.includes(request.url) && request.url !== reportUrl)
          || request.method !== 'GET' || request.body !== null || request.signal.aborted
          || request.headers.has('Transfer-Encoding')
          || (request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')
          || (request.url === reportUrl && auth !== `FGA-Qualification ${capability}`)) return deny();
      // Only the receiver's observation allowlist crosses the service boundary.
      const headers = new Headers();
      for (const name of ['Authorization', 'X-FGA-Canary'])
        if (request.headers.has(name)) headers.set(name, request.headers.get(name));
      try {
        if (!await matchingScope() || !active()) return deny();
        const caseId = request.url === reportUrl ? 'fixed-origin-report' : 'fixed-origin-receive';
        if (!await guard.admit('fga', caseId) || !active()) return deny();
        const response = await receiverBinding.fetch(new Request(request.url, { headers, redirect: 'manual', signal: request.signal }));
        if (active() && await guard.canPublish() && active()) return response;
        await response.body?.cancel().catch(() => {});
      } catch { /* The receiver owns durable admission; ambiguous calls are not retried. */ }
      return deny();
    }
    const controls = [...request.headers.keys()].filter(name => name.startsWith('x-fga-qualification'));
    if (!controls.length && !/^fga-qualification/i.test(auth ?? '')) {
      return wrapper.fetch(request, productionEnv);
    }
    const scenario = request.headers.get('X-FGA-Qualification-Case');
    const edge = EDGE_FAULT_CASES.includes(scenario);
    if (auth !== `FGA-Qualification ${capability}` || request.headers.get('X-FGA-Qualification-Run') !== run
        || controls.some(name => !['x-fga-qualification-run', 'x-fga-qualification-case'].includes(name))
        || !COMPOSITION_CASES.includes(scenario) || !live()
        || request.method !== 'GET' || request.body !== null || request.signal.aborted
        || request.headers.has('Transfer-Encoding')
        || (request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')
        || !(edge ? [PATHS[2]] : PATHS).some(path => request.url === ORIGIN + path)) return deny();
    if (!await guard.admit('fga', scenario) || !active()) return deny();
    try {
      if (!await matchingScope() || !active()) return deny();
      const headers = new Headers(request.headers);
      if (edge) headers.set('X-FGA-Qualification-Case', 'ok');
      let response = await wrapper.fetch(new Request(request, { headers }), productionEnv);
      if (edge && active()) response = await injectEdgeFault(response, { scenario, run, requestUrl: request.url });
      if (active() && await guard.canPublish() && active()) return response;
      await response.body?.cancel().catch(() => {});
    } catch { /* Admission stays consumed; no retry or candidate error details. */ }
    return deny();
  } });
}
