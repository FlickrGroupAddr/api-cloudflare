-- Copyright 2026 Terry Ott. MIT License.
-- Accepted #0083 upload journal. Injected and dormant; no network/render/SDK imports.
local C=require "UploadAttemptCodec"
local N=C.null
local M={STORE_FIELD="uploadAttemptRecoveryStore",PHOTO_FIELD="publishedPhotoCorrelations",
    MAX_RECORDS=256,MAX_RECORD_BYTES=65536,MAX_STORE_BYTES=33554432,
    MAX_PHOTO_ENTRIES=256,MAX_ENTRY_BYTES=16384,MAX_PHOTO_BYTES=8388608}
local fields=C.fields
local function fail(state) return {state=state} end
local scopeFields=fields("publishServiceLocalId fgaPublishServiceId publishedCollectionLocalId photoUuid")
local function scopeValid(v)
    return C.object(v,scopeFields) and C.integer(v.publishServiceLocalId,1)
        and C.opaque(v.fgaPublishServiceId) and C.integer(v.publishedCollectionLocalId,1) and C.uuid(v.photoUuid)
end
local function sameScope(a,b)
    for k in pairs(scopeFields) do if a[k]~=b[k] then return false end end; return true
end
local function scopeLess(a,b)
    if a.publishServiceLocalId~=b.publishServiceLocalId then return a.publishServiceLocalId<b.publishServiceLocalId end
    if a.publishedCollectionLocalId~=b.publishedCollectionLocalId then
        return a.publishedCollectionLocalId<b.publishedCollectionLocalId
    end
    if a.fgaPublishServiceId~=b.fgaPublishServiceId then return C.less(a.fgaPublishServiceId,b.fgaPublishServiceId) end
    return C.less(a.photoUuid,b.photoUuid)
end
local function nullable(value,validator) return value==N or validator(value) end
local function positive(v) return C.integer(v,1) end
local checkpointFields={
    photoProof=fields("state acknowledgedAt fgaPhotoBindingId linkedFlickrRevision verificationRevision"),
    catalogPublication=fields("state acknowledgedAt flickrPhotoId"),
    albumObligation=fields("state acknowledgedAt fgaAlbumBindingId fgaPhotoBindingId albumBindingRevision flickrPhotosetId hostedObligationState"),
    groupHandoff=fields("state acknowledgedAt fgaPhotoBindingId verificationRevision acceptedGroupCount allItemsValidated")}
-- The accepted album contract currently names membership_verified explicitly.
-- Other truthful natural-key admission states must be supplied by its reviewed
-- client validator, never inferred here from a generic HTTP success.
local function albumState(v)
    return v=="membership_verified" or v=="membership_reconciliation_pending" or v=="album_attachment_needs_attention"
