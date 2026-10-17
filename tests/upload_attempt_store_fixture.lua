-- Synthetic transactional SDK boundary. No host, files, photos or network.
catalog,plugin,photo,token={},{},{},{}
active,activation,owner=catalog,token,true
properties,photoProperties={},{}
uuid="00000000-0000-0000-0000-000000000095"
function photo:getRawMetadata(key) assert(key=="uuid"); return uuid end
function catalog:findPhotoByUuid(id) return not detachedPhoto and id==uuid and photo or nil end
function catalog:getPropertyForPlugin(p,key)
    assert(p==plugin and key=="uploadAttemptRecoveryStore")
    if readFailure then error("PRIVATE synthetic failure") end
    return properties[key]
end
function photo:getPropertyForPlugin(p,key)
    assert(p==plugin and key=="publishedPhotoCorrelations")
    return photoProperties[key]
end
function catalog:setPropertyForPlugin(p,key,value)
    assert(inside and p==plugin and key=="uploadAttemptRecoveryStore")
    properties[key]=value; writes=writes+1
    if failAt=="catalog" then error("PRIVATE synthetic full/IO failure") end
end
function photo:setPropertyForPlugin(p,key,value)
    assert(inside and p==plugin and key=="publishedPhotoCorrelations")
    photoProperties[key]=value; writes=writes+1
    if failAt=="photo" then error("PRIVATE synthetic photo failure") end
end
gateStatus,writes="executed",0
function catalog:withPrivateWriteAccessDo(callback,options)
    assert(options.timeout==5 and options.asynchronous==false and not inside)
    if beforeGate then local hook=beforeGate; beforeGate=nil; hook() end
    if gateStatus~="executed" then delayed=callback; return gateStatus end
    local a,b=properties.uploadAttemptRecoveryStore,photoProperties.publishedPhotoCorrelations
    inside=true; local ok,err=pcall(callback); inside=false
    if not ok then properties.uploadAttemptRecoveryStore=a; photoProperties.publishedPhotoCorrelations=b; error(err) end
    if afterGate then local hook=afterGate; afterGate=nil; hook() end
    return gateStatus
end
options={catalog=catalog,plugin=plugin,pcall=pcall,activationToken=token,
    activeCatalog=function() return active end,currentActivation=function() return activation end,
    isOwner=function() return owner end,readRemoteId=function() return remoteId end}
