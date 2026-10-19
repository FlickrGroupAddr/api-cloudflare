// MIT License; copyright 2026 Terry Ott.
import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { Pmb1ObjectCandidate, bootstrap } from "../pmb1-object/candidate.ts";
import { NATIVE_ALARM_NO_GO, Pmb1NativeAlarmRefusal, refuseNativeAlarmDisposition } from "./refusal.ts";
import { LocalStorage, deferred } from "./local-storage.mjs";

const MARKER = "pmb1:alarm-invocation";
// Fixture-only opening. Never an independent disposition proof.
const syntheticDisposition = async generation => ({ generation,
  preCloseExecutionsDisposed: true, temporaryExecutionsDisposed: true,
  oldVersionsFenced: true, queuedAndAlarmCallbacksDisposed: true });
async function fixture() {
  const storage = new LocalStorage(); await bootstrap(storage);
  const candidate = new Pmb1ObjectCandidate(storage, syntheticDisposition);
  await candidate.reopen("1");
  const invocation = await candidate.admit("work", "2");
  return { storage, candidate, invocation };
}
const refusal = promise => assert.rejects(promise, { message: NATIVE_ALARM_NO_GO });

test("source and native interface match the inspected unchanged pins", () => {
  const pins = JSON.parse(readFileSync(new URL("./source-pins.json", import.meta.url)));
  for (const file of pins.files) {
    const bytes = readFileSync(new URL("../../" + file.path, import.meta.url));
    assert.equal(createHash("sha256").update(bytes).digest("hex"), file.digest);
  }
  const types = readFileSync(new URL("../../node_modules/@cloudflare/workers-types/index.d.ts", import.meta.url), "utf8");
  const info = types.match(/interface AlarmInvocationInfo \{([^}]+)\}/)?.[1];
  assert.deepEqual([...info.matchAll(/readonly (\w+):/g)].map(match => match[1]),
    ["isRetry", "retryCount", "scheduledTime"]);
  const pkg = JSON.parse(readFileSync(new URL("../../node_modules/@cloudflare/workers-types/package.json", import.meta.url)));
  assert.equal(pkg.version, pins.workersTypesVersion);
});

test("zero-argument, native info and forged application identity all refuse without storage access", async () => {
  const handler = new Pmb1NativeAlarmRefusal();
  await refusal(handler.alarm());
  for (const info of [undefined, { isRetry: false, retryCount: 0, scheduledTime: 100 },
    { isRetry: true, retryCount: 1, scheduledTime: 100 },
    { id: "work", generation: "2", alarmGeneration: "1" }, null]) {
    await refusal(handler.alarm(info));
  }
});

test("equal-time replacement rejects original identity; native refusal preserves replacement", async () => {
  const { storage, candidate, invocation } = await fixture();
  const original = await candidate.write(invocation, "first", 100);
  const replacement = await candidate.write(invocation, "replacement", 100);
  assert.notDeepEqual(original, replacement);
  const before = await candidate.inspect();
  await assert.rejects(candidate.alarmCallback(original), /stale_alarm/);
  for (let retryCount = 0; retryCount <= 6; retryCount++) {
    await refusal(new Pmb1NativeAlarmRefusal().alarm({
      isRetry: retryCount > 0, retryCount, scheduledTime: 100,
    }));
  }
  assert.deepEqual(await candidate.inspect(), before);
  assert.deepEqual(storage.kv.get(MARKER), replacement);
  await candidate.suspendAdmission("2");
  await assert.rejects(candidate.close("2"), /drain_incomplete/);
});

test("negative control: reading latest marker lets old delivery consume equal-time replacement", async () => {
  const { storage, candidate, invocation } = await fixture();
  await candidate.write(invocation, "first", 100);
  const started = deferred(), resume = deferred();
  // An OLD handler has begun, but yields before its first marker read.
  // This deliberately UNSAFE test-only handler is never exported as an adapter.
  const oldDelivery = (async () => {
    started.resolve(); await resume.promise;
    await candidate.alarmCallback(structuredClone(storage.kv.get(MARKER)));
  })();
  await started.promise;
  const replacement = await candidate.write(invocation, "replacement", 100);
  resume.resolve(); await oldDelivery;
  const after = await candidate.inspect();
  assert.equal(after.alarm, null);
  assert.equal(after.executions[0].state, "settled");
  assert.equal(after.work[0].value, "alarm");
  assert.equal(replacement.alarmGeneration, "2");
});

