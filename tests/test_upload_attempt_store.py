"""Execute the dormant upload store's actual Lua5.1 transitions; synthetic SDK only."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
NOW = "2026-10-17T12:00:00Z"
UUID = "00000000-0000-0000-0000-000000000095"


class UploadAttemptStoreTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.lua.execute(f"package.path={str(BUNDLE / '?.lua')!r}..';'..package.path")
        self.lua.execute((ROOT / "tests/upload_attempt_store_fixture.lua").read_text("utf-8"))
        self.module = self.lua.eval('require "UploadAttemptStore"')
        self.codec = self.lua.eval('require "UploadAttemptCodec"')
        self.null = self.codec.null
        self.store = self.module.new(self.lua.globals().options)
        self.photo = self.lua.globals().photo
        self.scope = self.table(
            {
                "publishServiceLocalId": 12,
                "fgaPublishServiceId": "service-1",
                "publishedCollectionLocalId": 34,
                "photoUuid": UUID,
            }
        )
        self.album = self.table({"fgaAlbumBindingId": "album-1", "albumBindingRevision": 2})

    def table(self, value):
        return self.lua.table_from(value, recursive=True)

    def inspect(self, number=None):
        return self.store.inspect(self.store, self.scope, self.photo, NOW, number)

    def fence(self, number=None):
        result = self.inspect(number)
        self.assertEqual(result.state, "ready")
        return result.fence

    def call(self, method, *args, fence=None):
        return getattr(self.store, method)(
            self.store, self.scope, self.photo, fence or self.fence(), *args, NOW
        )

    def selection(self, groups=(), kind=None):
        return self.table(
            {
                "selectionKind": kind or ("groups" if groups else "none"),
                "selectionRevision": self.null if kind == "absent" else 4,
                "flickrGroupIds": list(groups),
            }
        )

    def prepare(self, groups=(), kind=None):
        return self.call("prepare", self.selection(groups, kind), self.album)

    def authorize(self):
        return self.call("authorize", f"authorization-{int(self.inspect().record.attemptNumber)}")

    def dispatch(self):
        return self.call("markDispatch")

    def result(self, kind="returned_upload_id", photo_id: str | None = "photo-1"):
        return self.call("recordResult", kind, self.null if photo_id is None else photo_id)

    def proof(self):
        return self.call(
            "acknowledgeProof",
            self.table(
                {
                    "fgaPhotoBindingId": "binding-1",
                    "flickrPhotoId": "photo-1",
                    "linkedFlickrRevision": 6,
                    "verificationRevision": 7,
                }
            ),
        )

    def album_ack(self):
        return self.call(
            "acknowledgeAlbum",
            self.table(
                {
                    "fgaAlbumBindingId": "album-1",
                    "fgaPhotoBindingId": "binding-1",
                    "albumBindingRevision": 2,
                    "flickrPhotosetId": "photoset-1",
                    "hostedObligationState": "membership_verified",
                    "fgaPublishServiceId": self.scope.fgaPublishServiceId,
                    "localCollectionIdentifier": str(int(self.scope.publishedCollectionLocalId)),
                    "linkedFlickrRevision": 6,
                }
            ),
        )

    def catalog_ack(self):
        self.lua.globals().remoteId = "photo-1"
        return self.call("acknowledgeCatalog", "photo-1")

    def group_ack(self, groups=("group-1",)):
        return self.call(
            "acknowledgeGroups",
            self.table({"fgaPhotoBindingId": "binding-1", "verificationRevision": 7}),
            self.table(
                [
                    {
                        "fgaSubmissionIntentId": f"intent-{index}",
                        "flickrGroupId": group,
                        "state": "queued",
                        "created": True,
                        "permanentSubmissionBlock": self.null,
                    }
                    for index, group in enumerate(groups)
                ]
            ),
        )

    def ready_result(self, groups=()):
        self.assertEqual(self.prepare(groups).state, "prepared")
        self.assertEqual(self.authorize().state, "authorized")
        self.assertEqual(self.dispatch().state, "dispatch_marked")
        self.assertEqual(self.result().state, "returned_id")

    def completed(self, groups=()):
        self.ready_result(groups)
        self.assertEqual(self.catalog_ack().state, "catalog_acknowledged")
        self.assertEqual(self.proof().state, "proof_acknowledged")
        self.assertEqual(self.album_ack().state, "album_acknowledged")
        if groups:
            self.assertEqual(self.group_ack(groups).state, "groups_acknowledged")

    def raw(self):
        return self.lua.globals().properties.uploadAttemptRecoveryStore

    def document(self):
        return json.loads(self.raw())

    def put(self, value):
        self.lua.globals().properties.uploadAttemptRecoveryStore = json.dumps(value)

    def test_normal_success_checkpoints_and_atomic_retirement(self):
        self.completed(("group-1", "group-2"))
        before = self.document()
        result = self.call("retire", "newer_revision_preserved")
        self.assertEqual(result.state, "retired")
        self.assertEqual(self.document()["attempts"], [])
        self.assertEqual(self.document()["nextAttemptNumber"], 2)
        self.assertEqual(self.document()["storeRevision"], before["storeRevision"] + 1)
        metadata = json.loads(self.lua.globals().photoProperties.publishedPhotoCorrelations)
        self.assertEqual(metadata["metadataRevision"], 1)
        self.assertTrue(metadata["entries"][0]["groupHandoffAcknowledged"])
        self.assertEqual(self.inspect().classification, "published_correlation")
        self.assertEqual(self.prepare().state, "catalog_repair_required")

    def test_zero_and_absent_snapshot_never_create_group_checkpoint(self):
        for kind in ("none", "absent"):
            with self.subTest(kind=kind):
                self.setUp()
                result = self.prepare(kind=kind)
                self.assertEqual(result.state, "prepared")
                self.assertEqual(result.record.selectionKind, kind)
                self.authorize()
                self.dispatch()
                self.result()
                self.catalog_ack()
                self.proof()
                self.album_ack()
                self.assertEqual(self.group_ack(()).state, "group_acknowledgement_invalid")
                self.assertEqual(
                    self.call("retire", "absent" if kind == "absent" else "consumed").state,
                    "retired",
                )

    def test_snapshot_is_immutable_and_does_not_alias_inputs_or_results(self):
        selection = self.selection(("group-1",))
        result = self.call("prepare", selection, self.album)
        selection.flickrGroupIds[1] = "changed"
        result.record.flickrGroupIds[1] = "changed-again"
        self.album.fgaAlbumBindingId = "changed-album"
        record = self.inspect().record
        self.assertEqual(record.flickrGroupIds[1], "group-1")
        self.assertEqual(record.albumObligation.fgaAlbumBindingId, "album-1")
        self.assertEqual(self.authorize().state, "authorized")
        self.assertEqual(self.call("authorize", "replacement").state, "transition_invalid")

    def test_one_shot_permission_and_reopen_never_replay_dispatch(self):
        self.prepare()
        self.authorize()
        result = self.dispatch()
        self.assertEqual(self.inspect().classification, "upload_outcome_unknown")
        self.assertEqual(
            self.store.takeDispatchPermission(self.store, result.dispatchPermission, NOW).state,
            "invoke_once",
        )
        self.assertEqual(
            self.store.takeDispatchPermission(self.store, result.dispatchPermission, NOW).state,
            "dispatch_refused",
        )
        self.store = self.module.new(self.lua.globals().options)
        self.assertEqual(self.dispatch().state, "transition_invalid")
        self.assertEqual(self.call("cancelBeforeInvocation").state, "transition_invalid")

    def test_permission_is_burned_after_unrelated_cas_or_lost_owner(self):
        self.prepare()
        self.authorize()
        permit = self.dispatch().dispatchPermission
        self.lua.globals().owner = False
        self.assertEqual(
            self.store.takeDispatchPermission(self.store, permit, NOW).state, "scope_invalid"
        )
        self.lua.globals().owner = True
        self.assertEqual(
            self.store.takeDispatchPermission(self.store, permit, NOW).state, "dispatch_refused"
        )

    def test_unknown_rejection_and_safe_unused_successor_keep_numbers(self):
        self.prepare()
        self.authorize()
        old = self.fence()
        result = self.call("successor", self.selection(), self.album, "unused", True)
        self.assertEqual(result.state, "prepared")
        self.assertEqual(result.successorFence.storeRevision, self.document()["storeRevision"])
        self.assertEqual(result.successor.attemptNumber, 2)
        self.assertEqual(
            self.document()["attempts"][0]["uploadPhase"], "superseded_before_invocation"
        )
        self.assertEqual(self.call("authorize", "stale", fence=old).state, "revision_conflict")
        self.authorize()
        self.dispatch()
        self.assertEqual(self.result("definitive_rejection", None).state, "definitive_rejection")
        self.assertEqual(
            self.call("successor", self.selection(), self.album, "rejected", True).state, "prepared"
        )
        self.assertEqual(self.document()["nextAttemptNumber"], 4)

    def test_unknown_and_deliberate_new_copy_preserve_possible_photo_forever(self):
        self.prepare(("group-1",))
        self.authorize()
        self.dispatch()
        self.assertEqual(
            self.result("upload_outcome_unknown", None).state, "upload_outcome_unknown"
        )
        self.assertEqual(
            self.call("successor", self.selection(), self.album, "new_copy", False).state,
            "confirmation_required",
        )
        result = self.call("successor", self.selection(), self.album, "new_copy", True)
        self.assertEqual(result.state, "prepared")
        predecessor = self.document()["attempts"][0]
        self.assertEqual(predecessor["uploadPhase"], "abandoned_possible_flickr_photo")
        self.assertIsNotNone(predecessor["dispatchMarkedAt"])
        self.assertEqual(predecessor["flickrGroupIds"], ["group-1"])
        self.assertEqual(
            self.call("retireNonDispatch", True, True, fence=self.fence(1)).state,
            "retirement_refused",
        )
        self.assertEqual(self.authorize().state, "authorized")

    def test_cancellation_retirement_requires_report_and_never_reuses_number(self):
        self.prepare()
        self.assertEqual(self.call("cancelBeforeInvocation").state, "cancelled_before_invocation")
        self.assertEqual(self.call("retireNonDispatch", False, True).state, "retirement_refused")
        self.assertEqual(self.call("retireNonDispatch", True, True).state, "retired_nondispatch")
        self.assertEqual(self.prepare().record.attemptNumber, 2)

    def test_photographer_resolution_persists_tuple_and_requires_proof_before_catalog(self):
        self.prepare(("group-1",))
        self.authorize()
        self.dispatch()
        self.result("upload_outcome_unknown", None)
        self.assertEqual(
            self.call("selectKnownPhoto", "photo-1", self.album, True).state,
            "ambiguity_resolution_pending",
        )
        self.assertEqual(self.catalog_ack().state, "correlation_invalid")
        self.assertEqual(self.proof().state, "proof_acknowledged")
        self.assertEqual(self.catalog_ack().state, "catalog_acknowledged")
        self.assertEqual(self.inspect().record.resultKind, "photographer_assertion")
        self.assertEqual(
            self.call("selectKnownPhoto", "other-photo", self.album, True).state,
            "transition_invalid",
        )

    def test_normal_returned_id_requires_catalog_before_proof(self):
        self.ready_result()
        self.assertEqual(self.proof().state, "correlation_invalid")
        self.assertEqual(self.call("retire", "consumed").state, "retirement_refused")
        self.assertEqual(
            self.call("checkpointNeedsAttention", "photoProof").state, "needs_attention"
        )
        self.assertEqual(self.catalog_ack().state, "catalog_acknowledged")
        self.assertEqual(self.proof().state, "proof_acknowledged")

    def test_copy_restore_absent_history_is_not_empty_upload_authority(self):
        self.assertEqual(self.call("enterRecovery").state, "history_untrusted")
        self.store = self.module.new(self.lua.globals().options)
        self.assertEqual(self.prepare().state, "history_untrusted")
        missing = self.call("recordMissingHistory")
        self.assertEqual(missing.record.recordKind, "history_attention")
        self.assertEqual(self.inspect().classification, "history_untrusted")
        self.assertEqual(
            self.call("selectKnownPhoto", "photo-1", self.album, True).state,
            "ambiguity_resolution_pending",
        )
        self.assertEqual(self.proof().state, "proof_acknowledged")
        self.assertEqual(self.catalog_ack().state, "catalog_acknowledged")
        self.assertEqual(self.call("retire", "absent").state, "retirement_refused")

    def test_restore_older_prepared_and_authorized_allows_only_explicit_disposition(self):
        for authorized in (False, True):
            with self.subTest(authorized=authorized):
                self.setUp()
                self.prepare()
                if authorized:
                    self.authorize()
                self.call("enterRecovery")
                self.store = self.module.new(self.lua.globals().options)
                self.assertEqual(self.dispatch().state, "history_untrusted")
                self.assertEqual(self.call("cancelBeforeInvocation").state, "history_untrusted")
                self.assertEqual(
                    self.call("selectKnownPhoto", "photo-1", self.album, True).state,
                    "ambiguity_resolution_pending",
                )
                self.assertIsNone(self.document()["attempts"][0]["dispatchMarkedAt"])

    def test_failed_recovery_persistence_keeps_memory_gate_closed(self):
        fence = self.fence()
        self.lua.globals().gateStatus = "aborted"
        self.assertEqual(self.call("enterRecovery", fence=fence).state, "write_unconfirmed")
        self.lua.globals().gateStatus = "executed"
        self.assertIsNone(self.raw())
        self.assertEqual(self.prepare().state, "history_untrusted")

    def test_strict_malformed_unknown_versions_duplicate_keys_and_utf8_refuse(self):
        self.prepare()
        good = self.document()
        variants = []
        for key, value in (("schemaVersion", 2), ("nextAttemptNumber", 1), ("secret", "NO")):
            d = copy.deepcopy(good)
            d[key] = value
            variants.append(json.dumps(d))
        variants += [
            self.raw().replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1'),
            '{"schemaVersion":1,"schemaVersion":1}',
            '{"schemaVersion":1,"schema\\u0056ersion":1}',
            '{"x":"\\ud800"}',
            '{"x":"\\udc00"}',
            "[1,]",
            '{"x":01}',
            '{"x":1e+}',
        ]
        for raw in variants:
            with self.subTest(raw=raw[:40]):
                self.lua.globals().properties.uploadAttemptRecoveryStore = raw
                before = self.raw()
                self.assertEqual(self.inspect().state, "stored_invalid")
                self.assertEqual(self.raw(), before)
        self.lua.execute(
            "properties.uploadAttemptRecoveryStore='{\"x\":\"'..string.char(192,128)..'\"}'"
        )
        self.assertEqual(self.inspect().state, "stored_invalid")

    def test_duplicate_active_scopes_and_invalid_phase_null_combinations_refuse(self):
        self.prepare()
        good = self.document()
        for mutate in (
            lambda d: d["attempts"][0].update(dispatchMarkedAt=NOW),
            lambda d: d["attempts"][0].update(recordRevision=0),
            lambda d: d["attempts"][0].update(
                flickrGroupIds=["duplicate", "duplicate"], selectionKind="groups"
            ),
            lambda d: d["attempts"][0].update(fgaUploadAuthorizationId="injected"),
            lambda d: d["attempts"][0].update(createdAt="2026-02-30T00:00:00Z"),
        ):
            d = copy.deepcopy(good)
            mutate(d)
            self.put(d)
            self.assertEqual(self.inspect().state, "stored_invalid")
        d = copy.deepcopy(good)
        second = copy.deepcopy(d["attempts"][0])
        second["attemptNumber"] = 2
        d["attempts"].append(second)
        d["nextAttemptNumber"] = 3
        self.put(d)
        self.assertEqual(self.inspect().state, "stored_invalid")

    def test_actual_count_boundary_256_and_257_without_eviction(self):
        self.prepare()
        d = self.document()
        base = d["attempts"][0]
        d["attempts"] = []
        for index in range(255):
            row = copy.deepcopy(base)
            row["attemptNumber"] = index + 1
            row["publishedCollectionLocalId"] = 1000 + index
            row["photoUuid"] = f"00000000-0000-0000-0000-{index:012d}"
            d["attempts"].append(row)
        d["nextAttemptNumber"] = 256
        self.put(d)
        self.assertEqual(self.prepare().state, "prepared")
        self.assertEqual(len(self.document()["attempts"]), 256)
        self.scope.publishedCollectionLocalId = 9999
        before = self.raw()
        self.assertEqual(self.prepare().state, "storage_full")
        self.assertEqual(self.raw(), before)

    def test_maximal_60_id_schema_and_integer_exactness(self):
        groups = tuple(f"{index:03d}" + "g" * 125 for index in range(60))
        self.scope.publishServiceLocalId = 9007199254740991
        self.scope.publishedCollectionLocalId = 9007199254740991
        self.scope.fgaPublishServiceId = "s" * 128
        self.album.fgaAlbumBindingId = "a" * 128
        self.album.albumBindingRevision = 9007199254740991
        self.ready_result(groups)
        self.catalog_ack()
        self.proof()
        self.assertLessEqual(len(self.raw().encode()), self.module.MAX_RECORD_BYTES)
        self.assertEqual(self.document()["attempts"][0]["publishServiceLocalId"], 9007199254740991)
        self.assertEqual(self.group_ack(groups).state, "groups_acknowledged")

    def test_counter_exhaustion_is_refusal_without_wrapping(self):
        self.prepare()
        d = self.document()
        for key in ("storeRevision", "nextAttemptNumber"):
            data = copy.deepcopy(d)
            data[key] = 9007199254740991
            self.put(data)
            before = self.raw()
            if key == "storeRevision":
                self.assertEqual(self.authorize().state, "counter_exhausted")
            else:
                self.scope.publishedCollectionLocalId += 1
                self.assertEqual(self.prepare().state, "storage_full")
            self.assertEqual(self.raw(), before)

    def test_stale_same_and_unrelated_scope_and_metadata_revisions(self):
        self.prepare()
        old = self.fence()
        self.authorize()
        self.assertEqual(self.call("authorize", "other", fence=old).state, "revision_conflict")
        current = self.fence()
        changed = self.table({key: value for key, value in current.items()})
        changed.metadataRevision = 99
        self.assertEqual(self.call("markDispatch", fence=changed).state, "revision_conflict")
        self.scope.publishedCollectionLocalId = 35
        self.assertEqual(self.call("markDispatch", fence=current).state, "revision_conflict")

    def test_gate_abort_timeout_queued_exception_and_delayed_callback_never_mutate(self):
        for status in ("aborted", "queued", "timeout", None):
            with self.subTest(status=status):
                self.setUp()
                fence = self.fence()
                self.lua.globals().gateStatus = status
                self.assertEqual(
                    self.call("prepare", self.selection(), self.album, fence=fence).state,
                    "write_unconfirmed",
                )
                self.assertIsNone(self.raw())
                self.lua.execute("assert(not pcall(delayed))")
                self.assertIsNone(self.raw())
        self.setUp()
        fence = self.fence()
        self.lua.globals().readFailure = True
        self.assertEqual(
            self.call("prepare", self.selection(), self.album, fence=fence).state,
            "storage_unavailable",
        )

    def test_readback_race_and_catalog_switch_deny_dependent_permission(self):
        for hook in (
            'properties.uploadAttemptRecoveryStore=properties.uploadAttemptRecoveryStore.." "',
            "active={}",
            "activation={}",
            "owner=false",
        ):
            with self.subTest(hook=hook):
                self.setUp()
                self.prepare()
                self.authorize()
                fence = self.fence()
                self.lua.execute(f"afterGate=function() {hook} end")
                result = self.call("markDispatch", fence=fence)
                self.assertEqual(result.state, "write_unconfirmed")
                self.assertIsNone(result.dispatchPermission)
                self.assertEqual(
                    self.document()["attempts"][0]["uploadPhase"], "dispatch_may_have_started"
                )

    def test_catalog_switch_before_gate_cannot_write_new_catalog(self):
        fence = self.fence()
        self.lua.execute("beforeGate=function() active={} end")
        self.assertEqual(
            self.call("prepare", self.selection(), self.album, fence=fence).state,
            "storage_unavailable",
        )
        self.assertIsNone(self.raw())
        self.assertEqual(self.lua.globals().writes, 0)

    def test_each_mutation_storage_failure_rolls_back_without_success(self):
        cases = [
            (lambda: None, lambda: self.prepare()),
            (lambda: self.prepare(), lambda: self.authorize()),
            (lambda: (self.prepare(), self.authorize()), lambda: self.dispatch()),
            (lambda: (self.prepare(), self.authorize(), self.dispatch()), lambda: self.result()),
            (lambda: self.prepare(), lambda: self.call("cancelBeforeInvocation")),
            (
                lambda: self.prepare(),
                lambda: self.call("successor", self.selection(), self.album, "unused", True),
            ),
            (lambda: self.ready_result(), lambda: self.catalog_ack()),
            (lambda: (self.ready_result(), self.catalog_ack()), lambda: self.proof()),
            (
                lambda: (self.ready_result(), self.catalog_ack(), self.proof()),
                lambda: self.album_ack(),
            ),
            (
                lambda: (self.ready_result(("group-1",)), self.catalog_ack(), self.proof()),
                lambda: self.group_ack(),
            ),
            (
                lambda: self.ready_result(),
                lambda: self.call("checkpointNeedsAttention", "photoProof"),
            ),
            (lambda: self.prepare(), lambda: self.call("enterRecovery")),
            (lambda: self.call("enterRecovery"), lambda: self.call("recordMissingHistory")),
            (
                lambda: (self.prepare(), self.authorize(), self.dispatch()),
                lambda: self.call("selectKnownPhoto", "photo-1", self.album, True),
            ),
            (
                lambda: (self.prepare(), self.call("cancelBeforeInvocation")),
                lambda: self.call("retireNonDispatch", True, True),
            ),
        ]
        for index, (setup, operation) in enumerate(cases):
            with self.subTest(transition=index):
                self.setUp()
                setup()
                before = self.raw()
                self.lua.globals().failAt = "catalog"
                self.assertEqual(operation().state, "storage_unavailable")
                self.assertEqual(self.raw(), before)

    def test_retirement_both_writes_rollback_and_both_readbacks_required(self):
        for fail_at in ("photo", "catalog"):
            with self.subTest(fail_at=fail_at):
                self.setUp()
                self.completed()
                before = self.raw()
                self.lua.globals().failAt = fail_at
                self.assertEqual(self.call("retire", "consumed").state, "storage_unavailable")
                self.assertEqual(self.raw(), before)
                self.assertIsNone(self.lua.globals().photoProperties.publishedPhotoCorrelations)
        self.setUp()
        self.completed()
        fence = self.fence()
        self.lua.execute(
            "afterGate=function() local value=photoProperties.publishedPhotoCorrelations; "
            'photoProperties.publishedPhotoCorrelations=value.." " end'
        )
        self.assertEqual(self.call("retire", "consumed", fence=fence).state, "write_unconfirmed")

    def test_photo_metadata_malformed_and_existing_remote_id_are_repair_states(self):
        fence = self.fence()
        self.lua.globals().photoProperties.publishedPhotoCorrelations = '{"schemaVersion":2}'
        self.assertEqual(self.inspect().state, "photo_metadata_invalid")
        self.assertEqual(
            self.call("prepare", self.selection(), self.album, fence=fence).state,
            "photo_metadata_invalid",
        )
        self.lua.globals().photoProperties.publishedPhotoCorrelations = None
        self.lua.globals().remoteId = "existing-photo"
        self.assertEqual(self.inspect().classification, "catalog_repair_required")
        self.assertEqual(self.prepare().state, "history_untrusted")
        self.assertEqual(self.document()["recoveryGate"]["state"], "history_untrusted")

    def test_group_ack_rejects_partial_foreign_duplicate_and_unvalidated_block(self):
        self.ready_result(("group-1", "group-2"))
        self.catalog_ack()
        self.proof()
        self.assertEqual(self.group_ack(("group-1",)).state, "group_acknowledgement_invalid")
        self.assertEqual(
            self.group_ack(("group-2", "group-1")).state, "group_acknowledgement_invalid"
        )
        self.assertEqual(self.call("retire", "consumed").state, "retirement_refused")
        self.assertEqual(self.group_ack(("group-1", "group-2")).state, "groups_acknowledged")

    def test_secrets_paths_and_arbitrary_fields_never_enter_schema(self):
        selection = self.selection()
        selection.uploadUrl = "PRIVATE"
        self.assertEqual(self.call("prepare", selection, self.album).state, "choice_invalid")
        self.assertIsNone(self.raw())
        for groups in (
            ("contains space",),
            ("z", "a"),
            ("a", "a"),
            tuple(str(i) for i in range(61)),
        ):
            self.assertEqual(self.prepare(groups).state, "choice_invalid")

    def test_photo_capacity_counts_completed_entries_and_unfinished_reservations(self):
        self.completed()
        self.call("retire", "consumed")
        metadata = json.loads(self.lua.globals().photoProperties.publishedPhotoCorrelations)
        entry = metadata["entries"][0]
        metadata["entries"] = []
        for index in range(255):
            row = copy.deepcopy(entry)
            row["publishedCollectionLocalId"] = index + 100
            metadata["entries"].append(row)
        self.lua.globals().photoProperties.publishedPhotoCorrelations = json.dumps(metadata)
        self.lua.globals().remoteId = None
        self.scope.publishedCollectionLocalId = 5000
        self.assertEqual(self.prepare().state, "prepared")
        self.scope.publishedCollectionLocalId = 5001
        before = self.raw()
        self.assertEqual(self.prepare().state, "storage_full")
        self.assertEqual(self.raw(), before)
        # Reservation survives checkpoint growth and is available for retirement.
        self.scope.publishedCollectionLocalId = 5000
        self.authorize()
        self.dispatch()
        self.result()
        self.catalog_ack()
        self.proof()
        self.album_ack()
        self.assertEqual(self.call("retire", "consumed").state, "retired")
        metadata = json.loads(self.lua.globals().photoProperties.publishedPhotoCorrelations)
        self.assertEqual(len(metadata["entries"]), 256)
        self.assertEqual(metadata["metadataRevision"], 2)

    def test_maximal_complete_record_and_correlation_fit_reserved_sizes(self):
        self.completed(tuple(f"{index:03d}" + "g" * 125 for index in range(60)))
        d = self.document()
        r = d["attempts"][0]
        for key in ("fgaPublishServiceId", "fgaUploadAuthorizationId", "flickrPhotoId"):
            r[key] = "x" * 128
        r["publishServiceLocalId"] = r["publishedCollectionLocalId"] = 9007199254740991
        r["selectionRevision"] = 9007199254740991
        r["attemptNumber"] = r["recordRevision"] = 9007199254740990
        r["predecessorAttemptNumber"] = 9007199254740989
        d["nextAttemptNumber"] = 9007199254740991
        d["storeRevision"] = 9007199254740990
        r["attentionCode"] = "checkpoint_needs_attention"
        r["recoveryDisposition"] = "known_photo_reconciliation"
        r["recoveryConfirmedAt"] = "9999-12-31T23:59:59.12345678901Z"
        r["resultKind"] = "photographer_assertion"
        for key in ("createdAt", "updatedAt", "dispatchMarkedAt"):
            r[key] = "9999-12-31T23:59:59.12345678901Z"
        for value in (
            r["photoProof"],
            r["catalogPublication"],
            r["albumObligation"],
            r["groupHandoff"],
        ):
            value["acknowledgedAt"] = "9999-12-31T23:59:59.12345678901Z"
            for key in value:
                if key.endswith("Id"):
                    value[key] = "x" * 128
                elif key.endswith("Revision"):
                    value[key] = 9007199254740991
        self.scope.fgaPublishServiceId = "x" * 128
        self.scope.publishServiceLocalId = self.scope.publishedCollectionLocalId = 9007199254740991
        self.lua.globals().remoteId = "x" * 128
        self.put(d)
        self.assertEqual(self.inspect().state, "ready")
        full_bytes = len(self.codec.encode(self.inspect().record).encode())
        self.measured_full_bytes = full_bytes
        self.assertLess(full_bytes, self.module.MAX_RECORD_BYTES)
        self.assertEqual(self.call("retire", "consumed").state, "retired")
        metadata = json.loads(self.lua.globals().photoProperties.publishedPhotoCorrelations)
        entry_bytes = len(json.dumps(metadata["entries"][0]).encode())
        self.measured_entry_bytes = entry_bytes
        self.assertLess(entry_bytes, self.module.MAX_ENTRY_BYTES)
        self.assertLess(256 * full_bytes + 4096, self.module.MAX_STORE_BYTES)
        self.assertLess(256 * entry_bytes + 4096, self.module.MAX_PHOTO_BYTES)

    def test_property_size_ceilings_and_foreign_photo_object_refuse(self):
        fence = self.fence()
        self.lua.globals().properties.uploadAttemptRecoveryStore = " " * (
            self.module.MAX_STORE_BYTES + 1
        )
        self.assertEqual(self.inspect().state, "stored_invalid")
        self.assertEqual(
            self.call("prepare", self.selection(), self.album, fence=fence).state, "stored_invalid"
        )
        self.lua.globals().properties.uploadAttemptRecoveryStore = None
        self.lua.globals().photoProperties.publishedPhotoCorrelations = " " * (
            self.module.MAX_PHOTO_BYTES + 1
        )
        self.assertEqual(self.inspect().state, "photo_metadata_invalid")
        self.lua.globals().photoProperties.publishedPhotoCorrelations = None
        self.lua.globals().detachedPhoto = True
        self.assertEqual(self.inspect().state, "scope_invalid")

    def test_undefined_album_admission_state_is_not_invented(self):
        self.ready_result()
        self.catalog_ack()
        self.proof()
        album = self.table(
            {
                "fgaAlbumBindingId": "album-1",
                "fgaPhotoBindingId": "binding-1",
                "albumBindingRevision": 2,
                "flickrPhotosetId": self.null,
                "hostedObligationState": "materialization_pending",
                "fgaPublishServiceId": "service-1",
                "localCollectionIdentifier": "34",
                "linkedFlickrRevision": 6,
            }
        )
        before = self.raw()
        self.assertEqual(self.call("acknowledgeAlbum", album).state, "correlation_invalid")
        self.assertEqual(self.raw(), before)
        self.assertEqual(self.inspect().record.albumObligation.state, "pending")

    def test_admitted_record_without_required_result_checkpoint_is_corruption(self):
        self.ready_result()
        d = self.document()
        d["attempts"][0]["photoProof"] = None
        self.put(d)
        self.assertEqual(self.inspect().state, "stored_invalid")

    def test_recovery_new_copy_from_missing_and_older_history_remains_explicit(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                self.setUp()
                if not missing:
                    self.prepare()
                    self.authorize()
                self.call("enterRecovery")
                if missing:
                    self.call("recordMissingHistory")
                self.assertEqual(
                    self.call("successor", self.selection(), self.album, "unused", True).state,
                    "history_untrusted",
                )
                result = self.call("successor", self.selection(), self.album, "new_copy", True)
                self.assertEqual(result.state, "prepared")
                self.assertEqual(self.authorize().state, "authorized")
                self.assertEqual(
                    self.document()["attempts"][0]["uploadPhase"], "abandoned_possible_flickr_photo"
                )

    def test_first_unbound_album_scope_survives_upload_and_later_binding_acknowledgement(self):
        self.album = self.table({"fgaAlbumBindingId": self.null, "albumBindingRevision": self.null})
        self.ready_result()
        record = self.inspect().record
        stored = self.document()["attempts"][0]
        self.assertIsNone(stored["albumObligation"]["fgaAlbumBindingId"])
        self.assertIsNone(stored["albumObligation"]["albumBindingRevision"])
        self.assertEqual(record.publishedCollectionLocalId, 34)
        self.catalog_ack()
        self.proof()
        self.assertEqual(self.album_ack().state, "album_acknowledged")
        self.assertEqual(self.call("retire", "consumed").state, "retired")
        entry = json.loads(self.lua.globals().photoProperties.publishedPhotoCorrelations)[
            "entries"
        ][0]
        self.assertEqual(entry["fgaAlbumBindingId"], "album-1")
        self.assertEqual(entry["albumBindingRevision"], 2)

    def test_album_binding_revision_may_advance_after_render_without_replacing_identity(self):
        self.ready_result()
        self.catalog_ack()
        self.proof()
        ack = self.table(
            {
                "fgaAlbumBindingId": "album-1",
                "fgaPhotoBindingId": "binding-1",
                "albumBindingRevision": 3,
                "flickrPhotosetId": "photoset-1",
                "hostedObligationState": "membership_verified",
                "fgaPublishServiceId": "service-1",
                "localCollectionIdentifier": "34",
                "linkedFlickrRevision": 6,
            }
        )
        good = self.raw()
        for key, value in (
            ("fgaAlbumBindingId", "other-album"),
            ("fgaPhotoBindingId", "other-photo-binding"),
            ("albumBindingRevision", 1),
            ("fgaPublishServiceId", "other-service"),
            ("localCollectionIdentifier", "35"),
            ("localCollectionIdentifier", "034"),
            ("linkedFlickrRevision", 5),
        ):
            original = ack[key]
            ack[key] = value
            self.assertEqual(self.call("acknowledgeAlbum", ack).state, "correlation_invalid")
            self.assertEqual(self.raw(), good)
            ack[key] = original
        self.assertEqual(self.call("acknowledgeAlbum", ack).state, "album_acknowledged")
        self.assertEqual(self.inspect().record.albumObligation.albumBindingRevision, 3)

    def test_unbound_album_ack_still_requires_exact_service_collection_link_and_photo(self):
        self.album = self.table({"fgaAlbumBindingId": self.null, "albumBindingRevision": self.null})
        self.ready_result()
        self.catalog_ack()
        self.proof()
        ack = self.table(
            {
                "fgaAlbumBindingId": "album-1",
                "fgaPhotoBindingId": "binding-1",
                "albumBindingRevision": 3,
                "flickrPhotosetId": "photoset-1",
                "hostedObligationState": "membership_verified",
                "fgaPublishServiceId": "service-1",
                "localCollectionIdentifier": "34",
                "linkedFlickrRevision": 6,
            }
        )
        for key, value in (
            ("fgaPhotoBindingId", "other-photo-binding"),
            ("fgaPublishServiceId", "other-service"),
            ("localCollectionIdentifier", "35"),
            ("linkedFlickrRevision", 7),
        ):
            original = ack[key]
            ack[key] = value
            self.assertEqual(self.call("acknowledgeAlbum", ack).state, "correlation_invalid")
            ack[key] = original
        self.assertEqual(self.call("acknowledgeAlbum", ack).state, "album_acknowledged")

    def test_persisted_number_lexemes_are_exact_before_double_conversion(self):
        self.prepare()
        good = self.document()
        fence = self.fence()
        for token in (
            "1.00000000000000001",
            "9007199254740991.1",
            "9007199254740992",
            "1.00000000000000001e0",
            "90071992547409911e-1",
            "1e-999999999999999999999",
            "1e999999999999999999999",
            "-1",
            "0.99999999999999999",
        ):
            with self.subTest(token=token):
                d = copy.deepcopy(good)
                d["storeRevision"] = "NUMBER"
                raw = json.dumps(d).replace('"NUMBER"', token)
                self.lua.globals().properties.uploadAttemptRecoveryStore = raw
                self.assertEqual(self.inspect().state, "stored_invalid")
                self.assertEqual(self.call("authorize", "new", fence=fence).state, "stored_invalid")
                self.assertEqual(self.raw(), raw)
        self.store = self.module.new(self.lua.globals().options)
        for token, expected in (
            ("1.00000000000000000", 1),
            ("1e0", 1),
            ("100e-2", 1),
            ("9.007199254740991e15", 9007199254740991),
            ("900719925474099100e-2", 9007199254740991),
        ):
            with self.subTest(valid_token=token):
                d = copy.deepcopy(good)
                d["storeRevision"] = "NUMBER"
                self.lua.globals().properties.uploadAttemptRecoveryStore = json.dumps(d).replace(
                    '"NUMBER"', token
                )
                result = self.inspect()
                self.assertEqual(result.state, "ready")
                self.assertEqual(result.fence.storeRevision, expected)

    def test_nested_and_photo_metadata_number_rounding_is_also_refused(self):
        self.completed()
        d = self.document()
        d["attempts"][0]["photoProof"]["verificationRevision"] = "NUMBER"
        self.lua.globals().properties.uploadAttemptRecoveryStore = json.dumps(d).replace(
            '"NUMBER"', "7.00000000000000001"
        )
        self.assertEqual(self.inspect().state, "stored_invalid")
        self.setUp()
        self.completed()
        self.call("retire", "consumed")
        raw = self.lua.globals().photoProperties.publishedPhotoCorrelations
        metadata = json.loads(raw)
        metadata["metadataRevision"] = "NUMBER"
        self.lua.globals().photoProperties.publishedPhotoCorrelations = json.dumps(
            metadata
        ).replace('"NUMBER"', "1.00000000000000001")
        self.assertEqual(self.inspect().state, "photo_metadata_invalid")

    def test_unbound_and_advanced_album_acknowledgement_write_failures_preserve_pending(self):
        for unbound in (True, False):
            with self.subTest(unbound=unbound):
                self.setUp()
                if unbound:
                    self.album = self.table(
                        {"fgaAlbumBindingId": self.null, "albumBindingRevision": self.null}
                    )
                self.ready_result()
                self.catalog_ack()
                self.proof()
                ack = self.table(
                    {
                        "fgaAlbumBindingId": "album-1",
                        "fgaPhotoBindingId": "binding-1",
                        "albumBindingRevision": 3,
                        "flickrPhotosetId": "photoset-1",
                        "hostedObligationState": "membership_verified",
                        "fgaPublishServiceId": "service-1",
                        "localCollectionIdentifier": "34",
                        "linkedFlickrRevision": 6,
                    }
                )
                before = self.raw()
                self.lua.globals().failAt = "catalog"
                self.assertEqual(self.call("acknowledgeAlbum", ack).state, "storage_unavailable")
                self.assertEqual(self.raw(), before)
                self.lua.globals().failAt = None
                self.assertEqual(self.call("acknowledgeAlbum", ack).state, "album_acknowledged")


if __name__ == "__main__":
    unittest.main()
