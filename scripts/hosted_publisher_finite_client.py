"""Finite #0121 client; no command-line live execution or ambient credentials.

The immutable Worker does not echo deployment identity. Receipts bind a request to
the separately verified deployment; they do not attest the deployed D1 overlay.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import ipaddress
import json
import math
import re
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, cast
from urllib.parse import urlsplit

PHASES = ("seed", "http", "materialize", "attach", "title", "remove", "finish")
SCENARIOS = ("happy", "create_lost", "attachment_lost", "title_lost")
HEX = re.compile(r"[0-9a-f]{64}")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class Refused(ValueError):
    """No dispatch is allowed."""


class UnknownOutcome(RuntimeError):
    """Dispatch may have happened. Never replay this phase."""


FAILURE_CODES = {
    "admission": "local_admission_failed",
    "reservation": "phase_reservation_failed",
    "pre_dispatch": "local_pre_dispatch_failed",
    "transport": "transport_failed",
    "response_accounting": "response_accounting_failed",
    "response_fence": "response_fence_failed",
    "response_status": "http_status_refused",
    "response_headers": "response_headers_refused",
    "response_oracle": "response_oracle_refused",
    "activity_accounting": "activity_accounting_failed",
    "journal_complete": "journal_completion_failed",
    "journal_unknown": "journal_unknown_failed",
    "operator": "lifecycle_failed",
}


def validate_failure_diagnostic(value: dict) -> dict:
    """Copy only a closed local category and optional exact parsed HTTP status.

    Never derive these fields from exception text, response bodies or headers.
    This describes where local progress stopped, not a remote root cause.
    """
    if (
        type(value) is not dict
        or set(value) not in ({"stage", "code"}, {"stage", "code", "parsedHttpStatus"})
        or type(value.get("stage")) is not str
        or value["stage"] not in FAILURE_CODES
        or type(value.get("code")) is not str
        or value["code"] != FAILURE_CODES[value["stage"]]
        or (
            "parsedHttpStatus" in value
            and (
                type(value["parsedHttpStatus"]) is not int
                or not 100 <= value["parsedHttpStatus"] <= 599
            )
        )
    ):
        raise Refused("invalid local failure diagnostic")
    return dict(value)


def failure_diagnostic(stage: str, status: int | None = None) -> dict:
    value: dict = {"stage": stage, "code": FAILURE_CODES[stage]}
    if type(status) is int and 100 <= status <= 599:
        value["parsedHttpStatus"] = status
    return validate_failure_diagnostic(value)


@dataclass(frozen=True)
class ClientIdentity:
    endpoint: str
    artifact_sha256: str
    run_id: str
    resource_id: str
    scenario: str
    expires_at: float

    def __post_init__(self) -> None:
        url = urlsplit(self.endpoint)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.port not in (None, 443)
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or not url.hostname.isascii()
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", url.hostname)
            or self.endpoint != f"https://{url.hostname}"
        ):
            raise Refused("exact HTTPS origin required")
        if (
            not HEX.fullmatch(self.artifact_sha256)
            or not HEX.fullmatch(self.run_id)
            or not UUID.fullmatch(self.resource_id)
            or self.resource_id == "00000000-0000-0000-0000-000000000000"
            or self.scenario not in SCENARIOS
            or type(self.expires_at) not in (int, float)
            or not math.isfinite(self.expires_at)
        ):
            raise Refused("invalid client identity")

    def receipt_identity(self) -> dict:
        return {
            "scenario": self.scenario,
            "runId": self.run_id,
            "resourceId": self.resource_id,
            "artifactSha256": self.artifact_sha256,
        }


@dataclass
class SharedBudget:
    max_requests: int
    max_request_bytes: int
    max_response_bytes: int
    deadline: float
    max_provider_calls: int = 448
    max_synthetic_posts: int = 28
    requests: int = field(default=0, init=False)
    request_bytes: int = field(default=0, init=False)
    response_bytes: int = field(default=0, init=False)
    provider_calls: int = field(default=0, init=False)
    synthetic_posts: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        for value in (
            self.max_requests,
            self.max_request_bytes,
            self.max_response_bytes,
            self.max_provider_calls,
            self.max_synthetic_posts,
        ):
            if type(value) is not int or value <= 0:
                raise Refused("positive integer budget required")
        if (
            self.max_requests > 128
            or self.max_provider_calls > 448
            or self.max_synthetic_posts > 28
            or type(self.deadline) not in (int, float)
            or not math.isfinite(self.deadline)
        ):
            raise Refused("budget exceeds closed run")

    def remaining(self, clock: Callable[[], float]) -> float:
        value = self.deadline - clock()
        if value <= 0:
            raise Refused("deadline exhausted")
        return value

    def reserve_request(self, count: int) -> None:
        if (
            self.requests >= self.max_requests
            or self.request_bytes + count > self.max_request_bytes
        ):
            raise Refused("request budget exhausted")
        self.requests += 1
        self.request_bytes += count

    def charge_response(self, count: int) -> None:
        if type(count) is not int or count < 0:
            raise Refused("invalid response accounting")
        self.response_bytes += count
        if self.response_bytes > self.max_response_bytes:
            raise UnknownOutcome("response budget exhausted")


@dataclass(frozen=True)
class Request:
    url: str
    headers: dict[str, str] = field(repr=False)
    timeout: float
    max_response_bytes: int
    deadline: float
    wire: bytes = field(repr=False)


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes = field(repr=False)
    wire_bytes: int | None = None


class Journal(Protocol):
    def reserve(self, key: str, payload: dict) -> bool: ...
    def complete(self, key: str, receipt: dict) -> None: ...
    def unknown(self, key: str, reason: str, diagnostic: dict | None = None) -> None: ...


class _DeadlineReader(io.RawIOBase):
    def __init__(self, connection: ssl.SSLSocket, request: Request, clock: Callable[[], float]):
        self.connection, self.request, self.clock = connection, request, clock
        self.received = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        remaining = self.request.deadline - self.clock()
        if remaining <= 0:
            raise TimeoutError("deadline")
        self.connection.settimeout(remaining)
        # Count every HTTP wire byte, including headers and chunk framing.
        data = self.connection.recv(
            min(len(buffer), self.request.max_response_bytes - self.received + 1)
        )
        self.received += len(data)
        if self.received > self.request.max_response_bytes:
            raise UnknownOutcome("response limit")
        buffer[: len(data)] = data
        return len(data)


class _ResponseSocket:
    def __init__(self, reader: _DeadlineReader):
        self.reader = reader

    def makefile(self, *args, **kwargs):
        return io.BufferedReader(self.reader, buffer_size=4096)


class HttpsTransport:
    """One HTTPS connection per request, no resolver, proxy, redirects or retries.

    A reviewed operator must supply an independently pinned numeric address and
    explicitly enable this transport after exact-run approval. Construction does
    not access the network. TLS still verifies the request's exact hostname.
    """

    def __init__(
        self, address: str, *, enabled: bool = False, clock: Callable[[], float] = time.monotonic
    ):
        self.address = ipaddress.ip_address(address)
        self.enabled, self.clock = enabled, clock

    def __call__(self, request: Request) -> Response:
        if not self.enabled:
            raise Refused("production transport disabled")
        url = urlsplit(request.url)
        family = socket.AF_INET6 if self.address.version == 6 else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        connection = None
        try:
            remaining = request.deadline - self.clock()
            if remaining <= 0:
                raise Refused("deadline exhausted")
            raw.settimeout(remaining)
            raw.connect((str(self.address), 443))
            raw.settimeout(max(0.001, request.deadline - self.clock()))
            connection = ssl.create_default_context().wrap_socket(raw, server_hostname=url.hostname)
            remaining = request.deadline - self.clock()
            if remaining <= 0:
                raise UnknownOutcome("deadline exhausted")
            connection.settimeout(remaining)
            connection.sendall(request.wire)
            reader = _DeadlineReader(connection, request, self.clock)
            response = http.client.HTTPResponse(cast(socket.socket, _ResponseSocket(reader)))
            response.begin()
            # Duplicated fields (especially length/type) are rejected, not collapsed.
            items = response.getheaders()
            headers = {}
            for key, value in items:
                key = key.lower()
                if key in headers:
                    raise UnknownOutcome("duplicate response header")
                headers[key] = value
            content_length = headers.get("content-length")
            transfer_encoding = headers.get("transfer-encoding")
            expected_length = None
            if transfer_encoding is not None:
                if content_length is not None or transfer_encoding.lower().strip() != "chunked":
                    raise UnknownOutcome("ambiguous response framing")
            if content_length is not None:
                if not re.fullmatch(r"[0-9]+", content_length) or len(content_length) > 10:
                    raise UnknownOutcome("invalid content length")
                expected_length = int(content_length)
                if expected_length > request.max_response_bytes:
                    raise UnknownOutcome("response limit")
            body = response.read(request.max_response_bytes + 1)
            if len(body) > request.max_response_bytes:
                raise UnknownOutcome("response limit")
            # read(amt) permits premature EOF for fixed lengths. Require both
            # the complete declared body and the parser's exhausted remainder.
            if expected_length is not None and (
                len(body) != expected_length or response.length != 0
            ):
                raise UnknownOutcome("incomplete response body")
            return Response(response.status, headers, body, reader.received)
        finally:
            if connection is not None:
                connection.close()
            raw.close()


def _strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _validate_status(response: Response) -> None:
    if type(response.status) is not int or response.status != 200:
        raise UnknownOutcome("non-success response")


def _validate_headers(response: Response) -> None:
    headers = {key.lower(): value for key, value in response.headers.items()}
    if len(headers) != len(response.headers):
        raise UnknownOutcome("duplicate response header")
    if (
        headers.get("content-type", "").split(";")[0].strip() != "application/json"
        or headers.get("cache-control") != "no-store"
        or headers.get("content-encoding", "identity") != "identity"
        or "location" in headers
    ):
        raise UnknownOutcome("response headers refused")


def _validate_oracle(response: Response, phase: str, scenario: str) -> dict:
    try:
        value = json.loads(
            response.body.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except UnicodeError, ValueError, RecursionError:
        raise UnknownOutcome("malformed response") from None
    base = {
        "schemaVersion",
        "phase",
        "scenario",
        "outcome",
        "status",
        "productionSchedulerQualified",
    }
    counters = set() if phase == "seed" else {"providerCalls", "syntheticPosts"}
    extras = set()
    expected = {
        "seed": "synthetic_seeded",
        "http": "actual_handler_admission",
        "materialize": "materialized",
        "attach": "membership_verified",
        "title": "synced",
        "remove": "local_removed_without_upstream",
        "finish": "finite_synthetic_sequence_complete",
    }[phase]
    fixed = {}
    if phase == "http":
        extras = {"albumRequests", "uploadProofs"}
        fixed = {"albumRequests": 3, "uploadProofs": 2}
    if phase == "materialize" and scenario == "create_lost":
        expected = "create_reconciled_no_replay"
        extras = {"createReplayOutcome", "repairStatus", "repairRequests"}
        fixed = {"createReplayOutcome": "no_work", "repairStatus": "materialized"}
    if (phase, scenario) in (("attach", "attachment_lost"), ("title", "title_lost")):
        extras = {"lostReplyRecovered", "reconciliationReads"}
        fixed = {"lostReplyRecovered": True}
    if (
        not isinstance(value, dict)
        or set(value) != base | counters | extras
        or type(value.get("schemaVersion")) is not int
        or value["schemaVersion"] != 1
        or value["phase"] != phase
        or value["scenario"] != scenario
        or value["outcome"] != expected
        or value["status"] != "NO-GO"
        or value["productionSchedulerQualified"] is not False
        or any(
            type(value[key]) is not type(item) or value[key] != item for key, item in fixed.items()
        )
    ):
        raise UnknownOutcome("response schema mismatch")
    for key, maximum in (
        ("providerCalls", 16),
        ("syntheticPosts", 1),
        ("repairRequests", 16),
        ("reconciliationReads", 16),
    ):
        if key in value and (type(value[key]) is not int or not 0 <= value[key] <= maximum):
            raise UnknownOutcome("response counter mismatch")
    if phase in ("materialize", "attach", "title") and value["syntheticPosts"] != 1:
        raise UnknownOutcome("missing synthetic post evidence")
    if phase in ("remove", "finish") and (value["providerCalls"] or value["syntheticPosts"]):
        raise UnknownOutcome("unexpected upstream activity")
    if "reconciliationReads" in value and value["reconciliationReads"] < 1:
        raise UnknownOutcome("missing reconciliation")
    if "repairRequests" in value and value["repairRequests"] < 1:
        raise UnknownOutcome("missing repair")
    return value


def validate_response(response: Response, phase: str, scenario: str) -> dict:
    """Validate the exact immutable Worker success shape, never an error body."""
    _validate_status(response)
    _validate_headers(response)
    return _validate_oracle(response, phase, scenario)


class FiniteClient:
    def __init__(
        self,
        identity: ClientIdentity,
        transport: Callable[[Request], Response],
        budget: SharedBudget,
        journal: Journal,
        token_supplier: Callable[[], str],
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        stop_check: Callable[[], bool] = lambda: False,
    ):
        self.identity, self.transport, self.budget, self.journal = (
            identity,
            transport,
            budget,
            journal,
        )
        self.token_supplier, self.clock, self.wall_clock = token_supplier, clock, wall_clock
        self.stop_check = stop_check
        self.started = False

    def _fence(self) -> float:
        if self.stop_check():
            raise Refused("stopped")
        lifetime = self.identity.expires_at - self.wall_clock()
        if not 0 < lifetime <= 1800:
            raise Refused("expired or excessive expiry")
        return min(60.0, lifetime, self.budget.remaining(self.clock))

    def run(self) -> dict:
        result = {**self.identity.receipt_identity(), "status": "refused", "phaseReceipts": []}
        if self.started:
            return result
        self.started = True
        stage = "admission"
        parsed_status = None
        try:
            run_deadline = min(self.budget.deadline, self.clock() + 1800)
            self._fence()
            token = self.token_supplier()
            if not isinstance(token, str) or not HEX.fullmatch(token):
                raise Refused("invalid private token")
            for phase in PHASES:
                timeout = min(self._fence(), run_deadline - self.clock())
                if timeout <= 0:
                    raise Refused("deadline")
                key = phase
                metadata = {**self.identity.receipt_identity(), "phase": phase}
                # Durable once-only reservation precedes any possible endpoint dispatch.
                stage = "reservation"
                if not self.journal.reserve(key, metadata):
                    raise Refused("phase already reserved")
                try:
                    stage = "pre_dispatch"
                    timeout = min(timeout, self._fence())
                    host = urlsplit(self.identity.endpoint).hostname
                    path = f"/__publisher/{phase}"
                    headers = {
                        "Host": host,
                        "Connection": "close",
                        "Content-Length": "0",
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                        "X-Probe-Access": token,
                        "X-Probe-Artifact": self.identity.artifact_sha256,
                        "X-Probe-Run": self.identity.run_id,
                        "X-Probe-Resource": self.identity.resource_id,
                        "X-Probe-Scenario": self.identity.scenario,
                    }
                    wire = (
                        "POST "
                        + path
                        + " HTTP/1.1\r\n"
                        + "".join(f"{key}: {value}\r\n" for key, value in headers.items())
                        + "\r\n"
                    ).encode("ascii")
                    reserved_calls, reserved_posts = (0, 0) if phase == "seed" else (16, 1)
                    if (
                        self.budget.provider_calls + reserved_calls > self.budget.max_provider_calls
                        or self.budget.synthetic_posts + reserved_posts
                        > self.budget.max_synthetic_posts
                    ):
                        raise Refused("synthetic activity budget exhausted")
                    self.budget.reserve_request(len(wire))
                    limit = min(65536, self.budget.max_response_bytes - self.budget.response_bytes)
                    if limit <= 0:
                        raise Refused("response budget exhausted")
                    request = Request(
                        self.identity.endpoint + path,
                        headers,
                        timeout,
                        limit,
                        min(run_deadline, self.clock() + timeout),
                        wire,
                    )
                    # Unknown outcomes retain the worst-case activity reservation.
                    self.budget.provider_calls += reserved_calls
                    self.budget.synthetic_posts += reserved_posts
                    stage = "transport"
                    response = self.transport(request)
                    # Only an exact, bounded parser status may enter diagnostics.
                    parsed_status = response.status
                    stage = "response_accounting"
                    used = response.wire_bytes
                    if used is None:
                        used = (
                            len(response.body)
                            + sum(len(k) + len(v) + 4 for k, v in response.headers.items())
                            + 32
                        )
                    if type(used) is not int or used < len(response.body) or used > limit:
                        raise UnknownOutcome("invalid response accounting")
                    self.budget.charge_response(used)
                    stage = "response_fence"
                    self._fence()
                    if self.clock() >= request.deadline:
                        raise UnknownOutcome("late response")
                    stage = "response_status"
                    _validate_status(response)
                    stage = "response_headers"
                    _validate_headers(response)
                    stage = "response_oracle"
                    checked = _validate_oracle(response, phase, self.identity.scenario)
                    stage = "activity_accounting"
                    calls, posts = checked.get("providerCalls", 0), checked.get("syntheticPosts", 0)
                    self.budget.provider_calls += calls - reserved_calls
                    self.budget.synthetic_posts += posts - reserved_posts
                    if (
                        self.budget.provider_calls > self.budget.max_provider_calls
                        or self.budget.synthetic_posts > self.budget.max_synthetic_posts
                    ):
                        raise UnknownOutcome("synthetic activity budget exceeded")
                    receipt = {
                        **metadata,
                        **checked,
                        "responseSha256": hashlib.sha256(response.body).hexdigest(),
                    }
                    stage = "journal_complete"
                    self.journal.complete(key, receipt)
                    result["phaseReceipts"].append(receipt)
                    parsed_status = None
                    stage = "admission"
                except Exception:
                    # Never persist exception text, headers, body, or token.
                    result["status"] = "unknown"
                    result["diagnostic"] = failure_diagnostic(stage, parsed_status)
                    try:
                        self.journal.unknown(key, "phase_outcome_unknown", result["diagnostic"])
                    except Exception:
                        # Persistence can remain an intent. Never downgrade to a
                        # pre-dispatch refusal or replay after a failed seal.
                        result["diagnostic"] = failure_diagnostic("journal_unknown", parsed_status)
                    return result
            result["status"] = "complete"
        except Exception:
            # A reservation failure or pre-dispatch fence refuses the entire sequence.
            result["status"] = "refused"
            result["diagnostic"] = failure_diagnostic(stage, parsed_status)
        return result


def main() -> None:
    raise SystemExit("NO-GO: live client entrypoint disabled; exact operator approval required.")


if __name__ == "__main__":
    main()
