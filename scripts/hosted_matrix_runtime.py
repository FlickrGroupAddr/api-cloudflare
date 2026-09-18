"""Supplement the killable adapter with the exact module on the hosted runtime."""

from __future__ import annotations

import http.client
import json
import re
import shutil
import time
from typing import TYPE_CHECKING

from scripts import bootstrap_deployment as bootstrap
from scripts import fail_polite_release as gate
from scripts import runtime_permissions_probe as runtime
from scripts.matrix_native import ControlError

if TYPE_CHECKING:
    from scripts.production_matrix import Matrix


def hosted_runtime(matrix: Matrix):
    native = matrix.native_bridge
    proof = matrix.proof
    if native is None or proof is None:
        raise ValueError("hosted_native_fixtures_required")
    name = proof.name + "-runtime"
    try:
        native.call("GET", "workers/scripts/" + name + "/settings")
    except ControlError as error:
        if error.status != 404:
            raise
    else:
        raise ValueError("hosted_runtime_name_collision")
    folder = matrix.directory / "hosted-runtime"
    folder.mkdir()
    shutil.copyfile(matrix.artifact, folder / "production.mjs")
    shutil.copyfile(runtime.ROOT / "probes/release/hosted-entry.mjs", folder / "entry.mjs")
    assert gate.digest(folder / "production.mjs") == gate.digest(matrix.artifact)
    database = matrix.settings["databaseId"]
    config = folder / "wrangler.json"
    bootstrap.save(
        config,
        {
            "name": name,
            "account_id": proof.operator.account_id,
            "main": str(folder / "entry.mjs"),
            "no_bundle": True,
            "find_additional_modules": True,
            "rules": [{"type": "ESModule", "globs": ["**/*.mjs"], "fallthrough": True}],
            "compatibility_date": "2026-09-18",
            "compatibility_flags": ["nodejs_compat"],
            "workers_dev": True,
            "preview_urls": False,
            "observability": {"enabled": False},
            "d1_databases": [
                {
                    "binding": "DB",
                    "database_id": database,
                    "database_name": next(k for k, v in proof.owned.items() if v == database),
                }
            ],
            "secrets_store_secrets": [
                {"binding": binding, "store_id": native.store, "secret_name": native.names[key]}
                for binding, key in [
                    ("FLICKR_GRANT", "GRANT"),
                    ("FLICKR_APPLICATION", "APPLICATION"),
                ]
            ],
            "vars": {
                "MATRIX_TOKEN": matrix.token,
                "MATRIX_EXPIRES": str(int((time.time() + 1800) * 1000)),
                "FGA_ARTIFACT_SHA2_256": gate.digest(matrix.artifact),
            },
        },
    )
    bootstrap.save(folder / "ownership.json", {"name": name, "attempted": True})
    report = {
        "scope": "hosted-production-runtime-supplement",
        "fullConformancePassed": False,
        "workerArtifactSha2_256": gate.digest(matrix.artifact),
        "workersCompatibilityDate": "2026-09-18",
        "liveFlickrCalls": 0,
        "cases": [],
    }
    run = runtime.Run(folder, {"accountId": proof.operator.account_id})
    try:
        deployed = runtime.wrangler(run, "deploy", "deploy", "--config", str(config))
        urls = re.findall(
            r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev", deployed.stdout
        )
        if not urls:
            raise RuntimeError("hosted_runtime_url_missing")
        url = urls[0]

        def request(body=None):
            from urllib.parse import urlsplit

            parsed = urlsplit(url)
            connection = http.client.HTTPSConnection(parsed.hostname, timeout=30)
            try:
                connection.request(
                    "GET" if body is None else "POST",
                    "/",
                    body=None if body is None else json.dumps(body),
                    headers={
                        "Authorization": "Bearer " + matrix.token,
                        "Content-Type": "application/json",
                        "User-Agent": "FlickrGroupAddr-RuntimeProof/1",
                    },
                )
                response = connection.getresponse()
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("hosted_runtime_response_over_budget")
                if response.status != 200:
                    report.setdefault("httpFailures", []).append(
                        {
                            "status": response.status,
                            "bodyBytes": len(raw),
                            "contentType": response.getheader("Content-Type", "")[:100],
                            "method": "GET" if body is None else "POST",
                        }
                    )
                    raise ValueError("hosted_runtime_http_" + str(response.status))
                return json.loads(raw)
            finally:
                connection.close()

        def ready():
            started = time.monotonic()
            deadline = started + 120
            consecutive = 0
            while time.monotonic() < deadline:
                try:
                    if request().get("ready") is not True:
                        raise ValueError("hosted_runtime_not_ready")
                    consecutive += 1
                    if consecutive >= 5 and time.monotonic() - started >= 30:
                        return
                except OSError, ValueError, http.client.HTTPException:
                    consecutive = 0
                time.sleep(2)
            raise RuntimeError("hosted_runtime_readiness_did_not_converge")

        ready()
        case = matrix.seed("FP-PRE-008-hosted-runtime")
        fast = request({"partitionId": case.partition})
        ok = fast["state"]["state"] == "moderation_submitted" and len(fast["calls"]) == 3
        report["cases"].append({"id": "hosted-prepared-handoff", "passed": ok, "witness": fast})
        if not ok:
            raise RuntimeError("hosted_normal_handoff_failed")
        runtime.wrangler(run, "redeploy", "deploy", "--config", str(config))
        ready()
        repeated = request({"partitionId": case.partition})
        ok = repeated["state"]["state"] == "moderation_submitted" and not repeated["calls"]
        report["cases"].append(
            {"id": "hosted-deployment-restart", "passed": ok, "witness": repeated}
        )
        if not ok:
            raise RuntimeError("hosted_redeployment_lost_protection")
        case = matrix.seed("FP-PRE-010-hosted-runtime")
        expired = request({"partitionId": case.partition, "delayAfterMarker": True})
        ok = (
            expired["state"]["state"] == "retrying"
            and expired["state"]["add_dispatch_count"] == 0
            and expired["handoffAt"] is None
        )
        report["cases"].append(
            {"id": "hosted-io-refreshed-expiry", "passed": ok, "witness": expired}
        )
        if not ok:
            raise RuntimeError("hosted_expired_request_dispatched")
        print("Hosted exact-module runtime and deployment restart: passed", flush=True)
    finally:
        native.call("DELETE", "workers/scripts/" + name)
        try:
            native.call("GET", "workers/scripts/" + name + "/settings")
        except ControlError as error:
            if error.status != 404:
                raise
            report["cleanupConfirmed"] = True
        bootstrap.save(folder / "report.json", report)
    if report.get("cleanupConfirmed") is not True:
        raise RuntimeError("hosted_runtime_cleanup_unconfirmed")
    return report
