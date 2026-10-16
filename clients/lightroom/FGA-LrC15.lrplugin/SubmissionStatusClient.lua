-- Injected read-only Lua 5.1 client. The SDK task owns yield-safe protection.
local Client = {MAX_PAGES=100, MAX_INTENTS=10000, MAX_RESPONSE_BYTES=2097152}
local function strictJson(body, decode)
    local pos, length = 1, #body
    local function char() return string.sub(body, pos, pos) end
    local function white()
        while char() == " " or char() == "\t" or char() == "\r" or char() == "\n" do pos = pos + 1 end
    end
    local function jsonString()
        if char() ~= '"' then return nil end
        local start = pos
        pos = pos + 1
        while pos <= length do
            local current = char()
            if current == '"' then pos = pos + 1; return string.sub(body, start, pos - 1) end
            if string.byte(current) < 32 then return nil end
            if current == "\\" then
                pos = pos + 1
                current = char()
                if current == "u" then
                    if not string.match(string.sub(body, pos + 1, pos + 4), "^%x%x%x%x$") then return nil end
                    pos = pos + 4
                elseif current ~= '"' and current ~= "\\" and current ~= "/" and current ~= "b"
                    and current ~= "f" and current ~= "n" and current ~= "r" and current ~= "t" then return nil end
            end
            pos = pos + 1
        end
        return nil
    end
    local function digits()
        local start = pos
        while string.match(char(), "^[0-9]$") do pos = pos + 1 end
        return pos > start
    end
    local value
    value = function(depth)
        if depth > 32 then return false end
        white()
        local current = char()
        if current == '"' then return jsonString() ~= nil end
        if current == "{" or current == "[" then
            local object, keys = current == "{", {}
            local finish = object and "}" or "]"
            pos = pos + 1
            white()
            if char() == finish then pos = pos + 1; return true end
            while true do
                if object then
                    local rawKey = jsonString()
                    if not rawKey then return false end
                    local ok, key = pcall(decode, rawKey)
                    if not ok or type(key) ~= "string" or keys[key] then return false end
                    keys[key] = true
                    white()
                    if char() ~= ":" then return false end
                    pos = pos + 1
                end
                if not value(depth + 1) then return false end
                white()
                if char() == finish then pos = pos + 1; return true end
                if char() ~= "," then return false end
                pos = pos + 1
                white()
            end
        end
        for _, literal in ipairs({"true", "false", "null"}) do
            if string.sub(body, pos, pos + #literal - 1) == literal then
                pos = pos + #literal
                return true
            end
        end
        if current == "-" then pos = pos + 1 end
        if char() == "0" then pos = pos + 1
        elseif string.match(char(), "^[1-9]$") then digits()
        else return false end
        if char() == "." then pos = pos + 1; if not digits() then return false end end
        if char() == "e" or char() == "E" then
            pos = pos + 1
            if char() == "+" or char() == "-" then pos = pos + 1 end
            if not digits() then return false end
        end
        return true
    end
    if not value(1) then return false end
    white()
    return pos == length + 1
end
local function exact(value, names)
    if type(value) ~= 'table' then return false end
    local fields = {}
    for name in names:gmatch('%S+') do fields[name] = true; if value[name] == nil then return false end end
    for name in pairs(value) do if not fields[name] then return false end end
    return true
end
local function integer(value, minimum)
    return type(value) == 'number' and value >= (minimum or 0)
        and value <= 9007199254740991 and value == math.floor(value)
end
local function id(value)
    return type(value) == 'string' and #value > 0 and #value <= 128
        and value:match('^[A-Za-z0-9][A-Za-z0-9@._:%-]*$') ~= nil
end
local function timestamp(value)
    if type(value) ~= 'string' then return false end
    local y,m,d,h,n,s = value:match('^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)%.%d%d%d%d%d%dZ$')
    if not y then return false end
    y,m,d,h,n,s = tonumber(y),tonumber(m),tonumber(d),tonumber(h),tonumber(n),tonumber(s)
    local days = {31,28,31,30,31,30,31,31,30,31,30,31}
    if y % 400 == 0 or y % 4 == 0 and y % 100 ~= 0 then days[2] = 29 end
    return m >= 1 and m <= 12 and d >= 1 and d <= days[m] and h < 24 and n < 60 and s < 60
end
local function array(value, maximum)
    if type(value) ~= 'table' or #value > maximum then return false end
    local meta = getmetatable(value)
    if not meta or meta.__jsontype ~= 'array' then return false end
    local count = 0
    for key in pairs(value) do if not integer(key,1) or key > #value then return false end; count=count+1 end
    return count == #value
end
local function same(a,b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= 'table' then return a == b end
    for k,v in pairs(a) do if not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function escape(value)
    return (value:gsub('([^A-Za-z0-9_.~-])',function(c) return string.format('%%%02X',c:byte()) end))
end
local function byteLess(a,b)
    for i=1,math.min(#a,#b) do if a:byte(i)~=b:byte(i) then return a:byte(i)<b:byte(i) end end
    return #a<#b
end
local active = {queued=true,attempting=true,retrying=true,throttled=true}
local terminal = {added=true,moderation_submitted=true,delivery_uncertain=true,needs_attention=true,cancelled=true}
local reasons = {}
for name in ('membership_already_present added moderation_submission_recorded post_dispatch_result_unavailable '
    .. 'temporary_flickr_failure flickr_group_limit photo_unavailable_or_ineligible group_unavailable_or_ineligible '
    .. 'request_policy_rejected user_flickr_reauthorization_required deployment_repair_required safe_transport_failure cancelled'):gmatch('%S+') do
    reasons[name] = true
end
local function attentionAction(reason)
    if reason == 'user_flickr_reauthorization_required' then return 'reauthorize_flickr' end
    if reason == 'deployment_repair_required' then return 'repair_deployment' end
    if reason == 'photo_unavailable_or_ineligible' or reason == 'group_unavailable_or_ineligible'
        or reason == 'request_policy_rejected' then return 'correct_future_selection' end
end
function Client.validateIntent(v, null, binding)
    if null == nil or not exact(v,'fgaSubmissionIntentId fgaPhotoBindingId flickrPhotoId flickrGroupId '
        .. 'groupDisplayName groupDisplayNameObservedAt state stateRevision createdAt stateChangedAt terminalAt '
        .. 'attemptCount queue lastOutcome permanentSubmissionBlock attention') then return false end
    for _,key in ipairs({'fgaSubmissionIntentId','fgaPhotoBindingId','flickrPhotoId','flickrGroupId'}) do
        if not id(v[key]) then return false end
    end
    if binding and (v.fgaPhotoBindingId ~= binding.fgaPhotoBindingId or v.flickrPhotoId ~= binding.flickrPhotoId) then return false end
    if not active[v.state] and not terminal[v.state] or not integer(v.stateRevision,1)
        or not integer(v.attemptCount) or not timestamp(v.createdAt) or not timestamp(v.stateChangedAt)
        or v.stateChangedAt < v.createdAt then return false end
    if v.groupDisplayName == null then
        if v.groupDisplayNameObservedAt ~= null then return false end
    elseif type(v.groupDisplayName) ~= 'string' or #v.groupDisplayName > 4096
        or v.groupDisplayName:find('[%z\1-\31\127]') or not timestamp(v.groupDisplayNameObservedAt) then return false end
    if active[v.state] then
        local q = v.queue
        if v.terminalAt ~= null or not exact(q,'isPartitionHead activeAheadInPartition nextWorkNotBefore holds')
            or type(q.isPartitionHead) ~= 'boolean' or not integer(q.activeAheadInPartition)
            or q.isPartitionHead ~= (q.activeAheadInPartition == 0) or not array(q.holds,2) then return false end
        local seen = {}
        for _,hold in ipairs(q.holds) do
            if seen[hold] or hold ~= 'user_flickr_write_gate_paused' and hold ~= 'deployment_flickr_write_gate_paused' then return false end
            seen[hold] = true
        end
        if q.isPartitionHead and v.state ~= 'attempting' then
            if not timestamp(q.nextWorkNotBefore) then return false end
        elseif q.nextWorkNotBefore ~= null then return false end
    elseif v.queue ~= null or not timestamp(v.terminalAt) or v.terminalAt ~= v.stateChangedAt then return false end
    local outcome = v.lastOutcome
    if outcome ~= null and (not exact(outcome,'reasonCode flickrResultCode observedAt correlationId')
        or not reasons[outcome.reasonCode] or not timestamp(outcome.observedAt) or not id(outcome.correlationId)
        or outcome.flickrResultCode ~= null and not integer(outcome.flickrResultCode)) then return false end
    local block = v.permanentSubmissionBlock
    local expected = v.state == 'moderation_submitted' and 'moderation_submission_recorded'
        or v.state == 'delivery_uncertain' and 'delivery_uncertain' or nil
    if expected then
        if not exact(block,'reasonCode createdAt') or block.reasonCode ~= expected or not timestamp(block.createdAt)
            or outcome == null or outcome.reasonCode ~= (v.state == 'moderation_submitted'
                and 'moderation_submission_recorded' or 'post_dispatch_result_unavailable') then return false end
    elseif block ~= null then return false end
    if v.state == 'added' and (outcome == null or outcome.reasonCode ~= 'added'
        and outcome.reasonCode ~= 'membership_already_present') then return false end
    if v.state == 'needs_attention' or v.state == 'delivery_uncertain' then
        local a = v.attention
        if outcome == null or not exact(a,'kind reasonCode occurredAt operatorAction fgaResubmissionAllowed')
            or a.kind ~= v.state or a.reasonCode ~= outcome.reasonCode or a.occurredAt ~= v.terminalAt
            or a.fgaResubmissionAllowed ~= false or a.operatorAction ~= (v.state == 'delivery_uncertain'
                and 'inspect_flickr_no_fga_resubmit' or attentionAction(outcome.reasonCode)) then return false end
    elseif v.attention ~= null then return false end
    return true
end
local function gatesValid(gates,null,count)
    if not array(gates,2) or #gates ~= 2 then return false end
    local seen = {}
    for _,g in ipairs(gates) do
        if not exact(g,'scope state revision pausedAt reasonCode affectedActiveIntentCount')
            or g.scope ~= 'user' and g.scope ~= 'deployment' or seen[g.scope]
            or not integer(g.revision,1) or not integer(g.affectedActiveIntentCount) then return false end
        seen[g.scope] = true
        if g.state == 'enabled' then
            if g.pausedAt ~= null or g.reasonCode ~= null or g.affectedActiveIntentCount ~= 0 then return false end
        elseif g.state == 'paused' then
            if not timestamp(g.pausedAt) or g.affectedActiveIntentCount ~= count
                or g.reasonCode ~= 'operator_review_required' and g.reasonCode ~= 'user_flickr_reauthorization_required'
                and g.reasonCode ~= 'deployment_repair_required' then return false end
        else return false end
    end
    return true
end
function Client.presentation(v, observedAt, null)
    if not Client.validateIntent(v,null) or not timestamp(observedAt) then return nil,'response_invalid' end
    local text, code = nil, 'existing_submission_intent'
    if v.state == 'moderation_submitted' then
        code='moderation_submission_protected'
        text='Flickr recorded a moderation submission for this photo and group. The final moderator decision is unknown. FGA components will not submit this exact pair again.'
    elseif v.state == 'delivery_uncertain' then
        code='delivery_uncertain_protected'
        text='FGA records cannot prove whether Flickr received the add request. To avoid a duplicate request, FGA components will not submit this exact pair again. Inspect Flickr manually.'
    elseif active[v.state] then
        local q=v.queue
        if #q.holds > 0 then text='Flickr writes are paused for review. Queue order is preserved.'
        elseif v.state == 'attempting' then text='Work has started for this group request.'
        elseif not q.isPartitionHead then text='Waiting behind '..q.activeAheadInPartition..' earlier requests for this Flickr group.'
        elseif q.nextWorkNotBefore <= observedAt then text='Waiting for the next worker opportunity.'
        elseif v.state == 'throttled' then text="Flickr's group limit was reached. Eligible for another check after "..q.nextWorkNotBefore..'.'
        elseif v.state == 'retrying' then text='Eligible for a safe retry after '..q.nextWorkNotBefore..'.'
        else text='Waiting for the next worker opportunity.' end
    elseif v.state == 'added' then text='Flickr confirmed the photo was in this group when the request was processed.'
    elseif v.state == 'cancelled' then text='This retained request was cancelled. No Flickr removal is implied.'
    elseif v.attention.operatorAction == 'reauthorize_flickr' then text='This request stopped because Flickr authorization needs repair. Repairing the connection will not resubmit this intent.'
    elseif v.attention.operatorAction == 'repair_deployment' then text='This request stopped because the deployment needs repair. Repairing the deployment will not resubmit this intent.'
    else text='This request needs attention. Correct future selections or inspect Flickr manually; this intent will not retry automatically.' end
    return {code=code,text=text,readOnly=true}
end
local function retryAfter(headers)
    local found
    for _,h in pairs(headers) do
        if type(h)=='table' and type(h.field)=='string' and h.field:lower()=='retry-after' then
            if found or type(h.value)~='string' or not h.value:match('^%d+$') or #h.value>6 then return nil end
            found=tonumber(h.value)
            if found<1 then return nil end
        end
    end
    return found
end
local function traversal(d,binding,pacing)
    local result,seenIds,seenGroups,cursor,previous = {state='complete',intents={},
        fgaPhotoBindingId=binding.fgaPhotoBindingId,flickrPhotoId=binding.flickrPhotoId}
    seenIds,seenGroups={},{}
    for pageNumber=1,Client.MAX_PAGES do
        if d.cancelled and d.cancelled() then return nil,'cancelled' end
        -- One collection reader is coalesced by the owner. Honor sustained
        -- admission throughout pagination, including the verification pass.
        if pacing.reads>0 then
            local delay=pacing.nextDelay or 5
            pacing.nextDelay=nil
            for _=1,delay do
                if d.cancelled and d.cancelled() then return nil,'cancelled' end
                d.sleep(1) -- Yielding SDK boundary; never raw Lua 5.1 pcall.
                if d.cancelled and d.cancelled() then return nil,'cancelled' end
            end
        end
        local path='/api/v001/group-submission-intents?view=history&page_size=100&photo_binding_id='..escape(binding.fgaPhotoBindingId)
        if cursor then path=path..'&before_created_at='..escape(cursor.beforeCreatedAt)..'&before_intent_id='..escape(cursor.beforeIntentId) end
        -- This injected call may yield. Never use raw Lua 5.1 pcall around it.
        pacing.reads=pacing.reads+1
        local body,headers=d.request('GET',path)
        if d.cancelled and d.cancelled() then return nil,'cancelled' end
        if type(headers)~='table' then return nil,'unavailable' end
        if headers.status~=200 then
            return nil,headers.status==401 and 'authentication_unconfirmed' or 'unavailable',retryAfter(headers)
        end
        if type(body)~='string' or #body>Client.MAX_RESPONSE_BYTES or not strictJson(body,d.decode) then return nil,'response_invalid' end
        local ok,page=pcall(d.decode,body)
        local null=d.jsonNull
        if not ok or not exact(page,'schemaVersion observedAt view pageSize photoBindingId summary intents nextPage recommendedPollAfterSeconds')
            or page.schemaVersion~=1 or not timestamp(page.observedAt) or page.view~='history' or page.pageSize~=100
            or page.photoBindingId~=binding.fgaPhotoBindingId or not array(page.intents,100)
            or page.recommendedPollAfterSeconds~=null and page.recommendedPollAfterSeconds~=15
                and page.recommendedPollAfterSeconds~=60 then return nil,'response_invalid' end
        local s=page.summary
        if not exact(s,'activeIntentCount activePartitionCount attentionIntentCount oldestActiveEnqueuedAt writeGates')
            or not integer(s.activeIntentCount) or not integer(s.activePartitionCount) or not integer(s.attentionIntentCount)
            or s.activePartitionCount>s.activeIntentCount or not gatesValid(s.writeGates,null,s.activeIntentCount)
            or (s.activeIntentCount==0 and s.oldestActiveEnqueuedAt~=null)
            or (s.activeIntentCount>0 and not timestamp(s.oldestActiveEnqueuedAt)) then return nil,'response_invalid' end
        local paused=false
        for _,g in ipairs(s.writeGates) do if g.state=='paused' then paused=true end end
        local poll=s.activeIntentCount==0 and null or paused and 60 or 15
        if page.recommendedPollAfterSeconds~=poll then return nil,'response_invalid' end
        if result.summary and (not same(result.summary,s) or result.recommendedPollAfterSeconds~=poll) then return nil,'status_changed' end
        if result.observedAt and page.observedAt<result.observedAt then return nil,'status_changed' end
        result.summary,result.observedAt,result.recommendedPollAfterSeconds=s,page.observedAt,poll
        for _,v in ipairs(page.intents) do
            if not Client.validateIntent(v,null,binding) or seenIds[v.fgaSubmissionIntentId] or seenGroups[v.flickrGroupId]
                or previous and (v.createdAt>previous.createdAt or v.createdAt==previous.createdAt
                    and not byteLess(v.fgaSubmissionIntentId,previous.fgaSubmissionIntentId)) then return nil,'response_invalid' end
            if active[v.state] then
                local holds={}
                for _,g in ipairs(s.writeGates) do if g.state=='paused' then holds[#holds+1]=g.scope..'_flickr_write_gate_paused' end end
                table.sort(holds)
                if not same(holds,v.queue.holds) then return nil,'response_invalid' end
            end
            if v.stateChangedAt>page.observedAt then return nil,'response_invalid' end
            seenIds[v.fgaSubmissionIntentId],seenGroups[v.flickrGroupId]=true,true
            result.intents[#result.intents+1],previous=v,v
            if #result.intents>Client.MAX_INTENTS then return nil,'response_invalid' end
        end
        result.requestCount=pageNumber
        if page.nextPage==null then
            local count,attention,oldest=0,0,nil
            for _,v in ipairs(result.intents) do
                if active[v.state] then count=count+1; if not oldest or v.createdAt<oldest then oldest=v.createdAt end end
                if v.state=='needs_attention' or v.state=='delivery_uncertain' then attention=attention+1 end
            end
            if count~=s.activeIntentCount or attention~=s.attentionIntentCount
                or (oldest or null)~=s.oldestActiveEnqueuedAt then return nil,'status_changed' end
            return result
        end
        if #page.intents~=100 or not exact(page.nextPage,'beforeCreatedAt beforeIntentId')
            or page.nextPage.beforeCreatedAt~=previous.createdAt
            or page.nextPage.beforeIntentId~=previous.fgaSubmissionIntentId then return nil,'response_invalid' end
        cursor=page.nextPage
    end
    return nil,'unavailable'
end
function Client.history(d,binding,prior)
    local function failed(reason,delay)
        return nil,reason,{state='unavailable',stale=prior~=nil,previous=prior,reason=reason,
            retryAfterSeconds=delay,minimumRefreshAfterSeconds=math.max(60,delay or 0)}
    end
    if type(d)~='table' or d.jsonNull==nil or type(d.request)~='function' or type(d.decode)~='function'
        or type(d.sleep)~='function'
        or type(binding)~='table' or not id(binding.fgaPhotoBindingId) or not id(binding.flickrPhotoId) then return failed('invalid_request') end
    local pacing={reads=0}
    local first,reason,delay=traversal(d,binding,pacing)
    if not first then return failed(reason,delay) end
    -- The server has keyset pages but no snapshot token. Re-read from page one,
    -- rejecting transitions rather than publishing a mixture of observations.
    local second
    -- Starting the verification traversal is another collection refresh. Honor
    -- the server's minimum poll interval even though no partial data is shown.
    pacing.nextDelay=first.recommendedPollAfterSeconds~=d.jsonNull
        and first.recommendedPollAfterSeconds or 5
    second,reason,delay=traversal(d,binding,pacing)
    if not second then return failed(reason,delay) end
    if not same(first.intents,second.intents) or not same(first.summary,second.summary)
        or first.recommendedPollAfterSeconds~=second.recommendedPollAfterSeconds
        or second.observedAt<first.observedAt then return failed('status_changed') end
    if prior and prior.fgaPhotoBindingId==binding.fgaPhotoBindingId and prior.flickrPhotoId==binding.flickrPhotoId then
        if not timestamp(prior.observedAt) or second.observedAt<prior.observedAt then return failed('status_changed') end
        if type(prior.summary)~='table' or type(prior.summary.writeGates)~='table' then return failed('status_changed') end
        local gates={}
        for _,g in ipairs(second.summary.writeGates) do gates[g.scope]=g end
        for _,g in ipairs(prior.summary.writeGates) do
            local current=gates[g.scope]
            if not current or not integer(g.revision,1) or current.revision<g.revision
                or current.revision==g.revision and (current.state~=g.state
                    or current.pausedAt~=g.pausedAt or current.reasonCode~=g.reasonCode) then return failed('status_changed') end
        end
        local known={}
        for _,v in ipairs(second.intents) do known[v.fgaSubmissionIntentId]=v end
        for _,v in ipairs(prior.intents or {}) do
            local current=known[v.fgaSubmissionIntentId]
            if not current or current.flickrGroupId~=v.flickrGroupId or current.createdAt~=v.createdAt
                or current.stateRevision<v.stateRevision or not same(current.permanentSubmissionBlock,v.permanentSubmissionBlock)
                    and v.permanentSubmissionBlock~=d.jsonNull
                or current.stateRevision==v.stateRevision and (current.state~=v.state
                    or current.stateChangedAt~=v.stateChangedAt) then return failed('status_changed') end
        end
    end
    second.requestCount=first.requestCount+second.requestCount
    if second.recommendedPollAfterSeconds~=d.jsonNull then
        second.minimumRefreshAfterSeconds=math.max(second.recommendedPollAfterSeconds,second.requestCount*5)
    end
    return second
end
Client.PRODUCTION_QUALIFIED=false
return Client
