-- Synthetic capability probe only. No photos, credentials, network or raw logs.
local LrApplication = import "LrApplication"
local LrDate = import "LrDate"
local LrDialogs = import "LrDialogs"
local LrFileUtils = import "LrFileUtils"
local LrPathUtils = import "LrPathUtils"
local LrTasks = import "LrTasks"
local Probe = {}
local FIELD = "syntheticOutboxProbeV2"
local ROOT = "C:\\Temp"
local busy = false
local PROBE_VERSION = "0.0.2.6"
local diagnostic
local function at(stage) diagnostic.stage = stage end
local function safeType(value)
    local kind = type(value)
    if kind == "nil" or kind == "boolean" or kind == "number" or kind == "string"
        or kind == "table" or kind == "function" or kind == "userdata" or kind == "thread" then
        return kind
    end
    return "other"
end
local function resultSummary(value)
    return safeType(value) .. "/" .. (value and "truthy" or "falsey")
end
local function diagnosticText(stage, category)
    return "Stage: " .. stage .. "; error type: " .. category
        .. "; file write: " .. diagnostic.write .. "; file close: " .. diagnostic.close
        .. "; file move: " .. diagnostic.move .. "; source is file: " .. diagnostic.source
        .. "; destination exists: " .. diagnostic.destination
        .. "; move reason type: " .. diagnostic.moveReasonType
        .. "; move category: " .. diagnostic.moveCategory .. ". No raw error was recorded."
end
local PREFIX = '{"schemaVersion":1,"runId":"'
local SUFFIX = '","revision":1,"records":[{"id":"synthetic-1","phase":"batch_unconfirmed","groups":["synthetic-group"]}]}'

local function fixture(runId) return PREFIX .. runId .. SUFFIX end
local function recordRun(value)
    if type(value) ~= "string" or #value > 512 then return nil end
    local runId = string.match(value, '^%{"schemaVersion":1,"runId":"(probe%-%d+%-%d+)"')
    if runId and #runId <= 64 and value == fixture(runId) then return runId end
    return nil
end
local function receiptPath(runId, stage, temporary)
    return LrPathUtils.child(ROOT, "FGA-Outbox-Probe-" .. runId .. "-" .. stage
        .. ".json" .. (temporary and ".tmp" or ""))
end
local function integer(value, minimum, maximum)
    return type(value) == "number" and value == math.floor(value)
        and value >= minimum and value <= maximum
end
local function hostContext()
    local version = LrApplication.versionTable()
    if type(version) ~= "table" or not integer(version.major, 1, 999)
        or not integer(version.minor, 0, 999) or not integer(version.revision, 0, 999)
        or type(version.build_version) ~= "string" or #version.build_version > 64
        or not string.match(version.build_version, "^[A-Za-z0-9][A-Za-z0-9._%-]*$") then
        return '{"contextValid":false}'
    end
    return '{"contextValid":true,"major":' .. version.major .. ',"minor":' .. version.minor
        .. ',"revision":' .. version.revision .. ',"buildVersion":"' .. version.build_version .. '"}'
end
local function writeTime()
    local year, month, day, hour, minute, second = LrDate.timestampToComponents(LrDate.currentTime(), 0)
    if type(second) == "number" and second == second and second >= 0 and second < 60 then
        second = math.floor(second)
    end
    if not integer(year, 2001, 9999) or not integer(month, 1, 12) or not integer(day, 1, 31)
        or not integer(hour, 0, 23) or not integer(minute, 0, 59) or not integer(second, 0, 59) then
        return "null"
    end
    return '"' .. string.format("%04d-%02d-%02dT%02d:%02d:%02dZ", year, month, day, hour, minute, second) .. '"'
