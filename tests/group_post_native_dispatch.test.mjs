// Synthetic source tests only: no Sky import, native input, or provider behavior.
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { ACTION, COMMAND, NATIVE_ROOT, observedCommandIndex, createNativeDispatchController } from '../scripts/group_post_native_dispatch.mjs';

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
    screenshots: [{ id: 'shot-1', width: 800, height: 600 }] };
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
      assert.deepEqual(input, { window: originalWindow, element_index: 12 });
      assert.equal(session.fgaPostAttempt.attempted, true); assert.equal(session.state, null);
      assert.equal(JSON.parse(records.get(c('attempted.json'))).requestedInputCount, 1);
      events.push('click'); if (clickError) throw clickError; await afterClick?.();
    },
    async get_window_state(input) {
      assert.deepEqual(input, { window: originalWindow, include_screenshot: true, include_text: true });
      captures += 1; events.push('capture');
      if (captures === 1) { now += captureDelay; await afterCapture?.(); return observation; }
      assert.equal(records.has(c('ack.json')), false);
      if (refreshError) throw refreshError;
      return { window: originalWindow, screenshots: [{ id: 'shot-2', width: 800, height: 600 }] };
    },
  };
  const options = { binding, sky, files, session, clock: () => now,
    sleep: async () => { sleeps += 1; }, randomNonce: () => 'c'.repeat(32) };
  const controller = createNativeDispatchController(options);
  const invoke = (extra = {}) => put(c('invoke.json'), { ...identity, action: ACTION, deadlineUnix: now + 30, requestedInputCount: 1, ...extra });
  const dispatch = (extra = {}) => controller.dispatchObserved({ observation, elementIndex: 12, commandLabel: COMMAND, ...extra });
  const ready = async () => { await controller.prewarm(); invoke(); await controller.observe(observation.window); };
  return { binding, identity, c, n, records, events, put, session, observation, options, controller, invoke, dispatch, ready,
    setNow: (value) => { now = value; }, live: (value) => { live = value; },
    fail: (name) => { failPublish = c(name); }, after: (fn) => { afterPublish = fn; },
    clickError: (error = Error('private click detail')) => { clickError = error; },
    refreshError: (error = Error('private screenshot detail')) => { refreshError = error; },
    captureDelay: (value) => { captureDelay = value; }, afterClick: (fn) => { afterClick = fn; },
    afterCapture: (fn) => { afterCapture = fn; }, sleeps: () => sleeps };
}

for (const prefix of ['[12]', '12:', '12.', '12)', '12']) {
  for (const label of [`MenuItem ${COMMAND}`, `MenuItem "${COMMAND}"`,
    `menu item ${COMMAND}`, `menu item "${COMMAND}"`]) {
    for (const suffix of ['', ' ID: 1', ' ID: 345', ' ID: 9007199254740991']) {
      test(`exact synthetic tree subset ${prefix} ${label}${suffix} yields its index`, () => {
        assert.equal(observedCommandIndex(`\t${prefix} ${label}${suffix}\r\n[1] MenuItem FGA-LrC15 disabled`), 12);
      });
    }
  }
}
for (const [name, tree] of [
  ['absent tree', null], ['empty tree', ''],
  ['header alone', '[12] MenuItem "FGA-LrC15" disabled'],
  ['wrong role', `[12] Button "${COMMAND}"`],
  ['substring label', `[12] MenuItem "${COMMAND} extra"`],
  ['disabled target annotation', `[12] MenuItem "${COMMAND}" disabled`],
  ['unknown state annotation', `[12] MenuItem "${COMMAND}" enabled`],
  ['duplicate command indexes', `[12] MenuItem "${COMMAND}"\n[13] MenuItem "${COMMAND}"`],
  ['disabled matching duplicate', `[12] MenuItem "${COMMAND}"\n[13] MenuItem "${COMMAND}" disabled`],
  ['unsupported matching duplicate', `[12] MenuItem "${COMMAND}"\nMenuItem(name=${COMMAND}, index=13)`],
  ['unindexed matching context', `[12] MenuItem "${COMMAND}"\nMenu ${COMMAND}`],
  ['reused index', `[12] MenuItem "${COMMAND}"\n[12] Button other`],
  ['unsafe integer index', `[9007199254740992] MenuItem "${COMMAND}"`],
  ['invented malformed index', `[12) MenuItem "${COMMAND}"`],
]) test(`${name} cannot establish a command target`, () => {
  assert.throws(() => observedCommandIndex(tree));
});

