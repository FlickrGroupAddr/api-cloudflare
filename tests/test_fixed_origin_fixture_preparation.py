"""Offline preparation refusal/provenance tests; no Git, Node or network calls."""

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "probes/fixed-origin-isolation/prepare_fixture.py"
SPEC = importlib.util.spec_from_file_location("fixture_preparation", SCRIPT)
assert SPEC and SPEC.loader
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


class FixturePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        (self.repository / "package-lock.json").write_bytes(b"pinned lock")
        self.private = self.root / "private-evidence"
        self.private.mkdir()
        self.output = self.private / "fresh"
        self.capture = self.private / "input.json"
        self.source = b"/api/v001/installations/current"
        self.capture.write_text(
            json.dumps(
                {
                    "result": {
                        "id": "00000000-0000-4000-8000-000000000001",
                        "main_module": "worker.js",
                        "modules": [
                            {
                                "name": "worker.js",
                                "content_type": "application/javascript+module",
                                "content_base64": base64.b64encode(self.source).decode("ascii"),
                            }
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )

    def run_preparation(self, output=None):
        arguments = [
            str(SCRIPT),
            str(self.repository),
            str(self.capture),
            str(output or self.output),
            "node.exe",
        ]
        with patch.object(sys, "argv", arguments), contextlib.redirect_stdout(io.StringIO()):
            preparation.main()

    def test_wrong_capture_digest_stops_before_output_or_process(self):
        with patch.object(preparation.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "unexpected_capture"):
                self.run_preparation()
            run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_output_must_be_private_and_outside_repository(self):
        for output in [self.root / "public", self.repository / "private-evidence/fresh"]:
            with self.subTest(path=output), patch.object(preparation.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "private_output_required"):
                    self.run_preparation(output)
                run.assert_not_called()

    def test_no_overwrite_existing_evidence(self):
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_text("preserve")
        with patch.object(preparation, "CAPTURE_DIGEST", hashlib.sha256(self.source).hexdigest()):
            with patch.object(preparation.subprocess, "run") as run:
                with self.assertRaises(FileExistsError):
                    self.run_preparation()
                run.assert_not_called()
        self.assertEqual(sentinel.read_text(), "preserve")

    def test_pinned_archive_command_and_manifest(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as files:
            files.writestr("src/worker.ts", b"pinned fixture")
            files.writestr("package-lock.json", b"pinned lock")
        original = self.capture.read_bytes()

        def process(command, **_kwargs):
            if command[0] == "git":
                self.assertIn(preparation.CANDIDATE, command)
                self.assertIn("archive", command)
                self.assertNotIn("HEAD", command)
                return SimpleNamespace(stdout=archive.getvalue())
            self.assertEqual(command[0], "node.exe")
            (self.output / "candidate.mjs").write_bytes(b"bundled fixture")
            return SimpleNamespace(stdout=b"")

        with patch.object(preparation, "CAPTURE_DIGEST", hashlib.sha256(self.source).hexdigest()):
            with patch.object(preparation.subprocess, "run", side_effect=process):
                self.run_preparation()
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["candidateCommit"], preparation.CANDIDATE)
        self.assertEqual((self.output / "captured.mjs").read_bytes(), self.source)
        self.assertEqual(self.capture.read_bytes(), original)
        self.assertEqual(
            manifest["candidateSourceFiles"],
            {
                "src/worker.ts": hashlib.sha256(b"pinned fixture").hexdigest(),
                "package-lock.json": hashlib.sha256(b"pinned lock").hexdigest(),
            },
        )

    def test_archive_traversal_refused(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as files:
            files.writestr("../escape", b"must not escape")
        with patch.object(preparation, "CAPTURE_DIGEST", hashlib.sha256(self.source).hexdigest()):
            with patch.object(
                preparation.subprocess,
                "run",
                return_value=SimpleNamespace(stdout=archive.getvalue()),
            ):
                with self.assertRaisesRegex(ValueError, "archive_path"):
                    self.run_preparation()
        self.assertFalse((self.output / "escape").exists())


if __name__ == "__main__":
    unittest.main()
