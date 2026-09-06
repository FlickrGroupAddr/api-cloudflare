"""Run the isolated #0007 capability probe; never a production conformance gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".probe-runs"
NODE = shutil.which("node") or "node"
USER_AGENT = "FlickrGroupAddr-RuntimePermissionProbe/0.0.0"
WRANGLER = ROOT / "node_modules/wrangler/bin/wrangler.js"
PROBE = ROOT / "probes/runtime-permissions"
ACTIONS = (
    "read",
    "insert",
    "update",
    "delete",
    "replace",
    "upsert",
    "cascade",
    "check_enforced",
    "foreign_key_enforced",
    "drop_update_guard",
    "drop_delete_guard",
    "drop_table",
    "rename_table",
    "disable_check",
)
GUARDS = {
    "update": "denied_guard",
    "delete": "denied_guard",
    "replace": "denied_guard",
    "upsert": "denied_guard",
    "cascade": "denied_guard",
    "check_enforced": "denied_check",
    "foreign_key_enforced": "denied_foreign_key",
}


class ProbeError(RuntimeError):
    """A bounded, safe-to-print probe failure."""


@dataclass
class Run:
    directory: Path
    state: dict[str, Any]

    @property
    def run_id(self) -> str:
        return self.state["runId"]

    def save(self) -> None:
        target = self.directory / "manifest.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)


def new_run(environment: str) -> Run:
    run_id = "rp-" + secrets.token_hex(12)
    directory = RUNS / run_id
    directory.mkdir(parents=True)
    run = Run(directory, {"runId": run_id, "environment": environment})
    run.save()
    (directory / "secret.json").write_text(
        json.dumps({"PROBE_TOKEN": secrets.token_urlsafe(32)}), encoding="utf-8"
    )
    return run


def load_run(directory: str) -> Run:
    resolved = Path(directory).resolve()
    if resolved.parent != RUNS.resolve() or not re.fullmatch(r"rp-[a-f0-9]{24}", resolved.name):
        raise ProbeError("Run directory must be an immediate child of .probe-runs.")
    state = json.loads((resolved / "manifest.json").read_text(encoding="utf-8"))
    if state.get("runId") != resolved.name:
        raise ProbeError("Run manifest does not match its directory.")
    return Run(resolved, state)


def command(
    run: Run,
    stage: str,
    args: list[str],
    *,
    input_text: str | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "WRANGLER_SEND_METRICS": "false",
            "WRANGLER_WRITE_LOGS": "false",
            "WRANGLER_LOG_SANITIZE": "true",
            "CI": "true",
            "NO_COLOR": "1",
        }
    )
    if run.state.get("accountId"):
        environment["CLOUDFLARE_ACCOUNT_ID"] = run.state["accountId"]
    print(f"Probe step: {stage}", flush=True)
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    (run.directory / f"{stage}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode and not allow_failure:
        raise ProbeError(f"{stage} failed (exit {result.returncode}); inspect its private run log.")
    return result


def wrangler(run: Run, stage: str, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return command(run, stage, [NODE, str(WRANGLER), *args], **kwargs)


ARTIFACT_FILES = (
    "package-lock.json",
    "package.json",
    "tsconfig.json",
    "probes/runtime-permissions/worker.ts",
    "probes/runtime-permissions/cases.ts",
    "probes/runtime-permissions/wrangler.jsonc",
    "scripts/runtime_permissions_probe.py",
    "probes/runtime-permissions/local.mjs",
    ".probe-build/worker.js",
)


def artifact_hashes(*, include_bundle: bool = True) -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ARTIFACT_FILES
        if include_bundle or name != ".probe-build/worker.js"
    }


def build(run: Run) -> None:
    before = artifact_hashes(include_bundle=False)
    command(run, "typescript", [NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"])
    wrangler(
        run,
        "build",
        "deploy",
        "--dry-run",
        "--config",
        str(PROBE / "wrangler.jsonc"),
        "--outdir",
        str(ROOT / ".probe-build"),
    )
    command(run, "fixture", [NODE, str(PROBE / "local.mjs"), "setup", str(run.directory)])

    after = artifact_hashes()
    if any(after[name] != digest for name, digest in before.items()):
        raise ProbeError("Probe source changed during the build.")
    run.state["artifactHashes"] = after
    run.save()


def verify_report(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schemaVersion") != 1 or report.get("productionConformance") is not False:
        raise ProbeError("Invalid report schema or production-conformance claim.")
    if report.get("environment") not in {"local", "cloudflare"}:
        raise ProbeError("Unknown evidence environment.")
    expected = {f"{family}.{action}" for family in ("blocks", "audit") for action in ACTIONS}
    violations: dict[str, list[str]] = {}
    inconclusive: dict[str, list[str]] = {}
    count = 0
    for backend in ("d1", "durableObject"):
        cases = report.get(backend, {}).get("cases", [])
        ids = [case.get("id") for case in cases]
        required = expected | ({"storage.delete_all"} if backend == "durableObject" else set())
        if len(ids) != len(set(ids)) or set(ids) != required:
            raise ProbeError(f"{backend}: missing, duplicate or unknown case IDs.")
        violations[backend], inconclusive[backend] = [], []
        for case in cases:
            before, after = case["before"], case["after"]
            if not before["tableExists"] or before["rowCount"] != 1 or not before["originalIntact"]:
                raise ProbeError(f"{backend}: invalid baseline for {case['id']}.")
            action = case["id"].split(".", 1)[1]
            expected_triggers = 2 if action in {"check_enforced", "disable_check"} else 3
            if before["triggerCount"] != expected_triggers or before["invalidCheckRows"] != 0:
                raise ProbeError("Fixture guards or checks are missing.")
            kind = (
                "control"
                if action in {"read", "insert"}
                else ("guard" if action in GUARDS else "capability")
            )
            if case["kind"] != kind:
                raise ProbeError("Case category drift.")
            changed = before != after
            forbidden = kind != "control" and changed
            if case["forbiddenChangeObserved"] is not forbidden:
                raise ProbeError("Reported capability finding disagrees with observed state.")
            execution = case["execution"]
            if execution not in {
                "allowed",
                "denied_guard",
                "denied_check",
                "denied_foreign_key",
                "operation_error",
            }:
                raise ProbeError("Unknown execution result.")
            if action == "read" and (execution != "allowed" or changed):
                raise ProbeError("Read control failed.")
            if action == "insert" and (
                execution != "allowed"
                or after["rowCount"] != 2
                or not after["originalIntact"]
                or not after["addedIntact"]
            ):
                raise ProbeError("Insert control failed.")
            if action in GUARDS and (execution != GUARDS[action] or changed):
                raise ProbeError(f"{backend}: expected constraint control failed: {case['id']}.")
            if forbidden:
                violations[backend].append(case["id"])
            if execution == "operation_error":
                inconclusive[backend].append(case["id"])
            count += 1
    return {
        "observedCases": count,
        "runtimeProtection": "violated" if any(violations.values()) else "unproven",
        "forbiddenChanges": violations,
        "inconclusiveCases": inconclusive,
    }


def finish_report(run: Run, report: dict[str, Any]) -> None:
    summary = verify_report(report)
    if report["environment"] != run.state["environment"] or report["runId"] != run.run_id:
        raise ProbeError("Report belongs to a different run.")
    hashes = artifact_hashes()
    if hashes != run.state.get("artifactHashes"):
        raise ProbeError("Probe source changed during execution; evidence refused.")
    report["summary"] = summary
    report["provenance"] = {
        "collectedAt": datetime.now(UTC).isoformat(),
        "hashAlgorithm": "SHA2-256",
        "fileHashes": hashes,
        "toolVersions": {
            name: json.loads(
                (ROOT / "node_modules" / name / "package.json").read_text(encoding="utf-8")
            )["version"]
            for name in ("typescript", "wrangler", "miniflare")
        },
        "node": subprocess.check_output([NODE, "--version"], text=True).strip(),
        "compatibilityDateRequested": "2026-09-06",
    }
    serialized = json.dumps(report, indent=2) + "\n"
    token = json.loads((run.directory / "secret.json").read_text())["PROBE_TOKEN"]
    if token in serialized:
        raise ProbeError("Probe token appeared in evidence; publication refused.")
    (run.directory / "report.json").write_text(serialized, encoding="utf-8")
    print(json.dumps(summary), flush=True)


def local(run: Run) -> None:
    build(run)
    command(run, "local", [NODE, str(PROBE / "local.mjs"), "local", str(run.directory)])
    finish_report(run, json.loads((run.directory / "report.json").read_text(encoding="utf-8")))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def http_json(
    url: str, token: str | None, method: str = "POST", *, timeout: int = 30
) -> tuple[int, dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        reply = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        reply = error
    with reply:
        raw = reply.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ProbeError("Probe response exceeded its fixed byte budget.")
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            match = re.search(rb"error code:\s*([0-9]{3,5})", raw)
            detail = f" (Cloudflare {match[1].decode()})" if match else ""
            raise ProbeError(f"Probe returned non-JSON HTTP {reply.status}{detail}.") from error
        if not isinstance(data, dict):
            raise ProbeError("Probe response is not an object.")
        status = reply.status
        if not isinstance(status, int):
            raise ProbeError("Probe response has no HTTP status.")
        return status, data


def databases(run: Run, stage: str) -> list[dict[str, Any]]:
    data = json.loads(wrangler(run, stage, "d1", "list", "--json").stdout)
    if not isinstance(data, list):
        raise ProbeError("Unexpected D1 inventory response.")
    return data


def missing_worker(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 0 and bool(re.search(r"\b10007\b", result.stdout + result.stderr))


def checked_resource_names(run: Run) -> tuple[str, str]:
    if run.state.get("environment") != "cloudflare":
        raise ProbeError("Remote actions require a Cloudflare run manifest.")
    name = "fga-" + run.run_id
    database = name + "-db"
    if run.state.get("workerName") != name or run.state.get("databaseName") != database:
        raise ProbeError("Resource names do not match this generated probe run.")
    return name, database


def provision(run: Run) -> None:
    identity = json.loads(wrangler(run, "identity", "whoami", "--json").stdout)
    accounts = identity.get("accounts", [])
    if not identity.get("loggedIn") or len(accounts) != 1:
        raise ProbeError("A working Wrangler login with exactly one selected account is required.")
    name = "fga-" + run.run_id
    run.state.update(
        {
            "accountId": accounts[0]["id"],
            "workerName": name,
            "databaseName": name + "-db",
        }
    )
    run.save()
    name, database = checked_resource_names(run)
    previous = wrangler(
        run,
        "worker-preflight",
        "deployments",
        "list",
        "--name",
        name,
        "--json",
        allow_failure=True,
    )
    if not missing_worker(previous):
        raise ProbeError("Could not establish that the generated Worker name is unused.")
    if any(row["name"] == database for row in databases(run, "database-preflight")):
        raise ProbeError("Generated database name already exists.")
    run.state["databaseAttempted"] = True
    run.save()
    wrangler(run, "database-create", "d1", "create", database, "--update-config=false")
    matches = [row for row in databases(run, "database-created") if row["name"] == database]
    if len(matches) != 1:
        raise ProbeError("Could not resolve the newly created probe database.")
    run.state["databaseId"] = matches[0]["uuid"]
    run.state["databaseCreated"] = True
    run.save()
    config = json.loads((PROBE / "wrangler.jsonc").read_text(encoding="utf-8"))
    config.update(
        {
            "name": name,
            "main": str(PROBE / "worker.ts"),
            "account_id": run.state["accountId"],
            "workers_dev": True,
            "preview_urls": False,
            "vars": {"PROBE_RUN_ID": run.run_id, "PROBE_MODE": "cloudflare"},
            "d1_databases": [
                {"binding": "DB", "database_name": database, "database_id": run.state["databaseId"]}
            ],
        }
    )
    (run.directory / "wrangler.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    wrangler(
        run,
        "fixture-provision",
        "d1",
        "execute",
        "DB",
        "--remote",
        "--config",
        str(run.directory / "wrangler.json"),
        "--file",
        str(run.directory / "fixture.sql"),
        "--yes",
    )
    run.state["workerAttempted"] = True
    run.save()
    deployed = wrangler(
        run, "worker-deploy", "deploy", "--config", str(run.directory / "wrangler.json")
    )
    found = re.search(
        r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev\b", deployed.stdout
    )
    version = re.search(r"Current Version ID:\s*([a-f0-9-]{36})", deployed.stdout)
    if not found or not version:
        raise ProbeError("Deployment did not return the expected probe URL and version.")
    run.state.update(
        {
            "workerDeployed": True,
            "url": found.group(0),
            "deploymentVersion": version.group(1),
        }
    )
    run.save()
    wrangler(
        run,
        "probe-secret",
        "secret",
        "bulk",
        "--config",
        str(run.directory / "wrangler.json"),
        input_text=(run.directory / "secret.json").read_text(encoding="utf-8"),
    )


def current_deployment(run: Run, stage: str) -> dict[str, Any]:
    name, _ = checked_resource_names(run)
    items = json.loads(wrangler(run, stage, "deployments", "list", "--name", name, "--json").stdout)
    if not isinstance(items, list) or not items:
        raise ProbeError("Could not identify the deployed probe version.")
    latest = max(items, key=lambda item: item["created_on"])
    return {"id": latest["id"], "versions": latest["versions"]}


def collect_remote(run: Run) -> dict[str, Any]:
    name, _ = checked_resource_names(run)
    url = run.state["url"]
    if not re.fullmatch(r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev", url):
        raise ProbeError("Unexpected hosted probe origin.")
    token = json.loads((run.directory / "secret.json").read_text())["PROBE_TOKEN"]
    for attempt in range(6):
        try:
            status, _ = http_json(url + "/run", None, timeout=5)
        except ProbeError, urllib.error.URLError:
            status = 0
        if status == 401:
            break
        if attempt == 5:
            raise ProbeError("Probe readiness or missing-token control did not succeed.")
        time.sleep(1)
    deployed_before = current_deployment(run, "deployed-artifact-before")
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "environment": "cloudflare",
        "runId": run.run_id,
        "productionConformance": False,
        "d1": {"cases": []},
        "durableObject": {"cases": []},
    }
    phases = (len(ACTIONS) * 2 + 3) // 4 + 1
    for phase in range(phases):
        print(f"Probe phase: {phase + 1}/{phases}", flush=True)
        status, part = http_json(url + "/run", token)
        (run.directory / f"phase-{phase}.json").write_text(
            json.dumps(part, indent=2) + "\n", encoding="utf-8"
        )
        backend = "d1" if phase < phases - 1 else "durableObject"
        if status != 200 or part.get("phase") != phase or part.get("phaseCount") != phases:
            raise ProbeError(
                f"Phase {phase} incomplete; never automatically replay a lost response."
            )
        if part.get("backend") != backend or part.get("runId") != run.run_id:
            raise ProbeError("Hosted phase identity mismatch.")
        if (
            part.get("environment") != "cloudflare"
            or part.get("productionConformance") is not False
        ):
            raise ProbeError("Hosted phase scope mismatch.")
        result = part["result"]
        for key in ("sqliteVersion", "sqliteVersionObservation"):
            if key in report[backend] and report[backend][key] != result[key]:
                raise ProbeError("Database version observation changed during the run.")
            report[backend][key] = result[key]
        report[backend]["cases"].extend(result["cases"])
    status, _ = http_json(url + "/run", token)
    if status != 409:
        raise ProbeError("A completed probe run could be repeated.")
    deployed_after = current_deployment(run, "deployed-artifact-after")
    if deployed_before != deployed_after:
        raise ProbeError("Probe deployment changed while collecting evidence.")
    report["harness"] = {
        "deployedArtifact": deployed_after,
        "checks": ["missing_token", "second_run_refused"],
        "phases": phases,
        "deploymentVersionBeforeSecretInstall": run.state["deploymentVersion"],
    }
    return report


def delete_worker_without_force(run: Run) -> int:
    name, _ = checked_resource_names(run)
    account = run.state.get("accountId", "")
    if not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ProbeError("Invalid probe account identity.")
    environment = os.environ.copy()
    environment.update(
        {
            "WRANGLER_SEND_METRICS": "false",
            "WRANGLER_WRITE_LOGS": "false",
            "WRANGLER_LOG_SANITIZE": "true",
            "CI": "true",
            "NO_COLOR": "1",
        }
    )
    # Intentionally bypass command(): its diagnostic log must never receive a token.
    auth = subprocess.run(
        [NODE, str(WRANGLER), "auth", "token", "--json"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if auth.returncode:
        raise ProbeError("Could not obtain in-memory Cloudflare cleanup authority.")
    credential = json.loads(auth.stdout)
    if credential.get("type") not in {"oauth", "api_token"} or not credential.get("token"):
        raise ProbeError("Cleanup requires Wrangler OAuth or API-token authentication.")
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/services/{name}?force=false",
        headers={"Authorization": "Bearer " + credential["token"], "User-Agent": USER_AGENT},
        method="DELETE",
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        reply = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        reply = error
    with reply:
        status = reply.status
        if not isinstance(status, int):
            raise ProbeError("Cleanup response has no HTTP status.")
        data = json.loads(reply.read(1_048_576))
        if not data.get("success") and status != 404:
            raise ProbeError(f"Non-forcing Worker deletion refused (HTTP {status}).")
    return status


def cleanup(run: Run) -> None:
    name, database = checked_resource_names(run)
    failures = []
    if run.state.get("workerAttempted") and not run.state.get("workerDeleted"):
        delete_status = delete_worker_without_force(run)
        check = wrangler(
            run,
            "worker-deleted-check",
            "deployments",
            "list",
            "--name",
            name,
            "--json",
            allow_failure=True,
        )
        if missing_worker(check):
            run.state["workerDeleted"] = True
        else:
            failures.append(f"Worker cleanup unconfirmed (HTTP {delete_status}).")
        run.save()
    if run.state.get("databaseAttempted") and not run.state.get("databaseDeleted"):
        matches = [
            row for row in databases(run, "database-cleanup-inventory") if row["name"] == database
        ]
        if len(matches) > 1:
            raise ProbeError("Ambiguous cleanup target; no database deletion attempted.")
        if matches:
            expected_id = run.state.get("databaseId")
            if expected_id and matches[0]["uuid"] != expected_id:
                raise ProbeError("Database identity changed; no deletion attempted.")
            wrangler(run, "database-delete", "d1", "delete", database, "--skip-confirmation")
        remaining = databases(run, "database-deleted-check")
        if any(row["name"] == database for row in remaining):
            failures.append("Database cleanup unconfirmed.")
        else:
            run.state["databaseDeleted"] = True
        run.save()
    if failures:
        raise ProbeError(" ".join(failures))
    run.state["cleanupConfirmed"] = True
    run.save()
    (run.directory / "secret.json").unlink(missing_ok=True)
    print("Probe cleanup confirmed.", flush=True)


def cloudflare(run: Run) -> None:
    build(run)
    try:
        provision(run)
        report = collect_remote(run)
        finish_report(run, report)
    finally:
        if run.state.get("databaseAttempted") or run.state.get("workerAttempted"):
            cleanup(run)
    report = json.loads((run.directory / "report.json").read_text(encoding="utf-8"))
    report["cleanup"] = {"confirmed": run.state.get("cleanupConfirmed", False)}
    (run.directory / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("local", "cloudflare", "cleanup"))
    parser.add_argument("--run", help="Existing .probe-runs directory; cleanup only.")
    args = parser.parse_args()
    if (args.action == "cleanup") != bool(args.run):
        parser.error("--run is required only for cleanup")
    run = load_run(args.run) if args.run else new_run(args.action)
    print(f"Run directory: {run.directory}", flush=True)
    try:
        if args.action == "local":
            local(run)
            (run.directory / "secret.json").unlink(missing_ok=True)
        elif args.action == "cloudflare":
            cloudflare(run)
        else:
            cleanup(run)
    except (ProbeError, subprocess.TimeoutExpired, urllib.error.URLError) as error:
        run.state["failureCategory"] = type(error).__name__
        run.save()
        print(f"Probe stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
