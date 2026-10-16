"""Fixed two-Worker/one-D1 native-network preparation and same-job cleanup."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from scripts.controlled_trial_pause_hosted import credentials, save
from scripts.existing_photo_qualification_hosted import Provider, bundle, success

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".coordination-runs/existing-photo-native-network"
PACKET = ROOT / "probes/existing-photo-native-network"
DATE = "2026-10-16"


def upload_metadata(bindings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "main_module": "worker.js",
        "compatibility_date": DATE,
        "observability": {"enabled": False},
        "logpush": False,
        "bindings": bindings,
    }


def upload(artifact: bytes, bindings: list[dict[str, str]]) -> tuple[bytes, str]:
    boundary = "fga" + secrets.token_hex(24)
    metadata = upload_metadata(bindings)
    parts = []
    for name, mime, body in [
        ("metadata", "application/json", json.dumps(metadata).encode()),
        ("worker.js", "application/javascript+module", artifact),
    ]:
        parts.extend(
            [
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                    f'filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'
                ).encode(),
                body,
                b"\r\n",
            ]
        )
    return b"".join(
        parts
    ) + f"--{boundary}--\r\n".encode(), "multipart/form-data; boundary=" + boundary


def persist(out: Path, journal: dict[str, Any]) -> None:
    save(out / "private/journal.json", journal)
    # Whitelist projection: private account, exact resource IDs and credentials never escape.
    receipt = {
        key: journal[key]
        for key in (
            "schemaVersion",
            "runId",
            "runName",
            "expiresAtUnix",
            "stage",
            "ready",
            "databaseAttempted",
            "databaseDeleted",
            "workers",
            "errorClass",
            "cleanupConfirmed",
            "stopReason",
            "counters",
            "artifactSha2_256",
            "schemaSha2_256",
            "dryRunConfigSha2_256",
        )
    }
    receipt["sourceSha2_256"] = journal["sourceSha2_256"]
    receipt["workers"] = [
        {
            key: worker[key]
            for key in (
                "name",
                "attempted",
                "acknowledged",
                "deleteAttempted",
                "deleted",
                "uploadMetadataSecretElidedSha2_256",
            )
        }
        for worker in journal["workers"]
    ]
    receipt["counters"] = [
        {key: row[key] for key in ("role", "requests", "receiver_requests")}
        for row in journal["counters"]
    ]
    save(out / "cleanup.json", receipt)


def cleanup(api, out: Path, journal: dict[str, Any]) -> None:
    journal["stage"] = "cleanup"
    persist(out, journal)
    for worker in reversed(journal["workers"]):
        if not worker["acknowledged"] or worker["deleted"]:
            continue
        try:
            path = "/workers/scripts/" + worker["name"]
            status, _ = api.call("GET", path + "/settings")
            if status == 404:
                worker["deleted"] = True
            elif status == 200 and not worker["deleteAttempted"]:
                worker["deleteAttempted"] = True
                persist(out, journal)
                success(*api.call("DELETE", path))
                status, _ = api.call("GET", path + "/settings")
                worker["deleted"] = status == 404
        except Exception:
            pass
        persist(out, journal)
    if journal["databaseId"] and not journal["databaseDeleted"]:
        try:
            path = "/d1/database/" + journal["databaseId"]
            status, current = api.call("GET", path)
            if status == 404:
                journal["databaseDeleted"] = True
            elif (
                status == 200
                and current.get("success") is True
                and current.get("result", {}).get("name") == journal["runName"]
                and not journal["databaseDeleteAttempted"]
            ):
                journal["databaseDeleteAttempted"] = True
                persist(out, journal)
                success(*api.call("DELETE", path))
                status, _ = api.call("GET", path)
                journal["databaseDeleted"] = status == 404
        except Exception:
            pass
    journal["cleanupConfirmed"] = (
        not journal["databaseAttempted"] or journal["databaseDeleted"]
    ) and all(not worker["attempted"] or worker["deleted"] for worker in journal["workers"])
    journal["stage"] = "cleanup_complete" if journal["cleanupConfirmed"] else "cleanup_unconfirmed"
    persist(out, journal)


def prepare(
    out: Path,
    api,
    account: str,
    github_run: str,
    gate: str,
    canary: str,
    build=bundle,
    clock=time.time,
) -> int:
    if (out / "private/journal.json").exists():
        raise ValueError("preparation_already_attempted")
    run_id = secrets.token_hex(12)
    name = "fga-native-network-db-" + run_id
    journal: dict[str, Any] = {
        "schemaVersion": 1,
        "runId": run_id,
        "runName": name,
        "accountId": account,
        "githubRunId": github_run,
        "expiresAtUnix": int(clock()) + 1200,
        "stage": "preparation",
        "ready": False,
        "databaseId": None,
        "databaseAttempted": False,
        "databaseDeleteAttempted": False,
        "databaseDeleted": False,
        "workers": [],
        "errorClass": None,
        "cleanupConfirmed": False,
        "stopReason": None,
        "counters": [],
        "artifactSha2_256": None,
        "dryRunConfigSha2_256": None,
        "schemaSha2_256": hashlib.sha256((PACKET / "schema.sql").read_bytes()).hexdigest(),
    }
    journal["sourceSha2_256"] = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            PACKET / "worker.ts",
            PACKET / "jpeg.ts",
            Path(__file__),
            ROOT / ".github/workflows/existing-photo-native-network.yml",
        )
    }
    for role in ("source", "receiver"):
        journal["workers"].append(
            {
                "role": role,
                "name": "fga-native-network-" + ("src-" if role == "source" else "recv-") + run_id,
                "attempted": False,
                "acknowledged": False,
                "deleteAttempted": False,
                "deleted": False,
                "uploadMetadataSecretElidedSha2_256": None,
            }
        )
    persist(out, journal)
    print(json.dumps({"runId": run_id, "runName": name}), flush=True)
    deadline = clock() + 240

    def checkpoint(stage):
        journal["stage"] = stage
        persist(out, journal)
        if clock() >= deadline:
            raise TimeoutError("preparation_deadline")

    try:
        if not re.fullmatch(r"[a-f0-9]{64}", gate) or not re.fullmatch(
            r"SYNTHETIC-[a-f0-9]{32}", canary
        ):
            raise ValueError("synthetic_inputs_unavailable")
        for worker in journal["workers"]:
            checkpoint("check_exact_worker_absence")
            status, _ = api.call("GET", "/workers/scripts/" + worker["name"] + "/settings")
            if status != 404:
                raise ValueError("fresh_worker_name_unconfirmed")
        checkpoint("create_database")
        journal["databaseAttempted"] = True
        persist(out, journal)
        created = success(*api.call("POST", "/d1/database", {"name": name}))
        candidate = created.get("uuid") if isinstance(created, dict) else None
        journal["returnedDatabaseId"] = candidate
        persist(out, journal)
        if (
            not isinstance(candidate, str)
            or str(uuid.UUID(candidate)) != candidate
            or created.get("name") != name
        ):
            raise ValueError("created_database_unconfirmed")
        journal["databaseId"] = candidate
        checkpoint("seed_fixed_schema")
        initialized = success(
            *api.call(
                "POST",
                "/d1/database/" + candidate + "/query",
                {
                    "batch": [
                        {"sql": (PACKET / "schema.sql").read_text(), "params": []},
                        *[
                            {
                                "sql": "INSERT INTO network_probe_budget "
                                "(run_id,role,expires_at_unix) VALUES(?,?,?)",
                                "params": [run_id, role, journal["expiresAtUnix"]],
                            }
                            for role in ("source", "receiver")
                        ],
                    ]
                },
            )
        )
        if (
            not isinstance(initialized, list)
            or len(initialized) != 3
            or any(row.get("success") is not True for row in initialized)
        ):
            raise ValueError("schema_initialization_unconfirmed")
        checkpoint("read_account_workers_label")
        label = success(*api.call("GET", "/workers/subdomain")).get("subdomain")
        if not isinstance(label, str) or not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label
        ):
            raise ValueError("workers_label_unconfirmed")
        config = {
            "name": journal["workers"][0]["name"],
            "main": str(PACKET / "worker.ts"),
            "compatibility_date": DATE,
            "workers_dev": True,
            "preview_urls": False,
            "observability": {"enabled": False},
            "d1_databases": [{"binding": "DB", "database_name": name, "database_id": candidate}],
        }
        checkpoint("bundle_fixed_artifact")
        journal["dryRunConfigSha2_256"] = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()
        artifact = build(out / "private", config)
        journal["artifactSha2_256"] = hashlib.sha256(artifact).hexdigest()
        for worker in journal["workers"]:
            checkpoint("upload_fixed_worker")
            bindings = [
                {"type": "d1", "name": "DB", "id": candidate},
                *[
                    {"type": "plain_text", "name": key, "text": value}
                    for key, value in {
                        "ROLE": worker["role"],
                        "RUN_ID": run_id,
                        "WORKERS_DEV_SUBDOMAIN": label,
                        "EXPIRES_AT_UNIX": str(journal["expiresAtUnix"]),
                    }.items()
                ],
                {"type": "secret_text", "name": "ACCESS_TOKEN", "text": gate},
                {"type": "secret_text", "name": "CANARY_TOKEN", "text": canary},
            ]
            body, content_type = upload(artifact, bindings)
            elided = [
                {**binding, "text": "[SECRET_ELIDED]"}
                if binding["type"] == "secret_text"
                else dict(binding)
                for binding in bindings
            ]
            worker["uploadMetadataSecretElidedSha2_256"] = hashlib.sha256(
                json.dumps(upload_metadata(elided), sort_keys=True).encode()
            ).hexdigest()
            worker["attempted"] = True
            persist(out, journal)
            uploaded = success(
                *api.call(
                    "PUT", "/workers/scripts/" + worker["name"], body, content_type=content_type
                )
            )
            worker["returnedId"] = uploaded.get("id") if isinstance(uploaded, dict) else None
            persist(out, journal)
            if not isinstance(uploaded, dict) or uploaded.get("id") != worker["name"]:
                raise ValueError("worker_upload_unconfirmed")
            worker["acknowledged"] = True
            checkpoint("enable_exact_worker_endpoint")
            enabled = success(
                *api.call(
                    "POST",
                    "/workers/scripts/" + worker["name"] + "/subdomain",
                    {"enabled": True, "previews_enabled": False},
                )
            )
            if (
                not isinstance(enabled, dict)
                or enabled.get("enabled") is not True
                or enabled.get("previews_enabled") is not False
            ):
                raise ValueError("endpoint_enable_unconfirmed")
        checkpoint("ready")
        if journal["expiresAtUnix"] - clock() < 300:
            raise TimeoutError("insufficient_native_window")
        save(
            out / "ready.json",
            {
                "schemaVersion": 1,
                "planVersion": "fga-native-network-v1",
                "runId": run_id,
                "workersDevSubdomain": label,
                "expiresAtUnix": journal["expiresAtUnix"],
            },
        )
        journal["ready"] = True
        persist(out, journal)
        return 0
    except Exception as error:
        journal["ready"] = False
        journal["errorClass"] = type(error).__name__
        return 1
    finally:
        if not journal["ready"]:
            cleanup(api, out, journal)


def hold_cleanup(
    out: Path,
    api,
    account: str,
    github_run: str,
    *,
    published: bool,
    clock=time.time,
    sleep=time.sleep,
) -> int:
    path = out / "private/journal.json"
    if not path.is_file():
        return 1  # Preparation never reached resource operations.
    journal = json.loads(path.read_text())
    run_id = journal.get("runId", "")
    if (
        journal.get("accountId") != account
        or journal.get("githubRunId") != github_run
        or not re.fullmatch(r"[a-f0-9]{24}", run_id)
        or journal.get("runName") != "fga-native-network-db-" + run_id
    ):
        raise ValueError("same_job_journal_unconfirmed")
    expected = ["fga-native-network-src-" + run_id, "fga-native-network-recv-" + run_id]
    if [worker.get("name") for worker in journal["workers"]] != expected:
        raise ValueError("same_job_worker_identity_unconfirmed")
    database = journal.get("databaseId")
    if database is not None and str(uuid.UUID(database)) != database:
        raise ValueError("same_job_database_identity_unconfirmed")
    try:
        journal["stopReason"] = "ready_not_published"
        if journal["ready"] and published:
            if not isinstance(database, str):
                raise ValueError("ready_database_identity_unconfirmed")
            journal["stage"] = "waiting_for_final_report"
            journal["stopReason"] = "expiry"
            persist(out, journal)
            for _ in range(121):
                if clock() >= journal["expiresAtUnix"]:
                    break
                result = success(
                    *api.call(
                        "POST",
                        "/d1/database/" + database + "/query",
                        {
                            "sql": "SELECT role,requests,receiver_requests "
                            "FROM network_probe_budget WHERE run_id=? ORDER BY role",
                            "params": [run_id],
                        },
                    )
                )
                if (
                    not isinstance(result, list)
                    or len(result) != 1
                    or result[0].get("success") is not True
                ):
                    raise ValueError("counter_observation_unconfirmed")
                rows = result[0].get("results")
                if (
                    not isinstance(rows, list)
                    or len(rows) != 2
                    or {row.get("role") for row in rows} != {"source", "receiver"}
                    or any(
                        type(row.get(key)) is not int or not 0 <= row[key] <= 32
                        for row in rows
                        for key in ("requests", "receiver_requests")
                    )
                ):
                    raise ValueError("counter_shape_unconfirmed")
                journal["counters"] = rows
                persist(out, journal)
                receiver = next(row for row in rows if row["role"] == "receiver")
                if receiver["requests"] - receiver["receiver_requests"] >= 2:
                    journal["stopReason"] = "final_receiver_report_observed"
                    journal["stage"] = "final_report_grace"
                    persist(out, journal)
                    sleep(min(60, max(0, journal["expiresAtUnix"] - clock())))
                    break
                sleep(min(10, max(0, journal["expiresAtUnix"] - clock())))
    except Exception as error:
        journal["errorClass"] = type(error).__name__
    finally:
        cleanup(api, out, journal)
    return 0 if journal["cleanupConfirmed"] and journal["errorClass"] is None else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "hold-cleanup"))
    args = parser.parse_args()
    try:
        if os.environ.get("GITHUB_ACTIONS") != "true" or not re.fullmatch(
            r"[0-9]+", os.environ.get("GITHUB_RUN_ID", "")
        ):
            raise ValueError("same_job_ci_required")
        account, token = credentials(None, from_env=True)
        api, github_run = Provider(account, token), os.environ["GITHUB_RUN_ID"]
        if args.phase == "prepare":
            return prepare(
                OUT,
                api,
                account,
                github_run,
                os.environ.get("FGA_NATIVE_NETWORK_ACCESS_TOKEN", ""),
                os.environ.get("FGA_NATIVE_NETWORK_CANARY_TOKEN", ""),
            )
        return hold_cleanup(
            OUT,
            api,
            account,
            github_run,
            published=os.environ.get("FGA_NATIVE_NETWORK_READY_PUBLISHED") == "success",
        )
    except Exception as error:
        print(json.dumps({"errorClass": type(error).__name__, "cleanupConfirmed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
