// Synthetic source tests only: no Sky import, native input, or provider behavior.
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { ACTION, COMMAND, NATIVE_ROOT, createNativeDispatchController } from '../scripts/group_post_native_dispatch.mjs';

function fixture() {
  const binding = { coordinationRoot: 'C:\\synthetic\\renewed-attempt', nativeRoot: NATIVE_ROOT,
    runId: '0a8b92d40ed1466fa7de82c1', owner: '1234', generation: 'b'.repeat(32) };
  const identity = { schemaVersion: 1, planVersion: 'fga-group-post-v1', runId: binding.runId,
    owner: binding.owner, generation: binding.generation };
  const c = (name) => path.win32.join(binding.coordinationRoot, name);
  const n = (name) => path.win32.join(binding.nativeRoot, name);
  const records = new Map(); const events = [];
  let now = 1000; let live = true; let failPublish; let afterPublish;
  let clickError = false; let refreshError = false; let captures = 0; let sleeps = 0; let captureDelay = 0; let afterClick;
  const observation = { window: { id: 5, app: 'synthetic-only' }, screenshots: [{ id: 'shot-1', width: 800, height: 600 }] };
  const originalWindow = observation.window;
  const session = {};
  const put = (file, value) => records.set(file, Buffer.from(JSON.stringify(value)));
  put(c('owner.json'), { ...identity, state: 'active', deadlineUnix: 1900 });
  const files = {
    async read(file, limit) { assert.equal(limit, 4096); if (!records.has(file)) throw Error('missing'); return records.get(file); },
    async exists(file) { return records.has(file); },
    async publish(file, value) {
      events.push(path.win32.basename(file));
      if (file === failPublish || records.has(file)) throw Error('exclusive_publication_failed');
      put(file, value);
      if (file.includes('challenge-') && live) put(file.replace('challenge-', 'response-'), value);
      await afterPublish?.(file);
    },
  };
  const sky = {
    async click(input) {
      assert.deepEqual(input, { window: originalWindow, screenshotId: 'shot-1', x: 100, y: 200 });
      assert.equal(session.fgaPostAttempt.attempted, true); assert.equal(session.state, null);
      assert.equal(JSON.parse(records.get(c('attempted.json'))).requestedInputCount, 1);
      events.push('click'); if (clickError) throw Error('private click detail'); await afterClick?.();
    },
    async get_window_state(input) {
      assert.equal(input.window, originalWindow); captures += 1; events.push('capture');
      if (captures === 1) { now += captureDelay; return observation; }
      assert.equal(records.has(c('ack.json')), false);
      if (refreshError) throw Error('private screenshot detail');
      return { window: originalWindow, screenshots: [{ id: 'shot-2', width: 800, height: 600 }] };
    },
  };
  const options = { binding, sky, files, session, clock: () => now,
    sleep: async () => { sleeps += 1; }, randomNonce: () => 'c'.repeat(32) };
  const controller = createNativeDispatchController(options);
  const invoke = (extra = {}) => put(c('invoke.json'), { ...identity, action: ACTION, deadlineUnix: now + 30, requestedInputCount: 1, ...extra });
  const dispatch = (extra = {}) => controller.dispatchObserved({ observation, screenshotId: 'shot-1', x: 100, y: 200, commandLabel: COMMAND, ...extra });
  const ready = async () => { await controller.prewarm(); await controller.observe(observation.window); invoke(); };
  return { binding, identity, c, n, records, events, put, session, observation, options, controller, invoke, dispatch, ready,
    setNow: (value) => { now = value; }, live: (value) => { live = value; },
    fail: (name) => { failPublish = c(name); }, after: (fn) => { afterPublish = fn; },
    clickError: () => { clickError = true; }, refreshError: () => { refreshError = true; },
    captureDelay: (value) => { captureDelay = value; }, afterClick: (fn) => { afterClick = fn; }, sleeps: () => sleeps };
}

test('fresh inspected screenshot dispatches once after durable intent, then immediate capture and ack', async () => {
  const f = fixture(); await f.ready(); const start = f.events.length;
  const result = await f.dispatch(); assert.equal(result.outcome, 'dispatched');
  assert.deepEqual(f.events.slice(start), ['attempted.json', 'challenge-dispatch.json', 'click', 'capture', 'ack.json']);
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, 1);
  await assert.rejects(f.dispatch());
  assert.equal(f.events.filter((x) => x === 'click').length, 1);
});

