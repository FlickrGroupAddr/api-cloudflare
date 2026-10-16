"""Actual existing-photo/browser/selection/read/store composition, synthetic SDK/HTTP."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"

HARNESS = r"""
local json=require 'dkjson'
local function array(t) return setmetatable(t or {},{__jsontype='array'}) end
local stamp='2026-10-16T12:00:00.000000Z'
local null=json.null
properties,plugin,catalog={},{},{}
identity={installationId='installation-1',linkedFlickrRevision=2}
activeCatalog=catalog
posts,proofs,gets,dialogs,sleeps=0,0,0,0,0
local credential=string.rep('0000-',12)..'0000'
local function headers() return {status=200} end
local function body(value) return json.encode(value),headers() end
function catalog:getPropertyForPlugin(p,key) assert(p==plugin); return properties[key] end
function catalog:setPropertyForPlugin(p,key,value)
    assert(insideGate and p==plugin); properties[key]=value
end
function catalog:withPrivateWriteAccessDo(fn,options)
    assert(options.asynchronous==false and not insideGate)
    if beforeGate then local callback=beforeGate; beforeGate=nil; callback() end
    insideGate=true; local ok,err=pcall(fn); insideGate=false
    if not ok then error(err) end
    return 'executed'
end
local sdk={}
local factory=setmetatable({}, {__index=function(_,kind)
    if kind=='control_spacing' or kind=='label_spacing' then return function() return 4 end end
    return function(_,p) p.kind=kind; return p end
end})
sdk.LrBinding={makePropertyTable=function() return {addObserver=function() end} end}
sdk.LrView={bind=function(k) return k end,osFactory=function() return factory end}
sdk.LrDate={currentTime=function() return 1 end}
sdk.LrPathUtils={child=function(a,b) return a..'/'..b end,
    getStandardFilePath=function() return 'synthetic-temp' end}
sdk.LrFileUtils={exists=function() return false end,delete=function() return true end,
    createAllDirectories=function() return true end,chooseUniqueFileName=function(p) return p end}
sdk.LrLogger=function() return {enable=function() end,warn=function() end} end
sdk.LrTasks={pcall=pcall}
sdk.LrFunctionContext={callWithContext=function(_,fn) return fn({}) end}
local function find(v,title)
    if v.title==title then return v end
    for _,child in ipairs(v) do local found=find(child,title); if found then return found end end
