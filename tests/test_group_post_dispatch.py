"""Offline faults against the real dispatch coordinator; no native API is loaded."""

from __future__ import annotations

import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import group_post_characterization as post
from scripts import group_post_dispatch as dispatch


class Provider:
    account = "a" * 32

    def __init__(self):
        self.objects: dict[str, Any] = {}
        self.calls: list[tuple[str, str]] = []

    def call(self, method, path, body: Any = None, timeout=20):
        self.calls.append((method, path))
        if method == "GET":
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


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.reset_fixture()

    def reset_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coordination = self.root / "coordination"
        self.native = self.root / "native"
        self.now = 1800000000.0
        self.inputs = {"runId": "a" * 24, "accountId": Provider.account, "subdomain": "synthetic"}
        self.requests = 0
        self.actual_inputs = 0
        self.handled = False
        self.request_seen = False
        self.mode = "done"
        self.api = Provider()
        for name, value in (("OUT", self.root / "out"), ("NATIVE_ROOT", self.native)):
            patcher = patch.object(post, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        original = post.bounded_json

        def bounded(path, maximum=65536):
            return (
                post.packet() if path == post.PACKET / "manifest.json" else original(path, maximum)
            )

        patcher = patch.object(post, "bounded_json", bounded)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def checkpoint(self, phase, identity, deadline):
        if self.mode == f"{phase}_bypass":
            return True
        challenge_path = self.coordination / f"challenge-{phase}.json"
        response_path = self.coordination / f"response-{phase}.json"
        if not challenge_path.exists():
            challenge = {
                **identity,
                "phase": phase,
                "nonce": ("1" if phase == "prewarm" else "2") * 32,
                "deadlineUnix": min(self.now + 10, deadline),
            }
            if self.mode == f"{phase}_no_challenge":
                return False
            if self.mode == f"{phase}_foreign":
                challenge["generation"] = "f" * 32
            if self.mode == f"{phase}_phase":
                challenge["phase"] = "other"
            if self.mode == f"{phase}_extra":
                challenge["command"] = "NEVER EXECUTE"
            if self.mode == f"{phase}_boolean":
                challenge["deadlineUnix"] = True
            if self.mode == f"{phase}_expired":
                challenge["deadlineUnix"] = self.now
            if self.mode == f"{phase}_extended":
                challenge["deadlineUnix"] = deadline + 1
            if self.mode == f"{phase}_partial":
                challenge_path.write_text('{"schemaVersion":', encoding="utf-8")
                return False
            self.write(challenge_path, challenge)
            if self.mode == f"{phase}_stale_nonce":
                self.write(response_path, {**challenge, "nonce": "f" * 32})
            if self.mode == f"{phase}_owner_lost":
                (self.coordination / "owner.json").unlink()
            if self.mode == f"{phase}_stop":
                self.write(self.coordination / "operator-stop.json", {"stop": True})
            return False
        if not response_path.exists():
            return False
        self.assertEqual(self.read(response_path), self.read(challenge_path))
        return True

    def sleep(self, seconds):
        self.now += seconds
        owner_path = self.coordination / "owner.json"
        if not owner_path.exists():
            return
        owner = self.read(owner_path)
        identity = {
            key: owner[key]
            for key in ("schemaVersion", "planVersion", "runId", "owner", "generation")
        }
        if not self.checkpoint("prewarm", identity, owner["deadlineUnix"]):
            return
        ready = self.coordination / "ready.json"
        if not ready.exists() and self.mode != "not_ready":
            value = {**identity, "state": "ready"}
            if self.mode == "ready_extra":
                value["command"] = "NEVER EXECUTE"
            self.write(ready, value)
        request_path = self.coordination / "invoke.json"
        if not request_path.exists() or self.handled:
            return
        if not self.request_seen:
            self.requests += 1
            self.request_seen = True
        request = self.read(request_path)
        if self.mode == "lost":
            self.handled = True
            return
        if self.mode == "owner_lost":
            owner_path.unlink()
            return
        if self.mode == "deadline":
            self.now += 1000
            return
        if self.mode == "stop":
            self.write(self.coordination / "operator-stop.json", {"stop": True})
            return
        attempted = dict(request)
        if not (self.coordination / "attempted.json").exists():
            self.write(self.coordination / "attempted.json", attempted)
        if self.mode == "attempt_extra":
            self.write(self.coordination / "attempted.json", {**attempted, "extra": True})
        if not self.checkpoint("dispatch", identity, request["deadlineUnix"]):
            return
        self.handled = True
        outcome, count = ("unknown", None) if self.mode == "unknown" else ("dispatched", 1)
        ack = {**identity, "outcome": outcome, "requestedInputCount": 1, "actualInputCount": count}
        if self.mode == "foreign":
            ack["generation"] = "b" * 32
        if self.mode == "ack_extra":
            ack["extra"] = True
        if self.mode == "false_dispatch":
            ack["actualInputCount"] = 0
        if self.mode == "ack_outcome":
            ack["outcome"] = "execute_another_command"
        if self.mode == "ack_boolean":
            ack["actualInputCount"] = True
        if self.mode == "missing_attempt":
            (self.coordination / "attempted.json").unlink()
        if self.mode == "unknown":
            self.write(self.coordination / "ack.json", ack)
            return
        self.actual_inputs += 1
        self.write(self.coordination / "ack.json", ack)
        self.write(
            self.native / "status.json",
            {
                "schemaVersion": 1,
                "planVersion": post.VERSION,
                "runId": self.inputs["runId"],
                "outcome": "characterized",
                "reasonCode": "measurements_require_external_receipt_review",
                "productionQualified": False,
                "remoteCleanupConfirmed": False,
                "postCalls": 23,
                "getCalls": 1,
            },
        )

    def execute(self):
        return dispatch.execute(
            self.api,
            self.inputs,
            coordination_root=self.coordination,
            clock=lambda: self.now,
            monotonic=lambda: self.now,
            sleep=self.sleep,
        )

    def test_actual_coordinator_cleans_and_persists_actual_input_separately(self):
        result = self.execute()
        self.assertEqual(result["outcome"], "characterized")
        self.assertEqual((self.requests, self.actual_inputs), (1, 1))
        self.assertEqual(result["requestedInputCount"], 1)
        self.assertEqual(result["actualInputCount"], 1)
        self.assertTrue(result["dispatchAttempted"])
        self.assertTrue(result["dispatchAcknowledged"])
        self.assertTrue(result["requestPublished"])
        self.assertFalse(self.api.objects)
        saved = self.read(post.OUT / self.inputs["runId"] / "action.json")
        journal = self.read(post.OUT / self.inputs["runId"] / "private/journal.json")
        for key in ("requestedInputCount", "actualInputCount", "dispatchAcknowledged"):
            self.assertEqual(saved[key], result[key])
            self.assertEqual(journal[key], result[key])
        self.assertEqual(self.read(self.coordination / "owner.json")["state"], "closed")

    def test_lost_ack_does_not_turn_callback_into_confirmed_input(self):
        self.mode = "lost"
        result = self.execute()
        self.assertTrue(result["requestPublished"])
        self.assertEqual(result["requestedInputCount"], 1)
        self.assertIsNone(result["actualInputCount"])
        self.assertFalse(result["dispatchAcknowledged"])
        self.assertFalse(result["dispatchAttempted"])
        self.assertEqual(self.actual_inputs, 0)
        self.assertNotEqual(result["outcome"], "characterized")
        self.assertTrue((self.native / "stop.json").exists())
        self.assertFalse(self.api.objects)

    def test_unknown_input_latches_stop_and_is_never_replayed(self):
        self.mode = "unknown"
        result = self.execute()
        self.assertTrue(result["dispatchAttempted"])
        self.assertIsNone(result["actualInputCount"])
        self.assertNotEqual(result["outcome"], "characterized")
        before = list(self.api.calls)
        with self.assertRaises((ValueError, FileExistsError)):
            self.execute()
        self.assertEqual(self.api.calls, before)
        self.assertEqual(self.requests, 1)

    def test_stop_owner_loss_deadline_after_request_cleanup_without_retry(self):
        for mode in ("owner_lost", "deadline", "stop"):
            with self.subTest(mode=mode):
                self.reset_fixture()
                self.mode = mode
                result = self.execute()
                self.assertNotEqual(result["outcome"], "characterized")
                self.assertEqual(self.requests, 1)
                self.assertEqual(self.actual_inputs, 0)
                self.assertTrue((self.native / "stop.json").exists())
                if mode != "deadline":
                    self.assertFalse(self.api.objects)

    def test_invalid_ack_or_attempt_cannot_qualify_even_with_terminal_status(self):
        for mode in (
            "foreign",
            "ack_extra",
            "false_dispatch",
            "attempt_extra",
            "missing_attempt",
            "ack_outcome",
            "ack_boolean",
        ):
            with self.subTest(mode=mode):
                self.reset_fixture()
                self.mode = mode
                result = self.execute()
                self.assertNotEqual(result["outcome"], "characterized")
                self.assertFalse(result["dispatchAcknowledged"])
                self.assertTrue((self.native / "stop.json").exists())
                self.assertFalse(self.api.objects)

    def test_operator_must_be_ready_before_first_provider_call(self):
        original = self.api.call

        def guarded(method, path, body=None, timeout=20):
            self.assertTrue((self.coordination / "ready.json").exists())
            self.assertEqual(
                self.read(self.coordination / "challenge-prewarm.json"),
                self.read(self.coordination / "response-prewarm.json"),
            )
            return original(method, path, body, timeout)

        self.api.call = guarded
        self.execute()

    def test_absent_or_open_schema_readiness_has_no_provider_effects(self):
        for mode in ("not_ready", "ready_extra"):
            with self.subTest(mode=mode):
                self.reset_fixture()
                self.mode = mode
                try:
                    result = self.execute()
                    self.assertNotEqual(result["outcome"], "characterized")
                except ValueError:
                    pass
                self.assertFalse(self.api.calls)
                self.assertEqual(self.requests, 0)

    def test_stop_or_deadline_between_target_and_request_prevents_input(self):
        for mode in ("stop", "deadline"):
            with self.subTest(mode=mode):
                self.reset_fixture()
                atomic = post.atomic_json

                def interrupt(path, value, atomic=atomic, mode=mode):
                    atomic(path, value)
                    if path == self.native / "target.json":
                        if mode == "stop":
                            self.write(self.coordination / "operator-stop.json", {"stop": True})
                        else:
                            self.now += 1000

                with patch.object(post, "atomic_json", interrupt):
                    result = self.execute()
                self.assertNotEqual(result["outcome"], "characterized")
                self.assertEqual(self.actual_inputs, 0)
                self.assertFalse(result["requestPublished"])
                self.assertFalse((self.coordination / "invoke.json").exists())

    def test_exclusive_claim_allows_only_one_concurrent_owner(self):
        def claim(_):
            native = dispatch.NativeFiles(
                coordination_root=self.coordination,
                run_id=self.inputs["runId"],
                clock=lambda: self.now,
                monotonic=lambda: self.now,
                sleep=self.sleep,
            )
            try:
                native.claim()
                return True
            except FileExistsError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(claim, range(8)))
        self.assertEqual(sum(results), 1)
        self.assertFalse(self.api.calls)

    def test_stop_and_deadline_before_prewarm_make_no_provider_call(self):
        for mode in ("stop", "deadline"):
            with self.subTest(mode=mode):
                self.reset_fixture()
                create = dispatch.create_json

                def interrupt(path, value, create=create, mode=mode):
                    create(path, value)
                    if path.name == "owner.json":
                        if mode == "stop":
                            self.write(self.coordination / "operator-stop.json", {"stop": True})
                        else:
                            self.now += 1000

                with patch.object(dispatch, "create_json", interrupt):
                    with self.assertRaises(ValueError):
                        self.execute()
                self.assertFalse(self.api.calls)
                self.assertEqual(self.requests, 0)

    def test_stale_ack_or_input_attempt_prevents_publication(self):
        for filename in ("ack.json", "attempted.json"):
            with self.subTest(filename=filename):
                self.reset_fixture()
                atomic = post.atomic_json

                def interrupt(path, value, atomic=atomic, filename=filename):
                    atomic(path, value)
                    if path.name == "target.json":
                        self.write(self.coordination / filename, {"stale": True})

                with patch.object(post, "atomic_json", interrupt):
                    result = self.execute()
                self.assertFalse(result["requestPublished"])
                self.assertEqual(result["actualInputCount"], 0)
                self.assertEqual(self.actual_inputs, 0)
                self.assertFalse(self.api.objects)

    def test_concurrent_exclusive_writers_cannot_overwrite_marker_or_ack(self):
        self.coordination.mkdir()
        for filename in ("attempted.json", "ack.json"):
            with self.subTest(filename=filename):
                path = self.coordination / filename

                def write_once(index, path=path):
                    try:
                        dispatch.create_json(path, {"writer": index})
                        return index
                    except FileExistsError:
                        return None

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    outcomes = list(pool.map(write_once, range(8)))
                winners = [value for value in outcomes if value is not None]
                self.assertEqual(len(winners), 1)
                self.assertEqual(self.read(path), {"writer": winners[0]})
                sealed = path.read_bytes()
                with self.assertRaises(FileExistsError):
                    dispatch.create_json(path, {"writer": "replacement"})
                self.assertEqual(path.read_bytes(), sealed)

    def test_owner_corruption_latches_even_if_original_owner_returns(self):
        for corruption in ({"extra": True}, {"schemaVersion": True}, {"generation": "foreign"}):
            with self.subTest(corruption=corruption):
                self.reset_fixture()
                native = dispatch.NativeFiles(
                    coordination_root=self.coordination,
                    run_id=self.inputs["runId"],
                    clock=lambda: self.now,
                    monotonic=lambda: self.now,
                    sleep=self.sleep,
                )
                native.claim()
                original = self.read(self.coordination / "owner.json")
                self.write(self.coordination / "owner.json", {**original, **corruption})
                self.assertTrue(native.stop_requested())
                self.write(self.coordination / "owner.json", original)
                self.assertTrue(native.stop_requested())
                self.assertFalse(self.api.calls)

    def test_original_expired_run_is_never_reopened(self):
        self.inputs["runId"] = "c01ba6d2c2754597aa311c9f"
        with self.assertRaises(ValueError):
            self.execute()
        self.assertFalse(self.coordination.exists())
        self.assertFalse(self.native.exists())
        self.assertFalse(self.api.calls)

    def test_visible_request_then_fsync_failure_preserves_unknown_input_and_grace(self):
        self.mode = "lost"
        publication_times = []
        cleanup_times = []
        create = dispatch.create_json
        call = self.api.call

        def failed_publication(path, value):
            create(path, value)
            if path == self.coordination / "invoke.json":
                publication_times.append(self.now)
                raise OSError("synthetic fsync failure after visible publication")

        def timed_provider(method, path, body=None, timeout=20):
            if method == "DELETE":
                cleanup_times.append(self.now)
                self.assertTrue((self.native / "stop.json").exists())
            return call(method, path, body, timeout)

        self.api.call = timed_provider
        with patch.object(dispatch, "create_json", failed_publication):
            result = self.execute()
        self.assertEqual(len(publication_times), 1)
        self.assertTrue(result["requestPublished"])
        self.assertEqual(result["requestedInputCount"], 1)
        self.assertIsNone(result["actualInputCount"])
        self.assertFalse(result["dispatchAcknowledged"])
        self.assertTrue(result["stopPreserved"])
        self.assertNotEqual(result["outcome"], "characterized")
        self.assertTrue(cleanup_times)
        self.assertGreaterEqual(min(cleanup_times) - publication_times[0], 20)
        self.assertEqual(self.requests, 1)
        self.assertFalse(self.api.objects)
        journal = self.read(post.OUT / self.inputs["runId"] / "private/journal.json")
        receipt = self.read(post.OUT / self.inputs["runId"] / "action.json")
        for value in (journal, receipt):
            self.assertTrue(value["requestPublished"])
            self.assertEqual(value["requestedInputCount"], 1)
            self.assertIsNone(value["actualInputCount"])
        before = list(self.api.calls)
        with self.assertRaises((ValueError, FileExistsError)):
            self.execute()
        self.assertEqual(self.api.calls, before)
        self.assertEqual(len(publication_times), 1)

    def test_bad_prewarm_challenges_never_reach_provider(self):
        for fault in (
            "no_challenge",
            "foreign",
            "phase",
            "extra",
            "boolean",
            "expired",
            "extended",
            "partial",
            "stale_nonce",
            "owner_lost",
            "stop",
        ):
            with self.subTest(fault=fault):
                self.reset_fixture()
                self.mode = "prewarm_" + fault
                with self.assertRaises(ValueError):
                    self.execute()
                self.assertFalse(self.api.calls)
                self.assertEqual(self.actual_inputs, 0)
                self.assertFalse((self.coordination / "invoke.json").exists())
                if fault != "stale_nonce":
                    self.assertFalse((self.coordination / "response-prewarm.json").exists())

    def test_bad_dispatch_challenges_preserve_unknown_input_and_stop(self):
        for fault in (
            "no_challenge",
            "foreign",
            "phase",
            "extra",
            "boolean",
            "expired",
            "extended",
            "partial",
            "stale_nonce",
            "owner_lost",
            "stop",
        ):
            with self.subTest(fault=fault):
                self.reset_fixture()
                self.mode = "dispatch_" + fault
                result = self.execute()
                self.assertTrue(result["requestPublished"])
                self.assertIsNone(result["actualInputCount"])
                self.assertFalse(result["dispatchAcknowledged"])
                self.assertNotEqual(result["outcome"], "characterized")
                self.assertEqual(self.actual_inputs, 0)
                self.assertTrue((self.native / "stop.json").exists())
                self.assertFalse(self.api.objects)
                if fault != "stale_nonce":
                    self.assertFalse((self.coordination / "response-dispatch.json").exists())

    def test_failed_response_cannot_fake_liveness_or_extend_request(self):
        for phase in ("prewarm", "dispatch"):
            with self.subTest(phase=phase):
                self.reset_fixture()
                create = dispatch.create_json

                def no_response(path, value, create=create, phase=phase):
                    if path.name == f"response-{phase}.json":
                        raise OSError("synthetic response writer unavailable")
                    create(path, value)

                with patch.object(dispatch, "create_json", no_response):
                    if phase == "prewarm":
                        with self.assertRaises(ValueError):
                            self.execute()
                        self.assertFalse(self.api.calls)
                    else:
                        result = self.execute()
                        self.assertIsNone(result["actualInputCount"])
                        self.assertTrue(result["stopPreserved"])
                        self.assertFalse(result["dispatchAcknowledged"])
                        request = self.read(self.coordination / "invoke.json")
                        self.assertLessEqual(self.now, request["deadlineUnix"] + 20)
                        self.assertFalse(self.api.objects)
                self.assertEqual(self.actual_inputs, 0)
                self.assertFalse((self.coordination / f"response-{phase}.json").exists())

    def test_ready_or_ack_cannot_bypass_owner_checkpoint(self):
        for phase in ("prewarm", "dispatch"):
            with self.subTest(phase=phase):
                self.reset_fixture()
                self.mode = phase + "_bypass"
                if phase == "prewarm":
                    with self.assertRaises(ValueError):
                        self.execute()
                    self.assertFalse(self.api.calls)
                else:
                    result = self.execute()
                    self.assertFalse(result["dispatchAcknowledged"])
                    self.assertIsNone(result["actualInputCount"])
                    self.assertNotEqual(result["outcome"], "characterized")
                    self.assertTrue((self.native / "stop.json").exists())
                    self.assertFalse(self.api.objects)
                self.assertFalse((self.coordination / f"response-{phase}.json").exists())

    def test_checkpoint_response_is_not_recreated_after_mutation_or_deletion(self):
        for fault in ("changed_nonce", "deleted_response"):
            with self.subTest(fault=fault):
                self.reset_fixture()
                native = dispatch.NativeFiles(
                    coordination_root=self.coordination,
                    run_id=self.inputs["runId"],
                    clock=lambda: self.now,
                    monotonic=lambda: self.now,
                    sleep=self.sleep,
                )
                native.claim()
                challenge = {
                    **native.identity,
                    "phase": "prewarm",
                    "nonce": "1" * 32,
                    "deadlineUnix": self.now + 10,
                }
                challenge_path = self.coordination / "challenge-prewarm.json"
                response_path = self.coordination / "response-prewarm.json"
                self.write(challenge_path, challenge)
                native.service_checkpoint("prewarm")
                sealed = response_path.read_bytes()
                if fault == "changed_nonce":
                    self.write(challenge_path, {**challenge, "nonce": "2" * 32})
                else:
                    response_path.unlink()
                with self.assertRaises(ValueError):
                    native.service_checkpoint("prewarm")
                self.assertTrue(native.stop_requested())
                if fault == "changed_nonce":
                    self.assertEqual(response_path.read_bytes(), sealed)
                else:
                    self.assertFalse(response_path.exists())
                self.assertFalse(self.api.calls)

    def test_failed_stop_writer_still_persists_uncertainty_after_grace(self):
        self.mode = "lost"
        create = dispatch.create_json
        atomic = post.atomic_json
        call = self.api.call
        cleanup_times = []
        stop_failures = []

        def failed_create(path, value):
            if path == self.native / "stop.json":
                stop_failures.append(self.now)
                raise OSError("synthetic persistent stop writer failure")
            create(path, value)

        def failed_atomic(path, value):
            if path == self.native / "stop.json":
                stop_failures.append(self.now)
                raise OSError("synthetic persistent stop writer failure")
            atomic(path, value)

        def timed_provider(method, path, body=None, timeout=20):
            if method == "DELETE":
                cleanup_times.append(self.now)
            return call(method, path, body, timeout)

        self.api.call = timed_provider
        with (
            patch.object(dispatch, "create_json", failed_create),
            patch.object(post, "atomic_json", failed_atomic),
        ):
            result = self.execute()
        self.assertTrue(stop_failures)
        self.assertTrue(cleanup_times)
        self.assertGreaterEqual(min(cleanup_times) - min(stop_failures), 20)
        self.assertEqual(result["outcome"], "failed")
        self.assertTrue(result["actionFailed"])
        self.assertTrue(result["stopPreserved"])
        self.assertEqual(result["stopReason"], "dispatch_stop_publication_failed")
        self.assertFalse(self.api.objects)
        self.assertFalse((self.native / "stop.json").exists())
        for path in (
            post.OUT / self.inputs["runId"] / "action.json",
            post.OUT / self.inputs["runId"] / "private/journal.json",
        ):
            saved = self.read(path)
            self.assertTrue(saved["requestPublished"])
            self.assertEqual(saved["requestedInputCount"], 1)
            self.assertIsNone(saved["actualInputCount"])
            self.assertEqual(saved["stopReason"], "dispatch_stop_publication_failed")

    def test_successful_attempt_is_not_replayed_or_overwritten(self):
        self.execute()
        saved = {path: path.read_bytes() for path in self.coordination.iterdir() if path.is_file()}
        calls = list(self.api.calls)
        with self.assertRaises((ValueError, FileExistsError)):
            self.execute()
        self.assertEqual(self.api.calls, calls)
        self.assertEqual(self.requests, 1)
        for path, content in saved.items():
            self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
