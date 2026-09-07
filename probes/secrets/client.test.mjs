import assert from "node:assert/strict";
import test from "node:test";
import { SyntheticSecretsClient } from "./client.ts";

const scope = { account: "123456789012", region: "us-east-2", runId: "0123456789abcdef01234567" };
const version = "11111111-1111-4111-8111-111111111111";
const name = `fga-proof/${scope.runId}/${version}`;
const reference = {
  name, version,
  arn: `arn:aws:secretsmanager:us-east-2:123456789012:secret:${name}-Ab12Cd`,
};
const fixture = JSON.stringify({ fixture: "fga-synthetic-only", generation: version });
const json = (value, status = 200) => Response.json(value, { status });
const missing = () => json({ __type: "ResourceNotFoundException", Message: "private provider text" }, 400);
const describe = () => json({ ARN: reference.arn, Name: name, VersionIdsToStages: { [version]: ["AWSCURRENT"] } });
const value = () => json({ ARN: reference.arn, Name: name, VersionId: version, SecretString: fixture });

function scripted(...steps) {
  const calls = [];
  const client = new SyntheticSecretsClient(scope, async (request) => {
    const body = await request.json();
    calls.push({ request, body });
    assert.ok(steps.length, "unexpected provider request");
    return await steps.shift()(body, request);
  });
  return { client, calls, finished: () => assert.equal(steps.length, 0) };
}

test("exact read supplies full ARN and VersionId and exposes no fixture payload", async () => {
  const run = scripted((body, request) => {
    assert.deepEqual(body, { SecretId: reference.arn, VersionId: version });
    assert.equal(request.url, "https://secretsmanager.us-east-2.amazonaws.com/");
    assert.equal(request.method, "POST");
    assert.equal(request.redirect, "error");
    assert.equal(request.headers.get("X-Amz-Target"), "secretsmanager.GetSecretValue");
    assert.equal(request.headers.get("Content-Type"), "application/x-amz-json-1.1");
    return value();
  });
  assert.equal(await run.client.read(reference), undefined);
  run.finished();
});

test("invalid selectors and cross-scope references are rejected before transport", async () => {
  const run = scripted();
  for (const change of [
    { version: undefined }, { version: "AWSCURRENT" }, { version: "latest" },
    { arn: name }, { arn: reference.arn.replace("123456789012", "999999999999") },
    { arn: reference.arn.replace("us-east-2", "us-west-2") },
    { arn: reference.arn + "/extra" }, { name: "production/flickr" },
    { name: name.replace(scope.runId, "aaaaaaaaaaaaaaaaaaaaaaaa") },
  ]) {
    for (const method of ["read", "requestDeletion", "observeAbsence"]) {
      await assert.rejects(run.client[method]({ ...reference, ...change }), /secret_probe_invalid_input/);
    }
  }
  assert.equal(run.calls.length, 0);
});

test("scope rejects endpoint injection and is copied before caller mutation", () => {
  for (const change of [
    { region: "us-east-2.attacker.test/" }, { account: "*" },
    { runId: "../../production" }, { region: "cn-north-1" },
  ]) assert.throws(() => new SyntheticSecretsClient({ ...scope, ...change }, () => {}));
  const mutable = { ...scope };
  const client = new SyntheticSecretsClient(mutable, () => {});
  mutable.account = "999999999999";
  assert.equal(client.scope.account, scope.account);
  assert.ok(Object.isFrozen(client.scope));
});

test("create sends only a synthetic payload and stable caller-retained idempotency token", async () => {
  const run = scripted((body, request) => {
    assert.equal(request.headers.get("X-Amz-Target"), "secretsmanager.CreateSecret");
    assert.deepEqual(body, { Name: name, ClientRequestToken: version, SecretString: fixture });
    return json({ ARN: reference.arn, Name: name, VersionId: version });
  });
  assert.deepEqual(await run.client.create({ name, version }), reference);
  const first = run.client.generation();
  const second = run.client.generation();
  assert.notEqual(first.version, second.version);
  assert.equal(first.name, `fga-proof/${scope.runId}/${first.version}`);
  run.finished();
});

