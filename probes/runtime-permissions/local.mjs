// Node is required for Miniflare's programmatic API; orchestration stays in Python.
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { Miniflare } from "miniflare";
import { allSetup, CASES, PHASE_COUNT } from "./cases.ts";

const [command, directory] = process.argv.slice(2);
if (!["setup", "local"].includes(command) || !directory) throw new Error("invalid_arguments");
const runDir = path.resolve(directory);
const root = path.resolve(".probe-runs") + path.sep;
if (!runDir.startsWith(root)) throw new Error("outside_probe_directory");
const manifest = JSON.parse(await readFile(path.join(runDir, "manifest.json"), "utf8"));
if (!/^rp-[a-f0-9]{24}$/.test(manifest.runId)) throw new Error("invalid_run_id");
const setup = allSetup(manifest.runId);
await writeFile(path.join(runDir, "fixture.sql"), setup.map((s) => s + ";").join("\n") + "\n");
if (command === "setup") process.exit(0);

const token = JSON.parse(await readFile(path.join(runDir, "secret.json"), "utf8")).PROBE_TOKEN;
let outboundCalls = 0;
const options = {
  name: "permissions-probe",
  modules: true,
  scriptPath: path.resolve(".probe-build/worker.js"),
  compatibilityDate: "2026-08-06",
  host: "127.0.0.1",
  port: 0,
  cf: false,
  logRequests: false,
  telemetry: { enabled: false },
  d1Persist: path.join(runDir, "storage", "d1"),
  durableObjectsPersist: path.join(runDir, "storage", "do"),
  bindings: { PROBE_RUN_ID: manifest.runId, PROBE_MODE: "local", PROBE_TOKEN: token },
  d1Databases: { DB: "00000000-0000-0000-0000-000000000007" },
  durableObjects: { PROBE_OBJECT: { className: "PermissionProbeObject", useSQLite: true } },
  outboundService() {
    outboundCalls++;
    throw new Error("external_network_forbidden");
  },
};
await mkdir(path.join(runDir, "storage"), { recursive: true });
const mf = new Miniflare(options);
try {
  const db = await mf.getD1Database("DB");
  for (const sql of setup) await db.prepare(sql).run();
  const headers = { Authorization: "Bearer " + token };
  const checks = [];
  async function refused(name, url, init, expected) {
    const response = await mf.dispatchFetch(url, init);
    assert.equal(response.status, expected, name);
    assert.equal((await db.prepare("SELECT executed FROM probe_meta").first()).executed, 0);
    checks.push(name);
  }
  await refused("missing_token", "http://probe.test/run", { method: "POST" }, 401);
  await refused("wrong_token", "http://probe.test/run",
    { method: "POST", headers: { Authorization: "Bearer " + "x".repeat(token.length) } }, 401);
  await refused("wrong_method", "http://probe.test/run", { headers }, 405);
  await refused("unknown_path", "http://probe.test/other", { method: "POST", headers }, 404);
  await refused("query_refused", "http://probe.test/run?sql=anything", { method: "POST", headers }, 404);
  await refused("body_refused", "http://probe.test/run",
    { method: "POST", headers, body: "anything" }, 400);
  await db.prepare("UPDATE probe_meta SET run_id = ?").bind("rp-" + "0".repeat(24)).run();
  await refused("wrong_fixture", "http://probe.test/run", { method: "POST", headers }, 409);
  await db.prepare("UPDATE probe_meta SET run_id = ?").bind(manifest.runId).run();
  const report = {
    schemaVersion: 1, environment: "local", runId: manifest.runId,
    productionConformance: false,
    d1: { sqliteVersion: null, cases: [] }, durableObject: { sqliteVersion: null, cases: [] },
  };
  for (let phase = 0; phase < PHASE_COUNT; phase++) {
    const reply = await mf.dispatchFetch("http://probe.test/run", { method: "POST", headers });
    const part = await reply.json();
    assert.equal(reply.status, 200, JSON.stringify(part));
    assert.equal(part.phase, phase);
    assert.equal(part.phaseCount, PHASE_COUNT);
    assert.equal(part.runId, manifest.runId);
    assert.equal(part.productionConformance, false);
    const backend = phase < PHASE_COUNT - 1 ? "d1" : "durableObject";
    assert.equal(part.backend, backend);
    const prior = report[backend].sqliteVersion;
    if (prior !== null) assert.equal(prior, part.result.sqliteVersion);
    report[backend].sqliteVersion = part.result.sqliteVersion;
    report[backend].sqliteVersionObservation = part.result.sqliteVersionObservation;
    report[backend].cases.push(...part.result.cases);
  }
  const replay = await mf.dispatchFetch("http://probe.test/run", { method: "POST", headers });
  assert.equal(replay.status, 409);
  checks.push("second_run_refused");
  assert.equal(outboundCalls, 0);
  report.harness = { compatibilityDate: "2026-08-06", checks, externalNetworkCalls: outboundCalls, expectedD1Cases: CASES.length };
  await writeFile(path.join(runDir, "report.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify({ environment: "local", cases: report.d1.cases.length +
    report.durableObject.cases.length, safetyChecks: checks.length, outboundCalls }));
} finally {
  await mf.dispose();
}