for (const suffix of [' ID: ', ' ID: 0', ' ID: -1', ' ID: +1', ' ID: 01',
  ' ID: 1.0', ' ID: 1e2', ' ID: 0x12', ' ID: NaN', ' ID: Infinity',
  ' ID: 9007199254740992', ` ID: ${'9'.repeat(100)}`, ' ID: １２',
  ' ID: 1 ', ' ID: 1\t', ' ID: 1\r', ' ID: 1\u2028', ' ID: 1\u2029',
  ' ID: 1 disabled', ' disabled ID: 1', ' ID: 1 enabled', ' enabled ID: 1',
  ' ID: 1 ID: 2', ' ID: 1 other', ' ID:1', ' ID:  1', ' id: 1']) {
  test(`hostile ID suffix ${JSON.stringify(suffix)} cannot establish a target`, () => {
    assert.throws(() => observedCommandIndex(`12 menu item ${COMMAND}${suffix}`));
  });
}

for (const other of [`13 menu item ${COMMAND} ID: 7`,
  `13 menu item ${COMMAND} disabled ID: 7`, `13 menu item ${COMMAND} ID: -1`,
  `MenuItem(name=${COMMAND}, index=13)`, '12 Button other ID: 7']) {
  test(`annotated target rejects duplicate command or reused index: ${other}`, () => {
    assert.throws(() => observedCommandIndex(`12 menu item ${COMMAND} ID: 7\n${other}`));
  });
}

test('ID annotation does not replace the safe unique click index', () => {
  assert.equal(observedCommandIndex(`0 menu item ${COMMAND} ID: 345`), 0);
  assert.throws(() => observedCommandIndex(`9007199254740992 menu item ${COMMAND} ID: 1`));
});

for (const row of [`12 menu item ${COMMAND} ID: 40228`,
  `\t[12] MenuItem "${COMMAND}" ID: 9007199254740991`]) {
  for (const count of [2, 3]) test(`${count} byte-identical ID-bearing references identify one index: ${row}`, () => {
    const tree = ['[1] MenuItem other', ...Array(count).fill(row), '[99] Button other'].join('\r\n');
    assert.equal(observedCommandIndex(tree), 12);
  });
}

const repeatedRow = `12 menu item ${COMMAND} ID: 40228`;
const repeatedConflicts = [
  ['different index', `13 menu item ${COMMAND} ID: 40228`],
  ['different role', `12 Button ${COMMAND} ID: 40228`],
  ['different role spelling', `12 MenuItem ${COMMAND} ID: 40228`],
  ['different full label', `12 menu item ${COMMAND} extra ID: 40228`],
  ['different quoting', `12 menu item "${COMMAND}" ID: 40228`],
  ['different ID', `12 menu item ${COMMAND} ID: 40229`],
  ['missing ID', `12 menu item ${COMMAND}`],
  ['disabled reference', `${repeatedRow} disabled`],
  ['disabled before ID', `12 menu item ${COMMAND} disabled ID: 40228`],
  ['unknown annotation', `${repeatedRow} unknown`],
  ['unknown target format', `MenuItem(name=${COMMAND}, index=12, ID=40228)`],
  ['different indentation', `\t${repeatedRow}`],
  ['different index notation', `[12] menu item ${COMMAND} ID: 40228`],
  ['index collision with distinct row', '12 Button other ID: 40228'],
  ['index collision without ID', '[12] MenuItem other'],
  ['unsupported index collision', '[12]Button other'],
  ['mismatched bracket index collision', '[12) Button other'],
  ['space before bracket index collision', '[12 ] Button other'],
  ['space after bracket index collision', '[ 12] Button other'],
  ['leading zero index collision', '[012] Button other'],
  ['unclosed bracket index collision', '[12 Button other'],
  ['unknown bracket suffix collision', '[12unknown Button other'],
  ['empty index collision', '12'],
  ['unindexed target context', `Menu ${COMMAND}`],
  ['second occurrence in row', `${repeatedRow} ${COMMAND}`],
];
for (const [name, conflict] of repeatedConflicts) {
  test(`repeated references reject ${name} before durable intent or input`, async () => {
    const f = fixture(); f.observation.accessibility.tree = `${repeatedRow}\n${repeatedRow}\n${conflict}`;
    assert.throws(() => observedCommandIndex(f.observation.accessibility.tree));
    await f.ready(); await assert.rejects(f.dispatch());
    assert.equal(f.records.has(f.c('attempted.json')), false);
    assert.equal(f.events.includes('click'), false);
  });
}

