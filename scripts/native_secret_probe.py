"""Checkpointed synthetic proof of paused D1/Cloudflare Secrets Store replacement."""

from __future__ import annotations

import argparse
import hashlib
import json
import msvcrt
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from . import runtime_permissions_probe as runtime
    from .secret_store_probe import private_process, write_json
except ImportError:
    import runtime_permissions_probe as runtime
    from secret_store_probe import private_process, write_json

ROOT = runtime.ROOT
RUNS = ROOT / ".native-secret-runs"
PROBE = ROOT / "probes/native-secrets"
DATE = "2026-09-11"
ProbeError = runtime.ProbeError
Run = runtime.Run


def validate(run: Run) -> None:
    if (
        run.directory.resolve().parent != RUNS.resolve()
        or run.directory.name != run.run_id
        or not re.fullmatch(r"rp-[a-f0-9]{24}", run.run_id)
    ):
        raise ProbeError("Invalid native run directory.")
    runtime.checked_resource_names(run)
    for key in ("accountId", "storeId", "secretId"):
        if run.state.get(key) and not re.fullmatch(r"[a-f0-9]{32}", run.state[key]):
            raise ProbeError("Invalid native provider identity.")
    if run.state["secretName"] != "fga-native-" + run.run_id[3:]:
        raise ProbeError("Invalid native secret namespace.")
    for value in run.state["generations"]:
        if str(uuid.UUID(value, version=4)) != value:
            raise ProbeError("Invalid synthetic generation.")


@contextmanager
def run_lock(run: Run):
    with (run.directory / "run.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ProbeError("This native proof run is already active.") from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def hashes() -> dict[str, str]:
    paths = [
        *PROBE.glob("*.ts"),
        PROBE / "schema.sql",
        Path(__file__),
        ROOT / "scripts/runtime_permissions_probe.py",
        ROOT / "scripts/secret_store_probe.py",
        ROOT / "package.json",
        ROOT / "package-lock.json",
        ROOT / "tsconfig.json",
    ]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


class NativeAPI:
    def __init__(self, run: Run):
        validate(run)
        result = private_process([runtime.NODE, str(runtime.WRANGLER), "auth", "token", "--json"])
        if result.returncode:
            raise ProbeError("Cloudflare operator credentials unavailable.")
        credentials = json.loads(result.stdout)
        if credentials.get("type") not in {"oauth", "api_token"} or not credentials.get("token"):
            raise ProbeError("Cloudflare operator identity unavailable.")
        self.run = run
        self.token = credentials["token"]

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        allow_failure: bool = False,
        invalid_token: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        validate(self.run)
        if not re.fullmatch(
            r"stores(?:/[a-f0-9]{32}(?:/secrets(?:/[a-f0-9]{32})?)?)?(?:[?]page=\d+&per_page=10)?",
            path,
        ):
            raise ProbeError("Native request escaped its fixed API surface.")
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.run.state['accountId']}/secrets_store/{path}"
        request = urllib.request.Request(
            url,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": "Bearer " + ("a" * 40 if invalid_token else self.token),
                "Content-Type": "application/json",
                "User-Agent": "FlickrGroupAddr-NativeSecretProof/0.0.0",
            },
        )
        try:
            reply = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=20)
        except urllib.error.HTTPError as error:
            reply = error
        with reply:
            status = reply.status
            raw = reply.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ProbeError("Oversized native API response.")
        try:
            data = json.loads(raw)
        except ValueError:
            raise ProbeError("Non-JSON native API response.") from None
        if not isinstance(data, dict) or not isinstance(status, int):
            raise ProbeError("Invalid native API response.")
        codes = [row["code"] for row in data.get("errors", []) if isinstance(row.get("code"), int)]
        if not allow_failure and (not 200 <= status < 300 or data.get("success") is not True):
            raise ProbeError(f"Native {method} failed (HTTP {status}; codes {codes}).")
        return status, data

    def rows(self, path: str) -> list[dict[str, Any]]:
        rows = []
        for page in range(1, 101):
            _, data = self.call("GET", f"{path}?page={page}&per_page=10")
            values = data.get("result")
            if not isinstance(values, list):
                raise ProbeError("Invalid native inventory.")
            rows.extend(values)
            if len(values) < 10:
                return rows
        raise ProbeError("Native inventory exceeded its bound.")

    def secret_path(self) -> str:
        validate(self.run)
        return f"stores/{self.run.state['storeId']}/secrets/{self.run.state['secretId']}"

    def check_secret(self) -> dict[str, Any]:
        _, reply = self.call("GET", self.secret_path())
        row = reply.get("result", {})
        if (
            row.get("id") != self.run.state["secretId"]
            or row.get("name") != self.run.state["secretName"]
            or row.get("store_id") != self.run.state["storeId"]
        ):
            raise ProbeError("Native secret ownership mismatch.")
        return row


