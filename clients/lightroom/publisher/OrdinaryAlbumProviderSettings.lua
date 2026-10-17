-- Copyright 2026 Terry Ott. MIT License. Original FGA source.
-- Pure collection-settings policy; no catalog or network capability.
local Settings = {}

-- SDK updateExportSettings runs before rendition objects are generated.
-- Resolve before mutating so unsupported retained settings fail as a whole.
function Settings.applyRenditionPolicy(exportSettings)
    local policy, reason = require('RenditionPolicy').resolve(exportSettings)
    if not policy then return nil, reason end
    for key, value in pairs(policy.exportSettings) do exportSettings[key] = value end
    return policy
end

-- Summary settings are documented plain records; dialog settings supply :pairs().
function Settings.valid(settings, iterate)
    if type(settings) ~= 'table' or settings.schemaVersion ~= 1
        or settings.albumLifecycle ~= 'local_unbound' then return false end
    for key in (iterate or pairs)(settings) do
        if key ~= 'schemaVersion' and key ~= 'albumLifecycle'
            and key ~= 'LR_canSaveCollection' and key ~= 'LR_liveName'
            and key ~= 'LR_canEditName' then return false end
    end
    return true
end

function Settings.prepare(info)
    if type(info) ~= 'table' or type(info.collectionSettings) ~= 'table' then
        return false, 'Album settings are unavailable'
    end
    local settings = info.collectionSettings
    if type(settings.pairs) ~= 'function' then
        settings.LR_canSaveCollection = false
        return false, 'Album settings are unavailable'
    end
    local function iterate(value) return value:pairs() end
    if info.isDefaultCollection ~= false or info.collectionType ~= 'collection' then
        settings.LR_canSaveCollection = false
        return false, 'Create or select an Album to publish'
    end
    -- Only a new, empty record can receive defaults. Never reset retained state.
    if info.publishedCollection == nil then
        for key in (iterate or pairs)(settings) do
            if key ~= 'LR_canSaveCollection' and key ~= 'LR_liveName'
                and key ~= 'LR_canEditName' and key ~= 'schemaVersion'
                and key ~= 'albumLifecycle' then
                settings.LR_canSaveCollection = false
                return false, 'Album settings require repair'
            end
        end
        if settings.schemaVersion == nil and settings.albumLifecycle == nil then
            settings.schemaVersion = 1
            settings.albumLifecycle = 'local_unbound'
        end
    end
    local valid = Settings.valid(settings, iterate)
    settings.LR_canSaveCollection = valid
    return valid, valid and 'Creates a local Album. No Flickr album is created here.'
        or 'Album settings require repair'
end

return Settings
