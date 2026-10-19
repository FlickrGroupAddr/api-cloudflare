"""Synthetic ports only: in-memory SQL, journal and clock; no network capability."""

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from adapter import (
    SOURCE,
    Adapter,
    CompleteRows,
    ConfirmedReceipt,
    FixedUpdate,
    Intent,
    JournalEntry,
    Observer,
    Refusal,
    Result,
    Window,
    generation,
    verify_source,
)

sys.path.insert(0, str(SOURCE))
from fixture import atomic_fixture_batch, bootstrap_fixture, source_database  # noqa: E402

PUBLIC = Path(os.environ.get("PMB1_PUBLIC_REPOSITORY", str(SOURCE.parents[1])))


class SyntheticClock:
    def __init__(self):
        self.value = 10.0

    def now(self) -> float:
        return self.value


class SyntheticJournal:
    """Not durable: tests only the required port interaction and global counters."""

    def __init__(self):
        self.entries: dict[str, JournalEntry] = {}
        self.reads: dict[str, int] = {}
        self.reconciliations: dict[str, int] = {}
        self.fail_latch = False
        self.ambiguous_latch = False
        self.fail_settle = False
        self.active: str | None = None
        self.lock = threading.Lock()

    def latch(self, intent: Intent, deadline: float) -> bool:
        with self.lock:
            if self.fail_latch:
                raise RuntimeError("synthetic journal unavailable")
            if intent.key in self.entries:
                return False
            # Reservation is permanent in this seam, independent of outcome phase.
            if self.entries:
                return False
            self.entries[intent.key] = JournalEntry(intent, "latched", root_key=intent.key)
            self.active = intent.key
            self.reads[intent.key] = self.reconciliations[intent.key] = 0
            if self.ambiguous_latch:
                raise TimeoutError("synthetic persisted acknowledgment loss")
            return True

    def advance(
        self, predecessor: Intent, successor: Intent, receipt: ConfirmedReceipt, deadline: float
    ) -> bool:
        # One locked operation models the REQUIRED durable transaction, not a
        # qualified backend. There is no release, delete or second latch.
        with self.lock:
            entry = self.entries.get(predecessor.key)
            if entry is None:
                return False
            root = self.entries[entry.root_key].intent
            if (
                self.active != predecessor.key
                or entry.intent != predecessor
                or entry.phase != "confirmed"
                or not entry.dispatch_claimed
                or entry.successor is not None
                or successor.key in self.entries
                or entry.ordinal >= root.transition_limit
                or successor.target_id != predecessor.target_id
                or successor.candidate != predecessor.candidate
                or successor.window != root.window
                or successor.transition_limit != root.transition_limit
                or successor.operation == predecessor.operation
                or successor.expected != predecessor.next_generation
                or receipt.predecessor != predecessor
                or receipt.status != "CONFIRMED"
                or receipt.result.status != "confirmed"
                or any(e.confirmation == receipt.reference for e in self.entries.values())
            ):
                return False
            self.entries[predecessor.key] = replace(
                entry, successor=successor.key, confirmation=receipt.reference
            )
            self.entries[successor.key] = JournalEntry(
                successor, "latched", root_key=entry.root_key, ordinal=entry.ordinal + 1
            )
            self.active = successor.key
            return True

    def get(self, key: str, deadline: float) -> JournalEntry:
        with self.lock:
            return self.entries[key]

    def spend_read(self, key: str, deadline: float) -> bool:
        with self.lock:
            root_key = self.entries[key].root_key
            if self.reads[root_key] >= self.entries[root_key].intent.read_limit:
                return False
            self.reads[root_key] += 1
            return True

    def claim_dispatch(self, key: str, deadline: float) -> bool:
        with self.lock:
            entry = self.entries[key]
            if entry.phase != "latched" or self.active != key or entry.dispatch_claimed:
                return False
            self.entries[key] = replace(entry, phase="dispatching", dispatch_claimed=True)
            return True

    def claim_reconcile(self, key: str, deadline: float) -> bool:
        with self.lock:
            root_key = self.entries[key].root_key
            if not self.entries[key].dispatch_claimed:
                return False
            if self.reconciliations[root_key] >= 2:
                return False
            self.reconciliations[root_key] += 1
            return True

    def settle(self, key: str, phase, deadline: float) -> None:
        with self.lock:
            if self.fail_settle:
                raise TimeoutError("synthetic outcome persistence failure")
            if self.entries[key].successor is not None:
                raise RuntimeError("synthetic consumed history cannot change")
            self.entries[key] = replace(self.entries[key], phase=phase)


class SyntheticConfirmations:
    """Fault-injection model only: no real attestation or independent custody."""

    def __init__(self):
        self.receipts: dict[str, ConfirmedReceipt] = {}
        self.calls: list[str] = []

    def retain_returned(self, reference: str, intent: Intent, result: Result) -> None:
        # This fixture accepts only the actual returned result in positive tests.
        # A real port must independently authenticate that provenance; trusting
        # a caller-constructed dataclass is explicitly NOT a qualified binding.
        if result.status != "confirmed" or result.confirmed_at is None:
            raise Refusal("cannot_retain_unknown_as_confirmed")
        if reference in self.receipts:
            raise Refusal("append_only_confirmation")
        self.receipts[reference] = ConfirmedReceipt(reference, intent, result)

    def read(self, reference: str, deadline: float) -> ConfirmedReceipt:
        self.calls.append(reference)
        return self.receipts[reference]


