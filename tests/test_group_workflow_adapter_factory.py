"""Disabled SDK factory with actual existing-photo workflow/store/client cores."""

import unittest
from typing import Any, cast

from lupa.lua51 import LuaRuntime

from tests.test_existing_photo_group_workflow import BUNDLE, HARNESS, ROOT


class AdapterFactoryTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute('package.path=bundle.."/?.lua;"..package.path')
        self.lua.globals().batchClient = self.lua.execute(
            (BUNDLE / "GroupSubmissionClient.lua").read_text("utf-8")
        )
        self.lua.execute(HARNESS)
        self.lua.execute(
            (ROOT / "tests/group_workflow_adapter_factory_fixture.lua").read_text("utf-8")
        )

    def run_factory(self, expression="startFactory()"):
        return self.lua.eval(expression)

    def test_actual_workflow_commits_with_documented_sdk_adapters(self):
        self.assertEqual(self.run_factory().state, "accepted")
        self.assertGreater(self.lua.globals().taskCalls, 5)
        self.assertEqual(self.lua.globals().taskStarts, 1)
        self.lua.execute("""
            assert(properties.groupHandoffSequenceV1=='1')
            local value=require('dkjson').decode(properties.existingPhotoGroupOutboxV1)
            assert(value.records[1].handoffId=='sdk-handoff-v1-1')
            assert(captured.cancelled() and captured.currentIdentity()==nil)
            assert(factory.PRODUCTION_QUALIFIED==false)
        """)

    def test_missing_capability_fails_before_io_or_private_writes(self):
        self.lua.execute("transport.capabilities.batchTransport=false")
        self.assertEqual(self.run_factory().state, "qualification_required")
        self.assertEqual(self.lua.globals().gets, 0)
        self.assertIsNone(self.lua.globals().properties.groupHandoffSequenceV1)

    def test_existing_candidate_refuses_before_network(self):
        self.lua.execute("rotationCandidate='candidate'")
        self.assertEqual(self.run_factory().state, "unavailable")
        self.assertEqual(self.lua.globals().gets, 0)

    def test_observed_wall_time_backward_and_expired_proof_refused(self):
        # First sample names the synthetic browser cache directory, then proof samples.
        for samples in ("{1,10,9}", "{1,10,25}", "{1,0/0}", "{1,math.huge}"):
            with self.subTest(samples=samples):
                self.setUp()
                self.lua.execute("clockSamples=" + samples)
                result = self.run_factory()
                self.assertNotEqual(result.state, "accepted")
                self.assertEqual(self.lua.globals().posts, 0)

    def test_empty_authenticated_discovery_still_establishes_identity(self):
        self.lua.execute("""
            local original=deps.httpGet
            deps.httpGet=function(url,...)
                local bytes,headers=original(url,...)
                if url:find('/existing-public-photos?',1,true) then
                    local json=require 'dkjson'
                    local value=json.decode(bytes)
                    value.photos=setmetatable({},{__jsontype='array'})
                    value.total=0; value.pages=0
                    bytes=json.encode(value)
                end
                return bytes,headers
            end
        """)
        result = self.run_factory("""startFactory(function(_,d)
            return {state='ready',identity=d.currentIdentity()}
        end)""")
        self.assertEqual(result.state, "ready")
        self.assertEqual(result.identity.linkedFlickrRevision, 2)

    def test_forged_context_refused(self):
        self.assertEqual(
            self.lua.eval("select(2,factory.new(context,options))"), "qualification_required"
        )

    def test_retained_credential_reader_refuses_after_context_cleanup_without_password_access(self):
        self.assertEqual(self.run_factory().state, "accepted")
        self.lua.execute("""
            local before=passwordReads
            local core=require 'ConnectionCore'
            for _,key in ipairs({core.CURRENT_KEY,core.CANDIDATE_KEY}) do
                assert(not pcall(captured.retrieve,key))
            end
            assert(passwordReads==before)
        """)

    def test_cancelled_credential_reader_refuses_without_password_access(self):
        for cancellation in ("d.cancel()", "progress.cancelled=true"):
            with self.subTest(cancellation=cancellation):
                self.setUp()
                result = self.run_factory(
                    """startFactory(function(_,d)
                    """
                    + cancellation
                    + """
                    local before=passwordReads
                    local core=require 'ConnectionCore'
                    for _,key in ipairs({core.CURRENT_KEY,core.CANDIDATE_KEY}) do
                        assert(not pcall(d.retrieve,key))
                    end
                    assert(passwordReads==before)
                    return {state='refused'}
                end)"""
                )
                self.assertEqual(result.state, "refused")

    def test_fences_local_rotation_and_catalog_switch_after_initial_get(self):
        for mutation in (
            "rotationCandidate='candidate'",
            "changedCredential=string.rep('0000-',12)..'0010'",
            "activeCatalog={}",
            "progress.cancelled=true",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.lua.execute("afterGet=function() " + mutation + " end")
                self.assertEqual(self.run_factory().state, "unavailable")
                self.assertEqual(self.lua.globals().posts, 0)
                self.assertEqual(self.lua.globals().dialogs, 0)

    def test_exact_installation_and_link_identity_fail_closed(self):
        self.lua.execute("options.expectedInstallationId='other-installation'")
        self.assertEqual(self.run_factory().state, "identity_unavailable")
        self.setUp()
        self.lua.execute("""
            local original=deps.httpGet
            local discovery=0
            deps.httpGet=function(url,...)
                local bytes,headers=original(url,...)
                if url:find('/existing-public-photos?',1,true) then
                    discovery=discovery+1
                    if discovery>1 then
                        bytes=bytes:gsub('"linkedFlickrRevision":2','"linkedFlickrRevision":3')
                    end
                end
                return bytes,headers
            end
        """)
        self.assertEqual(self.run_factory().state, "unavailable")
        self.assertEqual(self.lua.globals().posts, 0)
        self.assertEqual(self.lua.globals().proofs, 0)

    def test_sliced_sleep_cancellation_stops_next_slice(self):
        result = self.run_factory("""startFactory(function(_,d)
            onSleep=function() progress.cancelled=true end
            d.sleep(10)
            return {state='unexpected'}
        end)""")
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(self.lua.globals().sleepSlices, 1)

    def test_sequence_persists_across_invocations_and_corruption_refuses(self):
        consumer = """function(_,d)
            return {state='ready',first=d.newHandoffId(),second=d.newHandoffId()}
        end"""
        first = self.run_factory(f"startFactory({consumer})")
        self.assertEqual((first.first, first.second), ("sdk-handoff-v1-1", "sdk-handoff-v1-2"))
        second = self.run_factory(f"startFactory({consumer})")
        self.assertEqual(second.first, "sdk-handoff-v1-3")
        for counter in ("'01'", "'invalid'", "'9007199254740991'"):
            self.lua.execute(f"properties.groupHandoffSequenceV1={counter}")
            self.assertEqual(self.run_factory(f"startFactory({consumer})").state, "unavailable")

    def test_private_gate_nonexecution_and_late_callback_cannot_allocate(self):
        self.lua.execute("""
            catalog.withPrivateWriteAccessDo=function(_,fn)
                delayed=fn
                return 'queued'
            end
        """)
        result = self.run_factory("""startFactory(function(_,d)
            return {state='ready',id=d.newHandoffId()}
        end)""")
        self.assertEqual(result.state, "unavailable")
        self.lua.execute(
            "assert(not pcall(delayed)); assert(properties.groupHandoffSequenceV1==nil)"
        )

    def test_counter_exact_readback_failure_refuses_id(self):
        self.lua.execute("""
            catalog.setPropertyForPlugin=function() end
        """)
        result = self.run_factory("""startFactory(function(_,d)
            return {state='ready',id=d.newHandoffId()}
        end)""")
        self.assertEqual(result.state, "unavailable")
        self.assertIsNone(result.id)

    def test_allocated_id_reuse_is_refused_by_actual_store(self):
        result = self.run_factory("""startFactory(function(_,d)
            local scope={installationId='installation-1',fgaPhotoBindingId='binding-1',
                flickrPhotoId='photo-1',linkedFlickrRevision=2,sourceKind='fga_direct_upload'}
            local binding={fgaPhotoBindingId='binding-1',flickrPhotoId='photo-1',
                linkRevision=2,sourceKind='fga_direct_upload',verificationRevision=1}
            local id=d.newHandoffId()
            local store=d.newStore()
            assert(store:saveChoice(scope,{'group-1'},0,id,binding).state=='saved')
            return store:saveChoice(scope,{'group-1'},1,id,binding)
        end)""")
        self.assertEqual(result.state, "handoff_exists")

    def test_cancel_after_private_write_never_exposes_id(self):
        self.lua.execute("beforeGate=function() progress.cancelled=true end")
        result = self.run_factory("""startFactory(function(_,d)
            return {state='ready',id=d.newHandoffId()}
        end)""")
        self.assertEqual(result.state, "unavailable")
        self.assertIsNone(result.id)


if __name__ == "__main__":
    unittest.main()
