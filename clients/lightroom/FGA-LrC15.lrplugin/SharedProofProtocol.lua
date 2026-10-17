-- Copyright 2026 Terry Ott. MIT License.
-- Protocol composition only. GET evidence never qualifies proof POST.
local Module={PRODUCTION_QUALIFIED=false,PROOF_POST_AVAILABLE=false}
local Core=require "ConnectionCore"
local Photo=require "ExistingPhotoClient"
local Read=require "SharedReadTransport"
function Module.new(read,post)
    if type(read)~="table" or type(read.httpGet)~="function" or type(read.retrieve)~="function"
        or type(read.protect)~="function" or type(read.cancelled)~="function" then return nil,"adapter_unavailable" end
    local d={retrieve=read.retrieve,httpGet=read.httpGet,decode=Read.decode,
        encode=Read.encode,jsonNull=Read.jsonNull,cancelled=read.cancelled,
        expectedInstallationId=read.expectedInstallationId}
    -- #0061 must supply its separately reviewed/qualified POST implementation.
    -- No default LrHttp.post, no GET capability fallback, and no POST retries.
    -- Synthetic tests may explicitly inject the same SDK-signature seam.
    function d.httpPost(url,bytes,headers,method,timeout)
        if read.cancelled() or type(post)~="table" or type(post.httpPost)~="function"
            or type(post.capabilities)~="table" or post.capabilities.proofTransport~=true
            or url~=Read.ORIGIN.."/api/v001/existing-public-photo-bindings" or method~="POST"
            or timeout~=Core.TIMEOUT_SECONDS then return nil,{} end
        local body,response=read.protect(function()
            return post.httpPost(url,bytes,headers,method,timeout)
        end)
        if read.cancelled() then return nil,{} end
        -- POST status 201 is a valid new proof, unlike READ status 201.
        if type(response)~="table" or response.status~=201 then return Read.response(body,response,Photo.MAX_RESPONSE_BYTES) end
        local copy={status=200}
        for k,v in pairs(response) do if k~="status" then copy[k]=v end end
        local accepted,safe=Read.response(body,copy,Photo.MAX_RESPONSE_BYTES)
        if accepted then safe.status=201 end
        return accepted,safe
    end
    d.request=Photo.authenticatedRequest(d,Core)
    function d.prove(photoId,linkedRevision) return Photo.prove(d,photoId,linkedRevision) end
    d.capabilities={readTransport=false,proofTransport=false}
    d.PRODUCTION_QUALIFIED=false
    return d
end
return Module
