// MIT License; copyright 2026 Terry Ott.
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { bootstrap, Pmb1NativeWakeup, MAX_GENERATION } from "./candidate.ts";
import { LocalStorage, deferred } from "../pmb1-native-alarm/local-storage.mjs";

// Uses the existing actual SQL/KV/alarm-shaped storage model, not a provider scheduler.
class Storage extends LocalStorage {
  before = null;
  after = null;
  async transaction(fn) {
    const before = this.before; this.before = null;
    if (before) { before.enter.resolve(); await before.release.promise; }
    const result = await super.transaction(fn);
    const after = this.after; this.after = null;
    if (after) { after.enter.resolve(); await after.release.promise; }
    return result;
  }
  hold(when) {
    const gate = { enter: deferred(), release: deferred() };
    this[when] = gate; return gate;
  }
}
const disposition = async generation => ({ generation, preCloseExecutionsDisposed: true,
  temporaryExecutionsDisposed: true, oldVersionsFenced: true, queuedAndAlarmCallbacksDisposed: true });
async function fixture() {
  const storage = new Storage(); let now = 100;
  await bootstrap(storage);
  const candidate = new Pmb1NativeWakeup(storage, disposition, () => now);
  await candidate.reopen("1");
  return { storage, candidate, clock: value => { now = value; },
    restart: (verify = disposition) => new Pmb1NativeWakeup(storage, verify, () => now) };
}
const rows = (storage, table) => storage.sql.exec("SELECT * FROM " + table + " ORDER BY 1").toArray().map(row => ({ ...row }));
const executions = storage => rows(storage, "pmb1_wake_executions");
const results = storage => rows(storage, "pmb1_wake_results");
function snapshot(storage) {
  return { control: rows(storage, "maintenance_control"), work: rows(storage, "pmb1_wake_work"),
    executions: executions(storage), results: results(storage), kv: structuredClone(storage.kv), alarm: storage.alarm };
}
const admission = storage => { const { state, ...token } = executions(storage).at(-1); return token; };
const reject = (promise, message) => assert.rejects(promise, { message });

test("unchanged prerequisite source and installed native interface pins", () => {
  const pins = JSON.parse(readFileSync(new URL("./source-pins.json", import.meta.url)));
  for (const pin of pins.files)
    assert.equal(createHash("sha256").update(readFileSync(new URL("../../" + pin.path, import.meta.url))).digest("hex"), pin.digest);
  const native = readFileSync(new URL("../../node_modules/@cloudflare/workers-types/index.d.ts", import.meta.url), "utf8");
  assert.match(native, /alarm\?\(alarmInfo\?: AlarmInvocationInfo\): void \| Promise<void>/);
  assert.equal(Pmb1NativeWakeup.prototype.alarm.length, 0);
});

test("zero-argument actual handler checks due time, snapshots work, and duplicate retry is inert", async () => {
  const { storage, candidate, clock } = await fixture();
  await candidate.schedule("2", "first", 101);
  const before = snapshot(storage); await candidate.alarm(); assert.deepEqual(snapshot(storage), before);
  clock(101); await candidate.alarm();
  assert.deepEqual(results(storage), [{ id: "1", result: "local:first" }]);
  assert.equal(executions(storage)[0].revision, "1"); assert.equal(storage.alarm, null);
  const settled = snapshot(storage);
  await candidate.alarm(); await candidate.alarm({ isRetry: true, retryCount: 6, scheduledTime: 101 });
  assert.deepEqual(snapshot(storage), settled);
});

test("equal-time replacement and native info gain only fresh current admission", async () => {
  const { storage, candidate } = await fixture();
  assert.equal(await candidate.schedule("2", "old", 100), "1");
  assert.equal(await candidate.schedule("2", "replacement", 100), "2");
  await candidate.alarm({ isRetry: true, retryCount: 0, scheduledTime: 100, revision: "1", generation: "1" });
  assert.deepEqual(results(storage), [{ id: "1", result: "local:replacement" }]);
  assert.equal(executions(storage)[0].revision, "2");
});

