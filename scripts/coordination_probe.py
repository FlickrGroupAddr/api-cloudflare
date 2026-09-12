"""Bounded native D1 admission and DO wake proofs; disposable fixtures only."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from . import coordination_backup
    from . import runtime_permissions_probe as runtime
    from .native_secret_probe import deploy_with_bearer
    from .secret_store_probe import private_process
except ImportError:
    import coordination_backup
    import runtime_permissions_probe as runtime
    from native_secret_probe import deploy_with_bearer
    from secret_store_probe import private_process

ROOT = runtime.ROOT
RUNS = ROOT / ".coordination-runs"
PROBE = ROOT / "probes/coordination"
Run = runtime.Run
ProbeError = runtime.ProbeError
MIGRATIONS = [
    "0001_foundation.sql",
    "0002_audit_component.sql",
    "0003_submission_coordination.sql",
    "0004_fail_polite_attempts.sql",
]


def hashes() -> dict[str, str]:
    paths = [
        *ROOT.glob("src/*.ts"),
        *ROOT.glob("migrations/*.sql"),
        *PROBE.glob("*.ts"),
        PROBE / "schema.sql",
        PROBE / "local.mjs",
        Path(__file__),
        ROOT / "scripts/runtime_permissions_probe.py",
        ROOT / "scripts/coordination_backup.py",
        ROOT / "scripts/fail_polite_cases.py",
        ROOT / "scripts/fail_polite_mutations.py",
        ROOT / "scripts/foundation_probe.py",
        ROOT / "scripts/native_secret_probe.py",
        ROOT / "package-lock.json",
        ROOT / "tsconfig.json",
    ]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def statements(source: str) -> list[str]:
    result, pending = [], ""
    for line in source.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            result.append(pending.strip())
            pending = ""
    if pending.strip():
        raise ProbeError("Incomplete SQL migration.")
    return result


def new_run(environment: str, kind: str) -> Run:
    run_id = "rp-" + secrets.token_hex(12)
    directory = RUNS / run_id
    directory.mkdir(parents=True)
    name = "fga-" + run_id
    run = Run(
        directory,
        {
            "runId": run_id,
            "environment": environment,
            "kind": kind,
            "workerName": name,
            "databaseName": name + "-db",
            "sourceHashes": hashes(),
        },
    )
    run.save()
    return run


def validate(run: Run) -> None:
    if (
        run.directory.resolve().parent != RUNS.resolve()
        or run.directory.name != run.run_id
        or not re.fullmatch(r"rp-[a-f0-9]{24}", run.run_id)
    ):
        raise ProbeError("Invalid coordination run directory.")
    if run.state["environment"] == "cloudflare":
        runtime.checked_resource_names(run)


def config(run: Run) -> Path:
    data: dict[str, Any] = {
        "name": run.state["workerName"],
        "main": str(PROBE / "worker.ts"),
        "compatibility_date": "2026-09-11",
        "workers_dev": True,
        "preview_urls": False,
        "observability": {"enabled": False},
        "vars": {
            "PROOF_BUILD": run.run_id,
            "PROOF_MODE": run.state["kind"],
            "PROOF_EXPIRES": str(int((time.time() + 1800) * 1000)),
        },
    }
    if run.state.get("accountId"):
        data["account_id"] = run.state["accountId"]
        data["d1_databases"] = [
            {
                "binding": "DB",
                "database_name": run.state["databaseName"],
                "database_id": run.state["databaseId"],
                "migrations_dir": str(ROOT / "migrations"),
            }
        ]
    if run.state["kind"] in {"scheduling", "fail-polite"}:
        data["durable_objects"] = {
            "bindings": [{"name": "COORD", "class_name": "ProbePartitionWake"}]
        }
        data["exports"] = {"ProbePartitionWake": {"type": "durable-object", "storage": "sqlite"}}
        data["triggers"] = {"crons": ["* * * * *"]}
    path = run.directory / "wrangler.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def create_database(run: Run) -> None:
    validate(run)
    identity = json.loads(runtime.wrangler(run, "identity", "whoami", "--json").stdout)
    if not identity.get("loggedIn") or len(identity.get("accounts", [])) != 1:
        raise ProbeError("Exactly one authenticated Cloudflare account is required.")
    run.state["accountId"] = identity["accounts"][0]["id"]
    if any(
        row["name"] == run.state["databaseName"]
        for row in runtime.databases(run, "database-preflight")
    ):
        raise ProbeError("Generated database name is not unused.")
    run.state["databaseAttempted"] = True
    run.save()
    runtime.wrangler(
        run, "database-create", "d1", "create", run.state["databaseName"], "--update-config=false"
    )
    rows = [
        row
        for row in runtime.databases(run, "database-created")
        if row["name"] == run.state["databaseName"]
    ]
    if len(rows) != 1:
        raise ProbeError("Created database identity ambiguous.")
    run.state["databaseId"] = rows[0]["uuid"]
    run.save()


def provision(run: Run, token: str) -> None:
    create_database(run)
    path = config(run)
    runtime.wrangler(
        run,
        "migrations",
        "d1",
        "migrations",
        "apply",
        run.state["databaseName"],
        "--remote",
        "--config",
        str(path),
    )
    runtime.wrangler(
        run,
        "fixture-schema",
        "d1",
        "execute",
        run.state["databaseName"],
        "--remote",
        "--file",
        str(PROBE / "schema.sql"),
        "--yes",
        "--json",
    )
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
        raise ProbeError("Generated Worker name is not unused.")
    runtime.command(
        run, "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
    )
    run.state["workerAttempted"] = True
    run.save()
    output = deploy_with_bearer(run, path, token)
    urls = re.findall(r"https://[a-z0-9.-]+\.workers\.dev", output)
    if len(set(urls)) != 1:
        raise ProbeError("Ambiguous proof URL.")
    run.state["url"] = urls[0]
    run.save()
    if run.state["kind"] in {"scheduling", "fail-polite"}:
        owned = namespaces(run)
        if len(owned) != 1 or owned[0].get("class") != "ProbePartitionWake":
            raise ProbeError("Created namespace could not be identified.")
        run.state["namespaceId"] = owned[0]["id"]
        run.save()


def start_local(run: Run, token: str) -> tuple[subprocess.Popen[str], Any]:
    path = config(run)
    runtime.command(
        run, "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
    )
    bundle = run.directory / "bundle"
    runtime.wrangler(
        run, "build", "deploy", "--dry-run", "--config", str(path), "--outdir", str(bundle)
    )
    settings = json.loads(path.read_text(encoding="utf-8"))
    local = {
        "bundle": str(bundle / "worker.js"),
        "vars": settings["vars"],
        "statements": [
            statements((ROOT / "migrations" / name).read_text(encoding="utf-8"))
            for name in MIGRATIONS
        ]
        + [statements((PROBE / "schema.sql").read_text(encoding="utf-8"))],
    }
    local_path = run.directory / "local.json"
    local_path.write_text(json.dumps(local), encoding="utf-8")
    error_log = (run.directory / "local-stderr.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [runtime.NODE, str(PROBE / "local.mjs"), str(local_path)],
        cwd=ROOT,
        env={**os.environ, "FGA_COORDINATION_TOKEN": token},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=error_log,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    assert process.stdout is not None
    line = process.stdout.readline()
    if not line:
        process.wait(timeout=15)
        error_log.close()
        raise ProbeError("Local runtime did not start; inspect its private log.")
    run.state["url"] = json.loads(line)["url"].rstrip("/")
    run.save()
    return process, error_log


class Client:
    def __init__(self, run: Run, token: str):
        self.run, self.token = run, token

    def request(self, action: str, expected: int = 200, **data: Any) -> Any:
        safe = action in {
            "status",
            "seed",
            "state",
            "snapshot",
            "view",
            "due",
            "probe-events",
            "object-status",
        }
        url = urlsplit(self.run.state["url"])
        if self.run.state["environment"] == "cloudflare":
            if (
                url.scheme != "https"
                or not url.hostname
                or not url.hostname.endswith(".workers.dev")
            ):
                raise ProbeError("Request escaped the disposable Worker boundary.")
            connection_type = http.client.HTTPSConnection
        else:
            if url.scheme != "http" or url.hostname != "127.0.0.1":
                raise ProbeError("Local request escaped loopback.")
            connection_type = http.client.HTTPConnection
        for attempt in range(6 if safe else 1):
            connection = connection_type(url.hostname, url.port, timeout=30)
            try:
                body = (
                    None if action == "status" else json.dumps({"action": action, **data}).encode()
                )
                connection.request(
                    "GET" if body is None else "POST",
                    "/status" if body is None else "/proof",
                    body,
                    {
                        "Authorization": "Bearer " + self.token,
                        "Content-Type": "application/json",
                        "User-Agent": "FlickrGroupAddr-CoordinationProof/0.0.0",
                    },
                )
                response = connection.getresponse()
                status, raw = response.status, response.read(2_097_153)
                if len(raw) > 2_097_152:
                    raise ProbeError("Oversized proof response.")
                if safe and status in {404, 429, 500, 502, 503, 504} and attempt < 5:
                    self.run.state.setdefault("controlRetries", []).append(
                        {"action": action, "status": status}
                    )
                    self.run.save()
                    time.sleep(1)
                    continue
                try:
                    payload = json.loads(raw)
                except ValueError:
                    self.run.state["lastFailure"] = {
                        "action": action,
                        "status": status,
                        "bodySha2_256": hashlib.sha256(raw).hexdigest(),
                    }
                    self.run.save()
                    raise ProbeError(f"Non-JSON {action} response (HTTP {status}).") from None
                if status != expected or payload.get("build") != self.run.run_id:
                    raise ProbeError(
                        f"Unexpected {action} result (HTTP {status}, expected {expected}). "
                        + (
                            str(payload.get("result", {}).get("outcome", ""))
                            if action == "wake"
                            else ""
                        )
                    )
                return payload["result"]
            finally:
                connection.close()
        raise ProbeError("Bounded control-read retries exhausted.")

    def ready(self) -> None:
        deadline, consecutive = time.monotonic() + 120, 0
        while time.monotonic() < deadline:
            try:
                self.request("status")
                self.request("state")
                consecutive += 1
                if consecutive >= 3:
                    return
            except ProbeError, OSError, http.client.HTTPException:
                consecutive = 0
            time.sleep(1)
        raise ProbeError("Proof readiness did not converge.")


class Report:
    def __init__(self, run: Run):
        self.run = run
        self.data: dict[str, Any] = {
            "schemaVersion": 1,
            "kind": run.state["kind"],
            "environment": run.state["environment"],
            "productionConformance": False,
            "collectedAt": datetime.now(UTC).isoformat(),
            "sourceHashes": run.state["sourceHashes"],
            "cases": [],
        }

    def save(self) -> None:
        (self.run.directory / "report.json").write_text(
            json.dumps(self.data, indent=2) + "\n", encoding="utf-8"
        )

    def check(self, name: str, condition: bool, **detail: Any) -> None:
        self.data["cases"].append({"id": name, "passed": bool(condition), **detail})
        self.save()
        print(f"Coordination case: {name}: {'pass' if condition else 'FAIL'}", flush=True)
        if not condition:
            raise ProbeError("Failed case: " + name)


def selection(binding: int, groups: list[str], revision: int = 1) -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "photoBinding": {
            "fgaPhotoBindingId": f"binding-{binding}",
            "expectedVerificationRevision": revision,
        },
        "flickrGroupIds": groups,
    }


def admission_cases(client: Client, report: Report) -> None:
    client.request("seed")

    def admit(binding: int, groups: list[str], **options: Any) -> Any:
        return client.request("admit", request=selection(binding, groups), **options)

    def snapshot() -> str:
        return client.request("snapshot")["digest"]

    def hints(operation: str) -> list[Any]:
        return [
            e
            for e in client.request("probe-events")
            if e["kind"] == "hint" and e["detail"] == operation
        ]

    first = admit(0, ["group-c", "group-a", "group-b"], operation="many")
    report.check(
        "admission.complete_ordered_batch",
        [i["groupId"] for i in first["items"]] == ["group-c", "group-a", "group-b"]
        and all(i["created"] and i["ordinal"] == "1" for i in first["items"]),
    )
    state = client.request("state")
    partition_by_group = {p["group_id"]: p for p in state["partitions"]}
    report.check(
        "admission.one_canonical_post_commit_hint",
        len(hints("many")) == 1
        and first["hint"]["partitionId"] == partition_by_group["group-a"]["partition_id"],
    )
    before = snapshot()
    again = admit(0, ["group-c", "group-a", "group-b"], operation="retry")
    report.check(
        "admission.identical_retry_no_change",
        before == snapshot()
        and all(not i["created"] for i in again["items"])
        and [i["intentId"] for i in first["items"]] == [i["intentId"] for i in again["items"]]
        and not hints("retry"),
    )
    mixed = admit(0, ["group-b", "group-d"], operation="mixed")
    report.check(
        "admission.mixed_existing_missing",
        [i["created"] for i in mixed["items"]] == [False, True] and len(hints("mixed")) == 1,
    )
    old_due = partition_by_group["group-a"]["due_us"]
    behind = admit(1, ["group-a"], operation="behind")
    state = client.request("state")
    report.check(
        "admission.single_group_behind_head",
        behind["items"][0]["ordinal"] == "2"
        and behind["hint"] is None
        and not hints("behind")
        and next(p for p in state["partitions"] if p["group_id"] == "group-a")["due_us"] == old_due,
    )
    groups = [f"limit-{i:02}" for i in reversed(range(60))]
    maximum = admit(2, groups, operation="sixty")
    state = client.request("state")
    large = [p for p in state["partitions"] if p["group_id"].startswith("limit-")]
    report.check(
        "admission.sixty_groups_one_transaction",
        len(maximum["items"]) == 60
        and len(large) == 60
        and len({p["due_us"] for p in large}) == 1
        and all(p["next_ordinal"] == "2" for p in large)
        and len(hints("sixty")) == 1
        and [i["groupId"] for i in maximum["items"]] == groups,
    )
    invalid = [
        selection(3, []),
        selection(3, ["x", "x"]),
        selection(3, ["valid", "bad group"]),
        selection(3, [f"x{i}" for i in range(61)]),
        {**selection(3, ["x"]), "flickrPhotoId": "forged"},
        selection(3, ["x"], 2),
        selection(99, ["x"]),
    ]
    before = snapshot()
    for request in invalid:
        client.request("admit", expected=409, request=request)
    for auth in [
        {"installationId": "installation-a", "credentialDigest": "c" * 64},
        {"installationId": "missing", "credentialDigest": "a" * 64},
    ]:
        client.request("admit", expected=409, request=selection(3, ["x"]), auth=auth)
    report.check("admission.complete_validation_before_writes", snapshot() == before)
    for stage in range(8):
        before = snapshot()
        client.request(
            "admit", expected=409, request=selection(4, ["fault-a", "fault-b"]), faultStage=stage
        )
        report.check(f"admission.rollback_stage_{stage}", snapshot() == before)
    client.request("fail-group", value="fault-c")
    before = snapshot()
    client.request(
        "admit", expected=409, request=selection(4, ["fault-a", "fault-b", "fault-c", "fault-d"])
    )
    report.check("admission.rollback_inside_multirow_insert", snapshot() == before)
    client.request("fail-group")
    recovered = admit(4, ["fault-a", "fault-b", "fault-c", "fault-d"])
    report.check(
        "admission.rollback_does_not_consume_ordinals",
        all(i["ordinal"] == "1" for i in recovered["items"]),
    )
    with ThreadPoolExecutor(max_workers=6) as executor:
        same = list(
            executor.map(lambda _: admit(5, ["same-a", "same-b"], operation="same-race"), range(6))
        )
    report.check(
        "admission.concurrent_identical_natural_keys",
        sum(sum(i["created"] for i in r["items"]) for r in same) == 2
        and len(hints("same-race")) == 1
        and len({r["items"][0]["intentId"] for r in same}) == 1,
    )
    with ThreadPoolExecutor(max_workers=6) as executor:
        fifo = list(
            executor.map(
                lambda binding: admit(binding, ["fifo-shared"], operation="fifo-race"),
                range(10, 16),
            )
        )
    report.check(
        "admission.concurrent_distinct_committed_fifo",
        sorted(int(r["items"][0]["ordinal"]) for r in fifo) == list(range(1, 7))
        and len(hints("fifo-race")) == 1,
    )
    tail = admit(16, ["fifo-shared"])
    report.check("admission.happens_before_fifo", tail["items"][0]["ordinal"] == "7")
    before = client.request("state")
    client.request(
        "admit",
        expected=409,
        request=selection(17, ["binding-race"]),
        bindingId="binding-17",
        raceBinding=True,
    )
    after = client.request("state")
    report.check(
        "admission.binding_revision_race_rolls_back",
        all(before[k] == after[k] for k in ["partitions", "intents", "events", "guards"]),
    )
    client.request("age-binding", bindingId="binding-80", value=0)
    existing = admit(80, ["existing-one"])
    client.request("age-binding", bindingId="binding-80", value=16000)
    before = snapshot()
    retry = admit(80, ["existing-one"])
    client.request("admit", expected=409, request=selection(80, ["existing-one", "existing-two"]))
    report.check(
        "admission.expired_proof_only_all_existing_retry",
        not retry["items"][0]["created"]
        and retry["items"][0]["intentId"] == existing["items"][0]["intentId"]
        and snapshot() == before,
    )
    blocked = admit(20, ["protected"])
    client.request("block", partitionId=blocked["hint"]["partitionId"])
    before = snapshot()
    protected = admit(20, ["protected"])
    report.check(
        "admission.permanent_block_reused_without_revival",
        not protected["items"][0]["created"]
        and protected["items"][0]["state"] == "delivery_uncertain"
        and protected["items"][0]["blockReason"] == "delivery_uncertain"
        and snapshot() == before,
    )
    for kind in ["intent", "ordinal", "event", "block"]:
        client.request("guard-write", expected=409, kind=kind)
    report.check("admission.retained_identity_and_events", snapshot() == before)
    large = admit(21, ["large-ordinal"])
    pid = large["hint"]["partitionId"]
    client.request("counter", partitionId=pid, value="9007199254740992")
    values = [admit(binding, ["large-ordinal"])["items"][0]["ordinal"] for binding in [22, 23]]
    report.check(
        "admission.exact_integers_above_javascript_limit",
        values == ["9007199254740992", "9007199254740993"],
    )
    overflow = admit(24, ["zz-overflow"])
    client.request(
        "counter", partitionId=overflow["hint"]["partitionId"], value="9223372036854775807"
    )
    before = snapshot()
    client.request(
        "admit", expected=409, request=selection(25, ["new-before-overflow", "zz-overflow"])
    )
    report.check("admission.counter_exhaustion_fails_whole_batch", before == snapshot())
    client.request("gate", value=0)
    allowed = admit(26, ["paused-admission"])
    report.check(
        "admission.write_pause_does_not_block_handoff",
        allowed["items"][0]["created"] and not client.request("due"),
    )
    client.request("gate", value=1)
    lost = admit(27, ["lost-hint-a", "lost-hint-b"], failure=True, operation="lost-hint")
    state = client.request("state")
    pending = [p for p in state["partitions"] if p["group_id"].startswith("lost-hint-")]
    ready = [client.request("view", partitionId=p["partition_id"]) for p in pending]
    report.check(
        "admission.lost_hint_keeps_durable_due_work",
        len(ready) == 2
        and all(int(p["dueUs"]) <= int(p["nowUs"]) for p in ready)
        and len(hints("lost-hint")) == 1
        and all(i["created"] for i in lost["items"]),
    )
    report.check(
        "admission.no_retained_transaction_guards", client.request("state")["guards"] == []
    )


def await_condition(check: Any, timeout: float, description: str) -> Any:
    deadline = time.monotonic() + timeout
    next_progress = time.monotonic() + 30
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        if time.monotonic() >= next_progress:
            print("Waiting for " + description + ".", flush=True)
            next_progress = time.monotonic() + 30
        time.sleep(0.5)
    raise ProbeError("Timed out waiting for " + description + ".")


def scheduling_cases(client: Client, report: Report) -> None:
    client.request("seed")

    def admit(binding: int, groups: list[str]) -> Any:
        return client.request("admit", request=selection(binding, groups))

    def view(partition: str) -> Any:
        return client.request("view", partitionId=partition)

    def events(partition: str, kind: str) -> list[Any]:
        return [
            e
            for e in client.request("probe-events")
            if e["partition_id"] == partition and e["kind"] == kind
        ]

    admit(0, ["schedule-a", "schedule-b"])
    state = client.request("state")
    parts = {p["group_id"]: p["partition_id"] for p in state["partitions"]}
    pa, pb = parts["schedule-a"], parts["schedule-b"]
    with ThreadPoolExecutor(max_workers=6) as executor:
        claims = list(
            executor.map(
                lambda n: client.request(
                    "claim", partitionId=pa, operation=f"claim-{n}", revision="1"
                ),
                range(6),
            )
        )
    winners = [value for value in claims if value is not None]
    report.check(
        "scheduling.one_concurrent_lease_winner",
        len(winners) == 1 and view(pa)["generation"] == "1",
    )
    owner = winners[0]
    report.check(
        "scheduling.duplicate_and_stale_hint_no_claim",
        client.request("claim", partitionId=pa, revision="1") is None
        and client.request("claim", partitionId=pb, revision="0") is None
        and client.request("claim", partitionId=pb, revision="9223372036854775808") is None
        and view(pb)["generation"] == "0",
    )
    old_expiry = int(view(pa)["leaseExpiresUs"])
    renewed = client.request("renew", lease=owner)
    report.check(
        "scheduling.renew_current_owner", renewed and int(view(pa)["leaseExpiresUs"]) >= old_expiry
    )
    wrong = {**owner, "leaseId": "wrong-lease"}
    before = client.request("snapshot")
    report.check(
        "scheduling.wrong_lease_id_cannot_mutate",
        not client.request("renew", lease=wrong)
        and not client.request("release", lease=wrong)
        and not client.request("defer", lease=wrong, delayMs=1000)
        and client.request("snapshot") == before,
    )
    report.check("scheduling.release_current_owner", client.request("release", lease=owner))
    successor = client.request("claim", partitionId=pa, operation="successor")
    before = client.request("snapshot")
    report.check(
        "scheduling.stale_generation_fences_all_mutations",
        successor["generation"] == "2"
        and not client.request("renew", lease=owner)
        and not client.request("release", lease=owner)
        and not client.request("defer", lease=owner, delayMs=1000)
        and client.request("snapshot") == before,
    )
    report.check(
        "scheduling.defer_commits_exact_due_and_releases",
        client.request("defer", lease=successor, delayMs=60000),
    )
    deferred = view(pa)
    state = client.request("state")
    head = next(i for i in state["intents"] if i["intent_id"] == successor["headId"])
    report.check(
        "scheduling.no_early_claim_and_exact_due",
        head["state"] == "retrying"
        and head["retry_us"] == deferred["dueUs"]
        and deferred["leaseId"] is None
        and client.request("claim", partitionId=pa) is None,
    )
    later = admit(1, ["schedule-a"])
    report.check(
        "scheduling.later_intent_cannot_advance_head_due",
        later["items"][0]["ordinal"] == "2"
        and later["hint"] is None
        and view(pa)["dueUs"] == deferred["dueUs"],
    )
    for scope in ["deployment", "user"]:
        before_generation = view(pb)["generation"]
        client.request("gate", scope=scope, value=0)
        report.check(
            "scheduling.paused_" + scope + "_no_claim_churn",
            client.request("claim", partitionId=pb) is None
            and view(pb)["generation"] == before_generation,
        )
        client.request("gate", scope=scope, value=1)
    client.request("generation", partitionId=pb, value="9007199254740992")
    big = client.request("claim", partitionId=pb)
    report.check("scheduling.exact_64bit_fence", big["generation"] == "9007199254740993")
    report.check(
        "scheduling.reject_number_fence",
        not client.request("release", lease={**big, "generation": float(big["generation"])}),
    )
    client.request("release", lease=big)
    lost = admit(2, ["lost-claim-response"])
    plost = lost["hint"]["partitionId"]
    client.request(
        "claim",
        expected=409,
        partitionId=plost,
        operation="lost-response",
        policy={"leaseMs": 2000, "invocationMs": 1000},
        failure=True,
    )
    lost_view = view(plost)
    report.check(
        "scheduling.lost_claim_response_retains_lease",
        lost_view["leaseId"] is not None
        and lost_view["generation"] == "1"
        and client.request("claim", partitionId=plost) is None,
    )
    await_condition(
        lambda: int(view(plost)["nowUs"]) >= int(lost_view["leaseExpiresUs"]),
        15,
        "database lease expiry",
    )
    takeover = client.request("claim", partitionId=plost)
    report.check(
        "scheduling.database_expiry_allows_successor",
        takeover is not None and takeover["generation"] == "2",
    )
    stale = {
        "partitionId": plost,
        "leaseId": lost_view["leaseId"],
        "generation": "1",
        "headId": lost_view["headId"],
        "expiresUs": lost_view["leaseExpiresUs"],
        "invocationId": "lost-response",
    }
    report.check(
        "scheduling.expired_owner_cannot_overwrite_successor",
        not client.request("defer", lease=stale, delayMs=1),
    )
    do = admit(3, ["do-duplicate"])
    hint = do["hint"]
    with ThreadPoolExecutor(max_workers=6) as executor:
        wake_results = list(executor.map(lambda _: client.request("wake", hint=hint), range(6)))
    report.check(
        "scheduling.do_duplicate_delivery_one_owner",
        sum(r.get("lease") is not None for r in wake_results) == 1,
    )
    pdo = hint["partitionId"]
    observed = client.request("object-status", partitionId=pdo)
    lease_before = view(pdo)
    client.request("evict", expected=409, partitionId=pdo)
    restarted = client.request("object-status", partitionId=pdo)
    report.check(
        "scheduling.real_object_reset_keeps_d1_authority",
        restarted["instance"] != observed["instance"]
        and restarted["partitionId"] == pdo
        and view(pdo)["leaseId"] == lease_before["leaseId"]
        and view(pdo)["generation"] == lease_before["generation"],
    )
    report.check(
        "scheduling.restart_cannot_duplicate_claim",
        client.request("wake", hint=hint)["lease"] is None,
    )
    stale_wake = client.request("wake", hint={**hint, "wakeRevision": "0"})
    report.check(
        "scheduling.stale_do_hint_is_noop",
        stale_wake.get("stale") and view(pdo)["generation"] == lease_before["generation"],
    )
    alarm_batch = admit(4, ["do-alarm"])
    palarm = alarm_batch["hint"]["partitionId"]
    alarm_owner = client.request("claim", partitionId=palarm)
    client.request("defer", lease=alarm_owner, delayMs=8000)
    due = view(palarm)
    armed = client.request(
        "wake", hint={"partitionId": palarm, "wakeRevision": due["wakeRevision"]}
    )
    alarm_status = client.request("object-status", partitionId=palarm)
    report.check(
        "scheduling.future_alarm_is_advisory_only",
        armed["lease"] is None and alarm_status["alarm"] is not None,
    )
    client.request("evict", expected=409, partitionId=palarm)
    fresh = client.request("object-status", partitionId=palarm)
    report.check(
        "scheduling.alarm_survives_real_object_reset",
        fresh["instance"] != alarm_status["instance"]
        and fresh["partitionId"] == palarm
        and fresh["alarm"] is not None,
    )
    alarm_events = await_condition(
        lambda: [e for e in events(palarm, "wake_alarm") if e["detail"] == "claimed"],
        30,
        "actual Durable Object alarm",
    )
    report.check(
        "scheduling.actual_alarm_rechecks_database_due",
        int(alarm_events[0]["created_us"]) >= int(due["dueUs"])
        and view(palarm)["generation"] == "2",
    )
    forgotten = admit(5, ["forgotten-alarm"])
    pforgot = forgotten["hint"]["partitionId"]
    lease = client.request("claim", partitionId=pforgot)
    client.request("defer", lease=lease, delayMs=3000)
    d = view(pforgot)
    client.request("wake", hint={"partitionId": pforgot, "wakeRevision": d["wakeRevision"]})
    client.request("forget", partitionId=pforgot)
    await_condition(
        lambda: int(view(pforgot)["nowUs"]) >= int(d["dueUs"]), 15, "forgotten alarm due time"
    )
    client.request("sweep")
    report.check(
        "scheduling.lost_alarm_recovers_through_same_sweep_claim",
        bool([e for e in events(pforgot, "wake_manual") if e["detail"] == "claimed"])
        and not events(pforgot, "wake_alarm"),
    )
    if client.run.state["environment"] == "cloudflare":
        ticks = await_condition(
            lambda: [e for e in client.request("probe-events") if e["kind"] == "cron_tick"],
            1020,
            "provider Cron Trigger propagation",
        )
        previous_tick = max(int(e["detail"]) for e in ticks)
        ticks = await_condition(
            lambda: [
                e
                for e in client.request("probe-events")
                if e["kind"] == "cron_tick" and int(e["detail"]) > previous_tick
            ],
            120,
            "next minutely provider tick",
        )
        report.check(
            "scheduling.actual_provider_minutely_schedule",
            min(int(e["detail"]) for e in ticks) - previous_tick == 60000,
        )
        cron_batch = admit(6, ["cron-lost-hint"])
        pcron = cron_batch["hint"]["partitionId"]
        cron_due = view(pcron)["dueUs"]
        client.request("cron-enable", value=1)
        cron_events = await_condition(
            lambda: [e for e in events(pcron, "wake_cron") if e["detail"] == "claimed"],
            120,
            "cron recovery of an unhinted partition",
        )
        client.request("cron-enable", value=0)
        report.check(
            "scheduling.actual_cron_recovers_lost_hint",
            int(cron_events[0]["created_us"]) >= int(cron_due),
            observedLagMs=(int(cron_events[0]["created_us"]) - int(cron_due)) // 1000,
        )
    else:
        report.data["hostedCron"] = "Not claimed by the local harness; required by the hosted run."
    # Quiesce the earlier actors before final snapshot-based negative tests.
    # The second synthetic owner remains enabled, so its guards are still tested.
    client.request("gate", scope="user", value=0)
    client.request("age-binding", bindingId="binding-99", value=0)
    client.request(
        "admit",
        request=selection(99, ["bounded-invocation", "generation-exhaustion"]),
        auth={"installationId": "installation-b", "credentialDigest": "b" * 64},
    )
    final_state = client.request("state")
    final_parts = {
        p["group_id"]: p["partition_id"]
        for p in final_state["partitions"]
        if p["user_id"] == "owner-b"
    }
    bounded = {"hint": {"partitionId": final_parts["bounded-invocation"]}}
    pbounded = bounded["hint"]["partitionId"]
    limited = client.request(
        "claim", partitionId=pbounded, policy={"leaseMs": 60000, "invocationMs": 500}
    )
    deadline = view(pbounded)["invocationDeadlineUs"]
    await_condition(
        lambda: int(view(pbounded)["nowUs"]) >= int(deadline), 10, "bounded invocation deadline"
    )
    report.check(
        "scheduling.invocation_deadline_stops_renewal",
        not client.request("renew", lease=limited) and client.request("release", lease=limited),
    )
    pov = final_parts["generation-exhaustion"]
    client.request("generation", partitionId=pov, value="9223372036854775807")
    before = client.request("snapshot")
    report.check(
        "scheduling.generation_exhaustion_is_not_wrapped",
        client.request("claim", partitionId=pov) is None and client.request("snapshot") == before,
    )
    client.request("guard-write", expected=409, kind="lease")
    report.check("scheduling.lease_history_is_append_only", client.request("snapshot") == before)
    report.check(
        "scheduling.no_retained_transaction_guards", client.request("state")["guards"] == []
    )


def namespaces(run: Run) -> list[dict[str, Any]]:
    validate(run)
    account = run.state.get("accountId", "")
    if not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ProbeError("Invalid account identity for namespace inventory.")
    auth = private_process([runtime.NODE, str(runtime.WRANGLER), "auth", "token", "--json"])
    if auth.returncode:
        raise ProbeError("Operator identity unavailable for namespace inventory.")
    credentials = json.loads(auth.stdout)
    if credentials.get("type") not in {"oauth", "api_token"} or not credentials.get("token"):
        raise ProbeError("Unsupported operator identity.")
    found = []
    for page in range(1, 101):
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/"
            f"durable_objects/namespaces?page={page}&per_page=1000"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + credentials["token"],
                "User-Agent": "FlickrGroupAddr-CoordinationProof/0.0.0",
            },
        )
        try:
            response = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=30)
        except urllib.error.HTTPError:
            raise ProbeError("Namespace inventory was refused.") from None
        with response:
            raw = response.read(2_097_153)
        if len(raw) > 2_097_152:
            raise ProbeError("Namespace inventory exceeded its bound.")
        data = json.loads(raw)
        if data.get("success") is not True or not isinstance(data.get("result"), list):
            raise ProbeError("Invalid namespace inventory.")
        rows = data["result"]
        found.extend(row for row in rows if row.get("script") == run.state["workerName"])
        if len(rows) < 1000:
            return found
    raise ProbeError("Namespace inventory pagination exceeded its bound.")


def retire_namespace(run: Run) -> None:
    validate(run)
    if run.state["kind"] in {"scheduling", "fail-polite", "clocks", "intake"} and run.state.get(
        "workerAttempted"
    ):
        rows = namespaces(run)
        if rows:
            if len(rows) != 1 or rows[0].get("class") != "ProbePartitionWake":
                raise ProbeError("Unexpected namespace association; retirement refused.")
            expected = run.state.get("namespaceId")
            if expected and expected != rows[0].get("id"):
                raise ProbeError("Namespace identity changed; retirement refused.")
            run.state["namespaceId"] = rows[0]["id"]
            run.save()
            # Standard declarative class retirement, not force-delete. No live
            # class or binding remains in this inert replacement Worker.
            retirement = {
                "name": run.state["workerName"],
                "account_id": run.state["accountId"],
                "main": str(PROBE / "cleanup.ts"),
                "compatibility_date": "2026-09-11",
                "workers_dev": True,
                "preview_urls": False,
                "observability": {"enabled": False},
                "triggers": {"crons": []},
                "exports": {"ProbePartitionWake": {"type": "durable-object", "state": "deleted"}},
            }
            path = run.directory / "retire.json"
            path.write_text(json.dumps(retirement, indent=2) + "\n", encoding="utf-8")
            runtime.wrangler(run, "retire-object-class", "deploy", "--config", str(path))
            if namespaces(run):
                raise ProbeError("Namespace retirement unconfirmed.")
        run.state["namespaceDeleted"] = True
        run.save()


def cleanup(run: Run) -> None:
    validate(run)
    if run.state.get("restoreRunId"):
        child_id = run.state["restoreRunId"]
        if child_id == run.run_id or not re.fullmatch(r"rp-[a-f0-9]{24}", child_id):
            raise ProbeError("Invalid archive cleanup reference.")
        child_path = RUNS / child_id
        child = Run(
            child_path, json.loads((child_path / "manifest.json").read_text(encoding="utf-8"))
        )
        if child.state.get("kind") != "archive" or child.state.get("workerAttempted"):
            raise ProbeError("Unexpected archive cleanup target.")
        cleanup(child)

    retire_namespace(run)
    runtime.cleanup(run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["local", "hosted", "cleanup"])
    parser.add_argument(
        "kind", choices=["admission", "scheduling", "fail-polite"], nargs="?", default="admission"
    )
    parser.add_argument("--run")
    parser.add_argument(
        "--mutation-check",
        choices=[
            "marker_order",
            "unknown_retry",
            "unresolved_retry",
            "inclusive_clock",
            "split_block",
            "removed_guard",
        ],
    )
    args = parser.parse_args()
    if args.environment == "cleanup":
        directory = Path(args.run or "").resolve()
        if directory.parent != RUNS.resolve():
            raise ProbeError("Cleanup outside coordination runs.")
        run = Run(directory, json.loads((directory / "manifest.json").read_text(encoding="utf-8")))
        validate(run)
        cleanup(run)
        return 0
    run = new_run("cloudflare" if args.environment == "hosted" else "local", args.kind)
    report = Report(run)
    process, error_log = None, None
    token = secrets.token_urlsafe(32)
    print("Coordination private run: " + str(run.directory), flush=True)
    try:
        if args.environment == "hosted":
            provision(run, token)
        else:
            process, error_log = start_local(run, token)
        client = Client(run, token)
        client.ready()
        if args.kind == "admission":
            admission_cases(client, report)
        elif args.kind == "scheduling":
            scheduling_cases(client, report)
        else:
            from fail_polite_cases import cases, mutation_check

            if args.mutation_check:
                report.data["mutationOnly"] = args.mutation_check
                mutation_check(client, report, args.mutation_check)
            else:
                cases(client, report)
        if args.environment == "hosted" and args.kind in {"admission", "fail-polite"}:
            retire_namespace(run)
            runtime.delete_worker_without_force(run)
            absent = runtime.wrangler(
                run,
                "archive-worker-absent",
                "deployments",
                "list",
                "--name",
                run.state["workerName"],
                "--json",
                allow_failure=True,
            )
            if not runtime.missing_worker(absent):
                raise ProbeError("Source Worker absence unconfirmed; archive refused.")
            run.state["workerDeleted"] = True
            target = new_run("cloudflare", "archive")
            run.state["restoreRunId"] = target.run_id
            run.save()
            create_database(target)
            for name, passed in coordination_backup.restore_probe(run, target).items():
                report.check(args.kind + ".archive_" + name, passed)
        report.check("evidence.source_unchanged", hashes() == run.state["sourceHashes"])
        report.data["completed"] = True
    except (ProbeError, OSError, ValueError, KeyError, http.client.HTTPException) as error:
        report.data.update(completed=False, failureType=type(error).__name__)
        print(
            str(error)
            if isinstance(error, ProbeError)
            else "Proof failed; private evidence retained.",
            file=sys.stderr,
        )
    finally:
        if process is not None:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.close()
            tail = process.stdout.read()
            process.wait(timeout=20)
            if error_log is not None:
                error_log.close()
            report.data["localExitCode"] = process.returncode
            report.data["cleanupConfirmed"] = process.returncode == 0
            if tail.strip():
                report.data["localRuntime"] = json.loads(tail.strip().splitlines()[-1])
                clean_network = report.data["localRuntime"].get("outboundCalls") == 0
                report.data["cases"].append(
                    {"id": "network.no_external_calls", "passed": clean_network}
                )
                if not clean_network:
                    report.data["completed"] = False
        elif args.environment == "hosted":
            try:
                cleanup(run)
            except (ProbeError, OSError) as error:
                print("Cleanup not confirmed: " + str(error), file=sys.stderr)
            report.data["cleanupConfirmed"] = run.state.get("cleanupConfirmed", False)
        report.data["controlRetries"] = run.state.get("controlRetries", [])
        report.save()
    print("Coordination report: " + str(run.directory / "report.json"), flush=True)
    return 0 if report.data.get("completed") and report.data.get("cleanupConfirmed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
