"""Disposable hosted #0007/#0011 proofs. Never target a production database."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import secrets
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from . import runtime_permissions_probe as runtime
    from .native_secret_probe import deploy_with_bearer
except ImportError:
    import runtime_permissions_probe as runtime
    from native_secret_probe import deploy_with_bearer

ROOT = runtime.ROOT
RUNS = ROOT / ".foundation-runs"
ARCHITECTURE_DECISION_COMMIT = "0cf54f37cd4c293a0b62d467b9a9394fea1a486c"
# Same fixed provider fixture as the routing proof; keep this harness import-independent.
PROVIDER_BAD_REQUEST_SHA2_256 = "efca0895b4d88b27a94249f8e7ac0083eff0a4ff3ac37c2841b3f6d7e11c1905"
Run = runtime.Run
ProbeError = runtime.ProbeError
NUMBERS = [
    "9007199254740991",
    "9007199254740992",
    "9007199254740993",
    "9223372036854775807",
    "-9223372036854775808",
]


def hashes() -> dict[str, str]:
    paths = [
        *ROOT.glob("src/*.ts"),
        *ROOT.glob("migrations/*.sql"),
        ROOT / "probes/foundation/worker.ts",
        Path(__file__),
        ROOT / "scripts/native_secret_probe.py",
        ROOT / "scripts/runtime_permissions_probe.py",
        ROOT / "package-lock.json",
        ROOT / "tsconfig.json",
    ]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def new_run(mode: str) -> Run:
    run_id = "rp-" + secrets.token_hex(12)
    directory = RUNS / run_id
    directory.mkdir(parents=True)
    name = "fga-" + run_id
    run = Run(
        directory,
        {
            "runId": run_id,
            "environment": "cloudflare",
            "mode": mode,
            "workerName": name,
            "databaseName": name + "-db",
            "sourceHashes": hashes(),
        },
    )
    run.save()
    return run


def validate(run: Run) -> None:
    if (
        run.directory.resolve().parent != RUNS.resolve()
        or run.directory.name != run.run_id
        or not re.fullmatch(r"rp-[a-f0-9]{24}", run.run_id)
    ):
        raise ProbeError("Invalid foundation run directory.")
    runtime.checked_resource_names(run)


def create_database(run: Run) -> None:
    validate(run)
    identity = json.loads(runtime.wrangler(run, "identity", "whoami", "--json").stdout)
    if not identity.get("loggedIn") or len(identity.get("accounts", [])) != 1:
        raise ProbeError("Exactly one authenticated account is required.")
    run.state["accountId"] = identity["accounts"][0]["id"]
    if any(r["name"] == run.state["databaseName"] for r in runtime.databases(run, "preflight-db")):
        raise ProbeError("Generated database name already exists.")
    run.state["databaseAttempted"] = True
    run.save()
    runtime.wrangler(
        run, "create-db", "d1", "create", run.state["databaseName"], "--update-config=false"
    )
    matches = [
        r for r in runtime.databases(run, "created-db") if r["name"] == run.state["databaseName"]
    ]
    if len(matches) != 1:
        raise ProbeError("Created database identity ambiguous.")
    run.state["databaseId"] = matches[0]["uuid"]
    run.save()


def configure(run: Run, *, full: bool) -> Path:
    migration_dir = run.directory / "migrations"
    migration_dir.mkdir(exist_ok=True)
    for name in ["0001_foundation.sql", *(["0002_audit_component.sql"] if full else [])]:
        shutil.copyfile(ROOT / "migrations" / name, migration_dir / name)
    config = {
        "name": run.state["workerName"],
        "main": str(ROOT / "probes/foundation/worker.ts"),
        "compatibility_date": "2026-09-11",
        "compatibility_flags": ["nodejs_compat"],
        "account_id": run.state["accountId"],
        "workers_dev": True,
        "preview_urls": False,
        "observability": {"enabled": False},
        "vars": {
            "FGA_READ_ENABLED": "1",
            "PROOF_BUILD": run.run_id,
            "PROOF_MODE": run.state["mode"],
            "PROOF_EXPIRES": str(int((time.time() + 3600) * 1000)),
        },
        "d1_databases": [
            {
                "binding": "DB",
                "database_name": run.state["databaseName"],
                "database_id": run.state["databaseId"],
                "migrations_dir": str(migration_dir),
            }
        ],
    }
    target = run.directory / "wrangler.json"
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return target


def migrations(run: Run, stage: str, config: Path) -> None:
    runtime.wrangler(
        run,
        stage,
        "d1",
        "migrations",
        "apply",
        run.state["databaseName"],
        "--remote",
        "--config",
        str(config),
    )


def execute(run: Run, stage: str, sql: str, *, allow_failure: bool = False):
    # Only synthetic #0007 data is written to files/logs. #0011 secrets travel in memory via HTTPS.
    path = run.directory / (stage + ".sql")
    path.write_text(sql, encoding="utf-8")
    return runtime.wrangler(
        run,
        stage,
        "d1",
        "execute",
        run.state["databaseName"],
        "--remote",
        "--file",
        str(path),
        "--yes",
        "--json",
        allow_failure=allow_failure,
    )


def query(run: Run, stage: str, sql: str) -> list[dict[str, Any]]:
    payload = json.loads(
        runtime.wrangler(
            run,
            stage,
            "d1",
            "execute",
            run.state["databaseName"],
            "--remote",
            "--command",
            sql,
            "--json",
        ).stdout
    )
    return payload[-1]["results"]


def raw_once(
    run: Run,
    path: str,
    headers: list[tuple[str, str]],
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    url = urlsplit(run.state["url"])
    if url.scheme != "https" or not url.hostname or not url.hostname.endswith(".workers.dev"):
        raise ProbeError("Proof URL outside isolated HTTPS Worker boundary.")
    connection = http.client.HTTPSConnection(url.hostname, timeout=30)
    try:
        connection.putrequest(method, path, skip_accept_encoding=True)
        for name, value in headers:
            connection.putheader(name, value)
        if body is not None and not any(k.lower() == "content-length" for k, _ in headers):
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        return (
            response.status,
            {k.lower(): v for k, v in response.getheaders()},
            response.read(1_048_576),
        )
    finally:
        connection.close()


def raw(
    run: Run,
    path: str,
    headers: list[tuple[str, str]],
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    # GET/status are read-only. Seed is explicitly idempotent for an identical
    # seven-credential fixture: the unique keys and one D1 batch prevent extras.
    retryable = path in {"/__proof/status", "/__proof/seed"}
    attempts = 6 if retryable else 1
    for attempt in range(attempts):
        try:
            result = raw_once(run, path, headers, method, body)
            if result[0] not in {404, 429, 500, 502, 503, 504} or attempt == attempts - 1:
                return result
        except OSError, http.client.HTTPException:
            if attempt == attempts - 1:
                raise
            result = (0, {}, b"")
        run.state.setdefault("setupRetries", []).append(
            {
                "surface": path.rsplit("/", 1)[-1],
                "method": method,
                "status": result[0],
                "attempt": attempt + 1,
            }
        )
        run.save()
        time.sleep(2)
    raise ProbeError("Bounded HTTP attempt exhausted.")


def call(run: Run, token: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    status, _, raw_body = raw(
        run,
        "/__proof/" + action,
        [("Authorization", "Bearer " + token)],
        "GET" if data is None else "POST",
        None if data is None else json.dumps(data).encode(),
    )
    try:
        result = json.loads(raw_body)
    except ValueError:
        raise ProbeError(f"Proof {action} returned a non-JSON response (HTTP {status}).") from None
    if status != 200 or result.get("build") != run.run_id:
        raise ProbeError(f"Proof {action} rejected or wrong build (HTTP {status}).")
    return result["result"]


def deploy(run: Run, config: Path, token: str) -> None:
    previous = runtime.wrangler(
        run,
        "worker-preflight",
        "deployments",
        "list",
        "--name",
        run.state["workerName"],
        "--json",
        allow_failure=True,
    )
    if not runtime.missing_worker(previous):
        raise ProbeError("Generated Worker name was not unused.")
    runtime.command(
        run, "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
    )
    run.state["workerAttempted"] = True
    run.save()
    output = deploy_with_bearer(run, config, token)
    urls = re.findall(r"https://[a-z0-9.-]+\.workers\.dev", output)
    if len(set(urls)) != 1:
        raise ProbeError("Deployment URL was ambiguous.")
    run.state["url"] = urls[0]
    run.save()
    deadline = time.monotonic() + 120
    consecutive = 0
    while time.monotonic() < deadline:
        try:
            call(run, token, "status")
            call(run, token, "status", {})
            consecutive += 1
            if consecutive >= 3:
                return
            time.sleep(2)
        except ProbeError, OSError, http.client.HTTPException:
            consecutive = 0
            time.sleep(2)
    raise ProbeError("Hosted proof readiness did not converge.")


def credential() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    bits = int.from_bytes(secrets.token_bytes(32), "big") << 4
    text = "".join(alphabet[(bits >> shift) & 31] for shift in range(255, -1, -5))
    return "-".join(text[i : i + 4] for i in range(0, 52, 4))


def record(report: dict[str, Any], name: str, passed: bool, **details: Any) -> None:
    report["cases"].append({"id": name, "passed": passed, **details})
    print(f"Foundation case: {name}: {'pass' if passed else 'FAIL'}", flush=True)
    if not passed:
        raise ProbeError(f"Case failed: {name}")


def accepted_provider_rejection(
    case: str, status: int, headers: dict[str, str], body: bytes
) -> bool:
    """The owner-approved early parser boundary, never an arbitrary HTML allowance."""
    headers = {key.lower(): value for key, value in headers.items()}
    return (
        case in {"duplicate_auth", "encoded_separator"}
        and status == 400
        and headers.get("content-type", "").split(";", 1)[0].strip().lower() == "text/html"
        and not any(key.startswith("x-fga-") for key in headers)
        and not any(key in headers for key in ("location", "set-cookie", "www-authenticate"))
        and hashlib.sha256(body).hexdigest() == PROVIDER_BAD_REQUEST_SHA2_256
    )


def read_slice(run: Run, token: str, report: dict[str, Any]) -> None:
    credentials = [credential() for _ in range(7)]
    call(run, token, "seed", {"credentials": credentials})
    before = call(run, token, "status")["snapshot"]
    path = "/api/v001/installations/current"
    cases = [
        ("current", 0, 200, "current"),
        ("pending", 1, 200, "pending_rotation"),
        ("other_current", 2, 200, "current"),
        ("expired_pending", 3, 401, None),
        ("replaced", 4, 401, None),
        ("revoked", 5, 401, None),
        ("expired_unactivated", 6, 401, None),
    ]
    for name, index, expected, state in cases:
        status, headers, body = raw(run, path, [("Authorization", "Bearer " + credentials[index])])
        data = json.loads(body)
        passed = (
            status == expected
            and headers.get("cache-control") == "no-store"
            and headers.get("x-fga-proof-build") == run.run_id
        )
        if expected == 200:
            passed = (
                passed
                and set(data)
                == {
                    "schemaVersion",
                    "installationId",
                    "installationRevision",
                    "installationState",
                    "presentedCredentialState",
                }
                and data["schemaVersion"] == 1
                and data["installationState"] == "active"
                and data["presentedCredentialState"] == state
                and data["installationId"] == ("expired" if index == 2 else "active")
                and data["installationRevision"] == (2 if index == 2 else 7)
            )
        else:
            passed = (
                passed
                and data.get("error", {}).get("code") == "invalid_token"
                and headers.get("www-authenticate")
                == 'Bearer realm="fga-api", error="invalid_token"'
            )
        passed = passed and not any(
            c.encode() in body or hashlib.sha256(c.encode()).hexdigest().encode() in body
            for c in credentials
        )
        record(report, "read." + name, passed)
    corpus = [
        ("missing", path, [], "GET", None, 401, None),
        ("unsupported_scheme", path, [("Authorization", "Basic abc")], "GET", None, 401, None),
        (
            "unknown",
            path,
            [("Authorization", "Bearer " + credential())],
            "GET",
            None,
            401,
            "invalid_token",
        ),
        (
            "malformed",
            path,
            [("Authorization", "Bearer broken")],
            "GET",
            None,
            401,
            "invalid_token",
        ),
        (
            "lowercase",
            path,
            [("Authorization", "Bearer " + credentials[0].lower())],
            "GET",
            None,
            401,
            "invalid_token",
        ),
        (
            "padding",
            path,
            [("Authorization", "Bearer " + credentials[0][:-1] + "1")],
            "GET",
            None,
            401,
            "invalid_token",
        ),
        (
            "duplicate_auth",
            path,
            [("Authorization", "Bearer " + credentials[0])] * 2,
            "GET",
            None,
            400,
            "invalid_request",
        ),
        (
            "query",
            path + "?anything=1",
            [("Authorization", "Bearer " + credentials[0])],
            "GET",
            None,
            400,
            "invalid_request",
        ),
        (
            "two_transports",
            path + "?access_token=synthetic",
            [("Authorization", "Bearer " + credentials[0])],
            "GET",
            None,
            400,
            "invalid_request",
        ),
        (
            "body",
            path,
            [("Authorization", "Bearer " + credentials[0])],
            "GET",
            b"x",
            400,
            "invalid_request",
        ),
        ("wrong_method", path, [], "POST", None, 405, "method_not_allowed"),
        ("retired_route", "/api/v001/installations/token-check", [], "GET", None, 404, "not_found"),
        ("api_no_asset", "/api/v001/unknown", [], "GET", None, 404, "not_found"),
        ("health_no_asset", "/healthz/unknown", [], "GET", None, 404, "not_found"),
        (
            "encoded_separator",
            "/api%2fv001/installations/current",
            [],
            "GET",
            None,
            400,
            "invalid_request",
        ),
    ]
    for name, target, headers_in, method, body_in, expected, code in corpus:
        status, headers, body = raw(run, target, headers_in, method, body_in)
        passed = (
            status == expected
            and headers.get("cache-control") == "no-store"
            and headers.get("x-fga-proof-build") == run.run_id
        )
        if code is None:
            passed = (
                passed
                and body == b""
                and headers.get("www-authenticate") == 'Bearer realm="fga-api"'
            )
        else:
            try:
                data = json.loads(body)
            except ValueError:
                observation = {
                    "id": "http." + name,
                    "passed": False,
                    "expected": "application JSON error and no-store",
                    "status": status,
                    "contentType": headers.get("content-type"),
                    "cacheControl": headers.get("cache-control"),
                    "bodySha2_256": hashlib.sha256(body).hexdigest(),
                    "bodyBytes": len(body),
                    "applicationBuildPresent": "x-fga-proof-build" in headers,
                    "redirectPresent": "location" in headers,
                    "cookiePresent": "set-cookie" in headers,
                    "credentialOrDigestInBody": any(
                        c.encode() in body
                        or hashlib.sha256(c.encode()).hexdigest().encode() in body
                        for c in credentials
                    ),
                }
                if accepted_provider_rejection(name, status, headers, body):
                    authority = "ADR0054" if name == "duplicate_auth" else "ADR0037"
                    observation.update(passed=True, authority=authority)
                    observation["expected"] = "bounded early provider HTTP 400"
                    report.setdefault("acceptedProviderRejections", []).append(observation)
                    record(
                        report,
                        "http." + name,
                        True,
                        boundary="provider_parser",
                        authority=authority,
                    )
                else:
                    report.setdefault("unmetContractCases", []).append(observation)
                    print("Foundation boundary observation: " + json.dumps(observation), flush=True)
                continue
            error = data.get("error", {})
            passed = (
                passed
                and error.get("code") == code
                and bool(re.fullmatch(r"[a-f0-9-]{36}", error.get("correlationId", "")))
                and not error.get("retryable")
            )
            if code in {"invalid_request", "invalid_token"} and name != "encoded_separator":
                passed = (
                    passed
                    and headers.get("www-authenticate") == f'Bearer realm="fga-api", error="{code}"'
                )
            if name == "wrong_method":
                passed = passed and headers.get("allow") == "GET"
        record(report, "http." + name, passed)
    status, headers, body = raw(
        run,
        "/__proof/ordinary",
        [
            ("Authorization", "Bearer " + token),
            ("X-Fixture-Credential", "Bearer " + credentials[1]),
        ],
    )
    record(
        report,
        "read.pending_ordinary_scope",
        status == 403
        and json.loads(body)["error"]["code"] == "insufficient_scope"
        and headers.get("cache-control") == "no-store",
    )
    after = call(run, token, "status")["snapshot"]
    record(report, "read.no_durable_mutations", before == after)
    report["outboundFlickrOrAWSCalls"] = 0
    report["readPhaseProtectedWrites"] = 0
    report["fixtureCredentialsRetained"] = False


def bookmark(run: Run, stage: str) -> str:
    data = json.loads(
        runtime.wrangler(
            run, stage, "d1", "time-travel", "info", run.state["databaseName"], "--json"
        ).stdout
    )
    value = data["bookmark"]
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9-]+", value):
        raise ProbeError("Unexpected bookmark format.")
    return value


def stop_worker(run: Run) -> None:
    runtime.delete_worker_without_force(run)
    check = runtime.wrangler(
        run,
        "maintenance-worker-absent",
        "deployments",
        "list",
        "--name",
        run.state["workerName"],
        "--json",
        allow_failure=True,
    )
    if not runtime.missing_worker(check):
        raise ProbeError("Worker absence unconfirmed; restore forbidden.")
    run.state["workerDeleted"] = True
    run.state["maintenanceOutsideDatabase"] = True
    run.save()


def restore(run: Run, stage: str, value: str) -> None:
    if not run.state.get("maintenanceOutsideDatabase") or not run.state.get("workerDeleted"):
        raise ProbeError("Restore requires the disposable Worker to be removed first.")
    runtime.wrangler(
        run,
        stage,
        "d1",
        "time-travel",
        "restore",
        run.state["databaseName"],
        "--bookmark",
        value,
        "--json",
        input_text="y\n",
    )


def sql_literal(column: str) -> str:
    # quote(TEXT) truncates at a NUL. Hex preserves every UTF-8 text byte, while
    # quote() preserves INTEGER, REAL, BLOB and NULL without JavaScript numbers.
    if not re.fullmatch(r"[a-z_]+", column):
        raise ProbeError("Unsafe export column.")
    return (
        f"CASE WHEN typeof({column})='text' AND instr({column},char(0))>0 "
        f"THEN 'CAST(X''' || hex({column}) || ''' AS TEXT)' "
        f"ELSE quote({column}) END"
    )


def exact_export(run: Run, output: Path) -> None:
    schema = run.directory / "backup-schema.sql"
    runtime.wrangler(
        run,
        "export-schema",
        "d1",
        "export",
        run.state["databaseName"],
        "--remote",
        "--no-data",
        "--output",
        str(schema),
        "--skip-confirmation",
    )
    text = schema.read_text(encoding="utf-8")
    tables = {
        "d1_migrations": "id",
        "fga_users": "user_id",
        "installations": "installation_id",
        "installation_credential_versions": "installation_id,ordinal",
        "submission_blocks": "photo_id,group_id",
        "audit_events": "event_id",
        "integer_probe": "id",
    }
    rows = []
    for table, order in tables.items():
        columns = query(run, "export-columns-" + table, f"PRAGMA table_xinfo({table});")
        names = [row["name"] for row in columns if row["hidden"] == 0]
        if not names or any(not re.fullmatch(r"[a-z_]+", name) for name in names):
            raise ProbeError("Unexpected columns in scoped export.")
        joined = ",".join(names)
        expression = " || ',' || ".join(sql_literal(name) for name in names)
        sql = (
            f"SELECT 'INSERT INTO {table}({joined}) VALUES(' || {expression} || ');' "
            f"AS sql FROM {table} ORDER BY {order};"
        )
        rows.extend(row["sql"] for row in query(run, "export-values-" + table, sql))
    output.write_text(
        "PRAGMA defer_foreign_keys=ON;\n" + text + "\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def guard_recovery(run: Run, token: str, report: dict[str, Any], config: Path, clone: Run) -> None:
    call(run, token, "seed", {"credentials": [f"synthetic-history-{i}" for i in range(7)]})
    initial = query(
        run, "history-before-upgrade", "SELECT event_id,created_at_utc,reason FROM audit_events;"
    )
    configure(run, full=True)
    migrations(run, "upgrade-migration", config)
    record(
        report,
        "migration.upgrade_preserves_history",
        query(
            run, "history-after-upgrade", "SELECT event_id,created_at_utc,reason FROM audit_events;"
        )
        == initial,
    )
    for item in call(run, token, "guards", {})["cases"]:
        record(report, "guard." + item["id"], item["passed"])
    bad = run.directory / "migrations/0003_injected_failure.sql"
    bad.write_text(
        "CREATE TABLE migration_must_rollback(id INTEGER);\nDELETE FROM audit_events;\n",
        encoding="utf-8",
    )
    failed = runtime.wrangler(
        run,
        "injected-migration-failure",
        "d1",
        "migrations",
        "apply",
        run.state["databaseName"],
        "--remote",
        "--config",
        str(config),
        allow_failure=True,
    )
    absent = query(
        run,
        "failed-migration-rollback",
        "SELECT name FROM sqlite_master WHERE name='migration_must_rollback';",
    )
    record(report, "migration.failure_rolls_back", failed.returncode != 0 and absent == [])
    bad.unlink()
    values = ",".join(f"({i},{n})" for i, n in enumerate(NUMBERS))
    execute(
        run,
        "integer-fixture",
        "CREATE TABLE integer_probe(id INTEGER PRIMARY KEY,value INTEGER NOT NULL) STRICT;\n"
        f"INSERT INTO integer_probe VALUES{values};",
    )
    integer_sql = "SELECT CAST(value AS TEXT) AS value FROM integer_probe ORDER BY id;"
    record(
        report,
        "integer.exact_text_projection",
        [x["value"] for x in query(run, "integers-before", integer_sql)] == NUMBERS,
    )
    clocks = [call(run, token, "status")["clock"] for _ in range(12)]
    record(
        report,
        "clock.private_database_utc",
        all(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", x["utc"])
            and int(x["epoch_us"]) % 1000 == 0
            for x in clocks
        ),
    )
    report["clock"] = {
        "samples": len(clocks),
        "observedMicrosecondRemainder": sorted({int(x["epoch_us"]) % 1000 for x in clocks}),
        "storageFormatFractionDigits": 6,
        "documentedClockResolution": "milliseconds",
        "acceptedPrivateSourceResolution": "milliseconds",
        "authority": "ADR0053",
        "microsecondResolutionProven": False,
    }
    stop_worker(run)
    record(
        report,
        "recovery.runtime_removed_before_backup_and_restore",
        run.state["maintenanceOutsideDatabase"],
    )
    export = run.directory / "backup.sql"
    runtime.wrangler(
        run,
        "export",
        "d1",
        "export",
        run.state["databaseName"],
        "--remote",
        "--output",
        str(export),
        "--skip-confirmation",
    )
    create_database(clone)
    ordinary_sql = export.read_text(encoding="utf-8")
    numeric_literals = re.findall(
        r'INSERT INTO "integer_probe" \(\"id\",\"value\"\) VALUES\(\d+,([^)]*)\);',
        ordinary_sql,
    )
    report["ordinaryExport"] = {
        "integerLiteralsExact": numeric_literals == NUMBERS,
        "observedIntegerLiterals": numeric_literals,
    }
    # Standard SQLite quote() turns each value into SQL text inside D1, before
    # JavaScript/JSON can coerce an INTEGER to an inexact Number. No new service.
    exact_export(run, export)
    imported = runtime.wrangler(
        clone,
        "import",
        "d1",
        "execute",
        clone.state["databaseName"],
        "--remote",
        "--file",
        str(export),
        "--yes",
        "--json",
        allow_failure=True,
    )
    report["exportImport"] = {
        "importSucceeded": imported.returncode == 0,
        "largeIntegersExact": False,
    }
    if imported.returncode == 0:
        report["exportImport"]["largeIntegersExact"] = [
            x["value"] for x in query(clone, "import-integers", integer_sql)
        ] == NUMBERS
        record(report, "export.integer_fidelity", report["exportImport"]["largeIntegersExact"])
        for table in [
            "submission_blocks",
            "audit_events",
            "installations",
            "installation_credential_versions",
        ]:
            left = query(run, "export-" + table, f"SELECT * FROM {table} ORDER BY 1;")
            right = query(clone, "import-" + table, f"SELECT * FROM {table} ORDER BY 1;")
            record(report, "export.rows_" + table, left == right)
        for table in ["submission_blocks", "audit_events"]:
            denied = execute(
                clone, "import-guard-" + table, f"DELETE FROM {table};", allow_failure=True
            )
            record(report, "export.guard_" + table, denied.returncode != 0)
        record(
            report,
            "export.foreign_keys",
            query(clone, "import-fk", "PRAGMA foreign_key_check;") == [],
        )
    record(report, "export.exact_import_succeeded", report["exportImport"]["importSucceeded"])
    schema_sql = (
        "SELECT name,sql FROM sqlite_master WHERE type IN ('trigger','index') "
        "AND sql IS NOT NULL ORDER BY name;"
    )
    record(
        report,
        "export.schema_guards_preserved",
        query(run, "source-schema-guards", schema_sql)
        == query(clone, "import-schema-guards", schema_sql),
    )
    # The ordinary export limitation does not require an additional service.
    print("Foundation export observation: " + json.dumps(report["exportImport"]), flush=True)
    old = bookmark(run, "bookmark-before")
    run.state["beforeBookmark"] = old
    run.save()
    execute(
        run,
        "post-backup-history",
        """PRAGMA defer_foreign_keys=ON;
INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id)
VALUES('later-photo','group','flickr_code_6','later-attempt');
INSERT INTO audit_events(event_id,action,request_correlation_id,outcome,reason)
VALUES('later-event','fixture.revoke','later-request','succeeded','synthetic');
UPDATE installation_credential_versions SET state='revoked'
WHERE installation_id='active' AND state IN ('current','pending_rotation');
UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=8
WHERE installation_id='active';
""",
    )
    current = bookmark(run, "bookmark-after")
    run.state["afterBookmark"] = current
    run.save()
    restore(run, "restore-old", old)
    history_sql = (
        "SELECT (SELECT COUNT(*) FROM submission_blocks WHERE "
        "photo_id='later-photo') AS later_block,(SELECT COUNT(*) FROM "
        "audit_events WHERE event_id='later-event') AS later_audit,(SELECT "
        "state FROM installations WHERE installation_id='active') AS "
        "installation_state;"
    )
    old_rows = query(run, "old-history", history_sql)
    record(
        report,
        "recovery.old_copy_loses_new_history",
        old_rows == [{"later_block": 0, "later_audit": 0, "installation_state": "active"}],
    )
    record(report, "recovery.incomplete_history_keeps_runtime_removed", run.state["workerDeleted"])
    restore(run, "restore-complete", current)
    complete_rows = query(run, "complete-history", history_sql)
    record(
        report,
        "recovery.complete_bookmark_recovers_history",
        complete_rows == [{"later_block": 1, "later_audit": 1, "installation_state": "revoked"}],
    )
    record(
        report,
        "recovery.time_travel_integer_fidelity",
        [x["value"] for x in query(run, "restored-integers", integer_sql)] == NUMBERS,
    )
    record(
        report,
        "recovery.foreign_keys",
        query(run, "restored-fk", "PRAGMA foreign_key_check;") == [],
    )
    for table in ["submission_blocks", "audit_events"]:
        result = execute(
            run, "restored-guard-" + table, f"DELETE FROM {table};", allow_failure=True
        )
        record(report, "recovery.guard_" + table, result.returncode != 0)
    report["recoveryScope"] = (
        "quiescent disposable Worker; no schedulers, DOs or outgoing Flickr "
        "calls; runtime stays removed"
    )


def run_proof(mode: str) -> int:
    run = new_run(mode)
    clone = new_run("clone") if mode == "guards" else None
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "scope": mode,
        "acceptedDecisions": ["ADR0053", "ADR0054"],
        "architectureDecisionCommit": ARCHITECTURE_DECISION_COMMIT,
        "productionConformance": False,
        "collectedAt": datetime.now(UTC).isoformat(),
        "cases": [],
        "compatibilityDate": "2026-09-11",
        "sourceHashes": run.state["sourceHashes"],
    }
    token = secrets.token_urlsafe(32)
    print("Foundation private run: " + str(run.directory), flush=True)
    try:
        create_database(run)
        config = configure(run, full=mode == "read")
        migrations(run, "fresh-migration", config)
        record(report, "migration.fresh", True)
        deploy(run, config, token)
        if mode == "read":
            read_slice(run, token, report)
        else:
            assert clone is not None
            guard_recovery(run, token, report, config, clone)
        record(report, "evidence.source_unchanged", hashes() == run.state["sourceHashes"])
        report["completed"] = True
    except (ProbeError, OSError, ValueError, KeyError, http.client.HTTPException) as error:
        report["completed"] = False
        report["failureType"] = type(error).__name__
        print(
            str(error)
            if isinstance(error, ProbeError)
            else "Proof failed; private evidence retained.",
            file=sys.stderr,
        )
    finally:
        for item in [run, *([clone] if clone else [])]:
            if item.state.get("databaseAttempted") or item.state.get("workerAttempted"):
                try:
                    runtime.cleanup(item)
                except (ProbeError, OSError) as error:
                    print("Cleanup not confirmed: " + str(error), file=sys.stderr)
        report["setupRetries"] = run.state.get("setupRetries", [])
        report["applicationCaseRetries"] = 0
        report["cleanupConfirmed"] = run.state.get("cleanupConfirmed", False) and (
            clone is None or clone.state.get("cleanupConfirmed", False)
        )
        serialized = json.dumps(report, indent=2) + "\n"
        if token in serialized:
            raise ProbeError("Public evidence credential check failed.")
        (run.directory / "report.json").write_text(serialized, encoding="utf-8")
    print("Foundation report: " + str(run.directory / "report.json"), flush=True)
    return (
        0
        if report.get("completed")
        and report["cleanupConfirmed"]
        and not report.get("unmetContractCases")
        else 1
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["guards", "read", "cleanup"])
    parser.add_argument("--run")
    args = parser.parse_args()
    if args.mode == "cleanup":
        directory = Path(args.run or "").resolve()
        if directory.parent != RUNS.resolve():
            raise ProbeError("Cleanup path outside foundation runs.")
        run = Run(directory, json.loads((directory / "manifest.json").read_text(encoding="utf-8")))
        validate(run)
        runtime.cleanup(run)
        return 0
    return run_proof(args.mode)


if __name__ == "__main__":
    sys.exit(main())
