-- Copyright 2026 Terry Ott. MIT License.
-- Binding-only catalog-private group handoffs. No LrPhoto or registration.
local json = require "dkjson"
local Module = {}
Module.OUTBOX_FIELD = "existingPhotoGroupOutboxV1"
Module.MAX_OUTBOX_ENTRIES = 128
Module.MAX_OUTBOX_BYTES = 1024 * 1024
Module.WORKFLOW = "existing_public_photo"
local MAX_INTEGER = 9007199254740991
local function failure(state) return {state=state} end
local function integer(value, minimum)
    return type(value) == "number" and value >= minimum and value <= MAX_INTEGER
        and value == math.floor(value)
end
local function opaque(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and string.match(value, "^[A-Za-z0-9][A-Za-z0-9@._:%-]*$") ~= nil
end
local function exact(value, fields, required)
    if type(value) ~= "table" or value == json.null then return false end
    for key in pairs(value) do if not fields[key] then return false end end
    for _, key in ipairs(required) do if value[key] == nil then return false end end
    return true
end
local function array(value, maximum, persisted)
    if type(value) ~= "table" or value == json.null or #value > maximum then return false end
    local meta = getmetatable(value)
    if persisted and (type(meta) ~= "table" or meta.__jsontype ~= "array") then return false end
    local count = 0
    for key in pairs(value) do
        if not integer(key, 1) or key > #value then return false end
        count = count + 1
    end
    return count == #value
end
local function newArray() return setmetatable({}, {__jsontype="array"}) end
local function clone(value)
    if value == json.null then return value end
    if type(value) ~= "table" then return value end
    local result = {}
    for key, child in pairs(value) do result[key] = clone(child) end
    return setmetatable(result, getmetatable(value))
end
local function byteLess(left, right)
    for index=1, math.min(#left, #right) do
        local a,b = string.byte(left,index), string.byte(right,index)
        if a ~= b then return a < b end
    end
    return #left < #right
end
local bindingFields = {fgaPhotoBindingId=true,flickrPhotoId=true,verificationRevision=true,
    linkRevision=true,sourceKind=true}
local bindingRequired = {"fgaPhotoBindingId","flickrPhotoId","verificationRevision","linkRevision","sourceKind"}
local function validBinding(binding)
    return exact(binding,bindingFields,bindingRequired) and opaque(binding.fgaPhotoBindingId)
        and opaque(binding.flickrPhotoId) and integer(binding.verificationRevision,1)
        and integer(binding.linkRevision,1) and (binding.sourceKind == "existing_public_flickr_photo"
            or binding.sourceKind == "fga_direct_upload")
end
local function equalBinding(a,b)
    if a == nil or b == nil then return a == b end
    if not validBinding(a) or not validBinding(b) then return false end
    for key in pairs(bindingFields) do if a[key] ~= b[key] then return false end end
    return true
end
local function timestamp(value)
    if type(value) ~= "string" or #value > 40 then return false end
    local year,month,day,hour,minute,second,tail=string.match(value,
        "^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)(.*)$")
    if not year or (tail ~= "Z" and not string.match(tail,"^%.%d+Z$")) then return false end
    year,month,day=tonumber(year),tonumber(month),tonumber(day)
    local days={31,28,31,30,31,30,31,31,30,31,30,31}
    if year % 4 == 0 and (year % 100 ~= 0 or year % 400 == 0) then days[2]=29 end
    return month >= 1 and month <= 12 and day >= 1 and day <= days[month]
        and tonumber(hour) <= 23 and tonumber(minute) <= 59 and tonumber(second) <= 59
end
local states={queued=true,attempting=true,retrying=true,throttled=true,added=true,
    moderation_submitted=true,delivery_uncertain=true,needs_attention=true,cancelled=true}
local function validSubmissions(submissions,groups,persisted)
    if not array(submissions,60,persisted) or #submissions ~= #groups then return false end
    local ids={}
    for index,row in ipairs(submissions) do
        if not exact(row,{fgaSubmissionIntentId=true,flickrGroupId=true,state=true,created=true,
            permanentSubmissionBlock=true},{"fgaSubmissionIntentId","flickrGroupId","state","created","permanentSubmissionBlock"})
            or not opaque(row.fgaSubmissionIntentId) or ids[row.fgaSubmissionIntentId]
            or row.flickrGroupId ~= groups[index] or not states[row.state]
            or type(row.created) ~= "boolean" then return false end
        ids[row.fgaSubmissionIntentId]=true
        local block=row.permanentSubmissionBlock
        local reason=row.state == "moderation_submitted" and "moderation_submission_recorded"
            or row.state == "delivery_uncertain" and "delivery_uncertain" or nil
        if reason then
            if row.created or not exact(block,{reasonCode=true,createdAt=true},{"reasonCode","createdAt"})
                or block.reasonCode ~= reason or not timestamp(block.createdAt) then return false end
        elseif block ~= json.null then return false end
    end
    return true
end
-- Match the strict grammar convention in GroupDiscoveryClient before dkjson
-- decoding, including rejection of duplicate keys after escape decoding.
local function strictJson(body)
    local pos, length = 1, #body
    local function char() return string.sub(body,pos,pos) end
    local function white()
        while char() == " " or char() == "\t" or char() == "\r" or char() == "\n" do pos=pos+1 end
    end
    local function jsonString()
        if char() ~= '"' then return nil end
        local start = pos
        pos = pos + 1
        while pos <= length do
            local current = char()
            if current == '"' then pos=pos+1; return string.sub(body,start,pos-1) end
            if string.byte(current) < 32 then return nil end
            if current == "\\" then
                pos=pos+1
                current=char()
                if current == "u" then
                    if not string.match(string.sub(body,pos+1,pos+4),"^%x%x%x%x$") then return nil end
                    pos=pos+4
                elseif current ~= '"' and current ~= "\\" and current ~= "/" and current ~= "b"
                    and current ~= "f" and current ~= "n" and current ~= "r" and current ~= "t" then return nil end
            end
            pos=pos+1
        end
        return nil
    end
    local function digits()
        local start=pos
        while string.match(char(),"^[0-9]$") do pos=pos+1 end
        return pos > start
    end
    local value
    value=function(depth)
        if depth > 32 then return false end
        white()
        local current=char()
        if current == '"' then return jsonString() ~= nil end
        if current == "{" or current == "[" then
            local object,keys=current == "{",{}
            local finish=object and "}" or "]"
            pos=pos+1
            white()
            if char() == finish then pos=pos+1; return true end
            while true do
                if object then
                    local rawKey=jsonString()
                    if not rawKey then return false end
                    local ok,key=pcall(json.decode,rawKey)
                    if not ok or type(key) ~= "string" or keys[key] then return false end
                    keys[key]=true
                    white()
                    if char() ~= ":" then return false end
                    pos=pos+1
                end
                if not value(depth+1) then return false end
                white()
                if char() == finish then pos=pos+1; return true end
                if char() ~= "," then return false end
                pos=pos+1
                white()
            end
        end
        for _,literal in ipairs({"true","false","null"}) do
            if string.sub(body,pos,pos+#literal-1) == literal then pos=pos+#literal; return true end
        end
        if current == "-" then pos=pos+1 end
        if char() == "0" then pos=pos+1
        elseif string.match(char(),"^[1-9]$") then digits()
        else return false end
        if char() == "." then pos=pos+1; if not digits() then return false end end
        if char() == "e" or char() == "E" then
            pos=pos+1
            if char() == "+" or char() == "-" then pos=pos+1 end
            if not digits() then return false end
        end
        return true
    end
    if not value(1) then return false end
    white()
    return pos == length+1
end
-- dkjson uses Lua 5.1 tostring for numbers, which rounds large safe integers.
-- Its documented custom encoder keeps the JSON codec while preserving exact
-- catalog IDs and revisions. Every number in these validated documents is an integer.
local function encodeDocument(document)
    local function adapt(value)
        if type(value) == "number" then
            return setmetatable({}, {__tojson=function() return string.format("%.0f",value) end})
        end
        if type(value) ~= "table" or value == json.null then return value end
        local result={}
        for key,child in pairs(value) do result[key]=adapt(child) end
        return setmetatable(result,getmetatable(value))
    end
    return json.encode(adapt(document))
end

local scopeFields={installationId=true,fgaPhotoBindingId=true,flickrPhotoId=true,
    linkedFlickrRevision=true,sourceKind=true}
local scopeRequired={"installationId","fgaPhotoBindingId","flickrPhotoId","linkedFlickrRevision","sourceKind"}
local function scopeValues(scope)
    return opaque(scope.installationId) and opaque(scope.fgaPhotoBindingId)
        and opaque(scope.flickrPhotoId) and integer(scope.linkedFlickrRevision,1)
        and (scope.sourceKind == "existing_public_flickr_photo" or scope.sourceKind == "fga_direct_upload")
end
local function validScope(scope)
    return exact(scope,scopeFields,scopeRequired) and scopeValues(scope)
end
local function sameScope(a,b)
    for key in pairs(scopeFields) do if a[key] ~= b[key] then return false end end
    return true
end
local function matchesBinding(scope,binding)
    return validBinding(binding) and binding.fgaPhotoBindingId == scope.fgaPhotoBindingId
        and binding.flickrPhotoId == scope.flickrPhotoId and binding.sourceKind == scope.sourceKind
        and binding.linkRevision == scope.linkedFlickrRevision
end
local function validGroups(groups,persisted)
    if not array(groups,60,persisted) or #groups < 1 then return false end
    local previous
    for _,id in ipairs(groups) do
        if not opaque(id) or (previous and not byteLess(previous,id)) then return false end
        previous=id
    end
    return true
end
local function normalizeGroups(groups)
    if not array(groups,60,false) or #groups < 1 then return nil end
    local result=newArray()
    for _,id in ipairs(groups) do
        if not opaque(id) then return nil end
        table.insert(result,id)
    end
    table.sort(result,byteLess)
    return validGroups(result,false) and result or nil
end
local function groupsEqual(a,b)
    if #a ~= #b then return false end
    for index,id in ipairs(a) do if id ~= b[index] then return false end end
    return true
end
local recordFields=clone(scopeFields)
local recordRequired=clone(scopeRequired)
for _,key in ipairs({"selectionRevision","choice","flickrGroupIds","handoffId","outboxRevision","state","binding","workflow"}) do
    recordFields[key]=true
    table.insert(recordRequired,key)
end
recordFields.submissions=true
local function validDocument(document)
    if not exact(document,{schemaVersion=true,records=true},{"schemaVersion","records"})
        or document.schemaVersion ~= 1 or not array(document.records,Module.MAX_OUTBOX_ENTRIES,true) then return false end
    local previous
    for index,record in ipairs(document.records) do
        if not exact(record,recordFields,recordRequired) or not scopeValues(record)
            or record.workflow ~= Module.WORKFLOW
            or not matchesBinding(record,record.binding) or not integer(record.selectionRevision,1)
            or record.choice ~= "groups" or not validGroups(record.flickrGroupIds,true)
            or not opaque(record.handoffId) or (previous and not byteLess(previous.handoffId,record.handoffId))
            or (record.state ~= "prepared" and record.state ~= "acknowledged")
            or record.outboxRevision ~= (record.state == "prepared" and 1 or 2)
            or (record.state == "prepared" and record.submissions ~= nil)
            or (record.state == "acknowledged" and not validSubmissions(record.submissions,record.flickrGroupIds,true)) then
            return false
        end
        -- Distinct retained records for one exact scope cannot reuse a revision.
        for prior=1,index-1 do
            local other=document.records[prior]
            if sameScope(other,record) and other.selectionRevision == record.selectionRevision then return false end
        end
        previous=record
    end
    return true
end
local function readDocument(raw)
    if raw == nil then return {schemaVersion=1,records=newArray()} end
    if type(raw) ~= "string" or #raw > Module.MAX_OUTBOX_BYTES or not strictJson(raw) then return nil end
    local value,_,err=json.decode(raw,1,json.null)
    return not err and validDocument(value) and value or nil
end
local function latestRecord(document,scope)
    local latest
    for _,record in ipairs(document.records) do
        if sameScope(record,scope) and (not latest or latest.selectionRevision < record.selectionRevision) then latest=record end
    end
    return latest
end
local function findHandoff(document,id)
    for _,record in ipairs(document.records) do if record.handoffId == id then return record end end
end
local function choice(record)
    if not record or record.state ~= "prepared" then return nil end
    local selection=clone(record)
    selection.handoffId,selection.outboxRevision,selection.state,selection.binding,selection.submissions=nil,nil,nil,nil,nil
    return selection
end

function Module.new(options)
    options=options or {}
    local Store={}
    local catalog,plugin,protect=options.catalog,options.plugin,options.pcall
    local function current(scope)
        if type(options.activeCatalog) ~= "function" or options.activeCatalog() ~= catalog
            or type(options.currentIdentity) ~= "function" then return false end
        local identity=options.currentIdentity()
        return exact(identity,{installationId=true,linkedFlickrRevision=true},{"installationId","linkedFlickrRevision"})
            and identity.installationId == scope.installationId
            and identity.linkedFlickrRevision == scope.linkedFlickrRevision
    end
    local function run(scope,operation,operationCurrent)
        if type(protect) ~= "function" or catalog == nil or plugin == nil
            or (options.workflow ~= nil and options.workflow ~= Module.WORKFLOW)
            or (operationCurrent ~= nil and type(operationCurrent) ~= "function") then return failure("scope_invalid") end
        local function guardedCurrent()
            return current(scope) and (operationCurrent == nil or operationCurrent() == true)
        end
        local result,expected,completed
        local callbackOpen=true
        local ok,gate=protect(function()
            if not guardedCurrent() then return "scope_invalid" end
            return catalog:withPrivateWriteAccessDo(function()
                if not callbackOpen or not guardedCurrent() then error("scope_invalid") end
                local raw=catalog:getPropertyForPlugin(plugin,Module.OUTBOX_FIELD)
                local document=readDocument(raw)
                if not document then result=failure("stored_invalid"); return end
                local changed
                result,changed=operation(document)
                if not result then result=failure("internal_error"); return end
                expected=raw
                if changed then
                    if not validDocument(document) then error("stored_invalid") end
                    expected=encodeDocument(document)
                    if #expected > Module.MAX_OUTBOX_BYTES then result=failure("storage_full"); return end
                    if not guardedCurrent() then error("scope_invalid") end
                    catalog:setPropertyForPlugin(plugin,Module.OUTBOX_FIELD,expected)
                end
                completed=true
            end,{timeout=5,asynchronous=false})
        end)
        callbackOpen=false
        if not ok then return failure("storage_unavailable") end
        if gate == "scope_invalid" then return failure("scope_invalid") end
        if gate ~= "executed" then return failure("write_unconfirmed") end
        if not completed then return result or failure("write_unconfirmed") end
        local readOk,matched=protect(function()
            return guardedCurrent() and catalog:getPropertyForPlugin(plugin,Module.OUTBOX_FIELD) == expected
        end)
        return readOk and matched and result or failure("write_unconfirmed")
    end
    function Store:readChoice(scope)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        return run(scope,function(document)
            return {state="ready",selection=choice(latestRecord(document,scope))}
        end)
    end
    function Store:saveChoice(scope,groups,expectedRevision,handoffId,binding)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        local normalized=normalizeGroups(groups)
        if not normalized or not integer(expectedRevision,0) then return failure("choice_invalid") end
        if not opaque(handoffId) or not matchesBinding(scope,binding) then return failure("handoff_invalid") end
        binding=clone(binding)
        return run(scope,function(document)
            local prior=latestRecord(document,scope)
            local expected=prior and prior.state == "prepared" and prior.selectionRevision or 0
            if expectedRevision ~= expected then return failure("revision_conflict") end
            if findHandoff(document,handoffId) then return failure("handoff_exists") end
            if #document.records >= Module.MAX_OUTBOX_ENTRIES then return failure("storage_full") end
            local revision=prior and prior.selectionRevision or 0
            if revision == MAX_INTEGER then return failure("revision_exhausted") end
            local record=clone(scope)
            record.selectionRevision,record.choice,record.flickrGroupIds=revision+1,"groups",normalized
            record.handoffId,record.outboxRevision,record.state,record.binding=handoffId,1,"prepared",binding
            record.workflow=Module.WORKFLOW
            table.insert(document.records,record)
            table.sort(document.records,function(a,b) return byteLess(a.handoffId,b.handoffId) end)
            return {state="saved",selection=choice(record),handoff=clone(record)},true
        end)
    end
    function Store:readHandoff(scope,handoffId)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        if not opaque(handoffId) then return failure("handoff_invalid") end
        return run(scope,function(document)
            local record=findHandoff(document,handoffId)
            if not record or not sameScope(record,scope) then return failure("handoff_not_found") end
            return {state="ready",handoff=clone(record)}
        end)
    end
    function Store:listPending(scope)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        return run(scope,function(document)
            local handoffs=newArray()
            for _,record in ipairs(document.records) do
                if record.state == "prepared" and sameScope(record,scope) then
                    table.insert(handoffs,clone(record))
                end
            end
            return {state="ready",handoffs=handoffs}
        end)
    end
    -- Optional operationCurrent is a non-yielding session fence, evaluated within
    -- the private write callback as well as at entry and exact readback.
    function Store:confirm(scope,handoffId,expectedRevision,ack,operationCurrent)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        if not opaque(handoffId) or not integer(expectedRevision,1) then return failure("handoff_invalid") end
        return run(scope,function(document)
            local record=findHandoff(document,handoffId)
            if not record or not sameScope(record,scope) then return failure("handoff_not_found") end
            if record.outboxRevision ~= expectedRevision then return failure("revision_conflict") end
            if not exact(ack,{kind=true,selectionRevision=true,flickrGroupIds=true,binding=true,submissions=true},
                {"kind","selectionRevision","flickrGroupIds","binding","submissions"})
                or ack.kind ~= "groups_accepted" or ack.selectionRevision ~= record.selectionRevision
                or not validGroups(ack.flickrGroupIds,false) or not groupsEqual(ack.flickrGroupIds,record.flickrGroupIds)
                or not equalBinding(ack.binding,record.binding)
                or not validSubmissions(ack.submissions,record.flickrGroupIds,false) then return failure("ack_invalid") end
            if record.state == "acknowledged" then
                return {state="confirmed",selectionConsumed=false,handoff=clone(record)}
            end
            local latest=latestRecord(document,scope)
            local consumed=latest.selectionRevision == record.selectionRevision
            record.state,record.outboxRevision="acknowledged",record.outboxRevision+1
            record.submissions=newArray()
            for _,row in ipairs(ack.submissions) do table.insert(record.submissions,clone(row)) end
            return {state="confirmed",selectionConsumed=consumed,handoff=clone(record)},true
        end,operationCurrent)
    end
    return Store
end
return Module
