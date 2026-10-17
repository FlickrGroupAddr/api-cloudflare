-- Synthetic SDK boundary; every selection/store/controller operation is actual Lua.
json=require 'dkjson'
Adapter=require 'FrozenChoiceConsumptionAdapter'
plugin={}; catalog={}; activeCatalog=catalog; catalogProperties={}
photoUuid='00000000-0000-0000-0000-000000000065'
photo={catalog=catalog,properties={}}
service={localIdentifier=12}
function service:type() return 'LrPublishService' end
function service:getPluginId() return require('ConnectionCore').PLUGIN_ID end
album={localIdentifier=34}
function album:type() return 'LrPublishedCollection' end
function album:isSmartCollection() return false end
function album:getService() return service end
memberships={album}
function photo:getContainedPublishedCollections() return memberships end
function photo:getRawMetadata(key) assert(key=='uuid'); return photoUuid end
function photo:getPropertyForPlugin(p,key) assert(p==plugin); return self.properties[key] end
function photo:setPropertyForPlugin(p,key,v)
    assert(inGate and p==plugin); writes=writes+1; self.properties[key]=v
end
function catalog:getPropertyForPlugin(p,key) assert(p==plugin); return catalogProperties[key] end
function catalog:setPropertyForPlugin(p,key,v)
    assert(inGate and p==plugin); writes=writes+1; catalogProperties[key]=v
end
function catalog:getTargetPhotos() error('publisher must not use UI selection') end
function catalog:getActiveSources() error('publisher must not use UI selection') end
writes=0; gate='executed'; cancelled=false
function catalog:withPrivateWriteAccessDo(fn,options)
    assert(options.timeout==5 and options.asynchronous==false)
    if beforeGate then local hook=beforeGate; beforeGate=nil; hook() end
    if gate~='executed' then delayed=fn; return gate end
    local priorPhoto,priorOutbox=photo.properties.groupAdditionSelections,catalogProperties.groupAdditionOutboxV1
    inGate=true
    local ok,err=pcall(fn)
    inGate=false
    if not ok then
        photo.properties.groupAdditionSelections=priorPhoto
        catalogProperties.groupAdditionOutboxV1=priorOutbox
        error(err)
    end
    if afterGate then local hook=afterGate; afterGate=nil; hook() end
    return gate
end
context={publishService=service,publishedCollection=album,
    publishedCollectionInfo={isDefaultCollection=false}}
deps={plugin=plugin,call=pcall,activeCatalog=function() return activeCatalog end,
    cancelled=function() return cancelled end}
for _,key in ipairs({'credential','post','get','render','upload','publish','replay'}) do
    deps[key]=function() error('unexpected external operation') end
end
scope={publishServiceLocalId=12,publishedCollectionLocalId=34,photoUuid=photoUuid}
store=require('GroupSelectionStore').new{catalog=catalog,photo=photo,plugin=plugin,
    pcall=pcall,activeCatalog=deps.activeCatalog}
function start() return Adapter.new(deps,context,photo) end
function save(groups,revision) return store:saveChoice(scope,groups,revision or 0) end
function choice() return store:readChoice(scope).selection end
function freeze(id)
    session=assert(start())
    local result=session:freeze(id or 'handoff-65')
    assert(result.state=='frozen',result.state)
    handle=result.snapshot
    return result
end
binding={fgaPhotoBindingId='binding-65',flickrPhotoId='photo-65',verificationRevision=7,
    linkedFlickrRevision=9,sourceKind='fga_direct_upload'}
function response(groups)
    local rows={}
    for i,id in ipairs(groups or {'g1','g2'}) do
        rows[i]={fgaSubmissionIntentId='intent-'..id,flickrGroupId=id,state='queued',
            created=true,permanentSubmissionBlock=json.null}
    end
    return {schemaVersion=2,fgaPhotoBindingId='binding-65',flickrPhotoId='photo-65',submissions=rows}
end
