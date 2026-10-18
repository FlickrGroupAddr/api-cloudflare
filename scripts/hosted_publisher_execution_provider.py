"""Separately gated concrete transport for the accepted finite Beta ceremony.

The sealed offline adapters remain unchanged. These derivatives preserve their
identity, budget, durable-intent and unknown-outcome rules while selecting the
concrete HTTPS boundary explicitly. Construction performs no I/O. The runtime
permit must independently validate the exact reviewed plan, consent, source,
grant and remaining deadline before construction and every possible dispatch.
Transport injection is trusted synthetic test code, never an authority boundary.
"""

from __future__ import annotations

import http.client
import io
import ipaddress
import math
import re
import socket
import ssl
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from typing import cast
from urllib.parse import urlsplit

from scripts.hosted_publisher_finite_client import Request, Response, UnknownOutcome
from scripts.hosted_publisher_provider import ProviderError
from scripts.hosted_publisher_worker_deployment import BetaPublisherProvider
from scripts.hosted_publisher_worker_identity import BetaWorkerProvider


def _authorize(permit):
    if not callable(getattr(permit, "authorize", None)):
        raise ProviderError("execution_permit_required")
    permit.authorize()


def _remaining(permit):
    if not callable(getattr(permit, "remaining_seconds", None)):
        raise ProviderError("execution_permit_deadline_required")
    remaining = permit.remaining_seconds()
    if type(remaining) not in (int, float) or not math.isfinite(remaining) or remaining <= 0:
        raise ProviderError("execution_permit_deadline_exhausted")
    return remaining


def _address(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError, TypeError:
        raise ProviderError("execution_numeric_address_required") from None
    # This boundary cannot be used to reach local services or metadata endpoints.
    if not address.is_global:
        raise ProviderError("execution_public_address_required")
    return address


def _origin(endpoint):
    host = None
    try:
        url = urlsplit(endpoint)
        host = url.hostname
        valid = (
            url.scheme == "https"
            and url.hostname
            and re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,252}", url.hostname)
            and url.port in (None, 443)
            and endpoint == "https://" + url.hostname
        )
    except ValueError, TypeError:
        valid = False
    if not valid:
        raise ProviderError("execution_exact_origin_required")
    return host


class _WireReader(io.RawIOBase):
    def __init__(self, connection, request, clock):
        self.connection, self.request, self.clock = connection, request, clock
        self.received = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        remaining = self.request.deadline - self.clock()
        if remaining <= 0:
            raise UnknownOutcome("execution_response_deadline")
        self.connection.settimeout(min(self.request.timeout, remaining))
        data = self.connection.recv(
            min(len(buffer), self.request.max_response_bytes - self.received + 1)
        )
        self.received += len(data)
        if self.received > self.request.max_response_bytes:
            raise UnknownOutcome("execution_response_wire_limit")
        buffer[: len(data)] = data
        return len(data)


class _ResponseSocket:
    def __init__(self, reader):
        self.reader = reader

    def makefile(self, mode):
        if mode != "rb":
            raise UnknownOutcome("execution_response_stream_mode")
        return io.BufferedReader(self.reader, buffer_size=4096)


