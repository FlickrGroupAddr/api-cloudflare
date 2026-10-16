"""Fake provider coverage only: no credentials, HTTP, or cloud resources."""

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import existing_photo_qualification_hosted as hosted

DB = "11111111-1111-4111-8111-111111111111"


class FakeProvider:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.name = ""
        self.db_deleted = False
        self.worker_deleted = False
        self.upload = None
        self.output = Path(".")

    def call(self, method, suffix, body: Any = None, **kwargs):
        if method in {"POST", "PUT", "DELETE"}:
            marker = json.loads((self.output / hosted.RECEIPT).read_text())
            assert marker["passed"] is False
            assert marker["runName"].startswith("fga-photo-qualification-")
            assert marker["databaseName"] == marker["runName"] + "-db"
            if suffix == "/d1/database":
                assert marker["recovery"]["databaseAttempted"] is True
                assert marker["stage"] == "create_disposable_database"
            if method == "PUT":
                assert marker["recovery"]["workerAttempted"] is True
                assert marker["artifactSha2_256"]
                assert marker["uploadMetadataSecretElidedSha2_256"]
        self.calls.append((method, suffix))
        if suffix.endswith("/settings"):
            if self.upload is not None and not self.worker_deleted:
                return 200, {"success": True, "result": {}}
            return 404, {"success": False}
        if suffix == "/d1/database" and method == "POST":
            if self.failure == "create":
                raise TimeoutError("PRIVATE PROVIDER PAYLOAD")
            self.name = body["name"][:-3]
            return 200, {"success": True, "result": {"uuid": DB, "name": body["name"]}}
        if suffix.endswith("/query"):
            if self.failure == "migration":
                raise ValueError("PRIVATE SQL")
            return 200, {"success": True, "result": [{"success": True}]}
        if method == "PUT":
            self.upload = (body, kwargs)
            if self.failure == "upload":
                raise TimeoutError("PRIVATE SECRET")
            return 200, {"success": True, "result": {"id": self.name}}
        if suffix.endswith("/subdomain") and method == "POST":
            if self.failure == "enable":
                raise ValueError("PRIVATE ENDPOINT")
            return 200, {"success": True, "result": {"enabled": True, "previews_enabled": False}}
        if suffix == "/workers/subdomain":
            return 200, {"success": True, "result": {"subdomain": "synthetic"}}
        if method == "DELETE":
            if suffix.startswith("/workers/"):
                self.worker_deleted = self.failure != "cleanup"
            else:
                self.db_deleted = True
            return 200, {"success": True, "result": None}
        if suffix == "/d1/database/" + DB:
            if self.db_deleted:
                return 404, {"success": False}
            return 200, {"success": True, "result": {"name": self.name + "-db"}}
        raise AssertionError("unexpected fake call")


