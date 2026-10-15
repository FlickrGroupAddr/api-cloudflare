"""Independent multi-dialog adversarial review of the fixture selection UI.

This exercises actual Lua 5.1 observers and Preview.lua, not a native host.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

SOURCE_ROOT = Path(os.environ.get("FGA_SOURCE_ROOT", str(Path(__file__).resolve().parents[1])))
PLUGIN = SOURCE_ROOT / "clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin"
MODEL_OVERRIDE = os.environ.get("FGA_SELECTION_MODEL_OVERRIDE", "")


class SelectionPreviewAdversarialTests(unittest.TestCase):
    def run_preview(self, scenario, kind="new"):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(lua.lua_version, (5, 1))
        lua.globals().pluginPath = PLUGIN.as_posix()
        lua.globals().scenario = scenario
        lua.globals().fixtureKind = kind
        lua.globals().modelOverride = MODEL_OVERRIDE.replace("\\", "/")
        lua.execute("""
            _PLUGIN={path=pluginPath}
            local realDofile=dofile
            function dofile(path)
                local model=realDofile(modelOverride ~= "" and modelOverride or path)
                local original=model.fixture
                model.fixture=function(kind)
                    activeFixture=original(kind)
                    return activeFixture
                end
                return model
            end
            function propertyTable()
                local values, observers={}, {}
                return setmetatable({}, {
                    __index=function(_, key)
                        if key == "addObserver" then
                            return function(_, name, callback) observers[name]=callback end
                        end
                        return values[key]
                    end,
                    __newindex=function(_, key, value)
                        local previous=values[key]
                        values[key]=value
                        if previous ~= value and observers[key] then observers[key]() end
                    end,
                })
            end
            local factory=setmetatable({}, {__index=function(_, kind)
                return function(_, args) args.kind=kind; return args end
            end})
            function collect(view, kind, values)
                values=values or {}
                if view.kind == kind then values[#values+1]=view end
                for _, child in ipairs(view) do collect(child, kind, values) end
                return values
            end
            function check(value, message) assert(value, message) end
            function contains(text, part) return text:find(part, 1, true) ~= nil end
            local sdk={
                LrBinding={makePropertyTable=propertyTable},
                LrView={osFactory=function() return factory end, bind=function(key) return key end},
                LrFunctionContext={callWithContext=function(_, callback) return callback({}) end},
                LrPathUtils={child=function(parent, child) return parent .. "/" .. child end},
                LrTasks={startAsyncTask=function(callback) callback() end},
            }
            modalNumber=0
            summaries={}
            sdk.LrDialogs={
                message=function(title, text) summaries[#summaries+1]={title=title,text=text} end,
                presentModalDialog=function(options)
                    if options.title == "FGA Selection Preview — fixtures only" then
                        options.contents.bind_to_object.kind=fixtureKind
                        return "ok"
                    end
                    modalNumber=modalNumber+1
                    local p=options.contents.bind_to_object
                    local boxes=collect(options.contents,"checkbox")
                    check(#boxes <= 376,"bounded fixture row hierarchy")
                    return scenario(options,p,boxes,modalNumber)
                end,
            }
            function import(name) return assert(sdk[name],"unexpected SDK import " .. name) end
        """)
        lua.globals().scenario = lua.eval(scenario)
        lua.execute((PLUGIN / "Preview.lua").read_text(encoding="utf-8"))
        return lua

    def test_search_keeps_hidden_selection_and_exact_id_returns_single_row(self):
        lua = self.run_preview("""function(options,p,boxes,step)
            if step==1 then
                firstKey=boxes[1].value
                firstID=boxes[1].title:match("%[([^%]]+)%]")
                secondKey=boxes[2].value
                secondID=boxes[2].title:match("%[([^%]]+)%]")
                p[firstKey]=true
                p.query=secondID
                return "other"
            elseif step==2 then
                check(#boxes==1 and contains(boxes[1].title,secondID),"exact ID search")
                check(p[firstKey]==true and contains(p.summary,"1 selected"),
                    "hidden choice retained")
                p[boxes[1].value]=true
                check(p.allowed and contains(p.summary,"2 selected"),"two selected union")
                p.query=""
                return "other"
            end
            check(#boxes==376 and p[firstKey] and p[secondKey],"clear search restores checked rows")
            return "ok"
        end""")
        self.assertEqual(lua.globals().modalNumber, 3)
        self.assertIn("2 group(s)", lua.globals().summaries[1].text)

    def test_none_clears_hidden_marks_before_unpublished_confirmation(self):
        lua = self.run_preview("""function(options,p,boxes,step)
            if step==1 then
                hiddenKey=boxes[1].value
                p[hiddenKey]=true
                p.query=boxes[2].title:match("%[([^%]]+)%]")
                return "other"
            end
            check(#boxes==1 and p[hiddenKey],"selected row really hidden")
            p.choice="none"
            check(not p[hiddenKey] and p.allowed and contains(p.summary,"0 selected"),
                "none clears hidden")
            return "ok"
        end""")
        self.assertIn("Choice: none; 0 group(s)", lua.globals().summaries[1].text)

    def test_sixty_one_across_filtered_views_cannot_be_confirmed(self):
        lua = self.run_preview("""function(options,p,boxes,step)
            if step==1 then
                for index=1,60 do p[boxes[index].value]=true end
                check(p.allowed,"sixty valid")
                overflowKey=boxes[61].value
                p.query=boxes[61].title:match("%[([^%]]+)%]")
                return "other"
            elseif step==2 then
                check(#boxes==1,"filtered overflow target")
                p[overflowKey]=true
                check(not p.allowed and contains(p.summary,"61 selected"),
                    "61 invalid including hidden")
                p.query="literal unmatched .*[]%"
                return "other"
            elseif step==3 then
                check(#boxes==0 and not p.allowed,"no matches cannot hide invalid count")
                p.query=""
                return "other"
            end
            check(#boxes==376 and p[overflowKey],"overflow mark retained")
            p[overflowKey]=false
            check(p.allowed and contains(p.summary,"60 selected"),"return to60 valid")
            return "cancel"
        end""")
        self.assertEqual(lua.globals().modalNumber, 4)
        self.assertEqual(len(lua.globals().summaries), 0)

    def test_projection_becoming_unavailable_after_selection_disables_reopened_view(self):
        lua = self.run_preview(
            """function(options,p,boxes,step)
            if step==1 then
                p[boxes[1].value]=true
                check(p.allowed,"initial complete view confirmable")
                activeFixture.ready=false
                return "other"
            end
            check(#boxes==0 and not p.allowed,"failure discards selectable projection")
            return "ok" -- Host/action spoofing still cannot produce a result.
        end""",
            "bound",
        )
        self.assertEqual(lua.globals().modalNumber, 2)
        self.assertEqual(len(lua.globals().summaries), 0)

    def test_protected_member_row_keeps_full_protection_and_has_no_checkbox(self):
        lua = self.run_preview(
            """function(options,p,boxes)
            local all=collect(options.contents,"static_text")
            local protection,later,unknown=false,false,false
            for _, item in ipairs(all) do
                local title=item.title
                if type(title)=="string" then
                    protection=protection or contains(title,"will not submit this exact pair again")
                    later=later or contains(title,"Membership was later observed")
                    unknown=unknown or contains(title,"final moderator decision is unknown")
                end
            end
            check(protection and later and unknown,"both block and later membership remain visible")
            for _, box in ipairs(boxes) do
                for index=1,4 do
                    check(not contains(box.title,string.format("fixture-%04d@N00",index)),
                        "no unsafe checkbox")
                end
            end
            check(not p.allowed,"bound zero disabled")
            p[boxes[1].value]=true
            check(p.allowed,"one bound addition valid")
            p[boxes[1].value]=false
            check(not p.allowed,"bound zero disabled again")
            return "cancel"
        end""",
            "bound",
        )
        self.assertEqual(len(lua.globals().summaries), 0)

    def test_literal_search_special_characters_and_confirmation_cancellation(self):
        for query in (".*", "%", "[", "(", "nothing-matches"):
            with self.subTest(query=query):
                scenario = """function(options,p,boxes,step)
                    if step==1 then p.query=QUERY; return "other" end
                    check(#boxes==0,"search treats Lua pattern characters literally")
                    return "cancel"
                end""".replace("QUERY", repr(query))
                lua = self.run_preview(scenario)
                self.assertEqual(len(lua.globals().summaries), 0)

    def test_duplicate_names_remain_distinct_by_id_and_long_label_fixture_is_present(self):
        lua = self.run_preview("""function(options,p,boxes,step)
            if step==1 then
                local duplicates={}
                local longFound=false
                for _,box in ipairs(boxes) do
                    if contains(box.title,"Shared coastal photographers") then
                        duplicates[#duplicates+1]=box
                    end
                    longFound=longFound or #box.title>170
                end
                check(#duplicates==2,"duplicate-looking group names need distinct fixture IDs")
                check(longFound,"long label must exist for host clipping acceptance")
                p[duplicates[1].value]=true
                p[duplicates[2].value]=true
                duplicateID=duplicates[1].title:match("%[([^%]]+)%]")
                p.query=duplicateID
                return "other"
            end
            check(#boxes==1 and contains(boxes[1].title,duplicateID),"ID disambiguates same names")
            check(contains(p.summary,"2 selected") and p.allowed,
                "distinct same-name choices retained")
            return "cancel"
        end""")
        self.assertEqual(len(lua.globals().summaries), 0)


if __name__ == "__main__":
    unittest.main()
