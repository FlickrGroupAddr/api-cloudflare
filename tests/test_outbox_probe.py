"""Actual Lua 5.1 probe execution against injected SDK/file boundaries only."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

HARNESS = r"""
files, dialogs, properties = {}, {}, {}
catalogPath = "C:/Temp/FGA-Outbox-Probe.lrcat"
gateResult, rollback, failReceipt, mutations = "executed", true, false, 0
_PLUGIN = {}
catalog = {}
function catalog:getPath() return catalogPath end
function catalog:getPropertyForPlugin(_, field) return properties[field] end
function catalog:setPropertyForPlugin(_, field, value)
    mutations = mutations + 1
    properties[field] = value
end
function catalog:withPrivateWriteAccessDo(callback, options)
    assert(options.asynchronous == false and options.timeout == 5)
    if gateResult ~= "executed" then return gateResult end
    local old = properties.syntheticOutboxProbeV2
    local ok, err = pcall(callback)
    if not ok then
        if rollback then properties.syntheticOutboxProbeV2 = old end
        error(err)
    end
    return "executed"
end
modules = {
    LrApplication = {
        activeCatalog = function() return catalog end,
        versionTable = function()
            return hostVersion or {major=15, minor=6, revision=0,
                build_version="202609251514-f839cde9"}
        end,
    },
    LrDate = {
        currentTime = function() return 123456789 end,
        timestampToComponents = function(_, offset)
            assert(offset == 0)
            return 2026,10,15,18,30,receiptSecond or 0
        end,
    },
    LrDialogs = {message = function(a,b,c) table.insert(dialogs, a..b..c) end},
    LrPathUtils = {
        leafName = function(path) return string.match(path, "[^/\\]+$") end,
        child = function(parent, name)
            assert(parent == "C:\\Temp" and not string.find(name, "[/\\]"))
            return parent .. "\\" .. name
        end,
    },
    LrTasks = {pcall = pcall, startAsyncTask = function(callback) callback() end},
    LrFileUtils = {
        exists = function(path)
            assert(not string.find(path, "/"))
            return files[path] and "file" or false
        end,
        createAllDirectories = function(path) assert(path == "C:\\Temp") return true end,
        move = function(src, dest)
            assert(not string.find(src, "/") and not string.find(dest, "/"))
            if files[dest] or not files[src] then return false end
            files[dest], files[src] = files[src], nil
            return true
        end,
    },
}
function import(name)
    assert(modules[name], "prohibited or unknown SDK import")
    return modules[name]
