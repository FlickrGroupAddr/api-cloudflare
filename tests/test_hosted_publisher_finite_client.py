"""Actual finite client requests against a scripted, entirely synthetic HTTP seam."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts import hosted_publisher_finite_client as client
from scripts import hosted_publisher_operator as operator

PHASES = ("seed", "http", "materialize", "attach", "title", "remove", "finish")
OUTCOMES = (
    "synthetic_seeded",
    "actual_handler_admission",
    "materialized",
    "membership_verified",
    "synced",
    "local_removed_without_upstream",
    "finite_synthetic_sequence_complete",
)
TOKEN = "d" * 64


def phase_body(phase, scenario="happy"):
    body = {
        "schemaVersion": 1,
        "phase": phase,
        "outcome": OUTCOMES[PHASES.index(phase)],
        "scenario": scenario,
        "status": "NO-GO",
        "productionSchedulerQualified": False,
    }
    if phase != "seed":
        body.update(providerCalls=0, syntheticPosts=0)
    if phase == "http":
        body.update(albumRequests=3, uploadProofs=2)
    if phase in ("materialize", "attach", "title"):
        body.update(providerCalls=3, syntheticPosts=1)
    if scenario == "create_lost" and phase == "materialize":
        body.update(
            outcome="create_reconciled_no_replay",
            createReplayOutcome="no_work",
            repairStatus="materialized",
            repairRequests=2,
        )
    if (scenario, phase) in (("attachment_lost", "attach"), ("title_lost", "title")):
        body.update(lostReplyRecovered=True, reconciliationReads=1)
    return body


class ScriptedHTTP:
    """A request-consuming HTTP protocol double, never a live networking adapter."""

    def __init__(self, mutate=None):
        self.requests = []
        self.mutate = mutate

    def __call__(self, request):
        self.requests.append(request)
        phase = request.url.rsplit("/", 1)[-1]
        body = phase_body(phase)
        status = 200
        headers = {"content-type": "application/json", "cache-control": "no-store"}
        if self.mutate:
            status, headers, body = self.mutate(request, body, status, headers)
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        return client.Response(status=status, headers=headers, body=data)


class FiniteClientTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-finite-client-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "run.sqlite"
        self.journal = operator.DurableJournal(self.path, "a" * 64)
        self.addCleanup(self.journal.close)
        self.now = 100.0
        self.wall = 1000.0
        self.identity = client.ClientIdentity(
            "https://synthetic.workers.dev",
            "a" * 64,
            "b" * 64,
            "11111111-1111-4111-8111-111111111111",
            "happy",
            1100.0,
        )

    def make(self, transport=None, budget=None, identity=None, stop_check=lambda: False):
        self.http = transport or ScriptedHTTP()
        self.budget = budget or client.SharedBudget(128, 100000, 100000, 1000.0)
        return client.FiniteClient(
            identity or self.identity,
            self.http,
            self.budget,
            self.journal,
            lambda: TOKEN,
            clock=lambda: self.now,
            wall_clock=lambda: self.wall,
            stop_check=stop_check,
        )

    def assert_sanitized(self, result):
        rendered = json.dumps({"receipt": result, "journal": self.journal.snapshot()})
        self.assertNotIn(TOKEN, rendered)
        self.assertNotIn("X-Probe-Access", rendered)
        self.assertNotIn("SYNTHETIC-PRIVATE-RESPONSE", rendered)

    def test_seven_phases_exact_requests_and_single_use(self):
        finite = self.make()
        result = finite.run()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(
            [request.url.rsplit("/", 1)[-1] for request in self.http.requests], list(PHASES)
        )
        self.assertEqual(self.budget.requests, 7)
        self.assertEqual(self.budget.request_bytes, sum(len(r.wire) for r in self.http.requests))
        self.assertGreater(self.budget.response_bytes, 0)
        for request in self.http.requests:
            self.assertEqual(request.headers["Content-Length"], "0")
            self.assertEqual(request.headers["X-Probe-Access"], TOKEN)
            self.assertTrue(request.wire.startswith(b"POST /__publisher/"))
            self.assertNotIn(TOKEN, repr(request))
            self.assertLessEqual(request.timeout, 60)
            self.assertLessEqual(request.max_response_bytes, 65536)
        self.assertEqual(finite.run()["status"], "refused")
        self.assertEqual(len(self.http.requests), 7)
        self.assert_sanitized(result)

    def test_lost_response_stops_and_fresh_client_does_not_replay(self):
        def lost(request, body, status, headers):
            if body["phase"] == "http":
                raise ConnectionResetError("SYNTHETIC-PRIVATE-RESPONSE")
            return status, headers, body

        result = self.make(ScriptedHTTP(lost)).run()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(len(self.http.requests), 2)
        replacement = self.make()
        self.assertEqual(replacement.run()["status"], "refused")
        self.assertEqual(len(self.http.requests), 0)
        self.assertEqual(self.journal.snapshot()["http"]["state"], "unknown")
        self.assert_sanitized(result)

    def test_stop_and_expiry_before_dispatch_send_nothing(self):
        for identity, stopped in (
            (self.identity, True),
            (replace(self.identity, expires_at=999), False),
            (replace(self.identity, expires_at=3000), False),
        ):
            finite = self.make(identity=identity, stop_check=lambda s=stopped: s)
            self.assertEqual(finite.run()["status"], "refused")
            self.assertEqual(self.http.requests, [])

    def test_stop_after_response_leaves_unknown_and_stops_following_phase(self):
        stopped = False

        def stop(request, body, status, headers):
            nonlocal stopped
            stopped = True
            return status, headers, body

        result = self.make(ScriptedHTTP(stop), stop_check=lambda: stopped).run()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(len(self.http.requests), 1)

    def test_late_response_cannot_complete_phase(self):
        def late(request, body, status, headers):
            self.now = request.deadline
            return status, headers, body

        result = self.make(ScriptedHTTP(late)).run()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(len(self.http.requests), 1)

    def test_request_count_budget_is_shared_across_clients(self):
        budget = client.SharedBudget(7, 100000, 100000, 1000.0)
        self.assertEqual(self.make(budget=budget).run()["status"], "complete")
        second_journal = operator.DurableJournal(self.path.with_name("second.sqlite"), "a" * 64)
        self.addCleanup(second_journal.close)
        second = self.make(budget=budget)
        second.journal = second_journal
        self.assertNotEqual(second.run()["status"], "complete")
        self.assertEqual(len(self.http.requests), 0)
        self.assertEqual(budget.requests, 7)

    def test_request_byte_budget_refuses_before_transport(self):
        budget = client.SharedBudget(128, 1, 100000, 1000.0)
        self.assertNotEqual(self.make(budget=budget).run()["status"], "complete")
        self.assertEqual(self.http.requests, [])
        self.assertEqual(budget.requests, 0)

    def test_synthetic_call_headroom_prevents_dispatch_over_cumulative_cap(self):
        budget = client.SharedBudget(128, 100000, 100000, 1000.0, max_provider_calls=1)
        result = self.make(budget=budget).run()
        self.assertNotEqual(result["status"], "complete")
        self.assertEqual([r.url.rsplit("/", 1)[-1] for r in self.http.requests], ["seed"])
        self.assertLessEqual(budget.provider_calls, 1)

    def test_uncertain_phase_retains_worst_case_activity_charge(self):
        def lost(request, body, status, headers):
            if body["phase"] == "http":
                raise TimeoutError("SYNTHETIC-PRIVATE-RESPONSE")
            return status, headers, body

        result = self.make(ScriptedHTTP(lost)).run()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(self.budget.provider_calls, 16)
        self.assertEqual(self.budget.synthetic_posts, 1)

    def test_oversize_response_is_unknown_without_further_dispatch(self):
        def oversized(request, body, status, headers):
            return status, headers, b"x" * (request.max_response_bytes + 1)

        result = self.make(ScriptedHTTP(oversized)).run()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(len(self.http.requests), 1)
        self.assert_sanitized(result)

    def test_redirect_error_private_body_and_schema_drift_are_terminal(self):
        cases = (
            lambda r, b, s, h: (302, {**h, "location": "https://elsewhere.invalid"}, b),
            lambda r, b, s, h: (500, h, b"SYNTHETIC-PRIVATE-RESPONSE"),
            lambda r, b, s, h: (s, h, {**b, "resourceId": "self-asserted-overlay"}),
            lambda r, b, s, h: (s, h, {**b, "productionSchedulerQualified": True}),
            lambda r, b, s, h: (s, h, b'{"phase":"seed","phase":"http"}'),
        )
        for index, mutate in enumerate(cases):
            with self.subTest(index=index):
                journal = operator.DurableJournal(
                    self.path.with_name(f"fault-{index}.sqlite"), "a" * 64
                )
                self.addCleanup(journal.close)
                finite = self.make(ScriptedHTTP(mutate))
                finite.journal = journal
                result = finite.run()
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(len(self.http.requests), 1)
                self.assert_sanitized(result)

    def test_disabled_https_transport_never_opens_socket(self):
        from unittest.mock import patch

        finite = self.make(client.HttpsTransport("192.0.2.1"))
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(finite.run()["status"], "unknown")

    def test_identity_rejects_redirectable_and_non_origin_endpoints(self):
        for endpoint in (
            "http://synthetic.invalid",
            "https://synthetic.invalid/extra",
            "https://synthetic.invalid?secret=x",
            "https://x@y.invalid",
            "https://synthetic.invalid:8443",
            "https://synthetic.invalid/",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(client.Refused):
                replace(self.identity, endpoint=endpoint)

    def test_actual_candidate_schema_for_all_scenarios(self):
        for scenario in client.SCENARIOS:
            for phase in PHASES:
                with self.subTest(scenario=scenario, phase=phase):
                    body = phase_body(phase, scenario)
                    response = client.Response(
                        200,
                        {"content-type": "application/json", "cache-control": "no-store"},
                        json.dumps(body).encode(),
                    )
                    self.assertEqual(client.validate_response(response, phase, scenario), body)

    def test_out_of_range_or_boolean_activity_counts_refuse(self):
        for field, value in (
            ("providerCalls", 17),
            ("providerCalls", -1),
            ("providerCalls", True),
            ("syntheticPosts", 2),
            ("syntheticPosts", True),
        ):
            body = phase_body("materialize")
            body[field] = value
            response = client.Response(
                200,
                {"content-type": "application/json", "cache-control": "no-store"},
                json.dumps(body).encode(),
            )
            with self.subTest(field=field, value=value), self.assertRaises(client.UnknownOutcome):
                client.validate_response(response, "materialize", "happy")


class SyntheticTLSSocket:
    """Finite wire bytes for the real HTTP parser; no socket is ever created."""

    def __init__(self, wire, tick=lambda: None):
        self.pending = wire
        self.tick = tick
        self.sent = []
        self.closed = False

    def recv(self, count):
        self.tick()
        # Small reads exercise HTTP framing across read boundaries.
        size = min(count, 11)
        result, self.pending = self.pending[:size], self.pending[size:]
        return result

    def settimeout(self, timeout):
        if timeout <= 0:
            raise TimeoutError

    def connect(self, address):
        if address != ("192.0.2.1", 443):
            raise AssertionError("unexpected network target")

    def sendall(self, value):
        self.sent.append(value)

    def close(self):
        self.closed = True


class ActualHTTPParserTests(unittest.TestCase):
    def request(self, limit=65536):
        return client.Request(
            "https://synthetic.invalid/__publisher/seed",
            {},
            10,
            limit,
            110.0,
            b"POST /__publisher/seed HTTP/1.1\r\n\r\n",
        )

    def call(self, wire, *, limit=65536, clock=lambda: 100.0, tick=lambda: None):
        self.connection = SyntheticTLSSocket(wire, tick)
        with (
            patch.object(client.socket, "socket", return_value=self.connection),
            patch.object(client.ssl, "create_default_context") as context,
        ):
            context.return_value.wrap_socket.return_value = self.connection
            return client.HttpsTransport("192.0.2.1", enabled=True, clock=clock)(
                self.request(limit)
            )

    def test_chunked_response_charges_all_wire_bytes(self):
        wire = (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Cache-Control: no-store\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"2\r\n{}\r\n0\r\n\r\n"
        )
        response = self.call(wire)
        self.assertEqual(response.body, b"{}")
        self.assertEqual(response.wire_bytes, len(wire))
        self.assertEqual(len(self.connection.sent), 1)
        self.assertTrue(self.connection.closed)

    def test_duplicate_headers_are_rejected_by_actual_parser(self):
        wire = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\ncontent-length: 2\r\n\r\n{}"
        with self.assertRaises(client.UnknownOutcome):
            self.call(wire)
        self.assertTrue(self.connection.closed)

    def test_truncated_declared_body_is_unknown(self):
        wire = b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n{}"
        with self.assertRaises(client.UnknownOutcome):
            self.call(wire)
        self.assertTrue(self.connection.closed)

    def test_declared_body_exceeding_response_limit_is_unknown(self):
        wire = b"HTTP/1.1 200 OK\r\nContent-Length: 65537\r\n\r\n{}"
        with self.assertRaises(client.UnknownOutcome):
            self.call(wire)
        self.assertTrue(self.connection.closed)

    def test_ambiguous_or_unsupported_transfer_framing_is_unknown(self):
        for fields in (
            b"Transfer-Encoding: chunked\r\nContent-Length: 2\r\n",
            b"Transfer-Encoding: gzip\r\n",
            b"Transfer-Encoding: gzip, chunked\r\n",
            b"Transfer-Encoding: chunked, chunked\r\n",
        ):
            with self.subTest(fields=fields), self.assertRaises(client.UnknownOutcome):
                self.call(b"HTTP/1.1 200 OK\r\n" + fields + b"\r\n2\r\n{}\r\n0\r\n\r\n")
            self.assertTrue(self.connection.closed)

    def test_malformed_content_length_is_unknown(self):
        for value in (b"-1", b"+2", b"2.0", b"two", b"999999999999999999999"):
            with self.subTest(value=value), self.assertRaises(client.UnknownOutcome):
                self.call(b"HTTP/1.1 200 OK\r\nContent-Length: " + value + b"\r\n\r\n{}")
            self.assertTrue(self.connection.closed)

    def test_header_and_chunk_framing_counts_toward_limit(self):
        wire = b"HTTP/1.1 200 OK\r\nX-Large: " + b"x" * 300 + b"\r\nContent-Length: 2\r\n\r\n{}"
        with self.assertRaises(client.UnknownOutcome):
            self.call(wire, limit=128)
        self.assertTrue(self.connection.closed)

    def test_slow_drip_cannot_extend_absolute_deadline(self):
        now = 100.0

        def tick():
            nonlocal now
            now += 4

        wire = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        with self.assertRaises(TimeoutError):
            self.call(wire, clock=lambda: now, tick=tick)
        self.assertTrue(self.connection.closed)


if __name__ == "__main__":
    unittest.main()
