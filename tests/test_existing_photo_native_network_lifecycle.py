"""Fake control-plane tests only; no credentials or network."""

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import existing_photo_native_network_lifecycle as lifecycle

DB = "11111111-1111-4111-8111-111111111111"
GATE = "a" * 64
CANARY = "SYNTHETIC-" + "b" * 32


class Clock:
    def __init__(self):
        self.value = 1792166400
        self.sleeps = []

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class API:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.workers = set()
        self.database = None
        self.uploads = {}
        self.cleanup_clock: Clock | None = None

    def call(self, method, path, body: Any = None, **_kwargs):
        if self.cleanup_clock is not None and method in {"GET", "DELETE"}:
            self.cleanup_clock.value += 30
        self.calls.append((method, path))
        if method == "GET" and path.endswith("/settings"):
            name = path.split("/")[-2]
            return (200, {"success": True, "result": {}}) if name in self.workers else (404, {})
        if method == "POST" and path == "/d1/database":
            if self.failure == "create":
                raise TimeoutError("PRIVATE")
            self.database = body["name"]
            return 200, {"success": True, "result": {"uuid": DB, "name": self.database}}
        if method == "POST" and path.endswith("/query"):
            if "batch" in body:
                if self.failure == "seed":
                    raise ValueError("PRIVATE")
                return 200, {"success": True, "result": [{"success": True}] * 3}
            if self.failure == "hold":
                raise TimeoutError("PRIVATE")
            rows = [
                {"role": "receiver", "requests": 3, "receiver_requests": 1},
                {"role": "source", "requests": 9, "receiver_requests": 0},
            ]
            if self.failure == "no-final":
                rows[0]["requests"] = 1
                rows[0]["receiver_requests"] = 0
            return 200, {"success": True, "result": [{"success": True, "results": rows}]}
        if method == "GET" and path == "/workers/subdomain":
            return 200, {"success": True, "result": {"subdomain": "synthetic"}}
        if method == "PUT":
            name = path.split("/")[-1]
            self.uploads[name] = body
            if self.failure == "upload" and "recv" in name:
                raise TimeoutError("PRIVATE")
            self.workers.add(name)
            return 200, {"success": True, "result": {"id": name}}
        if method == "POST" and path.endswith("/subdomain"):
            return 200, {"success": True, "result": {"enabled": True, "previews_enabled": False}}
        if method == "DELETE" and path.startswith("/workers/"):
            self.workers.remove(path.split("/")[-1])
            return 200, {"success": True}
        if path == "/d1/database/" + DB:
            if method == "DELETE":
                self.database = None
                return 200, {"success": True}
            return (
                (200, {"success": True, "result": {"name": self.database}})
                if self.database
                else (404, {})
            )
        raise AssertionError("unexpected fake call")


