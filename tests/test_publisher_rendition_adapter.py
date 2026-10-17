"""Exercise actual rendition/preflight integration with synthetic SDK boundaries only."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "clients/lightroom/publisher"


class PublisherRenditionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.lua.globals().source = SOURCE.as_posix()
        self.lua.execute('package.path=source.."/?.lua;"..package.path')
        self.lua.globals().Fixture = self.lua.execute(
            (ROOT / "tests/publisher_rendition_adapter_fixture.lua").read_text("utf-8")
        )
        self.lua.execute("""
            Adapter=require 'RenditionAdapter'
            Policy=require 'RenditionPolicy'
            f=Fixture.new()
            adapter=Adapter.new(f.deps)
            f:file('synthetic-path','png')
            item=f:rendition('synthetic-path')
            function consume(lease,context,config) return f:consume(lease,context,config) end
        """)

    def test_default_and_deliberate_alternate_use_sourced_policy(self):
        self.lua.execute("""
            local config=assert(Policy.resolve({}))
            assert(config.format=='PNG')
            assert(config.exportSettings.LR_export_bitDepth==8)
            assert(config.exportSettings.LR_export_colorSpace=='sRGB')
            assert(config.exportSettings.LR_size_doConstrain==false)
            assert(config.sourceUrl:match('^https://www%.flickrhelp%.com/'))
            assert(config.retrievedOn=='2026-10-17' and type(config.policyId)=='string')
            assert(config.byteConvention=='conservative_decimal_engineering_ceiling')
            local result=adapter:process(item,{},f.context,consume)
            assert(result.ok and result.code=='handed_off')
            assert(f.calls.wait==1 and f.calls.consume==1)
            assert(f.events[1]=='wait')
            assert(f.bytes=='png' and f.config.maximumBytes==config.maximumBytes)
            assert(f.config.policyId==config.policyId and f.config.sourceUrl==config.sourceUrl)
            local bytes,reason=f.lease:read()
            assert(bytes==nil and reason=='lease_expired')
            local settings={LR_format='JPEG',LR_jpeg_quality=0.8}
            local alternate=assert(Policy.resolve(settings))
            assert(alternate.format=='JPEG' and alternate.exportSettings.LR_jpeg_quality==0.8)
            assert(adapter:process(f:rendition('synthetic-path'),settings,f.context,consume).ok)
            assert(settings.LR_format=='JPEG' and settings.LR_jpeg_quality==0.8)
        """)

    def test_policy_and_missing_prepared_context_refuse_wait_or_consume(self):
        self.lua.execute("""
            local result=adapter:process(item,{LR_format='TIFF'},f.context,consume)
            assert(not result.ok and f.calls.wait==0
                and f.calls.consume==0)
            result=adapter:process(f:rendition('synthetic-path'),{},nil,consume)
            assert(result.code=='context_required' and f.calls.wait==0 and f.calls.consume==0)
            result=adapter:process(f:rendition('synthetic-path'),{},false,consume)
            assert(result.code=='context_required' and f.calls.wait==0 and f.calls.consume==0)
        """)

    def test_failed_render_and_preflight_cannot_reach_authorization_consumer(self):
        self.lua.execute("""
            local failed=adapter:process(
                f:rendition('private-render-detail',false),{},f.context,consume)
            assert(failed.code=='render_failed' and f.calls.inspect==0)
            f.waitThrows=true
            assert(adapter:process(f:rendition('private'),{},f.context,consume).code=='render_failed')
            f.waitThrows=false
            local limit=assert(Policy.resolve({})).maximumBytes
            f.files.oversized={kind='file',size=limit+1,contents='never read'}
            local result=adapter:process(f:rendition('oversized'),{},f.context,consume)
            assert(result.code=='oversized' and result.sizeBytes==limit+1)
            assert(result.maximumBytes==limit and f.calls.read==0 and f.calls.consume==0)
            assert(adapter:process(f:rendition('missing'),{},f.context,consume).code=='missing_file')
            assert(f.calls.consume==0)
        """)

    def test_file_ownership_revalidation_detects_mutation_before_handoff(self):
        for mutation in (
            "f.files['synthetic-path'].contents='jpg'",
            "f.files['synthetic-path'].size=4; f.files['synthetic-path'].contents='pngx'",
            "f.files['synthetic-path']=nil",
            "f.files['synthetic-path'].unreadable=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("""
                    result=adapter:process(item,{},f.context,function(lease,context,config)
                        f.lease=lease
                """ + mutation + """
                        local bytes,reason=lease:read()
                        assert(bytes==nil and type(reason)=='string')
                        f.reason=reason
                        return false
                    end)
                    assert(not result.ok)
                    local bytes,reason=f.lease:read()
                    assert(bytes==nil and reason=='lease_expired')
                """)
                self.assertIn(
                    self.lua.globals().f["reason"],
                    ("file_changed", "missing_file", "unreadable_file"),
                )

    def test_callback_cannot_handoff_without_read_and_lease_expires_after_exception(self):
        self.lua.execute("""
            local result=adapter:process(item,{},f.context,function() return true end)
            assert(not result.ok and result.code=='file_not_read')
            result=adapter:process(f:rendition('synthetic-path'),{},f.context,function(lease)
                f.lease=lease; assert(lease:read()=='png')
                error('private consumer detail')
            end)
            assert(result.code=='handoff_failed')
            local bytes,reason=f.lease:read()
            assert(bytes==nil and reason=='lease_expired')
        """)

    def test_cancellation_and_stale_context_before_and_during_handoff(self):
        for field, expected in (("cancelled", "cancelled"), ("current", "context_stale")):
            with self.subTest(field=field):
                self.setUp()
                value = "true" if field == "cancelled" else "false"
                self.lua.execute(f"""
                    f.{field}={value}
                    local result=adapter:process(item,{{}},f.context,consume)
                    assert(result.code=='{expected}' and f.calls.wait==0 and f.calls.consume==0)
                """)
                self.setUp()
                self.lua.execute(f"""
                    local result=adapter:process(item,{{}},f.context,function(lease)
                        f.{field}={value}
                        local bytes,reason=lease:read()
                        assert(bytes==nil and reason=='{expected}')
                        return true
                    end)
                    assert(not result.ok and result.code=='{expected}')
                """)

    def test_wait_time_cancellation_or_context_change_prevents_consumer(self):
        for mutation, expected in (
            ("f.cancelled=true", "cancelled"),
            ("f.current=false", "context_stale"),
        ):
            with self.subTest(expected=expected):
                self.setUp()
                self.lua.execute(f"""
                    f.onWait=function() {mutation} end
                    local result=adapter:process(item,{{}},f.context,consume)
                    assert(result.code=='{expected}' and f.calls.consume==0)
                """)

    def test_one_truthful_outcome_per_photo_and_no_reprocessing(self):
        self.lua.execute("""
            local bad=f:rendition('missing')
            local a=adapter:process(bad,{},f.context,consume)
            local b=adapter:process(item,{},f.context,consume)
            local c=adapter:process(f:rendition('synthetic-path'),{},f.context,consume)
            assert(a.code=='missing_file' and b.code=='handed_off' and c.code=='handed_off')
            assert(f.calls.wait==3 and f.calls.consume==2)
            local duplicate=adapter:process(item,{},f.context,consume)
            assert(duplicate.code=='duplicate_rendition')
            assert(f.calls.wait==3 and f.calls.consume==2)
            for key in pairs(b) do
                assert(key=='ok' or key=='code' or key=='sizeBytes' or key=='maximumBytes')
            end
        """)


if __name__ == "__main__":
    unittest.main()
