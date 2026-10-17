"""Closed offline lifecycle rehearsal; no provider transport or live execution seam.

Synthetic state verifies orchestration only. Accepted method, schedule, custody,
current-provider preservation and live execution gates remain independently closed.
"""

from __future__ import annotations

import copy
import sqlite3
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from scripts.synthetic_restoration_packet import baseline_snapshot, build_packet, canonical, digest

WORK_MS = 600_000
OUTER_MS = 1_200_000
OPERATIONS = (
    "read_baseline",
    "create_receiver",
    "read_receiver_created",
    "apply_temporary",
    "read_temporary",
    "disable_temporary",
    "read_disabled",
    "restore_retained",
    "read_restored",
    "delete_receiver",
    "read_receiver_absent",
)
MUTATIONS = frozenset(
    (
        "create_receiver",
        "apply_temporary",
        "disable_temporary",
        "restore_retained",
        "delete_receiver",
    )
)
FAULTS = frozenset(
    (
        "refused",
        "unknown",
        "exception",
        "malformed",
        "identity_drift",
        "data_drift",
        "typed_data_drift",
        "schema_drift",
        "secret_drift",
        "gate_drift",
        "reference_drift",
        "version_drift",
        "weights_drift",
        "stop",
    )
)


def build_plan(run: str, start_ms: int) -> dict[str, Any]:
    packet = build_packet(run, start_ms)
    case = packet["cases"][0]
    retained = baseline_snapshot(case)
    receiver = "synthetic-receiver-" + run
    return {
        "schemaVersion": 1,
        "kind": "offline_temporary_composition_lifecycle",
        "run": run,
        "startMs": start_ms,
        "workExpiresMs": start_ms + WORK_MS,
        "outerExpiresMs": start_ms + OUTER_MS,
        "retained": retained,
        "temporaryVersion": "synthetic-temporary-" + run,
        "receiver": receiver,
        "receiverOwner": run,
        "restore": {
            "strategy": "percentage",
            "force": False,
            "versions": [{"version_id": retained["activeVersion"], "percentage": 100}],
        },
        "operations": list(OPERATIONS),
        "operationCap": len(OPERATIONS) + 2,
        "reconciliationReadCap": 2,
        "deploymentAllowed": False,
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "nativeQualified": False,
        "transportQualified": False,
    }


def validate_plan(plan: Any) -> None:
    try:
        if type(plan) is not dict or canonical(plan) != canonical(
            build_plan(plan["run"], plan["startMs"])
        ):
            raise ValueError("closed_plan_mismatch")
    except KeyError, TypeError, OverflowError, RecursionError:
        raise ValueError("closed_plan_mismatch") from None


