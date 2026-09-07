"""Disposable Worker-to-Secrets-Manager proof with checkpointed synthetic resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .runtime_permissions_probe import (
        NODE,
        ROOT,
        WRANGLER,
        NoRedirect,
        ProbeError,
        Run,
        command,
        delete_worker_without_force,
        missing_worker,
        wrangler,
    )
    from .secret_lifecycle_model import Lifecycle
except ImportError:
    from runtime_permissions_probe import (
        NODE,
        ROOT,
        WRANGLER,
        NoRedirect,
        ProbeError,
        Run,
        command,
        delete_worker_without_force,
        missing_worker,
        wrangler,
    )
    from secret_lifecycle_model import Lifecycle

RUNS = ROOT / ".secret-runs"
PROBE = ROOT / "probes/secrets"
AWS = (
    ["wsl.exe", "--distribution", "Ubuntu", "--exec", "/home/tdo/.local/bin/aws"]
    if sys.platform == "win32"
    else [str(Path.home() / ".local/bin/aws")]
)
SAFE_ERRORS = {
    "ResourceNotFoundException",
    "AccessDeniedException",
    "InvalidRequestException",
    "ExpiredTokenException",
    "UnrecognizedClientException",
}


def private_process(
    args: list[str], input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    # stdout can contain credentials. Never pass this through the logging wrapper.
    env = {
        **os.environ,
        "WRANGLER_WRITE_LOGS": "false",
        "WRANGLER_SEND_METRICS": "false",
        "WRANGLER_LOG_SANITIZE": "true",
        "CI": "true",
        "NO_COLOR": "1",
    }
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def aws(run: Run, service: str, operation: str, *args: str) -> tuple[Any, str | None]:
    result = private_process(
        [
            *AWS,
            service,
            operation,
            *args,
            "--profile",
            run.state["profile"],
            "--region",
            run.state["region"],
            "--output",
            "json",
            "--no-cli-pager",
        ]
    )
    if result.returncode:
        match = re.search(r"\(([A-Za-z]+)\)", result.stderr)
        return None, match[1] if match and match[1] in SAFE_ERRORS else "aws_failure"
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}, None
    except ValueError:
        raise ProbeError("AWS returned invalid JSON.") from None


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def hashes() -> dict[str, str]:
    paths = [
        *PROBE.glob("*.ts"),
        ROOT / "scripts/secret_store_probe.py",
        ROOT / "scripts/secret_lifecycle_model.py",
        ROOT / "scripts/runtime_permissions_probe.py",
        ROOT / "package.json",
        ROOT / "package-lock.json",
        ROOT / "tsconfig.json",
    ]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def validate(run: Run) -> None:
    state = run.state
    if (
        not re.fullmatch(r"rp-[a-f0-9]{24}", run.run_id)
        or not re.fullmatch(r"\d{12}", state["awsAccount"])
        or state["region"] != "us-east-2"
        or not re.fullmatch(r"[A-Za-z0-9_-]+", state["profile"])
    ):
        raise ProbeError("Invalid secret proof scope.")
    for row in state["generations"]:
        version = row["version"]
        if str(uuid.UUID(version, version=4)) != version:
            raise ProbeError("Invalid generation version.")
        if row["name"] != f"fga-proof/{run.run_id[3:]}/{version}":
            raise ProbeError("Invalid generation name.")
        if row.get("arn"):
            base = (
                f"arn:aws:secretsmanager:{state['region']}:{state['awsAccount']}:"
                f"secret:{row['name']}-"
            )
            if not row["arn"].startswith(base) or not re.fullmatch(
                r"[A-Za-z0-9]{6}", row["arn"][len(base) :]
            ):
                raise ProbeError("Invalid generation ARN.")


def call(run: Run, token: str, action: str, index: int = 0) -> tuple[int, dict[str, Any]]:
    ready = action == "ready"
    request = urllib.request.Request(
        run.state["url"] + ("/ready" if ready else "/probe"),
        data=None if ready else json.dumps({"action": action, "index": index}).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "FlickrGroupAddr-SecretProof/0.0.0",
        },
        method="GET" if ready else "POST",
    )
    try:
        reply = urllib.request.build_opener(NoRedirect).open(request, timeout=30)
    except urllib.error.HTTPError as error:
        reply = error
    with reply:
        status = reply.status
        if not isinstance(status, int):
            raise ProbeError("Invalid proof HTTP status.")
        content = reply.read(65537)
        if len(content) > 65536:
            raise ProbeError("Oversized proof response.")
        try:
            body = json.loads(content)
        except ValueError:
            return status, {"error": "non_json_edge_response"}
        if not isinstance(body, dict):
            raise ProbeError("Invalid proof response.")
        if reply.status == 200 and (
            body.get("build") != run.state["buildId"]
            or reply.headers.get("Cache-Control") != "no-store"
        ):
            raise ProbeError("Response build or cache boundary failed.")
        return status, body


def successful(run: Run, token: str, action: str, index: int) -> dict[str, Any]:
    status, body = call(run, token, action, index)
    if status != 200:
        run.state["failedStep"] = {
            "action": action,
            "index": index,
            "httpStatus": status,
            "error": (
                body.get("error")
                if re.fullmatch(
                    r"secret_probe_(?:invalid_input|transport|provider|protocol)"
                    r"|probe_(?:config|credentials|client|operation)_(?:syntax|type|other)"
                    r"|unauthorized|proof_expired|not_visible|non_json_edge_response",
                    str(body.get("error", "")),
                )
                else "unexpected"
            ),
        }
        run.save()
        raise ProbeError(f"Hosted {action} failed; sanitized details retained in manifest.")
    return body


def deploy(run: Run) -> str:
    identity, error = aws(run, "sts", "get-caller-identity")
    expected = f"arn:aws:iam::{run.state['awsAccount']}:user/fga-proof-operator"
    if error or identity.get("Arn") != expected:
        raise ProbeError("AWS identity is not the approved scoped operator.")
    credentials, error = aws(run, "configure", "export-credentials", "--format", "process")
    if error or not all(
        credentials.get(k) for k in ("AccessKeyId", "SecretAccessKey", "SessionToken", "Expiration")
    ):
        raise ProbeError("Temporary AWS session credentials unavailable.")
    if (
        datetime.fromisoformat(credentials["Expiration"].replace("Z", "+00:00")).timestamp()
        < time.time() + 600
    ):
        raise ProbeError("AWS credentials have less than ten minutes remaining.")
    run.state["credentialExpiration"] = credentials["Expiration"]
    cloud = json.loads(wrangler(run, "identity", "whoami", "--json").stdout)
    if not cloud.get("loggedIn") or len(cloud.get("accounts", [])) != 1:
        raise ProbeError("Exactly one Cloudflare account is required.")
    name = "fga-" + run.run_id
    run.state.update(
        accountId=cloud["accounts"][0]["id"], workerName=name, databaseName=name + "-db"
    )
    run.save()
    previous = wrangler(
        run, "preflight", "deployments", "list", "--name", name, "--json", allow_failure=True
    )
    if not missing_worker(previous):
        raise ProbeError("Generated Worker name is not proven unused.")
    source_hashes = hashes()
    run.state["sourceHashes"] = source_hashes
    run.state["buildId"] = hashlib.sha256(
        json.dumps(source_hashes, sort_keys=True).encode()
    ).hexdigest()
    config = {
        "name": name,
        "main": str(PROBE / "worker.ts"),
        "account_id": run.state["accountId"],
        "compatibility_date": "2026-09-07",
        "workers_dev": True,
        "preview_urls": False,
        "observability": {"enabled": False},
        "vars": {
            "PROOF_CONFIG": json.dumps(
                {
                    "scope": {
                        "account": run.state["awsAccount"],
                        "region": run.state["region"],
                        "runId": run.run_id[3:],
                    },
                    "generations": [
                        {"name": r["name"], "version": r["version"]}
                        for r in run.state["generations"]
                    ],
                    "build": run.state["buildId"],
                    "expires": int((time.time() + 3600) * 1000),
                }
            )
        },
    }
    config_path = run.directory / "wrangler.json"
    write_json(config_path, config)
    command(run, "typescript", [NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"])
    wrangler(
        run,
        "build",
        "deploy",
        "--dry-run",
        "--config",
        str(config_path),
        "--outdir",
        str(run.directory / "bundle"),
    )
    bundle = run.directory / "bundle/worker.js"
    run.state["bundleSha2_256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    config.update(main=str(bundle), no_bundle=True)
    write_json(config_path, config)
    run.state["workerAttempted"] = True
    run.save()
    deployed = wrangler(run, "deploy", "deploy", "--config", str(config_path)).stdout
    found = re.search(r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev\b", deployed)
    if not found:
        raise ProbeError("Isolated Worker URL unavailable.")
    run.state["url"] = found[0]
    run.save()
    token = uuid.uuid4().hex + uuid.uuid4().hex
    result = private_process(
        [NODE, str(WRANGLER), "secret", "bulk", "--config", str(config_path)],
        json.dumps({"AWS_SESSION": json.dumps(credentials), "PROOF_TOKEN": token}),
    )
    if result.returncode:
        raise ProbeError("Private credential binding installation failed.")
    run.state["deployment"] = json.loads(
        wrangler(run, "deployment", "deployments", "list", "--name", name, "--json").stdout
    )
    run.save()
    # Do not save token, credentials or the secret-install subprocess output.
    for _ in range(45):
        status, _ = call(run, token, "ready")
        if status == 200:
            post_status, _ = call(run, token, "preflight")
            if post_status == 200:
                return token
        time.sleep(1)
    raise ProbeError("Authenticated GET and mutation-free POST did not become ready.")


def cleanup(run: Run) -> None:
    validate(run)
    errors = []
    model = Lifecycle(run.directory / "lifecycle.sqlite")
    revision, _ = model.current()
    model.disconnect(revision)
    for row in run.state["generations"]:
        if not row.get("attempted") or row.get("cleanupConfirmed"):
            continue
        if not model.cleanup_allowed(row["name"]):
            raise ProbeError("Cleanup refused for a generation without durable inactive intent.")
        try:
            ref = row.get("arn") or row["name"]
            absent_samples = 0
            for _attempt in range(45):
                description, error = aws(
                    run, "secretsmanager", "describe-secret", "--secret-id", ref
                )
                if error == "ResourceNotFoundException":
                    _, read_error = aws(
                        run,
                        "secretsmanager",
                        "get-secret-value",
                        "--secret-id",
                        ref,
                        "--version-id",
                        row["version"],
                    )
                    absent_samples = (
                        absent_samples + 1 if read_error == "ResourceNotFoundException" else 0
                    )
                    if absent_samples >= 3:
                        row["cleanupConfirmed"] = True
                        row["absenceSamples"] = absent_samples
                        run.save()
                        break
                elif error:
                    raise ProbeError("AWS cleanup authority or availability failed.")
                else:
                    absent_samples = 0
                    if description.get("Name") != row["name"] or row[
                        "version"
                    ] not in description.get("VersionIdsToStages", {}):
                        raise ProbeError("Cleanup generation identity mismatch.")
                    row["arn"] = description["ARN"]
                    validate(run)
                    ref = row["arn"]
                    run.save()
                    if not row.get("deleteRequested"):
                        _, error = aws(
                            run,
                            "secretsmanager",
                            "delete-secret",
                            "--secret-id",
                            ref,
                            "--force-delete-without-recovery",
                        )
                        if error:
                            raise ProbeError("Synthetic secret deletion failed.")
                        row["deleteRequested"] = True
                        run.save()
                time.sleep(2)
            else:
                raise ProbeError("Secret deletion did not converge within the bounded checks.")
        except ProbeError, OSError, ValueError, subprocess.TimeoutExpired:
            errors.append("secret_cleanup_unconfirmed")
    # Attempt Worker cleanup even when AWS is unavailable; expire exposed bindings.
    if run.state.get("workerAttempted") and not run.state.get("workerDeleted"):
        try:
            delete_worker_without_force(run)
            check = wrangler(
                run,
                "cleanup-worker",
                "deployments",
                "list",
                "--name",
                run.state["workerName"],
                "--json",
                allow_failure=True,
            )
            if not missing_worker(check):
                raise ProbeError("Worker cleanup unconfirmed.")
            run.state["workerDeleted"] = True
        except ProbeError, OSError, ValueError, subprocess.TimeoutExpired:
            errors.append("worker_cleanup_unconfirmed")
    run.state["cleanupConfirmed"] = not errors
    run.save()
    if errors:
        raise ProbeError("Cleanup remains unconfirmed; resume cleanup using this run directory.")


def execute(run: Run) -> dict[str, Any]:
    model = Lifecycle(run.directory / "lifecycle.sqlite")
    results = []
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "productionConformance": False,
        "scope": "isolated-worker-aws-secrets",
        "passed": False,
        "compatibilityDate": "2026-09-07",
        "at": datetime.now(UTC).isoformat(),
        "sourceHashes": hashes(),
    }
    try:
        token = deploy(run)
        status, _ = call(run, "wrong-token", "ready")
        results.append({"id": "unauthorized", "passed": status == 401})
        for index, row in enumerate(run.state["generations"]):
            _, error = aws(run, "secretsmanager", "describe-secret", "--secret-id", row["name"])
            if error != "ResourceNotFoundException":
                raise ProbeError("Generated secret name is not proven unused.")
            row["attempted"] = True
            run.save()
            created = successful(run, token, "create", index)
            row.update(created["result"])
            validate(run)
            run.save()
            for _ in range(30):
                recovered = successful(run, token, "recover", index)
                if recovered["result"]:
                    break
                time.sleep(1)
            else:
                raise ProbeError("Created version not visible.")
            model.stage(row["name"], row["version"], row["arn"])
            model.activate(row["name"], index)
            results.append(
                {"id": f"create_{index}", "passed": True, "milliseconds": created["milliseconds"]}
            )
            for action in ("read", "read", "wrong-version", "put-denied", "bad-token"):
                observed = successful(run, token, action, index)
                result = observed["result"]
                results.append(
                    {
                        "id": f"{action}_{index}_{len(results)}",
                        "passed": result is True
                        or isinstance(result, dict)
                        and result.get("passed") is True,
                        "milliseconds": observed["milliseconds"],
                        "provider": result if isinstance(result, dict) else None,
                    }
                )
            write_json(run.directory / "report.json", {**report, "results": results})
        # Exercise deletion from the actual Worker only after the model has
        # durably replaced the old generation. Cleanup independently verifies it.
        old = run.state["generations"][0]
        if not model.cleanup_allowed(old["name"]):
            raise ProbeError("Old grant is still active.")
        deleted = successful(run, token, "delete", 0)
        old["deleteRequested"] = True
        run.save()
        results.append(
            {"id": "worker_delete_inactive", "passed": deleted["result"] == {"requested": True}}
        )
        after = json.loads(
            wrangler(
                run,
                "deployment-after",
                "deployments",
                "list",
                "--name",
                run.state["workerName"],
                "--json",
            ).stdout
        )
        if hashes() != run.state["sourceHashes"] or after != run.state["deployment"]:
            raise ProbeError("Source or hosted deployment changed during the proof.")
        report.update(
            passed=all(r["passed"] for r in results),
            results=results,
            buildId=run.state["buildId"],
            bundleSha2_256=run.state["bundleSha2_256"],
            sourceHashes=run.state["sourceHashes"],
            compatibilityDate="2026-09-07",
            at=datetime.now(UTC).isoformat(),
        )
    except (ProbeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        report["failure"] = str(error) if isinstance(error, ProbeError) else type(error).__name__
        if run.state.get("failedStep"):
            report["failedStep"] = run.state["failedStep"]
        raise
    finally:
        for field in ("buildId", "bundleSha2_256"):
            if field in run.state:
                report[field] = run.state[field]
        report["results"] = results
        write_json(run.directory / "report.json", report)
        try:
            cleanup(run)
        finally:
            report["cleanupConfirmed"] = run.state.get("cleanupConfirmed", False)
            report["passed"] = report["passed"] and report["cleanupConfirmed"]
            write_json(run.directory / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "cleanup"))
    parser.add_argument("--account")
    parser.add_argument("--profile", default="fga-proof")
    parser.add_argument("--run-directory")
    args = parser.parse_args()
    if args.action == "cleanup":
        directory = Path(args.run_directory or "").resolve()
        if directory.parent != RUNS.resolve():
            raise ProbeError("Invalid cleanup directory.")
        run = Run(directory, json.loads((directory / "manifest.json").read_text(encoding="utf-8")))
        if run.run_id != directory.name:
            raise ProbeError("Cleanup run identity mismatch.")
        cleanup(run)
        return 0
    run_id = "rp-" + os.urandom(12).hex()
    directory = RUNS / run_id
    directory.mkdir(parents=True)
    generations = []
    for _ in range(2):
        version = str(uuid.uuid4())
        generations.append({"name": f"fga-proof/{run_id[3:]}/{version}", "version": version})
    run = Run(
        directory,
        {
            "runId": run_id,
            "environment": "cloudflare",
            "awsAccount": args.account or "",
            "region": "us-east-2",
            "profile": args.profile,
            "generations": generations,
        },
    )
    validate(run)
    run.save()
    model = Lifecycle(directory / "lifecycle.sqlite")
    for row in generations:
        model.plan(row["name"], row["version"])
    print(f"Secret proof: {run_id}", flush=True)
    report = execute(run)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "cases": len(report["results"]),
                "cleanupConfirmed": report["cleanupConfirmed"],
            }
        )
    )
    return 0 if report["passed"] and report["cleanupConfirmed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ProbeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(
            str(error) if isinstance(error, ProbeError) else type(error).__name__, file=sys.stderr
        )
        sys.exit(1)
