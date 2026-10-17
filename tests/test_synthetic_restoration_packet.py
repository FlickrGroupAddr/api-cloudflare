"""Offline adversarial checks for the concrete synthetic restoration packet/lifecycle."""

import copy
import socket
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts import synthetic_restoration_packet as restoration


class SyntheticRestorationPacketTests(unittest.TestCase):
    def setUp(self):
        self.packet = restoration.build_packet("a" * 32, 1_000)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def journal(self, name="journal.sqlite3"):
        journal = restoration.Journal(self.root / name, self.packet)
        self.addCleanup(journal.close)
        return journal

    def test_packet_is_closed_finite_and_explicitly_offline(self):
        restoration.validate_packet(self.packet)
        self.assertEqual(self.packet["secretTypes"], ["secrets_store_secret"])
        self.assertEqual(
            self.packet["capturedBindingTypes"],
            {
                "assets": 1,
                "d1": 1,
                "durable_object_namespace": 1,
                "plain_text": 14,
                "secrets_store_secret": 9,
            },
        )
        self.assertEqual(
            self.packet["capturedBindingsSourceSha256"],
            "8d41009f984b5292e2e5ae6a89cdd2529d01b7aac5a7e8f8e0ad1d7e375ed097",
        )
        self.assertEqual(self.packet["workExpiresMs"] - self.packet["startMs"], 600_000)
        self.assertEqual(self.packet["outerExpiresMs"] - self.packet["startMs"], 1_200_000)
        self.assertEqual(len(self.packet["cases"]), 2 * len(restoration.SUPPORTED_SECRET_TYPES))
        identities = []
        for case in self.packet["cases"]:
            identities.extend(case["resources"].values())
            self.assertEqual(case["operationCap"], len(case["operations"]) + 2)
            self.assertEqual(len(case["operations"]), len(set(case["operations"])))
            self.assertEqual(case["syntheticInvocationsCap"], 4)
            self.assertEqual(
                case["restore"],
                {
                    "strategy": "percentage",
                    "force": False,
                    "versions": [{"version_id": case["baselineVersion"], "percentage": 100}],
                },
            )
            self.assertNotEqual(case["baselineVersion"], case["temporaryVersion"])
        self.assertEqual(len(identities), len(set(identities)))
        for key in (
            "providerRestorationVerified",
            "changedSecretSemanticsVerified",
            "productionStateVerified",
            "deploymentAllowed",
        ):
            self.assertIs(self.packet[key], False)

    def test_constructor_refuses_bad_run_time_and_owner(self):
        for run in (None, "a" * 31, "A" * 32, "../synthetic", 123):
            with self.subTest(run=run), self.assertRaises(ValueError):
                restoration.build_packet(cast(Any, run), 1_000)
        for start in (True, False, -1, 1.0, "1000", 2**53):
            with self.subTest(start=start), self.assertRaises(ValueError):
                restoration.build_packet("a" * 32, cast(Any, start))
        with self.assertRaises(ValueError):
            restoration.build_packet("a" * 32, 1_000, owner="terry")

    def test_closed_schema_rejects_tampering_and_json_boolean_integer_equivalence(self):
        mutations = (
            lambda p: p.update(schemaVersion=True),
            lambda p: p.update(deploymentAllowed=0),
            lambda p: p.update(startMs=True),
            lambda p: p.update(workExpiresMs=p["workExpiresMs"] + 1),
            lambda p: p.update(outerExpiresMs=p["outerExpiresMs"] + 1),
            lambda p: p.update(extra="unreviewed"),
            lambda p: p.update(captureIndexSha256="0" * 64),
            lambda p: p["secretTypes"].append("secret_text"),
            lambda p: p["cases"].pop(),
            lambda p: p["cases"][0].update(operationCap=999),
            lambda p: p["cases"][0].update(syntheticInvocationsCap=5),
            lambda p: p["cases"][0]["restore"].update(force=0),
            lambda p: p["cases"][0]["restore"].update(force=True),
            lambda p: p["cases"][0]["restore"]["versions"][0].update(percentage=100.0),
            lambda p: p["cases"][0]["restore"]["versions"][0].update(version_id="latest"),
            lambda p: p["cases"][0]["resources"].update(d1="production"),
            lambda p: p["cases"][0]["operations"].append("force_restore"),
        )
        for index, mutate in enumerate(mutations):
            packet = copy.deepcopy(self.packet)
            mutate(packet)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                restoration.validate_packet(cast(Any, packet))
        for packet in ({}, [], None):
            with self.subTest(shape=packet), self.assertRaises(ValueError):
                restoration.validate_packet(cast(Any, packet))

    def test_case_a_compares_every_snapshot_dimension(self):
        before = restoration.baseline_snapshot(self.packet["cases"][0])
        self.assertEqual(
            restoration.classify("A", before, copy.deepcopy(before), "accepted"), "preserved"
        )
        replacements = {
            "activeVersion": "unexpected",
            "weights": {"unexpected": 100},
            "moduleDigest": "0" * 64,
            "bindings": {"unexpected": True},
            "resources": {"unexpected": "synthetic"},
            "configuration": {},
            "data": {"schema": "synthetic_v1", "rows": []},
            "gates": {
                "deployment": {"enabled": False, "revision": 8},
                "user": {"enabled": False, "revision": 11},
            },
            "secretMatchesBaseline": False,
        }
        for key, replacement in replacements.items():
            after = copy.deepcopy(before)
            after[key] = replacement
            with self.subTest(dimension=key):
                self.assertEqual(restoration.classify("A", before, after, "accepted"), "drift")
        self.assertEqual(restoration.classify("A", before, before, "refused"), "drift")
        self.assertEqual(
            restoration.classify("A", before, before, "unknown"), "unknown_cleanup_unconfirmed"
        )

    def test_snapshot_rejects_boolean_integer_confusion_and_unpaused_baseline(self):
        before = restoration.baseline_snapshot(self.packet["cases"][0])
        mutations = (
            lambda p: p.update(secretMatchesBaseline=1),
            lambda p: p.update(weights={p["activeVersion"]: True}),
            lambda p: p["gates"]["deployment"].update(enabled=0),
            lambda p: p["gates"]["deployment"].update(revision=True),
            lambda p: p["gates"].update(extra={"enabled": False, "revision": 1}),
            lambda p: p.update(moduleDigest="invalid"),
            lambda p: p.update(extra="unreviewed"),
        )
        for index, mutate in enumerate(mutations):
            after = copy.deepcopy(before)
            mutate(after)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                restoration.classify("A", before, after, "accepted")
        before["gates"]["user"]["enabled"] = True
        with self.assertRaisesRegex(ValueError, "baseline_not_paused"):
            restoration.classify("A", before, before, "accepted")

    def test_case_b_accounts_refusal_and_distinguishes_value_and_reference_drift(self):
        case = next(c for c in self.packet["cases"] if c["case"] == "B")
        before = restoration.baseline_snapshot(case)
        changed = copy.deepcopy(before)
        changed.update(activeVersion=case["temporaryVersion"], secretMatchesBaseline=False)
        changed["weights"] = {case["temporaryVersion"]: 100}
        self.assertEqual(
            restoration.classify("B", before, changed, "refused", pre_restore=changed),
            "refusal_accounted",
        )
        self.assertEqual(
            restoration.classify("B", before, before, "refused", pre_restore=changed),
            "refusal_with_drift",
        )
        after = copy.deepcopy(before)
        after["secretMatchesBaseline"] = False
        self.assertEqual(
            restoration.classify("B", before, after, "accepted", pre_restore=changed),
            "accepted_changed_value_drift",
        )
        after["resources"]["secret"] = "unexpected-reference"
        self.assertEqual(
            restoration.classify("B", before, after, "accepted", pre_restore=changed),
            "accepted_configuration_or_data_drift",
        )
        self.assertEqual(
            restoration.classify("B", before, before, "accepted", pre_restore=changed),
            "accepted_baseline_observed",
        )
        with self.assertRaisesRegex(ValueError, "changed_snapshot_required"):
            restoration.classify("B", before, before, "accepted")
        with self.assertRaisesRegex(ValueError, "secret_change_not_measured"):
            restoration.classify("B", before, before, "accepted", pre_restore=before)

    def test_rehearsal_all_outcomes_never_qualify_provider_or_cleanup_case_b(self):
        outcomes = {
            "refused": "refusal_accounted",
            "changed_value": "accepted_changed_value_drift",
            "baseline": "accepted_baseline_observed",
            "unknown": "unknown_cleanup_unconfirmed",
            "resource_drift": "accepted_configuration_or_data_drift",
        }
        with patch.object(socket, "socket", side_effect=AssertionError("outbound forbidden")):
            for outcome, classification in outcomes.items():
                with self.subTest(outcome=outcome):
                    journal = self.journal(outcome + ".sqlite3")
                    receipt = restoration.rehearse(self.packet, journal, outcome)
                    for result, case in zip(receipt["results"], self.packet["cases"], strict=True):
                        self.assertLessEqual(result["operationsAttempted"], case["operationCap"])
                        if case["case"] == "A":
                            self.assertEqual(result["classification"], "preserved")
                            self.assertEqual(result["cleanup"], "confirmed_offline")
                        else:
                            self.assertEqual(result["classification"], classification)
                            self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                    self.assertEqual(receipt["packetSha256"], restoration.digest(self.packet))
                    for key in (
                        "providerRestorationVerified",
                        "changedSecretSemanticsVerified",
                        "productionStateVerified",
                        "deploymentAllowed",
                    ):
                        self.assertIs(receipt[key], False)

    def test_latch_rejects_replay_unknown_operations_and_invalid_times(self):
        journal = self.journal()
        case = self.packet["cases"][0]
        for case_id, operation in (("other", "restore_retained"), (case["id"], "force_restore")):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                journal.latch(case_id, operation, 1_000)
        for now in (True, 1_000.0, 999):
            with self.subTest(now=now), self.assertRaisesRegex(ValueError, "operation_time"):
                journal.latch(case["id"], case["operations"][0], cast(Any, now))
        journal.latch(case["id"], case["operations"][0], 1_000)
        with self.assertRaisesRegex(ValueError, "replay|already_attempted|unacknowledged"):
            journal.latch(case["id"], case["operations"][0], 1_000)

    def test_expiry_prevents_restore_and_snapshot_operations(self):
        journal = self.journal()
        case = self.packet["cases"][0]
        for operation in ("restore_retained", "snapshot_restored"):
            for now in (self.packet["workExpiresMs"], self.packet["outerExpiresMs"] + 1):
                with self.subTest(operation=operation, now=now):
                    with self.assertRaisesRegex(ValueError, "scope_expired"):
                        journal.latch(case["id"], operation, now)

    def test_ordering_and_pending_acknowledgment_prevent_unsafe_advance(self):
        journal = self.journal()
        case = self.packet["cases"][0]
        for operation in ("restore_retained", "delete_worker"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "operation_order"):
                    journal.latch(case["id"], operation, 1_000)
        with self.assertRaisesRegex(ValueError, "without_pending"):
            journal.acknowledge(case["id"], "create_worker")
        first, second = case["operations"][:2]
        journal.latch(case["id"], first, 1_000)
        with self.assertRaisesRegex(ValueError, "unacknowledged"):
            journal.latch(case["id"], second, 1_000)
        journal.acknowledge(case["id"], first)
        with self.assertRaisesRegex(ValueError, "without_pending"):
            journal.acknowledge(case["id"], first)
        journal.latch(case["id"], second, 1_000)

    def test_unknown_delete_retains_pending_identity_and_never_confirms_cleanup(self):
        journal = self.journal()
        receipt = restoration.rehearse(self.packet, journal, delete_outcome="unknown")
        for result in receipt["results"]:
            self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
        for case in self.packet["cases"]:
            if case["case"] == "A":
                with self.subTest(case=case["id"]):
                    with self.assertRaisesRegex(ValueError, "unacknowledged"):
                        journal.latch(case["id"], "delete_worker", 1_000)

    def test_unknown_restore_cannot_replay_or_delete_and_read_reconciliation_is_finite(self):
        journal = self.journal()
        receipt = restoration.rehearse(self.packet, journal, "unknown")
        for result, case in zip(receipt["results"], self.packet["cases"], strict=True):
            if case["case"] == "B":
                self.assertEqual(result["classification"], "unknown_cleanup_unconfirmed")
                self.assertEqual(result["cleanup"], "cleanup_unconfirmed")
                for operation in ("restore_retained", "snapshot_restored", "delete_worker"):
                    with self.subTest(case=case["id"], operation=operation):
                        with self.assertRaisesRegex(ValueError, "unacknowledged"):
                            journal.latch(case["id"], operation, 1_000)
                with self.assertRaisesRegex(ValueError, "reconciliation_exhausted"):
                    journal.reconcile(case["id"])

    def test_cleanup_can_finish_after_expiry_only_after_every_predecessor_acknowledged(self):
        journal = self.journal()
        case = self.packet["cases"][0]
        for operation in case["operations"]:
            now = (
                self.packet["outerExpiresMs"] + 1
                if operation.startswith("delete_")
                else self.packet["startMs"]
            )
            journal.latch(case["id"], operation, now)
            journal.acknowledge(case["id"], operation)
        with self.assertRaisesRegex(ValueError, "replay"):
            journal.latch(case["id"], "delete_worker", self.packet["outerExpiresMs"] + 1)

    def test_owner_lock_prevents_parallel_run_and_journal_prevents_replay_after_close(self):
        path = self.root / "owner.sqlite3"
        journal = restoration.Journal(path, self.packet)
        try:
            with self.assertRaises(FileExistsError):
                restoration.Journal(path, self.packet)
            restoration.rehearse(self.packet, journal)
        finally:
            journal.close()
        reopened = restoration.Journal(path, self.packet)
        try:
            with self.assertRaisesRegex(ValueError, "replay|already_attempted|unacknowledged"):
                restoration.rehearse(self.packet, reopened)
        finally:
            reopened.close()

    def test_pending_attempt_survives_connection_close_and_blocks_resume(self):
        path = self.root / "pending.sqlite3"
        case = self.packet["cases"][0]
        first, second = case["operations"][:2]
        journal = restoration.Journal(path, self.packet)
        journal.latch(case["id"], first, 1_000)
        journal.close()
        reopened = restoration.Journal(path, self.packet)
        try:
            for operation in (first, second):
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(ValueError, "unacknowledged"):
                        reopened.latch(case["id"], operation, 1_000)
        finally:
            reopened.close()

    def test_journal_packet_binding_refuses_other_run(self):
        path = self.root / "bound.sqlite3"
        journal = restoration.Journal(path, self.packet)
        journal.close()
        other = restoration.build_packet("b" * 32, 1_000)
        with self.assertRaisesRegex(ValueError, "journal_packet_mismatch"):
            restoration.Journal(path, other)
        self.assertFalse(path.with_name(path.name + ".owner").exists())


if __name__ == "__main__":
    unittest.main()
