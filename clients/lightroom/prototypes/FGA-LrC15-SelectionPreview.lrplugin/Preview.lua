-- Copyright 2026 Terry Ott. MIT License.
local LrBinding = import "LrBinding"
local LrDialogs = import "LrDialogs"
local LrFunctionContext = import "LrFunctionContext"
local LrPathUtils = import "LrPathUtils"
local LrTasks = import "LrTasks"
local LrView = import "LrView"
local M = dofile(LrPathUtils.child(_PLUGIN.path, "SelectionModel.lua"))
local bind = LrView.bind
local f = LrView.osFactory()

local function text(value, lines)
    return f:static_text { title = value, width_in_chars = 96,
        height_in_lines = lines and -1 or 1, fill_horizontal = 1 }
end

local function chooseFixture()
    return LrFunctionContext.callWithContext("fixture choice", function(context)
        local p = LrBinding.makePropertyTable(context)
        p.kind = "new"
        local items = {}
        for _, row in ipairs({
            { "new", "Unpublished photo in one FGA Album" },
            { "bound", "FGA-bound photo: memberships and retained intents" },
            { "bound59", "Bound limit test: 59 preselected eligible additions (synthetic)" },
            { "existing", "Existing public Flickr photo: verified fixture binding" },
            { "loading", "Loading complete projections" },
            { "empty", "Complete empty writable-group snapshot and memberships" },
            { "stale", "Stale prior observation; new read incomplete" },
            { "unavailable", "Required membership/history read unavailable" },
            { "contradictory", "Contradictory moderation state/block projection" },
        }) do items[#items + 1] = { value = row[1], title = row[2] } end
        local answer = LrDialogs.presentModalDialog {
            title = "FGA Selection Preview — fixtures only", actionVerb = "Open preview",
            contents = f:column { bind_to_object = p, spacing = 10,
                text("No account, catalog, credentials, API requests, or submissions are used."),
                text("Choose synthetic photo context and data condition:"),
                f:popup_menu { value = bind "kind", items = items, width_in_chars = 80 },
            },
        }
        return answer == "ok" and p.kind or nil
    end)
end

local function show(s)
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
        for _, g in ipairs(s.groups) do
            local group = g
            local code = M.code(s, group)
            if code ~= "eligible" and code ~= "unavailable" then
                local copy = M.copy[code]
                if code == "member" then
                    copy = "Currently in this Flickr group as observed at " .. M.observedAt .. ". Membership is read-only in FGA."
                end
                readonly[#readonly + 1] = text(group.name .. " [" .. group.id .. "]")
                readonly[#readonly + 1] = text(copy, 3)
                if group.member and code ~= "member" then
                    readonly[#readonly + 1] = text("Membership was later observed at " .. M.observedAt .. ".")
                end
            end
        end
        if #readonly == 0 then readonly[1] = text("No current memberships or retained intents in this complete fixture.") end
        local status
        if not M.valid(s) then
            status = s.kind == "loading" and "Loading complete projections — confirmation disabled."
                or M.copy.unavailable
            readonly = { text(s.kind == "stale"
                and "Prior observation is STALE, for diagnosis only. Current membership is Unavailable."
                or "Current memberships and retained intents: Unavailable. No partial rows displayed.", 2) }
        elseif not s.bound then
            status = "Not yet published. Groups are optional for this FGA Album."
        end
        refreshLists()
        sync()
        local contents = { bind_to_object = p, spacing = 8, fill_horizontal = 1,
            text("Preview only — nothing is saved or submitted."),
            text("Photo: " .. s.photo), text("FGA Album: " .. s.album),
        }
        if status then contents[#contents + 1] = text(status, 3) end
        if s.bound then
            contents[#contents + 1] = text("Current memberships and submission records (read-only)")
            contents[#contents + 1] = f:scrolled_view { height = 125, width = 740, f:column(readonly) }
        end
        contents[#contents + 1] = text("Changing selections never removes membership, cancels an intent, or clears protection.", 2)
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
            title = "FlickrGroupAddr — Group additions (FIXTURE PREVIEW)", resizable = true,
            actionVerb = p.actionTitle,
            actionBinding = {
                enabled = { bind_to_object = p, key = "allowed" },
                title = { bind_to_object = p, key = "actionTitle" },
            },
            cancelVerb = "Cancel", contents = f:column(contents),
        }
        s.query = p.query or ""
        return answer
    end)
end

LrTasks.startAsyncTask(function()
    local kind = chooseFixture()
    if not kind then return end
    local s = M.fixture(kind)
    local answer = show(s)
    local result = M.result(s, answer)
    if result then
        local nextStep = s.bound
            and "Production would snapshot into the local outbox and hand off additions without rendering/uploading. Existing public photos require fresh proof before handoff."
            or "Production would save this photo/Album selection. Use the Album's ordinary Publish action separately."
        LrDialogs.message("Fixture confirmation only",
            string.format("Choice: %s; %d group(s).\n%s\n\nNothing was saved or queued. Close/reopen resets every choice.",
                result.choice, #result.ids, nextStep), "info")
    end
end)
