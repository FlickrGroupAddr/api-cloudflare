"""Accepted deployment-record seam over actual operator hooks; synthetic I/O only."""

import copy
from datetime import UTC, datetime
from unittest.mock import patch

from scripts import hosted_publisher_operator as operator
from scripts import hosted_publisher_operator_plan as plans
from scripts.hosted_publisher_provider import ProviderUnknown
from tests.test_hosted_publisher_operator import HostedOperatorIntegrationTests
from tests.test_hosted_publisher_worker_deployment import StatefulTransport


class RecordTransport(StatefulTransport):
    def __init__(self, post=None, record=None, after=None):
        super().__init__()
        self.post, self.record, self.after = post, record, after

    def execute(self, method, path, body):
        value, status = super().execute(method, path, body)
        if method == "POST" and path.endswith("/deployments"):
            return (self.post(copy.deepcopy(value)) if self.post else {"id": value["id"]}), status
        if method == "GET" and "/deployments/" in path:
            if self.after:
                self.after()
            return (self.record(copy.deepcopy(value)) if self.record else value), status
        return value, status


class DeploymentRecordProofTests(HostedOperatorIntegrationTests):
    setUp = HostedOperatorIntegrationTests.setUp
    make = HostedOperatorIntegrationTests.make
    run_synthetic = HostedOperatorIntegrationTests.run_synthetic

    def ready(self, transport=None):
        instance = self.make(transport=transport or RecordTransport())
        case = self.plan.cases[0]
        prefix = case.scenario
        database = instance._call(
            self.provider.create_database, case.d1_name, key=prefix + ":create"
        )
        worker = instance._call(
            self.provider.create_worker, case.worker_name, key=prefix + ":worker-create"
        )
        version = instance._call(
            self.provider.create_version,
            worker,
            b"synthetic offline module",
            self.plan.pins["worker"],
            plans.deployment_projection(self.plan, case, database["uuid"]),
            "d" * 64,
            key=prefix + ":version",
        )
        return instance, worker, version, prefix + ":deploy"

    def deploy(self, values):
        instance, worker, version, key = values
        return instance._call(self.provider.deploy_version, worker, version, key=key)

    def assert_unknown(self, values):
        with self.assertRaises(operator.OperatorRefused):
            self.deploy(values)
        instance, _, _, key = values
        self.assertEqual(self.journal.snapshot()["operation:" + key]["state"], "unknown")
        self.assertEqual(self.provider._deployments, {})
        self.assertTrue(self.provider._closed)
        calls = len(self.provider_transport.calls)
        with self.assertRaises((operator.OperatorRefused, ProviderUnknown)):
            self.deploy(values)
        self.assertEqual(calls, len(self.provider_transport.calls))
        return instance

    def test_record_proof_preserves_offset_and_four_observations_before_receipt(self):
        stamp = "2026-10-17T08:00:03.123456-04:00"
        transport = RecordTransport(record=lambda value: {**value, "created_on": stamp})
        values = self.ready(transport)
        instance, _, _, key = values
        original = transport.execute

        def advancing(method, path, body):
            self.wall += 1
            value = original(method, path, body)
            if method == "POST" and path.endswith("/deployments"):
                for deployed in transport.deployments.values():
                    deployed["created_on"] = stamp
            return value

        transport.execute = advancing
        receipt = self.deploy(values)
        proof = self.journal.snapshot()["proof:" + key]["receipt"]
        self.assertEqual(receipt["created_on"], stamp)
        self.assertEqual(proof["providerCreatedOn"], stamp)
        observations = [
            proof[name]
            for name in ("postStartedAt", "postResponseAt", "recordStartedAt", "recordResponseAt")
        ]
        self.assertEqual(observations, sorted(observations))
        self.assertLess(observations[0], observations[1])
        self.assertLess(observations[2], observations[3])
        self.assertEqual(proof["planDigest"], self.plan.digest)
        self.assertEqual(proof["acknowledgedId"], receipt["id"])
        self.assertEqual(
            self.journal.snapshot()["operation:" + key]["receipt"]["proofRef"], "proof:" + key
        )
        instance._call(
            self.provider.inspect_deployment, values[1], values[2], receipt, key="happy:active"
        )
        self.assertEqual(sum("/deployments/" in p for _, p, _ in transport.calls), 1)
        self.assertTrue(any("?page=1&per_page=1" in p for _, p, _ in transport.calls))

    def test_partial_or_contradictory_post_never_reads_record(self):
        for mutate in (
            lambda value: {"id": value["id"], "metadata": {}},
            lambda value: {**value, "strategy": "invalid"},
            lambda value: {"id": "00000000-0000-0000-0000-000000000000"},
            lambda value: {"id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"},
        ):
            with self.subTest(mutate=mutate):
                # Separate genuine journal/fixture for each consumed finite run.
                child = DeploymentRecordProofTests()
                child.setUp()
                try:
                    values = child.ready(RecordTransport(post=mutate))
                    child.assert_unknown(values)
                    self.assertFalse(
                        any("/deployments/" in p for _, p, _ in child.provider_transport.calls)
                    )
                finally:
                    child.doCleanups()

    def test_bad_record_never_becomes_receipt(self):
        for field, value in (
            ("id", "99999999-9999-4999-8999-999999999999"),
            ("created_on", "2026-10-17T12:20:00Z"),
            ("created_on", "2026-10-17T11:59:59Z"),
            ("created_on", "2026-10-17T12:01:00"),
            ("versions", []),
            ("strategy", "invalid"),
        ):
            child = DeploymentRecordProofTests()
            child.setUp()
            try:
                values = child.ready(
                    RecordTransport(
                        record=lambda result, field=field, value=value: {**result, field: value}
                    )
                )
                child.assert_unknown(values)
            finally:
                child.doCleanups()

    def test_get_expiry_and_clock_reversal_fail_closed(self):
        for target in (datetime(2026, 10, 17, 12, 20, tzinfo=UTC).timestamp(), self.wall - 30):
            child = DeploymentRecordProofTests()
            child.setUp()
            try:
                values = child.ready(
                    RecordTransport(
                        after=lambda child=child, target=target: setattr(child, "wall", target)
                    )
                )
                child.assert_unknown(values)
            finally:
                child.doCleanups()

    def test_provenance_persistence_failure_prevents_registration(self):
        values = self.ready()
        original = self.journal.complete

        def fail(key, receipt):
            if key.startswith("proof:"):
                raise OSError("synthetic persistence failure")
            return original(key, receipt)

        with patch.object(self.journal, "complete", side_effect=fail):
            self.assert_unknown(values)

    def test_stop_before_exact_read_admission_consumes_intent_without_get(self):
        transport = RecordTransport()
        values = self.ready(transport)
        original = transport.execute
        stopped = False

        def stop(method, path, body):
            nonlocal stopped
            value = original(method, path, body)
            if method == "POST" and path.endswith("/deployments"):
                stopped = True
            return value

        transport.execute = stop
        values[0].stop_check = lambda: stopped
        self.assert_unknown(values)
        self.assertFalse(any("/deployments/" in p for _, p, _ in transport.calls))

    def test_four_case_run_keeps_shared_ids_list_proof_and_cleanup_budget(self):
        transport = RecordTransport()
        instance = self.make(transport=transport)
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.assertEqual(len(self.provider._acknowledged_deployments), 4)
        self.assertEqual(len([k for k in self.journal.snapshot() if k.startswith("proof:")]), 4)
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "resources_disposed")
        self.assertEqual(len(transport.calls), 252)
        self.assertEqual(sum(method != "GET" for method, _, _ in transport.calls), 144)
        self.assertEqual(transport.databases, {})
        self.assertEqual(transport.workers, {})

    def test_reused_acknowledgement_cross_case_refuses_before_record_get(self):
        transport = RecordTransport()
        instance = self.make(transport=transport)
        original = transport.execute
        first_id = None

        def reuse(method, path, body):
            nonlocal first_id
            value, status = original(method, path, body)
            if method == "POST" and path.endswith("/deployments"):
                first_id = first_id or value["id"]
                value = {"id": first_id}
            return value, status

        transport.execute = reuse
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(sum("/deployments/" in path for _, path, _ in transport.calls), 1)
        self.assertEqual(len(self.provider._acknowledged_deployments), 1)

    def test_known_post_clock_reversal_refuses_without_record_get(self):
        transport = RecordTransport()
        values = self.ready(transport)
        original = transport.execute

        def reverse(method, path, body):
            result = original(method, path, body)
            if method == "POST" and path.endswith("/deployments"):
                self.wall -= 1
            return result

        transport.execute = reverse
        self.assert_unknown(values)
        self.assertFalse(any("/deployments/" in path for _, path, _ in transport.calls))

    def test_identity_drift_after_exact_record_prevents_receipt(self):
        transport = RecordTransport()
        values = self.ready(transport)
        transport.after = lambda: transport.workers[values[1]["id"]].update({"id": "f" * 32})
        self.assert_unknown(values)

    def test_record_admission_uses_shared_call_byte_and_grant_limits(self):
        for limit in ("calls", "bytes", "grant"):
            child = DeploymentRecordProofTests()
            child.setUp()
            try:
                transport = RecordTransport()
                values = child.ready(transport)
                instance = values[0]
                original = transport.execute

                def exhaust(
                    method,
                    path,
                    body,
                    limit=limit,
                    original=original,
                    instance=instance,
                    child=child,
                ):
                    value = original(method, path, body)
                    if method == "POST" and path.endswith("/deployments"):
                        if limit == "calls":
                            instance._calls = child.plan.budgets.provider_calls
                        elif limit == "bytes":
                            instance._response_bytes = operator.PROVIDER_RESPONSE_BYTES
                        else:
                            child.wall = datetime(2026, 10, 17, 12, 2, tzinfo=UTC).timestamp()
                    return value

                if limit == "grant":
                    child.grant["expires_at"] = "2026-10-17T12:02:00Z"
                transport.execute = exhaust
                child.assert_unknown(values)
                self.assertFalse(any("/deployments/" in path for _, path, _ in transport.calls))
            finally:
                child.doCleanups()

    def test_id_only_without_canonical_context_never_reads_record(self):
        values = self.ready()
        self.provider.deployment_record_proof = None
        self.assert_unknown(values)
        self.assertFalse(
            any("/deployments/" in path for _, path, _ in self.provider_transport.calls)
        )

    def test_expiry_during_proof_sync_prevents_receipt_registration(self):
        values = self.ready()
        original = self.journal.complete

        def expire(key, receipt):
            original(key, receipt)
            if key.startswith("proof:"):
                self.wall = datetime(2026, 10, 17, 12, 20, tzinfo=UTC).timestamp()

        with patch.object(self.journal, "complete", side_effect=expire):
            self.assert_unknown(values)
        self.assertEqual(self.journal.snapshot()["proof:" + values[3]]["state"], "complete")

    def test_final_operation_persistence_failure_discards_proven_receipt(self):
        values = self.ready()
        original = self.journal.complete

        def fail(key, receipt):
            if key == "operation:" + values[3]:
                raise OSError("synthetic operation persistence failure")
            original(key, receipt)

        with patch.object(self.journal, "complete", side_effect=fail):
            self.assert_unknown(values)

    def test_successful_final_operation_sync_crossing_live_boundary_never_publishes(self):
        for boundary in ("case-plan", "grant", "lifecycle", "stop", "reversal"):
            child = DeploymentRecordProofTests()
            child.setUp()
            try:
                values = child.ready()
                instance, _, _, key = values
                original = child.journal.complete
                if boundary == "grant":
                    child.grant["expires_at"] = "2026-10-17T12:02:00Z"

                def cross(
                    name,
                    receipt,
                    boundary=boundary,
                    child=child,
                    instance=instance,
                    original=original,
                    key=key,
                ):
                    original(name, receipt)
                    if name != "operation:" + key:
                        return
                    if boundary == "case-plan":
                        child.wall = datetime(2026, 10, 17, 12, 20, tzinfo=UTC).timestamp()
                    elif boundary == "grant":
                        child.wall = datetime(2026, 10, 17, 12, 2, tzinfo=UTC).timestamp()
                    elif boundary == "lifecycle":
                        instance.monotonic = lambda: (
                            instance._started + instance.plan.budgets.lifecycle_seconds
                        )
                    elif boundary == "stop":
                        instance.stop_check = lambda: True
                    else:
                        child.wall -= 1

                with patch.object(child.journal, "complete", side_effect=cross):
                    with self.assertRaises(operator.OperatorRefused):
                        child.deploy(values)
                snapshot = child.journal.snapshot()
                self.assertEqual(snapshot["operation:" + key]["state"], "complete")
                self.assertEqual(snapshot["publication:" + key]["state"], "unknown")
                self.assertEqual(child.provider._deployments, {})
                self.assertTrue(child.provider._closed)
                self.assertTrue(instance._stopped)
                self.assertNotIn(key, instance._published_record_operations)
                calls = len(child.provider_transport.calls)
                with self.assertRaises(operator.OperatorRefused):
                    child.deploy(values)
                self.assertEqual(calls, len(child.provider_transport.calls))
            finally:
                child.doCleanups()

    def test_missing_or_recovered_publication_gate_never_adopts_complete_binding(self):
        for mode in ("missing", "recovered"):
            child = DeploymentRecordProofTests()
            child.setUp()
            try:
                transport = RecordTransport()
                instance = child.make(transport=transport)
                self.assertEqual(
                    child.run_synthetic(instance)["status"], "phases_complete_cleanup_pending"
                )
                entry = instance._ledger[child.plan.cases[0].scenario]
                if mode == "recovered":
                    instance = child.make(transport=transport)
                else:
                    instance._published_record_operations.clear()
                calls = len(transport.calls)
                with self.assertRaises(operator.OperatorRefused):
                    instance._check_deployment(child.plan.cases[0], entry, "missing-publication")
                self.assertEqual(calls, len(transport.calls))
                cleanup = instance.cleanup_only(child.authority)
                self.assertEqual(len(transport.databases), 4)
                self.assertEqual(transport.workers, {})
                self.assertTrue(
                    all(
                        case["status"] == "worker_removed_binding_unverified"
                        for case in cleanup["cases"]
                    )
                )
                self.assertEqual(len(transport.calls) - calls, 24)
            finally:
                child.doCleanups()

    def test_failure_audit_snapshot_cannot_bypass_in_memory_unknown_latch(self):
        values = self.ready()
        instance, _, _, key = values
        original_complete = self.journal.complete
        original_snapshot = self.journal.snapshot
        fail_next_snapshot = False

        def complete(name, receipt):
            nonlocal fail_next_snapshot
            original_complete(name, receipt)
            if name == "operation:" + key:
                self.wall = datetime(2026, 10, 17, 12, 20, tzinfo=UTC).timestamp()
                fail_next_snapshot = True

        def snapshot():
            nonlocal fail_next_snapshot
            if fail_next_snapshot:
                fail_next_snapshot = False
                raise OSError("synthetic failure-audit storage failure")
            return original_snapshot()

        with (
            patch.object(self.journal, "complete", side_effect=complete),
            patch.object(self.journal, "snapshot", side_effect=snapshot),
        ):
            with self.assertRaises(operator.OperatorRefused):
                self.deploy(values)
        self.assertTrue(self.provider._closed)
        self.assertTrue(instance._stopped)
        self.assertEqual(self.provider._deployments, {})
        self.assertNotIn(key, instance._published_record_operations)
        self.assertEqual(self.journal.snapshot()["operation:" + key]["state"], "complete")
        self.assertNotIn("publication:" + key, self.journal.snapshot())

    def test_unknown_absent_or_malformed_proof_kind_never_qualifies_publication(self):
        transport = RecordTransport()
        instance = self.make(transport=transport)
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        case = self.plan.cases[0]
        key = case.scenario + ":deploy"
        entry = instance._ledger[case.scenario]
        original_snapshot = self.journal.snapshot
        for kind in (None, "", "unrecognized", {}, [], 1, True):
            snapshot = original_snapshot()
            receipt = snapshot["operation:" + key]["receipt"]
            if kind is None:
                receipt.pop("proofKind")
            else:
                receipt["proofKind"] = kind
            self.assertFalse(instance._deployment_published(key, snapshot["operation:" + key]))
            calls = len(transport.calls)
            with patch.object(self.journal, "snapshot", return_value=snapshot):
                with self.assertRaises(operator.OperatorRefused):
                    instance._check_deployment(case, entry, "malformed-publication")
            self.assertEqual(calls, len(transport.calls))

        def malformed():
            snapshot = original_snapshot()
            for case in self.plan.cases:
                snapshot["operation:" + case.scenario + ":deploy"]["receipt"]["proofKind"] = (
                    "unrecognized"
                )
            return snapshot

        with patch.object(self.journal, "snapshot", side_effect=malformed):
            instance.cleanup_only(self.authority)
        self.assertEqual(len(transport.databases), 4)
        self.assertEqual(transport.workers, {})


def load_tests(loader, standard_tests, pattern):
    # Reuse the integration fixture without rerunning its inherited test cases.
    from unittest import TestSuite

    return TestSuite(
        DeploymentRecordProofTests(name)
        for name in DeploymentRecordProofTests.__dict__
        if name.startswith("test_")
    )
