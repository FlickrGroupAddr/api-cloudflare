"""Closed ADR0064 application-state boundary; no provider or file dispatch.

The manifest is private reviewed input, not evidence that a review occurred.
Its dependency attestations require independent review of the bound source and
migrations. Observable schema dependence additionally refuses here. No claim is
made about the inaccessible contents or their effect on provider behavior.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, cast

from scripts.fixed_origin_preservation import Refused, _hash, _json

PROFILE = "adr0064-private-d1-application-state-v1"
CONTRACT = "fixed-origin-preservation-2026-10-17/adr0064-v1"
NO_REAL_PROFILE = "pmb1-private-application-no-real-v1"
NO_REAL_CONTRACT = "adr0065-private-d1-application-no-real-v1"
DOCUMENTATION = "https://developers.cloudflare.com/d1/best-practices/import-export-data/"
EXCLUDED = "_cf_KV"
CONTENTS = {"observation": "unobserved", "freeze": "unfrozen", "verification": "unverified"}
SOURCE_FILES = (
    "private_d1_snapshot_profile.py",
    "private_d1_snapshot_codec.py",
    "fixed_origin_preservation.py",
)


def require(ok: bool, category: str) -> None:
    if not ok:
        raise Refused(category)


def sources(profile: str = PROFILE) -> dict[str, str]:
    root = Path(__file__).resolve().parent
    files = SOURCE_FILES + (("private_no_real_guards.py",) if profile == NO_REAL_PROFILE else ())
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}


def sha256(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def validate_manifest(manifest: Any, schema: Any, storage: Any) -> None:
    """Require exact reviewed identity/classification before any contents read."""
    no_real = type(manifest) is dict and manifest.get("profile") == NO_REAL_PROFILE
    extra = {"guardManifest", "guardManifestSha256"} if no_real else set()
    require(
        type(manifest) is dict
        and set(manifest)
        == {
            "profile",
            "contractRevision",
            "providerDocumentation",
            "schema",
            "tableList",
            "includedTables",
            "excluded",
            "dependencyReview",
            *extra,
        },
        "invalid_profile_manifest",
    )
    _json(manifest)
    require(
        manifest["profile"] == (NO_REAL_PROFILE if no_real else PROFILE)
        and manifest["contractRevision"] == (NO_REAL_CONTRACT if no_real else CONTRACT)
        and manifest["providerDocumentation"] == DOCUMENTATION,
        "profile_authority_mismatch",
    )
    require(
        _json(manifest["schema"]) == _json(schema)
        and _json(manifest["tableList"]) == _json(storage),
        "profile_census_mismatch",
    )
    require(type(schema) is list and type(storage) is list, "invalid_profile_census")
    schema = cast(list[dict[str, Any]], schema)
    storage = cast(list[dict[str, Any]], storage)
    # The codec validates every row's complete shape and rejects duplicates and
    # unsupported objects. This check also runs before column/content queries.
    require(
        all(type(row) is dict and set(row) == {"type", "name", "tbl_name", "sql"} for row in schema)
        and all(
            type(row) is dict and set(row) == {"schema", "name", "type", "ncol", "wr", "strict"}
            for row in storage
        ),
        "invalid_profile_census",
    )
    reserved = [row for row in schema if row["type"] == "table" and row["name"] == EXCLUDED]
    listed = [row for row in storage if row["name"] == EXCLUDED]
    require(
        len(reserved) == len(listed) == 1
        and reserved[0]["tbl_name"] == EXCLUDED
        and listed[0]["schema"] == "main"
        and listed[0]["type"] == "table",
        "profile_reserved_identity",
    )
    require(
        _json(manifest["excluded"])
        == _json({"schema": "main", "name": EXCLUDED, "kind": "table", "contents": CONTENTS}),
        "invalid_profile_exclusion",
    )
    names = [row["name"] for row in schema if row["type"] == "table"]
    require(
        all(type(name) is str for name in names)
        and manifest["includedTables"] == sorted(name for name in names if name != EXCLUDED),
        "profile_inclusion_mismatch",
    )
    # Conservative refusal, including quoted references, foreign keys and SQL
    # comments/literals: no SQL parser or authorizer bypass is introduced.
    for row in schema:
        if row is reserved[0]:
            continue
        require(
            row["tbl_name"] != EXCLUDED
            and (
                row["sql"] is None
                or (type(row["sql"]) is str and EXCLUDED.casefold() not in row["sql"].casefold())
            ),
            "profile_application_dependency",
        )
    review = manifest["dependencyReview"]
    require(
        type(review) is dict
        and set(review)
        == {
            "applicationDependsOnExcludedContents",
            "sourceSha256",
            "migrationsSha256",
            "observableSchemaSha256",
        }
        and review["applicationDependsOnExcludedContents"] is False
        and type(review["sourceSha256"]) is dict
        and bool(review["sourceSha256"])
        and all(
            type(name) is str and bool(name) and _hash(value)
            for name, value in review["sourceSha256"].items()
        )
        and _hash(review["migrationsSha256"])
        and review["observableSchemaSha256"] == sha256(schema),
        "profile_dependency_review_required",
    )
    if no_real:
        from scripts import private_no_real_guards as guards

        guard = manifest["guardManifest"]
        require(type(guard) is dict, "no_real_invalid_manifest")
        require(
            _hash(manifest["guardManifestSha256"])
            and guards.manifest_sha256(guard) == manifest["guardManifestSha256"],
            "no_real_manifest_pin_mismatch",
        )
        require({"baseSchema", "tableList", "columns"} <= set(guard), "no_real_invalid_manifest")
        expected = guards.build_guard_manifest(
            guard["baseSchema"], guard["tableList"], guard["columns"]
        )
        included_schema, included_storage = included_census(schema, storage)
        require(
            _json(guard) == _json(expected)
            and _json(included_schema) == _json(guard["schema"])
            and _json(included_storage) == _json(guard["tableList"]),
            "no_real_schema_or_guard_drift",
        )


def included_census(schema: Any, storage: Any) -> tuple[Any, Any]:
    """Project only the already manifest-qualified exact reserved table identity."""
    return (
        [row for row in schema if not (row["type"] == "table" and row["name"] == EXCLUDED)],
        [row for row in storage if row["name"] != EXCLUDED],
    )


def guard_queries(manifest: Any) -> list[str]:
    """Exact access-probe SQL from the bound #0237 guard cells, in manifest order."""
    from scripts.private_d1_snapshot_codec import _identifier

    if manifest["profile"] != NO_REAL_PROFILE:
        return []
    # JSON object member order is not authority: always use canonical table order.
    return [
        "SELECT "
        + ",".join("typeof(" + _identifier(cell) + ")" for cell in cells)
        + " FROM main."
        + _identifier(table)
        + " LIMIT 0"
        for table, cells in sorted(manifest["guardManifest"]["cells"].items())
    ]


