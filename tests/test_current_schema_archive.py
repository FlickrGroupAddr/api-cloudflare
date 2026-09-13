"""Round-trip the current production schema in real, independent SQLite files."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import current_schema_archive as archive


class CurrentArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="fga-current-restore-")
        self.addCleanup(self.directory.cleanup)
        self.source = sqlite3.connect(Path(self.directory.name) / "source.sqlite")
        self.target = sqlite3.connect(Path(self.directory.name) / "target.sqlite")
        self.addCleanup(self.source.close)
        self.addCleanup(self.target.close)
        for connection in (self.source, self.target):
            connection.execute("PRAGMA foreign_keys=ON")
        for file in sorted((archive.ROOT / "migrations").glob("*.sql")):
            self.source.executescript(file.read_text(encoding="utf-8"))
        self.contract = archive.schema_contract()
        self.query = archive.query_connection(self.source)
        self.source.executescript("""
            INSERT INTO fga_users VALUES('owner');
            INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id)
              VALUES('photo','group','delivery_uncertain','attempt');
            INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason)
              VALUES('event','owner','archive.test','request','succeeded','synthetic');
            INSERT INTO flickr_links VALUES('owner','synthetic-owner',1,'paused');
            INSERT INTO flickr_connection_state(user_id,state,local_state)
              VALUES('owner','unlinked','absent');
            INSERT INTO flickr_write_gates VALUES('deployment','*',0,1),('user','owner',0,1);
        """)
        self.source.execute(
            "INSERT INTO admin_principals VALUES(?,?,?,?)",
            ("owner", "https://accounts.google.com", "synthetic-subject", 2),
        )
        self.source.execute(
            "INSERT INTO admin_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "session",
                "a" * 64,
                "owner",
                "b" * 43,
                1000,
                1000,
                86400001000,
                1000,
                2000,
                "owner_revoked",
                2,
                "correlation",
            ),
        )
        self.source.execute(
            "INSERT INTO google_login_transactions VALUES(?,?,?,?,?,?,?,?)",
            ("c" * 64, "d" * 64, "reauthentication", "session", "owner", 1000, 300001000, 2000),
        )
        self.source.execute(
            "INSERT INTO auth_cost_events VALUES(?,?,?,?,?)", ("cost", "e" * 64, "login", 1000, 1)
        )
        self.source.execute("INSERT INTO auth_source_buckets VALUES(?,?,?)", ("e" * 64, 0.5, 1000))
        self.source.execute(
            "INSERT INTO flickr_lifecycle_operations(operation_id,user_id,kind,phase,"
            "generation,retiring_generation,expected_revision) VALUES(?,?,?,?,?,?,?)",
            ("operation", "owner", "retire", "repair_required", "retirement", "old-generation", 1),
        )
        self.source.execute(
            "INSERT INTO flickr_oauth_transactions(transaction_id,user_id,session_id,state_digest,"
            "slot,generation,expected_revision,phase,created_at_us,expires_at_us) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "oauth",
                "owner",
                "session",
                "f" * 64,
                0,
                "temporary-generation",
                1,
                "retiring",
                1000,
                300001000,
            ),
        )
        self.source.execute(
            "INSERT INTO deployment_conformance("
            "artifact_sha2_256,contract_sha2_256,evidence_sha2_256) "
            "VALUES(?,?,?)",
            ("a" * 64, "b" * 64, "c" * 64),
        )
        self.source.commit()

    def test_current_schema_round_trip_preserves_every_table_and_guard(self):
        saved = archive.capture(self.query, self.contract, source_stopped=True)
        self.assertEqual(set(saved.rows), set(self.contract.tables))
        self.assertGreater(len(saved.rows), 19)
        self.assertIn("flickr_connection_state", saved.rows)
        self.assertEqual(len(saved.rows["admin_sessions"]), 1)
        self.assertEqual(len(saved.rows["flickr_oauth_transactions"]), 1)
        self.assertEqual(len(saved.rows["flickr_lifecycle_operations"]), 1)
        self.target.executescript("BEGIN;\n" + saved.sql() + "\nCOMMIT;")
        result = archive.verify_restored(
            archive.query_connection(self.target), saved, self.contract
        )
        self.assertEqual(result["tableCount"], len(self.contract.tables))
        for table in ("submission_blocks", "audit_events"):
            for statement in (
                f"DELETE FROM {table}",
                f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.target.execute(statement)
                self.target.rollback()
        self.assertEqual(
            self.target.execute("SELECT first_reason FROM submission_blocks").fetchone(),
            ("delivery_uncertain",),
        )

    def test_unstopped_source_and_schema_drift_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "stopped"):
            archive.capture(self.query, self.contract, source_stopped=False)
        self.source.execute("CREATE TABLE unarchived_fact(id INTEGER PRIMARY KEY)")
        with self.assertRaisesRegex(ValueError, "Schema drift"):
            archive.capture(self.query, self.contract, source_stopped=True)
        self.source.execute("DROP TABLE unarchived_fact")
        self.source.execute("DROP TRIGGER block_no_delete")
        with self.assertRaisesRegex(ValueError, "Schema drift"):
            archive.capture(self.query, self.contract, source_stopped=True)

    def test_exact_integer_and_nul_text_round_trip(self):
        self.source.execute("UPDATE flickr_write_gates SET revision=?", (9223372036854775807,))
        self.source.execute("INSERT INTO fga_users VALUES(?)", ("nul\0owner'",))
        self.source.commit()
        saved = archive.capture(self.query, self.contract, source_stopped=True)
        self.target.executescript("BEGIN;\n" + saved.sql() + "\nCOMMIT;")
        archive.verify_restored(archive.query_connection(self.target), saved, self.contract)
        self.assertEqual(
            self.target.execute("SELECT MAX(revision) FROM flickr_write_gates").fetchone(),
            (9223372036854775807,),
        )
        self.assertEqual(
            self.target.execute(
                "SELECT COUNT(*) FROM fga_users WHERE user_id=?", ("nul\0owner'",)
            ).fetchone(),
            (1,),
        )

    def test_restored_change_is_detected(self):
        saved = archive.capture(self.query, self.contract, source_stopped=True)
        self.target.executescript("BEGIN;\n" + saved.sql() + "\nCOMMIT;")
        self.target.execute("UPDATE flickr_write_gates SET revision=2")
        with self.assertRaisesRegex(ValueError, "do not match"):
            archive.verify_restored(archive.query_connection(self.target), saved, self.contract)


class DispatchMigrationTests(unittest.TestCase):
    def test_migration_and_rollback_preserve_existing_resolution_and_block_evidence(self):
        with tempfile.TemporaryDirectory(prefix="fga-dispatch-migration-") as directory:
            connection = sqlite3.connect(Path(directory) / "db.sqlite")
            try:
                connection.execute("PRAGMA foreign_keys=ON")
                files = sorted((archive.ROOT / "migrations").glob("*.sql"))
                for file in files:
                    if file.name < "0009_dispatch_policy.sql":
                        connection.executescript(file.read_text(encoding="utf-8"))
                connection.executescript("""
                    INSERT INTO fga_users VALUES('owner');
                    INSERT INTO flickr_links VALUES('owner','nsid',1,'linked');
                    INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,
                      link_revision,verification_revision,source_kind)
                      VALUES('binding','owner','photo','nsid',1,1,'upload');
                    INSERT INTO group_partitions(partition_id,user_id,group_id)
                      VALUES('partition','owner','group');
                    INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,
                      group_id,partition_id,enqueue_ordinal,state,created_request_id,terminal_at_us)
                      VALUES('intent','binding','owner','photo','group','partition',1,
                      'moderation_submitted','request',1234567);
                    INSERT INTO submission_attempts(attempt_id,intent_id,ordinal,lease_id,
                      lease_generation,deployment_revision,user_revision,link_revision)
                      VALUES('attempt','intent',1,'lease',1,1,1,1);
                    INSERT INTO attempt_resolutions(attempt_id,outcome,reason,completed_at_us)
                      VALUES('attempt','moderation_submitted','flickr_code_6',1234567);
                    INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id)
                      VALUES('photo','group','flickr_code_6','attempt');
                """)
                before = connection.execute("SELECT * FROM attempt_resolutions").fetchall()
                blocks = connection.execute("SELECT * FROM submission_blocks").fetchall()
                schema = connection.execute(
                    "SELECT name,sql FROM sqlite_master "
                    "WHERE tbl_name='attempt_resolutions' ORDER BY name"
                ).fetchall()
                migration = (archive.ROOT / "migrations/0009_dispatch_policy.sql").read_text(
                    encoding="utf-8"
                )
                with self.assertRaises(sqlite3.OperationalError):
                    connection.executescript(
                        "BEGIN;\n" + migration + "\nSELECT missing_column;COMMIT;"
                    )
                connection.rollback()
                self.assertEqual(
                    connection.execute("SELECT * FROM attempt_resolutions").fetchall(), before
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT name,sql FROM sqlite_master "
                        "WHERE tbl_name='attempt_resolutions' ORDER BY name"
                    ).fetchall(),
                    schema,
                )
                connection.executescript("BEGIN;\n" + migration + "\nCOMMIT;")
                self.assertEqual(
                    connection.execute(
                        "SELECT attempt_id,outcome,reason,completed_at_us FROM attempt_resolutions"
                    ).fetchall(),
                    before,
                )
                self.assertEqual(
                    connection.execute("SELECT * FROM submission_blocks").fetchall(), blocks
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("DELETE FROM attempt_resolutions")
                connection.rollback()
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
