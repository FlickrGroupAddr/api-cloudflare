-- Copyright 2026 Terry Ott. MIT License.
-- Qualification-only constructor. Actual provider/selection/frozen/0028/0095
-- modules own behavior. This wrapper grants no production qualification.
local Provider=require 'OrdinaryAlbumProvider'
local M={PRODUCTION_QUALIFIED=false,NATIVE_SCHEDULING_PROVEN=false}
local cases={selection_absent=true,selection_none=true,selection_groups=true,
    selection_edit_after_freeze=true,photo_failure_isolation=true,target_rejected=true,
    catalog_changed=true,activation_changed=true,cancelled=true,render_failed=true,
    missing_file=true,oversized_file=true,file_changed=true,cleanup_revocation=true}
local codes={prepared=true,preparation_failed=true,preparation_invalid=true,
    settings_invalid=true,settings_not_applied=true,scope_invalid=true,
    scope_refused=true,fixture_closed=true,session_invalid=true,receipt_limit=true,
    rendition_failed=true,rendition_invalid=true,photo_not_prepared=true,
    photo_already_finished=true,settings_changed=true,context_stale=true,
    context_required=true,cancelled=true,render_failed=true,preflight_failed=true,
    missing_file=true,file_inspection_failed=true,unreadable_file=true,
    file_changed=true,oversized=true,empty_file=true,invalid_size=true,
    invalid_limit=true,handoff_failed=true,file_not_read=true,handed_off=true,
    closed=true,unresolved=true}
local function clone(t)
    local result={};for k,v in pairs(t) do
        result[k]=type(v)=='table' and clone(v) or v
    end;return result
end
local function construct(d,qualification)
    if type(d)~='table' or type(d.guard)~='function' or not cases[d.caseId]
        or type(d.scope)~='table' or d.scope.disposable~=true
        or d.scope.syntheticOnly~=true or d.scope.catalogIdentity==nil
        or type(d.scope.activeCatalog)~='function'
        or type(d.providerDependencies)~='table'
        or type(d.providerDependencies.pcall)~='function' then return nil,'scope_refused' end
    local call=d.providerDependencies.pcall
    local guard,active,catalog=d.guard,d.scope.activeCatalog,d.scope.catalogIdentity
    local caseId,closed,receipts,sessions=d.caseId,false,{},{}
    local function current()
        if closed then return false end
        local ok,value=call(function() return guard()==true and active()==catalog end)
        return ok and value==true
    end
    if not current() then return nil,'scope_refused' end
    local factoryDeps={}
    for k,v in pairs(d.providerDependencies) do factoryDeps[k]=v end
    local ok,provider=call(qualification and Provider.newQualification or Provider.new,factoryDeps)
    if not ok then return nil,'scope_refused' end
    local Q={}
    local function receipt(phase,code,passed)
        if #receipts>=64 then closed=true;sessions={};return end
        receipts[#receipts+1]={schemaVersion=1,caseId=caseId,phase=phase,
            code=codes[code] and code or 'unresolved',ok=passed==true,
            nativeSchedulingProven=false,productionQualified=false}
    end
    local function allowed()
        if closed then return nil,'fixture_closed' end
        if #receipts>=63 then receipt('guard','receipt_limit',false);return nil,'receipt_limit' end
        if not current() then receipt('guard','scope_refused',false);return nil,'scope_refused' end
        return true
    end
    function Q:prepare(context,preparation)
        if self~=Q then return nil,'scope_refused' end
        local valid,why=allowed();if not valid then return nil,why end
        if type(preparation)~='table' or type(preparation.contextDependencies)~='table' then
            receipt('preparation','preparation_invalid',false);return nil,'preparation_invalid'
        end
        local prep={};for k,v in pairs(preparation) do prep[k]=v end
        local deps={};for k,v in pairs(prep.contextDependencies) do deps[k]=v end
        local originalCancelled=deps.cancelled
        local originalActive=deps.activeCatalog
        if type(originalActive)~='function' then
            receipt('preparation','scope_refused',false);return nil,'scope_refused'
        end
        deps.activeCatalog=function()
            if current() and originalActive()==catalog then return catalog end
        end
        deps.cancelled=function()
            return not current() or (originalCancelled and originalCancelled()) or false
        end
        prep.contextDependencies=deps
        local worked,session,reason=call(provider.prepareBeforeRendering,context,prep)
        if not worked or not session then
            reason=worked and reason or 'preparation_failed'
            receipt('preparation',reason,false);return nil,codes[reason] and reason or 'unresolved'
        end
        if not current() then receipt('preparation','scope_refused',false);return nil,'scope_refused' end
        local handle={};sessions[handle]=session
        receipt('preparation','prepared',true);return handle
    end
    function Q:process(handle,rendition,consume)
        if self~=Q then return nil,'scope_refused' end
        local valid,why=allowed();if not valid then return nil,why end
        local session=sessions[handle]
        if not session then receipt('rendition','session_invalid',false);return nil,'session_invalid' end
        local worked,result,reason=call(session.process,session,rendition,consume)
        if not worked then result={ok=false,code='rendition_failed'} end
        receipt('rendition',result and result.code or reason,result and result.ok)
        return result,reason
    end
    function Q:receipts()
        if self~=Q then return {} end
        return clone(receipts)
    end
    function Q:finish()
        if self~=Q then return nil,'scope_refused' end
        if not closed then receipt('cleanup','closed',true) end
        closed=true;sessions={}
        return {ok=true,code='closed'}
    end
    return Q
end
function M.new(d) return construct(d,false) end
function M.newQualification(d) return construct(d,true) end
return M
