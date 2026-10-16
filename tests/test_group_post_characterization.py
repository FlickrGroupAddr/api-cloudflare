"""Offline finite POST packet tests: actual Lua51 clients, lifecycle, SQL bounds."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

from scripts.group_post_characterization import Lifecycle

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "probes/lightroom/FGA-GroupPost-v1.lrplugin"
RELEASE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"


class NativePostTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.module = self.lua.execute((NATIVE / "Post.lua").read_text())
        self.json = self.lua.execute((RELEASE / "dkjson.lua").read_text())
        self.proof = self.lua.execute((RELEASE / "ExistingPhotoClient.lua").read_text())
        self.batch = self.lua.execute((RELEASE / "GroupSubmissionClient.lua").read_text())
        self.target = self.lua.table_from(
            {
                "schemaVersion": 1,
                "planVersion": "fga-group-post-v1",
                "runId": "a" * 24,
                "subdomain": "synthetic",
                "access": "b" * 64,
                "canary": "SYNTHETIC-" + "c" * 32,
                "expiresAtUnix": 1800001200,
            }
        )
        self.clock, self.canceled, self.calls = 1800000000, False, []

    def execute(self, cancel_at=None):
        def post(url, body, headers, method, timeout):
            self.assertTrue(
                url.startswith(
                    "https://fga-post-src-" + "a" * 24 + ".synthetic.workers.dev/v1/cases/"
                )
            )
            self.assertEqual(method, "POST")
            self.assertEqual(timeout, 15)
            values = {h["field"]: h["value"] for h in headers.values()}
            self.assertEqual(values["Authorization"], "Bearer SYNTHETIC-" + "c" * 32)
            self.assertEqual(values["Content-Type"], "application/json")
            data = json.loads(body)
            self.assertEqual(data["schemaVersion"], 1 if url.endswith("/proof") else 2)
            if url.endswith("/batch-sixty"):
                self.assertEqual(len(data["flickrGroupIds"]), 60)
            self.calls.append(body)
            if len(self.calls) == cancel_at:
                self.canceled = True
            return "PRIVATE-UNRETAINED-RESPONSE", self.lua.table_from({"status": 202})

        encoder = self.lua.eval(
            "function(json) return {encode=function(v) return json.encode(v,{keyorder={"
            "'schemaVersion','photoBinding','fgaPhotoBindingId',"
            "'expectedVerificationRevision','flickrGroupIds'}}) end} end"
        )(self.json)
        deps = self.lua.table_from(
            {
                "now": lambda: self.clock,
                "cancelled": lambda: self.canceled,
                "post": post,
                "get": lambda *_: ("{}", self.lua.table_from({"status": 200})),
                "json": encoder,
                "proof": self.proof,
                "batch": self.batch,
            }
        )
        return self.module.execute(self.target, deps)

    def test_actual_clients_and_exact_sdk_post_shape(self):
        state = self.execute()
        self.assertEqual(state["postCalls"], 23)
        self.assertEqual(state["getCalls"], 1)
        self.assertFalse(state["productionQualified"])
        self.assertEqual(
            self.calls[0],
            '{"schemaVersion":1,"flickrPhotoId":"SYNTHETIC-PHOTO","expectedLinkedFlickrRevision":1}',
        )
        self.assertEqual(
            self.calls[1],
            '{"schemaVersion":2,"photoBinding":{"fgaPhotoBindingId":"SYNTHETIC-BINDING","expectedVerificationRevision":1},"flickrGroupIds":["SYNTHETIC-GROUP-01"]}',
        )
        self.assertNotIn("PRIVATE-UNRETAINED", self.json.encode(state))

    def test_stop_during_post_retains_observation_and_makes_no_more_requests(self):
        state = self.execute(cancel_at=2)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(state["outcome"], "stopped")
        self.assertEqual(state["reasonCode"], "cancelled")
        self.assertEqual(state["getCalls"], 0)

    def test_preexisting_stop_and_arbitrary_target_fail_closed(self):
        self.canceled = True
        self.assertEqual(self.execute()["postCalls"], 0)
        self.canceled = False
        self.target["source"] = "https://example.com"
        self.assertEqual(self.execute()["postCalls"], 0)

    def test_lua_files_parse_without_loading_native_sdk(self):
        for name in ("Info.lua", "Run.lua"):
            self.lua.execute("assert(loadstring(...))", (NATIVE / name).read_text())


class LifecycleTests(unittest.TestCase):
    def test_full_prepare_stop_export_and_identity_matched_cleanup(self):
        class API:
            account = "a" * 32

            def __init__(self):
                self.objects = {}
                self.calls = []

            def call(self, method, path, body: Any = None, timeout=20):
                self.calls.append((method, path, timeout))
                if method == "GET":
                    return (
                        (200, {"result": self.objects[path]}) if path in self.objects else (404, {})
                    )
                if method == "DELETE":
                    self.objects.pop(path + "/settings" if path.startswith("/workers") else path)
                    return 200, {"success": True}
                if path == "/d1/database":
                    value = {"name": body["name"], "uuid": "11111111-1111-4111-8111-111111111111"}
                    self.objects[path + "/" + value["uuid"]] = value
                    return 200, {"success": True, "result": value}
                if path.endswith("/query"):
                    return 200, {"success": True, "result": [{"success": True, "results": []}]}
                if method == "PUT":
                    self.objects[path + "/settings"] = {"bindings": body["metadata"]["bindings"]}
                    return 200, {"success": True, "result": {"id": path.split("/")[-1]}}
                return 200, {"success": True, "result": body}

        with tempfile.TemporaryDirectory() as temporary:
            api = API()
            life = Lifecycle(api, Path(temporary), "a" * 24, "123", clock=lambda: 1800000000)
            target = life.prepare("synthetic", "b" * 64, "SYNTHETIC-" + "c" * 32)
            self.assertEqual(target["expiresAtUnix"], 1800001200)
            receipt = life.hold_and_cleanup(lambda: True, sleep=lambda _: self.fail("stop slept"))
            self.assertTrue(receipt["cleanupConfirmed"])
            self.assertTrue(life.journal["observationsConfirmed"])
            self.assertEqual(api.objects, {})
            self.assertLess(len(api.calls), 120)
            self.assertTrue(all(timeout == 20 for _, _, timeout in api.calls))
            public = (Path(temporary) / "cleanup.json").read_text()
            self.assertNotIn("b" * 64, public)
            self.assertNotIn("SYNTHETIC-", public)

    def test_lost_create_response_preserves_unresolved_resource_and_no_guessed_delete(self):
        class API:
            account = "a" * 32

            def call(self, method, path, *_args, **_kwargs):
                if method == "GET":
                    return 404, {}
                if method == "POST" and path == "/d1/database":
                    raise TimeoutError("unretained-provider-detail")
                raise AssertionError("unexpected or guessed cleanup")

        with tempfile.TemporaryDirectory() as temporary:
            life = Lifecycle(API(), Path(temporary), "a" * 24, "123", clock=lambda: 1800000000)
            with self.assertRaises(TimeoutError):
                life.prepare("synthetic", "b" * 64, "SYNTHETIC-" + "c" * 32)
            self.assertEqual(life.journal["stage"], "cleanup_unconfirmed")
            public = (Path(temporary) / "cleanup.json").read_text()
            self.assertNotIn("unretained-provider-detail", public)

    def test_exact_identity_cleanup_and_sanitized_terminal_receipt(self):
        class API:
            account = "a" * 32

            def __init__(self):
                self.deleted = False
                self.calls = []

            def call(self, method, path, body, timeout):
                self.calls.append((method, path, timeout))
                if method == "DELETE":
                    self.deleted = True
                    return 200, {"success": True}
                return (
                    (404, {})
                    if self.deleted
                    else (
                        200,
                        {"result": {"name": "fga-post-db-" + "a" * 24, "uuid": "synthetic-id"}},
                    )
                )

        with tempfile.TemporaryDirectory() as temporary:
            api = API()
            life = Lifecycle(api, Path(temporary), "a" * 24, "123", clock=lambda: 1800000000)
            life.journal["resources"] = [
                {
                    "kind": "database",
                    "name": "fga-post-db-" + "a" * 24,
                    "id": "synthetic-id",
                    "path": "/d1/database/synthetic-id",
                    "deletePath": "/d1/database/synthetic-id",
                    "acknowledged": True,
                }
            ]
            self.assertTrue(life.cleanup()["cleanupConfirmed"])
            self.assertEqual(len(api.calls), 3)
            self.assertNotIn("synthetic-id", (Path(temporary) / "cleanup.json").read_text())

    def test_missing_ack_or_identity_mismatch_never_deletes(self):
        class API:
            account = "a" * 32

            def call(self, method, *_args, **_kwargs):
                if method == "DELETE":
                    raise AssertionError("unmatched delete")
                return 200, {"result": {"name": "foreign"}}

        for ack in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                life = Lifecycle(API(), Path(temporary), "a" * 24, "123", clock=lambda: 1800000000)
                life.journal["resources"] = [
                    {
                        "kind": "worker",
                        "name": "owned",
                        "path": "/workers/scripts/owned/settings",
                        "acknowledged": ack,
                    }
                ]
                self.assertFalse(life.cleanup()["cleanupConfirmed"])

    def test_atomic_durable_cap_uses_one_update(self):
        db = sqlite3.connect(":memory:")
        db.executescript((ROOT / "probes/group-post-characterization/schema.sql").read_text())
        db.execute("INSERT INTO post_budget VALUES(?,?,?,?)", ("run", "source", 9999999999, 0))
        sql = (
            "UPDATE post_budget SET requests=requests+1 WHERE run_id=? AND role=? "
            "AND expires_at=? AND expires_at>unixepoch() AND requests<64 RETURNING requests"
        )
        counts = [db.execute(sql, ("run", "source", 9999999999)).fetchone() for _ in range(65)]
        self.assertEqual(counts[-2], (64,))
        self.assertIsNone(counts[-1])
        db.close()


if __name__ == "__main__":
    unittest.main()
