-- Copyright 2026 Terry Ott. MIT License. Original FGA source.
-- Unregistered SDK callback factory. Integration must supply yielding pcall and
-- the verified, durable #0090 identity boundary; this shell cannot render/upload.
local Settings = require 'OrdinaryAlbumProviderSettings'
local Provider = {}

local function failure(code)
    return { ok = false, code = code, message = code == 'album_required'
        and 'Create or select an Album to publish' or 'Album publishing is unavailable; repair is required' }
end

local function positiveInteger(value)
    return type(value) == 'number' and value >= 1 and value <= 9007199254740991
        and value % 1 == 0
end

local function identityValid(value)
    if type(value) ~= 'table' or value.schemaVersion ~= 1 or value.serviceRevision ~= 1
        or not positiveInteger(value.linkedFlickrRevision)
        or type(value.issuingInstallationId) ~= 'string'
        or #value.issuingInstallationId < 1 or #value.issuingInstallationId > 128
        or not value.issuingInstallationId:match('^[A-Za-z0-9][A-Za-z0-9@._:%-]*$') then
        return false
    end
    local id = value.fgaPublishServiceId
    return type(id) == 'string' and #id == 36
        and id:match('^%x%x%x%x%x%x%x%x%-%x%x%x%x%-4%x%x%x%-[89ab]%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$')
        and not id:find('[A-F]')
end

function Provider.new(deps)
    assert(type(deps) == 'table' and type(deps.pcall) == 'function'
        and type(deps.verifyService) == 'function' and type(deps.pluginId) == 'string')
    local callbacks = {
        supportsIncrementalPublish = 'only',
        titleForPublishedCollection = 'Album',
        titleForPublishedCollection_standalone = 'Album',
    }

    function callbacks.viewForCollectionSettings(f, _publishSettings, info)
        local _, message = Settings.prepare(info)
        return f:group_box { title = 'Album', f:static_text { title = message } }
    end

    function callbacks.validatePublishedCollectionName(name)
        if type(name) ~= 'string' or not name:find('%S') then
            return false, 'Enter an Album name'
        end
        return true
    end

    -- Called within an SDK task. No caller-supplied local IDs or service titles
    -- participate in identity. Read the documented objects and their summary.
    function callbacks.validateTarget(_publishSettings, context)
        if type(context) ~= 'table' or type(context.publishedCollectionInfo) ~= 'table'
            or context.publishedCollectionInfo.isDefaultCollection ~= false then
            return failure('album_required')
        end
        local collection = context.publishedCollection
        if collection == nil then return failure('album_required') end
        local read, target = deps.pcall(function()
            if collection:isSmartCollection() ~= false then return failure('album_required') end
            local service = collection:getService()
            if service == nil or service:getPluginId() ~= deps.pluginId then
                return failure('foreign_service')
            end
            local info = collection:getCollectionInfoSummary()
            if type(info) ~= 'table' or info.isDefaultCollection ~= false then
                return failure('album_required')
            end
            if not positiveInteger(collection.localIdentifier)
                or info.localIdentifier ~= collection.localIdentifier then
                return failure('local_identity_invalid')
            end
            -- No bound albums are supported in this shell. Never adopt a remote
            -- ID/URL, even when its name, parent, or supplied service ID matches.
            if info.remoteId ~= nil or info.remoteUrl ~= nil
                or context.publishedCollectionInfo.remoteId ~= nil
                or context.publishedCollectionInfo.remoteUrl ~= nil then
                return failure('remote_identity_requires_reconciliation')
            end
            if not Settings.valid(info.collectionSettings) then
                return failure('album_settings_invalid')
            end
            return { ok = true, localCollectionIdentifier = string.format('%.0f', collection.localIdentifier),
                publishSettings = info.publishSettings }
        end)
        if not read or type(target) ~= 'table' then return failure('catalog_read_failed') end
        if not target.ok then return target end
        local verified, result = deps.pcall(deps.verifyService, target.publishSettings)
        if not verified or type(result) ~= 'table' or result.ok ~= true
            or result.linkStatus ~= 'ready' or not identityValid(result.identity) then
            return failure('service_identity_unavailable')
        end
        target.publishSettings = nil
        -- Only immutable saved fields supplied by the fresh identity boundary.
        target.fgaPublishServiceId = result.identity.fgaPublishServiceId
        target.linkedFlickrRevision = result.identity.linkedFlickrRevision
        return target
    end

    function callbacks.processRenderedPhotos(_functionContext, exportContext)
        local result = callbacks.validateTarget(exportContext and exportContext.propertyTable, exportContext)
        if not result.ok then error(result.message, 0) end
        -- Deliberately stop before renditions(), waitForRender(), or catalog writes.
        error('Album publisher integration is not enabled', 0)
    end

    return callbacks
end

return Provider
