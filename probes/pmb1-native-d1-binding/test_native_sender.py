"""Native sender SOURCE tests using invented fixtures and blocked socket/DNS.

Explicit trusted-facts objects below are synthetic test authority only. Their
existence and returned HTTP fixtures establish no actual native qualification.
"""

import io
import json
import sqlite3
import types
import unittest
from contextlib import closing
from dataclasses import asdict, replace
from unittest.mock import Mock, patch

import binding
import test_binding as fixtures

native = binding._GRAPH["native_sender"]
custody = binding._GRAPH["native_custody"]
adapter = binding.adapter
codec = binding.positional_receipt_successor


class NativeSenderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BindingTests(
            "test_successor_complete_returned_custody_and_second_transition"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def tearDown(self):
        self.fixture.tearDown()

    def plan(self, *, limit_overrides=None, allocation_edit=None, queries_edit=None):
        f = self.fixture
        intent = f.intent(limit=1)
        queries = [
            f.query("observer", fixtures.FIXED[name].decode())
            for name in ("readback.sql", "schema.sql")
        ]
        batch = codec.build(intent)
        queries.append(f.query("writer", batch.update_sql, [intent.expected]))
        queries.extend(
            f.query("observer", fixtures.FIXED[name].decode())
            for name in ("readback.sql", "schema.sql")
        )
        requests = []
        for query in queries:
            if query["role"] == "writer":
                requests.append(codec.manifest(batch))
            else:
                body = binding.canonical({"sql": query["sql"], "params": []})
                requests.append(
                    {
                        "protocol": "independent_primary_read",
                        "statementCount": 1,
                        "requestBodySha2_256": binding.sha2_256(body),
                        "statements": [{"sql": query["sql"], "params": []}],
                    }
                )
        limits = {
            "requests": 5,
            "statements": 6,
            "requestBytes": 1024 * 1024,
            "responseBytes": f.packet["maxTotalBytes"],
        }
        if limit_overrides:
            limits.update(limit_overrides)
        allocation = {
            "kind": "pmb1-native-positional-allocation-v1",
            "protocol": codec.BOUNDARY,
            "intents": [asdict(intent)],
            "requests": requests,
            "limits": limits,
        }
        if allocation_edit:
            allocation_edit(allocation)
        if queries_edit:
            queries_edit(queries)
        path = f.directory / "allocation.json"
        path.write_bytes(binding.canonical(allocation))
        f.packet["independentEvidence"]["allocation"] = {
            "path": str(path),
            "sha2_256": binding.sha2_256(path.read_bytes()),
        }
        base, journal, _ = f.plan(queries)
        core = binding.NativePositionalBinding(
            base.packet_path, base.packet_sha2_256, base.journal_path, f.source, clock=f.clock
        )
        sender = core.sender
        review = f.directory / "independent-review.txt"
        review.write_bytes(b"SYNTHETIC ONLY: no actual qualification or credential\n")
        review_ref = native.EvidenceRef(str(review), binding.sha2_256(review.read_bytes()))
        evidence = f.packet["independentEvidence"]
        facts = {
            name: native.EvidenceRef(**evidence["primaryAndCommitSemantics"])
            for name in (
                "sameConnection",
                "orderedTransactionRollbackCommit",
                "noInterleaving",
                "textBinding",
                "primaryCompleteness",
            )
        }
        for fact, role in {
            "durableCustody": "custody",
            "targetCurrentGrant": "grant",
            "allWriterInterval": "allWriterInterval",
            "sourceOracle": "sourceOracle",
            "allocation": "allocation",
        }.items():
            facts[fact] = native.EvidenceRef(**evidence[role])
        facts["clockAndWindow"] = review_ref
        delivery, delivery_ref = self.delivery(base, review_ref)
        facts["protectedDelivery"] = delivery_ref
        admission = native.ReviewedAdmission(
            "invented-test-reviewer",
            base.packet_sha2_256,
            codec.BOUNDARY,
            binding.source_pins(),
            fixtures.TARGET,
            f.packet["clockDomain"],
            f.packet["starts"],
            f.packet["ends"],
            f.packet["credentialSha2_256"],
            review_ref,
            facts,
        )
        return sender, journal, intent, admission, delivery

    def delivery(self, base, review_ref):
        f = self.fixture
        token = f.directory / "synthetic-not-actual-credential.txt"
        token.write_bytes(fixtures.TOKEN.encode())
        record = {
            "kind": "pmb1-reviewed-protected-delivery-v1",
            "packetSha2_256": base.packet_sha2_256,
            "target": fixtures.TARGET,
            "sourcePins": binding.source_pins(),
            "credential": {"path": str(token), "sha2_256": binding.sha2_256(token.read_bytes())},
            "grant": f.packet["independentEvidence"]["grant"],
            "custody": f.packet["independentEvidence"]["custody"],
        }
        path = f.directory / "synthetic-delivery-review.json"
        path.write_bytes(binding.canonical(record))
        pin = binding.sha2_256(path.read_bytes())
        return (
            custody.ProtectedCredential(
                str(path),
                pin,
                base.packet_sha2_256,
                fixtures.TARGET,
                binding.source_pins(),
                f.clock,
                100,
            ),
            native.EvidenceRef(str(path), pin),
        )

    def activate(self, **kwargs):
        sender, journal, intent, admission, delivery = self.plan(**kwargs)
        sender.core.activate(delivery, admission=admission)
        return sender, journal, intent, admission, delivery

    def strict_tls_lifecycle(self, *, chunked=False, invalid=None):
        """Exercise the real numeric TLS/HTTP parser over invented socket bytes.

        Only the socket and SSL context are scripted. The concrete transport,
        HTTP framing parser, source guards, public facade and controller all run.
        """
        sender, journal, intent, _admission, _delivery = self.activate()
        core = sender.core
        self.assertIs(core.sender, sender)
        transport = binding._GRAPH["scripts.hosted_publisher_execution_provider"]
        calls, sent, received, closed, hostnames = [], [], [], [], []
        fixture = self.fixture

        class ScriptedSocket:
            def __init__(self):
                self.stream = io.BytesIO()

            def settimeout(self, value):
                self_assert.assertGreater(value, 0)
                self_assert.assertLessEqual(value, 60)

            def connect(self, address):
                self_assert.assertEqual(address, ("1.1.1.1", 443))

            def sendall(self, wire):
                request = types.SimpleNamespace(wire=wire, url="https://api.cloudflare.com/query")
                response = fixture.batch_transport(
                    request,
                    core.address,
                    core.clock,
                    lambda: sender.guard(100),
                    discard_set_cookie=True,
                )
                calls.append(wire)
                sent.append(len(wire))
                body = response.body
                writer = b'"batch"' in wire.split(b"\r\n\r\n", 1)[1]
                current_invalid = invalid if writer else None
                media = b'Application/JSON; charset="UTF-8"; profile=pmb1'
                if current_invalid == "content_type":
                    media = b"text/html; charset=utf-8"
                headers = [
                    b"Content-Type: " + media,
                    b"Connection: close",
                    b"CF-Ray: invented-source-test",
                    b"Server: invented-provider",
                    b"Date: Fri, 23 Oct 2026 12:00:00 GMT",
                ]
                if chunked:
                    headers.append(b"Transfer-Encoding: chunked")
                    split = len(body) // 2
                    chunks = (body[:split], body[split:])
                    framed = (
                        b"".join(
                            f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n" for chunk in chunks
                        )
                        + b"0\r\nX-Probe-Trailer: bounded\r\n\r\n"
                    )
                else:
                    headers.append(b"Content-Length: " + str(len(body)).encode())
                    framed = body
                if current_invalid == "missing_framing":
                    headers = [
                        header for header in headers if not header.startswith(b"Content-Length:")
                    ]
                if current_invalid == "conflicting_framing":
                    headers.append(b"Transfer-Encoding: chunked")
                if current_invalid == "duplicate_content_type":
                    headers.append(b"Content-Type: application/json")
                status = (
                    b"HTTP/1.1 302 Found" if current_invalid == "redirect" else b"HTTP/1.1 200 OK"
                )
                if current_invalid == "redirect":
                    headers.append(b"Location: https://invented.invalid/")
                self.stream = io.BytesIO(
                    status + b"\r\n" + b"\r\n".join(headers) + b"\r\n\r\n" + framed
                )

            def recv(self, count):
                raw = self.stream.read(count)
                received.append(len(raw))
                return raw

            def close(self):
                closed.append(self)

        self_assert = self
        context = Mock()

        def wrap(raw, *, server_hostname):
            self.assertEqual(server_hostname, "api.cloudflare.com")
            hostnames.append(server_hostname)
            return raw

        context.wrap_socket.side_effect = wrap
        with patch.object(transport.socket, "socket", side_effect=lambda *args: ScriptedSocket()):
            with patch.object(transport.ssl, "create_default_context", return_value=context):
                controller = custody.NativeController(core.sender)
                result = controller.execute(intent)
                self.assertEqual(controller.execute(intent).status, "refused")
        self.assertEqual(len(calls), 3 if invalid else 5)
        self.assertEqual(len(hostnames), len(calls))
        self.assertEqual(len(closed), 2 * len(calls))
        self.assertEqual(self.fixture.socket_blocker.call_count, 0)
        self.assertEqual(self.fixture.dns_blocker.call_count, 0)
        with closing(sqlite3.connect(journal.path)) as db:
            statement_count, request_bytes = db.execute(
                "SELECT SUM(statements),SUM(request_bytes) FROM statement_allocations"
            ).fetchone()
            self.assertEqual(statement_count, 4 if invalid else 6)
            self.assertEqual(request_bytes, sum(sent))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batch_dispatches").fetchone()[0], 1)
            if invalid:
                self.assertIsNone(
                    db.execute("SELECT received FROM requests WHERE ordinal=2").fetchone()[0]
                )
            else:
                self.assertEqual(
                    db.execute("SELECT SUM(received) FROM requests").fetchone()[0], sum(received)
                )
                self.assertEqual(
                    db.execute("SELECT response_bytes FROM binding").fetchone()[0], sum(received)
                )
        self.assertEqual(journal.get(intent.key, 100).phase, "unknown" if invalid else "confirmed")
        self.assertEqual(result.status, "unknown" if invalid else "confirmed")

    def test_real_strict_tls_length_and_ordinary_metadata(self):
        self.strict_tls_lifecycle()

    def test_real_strict_tls_chunked_charset_and_ordinary_metadata(self):
        self.strict_tls_lifecycle(chunked=True)

    def test_real_strict_tls_wrong_media_type_is_unknown_no_replay(self):
        self.strict_tls_lifecycle(invalid="content_type")

    def test_real_strict_tls_redirect_is_unknown_no_replay(self):
        self.strict_tls_lifecycle(invalid="redirect")

    def test_real_strict_tls_missing_framing_is_unknown_no_replay(self):
        self.strict_tls_lifecycle(invalid="missing_framing")

    def test_real_strict_tls_conflicting_framing_is_unknown_no_replay(self):
        self.strict_tls_lifecycle(invalid="conflicting_framing")

    def test_real_strict_tls_duplicate_content_type_is_unknown_no_replay(self):
        self.strict_tls_lifecycle(invalid="duplicate_content_type")

    def test_json_media_type_parameters_are_validated(self):
        for value in (
            "application/json",
            ' Application/JSON; charset="UTF-8" ',
            'application/json; profile="safe;parameter"; CHARSET=utf-8',
        ):
            with self.subTest(value=value):
                self.assertTrue(native.json_media_type(value))
        for value in (
            None,
            "text/json",
            "application/jsonx",
            "application/json;",
            "application/json; charset=latin-1",
            'application/json; charset="utf-8',
            "application/json; charset=utf-8; CHARSET=utf-8",
            "application/json\r\nX-Test: unsafe",
        ):
            with self.subTest(value=value):
                self.assertFalse(native.json_media_type(value))

    def test_no_flag_or_callable_can_activate(self):
        sender, _journal, _intent, admission, _delivery = self.plan()
        with self.assertRaises(adapter.Refusal):
            sender.activate(lambda: fixtures.TOKEN, admission={"qualified": True})
        with self.assertRaises(adapter.Refusal):
            sender.activate(lambda: fixtures.TOKEN, admission=admission)
        self.assertIsNone(sender.core.token)

    def test_exact_native_http_path_and_durable_accounting(self):
        sender, journal, intent, _admission, _delivery = self.activate()
        with fixtures.patched_transport(side_effect=self.fixture.batch_transport) as transport:
            controller = custody.NativeController(sender)
            result = controller.execute(intent)
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(transport.call_count, 5)
        self.assertEqual([item["requestOrdinal"] for item in sender.read_evidence], [0, 1, 3, 4])
        self.assertEqual(journal.get(intent.key, 100).phase, "confirmed")
        with closing(sqlite3.connect(journal.path)) as db:
            self.assertEqual(
                db.execute("SELECT SUM(statements) FROM statement_allocations").fetchone()[0], 6
            )
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batch_dispatches").fetchone()[0], 1)
        result = controller.execute(intent)
        self.assertEqual(result.status, "refused")
        self.assertEqual(transport.call_count, 5)

    def test_lost_writer_response_consumes_without_replay(self):
        sender, journal, intent, _admission, _delivery = self.activate()

        def lost(request, *args, **kwargs):
            response = self.fixture.batch_transport(request, *args, **kwargs)
            if b'"batch"' in request.wire.split(b"\r\n\r\n", 1)[1]:
                raise TimeoutError("invented lost response")
            return response

        with fixtures.patched_transport(side_effect=lost) as transport:
            controller = custody.NativeController(sender)
            result = controller.execute(intent)
            self.assertEqual(result.status, "unknown")
            self.assertEqual(transport.call_count, 3)
            self.assertEqual(controller.execute(intent).status, "refused")
        self.assertEqual(journal.get(intent.key, 100).phase, "unknown")
        with closing(sqlite3.connect(journal.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batch_dispatches").fetchone()[0], 1)
            self.assertIsNone(
                db.execute("SELECT received FROM requests WHERE ordinal=2").fetchone()[0]
            )

    def test_statement_budget_refuses_writer_before_transport(self):
        sender, _journal, _intent, admission, delivery = self.plan(
            limit_overrides={"statements": 5}
        )
        with self.assertRaises(adapter.Refusal):
            sender.activate(delivery, admission=admission)
        self.assertIsNone(sender.core.token)
        self.assertFalse(delivery.used)

    def test_wire_request_budget_prevents_first_transport(self):
        sender, journal, intent, _admission, _delivery = self.activate(
            limit_overrides={"requestBytes": 1}
        )
        with fixtures.patched_transport(side_effect=self.fixture.batch_transport) as transport:
            result = custody.NativeController(sender).execute(intent)
        self.assertEqual(result.status, "refused")
        self.assertEqual(transport.call_count, 0)
        self.assertEqual(journal.remaining(self.fixture.packet["maxTotalBytes"], 100)[0], 0)

    def test_source_selection_and_generation_binding_refuse(self):
        sender, _journal, _intent, admission, delivery = self.plan(
            allocation_edit=lambda value: value.update(protocol="fixed_update_with_exact_count_v1")
        )
        with self.assertRaises(adapter.Refusal):
            sender.activate(delivery, admission=admission)
        self.assertIsNone(sender.core.token)

    def test_admission_target_drift_refuses_before_delivery(self):
        sender, _journal, _intent, admission, delivery = self.plan()
        bad = replace(admission, target_id="invented-other-target")
        with self.assertRaises(adapter.Refusal):
            sender.activate(delivery, admission=bad)
        self.assertIsNone(sender.core.token)

    def test_nonprimary_read_cannot_confirm(self):
        sender, _journal, intent, _admission, _delivery = self.activate()

        def nonprimary(*args, **kwargs):
            response = self.fixture.batch_transport(*args, **kwargs)
            body = json.loads(response.body)
            body["result"][0]["meta"]["served_by_primary"] = False
            raw = binding.canonical(body)
            return binding.Response(200, {"content-type": "application/json"}, raw, len(raw) + 128)

        with fixtures.patched_transport(side_effect=nonprimary) as transport:
            result = custody.NativeController(sender).execute(intent)
        self.assertEqual(result.status, "refused")
        self.assertEqual(transport.call_count, 1)

    def test_concurrent_request_refuses_without_reservation(self):
        sender, journal, _intent, _admission, _delivery = self.activate()
        self.assertTrue(sender.core.lock.acquire(blocking=False))
        try:
            with self.assertRaises(adapter.Refusal):
                sender.query("observer", fixtures.FIXED["readback.sql"].decode(), [], 100)
        finally:
            sender.core.lock.release()
        self.assertEqual(journal.remaining(self.fixture.packet["maxTotalBytes"], 100)[0], 0)

    def test_admission_mutation_stops_before_transport(self):
        sender, journal, intent, admission, _delivery = self.activate()
        admission.fact_evidence["clockAndWindow"] = admission.fact_evidence["allocation"]
        with fixtures.patched_transport(side_effect=self.fixture.batch_transport) as transport:
            result = custody.NativeController(sender).execute(intent)
        self.assertEqual(result.status, "refused")
        self.assertEqual(transport.call_count, 0)
        self.assertEqual(journal.remaining(self.fixture.packet["maxTotalBytes"], 100)[0], 0)

    def test_named_batch_type_is_never_promoted(self):
        sender, _journal, intent, _admission, _delivery = self.activate()
        named = binding.exact_receipt_successor.build(intent)
        with self.assertRaises(adapter.Refusal):
            sender.dispatch_batch(named, 100)

    def test_generation_overflow_refuses_before_credential_delivery(self):
        maximum = str(adapter.MAX_GENERATION)
        sender, _journal, _intent, admission, delivery = self.plan(
            allocation_edit=lambda value: value["intents"][0].update(expected=maximum)
        )
        with self.assertRaises(adapter.Refusal):
            sender.activate(delivery, admission=admission)
        self.assertFalse(delivery.used)

    def test_malformed_exact_count_is_unknown_without_replay(self):
        sender, journal, intent, _admission, _delivery = self.activate()

        def malformed(request, *args, **kwargs):
            response = self.fixture.batch_transport(request, *args, **kwargs)
            if b'"batch"' in request.wire.split(b"\r\n\r\n", 1)[1]:
                body = json.loads(response.body)
                body["result"][1]["results"][0]["exact_change_count"] = 1
                raw = binding.canonical(body)
                return binding.Response(
                    200, {"content-type": "application/json"}, raw, len(raw) + 128
                )
            return response

        with fixtures.patched_transport(side_effect=malformed) as transport:
            controller = custody.NativeController(sender)
            result = controller.execute(intent)
            self.assertEqual(result.status, "unknown")
            self.assertEqual(controller.execute(intent).status, "refused")
            self.assertEqual(transport.call_count, 3)
        with closing(sqlite3.connect(journal.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batch_dispatches").fetchone()[0], 1)
            self.assertIsNone(
                db.execute("SELECT received FROM requests WHERE ordinal=2").fetchone()[0]
            )


if __name__ == "__main__":
    unittest.main()
