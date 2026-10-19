"""Closed ADR0064 application-state boundary; no provider or file dispatch.

The manifest is private reviewed input, not evidence that a review occurred.
Its dependency attestations require independent review of the bound source and
migrations. Observable schema dependence additionally refuses here. No claim is
made about the inaccessible contents or their effect on provider behavior.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from scripts.fixed_origin_preservation import Refused, _hash, _json

PROFILE = "adr0064-private-d1-application-state-v1"
CONTRACT = "fixed-origin-preservation-2026-10-17/adr0064-v1"
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


def sources() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def sha256(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def validate_manifest(manifest: Any, schema: Any, storage: Any) -> None:
    """Require exact reviewed identity/classification before any contents read."""
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
        },
        "invalid_profile_manifest",
    )
    _json(manifest)
    require(
        manifest["profile"] == PROFILE
        and manifest["contractRevision"] == CONTRACT
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


def binding(manifest: Any, provenance: Any) -> dict[str, Any]:
    require(
        type(provenance) is dict
        and set(provenance) == {"sourceSha256", "queries", "pageSize", "columns"}
        and provenance["sourceSha256"] == sources()
        and type(provenance["queries"]) is list
        and bool(provenance["queries"])
        and all(type(sql) is str and bool(sql) for sql in provenance["queries"]),
        "profile_provenance_mismatch",
    )
    return {
        "profile": PROFILE,
        "contractRevision": CONTRACT,
        "manifestSha256": sha256(manifest),
        "sourceSha256": sha256(provenance["sourceSha256"]),
        "queriesSha256": sha256(provenance["queries"]),
        "excludedContents": dict(CONTENTS),
    }


def validate_snapshot(snapshot: Any, manifest: Any) -> dict[str, Any]:
    """Validate the private census and the exact ordered generated query provenance."""
    from scripts import private_d1_snapshot_codec as codec

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
    require(
        set(snapshot["tables"]) == {table.name for table in plan.tables},
        "profile_table_census_mismatch",
    )
    queries = [codec.SCHEMA_SQL, codec.TABLE_LIST_SQL, codec.ENCODING_SQL]
    queries.extend(codec.columns_sql(table.name) for table in plan.tables)
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
