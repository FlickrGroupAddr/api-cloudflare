"""Finite synthetic restoration preparation; intentionally no provider or secret reader."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

CAPTURE_INDEX_SHA256 = "ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202"
CAPTURED_BINDING_TYPES = {
    "assets": 1,
    "d1": 1,
    "durable_object_namespace": 1,
    "plain_text": 14,
    "secrets_store_secret": 9,
}
CAPTURED_BINDINGS_SHA256 = "8d41009f984b5292e2e5ae6a89cdd2529d01b7aac5a7e8f8e0ad1d7e375ed097"
SUPPORTED_SECRET_TYPES = ("secrets_store_secret",)
WORK_MS = 600_000
OUTER_MS = 1_200_000
SNAPSHOT_KEYS = frozenset(
    "activeVersion weights moduleDigest bindings resources configuration data gates "
    "secretMatchesBaseline".split()
)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_packet(run: str, start_ms: int, owner: str = "bot") -> dict[str, Any]:
    """Synthetic labels are not provider IDs; later acknowledged IDs need new review."""
    if not isinstance(run, str) or re.fullmatch("[0-9a-f]{32}", run) is None:
        raise ValueError("run_identity")
    if type(start_ms) is not int or not 0 <= start_ms <= 2**53 - OUTER_MS:
        raise ValueError("start_time")
    if owner != "bot":
        raise ValueError("owner")
    cases = []
    for secret_type in SUPPORTED_SECRET_TYPES:
        for case in ("A", "B"):
            key = f"{secret_type}-{case.lower()}"
            prefix = f"fga-rst-{run}-{case.lower()}"
            resources = {
                "worker": prefix,
                "d1": prefix + "-db",
                "durableObjectNamespace": prefix + "-do",
                "assets": prefix + "-assets",
                "secret": prefix + "-secret",
            }
            if secret_type == "secrets_store_secret":
                resources["store"] = prefix + "-store"
            operations = [f"check_absent_{name}" for name in resources]
            operations += [f"create_{name}" for name in resources]
            operations += [
                "seed_paused_fixture",
                "upload_baseline",
                "deploy_baseline",
                "snapshot_baseline",
                "upload_temporary",
                "deploy_temporary",
                "snapshot_temporary",
            ]
            if case == "B":
                operations += ["change_synthetic_secret", "snapshot_changed"]
            operations += ["restore_retained", "snapshot_restored"]
            operations += [
                "delete_worker",
                "delete_assets",
                "delete_durableObjectNamespace",
                "delete_d1",
            ]
            operations += ["delete_secret"]
            if "store" in resources:
                operations += ["delete_store"]
            cases.append(
                {
                    "id": key,
                    "case": case,
                    "secretType": secret_type,
                    "resources": resources,
                    "baselineVersion": prefix + "-retained",
                    "temporaryVersion": prefix + "-temporary",
                    "restore": {
                        "strategy": "percentage",
                        "force": False,
                        "versions": [{"version_id": prefix + "-retained", "percentage": 100}],
                    },
                    "operations": operations,
                    "operationCap": len(operations) + 2,
                    "readOnlyReconciliationCap": 2,
                    "syntheticInvocationsCap": 4,
                }
            )
    return {
        "schemaVersion": 1,
        "kind": "offline_synthetic_restoration_packet",
        "run": run,
        "owner": owner,
        "startMs": start_ms,
        "workExpiresMs": start_ms + WORK_MS,
        "outerExpiresMs": start_ms + OUTER_MS,
        "captureIndexSha256": CAPTURE_INDEX_SHA256,
        "capturedBindingTypes": dict(CAPTURED_BINDING_TYPES),
        "capturedBindingsSourceSha256": CAPTURED_BINDINGS_SHA256,
        "secretTypes": list(SUPPORTED_SECRET_TYPES),
        "cases": cases,
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "deploymentAllowed": False,
    }


def validate_packet(packet: dict[str, Any]) -> None:
    try:
        expected = build_packet(packet["run"], packet["startMs"], packet["owner"])
        # Canonical bytes distinguish JSON booleans from integers and reject NaN.
        if canonical(packet) != canonical(expected):
            raise ValueError("packet_mismatch")
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("packet_shape") from exc


def baseline_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    """Known synthetic rows and marker booleans only, never real captured values."""
    return {
        "activeVersion": case["baselineVersion"],
        "weights": {case["baselineVersion"]: 100},
        "moduleDigest": digest({"module": "synthetic_baseline_v1"}),
        "bindings": {"type": case["secretType"], **case["resources"]},
        "resources": copy.deepcopy(case["resources"]),
        "configuration": {
            "compatibilityDate": "2026-10-16",
            "intake": False,
            "dispatch": False,
            "routes": [],
            "customDomains": [],
            "outbound": False,
            "scheduled": False,
        },
        "data": {
            "schema": "synthetic_v1",
            "rows": [
                ["permanent_suppression", 1],
                ["credential_generation", 1],
                ["admission", 0],
                ["intent", 0],
                ["dispatch", 0],
            ],
        },
        "gates": {
            "deployment": {"enabled": False, "revision": 7},
            "user": {"enabled": False, "revision": 11},
        },
        "secretMatchesBaseline": True,
    }


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if type(snapshot) is not dict or set(snapshot) != SNAPSHOT_KEYS:
        raise ValueError("snapshot_shape")
    if type(snapshot["secretMatchesBaseline"]) is not bool:
        raise ValueError("snapshot_marker")
    if (
        not isinstance(snapshot["moduleDigest"], str)
        or re.fullmatch("[0-9a-f]{64}", snapshot["moduleDigest"]) is None
    ):
        raise ValueError("snapshot_digest")
    if type(snapshot["weights"]) is not dict or any(
        type(weight) is not int for weight in snapshot["weights"].values()
    ):
        raise ValueError("snapshot_weights")
    if type(snapshot["gates"]) is not dict or set(snapshot["gates"]) != {"deployment", "user"}:
        raise ValueError("snapshot_gates")
    for gate in snapshot["gates"].values():
        if (
            type(gate) is not dict
            or set(gate) != {"enabled", "revision"}
            or type(gate["enabled"]) is not bool
            or type(gate["revision"]) is not int
        ):
            raise ValueError("snapshot_gates")
    canonical(snapshot)


def classify(
    case: str,
    before: dict[str, Any],
    after: dict[str, Any],
    outcome: str,
    *,
    pre_restore: dict[str, Any] | None = None,
) -> str:
    """Compare complete snapshots; an acknowledgment alone establishes nothing."""
    if case not in ("A", "B") or outcome not in ("accepted", "refused", "unknown"):
        raise ValueError("classification_input")
    _validate_snapshot(before)
    _validate_snapshot(after)
    if any(gate["enabled"] is not False for gate in before["gates"].values()):
        raise ValueError("baseline_not_paused")
    if before["secretMatchesBaseline"] is not True:
        raise ValueError("baseline_marker")
    if outcome == "unknown":
        return "unknown_cleanup_unconfirmed"
    if case == "A":
        return (
            "preserved"
            if outcome == "accepted" and canonical(before) == canonical(after)
            else "drift"
        )
    if pre_restore is None:
        raise ValueError("changed_snapshot_required")
    _validate_snapshot(pre_restore)
    if pre_restore["secretMatchesBaseline"] is not False:
        raise ValueError("secret_change_not_measured")
    if outcome == "refused":
        return (
            "refusal_accounted"
            if canonical(after) == canonical(pre_restore)
            else "refusal_with_drift"
        )
    if canonical(before) == canonical(after):
        return "accepted_baseline_observed"
    expected = copy.deepcopy(before)
    expected["secretMatchesBaseline"] = False
    if canonical(expected) == canonical(after):
        return "accepted_changed_value_drift"
    return "accepted_configuration_or_data_drift"


class Journal:
    """One owner, durable per-operation latch; crash markers require investigation."""

    def __init__(self, path: Path, packet: dict[str, Any]):
        validate_packet(packet)
        self.packet = copy.deepcopy(packet)
        self.marker = path.with_name(path.name + ".owner")
        self.marker.open("x", encoding="utf-8").close()
        try:
            self.connection = sqlite3.connect(path)
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("CREATE TABLE IF NOT EXISTS packet (digest TEXT PRIMARY KEY)")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS attempts "
                "(case_id TEXT, operation TEXT, acknowledged INTEGER NOT NULL, "
                "PRIMARY KEY(case_id, operation))"
            )
            rows = self.connection.execute("SELECT digest FROM packet").fetchall()
            if rows and rows != [(digest(packet),)]:
                raise ValueError("journal_packet_mismatch")
            self.connection.execute("INSERT OR IGNORE INTO packet VALUES (?)", (digest(packet),))
            self.connection.commit()
        except BaseException:
            if hasattr(self, "connection"):
                self.connection.close()
            self.marker.unlink()
            raise

    def latch(self, case_id: str, operation: str, now_ms: int) -> None:
        cases = {case["id"]: case for case in self.packet["cases"]}
        if case_id not in cases or operation not in cases[case_id]["operations"]:
            raise ValueError("operation_outside_packet")
        if type(now_ms) is not int or now_ms < self.packet["startMs"]:
            raise ValueError("operation_time")
        cleanup = operation.startswith("delete_")
        if not cleanup and now_ms >= self.packet["workExpiresMs"]:
            raise ValueError("scope_expired")
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            if self.connection.execute(
                "SELECT 1 FROM attempts WHERE acknowledged=0 LIMIT 1"
            ).fetchone():
                raise ValueError("unacknowledged_operation")
            previous = self.connection.execute(
                "SELECT operation, acknowledged FROM attempts WHERE case_id=? "
                "AND operation NOT LIKE 'reconcile_%' "
                "ORDER BY rowid",
                (case_id,),
            ).fetchall()
            sequence = cases[case_id]["operations"]
            if previous != [(name, 1) for name in sequence[: len(previous)]]:
                raise ValueError("unacknowledged_operation")
            if len(previous) >= len(sequence) or operation != sequence[len(previous)]:
                raise ValueError("operation_order_or_replay")
            self.connection.execute("INSERT INTO attempts VALUES (?, ?, 0)", (case_id, operation))
            self.connection.commit()  # Must complete before the simulated operation.
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ValueError("operation_already_attempted") from exc
        except BaseException:
            self.connection.rollback()
            raise

    def acknowledge(self, case_id: str, operation: str) -> None:
        result = self.connection.execute(
            "UPDATE attempts SET acknowledged=1 WHERE case_id=? AND operation=? AND acknowledged=0",
            (case_id, operation),
        )
        self.connection.commit()
        if result.rowcount != 1:
            raise ValueError("acknowledgment_without_pending_attempt")

    def reconcile(self, case_id: str) -> None:
        if case_id not in {case["id"] for case in self.packet["cases"]}:
            raise ValueError("case_outside_packet")
        pending = self.connection.execute(
            "SELECT operation FROM attempts WHERE case_id=? AND acknowledged=0", (case_id,)
        ).fetchall()
        if pending != [("restore_retained",)]:
            raise ValueError("ambiguous_restore_required")
        rows = self.connection.execute(
            "SELECT operation FROM attempts WHERE case_id=? AND operation LIKE 'reconcile_%'",
            (case_id,),
        ).fetchall()
        if len(rows) >= 2:
            raise ValueError("reconciliation_exhausted")
        self.connection.execute(
            "INSERT INTO attempts VALUES (?, ?, 1)", (case_id, f"reconcile_{len(rows) + 1}")
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
        self.marker.unlink()


def rehearse(
    packet: dict[str, Any],
    journal: Journal,
    secret_outcome: str = "refused",
    *,
    now_ms: int | None = None,
    delete_outcome: str = "acknowledged",
) -> dict[str, Any]:
    """Execute only this built-in in-memory adapter; no dynamic/live adapter seam."""
    validate_packet(packet)
    if canonical(packet) != canonical(journal.packet):
        raise ValueError("journal_packet_mismatch")
    if secret_outcome not in ("refused", "changed_value", "baseline", "unknown", "resource_drift"):
        raise ValueError("synthetic_outcome")
    if delete_outcome not in ("acknowledged", "unknown"):
        raise ValueError("synthetic_delete_outcome")
    operation_time: int = packet["startMs"] if now_ms is None else now_ms
    results = []
    for case in packet["cases"]:
        before = baseline_snapshot(case)
        temporary = copy.deepcopy(before)
        temporary["activeVersion"] = case["temporaryVersion"]
        temporary["weights"] = {case["temporaryVersion"]: 100}
        temporary["moduleDigest"] = digest({"module": "synthetic_temporary_v1"})
        if case["case"] == "B":
            temporary["secretMatchesBaseline"] = False
        classification = "unknown_cleanup_unconfirmed"
        attempted = 0
        acknowledged_resources = {}
        current = copy.deepcopy(before)
        outcome = "unknown"
        cleanup_confirmed = False
        for operation in case["operations"]:
            if operation.startswith("delete_") and classification != "preserved":
                break  # Keep Case B or ambiguous resources for explicit investigation.
            journal.latch(case["id"], operation, operation_time)
            attempted += 1
            if operation.startswith("create_"):
                name = operation.removeprefix("create_")
                acknowledged_resources[name] = case["resources"][name]
            elif operation == "deploy_temporary":
                current = copy.deepcopy(temporary)
                current["secretMatchesBaseline"] = True
            elif operation == "change_synthetic_secret":
                current["secretMatchesBaseline"] = False
            elif operation == "restore_retained":
                outcome = "accepted"
                current = copy.deepcopy(before)
                if case["case"] == "B":
                    if secret_outcome in ("refused", "unknown"):
                        current = copy.deepcopy(temporary)
                        outcome = secret_outcome
                    elif secret_outcome in ("changed_value", "resource_drift"):
                        current["secretMatchesBaseline"] = False
                        if secret_outcome == "resource_drift":
                            current["resources"]["d1"] = "synthetic_unexpected"
                if outcome == "unknown":
                    # No acknowledgment or replay after ambiguity, only two reads.
                    for _ in range(2):
                        journal.reconcile(case["id"])
                        attempted += 1
                    break
            elif operation == "snapshot_restored":
                classification = classify(
                    case["case"], before, current, outcome, pre_restore=temporary
                )
            elif operation.startswith("delete_"):
                name = operation.removeprefix("delete_")
                if acknowledged_resources.get(name) != case["resources"][name]:
                    raise ValueError("unowned_resource")
                if delete_outcome == "unknown":
                    break  # No deletion acknowledgment: retain the pending latch.
                del acknowledged_resources[name]
            journal.acknowledge(case["id"], operation)
        cleanup_confirmed = classification == "preserved" and not acknowledged_resources
        results.append(
            {
                "case": case["case"],
                "secretType": case["secretType"],
                "classification": classification,
                "operationsAttempted": attempted,
                "cleanup": "confirmed_offline" if cleanup_confirmed else "cleanup_unconfirmed",
            }
        )
        if case["case"] == "A" and not cleanup_confirmed:
            break  # Do not begin another experiment after unresolved A cleanup.
    return {
        "schemaVersion": 1,
        "kind": "offline_synthetic_restoration_receipt",
        "packetSha256": digest(packet),
        "results": results,
        "notAttemptedCases": [case["id"] for case in packet["cases"][len(results) :]],
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "deploymentAllowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("start_ms", type=int)
    parser.add_argument("private_output", type=Path)
    parser.add_argument(
        "--synthetic-outcome",
        default="refused",
        choices=("refused", "changed_value", "baseline", "unknown", "resource_drift"),
    )
    args = parser.parse_args()
    journal = None
    try:
        packet = build_packet(args.run, args.start_ms)
        output = args.private_output.resolve()
        repository = Path(__file__).resolve().parent.parent
        if (
            repository == output
            or repository in output.parents
            or not any(parent.name == "private-evidence" for parent in output.parents)
        ):
            raise ValueError("private_destination_required")
        output.mkdir(parents=True, exist_ok=False)
        (output / "packet.json").write_text(json.dumps(packet, indent=2) + "\n", newline="\n")
        journal = Journal(output / "journal.sqlite3", packet)
        receipt = rehearse(packet, journal, args.synthetic_outcome)
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", newline="\n")
        print(json.dumps(receipt))
        return 0
    except ValueError, OSError, sqlite3.Error:
        print(
            json.dumps(
                {
                    "kind": "offline_synthetic_restoration_failure",
                    "cleanup": "cleanup_unconfirmed",
                    "deploymentAllowed": False,
                }
            )
        )
        return 2
    finally:
        if journal is not None:
            journal.close()


if __name__ == "__main__":
    raise SystemExit(main())
