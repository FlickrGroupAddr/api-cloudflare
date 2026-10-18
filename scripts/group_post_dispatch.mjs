// Node is required only for the supported Computer Use Node REPL integration.
// This module never imports/initializes Sky, discovers windows, or runs a UI loop.
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { setTimeout as pause } from 'node:timers/promises';

export const ACTION = 'invoke_characterize_synthetic_post_v1_once';
export const COMMAND = 'Characterize synthetic POST v1';
export const NATIVE_ROOT = 'C:\\Temp\\FGA-group-post-v1';
const MAX_BYTES = 4096;
const ID_KEYS = ['schemaVersion', 'planVersion', 'runId', 'owner', 'generation'];
function requireValue(ok, code) { if (!ok) throw new Error(code); }
function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|');
}

// Bounded reads use one handle and parse the same bytes. Final-path exclusive
// writes never overwrite. A visible partial/uncertain file is retained and readers
// fail closed; publication is not an atomic-complete JSON claim.
export function nodeFiles(fileSystem = fs) {
  return {
    async read(file, limit) {
      const handle = await fileSystem.open(file, 'r');
      try {
        const buffer = Buffer.alloc(limit + 1);
        const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
        requireValue(bytesRead <= limit, 'coordination_byte_limit');
        return buffer.subarray(0, bytesRead);
      } finally { await handle.close(); }
    },
    async exists(file) {
      try { await fileSystem.lstat(file); return true; }
      catch (error) { if (error.code === 'ENOENT') return false; throw error; }
    },
    async publish(file, value) {
      const bytes = `${JSON.stringify(value)}\n`;
      requireValue(Buffer.byteLength(bytes, 'utf8') <= MAX_BYTES, 'coordination_byte_limit');
      const handle = await fileSystem.open(file, 'wx');
      try { await handle.writeFile(bytes, 'utf8'); await handle.sync(); }
      finally { await handle.close(); }
    },
  };
}

/** All bindings/actions come from the primary's reviewed in-memory cell, never files.
 * session defaults to globalThis so recreating a controller cannot clear its latch.
 * observation must be the immediately preceding inspected supported Sky observation.
 */
