-- Copyright 2026 Terry Ott. MIT License.
-- Disabled publisher composition boundary. No provider callback or network API.
local Adapter = {PRODUCTION_QUALIFIED=false}
local Core = require "ConnectionCore"
local Store = require "GroupSelectionStore"
local Controller = require "GroupSelectionController"
local json = require "dkjson"
local function integer(v)
    return type(v)=="number" and v>=1 and v<=9007199254740991 and v==math.floor(v)
end
local function opaque(v)
    return type(v)=="string" and #v>=1 and #v<=128
        and v:match("^[A-Za-z0-9][A-Za-z0-9@._:%-]*$")~=nil
end
local function uuid(v)
    return type(v)=="string" and #v==36
        and v:match("^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$")~=nil
end
local function exact(v,fields)
    if type(v)~="table" or v==json.null then return false end
    local count=0
    for key in pairs(v) do if not fields[key] then return false end; count=count+1 end
    local expected=0; for _ in pairs(fields) do expected=expected+1 end
    return count==expected
end
local function clone(v)
    if v==json.null or type(v)~="table" then return v end
    local result={}; for key,value in pairs(v) do result[key]=clone(value) end
    return result
end
local function binding(v)
    return exact(v,{fgaPhotoBindingId=true,flickrPhotoId=true,verificationRevision=true,
        linkedFlickrRevision=true,sourceKind=true}) and opaque(v.fgaPhotoBindingId)
        and opaque(v.flickrPhotoId) and integer(v.verificationRevision)
        and integer(v.linkedFlickrRevision) and v.sourceKind=="fga_direct_upload"
end
local function failed(state) return {state=state} end

