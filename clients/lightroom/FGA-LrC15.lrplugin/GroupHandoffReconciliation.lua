-- Copyright 2026 Terry Ott. MIT License.
-- Disabled, explicit recovery core. No request is sent by construction or list().
local Core = require "ConnectionCore"
local Photo = require "ExistingPhotoClient"
local Selection = require "GroupSelectionController"
local R = {PRODUCTION_QUALIFIED=false}
R.__index=R
local function clone(value)
    if type(value)~="table" then return value end
    local result={}; for k,v in pairs(value) do result[k]=clone(v) end; return result
end
local function integer(v)
    return type(v)=="number" and v>=1 and v<=9007199254740991 and v==math.floor(v)
end
local function opaque(v)
    return type(v)=="string" and #v>=1 and #v<=128 and v:match("^[A-Za-z0-9][A-Za-z0-9@._:%-]*$")~=nil
end
local function identity(v)
    if type(v)~="table" or not opaque(v.installationId) or not integer(v.linkedFlickrRevision) then return false end
    for k in pairs(v) do if k~="installationId" and k~="linkedFlickrRevision" then return false end end
    return true
end
local function finite(v) return type(v)=="number" and v==v and v>-math.huge and v<math.huge end
local function dense(v,max)
    if type(v)~="table" or #v>max then return false end
    local n=0
    for k in pairs(v) do if not integer(k) or k>#v then return false end; n=n+1 end
    return n==#v
end
local function binding(v)
    return type(v)=="table" and opaque(v.fgaPhotoBindingId) and opaque(v.flickrPhotoId)
        and integer(v.verificationRevision) and integer(v.linkRevision)
        and (v.sourceKind=="existing_public_flickr_photo" or v.sourceKind=="fga_direct_upload")
end
function R.new(d)
    if type(d)~="table" or type(d.store)~="table" or type(d.client)~="table"
        or type(d.client.submit)~="function" or d.catalog==nil or d.jsonNull==nil
        or (d.workflow~="existing_public_photo" and d.workflow~="publisher_bound") then
        return nil,"qualification_required"
    end
    for _,key in ipairs({"listPending","readHandoff","confirm"}) do
        if type(d.store[key])~="function" then return nil,"qualification_required" end
    end
    for _,key in ipairs({"call","activeCatalog","currentIdentity","retrieve","cancelled",
        "prove","now","post","encode","decode"}) do
        if type(d[key])~="function" then return nil,"qualification_required" end
    end
    local ok,session=d.call(function()
        local v=d.currentIdentity()
        local credential=d.retrieve(Core.CURRENT_KEY)
        if not identity(v) or not Core.isCanonicalCredential(credential) then return nil end
        return {installationId=v.installationId,linkedFlickrRevision=v.linkedFlickrRevision,credential=credential}
    end)
    if not ok or not session then return nil,"unavailable" end
    local self=setmetatable({deps=d,session=session,workflow=d.workflow,catalog=d.catalog},R)
    if not self:_current() then return nil,"unavailable" end
    return self
end
function R:_current()
    local d,s=self.deps,self.session
    if d.cancelled() or d.activeCatalog()~=self.catalog then return false end
    local v=d.currentIdentity()
    local candidate=d.retrieve(Core.CANDIDATE_KEY)
    return identity(v) and v.installationId==s.installationId and v.linkedFlickrRevision==s.linkedFlickrRevision
        and (candidate==nil or candidate=="") and d.retrieve(Core.CURRENT_KEY)==s.credential
end
function R:_boundary(fn,...)
    if not self:_current() then error("recovery_context_changed") end
    local a,b=fn(...)
    if not self:_current() then error("recovery_context_changed") end
    return a,b
end
function R:_record(scope,id,h)
    if type(h)~="table" or h.handoffId~=id or h.state~="prepared" or h.choice~="groups"
        or not integer(h.selectionRevision) or not integer(h.outboxRevision) or not binding(h.binding)
        or h.binding.linkRevision~=self.session.linkedFlickrRevision
        or not dense(h.flickrGroupIds,60) or #h.flickrGroupIds<1 then return false end
    local seen={}
    for _,g in ipairs(h.flickrGroupIds) do if not opaque(g) or seen[g] then return false end; seen[g]=true end
    if self.workflow=="existing_public_photo" then
        if h.workflow~=self.workflow or scope.installationId~=self.session.installationId then return false end
        for _,key in ipairs({"installationId","fgaPhotoBindingId","flickrPhotoId","linkedFlickrRevision","sourceKind"}) do
            if h[key]~=scope[key] then return false end
        end
        return h.binding.fgaPhotoBindingId==scope.fgaPhotoBindingId and h.binding.flickrPhotoId==scope.flickrPhotoId
            and h.binding.linkRevision==scope.linkedFlickrRevision and h.binding.sourceKind==scope.sourceKind
    end
    if h.workflow~=nil then return false end
    for _,key in ipairs({"publishServiceLocalId","publishedCollectionLocalId","photoUuid"}) do
        if h[key]~=scope[key] then return false end
    end
    return true
