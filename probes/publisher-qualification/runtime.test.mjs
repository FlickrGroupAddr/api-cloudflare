// Local workerd/D1 proof of the finite synthetic candidate; never hosted qualification.
import test from "node:test";
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {mkdtemp, readFile, writeFile, rm} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {Miniflare} from "miniflare";

const gate = "a".repeat(64);
const artifact = "b".repeat(64);
const run = "c".repeat(64);
const resource = "11111111-1111-4111-8111-111111111111";
const phases = ["seed", "http", "materialize", "attach", "title", "remove", "finish"];
const headers = {
  "X-Probe-Access": gate, "X-Probe-Artifact": artifact,
  "X-Probe-Resource": resource, "X-Probe-Run": run,
};
let directory, bundled, migrations;
let outbound = 0;

test.before(async () => {
  directory = await mkdtemp(path.join(os.tmpdir(), "fga-publisher-local-"));
  const suppliedBundle = process.env.FGA_PUBLISHER_QUAL_BUNDLE;
  if (suppliedBundle) {
    bundled = await readFile(path.resolve(suppliedBundle), "utf8");
  } else {
  const config = path.join(directory, "wrangler.json");
  await writeFile(config, JSON.stringify({
    name: "publisher-offline-local", main: path.resolve("probes/publisher-qualification/worker.ts"),
    compatibility_date: "2026-10-16", compatibility_flags: ["nodejs_compat"],
    workers_dev: false, preview_urls: false,
  }));
  execFileSync(process.execPath, ["node_modules/wrangler/bin/wrangler.js", "deploy", "--dry-run",
    "--config", config, "--outdir", path.join(directory, "bundle")], {
    env: {...process.env, WRANGLER_WRITE_LOGS: "false", WRANGLER_SEND_METRICS: "false", CI: "true"},
    stdio: "pipe",
  });
  bundled = await readFile(path.join(directory, "bundle/worker.js"), "utf8");
  }
  const migrationProgram = `import json,sqlite3,sys
from pathlib import Path
assert sys.version_info[:3] == (3,14,7), 'Pinned Python 3.14.7 required'
def statements(source):
    result,pending=[],''
    for line in source.splitlines(keepends=True):
        pending+=line
        if sqlite3.complete_statement(pending):
            result.append(pending.strip());pending=''
    if pending.strip(): raise ValueError('Incomplete migration')
    return result
print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))`;
  const interpreter = process.env.FGA_QUALIFICATION_PYTHON;
  migrations = JSON.parse(execFileSync(interpreter || "uv", [
    ...(interpreter ? [] : ["run", "--frozen", "--offline", "--no-sync", "python"]), "-c", migrationProgram,
  ], {encoding: "utf8"}));
  assert.equal(migrations.length, 26);
});
test.after(async () => {
  if (directory) {
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    assert(path.basename(directory).startsWith("fga-publisher-local-"));
    await rm(directory, {recursive: true, force: true});
  }
});

async function fixture(t, overrides = {}, options = {}) {
  const mf = new Miniflare({
    modules: true, script: bundled, compatibilityDate: "2026-07-30",
    compatibilityFlags: ["nodejs_compat"], cf: false, telemetry: {enabled: false},
    d1Databases: ["DB"], d1Persist: options.persist, bindings: {
      PROBE_ENABLED: "1", PROBE_SCOPE: "publisher-disposable-v1", PROBE_ACCESS_TOKEN: gate,
      PROBE_ARTIFACT_SHA2_256: artifact, PROBE_RUN_ID: run, PROBE_RESOURCE_ID: resource,
      PROBE_EXPIRES_AT: new Date(Date.now() + 15 * 60_000).toISOString(), ...overrides,
    },
    outboundService() {outbound++; throw Error("real_external_access_forbidden");},
  });
  let disposed = false;
  const dispose = async () => {if (!disposed) {disposed = true; await mf.dispose();}};
  t.after(dispose);
  const db = await mf.getD1Database("DB");
  if (options.initialize !== false) {
    for (const statements of migrations) await db.batch(statements.map(sql => db.prepare(sql)));
  }
  return {db, mf, dispose};
}
async function noProbeRows(db) {
  assert.deepEqual((await db.prepare("SELECT name FROM sqlite_schema WHERE name LIKE 'publisher_probe_%'").all()).results, []);
}

