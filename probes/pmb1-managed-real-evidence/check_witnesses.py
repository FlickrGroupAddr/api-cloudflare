"""Check sanitized request fixtures only; no SQL, provider or database execution."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    packet = json.loads((HERE / "witnesses.json").read_text(encoding="utf-8"))
    assert packet["status"] == "UNSENT-unexecuted-witness-questions"
    assert packet["managed_observation"] == "not-performed"
    identities: set[str] = set()
    patterns: set[str] = set()
    for item in packet["finite_bit_witnesses"]:
        assert item["id"].startswith("synthetic-") and item["id"] not in identities
        identities.add(item["id"])
        bits = item["requested_insertion_bits"]
        assert len(bits) == 16 and all(c in "0123456789abcdef" for c in bits)
        assert bits not in patterns
        patterns.add(bits)
        exponent = (int(bits, 16) >> 52) & 0x7FF
        assert exponent != 0x7FF
        value = struct.unpack(">d", bytes.fromhex(bits))[0]
        assert math.isfinite(value)
        assert struct.pack(">d", value).hex() == bits
        assert value.hex() == item["codec_reference_hex"]
        assert item["actual_persisted_type"] is None
        assert item["actual_persisted_bits"] is None
        assert item["delivered_number_bits"] is None
        assert item["oracle_provenance"] is None
    assert {"0000000000000000", "8000000000000000"} <= patterns
    assert {"0000000000000001", "8000000000000001"} <= patterns
    assert {"000fffffffffffff", "0010000000000000"} <= patterns
    assert {"3fefffffffffffff", "3ff0000000000000", "3ff0000000000001"} <= patterns
    assert {"7fefffffffffffff", "ffefffffffffffff"} <= patterns
    for item in packet["nonfinite_refusal_patterns"]:
        assert (int(item, 16) >> 52) & 0x7FF == 0x7FF
    assert set(packet["type_controls"]) == {"integer", "real", "text", "blob", "null"}
    assert len(packet["affinity_cases"]) == 4
    assert len(packet["lifecycle_cases"]) == 5
    evidence = json.loads((HERE / "source-evidence.json").read_text(encoding="utf-8"))
    assert evidence["request_delivery"] == "UNSENT"
    assert evidence["integration_eligible"] is False
    for key, value in evidence.items():
        if key.startswith("managed_") and key != "managed_observation":
            assert value is None
    assert evidence["supported_all_finite_persisted_source_guarantee"] is None
    assert evidence["supported_independent_persisted_bit_channel"] is None
    print(f"PASS: {len(patterns)} finite fixture references; managed results remain unknown")


if __name__ == "__main__":
    main()
