"""Offline once-only operator tests using synthetic provider identities only."""

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
from scripts import hosted_publisher_worker_deployment as deployment
from tests.test_hosted_publisher_finite_client import phase_body
from tests.test_hosted_publisher_worker_deployment import StatefulTransport


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
                f"fga-publisher-synthetic-{index}",
                f"fga-publisher-db-{index}",
                f"https://fga-publisher-synthetic-{index}.synthetic.workers.dev",
                f"{index + 1:x}" * 64,
                start,
                expiry,
            )
            for index, scenario in enumerate(plan_module.SCENARIOS)
        )
        self.plan = plan_module.OperatorPlan(
            2,
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
            "actions": [
                "fence_dispatch",
                "disable_access",
                "delete_owned_worker",
                "dispose_exact_synthetic_d1",
            ],
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
            pins={
                **self.plan.pins,
                "manifest": hashlib.sha256(manifest).hexdigest(),
                "worker": hashlib.sha256(b"synthetic offline module").hexdigest(),
            },
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

    def make(self, fault=None, stopped=False, transport=None):
        self.provider_transport = transport or StatefulTransport(fault)
        self.provider = deployment.BetaPublisherProvider(
            self.plan.account_id,
            "synthetic-private-provider-token",
            [c.worker_name for c in self.plan.cases],
            [c.d1_name for c in self.plan.cases],
            exclusive_owner=True,
            transport=self.provider_transport,
            monotonic=lambda: 100.0,
        )
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

    def test_open_journal_cannot_adopt_changed_plan_owner_and_matching_new_consent(self):
        self.plan = replace(self.plan, owner="Different Synthetic Owner")
        self.consent = {**self.consent, "owner": self.plan.owner, "plan_digest": self.plan.digest}
        self.authority = {**self.authority, "plan_digest": self.plan.digest}
        for action in ("run", "cleanup"):
            with self.subTest(action=action), self.assertRaises(operator.OperatorRefused):
                instance = self.make()
                if action == "run":
                    self.run_synthetic(instance)
                else:
                    instance.cleanup_only(self.authority)
            self.assertEqual(self.provider_transport.calls, [])
            self.assertIsNone(self.provider.before_request)
            self.assertIsNone(self.provider.after_request)
        self.assertEqual(self.requests, [])

    def test_swapped_open_journal_refuses_run_and_cleanup_before_requests(self):
        other = operator.DurableJournal(self.root / "different-plan.sqlite", "f" * 64)
        self.addCleanup(other.close)
        for action in ("run", "cleanup"):
            instance = self.make()
            instance.journal = other
            with self.subTest(action=action), self.assertRaises(operator.OperatorRefused):
                if action == "run":
                    self.run_synthetic(instance)
                else:
                    instance.cleanup_only(self.authority)
            self.assertEqual(self.provider_transport.calls, [])
        self.assertEqual(self.requests, [])
        self.assertEqual(other.snapshot(), {})

    def test_four_pairs_actual_provider_lifecycle_then_ordered_disposal(self):
        instance = self.make()
        result = self.run_synthetic(instance)
        self.assertEqual(result["status"], "phases_complete_cleanup_pending")
        self.assertEqual(len(self.requests), 28)
        self.assertEqual(len(self.provider_transport.databases), 4)
        self.assertEqual(len(self.provider_transport.workers), 4)
        self.assertTrue(
            all(not w["subdomain"]["enabled"] for w in self.provider_transport.workers.values())
        )
        instance._ledger.clear()
        cleanup = instance.cleanup_only(self.authority)
        self.assertEqual(cleanup["status"], "resources_disposed")
        self.assertEqual(cleanup["querySettlement"], "unproved")
        self.assertEqual(cleanup["qualification"], "not_established")
        self.assertEqual(self.provider_transport.databases, {})
        self.assertEqual(self.provider_transport.workers, {})
        self.assertEqual(cleanup["revocation"], "external_owner_required")
        calls = self.provider_transport.calls
        worker_deletes = [
            i for i, (m, p, _) in enumerate(calls) if m == "DELETE" and "/workers/workers/" in p
        ]
        database_deletes = [
            i for i, (m, p, _) in enumerate(calls) if m == "DELETE" and "/d1/database/" in p
        ]
        self.assertEqual(len(worker_deletes), 4)
        self.assertEqual(len(database_deletes), 4)
        for worker_delete, db_delete in zip(worker_deletes, database_deletes, strict=True):
            self.assertLess(worker_delete, db_delete)
            worker_path = calls[worker_delete][1]
            self.assertIn(("GET", worker_path, None), calls[worker_delete + 1 : db_delete])
        self.assertFalse(any("force" in p.lower() or "unsafe" in p.lower() for _, p, _ in calls))
        self.assertLessEqual(self.provider.calls, self.plan.budgets.provider_calls)
        with self.assertRaises(operator.OperatorRefused):
            instance.cleanup_only(self.authority)
        self.assertNotIn("d" * 64, json.dumps(self.journal.snapshot()))

    def test_omitted_d1_provider_time_runs_with_separate_local_create_evidence(self):
        stateful = StatefulTransport()

        def omit_time(*args):
            status, headers, raw = stateful(*args)
            if "/d1/database" in args[1] and args[0] in {"POST", "GET"}:
                document = json.loads(raw)
                if type(document.get("result")) is dict:
                    document["result"].pop("created_at", None)
                    raw = json.dumps(document).encode()
            return status, headers, raw

        instance = self.make(transport=omit_time)
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        event = self.journal.snapshot()["operation:happy:create"]
        self.assertEqual(event["state"], "complete")
        self.assertIsNone(event["receipt"]["result"]["created_at"])
        self.assertEqual(event["receipt"]["requestStartedAt"], "2026-10-17T12:01:00.000000Z")
        self.assertEqual(event["receipt"]["responseReceivedAt"], "2026-10-17T12:01:00.000000Z")
        self.assertEqual(len(self.requests), 28)
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "resources_disposed")

    def test_invalid_provider_time_retains_closed_identity_without_advancing(self):
        for timestamp in (None, "SYNTHETIC-PRIVATE-INVALID-TIME"):
            with self.subTest(timestamp=timestamp):
                stateful = StatefulTransport()

                def invalid_time(*args, stateful=stateful, timestamp=timestamp):
                    status, headers, raw = stateful(*args)
                    value = json.loads(raw)
                    value["result"]["created_at"] = timestamp
                    return status, headers, json.dumps(value).encode()

                # Each once-only case needs its own genuinely fresh journal.
                with operator.DurableJournal(
                    self.root / (str(timestamp is None) + ".sqlite"), self.plan.digest
                ) as journal:
                    original_journal, self.journal = self.journal, journal
                    try:
                        instance = self.make(transport=invalid_time)
                        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
                        event = self.journal.snapshot()["operation:happy:create"]
                        diagnostic = event["receipt"]["acknowledgedCreate"]
                        self.assertEqual(event["state"], "unknown")
                        self.assertEqual(diagnostic["providerTimeStatus"], "invalid")
                        self.assertEqual(diagnostic["name"], self.plan.cases[0].d1_name)
                        self.assertNotIn("created_at", diagnostic)
                        self.assertNotIn("SYNTHETIC-PRIVATE-INVALID-TIME", json.dumps(event))
                        self.assertEqual(len(stateful.calls), 1)
                        self.assertEqual(self.requests, [])
                    finally:
                        self.journal = original_journal

    def replace_case_windows(self, **changes):
        self.plan = replace(
            self.plan, cases=tuple(replace(case, **changes) for case in self.plan.cases)
        )
        self.consent["plan_digest"] = self.authority["plan_digest"] = self.plan.digest
        self.journal.close()
        self.journal = operator.DurableJournal(
            self.root / "changed-window.sqlite", self.plan.digest
        )
        self.addCleanup(self.journal.close)

    def test_future_case_window_refuses_create_before_any_provider_request(self):
        self.replace_case_windows(starts_at="2026-10-17T12:05:00Z")
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.provider_transport.calls, [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.journal.snapshot()["operation:happy:create"]["state"], "unknown")
        self.assertFalse(any(key.startswith("provider:") for key in self.journal.snapshot()))

    def test_durable_provider_reservation_crossing_case_expiry_never_dispatches(self):
        self.replace_case_windows(expires_at="2026-10-17T12:02:00Z")
        instance = self.make()
        reserve = self.journal.reserve

        def expires_during_reservation(key, payload):
            admitted = reserve(key, payload)
            if key == "provider:happy:create":
                self.wall = datetime(2026, 10, 17, 12, 2, tzinfo=UTC).timestamp()
            return admitted

        with patch.object(self.journal, "reserve", side_effect=expires_during_reservation):
            self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.provider_transport.calls, [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.journal.snapshot()["provider:happy:create"]["state"], "unknown")

    def test_rejected_local_validation_retains_the_captured_response_sample(self):
        instance = self.make()
        identity = {
            "uuid": "11111111-1111-4111-8111-111111111111",
            "name": self.plan.cases[0].d1_name,
            "created_at": "2026-10-17T11:00:00Z",
        }
        self.provider.last_database_create = {**identity, "providerTimeStatus": "valid"}
        ticks = iter(datetime(2026, 10, 17, 12, minute, tzinfo=UTC) for minute in (1, 2, 3))

        def create_database(name, *, key):
            return identity.copy()

        with patch.object(instance, "_now", side_effect=lambda: next(ticks)):
            with self.assertRaises(operator.OperatorRefused):
                instance._call(create_database, identity["name"], key="review:rejected-time")
        receipt = self.journal.snapshot()["operation:review:rejected-time"]["receipt"]
        self.assertEqual(receipt["requestStartedAt"], "2026-10-17T12:01:00.000000Z")
        self.assertEqual(receipt["responseReceivedAt"], "2026-10-17T12:02:00.000000Z")
        self.assertEqual(next(ticks).minute, 3)

    def test_provider_validation_exception_retains_response_time_before_durable_delay(self):
        stateful = StatefulTransport()

        def invalid_provider_time(*args):
            status, headers, raw = stateful(*args)
            self.wall = datetime(2026, 10, 17, 12, 2, tzinfo=UTC).timestamp()
            value = json.loads(raw)
            value["result"]["created_at"] = "SYNTHETIC-PRIVATE-INVALID-TIME"
            return status, headers, json.dumps(value).encode()

        instance = self.make(transport=invalid_provider_time)
        complete = self.journal.complete

        def delayed_provider_receipt(key, receipt):
            if key == "provider:happy:create":
                self.wall = datetime(2026, 10, 17, 12, 3, tzinfo=UTC).timestamp()
            complete(key, receipt)

        with patch.object(self.journal, "complete", side_effect=delayed_provider_receipt):
            self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        event = self.journal.snapshot()["operation:happy:create"]
        self.assertEqual(event["state"], "unknown")
        self.assertEqual(event["receipt"]["requestStartedAt"], "2026-10-17T12:01:00.000000Z")
        self.assertEqual(event["receipt"]["responseReceivedAt"], "2026-10-17T12:02:00.000000Z")
        self.assertEqual(event["receipt"]["acknowledgedCreate"]["providerTimeStatus"], "invalid")
        self.assertNotIn("SYNTHETIC-PRIVATE-INVALID-TIME", json.dumps(event))
        self.assertEqual(len(stateful.calls), 1)
        self.assertEqual(self.requests, [])

    def test_create_local_response_outside_window_never_claims_resource_or_dispatches(self):
        stateful = StatefulTransport()

        def expires_during_create(*args):
            response = stateful(*args)
            self.wall = datetime(2026, 10, 17, 12, 20, tzinfo=UTC).timestamp()
            return response

        instance = self.make(transport=expires_during_create)
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        event = self.journal.snapshot()["operation:happy:create"]
        self.assertEqual(event["state"], "unknown")
        self.assertNotIn("result", event["receipt"])
        self.assertEqual(len(stateful.calls), 1)
        self.assertEqual(self.requests, [])

    def test_lost_create_has_no_retry_or_phase_and_retains_unknown(self):
        instance = self.make(fault="lost_create")
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(len(self.provider_transport.calls), 1)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.journal.snapshot()["operation:happy:create"]["state"], "unknown")
        cleanup = instance.cleanup_only(self.authority)
        self.assertEqual(cleanup["status"], "pending")
        self.assertEqual(len(self.provider_transport.calls), 1)
        with self.assertRaises(operator.OperatorRefused):
            self.run_synthetic(instance)
        self.assertNotIn("SYNTHETIC-PRIVATE-RESPONSE", json.dumps(self.journal.snapshot()))

    def test_client_diagnostic_reaches_terminal_operator_unknown_receipt(self):
        instance = self.make()

        def refuse(request):
            self.requests.append(request)
            return finite_client.Response(503, {}, b"SYNTHETIC-PRIVATE-RESPONSE")

        instance.client_transport = refuse
        result = self.run_synthetic(instance)
        expected = finite_client.failure_diagnostic("response_status", 503)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["diagnostic"], expected)
        snapshot = self.journal.snapshot()
        self.assertEqual(snapshot["operator:run"]["receipt"]["diagnostic"], expected)
        self.assertEqual(snapshot["client:happy:seed"]["receipt"]["diagnostic"], expected)
        self.assertEqual(len(self.requests), 1)
        with self.assertRaises(operator.OperatorRefused):
            self.run_synthetic(instance)
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("SYNTHETIC-PRIVATE-RESPONSE", json.dumps(result))

    def test_operator_unknown_journal_failure_returns_unknown_without_replay(self):
        instance = self.make()
        instance.client_transport = lambda request: finite_client.Response(503, {}, b"private")
        with patch.object(self.journal, "unknown", side_effect=OSError("private")):
            result = self.run_synthetic(instance)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["diagnostic"], finite_client.failure_diagnostic("journal_unknown"))
        snapshot = self.journal.snapshot()
        self.assertEqual(snapshot["operator:run"]["state"], "intent")
        self.assertEqual(snapshot["client:happy:seed"]["state"], "intent")
        with self.assertRaises(operator.OperatorRefused):
            self.run_synthetic(instance)

    def test_operator_rejects_malicious_client_diagnostic_before_retention(self):
        instance = self.make()
        with patch.object(
            finite_client.FiniteClient,
            "run",
            return_value={
                "status": "unknown",
                "diagnostic": {"stage": "private", "code": "private"},
            },
        ):
            result = self.run_synthetic(instance)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["diagnostic"], finite_client.failure_diagnostic("operator"))
        self.assertEqual(result["cases"], [])
        self.assertEqual(
            self.journal.snapshot()["operator:run"]["receipt"]["diagnostic"], result["diagnostic"]
        )

    def test_private_binding_drift_prevents_enable_and_client_dispatch(self):
        instance = self.make(fault="private_drift")
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.requests, [])
        self.assertFalse(
            any(
                m == "PATCH" and b["subdomain"]["enabled"]
                for m, _, b in self.provider_transport.calls
            )
        )
        self.assertNotIn("SYNTHETIC-PRIVATE-RESPONSE", json.dumps(self.journal.snapshot()))

    def test_stop_fence_prevents_initial_provider_request(self):
        instance = self.make(stopped=True)
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.provider_transport.calls, [])
        self.assertEqual(self.requests, [])

    def test_unknown_sql_outcome_survives_accepted_fixture_disposal(self):
        instance = self.make()
        original = instance.client_transport

        def lose_last_phase(request):
            response = original(request)
            if request.headers["X-Probe-Scenario"] == "title_lost" and request.url.endswith(
                "/finish"
            ):
                return finite_client.Response(503, {}, b"synthetic private response")
            return response

        instance.client_transport = lose_last_phase
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        unknown_before = {
            key for key, event in self.journal.snapshot().items() if event["state"] == "unknown"
        }
        self.assertTrue(unknown_before)
        cleanup = instance.cleanup_only(self.authority)
        self.assertEqual(cleanup["status"], "disposed_with_unknown_outcomes")
        self.assertEqual(cleanup["querySettlement"], "unproved")
        self.assertTrue(
            all(self.journal.snapshot()[key]["state"] == "unknown" for key in unknown_before)
        )
        self.assertEqual(self.provider_transport.databases, {})
        self.assertEqual(len(self.requests), 28)
        self.assertFalse(any("observe_pending" in p for _, p, _ in self.provider_transport.calls))

    def test_unknown_worker_delete_retains_d1_and_is_not_replayed(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.provider_transport.fault = "lost_worker_delete"
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "pending")
        self.assertEqual(len(self.provider_transport.databases), 4)
        self.assertFalse(
            any(m == "DELETE" and "/d1/" in p for m, p, _ in self.provider_transport.calls)
        )
        old_transport = self.provider_transport
        old_transport.fault = None
        instance = self.make(transport=old_transport)
        instance.cleanup_only({**self.authority, "decision_id": "separate-observation"})
        self.assertEqual(
            sum(
                m == "DELETE" and "/workers/workers/" in p
                for m, p, _ in self.provider_transport.calls
            ),
            4,
        )
        self.assertEqual(
            self.journal.snapshot()["operation:dispose:happy:worker"]["state"], "unknown"
        )

    def test_unknown_d1_delete_does_not_become_verified_cleanup(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.provider_transport.fault = "lost_d1_delete"
        cleanup = instance.cleanup_only(self.authority)
        self.assertEqual(cleanup["status"], "pending")
        self.assertEqual(
            self.journal.snapshot()["operation:dispose:happy:database"]["state"], "unknown"
        )
        self.assertEqual(
            sum(m == "DELETE" and "/d1/" in p for m, p, _ in self.provider_transport.calls), 1
        )
        old_transport = self.provider_transport
        old_transport.fault = None
        instance = self.make(transport=old_transport)
        instance.cleanup_only({**self.authority, "decision_id": "separate-observation"})
        self.assertEqual(
            sum(
                m == "DELETE" and p == "/d1/database/00000001-1111-4111-8111-111111111111"
                for m, p, _ in self.provider_transport.calls
            ),
            1,
        )

    def test_unknown_disable_retains_all_resources(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.provider_transport.fault = "lost_disable"
        cleanup = instance.cleanup_only(self.authority)
        self.assertEqual(cleanup["status"], "pending")
        self.assertFalse(any(m == "DELETE" for m, _, _ in self.provider_transport.calls))
        self.assertEqual(len(self.provider_transport.databases), 4)

    def test_worker_delete_ack_without_absence_retains_d1(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.provider_transport.fault = "worker_absence_unverified"
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "pending")
        self.assertTrue(
            any(m == "DELETE" and "/workers/" in p for m, p, _ in self.provider_transport.calls)
        )
        self.assertFalse(
            any(m == "DELETE" and "/d1/" in p for m, p, _ in self.provider_transport.calls)
        )

    def test_d1_delete_ack_without_absence_is_pending(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        self.provider_transport.fault = "database_absence_unverified"
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "pending")
        self.assertEqual(len(self.provider_transport.databases), 4)
        self.assertEqual(
            self.journal.snapshot()["operation:dispose:happy:database"]["state"], "complete"
        )
        self.assertEqual(
            self.journal.snapshot()["operation:dispose:happy:worker"]["state"], "complete"
        )

    def test_grant_expiry_during_durable_provider_reserve_prevents_transport(self):
        instance = self.make()
        self.grant["expires_at"] = "2026-10-17T12:02:00Z"
        original = self.journal.reserve

        def reserve(key, payload):
            result = original(key, payload)
            if key.startswith("provider:"):
                self.wall += 60
            return result

        with patch.object(self.journal, "reserve", side_effect=reserve):
            self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(self.provider_transport.calls, [])
        self.assertEqual(self.requests, [])
        self.assertTrue(any(key.startswith("provider:") for key in self.journal.snapshot()))

    def test_grant_expiry_fences_every_provider_and_phase_request(self):
        instance = self.make()
        self.grant["expires_at"] = "2026-10-17T12:02:00Z"
        original = self.provider_transport.execute

        def advance(method, path, body):
            result = original(method, path, body)
            self.wall += 60
            return result

        self.provider_transport.execute = advance
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertEqual(len(self.provider_transport.calls), 1)
        self.assertEqual(self.requests, [])

    def test_absent_or_expired_grant_refuses_before_any_request(self):
        instance = self.make()
        for grant in ({}, {**self.grant, "expires_at": self.plan.starts_at}):
            instance.operator_grant = grant
            with self.subTest(grant=bool(grant)), self.assertRaises(ValueError):
                self.run_synthetic(instance)
        self.assertEqual(self.provider_transport.calls, [])
        self.assertEqual(self.requests, [])

    def test_cleanup_requires_original_synthetic_exclusive_consent(self):
        instance = self.make()
        instance.consent = {}
        with self.assertRaises(ValueError):
            instance.cleanup_only(self.authority)
        self.assertEqual(self.provider_transport.calls, [])

    def test_cleanup_needs_separate_exact_authority(self):
        instance = self.make()
        self.assertEqual(self.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        calls = len(self.provider_transport.calls)
        for change in (
            {"granted": False},
            {"plan_digest": "f" * 64},
            {"owner": "Wrong Owner"},
            {"actions": ["delete_exact_pairs"]},
        ):
            with self.subTest(change=tuple(change)), self.assertRaises(operator.OperatorRefused):
                instance.cleanup_only({**self.authority, **change})
        self.assertEqual(len(self.provider_transport.calls), calls)

    def test_migration_changed_after_fixture_validation_is_not_submitted(self):
        instance = self.make()
        next((self.root / "migrations").glob("*.sql")).write_bytes(b"SELECT 2;")
        self.assertEqual(self.run_synthetic(instance)["status"], "unknown")
        self.assertFalse(
            any(
                m == "POST" and p.endswith("/query") and b["sql"] == "SELECT 2;"
                for m, p, b in self.provider_transport.calls
            )
        )
        self.assertEqual(self.requests, [])

    def test_cleanup_before_run_permanently_fences_provisioning(self):
        instance = self.make()
        self.assertEqual(instance.cleanup_only(self.authority)["status"], "pending")
        with self.assertRaises(operator.OperatorRefused):
            self.run_synthetic(instance)
        self.assertEqual(self.provider_transport.calls, [])

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
        (self.root / next(iter(self.plan.source_files))).write_bytes(b"changed source")
        calls = len(self.provider_transport.calls)
        with self.assertRaises(ValueError):
            instance.cleanup_only(self.authority)
        self.assertEqual(len(self.provider_transport.calls), calls)


if __name__ == "__main__":
    unittest.main()
