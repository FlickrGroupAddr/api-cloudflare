"""Cleanup must distinguish missing resources from denied or uncertain reads."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import secret_store_probe as probe


class CleanupTests(unittest.TestCase):
    def run_state(self, directory):
        version = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        name = "fga-proof/" + "a" * 24 + "/" + version
        run = probe.Run(
            Path(directory),
            {
                "runId": "rp-" + "a" * 24,
                "awsAccount": "123456789012",
                "region": "us-east-2",
                "profile": "fga-proof",
                "generations": [{"name": name, "version": version, "attempted": True}],
            },
        )
        probe.Lifecycle(Path(directory) / "lifecycle.sqlite").plan(name, version)
        return run

    def test_denied_description_does_not_confirm_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            with patch.object(probe, "aws", return_value=(None, "AccessDeniedException")):
                with self.assertRaises(probe.ProbeError):
                    probe.cleanup(run)
            self.assertFalse(run.state["cleanupConfirmed"])

    def test_mismatched_generation_never_requests_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            with patch.object(probe, "aws", return_value=({"Name": "unrelated"}, None)) as aws:
                with self.assertRaises(probe.ProbeError):
                    probe.cleanup(run)
            self.assertEqual(aws.call_count, 1)
            self.assertFalse(run.state["cleanupConfirmed"])

    def test_both_reads_must_confirm_absence_repeatedly(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            with (
                patch.object(probe, "aws", return_value=(None, "ResourceNotFoundException")) as aws,
                patch.object(probe.time, "sleep"),
            ):
                probe.cleanup(run)
            self.assertEqual(aws.call_count, 6)
            self.assertTrue(run.state["cleanupConfirmed"])

    def test_worker_cleanup_attempted_after_aws_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            run.state.update(workerAttempted=True, workerName="fga-" + run.run_id)
            with (
                patch.object(probe, "aws", return_value=(None, "AccessDeniedException")),
                patch.object(probe, "delete_worker_without_force") as delete,
                patch.object(probe, "wrangler"),
                patch.object(probe, "missing_worker", return_value=True),
            ):
                with self.assertRaises(probe.ProbeError):
                    probe.cleanup(run)
            delete.assert_called_once_with(run)
            self.assertTrue(run.state["workerDeleted"])
            self.assertFalse(run.state["cleanupConfirmed"])

    def test_untrusted_worker_error_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            with patch.object(probe, "call", return_value=(502, {"error": "private-payload"})):
                with self.assertRaises(probe.ProbeError):
                    probe.successful(run, "synthetic-token", "create", 0)
            self.assertEqual(run.state["failedStep"]["error"], "unexpected")
            self.assertNotIn("private-payload", (Path(directory) / "manifest.json").read_text())

    def test_failed_deployment_retains_failure_and_source_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_state(directory)
            with (
                patch.object(probe, "deploy", side_effect=probe.ProbeError("deployment_failed")),
                patch.object(probe, "cleanup") as cleanup,
            ):
                with self.assertRaises(probe.ProbeError):
                    probe.execute(run)
            report = probe.json.loads((Path(directory) / "report.json").read_text())
            self.assertFalse(report["passed"])
            self.assertFalse(report["cleanupConfirmed"])
            self.assertEqual(report["failure"], "deployment_failed")
            self.assertIn("probes/secrets/worker.ts", report["sourceHashes"])
            cleanup.assert_called_once_with(run)


if __name__ == "__main__":
    unittest.main()
