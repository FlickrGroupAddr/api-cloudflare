-- Pure Lua 5.1 group discovery. Only a complete validated aggregate is returned.
-- The SDK owner encloses yielding HTTP/sleep calls in LrTasks.pcall, never pcall.
local Module = {}
Module.URL = "https://flickrgroupaddr.com/api/v001/groups"
Module.PAGE_SIZE = 100
Module.MAX_PAGES = 100
Module.MAX_GROUPS = 10000
Module.MAX_BODY_BYTES = 2 * 1024 * 1024
Module.MAX_PENDING_POLLS = 12
Module.MAX_WAIT_SECONDS = 60

local function failure(state, message) return { state = state, message = message } end
local function invalid()
    return failure("service_response_invalid", "FGA returned an unexpected group response.")
end
local function exact(value, fields, required)
    if type(value) ~= "table" then return false end
    for key in pairs(value) do if not fields[key] then return false end end
    for _, key in ipairs(required) do if value[key] == nil then return false end end
    return true
end
local function opaque(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and string.match(value, "^[A-Za-z0-9][A-Za-z0-9@._:%-]*$") ~= nil
end
local function revision(value)
    return type(value) == "number" and value >= 1 and value <= 9007199254740991
        and value == math.floor(value)
end
local function byteLess(left, right)
    for index = 1, math.min(#left, #right) do
        local a, b = string.byte(left, index), string.byte(right, index)
        if a ~= b then return a < b end
    end
    return #left < #right
end
local function timestamp(value)
    if type(value) ~= "string" or #value > 40 then return false end
    local year, month, day, hour, minute, second, tail = string.match(value,
        "^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)(.*)$")
    if not year then return false end
    year, month, day = tonumber(year), tonumber(month), tonumber(day)
    if tail ~= "Z" and not string.match(tail, "^%.%d+Z$") then return false end
    local days = {31,28,31,30,31,30,31,31,30,31,30,31}
    if year % 4 == 0 and (year % 100 ~= 0 or year % 400 == 0) then days[2] = 29 end
    return month >= 1 and month <= 12 and day >= 1 and day <= days[month]
        and tonumber(hour) <= 23 and tonumber(minute) <= 59 and tonumber(second) <= 59
end
-- Validate UTF-8 and count Unicode characters to match the service's 1024 limit.
local function displayName(value)
    if type(value) ~= "string" or #value == 0 or #value > 4096 then return false end
    local pos, count = 1, 0
    while pos <= #value do
        local first = string.byte(value, pos)
        local width = first < 128 and 1 or first >= 194 and first <= 223 and 2
            or first >= 224 and first <= 239 and 3 or first >= 240 and first <= 244 and 4
        if not width or first < 32 or first == 127 or pos + width - 1 > #value then return false end
        for index = pos + 1, pos + width - 1 do
            local byte = string.byte(value, index)
            if byte < 128 or byte > 191 then return false end
        end
        local second = string.byte(value, pos + 1)
        if (first == 224 and second < 160) or (first == 237 and second > 159)
            or (first == 240 and second < 144) or (first == 244 and second > 143) then return false end
        pos, count = pos + width, count + 1
        if count > 1024 then return false end
    end
    return true
end
local pageFields = {schemaVersion=true, snapshotRevision=true, refreshedAt=true,
    snapshotStatus=true, refreshFailedAt=true, groups=true, nextAfterGroupId=true}
local pageRequired = {"schemaVersion", "snapshotRevision", "refreshedAt", "snapshotStatus",
    "groups", "nextAfterGroupId"}
local function pageValid(value, null, after)
    if not exact(value, pageFields, pageRequired) or value.schemaVersion ~= 1
        or not revision(value.snapshotRevision) or not timestamp(value.refreshedAt)
        or type(value.groups) ~= "table" or value.groups == null then return false end
    local arrayType = getmetatable(value.groups)
    if type(arrayType) ~= "table" or arrayType.__jsontype ~= "array" then return false end
    local status = value.snapshotStatus
    if status ~= "fresh" and status ~= "stale_refreshing" and status ~= "stale_refresh_failed" then
        return false
    end
    if status == "stale_refresh_failed" then
        if not timestamp(value.refreshFailedAt) then return false end
    elseif value.refreshFailedAt ~= nil then return false end
    local count, size, previous = 0, #value.groups, after
    if size > Module.PAGE_SIZE then return false end
    for key in pairs(value.groups) do
        if type(key) ~= "number" or key < 1 or key > size or key ~= math.floor(key) then return false end
        count = count + 1
    end
    if count ~= size then return false end
    for _, group in ipairs(value.groups) do
        if not exact(group, {flickrGroupId=true, displayName=true}, {"flickrGroupId", "displayName"})
            or not opaque(group.flickrGroupId) or not displayName(group.displayName)
            or (previous and not byteLess(previous, group.flickrGroupId)) then return false end
        previous = group.flickrGroupId
    end
    local nextId = value.nextAfterGroupId
    return nextId == null or (opaque(nextId) and size > 0 and nextId == previous)
end
local function errorCode(value)
    if not exact(value, {schemaVersion=true,error=true}, {"schemaVersion","error"})
        or value.schemaVersion ~= 1
        or not exact(value.error, {code=true,message=true,retryable=true,correlationId=true},
            {"code","message","retryable","correlationId"})
        or type(value.error.code) ~= "string" or type(value.error.message) ~= "string"
        or type(value.error.retryable) ~= "boolean" or not opaque(value.error.correlationId) then return nil end
    return value.error.code
end
local function retryAfter(headers)
    local found
    for _, header in pairs(headers) do
        if type(header) == "table" and type(header.field) == "string"
            and string.lower(header.field) == "retry-after" then
            if found ~= nil or type(header.value) ~= "string"
                or not string.match(header.value, "^%d+$") or #header.value > 3 then return nil end
            found = tonumber(header.value)
        end
    end
    if not found or found < 1 or found > Module.MAX_WAIT_SECONDS then return nil end
    return found
end
local function encode(value)
    return (string.gsub(value, "([^A-Za-z0-9%-._~])", function(char)
        return string.format("%%%02X", string.byte(char))
    end))
end
-- dkjson accepts comments, missing/trailing commas and non-JSON whitespace,
-- and overwrites duplicate keys. Check strict bounded grammar first; dkjson
-- still decodes strings/numbers and supplies the object/array/null identities.
local function strictJson(body, decode)
    local pos, length = 1, #body
    local function char() return string.sub(body, pos, pos) end
    local function white()
        while char() == " " or char() == "\t" or char() == "\r" or char() == "\n" do pos = pos + 1 end
    end
    local function jsonString()
        if char() ~= '"' then return nil end
        local start = pos
        pos = pos + 1
        while pos <= length do
            local current = char()
            if current == '"' then pos = pos + 1; return string.sub(body, start, pos - 1) end
            if string.byte(current) < 32 then return nil end
            if current == "\\" then
                pos = pos + 1
                current = char()
                if current == "u" then
                    if not string.match(string.sub(body, pos + 1, pos + 4), "^%x%x%x%x$") then return nil end
                    pos = pos + 4
                elseif current ~= '"' and current ~= "\\" and current ~= "/" and current ~= "b"
                    and current ~= "f" and current ~= "n" and current ~= "r" and current ~= "t" then return nil end
            end
            pos = pos + 1
        end
        return nil
    end
    local function digits()
        local start = pos
        while string.match(char(), "^[0-9]$") do pos = pos + 1 end
        return pos > start
    end
    local value
    value = function(depth)
        if depth > 32 then return false end
        white()
        local current = char()
        if current == '"' then return jsonString() ~= nil end
        if current == "{" or current == "[" then
            local object, keys = current == "{", {}
            local finish = object and "}" or "]"
            pos = pos + 1
            white()
            if char() == finish then pos = pos + 1; return true end
            while true do
                if object then
                    local rawKey = jsonString()
                    if not rawKey then return false end
                    local ok, key = pcall(decode, rawKey)
                    if not ok or type(key) ~= "string" or keys[key] then return false end
                    keys[key] = true
                    white()
                    if char() ~= ":" then return false end
                    pos = pos + 1
                end
                if not value(depth + 1) then return false end
                white()
                if char() == finish then pos = pos + 1; return true end
                if char() ~= "," then return false end
                pos = pos + 1
                white()
            end
        end
        for _, literal in ipairs({"true", "false", "null"}) do
            if string.sub(body, pos, pos + #literal - 1) == literal then
                pos = pos + #literal
                return true
            end
        end
        if current == "-" then pos = pos + 1 end
        if char() == "0" then pos = pos + 1
        elseif string.match(char(), "^[1-9]$") then digits()
        else return false end
        if char() == "." then pos = pos + 1; if not digits() then return false end end
        if char() == "e" or char() == "E" then
            pos = pos + 1
            if char() == "+" or char() == "-" then pos = pos + 1 end
            if not digits() then return false end
        end
        return true
    end
    if not value(1) then return false end
    white()
    return pos == length + 1
end

function Module.new(core)
    local Client = {}
    -- decode must reject malformed/trailing JSON and preserve explicit JSON null
    -- as jsonNull (dkjson.null). No callback may log a credential or response.
    function Client.discoverStored(retrieve, get, decode, sleep, cancelled, expectedId, jsonNull, onProgress)
        if jsonNull == nil or type(sleep) ~= "function" or type(cancelled) ~= "function" then
            return failure("internal_error", "Group discovery adapters are unavailable.")
        end
        local function isCancelled() return cancelled() == true end
        if isCancelled() then return failure("cancelled", "Group discovery cancelled.") end
        local credential
        local function read(key)
            local value = retrieve(key)
            if key == core.CURRENT_KEY then credential = value end
            return value
        end
        local connection = core.verifyStored(read, get, decode, expectedId)
        if connection.state ~= "connected" then credential = nil; return connection end
        if isCancelled() then credential = nil; return failure("cancelled", "Group discovery cancelled.") end
        local groups, after, snapshot, refreshedAt = {}, nil, nil, nil
        local pages, restarts, polls, waited = 0, 0, 0, 0
        local function credentialGate()
            -- A user can save a rotation candidate while HTTP/sleep yields.
            -- Recheck locally before each request; never switch credentials in
            -- the middle of one verified installation's aggregate.
            local candidateOk, candidate = pcall(retrieve, core.CANDIDATE_KEY)
            local currentOk, current = pcall(retrieve, core.CURRENT_KEY)
            if not candidateOk or not currentOk then
                return failure("secure_store_failed", "The secure credential store is unavailable.")
            end
            if (candidate ~= nil and candidate ~= "") or current ~= credential then
                return failure("rotation_incomplete", "The stored Plugin Code changed. Finish rotation and reload groups.")
            end
            return nil
        end
        while true do
            if isCancelled() then return failure("cancelled", "Group discovery cancelled.") end
            local gate = credentialGate()
            if gate then return gate end
            local url = Module.URL .. "?page_size=" .. tostring(Module.PAGE_SIZE)
            if snapshot then
                url = url .. "&snapshot_revision=" .. string.format("%.0f", snapshot)
                    .. "&after_group_id=" .. encode(after)
            end
            local body, headers = get(url, {{field="Authorization",value="Bearer " .. credential}},
                core.TIMEOUT_SECONDS)
            if isCancelled() then return failure("cancelled", "Group discovery cancelled.") end
            gate = credentialGate()
            if gate then return gate end
            if type(headers) ~= "table" or type(body) ~= "string" then
                return failure("retryable", "Group discovery could not reach FGA. Try again.")
            end
            if #body > Module.MAX_BODY_BYTES or not strictJson(body, decode) then return invalid() end
            local ok, value = pcall(decode, body)
            body = nil
            if not ok or type(value) ~= "table" then return invalid() end
            if headers.status == 200 then
                if not pageValid(value, jsonNull, after) then return invalid() end
                if snapshot and (snapshot ~= value.snapshotRevision or refreshedAt ~= value.refreshedAt) then
                    return invalid()
                end
                pages = pages + 1
                if pages > Module.MAX_PAGES or #groups + #value.groups > Module.MAX_GROUPS then return invalid() end
                for _, group in ipairs(value.groups) do
                    groups[#groups + 1] = {flickrGroupId=group.flickrGroupId,displayName=group.displayName}
                end
                if value.nextAfterGroupId == jsonNull then
                    credential = nil
                    return {state="complete",message="Groups loaded.",groups=groups,
                        snapshotRevision=value.snapshotRevision,refreshedAt=value.refreshedAt,
                        snapshotStatus=value.snapshotStatus,refreshFailedAt=value.refreshFailedAt}
                end
                if pages >= Module.MAX_PAGES then return invalid() end
                snapshot, after, refreshedAt = value.snapshotRevision, value.nextAfterGroupId, value.refreshedAt
            elseif headers.status == 202 then
                if snapshot or not exact(value, {schemaVersion=true,status=true}, {"schemaVersion","status"})
                    or value.schemaVersion ~= 1 or value.status ~= "refreshing" then return invalid() end
                local delay = retryAfter(headers)
                if not delay then return invalid() end
                if onProgress ~= nil then onProgress("refreshing") end
                polls = polls + 1
                if polls > Module.MAX_PENDING_POLLS or waited + delay > Module.MAX_WAIT_SECONDS then
                    return failure("retryable", "FGA is still refreshing groups. Try again later.")
                end
                for _ = 1, delay do
                    if isCancelled() then return failure("cancelled", "Group discovery cancelled.") end
                    sleep(1)
                    waited = waited + 1
                end
            elseif headers.status == 409 and errorCode(value) == "snapshot_changed" then
                if restarts >= 1 then return failure("snapshot_changed", "Groups changed again. Try discovery again.") end
                groups, after, snapshot, refreshedAt, pages = {}, nil, nil, nil, 0
                restarts = restarts + 1
            elseif headers.status == 401 then
                return failure("authentication_unconfirmed", "FGA did not authorize group discovery. Verify the connection.")
            elseif headers.status == 403 then
                return failure("administrative_repair", "The Flickr connection requires administrative repair.")
            elseif type(headers.status) == "number" and headers.status >= 500 and headers.status <= 599 then
                return failure("retryable", "FGA group discovery is unavailable. Try again later.")
            else return invalid() end
        end
    end
    return Client
end
return Module