test("restart has no write/rearm and zero-argument delivery admits durable current work", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "restart", 100);
  const before = snapshot(f.storage); const restarted = f.restart(); assert.deepEqual(snapshot(f.storage), before);
  await restarted.alarm(); assert.deepEqual(results(f.storage), [{ id: "1", result: "local:restart" }]);
});

test("null exposed native alarm during delivery is neither authority nor an empty durable-work census", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "due", 100);
  f.storage.alarm = null; // Inject the documented exposed-null shape; no provider model claimed.
  await f.candidate.alarm(); assert.equal(results(f.storage)[0].result, "local:due");
});

test("notification delayed before admission selects replacement as fresh current authority", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "old", 100);
  const gate = f.storage.hold("before"); const callback = f.candidate.alarm(); await gate.enter.promise;
  await f.candidate.schedule("2", "new", 200); f.clock(200);
  gate.release.resolve(); await callback;
  assert.equal(executions(f.storage)[0].revision, "2"); assert.equal(results(f.storage)[0].result, "local:new");
});

test("synchronous generation capture fences a notification delayed across close and reopen", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "old", 100);
  const gate = f.storage.hold("before"); const callback = f.candidate.alarm(); await gate.enter.promise;
  await f.candidate.deleteScheduled("2"); await f.candidate.suspendAdmission("2"); await f.candidate.close("2");
  await f.candidate.reopen("3"); await f.candidate.schedule("4", "new", 100);
  const before = snapshot(f.storage); gate.release.resolve(); await reject(callback, "fenced");
  assert.deepEqual(snapshot(f.storage), before);
  await f.candidate.alarm(); assert.equal(results(f.storage)[0].result, "local:new");
});

test("admitted callback cannot refresh revision after replacement; retry may freshly admit current work", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "old", 100);
  const gate = f.storage.hold("after"); const callback = f.candidate.alarm(); await gate.enter.promise;
  const old = admission(f.storage); await f.candidate.schedule("2", "new", 100);
  const before = snapshot(f.storage); gate.release.resolve(); await reject(callback, "revision_fenced");
  assert.deepEqual(snapshot(f.storage), before);
  await reject(f.restart().complete(old), "revision_fenced");
  await f.candidate.alarm();
  assert.deepEqual(results(f.storage), [{ id: "2", result: "local:new" }]);
  await f.candidate.suspendAdmission("2"); await reject(f.candidate.close("2"), "drain_incomplete");
  await f.candidate.cancel(old); await f.candidate.close("2");
  await f.candidate.reopen("3"); await f.candidate.schedule("4", "later", 100);
  await reject(f.candidate.complete(old), "fenced");
});

test("admitted local completion drains after admission stops, and close cannot overtake it", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "drain", 100);
  const gate = f.storage.hold("after"); const callback = f.candidate.alarm(); await gate.enter.promise;
  await f.candidate.suspendAdmission("2"); await reject(f.candidate.close("2"), "drain_incomplete");
  gate.release.resolve(); await callback; await f.candidate.close("2");
  const closed = snapshot(f.storage); await reject(f.restart().alarm(), "fenced"); assert.deepEqual(snapshot(f.storage), closed);
});

test("external result is mandatory during drain and after replacement; failed storage fully rolls back", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "external", 100);
  const t = await f.candidate.admitCurrentDue(); assert.ok(Object.isFrozen(t)); await f.candidate.beginExternal(t);
  await f.candidate.schedule("2", "replacement", 200); await f.candidate.suspendAdmission("2");
  await f.candidate.deleteScheduled("2"); const before = snapshot(f.storage);
  for (const fault of ["put", "commit"]) {
    f.storage.failAt = fault; await reject(f.restart().settleExternal(t, "confirmed_success"), "injected_" + fault);
    f.storage.failAt = null; assert.deepEqual(snapshot(f.storage), before);
  }
  await reject(f.restart().cancel(t), "admission_fenced");
  await reject(f.restart().settleExternal(t, "unknown"), "unsettled_external");
  await reject(f.restart().close("2"), "drain_incomplete");
  await f.restart().settleExternal(t, "confirmed_failure");
  assert.deepEqual(results(f.storage), [{ id: t.id, result: "confirmed_failure" }]);
  await f.candidate.close("2"); await reject(f.candidate.settleExternal(t, "confirmed_success"), "fenced");
});

