-- Unregistered SDK adapter. Call only after the future provider has durably
-- snapshotted each photo's context. This module cannot authorize or upload.
local LrFileUtils = import("LrFileUtils")
local LrTasks = import("LrTasks")
local Core = require("PreflightCore")

local RenderPreflight = {}

function RenderPreflight.checkRendition(rendition, maximumBytes)
    -- Reject configuration before requesting a render.
    if Core.checkSize(maximumBytes, 1).code == "invalid_limit" then
        return Core.result("invalid_limit")
    end
    local called, rendered, path = LrTasks.pcall(function()
        return rendition:waitForRender()
    end)
    if not called or rendered ~= true or type(path) ~= "string" or path == "" then
        return Core.result("render_failed", maximumBytes)
    end
    local inspected, kind, attributes = LrTasks.pcall(function()
        return LrFileUtils.exists(path), LrFileUtils.fileAttributes(path)
    end)
    if not inspected then
        return Core.result("file_inspection_failed", maximumBytes)
    end
    if kind ~= "file" then
        return Core.result("missing_file", maximumBytes)
    end
    local size = type(attributes) == "table" and attributes.fileSize or nil
    local result = Core.checkSize(maximumBytes, size)
    if not result.ok then
        return result
    end
    -- SDK readFile supports non-ASCII paths. Read only size-approved files;
    -- retaining a string briefly also proves readability and detects a changed
    -- size. The image data never leaves this function or enters its result.
    local readable, contents = LrTasks.pcall(LrFileUtils.readFile, path)
    if not readable or type(contents) ~= "string" then
        return Core.result("unreadable_file", maximumBytes, size)
    end
    if #contents ~= size then
        return Core.result("file_changed", maximumBytes, size)
    end
    return result
end

function RenderPreflight.checkAll(renditions, maximumBytes)
    local results = {}
    for index, rendition in ipairs(renditions) do
        local called, result = LrTasks.pcall(
            RenderPreflight.checkRendition, rendition, maximumBytes
        )
        results[index] = called and result or Core.result("preflight_failed", maximumBytes)
    end
    return results
end

return RenderPreflight
