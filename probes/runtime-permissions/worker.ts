import { allSetup, CASES, D1_PHASE_SIZE, PHASE_COUNT, type ProbeCase, type Row } from "./cases.ts";

interface Env {
  DB: D1Database;
  PROBE_OBJECT: DurableObjectNamespace;
  PROBE_RUN_ID: string;
  PROBE_MODE: string;
  PROBE_TOKEN: string;
}
interface Store {
  query(sql: string, values?: string[]): Promise<Row[]>;
  batch(statements: string[]): Promise<void>;
}
interface Snapshot {
  tableExists: boolean;
  rowCount: number;
  originalIntact: boolean;
  addedIntact: boolean;
  invalidCheckRows: number;
  triggerCount: number;
}
interface Result {
  id: string;
  kind: ProbeCase["kind"];
  family: string;
  execution: "allowed" | "denied_guard" | "denied_check" | "denied_foreign_key" | "operation_error";
  before: Snapshot;
  after: Snapshot;
  forbiddenChangeObserved: boolean;
}
function response(data: unknown, status = 200): Response {
  return Response.json(data, { status, headers: { "Cache-Control": "no-store" } });
}
function d1Store(db: D1Database): Store {
  return {
    async query(sql, values = []) {
      return (await db.prepare(sql).bind(...values).all<Row>()).results;
    },
    async batch(statements) {
      if (statements.length) await db.batch(statements.map((sql) => db.prepare(sql)));
    },
  };
}
function objectStore(storage: DurableObjectStorage): Store {
  return {
    async query(sql, values = []) {
      return storage.sql.exec<Row>(sql, ...values).toArray();
    },
    async batch(statements) {
      storage.transactionSync(() => {
        for (const sql of statements) storage.sql.exec(sql).toArray();
      });
    },
  };
}
async function snapshot(store: Store, table: string): Promise<Snapshot> {
  const schemaObjects = await store.query(
    "SELECT type, name FROM sqlite_master WHERE tbl_name = ? ORDER BY type, name",
    [table],
  );
  const tableExists = schemaObjects.some((row) => row.type === "table");
  const rows = tableExists ? await store.query(
    `SELECT record_id, evidence, check_value FROM ${table} ORDER BY record_id`,
  ) : [];
  return {
    tableExists, rowCount: rows.length,
    originalIntact: rows.some((r) => r.record_id === "seed" && r.evidence === "original" && r.check_value === 1),
    addedIntact: rows.some((r) => r.record_id === "added" && r.evidence === "new" && r.check_value === 1),
    invalidCheckRows: rows.filter((r) => r.check_value !== 1).length,
    triggerCount: schemaObjects.filter((r) => r.type === "trigger").length,
  };
}
function classify(error: unknown): Result["execution"] {
  let current = error;
  for (let depth = 0; current instanceof Error && depth < 5; depth++) {
    if (current.message.includes("FGA_PROBE_GUARD")) return "denied_guard";
    if (current.message.includes("CHECK constraint failed")) return "denied_check";
    if (current.message.includes("FOREIGN KEY constraint failed")) return "denied_foreign_key";
    current = current.cause;
  }
  // Infrastructure/syntax/unsupported errors are not successful permission denials.
  return "operation_error";
}
async function runCases(store: Store, tests: ProbeCase[] = CASES): Promise<Result[]> {
  const results: Result[] = [];
  for (const test of tests) {
    const before = await snapshot(store, test.table);
    if (!before.tableExists || before.rowCount !== 1 || !before.originalIntact) throw new Error("fixture_integrity");
    let execution: Result["execution"] = "allowed";
    try {
      await store.batch(test.steps);
    } catch (error) {
      execution = classify(error);
    }
    const after = await snapshot(store, test.table);
    results.push({
      id: test.id, family: test.family, kind: test.kind, execution, before, after,
      forbiddenChangeObserved: test.kind !== "control" &&
        JSON.stringify(before) !== JSON.stringify(after),
    });
  }
  return results;
}
async function engineMetadata(store: Store) {
  try {
    const rows = await store.query("SELECT sqlite_version() AS version");
    return { sqliteVersion: rows[0]?.version ?? null, sqliteVersionObservation: "reported" };
  } catch {
    // Some runtime SQL authorizers do not expose engine metadata. Record the
    // missing observation; actual fixture/constraint checks remain mandatory.
    return { sqliteVersion: null, sqliteVersionObservation: "unavailable" };
  }
}
async function claim(store: Store, runId: string): Promise<number | null> {
  // Each invocation consumes one bounded phase. Response loss makes a run
  // incomplete; collectors refuse a missing phase instead of replaying attacks.
  const changed = await store.query(
    `UPDATE probe_meta SET executed = executed + 1
     WHERE run_id = ? AND executed < ${PHASE_COUNT}
       AND (SELECT COUNT(*) FROM probe_meta) = 1
     RETURNING executed - 1 AS phase`,
    [runId],
  );
  return changed.length === 1 ? Number(changed[0].phase) : null;
}
function validEnvironment(env: Env): boolean {
  return /^rp-[a-f0-9]{24}$/.test(env.PROBE_RUN_ID) &&
    ["local", "cloudflare"].includes(env.PROBE_MODE) &&
    typeof env.PROBE_TOKEN === "string" && env.PROBE_TOKEN.length >= 32;
}
function authorized(request: Request, env: Env): boolean {
  const value = request.headers.get("Authorization") ?? "";
  const expected = `Bearer ${env.PROBE_TOKEN}`;
  const encoder = new TextEncoder();
  const actualBytes = encoder.encode(value);
  const expectedBytes = encoder.encode(expected);
  return actualBytes.byteLength === expectedBytes.byteLength &&
    crypto.subtle.timingSafeEqual(actualBytes, expectedBytes);
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname !== "/run" || url.search) return response({ error: "not_found" }, 404);
    if (request.method !== "POST") return response({ error: "method_not_allowed" }, 405);
    if (!validEnvironment(env)) return response({ error: "unconfigured_probe" }, 503);
    if (!authorized(request, env)) return response({ error: "unauthorized" }, 401);
    if (request.body !== null) {
      const reader = request.body.getReader();
      const first = await reader.read();
      await reader.cancel();
      if (!first.done) return response({ error: "body_not_allowed" }, 400);
    }
    const store = d1Store(env.DB);
    let stage = "fixture_claim";
    try {
      const phase = await claim(store, env.PROBE_RUN_ID);
      if (phase === null) return response({ error: "fixture_mismatch_or_already_run" }, 409);
      let backend: "d1" | "durableObject";
      let result: unknown;
      if (phase < PHASE_COUNT - 1) {
        backend = "d1";
        stage = "d1_metadata";
        const metadata = await engineMetadata(store);
        stage = "d1_cases";
        const tests = CASES.slice(phase * D1_PHASE_SIZE, (phase + 1) * D1_PHASE_SIZE);
        result = { ...metadata, cases: await runCases(store, tests) };
      } else {
        backend = "durableObject";
        stage = "durable_object";
        const stub = env.PROBE_OBJECT.get(env.PROBE_OBJECT.idFromName(env.PROBE_RUN_ID));
        const reply = await stub.fetch("https://probe.invalid/run", { method: "POST" });
        if (!reply.ok) throw new Error("object_probe_failed");
        result = await reply.json();
      }
      return response({
        schemaVersion: 1, environment: env.PROBE_MODE, runId: env.PROBE_RUN_ID,
        productionConformance: false, phase, phaseCount: PHASE_COUNT, backend, result,
      });
    } catch (error) {
      let reason = "unclassified";
      let current = error;
      for (let i = 0; current instanceof Error && i < 5; i++) {
        const message = current.message.toLowerCase();
        if (message.includes("too many") || message.includes("subrequest")) reason = "request_limit";
        if (message.includes("fixture_integrity")) reason = "fixture_integrity";
        if (message.includes("not authorized")) reason = "sql_authorization";
        current = current.cause;
      }
      return response({ error: "probe_execution_failed", stage, reason }, 500);
    }
  },
};

