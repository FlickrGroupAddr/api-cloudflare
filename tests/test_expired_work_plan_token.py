"""Synthetic expired-child retirement invariants; no real provider or credentials."""

import copy
import unittest
from datetime import UTC, datetime
from pathlib import Path

from scripts import provision_work_plan_token as issuer
from tests import test_provision_work_plan_token as base


class ExpiredRetirementTests(base.IssuerTests):
    """Also rerun every inherited issue/active-revoke refusal and no-replay test."""

    def expired_packet(self):
        self.run_issuer()
        historical = copy.deepcopy(self.child_details)
        self.prepare_revoke()
        self.now = datetime(2026, 10, 19, 14, 0, tzinfo=UTC).timestamp()
        self.plan.update(
            operation="revoke_expired",
            starts_at="2026-10-19T14:00:00Z",
            expires_at="2026-10-19T14:10:00Z",
        )
        self.plan["issuance"].update(child_details=historical, historical_validation_at=base.END)
        self.approval.update(recorded_at=self.plan["starts_at"], expires_at=self.plan["expires_at"])
        self.refresh()
        self.calls = []
        self.responses = [
            base.envelope(self.parent_verify),
            self.catalog,
            base.envelope(self.parent_details),
            base.envelope({**historical, "status": "expired"}),
            base.envelope({"id": base.CHILD_ID}),
        ]

    def test_expired_exact_child_uses_parent_five_calls_no_child_bearer_and_original_latch(self):
        self.expired_packet()
        original = copy.deepcopy(self.plan["issuance"]["child_details"])
        loaded = []

        def credential(path, limit):
            loaded.append(path)
            self.assertEqual(path, Path(self.plan["parent_credential"]))
            return base.PARENT

        result = issuer.run(
            self.inputs,
            wall_clock=lambda: self.now,
            monotonic=lambda: self.tick,
            transport=self.transport,
            credential_loader=credential,
        )
        self.assertEqual(result["requests"], 5)
        self.assertEqual(loaded, [Path(self.plan["parent_credential"])])
        self.assertEqual(
            [call.wire.split(b" ", 1)[0] for call in self.calls],
            [b"GET", b"GET", b"GET", b"GET", b"DELETE"],
        )
        self.assertTrue(self.calls[-1].url.endswith("/" + base.CHILD_ID))
        self.assertEqual(self.plan["issuance"]["child_details"], original)
        self.assertEqual(original["status"], "active")
        ref = self.plan["issuance"]
        self.assertEqual(
            self.journal(ref["journal"], ref["plan_digest"])["issuer:retire"]["state"], "complete"
        )

    def test_expired_revoke_future_child_refuses_before_parent_use(self):
        self.expired_packet()
        self.plan["child_expires_at"] = "2026-10-19T15:00:00Z"
        self.refresh()
        self.stopped(0)

    def test_expired_revoke_expired_parent_refuses_before_child_or_delete(self):
        self.expired_packet()
        self.responses[0]["result"].update(status="expired", expires_on="2026-10-19T13:30:00Z")
        self.stopped(1)

    def test_expired_revoke_parent_expires_midwindow_refuses_before_original_latch(self):
        self.expired_packet()
        self.responses[0]["result"]["expires_on"] = "2026-10-19T14:05:00Z"
        self.responses[2]["result"]["expires_on"] = "2026-10-19T14:05:00Z"
        self.stopped(3)
        ref = self.plan["issuance"]
        self.assertNotIn("issuer:retire", self.journal(ref["journal"], ref["plan_digest"]))

    def test_expired_revoke_active_or_disabled_or_unknown_status_refuses(self):
        for status in ("active", "disabled", "unknown"):
            with self.subTest(status=status):
                with self.subtests_packet() as fixture:
                    fixture.responses[3]["result"]["status"] = status
                    fixture.stopped(4)

    def subtests_packet(self):
        from contextlib import contextmanager

        @contextmanager
        def fixture():
            child = ExpiredRetirementTests(
                "test_expired_revoke_future_child_refuses_before_parent_use"
            )
            child.setUp()
            try:
                child.expired_packet()
                yield child
            finally:
                child.doCleanups()

        return fixture()

    def test_expired_revoke_identity_policy_lifetime_or_condition_drift_refuses(self):
        changes = {
            "id": "f" * 32,
            "name": "changed",
            "expires_on": "2026-10-19T13:01:00Z",
            "issued_on": "2026-10-19T12:00:31Z",
            "not_before": "2026-10-19T12:00:01Z",
            "policies": [],
            "condition": {"request_ip": {"in": ["1.1.1.1/32"]}},
        }
        for field, value in changes.items():
            with self.subTest(field=field), self.subtests_packet() as fixture:
                fixture.responses[3]["result"][field] = value
                fixture.stopped(4)

    def test_expired_revoke_ownership_mismatch_stops_before_child_read(self):
        self.expired_packet()
        self.plan["account_id"] = "f" * 32
        self.refresh()
        self.stopped(3)

    def test_unknown_expired_delete_spends_original_latch_no_fresh_packet_replay(self):
        self.expired_packet()
        self.responses[-1] = TimeoutError("synthetic unknown DELETE")
        self.stopped(5)
        ref = self.plan["issuance"]
        self.assertEqual(
            self.journal(ref["journal"], ref["plan_digest"])["issuer:retire"]["state"], "intent"
        )
        self.calls = []
        self.plan.update(
            claim=str(self.root / "retry.claim"),
            journal=str(self.root / "retry.sqlite"),
            evidence=str(self.root / "retry.jsonl"),
        )
        self.refresh()
        self.stopped(3)


if __name__ == "__main__":
    unittest.main()
