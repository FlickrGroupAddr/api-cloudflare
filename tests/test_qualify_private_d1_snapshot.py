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

    def evidence_run(self, transport=None, **kwargs):
        # Synthetic tests bypass OS-specific ACLs only; production uses the existing checks.
        with patch("scripts.hosted_publisher_execution._assert_private"):
            return self.run_qualifier(
                transport=transport or self.transport,
                evidence_path=Path(self.temp.name).resolve() / "response-evidence.jsonl",
                **kwargs,
            )

    def evidence_records(self):
        return [
            _json(line)
            for line in (Path(self.temp.name).resolve() / "response-evidence.jsonl")
            .read_bytes()
            .splitlines()
        ]

    def test_optional_evidence_preserves_successful_outbound_sequence(self):
        result = self.evidence_run()
        self.assertEqual(result["requests"], 18)
        self.assertEqual(self.methods, ["POST"] * 16 + ["DELETE", "GET"])
        records = self.evidence_records()
        self.assertEqual(len(records), 11)  # Separate isolated reader retains its own journal.
        self.assertEqual(records[-1]["status"], 404)
        self.assertEqual(records[-1]["ordinal"], 18)
        self.assertNotIn(self.token, str(records))

    def test_seed_status_and_schema_failures_captured_before_validation(self):
        import base64

        for failure in (
            Response(503, {}, b"provider unavailable", 100),
            Response(200, {"content-type": "application/json"}, b"{}", 100),
        ):
            with self.subTest(status=failure.status):

                def fail_seed(request, failure=failure):
                    if request.url.endswith("/query"):
                        self.methods.append("POST")
                        return failure
                    return self.transport(request)

                with self.assertRaises(q.QualificationError):
                    self.evidence_run(transport=fail_seed)
                records = self.evidence_records()
                self.assertEqual(len(records), 2)
                self.assertEqual(records[-1]["status"], failure.status)
                self.assertEqual(base64.b64decode(records[-1]["bodyBase64"]), failure.body)
                self.assertEqual(self.methods, ["POST", "POST"])
                Path(self.packet["journalPath"]).unlink()
                (Path(self.temp.name).resolve() / "response-evidence.jsonl").unlink()
                self.methods.clear()

    def test_evidence_refusal_before_credential_or_dispatch(self):
        called = []
        sink = Path(self.temp.name).resolve() / "existing"
        sink.write_bytes(b"unchanged")
        with (
            patch("scripts.hosted_publisher_execution._assert_private"),
            self.assertRaises(q.QualificationError),
        ):
            q.qualify(
                self.packet,
                digest(self.packet),
                self.consent,
                lambda: called.append(True),
                self.packet["journalPath"],
                now=lambda: self.now,
                transport=self.transport,
                evidence_path=sink,
            )
        self.assertEqual(sink.read_bytes(), b"unchanged")
        self.assertEqual(called, [])
        self.assertEqual(self.methods, [])

    def test_unsafe_acl_and_link_checks_refuse_before_credential(self):
        for helper in (
            "scripts.hosted_publisher_execution._assert_private",
            "scripts.hosted_publisher_operator_plan._refuse_links",
        ):
            with self.subTest(helper=helper), patch(helper, side_effect=ValueError("private")):
                with self.assertRaises(q.QualificationError):
                    self.run_qualifier(
                        transport=self.transport,
                        evidence_path=Path(self.temp.name).resolve() / "response-evidence.jsonl",
                    )
                self.assertEqual(self.methods, [])
                self.assertFalse(Path(self.packet["journalPath"]).exists())

    def test_secret_echo_and_oversized_body_never_persisted(self):
        for body in (
            self.token.encode(),
            b"Set-Cookie: secret",
            b"Authorization: other",
            b"x" * (q.MAX_EVIDENCE_BODY_BYTES + 1),
        ):
            with self.subTest(length=len(body)):

                def fail_seed(request, body=body):
                    if request.url.endswith("/query"):
                        self.methods.append("POST")
                        return Response(500, {"set-cookie": "never-save-me"}, body, len(body))
                    return self.transport(request)

                with self.assertRaises(q.QualificationError):
                    self.evidence_run(transport=fail_seed)
                self.assertEqual(len(self.evidence_records()), 1)
                self.assertEqual(self.methods, ["POST", "POST"])
                Path(self.packet["journalPath"]).unlink()
                (Path(self.temp.name).resolve() / "response-evidence.jsonl").unlink()
                self.methods.clear()

    def test_evidence_caps_refuse_before_exceeding_fixed_bounds(self):
        for cap, value in (
            ("MAX_REQUESTS", 1),
            ("MAX_EVIDENCE_RAW_BYTES", 300),
            ("MAX_EVIDENCE_FILE_BYTES", 600),
        ):
            with self.subTest(cap=cap), patch.object(q, cap, value):
                with self.assertRaises(q.QualificationError):
                    self.evidence_run()
                sink = Path(self.temp.name).resolve() / "response-evidence.jsonl"
                self.assertLessEqual(sink.stat().st_size, q.MAX_EVIDENCE_FILE_BYTES)
                records = self.evidence_records()
                self.assertLessEqual(len(records), q.MAX_REQUESTS)
                self.assertLessEqual(sum(r["bodyBytes"] for r in records), q.MAX_EVIDENCE_RAW_BYTES)
                Path(self.packet["journalPath"]).unlink()
                sink.unlink()
                self.methods.clear()

    def test_transport_exception_never_persists_exception_text(self):
        self.fail_query = 1
        with self.assertRaisesRegex(q.QualificationError, "^qualification_retained_no_replay$"):
            self.evidence_run()
        self.assertEqual(len(self.evidence_records()), 1)
        self.assertNotIn(
            b"synthetic lost",
            (Path(self.temp.name).resolve() / "response-evidence.jsonl").read_bytes(),
        )
        self.assertEqual(self.methods, ["POST", "POST"])

    def test_default_does_not_create_evidence_or_require_private_acl(self):
        with patch(
            "scripts.hosted_publisher_execution._assert_private", side_effect=AssertionError
        ):
            self.run_qualifier(transport=self.transport)
        self.assertFalse((Path(self.temp.name).resolve() / "response-evidence.jsonl").exists())

    def test_isolated_transport_with_evidence_keeps_actual_permit_route(self):
        with (
            patch("scripts.hosted_publisher_execution._assert_private"),
            patch.object(q, "_pinned_https", self.transport),
            patch("scripts.hosted_publisher_execution_provider._pinned_https", self.transport),
        ):
            result = self.run_qualifier(
                evidence_path=Path(self.temp.name).resolve() / "response-evidence.jsonl"
            )
        self.assertFalse(result["syntheticTransport"])
        self.assertEqual(result["requests"], 18)
        self.assertEqual(len(self.evidence_records()), 11)

    def test_evidence_fsync_failure_stops_without_further_request(self):
        real_fsync = q.os.fsync
        calls = []

        def fsync(descriptor):
            calls.append(descriptor)
            if len(calls) == 3:  # opened journal, dispatch intent, first evidence record
                raise OSError("synthetic private disk failure")
            return real_fsync(descriptor)

        with patch.object(q.os, "fsync", fsync), self.assertRaises(q.QualificationError):
            self.evidence_run()
        self.assertEqual(self.methods, ["POST"])
        self.assertIn("retained_no_replay", Path(self.packet["journalPath"]).read_text())

    def test_evidence_sink_change_stops_without_further_request(self):
        def tamper(request):
            response = self.transport(request)
            sink = Path(self.temp.name).resolve() / "response-evidence.jsonl"
            sink.write_bytes(b"unexpected-write")
            return response

        with self.assertRaises(q.QualificationError):
            self.evidence_run(transport=tamper)
        self.assertEqual(self.methods, ["POST"])
        self.assertEqual(
            (Path(self.temp.name).resolve() / "response-evidence.jsonl").read_bytes(),
            b"unexpected-write",
        )

    def test_response_headers_are_never_recorded(self):
        def headers(request):
            response = self.transport(request)
            return Response(
                response.status,
                {
                    **response.headers,
                    "set-cookie": "private-cookie-value",
                    "authorization": "Bearer private-header-value",
                },
                response.body,
                response.wire_bytes,
            )

        self.evidence_run(transport=headers)
        raw = (Path(self.temp.name).resolve() / "response-evidence.jsonl").read_bytes()
        self.assertNotIn(b"private-cookie-value", raw)
        self.assertNotIn(b"private-header-value", raw)

    def test_expired_response_is_fenced_before_capture_or_next_dispatch(self):
        def expired(request):
            response = self.transport(request)
            self.now += timedelta(minutes=21)
            return response

        with self.assertRaises(q.QualificationError):
            self.evidence_run(transport=expired)
        self.assertEqual(self.evidence_records(), [])
        self.assertEqual(self.methods, ["POST"])

    def test_changed_source_is_fenced_before_capture_or_next_dispatch(self):
        original = q.source_sha256
        drift = []

        def source():
            return {} if drift else original()

        def changed(request):
            response = self.transport(request)
            drift.append(True)
            return response

        with patch.object(q, "source_sha256", source), self.assertRaises(q.QualificationError):
            self.evidence_run(transport=changed)
        self.assertEqual(self.evidence_records(), [])
        self.assertEqual(self.methods, ["POST"])

    def test_escaped_authentication_and_credential_echoes_are_refused(self):
        spellings = (
            b'{"error":"' + b"".join(f"\\u{ord(c):04x}".encode() for c in self.token) + b'"}',
            rb'{"\u0061uthorization":"private-value"}',
            rb'{"coo\u006bie":"private-value"}',
            rb'{"\u005cu0061uthorization":"private-value"}',
            rb'{"error":"Bearer\tprivate-value"}',
            rb"malformed \u0061uthorization",
        )
        for body in spellings:
            with self.subTest(body_bytes=len(body)):

                def escaped(request, body=body):
                    self.methods.append("POST")
                    return Response(500, {}, body, len(body))

                with self.assertRaises(q.QualificationError):
                    self.evidence_run(transport=escaped)
                self.assertEqual(self.evidence_records(), [])
                self.assertEqual(self.methods, ["POST"])
                Path(self.packet["journalPath"]).unlink()
                (Path(self.temp.name).resolve() / "response-evidence.jsonl").unlink()
                self.methods.clear()

    def test_benign_escaped_unicode_response_is_retained_before_schema_refusal(self):
        import base64

        body = rb'{"message":"caf\u00e9"}'

        def benign(request):
            self.methods.append("POST")
            return Response(500, {}, body, len(body))

        with self.assertRaises(q.QualificationError):
            self.evidence_run(transport=benign)
        records = self.evidence_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(base64.b64decode(records[0]["bodyBase64"]), body)
        self.assertEqual(self.methods, ["POST"])


if __name__ == "__main__":
    unittest.main()
