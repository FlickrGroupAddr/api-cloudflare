-- Copyright 2026 Terry Ott. MIT License.
-- In-memory synthetic byte sink only. No HTTP, credential, upload, proof or
-- publication claim; actual 0095 transitions belong to the separate harness.
local M={}
function M.new()
    local closed,reads,total=false,0,0
    local T={kind='synthetic'}
    function T:consume(lease)
        if self~=T or closed then return false end
        local bytes=lease:read()
        if type(bytes)~='string' then return false end
        reads=reads+1;total=total+#bytes
        return true
    end
    function T:receipt()
        return {kind='synthetic',reads=reads,sizeBytes=total,
            networkCalls=0,uploadAcknowledged=false}
    end
    function T:close() closed=true;return true end
    return T
end
return M
