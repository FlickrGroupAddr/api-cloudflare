"""Offline full action ownership and actual Run.lua SDK-stub checks."""

from __future__ import annotations

import json
import ntpath
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from lupa.lua51 import LuaRuntime

from scripts import group_post_characterization as packet

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "probes/lightroom/FGA-GroupPost-v1.lrplugin"
RELEASE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
RUN = "a" * 24


class FakeProvider:
    account = "a" * 32

    def __init__(self):
        self.objects = {}
        self.calls = []

    def call(self, method, path, body: Any = None, timeout=20):
        self.calls.append((method, path, timeout))
        if method == "GET":
            return (200, {"result": self.objects[path]}) if path in self.objects else (404, {})
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


class RunnerTests(unittest.TestCase):
    def run_fixture(self, behavior, *, stop=False, bad_manifest=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probe = root / "packet"
            probe.mkdir()
            for filename in ("worker.mjs", "schema.sql"):
                (probe / filename).write_bytes((packet.PACKET / filename).read_bytes())
            (probe / "manifest.json").write_text(json.dumps({"approved": not bad_manifest}))
            api = FakeProvider()
            now = [1800000000]
            invokes = []

            def invoke(target, status):
                config = json.loads(target.read_text())
                self.assertEqual(config["runId"], RUN)
                invokes.append(config["runId"])
                if behavior == "throw":
                    raise RuntimeError("PRIVATE-NATIVE-DETAIL")
                if behavior in ("terminal", "wrong-run", "failed"):
                    status.write_text(
                        json.dumps(
                            {
                                "schemaVersion": 1,
                                "planVersion": packet.VERSION,
                                "runId": "b" * 24 if behavior == "wrong-run" else RUN,
                                "outcome": "failed" if behavior == "failed" else "characterized",
                                "reasonCode": "fixture_failure",
                                "postCalls": 1 if behavior == "failed" else 23,
                                "getCalls": 0 if behavior == "failed" else 1,
                                "productionQualified": False,
                                "remoteCleanupConfirmed": False,
                            }
                        )
                    )

            def sleep(seconds):
                now[0] += seconds

            with (
                patch.multiple(packet, PACKET=probe, OUT=root / "out", NATIVE_ROOT=root / "native"),
                patch.object(packet, "packet", return_value={"approved": True}),
            ):
                if bad_manifest:
                    with self.assertRaisesRegex(ValueError, "approved_manifest_changed"):
                        packet.run_once(
                            api,
                            run_id=RUN,
                            owner="123",
                            subdomain="synthetic",
                            access="b" * 64,
                            canary="SYNTHETIC-" + "c" * 32,
                            invoke_native=invoke,
                            stop_requested=lambda: False,
                            clock=lambda: now[0],
                            sleep=sleep,
                        )
                    self.assertEqual(api.calls, [])
                    return
                stop_calls = [0]

                def stopped():
                    stop_calls[0] += 1
                    return (
                        behavior == "publication-stop" and (root / "native/target.json").exists()
                    ) or (stop and stop_calls[0] >= 4)

                args: dict[str, Any] = dict(
                    run_id=RUN,
                    owner="123",
                    subdomain="synthetic",
                    access="b" * 64,
                    canary="SYNTHETIC-" + "c" * 32,
                    invoke_native=invoke,
                    stop_requested=stopped,
                    clock=lambda: now[0],
                    sleep=sleep,
                )
                result = packet.run_once(api, **args)
                self.assertTrue(result["cleanupConfirmed"])
                self.assertEqual(api.objects, {})
                expected_invocations = [] if behavior == "publication-stop" else [RUN]
                self.assertEqual(invokes, expected_invocations)
                self.assertEqual(result["nativeInvocations"], len(expected_invocations))
                self.assertEqual(result["nativeTerminal"], behavior in ("terminal", "failed"))
                self.assertEqual(result["actionFailed"], behavior in ("throw", "wrong-run"))
                if stop or behavior in ("throw", "wrong-run", "waiting", "publication-stop"):
                    self.assertTrue(result["stopPreserved"])
                    self.assertTrue((root / "native/stop.json").exists())
                journal = (root / "out" / RUN / "private/journal.json").read_text()
                self.assertNotIn("PRIVATE-NATIVE-DETAIL", journal)
                with self.assertRaises(FileExistsError):
                    packet.run_once(api, **args)
                self.assertEqual(invokes, expected_invocations)

    def test_full_terminal_and_failed_terminal(self):
        for behavior in ("terminal", "failed"):
            self.run_fixture(behavior)

    def test_sticky_stop_never_invokes_again_and_cleans_up(self):
        self.run_fixture("waiting", stop=True)

    def test_deadline_stops_and_cleans_up_without_native_terminal(self):
        self.run_fixture("waiting")

    def test_stop_arriving_at_target_publication_prevents_native_invocation(self):
        self.run_fixture("publication-stop")

    def test_native_failure_and_wrong_receipt_identity_cleanup(self):
        for behavior in ("throw", "wrong-run"):
            self.run_fixture(behavior)

    def test_manifest_mismatch_prevents_any_provider_or_native_call(self):
        self.run_fixture("terminal", bad_manifest=True)


class NativeRunTests(unittest.TestCase):
    def test_full_run_and_partial_failure_atomic_sanitized_publication(self):
        for behavior in ("success", "failure", "stop"):
            self.execute_run(behavior)

    def execute_run(self, behavior):
        fail_post = behavior == "failure"
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        module = lua.execute((NATIVE / "Post.lua").read_text())
        codec = lua.execute((RELEASE / "dkjson.lua").read_text())
        memory = lua.table()
        root = r"C:\Temp\FGA-group-post-v1"
        memory[ntpath.join(root, "target.json")] = json.dumps(
            {
                "schemaVersion": 1,
                "planVersion": packet.VERSION,
                "runId": RUN,
                "subdomain": "synthetic",
                "access": "b" * 64,
                "canary": "SYNTHETIC-" + "c" * 32,
                "expiresAtUnix": 1800001200,
            }
        )
        calls = []

        def post(*args):
            calls.append(args[0])
            if fail_post:
                raise RuntimeError("PRIVATE-NATIVE-DETAIL")
            if behavior == "stop":
                memory[ntpath.join(root, "stop.json")] = json.dumps(
                    {
                        "schemaVersion": 1,
                        "planVersion": packet.VERSION,
                        "runId": RUN,
                        "owner": "123",
                        "stop": True,
                    }
                )
            return "PRIVATE-RESPONSE-BYTES", lua.table_from({"status": 202})

        def exists(path):
            return "file" if memory[path] is not None else None

        def move(source, destination):
            memory[destination] = memory[source]
            memory[source] = None
            return True

        def delete(path):
            memory[path] = None
            return True

        context = lua.eval("{addCleanupHandler=function() end}")
        progress = lua.eval(
            "{setCancelable=function() end,isCanceled=function() return false end,"
            "done=function() end}"
        )
        captions = []
        progress.setCaption = lambda _, caption: captions.append(caption)
        sdk = {
            "LrPathUtils": lua.table_from({"child": ntpath.join, "parent": ntpath.dirname}),
            "LrFileUtils": lua.table_from({"exists": exists, "move": move, "delete": delete}),
            "LrTasks": lua.table_from({"pcall": lua.globals().pcall}),
            "LrFunctionContext": lua.table_from(
                {"postAsyncTaskWithContext": lambda _, fn: fn(context)}
            ),
            "LrHttp": lua.table_from(
                {"post": post, "get": lambda *_: ("{}", lua.table_from({"status": 200}))}
            ),
            "LrDate": lua.table_from({"currentTime": lambda: 1800000000 - 978307200}),
            "LrProgressScope": lua.eval("function(p) return function() return p end end")(progress),
        }
        lua.globals()["import"] = lambda name: sdk[name]
        lua.globals().require = lambda _: module
        lua.globals()._PLUGIN = lua.table_from({"path": str(NATIVE)})
        lua.globals().dofile = lambda path: (
            codec
            if path.endswith("dkjson.lua")
            else lua.execute((RELEASE / ntpath.basename(path)).read_text())
        )
        lua.globals().memory = memory
        lua.execute("""io={open=function(path,mode)
          if mode=='rb' then if not memory[path] then return nil end
            return {read=function(_,n) return memory[path]:sub(1,n) end,
              close=function() return true end}
          end
          return {write=function(_,v) memory[path]=v;return true end,
            close=function() return true end}
        end}""")
        lua.execute((NATIVE / "Run.lua").read_text())
        result = json.loads(memory[ntpath.join(root, "status.json")])
        self.assertEqual(result["runId"], RUN)
        self.assertFalse(result["productionQualified"])
        expected = "failed" if fail_post else "stopped" if behavior == "stop" else "characterized"
        self.assertEqual(result["outcome"], expected)
        self.assertEqual(len(captions), 1 if behavior in ("failure", "stop") else 23)
        self.assertEqual(
            captions[-1], "Case proof" if behavior in ("failure", "stop") else "Case cancel"
        )
        if behavior == "stop":
            self.assertEqual(len(calls), 1)
        if fail_post:
            self.assertEqual(result["reasonCode"], "fixture_failure")
        self.assertIsNone(memory[ntpath.join(root, "status.json.tmp")])
        self.assertIsNotNone(memory[ntpath.join(root, "target.used.json")])
        self.assertNotIn("PRIVATE", memory[ntpath.join(root, "status.json")])
        before = len(calls)
        lua.execute((NATIVE / "Run.lua").read_text())
        self.assertEqual(len(calls), before)


if __name__ == "__main__":
    unittest.main()
