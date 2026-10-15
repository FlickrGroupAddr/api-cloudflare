"""Production group discovery rules exercised in Lightroom's Lua 5.1 runtime."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
CREDENTIAL = "ABCD-" * 12 + "ABC0"


class GroupDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.core = self.lua.execute((BUNDLE / "ConnectionCore.lua").read_text("utf-8"))
        self.module = self.lua.execute((BUNDLE / "GroupDiscoveryClient.lua").read_text("utf-8"))
        self.client = self.module.new(self.core)
        self.json = self.lua.execute((BUNDLE / "dkjson.lua").read_text("utf-8"))
        self.decode = self.lua.eval(
            "function(json) return function(body) "
            "local value,pos,err=json.decode(body,1,json.null); "
            "if err or body:sub(pos):find('%S') then return nil end; return value end end"
        )(self.json)
        self.calls = []
        self.waits = []
        self.progress = []
        self.cancel = False
        self.after_get = None
        self.store = {self.core.CURRENT_KEY: CREDENTIAL}

    @staticmethod
    def page(ids=None, **patch):
        ids = [] if ids is None else ids
        return {
            "schemaVersion": 1,
            "snapshotRevision": 7,
            "refreshedAt": "2026-10-15T12:00:00.000000Z",
            "snapshotStatus": "fresh",
            "groups": [{"flickrGroupId": key, "displayName": "Group " + key} for key in ids],
            "nextAfterGroupId": None,
            **patch,
        }

    @staticmethod
    def changed():
        return {
            "schemaVersion": 1,
            "error": {
                "code": "snapshot_changed",
                "message": "Restart",
                "retryable": False,
                "correlationId": "request-1",
            },
        }

    def discover(self, responses, candidate=None, identity="installation-1", sleep=None):
        if candidate:
            self.store[self.core.CANDIDATE_KEY] = candidate
        sequence = iter(responses)

        def get(url, headers, timeout):
            self.calls.append((url, headers[1]["value"], timeout))
            if url == self.core.CURRENT_URL:
                document = {
                    "schemaVersion": 1,
                    "installationId": "installation-1",
                    "installationRevision": 1,
                    "installationState": "active",
                    "presentedCredentialState": "current",
                }
                return json.dumps(document), self.lua.table_from({"status": 200})
            response = next(sequence)
            value, status = response[:2]
            native_headers = self.lua.table_from({"status": status})
            if len(response) == 3:
                for index, delay in enumerate(response[2], 1):
                    native_headers[index] = self.lua.table_from(
                        {"field": "Retry-After", "value": delay}
                    )
            if self.after_get is not None:
                self.after_get()
            return value if isinstance(value, str) else json.dumps(value), native_headers

        # SDK callbacks are Lua functions in production. Wrap the Python callbacks
        # so callback type validation exercises the same interface.
        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        return self.client.discoverStored(
            self.store.get,
            get,
            self.decode,
            wrap(sleep or self.waits.append),
            wrap(lambda: self.cancel),
            identity,
            self.json.null,
            self.progress.append,
        )

    def assert_failed(self, result, state="service_response_invalid"):
        self.assertEqual(result.state, state)
        self.assertIsNone(result.groups)

    def test_complete_empty_and_stale_results(self):
        for status in ("fresh", "stale_refreshing", "stale_refresh_failed"):
            patch = {"snapshotStatus": status}
            if status == "stale_refresh_failed":
                patch["refreshFailedAt"] = "2026-10-15T12:01:00Z"
            result = self.discover([(self.page(**patch), 200)])
            self.assertEqual(result.state, "complete")
            self.assertEqual(len(result.groups), 0)
            self.assertEqual(result.snapshotStatus, status)
            self.assertEqual(result.refreshFailedAt, patch.get("refreshFailedAt"))

    def test_authenticated_keyset_aggregate_and_escaped_identity(self):
        ids = [f"a{index:03d}" for index in range(99)] + ["z@pool:1"]
        result = self.discover(
            [(self.page(ids, nextAfterGroupId=ids[-1]), 200), (self.page(["zz"]), 200)]
        )
        self.assertEqual(result.state, "complete")
        self.assertEqual(len(result.groups), 101)
        self.assertEqual(result.groups[100].flickrGroupId, ids[-1])
        self.assertEqual(result.groups[101].flickrGroupId, "zz")
        self.assertIn("snapshot_revision=7&after_group_id=z%40pool%3A1", self.calls[-1][0])
        self.assertTrue(all(call[1] == "Bearer " + CREDENTIAL for call in self.calls))
        self.assertTrue(all(call[2] == 30 for call in self.calls))

    def test_revision_conflict_discards_prefix_and_restarts_once(self):
        ids = [f"a{index:03d}" for index in range(100)]
        result = self.discover(
            [
                (self.page(ids, nextAfterGroupId=ids[-1]), 200),
                (self.changed(), 409),
                (self.page(["replacement"], snapshotRevision=8), 200),
            ]
        )
        self.assertEqual(result.state, "complete")
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[1].flickrGroupId, "replacement")
        self.assertEqual(self.calls[-1][0], self.module.URL + "?page_size=100")
        self.assert_failed(
            self.discover([(self.changed(), 409), (self.changed(), 409)]), "snapshot_changed"
        )

    def test_rotation_and_retained_identity_gate_precedes_group_read(self):
        self.assert_failed(self.discover([], candidate="candidate"), "rotation_incomplete")
        self.assertEqual(len(self.calls), 0)
        self.store.pop(self.core.CANDIDATE_KEY)
        self.assert_failed(self.discover([], identity="other"))
        self.assertEqual(len(self.calls), 1)

    def test_pending_honors_retry_after_and_is_cancellable(self):
        pending = {"schemaVersion": 1, "status": "refreshing"}
        result = self.discover([(pending, 202, ["2"]), (self.page(), 200)])
        self.assertEqual(result.state, "complete")
        self.assertEqual(self.waits, [1, 1])
        self.assertEqual(self.progress, ["refreshing"])

        def sleep(_):
            self.cancel = True

        self.assert_failed(self.discover([(pending, 202, ["60"])], sleep=sleep), "cancelled")

    def test_pending_waits_and_polls_are_bounded(self):
        pending = {"schemaVersion": 1, "status": "refreshing"}
        for delays in (["0"], ["61"], ["-1"], ["1.5"], ["1", "1"], [], ["Wed"]):
            with self.subTest(delays=delays):
                self.assert_failed(self.discover([(pending, 202, delays)]))
        self.assert_failed(self.discover([(pending, 202, ["60"])] * 2), "retryable")
        self.assert_failed(self.discover([(pending, 202, ["1"])] * 13), "retryable")

    def test_rotation_during_pending_wait_stops_before_next_request(self):
        pending = {"schemaVersion": 1, "status": "refreshing"}
        for key, value in (
            (self.core.CANDIDATE_KEY, "new-candidate"),
            (self.core.CURRENT_KEY, "WXYZ-" * 12 + "ABC0"),
        ):
            with self.subTest(key=key):
                self.store = {self.core.CURRENT_KEY: CREDENTIAL}
                self.calls = []

                def sleep(_, key=key, value=value):
                    self.store[key] = value

                self.assert_failed(
                    self.discover([(pending, 202, ["1"])], sleep=sleep),
                    "rotation_incomplete",
                )
                self.assertEqual(len(self.calls), 2)

    def test_rotation_while_http_yields_discards_complete_result(self):
        self.after_get = lambda: self.store.update({self.core.CANDIDATE_KEY: "candidate"})
        self.assert_failed(self.discover([(self.page(["a"]), 200)]), "rotation_incomplete")
        self.assertEqual(len(self.calls), 2)

    def test_closed_pages_reject_malformed_shapes(self):
        bad_pages = [
            self.page(extra=True),
            self.page(snapshotRevision=1.5),
            self.page(refreshedAt="2026-02-30T12:00:00Z"),
            self.page(snapshotStatus="unknown"),
            self.page(snapshotStatus="stale_refresh_failed"),
            self.page(refreshFailedAt="2026-10-15T12:00:00Z"),
            self.page(groups={}),
            self.page(["b", "a"]),
            self.page(["a", "a"]),
            self.page(["a"], nextAfterGroupId="b"),
            self.page(groups=[{"flickrGroupId": "a", "displayName": "A", "extra": 1}]),
            self.page(groups=[{"flickrGroupId": "a", "displayName": "x" * 1025}]),
            self.page(groups=[{"flickrGroupId": "a", "displayName": "\nsecret"}]),
        ]
        missing_next = self.page()
        del missing_next["nextAfterGroupId"]
        bad_pages.append(missing_next)
        for page in bad_pages:
            with self.subTest(page=page):
                self.assert_failed(self.discover([(page, 200)]))

    def test_failed_later_page_never_exposes_partial_groups(self):
        ids = [f"a{index:03d}" for index in range(100)]
        first = (self.page(ids, nextAfterGroupId=ids[-1]), 200)
        for response, state in [
            ((self.page(["a000"]), 200), "service_response_invalid"),
            ((self.page(["z"], snapshotRevision=8), 200), "service_response_invalid"),
            (("provider exception with secret", 503), "service_response_invalid"),
            (({}, 503), "retryable"),
            (({}, 401), "authentication_unconfirmed"),
            (({}, 403), "administrative_repair"),
        ]:
            with self.subTest(response=response):
                self.assert_failed(self.discover([first, response]), state)

    def test_body_row_page_limits_and_strict_json(self):
        self.assert_failed(self.discover([(" " * (2 * 1024 * 1024 + 1), 200)]))
        self.assert_failed(self.discover([(json.dumps(self.page()) + " {}", 200)]))
        for key in ('"snapshotRevision"', '"snapshot\\u0052evision"'):
            body = json.dumps(self.page()).replace(
                '"snapshotRevision": 7', key + ': 6, "snapshotRevision": 7'
            )
            self.assert_failed(self.discover([(body, 200)]))
        self.assert_failed(self.discover([(self.page([f"a{i:03d}" for i in range(101)]), 200)]))
        self.module.MAX_PAGES = 1
        ids = [f"a{index:03d}" for index in range(100)]
        self.assert_failed(self.discover([(self.page(ids, nextAfterGroupId=ids[-1]), 200)]))
        self.module.MAX_PAGES = 100
        self.module.MAX_GROUPS = 1
        self.assert_failed(self.discover([(self.page(["a", "b"]), 200)]))


if __name__ == "__main__":
    unittest.main()