test("wrong response identity, version and secret payload fail closed", async () => {
  for (const change of [
    { ARN: reference.arn + "other" }, { Name: "other" }, { VersionId: "AWSCURRENT" },
    { SecretString: "real-or-wrong-secret" }, { SecretBinary: "also-a-value" },
  ]) {
    const run = scripted(() => json({ ARN: reference.arn, Name: name, VersionId: version,
      SecretString: fixture, ...change }));
    await assert.rejects(run.client.read(reference), /secret_probe_protocol/);
  }
  const run = scripted(() => json({ ARN: reference.arn.replace("123456789012", "999999999999"),
    Name: name, VersionId: version }));
  await assert.rejects(run.client.create({ name, version }), /secret_probe_protocol/);
});

test("lost create response is reconciled without repeating the mutation", async () => {
  const run = scripted(
    () => { throw new Error("lost response containing PRIVATE_ACCESS_KEY"); },
    () => missing(), // eventual consistency; this does not authorize abandonment
    () => describe(),
    () => value(),
  );
  await assert.rejects(run.client.create({ name, version }), { message: "secret_probe_transport" });
  assert.equal(await run.client.recover({ name, version }), null);
  assert.deepEqual(await run.client.recover({ name, version }), reference);
  assert.deepEqual(run.calls.map(({ request }) => request.headers.get("X-Amz-Target")), [
    "secretsmanager.CreateSecret", "secretsmanager.DescribeSecret",
    "secretsmanager.DescribeSecret", "secretsmanager.GetSecretValue",
  ]);
  run.finished();
});

test("recovery rejects a same-name object without the retained version", async () => {
  const run = scripted(() => json({ ARN: reference.arn, Name: name, VersionIdsToStages: {} }));
  await assert.rejects(run.client.recover({ name, version }), /secret_probe_protocol/);
  assert.equal(run.calls.length, 1);
});

test("delete acknowledgement and scheduled deletion are not confirmed absence", async () => {
  const run = scripted((body) => {
    assert.deepEqual(body, { SecretId: reference.arn, ForceDeleteWithoutRecovery: true });
    return json({ ARN: reference.arn, Name: name, DeletionDate: 1 });
  }, () => json({ ARN: reference.arn, Name: name, DeletedDate: 1 }));
  assert.equal(await run.client.requestDeletion(reference), undefined);
  assert.equal(await run.client.observeAbsence(reference), false);
  run.finished();
});

test("absence requires not-found from both metadata and exact-version read", async () => {
  const run = scripted(() => missing(), () => value(), () => missing(), () => missing());
  assert.equal(await run.client.observeAbsence(reference), false);
  assert.equal(await run.client.observeAbsence(reference), true);
  assert.deepEqual(run.calls.at(-1).body, { SecretId: reference.arn, VersionId: version });
  run.finished();
});

test("denial, expiry, throttling and arbitrary error text never prove deletion", async () => {
  for (const type of ["AccessDeniedException", "ExpiredTokenException", "ThrottlingException",
    "InvalidRequestException", "ResourceNotFoundException: private text"]) {
    const run = scripted(() => missing(), () => json({ __type: type, Message: "PRIVATE_SECRET" }, 400));
    await assert.rejects(run.client.observeAbsence(reference), { message: "secret_probe_provider" });
    run.finished();
  }
  const run = scripted(() => json({ __type: "ResourceNotFoundException" }, 500));
  await assert.rejects(run.client.observeAbsence(reference), /secret_probe_provider/);
});

test("ordinary reads never treat not-found as success and never retry a fallback", async () => {
  const run = scripted(() => missing());
  await assert.rejects(run.client.read(reference), /secret_probe_provider/);
  assert.equal(run.calls.length, 1);
});

test("transport, oversized and malformed replies expose only fixed error categories", async () => {
  for (const reply of [
    () => { throw new Error("PRIVATE_CREDENTIAL_IN_EXCEPTION"); },
    () => new Response("PRIVATE_CREDENTIAL_IN_HTML", { status: 502 }),
    () => new Response("PRIVATE_CREDENTIAL".repeat(2000)),
    () => json(null), () => json([]),
    () => json({ __type: "PrivateProviderError", Message: "PRIVATE_CREDENTIAL" }, 403),
  ]) {
    const run = scripted(reply);
    await assert.rejects(run.client.read(reference), (error) => {
      assert.match(error.message, /^secret_probe_(transport|protocol|provider)$/);
      assert.equal(error.cause, undefined);
      assert.doesNotMatch(error.stack, /PRIVATE_CREDENTIAL/);
      return true;
    });
    run.finished();
  }
});
