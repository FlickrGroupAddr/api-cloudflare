-- Copyright 2026 Terry Ott. MIT License.
-- Disabled SDK composition. No registration or native transport qualification.
local Factory = {PRODUCTION_QUALIFIED=false, COUNTER_FIELD="groupHandoffSequenceV1"}
local Core = require "ConnectionCore"
local Photo = require "ExistingPhotoClient"
local json = require "dkjson"
local owned = setmetatable({}, {__mode="k"})
local MAX = 9007199254740991
local function integer(v,minimum)
    return type(v)=="number" and v>=minimum and v<=MAX and v==math.floor(v)
end
local function decode(bytes)
    local value,position,err=json.decode(bytes,1,json.null)
    if err or type(position)~="number" or bytes:sub(position):find("%S") then return nil end
    return value
end
local function unavailable() return nil,"qualification_required" end

-- Only start() owns a POST-capable documented SDK task context.
function Factory.new(context,options)
    local owner=owned[context]
    if not owner or owner.closed then return unavailable() end
    options=options or {}
    local transport=options.transport
    if type(transport)~="table" or type(transport.capabilities)~="table" then return unavailable() end
    for _,key in ipairs({"thumbnailTransport","readTransport","proofTransport","batchTransport"}) do
        if transport.capabilities[key]~=true then return unavailable() end
    end
    for _,key in ipairs({"httpGet","httpPost","batchPost"}) do
        if type(transport[key])~="function" then return unavailable() end
    end
    local Tasks=import "LrTasks"
    local Application=import "LrApplication"
    local Passwords=import "LrPasswords"
    local Date=import "LrDate"
    local catalog,plugin=Application.activeCatalog(),_PLUGIN
    if not catalog or not plugin then return unavailable() end
    local function retrieve(key) return Passwords.retrieve(key,nil,Core.PLUGIN_ID) end
    local credential=retrieve(Core.CURRENT_KEY)
    local session
    context:addCleanupHandler(function() credential=nil; session=nil end)
    local function unchanged()
        if owner.closed or owner.cancelled or owner.progress:isCanceled()
            or Application.activeCatalog()~=catalog then return false end
        local ok,current,candidate=Tasks.pcall(function()
            return retrieve(Core.CURRENT_KEY),retrieve(Core.CANDIDATE_KEY)
        end)
        return ok and Core.isCanonicalCredential(credential) and current==credential
            and (candidate==nil or candidate=="")
    end
    local function check() if not unchanged() then error("workflow_context_changed") end end
    local function guarded(fn)
        return function(...)
            check()
            local a,b=fn(...)
            check()
            return a,b
        end
    end
    local get,post,batch=guarded(transport.httpGet),guarded(transport.httpPost),guarded(transport.batchPost)
    local rawGet=get
    get=function(...)
        local bytes,headers=rawGet(...)
        if session and type(bytes)=="string" then
            local value=decode(bytes)
            if type(value)=="table" and value.linkedFlickrRevision~=nil
                and value.linkedFlickrRevision~=session.linkedFlickrRevision then
                owner.cancelled=true
                error("workflow_identity_changed")
            end
        end
        return bytes,headers
    end
    check()
    local verified=Core.verifyStored(retrieve,get,decode,options.expectedInstallationId)
    if verified.state~="connected" then return nil,"identity_unavailable" end
    check()
    local protocol={retrieve=retrieve,httpGet=get,httpPost=post,decode=decode,encode=json.encode,
        jsonNull=json.null,expectedInstallationId=verified.installationId,
        cancelled=function() return not unchanged() end}
    protocol.request=guarded(Photo.authenticatedRequest(protocol,Core))
    -- An authenticated, validated empty discovery page still supplies link identity.
    local page=Photo.discover(protocol,1,Photo.PAGE_SIZE)
    check()
    if not page then return nil,"identity_unavailable" end
    session={installationId=verified.installationId,linkedFlickrRevision=page.linkedFlickrRevision}
    local function currentIdentity()
        -- Synchronous local session read, safe inside the private catalog gate.
        if not unchanged() then return nil end
        return {installationId=session.installationId,linkedFlickrRevision=session.linkedFlickrRevision}
    end
    local d={catalog=catalog,plugin=plugin,call=Tasks.pcall,retrieve=guarded(retrieve),
        activeCatalog=Application.activeCatalog,currentIdentity=currentIdentity,
        httpGet=get,httpPost=post,batchPost=batch,decode=decode,encode=json.encode,jsonNull=json.null,
        batchClient=require "GroupSubmissionClient",cancelled=function() return not unchanged() end,
        -- SDK15.3 documents wall time. Backend proof-age enforcement is authoritative.
        now=function() check(); return Date.currentTime() end,
        capabilities={hostTask=true,thumbnailTransport=true,readTransport=true,proofTransport=true,
            batchTransport=true,catalogOutbox=true,currentIdentity=true,credentialBoundary=true}}
    function d.cancel() owner.cancelled=true end
    function d.sleep(seconds)
        if type(seconds)~="number" or seconds~=seconds or seconds<0 or seconds==math.huge then
            error("invalid_sleep")
        end
        check()
        while seconds>0 do
            local slice=math.min(seconds,0.1)
            Tasks.sleep(slice)
            check()
            seconds=seconds-slice
        end
    end
    function d.newHandoffId()
        check()
        local completed,expected
        local open=true
        local ok,gate=Tasks.pcall(function()
            return catalog:withPrivateWriteAccessDo(function()
                if not open then error("write_unconfirmed") end
                check()
                local prior=catalog:getPropertyForPlugin(plugin,Factory.COUNTER_FIELD)
                if prior==nil then prior="0" end
                if type(prior)~="string" or not prior:match("^%d+$") then error("counter_invalid") end
                local number=tonumber(prior)
                if not integer(number,0) or string.format("%.0f",number)~=prior or number==MAX then
                    error("counter_invalid")
                end
                expected=string.format("%.0f",number+1)
                catalog:setPropertyForPlugin(plugin,Factory.COUNTER_FIELD,expected)
                completed=true
            end,{timeout=5,asynchronous=false})
        end)
        open=false
        check()
        if not ok or gate~="executed" or not completed
            or catalog:getPropertyForPlugin(plugin,Factory.COUNTER_FIELD)~=expected then
            error("write_unconfirmed")
        end
        return "sdk-handoff-v1-"..expected
    end
    function d.newStore()
        check()
        return require("ExistingPhotoGroupStore").new{catalog=catalog,plugin=plugin,
            pcall=Tasks.pcall,activeCatalog=Application.activeCatalog,currentIdentity=currentIdentity,
            workflow="existing_public_photo"}
    end
    return d
end

-- Callers supply qualified transports; absent capability fails before credentials/I/O.
-- A consumer runs synchronously within this owning context and may yield.
function Factory.start(options,consumer,finished)
    if type(consumer)~="function" then return false end
    local Context=import "LrFunctionContext"
    local Tasks=import "LrTasks"
    local Progress=import "LrProgressScope"
    Context.postAsyncTaskWithContext("FGA group workflow",function(context)
        local owner={closed=false,cancelled=false}
        owned[context]=owner
        context:addCleanupHandler(function()
            owner.cancelled=true
            owner.closed=true
            owned[context]=nil
        end)
        local ok,result=Tasks.pcall(function()
            owner.progress=Progress{title="FGA group workflow"}
            owner.progress:attachToFunctionContext(context)
            owner.progress:setCancelable(true)
            local d,reason=Factory.new(context,options)
            if not d then return {state=reason} end
            return consumer(context,d)
        end)
        -- Cancel before SDK cleanup releases dialogs/cache/progress resources.
        owner.cancelled=true
        owner.closed=true
        owned[context]=nil
        if type(finished)=="function" then
            finished(ok and result or {state="unavailable"})
        end
    end)
    return true
end
return Factory