end
local function allocateRun()
    at("allocate_clock")
    local now = LrDate.currentTime()
    if type(now) ~= "number" or now ~= now or now < 0 or now > 1000000000000 then
        error("probe_clock_unavailable")
    end
    local base = "probe-" .. string.format("%.0f", now * 1000000)
    for index = 1, 32 do
        at("allocate_identity")
        local id = base .. "-" .. index
        if not LrFileUtils.exists(receiptPath(id, "rollback"))
            and not LrFileUtils.exists(receiptPath(id, "same_session"))
            and not LrFileUtils.exists(receiptPath(id, "failure"))
            and not LrFileUtils.exists(receiptPath(id, "preflight"))
            and not LrFileUtils.exists(receiptPath(id, "restart"))
            and not LrFileUtils.exists(receiptPath(id, "rollback", true))
            and not LrFileUtils.exists(receiptPath(id, "restart", true))
            and not LrFileUtils.exists(receiptPath(id, "same_session", true))
            and not LrFileUtils.exists(receiptPath(id, "failure", true))
            and not LrFileUtils.exists(receiptPath(id, "preflight", true)) then return id end
    end
    error("probe_identity_unavailable")
end
local function receipt(runId, stage, outcome, reason)
    -- All inputs below originate in this closed probe, never catalog/error text.
    diagnostic.write, diagnostic.close, diagnostic.move = "not_called", "not_called", "not_called"
    diagnostic.source, diagnostic.destination = "not_checked", "not_checked"
    diagnostic.moveReasonType, diagnostic.moveCategory = "not_called", "not_called"
    local path = receiptPath(runId, stage)
    local temporary = receiptPath(runId, stage, true)
    local terminal = stage ~= "same_session" or outcome ~= "passed"
    at("receipt_context")
    local body = '{"schemaVersion":2,"probe":"catalog_outbox","probeVersion":"' .. PROBE_VERSION
        .. '","writeTime":' .. writeTime() .. ',"host":' .. hostContext() .. ',"runId":"' .. runId
        .. '","stage":"' .. stage .. '","outcome":"' .. outcome
        .. '","reasonCode":"' .. reason .. '","stageTerminal":true,"terminal":' .. tostring(terminal) .. ','
        .. '"restartIndependentlyVerified":false,"crashQualified":false,"powerLossQualified":false}\n'
    at("receipt_directory")
    LrFileUtils.createAllDirectories(ROOT)
    at("receipt_open")
    local file = io.open(temporary, "wb")
    if not file then error("probe_receipt_unavailable") end
    at("receipt_write")
    local written = file:write(body)
    diagnostic.write = resultSummary(written)
    at("receipt_close")
    local closed = file:close()
    diagnostic.close = resultSummary(closed)
    if not written then at("receipt_write_result") error("probe_receipt_unavailable") end
    if not closed then at("receipt_close_result") error("probe_receipt_unavailable") end
    at("receipt_source_check")
    local sourceIsFile = LrFileUtils.exists(temporary) == "file"
    diagnostic.source = tostring(sourceIsFile)
    if not sourceIsFile then error("probe_receipt_unavailable") end
    at("receipt_destination_check")
    local destinationExists = LrFileUtils.exists(path) ~= false
    diagnostic.destination = tostring(destinationExists)
    if destinationExists then error("probe_receipt_unavailable") end
    at("receipt_move")
    local moved, moveReason = LrFileUtils.move(temporary, path)
    diagnostic.move = resultSummary(moved)
    diagnostic.moveReasonType = safeType(moveReason)
    diagnostic.moveCategory = moved and "none" or "sdk_move_failed"
    if not moved then at("receipt_move_result") error("probe_receipt_unavailable") end
end
local function catalogOrRefuse(runId)
    at("active_catalog")
    local catalog = LrApplication.activeCatalog()
    at("catalog_guard")
    if LrPathUtils.leafName(catalog:getPath()) ~= "FGA-Outbox-Probe.lrcat" then
        receipt(runId, "failure", "refused", "fixture_catalog_required")
        return nil
    end
    return catalog
end
local function write(catalog, value, fail)
    at(fail and "rollback_gate" or "private_gate")
    return catalog:withPrivateWriteAccessDo(function()
        at(fail and "rollback_set_property" or "set_property")
        catalog:setPropertyForPlugin(_PLUGIN, FIELD, value)
        if fail then error("synthetic_rollback_probe") end
    end, { timeout = 5, asynchronous = false })