test("actual candidate rejects unauthenticated/malformed requests before D1 control creation", async t => {
  const {mf, db} = await fixture(t);
  for (const [requestHeaders, method, suffix, body] of [
    [{}, "POST", "seed"], [{...headers, "X-Probe-Access": "wrong"}, "POST", "seed"],
    [{...headers, "X-Probe-Artifact": "d".repeat(64)}, "POST", "seed"],
    [{...headers, "X-Probe-Resource": "22222222-2222-4222-8222-222222222222"}, "POST", "seed"],
    [{...headers, "X-Probe-Run": "d".repeat(64)}, "POST", "seed"],
    [{...headers, "X-Probe-Scenario": "create_lost"}, "POST", "seed"],
    [headers, "GET", "seed"], [headers, "POST", "seed?extra=1"],
    [headers, "POST", "unsupported"], [headers, "POST", "seed", "synthetic-body"],
  ]) {
    const response = await mf.dispatchFetch("https://publisher.invalid/__publisher/" + suffix,
      {method, headers: requestHeaders, ...(body === undefined ? {} : {body})});
    assert.equal(response.status, 404);
    assert.match(response.headers.get("Cache-Control"), /no-store/);
    await noProbeRows(db);
  }
  assert.equal(outbound, 0);
});

test("actual candidate rejects disabled, wrong scope, expired and unbounded expiry before D1", async t => {
  for (const overrides of [
    {PROBE_ENABLED: "0"}, {PROBE_SCOPE: "production"}, {PROBE_SCENARIO: "unbounded"},
    {PROBE_EXPIRES_AT: new Date(Date.now() - 60_000).toISOString()},
    {PROBE_EXPIRES_AT: new Date(Date.now() + 31 * 60_000).toISOString()},
  ]) {
    await t.test(JSON.stringify(Object.keys(overrides)), async sub => {
      const {mf, db} = await fixture(sub, overrides);
      const response = await mf.dispatchFetch("https://publisher.invalid/__publisher/seed",
        {method: "POST", headers});
      assert.equal(response.status, 404);
      await noProbeRows(db);
    });
  }
  assert.equal(outbound, 0);
});

test("actual candidate runs finite synthetic handler and consumer phases on current local D1", async t => {
  const {mf, db} = await fixture(t);
  const receipts = [];
  for (const phase of phases) {
    const response = await mf.dispatchFetch("https://publisher.invalid/__publisher/" + phase,
      {method: "POST", headers});
    const body = await response.text();
        if (response.status !== 200) {
      const states = (await db.prepare("SELECT state,count(*) n FROM album_photo_obligations GROUP BY state").all()).results;
      const bindings = (await db.prepare("SELECT state,flickr_photoset_id FROM album_bindings").all()).results;
      assert.fail(`${phase}:${body};syntheticStates=${JSON.stringify(states)};syntheticBindings=${JSON.stringify(bindings)}`);
    }
    const receipt = JSON.parse(body);
    assert.equal(response.status, 200, JSON.stringify(receipt));
    assert.equal(receipt.schemaVersion, 1);
    assert.equal(receipt.phase, phase);
    assert.equal(receipt.status, "NO-GO");
    assert.equal(receipt.productionSchedulerQualified, false);
        const outcomes = {
      seed: "synthetic_seeded", http: "actual_handler_admission", materialize: "materialized",
      attach: "membership_verified", title: "synced", remove: "local_removed_without_upstream",
      finish: "finite_synthetic_sequence_complete",
    };
    assert.equal(receipt.outcome, outcomes[phase]);
    if (["materialize", "attach", "title"].includes(phase)) {
      assert.equal(receipt.syntheticPosts, 1);
      assert(receipt.providerCalls > 0 && receipt.providerCalls <= 16);
    }
    if (["remove", "finish"].includes(phase)) assert.equal(receipt.providerCalls, 0);
    if (phase === "http") {
      assert.equal(receipt.providerCalls, 3);
      assert.equal(receipt.syntheticPosts, 0);
      assert.equal(receipt.uploadProofs, 2);
      assert.equal(receipt.albumRequests, 3);
    }
    receipts.push(receipt);
  }
  const replay = await mf.dispatchFetch("https://publisher.invalid/__publisher/finish",
    {method: "POST", headers});
  assert.equal(replay.status, 409);
  assert.equal(outbound, 0);
  assert.equal(receipts.length, 7);
  const rate = await db.prepare("SELECT reserved_slots FROM flickr_rate_window WHERE singleton=1").first();
  assert.equal(rate.reserved_slots, receipts.reduce((sum, receipt) => sum + (receipt.providerCalls || 0), 0));
  assert.deepEqual((await db.prepare("PRAGMA foreign_key_check").all()).results, []);
});

