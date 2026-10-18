"""Renewed packet source tests, using public closure and synthetic inputs only."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_renewed_group_post_attempt as packet


class RenewedAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.run_root = Path(self.temp.name) / "new-run"
        override = patch.object(packet, "RUN_ROOT", self.run_root)
        override.start()
        self.addCleanup(override.stop)
        # Preserve sealed 0160 source bytes in a disposable public-source fixture.
        for name in packet.sealed.SOURCES | {packet.sealed.MANIFEST}:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((packet.ROOT / name).read_bytes())
        for name in packet.NEW_SOURCES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"inert synthetic source fixture\n")
        self.manifest = {
            "schemaVersion": 1,
            "kind": "ungranted_renewed_post_attempt",
            "binding": packet.binding(),
            "sources": {name: packet.digest(self.root / name) for name in packet.SOURCES},
            "productionQualified": False,
        }
        self.write_json(self.root / packet.MANIFEST, self.manifest)

    def write_json(self, path, value):
        path.write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")

    def prepare(self):
        packet.prepare(root=self.root)
        self.config_path = self.run_root / "private/config.json"
        self.approval_path = self.run_root / "private/approved-packet.json"
        _, self.config = packet.snapshot(self.config_path)
        _, self.approval = packet.snapshot(self.approval_path)

    def synthetic_bound_packet(self):
        self.prepare()
        self.config.update(
            accountId="a" * 32,
            subdomain="synthetic-only",
            actionDeadlineUnix=2500,
            tokenRequirementsConfirmed=True,
            actionScopeSha256=packet.digest(self.root / packet.PACKET),
        )
        self.approval.update(ownerConsent=True, nativeConsent=True)
        self.save_config()

    def save_config(self):
        self.write_json(self.config_path, self.config)
        self.approval["configSha256"] = packet.digest(self.config_path)
        self.write_json(self.approval_path, self.approval)

    def validate(self):
        with patch.object(packet.time, "time", return_value=1000):
            return packet.validate_packet(
                self.approval_path, packet.digest(self.approval_path), root=self.root
            )

    def test_preparation_leaves_missing_inputs_explicit_and_never_grants_authority(self):
        self.prepare()
        self.assertEqual(self.config["accountId"], "")
        self.assertEqual(self.config["subdomain"], "")
        self.assertIsNone(self.config["actionDeadlineUnix"])
        self.assertIs(self.config["tokenRequirementsConfirmed"], False)
        self.assertEqual(self.config["actionScopeSha256"], "")
        self.assertIs(self.approval["ownerConsent"], False)
        self.assertIs(self.approval["nativeConsent"], False)
        self.assertFalse((self.run_root / "private/operator-token.txt").exists())
        self.assertFalse((self.run_root / "handshake").exists())
        with self.assertRaisesRegex(ValueError, "consent_or_packet_invalid"):
            self.validate()
        with self.assertRaises(FileExistsError):
            packet.prepare(root=self.root)

    def test_exact_bound_approval_returns_only_config_without_runtime_state(self):
        self.synthetic_bound_packet()
        self.assertEqual(self.validate(), self.config)
        self.assertFalse((self.run_root / "private/operator-token.txt").exists())
        self.assertFalse((self.run_root / "handshake").exists())

    def test_absolute_deadline_boundaries_and_new_native_caller_are_in_exact_closure(self):
        self.synthetic_bound_packet()
        self.assertIn("scripts/renewed_group_post_attempt.py", packet.NEW_SOURCES)
        self.assertIn("scripts/group_post_native_dispatch.mjs", packet.NEW_SOURCES)
        for deadline in (2230, 2800):
            with self.subTest(deadline=deadline):
                self.config["actionDeadlineUnix"] = deadline
                self.save_config()
                self.assertEqual(self.validate(), self.config)

    def test_missing_or_invalid_action_inputs_fail_before_route_gate(self):
        self.synthetic_bound_packet()
        original = dict(self.config)
        for key, value in (
            ("accountId", ""),
            ("subdomain", ""),
            ("actionDeadlineUnix", None),
            ("actionDeadlineUnix", 1000),
            ("actionDeadlineUnix", 2229),
            ("actionDeadlineUnix", 2801),
            ("actionDeadlineUnix", True),
            ("actionDeadlineUnix", float("inf")),
            ("tokenRequirementsConfirmed", False),
            ("tokenRequirementsConfirmed", 1),
            ("actionScopeSha256", ""),
            ("actionScopeSha256", "0" * 64),
            ("runId", packet.sealed.RUN_ID),
            ("coordinationRoot", "C:/synthetic/old"),
            ("extra", "unreviewed"),
        ):
            with self.subTest(key=key, value=value):
                self.config = {**original, key: value}
                self.save_config()
                with self.assertRaisesRegex(ValueError, "^private_config_invalid$"):
                    self.validate()
        for key in ("actionDeadlineUnix", "tokenRequirementsConfirmed", "actionScopeSha256"):
            with self.subTest(missing=key):
                self.config = dict(original)
                del self.config[key]
                self.save_config()
                with self.assertRaisesRegex(ValueError, "^private_config_invalid$"):
                    self.validate()

    def test_old_consent_identity_or_changed_hash_cannot_authorize_new_packet(self):
        self.synthetic_bound_packet()
        original = dict(self.approval)
        for key, value in (
            ("ownerConsent", False),
            ("nativeConsent", False),
            ("ownerConsent", 1),
            ("runId", packet.sealed.RUN_ID),
            ("configSha256", "0" * 64),
            ("manifestSha256", "0" * 64),
            ("extra", True),
        ):
            with self.subTest(key=key):
                self.write_json(self.approval_path, {**original, key: value})
                with self.assertRaisesRegex(ValueError, "^consent_or_packet_invalid$"):
                    self.validate()
        with self.assertRaisesRegex(ValueError, "approval_digest_changed"):
            packet.validate_packet(self.approval_path, "0" * 64, root=self.root)

    def test_new_manifest_rejects_extra_source_and_changed_source(self):
        self.manifest["sources"]["scripts/unreviewed.py"] = "0" * 64
        self.write_json(self.root / packet.MANIFEST, self.manifest)
        with self.assertRaisesRegex(ValueError, "renewed_manifest_invalid"):
            packet.validate_manifest(root=self.root)
        del self.manifest["sources"]["scripts/unreviewed.py"]
        self.write_json(self.root / packet.MANIFEST, self.manifest)
        (self.root / "scripts/group_post_native_dispatch.mjs").write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "renewed_source_changed"):
            packet.validate_manifest(root=self.root)

    def test_rehash_cannot_replace_sealed_dispatch_or_original_source(self):
        original = self.root / "scripts/group_post_characterization.py"
        original.write_bytes(b"changed sealed source\n")
        with self.assertRaises(ValueError):
            packet.validate_manifest(root=self.root)
        (self.root / packet.BASE_MANIFEST).write_bytes(b"{}\n")
        self.manifest["sources"][packet.BASE_MANIFEST] = packet.digest(
            self.root / packet.BASE_MANIFEST
        )
        self.write_json(self.root / packet.MANIFEST, self.manifest)
        with self.assertRaisesRegex(ValueError, "sealed_dispatch_manifest_changed"):
            packet.validate_manifest(root=self.root)

    def test_duplicate_approval_fields_and_unbound_approval_path_are_refused(self):
        self.synthetic_bound_packet()
        self.approval_path.write_text('{"runId":"a","runId":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate_field"):
            self.validate()
        with self.assertRaisesRegex(ValueError, "approval_path_invalid"):
            packet.validate_packet(self.run_root / "old.json", "a" * 64, root=self.root)


if __name__ == "__main__":
    unittest.main()
