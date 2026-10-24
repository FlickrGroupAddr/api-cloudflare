"""Independent complete miniature state and semantic inventory regressions.

MIT License; copyright 2026 Terry Ott. Full65 fit remains a required refusal.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mechanism import MechanismAdapter, MechanismOracle, make_packet, source_pin
from runner import RUN_LIMIT, Cost, Refusal, Runner, SQLiteJournal
from test_runner_faults import Clock


class AcceptanceRegressions(unittest.TestCase):
    def test_inherited_oracle_source_is_in_the_executable_source_pin_closure(self):
        original = Path.read_bytes
        before = source_pin()

        def changed(path):
            raw = original(path)
            return (
                raw + b"\n# synthetic oracle-source fault\n"
                if path.name == "full_state_oracle.py"
                else raw
            )

        # Synthetic read interception only; no source file or private data changes.
        with patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(
                source_pin(), before, "inherited oracle code must participate in source binding"
            )

    def execute(self, number, after=None, before=None):
        clock = Clock()
        packet = make_packet(number)
        adapter = MechanismAdapter(packet, clock)
        oracle = MechanismOracle(packet)
        observed = []
        original = adapter.invoke

        def invoke(operation, deadline):
            if before:
                before(adapter, operation)
            receipt = original(operation, deadline)
            observed.append((operation, receipt))
            if after:
                after(adapter, operation, receipt)
            return receipt

        adapter.invoke = invoke
        try:
            with tempfile.TemporaryDirectory() as directory:
                result = Runner(
                    packet,
                    SQLiteJournal(Path(directory) / "journal.sqlite"),
                    {"mechanism": adapter},
                    clock,
                    source_pin,
                    oracle,
                ).run()
            return result, observed
        finally:
            adapter.close()

    def test_every_actual_receipt_tree_fits_its_declared_sql_effect_budget(self):
        for number in range(1, 13):
            with self.subTest(number=number):
                _, observed = self.execute(number)
                aggregate = Cost()
                for operation, receipt in observed:
                    self.assertTrue(receipt.actual_cost.within(operation.cost))
                    self.assertLessEqual(receipt.actual_cost.sql_statements, 8)
                    aggregate = aggregate.plus(receipt.actual_cost)
                self.assertTrue(aggregate.within(RUN_LIMIT))

    def test_setup_is_manifested_before_first_close_not_hidden_in_constructor(self):
        packet = make_packet(1)
        adapter = MechanismAdapter(packet, Clock())
        try:
            self.assertEqual(
                adapter.db.execute("SELECT count(*) FROM sqlite_schema").fetchone(), (0,)
            )
            setup = [o for o in packet.cases[0].operations if o.action.startswith("sqlite.setup.")]
            self.assertTrue(setup)
            self.assertTrue(all(o.cost.requests == 1 and o.cost.sql_statements > 0 for o in setup))
        finally:
            adapter.close()

    def test_postrestore_both_delayed_generations_actually_attempt_guarded_writes(self):
        result, observed = self.execute(7)
        self.assertEqual(result.status, "mechanism_complete")
        delayed = [(o, r) for o, r in observed if o.action.startswith("sqlite.restored-delayed.")]
        self.assertEqual(len(delayed), 2)
        self.assertTrue(all(r.actual_cost.sql_statements > 0 for _, r in delayed))
        self.assertTrue(all(r.actual_cost.mutations == 1 for _, r in delayed))

    def test_upsert_replace_cascade_and_side_effect_variants_are_real_operations(self):
        for number, minimum in ((3, 3), (8, 4), (9, 5)):
            with self.subTest(number=number):
                result, observed = self.execute(number)
                self.assertEqual(result.status, "mechanism_complete")
                challenges = [(o, r) for o, r in observed if o.stage == "challenge"]
                self.assertGreaterEqual(len(challenges), minimum)
                self.assertTrue(all(r.actual_cost.sql_statements >= 1 for _, r in challenges))
                self.assertTrue(all(r.actual_cost.effects == 0 for _, r in challenges))

    def test_unselected_terminal_variants_cannot_borrow_the_partial_output_allocation(self):
        for interruption in (
            "unknown_restore",
            "unknown_cleanup",
            "timeout",
            "malformed",
            "truncated",
            "unsupported",
        ):
            with self.subTest(interruption=interruption), self.assertRaises(Refusal):
                make_packet(12, interruption=interruption)

    def test_hidden_rowid_drift_cannot_pass_complete_miniature_equality(self):
        mutated = [False]

        def change_rowid(adapter, operation):
            if operation.stage == "close" and not mutated[0]:
                # Test fault while guard is still open. Text primary key does
                # not alias SQLite's hidden rowid. All visible values stay equal.
                adapter.db.execute("UPDATE object_kv SET rowid=77 WHERE id='binary'")
                adapter.db.commit()
                mutated[0] = True

        result, _ = self.execute(1, before=change_rowid)
        self.assertTrue(mutated[0])
        self.assertEqual(
            result.status,
            "unknown",
            "complete equality must retain hidden rowid, not only SELECT * values",
        )


if __name__ == "__main__":
    unittest.main()
