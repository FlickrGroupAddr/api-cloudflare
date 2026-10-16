"""Actual Lua5.1 binding-only outbox and controller composition; synthetic SDK."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
HARNESS = r"""
properties, plugin, catalog = {}, {}, {}
activeCatalog,gateResult,mutations = catalog,"executed",0
identity={installationId="synthetic-installation",linkedFlickrRevision=2}
function catalog:getPropertyForPlugin(p,key)
    assert(p == plugin and key == "existingPhotoGroupOutboxV1")
    if readFailure then error("SECRET read failure") end
    return properties[key]
end
function catalog:setPropertyForPlugin(p,key,value)
    assert(insideGate and p == plugin and key == "existingPhotoGroupOutboxV1")
    mutations=mutations+1; properties[key]=value
    if writeFailure then error("SECRET write failure") end
end
function catalog:withPrivateWriteAccessDo(callback,options)
    assert(not insideGate and options.asynchronous == false and options.timeout == 5)
    if beforeGate then local f=beforeGate; beforeGate=nil; f() end
    if gateResult ~= "executed" then pendingCallback=callback; return gateResult end
    local previous=properties.existingPhotoGroupOutboxV1
    insideGate=true
    local ok,err=pcall(callback)
    insideGate=false
    if not ok then properties.existingPhotoGroupOutboxV1=previous; error(err) end
    if mismatch then properties.existingPhotoGroupOutboxV1="SECRET readback mismatch" end
    if switchCatalog then activeCatalog={} end
    if switchIdentity then identity.installationId="synthetic-other" end
    return "executed"
end
options={catalog=catalog,plugin=plugin,pcall=pcall,
    activeCatalog=function() return activeCatalog end,
    currentIdentity=function() return identity end}
