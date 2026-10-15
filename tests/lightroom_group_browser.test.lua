-- Lua 5.1 fixture harness: SDK task mocks deliberately yield through the client.
local pluginPath = assert(arg[1], "Pass the .lrplugin directory")
package.path = pluginPath .. "/?.lua;" .. package.path
local sdk = {}
function import(name) return sdk[name] or {} end
package.loaded.ConnectionController = {}
package.loaded.ConnectionCore = {}
package.loaded.GroupDiscoveryClient = { new = function() return {} end }
local Browser = require "GroupBrowser"
local total = 0
local function check(value, message)
    assert(value, message)
    total = total + 1
end

local function fixture(discover)
    local props, queue, logs = {}, {}, {}
    local calls = 0
    local dependencies = {
        retrieve = function() error("UI must not read credentials itself") end,
        logState = function(state) logs[#logs + 1] = state end,
    }
    local tasks = {
        startAsyncTask = function(fn) queue[#queue + 1] = coroutine.create(fn) end,
        pcall = function(fn, ...)
            calls = calls + 1
            return true, fn(...)
        end,
    }
    local session = Browser.newSession(props, dependencies, discover, tasks)
    return props, session, queue, logs, function() return calls end
end

local function complete(status, groups)
    return {
        state = "complete", groups = groups or {}, snapshotStatus = status or "fresh",
        snapshotRevision = 8, refreshedAt = "2026-10-15T12:00:00Z", refreshFailedAt = "2026-10-15T12:01:00Z",
    }
end

local props, session, queue, logs, calls = fixture(function()
    coroutine.yield("network")
    return complete("fresh", {
        {flickrGroupId = "id-b", displayName = "Zebra"},
        {flickrGroupId = "id-a", displayName = "Alpha"},
    })
end)
session.reload()
session.reload()
check(#queue == 1 and props.state == "loading" and not props.canReload, "single in-flight task")
check(coroutine.resume(queue[1]), "task starts")
check(props.state == "loading" and #props.items == 0, "no partial result while request yields")
check(coroutine.resume(queue[1]), "task resumes across SDK safe protection")
check(calls() == 1 and props.state == "available", "uses injected yield-safe task protection")
check(props.items[1].value == "id-a" and props.items[2].value == "id-b", "sorted names retain exact IDs")
check(string.find(props.observed, "2026%-10%-15T12:00:00Z") ~= nil, "observation timestamp visible")
check(logs[2] == "available", "logs bounded UI state only")

for _, status in ipairs({"fresh", "stale_refreshing", "stale_refresh_failed"}) do
    local p, s, q = fixture(function() return complete(status) end)
    s.reload()
    check(coroutine.resume(q[1]), "empty snapshot task")
    local expected = status == "fresh" and "empty" or (status == "stale_refreshing" and "refreshing" or "stale")
    check(p.state == expected, "stale empty snapshot never reported fresh empty")
end

local p, s, q = fixture(function() return { state = "retryable", message = "Service unavailable." } end)
s.reload()
check(coroutine.resume(q[1]), "failure task")
check(p.state == "unavailable" and #p.items == 0 and p.canReload, "failure unavailable with explicit retry")

local progress, progressSession, progressQueue = fixture(function(_, _, _, _, _, _, _, onProgress)
    onProgress("refreshing")
    coroutine.yield()
    return complete()
end)
progressSession.reload()
check(coroutine.resume(progressQueue[1]) and progress.state == "refreshing" and #progress.items == 0,
    "pending server refresh is explicit without fabricated empty snapshot")
check(coroutine.resume(progressQueue[1]) and progress.state == "empty", "pending refresh publishes only complete snapshot")

local afterClose, cancel, pending, closeLogs = fixture(function(_, _, _, _, isCancelled)
    coroutine.yield()
    check(isCancelled(), "client observes dialog cancellation")
    return complete()
end)
cancel.reload()
check(coroutine.resume(pending[1]), "start cancellable task")
cancel.close()
local before = afterClose.status
check(coroutine.resume(pending[1]), "finish cancelled task")
check(afterClose.status == before and afterClose.state == "loading", "closed view is never mutated")
cancel.reload()
check(#pending == 1 and closeLogs[2] == "cancelled", "closed session cannot start work")

local beforeStart, closedSession, queued = fixture(function() error("must not start after close") end)
closedSession.reload()
closedSession.close()
check(coroutine.resume(queued[1]), "task cancelled before scheduling makes no request")

local failed = {}
local failedTask
local failedSession = Browser.newSession(failed, { logState = function() end }, function() end, {
    startAsyncTask = function(fn) failedTask = fn end,
    pcall = function() return false, "credential=secret body=private" end,
})
failedSession.reload()
failedTask()
check(failed.state == "unavailable" and not string.find(failed.status, "secret"), "exceptions never enter view")

local readCount, recorded = 0, {}
sdk.LrPasswords = { retrieve = function(key, _, pluginId)
    readCount = readCount + 1
    check(key == "current" and pluginId == "major-specific", "adapter preserves exact secure-store namespace")
    return "private-credential"
end }
sdk.LrPrefs = { prefsForPlugin = function() return { installationId = "installation-1" } end }
sdk.LrLogger = function() return {
    enable = function() end,
    info = function(_, message) recorded[#recorded + 1] = message end,
} end
sdk.LrHttp = { get = function() end, post = function() end }
sdk.LrTasks = { sleep = function() end }
package.loaded.ConnectionCore = { CURRENT_KEY = "current", PLUGIN_ID = "major-specific" }
package.loaded.dkjson = assert(loadfile((arg[2] or pluginPath) .. "/dkjson.lua"))()
local Controller = assert(loadfile(pluginPath .. "/ConnectionController.lua"))()
local deps = Controller.discoveryDependencies()
check(readCount == 0 and deps.expectedInstallationId == "installation-1", "adapter captures identity without fetching credentials")
check(deps.retrieve("current") == "private-credential", "credential returned only to injected client")
local decoded = deps.decode('{"items":[],"next":null}')
check(decoded.next == deps.jsonNull and getmetatable(decoded.items).__jsontype == "array", "strict decoder preserves null and array distinctions")
check(deps.decode('{} trailing-data') == nil and deps.decode('{') == nil, "malformed or trailing JSON rejected")
deps.logState("private-credential")
check(recorded[#recorded] == "discovery state=unavailable", "untrusted diagnostic state replaced by allowlisted code")
print("Group browser fixtures: " .. total .. " checks passed")
