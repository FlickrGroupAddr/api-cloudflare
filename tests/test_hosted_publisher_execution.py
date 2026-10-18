"""Execution-entrypoint gates tested with new, wholly synthetic private packets."""

import copy
import hashlib
import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution as runtime
from scripts import hosted_publisher_execution_provider as execution_provider
from scripts import hosted_publisher_finite_client as finite_client
from scripts import hosted_publisher_operator as operator
from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_runtime as packet
from tests import test_prepare_hosted_publisher_execution as preparation
from tests.test_hosted_publisher_finite_client import phase_body
from tests.test_hosted_publisher_worker_deployment import StatefulTransport


class ExecutionRuntimeTests(unittest.TestCase):
    root: Path
    current: Path
    candidate: Path
    bundle: Path
    destination: Path
    files: dict[str, bytes]
    scope: dict
    network: Mock
    entropy: Mock

    def git_response(self, root, *arguments):
        self.assertEqual(root, self.current)
        if arguments == ("rev-parse", "HEAD"):
            return preparation.HEAD
        self.assertEqual(arguments, ("ls-tree", "-r", preparation.HEAD, "--", *packet.SOURCE_FILES))
        return "\n".join(
            "100644 blob "
            + hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            + "\t"
            + name
            for name, raw in self.files.items()
        )

    def write(self, name, value):
        path = self.root / name
        raw = json.dumps(value).encode() if isinstance(value, dict) else value
        path.write_bytes(raw)
        return path, boundary.sha2_256(raw)

    def setUp(self):
        # Reuse only the sealed suite's explicitly synthetic retained-source fixture.
        preparation.ExecutionPreparationTests.setUp(cast(Any, self))
        for name in packet.SOURCE_FILES:
            if name not in self.files:
                data = (
                    ".".join(map(str, sys.version_info[:3]))
                    if name == ".python-version"
                    else "synthetic-current:" + name
                ).encode()
                self.files[name] = data
                path = self.current / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        self.manifest = packet.prepare(
            self.destination,
            json.dumps(self.scope).encode(),
            self.candidate,
            self.bundle,
            self.current,
            preparation.HEAD,
            json.dumps(
                {
                    "management_address": "1.1.1.1",
                    "client_addresses": {
                        case["endpoint"]: "1.1.1.1" for case in self.scope["cases"]
                    },
                }
            ).encode(),
        )
        self.plan = boundary.load_plan((self.destination / "plan.json").read_bytes())
        self.consent = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": self.plan.digest,
            "owner": self.plan.owner,
            "actions": list(boundary.OWNER_ACTIONS),
            "decision_id": "synthetic-consent",
        }
        self.grant = {
            "grant_id": "synthetic-grant",
            "account_id": self.plan.account_id,
            "permissions": ["D1:Edit", "Workers Scripts:Edit"],
            "issued_at": self.plan.starts_at,
            "expires_at": self.plan.cleanup_deadline,
            "revocation_owner": self.plan.revocation_owner,
            "resource_scope": "exact-account-only",
            "metadata_verified": True,
        }
        consent_path, consent_digest = self.write("consent.json", self.consent)
        grant_path, grant_digest = self.write("grant.json", self.grant)
        evidence_path, evidence_digest = self.write(
            "grant-evidence.txt", b"SYNTHETIC ONLY evidence"
        )
        self.approval = {
            "schema_version": 1,
            "granted": True,
            "owner": self.plan.owner,
            "decision_id": "synthetic-approval",
            "packet_digest": self.manifest["packet_sha2_256"],
            "plan_digest": self.plan.digest,
            "consent_digest": consent_digest,
            "grant_digest": grant_digest,
            "grant_evidence_digest": evidence_digest,
            "credential_sha2_256": boundary.sha2_256(b"synthetic-private-operator-token"),
            "source_commit": preparation.HEAD,
            "human_approval": {
                "reference": "synthetic-owner-approval",
                "evidence_sha2_256": "c" * 64,
                "recorded_at": "2026-10-17T12:00:00Z",
            },
            "isolation": {
                "exclusive_owner": True,
                "synthetic_only": True,
                "no_production_references": True,
                "journal_outside_resources": True,
            },
            "expires_at": self.plan.expires_at,
            "actions": list(boundary.OWNER_ACTIONS),
        }
        approval_path, approval_digest = self.write("approval.json", self.approval)
        credential_path, _ = self.write("credential.txt", b"synthetic-private-operator-token")
        self.inputs = runtime.RuntimeInputs(
            packet=self.destination,
            packet_digest=self.manifest["packet_sha2_256"],
            consent=consent_path,
            consent_digest=consent_digest,
            grant=grant_path,
            grant_digest=grant_digest,
            approval=approval_path,
            approval_digest=approval_digest,
            grant_evidence=evidence_path,
            credential=credential_path,
            journal=self.root / "run.sqlite",
            source_root=self.candidate,
            bundle=self.bundle,
            current_root=self.current,
        )
        self.now = boundary.utc_time("2026-10-17T12:01:00Z").timestamp()
        patch.object(runtime, "_running_root", return_value=self.current).start()
        # Synthetic ACL metadata seam: no native security API or actual private input.
        patch.object(runtime, "_windows_private").start()

    def check(self, inputs=None, now=None):
        return runtime.validate_inputs(
            inputs or self.inputs,
            now=datetime.fromtimestamp(self.now if now is None else now, UTC),
        )

    def test_synthetic_exact_packet_validates_without_credentials_or_network(self):
        checked = self.check()
        self.assertEqual(checked.plan.digest, self.plan.digest)
        self.network.assert_not_called()
        self.entropy.assert_not_called()

    def test_private_read_accepts_stable_descriptor_and_path_with_windows_timestamp_semantics(self):
        path, _ = self.write("stable-synthetic.txt", b"synthetic stable bytes\r\n")
        self.assertEqual(runtime._private_bytes(path), b"synthetic stable bytes\r\n")

    def test_changed_same_length_credential_never_constructs_provider(self):
        replacement = b"synthetic-private-operatpr-token"
        self.assertEqual(len(replacement), self.inputs.credential.stat().st_size)
        self.inputs.credential.write_bytes(replacement)
        factory = Mock()
        with self.assertRaises(operator.OperatorRefused):
            runtime.run(
                self.inputs,
                wall_clock=lambda: self.now,
                monotonic=lambda: 100,
                provider_factory=factory,
                client_factory=Mock(),
            )
        factory.assert_not_called()

    def test_existing_stop_refuses_before_token_or_provider_construction(self):
        stop, _ = self.write("stop", b"stop")
        factory = Mock()
        with patch.object(runtime, "_private_bytes", wraps=runtime._private_bytes) as reads:
            with self.assertRaises(operator.OperatorRefused):
                runtime.run(
                    replace(self.inputs, stop_file=stop),
                    wall_clock=lambda: self.now,
                    monotonic=lambda: 100,
                    provider_factory=factory,
                    client_factory=Mock(),
                )
        factory.assert_not_called()
        self.assertFalse(
            any(call.args[0] == self.inputs.credential for call in reads.call_args_list)
        )

    def test_stop_is_terminal_after_permit_creation_even_if_file_is_removed(self):
        stop = self.root / "late-stop"
        inputs = replace(self.inputs, stop_file=stop)
        permit = runtime.ExecutionPermit(
            inputs,
            self.check(inputs),
            cleanup_only=False,
            wall_clock=lambda: self.now,
            monotonic=lambda: 100,
        )
        permit.authorize()
        stop.write_bytes(b"stop")
        with self.assertRaises(operator.OperatorRefused):
            permit.authorize()
        stop.unlink()
        with self.assertRaises(operator.OperatorRefused):
            permit.authorize()

    def cleanup_reservations(self, *, expired=False):
        authority = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": self.plan.digest,
            "owner": self.plan.cleanup_owner,
            "decision_id": "synthetic-cleanup-budget",
            "expires_at": self.plan.cleanup_deadline,
            "actions": [
                "fence_dispatch",
                "disable_access",
                "delete_owned_worker",
                "dispose_exact_synthetic_d1",
            ],
        }
        cleanup_path, cleanup_digest = self.write("cleanup-budget.json", authority)
        inputs = replace(self.inputs, cleanup=cleanup_path, cleanup_digest=cleanup_digest)
        started = self.now - 7201 if expired else self.now
        with operator.DurableJournal(inputs.journal, self.plan.digest) as journal:
            journal.reserve("execution:authority", {"planDigest": self.plan.digest})
            journal.complete(
                "execution:authority",
                {
                    "packetDigest": inputs.packet_digest,
                    "approvalDigest": inputs.approval_digest,
                    "owner": self.plan.owner,
                    "startedAt": started,
                    "adapterDeadline": started + 7200,
                    "lifecycleDeadline": started + self.plan.budgets.lifecycle_seconds,
                },
            )
            journal.reserve("execution:started", {"planDigest": self.plan.digest})
            journal.complete("execution:started", {"status": "admitted_once"})
            journal.reserve(
                "provider:synthetic-unknown",
                {
                    "requestBytes": 1,
                    "mutation": True,
                    "reservedResponseBytes": 1 if expired else operator.PROVIDER_RESPONSE_BYTES,
                },
            )
            journal.unknown("provider:synthetic-unknown", "synthetic_lost_response")
        return inputs

    def assert_cleanup_refused_before_token(self, inputs):
        factory = Mock()
        with patch.object(runtime, "_private_bytes", wraps=runtime._private_bytes) as reads:
            with self.assertRaises(operator.OperatorRefused):
                runtime.run(
                    inputs,
                    cleanup_only=True,
                    wall_clock=lambda: self.now,
                    monotonic=lambda: 100,
                    provider_factory=factory,
                    client_factory=Mock(),
                )
        factory.assert_not_called()
        self.assertFalse(any(call.args[0] == inputs.credential for call in reads.call_args_list))

    def test_cleanup_unknown_response_reservation_exhaustion_refuses_before_token(self):
        self.assert_cleanup_refused_before_token(self.cleanup_reservations())

    def test_cleanup_restores_original_adapter_deadline_before_token(self):
        self.assert_cleanup_refused_before_token(self.cleanup_reservations(expired=True))

    def test_missing_or_changed_independent_digest_consent_grant_and_approval_refuse(self):
        for field in ("packet_digest", "consent_digest", "grant_digest", "approval_digest"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(replace(self.inputs, **{field: "0" * 64}))
        for name, document in (
            ("consent", self.consent),
            ("grant", self.grant),
            ("approval", self.approval),
        ):
            broken = copy.deepcopy(document)
            if name == "grant":
                broken["account_id"] = "b" * 32
            else:
                broken["granted"] = False
            path, digest = self.write(name + "-bad.json", broken)
            with self.subTest(document=name), self.assertRaises(ValueError):
                self.check(replace(self.inputs, **{name: path, name + "_digest": digest}))
        self.network.assert_not_called()

    def test_source_current_bundle_and_evidence_drift_refuse_before_io(self):
        for path in (
            self.current / packet.SOURCE_FILES[0],
            self.bundle,
            self.inputs.grant_evidence,
            self.destination / "source" / packet.SOURCE_FILES[-1],
        ):
            original = path.read_bytes()
            try:
                path.write_bytes(original + b"drift")
                with self.subTest(path=path.name), self.assertRaises(ValueError):
                    self.check()
            finally:
                path.write_bytes(original)
        self.network.assert_not_called()

    def test_invalid_authority_and_elapsed_deadline_never_construct_providers_or_read_token(self):
        for inputs, now in (
            (replace(self.inputs, approval_digest="0" * 64), self.now),
            (self.inputs, boundary.utc_time(self.plan.expires_at).timestamp()),
        ):
            provider_factory, client_factory = Mock(), Mock()
            with patch.object(runtime, "_private_bytes", wraps=runtime._private_bytes) as reads:
                with self.subTest(now=now), self.assertRaises(ValueError):
                    runtime.run(
                        inputs,
                        wall_clock=lambda now=now: now,
                        monotonic=lambda: 100,
                        provider_factory=provider_factory,
                        client_factory=client_factory,
                    )
            self.assertFalse(
                any(call.args[0] == inputs.credential for call in reads.call_args_list)
            )
            provider_factory.assert_not_called()
            client_factory.assert_not_called()
        self.assertFalse(self.inputs.journal.exists())

    def test_new_runtime_uses_one_journal_budget_no_replay_and_known_only_cleanup(self):
        transport = StatefulTransport()
        requests, providers = [], []

        def provider_factory(plan, token, manifest, permit):
            adapter = execution_provider.ExecutionBetaPublisherProvider(
                plan.account_id,
                token,
                [case.worker_name for case in plan.cases],
                [case.d1_name for case in plan.cases],
                permit=permit,
                management_address=manifest["network"]["management_address"],
                exclusive_owner=True,
                transport=transport,
                monotonic=lambda: 100,
            )
            providers.append(adapter)
            return adapter

        def client_factory(plan, manifest, permit):
            def dispatch(request):
                permit.authorize()
                requests.append(request)
                body = phase_body(
                    request.url.rsplit("/", 1)[-1], request.headers["X-Probe-Scenario"]
                )
                return finite_client.Response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                    },
                    json.dumps(body).encode(),
                )

            return dispatch

        self.entropy.side_effect = None
        self.entropy.return_value = "d" * 64
        kwargs = {
            "wall_clock": lambda: self.now,
            "monotonic": lambda: 100,
            "provider_factory": provider_factory,
            "client_factory": client_factory,
        }
        result = runtime.run(self.inputs, **kwargs)
        self.assertEqual(result["status"], "phases_complete_cleanup_pending")
        self.assertEqual(len(requests), 28)
        self.assertEqual(len(transport.databases), 4)
        self.assertEqual(len(transport.workers), 4)
        self.assertTrue(providers[0]._closed)
        self.assertEqual(providers[0].before_request.__name__, "_before_request")
        self.assertEqual(providers[0].after_request.__name__, "_after_request")
        self.assertEqual(providers[0]._token, "")
        calls_before = len(transport.calls)
        with self.assertRaises(operator.OperatorRefused):
            runtime.run(self.inputs, **kwargs)
        self.assertEqual(len(transport.calls), calls_before)
        self.assertEqual(len(providers), 1)
        authority = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": self.plan.digest,
            "owner": self.plan.cleanup_owner,
            "decision_id": "synthetic-cleanup",
            "expires_at": self.plan.cleanup_deadline,
            "actions": [
                "fence_dispatch",
                "disable_access",
                "delete_owned_worker",
                "dispose_exact_synthetic_d1",
            ],
        }
        cleanup_path, cleanup_digest = self.write("cleanup.json", authority)
        cleanup_inputs = replace(self.inputs, cleanup=cleanup_path, cleanup_digest=cleanup_digest)
        disposed = runtime.run(cleanup_inputs, cleanup_only=True, **kwargs)
        self.assertEqual(disposed["status"], "resources_disposed")
        self.assertEqual(disposed["querySettlement"], "unproved")
        self.assertEqual(transport.databases, {})
        self.assertEqual(transport.workers, {})
        self.assertEqual(len(requests), 28)
        with operator.DurableJournal(self.inputs.journal, self.plan.digest) as journal:
            snapshot = journal.snapshot()
        provider_events = [event for key, event in snapshot.items() if key.startswith("provider:")]
        self.assertEqual(len(provider_events), len(transport.calls))
        self.assertLessEqual(len(provider_events), self.plan.budgets.provider_calls)
        self.assertLessEqual(
            sum(event["payload"]["mutation"] for event in provider_events),
            self.plan.budgets.provider_mutations,
        )
        self.assertEqual(snapshot["execution:started"]["state"], "complete")
        self.assertEqual(
            snapshot["execution:authority"]["receipt"]["packetDigest"], self.inputs.packet_digest
        )
        before_repeat = len(transport.calls)
        with self.assertRaises(operator.OperatorRefused):
            runtime.run(cleanup_inputs, cleanup_only=True, **kwargs)
        self.assertEqual(len(transport.calls), before_repeat)
        self.network.assert_not_called()
