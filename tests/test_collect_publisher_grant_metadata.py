"""Synthetic evidence-only token-metadata tests; no provider or native ACL access."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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

    def assert_no_evidence(self):
        path = Path(self.plan["evidence"])
        self.assertTrue(not path.exists() or path.read_bytes() == b"")

    def assert_sanitized(self, value: Any):
        rendered = str(value)
        for secret in (TEST_TOKEN.decode(), READER_TOKEN.decode(), "provider-secret-error"):
            self.assertNotIn(secret, rendered)

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
