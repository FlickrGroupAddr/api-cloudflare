"""Independent filter/layout/selected-set review; no native host qualification."""

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
        local M = dofile(model_path)
        local probe = {name = 'One two [%].*', id = 'Exact-ID'}
        assert(M.matches(probe, ' '), 'space must remain a literal query')
        assert(M.matches(probe, '[%].*'), 'punctuation must be literal')
        assert(not M.matches(probe, '^One'), 'query must not act as Lua pattern')
        assert(M.matches(probe, 'exact-id'), 'ID matching remains case-insensitive')
        assert(not M.matches(probe, ' One'), 'leading whitespace must not be trimmed')
        assert(M.mode == nil, 'mutable mode API must be removed')
        for _, kind in ipairs({'new', 'bound', 'existing'}) do
            local s = M.fixture(kind)
            assert(s.choice == nil, 'fixture retains latent mutable choice')
            s.choice = 'groups' -- stale legacy field must have no authority
            assert(M.choice(s) == 'none')
            assert(M.canConfirm(s) == (kind == 'new'))
            local empty = M.result(s, 'ok')
            assert((empty ~= nil) == (kind == 'new'))
            if empty then assert(empty.choice == 'none' and #empty.ids == 0) end
            assert(M.toggle(s, 'fixture-0374@N00', true))
            s.choice = 'none'
            assert(M.choice(s) == 'groups' and M.canConfirm(s))
            assert(#M.result(s, 'ok').ids == 1)
            assert(M.toggle(s, 'fixture-0374@N00', false))
            assert(M.choice(s) == 'none')
            assert(M.canConfirm(s) == (kind == 'new'))
            s.selected['unknown-id'] = true
            assert(not M.canConfirm(s) and M.result(s, 'ok') == nil)
            assert(M.result(s, 'cancel') == nil)
        end
        local s = M.fixture('bound')
        for _, id in ipairs({'fixture-0001@N00', 'fixture-0002@N00',
            'fixture-0003@N00', 'fixture-0004@N00'}) do
            assert(not M.toggle(s, id, true))
            s.selected[id] = true
            assert(not M.canConfirm(s) and M.result(s, 'ok') == nil)
            s.selected[id] = nil
        end
        for _, kind in ipairs({'loading', 'stale', 'unavailable', 'contradictory'}) do
            local bad = M.fixture(kind)
            bad.choice = 'none'
            assert(not M.canConfirm(bad) and M.result(bad, 'ok') == nil)
        end
    """)
    lua.execute(r"""
        local M = dofile(model_path)
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
                share = function(key) return 'share:' .. key end,
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
                    assert(options.actionVerb == p.actionTitle, 'inaccurate initial fallback')
                    assert(options.actionBinding.title.bind_to_object == p)
                    assert(options.actionBinding.title.key == 'actionTitle')
                    assert(options.actionBinding.enabled.bind_to_object == p)
                    assert(options.actionBinding.enabled.key == 'allowed')
                    assert(#find(options.contents, 'radio_button') == 0, 'radios remain')
                    assert(observers.choice == nil and p.choice == nil, 'mutable UI choice remains')
                    local left, right = lists[1], lists[2]
                    assert(left.width == nil and right.width == nil, 'fixed list width')
                    assert(left.fill_horizontal == .5 and right.fill_horizontal == .5)
                    assert(left.height == right.height)
                    assert(options.contents.width == nil and options.contents.fill_horizontal == 1)
                    local function ancestors(view, target, path)
                        path = path or {}
                        if view == target then return path end
                        for _, child in ipairs(view) do
                            local nextPath = {}; for i,v in ipairs(path) do nextPath[i]=v end
                            nextPath[#nextPath+1] = view
                            local result = ancestors(child, target, nextPath)
                            if result then return result end
                        end
                    end
                    local leftParents = ancestors(options.contents, left)
                    local rightParents = ancestors(options.contents, right)
                    local outer = leftParents[#leftParents]
                    assert(outer == rightParents[#rightParents] and #outer == 3)
                    assert(outer[1] == left and outer[3] == right,
                        'both lists must be direct siblings in one shared row')
                    assert(outer.fill_horizontal == 1 and outer.width == nil)
                    assert(outer[2].width == 90 and outer[2].height == 220)
                    local index
                    for i, child in ipairs(options.contents) do
                        if child == outer then index = i end
                    end
                    local header, footer = options.contents[index-1], options.contents[index+1]
                    assert(header.kind == 'row' and footer.kind == 'row')
                    for _, row in ipairs({header, footer}) do
                        assert(row.fill_horizontal == 1 and row.spacing == outer.spacing)
                        assert(row[2].width == 90 and #row == 3)
                        for _, side in ipairs({row[1], row[3]}) do
                            assert(side.width == nil and side.fill_horizontal == .5)
                            assert(side[1].kind == 'spacer' and side[1].width == 450
                                and side[1].height == 0, 'matching native list minimum')
                        end
                    end
                    assert(header[3][2].title == 'Selected additions')
                    assert(header[3][2].alignment == 'center')
                    assert(header[1][2].title == 'searchHeading'
                        and header[1][2].font == '<system/bold>')
                    assert(header[1][4].title == 'filterStatus')
                    assert(header[1][4].tooltip == 'searchSummary')
                    assert(footer[3][2].title == 'summary', 'summary directly under right list')
                    assert(not left.allows_multiple_selection)
                    assert(not right.allows_multiple_selection)
                    local edits = find(options.contents, 'edit_field')
                    assert(#edits == 1, 'exactly one query field required')
                    local edit = edits[1]
                    assert(edit.width == nil and edit.fill_horizontal == 1)
                    local editParents = ancestors(options.contents, edit)
                    assert(editParents[#editParents].width == nil)
                    assert(editParents[#editParents].fill_horizontal == 1)
                    assert(edit.immediate == true, 'query must notify every change')
                    local add, remove, clear
                    for _, button in ipairs(find(options.contents, 'push_button')) do
                        if button.title == 'Add →' then add = button end
                        if button.title == '← Remove' then remove = button end
                        if button.title == 'Clear filter' then clear = button end
                    end
                    assert(add and remove and clear, 'explicit move/clear buttons required')
                    local clearParents = ancestors(options.contents, clear)
                    assert(clearParents[#clearParents] == editParents[#editParents]
                        and clearParents[#clearParents].kind == 'row',
                        'Clear filter must share the query field row')
                    assert(add.width == 90 and remove.width == add.width)
                    local buttonParents = ancestors(options.contents, add)
                    local center = buttonParents[#buttonParents]
                    assert(center.place_vertical == .5)
                    assert(buttonParents[#buttonParents-1].height == left.height)
                    assert(buttonParents[#buttonParents-1] == outer[2])
                    assert(header[1][3] == editParents[#editParents])
                    local boldStatus = false
                    for _, view in ipairs(find(options.contents, 'static_text')) do
                        if view.title == 'filterStatus' then
                            assert(view.font == '<system/bold>' and view.tooltip == 'searchSummary')
                            assert(view.text_color == nil, 'filter must not rely on color')
                            assert(view.height == nil, 'concise single-line count')
                            boldStatus = true
                        end
                    end
                    assert(boldStatus and clear.enabled == 'filterActive')
                    assert(observers[left.value] and observers[right.value],
                        'highlight must reveal full name/NSID')
                    if fixture_kind == 'new' then
                        local byID = {}; for _, row in ipairs(p[left.items]) do
                            byID[row.value] = row
                            assert(row.title:sub(-(#row.value+3)) == ' [' .. row.value .. ']')
                            assert(row.title:sub(1,1) ~= '[')
                        end
                        for _, id in ipairs({'fixture-0374@N00', 'fixture-0375@N00',
                            'fixture-0376@N00'}) do
                            local before = #p[right.items]
                            p[left.value] = {id}; flush()
                            assert(p.highlightDetail == 'Highlighted group: ' .. byID[id].title)
                            assert(#p[right.items] == before, 'highlight moved an addition')
                        end
                        assert(byID['fixture-0374@N00'].title ~= byID['fixture-0375@N00'].title)
                        assert(left.tooltip == 'highlightDetail'
                            and right.tooltip == 'highlightDetail')
                        local details = false
                        for _, view in ipairs(find(options.contents, 'static_text')) do
                            if view.title == 'highlightDetail' then
                                assert(view.height_in_lines == -1 and view.fill_horizontal == 1)
                                assert(view.tooltip == 'highlightDetail'); details = true
                            end
                        end
                        assert(details, 'wrapped full-name/ID detail missing')
                    end
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
                        local title_before = p.actionTitle
                        p[list.value] = {id}; flush()
                        assert(#p[right.items] == before, 'highlight caused automatic move')
                        assert(p.actionTitle == title_before, 'highlight changed action title')
                        local button = list == left and add or remove
                        button.action(button); flush()
                    end
                    local function count(n, allowed)
                        assert(#p[right.items] == n, 'unexpected selected count')
                        assert(p.allowed == allowed, 'incorrect confirmation bounds')
                        local eligible = 0
                        local fixture = M.fixture(fixture_kind)
                        for _, group in ipairs(fixture.groups) do
                            if M.code(fixture, group) == 'eligible' then eligible = eligible + 1 end
                        end
                        local expectedFilter = string.format('%d matches / %d total',
                            #p[left.items], eligible)
                        if not M.valid(fixture) then
                            local state = fixture_kind == 'loading' and 'Loading group data'
                                or 'Group data unavailable'
                            expectedFilter = state
                            assert(p.searchSummary:find('counts are unknown', 1, true),
                                'incomplete projections must not claim complete empty counts')
                        end
                        assert(p.filterStatus == expectedFilter,
                            'filter counts or label are misleading')
                        local groups = n .. (n == 1 and ' group' or ' groups')
                        local expected = fixture_kind == 'new'
                            and (n == 0 and 'Save for publish: no groups'
                                or 'Save for publish: ' .. groups)
                            or 'Queue for ' .. groups
                        assert(p.actionTitle == expected, 'inaccurate action title')
                    end
                    flush()
                    if fixture_kind == 'new' then
                        count(0, true)
                        local initialAvailable = #p[left.items]
                        for _, query in ipairs({' ', '%', '[', 'Shared', 'fixture-0374@N00'}) do
                            p[edit.value] = query; flush()
                            assert(p.filterActive == true, 'all nonempty queries must be active')
                            assert(p.searchHeading:find('FILTERED', 1, true),
                                'filtered text missing')
                            local expected = 0
                            for _, group in ipairs(M.fixture('new').groups) do
                                if M.matches(group, query) then expected = expected + 1 end
                            end
                            assert(#p[left.items] == expected, 'query must remain literal')
                            count(0, true)
                            clear.action(clear); flush()
                            assert(p[edit.value] == '' and not p.filterActive)
                            assert(#p[left.items] == initialAvailable, 'clear must restore rows')
                            count(0, true)
                        end
                        -- Clear synchronously before old query events are delivered.
                        p[left.value] = {'fixture-0374@N00'}
                        p[edit.value] = 'no-match-query'; clear.action(clear)
                        add.action(add); flush(); count(0, true)
                        assert(p[edit.value] == '' and not p.filterActive)
                        assert(#p[left.items] == initialAvailable)
                        p.choice = 'groups'; flush(); count(0, true)
                        click(left, 'fixture-0374@N00')
                        -- Hypothetical native adjacent selection cannot cascade.
                        p[left.value] = {'fixture-0375@N00'}; flush(); count(1, true)
                        click(left, 'fixture-0375@N00'); count(2, true)
                        assert(#p[left.items] == 374, 'available excludes selected')
                        p[edit.value] = 'zero-match-filter'; flush(); count(2, true)
                        assert(#p[left.items] == 0 and p.filterActive)
                        assert(p.searchSummary:lower():find('filter', 1, true),
                            'zero match must attribute empty list to filter')
                        clear.action(clear); flush(); count(2, true)
                        assert(#p[left.items] == 374 and not p.filterActive)
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
                        -- Every Remove including the last one leaves Save enabled.
                        p.choice = 'none'; flush(); count(2, true)
                        click(right, 'fixture-0374@N00'); count(1, true)
                        click(right, 'fixture-0375@N00'); count(0, true)
                        p[left.value] = {'fixture-0374@N00'}
                        p[edit.value] = 'nothing matches this'
                        -- Button action before pending query callback must not add stale row.
                        add.action(add); flush(); count(0, true)
                        p[edit.value] = ''; flush()
                        click(left, 'fixture-0374@N00')
                        click(left, 'fixture-0375@N00'); count(2, true)
                        p.choice = 'unexpected legacy value'; flush(); count(2, true)
                        click(right, 'fixture-0374@N00')
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
                        add.action(add); flush(); count(60, true)
                        p[left.value] = {'unknown-id'}; add.action(add); flush()
                        count(60, true)
                        -- Repeated removals clear every prior addition, including hidden ones.
                        p[edit.value] = 'nothing matches'; flush()
                        while #p[right.items] > 0 do
                            click(right, p[right.items][1].value)
                        end
                        count(0, false)
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
                        p[edit.value] = ' '; flush(); count(0, false)
                        assert(p.filterActive and p.searchHeading:find('FILTERED', 1, true))
                        clear.action(clear); flush(); count(0, false)
                        assert(not p.filterActive and #p[left.items] == 0)
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
    for kind in (
        "new",
        "bound",
        "existing",
        "bound59",
        "empty",
        "loading",
        "stale",
        "unavailable",
        "contradictory",
    ):
        for deferred in (False, True):
            run(bundle_path, model_path, kind, deferred)
    print(
        "PASS: literal filter/clear/count/layout invariants "
        "and 18 sync/deferred selected-set UI scenarios"
    )
