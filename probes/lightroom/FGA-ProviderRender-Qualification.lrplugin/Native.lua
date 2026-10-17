-- Copyright 2026 Terry Ott. MIT License.
-- Explicit native qualification dispatcher. No network or credential imports.
-- Fault rows inject at named boundaries around REAL SDK objects. They do not
-- assert that the host itself produced the injected failure or catalog switch.
local App=import 'LrApplication'
local Tasks=import 'LrTasks'
local Files=import 'LrFileUtils'
local Paths=import 'LrPathUtils'
local Date=import 'LrDate'
local Digest=import 'LrDigest'
local Dialogs=import 'LrDialogs'
local ExportSession=import 'LrExportSession'
local json=require 'dkjson'
local Config=require 'Config'
local Assets=require 'NativeAssets'
local Selection=require 'GroupSelectionStore'
local Attempts=require 'UploadAttemptStore'
local Provider=require 'OrdinaryAlbumProvider'
local Qualification=require 'Qualification'
local M={}
local ID='com.sixbuckssolutions.fga.providerrender.qualification.lrc15'
local SERVICE='12345678-1234-4123-8123-123456789abc'
local function check(value) if not value then error('qualification_refused',0) end end
local function hash(bytes) return string.lower(Digest.SHA256.digest(bytes)) end
local function digestIdentity(value)
    return type(value)=='string' and #value==64 and value:match('^[a-f0-9]+$')~=nil
end
local function hostProvenance(version)
    local result={}
    for _,key in ipairs({'major','minor','revision','build'}) do
        local value=version[key]
        if type(value)=='number' and value>=0 and value<=9007199254740991
            and value%1==0 then result[key]=value end
    end
    if type(version.build_version)=='string' and #version.build_version<=64
        and version.build_version:match('^[A-Za-z0-9._%-]+$') then
        result.buildVersion=version.build_version
    end
    return result
end
local function clock() return Date.timeToPosixDate(Date.currentTime()) end
local function timestamp()
    return Date.timeToUserFormat(Date.currentTime(),'%Y-%m-%dT%H:%M:%SZ',true)
end
local function readJson(path,limit)
    local a=Files.fileAttributes(path)
    check(a and type(a.fileSize)=='number' and a.fileSize>0 and a.fileSize<=limit)
    local bytes=Files.readFile(path)
    local value,position,reason=json.decode(bytes,1,json.null)
    check(type(value)=='table' and not reason and not bytes:sub(position):find('%S'))
    return value,bytes
end
local function samePath(a,b)
    return type(a)=='string' and type(b)=='string'
        and Paths.standardizePath(a)==Paths.standardizePath(b)
end
local function write(path,bytes)
    local file=assert(io.open(path,'wb'))
    local good=file:write(bytes);local closed=file:close();check(good and closed)
