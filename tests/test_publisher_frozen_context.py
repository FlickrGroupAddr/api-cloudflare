"""Exercise actual frozen publisher/selection/upload modules with synthetic SDK only."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class PublisherFrozenContextTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.globals().publisher = (ROOT / "clients/lightroom/publisher").as_posix()
        self.lua.execute('package.path=publisher.."/?.lua;"..bundle.."/?.lua;"..package.path')
        self.lua.execute((ROOT / "tests/publisher_frozen_context_fixture.lua").read_text("utf-8"))

    def test_absent_none_and_nonempty_reach_actual_upload_journal(self):
        for kind in ("absent", "none", "groups"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind != "absent":
                    self.lua.execute(
                        "assert(save(photo,"
                        + ("{'g2','g1'}" if kind == "groups" else "{}")
                        + ").state=='saved')"
                    )
                self.lua.globals().kind = kind
                self.lua.execute("""
                    local r=prepare(); assert(r.state=='prepared',r.state)
                    assert(r.snapshot.selectionState==kind)
                    local raw=catalogProperties.uploadAttemptRecoveryStore
                    local document=json.decode(raw,1,json.null)
                    local persisted=document.attempts[1]
                    assert(persisted.selectionKind==kind)
                    assert(#persisted.flickrGroupIds==(kind=='groups' and 2 or 0))
                    if kind=='absent' then assert(persisted.selectionRevision==json.null)
                    else assert(persisted.selectionRevision==1) end
                    assert(choice(photo)==nil or choice(photo).selectionRevision==1)
                """)

    def test_pre_render_choice_survives_later_edit_and_return_value_mutation(self):
        self.lua.execute("""
            assert(save(photo,{'g2','g1'}).state=='saved')
            local r=prepare(); assert(r.state=='prepared',r.state)
            r.snapshot.flickrGroupIds[1]='forged'; r.record.flickrGroupIds[1]='forged'
            assert(save(photo,{'g3'},1).state=='saved')
            local view=session:inspect(r.context,now)
            assert(view.state=='ready' or view.state=='prepared',view.state)
            assert(view.record.selectionRevision==1 and view.record.flickrGroupIds[1]=='g1')
            local raw=catalogProperties.uploadAttemptRecoveryStore
                    local document=json.decode(raw,1,json.null)
                    local persisted=document.attempts[1]
            assert(persisted.flickrGroupIds[1]=='g1' and persisted.selectionRevision==1)
            assert(choice(photo).selectionRevision==2 and choice(photo).flickrGroupIds[1]=='g3')
        """)

    def test_same_photo_in_multiple_scopes_keeps_independent_contexts(self):
        self.lua.execute("""
            assert(save(photo,{'g1'}).state=='saved')
            local a2=makeAlbum(35); photo.memberships[2]=a2
            assert(save(photo,{'g2'},0,a2).state=='saved')
            local first=prepare(); assert(first.state=='prepared',first.state)
            exportContext={publishService=service,publishedCollection=a2,
                publishedCollectionInfo={isDefaultCollection=false}}
            target.localCollectionIdentifier='35'; session=assert(start())
            local second=prepare(photo,'handoff-second')
            assert(second.state=='prepared',second.state)
            assert(first.record.publishedCollectionLocalId==34)
            assert(second.record.publishedCollectionLocalId==35)
            assert(first.record.flickrGroupIds[1]=='g1' and second.record.flickrGroupIds[1]=='g2')
            local s2={localIdentifier=13,type=service.type,getPluginId=service.getPluginId}
            local a3=makeAlbum(36,s2); photo.memberships[3]=a3
            assert(save(photo,{},0,a3,s2).state=='saved')
            exportContext={publishService=s2,publishedCollection=a3,
                publishedCollectionInfo={isDefaultCollection=false}}
            target.localCollectionIdentifier='36'; target.fgaPublishServiceId='service-2'
            session=assert(start()); local third=prepare(photo,'handoff-third')
            assert(third.state=='prepared',third.state)
            assert(third.record.publishServiceLocalId==13 and third.record.selectionKind=='none')
            assert(#json.decode(catalogProperties.uploadAttemptRecoveryStore,1,json.null).attempts==3)
        """)

    def test_bad_photo_does_not_poison_other_photo(self):
        self.lua.execute("""
            photo.properties.groupAdditionSelections='malformed'
            local bad=prepare(); assert(bad.state~='prepared' and bad.context==nil)
            local good=makePhoto('00000000-0000-0000-0000-000000000098')
            assert(save(good,{'good-group'}).state=='saved')
            local r=prepare(good,'good-handoff'); assert(r.state=='prepared',r.state)
            assert(r.record.flickrGroupIds[1]=='good-group')
            assert(photo.properties.groupAdditionSelections=='malformed')
            assert(#json.decode(catalogProperties.uploadAttemptRecoveryStore,1,json.null).attempts==1)
        """)

    def test_consumption_requires_persisted_publication_and_exact_validated_group_ack(self):
        self.lua.execute("""
            assert(save(photo,{'g1','g2'}).state=='saved')
            local r=prepare(); assert(r.state=='prepared',r.state)
            assert(session:confirmGroups(r.context,202,response(),now).state~='confirmed')
            assert(choice(photo).selectionRevision==1)
            publication(r)
            assert(session:bindGroups(r.context,now).state=='bound')
            assert(session:confirmGroups(r.context,202,response(),now).state~='confirmed')
            assert(groupCheckpoint(r,photo,{'g1','g2'}).state=='groups_acknowledged')
            local bad=response(); bad.submissions[2]=nil
            assert(session:confirmGroups(r.context,202,bad,now).state~='confirmed')
            assert(choice(photo).selectionRevision==1)
            local confirmed=session:confirmGroups(r.context,202,response(),now)
            assert(confirmed.state=='confirmed',confirmed.state)
            assert(confirmed.selectionConsumed and choice(photo)==nil)
        """)

    def test_confirmed_old_attempt_preserves_new_selection_revision(self):
        self.lua.execute("""
            assert(save(photo,{'g1','g2'}).state=='saved'); local r=prepare()
            publication(r); assert(session:bindGroups(r.context,now).state=='bound')
            assert(groupCheckpoint(r,photo,{'g1','g2'}).state=='groups_acknowledged')
            assert(save(photo,{},1).state=='saved')
            local confirmed=session:confirmGroups(r.context,202,response(),now)
            assert(confirmed.state=='confirmed' and not confirmed.selectionConsumed)
            assert(choice(photo).selectionRevision==2 and choice(photo).choice=='none')
        """)

    def test_zero_groups_require_both_stored_publication_obligations(self):
        self.lua.execute("""
            assert(save(photo,{}).state=='saved'); local r=prepare()
            assert(session:confirmPublication(r.context,now).state~='confirmed')
            assert(choice(photo).choice=='none')
            publication(r)
            local confirmed=session:confirmPublication(r.context,now)
            assert(confirmed.state=='confirmed' and confirmed.selectionConsumed)
            assert(choice(photo)==nil)
        """)

    def test_uncertain_or_failed_store_write_never_returns_context_capability(self):
        for mutation in (
            "gate='queued'",
            "failField='uploadAttemptRecoveryStore'",
            "afterGate=function() if catalogProperties.uploadAttemptRecoveryStore then "
            "catalogProperties.uploadAttemptRecoveryStore="
            "catalogProperties.uploadAttemptRecoveryStore..' ' end end",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("assert(save(photo,{'g1'}).state=='saved')")
                self.lua.execute(mutation)
                self.lua.execute("""
                    local r=prepare(); assert(r.state~='prepared' and r.context==nil,r.state)
                    gate='executed'; assert(choice(photo).selectionRevision==1)
                """)

    def test_identity_change_inside_consumption_gate_preserves_selection(self):
        for changed in (
            "target.linkedFlickrRevision=7",
            "target.fgaPublishServiceId='changed'",
            "owner=false",
        ):
            with self.subTest(changed=changed):
                self.setUp()
                self.lua.execute("""
                    assert(save(photo,{}).state=='saved'); r=prepare(); publication(r)
                    prior=photo.properties.groupAdditionSelections
                    priorOutbox=catalogProperties.groupAdditionOutboxV1
                    local base=gateCount
                    beforeGate=function(count)
                        -- First gate reads the upload checkpoint, second consumes #0065.
                        if count==base+2 then mutateIdentity() end
                    end
                """)
                self.lua.execute("function mutateIdentity() " + changed + " end")
                self.lua.execute("""
                    assert(session:confirmPublication(r.context,now).state~='confirmed')
                    assert(photo.properties.groupAdditionSelections==prior)
                    assert(catalogProperties.groupAdditionOutboxV1==priorOutbox)
                """)

    def test_failed_photo_admission_and_delayed_callback_leave_other_photo_independent(self):
        self.lua.execute("""
            assert(save(photo,{'g1'}).state=='saved')
            failField='uploadAttemptRecoveryStore'
            local failed=prepare(); assert(failed.context==nil and failed.state~='prepared')
            failField=nil
            local good=makePhoto('00000000-0000-0000-0000-000000000098')
            local r=prepare(good,'other-photo'); assert(r.state=='prepared',r.state)
            assert(choice(photo).selectionRevision==1)
            local stored=json.decode(catalogProperties.uploadAttemptRecoveryStore)
            assert(#stored.attempts==1 and stored.attempts[1].photoUuid==good.uuid)
        """)
        self.setUp()
        self.lua.execute("""
            assert(save(photo,{}).state=='saved'); gate='queued'
            local r=prepare(); assert(r.context==nil and r.state~='prepared')
            local before=writes; gate='executed'; assert(not pcall(delayed))
            assert(writes==before and catalogProperties.uploadAttemptRecoveryStore==nil)
            assert(choice(photo).selectionRevision==1)
        """)

    def test_catalog_activation_owner_and_target_change_cannot_consume(self):
        for mutation in (
            "activeCatalog={}",
            "activation={}",
            "owner=false",
            "target.fgaPublishServiceId='different-service'",
            "target.linkedFlickrRevision=7",
            "target.localCollectionIdentifier='35'",
            "photo.uuid='00000000-0000-0000-0000-000000000099'",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("""
                    assert(save(photo,{}).state=='saved'); r=prepare(); publication(r)
                    prior=photo.properties.groupAdditionSelections
                    priorOutbox=catalogProperties.groupAdditionOutboxV1
                """)
                self.lua.execute(mutation)
                self.lua.execute("""
                    assert(session:confirmPublication(r.context,now).state~='confirmed')
                    assert(photo.properties.groupAdditionSelections==prior)
                    assert(catalogProperties.groupAdditionOutboxV1==priorOutbox)
                """)


if __name__ == "__main__":
    unittest.main()
