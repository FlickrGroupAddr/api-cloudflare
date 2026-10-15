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
local catalog = {}
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
local modules = {
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
    LrPathUtils = {leafName = function(path) return string.match(path, "[^/]+$") end},
    LrTasks = {pcall = pcall, startAsyncTask = function(callback) callback() end},
    LrFileUtils = {
        exists = function(path) return files[path] ~= nil end,
        createAllDirectories = function(path) assert(path == "C:/Temp/") return true end,
        move = function(src, dest)
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
    local expected = "^C:/Temp/FGA%-Outbox%-Probe%-probe%-%d+%-%d+%-[%w_]+%.json%.tmp$"
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
            self.assertEqual(receipt["probeVersion"], "0.0.2.4")
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
