-- Bounded private selection and immutable handoff store. Not registered.
local json = require "dkjson"
local Module = {}
Module.SELECTION_FIELD = "groupAdditionSelections"
Module.OUTBOX_FIELD = "groupAdditionOutboxV1"
Module.MAX_SELECTION_ENTRIES = 64
Module.MAX_SELECTION_BYTES = 512 * 1024
Module.MAX_OUTBOX_ENTRIES = 128
Module.MAX_OUTBOX_BYTES = 1024 * 1024
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
local function uuid(value)
    return type(value) == "string" and #value == 36
        and string.match(value, "^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$") ~= nil
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
local scopeFields = {publishServiceLocalId=true,publishedCollectionLocalId=true,photoUuid=true}
local scopeRequired = {"publishServiceLocalId","publishedCollectionLocalId","photoUuid"}
local function validScope(scope)
    return exact(scope,scopeFields,scopeRequired) and integer(scope.publishServiceLocalId,1)
        and integer(scope.publishedCollectionLocalId,1) and uuid(scope.photoUuid)
end
local function sameScope(a,b)
    return a.publishServiceLocalId == b.publishServiceLocalId
        and a.publishedCollectionLocalId == b.publishedCollectionLocalId and a.photoUuid == b.photoUuid
end
local function scopeLess(a,b)
    return a.publishServiceLocalId < b.publishServiceLocalId
        or (a.publishServiceLocalId == b.publishServiceLocalId
            and a.publishedCollectionLocalId < b.publishedCollectionLocalId)
