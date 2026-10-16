-- Copyright 2026 Terry Ott. MIT License.
-- Disabled candidate. The composition root supplies qualified adapters.
local C = { PRODUCTION_QUALIFIED = false, MAX_RESPONSE_BYTES = 2097152 }
C.__index = C
local function integer(v) return type(v) == "number" and v >= 1 and v <= 9007199254740991 and v == math.floor(v) end
local function opaque(v) return type(v) == "string" and #v >= 1 and #v <= 128 and v:match("^[A-Za-z0-9][A-Za-z0-9@._:%-]*$") ~= nil end
local function dense(t, maximum)
    if type(t) ~= "table" or #t > maximum then return false end
    local n = 0
    for k in pairs(t) do
        if type(k) ~= "number" or k < 1 or k > #t or k ~= math.floor(k) then return false end
        n = n + 1
    end
    return n == #t
end
local function exact(t, keys)
    if type(t) ~= "table" then return false end
    local n = 0
    for k in pairs(t) do if not keys[k] then return false end; n = n + 1 end
    local expected = 0
    for _ in pairs(keys) do expected = expected + 1 end
    return n == expected
end
local function copy(t) local r = {}; for i,v in ipairs(t) do r[i] = v end; return r end
local function bindingCopy(b)
    return {fgaPhotoBindingId=b.fgaPhotoBindingId,flickrPhotoId=b.flickrPhotoId,
        verificationRevision=b.verificationRevision,linkedFlickrRevision=b.linkedFlickrRevision,
        sourceKind=b.sourceKind}
end
local function timestamp(v)
    if type(v)~="string" or #v>40 or not v:match("^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d%.?%d*Z$") then return false end
    local y,m,d,h,n,s=v:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)")
    y,m,d,h,n,s=tonumber(y),tonumber(m),tonumber(d),tonumber(h),tonumber(n),tonumber(s)
    if m<1 or m>12 or d<1 or h>23 or n>59 or s>59 then return false end
    local days={31,28,31,30,31,30,31,31,30,31,30,31}
    if y%400==0 or (y%4==0 and y%100~=0) then days[2]=29 end
    return d<=days[m] and not v:find("%.Z$",1)
end
local states = {queued=true,attempting=true,retrying=true,throttled=true,added=true,
    moderation_submitted=true,delivery_uncertain=true,needs_attention=true,cancelled=true}
function C.validate202(v, binding, groups, jsonNull)
    if not dense(groups,60) or #groups<1 or type(binding)~="table"
        or not exact(v,{schemaVersion=true,fgaPhotoBindingId=true,flickrPhotoId=true,submissions=true})
        or v.schemaVersion ~= 2 or v.fgaPhotoBindingId ~= binding.fgaPhotoBindingId
        or v.flickrPhotoId ~= binding.flickrPhotoId or not dense(v.submissions,60)
        or #v.submissions ~= #groups then return nil end
    local ids, intents = {}, {}
    for i,row in ipairs(v.submissions) do
        if not exact(row,{fgaSubmissionIntentId=true,flickrGroupId=true,state=true,created=true,permanentSubmissionBlock=true})
            or row.flickrGroupId ~= groups[i] or not opaque(row.fgaSubmissionIntentId)
            or ids[row.fgaSubmissionIntentId] or not states[row.state] or type(row.created) ~= "boolean" then return nil end
        local block, reason = row.permanentSubmissionBlock, nil
        if block ~= jsonNull then
            if not exact(block,{reasonCode=true,createdAt=true})
                or (block.reasonCode ~= "moderation_submission_recorded" and block.reasonCode ~= "delivery_uncertain")
                or not timestamp(block.createdAt) then return nil end
            reason = block.reasonCode
            if row.created then return nil end
        end
        if (row.state == "moderation_submitted") ~= (reason == "moderation_submission_recorded")
            or (row.state == "delivery_uncertain") ~= (reason == "delivery_uncertain") then return nil end
        ids[row.fgaSubmissionIntentId] = true
        intents[i] = {fgaSubmissionIntentId=row.fgaSubmissionIntentId,flickrGroupId=row.flickrGroupId,
            state=row.state,created=row.created,permanentSubmissionBlock=block}
    end
    return intents
end
function C.valid(s) return s.ready == true end
function C.code(s,g) return s.ready and "eligible" or "unavailable" end
function C.count(s) local n=0; for _,v in pairs(s.selected) do if v then n=n+1 end end; return n end
function C.toggle(s,id,value)
    if not s.ready then return false end
    for _,g in ipairs(s.groups) do if g.id==id then s.selected[id]=value==true; return true end end
    return false
