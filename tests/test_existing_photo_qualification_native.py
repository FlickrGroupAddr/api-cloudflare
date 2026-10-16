"""Run the native qualification fixture offline through actual Lua 5.1.

These checks test fixture logic and real release modules, never native SDK/network proof.
"""

from __future__ import annotations

import ntpath
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaError, LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "probes/FGA-ExistingPhoto-Qualification.lrplugin"
RELEASE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class ExistingPhotoQualificationTests(unittest.TestCase):
    def run_fixture(self, scenario: str, *, without_setfenv: bool = False):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True, encoding=None)
        self.lua = lua
        self.actions = (
            ["next", "previous", "cancel"]
            if scenario == "navigation_cancel"
            else [
                "ok"
                if scenario in {"success", "stale_proof", "membership_error", "cleanup_failure"}
                else "cancel"
            ]
        )
        self.views = []
        with tempfile.TemporaryDirectory() as directory:

            def mkdir(path):
                Path(path.decode()).mkdir(parents=True, exist_ok=True)
                return True

            def exists(path):
                value = Path(path.decode())
                return (b"directory" if value.is_dir() else b"file") if value.exists() else False

            def delete(path):
                import shutil

                value = Path(path.decode())
                if value.is_dir():
                    shutil.rmtree(value)
                else:
                    value.unlink()
                return True

            def modal(args):
                self.views.append(args)
                if args[b"title"] == b"Currently in Flickr groups":
                    return b"ok"
                args[b"contents"][b"bind_to_object"][b"selected"] = b"synthetic-photo-1"
                return self.actions.pop(0).encode()

            globals_ = lua.globals()
            globals_.mkdir, globals_.exists, globals_.delete, globals_.modal = (
                mkdir,
                exists,
                delete,
                modal,
            )
            sdk = lua.execute(b"""
                local factory={control_spacing=function() return 4 end,
                    label_spacing=function() return 2 end}
                for _, kind in ipairs({"row", "column", "picture", "radio_button", "static_text",
                    "push_button", "scrolled_view", "popup_menu"}) do
                    factory[kind]=function(self, args) args.kind=kind; return args end
                end
                setmetatable(factory, {__index=function(self, key)
                    error("unsupported_fixture_control:" .. key)
                end})
                local sdk={
                    LrBinding={makePropertyTable=function() return {} end},
                    LrDate={currentTime=function() return 12345 end},
                    LrFileUtils={createAllDirectories=mkdir, exists=exists, delete=delete,
                        chooseUniqueFileName=function(path) return path end},
                    LrPathUtils={child=function(a,b) return a .. "/" .. b end},
                    LrLogger=function() return {enable=function() end, warn=function() end} end,
                    LrDialogs={presentModalDialog=modal, message=function() end},
                    LrTasks={pcall=pcall, yield=function() end},
                    LrView={osFactory=function() return factory end,
                        bind=function(key) return key end},
                    LrFunctionContext={callWithContext=function(name, action)
                        local handlers={}
                        local ok, reason=pcall(action, {addCleanupHandler=function(self, callback)
                            handlers[#handlers+1]=callback
                        end})
                        for _, callback in ipairs(handlers) do callback() end
                        if not ok then error(reason) end
                    end},
                }
                return sdk
            """)
            if without_setfenv:
                lua.globals().setfenv = None
            fixture = lua.execute((FIXTURE / "Qualification.lua").read_bytes())
            self.sdk, self.fixture = sdk, fixture
            result = fixture.execute(
                scenario.encode(),
                sdk,
                RELEASE.as_posix().encode(),
                directory.encode(),
                (FIXTURE / "synthetic.png").read_bytes(),
            )
            self.assertEqual(result[b"outcome"], b"passed", scenario)
            self.assertTrue(result[b"cacheClean"])
            self.assertTrue(result[b"completePages"])
            self.assertEqual(list(Path(directory).rglob("image-*")), [])
            return result

    def test_every_scenario_and_cleanup(self):
        for scenario in (
            "success",
            "navigation_cancel",
            "empty",
            "cancel_during_thumbnail",
            "discovery_error",
            "malformed_page",
            "thumbnail_error",
            "stale_proof",
            "membership_error",
            "cleanup_failure",
        ):
            with self.subTest(scenario=scenario):
                result = self.run_fixture(scenario)
                if scenario == "navigation_cancel":
                    self.assertEqual(result[b"pagesPresented"], 3)
                    self.assertEqual(result[b"thumbnails"], 11)
                if scenario == "thumbnail_error":
                    self.assertEqual(result[b"thumbnails"], 2)
                    self.assertEqual(result[b"pagesPresented"], 0)
                if scenario == "cancel_during_thumbnail":
                    self.assertEqual(result[b"thumbnails"], 1)
                    self.assertEqual(result[b"pagesPresented"], 0)
                if scenario == "cleanup_failure":
                    self.assertTrue(result[b"cleanupFailureInjected"])
                    self.assertEqual(result[b"proofs"], 0)

    def test_real_browser_views_have_complete_rows_and_duplicate_notice(self):
        self.run_fixture("navigation_cancel")
        page_one = self.views[0][b"contents"][4][1]
        page_two = self.views[1][b"contents"][4][1]
        self.assertEqual(len(page_one), 5)
        self.assertEqual(page_one[1][3][1][b"title"], b"(Untitled)")
        self.assertEqual(page_one[1][2][b"kind"], b"picture")
        self.assertEqual(len(page_two), 1)
        self.assertIn(b"already shown", page_two[1][b"title"])

    def test_native_chooser_uses_supported_control_and_releases_active_after_error(self):
        self.run_fixture("success")
        sdk = self.sdk
        sdk[b"LrApplication"] = self.lua.table()
        sdk[b"LrTasks"][b"startAsyncTask"] = self.lua.eval(b"function(action) action() end")
        self.lua.globals().nativeSdk = sdk
        self.lua.execute(b"function import(name) return assert(nativeSdk[name]) end")
        factory = sdk[b"LrView"][b"osFactory"]()
        popup = factory[b"popup_menu"]
        factory[b"popup_menu"] = None
        with self.assertRaises(LuaError):
            self.fixture.run()
        factory[b"popup_menu"] = popup
        self.actions = ["cancel", "cancel"]
        before = len(self.views)
        self.fixture.run()
        self.fixture.run()
        self.assertEqual(len(self.views), before + 2)
        chooser = self.views[-1]
        self.assertEqual(chooser[b"contents"][2][b"kind"], b"popup_menu")
        self.assertEqual(len(chooser[b"contents"][2][b"items"]), 10)

    def test_receipt_windows_paths_and_checked_delete_move(self):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        with tempfile.TemporaryDirectory() as directory:
            native_root = r"C:\Temp\FGA-existing-photo-qualification"

            def local(path):
                self.assertNotIn("/", path)
                self.assertEqual(ntpath.dirname(path), native_root)
                return Path(directory) / ntpath.basename(path)

            def child(parent, name):
                self.assertNotIn("/", parent)
                self.assertNotIn("/", name)
                self.assertNotIn("\\", name)
                return ntpath.join(parent, name)

            fail = {"delete": False, "move": False}

            def delete(path):
                if fail["delete"]:
                    return False
                local(path).unlink()
                return True

            def move(source, destination):
                src, dest = local(source), local(destination)
                if fail["move"] or dest.exists() or not dest.parent.exists():
                    return False
                src.rename(dest)
                return True

            def write_bytes(path, body):
                local(path).write_text(body, encoding="utf-8")

            lua.globals().writeBytes = write_bytes
            fixture = lua.execute(
                b"""
                setfenv(1, setmetatable({io={open=function(path)
                    return {write=function(self, body) writeBytes(path, body); return self end,
                        close=function() return true end}
                end}}, {__index=_G}))
            """
                + (FIXTURE / "Qualification.lua").read_bytes()
            )
            sdk = lua.table_from(
                {
                    "LrPathUtils": lua.table_from({"child": child, "parent": ntpath.dirname}),
                    "LrFileUtils": lua.table_from(
                        {
                            "exists": lambda path: "file" if local(path).is_file() else False,
                            "delete": delete,
                            "move": move,
                        }
                    ),
                }
            )
            locations = fixture.locations(
                sdk, r"C:\Projects\FGA\api-cloudflare\probes\fixture.lrplugin"
            )
            self.assertEqual(locations.root, native_root)
            self.assertEqual(locations.cache, ntpath.join(native_root, "cache"))
            self.assertNotIn("/", locations.release)
            json = lua.table_from({"encode": lambda state: '{"outcome":"running"}'})
            state = lua.table()
            fixture.publish(sdk, json, locations, state)
            self.assertTrue(local(locations.receipt).is_file())
            fixture.publish(sdk, json, locations, state)
            self.assertFalse(local(locations.temporary).exists())
            fail["delete"] = True
            with self.assertRaises(LuaError):
                fixture.publish(sdk, json, locations, state)
            self.assertTrue(local(locations.receipt).is_file())
            self.assertTrue(local(locations.temporary).is_file())
            fail["delete"], fail["move"] = False, True
            with self.assertRaises(LuaError):
                fixture.publish(sdk, json, locations, state)
            self.assertFalse(local(locations.receipt).exists())
            self.assertTrue(local(locations.temporary).is_file())

    def test_explicit_browser_factory_runs_without_setfenv(self):
        result = self.run_fixture("success", without_setfenv=True)
        self.assertFalse(result[b"standardFunctions"][b"setfenv"])
        self.assertEqual(result[b"reasonCode"], b"observation_complete")

    def test_outer_browser_load_error_retains_closed_phase_and_no_raw_exception(self):
        self.run_fixture("success")
        self.sdk[b"LrLogger"] = None
        result = self.fixture.executeSafely(
            b"success",
            self.sdk,
            RELEASE.as_posix().encode(),
            b"unused-fixture-cache",
            (FIXTURE / "synthetic.png").read_bytes(),
        )
        self.assertEqual(result[b"outcome"], b"failed")
        self.assertEqual(result[b"reasonCode"], b"fixture_runtime_error")
        self.assertEqual(result[b"phase"], b"load_browser")
        self.assertEqual(result[b"failurePhase"], b"load_browser")
        self.assertEqual(result[b"errorType"], b"string")
        self.assertEqual(result[b"requests"], 0)
        self.assertFalse(result[b"cacheClean"])
        encoded = self.lua.execute((RELEASE / "dkjson.lua").read_bytes()).encode(result)
        self.assertNotIn(b"attempt", encoded)
        self.assertNotIn(RELEASE.as_posix().encode(), encoded)

    def test_png_asset_has_valid_chunks_crc_and_decodable_pixels(self):
        data = (FIXTURE / "synthetic.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        offset, pixels, chunks = 8, b"", []
        while offset < len(data):
            size = struct.unpack(">I", data[offset : offset + 4])[0]
            kind = data[offset + 4 : offset + 8]
            body = data[offset + 8 : offset + 8 + size]
            crc = struct.unpack(">I", data[offset + 8 + size : offset + 12 + size])[0]
            self.assertEqual(crc, zlib.crc32(kind + body))
            chunks.append(kind)
            if kind == b"IDAT":
                pixels += body
            offset += size + 12
        self.assertEqual(chunks, [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(len(zlib.decompress(pixels)), 150 * (1 + 150 * 3))

    def test_registration_versions_and_boundary(self):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        info = lua.execute((FIXTURE / "Info.lua").read_text(encoding="utf-8-sig"))
        module = lua.execute((FIXTURE / "Qualification.lua").read_text(encoding="utf-8-sig"))
        version = info.VERSION
        expected = f"{version.major}.{version.minor}.{version.revision}.{version.build}"
        self.assertEqual(module.VERSION, expected)
        self.assertIn(expected, (FIXTURE / "Run.lua").read_text())
        self.assertEqual(info.LrSdkVersion, 15.3)
        source = (FIXTURE / "Qualification.lua").read_text()
        self.assertNotIn('import "LrHttp"', source)
        self.assertNotIn("activeCatalog", source)
        self.assertNotIn("setfenv(", source)
        self.assertIn("state.nativeTransportQualified=false", source)
        self.assertIn("state.productionQualified=false", source)


if __name__ == "__main__":
    unittest.main()
