"""Closed artifact preparation checks; these never load a native fixture."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import prepare_provider_render_qualification as packet


class ProviderRenderPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "source"
        for relative in packet.SOURCES.values():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(packet.ROOT / relative, target)

    def test_exact_actual_modules_deterministic_identity_and_pending_plan(self):
        first, second = self.base / "first", self.base / "second"
        artifact = packet.prepare(first, self.root)
        self.assertEqual(artifact, packet.prepare(second, self.root))
        self.assertEqual(packet.verify(first, str(artifact["artifactSha2_256"])), artifact)
        for name, relative in packet.SOURCES.items():
            self.assertEqual(
                (first / packet.BUNDLE / name).read_bytes(), (packet.ROOT / relative).read_bytes()
            )
        plan = json.loads((first / "run-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["consent"]["status"], "not_granted")
        self.assertEqual(plan["nativeQualification"], "unmeasured")
        self.assertEqual(plan["cases"], list(packet.CASES))
        self.assertEqual(artifact["version"], "0.0.1.2")
        self.assertEqual(artifact["hostMajor"], 15)
        self.assertEqual(artifact["sdkVersion"], "15.3")
        self.assertEqual(artifact["hostVersion"], "15.6")

    def test_native_closure_and_consent_template_are_exact_and_ungranted(self):
        destination = self.base / "native"
        artifact = packet.prepare(destination, self.root)
        self.assertEqual(len(packet.SOURCES), 24)
        for name in (
            "Native.lua",
            "NativeAssets.lua",
            "QualificationProvider.lua",
            "MetadataDefinition.lua",
        ):
            self.assertIn(name, packet.SOURCES)
        consent = json.loads((destination / "consent-template.json").read_text(encoding="utf-8"))
        self.assertEqual(consent["artifactSha2_256"], artifact["artifactSha2_256"])
        self.assertEqual(
            consent["manifestSha2_256"], packet.digest((destination / "manifest.json").read_bytes())
        )
        self.assertIsNone(consent["owner"])
        self.assertIsNone(consent["catalogPath"])
        for key in (
            "allowQualificationProvider",
            "allowSyntheticCatalogWrites",
            "allow200000001ByteScratch",
            "allowCleanup",
        ):
            self.assertIs(consent[key], False)
        self.assertEqual(packet.run_plan(artifact)["maximumRunSeconds"], 1800)

    def test_stage_refuses_repo_destination_or_existing_directory(self):
        for destination in (self.root / "stage", self.root):
            with self.assertRaises(ValueError):
                packet.prepare(destination, self.root)

    def test_missing_or_new_dependency_refuses_before_writing(self):
        source = self.root / packet.SOURCES["OrdinaryAlbumProvider.lua"]
        source.write_bytes(source.read_bytes() + b"\nlocal other=require 'UnpinnedModule'\n")
        destination = self.base / "stage"
        with self.assertRaises(ValueError):
            packet.prepare(destination, self.root)
        self.assertFalse(destination.exists())
        source.unlink()
        with self.assertRaises(FileNotFoundError):
            packet.prepare(destination, self.root)

    def test_private_unlisted_sources_are_never_copied(self):
        (self.root / "credentials.local.json").write_text("private sentinel", encoding="utf-8")
        destination = self.base / "stage"
        packet.prepare(destination, self.root)
        self.assertFalse(
            any(
                "sentinel" in path.read_text(encoding="utf-8")
                for path in destination.rglob("*")
                if path.is_file()
            )
        )

    def test_case_or_version_drift_refuses_before_writing(self):
        source = self.root / packet.SOURCES["Config.lua"]
        original = source.read_bytes()
        for old, new in ((b"selection_absent", b"unexpected_case"), (b"0.0.1.2", b"0.0.1.3")):
            source.write_bytes(original.replace(old, new))
            with self.assertRaises(ValueError):
                packet.prepare(self.base / "unwritten", self.root)
            self.assertFalse((self.base / "unwritten").exists())

    def test_info_and_package_identity_drift_refuses_before_writing(self):
        mutations = (
            ("Info.lua", b"build=2", b"build=3"),
            ("Info.lua", b"LrSdkVersion=15.3", b"LrSdkVersion=15.30"),
            ("Info.lua", b"LrSdkMinimumVersion=15.3", b"LrSdkMinimumVersion=15.0"),
            ("Info.lua", b"qualification.lrc15", b"qualification.lrc16"),
            ("Package.lua", b"version='0.0.1.2'", b"version='0.0.1.3'"),
            ("Package.lua", b"hostMajor=15", b"hostMajor=16"),
            ("Package.lua", b"hostVersion='15.6'", b"hostVersion='15.5'"),
            ("Package.lua", b"sdkVersion='15.3'", b"sdkVersion='15.0'"),
            ("Package.lua", b"schemaVersion=1", b"schemaVersion=2"),
        )
        for name, old, new in mutations:
            with self.subTest(name=name, old=old):
                source = self.root / packet.SOURCES[name]
                original = source.read_bytes()
                self.assertIn(old, original)
                source.write_bytes(original.replace(old, new))
                with self.assertRaises(ValueError):
                    packet.prepare(self.base / "unwritten", self.root)
                self.assertFalse((self.base / "unwritten").exists())
                source.write_bytes(original)

    def test_verify_refuses_tampering_extra_missing_plan_and_wrong_pin(self):
        for mutation in ("tamper", "extra", "missing", "plan", "consent", "wrong_pin"):
            with self.subTest(mutation=mutation):
                destination = self.base / mutation
                packet.prepare(destination, self.root)
                if mutation == "tamper":
                    (destination / packet.BUNDLE / "RenditionPolicy.lua").write_bytes(b"changed")
                elif mutation == "extra":
                    (destination / "unexpected.local.json").write_text("{}", encoding="utf-8")
                elif mutation == "missing":
                    (destination / packet.BUNDLE / "Run.lua").unlink()
                elif mutation == "plan":
                    (destination / "run-plan.json").write_text("{}", encoding="utf-8")
                elif mutation == "consent":
                    (destination / "consent-template.json").write_text("{}", encoding="utf-8")
                with self.assertRaises(ValueError):
                    packet.verify(destination, "0" * 64 if mutation == "wrong_pin" else None)


if __name__ == "__main__":
    unittest.main()
