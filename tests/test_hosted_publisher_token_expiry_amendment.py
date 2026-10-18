"""Synthetic regression proof for the one-plan provider-expiry amendment.

The policy identifiers bind supplied metadata, not proof of human authorization.
No private packets or provider/network services are used.
"""

import copy
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution as runtime
from scripts import hosted_publisher_operator as operator
from scripts import hosted_publisher_operator_plan as boundary
from tests import test_hosted_publisher_execution as execution_tests
from tests import test_hosted_publisher_operator as operator_tests
from tests import test_prepare_hosted_publisher_execution as preparation
from tests.test_hosted_publisher_operator_plan import fixture, loaded


def policy(plan: boundary.OperatorPlan) -> dict[str, str]:
    return {
        "amendment_id": "hosted-publisher-token-expiry-amendment-2026-10-18",
        "decision_id": "call_db0854bafa8748aca10153fc4d4a8a7b",
        "plan_digest": plan.digest,
    }


def grant(plan: boundary.OperatorPlan) -> dict[str, Any]:
    return {
        "grant_id": "synthetic-expiry-grant",
        "account_id": plan.account_id,
        "permissions": ["D1:Edit", "Workers Scripts:Edit"],
        "issued_at": plan.starts_at,
        "expires_at": "2026-10-19T04:00:00Z",
        "revocation_owner": plan.revocation_owner,
        "resource_scope": "exact-account-only",
        "metadata_verified": True,
        "expiry_policy": policy(plan),
    }


