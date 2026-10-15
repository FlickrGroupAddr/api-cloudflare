-- Copyright 2026 Terry Ott. MIT License.
-- Pure fixture model. No host imports or durable side effects.
local M = {}
M.observedAt = "2026-10-15 12:00 UTC (synthetic)"
M.copy = {
    unavailable = "Group-addition status is unavailable. No FGA component submitted anything. Refresh before selecting groups.",
    moderation = "Flickr recorded a moderation submission for this photo and group. The final moderator decision is unknown. FGA components will not submit this exact pair again.",
    uncertain = "FGA records cannot prove whether Flickr received the add request. To avoid a duplicate request, FGA components will not submit this exact pair again. Inspect Flickr manually.",
    intent = "FGA already has a submission record for this photo and group. View its status; creating another submission is unavailable.",
}
function M.fixture(kind)
    local s = { kind = kind, bound = kind ~= "new", ready = true, groups = {},
        selected = {}, choice = "none", query = "", photo = "Harbor at dawn / DSC_0042.NEF",
        album = "Coastal light", scope = "service 12 / Album 34 / synthetic-photo-0042" }
    for i = 1, 376 do
        local topics = { "Architecture", "Birds", "Coast", "Landscape", "Night", "Travel" }
        s.groups[i] = { id = string.format("fixture-%04d@N00", i),
            name = string.format("%s photographers %03d", topics[(i - 1) % 6 + 1], i) }
    end
    if s.bound then
        s.groups[1].member = true
        s.groups[2].state = "queued"
        s.groups[3].state = "moderation_submitted"
        s.groups[3].block = "moderation_submission_recorded"
        s.groups[3].member = true -- Later membership must not hide permanent protection.
        s.groups[4].state = "delivery_uncertain"
        s.groups[4].block = "delivery_uncertain"
    end
    if kind == "empty" then s.groups = {} end
    if kind == "loading" or kind == "stale" or kind == "unavailable" then
        s.ready = false
    elseif kind == "contradictory" then
        s.groups[3].block = nil
    elseif kind == "existing" then
        s.photo = "Existing public Flickr photo / fixture-photo-A"
        s.album = "No Album attachment (existing-photo queue-only path)"
        s.scope = "binding fixture-existing-A / verification revision 3 (synthetic)"
    end
    table.sort(s.groups, function(a, b)
        return a.name == b.name and a.id < b.id or a.name < b.name
    end)
    return s
end
function M.valid(s)
    if not s.ready then return false end
    local seen = {}
    local states = { queued = true, moderation_submitted = true, delivery_uncertain = true }
    for _, g in ipairs(s.groups) do
        if type(g.id) ~= "string" or seen[g.id] or type(g.name) ~= "string" then return false end
        seen[g.id] = true
        if g.state and not states[g.state] then return false end
        if g.block and g.block ~= "moderation_submission_recorded" and g.block ~= "delivery_uncertain" then return false end
        if (g.state == "moderation_submitted") ~= (g.block == "moderation_submission_recorded") then return false end
        if (g.state == "delivery_uncertain") ~= (g.block == "delivery_uncertain") then return false end
    end
    return true
end
function M.code(s, g)
    if not M.valid(s) then return "unavailable" end
    if g.block == "moderation_submission_recorded" then return "moderation" end
    if g.block == "delivery_uncertain" then return "uncertain" end
    if g.member then return "member" end
    if g.state then return "intent" end
    return "eligible"
end
function M.count(s)
    local n = 0
    for _, v in pairs(s.selected) do if v then n = n + 1 end end
    return n
end
function M.mode(s, choice)
    s.choice = choice
    if choice == "none" then s.selected = {} end
end
function M.toggle(s, id, value)
    for _, g in ipairs(s.groups) do
        if g.id == id and M.code(s, g) == "eligible" then
            s.selected[id] = value == true
            if value then s.choice = "groups" end
            return true
        end
    end
    return false
end
function M.canConfirm(s)
    if not M.valid(s) then return false end
    local n = M.count(s)
    for id, v in pairs(s.selected) do
        if v then
            local eligible = false
            for _, g in ipairs(s.groups) do
                if g.id == id and M.code(s, g) == "eligible" then eligible = true end
            end
            if not eligible then return false end
        end
    end
    return (not s.bound and s.choice == "none" and n == 0)
        or (s.choice == "groups" and n >= 1 and n <= 60)
end
function M.matches(g, query)
    query = string.lower(query or "")
    return string.find(string.lower(g.name .. " " .. g.id), query, 1, true) ~= nil
end
function M.result(s, action)
    if action ~= "ok" or not M.canConfirm(s) then return nil end
    local ids = {}
    for id, v in pairs(s.selected) do if v then ids[#ids + 1] = id end end
    table.sort(ids)
    return { choice = s.choice, ids = ids, scope = s.scope }
end
return M
