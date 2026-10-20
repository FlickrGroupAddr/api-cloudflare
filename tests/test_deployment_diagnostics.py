"""Synthetic-only diagnostics and journal regression cases."""

import copy
import json
import threading
import unittest
from pathlib import Path

from scripts import hosted_publisher_operator as operator
from scripts import hosted_publisher_operator_plan as plan_module
from scripts import hosted_publisher_worker_deployment as deployment
from scripts.hosted_publisher_provider import ProviderError, ProviderUnknown
from tests.test_hosted_publisher_operator import HostedOperatorIntegrationTests
from tests.test_hosted_publisher_worker_deployment import (
    TOKEN,
    HostedPublisherWorkerDeploymentTests,
    StatefulTransport,
)

SENTINEL = "SYNTHETIC-PRIVATE-RESPONSE"


class PrivateAliasedKey(str):
    """An underlying private string can masquerade as a whitelisted key."""

    def __hash__(self):
        return hash("id")

    def __eq__(self, other):
        return type(other) is str and other == "id"


class ClassifiedString(str):
    pass


class ShapeDictionary(dict):
    pass


def aliased_shape(shape):
    return {
        PrivateAliasedKey(SENTINEL) if key == "id" else key: value for key, value in shape.items()
    }


class RejectedDeployment(StatefulTransport):
    def __init__(self, field, value=None, missing=False, metadata=None):
        super().__init__()
        self.field, self.value, self.missing = field, value, missing
        self.metadata = metadata

    def execute(self, method, path, body):
        result, status = super().execute(method, path, body)
        if method == "POST" and path.endswith("/deployments"):
            result = copy.deepcopy(result)
            if self.missing:
                result.pop(self.field)
            else:
                result[self.field] = self.value
            result["annotations"] = {"private": SENTINEL}
            if self.metadata is not None:
                result["metadata"] = self.metadata
        return result, status