class _StrictResponse(http.client.HTTPResponse):
    def __init__(self, sock, *, discard_set_cookie=False):
        super().__init__(sock)
        self.discard_set_cookie = discard_set_cookie

    def _duplicate_header(self, name):
        if not self.discard_set_cookie:
            raise UnknownOutcome("execution_duplicate_response_header")
        # Closed cookie-discard diagnostics: never expose arbitrary field names
        # or any field value through the sanitized failure boundary.
        category = {
            b"content-length": "framing",
            b"transfer-encoding": "framing",
            b"content-type": "content",
            b"content-encoding": "content",
            b"www-authenticate": "auth",
            b"proxy-authenticate": "auth",
            b"authentication-info": "auth",
            b"authorization": "auth",
        }.get(name, "other")
        raise UnknownOutcome("execution_duplicate_response_header_" + category)

    @staticmethod
    def _header(line):
        # Validate raw lines before the email-based stdlib parser can silently
        # stop parsing on a malformed field and hide a later framing field.
        match = re.fullmatch(rb"([!#$%&'*+.^_`|~0-9A-Za-z-]+):[ \t]*([^\r\n]*)\r\n", line)
        if match is None or any(c < 32 and c != 9 or c == 127 for c in match[2]):
            raise UnknownOutcome("execution_header_syntax_invalid")
        return match[1].lower(), match[2]

    def begin(self):
        if self.headers is not None:
            return
        line = self.fp.readline(65_537)
        status = re.fullmatch(rb"HTTP/1\.[01] ([2-5][0-9]{2})(?: [\t\x20-\x7e]*)?\r\n", line)
        # This client never sends Expect and does not implement streaming or
        # upgrades. Unsolicited informational responses are therefore refused.
        if status is None:
            raise UnknownOutcome("execution_status_or_interim_refused")
        self.code = self.status = int(status[1])
        # Every successful operation in this finite protocol requires a JSON
        # acknowledgement. A body on a bodyless status cannot supply one.
        if self.status in {204, 205, 304}:
            raise UnknownOutcome("execution_bodyless_status_refused")
        self.reason = line.decode("ascii").strip().split(" ", 2)[-1]
        self.version = 11 if line.startswith(b"HTTP/1.1 ") else 10
        raw, names, total, field_count = [], set(), len(line), 0
        while True:
            line = self.fp.readline(65_537)
            total += len(line)
            if total > 65_536 or field_count >= 100:
                raise UnknownOutcome("execution_header_limit")
            if line == b"\r\n":
                break
            name, _ = self._header(line)
            field_count += 1
            # Stateless cookie compatibility: RFC 9110 section 5.3
            # recognizes repeated Set-Cookie fields. Validate/count every raw
            # line, then discard it; never parse, retain or resend cookies.
            # Trailers deliberately keep their existing strict checks.
            if self.discard_set_cookie and name == b"set-cookie":
                continue
            if name in names:
                self._duplicate_header(name)
            names.add(name)
            raw.append(line)
        self.headers = self.msg = http.client.parse_headers(io.BytesIO(b"".join(raw) + b"\r\n"))
        self.chunked = self.headers.get("transfer-encoding", "").lower() == "chunked"
        self.chunk_left = None
        self.length = None
        length = self.headers.get("content-length")
        if length is not None and re.fullmatch(r"[0-9]{1,10}", length) and not self.chunked:
            self.length = int(length)
        self.will_close = True

    def _read_and_discard_trailer(self):
        # Require a real terminating CRLF. EOF is not a complete acknowledgement.
        names, total = set(), 0
        while True:
            line = self.fp.readline(65_537)
            total += len(line)
            if line == b"\r\n":
                return
            if total > 65_536 or len(names) >= 100:
                raise UnknownOutcome("execution_trailer_limit")
            name, _ = self._header(line)
            # Trailers cannot revise framing, routing, authentication or the
            # content metadata already used to interpret an acknowledgement.
            if name in names or name in {
                b"content-length",
                b"transfer-encoding",
                b"content-encoding",
                b"content-type",
                b"host",
                b"authorization",
                b"location",
                b"connection",
                b"trailer",
                b"cache-control",
            }:
                raise UnknownOutcome("execution_trailer_field_refused")
            names.add(name)

    def _get_chunk_left(self):
        if self.chunk_left == 0:
            if self._safe_read(2) != b"\r\n":  # pyright: ignore[reportAttributeAccessIssue]
                raise UnknownOutcome("execution_chunk_separator_invalid")
            self.chunk_left = None
        return super()._get_chunk_left()  # pyright: ignore[reportAttributeAccessIssue]

    def _read_next_chunk_size(self):
        line = self.fp.readline(65_537)
        if len(line) > 65_536 or not re.fullmatch(rb"[a-fA-F0-9]+(?:;[^\r\n]*)?\r\n", line):
            raise UnknownOutcome("execution_chunk_size_invalid")
        return int(line.split(b";", 1)[0], 16)


