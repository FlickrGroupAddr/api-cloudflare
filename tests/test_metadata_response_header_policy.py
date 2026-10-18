"""Synthetic raw HTTP responses exercise the metadata-only cookie opt-in."""

import http.client
import io
import ipaddress
import socket
import unittest
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution_provider as execution
from scripts import hosted_publisher_finite_client as finite
from scripts.hosted_publisher_provider import ProviderError


class SyntheticSocket:
    def __init__(self, raw):
        self.stream = io.BytesIO(raw)
        self.sent = []
        self.closed = False

    def settimeout(self, seconds):
        pass

    def connect(self, address):
        assert address == ("1.1.1.1", 443)

    def sendall(self, raw):
        self.sent.append(raw)

    def recv(self, size):
        return self.stream.read(size)

    def close(self):
        self.closed = True


class MetadataResponseHeaderPolicyTests(unittest.TestCase):
    def request(self, cap=65_536):
        return finite.Request(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            {"Host": "api.cloudflare.com", "Accept": "application/json"},
            5,
            cap,
            105,
            b"GET /client/v4/user/tokens/verify HTTP/1.1\r\n"
            b"Host: api.cloudflare.com\r\nAccept: application/json\r\n\r\n",
        )

    def parse(self, raw, *, opt_in=True, cap=65_536, clock=lambda: 100):
        self.sock = SyntheticSocket(raw)
        context = Mock()
        context.wrap_socket.return_value = self.sock
        with (
            patch.object(execution.socket, "socket", return_value=self.sock) as factory,
            patch.object(execution.ssl, "create_default_context", return_value=context),
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS")),
        ):
            try:
                options = {"discard_set_cookie": True} if opt_in else {}
                return execution._pinned_https(
                    self.request(cap), ipaddress.ip_address("1.1.1.1"), clock, **options
                )
            finally:
                self.assertEqual(factory.call_count, 1)
                self.assertEqual(self.sock.sent, [self.request(cap).wire])
                self.assertTrue(self.sock.closed)

    def response(self, headers=b"", *, status=b"200 OK", body=b"{}"):
        return (
            b"HTTP/1.1 "
            + status
            + b"\r\n"
            + headers
            + b"Content-Type: application/json\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\n\r\n"
            + body
        )

    def test_repeated_cookies_are_discarded_only_with_explicit_metadata_opt_in(self):
        raw = self.response(
            b"Set-Cookie: synthetic-cookie-one=first; Expires=Wed, 21 Oct 2037 07:28:00 GMT\r\n"
            b"sEt-CoOkIe: synthetic-cookie-two=second; Secure; HttpOnly\r\n"
        )
        with self.assertRaises(finite.UnknownOutcome):
            self.parse(raw, opt_in=False)
        result = self.parse(raw)
        self.assertEqual(result.body, b"{}")
        self.assertEqual(
            result.headers, {"content-type": "application/json", "content-length": "2"}
        )
        self.assertEqual(result.wire_bytes, len(raw))
        self.assertNotIn("synthetic-cookie", repr(result))
        # A later connection cannot inherit a cookie from the previous response.
        self.parse(self.response())
        self.assertNotIn(b"Cookie:", self.sock.sent[0])
        self.assertNotIn(b"synthetic-cookie", self.sock.sent[0])

    def test_even_one_cookie_is_discarded_with_opt_in_but_default_is_unchanged(self):
        raw = self.response(b"Set-Cookie: synthetic-cookie=one\r\n")
        self.assertIn("set-cookie", self.parse(raw, opt_in=False).headers)
        self.assertNotIn("set-cookie", self.parse(raw).headers)

    def test_every_other_repeated_field_stays_refused(self):
        for name, value in (
            (b"Content-Length", b"2"),
            (b"Transfer-Encoding", b"chunked"),
            (b"Content-Type", b"application/json"),
            (b"Content-Encoding", b"identity"),
            (b"Authorization", b"synthetic"),
            (b"WWW-Authenticate", b"Bearer"),
            (b"Location", b"https://other.invalid/"),
            (b"Cookie", b"synthetic=one"),
            (b"X-Unknown", b"one"),
        ):
            fields = name + b": " + value + b"\r\n" + name.lower() + b": " + value + b"\r\n"
            with self.subTest(field=name), self.assertRaises(finite.UnknownOutcome):
                self.parse(self.response(b"Set-Cookie: synthetic=ignored\r\n" + fields))

    def test_duplicate_diagnostics_use_fixed_categories_without_provider_field_values(self):
        for name, category in (
            (b"Content-Length", "framing"),
            (b"Transfer-Encoding", "framing"),
            (b"Content-Type", "content"),
            (b"Content-Encoding", "content"),
            (b"WWW-Authenticate", "auth"),
            (b"Authorization", "auth"),
            (b"Location", "other"),
            (b"X-Synthetic-Private-Name", "other"),
        ):
            field = name + b": synthetic-private-value\r\n"
            raw = self.response(field * 2)
            with self.subTest(field=name), self.assertRaises(finite.UnknownOutcome) as caught:
                self.parse(raw)
            self.assertEqual(
                str(caught.exception), "execution_duplicate_response_header_" + category
            )
            with self.assertRaises(finite.UnknownOutcome) as strict:
                self.parse(raw, opt_in=False)
            self.assertEqual(str(strict.exception), "execution_duplicate_response_header")

    def test_discarded_cookie_lines_still_require_valid_http_field_syntax(self):
        for line in (
            b"Set-Cookie: value\x00hidden\r\n",
            b"Set-Cookie: value\x7fhidden\r\n",
            b"Set-Cookie : value\r\n",
            b" Set-Cookie: folded\r\n",
            b"Set-Cookie: unterminated\n",
            b"Malformed header\r\n",
        ):
            with self.subTest(line=line), self.assertRaises(finite.UnknownOutcome):
                self.parse(self.response(b"Set-Cookie: synthetic=one\r\n" + line))

    def test_cookie_lines_count_toward_header_count_and_header_byte_limits(self):
        # Existing parser admits at most 99 fields because the terminating CRLF
        # participates in its 100-line check. Discarding must not change that.
        accepted = self.response(b"Set-Cookie: synthetic=one\r\n" * 97)
        self.assertEqual(self.parse(accepted).body, b"{}")
        for raw in (
            self.response(b"Set-Cookie: synthetic=one\r\n" * 98),
            self.response(b"Set-Cookie: " + b"x" * 65_500 + b"\r\n"),
        ):
            with self.subTest(size=len(raw)), self.assertRaises(finite.UnknownOutcome):
                self.parse(raw, cap=100_000)

    def test_wire_budget_includes_every_discarded_cookie_byte(self):
        raw = self.response(b"Set-Cookie: synthetic=one\r\nSet-Cookie: synthetic=two\r\n")
        self.assertEqual(self.parse(raw, cap=len(raw)).wire_bytes, len(raw))
        with self.assertRaises(finite.UnknownOutcome):
            self.parse(raw, cap=len(raw) - 1)

    def test_cookie_opt_in_requires_an_explicit_boolean_before_connect(self):
        for value in (None, 1, "true", [], {}):
            with (
                self.subTest(value=value),
                patch.object(execution.socket, "socket") as factory,
                self.assertRaises(ProviderError),
            ):
                execution._pinned_https(
                    self.request(),
                    ipaddress.ip_address("1.1.1.1"),
                    lambda: 100,
                    discard_set_cookie=value,  # pyright: ignore[reportArgumentType]
                )
            factory.assert_not_called()

    def test_cookie_stream_cannot_outlive_response_deadline(self):
        raw = self.response(b"Set-Cookie: synthetic=one\r\nSet-Cookie: synthetic=two\r\n")
        # Small synthetic TLS reads force another deadline check while parsing
        # cookies, rather than returning a complete response in one buffer.
        with (
            patch.object(
                SyntheticSocket, "recv", lambda sock, size: sock.stream.read(min(size, 16))
            ),
            self.assertRaises(finite.UnknownOutcome) as caught,
        ):
            self.parse(raw, clock=lambda: 105 if self.sock.stream.tell() >= 64 else 100)
        self.assertEqual(str(caught.exception), "execution_response_deadline")

    def test_opt_in_cannot_hide_status_redirect_framing_or_body_refusals(self):
        cookie = b"Set-Cookie: synthetic=one\r\nSet-Cookie: synthetic=two\r\n"
        for raw in (
            self.response(cookie, status=b"100 Continue"),
            self.response(cookie, status=b"204 No Content"),
            self.response(cookie, status=b"205 Reset Content"),
            self.response(cookie, status=b"304 Not Modified"),
            self.response(cookie, status=b"302 Found"),
            self.response(cookie + b"Location: https://other.invalid/\r\n"),
            self.response(cookie + b"Content-Encoding: gzip\r\n"),
            self.response(cookie + b"Transfer-Encoding: chunked\r\n"),
            b"HTTP/1.1 200 OK\r\n" + cookie + b"\r\n{}",
            b"HTTP/1.1 200 OK\r\n" + cookie + b"Content-Length: 3\r\n\r\n{}",
        ):
            with (
                self.subTest(raw=raw[:30]),
                self.assertRaises((finite.UnknownOutcome, http.client.IncompleteRead)),
            ):
                self.parse(raw)

    def test_chunked_body_and_trailers_keep_their_original_strict_rules(self):
        prefix = (
            b"HTTP/1.1 200 OK\r\nSet-Cookie: synthetic=one\r\nSet-Cookie: synthetic=two\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n"
        )
        raw = prefix + b"X-Synthetic: accepted\r\n\r\n"
        self.assertEqual(self.parse(raw).wire_bytes, len(raw))
        for trailer in (
            b"Set-Cookie: one\r\nSet-Cookie: two\r\n\r\n",
            b"Set-Cookie: bad\x00value\r\n\r\n",
            b"Content-Type: text/plain\r\n\r\n",
            b"Location: https://other.invalid/\r\n\r\n",
            b"X-Synthetic: one\r\nX-Synthetic: two\r\n\r\n",
            b"",
        ):
            with (
                self.subTest(trailer=trailer),
                self.assertRaises((finite.UnknownOutcome, http.client.IncompleteRead)),
            ):
                self.parse(prefix + trailer)


if __name__ == "__main__":
    unittest.main()
