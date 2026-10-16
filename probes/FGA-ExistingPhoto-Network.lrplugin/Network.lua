-- Development-only SDK 15.3 network characterization runtime 0.0.1.2.
-- No release credential, catalog, provider API, or mutable global environment.
local N={VERSION="0.0.1.2", PLAN_VERSION="fga-native-network-v1", TIMEOUT=15}
local active=false
local EPOCH=978307200 -- LrDate.currentTime is seconds since 2001-01-01 UTC.
local function integer(value, minimum, maximum)
    return type(value) == "number" and value >= minimum and value <= maximum
        and value == math.floor(value)
end
local function exact(value, fields)
    if type(value) ~= "table" then return false end
    local count=0
    for key in pairs(value) do if not fields[key] then return false end; count=count+1 end
    local expected=0
    for _ in pairs(fields) do expected=expected+1 end
    return count == expected
end
local function hex(value, length)
    return type(value) == "string" and #value == length and value:match("^[a-f0-9]+$") ~= nil
end
local configKeys={schemaVersion=true, planVersion=true, runId=true, workersDevSubdomain=true,
    accessToken=true, canaryToken=true, expiresAtUnix=true}
function N.validateConfig(value, nowUnix)
    if not exact(value, configKeys) or value.schemaVersion ~= 1 or value.planVersion ~= N.PLAN_VERSION
        or not hex(value.runId, 24) or not hex(value.accessToken, 64)
        or type(value.canaryToken) ~= "string" or value.canaryToken:sub(1, 10) ~= "SYNTHETIC-"
        or not hex(value.canaryToken:sub(11), 32)
        or type(value.workersDevSubdomain) ~= "string" or #value.workersDevSubdomain > 63
        or not (value.workersDevSubdomain:match("^[a-z0-9]$")
            or value.workersDevSubdomain:match("^[a-z0-9][a-z0-9%-]*[a-z0-9]$"))
        or not integer(nowUnix, 1, 100000000000)
        or not integer(value.expiresAtUnix, nowUnix+1, nowUnix+1200) then
        return nil, "target_invalid"
    end
    local suffix="." .. value.workersDevSubdomain .. ".workers.dev"
    return {runId=value.runId, accessToken=value.accessToken, canaryToken=value.canaryToken,
        expiresAtUnix=value.expiresAtUnix,
        source="https://fga-native-network-src-" .. value.runId .. suffix,
        receiver="https://fga-native-network-recv-" .. value.runId .. suffix}
end
local function now(sdk)
    local value=sdk.LrDate.currentTime()
    if type(value) ~= "number" then return nil end
    value=value+EPOCH
    if type(value) ~= "number" or value ~= value or value < 1 or value > 100000000000 then return nil end
    return value
end
local function headersValue(headers, wanted)
    if type(headers) ~= "table" then return nil end
    local value
    for _, row in ipairs(headers) do
        if type(row) ~= "table" or type(row.field) ~= "string" or type(row.value) ~= "string" then return nil end
        if row.field:lower() == wanted then
            if value ~= nil then return nil end
            value=row.value
        end
    end
    return value
end
local errorCodes={cancelled=true, badURL=true, timedOut=true, cannotFindHost=true,
    cannotConnectToHost=true, resourceUnavailable=true, networkConnectionLost=true,
    redirectError=true, badServerResponse=true, authenticationError=true, securityError=true,
    serverCertificateHasBadDate=true, serverCertificateHasUnknownRoot=true}
local function observed(sdk, before, body, headers)
    local elapsed, after=nil, now(sdk)
    if before and after and after >= before then elapsed=math.floor((after-before)*1000+0.5) end
    local code=type(headers) == "table" and type(headers.error) == "table" and headers.error.errorCode or nil
    local errorCategory=code and (errorCodes[code] and code or "other_network_error") or "none"
    local partial=type(headers) == "table" and headers.partial_data or nil
    local contentType=headersValue(headers, "content-type")
    local media=contentType == "image/png" and "png" or contentType == "image/jpeg" and "jpeg"
        or contentType == "application/json" and "json" or contentType == "text/plain" and "text" or "other"
    local status=type(headers) == "table" and headers.status or nil
    local cache=headersValue(headers, "cache-control")
    return {status=integer(status,100,599) and status or 0, returnedBody=type(body) == "string",
        bodyBytes=type(body) == "string" and #body or 0,
        partialBytes=type(partial) == "string" and #partial or 0,
        errorCategory=errorCategory, timingValid=elapsed ~= nil, elapsedMs=elapsed,
        media=media, noStore=cache and ("," .. cache:lower():gsub("%s", "") .. ","):find(",no%-store,") ~= nil or false,
        locationPresent=headersValue(headers, "location") ~= nil,
        headersObserved=type(headers) == "table"}
