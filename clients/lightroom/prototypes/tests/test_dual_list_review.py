"""Independent synthetic SDK event checks; no Lightroom native qualification."""

import sys
from pathlib import Path

from lupa.lua51 import LuaRuntime


def run(bundle: Path, model: Path, fixture: str, deferred: bool) -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().bundle_path = str(bundle)
    lua.globals().model_path = str(model)
    lua.globals().fixture_kind = fixture
    lua.globals().deferred_events = deferred
    lua.execute(r"""
        local pending, observers = {}, {}
        local function flush()
            local n = 0
            while #pending > 0 do
                n = n + 1; assert(n < 10000, 'observer loop')
                table.remove(pending, 1)()
            end
        end
        local function properties()
            local values = {}; observers = {}
            return setmetatable({}, {
                __index = function(_, key)
                    if key == 'addObserver' then
                        return function(_, name, fn) observers[name] = fn end
                    end
                    return values[key]
                end,
                __newindex = function(self, key, value)
                    local old = values[key]; values[key] = value
                    if old ~= value and observers[key] then
                        local fn = observers[key]
                        local callback = function() fn(self, key, value) end
                        if deferred_events then pending[#pending+1] = callback
                        else callback() end
                    end
                end,
            })
        end
        local original_dofile = dofile
        function dofile(_) return original_dofile(model_path) end
        local factory = setmetatable({}, {__index = function(_, kind)
            return function(_, props) props.kind = kind; return props end
        end})
        local function find(view, kind, result)
            result = result or {}
            if view.kind == kind then result[#result+1] = view end
            for _, child in ipairs(view) do find(child, kind, result) end
            return result
        end
        local dialogs = 0
        local sdk = {
            LrBinding = {makePropertyTable = properties},
            LrView = {bind = function(key) return key end,
                osFactory = function() return factory end},
            LrTasks = {startAsyncTask = function(fn) fn() end},
            LrFunctionContext = {callWithContext = function(_, fn) return fn({}) end},
            LrPathUtils = {child = function(a,b) return a .. '/' .. b end},
            LrDialogs = {
                message = function() error('Cancel emitted summary') end,
                presentModalDialog = function(options)
                    dialogs = dialogs + 1
                    local p = options.contents.bind_to_object
                    if dialogs == 1 then p.kind = fixture_kind; return 'ok' end
                    local lists = find(options.contents, 'simple_list')
                    assert(#lists == 2 and options.otherVerb == nil)
                    assert(#find(options.contents, 'radio_button') == 0)
                    assert(observers.choice == nil, 'no separate choice authority')
                    local left, right = lists[1], lists[2]
                    assert(not left.allows_multiple_selection)
                    assert(not right.allows_multiple_selection)
                    local edit = find(options.contents, 'edit_field')[1]
                    assert(edit.immediate == true, 'query must notify every change')
                    local add, remove
                    for _, button in ipairs(find(options.contents, 'push_button')) do
                        if button.title == 'Add →' then add = button end
                        if button.title == '← Remove' then remove = button end
                    end
                    assert(add and remove, 'explicit center move buttons required')
                    assert(observers[left.value] == nil and observers[right.value] == nil,
                        'native highlight must never mutate selected additions')
                    local function ids(list)
                        local result = {}
                        for _, row in ipairs(p[list.items]) do
                            assert(type(row.value) == 'string', 'identity must be exact string ID')
                            assert(not result[row.value], 'duplicate exact ID')
                            result[row.value] = true
                        end
                        return result
                    end
                    local function click(list, id)
                        local before = #p[right.items]
                        p[list.value] = {id}; flush()
                        assert(#p[right.items] == before, 'highlight caused automatic move')
                        local button = list == left and add or remove
                        button.action(button); flush()
                    end
                    local function count(n, allowed)
                        assert(#p[right.items] == n, 'unexpected selected count')
                        assert(p.allowed == allowed, 'incorrect confirmation bounds')
                        local expected
                        if fixture_kind == 'new' then
                            expected = n == 0 and 'Save for publish: no groups'
                                or 'Save for publish: ' .. n .. (n == 1 and ' group' or ' groups')
                        else expected = 'Queue for ' .. n .. (n == 1 and ' group' or ' groups') end
                        assert(p.actionTitle == expected, 'action title must track selected count')
                    end
                    flush()
                    assert(options.actionVerb == p.actionTitle, 'truthful initial action fallback')
                    assert(options.actionBinding.title.bind_to_object == p)
                    assert(options.actionBinding.title.key == 'actionTitle')
                    if fixture_kind == 'new' then
                        count(0, true)
                        p.choice = 'groups'; flush(); count(0, true)
                        click(left, 'fixture-0374@N00')
                        -- Hypothetical native adjacent selection cannot cascade.
                        p[left.value] = {'fixture-0375@N00'}; flush(); count(1, true)
                        click(left, 'fixture-0375@N00'); count(2, true)
                        p[edit.value] = 'nonsense'; p[edit.value] = 'Shared'
                        p[edit.value] = 'fixture-0374@N00'; flush()
                        assert(#p[left.items] == 0 and #p[right.items] == 2,
                            'query must preserve all right-side selections')
                        click(right, 'fixture-0374@N00'); count(1, true)
                        assert(ids(left)['fixture-0374@N00'] and ids(right)['fixture-0375@N00'])
                        -- Repeat native highlight changes after query/reorder: no ID moves.
                        p[left.value] = {}; p[right.value] = {}
                        p[left.value] = {'fixture-0374@N00'}
                        p[right.value] = {'fixture-0375@N00'}
                        flush(); count(1, true)
                        p[edit.value] = ''; flush()
                        click(left, 'fixture-0374@N00'); count(2, true)
                        click(right, 'fixture-0374@N00'); count(1, true)
                        click(right, 'fixture-0375@N00'); count(0, true)
                        p[right.value] = {'fixture-0375@N00'}
                        remove.action(remove); flush(); count(0, true)
                        p[left.value] = {'fixture-0374@N00'}
                        p[edit.value] = 'nothing matches this'
                        -- Action before the pending query callback rejects a stale left row.
                        add.action(add); flush(); count(0, true)
                        p[edit.value] = ''; flush()
                        click(left, 'fixture-0374@N00')
                        click(left, 'fixture-0375@N00'); count(2, true)
                        p.choice = 'none'; flush(); count(2, true)
                        click(right, 'fixture-0374@N00'); count(1, true)
                        click(right, 'fixture-0375@N00'); count(0, true)
                    elseif fixture_kind == 'bound59' then
                        count(59, true)
                        click(left, 'fixture-0007@N00'); count(60, true)
                        p[edit.value] = 'fixture-0013@N00'; flush()
                        click(left, 'fixture-0013@N00'); count(61, false)
                        p[edit.value] = 'fixture-0003@N00'; flush()
                        assert(#p[left.items] == 0)
                        for _, id in ipairs({'fixture-0001@N00', 'fixture-0002@N00',
                            'fixture-0003@N00', 'fixture-0004@N00'}) do
                            assert(not ids(right)[id], 'protected row selectable')
                        end
                        click(right, 'fixture-0013@N00'); count(60, true)
                        p[edit.value] = ''; flush(); count(60, true)
                        -- Even malformed native events cannot select protected IDs.
                        p[left.value] = {'fixture-0003@N00'}; flush(); count(60, true)
                    elseif fixture_kind == 'bound' or fixture_kind == 'existing' then
                        count(0, false)
                        click(left, 'fixture-0007@N00'); count(1, true)
                        p[edit.value] = 'nothing matches'; flush(); count(1, true)
                        click(right, 'fixture-0007@N00'); count(0, false)
                    elseif fixture_kind == 'empty' then
                        count(0, false)
                        assert(#p[left.items] == 0)
                    else
                        count(0, false)
                        assert(#p[left.items] == 0, 'incomplete projections expose additions')
                    end
                    return 'cancel'
                end,
            },
        }
        function import(name) return assert(sdk[name], name) end
        _PLUGIN = {path = bundle_path}
        assert(loadfile(bundle_path .. '/Preview.lua'))()
        assert(dialogs == 2, 'search must not rebuild the modal')
    """)


if __name__ == "__main__":
    bundle_path = Path(sys.argv[1]).resolve()
    model_path = Path(sys.argv[2]).resolve()
    for kind in ("new", "bound", "existing", "bound59", "empty", "unavailable", "contradictory"):
        for deferred in (False, True):
            run(bundle_path, model_path, kind, deferred)
    print("PASS: 14 independent dual-list sync/deferred identity/protection/bounds scenarios")
