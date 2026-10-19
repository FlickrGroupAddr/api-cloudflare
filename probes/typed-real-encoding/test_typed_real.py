"""Finite synthetic checks only; neither universal nor managed D1 evidence."""

from __future__ import annotations

import json
import sqlite3
import unittest
from fractions import Fraction
from typing import Any

from typed_real import (
    CELL_SQL,
    MAX_FINITE,
    SIGN,
    Refused,
    bits_of,
    decode_wire,
    from_bits,
    positive_rational,
    rounds_to,
)

BOUNDARIES = (
    1,
    2,
    0x000FFFFFFFFFFFFF,
    0x0010000000000000,
    0x0010000000000001,
    0x3FEFFFFFFFFFFFFF,
    0x3FF0000000000000,
    0x3FF0000000000001,
    0x3FB999999999999A,
    MAX_FINITE,
    MAX_FINITE - 1,
)


def wire(spelling: Any = "1.0", **changes: Any) -> bytes:
    cell = {"type": "real", "decimal": spelling, "guard": 1}
    cell.update(changes)
    return json.dumps(cell, separators=(",", ":")).encode()


class OracleTests(unittest.TestCase):
    def test_known_exact_values(self) -> None:
        self.assertEqual(positive_rational(1), Fraction(1, 1 << 1074))
        self.assertEqual(positive_rational(0x0010000000000000), Fraction(1, 1 << 1022))
        self.assertEqual(positive_rational(0x3FF0000000000000), 1)
        self.assertEqual(positive_rational(MAX_FINITE), Fraction((1 << 53) - 1) * (1 << 971))

    def test_exact_midpoint_ties_and_neighbors(self) -> None:
        for bits in BOUNDARIES:
            with self.subTest(bits=bits):
                value = positive_rational(bits)
                lower = (positive_rational(bits - 1) + value) / 2
                following = (
                    Fraction(1 << 1024) if bits == MAX_FINITE else positive_rational(bits + 1)
                )
                upper = (value + following) / 2
                self.assertTrue(rounds_to(value, bits))
                self.assertTrue(rounds_to(-value, bits | SIGN))
                self.assertEqual(rounds_to(lower, bits), bits % 2 == 0)
                self.assertEqual(rounds_to(upper, bits), bits % 2 == 0)
                self.assertFalse(rounds_to(lower - (value - lower) / 2, bits))
                self.assertFalse(rounds_to(upper + (upper - value) / 2, bits))

    def test_wrong_sign_neighbor_and_nonfinite_patterns(self) -> None:
        self.assertFalse(rounds_to(Fraction(1), 0x3FF0000000000001))
        self.assertFalse(rounds_to(Fraction(-1), 0x3FF0000000000000))
        for bits in (
            0,
            SIGN,
            0x7FF0000000000000,
            0xFFF0000000000000,
            0x7FF8000000000000,
            0xFFF8000000000000,
            0x7FF0000000000001,
            0xFFF0000000000001,
        ):
            self.assertFalse(rounds_to(Fraction(1), bits))

    def test_decoder_oracle_rejects_wrong_float_candidate(self) -> None:
        # Independent source-bit oracle rejects a one-bit drift without invoking float().
        decimal = Fraction("0.1")
        self.assertTrue(rounds_to(decimal, 0x3FB999999999999A))
        self.assertFalse(rounds_to(decimal, 0x3FB999999999999B))


