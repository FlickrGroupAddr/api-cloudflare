"""Publication audit output must not disclose the values it finds."""

import unittest
from unittest.mock import patch

from scripts import audit_architecture_publication as audit


class PublicationAuditTests(unittest.TestCase):
    def test_escaped_and_case_changed_paths_are_redacted(self):
        indicators = {"catalog_root": [b"Q:\\private\\photos"]}
        data = b"safe\nQ:\\\\PRIVATE\\\\photos\nQ:\\private\\photos"
        self.assertEqual(
            audit.find_sensitive(data, indicators),
            [
                {"rule": "catalog_root", "line": 2},
                {"rule": "catalog_root", "line": 3},
            ],
        )
        safe = audit.safe_path(data.decode(), indicators)
        self.assertTrue(safe.startswith("[path SHA2-256:"))
        self.assertNotIn("photos", safe)

    def test_safe_location_survives_without_matched_value(self):
        self.assertEqual(
            audit.safe_path("docs/report.md", {"private": [b"secret"]}), "docs/report.md"
        )
        self.assertEqual(
            audit.find_sensitive(b"secret secret", {"private": [b"secret"]}),
            [{"rule": "private", "line": 1}],
        )

    def test_repository_boundary_rejects_other_destination(self):
        with patch.object(audit, "command") as command:
            with self.assertRaises(RuntimeError):
                audit.github("repos/another/repository")
            command.assert_not_called()
