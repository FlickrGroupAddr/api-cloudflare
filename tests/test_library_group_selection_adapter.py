"""Actual Lua 5.1 Library scope/controller/store under synthetic SDK boundaries."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class LibraryGroupSelectionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.execute(
            (ROOT / "tests/library_group_selection_adapter_fixture.lua").read_text("utf-8")
        )

    def test_actual_core_empty_save_explicit_none_then_clear(self):
        self.lua.execute("""
            c=controller()
            assert(c.model.ready and not c.model.bound and c.revision==0)
            assert(c.deps.store:readChoice(c.scope).selection==nil)
            assert(c:commit().state=='saved')
            local choice=c.deps.store:readChoice(c.scope).selection
            assert(choice.choice=='none' and #choice.flickrGroupIds==0)
            assert(c.toggle(c.model,'g1',true))
            assert(c:commit().state=='saved')
            c.toggle(c.model,'g1',false)
            assert(c:commit().state=='saved')
            choice=c.deps.store:readChoice(c.scope).selection
            assert(choice.choice=='none' and choice.selectionRevision==3)
            assert(catalogProperties.groupAdditionOutboxV1==nil)
        """)

    def test_same_photo_two_services_and_albums_preserves_exact_scopes(self):
        self.lua.execute("""
            local first=controller()
            first.toggle(first.model,'g1',true); assert(first:commit().state=='saved')
            local service2={localIdentifier=13,type=service.type,getPluginId=service.getPluginId}
            local album2={localIdentifier=35,type=album.type,
                isSmartCollection=album.isSmartCollection,
                getName=album.getName,getService=function() return service2 end}
            memberships={album,album2}; sources={album2}
            local second=controller()
            second.toggle(second.model,'g2',true); assert(second:commit().state=='saved')
            assert(first:commit().state=='save_failed')
            sources={album}
            local reopened=controller()
            assert(reopened.model.selected.g1 and not reopened.model.selected.g2)
            assert(reopened:commit().state=='saved')
            local json=require 'dkjson'
            local entries=json.decode(photoProperties.groupAdditionSelections).entries
            assert(#entries==2 and entries[1].publishServiceLocalId==12
                and entries[2].publishServiceLocalId==13 and entries[2].flickrGroupIds[1]=='g2')
        """)

    def test_same_service_second_album_preserves_other_choice(self):
        self.lua.execute("""
            c=controller(); c.toggle(c.model,'g1',true); assert(c:commit().state=='saved')
            local other={localIdentifier=35,type=album.type,
                isSmartCollection=album.isSmartCollection,
                getService=album.getService,getName=album.getName}
            sources={other}; memberships={album,other}
            c=controller(); assert(c:commit().state=='saved')
            sources={album}; c=controller(); assert(c.model.selected.g1)
        """)

    def test_unavailable_saved_ids_require_explicit_removal(self):
        self.lua.execute("""
            c=controller(); c.toggle(c.model,'g1',true); assert(c:commit().state=='saved')
            snapshot.groups={{flickrGroupId='g2',displayName='Another'}}
            c=controller(); assert(c.model.selected.g1 and not c.canConfirm(c.model))
            assert(c:commit().state=='refused')
            assert(c.clearUnavailableChoices(c.model)); assert(c:commit().state=='saved')
            assert(c.deps.store:readChoice(c.scope).selection.choice=='none')
        """)

    def test_scope_refusals_before_open_or_write(self):
        mutations = (
            "targets={}",
            "targets={photo,photo}",
            "targets.extra=photo",
            "sources={}",
            "sources={album,album}",
            "sources.extra=album",
            "photo.catalog={}",
            "memberships={}",
            "memberships={{localIdentifier=34,getName=album.getName}}",
            "album.type=function() return 'LrCollection' end",
            "album.isSmartCollection=function() return true end",
            "album.isSmartCollection=function() return nil end",
            "service.type=function() return 'LrPublishedCollectionSet' end",
            "service.getPluginId=function() return 'foreign' end",
            "service.localIdentifier=0",
            "service.localIdentifier=0/0",
            "album.localIdentifier='34'",
            "photoUuid='invalid'",
            "cancelled=true",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute(mutation)
                self.lua.execute("assert(start()==nil); assert(writes==0)")

    def test_scope_fences_before_and_inside_gate_and_readback(self):
        for mutation in (
            "activeCatalog={}",
            "sources={}",
            "memberships={}",
            "photoUuid='00000000-0000-0000-0000-000000000025'",
            "cancelled=true",
            "album.localIdentifier=99",
            "service.localIdentifier=99",
        ):
            for boundary in ("before", "inside", "after"):
                with self.subTest(mutation=mutation, boundary=boundary):
                    self.setUp()
                    self.lua.execute("c=controller(); c.toggle(c.model,'g1',true)")
                    hook = "beforeGate" if boundary == "inside" else "afterGate"
                    self.lua.execute(
                        mutation if boundary == "before" else f"{hook}=function() {mutation} end"
                    )
                    self.lua.execute("assert(c:commit().state=='save_failed')")
                    if boundary != "after":
                        self.lua.execute("assert(writes==0)")

    def test_timeout_and_late_callback_do_not_write(self):
        self.lua.execute("""
            c=controller(); gate='queued'; assert(c:commit().state=='save_failed')
            assert(writes==0); assert(not pcall(delayed)); assert(writes==0)
        """)

    def test_malformed_and_full_storage_fail_closed(self):
        for raw in (
            "not json",
            " " * (512 * 1024 + 1),
            '{"schemaVersion":99,"entries":[]}',
            '{"schemaVersion":1,"entries":[],"entries":[]}',
        ):
            with self.subTest(raw=raw):
                self.setUp()
                self.lua.globals().raw = raw
                self.lua.execute("""
                    photoProperties.groupAdditionSelections=raw
                    session=assert(start()); assert(session:unpublishedController(snapshot)==nil)
                    assert(photoProperties.groupAdditionSelections==raw and writes==0)
                """)
        self.setUp()
        self.lua.execute("""
            local entries={}
            for i=1,64 do entries[i]={publishServiceLocalId=i,publishedCollectionLocalId=99,
                photoUuid=photoUuid,selectionRevision=1,choice='groups',flickrGroupIds={'g2'}} end
            photoProperties.groupAdditionSelections=require('dkjson').encode({schemaVersion=1,entries=entries})
            c=controller(); assert(c:commit().state=='save_failed'); assert(writes==0)
        """)

    def test_sixty_group_limit_and_exact_ids(self):
        self.lua.execute("""
            snapshot.groups={}
            for i=1,61 do snapshot.groups[i]={flickrGroupId='g'..i,displayName='Same'} end
            c=controller()
            for i=1,61 do c.toggle(c.model,'g'..i,true) end
            assert(c:commit().state=='refused' and writes==0)
            c.toggle(c.model,'g61',false); assert(c:commit().count==60)
        """)

    def test_other_photo_bytes_untouched_and_snapshot_failures(self):
        self.lua.execute("""
            c=controller(); c.toggle(c.model,'g1',true); assert(c:commit().state=='saved')
            local prior=photoProperties.groupAdditionSelections
            local second={catalog=catalog,properties={}}
            for key,value in pairs(photo) do
                if type(value)=='function' then second[key]=value end
            end
            second.getRawMetadata=function() return '00000000-0000-0000-0000-000000000025' end
            targets={second}
            c=controller(); assert(c:commit().state=='saved')
            assert(photoProperties.groupAdditionSelections==prior)
            assert(require('dkjson').decode(second.properties.groupAdditionSelections).entries[1].photoUuid
                =='00000000-0000-0000-0000-000000000025')
            snapshot.snapshotStatus='stale_refreshing'
            assert(session:unpublishedController(snapshot)==nil)
            snapshot.snapshotStatus='fresh'; snapshot.groups[2].flickrGroupId='g1'
            assert(session:unpublishedController(snapshot)==nil)
        """)

    def test_private_metadata_field_and_disabled_registration(self):
        definition = self.lua.execute((BUNDLE / "MetadataDefinition.lua").read_text("utf-8"))
        field = definition.metadataFieldsForPhotos[1]
        self.assertEqual(field.id, "groupAdditionSelections")
        self.assertEqual(field.dataType, "string")
        self.assertIsNone(field.title)
        self.assertFalse(self.lua.globals().Adapter.PRODUCTION_QUALIFIED)
        self.assertNotIn("MetadataDefinition", (BUNDLE / "Info.lua").read_text("utf-8"))
        self.assertNotIn("LibraryGroupSelection", (BUNDLE / "Info.lua").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
