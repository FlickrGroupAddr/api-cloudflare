"""Offline policy boundaries for the actual fixed-origin qualification seam."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
PROBE = ROOT / "probes/lightroom/FGA-FixedOrigin-v1.lrplugin"


class SharedReadQualificationTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.globals().probe = PROBE.as_posix()
        self.lua.execute("""
package.path=bundle..'/?.lua;'..package.path
Read=require 'SharedReadTransport';Core=require 'ConnectionCore'
C=dofile(probe..'/Config.lua')
credential=C.CREDENTIAL;candidate=nil;current=true;cancelled=false;clock=0;gets=0;reads=0
body='{}';metadata={status=200,{field='Content-Type',value='application/json'},
    {field='Cache-Control',value='no-store'}}
function make(call)
    return assert(Read.qualification{call=call or pcall,
        get=function(url,headers,timeout)
            gets=gets+1;lastTimeout=timeout
            assert(headers[1].value=='Bearer '..C.CREDENTIAL)
            if hook then hook() end
            if yielding then coroutine.yield('get') end
            return body,metadata
        end,
        retrieve=function(key)
            reads=reads+1
            if key==Core.CURRENT_KEY then return credential else return candidate end
        end,
        current=function() return current end,cancelled=function() return cancelled end,
        now=function() return clock end,expectedInstallationId='synthetic'})
end
adapter=make();headers={{field='Authorization',value='Bearer '..C.CREDENTIAL}}
image='/api/v001/existing-public-photos/photo1/thumbnail?page=1&page_size=2&linked_flickr_revision=1'
function imageResponse()
    body='image';metadata={status=200,{field='Content-Type',value='image/png'},
        {field='Cache-Control',value='no-store'}}
end
function get(path,timeout) return adapter.httpGet(Read.ORIGIN..path,headers,timeout) end
""")

    def test_finite_fixture_surface_and_production_refusal(self):
        self.lua.execute("""
local count=0
for path,timeout in pairs(C.PATHS) do
    if timeout==15 then imageResponse() else
        body='{}';metadata[1].value='application/json'
    end
    assert(get(path,timeout)==body and lastTimeout==timeout);count=count+1
end
assert(count==8 and gets==8)
assert(Read.new()==nil and Read.PRODUCTION_QUALIFIED==false)
for _,value in pairs(adapter.capabilities) do assert(value==false) end
assert(adapter.PRODUCTION_QUALIFIED==false)
""")

    def test_rejects_nonfixture_destinations_before_credential_or_network(self):
        for path in (
            "/api/v001/groups?page_size=100",
            "/api/v001/existing-public-photos?page=1&page_size=5",
            "/api/v001/existing-public-photos?page=3&page_size=2",
            "/api/v001/existing-public-photos/photo4/thumbnail?page=1&page_size=2&linked_flickr_revision=1",
            "/api/v001/existing-public-photos/photo1/thumbnail?page=1&page_size=2&linked_flickr_revision=2",
            "/api/v001/installations/current?x=1",
            "/api/v001/installations/current#fragment",
        ):
            with self.subTest(path=path):
                self.lua.globals().path = path
                self.lua.execute("assert(get(path,30)==nil and reads==0 and gets==0)")
        self.lua.execute("""
assert(adapter.httpGet('https://flickrgroupaddr.com.evil.test'..image,headers,15)==nil)
assert(get(image,30)==nil and reads==0 and gets==0)
""")

    def test_only_pinned_synthetic_credential_can_enter_qualification(self):
        self.lua.execute("""
credential=string.rep('0000-',12)..'0010'
assert(Core.isCanonicalCredential(credential))
assert(get('/api/v001/installations/current',30)==nil and gets==0)
credential=C.CREDENTIAL;assert(get('/api/v001/installations/current',30)==nil)
""")

    def test_image_response_gate_sanitizes_and_bounds_returned_bytes(self):
        self.lua.execute("""
imageResponse();body=string.rep('x',262144)
metadata[#metadata+1]={field='X-Private',value='private'}
local bytes,safe=get(image,15)
assert(bytes==body and #safe==2 and safe.error==nil)
body=body..'x';local rejected,h=get(image,15);assert(rejected==nil and next(h)==nil)
""")
        for mutation in (
            "metadata.status=302",
            "metadata.error={errorMessage='private'}",
            "metadata[1].value='application/json'",
            "metadata[2].value='private'",
            "metadata[3]={field='Location',value='https://evil.test/'}",
            "metadata[3]={field='Content-Length',value='7'}",
            "metadata[3]={field='Content-Type',value='image/png'}",
        ):
            with self.subTest(mutation=mutation):
                self.lua.execute("imageResponse();" + mutation + ";assert(get(image,15)==nil)")

    def test_json_retains_actual_strict_decoder_and_offline_excludes_images(self):
        self.lua.execute("""
body='{"duplicate":1,"duplicate":2}'
assert(get('/api/v001/installations/current',30)==nil)
assert(not Read.allowedPath(image))
""")

    def test_post_get_context_credential_and_elapsed_time_fences(self):
        for mutation in (
            "cancelled=true",
            "current=false",
            "candidate='rotation'",
            "credential=string.rep('0000-',12)..'0010'",
            "clock=15",
            "clock=-1",
            "clock=0/0",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("imageResponse();hook=function() " + mutation + " end")
                self.lua.execute(
                    "local b,h=get(image,15);assert(b==nil and next(h)==nil and gets==1)"
                )

    def test_yield_safe_call_allows_get_and_discards_cancelled_result(self):
        self.lua.execute("""
local function protect(fn)
    local co=coroutine.create(fn)
    local result={coroutine.resume(co)}
    while result[1] and coroutine.status(co)~='dead' do
        coroutine.yield(result[2]);result={coroutine.resume(co)}
    end
    return unpack(result)
end
adapter=make(protect);imageResponse();yielding=true
local co=coroutine.create(function() return get(image,15) end)
local ok,value=coroutine.resume(co);assert(ok and value=='get')
cancelled=true;ok,value=coroutine.resume(co)
assert(ok and value==nil and coroutine.status(co)=='dead')
""")


if __name__ == "__main__":
    unittest.main()
