"""Remote engine disclosure is distinct from auth, transport and provider failures."""

from __future__ import annotations

import copy
import io
import json
import unittest
from unittest.mock import patch

from scripts import d1_engine_provenance as provenance


class EngineObservationTests(unittest.TestCase):
    def setUp(self):
        self.denied = {"success": False, "errors": [{"code": 7500, "message": provenance.DENIAL}]}
        self.disclosed = {
            "success": True,
            "result": [{"success": True, "results": [{"sqlite_version": "3.50.0"}]}],
        }
        self.instant = "2026-09-14T11:00:30Z"

    def test_known_refusal_records_null_without_raw_payload(self):
        payload = {**self.denied, "private": "must not be retained"}
        result = provenance.query_observation(400, payload, self.instant)
        self.assertIsNone(result["version"])
        self.assertEqual(result["versionDisclosure"], "provider-undisclosed")
        self.assertNotIn("must not be retained", str(result))
        self.assertEqual(result["observation"]["message"], provenance.DENIAL)

    def test_future_disclosure_records_actual_remote_version(self):
        result = provenance.query_observation(200, self.disclosed, self.instant)
        self.assertEqual(result["version"], "3.50.0")
        self.assertEqual(result["versionDisclosure"], "disclosed")
        self.assertNotIn("message", result["observation"])

    def test_auth_service_malformed_and_unclassified_errors_never_qualify(self):
        for status, payload in (
            (403, self.denied),
            (401, self.denied),
            (500, self.denied),
            (400, {"success": False, "errors": []}),
            (400, {**self.denied, "success": True}),
            (400, {"success": False, "errors": [{"code": 7500, "message": "other"}]}),
            (200, {"success": True, "result": []}),
            (200, {"success": True, "result": [None]}),
        ):
            with self.subTest(status=status, payload=payload), self.assertRaises(ValueError):
                provenance.query_observation(status, payload, self.instant)
        for version in (None, "", "production", "unknown", 3500):
            payload = copy.deepcopy(self.disclosed)
            payload["result"][0]["results"][0]["sqlite_version"] = version
            with self.assertRaises(ValueError):
                provenance.query_observation(200, payload, self.instant)

    def test_collector_reads_configured_database_and_only_fixed_queries(self):
        config = {
            "account_id": "a" * 32,
            "d1_databases": [
                {"binding": "DB", "database_id": "00000000-0000-0000-0000-000000000001"}
            ],
        }
        responses = [
            (200, {"success": True, "result": {"version": "production"}}),
            (400, self.denied),
            (200, {"success": True, "result": [{"results": [{"name": "head.sql"}]}]}),
        ]
        with patch.object(provenance, "request", side_effect=responses) as request:
            engine = provenance.collect(config, "synthetic-test-token")
        self.assertEqual(engine["migrationHead"], "head.sql")
        self.assertEqual(engine["providerGeneration"], "production")
        self.assertIsNone(engine["version"])
        calls = request.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertTrue(
            all(
                call.args[:3]
                == (
                    config["account_id"],
                    config["d1_databases"][0]["database_id"],
                    "synthetic-test-token",
                )
                for call in calls
            )
        )
        self.assertEqual(calls[1].args[3], provenance.QUERY)
        self.assertEqual(
            calls[2].args[3], "SELECT name FROM d1_migrations ORDER BY id DESC LIMIT 1"
        )
        self.assertNotIn("synthetic-test-token", str(engine))


class ResponseBudgetTests(unittest.TestCase):
    def test_restore_metadata_can_use_explicit_bounded_budget(self):
        class Reply(io.BytesIO):
            status = 200

        payload = {"success": True, "result": [{"metadata": "x" * 70000}]}
        raw = json.dumps(payload).encode()
        args = ("a" * 32, "00000000-0000-0000-0000-000000000001", "synthetic-token")
        with patch.object(provenance.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = Reply(raw)
            with self.assertRaisesRegex(ValueError, "over_budget"):
                provenance.request(*args)
            opener.return_value.open.return_value = Reply(raw)
            self.assertEqual(provenance.request(*args, max_response_bytes=131072), (200, payload))
            opener.return_value.open.return_value = Reply(b"x" * 131073)
            with self.assertRaisesRegex(ValueError, "over_budget"):
                provenance.request(*args, max_response_bytes=131072)

    def test_invalid_or_unbounded_budget_never_opens_a_connection(self):
        with patch.object(provenance.urllib.request, "build_opener") as opener:
            for value in (True, 0, 65535, 4 * 1024 * 1024 + 1):
                with self.assertRaisesRegex(ValueError, "invalid_provider_response_budget"):
                    provenance.request("a" * 32, "unused", "synthetic", max_response_bytes=value)
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
