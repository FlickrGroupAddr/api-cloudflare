// Synthetic source tests only: no Sky import, native input, or provider behavior.
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { ACTION, COMMAND, NATIVE_ROOT, createScreenshotDispatchController } from '../scripts/group_post_screenshot_dispatch.mjs';

function fixture() {
  const binding = { coordinationRoot: 'C:\\synthetic\\renewed-attempt', nativeRoot: NATIVE_ROOT,
    runId: '0a8b92d40ed1466fa7de82c1', owner: '1234', generation: 'b'.repeat(32) };
  const identity = { schemaVersion: 1, planVersion: 'fga-group-post-v1', runId: binding.runId,
    owner: binding.owner, generation: binding.generation };
  const c = (name) => path.win32.join(binding.coordinationRoot, name);
  const n = (name) => path.win32.join(binding.nativeRoot, name);
  const records = new Map(); const events = [];
  let now = 1000; let live = true; let failPublish; let afterPublish;
  let clickError = false; let refreshError = false; let captures = 0; let sleeps = 0; let captureDelay = 0; let afterClick; let afterCapture;
  const observation = { window: { id: 5, app: 'synthetic-only' },
    accessibility: { tree: '[1] MenuItem "FGA-LrC15" disabled\n\t[12] MenuItem "Characterize synthetic POST v1"' },
    screenshots: [{ id: 'shot-1', width: 800, height: 600, originX: 100, originY: 200, zIndex: 1, url: 'synthetic-no-image' }] };
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
      assert.deepEqual(input, { window: originalWindow, screenshotId: 'shot-1', x: 420, y: 260 });
      assert.equal(session.fgaPostAttempt.attempted, true); assert.equal(session.state, null);
      assert.equal(JSON.parse(records.get(c('attempted.json'))).requestedInputCount, 1);
      events.push('click'); if (clickError) throw clickError; await afterClick?.();
    },
    async get_window_state(input) {
      assert.deepEqual(input, { window: originalWindow, include_screenshot: true, include_text: false });
      captures += 1; events.push('capture');
      if (captures === 1) { now += captureDelay; await afterCapture?.(); return observation; }
      assert.equal(records.has(c('ack.json')), false);
      if (refreshError) throw refreshError;
      return { window: originalWindow, screenshots: [{ id: 'shot-2', width: 800, height: 600 }] };
    },
  };
  const options = { binding, sky, files, session, clock: () => now,
    sleep: async () => { sleeps += 1; }, randomNonce: () => 'c'.repeat(32) };
  const controller = createScreenshotDispatchController(options);
  const invoke = (extra = {}) => put(c('invoke.json'), { ...identity, action: ACTION, deadlineUnix: now + 30, requestedInputCount: 1, ...extra });
  const dispatch = (extra = {}) => controller.dispatchObserved({ observation, screenshot: observation.screenshots[0], windowFrame: observation.screenshots[0], commandLabel: COMMAND, x: 420, y: 260, inspection: { enabledCommand: true, pointInsideCommand: true, windowFrame: true, targetOwnership: true, mapping: true, soleControl: true, duplicateCrops: [] }, ...extra });
  const ready = async () => { await controller.prewarm(); invoke(); await controller.observe(observation.window); };
  return { binding, identity, c, n, records, events, put, session, observation, options, controller, invoke, dispatch, ready,
    setNow: (value) => { now = value; }, live: (value) => { live = value; },
    fail: (name) => { failPublish = c(name); }, after: (fn) => { afterPublish = fn; },
    clickError: (error = Error('private click detail')) => { clickError = error; },
    refreshError: (error = Error('private screenshot detail')) => { refreshError = error; },
    captureDelay: (value) => { captureDelay = value; }, afterClick: (fn) => { afterClick = fn; },
    afterCapture: (fn) => { afterCapture = fn; }, sleeps: () => sleeps };
}

