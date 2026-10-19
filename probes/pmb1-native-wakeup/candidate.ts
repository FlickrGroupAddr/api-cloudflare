// MIT License; copyright 2026 Terry Ott.
// Unregistered successor. Native notifications are hints, never arm identities.
export { MAX_GENERATION } from "../pmb1-object/candidate.ts";
import { MAX_GENERATION, type Control, type VerifyDisposition } from "../pmb1-object/candidate.ts";
type Store = Pick<DurableObjectStorage, "sql" | "transaction">;
export interface Admission { readonly id: string; readonly generation: string; readonly revision: string; readonly value: string }
const ADMISSION = "pmb1:admission";
const REVISION = "pmb1:wake-revision";
const SEQUENCE = "pmb1:wake-admission-sequence";
const VALID = `(SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open')`;
function refuse(reason: string): never { throw new Error(reason); }
function counter(value: unknown, zero = false): string {
  if (typeof value !== "string" || !(zero ? /^(0|[1-9][0-9]{0,18})$/ : /^[1-9][0-9]{0,18}$/).test(value)
    || BigInt(value) > MAX_GENERATION) refuse("invalid_counter");
  return value;
}
function time(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) refuse("invalid_time");
  return value;
}
function token(value: Admission): Admission {
  if (value === null || typeof value !== "object" || typeof value.value !== "string" || value.value.length > 1024)
    refuse("invalid_admission");
  return Object.freeze({ id: counter(value.id), generation: counter(value.generation), revision: counter(value.revision), value: value.value });
}

