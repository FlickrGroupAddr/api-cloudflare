import test from 'node:test';
import assert from 'node:assert/strict';
import { ensureLightroomWindow } from '../scripts/lightroom_automation.mjs';

const APP = 'returned-lightroom-guid';
const WINDOW = { app: 'process:C:\\Program Files\\Adobe\\Adobe Lightroom Classic\\Lightroom.exe',
  id: 1903500, title: 'private fixture catalog title' };
const app = (windows = [], running = false, id = APP) => ({
  id, displayName: 'Adobe Lightroom Classic', isRunning: running, windows,
});
function fixture(inventories, launchError) {
  const calls = [], logs = [];
  let clock = 0, index = 0;
  const sky = {
    async list_apps() { calls.push(['list_apps']); return inventories[Math.min(index++, inventories.length - 1)]; },
    async launch_app(input) { calls.push(['launch_app', input]); if (launchError) throw launchError; },
    async get_window(input) { calls.push(['get_window', input]); return WINDOW; },
  };
  const options = { appId: APP, maxPolls: 4, timeoutMs: 5000, pollIntervalMs: 100,
    now: () => clock, sleep: async ms => { clock += ms; }, log: stage => logs.push(stage) };
  return { sky, options, calls, logs, advance: ms => { clock += ms; } };
}
const launches = f => f.calls.filter(([method]) => method === 'launch_app');

test('reuse selects one returned window without launch; GUID and process identifiers remain distinct', async () => {
  const f = fixture([[app([WINDOW], true)]]);
  assert.equal(await ensureLightroomWindow(f.sky, f.options), WINDOW);
  assert.deepEqual(launches(f), []);
  assert.deepEqual(f.calls.at(-1), ['get_window', { id: WINDOW.id, app: WINDOW.app }]);
  assert.deepEqual(f.logs, ['enumerating', 'reusing', 'rehydrating', 'ready']);
  assert(!JSON.stringify(f.logs).includes(WINDOW.title));
  assert(!JSON.stringify(f.logs).includes(APP));
});

test('cold launch uses only returned app ID, once, then selects returned window', async () => {
  const f = fixture([[app()], [app([WINDOW], true)]]);
  assert.equal(await ensureLightroomWindow(f.sky, f.options), WINDOW);
  assert.deepEqual(launches(f), [['launch_app', { app: APP }]]);
});

test('known launch false negative recovers immediately by re-enumeration without replay', async () => {
  const f = fixture([[app()], [app([WINDOW], true)]],
    new Error(`launched app did not expose a targetable window: ${APP}`));
  assert.equal(await ensureLightroomWindow(f.sky, f.options), WINDOW);
  assert.equal(launches(f).length, 1);
  assert(f.logs.includes('launch_window_pending'));
});

test('delayed false negative polls boundedly without a second launch', async () => {
  const f = fixture([[app()], [app([], true)], [], [app([WINDOW], true)]],
    new Error(`launched app did not expose a targetable window: ${APP}`));
  assert.equal(await ensureLightroomWindow(f.sky, f.options), WINDOW);
  assert.equal(launches(f).length, 1);
  assert.equal(f.calls.filter(([method]) => method === 'list_apps').length, 4);
});

test('already running app without a window is observed without relaunch', async () => {
  const f = fixture([[app([], true)], [app([WINDOW], true)]]);
  assert.equal(await ensureLightroomWindow(f.sky, f.options), WINDOW);
  assert.equal(launches(f).length, 0);
});

test('exact Lightroom display-name fallback excludes unrelated Lightroom apps', async () => {
  const f = fixture([[{ ...app([WINDOW], true), displayName: 'Lightroom Classic' },
    { ...app([], false, 'cloud'), displayName: 'Adobe Lightroom' }]]);
  delete f.options.appId;
  assert.equal(await ensureLightroomWindow(f.sky, f.options), WINDOW);
});

test('absent/ambiguous apps and windows fail before launch or rehydration', async () => {
  for (const [inventory, code] of [[[], 'app_not_found'],
    [[app(), app()], 'ambiguous_app'], [[app([WINDOW, { ...WINDOW, id: 123 }], true)], 'ambiguous_window']]) {
    const f = fixture([inventory]);
    await assert.rejects(ensureLightroomWindow(f.sky, f.options), { code });
    assert.equal(launches(f).length, 0);
    assert(!f.calls.some(([method]) => method === 'get_window'));
  }
});

test('post-launch ambiguous windows stop rather than select or launch again', async () => {
  const f = fixture([[app()], [app([WINDOW, { ...WINDOW, id: 123 }], true)]]);
  await assert.rejects(ensureLightroomWindow(f.sky, f.options), { code: 'ambiguous_window' });
  assert.equal(launches(f).length, 1);
  assert(!f.calls.some(([method]) => method === 'get_window'));
});

