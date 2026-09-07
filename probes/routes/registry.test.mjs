import assert from "node:assert/strict";
import test from "node:test";
import worker, { safePath } from "./worker.ts";
import { ROUTES, validateRegistry } from "./registry.ts";
test("registry rejects duplicate registrations and missing probes", () => {
  assert.throws(() => validateRegistry([...ROUTES, ROUTES[0]]));
  assert.throws(() => validateRegistry([{ ...ROUTES[0], probe: "" }]));
});
test("ambiguous request targets are rejected before URL normalization", () => {
  for (const path of ["/api\\debug", "/api/%2fdebug", "/api/%252fdebug", "/api/%00", "/api/%", "/api/%ff", "/api/\tdebug"]) {
    assert.equal(safePath("https://fixture.test" + path), null, path);
  }
});
test("server paths never reach an adversarial assets binding", async () => {
  let calls = 0;
  const env = { ROUTING_PROOF: "isolated-fixture", ASSETS: { fetch() { calls++; return new Response("wrong HTML"); } } };
  for (const route of ROUTES) {
    const path = route.pathPattern.replace(/\{[^}]+\}/g, "synthetic");
    for (const method of ["GET", "HEAD", "POST", "DELETE", "OPTIONS"]) {
      await worker.fetch(new Request("https://fixture.test" + path, { method }), env);
    }
  }
  for (const path of ["/api", "/api/debug", "/api/v001/missing", "/healthz/missing", "/admin/missing"]) {
    await worker.fetch(new Request("https://fixture.test" + path), env);
  }
  assert.equal(calls, 0);
});
