"""Independent fixed-program SOURCE faults; never native qualification.

MIT License; copyright 2026 Terry Ott. Every database is fresh synthetic state.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any

from mechanism import MechanismAdapter, MechanismOracle, make_packet, source_pin
from runner import Cost, Receipt, Refusal, Runner, SQLiteJournal, packet_digest, validate_packet


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now


class RunnerFaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "external-journal.sqlite"
        self.clock = Clock()
        self.value = make_packet(1)
        self.adapter = MechanismAdapter(self.value, self.clock)
        self.addCleanup(self.adapter.close)
        self.oracle = MechanismOracle(self.value)

    def run_source(self, value=None, journal=None, source=None, adapters=None, oracle=None):
        return Runner(
            value or self.value,
            journal or SQLiteJournal(self.path),
            {"mechanism": self.adapter} if adapters is None else adapters,
            self.clock,
            source or source_pin,
            self.oracle if oracle is None else oracle,
        ).run()

    def instrument(self, callback):
        original = self.adapter.invoke

        def invoke(operation, deadline):
            return callback(operation, deadline, original)

        self.adapter.invoke = invoke

    def fresh_adapter(self):
        self.adapter.close()
        self.clock.now = 10
        self.value = make_packet(1)
        self.adapter = MechanismAdapter(self.value, self.clock)
        self.addCleanup(self.adapter.close)
        self.oracle = MechanismOracle(self.value)

    def test_happy_mechanism_exact_order_no_replay_and_no_qualification(self):
        result = self.run_source()
        self.assertEqual((result.status, result.completed_cases), ("mechanism_complete", 1))
        self.assertEqual((result.scope, result.qualification), ("SOURCE_SYNTHETIC_ONLY", "NO_GO"))
        stages = [name.split("_", 1)[1] for name in self.adapter.calls]
        self.assertLess(stages.index("closure_readback"), stages.index("baseline_0"))
        self.assertLess(stages.index("admission_off"), stages.index("restore"))
        self.assertLess(stages.index("restore_readback"), stages.index("restored_0"))
        calls = self.adapter.calls[:]
        self.assertEqual(self.run_source().status, "refused")
        self.assertEqual(self.adapter.calls, calls)

    def test_all_twelve_source_program_outcomes_are_reachable(self):
        for number in range(1, 13):
            with self.subTest(case=number), tempfile.TemporaryDirectory() as directory:
                value = make_packet(number)
                adapter = MechanismAdapter(value, self.clock)
                try:
                    result = Runner(
                        value,
                        SQLiteJournal(Path(directory) / "journal.sqlite"),
                        {"mechanism": adapter},
                        self.clock,
                        source_pin,
                        MechanismOracle(value),
                    ).run()
                    expected = (
                        "unknown"
                        if number in {4, 5, 6, 10, 11}
                        else ("closed_refusal" if number == 12 else "mechanism_complete")
                    )
                    self.assertEqual(result.status, expected)
                    self.assertEqual(result.qualification, "NO_GO")
                    self.assertTrue(all(n.startswith(f"case{number}_") for n in adapter.calls))
                finally:
                    adapter.close()

    def test_missing_context_and_full65_candidate_refuse_before_dispatch(self):
        assert self.value.context
        for context in (None, dataclasses.replace(self.value.context, table_count=65)):
            with self.subTest(context=context):
                result = self.run_source(dataclasses.replace(self.value, context=context))
                self.assertEqual(result.status, "refused")
                self.assertEqual(result.completed_cases, 0)
                self.assertEqual(self.adapter.calls, [])

    def test_generic_adapter_or_oracle_flags_cannot_supply_programs(self):
        class Flags:
            program_pin = self.adapter.program_pin

            def invoke(self, operation, deadline):
                raise AssertionError("untrusted flag adapter was invoked")

        for adapters, oracle in (
            ({"mechanism": Flags()}, self.oracle),
            ({"mechanism": self.adapter}, Flags()),
            ({}, self.oracle),
        ):
            with self.subTest(adapters=adapters):
                result = self.run_source(adapters=adapters, oracle=oracle)
                self.assertEqual(result.status, "refused")
                self.assertEqual(self.adapter.calls, [])

    def test_operation_tree_relabel_and_cost_understatement_refuse(self):
        for field, replacement in (
            ("action", "arbitrary.aggregate.close"),
            ("cost", Cost(requests=1, mutations=1)),
        ):
            cases = list(self.value.cases)
            operations = list(cases[0].operations)
            operations[1] = dataclasses.replace(operations[1], **{field: replacement})
            cases[0] = dataclasses.replace(cases[0], operations=tuple(operations))
            with self.subTest(field=field):
                result = self.run_source(dataclasses.replace(self.value, cases=tuple(cases)))
                self.assertEqual(result.status, "refused")
                self.assertEqual(self.adapter.calls, [])

    def test_lost_unsafe_action_ack_stops_without_recovery_or_new_key(self):
        for stage in ("settle", "close", "restore", "cleanup", "restore_readback"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                self.path = Path(directory) / "journal.sqlite"
                self.fresh_adapter()

                def fail(operation, deadline, original, stage=stage):
                    if operation.stage == stage:
                        raise OSError("synthetic_private_marker_must_not_escape")
                    return original(operation, deadline)

                original = self.adapter.invoke
                self.instrument(fail)
                result = self.run_source()
                self.adapter.invoke = original
                self.assertEqual(result.status, "unknown")
                self.assertNotIn("synthetic_private_marker", result.reason)
                calls = self.adapter.calls[:]
                retry = self.run_source(dataclasses.replace(self.value, key="fresh-key"))
                self.assertEqual(retry.status, "refused")
                self.assertEqual(self.adapter.calls, calls)

    def test_expiry_after_awaited_work_keeps_pending_intent(self):
        self.adapter.after = lambda _: setattr(self.clock, "now", 1200)
        result = self.run_source()
        self.assertEqual(result.status, "unknown")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT status FROM operations").fetchall(), [("dispatching",)]
            )

    def test_clock_reversal_is_not_a_new_window(self):
        self.adapter.after = lambda _: setattr(self.clock, "now", 9)
        self.assertEqual(self.run_source().reason, "monotonic_clock_rewound")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_source_drift_after_dispatch_cannot_finish_receipt(self):
        pin = [source_pin()]
        self.adapter.after = lambda _: pin.__setitem__(0, "b" * 64)
        self.assertEqual(self.run_source(source=lambda: pin[0]).reason, "source_binding_drift")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_per_call_deadline_cannot_extend_sixty_seconds(self):
        self.adapter.after = lambda _: setattr(self.clock, "now", 70)
        self.assertEqual(self.run_source().status, "unknown")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_actual_overrun_cannot_borrow_a_later_slot(self):
        def overrun(operation, deadline, original):
            receipt = original(operation, deadline)
            return dataclasses.replace(
                receipt, actual_cost=dataclasses.replace(receipt.actual_cost, effects=9999)
            )

        self.instrument(overrun)
        self.assertEqual(self.run_source().reason, "invalid_or_unmeasurable_receipt")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_each_actual_counter_overrun_stops_at_reserved_operation(self):
        for field in dataclasses.fields(Cost):
            with self.subTest(counter=field.name), tempfile.TemporaryDirectory() as directory:
                self.path = Path(directory) / "journal.sqlite"
                self.fresh_adapter()

                def overrun(operation, deadline, original, field=field):
                    receipt = original(operation, deadline)
                    cost = dataclasses.replace(
                        receipt.actual_cost, **{field.name: getattr(operation.cost, field.name) + 1}
                    )
                    return dataclasses.replace(receipt, actual_cost=cost)

                self.instrument(overrun)
                self.assertEqual(self.run_source().reason, "invalid_or_unmeasurable_receipt")
                self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_expiry_during_final_oracle_cannot_become_terminal_success(self):
        original = self.oracle.verify_receipt

        def late(operation, receipt):
            original(operation, receipt)
            if operation.stage == "cleanup_readback":
                self.clock.now = 1200

        self.oracle.verify_receipt = late
        self.assertEqual(self.run_source().status, "unknown")

    def test_preflight_oracle_delay_cannot_escape_baseline_freshness(self):
        original = self.oracle.verify
        capture = [None]

        def observe(operation, deadline, invoke):
            capture[0] = operation.capture
            return invoke(operation, deadline)

        def delayed(snapshot):
            original(snapshot)
            if capture[0] == "preflight":
                self.clock.now = 80

        self.instrument(observe)
        self.oracle.verify = delayed
        self.assertEqual(self.run_source().status, "unknown")
        self.assertNotIn("case1_admission_off", self.adapter.calls)
        self.assertNotIn("case1_restore", self.adapter.calls)

    def test_restored_oracle_delay_cannot_escape_restore_freshness(self):
        original = self.oracle.verify
        capture = [None]

        def observe(operation, deadline, invoke):
            capture[0] = operation.capture
            return invoke(operation, deadline)

        def delayed(snapshot):
            original(snapshot)
            if capture[0] == "restored":
                self.clock.now = 80

        self.instrument(observe)
        self.oracle.verify = delayed
        self.assertEqual(self.run_source().status, "unknown")
        self.assertNotIn("case1_cleanup", self.adapter.calls)

    def test_delayed_durable_finish_cannot_extend_capture_call_deadline(self):
        clock = self.clock

        class DelayedFinish(SQLiteJournal):
            def finish(self, case, operation, receipt):
                super().finish(case, operation, receipt)
                if operation.capture == "preflight":
                    clock.now = 80

        self.assertEqual(self.run_source(journal=DelayedFinish(self.path)).status, "unknown")
        self.assertNotIn("case1_restore", self.adapter.calls)

    def test_expired_durable_reservation_stops_before_adapter_dispatch(self):
        clock = self.clock
        invocations = []

        class DelayedReserve(SQLiteJournal):
            def reserve(self, case, operation):
                super().reserve(case, operation)
                clock.now = 80

        def observed(operation, deadline, invoke):
            invocations.append(operation.name)
            return invoke(operation, deadline)

        self.instrument(observed)
        self.assertEqual(self.run_source(journal=DelayedReserve(self.path)).status, "unknown")
        self.assertEqual(invocations, [], "expired reservation must not reach any adapter")

    def test_receipt_oracle_cannot_extend_first_call_deadline(self):
        original = self.oracle.verify_receipt

        def delayed(operation, receipt):
            original(operation, receipt)
            self.clock.now = 80

        self.oracle.verify_receipt = delayed
        self.assertEqual(self.run_source().status, "unknown")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_source_drift_during_durable_finish_stops_before_oracle(self):
        pin = [source_pin()]
        oracle_calls = []
        original = self.oracle.verify_receipt

        class DriftedFinish(SQLiteJournal):
            def finish(self, case, operation, receipt):
                super().finish(case, operation, receipt)
                pin[0] = "b" * 64

        def observed(operation, receipt):
            oracle_calls.append(operation.name)
            original(operation, receipt)

        self.oracle.verify_receipt = observed
        result = self.run_source(journal=DriftedFinish(self.path), source=lambda: pin[0])
        self.assertEqual(result.status, "unknown")
        self.assertEqual(oracle_calls, [], "source drift must fence independent evidence work")

    def test_expiry_after_saved_terminal_retains_durable_unknown_and_blocks_replay(self):
        clock = self.clock

        class DelayedTerminal(SQLiteJournal):
            def terminal(self, status, reason):
                super().terminal(status, reason)
                if status == "mechanism_complete":
                    clock.now = 80

        result = self.run_source(journal=DelayedTerminal(self.path))
        self.assertEqual(result.status, "unknown")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT status FROM campaign").fetchone(), ("unknown",))
        calls = self.adapter.calls[:]
        clock.now = 10
        self.assertEqual(self.run_source().status, "refused")
        self.assertEqual(self.adapter.calls, calls)

    def test_source_drift_after_saved_terminal_retains_durable_unknown(self):
        pin = [source_pin()]

        class DriftedTerminal(SQLiteJournal):
            def terminal(self, status, reason):
                super().terminal(status, reason)
                if status == "mechanism_complete":
                    pin[0] = "b" * 64

        result = self.run_source(journal=DriftedTerminal(self.path), source=lambda: pin[0])
        self.assertEqual(result.status, "unknown")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT status FROM campaign").fetchone(), ("unknown",))

    def test_snapshot_complete_identity_source_and_empty_bytes_refuse(self):
        for changes in (
            {"complete": False},
            {"identity": "wrong-resource"},
            {"source_pin": "b" * 64},
            {"canonical": b""},
        ):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                self.path = Path(directory) / "journal.sqlite"
                self.fresh_adapter()
                original = self.adapter.invoke
                self.adapter.calls.clear()

                def corrupt(operation, deadline, invoke, changes=changes):
                    receipt = invoke(operation, deadline)
                    if receipt.snapshot and operation.capture == "preflight":
                        return dataclasses.replace(
                            receipt, snapshot=dataclasses.replace(receipt.snapshot, **changes)
                        )
                    return receipt

                self.instrument(corrupt)
                result = self.run_source()
                self.adapter.invoke = original
                self.assertEqual(result.status, "unknown")
                self.assertNotIn("case1_restore", self.adapter.calls)

    def test_cold_pending_intent_cannot_finish_another_case_or_retry(self):
        journal = SQLiteJournal(self.path)
        journal.latch(self.value, packet_digest(self.value))
        operation = self.value.cases[0].operations[0]
        journal.reserve(1, operation)
        cold = SQLiteJournal(self.path)
        with self.assertRaises(Refusal):
            cold.reserve(1, self.value.cases[0].operations[1])
        with self.assertRaises(Refusal):
            cold.finish(2, operation, Receipt("confirmed", operation.cost, b"synthetic"))
        self.assertEqual(self.run_source(journal=cold).status, "refused")
        self.assertEqual(self.adapter.calls, [])

    def test_lost_latch_ack_after_commit_is_durable_unknown_without_effect_or_replay(self):
        committed = []
        callbacks = []

        class LostLatch(SQLiteJournal):
            def latch(self, packet, digest):
                super().latch(packet, digest)
                with closing(sqlite3.connect(self.path)) as db:
                    committed.append(db.execute("SELECT status FROM campaign").fetchone())
                raise OSError("invented lost latch acknowledgement after commit")

        def forbidden(operation, deadline, original):
            callbacks.append(operation.name)
            raise AssertionError("adapter effect after unknown latch")

        self.instrument(forbidden)
        result = self.run_source(journal=LostLatch(self.path))
        self.assertEqual(committed, [("running",)])
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "external_ack_or_adapter_unknown")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT status FROM campaign").fetchone(), ("unknown",))
            self.assertEqual(db.execute("SELECT count(*) FROM operations").fetchone(), (0,))
        self.assertEqual(callbacks, [])
        cold = SQLiteJournal(self.path)
        for value in (self.value, dataclasses.replace(self.value, key="new-key-after-lost-latch")):
            self.assertEqual(self.run_source(value=value, journal=cold).status, "refused")
        self.assertEqual(callbacks, [])
        self.assertEqual(self.adapter.calls, [])

    def test_known_already_reserved_refusal_never_downgrades_the_existing_attempt(self):
        journal = SQLiteJournal(self.path)
        digest = packet_digest(self.value)
        journal.latch(self.value, digest)
        for value in (self.value, dataclasses.replace(self.value, key="different-known-key")):
            result = self.run_source(value=value, journal=SQLiteJournal(self.path))
            self.assertEqual(
                (result.status, result.reason), ("refused", "campaign_already_reserved_no_replay")
            )
            with closing(sqlite3.connect(self.path)) as db:
                self.assertEqual(
                    db.execute("SELECT status,digest FROM campaign").fetchone(), ("running", digest)
                )
                self.assertEqual(db.execute("SELECT count(*) FROM operations").fetchone(), (0,))
        self.assertEqual(self.adapter.calls, [])

    def test_lost_durable_finish_ack_stays_spent(self):
        class LostFinish(SQLiteJournal):
            def finish(self, case, operation, receipt):
                super().finish(case, operation, receipt)
                raise OSError("synthetic lost acknowledgement")

        self.assertEqual(self.run_source(journal=LostFinish(self.path)).status, "unknown")
        self.assertEqual(self.run_source().status, "refused")
        self.assertEqual(self.adapter.calls, [self.value.cases[0].operations[0].name])

    def test_unknown_restore_fault_cannot_precede_restore_position(self):
        value = make_packet(12)
        cases = list(value.cases)
        operations = list(cases[-1].operations)
        operations[-1] = dataclasses.replace(operations[-1], action="unknown_restore")
        cases[-1] = dataclasses.replace(
            cases[-1], interruption="unknown_restore", operations=tuple(operations)
        )
        with self.assertRaises(Refusal):
            validate_packet(dataclasses.replace(value, cases=tuple(cases)))

    def test_cost_types_reject_bool_float_and_negative(self):
        for field in dataclasses.fields(Cost):
            bad_values: tuple[Any, ...] = (-1, True, 0.5)
            for bad in bad_values:
                with self.subTest(field=field.name, bad=bad), self.assertRaises(Refusal):
                    Cost(**{field.name: bad}).validate()


class NativeBrokerTests(unittest.TestCase):
    """Invented bookkeeping leases grant no native or provider authority."""

    def setUp(self):
        self.native = importlib.import_module("native_journal")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "external-native-intents.sqlite"
        self.broker = self.native.SQLiteNativeBroker(self.path)
        self.addCleanup(self.broker.close)
        self.cost = Cost(
            requests=1,
            mutations=1,
            sql_statements=1,
            effects=1,
            outbound_bytes=32,
            inbound_bytes=32,
            artifact_bytes=8192,
        )
        self.leaves = tuple(
            self.native.LeafIntent(
                ordinal,
                hashlib.sha256(f"invented-identity-{ordinal}".encode()).hexdigest(),
                "source-fixture/operation.py",
                "a" * 64,
                "source.fixture.sql",
                "invented-resource",
                hashlib.sha256(f"invented-request-{ordinal}".encode()).hexdigest(),
                self.cost,
            )
            for ordinal in range(2)
        )
        self.lease = self.native.NativeLease(
            "invented-native-lease",
            "b" * 64,
            "a" * 64,
            "pmb1-private-application-no-real-v1",
            "pmb1-private-object-kv-interface-v1",
            self.leaves,
        )

    def begin(self, ordinal=0):
        leaf = self.leaves[ordinal]
        return self.broker.begin(self.lease, ordinal, leaf.identity, leaf.request_digest)

    def finish(self, ordinal=0, cost=None):
        leaf = self.leaves[ordinal]
        return self.broker.finish(
            self.lease,
            ordinal,
            leaf.identity,
            leaf.request_digest,
            cost or dataclasses.replace(self.cost, artifact_bytes=8192),
            b"ack",
        )

    def test_durable_intent_precedes_effect_and_completed_cost_never_refunds(self):
        self.broker.reserve_tree(self.lease)
        before = self.broker.observe()["reserved"]
        effects = []
        self.begin()
        observed = self.broker.observe()
        self.assertEqual(observed["leaves"][0]["status"], "dispatching")
        effects.append("invented-local-effect")
        self.finish()
        observed = self.broker.observe()
        self.assertEqual(observed["next_ordinal"], 1)
        self.assertEqual(observed["reserved"], before)
        self.assertEqual(effects, ["invented-local-effect"])
        self.assertNotIn("ack", json.dumps(observed))

    def test_unknown_cost_refuses_before_any_durable_admission(self):
        leaf = dataclasses.replace(self.leaves[0], cost=None)
        lease = dataclasses.replace(self.lease, leaves=(leaf,))
        with self.assertRaises(Refusal):
            self.broker.reserve_tree(lease)
        self.assertEqual(self.broker.observe()["status"], "unreserved")
        self.assertIsNone(self.broker.observe()["reserved"])

    def test_zero_artifact_declaration_cannot_hide_leaf_and_lease_metadata(self):
        leaves = tuple(
            dataclasses.replace(leaf, cost=dataclasses.replace(self.cost, artifact_bytes=0))
            for leaf in self.leaves
        )
        with self.assertRaises(Refusal):
            self.broker.reserve_tree(dataclasses.replace(self.lease, leaves=leaves))
        self.assertEqual(self.broker.observe()["status"], "unreserved")

    def test_evidence_only_byte_count_cannot_omit_retained_intent_metadata(self):
        self.broker.reserve_tree(self.lease)
        self.begin()
        with self.assertRaises(Refusal):
            self.finish(cost=dataclasses.replace(self.cost, artifact_bytes=len(b"ack")))
        self.assertEqual(self.broker.observe()["status"], "unknown")

    def artifact_boundary(self, lease, evidence):
        size = 0
        for _ in range(8):
            actual = dataclasses.replace(self.cost, artifact_bytes=size)
            needed = self.native._retained_bytes(lease, 0, actual, self.cost, len(evidence))
            if size == needed:
                return actual
            size = needed
        self.fail("artifact envelope did not reach its finite exact boundary")

    def test_exact_artifact_boundary_covers_every_persisted_logical_column(self):
        lease = dataclasses.replace(self.lease, leaves=(self.leaves[0],))
        evidence = b"invented-evidence"
        actual = self.artifact_boundary(lease, evidence)
        self.broker.reserve_tree(lease)
        leaf = lease.leaves[0]
        self.broker.begin(lease, 0, leaf.identity, leaf.request_digest)
        self.broker.finish(lease, 0, leaf.identity, leaf.request_digest, actual, evidence)
        with closing(sqlite3.connect(self.path)) as db:
            # Independent lower bound from every persisted logical value,
            # including duplicated identity/digests, status/reason/numerics,
            # JSON and evidence. Physical SQLite encoding stays unmeasured.
            measured = 0
            for table in ("native_attempt", "native_leaves"):
                for row in db.execute(f"SELECT * FROM {table}"):
                    for value in row:
                        if value is not None:
                            measured += len(
                                value if isinstance(value, bytes) else str(value).encode("utf-8")
                            )
        self.assertLessEqual(measured, actual.artifact_bytes)
        before = self.broker.observe()["reserved"]
        self.broker.mark_unknown(lease, "invented-lost-terminal-ack")
        self.assertEqual(self.broker.observe()["status"], "unknown")
        self.assertEqual(self.broker.observe()["reserved"], before)

    def test_one_byte_below_full_logical_envelope_stays_unknown_without_refund(self):
        lease = dataclasses.replace(self.lease, leaves=(self.leaves[0],))
        evidence = b"invented-evidence"
        exact = self.artifact_boundary(lease, evidence)
        actual = dataclasses.replace(exact, artifact_bytes=exact.artifact_bytes - 1)
        self.broker.reserve_tree(lease)
        before = self.broker.observe()["reserved"]
        leaf = lease.leaves[0]
        self.broker.begin(lease, 0, leaf.identity, leaf.request_digest)
        with self.assertRaises(Refusal):
            self.broker.finish(lease, 0, leaf.identity, leaf.request_digest, actual, evidence)
        self.assertEqual(self.broker.observe()["status"], "unknown")
        self.assertEqual(self.broker.observe()["reserved"], before)

    def test_overall_budget_is_checked_atomically_before_first_intent(self):
        expensive = dataclasses.replace(
            self.leaves[0], cost=dataclasses.replace(self.cost, effects=2048)
        )
        lease = dataclasses.replace(self.lease, leaves=(expensive, self.leaves[1]))
        with self.assertRaises(Refusal):
            self.broker.reserve_tree(lease)
        self.assertEqual(self.broker.observe()["status"], "unreserved")
        self.assertEqual(self.broker.observe()["leaves"], [])

    def test_wrong_order_identity_or_request_never_begins_a_leaf(self):
        variants = (
            (1, self.leaves[1].identity, self.leaves[1].request_digest),
            (0, "c" * 64, self.leaves[0].request_digest),
            (0, self.leaves[0].identity, "d" * 64),
        )
        for ordinal, identity, digest in variants:
            with (
                self.subTest(ordinal=ordinal, identity=identity),
                tempfile.TemporaryDirectory() as folder,
            ):
                broker = self.native.SQLiteNativeBroker(Path(folder) / "intents.sqlite")
                try:
                    broker.reserve_tree(self.lease)
                    with self.assertRaises(Refusal):
                        broker.begin(self.lease, ordinal, identity, digest)
                    self.assertFalse(
                        any(leaf["status"] == "dispatching" for leaf in broker.observe()["leaves"])
                    )
                finally:
                    broker.close()

    def test_cold_restart_cannot_take_ownership_or_replay_pending_intent(self):
        self.broker.reserve_tree(self.lease)
        self.begin()
        cold = self.native.SQLiteNativeBroker(self.path)
        try:
            with self.assertRaises(Refusal):
                cold.reserve_tree(self.lease)
            with self.assertRaises(Refusal):
                cold.reserve_tree(dataclasses.replace(self.lease, key="fresh-key"))
            with self.assertRaises(Refusal):
                leaf = self.leaves[0]
                cold.finish(self.lease, 0, leaf.identity, leaf.request_digest, self.cost, b"ack")
            self.assertEqual(cold.observe()["next_ordinal"], 0)
        finally:
            cold.close()

    def test_postbegin_overrun_is_unknown_and_retains_whole_reservation(self):
        self.broker.reserve_tree(self.lease)
        before = self.broker.observe()["reserved"]
        self.begin()
        with self.assertRaises(Refusal):
            self.finish(cost=dataclasses.replace(self.cost, effects=2))
        observed = self.broker.observe()
        self.assertEqual(observed["status"], "unknown")
        self.assertEqual(observed["reserved"], before)
        with self.assertRaises(Refusal):
            self.begin(1)

    def test_explicit_unknown_cannot_refund_release_or_reopen(self):
        self.broker.reserve_tree(self.lease)
        before = self.broker.observe()["reserved"]
        self.begin()
        self.broker.mark_unknown(self.lease, "invented-lost-ack")
        self.assertEqual(self.broker.observe()["status"], "unknown")
        self.assertEqual(self.broker.observe()["reserved"], before)
        with self.assertRaises(Refusal):
            self.finish()
        with self.assertRaises(Refusal):
            self.broker.reserve_tree(dataclasses.replace(self.lease, key="new-key"))

    def test_complete_tree_remains_spent_for_same_or_new_key(self):
        self.broker.reserve_tree(self.lease)
        for ordinal in range(2):
            self.begin(ordinal)
            self.finish(ordinal)
        self.assertEqual(self.broker.observe()["next_ordinal"], 2)
        for lease in (self.lease, dataclasses.replace(self.lease, key="new-key")):
            with self.assertRaises(Refusal):
                self.broker.reserve_tree(lease)

    def test_context_change_cannot_reuse_an_existing_durable_reservation(self):
        self.broker.reserve_tree(self.lease)
        changed = dataclasses.replace(self.lease, context_digest="e" * 64)
        leaf = self.leaves[0]
        with self.assertRaises(Refusal):
            self.broker.begin(changed, 0, leaf.identity, leaf.request_digest)
        self.assertNotEqual(self.native.lease_digest(changed), self.native.lease_digest(self.lease))
        self.assertEqual(self.broker.observe()["next_ordinal"], 0)

    def test_closing_local_owner_does_not_release_durable_campaign(self):
        self.broker.reserve_tree(self.lease)
        self.broker.close()
        with self.assertRaises(Refusal):
            self.begin()
        cold = self.native.SQLiteNativeBroker(self.path)
        try:
            with self.assertRaises(Refusal):
                cold.reserve_tree(self.lease)
        finally:
            cold.close()

    def subtree_receipts(self):
        return tuple(
            self.native.LeafReceipt(
                leaf.ordinal, leaf.identity, leaf.request_digest, self.cost, b"ack"
            )
            for leaf in self.leaves
        )

    def start_subtree(self):
        self.broker.reserve_tree(self.lease)
        first = self.leaves[0]
        self.broker.begin_subtree(self.lease, 0, 1, first.identity, first.request_digest)

    def test_entire_potential_subtree_is_durable_before_any_opaque_effect(self):
        self.start_subtree()
        before = self.broker.observe()
        self.assertEqual(before["status"], "subtree_dispatching")
        self.assertEqual(
            [leaf["status"] for leaf in before["leaves"]], ["dispatching", "dispatching"]
        )
        effects = ["invented-opaque-SDK-effect"]
        self.broker.finish_subtree(self.lease, 0, 1, self.subtree_receipts())
        after = self.broker.observe()
        self.assertEqual((after["status"], after["next_ordinal"]), ("complete", 2))
        self.assertEqual(after["reserved"], before["reserved"])
        self.assertEqual(effects, ["invented-opaque-SDK-effect"])

    def test_subtree_missing_extra_reordered_or_overrun_receipts_settle_nothing(self):
        receipts = self.subtree_receipts()
        variants = (
            receipts[:-1],
            receipts + (receipts[0],),
            tuple(reversed(receipts)),
            (
                receipts[0],
                dataclasses.replace(
                    receipts[1], actual_cost=dataclasses.replace(self.cost, effects=2)
                ),
            ),
        )
        for observations in variants:
            with self.subTest(length=len(observations)), tempfile.TemporaryDirectory() as folder:
                broker = self.native.SQLiteNativeBroker(Path(folder) / "subtree.sqlite")
                try:
                    broker.reserve_tree(self.lease)
                    first = self.leaves[0]
                    broker.begin_subtree(self.lease, 0, 1, first.identity, first.request_digest)
                    before = broker.observe()["reserved"]
                    with self.assertRaises(Refusal):
                        broker.finish_subtree(self.lease, 0, 1, observations)
                    observed = broker.observe()
                    self.assertEqual(observed["status"], "unknown")
                    self.assertEqual(observed["next_ordinal"], 0)
                    self.assertEqual(observed["reserved"], before)
                    self.assertTrue(all(leaf["actual"] is None for leaf in observed["leaves"]))
                finally:
                    broker.close()

    def test_individual_finish_cannot_interleave_an_opaque_subtree(self):
        self.start_subtree()
        before = self.broker.observe()["reserved"]
        with self.assertRaises(Refusal):
            self.finish()
        self.assertEqual(self.broker.observe()["status"], "unknown")
        self.assertEqual(self.broker.observe()["reserved"], before)

    def test_cold_or_new_key_cannot_resume_a_pending_subtree(self):
        self.start_subtree()
        cold = self.native.SQLiteNativeBroker(self.path)
        try:
            with self.assertRaises(Refusal):
                cold.reserve_tree(dataclasses.replace(self.lease, key="new-subtree-key"))
            with self.assertRaises(Refusal):
                cold.finish_subtree(self.lease, 0, 1, self.subtree_receipts())
            self.assertEqual(cold.observe()["next_ordinal"], 0)
        finally:
            cold.close()


if __name__ == "__main__":
    unittest.main()
