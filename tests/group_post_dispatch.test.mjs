import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { ACTION, COMMAND, NATIVE_ROOT, createDispatchController, nodeFiles } from '../scripts/group_post_dispatch.mjs';

function fixture() {
  const binding = { coordinationRoot: 'C:\\private\\fresh-dispatch', nativeRoot: NATIVE_ROOT,
    runId: 'a'.repeat(24), owner: '1234', generation: 'b'.repeat(32) };
  const identity = { schemaVersion: 1, planVersion: 'fga-group-post-v1',
    runId: binding.runId, owner: binding.owner, generation: binding.generation };
  const c = (name) => path.win32.join(binding.coordinationRoot, name);
  const n = (name) => path.win32.join(binding.nativeRoot, name);
  const records = new Map();
  const events = [];
  let now = 1000;
  let live = true;
  let probe;
  let sleepCount = 0;
  let clickError = false;
  let refreshError = false;
  let failPublish;
  let afterPublish;
  const put = (file, value) => records.set(file, Buffer.from(JSON.stringify(value)));
  put(c('owner.json'), { ...identity, state: 'active', deadlineUnix: 1900 });
  const files = {
    async read(file, limit) {
      assert.equal(limit, 4096);
      if (!records.has(file)) throw new Error('missing');
      return records.get(file);
    },
    async exists(file) {
      if (file.includes('response-') && records.has(file)) probe?.();
      return records.has(file);
    },
    async publish(file, value) {
      events.push(path.win32.basename(file));
      if (file === failPublish || records.has(file)) throw new Error('publish_refused');
      put(file, value);
      if (file.includes('challenge-') && live) put(file.replace('challenge-', 'response-'), value);
      await afterPublish?.(file);
    },
  };
  const observation = { window: { app: 'returned Lightroom', id: 5 },
    accessibility: { tree: `  [12] MenuItem ${COMMAND}\n  [13] MenuItem Other` } };
  const session = { state: observation };
  const sky = {
    async click(input) {
      assert.deepEqual(input, { window: observation.window, element_index: 12 });
      assert.equal(session.fgaPostAttempt.attempted, true);
      assert.equal(session.state, null);
      assert.equal(JSON.parse(records.get(c('attempted.json'))).requestedInputCount, 1);
      events.push('click');
      if (clickError) throw new Error('private native error');
    },
    async get_window_state(input) {
      assert.equal(input.window, observation.window);
      assert.equal(records.has(c('ack.json')), true);
      events.push('refresh');
      if (refreshError) throw new Error('private capture error');
      return { window: observation.window, accessibility: null };
    },
  };
  const options = { binding, files, clock: () => now, sleep: async () => { sleepCount += 1; }, randomNonce: () => 'c'.repeat(32), sky, session };
  const controller = createDispatchController(options);
  const invoke = (extra = {}) => put(c('invoke.json'), { ...identity, action: ACTION,
    deadlineUnix: 1030, requestedInputCount: 1, ...extra });
  const dispatch = () => controller.dispatchObserved({ observation, elementIndex: 12, commandLabel: COMMAND });
  return { binding, identity, c, n, records, events, put, session, options, controller, invoke, dispatch,
    sleeps: () => sleepCount, onProbe: (fn) => { probe = fn; }, setNow: (value) => { now = value; }, setLive: (value) => { live = value; },
    setClickError: () => { clickError = true; }, setRefreshError: () => { refreshError = true; },
    fail: (name) => { failPublish = c(name); }, after: (fn) => { afterPublish = fn; } };
}

test('prewarm rehearses the exact writer before ready, without native calls', async () => {
  const f = fixture();
  assert.deepEqual(await f.controller.prewarm(), { state: 'ready' });
  assert.deepEqual(f.events, ['writer-check.json', 'challenge-prewarm.json', 'ready.json']);
  assert.deepEqual(JSON.parse(f.records.get(f.c('ready.json'))), { ...f.identity, state: 'ready' });
});

test('one observed click has durable attempt then prompt ack then refresh; no repeat', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  const result = await f.dispatch();
  assert.equal(result.outcome, 'dispatched');
  assert.deepEqual(f.events.slice(3), ['attempted.json', 'challenge-dispatch.json', 'click', 'ack.json', 'refresh']);
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, 1);
  await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
  assert.equal(f.events.filter((value) => value === 'click').length, 1);
});

