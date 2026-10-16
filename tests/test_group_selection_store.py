"""Actual Lua 5.1 store behavior against synthetic transactional SDK mocks."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
PHOTO_UUID = "00000000-0000-0000-0000-000000000024"
HARNESS = r"""
photoProperties, catalogProperties = {}, {}
plugin, catalog, photo = {}, {}, {}
activeCatalog, gateResult, mutations = catalog, "executed", 0
photoUuid = "00000000-0000-0000-0000-000000000024"
function photo:getRawMetadata(key) assert(key == "uuid"); return photoUuid end
function photo:getPropertyForPlugin(p,key)
    assert(p == plugin and key == "groupAdditionSelections")
    if readFailure then error("SECRET synthetic storage error") end
    return photoProperties[key]
end
function catalog:getPropertyForPlugin(p,key)
    assert(p == plugin and key == "groupAdditionOutboxV1")
    return catalogProperties[key]
end
function photo:setPropertyForPlugin(p,key,value)
    assert(insideGate and p == plugin and key == "groupAdditionSelections")
    mutations=mutations+1; photoProperties[key]=value
    if failAt == "photo" then error("SECRET synthetic write error") end
end
function catalog:setPropertyForPlugin(p,key,value)
    assert(insideGate and p == plugin and key == "groupAdditionOutboxV1")
    mutations=mutations+1; catalogProperties[key]=value
    if failAt == "catalog" then error("SECRET synthetic write error") end
end
function catalog:withPrivateWriteAccessDo(callback,options)
    assert(options.asynchronous == false and options.timeout == 5 and options.callback == nil)
    assert(not insideGate)
    if beforeGate then local f=beforeGate; beforeGate=nil; f() end
    if gateResult ~= "executed" then pendingCallback=callback; return gateResult end
    local oldPhoto=photoProperties.groupAdditionSelections
    local oldCatalog=catalogProperties.groupAdditionOutboxV1
    insideGate=true
    local ok,err=pcall(callback)
    insideGate=false
    if not ok then
        photoProperties.groupAdditionSelections=oldPhoto
        catalogProperties.groupAdditionOutboxV1=oldCatalog
        error(err)
    end
    if mismatch then photoProperties.groupAdditionSelections="SECRET changed readback" end
    if switchAfterGate then activeCatalog={} end
    return gateResult
end
options={catalog=catalog,photo=photo,plugin=plugin,pcall=pcall,
    activeCatalog=function() return activeCatalog end}
