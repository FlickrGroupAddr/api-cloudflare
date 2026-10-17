-- Source-only synthetic SDK harness. No Lightroom host, transport, or real files.
local H = {}
function H.new(caseId)
    local files = FilesFixture.new()
    files:file('synthetic-render', 'png')
    target.fgaPublishServiceId = '12345678-1234-4123-8123-123456789abc'
    function album:getCollectionInfoSummary()
        return {localIdentifier=34,isDefaultCollection=false,
            collectionSettings={schemaVersion=1,albumLifecycle='local_unbound'},
            publishSettings=serviceSettings}
    end
    serviceSettings = {}
    local providerDependencies = {pcall=pcall,pluginId=service:getPluginId(),
        verifyService=function(settings)
            assert(settings==serviceSettings)
            return {ok=true,linkStatus='ready',identity={schemaVersion=1,
                serviceRevision=1,fgaPublishServiceId=target.fgaPublishServiceId,
                linkedFlickrRevision=6,issuingInstallationId='synthetic-installation'}}
        end}
    local provider = require('OrdinaryAlbumProvider').new(providerDependencies)
    exportContext.propertyTable = {}
    provider.updateExportSettings(exportContext.propertyTable)
    local h = {files=files,provider=provider,candidates={photo},removed={},
        renderStarted=false,guard=true,guardCalls=0,consumed=0}
    exportContext.exportSession = {
        photosToExport=function()
            assert(not h.renderStarted)
            local i=0
            return function() i=i+1; return h.candidates[i] end
        end,
        removePhoto=function(_,p)
            assert(not h.renderStarted)
            h.removed[p]=true
        end,
    }
    h.options = {providerDependencies=providerDependencies,caseId=caseId,
        guard=function() h.guardCalls=h.guardCalls+1; return h.guard end,
        scope={disposable=true,syntheticOnly=true,catalogIdentity=catalog,
            activeCatalog=function() return activeCatalog end}}
    h.preparation = {contextDependencies=deps,now=function() return now end,
        handoffId=function(p) return 'qualification-'..p.uuid end}
    h.fixture = assert(Qualification.new(h.options))
    function h:prepare()
        self.session,self.reason=self.fixture:prepare(exportContext,self.preparation)
        return self.session,self.reason
    end
    function h:render(p,successful)
        self.renderStarted=true
        local r=self.files:rendition('synthetic-render',successful)
        r.photo=p or photo
        return r
    end
    function h:consume(lease,handle,policy)
        self.consumed=self.consumed+1
        assert(handle~=nil and policy.maximumBytes==200000000)
        self.lease=lease
        local bytes=lease:read()
        return bytes=='png'
    end
    function h:process(p,successful,consume)
        return self.fixture:process(self.session,self:render(p,successful),
            consume or function(...) return self:consume(...) end)
    end
    function h:records()
        if catalogProperties.uploadAttemptRecoveryStore==nil then return {} end
        local data=json.decode(catalogProperties.uploadAttemptRecoveryStore,1,json.null)
        return data and data.attempts or {}
    end
    return h
end
return H
