-- Pure display assembly. Inputs are complete validated client aggregates, never
-- raw HTTP pages. No row is defaulted to eligible after an unavailable input.
local Eligibility = {PRODUCTION_QUALIFIED=false}
local function id(v)
    return type(v)=='string' and #v>0 and #v<=128 and v:match('^[A-Za-z0-9][A-Za-z0-9@._:%-]*$')~=nil
end
local function dense(v)
    if type(v)~='table' or #v>10000 then return false end
    local count=0
    for k in pairs(v) do if type(k)~='number' or k<1 or k>#v or k~=math.floor(k) then return false end; count=count+1 end
    return count==#v
end
local function groupMap(groups)
    if not dense(groups) then return nil end
    local map={}
    for _,g in ipairs(groups) do
        if type(g)~='table' or not id(g.flickrGroupId) or type(g.displayName)~='string'
            or #g.displayName==0 or #g.displayName>4096 or g.displayName:find('[%z\1-\31\127]')
            or map[g.flickrGroupId] then return nil end
        map[g.flickrGroupId]=g
    end
    return map
end
local copies={
    moderation_submission_protected='Flickr recorded a moderation submission for this photo and group. The final moderator decision is unknown. FGA components will not submit this exact pair again.',
    delivery_uncertain_protected='FGA records cannot prove whether Flickr received the add request. To avoid a duplicate request, FGA components will not submit this exact pair again. Inspect Flickr manually.',
    existing_submission_intent='FGA already has a submission record for this photo and group. View its status; creating another submission is unavailable.',
    eligible_group_addition='Select to ask the FGA group-submission worker to add this photo to the group. Flickr may accept it, queue it for moderation, or refuse it.'}
function Eligibility.assemble(groups,membership,history,statusClient,jsonNull)
    if type(groups)~='table' or groups.state~='complete' or groups.snapshotStatus~='fresh'
        or type(groups.snapshotRevision)~='number' or groups.snapshotRevision<1
        or groups.snapshotRevision~=math.floor(groups.snapshotRevision) then return nil,'selection_data_unavailable' end
    local writable=groupMap(groups.groups)
    if not writable then return nil,'selection_data_unavailable' end
    local members,intents={},{}
    local bound=membership~=nil or history~=nil
    if bound then
        if type(membership)~='table' or type(history)~='table' or history.state~='complete'
            or not id(membership.fgaPhotoBindingId) or not id(membership.flickrPhotoId)
            or membership.fgaPhotoBindingId~=history.fgaPhotoBindingId or membership.flickrPhotoId~=history.flickrPhotoId
            or type(membership.observationRevision)~='number' or membership.observationRevision<1
            or membership.observationRevision~=math.floor(membership.observationRevision)
            or type(membership.observedAt)~='string' or not dense(history.intents)
            or type(statusClient)~='table' or type(statusClient.validateIntent)~='function' or jsonNull==nil then
            return nil,'selection_data_unavailable'
        end
        members=groupMap(membership.groups)
        if not members then return nil,'selection_data_unavailable' end
        local seen={}
        for _,v in ipairs(history.intents) do
            if not statusClient.validateIntent(v,jsonNull,membership) or intents[v.flickrGroupId]
                or seen[v.fgaSubmissionIntentId] then return nil,'selection_data_unavailable' end
            intents[v.flickrGroupId],seen[v.fgaSubmissionIntentId]=v,true
        end
    end
    local all={}
    for key in pairs(writable) do all[key]=true end
    for key in pairs(members) do all[key]=true end
    for key in pairs(intents) do all[key]=true end
    local ids={}
    for key in pairs(all) do ids[#ids+1]=key end
    table.sort(ids,function(a,b)
        for i=1,math.min(#a,#b) do if a:byte(i)~=b:byte(i) then return a:byte(i)<b:byte(i) end end
        return #a<#b
    end)
    local result={state='ready',bound=bound,rows={},eligibleGroups={},eligibleGroupIds={},
        snapshotRevision=groups.snapshotRevision,refreshedAt=groups.refreshedAt}
    if bound then
        result.fgaPhotoBindingId,result.flickrPhotoId=membership.fgaPhotoBindingId,membership.flickrPhotoId
        result.membershipObservedAt,result.statusObservedAt=membership.observedAt,history.observedAt
    end
    for _,key in ipairs(ids) do
        local intent,member=intents[key],members[key]
        local block=intent and intent.permanentSubmissionBlock
        local code
        if block and block~=jsonNull then code=block.reasonCode=='moderation_submission_recorded'
            and 'moderation_submission_protected' or 'delivery_uncertain_protected'
        elseif member then code='current_membership_observed'
        elseif intent then code='existing_submission_intent'
        elseif writable[key] then code='eligible_group_addition'
        else return nil,'selection_data_unavailable' end
        local name=writable[key] and writable[key].displayName or member and member.displayName or key
        local copy=copies[code] or 'Currently in this Flickr group as observed at '..membership.observedAt..'. Membership is read-only in FGA.'
        local row={flickrGroupId=key,displayName=name,code=code,copy=copy,
            readOnly=code~='eligible_group_addition',currentMembershipObserved=member~=nil,
            intent=intent,actions={}}
        if intent then row.actions[#row.actions+1]='view_status' end
        if code=='delivery_uncertain_protected' then row.actions[#row.actions+1]='inspect_flickr' end
        if not row.readOnly then
            row.actions={'select_for_first_add'}
            result.eligibleGroups[#result.eligibleGroups+1]={flickrGroupId=key,displayName=name}
            result.eligibleGroupIds[#result.eligibleGroupIds+1]=key
        end
        result.rows[#result.rows+1]=row
    end
    return result
end
function Eligibility.load(d,binding,prior)
    local function failed()
        return nil,'selection_data_unavailable',{state='unavailable',stale=prior~=nil,previous=prior,
            code='selection_data_unavailable',copy='Group-addition status is unavailable. No FGA component submitted anything. Refresh before selecting groups.'}
    end
    if type(d)~='table' or type(d.loadGroups)~='function' then return failed() end
    local function cancelled() return d.cancelled and d.cancelled()==true end
    if cancelled() then return failed() end
    local groups=d.loadGroups()
    if cancelled() then return failed() end
    local membership,history
    if binding then
        if type(d.loadMemberships)~='function' or type(d.loadHistory)~='function' then return failed() end
        membership=d.loadMemberships(binding)
        if cancelled() or not membership then return failed() end
        history=d.loadHistory(binding)
        if cancelled() or not history then return failed() end
    end
    local result=Eligibility.assemble(groups,membership,history,d.statusClient,d.jsonNull)
    if not result then return failed() end
    if binding and (result.fgaPhotoBindingId~=binding.fgaPhotoBindingId or result.flickrPhotoId~=binding.flickrPhotoId) then return failed() end
    return result
end
return Eligibility
