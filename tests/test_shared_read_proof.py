"""Offline actual Lua5.1 READ policy and proof protocol; no native qualification."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class SharedReadProofTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().bundle = BUNDLE.as_posix()
        self.lua.execute((ROOT / "tests/shared_read_proof_fixture.lua").read_text("utf-8-sig"))

    def check(self, code):
        self.lua.execute(code)

    def test_release_constructor_disabled_before_credential_access(self):
        self.check("""
            local value,reason=Read.new{retrieve=function() error('credential access') end}
            assert(value==nil and reason=='qualification_required' and reads==0 and gets==0)
            assert(not Read.PRODUCTION_QUALIFIED and not read.capabilities.readTransport)
            assert(not Proof.PRODUCTION_QUALIFIED and not Proof.PROOF_POST_AVAILABLE)
        """)

    def test_discovery_uses_actual_existing_client_and_fixed_origin(self):
        self.check("""
            local result=assert(Photo.discover(protocol,1,5))
            assert(result.total==0 and gets==2)
            assert(getmetatable(result.photos).__jsontype=='array')
        """)

    def test_exact_read_allowlist(self):
        paths = [
            "/api/v001/installations/current",
            "/api/v001/groups?page_size=100&snapshot_revision=9007199254740991&after_group_id=g%40N00",
            "/api/v001/photo-bindings/binding/group-memberships?page_size=100",
            "/api/v001/group-submission-intents?view=history&page_size=100&photo_binding_id=binding",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(self.lua.eval("Read.allowedPath")(path)[0])

    def test_rejects_paths_before_credential_access(self):
        for path in (
            "/api/v001/groups?page_size=100&page_size=1",
            "/api/v001/groups?page_size=100&unknown=1",
            "/api/v001/groups?page_size=0100",
            "/api/v001/groups?page_size=100&after_group_id=g",
            "/api/v001/groups?page_size=100&snapshot_revision=1&after_group_id=%2Fg",
            "/api/v001/groups?page_size=100&snapshot_revision=1&after_group_id=%67",
            "/api/v001/../admin/",
            "/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=5&linked_flickr_revision=2",
            "/api/v001/installations/current#fragment",
            "//evil.test/api/v001/groups?page_size=100",
        ):
            with self.subTest(path=path):
                self.lua.globals().badPath = path
                self.check("""
                    local before=reads
                    assert(read.httpGet(Read.ORIGIN..badPath,headers,30)==nil)
                    assert(reads==before and gets==0)
                """)
        self.check(
            "assert(read.httpGet('https://flickrgroupaddr.com.evil.test/api/v001/groups?page_size=100',headers,30)==nil)"
        )

    def test_strict_json_null_array_object_and_duplicate_keys(self):
        self.check("""
            assert(Read.decode('null')==Read.jsonNull)
            assert(getmetatable(Read.decode('[]')).__jsontype=='array')
            assert(getmetatable(Read.decode('{}')).__jsontype=='object')
        """)
        for raw in (
            '{"x":1,"x":2}',
            '{"x":1,"\\u0078":2}',
            '{"x":1,}',
            '{"x":1 "y":2}',
            "[1,]",
            "/*bad*/{}",
            "{} trailing",
            "01",
            "1e999",
            "[nan]",
            '{"x":"\\q"}',
            '{"x":"\\uD800"}',
            "[" * 33 + "0" + "]" * 33,
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(self.lua.eval("Read.decode")(raw))
        self.check("assert(Read.decode(string.char(255))==nil)")

    def test_malformed_error_and_oversized_bodies_never_escape(self):
        self.check("""
            for _,bytes in ipairs({'private raw body','{"error":null,}',string.rep('x',2097153)}) do
                responses[url]=response(bytes)
                local body,h=get()
                assert(body==nil and next(h)==nil)
            end
            responses[Core.CURRENT_URL]=response(string.rep('x',65537))
            assert(read.httpGet(Core.CURRENT_URL,headers,30)==nil)
            responses[url]=response('null')
            assert(get()==nil)
            failGet=true
            local body,h=get()
            assert(body==nil and next(h)==nil)
        """)

    def test_redirect_bad_headers_and_length_fail_closed(self):
        self.check("""
            for _,status in ipairs({201,204,301,302,307,308}) do
                responses[url]=response(page,status)
                assert(get()==nil)
            end
            for _,header in ipairs({{field='Location',value='https://evil.test/'},
                {field='Content-Type',value='application/json'},
                {field='Content-Length',value='1'},
                {field='X-Raw',value='private\\r\\nheader'}}) do
                responses[url]=response(page)
                table.insert(responses[url][2],header)
                assert(get()==nil)
            end
            responses[url]={page,{status=200,{field='Content-Type',value='application/json'}}}
            assert(get()==nil)
        """)

    def test_header_tokens_reject_internal_whitespace_and_malformed_parameters(self):
        for index, values in (
            (
                1,
                (
                    "app lication/json",
                    "application/ json",
                    "application/json;charset=utf -8",
                    "application/json;char set=utf-8",
                    "application/json;charset= utf-8",
                    "application/json; charset=utf-8; charset=utf-8",
                ),
            ),
            (
                2,
                (
                    "no- store",
                    "private, no-\tstore",
                    "no-store=true",
                    "private no-store",
                    'private="no-store"',
                    'private="foo,no-store,bar"',
                    'no-store, extension="unterminated',
                    "no-store, max age=0",
                ),
            ),
        ):
            for raw in values:
                with self.subTest(header=index, value=raw):
                    self.lua.globals().header_index = index
                    self.lua.globals().header_value = raw
                    self.check("""
                        local h=response(page)[2]
                        h[header_index].value=header_value
                        local body,safe=Read.response(page,h,2097152)
                        assert(body==nil and next(safe)==nil)
                        responses[url]={page,h}
                        assert(get()==nil)
                    """)

    def test_header_tokens_accept_legal_ows_case_and_quoted_values(self):
        for media in (
            "application/json",
            " \tApplication/JSON\t ",
            "application/json ;\tcharset=UTF-8",
            'application/json; charset="utf-8"',
        ):
            for cache in (
                "no-store",
                " \tPRIVATE , \tNo-Store\t ",
                "max-age=0, no-store, no-transform",
                'extension="a, b", no-store',
                'extension="a\\\\\\"b", no-store',
            ):
                with self.subTest(media=media, cache=cache):
                    self.lua.globals().media_value = media
                    self.lua.globals().cache_value = cache
                    self.check("""
                        local h=response(page)[2]
                        h[1].value=media_value
                        h[2].value=cache_value
                        local body,safe=Read.response(page,h,2097152)
                        assert(body==page and safe.status==200)
                        responses[url]={page,h}
                        assert(get()==page)
                    """)

    def test_error_headers_sanitized_and_safe_error_code_preserved(self):
        self.check("""
            local raw=json.encode{schemaVersion=1,error={code='invalid_token',
                message='private',retryable=false,correlationId='c'}}
            responses[url]=response(raw,401)
            assert(get()==nil)
            table.insert(responses[url][2],{field='WWW-Authenticate',
                value='Bearer realm="fga-api", error="invalid_token"'})
            table.insert(responses[url][2],{field='X-Raw',value='private'})
            local body,h=get()
            assert(body==raw and h.status==401 and h.error==nil)
            local _,reason=Photo.discover(protocol,1,5)
            assert(reason=='invalid_token')
        """)

    def test_rotation_context_cancellation_and_clock_fence_after_yield(self):
        for mutation in (
            "current=string.rep('0000-',12)..'0010'",
            "candidate='rotation'",
            "context=false",
            "cancelled=true",
            "clock=30",
            "clock=-1",
            "clock=0/0",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.check("afterGet=function() " + mutation + " end; assert(get()==nil)")
        for mutation in ("context=false", "cancelled=true", "candidate='rotation'"):
            with self.subTest(before=mutation):
                self.setUp()
                self.check(mutation + "; assert(get()==nil and gets==0)")

    def test_cancellation_latches_and_credential_isolation(self):
        self.check("""
            read.cancel()
            local before=reads
            assert(get()==nil and read.retrieve(Core.CURRENT_KEY)==nil and reads==before)
            read=makeRead()
            local foreign={{field='Authorization',value='Bearer foreign'}}
            assert(read.httpGet(url,foreign,30)==nil and gets==0)
            assert(read.httpGet(url,headers,15)==nil and gets==0)
        """)

    def test_actual_group_and_membership_clients(self):
        self.check("""
            local groupUrl=Read.ORIGIN..'/api/v001/groups?page_size=100'
            responses[groupUrl]=response('{"schemaVersion":1,"snapshotRevision":1,"refreshedAt":"2026-10-17T12:00:00Z","snapshotStatus":"fresh","groups":[],"nextAfterGroupId":null}')
            local result=Groups.discoverStored(
                read.retrieve,read.httpGet,Read.decode,function() end,
                read.cancelled,'install',Read.jsonNull)
            assert(result.state=='complete' and #result.groups==0)
            local memberUrl=Read.ORIGIN..'/api/v001/photo-bindings/binding/'
                ..'group-memberships?page_size=100'
            responses[memberUrl]=response('{"schemaVersion":1,"fgaPhotoBindingId":"binding","flickrPhotoId":"photo","observationRevision":1,"observedAt":"2026-10-17T12:00:00Z","groups":[],"nextAfterGroupId":null}')
            assert(#assert(Photo.memberships(protocol,binding)).groups==0)
        """)

    def test_proof_post_absent_and_separate_synthetic_injection(self):
        self.check("""
            assert(protocol.prove('photo',2)==nil and posts==0)
            protocol=assert(Proof.new(read,{httpPost=syntheticPost,capabilities={proofTransport=true}}))
            assert(protocol.prove('photo',2).verificationRevision==3 and posts==1)
            assert(not protocol.capabilities.proofTransport and not protocol.PRODUCTION_QUALIFIED)
        """)

    def test_proof_post_rotation_exception_and_correlation_fail_closed(self):
        for mutation in (
            "candidate='rotation'",
            "error('private post failure')",
            "binding.flickrPhotoId='wrong'",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.check(
                    """
                    protocol=assert(Proof.new(read,{httpPost=syntheticPost,capabilities={proofTransport=true}}))
                    postHook=function() """
                    + mutation
                    + """ end
                    assert(protocol.prove('photo',2)==nil and posts==1)
                """
                )

    def test_actual_history_client_and_cursor_allowlist(self):
        self.check("""
            local historyUrl=Read.ORIGIN..'/api/v001/group-submission-intents'
                ..'?view=history&page_size=100&photo_binding_id=binding'
            local empty=setmetatable({},{__jsontype='array'})
            local null=Read.jsonNull
            local gates=setmetatable({},{__jsontype='array'})
            for _,scope in ipairs({'user','deployment'}) do
                gates[#gates+1]={scope=scope,state='enabled',revision=1,pausedAt=null,
                    reasonCode=null,affectedActiveIntentCount=0}
            end
            responses[historyUrl]=response(json.encode{schemaVersion=1,
                observedAt='2026-10-17T12:00:00.000000Z',view='history',pageSize=100,
                photoBindingId='binding',summary={activeIntentCount=0,activePartitionCount=0,
                    attentionIntentCount=0,oldestActiveEnqueuedAt=null,writeGates=gates},
                intents=empty,nextPage=null,recommendedPollAfterSeconds=null})
            protocol.sleep=function() end
            local result=Status.history(protocol,binding)
            assert(result.state=='complete' and result.requestCount==2 and #result.intents==0)
            assert(Read.allowedPath('/api/v001/group-submission-intents'
                ..'?view=history&page_size=100&photo_binding_id=binding'
                ..'&before_created_at=2026-10-17T12%3A00%3A00.123456Z&before_intent_id=intent'))
            responses[url]=response(page)
            responses[url][2].error={errorMessage='private'}
            assert(get()==nil)
        """)

    def test_yielding_get_uses_injected_protector_without_raw_pcall(self):
        self.check("""
            -- Synthetic coroutine-based yield-safe protector, not host evidence.
            local function protect(fn)
                local co=coroutine.create(fn)
                local result={coroutine.resume(co)}
                while result[1] and coroutine.status(co)~='dead' do
                    coroutine.yield(result[2])
                    result={coroutine.resume(co)}
                end
                return unpack(result)
            end
            yieldGet=true
            read=makeRead(protect)
            local co=coroutine.create(get)
            local ok,marker=coroutine.resume(co)
            assert(ok and marker=='network')
            local done,body=coroutine.resume(co)
            assert(done and body==page and coroutine.status(co)=='dead')
        """)


if __name__ == "__main__":
    unittest.main()
