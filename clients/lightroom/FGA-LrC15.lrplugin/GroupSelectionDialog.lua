-- Copyright 2026 Terry Ott. MIT License.
-- Disabled native candidate: no registration, task launch, catalog or HTTP adapter.
local LrBinding = import "LrBinding"
local LrDialogs = import "LrDialogs"
local LrFunctionContext = import "LrFunctionContext"
local LrView = import "LrView"
local bind, f = LrView.bind, LrView.osFactory()
local Dialog = { PRODUCTION_QUALIFIED = false }
local function text(value, lines)
    return f:static_text { title=value, width_in_chars=96,
        height_in_lines=lines and -1 or 1, fill_horizontal=1 }
end
function Dialog.show(controller, identity)
    local s, M = controller.model, controller
    return LrFunctionContext.callWithContext("fixture group selection", function(context)
        local p = LrBinding.makePropertyTable(context)
        p.query = s.query
        local function highlightedGroup(key, itemsKey)
            local values = p[key]
            if type(values) ~= "table" or #values == 0 then return end
            if #values > 1 then
                p.highlightDetail = string.format("%d highlighted groups — use Add or Remove to move them together.", #values)
                return
            end
            for _, row in ipairs(p[itemsKey] or {}) do
                if row.value == values[1] then
                    p.highlightDetail = "Highlighted group: " .. row.title
                    return
                end
            end
        end
        local function refreshLists()
            local available, selected = {}, {}
            local total = 0
            s.query = p.query or ""
            for _, group in ipairs(s.groups) do
                if M.code(s, group) == "eligible" then
                    total = total + 1
                    local row = { title = group.name .. " [" .. group.id .. "]", value = group.id }
                    if s.selected[group.id] then
                        selected[#selected + 1] = row
                    elseif M.matches(group, s.query) then
                        available[#available + 1] = row
                    end
                end
            end
            -- Native list controls may highlight an adjacent row when their
            -- items change. Highlights never move rows; only explicit buttons do.
            p.availableChoice, p.selectedChoice = {}, {}
            p.availableItems, p.selectedItems = available, selected
            p.highlightDetail = "Ctrl-click for separate groups; Shift-click for a range. Use Add or Remove to move highlighted groups."
            p.filterActive = s.query ~= ""
            p.searchHeading = p.filterActive
                and "Available groups — FILTERED — filter name or ID:"
                or "Available groups — filter name or ID:"
            p.filterStatus = (p.filterActive and "FILTERED: " or "")
                .. string.format("%d matches / %d total", #available, total)
            p.searchSummary = p.filterActive
                and string.format('FILTERED: query "%s"; %d available matches / %d eligible groups. Clear filter to see all available groups.',
                    s.query, #available, total)
                or string.format("All available: %d / %d eligible groups; no filter.", #available, total)
            if not M.valid(s) then
                local state = s.kind == "loading" and "Loading group data" or "Group data unavailable"
                p.filterStatus = state
                p.searchSummary = p.filterActive
                    and string.format('FILTERED: query "%s"; %s. Available and eligible counts are unknown.', s.query, state)
                    or state .. ". Available and eligible counts are unknown; no filter."
            end
        end
        local function sync()
            local n = M.count(s)
            local unavailable = M.unavailableChoices(s)
            p.hasUnavailableChoices = #unavailable > 0
            p.unavailableChoiceNotice = p.hasUnavailableChoices
                and ("Saved choices are no longer eligible: " .. table.concat(unavailable, ", ")
                    .. ". Clear these local choices before saving a replacement. Existing memberships and records stay read-only.")
                or "All local choices are eligible."
            local groups = n == 1 and "1 group" or string.format("%d groups", n)
            p.allowed = M.canConfirm(s)
            p.summary = string.format("%d selected / 60 maximum", n)
            if s.bound then
                p.actionTitle = "Queue for " .. groups
            else
                p.actionTitle = n == 0 and "Save for publish: no groups"
                    or "Save for publish: " .. groups
            end
        end
        local function move(key, selecting)
            if s.query ~= (p.query or "") then refreshLists(); return end
            local values = p[key]
            if type(values) ~= "table" or #values == 0 or not M.valid(s) then return end
            local items = selecting and p.availableItems or p.selectedItems
            local present, seen, ids = {}, {}, {}
            for _, row in ipairs(items) do present[row.value] = true end
            -- Validate the whole highlighted set before changing any choice.
            -- Stale/wrong-side IDs reject the batch rather than moving a subset.
            for index, id in pairs(values) do
                if type(index) ~= "number" or index % 1 ~= 0
                    or index < 1 or index > #values or type(id) ~= "string"
                    or seen[id] or not present[id]
                    or (s.selected[id] == true) == selecting then return end
                seen[id] = true
                ids[#ids + 1] = id
            end
            if #ids ~= #values then return end
            for _, id in ipairs(ids) do M.toggle(s, id, selecting) end
            refreshLists()
            sync()
        end
        p.availableChoice, p.selectedChoice = {}, {}
        local function queryChanged()
            if s.query ~= (p.query or "") then refreshLists() end
        end
        p:addObserver("query", queryChanged)
        p:addObserver("availableChoice", function() highlightedGroup("availableChoice", "availableItems") end)
        p:addObserver("selectedChoice", function() highlightedGroup("selectedChoice", "selectedItems") end)
        local readonly = { spacing = 8 }
        for _, row in ipairs(s.rows) do
            if row.readOnly then
                readonly[#readonly + 1] = text((row.displayName or "Group") .. " [" .. row.flickrGroupId .. "]")
                readonly[#readonly + 1] = text(row.copy or "Retained group record (read-only).", 3)
                if row.currentMembershipObserved and row.code ~= "current_membership_observed" then
                    readonly[#readonly + 1] = text("Also currently in this Flickr group as observed at "
                        .. (s.membershipObservedAt or "unavailable") .. ". Membership is read-only.", 2)
                end
            end
        end
        if #readonly == 0 then readonly[1] = text("No current memberships or retained intents in this complete observation.") end
        local status = not s.ready and "Group data unavailable. Refresh before selecting groups."
            or not s.bound and "Not yet published by this FGA collection. Groups are optional."
        refreshLists()
        sync()
        local contents = { bind_to_object = p, spacing = 8, fill_horizontal = 1,
            text("Choose optional group additions."),
            text("Photo: " .. identity.photoName), text("FGA Album: " .. identity.albumName),
        }
        if status then contents[#contents + 1] = text(status, 3) end
        contents[#contents + 1] = text(s.ready
            and ("Writable-group snapshot: complete; refreshed at " .. (s.refreshedAt or "unavailable") .. ".")
            or "Writable-group snapshot: unavailable.")
        if s.bound then
            contents[#contents + 1] = text("Membership observed at " .. (s.membershipObservedAt or "unavailable")
                .. "; submission status observed at " .. (s.statusObservedAt or "unavailable") .. ".", 2)
            contents[#contents + 1] = text("Current memberships and submission records (read-only)")
            contents[#contents + 1] = f:scrolled_view { height = 125, width = 740, f:column(readonly) }
        end
        contents[#contents + 1] = text("Changing selections never removes membership, cancels an intent, or clears protection.", 2)
        if #M.unavailableChoices(s) > 0 then
            contents[#contents + 1] = f:static_text { title = bind "unavailableChoiceNotice",
                width_in_chars = 96, height_in_lines = -1, fill_horizontal = 1 }
            contents[#contents + 1] = f:push_button { title = "Clear unavailable saved choices",
                enabled = bind "hasUnavailableChoices", action = function()
                    M.clearUnavailableChoices(s)
                    refreshLists()
                    sync()
                end }
        end
        -- Separate shared rows make list geometry independent of header height.
        -- Matching native 450px minima keep all three rows' edges aligned, while
        -- leaving the growing side containers and lists free of numeric widths.
        local function sideMinimum() return f:spacer { width = 450, height = 0 } end
        contents[#contents + 1] = f:row { spacing = 12, fill_horizontal = 1,
            f:column { spacing = 4, fill_horizontal = 0.5,
                sideMinimum(),
                f:static_text { title = bind "searchHeading", font = "<system/bold>",
                    width_in_chars = 32, fill_horizontal = 1 },
                f:row { spacing = 8, fill_horizontal = 1,
                    f:edit_field { value = bind "query", immediate = true,
                        width_in_chars = 24, fill_horizontal = 1,
                        validate = function(_, value)
                            p.query = value or ""
                            queryChanged()
                            return true, value
                        end,
                    },
                    f:push_button { title = "Clear filter", width = 90,
                        enabled = bind "filterActive",
                        action = function()
                            p.query = ""
                            -- Invalidate highlights even with deferred observers.
                            refreshLists()
                        end },
                },
                f:static_text { title = bind "filterStatus", font = "<system/bold>",
                    width_in_chars = 32, fill_horizontal = 1,
                    tooltip = bind "searchSummary" },
            },
            f:spacer { width = 90 },
            f:column { fill_horizontal = 0.5, place_vertical = 1,
                sideMinimum(),
                f:static_text { title = "Selected additions", width_in_chars = 32,
                    fill_horizontal = 1, alignment = "center" },
            },
        }
        -- Both lists are direct siblings: one row owns their top and bottom.
        contents[#contents + 1] = f:row { spacing = 12, fill_horizontal = 1,
            f:simple_list { items = bind "availableItems", value = bind "availableChoice",
                allows_multiple_selection = true, fill_horizontal = 0.5, height = 220,
                tooltip = bind "highlightDetail" },
            f:column { width = 90, height = 220,
                f:column { spacing = 8, place_vertical = 0.5,
                    f:push_button { title = "Add →", width = 90,
                        action = function() move("availableChoice", true) end },
                    f:push_button { title = "← Remove", width = 90,
                        action = function() move("selectedChoice", false) end },
                },
            },
            f:simple_list { items = bind "selectedItems", value = bind "selectedChoice",
                allows_multiple_selection = true, fill_horizontal = 0.5, height = 220,
                tooltip = bind "highlightDetail" },
        }
        contents[#contents + 1] = f:row { spacing = 12, fill_horizontal = 1,
            f:column { fill_horizontal = 0.5, sideMinimum() },
            f:spacer { width = 90 },
            f:column { fill_horizontal = 0.5, sideMinimum(),
                f:static_text { title = bind "summary", width_in_chars = 32,
                    fill_horizontal = 1 },
            },
        }
        -- simple_list has no documented per-row hover API or horizontal bar.
        -- A wrapped detail and whole-list tooltip describe the highlighted row.
        contents[#contents + 1] = f:static_text { title = bind "highlightDetail",
            tooltip = bind "highlightDetail", width_in_chars = 96,
            height_in_lines = -1, fill_horizontal = 1 }
        local answer = LrDialogs.presentModalDialog {
            title = "FlickrGroupAddr — Group additions", resizable = true,
            actionVerb = p.actionTitle,
            actionBinding = {
                enabled = { bind_to_object = p, key = "allowed" },
                title = { bind_to_object = p, key = "actionTitle" },
            },
            cancelVerb = "Cancel", contents = f:column(contents),
        }
        s.query = p.query or ""
        if answer ~= "ok" then return {state="cancelled"} end
        return controller:commit()
    end)
end

return Dialog
