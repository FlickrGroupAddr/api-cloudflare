local LrHttp = import "LrHttp"
local LrLogger = import "LrLogger"
local LrPasswords = import "LrPasswords"
local LrPrefs = import "LrPrefs"
local LrTasks = import "LrTasks"

local Core = require "ConnectionCore"
local json = require "dkjson"

local Controller = {}
local prefs = LrPrefs.prefsForPlugin()
local logger = LrLogger("FGA-LrC15")
local loggingEnabled = pcall(function() logger:enable("logfile") end)

local logStates = {
    client_loaded = true,
    request_started = true,
    connected = true,
    retryable = true,
    invalid_token = true,
    authentication_unconfirmed = true,
    administrative_repair = true,
    service_response_invalid = true,
    rotation_incomplete = true,
    stored_invalid = true,
    local_identity_invalid = true,
    secure_store_failed = true,
    disconnected = true,
    internal_error = true,
}
local logDiagnostics = {
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

local function logSafe(state, diagnostic)
    if not loggingEnabled then return end
    local safeState = logStates[state] and state or "unknown"
    local safeDiagnostic = logDiagnostics[diagnostic] and diagnostic or "none"
    if type(diagnostic) == "string" and string.match(diagnostic, "^http_[1-5]%d%d$") then
        safeDiagnostic = diagnostic
    end
    pcall(function()
        logger:info("connection state=" .. safeState .. " diagnostic=" .. safeDiagnostic)
    end)
end

logSafe("client_loaded", nil)

local function retrieve(key)
    return LrPasswords.retrieve(key, nil, Core.PLUGIN_ID)
end

local function store(key, value)
    LrPasswords.store(key, value, nil, Core.PLUGIN_ID)
end

local function decode(body)
    local value, _, decodeError = json.decode(body, 1, nil)
    if decodeError ~= nil then return nil end
    return value
end

local function refreshStorageState(properties)
    local candidateOk, candidate = pcall(retrieve, Core.CANDIDATE_KEY)
    local currentOk, current = pcall(retrieve, Core.CURRENT_KEY)
    if not candidateOk or not currentOk then
        properties.hasStoredCode = false
        properties.canStore = false
        return false, "The secure credential store is unavailable."
    end
    if candidate ~= nil and candidate ~= "" then
        properties.hasStoredCode = true
        properties.canStore = false
        candidate = nil
        current = nil
        return false, "A rotation candidate is stored. Finish or cancel rotation before continuing."
    end
    candidate = nil
    properties.hasStoredCode = current ~= nil and current ~= ""
    properties.canStore = not properties.hasStoredCode
    current = nil
    return true, nil
end

local function clearInvalidCurrent()
    local stored = pcall(store, Core.CURRENT_KEY, "")
    local read, value = pcall(retrieve, Core.CURRENT_KEY)
    local cleared = stored and read and value == ""
    value = nil
    if cleared then
        prefs.installationId = nil
        prefs.installationRevision = nil
    end
    return cleared
end

local function applyResult(properties, verification)
    if verification.state == "connected" then
        prefs.installationId = verification.installationId
        prefs.installationRevision = verification.installationRevision
        properties.installation = verification.installationId
            .. " (revision " .. tostring(verification.installationRevision) .. ")"
    elseif verification.state == "invalid_token" or verification.state == "stored_invalid" then
        if not clearInvalidCurrent() then
            verification.message = "The Plugin Code was rejected, but secure-store cleanup could not be confirmed."
        end
        properties.installation = "Not connected"
    else
        properties.installation = prefs.installationId ~= nil
            and prefs.installationId .. " (last verified)" or "Not connected"
    end
    properties.status = verification.message
    refreshStorageState(properties)
end

local function beginVerification(properties)
    if properties.busy then return end
    properties.busy = true
    properties.status = "Verifying the stored Plugin Code..."
    logSafe("request_started", nil)
    LrTasks.startAsyncTask(function()
        local ok, verification = LrTasks.pcall(Core.verifyStored, retrieve, LrHttp.get, decode,
            prefs.installationId)
        if not ok or type(verification) ~= "table" then
            verification = {
                state = "internal_error",
                message = "Verification could not be completed. Try again.",
            }
        end
        logSafe(verification.state, verification.diagnostic)
        applyResult(properties, verification)
        properties.busy = false
    end)
end

function Controller.initialize(properties)
    properties.pluginCodeUrl = Core.PLUGIN_CODE_URL
    properties.pluginCode = ""
    properties.busy = false
    properties.installation = prefs.installationId ~= nil
        and prefs.installationId .. " (last verified)" or "Not connected"
    local available, message = refreshStorageState(properties)
    if message ~= nil then
        properties.status = message
    elseif properties.hasStoredCode then
        properties.status = "A Plugin Code is stored. Verify it to connect."
    elseif available then
        properties.status = "No Plugin Code is stored."
    end
end

function Controller.restoreUrl(properties)
    if properties.pluginCodeUrl ~= Core.PLUGIN_CODE_URL then
        properties.pluginCodeUrl = Core.PLUGIN_CODE_URL
    end
end

function Controller.storeAndVerify(properties)
    if properties.busy then return end
    local available, message = refreshStorageState(properties)
    if not available or properties.hasStoredCode then
        properties.pluginCode = ""
        properties.status = message or "A Plugin Code is already stored."
        return
    end

    local credential = properties.pluginCode
    local stored, reason = Core.storeCurrent(credential, store, retrieve, function()
        properties.pluginCode = ""
    end)
    credential = nil
    if not stored then
        properties.status = reason == "invalid_syntax"
            and "Plugin Code format is invalid. Revoke it in FGA and create a new one."
            or "The Plugin Code could not be confirmed in the secure credential store."
        refreshStorageState(properties)
        return
    end
    refreshStorageState(properties)
    beginVerification(properties)
end

function Controller.verifyStored(properties)
    beginVerification(properties)
end

return Controller