async function phase(mf, name, scenario) {
  return mf.dispatchFetch("https://publisher.invalid/__publisher/" + name, {
    method: "POST", headers: {...headers, ...(scenario ? {"X-Probe-Scenario": scenario} : {})},
  });
}

test("durable phase order and duplicate reservation prevent repeated synthetic seed", async t => {
  const {mf, db} = await fixture(t);
  assert.equal((await phase(mf, "http")).status, 409);
  assert.equal((await db.prepare("SELECT count(*) n FROM fga_users").first()).n, 0);
  const duplicate = await Promise.all([phase(mf, "seed"), phase(mf, "seed")]);
  assert.deepEqual(duplicate.map(result => result.status).sort(), [200, 409]);
  assert.equal((await db.prepare("SELECT count(*) n FROM fga_users").first()).n, 1);
  const row = await db.prepare("SELECT cursor,busy,failed FROM publisher_probe_control").first();
  assert.deepEqual(row, {cursor: 1, busy: 0, failed: 0});
  assert.equal(outbound, 0);
});

test("actual D1 failure is durable and terminal, and preexisting owner data is preserved", async t => {
  const {mf, db} = await fixture(t);
  await db.prepare("INSERT INTO fga_users VALUES('synthetic-preexisting-owner')").run();
  assert.equal((await phase(mf, "seed")).status, 500);
  const row = await db.prepare("SELECT cursor,busy,failed FROM publisher_probe_control").first();
  assert.deepEqual(row, {cursor: 0, busy: 1, failed: 1});
  assert.equal((await phase(mf, "seed")).status, 409);
  assert.deepEqual((await db.prepare("SELECT user_id FROM fga_users").all()).results,
    [{user_id: "synthetic-preexisting-owner"}]);
  assert.equal(outbound, 0);
});

test("phase state and busy fence survive actual local isolate restart", async t => {
  const expires = new Date(Date.now() + 15 * 60_000).toISOString();
  const persist = path.join(directory, "restart-d1");
  const original = await fixture(t, {PROBE_EXPIRES_AT: expires}, {persist});
  assert.equal((await phase(original.mf, "seed")).status, 200);
  await original.dispose();
  const restarted = await fixture(t, {PROBE_EXPIRES_AT: expires}, {persist, initialize: false});
  assert.equal((await phase(restarted.mf, "seed")).status, 409);
  assert.equal((await phase(restarted.mf, "http")).status, 200);
  await restarted.db.prepare("UPDATE publisher_probe_control SET busy=1 WHERE id=1").run();
  await restarted.dispose();
  const busy = await fixture(t, {PROBE_EXPIRES_AT: expires}, {persist, initialize: false});
  assert.equal((await phase(busy.mf, "materialize")).status, 409);
  const row = await busy.db.prepare("SELECT cursor,busy,failed FROM publisher_probe_control").first();
  assert.deepEqual(row, {cursor: 2, busy: 1, failed: 0});
  assert.equal(outbound, 0);
});

test("synthetic ownership drift after seed fails the next phase before handler admission", async t => {
  const {mf, db} = await fixture(t);
  assert.equal((await phase(mf, "seed")).status, 200);
  await db.prepare("INSERT INTO fga_users VALUES('synthetic-drift-owner')").run();
  assert.equal((await phase(mf, "http")).status, 500);
  assert.equal((await phase(mf, "http")).status, 409);
  assert.equal((await db.prepare("SELECT count(*) n FROM publish_service_identities").first()).n, 0);
  const row = await db.prepare("SELECT cursor,busy,failed FROM publisher_probe_control").first();
  assert.deepEqual(row, {cursor: 1, busy: 1, failed: 1});
  assert.equal(outbound, 0);
});

