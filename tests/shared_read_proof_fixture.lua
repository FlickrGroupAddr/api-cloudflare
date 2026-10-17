-- Synthetic only: actual shared modules and existing protocol cores under Lua5.1.
package.path=bundle.."/?.lua;"..package.path
Read=require "SharedReadTransport"
Proof=require "SharedProofProtocol"
Core=require "ConnectionCore"
Photo=require "ExistingPhotoClient"
Groups=require("GroupDiscoveryClient").new(Core)
Status=require "SubmissionStatusClient"
json=require "dkjson"
credential=string.rep("0000-",12).."0000"
current,candidate,context,cancelled,clock=credential,nil,true,false,0
reads,gets,posts=0,0,0
responses={}
function response(bytes,status)
    return {bytes,{status=status or 200,{field="Content-Type",value="application/json"},
        {field="Cache-Control",value="no-store"}}}
end
installation=json.encode{schemaVersion=1,installationId="install",installationRevision=1,
    installationState="active",presentedCredentialState="current"}
page=json.encode{schemaVersion=1,linkedFlickrRevision=2,observedAt="2026-10-17T12:00:00Z",
    page=1,pageSize=5,pages=0,total=0,photos=setmetatable({},{__jsontype="array"})}
binding={schemaVersion=1,fgaPhotoBindingId="binding",sourceKind="existing_public_flickr_photo",
    flickrPhotoId="photo",linkedFlickrRevision=2,verificationRevision=3,verifiedAt="2026-10-17T12:00:00Z"}
function mockGet(url,headers,timeout)
    gets=gets+1
    assert(url:sub(1,#Read.ORIGIN)==Read.ORIGIN and timeout==30)
    assert(#headers==1 and headers[1].value=="Bearer "..credential)
    if afterGet then afterGet() end
    if failGet then error("private exception secret") end
    if yieldGet then coroutine.yield("network") end
    local result=responses[url] or response(url==Core.CURRENT_URL and installation or page)
    return unpack(result)
end
function makeRead(call)
    return assert(Read.offline{get=mockGet,call=call or pcall,
        retrieve=function(key) reads=reads+1; return key==Core.CURRENT_KEY and current or candidate end,
        current=function() return context end,cancelled=function() return cancelled end,
        now=function() return clock end,expectedInstallationId="install"})
end
read=makeRead()
protocol=assert(Proof.new(read))
headers={{field="Authorization",value="Bearer "..credential}}
url=Read.ORIGIN.."/api/v001/existing-public-photos?page=1&page_size=5"
function get() return read.httpGet(url,headers,30) end
function syntheticPost(url,bytes,requestHeaders,method,timeout)
    posts=posts+1
    assert(url==Read.ORIGIN.."/api/v001/existing-public-photo-bindings" and method=="POST" and timeout==30)
    assert(requestHeaders[1].value=="Bearer "..credential)
    assert(bytes:find('"expectedLinkedFlickrRevision":2',1,true))
    if postHook then postHook() end
    return json.encode(binding),response("",201)[2]
end
