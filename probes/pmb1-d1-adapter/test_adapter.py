"""Synthetic ports only: in-memory SQL, journal and clock; no network capability."""

import os
import sqlite3
import sys
import tempfile
import unittest
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import patch

from adapter import (
    SOURCE,
    Adapter,
    CompleteRows,
    FixedUpdate,
    Intent,
    JournalEntry,
    Observer,
    Refusal,
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

    def latch(self, intent: Intent, deadline: float) -> bool:
        if self.fail_latch:
            raise RuntimeError("synthetic journal unavailable")
        if intent.key in self.entries:
            return False
        # Reservation is permanent in this seam, independent of outcome phase.
        if self.entries:
            return False
        self.entries[intent.key] = JournalEntry(intent, "latched")
        self.reads[intent.key] = self.reconciliations[intent.key] = 0
        if self.ambiguous_latch:
            raise TimeoutError("synthetic persisted acknowledgment loss")
        return True

    def get(self, key: str, deadline: float) -> JournalEntry:
        return self.entries[key]

    def spend_read(self, key: str, deadline: float) -> bool:
        if self.reads[key] >= 8:
            return False
        self.reads[key] += 1
        return True

    def claim_dispatch(self, key: str, deadline: float) -> bool:
        entry = self.entries[key]
        if entry.phase != "latched":
            return False
        self.entries[key] = replace(entry, phase="dispatching", dispatch_claimed=True)
        return True

    def claim_reconcile(self, key: str, deadline: float) -> bool:
        if not self.entries[key].dispatch_claimed:
            return False
        if self.reconciliations[key] >= 2:
            return False
        self.reconciliations[key] += 1
        return True

    def settle(self, key: str, phase, deadline: float) -> None:
        if self.fail_settle:
            raise TimeoutError("synthetic outcome persistence failure")
        self.entries[key] = replace(self.entries[key], phase=phase)


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
        self.writer = SyntheticWriter(self.db, self.journal)
        self.observer = SyntheticObserver(self.db)
        self.adapter = Adapter(self.writer, self.observer, self.journal, self.clock)
        self.window = Window(0, 100, 200)

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
        intent = Intent("lost", "reopen", "1", self.window)
        self.assertEqual(self.adapter.execute(intent).status, "unknown")
        restarted = Adapter(self.writer, self.observer, self.journal, self.clock)
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
            Adapter(self.writer, cast(Observer, self.writer), self.journal, self.clock)

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
        intent = Intent("uncertain", "reopen", "1", self.window)
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

        intent = Intent("claim", "reopen", "1", self.window)
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
                    restarted = Adapter(self.writer, self.observer, self.journal, self.clock)
                    fresh = Window(200, 250, 300)
                    self.assertEqual(restarted.close("first", "2", fresh).status, "refused")
                    self.assertEqual(restarted.close("next", "2", fresh).status, "refused")
                    self.assertEqual(len(self.writer.calls), 1)

    def test_even_confirmed_result_cannot_implicitly_advance_reservation(self):
        self.open()
        restarted = Adapter(self.writer, self.observer, self.journal, self.clock)
        self.assertEqual(restarted.close("next", "2", self.window).status, "refused")
        self.assertEqual(self.journal.entries["open"].phase, "confirmed")
        self.assertEqual(len(self.writer.calls), 1)

    def test_confirmed_persistence_and_failed_unknown_ack_reconcile_without_release(self):
        settle = self.journal.settle

        def settle_without_ack(key: str, outcome, deadline: float) -> None:
            if outcome == "confirmed":
                settle(key, outcome, deadline)
            raise TimeoutError("synthetic terminal outcome acknowledgment unavailable")

        intent = Intent("persisted", "reopen", "1", self.window)
        with patch.object(self.journal, "settle", side_effect=settle_without_ack):
            self.assertEqual(self.adapter.execute(intent).status, "unknown")
        self.assertEqual(self.journal.entries[intent.key].phase, "confirmed")
        restarted = Adapter(self.writer, self.observer, self.journal, self.clock)
        self.assertEqual(restarted.reconcile(intent).status, "observed")
        self.assertEqual(restarted.close("next", "2", self.window).status, "refused")
        self.assertEqual(len(self.writer.calls), 1)


if __name__ == "__main__":
    unittest.main()
