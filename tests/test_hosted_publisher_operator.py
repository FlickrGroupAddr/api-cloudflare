"""Offline once-only operator tests using synthetic provider identities only."""

import copy
import hashlib
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import hosted_publisher_finite_client as finite_client
from scripts import hosted_publisher_operator as operator
from scripts import hosted_publisher_operator_plan as plan_module
from tests.test_hosted_publisher_finite_client import phase_body


class DurableJournalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-operator-journal-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "run.json"
        self.digest = "a" * 64

    def open(self):
        return operator.DurableJournal(self.path, self.digest)

    def test_intent_survives_interruption_and_cannot_be_reserved_again(self):
        class Interrupted(BaseException):
            pass

        with self.assertRaises(Interrupted), self.open() as journal:
            self.assertTrue(journal.reserve("create:happy", {"scenario": "happy"}))
            raise Interrupted
        with self.open() as recovered:
            self.assertFalse(recovered.reserve("create:happy", {"scenario": "happy"}))
            self.assertIn("create:happy", json.dumps(recovered.snapshot()))

    def test_unknown_and_completed_operations_are_never_replayed(self):
        with self.open() as journal:
            for key in ("create:happy", "delete:happy"):
                self.assertTrue(journal.reserve(key, {"scenario": "happy"}))
            journal.unknown("create:happy", "lost_response")
            journal.complete("delete:happy", {"absent": True})
        with self.open() as recovered:
            for key in ("create:happy", "delete:happy"):
                self.assertFalse(recovered.reserve(key, {"scenario": "happy"}))

    def test_second_owner_is_refused_until_first_closes(self):
        with self.open():
            with self.assertRaises(operator.OperatorRefused):
                self.open()
        with self.open() as next_owner:
            self.assertTrue(next_owner.reserve("inspect:happy", {}))

    def test_concurrent_reservations_have_exactly_one_winner(self):
        results = []
        with self.open() as journal:
            barrier = threading.Barrier(8)

            def reserve():
                barrier.wait(timeout=5)
                results.append(journal.reserve("phase:happy:seed", {"phase": "seed"}))

            threads = [threading.Thread(target=reserve) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 8)
        self.assertEqual(sum(results), 1)

    def test_different_plan_cannot_adopt_existing_journal(self):
        with self.open() as journal:
            journal.reserve("create:happy", {})
        with self.assertRaises(operator.OperatorRefused):
            operator.DurableJournal(self.path, "b" * 64)

    def test_private_payloads_are_rejected_before_persistence(self):
        sentinel = "SYNTHETIC-SECRET-DO-NOT-PERSIST"
        with self.open() as journal:
            for payload in (
                {"token": sentinel},
                {"nested": {"authorization": sentinel}},
                {"items": [{"password": sentinel}]},
                {"body": sentinel},
            ):
                with self.subTest(payload=tuple(payload)):
                    with self.assertRaises(operator.OperatorRefused):
                        journal.reserve("create:happy", payload)
            self.assertNotIn(sentinel, json.dumps(journal.snapshot()))
        self.assertNotIn(sentinel.encode(), self.path.read_bytes())


