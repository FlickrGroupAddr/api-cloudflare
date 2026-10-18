"""Finite Cloudflare primitives; construction never discovers or reads credentials.

Caller owns durable intents, consent, stop fencing and quiescence. This adapter
does not establish those facts. No CLI, account discovery, retries or broad lists.
API contracts reviewed 2026-10-17 against official Cloudflare API documentation:
https://developers.cloudflare.com/api/resources/d1/subresources/database/
https://developers.cloudflare.com/api/resources/workers/subresources/scripts/
https://developers.cloudflare.com/workers/configuration/multipart-upload-metadata/
"""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import queue
import re
import socket
import threading
import time
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from typing import cast


class ProviderError(ValueError):
    """Sanitized local rejection or unsuccessful provider response."""


class ProviderUnknown(ProviderError):
    """A submitted request may still be running; never automatically repeat."""


@dataclass(frozen=True)
class Limits:
    calls: int = 256
    request_bytes: int = 2_097_152
    response_bytes: int = 2_097_152
    total_request_bytes: int = 16_777_216
    total_response_bytes: int = 33_554_432
    socket_seconds: float = 20
    request_seconds: float = 25
    total_seconds: float = 7200


def _json(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    return (
        isinstance(value, str)
        and bool(
            re.fullmatch(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", value)
        )
        and value != "00000000-0000-0000-0000-000000000000"
    )


def validate_worker_projection(module, sha2, metadata, access_token):
    """Validate exact closed immutable candidate configuration without I/O."""
    if not isinstance(module, bytes) or _digest(module) != sha2:
        raise ProviderError("module_digest_invalid")
    expected_keys = {
        "main_module",
        "compatibility_date",
        "compatibility_flags",
        "bindings",
        "observability",
        "logpush",
    }
    if (
        not isinstance(metadata, dict)
        or set(metadata) != expected_keys
        or metadata["main_module"] != "worker.js"
        or metadata["compatibility_date"] != "2026-10-16"
        or metadata["compatibility_flags"] != ["nodejs_compat"]
        or metadata["observability"] != {"enabled": False}
        or metadata["logpush"] is not False
    ):
        raise ProviderError("worker_metadata_invalid")
    bindings = metadata["bindings"]
    allowed = {
        "DB",
        "PROBE_ENABLED",
        "PROBE_SCOPE",
        "PROBE_ACCESS_TOKEN",
        "PROBE_ARTIFACT_SHA2_256",
        "PROBE_RESOURCE_ID",
        "PROBE_RUN_ID",
        "PROBE_EXPIRES_AT",
        "PROBE_SCENARIO",
    }
    if not isinstance(bindings, list) or len(bindings) != len(allowed):
        raise ProviderError("worker_bindings_invalid")
    values = {b.get("name"): b for b in bindings if isinstance(b, dict)}
    if (
        set(values) != allowed
        or not isinstance(access_token, str)
        or not re.fullmatch(r"[a-f0-9]{64}", access_token)
    ):
        raise ProviderError("worker_bindings_invalid")
    db = values["DB"]
    if set(db) != {"name", "type", "id"} or db["type"] != "d1" or not _uuid(db["id"]):
        raise ProviderError("worker_database_binding_invalid")
    for var, binding in values.items():
        if var == "DB":
            continue
        if var == "PROBE_ACCESS_TOKEN":
            if binding != {"name": var, "type": "secret_text"}:
                raise ProviderError("worker_secret_binding_invalid")
        elif (
            set(binding) != {"name", "type", "text"}
            or binding["type"] != "plain_text"
            or not isinstance(binding["text"], str)
        ):
            raise ProviderError("worker_binding_invalid")
    texts = {n: b.get("text") for n, b in values.items()}
    if (
        texts["PROBE_SCOPE"] != "publisher-disposable-v1"
        or texts["PROBE_ENABLED"] != "1"
        or texts["PROBE_RESOURCE_ID"] != db["id"]
        or not re.fullmatch(r"[a-f0-9]{64}", texts["PROBE_ARTIFACT_SHA2_256"] or "")
        or texts["PROBE_SCENARIO"] not in {"happy", "create_lost", "attachment_lost", "title_lost"}
        or not re.fullmatch(r"[a-f0-9]{64}", texts["PROBE_RUN_ID"] or "")
    ):
        raise ProviderError("worker_projection_invalid")
    return {
        **metadata,
        "bindings": [
            {**b, "text": access_token} if b["name"] == "PROBE_ACCESS_TOKEN" else b.copy()
            for b in bindings
        ],
    }


class _WireReader(io.RawIOBase):
    """Cap decrypted HTTP message bytes, including headers/chunks/trailers."""

    def __init__(self, sock, maximum, deadline=None):
        self.sock, self.remaining = sock, maximum
        self.deadline = deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        if self.remaining <= 0:
            raise ProviderUnknown("provider_http_wire_limit")
        if self.deadline is not None:
            remaining_seconds = self.deadline - time.monotonic()
            if remaining_seconds <= 0:
                raise ProviderUnknown("provider_response_deadline")
            self.sock.settimeout(remaining_seconds)
        count = self.sock.recv_into(memoryview(buffer)[: self.remaining])
        self.remaining -= count
        return count


class _ResponseSocket:
    def __init__(self, sock, maximum, deadline=None):
        self.sock, self.maximum, self.deadline = sock, maximum, deadline

    def makefile(self, mode):
        if mode != "rb":
            raise ProviderError("provider_response_stream_mode")
        return io.BufferedReader(_WireReader(self.sock, self.maximum, self.deadline))


def https_transport(method, path, data, headers, timeout, response_bytes):
    """Fixed TLS origin; HTTP bytes <= payload allowance + 64 KiB framing.

    Request HTTP headers have a separate fixed 8 KiB ceiling, including the
    bounded ASCII bearer credential. TLS record overhead is not application
    data. Headers, interim responses,
    chunk framing and trailers all share the finite framing allowance. Across
    the run the maximum HTTP response bytes are total payload cap + 64 KiB/call.
    """
    dispatch_deadline = time.monotonic() + timeout
    connection = http.client.HTTPSConnection("api.cloudflare.com", timeout=timeout)

    # HTTPResponse normally reads sock.makefile, including header and chunk reads.
    # Wrapping that stream's raw socket caps all of those reads before buffering.
    class BoundedResponse(http.client.HTTPResponse):
        def __init__(self, sock, *args, **kwargs):
            super().__init__(
                cast(
                    socket.socket, _ResponseSocket(sock, response_bytes + 65_536, dispatch_deadline)
                ),
                *args,
                **kwargs,
            )

        def _read_and_discard_trailer(self):
            # stdlib accepts EOF here; hosted acknowledgement requires the
            # actual terminating empty CRLF line, within the raw wire cap.
            while True:
                line = self.fp.readline(65_537)
                if line == b"\r\n":
                    return
                if len(line) > 65_536 or not line.endswith(b"\r\n"):
                    raise ProviderUnknown("provider_chunk_trailer_incomplete")

        def _get_chunk_left(self):
            # stdlib discards these two bytes without checking their value.
            if self.chunk_left == 0:
                if self._safe_read(2) != b"\r\n":  # pyright: ignore[reportAttributeAccessIssue]
                    raise ProviderUnknown("provider_chunk_separator_invalid")
                self.chunk_left = None
            return super()._get_chunk_left()  # pyright: ignore[reportAttributeAccessIssue]

        def _read_next_chunk_size(self):
            line = self.fp.readline(65_537)
            if len(line) > 65_536 or not re.fullmatch(rb"[a-fA-F0-9]+(?:;[^\r\n]*)?\r\n", line):
                raise ProviderUnknown("provider_chunk_size_invalid")
            return int(line.split(b";", 1)[0], 16)

    connection.response_class = BoundedResponse
    try:
        header_bytes = len((method + " " + path + " HTTP/1.1\r\n").encode("ascii"))
        header_bytes += sum(
            len(k.encode("ascii")) + len(v.encode("ascii")) + 4 for k, v in headers.items()
        )
        # Reserve Host, Content-Length, Accept-Encoding and terminating CRLF.
        if header_bytes + 512 > 8192:
            raise ProviderError("provider_request_header_limit")
        # DNS can outlive a socket timeout. Connect before admitting any HTTP
        # bytes, then fence a late connection so it cannot send after its window.
        connection.connect()
        if time.monotonic() >= dispatch_deadline:
            raise ProviderUnknown("provider_connection_admission_expired")
        if connection.sock is None:
            raise ProviderUnknown("provider_connection_unavailable")
        connection.sock.settimeout(dispatch_deadline - time.monotonic())
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        lengths = response.headers.get_all("Content-Length", [])
        transfers = response.headers.get_all("Transfer-Encoding", [])
        encodings = response.headers.get_all("Content-Encoding", [])
        if (
            len(lengths) > 1
            or len(transfers) > 1
            or len(encodings) > 1
            or (lengths and transfers)
            or (lengths and not re.fullmatch(r"[0-9]+", lengths[0]))
            or (transfers and transfers[0].lower() != "chunked")
            or (encodings and encodings[0].lower() != "identity")
        ):
            raise ProviderUnknown("provider_response_framing_invalid")
        # One bounded read; caller independently enforces elapsed wall time.
        raw = response.read(response_bytes + 1)
        if lengths and (len(raw) != int(lengths[0]) or response.length != 0):
            raise ProviderUnknown("provider_content_length_incomplete")
        return response.status, dict(response.getheaders()), raw
    finally:
        connection.close()


class CloudflareProvider:
    """Explicit finite identity scope, with a durable-request callback seam.

    The daemon call wrapper returns at the request/total deadline even if DNS or
    a submitted provider operation cannot be cancelled. Any ambiguous outcome
    latches this adapter closed. That is observation failure, never cancellation
    proof. A later cleanup-only operator needs a new approved finite adapter.
    """

    unsupported_operations = (
        "reconcile_lost_database_create_without_uuid",
        "prove_provider_or_d1_inflight_quiescence",
        "revoke_or_verify_operator_token_revocation",
        "atomic_create_only_worker_upload",
    )

    def __init__(
        self,
        account,
        token,
        worker_names,
        database_names,
        *,
        limits=None,
        transport=None,
        monotonic=time.monotonic,
        before_request=None,
        after_request=None,
    ):
        if not isinstance(account, str) or not re.fullmatch(r"[a-f0-9]{32}", account):
            raise ProviderError("provider_account_invalid")
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 4096
            or any(not 33 <= ord(c) <= 126 for c in token)
        ):
            raise ProviderError("provider_token_invalid")
        self.worker_names, self.database_names = frozenset(worker_names), frozenset(database_names)
        if not 1 <= len(self.worker_names) <= 4 or not 1 <= len(self.database_names) <= 4:
            raise ProviderError("provider_scope_invalid")
        if any(
            not isinstance(n, str) or not re.fullmatch(r"fga-publisher-[a-z0-9-]{1,48}", n)
            for n in self.worker_names | self.database_names
        ):
            raise ProviderError("provider_name_invalid")
        caps = Limits()
        limits = caps if limits is None else limits
        for name in caps.__dataclass_fields__:
            value = getattr(limits, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 < value <= getattr(caps, name)
            ):
                raise ProviderError("provider_limits_invalid")
            if name in {
                "calls",
                "request_bytes",
                "response_bytes",
                "total_request_bytes",
                "total_response_bytes",
            } and not isinstance(value, int):
                raise ProviderError("provider_limits_invalid")
        self.account, self._token, self.limits = account, token, limits
        self._concrete = transport is None or transport is https_transport
        self._transport = transport or https_transport
        self._clock, self._started = monotonic, monotonic()
        self.before_request, self.after_request = before_request, after_request
        self.calls = self.request_bytes = self.response_bytes = 0
        self._closed = False
        self.last_status = None
        self._keys = set()
        self._databases = {}
        self._created_names = set()
        self._lock = threading.Lock()

    def _worker(self, name):
        if name not in self.worker_names:
            raise ProviderError("worker_outside_scope")
        return "/workers/scripts/" + name

    def _unknown(self, code):
        self._closed = True
        raise ProviderUnknown(code)

    def _database(self, identity):
        if not isinstance(identity, dict) or set(identity) != {"uuid", "name", "created_at"}:
            raise ProviderError("database_identity_invalid")
        if not _uuid(identity["uuid"]) or identity["name"] not in self.database_names:
            raise ProviderError("database_identity_invalid")
        if not isinstance(identity["created_at"], str) or not identity["created_at"]:
            raise ProviderError("database_identity_invalid")
        known = self._databases.get(identity["uuid"])
        if known is not None and known != identity:
            raise ProviderError("database_identity_drift")
        return "/d1/database/" + identity["uuid"]

    def _request(self, method, path, body=None, *, key, media="application/json", raw=False):
        if not self._lock.acquire(blocking=False):
            raise ProviderError("provider_concurrent_call_forbidden")
        try:
            return self._request_locked(method, path, body, key=key, media=media, raw=raw)
        finally:
            self._lock.release()

    def _request_locked(self, method, path, body, *, key, media, raw):
        self.last_status = None
        data = body if isinstance(body, bytes) else None if body is None else _json(body)
        size = len(data or b"")
        remaining = self.limits.total_seconds - (self._clock() - self._started)
        response_allowance = min(
            self.limits.response_bytes, self.limits.total_response_bytes - self.response_bytes
        )
        if (
            self._closed
            or not isinstance(key, str)
            or not key
            or key in self._keys
            or self.calls >= self.limits.calls
            or size > self.limits.request_bytes
            or self.request_bytes + size > self.limits.total_request_bytes
            or remaining <= 0
            or response_allowance <= 0
        ):
            raise ProviderError("provider_budget_or_replay_refused")
        mutation = method != "GET"
        # Metadata never includes credentials, request SQL, response prose or bindings.
        meta = {"method": method, "path": path, "requestBytes": size}
        if self.before_request is not None:
            self.before_request(key, mutation, meta)
        # Durable hooks can block on FULL-sync storage. Their time consumes the
        # same finite lifetime; a pre-hook allowance cannot admit late mutation.
        admitted_at = self._clock()
        remaining = self.limits.total_seconds - (admitted_at - self._started)
        if remaining <= 0:
            self._closed = True
            raise ProviderError("provider_admission_deadline")
        self._keys.add(key)
        self.calls += 1
        self.request_bytes += size
        output = queue.Queue(maxsize=1)
        deadline = min(self.limits.request_seconds, remaining)
        admission_deadline = admitted_at + deadline

        def invoke():
            try:
                allowance = admission_deadline - self._clock()
                if allowance <= 0:
                    output.put((False, None))
                    return
                timeout = min(self.limits.socket_seconds, allowance)
                output.put(
                    (
                        True,
                        self._transport(
                            method,
                            "/client/v4/accounts/" + self.account + path,
                            data,
                            {
                                "Authorization": "Bearer " + self._token,
                                "Content-Type": media,
                                "Accept-Encoding": "identity",
                            },
                            timeout,
                            response_allowance,
                        ),
                    )
                )
            except Exception:
                output.put((False, None))

        thread = threading.Thread(target=invoke, daemon=True)
        thread.start()
        try:
            okay, result = output.get(timeout=deadline)
            if not okay or self._clock() - self._started >= self.limits.total_seconds:
                raise ProviderUnknown("provider_outcome_unknown")
            status, headers, payload = result
            self.last_status = status
            if (
                not isinstance(payload, bytes)
                or len(payload) > response_allowance
                or self.response_bytes + len(payload) > self.limits.total_response_bytes
            ):
                raise ProviderUnknown("provider_response_limit")
            self.response_bytes += len(payload)
            if not isinstance(status, int) or 300 <= status < 400:
                raise ProviderUnknown("provider_redirect_or_status_invalid")
            if raw and status == 200:
                value = (headers, payload)
            else:
                value = json.loads(payload)
                if not isinstance(value, dict):
                    raise ProviderUnknown("provider_response_invalid")
                if status != 404 and (not 200 <= status < 300 or value.get("success") is not True):
                    raise ProviderUnknown("provider_request_unsuccessful")
                value = None if status == 404 else value.get("result")
            if self.after_request is not None:
                self.after_request(key, {"status": status, "responseBytes": len(payload)})
            return value
        except Exception:
            self._closed = True
            raise ProviderUnknown("provider_outcome_unknown") from None

    def create_database(self, name, *, key):
        if name not in self.database_names or name in self._created_names:
            raise ProviderError("database_creation_refused")
        self._created_names.add(name)
        result = self._request("POST", "/d1/database", {"name": name}, key=key)
        if not isinstance(result, dict):
            self._unknown("database_create_identity_unknown")
        identity = {k: result.get(k) for k in ("uuid", "name", "created_at")}
        try:
            self._database(identity)
        except Exception:
            self._unknown("database_create_identity_unknown")
        if identity["name"] != name:
            self._unknown("database_create_identity_unknown")
        self._databases[identity["uuid"]] = identity.copy()
        return identity

    def inspect_database(self, identity, *, key):
        result = self._request("GET", self._database(identity), key=key)
        if result is None:
            return None
        if not isinstance(result, dict) or any(result.get(k) != v for k, v in identity.items()):
            raise ProviderError("database_identity_drift")
        return identity.copy()

    def migrate(self, identity, sql, sha2, *, key):
        if not isinstance(sql, bytes) or _digest(sql) != sha2:
            raise ProviderError("migration_digest_invalid")
        result = self._request(
            "POST",
            self._database(identity) + "/query",
            {"sql": sql.decode("utf-8"), "params": []},
            key=key,
        )
        if (
            not isinstance(result, list)
            or not result
            or any(not isinstance(r, dict) or r.get("success") is not True for r in result)
        ):
            self._unknown("migration_outcome_unknown")
        return {"sha2_256": sha2, "statements": len(result)}

    def upload_worker(self, name, module, sha2, metadata, access_token, *, key):
        raise ProviderError("atomic_create_only_worker_upload_unsupported")

    def _synthetic_upload_worker(self, name, module, sha2, metadata, access_token, *, key):
        # Cloudflare's documented PUT replaces existing scripts. No documented
        # atomic create-only condition was established; concrete transport must
        # not turn new-resource consent into an upsert authorization.
        if self._concrete:
            raise ProviderError("atomic_create_only_worker_upload_unsupported")
        path = self._worker(name)
        private = validate_worker_projection(module, sha2, metadata, access_token)
        db_id = next(b["id"] for b in metadata["bindings"] if b["name"] == "DB")
        if db_id not in self._databases:
            raise ProviderError("worker_database_not_created")
        boundary = "fga_publisher_" + sha2
        parts = []
        for filename, mime, data in (
            ("metadata", "application/json", _json(private)),
            ("worker.js", "application/javascript+module", module),
        ):
            parts.append(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{filename}"; '
                    f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
                ).encode()
                + data
                + b"\r\n"
            )
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        result = self._request(
            "PUT", path, body, key=key, media="multipart/form-data; boundary=" + boundary
        )
        if (
            not isinstance(result, dict)
            or result.get("id") != name
            or not isinstance(result.get("etag"), str)
        ):
            self._unknown("worker_upload_identity_unknown")
        return {"id": name, "etag": result["etag"], "moduleSha2_256": sha2}

    def inspect_worker(self, name, *, key):
        result = self._request("GET", self._worker(name) + "/settings", key=key)
        if result is None:
            return None
        if not isinstance(result, dict) or not isinstance(result.get("bindings"), list):
            raise ProviderError("worker_settings_invalid")
        result = dict(result)
        result["bindings"] = [
            {k: v for k, v in b.items() if k != "text"} if b.get("type") == "secret_text" else b
            for b in result["bindings"]
        ]
        return result

    def inspect_module(self, name, sha2, *, key):
        result = self._request("GET", self._worker(name), key=key, raw=True)
        if result is None:
            return None
        headers, payload = result
        media = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
        message = BytesParser(policy=policy.default).parsebytes(
            ("Content-Type: " + media + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + payload
        )
        if not message.is_multipart():
            raise ProviderError("worker_content_not_multipart")
        parts = list(message.iter_parts())
        modules = [
            p
            for p in parts
            if p.get_filename() == "worker.js"
            or p.get_param("name", header="Content-Disposition") == "worker.js"
        ]
        if (
            len(parts) != 1
            or len(modules) != 1
            or _digest(modules[0].get_payload(decode=True)) != sha2
        ):
            raise ProviderError("worker_module_drift")
        etag = next((v for k, v in headers.items() if k.lower() == "etag"), None)
        if not isinstance(etag, str) or not etag:
            raise ProviderError("worker_content_etag_missing")
        return {"moduleSha2_256": sha2, "etag": etag}

    def verify_empty_database(self, identity, *, key):
        result = self._request(
            "POST",
            self._database(identity) + "/query",
            {
                "sql": (
                    "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
                ),
                "params": [],
            },
            key=key,
        )
        if (
            not isinstance(result, list)
            or len(result) != 1
            or not isinstance(result[0], dict)
            or result[0].get("success") is not True
            or not isinstance(result[0].get("results"), list)
        ):
            raise ProviderError("database_empty_readback_invalid")
        rows = result[0]["results"]
        if any(
            not isinstance(r, dict) or set(r) != {"name"} or r["name"] != "_cf_KV" for r in rows
        ):
            raise ProviderError("database_not_empty")
        return True

    def set_endpoint(self, name, enabled, *, key):
        if not isinstance(enabled, bool):
            raise ProviderError("endpoint_enabled_invalid")
        result = self._request(
            "POST",
            self._worker(name) + "/subdomain",
            {"enabled": enabled, "previews_enabled": False},
            key=key,
        )
        if (
            not isinstance(result, dict)
            or result.get("enabled") is not enabled
            or result.get("previews_enabled") is not False
        ):
            self._unknown("endpoint_outcome_unknown")
        return {"enabled": enabled, "previews_enabled": False}

    def inspect_endpoint(self, name, *, key):
        result = self._request("GET", self._worker(name) + "/subdomain", key=key)
        if result is None:
            return None
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("enabled"), bool)
            or result.get("previews_enabled") is not False
        ):
            raise ProviderError("endpoint_readback_invalid")
        return {"enabled": result["enabled"], "previews_enabled": False}

    def delete_worker(self, name, expected_settings, *, key):
        current = self.inspect_worker(name, key=key + ":identity")
        if current is None:
            return {"absent": True}
        if current != expected_settings:
            raise ProviderError("worker_delete_identity_drift")
        self._request("DELETE", self._worker(name), key=key)
        return {"deletionAcknowledged": True, "absenceVerified": False}

    def delete_database(self, identity, *, key):
        current = self.inspect_database(identity, key=key + ":identity")
        if current is None:
            return {"absent": True}
        self._request("DELETE", self._database(identity), key=key)
        return {"deletionAcknowledged": True, "absenceVerified": False}
