import assert from "node:assert/strict";
import test from "node:test";
import { bundle, parseBundle, observe, resolve } from "./lifecycle.ts";
const generations = ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"];
const linked = { revision: 2, state: "linked", generation: generations[0], writes_paused: 1,
  pending_generation: null, retiring_generation: null, operation: null };
test("exact matching bundle is usable without returning its token values", async () => {
  const result = await resolve(async () => linked, { get: async () => bundle(generations[0]) }, generations);
  assert.deepEqual(result, { outcome: "usable", generation: generations[0] });
  assert.equal(JSON.stringify(result).includes("synthetic-token"), false);
});
test("a newer or delayed older value cannot stand in for the active generation", async () => {
  assert.deepEqual(await resolve(async () => linked, { get: async () => bundle(generations[1]) }, generations),
    { outcome: "generation_mismatch" });
});
test("mixed pair, unknown generation, malformed and oversized bundles are refused", () => {
  const mixed = { ...JSON.parse(bundle(generations[0])), tokenSecret: "other-generation" };
  for (const value of [JSON.stringify(mixed), bundle("unknown"), "null", "[]", "{", "x".repeat(2049)]) {
    assert.throws(() => parseBundle(value, generations), { message: "invalid_bundle" });
  }
});
test("durable pause prevents even a secret read", async () => {
  for (const state of ["paused", "disconnecting", "disconnected"]) {
    assert.deepEqual(await resolve(async () => ({ ...linked, state }),
      { get: () => { throw new Error("must not read"); } }, generations), { outcome: "stopped" });
  }
});
test("a pause or revision change during the secret read is fenced", async () => {
  let row = { ...linked };
  const result = await resolve(async () => ({ ...row }), { get: async () => {
    row = { ...row, revision: 3, state: "paused" }; return bundle(generations[0]);
  } }, generations);
  assert.deepEqual(result, { outcome: "state_changed" });
});
test("binding failure exposes no provider text or secret and never proves deletion", async () => {
  assert.deepEqual(await observe({ get: async () => { throw new Error("private-secret-data"); } }, generations),
    { outcome: "unavailable" });
});
test("a hung secret binding is bounded by the deadline", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const waiting = observe({ get: () => new Promise(() => {}) }, generations);
  t.mock.timers.tick(10_001);
  assert.deepEqual(await waiting, { outcome: "unavailable" });
});