end
-- The owner retains BOTH digests outside this package. The manifest digest
-- authenticates its exact bytes; every listed bundle member is checked before
-- any catalog write. Consent is an operator record, not a remote authority.
local function scope(consentPath)
    local c,consentBytes=readJson(consentPath,8192)
    local keys={schemaVersion=true,owner=true,artifactSha2_256=true,
        manifestSha2_256=true,catalogPath=true,grantedAt=true,expiresAt=true,
        allowQualificationProvider=true,allowSyntheticCatalogWrites=true,
        allow200000001ByteScratch=true,allowCleanup=true}
    for k in pairs(c) do check(keys[k]) end
    check(c.schemaVersion==1 and c.owner=='Terry' and digestIdentity(c.artifactSha2_256)
        and digestIdentity(c.manifestSha2_256) and c.allowQualificationProvider==true
        and c.allowSyntheticCatalogWrites==true and c.allow200000001ByteScratch==true
        and c.allowCleanup==true and type(c.grantedAt)=='number'
        and type(c.expiresAt)=='number' and c.expiresAt>c.grantedAt
        and c.expiresAt-c.grantedAt<=1800 and clock()>=c.grantedAt and clock()<c.expiresAt)
    local parent=Paths.parent(_PLUGIN.path)
    local manifest,bytes=readJson(Paths.child(parent,'manifest.json'),131072)
    check(hash(bytes)==c.manifestSha2_256 and manifest.artifactSha2_256==c.artifactSha2_256
        and manifest.bundle=='FGA-ProviderRender-Qualification.lrplugin'
        and manifest.version==Config.VERSION and manifest.hostVersion=='15.6')
    local names={};local count=0
    for _,f in ipairs(manifest.files) do
        check(type(f.path)=='string' and f.path:match('^[A-Za-z][A-Za-z0-9_]*%.lua$')
            and not names[f.path])
        names[f.path]=true;count=count+1
        local raw=Files.readFile(Paths.child(_PLUGIN.path,f.path))
        check(type(raw)=='string' and #raw==f.bytes and hash(raw)==f.sha2_256)
    end
    local actual=0
    for path in Files.directoryEntries(_PLUGIN.path) do
        check(Files.exists(path)=='file' and names[Paths.leafName(path)]);actual=actual+1
    end
    check(actual==count and names['Native.lua'] and names['NativeAssets.lua']
        and names['QualificationProvider.lua'] and names['MetadataDefinition.lua'])
    local catalog=App.activeCatalog()
    local version=App.versionTable()
    check(version.major==15 and version.minor==6 and samePath(c.catalogPath,catalog:getPath())
        and Paths.leafName(catalog:getPath())=='FGA-ProviderRender-Disposable.lrcat'
        and #catalog:getAllPhotos()==0 and _PLUGIN.id==ID)
    local services=catalog:getPublishServices(nil)
    check(#services==1 and services[1]:getPluginId()==ID
        and #services[1]:getChildCollectionSets()==0)
    for _,album in ipairs(services[1]:getChildCollections()) do
        local info=album:getCollectionInfoSummary()
        check(info.isDefaultCollection==true and #album:getPhotos()==0
            and info.remoteId==nil and info.remoteUrl==nil)
    end
    check(catalog:getPropertyForPlugin(_PLUGIN,Selection.OUTBOX_FIELD)==nil
        and catalog:getPropertyForPlugin(_PLUGIN,Attempts.STORE_FIELD)==nil)
    local directory=Paths.child(Paths.parent(catalog:getPath()),'FGA-provider-render-qualification-v1')
    check(not Files.exists(directory))
    local revoked=false
    local allowedPhotos={}
    local function valid()
        if revoked or App.activeCatalog()~=catalog or not samePath(catalog:getPath(),c.catalogPath)
            or clock()<c.grantedAt or clock()>=c.expiresAt then return false end
        for _,photo in ipairs(catalog:getAllPhotos()) do
            if not allowedPhotos[photo] then return false end
        end
        local ok,current=Tasks.pcall(Files.readFile,consentPath)
        return ok and current==consentBytes
    end
    return {catalog=catalog,service=services[1],directory=directory,
        valid=valid,revoke=function() revoked=true end,
        allowPhoto=function(photo) allowedPhotos[photo]=true end,artifact=c.artifactSha2_256,
        host=hostProvenance(version)}
end
local function prepareChoice(s,photo,album,groups,revision)
    local store=Selection.new{catalog=s.catalog,photo=photo,plugin=_PLUGIN,
        pcall=Tasks.pcall,activeCatalog=function() return s.valid() and s.catalog or nil end}
    local key={publishServiceLocalId=s.service.localIdentifier,
        publishedCollectionLocalId=album.localIdentifier,photoUuid=photo:getRawMetadata('uuid')}
    check(store:saveChoice(key,groups,revision or 0).state=='saved')
end
local expected={selection_absent='handed_off',selection_none='handed_off',
    selection_groups='handed_off',selection_edit_after_freeze='handed_off',
    photo_failure_isolation='handed_off',target_rejected='scope_invalid',
    catalog_changed='context_stale',activation_changed='context_stale',
    cancelled='cancelled',render_failed='render_failed',missing_file='missing_file',
    oversized_file='oversized',file_changed='file_changed',cleanup_revocation='handed_off'}
-- A raw SDK wait is attempted once. Boolean success/failure is a terminal
-- observation; an exception/nonboolean is unknown and must never be retried.
-- The separately granted cleanup authority may wait after run revocation, but
-- does not decode bytes, invoke a consumer, cancel or claim a hard stop.
local function waitNative(entry,owned)
    if not entry.attempted then
        entry.attempted=true
        local worked,rendered,path=Tasks.pcall(function() return entry.rendition:waitForRender() end)
        entry.terminal=worked and (rendered==true or rendered==false)
        if worked then entry.rendered=rendered end
        if entry.terminal and rendered==true then
            if type(path)=='string' and samePath(Paths.parent(path),entry.output) then
                entry.path=path;owned.files[#owned.files+1]=path
            else entry.outputUnresolved=true end
        end
    end
    if not entry.terminal or entry.outputUnresolved then return nil,'native_completion_unknown' end
    return entry.rendered,entry.path
end
local function drain(owned)
    local proven,observed,terminal=true,0,0
    for _,state in ipairs(owned.sessions) do
        for _,entry in ipairs(state.entries) do
            waitNative(entry,owned)
            observed=observed+1
            if entry.terminal and not entry.outputUnresolved then terminal=terminal+1 end
        end
        if not state.enumeratedComplete or state.expected~=#state.entries then proven=false end
    end
    return proven and observed==terminal,observed,terminal
end
local function runCase(s,album,caseId,index,photos,owned)
    check(s.valid())
    local injected=caseId~='selection_absent' and caseId~='selection_none'
        and caseId~='selection_groups' and caseId~='cleanup_revocation'
    local row={caseId=caseId,terminal=false,ok=false,faultRequested=injected,
        boundaryFaultInjected=false,
        nativeSchedulingProven=false,productionQualified=false,renderCalls=0}
    local photo=photos[index]
    local candidates={photo}
    if caseId=='photo_failure_isolation' then candidates={photos[15],photo} end
    if caseId=='selection_none' then prepareChoice(s,photo,album,{}) end
    if caseId=='selection_groups' or caseId=='selection_edit_after_freeze' then
        prepareChoice(s,photo,album,{'synthetic-group-1'})
    end
    if caseId=='photo_failure_isolation' then
        s.catalog:withPrivateWriteAccessDo(function()
            check(s.valid());photos[15]:setPropertyForPlugin(_PLUGIN,Selection.SELECTION_FIELD,'invalid')
        end)
        row.boundaryFaultInjected=true
    end
    local output=Paths.child(s.directory,'render-'..string.format('%02d',index))
    Files.createDirectory(output);check(Files.exists(output)=='directory')
    owned.directories[#owned.directories+1]=output
    local settings={LR_format=caseId=='selection_none' and 'JPEG' or 'PNG',
        LR_export_destinationType='specificFolder',LR_export_destinationPathPrefix=output,
        LR_export_useSubfolder=false,LR_collisionHandling='overwrite',LR_renamingTokensOn=false,
        LR_outputSharpeningOn=false,LR_useWatermark=false,LR_minimizeEmbeddedMetadata=true}
    local identity={schemaVersion=1,serviceRevision=1,fgaPublishServiceId=SERVICE,
        linkedFlickrRevision=1,issuingInstallationId='synthetic-qualification-only'}
    local providerDeps={pcall=Tasks.pcall,pluginId=ID,verifyService=function()
        return {ok=true,linkStatus='ready',identity=identity}
    end}
    local provider=Provider.newQualification(providerDeps)
    provider.updateExportSettings(settings)
    -- The dispatcher record is not an SDK LrExportContext. All object-valued
    -- fields below ARE the real SDK catalog/service/collection/photo/session.
    local session=ExportSession{photosToExport=candidates,exportSettings=settings}
    local info=album:getCollectionInfoSummary()
    if caseId=='target_rejected' then
        info.isDefaultCollection=true;row.boundaryFaultInjected=true
    end
    local context={propertyTable=settings,exportSession=session,publishService=s.service,
        publishedCollection=album,publishedCollectionInfo=info}
    local token={};local activation=token;local cancelled=false;local catalogCurrent=true
    local fixture=assert(Qualification.newQualification{caseId=caseId,guard=s.valid,
        scope={disposable=true,syntheticOnly=true,catalogIdentity=s.catalog,
            activeCatalog=App.activeCatalog},providerDependencies=providerDeps})
    owned.fixtures[#owned.fixtures+1]=fixture
    local deps={plugin=_PLUGIN,pcall=Tasks.pcall,activationToken=token,
        currentActivation=function() return activation end,
        activeCatalog=function() return catalogCurrent and App.activeCatalog() or nil end,
        cancelled=function() return cancelled or not s.valid() end,
        isOwner=function(key)
            if not s.valid() or activation~=token then return false end
            for _,candidate in ipairs(candidates) do
                if candidate:getRawMetadata('uuid')==key.photoUuid then return true end
            end
            return false
        end,
        identityCurrent=function(t) return t.fgaPublishServiceId==SERVICE and t.linkedFlickrRevision==1 end,
        readRemoteId=function(p)
            local remote
            for _,published in ipairs(album:getPublishedPhotos()) do
                if published:getPhoto()==p then
                    check(remote==nil);remote=published:getRemoteId()
                end
            end
            return remote
        end}
    local handle,reason=fixture:prepare(context,{contextDependencies=deps,now=timestamp,
        handoffId=function(p) return 'qualification-'..caseId..'-'..p:getRawMetadata('uuid') end})
    row.preparationReturnedBeforeRenditions=true
    if not handle then
        row.code=reason;row.ok=reason==expected[caseId]
            and (not row.faultRequested or row.boundaryFaultInjected)
        row.faultStatus=row.faultRequested and (row.boundaryFaultInjected and 'applied' or 'not_applied')
            or 'not_requested'
        row.terminal=true
        fixture:finish();return row
    end
    local journal=assert(json.decode(s.catalog:getPropertyForPlugin(_PLUGIN,Attempts.STORE_FIELD)))
    local frozen
    for _,record in ipairs(journal.attempts) do
        if record.photoUuid==photo:getRawMetadata('uuid') then frozen=record end
    end
    check(frozen and frozen.uploadPhase=='prepared')
    row.durableAttemptReadBackBeforeRenditions=true
    row.frozenSelectionKind=frozen.selectionKind
    if caseId=='selection_absent' then check(frozen.selectionKind=='absent') end
    if caseId=='selection_none' then check(frozen.selectionKind=='none') end
    if caseId=='selection_groups' or caseId=='selection_edit_after_freeze' then
        check(frozen.selectionKind=='groups' and #frozen.flickrGroupIds==1
            and frozen.flickrGroupIds[1]=='synthetic-group-1')
    end
    if caseId=='selection_edit_after_freeze' then
        prepareChoice(s,photo,album,{'synthetic-group-2'},1)
        row.editAfterFreeze=true;row.boundaryFaultInjected=true
    end
    if caseId=='photo_failure_isolation' then check(session:countRenditions()==1) end
    if caseId=='catalog_changed' then catalogCurrent=false;row.boundaryFaultInjected=true end
    if caseId=='activation_changed' then activation={};row.boundaryFaultInjected=true end
    if caseId=='cancelled' then cancelled=true;row.boundaryFaultInjected=true end
    local heldLease,lastRendition;local count=0
    local state={expected=session:countRenditions(),entries={},enumeratedComplete=false,
        potentiallyActive=true}
    check(type(state.expected)=='number' and state.expected>=0 and state.expected%1==0)
    owned.sessions[#owned.sessions+1]=state
    -- FIRST render-triggering call in the dispatcher; all preparation and
    -- durable readback above have already returned in this SDK task.
    for _,rendition in session:renditions() do
        local entry={rendition=rendition,output=output,attempted=false,terminal=false}
        state.entries[#state.entries+1]=entry
        check(s.valid());count=count+1
        local proxy={photo=rendition.photo,waitForRender=function()
            row.renderCalls=row.renderCalls+1
            local rendered,path=waitNative(entry,owned)
            if rendered~=true then
                row.nativeRenderFailed=rendered==false
                return rendered,path
            end
            check(s.valid())
            local bytes=Files.readFile(path)
            row.file=Assets.inspect(bytes)
            check(row.file.format==settings.LR_format and row.file.bitDepth==8
                and row.file.width==8 and row.file.height==8)
            row.requestedColorSpace=settings.LR_export_colorSpace
            if caseId=='render_failed' then
                row.boundaryFaultInjected=true;return false,'injected_render_failure'
            end
            if caseId=='missing_file' then
                check(Files.delete(path));row.boundaryFaultInjected=true
            end
            if caseId=='oversized_file' then
                local file=assert(io.open(path,'wb'));local chunk=string.rep('x',1000000)
                local wrote=Tasks.pcall(function()
                    for _=1,200 do check(s.valid());check(file:write(chunk)) end
                    check(file:write('x'))
                end)
                local closed=file:close();check(wrote and closed)
                row.boundaryFaultInjected=true
            end
            return true,path
        end}
        lastRendition=proxy
        local result=fixture:process(handle,proxy,function(lease)
            heldLease=lease
            if caseId=='file_changed' then
                local path=owned.files[#owned.files];local bytes=Files.readFile(path)
                write(path,bytes:sub(1,#bytes-1)..string.char((bytes:byte(#bytes)+1)%256))
                row.boundaryFaultInjected=true
            end
            return type(lease:read())=='string'
        end)
        row.code=result and result.code or 'unresolved'
    end
    state.enumeratedComplete=true
    row.actualRenditions=count
    row.ok=count==1 and row.code==expected[caseId]
        and (not row.faultRequested or row.boundaryFaultInjected)
    row.faultStatus=row.faultRequested and (row.boundaryFaultInjected and 'applied' or 'not_applied')
        or 'not_requested'
    fixture:finish()
    if heldLease then
        local bytes,why=heldLease:read();row.byteLeaseRevoked=bytes==nil and why=='lease_expired'
        row.ok=row.ok and row.byteLeaseRevoked
    end
    if caseId=='cleanup_revocation' then
        local result,why=fixture:process(handle,lastRendition,function() return false end)
        row.cleanupHandleRevoked=result==nil and why=='fixture_closed'
        row.ok=row.ok and row.cleanupHandleRevoked
    end
    row.terminal=true
    return row
end
local function cleanup(s,owned,album)
    local receipt={scopeRevoked=true,privateRecordsCleared=false,albumDeleted=false,
        ownedFilesDeleted=false,catalogDisposalRequired=true,importedSyntheticPhotos=#owned.photos}
    s.revoke()
    for _,fixture in ipairs(owned.fixtures) do fixture:finish() end
    local completed,proven,observed,terminal=Tasks.pcall(drain,owned)
    receipt.renderSessions=#owned.sessions
    receipt.renderCompletionProven=completed and proven==true
    receipt.observedRenditions=completed and observed or 0
    receipt.terminalRenditions=completed and terminal or 0
    if not receipt.renderCompletionProven then
        receipt.preservedForUnresolvedRender=true
        receipt.catalogCleanupCompleted=false
        return receipt
    end
    receipt.ownedFilesDeleted=true
    -- Cleanup authority is granted separately in consent and remains valid after
    -- run expiry/revocation. It only touches captured objects in this catalog.
    if App.activeCatalog()==s.catalog then
        local ok=Tasks.pcall(function()
            s.catalog:withPrivateWriteAccessDo(function()
                s.catalog:setPropertyForPlugin(_PLUGIN,Selection.OUTBOX_FIELD,nil)
                s.catalog:setPropertyForPlugin(_PLUGIN,Attempts.STORE_FIELD,nil)
                for _,photo in ipairs(owned.photos) do
                    photo:setPropertyForPlugin(_PLUGIN,Selection.SELECTION_FIELD,nil)
                    photo:setPropertyForPlugin(_PLUGIN,Attempts.PHOTO_FIELD,nil)
                end
            end)
            receipt.privateRecordsCleared=s.catalog:getPropertyForPlugin(_PLUGIN,Selection.OUTBOX_FIELD)==nil
                and s.catalog:getPropertyForPlugin(_PLUGIN,Attempts.STORE_FIELD)==nil
            for _,photo in ipairs(owned.photos) do
                receipt.privateRecordsCleared=receipt.privateRecordsCleared
                    and photo:getPropertyForPlugin(_PLUGIN,Selection.SELECTION_FIELD)==nil
                    and photo:getPropertyForPlugin(_PLUGIN,Attempts.PHOTO_FIELD)==nil
            end
            if album then
                s.catalog:withWriteAccessDo('Remove qualification Album',function() album:delete() end)
                receipt.albumDeleted=true
                for _,candidate in ipairs(s.service:getChildCollections()) do
                    if candidate==album then receipt.albumDeleted=false end
                end
            end
        end)
        receipt.catalogCleanupCompleted=ok and receipt.privateRecordsCleared and receipt.albumDeleted
    else receipt.catalogCleanupCompleted=false end
    for _,path in ipairs(owned.files) do
        if Files.exists(path) and not Files.delete(path) then receipt.ownedFilesDeleted=false end
    end
    for _,path in ipairs(owned.directories) do
        local empty=true;for _ in Files.directoryEntries(path) do empty=false end
        -- Never recursively delete a directory with unexpected host output.
        if empty then
            if Files.exists(path) and not Files.delete(path) then receipt.ownedFilesDeleted=false end
        else receipt.ownedFilesDeleted=false end
    end
    return receipt
end
function M.run()
    Tasks.startAsyncTask(function()
        local selected=Dialogs.runOpenPanel{title='Choose Terry action-time qualification consent',
            canChooseFiles=true,canChooseDirectories=false,allowsMultipleSelection=false,fileTypes={'json'}}
        if not selected or #selected~=1 then return end
        local accepted,s=Tasks.pcall(scope,selected[1])
        if not accepted then Dialogs.message('Qualification refused','Check the exact artifact, empty disposable catalog and current consent.','critical');return end
        if Dialogs.confirm('Run this exact synthetic qualification?',
            'Creates 15 generated photos and one local Album; renders PNG/JPEG, injects bounded faults, and writes at most 200000001 scratch bytes. No network. Dispose of this catalog afterward.',
            'Run qualification','Cancel')~='ok' then return end
        local owned={files={},directories={},photos={},fixtures={},sessions={}}
        local report={schemaVersion=1,artifactSha2_256=s.artifact,status='incomplete',cases={},
            nativeSchedulingProven=false,productionQualified=false,networkCalls=0,
            fixtureProviderRegistered=true,productionProviderRegistered=false,
            actualHost=s.host,fixtureVersion=Config.VERSION,declaredSdkVersion=Config.SDK}
        local album
        local ok=Tasks.pcall(function()
            check(s.valid());Files.createDirectory(s.directory)
            check(Files.exists(s.directory)=='directory')
            for i=1,15 do
                check(s.valid())
                local path=Paths.child(s.directory,string.format('synthetic-%02d.tif',i))
                owned.files[#owned.files+1]=path;write(path,Assets.tiff())
                s.catalog:withWriteAccessDo('Import generated qualification photo',function()
                    check(s.valid());owned.photos[i]=assert(s.catalog:addPhoto(path))
                    s.allowPhoto(owned.photos[i])
                end)
            end
            s.catalog:withWriteAccessDo('Create qualification Album',function()
                check(s.valid());album=assert(s.service:createPublishedCollection('Qualification Album',nil,false))
                album:setCollectionSettings{schemaVersion=1,albumLifecycle='local_unbound'}
            end)
            s.catalog:withWriteAccessDo('Add generated qualification photos',function()
                check(s.valid());album:addPhotos(owned.photos)
            end)
            for index,caseId in ipairs(Config.CASES) do
                local worked,row=Tasks.pcall(runCase,s,album,caseId,index,owned.photos,owned)
                report.cases[#report.cases+1]=worked and row or
                    {caseId=caseId,terminal=true,ok=false,code='native_case_failed'}
                local drained,proven=Tasks.pcall(drain,owned)
                local current=report.cases[#report.cases]
                current.renderCompletionProven=drained and proven==true
                if not current.renderCompletionProven then current.ok=false end
                check(current.renderCompletionProven and s.valid())
            end
            report.status='measured_requires_independent_qualification'
        end)
        if not ok then report.status='run_failed' end
        for index=#report.cases+1,#Config.CASES do
            report.cases[index]={caseId=Config.CASES[index],terminal=true,ok=false,code='not_run'}
        end
        local cleaned,receipt=Tasks.pcall(cleanup,s,owned,album)
        report.cleanup=cleaned and receipt or {catalogCleanupCompleted=false,catalogDisposalRequired=true}
        if report.cleanup.renderCompletionProven~=true then report.status='cleanup_incomplete' end
        report.allCasesPassed=#report.cases==#Config.CASES
            and report.cleanup.renderCompletionProven==true
            and report.cleanup.catalogCleanupCompleted==true
            and report.cleanup.ownedFilesDeleted==true
        for _,row in ipairs(report.cases) do report.allCasesPassed=report.allCasesPassed and row.ok==true end
        -- Retain no paths, UUIDs, service/local IDs, bytes or raw error strings.
        local saved=Tasks.pcall(write,Paths.child(s.directory,'receipts.json'),assert(json.encode(report,{indent=true}))..'\n')
        Dialogs.message('Qualification finished',saved and
            (report.cleanup.renderCompletionProven==true and
                'Sanitized receipts.json is beside this disposable catalog in FGA-provider-render-qualification-v1. Review cleanup, close Lightroom, and dispose of the catalog.'
                or 'Render completion is unknown. Preserve all files and this catalog. Read sanitized receipts.json; do not dispose while native work may still be active.')
            or 'Receipt write failed. Preserve this disposable catalog for inspection; qualification is incomplete.','info')
    end)
end
return M
