"""Source-only synthetic caller tests. No provider or private inputs."""

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts import qualify_private_d1_snapshot as q
from scripts.hosted_publisher_finite_client import Response
from scripts.temporary_composition_metadata_collector import _json, canonical, digest


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 10, 18, tzinfo=UTC)
        self.token = "synthetic-token-value-only"
        self.packet = {
            "schemaVersion": 1,
            "kind": "fresh_synthetic_d1_qualification",
            "runId": "a" * 32,
            "sourceSha256": q.source_sha256(),
            "accountId": "b" * 32,
            "endpointAddress": "1.1.1.1",
            "startsAt": self.now.isoformat().replace("+00:00", "Z"),
            "expiresAt": (self.now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
            "providerTokenExpiresAt": (self.now + timedelta(hours=1))
            .isoformat()
            .replace("+00:00", "Z"),
            "credentialBinding": hashlib.sha256(self.token.encode()).hexdigest(),
            "grantEvidenceSha256": "c" * 64,
            "privateCustodySha256": "d" * 64,
            "journalPath": str(root / "private-journal.jsonl"),
            "outputPath": str(root / "out.json"),
            "readerJournalPath": str(root / "reader.jsonl"),
        }
        self.consent = {
            "approved": True,
            "decisionRef": "synthetic-owner-approval",
            "packetSha256": digest(self.packet),
        }
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.methods = []
        self.fail_reader = False
        self.fail_query = 0
        self.bad_query = 0
        self.fail_method = None
        self.bad_get = False
        self.query_count = 0

    def transport(self, request, *_args, **_kwargs):
        method = request.wire.split(b" ", 1)[0].decode()
        self.methods.append(method)
        if method == self.fail_method:
            raise TimeoutError("synthetic lost management response")
        if method == "GET":
            return Response(
                404,
                {"content-type": "application/json"},
                canonical(
                    {
                        "success": False,
                        "errors": [{"code": 10000 if self.bad_get else 7404}],
                        "messages": [],
                        "result": None,
                    }
                ),
                100,
            )
        if request.url.endswith("/query"):
            self.query_count += 1
            if (self.fail_reader and self.query_count == 9) or self.query_count == self.fail_query:
                raise TimeoutError("synthetic lost SQL response")
            body = _json(request.wire.split(b"\r\n\r\n", 1)[1])
            cursor = self.db.execute(body["sql"])
            rows = [dict(row) for row in cursor.fetchall()]
            result = [{"success": True, "results": rows, "meta": {}}]
            if self.query_count == self.bad_query:
                result = []
        elif method == "POST":
            body = _json(request.wire.split(b"\r\n\r\n", 1)[1])
            result = {"name": body["name"], "uuid": "11111111-2222-3333-4444-555555555555"}
        else:
            result = None
        encoded = canonical({"success": True, "errors": [], "messages": [], "result": result})
        return Response(
            200,
            {"content-type": "application/json"},
            encoded,
            len(encoded) + 100,
        )

    def run_qualifier(self, **kwargs):
        return q.qualify(
            self.packet,
            digest(self.packet),
            self.consent,
            lambda: self.token,
            self.packet["journalPath"],
            now=lambda: self.now,
            clock=lambda: 1.0,
            **kwargs,
        )

    def test_roundtrip_reader_and_delete_only_acknowledged_new_database(self):
        # Exercise the actual permit/collect_isolated route with network fully patched.
        with (
            patch.object(q, "_pinned_https", self.transport),
            patch("scripts.hosted_publisher_execution_provider._pinned_https", self.transport),
        ):
            result = self.run_qualifier()
        self.assertTrue(result["complete"])
        self.assertFalse(result["cleanupVerified"])
        self.assertTrue(result["providerNotFoundObserved"])
        self.assertFalse(result["productionQualified"])
        self.assertFalse(result["syntheticTransport"])
        self.assertEqual(result["requests"], 18)
        self.assertEqual(self.methods[-2:], ["DELETE", "GET"])
        self.assertIn("deleted_known_fresh_database", Path(self.packet["journalPath"]).read_text())
        self.assertIn(
            "cleanup_unconfirmed_provider_not_found", Path(self.packet["journalPath"]).read_text()
        )

    def test_missing_approval_refuses_before_credential(self):
        self.consent["approved"] = False
        called = []
        with self.assertRaises(q.QualificationError):
            q.qualify(
                self.packet,
                digest(self.packet),
                self.consent,
                lambda: called.append(True),
                self.packet["journalPath"],
                now=lambda: self.now,
                transport=self.transport,
            )
        self.assertEqual(called, [])
        self.assertEqual(self.methods, [])

    def test_lost_reader_sql_keeps_exact_database_no_delete_or_replay(self):
        self.fail_reader = True
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        journal = Path(self.packet["journalPath"]).read_text()
        self.assertIn("11111111-2222-3333-4444-555555555555", journal)
        self.assertIn("retained_no_replay", journal)
        self.assertNotIn("DELETE", self.methods)
        calls = len(self.methods)
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertEqual(len(self.methods), calls)

    def test_unknown_seed_sql_prevents_cleanup(self):
        self.fail_query = 1
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertNotIn("DELETE", self.methods)

    def test_malformed_census_sql_acknowledgment_prevents_cleanup(self):
        self.bad_query = 2
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertNotIn("DELETE", self.methods)

    def test_unknown_delete_never_replays_or_claims_cleanup(self):
        self.fail_method = "DELETE"
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertEqual(self.methods.count("DELETE"), 1)
        self.assertNotIn("GET", self.methods)
        self.assertIn("cleanup_unconfirmed_no_replay", Path(self.packet["journalPath"]).read_text())

    def test_unknown_absence_get_never_replays_cleanup(self):
        self.fail_method = "GET"
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertEqual(self.methods.count("DELETE"), 1)
        self.assertEqual(self.methods.count("GET"), 1)
        self.assertIn("cleanup_unconfirmed_no_replay", Path(self.packet["journalPath"]).read_text())

    def test_generic_not_found_is_not_database_absence_evidence(self):
        self.bad_get = True
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertIn("cleanup_unconfirmed_no_replay", Path(self.packet["journalPath"]).read_text())
        self.assertEqual(self.methods.count("DELETE"), 1)
        calls = len(self.methods)
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertEqual(len(self.methods), calls)

    def test_provider_expiry_cannot_be_relabelled_as_caller_window(self):
        self.packet["providerTokenExpiresAt"] = self.packet["startsAt"]
        self.consent["packetSha256"] = digest(self.packet)
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertEqual(self.methods, [])

    def test_unexpected_third_table_retains_all_without_omission_or_delete(self):
        self.db.execute("CREATE TABLE extra_one(v)")
        self.db.execute("CREATE TABLE extra_two(v)")
        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=self.transport)
        self.assertNotIn("DELETE", self.methods)
        self.assertIn("retained_no_replay", Path(self.packet["journalPath"]).read_text())

    def test_unknown_create_does_not_discover_or_adopt_any_resource(self):
        calls = []

        def lost(request):
            calls.append(request.url)
            raise TimeoutError("synthetic lost create acknowledgment")

        with self.assertRaises(q.QualificationError):
            self.run_qualifier(transport=lost)
        self.assertEqual(len(calls), 1)
        journal = Path(self.packet["journalPath"]).read_text()
        self.assertIn('"databaseId":null', journal)
        self.assertIn("retained_no_replay", journal)


if __name__ == "__main__":
    unittest.main()
