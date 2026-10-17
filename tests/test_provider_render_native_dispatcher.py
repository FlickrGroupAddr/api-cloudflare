"""Actual Native.run source under synthetic SDK objects; never native qualification."""

import binascii
import hashlib
import struct
import unittest
import zlib
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "probes/lightroom/FGA-ProviderRender-Qualification.lrplugin"


def png_bytes():
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", binascii.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + bytes(24)) * 8))
        + chunk(b"IEND", b"")
    )


class ProviderRenderNativeDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        g = self.lua.globals()
        g.publisher = (ROOT / "clients/lightroom/publisher").as_posix()
        g.client = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin").as_posix()
        g.bundle = BUNDLE.as_posix()
        self.lua.execute(
            'package.path=bundle.."/?.lua;"..publisher.."/?.lua;"..client.."/?.lua;"..package.path'
        )
        self.lua.execute((ROOT / "tests/publisher_frozen_context_fixture.lua").read_text("utf-8"))
        g.sha256 = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
        g.bundleSources = self.lua.table_from(
            {path.name: path.read_text("utf-8") for path in BUNDLE.glob("*.lua")}
        )
        g.bundleSources["MetadataDefinition.lua"] = (
            ROOT / "clients/lightroom/FGA-LrC15.lrplugin/MetadataDefinition.lua"
        ).read_text("utf-8")
        g.pngBytes = png_bytes()
        # Minimal bounded JPEG header/scan structure for the actual asset parser.
        jpeg = bytes.fromhex(
            "ffd8 ffc0 000b 08 0008 0008 01 01 11 00 ffda 0008 01 01 00 00 3f 00 01 ffd9"
        )
        g.jpegBytes = jpeg
        g.NativeHarness = self.lua.execute(
            (ROOT / "tests/provider_render_native_fixture.lua").read_text("utf-8")
        )
        self.lua.execute("Native=require 'Native';NativeHarness:consent()")

    def run_lua(self, body):
        return self.lua.execute(body)

    def test_all_fourteen_cases_dispatch_real_modules_and_cleanup(self):
        self.run_lua("""
            Native.run()
            local h=NativeHarness
            assert(h.report and #h.report.cases==14)
            for index,row in ipairs(h.report.cases) do
                assert(row.caseId==require('Config').CASES[index])
                assert(row.terminal and row.ok,row.caseId..':'..tostring(row.code))
                assert(row.nativeSchedulingProven~=true)
            end
            assert(h.report.allCasesPassed and h.report.networkCalls==0)
            assert(h.report.nativeSchedulingProven==false and not h.report.productionQualified)
            assert(h.imports==15 and h.report.cleanup.importedSyntheticPhotos==15)
            assert(h.report.cleanup.privateRecordsCleared and h.report.cleanup.albumDeleted)
            assert(h.report.cleanup.ownedFilesDeleted and h.report.cleanup.catalogDisposalRequired)
            assert(h.pending==0 and h.eagerStarts>0)
            assert(h.waits==h.eagerStarts)
            assert(h.deletesWhilePending==0 and h.catalogWritesWhilePending==0)
            assert(h.report.cleanup.renderCompletionProven)
            assert(h.report.actualHost.major==15 and h.report.actualHost.minor==6)
            assert(h.report.actualHost.revision==2 and h.report.actualHost.build==123456)
            assert(h.report.actualHost.buildVersion=='synthetic-unit-build')
            assert(h.report.actualHost.private==nil)
            assert(service:getPluginId()~=require('ConnectionCore').PLUGIN_ID)
            assert(service:getPluginId()==_PLUGIN.id)
            for _,session in ipairs(h.sessions) do
                assert(session.started or #session.candidates==1)
            end
        """)

    def test_consent_and_digest_refusals_precede_writes(self):
        for patch in (
            "c.owner='Other'",
            "c.expiresAt=c.grantedAt+1801",
            "c.expiresAt=1000",
            "c.grantedAt=1001",
            "c.manifestSha2_256=string.rep('0',64)",
            "c.artifactSha2_256=string.rep('0',64)",
            "c.allowCleanup=false",
            "c.unexpected=true",
        ):
            with self.subTest(patch=patch):
                self.setUp()
                self.run_lua(f"""
                    NativeHarness:consent(function(c) {patch} end)
                    Native.run()
                    assert(NativeHarness.mutations==0 and NativeHarness.imports==0)
                    assert(NativeHarness.dialogs[1]=='Qualification refused')
                """)

    def test_catalog_bundle_and_host_refusals_precede_writes(self):
        for patch in (
            "NativeHarness.foreignPhoto=true",
            "NativeHarness.services={}",
            "NativeHarness.hostMinor=5",
            "_PLUGIN.id='production-plugin'",
            "NativeHarness.file(_PLUGIN.path..'/extra.lua','unexpected')",
            "NativeHarness.directories[_PLUGIN.path..'/unexpected']=true",
            "NativeHarness.file(_PLUGIN.path..'/Native.lua','tampered')",
            "catalogProperties.uploadAttemptRecoveryStore='retained'",
            "NativeHarness.catalogPath='/disposable/Real.lrcat'",
        ):
            with self.subTest(patch=patch):
                self.setUp()
                self.run_lua(f"""
                    {patch}
                    Native.run()
                    assert(NativeHarness.mutations==0 and NativeHarness.imports==0)
                    assert(NativeHarness.dialogs[1]=='Qualification refused')
                """)

    def test_consent_expiry_after_confirmation_prevents_import_and_fills_receipts(self):
        self.run_lua("""
            local h=NativeHarness
            h.onConfirm=function() h.clock=1800 end
            Native.run()
            assert(h.imports==0 and h.report.status=='run_failed')
            assert(#h.report.cases==14 and not h.report.allCasesPassed)
            for _,row in ipairs(h.report.cases) do assert(row.terminal and row.code=='not_run') end
        """)

    def test_expiry_during_render_stops_later_cases_and_cleans_owned_records(self):
        self.run_lua("""
            local h=NativeHarness
            h.onWait=function() h.clock=1800 end
            Native.run()
            assert(h.waits==1 and h.report.status=='run_failed')
            assert(#h.report.cases==14 and h.report.cleanup.privateRecordsCleared)
            assert(h.report.cleanup.albumDeleted and h.report.cleanup.ownedFilesDeleted)
        """)

    def test_confirmation_cancel_never_mutates_catalog(self):
        self.run_lua("""
            NativeHarness.confirm='cancel'
            Native.run()
            assert(NativeHarness.mutations==0 and not NativeHarness.report)
        """)

    def test_consent_replacement_after_confirmation_prevents_imports(self):
        self.run_lua("""
            local h=NativeHarness
            h.onConfirm=function() h.file('/consent.json','revoked') end
            Native.run()
            assert(h.imports==0 and h.report.status=='run_failed')
            assert(#h.report.cases==14 and not h.report.allCasesPassed)
        """)

    def test_registered_test_provider_native_publish_callback_refuses(self):
        self.run_lua("""
            local provider=require 'QualificationProvider'
            local ok,message=pcall(provider.processRenderedPhotos)
            assert(not ok and message==
                'Use the explicit qualification menu after exact-artifact consent')
            assert(NativeHarness.mutations==0 and NativeHarness.waits==0)
        """)

    def test_unknown_render_completion_preserves_catalog_and_files(self):
        for fault in (
            "waitThrows",
            "waitNonboolean",
            "iteratorCreationThrows",
            "iteratorAdvanceThrows",
            "omitRendition",
        ):
            with self.subTest(fault=fault):
                self.setUp()
                self.run_lua(f"""
                    local h=NativeHarness
                    h.{fault}=true
                    Native.run()
                    assert(h.pending>0 and h.eagerStarts>0)
                    if '{fault}'=='waitThrows' or '{fault}'=='waitNonboolean' then
                        assert(h.waits==1)
                    end
                    assert(h.report and not h.report.allCasesPassed)
                    assert(#h.report.cases==14)
                    assert(h.report.cleanup.renderCompletionProven==false)
                    assert(h.report.cleanup.preservedForUnresolvedRender==true)
                    assert(h.report.cleanup.privateRecordsCleared==false)
                    assert(h.report.cleanup.albumDeleted==false and h.album~=nil)
                    assert(h.catalogWritesWhilePending==0 and h.deletesWhilePending==0)
                    assert(h.files['/disposable/FGA-provider-render-qualification-v1/synthetic-01.tif'])
                    for _,row in ipairs(h.report.cases) do assert(row.terminal) end
                """)

    def test_incomplete_enumeration_preserves_even_when_observed_render_is_terminal(self):
        self.run_lua("""
            local h=NativeHarness
            h.iteratorAdvanceThrows=true;h.iteratorAdvanceAfterFirst=true
            Native.run()
            assert(h.pending==0 and h.eagerStarts==1 and h.waits==1)
            assert(not h.report.allCasesPassed and h.report.status=='cleanup_incomplete')
            assert(h.report.cleanup.renderCompletionProven==false)
            assert(h.report.cleanup.preservedForUnresolvedRender==true)
            assert(h.album~=nil and not h.report.cleanup.privateRecordsCleared)
            assert(h.catalogWritesWhilePending==0 and h.deletesWhilePending==0)
        """)

    def test_boolean_failed_native_wait_is_cached_terminal_without_retry(self):
        self.run_lua("""
            local h=NativeHarness
            h.waitFalseAt=1
            Native.run()
            assert(h.pending==0 and h.waits==h.eagerStarts)
            assert(h.report.cases[1].code=='render_failed' and not h.report.cases[1].ok)
            assert(h.report.cleanup.renderCompletionProven==true)
            assert(h.report.cleanup.privateRecordsCleared and h.report.cleanup.albumDeleted)
            assert(not h.report.allCasesPassed)
            assert(not h.files['/disposable/FGA-provider-render-qualification-v1/receipts.json']
                .contents:find('private render detail',1,true))
        """)

    def test_real_render_failure_cannot_claim_unapplied_injected_failure(self):
        self.run_lua("""
            local h=NativeHarness
            h.waitFalseSession=10
            Native.run()
            local row=h.report.cases[10]
            assert(row.caseId=='render_failed' and row.code=='render_failed')
            assert(row.nativeRenderFailed==true and row.boundaryFaultInjected==false)
            assert(row.faultStatus=='not_applied' and row.ok==false)
            assert(h.report.allCasesPassed==false and h.report.nativeSchedulingProven==false)
            assert(h.report.cleanup.renderCompletionProven and h.pending==0)
            assert(h.waits==h.eagerStarts)
        """)


if __name__ == "__main__":
    unittest.main()