// Explicit isolated bootstrap only. No construction/restart/alarm repair path.
export async function bootstrap(storage: Store): Promise<void> {
  await storage.transaction(async tx => {
    if ((await tx.list()).size || await tx.getAlarm() !== null
      || storage.sql.exec("SELECT name FROM sqlite_master WHERE name <> '__cf_kv'").toArray().length) refuse("bootstrap_nonempty");
    storage.sql.exec(`CREATE TABLE maintenance_control (
      singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(typeof(singleton_id)='integer' AND singleton_id=1),
      generation INTEGER NOT NULL CHECK(typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807),
      state TEXT NOT NULL CHECK(typeof(state)='text' AND state IN ('open','closed')));
      INSERT INTO maintenance_control VALUES(1,1,'closed');
      CREATE TABLE pmb1_wake_work (id INTEGER NOT NULL PRIMARY KEY CHECK(id=1), revision TEXT NOT NULL,
        value TEXT NOT NULL, due INTEGER CHECK(due IS NULL OR (typeof(due)='integer' AND due>0)));
      CREATE TABLE pmb1_wake_executions (id TEXT NOT NULL PRIMARY KEY, generation TEXT NOT NULL,
        revision TEXT NOT NULL, value TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('admitted','external_pending','settled','cancelled')));
      CREATE TABLE pmb1_wake_results (id TEXT NOT NULL PRIMARY KEY, result TEXT NOT NULL);
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
    for (const table of ["pmb1_wake_work", "pmb1_wake_executions", "pmb1_wake_results"])
      for (const event of ["INSERT", "UPDATE", "DELETE"])
        storage.sql.exec(`CREATE TRIGGER ${table}_${event.toLowerCase()} BEFORE ${event} ON ${table}
          BEGIN SELECT CASE WHEN ${VALID} THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;`);
    await tx.put(ADMISSION, false); await tx.put(REVISION, "0"); await tx.put(SEQUENCE, "0");
  });
}

export class Pmb1NativeWakeup implements Pick<DurableObject, "alarm"> {
  private storage: Store;
  private verify: VerifyDisposition;
  private clock: () => number;
  constructor(storage: Store, verify: VerifyDisposition, clock: () => number = Date.now) {
    this.storage = storage; this.verify = verify; this.clock = clock;
  }
  private control(): Control {
    const rows = this.storage.sql.exec(`SELECT singleton_id,typeof(singleton_id) kt,CAST(generation AS TEXT) generation,
      typeof(generation) gt,state,typeof(state) st FROM maintenance_control`).toArray();
    if (rows.length !== 1) refuse("invalid_control");
    const r = rows[0];
    if (r.singleton_id !== 1 || r.kt !== "integer" || r.gt !== "integer" || r.st !== "text"
      || (r.state !== "open" && r.state !== "closed")) refuse("invalid_control");
    return { singleton_id: 1, generation: counter(r.generation), state: r.state };
  }
  private open(expected: string): Control {
    const c = this.control();
    if (c.state !== "open" || c.generation !== counter(expected)) refuse("fenced");
    return c;
  }
  private execution(input: Admission, state: "admitted" | "external_pending", currentRevision: boolean): Admission {
    const t = token(input); this.open(t.generation);
    const rows = this.storage.sql.exec("SELECT generation,revision,value,state FROM pmb1_wake_executions WHERE id=?", t.id).toArray();
    if (rows.length !== 1 || rows[0].generation !== t.generation || rows[0].revision !== t.revision
      || rows[0].value !== t.value || rows[0].state !== state) refuse("admission_fenced");
    if (currentRevision) {
      const work = this.storage.sql.exec("SELECT revision FROM pmb1_wake_work WHERE id=1").toArray();
      if (work.length !== 1 || work[0].revision !== t.revision) refuse("revision_fenced");
    }
    return t;
  }
  private async next(tx: DurableObjectTransaction, key: string): Promise<string> {
    const previous = counter(await tx.get(key), true);
    if (BigInt(previous) === MAX_GENERATION) refuse("counter_exhausted");
    const next = (BigInt(previous) + 1n).toString(); await tx.put(key, next); return next;
  }
  async schedule(expected: string, value: string, due: number): Promise<string> {
    counter(expected); time(due);
    if (typeof value !== "string" || value.length > 1024) refuse("invalid_value");
    return this.storage.transaction(async tx => {
      this.open(expected); if (await tx.get(ADMISSION) !== true) refuse("admission_stopped");
      const revision = await this.next(tx, REVISION);
      this.storage.sql.exec(`INSERT INTO pmb1_wake_work VALUES(1,?,?,?) ON CONFLICT(id)
        DO UPDATE SET revision=excluded.revision,value=excluded.value,due=excluded.due`, revision, value, due);
      await tx.put("pmb1:wake-value", value); await tx.setAlarm(due); return revision;
    });
  }
  // Synchronous capture occurs before the first await, including transaction admission.
  // No event information, timestamp, retry count or cached constructor arm is authority.
  async alarm(): Promise<void> {
    const captured = this.control();
    const admission = await this.admitDue(captured.generation);
    if (admission !== null) await this.complete(admission);
  }
  // The same fixed admission is exposed for a later trusted dispatcher bridge.
  // It captures control before yielding and cannot refresh it after waiting.
  async admitCurrentDue(): Promise<Admission | null> {
    const captured = this.control();
    return this.admitDue(captured.generation);
  }
  private async admitDue(expected: string): Promise<Admission | null> {
    return this.storage.transaction(async tx => {
      this.open(expected); if (await tx.get(ADMISSION) !== true) refuse("admission_stopped");
      const now = time(this.clock());
      const rows = this.storage.sql.exec("SELECT revision,value,due FROM pmb1_wake_work WHERE id=1").toArray();
      if (rows.length === 0) return null;
      const w = rows[0]; const revision = counter(w.revision);
      if (typeof w.value !== "string" || w.value.length > 1024) refuse("invalid_work");
      if (w.due === null || time(w.due) > now) return null;
      const id = await this.next(tx, SEQUENCE);
      const admission = token({ id, generation: expected, revision, value: w.value });
      this.storage.sql.exec("INSERT INTO pmb1_wake_executions VALUES(?,?,?,?,'admitted')", id, expected, revision, w.value);
      this.storage.sql.exec("UPDATE pmb1_wake_work SET due=NULL WHERE id=1 AND revision=?", revision);
      await tx.deleteAlarm(); return admission;
    });
  }
  async complete(input: Admission): Promise<void> {
    // Freeze before the first await; caller mutation cannot change authority.
    const frozen = token(input);
    await this.storage.transaction(async tx => {
      const t = this.execution(frozen, "admitted", true);
      this.storage.sql.exec("INSERT INTO pmb1_wake_results VALUES(?,?)", t.id, "local:" + t.value);
      await tx.put("pmb1:wake-result:" + t.id, "local:" + t.value);
      this.storage.sql.exec("UPDATE pmb1_wake_executions SET state='settled' WHERE id=?", t.id);
    });
  }
  async cancel(input: Admission): Promise<void> {
    const frozen = token(input);
    await this.storage.transaction(async () => {
      const t = this.execution(frozen, "admitted", false);
      this.storage.sql.exec("UPDATE pmb1_wake_executions SET state='cancelled' WHERE id=?", t.id);
    });
  }
  // Durable marker MUST commit before any later caller sends an external effect.
  async beginExternal(input: Admission): Promise<void> {
    const frozen = token(input);
    await this.storage.transaction(async tx => {
      const t = this.execution(frozen, "admitted", true);
      if (await tx.get(ADMISSION) !== true) refuse("admission_stopped");
      this.storage.sql.exec("UPDATE pmb1_wake_executions SET state='external_pending' WHERE id=?", t.id);
    });
  }
  async settleExternal(input: Admission, result: "confirmed_success" | "confirmed_failure"): Promise<void> {
    const frozen = token(input);
    if (result !== "confirmed_success" && result !== "confirmed_failure") refuse("unsettled_external");
    await this.storage.transaction(async tx => {
      // Mandatory safety result belongs to this execution even after replacement.
      const t = this.execution(frozen, "external_pending", false);
      this.storage.sql.exec("INSERT INTO pmb1_wake_results VALUES(?,?)", t.id, result);
      await tx.put("pmb1:wake-result:" + t.id, result);
      this.storage.sql.exec("UPDATE pmb1_wake_executions SET state='settled' WHERE id=?", t.id);
    });
  }
  async suspendAdmission(expected: string): Promise<void> {
    await this.storage.transaction(async tx => { this.open(expected); await tx.put(ADMISSION, false); });
  }
  async deleteScheduled(expected: string): Promise<void> {
    await this.storage.transaction(async tx => {
      this.open(expected);
      this.storage.sql.exec("DELETE FROM pmb1_wake_work WHERE id=1");
      await tx.delete("pmb1:wake-value"); await tx.deleteAlarm();
    });
  }
  private empty(): void {
    if (this.storage.sql.exec("SELECT id FROM pmb1_wake_executions WHERE state NOT IN ('settled','cancelled')").toArray().length)
      refuse("drain_incomplete");
    if (this.storage.sql.exec("SELECT id FROM pmb1_wake_work WHERE due IS NOT NULL").toArray().length) refuse("alarm_unsettled");
  }
  private transition(expected: string, from: "open" | "closed"): Control {
    const c = this.control();
    if (c.generation !== counter(expected) || c.state !== from) refuse("transition_refused");
    if (BigInt(expected) === MAX_GENERATION) refuse("counter_exhausted");
    this.storage.sql.exec(`UPDATE maintenance_control SET generation=generation+1,state=?
      WHERE singleton_id=1 AND state=? AND CAST(generation AS TEXT)=?`, from === "open" ? "closed" : "open", from, expected);
    if (this.storage.sql.exec("SELECT changes() n").toArray()[0]?.n !== 1) refuse("transition_refused");
    return this.control();
  }
  async close(expected: string): Promise<Control> {
    return this.storage.transaction(async tx => {
      this.open(expected); if (await tx.get(ADMISSION) !== false) refuse("admission_not_stopped");
      this.empty(); if (await tx.getAlarm() !== null) refuse("alarm_unsettled");
      return this.transition(expected, "open");
    });
  }
  async reopen(expected: string): Promise<Control> {
    counter(expected); const proof = await this.verify(expected);
    if (proof?.generation !== expected || proof.preCloseExecutionsDisposed !== true
      || proof.temporaryExecutionsDisposed !== true || proof.oldVersionsFenced !== true
      || proof.queuedAndAlarmCallbacksDisposed !== true) refuse("disposition_unconfirmed");
    return this.storage.transaction(async tx => {
      this.empty(); if (await tx.getAlarm() !== null) refuse("alarm_unsettled");
      const c = this.transition(expected, "closed"); await tx.put(ADMISSION, true); return c;
    });
  }
}
