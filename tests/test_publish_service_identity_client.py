"""Actual Lua 5.1 pure client; synthetic lock/settings/HTTP adapters, no SDK qualification."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class PublishServiceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin").as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.execute((ROOT / "tests/publish_service_identity_fixture.lua").read_text("utf-8"))

    def test_create_save_readback_and_resume_no_reprovision(self):
        self.lua.execute("""
        f=fixture();c=f:client()
        assert(c:verifyService(f.settings).code=='identity_missing' and f.posts==0)
        r=c:configure(f.settings)
        assert(r.ok and f.saved.fgaPublishServiceId==r.identity.fgaPublishServiceId)
        assert(f.saves==1 and f.posts==1 and f.gets==0)
        assert(c:configure(f.settings).ok and c:verifyService(f.settings).ok)
        assert(f.posts==1 and f.gets==2)
        """)

    def test_partial_missing_retained_and_immutable_mismatch_stop(self):
        self.lua.execute("""
        f=fixture();c=f:client();f.saved={fgaPublishServiceId=identity().fgaPublishServiceId}
        assert(c:configure(f.settings).code=='identity_repair_required' and f.posts==0)
        f.saved=nil;f.retained=true
        assert(c:configure(f.settings).code=='identity_repair_required' and f.posts==0)
        f.saved=identity();f.remote=identity();f.remote.linkedFlickrRevision=2
        assert(c:verifyService(f.settings).code=='identity_repair_required' and f.posts==0)
        """)

    def test_link_change_or_read_failure_never_replaces(self):
        self.lua.execute("""
        f=fixture();f.saved=identity();c=f:client()
        for _,status in ipairs({'link_changed','link_unavailable'}) do
         f.linkStatus=status;assert(c:configure(f.settings).code==status)
        end
        f.deps.request=function() return {status=404} end
        assert(c:configure(f.settings).code=='identity_read_failed' and f.posts==0)
        """)

    def test_failed_save_and_lost_response_leave_unused_identity(self):
        self.lua.execute("""
        f=fixture();f.deps.save=function() return false end;c=f:client()
        r=c:configure(f.settings);assert(not r.ok and not r.identity and f.saved==nil)
        assert(r.code=='identity_save_failed' and f.posts==1)
        assert(c:configure(f.settings).code=='identity_save_failed' and f.posts==2)
        f=fixture();local request=f.deps.request
        f.deps.request=function(...) request(...);return nil end;c=f:client()
        assert(c:configure(f.settings).code=='identity_create_failed')
        assert(f.saved==nil and f.saves==0)
        f.deps.request=request;assert(c:configure(f.settings).ok and f.posts==2)
        """)

    def test_readback_mismatch_no_authority_and_concurrent_saved_id_resumes(self):
        self.lua.execute("""
        f=fixture();local save=f.deps.save
        f.deps.save=function(settings,value)
         save(settings,value);f.saved.serviceRevision=2;return true end
        assert(f:client():configure(f.settings).code=='identity_save_failed')
        f=fixture();local request=f.deps.request
        f.deps.request=function(...) local result=request(...)
         f.saved=identity('22222222-2222-4222-8222-222222222222');return result end
        assert(f:client():configure(f.settings).identity.fgaPublishServiceId==f.saved.fgaPublishServiceId)
        assert(f.posts==1 and f.gets==1 and f.saves==0)
        """)

    def test_malformed_success_and_unknown_retained_status_fail_closed(self):
        self.lua.execute("""
        f=fixture();local request=f.deps.request
        f.deps.request=function(...)
         local result=request(...);result.body.extra=true;return result end
        assert(f:client():configure(f.settings).code=='identity_create_failed' and f.saves==0)
        f=fixture();f.deps.hasRetainedRecords=function() return nil end
        assert(f:client():configure(f.settings).code=='identity_repair_required' and f.posts==0)
        """)


if __name__ == "__main__":
    unittest.main()