class SyntheticProvider:
    """Execute finite provider-method protocol with per-request journal hooks."""

    before_request = None
    after_request = None

    def __init__(self, plan, fault=None, quiescent=True):
        self.plan, self.fault, self.quiescent = plan, fault, quiescent
        self.account = plan.account_id
        self.worker_names = {c.worker_name for c in plan.cases}
        self.database_names = {c.d1_name for c in plan.cases}
        self.workers, self.databases, self.enabled = {}, {}, {}
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_") or name == "unsupported_operations":
            raise AttributeError(name)

        def invoke(*args, key):
            mutation = name in {
                "create_database",
                "migrate",
                "upload_worker",
                "set_endpoint",
                "delete_worker",
                "delete_database",
            }
            assert self.before_request is not None
            is_worker = "worker" in name or "endpoint" in name or name == "inspect_module"
            path = "/workers/scripts" if is_worker else "/d1/database"
            self.before_request(
                key,
                mutation,
                {"method": "POST" if mutation else "GET", "path": path, "requestBytes": 0},
            )
            self.calls.append((name, args))
            if self.fault == "lost_create" and name == "create_database":
                raise TimeoutError("SYNTHETIC-PRIVATE-RESPONSE")
            result = self.execute(name, args)
            assert self.after_request is not None
            self.after_request(key, {"status": 200, "responseBytes": 2})
            return result

        invoke.__name__ = name
        return invoke

    def execute(self, name, args):
        target = args[0]
        if name == "inspect_worker":
            projection = copy.deepcopy(self.workers.get(target))
            if projection:
                projection.pop("main_module", None)
            if self.fault == "overlay_drift" and projection:
                projection["bindings"][0]["id"] = "99999999-9999-4999-8999-999999999999"
            if self.fault == "private_drift" and projection:
                projection["bindings"].append(
                    {
                        "name": "UNEXPECTED",
                        "type": "plain_text",
                        "text": "SYNTHETIC-PRIVATE-RESPONSE",
                    }
                )
            return projection
        if name == "create_database":
            number = len(self.databases) + 1
            result = {
                "uuid": f"{number:08}-1111-4111-8111-111111111111",
                "name": target,
                "created_at": self.plan.starts_at,
            }
            self.databases[result["uuid"]] = result
            return result
        if name == "inspect_database":
            return self.databases.get(target["uuid"])
        if name == "verify_empty_database":
            return True
        if name == "migrate":
            return {"statements": 1}
        if name == "upload_worker":
            self.workers[target] = copy.deepcopy(args[3])
            return {
                "id": target,
                "etag": "synthetic-version",
                "moduleSha2_256": self.plan.pins["worker"],
            }
        if name == "inspect_module":
            return {"moduleSha2_256": self.plan.pins["worker"], "etag": "synthetic-version"}
        if name == "set_endpoint":
            self.enabled[target] = args[1]
            return {"enabled": args[1], "previews_enabled": False}
        if name == "inspect_endpoint":
            return {"enabled": self.enabled.get(target, False), "previews_enabled": False}
        if name == "observe_pending":
            return {"quiescent": self.quiescent, "database_uuid": target["uuid"]}
        if name == "delete_worker":
            if self.fault == "delete_failure":
                raise TimeoutError("SYNTHETIC-PRIVATE-RESPONSE")
            del self.workers[target]
            return None
        if name == "delete_database":
            del self.databases[target["uuid"]]
            return None
        raise AssertionError(name)


class HostedOperatorIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-operator-integration-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        start, expiry, cleanup = (
            "2026-10-17T12:00:00Z",
            "2026-10-17T12:20:00Z",
            "2026-10-17T13:00:00Z",
        )
        cases = tuple(
            plan_module.CasePlan(
                scenario,
                f"synthetic-{index}",
                f"synthetic_db_{index}",
                f"https://synthetic-{index}.fixture.workers.dev",
                f"{index + 1:x}" * 64,
                start,
                expiry,
            )
            for index, scenario in enumerate(plan_module.SCENARIOS)
        )
        self.plan = plan_module.OperatorPlan(
            1,
            "a" * 32,
            "Synthetic Owner",
            "Synthetic Cleanup",
            "Synthetic Revoker",
            start,
            expiry,
            cleanup,
            cases,
            plan_module.Budgets(**plan_module.BUDGET_CEILINGS),
            dict(plan_module.CANDIDATE_PINS),
            dict.fromkeys(plan_module.REQUIRED_OPERATOR_FILES, "b" * 64),
        )
        self.consent = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": self.plan.digest,
            "owner": self.plan.owner,
            "actions": list(plan_module.OWNER_ACTIONS),
            "decision_id": "synthetic-only",
        }
        self.authority = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": self.plan.digest,
            "owner": self.plan.cleanup_owner,
            "decision_id": "synthetic-cleanup",
            "expires_at": cleanup,
            "actions": ["disable_access", "observe_pending", "delete_exact_pairs"],
        }
        files = []
        for index in range(1, 27):
            name = f"migrations/{index:04}_synthetic.sql"
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"SELECT 1;")
            files.append(
                {
                    "path": name,
                    "sha2_256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": len(path.read_bytes()),
                }
            )
        manifest = json.dumps({"files": files}).encode()
        (self.root / "manifest.json").write_bytes(manifest)
        current_files = {}
        for name in plan_module.REQUIRED_OPERATOR_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                (Path(__file__).resolve().parents[1] / name).read_bytes()
                if name in plan_module.CURRENT_CONFIG_PINS
                else b"synthetic reviewed operator source"
            )
            path.write_bytes(content)
            current_files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        # This synthetic fixture replaces only the manifest pin; no retained private artifact
        # is read. Real immutable artifact rehashing is covered by the separate plan tests.
        self.plan = replace(
            self.plan,
            pins={**self.plan.pins, "manifest": hashlib.sha256(manifest).hexdigest()},
            source_files=current_files,
        )
        self.consent["plan_digest"] = self.authority["plan_digest"] = self.plan.digest
        self.pins_patch = patch.object(plan_module, "CANDIDATE_PINS", dict(self.plan.pins))
        self.pins_patch.start()
        self.addCleanup(self.pins_patch.stop)
        self.grant = {
            "grant_id": "synthetic-grant",
            "account_id": self.plan.account_id,
            "permissions": ["D1:Edit", "Workers Scripts:Edit"],
            "issued_at": start,
            "expires_at": cleanup,
            "revocation_owner": self.plan.revocation_owner,
            "resource_scope": "exact-account-only",
            "metadata_verified": True,
        }
        self.bundle = self.root / "worker.js"
        self.bundle.write_bytes(b"synthetic offline module")
        self.journal = operator.DurableJournal(self.root / "run.sqlite", self.plan.digest)
        self.addCleanup(self.journal.close)
        self.wall = datetime(2026, 10, 17, 12, 1, tzinfo=UTC).timestamp()
        self.requests = []

    def transport(self, request):
        self.requests.append(request)
        body = phase_body(request.url.rsplit("/", 1)[-1], request.headers["X-Probe-Scenario"])
        return finite_client.Response(
            200,
            {"content-type": "application/json", "cache-control": "no-store"},
            json.dumps(body).encode(),
        )

    def make(self, fault=None, quiescent=True, stopped=False):
        self.provider = SyntheticProvider(self.plan, fault, quiescent)
        self.private = plan_module.PrivateInputs(dict.fromkeys(plan_module.SCENARIOS, "d" * 64))
        return operator.HostedPublisherOperator(
            self.plan,
            self.consent,
            self.provider,
            self.transport,
            self.journal,
            self.private,
            self.root,
            self.bundle,
            self.root,
            operator_grant=self.grant,
            wall_clock=lambda: self.wall,
            monotonic=lambda: 100.0,
            stop_check=lambda: stopped,
        )

    def run_synthetic(self, instance):
        # Retained private artifact bytes are replaced by explicit synthetic fixture bytes.
        # Current source, plan/consent/overlay/client/provider/journal checks remain actual.
        with patch.object(plan_module, "validate_artifact"):
            return instance.run()

    def test_four_distinct_pairs_all_phases_then_exact_cleanup(self):
        instance = self.make()
        result = self.run_synthetic(instance)
        self.assertEqual(result["status"], "phases_complete_cleanup_pending")
        self.assertEqual(len(self.requests), 28)
        self.assertEqual(len(self.provider.databases), 4)
        self.assertEqual(len(self.provider.workers), 4)
        self.assertTrue(all(not state for state in self.provider.enabled.values()))
        # Recovery reconstructs exact identities from durable receipts, including when
        # a replacement owner has no in-memory ledger from provisioning.
        instance._ledger.clear()
        cleanup = instance.cleanup_only(self.authority)
        self.assertEqual(cleanup["status"], "complete")
        self.assertEqual(self.provider.databases, {})
        self.assertEqual(self.provider.workers, {})
        self.assertEqual(cleanup["revocation"], "external_owner_required")
        self.assertNotIn("d" * 64, json.dumps({"run": result, "journal": self.journal.snapshot()}))
        with self.assertRaises(operator.OperatorRefused):
            instance.cleanup_only(self.authority)

    def test_lost_create_has_no_retry_or_phase_and_retains_unknown(self):
        instance = self.make(fault="lost_create")
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(sum(name == "create_database" for name, _ in self.provider.calls), 1)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.journal.snapshot()["operation:happy:create"]["state"], "unknown")
        with self.assertRaises(operator.OperatorRefused):
            self.run_synthetic(instance)
        self.assertNotIn("SYNTHETIC-PRIVATE-RESPONSE", json.dumps(self.journal.snapshot()))

    def test_overlay_drift_prevents_enable_and_client_dispatch(self):
        instance = self.make(fault="overlay_drift")
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.requests, [])
        self.assertFalse(
            any(name == "set_endpoint" and args[1] for name, args in self.provider.calls)
        )

    def test_stop_fence_prevents_initial_provider_request(self):
        instance = self.make(stopped=True)
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.requests, [])

    def test_cleanup_pending_observation_never_deletes(self):
        instance = self.make(quiescent=False)
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        result = instance.cleanup_only(self.authority)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(len(self.provider.databases), 4)
        self.assertFalse(any(name.startswith("delete_") for name, _ in self.provider.calls))

    def test_cleanup_failure_is_pending_with_exact_resources_retained(self):
        instance = self.make(fault="delete_failure")
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        result = instance.cleanup_only(self.authority)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(len(self.provider.databases), 4)
        self.assertEqual(len(self.provider.workers), 4)

    def test_absent_or_expired_grant_refuses_before_any_request(self):
        instance = self.make()
        for grant in ({}, {**self.grant, "expires_at": self.plan.starts_at}):
            instance.operator_grant = grant
            with self.subTest(grant=bool(grant)), self.assertRaises(ValueError):
                self.run_synthetic(instance)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.requests, [])

    def test_cleanup_needs_separate_exact_authority(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        calls = len(self.provider.calls)
        for change in (
            {"granted": False},
            {"plan_digest": "f" * 64},
            {"owner": "Wrong Owner"},
            {"actions": ["delete_exact_pairs"]},
        ):
            with self.subTest(change=tuple(change)), self.assertRaises(operator.OperatorRefused):
                instance.cleanup_only({**self.authority, **change})
        self.assertEqual(len(self.provider.calls), calls)

    def test_migration_changed_after_fixture_validation_is_not_submitted(self):
        instance = self.make()
        migration = next((self.root / "migrations").glob("*.sql"))
        migration.write_bytes(b"SELECT 2;")
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertFalse(any(name == "migrate" for name, _ in self.provider.calls))
        self.assertEqual(self.requests, [])

    def test_private_text_in_drifted_settings_is_never_persisted(self):
        instance = self.make(fault="private_drift")
        result = self.run_synthetic(instance)
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(any(name == "upload_worker" for name, _ in self.provider.calls))
        self.assertEqual(
            self.journal.snapshot()["operation:happy:deployed:settings"]["state"], "complete"
        )
        self.assertNotIn("SYNTHETIC-PRIVATE-RESPONSE", json.dumps(self.journal.snapshot()))
        self.assertNotIn(b"SYNTHETIC-PRIVATE-RESPONSE", (self.root / "run.sqlite").read_bytes())
        self.assertEqual(self.requests, [])

    def test_cleanup_before_run_permanently_fences_provisioning(self):
        instance = self.make()
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "pending")
        with self.assertRaises(operator.OperatorRefused):
            self.run_synthetic(instance)
        self.assertEqual(self.provider.calls, [])

    def test_plan_phase_seconds_limits_every_client_request(self):
        self.plan = replace(self.plan, budgets=replace(self.plan.budgets, phase_seconds=2))
        self.consent["plan_digest"] = self.authority["plan_digest"] = self.plan.digest
        self.journal.close()
        self.journal = operator.DurableJournal(self.root / "phase-limit.sqlite", self.plan.digest)
        self.addCleanup(self.journal.close)
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.assertEqual(len(self.requests), 28)
        self.assertTrue(all(request.timeout <= 2 for request in self.requests))

    def test_current_input_drift_blocks_cleanup_before_provider_request(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        path = self.root / next(iter(self.plan.source_files))
        path.write_bytes(b"changed synthetic reviewed operator")
        calls = len(self.provider.calls)
        with self.assertRaises(ValueError):
            instance.cleanup_only(self.authority)
        self.assertEqual(len(self.provider.calls), calls)


if __name__ == "__main__":
    unittest.main()
