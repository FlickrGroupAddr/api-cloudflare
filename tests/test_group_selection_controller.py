"""Actual Lua 5.1 controller and existing batch client, synthetic durable boundary."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().C = self.lua.execute(
            (BUNDLE / "GroupSelectionController.lua").read_text(encoding="utf-8")
        )
        self.lua.globals().client = self.lua.execute(
            (ROOT / "clients/lightroom/GroupSubmissionClient.lua").read_text(encoding="utf-8")
        )
        self.lua.execute("""
            null={}; calls=0; saves=0; confirms=0; proofs=0; newer=false; clock=0
            binding={fgaPhotoBindingId='b1',flickrPhotoId='p1',verificationRevision=1,
                linkedFlickrRevision=2,sourceKind='existing_public_flickr_photo'}
            response={schemaVersion=2,fgaPhotoBindingId='b1',flickrPhotoId='p1',submissions={
                {fgaSubmissionIntentId='i1',flickrGroupId='g1',state='queued',created=true,
                    permanentSubmissionBlock=null}}}
            store={
                readChoice=function() return {state='ready'} end,
                saveChoice=function(_,scope,groups,revision,id,b)
                    saves=saves+1; assert(revision==0); persisted=groups
                    return {state='saved',selection={selectionRevision=1},
                        handoff=id and {outboxRevision=1,binding=b} or nil}
                end,
                confirm=function(_,scope,id,rev,ack)
                    confirms=confirms+1; assert(ack.selectionRevision==1)
                    assert(ack.binding.fgaPhotoBindingId=='b1')
                    return {state='confirmed',selectionConsumed=not newer}
                end}
            deps={store=store,call=pcall,now=function() return clock end,
                prove=function() proofs=proofs+1
                binding.verificationRevision=3
                return binding end,
                credential=function() return string.rep('0000-',12)..'0000' end,
                newHandoffId=function() return 'handoff1' end,client=client,jsonNull=null,
                encode=function(value) assert(value.photoBinding.expectedVerificationRevision==3)
                return 'body' end,
                decode=function() return response end,
                post=function(path,body,headers)
                    assert(saves==1 and #persisted==1); calls=calls+1
                    return 'response',{status=202}
                end}
            eligibility={state='ready',bound=true,fgaPhotoBindingId='b1',flickrPhotoId='p1',
                eligibleGroups={{flickrGroupId='g1',displayName='Group 1'}}}
            function controller()
                local c=C.new(deps,{},eligibility,binding); C.toggle(c.model,'g1',true); return c
            end
        """)

    def test_durable_before_one_request_and_fresh_proof(self):
        self.lua.execute("""
            local c=controller(); assert(c:commit().state=='accepted')
            assert(proofs==1 and calls==1 and confirms==1 and not c.model.ready)
        """)

    def test_public_workflow_reproves_reused_upload_origin_binding(self):
        self.lua.execute("""
            binding.sourceKind='fga_direct_upload'
            local c=C.new(deps,{},eligibility,binding,{workflow='existing_public_photo'})
            C.toggle(c.model,'g1',true)
            assert(c:commit().state=='accepted' and proofs==1 and calls==1)
            assert(binding.sourceKind=='fga_direct_upload')
        """)

    def test_original_publisher_bound_path_does_not_gain_public_proof(self):
        self.lua.execute("""
            binding.sourceKind='fga_direct_upload'
            deps.encode=function(request)
                assert(request.photoBinding.expectedVerificationRevision==1); return 'body'
            end
            local c=C.new(deps,{},eligibility,binding,{workflow='publisher_bound'})
            C.toggle(c.model,'g1',true)
            assert(c:commit().state=='accepted' and proofs==0 and calls==1)
        """)

    def test_bad_or_ambiguous_response_retains_snapshot(self):
        for mutation in (
            "response.fgaPhotoBindingId='foreign'",
            "response.flickrPhotoId='foreign'",
            "response.submissions[1].flickrGroupId='extra'",
            "response.submissions[1].state='unknown'",
            "response.submissions[1].permanentSubmissionBlock={reasonCode='delivery_uncertain',createdAt='2026-10-16T00:00:00Z'}",
            "response.submissions={}",
            "deps.decode=function() error('private error') end",
            "deps.post=function() calls=calls+1; return nil end",
            "deps.post=function() calls=calls+1; error('private error') end",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute(
                    mutation
                    + """
                    local result=controller():commit()
                    assert(result.state=='unresolved' and result.reason==nil)
                    assert(saves==1 and confirms==0 and calls==1)
                """
                )

    def test_late_response_does_not_consume_newer_choice(self):
        self.lua.execute("""
            deps.post=function() newer=true; return 'body',{status=202} end
            local result=controller():commit()
            assert(result.state=='accepted' and not result.selectionConsumed)
        """)

    def test_empty_unpublished_and_whole_limit_refusal(self):
        self.lua.execute("""
            eligibility.bound=false
            local c=C.new(deps,{},eligibility)
            assert(c:commit().state=='saved' and saves==1 and calls==0 and proofs==0)
            eligibility.bound=true
            local c=controller()
            for i=2,61 do c.model.groups[i]={id='g'..i,name='group'}
            c.model.selected['g'..i]=true end
            assert(c:commit().state=='refused' and calls==0 and saves==1)
        """)

    def test_slow_durable_write_expires_proof_before_post(self):
        self.lua.execute("""
            local save=store.saveChoice
            store.saveChoice=function(...) clock=15; return save(...) end
            assert(controller():commit().reason=='proof_expired')
            assert(saves==1 and calls==0 and confirms==0)
        """)

    def test_unavailable_saved_choices_require_explicit_local_clear(self):
        self.lua.execute("""
            store.readChoice=function() return {state='ready',selection={selectionRevision=4,
                flickrGroupIds={'g1','protected','no-longer-writable'}}} end
            local c=controller()
            assert(not C.canConfirm(c.model) and C.count(c.model)==3)
            assert(#C.unavailableChoices(c.model)==2)
            assert(C.clearUnavailableChoices(c.model))
            assert(C.count(c.model)==1 and C.canConfirm(c.model))
            assert(c.model.selected.g1 and not c.model.selected.protected)
            assert(not C.toggle(c.model,'protected',true) and saves==0 and calls==0)
        """)

    def test_nonfinite_and_backward_proof_clocks_send_nothing(self):
        for start, end in (
            ("0/0", "0"),
            ("math.huge", "math.huge"),
            ("0", "0/0"),
            ("0", "math.huge"),
            ("3", "2"),
        ):
            with self.subTest(start=start, end=end):
                self.setUp()
                self.lua.execute(f"""
                    local reads=0
                    deps.now=function() reads=reads+1; if reads==1 then return {start} end
                        return {end} end
                    local result=controller():commit()
                    assert(result.state=='proof_required' or result.state=='unresolved')
                    assert(calls==0 and confirms==0)
                """)

    def test_sixty_groups_use_one_complete_request(self):
        self.lua.execute("""
            local c=controller()
            for i=2,60 do c.model.groups[i]={id='g'..i,name='Group'}
            c.model.selected['g'..i]=true end
            deps.encode=function(request)
                assert(#request.flickrGroupIds==60)
                response.submissions={}
                for i,id in ipairs(request.flickrGroupIds) do
                    response.submissions[i]={fgaSubmissionIntentId='i'..i,flickrGroupId=id,
                        state='queued',created=true,permanentSubmissionBlock=null}
                end
                return 'body'
            end
            deps.post=function() assert(#persisted==60)
            calls=calls+1
            return 'body',{status=202} end
            assert(c:commit().state=='accepted' and calls==1 and confirms==1)
        """)

    def test_duplicate_intents_reordered_pairs_and_unknown_keys_refused(self):
        self.lua.execute("""
            local groups={'g1','g2'}
            local a=response.submissions[1]
            response.submissions[2]={fgaSubmissionIntentId='i1',flickrGroupId='g2',state='queued',
                created=true,permanentSubmissionBlock=null}
            assert(not C.validate202(response,binding,groups,null))
            response.submissions[2].fgaSubmissionIntentId='i2'
            assert(C.validate202(response,binding,groups,null))
            a.extra=true; assert(not C.validate202(response,binding,groups,null)); a.extra=nil
            response.submissions[1],response.submissions[2]=response.submissions[2],response.submissions[1]
            assert(not C.validate202(response,binding,groups,null))
        """)


if __name__ == "__main__":
    unittest.main()
