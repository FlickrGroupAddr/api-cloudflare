"""Offline raw-wire proof for the proposed management-only cookie discard policy."""

import http.client
import ipaddress
import json
import socket
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution_provider as execution
from scripts import hosted_publisher_finite_client as client
from scripts import hosted_publisher_provider as provider
from tests.test_hosted_publisher_execution_transport import FakeSocket
from tests.test_hosted_publisher_provider import ACCOUNT, IDENTITY, NAME, TOKEN, envelope

COOKIE = b"Set-Cookie: synthetic-private-cookie=secret; Secure; HttpOnly\r\n"


def response(body=b"{}", headers=b"", status=200):
    return (
        f"HTTP/1.1 {status} Synthetic\r\n".encode()
        + headers
        + b"Content-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body
    )


@contextmanager
def sockets(*raw_responses):
    sockets = [FakeSocket(raw) for raw in raw_responses]
    context = Mock()
    context.wrap_socket.side_effect = sockets
    with (
        patch.object(execution.socket, "socket", side_effect=sockets) as factory,
        patch.object(execution.ssl, "create_default_context", return_value=context),
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS")),
    ):
        yield sockets, factory


class ManagementResponsePolicyTests(unittest.TestCase):
    sockets = staticmethod(sockets)

    def request(self, *, cap=4096):
        return client.Request(
            "https://api.cloudflare.com/client/v4/accounts/" + ACCOUNT + "/d1/database",
            {},
            5,
            cap,
            105,
            b"GET /synthetic HTTP/1.1\r\nHost: api.cloudflare.com\r\n\r\n",
        )

    def parse(self, raw, *, selected=True, request=None, clock=lambda: 100):
        with self.sockets(raw) as (sockets, factory):
            try:
                return execution._pinned_https(
                    request or self.request(),
                    ipaddress.ip_address("1.1.1.1"),
                    clock,
                    discard_set_cookie=selected,
                )
            finally:
                self.assertEqual(factory.call_count, 1)
                self.assertEqual(len(sockets[0].sent), 1)
                self.assertTrue(sockets[0].closed)

    def test_cookie_values_are_discarded_and_all_raw_bytes_are_charged(self):
        raw = response(headers=COOKIE + COOKIE.replace(b"Set-Cookie", b"sEt-CoOkIe"))
        result = self.parse(raw)
        self.assertEqual(result.body, b"{}")
        self.assertEqual(result.wire_bytes, len(raw))
        self.assertNotIn("set-cookie", result.headers)
        self.assertNotIn("synthetic-private-cookie", repr(result))

    def test_strict_default_still_refuses_repeated_cookie_fields(self):
        with self.assertRaisesRegex(client.UnknownOutcome, "execution_duplicate_response_header$"):
            self.parse(response(headers=COOKIE * 2), selected=False)

    def test_discarded_cookie_fields_consume_header_count_ceiling(self):
        self.assertEqual(
            self.parse(response(headers=COOKIE * 98), request=self.request(cap=100000)).body, b"{}"
        )
        with self.assertRaisesRegex(client.UnknownOutcome, "execution_header_limit"):
            self.parse(response(headers=COOKIE * 99), request=self.request(cap=100000))

    def test_discarded_cookie_fields_consume_header_and_wire_byte_ceilings(self):
        with self.assertRaisesRegex(client.UnknownOutcome, "execution_header_limit"):
            self.parse(
                response(headers=b"Set-Cookie: " + b"x" * 65520 + b"\r\n"),
                request=self.request(cap=100000),
            )
        raw = response(headers=COOKIE * 2)
        with self.assertRaisesRegex(client.UnknownOutcome, "execution_response_wire_limit"):
            self.parse(raw, request=self.request(cap=len(raw) - 1))

    def test_cookie_lines_are_validated_before_discard(self):
        for field in (
            b"Set-Cookie: value\x00secret\r\n",
            b"Set-Cookie: value\x7fsecret\r\n",
            b"Set-Cookie : value\r\n",
            b" Set-Cookie: value\r\n",
            b"Set-Cookie: value\n",
            COOKIE + b" folded-secret\r\n",
        ):
            with self.subTest(field=field[:12]), self.assertRaises(client.UnknownOutcome):
                self.parse(response(headers=field))

    def test_all_other_duplicate_fields_remain_unknown_with_closed_categories(self):
        for name, category in (
            (b"Content-Length", "framing"),
            (b"Transfer-Encoding", "framing"),
            (b"Content-Type", "content"),
            (b"Content-Encoding", "content"),
            (b"WWW-Authenticate", "auth"),
            (b"Proxy-Authenticate", "auth"),
            (b"Authentication-Info", "auth"),
            (b"Authorization", "auth"),
            (b"X-Synthetic-Private-Name", "other"),
        ):
            raw = response(
                headers=COOKIE + name + b": private\r\n" + name.lower() + b": secret\r\n"
            )
            with self.subTest(name=name), self.assertRaises(client.UnknownOutcome) as caught:
                self.parse(raw)
            self.assertEqual(
                str(caught.exception), "execution_duplicate_response_header_" + category
            )

    def test_cookie_discard_does_not_relax_framing_redirect_or_authentication(self):
        for raw in (
            b"HTTP/1.1 200 OK\r\n" + COOKIE + b"\r\n{}",
            response(headers=COOKIE + b"Transfer-Encoding: chunked\r\n"),
            response(headers=COOKIE + b"Content-Encoding: gzip\r\n"),
            response(headers=COOKIE + b"Location: https://elsewhere.invalid/\r\n"),
            response(headers=COOKIE, status=302),
            b"HTTP/1.1 100 Continue\r\n" + COOKIE + b"\r\n" + response(),
            b"HTTP/1.1 200 OK\r\n" + COOKIE + b"Content-Length: 50\r\n\r\n{}",
        ):
            with (
                self.subTest(size=len(raw)),
                self.assertRaises((client.UnknownOutcome, http.client.IncompleteRead)),
            ):
                self.parse(raw)

    def test_chunked_cookie_response_retains_strict_trailer_checks(self):
        prefix = b"HTTP/1.1 200 OK\r\n" + COOKIE * 2 + b"Transfer-Encoding: chunked\r\n\r\n"
        self.assertEqual(self.parse(prefix + b"2\r\n{}\r\n0\r\n\r\n").body, b"{}")
        for trailer in (COOKIE * 2, b"Content-Length: 2\r\n", b"Authorization: private\r\n"):
            with self.subTest(trailer=trailer[:12]), self.assertRaises(client.UnknownOutcome):
                self.parse(prefix + b"2\r\n{}\r\n0\r\n" + trailer + b"\r\n")

    def test_cookie_body_does_not_escape_body_limit_or_absolute_deadline(self):
        with self.assertRaises(client.UnknownOutcome):
            self.parse(response(b"x" * 4097, COOKIE), request=self.request())
        readings = iter((100, 100, 100, 100, 100, 106))
        with self.assertRaisesRegex(client.UnknownOutcome, "execution_response_deadline"):
            self.parse(response(headers=COOKIE), clock=lambda: next(readings))


