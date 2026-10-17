"""Original ordinary-Album callbacks in Lua 5.1 with fake documented SDK objects."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "clients/lightroom/publisher"


class OrdinaryAlbumProviderTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.lua.globals().settingsModule = self.lua.execute(
            (SOURCE / "OrdinaryAlbumProviderSettings.lua").read_text("utf-8-sig")
        )
        self.lua.execute("""
            function require(name)
                assert(name == 'OrdinaryAlbumProviderSettings')
                return settingsModule
            end
            function import() error('No SDK import permitted') end
        """)
        self.lua.globals().providerModule = self.lua.execute(
            (SOURCE / "OrdinaryAlbumProvider.lua").read_text("utf-8-sig")
        )
        self.lua.execute("""
            calls = { verify = 0, render = 0 }
            identity = { schemaVersion=1,
                fgaPublishServiceId='12345678-1234-4123-8123-123456789abc',
                issuingInstallationId='installation-1', linkedFlickrRevision=2,
                serviceRevision=1 }
            verified = { ok=true, identity=identity, linkStatus='ready' }
            saved = { schemaVersion=1, albumLifecycle='local_unbound' }
            serviceSettings = { configured=true }
            summary = { localIdentifier=42, isDefaultCollection=false,
                collectionSettings=saved, publishSettings=serviceSettings }
            service = { getPluginId=function() return 'fga-lrc15' end }
            collection = {
                localIdentifier=42,
                isSmartCollection=function() return false end,
                getService=function() return service end,
                getCollectionInfoSummary=function() return summary end,
            }
            context = { publishedCollection=collection,
                publishedCollectionInfo={isDefaultCollection=false},
                propertyTable={untrusted=true},
                renditions=function() calls.render=calls.render+1; error('render') end }
            provider = providerModule.new {
                pcall=pcall, pluginId='fga-lrc15',
                verifyService=function(settings)
                    assert(settings == serviceSettings)
                    calls.verify=calls.verify+1
                    return verified
                end,
            }
            function validate() return provider.validateTarget(context.propertyTable, context) end
            -- SDK LrObservableTable proxy: built-in pairs sees no backing fields.
            function observable(values)
                return setmetatable({}, {
                    __index=function(_, key)
                        if key == 'pairs' then
                            return function() return pairs(values) end
                        end
                        return values[key]
                    end,
                    __newindex=function(_, key, value) values[key]=value end,
                })
            end
            local originalView=provider.viewForCollectionSettings
            function provider.viewForCollectionSettings(f, settings, info)
                info.collectionSettings=observable(info.collectionSettings)
                return originalView(f, settings, info)
            end
            factory = { static_text=function(_, spec) return spec end,
                group_box=function(_, spec) return spec end }
        """)

    def run_lua(self, body):
        return self.lua.execute(body)

    def test_local_creation_stores_only_unbound_state(self):
        settings = self.run_lua("""
            local info = { collectionType='collection', isDefaultCollection=false,
                collectionSettings={} }
            provider.viewForCollectionSettings(factory, {}, info)
            assert(calls.verify == 0)
            return info.collectionSettings
        """)
        self.assertEqual(
            {
                key: settings[key]
                for key in ("schemaVersion", "albumLifecycle", "LR_canSaveCollection")
            },
            {
                "schemaVersion": 1,
                "albumLifecycle": "local_unbound",
                "LR_canSaveCollection": True,
            },
        )

    def test_default_smart_missing_kind_creation_cannot_save(self):
        for patch in (
            "isDefaultCollection=true",
            "collectionType='smartCollection'",
            "collectionType=nil",
            "isDefaultCollection=nil",
        ):
            with self.subTest(patch=patch):
                self.assertFalse(
                    self.run_lua(
                        """
                    local info={collectionType='collection', isDefaultCollection=false,
                        collectionSettings={}}
                """
                        + "info."
                        + patch
                        + """
                    provider.viewForCollectionSettings(factory, {}, info)
                    assert(info.collectionSettings.schemaVersion == nil)
                    return info.collectionSettings.LR_canSaveCollection
                """
                    )
                )

    def test_retained_or_dirty_settings_never_reset(self):
        for patch in (
            "albumLifecycle='bound'",
            "schemaVersion=2",
            "fgaAlbumBindingId='binding'",
            "remoteId='photoset'",
            "unexpected=true",
        ):
            with self.subTest(patch=patch):
                self.assertFalse(
                    self.run_lua(
                        """
                    local info={collectionType='collection', isDefaultCollection=false,
                        collectionSettings={
                """
                        + patch
                        + """}}
                    provider.viewForCollectionSettings(factory, {}, info)
                    return info.collectionSettings.LR_canSaveCollection
                """
                    )
                )
        self.assertFalse(
            self.run_lua("""
            local info={collectionType='collection', isDefaultCollection=false,
                publishedCollection=collection, collectionSettings={}}
            provider.viewForCollectionSettings(factory, {}, info)
            assert(info.collectionSettings.schemaVersion == nil)
            return info.collectionSettings.LR_canSaveCollection
        """)
        )

    def test_valid_target_uses_local_id_and_verified_server_identity(self):
        result = self.run_lua("return validate()")
        self.assertTrue(result.ok)
        self.assertEqual(result.localCollectionIdentifier, "42")
        self.assertEqual(
            result.fgaPublishServiceId, self.lua.globals().identity.fgaPublishServiceId
        )
        self.assertIsNone(result.publishSettings)
        self.assertEqual(self.lua.globals().calls.verify, 1)

    def test_reparent_name_and_duplicate_names_do_not_change_identity(self):
        result = self.run_lua("""
            summary.parents={{name='New parent', remoteCollectionId='ignored'}}
            summary.name='Duplicate name'
            return validate()
        """)
        self.assertTrue(result.ok)
        self.assertEqual(result.localCollectionIdentifier, "42")
        self.assertTrue(
            self.run_lua("return provider.validatePublishedCollectionName('Duplicate name')")
        )

    def test_default_smart_foreign_and_invalid_local_id_refuse_before_identity(self):
        for patch in (
            "context.publishedCollectionInfo.isDefaultCollection=true",
            "summary.isDefaultCollection=true",
            "collection.isSmartCollection=function() return true end",
            "service.getPluginId=function() return 'other-provider' end",
            "collection.localIdentifier=0",
            "summary.localIdentifier=43",
            "collection.getCollectionInfoSummary=function() error('private') end",
            "saved.albumLifecycle='bound'",
            "context.publishedCollection=nil",
        ):
            with self.subTest(patch=patch):
                self.setUp()
                result = self.run_lua(patch + "; return validate()")
                self.assertFalse(result.ok)
                self.assertEqual(self.lua.globals().calls.verify, 0)

    def test_all_remote_records_require_reconciliation(self):
        for location in ("summary", "context.publishedCollectionInfo"):
            for field in ("remoteId", "remoteUrl"):
                for value in ("'foreign'", "''", "42", "false"):
                    with self.subTest(location=location, field=field, value=value):
                        self.setUp()
                        result = self.run_lua(f"{location}.{field}={value}; return validate()")
                        self.assertEqual(result.code, "remote_identity_requires_reconciliation")
                        self.assertEqual(self.lua.globals().calls.verify, 0)

    def test_failed_nonready_malformed_identity_cannot_supply_target(self):
        for patch in (
            "verified.ok=false",
            "verified.linkStatus='link_changed'",
            "verified.linkStatus='link_unavailable'",
            "verified=nil",
            "identity.fgaPublishServiceId='local-invented'",
            "identity.serviceRevision=2",
            "identity.linkedFlickrRevision=0",
            "identity.issuingInstallationId='bad space'",
        ):
            with self.subTest(patch=patch):
                self.setUp()
                result = self.run_lua(patch + "; return validate()")
                self.assertFalse(result.ok)
                self.assertIsNone(result.localCollectionIdentifier)

    def test_processing_always_stops_before_rendition_and_never_echoes_private_errors(self):
        for patch, expected in (
            ("", "integration is not enabled"),
            (
                "context.publishedCollectionInfo.isDefaultCollection=true",
                "Create or select an Album",
            ),
        ):
            self.setUp()
            status, message = self.run_lua(
                patch
                + """
                return pcall(provider.processRenderedPhotos, {}, context)
            """
            )
            self.assertFalse(status)
            self.assertIn(expected, message)
            self.assertEqual(self.lua.globals().calls.render, 0)
        self.assertFalse(self.run_lua("return provider.getCollectionBehaviorInfo ~= nil"))
        self.assertEqual(self.lua.globals().provider.titleForPublishedCollection, "Album")

    def test_proxy_observable_iterator_controls_unknown_field_refusal(self):
        for values in (
            "unexpected=true",
            "schemaVersion=1, albumLifecycle='local_unbound', unexpected=true",
        ):
            with self.subTest(values=values):
                result = self.run_lua(
                    """
                    local info={collectionType='collection', isDefaultCollection=false,
                        collectionSettings={
                """
                    + values
                    + """}}
                    provider.viewForCollectionSettings(factory, {}, info)
                    assert(next(info.collectionSettings) == nil)
                    assert(info.collectionSettings.unexpected == true)
                    return info.collectionSettings.LR_canSaveCollection
                """
                )
                self.assertFalse(result)
        self.assertFalse(
            self.run_lua("""
            local settings={}
            local ok=settingsModule.prepare({collectionType='collection',
                isDefaultCollection=false, collectionSettings=settings})
            assert(settings.schemaVersion == nil)
            return ok
        """)
        )

    def test_near_maximum_local_ids_remain_distinct_canonical_decimal_strings(self):
        results = []
        for number in (1, 42, 9007199254740989, 9007199254740990, 9007199254740991):
            result = self.run_lua(f"""
                collection.localIdentifier={number}
                summary.localIdentifier={number}
                return validate()
            """)
            self.assertTrue(result.ok)
            self.assertEqual(result.localCollectionIdentifier, str(number))
            results.append(result.localCollectionIdentifier)
        self.assertEqual(len(set(results)), len(results))
        result = self.run_lua("""
            collection.localIdentifier=9007199254740992
            summary.localIdentifier=9007199254740992
            return validate()
        """)
        self.assertFalse(result.ok)

    def test_bundle_remains_unregistered(self):
        info = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin/Info.lua").read_text()
        self.assertNotIn("OrdinaryAlbumProvider", info)
        self.assertNotIn("LrExportServiceProvider", info)


if __name__ == "__main__":
    unittest.main()