for (const [name, mutate] of [
  ['foreign generation', (f) => f.invoke({ generation: 'c'.repeat(32) })],
  ['extra command field', (f) => f.invoke({ command: 'arbitrary' })],
  ['wrong action', (f) => f.invoke({ action: 'other' })],
  ['expired request', (f) => f.setNow(1030)],
  ['excess lifetime', (f) => f.invoke({ deadlineUnix: 1031 })],
  ['owner death', (f) => f.setLive(false)],
  ['closed owner', (f) => f.put(f.c('owner.json'), { ...f.identity, state: 'closed', deadlineUnix: 1900 })],
  ['native stop of any contents', (f) => f.records.set(f.n('stop.json'), Buffer.from('garbage'))],
  ['foreign terminal receipt', (f) => f.records.set(f.n('status.json'), Buffer.from('garbage'))],
  ['operator temporary stop', (f) => f.records.set(f.c('operator-stop.json.tmp'), Buffer.from(''))],
  ['oversized request', (f) => f.records.set(f.c('invoke.json'), Buffer.alloc(4097))],
  ['stale observation', (f) => { f.session.state = { ...f.session.state }; }],
]) {
  test(`${name} refuses before input`, async () => {
    const f = fixture(); await f.controller.prewarm(); f.invoke(); mutate(f);
    await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
    assert.equal(f.events.includes('click'), false);
  });
}

test('stop arriving during durable attempted publication wins final check', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  f.after((file) => { if (file === f.c('attempted.json')) f.put(f.n('stop.json'), {}); });
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.events.includes('click'), false);
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).actualInputCount, 0);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
});

test('failed attempted persistence latches without calling Sky', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke(); f.fail('attempted.json');
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.events.includes('click'), false);
  assert.equal(f.session.fgaPostAttempt.attempted, true);
  await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
});

test('input exception publishes unknown count and sticky stop without leaking error', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke(); f.setClickError();
  await assert.rejects(f.dispatch(), /^Error: dispatch_stopped_or_unknown_no_retry$/);
  const ack = JSON.parse(f.records.get(f.c('ack.json')));
  assert.equal(ack.outcome, 'unknown'); assert.equal(ack.actualInputCount, null);
  assert.equal(f.events.includes('refresh'), false);
  assert.equal(f.records.has(f.c('operator-stop.json')), true);
  await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
});

test('lost ack cannot authorize repeated dispatch after controller recreation', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke(); f.fail('ack.json');
  await assert.rejects(f.dispatch(), /no_retry/);
  const replacement = createDispatchController(f.options);
  await assert.rejects(replacement.prewarm());
  assert.equal(f.events.filter((value) => value === 'click').length, 1);
});

test('refresh exception keeps prompt input receipt and latches unknown stop', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke(); f.setRefreshError();
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(JSON.parse(f.records.get(f.c('ack.json'))).outcome, 'dispatched');
  assert.equal(JSON.parse(f.records.get(f.c('operator-stop.json'))).reason, 'unknown');
  assert.equal(f.session.fgaPostAttempt.stopped, true);
});

test('intentional Escape before invocation never permits later input', async () => {
  const f = fixture(); await f.controller.prewarm(); await f.controller.stop('escape'); f.invoke();
  await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
  assert.equal(f.events.includes('click'), false);
});

test('new session cannot bypass retained durable attempted evidence', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke(); await f.dispatch();
  const replacement = createDispatchController({ ...f.options, session: {} });
  await assert.rejects(replacement.prewarm());
  assert.equal(f.events.filter((value) => value === 'click').length, 1);
});

test('prewarm refuses stale native files and incomplete writer rehearsal', async () => {
  for (const name of ['target.json', 'target.json.tmp', 'target.used.json', 'target.used.json.tmp',
    'status.json', 'status.json.tmp', 'stop.json', 'stop.json.tmp']) {
    const f = fixture(); f.put(f.n(name), {});
    await assert.rejects(f.controller.prewarm());
    assert.equal(f.records.has(f.c('ready.json')), false);
  }
  const f = fixture(); f.fail('writer-check.json');
  await assert.rejects(f.controller.prewarm());
  assert.equal(f.records.has(f.c('ready.json')), false);
});

