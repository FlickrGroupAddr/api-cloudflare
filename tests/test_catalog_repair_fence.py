"""Direct read-only repair-fence checks against the real upload store in Lua5.1."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-17T12:00:00Z"


class CatalogRepairFenceTests(unittest.TestCase):
    def setUp(self, reconciled=False):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        bundle = ROOT / "clients/lightroom/FGA-LrC15.lrplugin/?.lua"
        publisher = ROOT / "clients/lightroom/publisher/?.lua"
        self.lua.execute(
            f"package.path={str(publisher)!r}..';'..{str(bundle)!r}..';'..package.path"
        )
        for name in ("upload_attempt_store_fixture.lua", "photo_repair_recovery_fixture.lua"):
            self.lua.execute((ROOT / "tests" / name).read_text("utf-8"))
        self.lua.execute(
            "C=require 'UploadAttemptCodec'; store=require('UploadAttemptStore').new(options); "
            "scope={publishServiceLocalId=12,fgaPublishServiceId='service-1',"
            "publishedCollectionLocalId=34,photoUuid=uuid}; "
            "function validate(e) local result; catalog:withWriteAccessDo('test',function() "
            "result=store:validateCatalogRepair(scope,photo,e,'2026-10-17T12:00:00Z') "
            "end,{timeout=5,asynchronous=false}); return result end"
        )
        self.g = self.lua.globals()
        self.store, self.scope, self.photo = self.g.store, self.g.scope, self.g.photo
        choice = self.lua.table_from(
            {"selectionKind": "none", "selectionRevision": 4, "flickrGroupIds": []},
            recursive=True,
        )
        album = self.lua.table_from({"fgaAlbumBindingId": "album-1", "albumBindingRevision": 2})
        self.assertEqual(self.transition("prepare", choice, album).state, "prepared")
        self.assertEqual(self.transition("authorize", "authorization-1").state, "authorized")
        self.assertEqual(self.transition("markDispatch").state, "dispatch_marked")
        if reconciled:
            self.assertEqual(
                self.transition("recordResult", "upload_outcome_unknown", self.g.C.null).state,
                "upload_outcome_unknown",
            )
            self.assertEqual(
                self.transition("selectKnownPhoto", "photo-1", album, True).state,
                "ambiguity_resolution_pending",
            )
        else:
            self.assertEqual(
                self.transition("recordResult", "returned_upload_id", "photo-1").state,
                "returned_id",
            )
        self.fence = self.inspect().fence
        self.lua.execute(
            "repairOptions.store=store; "
            "local repair=require('PhotoCatalogRepair').new(repairOptions); "
            "recovery=require('PhotoProofRecovery').new({store=store,catalogRepair=repair,"
            "pcall=pcall,proofTransport=proofTransport,proofAttempts=1,"
            "linkedFlickrRevision=function() return linkedRevision end})"
        )

    def inspect(self):
        return self.store.inspect(self.store, self.scope, self.photo, NOW)

    def transition(self, name, *args):
        return getattr(self.store, name)(
            self.store, self.scope, self.photo, self.inspect().fence, *args, NOW
        )

    def test_exact_snapshot_is_detached_and_enters_no_nested_gate_or_write(self):
        raw, writes = self.g.properties.uploadAttemptRecoveryStore, self.g.writes
        self.lua.execute("catalog.withPrivateWriteAccessDo=function() error('nested gate') end")
        result = self.g.validate(self.fence)
        self.assertEqual(result.state, "ready")
        result.record.flickrPhotoId = "tampered"
        self.assertEqual(self.g.validate(self.fence).record.flickrPhotoId, "photo-1")
        self.assertEqual(
            (self.g.properties.uploadAttemptRecoveryStore, self.g.writes), (raw, writes)
        )

    def test_empty_id_repairs_and_undo_retry_reuses_the_acknowledged_proof(self):
        self.g.remoteId = ""
        raw, writes = self.g.properties.uploadAttemptRecoveryStore, self.g.writes
        observed = self.inspect()
        self.assertEqual(observed.classification, "returned_id")
        self.assertEqual(observed.gate.state, "ordinary")
        self.assertEqual(self.g.validate(observed.fence).state, "ready")
        self.assertEqual(
            (self.g.properties.uploadAttemptRecoveryStore, self.g.writes), (raw, writes)
        )
        result = self.g.recovery.resume(self.g.recovery, self.scope, self.photo, 1, NOW, False)
        self.assertEqual(result.state, "hosted_photo_verified")
        self.assertEqual(
            (self.g.remoteId, self.g.remoteWrites, self.g.proofCalls), ("photo-1", 1, 1)
        )
        self.g.remoteId = ""
        result = self.g.recovery.resume(self.g.recovery, self.scope, self.photo, 1, NOW, False)
        self.assertEqual(result.state, "hosted_photo_verified")
        self.assertEqual(
            (self.g.remoteId, self.g.remoteWrites, self.g.proofCalls), ("photo-1", 2, 1)
        )
        self.assertEqual(self.inspect().gate.state, "ordinary")

    def test_reconciliation_empty_id_keeps_durable_proof_before_catalog_write(self):
        self.setUp(reconciled=True)
        self.g.remoteId = ""
        result = self.g.recovery.resume(self.g.recovery, self.scope, self.photo, 1, NOW, False)
        self.assertEqual(result.state, "hosted_photo_verified")
        self.assertEqual(
            (self.g.remoteId, self.g.remoteWrites, self.g.proofCalls), ("photo-1", 1, 1)
        )
        events = list(self.g.events.values())
        self.assertLess(events.index("proof_ack_durable"), events.index("catalog_remote_id"))
        self.assertEqual(self.inspect().gate.state, "ordinary")

    def test_catalog_ack_predicate_runs_inside_gate_and_rejects_stale_relationship(self):
        self.g.remoteId = "photo-1"
        raw, writes = self.g.properties.uploadAttemptRecoveryStore, self.g.writes
        predicate = self.lua.eval("function() assert(inside); return false end")
        result = self.store.acknowledgeCatalog(
            self.store, self.scope, self.photo, self.fence, "photo-1", NOW, predicate
        )
        self.assertEqual(result.state, "correlation_invalid")
        self.assertEqual(
            (self.g.properties.uploadAttemptRecoveryStore, self.g.writes), (raw, writes)
        )
        self.assertEqual(self.inspect().record.catalogPublication.state, "pending")

    def test_catalog_ack_rechecks_relationship_after_committed_readback(self):
        self.g.remoteId = "photo-1"
        predicate = self.lua.eval("function() return inside==true end")
        result = self.store.acknowledgeCatalog(
            self.store, self.scope, self.photo, self.fence, "photo-1", NOW, predicate
        )
        self.assertEqual(result.state, "write_unconfirmed")
        self.assertEqual(self.inspect().record.catalogPublication.state, "acknowledged")

    def test_catalog_ack_predicate_exception_cannot_acknowledge(self):
        self.g.remoteId = "photo-1"
        predicate = self.lua.eval("function() error('synthetic observer failure') end")
        result = self.store.acknowledgeCatalog(
            self.store, self.scope, self.photo, self.fence, "photo-1", NOW, predicate
        )
        self.assertEqual(result.state, "correlation_invalid")
        self.assertEqual(self.inspect().record.catalogPublication.state, "pending")

    def test_every_revision_and_attempt_is_checked(self):
        for key in (
            "storeRevision",
            "gateRevision",
            "attemptNumber",
            "recordRevision",
            "metadataRevision",
        ):
            with self.subTest(key=key):
                stale = self.g.C.clone(self.fence)
                stale[key] += 1
                self.assertEqual(self.g.validate(stale).state, "revision_conflict")

    def test_malformed_journal_and_photo_metadata_are_never_repaired(self):
        raw = self.g.properties.uploadAttemptRecoveryStore
        self.g.properties.uploadAttemptRecoveryStore = "{}"
        self.assertEqual(self.g.validate(self.fence).state, "stored_invalid")
        self.g.properties.uploadAttemptRecoveryStore = raw
        self.g.photoProperties.publishedPhotoCorrelations = "{}"
        self.assertEqual(self.g.validate(self.fence).state, "photo_metadata_invalid")

    def test_pending_assertion_is_not_catalog_repair_authority(self):
        self.lua.execute(
            "local d=C.decode(properties.uploadAttemptRecoveryStore,33554432); "
            "local r=d.attempts[1]; r.uploadPhase='ambiguity_resolution_pending'; "
            "r.resultKind='photographer_assertion'; "
            "r.recoveryDisposition='known_photo_reconciliation'; "
            "r.recoveryConfirmedAt='2026-10-17T12:00:00Z'; "
            "properties.uploadAttemptRecoveryStore=C.encode(d)"
        )
        self.assertEqual(self.g.validate(self.fence).state, "correlation_invalid")

    def test_history_remote_and_reader_failures_close_the_seam(self):
        self.g.remoteId = "foreign-photo"
        self.assertEqual(self.g.validate(self.fence).state, "catalog_repair_required")
        self.g.remoteId = None
        self.g.readFailure = True
        self.assertEqual(self.g.validate(self.fence).state, "storage_unavailable")
        self.g.readFailure = False
        self.lua.execute(
            "local d=C.decode(properties.uploadAttemptRecoveryStore,33554432); "
            "d.recoveryGate.state='history_untrusted'; "
            "d.recoveryGate.confirmedAt='2026-10-17T12:00:00Z'; "
            "properties.uploadAttemptRecoveryStore=C.encode(d)"
        )
        self.assertEqual(self.g.validate(self.fence).state, "history_untrusted")


if __name__ == "__main__":
    unittest.main()
