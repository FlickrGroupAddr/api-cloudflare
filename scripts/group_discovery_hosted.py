"""Disposable synthetic Worker/D1 proof; never touches production resources or Flickr."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from scripts.bootstrap_deployment import file_token
from scripts.native_secret_probe import deploy_with_bearer
from scripts.runtime_permissions_probe import NODE, ROOT, NoRedirect, Run, command, wrangler


def control(method: str, route: str, token: str, body: Any = None) -> tuple[int, Any]:
    request = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/" + route,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        response = urllib.request.build_opener(NoRedirect).open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        value = json.loads(response.read(2_097_152))
        status = response.status
        if not isinstance(status, int):
            raise RuntimeError("invalid_http_status")
        return status, value


def cleanup(run: Run, token: str) -> bool:
    state = run.state
    name = state["runId"]
    if not re.fullmatch(r"fga-groups-[a-f0-9]{16}", name):
        raise RuntimeError("unowned_resource_name")
    prefix = "accounts/" + state["accountId"]
    ok = True
    if state.get("workerAttempted"):
        status, _ = control("DELETE", prefix + "/workers/scripts/" + name, token)
        ok = status in {200, 404} and ok
    if state.get("databaseId"):
        route = prefix + "/d1/database/" + state["databaseId"]
        status, value = control("GET", route, token)
        if status == 200 and value.get("result", {}).get("name") == name:
            status, _ = control("DELETE", route, token)
            ok = status in {200, 204} and ok
        elif status != 404:
            ok = False
        status, _ = control("GET", route, token)
        ok = status == 404 and ok
    state["cleanupConfirmed"] = ok
    run.save()
    return ok


def request(base: str, path: str, token: str) -> tuple[int, Any]:
    req = urllib.request.Request(
        base + path,
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "FlickrGroupAddr-GroupDiscoveryProof/1",
            "Accept": "application/json",
        },
    )
    try:
        response = urllib.request.build_opener(NoRedirect).open(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(2_097_152)
        status = response.status
        if not isinstance(status, int):
            raise RuntimeError("invalid_http_status")
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        return status, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--cleanup-run")
    args = parser.parse_args()
    token = file_token(args.token_file)
    os.environ["CLOUDFLARE_API_TOKEN"] = token
    root = ROOT / ".coordination-runs"
    if args.cleanup_run:
        if not re.fullmatch(r"fga-groups-[a-f0-9]{16}", args.cleanup_run):
            raise RuntimeError("invalid_run")
        directory = root / args.cleanup_run
        run = Run(directory, json.loads((directory / "manifest.json").read_text()))
        return 0 if cleanup(run, token) else 1
    name = "fga-groups-" + secrets.token_hex(8)
    directory = root / name
    directory.mkdir(parents=True)
    account = json.loads((root / "fga-runtime-inputs.json").read_text())["accountId"]
    run = Run(directory, {"runId": name, "accountId": account})
    run.save()
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "scope": "group-discovery-synthetic-hosted",
        "startedAt": datetime.now(UTC).isoformat(),
        "compatibilityDate": "2026-09-18",
        "productionModified": False,
        "liveFlickrCalls": 0,
        "passed": False,
    }
    try:
        status, created = control("POST", f"accounts/{account}/d1/database", token, {"name": name})
        if status != 200 or not created.get("success"):
            raise RuntimeError("create_disposable_database_failed")
        run.state["databaseId"] = created["result"]["uuid"]
        run.save()
        config = {
            "name": name,
            "account_id": account,
            "main": str(ROOT / "probes/groups/worker.ts"),
            "compatibility_date": "2026-09-18",
            "compatibility_flags": ["nodejs_compat"],
            "workers_dev": True,
            "preview_urls": False,
            "observability": {"enabled": False},
            "vars": {"PROOF_EXPIRES": str(int((time.time() + 600) * 1000))},
            "d1_databases": [
                {
                    "binding": "DB",
                    "database_name": name,
                    "database_id": run.state["databaseId"],
                    "migrations_dir": str(ROOT / "migrations"),
                }
            ],
        }
        config_path = directory / "wrangler.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        command(run, "typescript", [NODE, "node_modules/typescript/bin/tsc", "--noEmit"])
        wrangler(
            run,
            "migrate",
            "d1",
            "migrations",
            "apply",
            name,
            "--remote",
            "--config",
            str(config_path),
        )
        wrangler(
            run,
            "build",
            "deploy",
            "--dry-run",
            "--config",
            str(config_path),
            "--outdir",
            str(directory / "bundle"),
        )
        bundle = directory / "bundle/worker.js"
        report["artifactSha2_256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
        config.update(main=str(bundle), no_bundle=True)
        config_path.write_text(json.dumps(config), encoding="utf-8")
        run.state["workerAttempted"] = True
        run.save()
        bearer = secrets.token_urlsafe(32)
        deployed = deploy_with_bearer(run, config_path, bearer)
        found = re.search(r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev", deployed)
        if found is None:
            raise RuntimeError("probe_url_unavailable")
        base = found.group(0)
        run.state["url"] = base
        run.save()
        # Account routing propagation can lag upload across Cloudflare locations.
        # Match the hosted-runtime proof's stable, bounded readiness boundary.
        report["preflightStatuses"] = []
        started = time.monotonic()
        consecutive = 0
        while time.monotonic() - started < 120:
            try:
                status, _ = request(base, "/api/v001/groups?page_size=2", "invalid")
                report["preflightStatuses"].append(status)
                if status == 401:
                    consecutive += 1
                    if consecutive >= 5 and time.monotonic() - started >= 30:
                        break
                else:
                    consecutive = 0
            except OSError, ValueError:
                consecutive = 0
            time.sleep(2)
        else:
            raise RuntimeError("probe_not_reachable")
        if request(base, "/probe/seed", bearer)[0] != 200:
            raise RuntimeError("seed_failed")
        code = "0000-" * 12 + "0000"
        if request(base, "/api/v001/groups?page_size=2", code)[0] != 202:
            raise RuntimeError("first_read_failed")
        if request(base, "/probe/refresh", bearer)[0] != 200:
            raise RuntimeError("refresh_failed")
        status, first = request(base, "/api/v001/groups?page_size=2", code)
        if (
            status != 200
            or first.get("snapshotRevision") != 1
            or first.get("snapshotStatus") != "fresh"
        ):
            raise RuntimeError("snapshot_failed")
        if [g["flickrGroupId"] for g in first["groups"]] != ["A", "a"]:
            raise RuntimeError("ordering_failed")
        status, last = request(
            base, "/api/v001/groups?page_size=2&snapshot_revision=1&after_group_id=a", code
        )
        if (
            status != 200
            or last.get("nextAfterGroupId") is not None
            or last["groups"][0]["flickrGroupId"] != "z"
        ):
            raise RuntimeError("continuation_failed")
        if (
            request(
                base, "/api/v001/groups?page_size=2&snapshot_revision=2&after_group_id=a", code
            )[0]
            != 409
        ):
            raise RuntimeError("revision_guard_failed")
        report.update(
            passed=True,
            checks=[
                "missing_authentication",
                "first_snapshot_pending",
                "whole_refresh",
                "binary_order",
                "continuation",
                "revision_conflict",
            ],
        )
    except (OSError, ValueError, RuntimeError) as error:
        # No raw provider response, URL, bearer, or exception text in public evidence.
        report["failureClass"] = type(error).__name__
        safe_failures = {
            "create_disposable_database_failed",
            "probe_url_unavailable",
            "probe_not_reachable",
            "seed_failed",
            "first_read_failed",
            "refresh_failed",
            "snapshot_failed",
            "ordering_failed",
            "continuation_failed",
            "revision_guard_failed",
        }
        report["failureCode"] = str(error) if str(error) in safe_failures else "probe_step_failed"
    finally:
        try:
            report["cleanupConfirmed"] = cleanup(run, token)
        except OSError, ValueError, RuntimeError:
            report["cleanupConfirmed"] = False
        report["completedAt"] = datetime.now(UTC).isoformat()
        target = ROOT / "docs/evidence/group-discovery-hosted-2026-09-18.json"
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    return 0 if report["passed"] and report["cleanupConfirmed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
