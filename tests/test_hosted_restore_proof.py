"""The current-snapshot barrier rejects stale backups with lost protection."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

from scripts import current_schema_archive as archive
from scripts import hosted_restore_proof as proof


class RestoreBarrierTests(unittest.TestCase):
    def test_only_named_sql_guard_failures_count_as_guard_evidence(self):
        self.assertTrue(
            proof.QueryFailure(
                400, [{"code": 7500, "message": "block_immutable: SQLITE_CONSTRAINT"}]
            ).is_guard("block_immutable")
        )
        for status, errors in (
            (403, [{"code": 7500, "message": "block_immutable"}]),
            (500, []),
            (400, [{"code": 7500, "message": "not authorized"}]),
        ):
            self.assertFalse(proof.QueryFailure(status, errors).is_guard("block_immutable"))

    def test_real_file_restore_keeps_later_protection_and_rejects_stale_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="fga-hosted-restore-test-") as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            source = sqlite3.connect(root / "source.sqlite")
            target = sqlite3.connect(root / "target.sqlite")
            try:
                source.execute("PRAGMA foreign_keys=ON")
                target.execute("PRAGMA foreign_keys=ON")
                for path in sorted((archive.ROOT / "migrations").glob("*.sql")):
                    source.executescript(path.read_text())
                contract = archive.schema_contract()
                source.executescript("BEGIN;" + proof.SEED + "COMMIT;")
                old = archive.capture(
                    archive.query_connection(source), contract, source_stopped=True
                )
                source.executescript("BEGIN;" + proof.LATER + "COMMIT;")
                current = archive.capture(
                    archive.query_connection(source), contract, source_stopped=True
                )
                with self.assertRaisesRegex(ValueError, "current_recovery_snapshot"):
                    proof.require_current_restore(old, current)
                target.executescript("BEGIN;" + current.sql() + "COMMIT;")
                restored = archive.capture(
                    archive.query_connection(target), contract, source_stopped=True
                )
                proof.require_current_restore(restored, current)
                self.assertEqual(
                    target.execute("SELECT COUNT(*) FROM submission_blocks").fetchone()[0], 4
                )
                self.assertEqual(
                    target.execute("SELECT state FROM installations").fetchone()[0], "revoked"
                )
                self.assertEqual(
                    target.execute("SELECT revoked_at_us FROM admin_sessions").fetchone()[0], 2000
                )
            finally:
                source.close()
                target.close()


class RestoreTargetTests(unittest.TestCase):
    def test_unowned_target_is_refused_before_any_provider_request(self):
        runner = cast(Any, proof.Proof.__new__(proof.Proof))
        runner.name = "fga-restore-" + "a" * 24
        runner.owned = {runner.name + "-target": "owned-id"}
        runner.operator = Mock()
        with self.assertRaisesRegex(ValueError, "not_owned"):
            runner.restore("production-id", None)
        runner.operator.call.assert_not_called()

    def test_server_side_name_change_is_refused_before_sql(self):
        runner = cast(Any, proof.Proof.__new__(proof.Proof))
        runner.name = "fga-restore-" + "a" * 24
        runner.owned = {runner.name + "-target": "owned-id"}
        runner.operator = Mock()
        runner.operator.call.return_value = {
            "result": {"name": "fga-production", "uuid": "owned-id"}
        }
        runner.query = Mock()
        with self.assertRaisesRegex(ValueError, "identity_changed"):
            runner.restore("owned-id", None)
        runner.query.assert_not_called()

    def test_nonempty_owned_target_is_refused_before_import(self):
        runner = cast(Any, proof.Proof.__new__(proof.Proof))
        runner.name = "fga-restore-" + "a" * 24
        name = runner.name + "-target"
        runner.owned = {name: "owned-id"}
        runner.operator = Mock()
        runner.operator.call.return_value = {"result": {"name": name, "uuid": "owned-id"}}
        runner.query = Mock(return_value=[{"tbl_name": "existing_user_data"}])
        with self.assertRaisesRegex(ValueError, "not_empty"):
            runner.restore("owned-id", None)
        self.assertEqual(runner.query.call_count, 1)


if __name__ == "__main__":
    unittest.main()