class DecoderTests(unittest.TestCase):
    def test_alternate_form_integral_precision(self) -> None:
        # SQLite's required .0 suffix does not add a 27th precision digit.
        for sign in (0, SIGN):
            spelling = "10000000000000000910000000.0"
            if sign:
                spelling = "-" + spelling
            self.assertEqual(
                decode_wire(wire(spelling)),
                ["real", from_bits(0x45208B2A2C280291 | sign).hex()],
            )
        for spelling in (
            "123456789012345678901234567.0",  # 27 integer digits, not formatter syntax
            "1.12345678901234567890123456",  # 27 significant digits
            "12345678901234567890123456.1",  # 27 significant digits
        ):
            with self.subTest(spelling=spelling), self.assertRaises(Refused):
                decode_wire(wire(spelling))

    def test_valid_and_exact_canonical(self) -> None:
        for spelling in (
            "1.0",
            "-1.0",
            "0.1",
            "4.9406564584124654e-324",
            "1.7976931348623157e+308",
        ):
            cell = decode_wire(wire(spelling))
            self.assertEqual(cell, ["real", float(spelling).hex()])
            self.assertEqual(bits_of(float.fromhex(cell[1])), bits_of(float(spelling)))

    def test_bad_decimal_spellings(self) -> None:
        for spelling in (
            "1",
            "+1.0",
            "01.0",
            "1.",
            ".1",
            " 1.0",
            "1.0 ",
            "1.0junk",
            "1_0.0",
            "0x1.0p0",
            "1.0E+01",
            "1.0e1",
            "NaN",
            "Inf",
            "1.0e+999",
            "1.0e+325",
            "1.0\u0000",
            "１.0",
            "1.123456789012345678901234567",
            "1." + "0" * 65,
        ):
            with self.subTest(spelling=spelling), self.assertRaises(Refused):
                decode_wire(wire(spelling))

    def test_zeros_overflow_and_underflow(self) -> None:
        for spelling in ("0.0", "-0.0", "0.0e+00", "1.0e-324", "1.8e+308", "-1.8e+308"):
            with self.assertRaises(Refused):
                decode_wire(wire(spelling))

    def test_decimal_must_be_string(self) -> None:
        for value in (None, 1, 1.0, True, [], {}):
            with self.assertRaises(Refused):
                decode_wire(wire(value))

    def test_guard_closed(self) -> None:
        for value in (0, -1, 2, None, True, "1", 1.0):
            with self.assertRaises(Refused):
                decode_wire(wire(guard=value))

    def test_tag_and_fields_closed(self) -> None:
        for tag in ("integer", "text", "blob", "null", None):
            with self.assertRaises(Refused):
                decode_wire(wire(type=tag))
        for raw in (b"{}", b"[]", b"null", wire(extra=1), b'{"type":"real","decimal":"1.0"}'):
            with self.assertRaises(Refused):
                decode_wire(raw)

    def test_duplicate_invalid_json_utf8_and_constants(self) -> None:
        for raw in (
            b'{"type":"real","type":"real","decimal":"1.0","guard":1}',
            b"\xff",
            b"{",
            b'{"decimal":NaN}',
            b'{"decimal":Infinity}',
            b'{"decimal":-Infinity}',
            b"{} trailing",
        ):
            with self.assertRaises(Refused):
                decode_wire(raw)

    def test_bound_before_json(self) -> None:
        with self.assertRaises(Refused):
            decode_wire(b" " * 257)

    def test_valid_substitution_is_unequal_not_authenticated(self) -> None:
        self.assertNotEqual(decode_wire(wire("1.0")), decode_wire(wire("1.0000000000000002")))
        # A fabricated true guard is not an authenticator. Both valid payloads decode.