def payload(run: Run, index: int) -> str:
    generation = run.state["generations"][index]
    return json.dumps(
        {
            "fixture": "fga-native-synthetic-only",
            "generation": generation,
            "token": "synthetic-token-" + generation,
            "tokenSecret": "synthetic-secret-" + generation,
        },
        separators=(",", ":"),
    )


def call(
    run: Run, token: str, action: str, expected: int = 0, index: int = 0, *, readiness: bool = False
) -> tuple[int, dict[str, Any]]:
    ready = action == "ready"
    request = urllib.request.Request(
        run.state["url"] + ("/ready" if ready else "/probe"),
        method="GET" if ready else "POST",
        data=None
        if ready
        else json.dumps(
            {
                "action": action,
                "expected": expected,
                "index": index,
                "operation": run.state["generations"][index],
            }
        ).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "FlickrGroupAddr-NativeSecretProof/0.0.0",
        },
    )
    try:
        reply = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=25)
    except urllib.error.HTTPError as error:
        reply = error
    with reply:
        status, raw = reply.status, reply.read(65537)
        no_store = reply.headers.get("Cache-Control") == "no-store"
        edge = {
            "contentType": reply.headers.get("Content-Type", "")[:80],
            "cloudflareRayPresent": bool(reply.headers.get("CF-Ray")),
            "bodySha2_256": hashlib.sha256(raw).hexdigest(),
        }
    if not isinstance(status, int) or len(raw) > 65536:
        raise ProbeError("Invalid native Worker response.")
    try:
        body = json.loads(raw)
    except ValueError:
        # Retain only bounded error classification, never the response body or bearer.
        normalized = raw.decode("utf-8", errors="replace").replace(token, "[redacted]")
        title = re.search(r"<title[^>]*>([^<]{0,160})</title>", normalized, re.IGNORECASE)
        edge["title"] = (
            title[1] if title and re.fullmatch(r"[A-Za-z0-9 .:_/|()-]{1,160}", title[1]) else None
        )
        error_code = re.search(r"error code:\s*(\d{3,5})", normalized, re.IGNORECASE)
        edge["errorCode"] = int(error_code[1]) if error_code else None
        return status, {"error": "non_json_edge", "diagnostic": edge}
    if not isinstance(body, dict):
        raise ProbeError("Invalid native Worker response schema.")
    if (
        status == 200
        and not readiness
        and (
            body.get("build") != run.state["buildId"]
            or body.get("instance") not in run.state.get("instances", [run.state["instance"]])
            or not no_store
        )
    ):
        run.state["failedResponse"] = {
            "action": action,
            "httpStatus": status,
            "buildMatched": body.get("build") == run.state["buildId"],
            "knownInstance": body.get("instance")
            in run.state.get("instances", [run.state["instance"]]),
            "noStore": no_store,
        }
        run.save()
        raise ProbeError("Native response build, deployment, or cache boundary failed.")
    return status, body


