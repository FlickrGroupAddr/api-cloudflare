"""Synthetic retained bytes; tests never invoke bundlers/provider clients."""

import json
import tempfile
import unittest
from pathlib import Path

from retained import retained_bytes, sha2_256


class RetainedTests(unittest.TestCase):
    def fixture(self, directory: Path):
        (directory / "modules").mkdir()
        module = b'export default {fetch(){return new Response("closed")}}'
        config = b'{"workers_dev":false}'
        (directory / "modules/entry.js").write_bytes(module)
        (directory / "configuration.json").write_bytes(config)
        manifest = {
            "schema": "pmb1-static-workers-artifact-v1",
            "moduleSha2_256": {"entry.js": sha2_256(module)},
            "configurationSha2_256": sha2_256(config),
            "restore": {"rebuildAllowed": False, "force": False, "actualImmutableVersion": None},
        }
        raw = json.dumps(manifest).encode()
        (directory / "artifact-manifest.json").write_bytes(raw)
        return sha2_256(raw), manifest

    def test_exact_bytes_without_rebuild(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            pin, _ = self.fixture(path)
            self.assertEqual(set(retained_bytes(path, pin)), {"entry.js", "configuration.json"})

    def test_module_and_configuration_drift_refuse(self):
        for name in ["modules/entry.js", "configuration.json"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                path = Path(temp)
                pin, _ = self.fixture(path)
                (path / name).write_bytes(b"tampered")
                with self.assertRaises(ValueError):
                    retained_bytes(path, pin)

    def test_manifest_pin_and_nonforced_semantics_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            pin, manifest = self.fixture(path)
            manifest["restore"]["force"] = True
            raw = json.dumps(manifest).encode()
            (path / "artifact-manifest.json").write_bytes(raw)
            for expected in [pin, sha2_256(raw)]:
                with self.assertRaises(ValueError):
                    retained_bytes(path, expected)

    def test_traversal_refuses_even_with_matching_manifest_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            _, manifest = self.fixture(path)
            manifest["moduleSha2_256"] = {"../outside": "0" * 64}
            raw = json.dumps(manifest).encode()
            (path / "artifact-manifest.json").write_bytes(raw)
            with self.assertRaises(ValueError):
                retained_bytes(path, sha2_256(raw))


if __name__ == "__main__":
    unittest.main()
