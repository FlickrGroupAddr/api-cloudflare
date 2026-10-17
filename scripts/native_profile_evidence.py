"""Bounded PNG/iCCP identity evidence; never decodes pixels or evaluates ICC transforms.

The sole reference is ICC's sRGB2014.icc (3024 bytes), fetched independently
from https://registry.color.org/rgb-registry/profiles/sRGB2014.icc on 2026-10-17.
Its SHA2-256 pin is compiled below, never supplied by the observed PNG.
Provenance/semantics: https://registry.color.org/rgb-registry/srgbprofiles
License: https://registry.color.org/profile-library/ (ICC's general profile terms).
Framing/CRC/iCCP: https://www.w3.org/TR/2025/REC-png-3-20250624/

A match establishes exact embedded profile identity only, not correct pixel
conversion, host behavior, or fixture provenance. A mismatch does not establish
that another profile is not sRGB. Markers and profile names cannot pass identity.
Only a newly authorized synthetic fixture can supply new host observations;
this tool cannot retroactively qualify deleted outputs or older receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

MAX_PNG_BYTES = 32 * 1024 * 1024
MAX_PROFILE_BYTES = 1024 * 1024
MAX_CHUNKS = 4096
REFERENCE_ID = "icc-srgb2014-2015-revision"
REFERENCE_BYTES = 3024
REFERENCE_SHA2_256 = "384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
Evidence = dict[str, str | int | None]


class EvidenceError(ValueError):
    """Fixed, sanitized reason for incomplete profile evidence."""


def _result(
    reason: str, profile: bytes | None = None, *, input_identity: tuple[str, int] | None = None
) -> Evidence:
    digest = hashlib.sha256(profile).hexdigest() if profile is not None else None
    match = digest == REFERENCE_SHA2_256 and len(profile or b"") == REFERENCE_BYTES
    return {
        "status": "inconclusive" if profile is None else "match" if match else "mismatch",
        "reason": reason
        if profile is None
        else "exact-reference-match"
        if match
        else "different-profile-bytes",
        "input_png_sha2_256": input_identity[0] if input_identity is not None else None,
        "input_png_bytes": input_identity[1] if input_identity is not None else None,
        "embedded_profile_sha2_256": digest,
        "embedded_profile_bytes": len(profile) if profile is not None else None,
        "reference_id": REFERENCE_ID,
        "reference_sha2_256": REFERENCE_SHA2_256,
    }


def _inflate_profile(payload: bytes) -> bytes:
    separator = payload.find(b"\0", 0, 80)
    if separator < 1 or separator > 79 or separator + 2 >= len(payload):
        raise EvidenceError("invalid-iccp-framing")
    name = payload[:separator]
    if (
        any(not (32 <= value <= 126 or 161 <= value <= 255) for value in name)
        or name.startswith(b" ")
        or name.endswith(b" ")
        or b"  " in name
        or payload[separator + 1] != 0
    ):
        raise EvidenceError("invalid-iccp-framing")
    try:
        inflater = zlib.decompressobj()
        profile = inflater.decompress(payload[separator + 2 :], MAX_PROFILE_BYTES + 1)
    except zlib.error:
        raise EvidenceError("invalid-profile-compression") from None
    if len(profile) > MAX_PROFILE_BYTES or inflater.unconsumed_tail:
        raise EvidenceError("profile-size-limit")
    if not inflater.eof or inflater.unused_data:
        raise EvidenceError("invalid-profile-compression")
    if (
        len(profile) < 132
        or int.from_bytes(profile[:4], "big") != len(profile)
        or profile[36:40] != b"acsp"
        or profile[16:20] != b"RGB "
    ):
        raise EvidenceError("invalid-rgb-profile-header")
    return profile


def _extract_profile(data: bytes) -> bytes:
    if len(data) > MAX_PNG_BYTES:
        raise EvidenceError("png-size-limit")
    if not data.startswith(PNG_SIGNATURE):
        raise EvidenceError("invalid-png-signature")
    offset = len(PNG_SIGNATURE)
    count = 0
    profile: bytes | None = None
    seen_palette = False
    seen_data = False
    ended_data = False
    while offset < len(data):
        count += 1
        if count > MAX_CHUNKS:
            raise EvidenceError("chunk-count-limit")
        if len(data) - offset < 12:
            raise EvidenceError("truncated-chunk")
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + size
        if size > 0x7FFFFFFF or end > len(data):
            raise EvidenceError("invalid-chunk-size")
        if any(not (65 <= value <= 90 or 97 <= value <= 122) for value in kind) or kind[2] & 32:
            raise EvidenceError("invalid-chunk-type")
        payload = data[offset + 8 : offset + 8 + size]
        crc = int.from_bytes(data[offset + 8 + size : end], "big")
        if zlib.crc32(payload, zlib.crc32(kind)) != crc:
            raise EvidenceError("chunk-crc-mismatch")
        if count == 1 and kind != b"IHDR":
            raise EvidenceError("missing-first-ihdr")
        if kind == b"IHDR":
            if count != 1 or size != 13:
                raise EvidenceError("invalid-ihdr")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (
                not 1 <= width <= 0x7FFFFFFF
                or not 1 <= height <= 0x7FFFFFFF
                or depth not in (8, 16)
                or color not in (2, 6)
                or compression != 0
                or filtering != 0
                or interlace not in (0, 1)
            ):
                raise EvidenceError("unsupported-ihdr")
        elif kind == b"iCCP":
            if profile is not None or seen_palette or seen_data:
                raise EvidenceError("duplicate-or-misordered-iccp")
            profile = _inflate_profile(payload)
        elif kind in (b"sRGB", b"cICP", b"acTL", b"fcTL", b"fdAT"):
            raise EvidenceError("unsupported-competing-color-or-animation")
        elif kind == b"PLTE":
            if seen_palette or seen_data or size == 0 or size > 768 or size % 3:
                raise EvidenceError("invalid-plte")
            seen_palette = True
        elif kind == b"IDAT":
            if ended_data:
                raise EvidenceError("nonconsecutive-idat")
            seen_data = True
        elif kind == b"IEND":
            if size != 0 or not seen_data or end != len(data):
                raise EvidenceError("invalid-iend")
            if profile is None:
                raise EvidenceError("missing-embedded-profile")
            return profile
        elif not kind[0] & 32:
            raise EvidenceError("unknown-critical-chunk")
        if seen_data and kind != b"IDAT":
            ended_data = True
        offset = end
    raise EvidenceError("missing-iend")


def analyze_png(data: bytes) -> Evidence:
    """Return only finite metadata; malformed or unsupported evidence cannot pass."""
    if len(data) > MAX_PNG_BYTES:
        return _result("png-size-limit")
    input_identity = (hashlib.sha256(data).hexdigest(), len(data))
    try:
        return _result("", _extract_profile(data), input_identity=input_identity)
    except EvidenceError as error:
        return _result(str(error), input_identity=input_identity)


def analyze_file(path: Path) -> Evidence:
    """Read at most the fixed limit plus one byte; do not expose the private path."""
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_PNG_BYTES + 1)
    except OSError:
        return _result("input-unavailable")
    return analyze_png(data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "PNG profile evidence").split("\n", 1)[0]
    )
    parser.add_argument("png", type=Path, help="exact privately staged synthetic PNG")
    arguments = parser.parse_args()
    result = analyze_file(arguments.png)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "match" else 1


if __name__ == "__main__":
    sys.exit(main())