def transition_committed(
    action: str, state: dict[str, Any], expected: int, generation: str
) -> bool:
    if state.get("revision") != expected + 1:
        return False
    if action == "begin":
        return (
            state.get("state") == "paused"
            and state.get("operation") == generation
            and state.get("pending_generation") == generation
        )
    if action == "activate":
        return (
            state.get("state") == "linked"
            and state.get("generation") == generation
            and state.get("operation") is None
        )
    if action == "disconnect":
        return (
            state.get("state") == "disconnecting"
            and state.get("operation") == generation
            and state.get("retiring_generation") == generation
        )
    if action == "confirm-retirement":
        return (
            state.get("state") == "disconnected"
            and state.get("operation") is None
            and state.get("retiring_generation") is None
        )
    return False


def successful(run: Run, token: str, action: str, expected: int = 0, index: int = 0) -> Any:
    safe_reads = {
        "state",
        "attempts",
        "audit",
        "observe",
        "resolve",
        "preflight",
        "check-write",
        "check-delete",
    }
    transitions = {"begin", "activate", "disconnect", "confirm-retirement"}
    status = 0
    body: dict[str, Any] = {}
    for attempt in range(6):
        status, body = call(run, token, action, expected, index)
        if status == 200:
            return body["result"]
        if action in transitions and status in (404, 409, 429, 500, 502, 503, 504):
            current = successful(run, token, "state")
            if transition_committed(action, current, expected, run.state["generations"][index]):
                run.state.setdefault("acknowledgementsReconciled", []).append(
                    {"action": action, "revision": current["revision"]}
                )
                run.save()
                return current
            if current["revision"] != expected:
                break
        if (
            action not in safe_reads | transitions
            or status not in (404, 429, 500, 502, 503, 504)
            or attempt == 5
        ):
            break
        run.state.setdefault("workerRetries", []).append(
            {"action": action, "httpStatus": status, "diagnostic": body.get("diagnostic")}
        )
        run.save()
        time.sleep(min(0.5 * (attempt + 1), 2))
    code = body.get("error")
    safe = (
        code
        if code
        in {
            "conflict",
            "candidate_unavailable",
            "operation_failed",
            "expired",
            "non_json_edge",
            "unauthorized",
        }
        else "unexpected"
    )
    run.state["failedStep"] = {
        "action": action,
        "httpStatus": status,
        "error": safe,
        "diagnostic": body.get("diagnostic"),
    }
    run.save()
    raise ProbeError(f"Native Worker {action} failed (HTTP {status}, {safe}).")


def wait_ready(run: Run, token: str) -> None:
    deadline = time.monotonic() + 120
    consecutive = 0
    while time.monotonic() < deadline:
        good = True
        for action in ("ready", "preflight", "state"):
            status, body = call(run, token, action, readiness=True)
            good = (
                good
                and status == 200
                and body.get("instance") == run.state["instance"]
                and body.get("build") == run.state["buildId"]
            )
        consecutive = consecutive + 1 if good else 0
        if consecutive >= 3:
            return
        time.sleep(2)
    raise ProbeError("Native GET/POST/D1 readiness did not converge.")


def observe_until(
    run: Run, token: str, outcome: str, index: int | None = None, samples: int = 1
) -> int:
    matched = 0
    for attempt in range(1, 61):
        result = successful(run, token, "observe")
        good = result.get("outcome") == outcome and (
            index is None or result.get("generation") == run.state["generations"][index]
        )
        matched = matched + 1 if good else 0
        if matched >= samples:
            return attempt
        time.sleep(2)
    raise ProbeError("Native value observations did not converge within the bound.")


def deploy_with_bearer(run: Run, config_path: Path, token: str) -> str:
    # Standard Wrangler atomic version upload. The temporary transport file is
    # outside retained run artifacts, never logged, and removed even on failure.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="fga-native-bearer-",
        suffix=".json",
        delete_on_close=False,
    ) as secret_input:
        json.dump({"PROOF_TOKEN": token}, secret_input)
        secret_input.flush()
        try:
            return runtime.wrangler(
                run,
                "deploy",
                "deploy",
                "--config",
                str(config_path),
                "--secrets-file",
                secret_input.name,
            ).stdout
        finally:
            leaked = False
            for log in run.directory.glob("*.log"):
                text = log.read_text(encoding="utf-8")
                if token in text:
                    log.write_text(text.replace(token, "[REDACTED_PROOF_BEARER]"), encoding="utf-8")
                    leaked = True
            if leaked:
                raise ProbeError(
                    "Unexpected bearer diagnostic was redacted; review the deployment boundary."
                )


