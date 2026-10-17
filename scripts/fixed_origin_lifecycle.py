"""Offline-only one-attempt fixed-origin lifecycle model; no provider implementation.

The injected operations object is a test double. This module never imports the
hosted lifecycle/provider/credential modules. CLI execution is always refused.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

LIMITS = {"fga": 96, "receiver": 16, "lifetimeMs": 1_200_000}
SECRET_NAMES = ("FGA_FIXED_ORIGIN_CAPABILITY", "FGA_FIXED_ORIGIN_CANARY")
QUALIFICATION_BINDINGS = (
    "FIXED_ORIGIN_DB",
    "FIXED_ORIGIN_RUN",
    "FIXED_ORIGIN_CAPABILITY",
    "FIXED_ORIGIN_CANARY",
    "FIXED_ORIGIN_RECEIVER",
)


class Refused(ValueError):
    """Closed failure without provider diagnostics or credential material."""


class OfflineOperations(Protocol):
    """Test seam only; implementing a live adapter requires a later ticket/gate."""

    offline: bool

    def absent(self, kind: str, name: str) -> bool: ...
    def create(self, kind: str, name: str) -> str: ...
    def initialize_guard(self, run: str, starts_at: int, expires_at: int) -> bool: ...
    def guard(self, run: str) -> dict[str, Any]: ...
    def install(self, bindings: tuple[str, ...], qualification_scope: dict[str, Any]) -> bool: ...
    def disable(self, run: str) -> bool: ...
    def restore(self, capture_digest: str) -> dict[str, Any]: ...
    def delete(self, kind: str, name: str, identity: str) -> bool: ...


class Lifecycle:
    """Durably latch every mutation before invoking the offline test seam.

    SQLite's transaction owns the attempt latch, including competing instances.
    A crash/exception after that latch is ambiguous and never retried. A failed
    delete is likewise retained for explicit reconciliation rather than replay.
    Journal content is private, contains identities, and must not be published.
    """

    def __init__(
        self,
        path: Path,
        *,
        run: str,
        starts_at: int,
        capture_digest: str,
        operations: OfflineOperations,
        clock: Callable[[], int],
    ):
        if (
            re.fullmatch(r"[a-f0-9]{32}", run) is None
            or re.fullmatch(r"[a-f0-9]{64}", capture_digest) is None
            or type(starts_at) is not int
            or starts_at < 0
            or operations.offline is not True
        ):
            raise Refused("invalid_offline_scope")
        self.operations = operations
        self.clock = clock
        self.lock_path = Path(str(path.resolve()) + ".owner")
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY, body TEXT)")
        state = {
            "schemaVersion": 1,
            "run": run,
            "startsAt": starts_at,
            "expiresAt": starts_at + LIMITS["lifetimeMs"],
            "qualificationStartsAt": starts_at,
            "qualificationExpiresAt": starts_at + 600_000,
            "captureDigest": capture_digest,
            "operations": {},
            "resources": [
                {"kind": "d1", "name": f"fga-fixed-origin-db-{run}"},
                {"kind": "receiver", "name": f"fga-fixed-origin-recv-{run}"},
                *({"kind": "actions-secret", "name": name} for name in SECRET_NAMES),
            ],
        }
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO journal VALUES (1, ?)", (json.dumps(state),))
        saved = self.state()
        for key in (
            "run",
            "startsAt",
            "expiresAt",
            "qualificationStartsAt",
            "qualificationExpiresAt",
            "captureDigest",
            "resources",
        ):
            if saved[key] != state[key]:
                self.db.close()
                raise Refused("journal_scope_mismatch")

    def close(self) -> None:
        self.db.close()

    def state(self) -> dict[str, Any]:
        return json.loads(self.db.execute("SELECT body FROM journal WHERE id=1").fetchone()[0])

    def _save(self, state: dict[str, Any]) -> None:
        self.db.execute("UPDATE journal SET body=? WHERE id=1", (json.dumps(state),))

    @contextmanager
    def _ownership(self):
        # One lifecycle operator, including cleanup, across processes. A crash
        # leaves the marker for explicit reconciliation; never infer it stale.
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise Refused("lifecycle_owner_or_recovery_required") from None
        try:
            yield
        finally:
            os.close(descriptor)
            self.lock_path.unlink()

    def _once(self, key: str, operation: Callable[[], Any]) -> Any:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            state = self.state()
            if key in state["operations"]:
                raise Refused("operation_already_attempted")
            state["operations"][key] = {"attempted": True, "acknowledged": False}
            self._save(state)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        # Deliberately no retry or exception-text persistence.
        result = operation()
        with self.db:
            state = self.state()
            state["operations"][key]["result"] = result
            state["operations"][key]["acknowledged"] = True
            self._save(state)
        return result

    def _time(self) -> None:
        state = self.state()
        now = self.clock()
        if type(now) is not int or not state["startsAt"] <= now < state["expiresAt"]:
            raise Refused("expired_or_invalid_clock")

    def _guard(self, *, disabled: bool = False) -> None:
        if not disabled:
            self._time()
        state = self.state()
        if not disabled and not (
            state["qualificationStartsAt"] <= self.clock() < state["qualificationExpiresAt"]
        ):
            raise Refused("qualification_window_expired")
        guard = self.operations.guard(state["run"])
        if (
            guard.get("run") != state["run"]
            or guard.get("startsAt") != state["startsAt"]
            or guard.get("expiresAt") != state["expiresAt"]
            or guard.get("enabled") is not (not disabled)
            or guard.get("initialized") is not True
            or guard.get("limits") != LIMITS
            or any(
                type(guard.get(role)) is not int
                or not 0 <= guard[role] <= LIMITS[role]
                or (not disabled and guard[role] == LIMITS[role])
                for role in ("fga", "receiver")
            )
        ):
            raise Refused("durable_guard_not_ready")

    def provision(self) -> None:
        """Simulate the exact proposed resources once, then gated publication."""
        with self._ownership():
            self._provision()

    def _provision(self) -> None:
        self._time()
        state = self.state()
        if state["operations"]:
            raise Refused("attempt_already_started")
        if (
            self._once(
                "preflight",
                lambda: all(
                    self.operations.absent(row["kind"], row["name"]) is True
                    for row in state["resources"]
                ),
            )
            is not True
        ):
            raise Refused("resource_or_secret_preexists")
        for row in state["resources"]:
            self._time()
            key = "create:" + row["name"]

            def create(row=row):
                identity = self.operations.create(row["kind"], row["name"])
                if not isinstance(identity, str) or not re.fullmatch(
                    r"[a-zA-Z0-9_-]{1,128}", identity
                ):
                    raise Refused("unacknowledged_identity")
                if row["kind"] != "d1" and identity != row["name"]:
                    raise Refused("identity_mismatch")
                if row["kind"] == "d1" and str(uuid.UUID(identity)) != identity:
                    raise Refused("identity_mismatch")
                return identity

            self._once(key, create)
        if (
            self._once(
                "initialize_guard",
                lambda: self.operations.initialize_guard(
                    state["run"], state["startsAt"], state["expiresAt"]
                ),
            )
            is not True
        ):
            raise Refused("guard_initialization_unconfirmed")
        self._guard()
        if (
            self._once(
                "install",
                lambda: self.operations.install(
                    QUALIFICATION_BINDINGS,
                    {
                        "run": state["run"],
                        "startsAt": state["qualificationStartsAt"],
                        "expiresAt": state["qualificationExpiresAt"],
                    },
                ),
            )
            is not True
        ):
            raise Refused("install_unconfirmed")
        self._guard()  # Publication receipt cannot succeed after delayed install/expiry.

    def attempt(self) -> bool:
        """Offline orchestration: cleanup on success, failure, expiry or cancellation.

        Exceptions propagate after cleanup, retaining the separate cleanup
        outcome in the private journal. Neither a pass nor cleanup unlocks #37.
        """
        try:
            self.provision()
        finally:
            self.cleanup()
        return self.state().get("cleanupConfirmed") is True

    def cleanup(self) -> bool:
        """Disable admission and verify exact restoration before any deletion."""
        with self._ownership():
            return self._cleanup()

    def _cleanup(self) -> bool:
        state = self.state()
        if "cleanupConfirmed" in state:
            return state["cleanupConfirmed"] is True
        try:
            if self._once("disable", lambda: self.operations.disable(state["run"])) is not True:
                raise Refused("admission_off_unconfirmed")
            self._guard(disabled=True)
            restored = self._once(
                "restore", lambda: self.operations.restore(state["captureDigest"])
            )
            if restored != {
                "captureDigest": state["captureDigest"],
                "ordinaryRoutesVerified": True,
                "qualificationBindingsAbsent": True,
                "writeGatesDisabled": True,
                "productionStateUnchanged": True,
            }:
                raise Refused("exact_restore_unconfirmed")
            for row in reversed(state["resources"]):
                creation = self.state()["operations"].get("create:" + row["name"])
                if creation is None:
                    continue
                if creation["acknowledged"] is not True:
                    raise Refused("creation_ambiguous")
                identity = creation["result"]
                if (
                    self._once(
                        "delete:" + row["name"],
                        lambda row=row, identity=identity: self.operations.delete(
                            row["kind"], row["name"], identity
                        ),
                    )
                    is not True
                ):
                    raise Refused("deletion_absence_unconfirmed")
            confirmed = True
        except Exception:
            confirmed = False
        with self.db:
            state = self.state()
            state["cleanupConfirmed"] = confirmed
            state["outcome"] = "cleanup_confirmed" if confirmed else "cleanup_unconfirmed"
            self._save(state)
        return confirmed


def main() -> int:
    print("fixed_origin_lifecycle_disabled: offline test model only")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
