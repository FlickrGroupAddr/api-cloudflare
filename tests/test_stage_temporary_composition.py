"""Synthetic staging and receipt-binding regressions; no provider or private inputs."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_temporary_composition as builder
from scripts import stage_temporary_composition as staged
from tests.test_temporary_composition_delta import composition_inputs

REPOSITORY = Path(__file__).resolve().parents[1]
CAPTURED = (
    b"export const retained = 'synthetic'; "
    b"export default {fetch() {return new Response('retained');}};\n"
)
CANDIDATE = b"export function createWorker() {throw Error('candidate_must_not_run');}\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class StageTemporaryCompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-staged-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private-evidence"
        self.fixture = self.root / "fixture"
        self.fixture.mkdir(parents=True)
        self.output = self.root / "stage"
        self.final = self.root / "final"
        self.node = Path(os.environ.get("FGA_COMPOSITION_NODE", shutil.which("node") or "node"))
        (self.fixture / "captured.mjs").write_bytes(CAPTURED)
        (self.fixture / "candidate.mjs").write_bytes(CANDIDATE)
        sources = {
            "src/worker.ts": b"export const synthetic = true;\n",
            "migrations/0001.sql": b"CREATE TABLE synthetic (id TEXT);\n",
        }
        for name, raw in sources.items():
            target = self.fixture / "candidate" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        manifest = builder.canonical(
            {
                "schemaVersion": 1,
                "candidateCommit": builder.CANDIDATE,
                "candidateSourceFiles": {name: sha(raw) for name, raw in sources.items()},
                "hostedQualified": False,
            }
        )
        (self.fixture / "manifest.json").write_bytes(manifest)
        for name, value in (
            ("MODULE_SHA256", sha(CAPTURED)),
            ("CANDIDATE_SHA256", sha(CANDIDATE)),
            ("FIXTURE_MANIFEST_SHA256", sha(manifest)),
        ):
            pin = patch.object(builder, name, value)
            pin.start()
            self.addCleanup(pin.stop)
        self.baseline, self.additions = composition_inputs()
        self.baseline["moduleSha256"] = sha(CAPTURED)
        self.scope = self.additions.pop("scope")
        self.additions.pop("temporaryVersion")
        self.additions.pop("moduleSha256")
        self.additions["receiver"].pop("moduleSha256")

    def stage(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network_forbidden")):
            return staged.stage(REPOSITORY, self.fixture, self.scope, self.output, self.node)

    def stage_pin(self):
        return sha((self.output / "manifest.json").read_bytes())

    def test_real_stage_requires_no_returned_identity_and_keeps_exact_fixture(self):
        retained = {p: p.read_bytes() for p in self.fixture.rglob("*") if p.is_file()}
        manifest = self.stage()
        self.assertEqual(staged.verify_stage(self.output, self.stage_pin()), manifest)
        for path, raw in retained.items():
            self.assertEqual(path.read_bytes(), raw)
        for name in ("worker.mjs", "receiver.mjs"):
            raw = (self.output / name).read_bytes()
            self.assertGreater(len(raw), 100)
            self.assertNotIn(b"temporary-version", raw)
            self.assertNotIn(b"synthetic-application-db", raw)
        self.assertFalse((self.output / "configuration-delta.json").exists())
        self.assertNotIn("temporaryVersion", json.dumps(manifest))

    def test_stage_tamper_extra_file_and_repackaging_refuse_retained_pin(self):
        self.stage()
        pin = self.stage_pin()
        extra = self.output / "unexpected.json"
        extra.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            staged.verify_stage(self.output, pin)
        extra.unlink()
        module = self.output / "worker.mjs"
        module.write_bytes(module.read_bytes() + b"// changed\n")
        with self.assertRaises(ValueError):
            staged.verify_stage(self.output, pin)
        manifest_path = self.output / "manifest.json"
        value = json.loads(manifest_path.read_bytes())
        value["files"]["worker.mjs"] = sha(module.read_bytes())
        value["moduleSha256"] = sha(module.read_bytes())
        manifest_path.write_bytes(builder.canonical(value))
        with self.assertRaises(ValueError):
            staged.verify_stage(self.output, pin)

    def test_stage_missing_fixture_and_source_drift_refuse_before_bundle(self):
        candidate = self.fixture / "candidate/src/worker.ts"
        candidate.write_bytes(candidate.read_bytes() + b"// unreviewed\n")
        with patch.object(builder.subprocess, "run") as process:
            with self.assertRaises(ValueError):
                self.stage()
            process.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_stage_scope_must_be_exact_and_output_exclusive(self):
        original = copy.deepcopy(self.scope)
        for change in (
            lambda s: s.update(temporaryVersion="invented"),
            lambda s: s.update(expiresAt=s["expiresAt"] + 1),
            lambda s: s.update(startsAt=True),
            lambda s: s["bindingKeys"].update(receiver=s["bindingKeys"]["quotaDb"]),
            lambda s: s.pop("canary"),
        ):
            self.scope = copy.deepcopy(original)
            change(self.scope)
            with patch.object(builder.subprocess, "run") as process:
                with self.assertRaises(ValueError):
                    self.stage()
                process.assert_not_called()
            self.assertFalse(self.output.exists())
        self.scope = original
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_bytes(b"preserve")
        with patch.object(builder.subprocess, "run") as process:
            with self.assertRaises(ValueError):
                self.stage()
            process.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_stage_rejects_changed_reviewed_entry_before_any_bundle(self):
        read = builder._read

        def altered(path):
            raw = read(path)
            return raw + b"// drift\n" if path == REPOSITORY / builder.ENTRY else raw

        with patch.object(builder, "_read", side_effect=altered):
            with patch.object(builder.subprocess, "run") as process:
                with self.assertRaises(ValueError):
                    self.stage()
                process.assert_not_called()
        self.assertFalse(self.output.exists())

    def evidence(self):
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        self.additions["temporaryVersion"] = "returned-version-0168"
        complete = copy.deepcopy(self.additions)
        complete.update(scope=copy.deepcopy(self.scope), moduleSha256=manifest["moduleSha256"])
        complete["receiver"]["moduleSha256"] = manifest["receiverModuleSha256"]
        delta = staged.build_delta(self.baseline, complete)
        digest = staged.object_digest
        evidence = {
            "schemaVersion": 1,
            "kind": "supplied_offline_composition_evidence",
            "stageManifestSha256": self.stage_pin(),
            "baseline": {
                "baselineSha256": digest(self.baseline),
                "productionStateSha256": digest(self.baseline["productionState"]),
                "captureReceiptSha256": "1" * 64,
                "consistencyReceiptSha256": "2" * 64,
                "pausedGatesReceiptSha256": "3" * 64,
                "writerReceiptSha256": "4" * 64,
            },
            "resources": [
                {
                    "resource": copy.deepcopy(resource),
                    "creationReceiptSha256": "5" * 64,
                    "initializationReceiptSha256": "6" * 64,
                    "cleanupAuthoritySha256": "7" * 64,
                }
                for resource in self.additions["resources"]
            ],
            "receiver": {
                "target": copy.deepcopy(self.additions["receiver"]["target"]),
                "run": self.additions["run"],
                "moduleSha256": manifest["receiverModuleSha256"],
                "configurationSha256": digest(self.additions["receiver"]["configuration"]),
                "versionId": "returned-receiver-version",
                "deploymentReceiptSha256": "8" * 64,
                "readbackReceiptSha256": "9" * 64,
            },
        }
        for role, receipt in (("upload", "a" * 64), ("readback", "b" * 64)):
            evidence[role] = {
                "operationId": "synthetic-" + role,
                "status": "acknowledged",
                "target": copy.deepcopy(self.baseline["target"]),
                "run": self.additions["run"],
                "versionId": self.additions["temporaryVersion"],
                "moduleSha256": manifest["moduleSha256"],
                "configurationSha256": digest(delta["temporary"]["configuration"]),
                "stageManifestSha256": self.stage_pin(),
                "receiptSha256": receipt,
            }
        return evidence

    def finalize(self, evidence, pin=None, output=None):
        with patch.object(socket, "socket", side_effect=AssertionError("network_forbidden")):
            return staged.finalize(
                REPOSITORY,
                self.output,
                self.stage_pin(),
                self.baseline,
                self.additions,
                evidence,
                staged.object_digest(evidence) if pin is None else pin,
                self.final if output is None else output,
            )

    def test_returned_id_binding_copies_every_approved_byte_without_rebuild(self):
        self.stage()
        evidence = self.evidence()
        before = {
            p.relative_to(self.output): p.read_bytes()
            for p in self.output.rglob("*")
            if p.is_file()
        }
        with patch.object(staged.subprocess, "run") as process:
            manifest = self.finalize(evidence)
            process.assert_not_called()
        for name, raw in before.items():
            target = "stage-manifest.json" if name == Path("manifest.json") else name
            self.assertEqual((self.final / target).read_bytes(), raw)
        for name in ("worker.mjs", "receiver.mjs"):
            self.assertEqual(sha((self.final / name).read_bytes()), sha(before[Path(name)]))
        delta = json.loads((self.final / "configuration-delta.json").read_bytes())
        self.assertEqual(delta["temporary"]["retainedVersion"], "returned-version-0168")
        self.assertEqual(delta["baseline"], self.baseline)
        self.assertEqual(
            delta["restore"],
            {
                "strategy": "percentage",
                "force": False,
                "versions": [{"version_id": self.baseline["retainedVersion"], "percentage": 100}],
            },
        )
        pin = sha((self.final / "manifest.json").read_bytes())
        self.assertEqual(staged.verify_final(self.final, pin), manifest)
        for field in staged.GATES:
            self.assertIs(manifest[field], False)
        self.assertIs(manifest["identityBound"], True)
        with self.assertRaises(OSError):
            self.finalize(evidence, output=self.root / "replayed-final")
        self.assertFalse((self.root / "replayed-final").exists())

    def test_missing_forged_ambiguous_or_foreign_receipts_refuse_before_claim(self):
        self.stage()
        original = self.evidence()
        mutations = (
            lambda e: e.pop("upload"),
            lambda e: e["upload"].update(status="ambiguous"),
            lambda e: e["upload"].update(versionId="guessed-version"),
            lambda e: e["readback"].update(versionId="other-version"),
            lambda e: e["readback"].update(moduleSha256="0" * 64),
            lambda e: e["readback"].update(configurationSha256="0" * 64),
            lambda e: e["upload"].update(target={"accountId": "foreign", "scriptName": "wrong"}),
            lambda e: e["upload"].update(run="f" * 32),
            lambda e: e.update(stageManifestSha256="0" * 64),
            lambda e: e["baseline"].update(baselineSha256="0" * 64),
            lambda e: e["baseline"].pop("writerReceiptSha256"),
            lambda e: e["resources"][0]["resource"].update(identity="foreign-db"),
            lambda e: e["resources"].pop(),
            lambda e: e["receiver"].update(moduleSha256="0" * 64),
            lambda e: e["receiver"].update(configurationSha256="0" * 64),
            lambda e: e["readback"].update(operationId=e["upload"]["operationId"]),
            lambda e: e["readback"].update(receiptSha256=e["upload"]["receiptSha256"]),
            lambda e: e.update(currentBaselineVerified=True),
        )
        for number, mutate in enumerate(mutations):
            evidence = copy.deepcopy(original)
            mutate(evidence)
            with self.subTest(case=number), self.assertRaises((ValueError, KeyError)):
                self.finalize(evidence)
            self.assertFalse(self.final.exists())
            self.assertFalse((self.output / staged.CLAIM).exists())
        changed = copy.deepcopy(original)
        changed["upload"]["receiptSha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "independent_evidence_pin"):
            self.finalize(changed, pin=staged.object_digest(original))
        self.assertFalse((self.output / staged.CLAIM).exists())

    def test_baseline_scope_or_configuration_drift_and_existing_outputs_refuse(self):
        self.stage()
        evidence = self.evidence()
        originals = copy.deepcopy((self.baseline, self.additions))
        mutations = (
            lambda: self.baseline["configuration"].pop("assets"),
            lambda: self.baseline.update(moduleSha256="0" * 64),
            lambda: self.baseline["productionState"].update(schema="changed"),
            lambda: self.additions["receiver"]["configuration"].update(routes=["foreign"]),
            lambda: self.additions.update(run="f" * 32),
            lambda: self.additions.update(temporaryVersion=self.baseline["retainedVersion"]),
            lambda: self.additions["bindings"][2].update(name="UNREVIEWED_RECEIVER"),
        )
        for number, mutate in enumerate(mutations):
            self.baseline, self.additions = copy.deepcopy(originals)
            mutate()
            with self.subTest(case=number), self.assertRaises(ValueError):
                self.finalize(evidence)
            self.assertFalse(self.final.exists())
            self.assertFalse((self.output / staged.CLAIM).exists())
        self.baseline, self.additions = originals
        self.final.mkdir()
        sentinel = self.final / "sentinel"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(ValueError):
            self.finalize(evidence)
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        self.assertFalse((self.output / staged.CLAIM).exists())

    def test_final_tamper_and_repackaging_cannot_replace_independent_manifest_pin(self):
        self.stage()
        self.finalize(self.evidence())
        manifest_path = self.final / "manifest.json"
        pin = sha(manifest_path.read_bytes())
        worker = self.final / "worker.mjs"
        worker.write_bytes(worker.read_bytes() + b"// changed after review\n")
        with self.assertRaises(ValueError):
            staged.verify_final(self.final, pin)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"]["worker.mjs"] = sha(worker.read_bytes())
        manifest["moduleSha256"] = sha(worker.read_bytes())
        manifest_path.write_bytes(builder.canonical(manifest))
        with self.assertRaisesRegex(ValueError, "manifest_pin"):
            staged.verify_final(self.final, pin)

    def test_stage_output_inside_fixture_refuses_without_touching_fixture(self):
        before = {
            p.relative_to(self.fixture): p.read_bytes()
            for p in self.fixture.rglob("*")
            if p.is_file()
        }
        self.output = self.fixture / "unapproved-stage"
        with patch.object(staged.subprocess, "run") as process:
            with self.assertRaises(ValueError):
                self.stage()
            process.assert_not_called()
        self.assertFalse(self.output.exists())
        after = {
            p.relative_to(self.fixture): p.read_bytes()
            for p in self.fixture.rglob("*")
            if p.is_file()
        }
        self.assertEqual(after, before)

    def test_post_claim_output_failures_consume_stage_without_reset_or_retry(self):
        for failure in ("mkdir", "copy"):
            with self.subTest(failure=failure):
                self.output = self.root / ("stage-failure-" + failure)
                self.final = self.root / ("final-failure-" + failure)
                manifest = self.stage()
                stage_pin = self.stage_pin()
                evidence = self.evidence()
                modules = {
                    name: (self.output / name).read_bytes()
                    for name in ("worker.mjs", "receiver.mjs")
                }
                if failure == "mkdir":
                    mkdir = Path.mkdir

                    def fail_mkdir(path, *args, original_mkdir=mkdir, **kwargs):
                        if path == self.final:
                            raise OSError("synthetic_output_creation_failure")
                        return original_mkdir(path, *args, **kwargs)

                    fault = patch.object(Path, "mkdir", fail_mkdir)
                else:
                    write_bytes = Path.write_bytes

                    def fail_copy(path, raw, original_write=write_bytes):
                        if path.is_relative_to(self.final):
                            raise OSError("synthetic_output_copy_failure")
                        return original_write(path, raw)

                    fault = patch.object(Path, "write_bytes", fail_copy)
                with fault, self.assertRaisesRegex(OSError, "synthetic_output_"):
                    self.finalize(evidence)
                claim = self.output / staged.CLAIM
                self.assertTrue(claim.is_file())
                claimed_bytes = claim.read_bytes()
                self.assertEqual(staged.verify_stage(self.output, stage_pin), manifest)
                retry_output = self.root / ("retry-" + failure)
                with self.assertRaises(FileExistsError):
                    self.finalize(evidence, output=retry_output)
                self.assertFalse(retry_output.exists())
                self.assertEqual(claim.read_bytes(), claimed_bytes)
                for name, raw in modules.items():
                    self.assertEqual((self.output / name).read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
