"""Synthetic source tests only. Never opens a database file or calls a provider."""

import hashlib
import json
import os
import sqlite3
import unittest
from pathlib import Path

from control import (
    HERE,
    MAX_GENERATION,
    Refusal,
    close,
    confirm_readback,
    generation_text,
    parse_readback,
    read_sql,
    reopen,
    require_one_change,
    schema_pins,
)
from fixture import atomic_fixture_batch, bootstrap_fixture, guard_sql, schema_rows, source_database

PUBLIC_ROOT = Path(os.environ.get("PMB1_PUBLIC_REPOSITORY", str(HERE.parents[1])))
MIGRATIONS = PUBLIC_ROOT / "migrations"
MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))


def readback(db: sqlite3.Connection) -> list[dict[str, object]]:
    cursor = db.execute(read_sql("readback"))
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


class CandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = source_database(MIGRATIONS)
        bootstrap_fixture(self.db)
        self.addCleanup(self.db.close)

    def transition(self, operation: str, generation: str) -> None:
        intent = close(generation) if operation == "close" else reopen(generation)
        affected = self.db.execute(intent.sql, {"expected_generation": generation}).rowcount
        require_one_change(affected)
        confirm_readback(intent, readback(self.db), schema_rows(self.db))

    def open(self) -> None:
        self.transition("reopen", "1")

    def test_exact_source_and_candidate_schema_pins(self) -> None:
        actual = [
            {"name": path.name, "sha2_256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(MIGRATIONS.glob("*.sql"))
        ]
        self.assertEqual(actual, MANIFEST["migrations"])
        self.assertEqual(schema_pins(schema_rows(self.db)), MANIFEST["candidate_schema"])
        tables = self.db.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")
        self.assertEqual(
            [row[0] for row in tables],
            sorted([*MANIFEST["ordinary_tables"], "maintenance_control"]),
        )
        self.assertEqual(len(MANIFEST["ordinary_tables"]), 62)
        self.assertEqual(len(MANIFEST["guard_triggers"]), 186)
        self.assertEqual(
            (HERE / "guards.sql").read_text(encoding="utf-8"),
            guard_sql(MANIFEST["ordinary_tables"]),
        )

    def test_closed_bootstrap_rowid_and_duplicate_bootstrap_refuses(self) -> None:
        self.assertEqual(parse_readback(readback(self.db)).generation, "1")
        self.assertEqual(parse_readback(readback(self.db)).state, "closed")
        before = self.db.iterdump()
        snapshot = list(before)
        with self.assertRaisesRegex(ValueError, "unexpected_source_schema"):
            bootstrap_fixture(self.db)
        self.assertEqual(list(self.db.iterdump()), snapshot)

    def test_atomic_bootstrap_late_ddl_failure_rolls_back(self) -> None:
        db = source_database(MIGRATIONS)
        self.addCleanup(db.close)
        before = schema_rows(db)
        # Deliberately collide after control creation; no partial control/guards.
        with self.assertRaises(sqlite3.Error):
            try:
                db.executescript(
                    "BEGIN;"
                    + read_sql("bootstrap")
                    + (HERE / "guards.sql").read_text(encoding="utf-8")
                    + ";CREATE TABLE fga_users(x);COMMIT;"
                )
            except sqlite3.Error:
                db.rollback()
                raise
        self.assertEqual(schema_rows(db), before)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM fga_users").fetchone()[0], 0)

    def test_control_insert_delete_key_and_illegal_transition_refuse(self) -> None:
        for sql in (
            "INSERT OR REPLACE INTO maintenance_control VALUES(1,2,'open')",
            "INSERT OR IGNORE INTO maintenance_control VALUES(1,2,'open')",
            "DELETE FROM maintenance_control",
            "UPDATE maintenance_control SET singleton_id=2",
            "UPDATE maintenance_control SET rowid=2",
            "UPDATE maintenance_control SET generation=2",
            "UPDATE maintenance_control SET state='open'",
            "UPDATE maintenance_control SET generation=3,state='open'",
            "UPDATE maintenance_control SET generation=0,state='open'",
            "UPDATE maintenance_control SET generation=2.5,state='open'",
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(sql)
        self.assertEqual(parse_readback(readback(self.db)).generation, "1")

    def test_duplicate_stale_and_zero_changes_are_refusal(self) -> None:
        for operation in (close("1"), reopen("2")):
            require = self.db.execute(
                operation.sql, {"expected_generation": operation.expected_generation}
            ).rowcount
            with self.assertRaises(Refusal):
                require_one_change(require)
        self.open()
        self.transition("close", "2")
        self.assertEqual(self.db.execute(close("2").sql, {"expected_generation": "2"}).rowcount, 0)
        self.assertEqual(self.db.execute(close("3").sql, {"expected_generation": "3"}).rowcount, 0)
        for value in (0, 2, -1, True, 1.0, "1", None):
            with self.subTest(value=value), self.assertRaises(Refusal):
                require_one_change(value)

    def test_noncanonical_generation_input_refuses_before_dispatch(self) -> None:
        for value in (
            1,
            True,
            1.0,
            None,
            "",
            "0",
            "01",
            "+1",
            " 1",
            "1 ",
            "1.0",
            "1e0",
            "١",
            "１",
            "9223372036854775808",
            "9" * 100,
        ):
            with self.subTest(value=value), self.assertRaises(Refusal):
                generation_text(value)
        for value in ("1", "9007199254740993", str(MAX_GENERATION)):
            self.assertEqual(generation_text(value), value)

    def test_sql_itself_refuses_nontext_and_noncanonical_binding(self) -> None:
        for value in (1, 1.0, None, b"1", "01", "+1", "1.0", "1e0"):
            with self.subTest(value=value):
                self.assertEqual(
                    self.db.execute(read_sql("reopen"), {"expected_generation": value}).rowcount, 0
                )
        self.assertEqual(parse_readback(readback(self.db)).state, "closed")

    def test_int64_above_javascript_safe_integer_and_exhaustion(self) -> None:
        # Corruption/seed fixture only: drop special guard, set exact synthetic
        # boundary, reinstall exact definition. No candidate reset operation.
        trigger = self.db.execute(
            "SELECT sql FROM sqlite_schema WHERE name='maintenance_control_transition'"
        ).fetchone()[0]
        self.db.execute("DROP TRIGGER maintenance_control_transition")
        self.db.execute("UPDATE maintenance_control SET generation=?", (9007199254740993,))
        self.db.execute(trigger)
        self.transition("reopen", "9007199254740993")
        self.assertEqual(parse_readback(readback(self.db)).generation, "9007199254740994")
        self.db.execute("DROP TRIGGER maintenance_control_transition")
        self.db.execute(
            "UPDATE maintenance_control SET generation=?,state='open'", (MAX_GENERATION - 1,)
        )
        self.db.execute(trigger)
        self.transition("close", str(MAX_GENERATION - 1))
        row = parse_readback(readback(self.db))
        self.assertEqual((row.generation, row.state), (str(MAX_GENERATION), "closed"))
        with self.assertRaises(Refusal):
            reopen(str(MAX_GENERATION))
        self.assertEqual(
            self.db.execute(
                read_sql("reopen"), {"expected_generation": str(MAX_GENERATION)}
            ).rowcount,
            0,
        )

    def test_each_ordinary_table_has_closed_insert_refusal(self) -> None:
        before = list(self.db.iterdump())
        for table in MANIFEST["ordinary_tables"]:
            with self.subTest(table=table), self.assertRaises(sqlite3.Error):
                self.db.execute(f'INSERT INTO "{table}" DEFAULT VALUES')
        self.assertEqual(list(self.db.iterdump()), before)

    def test_closed_direct_upsert_replace_and_ignore_all_refuse(self) -> None:
        self.open()
        self.db.execute("INSERT INTO fga_users VALUES('synthetic-user')")
        self.transition("close", "2")
        for recursive in (0, 1):
            self.db.execute(f"PRAGMA recursive_triggers={recursive}")
            for sql in (
                "INSERT INTO fga_users VALUES('next-user')",
                "UPDATE fga_users SET user_id='changed'",
                "DELETE FROM fga_users",
                "INSERT INTO fga_users VALUES('synthetic-user') ON CONFLICT(user_id) "
                "DO UPDATE SET user_id=excluded.user_id",
                "INSERT INTO fga_users VALUES('synthetic-user') ON CONFLICT DO NOTHING",
                "INSERT OR IGNORE INTO fga_users VALUES('synthetic-user')",
                "INSERT OR REPLACE INTO fga_users VALUES('synthetic-user')",
                "REPLACE INTO fga_users VALUES('synthetic-user')",
                "UPDATE OR IGNORE fga_users SET user_id='changed'",
            ):
                with (
                    self.subTest(recursive=recursive, sql=sql),
                    self.assertRaisesRegex(sqlite3.IntegrityError, "maintenance_closed"),
                ):
                    self.db.execute(sql)
        self.assertEqual(
            self.db.execute("SELECT user_id FROM fga_users").fetchall(), [("synthetic-user",)]
        )

    def test_existing_suppression_append_only_and_domain_guards_still_refuse_open(self) -> None:
        self.open()
        self.db.execute(
            "INSERT INTO submission_blocks(photo_id,group_id,first_reason,"
            "source_attempt_id) VALUES('synthetic-photo','synthetic-group',"
            "'flickr_code_6','synthetic-attempt')"
        )
        self.db.execute(
            "INSERT INTO audit_events(event_id,action,request_correlation_id,"
            "outcome,reason) VALUES('synthetic-event','synthetic','synthetic',"
            "'succeeded','synthetic')"
        )
        for table, key, value in (
            ("submission_blocks", "photo_id", "synthetic-photo"),
            ("audit_events", "event_id", "synthetic-event"),
        ):
            for sql in (
                f'UPDATE "{table}" SET "{key}"=?',
                f'DELETE FROM "{table}" WHERE "{key}"=?',
            ):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                    self.db.execute(sql, (value,))
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(f'INSERT OR REPLACE INTO "{table}" SELECT * FROM "{table}"')
        # Existing domain CHECK and FK constraints remain effective when open.
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO submission_blocks VALUES('p','g','invalid','a','t')")

    def test_missing_extra_malformed_null_and_unreadable_authority_fail_closed(self) -> None:
        for row_sql in (
            "",
            "INSERT INTO maintenance_control VALUES(1,1,'open');"
            "INSERT INTO maintenance_control VALUES(2,1,'open');",
            "INSERT INTO maintenance_control VALUES(NULL,1,'open');",
            "INSERT INTO maintenance_control VALUES(1,NULL,'open');",
            "INSERT INTO maintenance_control VALUES(1,1,NULL);",
            "INSERT INTO maintenance_control VALUES(1,1,'unknown');",
            "INSERT INTO maintenance_control VALUES(1,0,'open');",
            "INSERT INTO maintenance_control VALUES(1,1.5,'open');",
            "INSERT INTO maintenance_control VALUES(1,'1','open');",
        ):
            with self.subTest(row_sql=row_sql):
                db = sqlite3.connect(":memory:", isolation_level=None)
                try:
                    # Deliberately malformed relation, no affinity/constraints.
                    db.executescript(
                        "CREATE TABLE maintenance_control(singleton_id,generation,state);"
                        "CREATE TABLE work(id);" + guard_sql(["work"]) + row_sql
                    )
                    with self.assertRaisesRegex(sqlite3.IntegrityError, "maintenance_closed"):
                        db.execute("INSERT INTO work VALUES(1)")
                    for operation in ("close", "reopen"):
                        self.assertEqual(
                            db.execute(read_sql(operation), {"expected_generation": "1"}).rowcount,
                            0,
                        )
                finally:
                    db.close()
        self.db.execute("DROP TABLE maintenance_control")
        with self.assertRaises(sqlite3.OperationalError):
            self.db.execute("INSERT INTO fga_users VALUES('synthetic')")

    def test_zero_row_operations_do_not_prove_admission(self) -> None:
        self.db.execute("UPDATE fga_users SET user_id='unused' WHERE 0")
        self.db.execute("DELETE FROM fga_users WHERE 0")
        self.db.execute("INSERT INTO fga_users SELECT 'unused' WHERE 0")
        self.assertEqual(parse_readback(readback(self.db)).state, "closed")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM fga_users").fetchone()[0], 0)

    def test_abort_is_statement_only_but_atomic_wrapper_rolls_back_prior_work(self) -> None:
        # Uncovered TEMP witness exists solely to distinguish statement ABORT
        # from a qualified batch rollback; not a candidate ordinary table.
        self.db.execute("CREATE TEMP TABLE transaction_witness(value)")
        self.db.execute("BEGIN")
        self.db.execute("INSERT INTO transaction_witness VALUES(1)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO fga_users VALUES('synthetic')")
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM transaction_witness").fetchone()[0], 1
        )
        self.db.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            atomic_fixture_batch(
                self.db,
                [
                    ("INSERT INTO transaction_witness VALUES(?)", (1,)),
                    ("INSERT INTO fga_users VALUES(?)", ("synthetic",)),
                ],
            )
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM transaction_witness").fetchone()[0], 0
        )

    def test_stale_invocation_fails_closed_and_can_write_after_reopen(self) -> None:
        self.open()
        stale_sql = "INSERT INTO fga_users VALUES('delayed-synthetic')"
        # A prior SELECT/open observation is deliberately not carried as authority.
        self.assertEqual(parse_readback(readback(self.db)).state, "open")
        self.transition("close", "2")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(stale_sql)
        self.transition("reopen", "3")
        self.db.execute(stale_sql)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM fga_users").fetchone()[0], 1)

    def test_multirow_abort_and_open_domain_batch_leave_no_partial_work(self) -> None:
        self.open()
        self.db.execute(
            "INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) "
            "VALUES('existing','group','flickr_code_6','attempt')"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT OR IGNORE INTO submission_blocks"
                "(photo_id,group_id,first_reason,source_attempt_id) VALUES"
                "('new','group','flickr_code_7','attempt'),"
                "('existing','group','flickr_code_6','attempt')"
            )
        self.assertEqual(
            self.db.execute("SELECT photo_id FROM submission_blocks").fetchall(), [("existing",)]
        )
        with self.assertRaises(sqlite3.IntegrityError):
            atomic_fixture_batch(
                self.db,
                [
                    ("INSERT INTO fga_users VALUES(?)", ("must-roll-back",)),
                    ("DELETE FROM submission_blocks", ()),
                ],
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM fga_users").fetchone()[0], 0)

    def test_unknown_schema_and_nested_fixture_operation_refuse(self) -> None:
        db = source_database(MIGRATIONS)
        self.addCleanup(db.close)
        db.execute("CREATE TABLE unknown(value)")
        with self.assertRaisesRegex(ValueError, "unexpected_source_schema"):
            bootstrap_fixture(db)
        self.db.execute("BEGIN")
        with self.assertRaisesRegex(ValueError, "batch_requires_idle_connection"):
            atomic_fixture_batch(self.db, [])
        with self.assertRaisesRegex(ValueError, "bootstrap_requires_idle_connection"):
            bootstrap_fixture(self.db)
        self.db.rollback()

    def test_independent_readback_rejects_schema_drift_echo_and_malformed_rows(self) -> None:
        intent = reopen("1")
        with self.assertRaises(Refusal):
            confirm_readback(intent, readback(self.db), schema_rows(self.db))
        self.open()
        rows = readback(self.db)
        invalid_rows: list[list[dict[str, object]]] = [
            [],
            rows + rows,
            [{"generation_text": "2"}],
            [{**rows[0], "generation_type": "real"}],
            [{**rows[0], "generation_text": 2}],
            [{**rows[0], "rowid_text": "2"}],
        ]
        for invalid in invalid_rows:
            with self.subTest(invalid=invalid), self.assertRaises(Refusal):
                confirm_readback(intent, invalid, schema_rows(self.db))
        self.db.execute("CREATE TABLE uncovered(value)")
        with self.assertRaisesRegex(Refusal, "schema_readback_mismatch"):
            confirm_readback(intent, rows, schema_rows(self.db))


class IndirectMechanismTests(unittest.TestCase):
    def test_cascade_trigger_effect_and_generated_values(self) -> None:
        # Micro-fixture, not the 62-table manifest. Deliberately unguarded driver
        # forces indirect child guards to run without relying on trigger order.
        for recursive in (0, 1):
            db = sqlite3.connect(":memory:", isolation_level=None)
            try:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute(f"PRAGMA recursive_triggers={recursive}")
                db.executescript(
                    read_sql("bootstrap") + "CREATE TABLE driver(id INTEGER PRIMARY KEY);"
                    "CREATE TABLE child(id INTEGER PRIMARY KEY, "
                    "parent INTEGER REFERENCES driver(id) ON DELETE CASCADE "
                    "ON UPDATE CASCADE, twice INTEGER GENERATED ALWAYS AS (id*2));"
                    "INSERT INTO driver VALUES(1);INSERT INTO child(id,parent) VALUES(1,1);"
                    + guard_sql(["child"])
                )
                for sql in ("DELETE FROM driver", "UPDATE driver SET id=2"):
                    with (
                        self.subTest(recursive=recursive, sql=sql),
                        self.assertRaisesRegex(sqlite3.IntegrityError, "maintenance_closed"),
                    ):
                        db.execute(sql)
                db.executescript(
                    "CREATE TRIGGER driver_effect AFTER INSERT ON driver "
                    "BEGIN INSERT INTO child(id,parent) VALUES(NEW.id,NEW.id);END;"
                )
                with self.assertRaisesRegex(sqlite3.IntegrityError, "maintenance_closed"):
                    db.execute("INSERT INTO driver VALUES(2)")
                self.assertEqual(db.execute("SELECT * FROM driver").fetchall(), [(1,)])
                self.assertEqual(db.execute("SELECT * FROM child").fetchall(), [(1, 1, 2)])
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
