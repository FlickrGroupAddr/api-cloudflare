// Synthetic local adapter only. It models SQLite+KV+explicit alarm rollback and
// serialization; it does not emulate provider alarm delivery metadata or gates.
import assert from "node:assert/strict";
import test from "node:test";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { Pmb1ObjectCandidate, bootstrap } from "./candidate.ts";

class LocalStorage {
  db = new DatabaseSync(":memory:");
  kv = new Map();
  alarm = null;
  tail = Promise.resolve();
  failAt = null;
  sql = { exec: (sql, ...values) => {
    // Provider exec accepts multi-statement DDL; test adapter uses db.exec for it.
    if (values.length === 0 && sql.includes("CREATE TABLE")) {
      this.db.exec(sql); return { toArray: () => [] };
    }
    const stmt = this.db.prepare(sql);
    return { toArray: () => stmt.all(...values) };
  }};
  // SQL execute is eager, as in the provider cursor API, not deferred to toArray.
  constructor() {
    const raw = this.sql.exec;
    this.sql.exec = (...args) => {
      const cursor = raw(...args); const rows = cursor.toArray();
      return { toArray: () => rows };
    };
  }
  async transaction(fn) {
    const previous = this.tail;
    let release;
    this.tail = new Promise(resolve => { release = resolve; });
    await previous;
    const before = structuredClone(this.kv); const alarm = this.alarm;
    this.db.exec("BEGIN IMMEDIATE");
    const step = name => { if (this.failAt === name) throw new Error("injected_" + name); };
    const tx = {
      get: async key => { step("get"); return structuredClone(this.kv.get(key)); },
      list: async () => { step("list"); return structuredClone(this.kv); },
      put: async (key, value) => { step("put"); this.kv.set(key, structuredClone(value)); },
      delete: async key => { step("delete"); return this.kv.delete(key); },
      getAlarm: async () => { step("getAlarm"); return this.alarm; },
      setAlarm: async value => { step("setAlarm"); this.alarm = value; },
      deleteAlarm: async () => { step("deleteAlarm"); this.alarm = null; },
    };
    try {
      const result = await fn(tx); step("commit"); this.db.exec("COMMIT"); return result;
    } catch (error) {
      this.db.exec("ROLLBACK"); this.kv = before; this.alarm = alarm; throw error;
    } finally { release(); }
  }
}
const disposition = async generation => ({ generation, preCloseExecutionsDisposed: true,
  temporaryExecutionsDisposed: true, oldVersionsFenced: true, queuedAndAlarmCallbacksDisposed: true });
async function fixture(open = true, verify = disposition) {
  const storage = new LocalStorage(); await bootstrap(storage);
  const candidate = new Pmb1ObjectCandidate(storage, verify);
  if (open) await candidate.reopen("1");
  return { storage, candidate };
}
async function drained(candidate, expected = "2") {
  await candidate.suspendAdmission(expected); return candidate.close(expected);
}

