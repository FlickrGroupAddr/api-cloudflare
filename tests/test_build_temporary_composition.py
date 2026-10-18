"""Exercise real offline assembly with original synthetic modules, never captures."""

from __future__ import annotations

import copy
import json
import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_temporary_composition as builder
from scripts.temporary_composition_lifecycle import (
    LifecycleJournal,
    SyntheticCompositionProvider,
    build_composition_plan,
    rehearse_composition,
)
from tests.test_temporary_composition_delta import composition_inputs

REPOSITORY = Path(__file__).resolve().parents[1]
CAPTURED = b"""
export class RetainedClass { marker() { return 'original-class'; } }
export const retainedNamed = Object.freeze({ marker: 'original-named' });
export default {
  fetch(request, env, context) {
    if (request !== globalThis.expectedRequest || env !== globalThis.expectedEnv
        || context !== globalThis.expectedContext) throw Error('ordinary_identity_changed');
    return globalThis.expectedResponse;
  },
  scheduled(event, env, context) { return [event, env, context]; },
};
"""
CANDIDATE = b"export function createWorker() { throw Error('ordinary_candidate_called'); }\n"


class BuildTemporaryCompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-original-composition-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private-evidence"
        self.fixture = self.root / "fixture"
        self.fixture.mkdir(parents=True)
        self.output = self.root / "assembled"
        self.node = Path(os.environ.get("FGA_COMPOSITION_NODE", shutil.which("node") or "node"))
        (self.fixture / "captured.mjs").write_bytes(CAPTURED)
        (self.fixture / "candidate.mjs").write_bytes(CANDIDATE)
        sources = {
            "src/worker.ts": b"export const original = true;\n",
            "migrations/0001.sql": b"CREATE TABLE original_synthetic (id TEXT);\n",
        }
        for name, raw in sources.items():
            path = self.fixture / "candidate" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        fixture_manifest = builder.canonical(
            {
                "schemaVersion": 1,
                "candidateCommit": builder.CANDIDATE,
                "candidateSourceFiles": {
                    name: builder.digest(raw) for name, raw in sources.items()
                },
                "hostedQualified": False,
            }
        )
        (self.fixture / "manifest.json").write_bytes(fixture_manifest)
        for name, value in (
            ("MODULE_SHA256", builder.digest(CAPTURED)),
            ("CANDIDATE_SHA256", builder.digest(CANDIDATE)),
            ("FIXTURE_MANIFEST_SHA256", builder.digest(fixture_manifest)),
        ):
            pin = patch.object(builder, name, value)
            pin.start()
            self.addCleanup(pin.stop)
        self.baseline, self.additions = composition_inputs()
        self.baseline["moduleSha256"] = builder.digest(CAPTURED)
        self.additions.pop("moduleSha256")
        self.additions.pop("scope")
        self.additions["receiver"].pop("moduleSha256")
        self.scope = {
            "run": self.additions["run"],
            "canary": "c" * 64,
            "startsAt": 1000,
            "expiresAt": 601000,
            "bindingKeys": {
                "syntheticDb": "QUALIFICATION_DB",
                "quotaDb": "QUALIFICATION_QUOTA",
                "receiver": "QUALIFICATION_RECEIVER",
                "capability": "QUALIFICATION_CAPABILITY",
            },
        }

    def build(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            return builder.build(
                REPOSITORY,
                self.fixture,
                self.baseline,
                self.additions,
                self.scope,
                self.output,
                self.node,
            )

    def test_real_bundle_preserves_ordinary_reference_identity_and_named_exports(self):
        original = {path: path.read_bytes() for path in self.fixture.rglob("*") if path.is_file()}
        manifest = self.build()
        pin = builder.digest((self.output / "manifest.json").read_bytes())
        self.assertEqual(builder.verify(self.output, pin), manifest)
        for path, raw in original.items():
            self.assertEqual(path.read_bytes(), raw)
        delta = json.loads((self.output / "configuration-delta.json").read_bytes())
        self.assertEqual(delta["baseline"], self.baseline)
        plan = build_composition_plan(delta, self.scope["startsAt"])
        journal = LifecycleJournal(self.root / "built-lifecycle.sqlite", plan)
        try:
            provider = SyntheticCompositionProvider(plan)
            receipt = rehearse_composition(plan, journal, provider)
            self.assertEqual(receipt["cleanup"], "confirmed_offline")
            self.assertEqual(provider.snapshot()["snapshot"], self.baseline)
        finally:
            journal.close()
        script = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const worker = await import(pathToFileURL(process.argv[1]));
assert.equal(new worker.RetainedClass().marker(), 'original-class');
assert.equal(worker.retainedNamed.marker, 'original-named');
const request = new Request('https://example.invalid/ordinary', {
  method: 'POST', body: 'original-body', headers: {Authorization: 'Bearer ordinary'},
});
const env = new Proxy({}, {get() {throw Error('qualification_env_read');},
  ownKeys() {throw Error('qualification_env_enumerated');}});
const context = Object.freeze({waitUntil() {throw Error('unexpected_context_call');}});
const response = new Response('original-response', {status: 207});
Object.assign(globalThis, {expectedRequest: request, expectedEnv: env,
  expectedContext: context, expectedResponse: response});
assert.equal(await worker.default.fetch(request, env, context), response);
const event = {};
assert.deepEqual(worker.default.scheduled(event, env, context), [event, env, context]);
"""
        result = subprocess.run(
            [str(self.node), "--input-type=module", "-e", script, str(self.output / "worker.mjs")],
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        for field in (
            "deploymentAllowed",
            "providerRestorationVerified",
            "productionStateVerified",
            "nativeQualified",
            "transportQualified",
        ):
            self.assertIs(manifest[field], False)

    def test_generated_receiver_uses_exact_quota_capability_and_observation_contract(self):
        self.build()
        script = r"""
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const receiver = await import(pathToFileURL(process.argv[1]));
const {initializeQuota, createQuotaGuard} = await import(pathToFileURL(process.argv[2]));
const raw = new DatabaseSync(':memory:');
raw.exec(readFileSync(process.argv[3], 'utf8'));
const db = {prepare(sql) {return {args: [], bind(...args) {this.args=args; return this;},
 async first() {return raw.prepare(sql).get(...this.args) ?? null;},
 async run() {return raw.prepare(sql).run(...this.args);}};}};
const run = 'a'.repeat(32), capability = 'b'.repeat(64), canary = 'c'.repeat(64);
Date.now = () => 1000;
await initializeQuota({db, run, startsAt: 1000});
const env = {QUALIFICATION_QUOTA: db, QUALIFICATION_CAPABILITY: capability};
const prefix = 'https://flickrgroupaddr.com';
const receiverPath = '/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/';
const arrival = new Request(`${prefix}${receiverPath}${run}/308`,
 {headers: {'X-FGA-Canary': canary}});
assert.equal((await receiver.default.fetch(arrival, env)).status, 204);
const report = () => new Request(`${prefix}/report/${run}`,
 {headers: {Authorization: `FGA-Qualification ${capability}`}});
const response = await receiver.default.fetch(report(), env);
assert.equal(response.status, 200);
assert.deepEqual(await response.json(), {receiverRequests: 2, arrivals: 1,
 authorizationPresent: false, canaryMatch: true});
const guard = createQuotaGuard({db, run, clock: Date.now});
const foreignRaw = new DatabaseSync(':memory:');
foreignRaw.exec(readFileSync(process.argv[3], 'utf8'));
const foreignDb = {prepare(sql) {return {args: [], bind(...args) {this.args=args; return this;},
 async first() {return foreignRaw.prepare(sql).get(...this.args) ?? null;},
 async run() {return foreignRaw.prepare(sql).run(...this.args);}};}};
Date.now = () => 2000;
await initializeQuota({db: foreignDb, run, startsAt: 2000});
assert.equal((await receiver.default.fetch(report(),
 {...env, QUALIFICATION_QUOTA: foreignDb})).status, 404);
foreignRaw.close();
Date.now = () => 1000;
assert.equal((await guard.inspect()).receiver, 2);
await guard.disable();
assert.equal((await receiver.default.fetch(report(), env)).status, 404);
raw.close();
"""
        result = subprocess.run(
            [
                str(self.node),
                "--input-type=module",
                "-e",
                script,
                str(self.output / "receiver.mjs"),
                str(REPOSITORY / "probes/fixed-origin-lifecycle/quota_receiver.mjs"),
                str(REPOSITORY / "probes/fixed-origin-lifecycle/schema.sql"),
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        receiver = json.loads((self.output / "receiver-configuration.json").read_bytes())
        self.assertEqual(receiver["target"], self.additions["receiver"]["target"])
        self.assertEqual(receiver["configuration"], self.additions["receiver"]["configuration"])
        pin = builder.digest((self.output / "manifest.json").read_bytes())
        receiver_module = self.output / "receiver.mjs"
        receiver_module.write_bytes(receiver_module.read_bytes() + b"// altered receiver\n")
        with self.assertRaisesRegex(ValueError, "packet_file_pin"):
            builder.verify(self.output, pin)

    def test_missing_fixture_or_changed_candidate_closure_refuses_before_process(self):
        for name in ("captured.mjs", "candidate/migrations/0001.sql"):
            path = self.fixture / name
            original = path.read_bytes()
            path.unlink()
            with self.subTest(missing=name), patch.object(builder.subprocess, "run") as process:
                with self.assertRaises((ValueError, OSError)):
                    self.build()
                process.assert_not_called()
            self.assertFalse(self.output.exists())
            path.write_bytes(original)
        path = self.fixture / "candidate/src/worker.ts"
        path.write_bytes(path.read_bytes() + b"// unreviewed change\n")
        with patch.object(builder.subprocess, "run") as process:
            with self.assertRaisesRegex(ValueError, "candidate_source_pin"):
                self.build()
            process.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_missing_or_unsupported_inputs_do_not_create_partial_output(self):
        for mutation in (
            lambda: self.baseline["configuration"].pop("assets"),
            lambda: self.baseline.update(moduleSha256="f" * 64),
            lambda: self.scope["bindingKeys"].update(receiver="GUESSED_RECEIVER"),
            lambda: self.scope.update(expiresAt=601001),
            lambda: self.scope.pop("canary"),
            lambda: self.additions["receiver"]["configuration"].pop("runtime"),
            lambda: self.additions.update(moduleSha256="0" * 64),
        ):
            baseline, additions, scope = copy.deepcopy((self.baseline, self.additions, self.scope))
            mutation()
            with patch.object(builder.subprocess, "run") as process:
                with self.assertRaises(ValueError):
                    self.build()
                process.assert_not_called()
            self.assertFalse(self.output.exists())
            self.baseline, self.additions, self.scope = baseline, additions, scope

    def test_receiver_relationship_or_ordinary_resource_alias_refuses_before_bundle(self):
        original = copy.deepcopy((self.baseline, self.additions))
        for scenario in ("receiver_route", "unlisted_d1_alias"):
            if scenario == "receiver_route":
                self.additions["receiver"]["configuration"]["routes"] = [
                    {"pattern": "production.invalid/*", "zone_id": "production-zone"}
                ]
            else:
                self.baseline["configuration"]["bindings"].append(
                    {
                        "name": "ORDINARY_ALIAS",
                        "type": "d1",
                        "database_id": self.additions["resources"][0]["identity"],
                    }
                )
            with (
                self.subTest(scenario=scenario),
                patch.object(builder.subprocess, "run") as process,
            ):
                with self.assertRaises(ValueError):
                    self.build()
                process.assert_not_called()
            self.assertFalse(self.output.exists())
            self.baseline, self.additions = copy.deepcopy(original)

    def test_packet_tamper_and_self_consistent_repackaging_cannot_replace_retained_pin(self):
        self.build()
        manifest_path = self.output / "manifest.json"
        pin = builder.digest(manifest_path.read_bytes())
        worker = self.output / "worker.mjs"
        worker.write_bytes(worker.read_bytes() + b"// changed worker\n")
        with self.assertRaisesRegex(ValueError, "packet_file_pin"):
            builder.verify(self.output, pin)
        modified = json.loads(manifest_path.read_bytes())
        modified["files"]["worker.mjs"] = builder.digest(worker.read_bytes())
        modified["moduleSha256"] = builder.digest(worker.read_bytes())
        manifest_path.write_bytes(builder.canonical(modified))
        with self.assertRaisesRegex(ValueError, "manifest_pin"):
            builder.verify(self.output, pin)

    def test_unreviewed_entry_source_is_rejected_before_local_bundle(self):
        read = builder._read

        def altered_entry(path):
            raw = read(path)
            return (
                raw + b"// unreviewed entry source\n" if path == REPOSITORY / builder.ENTRY else raw
            )

        with patch.object(builder, "_read", side_effect=altered_entry):
            with patch.object(builder.subprocess, "run") as process:
                with self.assertRaisesRegex(ValueError, "deployment_entrypoint_pin"):
                    self.build()
                process.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_fresh_private_destination_and_explicit_inputs_are_required(self):
        self.output.mkdir()
        sentinel = self.output / "retained"
        sentinel.write_bytes(b"preserve")
        with patch.object(builder.subprocess, "run") as process:
            with self.assertRaises(ValueError):
                self.build()
            process.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        with self.assertRaisesRegex(ValueError, "private_path_required"):
            builder.build(
                REPOSITORY,
                self.fixture,
                self.baseline,
                self.additions,
                self.scope,
                REPOSITORY / "unapproved-build",
                self.node,
            )


if __name__ == "__main__":
    unittest.main()