def _pinned_https(request, address, clock, dispatch_guard=None, *, discard_set_cookie=False):
    """Single numeric-address TLS connection; hostname verification remains on.

    No DNS, proxy lookup, redirect following or retry is available. All decrypted
    HTTP bytes (headers, body, chunks and trailers) share the wire ceiling.
    The default refuses every duplicate response field. The accepted metadata
    opt-in and disabled proposed management candidate use
    ``discard_set_cookie=True`` to discard validated/budgeted Set-Cookie header
    fields, including repetitions; all other duplicate/trailer checks remain.
    No cookie jar, persistence or automatic cookie request behavior exists.
    """
    url = urlsplit(request.url)
    if (
        type(request.timeout) not in (int, float)
        or not math.isfinite(request.timeout)
        or not 0 < request.timeout <= 60
        or type(request.deadline) not in (int, float)
        or not math.isfinite(request.deadline)
        or type(request.max_response_bytes) is not int
        or not 0 < request.max_response_bytes <= 2_162_688
        or not isinstance(request.wire, bytes)
        or type(discard_set_cookie) is not bool
    ):
        raise ProviderError("execution_request_limits_invalid")
    remaining = request.deadline - clock()
    if remaining <= 0:
        raise ProviderError("execution_admission_deadline")
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    raw = socket.socket(family, socket.SOCK_STREAM)
    connection = None

    def fence_timeout():
        if dispatch_guard is not None:
            dispatch_guard()
        allowance = request.deadline - clock()
        if allowance <= 0:
            raise UnknownOutcome("execution_dispatch_deadline")
        return min(request.timeout, allowance)

    try:
        raw.settimeout(fence_timeout())
        raw.connect((str(address), 443))
        raw.settimeout(fence_timeout())
        connection = ssl.create_default_context().wrap_socket(raw, server_hostname=url.hostname)
        connection.settimeout(fence_timeout())
        connection.sendall(request.wire)
        reader = _WireReader(connection, request, clock)
        response = _StrictResponse(
            cast(socket.socket, _ResponseSocket(reader)), discard_set_cookie=discard_set_cookie
        )
        try:
            response.begin()
            headers = {}
            for key, value in response.getheaders():
                key = key.lower()
                if key in headers:
                    response._duplicate_header(key.encode("ascii"))
                headers[key] = value
            length, transfer = headers.get("content-length"), headers.get("transfer-encoding")
            if (
                (length is not None and transfer is not None)
                or (transfer is not None and transfer.lower() != "chunked")
                or (length is not None and not re.fullmatch(r"[0-9]{1,10}", length))
                or headers.get("content-encoding", "identity").lower() != "identity"
                or "location" in headers
                or 300 <= response.status < 400
            ):
                raise UnknownOutcome("execution_response_framing_or_redirect")
            # Require an explicit framing terminator rather than EOF framing.
            if length is None and transfer is None:
                raise UnknownOutcome("execution_response_framing_missing")
            if length is not None and int(length) > request.max_response_bytes:
                raise UnknownOutcome("execution_response_body_limit")
            body = response.read(request.max_response_bytes + 1)
            if len(body) > request.max_response_bytes or (
                length is not None and (len(body) != int(length) or response.length != 0)
            ):
                raise UnknownOutcome("execution_response_incomplete")
            if clock() >= request.deadline:
                raise UnknownOutcome("execution_response_deadline")
            return Response(response.status, headers, body, reader.received)
        finally:
            response.close()
    finally:
        if connection is not None:
            connection.close()
        raw.close()


