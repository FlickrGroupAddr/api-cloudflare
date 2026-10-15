-- Native hierarchy/observer fixture only; actual SDK rendering still needs host evidence.
local pluginPath = assert(arg[1], "Pass the .lrplugin directory")
package.path = pluginPath .. "/?.lua;" .. package.path
local checks, tasks, logs, cleanup = 0, {}, {}, {}
local function check(value, message) assert(value, message); checks = checks + 1 end
local function properties()
    local values, observers = {}, {}
    return setmetatable({}, {
        __index = function(_, key)
            if key == "addObserver" then
                return function(_, name, fn) observers[name] = fn end
            end
            return values[key]
        end,
        __newindex = function(_, key, value)
            local previous = values[key]
            values[key] = value
            if previous ~= value and observers[key] then observers[key]() end
        end,
    })
end
local methods = { column = true, row = true, static_text = true, push_button = true,
    edit_field = true, simple_list = true, scrolled_view = true }
local factory = setmetatable({ control_spacing = function() return 8 end }, { __index = function(_, kind)
    check(methods[kind], "SDK control is documented")
    return function(_, props)
        if kind == "scrolled_view" or kind == "simple_list" then
            check(type(props.width) == "number" and type(props.height) == "number", "numeric viewport dimensions")
        end
        if kind == "static_text" and type(props.title) == "table" then
            local key = props.title.key
            local height = key == "detailName" and 1 or key == "detailIdLines" and 2 or -1
            check(props.height_in_lines == height and type(props.width_in_chars) == "number",
                "dynamic text uses documented wrapping or explicit reserved lines")
        end
        props._kind = kind
        return props
    end
end })
local function collect(view, kind, found)
    found = found or {}
    if view._kind == kind then found[#found + 1] = view end
    for _, child in ipairs(view) do collect(child, kind, found) end
    return found
end
local longName = string.rep("\240\159\140\133", 1024)
local discoverCalls = 0
local detailDialogs = 0
local discover = function()
    discoverCalls = discoverCalls + 1
    local groups = {}
    for i = 1, 376 do groups[i] = { flickrGroupId = "id-" .. i, displayName = "Group " .. i } end
    groups[1].displayName = longName
    return {
        state = "complete", groups = groups, snapshotStatus = "stale_refresh_failed",
        refreshedAt = "2026-10-15T12:00:00Z", refreshFailedAt = "2026-10-15T12:01:00Z", snapshotRevision = 8,
    }
end
package.loaded.ConnectionCore = {}
package.loaded.ConnectionController = { discoveryDependencies = function() return {
    retrieve = function() error("UI may not read credentials") end,
    logState = function(state) logs[#logs + 1] = state end,
} end }
package.loaded.GroupDiscoveryClient = { new = function() return { discoverStored = discover } end }
local lastProperties
local sdk = {
    LrView = { osFactory = function() return factory end, bind = function(key) return { key = key } end },
    LrBinding = { makePropertyTable = properties },
    LrTasks = {
        startAsyncTask = function(fn) tasks[#tasks + 1] = coroutine.create(fn) end,
        pcall = function(fn, ...) return true, fn(...) end,
    },
    LrFunctionContext = { callWithContext = function(_, fn)
        fn({ addCleanupHandler = function(_, handler) cleanup[#cleanup + 1] = handler end })
        for _, handler in ipairs(cleanup) do handler() end
    end },
    LrDialogs = { presentModalDialog = function(dialog)
        if dialog.title == "Flickr group details" then
            detailDialogs = detailDialogs + 1
            local scroll = collect(dialog.contents, "scrolled_view")
            check(#scroll == 1 and scroll[1].height == 180, "complete name is in a bounded detail viewport")
            local name = collect(scroll[1], "static_text")
            check(#name == 1 and name[1].title == longName and name[1].height_in_lines == -1,
                "detail modal measures all rawUnicode name text at control creation")
            local labels = collect(dialog.contents, "static_text")
            check(labels[#labels].height_in_lines == 2 and labels[#labels].title == "id-1",
                "populated detailID reserves two lines outside detail scroll")
            return "ok"
        end
        check(dialog.resizable == true and dialog.actionVerb == "Close", "browse-only resizable modal")
        check(dialog.cancelVerb == "< exclude >", "documented excluded duplicate cancel button")
        local p = dialog.contents.bind_to_object
        lastProperties = p
        check(p.state == "loading" and not p.canSearch, "native view starts without partial searchable results")
        check(coroutine.resume(tasks[1]), "initial async task completes")
        check(#p.items == 376 and p.state == "stale", "native view displays complete stale snapshot")
        check(#collect(dialog.contents, "simple_list") == 1 and #collect(dialog.contents, "scrolled_view") == 0,
            "one browse list with exactID visible outside any scroll")
        local idControl
        for _, control in ipairs(dialog.contents) do
            if control._kind == "static_text" and type(control.title) == "table"
                and control.title.key == "detailIdLines" then idControl = control end
        end
        check(idControl and idControl.height_in_lines == 2, "exactID has fixed visible height outside name scroll")
        local search = collect(dialog.contents, "edit_field")
        check(#search == 1 and search[1].immediate == true and search[1].value.key == "query", "documented immediate local search binding")
        p.query = "id-1"
        check(#p.items > 0 and #p.items < 376 and p.state == "stale", "observer filters without resetting stale status")
        p.highlight = { "id-1" }
        check(p.detailName == longName and p.detailId == "Exact Flickr group ID: id-1", "native highlight observer exposes full text")
        check(p.detailIdLines == "id-1" and p.canInspect, "reservedID visible and raw-name inspector enabled")
        local buttons = collect(dialog.contents, "push_button")
        check(#buttons == 3 and buttons[1].title == "Clear search" and buttons[2].title == "Inspect full group name"
            and buttons[3].title == "Reload groups", "only browse controls exposed")
        buttons[2].action()
        check(detailDialogs == 1, "inspector opens populated native modal")
        p.query = "missing literal [%]"
        check(#p.items == 0 and p.state == "stale" and p.detailId == "", "zero matches clears detail and keeps stale state")
        buttons[2].action()
        check(detailDialogs == 1 and not p.canInspect, "no hidden stale detail modal after filter clears highlight")
        buttons[1].action()
        check(p.query == "" and #p.items == 376, "native clear button restores snapshot")
        buttons[3].action()
        check(#tasks == 2 and p.state == "loading" and #p.items == 0 and not p.canSearch, "reload clears old full detail and search authority")
        return "ok"
    end },
}
function import(name) return assert(sdk[name], "Unexpected SDK import: " .. name) end
local Browser = require "GroupBrowser"
Browser.run()
check(coroutine.resume(tasks[2]), "task scheduled before closure safely returns")
check(discoverCalls == 1 and lastProperties.state == "loading", "closed task makes no second discovery and cannot mutate view")
check(table.concat(logs, ",") == "loading,stale,loading,cancelled", "diagnostic events contain only bounded state codes")
print("Group browser native hierarchy fixtures: " .. checks .. " checks passed")
