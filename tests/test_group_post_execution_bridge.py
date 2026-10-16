"""Offline full owner/provider/file/operator composition; no native API loaded."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts import group_post_characterization as post
from scripts import group_post_execution_bridge as bridge


class Provider:
    account = "a" * 32

    def __init__(self, uncertain=False):
        self.objects = {}
        self.calls = []
        self.uncertain = uncertain

    def call(self, method, path, body: Any = None, timeout=20):
        self.calls.append((method, path))
        if method == "GET":
            if self.uncertain and path.endswith("/settings") and path in self.objects:
                return 503, {}
            return (200, {"result": self.objects[path]}) if path in self.objects else (404, {})
        if method == "DELETE":
            self.objects.pop(path + "/settings" if path.startswith("/workers") else path)
            return 200, {"success": True}
        if path == "/d1/database":
            value = {"name": body["name"], "uuid": "11111111-1111-4111-8111-111111111111"}
            self.objects[path + "/" + value["uuid"]] = value
            return 200, {"result": value}
        if path.endswith("/query"):
            return 200, {"success": True, "result": [{"success": True, "results": []}]}
        if method == "PUT":
            self.objects[path + "/settings"] = {"bindings": body["metadata"]["bindings"]}
            return 200, {"result": {"id": path.split("/")[-1]}}
        return 200, {"result": body}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in (("OUT", root / "out"), ("NATIVE_ROOT", root / "native")):
            patcher = patch.object(post, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Parent updates the manifest after integrating the new artifact.
        real_bounded = post.bounded_json

        def bounded(path, maximum=65536):
            return (
                post.packet()
                if path == post.PACKET / "manifest.json"
                else real_bounded(path, maximum)
            )

        patcher = patch.object(post, "bounded_json", bounded)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.time = 1800000000.0
        real_snapshot = bridge.snapshot

        def snapshot(path, maximum=8192):
            if path == post.PACKET / "manifest.json":
                return post.digest(path), post.packet()
            return real_snapshot(path, maximum)

        patcher = patch.object(bridge, "snapshot", snapshot)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.inputs = {
            "accountId": Provider.account,
            "runId": bridge.RUN_ID,
            "subdomain": "synthetic",
        }
        self.invocations = 0
        self.stop_at = None
        self.cleanup_at = None

    def operator(self, mode):
        handled = set()

        def sleep(seconds):
            self.time += seconds
            if (post.NATIVE_ROOT / "stop.json").exists() and self.stop_at is None:
                self.stop_at = self.time - seconds
            root = post.NATIVE_ROOT / "bridge"
            request = root / "invoke.json"
            if not request.exists() or (root / "ack.json").exists():
                return
            value = json.loads(request.read_text())
            if value["generation"] in handled:
                return
            handled.add(value["generation"])
            self.invocations += 1
            identity = {
                k: value[k]
                for k in ("schemaVersion", "planVersion", "runId", "owner", "generation")
            }
            if mode == "lost":
                return
            if mode == "owner_lost":
                (root / "owner.json").unlink()
                return
            if mode == "deadline":
                self.time += 1000
                return
            if mode == "escape":
                post.atomic_json(root / "operator-stop.json", {**identity, "reason": "escape"})
                return
            if mode == "foreign":
                identity["generation"] = "foreign"
            post.atomic_json(root / "ack.json", {**identity, "outcome": "dispatched"})
            if mode in ("done", "terminal_escape"):
                (post.NATIVE_ROOT / "target.json").replace(post.NATIVE_ROOT / "target.used.json")
                post.atomic_json(
                    post.NATIVE_ROOT / "status.json",
                    {
                        "schemaVersion": 1,
                        "planVersion": post.VERSION,
                        "runId": bridge.RUN_ID,
                        "outcome": "characterized",
                        "reasonCode": "measurements_require_external_receipt_review",
                        "productionQualified": False,
                        "remoteCleanupConfirmed": False,
                        "postCalls": 23,
                        "getCalls": 1,
                    },
                )
            if mode == "terminal_escape":
                post.atomic_json(root / "operator-stop.json", {**identity, "reason": "escape"})
            if mode == "foreign_terminal":
                post.atomic_json(post.NATIVE_ROOT / "status.json", {"runId": "0" * 24})

        return sleep

    def run_job(self, mode="done", uncertain=False):
        api = Provider(uncertain)
        call = api.call

        def timed_call(method, path, body=None, timeout=20):
            if method == "DELETE" and self.cleanup_at is None:
                self.cleanup_at = self.time
            return call(method, path, body, timeout)

        api.call = timed_call
        result = bridge.execute(
            api,
            self.inputs,
            clock=lambda: self.time,
            monotonic=lambda: self.time,
            sleep=self.operator(mode),
        )
        self.assertEqual(
            json.loads((post.NATIVE_ROOT / "bridge/owner.json").read_text())["state"], "closed"
        )
        return api, result

    def test_full_composition_consumes_target_and_cleans_exact_resources(self):
        api, result = self.run_job()
        self.assertEqual(result["outcome"], "characterized")
        self.assertEqual(self.invocations, 1)
        self.assertFalse(api.objects)
        self.assertTrue((post.NATIVE_ROOT / "target.used.json").exists())

    def test_lost_foreign_ack_escape_owner_loss_and_deadline_never_retry(self):
        for mode in ("lost", "foreign", "escape", "owner_lost", "deadline"):
            with self.subTest(mode=mode):
                # Each subcase is a fresh attempt sandbox, never a replay.
                with tempfile.TemporaryDirectory() as temporary:
                    with (
                        patch.object(post, "OUT", Path(temporary) / "out"),
                        patch.object(post, "NATIVE_ROOT", Path(temporary) / "native"),
                    ):
                        api, result = self.run_job(mode)
                        self.assertEqual(result["nativeInvocations"], 1)
                        self.assertTrue(result["stopPreserved"])
                        self.assertFalse(api.objects)
                        self.assertTrue((post.NATIVE_ROOT / "stop.json").exists())

    def test_cleanup_uncertainty_cannot_report_characterized(self):
        _, result = self.run_job(uncertain=True)
        self.assertFalse(result["cleanupConfirmed"])
        self.assertEqual(result["outcome"], "failed")

    def test_stop_before_preparation_and_after_publication(self):
        (post.NATIVE_ROOT).mkdir()
        post.atomic_json(post.NATIVE_ROOT / "stop.json", {"stop": True})
        with self.assertRaises(ValueError):
            self.run_job()
        self.assertEqual(self.invocations, 0)

    def test_post_publication_stop_prevents_request(self):
        real_atomic = post.atomic_json

        def atomic(path, value):
            real_atomic(path, value)
            if path.name == "target.json":
                real_atomic(path.parent / "bridge/operator-stop.json", {"reason": "escape"})

        with patch.object(post, "atomic_json", atomic):
            api, result = self.run_job()
        self.assertEqual(result["nativeInvocations"], 0)
        self.assertEqual(self.invocations, 0)
        self.assertFalse(api.objects)

    def test_stale_handshake_or_foreign_native_receipt_refuses(self):
        (post.NATIVE_ROOT / "bridge").mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.run_job()
        self.assertEqual(self.invocations, 0)

    def test_stale_target_refuses_before_provider_preparation(self):
        post.NATIVE_ROOT.mkdir()
        post.atomic_json(post.NATIVE_ROOT / "target.json", {"runId": "0" * 24})
        api = Provider()
        with self.assertRaises(ValueError):
            bridge.execute(api, self.inputs)
        self.assertFalse(api.calls)

    def test_foreign_terminal_after_dispatch_is_failure_and_cleanup(self):
        api, result = self.run_job("foreign_terminal")
        self.assertEqual(result["outcome"], "failed")
        self.assertFalse(result["nativeTerminal"])
        self.assertFalse(api.objects)
        self.assertEqual(self.invocations, 1)

    def test_stop_before_preparation_after_owner_claim_has_no_provider_calls(self):
        claim = bridge.NativeFiles.claim

        def stopped_claim(native):
            claim(native)
            post.atomic_json(native.paths["operator-stop.json"], {"reason": "escape"})

        with patch.object(bridge.NativeFiles, "claim", stopped_claim):
            api, result = self.run_job()
        self.assertFalse(api.calls)
        self.assertEqual(result["nativeInvocations"], 0)

    def test_bad_approval_digest_cannot_open_token(self):
        with (
            patch.object(bridge, "snapshot", return_value=("b" * 64, {})),
            patch.object(Path, "open", side_effect=AssertionError("token must not be opened")),
        ):
            with self.assertRaisesRegex(ValueError, "approval_digest_changed"):
                bridge.apply("a" * 64)

    def test_terminal_and_escape_race_preserves_stop_in_all_final_receipts(self):
        original_invoke = bridge.NativeFiles.invoke_native

        def invoke_then_stop(native, target, status):
            original_invoke(native, target, status)
            post.atomic_json(native.paths["operator-stop.json"], {"reason": "escape"})

        with patch.object(bridge.NativeFiles, "invoke_native", invoke_then_stop):
            _, result = self.run_job("done")
        self.assertEqual(result["outcome"], "stopped")
        self.assertTrue(result["stopPreserved"])
        directory = post.OUT / bridge.RUN_ID
        self.assertEqual(json.loads((directory / "action.json").read_text()), result)
        self.assertTrue(
            json.loads((directory / "private/journal.json").read_text())["stopPreserved"]
        )

    def test_lost_ack_publishes_stop_then_allows_twenty_second_grace_before_cleanup(self):
        _, result = self.run_job("lost")
        self.assertEqual(self.invocations, 1)
        self.assertIsNotNone(self.stop_at)
        self.assertIsNotNone(self.cleanup_at)
        self.assertEqual(cast(float, self.cleanup_at) - cast(float, self.stop_at), 20)
        self.assertTrue(result["stopPreserved"])

    def test_replaced_approval_and_config_cannot_substitute_after_snapshot(self):
        config = Path(self.temp.name) / "config"
        token = Path(self.temp.name) / "token"
        approval = Path(self.temp.name) / "approval"
        value = {
            **self.inputs,
            "tokenFile": str(token),
            "accountSource": str(bridge.ACCOUNT_SOURCE),
            "subdomainSource": str(bridge.SUBDOMAIN_SOURCE),
        }
        config.write_text(json.dumps(value))
        config_digest = post.digest(config)
        approval.write_text(
            json.dumps({"mode": "approved_execution", "configSha2_256": config_digest})
        )
        approved_digest = post.digest(approval)
        original_snapshot = bridge.snapshot
        reads = []

        def replace_after_snapshot(path, maximum=8192):
            reads.append(path)
            digest, parsed = original_snapshot(path, maximum)
            if path == approval:
                path.write_text('{"mode":"unapproved"}')
            elif path == config:
                path.write_text('{"accountId":"foreign"}')
            return digest, parsed

        with (
            patch.object(bridge, "CONFIG", config),
            patch.object(bridge, "TOKEN", token),
            patch.object(bridge, "APPROVAL", approval),
            patch.object(bridge, "description", return_value={"mode": "offline_preparation"}),
            patch.object(bridge, "snapshot", side_effect=replace_after_snapshot),
            patch.object(post, "Provider", return_value=Provider()),
            patch.object(bridge, "execute", return_value={"outcome": "offline"}) as execute,
        ):
            token.write_text("SYNTHETIC_APPROVED_TOKEN")
            self.assertEqual(bridge.apply(approved_digest), {"outcome": "offline"})
            self.assertEqual(execute.call_args.args[1], value)
        self.assertEqual(reads.count(config), 1)
        self.assertEqual(reads.count(approval), 1)

    def test_bad_config_snapshot_refuses_before_token_read(self):
        token = Path(self.temp.name) / "must-not-open-token"
        approval_value = {"mode": "approved_execution", "configSha2_256": "a" * 64}
        with (
            patch.object(bridge, "TOKEN", token),
            patch.object(bridge, "description", return_value={"mode": "offline_preparation"}),
            patch.object(
                bridge,
                "snapshot",
                side_effect=[("c" * 64, approval_value), ("b" * 64, {}), ("d" * 64, post.packet())],
            ),
            patch.object(Path, "open", side_effect=AssertionError("token read forbidden")),
        ):
            with self.assertRaisesRegex(ValueError, "approved_packet_changed"):
                bridge.apply("c" * 64)

    def test_invalid_private_token_is_refused_without_provider_or_secret_in_error(self):
        token = Path(self.temp.name) / "token"
        token.write_text("PRIVATE-UNRETAINED\n")
        config = Path(self.temp.name) / "config"
        config.write_text("{}")
        approval = Path(self.temp.name) / "approval"
        approval.write_text(
            json.dumps({"mode": "approved_execution", "configSha2_256": post.digest(config)})
        )
        with (
            patch.object(bridge, "TOKEN", token),
            patch.object(bridge, "CONFIG", config),
            patch.object(bridge, "APPROVAL", approval),
            patch.object(bridge, "description", return_value={"mode": "offline_preparation"}),
            patch.object(bridge, "load_inputs", return_value=self.inputs),
            patch.object(post, "Provider", side_effect=AssertionError("provider forbidden")),
        ):
            with self.assertRaisesRegex(ValueError, "^provider_token_invalid$"):
                bridge.apply(post.digest(approval))

    def test_default_cli_and_failure_never_open_token_or_log_exception(self):
        with (
            patch.object(bridge, "description", return_value={"mode": "offline_preparation"}),
            patch("sys.argv", ["bridge"]),
            patch.object(Path, "open", side_effect=AssertionError("TOKEN-PRIVATE")),
        ):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(bridge.main(), 0)
            self.assertNotIn("TOKEN-PRIVATE", output.getvalue())
        with (
            patch("sys.argv", ["bridge", "--apply", "--approved-sha2-256", "a" * 64]),
            patch.object(bridge, "apply", side_effect=ValueError("TOKEN-PRIVATE")),
        ):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(bridge.main(), 1)
            self.assertNotIn("TOKEN-PRIVATE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