def provision(run: Run) -> tuple[NativeAPI, str]:
    identity = json.loads(runtime.wrangler(run, "identity", "whoami", "--json").stdout)
    if not identity.get("loggedIn") or len(identity.get("accounts", [])) != 1:
        raise ProbeError("Exactly one authenticated Cloudflare account is required.")
    run.state["accountId"] = identity["accounts"][0]["id"]
    run.save()
    api = NativeAPI(run)
    stores = api.rows("stores")
    if len(stores) > 1:
        raise ProbeError("Native proof requires an unambiguous store.")
    if stores:
        run.state.update(storeId=stores[0]["id"], storeOwned=False)
    else:
        run.state.update(storeAttempted=True, storeOwned=True)
        run.save()
        _, result = api.call("POST", "stores", {"name": run.state["workerName"]})
        run.state["storeId"] = result["result"]["id"]
    validate(run)
    run.save()
    path = f"stores/{run.state['storeId']}/secrets"
    if any(row["name"] == run.state["secretName"] for row in api.rows(path)):
        raise ProbeError("Generated native secret name was not unused.")
    run.state["secretAttempted"] = True
    run.save()
    _, created = api.call(
        "POST",
        path,
        [
            {
                "name": run.state["secretName"],
                "value": payload(run, 0),
                "scopes": ["workers"],
                "comment": "Disposable synthetic FGA lifecycle proof",
            }
        ],
    )
    run.state["secretId"] = created["result"][0]["id"]
    validate(run)
    run.save()
    api.check_secret()
    name = run.state["workerName"]
    previous = runtime.wrangler(
        run, "worker-preflight", "deployments", "list", "--name", name, "--json", allow_failure=True
    )
    if not runtime.missing_worker(previous):
        raise ProbeError("Generated Worker name was not unused.")
    if any(
        row["name"] == run.state["databaseName"]
        for row in runtime.databases(run, "database-preflight")
    ):
        raise ProbeError("Generated D1 name was not unused.")
    run.state["databaseAttempted"] = True
    run.save()
    runtime.wrangler(
        run, "database-create", "d1", "create", run.state["databaseName"], "--update-config=false"
    )
    found = [
        row
        for row in runtime.databases(run, "database-created")
        if row["name"] == run.state["databaseName"]
    ]
    if len(found) != 1:
        raise ProbeError("Generated D1 identity unavailable.")
    run.state.update(databaseId=found[0]["uuid"], databaseCreated=True)
    run.state["sourceHashes"] = hashes()
    run.state["buildId"] = hashlib.sha256(
        json.dumps(run.state["sourceHashes"], sort_keys=True).encode()
    ).hexdigest()
    run.state["instance"] = uuid.uuid4().hex
    run.state["instances"] = [run.state["instance"]]
    config = {
        "name": name,
        "main": str(PROBE / "worker.ts"),
        "account_id": run.state["accountId"],
        "compatibility_date": DATE,
        "workers_dev": True,
        "preview_urls": False,
        "observability": {"enabled": False},
        "d1_databases": [
            {
                "binding": "DB",
                "database_name": run.state["databaseName"],
                "database_id": run.state["databaseId"],
            }
        ],
        "secrets_store_secrets": [
            {
                "binding": "GRANT",
                "store_id": run.state["storeId"],
                "secret_name": run.state["secretName"],
            }
        ],
        "vars": {
            "PROOF_CONFIG": json.dumps(
                {
                    "runId": run.run_id,
                    "generations": run.state["generations"],
                    "build": run.state["buildId"],
                    "instance": run.state["instance"],
                    "expires": int((time.time() + 3600) * 1000),
                }
            )
        },
    }
    config_path = run.directory / "wrangler.json"
    write_json(config_path, config)
    fixture = (
        (PROBE / "schema.sql").read_text()
        + "\nINSERT INTO link(id,run_id,state,generation) "
        + f"VALUES(1,'{run.run_id}','linked','{run.state['generations'][0]}');\n"
    )
    (run.directory / "fixture.sql").write_text(fixture, encoding="utf-8", newline="\n")
    runtime.wrangler(
        run,
        "fixture",
        "d1",
        "execute",
        "DB",
        "--remote",
        "--config",
        str(config_path),
        "--file",
        str(run.directory / "fixture.sql"),
        "--yes",
    )
    runtime.command(
        run, "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
    )
    runtime.wrangler(
        run,
        "build",
        "deploy",
        "--dry-run",
        "--config",
        str(config_path),
        "--outdir",
        str(run.directory / "bundle"),
    )
    bundle_path = run.directory / "bundle/worker.js"
    run.state["bundleSha2_256"] = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    config.update(main=str(bundle_path), no_bundle=True)
    write_json(config_path, config)
    run.state["workerAttempted"] = True
    run.save()
    token = uuid.uuid4().hex + uuid.uuid4().hex
    deployed = deploy_with_bearer(run, config_path, token)
    url = re.search(r"https://" + re.escape(name) + r"\.[a-z0-9-]+\.workers\.dev\b", deployed)
    if not url:
        raise ProbeError("Native Worker URL unavailable.")
    run.state["url"] = url[0]
    run.save()
    wait_ready(run, token)
    run.state["deploymentBeforeRestart"] = runtime.current_deployment(run, "deployment-before")
    run.save()
    return api, token


