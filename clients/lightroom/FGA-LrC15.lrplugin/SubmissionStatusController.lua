-- Copyright 2026 Terry Ott. MIT License.
-- Disabled, injected read-only owner. tick() may yield; only the SDK task calls it.
local C = {PRODUCTION_QUALIFIED=false}
C.__index = C
local contexts = setmetatable({}, {__mode='k'})
local errors = {unavailable=true, response_invalid=true, status_changed=true,
    authentication_unconfirmed=true, invalid_request=true, cancelled=true}
local function id(v)
    return type(v)=='string' and #v>0 and #v<=128 and v:match('^[A-Za-z0-9][A-Za-z0-9@._:%-]*$')~=nil
end
local function finite(v) return type(v)=='number' and v==v and math.abs(v)<math.huge end
function C.new(d, binding)
    if type(d)~='table' or type(binding)~='table' or not id(binding.fgaPhotoBindingId)
        or not id(binding.flickrPhotoId) or not id(d.installationId) or type(d.context)~='table'
        or type(d.client)~='table' or type(d.client.history)~='function'
        or type(d.client.presentation)~='function' or d.jsonNull==nil then return nil,'invalid_request' end
    for _,name in ipairs({'now','currentContext','request','decode','sleep','protect'}) do
        if type(d[name])~='function' then return nil,'invalid_request' end
    end
    local installations=contexts[d.context]
    if not installations then installations={}; contexts[d.context]=installations end
    local owner=installations[d.installationId]
    if not owner then owner={records={}, nextReadAt=0, failures=0}; installations[d.installationId]=owner end
    local key=binding.fgaPhotoBindingId..'/'..binding.flickrPhotoId
    local record=owner.records[key]
    if not record then record={nextAt=0}; owner.records[key]=record end
    return setmetatable({d=d,binding={fgaPhotoBindingId=binding.fgaPhotoBindingId,
        flickrPhotoId=binding.flickrPhotoId},owner=owner,record=record,
        visible=false,generation=0,model={state='unavailable',readOnly=true,stale=false}}, C)
end
function C:valid()
    return self.visible and self.d.currentContext()==self.d.context
end
function C:open()
    self.generation=self.generation+1
    self.visible=true
    self.pending=self.record.good==nil
    self:_sync()
end
function C:close()
    self.visible=false
    self.pending=false
    self.generation=self.generation+1
end
function C:_sync()
    local r=self.record
    if self.d.currentContext()~=self.d.context then
        self.model={state='unavailable',reason='cancelled',stale=false,readOnly=true}
        return
    end
    if r.good and self.seenGood~=r.good then
        self.pending=false -- A shared completed traversal satisfies existing demand.
        self.seenGood=r.good
    end
    self.model={state=r.good and (r.reason and 'stale' or 'complete') or 'unavailable',
        data=r.good,stale=r.good~=nil and r.reason~=nil,reason=r.reason,readOnly=true}
end
-- Manual refresh changes demand only, never admission time or write state.
function C:refresh()
    if not self:valid() then return false end
    self.pending=true
    return true
end
function C:tick()
    if not self:valid() then self:_sync(); return false end
    self:_sync()
    local r,owner=self.record,self.owner
    local now=self.d.now()
    if not finite(now) or owner.lastNow and now<owner.lastNow then
        owner.nextReadAt=math.huge; r.reason='unavailable'
        self:close(); self:_sync()
        return false
    end
    owner.lastNow=now
    local automatic=r.good~=nil and r.good.minimumRefreshAfterSeconds~=nil or r.reason~=nil
    if owner.busy or now<owner.nextReadAt or now<r.nextAt or not self.pending and not automatic then return false end
    -- Opening another consumer of a fresh cached result does not trigger a read.
    if r.good and not r.reason and r.good.minimumRefreshAfterSeconds==nil and not self.pending then return false end
    owner.busy=true
    self.pending=false
    local generation=self.generation
    local function cancelled() return not self:valid() or self.generation~=generation end
    local deps={request=self.d.request,decode=self.d.decode,sleep=self.d.sleep,
        jsonNull=self.d.jsonNull,cancelled=cancelled}
    local ok,result,reason,failed=self.d.protect(function()
        return self.d.client.history(deps,self.binding,r.good)
    end)
    owner.busy=false
    local finished=self.d.now()
    if not finite(finished) or finished<now then
        owner.nextReadAt=math.huge
        r.reason='unavailable'
        self:close(); self:_sync(); return false
    end
    owner.lastNow=finished
    owner.nextReadAt=finished+5
    if cancelled() then return false end
    if ok and result and result.state=='complete' then
        r.good,r.reason=result,nil
        owner.failures=0
        r.nextAt=finished+(result.minimumRefreshAfterSeconds or 5)
    else
        reason=ok and errors[reason] and reason or 'unavailable'
        r.reason=reason
        owner.failures=math.min(owner.failures+1,5)
        local retry=ok and type(failed)=='table' and failed.minimumRefreshAfterSeconds or 0
        if not finite(retry) or retry<0 then retry=0 end
        r.nextAt=finished+math.max(retry,math.min(60*2^(owner.failures-1),960))
        -- Collection failures apply to the installation, including other bindings.
        owner.nextReadAt=math.max(owner.nextReadAt,r.nextAt)
    end
    self:_sync()
    return true
end
return C
