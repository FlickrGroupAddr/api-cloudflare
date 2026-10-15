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
    properties.observed = "Last successful observation (UTC): " .. result.refreshedAt
        .. " | Snapshot revision: " .. string.format("%.0f", result.snapshotRevision)
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
    return groups
end

-- Exposed for fixture tests; all network work stays behind the injected client.
function Browser.newSession(properties, dependencies, discover, tasks)
    local closed = false
    local allGroups
    properties.items = {}
    properties.highlight = {}
    properties.busy = false
    properties.canReload = true
    properties.state = "loading"
    properties.status = "Loading writable Flickr groups..."
    properties.observed = "No complete snapshot available."
    properties.query = ""
    properties.canSearch = false
    properties.filterSummary = "No complete snapshot to search."
    properties.detailName = "Highlight a row to read its full group name."
    properties.detailId = ""
    properties.detailIdLines = ""
    properties.canInspect = false
    local function inspect()
        if closed then return end
        properties.detailName = "Highlight a row to read its full group name."
        properties.detailId = ""
        properties.detailIdLines = ""
        properties.canInspect = false
        local id = type(properties.highlight) == "table" and properties.highlight[1] or nil
        for _, group in ipairs(allGroups or {}) do
            if group.flickrGroupId == id then
                properties.detailName = group.displayName
                properties.detailId = "Exact Flickr group ID: " .. group.flickrGroupId
                properties.detailIdLines = string.sub(group.flickrGroupId, 1, 64)
                    .. (#group.flickrGroupId > 64 and ("\n" .. string.sub(group.flickrGroupId, 65)) or "")
                properties.canInspect = true
                return
            end
        end
    end
    local function filter()
        if closed then return end
        local query = type(properties.query) == "string" and string.lower(properties.query) or ""
        local items = {}
        for _, group in ipairs(allGroups or {}) do
            if string.find(string.lower(group.displayName), query, 1, true)
                or string.find(string.lower(group.flickrGroupId), query, 1, true) then
                items[#items + 1] = {
                    title = group.displayName .. "  [" .. group.flickrGroupId .. "]", value = group.flickrGroupId,
                }
            end
        end
        properties.items = items
        properties.highlight = {}
        inspect()
        properties.canSearch = allGroups ~= nil
        properties.filterSummary = allGroups ~= nil
            and ("Showing " .. #items .. " of " .. #allGroups .. " groups in the complete snapshot.")
            or "No complete snapshot to search."
    end
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
        allGroups = nil
        filter()
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
            allGroups = displayResult(properties, result)
            filter()
            properties.busy = false
            properties.canReload = true
            dependencies.logState(properties.state)
        end)
    end
    return { reload = reload, close = close, isCancelled = cancelled, filter = filter, inspect = inspect }
end

function Browser.run()
    LrFunctionContext.callWithContext("FGA writable group browser", function(context)
        local properties = LrBinding.makePropertyTable(context)
        local session = Browser.newSession(properties, Controller.discoveryDependencies(),
            Client.discoverStored, LrTasks)
        context:addCleanupHandler(session.close)
        properties:addObserver("query", session.filter)
        properties:addObserver("highlight", session.inspect)
        local factory = LrView.osFactory()
        local bind = LrView.bind
        local function inspectFullName()
            if session.isCancelled() or not properties.canInspect then return end
            -- Populate the title before creating this control. Native bound
            -- static_text does not reliably resize after its initial title.
            LrDialogs.presentModalDialog {
                title = "Flickr group details", actionVerb = "Close", cancelVerb = "< exclude >",
                resizable = true,
                contents = factory:column {
                    spacing = factory:control_spacing(),
                    factory:scrolled_view {
                        width = 700, height = 180,
                        factory:column {
                            factory:static_text {
                                title = properties.detailName, width_in_chars = 90, height_in_lines = -1,
                            },
                        },
                    },
                    factory:static_text { title = "Exact Flickr group ID:" },
                    factory:static_text { title = properties.detailIdLines, width_in_chars = 90, height_in_lines = 2 },
                },
            }
        end
        local contents = factory:column {
            bind_to_object = properties,
            spacing = factory:control_spacing(),
            factory:static_text {
                title = "Browse writable Flickr groups. Highlighting a row only inspects the list; it does not select a submission target.",
                width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1,
            },
            factory:static_text { title = bind "status", width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1 },
            factory:static_text { title = bind "observed", width_in_chars = 90, height_in_lines = -1, fill_horizontal = 1 },
            factory:row {
                spacing = factory:control_spacing(),
                factory:static_text { title = "Find name or group ID:" },
                factory:edit_field {
                    value = bind "query", immediate = true, enabled = bind "canSearch",
                    width_in_chars = 45, fill_horizontal = 1,
                },
                factory:push_button {
                    title = "Clear search", enabled = bind "canSearch",
                    action = function() properties.query = "" end,
                },
            },
            factory:static_text { title = bind "filterSummary", width_in_chars = 90, height_in_lines = -1 },
            factory:simple_list {
                items = bind "items", value = bind "highlight", allows_multiple_selection = false,
                width = 700, height = 280, fill_horizontal = 1, fill_vertical = 1,
            },
            factory:static_text { title = "Highlighted group (read-only):" },
            factory:static_text {
                title = bind "detailName", width_in_chars = 90, height_in_lines = 1, truncation = "tail",
            },
            factory:static_text { title = "Exact Flickr group ID:" },
            factory:static_text { title = bind "detailIdLines", width_in_chars = 90, height_in_lines = 2 },
            factory:push_button {
                title = "Inspect full group name", enabled = bind "canInspect", action = inspectFullName,
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