def validate_guards(manifest: Any, schema: Any, storage: Any, columns: Any, query: Any) -> None:
    """Verify actual included metadata and every bounded access probe before rows."""
    if manifest["profile"] != NO_REAL_PROFILE:
        return
    from scripts import private_no_real_guards as guards

    included_schema, included_storage = included_census(schema, storage)
    # #0237 traverses its supplied cells mapping; normalize that order to match
    # the canonical query plan even after a JSON round trip sorted its keys.
    guard = dict(manifest["guardManifest"])
    guard["cells"] = dict(sorted(guard["cells"].items()))
    guards.validate_guard_manifest(
        guard,
        included_schema,
        included_storage,
        columns,
        expected_manifest_sha256=manifest["guardManifestSha256"],
        query=query,
    )


def binding(manifest: Any, provenance: Any) -> dict[str, Any]:
    require(
        type(provenance) is dict
        and set(provenance) == {"sourceSha256", "queries", "pageSize", "columns"}
        and provenance["sourceSha256"] == sources(manifest["profile"])
        and type(provenance["queries"]) is list
        and bool(provenance["queries"])
        and all(type(sql) is str and bool(sql) for sql in provenance["queries"]),
        "profile_provenance_mismatch",
    )
    return {
        "profile": manifest["profile"],
        "contractRevision": manifest["contractRevision"],
        "manifestSha256": sha256(manifest),
        "sourceSha256": sha256(provenance["sourceSha256"]),
        "queriesSha256": sha256(provenance["queries"]),
        "excludedContents": dict(CONTENTS),
    }


