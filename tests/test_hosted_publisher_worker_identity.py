"""Offline fixtures for documented Beta Worker HTTP contracts; no provider proof.

Official create/edit/delete schemas reviewed 2026-10-17:
https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/
These injected responses do not qualify collision, cancellation, CAS or drain semantics.
"""

import contextlib
import io
import json
import threading
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from scripts import hosted_publisher_worker_identity as worker

ACCOUNT = "a" * 32
TOKEN = "synthetic-private-provider-token"
NAME = "fga-publisher-happy"
WORKER_ID = "1" * 32
IDENTITY = {"id": WORKER_ID, "name": NAME, "created_on": "2026-10-17T12:00:00Z"}
CONFIG = {
    "name": NAME,
    "logpush": False,
    "observability": {"enabled": False},
    "subdomain": {"enabled": False, "previews_enabled": False},
    "tags": [],
    "tail_consumers": [],
}
REFERENCES = {
    "dispatch_namespace_outbounds": [],
    "domains": [],
    "durable_objects": [],
    "queues": [],
    "workers": [],
}
RESULT = {**IDENTITY, **CONFIG, "references": REFERENCES}
PREFIX = "/client/v4/accounts/" + ACCOUNT + "/workers/workers"


def envelope(result=None, *, status=200, success=True, include_result=True):
    value = {"errors": [], "messages": [], "success": success}
    if include_result:
        value["result"] = result
    return status, {}, json.dumps(value).encode()