end
function C.matches(g,q) return (g.name.." "..g.id):lower():find((q or ""):lower(),1,true) ~= nil end
function C.unavailableChoices(s)
    local allowed,ids={},{}
    for _,g in ipairs(s.groups) do allowed[g.id]=true end
    for id,v in pairs(s.selected) do if v and not allowed[id] then ids[#ids+1]=id end end
    table.sort(ids); return ids
end
function C.clearUnavailableChoices(s)
    if not s.ready then return false end
    for _,id in ipairs(C.unavailableChoices(s)) do s.selected[id]=nil end
    return true
end
function C.canConfirm(s)
    if not s.ready then return false end
    local allowed={}; for _,g in ipairs(s.groups) do allowed[g.id]=true end
    for id,v in pairs(s.selected) do if v and not allowed[id] then return false end end
    local n=C.count(s); return n<=60 and (not s.bound or n>0)
end
function C.new(deps,scope,eligibility,binding,context)
    local self=setmetatable({deps=deps,scope=scope,binding=binding,busy=false},C)
    local s={ready=false,bound=eligibility.bound==true,groups={},selected={},query="",rows=eligibility.rows or {}}
    s.refreshedAt=eligibility.refreshedAt
    s.membershipObservedAt=eligibility.membershipObservedAt
    s.statusObservedAt=eligibility.statusObservedAt
    self.model=s
    -- Workflow is trusted composition context, independent of original binding provenance.
    if context ~= nil and (not exact(context,{workflow=true})
        or (context.workflow~="existing_public_photo" and context.workflow~="publisher_bound")) then return self end
    self.existingPublicWorkflow=context and context.workflow=="existing_public_photo" or false
    if eligibility.state~="ready" or not dense(eligibility.eligibleGroups,10000) then return self end
    local seen={}
    for _,g in ipairs(eligibility.eligibleGroups) do
        if not opaque(g.flickrGroupId) or seen[g.flickrGroupId] or type(g.displayName)~="string" then return self end
        seen[g.flickrGroupId]=true; s.groups[#s.groups+1]={id=g.flickrGroupId,name=g.displayName}
    end
    table.sort(s.groups,function(a,b) return a.name==b.name and a.id<b.id or a.name<b.name end)
    local loaded=deps.store:readChoice(scope)
    if type(loaded)~="table" or loaded.state~="ready" then return self end
    self.revision=loaded.selection and loaded.selection.selectionRevision or 0
    for _,id in ipairs(loaded.selection and loaded.selection.flickrGroupIds or {}) do s.selected[id]=true end
    if s.bound and (type(binding)~="table" or binding.fgaPhotoBindingId~=eligibility.fgaPhotoBindingId
        or binding.flickrPhotoId~=eligibility.flickrPhotoId) then return self end
    s.ready=true; return self
end
local function validBinding(b)
    return type(b)=="table" and opaque(b.fgaPhotoBindingId) and opaque(b.flickrPhotoId)
        and integer(b.verificationRevision) and integer(b.linkedFlickrRevision)
        and (b.sourceKind=="existing_public_flickr_photo" or b.sourceKind=="fga_direct_upload")
end
local function finite(v)
    return type(v)=="number" and v==v and v>-math.huge and v<math.huge
end
function C:commit()
    if self.busy or not C.canConfirm(self.model) then return {state="refused"} end
    self.busy=true
    -- call must be LrTasks.pcall in a yielding SDK task. Never raw Lua pcall around HTTP.
    local ok,result=self.deps.call(function() return self:_commit() end)
    self.busy=false
    return ok and result or {state="unresolved"}
end
function C:_commit()
    local d,s=self.deps,self.model
    local groups={}; for id,v in pairs(s.selected) do if v then groups[#groups+1]=id end end; table.sort(groups)
    if not s.bound then
        local saved=d.store:saveChoice(self.scope,groups,self.revision)
        if saved.state~="saved" then return {state="save_failed"} end
        self.revision=saved.selection.selectionRevision
        return {state="saved",count=#groups}
    end
    if not validBinding(self.binding) then return {state="proof_required"} end
    local b=bindingCopy(self.binding)
    local proofStarted
    if self.existingPublicWorkflow or b.sourceKind=="existing_public_flickr_photo" then
        proofStarted=d.now()
        if not finite(proofStarted) then return {state="proof_required"} end
        local fresh=d.prove(b.flickrPhotoId,b.linkedFlickrRevision)
        if not validBinding(fresh) or fresh.fgaPhotoBindingId~=b.fgaPhotoBindingId
            or fresh.flickrPhotoId~=b.flickrPhotoId or fresh.linkedFlickrRevision~=b.linkedFlickrRevision
            or fresh.sourceKind~=b.sourceKind then return {state="proof_required"} end
        b=bindingCopy(fresh)
    end
    local handoffId=d.newHandoffId()
    if not opaque(handoffId) then return {state="save_failed"} end
    local durable=d.store:saveChoice(self.scope,groups,self.revision,handoffId,{
        fgaPhotoBindingId=b.fgaPhotoBindingId,flickrPhotoId=b.flickrPhotoId,
        verificationRevision=b.verificationRevision,linkRevision=b.linkedFlickrRevision,sourceKind=b.sourceKind})
    if durable.state~="saved" or type(durable.handoff)~="table" then return {state="save_failed"} end
    self.revision=durable.selection.selectionRevision
    local h=durable.handoff
    -- Copy request identity before the yielding boundary; neither UI edits nor adapters own it.
    local revision=self.revision
    if proofStarted then
        local proofEnded=d.now()
        local elapsed=finite(proofEnded) and proofEnded-proofStarted or nil
        if not finite(elapsed) or elapsed<0 or elapsed>=15 then
            return {state="unresolved",reason="proof_expired"}
        end
    end
    local bytes,headers=d.client.submit(b.fgaPhotoBindingId,b.verificationRevision,copy(groups),d.credential(),d.post,d.encode)
    if type(bytes)~="string" or #bytes>C.MAX_RESPONSE_BYTES or type(headers)~="table" or headers.status~=202 then
        return {state="unresolved"}
    end
    local decoded,value=pcall(d.decode,bytes)
    local intents=decoded and C.validate202(value,b,groups,d.jsonNull) or nil
    if not intents then return {state="unresolved"} end
    local confirmed=d.store:confirm(self.scope,handoffId,h.outboxRevision,{
        kind="groups_accepted",selectionRevision=revision,flickrGroupIds=copy(groups),binding=h.binding,
        submissions=intents})
    if confirmed.state~="confirmed" then return {state="unresolved"} end
    if confirmed.selectionConsumed then self.model.ready=false end
    return {state="accepted",count=#groups,selectionConsumed=confirmed.selectionConsumed}
end
return C