test('original closed run and file-supplied binding commands are rejected', () => {
  const f = fixture();
  assert.throws(() => createDispatchController({ ...f.options,
    binding: { ...f.binding, runId: 'c01ba6d2c2754597aa311c9f' } }), /binding_identity/);
  assert.throws(() => createDispatchController({ ...f.options,
    binding: { ...f.binding, command: 'other' } }), /binding_schema/);
});

for (const label of ['Characterize synthetic POST v10', 'Other Characterize synthetic POST v1',
  'Characterize synthetic POST v1 extra', 'Button Characterize synthetic POST v1']) {
  test(`exact menu label refuses ${label}`, async () => {
    const f = fixture(); await f.controller.prewarm(); f.invoke();
    f.session.state.accessibility.tree = `  [12] MenuItem ${label}`;
    await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
    assert.equal(f.events.includes('click'), false);
  });
}

test('Escape latches even while its durable stop publication is pending', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  const originalExists = f.options.files.exists;
  let delayStop = false;
  let release;
  let stopping;
  f.options.files.exists = async (file) => {
    if (delayStop && file === f.c('operator-stop.json')) {
      delayStop = false;
      return new Promise((resolve) => { release = resolve; });
    }
    return originalExists(file);
  };
  f.onProbe(() => {
    f.onProbe(undefined); delayStop = true;
    stopping = f.controller.stop('escape');
  });
  await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
  assert.equal(f.events.includes('click'), false);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
  release(false); await stopping.catch(() => {});
});

test('observation replacement during owner checks refuses the old index', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  f.onProbe(() => { f.session.state = { ...f.session.state }; });
  await assert.rejects(f.dispatch(), /dispatch_refused|no_retry/);
  assert.equal(f.events.includes('click'), false);
});

test('observation replacement after durable attempt latches without input', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  f.after((file) => { if (file === f.c('attempted.json')) f.session.state = {}; });
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.events.includes('click'), false);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
});

for (const name of ['stop.json.tmp', 'status.json.tmp']) {
  test(`native temporary ${name} arriving after ready refuses dispatch`, async () => {
    const f = fixture(); await f.controller.prewarm(); f.invoke();
    f.after((file) => { if (file === f.c('attempted.json')) f.records.set(f.n(name), Buffer.from('')); });
    await assert.rejects(f.dispatch(), /no_retry/);
    assert.equal(f.events.includes('click'), false);
  });
}

test('prewarm never publishes ready after an Escape whose file write is pending', async () => {
  const f = fixture();
  const originalExists = f.options.files.exists;
  let delayStop = false;
  let release;
  let stopping;
  let probes = 0;
  f.options.files.exists = async (file) => {
    if (delayStop && file === f.c('operator-stop.json')) {
      delayStop = false;
      return new Promise((resolve) => { release = resolve; });
    }
    return originalExists(file);
  };
  f.onProbe(() => {
    probes += 1;
    if (probes === 1) { delayStop = true; stopping = f.controller.stop('escape'); }
  });
  await assert.rejects(f.controller.prewarm(), /prewarm_stopped_or_unknown_no_retry/);
  assert.equal(f.records.has(f.c('ready.json')), false);
  release(false); await stopping.catch(() => {});
});

test('prewarm does not report readiness after Escape during ready publication', async () => {
  const f = fixture();
  f.after(async (file) => {
    if (file === f.c('ready.json')) await f.controller.stop('escape');
  });
  await assert.rejects(f.controller.prewarm(), /prewarm_stopped_or_unknown_no_retry/);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
  f.invoke();
  await assert.rejects(f.dispatch(), /controller_not_ready/);
  assert.equal(f.events.includes('click'), false);
});

test('Node writer exclusively opens final file and completes write/fsync/close before success', async () => {
  const events = [];
  const writer = nodeFiles({
    async open(file, mode) {
      events.push([file, mode]);
      return {
        async writeFile(bytes, encoding) { events.push(['write', bytes, encoding]); },
        async sync() { events.push('sync'); },
        async close() { events.push('close'); },
      };
    },
  });
  await writer.publish('approved-ready.json', { state: 'ready' });
  assert.deepEqual(events, [['approved-ready.json', 'wx'],
    ['write', '{"state":"ready"}\n', 'utf8'], 'sync', 'close']);
});

