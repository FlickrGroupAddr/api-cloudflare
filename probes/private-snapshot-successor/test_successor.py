"""Fresh public source binding and synthetic input/no-replay checks only."""

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

from scripts import prepare_private_snapshot_qualification as preparer
from scripts import qualify_private_d1_snapshot as qualifier
from scripts.temporary_composition_metadata_collector import digest
from tests import test_qualify_private_d1_snapshot as fixtures

STAGE = Path(__file__).resolve().parent / "stage"


class SuccessorTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.QualificationTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.now += timedelta(days=1)
        fixture.packet["startsAt"] = fixture.now.isoformat().replace("+00:00", "Z")
        fixture.packet["expiresAt"] = (
            (fixture.now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
        )
        fixture.packet["providerTokenExpiresAt"] = (
            (fixture.now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        )
        fixture.consent["packetSha256"] = digest(fixture.packet)
        return fixture

    def assert_refuses_before_delivery(self, fixture):
        credential, transport = Mock(), Mock()
        with (
            patch.object(qualifier, "_pinned_https", side_effect=AssertionError("offline")),
            self.assertRaises(qualifier.QualificationError),
        ):
            qualifier.qualify(
                fixture.packet,
                digest(fixture.packet),
                fixture.consent,
                credential,
                fixture.packet["journalPath"],
                now=lambda: fixture.now,
                transport=transport,
            )
        credential.assert_not_called()
        transport.assert_not_called()
        self.assertFalse(Path(fixture.packet["journalPath"]).exists())

    def test_successor_matches_current_source_and_fixed_recipe(self):
        result = cast(dict[str, Any], preparer.verify(STAGE))
        self.assertEqual(result["sourceSha256"], preparer.source_sha256())
        self.assertEqual(result["maximumRequests"], 26)
        self.assertEqual(
            [phase["maximum"] for phase in result["orderedRequestBounds"]],
            [1, 1, 11, 11, 1, 1],
        )
        for flag in (
            "liveExecutionGranted",
            "effectiveGrantsVerified",
            "privateCustodyVerified",
            "cleanupVerified",
            "productionQualified",
            "realExtractionQualified",
        ):
            self.assertIs(result[flag], False)
        packet = json.loads((STAGE / "packet-template.json").read_bytes())
        self.assertEqual(packet["sourceSha256"], qualifier.source_sha256())
        for key in set(packet) - {"schemaVersion", "kind", "sourceSha256"}:
            self.assertIsNone(packet[key])
        self.assertEqual(
            json.loads((STAGE / "consent-template.json").read_bytes()),
            {"approved": False, "decisionRef": None, "packetSha256": None},
        )

    def test_valid_synthetic_packet_reaches_injected_transport_only(self):
        fixture = self.fixture()
        with patch.object(qualifier, "_pinned_https", side_effect=AssertionError("offline")):
            result = fixture.run_qualifier(transport=fixture.transport)
        self.assertTrue(result["complete"])
        self.assertTrue(result["syntheticTransport"])
        self.assertFalse(result["cleanupVerified"])
        self.assertFalse(result["productionQualified"])
        self.assertEqual(fixture.methods[-2:], ["DELETE", "GET"])

    def test_each_public_source_drift_invalidates_successor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            for name in preparer.source_sha256():
                (root / "scripts" / name).write_bytes(
                    (preparer.ROOT / "scripts" / name).read_bytes()
                )
            preparer.verify(STAGE, root=root)
            for name in preparer.source_sha256():
                source = root / "scripts" / name
                original = source.read_bytes()
                source.write_bytes(original + b"\n# synthetic drift\n")
                with self.subTest(source=name), self.assertRaises(ValueError):
                    preparer.verify(STAGE, root=root)
                source.write_bytes(original)

    def test_grant_custody_and_credential_binding_required_before_delivery(self):
        for key in ("grantEvidenceSha256", "privateCustodySha256", "credentialBinding"):
            for value in (None, "", "not-a-digest"):
                fixture = self.fixture()
                fixture.packet[key] = value
                fixture.consent["packetSha256"] = digest(fixture.packet)
                with self.subTest(field=key, value=value):
                    self.assert_refuses_before_delivery(fixture)

    def test_changed_grant_custody_or_source_requires_exact_consent(self):
        for key in ("grantEvidenceSha256", "privateCustodySha256", "sourceSha256"):
            fixture = self.fixture()
            fixture.packet[key] = (
                {**fixture.packet[key], "private_d1_snapshot_reader.py": "0" * 64}
                if key == "sourceSha256"
                else "e" * 64
            )
            with self.subTest(field=key):
                self.assert_refuses_before_delivery(fixture)

    def test_false_or_wrong_consent_refuses_before_delivery(self):
        for update in ({"approved": False}, {"packetSha256": "0" * 64}, {"decisionRef": ""}):
            fixture = self.fixture()
            fixture.consent.update(update)
            with self.subTest(change=update):
                self.assert_refuses_before_delivery(fixture)

    def test_expired_caller_or_provider_window_refuses_before_delivery(self):
        for change in ("caller", "provider"):
            fixture = self.fixture()
            if change == "caller":
                fixture.packet["startsAt"] = (
                    (fixture.now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
                )
                fixture.packet["expiresAt"] = (
                    (fixture.now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                )
            else:
                fixture.packet["providerTokenExpiresAt"] = fixture.now.isoformat().replace(
                    "+00:00", "Z"
                )
            fixture.consent["packetSha256"] = digest(fixture.packet)
            with self.subTest(change=change):
                self.assert_refuses_before_delivery(fixture)

    def test_overlong_or_future_window_refuses_before_delivery(self):
        for change in ("overlong", "future"):
            fixture = self.fixture()
            if change == "overlong":
                fixture.packet["expiresAt"] = (
                    (fixture.now + timedelta(minutes=21)).isoformat().replace("+00:00", "Z")
                )
            else:
                fixture.packet["startsAt"] = (
                    (fixture.now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
                )
            fixture.consent["packetSha256"] = digest(fixture.packet)
            with self.subTest(change=change):
                self.assert_refuses_before_delivery(fixture)

    def test_existing_database_input_refuses_before_delivery(self):
        fixture = self.fixture()
        fixture.packet["databaseId"] = "11111111-2222-3333-4444-555555555555"
        fixture.consent["packetSha256"] = digest(fixture.packet)
        self.assert_refuses_before_delivery(fixture)

    def test_unknown_seed_census_reader_sql_retain_without_replay(self):
        for query_number in (1, 2, 9):
            fixture = self.fixture()
            fixture.fail_query = query_number
            with self.subTest(query=query_number):
                with self.assertRaises(qualifier.QualificationError):
                    fixture.run_qualifier(transport=fixture.transport)
                methods = fixture.methods.copy()
                self.assertNotIn("DELETE", methods)
                self.assertNotIn("GET", methods)
                self.assertIn(
                    "11111111-2222-3333-4444-555555555555",
                    Path(fixture.packet["journalPath"]).read_text(),
                )
                with self.assertRaises(qualifier.QualificationError):
                    fixture.run_qualifier(transport=fixture.transport)
                self.assertEqual(fixture.methods, methods)

    def test_unknown_delete_retains_exact_identity_without_replay(self):
        fixture = self.fixture()
        fixture.fail_method = "DELETE"
        with self.assertRaises(qualifier.QualificationError):
            fixture.run_qualifier(transport=fixture.transport)
        self.assertEqual(fixture.methods.count("DELETE"), 1)
        self.assertNotIn("GET", fixture.methods)
        journal = Path(fixture.packet["journalPath"]).read_text()
        self.assertIn("11111111-2222-3333-4444-555555555555", journal)
        self.assertIn("cleanup_unconfirmed_no_replay", journal)
        methods = fixture.methods.copy()
        with self.assertRaises(qualifier.QualificationError):
            fixture.run_qualifier(transport=fixture.transport)
        self.assertEqual(fixture.methods, methods)


if __name__ == "__main__":
    unittest.main()
