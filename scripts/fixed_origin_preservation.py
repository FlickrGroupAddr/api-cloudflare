"""Bounded synthetic preservation comparator; no provider or credential adapter.

All accepted input is explicitly synthetic. A successful result tests the evidence
contract only and cannot establish current production state or authorize deployment.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sqlite3
from typing import Any, cast

from scripts.fixed_origin_restore import FILES, INDEX_SHA256, MODULE_SHA256

MAX_TABLES = 128
MAX_ROWS = 10_000
MAX_BYTES = 4 * 1024 * 1024
MAX_SCHEMA = 2048
MAX_AGE_MS = 60_000
LIFETIME_MS = 1_200_000
READ_CHECKS = ("installation-auth-refusal", "discovery-disabled", "thumbnail-disabled")
RESOURCE_KINDS = ("d1", "receiver", "actions-capability", "actions-canary")
LOCAL_KINDS = ("native-target", "native-cache", "local-secret")
MISSING_SOURCE_SEAMS = (
    "fresh_complete_capture_and_retained_target_readback",
    "current_exact_gate_scope_and_revision_authority",
    "bounded_consistent_production_schema_and_full_data_reader",
    "approved_background_quiescence_and_authenticated_read_checks",
    "resource_secret_reference_and_do_lifecycle_continuity_reader",
    "independent_admission_off_restore_and_exact_absence_receipts",
    "matching_run_native_and_local_cleanup_receipts",
)


class Refused(ValueError):
    """A closed failure category; never includes private input or SQL diagnostics."""


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise Refused(category)


def _keys(value: Any, keys: str, category: str) -> None:
    _require(type(value) is dict and set(value) == set(keys.split()), category)


def _integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= 2**63 - 1


def _hash(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _identity(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"synthetic-[a-z0-9-]{1,80}", value) is not None


def _json(value: Any) -> bytes:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except ValueError, TypeError, RecursionError:
        raise Refused("invalid_evidence_encoding") from None
    _require(len(raw) <= MAX_BYTES, "evidence_bound_exceeded")
    return raw


def _cell(value: Any) -> list[Any]:
    if value is None:
        return ["null", None]
    if type(value) is int:
        return ["integer", value]
    if type(value) is float:
        _require(math.isfinite(value), "unsupported_nonfinite_sqlite_value")
        # Binary representation avoids JSON number round trips and distinguishes -0.
        return ["real", value.hex()]
    if type(value) is str:
        return ["text", value]
    if type(value) is bytes:
        return ["blob", value.hex()]
    raise Refused("unsupported_sqlite_value")


def _canonical_real(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        decoded = float.fromhex(value)
    except ValueError, OverflowError:
        return False
    return math.isfinite(decoded) and decoded.hex() == value


def capture_sqlite(
    connection: sqlite3.Connection, *, run: str, database: str, observed_at_ms: int
) -> dict[str, Any]:
    """Read one explicit transaction from a caller-supplied synthetic SQLite DB.

    No file is opened, no remote adapter exists, and no caller transaction is committed.
    Schema, every table/column and every typed row are retained privately in the result.
    This intentionally cannot read arbitrary production paths or label itself hosted D1.
    """
    _require(_identity(database), "synthetic_database_required")
    _require(type(run) is str and re.fullmatch(r"[a-f0-9]{32}", run) is not None, "invalid_run")
    _require(_integer(observed_at_ms), "invalid_observation_time")
    try:
        _require(not connection.in_transaction, "caller_transaction_active")
        old_factory = connection.row_factory
        old_text_factory = connection.text_factory
        old_length_limit = connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_BYTES)
    except sqlite3.Error:
        raise Refused("synthetic_snapshot_unavailable") from None
    connection.row_factory = None
    connection.text_factory = str
    # Bound SQLite execution independently of fetched result sizes.
    budget = 0

    def progress() -> int:
        nonlocal budget
        budget += 1
        return int(budget > 10_000)

    try:
        connection.set_progress_handler(progress, 1000)
        connection.execute("BEGIN")
        # The engine's table classification handles whitespace/comments in CREATE
        # VIRTUAL TABLE and identifies shadow tables without parsing SQL text.
        storage = {}
        for table in connection.execute("PRAGMA main.table_list"):
            _require(table[2] not in ("virtual", "shadow"), "virtual_table_not_supported")
            _require(len(storage) <= MAX_TABLES, "table_bound_exceeded")
            storage[table[1]] = table[4]
        cursor = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name"
        )
        schema = []
        encoded_bytes = 0
        for row in cursor:
            _require(len(schema) < MAX_SCHEMA, "schema_bound_exceeded")
            encoded_bytes += len(_json(row))
            _require(encoded_bytes <= MAX_BYTES, "evidence_bound_exceeded")
            _require(
                not (
                    row[0] == "table"
                    and type(row[3]) is str
                    and row[3].upper().startswith("CREATE VIRTUAL TABLE")
                ),
                "virtual_table_not_supported",
            )
            schema.append(row)
        table_names = sorted(row[1] for row in schema if row[0] == "table")
        _require(len(table_names) <= MAX_TABLES, "table_bound_exceeded")
        tables = {}
        total = 0
        for name in table_names:
            quoted = '"' + name.replace('"', '""') + '"'
            cursor = connection.execute("SELECT * FROM " + quoted + " LIMIT 0")
            columns = [column[0] for column in cursor.description]
            _require(0 < len(columns) <= 256, "column_bound_exceeded")
            _require(name in storage and storage[name] in (0, 1), "storage_identity_unknown")
            has_rowid = storage[name] == 0
            if has_rowid:
                aliases = [
                    alias
                    for alias in ("rowid", "_rowid_", "oid")
                    if alias not in {column.lower() for column in columns}
                ]
                _require(bool(aliases), "hidden_rowid_inaccessible")
                cursor = connection.execute('SELECT "' + aliases[0] + '",* FROM ' + quoted)
            else:
                cursor = connection.execute("SELECT * FROM " + quoted)
            encoded = []
            identities = []
            for row in cursor:
                total += 1
                _require(total <= MAX_ROWS, "row_bound_exceeded")
                if has_rowid:
                    _require(type(row[0]) is int, "invalid_hidden_rowid")
                    identities.append(row[0])
                    row = row[1:]
                encoded_row = [_cell(cell) for cell in row]
                encoded_bytes += len(_json(encoded_row))
                if has_rowid:
                    encoded_bytes += len(_json(identities[-1]))
                _require(encoded_bytes <= MAX_BYTES, "evidence_bound_exceeded")
                encoded.append(encoded_row)
            if has_rowid:
                paired = sorted(zip(encoded, identities, strict=True), key=_json)
                encoded = [row for row, _ in paired]
                rowids = [rowid for _, rowid in paired]
            else:
                encoded = sorted(encoded, key=_json)
                rowids = None
            tables[name] = {"columns": columns, "rows": encoded, "rowids": rowids}
            _json(tables)
        result = {
            "mode": "synthetic-offline",
            "run": run,
            "database": database,
            "observedAtMs": observed_at_ms,
            "consistency": "single-sqlite-read-transaction",
            "schema": [list(row) for row in schema],
            "tables": tables,
        }
        _json(result)
        return result
    except sqlite3.Error:
        raise Refused("synthetic_snapshot_unavailable") from None
    finally:
        cleanup_failed = False
        try:
            if connection.in_transaction:
                connection.rollback()
        except sqlite3.Error:
            cleanup_failed = True
        # A denied rollback cannot skip independent restoration of client settings.
        try:
            connection.set_progress_handler(None, 0)
        except sqlite3.Error:
            cleanup_failed = True
        try:
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_length_limit)
        except sqlite3.Error:
            cleanup_failed = True
        try:
            connection.row_factory = old_factory
        except sqlite3.Error:
            cleanup_failed = True
        try:
            connection.text_factory = old_text_factory
        except sqlite3.Error:
            cleanup_failed = True
        if cleanup_failed:
            raise Refused("synthetic_snapshot_cleanup_failed_discard_connection") from None


def _database(
    snapshot: Any, run: str, identity: str, timestamp: int, profile_manifest: Any = None
) -> list[dict[str, Any]]:
    extra = (
        " profileManifest tableList provenance profileBinding"
        if profile_manifest is not None
        else ""
    )
    _keys(
        snapshot,
        "mode run database observedAtMs consistency schema tables" + extra,
        "invalid_snapshot",
    )
    _require(
        snapshot["mode"] == "synthetic-offline"
        and snapshot["run"] == run
        and snapshot["database"] == identity
        and snapshot["observedAtMs"] == timestamp
        and snapshot["consistency"] == "single-sqlite-read-transaction",
        "snapshot_scope_mismatch",
    )
    schema, tables = snapshot["schema"], snapshot["tables"]
    _require(type(schema) is list and len(schema) <= MAX_SCHEMA, "invalid_schema")
    _require(type(tables) is dict and len(tables) <= MAX_TABLES, "invalid_census")
    schema = cast(list[Any], schema)
    tables = cast(dict[str, Any], tables)
    names = []
    objects = set()
    for row in schema:
        _require(
            type(row) is list
            and len(row) == 4
            and row[0] in ("table", "index", "view", "trigger")
            and all(type(item) is str and item for item in row[1:3])
            and (row[3] is None or type(row[3]) is str),
            "invalid_schema",
        )
        _require((row[0], row[1]) not in objects, "duplicate_schema_object")
        objects.add((row[0], row[1]))
        if row[0] == "table":
            names.append(row[1])
    excluded = {"_cf_KV"} if profile_manifest is not None else set()
    _require(
        len(set(names)) == len(names) and set(names) - excluded == set(tables),
        "schema_census_mismatch",
    )
    total = 0
    for table in tables.values():
        _keys(table, "columns rows rowids", "invalid_table")
        columns, rows = table["columns"], table["rows"]
        _require(
            type(columns) is list
            and 0 < len(columns) <= 256
            and all(type(column) is str and column for column in columns)
            and len(columns) == len(set(columns))
            and type(rows) is list,
            "invalid_table",
        )
        total += len(rows)
        _require(total <= MAX_ROWS, "row_bound_exceeded")
        rowids = table["rowids"]
        _require(
            rowids is None
            or (
                type(rowids) is list
                and len(rowids) == len(rows)
                and all(type(item) is int and -(2**63) <= item < 2**63 for item in rowids)
                and len(rowids) == len(set(rowids))
            ),
            "invalid_hidden_rowids",
        )
        for row in rows:
            _require(type(row) is list and len(row) == len(columns), "invalid_row")
            row = cast(list[Any], row)
            for cell in row:
                _require(type(cell) is list and len(cell) == 2, "invalid_cell")
                tag, value = cell
                valid = (
                    (tag == "null" and value is None)
                    or (tag == "integer" and type(value) is int and -(2**63) <= value < 2**63)
                    or (tag == "text" and type(value) is str)
                    or (
                        tag == "blob"
                        and type(value) is str
                        and re.fullmatch(r"(?:[a-f0-9]{2})*", value) is not None
                    )
                    or (tag == "real" and _canonical_real(value))
                )
                _require(valid, "invalid_cell")
        if rowids is None:
            _require(rows == sorted(rows, key=_json), "noncanonical_rows")
        else:
            pairs = list(zip(rows, rowids, strict=True))
            _require(pairs == sorted(pairs, key=_json), "noncanonical_rows")
    if profile_manifest is not None:
        from scripts.private_d1_snapshot_profile import validate_snapshot

        validate_snapshot(snapshot, profile_manifest)
    _require("flickr_write_gates" in tables, "missing_durable_gates")
    gate_table = tables["flickr_write_gates"]
    _require(
        gate_table["columns"] == ["scope", "scope_id", "enabled", "revision"],
        "invalid_gate_columns",
    )
    return [
        dict(zip(gate_table["columns"], [cell[1] for cell in row], strict=True))
        for row in gate_table["rows"]
    ]


def _envelope(value: Any, profile_manifest: Any = None) -> None:
    extra = " profileBinding" if profile_manifest is not None else ""
    _keys(
        value,
        "mode run observedAtMs expiresAtMs admissionRevision captureIndexSha256 moduleSha256 "
        "inventory continuity gates database ordinaryReads ownedResources" + extra,
        "invalid_envelope",
    )
    _json(value)
    _require(value["mode"] == "synthetic-offline", "synthetic_evidence_required")
    run = value["run"]
    _require(type(run) is str and re.fullmatch(r"[a-f0-9]{32}", run) is not None, "invalid_run")
    _require(_integer(value["observedAtMs"]) and _integer(value["expiresAtMs"]), "invalid_time")
    _require(value["observedAtMs"] < value["expiresAtMs"], "expired_snapshot")
    _require(_integer(value["admissionRevision"], 1), "invalid_admission_revision")
    _require(
        value["captureIndexSha256"] == INDEX_SHA256 and value["moduleSha256"] == MODULE_SHA256,
        "captured_authority_mismatch",
    )
    inventory = value["inventory"]
    _require(
        type(inventory) is dict
        and set(inventory) == FILES
        and all(_hash(item) for item in inventory.values()),
        "incomplete_inventory",
    )
    continuity = value["continuity"]
    _keys(
        continuity,
        "retainedVersion weights bindingsSha256 runtimeSha256 edgeSha256 "
        "d1Identity doLifecycleSha256 assetsSha256 secretReferencesSha256 capabilities "
        "backgroundQuiescenceSha256",
        "incomplete_continuity",
    )
    _require(
        _identity(continuity["retainedVersion"]) and _identity(continuity["d1Identity"]),
        "invalid_retained_identity",
    )
    weights = continuity["weights"]
    _require(
        type(weights) is dict
        and set(weights) == {continuity["retainedVersion"]}
        and type(weights[continuity["retainedVersion"]]) is int
        and weights[continuity["retainedVersion"]] == 100,
        "invalid_retained_weights",
    )
    _require(
        all(_hash(item) for key, item in continuity.items() if key.endswith("Sha256")),
        "invalid_continuity_digest",
    )
    _keys(continuity["capabilities"], "intake dispatch thumbnail", "incomplete_capabilities")
    _require(
        all(item is False for item in continuity["capabilities"].values()),
        "capability_not_disabled",
    )
    gates = value["gates"]
    _require(type(gates) is list and len(gates) == 2, "invalid_gate_census")
    gates = cast(list[dict[str, Any]], gates)
    for gate in gates:
        _keys(gate, "scope scope_id enabled revision", "invalid_gate")
        _require(
            type(gate["enabled"]) is int and gate["enabled"] == 0 and _integer(gate["revision"], 1),
            "gate_not_paused",
        )
    _require(
        [(gate["scope"], gate["scope_id"]) for gate in gates]
        == [("deployment", "*"), ("user", "synthetic-user")],
        "gate_scope_mismatch",
    )
    db_gates = _database(
        value["database"], run, continuity["d1Identity"], value["observedAtMs"], profile_manifest
    )
    if profile_manifest is not None:
        _require(
            value["profileBinding"] == value["database"]["profileBinding"],
            "profile_envelope_mismatch",
        )
    _require(db_gates == gates, "gate_snapshot_contradiction")
    reads = value["ordinaryReads"]
    _require(type(reads) is list and len(reads) == len(READ_CHECKS), "incomplete_ordinary_reads")
    for read, check, status in zip(reads, READ_CHECKS, (401, 404, 404), strict=True):
        _keys(
            read,
            "check run moduleSha256 status boundedNoData noMutation noUpstream",
            "invalid_read",
        )
        _require(
            read["check"] == check
            and read["run"] == run
            and read["moduleSha256"] == MODULE_SHA256
            and type(read["status"]) is int
            and read["status"] == status
            and all(read[key] is True for key in ("boundedNoData", "noMutation", "noUpstream")),
            "ordinary_read_failed",
        )
    resources = value["ownedResources"]
    _require(type(resources) is list and len(resources) == len(RESOURCE_KINDS), "invalid_resources")
    identities = set()
    for resource, kind in zip(resources, RESOURCE_KINDS, strict=True):
        _keys(resource, "kind identity run", "invalid_resource")
        _require(
            resource["kind"] == kind
            and resource["run"] == run
            and _identity(resource["identity"])
            and resource["identity"] not in identities,
            "resource_scope_mismatch",
        )
        identities.add(resource["identity"])
    _require(continuity["d1Identity"] not in identities, "production_resource_in_cleanup")


def validate_preservation(
    baseline: dict[str, Any],
    refreshed: dict[str, Any],
    restored: dict[str, Any],
    cleanup: dict[str, Any],
    *,
    now_ms: int,
    profile_manifest: Any = None,
) -> dict[str, Any]:
    """Compare synthetic evidence; never initiate, retry or repair an operation.

    The default remains the original strict format. An explicit ADR0064 manifest
    requires new profile-bound inputs and cleanup evidence and returns a distinct
    limited receipt that explicitly denies whole-provider contents verification.
    """
    for value in (baseline, refreshed, restored):
        _envelope(value, profile_manifest)
    start = baseline["observedAtMs"]
    end = baseline["expiresAtMs"]
    _require(end - start == LIFETIME_MS, "lifecycle_bound_mismatch")
    _require(
        _integer(now_ms)
        and start <= refreshed["observedAtMs"] <= restored["observedAtMs"] <= now_ms < end
        and refreshed["observedAtMs"] - start <= MAX_AGE_MS
        and now_ms - restored["observedAtMs"] <= MAX_AGE_MS,
        "stale_or_invalid_observation",
    )
    # No accepted drift exception. All columns, rows, schema and continuity must agree.
    for value in (refreshed, restored):
        normalized = copy.deepcopy(value)
        normalized["observedAtMs"] = start
        normalized["database"]["observedAtMs"] = start
        _require(normalized == baseline, "unexplained_preservation_drift")
    extra = " profileBinding" if profile_manifest is not None else ""
    _keys(
        cleanup, "mode run stop restore resources local completedAtMs" + extra, "incomplete_cleanup"
    )
    if profile_manifest is not None:
        _require(
            cleanup["profileBinding"] == baseline["profileBinding"], "profile_cleanup_mismatch"
        )
    _json(cleanup)
    run = baseline["run"]
    _require(
        cleanup["mode"] == "synthetic-offline" and cleanup["run"] == run, "cleanup_scope_mismatch"
    )
    stop, restore = cleanup["stop"], cleanup["restore"]
    _keys(
        stop, "run observedAtMs enabled revision acknowledged independentReadback", "invalid_stop"
    )
    _require(
        stop["run"] == run
        and stop["enabled"] is False
        and _integer(stop["revision"], 2)
        and stop["revision"] == baseline["admissionRevision"] + 1
        and stop["acknowledged"] is True
        and stop["independentReadback"] is True
        and _integer(stop["observedAtMs"]),
        "admission_off_unconfirmed",
    )
    _keys(
        restore,
        "run target force latched acknowledged independentReadback observedAtMs",
        "invalid_restore",
    )
    _require(
        restore["run"] == run
        and restore["target"] == baseline["continuity"]["retainedVersion"]
        and restore["force"] is False
        and all(restore[key] is True for key in ("latched", "acknowledged", "independentReadback"))
        and _integer(restore["observedAtMs"]),
        "exact_restore_unconfirmed",
    )
    _require(
        refreshed["observedAtMs"]
        <= stop["observedAtMs"]
        < restore["observedAtMs"]
        <= restored["observedAtMs"],
        "cleanup_order_mismatch",
    )
    _require(
        _integer(cleanup["completedAtMs"])
        and restored["observedAtMs"] <= cleanup["completedAtMs"] <= now_ms,
        "cleanup_time_mismatch",
    )
    _require(
        type(cleanup["resources"]) is list
        and len(cleanup["resources"]) == len(RESOURCE_KINDS)
        and type(cleanup["local"]) is list
        and len(cleanup["local"]) == len(LOCAL_KINDS),
        "cleanup_inventory_mismatch",
    )
    expected = baseline["ownedResources"] + [
        {"kind": kind, "identity": "synthetic-" + kind + "-" + run, "run": run}
        for kind in LOCAL_KINDS
    ]
    for receipt, resource in zip(cleanup["resources"] + cleanup["local"], expected, strict=True):
        _keys(
            receipt,
            "kind identity run createdAcknowledged operationLatched deleteAcknowledged "
            "absentVerified observedAtMs",
            "invalid_cleanup_receipt",
        )
        _require(
            all(receipt[key] == resource[key] for key in ("kind", "identity", "run"))
            and all(
                receipt[key] is True
                for key in (
                    "createdAcknowledged",
                    "operationLatched",
                    "deleteAcknowledged",
                    "absentVerified",
                )
            ),
            "cleanup_absence_unconfirmed",
        )
        _require(
            _integer(receipt["observedAtMs"])
            and restored["observedAtMs"] <= receipt["observedAtMs"] <= cleanup["completedAtMs"],
            "cleanup_order_mismatch",
        )
    result = {
        "schemaVersion": 1,
        "kind": "synthetic_offline_preservation_contract",
        "comparisonPassed": True,
        "cleanupEvidenceComplete": True,
        "evidenceSha256": hashlib.sha256(
            _json([baseline, refreshed, restored, cleanup])
        ).hexdigest(),
        "currentProductionStateVerified": False,
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "authenticatedOrdinaryRoutesVerified": False,
        "deploymentAllowed": False,
        "missingSourceSeams": list(MISSING_SOURCE_SEAMS),
    }
    if profile_manifest is not None:
        result.update(
            schemaVersion=2,
            kind="synthetic_offline_application_state_preservation_contract",
            profileBinding=baseline["profileBinding"],
            wholeProviderContentsEqualityVerified=False,
        )
    return result


def synthetic_example() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Closed sample for tests only, not a captured production baseline."""
    run = "a" * 32
    start = 1_000_000
    digest = hashlib.sha256(b"synthetic-only").hexdigest()
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(
            "CREATE TABLE flickr_write_gates("
            "scope TEXT,scope_id TEXT,enabled INTEGER,revision INTEGER);"
            "INSERT INTO flickr_write_gates VALUES"
            "('deployment','*',0,7),('user','synthetic-user',0,11);"
            "CREATE TABLE synthetic_facts(id TEXT PRIMARY KEY,body BLOB);"
            "INSERT INTO synthetic_facts VALUES('synthetic-fact',X'001122');"
        )
        snapshot = capture_sqlite(
            db, run=run, database="synthetic-production-db", observed_at_ms=start
        )
    finally:
        db.close()
    resources = [
        {"kind": kind, "identity": "synthetic-" + kind + "-" + run, "run": run}
        for kind in RESOURCE_KINDS
    ]
    baseline = {
        "mode": "synthetic-offline",
        "run": run,
        "observedAtMs": start,
        "expiresAtMs": start + LIFETIME_MS,
        "admissionRevision": 1,
        "captureIndexSha256": INDEX_SHA256,
        "moduleSha256": MODULE_SHA256,
        "inventory": {name: digest for name in sorted(FILES)},
        "continuity": {
            "retainedVersion": "synthetic-retained-version",
            "weights": {"synthetic-retained-version": 100},
            "bindingsSha256": digest,
            "runtimeSha256": digest,
            "edgeSha256": digest,
            "d1Identity": "synthetic-production-db",
            "doLifecycleSha256": digest,
            "assetsSha256": digest,
            "secretReferencesSha256": digest,
            "capabilities": {"intake": False, "dispatch": False, "thumbnail": False},
            "backgroundQuiescenceSha256": digest,
        },
        "gates": [
            {"scope": "deployment", "scope_id": "*", "enabled": 0, "revision": 7},
            {"scope": "user", "scope_id": "synthetic-user", "enabled": 0, "revision": 11},
        ],
        "database": snapshot,
        "ordinaryReads": [
            {
                "check": check,
                "run": run,
                "moduleSha256": MODULE_SHA256,
                "status": status,
                "boundedNoData": True,
                "noMutation": True,
                "noUpstream": True,
            }
            for check, status in zip(READ_CHECKS, (401, 404, 404), strict=True)
        ],
        "ownedResources": resources,
    }
    refreshed, restored = copy.deepcopy(baseline), copy.deepcopy(baseline)
    for offset, value in ((100, refreshed), (400, restored)):
        value["observedAtMs"] = value["database"]["observedAtMs"] = start + offset
    cleanup = {
        "mode": "synthetic-offline",
        "run": run,
        "completedAtMs": start + 600,
        "stop": {
            "run": run,
            "observedAtMs": start + 200,
            "enabled": False,
            "revision": 2,
            "acknowledged": True,
            "independentReadback": True,
        },
        "restore": {
            "run": run,
            "target": "synthetic-retained-version",
            "force": False,
            "latched": True,
            "acknowledged": True,
            "independentReadback": True,
            "observedAtMs": start + 300,
        },
    }
    for key, identities in (
        ("resources", resources),
        (
            "local",
            [
                {"kind": kind, "identity": "synthetic-" + kind + "-" + run, "run": run}
                for kind in LOCAL_KINDS
            ],
        ),
    ):
        cleanup[key] = [
            {
                **identity,
                "createdAcknowledged": True,
                "operationLatched": True,
                "deleteAcknowledged": True,
                "absentVerified": True,
                "observedAtMs": start + 500,
            }
            for identity in identities
        ]
    return baseline, refreshed, restored, cleanup


def main() -> int:
    print("fixed_origin_preservation_disabled: synthetic offline contract only")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
