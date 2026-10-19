"""Synthetic finite faults, independent expected state and candidate corruption."""

from __future__ import annotations

import copy
import json
import sqlite3
import struct
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fixture import create_fixture, digest, reopen_reference
from full_state_oracle import OracleRefused, check, read_reference

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import fixed_origin_preservation as candidate  # noqa: E402


class FullStateOracleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="synthetic-pmb1-oracle-")
        self.addCleanup(self.directory.cleanup)
        self.fixture = create_fixture(Path(self.directory.name))
        self.reference = reopen_reference(self.fixture)
        self.snapshot = self.capture()

    def capture(self) -> dict[str, Any]:
        with closing(sqlite3.connect(self.fixture.path.as_uri() + "?mode=ro", uri=True)) as reader:
            result = candidate.capture_sqlite(
                reader, run="a" * 32, database="synthetic-oracle", observed_at_ms=1
            )
        return result

    def cell(self, label: str, snapshot: Any = None) -> list[Any]:
        selected = self.snapshot if snapshot is None else snapshot
        return next(r[1] for r in selected["tables"]["cells"]["rows"] if r[0] == ["text", label])

    def assertDrift(self, snapshot: Any) -> None:
        with self.assertRaises(OracleRefused):
            check(self.reference, snapshot)

    def test_reopened_complete_reference_and_provenance(self) -> None:
        check(self.reference, self.snapshot)
        self.assertEqual(digest(self.fixture.path), self.fixture.persisted_sha256)
        self.assertEqual(len(self.fixture.generator_sha256), 64)
        self.assertEqual(len(self.fixture.oracle_sha256), 64)
        self.assertEqual(reopen_reference(self.fixture), self.reference)
        self.assertEqual(self.snapshot["tables"]["keys"]["rowids"], None)
        self.assertEqual(self.snapshot["tables"]["generated"]["columns"], ["n", "doubled"])

    def test_one_bit_and_sign_faults_every_real_boundary(self) -> None:
        for row in self.snapshot["tables"]["cells"]["rows"]:
            if row[1][0] != "real":
                continue
            label = row[0][1]
            value = float.fromhex(row[1][1])
            bits = struct.unpack(">Q", struct.pack(">d", value))[0]
            for mask in (1, 1 << 63):
                with self.subTest(label=label, mask=mask):
                    changed = copy.deepcopy(self.snapshot)
                    raw = struct.pack(">Q", bits ^ mask)
                    self.cell(label, changed)[1] = struct.unpack(">d", raw)[0].hex()
                    self.assertDrift(changed)

    def test_integer_types_text_and_blob_faults(self) -> None:
        faults = {
            "int-max": ["integer", 2**63 - 2],
            "int-over-js": ["integer", 2**53],
            "int-zero": ["real", "0x0.0p+0"],
            "text-integer": ["integer", 1],
            "null": ["text", ""],
            "text-nul": ["text", "before"],
            "blob-nul": ["blob", "00ff8000"],
            "blob-empty": ["text", ""],
        }
        for label, replacement in faults.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(self.snapshot)
                self.cell(label, changed)[:] = replacement
                self.assertDrift(changed)

    def test_schema_census_order_and_sql_faults(self) -> None:
        for action in ("missing", "extra", "sql", "order"):
            with self.subTest(action=action):
                changed = copy.deepcopy(self.snapshot)
                schema = changed["schema"]
                if action == "missing":
                    schema.pop()
                elif action == "extra":
                    schema.append(["view", "extra", "extra", "CREATE VIEW extra AS SELECT 1"])
                elif action == "sql":
                    next(r for r in schema if r[3] is not None)[3] += " "
                else:
                    schema.reverse()
                self.assertDrift(changed)
        for table_action in ("missing", "extra", "column-order", "field"):
            changed = copy.deepcopy(self.snapshot)
            tables = changed["tables"]
            if table_action == "missing":
                tables.pop("_cf_KV")
            elif table_action == "extra":
                tables["extra"] = tables["_cf_KV"]
            elif table_action == "column-order":
                tables["cells"]["columns"].reverse()
            else:
                tables["cells"]["ignored"] = True
            self.assertDrift(changed)

    def test_duplicates_row_identity_keys_and_row_order(self) -> None:
        for action in ("missing", "extra", "same-count", "rowid", "key", "order"):
            with self.subTest(action=action):
                changed = copy.deepcopy(self.snapshot)
                table = changed["tables"]["duplicates"]
                if action == "missing":
                    table["rows"].pop()
                    table["rowids"].pop()
                elif action == "extra":
                    table["rows"].append(table["rows"][0])
                    table["rowids"].append(2)
                elif action == "same-count":
                    table["rows"][0] = [["text", "same"]]
                elif action == "rowid":
                    table["rowids"][0] = 6
                elif action == "key":
                    changed["tables"]["keys"]["rows"][0][0] = ["text", "changed-key"]
                else:
                    table["rows"].reverse()
                    table["rowids"].reverse()
                self.assertDrift(changed)

    def test_shared_candidate_decoder_corruption_cannot_self_confirm(self) -> None:
        original = candidate._cell

        def corrupted(value: Any) -> list[Any]:
            encoded = original(value)
            if type(value) is str:
                return ["text", value.split("\0")[0]]
            return encoded

        with patch.object(candidate, "_cell", side_effect=corrupted):
            first, second = self.capture(), self.capture()
        # A broken shared decoder can agree with itself on both observations.
        self.assertEqual(first, second)
        self.assertDrift(first)
        self.assertDrift(second)
        self.assertEqual(reopen_reference(self.fixture), self.reference)

    def test_fixture_replacement_is_refused_before_read(self) -> None:
        with self.fixture.path.open("ab") as target:
            target.write(b"synthetic-drift")
        with self.assertRaisesRegex(OracleRefused, "fixture_changed_before_reopen"):
            reopen_reference(self.fixture)

    def test_existing_fixture_refused(self) -> None:
        with self.assertRaises(FileExistsError):
            create_fixture(Path(self.directory.name))

    def test_pinned_completed_sources_unchanged(self) -> None:
        root = Path(__file__).resolve().parents[2]
        pins = json.loads(Path(__file__).with_name("source-pins.json").read_text())
        for relative, expected in pins.items():
            with self.subTest(source=relative):
                self.assertEqual(digest(root / relative), expected)

    def test_malformed_observed_cells_refuse(self) -> None:
        for malformed in (
            ["integer", True],
            ["integer", 2**63],
            ["real", "nan"],
            ["real", "0x1.0p+0"],
            ["real", "0x1.0000000000000p+1024"],
            ["blob", "FF"],
            ["text", "\ud800"],
            ["null", 0],
            ["unknown", "value"],
            ["integer"],
            {"type": "null"},
        ):
            changed = copy.deepcopy(self.snapshot)
            row = next(r for r in changed["tables"]["cells"]["rows"] if r[0] == ["text", "null"])
            row[1] = malformed
            self.assertDrift(changed)

    def test_reference_unsupported_and_row_bound_refuse(self) -> None:
        for sql in (
            "CREATE TABLE hidden(rowid,_rowid_,oid)",
            "CREATE TABLE many(x); INSERT INTO many SELECT 1 FROM "
            "(WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<10001) "
            "SELECT * FROM n)",
            "CREATE TABLE nonfinite(x); INSERT INTO nonfinite VALUES(1e999)",
        ):
            with self.subTest(sql=sql.split("(")[0]), closing(sqlite3.connect(":memory:")) as db:
                db.executescript(sql)
                with self.assertRaises(OracleRefused):
                    read_reference(db)

    def test_reference_does_not_commit_caller_transaction(self) -> None:
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE x(a)")
            db.execute("INSERT INTO x VALUES(1)")
            with self.assertRaisesRegex(OracleRefused, "active_reference_transaction"):
                read_reference(db)
            self.assertTrue(db.in_transaction)


if __name__ == "__main__":
    unittest.main()
