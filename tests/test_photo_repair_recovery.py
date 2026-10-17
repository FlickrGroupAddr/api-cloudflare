"""Execute actual repair/recovery modules with transactional SDK-boundary fakes.

The fake catalog has ordinary/private transaction separation and rollback;
the proof transport returns wire bytes and SDK headers. No native or live claim.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
NOW = "2026-10-17T12:00:00Z"


class PhotoRepairRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        publisher = ROOT / "clients/lightroom/publisher/?.lua"
        self.lua.execute(
            f"package.path={str(publisher)!r}..';'..{str(BUNDLE / '?.lua')!r}..';'..package.path"
        )
        for name in ("upload_attempt_store_fixture.lua", "photo_repair_recovery_fixture.lua"):
            self.lua.execute((ROOT / "tests" / name).read_text("utf-8"))
        self.g = self.lua.globals()
        self.module = self.lua.eval('require "UploadAttemptStore"')
        self.codec = self.lua.eval('require "UploadAttemptCodec"')
        self.repair_module = self.lua.eval('require "PhotoCatalogRepair"')
        self.recovery_module = self.lua.eval('require "PhotoProofRecovery"')
        self.scope = self.table(
            {
                "publishServiceLocalId": 12,
                "fgaPublishServiceId": "service-1",
                "publishedCollectionLocalId": 34,
                "photoUuid": self.g.uuid,
            }
        )
        self.album = self.table({"fgaAlbumBindingId": "album-1", "albumBindingRevision": 2})
        self.reopen()

    def table(self, value):
        return self.lua.table_from(value, recursive=True)

    def reopen(self, attempts=1):
        self.store = self.module.new(self.g.options)
        self.g.store = self.store
        self.g.scope = getattr(self, "scope", None)
        self.g.repairOptions.store = self.store
        self.repair = self.repair_module.new(self.g.repairOptions)
        self.g.recoveryOptions = self.table(
            {
                "store": self.store,
                "catalogRepair": self.repair,
                "pcall": self.g.pcall,
                "proofTransport": self.g.proofTransport,
                "linkedFlickrRevision": self.lua.eval("function() return linkedRevision end"),
                "proofAttempts": attempts,
                "backoff": self.lua.eval(
                    "function(seconds) assert(not inside and not ordinaryInside); "
                    "table.insert(events,'backoff_'..seconds); return true end"
                ),
            }
        )
        self.recovery = self.recovery_module.new(self.g.recoveryOptions)

    def inspect(self):
        return self.store.inspect(self.store, self.scope, self.g.photo, NOW)

    def transition(self, name, *args):
        return getattr(self.store, name)(
            self.store, self.scope, self.g.photo, self.inspect().fence, *args, NOW
        )

    def ready(self, reconciled=False):
        choice = self.table({"selectionKind": "none", "selectionRevision": 4, "flickrGroupIds": []})
        self.assertEqual(self.transition("prepare", choice, self.album).state, "prepared")
        self.assertEqual(self.transition("authorize", "authorization-1").state, "authorized")
        self.assertEqual(self.transition("markDispatch").state, "dispatch_marked")
        if reconciled:
            self.transition("recordResult", "upload_outcome_unknown", self.codec.null)
            self.assertEqual(
                self.transition("selectKnownPhoto", "photo-1", self.album, True).state,
                "ambiguity_resolution_pending",
            )
        else:
            self.assertEqual(
                self.transition("recordResult", "returned_upload_id", "photo-1").state,
                "returned_id",
            )

    def resume(self, retry=False):
        return self.recovery.resume(self.recovery, self.scope, self.g.photo, 1, NOW, retry)

    def repair_now(self):
        return self.repair.repair(self.repair, self.scope, 1, NOW)

    def events(self):
        return list(self.g.events.values())

    def assert_verified(self):
        record = self.inspect().record
        self.assertEqual(record.flickrPhotoId, "photo-1")
        self.assertEqual(record.photoProof.state, "acknowledged")
        self.assertEqual(record.catalogPublication.state, "acknowledged")
        self.assertEqual(self.g.remoteId, "photo-1")
        self.assertEqual(self.g.uploadCalls, 0)

    def test_normal_restart_repairs_catalog_before_hosted_proof(self):
        self.ready()
        self.reopen()
        self.resume()
        self.assert_verified()
        self.assertLess(
            self.events().index("catalog_remote_id"), self.events().index("hosted_proof")
        )
        self.assertEqual(self.g.proofCalls, 1)

    def test_reconciliation_commits_ack_before_catalog_and_reopens_locally(self):
        self.ready(reconciled=True)
        self.reopen()
        self.resume()
        self.assert_verified()
        self.assertLess(
            self.events().index("proof_ack_durable"), self.events().index("catalog_remote_id")
        )
        self.assertIn("ambiguity-resolution", self.g.requests[1].path)
        self.reopen()
        self.resume()
        self.assert_verified()
        self.assertEqual(self.g.proofCalls, 1)

    def test_hosted_commit_then_catalog_failure_retries_only_local_write(self):
        self.ready(reconciled=True)
        self.g.failRemoteWrite = True
        self.resume()
        self.assertEqual(self.inspect().record.photoProof.state, "acknowledged")
        self.assertIsNone(self.g.remoteId)
        self.g.failRemoteWrite = False
        self.reopen()
        self.resume()
        self.assert_verified()
        self.assertEqual((self.g.proofCalls, self.g.remoteWrites), (1, 2))

    def test_normal_catalog_failure_does_not_send_proof(self):
        self.ready()
        self.g.failRemoteWrite = True
        self.resume()
        self.assertEqual(self.g.proofCalls, 0)
        self.assertEqual(self.inspect().record.flickrPhotoId, "photo-1")
        self.g.failRemoteWrite = False
        self.reopen()
        self.resume()
        self.assert_verified()

    def test_lost_ack_repeats_exact_tuple_with_bounded_backoff(self):
        self.ready(reconciled=True)
        self.g.proofMode = "lost_once"
        self.reopen(attempts=2)
        self.resume()
        self.assert_verified()
        first, second = self.g.requests[1], self.g.requests[2]
        self.assertEqual(
            (first.method, first.path, first.body), (second.method, second.path, second.body)
        )
        self.assertEqual(json.loads(first.body), {"schemaVersion": 1, "flickrPhotoId": "photo-1"})
        self.assertIn("backoff_1", self.events())
        self.assertEqual(self.g.proofCalls, 2)

    def test_unconfirmed_ack_commit_cannot_write_catalog_and_retries_same_tuple(self):
        self.ready(reconciled=True)
        self.lua.execute("onProof=function() gateStatus='aborted' end")
        self.resume()
        self.assertEqual(self.g.remoteWrites, 0)
        persisted = json.loads(self.g.properties.uploadAttemptRecoveryStore)["attempts"][0]
        self.assertNotEqual(persisted["photoProof"]["state"], "acknowledged")
        first_path, first_body = self.g.requests[1].path, self.g.requests[1].body
        self.g.gateStatus = "executed"
        self.reopen()
        self.resume()
        self.assert_verified()
        self.assertEqual(
            (self.g.requests[2].path, self.g.requests[2].body), (first_path, first_body)
        )

    def test_late_proof_response_cannot_ack_record_revision_change(self):
        self.ready(reconciled=True)
        self.lua.execute(
            "onProof=function() "
            f"local observed=store:inspect(scope,photo,'{NOW}'); "
            "assert(store:checkpointNeedsAttention(scope,photo,observed.fence,"
            f"'photoProof','{NOW}').state=='needs_attention') end"
        )
        result = self.resume()
        self.assertEqual(result.state, "revision_conflict")
        self.assertEqual(self.g.remoteWrites, 0)
        self.assertEqual(self.inspect().record.photoProof.state, "needs_attention")

    def test_budget_exhaustion_retains_id_and_attention_across_restart(self):
        self.ready()
        self.g.proofMode = "lost"
        self.reopen(attempts=2)
        self.resume()
        record = self.inspect().record
        self.assertEqual(record.photoProof.state, "needs_attention")
        self.assertEqual((record.flickrPhotoId, self.g.remoteId), ("photo-1", "photo-1"))
        self.reopen()
        self.resume()
        self.assertEqual(self.g.proofCalls, 2)
        self.g.proofMode = "success"
        self.resume(retry=True)
        self.assert_verified()
        self.assertEqual(self.g.proofCalls, 3)

    def test_conflicting_remote_id_never_overwrites_or_proves(self):
        self.ready()
        self.g.remoteId = "other-photo"
        self.resume()
        self.assertEqual(
            (self.g.remoteId, self.g.remoteWrites, self.g.proofCalls), ("other-photo", 0, 0)
        )
        self.assertEqual(self.inspect().record.flickrPhotoId, "photo-1")

    def test_missing_correlation_and_unresolved_attempt_never_write(self):
        self.g.remoteId = "photo-1"
        self.resume()
        self.assertEqual((self.g.remoteWrites, self.g.proofCalls), (0, 0))
        self.setUp()
        self.ready(reconciled=True)
        self.assertNotEqual(self.repair_now().state, "catalog_acknowledged")
        self.assertEqual(self.g.remoteWrites, 0)

    def test_known_photo_without_authorization_remains_attention_only(self):
        self.assertEqual(self.transition("enterRecovery").state, "history_untrusted")
        self.assertEqual(self.transition("recordMissingHistory").state, "history_untrusted")
        self.assertEqual(
            self.transition("selectKnownPhoto", "photo-1", self.album, True).state,
            "ambiguity_resolution_pending",
        )
        result = self.resume()
        self.assertEqual(result.detail, "missing_correlation")
        self.assertEqual(self.inspect().record.photoProof.state, "needs_attention")
        self.assertEqual(self.inspect().record.flickrPhotoId, "photo-1")
        self.assertEqual((self.g.proofCalls, self.g.remoteWrites), (0, 0))

    def test_acknowledged_catalog_undo_repairs_local_id_without_new_proof(self):
        self.ready()
        self.resume()
        self.assert_verified()
        self.g.remoteId = None
        self.reopen()
        self.resume()
        self.assert_verified()
        self.assertEqual((self.g.proofCalls, self.g.remoteWrites), (1, 2))

    def test_empty_remote_id_repairs_retained_original_id(self):
        for reconciled in (False, True):
            with self.subTest(reconciled=reconciled):
                self.setUp()
                self.ready(reconciled=reconciled)
                self.g.remoteId = ""
                result = self.resume()
                self.assertEqual(result.state, "hosted_photo_verified")
                self.assert_verified()
                self.assertEqual(self.g.remoteWrites, 1)

    def test_relationship_disappearing_at_postwrite_readback_cannot_ack_catalog(self):
        for reconciled in (False, True):
            with self.subTest(reconciled=reconciled):
                self.setUp()
                self.ready(reconciled=reconciled)
                self.lua.execute(
                    "afterOrdinaryGate=function() "
                    "beforeGate=function() hiddenPublication=true end end"
                )
                result = self.resume()
                self.assertNotEqual(result.state, "hosted_photo_verified")
                self.assertNotEqual(self.inspect().record.catalogPublication.state, "acknowledged")
                self.assertEqual(self.g.proofCalls, int(reconciled))

    def test_relationship_disappearing_inside_catalog_ack_gate_cannot_ack(self):
        self.ready(reconciled=True)
        self.lua.execute(
            "afterOrdinaryGate=function() beforeGate=function() "
            "beforeGate=function() hiddenPublication=true end end end"
        )
        result = self.resume()
        self.assertNotEqual(result.state, "hosted_photo_verified")
        self.assertNotEqual(self.inspect().record.catalogPublication.state, "acknowledged")
        self.assertEqual(self.g.proofCalls, 1)

    def test_normal_proof_rechecks_relationship_after_last_private_yield(self):
        for offset in (3, 4):
            with self.subTest(offset=offset):
                self.setUp()
                self.ready()
                self.lua.execute(
                    "afterOrdinaryGate=function() local target=privateGateCount+"
                    f"{offset}; onPrivateGate=function(count) "
                    "if count==target then hiddenPublication=true end end end"
                )
                result = self.resume()
                self.assertTrue(self.g.hiddenPublication)
                self.assertNotEqual(result.state, "hosted_photo_verified")
                self.assertEqual((self.g.proofCalls, self.g.unsafeProofCalls), (0, 0))

    def test_verified_return_rechecks_relationship_after_last_private_yield(self):
        for reconciled in (False, True):
            with self.subTest(reconciled=reconciled):
                self.setUp()
                self.ready(reconciled=reconciled)
                self.resume()
                self.assert_verified()
                # Already acknowledged: adapter inspect, postordinary inspect,
                # then controller's final private inspect. Hide only at the latter.
                self.lua.execute(
                    "afterOrdinaryGate=function() local target=privateGateCount+2; "
                    "onPrivateGate=function(count) "
                    "if count==target then hiddenPublication=true end end end"
                )
                result = self.resume()
                self.assertTrue(self.g.hiddenPublication)
                self.assertNotEqual(result.state, "hosted_photo_verified")
                self.assertEqual(self.g.proofCalls, 1)

    def test_sdk_resolution_changes_are_refused_without_write(self):
        for setup in (
            "active={}",
            "activation={}",
            "owner=false",
            "hiddenPhoto=true",
            "hiddenPublication=true",
            "hiddenService=true",
            "hiddenCollection=true",
            "serviceIdentity='other-service'",
            "service.localIdentifier=99",
            "collection.localIdentifier=99",
            "uuid='00000000-0000-0000-0000-000000000099'",
        ):
            with self.subTest(setup=setup):
                self.setUp()
                self.ready()
                self.lua.execute(setup)
                self.resume()
                self.assertEqual((self.g.remoteWrites, self.g.proofCalls), (0, 0))

    def test_stale_callbacks_recheck_catalog_scope_inside_ordinary_gate(self):
        for mutation in (
            "active={}",
            "activation={}",
            "owner=false",
            "serviceIdentity='other-service'",
            "remoteId='other-photo'",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.ready()
                self.lua.execute(f"beforeOrdinaryGate=function() {mutation} end")
                self.resume()
                self.assertEqual((self.g.remoteWrites, self.g.proofCalls), (0, 0))

    def test_late_proof_reply_cannot_ack_changed_catalog_or_link(self):
        for mutation in ("active={}", "activation={}", "owner=false", "linkedRevision=9"):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.ready(reconciled=True)
                self.lua.execute(f"onProof=function() {mutation} end")
                self.resume()
                self.assertEqual(self.g.remoteWrites, 0)
                # Read persisted bytes directly when active-catalog fencing forbids inspect.
                row = json.loads(self.g.properties.uploadAttemptRecoveryStore)["attempts"][0]
                self.assertNotEqual(row["photoProof"]["state"], "acknowledged")

    def test_record_revision_change_inside_write_gate_fences_old_repair(self):
        self.ready()
        self.lua.execute(
            "beforeOrdinaryGate=function() "
            f"local observed=store:inspect(scope,photo,'{NOW}'); "
            "assert(store:checkpointNeedsAttention(scope,photo,observed.fence,"
            f"'photoProof','{NOW}').state=='needs_attention') end"
        )
        self.resume()
        self.assertEqual((self.g.remoteWrites, self.g.proofCalls), (0, 0))

    def test_proof_conflict_or_wrong_identity_retains_unproved_selected_id(self):
        for mode in ("conflict", "wrong_photo"):
            with self.subTest(mode=mode):
                self.setUp()
                self.ready(reconciled=True)
                self.g.proofMode = mode
                self.resume()
                self.assertEqual(self.g.remoteWrites, 0)
                self.assertEqual(self.inspect().record.flickrPhotoId, "photo-1")
                self.assertNotEqual(self.inspect().record.photoProof.state, "acknowledged")

    def test_strict_raw_proof_bytes_and_sdk_headers_cannot_forge_ack(self):
        for transform in (
            "body='{\"schema\\u0056ersion\":1,'..body:sub(2)",
            "body=body:gsub('\"verificationRevision\":7',"
            "'\"verificationRevision\":7.0000000000000001')",
            "body=body:gsub('photographer_reconciled_ambiguous_upload','unknown_source')",
            "body='{\"unexpected\":true,'..body:sub(2)",
            "body=string.rep(' ',4097)",
            "table.insert(headers,{field='Cache-Control',value='no-store'})",
            "table.remove(headers,3)",
        ):
            with self.subTest(transform=transform):
                self.setUp()
                self.ready(reconciled=True)
                self.lua.execute(
                    f"responseTransform=function(body,headers) {transform}; return body,headers end"
                )
                self.resume()
                self.assertEqual(self.inspect().record.photoProof.state, "needs_attention")
                self.assertEqual((self.g.proofCalls, self.g.remoteWrites), (1, 0))

    def test_deferred_sdk_gate_never_becomes_catalog_ack(self):
        self.ready()
        self.g.ordinaryGateStatus = "queued"
        self.resume()
        self.assertEqual((self.g.remoteWrites, self.g.proofCalls), (0, 0))
        self.assertNotEqual(self.inspect().record.catalogPublication.state, "acknowledged")
        self.g.active = self.lua.table()
        self.assertFalse(self.g.pcall(self.g.deferredOrdinary)[0])
        self.assertEqual(self.g.remoteWrites, 0)

    def test_recovery_has_no_rendition_dependency_or_retained_rendition(self):
        self.ready()
        self.lua.execute(
            "rendition=setmetatable({},{__index=function() error('rendition used') end}); "
            "weakRendition=setmetatable({rendition},{__mode='v'}); rendition=nil"
        )
        self.resume()
        self.assert_verified()
        self.lua.execute("collectgarbage('collect')")
        self.assertIsNone(self.g.weakRendition[1])


if __name__ == "__main__":
    unittest.main()