end
local function checkpointValid(kind,v,r)
    if v==N then return true end
    if not C.object(v,checkpointFields[kind]) then return false end
    local ack=v.state=="acknowledged"
    if not ack and v.state~="pending" and v.state~="needs_attention" then return false end
    if ack then if not C.time(v.acknowledgedAt) then return false end
    elseif v.acknowledgedAt~=N then return false end
    for k,value in pairs(v) do
        if k~="state" and k~="acknowledgedAt" then
            local valid
            if k=="allItemsValidated" then valid=type(value)=="boolean"
            elseif k=="acceptedGroupCount" then valid=C.integer(value,0) and value<=60
            elseif k=="linkedFlickrRevision" or k=="verificationRevision" or k=="albumBindingRevision" then valid=positive(value)
            elseif k=="hostedObligationState" then valid=albumState(value)
            else valid=C.opaque(value) end
            if not valid and (ack or value~=N) then
                if not (ack and kind=="albumObligation" and k=="flickrPhotosetId" and value==N) then return false end
            end
        end
    end
    if kind=="albumObligation" then
        if (v.fgaAlbumBindingId==N)~=(v.albumBindingRevision==N) then return false end
        if ack and (not C.opaque(v.fgaAlbumBindingId) or not positive(v.albumBindingRevision)) then return false end
        if ack and v.hostedObligationState=="membership_verified" and v.flickrPhotosetId==N then return false end
    end
    if kind=="catalogPublication" and v.flickrPhotoId~=N and v.flickrPhotoId~=r.flickrPhotoId then return false end
    if kind=="groupHandoff" then
        if r.flickrGroupIds==N or #r.flickrGroupIds==0 then return false end
        if ack and (v.acceptedGroupCount~=#r.flickrGroupIds or v.allItemsValidated~=true) then return false end
    end
    if ack and (kind=="albumObligation" or kind=="groupHandoff") then
        local proof=r.photoProof
        if proof==N or proof.state~="acknowledged" or v.fgaPhotoBindingId~=proof.fgaPhotoBindingId
            or (kind=="groupHandoff" and v.verificationRevision~=proof.verificationRevision) then return false end
    end
    return true
end
local phases=fields("prepared authorized superseded_before_invocation cancelled_before_invocation dispatch_may_have_started definitive_rejection returned_id upload_outcome_unknown ambiguity_resolution_pending abandoned_possible_flickr_photo history_untrusted")
local inactive=fields("superseded_before_invocation cancelled_before_invocation definitive_rejection abandoned_possible_flickr_photo")
local attention=fields("history_untrusted upload_outcome_unknown storage_unconfirmed checkpoint_needs_attention")
local recordFields=fields("recordKind attemptNumber recordRevision predecessorAttemptNumber publishServiceLocalId fgaPublishServiceId publishedCollectionLocalId photoUuid selectionRevision selectionKind flickrGroupIds fgaUploadAuthorizationId uploadPhase dispatchMarkedAt flickrPhotoId resultKind photoProof catalogPublication albumObligation groupHandoff createdAt updatedAt attentionCode recoveryDisposition recoveryConfirmedAt")
local function groupValid(groups,kind,persisted)
    if not C.array(groups,60,persisted) then return false end
    if (kind=="groups")~=(#groups>0) then return false end
    local previous
    for _,id in ipairs(groups) do
        if not C.opaque(id) or (previous and not C.less(previous,id)) then return false end; previous=id
    end
    return true
end
local function recordValid(r)
    if not C.object(r,recordFields) or not positive(r.attemptNumber) or not positive(r.recordRevision)
        or not C.integer(r.publishServiceLocalId,1) or not C.opaque(r.fgaPublishServiceId)
        or not positive(r.publishedCollectionLocalId) or not C.uuid(r.photoUuid)
        or not nullable(r.predecessorAttemptNumber,positive)
        or (r.predecessorAttemptNumber~=N and r.predecessorAttemptNumber>=r.attemptNumber)
        or not phases[r.uploadPhase] or not C.time(r.createdAt) or not C.time(r.updatedAt)
        or not nullable(r.fgaUploadAuthorizationId,C.opaque) or not nullable(r.dispatchMarkedAt,C.time)
        or not nullable(r.flickrPhotoId,C.opaque) or (r.attentionCode~=N and not attention[r.attentionCode]) then return false end
    if r.recoveryDisposition==N then if r.recoveryConfirmedAt~=N then return false end
    elseif r.recoveryDisposition~="history_untrusted" and r.recoveryDisposition~="known_photo_reconciliation"
        and r.recoveryDisposition~="deliberate_new_copy" then return false
    elseif not C.time(r.recoveryConfirmedAt) then return false end
    if r.recordKind=="history_attention" then
        if r.selectionKind~="unknown" or r.selectionRevision~=N or r.flickrGroupIds~=N
            or r.fgaUploadAuthorizationId~=N or r.dispatchMarkedAt~=N or r.recoveryDisposition==N
            or (r.uploadPhase~="history_untrusted" and r.uploadPhase~="ambiguity_resolution_pending" and r.uploadPhase~="returned_id"
                and r.uploadPhase~="abandoned_possible_flickr_photo") then return false end
    elseif r.recordKind=="upload_attempt" then
        if r.uploadPhase=="history_untrusted" or (r.selectionKind~="absent" and r.selectionKind~="none" and r.selectionKind~="groups")
            or not groupValid(r.flickrGroupIds,r.selectionKind,true)
            or (r.selectionKind=="absent" and r.selectionRevision~=N)
            or (r.selectionKind~="absent" and not positive(r.selectionRevision)) then return false end
    else return false end
    if r.uploadPhase=="prepared" then
        if r.fgaUploadAuthorizationId~=N or r.dispatchMarkedAt~=N then return false end
    elseif r.uploadPhase=="authorized" or r.uploadPhase=="superseded_before_invocation" or r.uploadPhase=="cancelled_before_invocation" then
        if r.dispatchMarkedAt~=N or (r.uploadPhase=="authorized" and r.fgaUploadAuthorizationId==N) then return false end
    elseif r.recordKind=="upload_attempt" and r.uploadPhase~="abandoned_possible_flickr_photo" then
        if r.fgaUploadAuthorizationId==N or r.dispatchMarkedAt==N then
            if not (r.recoveryDisposition=="known_photo_reconciliation" and r.resultKind=="photographer_assertion"
                and (r.uploadPhase=="ambiguity_resolution_pending" or r.uploadPhase=="returned_id")) then return false end
        end
    end
    if r.uploadPhase=="returned_id" or r.uploadPhase=="ambiguity_resolution_pending" then
        if not C.opaque(r.flickrPhotoId) or (r.resultKind~="returned_upload_id" and r.resultKind~="photographer_assertion") then return false end
        if r.uploadPhase=="ambiguity_resolution_pending" and r.resultKind~="photographer_assertion" then return false end
        if r.photoProof==N or r.catalogPublication==N
            or (r.flickrGroupIds~=N and #r.flickrGroupIds>0 and r.groupHandoff==N) then return false end
    elseif r.uploadPhase=="definitive_rejection" then
        if r.flickrPhotoId~=N or r.resultKind~="definitive_rejection" then return false end
    elseif r.flickrPhotoId~=N or r.resultKind~=N then return false end
    if r.uploadPhase~="returned_id" and r.uploadPhase~="ambiguity_resolution_pending" then
        if r.photoProof~=N or r.catalogPublication~=N or r.groupHandoff~=N then return false end
    end
    if r.recordKind=="history_attention" and (r.uploadPhase=="history_untrusted" or r.uploadPhase=="abandoned_possible_flickr_photo") then
        if r.albumObligation~=N then return false end
    elseif r.albumObligation==N then return false end
    for kind in pairs(checkpointFields) do if not checkpointValid(kind,r[kind],r) then return false end end
    if r.photoProof~=N and r.photoProof.state=="acknowledged" and r.resultKind=="returned_upload_id"
        and (r.catalogPublication==N or r.catalogPublication.state~="acknowledged") then return false end
    if r.catalogPublication~=N and r.catalogPublication.state=="acknowledged" and r.resultKind=="photographer_assertion"
        and (r.photoProof==N or r.photoProof.state~="acknowledged") then return false end
    return #C.encode(r)<=M.MAX_RECORD_BYTES
end
local rootFields=fields("schemaVersion storeRevision nextAttemptNumber recoveryGate attempts")
local gateFields=fields("state gateRevision confirmedAt")
local function rootValid(d)
    if not C.object(d,rootFields) or d.schemaVersion~=1 or not positive(d.storeRevision)
        or not positive(d.nextAttemptNumber) or not C.object(d.recoveryGate,gateFields)
        or not positive(d.recoveryGate.gateRevision) or not nullable(d.recoveryGate.confirmedAt,C.time)
        or (d.recoveryGate.state~="ordinary" and d.recoveryGate.state~="history_untrusted")
        or (d.recoveryGate.state=="history_untrusted" and d.recoveryGate.confirmedAt==N)
        or not C.array(d.attempts,M.MAX_RECORDS,true) then return false end
    local previous=0
    for i,r in ipairs(d.attempts) do
        if not recordValid(r) or r.attemptNumber<=previous or r.attemptNumber>=d.nextAttemptNumber then return false end
        for j=1,i-1 do
            local other=d.attempts[j]
            if r.fgaUploadAuthorizationId~=N and r.fgaUploadAuthorizationId==other.fgaUploadAuthorizationId then return false end
            if sameScope(r,other) and not inactive[r.uploadPhase] and not inactive[other.uploadPhase] then return false end
            if r.predecessorAttemptNumber==other.attemptNumber and not sameScope(r,other) then return false end
        end
        previous=r.attemptNumber
    end
    return #C.encode(d)<=M.MAX_STORE_BYTES
end
local entryFields=fields("attemptNumber predecessorAttemptNumber publishServiceLocalId fgaPublishServiceId publishedCollectionLocalId photoUuid fgaUploadAuthorizationId flickrPhotoId resultKind fgaPhotoBindingId linkedFlickrRevision verificationRevision fgaAlbumBindingId flickrPhotosetId albumBindingRevision hostedObligationState groupHandoffAcknowledged completedAt")
local function entryValid(e)
    if not C.object(e,entryFields) or not positive(e.attemptNumber) or not nullable(e.predecessorAttemptNumber,positive)
        or (e.predecessorAttemptNumber~=N and e.predecessorAttemptNumber>=e.attemptNumber)
        or not positive(e.publishServiceLocalId) or not positive(e.publishedCollectionLocalId) or not C.uuid(e.photoUuid)
        or not C.opaque(e.fgaPublishServiceId) or not nullable(e.fgaUploadAuthorizationId,C.opaque)
        or not C.opaque(e.flickrPhotoId) or not C.opaque(e.fgaPhotoBindingId) or not C.opaque(e.fgaAlbumBindingId)
        or not positive(e.linkedFlickrRevision) or not positive(e.verificationRevision) or not positive(e.albumBindingRevision)
        or not nullable(e.flickrPhotosetId,C.opaque) or not albumState(e.hostedObligationState)
        or (e.hostedObligationState=="membership_verified" and e.flickrPhotosetId==N)
        or (e.resultKind~="returned_upload_id" and e.resultKind~="photographer_assertion")
        or (e.groupHandoffAcknowledged~=true and e.groupHandoffAcknowledged~=N)
        or not C.time(e.completedAt) then return false end
    return #C.encode(e)<=M.MAX_ENTRY_BYTES
end
local function metadataValid(d,photoUuid)
    if not C.object(d,fields("schemaVersion metadataRevision entries")) or d.schemaVersion~=1
        or not C.integer(d.metadataRevision,0) or not C.array(d.entries,M.MAX_PHOTO_ENTRIES,true) then return false end
    local previous
    for _,e in ipairs(d.entries) do
        if not entryValid(e) or e.photoUuid~=photoUuid or (previous and not scopeLess(previous,e)) then return false end
        previous=e
    end
    return #C.encode(d)<=M.MAX_PHOTO_BYTES
end
local function blankRoot()
    return {schemaVersion=1,storeRevision=1,nextAttemptNumber=1,
        recoveryGate={state="ordinary",gateRevision=1,confirmedAt=N},attempts=C.newArray()}
end
local function readRoot(raw)
    if raw==nil then return blankRoot() end
    local d=C.decode(raw,M.MAX_STORE_BYTES); return d and rootValid(d) and d or nil
end
local function readMetadata(raw,uuid)
    if raw==nil then return {schemaVersion=1,metadataRevision=0,entries=C.newArray()} end
    local d=C.decode(raw,M.MAX_PHOTO_BYTES)
    return d and positive(d.metadataRevision) and metadataValid(d,uuid) and d or nil
end
local function findRecord(d,number)
    for _,r in ipairs(d.attempts) do if r.attemptNumber==number then return r end end
end
local function latest(d,scope)
    local result
    for _,r in ipairs(d.attempts) do if sameScope(r,scope) then result=r end end
    return result
end
local function entryFor(d,scope)
    for _,e in ipairs(d.entries) do if sameScope(e,scope) then return e end end
end
local function bump(d,r,now)
    if d.storeRevision==C.MAX_INTEGER or (r and r.recordRevision==C.MAX_INTEGER) then return false end
    d.storeRevision=d.storeRevision+1
    if r then r.recordRevision=r.recordRevision+1; r.updatedAt=now end
    return true
end
local function checkpoint(kind,now,values)
    local result={}
    for k in pairs(checkpointFields[kind]) do result[k]=N end
    result.state="pending"
    if values then for k,v in pairs(values) do result[k]=v end end
    if now then result.state="acknowledged"; result.acknowledgedAt=now end
    return result
end
local function knownResult(r,photoId,resultKind)
    r.flickrPhotoId,r.resultKind=photoId,resultKind
    r.photoProof=checkpoint("photoProof")
    r.catalogPublication=checkpoint("catalogPublication",nil,{flickrPhotoId=photoId})
    if r.flickrGroupIds~=N and #r.flickrGroupIds>0 then r.groupHandoff=checkpoint("groupHandoff") end
end
local expectFields=fields("storeRevision gateRevision attemptNumber recordRevision metadataRevision")
local function expectValid(e)
    return C.object(e,expectFields) and positive(e.storeRevision) and positive(e.gateRevision)
        and C.integer(e.metadataRevision,0) and nullable(e.attemptNumber,positive) and nullable(e.recordRevision,positive)
        and ((e.attemptNumber==N)==(e.recordRevision==N))
end
local function fence(d,p,r)
    return {storeRevision=d.storeRevision,gateRevision=d.recoveryGate.gateRevision,
        metadataRevision=p.metadataRevision,attemptNumber=r and r.attemptNumber or N,
        recordRevision=r and r.recordRevision or N}
end
function M.new(options)
    options=options or {}
    local S={}
    local catalog,plugin,token=options.catalog,options.plugin,options.activationToken
    local protect=options.pcall
    local memoryRecovery=false
    local permissions={}
    local function current(scope,number)
        return catalog~=nil and plugin~=nil and token~=nil and type(options.activeCatalog)=="function"
            and options.activeCatalog()==catalog and type(options.currentActivation)=="function"
            and options.currentActivation()==token and type(options.isOwner)=="function"
            and options.isOwner(scope,number)==true
    end
    local function photoCurrent(photo,scope)
        return photo~=nil and photo:getRawMetadata("uuid")==scope.photoUuid
            and catalog:findPhotoByUuid(scope.photoUuid)==photo
    end
    -- All reads happen inside the same synchronous private catalog gate. The
    -- injectable SDK pcall may yield while awaiting it; callbacks never yield.
    local function run(scope,photo,expected,now,operation,allowRecovery)
        if not scopeValid(scope) or type(protect)~="function" or not C.time(now)
            or (expected~=nil and not expectValid(expected)) then return fail("scope_invalid") end
        scope=C.clone(scope); expected=C.clone(expected)
        local result,rawExpected,photoExpected,completed
        local open=true
        local ok,status=protect(function()
            if not current(scope,expected and expected.attemptNumber) or not photoCurrent(photo,scope) then return "scope_invalid" end
            return catalog:withPrivateWriteAccessDo(function()
                if not open or not current(scope,expected and expected.attemptNumber) or not photoCurrent(photo,scope) then error("scope_invalid") end
                local raw=catalog:getPropertyForPlugin(plugin,M.STORE_FIELD)
                local photoRaw=photo:getPropertyForPlugin(plugin,M.PHOTO_FIELD)
                local d,p=readRoot(raw),readMetadata(photoRaw,scope.photoUuid)
                if not d then memoryRecovery=true; result=fail("stored_invalid"); return end
                if not p then result=fail("photo_metadata_invalid"); return end
                local r=expected and expected.attemptNumber~=N and findRecord(d,expected.attemptNumber) or nil
                if expected and (expected.storeRevision~=d.storeRevision or expected.gateRevision~=d.recoveryGate.gateRevision
                    or expected.metadataRevision~=p.metadataRevision or (expected.attemptNumber~=N and
                        (not r or not sameScope(r,scope) or r.recordRevision~=expected.recordRevision))) then
                    result=fail("revision_conflict"); return
                end
                if not allowRecovery and (memoryRecovery or d.recoveryGate.state=="history_untrusted") then
                    -- Explicit per-photo recovery disposition is the only exception.
                    if not r or (r.recoveryDisposition~="known_photo_reconciliation" and r.recoveryDisposition~="deliberate_new_copy") then
                        result=fail("history_untrusted"); return
                    end
                end
                local changed,photoChanged
                result,changed,photoChanged=operation(d,p,r,scope)
                if not result then error("internal_error") end
                rawExpected,photoExpected=raw,photoRaw
                if changed then
                    if not rootValid(d) or not metadataValid(p,scope.photoUuid) then error("transition_invalid") end
                    rawExpected=C.encode(d)
                    if photoChanged then photoExpected=C.encode(p) end
                    if not current(scope,expected and expected.attemptNumber) or not photoCurrent(photo,scope) then error("scope_invalid") end
                    if photoChanged then photo:setPropertyForPlugin(plugin,M.PHOTO_FIELD,photoExpected) end
                    catalog:setPropertyForPlugin(plugin,M.STORE_FIELD,rawExpected)
                end
                result.fence=result.fence or fence(d,p,r)
                if result.successor then result.successorFence=fence(d,p,result.successor) end
                completed=true
            end,{timeout=5,asynchronous=false})
        end)
        open=false
        if not ok then return fail("storage_unavailable") end
        if status=="scope_invalid" then return fail("scope_invalid") end
        if status~="executed" then return fail("write_unconfirmed") end
        if not completed then return result or fail("write_unconfirmed") end
        local readOk,matched=protect(function()
            return current(scope,expected and expected.attemptNumber) and photoCurrent(photo,scope)
                and catalog:getPropertyForPlugin(plugin,M.STORE_FIELD)==rawExpected
                and photo:getPropertyForPlugin(plugin,M.PHOTO_FIELD)==photoExpected
        end)
        return readOk and matched and result or fail("write_unconfirmed")
    end
    local function remote(photo)
        if type(options.readRemoteId)~="function" then error("remote_id_reader_required") end
        local id=options.readRemoteId(photo)
        if id==nil or id==N then return nil end
        if not C.opaque(id) then return false end
        return id
    end
    function S:inspect(scope,photo,now,number)
        if number~=nil and not positive(number) then return fail("scope_invalid") end
        return run(scope,photo,nil,now,function(d,p)
            local r=number and findRecord(d,number) or latest(d,scope)
            if r and not sameScope(r,scope) then return fail("scope_invalid") end
            local e=entryFor(p,scope)
            local id=remote(photo)
            local remoteConflict=id==false or (id and (not e or e.flickrPhotoId~=id)
                and (not r or r.flickrPhotoId~=id))
            local classification="unpublished"
            if remoteConflict then
                memoryRecovery=true
                classification="catalog_repair_required"
                if d.recoveryGate.state~="history_untrusted" then
                    if d.recoveryGate.gateRevision==C.MAX_INTEGER or not bump(d,nil,now) then return fail("counter_exhausted") end
                    d.recoveryGate={state="history_untrusted",gateRevision=d.recoveryGate.gateRevision+1,confirmedAt=now}
                    return {state="ready",classification=classification,record=r and C.clone(r) or nil,
                        correlation=e and C.clone(e) or nil,gate=C.clone(d.recoveryGate),fence=fence(d,p,r)},true
                end
            elseif memoryRecovery or d.recoveryGate.state=="history_untrusted" then classification="history_untrusted"
            elseif r then classification=r.uploadPhase=="dispatch_may_have_started" and "upload_outcome_unknown" or r.uploadPhase
            elseif e then classification="published_correlation" end
            return {state="ready",classification=classification,record=r and C.clone(r) or nil,
                correlation=e and C.clone(e) or nil,gate=C.clone(d.recoveryGate),fence=fence(d,p,r)}
        end,true)
    end
    -- Target metadata reservations derive from admitted full records. Fixed
    -- worst-case reservations cannot be consumed by later admissions.
    local function capacity(d,p,scope)
        if #d.attempts>=M.MAX_RECORDS or d.nextAttemptNumber==C.MAX_INTEGER or d.storeRevision==C.MAX_INTEGER then return false end
        local reserved={}
        local count=#p.entries
        local function add(s)
            if s.photoUuid~=scope.photoUuid or entryFor(p,s) then return end
            local key=string.format("%.0f/%.0f/",s.publishServiceLocalId,s.publishedCollectionLocalId)..s.fgaPublishServiceId
            if not reserved[key] then reserved[key]=true; count=count+1 end
        end
        for _,r in ipairs(d.attempts) do add(r) end; add(scope)
        return count<=M.MAX_PHOTO_ENTRIES and M.MAX_RECORDS*M.MAX_RECORD_BYTES+4096<=M.MAX_STORE_BYTES
            and count*M.MAX_ENTRY_BYTES+4096<=M.MAX_PHOTO_BYTES and p.metadataRevision<C.MAX_INTEGER
    end
    local function allocate(d,scope,selection,album,now,predecessor,disposition)
        local r=C.clone(scope)
        for k in pairs(recordFields) do if r[k]==nil then r[k]=N end end
        r.recordKind="upload_attempt"; r.attemptNumber=d.nextAttemptNumber; r.recordRevision=1
        r.predecessorAttemptNumber=predecessor or N; r.selectionKind=selection.selectionKind
        r.selectionRevision=selection.selectionRevision; r.flickrGroupIds=C.clone(selection.flickrGroupIds)
        setmetatable(r.flickrGroupIds,{__jsontype="array"})
        r.uploadPhase="prepared"; r.createdAt=now; r.updatedAt=now
        r.albumObligation=checkpoint("albumObligation",nil,album)
        if disposition then r.recoveryDisposition=disposition; r.recoveryConfirmedAt=now end
        d.nextAttemptNumber=d.nextAttemptNumber+1; table.insert(d.attempts,r)
        return r
    end
    local function validInputs(selection,album)
        return C.object(selection,fields("selectionRevision selectionKind flickrGroupIds"))
            and (selection.selectionKind=="absent" or selection.selectionKind=="none" or selection.selectionKind=="groups")
            and groupValid(selection.flickrGroupIds,selection.selectionKind,false)
            and ((selection.selectionKind=="absent" and selection.selectionRevision==N)
                or (selection.selectionKind~="absent" and positive(selection.selectionRevision)))
            and C.object(album,fields("fgaAlbumBindingId albumBindingRevision"))
            and nullable(album.fgaAlbumBindingId,C.opaque) and nullable(album.albumBindingRevision,positive)
            and ((album.fgaAlbumBindingId==N)==(album.albumBindingRevision==N))
    end
    function S:prepare(scope,photo,expected,selection,album,now)
        if not expectValid(expected) then return fail("scope_invalid") end
        if not validInputs(selection,album) then return fail("choice_invalid") end
        selection,album=C.clone(selection),C.clone(album)
        return run(scope,photo,expected,now,function(d,p)
            local id=remote(photo)
            if id~=nil or entryFor(p,scope) then return fail("catalog_repair_required") end
            for _,r in ipairs(d.attempts) do if sameScope(r,scope) then return fail("attempt_exists") end end
            if not capacity(d,p,scope) then return fail("storage_full") end
            local r=allocate(d,scope,selection,album,now)
            if not bump(d,nil,now) then return fail("counter_exhausted") end
            return {state="prepared",record=C.clone(r),fence=fence(d,p,r)},true
        end)
    end
    local function update(scope,photo,e,now,op,allow)
        if not expectValid(e) or e.attemptNumber==N then return fail("scope_invalid") end
        return run(scope,photo,e,now,function(d,p,r)
            if not r then return fail("revision_conflict") end
            if d.storeRevision==C.MAX_INTEGER or r.recordRevision==C.MAX_INTEGER then return fail("counter_exhausted") end
            local result,changed,photoChanged=op(d,p,r)
            if changed then bump(d,r,now); result.record=C.clone(r) end
            return result,changed,photoChanged
        end,allow)
    end
    function S:authorize(scope,photo,e,authorizationId,now)
        if not C.opaque(authorizationId) then return fail("correlation_invalid") end
        return update(scope,photo,e,now,function(d,_,r)
            if r.uploadPhase~="prepared" then return fail("transition_invalid") end
            for _,other in ipairs(d.attempts) do
                if other.fgaUploadAuthorizationId==authorizationId then return fail("correlation_invalid") end
            end
            r.fgaUploadAuthorizationId=authorizationId; r.uploadPhase="authorized"
            return {state="authorized"},true
        end)
    end
    function S:markDispatch(scope,photo,e,now)
        local result=update(scope,photo,e,now,function(_,_,r)
            if r.uploadPhase~="authorized" then return fail("transition_invalid") end
            r.uploadPhase="dispatch_may_have_started"; r.dispatchMarkedAt=now
            return {state="dispatch_marked"},true
        end)
        if result.state=="dispatch_marked" then
            local permission={}
            permissions[permission]={scope=C.clone(scope),photo=photo,fence=C.clone(result.fence)}
            result.dispatchPermission=permission
        end
        return result
    end
    function S:takeDispatchPermission(permission,now)
        local held=permissions[permission]; permissions[permission]=nil
        if not held then return fail("dispatch_refused") end
        -- Revalidate the exact confirmed marker; inspect never creates a permit.
        local result=run(held.scope,held.photo,held.fence,now,function(_,_,r)
            return r and r.uploadPhase=="dispatch_may_have_started" and {state="invoke_once"} or fail("dispatch_refused")
        end)
        return result
    end
    function S:recordResult(scope,photo,e,kind,photoId,now)
        if kind~="returned_upload_id" and kind~="definitive_rejection" and kind~="upload_outcome_unknown" then return fail("result_invalid") end
        if (kind=="returned_upload_id" and not C.opaque(photoId)) or (kind~="returned_upload_id" and photoId~=N) then return fail("result_invalid") end
        return update(scope,photo,e,now,function(_,_,r)
            if r.uploadPhase~="dispatch_may_have_started" and r.uploadPhase~="upload_outcome_unknown" then return fail("transition_invalid") end
            if kind=="returned_upload_id" then r.uploadPhase="returned_id"; knownResult(r,photoId,kind)
            elseif kind=="definitive_rejection" then r.uploadPhase=kind; r.resultKind=kind
            else r.uploadPhase=kind; r.attentionCode=kind end
            return {state=r.uploadPhase},true
        end)
    end
    function S:cancelBeforeInvocation(scope,photo,e,now)
        return update(scope,photo,e,now,function(_,_,r)
            if r.uploadPhase~="prepared" and r.uploadPhase~="authorized" then return fail("transition_invalid") end
            r.uploadPhase="cancelled_before_invocation"
            return {state=r.uploadPhase},true
        end)
    end
    function S:successor(scope,photo,e,selection,album,mode,confirmed,now)
        if not validInputs(selection,album) or confirmed~=true or (mode~="unused" and mode~="new_copy" and mode~="rejected") then return fail("confirmation_required") end
        selection,album=C.clone(selection),C.clone(album)
        return update(scope,photo,e,now,function(d,p,r)
            local phase=r.uploadPhase
            if mode=="unused" then
                if memoryRecovery or d.recoveryGate.state~="ordinary" or (phase~="prepared" and phase~="authorized") then return fail("history_untrusted") end
            elseif mode=="rejected" then
                if memoryRecovery or d.recoveryGate.state~="ordinary" then return fail("history_untrusted") end
                if phase~="definitive_rejection" then return fail("transition_invalid") end
            elseif phase~="dispatch_may_have_started" and phase~="upload_outcome_unknown" and phase~="history_untrusted"
                and not ((memoryRecovery or d.recoveryGate.state=="history_untrusted") and (phase=="prepared" or phase=="authorized")) then return fail("transition_invalid") end
            for _,other in ipairs(d.attempts) do
                if other~=r and sameScope(other,r) and not inactive[other.uploadPhase] then return fail("attempt_exists") end
            end
            if not capacity(d,p,scope) then return fail("storage_full") end
            if mode=="unused" then r.uploadPhase="superseded_before_invocation"
            elseif mode=="new_copy" then r.uploadPhase="abandoned_possible_flickr_photo" end
            local nextRecord=allocate(d,scope,selection,album,now,r.attemptNumber,mode=="new_copy" and "deliberate_new_copy" or nil)
            return {state="prepared",successor=C.clone(nextRecord),successorFence=fence(d,p,nextRecord)},true
        end,true)
    end
    function S:enterRecovery(scope,photo,e,now)
        memoryRecovery=true -- Survives failed persistence in this activation.
        if not expectValid(e) then return fail("scope_invalid") end
        return run(scope,photo,e,now,function(d)
            if d.recoveryGate.gateRevision==C.MAX_INTEGER or not bump(d,nil,now) then return fail("counter_exhausted") end
            d.recoveryGate={state="history_untrusted",gateRevision=d.recoveryGate.gateRevision+1,confirmedAt=now}
            return {state="history_untrusted"},true
        end,true)
    end
    function S:recordMissingHistory(scope,photo,e,now)
        if not expectValid(e) then return fail("scope_invalid") end
        return run(scope,photo,e,now,function(d,p)
            if not memoryRecovery and d.recoveryGate.state~="history_untrusted" then return fail("transition_invalid") end
            if latest(d,scope) then return fail("attempt_exists") end
            if not capacity(d,p,scope) then return fail("storage_full") end
            local r=C.clone(scope)
            for k in pairs(recordFields) do if r[k]==nil then r[k]=N end end
            r.recordKind="history_attention"; r.attemptNumber=d.nextAttemptNumber; r.recordRevision=1
            r.uploadPhase="history_untrusted"; r.selectionKind="unknown"; r.createdAt=now; r.updatedAt=now
            r.attentionCode="history_untrusted"; r.recoveryDisposition="history_untrusted"; r.recoveryConfirmedAt=now
            d.nextAttemptNumber=d.nextAttemptNumber+1; table.insert(d.attempts,r); bump(d,nil,now)
            return {state="history_untrusted",record=C.clone(r),fence=fence(d,p,r)},true
        end,true)
    end
    -- Persist the exact ADR0012 selected tuple before its idempotent hosted PUT.
    function S:selectKnownPhoto(scope,photo,e,photoId,album,confirmed,now)
        if not C.opaque(photoId) or confirmed~=true or not C.object(album,fields("fgaAlbumBindingId albumBindingRevision"))
            or not nullable(album.fgaAlbumBindingId,C.opaque) or not nullable(album.albumBindingRevision,positive)
            or ((album.fgaAlbumBindingId==N)~=(album.albumBindingRevision==N)) then return fail("confirmation_required") end
        album=C.clone(album)
        return update(scope,photo,e,now,function(d,_,r)
            if r.uploadPhase~="upload_outcome_unknown" and r.uploadPhase~="dispatch_may_have_started" and r.uploadPhase~="history_untrusted"
                and r.uploadPhase~="prepared" and r.uploadPhase~="authorized" then return fail("transition_invalid") end
            if (r.uploadPhase=="prepared" or r.uploadPhase=="authorized") and not memoryRecovery
                and d.recoveryGate.state~="history_untrusted" then return fail("repair_decision_required") end
            if r.albumObligation~=N and r.albumObligation.fgaAlbumBindingId~=N
                and (r.albumObligation.fgaAlbumBindingId~=album.fgaAlbumBindingId
                    or not positive(album.albumBindingRevision) or album.albumBindingRevision<r.albumObligation.albumBindingRevision) then return fail("correlation_invalid") end
            if r.albumObligation==N then r.albumObligation=checkpoint("albumObligation",nil,album) end
            r.recoveryDisposition="known_photo_reconciliation"; r.recoveryConfirmedAt=now
            r.uploadPhase="ambiguity_resolution_pending"; knownResult(r,photoId,"photographer_assertion")
            return {state="ambiguity_resolution_pending"},true
        end,true)
    end
    function S:acknowledgeCatalog(scope,photo,e,photoId,now)
        return update(scope,photo,e,now,function(_,_,r)
            if r.uploadPhase~="returned_id" or photoId~=r.flickrPhotoId or remote(photo)~=photoId
                or (r.resultKind=="photographer_assertion" and r.photoProof.state~="acknowledged") then return fail("correlation_invalid") end
            if r.catalogPublication.state=="acknowledged" then return fail("transition_invalid") end
            r.catalogPublication=checkpoint("catalogPublication",now,{flickrPhotoId=photoId})
            return {state="catalog_acknowledged"},true
        end)
    end
    function S:acknowledgeProof(scope,photo,e,proof,now)
        if not C.object(proof,fields("fgaPhotoBindingId flickrPhotoId linkedFlickrRevision verificationRevision"))
            or not C.opaque(proof.fgaPhotoBindingId) or not C.opaque(proof.flickrPhotoId)
            or not positive(proof.linkedFlickrRevision) or not positive(proof.verificationRevision) then return fail("correlation_invalid") end
        proof=C.clone(proof)
        return update(scope,photo,e,now,function(_,_,r)
            if (r.uploadPhase~="returned_id" and r.uploadPhase~="ambiguity_resolution_pending") or r.flickrPhotoId~=proof.flickrPhotoId
                or r.photoProof.state=="acknowledged" or (r.resultKind=="returned_upload_id" and r.catalogPublication.state~="acknowledged") then return fail("correlation_invalid") end
            proof.flickrPhotoId=nil
            r.photoProof=checkpoint("photoProof",now,proof)
            r.uploadPhase="returned_id"; r.attentionCode=N
            return {state="proof_acknowledged"},true
        end)
    end
    function S:acknowledgeAlbum(scope,photo,e,album,now)
        -- Scope fields are transient validated #0088 binding evidence. Persist
        -- only the accepted checkpoint projection; never a title/response body.
        if not C.object(album,fields("fgaAlbumBindingId fgaPhotoBindingId albumBindingRevision flickrPhotosetId hostedObligationState fgaPublishServiceId localCollectionIdentifier linkedFlickrRevision")) then return fail("correlation_invalid") end
        album=C.clone(album)
        return update(scope,photo,e,now,function(_,_,r)
            if r.uploadPhase~="returned_id" or r.photoProof.state~="acknowledged" or r.albumObligation.state=="acknowledged"
                or album.fgaPublishServiceId~=r.fgaPublishServiceId
                or album.localCollectionIdentifier~=string.format("%.0f",r.publishedCollectionLocalId)
                or album.linkedFlickrRevision~=r.photoProof.linkedFlickrRevision
                or not positive(album.albumBindingRevision)
                or (r.albumObligation.fgaAlbumBindingId~=N and r.albumObligation.fgaAlbumBindingId~=album.fgaAlbumBindingId)
                or (r.albumObligation.albumBindingRevision~=N and r.albumObligation.albumBindingRevision>album.albumBindingRevision)
                or (r.albumObligation.flickrPhotosetId~=N and r.albumObligation.flickrPhotosetId~=album.flickrPhotosetId) then return fail("correlation_invalid") end
            local value=checkpoint("albumObligation",now,{fgaAlbumBindingId=album.fgaAlbumBindingId,
                fgaPhotoBindingId=album.fgaPhotoBindingId,albumBindingRevision=album.albumBindingRevision,
                flickrPhotosetId=album.flickrPhotosetId,hostedObligationState=album.hostedObligationState})
            if not checkpointValid("albumObligation",value,r) then return fail("correlation_invalid") end
            r.albumObligation=value; return {state="album_acknowledged"},true
        end)
    end
    local itemStates=fields("queued attempting retrying throttled added moderation_submitted delivery_uncertain needs_attention cancelled")
    local function itemsValid(items,groups)
        if not C.array(items,60,false) or #items~=#groups then return false end
        local ids={}
        for i,item in ipairs(items) do
            if not C.object(item,fields("fgaSubmissionIntentId flickrGroupId state created permanentSubmissionBlock"))
                or not C.opaque(item.fgaSubmissionIntentId) or ids[item.fgaSubmissionIntentId]
                or item.flickrGroupId~=groups[i] or not itemStates[item.state] or type(item.created)~="boolean" then return false end
            ids[item.fgaSubmissionIntentId]=true
            local reason=item.state=="moderation_submitted" and "moderation_submission_recorded"
                or item.state=="delivery_uncertain" and "delivery_uncertain" or nil
            if reason then
                if item.created or not C.object(item.permanentSubmissionBlock,fields("reasonCode createdAt"))
                    or item.permanentSubmissionBlock.reasonCode~=reason or not C.time(item.permanentSubmissionBlock.createdAt) then return false end
            elseif item.permanentSubmissionBlock~=N then return false end
        end
        return true
    end
    function S:acknowledgeGroups(scope,photo,e,binding,items,now)
        if not C.object(binding,fields("fgaPhotoBindingId verificationRevision")) then return fail("correlation_invalid") end
        binding,items=C.clone(binding),C.clone(items)
        return update(scope,photo,e,now,function(_,_,r)
            if r.uploadPhase~="returned_id" or r.groupHandoff==N or r.groupHandoff.state=="acknowledged"
                or r.photoProof.state~="acknowledged" or r.catalogPublication.state~="acknowledged"
                or not itemsValid(items,r.flickrGroupIds) then return fail("group_acknowledgement_invalid") end
            local value=checkpoint("groupHandoff",now,{fgaPhotoBindingId=binding.fgaPhotoBindingId,
                verificationRevision=binding.verificationRevision,acceptedGroupCount=#items,allItemsValidated=true})
            if not checkpointValid("groupHandoff",value,r) then return fail("correlation_invalid") end
            r.groupHandoff=value; return {state="groups_acknowledged"},true
        end)
    end
    function S:checkpointNeedsAttention(scope,photo,e,kind,now)
        if not checkpointFields[kind] then return fail("transition_invalid") end
        return update(scope,photo,e,now,function(_,_,r)
            local value=r[kind]
            if value==N or value.state=="acknowledged" then return fail("transition_invalid") end
            value.state="needs_attention"; r.attentionCode="checkpoint_needs_attention"
            return {state="needs_attention"},true
        end)
    end
    function S:retire(scope,photo,e,choiceDisposition,now)
        if choiceDisposition~="consumed" and choiceDisposition~="newer_revision_preserved" and choiceDisposition~="absent" then return fail("choice_unconfirmed") end
        return update(scope,photo,e,now,function(d,p,r)
            if r.recordKind~="upload_attempt" or r.uploadPhase~="returned_id" or r.photoProof.state~="acknowledged"
                or r.catalogPublication.state~="acknowledged" or r.albumObligation.state~="acknowledged"
                or (r.groupHandoff~=N and r.groupHandoff.state~="acknowledged")
                or (r.selectionKind=="absent")~=(choiceDisposition=="absent") or remote(photo)~=r.flickrPhotoId then return fail("retirement_refused") end
            if p.metadataRevision==C.MAX_INTEGER then return fail("counter_exhausted") end
            local entry={}
            for k in pairs(entryFields) do entry[k]=r[k] or N end
            for _,key in ipairs({"fgaPhotoBindingId","linkedFlickrRevision","verificationRevision"}) do entry[key]=r.photoProof[key] end
            for _,key in ipairs({"fgaAlbumBindingId","flickrPhotosetId","albumBindingRevision","hostedObligationState"}) do entry[key]=r.albumObligation[key] end
            entry.groupHandoffAcknowledged=r.groupHandoff~=N and true or N; entry.completedAt=now
            if not entryValid(entry) then return fail("retirement_refused") end
            local replaced=false
            for i,other in ipairs(p.entries) do if sameScope(other,r) then p.entries[i]=entry; replaced=true; break end end
            if not replaced then
                if #p.entries>=M.MAX_PHOTO_ENTRIES then return fail("storage_full") end
                table.insert(p.entries,entry); table.sort(p.entries,scopeLess)
            end
            p.metadataRevision=p.metadataRevision+1
            for i,other in ipairs(d.attempts) do if other==r then table.remove(d.attempts,i); break end end
            return {state="retired",correlation=C.clone(entry)},true,true
        end)
    end
    function S:retireNonDispatch(scope,photo,e,reported,noRecoveryDependency,now)
        if reported~=true or noRecoveryDependency~=true then return fail("retirement_refused") end
        return update(scope,photo,e,now,function(d,_,r)
            if r.uploadPhase~="cancelled_before_invocation" and r.uploadPhase~="superseded_before_invocation"
                and r.uploadPhase~="definitive_rejection" then return fail("retirement_refused") end
            for _,other in ipairs(d.attempts) do
                if other.predecessorAttemptNumber==r.attemptNumber and not recordValid(other) then return fail("retirement_refused") end
            end
            for i,other in ipairs(d.attempts) do if other==r then table.remove(d.attempts,i); break end end
            return {state="retired_nondispatch"},true
        end)
    end
    return S
end
return M
