"""Assemble only public source into a NEW local prospective fixture.

Python owns maintainable inventory/DDL/pinning. Node imports existing TypeScript
bootstrap code to extract its real SQL; no duplicate object schema implementation.
No account client, state discovery, deployment, migration or network operation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from scripts import private_d1_snapshot_codec as codec  # noqa: E402
from scripts import private_d1_snapshot_profile as d1_profile  # noqa: E402
from scripts import private_no_real_guards as no_real  # noqa: E402

PROFILE = no_real.PROFILE
OUTPUTS = {
    "d1-schema.sql",
    "d1-guards.sql",
    "object-schema.sql",
    "object-guards.sql",
    "d1-guard-manifest.json",
    "object-guard-manifest.json",
    "store-manifest.json",
    "configuration-manifest.json",
    "source-manifest.json",
    "d1-profile-fixture.json",
}


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def query(db, sql):
    cursor = db.execute(sql)
    return [dict(zip([c[0] for c in cursor.description], row, strict=True)) for row in cursor]


def census(db):
    schema = query(db, codec.SCHEMA_SQL)
    storage = query(db, codec.TABLE_LIST_SQL)
    columns = {
        r["name"]: query(db, codec.columns_sql(r["name"])) for r in schema if r["type"] == "table"
    }
    return schema, storage, columns


def maintenance_guards(db):
    # Reuse the reviewed fixed guard generator without importing its file-global
    # fixture/control modules under ambiguous top-level module names.
    source = ROOT / "probes/pmb1-d1/fixture.py"
    import importlib.util

    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("pmb1_candidate_fixture", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tables = [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' "
            "AND name<>'maintenance_control' ORDER BY name"
        )
    ]
    return module.guard_sql(tables)


def local_inputs():
    paths = set(ROOT.glob("src/**/*.ts")) | set(ROOT.glob("migrations/*.sql"))
    paths.update(p for p in HERE.iterdir() if p.is_file() and p.name not in OUTPUTS)
    paths.update(
        ROOT / p
        for p in [
            "package.json",
            "package-lock.json",
            "tsconfig.json",
            ".gitattributes",
            "wrangler.example.jsonc",
            "tests/integer_quota_fixture.sql",
            "tests/main_entry_maintenance.test.mjs",
            "tests/test_private_d1_snapshot_profile.py",
            "probes/pmb1-d1/bootstrap.sql",
            "probes/pmb1-d1/fixture.py",
            "probes/pmb1-d1/control.py",
            "probes/pmb1-d1/close.sql",
            "probes/pmb1-d1/readback.sql",
            "probes/pmb1-d1/schema.sql",
            "probes/pmb1-d1/reopen.sql",
            "probes/pmb1-d1/manifest.json",
            "probes/pmb1-d1-adapter/adapter.py",
            "probes/pmb1-d1-adapter/test_adapter.py",
            "probes/pmb1-object/candidate.ts",
            "probes/pmb1-native-wakeup/candidate.ts",
            "probes/pmb1-native-alarm/local-storage.mjs",
            "probes/pmb1-no-real-object-reader/reader.ts",
            "scripts/private_d1_snapshot_codec.py",
            "scripts/private_d1_snapshot_reader.py",
            "scripts/private_d1_snapshot_profile.py",
            "scripts/private_no_real_guards.py",
            "scripts/fixed_origin_preservation.py",
            "scripts/fixed_origin_restore.py",
            "docs/operations/pmb1-prospective-profile-consumers-2026-10-23.md",
        ]
    )
    # Freeze every local TS runtime import recursively, including probe controls.
    pending = list(paths)
    while pending:
        path = pending.pop()
        if path.suffix == ".py":
            for statement in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                candidates = []
                if isinstance(statement, ast.ImportFrom) and statement.module:
                    candidates.append(statement.module)
                    candidates.extend(
                        statement.module + "." + alias.name for alias in statement.names
                    )
                elif isinstance(statement, ast.Import):
                    candidates.extend(alias.name for alias in statement.names)
                for module in candidates:
                    imported = ROOT / (module.replace(".", "/") + ".py")
                    if imported.is_file() and imported not in paths:
                        paths.add(imported)
                        pending.append(imported)
            continue
        if path.suffix not in {".ts", ".mjs"}:
            continue
        for relative in re.findall(
            r"(?:from\s*|import\s*)[\'\"](\.[^\'\"]+)[\'\"]", path.read_text()
        ):
            imported = (path.parent / relative).resolve()
            if imported.is_file() and imported not in paths:
                paths.add(imported)
                pending.append(imported)
    return {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}


def assemble(node="node"):
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    d1 = "-- NEW isolated prospective fixture ONLY; never apply to existing state.\n"
    for path in migrations:
        d1 += path.read_text(encoding="utf-8") + "\n"
    # Only a newly constructed in-memory domain is overlaid. This is deliberately
    # not a migration or E/R/X converter and accepts no database path/input state.
    d1 += "DROP TABLE auth_source_buckets;\nDROP TABLE status_read_buckets;\n"
    d1 += (ROOT / "tests/integer_quota_fixture.sql").read_text() + "\n"
    d1 += (ROOT / "probes/pmb1-d1/bootstrap.sql").read_text() + "\n"
    version = subprocess.run([node, "--version"], check=True, capture_output=True, text=True)
    if version.stdout.strip() != "v24.22.0":
        raise ValueError("candidate_requires_existing_node_24_22_0")
    extracted = subprocess.run(
        [node, str(HERE / "schema-fixture.mjs")],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    object_source = json.loads(extracted.stdout)
    # SQLite stores exact CREATE text; tables first, then indexes and triggers.
    schema = sorted(
        object_source["schema"],
        key=lambda r: ({"table": 0, "index": 1, "view": 2, "trigger": 3}[r["type"]], r["name"]),
    )
    obj = "-- NEW object fixture extracted by actual bootstrapPartitionMaintenance.\n"
    obj += "\n".join(r["sql"] + ";" for r in schema if r["sql"] is not None)
    obj += "\nINSERT INTO maintenance_control VALUES(1,1,'closed');\n"
    # The immutable no-insert trigger means fixture initialization must precede
    # installing triggers, just as the actual bootstrap does.
    control_trigger = next(r["sql"] for r in schema if r["name"] == "pmb1_control_no_insert")
    obj = obj.replace(control_trigger + ";", "")
    obj += control_trigger + ";\n"
    artifacts = {
        "d1-schema.sql": (d1.rstrip("\r\n") + "\n").encode(),
        "object-schema.sql": obj.encode(),
    }
    domains = {}
    for name, sql in (("d1", d1), ("object", obj)):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript(sql)
            extra = maintenance_guards(db) if name == "d1" else ""
            db.executescript(extra)
            manifest = no_real.build_guard_manifest(*census(db))
            guards = extra + "\n".join(g["sql"] + ";" for g in manifest["guards"]) + "\n"
            for g in manifest["guards"]:
                db.execute(g["sql"])
            no_real.validate_guard_manifest(
                manifest,
                *census(db),
                expected_manifest_sha256=no_real.manifest_sha256(manifest),
                query=lambda s, db=db: query(db, s),
            )
            artifacts[name + "-guards.sql"] = guards.encode()
            artifacts[name + "-guard-manifest.json"] = encode(manifest)
            domains[name] = {
                "tables": sorted(manifest["cells"]),
                "cells": manifest["cells"],
                "schemaObjects": len(manifest["schema"]),
                "guardManifestSha256": no_real.manifest_sha256(manifest),
                "allTypedCellsIncluded": True,
                "actualPopulationKnown": False,
            }
            if name == "d1":
                # Explicit synthetic provider-census emulation, NOT a statement
                # about any real D1 schema. Its inaccessible contents are never
                # returned by the profile reader, while metadata remains exact.
                provider_ddl = "CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID;"
                db.execute(provider_ddl)
                full_schema, full_storage, _ = census(db)
                profile_manifest = {
                    "profile": PROFILE,
                    "contractRevision": d1_profile.NO_REAL_CONTRACT,
                    "providerDocumentation": d1_profile.DOCUMENTATION,
                    "schema": full_schema,
                    "tableList": full_storage,
                    "includedTables": sorted(manifest["cells"]),
                    "excluded": {
                        "schema": "main",
                        "name": d1_profile.EXCLUDED,
                        "kind": "table",
                        "contents": dict(d1_profile.CONTENTS),
                    },
                    "dependencyReview": {
                        "applicationDependsOnExcludedContents": False,
                        "sourceSha256": {
                            p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                            for p in sorted((ROOT / "src").glob("*.ts"))
                        },
                        "migrationsSha256": digest(b"".join(p.read_bytes() for p in migrations)),
                        "observableSchemaSha256": d1_profile.sha256(full_schema),
                    },
                    "guardManifest": manifest,
                    "guardManifestSha256": no_real.manifest_sha256(manifest),
                }
                d1_profile.validate_manifest(profile_manifest, full_schema, full_storage)
                artifacts["d1-profile-fixture.json"] = encode(
                    {
                        "scope": "SYNTHETIC provider metadata only; actual D1 metadata UNKNOWN",
                        "providerMetadataDdl": provider_ddl,
                        "actualSourceOracle": False,
                        "actualDependencyReview": False,
                        "manifest": profile_manifest,
                    }
                )
        finally:
            db.close()
    domains["object"].update(
        {
            "class": "CandidatePartitionWorker",
            "binding": "COORD",
            "namespace": None,
            "population": None,
            "completeKV": True,
            "completeAlarm": True,
            "bootstrapKV": object_source["kv"],
            "bootstrapAlarm": object_source["alarm"],
            "kvKeysAndPatterns": [
                "pmb1:admission",
                "pmb1:wake-revision",
                "pmb1:wake-admission-sequence",
                "pmb1:wake-value",
                "pmb1:wake-result:<admission-id>",
            ],
            "readerClosedAlarmKeys": {
                "sequence": "pmb1:wake-admission-sequence",
                "invocation": "pmb1:alarm-invocation",
            },
            "readerClosedAlarmLimit": (
                "null only; close requires null; no synthetic legacy marker is written"
            ),
            "providerKVBacking": "all exposed KV included; no object-local exclusion",
        }
    )
    domains["d1"].update(
        {
            "binding": "DB",
            "resource": None,
            "providerMetadata": (
                "actual schema/census required; unknown tables refuse fixture equality"
            ),
            "onlyPossibleContentExclusion": (
                "exact independently accepted D1 main._cf_KV manifest; "
                "selected only in separate explicitly SYNTHETIC reader-profile fixture"
            ),
            "syntheticReaderProfileFixture": "d1-profile-fixture.json",
        }
    )
    writer_operations = []
    for path in sorted((ROOT / "src").glob("*.ts")):
        lines = [
            i
            for i, line in enumerate(path.read_text().splitlines(), 1)
            if re.search(
                r"\b(?:INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER)\b"
                r"|\.put\(|\.delete\(|\.setAlarm\(|\.deleteAlarm\(|waitUntil\(|\.fetch\(",
                line,
            )
        ]
        if lines:
            writer_operations.append(
                {"module": path.relative_to(ROOT).as_posix(), "effectLines": lines}
            )
    artifacts["store-manifest.json"] = encode(
        {
            "profile": PROFILE,
            "domains": domains,
            "writerSourceInventory": writer_operations,
            "externalWritersRequiringActualCensus": [
                "old/current/temporary versions",
                "operators",
                "CI",
                "migrations/import/restore/schema authority",
                "provider bookkeeping",
                "secret-store/native writer",
            ],
            "sourceOnly": True,
            "actualClosure": False,
        }
    )
    config = {
        "profile": PROFILE,
        "entry": "probes/pmb1-integer-candidate/candidate.ts:compose",
        "registration": False,
        "role": ["future retained", "future temporary"],
        "compatibilityDate": "2026-10-16",
        "compatibilityFlags": ["nodejs_compat"],
        "requiredBindings": [
            "DB",
            "COORD",
            "ASSETS",
            "FLICKR_APPLICATION",
            "FLICKR_GRANT",
            "AUTH_LIMITER_KEY",
            "NATIVE_WRITER_TOKEN",
            *[f"FLICKR_TEMP_{i}" for i in range(5)],
        ],
        "actualResourceMapping": None,
        "actualImmutableVersion": None,
        "prospectiveControlSource": "prospective_control.py:source_descriptor",
        "localD1SourceLimits": {
            "planAndConsentBytes": 2 * 1024 * 1024,
            "responseWireBytes": 512 * 1024,
            "aggregateWireBytes": 16 * 1024 * 1024,
            "queries": 2048,
            "actualCampaignAllowance": False,
        },
        "trustedPorts": [
            "main-entry journal outside compared stores",
            "independent main-entry observer",
            "explicit Flickr transport",
            "object disposition verifier",
            "partition reconciliation verifier",
            "complete bounded D1 query adapter",
            "complete bounded object population/read adapter",
        ],
        "closedRead": (
            "ordinary exact GET /api/v001/installations/current; only exact LOOKUP_SQL first()"
        ),
        "build": {
            "compiler": "TypeScript native Go 7.0.2",
            "command": (
                "node_modules/@typescript/typescript-win32-x64/lib/tsc.exe "
                "-p probes/pmb1-integer-candidate/tsconfig.json --noEmit"
            ),
            "moduleBuild": "offline build.py; native ESM source closure and exact private receipt",
            "providerBundle": False,
        },
        "actualQualification": False,
    }
    artifacts["configuration-manifest.json"] = encode(config)
    inputs = local_inputs()
    artifacts["source-manifest.json"] = encode(
        {
            "profile": PROFILE,
            "sourceOnly": True,
            "inputs": inputs,
            "artifacts": {name: digest(raw) for name, raw in sorted(artifacts.items())},
            "candidateSourceSha2_256": digest(encode({"inputs": inputs, "configuration": config})),
            "historicalArtifactsRelabeled": False,
        }
    )
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="write generated local source artifacts"
    )
    parser.add_argument("--node", default="node", help="existing pinned Node 24.22.0 executable")
    args = parser.parse_args()
    artifacts = assemble(args.node)
    for name, raw in artifacts.items():
        if args.write:
            (HERE / name).write_bytes(raw)
        elif not (HERE / name).is_file() or (HERE / name).read_bytes() != raw:
            raise SystemExit("candidate_source_drift: " + name)
    print(
        json.dumps({"artifacts": len(artifacts), "sourceOnly": True, "actualQualification": False})
    )


if __name__ == "__main__":
    main()
