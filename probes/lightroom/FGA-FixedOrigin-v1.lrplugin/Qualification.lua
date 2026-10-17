-- Copyright 2026 Terry Ott. MIT License. Original qualification composition.
-- No ambient SDK, secure store, catalog, network or module-cache access.
local Q={PRODUCTION_QUALIFIED=false}
function Q.translate(C,config,dependencies)
    return function(url,headers,timeout)
        local path=type(url)=="string" and url:sub(#C.ORIGIN+1) or nil
        local selected=path and C.requestCase(config,path)
        if not path or url~=C.ORIGIN..path or not C.PATHS[path] or C.PATHS[path]~=timeout
            or not selected
            or not C.validate(config,dependencies.now()) or dependencies.cancelled()
            or type(headers)~="table" or #headers~=1 then return nil,{} end
        for key in pairs(headers) do if key~=1 then return nil,{} end end
        local h=headers[1]
        if type(h)~="table" or h.field~="Authorization" or h.value~="Bearer "..C.CREDENTIAL then return nil,{} end
        for key in pairs(h) do if key~="field" and key~="value" then return nil,{} end end
        -- Only this exact, finite gate replaces the synthetic installation bearer.
        -- The ephemeral capability never enters release clients or the secure store.
        local bytes,response=dependencies.get(url,{
            {field="Authorization",value="FGA-Qualification "..config.capability},
            {field="X-FGA-Qualification-Run",value=config.run},
            {field="X-FGA-Qualification-Case",value=selected}},timeout)
        if dependencies.cancelled() or not C.validate(config,dependencies.now()) then return nil,{} end
        return bytes,response
    end
end
function Q.dependencies(C,config,d,Read,Core,Client)
    if type(Read.qualification)~="function" then return nil,"qualification_seam_unavailable" end
    local adapter,reason=Read.qualification{get=Q.translate(C,config,d),call=d.call,
        retrieve=function(key) return key==Core.CURRENT_KEY and C.CREDENTIAL or nil end,
        current=d.current,cancelled=d.cancelled,now=d.now,
        expectedInstallationId=C.installation(C.PREFLIGHT_CASE)}
    if not adapter then return nil,reason end
    local result={decode=adapter.decode,jsonNull=adapter.jsonNull,cancelled=adapter.cancelled}
    result.request=Client.authenticatedRequest(adapter,Core)
    result.close=adapter.cancel
    return result
end
-- Full-page staging precedes any rendering. Each request uses unchanged client
-- parsing, exact validated discovery references, and per-request verification.
function Q.execute(config,d,Client,state)
    local generation,pageNumber=0,1
    local function current(ticket) return not d.cancelled() and generation==ticket end
    if config.mode=="fault" then
        local page,reason=Client.discover(d.protocol,1,1)
        if not page then state.reason="discovery_rejected"; return end
        local bytes=Client.thumbnail(d.protocol,page.photos[1],page)
        state.thumbnailAccepted=bytes~=nil; bytes=nil
        state.reason=reason or (state.thumbnailAccepted and "response_accepted" or "thumbnail_rejected")
        return
    end
    for _=1,6 do
        if d.cancelled() then state.reason="cancelled"; return end
        generation=generation+1
        local ticket=generation
        local page=Client.discover(d.protocol,pageNumber,2)
        if not current(ticket) then state.staleResultsDiscarded=state.staleResultsDiscarded+1;state.reason="cancelled";return end
        if not page then state.reason="discovery_rejected"; return end
        local expected=pageNumber==1 and 2 or 1
        if page.total~=3 or page.pages~=2 or #page.photos~=expected then state.reason="page_shape_rejected";return end
        local staged={}
        for index,photo in ipairs(page.photos) do
            local bytes,media=Client.thumbnail(d.protocol,photo,page)
            -- Cancellation is cooperative. The SDK GET may still be in flight;
            -- late bytes never become a file or visible picture.
            if config.mode=="stale" and index==1 then generation=generation+1 end
            if not current(ticket) then
                bytes=nil;state.staleResultsDiscarded=state.staleResultsDiscarded+1
                state.reason=config.mode=="stale" and "stale_discarded" or "cancelled";return
            end
            if not bytes then state.reason="thumbnail_rejected";return end
            local path=d.stage(index,bytes,media)
            bytes=nil
            if not path then state.reason="cache_write_failed";return end
            staged[#staged+1]={path=path,photo=photo}
        end
        if not current(ticket) then state.reason="cancelled";return end
        state.completePages=state.completePages+1
        local action,confirmed=d.show(page,staged)
        state.pictureControls=state.pictureControls+#staged
        if confirmed then state.observerConfirmedPages=state.observerConfirmedPages+1 end
        if not d.clearPage() then state.reason="cache_cleanup_failed";return end
        if action=="next" and pageNumber==1 then pageNumber=2;state.navigation=state.navigation+1
        elseif action=="previous" and pageNumber==2 then pageNumber=1;state.navigation=state.navigation+1
        else state.reason=confirmed and "page_observed" or "cancelled";return end
    end
    state.reason="finite_limit"
end
return Q
