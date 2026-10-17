-- Native dispatcher UNIT boundary model; never loads Lightroom or proves host scheduling.
local H={clock=1000,mutations=0,waits=0,dialogs={},sessions={},files={},directories={},
    pending=0,eagerStarts=0,deletesWhilePending=0,catalogWritesWhilePending=0,
    imports=0,confirm='ok',catalogPath='/disposable/FGA-ProviderRender-Disposable.lrcat'}
local ID='com.sixbuckssolutions.fga.providerrender.qualification.lrc15'
_PLUGIN={id=ID,path='/packet/FGA-ProviderRender-Qualification.lrplugin'}
plugin=_PLUGIN
local baseMakePhoto=makePhoto
service.getPluginId=function() return ID end
function service:getChildCollectionSets() return {} end
function service:getChildCollections() return H.album and {H.album} or {} end
function service:createPublishedCollection()
    H.mutations=H.mutations+1
    album=makeAlbum(34,self);H.album=album
    function album:setCollectionSettings(v) self.settings=v end
    function album:getCollectionInfoSummary()
        return {localIdentifier=34,isDefaultCollection=false,collectionSettings=self.settings,
            publishSettings={}}
    end
    function album:addPhotos(values) self.photos=values end
    function album:getPublishedPhotos() return {} end
    function album:getPhotos() return self.photos or {} end
    function album:delete() H.album=nil end
    return album