end
local function run(operation)
    if busy then
        LrDialogs.message("Probe busy", "Wait for the current fixture check to finish.", "warning")
        return
    end
    busy = true
    LrTasks.startAsyncTask(function()
        local runId
        diagnostic = {stage = "start", write = "not_called", close = "not_called", move = "not_called",
            source = "not_checked", destination = "not_checked", moveReasonType = "not_called", moveCategory = "not_called"}
        local ok, err = LrTasks.pcall(function()
            runId = allocateRun()
            operation(runId)
        end)
        if not ok then
            -- Never log the exception: SDK and file errors may contain private paths.
            local summary = diagnosticText(diagnostic.stage, safeType(err))
            if runId then LrTasks.pcall(receipt, runId, "failure", "failed", "probe_operation_failed") end
            LrDialogs.message("Probe unavailable", summary .. " Inspect only complete JSON receipts. Catalog write outcome may be unknown.", "warning")
        end
        busy = false
    end)
end
function Probe.preflight()
    run(function(runId)
        -- Deliberately no activeCatalog, property read, or catalog write gate.
        receipt(runId, "preflight", "passed", "receipt_path_available")
        LrDialogs.message("Receipt preflight passed", diagnosticText("preflight_complete", "none")
            .. " No catalog API was called. This does not qualify catalog persistence.", "info")
    end)
end
function Probe.write()
    run(function(runId)
        local catalog = catalogOrRefuse(runId)
        if not catalog then return end
        at("get_property")
        local previous = catalog:getPropertyForPlugin(_PLUGIN, FIELD)
        if previous ~= nil and not recordRun(previous) then
            receipt(runId, "failure", "refused", "unexpected_fixture_state")
            return
        end
        local value = fixture(runId)
        local ok, result = LrTasks.pcall(write, catalog, value, false)
        if not ok then error(result, 0) end
        at("write_readback")
        if result ~= "executed" or catalog:getPropertyForPlugin(_PLUGIN, FIELD) ~= value then
            receipt(runId, "same_session", "failed", "write_or_readback_unconfirmed")
            return
        end
        receipt(runId, "same_session", "passed", "exact_readback_matched")
        local succeeded = LrTasks.pcall(write, catalog, "synthetic-must-roll-back", true)
        at("rollback_readback")
        if succeeded or catalog:getPropertyForPlugin(_PLUGIN, FIELD) ~= value then
            receipt(runId, "rollback", "failed", "callback_rollback_not_observed")
            return
        end
        receipt(runId, "rollback", "passed", "callback_rollback_observed")
        LrDialogs.message("Same-session fixture checks passed",
            "Matching run receipts are in C:/Temp. Close and reopen the fixture host before Verify after restart. This does not qualify crash or power-loss persistence.", "info")
    end)
end
function Probe.verify()
    run(function(failureId)
        local catalog = catalogOrRefuse(failureId)
        if not catalog then return end
        at("get_property")
        local value = catalog:getPropertyForPlugin(_PLUGIN, FIELD)
        local runId = recordRun(value)
        if not runId then
            receipt(failureId, "failure", "failed", "expected_run_record_unavailable")
            return
        end
        -- Refuse a second verification for this run rather than overwrite evidence.
        if LrFileUtils.exists(receiptPath(runId, "restart")) then
            receipt(failureId, "failure", "refused", "run_already_verified")
            return
        end
        if LrFileUtils.exists(receiptPath(runId, "restart", true)) then
            receipt(failureId, "failure", "refused", "verification_receipt_incomplete")
            return
        end
        receipt(runId, "restart", "matched", "exact_run_record_found")
        LrDialogs.message("Exact fixture run found",
            "A matching-run receipt is in C:/Temp. Independently record whether a host restart actually occurred. This command cannot prove restart, crash or power-loss persistence.", "info")
    end)
end
return Probe
