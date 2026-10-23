"""Read-only relational snapshot planner/decoder; no provider, files or SQL dumps.

Returned data is private, including authentication/session cells. This preserves
the schema/tables representation of fixed_origin_preservation.capture_sqlite;
it does not relabel that synthetic comparator as hosted evidence. The caller
owns exact query approval, bounded transport, source provenance and a continuous
all-writer barrier. Multiple SELECTs are not one transaction by themselves.

Integers are rendered by SQLite as decimal text before JSON transport. Text is
strict UTF-8 hex, BLOBs are hex and NULL stays distinct. REAL is deliberately
unsupported: neither SQL quote/printf nor JSON numbers establish lossless
binary64 (including negative zero) on the production D1 adapter. Any REAL or
unsupported/omitted application object makes the entire capture refuse. Only an
explicit reviewed ADR0064 manifest selects its narrowly scoped contents boundary;
the default remains strict and requires every enumerated table's contents.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from scripts.fixed_origin_preservation import (
    MAX_BYTES,
    MAX_ROWS,
    MAX_SCHEMA,
    MAX_TABLES,
    Refused,
    _json,
)

MAX_COLUMNS = 256
MAX_PAGE_ROWS = 256
MAX_QUERIES = MAX_ROWS + 3 * MAX_TABLES + 3
SCHEMA_SQL = (
    "SELECT type,name,tbl_name,sql FROM main.sqlite_schema "
    f"ORDER BY type,name,tbl_name LIMIT {MAX_SCHEMA + 1}"
)
TABLE_LIST_SQL = (
    'SELECT schema,name,type,ncol,wr,"strict" FROM pragma_table_list '
    f"WHERE schema='main' ORDER BY name LIMIT {MAX_SCHEMA + 1}"
)
# Behavioral SQLite CAST representation witness, not provider-reported PRAGMA metadata.
# CAST-to-BLOB uses the database connection encoding: UTF-8 'A' is exactly 41;
# UTF-16le/be are 4100/0041 and remain unsupported. Keep the actual query in provenance.
ENCODING_SQL = "SELECT hex(CAST('A' AS BLOB)) AS encoding_probe"
Query = Callable[[str], list[dict[str, Any]]]


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise Refused(category)


def _keys(value: Any, expected: tuple[str, ...], category: str) -> None:
    _require(type(value) is dict and set(value) == set(expected), category)


def _name(value: Any) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 4096
        and "\0" not in value
        and not any(0xD800 <= ord(char) <= 0xDFFF for char in value)
    )


def _text(value: Any) -> bool:
    return type(value) is str and not any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _identifier(value: str) -> str:
    _require(_name(value), "unsupported_identifier")
    return '"' + value.replace('"', '""') + '"'


def columns_sql(name: str) -> str:
    """A fixed metadata read, quoting the discovered name as a SQL value."""
    _require(_name(name), "unsupported_identifier")
    literal = "'" + name.replace("'", "''") + "'"
    return (
        'SELECT cid,name,type,"notnull",dflt_value,pk,hidden FROM pragma_table_xinfo('
        + literal
        + f") ORDER BY cid LIMIT {MAX_COLUMNS + 1}"
    )


@dataclass(frozen=True, repr=False)
class TablePlan:
    name: str
    columns: tuple[str, ...]
    rowid_alias: str | None
    key_columns: tuple[int, ...]


@dataclass(frozen=True, repr=False)
class SnapshotPlan:
    schema: tuple[tuple[Any, ...], ...]
    tables: tuple[TablePlan, ...]
    page_size: int
    profile_manifest: Any = None
    table_list: Any = None


def build_plan(
    schema_rows: Any,
    storage_rows: Any,
    columns_by_table: Any,
    *,
    page_size: int = MAX_PAGE_ROWS,
    profile_manifest: Any = None,
) -> SnapshotPlan:
    """Validate the complete actual census against the selected explicit profile.

    sqlite_schema itself is represented by its complete schema rows, as in the
    existing contract. Every table it names, including sqlite_sequence, stats,
    d1_migrations and provider-owned tables such as _cf_KV, must be read. A
    provider-denied table is a refusal under the default strict profile. An
    explicit ADR0064 manifest may exclude only exact main._cf_KV contents.
    """
    _require(type(page_size) is int and 1 <= page_size <= MAX_PAGE_ROWS, "invalid_page_size")
    _require(type(schema_rows) is list and len(schema_rows) <= MAX_SCHEMA, "schema_bound_exceeded")
    _require(
        type(storage_rows) is list and len(storage_rows) <= MAX_SCHEMA, "invalid_storage_census"
    )
    _require(type(columns_by_table) is dict, "invalid_column_census")
    _json([schema_rows, storage_rows, columns_by_table])
    schema_rows = cast(list[Any], schema_rows)
    storage_rows = cast(list[Any], storage_rows)
    columns_by_table = cast(dict[str, Any], columns_by_table)
    schema: list[tuple[Any, ...]] = []
    objects: set[tuple[str, str]] = set()
    table_names: list[str] = []
    view_names: list[str] = []
    for row in schema_rows:
        _keys(row, ("type", "name", "tbl_name", "sql"), "invalid_schema")
        kind, name, owner, sql = (row[key] for key in ("type", "name", "tbl_name", "sql"))
        _require(
            kind in ("table", "index", "view", "trigger")
            and _name(name)
            and _name(owner)
            and (sql is None or _text(sql)),
            "invalid_schema",
        )
        _require((kind, name) not in objects, "duplicate_schema_object")
        objects.add((kind, name))
        schema.append((kind, name, owner, sql))
        if kind == "table":
            _require(name == owner, "invalid_table_identity")
            table_names.append(name)
        elif kind == "view":
            view_names.append(name)
    _require(schema == sorted(schema, key=lambda row: row[:3]), "noncanonical_schema_census")
    table_names.sort()
    _require(len(table_names) <= MAX_TABLES, "table_bound_exceeded")
    excluded: set[str] = set()
    if profile_manifest is not None:
        from scripts.private_d1_snapshot_profile import EXCLUDED, validate_manifest

        validate_manifest(profile_manifest, schema_rows, storage_rows)
        excluded = {EXCLUDED}
    _require(set(columns_by_table) == set(table_names) - excluded, "column_census_mismatch")
    storage: dict[str, dict[str, Any]] = {}
    for row in storage_rows:
        _keys(row, ("schema", "name", "type", "ncol", "wr", "strict"), "invalid_storage_census")
        _require(
            row["schema"] == "main"
            and _name(row["name"])
            and row["type"] in ("table", "view", "virtual", "shadow")
            and type(row["ncol"]) is int
            and 0 < row["ncol"] <= MAX_COLUMNS
            and type(row["wr"]) is int
            and row["wr"] in (0, 1)
            and type(row["strict"]) is int
            and row["strict"] in (0, 1),
            "invalid_storage_census",
        )
        _require(row["type"] not in ("virtual", "shadow"), "virtual_table_not_supported")
        _require(row["name"] not in storage, "duplicate_storage_object")
        storage[row["name"]] = row
    _require(
        set(storage) == set(table_names) | set(view_names) | {"sqlite_schema"},
        "schema_storage_census_mismatch",
    )
    _require(storage["sqlite_schema"]["type"] == "table", "invalid_schema_storage")
    _require(all(storage[name]["type"] == "view" for name in view_names), "invalid_view_storage")
    tables: list[TablePlan] = []
    for name in table_names:
        info = storage[name]
        _require(info["type"] == "table", "unsupported_table_storage")
        if name in excluded:
            continue
        columns = columns_by_table[name]
        _require(
            type(columns) is list and 0 < len(columns) <= MAX_COLUMNS,
            "column_bound_exceeded",
        )
        _require(len(columns) == info["ncol"], "column_census_mismatch")
        names: list[str] = []
        primary: dict[int, int] = {}
        for index, column in enumerate(columns):
            _keys(
                column,
                ("cid", "name", "type", "notnull", "dflt_value", "pk", "hidden"),
                "invalid_column_metadata",
            )
            _require(
                type(column["cid"]) is int
                and column["cid"] == index
                and _name(column["name"])
                and _text(column["type"])
                and type(column["notnull"]) is int
                and column["notnull"] in (0, 1)
                and (column["dflt_value"] is None or _text(column["dflt_value"]))
                and type(column["pk"]) is int
                and 0 <= column["pk"] <= len(columns)
                and type(column["hidden"]) is int
                and column["hidden"] in (0, 2, 3),
                "unsupported_column_metadata",
            )
            names.append(column["name"])
            if column["pk"]:
                _require(column["pk"] not in primary, "invalid_primary_key")
                primary[column["pk"]] = index
        _require(len(set(names)) == len(names), "duplicate_column")
        aliases = [
            alias
            for alias in ("rowid", "_rowid_", "oid")
            if alias not in {n.lower() for n in names}
        ]
        if info["wr"] == 0:
            _require(bool(aliases), "hidden_rowid_inaccessible")
            rowid_alias = aliases[0]
            keys: tuple[int, ...] = ()
        else:
            _require(
                bool(primary) and set(primary) == set(range(1, len(primary) + 1)),
                "without_rowid_key_unknown",
            )
            rowid_alias = None
            keys = tuple(primary[key] for key in sorted(primary))
        tables.append(TablePlan(name, tuple(names), rowid_alias, keys))
    return SnapshotPlan(tuple(schema), tuple(tables), page_size, profile_manifest, storage_rows)


def count_sql(table: TablePlan) -> str:
    return "SELECT CAST(count(*) AS TEXT) AS row_count FROM main." + _identifier(table.name)


def _decimal(value: Any) -> int:
    _require(
        type(value) is str and re.fullmatch(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)", value) is not None,
        "invalid_integer_wire_value",
    )
    _require(len(value) <= 20, "invalid_integer_wire_value")
    number = int(value)
    _require(-(2**63) <= number < 2**63, "integer_range_exceeded")
    return number


def decode_count(rows: Any) -> int:
    _require(type(rows) is list and len(rows) == 1, "invalid_row_count")
    rows = cast(list[Any], rows)
    _keys(rows[0], ("row_count",), "invalid_row_count")
    count = _decimal(rows[0]["row_count"])
    _require(0 <= count <= MAX_ROWS, "row_bound_exceeded")
    return count


def table_page_sql(table: TablePlan, offset: int, limit: int) -> str:
    _require(type(offset) is int and 0 <= offset <= MAX_ROWS, "invalid_page_offset")
    _require(type(limit) is int and 1 <= limit <= MAX_PAGE_ROWS, "invalid_page_limit")
    expressions = []
    if table.rowid_alias is not None:
        expressions.append("CAST(" + _identifier(table.rowid_alias) + " AS TEXT) AS row_identity")
    for index, name in enumerate(table.columns):
        column = _identifier(name)
        expressions.extend(
            (
                f"typeof({column}) AS c{index}_type",
                f"CASE typeof({column}) WHEN 'integer' THEN CAST({column} AS TEXT) "
                f"WHEN 'text' THEN hex(CAST({column} AS BLOB)) "
                f"WHEN 'blob' THEN hex({column}) ELSE NULL END AS c{index}_value",
            )
        )
    if table.rowid_alias is not None:
        order = _identifier(table.rowid_alias)
    else:
        order = ",".join(
            _identifier(table.columns[key]) + " COLLATE BINARY" for key in table.key_columns
        )
    return (
        "SELECT "
        + ",".join(expressions)
        + " FROM main."
        + _identifier(table.name)
        + " ORDER BY "
        + order
        + f" LIMIT {limit} OFFSET {offset}"
    )


def _decode_cell(tag: Any, value: Any) -> list[Any]:
    if tag == "null":
        _require(value is None, "invalid_null_wire_value")
        return ["null", None]
    if tag == "integer":
        return ["integer", _decimal(value)]
    if tag == "real":
        raise Refused("lossless_real_transport_unqualified")
    _require(tag in ("text", "blob"), "unsupported_sqlite_value")
    _require(
        type(value) is str
        and len(value) <= MAX_BYTES * 2
        and re.fullmatch(r"(?:[0-9A-F]{2})*", value) is not None,
        "invalid_hex_wire_value",
    )
    raw = bytes.fromhex(value)
    if tag == "blob":
        return ["blob", raw.hex()]
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise Refused("unsupported_text_encoding") from None
    return ["text", text]


def decode_table_page(table: TablePlan, rows: Any) -> list[tuple[list[Any], int | None]]:
    _require(type(rows) is list and len(rows) <= MAX_PAGE_ROWS, "page_bound_exceeded")
    rows = cast(list[Any], rows)
    _json(rows)
    expected = tuple(
        key for index in range(len(table.columns)) for key in (f"c{index}_type", f"c{index}_value")
    ) + (("row_identity",) if table.rowid_alias is not None else ())
    decoded = []
    for row in rows:
        _keys(row, expected, "invalid_wire_row")
        identity = _decimal(row["row_identity"]) if table.rowid_alias is not None else None
        cells = [
            _decode_cell(row[f"c{index}_type"], row[f"c{index}_value"])
            for index in range(len(table.columns))
        ]
        decoded.append((cells, identity))
    return decoded


def assemble_snapshot(plan: SnapshotPlan, pages: Any, counts: Any) -> dict[str, Any]:
    """Require all exact-sized pages and an empty terminal sentinel per table."""
    names = {table.name for table in plan.tables}
    _require(type(pages) is dict and set(pages) == names, "incomplete_table_pages")
    _require(type(counts) is dict and set(counts) == names, "incomplete_table_counts")
    pages = cast(dict[str, Any], pages)
    counts = cast(dict[str, Any], counts)
    total = 0
    tables = {}
    for table in plan.tables:
        count = counts[table.name]
        _require(type(count) is int and 0 <= count <= MAX_ROWS, "invalid_row_count")
        total += count
        _require(total <= MAX_ROWS, "row_bound_exceeded")
        table_pages = pages[table.name]
        expected_pages = (count + plan.page_size - 1) // plan.page_size
        _require(
            type(table_pages) is list and len(table_pages) == expected_pages + 1,
            "incomplete_table_pages",
        )
        decoded = []
        for index, page in enumerate(table_pages):
            expected = (
                min(plan.page_size, count - index * plan.page_size) if index < expected_pages else 0
            )
            _require(type(page) is list and len(page) == expected, "incomplete_table_page")
            decoded.extend(decode_table_page(table, page))
        if table.rowid_alias is not None:
            identities = [identity for _, identity in decoded]
            _require(
                all(type(identity) is int for identity in identities)
                and identities == sorted(identities)
                and len(set(identities)) == len(identities),
                "invalid_hidden_rowids",
            )
            canonical = sorted(decoded, key=_json)
            rows = [row for row, _ in canonical]
            rowids = [identity for _, identity in canonical]
        else:
            keys = [_json([row[key] for key in table.key_columns]) for row, _ in decoded]
            _require(len(keys) == len(set(keys)), "duplicate_without_rowid_key")
            _require(
                all(row[key][0] != "null" for row, _ in decoded for key in table.key_columns),
                "invalid_without_rowid_key",
            )
            rows = sorted((row for row, _ in decoded), key=_json)
            rowids = None
        tables[table.name] = {"columns": list(table.columns), "rows": rows, "rowids": rowids}
        _json(tables)
    result = {"schema": [list(row) for row in plan.schema], "tables": tables}
    if plan.profile_manifest is not None:
        result["profileManifest"] = plan.profile_manifest
        result["tableList"] = plan.table_list
    _json(result)
    return result


def collect_snapshot(
    query: Query, *, page_size: int = MAX_PAGE_ROWS, profile_manifest: Any = None
) -> dict[str, Any]:
    """Issue only generated SELECTs through a caller-owned, bounded query seam.

    This function neither opens a connection nor returns provider diagnostics.
    The callback MUST reject response truncation and bound request/response/time
    before allocation; this codec also bounds aggregate serialized response bytes.
    It must bind every actual SQL request to the separately approved exact plan.
    """
    wire_bytes = 0
    query_count = 0
    queries: list[str] = []
    if profile_manifest is not None:
        profile_manifest = copy.deepcopy(profile_manifest)

    def read(sql: str) -> list[dict[str, Any]]:
        nonlocal wire_bytes, query_count
        query_count += 1
        queries.append(sql)
        _require(query_count <= MAX_QUERIES, "query_bound_exceeded")
        try:
            rows = query(sql)
        except Exception:
            raise Refused("snapshot_query_failed") from None
        _require(type(rows) is list, "invalid_query_response")
        wire_bytes += len(_json(rows))
        _require(wire_bytes <= MAX_BYTES, "evidence_bound_exceeded")
        return rows

    schema = read(SCHEMA_SQL)
    storage = read(TABLE_LIST_SQL)
    encoding = read(ENCODING_SQL)
    _require(encoding == [{"encoding_probe": "41"}], "unsupported_database_text_encoding")
    _require(type(schema) is list and len(schema) <= MAX_SCHEMA, "schema_bound_exceeded")
    names = []
    for row in schema:
        _keys(row, ("type", "name", "tbl_name", "sql"), "invalid_schema")
        if row["type"] == "table":
            _require(_name(row["name"]), "unsupported_identifier")
            names.append(row["name"])
    _require(len(names) <= MAX_TABLES and len(set(names)) == len(names), "invalid_table_census")
    if profile_manifest is not None:
        from scripts.private_d1_snapshot_profile import EXCLUDED, validate_manifest

        validate_manifest(profile_manifest, schema, storage)
        names.remove(EXCLUDED)
    columns = {name: read(columns_sql(name)) for name in sorted(names)}
    plan = build_plan(
        schema, storage, columns, page_size=page_size, profile_manifest=profile_manifest
    )
    if profile_manifest is not None:
        from scripts.private_d1_snapshot_profile import validate_guards

        validate_guards(profile_manifest, schema, storage, columns, read)
    pages = {}
    counts = {}
    total = 0
    for table in plan.tables:
        count = decode_count(read(count_sql(table)))
        total += count
        _require(total <= MAX_ROWS, "row_bound_exceeded")
        counts[table.name] = count
        pages[table.name] = [
            read(table_page_sql(table, offset, plan.page_size))
            for offset in range(0, count, plan.page_size)
        ]
        pages[table.name].append(read(table_page_sql(table, count, 1)))
    result = assemble_snapshot(plan, pages, counts)
    if profile_manifest is not None:
        from scripts.private_d1_snapshot_profile import binding, sources, validate_snapshot

        provenance = {
            "sourceSha256": sources(profile_manifest["profile"]),
            "queries": queries,
            "pageSize": page_size,
            "columns": columns,
        }
        result["provenance"] = provenance
        result["profileBinding"] = binding(profile_manifest, provenance)
        validate_snapshot(result, profile_manifest)
    _json(result)
    return result
