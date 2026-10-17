-- Copyright 2026 Terry Ott. MIT License.
-- Dormant publisher composition: no render, selector, transport or upload API.
local Choice = require 'FrozenChoiceConsumptionAdapter'
local Attempts = require 'UploadAttemptStore'
local C = require 'UploadAttemptCodec'
local N = C.null
local M = { PRODUCTION_QUALIFIED = false }
local function fail(state) return {state=state} end
local function same(a,b)
    if a==N or b==N or type(a)~='table' or type(b)~='table' then return a==b end
    for k,v in pairs(a) do if not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function acknowledged(value)
    return type(value)=='table' and value~=N and value.state=='acknowledged'
end

-- verifyTarget is the owning provider's fresh #0090 verified identity boundary.
-- isOwner is its current dispatcher ownership predicate, never an invented lease.
local function construct(d,exportContext,choiceFactory)
    if type(d)~='table' or type(exportContext)~='table' or d.plugin==nil
        or type(d.pcall)~='function' or type(d.activeCatalog)~='function'
        or d.activationToken==nil or type(d.currentActivation)~='function'
        or type(d.isOwner)~='function' or type(d.readRemoteId)~='function'
        or type(d.verifyTarget)~='function' or type(d.identityCurrent)~='function'
        or (d.cancelled~=nil and type(d.cancelled)~='function') then return nil,'scope_invalid' end
    local call=d.pcall
    local ok,catalog=call(d.activeCatalog)
    if not ok or catalog==nil then return nil,'scope_invalid' end
    local token=d.activationToken
    local target
    local function currentLocal()
        return d.activeCatalog()==catalog and d.currentActivation()==token
            and not (d.cancelled and d.cancelled())
            and (target==nil or d.identityCurrent(C.clone(target))==true)
    end
    local function currentTarget()
        if not currentLocal() then return nil end
        local value=d.verifyTarget(exportContext)
        if type(value)~='table' or value.ok~=true or not C.opaque(value.fgaPublishServiceId)
            or not C.integer(value.linkedFlickrRevision,1)
            or type(value.localCollectionIdentifier)~='string' then return nil end
        if target and (target.fgaPublishServiceId~=value.fgaPublishServiceId
            or target.linkedFlickrRevision~=value.linkedFlickrRevision
            or target.localCollectionIdentifier~=value.localCollectionIdentifier) then return nil end
        return {fgaPublishServiceId=value.fgaPublishServiceId,
            linkedFlickrRevision=value.linkedFlickrRevision,
            localCollectionIdentifier=value.localCollectionIdentifier}
    end
    local valid,value=call(currentTarget)
    if not valid or not value then return nil,'scope_invalid' end
    target=value
    local store=Attempts.new{catalog=catalog,plugin=d.plugin,activationToken=token,
        activeCatalog=function() return currentLocal() and catalog or nil end,
        currentActivation=d.currentActivation,isOwner=d.isOwner,
        pcall=call,readRemoteId=d.readRemoteId}
    local handles,photos,busy={},{},false
    local S={}
    local function run(operation)
        if busy then return fail('busy') end
        busy=true
        local worked,result=call(function()
            if not currentTarget() then return fail('scope_invalid') end
            return operation()
        end)
        busy=false
        return worked and result or fail('unresolved')
    end
    local function read(h,now)
        local result=store:inspect(h.scope,h.photo,now,h.record.attemptNumber)
        if result.state~='ready' then return nil,result end
        local r=result.record
        if not r or r.recordKind~='upload_attempt' or r.attemptNumber~=h.record.attemptNumber
            or r.selectionKind~=h.record.selectionKind or r.selectionRevision~=h.record.selectionRevision
            or not same(r.flickrGroupIds,h.record.flickrGroupIds)
            or not same({r.publishServiceLocalId,r.fgaPublishServiceId,r.publishedCollectionLocalId,r.photoUuid},
                {h.scope.publishServiceLocalId,h.scope.fgaPublishServiceId,h.scope.publishedCollectionLocalId,h.scope.photoUuid})
            or result.gate.state~='ordinary' then return nil,fail('context_invalid') end
        return result
    end
    function S:prepare(photo,handoffId,now)
        return run(function()
            if photo==nil or not C.time(now) then return fail('scope_invalid') end
            if photos[photo] then return fail('already_prepared') end
            local ownershipScope
            local ownerNumber=N
            local function choiceCurrent()
                return currentLocal() and (ownershipScope==nil
                    or (catalog:findPhotoByUuid(ownershipScope.photoUuid)==photo
                        and d.isOwner(C.clone(ownershipScope),ownerNumber)==true))
            end
            local adapter,reason=choiceFactory({plugin=d.plugin,call=call,
                activeCatalog=function() return choiceCurrent() and catalog or nil end,
                cancelled=function() return not choiceCurrent() end},exportContext,photo)
            if not adapter then return fail(reason) end
            ownershipScope={publishServiceLocalId=exportContext.publishService.localIdentifier,
                publishedCollectionLocalId=exportContext.publishedCollection.localIdentifier,
                photoUuid=photo:getRawMetadata('uuid'),fgaPublishServiceId=target.fgaPublishServiceId}
            if catalog:findPhotoByUuid(ownershipScope.photoUuid)~=photo
                or d.isOwner(ownershipScope,N)~=true then return fail('scope_invalid') end
            -- Freeze once. A failed attempt admission never authorizes rendering.
            photos[photo]=true
            local frozen=adapter:freeze(handoffId)
            if frozen.state~='frozen' then return frozen end
            local snapshot=frozen.choice
            local scope=C.clone(snapshot.scope)
            scope.fgaPublishServiceId=target.fgaPublishServiceId
            snapshot.scope=C.clone(scope)
            if target.localCollectionIdentifier~=string.format('%.0f',scope.publishedCollectionLocalId) then
                return fail('scope_invalid')
            end
            local inspected=store:inspect(scope,photo,now)
            if inspected.state~='ready' then return inspected end
            if inspected.classification~='unpublished' then return fail(inspected.classification) end
            local selection={selectionKind=snapshot.selectionState,
                selectionRevision=snapshot.selectionState=='absent' and N or snapshot.selectionRevision,
                flickrGroupIds=C.clone(snapshot.flickrGroupIds)}
            local prepared=store:prepare(scope,photo,inspected.fence,selection,
                {fgaAlbumBindingId=N,albumBindingRevision=N},now)
            if prepared.state~='prepared' then return prepared end
            ownerNumber=prepared.record.attemptNumber
            if not currentTarget() or not choiceCurrent() then return fail('scope_invalid') end
            local handle={}
            handles[handle]={adapter=adapter,choiceHandle=frozen.snapshot,scope=scope,photo=photo,
                record=C.clone(prepared.record),snapshot=C.clone(snapshot)}
            photos[photo]=handle
            return {state='prepared',context=handle,snapshot=C.clone(snapshot),
                record=C.clone(prepared.record),fence=C.clone(prepared.fence)}
        end)
    end
    function S:inspect(handle,now)
        return run(function()
            local h=handles[handle]
            if not h then return fail('context_invalid') end
            local result,reason=read(h,now)
            if not result then return reason end
            result.snapshot=C.clone(h.snapshot)
            return result
        end)
    end
    function S:bindGroups(handle,now)
        return run(function()
            local h=handles[handle]
            if not h then return fail('context_invalid') end
            local result,reason=read(h,now)
            if not result then return reason end
            local r=result.record
            if not acknowledged(r.photoProof) or r.photoProof.linkedFlickrRevision~=target.linkedFlickrRevision
                or not C.opaque(r.flickrPhotoId) then return fail('proof_required') end
            return h.adapter:bindGroups(h.choiceHandle,{fgaPhotoBindingId=r.photoProof.fgaPhotoBindingId,
                flickrPhotoId=r.flickrPhotoId,verificationRevision=r.photoProof.verificationRevision,
                linkedFlickrRevision=r.photoProof.linkedFlickrRevision,sourceKind='fga_direct_upload'})
        end)
    end
    function S:confirmGroups(handle,status,document,now)
        return run(function()
            local h=handles[handle]
            if not h then return fail('context_invalid') end
            local result,reason=read(h,now)
            if not result then return reason end
            local r=result.record
            if not acknowledged(r.photoProof) or r.photoProof.linkedFlickrRevision~=target.linkedFlickrRevision
                or not acknowledged(r.catalogPublication) or not acknowledged(r.groupHandoff) then
                return fail('handoff_required')
            end
            -- #0065 validates the complete 202 against its locked binding/group set
            -- and alone owns exact-revision consumption in the selection write gate.
            return h.adapter:confirmGroups(h.choiceHandle,status,document)
        end)
    end
    function S:confirmPublication(handle,now)
        return run(function()
            local h=handles[handle]
            if not h then return fail('context_invalid') end
            local result,reason=read(h,now)
            if not result then return reason end
            local r=result.record
            if not acknowledged(r.photoProof) or r.photoProof.linkedFlickrRevision~=target.linkedFlickrRevision
                or not acknowledged(r.catalogPublication) or not acknowledged(r.albumObligation) then
                return fail('publication_required')
            end
            return h.adapter:confirmPublication(h.choiceHandle,
                {publicationRecorded=true,albumAttachmentDurable=true})
        end)
    end
    return S
end
function M.new(d,exportContext)
    return construct(d,exportContext,Choice.new)
end
function M.newQualification(d,exportContext)
    return construct(d,exportContext,Choice.newQualification)
end
return M
