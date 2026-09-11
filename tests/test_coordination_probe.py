"""Guard resource scope and migration/archive behavior for the native proofs."""

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from scripts import coordination_backup as backup
from scripts import coordination_probe as proof
from tests.test_foundation_schema import migrate, seed


class CoordinationTests(unittest.TestCase):
    def test_sql_parser_keeps_trigger_bodies_intact(self):
        source = (
            "CREATE TABLE a(id INTEGER);\nCREATE TRIGGER guard BEFORE DELETE "
            "ON a BEGIN SELECT RAISE(ABORT,'guard'); END;\n"
        )
        statements = proof.statements(source)
        self.assertEqual(len(statements), 2)
        self.assertIn("RAISE(ABORT", statements[1])
        with self.assertRaises(proof.ProbeError):
            proof.statements("CREATE TABLE unfinished(")

    def test_archive_loads_history_before_allocation_triggers(self):
        with (
            closing(sqlite3.connect(":memory:")) as source,
            closing(sqlite3.connect(":memory:")) as target,
        ):
            source.execute("PRAGMA foreign_keys=ON")
            target.execute("PRAGMA foreign_keys=ON")
            for migration in proof.MIGRATIONS:
                migrate(source, migration)
            source.execute(
                "CREATE TABLE d1_migrations(id INTEGER PRIMARY KEY,name TEXT,applied_at TEXT)"
            )
            seed(source)
            with source:
                source.execute(
                    "INSERT INTO "
                    "photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind)"
                    " VALUES('binding','owner','photo','owner-nsid',1,1,'upload')"
                )
                source.execute(
                    "INSERT INTO group_partitions(partition_id,user_id,group_id) "
                    "VALUES('partition','owner','group')"
                )
                source.execute(
                    "INSERT INTO "
                    "submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id)"
                    " "
                    "VALUES('intent','binding','owner','photo','group','partition',1,'queued','request')"
                )
            objects = [
                dict(zip(["type", "name", "tbl_name", "sql"], row, strict=True))
                for row in source.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS "
                    "NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
                )
            ]
            rows = {}
            for table, order in backup.TABLES.items():
                names = [
                    row[1] for row in source.execute(f"PRAGMA table_xinfo({table})") if row[6] == 0
                ]
                expression = " || ',' || ".join(backup.sql_literal(name) for name in names)
                sql = (
                    f"SELECT 'INSERT INTO {table}({','.join(names)}) VALUES(' || "
                    f"{expression} || ');' FROM {table} ORDER BY {order}"
                )
                rows[table] = [row[0] for row in source.execute(sql)]
            text = backup.archive_text(objects, rows)
            target.executescript("BEGIN;\n" + text + "\nCOMMIT;")
            self.assertEqual(target.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                target.execute("SELECT next_enqueue_ordinal FROM group_partitions").fetchall(),
                [(2,)],
            )
            self.assertEqual(
                target.execute("SELECT COUNT(*) FROM submission_intent_events").fetchone(), (1,)
            )
            with self.assertRaises(sqlite3.IntegrityError), target:
                target.execute("DELETE FROM submission_intent_events")
            self.assertEqual(
                target.execute("SELECT COUNT(*) FROM submission_intents").fetchone(), (1,)
            )

    def test_cleanup_refuses_unrelated_namespace(self):
        run_id = "rp-" + "a" * 24
        run = proof.Run(
            proof.RUNS / run_id,
            {
                "runId": run_id,
                "environment": "cloudflare",
                "kind": "scheduling",
                "workerName": "fga-" + run_id,
                "databaseName": "fga-" + run_id + "-db",
                "workerAttempted": True,
                "namespaceId": "b" * 32,
            },
        )
        with (
            patch.object(
                proof, "namespaces", return_value=[{"class": "ProbePartitionWake", "id": "c" * 32}]
            ),
            patch.object(proof.runtime, "wrangler") as command,
            patch.object(proof.runtime, "cleanup") as cleanup,
        ):
            with self.assertRaises(proof.ProbeError):
                proof.cleanup(run)
            command.assert_not_called()
            cleanup.assert_not_called()

    def test_run_paths_cannot_escape_the_disposable_directory(self):
        run_id = "rp-" + "a" * 24
        run = proof.Run(Path("C:/unrelated") / run_id, {"runId": run_id})
        with self.assertRaises(proof.ProbeError):
            proof.validate(run)

    def test_archive_requires_stopped_source_and_unexposed_target(self):
        source = proof.Run(Path("."), {})
        target = proof.Run(Path("."), {"workerAttempted": True})
        with patch.object(backup, "query") as query:
            with self.assertRaises(proof.ProbeError):
                backup.restore_probe(source, target)
            query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