function import() error("No SDK imports or photo API permitted") end
"""


class ExistingPhotoGroupStoreTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.json = self.lua.execute((BUNDLE / "dkjson.lua").read_text("utf-8"))
        self.lua.globals().json = self.json
        self.lua.execute("package.preload.dkjson=function() return json end")
        self.lua.execute(HARNESS)
        self.module = self.lua.execute((BUNDLE / "ExistingPhotoGroupStore.lua").read_text("utf-8"))
        self.store = self.module.new(self.lua.globals().options)
        self.scope = self.table(
            {
                "installationId": "synthetic-installation",
                "fgaPhotoBindingId": "synthetic-binding",
                "flickrPhotoId": "synthetic-photo",
                "linkedFlickrRevision": 2,
                "sourceKind": "existing_public_flickr_photo",
            }
        )
        self.binding = self.table(
            {
                "fgaPhotoBindingId": "synthetic-binding",
                "flickrPhotoId": "synthetic-photo",
                "linkRevision": 2,
                "verificationRevision": 3,
                "sourceKind": "existing_public_flickr_photo",
            }
        )

    def table(self, value):
        return self.lua.table_from(value, recursive=True)

    def result(self, method, *args):
        return getattr(self.store, method)(self.store, self.scope, *args)

    def save(self, groups=("101@N00",), revision=0, handoff: str | None = "synthetic-handoff"):
        return self.result("saveChoice", self.table(list(groups)), revision, handoff, self.binding)

    def raw(self):
        return self.lua.globals().properties[self.module.OUTBOX_FIELD]

    def stored(self) -> Any:
        raw = self.raw()
        return json.loads(raw) if raw else None

    def ack(self, revision=1, groups=("101@N00",)):
        ack = self.table(
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
            }
        )
        ack.binding = self.binding
        for row in ack.submissions.values():
            row.permanentSubmissionBlock = self.json.null
        return ack

    def test_absent_choice_and_atomic_snapshot_have_no_local_photo_identity(self):
        self.assertEqual(self.result("readChoice").state, "ready")
        self.assertIsNone(self.result("readChoice").selection)
        self.assertIsNone(self.raw())
        saved = self.save(("202@N00", "101@N00"))
        self.assertEqual(saved.state, "saved")
        self.assertEqual(saved.selection.selectionRevision, 1)
        self.assertEqual(saved.handoff.outboxRevision, 1)
        self.assertEqual(self.stored()["records"][0]["flickrGroupIds"], ["101@N00", "202@N00"])
        for prohibited in (
            "photoUuid",
            "publishServiceLocalId",
            "publishedCollectionLocalId",
            "credential",
        ):
            self.assertNotIn(prohibited, self.raw())
        saved.handoff.flickrGroupIds[1] = "999@N00"
        self.store = self.module.new(self.lua.globals().options)
        self.assertEqual(self.result("readChoice").selection.flickrGroupIds[1], "101@N00")

    def test_ack_retained_and_next_revision_never_reuses_consumed_identity(self):
        self.save()
        self.assertTrue(
            self.result("confirm", "synthetic-handoff", 1, self.ack()).selectionConsumed
        )
        self.assertIsNone(self.result("readChoice").selection)
        retained = self.stored()["records"][0]
        self.assertEqual(retained["state"], "acknowledged")
        self.assertEqual(retained["submissions"][0]["fgaSubmissionIntentId"], "synthetic-intent-0")
        self.assertEqual(
            self.save(("202@N00",), 0, "synthetic-next").selection.selectionRevision, 2
        )
        self.assertEqual(
            self.result("confirm", "synthetic-handoff", 1, self.ack()).state, "revision_conflict"
        )
        self.assertFalse(
            self.result("confirm", "synthetic-handoff", 2, self.ack()).selectionConsumed
        )
        self.assertEqual(self.result("readChoice").selection.selectionRevision, 2)

    def test_late_ack_does_not_hide_newer_unresolved_choice(self):
        self.save()
        self.assertEqual(self.save(("202@N00",), 1, "synthetic-next").state, "saved")
        self.assertFalse(
            self.result("confirm", "synthetic-handoff", 1, self.ack()).selectionConsumed
        )
        self.assertEqual(self.result("readChoice").selection.flickrGroupIds[1], "202@N00")
        self.assertEqual(self.stored()["records"][0]["flickrGroupIds"], ["101@N00"])

    def test_restart_enumerates_older_unresolved_after_latest_acknowledgement(self):
        self.save(handoff="synthetic-older")
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
        self.scope.fgaPhotoBindingId = "synthetic-other"
        self.assertEqual(len(self.result("listPending").handoffs), 0)

    def test_exact_scope_and_binding_refuse_wrong_installation_link_source_or_photo(self):
        self.save()
        before = self.raw()
        for key, value in (
            ("installationId", "synthetic-other"),
            ("linkedFlickrRevision", 4),
            ("fgaPhotoBindingId", "synthetic-other"),
            ("flickrPhotoId", "synthetic-other"),
            ("sourceKind", "fga_direct_upload"),
        ):
            prior = self.scope[key]
            self.scope[key] = value
            self.assertNotEqual(self.save(revision=1, handoff="synthetic-wrong").state, "saved")
            self.assertNotEqual(
                self.result("confirm", "synthetic-handoff", 1, self.ack()).state, "confirmed"
            )
            self.scope[key] = prior
            self.assertEqual(self.raw(), before)
        self.binding.verificationRevision = 0
        self.assertEqual(self.save(revision=1, handoff="synthetic-wrong").state, "handoff_invalid")

    def test_empty_duplicate_oversized_and_unsnapshotted_queues_refuse(self):
        for groups in ([], ["101@N00"] * 2, [f"{index}@N00" for index in range(61)], ["SECRET\n"]):
            self.assertEqual(self.save(groups).state, "choice_invalid")
        self.assertEqual(self.save(handoff=None).state, "handoff_invalid")
        self.scope.photoUuid = "fabricated"
        self.assertEqual(self.save().state, "scope_invalid")
        self.assertEqual(self.lua.globals().mutations, 0)

    def test_bad_json_unknown_schema_and_extra_fields_are_preserved(self):
        for raw in (
            "SECRET",
            "",
            "null",
            "{}",
            '{"schemaVersion":2,"records":[]}',
            '{"schemaVersion":1,"records":{}}',
            '{"schemaVersion":1,"records":[],}',
            '{"schemaVersion":1 "records":[]}',
            '{"schemaVersion":1,"schema\\u0056ersion":1,"records":[]}',
            '{/*comment*/"schemaVersion":1,"records":[]}',
            '{"schemaVersion":1,"records":[]} false',
            '{"schemaVersion":1,"records":[],"credential":"SECRET"}',
        ):
            self.lua.globals().properties[self.module.OUTBOX_FIELD] = raw
            result = self.save()
            self.assertEqual(result.state, "stored_invalid")
            self.assertEqual(self.raw(), raw)
            self.assertEqual(self.lua.globals().mutations, 0)
            self.assertNotIn("SECRET", self.json.encode(result))

    def test_semantic_corruption_and_duplicate_scope_revisions_fail_closed(self):
        self.save()
        original = self.stored()["records"][0]
        variants = [
            {**original, "photoUuid": "fabricated"},
            {**original, "selectionRevision": 0},
            {**original, "outboxRevision": 3},
            {**original, "sourceKind": "unknown"},
            {**original, "binding": {**original["binding"], "flickrPhotoId": "synthetic-other"}},
            {**original, "choice": "none", "flickrGroupIds": []},
            {**original, "workflow": "unknown"},
        ]
        for record in variants:
            raw = json.dumps({"schemaVersion": 1, "records": [record]})
            self.lua.globals().properties[self.module.OUTBOX_FIELD] = raw
            self.assertEqual(
                self.save(revision=1, handoff="synthetic-next").state, "stored_invalid"
            )
            self.assertEqual(self.raw(), raw)
        other = {**original, "handoffId": "synthetic-second"}
        raw = json.dumps({"schemaVersion": 1, "records": [original, other]})
        self.lua.globals().properties[self.module.OUTBOX_FIELD] = raw
        self.assertEqual(self.result("readChoice").state, "stored_invalid")

    def test_count_and_byte_limits_preserve_all_retained_records(self):
        for index in range(self.module.MAX_OUTBOX_ENTRIES):
            self.assertEqual(
                self.save(revision=index, handoff=f"synthetic-{index:03}").state, "saved"
            )
        before = self.raw()
        self.assertEqual(self.save(revision=128, handoff="synthetic-full").state, "storage_full")
        self.assertEqual(self.raw(), before)
        self.lua.globals().properties[self.module.OUTBOX_FIELD] = " " * (
            self.module.MAX_OUTBOX_BYTES + 1
        )
        self.assertEqual(self.result("readChoice").state, "stored_invalid")
        self.lua.globals().properties[self.module.OUTBOX_FIELD] = None
        self.module.MAX_OUTBOX_BYTES = 20
        self.assertEqual(self.save().state, "storage_full")
        self.assertIsNone(self.raw())

    def test_high_integer_link_proof_and_selection_revisions_are_exact(self):
        high = 9007199254740991
        self.scope.linkedFlickrRevision = high
        self.binding.linkRevision = high
        self.binding.verificationRevision = high
        self.lua.globals().identity.linkedFlickrRevision = high
        self.save()
        record = self.stored()["records"][0]
        self.assertEqual(record["linkedFlickrRevision"], high)
        self.assertEqual(record["binding"]["verificationRevision"], high)
        record["selectionRevision"] = 100000000000001
        self.lua.globals().properties[self.module.OUTBOX_FIELD] = json.dumps(
            {"schemaVersion": 1, "records": [record]}
        )
        self.assertEqual(
            self.save(revision=100000000000001, handoff="synthetic-next").state, "saved"
        )
        self.assertEqual(self.stored()["records"][1]["selectionRevision"], 100000000000002)
        record["selectionRevision"] = high
        self.lua.globals().properties[self.module.OUTBOX_FIELD] = json.dumps(
            {"schemaVersion": 1, "records": [record]}
        )
        self.assertEqual(
            self.save(revision=high, handoff="synthetic-max").state, "revision_exhausted"
        )

    def test_revision_cas_is_checked_after_gate_acquisition_and_inputs_are_frozen(self):
        self.save()
        changed = self.stored()
        changed["records"][0]["selectionRevision"] = 2
        self.lua.globals().concurrentRaw = json.dumps(changed)
        self.lua.execute(
            "beforeGate=function() properties.existingPhotoGroupOutboxV1=concurrentRaw end"
        )
        self.assertEqual(self.save(revision=1, handoff="synthetic-next").state, "revision_conflict")
        self.lua.globals().callerScope = self.scope
        self.lua.globals().callerBinding = self.binding
        self.lua.execute("""
            beforeGate=function()
                callerScope.flickrPhotoId="synthetic-retarget"
                callerBinding.verificationRevision=4
            end
        """)
        result = self.save(revision=2, handoff="synthetic-frozen")
        self.assertEqual(result.state, "saved")
        self.assertEqual(result.handoff.flickrPhotoId, "synthetic-photo")
        self.assertEqual(result.handoff.binding.verificationRevision, 3)

    def test_failures_roll_back_and_nonexecuted_delayed_callbacks_are_fenced(self):
        self.lua.globals().writeFailure = True
        self.assertEqual(self.save().state, "storage_unavailable")
        self.assertIsNone(self.raw())
        self.lua.globals().writeFailure = False
        for result in ("queued", "aborted", "unknown"):
            self.lua.globals().gateResult = result
            mutations = self.lua.globals().mutations
            self.assertEqual(self.save().state, "write_unconfirmed")
            success = self.lua.eval("function() return pcall(pendingCallback) end")()
            self.assertFalse(success[0])
            self.assertEqual(self.lua.globals().mutations, mutations)

    def test_catalog_identity_read_failures_and_mismatch_never_claim_success(self):
        for injection, expected in (
            ('options.workflow="unknown"', "scope_invalid"),
            ("activeCatalog={}", "scope_invalid"),
            ("readFailure=true", "storage_unavailable"),
            ("mismatch=true", "write_unconfirmed"),
            ("switchCatalog=true", "write_unconfirmed"),
            ("switchIdentity=true", "write_unconfirmed"),
        ):
            self.setUp()
            self.lua.execute(injection)
            result = self.save()
            self.assertEqual(result.state, expected)
            self.assertNotIn("SECRET", self.json.encode(result))

    def test_partial_or_contradictory_ack_retains_prepared_record(self):
        self.save()
        for mutation in ("missing", "created", "state", "block", "photo", "revision"):
            ack = self.ack()
            if mutation == "missing":
                ack.submissions = self.table([])
            elif mutation == "created":
                ack.submissions[1].created = "true"
            elif mutation == "state":
                ack.submissions[1].state = "unknown"
            elif mutation == "block":
                ack.submissions[1].state = "delivery_uncertain"
            elif mutation == "photo":
                ack.binding = self.table({"fgaPhotoBindingId": "synthetic-foreign"})
            else:
                ack.selectionRevision = 2
            self.assertEqual(
                self.result("confirm", "synthetic-handoff", 1, ack).state, "ack_invalid"
            )
            self.assertEqual(self.stored()["records"][0]["state"], "prepared")
        ack = self.ack()
        row = ack.submissions[1]
        row.state, row.created = "moderation_submitted", False
        row.permanentSubmissionBlock = self.table(
            {"reasonCode": "moderation_submission_recorded", "createdAt": "2026-10-16T12:00:00Z"}
        )
        self.assertEqual(self.result("confirm", "synthetic-handoff", 1, ack).state, "confirmed")
        self.store = self.module.new(self.lua.globals().options)
        self.assertEqual(self.result("readHandoff", "synthetic-handoff").state, "ready")

    def _exercise_controller(self):
        self.lua.globals().store = self.store
        self.lua.globals().scope = self.scope
        self.lua.globals().Controller = self.lua.execute(
            (BUNDLE / "GroupSelectionController.lua").read_text("utf-8")
        )
        self.lua.globals().client = self.lua.execute(
            (ROOT / "clients/lightroom/GroupSubmissionClient.lua").read_text("utf-8")
        )
        self.lua.execute("""
            local binding={fgaPhotoBindingId="synthetic-binding",flickrPhotoId="synthetic-photo",
                linkedFlickrRevision=2,verificationRevision=3,sourceKind=scope.sourceKind}
            posts,proofs=0,0
            local deps={store=store,call=pcall,now=function() return 0 end,
                credential=function() return string.rep("0000-",12).."0000" end,
                newHandoffId=function() return "synthetic-composed" end,
                client=client,jsonNull=json.null,encode=json.encode,
                decode=function(body) return json.decode(body,1,json.null) end,
                prove=function()
                    proofs=proofs+1; binding.verificationRevision=4; return binding
                end,
                post=function(_,body)
                    posts=posts+1
                    local persisted=json.decode(properties.existingPhotoGroupOutboxV1)
                    assert(#persisted.records == 1 and persisted.records[1].state == "prepared")
                    assert(persisted.records[1].binding.verificationRevision == 4)
                    local request=json.decode(body)
                    assert(#request.flickrGroupIds == 1 and request.flickrGroupIds[1] == "101@N00")
                    return json.encode({schemaVersion=2,fgaPhotoBindingId="synthetic-binding",
                        flickrPhotoId="synthetic-photo",submissions={{
                            fgaSubmissionIntentId="synthetic-intent",flickrGroupId="101@N00",
                            state="queued",created=true,permanentSubmissionBlock=json.null}}}),{status=202}
                end}
            local eligibility={state="ready",bound=true,fgaPhotoBindingId="synthetic-binding",
                flickrPhotoId="synthetic-photo",eligibleGroups={{flickrGroupId="101@N00",displayName="Synthetic"}}}
            local context={workflow="existing_public_photo"}
            local c=Controller.new(deps,scope,eligibility,binding,context)
            assert(c.model.ready and Controller.toggle(c.model,"101@N00",true))
            assert(c:commit().state == "accepted")
            assert(posts == 1 and proofs == 1 and not c.model.ready)
        """)
        self.assertEqual(self.stored()["records"][0]["state"], "acknowledged")
        self.assertEqual(self.stored()["records"][0]["sourceKind"], self.scope.sourceKind)
        self.assertEqual(self.stored()["records"][0]["workflow"], "existing_public_photo")
        self.assertNotIn("0000-", self.raw())

    def test_actual_existing_public_controller_queues_without_any_lrphoto(self):
        self._exercise_controller()

    def test_public_workflow_refreshes_proof_with_preserved_direct_upload_provenance(self):
        self.scope.sourceKind = "fga_direct_upload"
        self.binding.sourceKind = "fga_direct_upload"
        self._exercise_controller()


if __name__ == "__main__":
    unittest.main()