-- context is the owning publisher's exportContext; photo is its exact rendition photo.
-- call is LrTasks.pcall. Selection/active-source UI is deliberately irrelevant here.
local function construct(d,context,photo,pluginId)
    if type(d)~="table" or d.plugin==nil or type(d.call)~="function"
        or type(d.activeCatalog)~="function" or type(context)~="table"
        or (d.cancelled~=nil and type(d.cancelled)~="function") then return nil,"scope_invalid" end
    local call,active,cancelled,plugin=d.call,d.activeCatalog,d.cancelled,d.plugin
    local service,album=context.publishService,context.publishedCollection
    local captured
    local function resolve()
        local catalog=active()
        if not catalog or not photo or photo.catalog~=catalog or not service or not album
            or context.publishService~=service or context.publishedCollection~=album
            or type(context.publishedCollectionInfo)~="table"
            or context.publishedCollectionInfo.isDefaultCollection~=false
            or (cancelled and cancelled()) or service:type()~="LrPublishService"
            or service:getPluginId()~=pluginId or album:type()~="LrPublishedCollection"
            or album:isSmartCollection()~=false or album:getService()~=service
            or not integer(service.localIdentifier) or not integer(album.localIdentifier) then return nil end
        local id=photo:getRawMetadata("uuid")
        if not uuid(id) then return nil end
        local member=false
        for _,collection in ipairs(photo:getContainedPublishedCollections()) do
            if collection==album then member=true end
        end
        if not member or active()~=catalog then return nil end
        return {catalog=catalog,publishServiceLocalId=service.localIdentifier,
            publishedCollectionLocalId=album.localIdentifier,photoUuid=id}
    end
    local ok,value=call(resolve)
    if not ok or not value then return nil,"scope_invalid" end
    captured=value
    local scope={publishServiceLocalId=value.publishServiceLocalId,
        publishedCollectionLocalId=value.publishedCollectionLocalId,photoUuid=value.photoUuid}
    local function current()
        local v=resolve()
        return v~=nil and v.catalog==captured.catalog and v.photoUuid==scope.photoUuid
            and v.publishServiceLocalId==scope.publishServiceLocalId
            and v.publishedCollectionLocalId==scope.publishedCollectionLocalId
    end
    local store=Store.new{catalog=value.catalog,photo=photo,plugin=plugin,pcall=call,
        activeCatalog=function() return current() and captured.catalog or nil end}
    local handles,busy={},false
    local session={}
    local function run(operation)
        if busy then return failed("busy") end
        busy=true
        local worked,result=call(function()
            if not current() then return failed("scope_invalid") end
            return operation()
        end)
        busy=false
        return worked and result or failed("unresolved")
    end
    local function view(h)
        return {scope=clone(scope),selectionState=h.selectionState,choice=h.record.choice,
            selectionRevision=h.record.selectionRevision,flickrGroupIds=clone(h.record.flickrGroupIds),
            handoffId=h.record.handoffId,outboxRevision=h.record.outboxRevision}
    end
    function session:freeze(handoffId)
        return run(function()
            if not opaque(handoffId) then return failed("handoff_invalid") end
            local read=store:readChoice(scope)
            if read.state~="ready" then return failed(read.state) end
            local revision=read.selection and read.selection.selectionRevision or 0
            local prepared=store:prepare(scope,revision,handoffId)
            if prepared.state~="prepared" then return failed(prepared.state) end
            -- Store.prepare freezes the exact revision inside the private write gate.
            local handle={}
            handles[handle]={record=clone(prepared.handoff),
                selectionState=prepared.handoff.selectionRevision==0 and "absent" or prepared.handoff.choice}
            return {state="frozen",snapshot=handle,choice=view(handles[handle])}
        end)
    end
    function session:inspect(handle)
        local h=handles[handle]
        return h and {state="frozen",choice=view(h)} or failed("snapshot_invalid")
    end
    -- The owning publisher supplies its validated direct-upload binding for this
    -- exact rendition after publication. This is correlation, never remote authority.
    -- One binding is locked before dispatch; responses cannot choose/rebind identity.
    function session:bindGroups(handle,value)
        return run(function()
            local h=handles[handle]
            if not h or h.record.choice~="groups" or h.confirmed or h.binding then
                return failed("snapshot_invalid")
            end
            if not binding(value) then return failed("binding_invalid") end
            h.binding=clone(value)
            return {state="bound"}
        end)
    end
    local function confirm(h,ack)
        local result=store:confirm(scope,h.record.handoffId,h.record.outboxRevision,ack,current)
        if result.state~="confirmed" then return failed(result.state) end
        h.confirmed=true
        return {state="confirmed",selectionConsumed=result.selectionConsumed,
            groupAcceptanceRecorded=h.record.choice=="groups"}
    end
    -- document is a decoded complete response, never a caller-authored store ack.
    -- Wire decoding/bounds are owned by the publisher's qualified transport adapter.
    function session:confirmGroups(handle,status,document)
        return run(function()
            local h=handles[handle]
            if not h or h.confirmed or h.record.choice~="groups" or not h.binding then
                return failed("snapshot_invalid")
            end
            if status~=202 then return failed("ack_invalid") end
            local submissions=Controller.validate202(document,h.binding,h.record.flickrGroupIds,json.null)
            if not submissions then return failed("ack_invalid") end
            return confirm(h,{kind="groups_accepted",selectionRevision=h.record.selectionRevision,
                flickrGroupIds=clone(h.record.flickrGroupIds),submissions=clone(submissions)})
        end)
    end
    function session:confirmPublication(handle,evidence)
        return run(function()
            local h=handles[handle]
            if not h or h.confirmed or h.record.choice~="none" then return failed("snapshot_invalid") end
            if not exact(evidence,{publicationRecorded=true,albumAttachmentDurable=true})
                or evidence.publicationRecorded~=true or evidence.albumAttachmentDurable~=true then
                return failed("ack_invalid")
            end
            return confirm(h,{kind="publication_recorded",selectionRevision=h.record.selectionRevision,
                flickrGroupIds={},publicationRecorded=true,albumAttachmentDurable=true})
        end)
    end
    return session
end
function Adapter.new(d,context,photo)
    return construct(d,context,photo,Core.PLUGIN_ID)
end
-- Fixed isolated fixture identity; production construction is unchanged.
function Adapter.newQualification(d,context,photo)
    return construct(d,context,photo,
        'com.sixbuckssolutions.fga.providerrender.qualification.lrc15')
end
return Adapter
