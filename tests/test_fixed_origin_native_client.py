"""Offline Lua 5.1 source checks; never invoke Lightroom or a network."""

from __future__ import annotations

import struct
import unittest
import zlib
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "probes/lightroom/FGA-FixedOrigin-v1.lrplugin"
RELEASE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


def png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x80"))
        + chunk(b"IEND", b"")
    )


class FixedOriginNativeClientTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True, encoding=None)
        self.lua.globals().probe = str(PROBE).replace("\\", "/").encode()
        self.lua.globals().release = str(RELEASE).replace("\\", "/").encode()
        self.lua.globals().png = png()
        self.lua.execute(b"""
package.path=release..'/?.lua;'..package.path
C=dofile(probe..'/Config.lua');Q=dofile(probe..'/Qualification.lua')
Client=require 'ExistingPhotoClient';Read=require 'SharedReadTransport'
Core=require 'ConnectionCore'
json=require 'dkjson'
config={schemaVersion=1,version=C.VERSION,run=string.rep('a',32),capability=string.rep('b',64),
    case='ok',mode='browser',startsAt=1,expiresAt=601,sources={},
    workerSha256=string.rep('c',64),configurationSha256=string.rep('d',64)}
for _,key in ipairs(C.SOURCES) do config.sources[key]=string.rep('e',64) end
clock=10;stopped=false;calls=0
d={now=function() return clock end,cancelled=function() return stopped end,
    get=function(url,headers,timeout)
        calls=calls+1
        assert(url==C.ORIGIN..'/api/v001/installations/current')
        assert(#headers==3 and headers[1].value=='FGA-Qualification '..config.capability)
        assert(headers[2].value==config.run and headers[3].value=='ok' and timeout==30)
        if yielding then coroutine.yield('network') end
        return 'body',{status=200}
    end}
get=Q.translate(C,config,d)
headers={{field='Authorization',value='Bearer '..C.CREDENTIAL}}
url=C.ORIGIN..'/api/v001/installations/current'
function receipt() return {completePages=0,pictureControls=0,observerConfirmedPages=0,
    staleResultsDiscarded=0,navigation=0} end
function page(n)
    local photos={}
    for i=(n==1 and 1 or 3),(n==1 and 2 or 3) do
        photos[#photos+1]={flickrPhotoId='photo'..i,title='Synthetic '..i,dateUploaded='1770000000',
            dateTaken='2026-02-01 14:30:00',thumbnail={sizeClass='q',
            url='https://live.staticflickr.com/1/photo'..i..'_key_q.png'}}
    end
    return json.encode{schemaVersion=1,linkedFlickrRevision=1,observedAt='2026-10-17T12:00:00Z',
        page=n,pageSize=2,pages=2,total=3,photos=photos}
end
function harness()
    local staged,shown,requests,clears={},{},0,0
    local protocol={decode=Read.decode,cancelled=function() return stopped end}
    protocol.request=function(method,path)
        assert(method=='GET');requests=requests+1
        if path:find('/thumbnail?',1,true) then
            if cancelAt and requests==cancelAt then stopped=true end
            return png,{status=200,{field='Content-Type',value='image/png'},
                {field='Cache-Control',value='private, no-store'}}
        end
        local n=tonumber(path:match('page=(%d)&page_size=2$'));assert(n)
        return page(n),{status=200}
    end
    return {protocol=protocol,cancelled=function() return stopped end,
        stage=function(index,bytes,media)
            assert(bytes==png and media=='image/png');staged[#staged+1]=index;return 'owned-'..index
        end,
        clearPage=function() clears=clears+1;return true end,
        show=function(value,rows)
            assert(#rows==#value.photos);shown[#shown+1]=value.page
            if #shown==1 then return 'next',true elseif #shown==2 then return 'previous',true end
            return 'cancel',false
        end,
        counts=function() return #staged,#shown,requests,clears end}
end
""")

    def test_exact_translation_refuses_credential_origin_path_and_timeout_changes(self):
        self.lua.execute(b"""
assert(C.validate(config,clock));assert(get(url,headers,30)=='body' and calls==1)
assert(get('https://evil.test'..url,headers,30)==nil)
assert(get(url..'?',headers,30)==nil);assert(get(url,headers,15)==nil)
assert(get(url,{{field='Authorization',value='Bearer actual-token'}},30)==nil)
headers.extra=true;assert(get(url,headers,30)==nil);headers.extra=nil
config.extra=true;assert(get(url,headers,30)==nil);config.extra=nil
clock=601;assert(get(url,headers,30)==nil);assert(calls==1)
""")

    def test_cooperative_cancel_discards_a_yielded_response(self):
        self.lua.execute(b"""
yielding=true
local co=coroutine.create(function() return get(url,headers,30) end)
local ok,value=coroutine.resume(co);assert(ok and value=='network')
stopped=true
ok,value=coroutine.resume(co);assert(ok and value==nil and calls==1)
""")

    def test_complete_pages_navigation_and_bounded_controls(self):
        self.lua.execute(b"""
local d=harness();local s=receipt();Q.execute(config,d,Client,s)
local staged,shown,requests,clears=d.counts()
assert(staged==5 and shown==3 and requests==8 and clears==3)
assert(s.completePages==3 and s.pictureControls==5 and s.navigation==2)
assert(s.observerConfirmedPages==2 and s.reason=='cancelled')
""")

    def test_cancelled_page_and_stale_response_never_render(self):
        self.lua.execute(b"""
cancelAt=3;local d=harness();local s=receipt();Q.execute(config,d,Client,s)
local staged,shown=d.counts();assert(staged==1 and shown==0)
assert(s.reason=='cancelled' and s.pictureControls==0)
stopped=false;cancelAt=nil;config.mode='stale';d=harness();s=receipt();Q.execute(config,d,Client,s)
staged,shown=d.counts();assert(staged==0 and shown==0)
assert(s.reason=='stale_discarded' and s.staleResultsDiscarded==1)
""")

    def test_source_info_and_run_parse_without_invocation(self):
        self.lua.execute(b"""
assert(loadfile(probe..'/Run.lua'));local info=dofile(probe..'/Info.lua')
assert(info.LrToolkitIdentifier=='com.sixbuckssolutions.fga.fixedorigin.v1.lrc15')
assert(Q.PRODUCTION_QUALIFIED==false and Read.PRODUCTION_QUALIFIED==false)
""")

    def test_real_qualification_adapter_reuses_release_authentication_and_parsing(self):
        self.lua.execute(b"""
local native=0
local nativeGet=function(requestUrl,requestHeaders,timeout)
    native=native+1
    assert(requestHeaders[1].value=='FGA-Qualification '..config.capability)
    assert(requestHeaders[2].value==config.run and requestHeaders[3].value=='ok')
    if requestUrl==Core.CURRENT_URL then
        return json.encode{schemaVersion=1,installationId=C.installation('ok'),
            installationRevision=1,installationState='active',presentedCredentialState='current'},
            {status=200,{field='Content-Type',value='application/json'},
                {field='Cache-Control',value='no-store'}}
    elseif requestUrl==C.ORIGIN..'/api/v001/existing-public-photos?page=1&page_size=2' then
        return page(1),{status=200,{field='Content-Type',value='application/json'},
            {field='Cache-Control',value='no-store'}}
    end
    assert(requestUrl==C.ORIGIN..
        '/api/v001/existing-public-photos/photo1/thumbnail?page=1&page_size=2&linked_flickr_revision=1')
    assert(timeout==15)
    return png,{status=200,{field='Content-Type',value='image/png'},
        {field='Cache-Control',value='private, no-store'},
        {field='Content-Length',value=tostring(#png)}}
end
local protocol=assert(Q.dependencies(C,config,{now=function() return clock end,
    cancelled=function() return stopped end,current=function() return true end,
    call=pcall,get=nativeGet},Read,Core,Client))
local observed=assert(Client.discover(protocol,1,2));assert(#observed.photos==2)
assert(Client.thumbnail(protocol,observed.photos[1],observed)==png and native==4)
protocol.close();assert(Client.discover(protocol,1,2)==nil and native==4)
assert(Read.PRODUCTION_QUALIFIED==false)
""")

    def test_every_fault_reaches_only_its_thumbnail_after_png_preflight(self):
        self.lua.execute(b"""
config.mode='fault'
for selected in pairs(C.CASES) do
    config.case=selected
    local preflights,stimuli=0,0
    local protocol=assert(Q.dependencies(C,config,{now=function() return clock end,
        cancelled=function() return false end,current=function() return true end,call=pcall,
        get=function(requestUrl,requestHeaders,timeout)
            local path=requestUrl:sub(#C.ORIGIN+1)
            local scenario=requestHeaders[3].value
            if path==C.FAULT_THUMBNAIL then
                assert(scenario==selected and timeout==15);stimuli=stimuli+1
                return png,{status=200,{field='Content-Type',value='image/png'},
                    {field='Cache-Control',value='no-store'}}
            end
            -- Reproduce wrapper authority: a fault selector on preflight would
            -- fail before the thumbnail. Verify the real client uses PNG here.
            assert(scenario=='png' and timeout==30);preflights=preflights+1
            local value
            if path=='/api/v001/installations/current' then
                value={schemaVersion=1,installationId='qualification-png-install',
                    installationRevision=1,installationState='active',presentedCredentialState='current'}
            else
                assert(path=='/api/v001/existing-public-photos?page=1&page_size=1')
                value={schemaVersion=1,linkedFlickrRevision=1,observedAt='2026-10-17T12:00:00Z',
                    page=1,pageSize=1,pages=1,total=1,photos={{flickrPhotoId='photo',title='Synthetic',
                    dateUploaded='1770000000',dateTaken='2026-02-01 14:30:00',
                    thumbnail={sizeClass='q',url='https://live.staticflickr.com/1/photo_key_q.png'}}}}
            end
            return json.encode(value),{status=200,{field='Content-Type',value='application/json'},
                {field='Cache-Control',value='no-store'}}
        end},Read,Core,Client))
    local state=receipt()
    Q.execute(config,{protocol=protocol,cancelled=function() return false end},Client,state)
    assert(preflights==3 and stimuli==1 and state.thumbnailAccepted==true)
    assert(C.requestCase(config,'/api/v001/existing-public-photos?page=1&page_size=2')==nil)
    protocol.close()
end
""")


if __name__ == "__main__":
    unittest.main()