class SQLiteTests(unittest.TestCase):
    def test_fixed_notation_26_digit_integers(self) -> None:
        # 1e25, another 26-digit integer, and both immediate binary64 neighbors.
        patterns = [
            (base + delta) | sign
            for base in (0x45208B2A2C280291, 0x45246C993044FD55)
            for delta in (-1, 0, 1)
            for sign in (0, SIGN)
        ]
        with sqlite3.connect(":memory:") as db:
            db.row_factory = sqlite3.Row
            db.execute("CREATE TABLE synthetic_values(id INTEGER PRIMARY KEY,x REAL) STRICT")
            db.executemany(
                "INSERT INTO synthetic_values(x) VALUES(?)", [(from_bits(b),) for b in patterns]
            )
            for bits, row in zip(patterns, db.execute(CELL_SQL), strict=True):
                with self.subTest(bits=bits):
                    self.assertEqual(row["guard"], 1)
                    self.assertNotIn("e", row["decimal"])
                    self.assertTrue(row["decimal"].endswith(".0"))
                    self.assertIn(len(row["decimal"].lstrip("-").split(".")[0]), (25, 26))
                    self.assertTrue(rounds_to(Fraction(row["decimal"]), bits))
                    self.assertEqual(
                        decode_wire(json.dumps(dict(row)).encode()),
                        ["real", from_bits(bits).hex()],
                    )

    def test_numeric_persistence_and_serialized_reopen(self) -> None:
        patterns = [b | sign for b in BOUNDARIES for sign in (0, SIGN)] + [0, SIGN]
        original = sqlite3.connect(":memory:")
        self.addCleanup(original.close)
        original.row_factory = sqlite3.Row
        original.execute("CREATE TABLE synthetic_values(id INTEGER PRIMARY KEY,x REAL) STRICT")
        original.executemany(
            "INSERT INTO synthetic_values VALUES(?,?)", enumerate(from_bits(b) for b in patterns)
        )
        original.commit()
        reopened = sqlite3.connect(":memory:")
        self.addCleanup(reopened.close)
        reopened.deserialize(original.serialize())
        reopened.row_factory = sqlite3.Row
        for connection in (original, reopened):
            source_rows = connection.execute(
                "SELECT typeof(x),x FROM synthetic_values ORDER BY id"
            ).fetchall()
            encoded = connection.execute(CELL_SQL).fetchall()
            self.assertEqual(len(encoded), 24)
            for bits, source, cell in zip(patterns, source_rows, encoded, strict=True):
                with self.subTest(bits=bits, reopened=connection is reopened):
                    self.assertEqual(source[0], "real")
                    if bits & (SIGN - 1) == 0:
                        self.assertEqual(source[1], 0.0)
                        # Observed for this pinned local build, never a D1 invariant.
                        self.assertEqual(bits_of(source[1]), 0)
                        self.assertEqual(cell["guard"], 0)
                        with self.assertRaises(Refused):
                            decode_wire(json.dumps(dict(cell)).encode())
                    else:
                        # Independent expected source pattern and direct local binary read;
                        # neither traverses the candidate decimal wire.
                        self.assertEqual(bits_of(source[1]), bits)
                        self.assertTrue(rounds_to(Fraction(cell["decimal"]), bits))
                        self.assertEqual(
                            decode_wire(json.dumps(dict(cell)).encode()),
                            ["real", from_bits(bits).hex()],
                        )

    def test_actual_tags_affinity_and_strict(self) -> None:
        with sqlite3.connect(":memory:") as db:
            for declaration, strict, expected in (
                ("", "", ["integer", "real", "text", "blob", "null"]),
                (" REAL", "", ["real", "real", "real", "blob", "null"]),
                (" REAL", " STRICT", ["real", "real", "real", "null"]),
            ):
                db.execute(
                    f"CREATE TABLE synthetic_values(id INTEGER PRIMARY KEY,x{declaration}){strict}"
                )
                values: list[Any] = [1, 1.0, "1.0", b"1.0", None]
                if strict:
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute("INSERT INTO synthetic_values(x) VALUES(?)", (b"1.0",))
                    values.remove(b"1.0")
                db.executemany("INSERT INTO synthetic_values(x) VALUES(?)", [(v,) for v in values])
                self.assertEqual(
                    [r[0] for r in db.execute("SELECT typeof(x) FROM synthetic_values")], expected
                )
                db.execute("DROP TABLE synthetic_values")

    def test_nonfinite_sql_insertion_semantics(self) -> None:
        with sqlite3.connect(":memory:") as db:
            db.row_factory = sqlite3.Row
            db.execute("CREATE TABLE synthetic_values(id INTEGER PRIMARY KEY,x REAL) STRICT")
            patterns = (
                0x7FF0000000000000,
                0xFFF0000000000000,
                0x7FF8000000000000,
                0xFFF8000000000000,
                0x7FF0000000000001,
                0xFFF0000000000001,
            )
            db.executemany(
                "INSERT INTO synthetic_values(x) VALUES(?)", [(from_bits(b),) for b in patterns]
            )
            rows = db.execute(CELL_SQL).fetchall()
            self.assertEqual([r["type"] for r in rows], ["real", "real"] + ["null"] * 4)
            for row in rows:
                self.assertEqual(row["guard"], 0)
                with self.assertRaises(Refused):
                    decode_wire(json.dumps(dict(row)).encode())

    def test_application_token_values(self) -> None:
        # Synthetic arithmetic values, not a current-schema integration fixture.
        with sqlite3.connect(":memory:") as db:
            db.row_factory = sqlite3.Row
            db.execute("CREATE TABLE synthetic_values(id INTEGER PRIMARY KEY,x REAL) STRICT")
            values = [0.0, 1.0, 10.0, 0.1, 7.0 / 60.0, 10.0 - 1.0 / 60.0]
            db.executemany("INSERT INTO synthetic_values(x) VALUES(?)", [(v,) for v in values])
            for value, row in zip(values, db.execute(CELL_SQL), strict=True):
                if value == 0:
                    with self.assertRaises(Refused):
                        decode_wire(json.dumps(dict(row)).encode())
                else:
                    self.assertEqual(
                        decode_wire(json.dumps(dict(row)).encode()), ["real", value.hex()]
                    )

    def test_sql_equality_cannot_distinguish_zero_sign(self) -> None:
        with sqlite3.connect(":memory:") as db:
            self.assertEqual(
                db.execute("SELECT ? = ?, ? IS ?", (-0.0, 0.0, -0.0, 0.0)).fetchone(), (1, 1)
            )
            self.assertEqual(db.execute("SELECT printf('%!.26g', ?)", (-0.0,)).fetchone()[0], "0.0")
            self.assertEqual(bits_of(-0.0), SIGN)


if __name__ == "__main__":
    unittest.main()
