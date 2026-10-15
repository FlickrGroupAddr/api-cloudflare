-- Independent structural/observer review. This mock does not prove native layout.
local path = assert(arg[1], "Pass selection preview .lrplugin path")
_PLUGIN = { path = path }
local currentKind, dialogs, checks = nil, 0, 0
local function check(value, message) assert(value, message); checks = checks + 1 end
local function propertyTable()
    local values, observers = {}, {}
    local methods = { addObserver = function(_, key, fn) observers[key] = fn end }
    local p
    p = setmetatable({}, {
        __index = function(_, key) return methods[key] or values[key] end,
        __newindex = function(_, key, value)
            local old = values[key]
            values[key] = value
            if old ~= value and observers[key] then observers[key](p, key, value) end
        end,
    })
    return p
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
    LrView = { share = function(key) return {shared=key} end, bind = function(key) return key end, osFactory = function() return factory end },
    LrTasks = { startAsyncTask = function(fn) fn() end },
    LrFunctionContext = { callWithContext = function(_, fn) return fn({}) end },
    LrPathUtils = { child = function(left, right) return left .. "/" .. right end },
    LrDialogs = {
        message = function() error("Cancellation must not produce a confirmation summary") end,
        presentModalDialog = function(options)
            dialogs = dialogs + 1
            local props = options.contents.bind_to_object
            if dialogs == 1 then props.kind = currentKind; return "ok" end
            local lists = collect(options.contents, "simple_list")
            local buttons = collect(options.contents, "push_button")
            check(#collect(options.contents, "radio_button") == 0, "selected list owns choice")
            check(#lists == 2 and #buttons == 3, "two lists, Clear and two explicit move buttons")
            local byTitle = {}
            for _, button in ipairs(buttons) do byTitle[button.title] = button end
            local addButton, removeButton, clearButton = byTitle["Add →"], byTitle["← Remove"], byTitle["Clear filter"]
            check(addButton and removeButton and clearButton, "all explicit actions present")
            check(lists[1].items == "availableItems" and lists[2].items == "selectedItems", "left/right binding")
            check(options.otherVerb == nil, "no distant search action")
            local edit = collect(options.contents, "edit_field")[1]
            check(edit.immediate and type(edit.validate) == "function", "per-change search callback")
            check(options.actionVerb == props.actionTitle, "truthful initial title fallback")
            check(options.actionBinding.title.bind_to_object == props
                and options.actionBinding.title.key == "actionTitle", "live action title binding")
            local function add(id) props.availableChoice = { id }; addButton.action() end
            if currentKind == "new" or currentKind == "bound" or currentKind == "existing" then
                local expected = currentKind == "new" and 376 or 372
                check(#props.availableItems == expected, "all eligible groups available")
                check(props.allowed == (currentKind == "new"), "zero boundary matches photo mode")
                check(not props.filterActive and props.filterStatus == string.format(
                    "All available: %d / %d eligible groups", expected, expected), "complete initial filter status")
                local title = props.actionTitle
                edit.validate(edit, "no possible match")
                check(props.filterActive and #props.availableItems == 0 and props.filterStatus == string.format(
                    "FILTERED: 0 available matches / %d eligible groups", expected), "visible active filter and counts")
                clearButton.action()
                check(not props.filterActive and props.query == "" and #props.availableItems == expected
                    and props.actionTitle == title and #props.selectedItems == 0, "clear in place preserves selection title")
                local ids = {}
                for i = 1, 61 do ids[i] = props.availableItems[i].value end
                props.availableChoice = { ids[1] }
                check(#props.selectedItems == 0, "highlight alone never moves")
                addButton.action()
                check(props.allowed and #props.selectedItems == 1, "Add one enables group mode")
                check(props.actionTitle == (currentKind == "new" and "Save for publish: 1 group"
                    or "Queue for 1 group"), "singular action title")
                for i = 2, 60 do add(ids[i]) end
                check(props.allowed, "60 additions permit confirmation")
                add(ids[61])
                check(not props.allowed, "61 additions disable confirmation")
                props.selectedChoice = { ids[61] }; removeButton.action()
                check(props.allowed, "return to60 restores confirmation")
                if currentKind == "new" then
                    for i = 60, 1, -1 do
                        props.selectedChoice = { ids[i] }; removeButton.action()
                    end
                    check(#props.selectedItems == 0 and #props.availableItems == expected, "removing last clears all additions")
                    check(props.allowed, "unpublished none permits confirmation")
                end
            else
                check(#props.availableItems == 0 and not props.allowed, "unavailable or bound-empty exposes no selectable rows")
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
