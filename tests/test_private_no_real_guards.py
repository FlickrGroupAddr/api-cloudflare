"""Local synthetic SQLite proofs only; no provider, migration, or live census."""

from __future__ import annotations

import copy
import sqlite3
import unittest
from pathlib import Path

from scripts import private_d1_snapshot_codec as codec
from scripts import private_no_real_guards as guards
from scripts.fixed_origin_preservation import Refused


class NoRealGuardTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA recursive_triggers=ON")
        self.db.executescript("""
            CREATE TABLE ledger(id INTEGER PRIMARY KEY, value, integral INTEGER,
                "odd'column" BLOB);
            CREATE TABLE generated(id INTEGER PRIMARY KEY, source INTEGER,
                stored INTEGER GENERATED ALWAYS AS(source/2.0) STORED,
                virtual INTEGER GENERATED ALWAYS AS(source/4.0) VIRTUAL);
            CREATE TABLE parent(id INTEGER PRIMARY KEY);
            CREATE TABLE child(id INTEGER PRIMARY KEY,
                parent_id INTEGER REFERENCES parent(id) ON UPDATE CASCADE,
                generated INTEGER GENERATED ALWAYS AS(parent_id/2.0) STORED);
            CREATE TABLE sink(value);
            CREATE TABLE trigger_source(value);
            CREATE TRIGGER synthetic_insert AFTER INSERT ON trigger_source
                WHEN NEW.value='bad' BEGIN INSERT INTO sink VALUES(1.25); END;
            CREATE TRIGGER synthetic_update AFTER UPDATE ON trigger_source
                WHEN NEW.value='bad' BEGIN INSERT INTO sink VALUES(1.25); END;
            CREATE TABLE _cf_application(value);
            CREATE TABLE d1_migrations(value);
            CREATE TABLE exact_key(value BLOB PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE strict_any(value ANY) STRICT;
        """)
        self.db.executescript(
            (Path(__file__).parent / "integer_quota_fixture.sql").read_text(encoding="utf-8")
        )
        schema, storage, columns = self.census()
        self.manifest = guards.build_guard_manifest(schema, storage, columns)
        self.pin = guards.manifest_sha256(self.manifest)
        for guard in self.manifest["guards"]:
            self.db.execute(guard["sql"])
        self.db.commit()

    def query(self, sql):
        cursor = self.db.execute(sql)
        return [
            dict(zip((item[0] for item in cursor.description), row, strict=True)) for row in cursor
        ]

    def census(self):
        schema = self.query(codec.SCHEMA_SQL)
        storage = self.query(codec.TABLE_LIST_SQL)
        columns = {
            row["name"]: self.query(codec.columns_sql(row["name"]))
            for row in schema
            if row["type"] == "table"
        }
        return schema, storage, columns

    def validate(self, manifest=None, pin=None, query=None):
        guards.validate_guard_manifest(
            self.manifest if manifest is None else manifest,
            *self.census(),
            expected_manifest_sha256=self.pin if pin is None else pin,
            query=self.query if query is None else query,
        )

    def refused(self, sql, values=()):
        with self.assertRaisesRegex(sqlite3.IntegrityError, guards.ERROR):
            self.db.execute(sql, values)

    def test_exact_manifest_every_column_rowid_and_both_events(self):
        self.validate()
        self.assertEqual(len(self.manifest["guards"]), 2 * len(self.manifest["columns"]))
        for table, columns in self.manifest["columns"].items():
            cells = self.manifest["cells"][table]
            self.assertTrue(all(column["name"] in cells for column in columns))
            self.assertEqual(
                {guard["event"] for guard in self.manifest["guards"] if guard["table"] == table},
                {"INSERT", "UPDATE"},
            )
        self.assertIn("rowid", self.manifest["cells"]["ledger"])
        self.assertEqual(self.manifest["cells"]["exact_key"], ["value"])
        self.assertIn("stored", self.manifest["cells"]["generated"])
        self.assertIn("virtual", self.manifest["cells"]["generated"])

    def test_post_affinity_integer_acceptance_and_actual_real_refusal(self):
        self.db.execute("INSERT INTO ledger VALUES(1,NULL,2.0,X'0001')")
        self.assertEqual(
            self.db.execute("SELECT typeof(integral) FROM ledger").fetchone(), ("integer",)
        )
        self.db.execute("UPDATE ledger SET integral=3.0")
        self.refused("UPDATE ledger SET integral=3.25")
        self.refused("UPDATE ledger SET value=2.0")
        self.refused('UPDATE ledger SET "odd\'column"=2.0')
        self.refused("INSERT INTO strict_any VALUES(2.0)")
        for value in (None, -(2**63), 2**63 - 1, "text", b"\x00\xff"):
            self.db.execute("INSERT INTO sink VALUES(?)", (value,))
        self.refused("INSERT INTO sink VALUES(?)", (float(2**53),))
        self.assertEqual(self.db.execute("SELECT integral FROM ledger").fetchone(), (3,))

    def test_generated_stored_and_virtual_cells_are_post_affinity(self):
        self.db.execute("INSERT INTO generated(id,source) VALUES(1,4)")
        self.assertEqual(
            self.db.execute("SELECT typeof(stored),typeof(virtual) FROM generated").fetchone(),
            ("integer", "integer"),
        )
        self.refused("INSERT INTO generated(id,source) VALUES(2,3)")
        self.refused("INSERT INTO generated(id,source) VALUES(2,6)")
        self.refused("UPDATE generated SET source=6")
        self.assertEqual(self.db.execute("SELECT source FROM generated").fetchall(), [(4,)])

    def test_trigger_and_cascade_failures_abort_parent_statement(self):
        for recursive in (0, 1):
            with self.subTest(recursive=recursive):
                self.db.execute(f"PRAGMA recursive_triggers={recursive}")
                self.refused("INSERT INTO trigger_source VALUES('bad')")
                self.db.execute("INSERT INTO trigger_source VALUES('ok')")
                self.refused("UPDATE trigger_source SET value='bad'")
                self.assertEqual(self.db.execute("SELECT * FROM sink").fetchall(), [])
                self.db.execute("DELETE FROM trigger_source")
        self.db.execute("INSERT INTO parent VALUES(2)")
        self.db.execute("INSERT INTO child(id,parent_id) VALUES(10,2)")
        self.refused("UPDATE parent SET id=3")
        self.assertEqual(self.db.execute("SELECT * FROM parent").fetchall(), [(2,)])
        self.assertEqual(self.db.execute("SELECT * FROM child").fetchall(), [(10, 2, 1)])

    def test_multirow_update_upsert_replace_and_conflict_overrides_roll_back_statement(self):
        self.db.execute("INSERT INTO ledger(id,value) VALUES(1,'retained'),(2,'second')")
        cases = (
            "INSERT INTO ledger(id,value) VALUES(3,7),(4,1.25)",
            "UPDATE ledger SET value=CASE id WHEN 1 THEN 7 ELSE 1.25 END",
            "INSERT INTO ledger(id,value) VALUES(3,7),(1,1.25) "
            "ON CONFLICT(id) DO UPDATE SET value=excluded.value",
            "REPLACE INTO ledger(id,value) VALUES(1,1.25)",
            "INSERT OR IGNORE INTO ledger(id,value) VALUES(3,1.25)",
            "UPDATE OR REPLACE ledger SET value=1.25 WHERE id=1",
        )
        for sql in cases:
            with self.subTest(sql=sql):
                self.refused(sql)
                self.assertEqual(
                    self.db.execute("SELECT id,value FROM ledger ORDER BY id").fetchall(),
                    [(1, "retained"), (2, "second")],
                )

    def test_full_transaction_owner_rolls_back_earlier_and_trigger_writes(self):
        for bad_sql in (
            "INSERT INTO sink VALUES(1.25)",
            "INSERT INTO trigger_source VALUES('bad')",
            "INSERT INTO ledger(id,value) VALUES(1,7),(2,1.25)",
        ):
            with self.subTest(sql=bad_sql):
                with self.assertRaisesRegex(sqlite3.IntegrityError, guards.ERROR):
                    with self.db:
                        self.db.execute("INSERT INTO sink VALUES('earlier')")
                        self.db.execute(bad_sql)
                        self.db.execute("INSERT INTO sink VALUES('later')")
                self.assertEqual(self.db.execute("SELECT * FROM sink").fetchall(), [])
                self.assertEqual(self.db.execute("SELECT * FROM ledger").fetchall(), [])

    def test_abort_alone_preserves_earlier_transaction_statement(self):
        self.db.execute("INSERT INTO sink VALUES('earlier')")
        self.refused("INSERT INTO sink VALUES(1.25)")
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT * FROM sink").fetchall(), [("earlier",)])
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT * FROM sink").fetchall(), [])

    def test_no_bookkeeping_or_provider_prefix_exemption(self):
        self.refused("INSERT INTO _cf_application VALUES(1.25)")
        self.refused("INSERT INTO d1_migrations VALUES(1.25)")

    def test_raise_ignore_fail_reordering_same_schema_cannot_receive_guard_authority(self):
        previous = self.db
        try:
            for event, mode in (
                ("INSERT", "IGNORE"),
                ("UPDATE", "IGNORE"),
                ("INSERT", "FAIL"),
                ("UPDATE", "FAIL"),
            ):
                schemas = []
                for guards_first in (False, True):
                    with self.subTest(event=event, mode=mode, guards_first=guards_first):
                        db = sqlite3.connect(":memory:")
                        self.addCleanup(db.close)
                        self.db = db
                        db.execute("CREATE TABLE t(value)")
                        if event == "UPDATE":
                            db.execute("INSERT INTO t VALUES(1)")
                        manifest = guards.build_guard_manifest(*self.census())
                        action = "IGNORE" if mode == "IGNORE" else "FAIL,'synthetic_fail'"
                        suppressor = (
                            "CREATE TRIGGER suppress AFTER " + event + " ON t "
                            "BEGIN SELECT rAiSe/*synthetic comment*/(" + action + "); END"
                        )
                        statements = [guard["sql"] for guard in manifest["guards"]]
                        statements = (
                            statements + [suppressor] if guards_first else [suppressor] + statements
                        )
                        for sql in statements:
                            db.execute(sql)
                        schema, storage, columns = self.census()
                        schemas.append(schema)
                        guard_names = {guard["name"] for guard in manifest["guards"]}
                        base_schema = [row for row in schema if row["name"] not in guard_names]
                        with self.assertRaisesRegex(Refused, "no_real_unsupported_base_trigger"):
                            guards.build_guard_manifest(base_schema, storage, columns)
                        # Model an old externally pinned manifest, independently of
                        # the corrected builder, to exercise reader-side refusal.
                        old_manifest = copy.deepcopy(manifest)
                        old_manifest["baseSchema"] = base_schema
                        old_manifest["schema"] = schema
                        with self.assertRaisesRegex(Refused, "no_real_unsupported_base_trigger"):
                            guards.validate_guard_manifest(
                                old_manifest,
                                schema,
                                storage,
                                columns,
                                expected_manifest_sha256=guards.manifest_sha256(old_manifest),
                                query=self.query,
                            )
                        sql = (
                            "INSERT INTO t VALUES(1.5)"
                            if event == "INSERT"
                            else "UPDATE t SET value=1.5"
                        )
                        if guards_first:
                            # Independent witness: exact schema metadata alone
                            # cannot detect this unsafe trigger execution order.
                            if mode == "FAIL":
                                with self.assertRaisesRegex(
                                    sqlite3.IntegrityError, "synthetic_fail"
                                ):
                                    db.execute(sql)
                            else:
                                db.execute(sql)
                            self.assertEqual(
                                db.execute("SELECT typeof(value) FROM t").fetchall(), [("real",)]
                            )
                        else:
                            self.refused(sql)
                self.assertEqual(schemas[0], schemas[1])
        finally:
            self.db = previous

    def test_base_raise_refusal_is_conservative_and_not_a_sql_parser(self):
        for body in (
            "SELECT RAISE(IGNORE)",
            "SELECT rAiSe /* comment */ (IGNORE)",
            "SELECT RAISE(FAIL,'synthetic')",
            "SELECT 'harmless raise ignore literal'",
            'SELECT "raise ignore"',
            "SELECT 1 /* harmless RAISE FAIL comment */",
        ):
            schema = copy.deepcopy(self.manifest["baseSchema"])
            schema.append(
                {
                    "type": "trigger",
                    "name": "suppress",
                    "tbl_name": "ledger",
                    "sql": "CREATE TRIGGER suppress AFTER INSERT ON ledger BEGIN " + body + "; END",
                }
            )
            schema.sort(key=lambda row: (row["type"], row["name"], row["tbl_name"]))
            with (
                self.subTest(body=body),
                self.assertRaisesRegex(Refused, "no_real_unsupported_base_trigger"),
            ):
                guards.build_guard_manifest(
                    schema, self.manifest["tableList"], self.manifest["columns"]
                )

    def test_plain_abort_and_rollback_base_invariants_remain_supported(self):
        previous = self.db
        try:
            for mode in ("ABORT", "ROLLBACK"):
                with self.subTest(mode=mode):
                    db = sqlite3.connect(":memory:")
                    self.addCleanup(db.close)
                    self.db = db
                    db.execute("CREATE TABLE t(value)")
                    db.execute(
                        "CREATE TRIGGER invariant AFTER INSERT ON t WHEN NEW.value IS NULL "
                        "BEGIN SELECT RAISE(" + mode + ",'synthetic_invariant'); END"
                    )
                    manifest = guards.build_guard_manifest(*self.census())
                    for guard in manifest["guards"]:
                        db.execute(guard["sql"])
                    guards.validate_guard_manifest(
                        manifest,
                        *self.census(),
                        expected_manifest_sha256=guards.manifest_sha256(manifest),
                        query=self.query,
                    )
                    db.execute("INSERT INTO t VALUES(1)")
                    db.commit()
                    self.refused("INSERT INTO t VALUES(1.25)")
                    with self.assertRaisesRegex(sqlite3.IntegrityError, "synthetic_invariant"):
                        db.execute("INSERT INTO t VALUES(NULL)")
                    self.assertEqual(db.execute("SELECT * FROM t").fetchall(), [(1,)])
        finally:
            self.db = previous

    def test_guard_removal_and_unknown_table_refuse(self):
        self.db.execute("DROP TRIGGER " + codec._identifier(self.manifest["guards"][0]["name"]))
        with self.assertRaises(Refused):
            self.validate()
        self.db.execute("CREATE TABLE unexpected(value)")
        self.db.execute("INSERT INTO unexpected VALUES(1.25)")
        with self.assertRaises(Refused):
            self.validate()

    def test_pinned_manifest_and_every_metadata_kind_refuse_drift(self):
        for field in ("baseSchema", "schema", "tableList", "columns", "cells", "guards"):
            changed = copy.deepcopy(self.manifest)
            changed[field] = []
            with self.subTest(field=field), self.assertRaises(Refused):
                self.validate(changed)
        changed = copy.deepcopy(self.manifest)
        changed["guards"][0]["sql"] = changed["guards"][0]["sql"].replace("ABORT", "IGNORE")
        with self.assertRaisesRegex(Refused, "no_real_guard_definition_mismatch"):
            self.validate(changed, guards.manifest_sha256(changed))
        for field in ("sql", "name", "tbl_name"):
            schema, storage, columns = self.census()
            schema[-1][field] = "changed"
            with self.subTest(field=field), self.assertRaises(Refused):
                guards.validate_guard_manifest(
                    self.manifest,
                    schema,
                    storage,
                    columns,
                    expected_manifest_sha256=self.pin,
                    query=self.query,
                )
        schema, storage, columns = self.census()
        columns["generated"][2]["hidden"] = 0
        with self.assertRaises(Refused):
            guards.validate_guard_manifest(
                self.manifest,
                schema,
                storage,
                columns,
                expected_manifest_sha256=self.pin,
                query=self.query,
            )

    def test_unsupported_hidden_virtual_unknown_and_inaccessible_schema_refuse(self):
        for field, value in (("hidden", 1), ("hidden", 4), ("cid", 99)):
            columns = copy.deepcopy(self.manifest["columns"])
            columns["ledger"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(Refused):
                guards.build_guard_manifest(
                    self.manifest["baseSchema"], self.manifest["tableList"], columns
                )
        storage = copy.deepcopy(self.manifest["tableList"])
        next(row for row in storage if row["name"] == "ledger")["type"] = "virtual"
        with self.assertRaises(Refused):
            guards.build_guard_manifest(
                self.manifest["baseSchema"], storage, self.manifest["columns"]
            )

        def unavailable(sql):
            raise sqlite3.OperationalError("synthetic private diagnostics must not escape")

        with self.assertRaisesRegex(Refused, "^no_real_cell_access_unavailable$"):
            self.validate(query=unavailable)
        for value in (None, [{}], {}):
            with self.subTest(value=value), self.assertRaises(Refused):
                self.validate(query=lambda sql, result=value: result)

    def test_internal_tables_refuse_complete_package_instead_of_being_skipped(self):
        self.db.execute("CREATE TABLE autoid(id INTEGER PRIMARY KEY AUTOINCREMENT)")
        schema, storage, columns = self.census()
        guard_names = {guard["name"] for guard in self.manifest["guards"]}
        base_schema = [row for row in schema if row["name"] not in guard_names]
        with self.assertRaisesRegex(Refused, "no_real_unguardable_table"):
            guards.build_guard_manifest(base_schema, storage, columns)

    def test_quoted_table_and_column_names_remain_fixed_sql(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute('CREATE TABLE "quote""table"("value""col" BLOB)')
        previous = self.db
        self.db = db
        try:
            manifest = guards.build_guard_manifest(*self.census())
            for guard in manifest["guards"]:
                db.execute(guard["sql"])
            guards.validate_guard_manifest(
                manifest,
                *self.census(),
                expected_manifest_sha256=guards.manifest_sha256(manifest),
                query=self.query,
            )
            self.refused('INSERT INTO "quote""table" VALUES(1.25)')
        finally:
            self.db = previous


if __name__ == "__main__":
    unittest.main()
