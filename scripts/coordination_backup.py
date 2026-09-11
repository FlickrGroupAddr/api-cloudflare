"""Exact scoped SQL archives for admission/scheduling migrations, on quiescent fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import runtime_permissions_probe as runtime
    from .foundation_probe import sql_literal
except ImportError:
    import runtime_permissions_probe as runtime
    from foundation_probe import sql_literal

TABLES = {
    "d1_migrations": "id",
    "fga_users": "user_id",
    "installations": "installation_id",
    "installation_credential_versions": "installation_id,ordinal",
    "flickr_links": "user_id",
    "photo_bindings": "binding_id",
    "flickr_write_gates": "scope,scope_id",
    "group_partitions": "partition_id",
    "submission_intents": "partition_id,enqueue_ordinal",
    "submission_blocks": "photo_id,group_id",
    "audit_events": "event_id",
    "submission_intent_events": "event_id",
    "partition_lease_events": "event_id",
    "transaction_guards": "transaction_id",
    "submission_attempts": "intent_id,ordinal",
    "attempt_membership": "attempt_id",
    "attempt_preflights": "attempt_id",
    "attempt_dispatches": "attempt_id",
    "attempt_resolutions": "attempt_id",
}


def query(run: runtime.Run, stage: str, sql: str) -> list[dict[str, Any]]:
    runtime.checked_resource_names(run)
    result = runtime.wrangler(
        run,
        stage,
        "d1",
        "execute",
        run.state["databaseName"],
        "--remote",
        "--command",
        sql,
        "--json",
    )
    return json.loads(result.stdout)[-1]["results"]


def schema(run: runtime.Run, stage: str) -> list[dict[str, Any]]:
    names = ",".join("'" + name + "'" for name in TABLES)
    return query(
        run,
        stage,
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL "
        f"AND tbl_name IN ({names}) AND name<>'probe_intent_failure' ORDER BY type,name;",
    )


def literal_rows(run: runtime.Run, label: str) -> dict[str, list[str]]:
    result = {}
    for table, order in TABLES.items():
        columns = query(run, f"{label}-columns-{table}", f"PRAGMA table_xinfo({table});")
        names = [row["name"] for row in columns if row["hidden"] == 0]
        if not names:
            raise runtime.ProbeError("A required archive table is missing.")
        expression = " || ',' || ".join(sql_literal(name) for name in names)
        sql = (
            f"SELECT 'INSERT INTO {table}({','.join(names)}) VALUES(' || "
            f"{expression} || ');' AS statement FROM {table} ORDER BY {order};"
        )
        result[table] = [row["statement"] for row in query(run, f"{label}-rows-{table}", sql)]
    return result


def archive_text(objects: list[dict[str, Any]], rows: dict[str, list[str]]) -> str:
    # SQLite dump ordering: create relations/indexes, load historical data, then
    # install triggers. Enqueue triggers must not allocate new ordinals/events
    # while restoring already committed ordinals and history into an empty DB.
    ddl = [
        str(row["sql"]) + ";"
        for kind in ("table", "index")
        for row in objects
        if row["type"] == kind
    ]
    triggers = [str(row["sql"]) + ";" for row in objects if row["type"] == "trigger"]
    inserts = [line for table in TABLES for line in rows[table]]
    return "\n".join(["PRAGMA defer_foreign_keys=ON;", *ddl, *inserts, *triggers, ""])


def restore_probe(source: runtime.Run, target: runtime.Run) -> dict[str, bool]:
    if not source.state.get("workerDeleted") or target.state.get("workerAttempted"):
        raise runtime.ProbeError("Archive requires stopped source and unexposed empty target.")
    before_schema = schema(source, "archive-source-schema")
    before = literal_rows(source, "archive-source")
    path: Path = source.directory / "coordination-archive.sql"
    path.write_text(archive_text(before_schema, before), encoding="utf-8", newline="\n")
    runtime.wrangler(
        target,
        "archive-import",
        "d1",
        "execute",
        target.state["databaseName"],
        "--remote",
        "--file",
        str(path),
        "--yes",
        "--json",
    )
    after = literal_rows(target, "archive-restored")
    after_schema = schema(target, "archive-restored-schema")
    protected = runtime.wrangler(
        target,
        "archive-protected-write",
        "d1",
        "execute",
        target.state["databaseName"],
        "--remote",
        "--command",
        "DELETE FROM submission_intent_events;",
        "--json",
        allow_failure=True,
    )
    return {
        "all_domain_rows_exact": before == after,
        "all_schema_guards_restored": before_schema == after_schema,
        "foreign_keys_valid": query(target, "archive-foreign-keys", "PRAGMA foreign_key_check;")
        == [],
        "history_guard_active": protected.returncode != 0,
    }