end
local function validGroups(groups, choice, persisted)
    if not array(groups,60,persisted) then return false end
    if choice ~= (#groups == 0 and "none" or "groups") then return false end
    local previous
    for _,id in ipairs(groups) do
        if not opaque(id) or (previous and not byteLess(previous,id)) then return false end
        previous = id
    end
    return true
end
local entryFields = {publishServiceLocalId=true,publishedCollectionLocalId=true,photoUuid=true,
    selectionRevision=true,choice=true,flickrGroupIds=true}
local entryRequired = {"publishServiceLocalId","publishedCollectionLocalId","photoUuid",
    "selectionRevision","choice","flickrGroupIds"}
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
local handoffFields = clone(entryFields)
handoffFields.handoffId, handoffFields.outboxRevision, handoffFields.state, handoffFields.binding = true,true,true,true
handoffFields.submissions=true
local handoffRequired = clone(entryRequired)
for _,key in ipairs({"handoffId","outboxRevision","state"}) do table.insert(handoffRequired,key) end
local function validEntry(entry, fields, required, minimum)
    return exact(entry,fields,required) and integer(entry.publishServiceLocalId,1)
        and integer(entry.publishedCollectionLocalId,1) and uuid(entry.photoUuid)
        and integer(entry.selectionRevision,minimum) and validGroups(entry.flickrGroupIds,entry.choice,true)
        and (entry.selectionRevision > 0 or entry.choice == "none")
end
local function validDocument(document, outbox, photoUuid)
    local name = outbox and "records" or "entries"
    local maximum = outbox and Module.MAX_OUTBOX_ENTRIES or Module.MAX_SELECTION_ENTRIES
    if not exact(document,{schemaVersion=true,[name]=true},{"schemaVersion",name})
        or document.schemaVersion ~= 1 or not array(document[name],maximum,true) then return false end
    local previous, ids = nil, {}
    for _,entry in ipairs(document[name]) do
        if not validEntry(entry,outbox and handoffFields or entryFields,
            outbox and handoffRequired or entryRequired,outbox and 0 or 1) then return false end
        if outbox then
            if not opaque(entry.handoffId) or ids[entry.handoffId]
                or not integer(entry.outboxRevision,1)
                or (entry.state ~= "prepared" and entry.state ~= "acknowledged")
                or entry.outboxRevision ~= (entry.state == "prepared" and 1 or 2)
                or (entry.binding ~= nil and not validBinding(entry.binding))
                or (entry.state == "prepared" and entry.submissions ~= nil)
                or (entry.state == "acknowledged" and entry.choice == "groups"
                    and not validSubmissions(entry.submissions,entry.flickrGroupIds,true))
                or (entry.choice == "none" and entry.submissions ~= nil)
                or (previous and not byteLess(previous.handoffId,entry.handoffId)) then return false end
            ids[entry.handoffId] = true
        elseif entry.photoUuid ~= photoUuid or (previous and not scopeLess(previous,entry)) then
            return false
        end
        previous = entry
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
local function readDocument(raw, outbox, photoUuid)
    if raw == nil then return {schemaVersion=1,[outbox and "records" or "entries"]=newArray()} end
    local bound=outbox and Module.MAX_OUTBOX_BYTES or Module.MAX_SELECTION_BYTES
    if type(raw) ~= "string" or #raw > bound or not strictJson(raw) then return nil end
    local value,_,err=json.decode(raw,1,json.null)
    if err or not validDocument(value,outbox,photoUuid) then return nil end
    return value
end
local function findSelection(document,scope)
    for index,entry in ipairs(document.entries) do
        if sameScope(entry,scope) then return entry,index end
    end
end
local function findHandoff(document,id)
    for _,record in ipairs(document.records) do if record.handoffId == id then return record end end
end
local function groupsEqual(a,b)
    if #a ~= #b then return false end
    for index,id in ipairs(a) do if id ~= b[index] then return false end end
    return true
end
local function normalizeGroups(groups)
    if not array(groups,60,false) then return nil end
    local result=newArray()
    for _,id in ipairs(groups) do if not opaque(id) then return nil end; table.insert(result,id) end
    table.sort(result,byteLess)
    if not validGroups(result,#result == 0 and "none" or "groups",false) then return nil end
    return result
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

function Module.new(options)
    options=options or {}
    local Store={}
    local catalog,photo,plugin=options.catalog,options.photo,options.plugin
    local protect=options.pcall
    local function inScope(scope)
        return validScope(scope) and type(options.activeCatalog) == "function"
            and options.activeCatalog() == catalog and photo:getRawMetadata("uuid") == scope.photoUuid
    end
    local function run(scope,operation,operationCurrent)
        if type(protect) ~= "function" or catalog == nil or photo == nil or plugin == nil
            or not validScope(scope) or (operationCurrent ~= nil and type(operationCurrent) ~= "function") then
            return failure("scope_invalid")
        end
        local function guardedScope()
            return inScope(scope) and (operationCurrent == nil or operationCurrent() == true)
        end
        local result,expectedSelection,expectedOutbox,completed
        local callbackOpen=true
        local ok,gate=protect(function()
            if not guardedScope() then return "scope_invalid" end
            return catalog:withPrivateWriteAccessDo(function()
                -- Fence a callback that unexpectedly runs after a queued/aborted return.
                if not callbackOpen or not guardedScope() then error("scope_invalid") end
                local selectionRaw=photo:getPropertyForPlugin(plugin,Module.SELECTION_FIELD)
                local outboxRaw=catalog:getPropertyForPlugin(plugin,Module.OUTBOX_FIELD)
                local selections=readDocument(selectionRaw,false,scope.photoUuid)
                local outbox=readDocument(outboxRaw,true,scope.photoUuid)
                if not selections or not outbox then result=failure("stored_invalid"); return end
                local selectionChanged,outboxChanged
                result,selectionChanged,outboxChanged=operation(selections,outbox)
                if not result then result=failure("internal_error"); return end
                expectedSelection,expectedOutbox=selectionRaw,outboxRaw
                if selectionChanged then
                    if not validDocument(selections,false,scope.photoUuid) then error("stored_invalid") end
                    expectedSelection=encodeDocument(selections)
                    if #expectedSelection > Module.MAX_SELECTION_BYTES then result=failure("storage_full"); return end
                end
                if outboxChanged then
                    if not validDocument(outbox,true,scope.photoUuid) then error("stored_invalid") end
                    expectedOutbox=encodeDocument(outbox)
                    if #expectedOutbox > Module.MAX_OUTBOX_BYTES then result=failure("storage_full"); return end
                end
                -- All validation/encoding/bounds checks precede either write.
                if not guardedScope() then error("scope_invalid") end
                if selectionChanged then photo:setPropertyForPlugin(plugin,Module.SELECTION_FIELD,expectedSelection) end
                if outboxChanged then catalog:setPropertyForPlugin(plugin,Module.OUTBOX_FIELD,expectedOutbox) end
                completed=true
            end,{timeout=5,asynchronous=false})
        end)
        callbackOpen=false
        if not ok then return failure("storage_unavailable") end
        if gate == "scope_invalid" then return failure("scope_invalid") end
        if gate ~= "executed" then return failure("write_unconfirmed") end
        if not completed then return result or failure("write_unconfirmed") end
        local readOk,matched=protect(function()
            return guardedScope() and photo:getPropertyForPlugin(plugin,Module.SELECTION_FIELD) == expectedSelection
                and catalog:getPropertyForPlugin(plugin,Module.OUTBOX_FIELD) == expectedOutbox
        end)
        if not readOk or not matched then return failure("write_unconfirmed") end
        return result
    end
    function Store:readChoice(scope)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        return run(scope,function(selections)
            return {state="ready",selection=clone(findSelection(selections,scope))}
        end)
    end
    local function addHandoff(scope,selection,outbox,handoffId,binding)
        if not opaque(handoffId) or (binding ~= nil and not validBinding(binding)) then
            return nil,"handoff_invalid"
        end
        if binding ~= nil and (selection == nil or selection.choice == "none") then
            return nil,"choice_invalid"
        end
        if findHandoff(outbox,handoffId) then return nil,"handoff_exists" end
        if #outbox.records >= Module.MAX_OUTBOX_ENTRIES then return nil,"storage_full" end
        local record=clone(selection or scope)
        if not selection then record.selectionRevision,record.choice,record.flickrGroupIds=0,"none",newArray() end
        record.handoffId,record.outboxRevision,record.state=handoffId,1,"prepared"
        record.binding=clone(binding)
        table.insert(outbox.records,record)
        table.sort(outbox.records,function(a,b) return byteLess(a.handoffId,b.handoffId) end)
        return record
    end
    function Store:saveChoice(scope,groups,expectedRevision,handoffId,binding)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        local normalized=normalizeGroups(groups)
        if not normalized or not integer(expectedRevision,0) then return failure("choice_invalid") end
        if binding ~= nil and handoffId == nil then return failure("handoff_invalid") end
        if binding ~= nil then
            if not validBinding(binding) then return failure("handoff_invalid") end
            binding=clone(binding)
        end
        return run(scope,function(selections,outbox)
            local prior,index=findSelection(selections,scope)
            if (prior and prior.selectionRevision or 0) ~= expectedRevision then return failure("revision_conflict") end
            if not prior and #selections.entries >= Module.MAX_SELECTION_ENTRIES then return failure("storage_full") end
            local revision=prior and prior.selectionRevision or 0
            -- Retained outbox revisions prevent an old receipt matching a new edit
            -- after the previous editable entry was consumed (revision ABA).
            for _,record in ipairs(outbox.records) do
                if sameScope(record,scope) then revision=math.max(revision,record.selectionRevision) end
            end
            if revision == MAX_INTEGER then return failure("revision_exhausted") end
            local entry=clone(scope)
            entry.selectionRevision,entry.choice,entry.flickrGroupIds=revision+1,#normalized == 0 and "none" or "groups",normalized
            local handoff,reason
            if handoffId ~= nil then
                handoff,reason=addHandoff(scope,entry,outbox,handoffId,binding)
                if not handoff then return failure(reason) end
            end
            if index then selections.entries[index]=entry else table.insert(selections.entries,entry) end
            table.sort(selections.entries,scopeLess)
            return {state="saved",selection=clone(entry),handoff=clone(handoff)},true,handoff ~= nil
        end)
    end
    function Store:prepare(scope,expectedRevision,handoffId,binding)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        if not integer(expectedRevision,0) then return failure("choice_invalid") end
        if binding ~= nil then
            if not validBinding(binding) then return failure("handoff_invalid") end
            binding=clone(binding)
        end
        return run(scope,function(selections,outbox)
            local entry=findSelection(selections,scope)
            if (entry and entry.selectionRevision or 0) ~= expectedRevision then return failure("revision_conflict") end
            local handoff,reason=addHandoff(scope,entry,outbox,handoffId,binding)
            if not handoff then return failure(reason) end
            return {state="prepared",handoff=clone(handoff)},false,true
        end)
    end
    function Store:readHandoff(scope,handoffId)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        if not opaque(handoffId) then return failure("handoff_invalid") end
        return run(scope,function(_,outbox)
            local handoff=findHandoff(outbox,handoffId)
            if not handoff or not sameScope(handoff,scope) then return failure("handoff_not_found") end
            return {state="ready",handoff=clone(handoff)}
        end)
    end
    function Store:listPending(scope)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        return run(scope,function(_,outbox)
            local handoffs=newArray()
            for _,record in ipairs(outbox.records) do
                if record.state == "prepared" and sameScope(record,scope) then
                    table.insert(handoffs,clone(record))
                end
            end
            return {state="ready",handoffs=handoffs}
        end)
    end
    -- Optional operationCurrent must be a non-yielding current-session read.
    function Store:confirm(scope,handoffId,expectedRevision,ack,operationCurrent)
        if not validScope(scope) then return failure("scope_invalid") end
        scope=clone(scope)
        if not opaque(handoffId) or not integer(expectedRevision,1) then return failure("handoff_invalid") end
        return run(scope,function(selections,outbox)
            local record=findHandoff(outbox,handoffId)
            if not record or not sameScope(record,scope) then return failure("handoff_not_found") end
            if record.outboxRevision ~= expectedRevision then return failure("revision_conflict") end
            if not exact(ack,{kind=true,selectionRevision=true,flickrGroupIds=true,binding=true,submissions=true,
                publicationRecorded=true,albumAttachmentDurable=true},{"kind","selectionRevision","flickrGroupIds"})
                or ack.selectionRevision ~= record.selectionRevision
                or not validGroups(ack.flickrGroupIds,record.choice,false)
                or not groupsEqual(ack.flickrGroupIds,record.flickrGroupIds)
                or not equalBinding(ack.binding,record.binding) then return failure("ack_invalid") end
            if record.choice == "groups" then
                if ack.kind ~= "groups_accepted" or ack.publicationRecorded ~= nil
                    or ack.albumAttachmentDurable ~= nil
                    or not validSubmissions(ack.submissions,record.flickrGroupIds,false) then return failure("ack_invalid") end
            elseif ack.kind ~= "publication_recorded" or ack.publicationRecorded ~= true
                or ack.albumAttachmentDurable ~= true or ack.submissions ~= nil then return failure("ack_invalid") end
            if record.state == "acknowledged" then
                return {state="confirmed",selectionConsumed=false,handoff=clone(record)}
            end
            local current,index=findSelection(selections,scope)
            local consume=current ~= nil and current.selectionRevision == record.selectionRevision
            if consume and (current.choice ~= record.choice
                or not groupsEqual(current.flickrGroupIds,record.flickrGroupIds)) then
                return failure("stored_invalid")
            end
            if consume then table.remove(selections.entries,index) end
            record.state,record.outboxRevision="acknowledged",record.outboxRevision+1
            if ack.submissions then
                record.submissions=newArray()
                for _,row in ipairs(ack.submissions) do table.insert(record.submissions,clone(row)) end
            end
            return {state="confirmed",selectionConsumed=consume,handoff=clone(record)},consume,true
        end,operationCurrent)
    end
    return Store
end
return Module
