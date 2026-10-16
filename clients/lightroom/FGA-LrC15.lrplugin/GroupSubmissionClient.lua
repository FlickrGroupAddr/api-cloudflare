-- Production batch-client adapter. The host supplies its documented HTTP/JSON adapters.
-- No catalog access, Flickr request, partial selection, pacing, or automatic retry.
local Client = {}
Client.MAX_GROUP_IDS = 60
Client.PATH = "/api/v001/group-submission-batches"
local function opaque(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and string.match(value, "^[%w][%w@._:%-]*$") ~= nil
end
local function canonicalCredential(value)
    if type(value) ~= "string" or #value ~= 64 then return false end
    for index = 0, 11 do
        if not string.match(string.sub(value, index * 5 + 1, index * 5 + 4), "^[0-9A-HJKMNP-TV-Z]+$")
            or string.sub(value, index * 5 + 5, index * 5 + 5) ~= "-" then
            return false
        end
    end
    return string.match(string.sub(value, 61, 64), "^[0-9A-HJKMNP-TV-Z][0-9A-HJKMNP-TV-Z][0-9A-HJKMNP-TV-Z][0G]$") ~= nil
end
function Client.submit(bindingId, revision, groups, credential, post, encode)
    if not opaque(bindingId) or type(revision) ~= "number" or revision < 1
        or revision > 9007199254740991 or revision ~= math.floor(revision)
        or type(groups) ~= "table" then
        return nil, "invalid_selection"
    end
    local count = #groups
    if count < 1 or count > Client.MAX_GROUP_IDS then
        return nil, "invalid_selection"
    end
    local seen, values, keys = {}, {}, 0
    for key, value in pairs(groups) do
        if type(key) ~= "number" or key < 1 or key > count or key ~= math.floor(key)
            or not opaque(value) or seen[value] then
            return nil, "invalid_selection"
        end
        seen[value] = true
        keys = keys + 1
    end
    if keys ~= count then return nil, "invalid_selection" end
    for index = 1, count do values[index] = groups[index] end
    if not canonicalCredential(credential) then
        return nil, "invalid_credential"
    end
    local request = {
        schemaVersion = 2,
        photoBinding = {
            fgaPhotoBindingId = bindingId,
            expectedVerificationRevision = revision,
        },
        flickrGroupIds = values,
    }
    -- One encoding and one HTTP operation, after validation of the entire selection.
    return post(Client.PATH, encode(request), {
        { field = "Authorization", value = "Bearer " .. credential },
        { field = "Content-Type", value = "application/json" },
    })
end
return Client