export function createDispatchController({ binding, sky, files = nodeFiles(),
  clock = () => Date.now() / 1000,
  sleep = pause, randomNonce = () => randomBytes(16).toString('hex'),
  session = globalThis }) {
  requireValue(exact(binding, ['coordinationRoot', 'nativeRoot', 'runId', 'owner', 'generation']), 'binding_schema');
  const b = Object.freeze({ ...binding });
  requireValue(typeof b.coordinationRoot === 'string' && path.win32.isAbsolute(b.coordinationRoot)
    && !path.win32.normalize(b.coordinationRoot).toLowerCase().startsWith(NATIVE_ROOT.toLowerCase() + '\\')
    && path.win32.normalize(b.coordinationRoot).toLowerCase() !== NATIVE_ROOT.toLowerCase()
    && path.win32.normalize(b.nativeRoot) === NATIVE_ROOT, 'binding_paths');
  requireValue(typeof b.runId === 'string' && typeof b.owner === 'string'
    && typeof b.generation === 'string' && /^[0-9a-f]{24}$/.test(b.runId) && b.runId !== 'c01ba6d2c2754597aa311c9f'
    && /^[1-9][0-9]*$/.test(b.owner) && Number.isSafeInteger(Number(b.owner))
    && /^[0-9a-f]{32}$/.test(b.generation), 'binding_identity');
  requireValue(sky && typeof sky.click === 'function' && typeof sky.get_window_state === 'function', 'sky_required');
  const identity = Object.freeze({ schemaVersion: 1, planVersion: 'fga-group-post-v1',
    runId: b.runId, owner: b.owner, generation: b.generation });
  const coord = (name) => path.win32.join(b.coordinationRoot, name);
  const native = (name) => path.win32.join(b.nativeRoot, name);
  let ready = false;
  let busy = false;
  let lastTime = -Infinity;
  function time() {
    const now = clock();
    requireValue(Number.isFinite(now) && now >= lastTime, 'clock_invalid_or_reversed');
    lastTime = now;
    return now;
  }
  const correlated = (value) => ID_KEYS.every((key) => value[key] === identity[key]);
  async function read(name, keys) {
    const bytes = await files.read(coord(name), MAX_BYTES);
    requireValue(Buffer.byteLength(bytes) <= MAX_BYTES, 'coordination_byte_limit');
    const value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    requireValue(exact(value, [...ID_KEYS, ...keys]) && correlated(value), 'coordination_identity_or_schema');
    return value;
  }
  async function absent(paths) {
    for (const file of paths) requireValue(!await files.exists(file), 'coordination_not_fresh_or_stopped');
  }
  async function active({ invocation = false, allowAttempt = false } = {}) {
    requireValue(!session.fgaPostAttempt?.stopped && (!session.fgaPostAttempt || allowAttempt), 'session_latched');
    await absent([coord('operator-stop.json'), coord('operator-stop.json.tmp'), native('stop.json'), native('stop.json.tmp'),
      native('status.json'), native('status.json.tmp'), coord('ack.json'), coord('ack.json.tmp')]);
    const owner = await read('owner.json', ['state', 'deadlineUnix']);
    requireValue(owner.state === 'active' && Number.isFinite(owner.deadlineUnix)
      && time() < owner.deadlineUnix && owner.deadlineUnix <= time() + 960, 'owner_not_active');
    if (!invocation) return owner;
    const request = await read('invoke.json', ['action', 'deadlineUnix', 'requestedInputCount']);
    const now = time();
    requireValue(request.action === ACTION && request.requestedInputCount === 1
      && Number.isFinite(request.deadlineUnix) && request.deadlineUnix > now
      && request.deadlineUnix <= owner.deadlineUnix && request.deadlineUnix <= now + 30,
    'request_not_active');
    await absent([coord('operator-stop.json'), coord('operator-stop.json.tmp'), native('stop.json'), native('stop.json.tmp'),
      native('status.json'), native('status.json.tmp'), coord('ack.json'), coord('ack.json.tmp')]);
    requireValue(time() < owner.deadlineUnix
      && time() < request.deadlineUnix, 'owner_or_deadline_lost');
    return request;
  }
  async function publish(name, value) { await files.publish(coord(name), { ...identity, ...value }); }
  // One fresh retained challenge per phase proves the attached owner executed a
  // current checkpoint. It does not claim atomic OS process-lifetime knowledge.
  async function checkpoint(phase, deadline) {
    const challengeName = `challenge-${phase}.json`;
    const responseName = `response-${phase}.json`;
    await absent([coord(challengeName), coord(responseName)]);
    const nonce = randomNonce();
    requireValue(typeof nonce === 'string' && /^[0-9a-f]{32}$/.test(nonce), 'nonce_invalid');
    const challenge = { phase, nonce, deadlineUnix: Math.min(time() + 10, deadline) };
    await publish(challengeName, challenge);
    for (let poll = 0; poll < 11; poll += 1) {
      requireValue(!session.fgaPostAttempt?.stopped && time() < challenge.deadlineUnix, 'checkpoint_stopped_or_expired');
      await active({ invocation: phase === 'dispatch', allowAttempt: phase === 'dispatch' });
      if (await files.exists(coord(responseName))) {
        const response = await read(responseName, ['phase', 'nonce', 'deadlineUnix']);
        requireValue(response.phase === phase && response.nonce === nonce
          && response.deadlineUnix === challenge.deadlineUnix && time() < response.deadlineUnix,
        'checkpoint_response_invalid');
        requireValue(!session.fgaPostAttempt?.stopped, 'session_latched');
        return challenge.deadlineUnix;
      }
      if (poll < 10) await sleep(1000);
    }
    throw new Error('checkpoint_response_absent');
  }
  async function stop(reason = 'operator') {
    requireValue(['operator', 'escape', 'unknown'].includes(reason), 'stop_reason');
    session.fgaPostAttempt ??= { ...identity, attempted: false };
    session.fgaPostAttempt.stopped = true;
    session.fgaPostAttempt.reason ??= reason;
    if (!await files.exists(coord('operator-stop.json'))) await publish('operator-stop.json',
      { reason: session.fgaPostAttempt.reason });
  }
  async function prewarm() {
    requireValue(!busy && !ready, 'controller_not_fresh');
    busy = true;
    try {
      await active();
      await absent(['ready.json', 'ready.json.tmp', 'attempted.json', 'attempted.json.tmp',
        'invoke.json', 'writer-check.json', 'writer-check.json.tmp'].map(coord));
      await absent(['target.json', 'target.json.tmp', 'target.used.json', 'target.used.json.tmp',
        'status.json', 'status.json.tmp', 'stop.json', 'stop.json.tmp'].map(native));
      // Retained bounded scratch proves the exact Node writer before cloud lifetime.
      await publish('writer-check.json', { state: 'writer_checked' });
      const probe = await read('writer-check.json', ['state']);
      requireValue(probe.state === 'writer_checked', 'writer_check_failed');
      const owner = await active();
      const checkpointDeadline = await checkpoint('prewarm', owner.deadlineUnix);
      await active();
      requireValue(time() < checkpointDeadline && !session.fgaPostAttempt, 'session_latched');
      await publish('ready.json', { state: 'ready' });
      requireValue(!session.fgaPostAttempt, 'session_latched');
      ready = true;
      return { state: 'ready' };
    } catch {
      try { await stop('unknown'); } catch { /* memory latch survives failed publication */ }
      throw new Error('prewarm_stopped_or_unknown_no_retry');
    } finally { busy = false; }
  }
  async function dispatchObserved({ observation, elementIndex, commandLabel }) {
    requireValue(!busy && ready, 'controller_not_ready');
    busy = true;
    let actualInputCount = 0;
    let attempted = false;
    try {
      requireValue(commandLabel === COMMAND && Number.isSafeInteger(elementIndex) && elementIndex >= 0
        && observation === session.state && observation?.window
        && typeof observation.accessibility?.tree === 'string', 'observed_command_required');
      // Human inspection selects the index; ensure that exact index and label occur
      // together in the supplied latest tree, rather than accepting a label alone.
      const line = observation.accessibility.tree.split('\n').filter((item) =>
        new RegExp(`^\\s*(?:\\[)?${elementIndex}(?:\\]|[.:)])?\\s`).test(item));
      const label = line[0]?.replace(new RegExp(`^\\s*(?:\\[)?${elementIndex}(?:\\]|[.:)])?\\s+`), '');
      requireValue(line.length === 1 && ['MenuItem ' + COMMAND, 'MenuItem ' + JSON.stringify(COMMAND),
        'menu item ' + COMMAND, 'menu item ' + JSON.stringify(COMMAND)].includes(label), 'observed_command_mismatch');
      const request = await active({ invocation: true });
      await absent([coord('attempted.json'), coord('attempted.json.tmp')]);
      requireValue(!session.fgaPostAttempt && observation === session.state, 'session_or_observation_latched');
      session.state = null;
      session.fgaPostAttempt = { ...identity, attempted: true, stopped: false };
      attempted = true;
      await publish('attempted.json', { action: ACTION, deadlineUnix: request.deadlineUnix, requestedInputCount: 1 });
      const checkpointDeadline = await checkpoint('dispatch', request.deadlineUnix);
      const finalRequest = await active({ invocation: true, allowAttempt: true });
      requireValue(JSON.stringify(finalRequest) === JSON.stringify(request), 'request_changed');
      requireValue(!session.fgaPostAttempt.stopped && session.state === null
        && time() < finalRequest.deadlineUnix && time() < checkpointDeadline, 'session_or_deadline_lost');
      // No waits or further file operations intervene between this final check and input.
      actualInputCount = null;
      await sky.click({ window: observation.window, element_index: elementIndex });
      actualInputCount = 1;
      await publish('ack.json', { outcome: 'dispatched', requestedInputCount: 1, actualInputCount });
      const state = await sky.get_window_state({ window: observation.window,
        include_screenshot: true, include_text: true });
      session.state = state;
      return { outcome: 'dispatched', actualInputCount, state };
    } catch {
      if (attempted || session.fgaPostAttempt?.stopped) {
        session.fgaPostAttempt.stopped = true;
        try { await stop('unknown'); } catch { /* memory latch remains authoritative locally */ }
        try {
          if (!await files.exists(coord('ack.json'))) await publish('ack.json',
            { outcome: actualInputCount === 0 ? 'stopped' : 'unknown', requestedInputCount: 1, actualInputCount });
        } catch { /* never retry input after an acknowledgement failure */ }
      }
      throw new Error(attempted ? 'dispatch_stopped_or_unknown_no_retry' : 'dispatch_refused');
    } finally { busy = false; }
  }
  return Object.freeze({ prewarm, dispatchObserved, stop });
}
