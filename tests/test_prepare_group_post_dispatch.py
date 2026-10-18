"""Closed packet adversarial checks; synthetic private values only, no provider/native action."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_group_post_dispatch as packet


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.run_root = Path(self.temp.name) / "new-run"
        self.override = patch.object(packet, "RUN_ROOT", self.run_root)
        self.override.start()
        self.addCleanup(self.override.stop)
        # Copy only the public immutable base closure. New callers use inert bytes.
        for name in packet.BASE_SOURCES | {packet.BASE_MANIFEST}:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((packet.ROOT / name).read_bytes())
        for name in packet.NEW_SOURCES:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"inert source fixture\n")
        self.write_manifest()

    def write_json(self, path, value):
        path.write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")

    def write_manifest(self):
        self.manifest = {
            "schemaVersion": 1,
            "kind": "offline_post_dispatch_preparation",
            "binding": packet.binding(),
            "sources": {name: packet.digest(self.root / name) for name in packet.SOURCES},
            "productionQualified": False,
        }
        self.write_json(self.root / packet.MANIFEST, self.manifest)

    def granted(self):
        packet.prepare(root=self.root)
        self.config_path = self.run_root / "private/config.json"
        self.approval_path = self.run_root / "private/approved-packet.json"
        _, self.config = packet.snapshot(self.config_path)
        self.config.update(accountId="a" * 32, subdomain="synthetic-only")
        self.write_json(self.config_path, self.config)
        _, self.approval = packet.snapshot(self.approval_path)
        self.approval.update(
            configSha256=packet.digest(self.config_path), ownerConsent=True, nativeConsent=True
        )
        self.write_json(self.approval_path, self.approval)

    def validate(self):
        return packet.validate_packet(
            self.approval_path, packet.digest(self.approval_path), root=self.root
        )

    def test_prepare_is_ungranted_and_does_not_create_handshake_or_token(self):
        packet.prepare(root=self.root)
        private = self.run_root / "private"
        _, value = packet.snapshot(private / "approved-packet.json")
        self.assertIs(value["ownerConsent"], False)
        self.assertIs(value["nativeConsent"], False)
        self.assertFalse((private / "operator-token.txt").exists())
        self.assertFalse((self.run_root / "handshake").exists())
        with self.assertRaises(ValueError):
            packet.validate_packet(
                private / "approved-packet.json",
                packet.digest(private / "approved-packet.json"),
                root=self.root,
            )
        with self.assertRaises(FileExistsError):
            packet.prepare(root=self.root)

    def test_exact_granted_binding_returns_only_config(self):
        self.granted()
        self.assertEqual(self.validate(), self.config)

    def test_manifest_missing_extra_and_substituted_paths_rejected(self):
        for change in ("missing", "extra", "substitute"):
            with self.subTest(change=change):
                self.write_manifest()
                if change != "extra":
                    self.manifest["sources"].pop("scripts/group_post_dispatch.py")
                if change != "missing":
                    self.manifest["sources"]["scripts/unreviewed.py"] = "a" * 64
                self.write_json(self.root / packet.MANIFEST, self.manifest)
                with self.assertRaises(ValueError):
                    packet.validate_manifest(root=self.root)

    def test_changed_source_or_pin_rejected(self):
        path = self.root / "scripts/group_post_dispatch.py"
        path.write_bytes(b"substitution\n")
        with self.assertRaises(ValueError):
            packet.validate_manifest(root=self.root)
        self.write_manifest()
        self.manifest["sources"]["scripts/group_post_dispatch.py"] = "f" * 64
        self.write_json(self.root / packet.MANIFEST, self.manifest)
        with self.assertRaises(ValueError):
            packet.validate_manifest(root=self.root)

    def test_base_manifest_or_source_cannot_be_repinned(self):
        path = self.root / "scripts/group_post_characterization.py"
        path.write_bytes(b"changed base\n")
        self.write_manifest()
        with self.assertRaises(ValueError):
            packet.validate_manifest(root=self.root)
        (self.root / packet.BASE_MANIFEST).write_bytes(b"{}\n")
        with self.assertRaises(ValueError):
            packet.validate_manifest(root=self.root)

    def test_config_identity_paths_extra_fields_and_boolean_schema_rejected(self):
        self.granted()
        original = dict(self.config)
        for key, item in (
            ("runId", "c01ba6d2c2754597aa311c9f"),
            ("coordinationRoot", "C:/Temp/old-bridge"),
            ("nativeRoot", "C:/Temp/other"),
            ("tokenFile", "C:/Temp/old-token"),
            ("schemaVersion", True),
            ("extra", "unreviewed"),
        ):
            with self.subTest(key=key):
                self.write_json(self.config_path, {**original, key: item})
                self.approval["configSha256"] = packet.digest(self.config_path)
                self.write_json(self.approval_path, self.approval)
                with self.assertRaises(ValueError):
                    self.validate()

    def test_approval_digest_config_digest_manifest_digest_and_consent_required(self):
        self.granted()
        with self.assertRaises(ValueError):
            packet.validate_packet(self.approval_path, "a" * 64, root=self.root)
        original = dict(self.approval)
        for key, item in (
            ("manifestSha256", "a" * 64),
            ("configSha256", "a" * 64),
            ("ownerConsent", False),
            ("nativeConsent", False),
            ("ownerConsent", 1),
            ("runId", "c01ba6d2c2754597aa311c9f"),
            ("extra", True),
        ):
            with self.subTest(key=key):
                self.write_json(self.approval_path, {**original, key: item})
                with self.assertRaises(ValueError):
                    self.validate()

    def test_duplicate_json_and_wrong_approval_path_refused(self):
        self.granted()
        self.approval_path.write_text('{"runId":"a","runId":"b"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.validate()
        with self.assertRaises(ValueError):
            packet.validate_packet(self.run_root / "old.json", "a" * 64, root=self.root)


if __name__ == "__main__":
    unittest.main()
