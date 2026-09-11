"""Publication boundary tests use only synthetic private-data fixtures."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_architecture_snapshot as snapshot


class SnapshotTests(unittest.TestCase):
    def test_photo_stem_is_detected_in_raw_and_rendered_variants(self):
        document = "docs/project-log/2026-08-20-raw-archive-survey.md"
        files = {document: b"Source `PRIVATE-CAMERA-001.CR3` under `Q:\\synthetic-archive`."}
        with patch.object(snapshot.audit, "indicator_values", return_value={}):
            private = snapshot.indicators(files)
        for extension in ("CR3", "png", "JPG"):
            original = ("PRIVATE-CAMERA-001." + extension).encode()
            result = snapshot.transform("example.md", original, private)
            self.assertNotIn(b"PRIVATE-CAMERA-001", result)
            self.assertEqual(snapshot.audit.find_sensitive(result, private), [])

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            marker = destination / "keep.txt"
            marker.write_text("owner data")
            with patch.object(snapshot, "DESTINATION", destination):
                with self.assertRaises(RuntimeError):
                    snapshot.prepare()
            self.assertEqual(marker.read_text(), "owner data")

    def test_clean_contract_bytes_are_unchanged(self):
        data = b"Status: Accepted\nA normative requirement.\n"
        self.assertEqual(
            snapshot.transform(
                "docs/decisions/0050.md", data, {"private": [b"PRIVATE-CAMERA-001"]}
            ),
            data,
        )
