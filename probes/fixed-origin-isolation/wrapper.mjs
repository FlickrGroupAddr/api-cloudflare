// Temporary composition only. No handler, router or authentication implementation.
// JavaScript composes the exact captured and pinned candidate Worker exports.
import { HANDLER_CASES, HANDLER_PATHS, BROWSER_PATHS, canonicalHandlerCase,
  createHandlerCaseProvider } from '../fixed-origin-lifecycle/handler_cases.mjs';

export const ORIGIN = 'https://flickrgroupaddr.com';
export const PATHS = HANDLER_PATHS;
export const CASES = Object.freeze(['ok', 'invalid-auth', ...Object.keys(HANDLER_CASES)]);
const PREFIX = 'FGA-Qualification ';

// Share the exact closed route/case matrix with the outer admission boundary.
export function qualificationPaths(value) {
  let scenario;
  try { scenario = canonicalHandlerCase(value); } catch { return []; }
  return scenario === 'png' ? [...PATHS, ...BROWSER_PATHS]
    : ['missing-auth', 'bad-auth'].includes(scenario) ? PATHS : [PATHS[2]];
}
export function createQualificationWrapper({ captured, candidate, syntheticDb,
  run, capability, startsAt, expiresAt, clock = Date.now, counters }) {
  if (!/^[a-f0-9]{32}$/.test(run) || !/^[a-f0-9]{64}$/.test(capability)
      || !Number.isSafeInteger(startsAt) || !Number.isSafeInteger(expiresAt)
      || expiresAt <= startsAt || expiresAt - startsAt > 600_000) throw Error('invalid_scope');
  // The caller provisions all namespaces once in a new disposable synthetic DB
  // before opening admission. Reconstruction never resets authority or quotas.
  const provider = createHandlerCaseProvider({ candidate, syntheticDb, counters });
  const refuse = () => new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
  return Object.freeze({ async fetch(request, productionEnv) {
    const auth = request.headers.get('Authorization');
    const controlHeaders = [...request.headers.keys()].filter(name => name.startsWith('x-fga-qualification'));
    const selected = controlHeaders.length > 0 || /^fga-qualification/i.test(auth ?? '');
    if (!selected) {
      counters.normal++;
      return captured.default.fetch(request, productionEnv);
    }
    const now = clock();
    const url = new URL(request.url);
    const scenario = request.headers.get('X-FGA-Qualification-Case');
    if (auth !== PREFIX + capability || request.headers.get('X-FGA-Qualification-Run') !== run
        || controlHeaders.some(name => !['x-fga-qualification-run', 'x-fga-qualification-case'].includes(name))
        || !CASES.includes(scenario) || !Number.isSafeInteger(now) || now < startsAt || now >= expiresAt
        || request.method !== 'GET' || url.origin !== ORIGIN || url.username || url.password || url.hash
        // Full observable URL retains empty '?'/'#' delimiters lost by the
        // pathname/search/hash getters. The host may already normalize wire input.
        || !qualificationPaths(scenario).some(path => request.url === ORIGIN + path) || request.body !== null || request.signal.aborted
        || (request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')
        || request.headers.has('Transfer-Encoding')) return refuse();
    return provider.fetch(request, scenario);
  } });
}
