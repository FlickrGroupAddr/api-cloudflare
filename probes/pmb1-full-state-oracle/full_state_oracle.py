"""Independent synthetic persisted-state reference; no candidate codec imports.

Expected REALs are direct SQLite-binding binary64 bytes, not candidate decimal or
hex text. The caller supplies only a newly created synthetic fixture connection.
No provider, filesystem reader, production adapter, registration or CLI exists.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Any, cast

MAX_ROWS = 10_000
MAX_BYTES = 4 * 1024 * 1024


class OracleRefused(ValueError):
    """Closed diagnostic; never interpolate schema or cell contents."""


def require(condition: bool, label: str) -> None:
    if not condition:
        raise OracleRefused(label)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    # Identity and cells remain paired; Counter comparisons retain multiplicity.
    rows: tuple[tuple[int | None, tuple[tuple[str, Any], ...]], ...]
    has_rowid: bool


@dataclass(frozen=True)
class Reference:
    schema: tuple[tuple[Any, ...], ...]
    tables: dict[str, Table]


def persisted_cell(tag: str, value: Any) -> tuple[str, Any]:
    """Use actual same-statement typeof, checking binding type independently."""
    expected = {"null": type(None), "integer": int, "real": float, "text": str, "blob": bytes}
    require(tag in expected and type(value) is expected[tag], "binding_type_mismatch")
    if tag == "real":
        require(math.isfinite(value), "nonfinite_reference")
        return tag, struct.pack(">d", value)
    if tag == "integer":
        require(-(2**63) <= value < 2**63, "integer_range")
    if tag == "text":
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise OracleRefused("invalid_reference_text") from None
    return tag, value


def read_reference(connection: sqlite3.Connection) -> Reference:
    """Independent direct read of a caller-owned synthetic persisted database.

    Requires default bindings/factories and no existing transaction. The test
    fixture owner closes the writer and reopens read-only before supplying this
    connection. This function neither opens a path nor authenticates provenance.
    """
    require(not connection.in_transaction, "active_reference_transaction")
    require(connection.row_factory is None and connection.text_factory is str, "binding_settings")
    used = 0
    instructions = 0

    def progress() -> int:
        nonlocal instructions
        instructions += 1
        return int(instructions > 10_000)

    def charge(value: Any) -> None:
        nonlocal used
        # Independent conservative accounting, also counts raw binary payloads.
        used += len(repr(value).encode("utf-8"))
        require(used <= MAX_BYTES, "reference_byte_bound")

    old_limit = connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_BYTES)
    connection.set_progress_handler(progress, 1000)
    try:
        connection.execute("BEGIN")
        require(connection.execute("PRAGMA encoding").fetchone() == ("UTF-8",), "encoding")
        schema = tuple(
            connection.execute(
                "SELECT type,name,tbl_name,sql FROM main.sqlite_schema "
                "ORDER BY type,name,tbl_name LIMIT 2049"
            )
        )
        require(len(schema) <= 2048, "reference_schema_bound")
        charge(schema)
        storage = {r[1]: (r[2], r[4]) for r in connection.execute("PRAGMA main.table_list")}
        require(
            all(kind not in ("virtual", "shadow") for kind, _ in storage.values()),
            "unsupported_storage",
        )
        names = [r[1] for r in schema if r[0] == "table"]
        require(len(names) <= 128, "reference_table_bound")
        tables: dict[str, Table] = {}
        count = 0
        for name in names:
            # xinfo supplies declared order, including generated columns.
            info = list(connection.execute("PRAGMA main.table_xinfo(" + quote(name) + ")"))
            require(0 < len(info) <= 256, "reference_column_bound")
            require(all(r[6] in (0, 2, 3) for r in info), "unsupported_hidden_column")
            columns = tuple(r[1] for r in info)
            has_rowid = storage[name][1] == 0
            aliases = [
                a for a in ("oid", "_rowid_", "rowid") if a not in {c.lower() for c in columns}
            ]
            require(not has_rowid or bool(aliases), "inaccessible_rowid")
            expressions = [quote(aliases[0])] if has_rowid else []
            for column in columns:
                expressions.extend(["typeof(" + quote(column) + ")", quote(column)])
            sql = "SELECT " + ",".join(expressions) + " FROM main." + quote(name)
            rows = []
            for row in connection.execute(sql):
                count += 1
                require(count <= MAX_ROWS, "reference_row_bound")
                identity = row[0] if has_rowid else None
                require(not has_rowid or type(identity) is int, "rowid_type")
                values = row[1:] if has_rowid else row
                cells = tuple(
                    persisted_cell(values[i], values[i + 1]) for i in range(0, len(values), 2)
                )
                record = (identity, cells)
                charge(record)
                rows.append(record)
            tables[name] = Table(columns, tuple(rows), has_rowid)
        return Reference(schema, tables)
    except sqlite3.Error, UnicodeError:
        raise OracleRefused("reference_read_failed") from None
    finally:
        try:
            connection.rollback()
        finally:
            connection.set_progress_handler(None, 0)
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_limit)


def observed_cell(cell: Any) -> tuple[str, Any]:
    """Translate only OBSERVED canonical cells to the reference's raw model."""
    require(type(cell) is list and len(cell) == 2, "observed_cell_shape")
    cell = cast(list[Any], cell)
    tag, value = cell
    require(type(tag) is str, "observed_tag")
    tag = cast(str, tag)
    if tag == "real":
        require(type(value) is str and len(value) <= 32, "observed_real")
        value = cast(str, value)
        require(
            re.fullmatch(r"-?0x(?:0\.[0-9a-f]{1,13}|1\.[0-9a-f]{13})p[+-][0-9]{1,4}", value)
            is not None,
            "observed_real",
        )
        try:
            parsed = float.fromhex(value)
        except ValueError, OverflowError:
            raise OracleRefused("observed_real") from None
        require(math.isfinite(parsed) and parsed.hex() == value, "observed_real")
        return tag, struct.pack(">d", parsed)
    if tag == "blob":
        require(
            type(value) is str and re.fullmatch(r"(?:[0-9a-f]{2})*", value) is not None,
            "observed_blob",
        )
        return tag, bytes.fromhex(cast(str, value))
    require(tag in ("null", "integer", "text"), "observed_tag")
    return persisted_cell(tag, value)


