"""One fresh disposable D1/Worker edge matrix; no production resources or Flickr calls."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import existing_photo_qualification as matrix
from scripts.controlled_trial_pause import NoRedirect
from scripts.controlled_trial_pause_hosted import credentials, save
from scripts.coordination_probe import statements

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = "existing-photo-hosted-qualification-2026-10-16.json"
FLAGS = ["nodejs_compat", "enable_request_signal"]
DATE = "2026-10-16"
OPERATION_SECONDS = 8 * 60


class MatrixFailure(Exception):
    def __init__(self, case: str, completed: list[dict[str, Any]], diagnostic=None):
        super().__init__("synthetic_matrix_case_failed")
        self.case = case
        self.completed = completed
        self.diagnostic = diagnostic


VALIDATION_REASONS = frozenset(
    {
        "status_or_redirect",
        "cache_policy",
        "content_policy",
        "upstream_contract",
        "stream_not_cancelled",
        "missing_auth_challenge",
        "error_body_bound",
        "error_envelope",
        "error_disclosure",
        "discovery_shape",
        "image_headers",
        "image_signature_or_origin",
    }
)
APPLICATION_CODES = frozenset(
    {
        "invalid_request",
        "invalid_token",
        "flickr_link_changed",
        "photo_thumbnail_unavailable",
        "existing_photo_discovery_unavailable",
        "service_unavailable",
        "not_found",
        "method_not_allowed",
        "insufficient_scope",
    }
)


def case_diagnostic(
    case: str, status: int | None, headers: dict[str, str], body: bytes | None, error: Exception
) -> dict[str, Any]:
    reason = "validation_unclassified"
    if isinstance(error, json.JSONDecodeError):
        reason = "invalid_json"
    elif isinstance(error, (KeyError, TypeError, IndexError)):
        reason = "invalid_envelope"
    elif isinstance(error, ValueError) and str(error) in VALIDATION_REASONS:
        reason = str(error)  # Only a closed known validator label, never arbitrary exception text.
    elif isinstance(error, ValueError) and str(error) == "response_byte_limit":
        reason = "response_limit"
    elif isinstance(error, (OSError, http.client.HTTPException)):
        reason = "transport_unconfirmed"

    def counter(name):
        value = headers.get(name, "")
        return int(value) if re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", value) else None

    code = "unavailable" if body is None else "not_app_json"
    if body is not None and len(body) <= 4096 and media_type(headers.get("content-type")) == "json":
        try:
            value = json.loads(body)
            candidate = value.get("error", {}).get("code") if isinstance(value, dict) else None
            code = (
                candidate
                if isinstance(candidate, str) and candidate in APPLICATION_CODES
                else "other"
            )
        except ValueError, TypeError, AttributeError:
            code = "malformed"
    expected_media = "image/jpeg" if case == "jpeg" else "image/png"
    return {
        "reason": reason,
        "status": status,
        "bodyBytes": len(body)
        if body is not None
        else 262145
        if reason == "response_limit"
        else None,
        "mediaType": media_type(headers.get("content-type"))
        if status is not None
        else "unavailable",
        "capCategory": "exceeded"
        if reason == "response_limit"
        else "within_limit"
        if body is not None
        else "unobserved",
        "applicationErrorCode": code,
        "headersObserved": status is not None,
        "observedPages": counter("x-probe-pages"),
        "observedImages": counter("x-probe-images"),
        "headerChecks": {
            "noLocation": "location" not in headers,
            "noStore": "no-store" in headers.get("cache-control", ""),
            "nosniff": headers.get("x-content-type-options") == "nosniff",
            "sameOrigin": headers.get("cross-origin-resource-policy") == "same-origin",
            "expectedImageMedia": headers.get("content-type") == expected_media,
            "lengthMatches": body is not None and headers.get("content-length") == str(len(body)),
            "cancelled": headers.get("x-probe-cancelled") == "true",
        },
    }


class EdgePreparationFailure(Exception):
    def __init__(self, diagnostic: dict[str, Any]):
        super().__init__("edge_preparation_unconfirmed")
        self.diagnostic = diagnostic


def media_type(value: str | None) -> str:
    if value is None:
        return "absent"
    mime = value.split(";", 1)[0].strip().lower()
    return {
        "application/json": "json",
        "text/html": "html",
        "text/plain": "text",
        "image/jpeg": "jpeg",
        "image/png": "png",
    }.get(mime, "other")


def preparation_exchange(
    origin: str, path: str, headers: dict[str, str], phase: str, attempt: int, diagnostic
) -> tuple[int, bytes, dict[str, Any]]:
    details: dict[str, Any] = {
        "phase": phase,
        "attempt": attempt,
        "reason": "pending",
        "status": None,
        "bodyBytes": None,
        "mediaType": "unavailable",
        "capCategory": "unobserved",
    }
    diagnostic(details.copy())
    try:
        status, received, body, _ = matrix.exchange(origin, path, headers)
    except Exception as error:
        if isinstance(error, ValueError) and str(error) == "response_byte_limit":
            details.update(reason="response_limit", bodyBytes=262145, capCategory="exceeded")
        elif isinstance(error, (OSError, http.client.HTTPException)):
            details.update(reason="transport_unconfirmed")
        else:
            details.update(reason="transport_validation")
        diagnostic(details.copy())
        raise EdgePreparationFailure(details) from error
    details.update(
        status=status,
        bodyBytes=len(body),
        mediaType=media_type(received.get("content-type")),
        capCategory="within_limit",
        reason="response_observed",
    )
    diagnostic(details.copy())
    return status, body, details


def success(status: int, value: dict[str, Any]) -> Any:
    if status not in (200, 201) or value.get("success") is not True:
        raise ValueError("provider_result_unconfirmed")
    return value.get("result")


class Provider:
    def __init__(self, account: str, token: str):
        self.account = account
        self.token = token

    def call(
        self, method: str, suffix: str, body=None, *, content_type=None
    ) -> tuple[int, dict[str, Any]]:
        data = body if content_type else None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/" + self.account + suffix,
            method=method,
            data=data,
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": content_type or "application/json",
            },
        )
        try:
            response = urllib.request.build_opener(NoRedirect).open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("provider_response_limit")
            value = json.loads(raw) if raw else {}
            if not isinstance(value, dict):
                raise ValueError("provider_response_shape")
            status = response.status
            if not isinstance(status, int):
                raise ValueError("provider_status_shape")
            return status, value


def bundle(directory: Path, config: dict[str, Any]) -> bytes:
    config_path = directory / "wrangler.json"
    save(config_path, config)
    out = directory / "bundle"
    # Building needs no provider credentials or inherited Wrangler profile.
    env = dict(os.environ)
    for name in list(env):
        if name.startswith(("CLOUDFLARE_", "CF_", "WRANGLER_", "FGA_")):
            del env[name]
    env["CI"] = "true"
    env["WRANGLER_SEND_METRICS"] = "false"
    env["WRANGLER_LOG_PATH"] = str(directory / "private-wrangler.log")
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(
            [
                "node",
                str(ROOT / "node_modules/wrangler/bin/wrangler.js"),
                "deploy",
                "--dry-run",
                "--config",
                str(config_path),
                "--outdir",
                str(out),
            ],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        output.seek(0)
        if result.returncode != 0 or len(output.read(65537)) > 65536:
            raise ValueError("local_bundle_unavailable")
    artifact = out / "worker.js"
    if not artifact.is_file() or artifact.stat().st_size > 3 * 1024 * 1024:
        raise ValueError("unexpected_bundle")
    if any(path.name not in {"worker.js", "worker.js.map", "README.md"} for path in out.iterdir()):
        raise ValueError("unexpected_bundle_module")
    return artifact.read_bytes()


def upload_metadata(database_id: str, access: str) -> dict[str, Any]:
    return {
        "main_module": "worker.js",
        "compatibility_date": DATE,
        "compatibility_flags": FLAGS,
        "logpush": False,
        "observability": {"enabled": False},
        "bindings": [
            {"type": "d1", "name": "DB", "id": database_id},
            {"type": "secret_text", "name": "PROBE_ACCESS_TOKEN", "text": access},
        ],
    }


def multipart(artifact: bytes, database_id: str, access: str) -> tuple[bytes, str]:
    boundary = "fga" + secrets.token_hex(24)
    metadata = upload_metadata(database_id, access)
    pieces = []
    for name, mime, value in [
        ("metadata", "application/json", json.dumps(metadata).encode()),
        ("worker.js", "application/javascript+module", artifact),
    ]:
        header = (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{name}"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'
        )
        pieces.extend([header.encode(), value, b"\r\n"])
    pieces.append(f"--{boundary}--\r\n".encode())
    return b"".join(pieces), "multipart/form-data; boundary=" + boundary


def run_matrix(
    origin: str, access: str, checkpoint=lambda: None, diagnostic=lambda _value: None
) -> list[dict[str, Any]]:
    # Readiness GETs are safe to repeat; seed and all mutating control calls are single-attempt.
    for attempt in range(10):
        checkpoint()
        try:
            status, body, details = preparation_exchange(
                origin,
                matrix.THUMBNAIL + matrix.QUERY,
                {},
                "gate_readiness",
                attempt + 1,
                diagnostic,
            )
        except EdgePreparationFailure as error:
            if error.diagnostic["reason"] != "transport_unconfirmed" or attempt == 9:
                raise
            time.sleep(1)
            continue
        if status == 404 and not body:
            break
        if attempt == 9 or status not in {404, 429, 500, 502, 503, 504}:
            details["reason"] = "unexpected_status" if status != 404 else "unexpected_body"
            diagnostic(details.copy())
            raise EdgePreparationFailure(details)
        time.sleep(1)
    checkpoint()
    status, body, details = preparation_exchange(
        origin, "/__probe/seed", {"X-Probe-Access": access}, "seed_fixture", 1, diagnostic
    )
    if status != 204 or body:
        details["reason"] = "unexpected_status" if status != 204 else "unexpected_body"
        diagnostic(details.copy())
        raise EdgePreparationFailure(details)
    diagnostic(
        {
            "phase": "matrix_cases",
            "attempt": 1,
            "reason": "started",
            "status": None,
            "bodyBytes": None,
            "mediaType": "unavailable",
            "capCategory": "unobserved",
        }
    )
    results = []
    for case in matrix.CASES:
        status = None
        received = {}
        body = None
        try:
            checkpoint()
            path, headers = matrix.case_request(case)
            headers["X-Probe-Access"] = access
            status, received, body, elapsed = matrix.exchange(origin, path, headers)
            matrix.validate(case, status, received, body)
        except Exception as error:
            raise MatrixFailure(
                case, results, case_diagnostic(case, status, received, body, error)
            ) from error
        results.append(
            {
                "case": case,
                "status": status,
                "bytes": len(body),
                "elapsedMs": elapsed,
                "passed": True,
            }
        )
    return results


def run(
    output: Path, *, provider: Any = None, build=bundle, exercise=run_matrix, identity=None
) -> int:
    name = "fga-photo-qualification-" + secrets.token_hex(12)
    deadline = time.monotonic() + OPERATION_SECONDS
    directory = output / "private" / name
    journal_path = directory / "journal.json"
    evidence_path = output / RECEIPT
    journal: dict[str, Any] = {
        "runName": name,
        "accountId": None,
        "databaseId": None,
        "workerId": None,
        "databaseAttempted": False,
        "workerAttempted": False,
        "databaseDeleted": False,
        "workerDeleted": False,
    }
    evidence: dict[str, Any] = {
        "schemaVersion": 1,
        "scope": "disposable_synthetic_edge_only",
        "runName": name,
        "databaseName": name + "-db",
        "startedAt": datetime.now(UTC).isoformat(),
        "compatibilityDate": DATE,
        "compatibilityFlags": FLAGS,
        "workersDev": True,
        "passed": False,
        "matrixPassed": False,
        "cleanupConfirmed": False,
        "cases": [],
        "errorClass": None,
        "sourceSha2_256": matrix.provenance(ROOT),
        "orchestratorSha2_256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    db = None
    worker = None
    api: Any = None
    evidence["stage"] = "credentials"

    def persist():
        evidence["recovery"] = {
            "databaseAttempted": journal["databaseAttempted"],
            "workerAttempted": journal["workerAttempted"],
            "databaseAcknowledged": journal["databaseId"] is not None,
            "workerAcknowledged": journal["workerId"] is not None,
            "databaseDeleted": journal["databaseDeleted"],
            "workerDeleted": journal["workerDeleted"],
        }
        save(journal_path, journal)
        save(evidence_path, evidence)

    def checkpoint():
        persist()
        # Reserve the remainder of the 14-minute CI step for one in-flight call,
        # acknowledged-resource cleanup and artifact retention. No mutation retry.
        if time.monotonic() >= deadline:
            raise TimeoutError("qualification_operation_deadline")

    def edge_diagnostic(value):
        evidence["edgePreparation"] = value
        evidence["stage"] = "edge_" + value["phase"]
        persist()

    persist()  # Nonsecret exact-name correlation survives even an early forced stop.
    print(json.dumps({"runName": name, "databaseName": name + "-db"}), flush=True)
    try:
        account, token = identity if identity is not None else credentials(None, from_env=True)
        api = provider if provider is not None else Provider(account, token)
        journal["accountId"] = account
        checkpoint()
        # A fresh random name must be absent before the single upload attempt.
        script = "/workers/scripts/" + name
        status, _ = api.call("GET", script + "/settings")
        if status != 404:
            raise ValueError("worker_name_not_unused")
        journal["databaseAttempted"] = True
        evidence["stage"] = "create_disposable_database"
        checkpoint()
        created = success(*api.call("POST", "/d1/database", {"name": name + "-db"}))
        candidate = created.get("uuid") if isinstance(created, dict) else None
        journal["returnedDatabaseId"] = candidate
        persist()
        if not isinstance(candidate, str) or str(uuid.UUID(candidate)) != candidate:
            raise ValueError("database_identity_unconfirmed")
        if created.get("name") != name + "-db":
            raise ValueError("database_name_unconfirmed")
        db = candidate
        journal["databaseId"] = db
        persist()  # Exact created ID durable before any subsequent operation.
        migrations = sorted((ROOT / "migrations").glob("*.sql"))
        evidence["stage"] = "apply_current_migrations"
        evidence["migrationsSha2_256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in migrations
        }
        for migration in migrations:
            checkpoint()
            result = success(
                *api.call(
                    "POST",
                    "/d1/database/" + db + "/query",
                    {
                        "batch": [
                            {"sql": sql, "params": []}
                            for sql in statements(migration.read_text(encoding="utf-8"))
                        ]
                    },
                )
            )
            if (
                not isinstance(result, list)
                or not result
                or any(row.get("success") is not True for row in result)
            ):
                raise ValueError("migration_unconfirmed")
        config = {
            "name": name,
            "main": str(ROOT / "probes/existing-photo-qualification/worker.ts"),
            "compatibility_date": DATE,
            "compatibility_flags": FLAGS,
            "workers_dev": True,
            "preview_urls": False,
            "observability": {"enabled": False},
            "d1_databases": [{"binding": "DB", "database_name": name + "-db", "database_id": db}],
        }
        evidence["stage"] = "bundle_fixed_probe"
        checkpoint()
        artifact = build(directory, config)
        evidence["artifactSha2_256"] = hashlib.sha256(artifact).hexdigest()
        evidence["dryRunConfigSha2_256"] = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()
        access = secrets.token_urlsafe(48)
        evidence["uploadMetadataSecretElidedSha2_256"] = hashlib.sha256(
            json.dumps(upload_metadata(db, "[SECRET_ELIDED]"), sort_keys=True).encode()
        ).hexdigest()
        body, content_type = multipart(artifact, db, access)
        journal["workerAttempted"] = True
        evidence["stage"] = "upload_fixed_worker"
        checkpoint()
        uploaded = success(*api.call("PUT", script, body, content_type=content_type))
        journal["returnedWorkerId"] = uploaded.get("id") if isinstance(uploaded, dict) else None
        persist()
        if not isinstance(uploaded, dict) or uploaded.get("id") != name:
            raise ValueError("worker_identity_unconfirmed")
        worker = name
        journal["workerId"] = worker
        persist()
        evidence["stage"] = "enable_disposable_workers_dev"
        checkpoint()
        enabled = success(
            *api.call("POST", script + "/subdomain", {"enabled": True, "previews_enabled": False})
        )
        if (
            not isinstance(enabled, dict)
            or enabled.get("enabled") is not True
            or enabled.get("previews_enabled") is not False
        ):
            raise ValueError("disposable_endpoint_unconfirmed")
        checkpoint()
        subdomain = success(*api.call("GET", "/workers/subdomain"))
        label = subdomain.get("subdomain") if isinstance(subdomain, dict) else None
        if not isinstance(label, str) or not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label
        ):
            raise ValueError("workers_subdomain_unconfirmed")
        evidence["stage"] = "synthetic_edge_matrix"
        checkpoint()
        if exercise is run_matrix:
            evidence["cases"] = exercise(
                f"https://{name}.{label}.workers.dev", access, checkpoint, edge_diagnostic
            )
        else:
            evidence["cases"] = exercise(f"https://{name}.{label}.workers.dev", access)
        evidence["matrixPassed"] = len(evidence["cases"]) == len(matrix.CASES) and all(
            row.get("passed") is True for row in evidence["cases"]
        )
    except Exception as error:
        # Never retain raw exceptions/provider payloads, URLs, headers or credentials.
        evidence["errorClass"] = type(error).__name__
        if isinstance(error, MatrixFailure):
            evidence["failedCase"] = error.case
            evidence["cases"] = error.completed
            if error.diagnostic is not None:
                evidence["caseFailure"] = error.diagnostic
        if isinstance(error, EdgePreparationFailure):
            edge_diagnostic(dict(error.diagnostic))
    finally:
        evidence["cleanupStarted"] = True
        persist()
        if worker and api is not None:
            try:
                success(*api.call("DELETE", "/workers/scripts/" + worker))
                status, _ = api.call("GET", "/workers/scripts/" + worker + "/settings")
                journal["workerDeleted"] = status == 404
                persist()
            except Exception:
                pass
        if db and api is not None:
            try:
                current = success(*api.call("GET", "/d1/database/" + db))
                if isinstance(current, dict) and current.get("name") == name + "-db":
                    success(*api.call("DELETE", "/d1/database/" + db))
                    status, _ = api.call("GET", "/d1/database/" + db)
                    journal["databaseDeleted"] = status == 404
                    persist()
            except Exception:
                pass
        clean = (not journal["databaseAttempted"] or journal["databaseDeleted"]) and (
            not journal["workerAttempted"] or journal["workerDeleted"]
        )
        evidence["cleanupConfirmed"] = clean
        evidence["passed"] = bool(evidence["matrixPassed"] and clean)
        evidence["completedAt"] = datetime.now(UTC).isoformat()
        persist()
    print(
        json.dumps(
            {
                "passed": evidence["passed"],
                "cleanupConfirmed": clean,
                "casesPassed": len(evidence["cases"]),
                "errorClass": evidence["errorClass"],
            }
        )
    )
    return 0 if evidence["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-env", action="store_true", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output_directory.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
