"""Exact current-schema archives for quiescent, isolated databases.

This codec does not mutate a database or access native-secret/input-file values.
Archives contain private authentication state, including CSRF values, and must
stay outside Git and logs. Stop all source writers and restore only to a new,
unexposed target. Older-backup
reconciliation and native-secret generation checks remain separate release gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.foundation_probe import sql_literal

ROOT = Path(__file__).resolve().parent.parent
Query = Callable[[str], list[dict[str, Any]]]
SCHEMA_SQL = (
    "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL "
    "AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
)


@dataclass(frozen=True)
class SchemaContract:
    migration_head: str
    migration_sha2_256: str
    objects: list[dict[str, Any]]
    tables: dict[str, list[str]]


@dataclass(frozen=True)
class Archive:
    migration_head: str
    migration_sha2_256: str
    objects: list[dict[str, Any]]
    rows: dict[str, list[str]]

    def sql(self) -> str:
        ddl = [
            str(row["sql"]) + ";"
            for kind in ("table", "index", "view")
            for row in self.objects
            if row["type"] == kind
        ]
        inserts = [line for table in sorted(self.rows) for line in self.rows[table]]
        triggers = [str(row["sql"]) + ";" for row in self.objects if row["type"] == "trigger"]
        # Historical rows load before allocation/audit triggers are reinstated.
        return "\n".join(["PRAGMA defer_foreign_keys=ON;", *ddl, *inserts, *triggers, ""])

    def summary(self) -> dict[str, Any]:
        return {
            "migrationHead": self.migration_head,
            "migrationSha2_256": self.migration_sha2_256,
            "archiveSha2_256": hashlib.sha256(self.sql().encode("utf-8")).hexdigest(),
            "tableCount": len(self.rows),
            "rowCounts": {name: len(rows) for name, rows in self.rows.items()},
        }


def query_connection(connection: sqlite3.Connection) -> Query:
    def query(sql: str) -> list[dict[str, Any]]:
        cursor = connection.execute(sql)
        names = [column[0] for column in cursor.description or []]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    return query


def schema_contract(migrations: Path = ROOT / "migrations") -> SchemaContract:
    files = sorted(migrations.glob("*.sql"))
    if not files:
        raise ValueError("No production migrations")
    digest = hashlib.sha256()
    # This connection discovers schema only; behavioral restore tests use files.
    connection = sqlite3.connect(":memory:")
    try:
        for path in files:
            source = path.read_bytes()
            digest.update(path.name.encode("utf-8") + b"\0" + source + b"\0")
            connection.executescript(source.decode("utf-8"))
        query = query_connection(connection)
        objects = query(SCHEMA_SQL)
        tables = {}
        for row in objects:
            if row["type"] != "table":
                continue
            name = row["name"]
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError("Unsupported migration table identifier")
            columns = query(f"PRAGMA table_xinfo({name})")
            tables[name] = [column["name"] for column in columns if column["hidden"] == 0]
        return SchemaContract(files[-1].name, digest.hexdigest(), objects, tables)
    finally:
        connection.close()


def normalized_sql(value: str) -> str:
    # Preserve quoted values and identifier case; normalize layout only.
    tokens = re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\S+", value)
    return " ".join(tokens).rstrip(";")


def object_map(objects: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    return {
        (row["type"], row["name"], row["tbl_name"]): normalized_sql(row["sql"]) for row in objects
    }


def capture(query: Query, contract: SchemaContract, *, source_stopped: bool) -> Archive:
    if not source_stopped:
        raise ValueError("Archive requires confirmed stopped writers")
    objects = query(SCHEMA_SQL)
    # _cf_KV is provider-owned; d1_migrations is retained verbatim when present.
    objects = [row for row in objects if row["tbl_name"] != "_cf_KV"]
    domain_objects = [row for row in objects if row["tbl_name"] != "d1_migrations"]
    if object_map(domain_objects) != object_map(contract.objects):
        raise ValueError("Schema drift: missing, extra or changed production objects")
    tables = dict(contract.tables)
    if any(row["name"] == "d1_migrations" and row["type"] == "table" for row in objects):
        tables["d1_migrations"] = [
            row["name"] for row in query("PRAGMA table_xinfo(d1_migrations)") if row["hidden"] == 0
        ]
    rows = {}
    for table, columns in sorted(tables.items()):
        # SQL constructs textual literals before JSON transport, preserving full
        # signed 64-bit integers, BLOBs and NUL-bearing text without float loss.
        expression = " || ',' || ".join(sql_literal(name) for name in columns)
        prefix = f"INSERT INTO {table}({','.join(columns)}) VALUES("
        statement = (
            "SELECT '"
            + prefix
            + "' || "
            + expression
            + " || ');' AS statement FROM "
            + table
            + " ORDER BY statement COLLATE BINARY"
        )
        rows[table] = [row["statement"] for row in query(statement)]
    return Archive(contract.migration_head, contract.migration_sha2_256, objects, rows)


def verify_restored(query: Query, expected: Archive, contract: SchemaContract) -> dict[str, Any]:
    if expected.migration_sha2_256 != contract.migration_sha2_256:
        raise ValueError("Archive is not from the selected migration head")
    actual = capture(query, contract, source_stopped=True)
    if actual.rows != expected.rows or object_map(actual.objects) != object_map(expected.objects):
        raise ValueError("Restored rows or schema do not match the exact archive")
    if query("PRAGMA foreign_key_check"):
        raise ValueError("Restored foreign keys are invalid")
    result = query("PRAGMA integrity_check")
    if len(result) != 1 or list(result[0].values()) != ["ok"]:
        raise ValueError("Restored integrity check failed")
    return actual.summary()


if __name__ == "__main__":
    contract = schema_contract()
    print(
        json.dumps(
            {
                "migrationHead": contract.migration_head,
                "migrationSha2_256": contract.migration_sha2_256,
                "tableCount": len(contract.tables),
            },
            indent=2,
        )
    )
