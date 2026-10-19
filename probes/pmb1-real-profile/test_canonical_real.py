"""Synthetic source-oracle and codec checks, never managed D1 qualification."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import struct
import subprocess
import unittest
from pathlib import Path
from typing import Any

from canonical_real import PROFILE, Refused, decode_wire

HERE = Path(__file__).resolve().parent
BOUNDARIES = (
    0x0000000000000000,
    0x0000000000000001,
    0x0000000000000002,
    0x000FFFFFFFFFFFFF,
    0x0010000000000000,
    0x0010000000000001,
    0x3FB999999999999A,
    0x3FEFFFFFFFFFFFFF,
    0x3FF0000000000000,
    0x3FF0000000000001,
    0x4534ADF4B7320334,  # 1e25: predecessor profile's fixed-notation boundary.
    0x7FEFFFFFFFFFFFFE,
    0x7FEFFFFFFFFFFFFF,
)


def from_bits(bits: int) -> float:
    return struct.unpack(">d", bits.to_bytes(8, "big"))[0]


def bits_of(value: float) -> str:
    return struct.pack(">d", value).hex()


def wire(bits: Any = "3ff0000000000000", **changes: Any) -> bytes:
    cell = {"profile": PROFILE, "row_id": "synthetic-cell", "type": "real", "binary64": bits}
    cell.update(changes)
    return json.dumps(cell, separators=(",", ":")).encode()


def encode_via_node(patterns: list[str], row_ids: list[str] | None = None) -> list[str]:
    # Local fixture process only. Bits enter as strings, so this test does not
    # erase -0 by placing a numeric fixture in JSON before the JS encoder.
    if row_ids is None:
        row_ids = [f"synthetic-{index}" for index in range(len(patterns))]
    fixtures = [
        {"binary64": bits, "row_id": identity}
        for bits, identity in zip(patterns, row_ids, strict=True)
    ]
    result = subprocess.run(
        ["node", str(HERE / "fixture-driver.mjs")],
        input=json.dumps(fixtures),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


class SourcePinTests(unittest.TestCase):
    def test_source_pins_are_current_and_cannot_assert_hosted_fidelity(self) -> None:
        pins = json.loads((HERE / "source-pins.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(pins["status"], "source-no-go")
        self.assertIsNone(pins["managed_engine_identity"])
        self.assertIsNone(pins["managed_binding_transport_identity"])
        self.assertEqual(pins["hosted_observation"], "not-performed")
        root = HERE.parent.parent
        for relative, expected in pins["sha256"].items():
            target = (root / relative).resolve()
            self.assertTrue(target.is_relative_to(root.resolve()))
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)


class CodecTests(unittest.TestCase):
    def test_known_canonical_values_and_both_zero_signs(self) -> None:
        for pattern, expected in (
            ("0000000000000000", "0x0.0p+0"),
            ("8000000000000000", "-0x0.0p+0"),
            ("0000000000000001", "0x0.0000000000001p-1022"),
            ("0010000000000000", "0x1.0000000000000p-1022"),
            ("3ff0000000000000", "0x1.0000000000000p+0"),
            ("7fefffffffffffff", "0x1.fffffffffffffp+1023"),
        ):
            self.assertEqual(
                decode_wire(wire(pattern), expected_row_id="synthetic-cell"), ["real", expected]
            )

    def test_cross_language_every_finite_exponent_and_boundaries(self) -> None:
        patterns = {
            f"{sign | (exponent << 52) | fraction:016x}"
            for exponent in range(2047)
            for fraction in (0, (1 << 52) - 1)
            for sign in (0, 1 << 63)
        }
        patterns.update(f"{bits | sign:016x}" for bits in BOUNDARIES for sign in (0, 1 << 63))
        ordered = sorted(patterns)
        for offset in range(0, len(ordered), 5000):
            chunk = ordered[offset : offset + 5000]
            for index, (pattern, encoded) in enumerate(
                zip(chunk, encode_via_node(chunk), strict=True)
            ):
                cell = decode_wire(encoded.encode(), expected_row_id=f"synthetic-{index}")
                self.assertEqual(bits_of(float.fromhex(cell[1])), pattern)

    def test_nonfinite_patterns_refuse(self) -> None:
        for bits in (
            "7ff0000000000000",
            "fff0000000000000",
            "7ff8000000000000",
            "fff8000000000000",
            "7ff0000000000001",
            "fff0000000000001",
        ):
            with self.assertRaisesRegex(Refused, "nonfinite_bits"):
                decode_wire(wire(bits), expected_row_id="synthetic-cell")

    def test_closed_wire_bounds_grammar_identity_and_tags(self) -> None:
        bad = [
            wire(profile="other"),
            wire(row_id="synthetic-other"),
            wire(extra=True),
            b"{}",
            b"[]",
            b"null",
            b"{",
            b"\xff",
            b" " * 257,
            wire(None),
            wire(1),
            wire("3FF0000000000000"),
            wire("0x3ff0000000000000"),
            wire("3ff0000000000000\n"),
            wire("0" * 15),
            wire("0" * 17),
            wire("g" * 16),
            wire("0" * 10_000),
            b'{"profile":NaN}',
            b'{"profile":Infinity}',
            wire().replace(b'"type":"real"', b'"type":"real","type":"real"'),
        ]
        bad.extend(wire(type=tag) for tag in ("integer", "text", "blob", "null", None, 1))
        for raw in bad:
            with self.subTest(raw_length=len(raw)), self.assertRaises(Refused):
                decode_wire(raw, expected_row_id="synthetic-cell")
        with self.assertRaises(Refused):
            decode_wire(wire(), expected_row_id="synthetic-cell\n")

    def test_prebinding_loss_passes_codec_but_independent_source_bits_detect_it(self) -> None:
        for actual, substituted in (
            ("8000000000000000", "0000000000000000"),
            ("3ff0000000000001", "3ff0000000000000"),
        ):
            decoded = decode_wire(wire(substituted), expected_row_id="synthetic-cell")
            self.assertEqual(bits_of(float.fromhex(decoded[1])), substituted)
            self.assertNotEqual(bits_of(float.fromhex(decoded[1])), actual)


class PersistedSourceTests(unittest.TestCase):
    def test_untyped_and_blob_columns_retain_negative_zero_across_reopen(self) -> None:
        expected = [f"{bits | sign:016x}" for bits in BOUNDARIES for sign in (0, 1 << 63)]
        for declaration in ("", "BLOB"):
            with sqlite3.connect(":memory:") as connection:
                connection.execute(
                    f"CREATE TABLE synthetic_values(id TEXT PRIMARY KEY, x {declaration})"
                )
                connection.executemany(
                    "INSERT INTO synthetic_values VALUES(?, ?)",
                    [
                        (f"synthetic-{i:04d}", from_bits(int(bits, 16)))
                        for i, bits in enumerate(expected)
                    ],
                )
                for reopened in (False, True):
                    with sqlite3.connect(":memory:") as reader:
                        reader.deserialize(connection.serialize())
                        source = reader if reopened else connection
                        rows = source.execute(
                            "SELECT id, typeof(x), x FROM synthetic_values ORDER BY id"
                        ).fetchall()
                        self.assertEqual([bits_of(row[2]) for row in rows], expected)
                        self.assertTrue(all(row[1] == "real" for row in rows))
                        encoded = encode_via_node(
                            [bits_of(row[2]) for row in rows], [row[0] for row in rows]
                        )
                        for i, item in enumerate(encoded):
                            decoded = decode_wire(item.encode(), expected_row_id=rows[i][0])
                            self.assertEqual(bits_of(float.fromhex(decoded[1])), expected[i])

    def test_real_affinity_normalization_is_not_codec_damage(self) -> None:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE t(x REAL) STRICT")
            connection.executemany("INSERT INTO t VALUES(?)", [(-0.0,), (+0.0,)])
            with sqlite3.connect(":memory:") as reopened:
                reopened.deserialize(connection.serialize())
                for reader in (connection, reopened):
                    rows = reader.execute("SELECT typeof(x), x FROM t").fetchall()
                    self.assertEqual(rows, [("real", 0.0), ("real", 0.0)])
                    self.assertEqual([bits_of(row[1]) for row in rows], ["0" * 16] * 2)

    def test_storage_tags_and_nonfinite_normalization_are_observed_separately(self) -> None:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE t(x)")
            values = (1, 1.0, "1", b"1", None, math.inf, -math.inf, math.nan)
            connection.executemany("INSERT INTO t VALUES(?)", [(value,) for value in values])
            rows = connection.execute("SELECT typeof(x), x FROM t").fetchall()
            self.assertEqual(
                [row[0] for row in rows],
                ["integer", "real", "text", "blob", "null", "real", "real", "null"],
            )
            self.assertTrue(math.isinf(rows[5][1]) and math.isinf(rows[6][1]))
            self.assertIsNone(rows[7][1])


if __name__ == "__main__":
    unittest.main()