def cleanup(run: Run) -> None:
    validate(run)
    errors = []
    try:
        if run.state.get("workerAttempted") or run.state.get("databaseAttempted"):
            runtime.cleanup(run)
    except ProbeError, OSError, ValueError, subprocess.TimeoutExpired:
        errors.append("compute_cleanup_unconfirmed")
    run.state["cleanupConfirmed"] = False
    run.save()
    try:
        if run.state.get("accountId") and (
            run.state.get("storeAttempted") or run.state.get("secretAttempted")
        ):
            api = NativeAPI(run)
            if run.state.get("storeAttempted") and not run.state.get("storeId"):
                matches = [
                    row for row in api.rows("stores") if row["name"] == run.state["workerName"]
                ]
                if len(matches) > 1:
                    raise ProbeError("Ambiguous generated store cleanup.")
                if matches:
                    run.state["storeId"] = matches[0]["id"]
                    run.save()
            if run.state.get("storeId"):
                store_path = f"stores/{run.state['storeId']}"
                status, store = api.call("GET", store_path, allow_failure=True)
                if status == 404:
                    run.state.update(secretDeleted=True, storeDeleted=True)
                elif store.get("success") is not True:
                    raise ProbeError("Store cleanup authority unavailable.")
                else:
                    rows = api.rows(store_path + "/secrets")
                    matches = [row for row in rows if row["name"] == run.state["secretName"]]
                    if len(matches) > 1:
                        raise ProbeError("Ambiguous generated secret cleanup.")
                    if matches and run.state.get("secretAttempted"):
                        row = matches[0]
                        if run.state.get("secretId") and row["id"] != run.state["secretId"]:
                            raise ProbeError("Native secret cleanup identity changed.")
                        if run.state.get("workerAttempted") and not run.state.get("workerDeleted"):
                            raise ProbeError(
                                "Refusing native deletion while Worker cleanup is uncertain."
                            )
                        run.state["secretId"] = row["id"]
                        run.save()
                        api.check_secret()
                        api.call("DELETE", api.secret_path())
                    for _ in range(30):
                        rows = api.rows(store_path + "/secrets")
                        if not any(row["name"] == run.state["secretName"] for row in rows):
                            run.state["secretDeleted"] = True
                            break
                        time.sleep(2)
                    else:
                        raise ProbeError("Native secret cleanup not confirmed.")
                    if run.state.get("storeOwned"):
                        if store["result"].get("name") != run.state["workerName"] or rows:
                            raise ProbeError("Refusing deletion of a nonempty or unowned store.")
                        api.call("DELETE", store_path)
                        status, _ = api.call("GET", store_path, allow_failure=True)
                        if status != 404:
                            raise ProbeError("Native store cleanup not confirmed.")
                        run.state["storeDeleted"] = True
    except ProbeError, OSError, ValueError, subprocess.TimeoutExpired:
        errors.append("native_cleanup_unconfirmed")
    run.state["cleanupConfirmed"] = not errors
    run.state["cleanupErrors"] = errors
    run.save()
    if errors:
        raise ProbeError("Native cleanup incomplete; resume the recorded run directory.")


