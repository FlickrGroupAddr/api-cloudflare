-- Copyright 2026 Terry Ott. MIT License.
-- Finite ordering instrumentation; source tests are not native evidence.
local M={}
function M.new(d)
    assert(type(d)=='table' and type(d.guard)=='function'
        and type(d.authorize)=='function' and type(d.stage)=='function')
    local s={ready=false,authorizationCalls=0,authorizationDeniedBeforeReady=false,
        authorizationAfterReady=false,staged=false,status='new',
        nativeSchedulingProven=false,productionQualified=false}
    local closed=false
    local function allowed()
        local ok,value=pcall(d.guard)
        return ok and value==true and not closed
    end
    local function authorize()
        if not allowed() then return nil,'scope_refused' end
        if not s.ready then
            s.authorizationDeniedBeforeReady=true
            return nil,'source_not_ready'
        end
        s.authorizationCalls=s.authorizationCalls+1
        local ok,value=pcall(d.authorize)
        s.authorizationAfterReady=ok and value==true
        return s.authorizationAfterReady or nil,'authorization_failed'
    end
    local o={}
    function o:beforeReady()
        if self~=o then return nil,'scope_refused' end
        return authorize()
    end
    function o:renderReady(path,size)
        if self~=o or not allowed() then return nil,'scope_refused' end
        if s.ready then return nil,'already_finished' end
        if type(path)~='string' or #path==0 or type(size)~='number'
            or size%1~=0 or size<1 or size>33554432 then
            closed=true;s.status='file_invalid';return nil,'file_invalid'
        end
        s.ready=true
        local ok=authorize()
        if not ok then closed=true;s.status='authorization_failed';return nil,s.status end
        if not allowed() then closed=true;s.status='scope_refused';return nil,s.status end
        local called,staged=pcall(d.stage,path,size)
        s.staged=called and staged==true and allowed()
        closed=true;s.status=s.staged and 'staged' or 'stage_failed'
        return s.staged or nil,s.status
    end
    function o:receipt()
        local copy={};for k,v in pairs(s) do copy[k]=v end;return copy
    end
    return o
end
return M
