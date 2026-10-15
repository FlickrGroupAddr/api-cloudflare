"""Actual Lua 5.1 dual-list callbacks; mocked SDK, never native qualification."""

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
    def run_preview(self, scenario, kind="new", deferred=False):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.assertEqual(lua.lua_version, (5, 1))
        lua.globals().pluginPath = PLUGIN.as_posix()
        lua.globals().fixtureKind = kind
        lua.globals().deferred = deferred
        lua.globals().modelOverride = MODEL_OVERRIDE.replace("\\", "/")
        lua.execute("""
            _PLUGIN={path=pluginPath}
            local realDofile=dofile
            function dofile(path)
                local model=realDofile(modelOverride ~= "" and modelOverride or path)
                local original=model.fixture
                model.fixture=function(kind) activeFixture=original(kind); return activeFixture end
                return model
            end
            pending,callbacks={},{}
            function flush()
                local count=0
                while #pending>0 do
                    count=count+1; assert(count<10000,"observer loop")
                    table.remove(pending,1)()
                end
            end
            function propertyTable()
                local values,observers={},{}
                callbacks=observers
                local p
                p=setmetatable({}, {
                    __index=function(_,key)
                        if key=="addObserver" then
                            return function(_,name,callback) observers[name]=callback end
                        end
                        return values[key]
                    end,
                    __newindex=function(_,key,value)
                        local old=values[key]; values[key]=value
                        local callback=observers[key]
                        if old~=value and callback then
                            if deferred then
                                pending[#pending+1]=function() callback(p,key,value) end
                            else callback(p,key,value) end
                        end
                    end,
                })
                return p
            end
            local factory=setmetatable({}, {__index=function(_,kind)
                return function(_,args) args.kind=kind; return args end
            end})
            function collect(view,kind,values)
                values=values or {}
                if view.kind==kind then values[#values+1]=view end
                for _,child in ipairs(view) do collect(child,kind,values) end
                return values
            end
            function check(value,message) assert(value,message) end
            function find(items,id)
                for _,item in ipairs(items) do if item.value==id then return item end end
            end
            function move(p,key,id,button) p[key]={id}; button.action(); flush() end
            modalNumber=0; summaries={}
            local sdk={
                LrBinding={makePropertyTable=propertyTable},
                LrView={osFactory=function() return factory end,bind=function(key) return key end},
                LrFunctionContext={callWithContext=function(_,fn) return fn({}) end},
                LrPathUtils={child=function(a,b) return a.."/"..b end},
                LrTasks={startAsyncTask=function(fn) fn() end},
                LrDialogs={
                    message=function(title,text)
                        summaries[#summaries+1]={title=title,text=text} end,
                    presentModalDialog=function(options)
                        if options.title=="FGA Selection Preview — fixtures only" then
                            options.contents.bind_to_object.kind=fixtureKind; return "ok"
                        end
                        modalNumber=modalNumber+1
                        local p=options.contents.bind_to_object
                        local lists=collect(options.contents,"simple_list")
                        check(#lists==2,"two native lists")
                        check(lists[1].items=="availableItems" and lists[2].items=="selectedItems",
                            "available left; selected right")
                        check(not lists[1].allows_multiple_selection and
                            not lists[2].allows_multiple_selection,
                            "single-selection array contract")
                        check(options.otherVerb==nil,"no Apply search modal action")
                        check(#collect(options.contents,"checkbox")==0,"no checkbox hierarchy")
                        local edit=collect(options.contents,"edit_field")[1]
                        check(edit.immediate and type(edit.validate)=="function",
                            "per-edit validation")
                        local buttons=collect(options.contents,"push_button")
                        check(#buttons==2 and buttons[1].title=="Add →" and
                            buttons[2].title=="← Remove","center arrow actions")
                        flush()
                        return scenario(options,p,edit,buttons[1],buttons[2])
                    end,
                },
            }
            function import(name) return assert(sdk[name],"unexpected SDK import "..name) end
        """)
        lua.globals().scenario = lua.eval(scenario)
        lua.execute((PLUGIN / "Preview.lua").read_text(encoding="utf-8"))
        self.assertEqual(lua.globals().modalNumber, 1)
        return lua

    def test_live_query_and_exact_id_moves(self):
        for deferred in (False, True):
            lua = self.run_preview(
                """function(options,p,edit,add,remove)
                check(#p.availableItems==376 and #p.selectedItems==0,"initial population")
                local first=p.availableItems[1].value
                p.availableChoice={first}; flush()
                check(#p.selectedItems==0,"highlight does not move")
                add.action(); flush()
                check(#p.availableItems==375 and #p.selectedItems==1 and p.allowed,"Add moves")
                local id,other="fixture-0374@N00","fixture-0375@N00"
                edit.validate(edit,id)
                check(#p.availableItems==1 and p.availableItems[1].value==id,
                    "exact ID filters before focus loss")
                flush(); move(p,"availableChoice",id,add)
                edit.validate(edit,other); flush(); move(p,"availableChoice",other,add)
                edit.validate(edit,"literal .*[]%")
                check(#p.availableItems==0 and #p.selectedItems==3,"right unfiltered; literal left")
                move(p,"selectedChoice",id,remove)
                check(#p.selectedItems==2 and #p.availableItems==0,"Remove preserves query")
                edit.validate(edit,""); flush()
                check(#p.availableItems==374 and find(p.availableItems,id),
                    "clear restores available")
                check(not find(p.availableItems,other) and find(p.selectedItems,other),
                    "same-name IDs remain distinct")
                for _,row in ipairs(p.availableItems) do
                    check(row.title:sub(1,#row.value+2)=="["..row.value.."]","ID first")
                end
                return "ok"
            end""",
                deferred=deferred,
            )
            self.assertIn("2 group(s)", lua.globals().summaries[1].text)

    def test_limits_none_and_cancel(self):
        for deferred in (False, True):
            lua = self.run_preview(
                """function(options,p,edit,add,remove)
                local ids={}
                for i=1,61 do ids[i]=p.availableItems[i].value end
                for i=1,60 do move(p,"availableChoice",ids[i],add) end
                check(p.allowed and #p.selectedItems==60,"60 valid")
                edit.validate(edit,ids[61]); flush(); move(p,"availableChoice",ids[61],add)
                check(not p.allowed and #p.selectedItems==61,"61 disabled")
                move(p,"selectedChoice",ids[61],remove)
                check(p.allowed and #p.selectedItems==60,"back to60")
                p.choice="none"; flush()
                check(p.allowed and #p.selectedItems==0,"None clears all")
                p.choice="groups"; flush(); check(not p.allowed,"zero groups invalid")
                return "cancel"
            end""",
                deferred=deferred,
            )
            self.assertEqual(len(lua.globals().summaries), 0)

    def test_projection_guards_and_bound59(self):
        for kind in (
            "bound",
            "existing",
            "bound59",
            "loading",
            "empty",
            "stale",
            "unavailable",
            "contradictory",
        ):
            lua = self.run_preview(
                """function(options,p,edit,add,remove)
                for _,items in ipairs({p.availableItems,p.selectedItems}) do
                    for _,row in ipairs(items) do
                        for i=1,4 do check(row.value~=string.format("fixture-%04d@N00",i),
                            "protected rows excluded") end
                    end
                end
                if activeFixture.kind=="bound59" then
                    check(#p.selectedItems==59 and p.allowed,"59 preload")
                    move(p,"availableChoice",p.availableItems[1].value,add)
                    check(#p.selectedItems==60 and p.allowed,"bound60")
                    move(p,"availableChoice",p.availableItems[1].value,add)
                    check(#p.selectedItems==61 and not p.allowed,"bound61")
                elseif activeFixture.kind=="bound" or activeFixture.kind=="existing" then
                    check(#p.availableItems==372 and not p.allowed,"bound zero invalid")
                    move(p,"availableChoice",p.availableItems[1].value,add)
                    check(p.allowed,"bound one valid")
                    move(p,"selectedChoice",p.selectedItems[1].value,remove)
                    check(not p.allowed,"bound zero again")
                else check(#p.availableItems==0 and #p.selectedItems==0 and not p.allowed,
                    "empty or failed projection") end
                move(p,"availableChoice","fixture-0003@N00",add)
                check(not activeFixture.selected["fixture-0003@N00"],"forged protected ID refused")
                return "cancel"
            end""",
                kind=kind,
                deferred=True,
            )
            self.assertEqual(len(lua.globals().summaries), 0)

    def test_deferred_replays_stale_query_and_native_highlights(self):
        self.run_preview(
            """function(options,p,edit,add,remove)
            local first=p.availableItems[1].value
            local second=p.availableItems[2].value
            move(p,"availableChoice",first,add)
            p.availableChoice={second} -- simulate adjacent native highlight after items replacement
            flush(); check(#p.selectedItems==1,"native adjacent highlight never cascades")
            p.query="no-match"
            add.action(); flush()
            check(#p.selectedItems==1,"newest pending query blocks stale Add")
            edit.validate(edit,""); flush()
            p.availableChoice={first}; add.action(); flush()
            check(#p.selectedItems==1,"wrong-side stale ID rejected")
            p.availableChoice={second,first}; add.action(); flush()
            check(#p.selectedItems==1,"multi-value event rejected")
            p.availableChoice=second; add.action(); flush()
            check(#p.selectedItems==1,"scalar event rejected")
            p.choice="none"; flush()
            check(#p.selectedItems==0 and p.allowed,"None clears selected marks")
            move(p,"availableChoice",first,add)
            p.availableChoice={second}
            p.choice="none"
            add.action(); flush()
            check(p.choice=="none" and #p.selectedItems==0 and p.allowed,
                "pending None reconciles before Add and requires fresh highlight")
            callbacks.choice(p,"choice","groups"); flush()
            check(p.choice=="none" and p.allowed,"stale radio replay ignored")
            edit.validate(edit,"nothing"); edit.validate(edit,""); flush()
            check(#p.availableItems==376,"latest rapid query wins")
            return "cancel"
        end""",
            deferred=True,
        )


if __name__ == "__main__":
    unittest.main()
