"""Finite hosted publisher lifecycle. Importing performs no IO or credential lookup.

The caller supplies reviewed authority and explicit provider/client adapters. There
is no command line that silently turns a source packet into live permission.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class OperatorRefused(ValueError):
    """Sanitized failure category; provider exceptions must never be persisted."""


_OWNERS: set[str] = set()
_OWNERS_LOCK = threading.Lock()
_SECRET_KEYS = re.compile(r"token|secret|password|authorization|cookie|headers?|body", re.I)
_KEY = re.compile(r"[a-z0-9_.:-]{1,120}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
PROVIDER_REQUEST_BYTES = 16_777_216
PROVIDER_RESPONSE_BYTES = 33_554_432
PROVIDER_SINGLE_RESPONSE_BYTES = 2_097_152


def _encoded(value: Any) -> str:
    def safe(item: Any, depth: int = 0) -> None:
        if depth > 8:
            raise OperatorRefused("journal_metadata_depth")
        if isinstance(item, dict):
            if len(item) > 64:
                raise OperatorRefused("journal_metadata_width")
            for key, child in item.items():
                if type(key) is not str or _SECRET_KEYS.search(key):
                    raise OperatorRefused("journal_private_material_refused")
                safe(child, depth + 1)
        elif isinstance(item, (list, tuple)):
            if len(item) > 128:
                raise OperatorRefused("journal_metadata_width")
            for child in item:
                safe(child, depth + 1)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise OperatorRefused("journal_metadata_type")

    safe(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except ValueError, TypeError, RecursionError:
        raise OperatorRefused("journal_metadata_encoding") from None
    if len(raw.encode()) > 32768:
        raise OperatorRefused("journal_metadata_size")
    return raw


class DurableJournal:
    """FULL-synchronous SQLite intent ledger and lifetime exclusive owner latch.

    A reserved intent is never released or replayed, including after a crash. The
    lock only excludes concurrent owners; a later owner can observe and perform
    separately authorized cleanup, never resume provisioning or phase dispatch.
    Journal and latch live together in a caller-chosen private directory.
    """

    def __init__(self, path: str | Path, plan_digest: str):
        if not _HASH.fullmatch(plan_digest):
            raise OperatorRefused("invalid_plan_digest")
        self.path = Path(path).absolute()
        if (
            self.path.is_symlink()
            or self.path.with_suffix(self.path.suffix + ".owner").is_symlink()
        ):
            raise OperatorRefused("journal_link_refused")
        self._name = os.path.normcase(str(self.path.resolve()))
        self._mutex = threading.RLock()
        self._closed = True
        self._owner: Any = None
        self._db: sqlite3.Connection | None = None
        with _OWNERS_LOCK:
            if self._name in _OWNERS:
                raise OperatorRefused("journal_owner_busy")
            _OWNERS.add(self._name)
        try:
            self._owner = open(str(self.path) + ".owner", "a+b")
            self._owner.seek(0, 2)
            if self._owner.tell() == 0:
                self._owner.write(b"0")
                self._owner.flush()
                os.fsync(self._owner.fileno())
            self._owner.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._db = sqlite3.connect(self.path, timeout=0, check_same_thread=False)
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("PRAGMA journal_mode=DELETE")
            with self._db:
                self._db.execute("CREATE TABLE IF NOT EXISTS meta (digest TEXT NOT NULL)")
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS intents ("
                    "key TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL, "
                    "receipt TEXT NOT NULL)"
                )
                rows = self._db.execute("SELECT digest FROM meta").fetchall()
                if rows and rows != [(plan_digest,)]:
                    raise OperatorRefused("journal_plan_mismatch")
                if not rows:
                    self._db.execute("INSERT INTO meta VALUES (?)", (plan_digest,))
            self._bound_digest = plan_digest
            self._closed = False
        except BaseException:
            if self._db is not None:
                self._db.close()
            if self._owner is not None:
                self._owner.close()
            with _OWNERS_LOCK:
                _OWNERS.discard(self._name)
            raise

    @property
    def bound_digest(self) -> str:
        """Immutable constructor-verified plan identity of this open journal."""
        return self._bound_digest

    def _connection(self) -> sqlite3.Connection:
        if self._closed or self._db is None:
            raise OperatorRefused("journal_closed")
        return self._db

    def reserve(self, key: str, payload: dict[str, Any]) -> bool:
        if type(key) is not str or not _KEY.fullmatch(key):
            raise OperatorRefused("journal_invalid_key")
        raw = _encoded(payload)
        with self._mutex:
            connection = self._connection()
            with connection:
                if connection.execute("SELECT 1 FROM intents WHERE key=?", (key,)).fetchone():
                    return False
                if connection.execute("SELECT count(*) FROM intents").fetchone()[0] >= 2048:
                    raise OperatorRefused("journal_intent_bound")
                connection.execute("INSERT INTO intents VALUES (?, 'intent', ?, '{}')", (key, raw))
        return True

    def _finish(self, key: str, state: str, receipt: dict[str, Any]) -> None:
        raw = _encoded(receipt)
        with self._mutex:
            connection = self._connection()
            with connection:
                changed = connection.execute(
                    "UPDATE intents SET state=?, receipt=? WHERE key=? AND state='intent'",
                    (state, raw, key),
                ).rowcount
                if changed != 1:
                    raise OperatorRefused("journal_terminal_or_missing")

    def complete(self, key: str, receipt: dict[str, Any]) -> None:
        self._finish(key, "complete", receipt)

    def unknown(self, key: str, reason: str) -> None:
        if not _KEY.fullmatch(reason):
            raise OperatorRefused("journal_invalid_reason")
        self._finish(key, "unknown", {"reason": reason})

    def snapshot(self) -> dict[str, Any]:
        with self._mutex:
            connection = self._connection()
            rows = connection.execute(
                "SELECT key,state,payload,receipt FROM intents ORDER BY rowid"
            ).fetchall()
            return {
                key: {
                    "state": state,
                    "payload": json.loads(payload),
                    "receipt": json.loads(receipt),
                }
                for key, state, payload, receipt in rows
            }

    def close(self) -> None:
        with self._mutex:
            if self._closed:
                return
            assert self._db is not None
            self._db.close()
            self._owner.close()
            self._closed = True
            with _OWNERS_LOCK:
                _OWNERS.discard(self._name)

    def __enter__(self) -> DurableJournal:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class CaseJournal:
    """Namespace a finite client's keys without relaxing once-only semantics."""

    def __init__(self, journal: DurableJournal, scenario: str):
        self.journal = journal
        self.prefix = "client:" + scenario + ":"

    def reserve(self, key: str, payload: dict[str, Any]) -> bool:
        return self.journal.reserve(self.prefix + key, payload)

    def complete(self, key: str, receipt: dict[str, Any]) -> None:
        self.journal.complete(self.prefix + key, receipt)

    def unknown(self, key: str, reason: str) -> None:
        self.journal.unknown(self.prefix + key, reason)


