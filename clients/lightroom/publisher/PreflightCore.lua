-- Original FGA policy. No SDK, filesystem, catalog, or network capability.
local PreflightCore = {}

local function positiveInteger(value)
    return type(value) == "number" and value > 0
        and value <= 9007199254740991 and value == math.floor(value)
end

function PreflightCore.result(code, maximumBytes, sizeBytes)
    local result = { ok = code == "ready", code = code }
    if positiveInteger(maximumBytes) then
        result.maximumBytes = maximumBytes
    end
    if type(sizeBytes) == "number" and sizeBytes >= 0 then
        result.sizeBytes = sizeBytes
    end
    if code == "oversized" then
        result.message = string.format(
            "Rendered photo is %.0f bytes; configured limit is %.0f bytes. Nothing was uploaded.",
            sizeBytes, maximumBytes
        )
    end
    return result
end

function PreflightCore.checkSize(maximumBytes, sizeBytes)
    if not positiveInteger(maximumBytes) then
        return PreflightCore.result("invalid_limit")
    end
    if sizeBytes == 0 then
        return PreflightCore.result("empty_file", maximumBytes, 0)
    end
    if not positiveInteger(sizeBytes) then
        return PreflightCore.result("invalid_size", maximumBytes)
    end
    if sizeBytes > maximumBytes then
        return PreflightCore.result("oversized", maximumBytes, sizeBytes)
    end
    return PreflightCore.result("ready", maximumBytes, sizeBytes)
end

return PreflightCore