end
local function decode(json, bytes, maximum)
    if type(bytes) ~= "string" or #bytes > maximum then return nil end
    local ok, value, position, reason=pcall(json.decode, bytes, 1, json.null)
    if not ok or reason or type(position) ~= "number" or not bytes:sub(position):match("^%s*$") then return nil end
    return value
end
function N.locations(paths, pluginPath)
    local root=paths.child("C:\\Temp", "FGA-existing-photo-network")
    local repository=paths.parent(paths.parent(pluginPath))
    local release=paths.child(paths.child(paths.child(repository,"clients"),"lightroom"),"FGA-LrC15.lrplugin")
    return {root=root, target=paths.child(root,"target.json"), status=paths.child(root,"status.json"),
        temporary=paths.child(root,"status.json.tmp"), json=paths.child(release,"dkjson.lua")}
end
function N.publish(files, json, locations, state)
    local file=assert(io.open(locations.temporary,"wb"),"network_receipt_unavailable")
    assert(file:write(json.encode(state)),"network_receipt_unavailable")
    assert(file:close(),"network_receipt_unavailable")
    assert(files.exists(locations.temporary) == "file","network_receipt_unavailable")
    if files.exists(locations.status) then assert(files.delete(locations.status),"network_receipt_unavailable") end
    assert(not files.exists(locations.status),"network_receipt_unavailable")
    assert(files.move(locations.temporary,locations.status),"network_receipt_unavailable")
    assert(files.exists(locations.status) == "file" and not files.exists(locations.temporary),"network_receipt_unavailable")
end

N.CASES={
    {id="png", status=200, media="png", bytes=68},
    {id="jpeg", status=200, media="jpeg", bytes=634},
    {id="boundary-image", status=200, media="png", bytes=262144},
    {id="oversize-image", status=200, media="png", bytes=262145},
    {id="oversize-error", status=503, media="text", bytes=262145},
    {id="slow-response", status=200, media="png", bytes=68},
    {id="redirect-same", redirect=true},
    {id="redirect-cross", redirect=true},
}
local MARKER="fga-native-network-v1"
-- This closed wire format contains only known ASCII field names, booleans
-- and canonical nonnegative integers. Do not use permissive dkjson grammar for
-- receiver attribution: comments, duplicate names and trailing commas fail.
local function primitiveObject(bytes, keys)
    if type(bytes) ~= "string" or #bytes > 4096 then return nil end
    local position, result, seen=1, {}, {}
    local function whitespace()
        while bytes:sub(position,position):match("[ \t\r\n]") do position=position+1 end
    end
    whitespace()
    if bytes:sub(position,position) ~= "{" then return nil end
    position=position+1
    while true do
        whitespace()
        local key=bytes:sub(position):match('^"([A-Za-z][A-Za-z0-9]*)"')
        if not key or not keys[key] or seen[key] then return nil end
        seen[key]=true
        position=position+#key+2
        whitespace()
        if bytes:sub(position,position) ~= ":" then return nil end
        position=position+1
        whitespace()
        local rest=bytes:sub(position)
        local value, length
        if rest:sub(1,4) == "true" then value,length=true,4
        elseif rest:sub(1,5) == "false" then value,length=false,5
        else
            local digits=rest:match("^0") or rest:match("^[1-9][0-9]*")
            if not digits or #digits > 16 then return nil end
            value,length=tonumber(digits),#digits
            if not integer(value,0,9007199254740991) then return nil end
        end
        result[key]=value
        position=position+length
        whitespace()
        local separator=bytes:sub(position,position)
        position=position+1
        if separator == "}" then
            whitespace()
            if position ~= #bytes+1 then return nil end
            return result
        end
        if separator ~= "," then return nil end
    end
