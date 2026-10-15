"""Fixture view-model acceptance; deliberately no Lightroom host claim."""

from pathlib import Path

from lupa.lua51 import LuaRuntime


def main() -> None:
    bundle = Path(__file__).resolve().parents[1] / "FGA-LrC15-SelectionPreview.lrplugin"
    lua = LuaRuntime(unpack_returned_tuples=True)
    assert lua.lua_version == (5, 1)
    lua.globals().model = lua.execute((bundle / "SelectionModel.lua").read_text())
    lua.execute(
        """
        local M = model
        local s = M.fixture('new')
        assert(#s.groups == 376 and M.canConfirm(s))
        local shared, long = {}, nil
        for _, g in ipairs(s.groups) do
            if g.name == 'Shared coastal photographers' then shared[#shared + 1] = g end
            if #g.name > 150 then long = g end
        end
        assert(#shared == 2 and shared[1].id == 'fixture-0374@N00')
        assert(shared[2].id == 'fixture-0375@N00' and long.id == 'fixture-0376@N00')
        assert(M.matches(shared[1], 'Shared coastal') and M.matches(shared[2], 'Shared coastal'))
        assert(M.matches(shared[1], 'fixture-0374@N00'))
        assert(not M.matches(shared[2], 'fixture-0374@N00'))
        M.toggle(s, shared[1].id, true)
        assert(M.count(s) == 1 and not s.selected[shared[2].id])
        for id in pairs(s.selected) do M.toggle(s, id, false) end
        assert(M.result(s, 'cancel') == nil)
        assert(M.choice(s) == 'none' and M.canConfirm(s))
        assert(M.result(s, 'ok').choice == 'none' and #M.result(s, 'ok').ids == 0)
        for i = 1, 60 do assert(M.toggle(s, s.groups[i].id, true)) end
        assert(M.canConfirm(s) and #M.result(s, 'ok').ids == 60)
        assert(M.toggle(s, s.groups[61].id, true))
        assert(not M.canConfirm(s) and M.result(s, 'ok') == nil)
        for id in pairs(s.selected) do M.toggle(s, id, false) end
        assert(M.count(s) == 0 and M.canConfirm(s) and M.choice(s) == 'none')
        assert(M.matches(s.groups[1], s.groups[1].id))
        assert(M.matches(s.groups[1], 'ARCHITECTURE'))
        assert(not M.matches(s.groups[1], '[%')) -- Literal, not Lua pattern search.
        for _, kind in ipairs({'bound', 'existing'}) do
            s = M.fixture(kind)
            assert(not M.canConfirm(s))
            local counts = {}
            for _, g in ipairs(s.groups) do
                local code = M.code(s, g)
                counts[code] = (counts[code] or 0) + 1
                if code ~= 'eligible' then assert(not M.toggle(s, g.id, true)) end
                if code == 'moderation' then assert(g.member == true) end
            end
            assert(counts.eligible == 372 and counts.member == 1)
            assert(counts.intent == 1 and counts.moderation == 1 and counts.uncertain == 1)
            for _, g in ipairs(s.groups) do
                if M.code(s, g) == 'eligible' then
                    M.toggle(s, g.id, true)
                    break
                end
            end
            assert(M.canConfirm(s) and M.choice(s) == 'groups')
            local selectedId = next(s.selected)
            assert(M.toggle(s, selectedId, false))
            assert(M.count(s) == 0 and not M.canConfirm(s) and M.choice(s) == 'none')
            assert(M.toggle(s, selectedId, true))
            assert(M.result(s, 'cancel') == nil)
            local oldCount = M.count(s)
            s.query = 'nothing matches'
            assert(M.count(s) == oldCount) -- Search must not deselect hidden rows.
            s.ready = false
            assert(not M.canConfirm(s)) -- Fail even after an earlier selection.
        end
        for _, kind in ipairs({'loading','stale','unavailable','contradictory'}) do
            s = M.fixture(kind)
            assert(not M.valid(s) and not M.canConfirm(s))
            for _, g in ipairs(s.groups) do assert(M.code(s,g) == 'unavailable') end
        end
        s = M.fixture('empty')
        assert(M.valid(s) and #s.groups == 0 and not M.canConfirm(s))
        s = M.fixture('bound')
        s.groups[1].block = 'unknown'
        assert(not M.valid(s))
        s = M.fixture('bound')
        s.groups[2].id = s.groups[1].id
        assert(not M.valid(s))
        s = M.fixture('bound')
        s.selected['unknown'] = true
        s.choice = 'none' -- Retired field cannot bypass unknown-ID validation.
        assert(not M.canConfirm(s))
        assert(M.copy.moderation:find('final moderator decision is unknown',1,true))
        assert(not M.copy.moderation:find('pending',1,true))
        """
    )
    source = (bundle / "Preview.lua").read_text(encoding="utf-8")
    for forbidden in ("LrHttp", "LrPasswords", "LrPrefs", "LrApplication", "setPropertyForPlugin"):
        assert forbidden not in source, forbidden
    info = (bundle / "Info.lua").read_text(encoding="utf-8")
    assert 'lrc15.selectionpreview"' in info
    assert "LrExportServiceProvider" not in info
    print(
        "PASS: selection boundaries, 376 groups, protected priority, "
        "fail-closed fixtures, cancel and isolation"
    )


if __name__ == "__main__":
    main()
