"""Hostile synthetic PNG/ICC checks; no profile binary or native qualification."""

import binascii
import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts import native_profile_evidence as evidence

SIGNATURE = b"\x89PNG\r\n\x1a\n"
PIN = "384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a"


def chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload))
    )


def synthetic_profile() -> bytes:
    # Structurally shaped, deliberately untrusted ICC; its name must confer no identity.
    header = bytearray(132)
    header[:4] = struct.pack(">I", len(header))
    header[16:20] = b"RGB "
    header[36:40] = b"acsp"
    return bytes(header)


def iccp(profile: bytes, name: bytes = b"sRGB2014") -> bytes:
    return chunk(b"iCCP", name + b"\0\0" + zlib.compress(profile))


def png(*extra: bytes) -> bytes:
    return (
        SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + b"".join(extra)
        + chunk(b"IDAT", zlib.compress(b"\0\0\0\0"))
        + chunk(b"IEND", b"")
    )


class NativeProfileEvidenceTests(unittest.TestCase):
    def assert_untrusted(self, data: bytes):
        result = evidence.analyze_png(data)
        self.assertIn(result["status"], ("inconclusive", "mismatch"))
        self.assertNotEqual(result["status"], "match")
        return result

    def test_reference_identity_is_independent_fixed_public_reference(self):
        result = evidence.analyze_png(png(iccp(synthetic_profile())))
        self.assertEqual(result["reference_sha2_256"], PIN)
        self.assertTrue(result["reference_id"])

    def test_plausible_same_name_profile_is_mismatch(self):
        first = evidence.analyze_png(png(iccp(synthetic_profile())))
        second = evidence.analyze_png(png(iccp(synthetic_profile(), b"other name")))
        self.assertEqual(first["status"], "mismatch")
        self.assertEqual(second["status"], "mismatch")
        self.assertEqual(first["embedded_profile_bytes"], 132)
        self.assertEqual(first["embedded_profile_sha2_256"], second["embedded_profile_sha2_256"])
        self.assertNotEqual(first["embedded_profile_sha2_256"], PIN)

    def test_srgb_marker_alone_never_proves_profile_identity(self):
        self.assert_untrusted(png(chunk(b"sRGB", b"\0")))
        self.assert_untrusted(png())

    def test_every_truncation_of_small_png_is_rejected(self):
        valid = png(iccp(synthetic_profile()))
        for size in range(len(valid)):
            with self.subTest(size=size):
                self.assert_untrusted(valid[:size])

    def test_crc_corruption_for_each_chunk_is_rejected(self):
        valid = png(iccp(synthetic_profile()))
        offset = len(SIGNATURE)
        while offset < len(valid):
            length = struct.unpack(">I", valid[offset : offset + 4])[0]
            crc_offset = offset + 8 + length
            damaged = bytearray(valid)
            damaged[crc_offset] ^= 1
            with self.subTest(chunk=valid[offset + 4 : offset + 8]):
                result = self.assert_untrusted(bytes(damaged))
                self.assertEqual(result["status"], "inconclusive")
            offset = crc_offset + 4

    def test_hostile_framing_and_duplicate_profiles_are_inconclusive(self):
        cases = (
            b"not a PNG",
            png(iccp(synthetic_profile())) + b"trailing",
            SIGNATURE + struct.pack(">I", 0xFFFFFFFF) + b"iCCP",
            png(iccp(synthetic_profile()), iccp(synthetic_profile())),
            SIGNATURE + chunk(b"IEND", b""),
            png(chunk(b"ABCD", b"unknown critical chunk")),
        )
        for data in cases:
            with self.subTest(size=len(data)):
                self.assertEqual(self.assert_untrusted(data)["status"], "inconclusive")

    def test_iccp_name_method_and_compressed_stream_refusals(self):
        compressed = zlib.compress(synthetic_profile())
        payloads = (
            b"sRGB2014",
            b"\0\0" + compressed,
            b"x" * 80 + b"\0\0" + compressed,
            b"sRGB2014\0\1" + compressed,
            b"sRGB2014\0\0not zlib",
            b"sRGB2014\0\0" + compressed[:-1],
            b"sRGB2014\0\0" + compressed + b"trailing",
            b"sRGB2014\0\0" + compressed + compressed,
        )
        for payload in payloads:
            with self.subTest(size=len(payload)):
                self.assertEqual(
                    self.assert_untrusted(png(chunk(b"iCCP", payload)))["status"], "inconclusive"
                )

    def test_decompression_bomb_and_excess_chunk_count_are_bounded(self):
        bomb = b"x" * (evidence.MAX_PROFILE_BYTES + 1)
        self.assertEqual(self.assert_untrusted(png(iccp(bomb)))["status"], "inconclusive")
        chunks = [chunk(b"tEXt", b"a\0b")] * (evidence.MAX_CHUNKS + 1)
        self.assertEqual(self.assert_untrusted(png(*chunks))["status"], "inconclusive")

    def test_profile_header_lies_do_not_become_identity_evidence(self):
        for offset, replacement in ((0, struct.pack(">I", 999)), (16, b"CMYK"), (36, b"nope")):
            profile = bytearray(synthetic_profile())
            profile[offset : offset + 4] = replacement
            with self.subTest(offset=offset):
                self.assertEqual(
                    self.assert_untrusted(png(iccp(bytes(profile))))["status"], "inconclusive"
                )

    def test_input_byte_limit_and_missing_file_have_sanitized_results(self):
        self.assertEqual(
            self.assert_untrusted(b"x" * (evidence.MAX_PNG_BYTES + 1))["status"], "inconclusive"
        )
        with tempfile.TemporaryDirectory() as directory:
            private_path = Path(directory) / "private-synthetic-name.png"
            result = evidence.analyze_file(private_path)
            self.assertEqual(result["status"], "inconclusive")
            self.assertNotIn("private-synthetic-name", str(result))
            private_path.write_bytes(png(iccp(synthetic_profile())))
            self.assertEqual(evidence.analyze_file(private_path)["status"], "mismatch")

    def test_report_binds_exact_bounded_input_even_when_malformed(self):
        samples = (png(iccp(synthetic_profile())), b"invalid synthetic PNG", b"")
        identities = []
        for sample in samples:
            result = evidence.analyze_png(sample)
            self.assertEqual(result["input_png_bytes"], len(sample))
            self.assertEqual(result["input_png_sha2_256"], hashlib.sha256(sample).hexdigest())
            identities.append(result["input_png_sha2_256"])
        self.assertEqual(len(set(identities)), len(samples))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            path.write_bytes(samples[0])
            self.assertEqual(evidence.analyze_file(path), evidence.analyze_png(samples[0]))
            unavailable = evidence.analyze_file(path.parent / "missing.png")
            self.assertIsNone(unavailable["input_png_sha2_256"])
            self.assertIsNone(unavailable["input_png_bytes"])
        oversized = evidence.analyze_png(b"x" * (evidence.MAX_PNG_BYTES + 1))
        self.assertIsNone(oversized["input_png_sha2_256"])
        self.assertIsNone(oversized["input_png_bytes"])


if __name__ == "__main__":
    unittest.main()
