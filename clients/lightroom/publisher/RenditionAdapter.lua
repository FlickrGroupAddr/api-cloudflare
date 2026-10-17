-- Copyright 2026 Terry Ott. MIT License. Original FGA source.
-- Unregistered composition boundary. No authorization, network or catalog API.
local Tasks = import 'LrTasks'
local Files = import 'LrFileUtils'
local Preflight = require 'RenderPreflight'
local Core = require 'PreflightCore'
local Policy = require 'RenditionPolicy'
local Adapter = {}

local function copy(value)
    local result = {}
    for key, item in pairs(value) do
        result[key] = type(item) == 'table' and copy(item) or item
    end
    return result
end

function Adapter.new(deps)
    assert(type(deps) == 'table' and type(deps.current) == 'function')
    local seen = setmetatable({}, { __mode = 'k' })
    local adapter = {}

    function adapter:process(rendition, settings, preparedContext, consume)
        if self ~= adapter then return Core.result('adapter_invalid') end
        if type(consume) ~= 'function' then return Core.result('consumer_required') end
        if preparedContext == nil or preparedContext == false then
            return Core.result('context_required')
        end
        if rendition == nil then return Core.result('rendition_invalid') end
        if seen[rendition] then return Core.result('duplicate_rendition') end
        seen[rendition] = true
        local configured, config = Tasks.pcall(Policy.resolve, settings)
        if not configured or type(config) ~= 'table' then
            return Core.result('settings_invalid')
        end
        config = copy(config)
        local maximum = config.maximumBytes
        if Core.checkSize(maximum, 1).code == 'invalid_limit' then
            return Core.result('invalid_limit')
        end
        -- This context must have been durably prepared before the owning export
        -- session started rendering. waitForRender cannot enforce that ordering.
        local context = preparedContext
        local function fence()
            if deps.cancelled then
                local checked, stopped = Tasks.pcall(deps.cancelled)
                if not checked or stopped then return 'cancelled' end
            end
            if context ~= nil then
                local checked, current = Tasks.pcall(deps.current, context)
                if not checked or current ~= true then return 'context_stale' end
            end
        end
        local stopped = fence()
        if stopped then return Core.result(stopped, maximum) end
        -- #0028 owns render and preflight. Capture the successful path privately;
        -- later checks reuse it without ever waiting on this rendition again.
        local path
        local proxy = { waitForRender = function()
            local rendered, location = rendition:waitForRender()
            if rendered == true then path = location end
            return rendered, location
        end }
        local checked, result = Tasks.pcall(Preflight.checkRendition, proxy, maximum)
        if not checked then return Core.result('preflight_failed', maximum) end
        if not result.ok then return result end
        local size = result.sizeBytes
        proxy = { waitForRender = function() return true, path end }
        local function readCompleted()
            local validated, preflight = Tasks.pcall(Preflight.checkRendition, proxy, maximum)
            if not validated then return nil, 'preflight_failed' end
            if not preflight.ok then return nil, preflight.code end
            if preflight.sizeBytes ~= size then return nil, 'file_changed' end
            local read, bytes = Tasks.pcall(Files.readFile, path)
            if not read or type(bytes) ~= 'string' then return nil, 'unreadable_file' end
            if #bytes ~= size then return nil, 'file_changed' end
            return bytes
        end
        local baseline, reason = readCompleted()
        if baseline == nil then return Core.result(reason, maximum, size) end
        stopped = fence()
        if stopped then return Core.result(stopped, maximum, size) end
        local active, didRead, terminal = true, false, nil
        local lease = {}
        function lease.read(leaseSelf)
            if leaseSelf ~= lease or not active then return nil, 'lease_expired' end
            if terminal then return nil, terminal end
            terminal = fence()
            if terminal then return nil, terminal end
            local bytes, failure = readCompleted()
            if bytes == nil then terminal = failure; return nil, terminal end
            if bytes ~= baseline then terminal = 'file_changed'; return nil, terminal end
            terminal = fence()
            if terminal then return nil, terminal end
            didRead = true
            return bytes
        end
        -- The callback must consume bytes synchronously within this export.
        -- Its true means only that its bounded handoff succeeded, never upload.
        local called, consumed = Tasks.pcall(consume, lease, context, copy(config))
        active = false
        baseline, path, proxy = nil, nil, nil
        stopped = terminal or fence()
        if stopped then return Core.result(stopped, maximum, size) end
        if not called or consumed ~= true then return Core.result('handoff_failed', maximum, size) end
        if not didRead then return Core.result('file_not_read', maximum, size) end
        local outcome = Core.result('handed_off', maximum, size)
        outcome.ok = true
        return outcome
    end

    return adapter
end

return Adapter