class SyntheticProvider:
    """Finite built-in memory model. No caller adapter, URL, credential or file IO."""

    def __init__(
        self, plan: dict[str, Any], faults: dict[str, str] | None = None, *, tick_ms: int = 0
    ):
        validate_plan(plan)
        faults = {} if faults is None else faults
        if (
            type(faults) is not dict
            or not set(faults) <= set(OPERATIONS)
            or any(type(v) is not str or v not in FAULTS for v in faults.values())
        ):
            raise ValueError("synthetic_fault")
        if type(tick_ms) is not int or not 0 <= tick_ms <= OUTER_MS:
            raise ValueError("synthetic_tick")
        self.plan = copy.deepcopy(plan)
        self.faults = dict(faults)
        self.tick_ms = tick_ms
        self.elapsed_ms = 0
        self.stop_requested = False
        self.calls: list[str] = []
        self._state = {
            "snapshot": copy.deepcopy(plan["retained"]),
            "admissionOff": True,
            "receiver": None,
        }

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._state)

    def _call(self, operation: str, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(operation)
        self.elapsed_ms += self.tick_ms
        fault = self.faults.get(operation)
        if fault == "refused":
            return {"outcome": "refused"}
        if operation == "create_receiver":
            if self._state["receiver"] is not None:
                return {"outcome": "refused"}
            self._state["receiver"] = {"id": self.plan["receiver"], "owner": self.plan["run"]}
        elif operation == "apply_temporary":
            self._state["snapshot"]["activeVersion"] = self.plan["temporaryVersion"]
            self._state["snapshot"]["weights"] = {self.plan["temporaryVersion"]: 100}
            self._state["snapshot"]["moduleDigest"] = digest("synthetic-temporary-module")
            self._state["admissionOff"] = False
        elif operation == "disable_temporary":
            self._state["admissionOff"] = True
        elif operation == "restore_retained":
            if request != self.plan["restore"] or self._state["admissionOff"] is not True:
                return {"outcome": "refused"}
            self._state["snapshot"] = copy.deepcopy(self.plan["retained"])
        elif operation == "delete_receiver":
            if request != self._state["receiver"]:
                return {"outcome": "refused"}
            self._state["receiver"] = None
        if fault == "identity_drift":
            self._state["snapshot"]["resources"]["d1"] = "synthetic-foreign-database"
        if fault == "data_drift":
            self._state["snapshot"]["data"]["rows"].append(["synthetic-drift", 1])
        if fault == "typed_data_drift":
            self._state["snapshot"]["data"]["rows"][0][1] = "1"
        if fault == "schema_drift":
            self._state["snapshot"]["data"]["schema"] = "synthetic_v2"
        if fault == "secret_drift":
            self._state["snapshot"]["secretMatchesBaseline"] = False
        if fault == "gate_drift":
            self._state["snapshot"]["gates"]["deployment"]["enabled"] = True
        if fault == "reference_drift":
            self._state["snapshot"]["bindings"]["secret"] = "synthetic-foreign-secret"
        if fault == "version_drift":
            self._state["snapshot"]["activeVersion"] = "synthetic-foreign-version"
        if fault == "weights_drift":
            self._state["snapshot"]["weights"] = {self.plan["retained"]["activeVersion"]: 99}
        if fault == "stop":
            self.stop_requested = True
        if fault == "exception":
            raise OSError("synthetic_dispatch_failure")
        if fault == "unknown":
            return {"outcome": "unknown"}
        if fault == "malformed":
            return {"outcome": True}
        return {"outcome": "accepted", "state": self.snapshot()}


class LifecycleJournal:
    """Exclusive owner and durable non-replayable dispatch markers.

    A pending marker survives close and reopen. Rehearsals never replay a journal;
    read-only reconciliation remains visible without clearing uncertain dispatch.
    """

    def __init__(self, path: Path, plan: dict[str, Any]):
        validate_plan(plan)
        self.plan = copy.deepcopy(plan)
        self.marker = path.with_name(path.name + ".owner")
        self._owner_token = uuid4().hex
        self._closed = False
        with self.marker.open("x", encoding="utf-8") as marker:
            marker.write(self._owner_token)
        try:
            self.connection = sqlite3.connect(path)
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("CREATE TABLE IF NOT EXISTS plan (digest TEXT PRIMARY KEY)")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS attempts "
                "(operation TEXT PRIMARY KEY, disposition TEXT NOT NULL)"
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS started "
                "(singleton INTEGER PRIMARY KEY CHECK(singleton=1))"
            )
            rows = self.connection.execute("SELECT digest FROM plan").fetchall()
            if rows and rows != [(digest(plan),)]:
                raise ValueError("journal_plan_mismatch")
            self.connection.execute("INSERT OR IGNORE INTO plan VALUES (?)", (digest(plan),))
            self.connection.commit()
        except BaseException:
            if hasattr(self, "connection"):
                self.connection.close()
            self._release_marker()
            raise

    def start_once(self) -> None:
        """Consume this exact plan even when preflight stops without dispatch."""
        try:
            self.connection.execute("INSERT INTO started VALUES (1)")
            self.connection.commit()
        except sqlite3.IntegrityError:
            self.connection.rollback()
            raise ValueError("run_already_attempted") from None

    def _release_marker(self) -> None:
        try:
            with self.marker.open("r", encoding="utf-8") as marker:
                owned = marker.read(65) == self._owner_token
            if owned:
                self.marker.unlink()
        except FileNotFoundError:
            pass

    def records(self) -> list[tuple[str, str]]:
        return self.connection.execute(
            "SELECT operation,disposition FROM attempts ORDER BY rowid"
        ).fetchall()

    def latch(self, operation: str) -> None:
        if operation not in OPERATIONS and operation not in ("reconcile_1", "reconcile_2"):
            raise ValueError("operation_outside_plan")
        if len(self.records()) >= self.plan["operationCap"]:
            raise ValueError("operation_cap")
        try:
            self.connection.execute("INSERT INTO attempts VALUES (?, 'pending')", (operation,))
            self.connection.commit()
        except sqlite3.IntegrityError:
            self.connection.rollback()
            raise ValueError("operation_replay") from None

    def finish(self, operation: str, disposition: str) -> None:
        if disposition not in ("accepted", "refused"):
            raise ValueError("invalid_disposition")
        result = self.connection.execute(
            "UPDATE attempts SET disposition=? WHERE operation=? AND disposition='pending'",
            (disposition, operation),
        )
        self.connection.commit()
        if result.rowcount != 1:
            raise ValueError("no_pending_attempt")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.connection.close()
        self._release_marker()