export class PermissionProbeObject {
  private storage: DurableObjectStorage;
  private env: Env;
  constructor(ctx: DurableObjectState, env: Env) {
    this.storage = ctx.storage;
    this.env = env;
  }
  async fetch(request: Request): Promise<Response> {
    if (request.method !== "POST" || new URL(request.url).pathname !== "/run") {
      return response({ error: "not_found" }, 404);
    }
    const store = objectStore(this.storage);
    const existing = await store.query(
      "SELECT name FROM sqlite_master WHERE name = 'probe_meta'",
    );
    if (existing.length) return response({ error: "already_run" }, 409);
    // Each run uses a new object name. This object-local initialization is part
    // of its own runtime capability, not a claimed independent migration role.
    await store.batch(allSetup(this.env.PROBE_RUN_ID));
    if (await claim(store, this.env.PROBE_RUN_ID) !== 0) throw new Error("object_claim_failed");
    const metadata = await engineMetadata(store);
    const cases = await runCases(store);
    const before = await snapshot(store, "probe_blocks_read");
    await this.storage.deleteAll();
    const after = await snapshot(store, "probe_blocks_read");
    cases.push({
      id: "storage.delete_all", family: "all", kind: "capability", execution: "allowed",
      before, after, forbiddenChangeObserved: !after.tableExists,
    });
    return response({ ...metadata, cases });
  }
}