class ShapedRejection(StatefulTransport):
    def __init__(self, response):
        super().__init__()
        self.response = response

    def execute(self, method, path, body):
        result, status = super().execute(method, path, body)
        if method == "POST" and path.endswith("/deployments"):
            result = self.response
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
                    shape = provider.last_deployment_response_shape
                    assert shape is not None
                    self.assertEqual(deployment.deployment_response_shape(shape), shape)
                    self.assertEqual(shape[field], "missing" if missing else "string")
                    self.assertNotIn(SENTINEL, json.dumps(shape))
                    self.assertFalse(provider._deployments)
                    calls = len(transport.calls)
                    with self.assertRaises(ProviderError):
                        provider.deploy_version(identity, version, key="repeat")
                    self.assertEqual(calls, len(transport.calls))
                    self.assertIsNone(provider.last_deployment_response_shape)

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
                assert provider.last_deployment_diagnostic is not None
                self.assertEqual(provider.last_deployment_diagnostic["stage"], stage)
                self.assertEqual(len(provider._deployments), 1)
                self.assertIn(identity["id"], provider._deployment_intents)
                self.assertNotIn(SENTINEL, json.dumps(provider.last_deployment_diagnostic))
                self.assertIsNone(provider.last_deployment_response_shape)

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
        self.assertIsNone(provider.last_deployment_response_shape)

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
                assert provider.last_deployment_diagnostic is not None
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
        assert provider.last_deployment_diagnostic is not None
        self.assertEqual(provider.last_deployment_diagnostic["stage"], "receipt_registration")
        self.assertIsNone(provider.last_deployment_response_shape)
        self.assertIn(identity["id"], provider._deployment_intents)

    def test_success_clears_diagnostic_and_readback_does_not_relabel_it(self):
        provider = self.provider()
        identity, version = self.version(provider)
        receipt = provider.deploy_version(identity, version, key="deploy")
        self.assertIsNone(provider.last_deployment_diagnostic)
        self.assertIsNone(provider.last_deployment_response_shape)
        self.assertEqual(
            provider.inspect_deployment(identity, version, receipt, key="read"), receipt
        )
        self.assertIsNone(provider.last_deployment_diagnostic)
        self.assertIsNone(provider.last_deployment_response_shape)

    def test_shape_records_only_fixed_types_even_for_nested_private_values(self):
        response = {
            "id": SENTINEL,
            "strategy": False,
            "versions": [{SENTINEL: TOKEN}],
            "metadata": {"created_on": SENTINEL, SENTINEL: {"token": TOKEN}},
            SENTINEL: TOKEN,
        }
        provider = self.provider()
        provider._transport = ShapedRejection(response)
        identity, version = self.version(provider)
        with self.assertRaises(ProviderUnknown):
            provider.deploy_version(identity, version, key="deploy")
        self.assertEqual(
            provider.last_deployment_response_shape,
            {
                "result": "object",
                "id": "string",
                "created_on": "missing",
                "strategy": "boolean",
                "versions": "array",
                "metadata": "object",
                "metadata.created_on": "string",
            },
        )
        serialized = json.dumps(provider.last_deployment_response_shape)
        for private in (SENTINEL, TOKEN):
            self.assertNotIn(private, serialized)

    def test_non_object_result_and_metadata_types_have_no_invented_nested_fields(self):
        for result in (None, False, 1, 1.5, SENTINEL, [TOKEN]):
            with self.subTest(result_type=type(result).__name__):
                provider = self.provider()
                provider._transport = ShapedRejection(result)
                identity, version = self.version(provider)
                with self.assertRaises(ProviderUnknown):
                    provider.deploy_version(identity, version, key="deploy")
                shape = provider.last_deployment_response_shape
                assert shape is not None
                self.assertEqual(deployment.deployment_response_shape(shape), shape)
                self.assertTrue(
                    all(
                        value == "unavailable"
                        for field, value in shape.items()
                        if field != "result"
                    )
                )
        for metadata, classification in (
            (None, "null"),
            (TOKEN, "string"),
            ([TOKEN], "array"),
            ({}, "object"),
        ):
            with self.subTest(metadata_type=classification):
                shape = deployment._response_shape({"metadata": metadata})
                self.assertEqual(shape["metadata"], classification)
                self.assertEqual(
                    shape["metadata.created_on"],
                    "missing" if classification == "object" else "unavailable",
                )
                self.assertEqual(deployment.deployment_response_shape(shape), shape)

    def test_shape_validator_rejects_injected_or_inconsistent_maps(self):
        shape = deployment._response_shape({})
        self.assertEqual(deployment.deployment_response_shape(shape), shape)
        for field in shape:
            for value in (
                SENTINEL,
                {"token": TOKEN},
                [TOKEN],
                None,
                False,
                ClassifiedString(shape[field]),
            ):
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.assertIsNone(deployment.deployment_response_shape({**shape, field: value}))
        for invalid in (
            {**shape, SENTINEL: TOKEN},
            {**shape, "result": "array"},
            {**shape, "metadata.created_on": "string"},
            {**shape, "id": "unavailable"},
            {"body": TOKEN},
            ShapeDictionary(shape),
            None,
        ):
            self.assertIsNone(deployment.deployment_response_shape(invalid))

    def test_secret_underlying_aliased_key_is_rejected_before_serialization(self):
        shape = deployment._response_shape({})
        hostile = aliased_shape(shape)
        self.assertEqual(set(hostile), set(shape))
        self.assertIn(SENTINEL, json.dumps(hostile))
        self.assertIsNone(deployment.deployment_response_shape(hostile))
        diagnostic = {"stage": "response_validation", "field": "id", "status": "invalid"}

        class PrivateStageKey(str):
            def __hash__(self):
                return hash("stage")

            def __eq__(self, other):
                return type(other) is str and other == "stage"

        forged = {
            PrivateStageKey(SENTINEL) if key == "stage" else key: value
            for key, value in diagnostic.items()
        }
        self.assertEqual(set(forged), set(diagnostic))
        self.assertIn(SENTINEL, json.dumps(forged))
        self.assertIsNone(deployment.deployment_diagnostic(forged))

    def test_concurrent_refusal_preserves_active_shape_until_next_owned_operation(self):
        provider = self.provider()
        identity, version = self.version(provider)
        marker = {"private": SENTINEL}
        provider.last_deployment_response_shape = marker
        held, release = threading.Event(), threading.Event()

        def hold_session():
            with provider._session_lock:
                held.set()
                release.wait(timeout=5)

        owner = threading.Thread(target=hold_session)
        owner.start()
        try:
            self.assertTrue(held.wait(timeout=5))
            calls = provider.calls
            with self.assertRaisesRegex(ProviderError, "worker_concurrent_operation_forbidden"):
                provider.deploy_version(identity, version, key="refused")
            self.assertEqual(provider.calls, calls)
            self.assertIs(provider.last_deployment_response_shape, marker)
        finally:
            release.set()
            owner.join(timeout=5)
        self.assertFalse(owner.is_alive())
        provider.deploy_version(identity, version, key="deploy")
        self.assertIsNone(provider.last_deployment_response_shape)

    def test_active_diagnostic_requires_request_key_before_transport(self):
        provider = self.provider()
        provider._deployment_diagnostic_active = True
        self.assertIsNone(provider._deployment_request_key)
        calls = provider.calls
        with self.assertRaises(AssertionError):
            provider._request("GET", "/synthetic", key="invalid-state")
        self.assertEqual(provider.calls, calls)

    def test_nested_timestamp_is_classified_but_never_normalized(self):
        provider = self.provider()
        provider._transport = RejectedDeployment(
            "created_on", missing=True, metadata={"created_on": "2026-10-17T12:01:00Z"}
        )
        identity, version = self.version(provider)
        with self.assertRaises(ProviderUnknown):
            provider.deploy_version(identity, version, key="deploy")
        assert provider.last_deployment_diagnostic is not None
        assert provider.last_deployment_response_shape is not None
        self.assertEqual(provider.last_deployment_diagnostic["field"], "created_on")
        self.assertEqual(provider.last_deployment_response_shape["created_on"], "missing")
        self.assertEqual(provider.last_deployment_response_shape["metadata.created_on"], "string")
        self.assertFalse(provider._deployments)

    def test_whitelist_refuses_arbitrary_values_and_extra_fields(self):
        valid = {"stage": "response_validation", "field": "id", "status": "invalid"}
        self.assertEqual(deployment.deployment_diagnostic(valid), valid)
        for name in valid:
            self.assertIsNone(deployment.deployment_diagnostic({**valid, name: SENTINEL}))
        self.assertIsNone(deployment.deployment_diagnostic({**valid, "raw": TOKEN}))


