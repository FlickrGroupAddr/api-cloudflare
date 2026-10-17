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
            self._closed = False
        except BaseException:
            if self._db is not None:
                self._db.close()
            if self._owner is not None:
                self._owner.close()
            with _OWNERS_LOCK:
                _OWNERS.discard(self._name)
            raise

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

    Real provider inability to prove pending D1 work is terminal `pending`, not
    inferred quiescence. Cleanup is a separate authority boundary below. An
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

    def _window(self, *, cleanup: bool = False) -> None:
        from scripts.hosted_publisher_operator_plan import utc_time

        if self.plan.digest != self._plan_digest:
            raise OperatorRefused("plan_changed_after_binding")
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

    def _before_request(self, key: str, mutation: bool, metadata: dict[str, Any]) -> None:
        from scripts.hosted_publisher_operator_plan import validate_operator_grant

        self._window(cleanup=getattr(self, "_cleanup_mode", False))
        validate_operator_grant(self.plan, self.operator_grant, self._now())
        if getattr(self, "_cleanup_mode", False):
            if self._now() >= self._cleanup_expires_at:
                raise OperatorRefused("cleanup_authority_expired")
        elif not getattr(self, "_stopping", False) and (self._stopped or self.stop_check()):
            self._stopped = True
            raise OperatorRefused("dispatch_stopped")
        if (
            type(metadata) is not dict
            or set(metadata) != {"method", "path", "requestBytes"}
            or metadata["method"] not in {"GET", "POST", "PUT", "DELETE"}
            or type(metadata["path"]) is not str
            or not re.fullmatch(
                r"/(?:d1/database|workers/scripts)(?:/[a-zA-Z0-9_/-]{1,160})?", metadata["path"]
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

    def _after_request(self, key: str, receipt: dict[str, Any]) -> None:
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
        if not self.journal.reserve("operation:" + key, {"operation": key}):
            raise OperatorRefused("operator_operation_already_reserved")
        try:
            result = method(*args, key=key, **kwargs)
            # Provider readbacks are untrusted until compared. A drifted binding
            # may contain a credential under an innocuous `text` key. Persist no
            # arbitrary response/projection, even on the rejecting path.
            receipt: dict[str, Any] = {"present": result is not None}
            if method.__name__ == "create_database":
                from scripts.hosted_publisher_operator_plan import utc_time

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
                utc_time(result["created_at"])
                receipt = {"result": result}
            elif method.__name__ == "upload_worker":
                if (
                    type(result) is not dict
                    or set(result) != {"id", "etag", "moduleSha2_256"}
                    or result["id"] not in {c.worker_name for c in self.plan.cases}
                    or result["moduleSha2_256"] != self.plan.pins["worker"]
                    or type(result["etag"]) is not str
                    or not 0 < len(result["etag"]) <= 512
                ):
                    raise OperatorRefused("upload_receipt_identity_unknown")
                result = {
                    "id": result["id"],
                    "moduleSha2_256": result["moduleSha2_256"],
                    "etagSha2_256": hashlib.sha256(result["etag"].encode()).hexdigest(),
                }
                receipt = {"result": result}
            self.journal.complete("operation:" + key, receipt)
            return result
        except Exception:
            if self._active_request is not None:
                self.journal.unknown(self._active_request, "provider_outcome_unknown")
                self._active_request = None
            self.journal.unknown("operation:" + key, "operation_outcome_unknown")
            raise OperatorRefused("operation_outcome_unknown") from None

    def _check_deployment(self, case: Any, entry: dict[str, Any], prefix: str) -> None:
        from scripts.hosted_publisher_operator_plan import validate_deployed_projection

        settings = self._call(
            self.provider.inspect_worker, case.worker_name, key=prefix + ":settings"
        )
        expected_settings = {k: v for k, v in entry["projection"].items() if k != "main_module"}
        validate_deployed_projection(expected_settings, settings)
        module = self._call(
            self.provider.inspect_module,
            case.worker_name,
            self.plan.pins["worker"],
            key=prefix + ":module",
        )
        if module.get("moduleSha2_256") != self.plan.pins["worker"]:
            raise OperatorRefused("deployed_module_drift")
        if (
            type(module.get("etag")) is not str
            or not module["etag"]
            or hashlib.sha256(module["etag"].encode()).hexdigest()
            != entry["version"]["etagSha2_256"]
        ):
            raise OperatorRefused("deployed_version_drift")

    def run(self) -> dict[str, Any]:
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
        if "atomic_create_only_worker_upload" in getattr(
            self.provider, "unsupported_operations", ()
        ):
            raise OperatorRefused("provider_atomic_worker_creation_unsupported")
        if not self.journal.reserve("operator:run", {"planDigest": self.plan.digest}):
            raise OperatorRefused("operator_run_already_reserved")
        result: dict[str, Any] = {
            "status": "pending",
            "cases": [],
            "cleanup": "not_attempted",
            "revocation": "external_owner_required",
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
                if (
                    self._call(
                        self.provider.inspect_worker, case.worker_name, key=key + ":worker-absent"
                    )
                    is not None
                ):
                    raise OperatorRefused("worker_already_exists")
                identity = self._call(
                    self.provider.create_database, case.d1_name, key=key + ":create"
                )
                entry = {
                    "database": identity,
                    "worker": case.worker_name,
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
                receipts.append(
                    CreationReceipt(
                        case.scenario,
                        case.worker_name,
                        case.d1_name,
                        identity["uuid"],
                        identity["created_at"],
                        True,
                        self.plan.digest,
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
                    self.provider.upload_worker,
                    case.worker_name,
                    bundle,
                    self.plan.pins["worker"],
                    projection,
                    self.private_inputs.token(key),
                    key=key + ":upload",
                )
                entry["uploaded"] = True
                self._check_deployment(case, entry, key + ":deployed")
                self._fence()
                self._call(self.provider.set_endpoint, case.worker_name, True, key=key + ":enable")
                if self._call(
                    self.provider.inspect_endpoint, case.worker_name, key=key + ":enabled"
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
                if entry and entry["uploaded"] and not entry.get("accessDisabled"):
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
            self._call(self.provider.set_endpoint, case.worker_name, False, key=key + ":disable")
            observed = self._call(
                self.provider.inspect_endpoint, case.worker_name, key=key + ":disabled"
            )
        finally:
            self._stopping = False
        entry["accessDisabled"] = observed == {"enabled": False, "previews_enabled": False}
        # Endpoint disable readback neither cancels an executing phase nor proves
        # provider/D1 drain. The concrete provider reports this seam unsupported.
        entry["quiescence"] = "unknown_pending_d1_observation"
        if not entry["accessDisabled"]:
            raise OperatorRefused("access_stop_unknown")

    def cleanup_only(self, authority: dict[str, Any]) -> dict[str, Any]:
        if not self._execution_lock.acquire(blocking=False):
            raise OperatorRefused("operator_concurrent_execution")
        try:
            return self._cleanup_once(authority)
        finally:
            self._cleanup_mode = False
            self._execution_lock.release()

    def _cleanup_once(self, authority: dict[str, Any]) -> dict[str, Any]:
        """Separate exact authority; real unsupported drain yields pending only.

        Resources are recovered from the durable completed create/upload operations,
        never from broad account discovery, prefix selection or a caller's ledger.
        A fresh operator can use this path after a crash without resuming `run`.
        """
        from scripts.hosted_publisher_operator_plan import (
            deployment_projection,
            utc_time,
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
            or authority["actions"] != ["disable_access", "observe_pending", "delete_exact_pairs"]
            or not isinstance(authority["decision_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", authority["decision_id"])
            or not self._now()
            < utc_time(authority["expires_at"])
            <= utc_time(self.plan.cleanup_deadline)
        ):
            raise OperatorRefused("separate_cleanup_authority_required")
        self._window(cleanup=True)
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
            create = snapshot.get("operation:" + case.scenario + ":create")
            upload = snapshot.get("operation:" + case.scenario + ":upload")
            if not create or create["state"] != "complete":
                results.append({"scenario": case.scenario, "status": "identity_unknown"})
                continue
            identity = create["receipt"]["result"]
            if not upload or upload["state"] != "complete":
                results.append({"scenario": case.scenario, "status": "worker_identity_unknown"})
                continue
            entry = {
                "database": identity,
                "version": upload["receipt"]["result"],
                "projection": deployment_projection(self.plan, case, identity["uuid"]),
            }
            prefix = attempt + ":" + case.scenario
            try:
                self._check_deployment(case, entry, prefix)
                if (
                    self._call(self.provider.inspect_database, identity, key=prefix + ":database")
                    != identity
                ):
                    raise OperatorRefused("cleanup_database_drift")
                self._call(
                    self.provider.set_endpoint, case.worker_name, False, key=prefix + ":disable"
                )
                disabled = self._call(
                    self.provider.inspect_endpoint, case.worker_name, key=prefix + ":disabled"
                )
                if disabled != {"enabled": False, "previews_enabled": False}:
                    raise OperatorRefused("cleanup_access_unknown")
                # No boolean or self-asserted receipt supplied by the caller can
                # stand in for provider operation observation. Real adapter lacks it.
                observe = getattr(self.provider, "observe_pending", None)
                if observe is None:
                    results.append({"scenario": case.scenario, "status": "pending_d1_observation"})
                    continue
                observation = self._call(observe, identity, key=prefix + ":pending")
                if observation != {"quiescent": True, "database_uuid": identity["uuid"]}:
                    results.append({"scenario": case.scenario, "status": "pending_d1_observation"})
                    continue
                self._call(
                    self.provider.delete_worker,
                    case.worker_name,
                    {k: v for k, v in entry["projection"].items() if k != "main_module"},
                    key=prefix + ":delete-worker",
                )
                self._call(self.provider.delete_database, identity, key=prefix + ":delete-database")
                if (
                    self._call(
                        self.provider.inspect_worker,
                        case.worker_name,
                        key=prefix + ":worker-absence",
                    )
                    is not None
                    or self._call(
                        self.provider.inspect_database, identity, key=prefix + ":database-absence"
                    )
                    is not None
                ):
                    raise OperatorRefused("cleanup_absence_unknown")
                results.append({"scenario": case.scenario, "status": "absent"})
            except Exception:
                results.append({"scenario": case.scenario, "status": "cleanup_unknown"})
                break
        self.journal.complete(attempt, {"results": results})
        return {
            "status": "complete"
            if len(results) == 4 and all(item["status"] == "absent" for item in results)
            else "pending",
            "cases": results,
            "revocation": "external_owner_required",
        }