def execute(run: Run) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "scope": "synthetic-native-secret-lifecycle",
        "at": datetime.now(UTC).isoformat(),
        "compatibilityDate": DATE,
        "productionConformance": False,
        "passed": False,
        "cleanupConfirmed": False,
        "results": [],
        "sourceHashes": hashes(),
    }

    def record(name: str, passed: bool, observation: Any = None):
        report["results"].append({"id": name, "passed": bool(passed), "observation": observation})
        write_json(run.directory / "report.json", report)
        if not passed:
            raise ProbeError("Native case failed: " + name)

    try:
        api, token = provision(run)
        record("unauthorized_worker", call(run, "wrong-token", "ready")[0] == 401)
        status, denied = api.call("GET", api.secret_path(), allow_failure=True, invalid_token=True)
        denial_codes = [item.get("code") for item in denied.get("errors", [])]
        record(
            "unauthorized_management",
            status == 401
            and denial_codes == [10000]
            and denied.get("success") is False
            and denied.get("result") is None,
            {"httpStatus": status, "errorCodes": denial_codes},
        )
        binding = successful(run, token, "binding")
        record(
            "binding_write_attempt_rejected",
            binding.get("read") is True
            and binding.get("writeAttemptRejected") is True
            and binding.get("managementCredentialPresent") is False,
            binding,
        )
        observe_until(run, token, "present", 0)
        record("initial_generation", successful(run, token, "resolve").get("outcome") == "usable")
        with ThreadPoolExecutor(max_workers=2) as pool:
            race = list(pool.map(lambda i: call(run, token, "begin", 0, i), (1, 2)))
        # HTTP acknowledgements can be lost. The D1 journal decides which start committed.
        seen: set[str] = set()
        for _ in range(5):
            attempts = successful(run, token, "attempts")["results"]
            seen = {row["operation"] for row in attempts if row["expected"] == 0}
            missing = [i for i in (1, 2) if run.state["generations"][i] not in seen]
            if not missing:
                break
            for candidate in missing:
                # Only the same idempotent D1 start is replayed, never a native secret write.
                race.append(call(run, token, "begin", 0, candidate))
        state = successful(run, token, "state")
        audit = successful(run, token, "audit")["results"]
        summary = {
            "httpStatuses": [row[0] for row in race],
            "attempts": len(seen),
            "revision": state["revision"],
            "auditEvents": len(audit),
        }
        record(
            "competing_relinks_one_winner",
            len(seen) == 2
            and state["revision"] == 1
            and state["state"] == "paused"
            and len(audit) == 1,
            summary,
        )
        index = run.state["generations"].index(state["pending_generation"])
        record(
            "pause_stops_resolution", successful(run, token, "resolve").get("outcome") == "stopped"
        )
        record(
            "disconnect_cannot_take_pending_replacement",
            call(run, token, "disconnect", 1, 0)[0] == 409,
        )
        # Actual replacement deployment while the durable operation is pending.
        config_path = run.directory / "wrangler.json"
        config = json.loads(config_path.read_text())
        proof = json.loads(config["vars"]["PROOF_CONFIG"])
        run.state["instance"] = uuid.uuid4().hex
        run.state["instances"].append(run.state["instance"])
        proof["instance"] = run.state["instance"]
        config["vars"]["PROOF_CONFIG"] = json.dumps(proof)
        write_json(config_path, config)
        run.save()
        runtime.wrangler(run, "restart", "deploy", "--config", str(config_path))
        wait_ready(run, token)
        run.state["deploymentAfterRestart"] = runtime.current_deployment(
            run, "deployment-restarted"
        )
        run.save()
        for _ in range(45):
            status, body = call(run, token, "state")
            if status == 200 and body.get("instance") == run.state["instance"]:
                state = body["result"]
                break
            time.sleep(1)
        else:
            raise ProbeError("New deployment did not observe durable state.")
        record(
            "pause_survives_deployment",
            state["state"] == "paused"
            and state["revision"] == 1
            and state["operation"] == run.state["generations"][index],
        )

        def patch_value(value: str, label: str):
            api.check_secret()
            run.state.setdefault("mutations", []).append(
                {"kind": label, "attempted": True, "acknowledged": False}
            )
            run.save()
            api.call("PATCH", api.secret_path(), {"value": value, "scopes": ["workers"]})
            run.state["mutations"][-1]["acknowledged"] = True
            run.save()

        successful(run, token, "check-write", 1, index)
        patch_value(payload(run, index), "replace")
        # Discard the mutation response; reconcile via native get and durable state.
        run.state["mutations"][-1]["acknowledged"] = False
        run.save()
        attempts = observe_until(run, token, "present", index)
        record(
            "lost_store_response_reconciled",
            successful(run, token, "state")["revision"] == 1,
            {"observationAttempts": attempts},
        )
        failure_status, failure_body = call(run, token, "activate-fail", 1, index)
        record(
            "failed_activation_is_rejected",
            failure_status == 409 and failure_body.get("error") == "injected_audit_failure",
        )
        state = successful(run, token, "state")
        audit = successful(run, token, "audit")
        record(
            "activation_and_audit_rollback",
            state["state"] == "paused" and state["revision"] == 1 and len(audit["results"]) == 1,
        )
        successful(run, token, "activate", 1, index)
        state = successful(run, token, "state")
        record(
            "lost_activation_response_reconciled",
            state["state"] == "linked" and state["revision"] == 2,
        )
        record("activation_does_not_resume_writes", state["writes_paused"] == 1)
        record("duplicate_activation_rejected", call(run, token, "activate", 1, index)[0] == 409)
        record(
            "new_generation_usable", successful(run, token, "resolve").get("outcome") == "usable"
        )
        # Inject reordered provider data independently of ordinary lifecycle authorization.
        patch_value(payload(run, 0), "fault_late_old_value")
        observe_until(run, token, "present", 0)
        record(
            "late_old_value_fails_closed",
            successful(run, token, "resolve").get("outcome") == "generation_mismatch",
        )
        patch_value("{malformed-synthetic", "fault_malformed_value")
        observe_until(run, token, "invalid_bundle")
        record(
            "malformed_value_fails_closed",
            successful(run, token, "resolve").get("outcome") == "invalid_bundle",
        )
        patch_value(payload(run, index), "repair")
        observe_until(run, token, "present", index)
        record(
            "matching_value_repair", successful(run, token, "resolve").get("outcome") == "usable"
        )
        record("stale_cleanup_rejected", call(run, token, "check-delete", 1, 0)[0] == 409)
        successful(run, token, "disconnect", 2, index)
        record(
            "disconnect_stops_new_operations",
            successful(run, token, "resolve").get("outcome") == "stopped",
        )
        record("relink_waits_for_cleanup", call(run, token, "begin", 3, 0)[0] == 409)
        retired = json.dumps(
            {"fixture": "fga-native-retired", "generation": run.state["generations"][index]},
            separators=(",", ":"),
        )
        successful(run, token, "check-delete", 3, index)
        patch_value(retired, "retire")
        attempts = observe_until(run, token, "retired", index, samples=3)
        record(
            "credential_payload_retired", True, {"consecutiveObservations": 3, "attempts": attempts}
        )
        successful(run, token, "confirm-retirement", 3, index)
        record(
            "confirmed_retirement_completes_disconnect",
            successful(run, token, "state")["state"] == "disconnected",
        )
        other = 2 if index == 1 else 1
        successful(run, token, "begin", 4, other)
        successful(run, token, "check-write", 5, other)
        patch_value(payload(run, other), "relink_after_disconnect")
        observe_until(run, token, "present", other)
        successful(run, token, "activate", 5, other)
        record(
            "relink_reuses_binding_without_deploy",
            successful(run, token, "resolve").get("outcome") == "usable",
        )
        record(
            "old_cleanup_cannot_touch_successor",
            call(run, token, "check-delete", 3, index)[0] == 409,
        )
        successful(run, token, "disconnect", 6, other)
        record(
            "retirement_target_is_durable",
            successful(run, token, "state")["retiring_generation"]
            == run.state["generations"][other],
        )
        patch_value(retired, "fault_old_retirement")
        observe_until(run, token, "retired", index)
        status, refused = call(run, token, "confirm-retirement", 7, other)
        record(
            "old_retirement_cannot_confirm_new_disconnect",
            status == 409 and refused.get("error") == "retirement_unconfirmed",
        )
        successful(run, token, "check-delete", 7, other)
        retired = json.dumps(
            {"fixture": "fga-native-retired", "generation": run.state["generations"][other]},
            separators=(",", ":"),
        )
        patch_value(retired, "final_retire")
        observe_until(run, token, "retired", other, samples=3)
        successful(run, token, "confirm-retirement", 7, other)
        state = successful(run, token, "state")
        audit = successful(run, token, "audit")
        record(
            "durable_audit_sequence",
            state["revision"] == 8
            and [r["revision"] for r in audit["results"]] == list(range(1, 9)),
        )
        after = runtime.current_deployment(run, "deployment-after")
        record(
            "source_and_deployment_stable",
            hashes() == run.state["sourceHashes"] and after == run.state["deploymentAfterRestart"],
        )
        report.update(
            passed=True,
            binding=binding,
            mutations=len(run.state["mutations"]),
            credentialRetirement=(
                "fixed slot overwritten with noncredential tombstone; "
                "native get observed three times"
            ),
            managementIdentity="local operator Wrangler credential; no management token deployed",
            workerRetries=run.state.get("workerRetries", []),
            acknowledgementsReconciled=run.state.get("acknowledgementsReconciled", []),
            fullProductionConformance=False,
        )
    except (ProbeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        report["failure"] = str(error) if isinstance(error, ProbeError) else type(error).__name__
        report["failedStep"] = run.state.get("failedStep")
        report["failedResponse"] = run.state.get("failedResponse")
        raise
    finally:
        for field in ("buildId", "bundleSha2_256", "sourceHashes"):
            if field in run.state:
                report[field] = run.state[field]
        write_json(run.directory / "report.json", report)
        try:
            cleanup(run)
        finally:
            report["cleanupConfirmed"] = run.state.get("cleanupConfirmed", False)
            report["passed"] = report["passed"] and report["cleanupConfirmed"]
            report["cleanup"] = {
                key: run.state.get(key, False)
                for key in (
                    "workerDeleted",
                    "databaseDeleted",
                    "secretDeleted",
                    "storeOwned",
                    "storeDeleted",
                )
            }
            write_json(run.directory / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "cleanup"))
    parser.add_argument("--run")
    args = parser.parse_args()
    if args.action == "cleanup":
        directory = Path(args.run or "").resolve()
        if directory.parent != RUNS.resolve():
            raise ProbeError("Cleanup directory is outside native proof runs.")
        run = Run(directory, json.loads((directory / "manifest.json").read_text()))
        validate(run)
        with run_lock(run):
            cleanup(run)
        return 0
    run_id = "rp-" + os.urandom(12).hex()
    directory = RUNS / run_id
    directory.mkdir(parents=True)
    run = Run(
        directory,
        {
            "runId": run_id,
            "environment": "cloudflare",
            "workerName": "fga-" + run_id,
            "databaseName": "fga-" + run_id + "-db",
            "secretName": "fga-native-" + run_id[3:],
            "generations": [str(uuid.uuid4()) for _ in range(3)],
        },
    )
    run.save()
    print("Native proof: " + run_id, flush=True)
    with run_lock(run):
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
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ProbeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(
            str(error) if isinstance(error, ProbeError) else type(error).__name__, file=sys.stderr
        )
        sys.exit(1)