test("explicit bootstrap starts closed, refuses repetition and constructor restart writes nothing", async () => {
  const { storage, candidate } = await fixture(false);
  const baseline = await candidate.inspect();
  assert.equal(baseline.control.generation, "1");
  assert.equal(baseline.control.state, "closed");
  await assert.rejects(bootstrap(storage), /bootstrap_nonempty/);
  const restart = new Pmb1ObjectCandidate(storage, disposition);
  assert.deepEqual(await restart.inspect(), baseline);
  await assert.rejects(restart.admit("x", "1"), /fenced/);
  await assert.rejects(restart.alarmCallback({ id: "old", generation: "1", alarmGeneration: "1" }), /unknown_alarm/);
  assert.deepEqual(await restart.inspect(), baseline);
});
test("bootstrap rejects unknown schema and unknown KV/alarm state without repair", async () => {
  for (const kind of ["schema", "kv", "alarm"]) {
    const storage = new LocalStorage();
    if (kind === "schema") storage.db.exec("CREATE TABLE unexpected (id)");
    if (kind === "kv") storage.kv.set("unexpected", 1);
    if (kind === "alarm") storage.alarm = 1;
    await assert.rejects(bootstrap(storage), /bootstrap_nonempty/);
    assert.equal(storage.db.prepare("SELECT count(*) n FROM sqlite_master WHERE name='maintenance_control'").get().n, 0);
  }
});
test("canonical exact generation, duplicate transitions and malformed controls refuse", async () => {
  const { storage, candidate } = await fixture();
  for (const expected of ["0", "02", "2.0", " 2", 2, "9223372036854775808", "3"])
    await assert.rejects(candidate.admit("invalid", expected));
  await assert.rejects(candidate.reopen("2"), /transition_refused/);
  await drained(candidate);
  await assert.rejects(candidate.close("3"), /fenced/);
  for (const sql of ["INSERT INTO maintenance_control VALUES(1,3,'closed')",
    "DELETE FROM maintenance_control", "UPDATE maintenance_control SET generation=generation+2,state='open'",
    "UPDATE maintenance_control SET singleton_id=2", "UPDATE maintenance_control SET state=state"])
    assert.throws(() => storage.db.exec(sql));
  storage.db.exec("DROP TRIGGER pmb1_control_no_delete; DELETE FROM maintenance_control;");
  await assert.rejects(candidate.admit("x", "3"), /invalid_control/);
});
test("generation stays exact above JS safe integer and refuses maximum exhaustion", async () => {
  const { storage, candidate } = await fixture(false);
  storage.db.exec("DROP TRIGGER pmb1_control_transition; UPDATE maintenance_control SET generation=9223372036854775806;");
  assert.deepEqual(await candidate.reopen("9223372036854775806"), {
    singleton_id: 1, generation: "9223372036854775807", state: "open" });
  await candidate.suspendAdmission("9223372036854775807");
  await assert.rejects(candidate.close("9223372036854775807"), /generation_exhausted/);
});
test("SQL, KV and explicit alarm create, replace, delete share guarded transaction", async () => {
  const { candidate } = await fixture(); const t = await candidate.admit("work", "2");
  await candidate.write(t, "first", 100); await candidate.write(t, "second", 200);
  const state = await candidate.inspect();
  assert.equal(state.work[0].value, "second"); assert.equal(state.alarm, 200);
  assert.equal(new Map(state.kv).get("pmb1:value"), "second");
  await candidate.deleteWork(t); await candidate.finish(t); await drained(candidate);
  const closed = await candidate.inspect();
  assert.equal(closed.work.length, 0); assert.equal(closed.alarm, null);
  await assert.rejects(candidate.write(t, "late", 300), /fenced/);
  await assert.rejects(candidate.deleteWork(t), /fenced/);
  assert.deepEqual(await candidate.inspect(), closed);
});
for (const stage of ["put", "setAlarm", "deleteAlarm", "delete", "commit"]) {
  test(`injected ${stage} failure rolls SQL/KV/alarm back together`, async () => {
    const { storage, candidate } = await fixture(); const t = await candidate.admit("work", "2");
    await candidate.write(t, "before", 100); const before = await candidate.inspect();
    storage.failAt = stage;
    await assert.rejects(stage === "delete" || stage === "deleteAlarm"
      ? candidate.deleteWork(t) : candidate.write(t, "after", 200), /injected_/);
    storage.failAt = null; assert.deepEqual(await candidate.inspect(), before);
  });
}
test("admission stops durably, admitted work drains before close, no timeout unlock", async () => {
  const { storage, candidate } = await fixture(); const t = await candidate.admit("drain", "2");
  await candidate.suspendAdmission("2");
  await assert.rejects(candidate.admit("new", "2"), /admission_stopped/);
  await assert.rejects(candidate.close("2"), /drain_incomplete/);
  const restart = new Pmb1ObjectCandidate(storage, disposition);
  await assert.rejects(restart.admit("new", "2"), /admission_stopped/);
  await restart.write(t, "settled-before-close", null); await restart.finish(t);
  assert.equal((await restart.close("2")).state, "closed");
});
test("external pending survives restart, cannot cancel, and blocks close until mandatory result", async () => {
  const { storage, candidate } = await fixture(); const t = await candidate.admit("external", "2");
  await candidate.beginExternal(t); await candidate.suspendAdmission("2");
  const restart = new Pmb1ObjectCandidate(storage, disposition);
  await assert.rejects(restart.cancel(t), /invocation_fenced/);
  await assert.rejects(restart.settleExternal(t, "unknown"), /unsettled_external/);
  await assert.rejects(restart.close("2"), /drain_incomplete/);
  await restart.settleExternal(t, "confirmed_success");
  const closed = await restart.close("2"); assert.equal(closed.generation, "3");
  await assert.rejects(restart.settleExternal(t, "confirmed_failure"), /fenced/);
});
test("drain prevents new external dispatch markers while allowing existing result settlement", async () => {
  const { candidate } = await fixture(); const t = await candidate.admit("external", "2");
  await candidate.suspendAdmission("2");
  await assert.rejects(candidate.beginExternal(t), /admission_stopped/);
  await candidate.cancel(t); await candidate.close("2");
});
test("failed mandatory result transaction preserves pending state and refuses closure", async () => {
  const { storage, candidate } = await fixture(); const t = await candidate.admit("external", "2");
  await candidate.beginExternal(t); await candidate.suspendAdmission("2");
  storage.failAt = "put"; await assert.rejects(candidate.settleExternal(t, "confirmed_failure"));
  storage.failAt = null; await assert.rejects(candidate.close("2"), /drain_incomplete/);
  assert.equal((await candidate.inspect()).executions[0].state, "external_pending");
});
test("explicit alarm must settle before close; delivery and retry after close mutate nothing", async () => {
  const { candidate } = await fixture(); const t = await candidate.admit("alarm", "2");
  const dispatch = await candidate.write(t, "pending", 100); await candidate.suspendAdmission("2");
  await assert.rejects(candidate.finish(t), /alarm_unsettled/);
  await assert.rejects(candidate.close("2"), /drain_incomplete/);
  await candidate.alarmCallback(dispatch); await candidate.close("2");
  const closed = await candidate.inspect();
  await assert.rejects(candidate.alarmCallback(dispatch), /unknown_alarm/);
  assert.deepEqual(await candidate.inspect(), closed);
});
test("reopen requires complete independent disposition and old callback tokens remain fenced", async () => {
  const { storage, candidate } = await fixture(); const t = await candidate.admit("stale", "2");
  await candidate.cancel(t); await drained(candidate);
  const baseline = await candidate.inspect();
  for (const verify of [async () => undefined, async () => ({}),
    async g => ({ ...await disposition(g), oldVersionsFenced: false }),
    async () => { throw new Error("unavailable"); }]) {
    const restart = new Pmb1ObjectCandidate(storage, verify);
    await assert.rejects(restart.reopen("3")); assert.deepEqual(await restart.inspect(), baseline);
  }
  await candidate.reopen("3");
  await assert.rejects(candidate.write(t, "stale", null), /fenced/);
  await assert.rejects(candidate.beginExternal(t), /fenced/);
});
test("old alarm delivery identity cannot consume a newer alarm marker, including after reopen", async () => {
  const { candidate } = await fixture(); const old = await candidate.admit("old", "2");
  const oldDispatch = await candidate.write(old, "old", 100); await candidate.deleteWork(old);
  await candidate.cancel(old); await drained(candidate); await candidate.reopen("3");
  const current = await candidate.admit("current", "4"); const currentDispatch = await candidate.write(current, "new", 200);
  assert.equal(currentDispatch.alarmGeneration, "2");
  const before = await candidate.inspect();
  await assert.rejects(candidate.alarmCallback(oldDispatch), /stale_alarm/);
  assert.deepEqual(await candidate.inspect(), before);
  await candidate.alarmCallback(currentDispatch);
});
test("same invocation alarm replacement has a fresh dispatch identity even at an identical time", async () => {
  const { candidate } = await fixture(); const invocation = await candidate.admit("same", "2");
  const first = await candidate.write(invocation, "first", 100);
  const replacement = await candidate.write(invocation, "replacement", 100);
  assert.equal(first.alarmGeneration, "1"); assert.equal(replacement.alarmGeneration, "2");
  const before = await candidate.inspect();
  await assert.rejects(candidate.alarmCallback(first), /stale_alarm/);
  await assert.rejects(candidate.alarmCallback(invocation), /stale_alarm/);
  assert.deepEqual(await candidate.inspect(), before);
  await candidate.alarmCallback(replacement);
});
test("alarm sequence never resets on deletion and malformed or exhausted authority rolls back the arm", async () => {
  const { storage, candidate } = await fixture(); const invocation = await candidate.admit("same", "2");
  const first = await candidate.write(invocation, "first", 100);
  await candidate.deleteWork(invocation);
  const second = await candidate.write(invocation, "second", 200);
  assert.equal(second.alarmGeneration, "2");
  await assert.rejects(candidate.alarmCallback(first), /stale_alarm/);
  for (const counter of [undefined, null, 2, "02", "-1", "9223372036854775807", "9223372036854775808"]) {
    storage.kv.set("pmb1:alarm-sequence", counter); const before = await candidate.inspect();
    await assert.rejects(candidate.write(invocation, "refused", 300), /alarm_sequence_refused/);
    assert.deepEqual(await candidate.inspect(), before);
  }
});
test("concurrent close and admission serialize: preceding admission blocks close, later admission refuses", async () => {
  const { candidate } = await fixture();
  const admitted = candidate.admit("before", "2");
  const stop = candidate.suspendAdmission("2"); const close = candidate.close("2");
  const t = await admitted; await stop; await assert.rejects(close, /drain_incomplete/);
  await candidate.cancel(t); const closing = candidate.close("2");
  const after = candidate.admit("after", "2");
  await closing; await assert.rejects(after, /fenced/);
});
test("concurrent admitted mutation fully commits before successful close; post-close mutation refuses", async () => {
  const { candidate } = await fixture(); const t = await candidate.admit("before", "2");
  await candidate.suspendAdmission("2");
  const write = candidate.write(t, "committed", null); const finish = candidate.finish(t); const close = candidate.close("2");
  await Promise.all([write, finish, close]); const baseline = await candidate.inspect();
  await assert.rejects(candidate.write(t, "after", null), /fenced/);
  assert.deepEqual(await candidate.inspect(), baseline);
});
test("direct ordinary SQL mutations refuse while closed including REPLACE", async () => {
  const { storage, candidate } = await fixture(); const t = await candidate.admit("existing", "2");
  await candidate.write(t, "original", null); await candidate.finish(t); await drained(candidate);
  const before = await candidate.inspect();
  for (const sql of ["INSERT INTO pmb1_work VALUES(2,'x')", "REPLACE INTO pmb1_work VALUES(1,'x')",
    "UPDATE pmb1_work SET value='changed'", "DELETE FROM pmb1_work",
    "INSERT INTO pmb1_executions VALUES('x','1','admitted')",
    "UPDATE pmb1_executions SET state='admitted'", "DELETE FROM pmb1_executions"])
    assert.throws(() => storage.db.exec(sql), /maintenance_closed/);
  assert.deepEqual(await candidate.inspect(), before);
});
test("source is unregistered and scoped config inherits canonical strict compiler policy", () => {
  const source = readFileSync(new URL("./candidate.ts", import.meta.url), "utf8");
  assert.equal(source.includes("export default"), false);
  assert.equal(/\bfetch\s*\(/.test(source), false);
  const config = JSON.parse(readFileSync(new URL("./tsconfig.json", import.meta.url), "utf8"));
  assert.deepEqual(config, { extends: "../../tsconfig.json", include: ["./candidate.ts"] });
});
