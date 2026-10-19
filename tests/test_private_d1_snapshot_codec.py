"""Lossless snapshot seams with synthetic SQLite only; no provider qualification."""

from __future__ import annotations

import copy
import sqlite3
import unittest
from unittest.mock import Mock, patch

from scripts import fixed_origin_preservation as preservation
from scripts import private_d1_snapshot_codec as codec


class SnapshotCodecTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.calls = []

    def query(self, sql):
        self.calls.append(sql)
        cursor = self.db.execute(sql)
        names = [item[0] for item in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor]

    def assert_matches_local_capture(self, *, page_size=2):
        actual = codec.collect_snapshot(self.query, page_size=page_size)
        expected = preservation.capture_sqlite(
            self.db, run="a" * 32, database="synthetic-codec", observed_at_ms=1
        )
        self.assertEqual(actual, {key: expected[key] for key in ("schema", "tables")})
        return actual

    def test_exact_all_schema_typed_rows_rowids_and_bookkeeping(self):
        self.db.executescript("""
            CREATE TABLE sample(id INTEGER PRIMARY KEY AUTOINCREMENT, value, extra);
            CREATE INDEX sample_value ON sample(value);
            CREATE VIEW sample_view AS SELECT id FROM sample;
            CREATE TRIGGER sample_trigger AFTER INSERT ON sample BEGIN SELECT 1; END;
            CREATE TABLE _cf_KV(key TEXT PRIMARY KEY, value BLOB) WITHOUT ROWID;
        """)
        values = [None, -(2**63), 2**63 - 1, "", "synthetic-private-\u96ea\x00tail", b"\x00\xff"]
        self.db.executemany(
            "INSERT INTO sample(value,extra) VALUES (?,?)", [(v, v) for v in values]
        )
        self.db.execute("INSERT INTO sample(value,extra) VALUES (?,?)", ("same", "same"))
        self.db.execute("INSERT INTO sample(value,extra) VALUES (?,?)", ("same", "same"))
        self.db.execute("INSERT INTO _cf_KV VALUES (?,?)", ("synthetic-key", b"private"))
        self.db.commit()
        actual = self.assert_matches_local_capture()
        self.assertIn("sqlite_sequence", actual["tables"])
        self.assertIn("_cf_KV", actual["tables"])
        self.assertTrue(all(sql.startswith("SELECT") for sql in self.calls))

    def test_quoted_identifiers_do_not_become_sql(self):
        name = 'odd"; DROP TABLE keeper; --'
        quoted = '"' + name.replace('"', '""') + '"'
        self.db.execute("CREATE TABLE keeper(value)")
        self.db.execute("CREATE TABLE " + quoted + '("select" TEXT, "rowid" TEXT)')
        self.db.execute("INSERT INTO " + quoted + " VALUES (?,?)", ("synthetic", "shadow"))
        self.db.commit()
        actual = self.assert_matches_local_capture(page_size=1)
        self.assertIn(name, actual["tables"])
        self.assertIn("keeper", actual["tables"])

    def test_empty_and_without_rowid_composite_keys_preserve_exact_identity(self):
        self.db.executescript("""
            CREATE TABLE empty(value);
            CREATE TABLE keyed(a TEXT, b INTEGER, value, PRIMARY KEY(a,b)) WITHOUT ROWID;
            INSERT INTO keyed VALUES ('x',2,NULL),('x',1,X'00'),('y',1,'');
        """)
        actual = self.assert_matches_local_capture(page_size=1)
        self.assertIsNone(actual["tables"]["keyed"]["rowids"])
        self.assertEqual(actual["tables"]["empty"]["rows"], [])

    def test_equal_count_cell_rowid_and_schema_drift_are_visible(self):
        self.db.executescript("CREATE TABLE sample(value); INSERT INTO sample VALUES ('a'),('a');")
        original = self.assert_matches_local_capture()
        self.db.execute("UPDATE sample SET value='b' WHERE rowid=1")
        self.db.commit()
        changed = self.assert_matches_local_capture()
        self.assertNotEqual(original, changed)
        self.db.execute("UPDATE sample SET rowid=30 WHERE rowid=1")
        self.db.commit()
        moved = self.assert_matches_local_capture()
        self.assertNotEqual(changed, moved)
        self.db.execute("CREATE INDEX marker_index ON sample(value)")
        self.db.commit()
        self.assertNotEqual(moved, self.assert_matches_local_capture())

    def test_real_and_inaccessible_hidden_rowid_refuse(self):
        for schema in (
            "CREATE TABLE sample(value); INSERT INTO sample VALUES (1.25);",
            "CREATE TABLE sample(rowid,_rowid_,oid); INSERT INTO sample VALUES (1,2,3);",
        ):
            with self.subTest(schema=schema):
                self.db.executescript("DROP TABLE IF EXISTS sample;" + schema)
                with self.assertRaises(codec.Refused):
                    codec.collect_snapshot(self.query)

    def test_generated_columns_match_existing_full_select_contract(self):
        self.db.executescript(
            "CREATE TABLE sample(value, generated AS (value+1));"
            "INSERT INTO sample(value) VALUES (4);"
        )
        self.assert_matches_local_capture()

    def test_census_loss_duplication_and_unsupported_column_refuse(self):
        self.db.executescript("CREATE TABLE sample(value); INSERT INTO sample VALUES (1);")
        schema = self.query(codec.SCHEMA_SQL)
        storage = self.query(codec.TABLE_LIST_SQL)
        columns = {"sample": self.query(codec.columns_sql("sample"))}
        for changed in (storage[:-1], storage + storage[:1], []):
            with self.subTest(changed=changed), self.assertRaises(codec.Refused):
                codec.build_plan(schema, changed, columns)
        for changed in ({}, {**columns, "omitted": []}):
            with self.assertRaises(codec.Refused):
                codec.build_plan(schema, storage, changed)
        columns["sample"][0]["hidden"] = 1
        with self.assertRaises(codec.Refused):
            codec.build_plan(schema, storage, columns)

    def test_wire_types_ranges_and_noncanonical_encodings_refuse(self):
        table = codec.TablePlan("sample", ("value",), "rowid", ())
        invalid = [
            ("integer", 1),
            ("integer", True),
            ("integer", "01"),
            ("integer", str(2**63)),
            ("integer", str(-(2**63) - 1)),
            ("null", ""),
            ("blob", "0"),
            ("blob", "aa"),
            ("text", "FF"),
            ("real", "1.0"),
            ("unknown", None),
        ]
        for tag, value in invalid:
            with self.subTest(tag=tag, value=value), self.assertRaises(codec.Refused):
                codec.decode_table_page(
                    table, [{"row_identity": "1", "c0_type": tag, "c0_value": value}]
                )
        for count in ([], [{"row_count": 0}], [{"row_count": "-1"}], [{"row_count": "01"}]):
            with self.assertRaises(codec.Refused):
                codec.decode_count(count)

    def test_utf16_database_refuses_instead_of_decoding_text_as_utf8(self):
        self.db.execute("PRAGMA encoding='UTF-16'")
        self.db.executescript("CREATE TABLE sample(value); INSERT INTO sample VALUES ('text');")
        with self.assertRaises(codec.Refused):
            codec.collect_snapshot(self.query)

    def test_encoding_witness_refuses_both_utf16_orders_and_malformed_results(self):
        for encoding, witness in (("UTF-8", "41"), ("UTF-16le", "4100"), ("UTF-16be", "0041")):
            with self.subTest(encoding=encoding):
                db = sqlite3.connect(":memory:")
                try:
                    db.execute("PRAGMA encoding='" + encoding + "'")
                    db.execute("CREATE TABLE sample(value)")
                    db.execute("INSERT INTO sample VALUES (?)", ("a\0b🌊",))
                    db.commit()
                    self.assertEqual(db.execute(codec.ENCODING_SQL).fetchall(), [(witness,)])

                    def query(sql, db=db):
                        cursor = db.execute(sql)
                        names = [item[0] for item in cursor.description]
                        return [dict(zip(names, row, strict=True)) for row in cursor]

                    if encoding == "UTF-8":
                        self.assertIn("sample", codec.collect_snapshot(query)["tables"])
                    else:
                        with self.assertRaisesRegex(
                            codec.Refused, "unsupported_database_text_encoding"
                        ):
                            codec.collect_snapshot(query)
                finally:
                    db.close()
        self.db.execute("CREATE TABLE sample(value)")
        for response in (
            [],
            [{"encoding_probe": "41"}] * 2,
            [{"encoding_probe": "4100"}],
            [{"encoding_probe": "0041"}],
            [{"encoding_probe": None}],
            [{"encoding_probe": 41}],
            [{"encoding_probe": "004100"}],
            [{"encoding_probe": "41", "extra": True}],
            [{"encoding": "UTF-8"}],
        ):
            with self.subTest(response=response):

                def changed(sql, response=response):
                    return response if sql == codec.ENCODING_SQL else self.query(sql)

                with self.assertRaises(codec.Refused):
                    codec.collect_snapshot(changed)

    def test_provider_reserved_table_denial_refuses_instead_of_omitting_state(self):
        self.db.executescript(
            "CREATE TABLE sample(v); "
            "CREATE TABLE _cf_KV(key TEXT PRIMARY KEY,value BLOB) WITHOUT ROWID;"
        )
        calls = []

        def deny_reserved(sql):
            calls.append(sql)
            if "_cf_KV" in sql:
                raise sqlite3.DatabaseError("synthetic reserved-table authorization refusal")
            return self.query(sql)

        with self.assertRaisesRegex(codec.Refused, "snapshot_query_failed"):
            codec.collect_snapshot(deny_reserved)
        self.assertTrue(any("_cf_KV" in sql for sql in calls))

    def test_virtual_table_refuses_instead_of_omitting_shadow_state(self):
        self.db.execute("CREATE VIRTUAL TABLE sample USING fts5(value)")
        with self.assertRaises(codec.Refused):
            codec.collect_snapshot(self.query)

    def test_malformed_wire_values_and_unknown_fields_refuse_without_echo(self):
        self.db.executescript("CREATE TABLE sample(value); INSERT INTO sample VALUES ('marker');")
        marker = "synthetic-private-wire-marker"

        def corrupt(sql):
            rows = self.query(sql)
            if rows and "c0_type" in rows[0]:
                rows = copy.deepcopy(rows)
                rows[0]["c0_type"] = marker
            return rows

        with self.assertRaises(codec.Refused) as raised:
            codec.collect_snapshot(corrupt)
        self.assertNotIn(marker, str(raised.exception))

    def test_missing_sentinel_duplicate_identity_and_extra_page_refuse(self):
        self.db.executescript("CREATE TABLE sample(value); INSERT INTO sample VALUES (1),(2);")
        plan = codec.build_plan(
            self.query(codec.SCHEMA_SQL),
            self.query(codec.TABLE_LIST_SQL),
            {"sample": self.query(codec.columns_sql("sample"))},
            page_size=2,
        )
        table = plan.tables[0]
        page = self.query(codec.table_page_sql(table, 0, 2))
        for pages in ([page], [page, [], []], [page, page]):
            with self.assertRaises(codec.Refused):
                codec.assemble_snapshot(plan, {"sample": pages}, {"sample": 2})
        duplicate = copy.deepcopy(page)
        duplicate[1]["row_identity"] = duplicate[0]["row_identity"]
        with self.assertRaises(codec.Refused):
            codec.assemble_snapshot(plan, {"sample": [duplicate, []]}, {"sample": 2})

    def test_callback_failure_and_finite_work_bounds_fail_closed(self):
        marker = "synthetic-private-query-diagnostic"
        failure = Mock(side_effect=RuntimeError(marker))
        with self.assertRaises(codec.Refused) as raised:
            codec.collect_snapshot(failure)
        self.assertNotIn(marker, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertEqual(failure.call_count, 1)
        for attribute, limit in (("MAX_QUERIES", 1), ("MAX_BYTES", 1)):
            self.calls.clear()
            with patch.object(codec, attribute, limit), self.assertRaises(codec.Refused):
                codec.collect_snapshot(self.query)
            self.assertLessEqual(len(self.calls), 1)

    def test_missing_page_is_not_an_empty_snapshot(self):
        self.db.executescript("CREATE TABLE sample(value); INSERT INTO sample VALUES (1),(2),(3);")

        def truncated(sql):
            rows = self.query(sql)
            if rows and "c0_type" in rows[0]:
                return []
            return rows

        with self.assertRaises(codec.Refused):
            codec.collect_snapshot(truncated, page_size=2)


if __name__ == "__main__":
    unittest.main()
