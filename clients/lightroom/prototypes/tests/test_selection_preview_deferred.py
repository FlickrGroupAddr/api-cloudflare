"""Reproduce delayed checkbox notifications racing a newer radio choice."""

from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime


def run(bundle: Path, source: str) -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    assert lua.lua_version == (5, 1)
    cast(Any, lua.globals()).bundle_path = str(bundle)
    cast(Any, lua.globals()).preview_source = source
    lua.execute(
        """
        local pending, callbacks = {}, {}
        local function flush()
            local limit = 0
            while #pending > 0 do
                limit = limit + 1
                assert(limit < 10000, 'Observer loop did not converge')
                table.remove(pending,1)()
            end
        end
        local function propertyTable()
            local values, observers = {}, {}
            callbacks = observers
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
                    if old ~= value and observers[key] then
                        pending[#pending+1] = observers[key]
                    end
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
                    if dialogs == 1 then p.kind = 'new'; return 'ok' end
                    flush()
                    local rows = boxes(options.contents)
                    if dialogs == 2 then
                        assert(#rows == 376 and p.choice == 'none' and p.allowed)
                        p.choice = 'groups'; flush()
                        assert(not p.allowed)
                        p[rows[1].value] = true; flush()
                        assert(p.allowed)
                        p[rows[1].value] = false; flush()
                        assert(not p.allowed and p.choice == 'groups')
                        -- A delayed duplicate unchecked notification arrives
                        -- after the user changes the bound radio value, before
                        -- its radio observer runs. It must not restore groups.
                        pending[#pending+1] = callbacks[rows[1].value]
                        p.choice = 'none'; flush()
                        assert(p.choice == 'none' and p.allowed,
                            'Delayed checkbox notification overwrote newer None choice')
                        assert(p.summary:find('0 selected',1,true))
                        p[rows[1].value] = true; flush()
                        p[rows[1].value] = false
                        p.choice = 'none'; flush()
                        assert(p.choice == 'none' and p.allowed,
                            'Delayed changed-uncheck notification overwrote newer None choice')
                        p[rows[1].value] = true
                        p[rows[2].value] = true
                        flush()
                        assert(p.summary:find('2 selected',1,true))
                        p.query = 'fixture-0001@N00'
                        return 'other'
                    elseif dialogs == 3 then
                        assert(#rows == 1 and p.summary:find('2 selected',1,true))
                        assert(p[rows[1].value] == true)
                        p.choice = 'none'; flush()
                        assert(p.choice == 'none' and p.allowed)
                        assert(p[rows[1].value] == false)
                        assert(p.summary:find('0 selected',1,true))
                        p.query = ''
                        return 'other'
                    end
                    assert(dialogs == 4 and #rows == 376)
                    for _, row in ipairs(rows) do assert(p[row.value] == false) end
                    assert(p.choice == 'none' and p.allowed)
                    return 'cancel'
                end,
            },
        }
        function import(name) return assert(sdk[name], 'Unexpected import: '..name) end
        _PLUGIN = {path = bundle_path}
        assert(loadstring(preview_source))()
        assert(dialogs == 4)
        """
    )


def main() -> None:
    bundle = Path(__file__).resolve().parents[1] / "FGA-LrC15-SelectionPreview.lrplugin"
    source = (bundle / "Preview.lua").read_text()
    guard = "if (p[key] == true) == (s.selected[group.id] == true) then return end"
    choice_guard = "if p[key] == true then p.choice = s.choice end"
    assert guard in source
    assert choice_guard in source
    try:
        run(bundle, source.replace(guard, "").replace(choice_guard, "p.choice = s.choice"))
    except Exception as error:
        assert "overwrote newer None choice" in str(error), error
    else:
        raise AssertionError("Removing the observer guard must reproduce the radio regression")
    try:
        run(bundle, source.replace(choice_guard, "p.choice = s.choice"))
    except Exception as error:
        assert "changed-uncheck notification overwrote newer None choice" in str(error), error
    else:
        raise AssertionError("An actual deferred uncheck must also preserve the newer radio choice")
    run(bundle, source)
    print("PASS: delayed observer regression, guard mutation, bulk clear and hidden choices")


if __name__ == "__main__":
    main()
