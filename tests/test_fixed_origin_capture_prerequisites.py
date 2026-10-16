"""Offline input/refusal tests for the capture prerequisite inspector."""

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/fixed_origin_capture_prerequisites.py"
SPEC = importlib.util.spec_from_file_location("capture_prerequisites", SCRIPT)
assert SPEC and SPEC.loader
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


def capture(source: bytes = b"/api/v001/installations/current") -> dict:
    return {
        "result": {
            "id": "00000000-0000-4000-8000-000000000001",
            "main_module": "worker.js",
            "modules": [
                {
                    "name": "worker.js",
                    "content_type": "application/javascript+module",
                    "content_base64": base64.b64encode(source).decode("ascii"),
                }
            ],
        }
    }


class CapturePrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "private.json"

    def run_input(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")
        before = self.path.read_bytes()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = inspector.main([str(self.path)])
        self.assertEqual(self.path.read_bytes(), before)
        return code, out.getvalue(), err.getvalue()

    def test_missing_routes_are_not_qualification(self):
        code, out, err = self.run_input(capture())
        receipt = json.loads(out)
        self.assertEqual((code, err), (1, ""))
        self.assertTrue(receipt["findings"]["currentInstallationPath"])
        self.assertFalse(receipt["prerequisitesPresent"])
        self.assertFalse(receipt["wrapperIsolationProved"])
        self.assertFalse(receipt["hostedQualified"])
        self.assertEqual(
            receipt["moduleSha2_256"],
            hashlib.sha256(b"/api/v001/installations/current").hexdigest(),
        )
        self.assertNotIn("00000000", out)
        self.assertNotIn(str(self.path), out)

    def test_all_text_markers_still_do_not_qualify(self):
        source = "/* " + " ".join(inspector.MARKERS.values()) + " */"
        code, out, err = self.run_input(capture(source.encode()))
        receipt = json.loads(out)
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(receipt["prerequisitesPresent"])
        self.assertFalse(receipt["wrapperIsolationProved"])
        self.assertFalse(receipt["hostedQualified"])

    def test_malformed_shapes_refuse_without_payload(self):
        values = [None, [], {}, {"result": None}]
        for field, value in [
            ("id", "private-bad-id"),
            ("modules", []),
            ("modules", [None]),
            ("main_module", "other.js"),
        ]:
            item = capture()
            item["result"][field] = value
            values.append(item)
        for field, value in [
            ("name", "other.js"),
            ("content_type", "text/plain"),
            ("content_base64", "private!"),
            ("content_base64", ""),
            ("content_base64", "/w=="),
            ("content_base64", "Zh=="),
        ]:
            item = capture()
            item["result"]["modules"][0][field] = value
            values.append(item)
        item = capture()
        item["result"]["modules"] *= 2
        values.append(item)
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(self.run_input(value), (2, "", "capture_inspection_refused\n"))

    def test_size_bounds(self):
        with patch.object(inspector, "MAX_CAPTURE_BYTES", 8):
            self.assertEqual(self.run_input(capture()), (2, "", "capture_inspection_refused\n"))
        with patch.object(inspector, "MAX_MODULE_BYTES", 1):
            self.assertEqual(self.run_input(capture()), (2, "", "capture_inspection_refused\n"))

    def test_invalid_json_and_missing_file_refuse(self):
        for raw in [b"private-secret", b"\xff"]:
            self.path.write_bytes(raw)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(inspector.main([str(self.path)]), 2)
            self.assertEqual((out.getvalue(), err.getvalue()), ("", "capture_inspection_refused\n"))
        self.path.unlink()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(inspector.main([str(self.path)]), 2)
        self.assertEqual(err.getvalue(), "capture_inspection_refused\n")

    def test_single_input_no_output_path(self):
        for arguments in [[], [str(self.path), "output.json"]]:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(inspector.main(arguments), 2)
            self.assertTrue(err.getvalue().startswith("usage:"))
        self.assertFalse((Path(self.temporary.name) / "output.json").exists())


if __name__ == "__main__":
    unittest.main()
