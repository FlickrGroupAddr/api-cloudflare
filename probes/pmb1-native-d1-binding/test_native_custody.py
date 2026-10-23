"""Temporary synthetic native-interface tests; no actual credentials/native proof."""

import json
import sqlite3
import threading
import types
import unittest
from contextlib import closing, contextmanager
from dataclasses import asdict
from unittest.mock import Mock, patch

import binding
import test_binding

adapter = binding.adapter
custody = binding._GRAPH["native_custody"]
native_sender = binding._GRAPH["native_sender"]
positional = binding.positional_receipt_successor


class NativeCustodyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_binding.BindingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.intent = self.fixture.intent()
        self.packet_pin = "a" * 64
        self.directory = self.fixture.directory
        self.journal = binding.SQLiteJournal(
            self.directory / "journal.sqlite",
            self.intent.target_id,
            self.packet_pin,
            self.fixture.clock,
        )
        self.journal.provision(200)
        core = types.SimpleNamespace(
            journal=self.journal,
            clock=self.fixture.clock,
            packet={"targetId": self.intent.target_id},
            source=self.fixture.source,
            packet_sha2_256=self.packet_pin,
        )
        core.active = lambda: (core.packet, self.journal, "synthetic-noncredential")
        self.sender = native_sender.NativePositionalSender(core)
        self.sender.allocation = {"intents": [asdict(self.intent)]}
        self.sender.guard = Mock()
        self.sender.query = Mock(side_effect=self.read)
        self.sender.dispatch_batch = Mock(side_effect=self.dispatch)
        self.controller = custody.NativeController(self.sender)
        self.custodian = self.open_custodian()
        self.custodian.provision(200)

    def open_custodian(self):
        return custody.ReturnedInvocations(
            self.directory / "custody.sqlite",
            self.packet_pin,
            self.intent.target_id,
            self.intent.candidate,
            self.fixture.clock,
        )

    def read(self, role, sql, params, deadline):
        self.assertEqual(role, "observer")
        cursor = self.fixture.db.execute(sql, params)
        rows = [
            dict(zip([c[0] for c in cursor.description], row, strict=True))
            for row in cursor.fetchall()
        ]
        self.sender.read_evidence.append(
            {
                "requestOrdinal": len(self.sender.read_evidence) * 2,
                "request": custody._read_manifest(sql),
                "responseBodySha2_256": "b" * 64,
                "wireBytes": 100,
                "primary": True,
                "complete": True,
            }
        )
        return rows, {"served_by_primary": True}

    def dispatch(self, batch, deadline):
        self.fixture.db.execute(batch.update_sql, [batch.intent.expected])
        count = self.fixture.db.execute(positional.COUNT_SQL).fetchone()[0]
        body = binding.canonical(
            {
                "success": True,
                "errors": [],
                "messages": [],
                "result": [
                    {"success": True, "results": [], "meta": {"served_by_primary": True}},
                    {
                        "success": True,
                        "results": [{"exact_change_count": count}],
                        "meta": {"served_by_primary": True},
                    },
                ],
            }
        )
        evidence = binding.canonical(
            {
                "scope": "NATIVE_RETURNED_HTTP_EVIDENCE",
                "target": batch.intent.target_id,
                "packet": self.packet_pin,
                "intent": asdict(batch.intent),
                "receipt": positional.receipt_manifest(batch, body),
            }
        )
        return native_sender.NativeBatchReceipt(batch, int(count), evidence)

    def invoke(self, reference="native:first"):
        return self.custodian.invoke(self.controller, self.intent, reference)

    def test_returned_confirmation_retains_full_primary_reads_and_survives_restart(self):
        result = self.invoke()
        self.assertEqual(result.status, "confirmed")
        receipt = self.open_custodian().read("native:first", 100)
        self.assertEqual(receipt, adapter.ConfirmedReceipt("native:first", self.intent, result))
        with closing(sqlite3.connect(self.custodian.path)) as db:
            evidence = json.loads(db.execute("SELECT evidence FROM returned").fetchone()[0])
        self.assertEqual(len(evidence["independentPrimaryReads"]), 4)
        self.assertTrue(evidence["independentPrimaryReads"][1]["rows"])
        self.assertEqual(evidence["finalJournalAcknowledgedAt"], result.confirmed_at)
        self.assertEqual(self.sender.dispatch_batch.call_count, 1)

    def test_lost_final_journal_ack_never_retains_or_reconstructs(self):
        original = self.journal.settle

        def lost_ack(key, phase, deadline):
            original(key, phase, deadline)
            if phase == "confirmed":
                raise OSError("synthetic lost final ACK")

        self.journal.settle = lost_ack
        self.assertEqual(self.invoke().status, "unknown")
        with self.assertRaises(adapter.Refusal):
            self.open_custodian().read("native:first", 100)
        with self.assertRaises(sqlite3.IntegrityError):
            self.open_custodian().invoke(self.controller, self.intent, "native:again")
        self.assertEqual(self.sender.dispatch_batch.call_count, 1)

    def test_lost_native_response_never_retains_and_claim_remains_spent(self):
        self.sender.dispatch_batch.side_effect = OSError("synthetic lost response")
        self.assertEqual(self.invoke().status, "unknown")
        with self.assertRaises(adapter.Refusal):
            self.custodian.read("native:first", 100)
        with self.assertRaises(sqlite3.IntegrityError):
            self.open_custodian().invoke(self.controller, self.intent, "native:first")
        self.assertEqual(self.sender.dispatch_batch.call_count, 1)

    def test_source_or_deadline_failure_after_final_ack_cannot_promote(self):
        self.sender.guard.side_effect = [None, OSError("synthetic final source drift"), None]
        self.assertEqual(self.invoke().status, "unknown")
        with self.assertRaises(adapter.Refusal):
            self.custodian.read("native:first", 100)

    def test_missing_custodian_refuses_before_dispatch(self):
        missing = custody.ReturnedInvocations(
            self.directory / "missing.sqlite",
            self.packet_pin,
            self.intent.target_id,
            self.intent.candidate,
            self.fixture.clock,
        )
        with self.assertRaises(adapter.Refusal):
            missing.invoke(self.controller, self.intent, "native:first")
        self.sender.dispatch_batch.assert_not_called()

    def test_no_caller_result_or_arbitrary_producer_api(self):
        fabricated = adapter.Result(
            "confirmed", "one_row_and_independent_readback", "2", "open", 10
        )
        self.assertFalse(hasattr(self.custodian, "retain"))
        with self.assertRaises(adapter.Refusal):
            self.custodian.invoke(lambda: fabricated, self.intent, "native:fake")
        self.sender.dispatch_batch.assert_not_called()

    def test_phase_alone_and_current_readback_cannot_supply_receipt(self):
        self.journal.latch(self.intent, 100)
        self.journal.claim_dispatch(self.intent.key, 100)
        self.journal.settle(self.intent.key, "confirmed", 100)
        with self.assertRaises(adapter.Refusal):
            self.custodian.read("native:invented", 100)

    def test_incomplete_primary_evidence_refuses_before_mutation(self):
        original = self.read

        def incomplete(*args):
            rows, meta = original(*args)
            self.sender.read_evidence[-1]["complete"] = False
            return rows, meta

        self.sender.query.side_effect = incomplete
        self.assertEqual(self.invoke().status, "refused")
        self.sender.dispatch_batch.assert_not_called()

    def test_wrong_result_receipt_type_cannot_promote(self):
        self.sender.dispatch_batch.side_effect = None
        self.sender.dispatch_batch.return_value = {"success": True, "changes": 1}
        self.assertEqual(self.invoke().status, "unknown")
        with self.assertRaises(adapter.Refusal):
            self.custodian.read("native:first", 100)

    def test_clock_watermark_survives_restart(self):
        with self.custodian._transaction(100):
            pass
        self.fixture.clock_value = 9.0
        with self.assertRaises(adapter.Refusal):
            self.open_custodian().read("native:first", 100)

    def test_append_only_claims_and_receipts(self):
        self.assertEqual(self.invoke().status, "confirmed")
        with closing(sqlite3.connect(self.custodian.path)) as db:
            for table in ("invocations", "returned"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("DELETE FROM " + table)
        with self.assertRaises(FileExistsError):
            self.custodian.provision(200)

    def delivery(self, **changes):
        token_path = self.directory / "synthetic-token.txt"
        token_path.write_bytes(b"synthetic-noncredential-only")
        grant_path = self.directory / "synthetic-grant.json"
        grant_path.write_text("SYNTHETIC ONLY")
        record = {
            "kind": "pmb1-reviewed-protected-delivery-v1",
            "packetSha2_256": self.packet_pin,
            "target": self.intent.target_id,
            "sourcePins": {"source": "c" * 64},
            "credential": {
                "path": str(token_path),
                "sha2_256": binding.sha2_256(token_path.read_bytes()),
            },
            "grant": {
                "path": str(grant_path),
                "sha2_256": binding.sha2_256(grant_path.read_bytes()),
            },
            "custody": {
                "path": str(grant_path),
                "sha2_256": binding.sha2_256(grant_path.read_bytes()),
            },
        }
        record.update(changes)
        review = self.directory / "synthetic-delivery-review.json"
        review.write_bytes(binding.canonical(record))
        loader = custody.ProtectedCredential(
            str(review),
            binding.sha2_256(review.read_bytes()),
            self.packet_pin,
            self.intent.target_id,
            {"source": "c" * 64},
            self.fixture.clock,
            100,
        )
        return loader, token_path

    def test_successor_consumes_actual_returned_confirmation_without_new_root(self):
        self.assertEqual(self.invoke().status, "confirmed")
        successor = self.fixture.intent("second", "close", "2")
        self.sender.allocation["intents"].append(asdict(successor))
        result = self.custodian.invoke(
            self.controller,
            successor,
            "native:second",
            predecessor=self.intent,
            previous="native:first",
        )
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(self.journal.get(successor.key, 100).root_key, self.intent.key)
        self.assertEqual(self.open_custodian().read("native:second", 100).predecessor, successor)
        self.assertEqual(self.sender.dispatch_batch.call_count, 2)

    def test_lost_invocation_claim_ack_never_calls_or_replays_producer(self):
        original = self.custodian._transaction

        @contextmanager
        def lost_ack(deadline):
            with original(deadline) as db:
                yield db
            raise OSError("synthetic claim ACK lost")

        self.custodian._transaction = lost_ack
        with self.assertRaises(OSError):
            self.invoke()
        self.sender.dispatch_batch.assert_not_called()
        with self.assertRaises(sqlite3.IntegrityError):
            self.open_custodian().invoke(self.controller, self.intent, "native:new")

    def test_delivery_metadata_check_precedes_secret_read(self):
        loader, token_path = self.delivery()
        token_path.unlink()
        with self.assertRaisesRegex(adapter.Refusal, "admission_evidence"):
            loader.validate_binding(
                self.packet_pin, self.intent.target_id, {"source": "c" * 64}, "d" * 64, {}, {}
            )

    def test_delivery_constructor_inert_exact_and_one_use(self):
        with patch.object(custody, "_pin", side_effect=AssertionError("constructor read")):
            custody.ProtectedCredential(
                "missing",
                "a" * 64,
                self.packet_pin,
                self.intent.target_id,
                {},
                self.fixture.clock,
                100,
            )
        loader, _path = self.delivery()
        self.assertEqual(loader(), "synthetic-noncredential-only")
        with self.assertRaises(adapter.Refusal):
            loader()

    def test_delivery_wrong_review_binding_refuses_before_secret_read(self):
        loader, token_path = self.delivery(target="wrong")
        token_path.unlink()
        with self.assertRaisesRegex(adapter.Refusal, "review_binding"):
            loader()

    def test_delivery_pin_mismatch_is_spent_without_retry(self):
        loader, token_path = self.delivery()
        token_path.write_bytes(b"different-synthetic-noncredential")
        with self.assertRaises(adapter.Refusal):
            loader()
        with self.assertRaisesRegex(adapter.Refusal, "delivery_spent"):
            loader()

    def test_concurrent_delivery_atomically_consumes_before_any_protected_read(self):
        loader, token_path = self.delivery()
        first_in_check = threading.Event()
        release_first = threading.Event()
        original_require, original_pin = custody._require, custody._pin
        reads, values, errors = [], [], []

        def require(value, reason):
            if reason == "native_credential_delivery_spent" and not first_in_check.is_set():
                first_in_check.set()
                if not release_first.wait(timeout=5):
                    raise AssertionError("synthetic consume test timeout")
            return original_require(value, reason)

        def pin(path, expected, limit):
            if str(path) == str(token_path):
                reads.append(True)
            return original_pin(path, expected, limit)

        def call():
            try:
                values.append(loader())
            except Exception as error:
                errors.append(error)

        with patch.object(custody, "_require", require), patch.object(custody, "_pin", pin):
            first = threading.Thread(target=call)
            competing = threading.Thread(target=call)
            first.start()
            try:
                self.assertTrue(first_in_check.wait(timeout=5))
                competing.start()
                competing.join(timeout=5)
                self.assertFalse(competing.is_alive())
            finally:
                release_first.set()
                first.join(timeout=5)
                if competing.ident is not None:
                    competing.join(timeout=5)
            self.assertFalse(first.is_alive())
            self.assertFalse(competing.is_alive())
        self.assertEqual(len(reads), 1)
        self.assertEqual(values, ["synthetic-noncredential-only"])
        self.assertEqual(len(errors), 1)
        self.assertIs(type(errors[0]), adapter.Refusal)
        self.assertTrue(loader.used)

    def test_interrupted_consume_remains_spent_without_any_read(self):
        loader, _token_path = self.delivery()
        with patch.object(custody, "_require", side_effect=RuntimeError("synthetic interruption")):
            with patch.object(custody, "_pin") as pinned:
                with self.assertRaises(RuntimeError):
                    loader()
                pinned.assert_not_called()
        with self.assertRaisesRegex(adapter.Refusal, "delivery_spent"):
            loader()


if __name__ == "__main__":
    unittest.main()
