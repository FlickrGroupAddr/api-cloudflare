-- Copyright 2026 Terry Ott. MIT License. Original FGA source.
-- Unregistered SDK callback factory. Integration must supply yielding pcall and
-- the verified, durable #0090 identity boundary. SDK processing remains disabled;
-- the explicit pre-start composition seam awaits the #0103 dispatcher.
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

local function construct(deps,qualification)
    assert(type(deps) == 'table' and type(deps.pcall) == 'function'
        and type(deps.verifyService) == 'function' and type(deps.pluginId) == 'string')
    local callbacks = {
        supportsIncrementalPublish = 'only',
        titleForPublishedCollection = 'Album',
        titleForPublishedCollection_standalone = 'Album',
    }

    function callbacks.updateExportSettings(exportSettings)
        local policy = Settings.applyRenditionPolicy(exportSettings)
        if not policy then error('Album rendition settings are unsupported', 0) end
    end

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

    -- Explicit dormant dispatcher seam, NOT an SDK callback. #0103 must call
    -- this before startRendering/renditions/doExportOnCurrentTask. The documented
    -- processRenderedPhotos callback is already too late to establish that order.
    -- updateExportSettings must already have projected the actual session settings.
    function callbacks.prepareBeforeRendering(exportContext, preparation)
        if type(exportContext) ~= 'table' or type(preparation) ~= 'table'
            or type(preparation.now) ~= 'function'
            or type(preparation.handoffId) ~= 'function'
            or type(preparation.contextDependencies) ~= 'table' then
            return nil, 'preparation_invalid'
        end
        local configured, policy = deps.pcall(function()
            return require('RenditionPolicy').resolve(exportContext.propertyTable)
        end)
        if not configured or not policy then return nil, 'settings_invalid' end
        for key, value in pairs(policy.exportSettings) do
            if exportContext.propertyTable[key] ~= value then return nil, 'settings_not_applied' end
        end
        local actualSettings, actualSession = exportContext.propertyTable, exportContext.exportSession
        local function settingsCurrent()
            if exportContext.propertyTable ~= actualSettings
                or exportContext.exportSession ~= actualSession then return false end
            for key, value in pairs(policy.exportSettings) do
                if actualSettings[key] ~= value then return false end
            end
            return true
        end
        local contextDeps = {}
        for key, value in pairs(preparation.contextDependencies) do contextDeps[key] = value end
        contextDeps.verifyTarget = function(context)
            return callbacks.validateTarget(context.propertyTable, context)
        end
        local contextFactory = require('FrozenPublishContext')
        local contexts, reason = (qualification and contextFactory.newQualification
            or contextFactory.new)(contextDeps, exportContext)
        if not contexts then return nil, reason end
        local prepared, results, finished = {}, {}, {}
        local walked = deps.pcall(function()
            -- This iterator does not request rendering. Complete the entire
            -- durable snapshot pass before returning the callable render seam.
            for photo in exportContext.exportSession:photosToExport() do
                if prepared[photo] ~= nil then error('duplicate photo', 0) end
                local worked, result = deps.pcall(function()
                    return contexts:prepare(photo, preparation.handoffId(photo), preparation.now())
                end)
                if not worked or type(result) ~= 'table' then result = {state='unresolved'} end
                prepared[photo] = result
                if result.state ~= 'prepared' then
                    results[#results + 1] = {photo=photo, result={ok=false, code=result.state}}
                    finished[photo] = true
                    -- A failed candidate must not be rendered with unfrozen state.
                    exportContext.exportSession:removePhoto(photo)
                end
            end
        end)
        if not walked then return nil, 'preparation_failed' end
        local adapter = require('RenditionAdapter').new {
            current = function(handle)
                return settingsCurrent()
                    and contexts:inspect(handle, preparation.now()).state == 'ready'
            end,
            cancelled = contextDeps.cancelled,
        }
        local session = {}
        function session:process(rendition, consume)
            if self ~= session or rendition == nil then return nil, 'rendition_invalid' end
            local photo = rendition.photo
            local value = prepared[photo]
            if not value or value.state ~= 'prepared' then return nil, 'photo_not_prepared' end
            if finished[photo] then return nil, 'photo_already_finished' end
            finished[photo] = true
            local worked, result = deps.pcall(function()
                if not settingsCurrent() then return {ok=false, code='settings_changed'} end
                return adapter:process(rendition, actualSettings, value.context, consume)
            end)
            if not worked or type(result) ~= 'table' then result = {ok=false, code='rendition_failed'} end
            results[#results + 1] = {photo=photo, result=result}
            return result
        end
        function session:outcomes()
            local copy = {}
            for index, value in ipairs(results) do
                local result = {}
                for key, item in pairs(value.result) do result[key] = item end
                copy[index] = {photo=value.photo, result=result}
            end
            return copy
        end
        -- Post-proof operations delegate exact-revision consumption to #0065.
        function session:bindGroups(photo, now)
            local value = prepared[photo]
            if not value or value.state ~= 'prepared' then return {state='context_invalid'} end
            return contexts:bindGroups(value.context, now)
        end
        function session:confirmGroups(photo, status, document, now)
            local value = prepared[photo]
            if not value or value.state ~= 'prepared' then return {state='context_invalid'} end
            return contexts:confirmGroups(value.context, status, document, now)
        end
        function session:confirmPublication(photo, now)
            local value = prepared[photo]
            if not value or value.state ~= 'prepared' then return {state='context_invalid'} end
            return contexts:confirmPublication(value.context, now)
        end
        return session
    end

    function callbacks.processRenderedPhotos(_functionContext, exportContext)
        local result = callbacks.validateTarget(exportContext and exportContext.propertyTable, exportContext)
        if not result.ok then error(result.message, 0) end
        -- Deliberately stop before renditions(), waitForRender(), or catalog writes.
        error('Album publisher integration is not enabled', 0)
    end

    return callbacks
end

function Provider.new(deps)
    return construct(deps,false)
end
function Provider.newQualification(deps)
    local fixed={}
    for k,v in pairs(deps) do fixed[k]=v end
    fixed.pluginId='com.sixbuckssolutions.fga.providerrender.qualification.lrc15'
    return construct(fixed,true)
end
return Provider