test("stopped admission denies fresh notifications, schedules and external dispatch", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "work", 100);
  const t = await f.candidate.admitCurrentDue(); await f.candidate.suspendAdmission("2");
  const before = snapshot(f.storage);
  await reject(f.candidate.beginExternal(t), "admission_stopped");
  await reject(f.candidate.schedule("2", "new", 100), "admission_stopped");
  await reject(f.candidate.alarm(), "admission_stopped"); assert.deepEqual(snapshot(f.storage), before);
  await f.candidate.complete(t); await f.candidate.close("2");
});

test("future replacement is not stolen by an earlier notification", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "old", 100); await f.candidate.schedule("2", "future", 101);
  const before = snapshot(f.storage); await f.candidate.alarm(); assert.deepEqual(snapshot(f.storage), before);
  f.clock(101); await f.candidate.alarm(); assert.equal(results(f.storage)[0].result, "local:future");
});

test("concurrent notifications admit a due revision once", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "once", 100);
  await Promise.all(Array.from({ length: 8 }, () => f.candidate.alarm()));
  assert.equal(executions(f.storage).length, 1); assert.equal(results(f.storage).length, 1);
});

test("SQL KV alarm changes and admission roll back at meaningful boundaries", async () => {
  for (const fault of ["put", "setAlarm", "commit"]) {
    const f = await fixture(); const before = snapshot(f.storage); f.storage.failAt = fault;
    await reject(f.candidate.schedule("2", "no-leak", 100), "injected_" + fault);
    f.storage.failAt = null; assert.deepEqual(snapshot(f.storage), before);
  }
  for (const fault of ["put", "deleteAlarm", "commit"]) {
    const f = await fixture(); await f.candidate.schedule("2", "retry", 100); const before = snapshot(f.storage);
    f.storage.failAt = fault; await reject(f.candidate.alarm(), "injected_" + fault);
    f.storage.failAt = null; assert.deepEqual(snapshot(f.storage), before);
    await f.candidate.alarm(); assert.equal(results(f.storage)[0].result, "local:retry");
  }
});

test("result SQL failure preserves admitted state and permits exact later completion", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "sql-fault", 100); const t = await f.candidate.admitCurrentDue();
  const before = snapshot(f.storage); const original = f.storage.sql.exec;
  f.storage.sql.exec = (sql, ...args) => { if (sql.startsWith("INSERT INTO pmb1_wake_results")) throw new Error("injected_sql"); return original(sql, ...args); };
  await reject(f.candidate.complete(t), "injected_sql"); f.storage.sql.exec = original;
  assert.deepEqual(snapshot(f.storage), before); await f.candidate.complete(t);
});

test("native handler completion failure retains immutable admission across restart and blocks close", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "retained", 100);
  const original = f.storage.sql.exec;
  f.storage.sql.exec = (sql, ...args) => { if (sql.startsWith("INSERT INTO pmb1_wake_results")) throw new Error("injected_sql"); return original(sql, ...args); };
  await reject(f.candidate.alarm(), "injected_sql"); f.storage.sql.exec = original;
  const t = admission(f.storage); const before = snapshot(f.storage);
  await f.restart().alarm(); assert.deepEqual(snapshot(f.storage), before); // A retry cannot invent a new admission.
  await f.candidate.suspendAdmission("2"); await reject(f.restart().close("2"), "drain_incomplete");
  await f.restart().complete(t); assert.equal(results(f.storage)[0].result, "local:retained");
  await f.candidate.close("2");
});