"""


class GroupSelectionStoreTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.json = self.lua.execute((BUNDLE / "dkjson.lua").read_text("utf-8"))
        self.lua.globals().json = self.json
        self.lua.execute("package.preload.dkjson=function() return json end")
        self.lua.execute(HARNESS)
        self.module = self.lua.execute((BUNDLE / "GroupSelectionStore.lua").read_text("utf-8"))
        self.store = self.module.new(self.lua.globals().options)
        self.scope = self.table(
            {
                "publishServiceLocalId": 12,
                "publishedCollectionLocalId": 34,
                "photoUuid": PHOTO_UUID,
            }
        )

    def table(self, value):
        return self.lua.table_from(value, recursive=True)

    def result(self, method, *args):
        return getattr(self.store, method)(self.store, self.scope, *args)

    def save(self, groups=(), revision=0, handoff=None, binding=None):
        return self.result("saveChoice", self.table(list(groups)), revision, handoff, binding)

    def stored(self, outbox=False) -> Any:
        target = (
            self.lua.globals().catalogProperties if outbox else self.lua.globals().photoProperties
        )
        field = self.module.OUTBOX_FIELD if outbox else self.module.SELECTION_FIELD
        raw = target[field]
        return json.loads(raw) if raw else None

    def ack(self, revision=1, groups=("101@N00",), binding=None, **patch):
        result = self.table(
            {
                "kind": "groups_accepted",
                "selectionRevision": revision,
                "flickrGroupIds": list(groups),
                "submissions": [
                    {
                        "fgaSubmissionIntentId": f"synthetic-intent-{index}",
                        "flickrGroupId": group,
                        "state": "queued",
                        "created": True,
                    }
                    for index, group in enumerate(groups)
                ],
                **patch,
            }
        )
        for row in result.submissions.values():
            row.permanentSubmissionBlock = self.json.null
        if binding is not None:
            result.binding = binding
        return result

    def test_exact_scope_sorted_groups_and_revision_checked_replacement(self):
        self.assertEqual(self.result("readChoice").state, "ready")
        self.assertIsNone(self.result("readChoice").selection)
        self.assertEqual(self.save(("202@N00", "101@N00")).state, "saved")
        self.assertEqual(self.stored()["entries"][0]["flickrGroupIds"], ["101@N00", "202@N00"])
        before = self.stored()
        self.assertEqual(self.save(("303@N00",), 0).state, "revision_conflict")
        self.assertEqual(self.stored(), before)
        self.assertEqual(self.save((), 1).selection.choice, "none")
        self.assertEqual(self.stored()["entries"][0]["selectionRevision"], 2)

    def test_other_album_entries_preserved_and_no_cross_photo_reads(self):
        self.save(("101@N00",))
        self.scope.publishedCollectionLocalId = 35
        self.assertIsNone(self.result("readChoice").selection)
        self.save(())
        self.assertEqual(len(self.stored()["entries"]), 2)
        before = self.stored()
        self.scope.photoUuid = "00000000-0000-0000-0000-000000000099"
        self.assertEqual(self.save().state, "scope_invalid")
        self.assertEqual(self.stored(), before)

    def test_atomic_save_and_immutable_outbox_survive_new_store_and_later_edit(self):
        saved = self.save(("101@N00",), handoff="synthetic-handoff-1")
        self.assertEqual(saved.handoff.outboxRevision, 1)
        saved.handoff.flickrGroupIds[1] = "999@N00"
        self.save(("202@N00",), 1)
        self.store = self.module.new(self.lua.globals().options)
        handoff = self.result("readHandoff", "synthetic-handoff-1").handoff
        self.assertEqual(handoff.flickrGroupIds[1], "101@N00")
        confirmed = self.result("confirm", handoff.handoffId, 1, self.ack())
        self.assertEqual(confirmed.state, "confirmed")
        self.assertFalse(confirmed.selectionConsumed)
        self.assertEqual(self.result("readChoice").selection.selectionRevision, 2)
        row = self.stored(True)["records"][0]
        self.assertEqual(row["state"], "acknowledged")
        self.assertEqual(row["submissions"][0]["fgaSubmissionIntentId"], "synthetic-intent-0")
        self.assertIsNone(row["submissions"][0]["permanentSubmissionBlock"])

    def test_matching_confirm_consumes_only_equal_revision_and_prevents_revision_aba(self):
        self.save(("101@N00",), handoff="synthetic-handoff-1")
        confirmed = self.result("confirm", "synthetic-handoff-1", 1, self.ack())
        self.assertTrue(confirmed.selectionConsumed)
        self.assertEqual(self.stored()["entries"], [])
        saved = self.save(("202@N00",))
        self.assertEqual(saved.selection.selectionRevision, 2)
        self.assertEqual(
            self.result("confirm", "synthetic-handoff-1", 1, self.ack()).state, "revision_conflict"
        )
        repeated = self.result("confirm", "synthetic-handoff-1", 2, self.ack())
        self.assertFalse(repeated.selectionConsumed)
        self.assertEqual(self.result("readChoice").selection.selectionRevision, 2)

    def test_restart_lists_older_unresolved_handoff_after_newer_acknowledgement(self):
        self.save(("101@N00",), handoff="synthetic-older")
        self.save(("202@N00",), 1, "synthetic-newer")
        self.assertTrue(
            self.result(
                "confirm", "synthetic-newer", 1, self.ack(2, ("202@N00",))
            ).selectionConsumed
        )
        self.store = self.module.new(self.lua.globals().options)
        self.assertIsNone(self.result("readChoice").selection)
        listed = self.result("listPending")
        self.assertEqual(listed.state, "ready")
        self.assertEqual(len(listed.handoffs), 1)
        self.assertEqual(listed.handoffs[1].handoffId, "synthetic-older")
        listed.handoffs[1].flickrGroupIds[1] = "999@N00"
        self.assertEqual(self.result("listPending").handoffs[1].flickrGroupIds[1], "101@N00")
        self.scope.publishedCollectionLocalId = 35
        self.assertEqual(len(self.result("listPending").handoffs), 0)

    def test_high_safe_integer_ids_and_revisions_round_trip_without_tostring_rounding(self):
        self.scope.publishServiceLocalId = 9007199254740991
        self.scope.publishedCollectionLocalId = 100000000000001
        self.assertEqual(self.save(("101@N00",)).state, "saved")
        document = self.stored()
        self.assertEqual(document["entries"][0]["publishServiceLocalId"], 9007199254740991)
        self.assertEqual(document["entries"][0]["publishedCollectionLocalId"], 100000000000001)
        document["entries"][0]["selectionRevision"] = 100000000000001
        self.lua.globals().photoProperties[self.module.SELECTION_FIELD] = json.dumps(document)
        saved = self.save(("101@N00",), 100000000000001, "synthetic-high")
        self.assertEqual(saved.selection.selectionRevision, 100000000000002)
        self.assertEqual(self.stored(True)["records"][0]["selectionRevision"], 100000000000002)
        self.assertEqual(self.result("readChoice").selection.selectionRevision, 100000000000002)
        document["entries"][0]["selectionRevision"] = 9007199254740991
        self.lua.globals().photoProperties[self.module.SELECTION_FIELD] = json.dumps(document)
        self.assertEqual(self.save((), 9007199254740991).state, "revision_exhausted")
        self.assertEqual(self.stored()["entries"][0]["selectionRevision"], 9007199254740991)

    def test_missing_and_explicit_none_snapshot_require_publication_and_album_ack(self):
        prepared = self.result("prepare", 0, "synthetic-empty")
        self.assertEqual(prepared.handoff.choice, "none")
        self.assertEqual(prepared.handoff.selectionRevision, 0)
        self.assertEqual(
            self.result("confirm", "synthetic-empty", 1, self.ack()).state, "ack_invalid"
        )
        self.save(())
        self.result("prepare", 1, "synthetic-none")
        ack = self.table(
            {
                "kind": "publication_recorded",
                "selectionRevision": 1,
                "flickrGroupIds": [],
                "publicationRecorded": True,
            }
        )
        self.assertEqual(self.result("confirm", "synthetic-none", 1, ack).state, "ack_invalid")
        ack.albumAttachmentDurable = True
        self.assertTrue(self.result("confirm", "synthetic-none", 1, ack).selectionConsumed)

    def test_corrupt_unknown_schema_or_non_strict_json_never_overwritten(self):
        values = [
            "SECRET synthetic corruption",
            "",
            "null",
            "{}",
            '{"schemaVersion":2,"entries":[]}',
            '{"schemaVersion":1,"entries":{}}',
            '{"schemaVersion":1,"entries":[],}',
            '{"schemaVersion":1 "entries":[]}',
            '{"schemaVersion":1,"schema\\u0056ersion":1,"entries":[]}',
            '{/*comment*/"schemaVersion":1,"entries":[]}',
            '{"schemaVersion":1,"entries":[]} false',
            '{"schemaVersion":1,"entries":[],"credential":"SECRET"}',
        ]
        for raw in values:
            with self.subTest(raw=raw):
                self.lua.globals().photoProperties[self.module.SELECTION_FIELD] = raw
                result = self.save()
                self.assertEqual(result.state, "stored_invalid")
                self.assertEqual(self.lua.globals().mutations, 0)
                self.assertNotIn("SECRET", self.json.encode(result))
                self.assertEqual(
                    self.lua.globals().photoProperties[self.module.SELECTION_FIELD], raw
                )

    def test_invalid_persisted_scope_order_duplicates_groups_and_choices(self):
        self.save(("101@N00",))
        valid = self.stored()
        mutations = self.lua.globals().mutations
        variants = []
        for patch in (
            {"photoUuid": "wrong"},
            {"selectionRevision": 0},
            {"choice": "none"},
            {"flickrGroupIds": ["101@N00", "101@N00"]},
            {"flickrGroupIds": ["202@N00", "101@N00"]},
            {"publishServiceLocalId": "12"},
        ):
            variants.append({"schemaVersion": 1, "entries": [{**valid["entries"][0], **patch}]})
        variants.append({"schemaVersion": 1, "entries": valid["entries"] * 2})
        for value in variants:
            self.lua.globals().photoProperties[self.module.SELECTION_FIELD] = json.dumps(value)
            self.assertEqual(self.save().state, "stored_invalid")
            self.assertEqual(self.lua.globals().mutations, mutations)

    def test_invalid_input_and_bounds_refuse_without_eviction(self):
        for groups in (["101@N00"] * 2, [f"{i}@N00" for i in range(61)], ["SECRET\n"], [1]):
            self.assertEqual(self.save(groups).state, "choice_invalid")
        self.assertEqual(self.lua.globals().mutations, 0)
        for index in range(self.module.MAX_SELECTION_ENTRIES):
            self.scope.publishedCollectionLocalId = index + 1
            self.assertEqual(self.save().state, "saved")
        before = self.stored()
        self.scope.publishedCollectionLocalId = 1000
        self.assertEqual(self.save().state, "storage_full")
        self.assertEqual(self.stored(), before)
        self.lua.globals().photoProperties[self.module.SELECTION_FIELD] = " " * (
            self.module.MAX_SELECTION_BYTES + 1
        )
        self.assertEqual(self.result("readChoice").state, "stored_invalid")

    def test_outbox_count_byte_bounds_and_corruption_refuse_save_atomically(self):
        for index in range(self.module.MAX_OUTBOX_ENTRIES):
            self.assertEqual(self.result("prepare", 0, f"synthetic-{index:03}").state, "prepared")
        before = self.stored(True)
        self.assertEqual(self.save(("101@N00",), handoff="synthetic-full").state, "storage_full")
        self.assertIsNone(self.stored())
        self.assertEqual(self.stored(True), before)
        for raw in ("SECRET corrupt outbox", " " * (self.module.MAX_OUTBOX_BYTES + 1)):
            self.lua.globals().catalogProperties[self.module.OUTBOX_FIELD] = raw
            self.assertEqual(self.save().state, "stored_invalid")
            self.assertIsNone(self.stored())

    def test_storage_full_at_encoding_does_not_write_either_document(self):
        self.module.MAX_OUTBOX_BYTES = 20
        self.assertEqual(self.save(("101@N00",), handoff="synthetic-full").state, "storage_full")
        self.assertEqual(self.lua.globals().mutations, 0)
        self.assertIsNone(self.stored())

    def test_callback_write_failure_rolls_back_both_documents(self):
        self.save(("202@N00",))
        before = self.stored()
        self.lua.globals().failAt = "catalog"
        result = self.save(("101@N00",), 1, "synthetic-failure")
        self.assertEqual(result.state, "storage_unavailable")
        self.assertNotIn("SECRET", self.json.encode(result))
        self.assertEqual(self.stored(), before)
        self.assertIsNone(self.stored(True))

    def test_queued_aborted_or_delayed_callbacks_never_report_success(self):
        for result in ("queued", "aborted", "unknown"):
            with self.subTest(result=result):
                self.lua.globals().gateResult = result
                self.assertEqual(self.save().state, "write_unconfirmed")
                ok = self.lua.eval("function() return pcall(pendingCallback) end")()
                self.assertFalse(ok[0])
                self.assertEqual(self.lua.globals().mutations, 0)

    def test_concurrent_revision_rechecked_inside_gate(self):
        self.save(("101@N00",))
        changed = self.stored()
        changed["entries"][0]["selectionRevision"] = 2
        self.lua.globals().concurrentRaw = json.dumps(changed)
        self.lua.execute(
            "beforeGate=function() photoProperties.groupAdditionSelections=concurrentRaw end"
        )
        self.assertEqual(self.save(("202@N00",), 1).state, "revision_conflict")
        self.assertEqual(self.stored(), changed)

    def test_gate_wait_cannot_retarget_callers_mutable_scope(self):
        self.lua.globals().callerScope = self.scope
        self.lua.execute("beforeGate=function() callerScope.publishedCollectionLocalId=35 end")
        saved = self.save(("101@N00",))
        self.assertEqual(saved.state, "saved")
        self.assertEqual(saved.selection.publishedCollectionLocalId, 34)
        self.assertEqual(self.stored()["entries"][0]["publishedCollectionLocalId"], 34)
        self.assertIsNone(self.result("readChoice").selection)

    def test_equal_revision_but_contradictory_groups_are_never_consumed(self):
        self.save(("101@N00",), handoff="synthetic-handoff")
        changed = self.stored()
        changed["entries"][0]["flickrGroupIds"] = ["202@N00"]
        self.lua.globals().photoProperties[self.module.SELECTION_FIELD] = json.dumps(changed)
        self.assertEqual(
            self.result("confirm", "synthetic-handoff", 1, self.ack()).state, "stored_invalid"
        )
        self.assertEqual(self.stored(), changed)
        self.assertEqual(self.stored(True)["records"][0]["state"], "prepared")

    def test_catalog_switch_storage_read_failure_and_mismatch_are_unconfirmed(self):
        self.lua.globals().activeCatalog = self.table({})
        self.assertEqual(self.save().state, "scope_invalid")
        self.assertEqual(self.lua.globals().mutations, 0)
        self.lua.execute("activeCatalog=catalog; readFailure=true")
        self.assertEqual(self.save().state, "storage_unavailable")
        self.lua.execute("readFailure=false; mismatch=true")
        self.assertEqual(self.save().state, "write_unconfirmed")
        self.assertNotIn("SECRET", self.json.encode(self.result("readChoice")))
        self.lua.execute("photoProperties={}; mismatch=false; switchAfterGate=true")
        self.assertEqual(self.save().state, "write_unconfirmed")

    def test_handoff_ids_scope_and_binding_cannot_be_reused_or_crossed(self):
        binding = self.table(
            {
                "fgaPhotoBindingId": "synthetic-binding",
                "flickrPhotoId": "100024",
                "verificationRevision": 3,
                "linkRevision": 2,
                "sourceKind": "existing_public_flickr_photo",
            }
        )
        saved = self.save(("101@N00",), handoff="synthetic-handoff", binding=binding)
        self.assertEqual(saved.state, "saved")
        before = self.stored()
        self.assertEqual(self.save((), 1, "synthetic-empty-bound", binding).state, "choice_invalid")
        self.assertEqual(self.save(("202@N00",), 1, "synthetic-handoff").state, "handoff_exists")
        self.assertEqual(self.stored(), before)
        self.assertEqual(
            self.result("confirm", "synthetic-handoff", 1, self.ack()).state, "ack_invalid"
        )
        binding.verificationRevision = 4
        self.assertEqual(
            self.result("confirm", "synthetic-handoff", 1, self.ack(binding=binding)).state,
            "ack_invalid",
        )
        binding.verificationRevision = 3
        self.assertEqual(
            self.result("confirm", "synthetic-handoff", 1, self.ack(binding=binding)).state,
            "confirmed",
        )
        self.scope.publishedCollectionLocalId = 35
        self.assertEqual(self.result("readHandoff", "synthetic-handoff").state, "handoff_not_found")

    def test_partial_or_contradictory_ack_retains_unresolved_snapshot(self):
        self.save(("101@N00",), handoff="synthetic-handoff")
        for mutation in ("missing", "created", "state", "block", "group", "revision"):
            ack = self.ack()
            row = ack.submissions[1]
            if mutation == "missing":
                ack.submissions = self.table([])
            elif mutation == "created":
                row.created = "true"
            elif mutation == "state":
                row.state = "unknown"
            elif mutation == "block":
                row.state = "delivery_uncertain"
            elif mutation == "group":
                row.flickrGroupId = "202@N00"
            else:
                ack.selectionRevision = 2
            self.assertEqual(
                self.result("confirm", "synthetic-handoff", 1, ack).state, "ack_invalid"
            )
            self.assertEqual(self.stored(True)["records"][0]["state"], "prepared")
            self.assertIsNotNone(self.result("readChoice").selection)
        ack = self.ack()
        ack.submissions[1].state = "delivery_uncertain"
        ack.submissions[1].created = False
        ack.submissions[1].permanentSubmissionBlock = self.table(
            {"reasonCode": "delivery_uncertain", "createdAt": "2026-10-16T12:00:00Z"}
        )
        self.assertEqual(self.result("confirm", "synthetic-handoff", 1, ack).state, "confirmed")
        self.store = self.module.new(self.lua.globals().options)
        self.assertEqual(self.result("readHandoff", "synthetic-handoff").state, "ready")


if __name__ == "__main__":
    unittest.main()