test("shared durable fault and global rate gates prevent every synthetic provider handoff", async t => {
  for (const target of ["materialize", "attach", "title"]) {
  for (const kind of ["disabled", "revision_drift", "rate_exhausted"]) {
    await t.test(`${target}:${kind}`, async sub => {
      const {mf, db} = await fixture(sub);
      for (const prior of phases.slice(0, phases.indexOf(target))) {
        assert.equal((await phase(mf, prior)).status, 200);
      }
      if (kind === "disabled") {
        await db.prepare("UPDATE flickr_write_gates SET enabled=0 WHERE scope='deployment'").run();
      } else if (kind === "revision_drift") {
        await db.prepare("UPDATE flickr_write_gates SET revision=2 WHERE scope='deployment'").run();
      } else {
        await db.prepare("UPDATE flickr_rate_window SET reserved_slots=capacity WHERE singleton=1").run();
      }
      const response = await phase(mf, target);
      assert.equal(response.status, 500);
      const receipt = await response.json();
      assert.equal(receipt.providerCalls, 0);
      assert.equal(receipt.syntheticPosts, 0);
      assert.equal((await db.prepare("SELECT failed FROM publisher_probe_control").first()).failed, 1);
      assert.equal((await phase(mf, target)).status, 409);
    });
  }
  }
  assert.equal(outbound, 0);
});

test("forced cancellation checkpoint seam blocks later D1 admission and synthetic handoff", async t => {
  const {mf, db} = await fixture(t);
  assert.equal((await phase(mf, "seed")).status, 200);
  const {runPhase} = await import("./worker.ts");
  const counters = {providerCalls: 0, syntheticPosts: 0};
  let checkpoints = 0;
  await assert.rejects(runPhase(db, "http", () => {
    if (++checkpoints >= 5) throw Error("synthetic_action_time_revoked");
  }, counters), /synthetic_action_time_revoked/);
  assert.equal(checkpoints, 5);
  assert.equal((await db.prepare("SELECT count(*) n FROM publish_service_identities").first()).n, 0);
  assert.deepEqual(counters, {providerCalls: 0, syntheticPosts: 0});
  assert.equal(outbound, 0);
});

test("closed lost-response scenarios use fresh proof and retain exactly one marked POST", async t => {
  for (const scenario of ["create_lost", "attachment_lost", "title_lost"]) {
    await t.test(scenario, async sub => {
      const {mf, db} = await fixture(sub, {PROBE_SCENARIO: scenario});
      const receipts = new Map();
      for (const name of phases) {
        const response = await phase(mf, name, scenario);
        const body = await response.text();
        assert.equal(response.status, 200, `${scenario}:${name}:${body}`);
        const receipt = JSON.parse(body);
        assert.equal(receipt.phase, name);
        assert.equal(receipt.scenario, scenario);
        assert.equal(receipt.status, "NO-GO");
        assert.equal(receipt.productionSchedulerQualified, false);
        receipts.set(name, receipt);
      }
      const affected = receipts.get(scenario === "create_lost" ? "materialize" :
        scenario === "attachment_lost" ? "attach" : "title");
      assert.equal(affected.syntheticPosts, 1);
      if (scenario === "create_lost") {
        assert.equal(affected.outcome, "create_reconciled_no_replay");
        assert.equal(affected.createReplayOutcome, "no_work");
        assert.equal(affected.repairStatus, "materialized");
        assert(affected.repairRequests > 0 && affected.repairRequests <= 16);
        assert.deepEqual((await db.prepare("SELECT state,dispatch_count FROM album_materialization_attempts").all()).results,
          [{state: "create_outcome_unknown", dispatch_count: 1}]);
        assert.equal((await db.prepare("SELECT count(*) n FROM album_create_repair_receipts").first()).n, 1);
      } else {
        assert.equal(affected.lostReplyRecovered, true);
        assert(affected.reconciliationReads > 0 && affected.reconciliationReads <= 16);
        assert.equal(affected.outcome, scenario === "attachment_lost" ? "membership_verified" : "synced");
      }
      for (const table of ["album_materialization_attempts", "album_attachment_attempts", "album_title_attempts"]) {
        const row = await db.prepare(`SELECT count(*) n,sum(dispatch_count) dispatched FROM ${table}`).first();
        assert.deepEqual(row, {n: 1, dispatched: 1});
      }
      assert.equal(receipts.get("finish").outcome, "finite_synthetic_sequence_complete");
      const rate = await db.prepare("SELECT reserved_slots FROM flickr_rate_window WHERE singleton=1").first();
      assert.equal(rate.reserved_slots, [...receipts.values()].reduce((sum, receipt) => sum + (receipt.providerCalls || 0), 0));
      assert.equal((await phase(mf, "finish", scenario)).status, 409);
      assert.deepEqual((await db.prepare("PRAGMA foreign_key_check").all()).results, []);
    });
  }
  assert.equal(outbound, 0);
});