for (const [name, params] of [
  ['unknown screenshot', { screenshotId: 'unobserved' }], ['wrong exact command', { commandLabel: COMMAND + ' extra' }],
  ['negative x', { x: -1 }], ['negative y', { y: -1 }], ['x outside image', { x: 800 }], ['y outside image', { y: 600 }],
  ['NaN', { x: NaN }], ['infinity', { y: Infinity }], ['string coordinate', { x: '100' }],
]) test(`${name} refuses before intent or input`, async () => {
  const f = fixture(); await f.ready(); await assert.rejects(f.dispatch(params));
  assert.equal(f.records.has(f.c('attempted.json')), false); assert.equal(f.events.includes('click'), false);
});

for (const [name, mutate] of [
  ['replacement state reference', (f) => { f.session.state = { ...f.observation }; }],
  ['observation age exceeds limit', (f) => { f.setNow(1031); f.invoke(); }],
  ['reversed clock', (f) => { f.setNow(999); }],
  ['missing dimensions', (f) => { delete f.observation.screenshots[0].width; }],
  ['foreign generation', (f) => { f.invoke({ generation: 'e'.repeat(32) }); }],
  ['wrong requested count', (f) => { f.invoke({ requestedInputCount: 2 }); }],
  ['unrecognized authority field', (f) => { f.invoke({ command: 'arbitrary' }); }],
  ['expired action', (f) => { f.invoke({ deadlineUnix: 1000 }); }],
  ['native stop', (f) => { f.records.set(f.n('stop.json.tmp'), Buffer.from('')); }],
]) test(`${name} refuses without click`, async () => {
  const f = fixture(); await f.ready(); mutate(f); await assert.rejects(f.dispatch()); assert.equal(f.events.includes('click'), false);
});

test('a manually assigned observation cannot substitute for controller capture', async () => {
  const f = fixture(); await f.controller.prewarm(); f.session.state = f.observation; f.invoke();
  await assert.rejects(f.dispatch()); assert.equal(f.events.includes('click'), false);
});

for (const [name, mutate] of [
  ['stop signal', (f) => f.put(f.n('stop.json'), {})],
  ['observation replacement', (f) => { f.session.state = {}; }],
  ['observation expiry', (f) => { f.setNow(1031); }],
  ['action replacement', (f) => f.invoke({ action: 'other' })],
]) test(`${name} after durable intent stops permanently before input`, async () => {
  const f = fixture(); await f.ready();
  f.after((file) => { if (file === f.c('attempted.json')) mutate(f); });
  await assert.rejects(f.dispatch(), /no_retry/); assert.equal(f.events.includes('click'), false);
  assert.equal(f.session.fgaPostAttempt.stopped, true); await assert.rejects(f.dispatch());
});

for (const phase of ['attempted.json', 'ack.json']) test(`${phase} publication failure cannot replay input`, async () => {
  const f = fixture(); await f.ready(); f.fail(phase); await assert.rejects(f.dispatch(), /no_retry/);
  const expected = phase === 'attempted.json' ? 0 : 1;
  const replacement = createNativeDispatchController(f.options); await assert.rejects(replacement.prewarm());
  assert.equal(f.events.filter((x) => x === 'click').length, expected);
});

test('unknown input result preserves unknown count and terminal stop without private error', async () => {
  const f = fixture(); await f.ready(); f.clickError();
  await assert.rejects(f.dispatch(), /^Error: dispatch_stopped_or_unknown_no_retry$/);
  const ack = JSON.parse(f.records.get(f.c('ack.json')));
  assert.equal(ack.outcome, 'unknown'); assert.equal(ack.actualInputCount, null);
  assert.equal(f.session.fgaPostAttempt.stopped, true); await assert.rejects(f.dispatch());
  assert.equal(f.events.filter((x) => x === 'click').length, 1);
});

test('failed post-input observation records unknown outcome with one input and stops without replay', async () => {
  const f = fixture(); await f.ready(); f.refreshError(); await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).outcome, 'unknown');
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, 1);
  assert.equal(JSON.parse(f.records.get(f.c('operator-stop.json'))).reason, 'unknown');
  await assert.rejects(f.dispatch()); assert.equal(f.events.filter((x) => x === 'click').length, 1);
});

test('slow capture cannot reset the observation age after capture completes', async () => {
  const f = fixture(); f.captureDelay(31); await f.ready(); await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false);
});

test('observation expiry after owner checkpoint stops even with action deadline still valid', async () => {
  const f = fixture(); await f.ready(); f.setNow(1020); f.invoke();
  f.after((file) => { if (file === f.c('attempted.json')) f.setNow(1031); });
  await assert.rejects(f.dispatch(), /no_retry/); assert.equal(f.events.includes('click'), false);
});

