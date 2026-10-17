-- Synthetic SDK persistence only; publisher, selection and upload store are real modules.
json=require 'dkjson'
Context=require 'FrozenPublishContext'
plugin,catalog,token={},{},{}
activeCatalog,activation,owner=catalog,token,true
catalogProperties,photos={},{}
writes,gate=0,'executed'
now='2026-10-17T12:00:00Z'
service={localIdentifier=12}
function service:type() return 'LrPublishService' end
function service:getPluginId() return require('ConnectionCore').PLUGIN_ID end
function makeAlbum(id,svc)
    local a={localIdentifier=id,service=svc or service}
    function a:type() return 'LrPublishedCollection' end
    function a:isSmartCollection() return false end
    function a:getService() return self.service end
    return a
end
album=makeAlbum(34)
function makePhoto(id)
    local p={catalog=catalog,uuid=id,properties={},memberships={album}}
    function p:getRawMetadata(key) assert(key=='uuid'); return self.uuid end
    function p:getContainedPublishedCollections() return self.memberships end
    function p:getPropertyForPlugin(plug,key) assert(plug==plugin); return self.properties[key] end
    function p:setPropertyForPlugin(plug,key,v)
        assert(inGate and plug==plugin); self.properties[key]=v; writes=writes+1
        if failField==key then error('synthetic property failure') end
    end
    photos[id]=p; return p
end
photo=makePhoto('00000000-0000-0000-0000-000000000097')
function catalog:findPhotoByUuid(id) return photos[id] end
function catalog:getPropertyForPlugin(plug,key) assert(plug==plugin); return catalogProperties[key] end
function catalog:setPropertyForPlugin(plug,key,v)
    assert(inGate and plug==plugin); catalogProperties[key]=v; writes=writes+1
    if failField==key then error('synthetic property failure') end
end
function catalog:getTargetPhotos() error('unexpected UI selection') end
function catalog:getActiveSources() error('unexpected UI selection') end
local function copy(v)
    if type(v)~='table' then return v end
    local c={}; for k,x in pairs(v) do c[k]=copy(x) end; return c
end
function catalog:withPrivateWriteAccessDo(fn,options)
    assert(options.timeout==5 and options.asynchronous==false and not inGate)
    gateCount=(gateCount or 0)+1
    if beforeGate then beforeGate(gateCount) end
    if gate~='executed' then delayed=fn; return gate end
    local prior=copy(catalogProperties); local pp={}
    for id,p in pairs(photos) do pp[id]=copy(p.properties) end
    inGate=true; local ok,err=pcall(fn); inGate=false
    if not ok then
        catalogProperties=prior
        for id,p in pairs(photos) do p.properties=pp[id] end
        error(err)
    end
    if afterGate then afterGate(gateCount) end
    return gate
end
exportContext={publishService=service,publishedCollection=album,
    publishedCollectionInfo={isDefaultCollection=false}}
target={ok=true,fgaPublishServiceId='service-1',linkedFlickrRevision=6,
    localCollectionIdentifier='34'}
deps={plugin=plugin,pcall=pcall,call=pcall,activationToken=token,
    activeCatalog=function() return activeCatalog end,
    currentActivation=function() return activation end,isOwner=function() return owner end,
    readRemoteId=function(p) return p.remoteId end,verifyTarget=function() return target end,
    identityCurrent=function(expected)
        return target.ok==true and target.fgaPublishServiceId==expected.fgaPublishServiceId
            and target.linkedFlickrRevision==expected.linkedFlickrRevision
            and target.localCollectionIdentifier==expected.localCollectionIdentifier
    end}
for _,key in ipairs({'selector','render','upload','post','get','credential','publish'}) do
    deps[key]=function() error('unexpected external operation') end
end
function selectionScope(p,a,s)
    return {publishServiceLocalId=(s or service).localIdentifier,
        publishedCollectionLocalId=(a or album).localIdentifier,photoUuid=p.uuid}
end
function selectionStore(p)
    return require('GroupSelectionStore').new{catalog=catalog,photo=p,plugin=plugin,
        pcall=pcall,activeCatalog=deps.activeCatalog}
end
function save(p,groups,revision,a,s)
    return selectionStore(p):saveChoice(selectionScope(p,a,s),groups,revision or 0)
end
function choice(p,a,s) return selectionStore(p):readChoice(selectionScope(p,a,s)).selection end
function start() return Context.new(deps,exportContext) end
session=assert(start())
function prepare(p,id) return session:prepare(p or photo,id or 'handoff-97',now) end
uploadStore=require('UploadAttemptStore').new{catalog=catalog,plugin=plugin,pcall=pcall,
    activationToken=token,activeCatalog=deps.activeCatalog,currentActivation=deps.currentActivation,
    isOwner=deps.isOwner,readRemoteId=deps.readRemoteId}
function uploadCall(result,p,method,...)
    p=p or photo
    local scope=result.snapshot.scope
    local read=uploadStore:inspect(scope,p,now,result.record.attemptNumber)
    assert(read.state=='ready',read.state)
    local args={...}; args[#args+1]=now
    return uploadStore[method](uploadStore,scope,p,read.fence,unpack(args))
end
function publication(result,p,groups)
    p=p or photo
    assert(uploadCall(result,p,'authorize','authorization-'..result.record.attemptNumber).state=='authorized')
    assert(uploadCall(result,p,'markDispatch').state=='dispatch_marked')
    assert(uploadCall(result,p,'recordResult','returned_upload_id','photo-97').state=='returned_id')
    p.remoteId='photo-97'
    assert(uploadCall(result,p,'acknowledgeCatalog','photo-97').state=='catalog_acknowledged')
    assert(uploadCall(result,p,'acknowledgeProof',{fgaPhotoBindingId='binding-97',
        flickrPhotoId='photo-97',linkedFlickrRevision=6,verificationRevision=7}).state=='proof_acknowledged')
    assert(uploadCall(result,p,'acknowledgeAlbum',{fgaAlbumBindingId='album-97',
        fgaPhotoBindingId='binding-97',albumBindingRevision=2,flickrPhotosetId=json.null,
        hostedObligationState='waiting_for_album',fgaPublishServiceId='service-1',
        localCollectionIdentifier='34',linkedFlickrRevision=6}).state=='album_acknowledged')
end
function response(groups)
    local rows={}
    for i,id in ipairs(groups or {'g1','g2'}) do
        rows[i]={fgaSubmissionIntentId='intent-'..id,flickrGroupId=id,state='queued',
            created=true,permanentSubmissionBlock=json.null}
    end
    return {schemaVersion=2,fgaPhotoBindingId='binding-97',flickrPhotoId='photo-97',submissions=rows}
end
function groupCheckpoint(result,p,groups)
    return uploadCall(result,p,'acknowledgeGroups',
        {fgaPhotoBindingId='binding-97',verificationRevision=7},response(groups).submissions)
end
