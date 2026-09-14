"""Read-only, sanitized managed-D1 provenance for accepted private ADR0058."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import deployment_readiness as readiness
from scripts import runtime_permissions_probe as runtime

ROOT = runtime.ROOT
PRIVATE_PROFILE = "adr-0058-private-single-owner-d1"
QUERY = "SELECT sqlite_version() AS sqlite_version"
DENIAL = "not authorized to use function: sqlite_version at offset 7: SQLITE_ERROR"


def utc_instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("UTC instant required")
    result = datetime.fromisoformat(value)
    offset = result.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("UTC instant required")
    return result


def query_observation(status: int, payload: dict[str, Any], checked_at: str) -> dict[str, Any]:
    """Only a verified remote value or the exact known function refusal qualifies."""
    utc_instant(checked_at)
    receipt = {"query": QUERY, "checkedAt": checked_at, "httpStatus": status}
    if status == 200 and payload.get("success") is True:
        results = payload.get("result")
        if isinstance(results, list) and len(results) == 1:
            result = results[0]
            if isinstance(result, dict) and result.get("success") is True:
                rows = result.get("results")
                if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
                    version = rows[0].get("sqlite_version")
                    if isinstance(version, str) and re.fullmatch(
                        r"[0-9]+\.[0-9]+\.[0-9]+", version
                    ):
                        return {
                            "version": version,
                            "versionDisclosure": "disclosed",
                            "observation": receipt,
                        }
    if (
        status == 400
        and payload.get("success") is False
        and payload.get("errors") == [{"code": 7500, "message": DENIAL}]
    ):
        return {
            "version": None,
            "versionDisclosure": "provider-undisclosed",
            "observation": {**receipt, "errorCode": 7500, "message": DENIAL},
        }
    raise ValueError("remote_engine_provenance_unavailable")


def valid_engine(engine: Any, report: dict[str, Any]) -> bool:
    if not isinstance(engine, dict) or set(engine) != {
        "provider",
        "runtime",
        "versionKind",
        "versionSource",
        "providerGeneration",
        "migrationHead",
        "version",
        "versionDisclosure",
        "observation",
    }:
        return False
    if (
        report.get("deploymentProfile") != PRIVATE_PROFILE
        or engine.get("provider") != "cloudflare-d1"
        or engine.get("runtime") != "cloudflare-d1"
        or engine.get("versionKind") != "sqlite-library"
        or engine.get("versionSource") != "remote-sqlite-version-query"
        or not isinstance(engine.get("providerGeneration"), str)
        or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", engine["providerGeneration"]) is None
    ):
        return False
    receipt = engine.get("observation")
    if not isinstance(receipt, dict) or receipt.get("query") != QUERY:
        return False
    try:
        if not (
            utc_instant(report.get("runStartedAt"))
            <= utc_instant(receipt.get("checkedAt"))
            <= utc_instant(report.get("runCompletedAt"))
        ):
            return False
    except ValueError, OverflowError:
        return False
    if engine.get("versionDisclosure") == "disclosed":
        return (
            isinstance(engine.get("version"), str)
            and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", engine["version"]) is not None
            and type(receipt.get("httpStatus")) is int
            and receipt["httpStatus"] == 200
            and set(receipt) == {"query", "checkedAt", "httpStatus"}
        )
    return (
        engine.get("versionDisclosure") == "provider-undisclosed"
        and "version" in engine
        and engine["version"] is None
        and type(receipt.get("httpStatus")) is int
        and receipt["httpStatus"] == 400
        and type(receipt.get("errorCode")) is int
        and receipt["errorCode"] == 7500
        and receipt.get("message") == DENIAL
        and set(receipt) == {"query", "checkedAt", "httpStatus", "errorCode", "message"}
    )


def source_identities(root: Path = ROOT) -> dict[str, Any]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    paths = (
        subprocess.run(
            ["git", "ls-files", "-z", "--", "scripts", "tests", "probes", ".github"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted(path for path in paths if path):
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256((root / name).read_bytes()).digest())
    return {
        "testAdapterSha2_256": digest.hexdigest(),
        "tooling": {
            **{
                name: package["devDependencies"][name]
                for name in ("wrangler", "typescript", "miniflare", "@cloudflare/workers-types")
            },
            "python": (root / ".python-version").read_text().strip(),
            "uv": project["tool"]["uv"]["required-version"],
            "npm": package["packageManager"],
            "node": subprocess.run(
                [runtime.NODE, "--version"], check=True, capture_output=True, text=True
            ).stdout.strip(),
        },
    }


def request(
    account: str,
    database: str,
    token: str,
    sql: str | None = None,
    *,
    max_response_bytes: int = 65536,
) -> tuple[int, Any]:
    if type(max_response_bytes) is not int or not 65536 <= max_response_bytes <= 4 * 1024 * 1024:
        raise ValueError("invalid_provider_response_budget")
    if (
        re.fullmatch(r"[a-f0-9]{32}", account) is None
        or re.fullmatch(r"[a-f0-9-]{36}", database) is None
    ):
        raise ValueError("invalid_database_configuration")
    suffix = "/query" if sql else ""
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/accounts/"
        + account
        + "/d1/database/"
        + database
        + suffix,
        method="POST" if sql else "GET",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "FlickrGroupAddr-EngineProvenance/1",
        },
        data=json.dumps({"sql": sql, "params": []}).encode() if sql else None,
    )
    try:
        response = urllib.request.build_opener(runtime.NoRedirect).open(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(max_response_bytes + 1)
        if len(raw) > max_response_bytes:
            raise ValueError("provider_response_over_budget")
        status = response.status
        payload = json.loads(raw)
        if type(status) is not int or not isinstance(payload, dict):
            raise ValueError("provider_response_invalid")
        return status, payload


def collect(config: dict[str, Any], token: str) -> dict[str, Any]:
    bindings = [row for row in config["d1_databases"] if row["binding"] == "DB"]
    if len(bindings) != 1:
        raise ValueError("unique_production_database_required")
    account = config.get("account_id") or config["vars"]["CF_ACCOUNT_ID"]
    database = bindings[0]["database_id"]
    status, metadata = request(account, database, token)
    if status != 200 or metadata.get("success") is not True:
        raise ValueError("database_metadata_unavailable")
    status, response = request(account, database, token, QUERY)
    observed = query_observation(status, response, datetime.now(UTC).isoformat())
    status, migrations = request(
        account, database, token, "SELECT name FROM d1_migrations ORDER BY id DESC LIMIT 1"
    )
    if status != 200 or migrations.get("success") is not True:
        raise ValueError("remote_migration_head_unavailable")
    head = migrations["result"][0]["results"][0]["name"]
    return {
        "provider": "cloudflare-d1",
        "runtime": "cloudflare-d1",
        "versionKind": "sqlite-library",
        "versionSource": "remote-sqlite-version-query",
        "providerGeneration": metadata["result"]["version"],
        "migrationHead": head,
        **observed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Private deployment JSON")
    parser.add_argument("--output", required=True, type=Path, help="Sanitized observation JSON")
    args = parser.parse_args()
    try:
        started = datetime.now(UTC).isoformat()
        config = json.loads(args.config.read_text(encoding="utf-8"))
        engine = collect(config, readiness.token())
        report = {
            "schemaVersion": 2,
            "scope": "provenance-only",
            "releaseEligible": False,
            "deploymentProfile": PRIVATE_PROFILE,
            "runStartedAt": started,
            "runCompletedAt": datetime.now(UTC).isoformat(),
            "databaseEngine": engine,
            "workersCompatibilityDate": config["compatibility_date"],
            "configurationSha2_256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
            **source_identities(),
        }
        if not valid_engine(engine, report):
            raise ValueError("invalid_provenance")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(
            json.dumps(
                {
                    "provenanceCollected": True,
                    "releaseEligible": False,
                    "versionDisclosure": engine["versionDisclosure"],
                }
            )
        )
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
    ):
        print(json.dumps({"provenanceCollected": False, "releaseEligible": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