def validate_snapshot(snapshot: Any, manifest: Any) -> dict[str, Any]:
    """Validate the private census and the exact ordered generated query provenance."""
    from scripts import private_d1_snapshot_codec as codec

    if manifest["profile"] == NO_REAL_PROFILE:
        _json(snapshot)
    require(_json(snapshot["profileManifest"]) == _json(manifest), "profile_manifest_mismatch")
    schema = [
        dict(zip(("type", "name", "tbl_name", "sql"), row, strict=True))
        for row in snapshot["schema"]
    ]
    validate_manifest(manifest, schema, snapshot["tableList"])
    provenance = snapshot["provenance"]
    expected_binding = binding(manifest, provenance)
    require(
        _json(snapshot["profileBinding"]) == _json(expected_binding), "profile_binding_mismatch"
    )
    plan = codec.build_plan(
        schema,
        snapshot["tableList"],
        provenance["columns"],
        page_size=provenance["pageSize"],
        profile_manifest=manifest,
    )
    if manifest["profile"] == NO_REAL_PROFILE:
        require(
            _json(provenance["columns"]) == _json(manifest["guardManifest"]["columns"]),
            "no_real_schema_or_guard_drift",
        )
        require(
            type(snapshot["tables"]) is dict
            and set(snapshot["tables"]) == {table.name for table in plan.tables},
            "profile_table_census_mismatch",
        )
        for table in plan.tables:
            validate_no_real_table(table, snapshot["tables"][table.name])
        require(
            sum(len(data["rows"]) for data in snapshot["tables"].values()) <= codec.MAX_ROWS,
            "row_bound_exceeded",
        )
    require(
        set(snapshot["tables"]) == {table.name for table in plan.tables},
        "profile_table_census_mismatch",
    )
    queries = [codec.SCHEMA_SQL, codec.TABLE_LIST_SQL, codec.ENCODING_SQL]
    queries.extend(codec.columns_sql(table.name) for table in plan.tables)
    queries.extend(guard_queries(manifest))
    for table in plan.tables:
        data = snapshot["tables"][table.name]
        require(data["columns"] == list(table.columns), "profile_columns_mismatch")
        require(
            (data["rowids"] is None) == (table.rowid_alias is None), "profile_row_identity_mismatch"
        )
        if table.rowid_alias is None:
            keys = [codec._json([row[key] for key in table.key_columns]) for row in data["rows"]]
            require(
                len(keys) == len(set(keys))
                and all(row[key][0] != "null" for row in data["rows"] for key in table.key_columns),
                "profile_key_identity_mismatch",
            )
        count = len(data["rows"])
        queries.append(codec.count_sql(table))
        queries.extend(
            codec.table_page_sql(table, offset, plan.page_size)
            for offset in range(0, count, plan.page_size)
        )
        queries.append(codec.table_page_sql(table, count, 1))
    require(provenance["queries"] == queries, "profile_query_provenance_mismatch")
    return expected_binding


def validate_no_real_table(table: Any, data: Any) -> None:
    """Independently validate decoded typed state, including externally supplied snapshots."""
    from scripts import private_d1_snapshot_codec as codec

    require(type(data) is dict and set(data) == {"columns", "rows", "rowids"}, "invalid_table")
    require(data["columns"] == list(table.columns), "profile_columns_mismatch")
    rows, rowids = data["rows"], data["rowids"]
    require(type(rows) is list and len(rows) <= codec.MAX_ROWS, "row_bound_exceeded")
    rows = cast(list[Any], rows)
    for row in rows:
        require(type(row) is list and len(row) == len(table.columns), "invalid_row")
        row = cast(list[Any], row)
        for cell in row:
            require(type(cell) is list and len(cell) == 2, "invalid_cell")
            tag, value = cell
            require(type(tag) is str and tag in ("null", "integer", "text", "blob"), "invalid_cell")
            valid = (
                (tag == "null" and value is None)
                or (tag == "integer" and type(value) is int and -(2**63) <= value < 2**63)
                or (tag == "text" and codec._text(value))
                or (
                    tag == "blob"
                    and type(value) is str
                    and re.fullmatch(r"(?:[a-f0-9]{2})*", value) is not None
                )
            )
            require(valid, "invalid_cell")
    if table.rowid_alias is not None:
        require(
            type(rowids) is list
            and len(rowids) == len(rows)
            and all(type(value) is int and -(2**63) <= value < 2**63 for value in rowids)
            and len(rowids) == len(set(rowids)),
            "invalid_hidden_rowids",
        )
        rowids = cast(list[int], rowids)
        pairs = list(zip(rows, rowids, strict=True))
        require(pairs == sorted(pairs, key=codec._json), "noncanonical_rows")
    else:
        require(rowids is None and rows == sorted(rows, key=codec._json), "noncanonical_rows")
        keys = [codec._json([row[key] for key in table.key_columns]) for row in rows]
        require(len(keys) == len(set(keys)), "duplicate_without_rowid_key")
        require(
            all(row[key][0] != "null" for row in rows for key in table.key_columns),
            "invalid_without_rowid_key",
        )
