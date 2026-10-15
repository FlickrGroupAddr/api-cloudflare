-- Pure Lua 5.1 protocol client. The host owns yielding/error protection and
-- secure credentials; injected requests never expose credentials to UI state.
local Client = {}
Client.PAGE_SIZE = 5
Client.MAX_MEMBERSHIPS = 10000
Client.MAX_RESPONSE_BYTES = 2097152
Client.PRODUCTION_QUALIFIED = false

local function integer(value, minimum, maximum)
    return type(value) == "number" and value >= minimum and value <= maximum
        and value == math.floor(value)
end
local function opaque(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and value:match("^[A-Za-z0-9][A-Za-z0-9@._:%-]*$") ~= nil
end
local function text(value, limit)
    return type(value) == "string" and #value <= limit and not value:find("[%z\1-\8\11\12\14-\31\127]")
end
local function calendar(value, separator)
    if type(value) ~= "string" then return false end
    local year, month, day, hour, minute, second = value:match(
        "^(%d%d%d%d)%-(%d%d)%-(%d%d)" .. separator .. "(%d%d):(%d%d):(%d%d)")
    year, month, day = tonumber(year), tonumber(month), tonumber(day)
    hour, minute, second = tonumber(hour), tonumber(minute), tonumber(second)
    if not year or month < 1 or month > 12 or day < 1
        or hour > 23 or minute > 59 or second > 59 then return false end
    local days = {31,28,31,30,31,30,31,31,30,31,30,31}
    if year % 400 == 0 or (year % 4 == 0 and year % 100 ~= 0) then days[2] = 29 end
    return day <= days[month]
end
local function timestamp(value)
    if type(value) ~= "string" or #value > 40 or not calendar(value, "T") then return false end
    return value:match("^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%dZ$") ~= nil
        or value:match("^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d%.%d+Z$") ~= nil
end
local function captureDate(value)
    return type(value) == "string" and #value == 19 and calendar(value, " ")
end
local function uploadDate(value)
    return type(value) == "string" and #value <= 13 and value:match("^%d+$") ~= nil
        and (value == "0" or value:sub(1, 1) ~= "0") and tonumber(value) <= 8640000000000
end
local function bytewiseLess(left, right)
    for index = 1, math.min(#left, #right) do
        local a, b = left:byte(index), right:byte(index)
        if a ~= b then return a < b end
    end
    return #left < #right
end
local function exact(value, keys)
    if type(value) ~= "table" then return false end
    local count = 0
    for key in pairs(value) do
        if not keys[key] then return false end
        count = count + 1
    end
    local expected = 0
    for _ in pairs(keys) do expected = expected + 1 end
    return count == expected
end
local function array(value, limit)
    if type(value) ~= "table" then return false end
    local meta = getmetatable(value)
    -- dkjson distinguishes [] from {} even when either is empty.
    if meta == nil or meta.__jsontype ~= "array" or #value > limit then return false end
    local count = 0
    for key in pairs(value) do
        if not integer(key, 1, #value) then return false end
        count = count + 1
    end
    return count == #value
end
local function encodeComponent(value)
    return (value:gsub("([^A-Za-z0-9_.~-])", function(character)
        return string.format("%%%02X", string.byte(character))
    end))
end
function Client.allowedThumbnail(url)
    if type(url) ~= "string" or #url > 2048 then return false end
    local extension = url:match("^https://live%.staticflickr%.com/%d+/[A-Za-z0-9_%-]+_q%.([a-z]+)$")
    return extension == "jpg" or extension == "jpeg" or extension == "png"
end
local pageKeys = { schemaVersion=true, linkedFlickrRevision=true, observedAt=true,
    page=true, pageSize=true, pages=true, total=true, photos=true }
local photoKeys = { flickrPhotoId=true, title=true, dateUploaded=true, dateTaken=true, thumbnail=true }
function Client.validatePage(value, pageNumber, pageSize)
    if not exact(value, pageKeys) or value.schemaVersion ~= 1
        or not integer(value.linkedFlickrRevision, 1, 9007199254740991)
        or not timestamp(value.observedAt) or value.page ~= pageNumber or value.pageSize ~= pageSize
        or not integer(value.pages, 0, 1000000) or not integer(value.total, 0, 100000000)
        or not array(value.photos, pageSize) then return false end
    if (#value.photos == 0 and (value.total ~= 0 or pageNumber ~= 1 or value.pages > 1))
        or (#value.photos > 0 and (value.pages < pageNumber or value.total < #value.photos)) then
        return false
    end
    local seen = {}
    for _, photo in ipairs(value.photos) do
        if not exact(photo, photoKeys) or not opaque(photo.flickrPhotoId) or seen[photo.flickrPhotoId]
            or not text(photo.title, 1024) or not uploadDate(photo.dateUploaded)
            or not captureDate(photo.dateTaken)
            or not exact(photo.thumbnail, {url=true, sizeClass=true})
            or photo.thumbnail.sizeClass ~= "q" or not Client.allowedThumbnail(photo.thumbnail.url) then
            return false
        end
        seen[photo.flickrPhotoId] = true
    end
    return true
end
local bindingKeys = {schemaVersion=true, fgaPhotoBindingId=true, sourceKind=true,
    flickrPhotoId=true, linkedFlickrRevision=true, verificationRevision=true, verifiedAt=true}
function Client.validateBinding(value, photoId, linkRevision)
    return exact(value, bindingKeys) and value.schemaVersion == 1
        and opaque(value.fgaPhotoBindingId) and value.flickrPhotoId == photoId
        and (value.sourceKind == "existing_public_flickr_photo" or value.sourceKind == "fga_direct_upload")
        and value.linkedFlickrRevision == linkRevision
        and integer(value.verificationRevision, 1, 9007199254740991) and timestamp(value.verifiedAt)
end
local safeErrors = {invalid_token=true, flickr_link_changed=true, photo_owner_mismatch=true,
    existing_photo_not_public=true, invalid_existing_photo=true, existing_photo_verification_unavailable=true,
    existing_photo_discovery_unavailable=true, membership_observation_unavailable=true,
    membership_observation_changed=true, not_found=true}
local function readResponse(dependencies, method, path, body)
    if dependencies.cancelled and dependencies.cancelled() then return nil, "cancelled" end
    -- request may yield; do not wrap it in Lua 5.1 pcall.
    local bytes, headers = dependencies.request(method, path, body)
    if dependencies.cancelled and dependencies.cancelled() then return nil, "cancelled" end
    if type(bytes) ~= "string" or #bytes > Client.MAX_RESPONSE_BYTES or type(headers) ~= "table" then
        return nil, "unavailable"
    end
    local ok, document = pcall(dependencies.decode, bytes)
    if not ok or type(document) ~= "table" then return nil, "response_invalid" end
    if headers.status ~= 200 and headers.status ~= 201 then
        local code = type(document.error) == "table" and document.error.code or nil
        return nil, safeErrors[code] and code or "unavailable"
    end
    if method == "GET" and headers.status ~= 200 then return nil, "response_invalid" end
    return document
end
function Client.discover(dependencies, pageNumber, pageSize)
    pageSize = pageSize or Client.PAGE_SIZE
    if not integer(pageNumber, 1, 1000000) or not integer(pageSize, 1, 100) then return nil, "invalid_request" end
    local value, reason = readResponse(dependencies, "GET", "/api/v001/existing-public-photos?page="
        .. tostring(pageNumber) .. "&page_size=" .. tostring(pageSize))
    if not value then return nil, reason end
    if not Client.validatePage(value, pageNumber, pageSize) then return nil, "response_invalid" end
    return value
end
function Client.prove(dependencies, photoId, linkedRevision)
    if not opaque(photoId) or not integer(linkedRevision, 1, 9007199254740991) then return nil, "invalid_request" end
    local value, reason = readResponse(dependencies, "POST", "/api/v001/existing-public-photo-bindings", {
        schemaVersion = 1, flickrPhotoId = photoId, expectedLinkedFlickrRevision = linkedRevision,
    })
    if not value then return nil, reason end
    if not Client.validateBinding(value, photoId, linkedRevision) then return nil, "response_invalid" end
    return value
end
local membershipKeys = {schemaVersion=true, fgaPhotoBindingId=true, flickrPhotoId=true,
    observationRevision=true, observedAt=true, groups=true, nextAfterGroupId=true}
local function membershipsOnce(dependencies, binding)
    local groups, seen, revision, observedAt, after = {}, {}, nil, nil, nil
    for _ = 1, 100 do
        local path = "/api/v001/photo-bindings/" .. encodeComponent(binding.fgaPhotoBindingId)
            .. "/group-memberships?page_size=100"
        if after then path = path .. "&observation_revision=" .. string.format("%.0f", revision)
            .. "&after_group_id=" .. encodeComponent(after) end
        local page, reason = readResponse(dependencies, "GET", path)
        if not page then return nil, reason end
        if not exact(page, membershipKeys) or page.schemaVersion ~= 1
            or page.fgaPhotoBindingId ~= binding.fgaPhotoBindingId or page.flickrPhotoId ~= binding.flickrPhotoId
            or not integer(page.observationRevision, 1, 9007199254740991) or not timestamp(page.observedAt)
            or not array(page.groups, 100) then return nil, "response_invalid" end
        if revision and (revision ~= page.observationRevision or observedAt ~= page.observedAt) then
            return nil, "membership_observation_changed"
        end
        revision, observedAt = page.observationRevision, page.observedAt
        local previous = after
        for _, group in ipairs(page.groups) do
            if not exact(group, {flickrGroupId=true, displayName=true}) or not opaque(group.flickrGroupId)
                or not text(group.displayName, 1024) or seen[group.flickrGroupId]
                or (previous and not bytewiseLess(previous, group.flickrGroupId)) then return nil, "response_invalid" end
            previous = group.flickrGroupId
            seen[group.flickrGroupId] = true
            groups[#groups + 1] = group
        end
        if #groups > Client.MAX_MEMBERSHIPS then return nil, "response_invalid" end
        if page.nextAfterGroupId == dependencies.jsonNull then
            return {groups=groups, observedAt=observedAt, observationRevision=revision,
                fgaPhotoBindingId=binding.fgaPhotoBindingId, flickrPhotoId=binding.flickrPhotoId}
        end
        if #page.groups == 0 or not opaque(page.nextAfterGroupId) or page.nextAfterGroupId ~= previous then
            return nil, "response_invalid"
        end
        after = page.nextAfterGroupId
    end
    return nil, "membership_observation_unavailable"
end
function Client.memberships(dependencies, binding)
    if type(binding) ~= "table" or not opaque(binding.fgaPhotoBindingId) or not opaque(binding.flickrPhotoId) then
        return nil, "invalid_request"
    end
    local result, reason = membershipsOnce(dependencies, binding)
    if not result and reason == "membership_observation_changed" then
        return membershipsOnce(dependencies, binding)
    end
    return result, reason
end
function Client.encodeProof(body, encode)
    if not exact(body, {schemaVersion=true, flickrPhotoId=true, expectedLinkedFlickrRevision=true})
        or body.schemaVersion ~= 1 or not opaque(body.flickrPhotoId)
        or not integer(body.expectedLinkedFlickrRevision, 1, 9007199254740991) then return nil end
    -- Lua 5.1 tostring (and dkjson's default number encoder) rounds high safe
    -- integers. Preserve the exact revision without changing vendored dkjson.
    return '{"schemaVersion":1,"flickrPhotoId":' .. encode(body.flickrPhotoId)
        .. ',"expectedLinkedFlickrRevision":' .. string.format("%.0f", body.expectedLinkedFlickrRevision) .. '}'
end
function Client.authenticatedRequest(dependencies, core)
    return function(method, path, body)
        -- luacheck: push ignore 311
        local verifiedCredential
        local verification = core.verifyStored(function(key)
            local value = dependencies.retrieve(key)
            if key == core.CURRENT_KEY then verifiedCredential = value end
            return value
        end, dependencies.httpGet, dependencies.decode, dependencies.expectedInstallationId)
        if verification.state ~= "connected" then verifiedCredential = nil; return nil, {} end
        local function unchanged()
            local candidateOk, candidate = pcall(dependencies.retrieve, core.CANDIDATE_KEY)
            local currentOk, current = pcall(dependencies.retrieve, core.CURRENT_KEY)
            local same = candidateOk and (candidate == nil or candidate == "") and currentOk
                and current == verifiedCredential and core.isCanonicalCredential(current)
            current, candidate = nil, nil
            return same
        end
        if not unchanged() then verifiedCredential = nil; return nil, {} end
        local headers = {{field="Authorization", value="Bearer " .. verifiedCredential}}
        local bytes, responseHeaders
        if method == "GET" then
            bytes, responseHeaders = dependencies.httpGet("https://flickrgroupaddr.com" .. path,
                headers, core.TIMEOUT_SECONDS)
        elseif method == "POST" and path == "/api/v001/existing-public-photo-bindings" then
            local encoded = Client.encodeProof(body, dependencies.encode)
            if not encoded then verifiedCredential = nil; return nil, {} end
            headers[#headers + 1] = {field="Content-Type", value="application/json"}
            bytes, responseHeaders = dependencies.httpPost("https://flickrgroupaddr.com" .. path,
                encoded, headers, "POST", core.TIMEOUT_SECONDS)
        else verifiedCredential = nil; return nil, {} end
        headers = nil
        if not unchanged() then bytes = nil; verifiedCredential = nil; return nil, {} end
        verifiedCredential = nil
        return bytes, responseHeaders
        -- luacheck: pop
    end
end
return Client
