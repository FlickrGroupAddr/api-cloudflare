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
        p.query, p.choice = s.query, s.choice
        local updating = false
        local function sync()
            p.allowed = M.canConfirm(s)
            p.summary = string.format("%d selected / 60 maximum. Hidden search results keep their selection.", M.count(s))
        end
        p:addObserver("choice", function()
            if updating then return end
            M.mode(s, p.choice)
            if p.choice == "none" then
                updating = true
                for i, _ in ipairs(s.groups) do p["g" .. i] = false end
                updating = false
            end
            sync()
        end)
        local eligible = { spacing = 4 }
        local readonly = { spacing = 8 }
        local shown, total = 0, 0
        for i, g in ipairs(s.groups) do
            local group, key = g, "g" .. i
            local code = M.code(s, group)
            if code == "eligible" then
                total = total + 1
                p[key] = s.selected[group.id] == true
                p:addObserver(key, function()
                    if updating then return end
                    -- SDK notifications may be deferred or repeated. A queued
                    -- no-op must not overwrite a newer radio-button choice.
                    if (p[key] == true) == (s.selected[group.id] == true) then return end
                    M.toggle(s, group.id, p[key])
                    updating = true
                    -- Only checking a group changes the radio mode. An
                    -- unchecked notification must not replace a newer choice.
                    if p[key] == true then p.choice = s.choice end
                    updating = false
                    sync()
                end)
                if M.matches(group, s.query) then
                    shown = shown + 1
                    eligible[#eligible + 1] = f:checkbox {
                        title = group.name .. "  [" .. group.id .. "]", value = bind(key),
                        width_in_chars = 92,
                    }
                end
            elseif code ~= "unavailable" then
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
        if #eligible == 0 then eligible[1] = text("No eligible groups match this view.") end
        if #readonly == 0 then readonly[1] = text("No current memberships or retained intents in this complete fixture.") end
        local status
        if not M.valid(s) then
            status = s.kind == "loading" and "Loading complete projections — confirmation disabled."
                or M.copy.unavailable
            readonly = { text(s.kind == "stale"
                and "Prior observation is STALE, for diagnosis only. Current membership is Unavailable."
                or "Current memberships and retained intents: Unavailable. No partial rows displayed.", 2) }
        elseif s.bound then
            status = "Complete writable groups, fresh membership and retained history: " .. M.observedAt
        else
            status = "Not yet published by this FGA collection. Writable groups: " .. M.observedAt
            readonly = { text("No Flickr membership request for this unpublished fixture.") }
        end
        sync()
        local contents = { bind_to_object = p, spacing = 8, fill_horizontal = 1,
            text("FIXTURE PREVIEW — every confirmation produces only an in-memory summary."),
            text("Photo: " .. s.photo), text("FGA Album: " .. s.album), text("Scope: " .. s.scope),
            text(status, 3),
            text("Currently in Flickr groups / existing or protected submission records (read-only)"),
            f:scrolled_view { height = 125, width = 740, f:column(readonly) },
        }
        if not s.bound then
            contents[#contents + 1] = f:row {
                f:radio_button { title = "No group additions", value = bind "choice", checked_value = "none" },
                f:radio_button { title = "Add to selected groups", value = bind "choice", checked_value = "groups" },
            }
        end
        contents[#contents + 1] = text("Additions only — unchecking never removes membership, cancels an intent, or clears protection.", 2)
        contents[#contents + 1] = f:row {
            f:static_text { title = "Find name or exact group ID:" },
            f:edit_field { value = bind "query", width_in_chars = 45 },
        }
        contents[#contents + 1] = text(string.format("Showing %d of %d eligible groups; sorted by name, with exact IDs.", shown, total))
        contents[#contents + 1] = f:scrolled_view { height = 220, width = 740, f:column(eligible) }
        contents[#contents + 1] = f:static_text { title = bind "summary", width_in_chars = 96 }
        contents[#contents + 1] = text("Refresh: close this fixture and reopen a complete bound/new fixture from the launcher.")
        local answer = LrDialogs.presentModalDialog {
            title = "FlickrGroupAddr — Group additions (FIXTURE PREVIEW)", resizable = true,
            actionVerb = s.bound and "Queue selected additions" or "Save for publish",
            actionBinding = { enabled = { bind_to_object = p, key = "allowed" } },
            cancelVerb = "Cancel", otherVerb = "Apply search", contents = f:column(contents),
        }
        s.query = p.query or ""
        return answer
    end)
end

LrTasks.startAsyncTask(function()
    local kind = chooseFixture()
    if not kind then return end
    local s = M.fixture(kind)
    local answer
    repeat answer = show(s) until answer ~= "other"
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
