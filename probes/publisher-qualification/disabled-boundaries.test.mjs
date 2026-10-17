// Offline request/consumer execution only. This is not hosted publisher qualification.
import test from "node:test";
import assert from "node:assert/strict";
import {createWorker, ROUTES} from "../../src/worker.ts";
import {consumeAlbumMaterialization} from "../../src/album_materialization_worker.ts";
import {consumeAlbumAttachment} from "../../src/album_attachment_worker.ts";
import {consumeAlbumTitle} from "../../src/album_title_worker.ts";

const handlers = [
  "album_binding_status", "album_photo_association_status", "album_create_repair_candidates",
  "album_create_repair_resolution", "album_lifecycle_read", "album_title_intent",
  "album_photo_local_removal", "album_local_removal", "album_photo_association",
  "album_binding_ensure", "album_binding_read", "upload_candidates", "publish_service_create",
  "publish_service_read", "upload_authorization", "upload_photo_binding",
  "upload_ambiguity_resolution",
];
const flags = [
  "FGA_ALBUM_CREATE_REPAIR_ENABLED", "FGA_ALBUM_TITLE_ENABLED", "FGA_ALBUM_LOCAL_REMOVAL_ENABLED",
  "FGA_ALBUM_OBLIGATIONS_ENABLED", "FGA_ALBUM_BINDINGS_ENABLED", "FGA_UPLOAD_CANDIDATES_ENABLED",
  "FGA_PUBLISH_SERVICE_ENABLED", "FGA_UPLOAD_AUTHORIZATION_ENABLED",
  "FGA_UPLOAD_PHOTO_BINDING_ENABLED", "FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED",
];
const syntheticId = "00000000-0000-4000-8000-000000000001";

function deniedDependencies() {
  const calls = {database: 0, transport: 0, clock: 0};
  const db = new Proxy({}, {get() {calls.database++; throw Error("unexpected_database_access");}});
  const transport = async () => {calls.transport++; throw Error("unexpected_transport_access");};
  const monotonicMs = () => {calls.clock++; throw Error("unexpected_clock_access");};
  return {calls, db, transport, monotonicMs};
}

test("actual Worker executes every scoped installation route with default-off refusal", async () => {
  const scoped = ROUTES.filter(route => handlers.includes(route.handler));
  assert.equal(scoped.length, 17);
  assert.deepEqual(new Set(scoped.map(route => route.handler)), new Set(handlers));
  for (const value of [undefined, "0", "false", "true", "01"]) {
    const denied = deniedDependencies();
    const env = {DB: denied.db, ...Object.fromEntries(flags.map(flag => [flag, value]))};
    const worker = createWorker(denied.transport);
    for (const route of scoped) {
      const path = route.pathPattern.replace(/\{[^}]+\}/g, syntheticId);
      const response = await worker.fetch(new Request("https://publisher.invalid" + path,
        {method: route.method}), env);
      assert.equal(response.status, 503, `${route.handler}: ${String(value)}`);
      assert.match(response.headers.get("Cache-Control"), /no-store/);
      const body = await response.json();
      assert.equal(body.error.code, "service_unavailable");
    }
    assert.deepEqual(denied.calls, {database: 0, transport: 0, clock: 0});
  }
});

test("actual background consumers refuse before storage, factory, or clock when disabled", async () => {
  for (const [consumer, flag] of [
    [consumeAlbumMaterialization, "FGA_ALBUM_MATERIALIZATION_ENABLED"],
    [consumeAlbumAttachment, "FGA_ALBUM_ATTACHMENT_ENABLED"],
    [consumeAlbumTitle, "FGA_ALBUM_TITLE_SYNC_ENABLED"],
  ]) {
    for (const value of [undefined, "0", "false", "true", "01"]) {
      const denied = deniedDependencies();
      const result = await consumer({DB: denied.db, [flag]: value}, syntheticId,
        denied.transport, {monotonicMs: denied.monotonicMs});
      assert.equal(result, "disabled");
      assert.deepEqual(denied.calls, {database: 0, transport: 0, clock: 0});
    }
  }
});

// Exercise the packaged diagnostic itself, including its synthetic network boundary.
test("packaged diagnostic executes requests and consumers, restores network, and remains NO-GO", async () => {
  const {runOfflineDiagnostic} = await import("./offline.mjs");
  const originalFetch = globalThis.fetch;
  for (let attempt = 0; attempt < 2; attempt++) {
    const receipt = await runOfflineDiagnostic();
    assert.equal(globalThis.fetch, originalFetch);
    assert.deepEqual(receipt, {
      schemaVersion: 1, status: "NO-GO", diagnostic: "passed",
      fullPublisherExecutable: false, hostedQualification: "not_executed",
      requests: 44, defaultOffConsumers: 6, providerCalls: 0, databaseCalls: 0,
    });
  }
});