class ScopedExpiryBoundaryTests(unittest.TestCase):
    def setUp(self):
        value = fixture()
        for name in ("starts_at", "expires_at", "cleanup_deadline"):
            value[name] = value[name].replace("2026-10-17", "2026-10-18")
        for case in value["cases"]:
            for name in ("starts_at", "expires_at"):
                case[name] = case[name].replace("2026-10-17", "2026-10-18")
        value["revocation_owner"] = "Terry Ott"
        self.plan = loaded(value)
        self.now = datetime(2026, 10, 18, 12, 1, tzinfo=UTC)
        self.grant = grant(self.plan)

    def test_default_still_requires_provider_expiry_no_later_than_cleanup(self):
        default = {k: v for k, v in self.grant.items() if k != "expiry_policy"}
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(self.plan, default, self.now)
        default["expires_at"] = self.plan.cleanup_deadline
        boundary.validate_operator_grant(self.plan, default, self.now)
        default["expires_at"] = "2026-10-18T13:00:01Z"
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(self.plan, default, self.now)

    def test_exact_exception_accepts_actual_expiry_without_mutating_plan_or_metadata(self):
        original = copy.deepcopy(self.grant)
        digest = self.plan.digest
        boundary.validate_operator_grant(self.plan, self.grant, self.now)
        self.assertEqual(self.grant, original)
        self.assertEqual(self.plan.digest, digest)
        self.assertEqual(self.plan.cleanup_deadline, "2026-10-18T13:00:00Z")
        self.assertEqual(self.grant["expires_at"], "2026-10-19T04:00:00Z")

    def test_inclusive_24_hour_and_day_ceiling_and_one_second_over(self):
        self.grant["issued_at"] = "2026-10-18T04:00:00Z"
        boundary.validate_operator_grant(self.plan, self.grant, self.now)
        for change in (
            {"issued_at": "2026-10-18T03:59:59Z"},
            {"expires_at": "2026-10-19T04:00:01Z"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                boundary.validate_operator_grant(self.plan, {**self.grant, **change}, self.now)

    def test_exception_is_closed_exact_and_mandatory_even_for_short_expiry(self):
        invalid: list[Any] = [None, True, [], "accepted", {}, {**policy(self.plan), "extra": True}]
        for name in policy(self.plan):
            invalid.append({k: v for k, v in policy(self.plan).items() if k != name})
            invalid.extend({**policy(self.plan), name: value} for value in (None, True, "wrong"))
        for expiry in (self.plan.cleanup_deadline, self.grant["expires_at"]):
            for value in invalid:
                with self.subTest(expiry=expiry, policy=value), self.assertRaises(ValueError):
                    boundary.validate_operator_grant(
                        self.plan,
                        {**self.grant, "expires_at": expiry, "expiry_policy": value},
                        self.now,
                    )

    def test_exception_does_not_waive_provider_identity_or_current_metadata(self):
        for name, value in (
            ("account_id", "b" * 32),
            ("permissions", ["D1:Edit", "Workers Scripts:Edit", "Account:Edit"]),
            ("resource_scope", "all-accounts"),
            ("metadata_verified", False),
            ("metadata_verified", 1),
            ("revocation_owner", "Other Owner"),
            ("issued_at", "2026-10-18T12:01:01Z"),
            ("issued_at", "2026-10-19T04:00:00Z"),
            ("expires_at", "2026-10-18T12:01:00Z"),
            ("expires_at", "2026-10-18T11:59:59Z"),
            ("issued_at", "2026-10-18T12:00:00+00:00"),
            ("expires_at", "not-a-time"),
        ):
            with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                boundary.validate_operator_grant(self.plan, {**self.grant, name: value}, self.now)
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(
                self.plan, self.grant, boundary.utc_time(self.grant["expires_at"])
            )

    def test_amendment_requires_named_revocation_owner_even_with_matching_plan_policy(self):
        other = replace(self.plan, revocation_owner="Other Owner")
        amended = {
            **self.grant,
            "revocation_owner": other.revocation_owner,
            "expiry_policy": policy(other),
        }
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(other, amended, self.now)

    def test_policy_for_other_plan_is_rejected_without_losing_original_consent_binding(self):
        other = replace(self.plan, owner="Different Synthetic Owner")
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(other, self.grant, self.now)
        consent = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": self.plan.digest,
            "owner": self.plan.owner,
            "actions": list(boundary.OWNER_ACTIONS),
            "decision_id": "synthetic-owner-action",
        }
        boundary.validate_consent(self.plan, consent, self.now)
        for change in ({"granted": False}, {"plan_digest": other.digest}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                boundary.validate_consent(self.plan, {**consent, **change}, self.now)


class ScopedExpiryOperatorTests(unittest.TestCase):
    def setUp(self):
        self.f = operator_tests.HostedOperatorIntegrationTests()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.f.plan = replace(self.f.plan, revocation_owner="Terry Ott")
        self.f.consent["plan_digest"] = self.f.authority["plan_digest"] = self.f.plan.digest
        self.f.journal.close()
        self.f.journal = operator.DurableJournal(self.f.root / "amended.sqlite", self.f.plan.digest)
        self.addCleanup(self.f.journal.close)
        self.f.grant["revocation_owner"] = "Terry Ott"
        self.f.grant["expires_at"] = "2026-10-18T12:00:00Z"
        self.f.grant["expiry_policy"] = policy(self.f.plan)

    def test_actual_operator_keeps_earlier_dispatch_deadline_and_no_replay(self):
        f = self.f
        instance = f.make()
        self.assertEqual(f.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        before = len(f.provider_transport.calls)
        with self.assertRaises(operator.OperatorRefused):
            f.run_synthetic(instance)
        self.assertEqual(len(f.provider_transport.calls), before)
        self.assertEqual(len(f.requests), 28)
        f.wall = boundary.utc_time(f.plan.expires_at).timestamp() + 1
        with self.assertRaises(ValueError):
            f.run_synthetic(instance)
        self.assertEqual(len(f.provider_transport.calls), before)
        self.assertEqual(f.grant["expires_at"], "2026-10-18T12:00:00Z")

    def test_long_grant_does_not_extend_cleanup_authority(self):
        f = self.f
        instance = f.make()
        self.assertEqual(f.run_synthetic(instance)["status"], "phases_complete_cleanup_pending")
        f.wall = boundary.utc_time(f.plan.cleanup_deadline).timestamp()
        before = len(f.provider_transport.calls)
        with self.assertRaises(operator.OperatorRefused):
            instance.cleanup_only(f.authority)
        self.assertEqual(len(f.provider_transport.calls), before)


class ScopedExpiryRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f = execution_tests.ExecutionRuntimeTests()
        self.addCleanup(self.f.doCleanups)
        original = preparation.fixture
        with patch.object(
            preparation,
            "fixture",
            side_effect=lambda: {**original(), "revocation_owner": "Terry Ott"},
        ):
            self.f.setUp()
        f = self.f
        f.grant["expires_at"] = "2026-10-18T12:00:00Z"
        f.grant["expiry_policy"] = policy(f.plan)
        path, digest = f.write("grant.json", f.grant)
        f.inputs = replace(f.inputs, grant=path, grant_digest=digest)
        f.approval["grant_digest"] = digest
        path, digest = f.write("approval.json", f.approval)
        f.inputs = replace(f.inputs, approval=path, approval_digest=digest)

    def test_runtime_preserves_actual_expiry_and_earlier_action_permit(self):
        f = self.f
        checked = f.check()
        self.assertEqual(checked.grant["expires_at"], "2026-10-18T12:00:00Z")
        permit = runtime.ExecutionPermit(
            f.inputs,
            checked,
            cleanup_only=False,
            wall_clock=lambda: f.now,
            monotonic=lambda: 100,
        )
        permit.authorize()
        self.assertEqual(
            permit.remaining_seconds(),
            boundary.utc_time(f.approval["expires_at"]).timestamp() - f.now,
        )
        f.now = boundary.utc_time(f.plan.expires_at).timestamp()
        with self.assertRaises(operator.OperatorRefused):
            permit.authorize()
        f.network.assert_not_called()
        f.entropy.assert_not_called()

    def test_grant_exception_changes_still_require_exact_approval_fingerprint(self):
        f = self.f
        f.grant["expires_at"] = "2026-10-18T11:59:59Z"
        path, digest = f.write("grant.json", f.grant)
        changed_inputs = replace(f.inputs, grant=path, grant_digest=digest)
        factory = Mock()
        with self.assertRaises(operator.OperatorRefused):
            runtime.run(
                changed_inputs,
                wall_clock=lambda: f.now,
                monotonic=lambda: 100,
                provider_factory=factory,
                client_factory=Mock(),
            )
        factory.assert_not_called()
        self.assertFalse(f.inputs.journal.exists())

    def test_exception_does_not_replace_separate_owner_consent(self):
        f = self.f
        f.consent["granted"] = False
        path, digest = f.write("consent.json", f.consent)
        f.inputs = replace(f.inputs, consent=path, consent_digest=digest)
        f.approval["consent_digest"] = digest
        path, digest = f.write("approval.json", f.approval)
        f.inputs = replace(f.inputs, approval=path, approval_digest=digest)
        factory = Mock()
        with self.assertRaises(ValueError):
            runtime.run(
                f.inputs,
                wall_clock=lambda: f.now,
                monotonic=lambda: 100,
                provider_factory=factory,
                client_factory=Mock(),
            )
        factory.assert_not_called()
        f.network.assert_not_called()

    def test_long_grant_keeps_full_runtime_once_only_and_separate_cleanup_paths(self):
        # Run the established real-adapter synthetic scenario with the amended grant.
        # Its assertions cover a fresh invocation, disposal, and cleanup replay.
        self.f.test_new_runtime_uses_one_journal_budget_no_replay_and_known_only_cleanup()
