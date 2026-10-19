"""Adversarial offline provider fixtures; no sockets or ambient credentials."""

import contextlib
import hashlib
import io
import json
import threading
import unittest
from dataclasses import replace
from email.message import Message
from unittest.mock import Mock, patch

from scripts import hosted_publisher_provider as provider

ACCOUNT = "a" * 32
TOKEN = "synthetic-private-provider-token"
NAME = "fga-publisher-happy"
IDENTITY = {
    "uuid": "11111111-1111-4111-8111-111111111111",
    "name": NAME,
    "created_at": "2026-10-17T12:00:00Z",
}


def envelope(result, *, success=True):
    return 200, {}, json.dumps({"success": success, "result": result}).encode()


class HostedPublisherProviderTests(unittest.TestCase):
    def adapter(self, *responses, limits=None, **kwargs):
        transport = Mock(side_effect=list(responses))
        instance = provider.CloudflareProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            transport=transport,
            limits=limits or provider.Limits(),
            **kwargs,
        )
        return instance, transport

    def test_exact_account_paths_create_query_inspect_and_cleanup(self):
        p, transport = self.adapter(
            envelope(IDENTITY), envelope([{"success": True}]), envelope(IDENTITY), envelope({})
        )
        identity = p.create_database(NAME, key="create")
        sql = b"CREATE TABLE synthetic_only (id INTEGER);"
        p.migrate(identity, sql, hashlib.sha256(sql).hexdigest(), key="migration")
        self.assertEqual(
            p.delete_database(identity, key="delete"),
            {"deletionAcknowledged": True, "absenceVerified": False},
        )
        prefix = "/client/v4/accounts/" + ACCOUNT + "/d1/database"
        self.assertEqual(
            [(c.args[0], c.args[1]) for c in transport.call_args_list],
            [
                ("POST", prefix),
                ("POST", prefix + "/" + IDENTITY["uuid"] + "/query"),
                ("GET", prefix + "/" + IDENTITY["uuid"]),
                ("DELETE", prefix + "/" + IDENTITY["uuid"]),
            ],
        )
        self.assertEqual(
            json.loads(transport.call_args_list[1].args[2]), {"sql": sql.decode(), "params": []}
        )
        for call in transport.call_args_list:
            self.assertEqual(call.args[3]["Authorization"], "Bearer " + TOKEN)
            self.assertEqual(call.args[3]["Accept-Encoding"], "identity")

    def test_omitted_provider_time_retains_exact_acknowledged_uuid_and_name(self):
        minimal = {k: IDENTITY[k] for k in ("uuid", "name")}
        p, transport = self.adapter(envelope(minimal), envelope(IDENTITY), envelope({}))
        identity = p.create_database(NAME, key="create")
        self.assertEqual(identity, {**minimal, "created_at": None})
        with self.assertRaises(provider.ProviderError):
            p.create_database(NAME, key="another-create")
        self.assertIsNone(p.last_database_create)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(
            p.delete_database(identity, key="cleanup"),
            {"deletionAcknowledged": True, "absenceVerified": False},
        )
        self.assertEqual(transport.call_count, 3)

    def test_supplied_optional_time_is_validated_without_losing_fractional_precision(self):
        valid = {**IDENTITY, "created_at": "2026-10-17T12:00:00.442097123456789123Z"}
        p, _ = self.adapter(envelope(valid), envelope(valid))
        identity = p.create_database(NAME, key="create")
        self.assertEqual(identity, valid)
        self.assertEqual(p.inspect_database(identity, key="inspect"), identity)
        for value in (
            None,
            "",
            False,
            "not-a-time",
            "2026-02-30T12:00:00Z",
            "2026-10-17T12:00:00+00:00",
        ):
            p, transport = self.adapter(envelope({**IDENTITY, "created_at": value}))
            with self.subTest(value=value), self.assertRaises(provider.ProviderUnknown):
                p.create_database(NAME, key="create")
            with self.assertRaises(provider.ProviderError):
                p.create_database(NAME, key="retry")
            self.assertEqual(transport.call_count, 1)

    def test_missing_uuid_or_name_never_uses_optional_time_as_ownership(self):
        for field in ("uuid", "name"):
            value = {k: v for k, v in IDENTITY.items() if k != field}
            p, transport = self.adapter(envelope(value))
            with self.subTest(field=field), self.assertRaises(provider.ProviderUnknown):
                p.create_database(NAME, key="create")
            with self.assertRaises(provider.ProviderError):
                p.inspect_database(IDENTITY, key="followup")
            self.assertEqual(transport.call_count, 1)

    def test_optional_time_never_allows_drift_or_malformed_readback_before_delete(self):
        minimal = {k: IDENTITY[k] for k in ("uuid", "name")}
        for result in (
            {**minimal, "uuid": "22222222-2222-4222-8222-222222222222"},
            {**minimal, "name": "fga-publisher-other"},
            {**minimal, "created_at": None},
            {**minimal, "created_at": "not-a-time"},
        ):
            p, transport = self.adapter(envelope(minimal), envelope(result))
            identity = p.create_database(NAME, key="create")
            with self.subTest(result=result), self.assertRaises(provider.ProviderError):
                p.delete_database(identity, key="delete")
            self.assertEqual([c.args[0] for c in transport.call_args_list], ["POST", "GET"])
        p, transport = self.adapter(envelope(IDENTITY), envelope(minimal))
        identity = p.create_database(NAME, key="create")
        with self.assertRaises(provider.ProviderError):
            p.delete_database(identity, key="delete")
        self.assertEqual(transport.call_count, 2)

    def test_cleanup_refuses_reused_name_with_different_creation_identity(self):
        p, transport = self.adapter(envelope({**IDENTITY, "created_at": "2026-10-18T12:00:00Z"}))
        with self.assertRaises(provider.ProviderError):
            p.delete_database(IDENTITY, key="cleanup")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(transport.call_args.args[0], "GET")

    def test_worker_cleanup_requires_exact_settings_and_never_calls_delete_on_drift(self):
        p, transport = self.adapter(envelope({"bindings": [{"name": "DB", "id": "other"}]}))
        with self.assertRaises(provider.ProviderError):
            p.delete_worker(NAME, {"bindings": []}, key="cleanup")
        self.assertEqual(transport.call_count, 1)

    def test_404_is_absence_observation_not_deletion_acknowledgment(self):
        p, transport = self.adapter((404, {}, b'{"success":false}'))
        self.assertEqual(p.delete_database(IDENTITY, key="cleanup"), {"absent": True})
        self.assertEqual(transport.call_count, 1)

    def test_no_retry_and_unknown_latches_closed_without_disclosing_response(self):
        responses = [
            (302, {"Location": "https://elsewhere.invalid/"}, b""),
            (503, {}, TOKEN.encode()),
            (200, {}, b"not-json"),
            envelope({}, success=False),
            OSError(TOKEN),
        ]
        for response in responses:
            with self.subTest(response=type(response).__name__):
                p, transport = self.adapter(response)
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    with self.assertRaises(provider.ProviderUnknown) as caught:
                        p.create_database(NAME, key="first")
                    with self.assertRaises(provider.ProviderError):
                        p.inspect_database(IDENTITY, key="second")
                self.assertEqual(transport.call_count, 1)
                emitted = str(caught.exception) + stdout.getvalue() + stderr.getvalue()
                self.assertNotIn(TOKEN, emitted)

    def test_durable_before_hook_crossing_lifetime_never_dispatches_transport(self):
        clock = Mock(return_value=0.0)

        def slow_journal_hook(*_):
            clock.return_value = 1.0

        instance, transport = self.adapter(
            envelope(IDENTITY),
            monotonic=clock,
            before_request=slow_journal_hook,
            limits=replace(provider.Limits(), total_seconds=1),
        )
        with self.assertRaises(provider.ProviderError):
            instance.create_database(NAME, key="expires-during-journal")
        transport.assert_not_called()
        with self.assertRaises(provider.ProviderError):
            instance.inspect_database(IDENTITY, key="after-expiry")
        transport.assert_not_called()

    def test_post_hook_remaining_lifetime_controls_transport_timeout(self):
        clock = Mock(return_value=0.0)

        def slow_journal_hook(*_):
            clock.return_value = 0.75

        instance, transport = self.adapter(
            envelope(IDENTITY),
            monotonic=clock,
            before_request=slow_journal_hook,
            limits=replace(provider.Limits(), total_seconds=1),
        )
        instance.create_database(NAME, key="admitted-after-journal")
        self.assertLessEqual(transport.call_args.args[4], 0.25)

    def test_call_key_and_cumulative_budgets_reject_before_transport(self):
        for limits, key in (
            (replace(provider.Limits(), calls=1), "second"),
            (provider.Limits(), "first"),
        ):
            p, transport = self.adapter(envelope(IDENTITY), limits=limits)
            p.inspect_database(IDENTITY, key="first")
            with self.assertRaises(provider.ProviderError):
                p.inspect_database(IDENTITY, key=key)
            self.assertEqual(transport.call_count, 1)

    def test_response_limit_is_cumulative_and_single_response_is_bounded(self):
        response = envelope(IDENTITY)
        length = len(response[2])
        p, transport = self.adapter(
            response, response, limits=replace(provider.Limits(), total_response_bytes=length)
        )
        p.inspect_database(IDENTITY, key="one")
        with self.assertRaises(provider.ProviderError):
            p.inspect_database(IDENTITY, key="two")
        self.assertEqual(transport.call_count, 1)
        p, _ = self.adapter(response, limits=replace(provider.Limits(), response_bytes=length - 1))
        with self.assertRaises(provider.ProviderUnknown):
            p.inspect_database(IDENTITY, key="oversize")

    def test_deadline_returns_unknown_and_does_not_replay_pending_operation(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(*args):
            entered.set()
            release.wait(2)
            return envelope(IDENTITY)

        transport = Mock(side_effect=blocked)
        p = provider.CloudflareProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            transport=transport,
            limits=replace(provider.Limits(), request_seconds=0.02),
        )
        try:
            with self.assertRaises(provider.ProviderUnknown):
                p.create_database(NAME, key="pending")
            self.assertTrue(entered.is_set())
            with self.assertRaises(provider.ProviderError):
                p.inspect_database(IDENTITY, key="observe-on-closed-adapter")
            self.assertEqual(transport.call_count, 1)
        finally:
            release.set()

    def test_http_transport_uses_fixed_tls_origin_finite_read_and_closes(self):
        response = Mock(status=302)
        response.headers = Message()
        response.read.return_value = b"redirect"
        response.getheaders.return_value = [("Location", "https://elsewhere.invalid")]
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(
            provider.http.client, "HTTPSConnection", return_value=connection
        ) as factory:
            status, _, _ = provider.https_transport("GET", "/synthetic", None, {}, 0.5, 41)
        factory.assert_called_once_with("api.cloudflare.com", timeout=0.5)
        response.read.assert_called_once_with(42)
        connection.request.assert_called_once_with("GET", "/synthetic", body=None, headers={})
        connection.close.assert_called_once()
        self.assertEqual(status, 302)

    def test_scope_and_digest_refusals_do_not_dispatch(self):
        p, transport = self.adapter()
        for action in (
            lambda: p.create_database("production", key="create"),
            lambda: p.inspect_worker("../production", key="worker"),
            lambda: p.migrate(IDENTITY, b"synthetic", "0" * 64, key="sql"),
            lambda: p.inspect_database({**IDENTITY, "uuid": "../other"}, key="db"),
        ):
            with self.assertRaises(provider.ProviderError):
                action()
        transport.assert_not_called()

    def test_empty_database_proof_reads_schema_and_refuses_hidden_user_objects(self):
        for rows in ([], [{"name": "_cf_KV"}]):
            p, transport = self.adapter(envelope([{"success": True, "results": rows}]))
            self.assertIs(p.verify_empty_database(IDENTITY, key="empty"), True)
            body = json.loads(transport.call_args.args[2])
            self.assertIn("sqlite_schema", body["sql"])
            self.assertEqual(body["params"], [])
        for result in (
            [{"success": True, "results": [{"name": "production_data"}]}],
            [{"success": True, "results": [{"name": "_cf_KV", "extra": True}]}],
            [{"success": False, "results": []}],
            [],
        ):
            p, _ = self.adapter(envelope(result))
            with self.subTest(result=result), self.assertRaises(provider.ProviderError):
                p.verify_empty_database(IDENTITY, key="empty")

    def test_module_readback_is_exact_single_module_and_etag_bound(self):
        module = b"export default {fetch(){return new Response('synthetic')}}"
        digest = hashlib.sha256(module).hexdigest()
        part = (
            b'--synthetic\r\nContent-Disposition: form-data; name="worker.js"; '
            b'filename="worker.js"\r\nContent-Type: application/javascript+module\r\n\r\n'
            + module
            + b"\r\n"
        )
        body = part + b"--synthetic--\r\n"
        headers = {"content-type": "multipart/form-data; boundary=synthetic", "etag": "exact-etag"}
        p, _ = self.adapter((200, headers, body))
        self.assertEqual(
            p.inspect_module(NAME, digest, key="module"),
            {"moduleSha2_256": digest, "etag": "exact-etag"},
        )
        for altered_headers, altered_body in (
            (headers, part + part + b"--synthetic--\r\n"),
            (headers, body.replace(module, b"changed")),
            ({"content-type": headers["content-type"]}, body),
        ):
            p, _ = self.adapter((200, altered_headers, altered_body))
            with self.assertRaises(provider.ProviderError):
                p.inspect_module(NAME, digest, key="module")

    def test_journal_metadata_never_contains_request_or_response_secrets(self):
        before, after = Mock(), Mock()
        p, _ = self.adapter(
            envelope([{"success": True}]), before_request=before, after_request=after
        )
        sql = b"SELECT 'synthetic-private-sql-value';"
        p.migrate(IDENTITY, sql, hashlib.sha256(sql).hexdigest(), key="migration")
        metadata = repr(before.call_args_list) + repr(after.call_args_list)
        self.assertNotIn(TOKEN, metadata)
        self.assertNotIn("synthetic-private-sql-value", metadata)
        self.assertEqual(before.call_args.args[:2], ("migration", True))

    def test_residual_response_allowance_is_passed_before_dispatch(self):
        response = envelope(IDENTITY)
        length = len(response[2])
        p, transport = self.adapter(
            response, response, limits=replace(provider.Limits(), total_response_bytes=length + 7)
        )
        p.inspect_database(IDENTITY, key="first")
        with self.assertRaises(provider.ProviderUnknown):
            p.inspect_database(IDENTITY, key="second")
        self.assertEqual(transport.call_args.args[5], 7)

    def test_malformed_mutation_identity_latches_unknown_before_any_followup(self):
        for result in ({}, {**IDENTITY, "uuid": "invalid"}, {**IDENTITY, "name": "production"}):
            p, transport = self.adapter(envelope(result))
            with self.subTest(result=result), self.assertRaises(provider.ProviderUnknown):
                p.create_database(NAME, key="create")
            with self.assertRaises(provider.ProviderError):
                p.inspect_database(IDENTITY, key="followup")
            self.assertEqual(transport.call_count, 1)

    def test_public_worker_upload_is_always_zero_call_refused(self):
        p, transport = self.adapter()
        with self.assertRaises(provider.ProviderError):
            p.upload_worker(NAME, b"synthetic", "0" * 64, {}, "a" * 64, key="upload")
        transport.assert_not_called()
        self.assertEqual(p.calls, 0)

    def test_invalid_token_and_oversized_request_headers_never_dispatch(self):
        for token in ("a" * 4097, "ÃƒÂ©", "contains space", "line\nfeed", "\x7f"):
            with self.subTest(token_length=len(token)), self.assertRaises(provider.ProviderError):
                provider.CloudflareProvider(ACCOUNT, token, [NAME], [NAME], transport=Mock())
        connection = Mock()
        with patch.object(provider.http.client, "HTTPSConnection", return_value=connection):
            with self.assertRaises(provider.ProviderError):
                provider.https_transport("GET", "/synthetic", None, {"X-Large": "x" * 8192}, 1, 10)
        connection.request.assert_not_called()
        connection.connect.assert_not_called()
        connection.close.assert_called_once()

    def test_actual_http_parser_rejects_ambiguous_framing_and_caps_chunk_metadata(self):
        class FakeSocket:
            def __init__(self, raw):
                self.stream = io.BytesIO(raw)
                self.received = 0

            def settimeout(self, timeout):
                self.timeout = timeout

            def recv_into(self, buffer):
                data = self.stream.read(len(buffer))
                buffer[: len(data)] = data
                self.received += len(data)
                return len(data)

        def parse(raw, cap=64):
            sock = FakeSocket(raw)
            connection = Mock(sock=sock)

            def getresponse():
                response = connection.response_class(sock)
                response.begin()
                return response

            connection.getresponse.side_effect = getresponse
            with patch.object(provider.http.client, "HTTPSConnection", return_value=connection):
                return provider.https_transport("GET", "/synthetic", None, {}, 1, cap)

        self.assertEqual(
            parse(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n")[2],
            b"{}",
        )
        for headers in (
            b"Content-Length: 2\r\nContent-Length: 2\r\n",
            b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n",
            b"Content-Encoding: gzip\r\n",
            b"Transfer-Encoding: gzip\r\n",
        ):
            with self.subTest(headers=headers), self.assertRaises(provider.ProviderUnknown):
                parse(b"HTTP/1.1 200 OK\r\n" + headers + b"\r\n{}")
        for truncated in (
            b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n",
            (
                b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                b"2\r\n{}\r\n0\r\nX-Synthetic: yes\r\n"
            ),
        ):
            with (
                self.subTest(truncated=truncated),
                self.assertRaises((provider.ProviderUnknown, provider.http.client.IncompleteRead)),
            ):
                parse(truncated)
        chunks = (b"1;" + b"x" * 900 + b"\r\na\r\n") * 80
        with self.assertRaises((provider.ProviderUnknown, provider.http.client.IncompleteRead)):
            parse(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks, 100)

    def test_late_connect_and_expired_reader_cannot_send_or_receive_http_bytes(self):
        connection = Mock()
        with (
            patch.object(provider.http.client, "HTTPSConnection", return_value=connection),
            patch.object(provider.time, "monotonic", side_effect=[0, 2]),
        ):
            with self.assertRaises(provider.ProviderUnknown):
                provider.https_transport("GET", "/synthetic", None, {}, 1, 10)
        connection.request.assert_not_called()
        connection.close.assert_called_once()
        sock = Mock()
        reader = provider._WireReader(sock, 10, deadline=1)
        with patch.object(provider.time, "monotonic", return_value=2):
            with self.assertRaises(provider.ProviderUnknown):
                reader.readinto(bytearray(10))
        sock.recv_into.assert_not_called()


if __name__ == "__main__":
    unittest.main()