test('identical references without an ID cannot establish one element', () => {
  const row = `12 menu item ${COMMAND}`;
  assert.throws(() => observedCommandIndex(`${row}\n${row}`));
});

test('malformed non-command references to a different index do not become target collisions', () => {
  assert.equal(observedCommandIndex(`${repeatedRow}\n[13) Button other\n${repeatedRow}`), 12);
});

test('repeated-reference dispatch retains the whole observation and performs one indexed input without replay', async () => {
  const f = fixture();
  const tree = `[1] MenuItem other\n${repeatedRow}\n[40] Button other\n${repeatedRow}`;
  f.observation.accessibility.tree = tree;
  await f.ready(); assert.equal(f.session.state, f.observation);
  const start = f.events.length;
  const result = await f.dispatch(); assert.equal(result.actualInputCount, 1);
  assert.equal(f.observation.accessibility.tree, tree);
  assert.deepEqual(f.events.slice(start), ['attempted.json', 'challenge-dispatch.json', 'click', 'capture', 'ack.json']);
  await assert.rejects(f.dispatch()); await assert.rejects(f.controller.observe(f.observation.window));
  assert.equal(f.events.filter((event) => event === 'click').length, 1);
  assert.equal(f.events.filter((event) => event === 'capture').length, 2);
});

test('editing the captured repeated tree during checkpoint permanently refuses input', async () => {
  const f = fixture(); f.observation.accessibility.tree = `${repeatedRow}\n${repeatedRow}`;
  await f.ready();
  f.after((file) => { if (file === f.c('challenge-dispatch.json')) f.observation.accessibility.tree = repeatedRow; });
  await assert.rejects(f.dispatch(), /no_retry/); await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
});

test('observation requires an active correlated invocation before capture', async () => {
  const f = fixture(); await f.controller.prewarm();
  await assert.rejects(f.controller.observe(f.observation.window));
  assert.equal(f.events.includes('capture'), false);
  f.invoke(); await assert.rejects(f.controller.observe(f.observation.window));
});

test('controller permits only one observation and cannot refresh its age or index', async () => {
  const f = fixture(); await f.ready();
  await assert.rejects(f.controller.observe(f.observation.window));
  assert.equal(f.events.filter((event) => event === 'capture').length, 1);
  const result = await f.dispatch(); assert.equal(result.actualInputCount, 1);
});

for (const state of [null, {}, { tree: '' }]) test(`missing or empty accessibility cannot dispatch (${JSON.stringify(state)})`, async () => {
  const f = fixture(); f.observation.accessibility = state;
  await f.controller.prewarm(); f.invoke();
  if (typeof state?.tree !== 'string') await assert.rejects(f.controller.observe(f.observation.window));
  else { await f.controller.observe(f.observation.window); await assert.rejects(f.dispatch()); }
  assert.equal(f.events.includes('click'), false); assert.equal(f.records.has(f.c('attempted.json')), false);
});

test('unsupported actual tree format refuses instead of falling back to coordinates', async () => {
  const f = fixture(); f.observation.accessibility.tree = `MenuItem(name=${COMMAND}, index=12)`;
  await f.ready(); await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false); assert.equal(f.records.has(f.c('attempted.json')), false);
});

for (const duplicate of [`[13] MenuItem "${COMMAND}" disabled`, `MenuItem(name=${COMMAND}, index=13)`]) {
  test(`matching duplicate cannot dispatch: ${duplicate}`, async () => {
    const f = fixture(); f.observation.accessibility.tree += '\n' + duplicate;
    await f.ready(); await assert.rejects(f.dispatch());
    assert.equal(f.events.includes('click'), false); assert.equal(f.records.has(f.c('attempted.json')), false);
  });
}

test('replacement invoke cannot extend the original observed expired request', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke({ deadlineUnix: 1010 });
  await f.controller.observe(f.observation.window); f.setNow(1011); f.invoke({ deadlineUnix: 1030 });
  await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false); assert.equal(f.records.has(f.c('attempted.json')), false);
});

test('even an unexpired shortened replacement request cannot substitute observation authority', async () => {
  const f = fixture(); await f.ready(); f.invoke({ deadlineUnix: 1020 });
  await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false); assert.equal(f.records.has(f.c('attempted.json')), false);
});