class BetaWorkerIdentityTests(unittest.TestCase):
    def adapter(self, *responses, **kwargs):
        transport = Mock(side_effect=list(responses))
        instance = worker.BetaWorkerProvider(ACCOUNT, TOKEN, [NAME], transport=transport, **kwargs)
        return instance, transport

    def created(self, *responses, **kwargs):
        instance, transport = self.adapter(envelope(RESULT), *responses, **kwargs)
        identity = instance.create_worker(NAME, key="create")
        self.assertEqual(identity, IDENTITY)
        return instance, transport, identity

    def test_documented_post_then_id_get_patch_get_delete_without_force(self):
        instance, transport, identity = self.created(
            envelope(RESULT),
            envelope(RESULT),
            envelope(RESULT),
            envelope(RESULT),
            envelope(include_result=False),
        )
        instance.inspect_worker(identity, key="inspect")
        instance.disable_worker(identity, key="disable")
        receipt = instance.delete_worker(identity, key="delete")
        self.assertTrue(receipt["deletionAcknowledged"])
        self.assertFalse(receipt["absenceVerified"])
        calls = transport.call_args_list
        self.assertEqual(
            [(call.args[0], call.args[1]) for call in calls],
            [
                ("POST", PREFIX),
                ("GET", PREFIX + "/" + WORKER_ID),
                ("GET", PREFIX + "/" + WORKER_ID),
                ("PATCH", PREFIX + "/" + WORKER_ID),
                ("GET", PREFIX + "/" + WORKER_ID),
                ("DELETE", PREFIX + "/" + WORKER_ID),
            ],
        )
        for call in (calls[0], calls[3]):
            self.assertEqual(json.loads(call.args[2]), CONFIG)
        for call in calls:
            self.assertEqual(call.args[3]["Authorization"], "Bearer " + TOKEN)
            self.assertNotIn("?", call.args[1])
            self.assertNotIn("/scripts/", call.args[1])

    def test_concrete_default_refuses_before_https_dispatch(self):
        with patch("scripts.hosted_publisher_provider.https_transport") as transport:
            instance = worker.BetaWorkerProvider(ACCOUNT, TOKEN, [NAME])
            with self.assertRaises(worker.ProviderError):
                instance.create_worker(NAME, key="create")
        transport.assert_not_called()

    def test_identity_cannot_be_adopted_by_name_or_supplied_before_create(self):
        instance, transport = self.adapter()
        for method in (instance.inspect_worker, instance.disable_worker, instance.delete_worker):
            for identity in (
                NAME,
                IDENTITY,
                {"id": NAME, "name": NAME, "created_on": IDENTITY["created_on"]},
            ):
                with self.subTest(method=method.__name__, identity=type(identity).__name__):
                    with self.assertRaises(worker.ProviderError):
                        method(identity, key="unowned")
        transport.assert_not_called()

    def test_unknown_creation_never_retries_or_recovers_via_name(self):
        for response in (
            OSError(TOKEN),
            envelope({}, success=False),
            (302, {}, b""),
            (503, {}, TOKEN.encode()),
            (200, {}, b"not-json"),
        ):
            with self.subTest(response=type(response).__name__):
                instance, transport = self.adapter(response)
                with self.assertRaises(worker.ProviderUnknown):
                    instance.create_worker(NAME, key="create")
                for method in (
                    instance.inspect_worker,
                    instance.disable_worker,
                    instance.delete_worker,
                ):
                    with self.assertRaises(worker.ProviderError):
                        method(IDENTITY, key="recovery")
                with self.assertRaises(worker.ProviderError):
                    instance.create_worker(NAME, key="retry")
                self.assertEqual(transport.call_count, 1)

    def test_response_identity_drift_blocks_delete_after_exact_id_read(self):
        for change in (
            {"id": "2" * 32},
            {"name": "fga-publisher-other"},
            {"created_on": "2026-10-18T12:00:00Z"},
        ):
            with self.subTest(field=next(iter(change))):
                instance, transport, identity = self.created(envelope({**RESULT, **change}))
                with self.assertRaises(worker.ProviderError):
                    instance.delete_worker(identity, key="cleanup")
                self.assertEqual(transport.call_count, 2)
                self.assertEqual(transport.call_args.args[0], "GET")
                self.assertTrue(transport.call_args.args[1].endswith("/" + WORKER_ID))

    def test_caller_identity_drift_never_dispatches_mutation(self):
        instance, transport, identity = self.created()
        for change in (
            {"id": "2" * 32},
            {"name": "fga-publisher-other"},
            {"created_on": "2026-10-18T12:00:00Z"},
        ):
            with self.assertRaises(worker.ProviderError):
                instance.delete_worker({**identity, **change}, key="drift")
        self.assertEqual(transport.call_count, 1)

    def test_create_rejects_missing_malformed_or_mutable_name_id(self):
        for change in (
            {"id": NAME},
            {"id": "00000000-0000-0000-0000-000000000001"},
            {"id": None},
            {"created_on": "not-a-date"},
            {"name": "fga-publisher-other"},
        ):
            with self.subTest(change=next(iter(change))):
                instance, transport = self.adapter(envelope({**RESULT, **change}))
                with self.assertRaises(worker.ProviderUnknown):
                    instance.create_worker(NAME, key="create")
                self.assertEqual(transport.call_count, 1)

    def test_enabled_settings_or_external_references_fail_closed(self):
        for change in (
            {"subdomain": {"enabled": True, "previews_enabled": False}},
            {"subdomain": {"enabled": False, "previews_enabled": True}},
            {"logpush": True},
            {"observability": {"enabled": True}},
            {"references": {"workers": [{"id": "2" * 32, "name": "other"}]}},
        ):
            with self.subTest(field=next(iter(change))):
                instance, transport = self.adapter(envelope({**RESULT, **change}))
                with self.assertRaises(worker.ProviderUnknown):
                    instance.create_worker(NAME, key="create")
                self.assertEqual(transport.call_count, 1)

    def test_missing_or_nonlist_reference_categories_block_delete_before_mutation(self):
        for category in REFERENCES:
            incomplete = {key: value for key, value in REFERENCES.items() if key != category}
            hostile: list[dict[str, object]] = [dict(incomplete)]
            hostile.extend({**REFERENCES, category: value} for value in (None, {}, "", False))
            for references in hostile:
                with self.subTest(category=category, shape=type(references.get(category)).__name__):
                    instance, transport, identity = self.created(
                        envelope({**RESULT, "references": references})
                    )
                    with self.assertRaises(worker.ProviderUnknown):
                        instance.delete_worker(identity, key="delete")
                    self.assertEqual(transport.call_count, 2)
                    self.assertEqual(transport.call_args.args[0], "GET")

    def test_active_endpoint_blocks_delete_before_mutation(self):
        for flags in (
            {"enabled": True, "previews_enabled": False},
            {"enabled": False, "previews_enabled": True},
        ):
            instance, transport, identity = self.created(envelope({**RESULT, "subdomain": flags}))
            with self.assertRaises(worker.ProviderUnknown):
                instance.delete_worker(identity, key="delete")
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(transport.call_args.args[0], "GET")

    def test_unknown_patch_or_delete_outcome_latches_all_requests_closed(self):
        for method_name in ("disable_worker", "delete_worker"):
            instance, transport, identity = self.created(
                envelope(RESULT), (503, {}, TOKEN.encode())
            )
            with self.assertRaises(worker.ProviderUnknown):
                getattr(instance, method_name)(identity, key="mutation")
            self.assertEqual(transport.call_count, 3)
            with self.assertRaises(worker.ProviderError):
                instance.inspect_worker(identity, key="read-after-unknown")
            self.assertEqual(transport.call_count, 3)

    def test_owned_active_endpoint_can_be_disabled_by_exact_id(self):
        active = {**RESULT, "subdomain": {"enabled": True, "previews_enabled": True}}
        instance, transport, identity = self.created(envelope(active), envelope(RESULT))
        receipt = instance.disable_worker(identity, key="disable")
        self.assertTrue(receipt["disableAcknowledged"])
        self.assertFalse(receipt["drainProven"])
        self.assertFalse(receipt["providerQualified"])
        self.assertFalse(receipt["liveExecutionAllowed"])
        self.assertEqual(
            [(call.args[0], call.args[1]) for call in transport.call_args_list[1:]],
            [("GET", PREFIX + "/" + WORKER_ID), ("PATCH", PREFIX + "/" + WORKER_ID)],
        )
        self.assertEqual(json.loads(transport.call_args.args[2]), CONFIG)

    def test_disable_rejects_nonboolean_active_flags_before_patch(self):
        for value in (1, "true", None):
            active = {**RESULT, "subdomain": {"enabled": value, "previews_enabled": True}}
            instance, transport, identity = self.created(envelope(active))
            with self.assertRaises(worker.ProviderUnknown):
                instance.disable_worker(identity, key="disable")
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(transport.call_args.args[0], "GET")

    def test_disable_patch_must_acknowledge_both_endpoints_disabled(self):
        active = {**RESULT, "subdomain": {"enabled": True, "previews_enabled": True}}
        for flags in (
            {"enabled": True, "previews_enabled": False},
            {"enabled": False, "previews_enabled": True},
        ):
            instance, transport, identity = self.created(
                envelope(active), envelope({**RESULT, "subdomain": flags})
            )
            with self.assertRaises(worker.ProviderUnknown):
                instance.disable_worker(identity, key="disable")
            self.assertEqual(transport.call_count, 3)
            self.assertEqual(transport.call_args.args[0], "PATCH")
            with self.assertRaises(worker.ProviderError):
                instance.disable_worker(identity, key="retry")
            self.assertEqual(transport.call_count, 3)

    def test_subdomain_url_presence_does_not_mean_enabled(self):
        result = {
            **RESULT,
            "subdomain": {
                **CONFIG["subdomain"],
                "url": "https://synthetic.example.workers.dev",
                "preview_url_suffix": "synthetic.example.workers.dev",
            },
        }
        instance, _ = self.adapter(envelope(result))
        self.assertEqual(instance.create_worker(NAME, key="create"), IDENTITY)

    def test_404_is_only_absence_observation_and_never_delete_ack(self):
        instance, transport, identity = self.created(envelope(status=404, success=False))
        receipt = instance.delete_worker(identity, key="cleanup")
        self.assertTrue(receipt["absent"])
        self.assertNotEqual(receipt.get("deletionAcknowledged"), True)
        self.assertEqual(transport.call_count, 2)

    def test_deletion_404_after_precheck_is_not_success_ack(self):
        instance, transport, identity = self.created(
            envelope(RESULT), envelope(status=404, success=False)
        )
        receipt = instance.delete_worker(identity, key="delete")
        self.assertTrue(receipt["absent"])
        self.assertNotEqual(receipt.get("deletionAcknowledged"), True)
        self.assertEqual(transport.call_count, 3)

    def test_response_cap_exhaustion_latches_closed(self):
        raw = envelope(RESULT)
        instance, transport = self.adapter(
            raw, limits=replace(worker.Limits(), response_bytes=len(raw[2]) - 1)
        )
        with self.assertRaises(worker.ProviderUnknown):
            instance.create_worker(NAME, key="create")
        with self.assertRaises(worker.ProviderError):
            instance.create_worker(NAME, key="retry")
        self.assertEqual(transport.call_count, 1)

    def test_duplicate_key_and_call_budget_refuse_before_transport(self):
        for limits, key in (
            (worker.Limits(), "create"),
            (replace(worker.Limits(), calls=1), "read"),
        ):
            instance, transport, identity = self.created(limits=limits)
            with self.assertRaises(worker.ProviderError):
                instance.inspect_worker(identity, key=key)
            self.assertEqual(transport.call_count, 1)

    def test_cumulative_response_budget_refuses_before_second_request(self):
        raw = envelope(RESULT)
        instance, transport, identity = self.created(
            limits=replace(worker.Limits(), total_response_bytes=len(raw[2]))
        )
        with self.assertRaises(worker.ProviderError):
            instance.inspect_worker(identity, key="read")
        self.assertEqual(transport.call_count, 1)

    def test_request_byte_or_elapsed_budget_refuses_before_dispatch(self):
        instance, transport = self.adapter(limits=replace(worker.Limits(), request_bytes=1))
        with self.assertRaises(worker.ProviderError):
            instance.create_worker(NAME, key="create")
        transport.assert_not_called()
        clock = Mock(return_value=0.0)
        instance, transport = self.adapter(
            monotonic=clock, limits=replace(worker.Limits(), total_seconds=1)
        )
        clock.return_value = 1.0
        with self.assertRaises(worker.ProviderError):
            instance.create_worker(NAME, key="expired")
        transport.assert_not_called()

    def test_private_error_payload_and_transport_exception_are_sanitized(self):
        for response in ((503, {}, TOKEN.encode()), OSError(TOKEN)):
            instance, transport = self.adapter(response)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(worker.ProviderUnknown) as caught:
                    instance.create_worker(NAME, key="create")
            self.assertNotIn(TOKEN, str(caught.exception) + stdout.getvalue() + stderr.getvalue())
            self.assertEqual(transport.call_count, 1)

    def test_deadline_unknown_does_not_replay_or_claim_cancellation(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        def blocked(*args):
            entered.set()
            release.wait(2)
            finished.set()
            return envelope(RESULT)

        transport = Mock(side_effect=blocked)
        instance = worker.BetaWorkerProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            transport=transport,
            limits=replace(worker.Limits(), request_seconds=0.02),
        )
        try:
            with self.assertRaises(worker.ProviderUnknown):
                instance.create_worker(NAME, key="create")
            self.assertTrue(entered.is_set())
            self.assertFalse(finished.is_set())
            with self.assertRaises(worker.ProviderError):
                instance.create_worker(NAME, key="retry")
            self.assertEqual(transport.call_count, 1)
        finally:
            release.set()
            self.assertTrue(finished.wait(1))

    def test_journal_and_receipts_exclude_credentials_and_response_prose(self):
        before, after = Mock(), Mock()
        result = {**RESULT, "unexpected_provider_prose": TOKEN}
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            instance, _ = self.adapter(
                envelope(result),
                envelope(RESULT),
                envelope(RESULT),
                before_request=before,
                after_request=after,
            )
            identity = instance.create_worker(NAME, key="create")
            receipt = instance.disable_worker(identity, key="disable")
        emitted = repr(before.call_args_list) + repr(after.call_args_list)
        emitted += repr(identity) + repr(receipt) + stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(TOKEN, emitted)
        self.assertFalse(receipt["providerQualified"])
        self.assertFalse(receipt["liveExecutionAllowed"])
        # Raw provider prose is never a required field in a sanitized receipt.
        self.assertNotIn("unexpected_provider_prose", repr(receipt))
        self.assertIn(TOKEN, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
