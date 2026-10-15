"""Check isolated publisher preflight in actual Lua 5.1 with synthetic SDK I/O."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

SOURCE = Path(__file__).resolve().parents[1] / "clients/lightroom/publisher"


class PublisherPreflightTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.core = self.lua.execute((SOURCE / "PreflightCore.lua").read_text())
        self.lua.globals().preflightCore = self.core
        self.lua.execute("""
            files, calls = {}, { render = 0, inspect = 0, read = 0 }
            function require(name)
                assert(name == 'PreflightCore')
                return preflightCore
            end
            function import(name)
                if name == 'LrTasks' then return { pcall = pcall } end
                assert(name == 'LrFileUtils') -- no network/catalog capability
                return {
                    exists = function(path)
                        calls.inspect = calls.inspect + 1
                        local file = files[path]
                        if file and file.inspectError then error('private path') end
                        return file and file.kind or nil
                    end,
                    fileAttributes = function(path)
                        return { fileSize = files[path] and files[path].size }
                    end,
                    readFile = function(path)
                        calls.read = calls.read + 1
                        if files[path].unreadable then error('private path') end
                        return files[path].contents
                    end,
                }
            end
            function rendition(path, success, throws)
                return { waitForRender = function()
                    calls.render = calls.render + 1
                    if throws then error('private render detail') end
                    return success, path
                end }
            end
        """)
        self.adapter = self.lua.execute((SOURCE / "RenderPreflight.lua").read_text())
        self.lua.globals().adapter = self.adapter

    def run_lua(self, code):
        return self.lua.execute(code)

    def test_exact_byte_limit_boundaries(self):
        for size, expected in ((9, "ready"), (10, "ready"), (11, "oversized")):
            with self.subTest(size=size):
                result = self.run_lua(f"""
                    files['photo'] = {{kind='file', size={size},
                        contents=string.rep('x', {size})}}
                    return adapter.checkRendition(rendition('photo', true), 10)
                """)
                self.assertEqual(result["code"], expected)
                self.assertEqual(result["sizeBytes"], size)
                self.assertEqual(result["maximumBytes"], 10)
                if size == 11:
                    self.assertIn("11 bytes", result["message"])
                    self.assertIn("10 bytes", result["message"])
                    self.assertIn("Nothing was uploaded", result["message"])
        # Oversized contents are never read.
        self.assertEqual(self.lua.globals().calls["read"], 2)

    def test_missing_directory_and_empty_file(self):
        for setup, expected in (
            ("files.photo = nil", "missing_file"),
            ("files.photo = {kind='directory', size=5}", "missing_file"),
            ("files.photo = {kind='file', size=0, contents=''}", "empty_file"),
        ):
            with self.subTest(expected=expected):
                result = self.run_lua(
                    setup + "\nreturn adapter.checkRendition(rendition('photo', true), 10)"
                )
                self.assertEqual(result["code"], expected)
        self.assertEqual(self.lua.globals().calls["read"], 0)

    def test_unreadable_and_size_change(self):
        for body, expected in (
            ("unreadable=true", "unreadable_file"),
            ("contents='xx'", "file_changed"),
        ):
            result = self.run_lua(f"""
                files.photo = {{kind='file', size=5, {body}}}
                return adapter.checkRendition(rendition('photo', true), 10)
            """)
            self.assertEqual(result["code"], expected)
            self.assertIsNone(result["path"])
            self.assertIsNone(result["contents"])

    def test_render_failure_or_exception_does_not_inspect(self):
        for expression in (
            "rendition('private render detail', false)",
            "rendition('photo', true, true)",
            "rendition(nil, true)",
        ):
            result = self.run_lua(f"return adapter.checkRendition({expression}, 10)")
            self.assertEqual(result["code"], "render_failed")
        self.assertEqual(self.lua.globals().calls["inspect"], 0)

    def test_invalid_limit_refuses_render(self):
        for value in ("nil", "0", "-1", "1.5", "0/0", "math.huge", "'10'"):
            result = self.run_lua(
                f"return adapter.checkRendition(rendition('photo', true), {value})"
            )
            self.assertEqual(result["code"], "invalid_limit")
        self.assertEqual(self.lua.globals().calls["render"], 0)

    def test_invalid_file_size_refuses_read(self):
        for value in ("nil", "-1", "1.5", "0/0", "math.huge", "'5'"):
            result = self.run_lua(f"""
                files.photo = {{kind='file', size={value}}}
                return adapter.checkRendition(rendition('photo', true), 10)
            """)
            self.assertEqual(result["code"], "invalid_size")
        self.assertEqual(self.lua.globals().calls["read"], 0)

    def test_each_photo_survives_neighbour_failure(self):
        results = self.run_lua("""
            files.good = {kind='file', size=5, contents='12345'}
            files.bad = {kind='file', inspectError=true}
            return adapter.checkAll({
                rendition('bad', true), rendition('good', true),
                rendition('missing', true), rendition('good', true)
            }, 10)
        """)
        self.assertEqual(len(results), 4)
        self.assertEqual(
            [results[i]["code"] for i in range(1, 5)],
            ["file_inspection_failed", "ready", "missing_file", "ready"],
        )

    def test_preflight_does_not_change_rendition_or_expose_image(self):
        result = self.run_lua("""
            files['unicode-photo'] = {kind='file', size=3, contents='png'}
            local item = rendition('unicode-photo', true)
            item.format = 'PNG'
            local result = adapter.checkRendition(item, 10)
            assert(item.format == 'PNG')
            assert(files['unicode-photo'].contents == 'png')
            return result
        """)
        self.assertTrue(result["ok"])
        self.assertEqual(set(result.keys()), {"ok", "code", "sizeBytes", "maximumBytes"})


if __name__ == "__main__":
    unittest.main()