def check(reference: Reference, snapshot: Any) -> None:
    """Check full relational content only; no scope/barrier/hosted verdict.

    Snapshot envelope authority stays with its existing caller. Unknown table
    fields, noncanonical ordering, omissions and extra schema/rows fail here.
    """
    require(
        type(snapshot) is dict and "schema" in snapshot and "tables" in snapshot,
        "observed_snapshot",
    )
    schema, tables = snapshot["schema"], snapshot["tables"]
    require(type(schema) is list and all(type(r) is list for r in schema), "observed_schema")
    schema = cast(list[list[Any]], schema)
    require(tuple(tuple(r) for r in schema) == reference.schema, "schema_drift")
    require(type(tables) is dict and set(tables) == set(reference.tables), "table_census_drift")
    tables = cast(dict[str, Any], tables)
    for name, expected in reference.tables.items():
        actual = tables[name]
        require(
            type(actual) is dict and set(actual) == {"columns", "rows", "rowids"}, "observed_table"
        )
        actual = cast(dict[str, Any], actual)
        require(
            type(actual["columns"]) is list and tuple(actual["columns"]) == expected.columns,
            "column_order_drift",
        )
        rows, identities = actual["rows"], actual["rowids"]
        require(type(rows) is list and len(rows) == len(expected.rows), "row_count_drift")
        rows = cast(list[Any], rows)
        if expected.has_rowid:
            require(
                type(identities) is list
                and len(identities) == len(rows)
                and all(type(i) is int and -(2**63) <= i < 2**63 for i in identities)
                and len(set(identities)) == len(identities),
                "observed_rowids",
            )
            identities = cast(list[Any], identities)
        else:
            require(identities is None, "unexpected_rowids")
            identities = [None] * len(rows)
        records = []
        for identity, row in zip(identities, rows, strict=True):
            require(type(row) is list and len(row) == len(expected.columns), "observed_row")
            records.append((identity, tuple(observed_cell(c) for c in row)))
        require(Counter(records) == Counter(expected.rows), "typed_state_drift")
        # Canonical ordering is validated on observed data only. Expected state
        # does not use JSON, candidate assembly, float.hex(), or transport codecs.
        ordered = list(zip(rows, identities, strict=True)) if expected.has_rowid else rows
        require(
            ordered
            == sorted(
                ordered,
                key=lambda r: json.dumps(
                    r, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode(),
            ),
            "noncanonical_row_order",
        )
