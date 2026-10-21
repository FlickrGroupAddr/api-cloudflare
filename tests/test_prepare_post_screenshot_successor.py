"""Adversarial offline successor bindings; no native or provider boundaries."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import hosted_publisher_execution as protected
from scripts import prepare_post_screenshot_successor as subject


class PreparationTests(unittest.TestCase):
    def test_unqualified_runtime_root_refuses_before_creating_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            runs.mkdir(mode=0o700)
            with (
                patch.object(subject, "validate_manifest", return_value="a" * 64),
                patch.object(subject, "_assert_private", side_effect=ValueError("custody")),
            ):
                with self.assertRaisesRegex(ValueError, "custody"):
                    subject.prepare(runs=runs, run_id="b" * 24)
            self.assertFalse((runs / ("b" * 24)).exists())

    def test_private_history_rejects_consumed_and_malformed_lists(self):
        subject.validate_spent_history("b" * 24, ["c" * 24])
        for values in (["b" * 24], [], ["c" * 24] * 2, ["invalid"], ["c" * 24] * 257):
            with self.subTest(values=values), self.assertRaises(ValueError):
                subject.validate_spent_history("b" * 24, values)

    def test_spent_and_placeholder_identities_refused(self):
        for value in (*subject.SPENT, "", "a" * 23, "A" * 24, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                subject.identity(value)

    def test_exclusive_ungranted_preparation_and_pin_drift(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(protected, "_windows_private"),
        ):
            root = Path(directory)
            sources = {"source.py"}
            (root / "source.py").write_text("source", encoding="utf-8")
            manifest = root / subject.MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "ungranted_screenshot_post_successor",
                        "productionQualified": False,
                        "sources": {"source.py": subject.digest(root / "source.py")},
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(subject, "SOURCES", sources):
                result = subject.prepare(root=root, runs=root / "runs", run_id="a" * 24)
                private = root / "runs" / result["runId"] / "private"
                _, approval = subject.snapshot(private / "approved-packet.json")
                for key in ("ownerConsent", "nativeConsent", "caseCancelConsent"):
                    self.assertIs(approval[key], False)
                with self.assertRaises(FileExistsError):
                    subject.prepare(root=root, runs=root / "runs", run_id="a" * 24)
                with self.assertRaises(ValueError):
                    subject.validate_packet(
                        private / "approved-packet.json",
                        subject.digest(private / "approved-packet.json"),
                        root=root,
                        runs=root / "runs",
                    )
                (root / "source.py").write_text("drift", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "source_changed"):
                    subject.validate_manifest(root=root)

    def test_source_set_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / subject.MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "ungranted_screenshot_post_successor",
                        "productionQualified": False,
                        "sources": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "manifest_invalid"):
                subject.validate_manifest(root=root)

    def test_exact_valid_envelope_then_config_drift(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(protected, "_windows_private"),
        ):
            root = Path(directory)
            scope = root / subject.SCOPE
            (root / "runs").mkdir(mode=0o700)
            scope.parent.mkdir(parents=True)
            scope.write_text("finite exact scope", encoding="utf-8")
            with patch.object(subject, "validate_manifest", return_value="a" * 64):
                subject.prepare(root=root, runs=root / "runs", run_id="b" * 24)
                private = root / "runs" / ("b" * 24) / "private"
                config_path = private / "config.json"
                _, config = subject.snapshot(config_path)
                parent = root / "synthetic-parent-token.txt"
                parent.write_bytes(b"SYNTHETIC-PARENT-NOT-A-REAL-CREDENTIAL")
                config.update(
                    parentTokenFile=str(parent),
                    spentRunIds=["c" * 24],
                    accountId="a" * 32,
                    subdomain="test",
                    actionDeadlineUnix=2300,
                    credentialExpiryUnix=2400,
                    windowId=321,
                )
                for key in config:
                    if key.endswith("Sha2_256"):
                        config[key] = "a" * 64
                config["scopeSha2_256"] = subject.digest(scope)
                config_path.write_text(json.dumps(config), encoding="utf-8")
                approval_path = private / "approved-packet.json"
                _, approval = subject.snapshot(approval_path)
                approval.update(
                    configSha2_256=subject.digest(config_path),
                    ownerConsent=True,
                    nativeConsent=True,
                    caseCancelConsent=True,
                )
                approval_path.write_text(json.dumps(approval), encoding="utf-8")
                pin = subject.digest(approval_path)
                self.assertEqual(
                    subject.validate_packet(
                        approval_path, pin, root=root, runs=root / "runs", clock=lambda: 1000
                    ),
                    config,
                )
                config["windowId"] = 322
                config_path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(ValueError):
                    subject.validate_packet(
                        approval_path, pin, root=root, runs=root / "runs", clock=lambda: 1000
                    )


if __name__ == "__main__":
    unittest.main()
