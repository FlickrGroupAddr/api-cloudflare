"""Synthetic sockets exercise the execution adapter's actual HTTPS parser."""

import http.client
import io
import ipaddress
import socket
import threading
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution_provider as execution
from scripts import hosted_publisher_finite_client as client
from scripts import hosted_publisher_provider as provider
from tests.test_hosted_publisher_provider import ACCOUNT, IDENTITY, NAME, TOKEN, envelope


class FakeSocket:
    def __init__(self, response):
        self.stream = io.BytesIO(response)
        self.sent = []
        self.connected = []
        self.closed = False
        self.timeouts = []

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def connect(self, address):
        self.connected.append(address)

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, count):
        return self.stream.read(count)

    def close(self):
        self.closed = True


class ExecutionTransportTests(unittest.TestCase):
    def permit(self):
        return Mock(remaining_seconds=Mock(return_value=5.0))

    def request(self, *, url="https://synthetic.workers.dev/probe/seed", cap=4096):
        return client.Request(
            url,
            {"Authorization": "Bearer synthetic-client-token"},
            5,
            cap,
            105,
            b"POST /probe/seed HTTP/1.1\r\nHost: synthetic.workers.dev\r\n\r\n",
        )

    def client_request(self):
        headers = {
            "Host": "synthetic.workers.dev",
            "Connection": "close",
            "Content-Length": "0",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "X-Probe-Access": "d" * 64,
            "X-Probe-Artifact": "a" * 64,
            "X-Probe-Run": "b" * 64,
            "X-Probe-Resource": "11111111-1111-4111-8111-111111111111",
            "X-Probe-Scenario": "happy",
        }
        wire = (
            "POST /__publisher/seed HTTP/1.1\r\n"
            + "".join(f"{key}: {value}\r\n" for key, value in headers.items())
            + "\r\n"
        ).encode()
        return client.Request(
            "https://synthetic.workers.dev/__publisher/seed",
            headers,
            5,
            4096,
            105,
            wire,
        )

    def parse(self, raw, *, request=None, clock=lambda: 100):
        self.sock = FakeSocket(raw)
        self.context = Mock()
        self.context.wrap_socket.return_value = self.sock
        with (
            patch.object(execution.socket, "socket", return_value=self.sock) as factory,
            patch.object(execution.ssl, "create_default_context", return_value=self.context),
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS")),
        ):
            result = execution._pinned_https(
                request or self.request(), ipaddress.ip_address("1.1.1.1"), clock
            )
        self.assertEqual(factory.call_count, 1)
        return result

    def test_numeric_connect_hostname_tls_and_exact_one_request_without_ambient_proxy(self):
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://proxy.invalid:9"}):
            result = self.parse(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
        self.assertEqual(result.body, b"{}")
        self.assertEqual(self.sock.connected, [("1.1.1.1", 443)])
        self.context.wrap_socket.assert_called_once_with(
            self.sock, server_hostname="synthetic.workers.dev"
        )
        self.assertEqual(self.sock.sent, [self.request().wire])
        self.assertTrue(self.sock.closed)

    def test_ambiguous_incomplete_and_encoded_responses_are_unknown(self):
        for raw in (
            b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
            b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{}",
            b"Content-Encoding: gzip\r\nContent-Length: 2\r\n\r\n{}",
            b"Transfer-Encoding: gzip\r\n\r\n{}",
            b"Content-Length: 2\r\nMalformed header\r\nTransfer-Encoding: chunked\r\n\r\n{}",
            b"Content-Length: 20\r\n\r\n{}",
            b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}XX0\r\n\r\n",
            b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n",
            b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\nContent-Length: 9\r\n\r\n",
        ):
            with (
                self.subTest(raw=raw[:50]),
                self.assertRaises((client.UnknownOutcome, http.client.IncompleteRead)),
            ):
                self.parse(b"HTTP/1.1 200 OK\r\n" + raw)
            self.assertEqual(len(self.sock.sent), 1)
            self.assertTrue(self.sock.closed)

    def test_body_and_framing_budget_and_timeout_never_retry(self):
        for raw in (
            b"HTTP/1.1 200 OK\r\nContent-Length: 4097\r\n\r\n" + b"x" * 4097,
            b"HTTP/1.1 200 OK\r\nX-Large: " + b"x" * 70000 + b"\r\n\r\n",
        ):
            with (
                self.subTest(length=len(raw)),
                self.assertRaises((client.UnknownOutcome, http.client.HTTPException)),
            ):
                self.parse(raw)
            self.assertLessEqual(len(self.sock.sent), 1)
        with patch.object(execution.socket, "socket") as factory:
            with self.assertRaises(provider.ProviderError):
                execution._pinned_https(
                    self.request(), ipaddress.ip_address("1.1.1.1"), lambda: 106
                )
        factory.assert_not_called()

    def test_valid_client_wire_redirect_unknown_latches_without_retry(self):
        dispatch = execution.ExecutionClientTransport(
            "https://synthetic.workers.dev",
            "1.1.1.1",
            permit=self.permit(),
            clock=lambda: 100,
        )
        sock = FakeSocket(
            b"HTTP/1.1 302 Found\r\nLocation: https://other.invalid/\r\nContent-Length: 0\r\n\r\n"
        )
        context = Mock()
        context.wrap_socket.return_value = sock
        with (
            patch.object(execution.socket, "socket", return_value=sock) as factory,
            patch.object(execution.ssl, "create_default_context", return_value=context),
        ):
            with self.assertRaises(client.UnknownOutcome):
                dispatch(self.client_request())
            with self.assertRaises(provider.ProviderError):
                dispatch(self.client_request())
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(sock.sent, [self.client_request().wire])

    def test_exhausted_response_wire_latches_without_retry(self):
        dispatch = execution.ExecutionClientTransport(
            "https://synthetic.workers.dev",
            "1.1.1.1",
            permit=self.permit(),
            clock=lambda: 100,
        )
        wire = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        request = replace(self.client_request(), max_response_bytes=len(wire) - 1)
        sock = FakeSocket(wire)
        context = Mock()
        context.wrap_socket.return_value = sock
        with (
            patch.object(execution.socket, "socket", return_value=sock) as factory,
            patch.object(execution.ssl, "create_default_context", return_value=context),
        ):
            with self.assertRaisesRegex(client.UnknownOutcome, "execution_response_wire_limit"):
                dispatch(request)
            with self.assertRaises(provider.ProviderError):
                dispatch(request)
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(sock.sent, [request.wire])
        self.assertEqual(sock.stream.tell(), request.max_response_bytes)
        self.assertTrue(sock.closed)

    def test_interim_response_cannot_hide_conflicting_framing(self):
        raw = (
            b"HTTP/1.1 100 Continue\r\nContent-Length: 90\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        )
        with self.assertRaises(client.UnknownOutcome):
            self.parse(raw)

    def test_no_body_status_cannot_carry_a_json_acknowledgement(self):
        for status in (204, 205):
            with self.subTest(status=status), self.assertRaises(client.UnknownOutcome):
                self.parse(
                    f"HTTP/1.1 {status} No Content\r\nContent-Length: 2\r\n\r\n{{}}".encode()
                )

    def test_management_route_credential_and_unknown_latch_use_production_subclass(self):
        permit = self.permit()
        transport = Mock(
            side_effect=[envelope(IDENTITY), (302, {"Location": "https://other.invalid"}, b"")]
        )
        adapter = execution.ExecutionBetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            permit=permit,
            management_address="1.1.1.1",
            exclusive_owner=True,
            transport=transport,
            monotonic=lambda: 100,
        )
        self.assertTrue(adapter._concrete)
        adapter.inspect_database(IDENTITY, key="inspect")
        call = transport.call_args
        self.assertEqual(
            call.args[1], f"/client/v4/accounts/{ACCOUNT}/d1/database/{IDENTITY['uuid']}"
        )
        self.assertEqual(call.args[3]["Authorization"], "Bearer " + TOKEN)
        with self.assertRaises(provider.ProviderUnknown):
            adapter.inspect_database(IDENTITY, key="redirect")
        with self.assertRaises(provider.ProviderError):
            adapter.inspect_database(IDENTITY, key="no-retry")
        self.assertEqual(transport.call_count, 2)
        self.assertGreaterEqual(permit.authorize.call_count, 1)

    def test_permit_refusal_precedes_both_management_and_client_io(self):
        permit = self.permit()
        permit.authorize.side_effect = ValueError("synthetic refused")
        transport = Mock()
        with self.assertRaises(ValueError):
            adapter = execution.ExecutionBetaPublisherProvider(
                ACCOUNT,
                TOKEN,
                [NAME],
                [NAME],
                permit=permit,
                management_address="1.1.1.1",
                exclusive_owner=True,
                transport=transport,
            )
            adapter.inspect_database(IDENTITY, key="inspect")
        transport.assert_not_called()
        with patch.object(execution, "_pinned_https") as wire:
            with self.assertRaises(ValueError):
                execution.ExecutionClientTransport(
                    "https://synthetic.workers.dev",
                    "1.1.1.1",
                    permit=permit,
                )(self.request())
        wire.assert_not_called()

    def test_client_origin_is_closed_and_authorization_never_crosses_origins(self):
        permit = self.permit()
        dispatch = execution.ExecutionClientTransport(
            "https://synthetic.workers.dev",
            "1.1.1.1",
            permit=permit,
            clock=lambda: 100,
        )
        for url in (
            "https://other.workers.dev/probe/seed",
            "http://synthetic.workers.dev/probe/seed",
            "https://synthetic.workers.dev@other.invalid/probe/seed",
            "https://synthetic.workers.dev:444/probe/seed",
        ):
            with (
                self.subTest(url=url),
                patch.object(execution, "_pinned_https") as wire,
                self.assertRaises(ValueError),
            ):
                dispatch(self.request(url=url))
            wire.assert_not_called()

    def test_exact_database_cleanup_refuses_changed_creation_identity(self):
        transport = Mock(return_value=envelope({**IDENTITY, "created_at": "2026-10-18T12:00:00Z"}))
        adapter = execution.ExecutionBetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            permit=self.permit(),
            management_address="1.1.1.1",
            exclusive_owner=True,
            transport=transport,
        )
        with self.assertRaises(provider.ProviderError):
            adapter.delete_database(IDENTITY, key="cleanup-known-only")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(transport.call_args.args[0], "GET")

    def test_concrete_management_transport_uses_pinned_tls_and_exact_bearer_wire(self):
        body = envelope(IDENTITY)[2]
        sock = FakeSocket(
            b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        )
        context = Mock()
        context.wrap_socket.return_value = sock
        adapter = execution.ExecutionBetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            permit=self.permit(),
            management_address="1.1.1.1",
            exclusive_owner=True,
            monotonic=lambda: 100,
        )
        with (
            patch.object(execution.socket, "socket", return_value=sock) as factory,
            patch.object(execution.ssl, "create_default_context", return_value=context),
        ):
            self.assertEqual(adapter.inspect_database(IDENTITY, key="concrete"), IDENTITY)
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(sock.connected, [("1.1.1.1", 443)])
        context.wrap_socket.assert_called_once_with(sock, server_hostname="api.cloudflare.com")
        wire = sock.sent[0]
        self.assertTrue(
            wire.startswith(
                (
                    f"GET /client/v4/accounts/{ACCOUNT}/d1/database/{IDENTITY['uuid']} HTTP/1.1\r\n"
                ).encode()
            )
        )
        self.assertIn(b"Host: api.cloudflare.com\r\n", wire)
        self.assertIn(("Authorization: Bearer " + TOKEN + "\r\n").encode(), wire)
        self.assertIn(b"Content-Length: 0\r\n", wire)

    def test_late_permit_refusal_after_tls_cannot_send_http(self):
        sock = FakeSocket(b"")
        context = Mock()
        context.wrap_socket.return_value = sock
        guard = Mock(side_effect=[None, None, provider.ProviderError("revoked")])
        with (
            patch.object(execution.socket, "socket", return_value=sock),
            patch.object(execution.ssl, "create_default_context", return_value=context),
        ):
            with self.assertRaises(provider.ProviderError):
                execution._pinned_https(
                    self.request(), ipaddress.ip_address("1.1.1.1"), lambda: 100, guard
                )
        self.assertEqual(sock.sent, [])
        self.assertTrue(sock.closed)

    def test_delayed_management_daemon_cannot_rebase_original_deadline(self):
        owner = threading.current_thread()
        daemon_reads = 0

        def clock():
            nonlocal daemon_reads
            if threading.current_thread() is owner:
                return 100.0
            daemon_reads += 1
            return 100.0 if daemon_reads == 1 else 130.0

        adapter = execution.ExecutionBetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            permit=self.permit(),
            management_address="1.1.1.1",
            exclusive_owner=True,
            monotonic=clock,
        )
        with patch.object(execution.socket, "socket") as factory:
            with self.assertRaises(provider.ProviderUnknown):
                adapter.inspect_database(IDENTITY, key="delayed-daemon")
        factory.assert_not_called()
