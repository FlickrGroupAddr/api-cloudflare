"""Meaningful guardrails for disposable resource scope and generated credential transport."""

import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from scripts import foundation_probe as proof


class FoundationControllerTests(unittest.TestCase):
    def test_credentials_are_canonical_and_use_every_random_octet(self):
        with patch.object(proof.secrets, "token_bytes", return_value=b"\xff" * 32) as source:
            token = proof.credential()
        source.assert_called_once_with(32)
        self.assertEqual(token, "-".join(["ZZZZ"] * 12 + ["ZZZG"]))
        for _ in range(50):
            self.assertRegex(
                proof.credential(),
                re.compile(
                    r"^[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){11}-"
                    r"[0-9A-HJKMNP-TV-Z]{3}[0G]$"
                ),
            )

    def test_restore_refuses_a_running_or_unconfirmed_worker(self):
        run = proof.Run(Path(tempfile.gettempdir()), {})
        with patch.object(proof.runtime, "wrangler") as command:
            for state in [{}, {"workerDeleted": True}, {"maintenanceOutsideDatabase": True}]:
                run.state = state
                with self.assertRaises(proof.ProbeError):
                    proof.restore(run, "restore", "bookmark")
            command.assert_not_called()

    def test_cleanup_cannot_target_an_arbitrary_or_production_name(self):
        run = proof.Run(
            proof.RUNS / ("rp-" + "a" * 24),
            {
                "runId": "rp-" + "a" * 24,
                "environment": "cloudflare",
                "workerName": "production",
                "databaseName": "production-db",
            },
        )
        with self.assertRaises(proof.ProbeError):
            proof.validate(run)
        run.state.update(workerName="fga-" + run.run_id, databaseName="fga-" + run.run_id + "-db")
        proof.validate(run)
        run.directory = Path(tempfile.gettempdir()) / run.run_id
        with self.assertRaises(proof.ProbeError):
            proof.validate(run)

    def test_export_literals_preserve_integer_text_and_blob_bytes(self):
        with closing(sqlite3.connect(":memory:")) as db:
            for value in [
                None,
                1.5,
                2**53 + 1,
                2**63 - 1,
                -(2**63),
                "quote'\r\n☺\x00tail",
                b"\x00\xff",
            ]:
                literal = db.execute(
                    "SELECT " + proof.sql_literal("value") + " FROM (SELECT ? AS value)", (value,)
                ).fetchone()[0]
                self.assertEqual(db.execute("SELECT " + literal).fetchone()[0], value)
        with self.assertRaises(proof.ProbeError):
            proof.sql_literal("value); DROP TABLE example;")

    def test_application_case_failure_is_never_retried_into_success(self):
        run = proof.Run(Path(tempfile.gettempdir()), {})
        with patch.object(proof, "raw_once", return_value=(500, {}, b"provider")) as raw:
            result = proof.raw(run, "/api/v001/installations/current", [])
        self.assertEqual(result[0], 500)
        raw.assert_called_once()

    def test_failed_case_stops_execution_instead_of_claiming_success(self):
        report = {"cases": []}
        with self.assertRaises(proof.ProbeError), patch("builtins.print"):
            proof.record(report, "synthetic.failure", False)
        self.assertEqual(report["cases"], [{"id": "synthetic.failure", "passed": False}])


if __name__ == "__main__":
    unittest.main()
