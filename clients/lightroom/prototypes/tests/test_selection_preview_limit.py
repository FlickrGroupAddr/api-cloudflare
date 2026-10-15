"""Lua 5.1 model and native-view observer proof for the synthetic 59 fixture."""

from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime


def main() -> None:
    bundle = Path(__file__).resolve().parents[1] / "FGA-LrC15-SelectionPreview.lrplugin"
    lua = LuaRuntime(unpack_returned_tuples=True)
    assert lua.lua_version == (5, 1)
    cast(Any, lua.globals()).bundle_path = str(bundle)
    lua.execute(
        """
        local M = dofile(bundle_path .. '/SelectionModel.lua')
        local s = M.fixture('bound59')
        assert(s.bound and M.valid(s) and s.choice == 'groups')
        assert(#s.groups == 376 and M.count(s) == 59 and M.canConfirm(s))
        local eligible = 0
        for _, g in ipairs(s.groups) do
            if M.code(s, g) == 'eligible' then eligible = eligible + 1 end
            if s.selected[g.id] then assert(M.code(s, g) == 'eligible') end
        end
        assert(eligible == 372)
        assert(not s.selected['fixture-0007@N00'])
        assert(not s.selected['fixture-0013@N00'])
        assert(M.toggle(s, 'fixture-0007@N00', true))
        assert(M.count(s) == 60 and M.canConfirm(s))
        assert(M.toggle(s, 'fixture-0013@N00', true))
        assert(M.count(s) == 61 and not M.canConfirm(s) and M.result(s, 'ok') == nil)
        assert(M.toggle(s, 'fixture-0013@N00', false))
        assert(M.count(s) == 60 and M.canConfirm(s))
        assert(M.result(s, 'cancel') == nil)
        assert(M.count(M.fixture('bound59')) == 59)
        assert(M.count(M.fixture('bound')) == 0)
        assert(M.count(M.fixture('new')) == 0)

        local function propertyTable()
            local values, observers = {}, {}
            return setmetatable({}, {
                __index = function(_, key)
                    if key == 'addObserver' then
                        return function(_, name, fn) observers[name] = fn end
                    end
                    return values[key]
                end,
                __newindex = function(_, key, value)
                    local old = values[key]
                    values[key] = value
                    if old ~= value and observers[key] then observers[key]() end
                end,
            })
        end
        local factory = setmetatable({}, {__index = function(_, kind)
            return function(_, props) props.kind = kind; return props end
        end})
        local function boxes(view, found)
            found = found or {}
            if view.kind == 'checkbox' then found[#found+1] = view end
            for _, child in ipairs(view) do boxes(child, found) end
            return found
        end
        local dialogs = 0
        local sdk = {
            LrBinding = {makePropertyTable = propertyTable},
            LrView = {bind = function(key) return key end,
                osFactory = function() return factory end},
            LrTasks = {startAsyncTask = function(fn) fn() end},
            LrFunctionContext = {callWithContext = function(_, fn) return fn({}) end},
            LrPathUtils = {child = function(a,b) return a .. '/' .. b end},
            LrDialogs = {
                message = function() error('Cancel must not show a summary') end,
                presentModalDialog = function(options)
                    dialogs = dialogs + 1
                    local p = options.contents.bind_to_object
                    if dialogs == 1 then p.kind = 'bound59'; return 'ok' end
                    assert(options.actionVerb == 'Queue selected additions')
                    assert(options.title == 'FlickrGroupAddr — Group additions (FIXTURE PREVIEW)')
                    local rows = boxes(options.contents)
                    assert(#rows == 372)
                    assert(rows[1].title:find('fixture-0007@N00',1,true))
                    assert(rows[2].title:find('fixture-0013@N00',1,true))
                    assert(not p[rows[1].value] and not p[rows[2].value])
                    assert(p.allowed and p.summary:find('59 selected',1,true))
                    p[rows[1].value] = true
                    assert(p.allowed and p.summary:find('60 selected',1,true))
                    p[rows[2].value] = true
                    assert(not p.allowed and p.summary:find('61 selected',1,true))
                    p[rows[2].value] = false
                    assert(p.allowed and p.summary:find('60 selected',1,true))
                    return 'cancel'
                end,
            },
        }
        function import(name) return assert(sdk[name], 'Unexpected import: '..name) end
        _PLUGIN = {path = bundle_path}
        dofile(bundle_path .. '/Preview.lua')
        assert(dialogs == 2)
        """
    )
    assert "build = 4" in (bundle / "Info.lua").read_text()
    print("PASS: synthetic bound59 model and actual view observers: 59/60/61/60, cancel")


if __name__ == "__main__":
    main()
