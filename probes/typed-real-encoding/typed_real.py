"""Unselected local REAL experiment. No provider adapter or reader integration."""

from __future__ import annotations

import json
import math
import re
import struct
from fractions import Fraction
from typing import Any, cast

MAX_FINITE = 0x7FEFFFFFFFFFFFFF
SIGN = 1 << 63
MAX_WIRE_BYTES = 256
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)\.[0-9]+(?:e[+-][0-9]{2,3})?", re.ASCII)

# Fixed synthetic table, not a general SQL generator. All three fields refer to
# the same direct column in one SELECT. The caller retains row identity/order.
CELL_SQL = """SELECT typeof(x) AS type, printf('%!.26g', x) AS decimal,
CASE WHEN typeof(x) = 'real' AND x != 0.0
AND x BETWEEN -1.7976931348623157e308 AND 1.7976931348623157e308
AND CAST(printf('%!.26g', x) AS REAL) = x THEN 1 ELSE 0 END AS guard
FROM synthetic_values ORDER BY id"""


class Refused(ValueError):
    """Closed synthetic failure; no payload in diagnostics."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise Refused(category)


def bits_of(value: float) -> int:
    return int.from_bytes(struct.pack(">d", value), "big")


def from_bits(bits: int) -> float:
    return struct.unpack(">d", bits.to_bytes(8, "big"))[0]


def positive_rational(bits: int) -> Fraction:
    """Exact positive binary64 value from integer fields, without float parsing."""
    require(type(bits) is int and 0 <= bits <= MAX_FINITE, "invalid_oracle_bits")
    exponent, fraction = bits >> 52, bits & ((1 << 52) - 1)
    significand = fraction if exponent == 0 else (1 << 52) + fraction
    power = -1074 if exponent == 0 else exponent - 1075
    if power >= 0:
        return Fraction(significand << power)
    return Fraction(significand, 1 << -power)


def rounds_to(decimal: Fraction, bits: int) -> bool:
    """Independent exact midpoint oracle for nonzero finite round-to-nearest/even.

    The overflow neighbor is the mathematical 2**1024, not a floating infinity.
    Negative values are symmetric. Signed zeros are deliberately outside profile.
    """
    require(type(bits) is int and 0 <= bits < 1 << 64, "invalid_oracle_bits")
    magnitude = bits & (SIGN - 1)
    if not 0 < magnitude <= MAX_FINITE or decimal == 0:
        return False
    if (decimal < 0) != bool(bits & SIGN):
        return False
    value = positive_rational(magnitude)
    previous = positive_rational(magnitude - 1)
    following = Fraction(1 << 1024) if magnitude == MAX_FINITE else positive_rational(magnitude + 1)
    lower, upper = (previous + value) / 2, (value + following) / 2
    exact = abs(decimal)
    if magnitude & 1:
        return lower < exact < upper
    return lower <= exact <= upper


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_field")
        result[key] = value
    return result


def _nonfinite(_: str) -> Any:
    raise Refused("nonfinite_json")


def decode_wire(raw: bytes) -> list[str]:
    """Decode one closed bounded typed cell, never a whole-capture authorization.

    A true guard is a trusted-engine assertion, not proof of response authenticity
    or agreement between the engine parser and this exact rounding oracle.
    """
    require(type(raw) is bytes and len(raw) <= MAX_WIRE_BYTES, "wire_bound")
    try:
        cell = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique,
            parse_constant=_nonfinite,
        )
    except UnicodeError, json.JSONDecodeError, RecursionError:
        raise Refused("invalid_json") from None
    require(type(cell) is dict and set(cell) == {"type", "decimal", "guard"}, "invalid_fields")
    cell = cast(dict[str, Any], cell)
    require(cell["type"] == "real", "not_real")
    require(type(cell["guard"]) is int and cell["guard"] == 1, "source_guard")
    spelling = cell["decimal"]
    require(type(spelling) is str and 0 < len(spelling) <= 64, "decimal_bound")
    spelling = cast(str, spelling)
    require(DECIMAL.fullmatch(spelling) is not None, "decimal_grammar")
    coefficient, _, exponent = spelling.partition("e")
    # Alternate-form-2 appends .0 to an integral fixed-notation result even
    # when its integer portion already consumes all 26 significant digits.
    # That sole fractional zero is syntax, not another precision digit.
    significant = coefficient.removesuffix(".0").lstrip("-").replace(".", "").lstrip("0")
    require(0 < len(significant) <= 26, "decimal_precision_or_zero")
    require(not exponent or abs(int(exponent)) <= 324, "decimal_exponent")
    value = float(spelling)
    require(math.isfinite(value) and value != 0.0, "nonfinite_or_zero")
    bits = bits_of(value)
    require(rounds_to(Fraction(spelling), bits), "decoder_rounding")
    canonical = value.hex()
    require(bits_of(float.fromhex(canonical)) == bits, "canonical_roundtrip")
    return ["real", canonical]
