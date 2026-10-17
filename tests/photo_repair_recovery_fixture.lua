-- SDK-boundary fakes only. All upload-store/repair/recovery code is required
-- from the production bundle; no native host, rendition, upload or network.
pluginId="com.flickrgroupaddr.lrc15"
serviceIdentity="service-1"
remoteWrites,proofCalls,uploadCalls=0,0,0
unsafeProofCalls,privateGateCount=0,0
events,requests={},{}
service={localIdentifier=12}
collection={localIdentifier=34}
publication={}
function service:getPluginId() return pluginId end
function service:getChildCollections() return {collection} end
function service:getChildCollectionSets() return {} end
function collection:getService() return service end
function collection:isSmartCollection() return false end
function collection:getPhotos() return hiddenPhoto and {} or {photo} end
function collection:getPublishedPhotos() return hiddenPublication and {} or {publication} end
function publication:getPhoto() return photo end
function publication:getRemoteId() return remoteId end
function publication:setRemoteId(value)
    assert(ordinaryInside and not inside)
    remoteWrites=remoteWrites+1
    table.insert(events,"catalog_remote_id")
    if failRemoteWrite then error("synthetic catalog write refused") end
    remoteId=value
end
function catalog:getPublishServices(id)
    assert(id==pluginId)
    return hiddenService and {} or {service}
end
function catalog:getPublishedCollectionByLocalIdentifier(id)
    return not hiddenCollection and id==collection.localIdentifier and collection or nil
end
function catalog:withWriteAccessDo(_,callback,opts)
    assert(opts.timeout==5 and opts.asynchronous==false and not inside and not ordinaryInside)
    if beforeOrdinaryGate then local hook=beforeOrdinaryGate; beforeOrdinaryGate=nil; hook() end
    if ordinaryGateStatus~="executed" then deferredOrdinary=callback; return ordinaryGateStatus end
    local old=remoteId
    ordinaryInside=true
    local ok,err=pcall(callback)
    ordinaryInside=false
    if not ok then remoteId=old; error(err) end
    if afterOrdinaryGate then local hook=afterOrdinaryGate; afterOrdinaryGate=nil; hook() end
    return ordinaryGateStatus
end
ordinaryGateStatus="executed"
local originalPrivateGate=catalog.withPrivateWriteAccessDo
function catalog:withPrivateWriteAccessDo(callback,opts)
    assert(not ordinaryInside)
    privateGateCount=privateGateCount+1
    if onPrivateGate then onPrivateGate(privateGateCount) end
    return originalPrivateGate(self,callback,opts)
end
local originalWrite=catalog.setPropertyForPlugin
function catalog:setPropertyForPlugin(p,key,value)
    assert(not ordinaryInside)
    local decoded=require("UploadAttemptCodec").decode(value,33554432)
    local record=decoded and decoded.attempts[1]
    if record and record.photoProof and record.photoProof.state=="acknowledged" then
        table.insert(events,"proof_ack_durable")
    end
    return originalWrite(self,p,key,value)
end
repairOptions={catalog=catalog,pluginId=pluginId,activationToken=token,
    activeCatalog=function() return active end,currentActivation=function() return activation end,
    isOwner=function() return owner end,pcall=pcall,
    readServiceIdentity=function() return serviceIdentity end}
proofMode="success"
linkedRevision=6
proofTransport={capabilities={uploadPhotoProof=true}}
function proofTransport.request(method,path,body,maximum)
    assert(method=="PUT" and maximum==4096 and not inside and not ordinaryInside)
    proofCalls=proofCalls+1
    if hiddenPublication and not string.find(path,"ambiguity%-resolution") then
        unsafeProofCalls=unsafeProofCalls+1
    end
    table.insert(events,"hosted_proof")
    table.insert(requests,{method=method,path=path,body=body})
    if onProof then local hook=onProof; onProof=nil; hook() end
    if proofMode=="lost" or (proofMode=="lost_once" and proofCalls==1) then
        return nil,{status=503}
    end
    local response={schemaVersion=1,fgaPhotoBindingId="binding-1",
        sourceKind=string.find(path,"ambiguity%-resolution") and
            "photographer_reconciled_ambiguous_upload" or "fga_direct_upload",
        flickrPhotoId="photo-1",linkedFlickrRevision=6,verificationRevision=7,
        verifiedAt="2026-10-17T12:00:00.000000Z"}
    if proofMode=="wrong_photo" then response.flickrPhotoId="other-photo" end
    if proofMode=="conflict" then return "",{status=409} end
    local bodyOut=require("UploadAttemptCodec").encode(response)
    local headersOut={
        {field="Content-Type",value="application/json"},
        {field="Cache-Control",value="no-store"},{field="Location",value=path},
        status=proofCalls==1 and 201 or 200}
    if responseTransform then return responseTransform(bodyOut,headersOut) end
    return bodyOut,headersOut
end