test('inspected full-window frame dispatches exactly once then immediately refreshes and acknowledges', async () => {
  const f = fixture(); await f.ready();
  const result = await f.dispatch(); assert.equal(result.actualInputCount, 1);
  assert.deepEqual(f.events.slice(f.events.indexOf('click')), ['click', 'capture', 'ack.json']);
  await assert.rejects(f.dispatch()); assert.equal(f.events.filter(x => x === 'click').length, 1);
});
for (const [name, mutate] of [
  ['window clone', f => { f.observation.window = { ...f.observation.window }; }],
  ['array clone', f => { f.observation.screenshots = [...f.observation.screenshots]; }],
  ['shot clone', f => { f.observation.screenshots[0] = { ...f.observation.screenshots[0] }; }],
  ...['id','width','height','originX','originY','zIndex','url'].map(key => [key, f => { f.observation.screenshots[0][key] = 'changed'; }]),
  ['window id', f => { f.observation.window.id++; }],
  ['window app', f => { f.observation.window.app = 'other'; }],
  ['session state', f => { f.session.state = { ...f.observation }; }],
]) test(`${name} mutation refuses before attempted intent`, async () => {
  const f = fixture(); await f.ready(); mutate(f); await assert.rejects(f.dispatch());
  assert.equal(f.records.has(f.c('attempted.json')), false); assert.ok(!f.events.includes('click'));
});
for (const [name, alter, extra] of [
  ['missing geometry', f => { delete f.observation.screenshots[0].originX; }],
  ['duplicate ids', f => { f.observation.screenshots.push({ ...f.observation.screenshots[0] }); }],
  ['overlapping region', f => { f.observation.screenshots.push({ ...f.observation.screenshots[0], id: 'other', zIndex: 2 }); }],
  ['invalid z-order', f => { f.observation.screenshots[0].zIndex = NaN; }],
  ['infinite width', f => { f.observation.screenshots[0].width = Infinity; }],
  ['empty id', f => { f.observation.screenshots[0].id = ''; }],
  ['negative point', null, { x: -1 }], ['right edge', null, { x: 800 }],
  ['bottom edge', null, { y: 600 }], ['NaN point', null, { x: NaN }],
  ['wrong command', null, { commandLabel: 'other command' }],
  ['callback injection', null, { click: () => {} }],
  ['uninspected', null, { inspection: {} }],
]) test(`${name} cannot establish an action`, async () => {
  const f = fixture(); alter?.(f); await f.ready(); await assert.rejects(f.dispatch(extra));
  assert.equal(f.records.has(f.c('attempted.json')), false); assert.ok(!f.events.includes('click'));
});
test('popup cannot obtain mapping by subtracting screen origins', async () => {
  const f = fixture(); const base = f.observation.screenshots[0];
  const popup = { ...base, id: 'popup', originX: 200, originY: 300, width: 200, height: 200, zIndex: 2 };
  f.observation.screenshots.push(popup); await f.ready();
  await assert.rejects(f.dispatch({ screenshot: popup, windowFrame: base, x: 150, y: 150 }));
  assert.ok(!f.events.includes('click'));
});
for (const phase of ['attempted.json','challenge-dispatch.json']) {
  test(`frame changed during ${phase} refuses at final guard and latches`, async () => {
    const f = fixture(); await f.ready(); f.after(file => { if (file === f.c(phase)) f.observation.screenshots[0].originX++; });
    await assert.rejects(f.dispatch()); assert.ok(!f.events.includes('click')); assert.equal(f.session.fgaPostAttempt.stopped, true);
    assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, 0);
    await assert.rejects(f.dispatch());
  });
}
test('input object mutated during intent cannot change original click coordinates', async () => {
  const f = fixture(); await f.ready();
  const input = { observation: f.observation, screenshot: f.observation.screenshots[0], windowFrame: f.observation.screenshots[0], commandLabel: COMMAND,
    x: 420, y: 260, inspection: { enabledCommand: true, pointInsideCommand: true, windowFrame: true, targetOwnership: true, mapping: true, soleControl: true, duplicateCrops: [] } };
  f.after(file => { if (file === f.c('attempted.json')) { input.x = 799; input.commandLabel = 'other'; } });
  assert.equal((await f.controller.dispatchObserved(input)).actualInputCount, 1);
});
for (const kind of ['click','refresh','ack']) test(`${kind} failure is terminal with honest count`, async () => {
  const f = fixture(); await f.ready();
  if (kind === 'click') f.clickError(); if (kind === 'refresh') f.refreshError(); if (kind === 'ack') f.fail('ack.json');
  await assert.rejects(f.dispatch()); assert.equal(f.session.fgaPostAttempt.stopped, true);
  if (kind !== 'ack') assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, kind === 'click' ? null : 1);
  await assert.rejects(f.dispatch()); assert.equal(f.events.filter(x => x === 'click').length, 1);
});
for (const kind of ['expiry','request substitution','stop','owner loss']) test(`${kind} after intent prevents input`, async () => {
  const f = fixture(); await f.ready(); f.after(file => {
    if (file !== f.c('attempted.json')) return;
    if (kind === 'expiry') f.setNow(1031);
    if (kind === 'request substitution') f.invoke({ deadlineUnix: 1029 });
    if (kind === 'stop') f.put(f.n('stop.json'), {});
    if (kind === 'owner loss') f.put(f.c('owner.json'), { ...f.identity, state: 'closed', deadlineUnix: 1900 });
  });
  await assert.rejects(f.dispatch()); assert.ok(!f.events.includes('click')); assert.equal(f.session.fgaPostAttempt.stopped, true);
});
test('capture delay counts against observation age; no second observation under run', async () => {
  const f = fixture(); f.captureDelay(31); await f.controller.prewarm(); f.invoke();
  await assert.rejects(f.controller.observe(f.observation.window));
  await assert.rejects(f.controller.observe(f.observation.window)); assert.equal(f.events.filter(x => x === 'capture').length, 1);
});
test('distinct returned Window with equivalent app/id becomes exact pinned action Window', async () => {
  const f = fixture(); const selected = f.observation.window;
  f.afterCapture(() => { f.observation.window = { ...selected }; });
  await f.controller.prewarm(); f.invoke(); const state = await f.controller.observe(selected);
  assert.notEqual(state.window, selected); assert.equal((await f.dispatch()).actualInputCount, 1);
});
for (const key of ['id', 'app']) test(`returned changed Window ${key} refuses observation`, async () => {
  const f = fixture(); const selected = f.observation.window;
  f.afterCapture(() => { f.observation.window = { ...selected, [key]: key === 'id' ? selected.id + 1 : 'other' }; });
  await f.controller.prewarm(); f.invoke(); await assert.rejects(f.controller.observe(selected));
  assert.ok(!f.events.includes('click'));
});
test('disjoint-looking frames also refuse without documented unit mapping', async () => {
  const f = fixture(); const target = f.observation.screenshots[0];
  f.observation.screenshots.unshift({ ...target, id: 'disjoint', originX: -2000 });
  await f.ready(); await assert.rejects(f.dispatch({ screenshot: target, windowFrame: target })); assert.ok(!f.events.includes('click'));
});