end
function catalog:getPath() return H.catalogPath end
function catalog:getAllPhotos()
    local result={};for _,p in pairs(photos) do result[#result+1]=p end
    if H.foreignPhoto then result[#result+1]={} end
    return result
end
photos={}
function catalog:getPublishServices() return H.services or {service} end
function catalog:addPhoto()
    H.imports=H.imports+1;H.mutations=H.mutations+1
    local p=baseMakePhoto(string.format('00000000-0000-0000-0000-%012d',H.imports))
    -- Imported photos acquire the real modeled Album membership when added.
    function p:getContainedPublishedCollections() return H.album and {H.album} or {} end
    return p
end
function catalog:withWriteAccessDo(_,fn)
    H.mutations=H.mutations+1;fn()
end
local oldCatalogProperty=catalog.setPropertyForPlugin
function catalog:setPropertyForPlugin(plug,key,value)
    if value==nil then
        H.cleanupStarted=true
        if H.pending>0 then H.catalogWritesWhilePending=H.catalogWritesWhilePending+1 end
    end
    return oldCatalogProperty(self,plug,key,value)
end
local oldPrivate=catalog.withPrivateWriteAccessDo
function catalog:withPrivateWriteAccessDo(fn,options)
    H.mutations=H.mutations+1
    return oldPrivate(self,fn,options or {timeout=5,asynchronous=false})
end
local function parent(path) return path:match('^(.*)/[^/]+$') end
local function leaf(path) return path:match('([^/]+)$') end
local function file(path,contents,size) H.files[path]={contents=contents,size=size or #contents} end
H.file=file
local F={}
function F.exists(path) return H.files[path] and 'file' or H.directories[path] and 'directory' or nil end
function F.fileAttributes(path) local f=H.files[path];return f and {fileSize=f.size} end
function F.readFile(path) assert(H.files[path],'synthetic missing file');return H.files[path].contents end
function F.createDirectory(path) H.directories[path]=true end
function F.directoryEntries(path)
    local entries={}
    for p in pairs(H.files) do if parent(p)==path then entries[#entries+1]=p end end
    for p in pairs(H.directories) do if parent(p)==path then entries[#entries+1]=p end end
    table.sort(entries);local i=0
    return function() i=i+1;return entries[i] end
end
function F.delete(path)
    if H.pending>0 and (H.cleanupStarted or not (H.files[path] and H.files[path].completed)) then
        H.deletesWhilePending=H.deletesWhilePending+1
        error('attempted cleanup before eager renders terminal')
    end
    H.files[path]=nil;H.directories[path]=nil;return true
end
io={open=function(path,mode)
    assert(mode=='wb');local chunks,size={},0
    return {write=function(self,bytes)
        size=size+#bytes
        if size<=1048576 then chunks[#chunks+1]=bytes end
        return self
    end,close=function()
        file(path,size<=1048576 and table.concat(chunks) or '',size)
        if path:match('receipts.json$') then H.report=json.decode(H.files[path].contents) end
        return true
    end}
end}
function import(name)
    if name=='LrTasks' then return {pcall=function(fn,...) local a,b,c=pcall(fn,...); if not a then H.lastError=tostring(b) end;return a,b,c end,startAsyncTask=function(fn) fn() end} end
    if name=='LrFileUtils' then return F end
    if name=='LrPathUtils' then return {parent=parent,leafName=leaf,
        child=function(a,b) return a..'/'..b end,standardizePath=function(p) return p end} end
    if name=='LrApplication' then return {activeCatalog=function() return activeCatalog end,
        versionTable=function() return {major=15,minor=H.hostMinor or 6,revision=2,
            build=123456,build_version='synthetic-unit-build',private='never retained'} end} end
    if name=='LrDigest' then return {SHA256={digest=function(bytes) return sha256(bytes) end}} end
    if name=='LrDate' then return {currentTime=function() return H.clock end,
        timeToPosixDate=function(n) return n end,
        timeToUserFormat=function() return '2026-10-17T12:00:00Z' end} end
    if name=='LrDialogs' then return {
        runOpenPanel=function() return H.panel or {'/consent.json'} end,
        confirm=function() if H.onConfirm then H.onConfirm() end;return H.confirm end,
        message=function(title) H.dialogs[#H.dialogs+1]=title end} end
    if name=='LrExportSession' then return function(spec)
        local session={candidates={}}
        for _,p in ipairs(spec.photosToExport) do session.candidates[#session.candidates+1]=p end
        H.sessions[#H.sessions+1]=session
        session.sequence=#H.sessions
        function session:photosToExport()
            assert(not self.started);local copy={};for i,p in ipairs(self.candidates) do copy[i]=p end
            local i=0;return function() i=i+1;return copy[i] end
        end
        function session:removePhoto(p)
            assert(not self.started)
            for i,value in ipairs(self.candidates) do if value==p then table.remove(self.candidates,i);return end end
        end
        function session:countRenditions() return #self.candidates end
        function session:renditions()
            assert(not self.started);self.started=true
            local journal=json.decode(catalogProperties.uploadAttemptRecoveryStore)
            for _,p in ipairs(self.candidates) do
                local found=false
                for _,r in ipairs(journal.attempts) do if r.photoUuid==p.uuid then found=true end end
                assert(found,'render requested before durable snapshot')
            end
            -- Model the SDK's eager start independently of obtaining/waiting a rendition.
            self.renditions={}
            for index,p in ipairs(self.candidates) do
                local path=spec.exportSettings.LR_export_destinationPathPrefix..'/output-'..index
                file(path,spec.exportSettings.LR_format=='JPEG' and jpegBytes or pngBytes)
                H.pending=H.pending+1;H.eagerStarts=H.eagerStarts+1
                local r={photo=p,pending=true}
                function r:waitForRender()
                    H.waits=H.waits+1
                    if H.waitThrows then error('synthetic unknown wait completion') end
                    if H.waitNonboolean then return 'unknown',path end
                    if self.pending then self.pending=false;H.pending=H.pending-1 end
                    if H.files[path] then H.files[path].completed=true end
                    if H.onWait then H.onWait() end
                    if H.waitFalseAt==H.waits or H.waitFalseSession==session.sequence then
                        return false,'private render detail'
                    end
                    return true,path
                end
                self.renditions[index]=r
            end
            if H.iteratorCreationThrows then error('synthetic iterator construction failure') end
            local i=0
            return function()
                i=i+1
                if H.omitRendition then return nil end
                if H.iteratorAdvanceThrows and (not H.iteratorAdvanceAfterFirst or i>1) then
                    error('synthetic iterator advancement failure')
                end
                local r=self.renditions[i];if r then return i,r end
            end
        end
        return session
    end end
    error('unexpected SDK import '..name)
end
function H:consent(patch)
    local config=require 'Config'
    local manifest={bundle='FGA-ProviderRender-Qualification.lrplugin',version=config.VERSION,
        hostVersion='15.6',artifactSha2_256=string.rep('a',64),files={}}
    for name,bytes in pairs(bundleSources) do
        file(_PLUGIN.path..'/'..name,bytes)
        manifest.files[#manifest.files+1]={path=name,bytes=#bytes,sha2_256=sha256(bytes)}
    end
    local raw=assert(json.encode(manifest));file('/packet/manifest.json',raw)
    local consent={schemaVersion=1,owner='Terry',artifactSha2_256=manifest.artifactSha2_256,
        manifestSha2_256=sha256(raw),catalogPath=self.catalogPath,grantedAt=900,expiresAt=1800,
        allowQualificationProvider=true,allowSyntheticCatalogWrites=true,
        allow200000001ByteScratch=true,allowCleanup=true}
    if patch then patch(consent) end
    file('/consent.json',assert(json.encode(consent)))
end
return H
