import { jpeg } from './jpeg.ts';
export const LIMITS = { requestsPerRole: 32, bytes: 262145, delayMs: 16000, lifetimeSeconds: 1200 } as const;
export const CASES = ['png', 'jpeg', 'boundary-image', 'oversize-image', 'oversize-error',
  'slow-response', 'redirect-same', 'redirect-cross'] as const;
interface Env {
  DB: D1Database;
  ROLE: 'source' | 'receiver';
  RUN_ID: string;
  WORKERS_DEV_SUBDOMAIN: string;
  EXPIRES_AT_UNIX: string;
  ACCESS_TOKEN?: string;
  CANARY_TOKEN?: string;
}
interface Observation { requests: number; receiverRequests: number; authorizationObserved: number; canaryObserved: number; }
const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='), c => c.charCodeAt(0));
const BUDGET = `UPDATE network_probe_budget SET requests=requests+1,
  receiver_requests=receiver_requests+?, authorization_seen=max(authorization_seen,?),
  canary_seen=max(canary_seen,?)
  WHERE run_id=? AND role=? AND expires_at_unix=? AND expires_at_unix>unixepoch() AND requests<32
  RETURNING requests,receiver_requests receiverRequests,authorization_seen authorizationObserved,
    canary_seen canaryObserved`;

function origin(env: Env, role: 'source' | 'receiver') {
  return `https://fga-native-network-${role === 'source' ? 'src' : 'recv'}-${env.RUN_ID}.${env.WORKERS_DEV_SUBDOMAIN}.workers.dev`;
}
function configured(env: Env, now: number): boolean {
  const expiry = Number(env.EXPIRES_AT_UNIX);
  return ['source', 'receiver'].includes(env.ROLE) && /^[a-f0-9]{24}$/.test(env.RUN_ID)
    && env.RUN_ID !== '0'.repeat(24) && /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(env.WORKERS_DEV_SUBDOMAIN)
    && /^[a-f0-9]{64}$/.test(env.ACCESS_TOKEN ?? '') && /^SYNTHETIC-[a-f0-9]{32}$/.test(env.CANARY_TOKEN ?? '')
    && /^[1-9][0-9]{9,10}$/.test(env.EXPIRES_AT_UNIX) && Number.isSafeInteger(expiry)
    && Number.isFinite(now) && expiry > now && expiry - now <= LIMITS.lifetimeSeconds;
}
function headers(type: string, role: string): Headers {
  return new Headers({ 'Content-Type': type, 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff', 'X-FGA-Network-Probe': 'fga-native-network-v1' });
}
function json(value: unknown, role: string, status = 200): Response {
  return new Response(JSON.stringify(value), { status, headers: headers('application/json', role) });
}
function markerImage(size: number): Uint8Array<ArrayBuffer> {
  if (size === png.length) return png;
  const bytes = new Uint8Array(size); bytes.set(png.subarray(0, 33)); bytes.set(png.subarray(-12), size - 12);
  return bytes; // Allocation/signature fixture only; never claim this is a decodable photograph.
}

export function createNetworkProbe(sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms)),
  now = () => Date.now() / 1000) {
  return {
    async fetch(request: Request, env: Env): Promise<Response> {
      if (!configured(env, now())) return json({ error: 'expired_or_unconfigured' }, 'unavailable', 410);
      const url = new URL(request.url), denied = () => json({ error: 'not_found' }, env.ROLE, 404);
      if (request.method !== 'GET' || url.origin !== origin(env, env.ROLE) || url.search || url.hash) return denied();
      const gated = request.headers.get('X-FGA-Network-Access') === env.ACCESS_TOKEN;
      const receive = env.ROLE === 'receiver' && url.pathname === '/v1/receive/' + env.RUN_ID;
      const report = env.ROLE === 'receiver' && url.pathname === '/v1/report';
      const scenario = env.ROLE === 'source' && url.pathname.startsWith('/v1/cases/') ? url.pathname.slice(10) : '';
      if (!receive && !gated) return denied();
      if (!receive && !report && !CASES.includes(scenario as typeof CASES[number])) return denied();
      if (report && request.headers.has('Authorization')) return denied();
      if (env.ROLE === 'source' && request.headers.get('Authorization') !== 'Bearer ' + env.CANARY_TOKEN) return denied();
      const authorizationPresent = receive && request.headers.has('Authorization');
      const canaryMatched = receive && request.headers.get('Authorization') === 'Bearer ' + env.CANARY_TOKEN;
      let observation: Observation | null;
      try {
        observation = await env.DB.prepare(BUDGET).bind(Number(receive), Number(authorizationPresent),
          Number(canaryMatched), env.RUN_ID, env.ROLE, Number(env.EXPIRES_AT_UNIX)).first<Observation>();
      } catch { return json({ error: 'observation_unavailable' }, env.ROLE, 503); }
      if (!observation) return json({ error: 'budget_or_expiry_unavailable' }, env.ROLE, 429);
      if (!configured(env, now())) return json({ error: 'expired_or_unconfigured' }, env.ROLE, 410);
      if (receive) return json({ schemaVersion: 1, receiverReached: true, authorizationPresent, canaryMatched }, env.ROLE);
      if (report) return json({ schemaVersion: 1, receiverRequests: observation.receiverRequests,
        authorizationObserved: observation.authorizationObserved === 1, canaryObserved: observation.canaryObserved === 1 }, env.ROLE);
      if (scenario === 'redirect-same' || scenario === 'redirect-cross') {
        const location = scenario === 'redirect-same' ? origin(env, 'source') + '/v1/cases/png'
          : origin(env, 'receiver') + '/v1/receive/' + env.RUN_ID;
        const h = headers('application/json', env.ROLE); h.set('Location', location);
        return new Response(null, { status: 302, headers: h });
      }
      if (scenario === 'slow-response') await sleep(LIMITS.delayMs);
      if (!configured(env, now())) return json({ error: 'expired_or_unconfigured' }, env.ROLE, 410);
      const size = scenario === 'boundary-image' ? 262144 : ['oversize-image', 'oversize-error'].includes(scenario) ? LIMITS.bytes : png.length;
      const error = scenario === 'oversize-error', body = scenario === 'jpeg' ? jpeg : error ? new Uint8Array(size).fill(120) : markerImage(size);
      const h = headers(error ? 'text/plain' : scenario === 'jpeg' ? 'image/jpeg' : 'image/png', env.ROLE); h.set('Content-Length', String(body.length));
      return new Response(body, { status: error ? 503 : 200, headers: h });
    },
  } satisfies ExportedHandler<Env>;
}
export default createNetworkProbe();