end
io = {open = function(path, mode)
    local expected = "^C:\\Temp\\FGA%-Outbox%-Probe%-probe%-%d+%-%d+%-[%w_]+%.json%.tmp$"
    assert(mode == "wb" and string.match(path, expected))
    if failReceipt then error("SECRET synthetic error with private path") end
    local file = {}
    function file:write(body) files[path] = body return self end
    function file:close() return true end
    return file
end}
"""


class OutboxProbeTests(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ.get("FGA_OUTBOX_PROBE_ROOT", Path(__file__).resolve().parents[1]))
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.execute(HARNESS)
        self.probe = self.lua.execute(
            (root / "probes/FGA-Outbox-Probe.lrplugin/Probe.lua").read_text("utf-8")
        )

    def receipts(self):
        return [
            json.loads(body)
            for path, body in self.lua.globals().files.items()
            if path.endswith(".json")
        ]

    def test_every_bundle_lua_file_compiles_under_lua51(self):
        root = Path(os.environ.get("FGA_OUTBOX_PROBE_ROOT", Path(__file__).resolve().parents[1]))
        compile_lua = self.lua.eval("function(source) return assert(loadstring(source)) end")
        for path in (root / "probes/FGA-Outbox-Probe.lrplugin").glob("*.lua"):
            with self.subTest(file=path.name):
                compile_lua(path.read_text("utf-8"))

    def test_correlated_write_rollback_and_verify_without_restart_overclaim(self):
        self.probe.write()
        self.probe.verify()
        receipts = self.receipts()
        self.assertEqual({r["stage"] for r in receipts}, {"same_session", "rollback", "restart"})
        self.assertEqual(len({r["runId"] for r in receipts}), 1)
        for receipt in receipts:
            self.assertTrue(receipt["stageTerminal"])
            self.assertEqual(receipt["terminal"], receipt["stage"] != "same_session")
            self.assertEqual(receipt["writeTime"], "2026-10-15T18:30:00Z")
            self.assertEqual(receipt["probeVersion"], "0.0.2.6")
            self.assertEqual(receipt["host"]["buildVersion"], "202609251514-f839cde9")
            self.assertFalse(receipt["restartIndependentlyVerified"])
            self.assertFalse(receipt["crashQualified"])
            self.assertFalse(receipt["powerLossQualified"])

    def test_fractional_seconds_are_floored_without_minute_rollover(self):
        self.lua.globals().receiptSecond = 59.999
        self.probe.write()
        for receipt in self.receipts():
            self.assertEqual(receipt["writeTime"], "2026-10-15T18:30:59Z")

    def test_invalid_host_context_is_never_echoed_or_claimed_qualified(self):
        self.lua.execute('hostVersion = {major=15, minor=6, revision=0, build_version="SECRET\\n"}')
        self.probe.write()
        for receipt in self.receipts():
            self.assertEqual(receipt["host"], {"contextValid": False})
        self.assertNotIn("SECRET", json.dumps(self.receipts()))

    def test_manifest_and_runtime_receipt_versions_match(self):
        root = Path(os.environ.get("FGA_OUTBOX_PROBE_ROOT", Path(__file__).resolve().parents[1]))
        info = self.lua.execute(
            (root / "probes/FGA-Outbox-Probe.lrplugin/Info.lua").read_text("utf-8")
        )
        self.probe.write()
        version = info.VERSION
        expected = f"{version.major}.{version.minor}.{version.revision}.{version.build}"
        self.assertEqual(self.receipts()[0]["probeVersion"], expected)

    def test_wrong_catalog_refuses_without_any_catalog_read_or_write(self):
        self.lua.execute('catalogPath = "C:/Private/Actual.lrcat"')
        self.probe.write()
        self.assertEqual(self.lua.globals().mutations, 0)
        self.assertEqual(self.receipts()[0]["reasonCode"], "fixture_catalog_required")
        self.assertNotIn("Private", json.dumps(self.receipts()))

    def test_queued_or_aborted_gate_never_reports_pass_or_tests_rollback(self):
        for result in ("queued", "aborted"):
            with self.subTest(result=result):
                self.setUp()
                self.lua.globals().gateResult = result
                self.probe.write()
                self.assertEqual(self.lua.globals().mutations, 0)
                self.assertEqual(self.receipts()[0]["outcome"], "failed")

    def test_failed_rollback_is_reported_and_cannot_verify_fixture(self):
        self.lua.globals().rollback = False
        self.probe.write()
        self.probe.verify()
        receipts = self.receipts()
        self.assertIn("callback_rollback_not_observed", {r["reasonCode"] for r in receipts})
        self.assertNotIn("restart", {r["stage"] for r in receipts})

    def test_corrupt_state_is_preserved_without_echoing_private_content(self):
        self.lua.execute('properties.syntheticOutboxProbeV2 = "SECRET private metadata"')
        self.probe.write()
        self.assertEqual(self.lua.globals().mutations, 0)
        self.assertNotIn("SECRET", json.dumps(self.receipts()))

    def test_receipt_failure_does_not_expose_raw_exception_or_continue_rollback(self):
        self.lua.globals().failReceipt = True
        self.probe.write()
        self.assertEqual(self.receipts(), [])
        self.assertEqual(self.lua.globals().mutations, 1)
        self.assertNotIn("SECRET", "".join(self.lua.globals().dialogs.values()))

    def dialog_text(self):
        return "".join(self.lua.globals().dialogs.values())

    def test_preflight_never_calls_catalog_and_preserves_existing_property(self):
        self.lua.execute("""
            properties.syntheticOutboxProbeV2 = "SECRET prior run"
            modules.LrApplication.activeCatalog = function() error("SECRET catalog called") end
        """)
        self.probe.preflight()
        self.assertEqual(self.lua.globals().mutations, 0)
        self.assertEqual(self.lua.globals().properties.syntheticOutboxProbeV2, "SECRET prior run")
        self.assertEqual(self.receipts()[0]["stage"], "preflight")
        self.assertEqual(self.receipts()[0]["reasonCode"], "receipt_path_available")
        self.assertIn("file close: boolean/truthy", self.dialog_text())
        self.assertIn("file move: boolean/truthy", self.dialog_text())
        self.assertIn("source is file: true; destination exists: false", self.dialog_text())
        self.assertNotIn("SECRET", self.dialog_text())

    def test_actual_missing_apis_and_io_failures_have_closed_diagnostics(self):
        cases = [
            ("io = nil", "receipt_open", "nil", "preflight"),
            ("io.open = nil", "receipt_open", "nil", "preflight"),
            (
                'io.open = function() return nil, "SECRET private path" end',
                "receipt_open",
                "nil",
                "preflight",
            ),
            ("modules.LrFileUtils.exists = nil", "allocate_identity", "nil", "preflight"),
            ("modules.LrFileUtils.move = nil", "receipt_move", "nil", "preflight"),
            (
                'modules.LrFileUtils.move = function() return false, "SECRET" end',
                "receipt_move_result",
                "nil",
                "preflight",
            ),
            ("catalog.getPropertyForPlugin = nil", "get_property", "nil", "write"),
            ("catalog.withPrivateWriteAccessDo = nil", "private_gate", "nil", "write"),
            ("catalog.setPropertyForPlugin = nil", "set_property", "nil", "write"),
        ]
        for injection, stage, _, command in cases:
            with self.subTest(injection=injection):
                self.setUp()
                self.lua.execute(injection)
                self.probe[command]()
                self.assertIn("Stage: " + stage + "; error type: string", self.dialog_text())
                self.assertNotIn("SECRET", self.dialog_text())
                self.assertEqual(self.lua.globals().mutations, 0)

    def test_write_and_close_falsey_returns_are_diagnosed_without_move(self):
        for method in ("write", "close"):
            with self.subTest(method=method):
                self.setUp()
                self.lua.execute(
                    """
                    local open = io.open
                    io.open = function(path, mode)
                        local file = open(path, mode)
                        file.METHOD = function() return nil, "SECRET private path" end
                        return file
                    end
                """.replace("METHOD", method)
                )
                self.probe.preflight()
                self.assertEqual(self.receipts(), [])
                self.assertIn("Stage: receipt_" + method + "_result", self.dialog_text())
                self.assertIn("file " + method + ": nil/falsey", self.dialog_text())
                self.assertIn("file move: not_called", self.dialog_text())
                self.assertNotIn("SECRET", self.dialog_text())

    def test_error_object_is_classified_without_tostring(self):
        self.lua.execute("""
            io.open = function() error(setmetatable({}, {
                __tostring = function() error("SECRET must not stringify") end
            })) end
        """)
        self.probe.preflight()
        self.assertIn("Stage: receipt_open; error type: table", self.dialog_text())
        self.assertNotIn("SECRET", self.dialog_text())

    def test_preflight_preserves_prior_incomplete_receipt(self):
        path = r"C:\Temp\FGA-Outbox-Probe-probe-123456789000000-1-preflight.json.tmp"
        self.lua.globals().files[path] = "PRIOR"
        self.probe.preflight()
        self.assertEqual(self.lua.globals().files[path], "PRIOR")
        self.assertTrue(self.receipts()[0]["runId"].endswith("-2"))

    def test_verify_preserves_prior_incomplete_restart_receipt(self):
        self.probe.write()
        run_id = self.receipts()[0]["runId"]
        path = rf"C:\Temp\FGA-Outbox-Probe-{run_id}-restart.json.tmp"
        self.lua.globals().files[path] = "PRIOR"
        self.probe.verify()
        self.assertEqual(self.lua.globals().files[path], "PRIOR")
        self.assertNotIn("restart", {r["stage"] for r in self.receipts()})
        self.assertIn("verification_receipt_incomplete", {r["reasonCode"] for r in self.receipts()})

    def test_sdk_cannot_see_closed_source_is_reported_without_move(self):
        self.lua.execute("""
            modules.LrFileUtils.exists = function() return false end
        """)
        self.probe.preflight()
        self.assertEqual(self.receipts(), [])
        self.assertIn("Stage: receipt_source_check", self.dialog_text())
        self.assertIn("source is file: false", self.dialog_text())
        self.assertIn("file move: not_called", self.dialog_text())

    def test_destination_collision_after_allocation_is_preserved_without_move(self):
        self.lua.execute("""
            local open = io.open
            io.open = function(path, mode)
                local file = open(path, mode)
                file.close = function()
                    files[string.sub(path, 1, -5)] = "PRIOR"
                    return true
                end
                return file
            end
        """)
        self.probe.preflight()
        self.assertIn("Stage: receipt_destination_check", self.dialog_text())
        self.assertIn("destination exists: true", self.dialog_text())
        self.assertIn("file move: not_called", self.dialog_text())
        for path, body in self.lua.globals().files.items():
            if path.endswith(".json"):
                self.assertEqual(body, "PRIOR")

    def test_move_reason_is_type_only_with_fixed_category(self):
        self.lua.execute("""
            modules.LrFileUtils.move = function()
                return false, setmetatable({}, {
                    __tostring = function() error("SECRET must not stringify") end
                })
            end
        """)
        self.probe.preflight()
        self.assertEqual(self.receipts(), [])
        self.assertIn("Stage: receipt_move_result", self.dialog_text())
        self.assertIn("move reason type: table; move category: sdk_move_failed", self.dialog_text())
        self.assertNotIn("SECRET", self.dialog_text())

    def test_repeated_verify_preserves_prior_receipt_and_refuses_overwrite(self):
        self.probe.write()
        self.probe.verify()
        before = {p: b for p, b in self.lua.globals().files.items() if "-restart.json" in p}
        self.probe.verify()
        after = {p: b for p, b in self.lua.globals().files.items() if "-restart.json" in p}
        self.assertEqual(before, after)
        self.assertIn("run_already_verified", {r["reasonCode"] for r in self.receipts()})

    def test_second_write_allocates_distinct_run_and_cannot_reuse_first_restart(self):
        self.probe.write()
        self.probe.verify()
        first = next(r["runId"] for r in self.receipts() if r["stage"] == "restart")
        self.probe.write()
        self.probe.verify()
        verified = {r["runId"] for r in self.receipts() if r["stage"] == "restart"}
        self.assertEqual(len(verified), 2)
        self.assertIn(first, verified)


if __name__ == "__main__":
    unittest.main()
