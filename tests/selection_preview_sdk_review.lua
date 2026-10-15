-- Independent structural/observer review. This mock does not prove native layout.
local path = assert(arg[1], "Pass selection preview .lrplugin path")
_PLUGIN = { path = path }
local currentKind, dialogs, checks = nil, 0, 0
local function check(value, message) assert(value, message); checks = checks + 1 end
local function propertyTable()
    local values, observers = {}, {}
    local methods = { addObserver = function(_, key, fn) observers[key] = fn end }
    return setmetatable({}, {
        __index = function(_, key) return methods[key] or values[key] end,
        __newindex = function(_, key, value)
            local old = values[key]
            values[key] = value
            if old ~= value and observers[key] then observers[key]() end
        end,
    })
end
local factory = setmetatable({}, { __index = function(_, kind)
    return function(_, props)
        if kind == "static_text" and props.height_in_lines and props.height_in_lines > 1 then
            error("Multiline static_text must explicitly enable documented wrapping with height_in_lines=-1")
        end
        if kind == "scrolled_view" then
            check(type(props.width) == "number" and type(props.height) == "number", "numeric scrolled viewport")
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
local sdk = {
    LrBinding = { makePropertyTable = propertyTable },
    LrView = { bind = function(key) return key end, osFactory = function() return factory end },
    LrTasks = { startAsyncTask = function(fn) fn() end },
    LrFunctionContext = { callWithContext = function(_, fn) return fn({}) end },
    LrPathUtils = { child = function(left, right) return left .. "/" .. right end },
    LrDialogs = {
        message = function() error("Cancellation must not produce a confirmation summary") end,
        presentModalDialog = function(options)
            dialogs = dialogs + 1
            local props = options.contents.bind_to_object
            if dialogs == 1 then props.kind = currentKind; return "ok" end
            local boxes = collect(options.contents, "checkbox")
            if currentKind == "new" or currentKind == "bound" or currentKind == "existing" then
                local expected = currentKind == "new" and 376 or 372
                check(#boxes == expected, "all eligible groups rendered in ordinary checkbox hierarchy")
                check(props.allowed == (currentKind == "new"), "zero boundary matches photo mode")
                props[boxes[1].value] = true
                check(props.allowed and props.choice == "groups", "checking one enables group mode")
                for i = 2, 60 do props[boxes[i].value] = true end
                check(props.allowed, "60 checked boxes permit confirmation")
                props[boxes[61].value] = true
                check(not props.allowed, "61 checked boxes disable confirmation")
                props[boxes[61].value] = false
                check(props.allowed, "return to60 restores confirmation")
                if currentKind == "new" then
                    props.choice = "none"
                    for _, box in ipairs(boxes) do check(props[box.value] == false, "none clears every visible checkbox") end
                    check(props.allowed, "unpublished none permits confirmation")
                end
            else
                check(#boxes == 0 and not props.allowed, "unavailable or bound-empty exposes no selectable rows")
            end
            return "cancel"
        end,
    },
}
function import(name) return assert(sdk[name], "Unsafe or undocumented import: " .. name) end
for _, kind in ipairs({"new", "bound", "existing", "loading", "empty", "stale", "unavailable", "contradictory"}) do
    currentKind, dialogs = kind, 0
    assert(loadfile(path .. "/Preview.lua"))()
    check(dialogs == 2, "launcher plus single cancelled view")
end
print("Independent preview view/observer review: " .. checks .. " checks passed")
