/** Bounded selection/launch through the documented injected @oai/sky API only.
 * No inputs, helper protocol, process spawning, cancellation reset, or metadata logs.
 * A timeout stops this caller; sky operations already dispatched may still finish.
 * Callers must re-enumerate before deciding what to do after any unknown outcome.
 */
import { setTimeout as delay } from 'node:timers/promises';

export class LightroomAutomationError extends Error {
  constructor(code) {
    super(code);
    this.name = 'LightroomAutomationError';
    this.code = code;
  }
}

const defaultName = /^(?:Adobe )?Lightroom Classic$/i;
const stages = new Set(['enumerating', 'reusing', 'launching', 'launch_window_pending',
  'waiting_for_window', 'rehydrating', 'ready']);

/** Select exactly one returned app/window, launch at most once, and rehydrate it.
 * Supply appId from an inspected list_apps() result when display names vary.
 * Window ownership identifiers may legitimately differ from the selected app ID.
 * log receives fixed stages only. Keep returned window/state private to UI work.
 */
export async function ensureLightroomWindow(sky, {
  appId,
  signal,
  timeoutMs = 30_000,
  pollIntervalMs = 500,
  maxPolls = 60,
  now = () => performance.now(),
  sleep = (ms, abortSignal) => delay(ms, undefined, { signal: abortSignal }),
  log = () => {},
} = {}) {
  if (!sky || ['list_apps', 'launch_app', 'get_window'].some(key => typeof sky[key] !== 'function')
    || appId !== undefined && (typeof appId !== 'string' || appId.length === 0)
    || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 120_000
    || !Number.isInteger(pollIntervalMs) || pollIntervalMs < 1 || pollIntervalMs > 5_000
    || !Number.isInteger(maxPolls) || maxPolls < 1 || maxPolls > 240
    || typeof now !== 'function' || typeof sleep !== 'function' || typeof log !== 'function') {
    throw new LightroomAutomationError('invalid_options');
  }
  const started = now();
  if (!Number.isFinite(started)) throw new LightroomAutomationError('invalid_clock');
  let lastTime = started;
  const check = () => {
    if (signal?.aborted) throw signal.reason ?? new DOMException('Aborted', 'AbortError');
    const time = now();
    if (!Number.isFinite(time) || time < lastTime) throw new LightroomAutomationError('invalid_clock');
    lastTime = time;
    const remaining = timeoutMs - (time - started);
    if (remaining <= 0) throw new LightroomAutomationError('window_timeout');
    return remaining;
  };
  const stage = value => {
    check();
    if (stages.has(value)) log(value);
  };
  const bounded = async operation => {
    const remaining = check();
    let timer, onAbort;
    try {
      const result = await Promise.race([
        Promise.resolve().then(() => { check(); return operation(); }),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new LightroomAutomationError('window_timeout')), remaining);
          if (signal) {
            onAbort = () => reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
            signal.addEventListener('abort', onAbort, { once: true });
          }
        }),
      ]);
      check();
      return result;
    } finally {
      clearTimeout(timer);
      if (onAbort) signal.removeEventListener('abort', onAbort);
    }
  };
  const choose = (apps, targetId) => {
    if (!Array.isArray(apps)) throw new LightroomAutomationError('invalid_app_inventory');
    const candidates = apps.filter(app => app && (targetId !== undefined
      ? app.id === targetId : typeof app.displayName === 'string' && defaultName.test(app.displayName)));
    if (candidates.length > 1) throw new LightroomAutomationError('ambiguous_app');
    const app = candidates[0];
    if (!app) return null;
    if (typeof app.id !== 'string' || app.id.length === 0 || !Array.isArray(app.windows)) {
      throw new LightroomAutomationError('invalid_app_inventory');
    }
    if (app.windows.length > 1) throw new LightroomAutomationError('ambiguous_window');
    if (app.windows.length === 1) {
      const window = app.windows[0];
      if (!window || !Number.isSafeInteger(window.id) || window.id < 1
        || typeof window.app !== 'string' || window.app.length === 0) {
        throw new LightroomAutomationError('invalid_window');
      }
    }
    return app;
  };
  const rehydrate = async app => {
    stage('rehydrating');
    const returned = app.windows[0];
    const window = await bounded(() => sky.get_window({ id: returned.id, app: returned.app }));
    if (!window || window.id !== returned.id || window.app !== returned.app) {
      throw new LightroomAutomationError('window_identity_changed');
    }
    stage('ready');
    return window;
  };

  stage('enumerating');
  const initial = choose(await bounded(() => sky.list_apps()), appId);
  if (!initial) throw new LightroomAutomationError('app_not_found');
  const targetId = initial.id;
  if (initial.windows.length === 1) {
    stage('reusing');
    return rehydrate(initial);
  }
  if (initial.isRunning !== true) {
    stage('launching');
    try {
      await bounded(() => sky.launch_app({ app: targetId }));
    } catch (error) {
      if (signal?.aborted) throw signal.reason ?? error;
      // This one observed false-negative outcome means launch may have succeeded.
      // Other errors (including intentional Escape cancellation) retain identity.
      if (!(error instanceof Error) || error.name !== 'Error'
        || error.message !== `launched app did not expose a targetable window: ${targetId}`) throw error;
      check();
      stage('launch_window_pending');
    }
  }
  for (let poll = 0; poll < maxPolls; poll++) {
    stage('waiting_for_window');
    if (poll > 0) await bounded(() => sleep(Math.min(pollIntervalMs, check()), signal));
    const app = choose(await bounded(() => sky.list_apps()), targetId);
    if (app?.windows.length === 1) return rehydrate(app);
  }
  throw new LightroomAutomationError('window_timeout');
}
