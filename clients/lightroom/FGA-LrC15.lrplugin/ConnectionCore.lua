-- Pure connection rules for the production FlickrGroupAddr Lightroom plug-in.
-- This module has no Lightroom imports so its request and secret-handling rules
-- can be exercised under the same Lua 5.1 language version used by Lightroom.
local Core = {}

Core.PLUGIN_ID = "com.sixbuckssolutions.flickrgroupaddr.lrc15"
Core.CURRENT_KEY = "fga.installation.current"
Core.CANDIDATE_KEY = "fga.installation.rotation_candidate"
Core.PLUGIN_CODE_URL = "https://flickrgroupaddr.com/admin/"
Core.CURRENT_URL = "https://flickrgroupaddr.com/api/v001/installations/current"
Core.TIMEOUT_SECONDS = 30

local expectedFields = {
    schemaVersion = true,
    installationId = true,
    installationRevision = true,
    installationState = true,
    presentedCredentialState = true,
}

-- Only SDK-defined identifiers may be shown; never surface raw native error
-- text, HTTP bodies, headers, URLs, or exceptions beside a bearer credential.
local safeTransportCodes = {
    cancelled = true,
    badURL = true,
    timedOut = true,
    cannotFindHost = true,
    cannotConnectToHost = true,
    resourceUnavailable = true,
    networkConnectionLost = true,
    redirectError = true,
    badServerResponse = true,
    authenticationError = true,
    securityError = true,
    serverCertificateHasBadDate = true,
    serverCertificateHasUnknownRoot = true,
}

local function result(state, message, installationId, installationRevision, diagnostic)
    return {
        state = state,
        message = message,
        installationId = installationId,
        installationRevision = installationRevision,
        diagnostic = diagnostic,
    }
end