end
function R:_run(fn)
    if self.busy then return {state="busy"} end
    self.busy=true
    -- The composition supplies LrTasks.pcall so protected calls may yield.
    local ok,value=self.deps.call(fn)
    self.busy=false
    return ok and value or {state="unresolved"}
end
function R:list(scope)
    return self:_run(function()
        scope=clone(scope)
        local d=self.deps
        local pending=self:_boundary(function() return d.store:listPending(scope) end)
        if type(pending)~="table" or pending.state~="ready" or not dense(pending.handoffs,128) then
            return {state="unresolved"}
        end
        local ids,seen={},{}
        for _,record in ipairs(pending.handoffs) do
            local id=record.handoffId
            if not opaque(id) or seen[id] then return {state="unresolved"} end
            local found=self:_boundary(function() return d.store:readHandoff(scope,id) end)
            if type(found)~="table" or found.state~="ready" or not self:_record(scope,id,found.handoff) then
                return {state="unresolved"}
            end
            seen[id]=true; ids[#ids+1]=id
        end
        return {state="ready",pendingHandoffIds=ids}
    end)
end
function R:reconcile(scope,handoffId)
    return self:_run(function()
        scope=clone(scope)
        local d=self.deps
        if not opaque(handoffId) then return {state="unresolved"} end
        local found=self:_boundary(function() return d.store:readHandoff(scope,handoffId) end)
        if type(found)~="table" or found.state~="ready" or not self:_record(scope,handoffId,found.handoff) then
            return {state="unresolved"}
        end
        local h=clone(found.handoff)
        local original=h.binding
        local attempt={fgaPhotoBindingId=original.fgaPhotoBindingId,flickrPhotoId=original.flickrPhotoId,
            sourceKind=original.sourceKind,verificationRevision=original.verificationRevision,
            linkedFlickrRevision=original.linkRevision}
        local started
        if self.workflow=="existing_public_photo" or attempt.sourceKind=="existing_public_flickr_photo" then
            started=d.now()
            if not finite(started) then return {state="unresolved",reason="proof_expired"} end
            local fresh=self:_boundary(d.prove,attempt.flickrPhotoId,attempt.linkedFlickrRevision)
            if not Photo.validateBinding(fresh,attempt.flickrPhotoId,attempt.linkedFlickrRevision)
                or fresh.fgaPhotoBindingId~=attempt.fgaPhotoBindingId or fresh.sourceKind~=attempt.sourceKind then
                return {state="unresolved",reason="proof_required"}
            end
            attempt=clone(fresh)
            local ended=d.now()
            if not finite(ended) or ended<started or ended-started>=15 then
                return {state="unresolved",reason="proof_expired"}
            end
        end
        -- Fence inside post as well: encoding/client adapters may run before dispatch.
        local function post(...)
            if started then
                local ended=d.now()
                if not finite(ended) or ended<started or ended-started>=15 then error("proof_expired") end
            end
            return self:_boundary(d.post,...)
        end
        local bytes,headers=self:_boundary(d.client.submit,attempt.fgaPhotoBindingId,
            attempt.verificationRevision,clone(h.flickrGroupIds),self.session.credential,post,d.encode)
        if type(bytes)~="string" or #bytes>Selection.MAX_RESPONSE_BYTES or type(headers)~="table"
            or headers.status~=202 then return {state="unresolved"} end
        local decoded,value=pcall(d.decode,bytes)
        local submissions=decoded and Selection.validate202(value,attempt,h.flickrGroupIds,d.jsonNull) or nil
        if not submissions then return {state="unresolved"} end
        local confirmed=self:_boundary(function()
            return d.store:confirm(scope,handoffId,h.outboxRevision,{kind="groups_accepted",
                selectionRevision=h.selectionRevision,flickrGroupIds=clone(h.flickrGroupIds),
                binding=original,submissions=submissions},function() return self:_current() end)
        end)
        if type(confirmed)~="table" or confirmed.state~="confirmed" then return {state="unresolved"} end
        return {state="accepted",handoffId=handoffId,count=#h.flickrGroupIds,
            selectionConsumed=confirmed.selectionConsumed}
    end)
end
return R