class ExecutionClientTransport:
    """Exact-origin finite client transport; the existing client owns journaling."""

    def __init__(self, endpoint, address, *, permit, clock=time.monotonic):
        _authorize(permit)
        _remaining(permit)
        self.host = _origin(endpoint)
        self.endpoint, self.address, self.permit, self.clock = (
            endpoint,
            _address(address),
            permit,
            clock,
        )
        self._closed = False
        self._lock = threading.Lock()

    def __call__(self, request):
        if not self._lock.acquire(blocking=False):
            raise ProviderError("execution_client_concurrent_call")
        try:
            _authorize(self.permit)
            if self._closed or not isinstance(request, Request):
                raise ProviderError("execution_client_closed_or_invalid")
            phase = request.url.removeprefix(self.endpoint + "/__publisher/")
            if phase not in ("seed", "http", "materialize", "attach", "title", "remove", "finish"):
                raise ProviderError("execution_client_target_invalid")
            expected_headers = {
                "Host",
                "Connection",
                "Content-Length",
                "Accept",
                "Accept-Encoding",
                "X-Probe-Access",
                "X-Probe-Artifact",
                "X-Probe-Run",
                "X-Probe-Resource",
                "X-Probe-Scenario",
            }
            headers = request.headers
            if (
                set(headers) != expected_headers
                or headers.get("Host") != self.host
                or headers.get("Connection") != "close"
                or headers.get("Content-Length") != "0"
                or headers.get("Accept") != "application/json"
                or headers.get("Accept-Encoding") != "identity"
                or any(not isinstance(v, str) or "\r" in v or "\n" in v for v in headers.values())
            ):
                raise ProviderError("execution_client_headers_invalid")
            wire = (
                f"POST /__publisher/{phase} HTTP/1.1\r\n"
                + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                + "\r\n"
            ).encode("ascii")
            if wire != request.wire or len(wire) > 8192 or request.max_response_bytes > 65_536:
                raise ProviderError("execution_client_wire_invalid")
            try:
                remaining = _remaining(self.permit)
                bounded = replace(
                    request,
                    timeout=min(request.timeout, remaining),
                    deadline=min(request.deadline, self.clock() + remaining),
                )
                return _pinned_https(bounded, self.address, self.clock, self.permit.authorize)
            except Exception:
                self._closed = True
                raise
        finally:
            self._lock.release()


class _ManagementTransport:
    """Strict management transport with a disabled offline policy candidate.

    Only synthetic qualification selects ``proposed_discard_set_cookie=True``.
    ExecutionBetaPublisherProvider always constructs the strict default; no
    execution caller or CLI selects this proposed exception. Owner acceptance,
    reviewed integration and fresh source-bound action authority remain required.
    """

    def __init__(self, account, address, permit, clock, *, proposed_discard_set_cookie=False):
        if type(proposed_discard_set_cookie) is not bool:
            raise ProviderError("execution_management_response_policy_invalid")
        self._proposed_discard_set_cookie = proposed_discard_set_cookie
        _remaining(permit)
        self.account, self.address, self.permit, self.clock = (
            account,
            _address(address),
            permit,
            clock,
        )
        self.provider: ExecutionBetaPublisherProvider | None = None

    def __call__(self, method, path, data, headers, timeout, response_bytes):
        admitted_at = self.clock()
        if self.provider is None:
            raise ProviderError("execution_management_session_required")
        self.provider._dispatch_guard()
        timeout = min(timeout, _remaining(self.permit))
        absolute = self.provider._dispatch_deadline
        if absolute is None:
            raise ProviderError("execution_management_admission_required")
        deadline = min(admitted_at + timeout, absolute)
        prefix = "/client/v4/accounts/" + self.account + "/"
        if (
            method not in {"GET", "POST", "PATCH", "DELETE"}
            or not path.startswith(prefix)
            or not re.fullmatch(r"[A-Za-z0-9_/?=&.-]+", path)
            or ".." in path
            or not isinstance(headers, dict)
            or set(headers) != {"Authorization", "Content-Type", "Accept-Encoding"}
            or any(not isinstance(v, str) or "\r" in v or "\n" in v for v in headers.values())
        ):
            raise ProviderError("execution_management_request_invalid")
        body = b"" if data is None else data
        wire_headers = {
            "Host": "api.cloudflare.com",
            "Connection": "close",
            "Content-Length": str(len(body)),
            **headers,
        }
        head = (
            f"{method} {path} HTTP/1.1\r\n"
            + "".join(f"{k}: {v}\r\n" for k, v in wire_headers.items())
            + "\r\n"
        ).encode("ascii")
        if len(head) > 8192:
            raise ProviderError("execution_management_header_limit")
        request = Request(
            "https://api.cloudflare.com" + path,
            wire_headers,
            timeout,
            response_bytes + 65_536,
            deadline,
            head + body,
        )
        response = _pinned_https(
            request,
            self.address,
            self.clock,
            self.provider._dispatch_guard,
            discard_set_cookie=self._proposed_discard_set_cookie,
        )
        if len(response.body) > response_bytes:
            raise ProviderError("execution_management_payload_limit")
        return response.status, response.headers, response.body


