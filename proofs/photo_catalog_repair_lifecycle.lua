-- Standalone source proof only. No manifest, menu, imports, network, or autoload.
-- Caller runs in LrTasks and supplies freshly resolved SDK objects plus a
-- validated durable-record projection. This is not a production outbox adapter.
local M = {}

function M.repair(catalog, collection, photo, record, tasks)
    if type(record) ~= "table" or type(record.flickrPhotoId) ~= "string"
        or not string.match(record.flickrPhotoId, "^%d+$") then
        return false, "invalid_record"
    end
    if record.path == "normal" then
        if record.uploadResultDurable ~= true then return false, "result_pending" end
    elseif record.path == "reconciled" then
        if record.bindingAcknowledgementDurable ~= true then
            return false, "acknowledgement_pending"
        end
    else
        return false, "invalid_path"
    end
    local function resolve()
        local service = collection:getService()
        if catalog:getPath() ~= record.catalogPath
            or service:getPluginId() ~= record.pluginId
            or service.localIdentifier ~= record.serviceId
            or collection.localIdentifier ~= record.collectionId
            or photo:getRawMetadata("uuid") ~= record.photoUuid then
            error("scope_mismatch")
        end
        local found
        for _, candidate in ipairs(collection:getPublishedPhotos()) do
            if candidate:getPhoto() == photo then
                if found then error("duplicate_publication_data") end
                found = candidate
            end
        end
        if not found then error("publication_data_missing") end
        local old = found:getRemoteId()
        if old ~= nil and old ~= "" and tostring(old) ~= record.flickrPhotoId then
            error("remote_id_conflict")
        end
        return found
    end
    local ok, outcome = tasks.pcall(function()
        local result = catalog:withWriteAccessDo("Repair photo remote ID proof", function()
            -- Resolve and check again inside the serialized write gate.
            resolve():setRemoteId(record.flickrPhotoId)
        end, {timeout = 5, asynchronous = false})
        if result ~= "executed" then error("gate_not_executed") end
        if tostring(resolve():getRemoteId()) ~= record.flickrPhotoId then
            error("readback_mismatch")
        end
        return "catalog_identity_observed"
    end)
    if not ok then return false, "catalog_repair_pending" end
    return true, outcome
end

return M
