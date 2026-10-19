"""Synthetic-only diagnostics and journal regression cases."""

import copy
import json
import unittest

from scripts import hosted_publisher_operator as operator
from scripts import hosted_publisher_worker_deployment as deployment
from scripts.hosted_publisher_provider import ProviderError, ProviderUnknown
from tests.test_hosted_publisher_operator import HostedOperatorIntegrationTests
from tests.test_hosted_publisher_worker_deployment import (
    TOKEN,
    HostedPublisherWorkerDeploymentTests,
    StatefulTransport,
)

SENTINEL = "SYNTHETIC-PRIVATE-RESPONSE"


class RejectedDeployment(StatefulTransport):
    def __init__(self, field, value=None, missing=False):
        super().__init__()
        self.field, self.value, self.missing = field, value, missing

    def execute(self, method, path, body):
        result, status = super().execute(method, path, body)
        if method == "POST" and path.endswith("/deployments"):
            result = copy.deepcopy(result)
            if self.missing:
                result.pop(self.field)
            else:
                result[self.field] = self.value
            result["annotations"] = {"private": SENTINEL}
        return result, status


class DeploymentDiagnosticTests(unittest.TestCase):
    setUp = HostedPublisherWorkerDeploymentTests.setUp
    provider = HostedPublisherWorkerDeploymentTests.provider
    version = HostedPublisherWorkerDeploymentTests.version

    def test_missing_and_invalid_fields_reject_without_values_or_replay(self):
        for field in ("id", "created_on", "strategy", "versions"):
            for missing in (True, False):
                with self.subTest(field=field, missing=missing):
                    provider = self.provider()
                    transport = RejectedDeployment(field, SENTINEL, missing)
                    provider._transport = transport
                    identity, version = self.version(provider)
                    with self.assertRaises(ProviderUnknown):
                        provider.deploy_version(identity, version, key="deploy")
                    self.assertEqual(
                        provider.last_deployment_diagnostic,
                        {
                            "stage": "response_validation",
                            "field": field,
                            "status": "missing" if missing else "invalid",
                        },
                    )
                    self.assertNotIn(SENTINEL, json.dumps(provider.last_deployment_diagnostic))
                    self.assertFalse(provider._deployments)
                    calls = len(transport.calls)
                    with self.assertRaises(ProviderError):
                        provider.deploy_version(identity, version, key="repeat")
                    self.assertEqual(calls, len(transport.calls))

    def test_post_read_admission_transport_and_validation_are_distinct(self):
        for failure, stage in (
            ("admission", "post_identity_admission"),
            ("transport", "post_identity_response"),
            ("validation", "post_identity_validation"),
        ):
            with self.subTest(failure=failure):
                provider = self.provider()
                identity, version = self.version(provider)
                original = provider._transport

                def transport(*args, provider=provider, failure=failure, original=original):
                    if provider._deployments:
                        if failure == "transport":
                            raise OSError(SENTINEL)
                        if failure == "validation":
                            response = json.loads(original(*args)[2])
                            response["result"]["id"] = "f" * 32
                            return 200, {}, json.dumps(response).encode()
                    return original(*args)

                def admission(key, *_, failure=failure):
                    if failure == "admission" and key == "deploy:after":
                        raise ProviderError(SENTINEL)

                provider._transport = transport
                provider.before_request = admission
                with self.assertRaises(ProviderError):
                    provider.deploy_version(identity, version, key="deploy")
                self.assertEqual(provider.last_deployment_diagnostic["stage"], stage)
                self.assertEqual(len(provider._deployments), 1)
                self.assertIn(identity["id"], provider._deployment_intents)
                self.assertNotIn(SENTINEL, json.dumps(provider.last_deployment_diagnostic))

    def test_lost_post_ack_is_not_a_field_rejection(self):
        provider = self.provider("lost_deployment")
        identity, version = self.version(provider)
        with self.assertRaises(ProviderUnknown):
            provider.deploy_version(identity, version, key="deploy")
        self.assertEqual(
            provider.last_deployment_diagnostic,
            {
                "stage": "deployment_response",
                "field": "none",
                "status": "not_checked",
            },
        )
        self.assertFalse(provider._deployments)

    def test_well_formed_wrong_allocation_and_naive_time_still_reject(self):
        for field, value in (
            (
                "versions",
                [{"version_id": "99999999-9999-4999-8999-999999999999", "percentage": 100}],
            ),
            (
                "versions",
                [{"version_id": "00000001-2222-4222-8222-222222222222", "percentage": 99}],
            ),
            ("created_on", "2026-10-17T12:00:00"),
        ):
            with self.subTest(field=field, value=value):
                provider = self.provider()
                provider._transport = RejectedDeployment(field, value)
                identity, version = self.version(provider)
                with self.assertRaises(ProviderUnknown):
                    provider.deploy_version(identity, version, key="deploy")
                self.assertEqual(provider.last_deployment_diagnostic["field"], field)
                self.assertTrue(provider._closed)

    def test_receipt_registration_failure_does_not_become_success(self):
        class BrokenRegistration(dict):
            def __setitem__(self, key, value):
                raise RuntimeError(SENTINEL)

        provider = self.provider()
        identity, version = self.version(provider)
        provider._deployments = BrokenRegistration()
        with self.assertRaises(RuntimeError):
            provider.deploy_version(identity, version, key="deploy")
        self.assertEqual(provider.last_deployment_diagnostic["stage"], "receipt_registration")
        self.assertIn(identity["id"], provider._deployment_intents)

    def test_success_clears_diagnostic_and_readback_does_not_relabel_it(self):
        provider = self.provider()
        identity, version = self.version(provider)
        receipt = provider.deploy_version(identity, version, key="deploy")
        self.assertIsNone(provider.last_deployment_diagnostic)
        self.assertEqual(
            provider.inspect_deployment(identity, version, receipt, key="read"), receipt
        )
        self.assertIsNone(provider.last_deployment_diagnostic)

    def test_whitelist_refuses_arbitrary_values_and_extra_fields(self):
        valid = {"stage": "response_validation", "field": "id", "status": "invalid"}
        self.assertEqual(deployment.deployment_diagnostic(valid), valid)
        for name in valid:
            self.assertIsNone(deployment.deployment_diagnostic({**valid, name: SENTINEL}))
        self.assertIsNone(deployment.deployment_diagnostic({**valid, "raw": TOKEN}))