for (const phase of ['writeFile', 'sync', 'close']) {
  test(`Node writer ${phase} failure remains uncertain without overwrite or retry`, async () => {
    let opens = 0;
    let closed = 0;
    const writer = nodeFiles({
      async open(_file, mode) {
        opens += 1; assert.equal(mode, 'wx');
        return {
          async writeFile() { if (phase === 'writeFile') throw new Error('write_failed'); },
          async sync() { if (phase === 'sync') throw new Error('sync_failed'); },
          async close() { closed += 1; if (phase === 'close') throw new Error('close_failed'); },
        };
      },
    });
    await assert.rejects(writer.publish('approved-attempted.json', { attempted: true }));
    assert.equal(opens, 1); assert.equal(closed, 1);
  });
}

test('Node writer rejects excess JSON bytes before creating any signal', async () => {
  const writer = nodeFiles({ async open() { assert.fail('must not open oversized signal'); } });
  await assert.rejects(writer.publish('approved-ready.json', { state: 'x'.repeat(4096) }), /byte_limit/);
});

test('missing prewarm checkpoint response stops after finite coordination polling', async () => {
  const f = fixture(); f.setLive(false);
  await assert.rejects(f.controller.prewarm(), /no_retry/);
  assert.equal(f.sleeps(), 10);
  assert.equal(f.records.has(f.c('ready.json')), false);
  assert.equal(f.records.has(f.c('challenge-prewarm.json')), true);
  assert.equal(f.records.has(f.c('operator-stop.json')), true);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
  await assert.rejects(f.controller.prewarm());
  assert.equal(f.sleeps(), 10);
});

for (const [name, mutate] of [
  ['foreign nonce', (value) => ({ ...value, nonce: 'e'.repeat(32) })],
  ['wrong phase', (value) => ({ ...value, phase: 'prewarm' })],
  ['foreign generation', (value) => ({ ...value, generation: 'e'.repeat(32) })],
  ['changed deadline', (value) => ({ ...value, deadlineUnix: value.deadlineUnix + 1 })],
  ['extra field', (value) => ({ ...value, instruction: 'not accepted' })],
]) {
  test(`dispatch checkpoint ${name} latches without input or replay`, async () => {
    const f = fixture(); await f.controller.prewarm(); f.invoke();
    f.after((file) => {
      if (file === f.c('challenge-dispatch.json')) {
        const original = JSON.parse(f.records.get(file));
        f.put(f.c('response-dispatch.json'), mutate(original));
      }
    });
    await assert.rejects(f.dispatch(), /no_retry/);
    assert.equal(f.events.includes('click'), false);
    assert.equal(f.sleeps(), 0);
    assert.equal(f.session.fgaPostAttempt.stopped, true);
    await assert.rejects(f.dispatch());
    assert.equal(f.events.filter((event) => event === 'challenge-dispatch.json').length, 1);
  });
}

test('partial checkpoint response is terminal rather than retried', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  f.after((file) => {
    if (file === f.c('challenge-dispatch.json')) f.records.set(f.c('response-dispatch.json'), Buffer.from('{'));
  });
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.events.includes('click'), false);
  assert.equal(f.sleeps(), 0);
  assert.equal(f.session.fgaPostAttempt.stopped, true);
});

test('replayed phase response is refused before a new challenge', async () => {
  const f = fixture(); await f.controller.prewarm(); f.invoke();
  f.records.set(f.c('response-dispatch.json'), f.records.get(f.c('response-prewarm.json')));
  await assert.rejects(f.dispatch(), /no_retry/);
  assert.equal(f.events.includes('challenge-dispatch.json'), false);
  assert.equal(f.events.includes('click'), false);
});

for (const nextTime of [1010, 999, NaN]) {
  test(`checkpoint clock expiry or reversal ${nextTime} fails closed`, async () => {
    const f = fixture(); await f.controller.prewarm(); f.invoke();
    f.after((file) => { if (file === f.c('challenge-dispatch.json')) f.setNow(nextTime); });
    await assert.rejects(f.dispatch(), /no_retry/);
    assert.equal(f.events.includes('click'), false);
    assert.equal(f.session.fgaPostAttempt.stopped, true);
  });
}
