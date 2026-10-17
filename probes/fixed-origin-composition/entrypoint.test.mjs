import assert from 'node:assert/strict';
import test from 'node:test';
import * as entry from './entrypoint.mjs';

function options() {
  const ordinary = [];
  const result = new Response('ordinary');
  const captured = { default: { fetch(request, env) {
    ordinary.push({ request, env });
    return result;
  } } };
  return { captured, candidate: { createWorker() {
    return { fetch() { throw Error('candidate_must_not_run'); } };
  } }, syntheticDb: {}, quotaDb: { prepare() { throw Error('quota_must_not_run'); } },
  receiverBinding: { fetch() { throw Error('receiver_must_not_run'); } },
  run: 'a'.repeat(32), capability: 'b'.repeat(64), startsAt: 1000,
  expiresAt: 601000, clock: () => 2000, counters: { normal: 0 }, ordinary, result };
}

test('ordinary request and full environment retain their exact identities', async () => {
  const input = options();
  const worker = entry.createTemporaryComposition(input);
  const request = new Request('https://flickrgroupaddr.com/api/v001/installations/current',
    { headers: { Authorization: 'Bearer synthetic-ordinary' } });
  const env = Object.freeze({ unknownBinding: Object.freeze({ value: 42 }) });
  const result = await worker.fetch(request, env);
  assert.equal(result, input.result);
  assert.equal(input.ordinary.length, 1);
  assert.equal(input.ordinary[0].request, request);
  assert.equal(input.ordinary[0].env, env);
  assert.equal(input.counters.normal, 1);
});

test('invalid qualification traffic cannot fall through to captured dispatcher', async () => {
  const input = options();
  const worker = entry.createTemporaryComposition(input);
  const request = new Request('https://flickrgroupaddr.com/api/v001/installations/current',
    { headers: { Authorization: 'FGA-Qualification invalid' } });
  assert.equal((await worker.fetch(request, {})).status, 404);
  assert.equal(input.ordinary.length, 0);
});

test('offline constructor has no default Worker and requires module interfaces', () => {
  assert.equal(Object.hasOwn(entry, 'default'), false);
  assert.throws(() => entry.createTemporaryComposition({}), /module_interface_required/);
  assert.throws(() => entry.createTemporaryComposition({ ...options(), receiverBinding: null }),
    /invalid_receiver_binding/);
});
