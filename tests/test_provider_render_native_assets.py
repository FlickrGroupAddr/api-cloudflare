"""Exercise the real Lua helper without loading Lightroom or reading photos."""

import struct
import unittest
import zlib
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "probes/lightroom/FGA-ProviderRender-Qualification.lrplugin/NativeAssets.lua"


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(*extra, depth=8, color=2, pixels=None):
    # Valid original 8x8 RGB scanlines; decompression is outside the Lua helper.
    if pixels is None:
        pixels = zlib.compress((b"\0" + bytes(8 * 3 * (2 if depth == 16 else 1))) * 8)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, depth, color, 0, 0, 0))
        + b"".join(extra)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


def segment(marker, data):
    return bytes([255, marker]) + struct.pack(">H", len(data) + 2) + data


def jpeg(*extra, depth=8):
    return (
        b"\xff\xd8"
        + b"".join(extra)
        + segment(0xDB, b"\0" + bytes([1]) * 64)
        + segment(0xC4, b"\0\x01" + bytes(15) + b"\0")
        + segment(0xC4, b"\x10\x01" + bytes(15) + b"\0")
        + segment(0xC0, bytes([depth]) + struct.pack(">HH", 8, 8) + b"\x01\x01\x11\x00")
        + segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
        # One original grayscale block: zero DC difference, EOB, padding.
        + b"\x3f\xff\xd9"
    )


class NativeAssetsTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(encoding=None, unpack_returned_tuples=True)
        self.assets = self.lua.execute(MODULE.read_bytes())

    def inspect(self, data):
        observed = self.assets[b"inspect"](data)
        return None if observed is None else dict(observed)

    def test_tiff_has_independently_parsed_rgb_pixels_and_ifd(self):
        data = self.assets[b"tiff"]()
        self.assertEqual(data, self.assets[b"tiff"]())
        self.assertEqual(data[:4], b"II*\0")
        offset = struct.unpack_from("<I", data, 4)[0]
        count = struct.unpack_from("<H", data, offset)[0]
        entries = {}
        for at in range(offset + 2, offset + 2 + count * 12, 12):
            tag, kind, size, value = struct.unpack_from("<HHII", data, at)
            self.assertNotIn(tag, entries)
            entries[tag] = (kind, size, value)
        self.assertEqual(count, 10)
        self.assertEqual(entries[256], (4, 1, 8))
        self.assertEqual(entries[257], (4, 1, 8))
        self.assertEqual(entries[259], (3, 1, 1))
        self.assertEqual(entries[262], (3, 1, 2))
        self.assertEqual(entries[277], (3, 1, 3))
        self.assertEqual(entries[278], (4, 1, 8))
        self.assertEqual(entries[279], (4, 1, 192))
        self.assertEqual(entries[284], (3, 1, 1))
        self.assertEqual(entries[258][:2], (3, 3))
        self.assertEqual(struct.unpack_from("<HHH", data, entries[258][2]), (8, 8, 8))
        self.assertEqual(struct.unpack_from("<I", data, offset + 2 + count * 12)[0], 0)
        pixels = data[entries[273][2] :]
        self.assertEqual(len(pixels), 192)
        # Independent corner/row checks establish the original synthetic gradient.
        self.assertEqual(pixels[:6], bytes([0, 0, 0, 32, 0, 16]))
        self.assertEqual(pixels[24:27], bytes([0, 32, 16]))
        self.assertEqual(pixels[-3:], bytes([224, 224, 224]))

    def test_png_observations_never_claim_profile_verification(self):
        row = self.inspect(png(chunk(b"sRGB", b"\0")))
        self.assertEqual(
            row,
            {
                b"format": b"PNG",
                b"bitDepth": 8,
                b"width": 8,
                b"height": 8,
                b"srgbMarker": True,
                b"iccMarker": False,
                b"profileVerified": False,
            },
        )
        row = self.inspect(png(chunk(b"iCCP", b"test\0\0compressed")))
        assert row is not None
        self.assertTrue(row[b"iccMarker"])
        self.assertFalse(row[b"profileVerified"])
        self.assertFalse(row[b"srgbMarker"])
        deep = self.inspect(png(depth=16))
        assert deep is not None
        self.assertEqual(deep[b"bitDepth"], 16)

    def test_jpeg_observations_and_complete_icc_marker_sequence(self):
        def icc(sequence, count):
            return segment(0xE2, b"ICC_PROFILE\0" + bytes([sequence, count]) + b"x")

        row = self.inspect(jpeg(icc(2, 2), icc(1, 2)))
        self.assertEqual(
            row,
            {
                b"format": b"JPEG",
                b"bitDepth": 8,
                b"width": 8,
                b"height": 8,
                b"srgbMarker": False,
                b"iccMarker": True,
                b"profileVerified": False,
            },
        )
        for malformed in (
            jpeg(icc(1, 2)),
            jpeg(icc(0, 1)),
            jpeg(icc(1, 1), icc(1, 1)),
            jpeg(icc(1, 2), icc(2, 3)),
            jpeg(depth=12),
        ):
            self.assertIsNone(self.inspect(malformed))

    def test_png_malformed_chunk_boundaries_order_and_crc_fail_closed(self):
        valid = png()
        bad_crc = bytearray(valid)
        bad_crc[20] ^= 1
        cases = [
            bytes(bad_crc),
            valid + b"x",
            png(pixels=b""),
            png(depth=3),
            png(color=3),
            png(chunk(b"sRGB", b"\4")),
            png(chunk(b"sRGB", b"\0"), chunk(b"sRGB", b"\0")),
            png(chunk(b"iCCP", b"test\0\1x")),
            png(chunk(b"iCCP", b"test\0\0x"), chunk(b"sRGB", b"\0")),
            png(chunk(b"ABCD", b"")),
            valid[:8] + chunk(b"IEND", b"") + valid[8:],
            valid[:8] + struct.pack(">I", 0xFFFFFFFF) + b"IHDR",
        ]
        for data in cases:
            with self.subTest(data=data[:16]):
                self.assertIsNone(self.inspect(data))

    def test_truncations_and_jpeg_malformed_markers_fail_closed(self):
        for data in (png(), jpeg()):
            for length in range(len(data)):
                self.assertIsNone(self.inspect(data[:length]), length)
        for data in (
            jpeg() + b"x",
            b"\xff\xd8\xff\xd9",
            jpeg()[:-2] + b"\xff",
            b"\xff\xd8" + segment(0xDA, b"\x01\x01\0\0\x3f\0") + b"\xff\xd9",
            b"\xff\xd8\xff\xe1\0\1",
            b"\xff\xd8\xff\xe1\xff\xff",
        ):
            self.assertIsNone(self.inspect(data))

    def test_limits_and_non_bytes_inputs(self):
        for data in (None, 1, True, b"x" * (1024 * 1024 + 1), b"II*\0"):
            self.assertIsNone(self.inspect(data))
        self.assertIsNone(self.inspect(png(*(chunk(b"tEXt", b"") for _ in range(4096)))))


if __name__ == "__main__":
    unittest.main()
