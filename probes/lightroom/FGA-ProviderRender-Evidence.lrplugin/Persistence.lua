-- Copyright 2026 Terry Ott. MIT License.
-- Supplemental synthetic evidence only. No host initialization, scheduling or network.
local Selection=require 'GroupSelectionStore'
local Attempts=require 'UploadAttemptStore'
local M={FIELD='providerRenderEvidencePersistenceV1',MAX_FIELD_BYTES=65536,MAX_RECORD_BYTES=2048}
local scopeKeys={'artifactSha2_256','runId','catalogKey','serviceId','albumId','photoUuid'}
local function token(v) return type(v)=='string' and #v>=1 and #v<=128
    and v:match('^[A-Za-z0-9][A-Za-z0-9._:%-]*$')~=nil end
local function digest(v) return type(v)=='string' and #v==64 and v:match('^[a-f0-9]+$')~=nil end
local function fail(state) return {state=state,restartProven=false} end
local function scopePrefix(s)
    if type(s)~='table' or getmetatable(s)~=nil then return nil end
    local allowed={};local values={'FGA-EVIDENCE-PERSISTENCE-1'}
    for _,k in ipairs(scopeKeys) do
        allowed[k]=true
        if not token(s[k]) then return nil end
        values[#values+1]=s[k]
    end
    for k in pairs(s) do if not allowed[k] then return nil end end
    if not digest(s.artifactSha2_256) or not digest(s.catalogKey) then return nil end
    return table.concat(values,'|')..'|'
end
function M.new(o)
    o=o or {}
    local prefix=scopePrefix(o.scope)
    local photoUuid=prefix and o.scope.photoUuid or nil
    local catalog,photo,plugin=o.catalog,o.photo,o.plugin
    local consumed={}
    local usedPhases={}
    local result={}
    -- IDs bind finite actions and correlate evidence; they are not secrets or
    -- proof of a different host process. No wall-clock inference occurs here.
    local function valid(phase,actionId)
        return prefix~=nil and catalog~=nil and photo~=nil and plugin~=nil
            and type(o.pcall)=='function' and type(o.hash)=='function'
            and type(o.guard)=='function' and type(o.activeCatalog)=='function'
            and o.activeCatalog()==catalog and o.guard(phase,actionId)==true
            and photo:getRawMetadata('uuid')==photoUuid
    end
    local function snapshot()
        local values={photo:getPropertyForPlugin(plugin,Selection.SELECTION_FIELD),
            catalog:getPropertyForPlugin(plugin,Selection.OUTBOX_FIELD),
            catalog:getPropertyForPlugin(plugin,Attempts.STORE_FIELD),
            photo:getPropertyForPlugin(plugin,Attempts.PHOTO_FIELD)}
        local fingerprints={}
        -- All four actual persisted production-store fields are compared. The
        -- correlation field may be absent before a synthetic upload completes.
        for i=1,4 do
            local v=values[i]
            if v==nil and i==4 then fingerprints[i]='absent'
            elseif type(v)~='string' or #v<1 or #v>M.MAX_FIELD_BYTES then return nil
            else
                local h=o.hash(v)
                if not digest(h) then return nil end
                fingerprints[i]=tostring(#v)..':'..h
            end
        end
        return table.concat(fingerprints,'|')
    end
    local function run(phase,actionId)
        if not token(actionId) or consumed[actionId] or usedPhases[phase] or type(o.pcall)~='function' then
            return fail('action_refused')
        end
        -- One attempt per module instance even when the write outcome is unknown.
        consumed[actionId]=true;usedPhases[phase]=true
        local callbackOpen=true
        local expected,operationState,finished,expectedFields
        local ok,gate=o.pcall(function()
            if not valid(phase,actionId) then return 'scope_invalid' end
            return catalog:withPrivateWriteAccessDo(function()
                if not callbackOpen or not valid(phase,actionId) then error('scope_invalid',0) end
                local stored=catalog:getPropertyForPlugin(plugin,M.FIELD)
                if stored~=nil and (type(stored)~='string' or #stored>M.MAX_RECORD_BYTES) then
                    operationState='stored_invalid';return
                end
                local actual=snapshot()
                if not actual then operationState='store_fields_invalid';return end
                expectedFields=actual
                if phase=='prepare' then
                    if stored~=nil then operationState='already_prepared';return end
                    expected=prefix..'prepared|'..actionId..'|'..actual
                else
                    local start=prefix..'prepared|'
                    if type(stored)~='string' or stored:sub(1,#start)~=start then
                        operationState='scope_or_phase_mismatch';return
                    end
                    local remainder=stored:sub(#start+1)
                    local prior,fields=remainder:match('^([^|]+)|(.+)$')
                    if not token(prior) or prior==actionId or fields~=actual then
                        operationState='store_or_action_mismatch';return
                    end
                    expected=prefix..'consumed|'..actionId..'|'..actual
                end
                if #expected>M.MAX_RECORD_BYTES then error('record_too_large',0) end
                if not valid(phase,actionId) then error('scope_invalid',0) end
                catalog:setPropertyForPlugin(plugin,M.FIELD,expected)
                finished=true
            end,{timeout=5,asynchronous=false})
        end)
        callbackOpen=false
        if not ok then return fail('storage_unavailable') end
        if gate=='scope_invalid' then return fail('scope_invalid') end
        if gate~='executed' then return fail('write_unconfirmed') end
        if not finished then return fail(operationState or 'write_unconfirmed') end
        local readOk,matched=o.pcall(function()
            return valid(phase,actionId) and catalog:getPropertyForPlugin(plugin,M.FIELD)==expected
                and snapshot()==expectedFields
        end)
        if not readOk or not matched then return fail('write_unconfirmed') end
        return {state=phase=='prepare' and 'prepared_readback' or 'observed_consumed',
            restartProven=false,actualStoreFieldsCompared=4,
            lifecycleEvidenceRequired=true}
    end
    function result:prepare(actionId) return run('prepare',actionId) end
    function result:observe(actionId) return run('observe',actionId) end
    return result
end
return M