class HostedPublisherOperator:
    """One invocation, four exact fresh pairs, no phase or lifecycle replay.

    Synthetic fixture disposal preserves unproved SQL outcomes. Cleanup is a
    separate exact authority boundary below. An
    expired operation grant never silently extends to stop/provider mutations.
    """

    def __init__(
        self,
        plan: Any,
        consent: dict[str, Any],
        provider: Any,
        client_transport: Callable[..., Any],
        journal: DurableJournal,
        private_inputs: Any,
        source_root: Path,
        bundle_path: Path,
        current_root: Path,
        *,
        operator_grant: dict[str, Any] | None = None,
        wall_clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
        stop_check: Callable[[], bool] = lambda: False,
    ):
        if journal.bound_digest != plan.digest:
            raise OperatorRefused("journal_plan_mismatch")
        self.plan, self.consent, self.provider = plan, consent, provider
        self._plan_digest = plan.digest
        self.operator_grant = operator_grant if type(operator_grant) is dict else {}
        if (
            getattr(provider, "account", None) != plan.account_id
            or set(getattr(provider, "worker_names", ())) != {c.worker_name for c in plan.cases}
            or set(getattr(provider, "database_names", ())) != {c.d1_name for c in plan.cases}
        ):
            raise OperatorRefused("provider_identity_scope_mismatch")
        self.client_transport, self.journal, self.private_inputs = (
            client_transport,
            journal,
            private_inputs,
        )
        self.source_root, self.bundle_path, self.current_root = (
            source_root,
            bundle_path,
            current_root,
        )
        self.wall_clock, self.monotonic, self.stop_check = wall_clock, monotonic, stop_check
        self._started = monotonic()
        self._stopped = False
        self._calls = self._mutations = self._sql_calls = self._sql_statements = 0
        self._request_bytes = self._response_bytes = 0
        self._ledger: dict[str, dict[str, Any]] = {}
        self._active_request: str | None = None
        self._execution_lock = threading.Lock()
        for key, event in journal.snapshot().items():
            if key.startswith("provider:"):
                self._calls += 1
                self._mutations += int(event["payload"].get("mutation") is True)
                self._request_bytes += event["payload"]["requestBytes"]
                self._response_bytes += (
                    event["receipt"]["responseBytes"]
                    if event["state"] == "complete"
                    else event["payload"]["reservedResponseBytes"]
                )
            elif key.startswith("sql:"):
                self._sql_calls += event["payload"]["calls"]
                self._sql_statements += event["payload"]["statements"]
        # Every actual request, including reads hidden inside deletion primitives,
        # passes the same durable and cumulative boundary.
        if provider.before_request is not None or provider.after_request is not None:
            raise OperatorRefused("provider_hooks_already_owned")
        provider.before_request, provider.after_request = self._before_request, self._after_request

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self.wall_clock(), UTC)

    def _assert_binding(self) -> None:
        if self.plan.digest != self._plan_digest:
            raise OperatorRefused("plan_changed_after_binding")
        if self.journal.bound_digest != self._plan_digest:
            raise OperatorRefused("journal_plan_mismatch")

    def _window(self, *, cleanup: bool = False) -> None:
        from scripts.hosted_publisher_operator_plan import utc_time

        self._assert_binding()
        end = self.plan.cleanup_deadline if cleanup else self.plan.expires_at
        if not utc_time(self.plan.starts_at) <= self._now() < utc_time(end):
            raise OperatorRefused("authority_window_closed")
        if self.monotonic() - self._started >= self.plan.budgets.lifecycle_seconds:
            raise OperatorRefused("lifecycle_deadline")

    def _fence(self) -> None:
        self._window()
        if self._stopped or self.stop_check():
            self._stopped = True
            raise OperatorRefused("dispatch_stopped")

    def _case_window(self, now: datetime | None = None) -> datetime:
        from scripts.hosted_publisher_operator_plan import utc_time

        observed = self._now() if now is None else now
        if getattr(self, "_cleanup_mode", False) or getattr(self, "_stopping", False):
            return observed
        case = getattr(self, "_request_case", None)
        if case is None or case not in self.plan.cases:
            raise OperatorRefused("provider_case_scope_required")
        if not utc_time(case.starts_at) <= observed < utc_time(case.expires_at):
            raise OperatorRefused("case_window_closed")
        return observed

    def _before_request(self, key: str, mutation: bool, metadata: dict[str, Any]) -> None:
        from scripts.hosted_publisher_operator_plan import validate_operator_grant

        self._window(cleanup=getattr(self, "_cleanup_mode", False))
        validate_operator_grant(self.plan, self.operator_grant, self._now())
        if mutation:
            self._case_window()
        if getattr(self, "_cleanup_mode", False):
            if self._now() >= self._cleanup_expires_at:
                raise OperatorRefused("cleanup_authority_expired")
        elif not getattr(self, "_stopping", False) and (self._stopped or self.stop_check()):
            self._stopped = True
            raise OperatorRefused("dispatch_stopped")
        if (
            type(metadata) is not dict
            or set(metadata) != {"method", "path", "requestBytes"}
            or metadata["method"] not in {"GET", "POST", "PUT", "PATCH", "DELETE"}
            or type(metadata["path"]) is not str
            or not re.fullmatch(
                r"/(?:d1/database|workers/scripts|workers/workers|workers/subdomain)"
                r"(?:/[a-zA-Z0-9_/-]{1,160})?(?:\?(?:include=modules|deploy=false|page=1&per_page=1))?",
                metadata["path"],
            )
            or type(metadata["requestBytes"]) is not int
            or not 0 <= metadata["requestBytes"] <= 2_097_152
        ):
            raise OperatorRefused("provider_request_metadata_invalid")
        if self._calls >= self.plan.budgets.provider_calls:
            raise OperatorRefused("provider_call_budget")
        if mutation and self._mutations >= self.plan.budgets.provider_mutations:
            raise OperatorRefused("provider_mutation_budget")
        if (
            self._request_bytes + metadata["requestBytes"] > PROVIDER_REQUEST_BYTES
            or self._response_bytes + PROVIDER_SINGLE_RESPONSE_BYTES > PROVIDER_RESPONSE_BYTES
        ):
            raise OperatorRefused("provider_cumulative_byte_budget")
        if not self.journal.reserve(
            "provider:" + key,
            {
                **metadata,
                "mutation": mutation,
                "reservedResponseBytes": PROVIDER_SINGLE_RESPONSE_BYTES,
            },
        ):
            raise OperatorRefused("provider_request_already_reserved")
        self._calls += 1
        self._mutations += int(mutation)
        self._request_bytes += metadata["requestBytes"]
        self._response_bytes += PROVIDER_SINGLE_RESPONSE_BYTES
        self._active_request = "provider:" + key
        self._window(cleanup=getattr(self, "_cleanup_mode", False))
        validate_operator_grant(self.plan, self.operator_grant, self._now())
        if getattr(self, "_cleanup_mode", False) and self._now() >= self._cleanup_expires_at:
            raise OperatorRefused("cleanup_authority_expired")
        # FULL-sync reservation may cross a narrower case deadline. Check again
        # immediately before returning admission to the provider transport.
        if mutation:
            admitted = self._case_window()
            timing = getattr(self, "_create_timing", None)
            if timing is not None:
                timing["request_started"] = admitted

    def _after_request(self, key: str, receipt: dict[str, Any]) -> None:
        # Observe once before validation or durable receipt persistence can
        # consume time. Provider field validation may raise after this callback.
        timing = getattr(self, "_create_timing", None)
        if timing is not None:
            timing["response_received"] = self._now()
        if (
            type(receipt) is not dict
            or set(receipt) != {"status", "responseBytes"}
            or type(receipt["status"]) is not int
            or not 100 <= receipt["status"] <= 599
            or type(receipt["responseBytes"]) is not int
            or not 0 <= receipt["responseBytes"] <= 2_097_152
        ):
            raise OperatorRefused("provider_response_metadata_invalid")
        self.journal.complete("provider:" + key, receipt)
        self._response_bytes += receipt["responseBytes"] - PROVIDER_SINGLE_RESPONSE_BYTES
        self._active_request = None

    def _call(self, method: Callable[..., Any], *args: Any, key: str, **kwargs: Any) -> Any:
        # Method-level intent retains parsed identity even if request succeeded but
        # the provider response failed local validation after its request receipt.
        if method.__name__ == "deploy_version":
            # A previous operation's diagnostic must never be attributed here.
            self.provider.last_deployment_diagnostic = None
            self.provider.last_deployment_response_shape = None
        if not self.journal.reserve("operation:" + key, {"operation": key}):
            raise OperatorRefused("operator_operation_already_reserved")
        request_started = response_received = None
        previous_case = getattr(self, "_request_case", None)
        previous_timing = getattr(self, "_create_timing", None)
        self._request_case = next(
            (case for case in self.plan.cases if case.scenario == key.split(":", 1)[0]), None
        )
        if method.__name__ in {"create_database", "create_worker"}:
            field = "d1_name" if method.__name__ == "create_database" else "worker_name"
            self._request_case = next(
                (case for case in self.plan.cases if getattr(case, field) == args[0]), None
            )
        self._create_timing = {} if method.__name__ == "create_database" else None
        try:
            request_started = self._now()
            if method.__name__ in {"create_database", "create_worker"}:
                self._case_window(request_started)
            result = method(*args, key=key, **kwargs)
            if self._create_timing is not None:
                request_started = self._create_timing.get("request_started", request_started)
                response_received = self._create_timing.get("response_received")
            if response_received is None:
                response_received = self._now()
            # Provider readbacks are untrusted until compared. A drifted binding
            # may contain a credential under an innocuous `text` key. Persist no
            # arbitrary response/projection, even on the rejecting path.
            receipt: dict[str, Any] = {"present": result is not None}
            if method.__name__ == "create_database":
                from scripts.hosted_publisher_operator_plan import database_time, utc_time

                if (
                    type(result) is not dict
                    or set(result) != {"uuid", "name", "created_at"}
                    or result["name"] not in {c.d1_name for c in self.plan.cases}
                    or type(result["uuid"]) is not str
                    or not re.fullmatch(
                        r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", result["uuid"]
                    )
                    or result["uuid"] == "00000000-0000-0000-0000-000000000000"
                ):
                    raise OperatorRefused("create_receipt_identity_unknown")
                case = next(c for c in self.plan.cases if c.d1_name == result["name"])
                if not utc_time(case.starts_at) <= request_started <= response_received < utc_time(
                    case.expires_at
                ) or (
                    result["created_at"] is not None
                    and not database_time(self.plan.starts_at)
                    <= database_time(result["created_at"])
                    < database_time(case.expires_at)
                ):
                    raise OperatorRefused("database_creation_time_unknown")
                receipt = {
                    "result": result,
                    "requestStartedAt": request_started.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "responseReceivedAt": response_received.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                }
            elif method.__name__ == "create_worker":
                from scripts.hosted_publisher_operator_plan import utc_time

                if (
                    type(result) is not dict
                    or set(result) != {"id", "name", "created_on"}
                    or result["name"] not in {c.worker_name for c in self.plan.cases}
                    or not isinstance(result["id"], str)
                    or not re.fullmatch(r"[a-f0-9]{32}", result["id"])
                    or result["id"] == "0" * 32
                    or not isinstance(result["created_on"], str)
                ):
                    raise OperatorRefused("worker_create_identity_unknown")
                created = datetime.fromisoformat(result["created_on"])
                case = next(c for c in self.plan.cases if c.worker_name == result["name"])
                if not utc_time(self.plan.starts_at) <= created < utc_time(case.expires_at):
                    raise OperatorRefused("worker_creation_time_unknown")
                receipt = {"result": result}
            elif method.__name__ in {"create_version", "deploy_version"}:
                fields = (
                    {"id", "workerId", "moduleSha2_256"}
                    if method.__name__ == "create_version"
                    else {"id", "workerId", "versionId", "created_on"}
                )
                if type(result) is not dict or set(result) != fields:
                    raise OperatorRefused("deployment_receipt_unknown")
                if result["workerId"] != args[0]["id"]:
                    raise OperatorRefused("deployment_worker_identity_drift")
                for field in fields - {"moduleSha2_256", "created_on"}:
                    if not isinstance(result[field], str) or not re.fullmatch(
                        r"[a-f0-9-]{32,36}", result[field]
                    ):
                        raise OperatorRefused("deployment_identity_unknown")
                if method.__name__ == "create_version":
                    if result["moduleSha2_256"] != self.plan.pins["worker"]:
                        raise OperatorRefused("version_module_drift")
                elif result["versionId"] != args[1]["id"]:
                    raise OperatorRefused("deployment_version_drift")
                receipt = {"result": result}
            elif method.__name__ in {"delete_worker", "delete_database"}:
                if type(result) is not dict or result.get("deletionAcknowledged") is not True:
                    raise OperatorRefused("deletion_acknowledgement_unknown")
                receipt = {"result": {"deletionAcknowledged": True}}
            self.journal.complete("operation:" + key, receipt)
            return result
        except Exception:
            if self._active_request is not None:
                self.journal.unknown(self._active_request, "provider_outcome_unknown")
                self._active_request = None
            if self._create_timing is not None:
                request_started = self._create_timing.get("request_started", request_started)
                response_received = self._create_timing.get("response_received", response_received)
            diagnostic = getattr(self.provider, "last_database_create", None)
            if (
                method.__name__ == "create_database"
                and request_started is not None
                and response_received is not None
                and type(diagnostic) is dict
                and set(diagnostic)
                in (
                    {"uuid", "name", "providerTimeStatus"},
                    {"uuid", "name", "providerTimeStatus", "created_at"},
                )
                and diagnostic.get("name") == args[0]
                and diagnostic.get("name") in {c.d1_name for c in self.plan.cases}
                and type(diagnostic.get("uuid")) is str
                and re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", diagnostic["uuid"])
                and diagnostic["uuid"] != "00000000-0000-0000-0000-000000000000"
                and diagnostic.get("providerTimeStatus") in {"omitted", "valid", "invalid"}
                and (("created_at" in diagnostic) == (diagnostic["providerTimeStatus"] == "valid"))
            ):
                from scripts.hosted_publisher_operator_plan import database_time

                retained = dict(diagnostic)
                if "created_at" in retained:
                    database_time(retained["created_at"])
                # This is an unknown operation with an acknowledged identity,
                # never a successful receipt, qualification or cleanup adoption.
                self.journal._finish(
                    "operation:" + key,
                    "unknown",
                    {
                        "reason": "operation_outcome_unknown",
                        "acknowledgedCreate": retained,
                        "requestStartedAt": request_started.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "responseReceivedAt": response_received.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    },
                )
            elif method.__name__ == "deploy_version":
                from scripts.hosted_publisher_worker_deployment import (
                    deployment_diagnostic,
                    deployment_response_shape,
                )

                closed = deployment_diagnostic(
                    getattr(self.provider, "last_deployment_diagnostic", None)
                )
                observed = None
                if closed is not None:
                    try:
                        # Optional diagnostic time must not prevent unknown settlement.
                        observed = self._now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    except Exception:
                        closed = None
                if closed is None:
                    self.journal.unknown("operation:" + key, "operation_outcome_unknown")
                else:
                    # Observation time is local, never the untrusted provider timestamp.
                    receipt = {
                        "reason": "operation_outcome_unknown",
                        "deploymentDiagnostic": closed,
                        "diagnosticObservedAt": observed,
                    }
                    if closed["stage"] == "response_validation" and closed["status"] in {
                        "missing",
                        "invalid",
                    }:
                        shape = deployment_response_shape(
                            getattr(self.provider, "last_deployment_response_shape", None)
                        )
                        if shape is not None:
                            receipt["deploymentResponseShape"] = shape
                    self.journal._finish(
                        "operation:" + key,
                        "unknown",
                        receipt,
                    )
            else:
                self.journal.unknown("operation:" + key, "operation_outcome_unknown")
            raise OperatorRefused("operation_outcome_unknown") from None
        finally:
            self._request_case = previous_case
            self._create_timing = previous_timing

    def _check_deployment(self, case: Any, entry: dict[str, Any], prefix: str) -> None:
        version = self._call(
            self.provider.inspect_version,
            entry["worker"],
            entry["version"],
            key=prefix + ":version",
        )
        if version != entry["version"]:
            raise OperatorRefused("version_readback_drift")
        deployment = self._call(
            self.provider.inspect_deployment,
            entry["worker"],
            entry["version"],
            entry["deployment"],
            key=prefix + ":deployment",
        )
        if deployment != entry["deployment"]:
            raise OperatorRefused("deployment_readback_drift")
        endpoint = self._call(
            self.provider.assert_endpoint,
            entry["worker"],
            case.endpoint,
            key=prefix + ":origin",
        )
        if endpoint is not True:
            raise OperatorRefused("endpoint_origin_drift")

    def run(self) -> dict[str, Any]:
        self._assert_binding()
        if not self._execution_lock.acquire(blocking=False):
            raise OperatorRefused("operator_concurrent_execution")
        try:
            if "operator:cleanup-entered" in self.journal.snapshot():
                raise OperatorRefused("cleanup_terminal_dispatch_barrier")
            return self._run()
        finally:
            self._execution_lock.release()

    def _client_stopped(self) -> bool:
        from scripts.hosted_publisher_operator_plan import validate_operator_grant

        try:
            self._fence()
            validate_operator_grant(self.plan, self.operator_grant, self._now())
        except Exception:
            self._stopped = True
            return True
        return False

    def _transport(self, request: Any) -> Any:
        if self._client_stopped():
            raise OperatorRefused("client_dispatch_stopped")
        remaining = min(request.timeout, self.plan.budgets.phase_seconds)
        deadline = min(request.deadline, self.monotonic() + remaining)
        response = self.client_transport(replace(request, timeout=remaining, deadline=deadline))
        if self.monotonic() >= deadline:
            raise OperatorRefused("client_phase_deadline_unknown")
        return response

    def _run(self) -> dict[str, Any]:
        from scripts.hosted_publisher_finite_client import (
            ClientIdentity,
            FiniteClient,
            SharedBudget,
        )
        from scripts.hosted_publisher_operator_plan import (
            CreationReceipt,
            bind_resources,
            deployment_projection,
            utc_time,
            validate_artifact,
            validate_consent,
            validate_current_inputs,
            validate_operator_grant,
        )

        validate_consent(self.plan, self.consent, self._now())
        validate_operator_grant(self.plan, self.operator_grant, self._now())
        validate_current_inputs(self.plan, self.current_root)
        validate_artifact(self.source_root, self.bundle_path)
        if getattr(self.provider, "selected_strategy", None) != "beta-synthetic-disposal-v1":
            raise OperatorRefused("selected_beta_provider_required")
        if not self.journal.reserve("operator:run", {"planDigest": self.plan.digest}):
            raise OperatorRefused("operator_run_already_reserved")
        result: dict[str, Any] = {
            "status": "pending",
            "cases": [],
            "cleanup": "not_attempted",
            "revocation": "external_owner_required",
            "querySettlement": "unproved",
        }
        try:
            bundle = self.bundle_path.read_bytes()
            manifest_raw = (self.source_root / "manifest.json").read_bytes()
            if hashlib.sha256(manifest_raw).hexdigest() != self.plan.pins["manifest"]:
                raise OperatorRefused("manifest_changed_after_validation")
            manifest = json.loads(manifest_raw)
            migration_records = {r["path"]: r for r in manifest["files"]}
            migrations = sorted(
                r["path"] for r in manifest["files"] if r["path"].startswith("migrations/")
            )
            if len(migrations) != 26:
                raise OperatorRefused("migration_closure_changed")
            receipts = []
            for case in self.plan.cases:
                self._fence()
                key = case.scenario
                identity = self._call(
                    self.provider.create_database, case.d1_name, key=key + ":create"
                )
                create_receipt = self.journal.snapshot()["operation:" + key + ":create"]["receipt"]
                entry = {
                    "database": identity,
                    "worker": None,
                    "uploaded": False,
                    "scenario": case.scenario,
                    "d1Submitted": False,
                }
                self._ledger[key] = entry
                if (
                    self._call(self.provider.inspect_database, identity, key=key + ":database")
                    != identity
                ):
                    raise OperatorRefused("database_identity_drift")
                self._charge_sql(key + ":empty", 1, 1)
                empty = self._call(
                    self.provider.verify_empty_database, identity, key=key + ":empty"
                )
                if empty is not True:
                    raise OperatorRefused("database_not_empty")
                entry["worker"] = self._call(
                    self.provider.create_worker, case.worker_name, key=key + ":worker-create"
                )
                receipts.append(
                    CreationReceipt(
                        case.scenario,
                        case.worker_name,
                        case.d1_name,
                        identity["uuid"],
                        identity["created_at"],
                        True,
                        self.plan.digest,
                        create_receipt["requestStartedAt"],
                        create_receipt["responseReceivedAt"],
                    )
                )
            bound = bind_resources(self.plan, receipts)
            budget = SharedBudget(
                self.plan.budgets.client_requests,
                262144,
                8_388_608,
                self._started + self.plan.budgets.lifecycle_seconds,
            )
            for bound_case in bound:
                case = bound_case.case
                key = case.scenario
                entry = self._ledger[key]
                self._fence()
                if not utc_time(case.starts_at) <= self._now() < utc_time(case.expires_at):
                    raise OperatorRefused("case_window_closed")
                for index, name in enumerate(migrations, 1):
                    self._fence()
                    sql = (self.source_root / name).read_bytes()
                    if (
                        hashlib.sha256(sql).hexdigest() != migration_records[name]["sha2_256"]
                        or len(sql) != migration_records[name]["bytes"]
                    ):
                        raise OperatorRefused("migration_changed_after_validation")
                    # Charge before submission; outcome may remain unknown forever.
                    statement_bound = sql.count(b";") + 1
                    self._charge_sql(f"{key}:migration-{index:02}", 1, statement_bound)
                    entry["d1Submitted"] = True
                    receipt = self._call(
                        self.provider.migrate,
                        entry["database"],
                        sql,
                        hashlib.sha256(sql).hexdigest(),
                        key=f"{key}:migration-{index:02}",
                    )
                    if type(receipt["statements"]) is not int or not (
                        0 < receipt["statements"] <= statement_bound
                    ):
                        raise OperatorRefused("migration_statement_bound_unknown")
                projection = deployment_projection(self.plan, case, entry["database"]["uuid"])
                entry["projection"] = projection
                entry["version"] = self._call(
                    self.provider.create_version,
                    entry["worker"],
                    bundle,
                    self.plan.pins["worker"],
                    projection,
                    self.private_inputs.token(key),
                    key=key + ":version",
                )
                entry["deployment"] = self._call(
                    self.provider.deploy_version,
                    entry["worker"],
                    entry["version"],
                    key=key + ":deploy",
                )
                entry["uploaded"] = True
                self._check_deployment(case, entry, key + ":deployed")
                self.journal.reserve("binding:" + key, {"databaseUuid": entry["database"]["uuid"]})
                self.journal.complete("binding:" + key, {"verified": True})
                self._fence()
                self._call(self.provider.enable_worker, entry["worker"], key=key + ":enable")
                if self._call(
                    self.provider.inspect_endpoint, entry["worker"], key=key + ":enabled"
                ) != {"enabled": True, "previews_enabled": False}:
                    raise OperatorRefused("endpoint_enable_drift")
                identity = ClientIdentity(
                    case.endpoint,
                    self.plan.pins["source_artifact"],
                    case.run_id,
                    entry["database"]["uuid"],
                    key,
                    utc_time(case.expires_at).timestamp(),
                )
                client = FiniteClient(
                    identity,
                    self._transport,
                    budget,
                    CaseJournal(self.journal, key),
                    lambda scenario=key: self.private_inputs.token(scenario),
                    self.monotonic,
                    self.wall_clock,
                    self._client_stopped,
                )
                # Per-phase SQL guard is 256 calls, batch width128; eight further
                # control operations conservatively include reservation/sealing.
                # This is submitted-operation/statement capacity, not rows written.
                self._charge_sql(key + ":phases", 7 * 264, 7 * (256 * 128 + 8))
                receipt = client.run()
                result["cases"].append(receipt)
                if receipt["status"] != "complete":
                    raise OperatorRefused("client_outcome_unknown")
                self._stop_case(case, entry)
            result["status"] = "phases_complete_cleanup_pending"
            self.journal.complete("operator:run", {"status": result["status"]})
        except Exception:
            self._stopped = True
            self.journal.unknown("operator:run", "lifecycle_outcome_unknown")
            result["status"] = "unknown"
        finally:
            # Stop each definitely uploaded identity. Unknown upload/create remains
            # explicitly unresolved; no same-name mutation guesses its identity.
            for case in self.plan.cases:
                entry = self._ledger.get(case.scenario)
                if entry and entry["worker"] and not entry.get("accessDisabled"):
                    try:
                        self._stop_case(case, entry)
                    except Exception:
                        entry["accessDisabled"] = False
            self.private_inputs.revoke_local()
        result["resources"] = self._ledger
        result["providerCalls"] = self._calls
        result["providerMutations"] = self._mutations
        result["providerRequestBytes"] = self._request_bytes
        result["providerResponseByteCapacity"] = self._response_bytes
        result["sqlCapacityCalls"] = self._sql_calls
        result["sqlCapacityStatements"] = self._sql_statements
        result["unresolvedIntents"] = [
            key
            for key, event in self.journal.snapshot().items()
            if event["state"] in {"intent", "unknown"}
        ]
        result["cleanupOwner"] = self.plan.cleanup_owner
        return result

    def _charge_sql(self, key: str, calls: int, statements: int) -> None:
        if (
            self._sql_calls + calls > self.plan.budgets.sql_calls
            or self._sql_statements + statements > self.plan.budgets.sql_statements
        ):
            raise OperatorRefused("sql_capacity_budget")
        if not self.journal.reserve("sql:" + key, {"calls": calls, "statements": statements}):
            raise OperatorRefused("sql_capacity_already_reserved")
        self._sql_calls += calls
        self._sql_statements += statements
        self.journal.complete("sql:" + key, {"reserved": True})

    def _stop_case(self, case: Any, entry: dict[str, Any]) -> None:
        key = case.scenario
        self._window()
        self._stopping = True
        try:
            self._call(self.provider.disable_worker, entry["worker"], key=key + ":disable")
            observed = self._call(
                self.provider.inspect_endpoint, entry["worker"], key=key + ":disabled"
            )
        finally:
            self._stopping = False
        entry["accessDisabled"] = observed == {"enabled": False, "previews_enabled": False}
        # Endpoint disable readback neither cancels an executing phase nor proves
        # provider/D1 drain. The accepted disposal rule preserves that uncertainty.
        entry["querySettlement"] = "unproved"
        if not entry["accessDisabled"]:
            raise OperatorRefused("access_stop_unknown")

    def cleanup_only(self, authority: dict[str, Any]) -> dict[str, Any]:
        self._assert_binding()
        if not self._execution_lock.acquire(blocking=False):
            raise OperatorRefused("operator_concurrent_execution")
        try:
            return self._cleanup_once(authority)
        finally:
            self._cleanup_mode = False
            self._execution_lock.release()

    def _cleanup_once(self, authority: dict[str, Any]) -> dict[str, Any]:
        """Dispose exact synthetic fixtures without claiming SQL settlement.

        Ownership comes only from durable acknowledged creation. Dispatch remains
        fenced forever. Delete intents are global across cleanup attempts, so a
        lost deletion is never retried under a newly named authority.
        """
        from scripts.hosted_publisher_operator_plan import (
            deployment_projection,
            utc_time,
            validate_consent,
            validate_current_inputs,
            validate_operator_grant,
        )

        expected = {
            "schema_version",
            "granted",
            "plan_digest",
            "owner",
            "decision_id",
            "expires_at",
            "actions",
        }
        if (
            set(authority) != expected
            or type(authority["schema_version"]) is not int
            or authority["schema_version"] != 1
            or authority["granted"] is not True
            or authority["plan_digest"] != self.plan.digest
            or authority["owner"] != self.plan.cleanup_owner
            or authority["actions"]
            != [
                "fence_dispatch",
                "disable_access",
                "delete_owned_worker",
                "dispose_exact_synthetic_d1",
            ]
            or not isinstance(authority["decision_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", authority["decision_id"])
            or not self._now()
            < utc_time(authority["expires_at"])
            <= utc_time(self.plan.cleanup_deadline)
        ):
            raise OperatorRefused("separate_cleanup_authority_required")
        self._window(cleanup=True)
        # Revalidate the original exact synthetic/exclusive-writer scope without
        # treating its elapsed dispatch window as a new cleanup grant.
        validate_consent(self.plan, self.consent, utc_time(self.plan.starts_at))
        validate_current_inputs(self.plan, self.current_root)
        validate_operator_grant(self.plan, self.operator_grant, self._now())
        self._stopped = True
        if self.journal.reserve("operator:cleanup-entered", {"planDigest": self.plan.digest}):
            self.journal.complete("operator:cleanup-entered", {"dispatchStopped": True})
        attempt = "cleanup:" + hashlib.sha256(authority["decision_id"].encode()).hexdigest()[:16]
        if not self.journal.reserve(attempt, {"planDigest": self.plan.digest}):
            raise OperatorRefused("cleanup_attempt_already_reserved")
        self._cleanup_mode = True
        self._cleanup_expires_at = utc_time(authority["expires_at"])
        results = []
        snapshot = self.journal.snapshot()
        for case in self.plan.cases:
            key = case.scenario
            create = snapshot.get("operation:" + key + ":create")
            worker_create = snapshot.get("operation:" + key + ":worker-create")
            version = snapshot.get("operation:" + key + ":version")
            deployment = snapshot.get("operation:" + key + ":deploy")
            binding = snapshot.get("binding:" + key)
            if not create or create["state"] != "complete":
                results.append({"scenario": key, "status": "identity_unknown"})
                continue
            if not worker_create or worker_create["state"] != "complete":
                results.append({"scenario": key, "status": "worker_identity_unknown"})
                continue
            identity = create["receipt"]["result"]
            worker = worker_create["receipt"]["result"]
            prefix = attempt + ":" + key
            entry = {
                "database": identity,
                "worker": worker,
                "projection": deployment_projection(self.plan, case, identity["uuid"]),
            }
            verified_binding = (
                binding is not None
                and binding["state"] == "complete"
                and binding["payload"] == {"databaseUuid": identity["uuid"]}
                and binding["receipt"] == {"verified": True}
                and version is not None
                and version["state"] == "complete"
                and deployment is not None
                and deployment["state"] == "complete"
            )
            if verified_binding:
                assert version is not None and deployment is not None
                entry["version"] = version["receipt"]["result"]
                entry["deployment"] = deployment["receipt"]["result"]
            try:
                self.provider.restore_owned_resources(
                    identity,
                    worker,
                    version=entry.get("version"),
                    projection=entry["projection"],
                    deployment=entry.get("deployment"),
                )
                prior_worker_delete = snapshot.get("operation:dispose:" + key + ":worker")
                prior_db_delete = snapshot.get("operation:dispose:" + key + ":database")
                # Unknown deletion is residual even if a later observation sees
                # absence. A separate reviewed observation may report that fact,
                # but cannot silently convert its acknowledgement or replay it.
                if prior_worker_delete and prior_worker_delete["state"] != "complete":
                    results.append({"scenario": key, "status": "worker_deletion_unknown"})
                    continue
                if not prior_worker_delete:
                    if verified_binding:
                        self._check_deployment(case, entry, prefix)
                    self._call(self.provider.disable_worker, worker, key=prefix + ":disable")
                    disabled = self._call(
                        self.provider.inspect_endpoint, worker, key=prefix + ":disabled"
                    )
                    if disabled != {"enabled": False, "previews_enabled": False}:
                        raise OperatorRefused("cleanup_access_unknown")
                    deletion = self._call(
                        self.provider.delete_worker, worker, key="dispose:" + key + ":worker"
                    )
                    if (
                        not isinstance(deletion, dict)
                        or deletion.get("deletionAcknowledged") is not True
                    ):
                        raise OperatorRefused("worker_deletion_not_acknowledged")
                if (
                    self._call(self.provider.inspect_worker, worker, key=prefix + ":worker-absence")
                    is not None
                ):
                    raise OperatorRefused("worker_absence_unknown")
                if not verified_binding:
                    results.append({"scenario": key, "status": "worker_removed_binding_unverified"})
                    continue
                if prior_db_delete and prior_db_delete["state"] != "complete":
                    results.append({"scenario": key, "status": "database_deletion_unknown"})
                    continue
                if not prior_db_delete:
                    deletion = self._call(
                        self.provider.delete_database, identity, key="dispose:" + key + ":database"
                    )
                    if (
                        not isinstance(deletion, dict)
                        or deletion.get("deletionAcknowledged") is not True
                    ):
                        raise OperatorRefused("database_deletion_not_acknowledged")
                if (
                    self._call(
                        self.provider.inspect_database, identity, key=prefix + ":database-absence"
                    )
                    is not None
                ):
                    raise OperatorRefused("database_absence_unknown")
                results.append({"scenario": key, "status": "absent", "querySettlement": "unproved"})
            except Exception:
                results.append({"scenario": key, "status": "cleanup_unknown"})
                break
        self.journal.complete(attempt, {"results": results})
        unknown = any(
            event["state"] in {"intent", "unknown"}
            for key, event in self.journal.snapshot().items()
            if key != attempt
        )
        disposed = len(results) == 4 and all(item["status"] == "absent" for item in results)
        return {
            "status": ("disposed_with_unknown_outcomes" if unknown else "resources_disposed")
            if disposed
            else "pending",
            "cases": results,
            "querySettlement": "unproved",
            "qualification": "not_established",
            "resources": {
                case.scenario: {
                    "database": snapshot.get("operation:" + case.scenario + ":create", {})
                    .get("receipt", {})
                    .get("result"),
                    "worker": snapshot.get("operation:" + case.scenario + ":worker-create", {})
                    .get("receipt", {})
                    .get("result"),
                }
                for case in self.plan.cases
            },
            "unresolvedIntents": [
                key
                for key, event in self.journal.snapshot().items()
                if event["state"] in {"intent", "unknown"}
            ],
            "providerCalls": self._calls,
            "providerMutations": self._mutations,
            "cleanupOwner": self.plan.cleanup_owner,
            "revocationOwner": self.plan.revocation_owner,
            "revocation": "external_owner_required",
        }
