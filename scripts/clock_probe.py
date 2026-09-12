"""Observe deployed clock freshness limitations using isolated native resources."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from . import coordination_probe as coordination
    from . import runtime_permissions_probe as runtime
    from .native_secret_probe import deploy_with_bearer
except ImportError:
    import coordination_probe as coordination
    import runtime_permissions_probe as runtime
    from native_secret_probe import deploy_with_bearer

ROOT = runtime.ROOT
PROBE = ROOT / "probes/clocks"


def hashes() -> dict[str, str]:
    files = [
        *PROBE.glob("*.ts"),
        *PROBE.glob("*.mjs"),
        *PROBE.glob("*.sql"),
        ROOT / "src/dispatch_freshness.ts",
        ROOT / "src/installations.ts",
        Path(__file__),
        ROOT / "scripts/coordination_probe.py",
        ROOT / "scripts/runtime_permissions_probe.py",
        ROOT / "scripts/native_secret_probe.py",
        ROOT / "package-lock.json",
        ROOT / "package.json",
        ROOT / "tsconfig.json",
    ]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
        if p.is_file()
    }


def configuration(run: runtime.Run) -> Path:
    data: dict[str, Any] = {
        "name": run.state["workerName"],
        "main": str(PROBE / "worker.ts"),
        "compatibility_date": "2026-09-11",
        "compatibility_flags": ["nodejs_compat", "global_fetch_strictly_public"],
        "workers_dev": True,
        "preview_urls": False,
        "observability": {"enabled": False},
        "minify": True,
        "limits": {"cpu_ms": 5000},
        "vars": {"PROOF_BUILD": run.run_id, "PROOF_EXPIRES": str(int((time.time() + 1800) * 1000))},
        "durable_objects": {"bindings": [{"name": "COORD", "class_name": "ProbePartitionWake"}]},
        "exports": {"ProbePartitionWake": {"type": "durable-object", "storage": "sqlite"}},
        "triggers": {"crons": []},
    }
    if run.state.get("accountId"):
        data.update(
            account_id=run.state["accountId"],
            d1_databases=[
                {
                    "binding": "DB",
                    "database_name": run.state["databaseName"],
                    "database_id": run.state["databaseId"],
                }
            ],
        )
    path = run.directory / "wrangler.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def build(run: runtime.Run, path: Path) -> Path:
    runtime.command(
        run, "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
    )
    runtime.wrangler(
        run,
        "clock-build",
        "deploy",
        "--dry-run",
        "--config",
        str(path),
        "--outdir",
        str(run.directory / "bundle"),
    )
    bundle = run.directory / "bundle/worker.js"
    run.state["bundleSha2_256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    run.save()
    return bundle


def provision(run: runtime.Run, token: str) -> None:
    coordination.create_database(run)
    path = configuration(run)
    runtime.wrangler(
        run,
        "clock-schema",
        "d1",
        "execute",
        run.state["databaseName"],
        "--remote",
        "--file",
        str(PROBE / "schema.sql"),
        "--yes",
        "--json",
    )
    bundle = build(run, path)
    config = json.loads(path.read_text())
    config.update(main=str(bundle), no_bundle=True, find_additional_modules=False, minify=False)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
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
        raise runtime.ProbeError("Generated Worker name already exists.")
    run.state["workerAttempted"] = True
    run.save()
    output = deploy_with_bearer(run, path, token)
    urls = set(re.findall(r"https://[a-z0-9.-]+\.workers\.dev", output))
    if len(urls) != 1:
        raise runtime.ProbeError("Ambiguous clock Worker URL.")
    run.state["url"] = urls.pop()
    run.save()
    owned = coordination.namespaces(run)
    if len(owned) != 1 or owned[0].get("class") != "ProbePartitionWake":
        raise runtime.ProbeError("Unexpected clock namespace.")
    run.state["namespaceId"] = owned[0]["id"]
    run.save()


def local(run: runtime.Run, token: str) -> tuple[subprocess.Popen[str], Any]:
    path = configuration(run)
    bundle = build(run, path)
    config = json.loads(path.read_text())
    local_config = {
        "bundle": str(bundle),
        "vars": config["vars"],
        "statements": coordination.statements((PROBE / "schema.sql").read_text()),
    }
    config_path = run.directory / "local.json"
    config_path.write_text(json.dumps(local_config), encoding="utf-8")
    log = (run.directory / "local-stderr.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [runtime.NODE, str(PROBE / "local.mjs"), str(config_path)],
        cwd=ROOT,
        env={**os.environ, "FGA_CLOCK_TOKEN": token},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=log,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    assert process.stdout is not None
    line = process.stdout.readline()
    if not line:
        raise runtime.ProbeError("Local clock runtime did not start.")
    run.state["url"] = json.loads(line)["url"]
    run.save()
    return process, log


class Client:
    def __init__(self, run: runtime.Run, token: str):
        self.run, self.token = run, token

    def call(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urlsplit(self.run.state["url"])
        if self.run.state["environment"] == "cloudflare":
            if (
                url.scheme != "https"
                or not url.hostname
                or not url.hostname.endswith(".workers.dev")
            ):
                raise runtime.ProbeError("Unexpected hosted URL.")
            cls = http.client.HTTPSConnection
        else:
            if url.scheme != "http" or url.hostname != "127.0.0.1":
                raise runtime.ProbeError("Unexpected local URL.")
            cls = http.client.HTTPConnection
        conn = cls(url.hostname, url.port, timeout=30)
        started = time.monotonic_ns()
        try:
            conn.request(
                "GET" if data is None else "POST",
                "/status" if data is None else "/proof",
                None if data is None else json.dumps(data).encode(),
                {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            )
            response = conn.getresponse()
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                diagnostic = {}
                try:
                    body = json.loads(raw)
                    diagnostic = {k: body.get(k) for k in ("stage", "category")}
                except ValueError:
                    normalized = raw.decode("utf-8", "replace").replace(self.token, "[redacted]")
                    match = re.search(r"error code:\s*(\d{3,5})", normalized, re.I)
                    diagnostic = {
                        "edgeCode": match[1] if match else None,
                        "bodySha2_256": hashlib.sha256(raw).hexdigest(),
                    }
                self.run.state["lastFailure"] = {"status": response.status, **diagnostic}
                self.run.save()
                raise runtime.ProbeError(
                    "Clock request failed HTTP " + str(response.status) + " " + str(diagnostic)
                )
            result = json.loads(raw)
            if result["build"] != self.run.run_id:
                raise runtime.ProbeError("Clock build mismatch.")
            result["result"]["roundTripMonoMs"] = (time.monotonic_ns() - started) / 1e6
            return result["result"]
        finally:
            conn.close()

    def ready(self) -> None:
        started = time.monotonic()
        deadline = started + 120
        consecutive = 0
        while time.monotonic() < deadline:
            try:
                self.call()
                consecutive += 1
                if consecutive >= 5 and time.monotonic() - started >= 30:
                    return
            except runtime.ProbeError, OSError, ValueError, http.client.HTTPException:
                consecutive = 0
            time.sleep(2)
        raise runtime.ProbeError("Clock readiness did not converge.")


def cases(client: Client, report: coordination.Report) -> None:
    for target in ("worker", "object"):

        def invoke(name: str, target: str = target, **values: Any) -> dict[str, Any]:
            row = client.call({"id": target + "-" + name, "target": target, **values})
            report.data.setdefault("observations", []).append({"case": target + "." + name, **row})
            report.save()
            report.check(
                target + "." + name + ".transport_consistent",
                row["postCount"] == int(row["eligible"])
                and (not row["eligible"] or row["peerMarkerVisible"] == 1),
            )
            return row

        baseline = invoke("baseline")
        report.check(target + ".baseline_admits", baseline["eligible"])
        sample = invoke("calibration", afterMarkerIterations=100_000_000)
        sample_ms = max(
            sample["cpuAfterMarkerPerfMs"],
            sample["roundTripMonoMs"] - baseline["roundTripMonoMs"],
            1,
        )
        iterations = min(800_000_000, max(100_000_000, math.ceil(1600 / sample_ms * 100_000_000)))
        if client.run.state["environment"] == "cloudflare":
            iterations = (
                800_000_000  # Fixed bounded stress; HTTP calibration includes network time.
            )
        cpu = invoke("cpu-after-marker", afterMarkerIterations=iterations)
        report.check(
            target + ".cpu_interval_exercised",
            cpu["roundTripMonoMs"] >= 1000,
            iterations=iterations,
        )
        frozen = cpu["cpuAfterMarkerPerfMs"] == 0
        report.data.setdefault("clockFindings", []).append(
            {
                "target": target,
                "cpuClockFrozen": frozen,
                "latePeerPostObserved": bool(cpu["postCount"] and cpu["peerReceiptGapMs"] >= 1000),
                "performanceEqualsDate": cpu["performanceEqualsDate"],
                "hrtimeAvailable": cpu["hrtimeAvailable"],
                "hrtimeCpuDeltaMs": cpu["cpuAfterMarkerHrMs"],
            }
        )
        before = invoke("cpu-before-marker", beforeMarkerIterations=iterations)
        report.check(target + ".marker_io_exposes_elapsed_cpu", not before["eligible"])
        delay = invoke("delayed-marker", markerDelayMs=1200)
        report.check(target + ".delayed_marker_rejected", not delay["eligible"])
        suspended = invoke("io-suspension", afterMarkerWaitMs=1200)
        report.check(target + ".io_suspension_rejected", not suspended["eligible"])
        refreshed = invoke(
            "refresh-after-cpu", afterMarkerIterations=iterations, refreshBeforeDispatch=True
        )
        report.check(target + ".extra_io_exposes_elapsed_cpu", not refreshed["eligible"])
        residual = invoke(
            "cpu-after-extra-io", refreshBeforeDispatch=True, afterRefreshIterations=iterations
        )
        report.data["clockFindings"][-1]["extraIoStillHasFinalCpuGap"] = bool(
            residual["eligible"] and residual["peerReceiptGapMs"] >= 1000
        )
        backward = invoke("backward-injection", clockShiftMs=-2000)
        report.check(target + ".negative_age_rejected", not backward["eligible"])
        wall = invoke("independent-wall-jump", wallOnlyShiftMs=-600_000)
        report.check(
            target + ".injected_wall_does_not_drive_policy",
            wall["eligible"] and wall["injectedWallAgeMs"] < 0,
        )
    report.data["satisfiesRequiredClock"] = False
    report.data["limitations"] = [
        "Peer receipt gaps compare independent request wall samples; "
        "they are not a universal monotonic guarantee.",
        "I/O suspension and injected wall changes are controlled tests; "
        "actual provider process suspension or clock rollback was not forced.",
        "The CPU stress deliberately amplifies a blind interval; "
        "it does not estimate normal production incident frequency.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["local", "hosted"])
    args = parser.parse_args()
    run = coordination.new_run("cloudflare" if args.environment == "hosted" else "local", "clocks")
    run.state["sourceHashes"] = hashes()
    run.save()
    report = coordination.Report(run)
    process, log = None, None
    token = secrets.token_urlsafe(32)
    print("Clock private run: " + str(run.directory), flush=True)
    try:
        if args.environment == "hosted":
            provision(run, token)
        else:
            process, log = local(run, token)
        client = Client(run, token)
        client.ready()
        cases(client, report)
        report.check("source.unchanged", hashes() == run.state["sourceHashes"])
        report.data.update(
            completed=True,
            bundleSha2_256=run.state["bundleSha2_256"],
            runtimeCompatibilityDate="2026-09-11" if args.environment == "hosted" else "2026-07-30",
        )
    except (runtime.ProbeError, OSError, ValueError, KeyError, http.client.HTTPException) as error:
        report.data.update(completed=False, failureType=type(error).__name__)
        print(
            str(error)
            if isinstance(error, runtime.ProbeError)
            else "Clock investigation failed; private record retained.",
            file=sys.stderr,
        )
    finally:
        if process is not None:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.close()
            tail = process.stdout.read()
            process.wait(timeout=20)
            if log is not None:
                log.close()
            result = json.loads(tail.strip().splitlines()[-1]) if tail.strip() else {}
            report.data.update(localRuntime=result, cleanupConfirmed=process.returncode == 0)
            if result.get("externalCalls") != 0:
                report.data["completed"] = False
        elif args.environment == "hosted":
            try:
                coordination.cleanup(run)
            except runtime.ProbeError, OSError:
                print("Clock cleanup not confirmed.", file=sys.stderr)
            report.data["cleanupConfirmed"] = run.state.get("cleanupConfirmed", False)
        report.save()
    print("Clock report: " + str(run.directory / "report.json"), flush=True)
    return 0 if report.data.get("completed") and report.data.get("cleanupConfirmed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
