// Miniflare requires Node; provider orchestration and cleanup are Python.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { Miniflare } from "miniflare";
import { bundle } from "./lifecycle.ts";
const generations = ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "cccccccc-cccc-4ccc-8ccc-cccccccccccc"];
const runId = "rp-" + "a".repeat(24);
test("real local D1 and Secrets Store reject lifecycle races and retain durable pause", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "fga-native-secret-"));
  const configPath = path.join(directory, "wrangler.json");
  await writeFile(configPath, JSON.stringify({ name: "fga-native-secret-local",
    main: path.resolve("probes/native-secrets/worker.ts"), compatibility_date: "2026-09-11", workers_dev: false }));
  execFileSync(process.execPath, ["node_modules/typescript/bin/tsc", "--noEmit"]);
  execFileSync(process.execPath, ["node_modules/wrangler/bin/wrangler.js", "deploy", "--dry-run",
    "--config", configPath, "--outdir", path.join(directory, "bundle")], {
    env: { ...process.env, WRANGLER_WRITE_LOGS: "false", WRANGLER_SEND_METRICS: "false", CI: "true" }, stdio: "pipe" });
  const options = { modules: true, script: await readFile(path.join(directory, "bundle/worker.js"), "utf8"),
    compatibilityDate: "2026-07-30", host: "127.0.0.1", port: 0, cf: false,
    logRequests: false, telemetry: { enabled: false },
    d1Databases: { DB: "00000000-0000-0000-0000-000000000009" },
    d1Persist: path.join(directory,"d1"), secretsStorePersist: path.join(directory,"secrets"),
    secretsStoreSecrets: { GRANT: { store_id: "native-proof-store", secret_name: "native-proof-grant" } },
    bindings: { PROOF_TOKEN: "synthetic-bearer", PROOF_CONFIG: JSON.stringify({ runId, generations,
      build: "local-build", expires: Date.now()+120_000 }) },
    outboundService() { throw new Error("External network forbidden"); },
  };
  let mf = new Miniflare(options);
  async function call(action, expected=0, index=0, operation=generations[index]) {
    const response = await mf.dispatchFetch("http://proof.test/probe", { method: "POST",
      headers: { Authorization: "Bearer synthetic-bearer" },
      body: JSON.stringify({ action, expected, index, operation }) });
    const body = await response.json();
    assert.equal(body.build, "local-build");
    assert.equal(response.headers.get("Cache-Control"), "no-store");
    return { status: response.status, ...body };
  }
  try {
    const db = await mf.getD1Database("DB");
    const schema = await readFile("probes/native-secrets/schema.sql", "utf8");
    // This fixture has one CREATE statement per top-level line; preserve trigger bodies.
    for (const statement of schema.split(/(?=^CREATE )/m).filter(s => s.trim())) {
      await db.prepare(statement).run();
    }
    await db.prepare("INSERT INTO link(id,run_id,state,generation) VALUES(1,?,'linked',?)").bind(runId,generations[0]).run();
    let admin = (await mf.getSecretsStoreSecretAPI("GRANT"))();
    const secretId = await admin.create(bundle(generations[0]));
    assert.equal((await call("resolve")).result.outcome,"usable");
    const binding = (await call("binding")).result;
    assert.equal(binding.writeAttemptRejected,true);
    assert.equal(binding.managementCredentialPresent,false);
    const race = await Promise.all([call("begin",0,1),call("begin",0,2)]);
    assert.deepEqual(race.map(r=>r.status).sort(),[200,409]);
    assert.equal((await call("attempts")).result.results.length,2);
    const index = race[0].status===200 ? 1 : 2;
    assert.equal((await call("resolve")).result.outcome,"stopped");
    assert.equal((await call("disconnect",1,0)).status,409);
    await mf.dispose(); mf = new Miniflare(options);
    assert.equal((await call("state")).result.state,"paused");
    assert.equal((await call("resolve")).result.outcome,"stopped");
    admin = (await mf.getSecretsStoreSecretAPI("GRANT"))();
    await admin.update(bundle(generations[index]),secretId);
    const failedActivation = await call("activate-fail",1,index);
    assert.equal(failedActivation.status,409);
    assert.equal(failedActivation.error,"injected_audit_failure");
    assert.equal((await call("state")).result.revision,1);
    const reopenedDb = await mf.getD1Database("DB");
    assert.equal((await reopenedDb.prepare("SELECT COUNT(*) AS n FROM events").first()).n,1);
    assert.equal((await call("activate",1,index)).status,200);
    assert.equal((await call("activate",1,index)).status,409);
    assert.equal((await call("check-delete",1,0)).status,409);
    assert.equal((await call("resolve")).result.outcome,"usable");
    await admin.update(bundle(generations[0]),secretId);
    assert.equal((await call("resolve")).result.outcome,"generation_mismatch");
    await admin.update("{broken",secretId);
    assert.equal((await call("resolve")).result.outcome,"invalid_bundle");
    await admin.update(bundle(generations[index]),secretId);
    assert.equal((await call("disconnect",2,index)).status,200);
    assert.equal((await call("begin",3,0)).status,409);
    assert.equal((await call("resolve")).result.outcome,"stopped");
    assert.equal((await call("state")).result.retiring_generation,generations[index]);
    await admin.update(JSON.stringify({ fixture: "fga-native-retired", generation: generations[0] }),secretId);
    assert.equal((await call("confirm-retirement",3,index)).error,"retirement_unconfirmed");
    await admin.delete(secretId);
    assert.equal((await call("observe")).result.outcome,"unavailable");
    assert.equal((await call("confirm-retirement",3,index)).error,"retirement_unconfirmed");
    const recreated = await admin.create(JSON.stringify({ fixture: "fga-native-retired", generation: generations[index] }));
    assert.equal((await call("confirm-retirement",3,index)).status,200);
    assert.equal((await call("state")).result.state,"disconnected");
    await admin.delete(recreated);
  } finally { await mf.dispose(); }
});