for (const delay of [0, 11]) test(`request replacement during capture refuses (${delay}s delay)`, async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke({ deadlineUnix: 1010 }); f.captureDelay(delay);
  f.afterCapture(() => f.invoke({ deadlineUnix: 1030 }));
  await assert.rejects(f.controller.observe(f.observation.window), /observed_request_changed_or_expired/);
  await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false); assert.equal(f.records.has(f.c('attempted.json')), false);
});

for (const expire of [false, true]) test(`request replacement during checkpoint cannot alter original binding (expired=${expire})`, async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke({ deadlineUnix: 1010 });
  await f.controller.observe(f.observation.window);
  f.after((file) => {
    if (file === f.c('challenge-dispatch.json')) {
      if (expire) f.setNow(1011);
      f.invoke({ deadlineUnix: 1030 });
    }
  });
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.events.includes('click'), false); assert.equal(f.session.fgaPostAttempt.stopped, true);
  await assert.rejects(f.dispatch());
});

for (const suffix of ['', ' ID: 345']) test(`fresh exact menu item${suffix} dispatches once after durable intent, then immediate capture and ack`, async () => {
  const f = fixture();
  f.observation.accessibility.tree = `12 menu item ${COMMAND}${suffix}`;
  await f.ready(); const start = f.events.length;
  const result = await f.dispatch(); assert.equal(result.outcome, 'dispatched');
  assert.deepEqual(f.events.slice(start), ['attempted.json', 'challenge-dispatch.json', 'click', 'capture', 'ack.json']);
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, 1);
  await assert.rejects(f.dispatch());
  assert.equal(f.events.filter((x) => x === 'click').length, 1);
});

for (const suffix of [' ID: -1', ' ID: 345 disabled', ' disabled ID: 345', ' ID: 345 unknown']) {
  test(`unsupported annotated target${suffix} refuses before durable intent or input`, async () => {
    const f = fixture(); f.observation.accessibility.tree = `12 menu item ${COMMAND}${suffix}`;
    await f.ready(); await assert.rejects(f.dispatch());
    assert.equal(f.records.has(f.c('attempted.json')), false);
    assert.equal(f.events.includes('click'), false);
  });
}

for (const [name, params] of [
  ['old coordinate action', { screenshotId: 'shot-1', x: 100, y: 200 }],
  ['wrong exact command', { commandLabel: COMMAND + ' extra' }],
  ['header index', { elementIndex: 1 }], ['negative index', { elementIndex: -1 }],
  ['unknown index', { elementIndex: 800 }], ['fractional index', { elementIndex: 12.5 }],
  ['NaN', { elementIndex: NaN }], ['infinity', { elementIndex: Infinity }], ['string index', { elementIndex: '12' }],
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
  const f = fixture(); f.captureDelay(31); await assert.rejects(f.ready()); await assert.rejects(f.dispatch());
  assert.equal(f.events.includes('click'), false);
});

