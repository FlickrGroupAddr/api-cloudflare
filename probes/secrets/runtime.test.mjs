// Node is required for Miniflare's API; the hosted controller stays in Python.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { Miniflare } from "miniflare";

test("bundled Worker signs synthetic creation inside workerd with no external network", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "fga-secret-runtime-"));
  const configPath = path.join(directory, "wrangler.json");
  await writeFile(configPath, JSON.stringify({
    name: "fga-secret-local", main: path.resolve("probes/secrets/worker.ts"),
    compatibility_date: "2026-09-07", workers_dev: false,
  }));
  // The required native compiler must pass before provider bundling.
  execFileSync(process.execPath, ["node_modules/typescript/bin/tsc", "--noEmit"]);
  execFileSync(process.execPath, ["node_modules/wrangler/bin/wrangler.js", "deploy",
    "--dry-run", "--config", configPath, "--outdir", path.join(directory, "bundle")], {
    env: { ...process.env, WRANGLER_SEND_METRICS: "false", WRANGLER_WRITE_LOGS: "false",
      CI: "true" }, stdio: "pipe",
  });
  const version = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const name = `fga-proof/${"a".repeat(24)}/${version}`;
  const arn = `arn:aws:secretsmanager:us-east-2:123456789012:secret:${name}-Ab1234`;
  let calls = 0;
  const mf = new Miniflare({
    modules: true, script: await readFile(path.join(directory, "bundle/worker.js"), "utf8"),
    compatibilityDate: "2026-07-30", host: "127.0.0.1", port: 0,
    cf: false, logRequests: false, telemetry: { enabled: false },
    bindings: {
      PROOF_TOKEN: "synthetic-bearer",
      AWS_SESSION: JSON.stringify({ AccessKeyId: "synthetic-access-id",
        SecretAccessKey: "synthetic-secret", SessionToken: "synthetic-session",
        Expiration: "2099-01-01T00:00:00Z" }),
      PROOF_CONFIG: JSON.stringify({
        scope: { account: "123456789012", region: "us-east-2", runId: "a".repeat(24) },
        generations: [{ name, version }], build: "local-build", expires: Date.now() + 60_000,
      }),
    },
    async outboundService(request) {
      calls++;
      assert.equal(request.url, "https://secretsmanager.us-east-2.amazonaws.com/");
      assert.equal(request.headers.get("X-Amz-Target"), "secretsmanager.CreateSecret");
      assert.match(request.headers.get("Authorization"), /^AWS4-HMAC-SHA256 /);
      assert.deepEqual(await request.json(), { Name: name, ClientRequestToken: version,
        SecretString: JSON.stringify({ fixture: "fga-synthetic-only", generation: version }) });
      return Response.json({ ARN: arn, Name: name, VersionId: version });
    },
  });
  try {
    const preflight = await mf.dispatchFetch("http://proof.test/probe", { method: "POST",
      headers: { Authorization: "Bearer synthetic-bearer" },
      body: JSON.stringify({ action: "preflight", index: 0 }) });
    assert.equal(preflight.status, 200);
    assert.deepEqual(await preflight.json(), { build: "local-build", result: true });
    assert.equal(calls, 0);
    const reply = await mf.dispatchFetch("http://proof.test/probe", { method: "POST",
      headers: { Authorization: "Bearer synthetic-bearer" },
      body: JSON.stringify({ action: "create", index: 0 }) });
    const body = await reply.json();
    assert.equal(reply.status, 200, JSON.stringify(body));
    assert.deepEqual(body.result, { name, version, arn });
    assert.equal(calls, 1);
  } finally {
    await mf.dispose();
  }
});
