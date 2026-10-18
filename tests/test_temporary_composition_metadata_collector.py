"""Bounded metadata collector tests; every credential and transport is synthetic."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import temporary_composition_metadata_collector as collector
from scripts.hosted_publisher_finite_client import Response
from tests.test_temporary_composition_metadata_projection import payload_for, target_for

NOW = datetime(2026, 10, 18, 14, 30, tzinfo=UTC)
TOKEN = "synthetic-token-only-123456789"
SENTINEL = "synthetic-private-response-sentinel"


def plan_inputs(scopes=("versions",)):
    plan = {
        "grantEvidenceSha256": "e" * 64,
        "schemaVersion": 1,
        "kind": "temporary_composition_metadata_plan",
        "runId": "c" * 32,
        "sourceSha256": collector.source_sha256(),
        "endpointAddress": "1.1.1.1",
        "startsAt": "2026-10-18T14:00:00Z",
        "expiresAt": "2026-10-18T15:00:00Z",
        "timeoutSeconds": 10,
        "maxResponseBytes": 4096,
        "credentialBinding": hashlib.sha256(TOKEN.encode("ascii")).hexdigest(),
        "requests": [{"scope": scope, "target": target_for(scope)} for scope in scopes],
    }
    return plan, consent_for(plan)


def consent_for(plan):
    return {
        "grantEvidenceSha256": plan["grantEvidenceSha256"],
        "approved": True,
        "decisionRef": "synthetic-independent-owner-decision",
        "planSha256": collector.digest(plan),
        "sourceSha256": copy.deepcopy(plan["sourceSha256"]),
        "credentialBinding": plan["credentialBinding"],
    }


def response_for(scope="versions", *, payload=None, status=200, headers=None):
    return Response(
        status,
        headers if headers is not None else {"Content-Type": "application/json"},
        collector.canonical(payload if payload is not None else payload_for(scope)),
    )


class MetadataCollectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-synthetic-metadata-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output, self.journal = self.root / "projection.json", self.root / "intent.jsonl"
        self.token = Mock(return_value=TOKEN)
        self.transport = Mock(return_value=response_for())
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

    def inputs(self, scopes=("versions",)):
        plan, _ = plan_inputs(scopes)
        plan["outputPath"] = str(self.output.resolve())
        plan["journalPath"] = str(self.journal.resolve())
        return plan, consent_for(plan)

    def collect(self, plan=None, consent=None, **kwargs):
        default_plan, default_consent = self.inputs()
        plan = default_plan if plan is None else plan
        consent = default_consent if consent is None else consent
        options = {"now": lambda: NOW, "clock": lambda: 100.0, "transport": self.transport}
        options.update(kwargs)
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            return collector.collect(
                plan,
                collector.digest(plan),
                consent,
                self.token,
                self.output,
                self.journal,
                **options,
            )

    def assert_private_failure(self, callback):
        with self.assertRaises(collector.CollectionError) as raised:
            callback()
        for text in (str(raised.exception), self.stdout.getvalue(), self.stderr.getvalue()):
            for secret in (TOKEN, SENTINEL, str(self.output), str(self.journal)):
                self.assertNotIn(secret, text)
        return raised.exception

    def test_exact_get_ledger_and_partial_projection_success_without_external_access(self):
        scopes = (
            "deployments",
            "versions",
            "schedules",
            "script_subdomain",
            "d1_database",
            "zone_routes",
        )
        plan, consent = self.inputs(scopes)
        self.transport.side_effect = [response_for(scope) for scope in scopes]
        original = copy.deepcopy((plan, consent))
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            result = self.collect(plan, consent)
        self.assertEqual((plan, consent), original)
        self.assertEqual(self.token.call_count, 1)
        self.assertEqual(self.transport.call_count, len(scopes))
        self.assertEqual(result["requests"], len(scopes))
        self.assertIs(result["completeBaseline"], False)
        self.assertEqual(json.loads(self.output.read_bytes()), result)
        states = [json.loads(line) for line in self.journal.read_bytes().splitlines()]
        self.assertEqual(
            [row["state"] for row in states],
            ["opened"]
            + [state for _ in scopes for state in ("intent", "projected")]
            + ["complete"],
        )
        for ordinal, call in enumerate(self.transport.call_args_list, 1):
            request = call.args[0]
            item = plan["requests"][ordinal - 1]
            path = collector.endpoint_for(item["scope"], item["target"])
            self.assertEqual(request.url, "https://api.cloudflare.com" + path)
            self.assertTrue(request.wire.startswith(f"GET {path} HTTP/1.1\r\n".encode()))
            self.assertTrue(request.wire.endswith(b"\r\n\r\n"))
            self.assertEqual(request.headers["Authorization"], "Bearer " + TOKEN)
            self.assertEqual(request.headers["Content-Length"], "0")
            self.assertEqual(request.timeout, 10)
            self.assertEqual(request.deadline, 110)
            self.assertEqual(states[ordinal * 2 - 1]["ordinal"], ordinal)
        self.assertNotIn(TOKEN, self.output.read_text() + self.journal.read_text())
        self.assertNotIn("synthetic-worker", self.journal.read_text())

    def test_missing_or_forged_consent_refuses_before_token_or_sink_creation(self):
        for mutate in (
            lambda c: c.update(approved=False),
            lambda c: c.update(approved=1),
            lambda c: c.update(planSha256="0" * 64),
            lambda c: c.update(sourceSha256={}),
            lambda c: c.update(credentialBinding="0" * 64),
            lambda c: c.update(grantEvidenceSha256="0" * 64),
            lambda c: c.update(decisionRef=""),
            lambda c: c.clear(),
        ):
            plan, consent = self.inputs()
            mutate(consent)
            self.assert_private_failure(
                lambda plan=plan, consent=consent: self.collect(plan, consent)
            )
            self.assertFalse(self.output.exists())
            self.assertFalse(self.journal.exists())
        self.token.assert_not_called()
        self.transport.assert_not_called()

    def test_stale_independent_plan_or_source_pins_refuse_before_token(self):
        plan, consent = self.inputs()
        with self.assertRaises(collector.CollectionError):
            collector.collect(
                plan,
                "0" * 64,
                consent,
                self.token,
                self.output,
                self.journal,
                now=lambda: NOW,
                transport=self.transport,
            )
        plan["sourceSha256"] = {}
        self.assert_private_failure(lambda plan=plan: self.collect(plan, consent_for(plan)))
        self.token.assert_not_called()
        self.transport.assert_not_called()

    def test_unsafe_settings_and_unbounded_or_duplicate_requests_refuse_before_token(self):
        for mutation in ("settings", "duplicate", "empty", "nineteen", "foreign_target"):
            plan, _ = self.inputs()
            if mutation == "settings":
                plan["requests"][0]["scope"] = "settings"
            elif mutation == "duplicate":
                plan["requests"] *= 2
            elif mutation == "empty":
                plan["requests"] = []
            elif mutation == "nineteen":
                plan["requests"] *= 19
            else:
                plan["requests"][0]["target"]["scriptName"] = "../../" + SENTINEL
            self.assert_private_failure(lambda plan=plan: self.collect(plan, consent_for(plan)))
        self.token.assert_not_called()
        self.transport.assert_not_called()

    def test_window_clock_and_numeric_limits_refuse_before_token(self):
        for field, value in (
            ("grantEvidenceSha256", "bad-grant-pin"),
            ("timeoutSeconds", True),
            ("timeoutSeconds", 61),
            ("maxResponseBytes", 262145),
            ("endpointAddress", "127.0.0.1"),
            ("expiresAt", "2026-10-18T16:00:00Z"),
        ):
            plan, _ = self.inputs()
            plan[field] = value
            self.assert_private_failure(lambda plan=plan: self.collect(plan, consent_for(plan)))
        for now in (
            NOW - timedelta(hours=1),
            NOW + timedelta(minutes=30),
            NOW.replace(tzinfo=None),
        ):
            self.assert_private_failure(lambda now=now: self.collect(now=lambda: now))
        self.assert_private_failure(lambda: self.collect(clock=lambda: float("nan")))
        self.token.assert_not_called()
        self.transport.assert_not_called()

    def test_existing_either_sink_and_equal_sink_paths_refuse_without_overwrite(self):
        for sink in (self.output, self.journal):
            sink.write_bytes(b"synthetic-existing-custody")
            self.assert_private_failure(lambda: self.collect())
            self.assertEqual(sink.read_bytes(), b"synthetic-existing-custody")
            sink.unlink()
        with self.assertRaises(collector.CollectionError):
            plan, consent = self.inputs()
            collector.collect(
                plan,
                collector.digest(plan),
                consent,
                self.token,
                self.output,
                self.output,
                now=lambda: NOW,
                transport=self.transport,
            )
        self.token.assert_not_called()
        self.transport.assert_not_called()

    def test_one_owner_reentrant_delivery_cannot_obtain_second_credential(self):
        second_token = Mock(return_value=TOKEN)
        plan, consent = self.inputs()

        def delivery():
            with self.assertRaises(collector.CollectionError):
                collector.collect(
                    plan,
                    collector.digest(plan),
                    consent,
                    second_token,
                    self.output,
                    self.journal,
                    now=lambda: NOW,
                    transport=self.transport,
                )
            return TOKEN

        self.token.side_effect = delivery
        self.collect(plan, consent)
        second_token.assert_not_called()
        self.assertEqual(self.transport.call_count, 1)

    def test_token_mismatch_leaves_tombstones_and_never_dispatches(self):
        self.token.return_value = "synthetic-wrong-token-123456"
        self.assert_private_failure(lambda: self.collect())
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertIn("aborted_no_replay", self.journal.read_text())
        self.transport.assert_not_called()

    def test_unknown_transport_exception_is_sanitized_and_permanently_refuses_replay(self):
        self.transport.side_effect = RuntimeError(SENTINEL + TOKEN)
        self.assert_private_failure(lambda: self.collect())
        self.assertEqual(self.output.read_bytes(), b"")
        journal = self.journal.read_bytes()
        self.assertIn(b"intent", journal)
        self.assertIn(b"aborted_no_replay", journal)
        self.assertNotIn(SENTINEL.encode(), journal)
        self.assert_private_failure(lambda: self.collect())
        self.assertEqual(self.token.call_count, 1)
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.journal.read_bytes(), journal)

    def test_response_failures_stop_before_next_get_and_never_retain_raw_body(self):
        failures = [
            response_for(status=302, headers={"Location": "https://example.invalid/" + SENTINEL}),
            response_for(headers={"Content-Type": "text/plain"}),
            response_for(headers={"Content-Type": "application/json", "Content-Encoding": "gzip"}),
            response_for(
                headers={"Content-Type": "application/json", "content-type": "text/plain"}
            ),
            Response(200, {"Content-Type": "application/json"}, b"x" * 4097),
            Response(
                200,
                {"Content-Type": "application/json"},
                ('{"success":true,"success":true,"secret":"' + SENTINEL + '"}').encode(),
            ),
            Response(200, {"Content-Type": "application/json"}, b'{"x":NaN}'),
        ]
        for index, response in enumerate(failures):
            self.output, self.journal = self.root / f"out-{index}", self.root / f"log-{index}"
            self.transport.reset_mock()
            self.transport.return_value = response
            plan, consent = self.inputs(("versions", "schedules"))
            self.assert_private_failure(
                lambda plan=plan, consent=consent: self.collect(plan, consent)
            )
            self.assertEqual(self.transport.call_count, 1)
            self.assertEqual(self.output.read_bytes(), b"")
            self.assertNotIn(SENTINEL, self.journal.read_text())

    def test_pagination_unknown_fields_and_d1_rows_fail_closed_without_second_get(self):
        for index, scope in enumerate(("versions", "d1_database")):
            self.output, self.journal = (
                self.root / f"projection-{index}",
                self.root / f"ledger-{index}",
            )
            payload = payload_for(scope)
            if scope == "versions":
                payload["result_info"] = {"total_pages": 2}
            else:
                payload["result"]["rows"] = [{"photo": SENTINEL}]
            self.transport.reset_mock()
            self.transport.return_value = response_for(scope, payload=payload)
            plan, consent = self.inputs((scope, "schedules"))
            self.assert_private_failure(
                lambda plan=plan, consent=consent: self.collect(plan, consent)
            )
            self.assertEqual(self.transport.call_count, 1)
            self.assertEqual(self.output.read_bytes(), b"")
            self.assertNotIn(SENTINEL, self.journal.read_text())

    def test_deadline_expiring_during_response_discards_projection_and_stops(self):
        current = [NOW]

        def delayed_response(request):
            current[0] = NOW + timedelta(minutes=30)
            return response_for()

        self.transport.side_effect = delayed_response
        plan, consent = self.inputs(("versions", "schedules"))
        self.assert_private_failure(lambda: self.collect(plan, consent, now=lambda: current[0]))
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertNotIn("projected", self.journal.read_text())

    def test_mutable_plan_callback_cannot_change_reviewed_next_request(self):
        plan, consent = self.inputs(("versions", "schedules"))

        def delivery():
            plan["requests"][1]["scope"] = "settings"
            return TOKEN

        self.token.side_effect = delivery
        self.transport.side_effect = [response_for("versions"), response_for("schedules")]
        result = self.collect(plan, consent)
        self.assertEqual(result["requests"], 2)
        self.assertTrue(self.transport.call_args_list[1].args[0].url.endswith("/schedules"))

    def test_changed_source_after_first_response_aborts_before_next_dispatch(self):
        plan, consent = self.inputs(("versions", "schedules"))
        manifest = plan["sourceSha256"]
        changed = [False]

        def transport(request):
            changed[0] = True
            return response_for()

        def source():
            return {} if changed[0] else manifest

        self.transport.side_effect = transport
        with patch.object(collector, "source_sha256", side_effect=source):
            self.assert_private_failure(
                lambda plan=plan, consent=consent: self.collect(plan, consent)
            )
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_cli_unapproved_and_existing_sinks_never_open_token_or_call_network(self):
        plan, consent = self.inputs()
        plan_path, consent_path = self.root / "plan.json", self.root / "consent.json"
        token_path = self.root / "private-token-never-opened"
        plan_path.write_bytes(collector.canonical(plan))
        consent["approved"] = False
        consent_path.write_bytes(collector.canonical(consent))
        argv = [
            "--plan",
            str(plan_path),
            "--expected-plan-sha256",
            collector.digest(plan),
            "--consent",
            str(consent_path),
            "--token-file",
            str(token_path),
            "--output",
            str(self.output),
            "--journal",
            str(self.journal),
        ]
        actual_open = Path.open

        def checked_open(path, *args, **kwargs):
            self.assertNotEqual(path, token_path, "credential opened before authorization")
            return actual_open(path, *args, **kwargs)

        with (
            patch.object(Path, "open", checked_open),
            patch.object(
                collector, "_pinned_https", side_effect=AssertionError("network forbidden")
            ),
            redirect_stdout(self.stdout),
            redirect_stderr(self.stderr),
        ):
            self.assertEqual(collector.main(argv), 1)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.journal.exists())
        consent["approved"] = True
        consent_path.write_bytes(collector.canonical(consent))
        self.output.write_bytes(b"synthetic-existing")
        with (
            patch.object(Path, "open", checked_open),
            patch.object(
                collector, "_pinned_https", side_effect=AssertionError("network forbidden")
            ),
            redirect_stdout(self.stdout),
            redirect_stderr(self.stderr),
        ):
            self.assertEqual(collector.main(argv), 1)
        self.assertEqual(self.output.read_bytes(), b"synthetic-existing")
        self.assertNotIn(str(token_path), self.stdout.getvalue() + self.stderr.getvalue())

    def test_cli_explicit_synthetic_token_succeeds_through_fake_transport_only(self):
        plan, consent = self.inputs()
        paths = [self.root / name for name in ("plan.json", "consent.json", "token")]
        paths[0].write_bytes(collector.canonical(plan))
        paths[1].write_bytes(collector.canonical(consent))
        paths[2].write_text(TOKEN, encoding="ascii")
        argv = [
            "--plan",
            str(paths[0]),
            "--expected-plan-sha256",
            collector.digest(plan),
            "--consent",
            str(paths[1]),
            "--token-file",
            str(paths[2]),
            "--output",
            str(self.output),
            "--journal",
            str(self.journal),
        ]
        actual_collect = collector.collect

        def synthetic_collect(*args, **kwargs):
            return actual_collect(
                *args, now=lambda: NOW, clock=lambda: 100.0, transport=self.transport, **kwargs
            )

        with (
            patch.object(collector, "collect", side_effect=synthetic_collect),
            patch.object(
                collector, "_pinned_https", side_effect=AssertionError("network forbidden")
            ),
            redirect_stdout(self.stdout),
            redirect_stderr(self.stderr),
        ):
            self.assertEqual(collector.main(argv), 0)
        self.assertEqual(self.transport.call_count, 1)
        self.assertNotIn(TOKEN, self.stdout.getvalue() + self.stderr.getvalue())
        self.assertIs(json.loads(self.output.read_bytes())["completeBaseline"], False)

    def test_reviewed_sink_paths_cannot_be_substituted_for_replay(self):
        plan, consent = self.inputs()
        self.collect(plan, consent)
        original_output, original_journal = self.output, self.journal
        self.output, self.journal = self.root / "other-output", self.root / "other-journal"
        self.token.reset_mock()
        self.transport.reset_mock()
        self.assert_private_failure(lambda: self.collect(plan, consent))
        self.token.assert_not_called()
        self.transport.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.journal.exists())
        self.assertTrue(original_output.exists())
        self.assertTrue(original_journal.exists())


if __name__ == "__main__":
    unittest.main()