test('Escape stop is terminal and retained intent prevents new-session replay', async () => {
  const f = fixture(); await f.ready(); await f.controller.stop('escape'); await assert.rejects(f.dispatch());
  const replacement = createNativeDispatchController({ ...f.options, session: {} });
  await assert.rejects(replacement.prewarm()); assert.equal(f.events.includes('click'), false);
});

test('missing current owner checkpoint stops after finite polling without click', async () => {
  const f = fixture(); await f.ready(); f.live(false); await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.sleeps(), 10); assert.equal(f.session.fgaPostAttempt.stopped, true); assert.equal(f.events.includes('click'), false);
});

test('closed original identity remains forbidden', () => {
  const f = fixture(); assert.throws(() => createNativeDispatchController({ ...f.options,
    binding: { ...f.binding, runId: 'c01ba6d2c2754597aa311c9f' } }), /binding_identity/);
});

const observationMutations = [
  ['window replacement', (f) => { f.observation.window = { ...f.observation.window }; }],
  ['window id', (f) => { f.observation.window.id = 999; }],
  ['window app', (f) => { f.observation.window.app = 'fabricated'; }],
  ['window title', (f) => { f.observation.window.title = 'fabricated'; }],
  ['screenshot array', (f) => { f.observation.screenshots = [...f.observation.screenshots]; }],
  ['screenshot entry', (f) => { f.observation.screenshots[0] = { ...f.observation.screenshots[0] }; }],
  ['screenshot id', (f) => { f.observation.screenshots[0].id = 'fabricated'; }],
  ['screenshot width', (f) => { f.observation.screenshots[0].width = 900; }],
  ['screenshot origin', (f) => { f.observation.screenshots[0].originX = 42; }],
  ['screenshot length', (f) => { f.observation.screenshots.push({ id: 'added' }); }],
];

for (const [name, mutate] of observationMutations) {
  test(`mutated ${name} before intent cannot substitute captured authority`, async () => {
    const f = fixture(); await f.ready(); mutate(f); await assert.rejects(f.dispatch());
    assert.equal(f.records.has(f.c('attempted.json')), false); assert.equal(f.events.includes('click'), false);
  });
  test(`mutated ${name} during awaited checkpoint permanently stops before input`, async () => {
    const f = fixture(); await f.ready();
    f.after((file) => { if (file === f.c('challenge-dispatch.json')) mutate(f); });
    await assert.rejects(f.dispatch(), /no_retry/); assert.equal(f.events.includes('click'), false);
    assert.equal(f.session.fgaPostAttempt.stopped, true); await assert.rejects(f.dispatch());
  });
}

for (const [name, mutate] of observationMutations.filter(([name]) => !['window id', 'window app', 'window title'].includes(name))) {
  test(`post-click ${name} still immediately refreshes original returned Window`, async () => {
    const f = fixture(); await f.ready(); f.afterClick(() => mutate(f));
    const start = f.events.length; const result = await f.dispatch();
    assert.equal(result.outcome, 'dispatched');
    assert.deepEqual(f.events.slice(start), ['attempted.json', 'challenge-dispatch.json', 'click', 'capture', 'ack.json']);
  });
}

for (const key of ['id', 'app', 'title']) test(`post-click original Window ${key} mutation stops with unknown single-input receipt`, async () => {
  const f = fixture(); await f.ready(); f.afterClick(() => { f.observation.window[key] = 'fabricated'; });
  const start = f.events.length; await assert.rejects(f.dispatch(), /no_retry/);
  const ack = JSON.parse(f.records.get(f.c('ack.json')));
  assert.equal(ack.outcome, 'unknown'); assert.equal(ack.actualInputCount, 1);
  assert.equal(f.events.slice(start).includes('capture'), false);
  assert.equal(f.session.fgaPostAttempt.stopped, true); await assert.rejects(f.dispatch());
});

test('post-click session state replacement still refreshes original Window immediately', async () => {
  const f = fixture(); await f.ready(); f.afterClick(() => { f.session.state = { window: { id: 999 } }; });
  const start = f.events.length; const result = await f.dispatch(); assert.equal(result.outcome, 'dispatched');
  assert.deepEqual(f.events.slice(start), ['attempted.json', 'challenge-dispatch.json', 'click', 'capture', 'ack.json']);
  assert.equal(f.session.state.window.id, 5);
});
