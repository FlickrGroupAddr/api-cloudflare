"""Source-only closure, metadata and private artifact integrity checks."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_native_evidence_checks as packet


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        for relative in (*packet.SOURCES.values(), *packet.CHECKS.values()):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((packet.ROOT / relative).read_bytes())
        self.stage = self.base / "private-stage"

    def test_real_closure_and_invalid_template_round_trip(self):
        result = packet.prepare(self.stage, self.root)
        pin = result["artifactSha2_256"]
        assert isinstance(pin, str)
        self.assertEqual(packet.verify(self.stage, pin), result)
        consent = json.loads((self.stage / "consent-template.json").read_bytes())
        self.assertIsNone(consent["owner"])
        for key in ("runId", "actionId", "phase", "catalogPath", "grantedAt", "expiresAt"):
            self.assertIsNone(consent[key])
        self.assertTrue(all(v is False for k, v in consent.items() if k.startswith("allow")))
        plan = json.loads((self.stage / "run-plan.json").read_bytes())
        self.assertEqual(plan["phases"], list(packet.PHASES))
        self.assertFalse(plan["productionQualified"])
        self.assertNotIn("maximumRunSeconds", plan)
        self.assertEqual(plan["maximumConsentSeconds"], 1800)
        self.assertFalse(plan["hostWaitBoundProven"])
        self.assertFalse(plan["filesystemIdentityProven"])
        self.assertFalse(plan["atomicOutputCreationProven"])
        self.assertTrue(plan["nativeActionStillUnavailable"])
        self.assertEqual(plan["phaseReplay"], "refused_consumed_once")
        checks = result["checks"]
        assert isinstance(checks, list)
        self.assertEqual(len(checks), len(packet.CHECKS))

    def test_old_fixture_version_or_wrong_host_refuses(self):
        config = self.root / packet.FIXTURE / "Config.lua"
        original = config.read_bytes()
        for before, after in ((b"0.0.1.1", b"0.0.1.2"), (b"15.3", b"15.30")):
            with self.subTest(after=after):
                self.assertIn(before, original)
                config.write_bytes(original.replace(before, after))
                with self.assertRaises(ValueError):
                    packet.prepare(self.stage, self.root)
                self.assertFalse(self.stage.exists())
        config.write_bytes(original)

    def test_unresolved_dependency_refuses_before_writing(self):
        native = self.root / packet.FIXTURE / "Native.lua"
        native.write_bytes(native.read_bytes() + b"\nrequire 'UnreviewedTransport'\n")
        with self.assertRaises(ValueError):
            packet.prepare(self.stage, self.root)
        self.assertFalse(self.stage.exists())

    def test_capability_flags_phase_plan_and_info_identity_are_invariant(self):
        changes = (
            ("Config.lua", b"NATIVE_SCOPE_READY=false", b"NATIVE_SCOPE_READY=true"),
            ("Config.lua", b"'restart_observe'", b"'unbounded_retry'"),
            ("Info.lua", b".evidence.lrc15", b".qualification.lrc15"),
            ("Info.lua", b"build=1", b"build=2"),
            ("Package.lua", b"nativeSchedulingProven=false", b"nativeSchedulingProven=true"),
        )
        for name, before, after in changes:
            with self.subTest(name=name, before=before):
                path = self.root / packet.FIXTURE / name
                original = path.read_bytes()
                self.assertIn(before, original)
                path.write_bytes(original.replace(before, after))
                with self.assertRaises(ValueError):
                    packet.prepare(self.stage, self.root)
                self.assertFalse(self.stage.exists())
                path.write_bytes(original)

    def test_extra_modified_missing_and_granted_template_refuse(self):
        packet.prepare(self.stage, self.root)
        targets = {
            self.stage / "extra.txt": b"extra",
            self.stage / packet.BUNDLE / "Native.lua": b"modified",
            self.stage / "checks" / "native_profile_evidence.py": b"modified",
            self.stage / "consent-template.json": b'{"owner":"Terry"}',
            self.stage / "run-plan.json": b"{}",
        }
        for path, changed in targets.items():
            with self.subTest(path=path.name):
                old = path.read_bytes() if path.exists() else None
                path.write_bytes(changed)
                with self.assertRaises(ValueError):
                    packet.verify(self.stage)
                if old is None:
                    path.unlink()
                else:
                    path.write_bytes(old)
        native = self.stage / packet.BUNDLE / "Native.lua"
        native.unlink()
        with self.assertRaises(ValueError):
            packet.verify(self.stage)

    def test_duplicate_all_protected_metadata_declarations_refuse(self):
        files = packet.source_files(self.root)
        fields = {
            "Config.lua": (
                "VERSION",
                "SDK",
                "EXPECTED_HOST",
                "PHASES",
                "PRODUCTION_QUALIFIED",
                "NATIVE_SCHEDULING_PROVEN",
                "NATIVE_SCOPE_READY",
            ),
            "Package.lua": (
                "schemaVersion",
                "version",
                "hostMajor",
                "hostVersion",
                "sdkVersion",
                "nativeScopeReady",
                "productionQualified",
                "nativeSchedulingProven",
            ),
            "Info.lua": (
                "LrMetadataProvider",
                "LrSdkVersion",
                "LrSdkMinimumVersion",
                "LrToolkitIdentifier",
                "VERSION",
            ),
        }
        for name, keys in fields.items():
            for key in keys:
                with self.subTest(name=name, key=key):
                    original = files[name]
                    prefix, suffix = original.rsplit(b"}", 1)
                    mutated = {**files, name: prefix + b"," + key.encode() + b"=true}" + suffix}
                    with self.assertRaises(ValueError):
                        packet.validate_files(mutated)

    def test_self_rehashed_readiness_flip_still_refuses(self):
        packet.prepare(self.stage, self.root)
        path = self.stage / packet.BUNDLE / "Config.lua"
        old = path.read_bytes()
        path.write_bytes(
            old.replace(
                b"NATIVE_SCOPE_READY=false", b"NATIVE_SCOPE_READY=false,NATIVE_SCOPE_READY=true"
            )
        )
        files = {name: (self.stage / packet.BUNDLE / name).read_bytes() for name in packet.SOURCES}
        checks = {name: (self.stage / "checks" / name).read_bytes() for name in packet.CHECKS}
        forged = packet.manifest(files, checks)
        (self.stage / "manifest.json").write_bytes(packet.encoded(forged))
        (self.stage / "run-plan.json").write_bytes(packet.encoded(packet.run_plan(forged)))
        (self.stage / "consent-template.json").write_bytes(
            packet.encoded(packet.consent_template(forged))
        )
        # Even without an external artifact pin, exact independent metadata
        # pins refuse a self-consistent artifact with readiness enabled.
        with self.assertRaises(ValueError):
            packet.verify(self.stage)

    def test_existing_checkout_stage_and_wrong_retained_pin_refuse(self):
        with self.assertRaises(ValueError):
            packet.prepare(self.root / "stage", self.root)
        packet.prepare(self.stage, self.root)
        with self.assertRaises(ValueError):
            packet.prepare(self.stage, self.root)
        with self.assertRaises(ValueError):
            packet.verify(self.stage, "0" * 64)

    def test_root_link_refuses_before_resolving(self):
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(ValueError):
                packet.verify(self.stage)


if __name__ == "__main__":
    unittest.main()
