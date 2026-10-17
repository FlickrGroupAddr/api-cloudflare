"""Closed restoration-input failures; actual captured VM rehearsal is separate."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fixed_origin_restore as restore


class RestorationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.capture = self.root / "private-evidence" / "capture"
        (self.capture / "private").mkdir(parents=True)
        self.output = self.capture.parent / "restoration"
        source = b"synthetic unit input, never executed"
        self.source_digest = restore.digest(source)
        self.contents = dict.fromkeys(restore.FILES, b"{}")
        self.contents["active_version_0_modules.json"] = self.encode(
            {
                "result": {
                    "id": "unit-version",
                    "main_module": "worker.js",
                    "modules": [
                        {
                            "content_base64": base64.b64encode(source).decode(),
                        }
                    ],
                }
            }
        )
        self.contents["active_version_0.json"] = self.encode(
            {
                "result": {
                    "id": "unit-version",
                    "resources": {
                        "bindings": [
                            {
                                "type": "plain_text",
                                "name": "FGA_ARTIFACT_SHA2_256",
                                "text": self.source_digest,
                            },
                            {"type": "plain_text", "name": "FGA_INTAKE_ENABLED", "text": "0"},
                            {"type": "plain_text", "name": "FGA_DISPATCH_ENABLED", "text": "0"},
                        ]
                    },
                }
            }
        )
        self.contents["restoration-inputs.json"] = self.encode(
            {
                "deploymentStable": True,
                "artifactBoundToEveryActiveVersion": True,
                "pinnedActiveVersionWeights": {"unit-version": 100},
                "captured": {
                    name.removesuffix(".json").removesuffix(".bin"): {
                        "SHA2-256": restore.digest(raw),
                    }
                    for name, raw in self.contents.items()
                    if name != "restoration-inputs.json"
                },
            }
        )
        self.write_capture()

    @staticmethod
    def encode(value):
        return json.dumps(value).encode()

    def write_capture(self):
        for name, raw in self.contents.items():
            (self.capture / "private" / name).write_bytes(raw)
        index = self.encode(
            {
                "files": [
                    {"name": name, "bytes": len(raw), "sha256": restore.digest(raw)}
                    for name, raw in self.contents.items()
                ]
            }
        )
        (self.capture / "private-integrity-index.json").write_bytes(index)
        self.index_digest = restore.digest(index)

    def prepare(self):
        with (
            patch.object(restore, "INDEX_SHA256", self.index_digest),
            patch.object(restore, "MODULE_SHA256", self.source_digest),
        ):
            return restore.prepare(self.repo, self.capture, self.output)

    def test_private_packet_retains_exact_inputs_and_refuses_reuse(self):
        manifest = self.prepare()
        self.assertFalse(manifest["deploymentAllowed"])
        self.assertFalse(manifest["providerRestorationVerified"])
        for name, raw in self.contents.items():
            self.assertEqual((self.output / name).read_bytes(), raw)
        with self.assertRaisesRegex(ValueError, "fresh_private"):
            self.prepare()

    def test_tampering_cannot_be_hidden_by_rewriting_packet_manifest(self):
        self.prepare()
        (self.output / "routes.json").write_bytes(b"changed")
        manifest = json.loads((self.output / "manifest.json").read_text())
        manifest["files"]["routes.json"] = restore.digest(b"changed")
        (self.output / "manifest.json").write_text(json.dumps(manifest))
        with (
            patch.object(restore, "INDEX_SHA256", self.index_digest),
            patch.object(restore, "MODULE_SHA256", self.source_digest),
            self.assertRaisesRegex(ValueError, "packet_integrity"),
        ):
            restore.verify_packet(self.output)

    def test_capture_tampering_fails_before_destination_creation(self):
        (self.capture / "private" / "zone_settings.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "capture_integrity"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_offline_packet_cannot_claim_deployment_permission(self):
        self.prepare()
        manifest = json.loads((self.output / "manifest.json").read_text())
        manifest["deploymentAllowed"] = True
        (self.output / "manifest.json").write_text(json.dumps(manifest))
        with (
            patch.object(restore, "INDEX_SHA256", self.index_digest),
            patch.object(restore, "MODULE_SHA256", self.source_digest),
            self.assertRaisesRegex(ValueError, "packet_inventory"),
        ):
            restore.verify_packet(self.output)

    def test_untrusted_index_refused(self):
        with self.assertRaisesRegex(ValueError, "capture_index"):
            restore.validate_capture(self.capture)

    def test_public_or_repository_destinations_refused(self):
        for path in [self.repo / "private-evidence" / "packet", self.root / "public"]:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "private"):
                restore.private_path(path, self.repo)

    def test_enabled_write_configuration_refused(self):
        version = json.loads(self.contents["active_version_0.json"])
        version["result"]["resources"]["bindings"][2]["text"] = "1"
        self.contents["active_version_0.json"] = self.encode(version)
        restoration = json.loads(self.contents["restoration-inputs.json"])
        restoration["captured"]["active_version_0"]["SHA2-256"] = restore.digest(
            self.contents["active_version_0.json"]
        )
        self.contents["restoration-inputs.json"] = self.encode(restoration)
        self.write_capture()
        with self.assertRaisesRegex(ValueError, "capability"):
            self.prepare()

    def test_weight_or_exact_version_mismatch_refused(self):
        restoration = json.loads(self.contents["restoration-inputs.json"])
        restoration["pinnedActiveVersionWeights"] = {"other-version": 100}
        self.contents["restoration-inputs.json"] = self.encode(restoration)
        self.write_capture()
        with self.assertRaisesRegex(ValueError, "version_mismatch"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
