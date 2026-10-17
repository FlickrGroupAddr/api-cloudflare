"""Qualification source checks: actual dormant modules, synthetic SDK boundaries.

These tests do not load Lightroom or establish native render scheduling evidence.
"""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = ROOT / "probes/lightroom/FGA-ProviderRender-Qualification.lrplugin"


class ProviderRenderQualificationTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.lua.globals().publisher = (ROOT / "clients/lightroom/publisher").as_posix()
        self.lua.globals().bundle = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin").as_posix()
        self.lua.execute('package.path=publisher.."/?.lua;"..bundle.."/?.lua;"..package.path')
        self.lua.execute((ROOT / "tests/publisher_frozen_context_fixture.lua").read_text("utf-8"))
        self.lua.globals().FilesFixture = self.lua.execute(
            (ROOT / "tests/publisher_rendition_adapter_fixture.lua").read_text("utf-8")
        )
        self.lua.globals().Qualification = self.lua.execute(
            (QUALIFICATION / "Qualification.lua").read_text("utf-8")
        )
        self.lua.globals().Harness = self.lua.execute(
            (ROOT / "tests/provider_render_qualification_fixture.lua").read_text("utf-8")
        )

    def run_lua(self, source):
        return self.lua.execute(source)

    def test_real_selection_snapshots_absent_none_and_groups(self):
        for case_id, groups, kind in (
            ("selection_absent", None, "absent"),
            ("selection_none", "{}", "none"),
            ("selection_groups", "{'synthetic-group'}", "groups"),
        ):
            with self.subTest(case=case_id):
                self.setUp()
                save = "" if groups is None else f"assert(save(photo,{groups}).state=='saved')"
                self.run_lua(f"""
                    local h=Harness.new('{case_id}')
                    {save}
                    assert(h:prepare())
                    assert(h.files.calls.wait==0 and not h.renderStarted)
                    local records=h:records()
                    assert(#records==1 and records[1].selectionKind=='{kind}')
                    assert(h:process().code=='handed_off' and h.consumed==1)
                    assert(h.lease:read()==nil)
                """)

    def test_edit_after_freeze_preserves_durable_exact_revision(self):
        self.run_lua("""
            local h=Harness.new('selection_edit_after_freeze')
            assert(save(photo,{'before'}).state=='saved')
            assert(h:prepare())
            assert(save(photo,{'after'},1).state=='saved')
            assert(h:process().code=='handed_off')
            local record=h:records()[1]
            assert(record.selectionRevision==1 and record.flickrGroupIds[1]=='before')
            assert(choice(photo).selectionRevision==2)
        """)

    def test_failed_candidate_removed_before_valid_candidate_handoff(self):
        self.run_lua("""
            local h=Harness.new('photo_failure_isolation')
            photo.properties.groupAdditionSelections='malformed'
            local good=makePhoto('00000000-0000-0000-0000-000000000098')
            h.candidates={photo,good}
            assert(h:prepare())
            assert(h.removed[photo] and not h.removed[good])
            assert(#h:records()==1 and h.files.calls.wait==0)
            assert(h:process(good).code=='handed_off' and h.consumed==1)
        """)

    def test_settings_change_refuses_before_wait_and_byte_handoff(self):
        self.run_lua("""
            local h=Harness.new('selection_groups')
            assert(h:prepare())
            exportContext.propertyTable.LR_format='JPEG'
            assert(h:process().code=='settings_changed')
            assert(h.files.calls.wait==0 and h.consumed==0)
        """)

    def test_completed_file_failures_never_reach_consumer(self):
        for case_id, patch, expected in (
            ("render_failed", "h.files.waitThrows=true", "render_failed"),
            ("missing_file", "h.files.files['synthetic-render']=nil", "missing_file"),
            ("oversized_file", "h.files.files['synthetic-render'].size=200000001", "oversized"),
            ("file_changed", "h.files.files['synthetic-render'].size=4", "file_changed"),
        ):
            with self.subTest(case=case_id):
                self.setUp()
                self.run_lua(f"""
                    local h=Harness.new('{case_id}')
                    assert(h:prepare())
                    {patch}
                    assert(h:process().code=='{expected}')
                    assert(h.consumed==0 and h.files.calls.wait==1)
                """)

    def test_catalog_guard_and_consent_refuse_before_private_writes(self):
        for patch in ("h.guard=false", "activeCatalog={}"):
            with self.subTest(patch=patch):
                self.setUp()
                self.run_lua(f"""
                    local h=Harness.new('catalog_changed')
                    local prior=writes
                    {patch}
                    local session,reason=h:prepare()
                    assert(session==nil and reason=='scope_refused')
                    assert(writes==prior and h.files.calls.wait==0)
                """)

    def test_activation_and_cancel_fences_refuse_before_render(self):
        for case_id, patch in (
            ("activation_changed", "activation={}"),
            ("cancelled", "deps.cancelled=function() return true end"),
        ):
            with self.subTest(case=case_id):
                self.setUp()
                self.run_lua(f"""
                    local h=Harness.new('{case_id}')
                    {patch}
                    assert(h:prepare()==nil)
                    assert(h.files.calls.wait==0 and h.consumed==0)
                """)

    def test_guard_revocation_after_preparation_refuses_before_wait(self):
        for patch in ("h.guard=false", "activeCatalog={}"):
            with self.subTest(patch=patch):
                self.setUp()
                self.run_lua(f"""
                    local h=Harness.new('catalog_changed')
                    assert(h:prepare())
                    {patch}
                    local result,reason=h:process()
                    assert(result==nil and reason=='scope_refused')
                    assert(h.files.calls.wait==0 and h.consumed==0)
                    local receipts=h.fixture:receipts()
                    assert(receipts[#receipts].code=='scope_refused')
                """)

    def test_constructor_guard_short_circuits_catalog_access_and_bad_scope(self):
        self.run_lua("""
            local h=Harness.new('catalog_changed')
            h.options.guard=function() return false end
            h.options.scope.activeCatalog=function() error('catalog must not be read') end
            local fixture,reason=Qualification.new(h.options)
            assert(fixture==nil and reason=='scope_refused' and writes==0)
            h.options.guard=function() return true end
            h.options.scope.disposable=false
            assert(Qualification.new(h.options)==nil and writes==0)
            h.options.scope.disposable=true
            h.options.caseId='unbounded-history-matrix'
            assert(Qualification.new(h.options)==nil and writes==0)
        """)

    def test_invalid_session_receipt_is_terminal_and_has_no_private_fields(self):
        self.run_lua("""
            local h=Harness.new('cleanup_revocation')
            local result,reason=h.fixture:process({}, {}, function() error('must not run') end)
            assert(result==nil and reason=='session_invalid')
            local receipt=h.fixture:receipts()[1]
            assert(receipt.phase=='rendition' and receipt.code=='session_invalid')
            assert(receipt.ok==false and h.files.calls.wait==0)
            for key in pairs(receipt) do
                assert(key=='schemaVersion' or key=='caseId' or key=='phase'
                    or key=='code' or key=='ok' or key=='nativeSchedulingProven'
                    or key=='productionQualified')
            end
        """)

    def test_cleanup_during_consumption_revokes_actual_lease(self):
        self.run_lua("""
            local h=Harness.new('cleanup_revocation')
            assert(h:prepare())
            local result=h:process(nil,nil,function(lease)
                assert(lease:read()=='png')
                assert(h.fixture:finish().code=='closed')
                assert(lease:read()==nil)
                return true
            end)
            assert(result.ok==false and result.code=='cancelled')
            assert(h.files.calls.wait==1)
        """)

    def test_synthetic_sink_reads_actual_lease_without_upload_claim(self):
        self.lua.globals().Sink = self.lua.execute(
            (QUALIFICATION / "SyntheticTransport.lua").read_text("utf-8")
        )
        self.run_lua("""
            local h=Harness.new('selection_absent')
            local sink=Sink.new()
            assert(h:prepare())
            assert(h:process(nil,nil,function(lease) return sink:consume(lease) end).ok)
            local receipt=sink:receipt()
            assert(receipt.reads==1 and receipt.sizeBytes==3)
            assert(receipt.networkCalls==0 and receipt.uploadAcknowledged==false)
            assert(sink:close())
            assert(not sink:consume({read=function() error('closed sink read') end}))
        """)

    def test_target_rejected_without_durable_snapshot_or_render(self):
        self.run_lua("""
            local h=Harness.new('target_rejected')
            exportContext.publishedCollectionInfo.isDefaultCollection=true
            assert(h:prepare()==nil)
            assert(#h:records()==0 and h.files.calls.wait==0)
        """)

    def test_receipts_are_sanitized_terminal_copies_and_cleanup_revokes(self):
        self.run_lua("""
            local h=Harness.new('cleanup_revocation')
            assert(h:prepare())
            assert(h:process().code=='handed_off')
            local receipts=h.fixture:receipts()
            assert(#receipts>=1)
            for _,receipt in ipairs(receipts) do
                assert(receipt.schemaVersion==1)
                assert(receipt.nativeSchedulingProven==false)
                assert(receipt.productionQualified==false)
                assert(receipt.photo==nil and receipt.path==nil and receipt.message==nil)
            end
            receipts[1].code='private detail must not escape'
            assert(h.fixture:receipts()[1].code~='private detail must not escape')
            assert(h.fixture:finish().code=='closed')
            assert(h.fixture:finish().code=='closed')
            local result,reason=h:process()
            assert(result==nil and reason=='fixture_closed')
            assert(h.lease:read()==nil)
            assert(h.files.calls.wait==1 and h.consumed==1)
        """)


if __name__ == "__main__":
    unittest.main()
