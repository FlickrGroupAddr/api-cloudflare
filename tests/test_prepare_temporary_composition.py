"""Adversarial integrity checks for the supplied offline composition source packet.

No captured private modules, provider configuration, credentials or native host are read.
"""

import hashlib
import json
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_temporary_composition as packet


class TemporaryCompositionPacketTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-composition-packet-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "repository"
        self.source.mkdir()
        for name in packet.FILES:
            destination = self.source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((Path(__file__).resolve().parents[1] / name).read_bytes())
        self.output = self.base / "packet"

    def prepare(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            return packet.prepare(self.source, self.output)

    def directory_link(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        self.assertTrue(link.is_symlink() or link.is_junction())

    def test_deterministic_closed_source_packet(self):
        manifest = self.prepare()
        self.assertEqual(packet.verify(self.output), manifest)
        second = packet.prepare(self.source, self.base / "second")
        self.assertEqual(manifest, second)
        actual = {
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual, {"manifest.json", *("source/" + name for name in packet.FILES)})
        for name in packet.FILES:
            self.assertEqual(
                (self.output / "source" / name).read_bytes(), (self.source / name).read_bytes()
            )

    def test_extra_missing_and_changed_packet_files_refused(self):
        self.prepare()
        extra = self.output / "unlisted.json"
        extra.write_bytes(b"{}")
        with self.assertRaises(ValueError):
            packet.verify(self.output)
        extra.unlink()
        source = self.output / "source" / packet.FILES[0]
        original = source.read_bytes()
        source.write_bytes(original + b"\n// altered offline source\n")
        with self.assertRaises(ValueError):
            packet.verify(self.output)
        source.unlink()
        with self.assertRaises(ValueError):
            packet.verify(self.output)

    def test_manifest_byte_and_schema_tamper_refused(self):
        self.prepare()
        path = self.output / "manifest.json"
        original = path.read_bytes()
        path.write_bytes(b"{")
        with self.assertRaises(ValueError):
            packet.verify(self.output)
        modified = json.loads(original)
        modified["unexpected"] = "unreviewed"
        path.write_text(json.dumps(modified), encoding="utf-8")
        with self.assertRaises(ValueError):
            packet.verify(self.output)

    def test_existing_and_nested_destinations_refused_before_writes(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(self.output.iterdir()), [])
        nested = self.source / "nested-packet"
        with self.assertRaises(ValueError):
            packet.prepare(self.source, nested)
        self.assertFalse(nested.exists())

    def test_unlisted_repository_content_never_copied(self):
        unrelated = self.source / "unlisted-private.json"
        unrelated.write_bytes(b"synthetic private sentinel")
        self.prepare()
        self.assertFalse((self.output / unrelated.name).exists())
        self.assertFalse((self.output / "source" / unrelated.name).exists())
        self.assertEqual(unrelated.read_bytes(), b"synthetic private sentinel")

    def test_source_and_packet_directory_links_refused(self):
        original = self.source / "probes"
        target = self.base / "linked-content"
        original.rename(target)
        self.directory_link(original, target)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_packet_root_and_nested_links_refused(self):
        self.prepare()
        linked = self.base / "linked-packet"
        self.directory_link(linked, self.output)
        with self.assertRaises(ValueError):
            packet.verify(linked)
        original = self.output / "source" / "probes"
        target = self.base / "linked-packet-content"
        original.rename(target)
        self.directory_link(original, target)
        with self.assertRaises(ValueError):
            packet.verify(self.output)

    def test_hash_provenance_and_absent_configuration_stay_explicit(self):
        manifest = self.prepare()
        self.assertEqual(manifest["kind"], "offline_source_safe_temporary_composition")
        self.assertEqual(manifest["entrypoint"], "probes/fixed-origin-composition/entrypoint.mjs")
        self.assertEqual(manifest["export"], "createTemporaryComposition")
        self.assertIs(manifest["defaultWorkerExport"], False)
        self.assertEqual(set(manifest["files"]), set(packet.FILES))
        for name, row in manifest["files"].items():
            raw = (self.output / "source" / name).read_bytes()
            self.assertEqual(row, {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        captured = manifest["captured"]
        self.assertEqual(
            captured["moduleSha256"],
            "f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d",
        )
        self.assertEqual(
            captured["captureIndexSha256"],
            "ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202",
        )
        self.assertIsNone(captured["retainedVersionIdentity"])
        self.assertEqual(
            captured["ordinaryDispatch"], "captured.default.fetch(request, productionEnv)"
        )
        self.assertIs(captured["requestIdentityPreserved"], True)
        self.assertIs(captured["environmentIdentityPreserved"], True)
        configuration = manifest["configuration"]
        self.assertEqual(configuration["source"], "constructor_injection_only")
        for field in ("receiverBindingKey", "providerTarget"):
            self.assertIsNone(configuration[field])
        for field in ("capturedBindingDeltaVerified", "intakeEnabled", "dispatchEnabled"):
            self.assertIs(configuration[field], False)
        self.assertEqual(
            manifest["existingLimits"], {"fga": 96, "receiver": 16, "lifetimeMs": 1200000}
        )
        self.assertEqual(
            manifest["authority"], "offline_preparation_only_no_proposed_amendment_assumed"
        )
        self.assertEqual(manifest["missingProofs"], list(packet.MISSING_PROOFS))
        self.assertIn("immutable_candidate_module_and_migration_closure", manifest["missingProofs"])
        self.assertIn(
            "complete_temporary_configuration_delta_and_receiver_target", manifest["missingProofs"]
        )
        for field in (
            "deployReady",
            "deploymentAllowed",
            "providerRestorationVerified",
            "productionStateVerified",
        ):
            self.assertIs(manifest[field], False)

    def test_each_disabled_gate_and_provenance_promotion_refused(self):
        manifest = self.prepare()
        path = self.output / "manifest.json"
        for field in (
            "deployReady",
            "deploymentAllowed",
            "providerRestorationVerified",
            "productionStateVerified",
        ):
            for replacement in (True, 0):
                modified = json.loads(json.dumps(manifest))
                modified[field] = replacement
                path.write_text(json.dumps(modified), encoding="utf-8")
                with self.subTest(field=field, value=replacement), self.assertRaises(ValueError):
                    packet.verify(self.output)
        modifications = (
            ("configuration", "capturedBindingDeltaVerified", True),
            ("configuration", "intakeEnabled", True),
            ("configuration", "dispatchEnabled", True),
            ("configuration", "providerTarget", "synthetic-target"),
            ("captured", "moduleSha256", "0" * 64),
            ("captured", "retainedVersionIdentity", "synthetic-version"),
        )
        for group, field, value in modifications:
            modified = json.loads(json.dumps(manifest))
            modified[group][field] = value
            path.write_text(json.dumps(modified), encoding="utf-8")
            with self.subTest(field=field), self.assertRaises(ValueError):
                packet.verify(self.output)
        modified = dict(manifest, missingProofs=[])
        path.write_text(json.dumps(modified), encoding="utf-8")
        with self.assertRaises(ValueError):
            packet.verify(self.output)

    def test_self_consistent_repackaging_cannot_replace_source_pin(self):
        self.prepare()
        name = packet.FILES[0]
        source = self.output / "source" / name
        raw = source.read_bytes() + b"\n// replacement source\n"
        source.write_bytes(raw)
        path = self.output / "manifest.json"
        modified = json.loads(path.read_bytes())
        modified["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        path.write_text(json.dumps(modified), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source_pin_mismatch"):
            packet.verify(self.output)

    def test_changed_source_imports_escape_and_external_dependency_refused_before_writes(self):
        path = self.source / packet.FILES[0]
        original = path.read_bytes()
        for added in (
            b'import "../../../../outside.mjs";\n',
            b'import "./missing.mjs";\n',
            b'import "unlisted-provider";\n',
        ):
            path.write_bytes(added + original)
            with self.subTest(imported=added), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.output.exists())
        path.unlink()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_extra_empty_directory_and_manifest_path_escape_refused(self):
        self.prepare()
        extra = self.output / "unlisted-empty"
        extra.mkdir()
        with self.assertRaises(ValueError):
            packet.verify(self.output)
        extra.rmdir()
        path = self.output / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["files"]["../../outside.mjs"] = manifest["files"].pop(packet.FILES[0])
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            packet.verify(self.output)


if __name__ == "__main__":
    unittest.main()
