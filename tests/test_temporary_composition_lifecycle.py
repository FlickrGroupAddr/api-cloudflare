"""Adversarial closed-model tests; no provider, native host, credentials or network."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts.temporary_composition_delta import build_delta
from scripts.temporary_composition_lifecycle import (
    COMPOSITION_OPERATIONS,
    OPERATIONS,
    LifecycleJournal,
    SyntheticCompositionProvider,
    SyntheticProvider,
    build_composition_plan,
    build_plan,
    rehearse,
    rehearse_composition,
    validate_plan,
)
from tests.test_temporary_composition_delta import composition_inputs

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

    def test_unknown_temporary_observation_never_guesses_safe_restore(self):
        for fault in ("unknown", "exception", "malformed"):
            with self.subTest(fault=fault):
                plan, journal, provider, result = self.run_model({"read_temporary": fault})
                self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                self.assertIn("read_temporary", result["pendingOperations"])
                self.assertEqual(provider.calls[-1], "read_temporary")
                self.assertNotIn("disable_temporary", provider.calls)
                self.assertNotIn("restore_retained", provider.calls)
                self.assertEqual(
                    provider.snapshot()["snapshot"]["activeVersion"], plan["temporaryVersion"]
                )
                self.assertIsNotNone(provider.snapshot()["receiver"])
                self.assertEqual(
                    [name for name, _ in journal.records() if name.startswith("reconcile_")],
                    ["reconcile_1", "reconcile_2"],
                )

    def test_refused_restore_cannot_delete_receiver_or_guess_original_version(self):
        plan, _, provider, result = self.run_model({"restore_retained": "refused"})
        self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
        self.assertEqual(provider.snapshot()["snapshot"]["activeVersion"], plan["temporaryVersion"])
        self.assertNotIn("delete_receiver", provider.calls)
        self.assertIsNotNone(provider.snapshot()["receiver"])

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


class CompleteCompositionLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="full-baseline-lifecycle-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sequence = 0

    def make_model(self, faults=None, tick_ms=0):
        self.sequence += 1
        baseline, additions = composition_inputs()
        plan = build_composition_plan(build_delta(baseline, additions), START)
        path = self.root / f"attempt-{self.sequence}.sqlite"
        journal = LifecycleJournal(path, plan)
        self.addCleanup(journal.close)
        provider = SyntheticCompositionProvider(plan, faults, tick_ms=tick_ms)
        return plan, path, journal, provider

    def test_complete_baseline_round_trip_and_reverse_owned_resource_cleanup(self):
        plan, _, journal, provider = self.make_model()
        baseline = copy.deepcopy(plan["delta"]["baseline"])
        result = rehearse_composition(plan, journal, provider)
        self.assertEqual(result["cleanup"], "confirmed_offline")
        self.assertEqual(provider.calls, list(COMPOSITION_OPERATIONS))
        final = provider.snapshot()
        self.assertEqual(final["snapshot"], baseline)
        self.assertEqual(final["ownedResources"], [])
        self.assertIs(final["admission"]["enabled"], False)
        self.assertEqual(result["retainedTemporaryVersion"], "temporary-version")
        self.assertEqual(final["uploadedVersion"]["version"], "temporary-version")
        self.assertLess(
            provider.calls.index("read_disabled"), provider.calls.index("restore_retained")
        )
        self.assertLess(
            provider.calls.index("read_restored"), provider.calls.index("delete_resource_2")
        )
        self.assertEqual(
            [call for call in provider.calls if call.startswith("delete_resource_")],
            ["delete_resource_2", "delete_resource_1", "delete_resource_0"],
        )
        for field in PROOF_FIELDS:
            self.assertIs(result[field], False)
        self.assertFalse(result["pendingOperations"])

    def test_unknown_effects_latch_without_guessed_rollback_or_replay(self):
        for operation in COMPOSITION_OPERATIONS:
            for fault in ("unknown", "exception", "malformed"):
                with self.subTest(operation=operation, fault=fault):
                    plan, path, journal, provider = self.make_model({operation: fault})
                    result = rehearse_composition(plan, journal, provider)
                    self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                    self.assertIn(operation, result["pendingOperations"])
                    self.assertEqual(provider.calls[-3:], [operation, "reconcile_1", "reconcile_2"])
                    self.assertEqual(len(provider.calls), len(set(provider.calls)))
                    self.assertLessEqual(result["operationsAttempted"], 25)
                    records = journal.records()
                    journal.close()
                    reopened = LifecycleJournal(path, plan)
                    self.addCleanup(reopened.close)
                    fresh_provider = SyntheticCompositionProvider(plan)
                    with self.assertRaisesRegex(ValueError, "already_attempted"):
                        rehearse_composition(plan, reopened, fresh_provider)
                    self.assertFalse(fresh_provider.calls)
                    self.assertEqual(reopened.records(), records)
                    if operation == "upload_version":
                        self.assertEqual(result["temporaryVersionDisposition"], "unknown")
                        self.assertIsNotNone(provider.snapshot()["uploadedVersion"])
                    if operation.startswith("create_resource_"):
                        self.assertIn(operation, result["unacknowledgedCreationOperations"])
                    if operation.startswith("delete_resource_"):
                        self.assertTrue(result["ownedResourcesRequiringReconciliation"])
                    if operation == "apply_temporary":
                        self.assertEqual(
                            provider.snapshot()["snapshot"], plan["delta"]["temporary"]
                        )
                        self.assertNotIn("restore_retained", provider.calls)
                    if operation == "restore_retained":
                        self.assertEqual(provider.snapshot()["snapshot"], plan["delta"]["baseline"])
                        self.assertEqual(len(provider.snapshot()["ownedResources"]), 3)

    def test_failed_reconciliation_never_clears_unknown_apply_or_adds_mutations(self):
        for fault in ("unknown", "exception", "malformed", "refused"):
            plan, _, journal, provider = self.make_model(
                {"apply_temporary": "unknown", "reconcile_1": fault, "reconcile_2": fault}
            )
            result = rehearse_composition(plan, journal, provider)
            self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
            self.assertIn("apply_temporary", result["pendingOperations"])
            self.assertEqual(provider.calls[-3:], ["apply_temporary", "reconcile_1", "reconcile_2"])
            self.assertNotIn("restore_retained", provider.calls)
            self.assertLessEqual(len(journal.records()), plan["operationCap"])

    def test_known_drift_requires_independent_full_state_match_before_restore_or_delete(self):
        for fault in (
            "configuration_drift",
            "module_drift",
            "ownership_drift",
            "typed_data_drift",
            "secret_drift",
            "weights_drift",
        ):
            for operation in ("read_resource_2", "read_disabled", "read_restored"):
                with self.subTest(operation=operation, fault=fault):
                    plan, _, journal, provider = self.make_model({operation: fault})
                    result = rehearse_composition(plan, journal, provider)
                    self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                    self.assertFalse(
                        any(call.startswith("delete_resource_") for call in provider.calls)
                    )
                    if operation == "read_disabled":
                        self.assertNotIn("restore_retained", provider.calls)
                    self.assertEqual(len(provider.snapshot()["ownedResources"]), 3)

    def test_stop_after_each_work_stage_never_applies_and_cleans_only_confirmed_owned_state(self):
        for operation in (
            "create_resource_0",
            "read_resource_1",
            "initialize_synthetic",
            "read_version",
        ):
            with self.subTest(operation=operation):
                plan, _, journal, provider = self.make_model({operation: "stop"})
                result = rehearse_composition(plan, journal, provider)
                self.assertTrue(result["stopObserved"])
                self.assertNotIn("apply_temporary", provider.calls)
                self.assertEqual(result["cleanup"], "confirmed_offline")
                self.assertEqual(provider.snapshot()["snapshot"], plan["delta"]["baseline"])
                self.assertEqual(provider.snapshot()["ownedResources"], [])

    def test_stop_after_apply_restores_exact_original_but_unknown_stop_never_restores(self):
        plan, _, journal, provider = self.make_model({"apply_temporary": "stop"})
        result = rehearse_composition(plan, journal, provider)
        self.assertTrue(result["stopObserved"])
        self.assertEqual(result["cleanup"], "confirmed_offline")
        self.assertEqual(provider.snapshot()["snapshot"], plan["delta"]["baseline"])
        for fault in ("refused", "unknown"):
            plan, _, journal, provider = self.make_model({"disable_temporary": fault})
            result = rehearse_composition(plan, journal, provider)
            self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
            self.assertNotIn("restore_retained", provider.calls)
            self.assertFalse(any(call.startswith("delete_resource_") for call in provider.calls))

    def test_deadlines_do_not_extend_or_replay_expired_plan(self):
        options_list: list[dict[str, Any]] = [{"stop_requested": True}, {"now_ms": START + 600_000}]
        for options in options_list:
            plan, path, journal, provider = self.make_model()
            result = rehearse_composition(plan, journal, provider, **options)
            self.assertEqual(result["cleanup"], "not_applied")
            self.assertFalse(provider.calls)
            journal.close()
            reopened = LifecycleJournal(path, plan)
            self.addCleanup(reopened.close)
            with self.assertRaisesRegex(ValueError, "already_attempted"):
                rehearse_composition(plan, reopened, SyntheticCompositionProvider(plan))
        plan, _, journal, provider = self.make_model(tick_ms=120_000)
        result = rehearse_composition(plan, journal, provider)
        self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
        self.assertEqual(result["reason"], "outer_expired")
        self.assertLessEqual(provider.elapsed_ms, plan["outerExpiresMs"] - START)
        self.assertNotIn("apply_temporary", provider.calls)

    def test_foreign_or_lost_journal_owner_refuses_before_provider_effects(self):
        for replacement in (None, "synthetic-foreign-owner"):
            with self.subTest(replacement=replacement):
                plan, _, journal, provider = self.make_model()
                journal.marker.unlink()
                if replacement is not None:
                    journal.marker.write_text(replacement, encoding="utf-8")
                with self.assertRaises((ValueError, FileExistsError)):
                    rehearse_composition(plan, journal, provider)
                self.assertFalse(provider.calls)
                journal.close()
                if replacement is not None:
                    self.assertEqual(journal.marker.read_text(encoding="utf-8"), replacement)

    def test_quota_reinitialization_cannot_reset_usage_and_disable_preserves_observations(self):
        plan, _, journal, provider = self.make_model({"initialize_synthetic": "unknown"})
        result = rehearse_composition(plan, journal, provider)
        self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
        provider._state["quotaScope"].update(
            fga=3, receiver=2, arrivals=1, authorizationPresent=True, canaryMatch=True
        )
        original = copy.deepcopy(provider.snapshot()["quotaScope"])
        response = provider._call("initialize_synthetic", {"run": plan["run"], "startsAt": START})
        self.assertEqual(response["outcome"], "refused")
        self.assertEqual(provider.snapshot()["quotaScope"], original)
        response = provider._call("disable_temporary", {"run": plan["run"]})
        self.assertEqual(response["outcome"], "accepted")
        original["enabled"] = False
        self.assertEqual(provider.snapshot()["quotaScope"], original)

    def test_version_restore_cannot_repair_or_hide_production_data_drift(self):
        plan, _, _, provider = self.make_model()
        provider._state["snapshot"]["productionState"]["rows"].append(["unexpected-row", 2])
        before = copy.deepcopy(provider.snapshot()["snapshot"]["productionState"])
        response = provider._call("restore_retained", plan["delta"]["restore"])
        self.assertEqual(response["outcome"], "accepted")
        self.assertEqual(provider.snapshot()["snapshot"]["productionState"], before)
        self.assertNotEqual(provider.snapshot()["snapshot"], plan["delta"]["baseline"])

    def test_unreviewed_provider_state_is_not_inherited_as_expected_baseline(self):
        plan, _, journal, provider = self.make_model()
        provider._state["unreviewed"] = True
        result = rehearse_composition(plan, journal, provider)
        self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
        self.assertEqual(provider.calls, ["read_baseline"])
        self.assertEqual(provider.snapshot()["ownedResources"], [])

    def test_owner_replacement_between_observation_and_apply_prevents_next_dispatch(self):
        plan, _, journal, provider = self.make_model()
        dispatch = provider._call

        def replace_owner(operation, request):
            result = dispatch(operation, request)
            if operation == "read_version":
                journal.marker.write_text("synthetic-replacement-owner", encoding="utf-8")
            return result

        with patch.object(provider, "_call", side_effect=replace_owner):
            with self.assertRaises(ValueError):
                rehearse_composition(plan, journal, provider)
        self.assertEqual(provider.calls[-1], "read_version")
        self.assertNotIn("apply_temporary", provider.calls)
        self.assertEqual(provider.snapshot()["snapshot"], plan["delta"]["baseline"])
        journal.close()
        self.assertEqual(journal.marker.read_text(encoding="utf-8"), "synthetic-replacement-owner")

    def test_lifecycle_cannot_move_embedded_worker_window_to_a_new_start(self):
        baseline, additions = composition_inputs()
        delta = build_delta(baseline, additions)
        with self.assertRaises(ValueError):
            build_composition_plan(delta, START + 1)

    def test_closure_tamper_and_journal_plan_mismatch_refuse_before_effects(self):
        plan, path, journal, provider = self.make_model()
        tampered = copy.deepcopy(plan)
        tampered["delta"]["temporary"]["configuration"]["attachment"]["logpush"] = True
        with self.assertRaises(ValueError):
            rehearse_composition(tampered, journal, provider)
        self.assertFalse(provider.calls)
        self.assertFalse(journal.records())
        journal.close()
        baseline, additions = composition_inputs()
        baseline["configuration"]["assets"]["directory"] = "different-assets"
        other = build_composition_plan(build_delta(baseline, additions), START)
        with self.assertRaisesRegex(ValueError, "plan_mismatch"):
            LifecycleJournal(path, other)


if __name__ == "__main__":
    unittest.main()
