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
    if type(plan) is dict and plan.get("kind") == "offline_complete_composition_lifecycle":
        try:
            expected = build_composition_plan(plan["delta"], plan["startMs"])
            if canonical(plan) != canonical(expected):
                raise ValueError("closed_plan_mismatch")
        except KeyError, TypeError, OverflowError, RecursionError:
            raise ValueError("closed_plan_mismatch") from None
        return
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

    def _assert_owner(self) -> None:
        if self._closed:
            raise ValueError("journal_closed")
        try:
            with self.marker.open("r", encoding="utf-8") as marker:
                owned = marker.read(65) == self._owner_token
        except OSError, UnicodeError:
            owned = False
        if not owned:
            raise ValueError("journal_owner_mismatch")

    def start_once(self) -> None:
        """Consume this exact plan even when preflight stops without dispatch."""
        self._assert_owner()
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
        except OSError, UnicodeError:
            pass

    def records(self) -> list[tuple[str, str]]:
        return self.connection.execute(
            "SELECT operation,disposition FROM attempts ORDER BY rowid"
        ).fetchall()

    def latch(self, operation: str) -> None:
        self._assert_owner()
        if operation not in self.plan["operations"] and operation not in (
            "reconcile_1",
            "reconcile_2",
        ):
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
        self._assert_owner()
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


# The complete-delta adapter below deliberately has no caller-supplied transport.
# It executes concrete operations only against this finite synthetic provider.
COMPOSITION_OPERATIONS = (
    "read_baseline",
    *(
        name
        for number in range(3)
        for name in (f"create_resource_{number}", f"read_resource_{number}")
    ),
    "initialize_synthetic",
    "read_initialized",
    "upload_version",
    "read_version",
    "apply_temporary",
    "read_temporary",
    "disable_temporary",
    "read_disabled",
    "restore_retained",
    "read_restored",
    *(
        name
        for number in reversed(range(3))
        for name in (f"delete_resource_{number}", f"read_absent_{number}")
    ),
)
COMPOSITION_FAULTS = FAULTS | {"ownership_drift", "configuration_drift", "module_drift"}


def build_composition_plan(delta: dict[str, Any], start_ms: int) -> dict[str, Any]:
    """Bind a complete reviewed delta to one finite non-replayable offline attempt."""
    from scripts.temporary_composition_delta import validate_delta

    validate_delta(delta)
    if type(start_ms) is not int or not 0 <= start_ms <= 2**53 - OUTER_MS:
        raise ValueError("operation_time")
    if start_ms != delta["additions"]["scope"]["startsAt"]:
        raise ValueError("composition_start_mismatch")
    return {
        "schemaVersion": 1,
        "kind": "offline_complete_composition_lifecycle",
        "run": delta["additions"]["run"],
        "startMs": start_ms,
        "workExpiresMs": start_ms + WORK_MS,
        "outerExpiresMs": start_ms + OUTER_MS,
        "delta": copy.deepcopy(delta),
        "operations": list(COMPOSITION_OPERATIONS),
        "operationCap": len(COMPOSITION_OPERATIONS) + 2,
        "reconciliationReadCap": 2,
        "deploymentAllowed": False,
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "nativeQualified": False,
        "transportQualified": False,
    }