class DeploymentJournalTests(unittest.TestCase):
    # These attributes are supplied by the shared synthetic integration fixture.
    root: Path
    journal: operator.DurableJournal
    provider: deployment.BetaPublisherProvider
    plan: plan_module.OperatorPlan
    wall: float

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
        self.assertEqual(
            event["receipt"]["deploymentResponseShape"],
            {
                "result": "object",
                "id": "string",
                "created_on": "string",
                "strategy": "string",
                "versions": "array",
                "metadata": "missing",
                "metadata.created_on": "unavailable",
            },
        )
        # The private durable journal, rather than only provider memory, retains the supplement.
        self.journal.close()
        with operator.DurableJournal(self.root / "run.sqlite", self.plan.digest) as recovered:
            self.assertEqual(recovered.snapshot()["operation:happy:deploy"], event)
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

    def test_forged_or_stale_shape_never_enters_rejection_evidence(self):
        instance = self.make()
        valid_shape = deployment._response_shape({})
        for index, (shape, stage, fresh) in enumerate(
            (
                ({**valid_shape, "body": TOKEN}, "response_validation", True),
                ({**valid_shape, "created_on": SENTINEL}, "response_validation", True),
                ({**valid_shape, "created_on": {"token": TOKEN}}, "response_validation", True),
                (aliased_shape(valid_shape), "response_validation", True),
                (
                    {**valid_shape, "created_on": ClassifiedString("missing")},
                    "response_validation",
                    True,
                ),
                ({**valid_shape, "created_on": False}, "response_validation", True),
                (ShapeDictionary(valid_shape), "response_validation", True),
                (valid_shape, "receipt_registration", True),
                (valid_shape, "response_validation", False),
            )
        ):
            with self.subTest(index=index):
                self.provider.last_deployment_response_shape = shape

                def deploy_version(*args, shape=shape, stage=stage, fresh=fresh, **kwargs):
                    self.provider.last_deployment_diagnostic = {
                        "stage": stage,
                        "field": "created_on",
                        "status": "missing",
                    }
                    if fresh:
                        self.provider.last_deployment_response_shape = shape
                    raise ProviderUnknown(SENTINEL)

                key = "happy:shape-" + str(index)
                with self.assertRaises(operator.OperatorRefused):
                    instance._call(deploy_version, key=key)
                event = self.journal.snapshot()["operation:" + key]
                self.assertEqual(event["state"], "unknown")
                self.assertNotIn("deploymentResponseShape", event["receipt"])
                for private in (SENTINEL, TOKEN):
                    self.assertNotIn(private, json.dumps(event))
