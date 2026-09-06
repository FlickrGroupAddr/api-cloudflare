"""Regression checks for evidence handling and narrowly scoped cleanup."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import runtime_permissions_probe as probe

EVIDENCE = probe.ROOT / "docs/evidence/runtime-permissions-local-2026-09-06.json"


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_complete_observations_reconcile(self):
        result = probe.verify_report(self.report)
        self.assertEqual(result["observedCases"], 57)
        self.assertEqual(result["runtimeProtection"], "violated")

    def test_missing_and_duplicate_cases_are_refused(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                report = copy.deepcopy(self.report)
                cases = report["d1"]["cases"]
                if duplicate:
                    cases.append(copy.deepcopy(cases[0]))
                else:
                    cases.pop()
                with self.assertRaises(probe.ProbeError):
                    probe.verify_report(report)

    def test_changed_records_cannot_be_reported_as_protected(self):
        case = next(c for c in self.report["d1"]["cases"] if c["id"] == "blocks.drop_table")
        case["forbiddenChangeObserved"] = False
        with self.assertRaises(probe.ProbeError):
            probe.verify_report(self.report)

    def test_failed_guard_control_refuses_evidence(self):
        case = next(c for c in self.report["d1"]["cases"] if c["id"] == "blocks.update")
        case["execution"] = "operation_error"
        with self.assertRaises(probe.ProbeError):
            probe.verify_report(self.report)

    def test_operation_error_stays_inconclusive(self):
        case = next(c for c in self.report["d1"]["cases"] if c["id"] == "blocks.drop_table")
        case.update(
            execution="operation_error",
            after=copy.deepcopy(case["before"]),
            forbiddenChangeObserved=False,
        )
        result = probe.verify_report(self.report)
        self.assertIn("blocks.drop_table", result["inconclusiveCases"]["d1"])
        self.assertNotIn("blocks.drop_table", result["forbiddenChanges"]["d1"])

    def test_production_claim_is_refused(self):
        self.report["productionConformance"] = True
        with self.assertRaises(probe.ProbeError):
            probe.verify_report(self.report)


class JsonReply(io.BytesIO):
    status = 200


class CleanupTests(unittest.TestCase):
    def run_state(self, directory):
        run_id = "rp-" + "a" * 24
        return probe.Run(
            Path(directory),
            {
                "runId": run_id,
                "environment": "cloudflare",
                "accountId": "b" * 32,
                "workerName": "fga-" + run_id,
                "databaseName": "fga-" + run_id + "-db",
            },
        )

    def test_unrelated_resource_names_are_refused(self):
        run = self.run_state("unused")
        run.state["workerName"] = "production-worker"
        with self.assertRaises(probe.ProbeError):
            probe.checked_resource_names(run)

    def test_cleanup_path_outside_run_root_is_refused(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(probe.ProbeError):
            probe.load_run(directory)

    def test_worker_delete_is_non_forcing_and_token_is_not_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            credential = "synthetic-test-token-not-a-real-credential"
            auth = Mock(returncode=0, stdout=json.dumps({"type": "oauth", "token": credential}))
            response = JsonReply(b'{"success": true}')
            opener = Mock()
            opener.open.return_value = response
            with (
                patch.object(probe.subprocess, "run", return_value=auth) as process,
                patch.object(probe.urllib.request, "build_opener", return_value=opener),
            ):
                self.assertEqual(probe.delete_worker_without_force(run), 200)
            request = opener.open.call_args.args[0]
            self.assertTrue(request.full_url.endswith("?force=false"))
            self.assertEqual(request.get_method(), "DELETE")
            self.assertEqual(request.get_header("Authorization"), "Bearer " + credential)
            self.assertTrue(process.call_args.kwargs["capture_output"])
            self.assertEqual(process.call_args.kwargs["env"]["WRANGLER_WRITE_LOGS"], "false")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
