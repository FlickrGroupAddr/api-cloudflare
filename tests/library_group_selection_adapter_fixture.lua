-- Synthetic SDK boundaries only; actual store/controller/eligibility are required.
plugin={}
catalogProperties={}
photoProperties={}
catalog={}
activeCatalog=catalog
photoUuid='00000000-0000-0000-0000-000000000024'
photo={catalog=catalog,properties=photoProperties}
service={localIdentifier=12}
function service:type() return 'LrPublishService' end
function service:getPluginId() return require('ConnectionCore').PLUGIN_ID end
album={localIdentifier=34}
function album:type() return 'LrPublishedCollection' end
function album:isSmartCollection() return false end
function album:getService() return service end
function album:getName() return 'Same Album Name' end
targets={photo}; sources={album}; memberships={album}
function catalog:getTargetPhotos() return targets end
function catalog:getActiveSources() return sources end
function photo:getContainedPublishedCollections() return memberships end
function photo:getRawMetadata(key) assert(key=='uuid'); return photoUuid end
function photo:getFormattedMetadata(key) assert(key=='fileName'); return 'Same Photo Name' end
function photo:getPropertyForPlugin(p,key) assert(p==plugin); return self.properties[key] end
function photo:setPropertyForPlugin(p,key,value)
    assert(inGate and p==plugin); writes=writes+1; self.properties[key]=value
end
function catalog:getPropertyForPlugin(p,key) assert(p==plugin); return catalogProperties[key] end
function catalog:setPropertyForPlugin(p,key,value)
    assert(inGate and p==plugin); writes=writes+1; catalogProperties[key]=value
end
writes=0; gate='executed'; cancelled=false
function catalog:withPrivateWriteAccessDo(fn,options)
    assert(options.timeout==5 and options.asynchronous==false)
    if beforeGate then local run=beforeGate; beforeGate=nil; run() end
    if gate~='executed' then delayed=fn; return gate end
    local selected=targets[1]
    local prior=selected.properties.groupAdditionSelections
    inGate=true
    local ok,err=pcall(fn)
    inGate=false
    if not ok then selected.properties.groupAdditionSelections=prior; error(err) end
    if afterGate then local run=afterGate; afterGate=nil; run() end
    return gate
end
deps={plugin=plugin,call=pcall,activeCatalog=function() return activeCatalog end,
    cancelled=function() return cancelled end}
for _,key in ipairs({'httpGet','httpPost','batchPost','render','upload','loadMemberships','loadHistory'}) do
    deps[key]=function() error('unexpected external operation') end
end
snapshot={state='complete',snapshotStatus='fresh',snapshotRevision=1,
    refreshedAt='2026-10-16T10:00:00Z',groups={
        {flickrGroupId='g1',displayName='Same name'},
        {flickrGroupId='g2',displayName='Same name'}}}
Adapter=require 'LibraryGroupSelectionAdapter'
function start() return Adapter.new(deps) end
function controller()
    session=assert(start())
    return assert(session:unpublishedController(snapshot))
end
