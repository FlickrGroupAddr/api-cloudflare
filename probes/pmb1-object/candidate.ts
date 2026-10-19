// MIT License; copyright 2026 Terry Ott.
// Unregistered PMB-1 source candidate. No Worker entry point or provider binding.
export const MAX_GENERATION = 9223372036854775807n;
export interface Control { singleton_id: 1; generation: string; state: "open" | "closed" }
export interface Invocation { id: string; generation: string }
export interface AlarmDispatch extends Invocation { alarmGeneration: string }
export interface ReopenDisposition {
  generation: string;
  preCloseExecutionsDisposed: true;
  temporaryExecutionsDisposed: true;
  oldVersionsFenced: true;
  queuedAndAlarmCallbacksDisposed: true;
}
// This trusted, separately qualified verifier is deliberately NOT an RPC input.
// No default verifier, guessed evidence, timeout unlock or automatic reopen exists.
export type VerifyDisposition = (generation: string) => Promise<ReopenDisposition>;
type Store = Pick<DurableObjectStorage, "sql" | "transaction">;
const ADMISSION = "pmb1:admission";
const VALUE = "pmb1:value";
const ALARM = "pmb1:alarm-invocation";
const ALARM_SEQUENCE = "pmb1:alarm-sequence";
const VALID = `(SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open')`;

function refuse(reason: string): never { throw new Error(reason); }
function generation(value: unknown): string {
  if (typeof value !== "string" || !/^[1-9][0-9]{0,18}$/.test(value)
      || BigInt(value) > MAX_GENERATION) refuse("invalid_generation");
  return value;
}
function identifier(value: unknown): string {
  if (typeof value !== "string" || !/^[a-zA-Z0-9_-]{1,80}$/.test(value)) refuse("invalid_invocation");
  return value;
}
function token(value: Invocation): Invocation {
  if (value === null || typeof value !== "object") refuse("invalid_invocation");
  return { id: identifier(value.id), generation: generation(value.generation) };
}

// Explicit one-time isolated bootstrap only; never invoked by a constructor,
// ordinary request, alarm, restart or exception recovery. Unexpected state aborts.
export async function bootstrap(storage: Store): Promise<void> {
  await storage.transaction(async tx => {
    if ((await tx.list()).size !== 0 || await tx.getAlarm() !== null) refuse("bootstrap_nonempty");
    if (storage.sql.exec("SELECT name FROM sqlite_master WHERE name <> '__cf_kv'").toArray().length !== 0)
      refuse("bootstrap_nonempty");
    storage.sql.exec(`CREATE TABLE maintenance_control (
      singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(typeof(singleton_id)='integer' AND singleton_id=1),
      generation INTEGER NOT NULL CHECK(typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807),
      state TEXT NOT NULL CHECK(typeof(state)='text' AND state IN ('open','closed')));
      INSERT INTO maintenance_control VALUES(1,1,'closed');
      CREATE TABLE pmb1_executions (id TEXT NOT NULL PRIMARY KEY, generation TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('admitted','external_pending','settled','cancelled')));
      CREATE TABLE pmb1_work (id INTEGER NOT NULL PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
      CREATE TRIGGER pmb1_control_no_insert BEFORE INSERT ON maintenance_control BEGIN SELECT RAISE(ABORT,'control_insert_denied'); END;
      CREATE TRIGGER pmb1_control_no_delete BEFORE DELETE ON maintenance_control BEGIN SELECT RAISE(ABORT,'control_delete_denied'); END;
      CREATE TRIGGER pmb1_control_transition BEFORE UPDATE ON maintenance_control BEGIN
        SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1
        AND typeof(OLD.singleton_id)='integer' AND OLD.singleton_id=1 AND NEW.singleton_id=OLD.singleton_id
        AND typeof(NEW.singleton_id)='integer' AND typeof(OLD.generation)='integer'
        AND OLD.generation BETWEEN 1 AND 9223372036854775806 AND typeof(NEW.generation)='integer'
        AND NEW.generation=OLD.generation+1 AND typeof(OLD.state)='text' AND typeof(NEW.state)='text'
        AND ((OLD.state='open' AND NEW.state='closed') OR (OLD.state='closed' AND NEW.state='open'))
        THEN 1 ELSE RAISE(ABORT,'control_transition_denied') END; END;`);
    for (const table of ["pmb1_executions", "pmb1_work"]) {
      for (const event of ["INSERT", "UPDATE", "DELETE"]) {
        storage.sql.exec(`CREATE TRIGGER ${table}_${event.toLowerCase()} BEFORE ${event} ON ${table}
          BEGIN SELECT CASE WHEN ${VALID} THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;`);
      }
    }
    await tx.put(ADMISSION, false);
    await tx.put(ALARM_SEQUENCE, "0");
  });
}

