"""Offline-prepared finite lifecycle. CLI describes only; no credential/provider integration."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

VERSION = "fga-group-post-v1"
ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "probes/group-post-characterization"
OUT = ROOT / ".coordination-runs/group-post-characterization"
NATIVE_ROOT = Path(r"C:\Temp\FGA-group-post-v1")
RUNTIMES = {"python": "3.14", "uv": "0.12.5", "node": "24.22.0", "lightroom": "15.6", "sdk": "15.3"}
LIMITS = {
    "lifetimeSeconds": 1200,
    "cleanupMarginSeconds": 240,
    "providerCalls": 120,
    "providerTimeoutSeconds": 20,
    "requestsPerRole": 64,
    "requestBytes": 16384,
    "responseBytes": 2097153,
    "delayMs": 16000,
    "workers": 2,
    "databases": 1,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packet() -> dict[str, Any]:
    files = [
        PACKET / "worker.mjs",
        PACKET / "schema.sql",
        Path(__file__),
        *sorted((ROOT / "probes/lightroom/FGA-GroupPost-v1.lrplugin").glob("*.lua")),
        ROOT / "clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua",
        ROOT / "clients/lightroom/FGA-LrC15.lrplugin/GroupSubmissionClient.lua",
        ROOT / "clients/lightroom/FGA-LrC15.lrplugin/dkjson.lua",
    ]
    return {
        "schemaVersion": 1,
        "planVersion": VERSION,
        "mode": "offline_preparation",
        "limits": LIMITS,
        "productionQualified": False,
        "runtimes": RUNTIMES,
        "actionPaths": {
            "manifest": str(PACKET / "manifest.json"),
            "outputRoot": str(OUT),
            "nativeRoot": str(NATIVE_ROOT),
            "target": str(NATIVE_ROOT / "target.json"),
            "status": str(NATIVE_ROOT / "status.json"),
            "stop": str(NATIVE_ROOT / "stop.json"),
        },
        "sha2_256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files},
        "effectiveConfig": {
            "compatibility_date": "2026-10-16",
            "workers_dev": True,
            "preview_urls": False,
            "observability": {"enabled": False},
            "logpush": False,
            "bindings": ["DB", "RUN_ID", "ROLE", "SUBDOMAIN", "EXPIRES", "ACCESS", "CANARY"],
        },
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Provider:
    """Explicit-argument provider transport; never reads credentials or config.

    Nothing instantiates this in the offline CLI. Each request has a 20-second
    socket timeout, 64 KiB response cap, fixed account origin and no redirects.
    A socket timeout is not a production hard wall-clock cancellation guarantee.
    """

    def __init__(self, account: str, token: str, run_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", account) or not token:
            raise ValueError("provider_identity_invalid")
        if not re.fullmatch(r"[a-f0-9]{24}", run_id):
            raise ValueError("run_identity_invalid")
        self.account, self.token, self.run_id = account, token, run_id
        self.calls = 0

    def call(self, method, path, body=None, *, timeout=20):
        worker = r"/workers/scripts/fga-post-(?:src|recv)-" + self.run_id
        database = r"/d1/database(?:/[a-f0-9-]{36}(?:/query)?)?"
        allowed = {
            "GET": worker + r"/settings|" + database,
            "PUT": worker,
            "POST": worker + r"/subdomain|" + database,
            "DELETE": worker + "|" + r"/d1/database/[a-f0-9-]{36}",
        }
        if (
            timeout != 20
            or self.calls >= 120
            or not re.fullmatch(allowed.get(method, "(?!)"), path)
        ):
            raise ValueError("provider_request_outside_packet")
        self.calls += 1
        media = "application/json"
        if method == "PUT":
            if not isinstance(body, dict) or set(body) != {"metadata", "module"}:
                raise ValueError("provider_upload_shape")
            boundary = "fga_post_v1_" + self.run_id
            pieces = []
            for name, mime, value in (
                ("metadata", "application/json", json.dumps(body["metadata"])),
                ("worker.mjs", "application/javascript+module", body["module"]),
            ):
                pieces.append(
                    (
                        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                        f'filename="{name}"\r\nContent-Type: {mime}\r\n\r\n{value}\r\n'
                    ).encode()
                )
            data = b"".join(pieces) + f"--{boundary}--\r\n".encode()
            media = "multipart/form-data; boundary=" + boundary
        else:
            data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/" + self.account + path,
            method=method,
            data=data,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": media},
        )
        try:
            response = urllib.request.build_opener(NoRedirect).open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("provider_response_limit")
            result = json.loads(raw) if raw else {}
            if not isinstance(result, dict):
                raise ValueError("provider_response_invalid")
            return response.status, result


class Lifecycle:
    """A caller must supply its approved bounded provider adapter; none is loaded here.

    Adapter call(method,path,body,timeout=20) returns (HTTP status, parsed JSON).
    No retries. Creation intent persists before a request; unknown acknowledgement
    remains cleanup_unconfirmed. Destruction requires an exact journal identity.
    """

    def __init__(self, api, directory: Path, run_id: str, owner: str, clock=time.time):
        if not re.fullmatch(r"[a-f0-9]{24}", run_id) or run_id == "0" * 24:
            raise ValueError("run_identity_invalid")
        if not re.fullmatch(r"[0-9]+", owner):
            raise ValueError("same_job_owner_required")
        self.api, self.directory, self.clock = api, directory, clock
        account_identity = getattr(api, "account", "")
        if not isinstance(account_identity, str) or not re.fullmatch(
            r"[a-f0-9]{32}", account_identity
        ):
            raise ValueError("provider_account_identity_required")
        self.preparation_deadline = clock() + 240
        self.journal = {
            "schemaVersion": 1,
            "planVersion": VERSION,
            "runId": run_id,
            "owner": owner,
            "accountId": account_identity,
            "expiresAtUnix": int(clock()) + 1200,
            "stage": "planned",
            "calls": 0,
            "resources": [],
            "artifactSha2_256": digest(PACKET / "worker.mjs"),
        }
        self.path = directory / "private/journal.json"
        if self.path.exists():
            raise ValueError("journal_already_exists")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.journal), encoding="utf-8")
        temporary.replace(self.path)

    def call(self, method, path, body=None, *, cleanup=False):
        if getattr(self.api, "account", None) != self.journal["accountId"]:
            raise ValueError("provider_account_changed")
        cutoff = self.journal["expiresAtUnix"] if cleanup else self.journal["expiresAtUnix"] - 240
        if not cleanup and self.journal["stage"] != "ready":
            cutoff = min(cutoff, self.preparation_deadline)
        if self.clock() + 20 >= cutoff or self.journal["calls"] >= 120:
            raise TimeoutError("finite_provider_budget")
        self.journal["calls"] += 1
        self.save()
        return self.api.call(method, path, body, timeout=20)

    def cleanup(self):
        self.journal["stage"] = "cleanup"
        for resource in reversed(self.journal["resources"]):
            if resource.get("deleted"):
                continue
            try:
                # Missing creation acknowledgement never licenses deletion by guess.
                if not resource.get("acknowledged"):
                    continue
                status, current = self.call("GET", resource["path"], cleanup=True)
                if status == 404:
                    resource["deleted"] = True
                    continue
                result = current.get("result", {})
                if status != 200:
                    continue
                if resource["kind"] == "worker":
                    bindings = result.get("bindings", [])
                    expected = {
                        "RUN_ID": self.journal["runId"],
                        "ROLE": resource["role"],
                        "EXPIRES": str(self.journal["expiresAtUnix"]),
                    }
                    if any(
                        sum(b.get("name") == key and b.get("text") == value for b in bindings) != 1
                        for key, value in expected.items()
                    ):
                        continue
                elif result.get("uuid") != resource["id"] or result.get("name") != resource["name"]:
                    continue
                self.call("DELETE", resource["deletePath"], cleanup=True)
                status, _ = self.call("GET", resource["path"], cleanup=True)
                resource["deleted"] = status == 404
            except Exception:
                resource["cleanupError"] = True
            finally:
                self.save()
        confirmed = all(r.get("deleted") for r in self.journal["resources"])
        self.journal["stage"] = "cleanup_complete" if confirmed else "cleanup_unconfirmed"
        self.save()
        receipt = {
            "schemaVersion": 1,
            "planVersion": VERSION,
            "stage": self.journal["stage"],
            "cleanupConfirmed": confirmed,
            "observationsConfirmed": self.journal.get("observationsConfirmed", False),
            "stopReason": self.journal.get("stopReason", "preparation_failed"),
            "providerCalls": self.journal["calls"],
            "productionQualified": False,
            "resources": [
                {
                    "kind": r["kind"],
                    "acknowledged": r.get("acknowledged", False),
                    "deleted": r.get("deleted", False),
                }
                for r in self.journal["resources"]
            ],
        }
        (self.directory / "cleanup.json").write_text(json.dumps(receipt), encoding="utf-8")
        return receipt

    def prepare(self, subdomain: str, access: str, canary: str):
        # This method is a provider-adapter seam, deliberately unavailable in CLI.
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain):
            raise ValueError("subdomain_invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", access) or not re.fullmatch(
            r"SYNTHETIC-[a-f0-9]{32}", canary
        ):
            raise ValueError("synthetic_markers_required")
        run = self.journal["runId"]
        try:
            for role in ("src", "recv"):
                name = f"fga-post-{role}-{run}"
                status, _ = self.call("GET", "/workers/scripts/" + name + "/settings")
                if status != 404:
                    raise ValueError("worker_absence_unconfirmed")
            db = {"kind": "database", "name": "fga-post-db-" + run, "acknowledged": False}
            self.journal["resources"].append(db)
            self.save()
            status, response = self.call("POST", "/d1/database", {"name": db["name"]})
            value = response.get("result", {})
            dbid = str(uuid.UUID(value.get("uuid", "")))
            if status != 200 or value.get("name") != db["name"] or dbid != value.get("uuid"):
                raise ValueError("database_creation_unconfirmed")
            db.update(
                id=dbid,
                path="/d1/database/" + dbid,
                deletePath="/d1/database/" + dbid,
                acknowledged=True,
            )
            self.save()
            seed = [{"sql": (PACKET / "schema.sql").read_text(), "params": []}]
            seed += [
                {
                    "sql": "INSERT INTO post_budget(run_id,role,expires_at) VALUES(?,?,?)",
                    "params": [run, role, self.journal["expiresAtUnix"]],
                }
                for role in ("source", "receiver")
            ]
            status, result = self.call("POST", db["path"] + "/query", {"batch": seed})
            if status != 200 or result.get("success") is not True:
                raise ValueError("seed_unconfirmed")
            for role, short in (("source", "src"), ("receiver", "recv")):
                name = f"fga-post-{short}-{run}"
                worker = {
                    "kind": "worker",
                    "name": name,
                    "role": role,
                    "acknowledged": False,
                    "path": "/workers/scripts/" + name + "/settings",
                    "deletePath": "/workers/scripts/" + name,
                }
                self.journal["resources"].append(worker)
                self.save()
                values = {
                    "ROLE": role,
                    "RUN_ID": run,
                    "SUBDOMAIN": subdomain,
                    "EXPIRES": str(self.journal["expiresAtUnix"]),
                    "ACCESS": access,
                    "CANARY": canary,
                }
                # Adapter owns multipart encoding; this is its exact upload input.
                config = {
                    "compatibility_date": "2026-10-16",
                    "observability": {"enabled": False},
                    "logpush": False,
                }
                bindings = [{"type": "d1", "name": "DB", "id": dbid}] + [
                    {
                        "type": "secret_text" if k in ("ACCESS", "CANARY") else "plain_text",
                        "name": k,
                        "text": v,
                    }
                    for k, v in values.items()
                ]
                status, result = self.call(
                    "PUT",
                    worker["deletePath"],
                    {
                        "metadata": {**config, "main_module": "worker.mjs", "bindings": bindings},
                        "module": (PACKET / "worker.mjs").read_text(),
                    },
                )
                if status != 200 or result.get("result", {}).get("id") != name:
                    raise ValueError("worker_creation_unconfirmed")
                worker["acknowledged"] = True
                self.save()
                status, enabled = self.call(
                    "POST",
                    worker["deletePath"] + "/subdomain",
                    {"enabled": True, "previews_enabled": False},
                )
                if status != 200 or enabled.get("result") != {
                    "enabled": True,
                    "previews_enabled": False,
                }:
                    raise ValueError("endpoint_enable_unconfirmed")
            self.journal["stage"] = "ready"
            if self.clock() + 600 > self.journal["expiresAtUnix"]:
                raise TimeoutError("native_window_unavailable")
            self.save()
            return {
                "schemaVersion": 1,
                "planVersion": VERSION,
                "runId": run,
                "subdomain": subdomain,
                "access": access,
                "canary": canary,
                "expiresAtUnix": self.journal["expiresAtUnix"],
            }
        except Exception:
            self.cleanup()
            raise

    def hold_and_cleanup(self, stopped, *, sleep=time.sleep):
        """Stop/native-terminal signal is sticky; always clean up in the same job.

        The caller must continue this owner after publishing the target. It may
        never leave resources waiting for a separate later invocation.
        """
        try:
            self.journal["stopReason"] = "cleanup_cutoff"
            for _ in range(1021):
                if self.clock() >= self.journal["expiresAtUnix"] - 240:
                    break
                if stopped():
                    self.journal["stopReason"] = "native_terminal_or_stop"
                    break
                sleep(1)
        finally:
            try:
                self.observe()
            except Exception:
                self.journal["observationsConfirmed"] = False
            receipt = self.cleanup()
        return receipt

    def observe(self):
        """Read-only, schema-checked export; arbitrary provider fields never escape."""
        db = next(r for r in self.journal["resources"] if r["kind"] == "database")
        columns = {
            "role",
            "case_id",
            "method",
            "body_bytes",
            "body_matches",
            "authorization_present",
            "canary_matches",
            "content_type_matches",
        }
        sql = "SELECT " + ",".join(sorted(columns)) + " FROM post_observations WHERE run_id=?"
        status, response = self.call(
            "POST",
            db["path"] + "/query",
            {"sql": sql, "params": [self.journal["runId"]]},
            cleanup=True,
        )
        results = response.get("result")
        if (
            status != 200
            or response.get("success") is not True
            or not isinstance(results, list)
            or len(results) != 1
        ):
            raise ValueError("observations_unconfirmed")
        rows = results[0].get("results")
        if results[0].get("success") is not True or not isinstance(rows, list) or len(rows) > 46:
            raise ValueError("observation_shape_invalid")
        for row in rows:
            if (
                not isinstance(row, dict)
                or set(row) != columns
                or row["role"] not in ("source", "receiver")
                or row["method"] not in ("GET", "POST")
            ):
                raise ValueError("observation_shape_invalid")
            case = row["case_id"]
            pattern = (
                r"(?:receive-)?(?:proof|batch-(?:one|sixty)|status-(?:400|401|409|429|503)|"
                r"oversize-(?:success|error)|timeout|cancel|lost-response|"
                r"(?:same|cross)-(?:301|302|303|307|308))"
            )
            if not isinstance(case, str) or not re.fullmatch(pattern, case):
                raise ValueError("observation_case_invalid")
            if type(row["body_bytes"]) is not int or not 0 <= row["body_bytes"] <= 16384:
                raise ValueError("observation_count_invalid")
            for key in (
                "body_matches",
                "authorization_present",
                "canary_matches",
                "content_type_matches",
            ):
                if type(row[key]) is not int or row[key] not in (0, 1):
                    raise ValueError("observation_boolean_invalid")
        receipt = {
            "schemaVersion": 1,
            "planVersion": VERSION,
            "runId": self.journal["runId"],
            "observations": rows,
            "productionQualified": False,
        }
        (self.directory / "observations.json").write_text(json.dumps(receipt), encoding="utf-8")
        self.journal["observationsConfirmed"] = True
        self.save()
        return receipt


def atomic_json(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as output:
        json.dump(value, output)
    temporary.replace(path)


def bounded_json(path: Path, maximum=65536):
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("receipt_byte_limit")
    return json.loads(raw)


def native_terminal(value, run_id: str):
    """Return a closed sanitized terminal projection; never export arbitrary SDK text."""
    reasons = {
        "target_invalid",
        "fixture_failure",
        "cancelled",
        "clock_invalid",
        "cleanup_margin",
        "finite_response_exceeded",
        "measurements_require_external_receipt_review",
    }
    if (
        not isinstance(value, dict)
        or value.get("schemaVersion") != 1
        or value.get("planVersion") != VERSION
        or value.get("runId") != run_id
        or value.get("productionQualified") is not False
        or value.get("remoteCleanupConfirmed") is not False
        or value.get("outcome") not in ("characterized", "failed", "stopped")
        or value.get("reasonCode") not in reasons
    ):
        raise ValueError("native_terminal_identity_invalid")
    for key, maximum in (("postCalls", 23), ("getCalls", 1)):
        if type(value.get(key)) is not int or not 0 <= value[key] <= maximum:
            raise ValueError("native_terminal_count_invalid")
    if value["outcome"] == "characterized" and (value["postCalls"] != 23 or value["getCalls"] != 1):
        raise ValueError("native_terminal_incomplete")
    return {
        key: value[key]
        for key in (
            "schemaVersion",
            "planVersion",
            "runId",
            "outcome",
            "reasonCode",
            "postCalls",
            "getCalls",
            "productionQualified",
            "remoteCleanupConfirmed",
        )
    }


def run_once(
    api,
    *,
    run_id: str,
    owner: str,
    subdomain: str,
    access: str,
    canary: str,
    invoke_native,
    stop_requested,
    clock=time.time,
    sleep=time.sleep,
):
    """Prepared one-attempt action runner; unavailable through the CLI.

    Only an approved caller supplies the adapter, synthetic markers and one native
    invocation callback. Tests inject all effects. This function never installs,
    reads credentials, invokes a shell, or retries a native operation itself.
    """
    if bounded_json(PACKET / "manifest.json") != packet():
        raise ValueError("approved_manifest_changed")
    if not re.fullmatch(r"[a-f0-9]{24}", run_id) or run_id == "0" * 24:
        raise ValueError("run_identity_invalid")
    directory = OUT / run_id
    directory.mkdir(parents=True, exist_ok=False)
    life = Lifecycle(api, directory, run_id, owner, clock=clock)
    paths = {
        key: NATIVE_ROOT / filename
        for key, filename in {
            "target": "target.json",
            "used": "target.used.json",
            "status": "status.json",
            "stop": "stop.json",
            "targetTemporary": "target.json.tmp",
            "statusTemporary": "status.json.tmp",
            "stopTemporary": "stop.json.tmp",
        }.items()
    }
    if any(path.exists() for path in paths.values()):
        life.journal.update(stage="native_paths_not_fresh", actionFailed=True)
        life.save()
        raise ValueError("native_paths_not_fresh")
    NATIVE_ROOT.mkdir(parents=True, exist_ok=True)
    life.journal.update(
        stage="planned",
        nativeInvocations=0,
        nativeTerminal=False,
        nativePaths={k: str(v) for k, v in paths.items()},
        manifestSha2_256=digest(PACKET / "manifest.json"),
        runtimes=RUNTIMES,
    )
    life.save()
    projection = None
    terminal = False
    sticky_stop = False
    stop_at = None
    previous = clock()
    try:
        if stop_requested():
            sticky_stop = True
            life.journal["stopReason"] = "stop_before_preparation"
        else:
            target = life.prepare(subdomain, access, canary)
            if stop_requested():
                sticky_stop = True
                life.journal["stopReason"] = "stop_before_publication"
            else:
                atomic_json(paths["target"], target)
                life.journal["targetPublished"] = True
                life.save()
                # Record the irreversible attempt before handing control to native.
                life.journal["nativeInvocations"] = 1
                life.save()
                if stop_requested():
                    sticky_stop = True
                    life.journal["nativeInvocations"] = 0
                    life.journal["stopReason"] = "stop_before_invocation"
                    life.save()
                else:
                    invoke_native(paths["target"], paths["status"])
                    for _ in range(1221):
                        current = clock()
                        if current < previous or current != current:
                            sticky_stop = True
                            life.journal["stopReason"] = "clock_invalid"
                        previous = current
                        if paths["status"].exists():
                            projection = native_terminal(bounded_json(paths["status"]), run_id)
                            terminal = True
                            life.journal["nativeTerminal"] = True
                            life.journal["stopReason"] = "native_terminal"
                            break
                        if stop_requested() or current >= life.journal["expiresAtUnix"] - 240:
                            sticky_stop = True
                            life.journal["stopReason"] = "stop_or_cleanup_cutoff"
                        if sticky_stop and stop_at is None:
                            atomic_json(
                                paths["stop"],
                                {
                                    "schemaVersion": 1,
                                    "planVersion": VERSION,
                                    "runId": run_id,
                                    "owner": owner,
                                    "stop": True,
                                },
                            )
                            stop_at = current
                        if stop_at is not None and current >= stop_at + 20:
                            break
                        sleep(1)
                    if not terminal and not sticky_stop:
                        life.journal["stopReason"] = "watch_iteration_limit"
                        sticky_stop = True
    except Exception:
        life.journal["stopReason"] = "action_failure"
        life.journal["actionFailed"] = True
        sticky_stop = True
    finally:
        try:
            if (
                sticky_stop
                and life.journal.get("targetPublished", False)
                and not terminal
                and not paths["stop"].exists()
            ):
                atomic_json(
                    paths["stop"],
                    {
                        "schemaVersion": 1,
                        "planVersion": VERSION,
                        "runId": run_id,
                        "owner": owner,
                        "stop": True,
                    },
                )
            if projection is not None:
                atomic_json(directory / "native-terminal.json", projection)
        except Exception:
            life.journal["actionFailed"] = True
        try:
            life.observe()
        except Exception:
            life.journal["observationsConfirmed"] = False
        receipt = life.cleanup()
        # Preserve private target/status/journal for exact review and explicit
        # identity-matched local teardown. A second run cannot overwrite them.
        life.journal["targetRetained"] = paths["target"].exists() or paths["used"].exists()
        life.journal["stopPreserved"] = sticky_stop
        life.save()
    result = {
        **receipt,
        "nativeInvocations": life.journal["nativeInvocations"],
        "nativeTerminal": terminal,
        "stopPreserved": sticky_stop,
        "actionFailed": life.journal.get("actionFailed", False),
    }
    result["nativeOutcome"] = projection["outcome"] if projection else "unmeasured"
    result["outcome"] = (
        "failed"
        if result["actionFailed"]
        else "stopped"
        if sticky_stop or result["nativeOutcome"] == "stopped"
        else "failed"
        if result["nativeOutcome"] == "failed"
        or not terminal
        or not receipt["cleanupConfirmed"]
        or not receipt["observationsConfirmed"]
        else "characterized"
    )
    atomic_json(directory / "action.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(packet(), indent=2))