test("caller token mutation while yielding cannot refresh immutable execution authority", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "original", 100);
  const original = await f.candidate.admitCurrentDue(); const mutable = { ...original };
  const gate = f.storage.hold("before"); const completion = f.candidate.complete(mutable); await gate.enter.promise;
  mutable.revision = "2"; mutable.value = "forged"; gate.release.resolve(); await completion;
  assert.equal(results(f.storage)[0].result, "local:original");
  await reject(f.candidate.complete(mutable), "admission_fenced");
});

test("exact durable counters exceed safe integers; corruption and exhaustion refuse atomically", async () => {
  const f = await fixture(); f.storage.kv.set("pmb1:wake-revision", "9007199254740992");
  f.storage.kv.set("pmb1:wake-admission-sequence", "9007199254740992");
  assert.equal(await f.candidate.schedule("2", "exact", 100), "9007199254740993");
  await f.candidate.alarm(); assert.equal(executions(f.storage)[0].id, "9007199254740993");
  for (const value of [undefined, 2, "01", "9223372036854775808", MAX_GENERATION.toString()]) {
    const g = await fixture(); g.storage.kv.set("pmb1:wake-revision", value); const before = snapshot(g.storage);
    await assert.rejects(g.candidate.schedule("2", "refuse", 100)); assert.deepEqual(snapshot(g.storage), before);
    const h = await fixture(); await h.candidate.schedule("2", "refuse", 100);
    h.storage.kv.set("pmb1:wake-admission-sequence", value); const prior = snapshot(h.storage);
    await assert.rejects(h.candidate.alarm()); assert.deepEqual(snapshot(h.storage), prior);
  }
});

test("closed SQL guards cover every ordinary table and all mutation events; no implicit reopen", async () => {
  const f = await fixture(); await f.candidate.schedule("2", "done", 100); await f.candidate.alarm();
  await f.candidate.suspendAdmission("2"); await f.candidate.close("2"); const before = snapshot(f.storage);
  for (const sql of [
    "INSERT INTO pmb1_wake_work VALUES(2,'2','x',100)", "UPDATE pmb1_wake_work SET value='x'", "DELETE FROM pmb1_wake_work",
    "INSERT INTO pmb1_wake_executions VALUES('2','2','1','x','admitted')", "UPDATE pmb1_wake_executions SET value='x'", "DELETE FROM pmb1_wake_executions",
    "INSERT INTO pmb1_wake_results VALUES('2','x')", "UPDATE pmb1_wake_results SET result='x'", "DELETE FROM pmb1_wake_results",
    "DELETE FROM maintenance_control", "INSERT INTO maintenance_control VALUES(1,4,'open')", "UPDATE maintenance_control SET generation=1,state='open'",
  ]) assert.throws(() => f.storage.sql.exec(sql));
  await reject(f.restart(async generation => ({ generation })).reopen("3"), "disposition_unconfirmed");
  await reject(f.restart().schedule("2", "stale", 100), "fenced");
  assert.deepEqual(snapshot(f.storage), before);
  await f.candidate.reopen("3"); assert.equal(f.storage.kv.get("pmb1:wake-revision"), "1");
  assert.equal(f.storage.kv.get("pmb1:wake-admission-sequence"), "1");
});

test("invalid time/value and stale or duplicate transitions cannot commit", async () => {
  const f = await fixture();
  for (const due of [0, -1, 1.5, Infinity, Number.MAX_SAFE_INTEGER + 1]) await reject(f.candidate.schedule("2", "x", due), "invalid_time");
  await reject(f.candidate.schedule("2", "x".repeat(1025), 100), "invalid_value");
  await reject(f.candidate.close("2"), "admission_not_stopped");
  await f.candidate.suspendAdmission("2"); await f.candidate.close("2");
  await reject(f.candidate.close("2"), "fenced"); await reject(f.candidate.reopen("1"), "transition_refused");
});
