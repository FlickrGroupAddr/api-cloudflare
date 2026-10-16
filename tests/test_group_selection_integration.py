"""Cross-module handoff with actual Lua 5.1 cores and synthetic SDK/HTTP."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

from tests.test_group_selection_store import HARNESS

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().json = self.lua.execute((BUNDLE / "dkjson.lua").read_text("utf-8"))
        self.lua.execute("package.preload.dkjson=function() return json end")
        self.lua.execute(HARNESS)
        for name in (
            "GroupSelectionStore",
            "GroupSelectionEligibility",
            "GroupSelectionController",
        ):
            self.lua.globals()[name] = self.lua.execute(
                (BUNDLE / (name + ".lua")).read_text("utf-8")
            )
        self.lua.globals().batchClient = self.lua.execute(
            (ROOT / "clients/lightroom/GroupSubmissionClient.lua").read_text("utf-8")
        )
        self.lua.execute("""
            store=GroupSelectionStore.new(options)
            scope={publishServiceLocalId=12,publishedCollectionLocalId=34,photoUuid=photoUuid}
            groups={state='complete',snapshotStatus='fresh',snapshotRevision=1,
                refreshedAt='2026-10-16T12:00:00Z',groups={
                {flickrGroupId='g1',displayName='Group 1'},
                {flickrGroupId='g2',displayName='Group 2'},
                {flickrGroupId='g3',displayName='Group 3'}}}
            eligibility=assert(GroupSelectionEligibility.assemble(groups))
            binding={fgaPhotoBindingId='binding1',flickrPhotoId='photo1',
                verificationRevision=1,linkedFlickrRevision=1,
                sourceKind='existing_public_flickr_photo'}
            posts,proofs=0,0
            deps={store=store,client=batchClient,call=pcall,jsonNull=json.null,
                now=function() return 0 end,newHandoffId=function() return 'handoff1' end,
                credential=function() return string.rep('0000-',12)..'0000' end,
                encode=json.encode,decode=function(body) return json.decode(body,1,json.null) end,
                prove=function()
                    proofs=proofs+1; binding.verificationRevision=2; return binding
                end,
                post=function(_,body)
                    posts=posts+1
                    local outbox=json.decode(catalogProperties.groupAdditionOutboxV1,1,json.null)
                    assert(outbox.records[1].state=='prepared','snapshot before HTTP')
                    local request=json.decode(body,1,json.null)
                    assert(request.photoBinding.expectedVerificationRevision==2)
                    if concurrentEdit then
                        assert(store:saveChoice(scope,{'g3'},1).state=='saved')
                    end
                    if malformed then return '{}',{status=202} end
                    local submissions={}
                    for i,id in ipairs(request.flickrGroupIds) do
                        submissions[i]={fgaSubmissionIntentId='intent'..i,flickrGroupId=id,
                            state='queued',created=true,permanentSubmissionBlock=json.null}
                    end
                    return json.encode({schemaVersion=2,fgaPhotoBindingId='binding1',
                        flickrPhotoId='photo1',submissions=submissions}),{status=202}
                end}
            function boundController()
                eligibility.bound=true; eligibility.fgaPhotoBindingId='binding1'
                eligibility.flickrPhotoId='photo1'
                local c=GroupSelectionController.new(deps,scope,eligibility,binding,
                    {workflow='existing_public_photo'})
                GroupSelectionController.toggle(c.model,'g2',true)
                GroupSelectionController.toggle(c.model,'g1',true)
                return c
            end
        """)

    def test_actual_store_confirmed_batch_and_retained_intent_identities(self):
        self.lua.execute("""
            local result=boundController():commit()
            assert(result.state=='accepted' and result.count==2 and result.selectionConsumed)
            assert(posts==1 and proofs==1 and not store:readChoice(scope).selection)
            local doc=json.decode(catalogProperties.groupAdditionOutboxV1,1,json.null)
            assert(doc.records[1].state=='acknowledged' and #doc.records[1].submissions==2)
            assert(doc.records[1].submissions[1].flickrGroupId=='g1')
        """)

    def test_late_ack_preserves_newer_edit_with_real_store(self):
        self.lua.execute("""
            concurrentEdit=true
            local result=boundController():commit()
            assert(result.state=='accepted' and not result.selectionConsumed)
            local choice=store:readChoice(scope).selection
            assert(choice.selectionRevision==2 and choice.flickrGroupIds[1]=='g3')
        """)

    def test_malformed_ack_survives_new_store_instance_as_unresolved(self):
        self.lua.execute("""
            malformed=true
            assert(boundController():commit().state=='unresolved' and posts==1)
            store=GroupSelectionStore.new(options)
            assert(#store:readChoice(scope).selection.flickrGroupIds==2)
            local doc=json.decode(catalogProperties.groupAdditionOutboxV1,1,json.null)
            assert(doc.records[1].state=='prepared' and not doc.records[1].submissions)
        """)

    def test_empty_unpublished_choice_never_posts_or_creates_outbox(self):
        self.lua.execute("""
            local c=GroupSelectionController.new(deps,scope,eligibility)
            local result=c:commit()
            assert(result.state=='saved' and result.count==0 and posts==0 and proofs==0)
            assert(store:readChoice(scope).selection.choice=='none')
            assert(catalogProperties.groupAdditionOutboxV1==nil)
        """)
