"""Build and black-box the isolated routing fixture locally AND on Cloudflare."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Timer
from typing import Any
from urllib.parse import urlsplit

from runtime_permissions_probe import (
    NODE,
    ROOT,
    ProbeError,
    Run,
    command,
    delete_worker_without_force,
    missing_worker,
    wrangler,
)

PROBE = ROOT / "probes/routes"
RUNS = ROOT / ".route-runs"
GENERATED = PROBE / "generated"
USER_AGENT = "FlickrGroupAddr-RouteConformance/0.0.0"
EXPIRE = (
    "__Host-fga_admin=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; "
    "Secure; HttpOnly; SameSite=Strict"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sources() -> dict[str, str]:
    files = [ROOT / n for n in ("package.json", "package-lock.json", "tsconfig.json")]
    files += [p for p in PROBE.iterdir() if p.suffix in {".ts", ".mjs"}]
    files += [Path(__file__), ROOT / "scripts/runtime_permissions_probe.py"]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(files)}


def generate(run: Run) -> dict[str, Any]:
    command(run, "typescript", [NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"])
    result = command(run, "registry", [NODE, str(PROBE / "export.mjs")])
    data = json.loads(result.stdout)
    for name, value in (
        ("route-inventory.json", data["inventory"]),
        ("openapi.json", data["openapi"]),
    ):
        write_json(GENERATED / name, value)
    assets = run.directory / "assets"
    script = b'"use strict";\ndocument.documentElement.dataset.routingProof = "ready";\n'
    asset_name = "proof." + hashlib.sha256(script).hexdigest()[:16] + ".js"
    asset = assets / "admin/assets" / asset_name
    asset.parent.mkdir(parents=True)
    asset.write_bytes(script)
    (assets / "admin/index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Routing proof</title>'
        '<h1>Isolated routing proof</h1><script src="/admin/assets/'
        + asset_name
        + '"></script></html>\n',
        encoding="utf-8",
    )
    # Deliberate colliding files catch an asset-first provider configuration.
    shadow_paths = sorted(
        {
            re.sub(r"\{[^}]+\}", "conformance-missing", r["pathPattern"])
            for r in data["inventory"]["routes"]
        }
    )
    for path in shadow_paths:
        shadow = assets / path.lstrip("/")
        # Keep leaf files at the exact handler paths to challenge asset precedence.
        if any(other.startswith(path + "/") for other in shadow_paths):
            shadow = shadow / "index.html"
        shadow.parent.mkdir(parents=True, exist_ok=True)
        shadow.write_text("<!doctype html><p>WRONG ASSET OWNER</p>", encoding="utf-8")
    write_json(
        run.directory / "asset-manifest.json",
        {"path": "/admin/assets/" + asset_name, "sha2_256": digest(asset)},
    )
    base = {
        "name": "fga-routing-proof-unconfigured",
        "main": str(PROBE / "worker.ts"),
        "compatibility_date": "2026-09-07",
        "workers_dev": False,
        "preview_urls": False,
        "observability": {"enabled": False},
        "vars": {"ROUTING_PROOF": "isolated-fixture"},
        "assets": {"directory": str(assets), **data["assetConfig"]},
    }
    write_json(run.directory / "build.json", base)
    wrangler(
        run,
        "build",
        "deploy",
        "--dry-run",
        "--config",
        str(run.directory / "build.json"),
        "--outdir",
        str(run.directory / "bundle"),
    )
    base.update({"main": str(run.directory / "bundle/worker.js"), "no_bundle": True})
    local = {**base, "compatibility_date": "2026-08-06"}
    write_json(run.directory / "local.json", local)
    write_json(run.directory / "deploy.json", base)
    run.state["artifactHashes"] = sources()
    for p in [
        *GENERATED.glob("*.json"),
        *assets.rglob("*"),
        run.directory / "bundle/worker.js",
        run.directory / "local.json",
        run.directory / "deploy.json",
    ]:
        if p.is_file():
            run.state["artifactHashes"][str(p.relative_to(ROOT)).replace("\\", "/")] = digest(p)
    run.save()
    return data["inventory"]


def matrix(inventory: dict[str, Any], asset: dict[str, str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def add(name: str, method: str, path: str, status: int, **extra: Any) -> None:
        cases.append({"id": name, "method": method, "path": path, "status": status, **extra})

    for r in inventory["routes"]:
        path = re.sub(r"\{[^}]+\}", "conformance-missing", r["pathPattern"])
        add(r["probe"], r["method"], path, r["expectedStatus"], boundary=r["authBoundary"])
        add(r["id"] + "_unsupported", "DELETE", path, 405)
        add(
            r["id"] + "_navigation",
            r["method"],
            path + "?probe=synthetic",
            r["expectedStatus"],
            boundary=r["authBoundary"],
            headers={"Sec-Fetch-Mode": "navigate", "Accept": "text/html"},
        )
    missing = [
        "/api",
        "/api/v001",
        "/api/debug",
        "/api/v001/__route_conformance_missing__",
        "/healthz/__route_conformance_missing__",
        "/api/v001/flickr-api-proxy/groups",
        "/api/v001/auth/device/token-check?device_type=lrc15_plugin",
        "/oauth",
        "/auth",
        "/admin/Google-login",
        "/admin/google-login/",
        "/admin/missing",
    ]
    for i, path in enumerate(missing):
        add(
            f"unknown_{i}",
            "GET",
            path,
            404,
            headers={"Sec-Fetch-Mode": "navigate", "Accept": "text/html"},
        )
    for i, path in enumerate(
        [
            "/api/v001/group-submission",
            "/api/v001/group-submissions",
            "/api/v001/group-submission-intents/conformance-id/retry-now",
            "/api/v001/admin/group-submission-intents/conformance-id/reopen",
            "/admin/__route_conformance_missing__",
        ]
    ):
        add(f"retired_mutation_{i}", "POST", path, 404)
    add("installation_wrong_method", "POST", "/api/v001/installations/current", 405)
    add("health_wrong_method", "POST", "/healthz/live", 405)
    add(
        "debug_headers",
        "GET",
        "/api/debug?probe=synthetic",
        404,
        headers={"Cookie": "synthetic=1", "Authorization": "Bearer synthetic"},
    )
    for endpoint in ["startup", "live"]:
        add(
            "health_headers_" + endpoint,
            "GET",
            "/healthz/" + endpoint + "?synthetic=1",
            200,
            boundary="health",
            headers={
                "Cookie": "synthetic=1",
                "Authorization": "Bearer synthetic",
                "Origin": "https://invalid.example",
                "Accept": "text/html",
            },
        )
    for i, path in enumerate(
        [
            "/api/%2fdebug",
            "/api/%5cdebug",
            "/api/%252fdebug",
            "/api/%00",
            "/api/%",
            "/api/%ff",
            "/admin%2f",
            "/admin\\",
        ]
    ):
        add(f"malformed_{i}", "GET", path, 400)
    add("admin_shell", "GET", "/admin/", 200, boundary="shell")
    add("admin_shell_head", "HEAD", "/admin/", 200, boundary="shell")
    add("admin_shell_unsafe", "POST", "/admin/", 405)
    add("asset", "GET", asset["path"], 200, boundary="asset", sha2_256=asset["sha2_256"])
    add("asset_unsafe", "POST", asset["path"], 405)
    add("missing_asset", "GET", "/admin/assets/missing.js", 404)
    add(
        "logout_wrong_origin",
        "POST",
        "/api/v001/admin/session/logout",
        403,
        headers={"Origin": "https://invalid.example"},
    )
    return cases


def probe(origin: str, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target = urlsplit(origin)
    if target.scheme not in {"http", "https"} or not target.hostname or target.path:
        raise ProbeError("Invalid probe origin.")
    results = []
    for case in cases:
        headers = {"User-Agent": USER_AGENT, **case.get("headers", {})}
        if case.get("boundary") == "logout":
            headers["Origin"] = origin
        cls = (
            http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        )
        connection = cls(target.hostname, target.port, timeout=15)
        try:
            # http.client preserves malformed escapes instead of normalizing the test path.
            connection.request(case["method"], case["path"], headers=headers)
            reply = connection.getresponse()
            body = reply.read(65537)
            h = {k.lower(): v for k, v in reply.getheaders()}
            errors = []
            if reply.status != case["status"]:
                errors.append("status")
            if len(body) > 65536 or "location" in h:
                errors.append("body_or_redirect")
            boundary = case.get("boundary")
            if h.get("cache-control") != "no-store":
                errors.append("cache")
            if case["method"] == "HEAD" and body:
                errors.append("head_body")
            if boundary == "shell":
                if not h.get("content-type", "").startswith("text/html"):
                    errors.append("shell_type")
                if case["method"] != "HEAD" and b"Isolated routing proof" not in body:
                    errors.append("shell_bytes")
                if h.get(
                    "referrer-policy"
                ) != "no-referrer" or "frame-ancestors 'none'" not in h.get(
                    "content-security-policy", ""
                ):
                    errors.append("shell_security")
            elif boundary == "asset":
                if hashlib.sha256(body).hexdigest() != case[
                    "sha2_256"
                ] or "javascript" not in h.get("content-type", ""):
                    errors.append("asset_bytes_or_type")
            elif case["status"] != 204:
                if h.get("content-type", "").split(";")[0] != "application/json":
                    errors.append("json_type")
                if case["method"] != "HEAD":
                    try:
                        decoded = json.loads(body)
                        expected = (
                            {"schemaVersion": 1, "status": "ok"} if boundary == "health" else None
                        )
                        if expected is not None and decoded != expected:
                            errors.append("health_schema")
                        elif expected is None and (
                            not isinstance(decoded, dict) or set(decoded) != {"error"}
                        ):
                            errors.append("error_schema")
                    except ValueError:
                        errors.append("json_body")
            if (h.get("www-authenticate") == "Bearer") != (boundary == "bearer"):
                errors.append("challenge")
            if boundary == "logout":
                if body or h.get("set-cookie") != EXPIRE:
                    errors.append("logout")
            elif "set-cookie" in h:
                errors.append("cookie")
            if boundary == "health" and any(
                k in h for k in ("etag", "last-modified", "age", "access-control-allow-origin")
            ):
                errors.append("health_headers")
            error_code = re.search(rb"error code: (\d+)", body)
            results.append(
                {
                    "id": case["id"],
                    "status": reply.status,
                    "passed": not errors,
                    "errors": errors,
                    "mediaType": h.get("content-type", "").split(";")[0],
                    "bodySha2_256": hashlib.sha256(body).hexdigest(),
                    "providerErrorCode": error_code.group(1).decode() if error_code else None,
                }
            )
        finally:
            connection.close()
    return results


def local(run: Run, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with (run.directory / "local-server.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen(
            [NODE, str(PROBE / "local.mjs"), str(run.directory / "local.json")],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            encoding="utf-8",
        )
        startup_timeout = Timer(30, child.terminate)
        startup_timeout.daemon = True
        startup_timeout.start()
        try:
            assert child.stdout is not None
            for _ in range(30):
                line = child.stdout.readline()
                if not line:
                    raise ProbeError("Local asset router did not start; inspect private log.")
                try:
                    ready = json.loads(line)
                except ValueError:
                    continue
                if ready.get("url"):
                    startup_timeout.cancel()
                    results = probe(ready["url"], cases)
                    break
            else:
                raise ProbeError("Local asset router did not report readiness.")
        finally:
            startup_timeout.cancel()
            stdout, _ = child.communicate(timeout=30)
        summary = json.loads(stdout.strip().splitlines()[-1])
        if child.returncode or summary.get("outboundCalls") != 0:
            raise ProbeError("Local router shutdown or dependency isolation failed.")
        return results


def hosted(run: Run, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identity = json.loads(wrangler(run, "identity", "whoami", "--json").stdout)
    if not identity.get("loggedIn") or len(identity.get("accounts", [])) != 1:
        raise ProbeError("Exactly one authenticated Cloudflare account is required.")
    name = "fga-" + run.run_id
    run.state.update(
        accountId=identity["accounts"][0]["id"], workerName=name, databaseName=name + "-db"
    )
    run.save()
    previous = wrangler(
        run, "preflight", "deployments", "list", "--name", name, "--json", allow_failure=True
    )
    if not missing_worker(previous):
        raise ProbeError("Generated preview name is not proven unused.")
    config_path = run.directory / "deploy.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.update(name=name, account_id=run.state["accountId"], workers_dev=True)
    write_json(config_path, config)
    run.state["artifactHashes"][config_path.relative_to(ROOT).as_posix()] = digest(config_path)
    run.state["workerAttempted"] = True
    run.save()
    deployed = wrangler(run, "deploy", "deploy", "--config", str(config_path))
    found = re.search(
        r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev\b", deployed.stdout
    )
    if not found:
        raise ProbeError("Expected isolated preview URL absent.")
    before = wrangler(
        run, "deployment-before", "deployments", "list", "--name", name, "--json"
    ).stdout
    run.state["deployment"] = json.loads(before)
    run.state["url"] = found.group(0)
    run.save()
    readiness = [
        case
        for case in cases
        if case["id"] in {"live_get_safe", "installation_current_safe", "admin_shell"}
    ]
    samples = []
    consecutive = 0
    settling_started = time.monotonic()
    for _ in range(60):
        sample = probe(found.group(0), readiness)
        samples.append(sample)
        consecutive = consecutive + 1 if all(row["passed"] for row in sample) else 0
        if consecutive >= 5 and time.monotonic() - settling_started >= 30:
            break
        time.sleep(1)
    else:
        write_json(run.directory / "readiness.json", samples)
        raise ProbeError("Preview did not become ready; inspect readiness.json.")
    write_json(run.directory / "readiness.json", samples)
    results = probe(found.group(0), cases)
    run.state["firstHostedMatrix"] = results
    run.save()
    results = probe(found.group(0), cases)
    after = wrangler(
        run, "deployment-after", "deployments", "list", "--name", name, "--json"
    ).stdout
    if json.loads(before) != json.loads(after):
        raise ProbeError("Preview deployment changed during probing.")
    return results


def cleanup(run: Run) -> None:
    if run.state.get("workerAttempted"):
        delete_worker_without_force(run)
        check = wrangler(
            run,
            "cleanup-check",
            "deployments",
            "list",
            "--name",
            run.state["workerName"],
            "--json",
            allow_failure=True,
        )
        if not missing_worker(check):
            raise ProbeError("Preview cleanup unconfirmed.")
        run.state["cleanupConfirmed"] = True
        run.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "cleanup"))
    parser.add_argument("--run-directory")
    args = parser.parse_args()
    if args.action == "cleanup":
        directory = Path(args.run_directory or "").resolve()
        if directory.parent != RUNS.resolve() or not re.fullmatch(
            r"rp-[a-f0-9]{24}", directory.name
        ):
            raise ProbeError("Invalid routing run directory.")
        run = Run(directory, json.loads((directory / "manifest.json").read_text(encoding="utf-8")))
        if run.run_id != directory.name:
            raise ProbeError("Run identity mismatch.")
        cleanup(run)
        return 0
    run_id = "rp-" + secrets.token_hex(12)
    directory = RUNS / run_id
    directory.mkdir(parents=True)
    run = Run(directory, {"runId": run_id, "environment": "cloudflare"})
    run.save()
    print(f"Routing run: {run_id}", flush=True)
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "scope": "isolated-routing-proof",
        "productionConformance": False,
    }
    try:
        inventory = generate(run)
        cases = matrix(
            inventory, json.loads((directory / "asset-manifest.json").read_text(encoding="utf-8"))
        )
        write_json(directory / "cases.json", cases)
        report["local"] = local(run, cases)
        write_json(directory / "report.json", report)
        # Collect both real boundaries even on a mismatch; neither can approve the other.
        report["cloudflare"] = hosted(run, cases)
        report["cloudflareInitial"] = run.state["firstHostedMatrix"]
        write_json(directory / "report.json", report)
        if any(digest(ROOT / p) != d for p, d in run.state["artifactHashes"].items()):
            raise ProbeError("Build artifacts changed during the gate.")
        report.update(
            passed=all(
                row["passed"]
                for phase in ("local", "cloudflareInitial", "cloudflare")
                for row in report[phase]
            ),
            at=datetime.now(UTC).isoformat(),
            artifactHashes=run.state["artifactHashes"],
            deployment=run.state["deployment"],
            localCompatibilityDate="2026-08-06",
            hostedCompatibilityDate="2026-09-07",
        )
    finally:
        cleanup(run)
        report["cleanupConfirmed"] = run.state.get("cleanupConfirmed", False)
        write_json(directory / "report.json", report)
    if not report.get("passed"):
        raise ProbeError("Routing matrix failed; both environments are recorded in report.json.")
    print(
        json.dumps(
            {
                "passed": report.get("passed", False),
                "casesPerEnvironment": len(cases),
                "cleanupConfirmed": report["cleanupConfirmed"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ProbeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(
            str(error) if isinstance(error, ProbeError) else type(error).__name__, file=sys.stderr
        )
        sys.exit(1)
