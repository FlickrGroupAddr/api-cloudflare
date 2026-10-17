// Temporary synthetic D1 guard; no production environment or getter is accepted.
export const LIMITS = Object.freeze({ fga: 96, receiver: 16, lifetimeMs: 1_200_000 });
export const CASES = Object.freeze(['ok', 'invalid-auth', 'fixed-origin-receive', 'fixed-origin-report', 'png', 'jpeg', 'exact-limit',
  'declared-excess', 'undeclared-excess', 'upstream-error', 'truncation', 'wrong-media',
  'wrong-signature', 'redirect', 'stall', 'missing-auth', 'bad-auth', 'bad-query',
  'final-installation', 'final-link', 'final-grant', 'foreign-identity', 'private-photo',
  'foreign-destination', 'edge-redirect-301', 'edge-redirect-302', 'edge-redirect-303',
  'edge-redirect-307', 'edge-redirect-308', 'edge-wrong-media', 'edge-malformed-png',
  'edge-truncated-png', 'edge-declared-excess', 'edge-undeclared-excess']);
const REDIRECT_CODES = Object.freeze([301, 302, 303, 307, 308]);
const validRun = run => typeof run === 'string' && /^[a-f0-9]{32}$/.test(run);
const validTime = now => Number.isSafeInteger(now) && now >= 0;
const deny = () => new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });

// Private lifecycle only. Existing singleton (including an expired run) cannot reset.
export async function initializeQuota({ db, run, startsAt }) {
  if (!validRun(run) || !validTime(startsAt) || !validTime(startsAt + LIMITS.lifetimeMs)) throw Error('invalid_scope');
  await db.prepare('INSERT INTO qualification_run(singleton,run,starts_at,expires_at) VALUES(1,?,?,?)')
    .bind(run, startsAt, startsAt + LIMITS.lifetimeMs).run();
}

export function createQuotaGuard({ db, run, clock = Date.now }) {
  if (!validRun(run) || !db || typeof db.prepare !== 'function') throw Error('invalid_scope');
  const now = () => { const value = clock(); return validTime(value) ? value : null; };
  const liveWhere = 'singleton=1 AND run=? AND enabled=1 AND starts_at<=? AND expires_at>?';
  return Object.freeze({
    async admit(role, caseId, observation) {
      if (!((role === 'fga' && CASES.includes(caseId) && observation === undefined)
          || (role === 'receiver' && ['receive', 'report'].includes(caseId)
            && (caseId === 'report' ? observation === undefined
              : observation && typeof observation.authorizationPresent === 'boolean' && typeof observation.canaryMatch === 'boolean'
                && Object.keys(observation).sort().join(',') === 'authorizationPresent,canaryMatch')))) return false;
      const time = now(); if (time === null) return false;
      try {
        // One conditional write is the admission authority across isolates/restarts.
        const sql = role === 'fga'
          ? `UPDATE qualification_run SET fga_count=fga_count+1 WHERE ${liveWhere} AND fga_count<96 RETURNING singleton`
          : `UPDATE qualification_run SET receiver_count=receiver_count+1, arrivals=arrivals+?,
              authorization_present=MAX(authorization_present,?), canary_match=MAX(canary_match,?)
              WHERE ${liveWhere} AND receiver_count<16 RETURNING singleton`;
        const args = role === 'fga' ? [run,time,time]
          : [caseId === 'receive' ? 1 : 0, observation?.authorizationPresent ? 1 : 0, observation?.canaryMatch ? 1 : 0,run,time,time];
        return !!await db.prepare(sql).bind(...args).first();
      } catch { return false; }
    },
    async canPublish() {
      const time = now(); if (time === null) return false;
      try { return !!await db.prepare(`SELECT singleton FROM qualification_run WHERE ${liveWhere}`).bind(run,time,time).first(); }
      catch { return false; }
    },
    async disable() {
      try { return !!await db.prepare('UPDATE qualification_run SET enabled=0 WHERE singleton=1 AND run=? RETURNING singleton').bind(run).first(); }
      catch { return false; }
    },
    async inspect() {
      try {
        const row = await db.prepare(`SELECT run,starts_at AS startsAt,expires_at AS expiresAt,enabled,
          fga_count AS fga,receiver_count AS receiver,arrivals,
          authorization_present AS authorizationPresent,canary_match AS canaryMatch FROM qualification_run WHERE singleton=1 AND run=?`).bind(run).first();
        return row ? { ...row, enabled: !!row.enabled, authorizationPresent: !!row.authorizationPresent,
          canaryMatch: !!row.canaryMatch, initialized: true, limits: LIMITS } : null;
      }
      catch { return null; }
    },
  });
}

export function createReceiver({ guard, run, origin, capability, canary }) {
  // The fixed origin reaches this receiver only through the wrapper's narrow
  // service binding. Other public origins still require the exact run receiver.
  const allowedOrigin = origin === 'https://flickrgroupaddr.com'
    || (typeof origin === 'string' && /^https:\/\/fga-fixed-origin-recv-[a-f0-9]{32}\.[a-z0-9-]+\.workers\.dev$/.test(origin)
      && new URL(origin).hostname.split('.')[0] === `fga-fixed-origin-recv-${run}`);
  if (!validRun(run) || !/^[a-f0-9]{64}$/.test(capability) || !/^[a-f0-9]{64}$/.test(canary)
      || !allowedOrigin) throw Error('invalid_scope');
  return Object.freeze({ async fetch(request) {
    // Production credentials never enter receiver storage or observation counters.
    if (/^Bearer(?:\s|$)/i.test(request.headers.get('Authorization') ?? '')) return deny();
    if (request.method !== 'GET' || request.body !== null || request.signal.aborted
        || request.headers.has('Transfer-Encoding')
        || (request.headers.has('Content-Length') && request.headers.get('Content-Length') !== '0')) return deny();
    const receive = REDIRECT_CODES.some(code => request.url === `${origin}/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${run}/${code}`);
    const report = request.url === `${origin}/report/${run}`;
    if (!receive && !report) return deny();
    if (report && request.headers.get('Authorization') !== `FGA-Qualification ${capability}`) return deny();
    const observation = receive ? { authorizationPresent: request.headers.has('Authorization'),
      canaryMatch: request.headers.get('X-FGA-Canary') === canary } : undefined;
    if (!await guard.admit('receiver', receive ? 'receive' : 'report', observation)) return deny();
    const receipt = report ? await guard.inspect() : null;
    if (report && !receipt) return deny();
    // Never reflect request data, headers, bodies, capability, canary or origin.
    const response = report ? Response.json({ receiverRequests: receipt.receiver, arrivals: receipt.arrivals,
      authorizationPresent: !!receipt.authorizationPresent, canaryMatch: !!receipt.canaryMatch },
    { headers: { 'Cache-Control': 'no-store' } }) : new Response(null, { status: 204, headers: { 'Cache-Control': 'no-store' } });
    return await guard.canPublish() ? response : deny();
  } });
}
