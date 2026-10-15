-- Isolated SDK capability probe, not a production outbox implementation.
-- Never run in a working photo catalog. No network, photos, credentials or logs.
local LrApplication = import "LrApplication"
local LrDialogs = import "LrDialogs"
local LrPathUtils = import "LrPathUtils"
local LrTasks = import "LrTasks"
local Probe = {}
local FIELD = "syntheticOutboxProbeV1"
local FIXTURE = '{"schemaVersion":1,"revision":1,"records":[{"id":"synthetic-1","phase":"batch_unconfirmed","groups":["synthetic-group"]}]}'

local function fixtureCatalog()
    local catalog = LrApplication.activeCatalog()
    if LrPathUtils.leafName(catalog:getPath()) ~= "FGA-Outbox-Probe.lrcat" then
        LrDialogs.message("Fixture catalog required",
            "Open a newly created empty catalog named FGA-Outbox-Probe.lrcat. No change was made.", "warning")
        return nil
    end
    return catalog
end

local function write(catalog, value, fail)
    return catalog:withPrivateWriteAccessDo(function()
        catalog:setPropertyForPlugin(_PLUGIN, FIELD, value)
        if fail then error("synthetic_rollback_probe") end
    end, { timeout = 5, asynchronous = false })
end

function Probe.write()
    LrTasks.startAsyncTask(function()
        local catalog = fixtureCatalog()
        if not catalog then return end
        local previous = catalog:getPropertyForPlugin(_PLUGIN, FIELD)
        if previous ~= nil and previous ~= FIXTURE then
            LrDialogs.message("Fixture state unavailable",
                "Unexpected existing probe state. Nothing was overwritten.", "warning")
            return
        end
        local ok, result = LrTasks.pcall(write, catalog, FIXTURE, false)
        if not ok or result ~= "executed"
            or catalog:getPropertyForPlugin(_PLUGIN, FIELD) ~= FIXTURE then
            LrDialogs.message("Probe failed", "Private write or exact readback failed.", "warning")
            return
        end
        local failed = LrTasks.pcall(write, catalog, "synthetic-must-roll-back", true)
        if failed or catalog:getPropertyForPlugin(_PLUGIN, FIELD) ~= FIXTURE then
            LrDialogs.message("Probe failed", "Private callback rollback was not observed.", "warning")
            return
        end
        LrDialogs.message("Same-session fixture checks passed",
            "Private write executed, exact readback matched, and callback error rolled back. Close the host, reopen this fixture catalog, then use Verify after restart. Persistence across restart has not yet been checked.", "info")
    end)
end

function Probe.verify()
    LrTasks.startAsyncTask(function()
        local catalog = fixtureCatalog()
        if not catalog then return end
        if catalog:getPropertyForPlugin(_PLUGIN, FIELD) ~= FIXTURE then
            LrDialogs.message("Probe failed", "Expected fixture record is absent or different.", "warning")
            return
        end
        LrDialogs.message("Exact fixture record found",
            "Record this result with whether the host was actually restarted and how it stopped. This command cannot verify that a restart occurred. No power-loss guarantee is established.", "info")
    end)
end

return Probe
