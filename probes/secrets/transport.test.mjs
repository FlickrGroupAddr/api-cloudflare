import assert from "node:assert/strict";
import test from "node:test";
import { signedTransport } from "./transport.ts";
import worker from "./worker.ts";

const credentials = {
  AccessKeyId: "synthetic-access-id", SecretAccessKey: "synthetic-secret",
  SessionToken: "synthetic-session", Expiration: "2099-01-01T00:00:00Z",
};
function request(url = "https://secretsmanager.us-east-2.amazonaws.com/") {
  return new Request(url, { method: "POST", redirect: "manual",
    signal: AbortSignal.timeout(1000),
    headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "secretsmanager.GetSecretValue" },
    body: JSON.stringify({ SecretId: "synthetic", VersionId: "fixed-version" }) });
}

test("SigV4 transport signs exact request with temporary token and does not retry", async () => {
  let calls = 0;
  const send = signedTransport(credentials, "us-east-2", async (signed) => {
    calls++;
    assert.equal(signed.redirect, "manual");
    assert.match(signed.headers.get("Authorization"), /^AWS4-HMAC-SHA256 Credential=synthetic-access-id\//);
    assert.equal(signed.headers.get("X-Amz-Security-Token"), credentials.SessionToken);
    assert.match(signed.headers.get("Authorization"), /us-east-2\/secretsmanager\/aws4_request/);
    assert.deepEqual(await signed.json(), { SecretId: "synthetic", VersionId: "fixed-version" });
    return new Response("busy", { status: 503 });
  });
  assert.equal((await send(request())).status, 503);
  assert.equal(calls, 1);
});

test("transport refuses expired credentials and endpoint substitution before sending", async () => {
  let calls = 0;
  const send = async () => { calls++; return new Response(); };
  await assert.rejects(signedTransport({ ...credentials, Expiration: "2000-01-01T00:00:00Z" }, "us-east-2", send)(request()));
  await assert.rejects(signedTransport(credentials, "us-east-2", send)(request("https://attacker.example/")));
  await assert.rejects(signedTransport({ ...credentials, SessionToken: "" }, "us-east-2", send)(request()));
  assert.equal(calls, 0);
});

test("transport errors cannot leak signing credentials", async () => {
  const send = signedTransport(credentials, "us-east-2", () => { throw new Error(credentials.SecretAccessKey); });
  await assert.rejects(send(request()), { message: "secret_probe_transport" });
});

test("Worker boundary requires private bearer, current fixture TTL and fixed request schema", async () => {
  const config = { scope: { account: "123456789012", region: "us-east-2", runId: "a".repeat(24) },
    build: "test-build", expires: Date.now() + 60_000, generations: [] };
  const env = { PROOF_TOKEN: "synthetic-token", PROOF_CONFIG: JSON.stringify(config) };
  assert.equal((await worker.fetch(new Request("https://proof.test/ready"), env)).status, 401);
  const headers = { Authorization: "Bearer synthetic-token" };
  const ready = await worker.fetch(new Request("https://proof.test/ready", { headers }), env);
  assert.equal(ready.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await ready.json(), { build: "test-build" });
  assert.equal((await worker.fetch(new Request("https://proof.test/probe", { headers, method: "POST",
    body: JSON.stringify({ action: "delete", index: 0, secretId: "production" }) }), env)).status, 400);
  const expired = { ...env, PROOF_CONFIG: JSON.stringify({ ...config, expires: 0 }) };
  assert.equal((await worker.fetch(new Request("https://proof.test/ready", { headers }), expired)).status, 410);
});

test("transport refuses redirect responses without following their destination", async () => {
  let calls = 0;
  const send = signedTransport(credentials, "us-east-2", async (signed) => {
    calls++;
    assert.equal(signed.redirect, "manual");
    return new Response(null, { status: 307, headers: { Location: "https://attacker.example/" } });
  });
  await assert.rejects(send(request()), { message: "secret_probe_transport" });
  assert.equal(calls, 1);
});