test('inventory never invents a window from a running app or launch outcome', async () => {
  const f = fixture([[app()]], new Error(`launched app did not expose a targetable window: ${APP}`));
  await assert.rejects(ensureLightroomWindow(f.sky, f.options), { code: 'window_timeout' });
  assert.equal(launches(f).length, 1);
  assert.equal(f.calls.filter(([method]) => method === 'list_apps').length, 5);
  assert(!f.calls.some(([method]) => method === 'get_window'));
});

test('unknown launch errors, mismatched IDs and intentional Escape propagate unchanged', async () => {
  for (const error of [new Error('intentional Escape cancellation'), new Error('launch refused'),
    new Error('launched app did not expose a targetable window: another-app'),
    Object.assign(new Error(`launched app did not expose a targetable window: ${APP}`), { name: 'AbortError' })]) {
    const f = fixture([[app()], [app([WINDOW], true)]], error);
    await assert.rejects(ensureLightroomWindow(f.sky, f.options), value => value === error);
    assert.equal(launches(f).length, 1);
    assert.equal(f.calls.filter(([method]) => method === 'list_apps').length, 1);
  }
});

test('cancelled before entry preserves original reason and invokes no API', async () => {
  const f = fixture([[app([WINDOW], true)]]), controller = new AbortController();
  const reason = new Error('owner cancellation'); controller.abort(reason);
  await assert.rejects(ensureLightroomWindow(f.sky, { ...f.options, signal: controller.signal }), value => value === reason);
  assert.deepEqual(f.calls, []);
});

test('native cancellation/error identity is preserved even at an elapsed deadline', async () => {
  const f = fixture([[app()]]), reason = new Error('intentional Escape');
  f.sky.launch_app = async () => { f.advance(5000); throw reason; };
  await assert.rejects(ensureLightroomWindow(f.sky, f.options), value => value === reason);
  assert.equal(f.calls.filter(([method]) => method === 'list_apps').length, 1);
});

test('cancellation during launch stops promptly without recovery or replay', async () => {
  const f = fixture([[app()]]), controller = new AbortController(), reason = new Error('intentional Escape');
  f.sky.launch_app = async () => { f.calls.push(['launch_app']); controller.abort(reason); return new Promise(() => {}); };
  await assert.rejects(ensureLightroomWindow(f.sky, { ...f.options, signal: controller.signal }), value => value === reason);
  assert.equal(launches(f).length, 1);
  assert.equal(f.calls.length, 2);
});

test('cancellation during polling stops further enumeration', async () => {
  const f = fixture([[app([], true)]]), controller = new AbortController(), reason = new Error('stop');
  f.options.sleep = async () => { controller.abort(reason); };
  await assert.rejects(ensureLightroomWindow(f.sky, { ...f.options, signal: controller.signal }), value => value === reason);
  assert.equal(launches(f).length, 0);
  assert.equal(f.calls.filter(([method]) => method === 'list_apps').length, 2);
});

test('deadline bounds a hung native call without replay', async () => {
  const f = fixture([[app()]]);
  f.sky.launch_app = async () => { f.calls.push(['launch_app']); return new Promise(() => {}); };
  await assert.rejects(ensureLightroomWindow(f.sky, { ...f.options, timeoutMs: 20 }), { code: 'window_timeout' });
  assert.equal(launches(f).length, 1);
  assert.equal(f.calls.length, 2);
});

test('elapsed deadline and invalid clocks cannot produce ready state', async () => {
  const f = fixture([[app([], true)]]);
  f.options.sleep = async () => f.advance(5000);
  await assert.rejects(ensureLightroomWindow(f.sky, f.options), { code: 'window_timeout' });
  assert(!f.logs.includes('ready'));
  const g = fixture([[app([WINDOW], true)]]);
  g.options.now = () => NaN;
  await assert.rejects(ensureLightroomWindow(g.sky, g.options), { code: 'invalid_clock' });
  assert.deepEqual(g.calls, []);
});

test('get_window failures and changed identities cannot manufacture a target', async () => {
  const f = fixture([[app([WINDOW], true)]]), error = new Error('window disappeared');
  f.sky.get_window = async () => { throw error; };
  await assert.rejects(ensureLightroomWindow(f.sky, f.options), value => value === error);
  f.sky.get_window = async () => ({ ...WINDOW, id: 123 });
  await assert.rejects(ensureLightroomWindow(f.sky, f.options), { code: 'window_identity_changed' });
  assert(!f.logs.includes('ready'));
});

test('invalid options and malformed returned windows cause no unsupported calls', async () => {
  const f = fixture([[app([WINDOW], true)]]);
  await assert.rejects(ensureLightroomWindow(f.sky, { ...f.options, maxPolls: 0 }), { code: 'invalid_options' });
  assert.deepEqual(f.calls, []);
  const g = fixture([[app([{ id: WINDOW.id }], true)]]);
  await assert.rejects(ensureLightroomWindow(g.sky, g.options), { code: 'invalid_window' });
});
