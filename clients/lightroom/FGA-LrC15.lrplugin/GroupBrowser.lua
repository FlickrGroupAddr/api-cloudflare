-- Native, browse-only dialog. Completed snapshots stay in this dialog's memory.
local LrBinding = import "LrBinding"
local LrDialogs = import "LrDialogs"
local LrFunctionContext = import "LrFunctionContext"
local LrTasks = import "LrTasks"
local LrView = import "LrView"

local Controller = require "ConnectionController"
local Client = require("GroupDiscoveryClient").new(require "ConnectionCore")
local Browser = {}

local function displayResult(properties, result)
    properties.items = {}
    properties.highlight = {}
    properties.observed = "No complete snapshot available."
    if result.state ~= "complete" then
        properties.state = "unavailable"
        properties.status = result.message or "Writable groups are unavailable. Reload to try again."
        return
    end

    local groups = {}
    for _, group in ipairs(result.groups) do groups[#groups + 1] = group end
    table.sort(groups, function(left, right)
        if left.displayName == right.displayName then return left.flickrGroupId < right.flickrGroupId end
        return left.displayName < right.displayName
    end)
    local items = {}
    for _, group in ipairs(groups) do
        items[#items + 1] = {
            title = group.displayName .. "  [" .. group.flickrGroupId .. "]", value = group.flickrGroupId,
        }
    end
    properties.items = items
    properties.observed = "Last successful observation (UTC): " .. result.refreshedAt
        .. " | Snapshot revision: " .. tostring(result.snapshotRevision)
    if result.snapshotStatus == "stale_refreshing" then
        properties.state = "refreshing"
        properties.status = "Stale snapshot: refresh in progress. Showing " .. #groups
            .. " previously observed writable groups. Reload later to check the result."
    elseif result.snapshotStatus == "stale_refresh_failed" then
        properties.state = "stale"
        properties.status = "Stale snapshot: the latest refresh failed at " .. result.refreshFailedAt
            .. " (UTC). Showing " .. #groups .. " previously observed writable groups."
    elseif #groups == 0 then
        properties.state = "empty"
        properties.status = "The complete snapshot contains no writable Flickr groups."
    else
        properties.state = "available"
        properties.status = tostring(#groups) .. " writable Flickr groups available."
    end
end

-- Exposed for fixture tests; all network work stays behind the injected client.
function Browser.newSession(properties, dependencies, discover, tasks)
    local closed = false
    properties.items = {}
    properties.highlight = {}
    properties.busy = false
    properties.canReload = true
    properties.state = "loading"
    properties.status = "Loading writable Flickr groups..."
    properties.observed = "No complete snapshot available."
    local function cancelled() return closed end
    local function close()
        if not closed and properties.busy then dependencies.logState("cancelled") end
        closed = true
    end
    local function reload()
        if closed or properties.busy then return end
        properties.busy = true
        properties.canReload = false
        properties.state = "loading"
        properties.status = "Loading a complete writable-group snapshot..."
        properties.items = {}
        properties.highlight = {}
        properties.observed = "No complete snapshot available."
        dependencies.logState("loading")
        tasks.startAsyncTask(function()
            if closed then return end
            local ok, result = tasks.pcall(discover, dependencies.retrieve, dependencies.httpGet,
                dependencies.decode, dependencies.sleep, cancelled,
                dependencies.expectedInstallationId, dependencies.jsonNull, function(state)
                    if not closed and state == "refreshing" then
                        properties.state = "refreshing"
                        properties.status = "The service is refreshing writable groups. Waiting for a complete snapshot; close this dialog to cancel."
                    end
                end)
            if closed then return end
            if not ok or type(result) ~= "table" then
                result = { state = "unavailable", message = "Writable groups could not be loaded. Reload to try again." }
            end
            displayResult(properties, result)
            properties.busy = false
            properties.canReload = true
            dependencies.logState(properties.state)
        end)
    end
    return { reload = reload, close = close, isCancelled = cancelled }
end

function Browser.run()
    LrFunctionContext.callWithContext("FGA writable group browser", function(context)
        local properties = LrBinding.makePropertyTable(context)
        local session = Browser.newSession(properties, Controller.discoveryDependencies(),
            Client.discoverStored, LrTasks)
        context:addCleanupHandler(session.close)
        local factory = LrView.osFactory()
        local bind = LrView.bind
        local contents = factory:column {
            bind_to_object = properties,
            spacing = factory:control_spacing(),
            factory:static_text {
                title = "Browse writable Flickr groups. Highlighting a row only inspects the list; it does not select a submission target.",
                width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1,
            },
            factory:static_text { title = bind "status", width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1 },
            factory:static_text { title = bind "observed", width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1 },
            factory:simple_list {
                items = bind "items", value = bind "highlight", allows_multiple_selection = false,
                width = 700, height = 350, fill_horizontal = 1, fill_vertical = 1,
            },
            factory:push_button { title = "Reload groups", enabled = bind "canReload", action = session.reload },
            factory:static_text {
                title = "Reload follows the service freshness policy: snapshots up to 15 minutes old are reused; older snapshots may start or join one refresh. No automatic repeat refresh runs here.",
                width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1,
            },
        }
        session.reload()
        LrDialogs.presentModalDialog {
            title = "FGA-LrC15 — Writable Flickr groups", contents = contents,
            actionVerb = "Close", cancelVerb = "< exclude >", resizable = true,
        }
        session.close()
    end)
end

return Browser