class LifecycleTests(unittest.TestCase):
    def setup_run(self, failure=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        out, api, clock = Path(directory.name), API(failure), Clock()
        with contextlib.redirect_stdout(io.StringIO()):
            code = lifecycle.prepare(
                out,
                api,
                "a" * 32,
                "123",
                GATE,
                CANARY,
                build=lambda *_args: b"synthetic artifact",
                clock=clock,
            )
        return out, api, clock, code

    def test_ready_is_only_nonsecret_handoff_and_final_report_gets_grace_then_cleanup(self):
        out, api, clock, code = self.setup_run()
        self.assertEqual(code, 0)
        ready = json.loads((out / "ready.json").read_text())
        self.assertEqual(
            set(ready),
            {"schemaVersion", "planVersion", "runId", "workersDevSubdomain", "expiresAtUnix"},
        )
        self.assertEqual(
            lifecycle.hold_cleanup(
                out, api, "a" * 32, "123", published=True, clock=clock, sleep=clock.sleep
            ),
            0,
        )
        self.assertEqual(clock.sleeps, [60])
        receipt = (out / "cleanup.json").read_text()
        self.assertTrue(json.loads(receipt)["cleanupConfirmed"])
        self.assertEqual(json.loads(receipt)["stopReason"], "final_receiver_report_observed")
        value = json.loads(receipt)
        self.assertRegex(value["dryRunConfigSha2_256"], r"^[a-f0-9]{64}$")
        for worker in value["workers"]:
            metadata = json.loads(
                api.uploads[worker["name"]].split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0]
            )
            secrets_found = 0
            for binding in metadata["bindings"]:
                if binding["type"] == "secret_text":
                    self.assertIn(binding["text"], (GATE, CANARY))
                    binding["text"] = "[SECRET_ELIDED]"
                    secrets_found += 1
            self.assertEqual(secrets_found, 2)
            self.assertEqual(
                worker["uploadMetadataSecretElidedSha2_256"],
                hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest(),
            )
        for private in (GATE, CANARY, DB, "accountId", "PRIVATE"):
            self.assertNotIn(private, receipt)
        self.assertFalse(api.workers)
        self.assertIsNone(api.database)

    def test_prepare_failure_cleans_only_acknowledged_resources_no_mutation_retry(self):
        for failure in ("create", "seed", "upload"):
            with self.subTest(failure=failure):
                out, api, _, code = self.setup_run(failure)
                self.assertEqual(code, 1)
                receipt = json.loads((out / "cleanup.json").read_text())
                self.assertEqual(receipt["cleanupConfirmed"], failure == "seed")
                self.assertFalse((out / "ready.json").exists())
                self.assertFalse(api.workers)
                self.assertEqual(
                    sum(method == "POST" and path == "/d1/database" for method, path in api.calls),
                    1,
                )

    def test_ready_upload_failure_skips_wait_and_cleans(self):
        out, api, clock, _ = self.setup_run()
        self.assertEqual(
            lifecycle.hold_cleanup(
                out, api, "a" * 32, "123", published=False, clock=clock, sleep=clock.sleep
            ),
            0,
        )
        self.assertEqual(clock.sleeps, [])
        self.assertFalse(api.workers)

    def test_expiry_cleans_and_grace_cannot_extend_expiry(self):
        out, api, clock, _ = self.setup_run()
        clock.value += 1190
        lifecycle.hold_cleanup(
            out, api, "a" * 32, "123", published=True, clock=clock, sleep=clock.sleep
        )
        self.assertEqual(clock.sleeps, [10])
        self.assertEqual(clock.value, 1792167600)
        self.assertFalse(api.workers)

    def test_counter_failure_still_cleans_and_marks_failure(self):
        out, api, clock, _ = self.setup_run()
        api.failure = "hold"
        self.assertEqual(
            lifecycle.hold_cleanup(
                out, api, "a" * 32, "123", published=True, clock=clock, sleep=clock.sleep
            ),
            1,
        )
        self.assertTrue(json.loads((out / "cleanup.json").read_text())["cleanupConfirmed"])

    def test_no_final_report_waits_until_expiry_then_all_cleanup_calls_fit_25_minutes(self):
        out, api, clock, _ = self.setup_run()
        api.failure = "no-final"
        api.cleanup_clock = clock
        start = clock()
        self.assertEqual(
            lifecycle.hold_cleanup(
                out, api, "a" * 32, "123", published=True, clock=clock, sleep=clock.sleep
            ),
            0,
        )
        self.assertEqual(sum(clock.sleeps), 1200)
        self.assertEqual(clock() - start, 1200 + 9 * 30)
        self.assertLess(clock() - start, 25 * 60)
        self.assertFalse(api.workers)
        self.assertIsNone(api.database)
        receipt = json.loads((out / "cleanup.json").read_text())
        self.assertEqual(receipt["stopReason"], "expiry")
        self.assertTrue(receipt["cleanupConfirmed"])

    def test_other_job_journal_is_rejected_and_prepare_is_not_repeated(self):
        out, api, clock, _ = self.setup_run()
        before = len(api.calls)
        with self.assertRaises(ValueError):
            lifecycle.hold_cleanup(out, api, "a" * 32, "different", published=True, clock=clock)
        self.assertEqual(len(api.calls), before)
        with self.assertRaises(ValueError):
            lifecycle.prepare(out, api, "a" * 32, "123", GATE, CANARY)
        lifecycle.hold_cleanup(out, api, "a" * 32, "123", published=False, clock=clock)


if __name__ == "__main__":
    unittest.main()
