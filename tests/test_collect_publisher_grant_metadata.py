"""Synthetic evidence-only token-metadata tests; no provider or native ACL access."""

from __future__ import annotations

import copy
import hashlib
import http.client
import io
import json
import socket
import sqlite3
import ssl
import tempfile
import traceback
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Inexact, localcontext
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import collect_publisher_grant_metadata as metadata
from scripts import hosted_publisher_execution as execution
from scripts import hosted_publisher_finite_client as finite

TEST_TOKEN = b"synthetic-test-credential-A1234567890"
READER_TOKEN = b"synthetic-reader-credential-B1234567890"
TEST_ID = "a" * 32
READER_ID = "b" * 32
HEAD = "1" * 40
START = "2026-10-18T12:00:00Z"
END = "2026-10-18T12:20:00Z"
NOW = datetime(2026, 10, 18, 12, 1, tzinfo=UTC).timestamp()
ISSUED = "2026-10-18T11:55:00.123456789Z"
NOT_BEFORE = "2026-10-18T11:56:00.987654321Z"
EXPIRES = "2026-10-19T00:00:00.123456789Z"


def encoded(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_result(token_id: str) -> dict[str, Any]:
    return {
        "id": token_id,
        "status": "active",
        "not_before": NOT_BEFORE,
        "expires_on": EXPIRES,
    }


def envelope(result: Any) -> dict[str, Any]:
    return {"success": True, "errors": [], "messages": [], "result": result}


class MetadataCollectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-metadata-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.calls: list[finite.Request] = []
        self.loads: list[Path] = []
        self.tick = 100.0
        self.now = NOW
        self.addCleanup(patch.stopall)
        self.network = patch.object(
            socket, "socket", side_effect=AssertionError("no network")
        ).start()
        self.dns = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS")).start()
        # Replace only metadata inspection: all file operations use fresh synthetic files.
        patch.object(execution, "_windows_private").start()
        patch.object(metadata, "_assert_private").start()
        patch.object(metadata, "_validate_source").start()
        self.plan = {
            "schema_version": 1,
            "purpose": "publisher_grant_metadata_evidence",
            "owner": "Terry",
            "source_commit": HEAD,
            "source_sha2_256": {name: "c" * 64 for name in metadata.SOURCE_FILES},
            "starts_at": START,
            "expires_at": END,
            "api_address": "1.1.1.1",
            "test_credential": str(self.root / "test.txt"),
            "reader_credential": str(self.root / "reader.txt"),
            "evidence": str(self.root / "evidence.json"),
            "journal": str(self.root / "journal.json"),
            "claim": str(self.root / "claim.json"),
            "discovery": "test_verify_id_only",
            "actions": list(metadata.ACTIONS),
        }
        self.write("test.txt", TEST_TOKEN)
        self.write("reader.txt", READER_TOKEN)
        human, human_digest = self.write("human.txt", b"SYNTHETIC owner approval only")
        self.approval = {
            "schema_version": 1,
            "granted": True,
            "owner": "Terry",
            "decision_id": "synthetic-decision",
            "plan_digest": "",
            "source_commit": HEAD,
            "human_approval": {
                "reference": "synthetic-human-reference",
                "evidence_sha2_256": human_digest,
                "recorded_at": START,
            },
            "owner_provisioned": {"test": True, "reader": True},
            "reader_policy_limitation_acknowledged": True,
            "revocation_acknowledged": True,
            "actions": list(metadata.ACTIONS),
            "expires_at": END,
        }
        self.human = human
        self.refresh_inputs()
        self.details = {
            **verify_result(TEST_ID),
            "name": "synthetic test token",
            "issued_on": ISSUED,
            "policies": [
                {
                    "effect": "allow",
                    "resources": {"com.cloudflare.api.account." + "d" * 32: "*"},
                    "permission_groups": [{"id": "e" * 32, "name": "Workers Scripts Write"}],
                }
            ],
        }
        self.responses: list[Any] = [
            envelope(verify_result(TEST_ID)),
            envelope(verify_result(READER_ID)),
            envelope(copy.deepcopy(self.details)),
        ]

    def refresh_inputs(self):
        plan_path, plan_digest = self.write("plan.json", self.plan)
        self.approval["plan_digest"] = plan_digest
        approval_path, approval_digest = self.write("approval.json", self.approval)
        self.inputs = metadata.RuntimeInputs(
            plan=plan_path,
            plan_digest=plan_digest,
            approval=approval_path,
            approval_digest=approval_digest,
            human_evidence=self.human,
            source_root=self.source,
        )

    def reset_attempt(self):
        for name in ("claim", "journal", "evidence"):
            path = Path(self.plan[name])
            if path.exists():
                path.unlink()
        for suffix in (".owner", "-journal"):
            sidecar = Path(self.plan["journal"] + suffix)
            if sidecar.exists():
                sidecar.unlink()
        self.calls.clear()
        self.loads.clear()

    def write(self, name: str, value: Any) -> tuple[Path, str]:
        path = self.root / name
        raw = value if isinstance(value, bytes) else encoded(value)
        path.write_bytes(raw)
        return path, digest(raw)

    def load(self, path: Path, maximum: int) -> bytes:
        self.assertEqual(maximum, 2048)
        self.loads.append(path)
        self.assertTrue(Path(self.plan["claim"]).exists(), "claim must precede secret reads")
        self.assertTrue(Path(self.plan["journal"]).exists(), "journal must precede secret reads")
        return path.read_bytes()

    def transport(self, request: finite.Request) -> finite.Response:
        self.calls.append(request)
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return finite.Response(200, {"content-type": "application/json"}, encoded(response), 2048)

    def run_collection(self, **kwargs):
        return metadata.run(
            self.inputs,
            wall_clock=lambda: self.now,
            monotonic=lambda: self.tick,
            transport=kwargs.pop("transport", self.transport),
            credential_loader=kwargs.pop("credential_loader", self.load),
            **kwargs,
        )

    def test_concrete_collector_explicitly_selects_cookie_discard_on_all_three_gets(self):
        def pinned(request, address, clock, guard, *, discard_set_cookie=False):
            self.assertTrue(discard_set_cookie)
            self.assertEqual(str(address), "1.1.1.1")
            self.assertEqual(clock(), self.tick)
            guard()
            self.assertNotIn("Cookie", request.headers)
            self.assertNotIn(b"Cookie:", request.wire)
            return self.transport(request)

        with patch.object(metadata, "_pinned_https", side_effect=pinned) as concrete:
            result = self.run_collection(transport=None)
        self.assertEqual(result["requests"], 3)
        self.assertEqual(concrete.call_count, 3)
        self.network.assert_not_called()
        self.dns.assert_not_called()

    def assert_no_evidence(self):
        path = Path(self.plan["evidence"])
        self.assertTrue(not path.exists() or path.read_bytes() == b"")

    def assert_sanitized(self, value: Any):
        rendered = str(value)
        for secret in (TEST_TOKEN.decode(), READER_TOKEN.decode(), "provider-secret-error"):
            self.assertNotIn(secret, rendered)

    def assert_failure_diagnostic(self, operation, *, stage, category, cause, requests):
        output = io.StringIO()
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            self.assertRaises(metadata.MetadataCollectionRefused) as caught,
        ):
            operation()
        failure = caught.exception
        expected = f"metadata_failed:{stage}:{category}:{cause}"
        self.assertEqual(failure.diagnostic, expected)
        self.assertEqual((failure.stage, failure.category, failure.cause), (stage, category, cause))
        self.assertEqual(failure.requests, requests)
        self.assertEqual(len(self.calls), requests)
        self.assertLessEqual(len(expected), 120)
        self.assertEqual(output.getvalue(), "")
        self.assertIsNone(failure.__cause__)
        self.assertIsNone(failure.__context__)
        self.assert_sanitized(vars(failure))
        self.assert_sanitized("".join(traceback.format_exception(failure)))
        self.assert_no_evidence()
        return failure

    def assert_failed_journal(self, failure, *, requests):
        path = Path(self.plan["journal"])
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as connection:
            rows = connection.execute(
                "SELECT key,state,receipt FROM intents ORDER BY rowid"
            ).fetchall()
        retained = {key: (state, json.loads(receipt)) for key, state, receipt in rows}
        self.assertEqual(retained["metadata:started"], ("unknown", {"reason": failure.diagnostic}))
        for index in range(1, requests + 1):
            key = f"metadata:request:{index}"
            expected = (
                ("unknown", {"reason": failure.diagnostic})
                if index == requests
                else ("complete", {"status": "response_retained_privately"})
            )
            self.assertEqual(retained[key], expected)
        self.assertEqual(len(retained), requests + 1)
        for name in ("claim", "journal", "journal.json.owner"):
            candidate = self.root / name if name.endswith(".owner") else Path(self.plan[name])
            self.assertTrue(candidate.exists())
            self.assert_sanitized(candidate.read_bytes())
        self.loads.clear()
        with self.assertRaises(metadata.MetadataCollectionRefused):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.assertEqual(len(self.calls), requests)
        self.network.assert_not_called()
        self.dns.assert_not_called()

    def test_transport_failure_diagnostics_are_static_at_each_once_only_dispatch(self):
        secret = "provider-secret-error " + TEST_TOKEN.decode() + " " + READER_TOKEN.decode()
        errors = (
            (ssl.SSLCertVerificationError(secret), "tls", "certificate_verification"),
            (ssl.SSLError(secret), "tls", "handshake_or_protocol"),
            (TimeoutError(secret), "timeout", "deadline_or_socket"),
            (ConnectionRefusedError(secret), "network", "connection_refused"),
            (ConnectionResetError(secret), "network", "connection_reset"),
            (OSError(secret), "network", "io_error"),
            (http.client.IncompleteRead(secret.encode()), "http", "protocol_or_incomplete"),
            (
                metadata.UnknownOutcome("execution_response_framing_missing"),
                "refusal",
                "execution_response_framing_missing",
            ),
            (
                metadata.UnknownOutcome("execution_response_incomplete"),
                "refusal",
                "execution_response_incomplete",
            ),
            *(
                (metadata.UnknownOutcome(code), "refusal", code)
                for code in (
                    "execution_duplicate_response_header_framing",
                    "execution_duplicate_response_header_content",
                    "execution_duplicate_response_header_auth",
                    "execution_duplicate_response_header_other",
                )
            ),
            (RuntimeError(secret), "unexpected", "unclassified"),
        )
        for index in range(3):
            original = self.responses[index]
            for error, category, cause in errors:
                with self.subTest(dispatch=index + 1, category=category, cause=cause):
                    self.responses[index] = error
                    failure = self.assert_failure_diagnostic(
                        self.run_collection,
                        stage=f"request{index + 1}_transport",
                        category=category,
                        cause=cause,
                        requests=index + 1,
                    )
                    self.assertEqual(failure.response_wire_bytes, index * 2048)
                    self.assert_failed_journal(failure, requests=index + 1)
                    self.reset_attempt()
            self.responses[index] = original

    def test_provider_refusal_diagnostics_distinguish_status_framing_schema_and_time(self):
        cases = (
            (
                finite.Response(403, {}, b"provider-secret-error " + TEST_TOKEN, 2048),
                "metadata_provider_nonsuccess",
            ),
            (
                finite.Response(200, {}, encoded(self.responses[0]), 2048),
                "metadata_response_headers_or_private_material_refused",
            ),
            (
                finite.Response(200, {"content-type": "application/json"}, b"{", 2048),
                "metadata_json_refused",
            ),
            (
                finite.Response(200, {"content-type": "application/json"}, encoded({}), 2048),
                "metadata_closed_shape_required",
            ),
            (
                finite.Response(
                    200,
                    {"content-type": "application/json"},
                    encoded(envelope({**verify_result(TEST_ID), "status": "expired"})),
                    2048,
                ),
                "metadata_active_verify_required",
            ),
            (finite.Response(200, {}, b"", 65537), "metadata_wire_accounting_refused"),
        )
        for response, cause in cases:
            with self.subTest(cause=cause):

                def refused(request, response=response):
                    self.calls.append(request)
                    return response

                failure = self.assert_failure_diagnostic(
                    lambda: self.run_collection(transport=refused),
                    stage="request1_validate",
                    category="refusal",
                    cause=cause,
                    requests=1,
                )
                self.assert_failed_journal(failure, requests=1)
                self.reset_attempt()

    def test_untrusted_refusal_messages_and_exception_formatters_cannot_enter_diagnostics(self):
        secret = "provider-secret-error " + TEST_TOKEN.decode()

        class HostileError(RuntimeError):
            def __str__(self):
                raise AssertionError("exception message must not be inspected")

            def __repr__(self):
                raise AssertionError("exception representation must not be inspected")

        for error, category, cause in (
            (metadata.OperatorRefused(secret), "refusal", "unrecognized"),
            (
                metadata.OperatorRefused("metadata_json_refused " + secret),
                "refusal",
                "unrecognized",
            ),
            (
                metadata.OperatorRefused("metadata_failed:request1_transport:" + secret),
                "refusal",
                "unrecognized",
            ),
            (HostileError(secret), "unexpected", "unclassified"),
        ):
            with self.subTest(category=category, cause=cause):
                self.responses[0] = error
                failure = self.assert_failure_diagnostic(
                    self.run_collection,
                    stage="request1_transport",
                    category=category,
                    cause=cause,
                    requests=1,
                )
                self.assert_failed_journal(failure, requests=1)
                self.reset_attempt()

    def test_credential_failure_has_private_diagnostic_without_any_dispatch(self):
        def failed_loader(path, maximum):
            self.load(path, maximum)
            raise PermissionError("provider-secret-error " + READER_TOKEN.decode())

        failure = self.assert_failure_diagnostic(
            lambda: self.run_collection(credential_loader=failed_loader),
            stage="credentials",
            category="storage",
            cause="permission_denied",
            requests=0,
        )
        self.assert_failed_journal(failure, requests=0)

    def test_expired_budget_diagnostics_distinguish_before_and_after_dispatch(self):
        def delayed(path, maximum):
            value = self.load(path, maximum)
            self.tick += 1201
            return value

        failure = self.assert_failure_diagnostic(
            lambda: self.run_collection(credential_loader=delayed),
            stage="request1_fence",
            category="refusal",
            cause="metadata_remaining_budget_exhausted",
            requests=0,
        )
        self.assert_failed_journal(failure, requests=0)
        self.reset_attempt()
        self.tick = 100.0

        def expires(request):
            response = self.transport(request)
            self.tick += 1201
            return response

        failure = self.assert_failure_diagnostic(
            lambda: self.run_collection(transport=expires),
            stage="request1_validate",
            category="refusal",
            cause="metadata_remaining_budget_exhausted",
            requests=1,
        )
        self.assert_failed_journal(failure, requests=1)

    def test_authority_change_after_first_dispatch_stops_with_bounded_diagnostic(self):
        def changes_authority(request):
            response = self.transport(request)
            self.human.write_bytes(b"changed synthetic human authority")
            return response

        failure = self.assert_failure_diagnostic(
            lambda: self.run_collection(transport=changes_authority),
            stage="request1_validate",
            category="refusal",
            cause="metadata_human_evidence_mismatch",
            requests=1,
        )
        self.assert_failed_journal(failure, requests=1)

    def test_nested_secret_exception_chains_are_not_retained_by_public_failure(self):
        def chained(request):
            self.calls.append(request)
            try:
                raise OSError("provider-secret-error " + READER_TOKEN.decode())
            except OSError as inner:
                raise TimeoutError("provider-secret-error " + TEST_TOKEN.decode()) from inner

        failure = self.assert_failure_diagnostic(
            lambda: self.run_collection(transport=chained),
            stage="request1_transport",
            category="timeout",
            cause="deadline_or_socket",
            requests=1,
        )
        self.assert_failed_journal(failure, requests=1)

    def test_receipt_write_failure_keeps_original_diagnostic_and_spent_intents(self):
        self.responses[0] = TimeoutError("provider-secret-error " + TEST_TOKEN.decode())
        with patch.object(
            metadata.DurableJournal,
            "unknown",
            side_effect=OSError("provider-secret-error " + READER_TOKEN.decode()),
        ):
            failure = self.assert_failure_diagnostic(
                self.run_collection,
                stage="request1_transport",
                category="timeout",
                cause="deadline_or_socket",
                requests=1,
            )
        self.assertEqual(failure.response_wire_bytes, 0)
        path = Path(self.plan["journal"])
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as connection:
            rows = connection.execute(
                "SELECT key,state,receipt FROM intents ORDER BY rowid"
            ).fetchall()
        self.assertEqual(
            rows, [("metadata:started", "intent", "{}"), ("metadata:request:1", "intent", "{}")]
        )
        self.assert_sanitized(path.read_bytes())
        self.assertTrue(Path(self.plan["claim"]).exists())
        self.loads.clear()
        with self.assertRaises(metadata.MetadataCollectionRefused):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.assertEqual(len(self.calls), 1)

    def test_hostile_exception_type_hooks_are_never_invoked_at_failure_boundaries(self):
        invoked = []
        secret = "provider-secret-error " + TEST_TOKEN.decode()

        class HostileClassAttribute(RuntimeError):
            def __getattribute__(self, name):
                if name == "__class__":
                    invoked.append("class_attribute")
                    raise RuntimeError(secret)
                return super().__getattribute__(name)

        class HostileMeta(type):
            def __eq__(cls, other):
                invoked.append("metaclass_equality")
                raise RuntimeError(secret)

            __hash__ = type.__hash__

        class HostileTypeEquality(RuntimeError, metaclass=HostileMeta):
            pass

        for error_type in (HostileClassAttribute, HostileTypeEquality):
            for boundary in ("inputs", "clock", "request1_transport"):
                with self.subTest(error_type=error_type.__name__, boundary=boundary):

                    def fail(error_type=error_type):
                        raise error_type(secret)

                    def failed_transport(request):
                        self.calls.append(request)
                        fail()

                    def operation(boundary=boundary):
                        return metadata.run(
                            self.inputs,
                            wall_clock=fail if boundary == "inputs" else lambda: self.now,
                            monotonic=fail if boundary == "clock" else lambda: self.tick,
                            transport=failed_transport,
                            credential_loader=self.load,
                        )

                    requests = 1 if boundary == "request1_transport" else 0
                    failure = self.assert_failure_diagnostic(
                        operation,
                        stage=boundary,
                        category="unexpected",
                        cause="unclassified",
                        requests=requests,
                    )
                    self.assertEqual(invoked, [])
                    if requests:
                        self.assert_failed_journal(failure, requests=1)
                    else:
                        self.assertEqual(self.loads, [])
                        for name in ("claim", "journal", "evidence"):
                            self.assertFalse(Path(self.plan[name]).exists())
                    self.reset_attempt()

    def test_source_refusal_uses_exact_closed_cause_before_credentials(self):
        literal = "Exact separately reviewed committed source required"
        for message, category, cause in (
            (literal, "refusal", "source_commit_refused"),
            (
                literal + " provider-secret-error " + TEST_TOKEN.decode(),
                "unexpected",
                "unclassified",
            ),
        ):
            with (
                self.subTest(category=category),
                patch.object(metadata, "_validate_source", side_effect=ValueError(message)),
            ):
                self.assert_failure_diagnostic(
                    self.run_collection,
                    stage="inputs",
                    category=category,
                    cause=cause,
                    requests=0,
                )
                self.assertEqual(self.loads, [])
                self.assertFalse(Path(self.plan["claim"]).exists())
                self.assertFalse(Path(self.plan["journal"]).exists())

    def test_invalid_authority_diagnostic_precedes_claim_credentials_and_dispatch(self):
        self.plan["discovery"] = "list_tokens"
        self.refresh_inputs()
        failure = self.assert_failure_diagnostic(
            self.run_collection,
            stage="inputs",
            category="refusal",
            cause="metadata_exact_plan_required",
            requests=0,
        )
        self.assertEqual(failure.response_wire_bytes, 0)
        self.assertEqual(self.loads, [])
        for name in ("claim", "journal", "evidence"):
            self.assertFalse(Path(self.plan[name]).exists())

    def test_exact_three_gets_bind_details_to_verified_test_id_and_separate_credentials(self):
        result = self.run_collection()
        self.assertEqual(
            [request.url for request in self.calls],
            [
                "https://api.cloudflare.com/client/v4/user/tokens/verify",
                "https://api.cloudflare.com/client/v4/user/tokens/verify",
                "https://api.cloudflare.com/client/v4/user/tokens/" + TEST_ID,
            ],
        )
        for request in self.calls:
            self.assertTrue(request.wire.startswith(b"GET "))
            self.assertLessEqual(request.timeout, 20)
            self.assertGreater(request.timeout, 0)
            self.assertLessEqual(request.max_response_bytes, 65536)
            self.assertLessEqual(request.deadline - self.tick, 1200)
        self.assertEqual(
            [r.headers["Authorization"] for r in self.calls],
            [
                "Bearer " + TEST_TOKEN.decode(),
                "Bearer " + READER_TOKEN.decode(),
                "Bearer " + READER_TOKEN.decode(),
            ],
        )
        self.assertEqual(
            self.loads, [Path(self.plan["test_credential"]), Path(self.plan["reader_credential"])]
        )
        self.assert_sanitized(result)
        self.network.assert_not_called()
        self.dns.assert_not_called()

    def test_exact_provider_fractional_timestamps_and_full_policy_survive_private_evidence(self):
        self.details["condition"] = {"request_ip": {"in": ["192.0.2.0/24"]}}
        self.details["policies"][0]["permission_groups"][0]["meta"] = {"key": "value"}
        self.responses[2] = envelope(copy.deepcopy(self.details))
        self.run_collection()
        evidence = Path(self.plan["evidence"]).read_text()
        self.assertIn(ISSUED, evidence)
        self.assertIn(NOT_BEFORE, evidence)
        self.assertIn(EXPIRES, evidence)
        self.assertIn("192.0.2.0/24", evidence)
        self.assertIn("Workers Scripts Write", evidence)
        self.assertIn('"key"', evidence)
        self.assertNotIn('"issued_at"', evidence)
        self.assertNotIn('"metadata_verified"', evidence)
        self.assert_sanitized(evidence)

    def test_late_year_eighteen_digit_metadata_is_exact_under_hostile_decimal_contexts(self):
        verified = {
            "id": TEST_ID,
            "status": "active",
            "not_before": "9999-12-31T23:59:57.987654321987654321Z",
            "expires_on": "9999-12-31T23:59:59.123456789123456789Z",
        }
        details = {
            **self.details,
            **verified,
            "issued_on": "9999-12-31T23:59:56.123456789123456789Z",
        }
        original = copy.deepcopy(details)
        for precision in (2, 6, 28, 80):
            with self.subTest(precision=precision), localcontext() as context:
                context.prec = precision
                context.traps[Inexact] = True
                response = finite.Response(
                    200, {"content-type": "application/json"}, encoded(envelope(details)), 2048
                )
                retained = metadata.validate_response(
                    response,
                    details=True,
                    verified=verified,
                    now=metadata._now(lambda: 253402300798),
                )
                self.assertEqual(retained["result"], original)
                for field, changed in (
                    ("expires_on", "9999-12-31T23:59:59.123456789123456788Z"),
                    ("not_before", "9999-12-31T23:59:57.987654321987654320Z"),
                ):
                    altered = envelope({**details, field: changed})
                    response = replace(response, body=encoded(altered))
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        metadata.validate_response(
                            response,
                            details=True,
                            verified=verified,
                            now=metadata._now(lambda: 253402300798),
                        )
        self.assertEqual(details, original)

    def test_current_fractional_evidence_survives_hostile_decimal_context(self):
        with localcontext() as context:
            context.prec = 6
            context.traps[Inexact] = True
            self.run_collection()
        evidence = Path(self.plan["evidence"]).read_text()
        for exact in (ISSUED, NOT_BEFORE, EXPIRES):
            self.assertIn(exact, evidence)

    def test_unicode_escaped_credential_echo_cannot_reach_private_evidence(self):
        details = {**self.details, "name": TEST_TOKEN.decode()}
        escaped = encoded(envelope(details)).replace(
            TEST_TOKEN, ("\\u0073" + TEST_TOKEN.decode()[1:]).encode()
        )
        self.assertNotIn(TEST_TOKEN, escaped)

        def escaped_echo(request):
            if len(self.calls) < 2:
                return self.transport(request)
            self.calls.append(request)
            return finite.Response(200, {"content-type": "application/json"}, escaped, 2048)

        with self.assertRaises(ValueError) as caught:
            self.run_collection(transport=escaped_echo)
        self.assertEqual(len(self.calls), 3)
        self.assert_sanitized(caught.exception)
        self.assert_no_evidence()

    def test_planned_unicode_token_name_and_empty_permission_metadata_are_retained(self):
        name = "FGA publisher qualification \u2014 temporary"
        self.responses[2]["result"]["name"] = name
        group = self.responses[2]["result"]["policies"][0]["permission_groups"][0]
        for provider_meta, group_name in (
            ({}, "Workers Scripts \u2014 Write"),
            ({"description": ""}, ""),
        ):
            group["meta"] = provider_meta
            group["name"] = group_name
            with self.subTest(meta=provider_meta):
                self.run_collection()
                evidence = json.loads(Path(self.plan["evidence"]).read_bytes())
                retained = evidence["responses"][metadata.ACTIONS[2]]["result"]
                self.assertEqual(retained["name"], name)
                retained_group = retained["policies"][0]["permission_groups"][0]
                self.assertEqual(retained_group["meta"], provider_meta)
                self.assertEqual(retained_group["name"], group_name)
            self.reset_attempt()

    def test_empty_provider_ip_lists_preserve_no_restriction_evidence_after_three_gets(self):
        condition = {"request_ip": {"in": [], "not_in": []}}
        self.responses[2]["result"]["condition"] = copy.deepcopy(condition)
        result = self.run_collection()
        self.assertEqual(result["requests"], 3)
        self.assertEqual(len(self.calls), 3)
        evidence = json.loads(Path(self.plan["evidence"]).read_bytes())
        retained = evidence["responses"][metadata.ACTIONS[2]]["result"]
        self.assertEqual(retained["condition"], condition)
        self.assert_sanitized(evidence)

    def test_provider_ip_conditions_reject_bad_cidr_nonlists_and_oversized_lists(self):
        for rules in (["not-a-cidr"], "192.0.2.0/24", None, ["192.0.2.0/24"] * 65):
            for key in ("in", "not_in"):
                self.responses[2]["result"]["condition"] = {"request_ip": {key: rules}}
                with (
                    self.subTest(key=key, rules_type=type(rules).__name__),
                    self.assertRaises(ValueError),
                ):
                    self.run_collection()
                self.assertEqual(len(self.calls), 3)
                self.assert_no_evidence()
                self.reset_attempt()

    def test_provider_names_reject_controls_surrogates_and_unbounded_strings(self):
        for name in ("bad\nname", "bad\x00name", "bad\ud800name", "a" * 481, "\u2014" * 161):
            self.responses[2]["result"]["name"] = name
            with self.subTest(name=ascii(name)), self.assertRaises(ValueError):
                self.run_collection()
            self.assertEqual(len(self.calls), 3)
            self.assert_no_evidence()
            self.reset_attempt()

    def test_invalid_nonsecret_plan_and_authority_refuse_before_claim_or_credentials(self):
        cases = [
            ("plan", "discovery", "list_tokens"),
            ("plan", "api_address", "api.cloudflare.com"),
            ("plan", "api_address", "127.0.0.1"),
            ("plan", "expires_at", "2026-10-18T12:20:01Z"),
            ("plan", "actions", [*metadata.ACTIONS, "write_token"]),
            ("approval", "reader_policy_limitation_acknowledged", False),
            ("approval", "revocation_acknowledged", False),
            ("approval", "granted", False),
            ("approval", "owner_provisioned", {"test": True, "reader": False}),
        ]
        for target, key, value in cases:
            document = self.plan if target == "plan" else self.approval
            original = copy.deepcopy(document[key])
            document[key] = value
            self.refresh_inputs()
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                self.run_collection()
            self.assertEqual(self.loads, [])
            self.assertEqual(self.calls, [])
            self.assertFalse(Path(self.plan["claim"]).exists())
            document[key] = original
        self.refresh_inputs()

    def test_digests_and_human_evidence_are_bound_before_credentials(self):
        for inputs in (
            replace(self.inputs, plan_digest="f" * 64),
            replace(self.inputs, approval_digest="f" * 64),
        ):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                metadata.run(
                    inputs,
                    transport=self.transport,
                    credential_loader=self.load,
                    wall_clock=lambda: NOW,
                    monotonic=lambda: self.tick,
                )
            self.assertEqual(self.loads, [])
        self.human.write_bytes(b"changed synthetic human evidence")
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.assertEqual(self.calls, [])

    def test_same_path_or_same_secret_cannot_supply_both_roles(self):
        original = self.plan["reader_credential"]
        self.plan["reader_credential"] = self.plan["test_credential"]
        self.refresh_inputs()
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.plan["reader_credential"] = original
        self.refresh_inputs()
        Path(original).write_bytes(TEST_TOKEN)
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.calls, [])

    def test_raw_ascii_bounded_credentials_are_required_without_transport(self):
        for token in (b"", b"has newline\n", b"has space", b"\xff" * 32, b"x" * 4097):
            with self.subTest(size=len(token)), self.assertRaises(ValueError):
                self.run_collection(credential_loader=lambda path, maximum, token=token: token)
            self.assertEqual(self.calls, [])
            self.reset_attempt()

    def test_aliasing_evidence_and_credential_paths_refuses_before_secret_reads(self):
        self.plan["evidence"] = self.plan["test_credential"]
        self.refresh_inputs()
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.assertEqual(Path(self.plan["test_credential"]).read_bytes(), TEST_TOKEN)

    def test_credential_loading_cannot_consume_budget_then_dispatch(self):
        def delayed(path, maximum):
            token = self.load(path, maximum)
            self.tick += 1201
            return token

        with self.assertRaises(ValueError):
            self.run_collection(credential_loader=delayed)
        self.assertEqual(self.calls, [])

    def test_existing_claim_fences_replay_before_secret_reads(self):
        self.run_collection()
        self.loads.clear()
        self.calls.clear()
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.assertEqual(self.calls, [])

    def test_provider_failure_spends_attempt_and_suppresses_all_raw_error_and_token_output(self):
        self.responses[0] = RuntimeError("provider-secret-error " + TEST_TOKEN.decode())
        output = io.StringIO()
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            self.assertRaises(ValueError) as caught,
        ):
            self.run_collection()
        self.assert_sanitized(output.getvalue())
        self.assert_sanitized(caught.exception)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(Path(self.plan["journal"]).exists())
        self.assertTrue(Path(self.plan["claim"]).exists())
        self.assert_no_evidence()
        self.assertEqual(len(self.calls), 1)
        self.loads.clear()
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.loads, [])
        for name in ("journal", "claim"):
            self.assert_sanitized(Path(self.plan[name]).read_bytes())

    def test_verify_identity_status_expiry_and_temporal_mismatches_stop_before_details(self):
        for index, field, value in (
            (0, "id", "../other"),
            (0, "status", "disabled"),
            (0, "expires_on", "2026-10-18T12:00:00Z"),
            (0, "not_before", "2026-10-18T12:02:00Z"),
            (1, "id", TEST_ID),
            (1, "status", "expired"),
        ):
            original = copy.deepcopy(self.responses[index])
            self.responses[index]["result"][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                self.run_collection()
            self.assertLessEqual(len(self.calls), index + 1)
            self.assert_no_evidence()
            self.responses[index] = original
            self.reset_attempt()

    def test_details_must_match_acknowledged_test_identity_status_and_times(self):
        for field, value in (
            ("id", READER_ID),
            ("status", "disabled"),
            ("expires_on", "2026-10-19T00:00:00.123456788Z"),
            ("not_before", "2026-10-18T11:56:00.987654320Z"),
            ("issued_on", "2026-10-18T12:02:00Z"),
            ("issued_on", None),
        ):
            original = copy.deepcopy(self.responses[2])
            self.responses[2]["result"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.run_collection()
            self.assertEqual(len(self.calls), 3)
            self.assert_no_evidence()
            self.responses[2] = original
            self.reset_attempt()

    def test_missing_extra_or_malformed_policies_and_success_envelopes_fail_closed(self):
        invalid = []
        for field in self.details:
            value = copy.deepcopy(self.details)
            del value[field]
            invalid.append(envelope(value))
        for policy in (
            None,
            [],
            [{}],
            [{"effect": "allow", "resources": {}, "permission_groups": [{"id": "e" * 32}]}],
        ):
            invalid.append(envelope({**self.details, "policies": policy}))
        invalid.extend(
            [
                envelope({**self.details, "unreviewed": True}),
                {**envelope(self.details), "success": 1},
                {**envelope(self.details), "errors": [{"message": "provider-secret-error"}]},
                {**envelope(self.details), "extra": True},
            ]
        )
        for index, response in enumerate(invalid):
            self.responses[2] = response
            with self.subTest(index=index), self.assertRaises(ValueError) as caught:
                self.run_collection()
            self.assert_sanitized(caught.exception)
            self.assert_no_evidence()
            self.reset_attempt()

    def test_elapsed_absolute_or_monotonic_budget_prevents_next_dispatch(self):
        self.now = datetime(2026, 10, 18, 12, 20, tzinfo=UTC).timestamp()
        with self.assertRaises(ValueError):
            self.run_collection()
        self.assertEqual(self.loads, [])
        self.now = NOW

        def expires_during_first(request):
            response = self.transport(request)
            self.tick += 1201
            return response

        with self.assertRaises(ValueError):
            self.run_collection(transport=expires_during_first)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_evidence()

    def test_http_errors_redirects_and_invalid_json_never_retry_or_retain_raw_body(self):
        for status, body in (
            (302, b"provider-secret-error"),
            (403, b"provider-secret-error " + READER_TOKEN),
            (200, b"provider-secret-error"),
            (200, b'{"success":true,"success":true}'),
        ):

            def refused(request, code=status, raw=body):
                self.calls.append(request)
                return finite.Response(code, {}, raw, len(raw) + 100)

            with (
                self.subTest(status=status, size=len(body)),
                self.assertRaises(ValueError) as caught,
            ):
                self.run_collection(transport=refused)
            self.assert_sanitized(caught.exception)
            self.assertEqual(len(self.calls), 1)
            self.assert_no_evidence()
            self.reset_attempt()

    def test_wire_response_budget_and_missing_accounting_never_allow_next_request(self):
        for wire_bytes in (65537, None, -1, True):

            def oversized(request, count=wire_bytes):
                self.calls.append(request)
                return finite.Response(200, {}, encoded(self.responses[0]), count)

            with self.subTest(wire_bytes=wire_bytes), self.assertRaises(ValueError):
                self.run_collection(transport=oversized)
            self.assertEqual(len(self.calls), 1)
            self.assert_no_evidence()
            self.reset_attempt()

    def test_existing_evidence_or_journal_sink_refuses_without_overwrite_or_secret_read(self):
        for name in ("evidence", "journal"):
            path = Path(self.plan[name])
            path.write_bytes(b"synthetic retained evidence")
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_collection()
            self.assertEqual(path.read_bytes(), b"synthetic retained evidence")
            self.assertEqual(self.loads, [])
            self.assertEqual(self.calls, [])
            self.reset_attempt()


if __name__ == "__main__":
    unittest.main()
