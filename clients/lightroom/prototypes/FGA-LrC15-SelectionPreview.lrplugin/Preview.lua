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
        local function refreshLists()
            local available, selected = {}, {}
            local total = 0
            s.query = p.query or ""
            for _, group in ipairs(s.groups) do
                if M.code(s, group) == "eligible" then
                    total = total + 1
                    local row = { title = "[" .. group.id .. "]  " .. group.name, value = group.id }
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
            p.searchSummary = string.format("%d available matches / %d eligible groups", #available, total)
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
            if type(values) ~= "table" or #values ~= 1 then return end
            local id = values[1]
            local items = selecting and p.availableItems or p.selectedItems
            local present = false
            for _, row in ipairs(items) do if row.value == id then present = true end end
            if not present then return end
            if (s.selected[id] == true) == selecting then return end
            if M.toggle(s, id, selecting) then
                refreshLists()
                sync()
            end
        end
        p.availableChoice, p.selectedChoice = {}, {}
        local function queryChanged()
            if s.query ~= (p.query or "") then refreshLists() end
        end
        p:addObserver("query", queryChanged)
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
        contents[#contents + 1] = f:row { spacing = 12,
            f:column { spacing = 4, width = 325,
                f:static_text { title = "Available groups — search name or ID:", width = 325 },
                f:edit_field { value = bind "query", immediate = true, width = 325,
                    validate = function(_, value)
                        -- The edit-properties reference explicitly guarantees
                        -- validation on every change with immediate=true.
                        p.query = value or ""
                        queryChanged()
                        return true, value
                    end,
                },
            },
            f:spacer { width = 90 },
            f:static_text { title = "Selected additions", width = 325 },
        }
        contents[#contents + 1] = f:row { spacing = 12,
            f:simple_list { items = bind "availableItems", value = bind "availableChoice",
                allows_multiple_selection = false, width = 325, height = 220 },
            -- SDK node layout place_vertical=.5 centers this column in the
            -- list row's free height, independently of the search/header row.
            f:column { spacing = 8, width = 90, place_vertical = 0.5,
                f:push_button { title = "Add →", width = 90, fill_horizontal = 1,
                    action = function() move("availableChoice", true) end },
                f:push_button { title = "← Remove", width = 90, fill_horizontal = 1,
                    action = function() move("selectedChoice", false) end },
            },
            f:simple_list { items = bind "selectedItems", value = bind "selectedChoice",
                allows_multiple_selection = false, width = 325, height = 220 },
        }
        contents[#contents + 1] = f:static_text { title = bind "searchSummary", width_in_chars = 96 }
        contents[#contents + 1] = f:static_text { title = bind "summary", width_in_chars = 96 }
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
