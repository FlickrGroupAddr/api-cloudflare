"""Synthetic Lua evidence checks; Lupa is not Lightroom host qualification."""

import hashlib
import struct
import unittest
import zlib
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "probes/lightroom/FGA-ProviderRender-Evidence.lrplugin"


class NativeEvidenceFixtureTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.execute("""
            guardAllowed=true
            authorizationCalls=0
            stageCalls=0
            order={}
            evidence=require('Evidence').new {
                guard=function() return guardAllowed end,
                authorize=function()
                    authorizationCalls=authorizationCalls+1
                    order[#order+1]='authorize'
                    return true
                end,
                stage=function(path,size)
                    stageCalls=stageCalls+1
                    order[#order+1]='stage'
                    return true
                end,
                maximumBytes=33554432,
            }
        """)

    def test_authorization_before_source_ready_never_invokes_callback(self):
        self.lua.execute("""
            evidence:beforeReady()
            assert(authorizationCalls==0 and stageCalls==0)
            local result=evidence:receipt()
            assert(result.ready==false)
            assert(result.authorizationDeniedBeforeReady==true)
            assert(result.nativeSchedulingProven==false and result.productionQualified==false)
        """)

    def test_ready_gate_allows_only_bounded_source_then_records_limited_receipt(self):
        self.lua.execute("""
            evidence:beforeReady()
            evidence:renderReady('/synthetic/owned.png',128)
            assert(authorizationCalls==1 and stageCalls==1)
            local result=evidence:receipt()
            assert(result.ready and result.staged)
            assert(result.authorizationAfterReady)
            assert(result.nativeSchedulingProven==false and result.productionQualified==false)
        """)

    def test_guard_failure_never_authorizes_or_stages(self):
        self.lua.execute("""
            guardAllowed=false
            pcall(function() evidence:renderReady('/synthetic/owned.png',128) end)
            assert(authorizationCalls==0 and stageCalls==0)
            assert(evidence:receipt().productionQualified==false)
        """)

    def test_invalid_path_and_source_size_never_authorize(self):
        for path, size in (
            ("''", "1"),
            ("nil", "1"),
            ("'owned.png'", "0"),
            ("'owned.png'", "-1"),
            ("'owned.png'", "33554433"),
            ("'owned.png'", "1.5"),
            ("'owned.png'", "0/0"),
            ("'owned.png'", "math.huge"),
        ):
            with self.subTest(path=path, size=size):
                self.setUp()
                self.lua.execute(f"""
                    pcall(function() evidence:renderReady({path},{size}) end)
                    assert(authorizationCalls==0 and stageCalls==0)
                """)

    def test_success_is_terminal_and_receipt_cannot_mutate_internal_state(self):
        self.lua.execute("""
            assert(evidence:renderReady('/synthetic/owned.png',33554432))
            local result=evidence:receipt()
            result.productionQualified=true
            result.ready=false
            evidence:renderReady('/synthetic/owned.png',1)
            evidence:beforeReady()
            assert(authorizationCalls==1 and stageCalls==1)
            assert(evidence:receipt().ready)
            assert(evidence:receipt().productionQualified==false)
        """)

    def test_guard_exception_fails_closed(self):
        self.lua.execute("""
            local item=require('Evidence').new {
                guard=function() error('private scope sentinel') end,
                authorize=function() error('must not authorize') end,
                stage=function() error('must not stage') end,
            }
            local ok,code=item:renderReady('/synthetic/owned.png',1)
            assert(not ok and code=='scope_refused')
            assert(item:receipt().authorizationCalls==0)
        """)

    def test_revocation_during_authorization_prevents_staging(self):
        self.lua.execute("""
            local authorized,staged=0,0
            local allowed=true
            local item=require('Evidence').new {
                guard=function() return allowed end,
                authorize=function() authorized=authorized+1;allowed=false;return true end,
                stage=function() staged=staged+1;return true end,
            }
            assert(not item:renderReady('/synthetic/owned.png',1))
            assert(authorized==1 and staged==0)
            assert(item:receipt().productionQualified==false)
        """)

    def test_authorization_and_stage_failures_are_terminal_and_sanitized(self):
        for phase in ("authorization", "stage"):
            with self.subTest(phase=phase):
                self.lua.globals().failurePhase = phase
                self.lua.execute("""
                    local authCount,stageCount=0,0
                    local item=require('Evidence').new {
                        guard=function() return true end,
                        authorize=function()
                            authCount=authCount+1
                            if failurePhase=='authorization' then error('private sentinel') end
                            return true
                        end,
                        stage=function()
                            stageCount=stageCount+1
                            error('private staging sentinel')
                        end,
                    }
                    local ok,code=item:renderReady('/synthetic/owned.png',1)
                    assert(not ok)
                    assert(code==failurePhase..'_failed')
                    item:renderReady('/synthetic/owned.png',1)
                    assert(authCount==1)
                    assert(stageCount==(failurePhase=='stage' and 1 or 0))
                    assert(item:receipt().productionQualified==false)
                """)

    def test_revocation_during_staging_cannot_report_success(self):
        self.lua.execute("""
            local allowed=true
            local item=require('Evidence').new {
                guard=function() return allowed end,
                authorize=function() return true end,
                stage=function() allowed=false;return true end,
            }
            assert(not item:renderReady('/synthetic/owned.png',1))
            assert(item:receipt().staged==false and item:receipt().productionQualified==false)
        """)


class NativePersistenceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        g = self.lua.globals()
        g.bundle = BUNDLE.as_posix()
        g.client = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin").as_posix()
        g.sha2 = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
        self.lua.execute('package.path=bundle.."/?.lua;"..client.."/?.lua;"..package.path')
        self.lua.execute("""
            local Selection=require 'GroupSelectionStore'
            local Attempts=require 'UploadAttemptStore'
            Persistence=require 'Persistence'
            catalogValues={}
            photoValues={}
            catalogValues[Selection.OUTBOX_FIELD]='synthetic-outbox'
            catalogValues[Attempts.STORE_FIELD]='synthetic-attempts'
            photoValues[Selection.SELECTION_FIELD]='synthetic-selections'
            photoValues[Attempts.PHOTO_FIELD]='synthetic-correlations'
            writes=0
            allowed=true
            writeMode='executed'
            plugin={}
            scope={artifactSha2_256=string.rep('a',64),runId='test-run',
                catalogKey=string.rep('b',64),serviceId='service',albumId='album',
                photoUuid='00000000-0000-4000-8000-000000000001'}
            catalog={
                getPropertyForPlugin=function(_,_,key) return catalogValues[key] end,
                setPropertyForPlugin=function(_,_,key,value)
                    writes=writes+1;catalogValues[key]=value
                end,
                withPrivateWriteAccessDo=function(_,callback,options)
                    assert(options.timeout==5 and options.asynchronous==false)
                    if writeMode=='delayed' then lateCallback=callback;return 'queued' end
                    callback()
                    if writeMode=='unknown' then return 'unknown' end
                    return 'executed'
                end,
            }
            photo={
                getRawMetadata=function(_,key) assert(key=='uuid');return scope.photoUuid end,
                getPropertyForPlugin=function(_,_,key) return photoValues[key] end,
            }
            function fresh()
                return Persistence.new {catalog=catalog,photo=photo,plugin=plugin,
                    pcall=pcall,hash=function(value) return sha2(value) end,
                    guard=function() return allowed end,
                    activeCatalog=function() return catalog end,scope=scope}
            end
        """)

    def test_fresh_module_observes_actual_fields_without_claiming_host_restart(self):
        self.lua.execute("""
            local prepared=fresh():prepare('prepare-1')
            assert(prepared.state=='prepared_readback')
            assert(prepared.restartProven==false and prepared.lifecycleEvidenceRequired)
            local observed=fresh():observe('observe-1')
            assert(observed.state=='observed_consumed' and observed.actualStoreFieldsCompared==4)
            assert(observed.restartProven==false and observed.lifecycleEvidenceRequired)
            assert(fresh():observe('observe-2').state~='observed_consumed')
            assert(writes==2)
        """)

    def test_each_persisted_production_field_tamper_refuses_observation(self):
        for store, field in (
            ("photoValues", "require('GroupSelectionStore').SELECTION_FIELD"),
            ("catalogValues", "require('GroupSelectionStore').OUTBOX_FIELD"),
            ("catalogValues", "require('UploadAttemptStore').STORE_FIELD"),
            ("photoValues", "require('UploadAttemptStore').PHOTO_FIELD"),
        ):
            with self.subTest(field=field):
                self.setUp()
                self.lua.execute(f"""
                    assert(fresh():prepare('prepare-1').state=='prepared_readback')
                    {store}[{field}]='changed-synthetic-store'
                    assert(fresh():observe('observe-1').state=='store_or_action_mismatch')
                    assert(writes==1)
                """)

    def test_replay_scope_drift_and_corrupt_envelopes_never_consume(self):
        for mutation in (
            "scope.albumId='other-album'",
            "scope.extra='unexpected'",
            "catalogValues[Persistence.FIELD]='malformed'",
            "catalogValues[Persistence.FIELD]=string.rep('x',2049)",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute(f"""
                    assert(fresh():prepare('prepare-1').state=='prepared_readback')
                    {mutation}
                    local result=fresh():observe('observe-1')
                    assert(result.state~='observed_consumed' and result.restartProven==false)
                    assert(writes==1)
                """)
        self.setUp()
        self.lua.execute("""
            local instance=fresh()
            assert(instance:prepare('prepare-1').state=='prepared_readback')
            assert(instance:prepare('prepare-2').state=='action_refused')
            assert(fresh():observe('prepare-1').state=='store_or_action_mismatch')
            assert(writes==1)
        """)

    def test_unknown_write_is_not_retried_and_late_callback_is_fenced(self):
        self.lua.execute("""
            writeMode='unknown'
            local item=fresh()
            assert(item:prepare('prepare-1').state=='write_unconfirmed')
            assert(item:prepare('prepare-2').state=='action_refused' and writes==1)
        """)
        self.setUp()
        self.lua.execute("""
            writeMode='delayed'
            local item=fresh()
            assert(item:prepare('prepare-1').state=='write_unconfirmed')
            assert(lateCallback and writes==0)
            assert(not pcall(lateCallback))
            assert(writes==0)
        """)

    def test_guard_refusal_and_oversized_store_precede_writes(self):
        for mutation in (
            "allowed=false",
            "catalogValues[require('UploadAttemptStore').STORE_FIELD]=string.rep('x',65537)",
            "photoValues[require('GroupSelectionStore').SELECTION_FIELD]=nil",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute(f"""
                    {mutation}
                    local result=fresh():prepare('prepare-1')
                    assert(result.state~='prepared_readback' and result.restartProven==false)
                    assert(writes==0)
                """)


class NativeCallbackBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        g = self.lua.globals()
        g.bundle = BUNDLE.as_posix()
        g.client = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin").as_posix()
        g.publisher = (ROOT / "clients/lightroom/publisher").as_posix()
        self.lua.execute(
            'package.path=bundle.."/?.lua;"..client.."/?.lua;"..publisher.."/?.lua;"..package.path'
        )
        self.lua.execute("""
            panelCalls=0
            forbiddenCalls=0
            local function forbidden()
                forbiddenCalls=forbiddenCalls+1
                error('unexpected boundary action')
            end
            function import(name)
                if name=='LrTasks' then return {pcall=pcall,startAsyncTask=forbidden} end
                if name=='LrDialogs' then return {runOpenPanel=function()
                    panelCalls=panelCalls+1;return nil
                end} end
                if name=='LrDigest' then return {SHA256={digest=forbidden}} end
                if name=='LrApplication' then return {activeCatalog=forbidden} end
                if name=='LrFileUtils' then return {readFile=forbidden,fileAttributes=forbidden} end
                if name=='LrPathUtils' or name=='LrDate' then return {} end
                error('unexpected SDK import')
            end
        """)

    def test_manufactured_context_cannot_bypass_disabled_native_scope(self):
        self.lua.execute("""
            local native=require 'Native'
            local fake={sdkCallbackEntered=true,contextOrigin='registered_processRenderedPhotos',
                publishService={},publishedCollection={},publishedCollectionInfo={},
                renditions=function() forbiddenCalls=forbiddenCalls+1;error('must not render') end}
            local ok=pcall(native.callback,{},fake)
            assert(not ok and panelCalls==0 and forbiddenCalls==0)
        """)

    def test_menu_entry_is_disabled_before_task_or_consent(self):
        self.lua.execute("""
            local native=require 'Native'
            assert(not pcall(native.run))
            assert(panelCalls==0 and forbiddenCalls==0)
            assert(require('Config').NATIVE_SCOPE_READY==false)
        """)

    def test_all_new_bundle_lua_sources_compile_without_host_initialization(self):
        for path in sorted(BUNDLE.glob("*.lua")):
            with self.subTest(source=path.name):
                self.assertTrue(
                    self.lua.eval("function(s) return loadstring(s)~=nil end")(
                        path.read_text(encoding="utf-8")
                    )
                )

    def test_provider_forwards_original_callback_arguments_without_host_proof(self):
        self.lua.execute("""
            local receivedFunction,receivedExport
            package.loaded.Native={callback=function(f,e)
                receivedFunction=f;receivedExport=e;return 'forwarded'
            end}
            local provider=require 'EvidenceProvider'
            local f,e={},{manufactured=true}
            assert(provider.processRenderedPhotos(f,e)=='forwarded')
            assert(receivedFunction==f and receivedExport==e)
            assert(panelCalls==0 and forbiddenCalls==0)
        """)

    def test_receipt_requires_external_host_origin_evidence(self):
        # The documented SDK has no context authenticity predicate. Guard the
        # explicit limitation so invoking a public Lua callback cannot pass it.
        source = (BUNDLE / "Native.lua").read_text(encoding="utf-8")
        self.assertIn("sdkCallbackOriginProven=false", source)
        self.assertIn("hostMeasurementRequired=true", source)
        self.assertNotIn("sdkCallbackEntered=true", source)
        self.assertNotIn("sdkCallbackOriginProven=true", source)


class NativeFiniteInternalTests(unittest.TestCase):
    """Reach local closures through Lua debug, never add a production escape."""

    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True, encoding=None)
        g = self.lua.globals()
        g.bundle = BUNDLE.as_posix().encode()
        g.client = (ROOT / "clients/lightroom/FGA-LrC15.lrplugin").as_posix().encode()
        g.publisher = (ROOT / "clients/lightroom/publisher").as_posix().encode()
        g.sha2 = lambda value: hashlib.sha256(value).hexdigest().encode()

        def png_chunk(kind, payload):
            return (
                struct.pack(">I", len(payload))
                + kind
                + payload
                + struct.pack(">I", zlib.crc32(kind + payload))
            )

        g.renderBytes = (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress((b"\0" + bytes(24)) * 8))
            + png_chunk(b"IEND", b"")
        )
        self.lua.execute(
            'package.path=bundle.."/?.lua;"..client.."/?.lua;"..publisher.."/?.lua;"..package.path'
        )
        self.lua.execute("""
            json=require 'dkjson'
            memory={};directories={};sizes={};readRequests={};mutations={}
            validFlag=true;privateMode='executed';prepareMode='executed';clockValue=100
            ledgerWrites=0;authorizationCalls=0;renditionIterations=0;waits=0
            local ID='com.sixbuckssolutions.fga.providerrender.evidence.lrc15'
            _PLUGIN={id=ID,path='/sandbox/bundle'}
            catalogPath='/sandbox/FGA-NativeEvidence-Disposable.lrcat'
            evidenceDir='/sandbox/FGA-native-evidence-v1'
            sourcePath=evidenceDir..'/synthetic.tif'
            renderedPath=evidenceDir..'/render/output.png'
            function mutate(name)
                mutations[#mutations+1]=name
                if revokeAfter==#mutations then validFlag=false end
            end
            photo={getRawMetadata=function() return '00000000-0000-4000-8000-000000000001' end}
            service={localIdentifier=1,getPluginId=function() return ID end,
                getChildCollectionSets=function() return {} end}
            function collection(id,isDefault)
                local item={localIdentifier=id,photos={}}
                item.info={localIdentifier=id,isDefaultCollection=isDefault,
                    collectionSettings={schemaVersion=1,albumLifecycle='local_unbound'}}
                function item:getCollectionInfoSummary() return self.info end
                function item:isSmartCollection() return false end
                function item:getService() return service end
                function item:getPhotos() return self.photos end
                function item:setCollectionSettings(settings)
                    mutate('settings');self.info.collectionSettings=settings
                end
                function item:addPhotos(photos)
                    mutate(isDefault and 'default-photos' or 'album-photos');self.photos=photos
                end
                return item
            end
            default=collection(2,true);album=collection(3,false)
            photos={};collections={default};catalogProperties={}
            catalog={getPath=function() return catalogPath end,
                getPublishServices=function() return {service} end,
                getAllPhotos=function() return photos end,
                findPhotoByPath=function(_,path) return path==sourcePath and photo or nil end,
                getPropertyForPlugin=function(_,_,key) return catalogProperties[key] end,
                setPropertyForPlugin=function(_,_,key,value)
                    ledgerWrites=ledgerWrites+1;catalogProperties[key]=value
                end,
                withPrivateWriteAccessDo=function(_,callback,options)
                    assert(options.timeout==5 and options.asynchronous==false)
                    if privateMode=='delayed' then lateLedger=callback;return 'queued' end
                    callback();return privateMode
                end,
                withWriteAccessDo=function(_,_,callback,options)
                    assert(options.timeout==5 and options.asynchronous==false)
                    if prepareMode=='delayed' then latePrepare=callback;return 'queued' end
                    callback();return prepareMode
                end,
                addPhoto=function() mutate('photo');photos={photo};return photo end}
            function service:getChildCollections() return collections end
            function service:createPublishedCollection()
                mutate('album');collections={default,album};return album
            end
            local files={
                exists=function(path)
                    return directories[path] and 'directory' or memory[path] and 'file' or nil
                end,
                fileAttributes=function(path)
                    return memory[path] and {fileSize=sizes[path] or #memory[path]} or nil
                end,
                readFile=function(path) return memory[path] end,
                createDirectory=function(path) directories[path]=true end,
                directoryEntries=function()
                    local i=0;return function() i=i+1;return bundlePaths[i] end
                end}
            io.open=function(path,mode)
                if mode=='rb' then
                    if memory[path]==nil then return nil end
                    local position=1;local bytes=memory[path]
                    return {read=function(_,count)
                        assert(type(count)=='number')
                        readRequests[#readRequests+1]={path=path,count=count}
                        if position>#bytes then return nil end
                        local part=bytes:sub(position,position+count-1)
                        position=position+#part;return part
                    end,close=function() return true end}
                end
                assert(mode=='wb');memory[path]=''
                return {write=function(_,bytes) memory[path]=memory[path]..bytes;return true end,
                    close=function() return true end}
            end
            function import(name)
                if name=='LrApplication' then return {
                    activeCatalog=function() return validFlag and catalog or nil end,
                    versionTable=function() return {major=15,minor=6} end} end
                if name=='LrTasks' then return {
                    pcall=pcall,startAsyncTask=function(callback) callback() end} end
                if name=='LrFileUtils' then return files end
                if name=='LrPathUtils' then return {
                    standardizePath=function(path) return path end,
                    child=function(a,b) return a..'/'..b end,
                    parent=function(path) return path:match('^(.*)/[^/]+$') end,
                    leafName=function(path) return path:match('([^/]+)$') end} end
                if name=='LrDate' then return {currentTime=function() return clockValue end,
                    timeToPosixDate=function(value) return value end} end
                if name=='LrDigest' then return {
                    SHA256={digest=function(value) return sha2(value) end}} end
                if name=='LrDialogs' then return {
                    runOpenPanel=function() return {'/consent.json'} end} end
                error('unexpected import')
            end
            bundlePaths={};local manifestFiles={}
            local requiredNames={'Native.lua','EvidenceProvider.lua','Persistence.lua',
                'MetadataDefinition.lua'}
            for _,name in ipairs(requiredNames) do
                local path=_PLUGIN.path..'/'..name;memory[path]='synthetic source'
                bundlePaths[#bundlePaths+1]=path
                manifestFiles[#manifestFiles+1]={path=name,bytes=#memory[path],
                    sha2_256=sha2(memory[path])}
            end
            manifest={artifactSha2_256=string.rep('a',64),
                bundle='FGA-ProviderRender-Evidence.lrplugin',
                version=require('Config').VERSION,files=manifestFiles}
            memory['/sandbox/manifest.json']=assert(json.encode(manifest))
            grant={schemaVersion=1,owner='Terry',artifactSha2_256=string.rep('a',64),
                manifestSha2_256=sha2(memory['/sandbox/manifest.json']),runId='synthetic-run',
                actionId='synthetic-action',phase='prepare',catalogPath=catalogPath,
                grantedAt=99,expiresAt=1000,allowSyntheticCatalogWrites=true,
                allowPrivateRenderedBytes=true,allowSyntheticCallback=true,allowCleanup=true}
            function updateGrant() memory['/consent.json']=assert(json.encode(grant)) end
            updateGrant()
            Native=require 'Native'
            function up(fn,name)
                local i=1
                while true do local key,value=debug.getupvalue(fn,i)
                    if not key then error('missing closure '..name) end
                    if key==name then return value end;i=i+1
                end
            end
            consent=up(Native.callback,'consent');prepare=up(Native.run,'prepare')
            assets=require 'NativeAssets'
            function scopeForPrepare()
                return {c=grant,catalog=catalog,service=service,directory=evidenceDir,
                    valid=function() return validFlag end}
            end
            function contextForCallback(phase)
                grant.actionId='prepare-action';updateGrant()
                prepare(consent())
                memory[sourcePath]=assets.tiff();memory[renderedPath]=renderBytes
                directories[evidenceDir]=true;photos={photo};collections={default,album}
                album.photos={photo};default.photos={photo}
                selectedPhotos={photo}
                local context={publishService=service,publishedCollectionInfo=album.info,
                    publishedCollection=album,propertyTable={LR_format='PNG',
                        LR_export_destinationType='specificFolder',
                        LR_export_destinationPathPrefix=evidenceDir..'/render',
                        LR_export_useSubfolder=false}}
                if phase=='default_callback' then
                    context.publishedCollection=default;context.publishedCollectionInfo=default.info
                end
                context.exportSession={photosToExport=function()
                    local i=0;return function() i=i+1;return selectedPhotos[i] end
                end}
                function context:renditions()
                    assert(progressConfigured)
                    renditionIterations=renditionIterations+1
                    local done=false;return function()
                        if done then return nil end;done=true
                        return 1,{photo=photo,wasSkipped=skipped==true,
                            waitForRender=function()
                                waits=waits+1;return renderSucceeded~=false,renderedPath
                            end}
                    end
                end
                function context:configureProgress()
                    assert(renditionIterations==0);progressConfigured=true
                    return {setCancelable=function() end}
                end
                local evidence=require 'Evidence';local original=evidence.new
                evidence.new=function(deps)
                    local authorize=deps.authorize
                    deps.authorize=function()
                        authorizationCalls=authorizationCalls+1;return authorize()
                    end
                    return original(deps)
                end
                if phase=='album_callback' then
                    grant.phase='default_callback';grant.actionId='default-action';updateGrant()
                    context.publishedCollection=default
                    context.publishedCollectionInfo=default.info
                    require('Config').NATIVE_SCOPE_READY=true
                    Native.callback({},context)
                    require('Config').NATIVE_SCOPE_READY=false
                    context.publishedCollection=album;context.publishedCollectionInfo=album.info
                end
                grant.phase=phase;grant.actionId='synthetic-action';updateGrant()
                return context
            end
        """)

    def test_actual_consent_ledger_late_callback_is_fenced(self):
        self.lua.execute("""
            privateMode='delayed'
            assert(not pcall(consent) and ledgerWrites==0 and lateLedger)
            assert(not pcall(lateLedger) and ledgerWrites==0)
            assert(#mutations==0)
        """)

    def test_unknown_ledger_outcome_remains_consumed(self):
        self.lua.execute("""
            privateMode='unknown'
            assert(not pcall(consent) and ledgerWrites==1)
            privateMode='executed'
            assert(not pcall(consent) and ledgerWrites==1)
        """)

    def test_actual_consent_recheck_rejects_revocation_and_expiry(self):
        for patch in ("memory['/consent.json']='revoked'", "clockValue=1000"):
            with self.subTest(patch=patch):
                self.setUp()
                self.lua.execute(f"""
                    local scope=consent()
                    assert(scope.valid())
                    {patch}
                    assert(not scope.valid())
                    assert(#mutations==0)
                """)

    def test_same_run_ledger_cannot_authorize_another_artifact(self):
        self.lua.execute("""
            prepare(consent())
            grant.phase='default_callback';grant.actionId='another-action'
            grant.artifactSha2_256=string.rep('c',64)
            manifest.artifactSha2_256=grant.artifactSha2_256
            memory['/sandbox/manifest.json']=assert(json.encode(manifest))
            grant.manifestSha2_256=sha2(memory['/sandbox/manifest.json']);updateGrant()
            assert(not pcall(consent) and ledgerWrites==1)
        """)

    def test_malformed_phase_hole_cannot_substitute_for_prior_success(self):
        self.lua.execute("""
            assert(consent())
            local ledger=assert(json.decode(catalogProperties.nativeEvidenceActionsV1))
            ledger.phases={album_callback='tampered-prior'}
            catalogProperties.nativeEvidenceActionsV1=assert(json.encode(ledger))
            memory[evidenceDir..'/tampered-prior-receipt.json']=assert(json.encode {
                schemaVersion=1,fixtureVersion=require('Config').VERSION,
                runId=grant.runId,artifactSha2_256=grant.artifactSha2_256,
                actionId='tampered-prior',phase='album_callback',status='private_render_staged'})
            grant.phase='default_callback';grant.actionId='new-default';updateGrant()
            assert(not pcall(consent) and ledgerWrites==1)
        """)

    def test_prepare_delayed_unknown_and_revoked_mutation_boundaries(self):
        self.lua.execute("""
            prepareMode='delayed'
            assert(not pcall(prepare,scopeForPrepare()) and latePrepare and #mutations==0)
            assert(not pcall(latePrepare) and #mutations==0)
        """)
        self.setUp()
        self.lua.execute("""
            prepareMode='unknown'
            assert(not pcall(prepare,scopeForPrepare()))
            assert(#mutations==5)
            assert(memory[evidenceDir..'/synthetic-action-receipt.json']==nil)
        """)
        for boundary in range(1, 6):
            with self.subTest(boundary=boundary):
                self.setUp()
                self.lua.globals().revokeAfter = boundary
                self.lua.execute("""
                    assert(not pcall(prepare,scopeForPrepare()))
                    assert(#mutations==revokeAfter)
                    assert(memory[evidenceDir..'/synthetic-action-receipt.json']==nil)
                """)

    def test_consent_reads_are_bounded_even_when_attributes_lie(self):
        self.lua.execute("""
            memory['/consent.json']=memory['/consent.json']..string.rep(' ',8193)
            sizes['/consent.json']=1
            assert(not pcall(consent) and ledgerWrites==0)
            assert(#readRequests>0)
            for _,request in ipairs(readRequests) do assert(request.count<=8193) end
        """)

    def test_session_photo_mismatch_refuses_before_renditions_or_authorization(self):
        for selection in ("{}", "{photo,{}}", "{{}}"):
            with self.subTest(selection=selection):
                self.setUp()
                self.lua.execute(f"""
                    local context=contextForCallback('album_callback')
                    selectedPhotos={selection}
                    require('Config').NATIVE_SCOPE_READY=true
                    assert(not pcall(Native.callback,{{}},context))
                    assert(renditionIterations==0 and authorizationCalls==0)
                """)

    def test_malformed_skipped_or_oversized_source_never_authorizes(self):
        for patch in (
            "memory[renderedPath]='not png'",
            "skipped=true",
            "renderSucceeded=false",
            "sizes[renderedPath]=33554433",
            "memory[renderedPath]=renderBytes..'extra';sizes[renderedPath]=#renderBytes",
        ):
            with self.subTest(patch=patch):
                self.setUp()
                self.lua.execute(f"""
                    local context=contextForCallback('album_callback')
                    {patch}
                    require('Config').NATIVE_SCOPE_READY=true
                    Native.callback({{}},context)
                    assert(authorizationCalls==0)
                    assert(memory[evidenceDir..'/synthetic-action-rendered.png']==nil)
                    local result=assert(json.decode(
                        memory[evidenceDir..'/synthetic-action-receipt.json']))
                    assert(result.status=='render_or_validation_failed')
                    assert(result.renderCompletionProven==false)
                    assert(result.preserveNativeWorkRequired and result.hostDrainEvidenceRequired)
                    for _,request in ipairs(readRequests) do
                        if request.path==renderedPath then assert(request.count<=33554433) end
                    end
                """)

    def test_valid_synthetic_callback_binds_staged_bytes_and_limits_claims(self):
        self.lua.execute("""
            local context=contextForCallback('album_callback')
            require('Config').NATIVE_SCOPE_READY=true
            Native.callback({},context)
            assert(authorizationCalls==1 and waits==1 and renditionIterations==1)
            assert(memory[evidenceDir..'/synthetic-action-rendered.png']==renderBytes)
            local receipt=assert(json.decode(memory[evidenceDir..'/synthetic-action-receipt.json']))
            assert(receipt.sdkCallbackOriginProven==false and receipt.hostMeasurementRequired)
            assert(receipt.productionQualified==false and receipt.nativeSchedulingProven==false)
            assert(receipt.renderedPngSha2_256==sha2(renderBytes))
            assert(receipt.renderedPngBytes==#renderBytes)
        """)

    def test_default_callback_refuses_before_render_and_authorization(self):
        self.lua.execute("""
            local context=contextForCallback('default_callback')
            require('Config').NATIVE_SCOPE_READY=true
            Native.callback({},context)
            assert(authorizationCalls==0 and waits==0 and renditionIterations==0)
            local receipt=assert(json.decode(memory[evidenceDir..'/synthetic-action-receipt.json']))
            assert(receipt.status=='default_refused' and receipt.sdkCallbackOriginProven==false)
        """)


if __name__ == "__main__":
    unittest.main()