def _temporary(plan: dict[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(plan["retained"])
    state["activeVersion"] = plan["temporaryVersion"]
    state["weights"] = {plan["temporaryVersion"]: 100}
    state["moduleDigest"] = digest("synthetic-temporary-module")
    return state


def rehearse(
    plan: dict[str, Any],
    journal: LifecycleJournal,
    provider: SyntheticProvider,
    *,
    now_ms: int | None = None,
    stop_requested: bool = False,
) -> dict[str, Any]:
    """Rehearse exactly once. Unknown dispatch permits only two reads, never retry.

    Stop/inner expiry skips new work and enters bounded safety cleanup. Outer
    expiry forbids further operations and leaves cleanup explicitly unconfirmed.
    """
    validate_plan(plan)
    if type(provider) is not SyntheticProvider or type(journal) is not LifecycleJournal:
        raise ValueError("builtin_synthetic_only")
    if canonical(plan) != canonical(journal.plan) or canonical(plan) != canonical(provider.plan):
        raise ValueError("plan_identity_mismatch")
    base = plan["startMs"] if now_ms is None else now_ms
    if type(base) is not int or not plan["startMs"] <= base <= 2**53:
        raise ValueError("operation_time")
    if type(stop_requested) is not bool:
        raise ValueError("stop_flag")
    if journal.records() or provider.calls:
        raise ValueError("run_already_attempted")
    journal.start_once()
    status = "cleanup_unconfirmed"
    reason = "not_started"
    stop_seen = stop_requested
    attempted = 0

    def call(operation: str, request: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal attempted, reason
        if base + provider.elapsed_ms >= plan["outerExpiresMs"]:
            reason = "outer_expired"
            return None
        journal.latch(operation)
        attempted += 1
        try:
            reply = provider._call(operation, request)
        except Exception:
            reply = {"outcome": "unknown"}
        if (
            type(reply) is not dict
            or set(reply) not in ({"outcome"}, {"outcome", "state"})
            or type(reply.get("outcome")) is not str
            or reply["outcome"] not in ("accepted", "refused", "unknown")
            or (reply["outcome"] == "accepted" and set(reply) != {"outcome", "state"})
        ):
            reply = {"outcome": "unknown"}
        if reply["outcome"] == "unknown":
            reason = "ambiguous_dispatch"
            # No state-changing call follows uncertainty. Mark reads before dispatch too.
            for number in range(1, 3):
                if base + provider.elapsed_ms >= plan["outerExpiresMs"]:
                    break
                reconcile = f"reconcile_{number}"
                journal.latch(reconcile)
                attempted += 1
                provider.elapsed_ms += provider.tick_ms
                provider.snapshot()
                journal.finish(reconcile, "accepted")
            return None
        journal.finish(operation, reply["outcome"])
        if reply["outcome"] == "refused":
            reason = "operation_refused"
            return None
        # An operation reaching the outer deadline cannot establish timely cleanup.
        if base + provider.elapsed_ms >= plan["outerExpiresMs"]:
            reason = "outer_expired"
            return None
        return cast(dict[str, Any], reply["state"])

    def matches(
        state: Any, expected: dict[str, Any], admission_off: bool, receiver_present: bool = True
    ) -> bool:
        receiver = {"id": plan["receiver"], "owner": plan["run"]} if receiver_present else None
        return canonical(state) == canonical(
            {"snapshot": expected, "admissionOff": admission_off, "receiver": receiver}
        )

    if stop_requested or base >= plan["workExpiresMs"]:
        reason = "stopped_before_apply" if stop_requested else "work_expired_before_apply"
        status = "not_applied"
    else:
        before = call("read_baseline", {})
        if before is not None and matches(before, plan["retained"], True, False):
            if base + provider.elapsed_ms >= plan["workExpiresMs"] or provider.stop_requested:
                status = "not_applied"
                reason = (
                    "stopped_before_apply"
                    if provider.stop_requested
                    else "work_expired_before_apply"
                )
            else:
                created = call("create_receiver", {"id": plan["receiver"], "owner": plan["run"]})
                checked_receiver = (
                    call("read_receiver_created", {}) if created is not None else None
                )
                if checked_receiver is not None and matches(
                    checked_receiver, plan["retained"], True
                ):
                    stop_seen = stop_requested or provider.stop_requested
                    work_expired = base + provider.elapsed_ms >= plan["workExpiresMs"]
                    restored_ok = False
                    if stop_seen or work_expired:
                        # Receiver exists, but no application dispatch occurred.
                        checked = call("read_restored", {})
                        restored_ok = checked is not None and matches(
                            checked, plan["retained"], True
                        )
                    else:
                        applied = call("apply_temporary", {"version": plan["temporaryVersion"]})
                        if applied is not None:
                            # A failed observation never substitutes for admission-off.
                            call("read_temporary", {})
                            stop_seen = stop_requested or provider.stop_requested
                            if reason != "ambiguous_dispatch":
                                disabled = call("disable_temporary", {"receiver": plan["receiver"]})
                                if disabled is not None:
                                    off = call("read_disabled", {})
                                    if off is not None and matches(off, _temporary(plan), True):
                                        restored = call(
                                            "restore_retained", copy.deepcopy(plan["restore"])
                                        )
                                        if restored is not None:
                                            checked = call("read_restored", {})
                                            restored_ok = checked is not None and matches(
                                                checked, plan["retained"], True
                                            )
                        elif reason == "operation_refused":
                            # Refused apply changed no application state; retain an
                            # independent baseline check before owned-resource cleanup.
                            checked = call("read_restored", {})
                            restored_ok = checked is not None and matches(
                                checked, plan["retained"], True
                            )
                    if restored_ok:
                        deleted = call(
                            "delete_receiver", {"id": plan["receiver"], "owner": plan["run"]}
                        )
                        if deleted is not None:
                            absent = call("read_receiver_absent", {})
                            if absent is not None and matches(
                                absent, plan["retained"], True, False
                            ):
                                status, reason = "confirmed_offline", "restored_and_absent"
    if reason == "not_started":
        reason = "independent_state_mismatch"
    return {
        "schemaVersion": 1,
        "kind": "offline_lifecycle_receipt",
        "planSha256": digest(plan),
        "cleanup": status,
        "reason": reason,
        "stopObserved": stop_seen or provider.stop_requested,
        "operationsAttempted": attempted,
        "pendingOperations": [name for name, state in journal.records() if state == "pending"],
        "deploymentAllowed": False,
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "nativeQualified": False,
        "transportQualified": False,
    }
