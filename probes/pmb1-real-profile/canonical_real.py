"""Closed postbinding binary64 decoder; unselected and no provider adapter."""

from __future__ import annotations

import json
import math
import re
import struct
from typing import Any, cast

PROFILE = "pmb1-real-binding-binary64-v1"
MAX_WIRE_BYTES = 256


class Refused(ValueError):
    """Closed category only: no source payload or diagnostics."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise Refused(category)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_field")
        result[key] = value
    return result


def _nonfinite(_: str) -> Any:
    raise Refused("nonfinite_json")


def decode_wire(raw: bytes, *, expected_row_id: str) -> list[str]:
    """Preserve every finite received bit pattern, including both zero signs.

    Neither this decoder nor the profile name attests that the received bits
    equal a managed persisted cell. Source sufficiency remains explicitly NO-GO.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_WIRE_BYTES, "wire_bound")
    require(
        type(expected_row_id) is str
        and re.fullmatch(r"synthetic-[a-z0-9-]{1,64}", expected_row_id, re.ASCII) is not None,
        "expected_identity",
    )
    try:
        cell = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique,
            parse_constant=_nonfinite,
        )
    except UnicodeError, json.JSONDecodeError, RecursionError:
        raise Refused("invalid_json") from None
    require(
        type(cell) is dict and set(cell) == {"profile", "row_id", "type", "binary64"},
        "invalid_fields",
    )
    cell = cast(dict[str, Any], cell)
    require(cell["profile"] == PROFILE, "profile")
    require(cell["row_id"] == expected_row_id, "row_identity")
    require(cell["type"] == "real", "not_real")
    bits = cell["binary64"]
    require(
        type(bits) is str and re.fullmatch(r"[0-9a-f]{16}", bits, re.ASCII) is not None,
        "binary64_grammar",
    )
    bits = cast(str, bits)
    packed = bytes.fromhex(bits)
    # Exponent all ones means infinity or NaN; reject before unpack/conversion.
    require((int(bits, 16) >> 52) & 0x7FF != 0x7FF, "nonfinite_bits")
    value = struct.unpack(">d", packed)[0]
    require(math.isfinite(value), "nonfinite_value")
    canonical = value.hex()
    require(struct.pack(">d", float.fromhex(canonical)) == packed, "canonical_roundtrip")
    return ["real", canonical]
