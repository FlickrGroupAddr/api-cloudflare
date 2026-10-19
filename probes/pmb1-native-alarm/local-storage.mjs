// MIT License; copyright 2026 Terry Ott.
// Synthetic SQLite/KV/explicit-alarm adapter. No provider scheduling emulation.
import { DatabaseSync } from "node:sqlite";

export class LocalStorage {
  db = new DatabaseSync(":memory:");
  kv = new Map();
  alarm = null;
  tail = Promise.resolve();
  failAt = null;
  sql = { exec: (sql, ...values) => {
    if (values.length === 0 && sql.includes("CREATE TABLE")) {
      this.db.exec(sql); return { toArray: () => [] };
    }
    const rows = this.db.prepare(sql).all(...values);
    return { toArray: () => rows };
  }};
  async transaction(fn) {
    const previous = this.tail;
    let release;
    this.tail = new Promise(resolve => { release = resolve; });
    await previous;
    const kv = structuredClone(this.kv), alarm = this.alarm;
    this.db.exec("BEGIN IMMEDIATE");
    const step = name => { if (this.failAt === name) throw new Error("injected_" + name); };
    const tx = {
      get: async key => { step("get"); return structuredClone(this.kv.get(key)); },
      list: async () => { step("list"); return structuredClone(this.kv); },
      put: async (key, value) => { step("put"); this.kv.set(key, structuredClone(value)); },
      delete: async key => { step("delete"); return this.kv.delete(key); },
      getAlarm: async () => { step("getAlarm"); return this.alarm; },
      setAlarm: async time => { step("setAlarm"); this.alarm = time; },
      deleteAlarm: async () => { step("deleteAlarm"); this.alarm = null; },
    };
    try {
      const result = await fn(tx); step("commit"); this.db.exec("COMMIT"); return result;
    } catch (error) {
      this.db.exec("ROLLBACK"); this.kv = kv; this.alarm = alarm; throw error;
    } finally { release(); }
  }
}

export function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
