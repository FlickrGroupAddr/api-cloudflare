"""Finite in-memory SQLite fixture. No D1, network or filesystem database client."""

import json
import sqlite3
from pathlib import Path

from control import HERE, ControlReadback, parse_readback, read_sql, schema_pins

GUARD_BODY = """  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;"""


def schema_rows(db: sqlite3.Connection) -> list[dict[str, object]]:
    cursor = db.execute(read_sql("schema"))
    return [
        dict(zip([column[0] for column in cursor.description], row, strict=True))
        for row in cursor.fetchall()
    ]


def source_database(migrations: Path) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:", isolation_level=None)
    db.execute("PRAGMA foreign_keys=ON")
    for path in sorted(migrations.glob("*.sql")):
        db.executescript(path.read_text(encoding="utf-8"))
    return db


def guard_sql(tables: list[str]) -> str:
    statements: list[str] = ["-- INERT CANDIDATE ONLY. Enumerated public-source fixture tables.\n"]
    for table in tables:
        if not table.replace("_", "").isascii() or not table.replace("_", "").isalnum():
            raise ValueError("unsupported_fixture_identifier")
        for event in ("INSERT", "UPDATE", "DELETE"):
            name = f"pmb1_{table}_{event.lower()}"
            statements.append(
                f'CREATE TRIGGER "{name}" BEFORE {event} ON "{table}"\nBEGIN\n{GUARD_BODY}\nEND;\n'
            )
    return "\n".join(statements)


def bootstrap_fixture(db: sqlite3.Connection) -> None:
    # executescript commits any pending transaction: BEGIN is deliberately IN
    # the script. Rollback is explicit on failure, including late DDL failure.
    if db.in_transaction:
        raise ValueError("bootstrap_requires_idle_connection")
    pinned = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    if schema_pins(schema_rows(db)) != pinned["source_schema"]:
        raise ValueError("unexpected_source_schema")
    try:
        db.executescript(
            "BEGIN IMMEDIATE;\n"
            + read_sql("bootstrap")
            + "\n"
            + (HERE / "guards.sql").read_text(encoding="utf-8")
        )
        if schema_pins(schema_rows(db)) != pinned["candidate_schema"]:
            raise ValueError("candidate_schema_mismatch")
        cursor = db.execute(read_sql("readback"))
        names = [column[0] for column in cursor.description]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
        if parse_readback(rows) != ControlReadback("1", "closed"):
            raise ValueError("candidate_bootstrap_mismatch")
        db.commit()
    except sqlite3.Error, ValueError:
        if db.in_transaction:
            db.rollback()
        raise


def atomic_fixture_batch(db: sqlite3.Connection, statements: list[tuple[str, tuple]]) -> None:
    """Local synthetic analogue only; D1 batch semantics require actual proof."""
    if db.in_transaction:
        raise ValueError("batch_requires_idle_connection")
    db.execute("BEGIN IMMEDIATE")
    try:
        for sql, parameters in statements:
            db.execute(sql, parameters)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
