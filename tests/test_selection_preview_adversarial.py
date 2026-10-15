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
            function checkActionTitle(p)
                local n=#p.selectedItems
                local expected
                if activeFixture.bound then
                    expected=n==1 and "Queue for 1 group" or "Queue for "..n.." groups"
                elseif n==0 then expected="Save for publish: no groups"
                else expected=n==1 and "Save for publish: 1 group"
                    or "Save for publish: "..n.." groups" end
                check(p.actionTitle==expected,"truthful action title and pluralization")
                check(not p.actionTitle:find("-",1,true),"action count never negative")
            end
            function find(items,id)
                for _,item in ipairs(items) do if item.value==id then return item end end
            end
            function move(p,key,id,button)
                p[key]={id}; button.action(); flush(); checkActionTitle(p)
            end
            modalNumber=0; summaries={}
            local sdk={
                LrBinding={makePropertyTable=propertyTable},
                LrView={share=function(key) return {shared=key} end,
                    osFactory=function() return factory end,bind=function(key) return key end},
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
                        check(options.actionBinding.title.bind_to_object==p,
                            "action title bound to live dialog properties")
                        check(options.actionBinding.title.key=="actionTitle","action title key")
                        check(options.actionBinding.enabled.bind_to_object==p and
                            options.actionBinding.enabled.key=="allowed","enabled guard retained")
                        check(options.actionVerb==p.actionTitle,"truthful initial title fallback")
                        local lists=collect(options.contents,"simple_list")
                        check(#lists==2,"two native lists")
                        check(lists[1].items=="availableItems" and lists[2].items=="selectedItems",
                            "available left; selected right")
                        check(not lists[1].allows_multiple_selection and
                            not lists[2].allows_multiple_selection,
                            "single-selection array contract")
                        check(options.otherVerb==nil,"no Apply search modal action")
                        check(#collect(options.contents,"checkbox")==0,"no checkbox hierarchy")
                        check(#collect(options.contents,"radio_button")==0,
                            "selected list owns choice")
                        check(callbacks.choice==nil,"no mutable choice observer")
                        local edit=collect(options.contents,"edit_field")[1]
                        check(edit.immediate and type(edit.validate)=="function",
                            "per-edit validation")
                        local buttons=collect(options.contents,"push_button")
                        check(#buttons==3,"Clear and two center arrow actions")
                        local byTitle={}
                        for _,button in ipairs(buttons) do byTitle[button.title]=button end
                        check(byTitle["Add →"] and byTitle["← Remove"] and byTitle["Clear filter"],
                            "explicit actions identified by title")
                        flush()
                        checkActionTitle(p)
                        return scenario(options,p,edit,byTitle["Add →"],byTitle["← Remove"],
                            byTitle["Clear filter"])
                    end,
                },
            }
            function import(name) return assert(sdk[name],"unexpected SDK import "..name) end
        """)
        lua.globals().scenario = lua.eval(scenario)
        lua.execute((PLUGIN / "Preview.lua").read_text(encoding="utf-8"))
        self.assertEqual(lua.globals().modalNumber, 1)
        return lua

    def test_concise_context_and_readonly_safety(self):
        for kind in ("new", "bound", "existing", "stale", "contradictory"):
            self.run_preview(
                """function(options,p,edit,add,remove)
                local texts=collect(options.contents,"static_text")
                local photo,album,notice=false,false,false
                local protected,later,identity,unavailable=false,false,false,false
                for _,item in ipairs(texts) do
                    local title=item.title
                    if type(title)=="string" then
                        photo=photo or title=="Photo: "..activeFixture.photo
                        album=album or title=="FGA Album: "..activeFixture.album
                        notice=notice or title=="Preview only — nothing is saved or submitted."
                        protected=protected or
                            title:find("will not submit this exact pair again",1,true)~=nil
                        later=later or title:find("Membership was later observed",1,true)~=nil
                        identity=identity or title:find("fixture-0003@N00",1,true)~=nil
                        unavailable=unavailable or title:lower():find("unavailable",1,true)~=nil
                        check(not title:find("Scope:",1,true),"internal scope absent")
                        check(not title:find("Refresh:",1,true),"debug refresh instruction absent")
                        check(not title:find("Complete writable groups, fresh membership",1,true),
                            "internal freshness header absent")
                    end
                end
                check(photo and album and notice,"clear photo/Album and fixture boundary")
                check(add.width==remove.width and add.width==90,"equal button widths")
                local lists=collect(options.contents,"simple_list")
                local outer
                for _,row in ipairs(collect(options.contents,"row")) do
                    if row[1]==lists[1] and row[3]==lists[2] then outer=row end
                end
                check(outer and #outer==3,"one shared list-only row")
                check(outer[2].width==90 and outer[2].height==220,"fixed center list region")
                local centered=outer[2][1]
                check(centered[1]==add and centered[2]==remove and
                    centered.place_vertical==0.5,"move buttons centered within list region")
                local panels=collect(options.contents,"scrolled_view")
                if activeFixture.kind=="new" then
                    check(#panels==0,"unpublished has no empty membership panel")
                    check(#p.availableItems==376 and p.allowed,"unpublished functionality retained")
                else
                    check(#panels==1 and panels[1].height==125,"bound read-only panel retained")
                    if activeFixture.kind=="bound" or activeFixture.kind=="existing" then
                        check(protected and later and identity,"protection and ID retained")
                    else
                        check(unavailable and not p.allowed,"unavailable and fail-closed")
                    end
                end
                return "cancel"
            end""",
                kind=kind,
                deferred=True,
            )

    def test_expandable_layout_and_full_highlight_identity(self):
        for deferred in (False, True):
            self.run_preview(
                """function(options,p,edit,add,remove)
                local lists=collect(options.contents,"simple_list")
                check(options.resizable and options.contents.fill_horizontal==1,
                    "dialog and contents accept horizontal growth")
                for _,list in ipairs(lists) do
                    check(list.width==nil and list.fill_horizontal==0.5,
                        "equal expandable native list minima without fixed width")
                    check(list.tooltip=="highlightDetail","whole-list highlight tooltip")
                end
                check(edit.width==nil and edit.width_in_chars==24 and edit.fill_horizontal==1,
                    "search follows expandable left header")
                local outer,index
                for i,row in ipairs(options.contents) do
                    if row[1]==lists[1] and row[3]==lists[2] then outer=row; index=i end
                end
                check(outer and outer.fill_horizontal==1 and outer.width==nil,"row fills dialog")
                local header,footer=options.contents[index-1],options.contents[index+1]
                for _,row in ipairs({header,footer}) do
                    check(row.kind=="row" and row.fill_horizontal==1 and row.spacing==outer.spacing,
                        "metadata rows follow same horizontal layout")
                    check(row[2].width==90,"matching center gap")
                    for _,side in ipairs({row[1],row[3]}) do
                        check(side.fill_horizontal==0.5 and side.width==nil,"equal growing sides")
                        check(side[1].width==450 and side[1].height==0,"native list minimum spacer")
                    end
                end
                check(header[1][3][1]==edit and header[1][3][2].title=="Clear filter",
                    "query and clear share left header")
                check(header[1][2].title=="searchHeading" and
                    header[1][2].font=="<system/bold>","bold heading owns FILTERED cue")
                check(header[1][4].title=="filterStatus" and
                    header[1][4].tooltip=="searchSummary","count above left list")
                check(header[3][2].title=="Selected additions" and
                    header[3][2].alignment=="center","selected heading centered")
                check(footer[3][2].title=="summary","selected count directly below right")
                check(header[3].place_vertical==1,"selected heading rests above right list")
                check(outer[2].width==90 and outer[2].height==lists[1].height and
                    outer[2][1].place_vertical==0.5,"compact centered button column")
                edit.validate(edit,"Landscape"); flush()
                check(p.filterStatus=="FILTERED: 62 matches / 376 total",
                    "exact requested count format")
                check(p.searchHeading:find("FILTERED",1,true),"heading shows active filter")
                edit.validate(edit,""); flush()
                check(not p.searchHeading:find("FILTERED",1,true),"clear removes heading cue")
                local detail
                for _,view in ipairs(collect(options.contents,"static_text")) do
                    if view.title=="highlightDetail" then detail=view end
                end
                check(detail and detail.height_in_lines==-1 and detail.fill_horizontal==1
                    and detail.tooltip=="highlightDetail","wrapped full identity detail")
                for _,group in ipairs(activeFixture.groups) do
                    local row=find(p.availableItems,group.id)
                    check(row.title==group.name.." ["..group.id.."]","name then exact NSID")
                end
                local id,other="fixture-0374@N00","fixture-0375@N00"
                p.availableChoice={id}; flush()
                check(p.highlightDetail=="Highlighted group: "..find(p.availableItems,id).title,
                    "highlight exposes exact duplicate identity")
                check(#p.selectedItems==0,"detail observer never moves rows")
                p.availableChoice={other}; flush()
                check(p.highlightDetail:find(other,1,true) and
                    not p.highlightDetail:find(id,1,true),"duplicate labels distinguish exact IDs")
                local long="fixture-0376@N00"
                p.availableChoice={long}; flush()
                local expected="Highlighted group: "..find(p.availableItems,long).title
                check(#expected>180 and p.highlightDetail==expected,
                    "full long name and trailing NSID")
                move(p,"availableChoice",long,add)
                p.selectedChoice={long}; flush()
                check(p.highlightDetail==expected,"right list exposes full exact identity")
                edit.validate(edit,"no matches"); flush()
                check(not p.highlightDetail:find(long,1,true),"list refresh clears stale detail")
                p.availableChoice={long}; flush()
                check(not p.highlightDetail:find(long,1,true),"wrong-side stale highlight ignored")
                check(#p.selectedItems==1,"search and details preserve additions")
                return "cancel"
            end""",
                deferred=deferred,
            )

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
                    check(row.title:sub(-(#row.value+2))=="["..row.value.."]","NSID at end")
                end
                return "ok"
            end""",
                deferred=deferred,
            )
            self.assertIn("2 group(s)", lua.globals().summaries[1].text)

    def test_limits_remove_last_and_explicit_none(self):
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
                for i=60,1,-1 do move(p,"selectedChoice",ids[i],remove) end
                check(p.allowed and #p.selectedItems==0,"removing last enables unpublished zero")
                check(activeFixture.selected[ids[1]]==false,"removed ID cleared")
                return "ok"
            end""",
                deferred=deferred,
            )
            self.assertEqual(len(lua.globals().summaries), 1)
            self.assertIn("Choice: none; 0 group(s)", lua.globals().summaries[1].text)

    def test_initial_none_add_groups_and_cancel(self):
        for deferred in (False, True):
            for action in ("none", "groups", "cancel"):
                lua = self.run_preview(
                    """function(options,p,edit,add,remove)
                    check(p.allowed and #p.selectedItems==0,"initial none is saveable")
                    check(options.actionVerb=="Save for publish: no groups","unpublished action")
                    if requestedAction~="none" then
                        move(p,"availableChoice",p.availableItems[1].value,add)
                        check(p.allowed and #p.selectedItems==1,"Add one enables groups")
                    end
                    return requestedAction=="cancel" and "cancel" or "ok"
                end""".replace("requestedAction", '"' + action + '"'),
                    deferred=deferred,
                )
                if action == "cancel":
                    self.assertEqual(len(lua.globals().summaries), 0)
                else:
                    expected = "none; 0" if action == "none" else "groups; 1"
                    self.assertIn("Choice: " + expected, lua.globals().summaries[1].text)

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

    def test_action_title_tracks_only_selected_additions(self):
        for kind in ("new", "bound", "existing"):
            for deferred in (False, True):
                self.run_preview(
                    """function(options,p,edit,add,remove)
                    local before=p.actionTitle
                    local first,second=p.availableItems[1].value,p.availableItems[2].value
                    p.availableChoice={first}; flush()
                    check(p.actionTitle==before,"highlight leaves action title unchanged")
                    edit.validate(edit,"nothing matches"); flush()
                    check(p.actionTitle==before,"query leaves action title unchanged")
                    edit.validate(edit,""); flush()
                    move(p,"availableChoice",first,add)
                    local singular=p.actionTitle
                    p.selectedChoice={first}; flush()
                    edit.validate(edit,"nothing matches"); flush()
                    check(p.actionTitle==singular,"selected highlight and query preserve count")
                    edit.validate(edit,""); flush()
                    move(p,"availableChoice",second,add)
                    move(p,"selectedChoice",first,remove)
                    check(p.actionTitle==singular,"removing one restores singular")
                    move(p,"selectedChoice",second,remove)
                    check(p.actionTitle==before,"removing last restores truthful zero")
                    check(p.allowed==(not activeFixture.bound),"zero enabled guard retained")
                    move(p,"selectedChoice",second,remove)
                    check(p.actionTitle==before,"stale Remove cannot create negative count")
                    return "cancel"
                end""",
                    kind=kind,
                    deferred=deferred,
                )

    def test_filter_status_clear_and_deferred_highlights(self):
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
                self.run_preview(
                    """function(options,p,edit,add,remove,clear)
                    local total=#p.availableItems+#p.selectedItems
                    local available=#p.availableItems
                    local selected=#p.selectedItems
                    local title=p.actionTitle
                    check(clear.enabled=="filterActive","Clear enabled follows filter state")
                    local unknown=activeFixture.kind=="loading" or activeFixture.kind=="stale" or
                        activeFixture.kind=="unavailable" or activeFixture.kind=="contradictory"
                    local state=activeFixture.kind=="loading" and "Loading group data"
                        or "Group data unavailable"
                    check(not p.filterActive and p.filterStatus==(unknown and state or
                        string.format("%d matches / %d total",available,total)),
                        "empty filter truthful even with selected or unavailable groups")
                    for _,query in ipairs({" ","  ","[%.*","no possible match"}) do
                        edit.validate(edit,query)
                        local expected=0
                        for _,group in ipairs(activeFixture.groups) do
                            local protected=activeFixture.bound and
                                (group.member or group.state or group.block)
                            if not unknown and not protected
                                and not activeFixture.selected[group.id]
                                and string.find(string.lower(group.name.." "..group.id),
                                    string.lower(query),1,true) then expected=expected+1 end
                        end
                        check(p.filterActive and p.filterStatus==(unknown and state
                            or string.format(
                            "FILTERED: %d matches / %d total",expected,total)),
                            "any characters activate a literal filter with truthful counts")
                        check(p.searchSummary:find(query,1,true),"tooltip retains literal query")
                        if unknown then
                            check(p.searchSummary:find("counts are unknown",1,true)
                                and not p.allowed,"unknown counts; confirmation disabled")
                        end
                        check(#p.selectedItems==selected and p.actionTitle==title,
                            "filter preserves selected set and confirmation title")
                        clear.action()
                        check(p.query=="" and not p.filterActive and #p.availableItems==available,
                            "Clear restores available rows synchronously in place")
                        check(#p.selectedItems==selected and p.actionTitle==title,
                            "Clear preserves selections and title")
                        flush()
                    end
                    if available>0 then
                        local id=p.availableItems[1].value
                        p.availableChoice={id}
                        p.query="no-match" -- a property event may still be pending
                        clear.action()
                        add.action(); flush()
                        check(#p.selectedItems==selected and not activeFixture.selected[id],
                            "Clear invalidates stale highlights before Add with deferred observers")
                        move(p,"availableChoice",id,add)
                        local after=p.actionTitle
                        edit.validate(edit,"no possible match")
                        check(#p.selectedItems==selected+1 and p.actionTitle==after,
                            "selected right stays visible through filtering")
                        clear.action(); flush()
                        check(#p.availableItems==available-1 and p.actionTitle==after,
                            "Clear excludes selected rows and retains action title")
                    end
                    return "cancel"
                end""",
                    kind=kind,
                    deferred=deferred,
                )

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
            move(p,"selectedChoice",first,remove)
            check(#p.selectedItems==0 and p.allowed,"remove last restores explicit none")
            p.selectedChoice={first}; remove.action(); flush()
            check(#p.selectedItems==0 and p.allowed,"stale repeated Remove is inert")
            p.choice="groups"; flush()
            check(#p.selectedItems==0 and p.allowed,"retired choice field cannot block zero save")
            move(p,"availableChoice",first,add)
            p.choice="none"; flush()
            check(#p.selectedItems==1 and p.allowed,"retired choice field cannot clear selections")
            move(p,"selectedChoice",first,remove)
            edit.validate(edit,"nothing"); edit.validate(edit,""); flush()
            check(#p.availableItems==376,"latest rapid query wins")
            return "cancel"
        end""",
            deferred=True,
        )


if __name__ == "__main__":
    unittest.main()
