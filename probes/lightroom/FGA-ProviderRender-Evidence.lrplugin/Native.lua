-- Copyright 2026 Terry Ott. MIT License.
-- Offline-prepared manual evidence fixture. No automatic task or network API.
local App=import 'LrApplication'
local Tasks=import 'LrTasks'
local Files=import 'LrFileUtils'
local Paths=import 'LrPathUtils'
local Date=import 'LrDate'
local Digest=import 'LrDigest'
local Dialogs=import 'LrDialogs'
local json=require 'dkjson'
local Config=require 'Config'
local Selection=require 'GroupSelectionStore'
local Attempts=require 'UploadAttemptStore'
local Evidence=require 'Evidence'
local Persistence=require 'Persistence'
local Assets=require 'NativeAssets'
local Provider=require 'OrdinaryAlbumProvider'
local M={}
local ID='com.sixbuckssolutions.fga.providerrender.evidence.lrc15'
local SERVICE='12345678-1234-4123-8123-123456789abc'
local function check(v) if not v then error('evidence_refused',0) end end
local function hash(v) return string.lower(Digest.SHA256.digest(v)) end
local function clock() return Date.timeToPosixDate(Date.currentTime()) end
local function now() return Date.timeToUserFormat(Date.currentTime(),'%Y-%m-%dT%H:%M:%SZ',true) end
local function same(a,b) return type(a)=='string' and type(b)=='string'
    and Paths.standardizePath(a)==Paths.standardizePath(b) end
