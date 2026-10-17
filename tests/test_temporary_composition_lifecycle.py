"""Adversarial closed-model tests; no provider, native host, credentials or network."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from scripts.temporary_composition_lifecycle import (
    OPERATIONS,
    LifecycleJournal,
    SyntheticProvider,
    build_plan,
    rehearse,
    validate_plan,
)

RUN = "a" * 32
START = 1_000
PROOF_FIELDS = (
    "deploymentAllowed",
    "providerRestorationVerified",
    "productionStateVerified",
    "changedSecretSemanticsVerified",
    "nativeQualified",
    "transportQualified",
)


class TemporaryCompositionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sequence = 0
        self.journals = []

    def tearDown(self):
        for journal in self.journals:
            journal.close()

    def run_model(self, faults=None, *, tick_ms=0, now_ms=None, stop_requested=False):
        self.sequence += 1
        plan = build_plan(RUN, START)
        path = Path(self.temp.name) / f"lifecycle-{self.sequence}.sqlite"
        journal = LifecycleJournal(path, plan)
        self.journals.append(journal)
        provider = SyntheticProvider(plan, faults, tick_ms=tick_ms)
        result = rehearse(plan, journal, provider, now_ms=now_ms, stop_requested=stop_requested)
        self.assertLessEqual(result["operationsAttempted"], plan["operationCap"])
        self.assertEqual(len(provider.calls), len(set(provider.calls)))
        for field in PROOF_FIELDS:
            self.assertIs(result[field], False)
        return plan, journal, provider, result

    def test_success_restores_actual_retained_state_and_deletes_only_after_readback(self):
        plan, journal, provider, result = self.run_model()
        self.assertEqual(result["cleanup"], "confirmed_offline")
        self.assertEqual(
            provider.snapshot(),
            {"snapshot": plan["retained"], "admissionOff": True, "receiver": None},
        )
        self.assertEqual(provider.calls, list(OPERATIONS))
        self.assertLess(
            provider.calls.index("read_disabled"), provider.calls.index("restore_retained")
        )
        self.assertLess(
            provider.calls.index("read_restored"), provider.calls.index("delete_receiver")
        )
        self.assertEqual(result["pendingOperations"], [])
        self.assertTrue(all(disposition == "accepted" for _, disposition in journal.records()))
        snapshot = provider.snapshot()
        snapshot["snapshot"]["activeVersion"] = "foreign"
        self.assertEqual(provider.snapshot()["snapshot"], plan["retained"])

    def test_unknown_effects_do_not_become_acknowledgments_or_replay_after_restart(self):
        for operation in (
            "create_receiver",
            "apply_temporary",
            "disable_temporary",
            "restore_retained",
            "delete_receiver",
        ):
            for fault in ("unknown", "exception", "malformed"):
                with self.subTest(operation=operation, fault=fault):
                    plan, journal, provider, result = self.run_model({operation: fault})
                    self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                    self.assertIn(operation, result["pendingOperations"])
                    self.assertEqual(provider.calls[-1], operation)
                    self.assertEqual(provider.calls.count(operation), 1)
                    if operation == "restore_retained":
                        self.assertEqual(provider.snapshot()["snapshot"], plan["retained"])
                        self.assertIsNotNone(provider.snapshot()["receiver"])
                    if operation == "delete_receiver":
                        self.assertIsNone(provider.snapshot()["receiver"])
                    records = journal.records()
                    reconciliations = [name for name, _ in records if name.startswith("reconcile_")]
                    self.assertEqual(len(reconciliations), plan["reconciliationReadCap"])
                    path = Path(self.temp.name) / f"lifecycle-{self.sequence}.sqlite"
                    journal.close()
                    self.journals.remove(journal)
                    reopened = LifecycleJournal(path, plan)
                    self.journals.append(reopened)
                    calls = provider.calls[:]
                    with self.assertRaisesRegex(ValueError, "already_attempted"):
                        rehearse(plan, reopened, provider)
                    self.assertEqual(provider.calls, calls)
                    self.assertEqual(reopened.records(), records)

    def test_refused_mutations_retain_known_outcomes_and_cleanup_boundaries(self):
        for operation in (
            "create_receiver",
            "apply_temporary",
            "disable_temporary",
            "restore_retained",
            "delete_receiver",
        ):
            with self.subTest(operation=operation):
                _, journal, provider, result = self.run_model({operation: "refused"})
                self.assertEqual(
                    result["cleanup"],
                    "confirmed_offline"
                    if operation == "apply_temporary"
                    else "cleanup_unconfirmed",
                )
                self.assertEqual(dict(journal.records())[operation], "refused")
                self.assertNotIn(operation, result["pendingOperations"])
                self.assertEqual(provider.calls.count(operation), 1)
                if operation in ("disable_temporary", "restore_retained"):
                    self.assertNotIn("delete_receiver", provider.calls)

    def test_independent_restored_state_drift_prevents_resource_deletion(self):
        for fault in (
            "identity_drift",
            "data_drift",
            "typed_data_drift",
            "schema_drift",
            "secret_drift",
            "gate_drift",
            "reference_drift",
            "version_drift",
            "weights_drift",
            "refused",
            "unknown",
            "malformed",
        ):
            with self.subTest(fault=fault):
                _, _, provider, result = self.run_model({"read_restored": fault})
                self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                self.assertNotIn("delete_receiver", provider.calls)
                self.assertIsNotNone(provider.snapshot()["receiver"])

    def test_independent_admission_readback_is_required_before_restoration(self):
        for fault in ("identity_drift", "data_drift", "refused", "unknown", "malformed"):
            with self.subTest(fault=fault):
                _, _, provider, result = self.run_model({"read_disabled": fault})
                self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                self.assertNotIn("restore_retained", provider.calls)
                self.assertNotIn("delete_receiver", provider.calls)

    def test_baseline_or_receiver_identity_drift_prevents_apply(self):
        for operation in ("read_baseline", "read_receiver_created"):
            for fault in ("identity_drift", "data_drift"):
                with self.subTest(operation=operation, fault=fault):
                    _, _, provider, result = self.run_model({operation: fault})
                    self.assertNotEqual(result["cleanup"], "confirmed_offline")
                    self.assertNotIn("apply_temporary", provider.calls)

    def test_preflight_stop_and_inner_expiry_leave_baseline_untouched(self):
        options_list: list[dict[str, Any]] = [{"stop_requested": True}, {"now_ms": START + 600_000}]
        for options in options_list:
            with self.subTest(options=options):
                plan, _, provider, result = self.run_model(**options)
                self.assertEqual(result["cleanup"], "not_applied")
                self.assertFalse(provider.calls)
                self.assertEqual(provider.snapshot()["snapshot"], plan["retained"])
                self.assertIsNone(provider.snapshot()["receiver"])

    def test_inner_expiry_after_baseline_is_reported_without_inventing_stop(self):
        plan, _, provider, result = self.run_model(tick_ms=600_000)
        self.assertEqual(provider.calls, ["read_baseline"])
        self.assertEqual(result["cleanup"], "not_applied")
        self.assertEqual(result["reason"], "work_expired_before_apply")
        self.assertIs(result["stopObserved"], False)
        self.assertFalse(provider.stop_requested)
        self.assertEqual(provider.snapshot()["snapshot"], plan["retained"])
        self.assertIsNone(provider.snapshot()["receiver"])

    def test_stop_after_apply_performs_bounded_exact_cleanup(self):
        plan, _, provider, result = self.run_model({"apply_temporary": "stop"})
        self.assertTrue(result["stopObserved"])
        self.assertEqual(result["cleanup"], "confirmed_offline")
        self.assertEqual(provider.snapshot()["snapshot"], plan["retained"])
        self.assertIsNone(provider.snapshot()["receiver"])

    def test_stop_and_inner_expiry_before_apply_do_not_publish(self):
        options_list: list[dict[str, Any]] = [
            {"faults": {"create_receiver": "stop"}},
            {"faults": {"read_receiver_created": "stop"}},
            {"tick_ms": 200_000},
        ]
        for options in options_list:
            with self.subTest(options=options):
                _, _, provider, result = self.run_model(**options)
                self.assertNotIn("apply_temporary", provider.calls)
                if "tick_ms" in options:
                    self.assertEqual(result["reason"], "outer_expired")
                else:
                    self.assertEqual(result["cleanup"], "confirmed_offline")

    def test_outer_expiry_during_cleanup_never_confirms_or_extends_window(self):
        plan, _, provider, result = self.run_model(tick_ms=120_000)
        self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
        self.assertEqual(result["reason"], "outer_expired")
        self.assertLessEqual(provider.elapsed_ms, plan["outerExpiresMs"] - START)
        self.assertIn("delete_receiver", provider.calls)
        self.assertNotIn("read_receiver_absent", provider.calls)

    def test_closed_plan_rejects_forged_restoration_authority_limits_and_types(self):
        for field, replacement in (
            ("restore", {"strategy": "percentage", "force": True, "versions": []}),
            ("operationCap", 100),
            ("reconciliationReadCap", 3),
            ("deploymentAllowed", True),
            ("workExpiresMs", START + 600_001),
            ("startMs", True),
            ("unknown", "accepted"),
        ):
            plan = build_plan(RUN, START)
            plan[field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(plan)
        for key in ("force", "versions"):
            plan = build_plan(RUN, START)
            if key == "force":
                plan["restore"][key] = 0
            else:
                plan["restore"][key][0]["percentage"] = 100.0
            with self.subTest(type_confusion=key), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_complete_plan_binding_and_existing_owner_marker_refuse_before_calls(self):
        plan, journal, provider, _ = self.run_model()
        path = Path(self.temp.name) / f"lifecycle-{self.sequence}.sqlite"
        with self.assertRaises(FileExistsError):
            LifecycleJournal(path, plan)
        self.assertTrue(journal.marker.exists())
        journal.close()
        self.journals.remove(journal)
        for run, start in (("b" * 32, START), (RUN, START + 1)):
            changed = build_plan(run, start)
            with (
                self.subTest(run=run, start=start),
                self.assertRaisesRegex(ValueError, "plan_mismatch"),
            ):
                LifecycleJournal(path, changed)
        reopened = LifecycleJournal(path, plan)
        self.journals.append(reopened)
        calls = provider.calls[:]
        with self.assertRaisesRegex(ValueError, "already_attempted"):
            rehearse(plan, reopened, provider)
        self.assertEqual(calls, provider.calls)

    def test_failed_temporary_observation_still_stops_known_temporary_admission(self):
        for fault in ("refused", "identity_drift", "data_drift"):
            with self.subTest(fault=fault):
                _, _, provider, result = self.run_model({"read_temporary": fault})
                self.assertIn("disable_temporary", provider.calls)
                self.assertTrue(provider.snapshot()["admissionOff"])
                if fault == "refused":
                    self.assertEqual(result["cleanup"], "confirmed_offline")
                else:
                    self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                    self.assertNotIn("delete_receiver", provider.calls)

    def test_every_declared_fault_has_finite_unique_dispatch_and_closed_proofs(self):
        for operation in OPERATIONS:
            for fault in (
                "refused",
                "unknown",
                "exception",
                "malformed",
                "identity_drift",
                "data_drift",
                "stop",
            ):
                with self.subTest(operation=operation, fault=fault):
                    plan, journal, provider, result = self.run_model({operation: fault})
                    self.assertLessEqual(len(journal.records()), plan["operationCap"])
                    if fault in ("unknown", "exception", "malformed"):
                        self.assertNotEqual(result["cleanup"], "confirmed_offline")
                        self.assertEqual(provider.calls[-1], operation)

    def test_preflight_stop_and_expiry_are_terminal_across_journal_reopen(self):
        options_list: list[dict[str, Any]] = [
            {"stop_requested": True},
            {"now_ms": START + 600_000},
            {"now_ms": START + 1_200_000},
        ]
        for options in options_list:
            with self.subTest(options=options):
                plan, journal, provider, result = self.run_model(**options)
                self.assertEqual(result["cleanup"], "not_applied")
                self.assertEqual(result["operationsAttempted"], 0)
                self.assertFalse(provider.calls)
                path = Path(self.temp.name) / f"lifecycle-{self.sequence}.sqlite"
                journal.close()
                self.journals.remove(journal)
                reopened = LifecycleJournal(path, plan)
                self.journals.append(reopened)
                fresh_provider = SyntheticProvider(plan)
                with self.assertRaisesRegex(ValueError, "already_attempted"):
                    rehearse(plan, reopened, fresh_provider, now_ms=START)
                self.assertFalse(fresh_provider.calls)
                self.assertEqual(fresh_provider.snapshot()["snapshot"], plan["retained"])
                self.assertIsNone(fresh_provider.snapshot()["receiver"])

    def test_old_owner_double_close_cannot_release_new_owner_marker(self):
        path = Path(self.temp.name) / "owner-lifetime.sqlite"
        plan = build_plan(RUN, START)
        old_owner = LifecycleJournal(path, plan)
        old_owner.close()
        owner = LifecycleJournal(path, plan)
        self.journals.append(owner)
        marker_content = owner.marker.read_bytes()
        old_owner.close()
        self.assertEqual(owner.marker.read_bytes(), marker_content)
        with self.assertRaises(FileExistsError):
            LifecycleJournal(path, plan)
        provider = SyntheticProvider(plan)
        result = rehearse(plan, owner, provider)
        self.assertEqual(result["cleanup"], "confirmed_offline")

    def test_close_preserves_a_replaced_marker_from_another_owner(self):
        path = Path(self.temp.name) / "replaced-owner.sqlite"
        plan = build_plan(RUN, START)
        owner = LifecycleJournal(path, plan)
        owner.marker.unlink()
        replacement = "synthetic-other-owner"
        owner.marker.write_text(replacement, encoding="utf-8")
        try:
            owner.close()
            owner.close()
            self.assertEqual(owner.marker.read_text(encoding="utf-8"), replacement)
            with self.assertRaises(FileExistsError):
                LifecycleJournal(path, plan)
        finally:
            owner.marker.unlink(missing_ok=True)

    def test_stop_receipt_reports_observed_stop_at_every_operation(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                _, _, provider, result = self.run_model({operation: "stop"})
                self.assertIn(operation, provider.calls)
                self.assertTrue(provider.stop_requested)
                self.assertIs(result["stopObserved"], True)

    def test_invalid_clock_stop_and_provider_inputs_refuse_without_effect(self):
        plan = build_plan(RUN, START)
        for clock in (True, START - 1, float("nan"), float("inf")):
            path = Path(self.temp.name) / f"invalid-{str(clock)}.sqlite"
            journal = LifecycleJournal(path, plan)
            try:
                provider = SyntheticProvider(plan)
                with (
                    self.subTest(clock=clock),
                    self.assertRaisesRegex(ValueError, "operation_time"),
                ):
                    rehearse(plan, journal, provider, now_ms=cast(Any, clock))
                self.assertFalse(provider.calls)
                self.assertFalse(journal.records())
            finally:
                journal.close()
        for faults in ({"foreign": "unknown"}, {"read_baseline": "retry"}):
            with self.assertRaisesRegex(ValueError, "synthetic_fault"):
                SyntheticProvider(plan, faults)
        for tick in (-1, True, 1_200_001):
            with self.assertRaisesRegex(ValueError, "synthetic_tick"):
                SyntheticProvider(plan, tick_ms=tick)
        changed: Any = copy.deepcopy(plan)
        changed["retained"]["weights"] = {"foreign": 100}
        with self.assertRaises(ValueError):
            SyntheticProvider(changed)


if __name__ == "__main__":
    unittest.main()
