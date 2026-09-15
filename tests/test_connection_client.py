"""Exercise the production Lightroom connection core in actual Lua 5.1."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime, lua_type

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "clients/lightroom/FlickrGroupAddr.lrplugin/ConnectionCore.lua"
)
PLUGIN_ROOT = SOURCE.parent
CREDENTIAL = "ABCD-" * 12 + "ABC0"
INSTALLATION_ID = "installation-1"


class ConnectionClientTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.core = self.lua.execute(SOURCE.read_text(encoding="utf-8"))
        self.calls: list[tuple[str, Any, int]] = []

    def plain(self, value: Any) -> Any:
        if lua_type(value) != "table":
            return value
        keys = list(value.keys())
        if keys and set(keys) == set(range(1, len(keys) + 1)):
            return [self.plain(value[index]) for index in range(1, len(keys) + 1)]
        return {key: self.plain(value[key]) for key in keys if value[key] is not None}

    def decode(self, body: str) -> Any:
        return self.lua.table_from(json.loads(body), recursive=True)

    def response(self, state: str = "current", **patch: Any) -> str:
        value = {
            "schemaVersion": 1,
            "installationId": INSTALLATION_ID,
            "installationRevision": 7,
            "installationState": "active",
            "presentedCredentialState": state,
            **patch,
        }
        return json.dumps(value)

    def headers(self, status: int, challenge: str | None = None) -> Any:
        value = self.lua.table_from({}, recursive=True)
        value["status"] = status
        if challenge is not None:
            value[1] = self.lua.table_from(
                {"field": "WWW-Authenticate", "value": challenge}, recursive=True
            )
        return value

    def get(self, body: str, status: int = 200, challenge: str | None = None) -> Any:
        def request(url, headers, timeout):
            self.calls.append((url, self.plain(headers), timeout))
            return body, self.headers(status, challenge)

        return request

    def test_canonical_plugin_code_is_strict(self):
        self.assertTrue(self.core.isCanonicalCredential(CREDENTIAL))
        for value in (
            CREDENTIAL.lower(),
            " " + CREDENTIAL[1:],
            CREDENTIAL[:-1] + "1",
            CREDENTIAL.replace("0", "O", 1),
            CREDENTIAL.replace("-", "", 1),
            CREDENTIAL + "0",
        ):
            with self.subTest(value=value):
                self.assertFalse(self.core.isCanonicalCredential(value))

    def test_release_bundle_identity_and_manifest(self):
        self.assertEqual(PLUGIN_ROOT.suffix, ".lrplugin")
        self.assertNotIn(".lrdevplugin", PLUGIN_ROOT.as_posix())
        manifest = self.plain(
            self.lua.execute((PLUGIN_ROOT / "Info.lua").read_text(encoding="utf-8"))
        )
        self.assertEqual(
            manifest["LrToolkitIdentifier"], "com.sixbuckssolutions.flickrgroupaddr"
        )
        self.assertEqual(manifest["LrPluginName"], "FlickrGroupAddr")
        self.assertEqual(manifest["LrPluginInfoProvider"], "PluginInfoProvider.lua")
        self.assertEqual(
            manifest["VERSION"], {"major": 0, "minor": 1, "revision": 0, "build": 1}
        )

    def test_store_precedes_clear_and_confirms_exact_retrieval(self):
        saved = {}
        events = []

        def store(key, value):
            events.append(("store", key))
            saved[key] = value

        def retrieve(key):
            events.append(("retrieve", key))
            return saved.get(key, "")

        ok, reason = self.core.storeCurrent(
            CREDENTIAL, store, retrieve, lambda: events.append(("clear", None))
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertEqual(
            events,
            [
                ("store", "fga.installation.current"),
                ("clear", None),
                ("retrieve", "fga.installation.current"),
            ],
        )

    def test_invalid_input_clears_without_storage_or_network(self):
        events = []
        ok, reason = self.core.storeCurrent(
            CREDENTIAL[:-1] + "1",
            lambda *_: events.append("store"),
            lambda *_: events.append("retrieve"),
            lambda: events.append("clear"),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_syntax")
        self.assertEqual(events, ["clear"])

    def test_safe_get_has_exact_url_and_single_bearer_header(self):
        outcome = self.plain(
            self.core.verifyCredential(
                CREDENTIAL, self.get(self.response()), self.decode, None
            )
        )
        self.assertEqual(outcome["state"], "connected")
        self.assertEqual(outcome["installationId"], INSTALLATION_ID)
        self.assertEqual(len(self.calls), 1)
        url, headers, timeout = self.calls[0]
        self.assertEqual(
            url, "https://flickrgroupaddr.com/api/v001/installations/current"
        )
        self.assertNotIn("?", url)
        self.assertEqual(
            headers,
            [{"field": "Authorization", "value": "Bearer " + CREDENTIAL}],
        )
        self.assertEqual(timeout, 30)

    def test_success_shape_and_expected_identity_are_exhaustive(self):
        cases = (
            self.response(extra="unexpected"),
            self.response(schemaVersion=2),
            self.response(installationRevision=0),
            self.response(installationState="revoked"),
            "[]",
            "not-json",
        )
        for body in cases:
            with self.subTest(body=body):
                outcome = self.plain(
                    self.core.verifyCredential(
                        CREDENTIAL, self.get(body), self.decode, INSTALLATION_ID
                    )
                )
                self.assertEqual(outcome["state"], "service_response_invalid")
        mismatch = self.plain(
            self.core.verifyCredential(
                CREDENTIAL, self.get(self.response()), self.decode, "another-installation"
            )
        )
        self.assertEqual(mismatch["state"], "service_response_invalid")

    def test_pending_candidate_never_marks_connection_active(self):
        outcome = self.plain(
            self.core.verifyCredential(
                CREDENTIAL, self.get(self.response("pending_rotation")), self.decode, None
            )
        )
        self.assertEqual(outcome["state"], "rotation_incomplete")

    def test_invalid_token_requires_matching_body_and_challenge(self):
        error = json.dumps(
            {
                "schemaVersion": 1,
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid installation credential.",
                    "retryable": False,
                    "correlationId": "00000000-0000-4000-8000-000000000000",
                },
            }
        )
        challenge = 'Bearer realm="fga-api", error="invalid_token"'
        outcome = self.plain(
            self.core.verifyCredential(
                CREDENTIAL, self.get(error, 401, challenge), self.decode, None
            )
        )
        self.assertEqual(outcome["state"], "invalid_token")
        unconfirmed = self.plain(
            self.core.verifyCredential(
                CREDENTIAL, self.get(error, 401, 'Bearer realm="fga-api"'), self.decode, None
            )
        )
        self.assertEqual(unconfirmed["state"], "authentication_unconfirmed")

    def test_transport_and_server_failure_keep_retry_path(self):
        def failed_request(*_):
            return None, self.headers(0)

        transport = self.plain(
            self.core.verifyCredential(CREDENTIAL, failed_request, self.decode, None)
        )
        server = self.plain(
            self.core.verifyCredential(
                CREDENTIAL, self.get("", 503), self.decode, None
            )
        )
        self.assertEqual(transport["state"], "retryable")
        self.assertEqual(server["state"], "retryable")

    def test_candidate_blocks_current_fallback_and_all_http(self):
        reads = []

        def retrieve(key):
            reads.append(key)
            return CREDENTIAL

        outcome = self.plain(
            self.core.verifyStored(
                retrieve,
                lambda *_: self.fail("candidate state must not make a request"),
                self.decode,
                None,
            )
        )
        self.assertEqual(outcome["state"], "rotation_incomplete")
        self.assertEqual(reads, ["fga.installation.rotation_candidate"])

    def test_results_never_contain_the_plugin_code(self):
        outcomes = [
            self.plain(
                self.core.verifyCredential(
                    CREDENTIAL, self.get(self.response()), self.decode, None
                )
            ),
            self.plain(
                self.core.verifyCredential(
                    CREDENTIAL, self.get("", 503), self.decode, None
                )
            ),
        ]
        for outcome in outcomes:
            self.assertNotIn(CREDENTIAL, repr(outcome))

    def controller(
        self, body: str, status: int, challenge: str | None = None
    ) -> tuple[Any, Any]:
        lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        lua.globals()["plugin_root"] = PLUGIN_ROOT.as_posix()
        lua.globals()["mock_body"] = body
        lua.globals()["mock_status"] = status
        lua.globals()["mock_challenge"] = challenge
        lua.execute(
            """
            package.path = plugin_root .. "/?.lua;" .. package.path
            mockStorage = {}
            mockPrefs = {}
            mockStores = {}
            mockCalls = 0
            mockLastUrl = nil
            mockLastHeaders = nil
            mockLastTimeout = nil

            local modules = {}
            modules.LrPasswords = {
                store = function(key, value, salt, pluginId)
                    mockStorage[key] = value
                    mockStores[#mockStores + 1] = {
                        key = key, value = value, salt = salt, pluginId = pluginId
                    }
                end,
                retrieve = function(key, salt, pluginId)
                    return mockStorage[key] or ""
                end,
            }
            modules.LrPrefs = { prefsForPlugin = function() return mockPrefs end }
            modules.LrTasks = { startAsyncTask = function(task) task() end }
            modules.LrHttp = {
                get = function(url, headers, timeout)
                    mockCalls = mockCalls + 1
                    mockLastUrl = url
                    mockLastHeaders = headers
                    mockLastTimeout = timeout
                    local responseHeaders = { status = mock_status }
                    if mock_challenge ~= nil then
                        responseHeaders[1] = {
                            field = "WWW-Authenticate", value = mock_challenge
                        }
                    end
                    return mock_body, responseHeaders
                end,
            }
            function import(name) return modules[name] end
            """
        )
        controller = lua.execute('return require "ConnectionController"')
        return lua, controller

    def test_controller_stores_clears_then_connects_with_sdk_adapters(self):
        lua, controller = self.controller(self.response(), 200)
        properties = lua.table_from(
            {
                "pluginCode": CREDENTIAL,
                "busy": False,
                "hasStoredCode": False,
                "canStore": True,
                "installation": "Not connected",
            },
            recursive=True,
        )
        controller.storeAndVerify(properties)
        globals_ = lua.globals()
        self.assertEqual(properties["pluginCode"], "")
        self.assertEqual(properties["status"], "Connected.")
        self.assertEqual(properties["installation"], "installation-1 (revision 7)")
        self.assertEqual(globals_.mockCalls, 1)
        self.assertEqual(globals_.mockLastUrl, self.core.CURRENT_URL)
        self.assertEqual(globals_.mockLastTimeout, 30)
        self.assertEqual(
            globals_.mockStores[1]["key"], "fga.installation.current"
        )
        self.assertIsNone(globals_.mockStores[1]["salt"])
        self.assertEqual(
            globals_.mockStores[1]["pluginId"],
            "com.sixbuckssolutions.flickrgroupaddr",
        )
        self.assertEqual(globals_.mockPrefs["installationId"], INSTALLATION_ID)

    def test_controller_clears_rejected_current_code(self):
        error = json.dumps(
            {
                "schemaVersion": 1,
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid installation credential.",
                    "retryable": False,
                    "correlationId": "00000000-0000-4000-8000-000000000000",
                },
            }
        )
        lua, controller = self.controller(
            error, 401, 'Bearer realm="fga-api", error="invalid_token"'
        )
        properties = lua.table_from(
            {
                "pluginCode": CREDENTIAL,
                "busy": False,
                "hasStoredCode": False,
                "canStore": True,
                "installation": "Not connected",
            },
            recursive=True,
        )
        controller.storeAndVerify(properties)
        globals_ = lua.globals()
        self.assertEqual(
            globals_.mockStorage["fga.installation.current"], ""
        )
        self.assertTrue(properties["canStore"])
        self.assertIn("invalid", properties["status"].lower())
        self.assertNotIn(CREDENTIAL, properties["status"])


if __name__ == "__main__":
    unittest.main()