class SyntheticWriter:
    def __init__(self, db, journal):
        self.db, self.journal = db, journal
        self.calls: list[FixedUpdate] = []
        self.receipt: object = None
        self.lost_ack = False
        self.before: Callable[[], object] = lambda: None
        self.after: Callable[[], object] = lambda: None

    def dispatch(self, update: FixedUpdate, deadline: float) -> object:
        assert any(e.phase == "dispatching" for e in self.journal.entries.values())
        assert update.boundary == "single_fixed_update"
        assert type(update.expected_generation) is str
        self.calls.append(update)
        self.before()
        cursor = self.db.execute(update.sql, {"expected_generation": update.expected_generation})
        self.after()
        if self.lost_ack:
            raise TimeoutError("synthetic commit receipt lost")
        return (
            self.receipt
            if self.receipt is not None
            else {
                "success": True,
                "changes": cursor.rowcount,
            }
        )


class SyntheticObserver:
    def __init__(self, db):
        self.db = db
        self.calls = []
        self.incomplete = False
        self.fail_at = -1
        self.after = lambda: None

    def read(self, sql: str, deadline: float) -> CompleteRows:
        self.calls.append(sql)
        if len(self.calls) == self.fail_at:
            raise TimeoutError("synthetic authoritative read lost")
        cursor = self.db.execute(sql)
        keys = [column[0] for column in cursor.description]
        rows = [dict(zip(keys, row, strict=True)) for row in cursor.fetchall()]
        self.after()
        return CompleteRows(rows, not self.incomplete)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.db = source_database(PUBLIC / "migrations")
        bootstrap_fixture(self.db)
        self.addCleanup(self.db.close)
        self.clock = SyntheticClock()
        self.journal = SyntheticJournal()
        self.confirmations = SyntheticConfirmations()
        self.writer = SyntheticWriter(self.db, self.journal)
        self.observer = SyntheticObserver(self.db)
        self.adapter = self.restart()
        self.window = Window(0, 100, 200)

    def restart(self):
        return Adapter(
            self.writer,
            self.observer,
            self.journal,
            self.clock,
            target_id="synthetic-target",
            confirmations=self.confirmations,
        )

    def open(self):
        result = self.adapter.reopen("open", "1", self.window)
        self.assertEqual(result.status, "confirmed")
        return result

    def test_fixed_sql_complete_readbacks_and_source_pins(self):
        self.assertEqual(len(verify_source()), 11)
        self.open()
        files = verify_source()
        self.assertEqual(self.writer.calls[0].sql, files["reopen.sql"].decode())
        self.assertEqual(self.journal.reads, {"open": 4})
        # A DIFFERENT synthetic target, not a reset/release of the first journal.
        self.setUp()
        self.db.execute(files["reopen.sql"].decode(), {"expected_generation": "1"})
        result = self.adapter.close("close", "2", self.window)
        self.assertEqual(
            (result.status, result.observed_generation, result.observed_state),
            ("confirmed", "3", "closed"),
        )
        self.assertEqual(self.writer.calls[0].sql, files["close.sql"].decode())
        self.assertEqual(
            self.observer.calls, [files[n].decode() for n in ("readback.sql", "schema.sql") * 2]
        )
        self.assertEqual(self.journal.reads, {"close": 4})

    def test_generation_boundary_and_overflow(self):
        for value in (True, 1, 1.0, "0", "01", "+1", "1.0", " 1", "１", "9223372036854775808"):
            with self.subTest(value=value), self.assertRaises(Refusal):
                generation(value)
        self.assertEqual(generation("9223372036854775807"), "9223372036854775807")
        self.assertEqual(
            self.adapter.reopen("max", "9223372036854775807", self.window).status, "refused"
        )
        self.assertEqual(self.writer.calls, [])

    def test_int64_above_javascript_safe_integer_executes_exact_text(self):
        sql = self.db.execute(
            "SELECT sql FROM sqlite_schema WHERE name = 'maintenance_control_transition'"
        ).fetchone()[0]
        self.db.execute("DROP TRIGGER maintenance_control_transition")
        self.db.execute("UPDATE maintenance_control SET generation=9223372036854775806")
        self.db.execute(sql)
        result = self.adapter.reopen("int64", "9223372036854775806", self.window)
        self.assertEqual(
            (result.status, result.observed_generation), ("confirmed", "9223372036854775807")
        )
        self.assertEqual(self.writer.calls[0].expected_generation, "9223372036854775806")

    def test_stale_and_same_state_refuse_before_dispatch(self):
        for key, method, expected in (
            ("same", self.adapter.close, "1"),
            ("stale", self.adapter.reopen, "2"),
        ):
            self.assertEqual(method(key, expected, self.window).status, "refused")
        self.assertEqual(self.writer.calls, [])

    def test_latch_failure_and_lost_latch_ack_never_dispatch(self):
        self.journal.fail_latch = True
        self.assertEqual(self.adapter.reopen("no-latch", "1", self.window).status, "refused")
        self.journal.fail_latch = False
        self.journal.ambiguous_latch = True
        self.assertEqual(self.adapter.reopen("ambiguous", "1", self.window).status, "refused")
        self.journal.ambiguous_latch = False
        self.assertEqual(self.adapter.reopen("ambiguous", "1", self.window).status, "refused")
        self.assertEqual(self.writer.calls, [])

    def test_lost_ack_sticky_across_adapter_restart_and_bounded_reconciliation(self):
        self.writer.lost_ack = True
        intent = Intent("lost", "reopen", "1", self.window, "synthetic-target")
        self.assertEqual(self.adapter.execute(intent).status, "unknown")
        restarted = self.restart()
        self.assertEqual(restarted.execute(intent).status, "refused")
        self.assertEqual(restarted.execute(replace(intent, expected="2")).status, "refused")
        self.assertEqual(restarted.execute(replace(intent, key="new-key")).status, "refused")
        self.assertEqual(restarted.reconcile(intent).status, "observed")
        self.assertEqual(restarted.reconcile(intent).status, "observed")
        self.assertEqual(restarted.reconcile(intent).status, "unknown")
        self.assertEqual(len(self.writer.calls), 1)
        self.assertEqual(self.journal.entries["lost"].phase, "unknown")
        self.assertEqual(self.journal.reads["lost"], 6)

    def test_malformed_and_affected_row_mismatch_receipts_stay_unknown(self):
        for value in (
            {"success": True, "changes": True},
            {"success": 1, "changes": 1},
            {"success": True, "changes": 2},
            {"success": True, "changes": -1},
            {"success": True, "changes": 1.0},
            {"success": True},
            {"success": True, "changes": 1, "echo": "closed"},
            "lost",
        ):
            with self.subTest(value=value):
                # Return to known closed input via test fixture reset.
                self.setUp()
                self.writer.receipt = value
                self.assertEqual(self.adapter.reopen("bad", "1", self.window).status, "unknown")
                self.assertEqual(len(self.writer.calls), 1)

    def test_stale_race_zero_receipt_is_refusal_never_idempotent_success(self):
        sql = verify_source()["reopen.sql"].decode()
        self.writer.before = lambda: self.db.execute(sql, {"expected_generation": "1"})
        result = self.adapter.reopen("race", "1", self.window)
        self.assertEqual((result.status, result.reason), ("refused", "zero_affected_rows"))
        self.assertEqual(self.adapter.reopen("race", "1", self.window).status, "refused")
        self.assertEqual(len(self.writer.calls), 1)

    def test_missing_guard_and_unknown_schema_refuse_pre_dispatch(self):
        self.db.execute('DROP TRIGGER "pmb1_installations_update"')
        self.assertEqual(self.adapter.reopen("drift", "1", self.window).status, "refused")
        self.assertEqual(self.writer.calls, [])

    def test_post_dispatch_guard_drift_and_read_failure_are_unknown(self):
        self.writer.after = lambda: self.db.execute("CREATE TABLE uncovered(value TEXT)")
        self.assertEqual(self.adapter.reopen("drift", "1", self.window).status, "unknown")
        self.assertEqual(len(self.writer.calls), 1)

    def test_complete_readback_and_read_budget_are_mandatory(self):
        self.observer.incomplete = True
        self.assertEqual(self.adapter.reopen("partial", "1", self.window).status, "refused")
        self.assertEqual(self.writer.calls, [])
        # Continue on a different fixture target; refusal does not release custody.
        self.setUp()
        self.observer.incomplete = False
        self.observer.fail_at = len(self.observer.calls) + 3
        self.assertEqual(self.adapter.reopen("failed-post", "1", self.window).status, "unknown")
        intent = self.journal.entries["failed-post"].intent
        self.journal.reads[intent.key] = 8
        calls = len(self.observer.calls)
        self.assertEqual(self.adapter.reconcile(intent).status, "unknown")
        self.assertEqual(len(self.observer.calls), calls)

    def test_deadline_checked_after_reads_and_dispatch_and_never_extended(self):
        self.observer.after = lambda: setattr(self.clock, "value", 101)
        self.assertEqual(self.adapter.reopen("read-timeout", "1", self.window).status, "refused")
        self.assertEqual(self.writer.calls, [])
        # The expired target stays reserved; this is a different fixture target.
        self.setUp()
        self.observer.after = lambda: None
        self.writer.after = lambda: setattr(self.clock, "value", 201)
        self.assertEqual(self.adapter.reopen("write-timeout", "1", self.window).status, "unknown")
        intent = self.journal.entries["write-timeout"].intent
        calls = len(self.observer.calls)
        self.assertEqual(self.adapter.reconcile(intent).status, "unknown")
        self.assertEqual(len(self.observer.calls), calls)
        self.assertEqual(len(self.writer.calls), 1)

    def test_backward_clock_invalid_windows_and_source_drift_refuse(self):
        self.adapter.last_time = 20
        self.assertEqual(self.adapter.reopen("clock", "1", self.window).status, "refused")
        self.assertEqual(self.adapter.reopen("long", "1", Window(0, 1, 301)).status, "refused")
        with patch("adapter.verify_source", side_effect=Refusal("source_pin_mismatch")):
            self.assertEqual(self.adapter.reopen("pin", "1", self.window).status, "refused")
        self.assertEqual(self.writer.calls, [])

    def test_external_journal_outcome_failure_never_claims_confirmed(self):
        self.journal.fail_settle = True
        self.assertEqual(self.adapter.reopen("journal-outcome", "1", self.window).status, "unknown")
        self.assertEqual(len(self.writer.calls), 1)
        self.assertEqual(self.adapter.reopen("journal-outcome", "1", self.window).status, "refused")

    def test_ordinary_guards_and_batch_rollback_survive_adapter_transitions(self):
        self.db.execute(verify_source()["reopen.sql"].decode(), {"expected_generation": "1"})
        self.db.execute("CREATE TEMP TABLE transaction_witness(value INTEGER)")
        # Direct/indirect/domain behavior is additionally covered by immutable #0185 suite.
        self.adapter.close("close", "2", self.window)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "maintenance_closed"):
            atomic_fixture_batch(
                self.db,
                [
                    ("INSERT INTO transaction_witness VALUES (1)", ()),
                    ("INSERT INTO installations(installation_id) VALUES ('synthetic')", ()),
                ],
            )
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM transaction_witness").fetchone()[0], 0
        )
        self.assertEqual(len(self.writer.calls), 1)

    def test_writer_cannot_be_its_own_readback_port(self):
        with self.assertRaises(Refusal):
            Adapter(
                self.writer,
                cast(Observer, self.writer),
                self.journal,
                self.clock,
                target_id="synthetic-target",
            )

    def test_success_receipt_cannot_replace_independent_target_readback(self):
        with patch.object(self.writer, "dispatch", return_value={"success": True, "changes": 1}):
            result = self.adapter.reopen("receipt-echo", "1", self.window)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(len(self.observer.calls), 4)
        self.assertEqual(
            self.db.execute("SELECT state FROM maintenance_control").fetchone()[0], "closed"
        )

    def test_real_byte_pin_mutation_refuses_without_dispatch(self):
        files = verify_source()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in files.items():
                (root / name).write_bytes(value)
            (root / "close.sql").write_bytes(files["close.sql"] + b"\n-- changed\n")
            with patch("adapter.SOURCE", root):
                self.assertEqual(
                    self.adapter.reopen("changed-pin", "1", self.window).status, "refused"
                )
        self.assertEqual(self.writer.calls, [])

    def test_reconciliation_cannot_change_intent_or_window(self):
        self.writer.lost_ack = True
        intent = Intent("uncertain", "reopen", "1", self.window, "synthetic-target")
        self.assertEqual(self.adapter.execute(intent).status, "unknown")
        count = len(self.observer.calls)
        for changed in (
            replace(intent, expected="2"),
            replace(intent, operation="close"),
            replace(intent, window=Window(0, 100, 201)),
        ):
            self.assertEqual(self.adapter.reconcile(changed).status, "unknown")
        self.assertEqual(len(self.observer.calls), count)
        self.assertEqual(len(self.writer.calls), 1)

    def test_ambiguous_dispatch_claim_consumes_intent_without_sending(self):
        claim = self.journal.claim_dispatch

        def claim_without_ack(key: str, deadline: float) -> bool:
            claim(key, deadline)
            raise TimeoutError("synthetic durable claim lost acknowledgment")

        intent = Intent("claim", "reopen", "1", self.window, "synthetic-target")
        with patch.object(self.journal, "claim_dispatch", side_effect=claim_without_ack):
            self.assertEqual(self.adapter.execute(intent).status, "unknown")
        self.assertEqual(self.writer.calls, [])
        self.assertEqual(self.adapter.execute(replace(intent, key="other")).status, "refused")
        self.assertEqual(self.adapter.reconcile(intent).status, "unknown")

    def test_persisted_outcomes_with_lost_or_late_ack_never_release_target(self):
        for phase in ("confirmed", "refused", "unknown"):
            for lost in (False, True):
                with self.subTest(phase=phase, lost_ack=lost):
                    self.setUp()  # Separate target for each fault case.
                    if phase == "refused":
                        sql = verify_source()["reopen.sql"].decode()
                        self.writer.before = lambda sql=sql: self.db.execute(
                            sql, {"expected_generation": "1"}
                        )
                    elif phase == "unknown":
                        self.writer.receipt = {"success": True, "changes": 2}
                    settle = self.journal.settle

                    def persist_without_timely_ack(
                        key: str, outcome, deadline: float, save=settle, lose_ack=lost
                    ) -> None:
                        save(key, outcome, deadline)
                        self.clock.value = 201
                        if lose_ack:
                            raise TimeoutError("synthetic persisted outcome acknowledgment lost")

                    with patch.object(
                        self.journal, "settle", side_effect=persist_without_timely_ack
                    ):
                        result = self.adapter.reopen("first", "1", self.window)
                    self.assertEqual(result.status, "unknown")
                    self.assertEqual(self.journal.entries["first"].phase, phase)
                    self.clock.value = 210
                    restarted = self.restart()
                    fresh = Window(200, 250, 300)
                    self.assertEqual(restarted.close("first", "2", fresh).status, "refused")
                    self.assertEqual(restarted.close("next", "2", fresh).status, "refused")
                    self.assertEqual(len(self.writer.calls), 1)

    def test_even_confirmed_result_cannot_implicitly_advance_reservation(self):
        self.open()
        restarted = self.restart()
        self.assertEqual(restarted.close("next", "2", self.window).status, "refused")
        self.assertEqual(self.journal.entries["open"].phase, "confirmed")
        self.assertEqual(len(self.writer.calls), 1)

    def test_confirmed_persistence_and_failed_unknown_ack_reconcile_without_release(self):
        settle = self.journal.settle

        def settle_without_ack(key: str, outcome, deadline: float) -> None:
            if outcome == "confirmed":
                settle(key, outcome, deadline)
            raise TimeoutError("synthetic terminal outcome acknowledgment unavailable")

        intent = Intent("persisted", "reopen", "1", self.window, "synthetic-target")
        with patch.object(self.journal, "settle", side_effect=settle_without_ack):
            self.assertEqual(self.adapter.execute(intent).status, "unknown")
        self.assertEqual(self.journal.entries[intent.key].phase, "confirmed")
        restarted = self.restart()
        self.assertEqual(restarted.reconcile(intent).status, "observed")
        self.assertEqual(restarted.close("next", "2", self.window).status, "refused")
        self.assertEqual(len(self.writer.calls), 1)

    def lifecycle(self):
        # Synthetic fixture starts closed. Arrange an independently known open
        # baseline before this target's lifecycle reservation, using fixed SQL.
        self.db.execute(verify_source()["reopen.sql"].decode(), {"expected_generation": "1"})
        predecessor = Intent(
            "close-root", "close", "2", self.window, "synthetic-target", transition_limit=2
        )
        result = self.adapter.execute(predecessor)
        self.assertEqual(result.status, "confirmed")
        self.confirmations.retain_returned("retained-close", predecessor, result)
        successor = replace(predecessor, key="reopen-successor", operation="reopen", expected="3")
        return predecessor, successor, self.confirmations.receipts["retained-close"]

    def test_explicit_advancement_preserves_custody_history_sql_and_full_readbacks(self):
        predecessor, successor, receipt = self.lifecycle()
        before = self.journal.entries[predecessor.key]
        result = self.restart().advance(predecessor, successor, receipt.reference)
        self.assertEqual(
            (result.status, result.observed_generation, result.observed_state),
            ("confirmed", "4", "open"),
        )
        old = self.journal.entries[predecessor.key]
        self.assertEqual(old.intent, before.intent)
        self.assertEqual((old.phase, old.dispatch_claimed), ("confirmed", True))
        self.assertEqual((old.successor, old.confirmation), (successor.key, receipt.reference))
        self.assertEqual(self.journal.active, successor.key)
        self.assertEqual(self.journal.entries[successor.key].ordinal, 2)
        self.assertEqual(self.journal.reads, {predecessor.key: 8})
        self.assertEqual(self.journal.reconciliations, {predecessor.key: 0})
        files = verify_source()
        self.assertEqual(
            [u.sql for u in self.writer.calls],
            [files[n].decode() for n in ("close.sql", "reopen.sql")],
        )
        self.assertEqual([u.expected_generation for u in self.writer.calls], ["2", "3"])
        self.assertEqual(
            self.observer.calls, [files[n].decode() for n in ("readback.sql", "schema.sql") * 4]
        )
        self.assertEqual(
            self.adapter.advance(predecessor, successor, receipt.reference).status, "refused"
        )
        self.assertEqual(self.adapter.execute(replace(successor, key="fresh")).status, "refused")
        self.confirmations.retain_returned("retained-reopen", successor, result)
        third = replace(successor, key="third", operation="close", expected="4")
        self.assertEqual(
            self.adapter.advance(successor, third, "retained-reopen").status, "refused"
        )
        self.assertEqual(len(self.writer.calls), 2)
        with self.assertRaises(RuntimeError):
            self.journal.settle(predecessor.key, "unknown", 100)

    def test_phase_or_assertion_without_independent_receipt_never_advances(self):
        predecessor, successor, receipt = self.lifecycle()
        self.confirmations.receipts.clear()
        self.assertEqual(
            self.adapter.advance(predecessor, successor, receipt.reference).status, "refused"
        )
        self.assertEqual(
            self.adapter.advance(predecessor, successor, cast(str, receipt)).status, "refused"
        )
        self.adapter.confirmations = None
        self.assertEqual(
            self.adapter.advance(predecessor, successor, receipt.reference).status, "refused"
        )
        self.assertEqual(len(self.writer.calls), 1)
        self.assertEqual(self.journal.active, predecessor.key)
        with self.assertRaises(Refusal):
            Adapter(
                self.writer,
                self.observer,
                self.journal,
                self.clock,
                target_id="synthetic-target",
                confirmations=cast(Any, self.journal),
            )

    def test_unknown_lost_late_and_refused_returned_results_cannot_supply_confirmation(self):
        for fault in ("provider_ack", "settle_ack", "late_settle", "zero", "malformed", "readback"):
            with self.subTest(fault=fault):
                self.setUp()
                intent = Intent(
                    "first", "reopen", "1", self.window, "synthetic-target", transition_limit=2
                )
                successor = replace(intent, key="next", operation="close", expected="2")
                if fault == "provider_ack":
                    self.writer.lost_ack = True
                elif fault == "zero":
                    self.writer.receipt = {"success": True, "changes": 0}
                elif fault == "malformed":
                    self.writer.receipt = {"success": True, "changes": True}
                elif fault == "readback":
                    self.observer.fail_at = 3
                settle = self.journal.settle

                def fault_settle(key, phase, deadline, save=settle, fault=fault):
                    save(key, phase, deadline)
                    if phase == "confirmed" and fault == "settle_ack":
                        raise TimeoutError("synthetic final ack lost after persistence")
                    if phase == "confirmed" and fault == "late_settle":
                        self.clock.value = 101

                with patch.object(self.journal, "settle", side_effect=fault_settle):
                    result = self.adapter.execute(intent)
                self.assertNotEqual(result.status, "confirmed")
                self.assertIsNone(result.confirmed_at)
                with self.assertRaises(Refusal):
                    self.confirmations.retain_returned("no-receipt", intent, result)
                self.clock.value = 10
                self.assertEqual(
                    self.restart().advance(intent, successor, "no-receipt").status, "refused"
                )
                self.assertEqual(len(self.writer.calls), 1)

    def test_retained_receipt_requires_exact_confirmed_terminal_result(self):
        predecessor, successor, receipt = self.lifecycle()
        for bad in (
            None,
            {"status": "CONFIRMED"},
            replace(receipt, reference="different"),
            replace(receipt, predecessor=replace(predecessor, target_id="other")),
            replace(receipt, predecessor=replace(predecessor, candidate="wrong")),
            replace(receipt, predecessor=replace(predecessor, key="other")),
            replace(receipt, status=cast(Any, "UNKNOWN")),
            *(
                replace(receipt, result=replace(receipt.result, **change))
                for change in (
                    {"status": "unknown"},
                    {"reason": "phase_only"},
                    {"observed_generation": "4"},
                    {"observed_state": "open"},
                    {"confirmed_at": None},
                    {"confirmed_at": True},
                    {"confirmed_at": float("nan")},
                    {"confirmed_at": 100},
                    {"confirmed_at": 11},
                    {"confirmed_at": -1},
                )
            ),
        ):
            with self.subTest(receipt=bad):
                self.confirmations.receipts[receipt.reference] = cast(ConfirmedReceipt, bad)
                self.assertEqual(
                    self.adapter.advance(predecessor, successor, receipt.reference).status,
                    "refused",
                )
                self.assertEqual(self.journal.active, predecessor.key)
        self.assertEqual(len(self.writer.calls), 1)

    def test_wrong_binding_predecessor_or_successor_refuses_without_reservation(self):
        predecessor, successor, receipt = self.lifecycle()
        for changed in (
            replace(successor, target_id="other"),
            replace(successor, candidate="other"),
            replace(successor, key=predecessor.key),
            replace(successor, operation="close"),
            replace(successor, expected="4"),
            replace(successor, transition_limit=1),
            replace(successor, window=Window(0, 101, 200)),
            replace(successor, window=Window(0, 100, 201)),
        ):
            self.assertEqual(
                self.adapter.advance(predecessor, changed, receipt.reference).status, "refused"
            )
        for changed in (replace(predecessor, key="other"), replace(predecessor, expected="1")):
            self.assertEqual(
                self.adapter.advance(changed, successor, receipt.reference).status, "refused"
            )
        self.assertEqual(len(self.writer.calls), 1)
        self.assertEqual(self.journal.active, predecessor.key)

    def test_reservation_faults_never_dispatch_or_resume_unacknowledged_successor(self):
        for fault in ("before", "after", "late", "malformed", "crash"):
            with self.subTest(fault=fault):
                self.setUp()
                predecessor, successor, receipt = self.lifecycle()
                advance = self.journal.advance

                def fault_advance(
                    prior, next_intent, confirmation, deadline, fault=fault, save=advance
                ):
                    if fault == "before":
                        raise TimeoutError("synthetic failure before persistence")
                    save(prior, next_intent, confirmation, deadline)
                    if fault == "crash":
                        raise KeyboardInterrupt("synthetic process crash")
                    if fault == "after":
                        raise TimeoutError("synthetic lost CAS acknowledgement")
                    if fault == "late":
                        self.clock.value = 101
                    return 1 if fault == "malformed" else True

                with patch.object(self.journal, "advance", side_effect=fault_advance):
                    if fault == "crash":
                        with self.assertRaises(KeyboardInterrupt):
                            self.adapter.advance(predecessor, successor, receipt.reference)
                    else:
                        self.assertEqual(
                            self.adapter.advance(predecessor, successor, receipt.reference).status,
                            "refused",
                        )
                self.assertEqual(len(self.writer.calls), 1)
                self.clock.value = 10
                restart = self.restart()
                self.assertEqual(restart.execute(successor).status, "refused")
                self.assertEqual(
                    restart.execute(replace(successor, key="bypass")).status, "refused"
                )
                if fault != "before":
                    self.assertEqual(
                        restart.advance(predecessor, successor, receipt.reference).status, "refused"
                    )
                    self.assertEqual(self.journal.active, successor.key)
                    self.assertEqual(self.journal.entries[successor.key].phase, "latched")
                else:
                    self.assertEqual(self.journal.active, predecessor.key)
                self.assertEqual(len(self.writer.calls), 1)

    def test_concurrent_different_and_duplicate_successors_have_one_atomic_winner(self):
        for duplicate in (False, True):
            self.setUp()
            predecessor, successor, receipt = self.lifecycle()
            barrier = threading.Barrier(3)
            results = []

            def reserve(
                intent, barrier=barrier, results=results, prior=predecessor, receipt=receipt
            ):
                barrier.wait()
                results.append(self.journal.advance(prior, intent, receipt, 100))

            rival = successor if duplicate else replace(successor, key="rival")
            threads = [threading.Thread(target=reserve, args=(i,)) for i in (successor, rival)]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(results), [False, True])
            self.assertEqual(len(self.journal.entries), 2)
            self.assertEqual(self.journal.entries[predecessor.key].successor, self.journal.active)
            # A crash after reservation is deliberately not a resume mechanism.
            self.assertEqual(
                self.restart().advance(predecessor, successor, receipt.reference).status, "refused"
            )
            self.assertEqual(len(self.writer.calls), 1)

    def test_lifecycle_headroom_budget_and_deadlines_cannot_reset_at_advancement(self):
        for limit in (0, True, 4):
            intent = Intent(
                "invalid", "reopen", "1", self.window, "synthetic-target", transition_limit=limit
            )
            self.assertEqual(self.adapter.execute(intent).status, "refused")
        intent = Intent(
            "headroom",
            "reopen",
            "9223372036854775806",
            self.window,
            "synthetic-target",
            transition_limit=2,
        )
        self.assertEqual(self.adapter.execute(intent).status, "refused")
        self.assertEqual(self.journal.entries, {})
        predecessor, successor, receipt = self.lifecycle()
        self.journal.reads[predecessor.key] = 16
        self.journal.reconciliations[predecessor.key] = 2
        calls = len(self.observer.calls)
        self.assertEqual(
            self.adapter.advance(predecessor, successor, receipt.reference).status, "refused"
        )
        self.assertEqual(len(self.observer.calls), calls)
        self.assertEqual(self.journal.reads, {predecessor.key: 16})
        self.assertEqual(self.journal.reconciliations, {predecessor.key: 2})
        self.assertEqual(len(self.writer.calls), 1)

    def test_late_or_failed_confirmation_read_cannot_reserve_successor(self):
        predecessor, successor, receipt = self.lifecycle()
        with patch.object(self.confirmations, "read", side_effect=TimeoutError):
            self.assertEqual(
                self.adapter.advance(predecessor, successor, receipt.reference).status, "refused"
            )

        def late_read(reference, deadline):
            self.clock.value = 101
            return receipt

        with patch.object(self.confirmations, "read", side_effect=late_read):
            self.assertEqual(
                self.adapter.advance(predecessor, successor, receipt.reference).status, "refused"
            )
        self.assertEqual(self.journal.active, predecessor.key)
        self.assertEqual(len(self.writer.calls), 1)

    def test_crash_after_mutation_or_final_persistence_cannot_mint_confirmation(self):
        for point in ("writer", "settle"):
            self.setUp()
            intent = Intent(
                "crashed", "reopen", "1", self.window, "synthetic-target", transition_limit=2
            )
            successor = replace(intent, key="next", operation="close", expected="2")

            def crash():
                raise KeyboardInterrupt("synthetic process crash")

            if point == "writer":
                self.writer.after = crash
                with self.assertRaises(KeyboardInterrupt):
                    self.adapter.execute(intent)
            else:
                settle = self.journal.settle

                def crash_settle(key, phase, deadline, save=settle):
                    save(key, phase, deadline)
                    crash()

                with patch.object(self.journal, "settle", side_effect=crash_settle):
                    with self.assertRaises(KeyboardInterrupt):
                        self.adapter.execute(intent)
            restart = self.restart()
            self.assertEqual(restart.execute(replace(intent, key="fresh")).status, "refused")
            self.assertEqual(restart.advance(intent, successor, "missing").status, "refused")
            self.assertEqual(len(self.writer.calls), 1)
            self.assertEqual(self.journal.active, intent.key)

    def test_successor_ack_loss_and_restart_remain_unknown_with_shared_observation_bounds(self):
        predecessor, successor, receipt = self.lifecycle()
        self.journal.reconciliations[predecessor.key] = 1
        self.writer.lost_ack = True
        self.assertEqual(
            self.adapter.advance(predecessor, successor, receipt.reference).status, "unknown"
        )
        restart = self.restart()
        self.assertEqual(restart.reconcile(successor).status, "observed")
        self.assertEqual(restart.reconcile(successor).status, "unknown")
        self.assertEqual(self.journal.reconciliations, {predecessor.key: 2})
        self.assertEqual(self.journal.reads, {predecessor.key: 8})
        self.assertEqual(restart.execute(replace(successor, key="fresh")).status, "refused")
        self.assertEqual(len(self.writer.calls), 2)

    def bootstrap_campaign_prefix(self):
        first = Intent(
            "bootstrap-open", "reopen", "1", self.window, "synthetic-target", transition_limit=3
        )
        result = self.adapter.execute(first)
        self.assertEqual(result.status, "confirmed")
        self.confirmations.retain_returned("retained-bootstrap-open", first, result)
        second = replace(first, key="campaign-close", operation="close", expected="2")
        result = self.adapter.advance(first, second, "retained-bootstrap-open")
        self.assertEqual(result.status, "confirmed")
        self.confirmations.retain_returned("retained-campaign-close", second, result)
        third = replace(second, key="authorized-final-open", operation="reopen", expected="3")
        return first, second, third

    def test_bootstrap_reopen_close_final_reopen_and_terminal_exhaustion(self):
        first, second, third = self.bootstrap_campaign_prefix()
        result = self.restart().advance(second, third, "retained-campaign-close")
        self.assertEqual(
            (result.status, result.observed_generation, result.observed_state),
            ("confirmed", "4", "open"),
        )
        self.assertEqual(self.journal.active, third.key)
        self.assertEqual(self.journal.entries[first.key].successor, second.key)
        self.assertEqual(self.journal.entries[second.key].successor, third.key)
        self.assertEqual(self.journal.entries[third.key].ordinal, 3)
        self.assertEqual(self.journal.reads, {first.key: 12})
        self.assertEqual(self.journal.reconciliations, {first.key: 0})
        files = verify_source()
        self.assertEqual(
            [u.sql for u in self.writer.calls],
            [files[n].decode() for n in ("reopen.sql", "close.sql", "reopen.sql")],
        )
        self.assertEqual([u.expected_generation for u in self.writer.calls], ["1", "2", "3"])
        self.assertEqual(
            self.observer.calls, [files[n].decode() for n in ("readback.sql", "schema.sql") * 6]
        )
        self.confirmations.retain_returned("retained-final-open", third, result)
        fourth = replace(third, key="exhausted", operation="close", expected="4")
        self.assertEqual(
            self.adapter.advance(third, fourth, "retained-final-open").status, "refused"
        )
        self.assertEqual(self.journal.reads, {first.key: 12})
        self.assertEqual(len(self.writer.calls), 3)

    def test_third_transition_ack_loss_and_budget_refusal_preserve_custody(self):
        for fault in ("provider_ack", "final_ack", "budget"):
            with self.subTest(fault=fault):
                self.setUp()
                first, second, third = self.bootstrap_campaign_prefix()
                if fault == "provider_ack":
                    self.writer.lost_ack = True
                elif fault == "budget":
                    self.journal.reads[first.key] = first.read_limit
                settle = self.journal.settle

                def uncertain_settle(key, phase, deadline, save=settle, fault=fault):
                    if fault == "final_ack":
                        if phase == "confirmed":
                            save(key, phase, deadline)
                        raise TimeoutError("synthetic final campaign acknowledgment lost")
                    save(key, phase, deadline)

                with patch.object(self.journal, "settle", side_effect=uncertain_settle):
                    result = self.adapter.advance(second, third, "retained-campaign-close")
                self.assertEqual(result.status, "refused" if fault == "budget" else "unknown")
                self.assertIsNone(result.confirmed_at)
                with self.assertRaises(Refusal):
                    self.confirmations.retain_returned("missing-final", third, result)
                restart = self.restart()
                self.assertEqual(restart.execute(replace(third, key="fresh")).status, "refused")
                self.assertEqual(
                    restart.advance(second, third, "retained-campaign-close").status, "refused"
                )
                self.assertEqual(self.journal.active, third.key)
                self.assertEqual(self.journal.entries[second.key].successor, third.key)
                self.assertEqual(len(self.writer.calls), 2 if fault == "budget" else 3)
                if fault == "budget":
                    self.assertEqual(self.journal.reads, {first.key: 16})
                else:
                    self.assertEqual(restart.reconcile(third).status, "observed")
                    self.assertEqual(restart.reconcile(third).status, "observed")
                    self.assertEqual(restart.reconcile(third).status, "unknown")
                    self.assertLessEqual(self.journal.reads[first.key], 16)
                    self.assertEqual(self.journal.reconciliations, {first.key: 2})

    def test_three_transition_generation_headroom_is_reserved_before_latch(self):
        intent = Intent(
            "headroom-three",
            "reopen",
            "9223372036854775805",
            self.window,
            "synthetic-target",
            transition_limit=3,
        )
        self.assertEqual(self.adapter.execute(intent).status, "refused")
        self.assertEqual(self.journal.entries, {})
        self.assertEqual(self.writer.calls, [])
        trigger = self.db.execute(
            "SELECT sql FROM sqlite_schema WHERE name = 'maintenance_control_transition'"
        ).fetchone()[0]
        self.db.execute("DROP TRIGGER maintenance_control_transition")
        self.db.execute("UPDATE maintenance_control SET generation=9223372036854775804")
        self.db.execute(trigger)
        current = replace(intent, expected="9223372036854775804")
        result = self.adapter.execute(current)
        for key, operation in (("last-close", "close"), ("last-open", "reopen")):
            self.assertEqual(result.status, "confirmed")
            self.confirmations.retain_returned(key, current, result)
            successor = replace(
                current, key=key, operation=operation, expected=current.next_generation
            )
            result = self.adapter.advance(current, successor, key)
            current = successor
        self.assertEqual(
            (result.status, result.observed_generation), ("confirmed", "9223372036854775807")
        )
        self.assertEqual(
            [u.expected_generation for u in self.writer.calls],
            ["9223372036854775804", "9223372036854775805", "9223372036854775806"],
        )


if __name__ == "__main__":
    unittest.main()
