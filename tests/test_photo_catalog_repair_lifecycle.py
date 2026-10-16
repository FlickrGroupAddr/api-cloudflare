"""Execute the standalone Lua proof with explicitly synthetic SDK boundaries."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
calls, inGate, gateResult, failWrite, hidden = 0, false, "executed", false, false
remoteId, edited, publishCount = nil, true, 0
photo = {getRawMetadata = function(_, key) assert(key == "uuid") return "fixture" end}
publication = {
    getPhoto = function() return photo end,
    getRemoteId = function() return remoteId end,
    setRemoteId = function(_, id)
        assert(inGate)
        calls = calls + 1
        if failWrite then error("synthetic write failure") end
        remoteId = id
    end,
}
service = {localIdentifier = 1, getPluginId = function() return "proof.provider" end}
collection = {
    localIdentifier = 2,
    getService = function() return service end,
    getPublishedPhotos = function() return hidden and {} or {publication} end,
}
catalog = {
    getPath = function() return "synthetic.lrcat" end,
    withWriteAccessDo = function(_, _, callback, options)
        assert(options.timeout == 5 and options.asynchronous == false)
        if gateResult ~= "executed" then return gateResult end
        local old = remoteId
        inGate = true
        local ok, err = pcall(callback)
        inGate = false
        if not ok then remoteId = old error(err) end
        return "executed"
    end,
}
record = {path="normal", uploadResultDurable=true, flickrPhotoId="123",
    catalogPath="synthetic.lrcat", pluginId="proof.provider", serviceId=1,
    collectionId=2, photoUuid="fixture"}
tasks = {pcall = pcall}
"""


class PhotoCatalogRepairLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.execute(HARNESS)
        self.module = self.lua.execute(
            (ROOT / "proofs/photo_catalog_repair_lifecycle.lua").read_text("utf-8")
        )

    def run_repair(self):
        g = self.lua.globals()
        return self.module.repair(g.catalog, g.collection, g.photo, g.record, g.tasks)

    def test_normal_identity_and_idempotent_readback_preserve_status(self):
        self.assertEqual(self.run_repair(), (True, "catalog_identity_observed"))
        self.assertEqual(self.run_repair(), (True, "catalog_identity_observed"))
        g = self.lua.globals()
        self.assertEqual((g.remoteId, g.edited, g.publishCount), ("123", True, 0))

    def test_reconciled_acknowledgement_precedes_write(self):
        self.lua.execute('record.path="reconciled"')
        self.assertFalse(self.run_repair()[0])
        self.assertEqual(self.lua.globals().calls, 0)
        self.lua.execute("record.bindingAcknowledgementDurable=true")
        self.assertTrue(self.run_repair()[0])

    def test_unsafe_or_unresolved_inputs_do_not_write(self):
        for setup in (
            "record.uploadResultDurable=false",
            'record.path="unknown"',
            'record.flickrPhotoId=""',
            'record.catalogPath="other.lrcat"',
            'record.pluginId="foreign.provider"',
            "record.serviceId=9",
            "record.collectionId=9",
            'record.photoUuid="other"',
            'remoteId="999"',
            "hidden=true",
            'gateResult="queued"',
            'gateResult="aborted"',
        ):
            with self.subTest(setup=setup):
                self.setUp()
                self.lua.execute(setup)
                self.assertFalse(self.run_repair()[0])
                self.assertEqual(self.lua.globals().calls, 0)

    def test_catalog_failure_retains_retryable_identity_obligation(self):
        self.lua.execute("failWrite=true")
        self.assertEqual(self.run_repair(), (False, "catalog_repair_pending"))
        self.assertIsNone(self.lua.globals().remoteId)
        self.lua.execute("failWrite=false")
        self.assertTrue(self.run_repair()[0])


if __name__ == "__main__":
    unittest.main()
