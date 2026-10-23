"""Complete NEW synthetic D1 control adapter integration, no native transport."""

import hashlib
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import prospective_control as control
import test_adapter as fixtures

HERE = Path(__file__).resolve().parent
adapter = control.adapter


def read(name):
    return (HERE / name).read_text(encoding="utf-8")


class ControlIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(read("d1-schema.sql"))
        self.db.executescript(read("d1-guards.sql"))
        self.db.execute(json.loads(read("d1-profile-fixture.json"))["providerMetadataDdl"])
        self.pin = hashlib.sha256((HERE / "source-manifest.json").read_bytes()).hexdigest()
        self.source = control.source_descriptor(self.pin)
        self.clock = fixtures.SyntheticClock()
        self.journal = fixtures.SyntheticJournal()
        self.writer = fixtures.SyntheticWriter(self.db, self.journal)
        self.observer = fixtures.SyntheticObserver(self.db)
        self.confirmations = fixtures.SyntheticConfirmations()
        self.window = adapter.Window(0, 100, 200)

    def instance(self, source=None):
        return adapter.Adapter(
            self.writer,
            self.observer,
            self.journal,
            self.clock,
            target_id="synthetic-new-only",
            confirmations=self.confirmations,
            source=self.source if source is None else source,
        )

    def intent(self, key, operation, generation):
        return adapter.Intent(
            key,
            operation,
            generation,
            self.window,
            "synthetic-new-only",
            self.source.candidate,
            transition_limit=3,
        )

    def test_full_schema_source_binding_and_existing_three_transition_lifecycle(self):
        current = self.instance()
        first = self.intent("synthetic-first", "reopen", "1")
        result = current.execute(first)
        self.assertEqual(
            (result.status, result.observed_generation, result.observed_state),
            ("confirmed", "2", "open"),
        )
        self.confirmations.retain_returned("synthetic-receipt-one", first, result)
        self.db.execute("INSERT INTO fga_users VALUES('synthetic-user')")
        close = self.intent("synthetic-close", "close", "2")
        result = current.advance(first, close, "synthetic-receipt-one")
        self.assertEqual(
            (result.status, result.observed_generation, result.observed_state),
            ("confirmed", "3", "closed"),
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "maintenance_closed"):
            self.db.execute("INSERT INTO fga_users VALUES('late')")
        self.confirmations.retain_returned("synthetic-receipt-two", close, result)
        final = self.intent("synthetic-final", "reopen", "3")
        result = self.instance().advance(close, final, "synthetic-receipt-two")
        self.assertEqual(
            (result.status, result.observed_generation, result.observed_state),
            ("confirmed", "4", "open"),
        )
        self.assertEqual(len(self.writer.calls), 3)
        self.assertLessEqual(sum(self.journal.reads.values()), first.read_limit)
        self.assertEqual(self.instance().execute(final).status, "refused")
        self.assertEqual(len(self.writer.calls), 3)

    def test_lost_ack_restart_reconciles_without_replay_and_schema_drift_refuses(self):
        self.writer.lost_ack = True
        intent = self.intent("synthetic-lost", "reopen", "1")
        self.assertEqual(self.instance().execute(intent).status, "unknown")
        self.assertEqual(len(self.writer.calls), 1)
        result = self.instance().reconcile(intent)
        self.assertEqual((result.status, result.observed_generation), ("observed", "2"))
        self.assertEqual(self.instance().execute(intent).status, "refused")
        self.assertEqual(len(self.writer.calls), 1)
        self.db.execute("CREATE TABLE unexpected(value)")
        with self.assertRaisesRegex(adapter.Refusal, "schema_or_guard_mismatch"):
            self.instance().observe(intent, reconciliation=True)
        self.assertEqual(len(self.writer.calls), 1)

    def test_old_candidate_mixed_descriptor_and_source_drift_fail_before_dispatch(self):
        old = adapter.Intent("synthetic-old", "reopen", "1", self.window, "synthetic-new-only")
        self.assertEqual(self.instance().execute(old).status, "refused")
        with self.assertRaises(adapter.Refusal):
            self.instance({"candidate": self.source.candidate, "manifest": self.source.manifest})
        raw_read = Path.read_bytes
        source_path = HERE / "source-manifest.json"

        def altered(path):
            return b"{}" if path == source_path else raw_read(path)

        with patch.object(Path, "read_bytes", altered):
            self.assertEqual(
                self.instance().execute(self.intent("synthetic-drift", "reopen", "1")).status,
                "refused",
            )
        self.assertEqual(len(self.writer.calls), 0)
        self.assertEqual(self.journal.entries, {})

    def test_verified_initial_bytes_are_frozen_without_unchecked_reread(self):
        raw_read = Path.read_bytes
        for filename in ("source-manifest.json", "d1-profile-fixture.json"):
            with self.subTest(filename=filename):
                calls = 0
                watched = HERE / filename

                def changes_after_verified_read(path, watched=watched):
                    nonlocal calls
                    if path == watched:
                        calls += 1
                        if calls > 1:
                            return b"{}"
                    return raw_read(path)

                with patch.object(Path, "read_bytes", changes_after_verified_read):
                    frozen = control.source_descriptor(self.pin)
                    self.assertEqual(calls, 1)
                    self.assertEqual(frozen.candidate, self.source.candidate)
                    self.assertEqual(frozen.manifest, self.source.manifest)
                    with self.assertRaises(adapter.Refusal):
                        frozen.recheck()


if __name__ == "__main__":
    unittest.main()