def _quota_scope(plan: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    # These are the existing quota_receiver.mjs row/limit semantics. Revision in
    # the admission receipt is a local sequence only, never a provider CAS token.
    return {
        "run": plan["run"],
        "startsAt": plan["startMs"],
        "expiresAt": plan["outerExpiresMs"],
        "enabled": enabled,
        "fga": 0,
        "receiver": 0,
        "arrivals": 0,
        "authorizationPresent": False,
        "canaryMatch": False,
        "initialized": True,
        "limits": {"fga": 96, "receiver": 16, "lifetimeMs": OUTER_MS},
    }


class SyntheticCompositionProvider:
    """Full-state synthetic resource/version/deployment seam, never a provider client.

    Reads compare the supplied complete baseline, not a guessed five-binding
    subset. The retained version is immutable and restoration selects it without
    uploading or rebuilding it. Temporary uploaded versions remain retained and
    are reported separately from owned-resource cleanup.
    """

    def __init__(
        self, plan: dict[str, Any], faults: dict[str, str] | None = None, *, tick_ms: int = 0
    ):
        validate_plan(plan)
        if plan["kind"] != "offline_complete_composition_lifecycle":
            raise ValueError("complete_plan_required")
        faults = {} if faults is None else faults
        if (
            type(faults) is not dict
            or not set(faults) <= set(COMPOSITION_OPERATIONS) | {"reconcile_1", "reconcile_2"}
            or any(
                type(value) is not str or value not in COMPOSITION_FAULTS
                for value in faults.values()
            )
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
        self._retained = copy.deepcopy(plan["delta"]["baseline"])
        self._state = {
            "snapshot": copy.deepcopy(self._retained),
            "admission": {"run": plan["run"], "enabled": False, "revision": 1},
            "initialized": False,
            "ownedResources": [],
            "receiverArtifact": None,
            "quotaScope": None,
            "uploadedVersion": None,
        }

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._state)

    def _call(self, operation: str, request: dict[str, Any]) -> dict[str, Any]:
        if operation not in COMPOSITION_OPERATIONS and operation not in (
            "reconcile_1",
            "reconcile_2",
        ):
            raise ValueError("operation_outside_plan")
        self.calls.append(operation)
        self.elapsed_ms += self.tick_ms
        fault = self.faults.get(operation)
        if fault == "refused":
            return {"outcome": "refused"}
        delta = self.plan["delta"]
        resources = delta["additions"]["resources"]
        owned = self._state["ownedResources"]
        if operation.startswith("create_resource_"):
            number = int(operation.rsplit("_", 1)[1])
            expected_request = (
                resources[number]
                if number != 2
                else {"resource": resources[number], "artifact": delta["additions"]["receiver"]}
            )
            if canonical(request) != canonical(expected_request) or any(
                item["identity"] == resources[number]["identity"] for item in owned
            ):
                return {"outcome": "refused"}
            owned.append(copy.deepcopy(resources[number]))
            if number == 2:
                self._state["receiverArtifact"] = copy.deepcopy(delta["additions"]["receiver"])
        elif operation == "initialize_synthetic":
            if (
                request != {"run": self.plan["run"], "startsAt": self.plan["startMs"]}
                or canonical(owned) != canonical(resources)
                or self._state["initialized"] is not False
            ):
                return {"outcome": "refused"}
            self._state["initialized"] = True
            self._state["admission"]["enabled"] = True
            self._state["quotaScope"] = _quota_scope(self.plan, enabled=True)
        elif operation == "upload_version":
            expected = {
                "version": delta["additions"]["temporaryVersion"],
                "moduleSha256": delta["temporary"]["moduleSha256"],
                "configurationSha256": digest(delta["temporary"]["configuration"]),
            }
            if request != expected or self._state["uploadedVersion"] is not None:
                return {"outcome": "refused"}
            self._state["uploadedVersion"] = copy.deepcopy(expected)
        elif operation == "apply_temporary":
            expected = {
                "strategy": "percentage",
                "force": False,
                "versions": [
                    {"version_id": delta["additions"]["temporaryVersion"], "percentage": 100}
                ],
            }
            if request != expected or self._state["uploadedVersion"] is None:
                return {"outcome": "refused"}
            production_state = copy.deepcopy(self._state["snapshot"]["productionState"])
            self._state["snapshot"] = copy.deepcopy(delta["temporary"])
            self._state["snapshot"]["productionState"] = production_state
        elif operation == "disable_temporary":
            if request != {"run": self.plan["run"]}:
                return {"outcome": "refused"}
            self._state["admission"] = {"run": self.plan["run"], "enabled": False, "revision": 2}
            if self._state["quotaScope"] is not None:
                self._state["quotaScope"]["enabled"] = False
        elif operation == "restore_retained":
            if request != delta["restore"] or self._state["admission"]["enabled"] is not False:
                return {"outcome": "refused"}
            # A version selection never rewinds, repairs, or replaces database facts.
            production_state = copy.deepcopy(self._state["snapshot"]["productionState"])
            self._state["snapshot"] = copy.deepcopy(self._retained)
            self._state["snapshot"]["productionState"] = production_state
        elif operation.startswith("delete_resource_"):
            number = int(operation.rsplit("_", 1)[1])
            if (
                request != resources[number]
                or not owned
                or canonical(owned[-1]) != canonical(request)
                or canonical(self._state["snapshot"]) != canonical(self._retained)
                or self._state["admission"]["enabled"] is not False
            ):
                return {"outcome": "refused"}
            owned.pop()
            if number == 2:
                self._state["receiverArtifact"] = None
            if number == 1:
                self._state["quotaScope"] = None
        elif request:
            return {"outcome": "refused"}
        if fault in ("identity_drift", "configuration_drift", "reference_drift"):
            self._state["snapshot"]["configuration"]["runtime"]["syntheticDrift"] = True
        if fault in (
            "data_drift",
            "typed_data_drift",
            "schema_drift",
            "secret_drift",
            "gate_drift",
        ):
            self._state["snapshot"]["productionState"]["syntheticDrift"] = fault
        if fault == "ownership_drift" and owned:
            owned[-1]["run"] = "b" * 32
        if fault == "version_drift":
            self._state["snapshot"]["retainedVersion"] = "synthetic-foreign-version"
        if fault == "weights_drift":
            version = self._state["snapshot"]["retainedVersion"]
            self._state["snapshot"]["deploymentWeights"] = {version: 99}
        if fault == "module_drift":
            self._state["snapshot"]["moduleSha256"] = "0" * 64
        if fault == "stop":
            self.stop_requested = True
        if fault == "exception":
            raise OSError("synthetic_dispatch_failure")
        if fault == "unknown":
            return {"outcome": "unknown"}
        if fault == "malformed":
            return {"outcome": True}
        return {"outcome": "accepted", "state": self.snapshot()}


def rehearse_composition(
    plan: dict[str, Any],
    journal: LifecycleJournal,
    provider: SyntheticCompositionProvider,
    *,
    now_ms: int | None = None,
    stop_requested: bool = False,
) -> dict[str, Any]:
    """Execute the fixed synthetic apply/stop/restore/cleanup adapter exactly once.

    No global-drain oracle, provider CAS, live authority, or retry is implied.
    Complete-state reads fence each transition locally; unknown outcomes leave a
    durable pending latch and permit only two bounded independent reads.
    """
    validate_plan(plan)
    if type(provider) is not SyntheticCompositionProvider or type(journal) is not LifecycleJournal:
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
    delta = plan["delta"]
    # Construct expected state from the plan alone. A provider snapshot cannot
    # grant authority to extra state or silently inherit an unreviewed field.
    expected = {
        "snapshot": copy.deepcopy(delta["baseline"]),
        "ownedResources": [],
        "receiverArtifact": None,
        "quotaScope": None,
        "admission": {"run": plan["run"], "enabled": False, "revision": 1},
        "initialized": False,
        "uploadedVersion": None,
    }
    reason = "not_started"
    cleanup = "cleanup_unconfirmed"
    halted = False
    applied = False
    initialized = False
    uploaded = False
    created: list[int] = []
    absence_confirmed: set[int] = set()

    def call(operation: str, request: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal reason, halted
        if halted:
            return None
        if base + provider.elapsed_ms >= plan["outerExpiresMs"]:
            reason, halted = "outer_expired", True
            return None
        journal.latch(operation)
        try:
            reply = provider._call(operation, copy.deepcopy(request))
            valid = (
                type(reply) is dict
                and type(reply.get("outcome")) is str
                and reply["outcome"] in ("accepted", "refused", "unknown")
                and set(reply)
                == ({"outcome", "state"} if reply["outcome"] == "accepted" else {"outcome"})
            )
            if valid and reply["outcome"] == "accepted":
                valid = type(reply["state"]) is dict
                canonical(reply["state"])
        except Exception:
            valid = False
            reply = {"outcome": "unknown"}
        if not valid or reply["outcome"] == "unknown":
            reason, halted = "ambiguous_dispatch", True
            for number in range(1, 3):
                if base + provider.elapsed_ms >= plan["outerExpiresMs"]:
                    break
                name = f"reconcile_{number}"
                journal.latch(name)
                try:
                    observation = provider._call(name, {})
                    if type(observation) is dict and observation.get("outcome") == "accepted":
                        journal.finish(name, "accepted")
                    elif type(observation) is dict and observation == {"outcome": "refused"}:
                        journal.finish(name, "refused")
                except Exception:
                    pass
            return None
        journal.finish(operation, reply["outcome"])
        if reply["outcome"] == "refused":
            reason, halted = "operation_refused", True
            return None
        if base + provider.elapsed_ms >= plan["outerExpiresMs"]:
            reason, halted = "outer_expired", True
            return None
        return cast(dict[str, Any], reply["state"])

    def observed(operation: str) -> bool:
        nonlocal reason
        state = call(operation, {})
        if state is None:
            return False
        if canonical(state) != canonical(expected):
            reason = "independent_state_mismatch"
            return False
        return True

    def work_open() -> bool:
        nonlocal reason
        if stop_requested or provider.stop_requested:
            reason = "stopped_before_apply"
            return False
        if base + provider.elapsed_ms >= plan["workExpiresMs"]:
            reason = "work_expired_before_apply"
            return False
        return True

    if not work_open():
        cleanup = "not_applied"
    elif observed("read_baseline"):
        if not work_open():
            cleanup = "not_applied"
        else:
            ready = True
            for number, resource in enumerate(delta["additions"]["resources"]):
                if not work_open():
                    ready = False
                    break
                create_request = (
                    resource
                    if number != 2
                    else {"resource": resource, "artifact": delta["additions"]["receiver"]}
                )
                if call(f"create_resource_{number}", create_request) is None:
                    ready = False
                    break
                created.append(number)
                expected["ownedResources"].append(copy.deepcopy(resource))
                if number == 2:
                    expected["receiverArtifact"] = copy.deepcopy(delta["additions"]["receiver"])
                if not observed(f"read_resource_{number}"):
                    ready = False
                    break
            if ready and work_open():
                if (
                    call("initialize_synthetic", {"run": plan["run"], "startsAt": plan["startMs"]})
                    is not None
                ):
                    initialized = True
                    expected["initialized"] = True
                    expected["admission"]["enabled"] = True
                    expected["quotaScope"] = _quota_scope(plan, enabled=True)
                    ready = observed("read_initialized")
                else:
                    ready = False
            else:
                ready = False
            if ready and work_open():
                upload = {
                    "version": delta["additions"]["temporaryVersion"],
                    "moduleSha256": delta["temporary"]["moduleSha256"],
                    "configurationSha256": digest(delta["temporary"]["configuration"]),
                }
                if call("upload_version", upload) is not None:
                    uploaded = True
                    expected["uploadedVersion"] = upload
                    ready = observed("read_version")
                else:
                    ready = False
            else:
                ready = False
            if ready and work_open():
                deploy = {
                    "strategy": "percentage",
                    "force": False,
                    "versions": [
                        {"version_id": delta["additions"]["temporaryVersion"], "percentage": 100}
                    ],
                }
                if call("apply_temporary", deploy) is not None:
                    applied = True
                    expected["snapshot"] = copy.deepcopy(delta["temporary"])
                    observed("read_temporary")
            # Stop admission even after a known observation mismatch. The full
            # disabled read then prevents restore/deletion when any drift exists.
            stopped = not initialized
            if initialized and call("disable_temporary", {"run": plan["run"]}) is not None:
                expected["admission"] = {"run": plan["run"], "enabled": False, "revision": 2}
                expected["quotaScope"] = _quota_scope(plan, enabled=False)
                stopped = observed("read_disabled")
            if stopped and not halted:
                restored = not applied
                if applied and call("restore_retained", delta["restore"]) is not None:
                    expected["snapshot"] = copy.deepcopy(delta["baseline"])
                    restored = True
                if restored and observed("read_restored"):
                    for number in reversed(created):
                        resource = delta["additions"]["resources"][number]
                        if call(f"delete_resource_{number}", resource) is None:
                            break
                        expected["ownedResources"].pop()
                        if number == 2:
                            expected["receiverArtifact"] = None
                        if number == 1:
                            expected["quotaScope"] = None
                        if not observed(f"read_absent_{number}"):
                            break
                        absence_confirmed.add(number)
                    else:
                        cleanup, reason = "confirmed_offline", "restored_and_absent"
    if reason == "not_started":
        reason = "independent_state_mismatch"
    return {
        "schemaVersion": 1,
        "kind": "offline_complete_composition_receipt",
        "planSha256": digest(plan),
        "cleanup": cleanup,
        "reason": reason,
        "stopObserved": stop_requested or provider.stop_requested,
        "operationsAttempted": len(journal.records()),
        "pendingOperations": [name for name, state in journal.records() if state == "pending"],
        "retainedTemporaryVersion": delta["additions"]["temporaryVersion"] if uploaded else None,
        "temporaryVersionDisposition": (
            "acknowledged_retained"
            if uploaded
            else "unknown"
            if ("upload_version", "pending") in journal.records()
            else "not_uploaded"
        ),
        "ownedResourcesRequiringReconciliation": [
            copy.deepcopy(delta["additions"]["resources"][number])
            for number in created
            if number not in absence_confirmed
        ],
        "unacknowledgedCreationOperations": [
            name
            for name, state in journal.records()
            if name.startswith("create_resource_") and state == "pending"
        ],
        "deploymentAllowed": False,
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "nativeQualified": False,
        "transportQualified": False,
    }
