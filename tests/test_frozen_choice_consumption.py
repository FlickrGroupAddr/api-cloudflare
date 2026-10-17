"""Actual Lua5.1 frozen choices with synthetic SDK persistence boundaries only."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class FrozenChoiceConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.execute((ROOT / "tests/frozen_choice_consumption_fixture.lua").read_text("utf-8"))

    def test_absent_and_explicit_none_have_distinct_frozen_revisions(self):
        self.lua.execute("""
            local absent=freeze()
            assert(absent.choice.selectionState=='absent' and absent.choice.choice=='none')
            assert(absent.choice.selectionRevision==0 and #absent.choice.flickrGroupIds==0)
            assert(choice()==nil)
            local confirmed=session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true})
            assert(confirmed.state=='confirmed' and not confirmed.selectionConsumed)
            assert(confirmed.groupAcceptanceRecorded==false)
            assert(save({}).state=='saved')
            local explicit=freeze('explicit-none')
            assert(explicit.choice.selectionState=='none' and explicit.choice.selectionRevision==1)
            confirmed=session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true})
            assert(confirmed.state=='confirmed' and confirmed.selectionConsumed and choice()==nil)
            local row=store:readHandoff(scope,'explicit-none').handoff
            assert(row.state=='acknowledged' and row.submissions==nil)
        """)

    def test_snapshot_and_binding_are_private_detached_copies(self):
        self.lua.execute("""
            assert(save({'g2','g1'}).state=='saved')
            local frozen=freeze()
            frozen.choice.scope.photoUuid='other'; frozen.choice.selectionRevision=999
            frozen.choice.flickrGroupIds[1]='forged'; frozen.choice.handoffId='other'
            handle.record={}; handle.flickrGroupIds={'forged'}
            local view=session:inspect(handle).choice
            assert(view.scope.photoUuid==photoUuid and view.selectionRevision==1)
            assert(view.flickrGroupIds[1]=='g1' and view.handoffId=='handoff-65')
            assert(session:bindGroups(handle,binding).state=='bound')
            binding.flickrPhotoId='forged'; binding.verificationRevision=99
            assert(session:bindGroups(handle,binding).state=='snapshot_invalid')
            assert(session:confirmGroups(handle,202,response()).state=='confirmed')
            assert(choice()==nil)
        """)

    def test_confirm_only_valid_whole_acknowledgements(self):
        mutations = (
            "status=200",
            "document.schemaVersion=1",
            "document.fgaPhotoBindingId='other-binding'",
            "document.flickrPhotoId='other-photo'",
            "document.extra=true",
            "document.submissions[2]=nil",
            "document.submissions[1].flickrGroupId='g2'",
            "document.submissions[2].fgaSubmissionIntentId='intent-g1'",
            "document.submissions[1].state='unknown'",
            "document.submissions[1].created='true'",
            "document.submissions[1].permanentSubmissionBlock={}",
            "document.submissions[1].extra=true",
            "document.submissions[1].state='moderation_submitted'",
            "document.submissions[1].permanentSubmissionBlock="
            "{reasonCode='delivery_uncertain',createdAt='2026-10-17T00:00:00Z'}",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("""
                    assert(save({'g1','g2'}).state=='saved'); freeze()
                    assert(session:bindGroups(handle,binding).state=='bound')
                    document=response(); status=202
                    priorChoice=photo.properties.groupAdditionSelections
                    priorOutbox=catalogProperties.groupAdditionOutboxV1; priorWrites=writes
                """)
                self.lua.execute(mutation)
                self.lua.execute("""
                    assert(session:confirmGroups(handle,status,document).state=='ack_invalid')
                    assert(photo.properties.groupAdditionSelections==priorChoice)
                    assert(catalogProperties.groupAdditionOutboxV1==priorOutbox
                        and writes==priorWrites)
                """)

    def test_missing_binding_and_forged_handle_cannot_acknowledge(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved'); freeze()
            assert(session:confirmGroups(handle,202,response()).state=='snapshot_invalid')
            assert(session:inspect({}).state=='snapshot_invalid')
            assert(session:bindGroups({},binding).state=='snapshot_invalid')
            assert(session:confirmGroups({},202,response()).state=='snapshot_invalid')
            assert(session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true}).state=='snapshot_invalid')
            assert(choice().selectionRevision==1)
        """)

    def test_binding_schema_and_safe_integer_revisions(self):
        for mutation in (
            "binding.verificationRevision=0",
            "binding.verificationRevision=1.5",
            "binding.verificationRevision=0/0",
            "binding.verificationRevision=math.huge",
            "binding.verificationRevision=9007199254740992",
            "binding.linkedFlickrRevision='9'",
            "binding.fgaPhotoBindingId=''",
            "binding.sourceKind='unknown'",
            "binding.extra=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("assert(save({'g1','g2'}).state=='saved'); freeze()")
                self.lua.execute(mutation)
                self.lua.execute(
                    "assert(session:bindGroups(handle,binding).state=='binding_invalid')"
                )
        self.setUp()
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved'); freeze()
            binding.verificationRevision=9007199254740991
            binding.linkedFlickrRevision=9007199254740991
            assert(session:bindGroups(handle,binding).state=='bound')
            assert(session:confirmGroups(handle,202,response()).state=='confirmed')
        """)

    def test_late_ack_and_revision_aba_preserve_newer_choices(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved'); freeze()
            assert(session:bindGroups(handle,binding).state=='bound')
            assert(save({},1).selection.selectionRevision==2)
            local result=session:confirmGroups(handle,202,response())
            assert(result.state=='confirmed' and not result.selectionConsumed)
            assert(choice().choice=='none' and choice().selectionRevision==2)
            freeze('none-2')
            assert(session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true}).selectionConsumed)
            assert(save({'g1'}).selection.selectionRevision==3)
            assert(session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true}).state=='snapshot_invalid')
            assert(choice().selectionRevision==3)
        """)

    def test_zero_group_requires_both_independent_publication_obligations(self):
        for evidence in (
            "{}",
            "{publicationRecorded=true}",
            "{albumAttachmentDurable=true}",
            "{publicationRecorded=true,albumAttachmentDurable=false}",
            "{publicationRecorded=false,albumAttachmentDurable=true}",
            "{publicationRecorded='true',albumAttachmentDurable=true}",
            "{publicationRecorded=true,albumAttachmentDurable=true,submissions={}}",
        ):
            with self.subTest(evidence=evidence):
                self.setUp()
                self.lua.execute("assert(save({}).state=='saved'); freeze(); priorWrites=writes")
                self.lua.execute(
                    f"assert(session:confirmPublication(handle,{evidence}).state=='ack_invalid')"
                )
                self.lua.execute("assert(choice().choice=='none' and writes==priorWrites)")
        self.lua.execute("""
            assert(session:bindGroups(handle,binding).state=='snapshot_invalid')
            assert(session:confirmGroups(handle,202,response({})).state=='snapshot_invalid')
        """)

    def test_late_absent_ack_does_not_clear_a_new_explicit_choice(self):
        self.lua.execute("""
            freeze(); assert(save({}).state=='saved')
            local result=session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true})
            assert(result.state=='confirmed' and not result.selectionConsumed)
            assert(choice().selectionRevision==1 and choice().choice=='none')
        """)

    def test_ack_response_mutation_while_waiting_cannot_change_frozen_ack(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved'); freeze()
            assert(session:bindGroups(handle,binding).state=='bound')
            document=response()
            beforeGate=function()
                document.submissions[1].flickrGroupId='forged'
                document.submissions[1].fgaSubmissionIntentId='forged'
                assert(session:confirmGroups(handle,202,response()).state=='busy')
            end
            assert(session:confirmGroups(handle,202,document).state=='confirmed')
            local h=store:readHandoff(scope,'handoff-65').handoff
            assert(h.submissions[1].flickrGroupId=='g1'
                and h.submissions[1].fgaSubmissionIntentId=='intent-g1')
        """)

    def test_protected_terminal_intents_are_retained_without_new_acceptance(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved'); freeze()
            assert(session:bindGroups(handle,binding).state=='bound')
            local document=response()
            local row=document.submissions[1]
            row.state='moderation_submitted'; row.created=false
            row.permanentSubmissionBlock={reasonCode='moderation_submission_recorded',
                createdAt='2026-10-17T00:00:00Z'}
            document.submissions[2].state='delivery_uncertain'
            document.submissions[2].created=false
            document.submissions[2].permanentSubmissionBlock={reasonCode='delivery_uncertain',
                createdAt='2026-10-17T00:00:00Z'}
            assert(session:confirmGroups(handle,202,document).state=='confirmed')
            local stored=store:readHandoff(scope,'handoff-65').handoff
            assert(stored.submissions[1].state=='moderation_submitted')
            assert(stored.submissions[2].state=='delivery_uncertain')
        """)

    def test_invalid_scope_and_export_context_fail_before_durable_work(self):
        for mutation in (
            "context.publishService={}",
            "context.publishedCollection={}",
            "context.publishedCollectionInfo=nil",
            "context.publishedCollectionInfo.isDefaultCollection=true",
            "photo.catalog={}",
            "memberships={}",
            "album.isSmartCollection=function() return true end",
            "album.getService=function() return {} end",
            "service.getPluginId=function() return 'foreign' end",
            "service.localIdentifier=0",
            "service.localIdentifier=9007199254740992",
            "album.localIdentifier=1.5",
            "photoUuid='invalid'",
            "cancelled=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute(mutation)
                self.lua.execute("assert(start()==nil and writes==0)")

    def test_scope_change_at_confirmation_gate_preserves_all_bytes(self):
        for mutation in (
            "activeCatalog={}",
            "cancelled=true",
            "memberships={}",
            "photoUuid='00000000-0000-0000-0000-000000000066'",
            "service.localIdentifier=13",
            "album.localIdentifier=35",
            "context.publishService={}",
            "context.publishedCollectionInfo.isDefaultCollection=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("""
                    assert(save({'g1','g2'}).state=='saved'); freeze()
                    assert(session:bindGroups(handle,binding).state=='bound')
                    priorPhoto=photo.properties.groupAdditionSelections
                    priorOutbox=catalogProperties.groupAdditionOutboxV1
                    priorWrites=writes
                """)
                self.lua.execute(f"beforeGate=function() {mutation} end")
                self.lua.execute("""
                    assert(session:confirmGroups(handle,202,response()).state~='confirmed')
                    assert(photo.properties.groupAdditionSelections==priorPhoto)
                    assert(catalogProperties.groupAdditionOutboxV1==priorOutbox
                        and writes==priorWrites)
                """)

    def test_queued_callback_is_closed_and_cannot_consume_later(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved'); freeze()
            assert(session:bindGroups(handle,binding).state=='bound')
            local prior=writes; gate='queued'
            assert(session:confirmGroups(handle,202,response()).state=='write_unconfirmed')
            assert(not pcall(delayed) and writes==prior)
            gate='executed'; assert(choice().selectionRevision==1)
        """)

    def test_revision_race_during_freeze_preserves_latest_edit(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved')
            session=assert(start())
            afterGate=function()
                assert(save({},1).state=='saved')
            end
            local result=session:freeze('race')
            assert(result.state~='frozen')
            assert(choice().selectionRevision==2 and choice().choice=='none')
            assert(catalogProperties.groupAdditionOutboxV1==nil)
        """)

    def test_corrupt_photo_does_not_block_independent_photo(self):
        self.lua.execute("""
            photo.properties.groupAdditionSelections='corrupt'
            local bad=assert(start())
            assert(bad:freeze('bad').state=='stored_invalid')
            assert(photo.properties.groupAdditionSelections=='corrupt' and writes==0)
            local oldPhoto=photo
            photo={catalog=catalog,properties={}}
            for key,value in pairs(oldPhoto) do
                if type(value)=='function' then photo[key]=value end
            end
            photoUuid='00000000-0000-0000-0000-000000000066'
            local good=assert(start()); local result=good:freeze('good')
            assert(result.state=='frozen')
            assert(bad:confirmPublication(result.snapshot,
                {publicationRecorded=true,albumAttachmentDurable=true}).state~='confirmed')
            assert(good:confirmPublication(result.snapshot,
                {publicationRecorded=true,albumAttachmentDurable=true}).state=='confirmed')
            assert(oldPhoto.properties.groupAdditionSelections=='corrupt')
        """)

    def test_corrupt_outbox_or_selection_preserved_without_repair(self):
        for field in ("photo", "outbox"):
            for raw in (
                "not-json",
                '{"schemaVersion":99,"entries":[]}',
                '{"schemaVersion":1,"entries":[],"entries":[]}',
            ):
                with self.subTest(field=field, raw=raw):
                    self.setUp()
                    self.lua.globals().raw = raw
                    self.lua.execute(
                        "photo.properties.groupAdditionSelections=raw"
                        if field == "photo"
                        else "catalogProperties.groupAdditionOutboxV1=raw"
                    )
                    self.lua.execute("""
                        local s=assert(start()); assert(s:freeze('corrupt').state=='stored_invalid')
                        assert(writes==0)
                    """)
                    self.lua.execute(
                        "assert(photo.properties.groupAdditionSelections==raw)"
                        if field == "photo"
                        else "assert(catalogProperties.groupAdditionOutboxV1==raw)"
                    )

    def test_safe_integer_high_selection_revision_does_not_round(self):
        self.lua.execute("""
            photo.properties.groupAdditionSelections='{"schemaVersion":1,"entries":[{'
                ..'"publishServiceLocalId":12,"publishedCollectionLocalId":34,'
                ..'"photoUuid":"'..photoUuid..'","selectionRevision":9007199254740991,'
                ..'"choice":"none","flickrGroupIds":[]}]}'
            local result=freeze()
            assert(result.choice.selectionRevision==9007199254740991)
            assert(catalogProperties.groupAdditionOutboxV1:find('9007199254740991',1,true))
            assert(session:confirmPublication(handle,
                {publicationRecorded=true,albumAttachmentDurable=true}).selectionConsumed)
            assert(save({}).state=='revision_exhausted')
        """)

    def test_other_service_and_album_scopes_survive_consumption(self):
        self.lua.execute("""
            assert(save({'g1','g2'}).state=='saved')
            local other={publishServiceLocalId=13,publishedCollectionLocalId=34,photoUuid=photoUuid}
            assert(store:saveChoice(other,{'other-service'},0).state=='saved')
            other={publishServiceLocalId=12,publishedCollectionLocalId=35,photoUuid=photoUuid}
            assert(store:saveChoice(other,{'other-album'},0).state=='saved')
            freeze(); assert(session:bindGroups(handle,binding).state=='bound')
            assert(session:confirmGroups(handle,202,response()).selectionConsumed)
            assert(store:readChoice(other).selection.flickrGroupIds[1]=='other-album')
            other.publishServiceLocalId=13; other.publishedCollectionLocalId=34
            assert(store:readChoice(other).selection.flickrGroupIds[1]=='other-service')
        """)

    def test_unregistered_and_unqualified(self):
        self.assertFalse(self.lua.globals().Adapter.PRODUCTION_QUALIFIED)
        self.assertNotIn("FrozenChoice", (BUNDLE / "Info.lua").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
