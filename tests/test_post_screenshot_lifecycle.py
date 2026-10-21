"""Synthetic files, clock and management transport; no native/provider effects."""

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from scripts import post_screenshot_lifecycle as post
from scripts.hosted_publisher_provider import CloudflareProvider, ProviderError, ProviderUnknown
from tests.test_hosted_publisher_worker_deployment import ACCOUNT, TOKEN, StatefulTransport

RUN = "b" * 24
ACCESS = "c" * 64
CANARY = "SYNTHETIC-" + "d" * 32


class PostTransport(StatefulTransport):
    def execute(self, method, path, body):
        if method == "GET" and path in {
            f"/workers/scripts/fga-post-{role}-{RUN}/settings" for role in ("src", "recv")
        }:
            return None, 404
        return super().execute(method, path, body)


class Permit:
    remaining = 1800

    def authorize(self):
        if self.remaining <= 0:
            raise ProviderError("synthetic_expired")

    def remaining_seconds(self):
        return self.remaining

    def begin_cleanup(self):
        pass


class PostScreenshotLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000.0
        self.permit = Permit()
        self.transport = PostTransport()
        self.provider = self.make_provider()
        self.life = post.Lifecycle(
            self.provider, Path(self.temp.name), RUN, "123", clock=lambda: self.now
        )
        self.life.journal["nativeInvocations"] = 0

    def make_provider(self, **overrides):
        args = dict(
            management_profile=post.MANAGEMENT_PROFILE,
            permit=self.permit,
            management_address="1.1.1.1",
            exclusive_owner=True,
            transport=self.transport,
            monotonic=lambda: self.now,
        )
        args.update(overrides)
        return post.Provider(ACCOUNT, TOKEN, RUN, **args)

    def prepare(self):
        return self.life.prepare("synthetic", ACCESS, CANARY)

    def test_exact_two_workers_one_database_and_distinct_secret_overlay(self):
        target = self.prepare()
        self.assertEqual(target["runId"], RUN)
        self.assertEqual(len(self.transport.workers), 2)
        self.assertEqual(len(self.transport.databases), 1)
        for version in self.transport.versions.values():
            values = {b["name"]: b.get("text") for b in version["bindings"]}
            self.assertEqual(values["ACCESS"], ACCESS)
            self.assertEqual(values["CANARY"], CANARY)
            self.assertEqual(version["modules"][0]["name"], "worker.mjs")
            self.assertEqual(version["compatibility_flags"], [])
        self.assertFalse(any(method == "PUT" for method, _, _ in self.transport.calls))
        self.assertLess(self.provider.calls, 120)
        self.assertEqual(self.provider.limits.response_bytes, 65536)
        self.assertEqual(self.provider.limits.request_seconds, 20)

    def test_preparation_creates_durable_intent_before_each_effect(self):
        original = self.provider._transport

        def witnessed(method, path, data, headers, timeout, cap):
            journal = json.loads(self.life.path.read_text())
            self.assertEqual(journal["operations"][-1]["path"], path.split(ACCOUNT)[1])
            self.assertFalse(journal["operations"][-1]["terminal"])
            self.assertEqual(journal["calls"], len(self.transport.calls) + 1)
            self.assertEqual(timeout, 20)
            self.assertEqual(cap, 65536)
            return original(method, path, data, headers, timeout, cap)

        self.provider._transport = witnessed
        self.prepare()
        self.assertTrue(all(row["terminal"] for row in self.life.journal["operations"]))

    def test_complete_pre_native_cleanup_has_delete_and_id_absence_within_reserve(self):
        self.prepare()
        count_before_export = len(self.transport.calls)
        self.life.observe()
        result = self.life.cleanup()
        self.assertTrue(result["cleanupConfirmed"])
        self.assertFalse(self.transport.workers)
        self.assertFalse(self.transport.databases)
        self.assertEqual(len(self.transport.calls) - count_before_export, 10)
        for method, path, _ in self.transport.calls:
            if method == "DELETE" and "/workers/" in path:
                self.assertRegex(path, r"^/workers/workers/[a-f0-9]{32}$")
        count = len(self.transport.calls)
        self.life.cleanup()
        self.assertEqual(len(self.transport.calls), count)

    def test_lost_worker_creation_is_unknown_and_never_adopted_by_name(self):
        self.transport.fault = "lost_worker_create"
        with self.assertRaises(ProviderUnknown):
            self.prepare()
        self.assertFalse(self.life.journal["resources"][-1]["acknowledged"])
        result = self.life.cleanup()
        self.assertFalse(result["cleanupConfirmed"])
        creates = [row for row in self.transport.calls if row[:2] == ("POST", "/workers/workers")]
        self.assertEqual(len(creates), 1)
        with self.assertRaises(ProviderError):
            self.prepare()
        self.assertFalse(any(method == "DELETE" for method, _, _ in self.transport.calls))

    def test_unknown_owned_operation_retains_database(self):
        self.prepare()
        self.life.journal["operations"].append(
            {"key": "unknown", "terminal": False, "method": "POST", "path": "/synthetic"}
        )
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        self.assertTrue(self.transport.databases)

    def test_native_boolean_alone_is_not_terminal_evidence(self):
        self.prepare()
        self.life.journal.update(
            nativeInvocations=1, nativeTerminal=True, allAcknowledgedCallersTerminal=True
        )
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        self.assertTrue(self.transport.databases)

    def test_bound_native_status_and_consumed_target_support_disposal(self):
        target = self.prepare()
        status = Path(self.temp.name) / "status.json"
        used = Path(self.temp.name) / "target.used.json"
        status.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "planVersion": post.VERSION,
                    "runId": RUN,
                    "outcome": "characterized",
                    "reasonCode": "measurements_require_external_receipt_review",
                    "postCalls": 23,
                    "getCalls": 1,
                    "productionQualified": False,
                    "remoteCleanupConfirmed": False,
                    "responseReferencesCleared": True,
                }
            )
        )
        used.write_text(json.dumps(target))
        self.life.journal.update(
            nativeInvocations=1,
            nativeTerminal=True,
            targetPublished=True,
            nativePaths={"status": str(status), "used": str(used)},
        )
        self.assertTrue(self.life.cleanup()["cleanupConfirmed"])
        self.assertFalse(self.life.journal["callerTerminalEvidence"]["remoteSqlSettlementProven"])

    def test_no_second_database_delete_after_lost_ack(self):
        self.prepare()
        self.transport.fault = "lost_d1_delete"
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        self.life.cleanup()
        deletes = [row for row in self.transport.calls if row[0] == "DELETE" and "/d1/" in row[1]]
        self.assertEqual(len(deletes), 1)

    def test_database_retained_when_worker_absence_unverified(self):
        self.prepare()
        self.transport.fault = "worker_absence_unverified"
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        self.assertTrue(self.transport.databases)

    def test_first_effect_checks_remaining_window_after_source_preparation(self):
        self.permit.remaining = 1199
        with self.assertRaisesRegex(ProviderError, "first_effect_window"):
            self.prepare()
        self.assertEqual(self.transport.calls, [])

    def test_account_drift_prevents_dispatch(self):
        self.provider.account = "e" * 32
        with self.assertRaises(ProviderError):
            self.prepare()
        self.assertFalse(self.transport.calls)

    def test_worker_name_preflight_is_exact_and_precedes_every_create(self):
        self.prepare()
        self.assertEqual(
            [row[:2] for row in self.transport.calls[:2]],
            [
                ("GET", f"/workers/scripts/fga-post-src-{RUN}/settings"),
                ("GET", f"/workers/scripts/fga-post-recv-{RUN}/settings"),
            ],
        )
        original = self.transport.execute
        self.assertEqual(self.provider.selected_strategy, "post-screenshot-returned-id-v1")
        # Arbitrary names cannot become a discovery or adoption surface.
        with self.assertRaises(ProviderError):
            self.provider.preflight_worker_absence("foreign", key="foreign")
        self.transport.execute = original

    def test_delete_operations_preserve_nonblocking_shared_session_exclusion(self):
        self.prepare()
        acquired, release = threading.Event(), threading.Event()

        def owner():
            with self.provider._session_lock:
                acquired.set()
                release.wait(5)

        thread = threading.Thread(target=owner)
        thread.start()
        self.assertTrue(acquired.wait(5))
        before = len(self.transport.calls)
        try:
            for resource in self.life.journal["resources"]:
                operation = (
                    self.provider.delete_worker
                    if resource["kind"] == "worker"
                    else self.provider.delete_database
                )
                with self.assertRaisesRegex(ProviderError, "concurrent_operation_forbidden"):
                    operation(resource["identity"], key="concurrent:" + resource["kind"])
            self.assertEqual(len(self.transport.calls), before)
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())

    def test_existing_worker_name_prevents_all_creation(self):
        self.transport.execute = lambda method, path, body: ({"existing": True}, 200)
        with self.assertRaisesRegex(ProviderError, "absence_unconfirmed"):
            self.prepare()
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.calls[0][0], "GET")

    def test_slow_intent_save_cannot_dispatch_after_preparation_deadline(self):
        original = self.life.save
        delayed = False

        def slow_save():
            nonlocal delayed
            original()
            if self.life.journal["operations"] and not delayed:
                delayed = True
                self.now += 250

        self.life.save = slow_save
        with self.assertRaises(ProviderError):
            self.prepare()
        self.assertEqual(self.transport.calls, [])

    def test_worker_delete404_is_absence_without_disposal_acknowledgement(self):
        self.prepare()
        original = self.transport.execute

        def deletion404(method, path, body):
            result = original(method, path, body)
            return (None, 404) if method == "DELETE" and "/workers/workers/" in path else result

        self.transport.execute = deletion404
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        self.assertTrue(self.transport.databases)
        self.assertTrue(
            all(
                not row.get("delete", {}).get("deletionAcknowledged")
                for row in self.life.journal["resources"]
                if row["kind"] == "worker"
            )
        )

    def test_last_transport_guard_rechecks_after_other_local_delay(self):
        original = self.provider._transport

        def delayed(method, path, data, headers, timeout, cap):
            self.now += 250
            return original(method, path, data, headers, timeout, cap)

        self.provider._transport = delayed
        with self.assertRaises(ProviderUnknown):
            self.prepare()
        self.assertEqual(self.transport.calls, [])

    def test_ready_save_cannot_return_target_after_preparation_deadline(self):
        original = self.life.save

        def delayed():
            original()
            if self.life.journal["stage"] == "ready":
                self.now += 250

        self.life.save = delayed
        with self.assertRaisesRegex(ProviderError, "preparation_deadline"):
            self.prepare()
        self.assertIsNone(self.life._target)

    def test_database_delete404_never_admits_post_delete_get(self):
        self.prepare()
        original = self.transport.execute

        def deletion404(method, path, body):
            result = original(method, path, body)
            return (None, 404) if method == "DELETE" and "/d1/database/" in path else result

        self.transport.execute = deletion404
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        delete_index = next(
            i
            for i, row in enumerate(self.transport.calls)
            if row[0] == "DELETE" and "/d1/database/" in row[1]
        )
        self.assertEqual(self.transport.calls[delete_index + 1 :], [])

    def test_expired_cleanup_is_retained_without_new_effect(self):
        self.prepare()
        self.now += 1181
        before = len(self.transport.calls)
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])
        self.assertEqual(len(self.transport.calls), before)

    def test_non_cleanup_calls_cannot_consume_ten_call_reserve(self):
        self.life.journal["calls"] = 110
        with self.assertRaisesRegex(ProviderError, "cleanup_call_reserve"):
            self.prepare()
        self.assertFalse(self.transport.calls)

    def test_exact_module_readback_drift_closes_provider_without_enable(self):
        self.transport.fault = "module_drift"
        with self.assertRaises(ProviderUnknown):
            self.prepare()
        self.assertFalse(any(method == "PATCH" for method, _, _ in self.transport.calls))
        self.assertFalse(self.life.cleanup()["cleanupConfirmed"])

    def test_explicit_profile_and_sole_owner_required(self):
        with self.assertRaises(ProviderError):
            self.make_provider(management_profile="implicit")
        with self.assertRaises(ProviderError):
            self.make_provider(exclusive_owner=False)

    def test_original_publisher_defaults_reject_post_names(self):
        with self.assertRaisesRegex(ProviderError, "provider_name_invalid"):
            CloudflareProvider(
                ACCOUNT,
                TOKEN,
                self.provider.worker_names,
                self.provider.database_names,
                transport=self.transport,
            )
        self.assertEqual(ExecutionDefaults.module_name, "worker.js")

    def test_closed_projection_rejects_extra_binding_or_secret_drift(self):
        self.prepare()
        version = next(iter(self.transport.versions.values()))
        metadata = {
            k: copy.deepcopy(version[k])
            for k in ("main_module", "compatibility_date", "compatibility_flags", "bindings")
        }
        metadata.update(observability={"enabled": False}, logpush=False)
        metadata["bindings"][0]["id"] = metadata["bindings"][0].pop("database_id")
        metadata["bindings"].append({"name": "EXTRA", "type": "plain_text", "text": "x"})
        module = (post.PACKET / "worker.mjs").read_bytes()
        with self.assertRaises(ProviderError):
            self.provider._validate_projection(module, post._digest(module), metadata, ACCESS)
        metadata["bindings"].pop()
        next(b for b in metadata["bindings"] if b["name"] == "ACCESS")["text"] = "a" * 64
        with self.assertRaises(ProviderError):
            self.provider._validate_projection(module, post._digest(module), metadata, ACCESS)


ExecutionDefaults = post.ExecutionBetaPublisherProvider


if __name__ == "__main__":
    unittest.main()