class DeploymentJournalTests(unittest.TestCase):
    setUp = HostedOperatorIntegrationTests.setUp
    make = HostedOperatorIntegrationTests.make
    transport = HostedOperatorIntegrationTests.transport

    def test_failed_optional_observation_still_finishes_unknown(self):
        instance = self.make()

        def broken_clock():
            raise RuntimeError(SENTINEL)

        for index, bad_clock in enumerate((lambda: float("nan"), broken_clock)):
            with self.subTest(index=index):
                instance.wall_clock = lambda: self.wall

                def deploy_version(*args, bad_clock=bad_clock, **kwargs):
                    self.provider.last_deployment_diagnostic = {
                        "stage": "response_validation",
                        "field": "id",
                        "status": "invalid",
                    }
                    instance.wall_clock = bad_clock
                    raise ProviderUnknown(SENTINEL)

                key = "happy:clock-" + str(index)
                with self.assertRaisesRegex(
                    operator.OperatorRefused, "^operation_outcome_unknown$"
                ):
                    instance._call(deploy_version, key=key)
                event = self.journal.snapshot()["operation:" + key]
                self.assertEqual(event["state"], "unknown")
                self.assertEqual(event["receipt"], {"reason": "operation_outcome_unknown"})
                self.assertNotIn(SENTINEL, json.dumps(event))

    def test_rejected_response_retained_as_unknown_with_closed_fields_only(self):
        instance = self.make(transport=RejectedDeployment("created_on", SENTINEL))
        case = self.plan.cases[0]
        database = instance._call(self.provider.create_database, case.d1_name, key="happy:db")
        identity = instance._call(self.provider.create_worker, case.worker_name, key="happy:worker")
        # Use the existing actual parser with the ordinary synthetic projection.
        from scripts.hosted_publisher_operator_plan import deployment_projection

        projection = deployment_projection(self.plan, case, database["uuid"])
        version = instance._call(
            self.provider.create_version,
            identity,
            b"synthetic offline module",
            self.plan.pins["worker"],
            projection,
            "d" * 64,
            key="happy:version",
        )
        with self.assertRaises(operator.OperatorRefused):
            instance._call(self.provider.deploy_version, identity, version, key="happy:deploy")
        event = self.journal.snapshot()["operation:happy:deploy"]
        self.assertEqual(event["state"], "unknown")
        self.assertEqual(
            event["receipt"]["deploymentDiagnostic"],
            {
                "stage": "response_validation",
                "field": "created_on",
                "status": "invalid",
            },
        )
        self.assertRegex(
            event["receipt"]["diagnosticObservedAt"], r"^2026-10-17T12:01:00\.000000Z$"
        )
        serialized = json.dumps(event)
        for private in (SENTINEL, TOKEN, identity["id"], version["id"]):
            self.assertNotIn(private, serialized)

    def test_stale_or_forged_diagnostic_is_not_retained(self):
        instance = self.make()

        def deploy_version(*args, **kwargs):
            raise ProviderError(SENTINEL)

        self.provider.last_deployment_diagnostic = {
            "stage": "response_validation",
            "field": "id",
            "status": "invalid",
        }
        with self.assertRaises(operator.OperatorRefused):
            instance._call(deploy_version, key="happy:deploy")
        event = self.journal.snapshot()["operation:happy:deploy"]
        self.assertEqual(event["receipt"], {"reason": "operation_outcome_unknown"})

        def forged(*args, **kwargs):
            self.provider.last_deployment_diagnostic = {"stage": SENTINEL}
            raise ProviderError(SENTINEL)

        forged.__name__ = "deploy_version"
        with self.assertRaises(operator.OperatorRefused):
            instance._call(forged, key="happy:forged")
        event = self.journal.snapshot()["operation:happy:forged"]
        self.assertEqual(event["receipt"], {"reason": "operation_outcome_unknown"})