end
sdk.LrDialogs={message=function() end,presentModalDialog=function(options)
    dialogs=dialogs+1
    if options.actionVerb=='Verify Photo' then
        if cancelBrowser then return 'cancel' end
        options.contents.bind_to_object.selected='photo-1'; return 'ok'
    elseif options.actionVerb=='Close' then return 'ok' end
    assert(options.title=='FlickrGroupAddr — Group additions')
    if cancelGroups then return 'cancel' end
    local p=options.contents.bind_to_object
    assert(#p.availableItems==1 and p.availableItems[1].value=='group-1')
    p.availableChoice={'group-1'}
    find(options.contents,'Add →').action()
    assert(p.allowed and p.actionTitle=='Queue for 1 group')
    if switchBeforeCommit then identity.linkedFlickrRevision=3 end
    return 'ok'
end}
import=function(name) return assert(sdk[name],name) end
-- Cache writes are replaced at the synthetic SDK boundary; no real file/catalog/photo.
io.open=function() return {write=function(self) return self end,
    close=function() return true end} end
cleanup={}
context={addCleanupHandler=function(_,fn) cleanup[#cleanup+1]=fn end}
local gates=array()
for _,scope in ipairs({'user','deployment'}) do
    gates[#gates+1]={scope=scope,state='enabled',revision=1,pausedAt=null,reasonCode=null,
        affectedActiveIntentCount=0}
end
deps={catalog=catalog,plugin=plugin,call=pcall,
    capabilities={hostTask=true,thumbnailTransport=true,readTransport=true,proofTransport=true,
        batchTransport=true,catalogOutbox=true,currentIdentity=true,credentialBoundary=true},
    batchClient=batchClient,jsonNull=null,encode=json.encode,
    decode=function(bytes)
        local value,pos,err=json.decode(bytes,1,null)
        if err or not bytes:sub(pos):match('^%s*$') then error('bad_json') end
        return value
    end,
    retrieve=function(key)
        if key=='fga.installation.current' then return changedCredential or credential end
        if key=='fga.installation.rotation_candidate' then return rotationCandidate end
    end,
    currentIdentity=function() return identity end,
    activeCatalog=function() return activeCatalog end,
    cancelled=function() return cancelledFlag==true end,
    sleep=function(seconds) sleeps=sleeps+seconds end,
    now=function() return sleeps end,newHandoffId=function() return 'handoff-1' end}
deps.httpGet=function(url)
    gets=gets+1
    if url:find('/installations/current',1,true) then
        return body{schemaVersion=1,installationId='installation-1',installationRevision=1,
            installationState='active',presentedCredentialState='current'}
    elseif url:find('/thumbnail?',1,true) then
        return '\255\216\255synthetic\255\217',{status=200,
            {field='Content-Type',value='image/jpeg'},{field='Cache-Control',value='no-store'}}
    elseif url:find('/existing-public-photos?',1,true) then
        return body{schemaVersion=1,linkedFlickrRevision=2,observedAt=stamp,page=1,pageSize=5,
            pages=1,total=1,photos=array{{flickrPhotoId='photo-1',title='Synthetic photo',
                dateUploaded='1700000000',dateTaken='2026-10-16 12:00:00',
                thumbnail={url='https://live.staticflickr.com/123/fixture_q.jpg',sizeClass='q'}}}}
    elseif url:find('/group-memberships?',1,true) then
        return body{schemaVersion=1,fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',
            observationRevision=1,observedAt=stamp,groups=array(),nextAfterGroupId=null}
    elseif url:find('/groups?',1,true) then
        return body{schemaVersion=1,snapshotRevision=1,refreshedAt=stamp,
            snapshotStatus=staleGroups and 'stale_refreshing' or 'fresh',
            groups=array{{flickrGroupId='group-1',displayName='Synthetic group'}},
            nextAfterGroupId=null}
    elseif url:find('/group-submission-intents?',1,true) then
        if badHistory then return 'private failure',{status=503} end
        return body{schemaVersion=1,observedAt=stamp,view='history',pageSize=100,
            photoBindingId='binding-1',summary={activeIntentCount=0,activePartitionCount=0,
                attentionIntentCount=0,oldestActiveEnqueuedAt=null,writeGates=gates},
            intents=array(),nextPage=null,recommendedPollAfterSeconds=null}
    end
    error('unexpected GET')
end
deps.httpPost=function(url,bytes)
    assert(url=='https://flickrgroupaddr.com/api/v001/existing-public-photo-bindings')
    proofs=proofs+1
    return body{schemaVersion=1,fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',
        sourceKind='fga_direct_upload',linkedFlickrRevision=2,verificationRevision=proofs,
        verifiedAt=stamp}
end
deps.batchPost=function(path,bytes)
    assert(path=='/api/v001/group-submission-batches')
    posts=posts+1
    local stored=json.decode(properties.existingPhotoGroupOutboxV1)
    assert(#stored.records==1 and stored.records[1].state=='prepared')
    assert(stored.records[1].binding.verificationRevision==2)
    if loseResponse then return nil,{} end
    local response={schemaVersion=2,fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',
        submissions=array{{fgaSubmissionIntentId='intent-1',flickrGroupId='group-1',
            state='queued',created=true,permanentSubmissionBlock=null}}}
    return json.encode(response),{status=202}
end
"""


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.globals().batchClient = self.lua.execute(
            (ROOT / "clients/lightroom/GroupSubmissionClient.lua").read_text("utf-8")
        )
        self.lua.execute(HARNESS)
        self.workflow = self.lua.execute(
            (BUNDLE / "ExistingPhotoGroupWorkflow.lua").read_text("utf-8")
        )

    def run_workflow(self):
        result = self.workflow.run(self.lua.globals().context, self.lua.globals().deps)
        self.lua.execute("for _,fn in ipairs(cleanup) do fn() end; cleanup={}")
        return result

    def test_full_actual_core_composition_reproves_upload_origin_and_commits(self):
        result = self.run_workflow()
        self.assertEqual(result.state, "accepted")
        self.assertEqual(self.lua.globals().proofs, 2)
        self.assertEqual(self.lua.globals().posts, 1)
        self.lua.execute("""
            local outbox=require('dkjson').decode(properties.existingPhotoGroupOutboxV1)
            assert(outbox.records[1].state=='acknowledged')
            assert(outbox.records[1].sourceKind=='fga_direct_upload')
            assert(outbox.records[1].workflow=='existing_public_photo')
        """)

    def test_missing_capability_refuses_before_reads_dialog_or_writes(self):
        self.lua.execute("deps.capabilities.batchTransport=false")
        self.assertEqual(self.run_workflow().state, "qualification_required")
        self.assertEqual(self.lua.globals().gets, 0)
        self.assertEqual(self.lua.globals().dialogs, 0)

    def test_invalid_initial_identity_refuses_before_requests_dialogs_and_writes(self):
        for injection in (
            "identity.installationId=nil",
            "identity.installationId='invalid id'",
            "identity.linkedFlickrRevision='2'",
            "identity.linkedFlickrRevision=0/0",
            "identity.linkedFlickrRevision=math.huge",
            "identity.linkedFlickrRevision=0",
            "identity.extra=true",
        ):
            with self.subTest(injection=injection):
                self.setUp()
                self.lua.execute(injection)
                self.assertEqual(self.run_workflow().state, "unavailable")
                self.assertEqual(self.lua.globals().gets, 0)
                self.assertEqual(self.lua.globals().proofs, 0)
                self.assertEqual(self.lua.globals().dialogs, 0)
                self.assertIsNone(self.lua.globals().properties.existingPhotoGroupOutboxV1)

    def test_pending_gate_rechecks_rotation_credential_and_cancellation(self):
        for mutation in (
            "rotationCandidate='candidate'",
            "changedCredential=string.rep('0000-',12)..'0010'",
            "cancelledFlag=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("loseResponse=true")
                self.assertEqual(self.run_workflow().state, "unresolved")
                self.lua.execute("beforeGate=function() " + mutation + " end")
                result = self.run_workflow()
                self.assertEqual(result.state, "unavailable")
                self.assertIsNone(result.pendingHandoffIds)
                self.assertEqual(self.lua.globals().posts, 1)

    def test_lost_response_retains_pending_identity_and_reopen_cannot_replay(self):
        self.lua.execute("loseResponse=true")
        self.assertEqual(self.run_workflow().state, "unresolved")
        result = self.run_workflow()
        self.assertEqual(result.state, "reconciliation_required")
        self.assertEqual(result.pendingHandoffIds[1], "handoff-1")
        self.assertEqual(self.lua.globals().posts, 1)

    def test_incomplete_or_stale_reads_and_identity_change_send_nothing(self):
        for injection in ("badHistory=true", "staleGroups=true", "switchBeforeCommit=true"):
            with self.subTest(injection=injection):
                self.setUp()
                self.lua.execute(injection)
                self.assertIn(
                    self.run_workflow().state, ("unavailable", "unresolved", "proof_required")
                )
                self.assertEqual(self.lua.globals().posts, 0)

    def test_cancel_changes_no_outbox(self):
        for injection in ("cancelBrowser=true", "cancelGroups=true"):
            with self.subTest(injection=injection):
                self.setUp()
                self.lua.execute(injection)
                self.assertEqual(self.run_workflow().state, "cancelled")
                self.assertIsNone(self.lua.globals().properties.existingPhotoGroupOutboxV1)
                self.assertEqual(self.lua.globals().posts, 0)


if __name__ == "__main__":
    unittest.main()
