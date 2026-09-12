"""Disposable hosted intake/admin integration with real native secret writes, fake Flickr only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime, lua_type

try:
    from . import coordination_probe as coordination
    from . import runtime_permissions_probe as runtime
    from .native_secret_probe import deploy_with_bearer
    from .secret_store_probe import private_process
except ImportError:
    import coordination_probe as coordination
    import runtime_permissions_probe as runtime
    from native_secret_probe import deploy_with_bearer
    from secret_store_probe import private_process
ROOT = runtime.ROOT


class API:
    def __init__(self, run):
        self.run = run
        value = private_process([runtime.NODE, str(runtime.WRANGLER), "auth", "token", "--json"])
        if value.returncode:
            raise runtime.ProbeError("Operator credentials unavailable")
        self.token = json.loads(value.stdout)["token"]

    def call(self, method, suffix, body=None):
        coordination.validate(self.run)
        if not re.fullmatch(
            r"stores(?:/[a-f0-9]{32}(?:/secrets(?:/[a-f0-9]{32})?)?)?(?:\?page=\d+&per_page=100)?",
            suffix,
        ):
            raise runtime.ProbeError("Native API scope mismatch")
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{self.run.state['accountId']}/secrets_store/{suffix}",
            method=method,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            data=None if body is None else json.dumps(body).encode(),
        )
        try:
            reply = urllib.request.build_opener(runtime.NoRedirect).open(req, timeout=25)
        except urllib.error.HTTPError as error:
            reply = error
        with reply:
            value = json.loads(reply.read(1048576))
            status = reply.status
        if not value.get("success") and status != 404:
            raise runtime.ProbeError(f"Native {method} failed: HTTP {status}")
        return value.get("result")

    def rows(self, path):
        result = []
        for page in range(1, 11):
            rows = self.call("GET", f"{path}?page={page}&per_page=100") or []
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise runtime.ProbeError("Native inventory pagination exceeded")


def cleanup(run):
    coordination.validate(run)
    coordination.cleanup(run)
    api = API(run)
    if not run.state.get("storeId") and run.state.get("storeAttempted"):
        rows = [r for r in api.rows("stores") if r["name"] == run.state["workerName"]]
        if len(rows) > 1:
            raise runtime.ProbeError("Ambiguous owned store")
        if rows:
            run.state["storeId"] = rows[0]["id"]
            run.save()
    if run.state.get("storeId"):
        base = "stores/" + run.state["storeId"]
        for row in api.rows(base + "/secrets"):
            if row["name"] in run.state.get("secretNames", []):
                expected = run.state.get("secretIds", {}).get(row["name"])
                if expected and expected != row["id"]:
                    raise runtime.ProbeError("Secret cleanup identity changed")
                api.call("DELETE", base + "/secrets/" + row["id"])
        if any(
            row["name"] in run.state.get("secretNames", []) for row in api.rows(base + "/secrets")
        ):
            raise runtime.ProbeError("Native secret cleanup unconfirmed")
        if run.state.get("storeOwned"):
            if api.rows(base + "/secrets"):
                raise runtime.ProbeError("Owned store is not empty")
            api.call("DELETE", base)
            if any(row["id"] == run.state["storeId"] for row in api.rows("stores")):
                raise runtime.ProbeError("Store cleanup unconfirmed")
    run.state["nativeCleanupConfirmed"] = True
    run.save()


class Client:
    def __init__(self, run, token):
        self.run = run
        self.token = token

    def call(self, path, body=None, headers=None, method=None) -> tuple[int, Any, dict[str, str]]:
        req = urllib.request.Request(
            self.run.state["url"] + path,
            method=method or ("POST" if body is not None else "GET"),
            headers={
                "X-FGA-Proof": self.token,
                "User-Agent": "FlickrGroupAddr-IntegrationProof/0.0.0",
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if body is not None else {}),
                **(headers or {}),
            },
            data=None
            if body is None
            else body
            if isinstance(body, bytes)
            else json.dumps(body).encode(),
        )
        try:
            reply = urllib.request.build_opener(runtime.NoRedirect).open(req, timeout=45)
        except urllib.error.HTTPError as error:
            reply = error
        with reply:
            raw = reply.read(2097152)
            status = reply.status
            head = dict(reply.headers)
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw.decode("utf-8", errors="replace")
        if not isinstance(status, int):
            raise runtime.ProbeError("HTTP status unavailable")
        return status, value, head

    def control(self, name, body=None):
        status, value, _ = self.call("/probe/" + name, {} if body is None else body)
        if status != 200 or value.get("build") != self.run.run_id:
            raise runtime.ProbeError("Control failed: " + name)
        return value["result"]


def provision(run, token, keys):
    cfg = json.loads(
        (ROOT / ".coordination-runs/fga-runtime-inputs.json").read_text(encoding="utf-8")
    )
    identity = json.loads(runtime.wrangler(run, "identity", "whoami", "--json").stdout)
    if not any(
        a["id"] == cfg.get("accountId") and "sixbuckssolutions.com" in a.get("name", "").lower()
        for a in identity.get("accounts", [])
    ):
        raise runtime.ProbeError("Approved business account not active")
    run.state["accountId"] = cfg["accountId"]
    run.save()
    api = API(run)
    stores = api.rows("stores")
    if len(stores) > 1:
        raise runtime.ProbeError("Ambiguous native store")
    if stores:
        run.state.update(storeId=stores[0]["id"], storeOwned=False)
    else:
        run.state.update(storeAttempted=True, storeOwned=True)
        run.save()
        run.state["storeId"] = api.call("POST", "stores", {"name": run.state["workerName"]})["id"]
    run.save()
    base = "stores/" + run.state["storeId"]
    raw = Path(cfg["writerTokenFile"]).read_text(encoding="utf-8-sig")
    candidates = re.findall(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{35,256}(?![A-Za-z0-9_-])", raw)
    if len(candidates) != 1:
        raise runtime.ProbeError("Expected one runtime writer token")
    values = {
        "FLICKR_APPLICATION": json.dumps(
            {
                "schemaVersion": 1,
                "consumerKey": "synthetic-app-key",
                "consumerSecret": "synthetic-app-secret",
            }
        ),
        "FLICKR_GRANT": json.dumps(
            {
                "schemaVersion": 1,
                "generation": "generation-a",
                "token": "synthetic-token",
                "tokenSecret": "synthetic-token-secret",
            }
        ),
        "AUTH_LIMITER_KEY": secrets.token_hex(32),
        "NATIVE_WRITER_TOKEN": candidates[0],
        **{
            f"FLICKR_TEMP_{i}": json.dumps(
                {"schemaVersion": 1, "generation": "initial-" + str(i), "retired": True}
            )
            for i in range(5)
        },
    }
    names = {
        binding: run.state["workerName"] + "-" + binding.lower().replace("_", "-")
        for binding in values
    }
    if any(row["name"] in names.values() for row in api.rows(base + "/secrets")):
        raise runtime.ProbeError("Generated secret name already existed")
    run.state["secretNames"] = list(names.values())
    run.save()
    created = api.call(
        "POST",
        base + "/secrets",
        [
            {
                "name": names[b],
                "value": value,
                "scopes": ["workers"],
                "comment": "Disposable FGA integration fixture",
            }
            for b, value in values.items()
        ],
    )
    run.state["secretIds"] = {row["name"]: row["id"] for row in created}
    run.save()
    values.clear()
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
        raise runtime.ProbeError("Generated Worker already existed")
    if any(
        row["name"] == run.state["databaseName"]
        for row in runtime.databases(run, "database-preflight")
    ):
        raise runtime.ProbeError("Generated D1 already existed")
    run.state["databaseAttempted"] = True
    run.save()
    runtime.wrangler(
        run, "database-create", "d1", "create", run.state["databaseName"], "--update-config=false"
    )
    found = [
        r
        for r in runtime.databases(run, "database-created")
        if r["name"] == run.state["databaseName"]
    ]
    if len(found) != 1:
        raise runtime.ProbeError("D1 identity unavailable")
    run.state["databaseId"] = found[0]["uuid"]
    run.save()
    config = {
        "name": run.state["workerName"],
        "account_id": run.state["accountId"],
        "main": str(ROOT / "probes/intake/hosted_worker.ts"),
        "compatibility_date": "2026-09-11",
        "compatibility_flags": ["nodejs_compat", "global_fetch_strictly_public"],
        "workers_dev": True,
        "preview_urls": False,
        "observability": {"enabled": False},
        "vars": {
            "PROOF_BUILD": run.run_id,
            "PROOF_EXPIRES": str(int((time.time() + 1800) * 1000)),
            "PROOF_GOOGLE_KEYS": json.dumps({"keys": [keys["publicKey"]]}),
            "FGA_ADMIN_ENABLED": "1",
            "FGA_INTAKE_ENABLED": "1",
            "FGA_READ_ENABLED": "1",
            "FGA_MAX_GROUP_IDS_PER_BATCH": "60",
            "GOOGLE_CLIENT_ID": "synthetic-client",
            "GOOGLE_OWNER_SUB": "synthetic-sub",
            "CF_ACCOUNT_ID": run.state["accountId"],
            "CF_SECRET_STORE_ID": run.state["storeId"],
            "CF_GRANT_SLOT_ID": run.state["secretIds"][names["FLICKR_GRANT"]],
            "CF_OAUTH_SLOT_IDS": json.dumps(
                [run.state["secretIds"][names[f"FLICKR_TEMP_{i}"]] for i in range(5)]
            ),
        },
        "d1_databases": [
            {
                "binding": "DB",
                "database_name": run.state["databaseName"],
                "database_id": run.state["databaseId"],
                "migrations_dir": str(ROOT / "migrations"),
            }
        ],
        "durable_objects": {"bindings": [{"name": "COORD", "class_name": "ProbePartitionWake"}]},
        "exports": {"ProbePartitionWake": {"type": "durable-object", "storage": "sqlite"}},
        "secrets_store_secrets": [
            {"binding": b, "store_id": run.state["storeId"], "secret_name": n}
            for b, n in names.items()
        ],
        "assets": {
            "directory": str(ROOT / "assets"),
            "binding": "ASSETS",
            "run_worker_first": True,
        },
    }
    path = run.directory / "wrangler.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    schema = run.directory / "schema.sql"
    schema.write_text(
        "\n".join(
            p.read_text(encoding="utf-8") for p in sorted((ROOT / "migrations").glob("*.sql"))
        )
        + "\n"
        + (ROOT / "probes/intake/schema.sql").read_text(encoding="utf-8")
        + "\nCREATE TABLE intake_proof_budget(id INTEGER PRIMARY KEY,used INTEGER);\n"
        "INSERT INTO intake_proof_budget VALUES(1,0);\n"
        "CREATE TABLE intake_proof_events(kind TEXT,status INTEGER);\n",
        encoding="utf-8",
    )
    runtime.wrangler(
        run,
        "schema",
        "d1",
        "execute",
        "DB",
        "--remote",
        "--config",
        str(path),
        "--file",
        str(schema),
        "--yes",
        "--json",
    )
    runtime.command(
        run, "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
    )
    runtime.wrangler(
        run,
        "bundle",
        "deploy",
        "--dry-run",
        "--minify",
        "--config",
        str(path),
        "--outdir",
        str(run.directory / "bundle"),
    )
    bundle = run.directory / "bundle/hosted_worker.js"
    run.state["bundleSha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    config.update(main=str(bundle), no_bundle=True, find_additional_modules=False)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    run.state["workerAttempted"] = True
    run.save()
    output = deploy_with_bearer(run, path, token)
    urls = re.findall(
        r"https://" + re.escape(run.state["workerName"]) + r"\.[a-z0-9-]+\.workers\.dev", output
    )
    if not urls:
        raise runtime.ProbeError("Hosted URL unavailable")
    run.state["url"] = urls[-1]
    run.save()


def collect(run, token, keys, admin_only=False):
    client = Client(run, token)
    report = coordination.Report(run)
    start = time.monotonic()
    deadline = start + 180
    consecutive = 0
    print("Waiting for stable hosted binding readiness", flush=True)
    while time.monotonic() < deadline:
        try:
            status, value, _ = client.call("/proof/ready")
            if (
                status == 403
                and isinstance(value, str)
                and re.fullmatch(r"error code: [0-9]+\s*", value)
            ):
                raise runtime.ProbeError("Readiness rejected before Worker: " + value.strip())
            ok = (
                status == 200
                and isinstance(value, dict)
                and value.get("ready")
                and value.get("build") == run.run_id
            )
        except OSError:
            ok = False
        consecutive = consecutive + 1 if ok else 0
        if consecutive >= 3 and time.monotonic() - start >= 30:
            break
        time.sleep(5)
    else:
        raise runtime.ProbeError("Readiness did not converge")
    report.check("hosted_native_binding_readiness", True)
    status, _, _ = client.call("/api/v001/group-submission-batches", {})
    report.check("batch_missing_authentication", status == 401)
    client.control("seed")
    bearer = {"Authorization": "Bearer " + "0000-" * 12 + "0000"}
    serial = 0

    def observe_native(field):
        matched = 0
        for _ in range(60):
            status, value, _ = client.call("/proof/observation")
            matched = matched + 1 if status == 200 and value.get(field) else 0
            if matched >= 3:
                return
            time.sleep(2)
        raise runtime.ProbeError("Native observation did not converge: " + field)

    def fresh(groups):
        nonlocal serial
        serial += 1
        status, proof, _ = client.call(
            "/api/v001/existing-public-photo-bindings",
            {
                "schemaVersion": 1,
                "flickrPhotoId": "hosted-photo-" + str(serial),
                "expectedLinkedFlickrRevision": 1,
            },
            bearer,
        )
        if status != 201:
            raise runtime.ProbeError("Fresh binding failed")
        return {
            "schemaVersion": 2,
            "photoBinding": {
                "fgaPhotoBindingId": proof["fgaPhotoBindingId"],
                "expectedVerificationRevision": proof["verificationRevision"],
            },
            "flickrGroupIds": groups,
        }

    def batch(value):
        return client.call("/api/v001/group-submission-batches", value, bearer)

    def state():
        return client.control("state")

    if not admin_only:
        selection = fresh(["lua-c", "lua-a", "lua-b"])
        lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        adapter = lua.execute(
            (ROOT / "clients/lightroom/GroupSubmissionClient.lua").read_text(encoding="utf-8")
        )
        calls = []

        def plain(value: Any) -> Any:
            if lua_type(value) != "table":
                return value
            keys = list(value.keys())
            if keys and set(keys) == set(range(1, len(keys) + 1)):
                return [plain(value[i]) for i in keys]
            return {key: plain(value[key]) for key in keys}

        def post(path, body, fields):
            calls.append(json.loads(body))
            headers = {row["field"]: row["value"] for row in plain(fields)}
            status, value, _ = client.call(path, body.encode(), headers)
            return json.dumps(value), status

        outcome = adapter.submit(
            selection["photoBinding"]["fgaPhotoBindingId"],
            selection["photoBinding"]["expectedVerificationRevision"],
            lua.table_from(selection["flickrGroupIds"]),
            "0000-" * 12 + "0000",
            post,
            lambda value: json.dumps(plain(value)),
        )
        report.check(
            "CBA-CLIENT-001",
            outcome[1] == 202
            and len(calls) == 1
            and calls[0]["flickrGroupIds"] == selection["flickrGroupIds"],
        )
        for ident, groups in [
            ("CBA-ROUTE-001", ["one"]),
            ("CBA-ROUTE-002", ["many-c", "many-a", "many-b"]),
        ]:
            value = fresh(groups)
            status, result, _ = batch(value)
            report.check(
                ident,
                status == 202 and [r["flickrGroupId"] for r in result["submissions"]] == groups,
            )
        status, _, _ = client.call("/api/v001/group-submission", {}, bearer)
        report.check("CBA-ROUTE-003", status == 404)
        value = fresh(["future"])
        client.control("control", {"futureClass": 1})
        before = state()
        status, _, _ = batch(value)
        report.check("CBA-ROUTE-004", status == 401 and state() == before)
        client.control("control")
        value = fresh(["valid"])
        before = state()
        valid = True
        for groups in [
            [],
            ["duplicate", "duplicate"],
            ["valid", "bad group"],
            list(map(lambda i: "g" + str(i), range(61))),
        ]:
            valid = valid and batch({**value, "flickrGroupIds": groups})[0] == 400
        report.check("CBA-VALID-001", valid and state() == before)
        value = fresh(["limit-" + str(i) for i in range(60)])
        client.control("control", {"limit": "61"})
        status, _, _ = batch(value)
        client.control("control")
        report.check("CBA-VALID-002", status == 503 and batch(value)[0] == 202)
        value = fresh(["txn-a", "txn-b"])
        status, result, _ = batch(value)
        report.check(
            "CBA-TXN-001", status == 202 and all(r["created"] for r in result["submissions"])
        )
        status, result, _ = batch({**value, "flickrGroupIds": ["txn-b", "txn-c", "txn-a"]})
        report.check(
            "CBA-TXN-002",
            status == 202 and [r["created"] for r in result["submissions"]] == [False, True, False],
        )
        value = fresh(["rollback"])
        rolled = True
        for fault in range(7):
            client.control("control", {"fault": fault})
            before = state()
            rolled = rolled and batch(value)[0] == 503 and state() == before
        client.control("control")
        report.check("CBA-TXN-003", rolled)
        value = fresh(["overlap-a", "overlap-b"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(batch, [value, {**value, "flickrGroupIds": ["overlap-b", "overlap-c"]}])
            )
        rows = [
            r
            for r in state()["submission_intents"]
            if r["binding_id"] == value["photoBinding"]["fgaPhotoBindingId"]
        ]
        report.check("CBA-TXN-004", all(r[0] == 202 for r in results) and len(rows) == 3)
        value = fresh(["no-flickr"])
        before = len(state()["intake_probe_calls"])
        batch(value)
        report.check("CBA-TXN-005", len(state()["intake_probe_calls"]) == before)
        value = fresh(["canonical-z", "canonical-a", "canonical-b"])
        before = len(state()["intake_probe_hints"])
        batch(value)
        snapshot = state()
        hints = snapshot["intake_probe_hints"][before:]
        report.check(
            "CBA-HINT-001",
            len(hints) == 1
            and next(
                p
                for p in snapshot["group_partitions"]
                if p["partition_id"] == hints[0]["partition_id"]
            )["group_id"]
            == "canonical-a",
        )
        value = fresh(["behind"])
        batch(value)
        other = fresh(["behind"])
        before = len(state()["intake_probe_hints"])
        batch(other)
        report.check("CBA-HINT-002", len(state()["intake_probe_hints"]) == before)
        value = fresh(["retry"])
        batch(value)
        before = state()
        status, result, _ = batch(value)
        report.check(
            "CBA-HINT-003",
            status == 202 and not result["submissions"][0]["created"] and state() == before,
        )
        value = fresh(["mixed-old"])
        batch(value)
        before = len(state()["intake_probe_hints"])
        batch({**value, "flickrGroupIds": ["mixed-old", "mixed-z", "mixed-a"]})
        snapshot = state()
        hints = snapshot["intake_probe_hints"][before:]
        report.check(
            "CBA-HINT-004",
            len(hints) == 1
            and next(
                p
                for p in snapshot["group_partitions"]
                if p["partition_id"] == hints[0]["partition_id"]
            )["group_id"]
            == "mixed-a",
        )
        client.control("sweep")
        client.control("sweep")
        value = fresh(["lost-a", "lost-b"])
        client.control("control", {"loseHint": 1})
        batch(value)
        client.control("control")
        client.control("sweep")
        snapshot = state()
        ids = [
            r["partition_id"]
            for r in snapshot["submission_intents"]
            if r["binding_id"] == value["photoBinding"]["fgaPhotoBindingId"]
        ]
        report.check(
            "CBA-HINT-005",
            all(
                next(p for p in snapshot["group_partitions"] if p["partition_id"] == i)["lease_id"]
                for i in ids
            ),
        )
        value = fresh(["duplicate-hint"])
        batch(value)
        before = next(p for p in state()["group_partitions"] if p["group_id"] == "duplicate-hint")[
            "lease_generation"
        ]
        client.call("/proof/duplicate-hint", {"group": "duplicate-hint"})
        after = next(p for p in state()["group_partitions"] if p["group_id"] == "duplicate-hint")[
            "lease_generation"
        ]
        report.check("CBA-HINT-006", before == after)
    # Real compiled Google verifier, synthetic signed assertion, no Google account traffic.
    status, page, _ = client.call("/admin/login")
    report.check("admin_login_page", status == 200)
    nonce_match = re.search(r'data-nonce="([^"]+)"', page)
    state_match = re.search(r'data-state="([^"]+)"', page)
    if not nonce_match or not state_match:
        raise runtime.ProbeError("Google login transaction markup missing")
    nonce = nonce_match[1]
    oauth_state = state_match[1]
    signed = private_process(
        [runtime.NODE, str(ROOT / "scripts/proof_google_identity.mjs")],
        json.dumps({"action": "sign", "privateKey": keys["privateKey"], "nonce": nonce}),
    ).stdout
    status, login_result, headers = client.call(
        "/admin/google-login",
        urllib.parse.urlencode(
            {"credential": signed, "state": oauth_state, "g_csrf_token": "synthetic-csrf"}
        ).encode(),
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": "g_csrf_token=synthetic-csrf",
        },
    )
    code = (
        login_result.get("error", {}).get("code")
        if isinstance(login_result, dict)
        else login_result.strip()
        if isinstance(login_result, str) and re.fullmatch(r"error code: [0-9]+\s*", login_result)
        else "unclassified"
    )
    report.check(
        "admin_signed_login",
        status == 303,
        httpStatus=status,
        errorCode=code
        if code
        in {
            "invalid_google_assertion",
            "unauthorized",
            "service_unavailable",
            "rate_limited",
            "admission_unavailable",
            "error code: 1101",
            "error code: 1102",
            "error code: 1010",
        }
        else "unclassified",
    )
    cookie = next(v for k, v in headers.items() if k.lower() == "set-cookie").split(";")[0]
    admin = {"Cookie": cookie}
    status, session, _ = client.call("/api/v001/admin/session", headers=admin)
    report.check("admin_session_cookie", status == 200 and len(session["csrfToken"]) == 43)
    admin.update({"Origin": "https://flickrgroupaddr.com", "X-CSRF-Token": session["csrfToken"]})
    status, _, _ = client.call(
        "/api/v001/admin/flickr-connection/authorization",
        {"schemaVersion": 1, "expectedRevision": 1},
        {**admin, "Origin": "https://wrong.invalid"},
    )
    report.check("admin_origin_denied", status == 403)
    status, authorization, _ = client.call(
        "/api/v001/admin/flickr-connection/authorization",
        {"schemaVersion": 1, "expectedRevision": 1},
        admin,
    )
    diagnostic = client.call("/proof/admin-state")[1] if status != 201 else {}
    report.check("native_oauth_start", status == 201, httpStatus=status, diagnostic=diagnostic)
    observe_native("temporaryObserved")
    temporary = urllib.parse.parse_qs(
        urllib.parse.urlsplit(authorization["authorizationUrl"]).query
    )["oauth_token"][0]
    callback = "/admin/flickr-oauth/callback?" + urllib.parse.urlencode(
        {
            "state": temporary.removeprefix("temporary-"),
            "oauth_token": temporary,
            "oauth_verifier": "synthetic-verifier",
        }
    )
    status, _, _ = client.call(callback)
    report.check("native_oauth_callback", status == 303)
    observe_native("grantObserved")
    status, _, _ = client.call("/proof/maintenance", {})
    report.check("native_reconciliation_handler", status == 200)
    status, view, _ = client.call("/api/v001/admin/flickr-connection", headers=admin)
    report.check(
        "native_activation_keeps_writes_paused",
        status == 200 and view["state"] == "linked" and view["userWriteGate"]["state"] == "paused",
    )
    status, view, _ = client.call(
        "/api/v001/admin/flickr-connection/disconnection",
        {
            "schemaVersion": 1,
            "expectedRevision": view["revision"],
            "expectedFlickrOwnerNsid": "synthetic-owner",
        },
        admin,
    )
    report.check(
        "native_disconnect_stops_authority",
        status in (200, 202) and view["fgaOperationState"] == "stopped",
    )
    observe_native("grantObserved")
    client.call("/proof/maintenance", {})
    status, view, _ = client.call("/api/v001/admin/flickr-connection", headers=admin)
    report.check(
        "native_retirement_confirmed", status == 200 and view["localCredentialState"] == "retired"
    )
    status, _, _ = client.call("/api/v001/admin/session/logout", {}, admin)
    report.check(
        "admin_logout",
        status == 204
        and client.call("/api/v001/admin/session", headers={"Cookie": cookie})[0] == 401,
    )
    return report.data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "cleanup"])
    parser.add_argument("--run")
    parser.add_argument("--admin-only", action="store_true")
    args = parser.parse_args()
    if args.action == "cleanup":
        path = Path(args.run).resolve()
        run = runtime.Run(path, json.loads((path / "manifest.json").read_text(encoding="utf-8")))
        cleanup(run)
        return
    run = coordination.new_run("cloudflare", "intake")
    for source in [
        *ROOT.glob("probes/intake/*.*"),
        *ROOT.glob("assets/admin/*"),
        Path(__file__),
        ROOT / "scripts/proof_google_identity.mjs",
    ]:
        if source.is_file():
            run.state["sourceHashes"][source.relative_to(ROOT).as_posix()] = hashlib.sha256(
                source.read_bytes()
            ).hexdigest()
    run.save()
    token = secrets.token_urlsafe(32)
    print("Intake run: " + str(run.directory), flush=True)
    keys = json.loads(
        private_process(
            [runtime.NODE, str(ROOT / "scripts/proof_google_identity.mjs")], '{"action":"generate"}'
        ).stdout
    )
    report = None
    try:
        provision(run, token, keys)
        report = collect(run, token, keys, args.admin_only)
    finally:
        cleanup(run)
    if report is not None:
        report["bundleSha256"] = run.state.get("bundleSha256")
        report["cleanup"] = {
            "workerAndDatabase": run.state.get("cleanupConfirmed", False),
            "nativeSecrets": run.state.get("nativeCleanupConfirmed", False),
        }
        (run.directory / "report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    print("Intake report: " + str(run.directory / "report.json"), flush=True)


if __name__ == "__main__":
    main()
