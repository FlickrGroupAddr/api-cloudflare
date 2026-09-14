"""Remote engine disclosure is distinct from auth, transport and provider failures."""

from __future__ import annotations

import copy
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


if __name__ == "__main__":
    unittest.main()