test('visually inspected smaller higher-z duplicate crop permits selected full-window action without origin transforms', async () => {
  const f = fixture(); const full = f.observation.screenshots[0];
  const crop = { ...full, id: 'crop', width: 250, height: 300, originX: 804, originY: 378, zIndex: 2 };
  f.observation.screenshots.push(crop); await f.ready();
  const inspection = { enabledCommand: true, pointInsideCommand: true, windowFrame: true, targetOwnership: true, mapping: true, soleControl: true, duplicateCrops: [crop] };
  assert.equal((await f.dispatch({ inspection })).actualInputCount, 1);
});
for (const kind of ['clone','same-size','lower-z','unlisted']) test(`duplicate crop ${kind} cannot establish relationship`, async () => {
  const f = fixture(); const full = f.observation.screenshots[0];
  const crop = { ...full, id: 'crop', width: 250, height: 300, zIndex: 2 };
  if (kind === 'same-size') { crop.width = full.width; crop.height = full.height; }
  if (kind === 'lower-z') crop.zIndex = 0;
  f.observation.screenshots.push(crop); await f.ready();
  const inspection = { enabledCommand: true, pointInsideCommand: true, windowFrame: true, targetOwnership: true, mapping: true, soleControl: true,
    duplicateCrops: kind === 'unlisted' ? [] : [kind === 'clone' ? { ...crop } : crop] };
  await assert.rejects(f.dispatch({ inspection })); assert.ok(!f.events.includes('click'));
});

test('ambiguous pre-intent refusal terminates the run rather than permitting corrected replay', async () => {
  const f = fixture(); await f.ready(); await assert.rejects(f.dispatch({ x: -1 }));
  assert.equal(f.session.fgaPostAttempt.stopped, true); await assert.rejects(f.dispatch());
  assert.ok(!f.events.includes('click')); assert.equal(f.records.has(f.c('attempted.json')), false);
});
