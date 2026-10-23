"""Bounded no-REAL DDL source for supplied, synthetic SQL schema metadata.

No discovery, installation, migration, or provider adapter is implemented here.
The caller owns reviewed input/pins, complete discovery and the writer embargo.
An AFTER guard observes actual NEW cells after affinity, including generated
columns. RAISE(ABORT) rolls back its complete statement; the transaction owner
must roll back the complete batch on any failure. No existing REAL is certified.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from scripts import private_d1_snapshot_codec as codec
from scripts.fixed_origin_preservation import Refused, _hash, _json

PROFILE = "pmb1-private-application-no-real-v1"
CONTRACT = "adr0065-no-real-sql-guards-v1"
ERROR = "pmb1_no_real"


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise Refused(category)


def manifest_sha256(manifest: Any) -> str:
    """A SHA2-256 pin, to retain separately in the reviewed candidate binding."""
    return hashlib.sha256(_json(manifest)).hexdigest()


def build_guard_manifest(
    schema_rows: Any, storage_rows: Any, columns_by_table: Any
) -> dict[str, Any]:
    """Build fixed text only; this does not authorize or perform installation.

    Inputs have the existing codec's exact schema/table_list/table_xinfo shapes.
    Every enumerated table must be guardable. There is no provider, bookkeeping
    or name-prefix exemption. SQLite-owned tables on which triggers cannot be
    created cause complete refusal, requiring a separately reviewed solution.
    """
    plan = codec.build_plan(schema_rows, storage_rows, columns_by_table)
    _require(bool(plan.tables), "no_real_empty_schema")
    # RAISE(IGNORE/FAIL) can preempt later guards without undoing the row write.
    # sqlite_schema does not bind trigger creation/execution order. Conservatively
    # refuse definitions containing both RAISE and either IGNORE or FAIL, including
    # harmless comments, literals and quoted names. ABORT/ROLLBACK remain supported.
    # No SQL parser or trigger-order assumption supplies authority here.
    _require(
        all(
            type(row["sql"]) is str
            and bool(row["sql"])
            and not (
                "raise" in row["sql"].casefold()
                and any(word in row["sql"].casefold() for word in ("ignore", "fail"))
            )
            for row in schema_rows
            if row["type"] == "trigger"
        ),
        "no_real_unsupported_base_trigger",
    )
    _require(
        all(not table.name.casefold().startswith("sqlite_") for table in plan.tables),
        "no_real_unguardable_table",
    )
    _require(
        len({table.name.casefold() for table in plan.tables}) == len(plan.tables)
        and all(row["sql"] for row in schema_rows if row["type"] == "table"),
        "no_real_unknown_table_definition",
    )
    # SnapshotPlanner already validates complete bounded metadata, generated
    # hidden=2/3, ordinary hidden rowid access and unsupported virtual/hidden=1.
    guards: list[dict[str, Any]] = []
    names = {row["name"].casefold() for row in schema_rows}
    coverage: dict[str, list[str]] = {}
    for table in plan.tables:
        cells = list(table.columns)
        if table.rowid_alias is not None:
            cells.append(table.rowid_alias)
        coverage[table.name] = cells
        predicate = " OR ".join(
            "typeof(NEW." + codec._identifier(cell) + ")='real'" for cell in cells
        )
        suffix = hashlib.sha256(table.name.encode("utf-8")).hexdigest()
        for event in ("INSERT", "UPDATE"):
            name = "pmb1_no_real_" + suffix + "_" + event.lower()
            _require(name.casefold() not in names, "no_real_guard_name_collision")
            names.add(name.casefold())
            sql = (
                "CREATE TRIGGER "
                + codec._identifier(name)
                + " AFTER "
                + event
                + " ON "
                + codec._identifier(table.name)
                + " WHEN "
                + predicate
                + " BEGIN SELECT RAISE(ABORT,'"
                + ERROR
                + "'); END"
            )
            guards.append({"name": name, "table": table.name, "event": event, "sql": sql})
    installed = copy.deepcopy(schema_rows) + [
        {"type": "trigger", "name": guard["name"], "tbl_name": guard["table"], "sql": guard["sql"]}
        for guard in guards
    ]
    installed.sort(key=lambda row: (row["type"], row["name"], row["tbl_name"]))
    codec.build_plan(installed, storage_rows, columns_by_table)
    manifest = {
        "profile": PROFILE,
        "contractRevision": CONTRACT,
        "baseSchema": copy.deepcopy(schema_rows),
        "schema": installed,
        "tableList": copy.deepcopy(storage_rows),
        "columns": copy.deepcopy(columns_by_table),
        "cells": coverage,
        "guards": guards,
    }
    _json(manifest)
    return manifest


def _validate_definition(manifest: Any, expected_manifest_sha256: str) -> None:
    _require(
        _hash(expected_manifest_sha256) and manifest_sha256(manifest) == expected_manifest_sha256,
        "no_real_manifest_pin_mismatch",
    )
    _require(
        type(manifest) is dict
        and set(manifest)
        == {
            "profile",
            "contractRevision",
            "baseSchema",
            "schema",
            "tableList",
            "columns",
            "cells",
            "guards",
        },
        "no_real_invalid_manifest",
    )
    expected = build_guard_manifest(
        manifest["baseSchema"], manifest["tableList"], manifest["columns"]
    )
    _require(_json(manifest) == _json(expected), "no_real_guard_definition_mismatch")


def validate_guard_manifest(
    manifest: Any,
    schema_rows: Any,
    storage_rows: Any,
    columns_by_table: Any,
    *,
    expected_manifest_sha256: str,
    query: codec.Query,
) -> None:
    """Compare exact installed metadata and compile bounded cell-access probes.

    The manifest pin must come from the separately reviewed candidate, not be
    derived from an untrusted incoming manifest. The caller supplies its approved
    read interface. Probes return no rows and do not certify contents, trigger
    behavior, a common closed interval, or managed-provider compatibility.
    """
    _validate_definition(manifest, expected_manifest_sha256)
    codec.build_plan(schema_rows, storage_rows, columns_by_table)
    _require(
        _json(schema_rows) == _json(manifest["schema"])
        and _json(storage_rows) == _json(manifest["tableList"])
        and _json(columns_by_table) == _json(manifest["columns"]),
        "no_real_schema_or_guard_drift",
    )
    for table, cells in manifest["cells"].items():
        sql = (
            "SELECT "
            + ",".join("typeof(" + codec._identifier(cell) + ")" for cell in cells)
            + " FROM main."
            + codec._identifier(table)
            + " LIMIT 0"
        )
        try:
            result = query(sql)
        except Exception:
            raise Refused("no_real_cell_access_unavailable") from None
        _require(type(result) is list and not result, "no_real_invalid_access_result")
