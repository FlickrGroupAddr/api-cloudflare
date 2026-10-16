-- Copyright 2026 Terry Ott. MIT License.
-- Unregistered composition candidate. The caller owns a documented SDK task/context.
local W = {PRODUCTION_QUALIFIED=false}
local active=false
local requiredCapabilities={"hostTask","thumbnailTransport","readTransport","proofTransport",
    "batchTransport","catalogOutbox","currentIdentity","credentialBoundary"}
local requiredFunctions={"call","retrieve","httpGet","httpPost","batchPost","decode","encode",
    "sleep","cancelled","now","newHandoffId","currentIdentity","activeCatalog"}
local function validIdentity(v)
    if type(v)~="table" or type(v.installationId)~="string" or #v.installationId<1
        or #v.installationId>128 or not v.installationId:match("^[A-Za-z0-9][A-Za-z0-9@._:%-]*$")
        or type(v.linkedFlickrRevision)~="number" or v.linkedFlickrRevision<1
        or v.linkedFlickrRevision>9007199254740991
        or v.linkedFlickrRevision~=math.floor(v.linkedFlickrRevision) then return false end
    local count=0
    for key in pairs(v) do
        if key~="installationId" and key~="linkedFlickrRevision" then return false end
        count=count+1
    end
    return count==2
end
local function qualified(d)
    if type(d)~="table" or type(d.capabilities)~="table" or d.jsonNull==nil
        or d.catalog==nil or d.plugin==nil or type(d.batchClient)~="table"
        or type(d.batchClient.submit)~="function" then return false end
    for _,key in ipairs(requiredCapabilities) do if d.capabilities[key]~=true then return false end end
    for _,key in ipairs(requiredFunctions) do if type(d[key])~="function" then return false end end
    return true
end
local function run(context,d)
    local Core=require "ConnectionCore"
    local Photo=require "ExistingPhotoClient"
    local Browser=require "ExistingPhotoBrowser"
    local Discovery=require "GroupDiscoveryClient"
    local Status=require "SubmissionStatusClient"
    local Eligibility=require "GroupSelectionEligibility"
    local Store=require "ExistingPhotoGroupStore"
    local Controller=require "GroupSelectionController"
    local Dialog=require "GroupSelectionDialog"
    local identity=d.currentIdentity()
    if not validIdentity(identity) then return {state="unavailable"} end
    -- Copy the exact installation/link context before any yielding operation.
    local installationId,linkedRevision=identity.installationId,identity.linkedFlickrRevision
    local credential=d.retrieve(Core.CURRENT_KEY)
    if not Core.isCanonicalCredential(credential) then return {state="unavailable"} end
    local function unchanged()
        if d.cancelled() or d.activeCatalog()~=d.catalog then return false end
        local current=d.currentIdentity()
        local candidate=d.retrieve(Core.CANDIDATE_KEY)
        return validIdentity(current) and current.installationId==installationId
            and current.linkedFlickrRevision==linkedRevision
            and (candidate==nil or candidate=="") and d.retrieve(Core.CURRENT_KEY)==credential
    end
    local function guard(fn)
        return function(...)
            if not unchanged() then error("workflow_context_changed") end
            local a,b=fn(...)
            if not unchanged() then error("workflow_context_changed") end
            return a,b
        end
    end
    if not unchanged() then return {state="unavailable"} end
    local protocol={retrieve=d.retrieve,httpGet=guard(d.httpGet),httpPost=guard(d.httpPost),
        expectedInstallationId=installationId,decode=d.decode,encode=d.encode,
        jsonNull=d.jsonNull,cancelled=function() return not unchanged() end,
        thumbnailTransportQualified=true}
    protocol.request=guard(Photo.authenticatedRequest(protocol,Core))
    local binding,membership=Browser.run(context,protocol)
    if not binding then return {state=membership=="cancelled" and "cancelled" or "unavailable"} end
    if not unchanged() or not Photo.validateBinding(binding,binding.flickrPhotoId,linkedRevision) then
        return {state="unavailable"}
    end
    local scope={installationId=installationId,fgaPhotoBindingId=binding.fgaPhotoBindingId,
        flickrPhotoId=binding.flickrPhotoId,linkedFlickrRevision=linkedRevision,sourceKind=binding.sourceKind}
    local store=Store.new{catalog=d.catalog,plugin=d.plugin,pcall=d.call,
        activeCatalog=d.activeCatalog,currentIdentity=d.currentIdentity,workflow="existing_public_photo"}
    local pending=store:listPending(scope)
    if not unchanged() then return {state="unavailable"} end
    if type(pending)~="table" or pending.state~="ready" then return {state="unavailable"} end
    if #pending.handoffs>0 then
        local ids={}
        for _,h in ipairs(pending.handoffs) do ids[#ids+1]=h.handoffId end
        return {state="reconciliation_required",pendingHandoffIds=ids}
    end
    local groups=Discovery.new(Core).discoverStored(d.retrieve,guard(d.httpGet),d.decode,
        d.sleep,function() return not unchanged() end,installationId,d.jsonNull)
    if not unchanged() then return {state="unavailable"} end
    local history=Status.history({request=protocol.request,decode=d.decode,jsonNull=d.jsonNull,
        sleep=d.sleep,cancelled=function() return not unchanged() end},binding)
    if not unchanged() then return {state="unavailable"} end
    local eligible=Eligibility.assemble(groups,membership,history,Status,d.jsonNull)
    if not eligible then return {state="unavailable"} end
    local controller=Controller.new({store=store,call=d.call,now=d.now,
        credential=function() if not unchanged() then error("workflow_context_changed") end; return credential end,
        newHandoffId=d.newHandoffId,client=d.batchClient,jsonNull=d.jsonNull,
        encode=d.encode,decode=d.decode,post=guard(d.batchPost),
        prove=function(photoId,revision) return Photo.prove(protocol,photoId,revision) end},
        scope,eligible,binding,{workflow="existing_public_photo"})
    if not unchanged() or not controller.model.ready then return {state="unavailable"} end
    return Dialog.show(controller,{photoName="Existing public Flickr photo "..binding.flickrPhotoId,
        albumName="None (existing public photo; queue only)"})
end
function W.run(context,d)
    if not qualified(d) or type(context)~="table" or type(context.addCleanupHandler)~="function" then
        return {state="qualification_required"}
    end
    if active then return {state="busy"} end
    active=true
    local ok,result=d.call(function() return run(context,d) end)
    active=false
    return ok and result or {state="unavailable"}
end
return W
