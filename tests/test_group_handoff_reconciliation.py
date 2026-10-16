"""Explicit immutable recovery using actual Lua5.1 stores and batch protocol."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.execute(
            (ROOT / "tests/group_handoff_reconciliation_fixture.lua").read_text("utf-8")
        )

    def check(self, code):
        self.lua.execute(code)

    def test_open_lists_original_ids_without_proof_or_dispatch(self):
        self.check("""
            local result=recovery:list(scope)
            assert(result.state=='ready' and result.pendingHandoffIds[1]=='handoff-1')
            assert(posts==0 and proofs==0); preserved()
            assert(R.PRODUCTION_QUALIFIED==false)
        """)

    def test_lost_committed_response_reconciles_same_pairs_without_new_work(self):
        self.check("""
            loseResponse=true
            assert(run().state=='unresolved'); preserved()
            assert(hints==2 and orders==2 and attempts==2)
            recovery=assert(R.new(deps))
            assert(recovery:list(scope).pendingHandoffIds[1]=='handoff-1' and posts==1)
            loseResponse=false
            local result=run()
            assert(result.state=='accepted' and result.selectionConsumed)
            assert(hints==2 and orders==2 and attempts==2 and posts==2)
            local h=pending()
            assert(h.state=='acknowledged' and h.outboxRevision==2)
            assert(h.binding.verificationRevision==3)
            assert(h.submissions[1].fgaSubmissionIntentId=='intent-1')
            assert(h.submissions[2].fgaSubmissionIntentId=='intent-2')
            assert(not h.submissions[1].created and not h.submissions[2].created)
            assert(requests[1].photoBinding.expectedVerificationRevision==4)
            assert(requests[2].photoBinding.expectedVerificationRevision==5)
            assert(run().state=='unresolved' and posts==2)
        """)

    def test_proof_failure_or_changed_binding_authority_preserves_original(self):
        for injection in (
            "proofFailure='photo_owner_mismatch'",
            "proofFailure='existing_photo_not_public'",
            "proofFailure='flickr_link_changed'",
            "freshOverride={}",
            "proofHook=function() identity.linkedFlickrRevision=3 end",
            "proofHook=function() identity.installationId='other' end",
            "proofHook=function() candidate='rotation' end",
            "proofHook=function() activeCatalog={} end",
            "proofHook=function() cancelledFlag=true end",
        ):
            with self.subTest(injection=injection):
                self.setUp()
                self.check(injection + "; assert(run().state=='unresolved' and posts==0)")
                self.check("""
                    local document=require('dkjson').decode(properties.existingPhotoGroupOutboxV1)
                    local h=document.records[1]
                    assert(h.state=='prepared' and h.binding.verificationRevision==3)
                """)

    def test_stale_backward_and_nonfinite_observed_proof_refuse_dispatch(self):
        for value in ("15", "-1", "math.huge", "0/0"):
            with self.subTest(value=value):
                self.setUp()
                self.check(f"proofClock={value}; assert(run().state=='unresolved' and posts==0)")
                self.check("preserved()")

    def test_context_fences_before_list_dispatch_and_after_response(self):
        for injection in (
            "candidate='rotation'",
            "changedCredential=string.rep('0000-',12)..'0010'",
            "identity.installationId='other'",
            "identity.linkedFlickrRevision=3",
            "activeCatalog={}",
            "cancelledFlag=true",
        ):
            with self.subTest(injection=injection):
                self.setUp()
                self.check(injection + "; assert(recovery:list(scope).state=='unresolved')")
                self.check("assert(posts==0)")
                self.setUp()
                self.check("batchHook=function() " + injection + " end")
                self.check("assert(run().state=='unresolved')")
                self.check("""
                    local document=require('dkjson').decode(properties.existingPhotoGroupOutboxV1)
                    assert(document.records[1].state=='prepared')
                """)

    def test_proof_identity_and_provenance_cannot_change(self):
        for mutation in (
            "v.fgaPhotoBindingId='other'",
            "v.flickrPhotoId='other'",
            "v.linkedFlickrRevision=3",
            "v.sourceKind='existing_public_flickr_photo'",
            "v.verificationRevision=0",
            "v.extra=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.check(
                    "local prove=deps.prove; deps.prove=function(...) local v=prove(...); "
                    + mutation
                    + "; return v end"
                )
                self.check("assert(run().state=='unresolved' and posts==0); preserved()")

    def test_dispatch_fence_covers_encoding_and_observed_clock(self):
        for mutation in (
            "clock=15",
            "candidate='rotation'",
            "activeCatalog={}; deps.catalog=activeCatalog",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.check(
                    "local encode=deps.encode; deps.encode=function(v) "
                    + mutation
                    + "; return encode(v) end"
                )
                self.check("assert(run().state=='unresolved' and posts==0)")

    def test_same_controller_coalesces_explicit_actions_while_yielding(self):
        self.check("""
            proofHook=function()
                assert(run().state=='busy' and recovery:list(scope).state=='busy')
            end
            assert(run().state=='accepted' and posts==1 and proofs==1)
        """)

    def test_whole_response_validation_before_any_confirmation(self):
        for injection in (
            "responseStatus=200",
            "malformedBytes='{'",
            "mutateResponse=function(v) v.extra=true end",
            "mutateResponse=function(v) v.flickrPhotoId='other' end",
            "mutateResponse=function(v) table.remove(v.submissions) end",
            "mutateResponse=function(v) v.submissions[2].fgaSubmissionIntentId='intent-1' end",
            "mutateResponse=function(v) v.submissions[2].flickrGroupId='other' end",
            "mutateResponse=function(v) v.submissions[2].created='false' end",
            "mutateResponse=function(v) v.submissions[2].permanentSubmissionBlock={} end",
        ):
            with self.subTest(injection=injection):
                self.setUp()
                self.check(injection + "; assert(run().state=='unresolved'); preserved()")

    def test_newer_edit_survives_old_receipt(self):
        self.check("""
            batchHook=function() assert(seed('handoff-2',1,{'group-3'}).state=='saved') end
            local result=run()
            assert(result.state=='accepted' and result.selectionConsumed==false)
            local selected=store:readChoice(scope).selection
            assert(selected.selectionRevision==2 and selected.flickrGroupIds[1]=='group-3')
            assert(store:listPending(scope).handoffs[1].handoffId=='handoff-2')
        """)

    def test_corrupt_absent_and_wrong_scope_never_infer_remote_absence(self):
        for injection in (
            "properties.existingPhotoGroupOutboxV1='{'",
            "properties.existingPhotoGroupOutboxV1=nil",
            "scope.flickrPhotoId='other'",
            "scope.installationId='other'",
        ):
            with self.subTest(injection=injection):
                self.setUp()
                self.check(injection + "; assert(run().state=='unresolved')")
                self.check("assert(posts==0 and proofs==0)")

    def test_full_real_outbox_can_reconcile_without_allocating_replacement(self):
        self.check("""
            for i=2,128 do assert(seed(string.format('handoff-%03d',i),i-1).state=='saved') end
            assert(seed('overflow',128).state=='storage_full')
            local result=run()
            assert(result.state=='accepted' and not result.selectionConsumed)
            local records=require('dkjson').decode(properties.existingPhotoGroupOutboxV1).records
            assert(#records==128 and posts==1)
        """)

    def test_permanent_block_is_retained_and_never_resubmitted(self):
        self.check("""
            remote['group-1']={fgaSubmissionIntentId='old-intent',flickrGroupId='group-1',
                state='delivery_uncertain',permanentSubmissionBlock={reasonCode='delivery_uncertain',
                    createdAt='2026-10-16T12:00:00.000000Z'}}
            assert(run().state=='accepted')
            assert(hints==1 and orders==1 and attempts==1)
            local row=pending().submissions[1]
            assert(not row.created)
            assert(row.permanentSubmissionBlock.reasonCode=='delivery_uncertain')
        """)

    def test_batch_rejection_or_confirmation_ambiguity_retains_record(self):
        for injection in (
            "rejectBatch=true",
            "store.confirm=function() return {state='write_unconfirmed'} end",
        ):
            with self.subTest(injection=injection):
                self.setUp()
                self.check(injection + "; assert(run().state=='unresolved'); preserved()")

    def test_publisher_store_reconciles_literal_original_request_and_preserves_new_edit(self):
        self.check("""
            usePublisherStore()
            local requests={}
            local realPost=deps.post
            deps.post=function(path,bytes,headers)
                requests[#requests+1]=bytes
                return realPost(path,bytes,headers)
            end
            loseResponse=true
            assert(run().state=='unresolved' and proofs==0)
            assert(store:saveChoice(scope,{'group-3'},1).state=='saved')
            loseResponse=false
            local result=run()
            assert(result.state=='accepted' and not result.selectionConsumed)
            assert(proofs==0 and posts==2 and hints==2 and orders==2 and attempts==2)
            assert(requests[1]==requests[2])
            assert(store:readChoice(scope).selection.flickrGroupIds[1]=='group-3')
        """)

    def test_confirm_gate_wait_session_changes_cannot_acknowledge_or_consume(self):
        for publisher in (False, True):
            for mutation in (
                "cancelledFlag=true",
                "candidate='rotation'",
                "changedCredential=string.rep('0000-',12)..'0010'",
                "activeCatalog={}",
                "identity.installationId='other'",
                "identity.linkedFlickrRevision=3",
            ):
                with self.subTest(publisher=publisher, mutation=mutation):
                    self.setUp()
                    if publisher:
                        self.check("usePublisherStore()")
                    self.check("""
                        local key=deps.workflow=='publisher_bound' and 'groupAdditionOutboxV1'
                            or 'existingPhotoGroupOutboxV1'
                        originalOutbox=properties[key]
                        originalSelection=properties.groupAdditionSelections
                    """)
                    self.check(
                        "batchHook=function() beforeGate=function() " + mutation + " end end"
                    )
                    self.check("""
                        assert(run().state=='unresolved' and posts==1)
                        local key=deps.workflow=='publisher_bound' and 'groupAdditionOutboxV1'
                            or 'existingPhotoGroupOutboxV1'
                        assert(properties[key]==originalOutbox)
                        assert(properties.groupAdditionSelections==originalSelection)
                        local h=require('dkjson').decode(properties[key]).records[1]
                        assert(h.state=='prepared' and h.outboxRevision==1)
                    """)

    def test_operation_guard_requires_literal_true_and_runs_in_commit_callback(self):
        for publisher in (False, True):
            with self.subTest(publisher=publisher):
                self.setUp()
                if publisher:
                    self.check("usePublisherStore()")
                self.check("""
                    local originalConfirm=store.confirm
                    guardInside=0
                    store.confirm=function(self,scope,id,revision,ack,guard)
                        assert(type(guard)=='function')
                        return originalConfirm(self,scope,id,revision,ack,function()
                            if insideGate then guardInside=guardInside+1 end
                            return guard()
                        end)
                    end
                    assert(run().state=='accepted' and guardInside>=2)
                """)
                self.setUp()
                if publisher:
                    self.check("usePublisherStore()")
                self.check("""
                    local originalConfirm=store.confirm
                    store.confirm=function(self,scope,id,revision,ack,guard)
                        local truthy=function() return 'true' end
                        return originalConfirm(self,scope,id,revision,ack,truthy)
                    end
                    assert(run().state=='unresolved')
                    local key=deps.workflow=='publisher_bound' and 'groupAdditionOutboxV1'
                        or 'existingPhotoGroupOutboxV1'
                    assert(require('dkjson').decode(properties[key]).records[1].state=='prepared')
                """)


if __name__ == "__main__":
    unittest.main()
