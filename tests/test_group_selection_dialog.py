"""Native-view adapter event tests; no native-host qualification claim."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

BUNDLE = Path(__file__).resolve().parents[1] / "clients/lightroom/FGA-LrC15.lrplugin"


class DialogTests(unittest.TestCase):
    def test_protection_membership_times_and_local_stale_choice_action(self):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        lua.globals().C = lua.execute(
            (BUNDLE / "GroupSelectionController.lua").read_text(encoding="utf-8")
        )
        lua.execute("""
            local factory=setmetatable({}, {__index=function(_,kind)
                return function(_,p) p.kind=kind; return p end end})
            local sdk={LrBinding={makePropertyTable=function()
                return {addObserver=function() end} end},
                LrView={bind=function(k) return k end,osFactory=function() return factory end},
                LrFunctionContext={callWithContext=function(_,fn) return fn({}) end}}
            sdk.LrDialogs={presentModalDialog=function(options)
                local titles,clear={},nil
                local function scan(v)
                    if type(v.title)=='string' then titles[#titles+1]=v.title end
                    if v.title=='Clear unavailable saved choices' then clear=v end
                    for _,child in ipairs(v) do scan(child) end
                end
                scan(options.contents)
                local all=table.concat(titles,'|')
                assert(all:find('moderator decision is unknown',1,true))
                local positive='Also currently in this Flickr group as observed at member-time'
                assert(all:find(positive,1,true))
                assert(all:find('refreshed at group-time',1,true))
                assert(all:find('submission status observed at status-time',1,true))
                local p=options.contents.bind_to_object
                assert(not p.allowed and p.hasUnavailableChoices and clear)
                assert(p.unavailableChoiceNotice:find('protected',1,true))
                clear.action()
                assert(p.allowed and not p.hasUnavailableChoices)
                assert(p.actionTitle=='Queue for 1 group')
                assert(controller.model.selected.g1 and not controller.model.selected.protected)
                return 'cancel'
            end}
            import=function(name) return assert(sdk[name]) end
            controller=setmetatable({model={ready=true,bound=true,groups={{id='g1',name='Alpha'}},
                selected={g1=true,protected=true},query='',refreshedAt='group-time',
                membershipObservedAt='member-time',statusObservedAt='status-time',rows={
                    {readOnly=true,flickrGroupId='protected',displayName='Protected',
                    code='moderation_submission_protected',currentMembershipObserved=true,
                    copy='The final moderator decision is unknown.'}}},
                commit=function() error('Cancel wrote state') end},C)
        """)
        dialog = lua.execute((BUNDLE / "GroupSelectionDialog.lua").read_text(encoding="utf-8"))
        result = dialog.show(
            lua.globals().controller,
            lua.table_from({"photoName": "Synthetic photo", "albumName": "Synthetic album"}),
        )
        self.assertEqual(result["state"], "cancelled")

    def test_live_filter_multiselect_clear_and_context_labels(self):
        for deferred in (False, True):
            with self.subTest(deferred=deferred):
                lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
                lua.globals().deferred = deferred
                lua.globals().C = lua.execute(
                    (BUNDLE / "GroupSelectionController.lua").read_text(encoding="utf-8")
                )
                lua.execute("""
                    local pending={}
                    local function properties()
                        local values,observers={},{}
                        return setmetatable({}, {
                            __index=function(_,k)
                                if k=='addObserver' then
                                    return function(_,key,fn) observers[key]=fn end
                                end
                                return values[k]
                            end,
                            __newindex=function(t,k,v)
                                local old=values[k]; values[k]=v
                                if old~=v and observers[k] then
                                    local cb=function() observers[k](t,k,v) end
                                    if deferred then pending[#pending+1]=cb else cb() end
                                end
                            end})
                    end
                    local function flush() while #pending>0 do table.remove(pending,1)() end end
                    local factory=setmetatable({}, {__index=function(_,kind)
                        return function(_,p) p.kind=kind; return p end end})
                    local function find(view,kind,items)
                        items=items or {}; if view.kind==kind then items[#items+1]=view end
                        for _,v in ipairs(view) do find(v,kind,items) end; return items
                    end
                    local sdk={LrBinding={makePropertyTable=properties},
                        LrView={bind=function(k) return k end,
                            osFactory=function() return factory end},
                        LrFunctionContext={callWithContext=function(_,fn) return fn({}) end}}
                    sdk.LrDialogs={presentModalDialog=function(options)
                        local p=options.contents.bind_to_object
                        local lists=find(options.contents,'simple_list')
                        assert(#lists==2 and lists[1].allows_multiple_selection
                            and lists[2].allows_multiple_selection)
                        assert(lists[1].height==lists[2].height and lists[1].width==nil)
                        assert(#find(options.contents,'radio_button')==0)
                        assert(options.actionBinding.title.key=='actionTitle' and options.resizable)
                        local buttons=find(options.contents,'push_button')
                        local clear,add,remove=buttons[1],buttons[2],buttons[3]
                        assert(add.width==remove.width and clear.title=='Clear filter')
                        assert(p.actionTitle=='Save for publish: no groups' and p.allowed)
                        p.availableChoice={'g1','g2'}; add.action(); flush()
                        assert(p.actionTitle=='Save for publish: 2 groups' and #p.selectedItems==2)
                        p.query='nothing'; flush()
                        assert(p.filterActive and p.filterStatus:find('FILTERED',1,true))
                        assert(#p.availableItems==0 and #p.selectedItems==2)
                        assert(p.actionTitle=='Save for publish: 2 groups')
                        clear.action(); flush(); assert(p.query=='' and not p.filterActive)
                        p.selectedChoice={'g1','g2'}; remove.action(); flush()
                        assert(p.allowed and p.actionTitle=='Save for publish: no groups')
                        p.availableChoice={'g1','g1'}; add.action(); assert(#p.selectedItems==0)
                        p.availableChoice={'g1'}
                        p.query='changed before observer'
                        add.action()
                        flush()
                        assert(#p.selectedItems==0)
                        return 'cancel'
                    end}
                    import=function(name) assert(sdk[name],name); return sdk[name] end
                    controller=setmetatable({model={ready=true,bound=false,groups={
                        {id='g1',name='Alpha'},{id='g2',name='Beta'}},selected={},query='',rows={}},
                        commit=function() error('cancel committed') end},C)
                """)
                dialog = lua.execute(
                    (BUNDLE / "GroupSelectionDialog.lua").read_text(encoding="utf-8")
                )
                result = dialog.show(
                    lua.globals().controller,
                    lua.table_from(
                        {"photoName": "Synthetic photo", "albumName": "Synthetic album"}
                    ),
                )
                self.assertEqual(result["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