end
local receiverKeys={schemaVersion=true,receiverReached=true,authorizationPresent=true,canaryMatched=true}
local reportKeys={schemaVersion=true, receiverRequests=true, authorizationObserved=true, canaryObserved=true}
local function report(sdk, json, target, state)
    if not now(sdk) or now(sdk) >= target.expiresAtUnix then return nil,"target_expired" end
    state.getCalls=state.getCalls+1
    local before=now(sdk)
    -- Never send Authorization to the receiver report; its observations must
    -- originate solely in the controlled redirect, not in our reporting read.
    local body, headers=sdk.LrHttp.get(target.receiver .. "/v1/report",
        {{field="X-FGA-Network-Access",value=target.accessToken}},N.TIMEOUT)
    local observation=observed(sdk,before,body,headers)
    local value=primitiveObject(body,reportKeys)
    local valid=observation.status == 200 and observation.bodyBytes <= 4096
        and headersValue(headers,"x-fga-network-probe") == MARKER
        and observation.noStore and exact(value,reportKeys) and value.schemaVersion == 1
        and integer(value.receiverRequests,0,32) and type(value.authorizationObserved) == "boolean"
        and type(value.canaryObserved) == "boolean"
        and (not value.canaryObserved or value.authorizationObserved)
        and (value.receiverRequests > 0 or (not value.authorizationObserved and not value.canaryObserved))
    observation.validReport=valid
    state.receiverReports[#state.receiverReports+1]=observation
    body, headers=nil,nil
    state.responseReferencesCleared=true
    if not valid then return nil,"receiver_report_invalid" end
    return {receiverRequests=value.receiverRequests,authorizationObserved=value.authorizationObserved,
        canaryObserved=value.canaryObserved}
end
function N.execute(sdk,json,rawTarget,state,progress)
    state=state or {}
    state.getCalls=0
    state.cases=setmetatable({}, {__jsontype="array"})
    state.receiverReports=setmetatable({}, {__jsontype="array"})
    state.responseFilesCreated=0
    state.remoteCleanupConfirmed=false
    state.responseReferencesCleared=true
    state.outcome="running"
    local current=now(sdk)
    local target, reason=N.validateConfig(rawTarget,current and math.floor(current) or nil)
    if not target then state.outcome="failed"; state.reasonCode=reason; return state end
    state.planId=target.runId
    state.stage="baseline_report"
    local baseline, baselineReason=report(sdk,json,target,state)
    if not baseline or baseline.receiverRequests ~= 0 or baseline.authorizationObserved or baseline.canaryObserved then
        state.outcome="failed"; state.reasonCode=baselineReason or "target_not_fresh"; return state
    end
    local crossObservation
    for _, case in ipairs(N.CASES) do
        if not now(sdk) or now(sdk) >= target.expiresAtUnix then
            state.outcome="failed"; state.reasonCode="target_expired"; return state
        end
        state.stage="case_request"
        state.currentCase=case.id
        state.responseReferencesCleared=false
        state.getCalls=state.getCalls+1
        local before=now(sdk)
        local body, headers=sdk.LrHttp.get(target.source .. "/v1/cases/" .. case.id, {
            {field="X-FGA-Network-Access",value=target.accessToken},
            {field="Authorization",value="Bearer " .. target.canaryToken},
        },N.TIMEOUT)
        local observation=observed(sdk,before,body,headers)
        observation.caseId=case.id
        observation.markerMatches=headersValue(headers,"x-fga-network-probe") == MARKER
        observation.returnedOverImageLimit=observation.bodyBytes > 262144
        observation.withinFinitePlan=observation.bodyBytes <= 262145 and observation.partialBytes <= 262145
        if case.redirect then
            -- Following or refusing the controlled redirect are both measured
            -- outcomes. Neither demonstrates safety of real credential forwarding.
            observation.expectedResponse=observation.markerMatches
                and (observation.status == 200 or observation.status == 302 or observation.status == 404)
                and observation.withinFinitePlan and observation.noStore
            if case.id == "redirect-same" then
                observation.sameOriginCanaryAccepted=observation.status == 200 and observation.media == "png"
                    and observation.bodyBytes == 68 and observation.markerMatches
            end
            if case.id == "redirect-cross" then
                crossObservation=observation
                observation.redirectResponseCategory="other"
                if observation.expectedResponse and observation.status == 302 then
                    observation.redirectResponseCategory="original_redirect"
                elseif observation.expectedResponse and observation.status == 200 and observation.media == "json" then
                    local receiver=primitiveObject(body,receiverKeys)
                    local valid=exact(receiver,receiverKeys) and receiver.schemaVersion == 1
                        and receiver.receiverReached == true
                        and type(receiver.authorizationPresent) == "boolean"
                        and type(receiver.canaryMatched) == "boolean"
                        and (not receiver.canaryMatched or receiver.authorizationPresent)
                    observation.receiverPayloadValid=valid
                    if valid then
                        observation.redirectResponseCategory="receiver_response"
                        observation.receiverAuthorizationPresent=receiver.authorizationPresent
                        observation.receiverCanaryMatched=receiver.canaryMatched
                    end
                end
                observation.expectedResponse=observation.redirectResponseCategory ~= "other"
            end
        else
            observation.expectedResponse=observation.markerMatches and observation.status == case.status
                and observation.media == case.media and observation.noStore
                and (case.bytes and observation.bodyBytes == case.bytes
                    or case.maximum and observation.bodyBytes > 0 and observation.bodyBytes <= case.maximum) or false
            if case.id == "slow-response" and not observation.returnedBody and observation.errorCategory == "timedOut" then
                observation.expectedResponse=true
            end
        end
        observation.expectedResponse=observation.expectedResponse and observation.withinFinitePlan
        body, headers=nil,nil
        state.responseReferencesCleared=true
        state.cases[#state.cases+1]=observation
        if progress then progress(state) end
    end
    state.stage="final_report"
    local final, finalReason=report(sdk,json,target,state)
    if not final then state.outcome="failed"; state.reasonCode=finalReason; return state end
    state.canary=final
    state.receiverCountExpected=final.receiverRequests <= 1
    local correlated=false
    if crossObservation and crossObservation.redirectResponseCategory == "original_redirect" then
        correlated=final.receiverRequests == 0 and not final.authorizationObserved and not final.canaryObserved
    elseif crossObservation and crossObservation.redirectResponseCategory == "receiver_response" then
        correlated=final.receiverRequests == 1
            and final.authorizationObserved == crossObservation.receiverAuthorizationPresent
            and final.canaryObserved == crossObservation.receiverCanaryMatched
    end
    state.canary.observationConclusive=correlated
    if correlated then
        state.canary.redirectFollowObserved=crossObservation.redirectResponseCategory == "receiver_response"
    end
    state.allExpectedResponses=correlated
    for _, observation in ipairs(state.cases) do
        state.allExpectedResponses=state.allExpectedResponses and observation.expectedResponse
    end
    target=nil
    state.stage="complete"
    state.currentCase=nil
    state.outcome=state.allExpectedResponses and "characterized" or "incomplete"
    state.reasonCode=state.allExpectedResponses and "finite_observations_complete" or "unexpected_observation"
    return state
end
local function hostContext(sdk)
    local value=sdk.LrApplication.versionTable()
    local result={}
    for _, key in ipairs({"major","minor","revision"}) do
        assert(integer(value[key],0,999),"network_host_unavailable")
        result[key]=value[key]
    end
    assert(type(value.build_version) == "string" and #value.build_version <= 64
        and value.build_version:match("^[A-Za-z0-9][A-Za-z0-9._%-]*$"),"network_host_unavailable")
    result.buildVersion=value.build_version
    return result
end
function N.run()
    if active then return end
    local sdk={}
    for _, name in ipairs({"LrApplication","LrDate","LrDialogs","LrFileUtils",
        "LrFunctionContext","LrHttp","LrPathUtils","LrTasks"}) do sdk[name]=import(name) end
    active=true
    sdk.LrTasks.startAsyncTask(function()
        sdk.LrFunctionContext.callWithContext("native-network-characterization",function(context)
            context:addCleanupHandler(function() active=false end)
            local locations=N.locations(sdk.LrPathUtils,_PLUGIN.path)
            assert(sdk.LrFileUtils.createAllDirectories(locations.root),"network_directory_unavailable")
            local json=assert(loadfile(locations.json))()
            local started=assert(now(sdk),"network_clock_unavailable")
            local state={schemaVersion=1,probe="existing_photo_native_network",probeVersion=N.VERSION,
                planVersion=N.PLAN_VERSION,attemptId="native-" .. string.format("%.0f",started*1000000),
                host=hostContext(sdk),stage="read_target",outcome="running",terminal=false,
                nativeTransportQualified=false,productionQualified=false,
                allocationBoundProven=false,totalDeadlineProven=false,remoteCleanupConfirmed=false}
            local function publish() N.publish(sdk.LrFileUtils,json,locations,state) end
            publish()
            local ok=sdk.LrTasks.pcall(function()
                local file=assert(io.open(locations.target,"rb"),"network_target_unavailable")
                local bytes=file:read(8193)
                local closed=file:close()
                assert(closed,"network_target_unavailable")
                local rawTarget=decode(json,bytes,8192)
                bytes=nil
                state.stage="validate_target"
                N.execute(sdk,json,rawTarget,state,function() publish() end)
                rawTarget=nil
            end)
            if not ok then state.outcome="failed"; state.reasonCode="network_runtime_error" end
            state.terminal=true
            publish()
            sdk.LrDialogs.message("Native network " .. state.outcome,
                "Sanitized status updated. This disposable experiment does not qualify production transport.","info")
        end)
    end)
end
return N