class HostedTests(unittest.TestCase):
    def run_fake(self, failure=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        provider = FakeProvider(failure)
        provider.output = root
        captured = io.StringIO()

        def build(private, config):
            journal = json.loads((private / "journal.json").read_text())
            self.assertEqual(journal["databaseId"], DB)
            self.assertTrue(config["workers_dev"])
            self.assertEqual(config["compatibility_date"], "2026-10-16")
            self.assertEqual(config["compatibility_flags"], hosted.FLAGS)
            self.assertEqual(
                set(config["d1_databases"][0]), {"binding", "database_name", "database_id"}
            )
            self.assertNotIn("routes", config)
            return b"synthetic bundled artifact"

        def exercise(origin, access):
            journal = json.loads(next((root / "private").glob("*/journal.json")).read_text())
            self.assertEqual(journal["workerId"], provider.name)
            self.assertGreaterEqual(len(access), 32)
            self.assertTrue(origin.endswith(".synthetic.workers.dev"))
            if failure == "matrix":
                raise ValueError("PRIVATE IMAGE")
            if failure == "edge":
                raise hosted.EdgePreparationFailure(
                    {
                        "phase": "seed_fixture",
                        "attempt": 1,
                        "reason": "unexpected_status",
                        "status": 500,
                        "bodyBytes": 7,
                        "mediaType": "html",
                        "capCategory": "within_limit",
                    }
                )
            return [{"case": case, "passed": True} for case in hosted.matrix.CASES]

        with contextlib.redirect_stdout(captured):
            code = hosted.run(
                root,
                provider=provider,
                build=build,
                exercise=exercise,
                identity=("a" * 32, "SYNTHETIC-NOT-A-CREDENTIAL"),
            )
        evidence_text = (root / hosted.RECEIPT).read_text()
        evidence = json.loads(evidence_text)
        journal = json.loads(next((root / "private").glob("*/journal.json")).read_text())
        self.assertNotIn("PRIVATE", evidence_text + captured.getvalue())
        self.assertNotIn("SYNTHETIC-NOT-A-CREDENTIAL", evidence_text + captured.getvalue())
        self.assertNotIn(DB, evidence_text + captured.getvalue())
        self.assertTrue(evidence["runName"].startswith("fga-photo-qualification-"))
        self.assertEqual(evidence["databaseName"], evidence["runName"] + "-db")
        self.assertNotIn("accountId", evidence_text)
        return code, evidence, journal, provider

    def test_success_and_exact_cleanup(self):
        code, evidence, journal, provider = self.run_fake()
        self.assertEqual(code, 0)
        self.assertTrue(evidence["passed"])
        self.assertTrue(journal["databaseDeleted"] and journal["workerDeleted"])
        assert provider.upload is not None
        uploaded = provider.upload[0]
        metadata = json.loads(uploaded.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0])
        secret = metadata["bindings"][1]["text"]
        self.assertGreaterEqual(len(secret), 32)
        metadata["bindings"][1]["text"] = "[SECRET_ELIDED]"
        self.assertEqual(
            evidence["uploadMetadataSecretElidedSha2_256"],
            hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest(),
        )
        self.assertNotIn(secret, json.dumps(evidence))
        self.assertEqual(
            [call for call in provider.calls if call[0] == "DELETE"],
            [("DELETE", "/workers/scripts/" + provider.name), ("DELETE", "/d1/database/" + DB)],
        )

    def test_ambiguous_create_not_retried_or_deleted(self):
        code, evidence, journal, provider = self.run_fake("create")
        self.assertEqual(code, 1)
        self.assertFalse(evidence["cleanupConfirmed"])
        self.assertIsNone(journal["databaseId"])
        self.assertFalse(any(method == "DELETE" for method, _ in provider.calls))
        self.assertEqual(sum(method == "POST" for method, _ in provider.calls), 1)

    def test_ambiguous_upload_cleans_only_acknowledged_database(self):
        code, evidence, journal, provider = self.run_fake("upload")
        self.assertEqual(code, 1)
        self.assertFalse(evidence["cleanupConfirmed"])
        self.assertIsNone(journal["workerId"])
        self.assertEqual(
            [call for call in provider.calls if call[0] == "DELETE"],
            [("DELETE", "/d1/database/" + DB)],
        )
        self.assertEqual(sum(method == "PUT" for method, _ in provider.calls), 1)

    def test_failures_clean_every_acknowledged_resource(self):
        for failure in ["migration", "enable", "matrix"]:
            with self.subTest(failure=failure):
                code, evidence, _, _ = self.run_fake(failure)
                self.assertEqual(code, 1)
                self.assertFalse(evidence["passed"])
                self.assertTrue(evidence["cleanupConfirmed"])

    def test_unconfirmed_cleanup_fails_receipt(self):
        code, evidence, _, _ = self.run_fake("cleanup")
        self.assertEqual(code, 1)
        self.assertFalse(evidence["passed"])
        self.assertFalse(evidence["cleanupConfirmed"])

    def test_no_credentials_means_no_provider_calls(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(hosted, "credentials", side_effect=RuntimeError("PRIVATE AUTH")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            provider = FakeProvider()
            code = hosted.run(Path(directory), provider=provider)
            self.assertEqual(code, 1)
            self.assertEqual(provider.calls, [])
            receipt = json.loads((Path(directory) / hosted.RECEIPT).read_text())
            self.assertTrue(receipt["cleanupConfirmed"])

    def test_operation_deadline_stops_before_first_provider_call(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(hosted.time, "monotonic", side_effect=[0, hosted.OPERATION_SECONDS + 1]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            provider = FakeProvider()
            result = hosted.run(
                Path(directory), provider=provider, identity=("a" * 32, "synthetic")
            )
            self.assertEqual(result, 1)
            self.assertEqual(provider.calls, [])
            receipt = json.loads((Path(directory) / hosted.RECEIPT).read_text())
            self.assertEqual(receipt["errorClass"], "TimeoutError")
            self.assertTrue(receipt["cleanupConfirmed"])

    def test_failing_preparation_reason_retained_in_receipt(self):
        _, evidence, _, _ = self.run_fake("edge")
        self.assertEqual(evidence["stage"], "edge_seed_fixture")
        self.assertEqual(
            evidence["edgePreparation"],
            {
                "phase": "seed_fixture",
                "attempt": 1,
                "reason": "unexpected_status",
                "status": 500,
                "bodyBytes": 7,
                "mediaType": "html",
                "capCategory": "within_limit",
            },
        )
        self.assertTrue(evidence["cleanupConfirmed"])

    def test_gate_and_seed_closed_diagnostics_and_no_seed_retry(self):
        ready = (404, {}, b"", 1)
        html = (500, {"content-type": "text/html; private=NEVER_RECORD"}, b"private", 1)
        cases = [
            (
                [(200, {"content-type": "arbitrary/NEVER_RECORD"}, b"private", 1)],
                "gate_readiness",
                "unexpected_status",
                200,
                7,
                "other",
                "within_limit",
                1,
            ),
            ([ready, html], "seed_fixture", "unexpected_status", 500, 7, "html", "within_limit", 2),
            (
                [ready, TimeoutError("NEVER_RECORD")],
                "seed_fixture",
                "transport_unconfirmed",
                None,
                None,
                "unavailable",
                "unobserved",
                2,
            ),
            (
                [ValueError("response_byte_limit")],
                "gate_readiness",
                "response_limit",
                None,
                262145,
                "unavailable",
                "exceeded",
                1,
            ),
        ]
        for replies, phase, reason, status, count, media, cap, calls in cases:
            with (
                self.subTest(phase=phase, reason=reason),
                patch.object(hosted.matrix, "exchange", side_effect=replies) as exchange,
                patch.object(hosted.time, "sleep"),
            ):
                observed = []
                with self.assertRaises(hosted.EdgePreparationFailure) as caught:
                    hosted.run_matrix(
                        "https://synthetic.invalid", "NEVER_RECORD", diagnostic=observed.append
                    )
                details = caught.exception.diagnostic
                self.assertEqual(details["phase"], phase)
                self.assertEqual(details["reason"], reason)
                self.assertEqual(details["status"], status)
                self.assertEqual(details["bodyBytes"], count)
                self.assertEqual(details["mediaType"], media)
                self.assertEqual(details["capCategory"], cap)
                self.assertEqual(exchange.call_count, calls)
                self.assertNotIn("NEVER_RECORD", json.dumps(observed))

    def test_readiness_transients_retry_only_safe_get(self):
        ready = (404, {}, b"", 1)
        error = (503, {"content-type": "text/html"}, b"temporary", 1)
        replies = [TimeoutError("PRIVATE"), error, ready, error]
        with (
            patch.object(hosted.matrix, "exchange", side_effect=replies) as exchange,
            patch.object(hosted.time, "sleep"),
        ):
            with self.assertRaises(hosted.EdgePreparationFailure) as caught:
                hosted.run_matrix("https://synthetic.invalid", "PRIVATE")
            self.assertEqual(caught.exception.diagnostic["phase"], "seed_fixture")
            self.assertEqual(exchange.call_count, 4)
            self.assertEqual(
                sum(call.args[1] == "/__probe/seed" for call in exchange.call_args_list), 1
            )

    def test_gate_body_failure_retained_after_bounded_readiness_attempts(self):
        with (
            patch.object(
                hosted.matrix,
                "exchange",
                return_value=(
                    404,
                    {"content-type": "text/html; private=NEVER_RECORD"},
                    b"private",
                    1,
                ),
            ) as exchange,
            patch.object(hosted.time, "sleep"),
        ):
            with self.assertRaises(hosted.EdgePreparationFailure) as caught:
                hosted.run_matrix("https://synthetic.invalid", "NEVER_RECORD")
            self.assertEqual(
                caught.exception.diagnostic,
                {
                    "phase": "gate_readiness",
                    "attempt": 10,
                    "reason": "unexpected_body",
                    "status": 404,
                    "bodyBytes": 7,
                    "mediaType": "html",
                    "capCategory": "within_limit",
                },
            )
            self.assertEqual(exchange.call_count, 10)
            self.assertTrue(
                all(call.args[1] != "/__probe/seed" for call in exchange.call_args_list)
            )


if __name__ == "__main__":
    unittest.main()
