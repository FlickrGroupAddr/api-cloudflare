-- Synthetic qualification runtime 0.0.1.5. No network or catalog API is imported.
local Q = {VERSION="0.0.1.5"}
Q.SCENARIOS = {"success", "navigation_cancel", "empty", "cancel_during_thumbnail",
    "discovery_error", "malformed_page", "thumbnail_error", "stale_proof",
    "membership_error", "cleanup_failure"}
local active=false
local WHEN = "2026-10-16T12:00:00Z"
local function array(values) return setmetatable(values or {}, {__jsontype="array"}) end
local function load(path) return assert(loadfile(path))() end
local function allowed(scenario)
    for _, value in ipairs(Q.SCENARIOS) do if value == scenario then return true end end
    return false
end
-- Narrow SDK adapters isolate the real browser's temporary cache. All ordinary
-- filesystem and UI operations delegate to the supplied real SDK objects.
-- Offline tests supply stand-ins; native use supplies only documented imports.
function Q.execute(scenario, sdk, release, fixtureRoot, png, diagnosticState)
    assert(allowed(scenario), "fixture_scenario_invalid")
    local initial = {scenario=scenario, requests=0, discoveries=0, thumbnails=0,
        proofs=0, memberships=0, pagesPresented=0, membershipDialogs=0,
        completePages=true, cacheClean=false, cleanupFailureInjected=false,
        availableStates=0, emptyStates=0, cancelledStates=0}
    local state=diagnosticState or {}
    for key, value in pairs(initial) do state[key]=value end
    state.standardFunctions={loadfile=type(loadfile) == "function",
        setfenv=type(setfenv) == "function", setmetatable=type(setmetatable) == "function",
        globalTable=type(_G) == "table"}
    state.phase="load_json"
    local cancel, pageThumbnails, pageRows = false, 0, 0
    local proofPhotoId
    local json = load(sdk.LrPathUtils.child(release, "dkjson.lua"))
    state.phase="load_client"
    local client = load(sdk.LrPathUtils.child(release, "ExistingPhotoClient.lua"))
    local function photo(index)
        return {flickrPhotoId=index == 5 and ("synthetic-" .. string.rep("x", 118)) or ("synthetic-photo-" .. index),
            title=index == 1 and "" or ("Synthetic title " .. index .. string.rep(" long", 30)),
            dateUploaded="1700000000", dateTaken="2026-10-16 10:30:00",
            thumbnail={url="https://live.staticflickr.com/1/synthetic_q.png", sizeClass="q"}}
    end
    local function respond(value, status) return json.encode(value), {status=status or 200} end
    local deps = {thumbnailTransportQualified=true, jsonNull=json.null,
        cancelled=function() return cancel end,
        decode=function(bytes)
            local value, position, reason = json.decode(bytes, 1, json.null)
            if reason or not bytes:sub(position):match("^%s*$") then return nil end
            return value
        end,
        logState=function(value)
            if value == "available" then state.availableStates=state.availableStates+1
            elseif value == "empty" then state.emptyStates=state.emptyStates+1
            elseif value == "cancelled" then state.cancelledStates=state.cancelledStates+1 end
        end}
    deps.request = function(method, path, body)
        state.requests=state.requests+1
        if method == "GET" and path:match("^/api/v001/existing%-public%-photos%?") then
            state.discoveries=state.discoveries+1
            pageThumbnails=0
            if scenario == "discovery_error" then
                return respond({error={code="existing_photo_discovery_unavailable"}}, 503)
            end
            local page = tonumber(path:match("page=(%d+)"))
            local values = array()
            if scenario ~= "empty" then
                for index=1,(page == 1 and 5 or 1) do
                    -- Page 2 intentionally repeats a page-1 identity.
                    values[#values+1]=photo(index)
                end
            end
            pageRows=#values
            local result = {schemaVersion=1, linkedFlickrRevision=7, observedAt=WHEN,
                page=page, pageSize=5, pages=scenario == "empty" and 0 or 2,
                total=scenario == "empty" and 0 or 6, photos=values}
            if scenario == "malformed_page" then result.photos[2]=result.photos[1] end
            return respond(result)
        elseif method == "GET" and path:find("/thumbnail?", 1, true) then
            state.thumbnails=state.thumbnails+1
            pageThumbnails=pageThumbnails+1
            -- Yield in the SDK task, never inside ordinary Lua 5.1 pcall.
            sdk.LrTasks.yield()
            if scenario == "cancel_during_thumbnail" then cancel=true end
            if scenario == "thumbnail_error" and pageThumbnails == 2 then
                return "synthetic-invalid-image", {status=200,
                    {field="Content-Type", value="image/png"},
                    {field="Cache-Control", value="private, no-store"}}
            end
            return png, {status=200, {field="Content-Type", value="image/png"},
                {field="Cache-Control", value="private, no-store"},
                {field="Content-Length", value=tostring(#png)}}
        elseif method == "POST" and path == "/api/v001/existing-public-photo-bindings" then
            state.proofs=state.proofs+1
            assert(body.expectedLinkedFlickrRevision == 7, "fixture_revision_invalid")
            if scenario == "stale_proof" then return respond({error={code="flickr_link_changed"}}, 409) end
            proofPhotoId=body.flickrPhotoId
            return respond({schemaVersion=1, fgaPhotoBindingId="synthetic-binding",
                sourceKind="existing_public_flickr_photo", flickrPhotoId=body.flickrPhotoId,
                linkedFlickrRevision=7, verificationRevision=3, verifiedAt=WHEN}, 201)
        elseif method == "GET" and path:match("^/api/v001/photo%-bindings/") then
            state.memberships=state.memberships+1
            if scenario == "membership_error" then
                return respond({error={code="membership_observation_unavailable"}}, 503)
            end
            return respond({schemaVersion=1, fgaPhotoBindingId="synthetic-binding",
                flickrPhotoId=proofPhotoId, observationRevision=4, observedAt=WHEN,
                groups=array({{flickrGroupId="synthetic-group", displayName="Synthetic group"}}),
                nextAfterGroupId=json.null})
        end
        error("fixture_unexpected_request")
    end
    state.phase="build_adapters"
    local paths = setmetatable({}, {__index=sdk.LrPathUtils})
    paths.getStandardFilePath=function(kind)
        assert(kind == "temp", "fixture_path_invalid")
        return fixtureRoot
    end
    local files = setmetatable({}, {__index=sdk.LrFileUtils})
    local ownedRuns={}
    files.chooseUniqueFileName=function(path)
        local chosen=sdk.LrFileUtils.chooseUniqueFileName(path)
        ownedRuns[#ownedRuns+1]=chosen
        return chosen
    end
    files.delete=function(path)
        if scenario == "cleanup_failure" and path:match("[/\\]page$") then
            state.cleanupFailureInjected=true
            return false
        end
        return sdk.LrFileUtils.delete(path)
    end
    local dialogs=setmetatable({}, {__index=sdk.LrDialogs})
    dialogs.presentModalDialog=function(args)
        if args.title == "Currently in Flickr groups" then
            state.membershipDialogs=state.membershipDialogs+1
        else
            state.pagesPresented=state.pagesPresented+1
            state.completePages=state.completePages and pageThumbnails == pageRows
        end
        return sdk.LrDialogs.presentModalDialog(args)
    end
    state.phase="load_browser"
    local browserModule=load(sdk.LrPathUtils.child(release, "ExistingPhotoBrowser.lua"))
    local browser=browserModule.new({
        LrBinding=sdk.LrBinding, LrDate=sdk.LrDate, LrDialogs=dialogs,
        LrFileUtils=files, LrLogger=sdk.LrLogger, LrPathUtils=paths,
        LrTasks=sdk.LrTasks, LrView=sdk.LrView,
    }, client)
    local result, reason
    state.phase="browser_run"
    local ok, runError=sdk.LrTasks.pcall(function()
        sdk.LrFunctionContext.callWithContext("existing-photo-synthetic", function(context)
            result, reason=browser.run(context, deps)
        end)
    end)
    if not ok then state.failurePhase="browser_run"; state.errorType=type(runError) end
    runError=nil
    state.phase="cache_cleanup"
    state.cacheClean=true
    for _, path in ipairs(ownedRuns) do
        if sdk.LrFileUtils.exists(path) then state.cacheClean=false end
    end
    state.reasonCode=not ok and "fixture_runtime_error" or
        (result and "observation_complete" or reason or "fixture_no_result")
    -- Only closed reason values may leave the fixture. Never serialize SDK errors.
    local safe={observation_complete=true, cancelled=true, response_invalid=true,
        thumbnail_unavailable=true, flickr_link_changed=true,
        existing_photo_discovery_unavailable=true, membership_observation_unavailable=true,
        fixture_runtime_error=true, fixture_no_result=true}
    if not safe[state.reasonCode] then state.reasonCode="fixture_unexpected_result" end
    local expected={success="observation_complete", navigation_cancel="cancelled", empty="cancelled",
        cancel_during_thumbnail="cancelled", discovery_error="existing_photo_discovery_unavailable",
        malformed_page="response_invalid", thumbnail_error="thumbnail_unavailable",
        stale_proof="flickr_link_changed", membership_error="membership_observation_unavailable",
        cleanup_failure="thumbnail_unavailable"}
    local valid=ok and state.reasonCode == expected[scenario] and state.completePages and state.cacheClean
    if scenario == "success" then
        valid=valid and state.proofs == 1 and state.memberships == 1 and state.membershipDialogs == 1
    elseif scenario == "navigation_cancel" then
        valid=valid and state.pagesPresented >= 3 and state.proofs == 0
    elseif scenario == "stale_proof" then valid=valid and state.proofs == 1 and state.memberships == 0
    elseif scenario == "membership_error" then valid=valid and state.proofs == 1 and state.membershipDialogs == 0
    elseif scenario == "cleanup_failure" then valid=valid and state.cleanupFailureInjected and state.proofs == 0
    elseif scenario == "empty" then valid=valid and state.emptyStates == 1 and state.thumbnails == 0
    else valid=valid and state.pagesPresented == 0 and state.proofs == 0 end
    state.outcome=valid and "passed" or "failed"
    return state
end
-- Keep only closed phase labels, primitive counters and type information when
-- initialization fails before the browser's own protected run boundary.
function Q.executeSafely(scenario, sdk, release, fixtureRoot, png)
    local state={scenario=scenario, phase="load_json", cacheClean=false}
    local ok, result=sdk.LrTasks.pcall(Q.execute, scenario, sdk, release, fixtureRoot, png, state)
    if ok then return result end
    state.failurePhase=state.phase
    state.errorType=type(result)
    result=nil
    state.outcome="failed"
    state.reasonCode="fixture_runtime_error"
    state.cacheClean=false
    return state
end
-- All native paths use documented host-aware SDK joins; Lua file I/O may
-- accept slash paths that an SDK filesystem operation rejects on Windows.
function Q.locations(sdk, pluginPath)
    local child=sdk.LrPathUtils.child
    local root=child("C:\\Temp", "FGA-existing-photo-qualification")
    local repository=sdk.LrPathUtils.parent(sdk.LrPathUtils.parent(pluginPath))
    local release=child(child(child(repository, "clients"), "lightroom"), "FGA-LrC15.lrplugin")
    return {root=root, release=release, cache=child(root, "cache"),
        receipt=child(root, "status.json"), temporary=child(root, "status.json.tmp")}
end
function Q.publish(sdk, json, locations, state)
    local file=assert(io.open(locations.temporary, "wb"), "fixture_receipt_unavailable")
    assert(file:write(json.encode(state)), "fixture_receipt_unavailable")
    assert(file:close(), "fixture_receipt_unavailable")
    assert(sdk.LrFileUtils.exists(locations.temporary) == "file", "fixture_receipt_unavailable")
    -- SDK move refuses an existing destination. Remove only our stable receipt,
    -- check the result and verify absence; never treat failed deletion as success.
    if sdk.LrFileUtils.exists(locations.receipt) then
        assert(sdk.LrFileUtils.delete(locations.receipt), "fixture_receipt_unavailable")
    end
    assert(not sdk.LrFileUtils.exists(locations.receipt), "fixture_receipt_unavailable")
    assert(sdk.LrFileUtils.move(locations.temporary, locations.receipt), "fixture_receipt_unavailable")
    assert(sdk.LrFileUtils.exists(locations.receipt) == "file"
        and not sdk.LrFileUtils.exists(locations.temporary), "fixture_receipt_unavailable")
end
function Q.run()
    if active then return end
    local names={"LrApplication", "LrBinding", "LrDate", "LrDialogs", "LrFileUtils",
        "LrFunctionContext", "LrLogger", "LrPathUtils", "LrTasks", "LrView"}
    local sdk={}
    for _, name in ipairs(names) do sdk[name]=import(name) end
    active=true
    sdk.LrTasks.startAsyncTask(function()
        sdk.LrFunctionContext.callWithContext("fixture-choice", function(context)
            context:addCleanupHandler(function() active=false end)
            local factory=sdk.LrView.osFactory()
            local properties=sdk.LrBinding.makePropertyTable(context)
            properties.scenario="success"
            local choices={}
            for _, name in ipairs(Q.SCENARIOS) do choices[#choices+1]={title=name, value=name} end
            if sdk.LrDialogs.presentModalDialog {title="Synthetic existing-photo fixture 0.0.1.5",
                contents=factory:column {bind_to_object=properties,
                    factory:static_text {title="Synthetic data only. Select scenario; follow the documented run order.", width_in_chars=80},
                    factory:popup_menu {value=sdk.LrView.bind "scenario", items=choices}},
                actionVerb="Run fixture", cancelVerb="Cancel"} ~= "ok" then return end
            local locations=Q.locations(sdk, _PLUGIN.path)
            local root, release=locations.root, locations.release
            local pngFile=assert(io.open(sdk.LrPathUtils.child(_PLUGIN.path, "synthetic.png"), "rb"))
            local png=pngFile:read("*a")
            pngFile:close()
            assert(sdk.LrFileUtils.createAllDirectories(root), "fixture_directory_unavailable")
            local json=load(sdk.LrPathUtils.child(release, "dkjson.lua"))
            local releaseInfo=load(sdk.LrPathUtils.child(release, "Info.lua"))
            local releaseVersion=releaseInfo.VERSION
            assert(type(releaseVersion) == "table", "fixture_version_unavailable")
            for _, key in ipairs({"major", "minor", "revision", "build"}) do
                local value=releaseVersion[key]
                assert(type(value) == "number" and value >= 0 and value <= 999999
                    and value == math.floor(value), "fixture_version_unavailable")
            end
            local releaseBuild=string.format("%d.%d.%d.%d", releaseVersion.major,
                releaseVersion.minor, releaseVersion.revision, releaseVersion.build)
            local now=sdk.LrDate.currentTime()
            local runId="fixture-" .. string.format("%.0f", now * 1000000)
            local function publish(state) Q.publish(sdk, json, locations, state) end
            local host=sdk.LrApplication.versionTable()
            local hostVersion={}
            for _, key in ipairs({"major", "minor", "revision"}) do
                local value=host[key]
                assert(type(value) == "number" and value >= 0 and value <= 999 and value == math.floor(value),
                    "fixture_host_unavailable")
                hostVersion[key]=value
            end
            assert(type(host.build_version) == "string" and #host.build_version <= 64
                and host.build_version:match("^[A-Za-z0-9][A-Za-z0-9._%-]*$"), "fixture_host_unavailable")
            hostVersion.buildVersion=host.build_version
            local function envelope(state, terminal)
                state.schemaVersion=1
                state.probe="existing_photo_synthetic"
                state.probeVersion=Q.VERSION
                state.releaseVersion=releaseBuild
                state.runId=runId
                state.host=hostVersion
                state.terminal=terminal
                state.nativeTransportQualified=false
                state.productionQualified=false
                return state
            end
            publish(envelope({scenario=properties.scenario, outcome="running"}, false))
            local result=Q.executeSafely(properties.scenario, sdk, release, locations.cache, png)
            publish(envelope(result, true))
            sdk.LrDialogs.message("Synthetic fixture " .. result.outcome,
                "Receipt updated in C:/Temp/FGA-existing-photo-qualification/status.json. Native transport remains unqualified.", "info")
        end)
    end)
end
return Q
