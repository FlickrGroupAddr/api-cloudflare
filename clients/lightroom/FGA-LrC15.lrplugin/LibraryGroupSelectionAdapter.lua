-- Copyright 2026 Terry Ott. MIT License.
-- Disabled SDK15.3 composition. No task/menu/provider registration.
local Adapter = {PRODUCTION_QUALIFIED=false}
local Core = require "ConnectionCore"
local Store = require "GroupSelectionStore"
local Controller = require "GroupSelectionController"
local Eligibility = require "GroupSelectionEligibility"
local function integer(v)
    return type(v)=="number" and v>=1 and v<=9007199254740991 and v==math.floor(v)
end
local function uuid(v)
    return type(v)=="string" and #v==36
        and v:match("^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$")~=nil
end
local function single(values)
    if type(values)~="table" or #values~=1 then return nil end
    for key in pairs(values) do if key~=1 then return nil end end
    return values[1]
end
local function resolve(d)
    local catalog=d.activeCatalog()
    if not catalog or (d.cancelled and d.cancelled()) then return nil end
    local photo=single(catalog:getTargetPhotos())
    local album=single(catalog:getActiveSources())
    if not photo or not album or photo.catalog~=catalog or album:type()~="LrPublishedCollection"
        or album:isSmartCollection()~=false then return nil end
    local service=album:getService()
    if not service or service:type()~="LrPublishService" or service:getPluginId()~=Core.PLUGIN_ID
        or not integer(service.localIdentifier) or not integer(album.localIdentifier) then return nil end
    local found=false
    for _,member in ipairs(photo:getContainedPublishedCollections()) do
        if member==album then found=true end
    end
    local id=photo:getRawMetadata("uuid")
    if not found or not uuid(id) or d.activeCatalog()~=catalog then return nil end
    return {catalog=catalog,photo=photo,album=album,service=service,
        scope={publishServiceLocalId=service.localIdentifier,
            publishedCollectionLocalId=album.localIdentifier,photoUuid=id}}
end
-- d is an owning SDK task's dependency object (call=LrTasks.pcall).
-- No credential, HTTP, rendering or uploading dependency is accepted or invoked.
function Adapter.resolve(d)
    if type(d)~="table" or type(d.call)~="function" or type(d.activeCatalog)~="function"
        or (d.cancelled~=nil and type(d.cancelled)~="function") then return nil,"scope_invalid" end
    local ok,value=d.call(function() return resolve(d) end)
    if not ok or not value then return nil,"scope_invalid" end
    return value
end
function Adapter.new(d)
    if type(d)~="table" or d.plugin==nil then return nil,"scope_invalid" end
    local captured,reason=Adapter.resolve(d)
    if not captured then return nil,reason end
    local function current()
        local value=Adapter.resolve(d)
        return value and value.catalog==captured.catalog and value.photo==captured.photo
            and value.album==captured.album and value.service==captured.service
            and value.scope.photoUuid==captured.scope.photoUuid
            and value.scope.publishServiceLocalId==captured.scope.publishServiceLocalId
            and value.scope.publishedCollectionLocalId==captured.scope.publishedCollectionLocalId
    end
    local store=Store.new{catalog=captured.catalog,photo=captured.photo,plugin=d.plugin,pcall=d.call,
        -- The store calls this fence before, inside and after its private gate.
        activeCatalog=function() return current() and captured.catalog or nil end}
    local session={}
    -- Caller establishes unpublished status from its trusted binding context.
    -- groups is the complete validated group-discovery aggregate; never raw HTTP.
    -- Bound Queue and membership/history composition belong to their own adapter.
    function session:unpublishedController(groups)
        if not current() then return nil,"scope_invalid" end
        local eligibility=Eligibility.assemble(groups,nil,nil)
        if not eligibility then return nil,"selection_data_unavailable" end
        local controller=Controller.new({store=store,call=d.call},captured.scope,eligibility)
        if not current() or not controller.model.ready then return nil,"selection_data_unavailable" end
        return controller
    end
    function session:showUnpublished(groups)
        local controller,err=self:unpublishedController(groups)
        if not controller then return {state=err} end
        local ok,result=d.call(function()
            local identity={photoName=captured.photo:getFormattedMetadata("fileName"),
                albumName=captured.album:getName()}
            if not current() then return {state="scope_invalid"} end
            return require("GroupSelectionDialog").show(controller,identity)
        end)
        return ok and result or {state="unavailable"}
    end
    return session
end
return Adapter