test("captured identity already running before replacement cannot consume the new arm", async () => {
  const { candidate, invocation } = await fixture();
  const original = await candidate.write(invocation, "first", 100);
  const started = deferred(), resume = deferred();
  const oldDelivery = (async () => {
    started.resolve(); await resume.promise; return candidate.alarmCallback(original);
  })();
  await started.promise;
  await candidate.write(invocation, "replacement", 100);
  const before = await candidate.inspect();
  resume.resolve(); await assert.rejects(oldDelivery, /stale_alarm/);
  assert.deepEqual(await candidate.inspect(), before);
});

test("null exposed alarm and delete do not constitute callback disposition", async () => {
  const { storage, candidate, invocation } = await fixture();
  const dispatch = await candidate.write(invocation, "first", 100);
  // Independent scheduler fault: delivery is running; exposed time is null.
  storage.alarm = null;
  await candidate.suspendAdmission("2");
  await assert.rejects(candidate.close("2"), /drain_incomplete/);
  // App deletion cancels work, but cannot settle an unobserved provider callback.
  await candidate.deleteWork(invocation); await candidate.cancel(invocation);
  await candidate.close("2");
  const before = await candidate.inspect();
  await assert.rejects(candidate.alarmCallback(dispatch), /unknown_alarm/);
  const restart = new Pmb1ObjectCandidate(storage, refuseNativeAlarmDisposition);
  await refusal(restart.reopen("3"));
  assert.deepEqual(await restart.inspect(), before);
});

test("restart preserves external pending and failed mandatory result; native refusal cannot erase it", async () => {
  const { storage, candidate, invocation } = await fixture();
  await candidate.beginExternal(invocation); await candidate.suspendAdmission("2");
  const before = await candidate.inspect();
  const restart = new Pmb1ObjectCandidate(storage, refuseNativeAlarmDisposition);
  await refusal(new Pmb1NativeAlarmRefusal().alarm());
  storage.failAt = "put";
  await assert.rejects(restart.settleExternal(invocation, "confirmed_success"), /injected_put/);
  storage.failAt = null;
  assert.deepEqual(await restart.inspect(), before);
  await assert.rejects(restart.close("2"), /drain_incomplete/);
  await restart.settleExternal(invocation, "confirmed_success");
  await restart.close("2");
  const closed = await restart.inspect();
  await refusal(restart.reopen("3"));
  assert.deepEqual(await restart.inspect(), closed);
});

test("closure remains exact and no native result supplies reopen proof at any generation", async () => {
  const { storage, candidate, invocation } = await fixture();
  await candidate.cancel(invocation); await candidate.suspendAdmission("2");
  await candidate.close("2");
  const before = await candidate.inspect();
  for (const expected of ["3", "2", "9007199254740993", "9223372036854775807", "03"]) {
    await refusal(refuseNativeAlarmDisposition(expected));
  }
  const restart = new Pmb1ObjectCandidate(storage, refuseNativeAlarmDisposition);
  await refusal(restart.reopen("3"));
  await assert.rejects(restart.reopen("03"), /invalid_generation/);
  await refusal(new Pmb1NativeAlarmRefusal().alarm({ isRetry: true, retryCount: 6, scheduledTime: 100 }));
  assert.deepEqual(await restart.inspect(), before);
});

test("provider metadata drift is independent from unchanged application state", async () => {
  const { candidate, invocation } = await fixture();
  await candidate.cancel(invocation); await candidate.suspendAdmission("2"); await candidate.close("2");
  const before = await candidate.inspect();
  // Illustrative external fault only: this is not a provider reader/emulator.
  const metadata = { delivered: 0, retries: 0 };
  metadata.delivered++;
  await refusal(new Pmb1NativeAlarmRefusal().alarm());
  metadata.retries++;
  assert.deepEqual(await candidate.inspect(), before);
  assert.notDeepEqual(metadata, { delivered: 0, retries: 0 });
});