test('original request deadline expiry after owner checkpoint stops input', async () => {
  const f = fixture(); await f.ready(); f.setNow(1020);
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
  ['accessibility replacement', (f) => { f.observation.accessibility = { ...f.observation.accessibility }; }],
  ['accessibility text', (f) => { f.observation.accessibility.tree += '\n[13] MenuItem other'; }],
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


// These errors deliberately carry forbidden dynamic fields. No property may be
// read, retained or forwarded by the diagnostic path (including during cleanup).
function hostileFailure() {
  const secret = 'Bearer synthetic-secret-token C:\\private\\photo.jpg';
  const error = { secret };
  for (const key of ['message', 'stack', 'cause', 'code', 'title', 'path']) {
    Object.defineProperty(error, key, { get() { throw Error(secret); } });
  }
  return error;
}

for (const [name, inject, stage, failureClass, count] of [
  ['click', (f) => f.clickError(hostileFailure()), 'click_pending', 'click_call_did_not_return', null],
  ['refresh', (f) => f.refreshError(hostileFailure()), 'refresh_pending', 'refresh_call_did_not_return', 1],
  ['window check', (f) => f.afterClick(() => { f.observation.window.title = 'private-title'; }),
    'post_click_window_check', 'post_click_window_check_failed', 1],
  ['ack', (f) => f.fail('ack.json'), 'ack_publication', 'ack_publication_failed', 1],
  ['attempt', (f) => f.fail('attempted.json'), 'attempted_publication', 'local_guard_or_coordination_failure', 0],
  ['checkpoint', (f) => f.live(false), 'dispatch_checkpoint', 'local_guard_or_coordination_failure', 0],
  ['final guard', (f) => f.after((file) => {
    if (file === f.c('challenge-dispatch.json')) f.observation.window.title = 'private-title';
  }), 'final_guard', 'local_guard_or_coordination_failure', 0],
]) test(`closed ${name} diagnostic preserves counts and its original failure boundary`, async () => {
  const f = fixture(); await f.ready();
  assert.equal(f.controller.getFailureDiagnostic(), null);
  inject(f);
  await assert.rejects(f.dispatch(), /^Error: dispatch_stopped_or_unknown_no_retry$/);
  const diagnostic = f.controller.getFailureDiagnostic();
  assert.deepEqual(diagnostic, { stage, failureClass });
  assert.equal(Object.isFrozen(diagnostic), true);
  assert.throws(() => { diagnostic.stage = 'private-title'; }, TypeError);
  if (name !== 'ack') {
    const ack = JSON.parse(f.records.get(f.c('ack.json')));
    assert.equal(ack.actualInputCount, count);
    assert.equal(ack.outcome, count === 0 ? 'stopped' : 'unknown');
  } else assert.equal(f.records.has(f.c('ack.json')), false);
  await assert.rejects(f.dispatch());
  assert.equal(f.controller.getFailureDiagnostic(), diagnostic);
  assert.equal(f.events.filter((event) => event === 'click').length, count === 0 ? 0 : 1);
  // Receipts retain their exact existing schemas; diagnostic data is memory only.
  for (const [file, bytes] of f.records) {
    const record = JSON.parse(bytes);
    assert.equal(Object.hasOwn(record, 'stage'), false);
    assert.equal(Object.hasOwn(record, 'failureClass'), false);
    assert.doesNotMatch(bytes.toString(), /synthetic-secret-token|private-title|private.click.detail/);
  }
});

test('failed stop and unknown ack cleanup cannot overwrite click diagnostic or retry input', async () => {
  const f = fixture(); await f.ready(); f.clickError(hostileFailure());
  const publish = f.options.files.publish;
  f.options.files.publish = async (file, value) => {
    if (file === f.c('operator-stop.json') || file === f.c('ack.json')) throw hostileFailure();
    await publish(file, value);
  };
  await assert.rejects(f.dispatch(), /^Error: dispatch_stopped_or_unknown_no_retry$/);
  const diagnostic = f.controller.getFailureDiagnostic();
  assert.deepEqual(diagnostic, { stage: 'click_pending', failureClass: 'click_call_did_not_return' });
  assert.equal(f.session.fgaPostAttempt.stopped, true);
  assert.equal(f.records.has(f.c('ack.json')), false);
  assert.equal(f.records.has(f.c('operator-stop.json')), false);
  await assert.rejects(f.dispatch());
  assert.equal(f.controller.getFailureDiagnostic(), diagnostic);
  assert.equal(f.events.filter((event) => event === 'click').length, 1);
});

test('pre-attempt refusal has a closed guard diagnostic and cannot hide later input uncertainty', async () => {
  const f = fixture(); await f.ready();
  await assert.rejects(f.dispatch({ elementIndex: -1 }), /^Error: dispatch_refused$/);
  assert.deepEqual(f.controller.getFailureDiagnostic(), {
    stage: 'request_guard', failureClass: 'local_guard_or_coordination_failure',
  });
  assert.equal(f.records.has(f.c('attempted.json')), false);
  f.clickError(hostileFailure());
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.deepEqual(f.controller.getFailureDiagnostic(), {
    stage: 'click_pending', failureClass: 'click_call_did_not_return',
  });
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, null);
});

test('successful dispatch leaves failure diagnostic unavailable', async () => {
  const f = fixture(); await f.ready(); await f.dispatch();
  assert.equal(f.controller.getFailureDiagnostic(), null);
});


for (const thrown of [null, undefined, 'Bearer synthetic-secret-token',
  Object.assign(Error('Bearer synthetic-secret-token'), {
    code: 'invented-Sky-code', cause: { path: 'C:\\private\\photo.jpg' },
  })]) test('arbitrary thrown input values do not supply diagnostic causes or fields', async () => {
  const f = fixture(); await f.ready();
  f.afterClick(() => { throw thrown; });
  await assert.rejects(f.dispatch(), /^Error: dispatch_stopped_or_unknown_no_retry$/);
  assert.deepEqual(f.controller.getFailureDiagnostic(), {
    stage: 'click_pending', failureClass: 'click_call_did_not_return',
  });
  const ack = JSON.parse(f.records.get(f.c('ack.json')));
  assert.equal(ack.outcome, 'unknown'); assert.equal(ack.actualInputCount, null);
});