export class Pmb1ObjectCandidate {
  private storage: Store;
  private verify: VerifyDisposition;
  constructor(storage: Store, verify: VerifyDisposition) {
    this.storage = storage;
    this.verify = verify;
    // Restart performs no write, alarm rearm, admission or self-repair.
  }
  private control(): Control {
    const rows = this.storage.sql.exec(`SELECT singleton_id, typeof(singleton_id) kt,
      CAST(generation AS TEXT) generation, typeof(generation) gt, state, typeof(state) st
      FROM maintenance_control`).toArray();
    if (rows.length !== 1) refuse("invalid_control");
    const r = rows[0];
    if (r.singleton_id !== 1 || r.kt !== "integer" || r.gt !== "integer" || r.st !== "text"
        || (r.state !== "open" && r.state !== "closed")) refuse("invalid_control");
    return { singleton_id: 1, generation: generation(r.generation), state: r.state };
  }
  private open(expected: string): Control {
    const c = this.control();
    if (c.state !== "open" || c.generation !== generation(expected)) refuse("fenced");
    return c;
  }
  private execution(invocation: Invocation, state: "admitted" | "external_pending"): Invocation {
    const t = token(invocation);
    this.open(t.generation);
    const rows = this.storage.sql.exec("SELECT generation,state FROM pmb1_executions WHERE id=?", t.id).toArray();
    if (rows.length !== 1 || rows[0].generation !== t.generation || rows[0].state !== state) refuse("invocation_fenced");
    return t;
  }
  private transition(expected: string, from: "open" | "closed"): Control {
    const c = this.control();
    if (c.state !== from || c.generation !== generation(expected)) refuse("transition_refused");
    if (BigInt(c.generation) === MAX_GENERATION) refuse("generation_exhausted");
    const next = from === "open" ? "closed" : "open";
    this.storage.sql.exec(`UPDATE maintenance_control SET generation=generation+1,state=?
      WHERE singleton_id=1 AND state=? AND CAST(generation AS TEXT)=?`, next, from, expected);
    const changed = this.storage.sql.exec("SELECT changes() n").toArray();
    if (changed.length !== 1 || changed[0].n !== 1) refuse("transition_refused");
    return this.control(); // Acknowledgment only, not independent readback.
  }
  async admit(id: string, expected: string): Promise<Invocation> {
    identifier(id); generation(expected);
    return this.storage.transaction(async tx => {
      const c = this.open(expected);
      if (await tx.get(ADMISSION) !== true) refuse("admission_stopped");
      this.storage.sql.exec("INSERT INTO pmb1_executions VALUES(?,?,'admitted')", id, c.generation);
      return { id, generation: c.generation };
    });
  }
  async suspendAdmission(expected: string): Promise<void> {
    await this.storage.transaction(async tx => {
      this.open(expected);
      await tx.put(ADMISSION, false);
    });
  }
  // The fixed local operation updates SQL and KV together. The optional explicit
  // alarm change shares that same transaction, never a cached pre-await check.
  async write(invocation: Invocation, value: string, alarm: number | null): Promise<AlarmDispatch | null> {
    if (typeof value !== "string" || value.length > 1024) refuse("invalid_value");
    if (alarm !== null && (!Number.isSafeInteger(alarm) || alarm < 1)) refuse("invalid_alarm");
    return this.storage.transaction(async tx => {
      const t = this.execution(invocation, "admitted");
      this.storage.sql.exec("INSERT INTO pmb1_work VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value", value);
      await tx.put(VALUE, value);
      if (alarm === null) {
        await tx.deleteAlarm();
        await tx.delete(ALARM);
        return null;
      } else {
        const previous = await tx.get(ALARM_SEQUENCE);
        if (typeof previous !== "string" || !/^(0|[1-9][0-9]{0,18})$/.test(previous)
            || BigInt(previous) >= MAX_GENERATION) refuse("alarm_sequence_refused");
        const dispatch: AlarmDispatch = { ...t, alarmGeneration: (BigInt(previous) + 1n).toString() };
        await tx.setAlarm(alarm);
        await tx.put(ALARM_SEQUENCE, dispatch.alarmGeneration);
        await tx.put(ALARM, dispatch);
        return dispatch;
      }
    });
  }
  async deleteWork(invocation: Invocation): Promise<void> {
    await this.storage.transaction(async tx => {
      this.execution(invocation, "admitted");
      this.storage.sql.exec("DELETE FROM pmb1_work WHERE id=1");
      await tx.delete(VALUE);
      await tx.deleteAlarm();
      await tx.delete(ALARM);
    });
  }
  async finish(invocation: Invocation): Promise<void> {
    await this.storage.transaction(async tx => {
      const t = this.execution(invocation, "admitted");
      if ((await tx.get<Invocation>(ALARM))?.id === t.id) refuse("alarm_unsettled");
      this.storage.sql.exec("UPDATE pmb1_executions SET state='settled' WHERE id=?", t.id);
    });
  }
  async cancel(invocation: Invocation): Promise<void> {
    await this.storage.transaction(async tx => {
      const t = this.execution(invocation, "admitted");
      if ((await tx.get<Invocation>(ALARM))?.id === t.id) refuse("alarm_unsettled");
      this.storage.sql.exec("UPDATE pmb1_executions SET state='cancelled' WHERE id=?", t.id);
    });
  }
  // Record external admission BEFORE dispatch outside this class. A failed or
  // unknown dispatch stays pending across restart. This class never calls fetch.
  async beginExternal(invocation: Invocation): Promise<void> {
    await this.storage.transaction(async tx => {
      const t = this.execution(invocation, "admitted");
      if (await tx.get(ADMISSION) !== true) refuse("admission_stopped");
      if ((await tx.get<Invocation>(ALARM))?.id === t.id) refuse("alarm_unsettled");
      this.storage.sql.exec("UPDATE pmb1_executions SET state='external_pending' WHERE id=?", t.id);
    });
  }
  // The mandatory result transaction remains admissible DURING drain, before
  // close. Unknown outcomes have no settle method or automatic retry.
  async settleExternal(invocation: Invocation, result: "confirmed_success" | "confirmed_failure"): Promise<void> {
    if (result !== "confirmed_success" && result !== "confirmed_failure") refuse("unsettled_external");
    await this.storage.transaction(async tx => {
      const t = this.execution(invocation, "external_pending");
      this.storage.sql.exec("INSERT INTO pmb1_work VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value", result);
      await tx.put(VALUE, result);
      this.storage.sql.exec("UPDATE pmb1_executions SET state='settled' WHERE id=?", t.id);
    });
  }
  // Explicit callback operation, NOT the native zero-argument alarm handler.
  // The frozen dispatch identity must come from independently qualified delivery
  // provenance. Reading the latest marker alone cannot identify an old retry.
  async alarmCallback(invocation: AlarmDispatch): Promise<void> {
    const callback = token(invocation);
    if (typeof invocation.alarmGeneration !== "string") refuse("stale_alarm");
    const alarmGeneration = generation(invocation.alarmGeneration);
    await this.storage.transaction(async tx => {
      const stored = await tx.get<AlarmDispatch>(ALARM);
      if (stored === undefined) refuse("unknown_alarm");
      if (stored.id !== callback.id || stored.generation !== callback.generation
          || stored.alarmGeneration !== alarmGeneration) refuse("stale_alarm");
      const t = this.execution(stored, "admitted");
      this.storage.sql.exec("INSERT INTO pmb1_work VALUES(1,'alarm') ON CONFLICT(id) DO UPDATE SET value=excluded.value");
      await tx.put(VALUE, "alarm");
      await tx.deleteAlarm();
      await tx.delete(ALARM);
      this.storage.sql.exec("UPDATE pmb1_executions SET state='settled' WHERE id=?", t.id);
    });
  }
  async close(expected: string): Promise<Control> {
    return this.storage.transaction(async tx => {
      this.open(expected);
      if (await tx.get(ADMISSION) !== false) refuse("admission_not_stopped");
      if (this.storage.sql.exec("SELECT id FROM pmb1_executions WHERE state NOT IN ('settled','cancelled')").toArray().length !== 0)
        refuse("drain_incomplete");
      if (await tx.getAlarm() !== null || await tx.get(ALARM) !== undefined) refuse("alarm_unsettled");
      return this.transition(expected, "open");
    });
  }
  async reopen(expected: string): Promise<Control> {
    generation(expected);
    const proof = await this.verify(expected);
    if (proof?.generation !== expected || proof.preCloseExecutionsDisposed !== true
        || proof.temporaryExecutionsDisposed !== true || proof.oldVersionsFenced !== true
        || proof.queuedAndAlarmCallbacksDisposed !== true) refuse("disposition_unconfirmed");
    return this.storage.transaction(async tx => {
      if (this.storage.sql.exec("SELECT id FROM pmb1_executions WHERE state NOT IN ('settled','cancelled')").toArray().length !== 0)
        refuse("drain_incomplete");
      if (await tx.getAlarm() !== null || await tx.get(ALARM) !== undefined) refuse("alarm_unsettled");
      const c = this.transition(expected, "closed");
      await tx.put(ADMISSION, true); // control is now open in this transaction.
      return c;
    });
  }
  // Diagnostic source-local read only: known candidate tables + COMPLETE KV list
  // + exposed alarm time. NOT independent, arbitrary SQL, census or metadata proof.
  async inspect(): Promise<unknown> {
    return this.storage.transaction(async tx => ({
      control: this.control(),
      work: this.storage.sql.exec("SELECT id,value FROM pmb1_work ORDER BY id").toArray(),
      executions: this.storage.sql.exec("SELECT id,generation,state FROM pmb1_executions ORDER BY id").toArray(),
      kv: Array.from(await tx.list()), alarm: await tx.getAlarm(),
    }));
  }
}
