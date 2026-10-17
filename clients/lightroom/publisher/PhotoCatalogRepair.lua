-- Copyright 2026 Terry Ott. MIT License.
-- Dormant post-callback adapter. Caller runs in an LrTasks asynchronous task.
-- No rendition, HTTP, rendering, association creation, or SDK imports.
local C = require "UploadAttemptCodec"
local M = {}
local scopeFields = C.fields("publishServiceLocalId fgaPublishServiceId publishedCollectionLocalId photoUuid")
local function fail(state) return {state=state} end
local function scopeValid(scope)
    return C.object(scope,scopeFields) and C.integer(scope.publishServiceLocalId,1)
        and C.opaque(scope.fgaPublishServiceId) and C.integer(scope.publishedCollectionLocalId,1)
        and C.uuid(scope.photoUuid)
end

function M.new(options)
    options=options or {}
    local R={}
    local catalog,token=options.catalog,options.activationToken
    local protect,store=options.pcall,options.store
    local function current(scope,number)
        return catalog~=nil and token~=nil and type(options.pluginId)=="string" and options.pluginId~=""
            and type(options.activeCatalog)=="function" and options.activeCatalog()==catalog
            and type(options.currentActivation)=="function" and options.currentActivation()==token
            and type(options.isOwner)=="function" and options.isOwner(scope,number)==true
    end
    local function resolve(scope,number)
        if not current(scope,number) then return nil,"scope_invalid" end
        local service
        for _,candidate in ipairs(catalog:getPublishServices(options.pluginId)) do
            if candidate.localIdentifier==scope.publishServiceLocalId then
                if service or candidate:getPluginId()~=options.pluginId then return nil,"scope_invalid" end
                service=candidate
            end
        end
        if not service or type(options.readServiceIdentity)~="function"
            or options.readServiceIdentity(service)~=scope.fgaPublishServiceId then return nil,"scope_invalid" end
        local collection=catalog:getPublishedCollectionByLocalIdentifier(scope.publishedCollectionLocalId)
        if not collection or collection.localIdentifier~=scope.publishedCollectionLocalId
            or type(collection.getPublishedPhotos)~="function" or type(collection.getPhotos)~="function"
            or type(collection.isSmartCollection)~="function" or collection:isSmartCollection()~=false
            or collection:getService()~=service then return nil,"scope_invalid" end
        local photo=catalog:findPhotoByUuid(scope.photoUuid)
        if not photo or photo:getRawMetadata("uuid")~=scope.photoUuid then return nil,"scope_invalid" end
        local memberCount=0
        for _,member in ipairs(collection:getPhotos()) do if member==photo then memberCount=memberCount+1 end end
        if memberCount~=1 then return nil,"scope_invalid" end
        local relationship
        for _,candidate in ipairs(collection:getPublishedPhotos()) do
            local source=candidate:getPhoto()
            if source==photo or (source and source:getRawMetadata("uuid")==scope.photoUuid) then
                if relationship or source~=photo then return nil,"publication_data_conflict" end
                relationship=candidate
            end
        end
        if not relationship then return nil,"publication_data_missing" end
        if not current(scope,number) then return nil,"scope_invalid" end
        return {photo=photo,relationship=relationship}
    end
    local function allowed(record)
        if not record or record.uploadPhase~="returned_id" or not C.opaque(record.flickrPhotoId)
            or type(record.catalogPublication)~="table" then return false end
        if record.resultKind=="returned_upload_id" then return true end
        return record.resultKind=="photographer_assertion" and type(record.photoProof)=="table"
            and record.photoProof.state=="acknowledged"
    end
    local function identityMatches(relationship,id)
        local old=relationship:getRemoteId()
        return old==nil or old=="" or old==id
    end

    -- Pure current SDK observation: no journal gate, mutation or yielding seam.
    -- Recovery calls this after its last potentially yielding journal/link read.
    function R:observe(scope,number,photoId)
        if not scopeValid(scope) or not C.integer(number,1) or not C.opaque(photoId)
            or type(protect)~="function" then return fail("scope_invalid") end
        local outcome
        local ok=protect(function()
            local fresh,why=resolve(scope,number)
            if not fresh then outcome=fail(why); return end
            if fresh.relationship:getRemoteId()~=photoId then outcome=fail("catalog_repair_pending"); return end
            outcome={state="catalog_identity_observed"}
        end)
        return ok and outcome or fail("catalog_repair_pending")
    end

    function R:repair(scope,number,now)
        if not scopeValid(scope) or not C.integer(number,1) or not C.time(now)
            or type(protect)~="function" or not store then return fail("scope_invalid") end
        scope=C.clone(scope)
        local outcome
        local ok=protect(function()
            local target,reason=resolve(scope,number)
            if not target then outcome=fail(reason); return end
            local observed=store:inspect(scope,target.photo,now,number)
            if observed.state~="ready" then outcome=observed; return end
            if not allowed(observed.record) then outcome=fail("correlation_invalid"); return end
            local record=observed.record
            local photoId=record.flickrPhotoId
            if not identityMatches(target.relationship,photoId) then outcome=fail("remote_id_conflict"); return end
            local open,completed=true,false
            local gateReason
            local gateOk,status=protect(function()
                return catalog:withWriteAccessDo("Repair FGA photo identity",function()
                    -- A callback queued beyond this invocation can never write.
                    if not open then error("expired_repair") end
                    local fresh,why=resolve(scope,number)
                    if not fresh or fresh.photo~=target.photo then gateReason=why or "scope_invalid"; return end
                    -- Read-only seam: no nested access gate and no yielding here.
                    local checked=store:validateCatalogRepair(scope,fresh.photo,observed.fence,now)
                    if checked.state~="ready" then gateReason=checked.state; return end
                    if not allowed(checked.record) or checked.record.flickrPhotoId~=photoId then
                        gateReason="correlation_invalid"; return
                    end
                    if not identityMatches(fresh.relationship,photoId) then gateReason="remote_id_conflict"; return end
                    if not current(scope,number) then gateReason="scope_invalid"; return end
                    if fresh.relationship:getRemoteId()~=photoId then fresh.relationship:setRemoteId(photoId) end
                    completed=true
                end,{timeout=5,asynchronous=false})
            end)
            open=false
            if not gateOk or status~="executed" then outcome=fail("catalog_repair_pending"); return end
            if gateReason then outcome=fail(gateReason); return end
            if not completed then outcome=fail("catalog_repair_pending"); return end
            local fresh,why=resolve(scope,number)
            if not fresh then outcome=fail(why); return end
            if fresh.photo~=target.photo or fresh.relationship:getRemoteId()~=photoId then
                outcome=fail("catalog_repair_pending"); return
            end
            local after=store:inspect(scope,fresh.photo,now,number)
            if after.state~="ready" then outcome=after; return end
            if not allowed(after.record) or after.record.flickrPhotoId~=photoId then
                outcome=fail("correlation_invalid"); return
            end
            local function exactRelationship()
                local live=resolve(scope,number)
                return live~=nil and live.photo==target.photo and live.relationship:getRemoteId()==photoId
            end
            -- Undo/resumption still re-resolves and observes the current ID.
            if after.record.catalogPublication.state=="acknowledged" then
                if not exactRelationship() then outcome=fail("catalog_repair_pending"); return end
                outcome={state="catalog_acknowledged",fence=after.fence}; return
            end
            -- A private journal gate can wait after the preceding observation.
            -- Re-resolve inside that gate before creating the acknowledgement.
            outcome=store:acknowledgeCatalog(scope,fresh.photo,after.fence,photoId,now,exactRelationship)
            if outcome.state=="catalog_acknowledged" and not exactRelationship() then
                outcome=fail("catalog_repair_pending")
            end
        end)
        return ok and outcome or fail("catalog_repair_pending")
    end
    return R
end
return M
