-- Synthetic SDK/storage/backend; real Lua5.1 store, batch client and response validator.
local json=require 'dkjson'
local function array(t) return setmetatable(t or {},{__jsontype='array'}) end
local function clone(t) if type(t)~='table' or t==json.null then return t end
    local c={}; for k,v in pairs(t) do c[k]=clone(v) end; return setmetatable(c,getmetatable(t)) end
properties,plugin,catalog={},{},{}
activeCatalog=catalog
identity={installationId='installation-1',linkedFlickrRevision=2}
scope={installationId='installation-1',fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',
    linkedFlickrRevision=2,sourceKind='fga_direct_upload'}
original={fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',linkRevision=2,
    sourceKind='fga_direct_upload',verificationRevision=3}
credential=string.rep('0000-',12)..'0000'
function catalog:getPropertyForPlugin(p,key) assert(p==plugin); return properties[key] end
function catalog:setPropertyForPlugin(p,key,value) assert(insideGate and p==plugin); properties[key]=value end
function catalog:withPrivateWriteAccessDo(fn,options)
    assert(not insideGate and options.asynchronous==false and options.timeout==5)
    if beforeGate then local f=beforeGate; beforeGate=nil; f() end
    insideGate=true; local ok,err=pcall(fn); insideGate=false
    if not ok then error(err) end
    return 'executed'
end
storeOptions={catalog=catalog,plugin=plugin,pcall=pcall,
    activeCatalog=function() return activeCatalog end,currentIdentity=function() return identity end}
store=require('ExistingPhotoGroupStore').new(storeOptions)
function seed(id,revision,groups)
    return store:saveChoice(scope,groups or {'group-1','group-2'},revision or 0,id or 'handoff-1',original)
end
assert(seed().state=='saved')
posts,proofs,hints,orders,attempts,clock=0,0,0,0,0,0
remote,requests={},{}
deps={store=store,client=require('GroupSubmissionClient'),workflow='existing_public_photo',
    catalog=catalog,jsonNull=json.null,call=pcall,encode=json.encode,
    decode=function(bytes)
        local v,pos,err=json.decode(bytes,1,json.null)
        if err or not bytes:sub(pos):match('^%s*$') then error('bad_json') end
        return v
    end,
    retrieve=function(key)
        if key=='fga.installation.current' then return changedCredential or credential end
        if key=='fga.installation.rotation_candidate' then return candidate end
    end,
    activeCatalog=function() return activeCatalog end,currentIdentity=function() return identity end,
    cancelled=function() return cancelledFlag==true end,now=function() return clock end,
    prove=function(photoId,revision)
        assert(not insideGate and photoId=='photo-1' and revision==2); proofs=proofs+1
        if proofHook then proofHook() end
        if proofFailure then return nil,proofFailure end
        clock=proofClock or clock
        return freshOverride or {schemaVersion=1,fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',
            linkedFlickrRevision=2,verificationRevision=proofs+3,sourceKind='fga_direct_upload',
            verifiedAt='2026-10-16T12:00:00.000000Z'}
    end,
    post=function(path,bytes,headers)
        assert(not insideGate and path=='/api/v001/group-submission-batches')
        posts=posts+1
        local request=json.decode(bytes); requests[#requests+1]=request
        local outbox=json.decode(properties.existingPhotoGroupOutboxV1)
        assert(outbox.records[1].binding.verificationRevision==3)
        if rejectBatch then return '{}',{status=409} end
        local submissions=array()
        for _,g in ipairs(request.flickrGroupIds) do
            local row=remote[g]
            local created=row==nil
            if not row then
                hints=hints+1; orders=orders+1; attempts=attempts+1
                row={fgaSubmissionIntentId='intent-'..orders,flickrGroupId=g,state='queued',
                    permanentSubmissionBlock=json.null}; remote[g]=row
            end
            local copy=clone(row); copy.created=created; submissions[#submissions+1]=copy
        end
        if batchHook then batchHook() end
        if loseResponse then return nil,{} end
        local response={schemaVersion=2,fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',submissions=submissions}
        if mutateResponse then mutateResponse(response) end
        return malformedBytes or json.encode(response),{status=responseStatus or 202}
    end}
R=require 'GroupHandoffReconciliation'
recovery=assert(R.new(deps))
function pending() return store:readHandoff(scope,'handoff-1').handoff end
function run() return recovery:reconcile(scope,'handoff-1') end
function preserved()
    local h=pending()
    assert(h.state=='prepared' and h.handoffId=='handoff-1' and h.binding.verificationRevision==3
        and h.selectionRevision==1 and h.outboxRevision==1)
end
function usePublisherStore()
    local photo={}
    function photo:getRawMetadata(key) assert(key=='uuid'); return scope.photoUuid end
    function photo:getPropertyForPlugin(p,key) assert(p==plugin); return properties[key] end
    function photo:setPropertyForPlugin(p,key,value)
        assert(insideGate and p==plugin); properties[key]=value
    end
    scope={publishServiceLocalId=1,publishedCollectionLocalId=2,
        photoUuid='00000000-0000-0000-0000-000000000001'}
    store=require('GroupSelectionStore').new{catalog=catalog,plugin=plugin,photo=photo,pcall=pcall,
        activeCatalog=function() return activeCatalog end}
    assert(store:saveChoice(scope,{'group-1','group-2'},0,'handoff-1',original).state=='saved')
    deps.store=store; deps.workflow='publisher_bound'
    recovery=assert(R.new(deps))
end