local function opaque(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and string.match(value, "^[A-Za-z0-9][A-Za-z0-9@._:%-]*$") ~= nil
end

function Core.isCanonicalCredential(value)
    if type(value) ~= "string" or #value ~= 64 then return false end
    for index = 0, 11 do
        local start = index * 5 + 1
        if string.match(string.sub(value, start, start + 3), "^[0-9A-HJKMNP-TV-Z]+$") == nil
            or string.sub(value, start + 4, start + 4) ~= "-" then
            return false
        end
    end
    return string.match(string.sub(value, 61, 64),
        "^[0-9A-HJKMNP-TV-Z][0-9A-HJKMNP-TV-Z][0-9A-HJKMNP-TV-Z][0G]$") ~= nil
end

local function exactCurrentDocument(value, expectedInstallationId)
    if type(value) ~= "table" then return false end
    local count = 0
    for key, _ in pairs(value) do
        if expectedFields[key] ~= true then return false end
        count = count + 1
    end
    if count ~= 5
        or value.schemaVersion ~= 1
        or not opaque(value.installationId)
        or type(value.installationRevision) ~= "number"
        or value.installationRevision < 1
        or value.installationRevision > 9007199254740991
        or value.installationRevision ~= math.floor(value.installationRevision)
        or value.installationState ~= "active"
        or (value.presentedCredentialState ~= "current"
            and value.presentedCredentialState ~= "pending_rotation") then
        return false
    end
    return expectedInstallationId == nil or value.installationId == expectedInstallationId
end

local function headerContains(headers, name, fragment)
    if type(headers) ~= "table" then return false end
    for _, header in pairs(headers) do
        if type(header) == "table" and type(header.field) == "string"
            and type(header.value) == "string"
            and string.lower(header.field) == string.lower(name)
            and string.find(header.value, fragment, 1, true) ~= nil then
            return true
        end
    end
    return false
end

local function decodeValue(body, decode)
    local ok, value = pcall(decode, body)
    if not ok or type(value) ~= "table" then return nil end
    return value
end

function Core.storeCurrent(credential, store, retrieve, clearTransient)
    if not Core.isCanonicalCredential(credential) then
        clearTransient()
        return false, "invalid_syntax"
    end

    local stored = pcall(store, Core.CURRENT_KEY, credential)
    clearTransient()
    if not stored then
        credential = nil
        return false, "secure_store_failed"
    end

    local retrieved, saved = pcall(retrieve, Core.CURRENT_KEY)
    local matches = retrieved and saved == credential
    credential = nil
    saved = nil
    if not matches then
        pcall(store, Core.CURRENT_KEY, "")
        return false, "secure_store_failed"
    end
    return true, nil
end

function Core.verifyCredential(credential, httpGet, decode, expectedInstallationId)
    if not Core.isCanonicalCredential(credential) then
        return result("stored_invalid", "The stored Plugin Code is not canonical.")
    end
    if expectedInstallationId ~= nil and not opaque(expectedInstallationId) then
        return result("local_identity_invalid", "The retained installation identity is invalid.")
    end

    local requestHeaders = {
        { field = "Authorization", value = "Bearer " .. credential },
    }
    -- LrHttp.get can yield. Lua 5.1's built-in pcall cannot enclose a yield;
    -- the owning Lightroom task uses LrTasks.pcall for yield-safe protection.
    local body, responseHeaders = httpGet(
        Core.CURRENT_URL, requestHeaders, Core.TIMEOUT_SECONDS)
    requestHeaders = nil
    credential = nil
    if type(responseHeaders) ~= "table" then
        return result("retryable", "Lightroom returned no HTTP response details. Try again.")
    end
    if body == nil then
        local transport = responseHeaders.error
        local code = type(transport) == "table" and transport.errorCode or nil
        if safeTransportCodes[code] then
            return result("retryable", "Lightroom network error: " .. code .. ".",
                nil, nil, code)
        end
        local status = responseHeaders.status
        if type(status) == "number" and status >= 100 and status <= 599
            and status == math.floor(status) then
            return result("retryable", "Lightroom received HTTP " .. tostring(status)
                .. " without a response body.", nil, nil, "http_" .. tostring(status))
        end
        return result("retryable", "Lightroom returned no HTTP response body. Try again.")
    end

    local status = responseHeaders.status
    if status == 200 then
        local value = decodeValue(body, decode)
        body = nil
        if not exactCurrentDocument(value, expectedInstallationId) then
            return result("service_response_invalid", "FGA returned an unexpected installation response.")
        end
        if value.presentedCredentialState ~= "current" then
            return result("rotation_incomplete",
                "A rotation candidate is present. Finish the browser rotation workflow before connecting.",
                value.installationId, value.installationRevision)
        end
        return result("connected", "Connected.", value.installationId,
            value.installationRevision)
    end

    if status == 401 then
        local value = decodeValue(body, decode)
        body = nil
        if value ~= nil and value.schemaVersion == 1 and type(value.error) == "table"
            and value.error.code == "invalid_token"
            and headerContains(responseHeaders, "WWW-Authenticate", 'error="invalid_token"') then
            return result("invalid_token",
                "The Plugin Code is invalid. Revoke this installation in FGA and create a new one.")
        end
        return result("authentication_unconfirmed", "FGA did not confirm this Plugin Code.")
    end

    body = nil
    if type(status) == "number" and status >= 500 and status <= 599 then
        return result("retryable", "The FGA service is temporarily unavailable. Try verification again.")
    end
    if status == 403 then
        return result("administrative_repair",
            "The Plugin Code was recognized but requires administrative repair.")
    end
    return result("service_response_invalid", "FGA returned an unexpected verification response.")
end

function Core.verifyStored(retrieve, httpGet, decode, expectedInstallationId)
    local candidateRead, candidate = pcall(retrieve, Core.CANDIDATE_KEY)
    if not candidateRead then
        return result("secure_store_failed", "The secure credential store is unavailable.")
    end
    if candidate ~= nil and candidate ~= "" then
        candidate = nil
        return result("rotation_incomplete",
            "A saved rotation candidate exists. Finish or cancel the browser rotation workflow.")
    end
    candidate = nil

    local currentRead, current = pcall(retrieve, Core.CURRENT_KEY)
    if not currentRead then
        return result("secure_store_failed", "The secure credential store is unavailable.")
    end
    if current == nil or current == "" then
        current = nil
        return result("disconnected", "No Plugin Code is stored.")
    end
    return Core.verifyCredential(current, httpGet, decode, expectedInstallationId)
end

return Core