class ExecutionBetaWorkerProvider(BetaWorkerProvider):
    """Concrete identity derivative composed with the single provider session."""

    @contextmanager
    def _operation(self):
        cast(ExecutionBetaPublisherProvider, self._provider)._guard()
        if not self._lock.acquire(blocking=False):
            raise ProviderError("worker_concurrent_operation_forbidden")
        try:
            yield
        finally:
            self._lock.release()


class ExecutionBetaPublisherProvider(BetaPublisherProvider):
    """Explicit Beta selection; inherited caps, hooks, identity and unknown latch."""

    def __init__(
        self,
        account,
        token,
        worker_names,
        database_names,
        *,
        permit,
        management_address,
        limits=None,
        transport=None,
        monotonic=time.monotonic,
        before_request=None,
        after_request=None,
        exclusive_owner=False,
    ):
        _authorize(permit)
        self._permit = permit
        self._dispatch_deadline: float | None = None
        concrete = _ManagementTransport(account, management_address, permit, monotonic)

        super().__init__(
            account,
            token,
            worker_names,
            database_names,
            exclusive_owner=exclusive_owner,
            limits=limits,
            transport=concrete if transport is None else transport,
            monotonic=monotonic,
            before_request=before_request,
            after_request=after_request,
        )
        # The separate derivative explicitly selects real execution. An injected
        # callable must never masquerade as authorization to bypass offline guards.
        self._concrete = True
        concrete.provider = self
        self.identity = ExecutionBetaWorkerProvider(
            account, token, self.worker_names, shared_provider=self
        )

    def _guard(self):
        _authorize(self._permit)
        if self._closed:
            raise ProviderError("execution_provider_closed")

    def _dispatch_guard(self):
        self._guard()
        if self._dispatch_deadline is None or self._clock() >= self._dispatch_deadline:
            raise ProviderError("execution_provider_admission_deadline")

    def _request_locked(self, method, path, body, *, key, media, raw):
        # The operator owns the public durable hooks. Wrap them only while the
        # inherited exclusive request lock is held, then restore exactly those
        # hooks so composition's clean-constructor ownership check still holds.
        before_request, after_request = self.before_request, self.after_request

        def before(key, mutation, metadata):
            if before_request is not None:
                before_request(key, mutation, metadata)
            # Conservative absolute deadline captured after durable intent.
            self._dispatch_deadline = min(
                self._clock() + self.limits.request_seconds,
                self._started + self.limits.total_seconds,
            )

        def after(key, metadata):
            # Late/unknown results must not become durable success receipts.
            self._dispatch_guard()
            if after_request is not None:
                after_request(key, metadata)

        self.before_request, self.after_request = before, after
        try:
            value = super()._request_locked(method, path, body, key=key, media=media, raw=raw)
        finally:
            self.before_request, self.after_request = before_request, after_request
        if self._dispatch_deadline is None or self._clock() >= self._dispatch_deadline:
            self._unknown("execution_provider_late_completion")
        return value