if __name__ == "__main__":
    unittest.main()


class ManagementPolicyCompositionTests(unittest.TestCase):
    sockets = staticmethod(sockets)

    # This class's provider checks explicitly opt in through the private synthetic
    # transport seam. No public constructor or runtime caller selects the proposal.
    def adapter(self, *, proposed=True, before=None, after=None, clock=lambda: 100):
        permit = Mock(remaining_seconds=Mock(return_value=5.0))
        concrete = execution._ManagementTransport(
            ACCOUNT, "1.1.1.1", permit, clock, proposed_discard_set_cookie=proposed
        )
        instance = execution.ExecutionBetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            permit=permit,
            management_address="1.1.1.1",
            exclusive_owner=True,
            transport=concrete,
            monotonic=clock,
            before_request=before,
            after_request=after,
        )
        concrete.provider = instance
        return instance

    def test_candidate_cookie_response_has_no_cookie_in_next_management_request(self):
        body = envelope(IDENTITY)[2]
        adapter = self.adapter()
        with self.sockets(response(body, COOKIE * 2), response(body)) as (sockets, factory):
            self.assertEqual(adapter.inspect_database(IDENTITY, key="first"), IDENTITY)
            self.assertEqual(adapter.inspect_database(IDENTITY, key="second"), IDENTITY)
        self.assertEqual(factory.call_count, 2)
        for sock in sockets:
            wire = sock.sent[0].lower()
            self.assertNotIn(b"cookie:", wire)
            self.assertNotIn(b"synthetic-private-cookie", wire)
            self.assertIn(b"authorization: bearer " + TOKEN.encode(), wire)

    def test_unselected_management_and_probe_client_remain_strict(self):
        from tests.test_hosted_publisher_execution_transport import ExecutionTransportTests

        adapter = self.adapter(proposed=False)
        body = envelope(IDENTITY)[2]
        with self.sockets(response(body, COOKIE * 2)) as (_, factory):
            with self.assertRaises(provider.ProviderUnknown):
                adapter.inspect_database(IDENTITY, key="strict")
            with self.assertRaises(provider.ProviderError):
                adapter.inspect_database(IDENTITY, key="no-replay")
        self.assertEqual(factory.call_count, 1)
        permit = Mock(remaining_seconds=Mock(return_value=5.0))
        dispatch = execution.ExecutionClientTransport(
            "https://synthetic.workers.dev", "1.1.1.1", permit=permit, clock=lambda: 100
        )
        request = ExecutionTransportTests().client_request()
        with self.sockets(response(headers=COOKIE * 2)) as (_, factory):
            with self.assertRaises(client.UnknownOutcome):
                dispatch(request)
            with self.assertRaises(provider.ProviderError):
                dispatch(request)
        self.assertEqual(factory.call_count, 1)

    def test_candidate_rejects_non_boolean_selection_before_any_socket(self):
        with patch.object(execution.socket, "socket") as factory:
            for flag in (None, 1, "true"):
                with self.subTest(flag=flag), self.assertRaises(provider.ProviderError):
                    self.adapter(proposed=flag)  # pyright: ignore[reportArgumentType]
        factory.assert_not_called()

    def test_unknown_create_preserves_consumed_intent_and_never_infers_identity(self):
        before, after = Mock(), Mock()
        adapter = self.adapter(before=before, after=after)
        raw = response(envelope(IDENTITY)[2], COOKIE + b"X-Private: one\r\nX-Private: two\r\n")
        with self.sockets(raw) as (_, factory):
            with self.assertRaises(provider.ProviderUnknown) as caught:
                adapter.create_database(NAME, key="create")
            with self.assertRaises(provider.ProviderError):
                adapter.create_database(NAME, key="different-key")
            with self.assertRaises(provider.ProviderError):
                adapter.delete_database(IDENTITY, key="unsafe-inference")
        self.assertEqual(factory.call_count, 1)
        self.assertIn(NAME, adapter._created_names)
        self.assertIn("create", adapter._keys)
        self.assertEqual(adapter._databases, {})
        before.assert_called_once()
        after.assert_not_called()
        self.assertNotIn("private", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_unknown_delete_keeps_exact_known_reference_without_success_or_replay(self):
        before, after = Mock(), Mock()
        adapter = self.adapter(before=before, after=after)
        adapter.restore_owned_resources(database=IDENTITY)
        raw_unknown = response(
            envelope({})[2], COOKIE + b"Content-Type: one\r\nContent-Type: two\r\n"
        )
        with self.sockets(response(envelope(IDENTITY)[2], COOKIE * 2), raw_unknown) as (_, factory):
            with self.assertRaises(provider.ProviderUnknown):
                adapter.delete_database(IDENTITY, key="delete")
            with self.assertRaises(provider.ProviderError):
                adapter.delete_database(IDENTITY, key="retry")
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(adapter._databases, {IDENTITY["uuid"]: IDENTITY})
        self.assertIn("delete", adapter._keys)
        self.assertEqual(before.call_count, 2)
        self.assertEqual(after.call_count, 1)  # Identity observation only.
        self.assertEqual(after.call_args.args[0], "delete:identity")

    def test_identity_drift_still_prevents_delete_after_valid_cookie_response(self):
        adapter = self.adapter()
        adapter.restore_owned_resources(database=IDENTITY)
        drift = {**IDENTITY, "created_at": "2026-10-18T12:00:00Z"}
        with self.sockets(response(envelope(drift)[2], COOKIE * 2)) as (sockets, factory):
            with self.assertRaises(provider.ProviderError):
                adapter.delete_database(IDENTITY, key="delete")
        self.assertEqual(factory.call_count, 1)
        self.assertTrue(sockets[0].sent[0].startswith(b"GET "))
        self.assertEqual(adapter._databases, {IDENTITY["uuid"]: IDENTITY})

    def test_authentication_failure_does_not_become_cookie_compatibility_success(self):
        adapter = self.adapter()
        raw = response(json.dumps({"success": False}).encode(), COOKIE * 2, status=401)
        with self.sockets(raw) as (_, factory):
            with self.assertRaises(provider.ProviderUnknown):
                adapter.create_database(NAME, key="unauthenticated")
            with self.assertRaises(provider.ProviderError):
                adapter.create_database(NAME, key="no-replay")
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(adapter._databases, {})

    def test_public_execution_provider_keeps_the_strict_management_default(self):
        permit = Mock(remaining_seconds=Mock(return_value=5.0))
        adapter = execution.ExecutionBetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [NAME],
            [NAME],
            permit=permit,
            management_address="1.1.1.1",
            exclusive_owner=True,
            monotonic=lambda: 100,
        )
        with self.sockets(response(envelope(IDENTITY)[2], COOKIE * 2)) as (_, factory):
            with self.assertRaises(provider.ProviderUnknown):
                adapter.inspect_database(IDENTITY, key="strict-public-constructor")
            with self.assertRaises(provider.ProviderError):
                adapter.inspect_database(IDENTITY, key="no-replay")
        self.assertEqual(factory.call_count, 1)

    def test_malformed_or_unsuccessful_body_cannot_supply_a_create_identity(self):
        for body in (b"not-json", b"{}", b"[]", b'{"success":false,"result":{}}'):
            adapter = self.adapter()
            with (
                self.subTest(body=body[:10]),
                self.sockets(response(body, COOKIE * 2)) as (_, factory),
            ):
                with self.assertRaises(provider.ProviderUnknown):
                    adapter.create_database(NAME, key="create")
                with self.assertRaises(provider.ProviderError):
                    adapter.create_database(NAME, key="retry")
            self.assertEqual(factory.call_count, 1)
            self.assertIn(NAME, adapter._created_names)
            self.assertEqual(adapter._databases, {})