local function read(path,max)
    local a=Files.fileAttributes(path)
    check(a and type(a.fileSize)=='number' and a.fileSize>0 and a.fileSize<=max)
    local file=assert(io.open(path,'rb'))
    local ok,bytes=Tasks.pcall(function() return file:read(max+1) end)
    local closed=file:close()
    check(ok and closed and type(bytes)=='string' and #bytes==a.fileSize and #bytes<=max)
    return bytes
end
local function decode(path,max)
    local bytes=read(path,max);local v,pos,err=json.decode(bytes,1,json.null)
    check(type(v)=='table' and not err and not bytes:sub(pos):find('%S'))
    return v,bytes
end
local function write(path,bytes)
    check(not Files.exists(path))
    local f=assert(io.open(path,'wb'));local ok=f:write(bytes);local closed=f:close()
    check(ok and closed)
end
local function token(v) return type(v)=='string' and #v>=1 and #v<=128
    and v:match('^[A-Za-z0-9][A-Za-z0-9._:%-]*$') end
local function digest(v) return type(v)=='string' and #v==64 and v:match('^[a-f0-9]+$') end
local function consent()
    local choice=Dialogs.runOpenPanel{title='Choose exact fresh native evidence consent',
        canChooseFiles=true,canChooseDirectories=false,allowsMultipleSelection=false,fileTypes={'json'}}
    check(choice and #choice==1)
    local consentPath=choice[1]
    local c,raw=decode(consentPath,8192)
    local keys={schemaVersion=true,owner=true,artifactSha2_256=true,manifestSha2_256=true,
        runId=true,actionId=true,phase=true,catalogPath=true,grantedAt=true,expiresAt=true,
        allowSyntheticCatalogWrites=true,allowPrivateRenderedBytes=true,
        allowSyntheticCallback=true,allowCleanup=true}
    for k in pairs(c) do check(keys[k]) end
    check(c.schemaVersion==1 and c.owner=='Terry' and digest(c.artifactSha2_256)
        and digest(c.manifestSha2_256) and token(c.runId) and token(c.actionId)
        and c.allowSyntheticCatalogWrites==true and c.allowPrivateRenderedBytes==true
        and c.allowSyntheticCallback==true and c.allowCleanup==true
        and type(c.grantedAt)=='number' and type(c.expiresAt)=='number'
        and c.expiresAt>c.grantedAt and c.expiresAt-c.grantedAt<=1800)
    local phase=false;for _,v in ipairs(Config.PHASES) do if v==c.phase then phase=true end end
    check(phase and clock()>=c.grantedAt and clock()<c.expiresAt)
    local manifest,bytes=decode(Paths.child(Paths.parent(_PLUGIN.path),'manifest.json'),131072)
    check(hash(bytes)==c.manifestSha2_256 and manifest.artifactSha2_256==c.artifactSha2_256
        and manifest.bundle=='FGA-ProviderRender-Evidence.lrplugin' and manifest.version==Config.VERSION)
    local names={};local count=0
    for _,f in ipairs(manifest.files) do
        check(type(f.path)=='string' and f.path:match('^[A-Za-z][A-Za-z0-9_]*%.lua$')
            and not names[f.path] and type(f.bytes)=='number' and f.bytes>0 and f.bytes<=2097152)
        names[f.path]=true;count=count+1
        local data=read(Paths.child(_PLUGIN.path,f.path),2097152)
        check(#data==f.bytes and hash(data)==f.sha2_256)
    end
    local actual=0
    for path in Files.directoryEntries(_PLUGIN.path) do
        check(Files.exists(path)=='file' and names[Paths.leafName(path)]);actual=actual+1
    end
    check(actual==count and names['Native.lua'] and names['EvidenceProvider.lua']
        and names['Persistence.lua'] and names['MetadataDefinition.lua'])
    local catalog=App.activeCatalog();local version=App.versionTable()
    check(version.major==15 and version.minor==6 and _PLUGIN.id==ID
        and same(c.catalogPath,catalog:getPath())
        and Paths.leafName(c.catalogPath)=='FGA-NativeEvidence-Disposable.lrcat')
    local services=catalog:getPublishServices(nil)
    check(#services==1 and services[1]:getPluginId()==ID
        and #services[1]:getChildCollectionSets()==0)
    local directory=Paths.child(Paths.parent(c.catalogPath),'FGA-native-evidence-v1')
    -- Documented SDK attributes/resolveAlias do not prove Windows reparse-point
    -- identity or atomic exclusive file creation. The fixed paths below are
    -- scope checks only; readiness stays false pending a reviewed boundary.
    -- Expiry fences later operations; it cannot abort/bound waitForRender.
    local function valid()
        if App.activeCatalog()~=catalog or not same(catalog:getPath(),c.catalogPath)
            or clock()<c.grantedAt or clock()>=c.expiresAt then return false end
        local ok,current=Tasks.pcall(read,consentPath,8192)
        return ok and current==raw
    end
    check(valid())
    -- Consume before writes, rendering, or store operations. Unknown outcomes
    -- remain consumed; a new action ID cannot replay an already used phase.
    local field='nativeEvidenceActionsV1'
    local expected
    local callbackOpen=true
    local worked,result=Tasks.pcall(function() return catalog:withPrivateWriteAccessDo(function()
        check(callbackOpen and valid())
        local prior=catalog:getPropertyForPlugin(_PLUGIN,field)
        local doc={schemaVersion=1,runId=c.runId,artifactSha2_256=c.artifactSha2_256,
            catalogKey=hash(Paths.standardizePath(c.catalogPath)),
            serviceId=tostring(services[1].localIdentifier),phases={}}
        if prior~=nil then
            check(type(prior)=='string' and #prior<=4096)
            local value,pos,reason=json.decode(prior,1,json.null)
            check(type(value)=='table' and not reason and not prior:sub(pos):find('%S')
                and value.schemaVersion==1 and value.runId==c.runId
                and value.artifactSha2_256==c.artifactSha2_256
                and value.catalogKey==doc.catalogKey and value.serviceId==doc.serviceId
                and type(value.phases)=='table')
            doc=value
        end
        local count=0
        for phase,action in pairs(doc.phases) do
            count=count+1;check(token(action) and action~=c.actionId)
            local known=false;for _,v in ipairs(Config.PHASES) do if phase==v then known=true end end
            check(known)
        end
        for index,phase in ipairs(Config.PHASES) do
            check((doc.phases[phase]~=nil)==(index<=count))
        end
        check(count<5 and doc.phases[c.phase]==nil and Config.PHASES[count+1]==c.phase)
        local statuses={prepare='synthetic_scope_prepared',default_callback='default_refused',
            album_callback='private_render_staged',restart_prepare='prepared_readback'}
        for phase,action in pairs(doc.phases) do
            local receipt=decode(Paths.child(directory,action..'-receipt.json'),8192)
            check(receipt.schemaVersion==1 and receipt.fixtureVersion==Config.VERSION
                and receipt.phase==phase and receipt.actionId==action and receipt.runId==c.runId
                and receipt.artifactSha2_256==c.artifactSha2_256 and receipt.status==statuses[phase])
        end
        doc.phases[c.phase]=c.actionId
        expected=assert(json.encode(doc));check(#expected<=4096 and callbackOpen and valid())
        catalog:setPropertyForPlugin(_PLUGIN,field,expected)
    end,{timeout=5,asynchronous=false}) end)
    callbackOpen=false
    check(worked and result=='executed' and valid() and expected~=nil
        and catalog:getPropertyForPlugin(_PLUGIN,field)==expected)
    return {c=c,catalog=catalog,service=services[1],directory=directory,valid=valid}
end
local function objects(s)
    check(s.valid())
    local all=s.catalog:getAllPhotos();check(#all==1)
    local photo=all[1];local source=Paths.child(s.directory,'synthetic.tif')
    check(s.catalog:findPhotoByPath(source)==photo and read(source,131072)==Assets.tiff())
    local album,default;local count=0
    for _,v in ipairs(s.service:getChildCollections()) do
        count=count+1;local info=v:getCollectionInfoSummary()
        if info.isDefaultCollection==true then check(not default);default=v
        else check(not album and v:isSmartCollection()==false and v:getService()==s.service
            and info.remoteId==nil and info.remoteUrl==nil
            and info.collectionSettings.schemaVersion==1
            and info.collectionSettings.albumLifecycle=='local_unbound');album=v end
    end
    check(count==2 and album and default and #album:getPhotos()==1 and album:getPhotos()[1]==photo)
    local defaults=default:getPhotos()
    check(#defaults<=1 and (#defaults==0 or defaults[1]==photo))
    return photo,album,default
end
local function saveReceipt(s,row)
    check(s.valid());row.schemaVersion=1;row.phase=s.c.phase
    row.fixtureVersion=Config.VERSION;row.artifactSha2_256=s.c.artifactSha2_256
    row.runId=s.c.runId;row.actionId=s.c.actionId
    row.nativeSchedulingProven=false;row.productionQualified=false
    write(Paths.child(s.directory,s.c.actionId..'-receipt.json'),assert(json.encode(row,{indent=true}))..'\n')
end
local function seed(s,photo,album)
    local key={publishServiceLocalId=s.service.localIdentifier,
        publishedCollectionLocalId=album.localIdentifier,photoUuid=photo:getRawMetadata('uuid')}
    local store=Selection.new{catalog=s.catalog,photo=photo,plugin=_PLUGIN,pcall=Tasks.pcall,
        activeCatalog=function() return s.valid() and s.catalog or nil end}
    check(store:saveChoice(key,{'synthetic-group-1'},0).state=='saved')
    local frozen=store:prepare(key,1,'evidence-restart-handoff')
    check(frozen.state=='prepared')
    local scope={};for k,v in pairs(key) do scope[k]=v end;scope.fgaPublishServiceId=SERVICE
    local activation={}
    local attempts=Attempts.new{catalog=s.catalog,plugin=_PLUGIN,activationToken=activation,
        activeCatalog=function() return s.valid() and s.catalog or nil end,
        currentActivation=function() return activation end,
        isOwner=function(k) return s.valid() and k.photoUuid==key.photoUuid end,
        pcall=Tasks.pcall,readRemoteId=function() return nil end}
    local inspected=attempts:inspect(scope,photo,now())
    check(inspected.state=='ready' and inspected.classification=='unpublished')
    local null=json.null
    local result=attempts:prepare(scope,photo,inspected.fence,
        {selectionKind='groups',selectionRevision=1,flickrGroupIds={'synthetic-group-1'}},
        {fgaAlbumBindingId=null,albumBindingRevision=null},now())
    check(result.state=='prepared')
end
local function persistence(s,photo,album)
    return Persistence.new{catalog=s.catalog,photo=photo,plugin=_PLUGIN,pcall=Tasks.pcall,
        hash=hash,activeCatalog=App.activeCatalog,
        scope={artifactSha2_256=s.c.artifactSha2_256,runId=s.c.runId,
            catalogKey=hash(Paths.standardizePath(s.c.catalogPath)),
            serviceId=tostring(s.service.localIdentifier),albumId=tostring(album.localIdentifier),
            photoUuid=photo:getRawMetadata('uuid')},
        guard=function(phase,action)
            return s.valid() and action==s.c.actionId
                and s.c.phase==(phase=='prepare' and 'restart_prepare' or 'restart_observe')
        end}
end
local function prepare(s)
    check(s.c.phase=='prepare' and #s.catalog:getAllPhotos()==0 and not Files.exists(s.directory))
    local existing=s.service:getChildCollections();check(#existing==1)
    check(existing[1]:getCollectionInfoSummary().isDefaultCollection==true)
    check(s.valid());Files.createDirectory(s.directory);check(Files.exists(s.directory)=='directory')
    check(s.valid());write(Paths.child(s.directory,'synthetic.tif'),Assets.tiff())
    local photo,album,finished
    local callbackOpen=true
    local function current() check(callbackOpen and s.valid()) end
    local worked,result=Tasks.pcall(function()
        return s.catalog:withWriteAccessDo('Prepare generated native evidence',function()
            current();photo=assert(s.catalog:addPhoto(Paths.child(s.directory,'synthetic.tif')))
            current();album=assert(s.service:createPublishedCollection('Synthetic Evidence Album',nil,false))
            current();album:setCollectionSettings{schemaVersion=1,albumLifecycle='local_unbound'}
            current();album:addPhotos{photo}
            current();existing[1]:addPhotos{photo}
            current();finished=true
        end,{timeout=5,asynchronous=false})
    end)
    callbackOpen=false
    check(worked and result=='executed' and finished and s.valid())
    objects(s);saveReceipt(s,{status='synthetic_scope_prepared',networkCalls=0})
end
function M.run()
    check(Config.NATIVE_SCOPE_READY==true)
    Tasks.startAsyncTask(function()
        local ok=Tasks.pcall(function()
            local s=consent()
            if s.c.phase=='prepare' then prepare(s)
            elseif s.c.phase=='restart_prepare' or s.c.phase=='restart_observe' then
                local photo,album=objects(s)
                if s.c.phase=='restart_prepare' then seed(s,photo,album) end
                local p=persistence(s,photo,album)
                local result=s.c.phase=='restart_prepare' and p:prepare(s.c.actionId) or p:observe(s.c.actionId)
                saveReceipt(s,{status=result.state,restart=result,networkCalls=0})
            else error('Use exact synthetic provider callback action',0) end
        end)
        Dialogs.message('Native evidence phase',ok and 'Private receipt saved; independent review required.'
            or 'Phase refused or incomplete. Preserve disposable catalog and evidence.','info')
    end)
end
function M.callback(_functionContext,exportContext)
    check(Config.NATIVE_SCOPE_READY==true)
    -- Only this registered SDK entry observes the SDK-created context. Neither
    -- test injections nor menu-created records are labeled actual callbacks.
    local s=consent()
    check(s.c.phase=='default_callback' or s.c.phase=='album_callback')
    local photo,album,default=objects(s)
    check(type(exportContext)=='table' and exportContext.publishService==s.service
        and exportContext.publishedCollectionInfo~=nil)
    local selected=0
    for candidate in exportContext.exportSession:photosToExport() do
        selected=selected+1;check(selected==1 and candidate==photo)
    end
    check(selected==1 and s.valid())
    local wanted=s.c.phase=='default_callback' and default or album
    check(exportContext.publishedCollection==wanted)
    local row={status='callback_entry_observed',callbackEntryInvoked=true,
        sdkCallbackOriginProven=false,hostMeasurementRequired=true,
        registeredEntry='processRenderedPhotos',pluginRenderRequests=0,networkCalls=0,
        syntheticAuthorizationOnly=true,renderCompletionProven=false,
        hostDrainEvidenceRequired=true,preserveNativeWorkRequired=true,nativeActionStillUnavailable=true,
        filesystemIdentityProven=false,atomicOutputCreationProven=false,
        hostWaitBoundProven=false,consentValiditySeconds=1800}
    local provider=Provider.new{pcall=Tasks.pcall,pluginId=ID,verifyService=function()
        check(s.valid());return {ok=true,linkStatus='ready',identity={schemaVersion=1,
            serviceRevision=1,fgaPublishServiceId=SERVICE,linkedFlickrRevision=1,
            issuingInstallationId='synthetic-evidence-only'}}
    end}
    local target=provider.validateTarget(exportContext.propertyTable,exportContext)
    if s.c.phase=='default_callback' then
        check(not target.ok and target.code=='album_required')
        row.status='default_refused';row.authorizationCalls=0
        saveReceipt(s,row);return
    end
    check(target.ok)
    local actualSettings=exportContext.propertyTable
    check(actualSettings.LR_format=='PNG'
        and actualSettings.LR_export_destinationType=='specificFolder'
        and same(actualSettings.LR_export_destinationPathPrefix,Paths.child(s.directory,'render'))
        and actualSettings.LR_export_useSubfolder==false)
    local validatedBytes
    local instrument=Evidence.new{guard=s.valid,authorize=function() return true end,
        stage=function(path,size)
            check(s.valid())
            local destination=Paths.child(s.directory,s.c.actionId..'-rendered.png')
            check(not Files.exists(destination))
            check(type(validatedBytes)=='string' and #validatedBytes==size)
            -- Stage the exact bounded bytes validated from the opened source;
            -- never reopen an attacker-replaced path after authorization.
            write(destination,validatedBytes)
            return s.valid()
        end}
    local denied,why=instrument:beforeReady();check(denied==nil and why=='source_not_ready')
    local count=0
    exportContext:configureProgress{title='Synthetic native evidence'}
    local completed=Tasks.pcall(function()
    for _,rendition in exportContext:renditions{stopIfCanceled=true} do
        count=count+1;check(count==1 and rendition.photo==photo and s.valid())
        row.pluginRenderRequests=row.pluginRenderRequests+1
        local rendered,path=rendition:waitForRender()
        check(rendered==true and rendition.wasSkipped==false and type(path)=='string'
            and same(Paths.parent(path),Paths.child(s.directory,'render'))
            and Files.exists(path)=='file')
        local attributes=Files.fileAttributes(path)
        check(attributes and type(attributes.fileSize)=='number'
            and attributes.fileSize>=1 and attributes.fileSize<=33554432)
        local opened=assert(io.open(path,'rb'))
        local readOk,bytes=Tasks.pcall(function() return opened:read(33554433) end)
        local closed=opened:close()
        check(readOk and closed and type(bytes)=='string' and #bytes==attributes.fileSize
            and #bytes<=33554432 and s.valid())
        local png=Assets.inspect(bytes)
        check(png and png.format=='PNG' and png.bitDepth==8 and png.width==8 and png.height==8)
        validatedBytes=bytes
        row.renderedPngSha2_256=hash(validatedBytes);row.renderedPngBytes=#validatedBytes
        check(instrument:renderReady(path,#validatedBytes)==true)
        validatedBytes=nil
        row.renderCompletionProven=true
    end
    check(count==1)
    end)
    row.ordering=instrument:receipt()
    if not completed then
        row.status='render_or_validation_failed';row.renderCompletionProven=false
        row.preserveNativeWorkRequired=true
        saveReceipt(s,row);return
    end
    row.status='private_render_staged'
    row.nativeCallbackTimingDoesNotProvePreRenderPreparation=true
    saveReceipt(s,row)
end
return M
