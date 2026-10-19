"""Synthetic-only regression and unchanged-adapter integration; no OS effects."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from dataclasses import replace

from binding import FIXED_PACKET, MARKERS, Attempt, Packet, ProcessIdentity, fingerprint, main
from reviewed_adapter import ReviewedSyntheticAdapter
from test_0161_local_preparation_candidate import Clock, FixtureFacade


class Store:
    synthetic_only = True

    def __init__(self):
        self.claims: dict[str, str] = {}
        self.receipts: dict[str, object] = {}
        self.paths: tuple[str, ...] | None = None
        self.fail: str | None = None
        self.clock: Clock | None = None

    def markers_absent(self, exact_paths: tuple[str, ...]) -> bool:
        self.paths = exact_paths
        if self.fail == "markers":
            return False
        if self.fail == "markers_unknown":
            raise OSError("synthetic unknown")
        return not any(path in self.claims or path in self.receipts for path in exact_paths)

    def create_claim(self, exact_path: str, packet_sha2_256: str) -> bool:
        if exact_path in self.claims:
            return False
        self.claims[exact_path] = packet_sha2_256
        if self.fail == "claim_unknown":
            raise OSError("synthetic partial claim")
        if self.clock is not None:
            self.clock.expired = True
        return self.fail != "claim_false"

    def create_receipt(self, exact_path: str, receipt: object) -> bool:
        if exact_path in self.receipts:
            return False
        self.receipts[exact_path] = receipt
        if self.fail == "receipt_unknown":
            raise OSError("synthetic partial receipt")
        return self.fail != "receipt_false"


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.facade = FixtureFacade(self.clock)
        self.adapter = ReviewedSyntheticAdapter(self.facade)
        self.store = Store()
        self.attempt = Attempt()

    def run_binding(self, packet: Packet = FIXED_PACKET, pin: str | None = None):
        return self.attempt.run(
            packet,
            fingerprint(FIXED_PACKET) if pin is None else pin,
            self.adapter,
            self.store,
            self.clock,
        )

    def test_complete_binding_calls_actual_unchanged_adapter(self):
        receipt = self.run_binding()
        self.assertEqual(receipt.outcome, "synthetic_binding_complete_no_run_authority")
        self.assertTrue(receipt.receipt_confirmed)
        self.assertEqual(self.store.paths, MARKERS)
        self.assertEqual(self.store.claims, {FIXED_PACKET.claim: fingerprint(FIXED_PACKET)})
        self.assertEqual(len(self.facade.effects("read")), 1)
        self.assertFalse(receipt.actionReady or receipt.ownerConsent or receipt.nativeConsent)

    def test_exact_packet_mutations_refused_before_store_or_adapter(self):
        changes = {
            "schema": "other",
            "run_identity": "spent",
            "source": "C:\\other",
            "destination": "C:\\other",
            "source_sha2_256": "0" * 64,
            "adapter_sha2_256": "0" * 64,
            "guard_sha2_256": "0" * 64,
            "markers": MARKERS[:-1],
            "claim": FIXED_PACKET.receipt,
            "receipt": FIXED_PACKET.claim,
            "start": 1001.0,
            "deadline": 1901.0,
            "ownerConsent": True,
            "nativeConsent": True,
            "actionReady": True,
            "process": replace(ProcessIdentity(), started="other"),
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                self.setUp()
                result = self.run_binding(replace(FIXED_PACKET, **{key: value}))
                self.assertEqual(result.outcome, "fixed_binding_refused")
                self.assertIsNone(self.store.paths)
                self.assertFalse(result.adapter_attempted)

    def test_packet_float_type_and_review_pin_are_exact(self):
        self.assertEqual(
            self.run_binding(replace(FIXED_PACKET, start=1000)).outcome, "fixed_binding_refused"
        )
        self.setUp()
        self.assertEqual(self.run_binding(pin="0" * 64).outcome, "fixed_binding_refused")

    def test_different_process_generation_and_source_pin_refused(self):
        for field, value in (
            ("process", replace(ProcessIdentity(), process_id=162)),
            ("adapter_sha2_256", "0" * 64),
            ("guard_sha2_256", "0" * 64),
            ("synthetic_only", False),
        ):
            with self.subTest(field=field):
                self.setUp()
                setattr(self.adapter, field, value)
                self.assertEqual(self.run_binding().outcome, "fixed_binding_refused")

    def test_non_synthetic_store_refused(self):
        self.store.synthetic_only = False
        self.assertEqual(self.run_binding().outcome, "fixed_binding_refused")

    def test_marker_presence_or_unknown_never_claims(self):
        for failure in ("markers", "markers_unknown"):
            with self.subTest(failure=failure):
                self.setUp()
                self.store.fail = failure
                result = self.run_binding()
                self.assertFalse(result.claim_attempted or result.adapter_attempted)

    def test_claim_false_or_unknown_stays_spent_and_never_reads(self):
        for failure in ("claim_false", "claim_unknown"):
            with self.subTest(failure=failure):
                self.setUp()
                self.store.fail = failure
                result = self.run_binding()
                self.assertTrue(result.claim_attempted)
                self.assertFalse(result.claim_confirmed or result.adapter_attempted)
                self.assertTrue(self.store.claims)
                self.assertFalse(self.store.receipts)
                self.assertEqual(self.run_binding().outcome, "no_replay")

    def test_new_coordinator_cannot_replay_persisted_claim(self):
        self.run_binding()
        self.attempt = Attempt()
        self.assertEqual(self.run_binding().outcome, "marker_freshness_refused")
        self.assertEqual(len(self.facade.effects("read")), 1)

    def test_claim_race_is_exclusive(self):
        self.store.claims[FIXED_PACKET.claim] = "another fingerprint"
        self.store.markers_absent = lambda exact_paths: True
        result = self.run_binding()
        self.assertEqual(result.outcome, "claim_unconfirmed_no_replay")
        self.assertFalse(result.adapter_attempted)

    def test_expired_before_claim_has_no_store_effects(self):
        self.clock.expired = True
        self.assertEqual(self.run_binding().outcome, "window_closed")
        self.assertFalse(self.store.claims)

    def test_expiry_after_claim_never_reads_or_writes_receipt(self):
        self.store.clock = self.clock
        result = self.run_binding()
        self.assertEqual(result.outcome, "receipt_unconfirmed_no_replay")
        self.assertTrue(result.claim_confirmed)
        self.assertFalse(result.adapter_attempted or result.receipt_attempted)

    def test_clock_backward_nan_infinite_and_elapsed_refused(self):
        for values in (
            ((1001.0, 1.0), (1000.0, 2.0)),
            ((1001.0, 1.0), (1001.0, 0.0)),
            ((float("nan"), 1.0),),
            ((1001.0, float("inf")),),
            ((1001.0, 1.0), (1001.0, 901.0)),
        ):
            with self.subTest(values=values):
                self.setUp()
                sequence = iter(values)
                result = self.attempt.run(
                    FIXED_PACKET,
                    fingerprint(FIXED_PACKET),
                    self.adapter,
                    self.store,
                    lambda sequence=sequence: next(sequence),
                )
                self.assertEqual(result.outcome, "window_closed")
                self.assertFalse(result.adapter_attempted)

    def test_adapter_failure_and_cleanup_are_recorded_without_replay(self):
        for operation in ("read", "write", "flush", "close"):
            with self.subTest(operation=operation):
                self.setUp()
                self.facade.fail_at = operation
                result = self.run_binding()
                self.assertEqual(result.outcome, "adapter_result_refused_no_replay")
                self.assertTrue(result.receipt_confirmed)
                self.assertFalse(self.run_binding().adapter_attempted)

    def test_receipt_false_or_unknown_does_not_replay_delivery(self):
        for failure in ("receipt_false", "receipt_unknown"):
            with self.subTest(failure=failure):
                self.setUp()
                self.store.fail = failure
                result = self.run_binding()
                self.assertEqual(result.outcome, "receipt_unconfirmed_no_replay")
                self.assertFalse(result.receipt_confirmed)
                self.assertTrue(result.adapter_result and result.adapter_result.delivered)
                self.assertEqual(self.run_binding().outcome, "no_replay")

    def test_adapter_itself_cannot_be_replayed(self):
        self.adapter.run(self.clock)
        with self.assertRaisesRegex(ValueError, "adapter_no_replay"):
            self.adapter.run(self.clock)

    def test_bridge_refuses_wrong_sid_and_non_fixture(self):
        self.facade.current_user_sid = "S-1-5-21-100-200-300-9999"
        with self.assertRaises(ValueError):
            ReviewedSyntheticAdapter(self.facade)
        self.facade.current_user_sid = ProcessIdentity().user_sid
        self.facade.fixture_only = False
        with self.assertRaises(ValueError):
            ReviewedSyntheticAdapter(self.facade)

    def test_entry_point_never_constructs_adapter_or_store(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result["outcome"], "NO_APPLY_source_only")
        self.assertFalse(result["actionReady"] or result["ownerConsent"])
        self.assertFalse(result["claim_attempted"] or result["adapter_attempted"])


if __name__ == "__main__":
    unittest.main()
