"""Production artifact matrix through real API/transport/allocator boundaries.

Partial inventory remains release-blocking; this runner never infers missing passes.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
import queue
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit

from scripts import bootstrap_deployment as bootstrap
from scripts import coordination_probe as probe
from scripts import fail_polite_release as gate
from scripts import runtime_permissions_probe as runtime
from scripts.hosted_restore_proof import Proof
from scripts.matrix_native import NativeFixtures

ROOT = runtime.ROOT


@dataclass
class Case:
    user: str
    photo: str
    group: str
    binding: str
    code: str
    partition: str
    intent: str
    admin_token: str = ""
    csrf_token: str = ""
    binding_revision: int = 1
    session_id: str = ""


class Peer:
    def __init__(self, directory: Path):
        self.mode: dict[str, Any] = {}
        self.calls: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.barrier: threading.Barrier | None = None
        self.hold_add: dict[str, threading.Event] = {}
        self.oauth_callback = ""
        self.marker = lambda photo, group: False
        openssl = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
        self.cert = directory / "peer.crt"
        key = directory / "peer.key"
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-keyout",
                str(key),
                "-out",
                str(self.cert),
                "-subj",
                "/CN=127.0.0.1",
                "-addext",
                "subjectAltName=IP:127.0.0.1,DNS:localhost",
            ],
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        peer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args):
                pass

            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def respond(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                pairs = parse_qsl(urlsplit(self.path).query) + parse_qsl(body.decode())
                params = dict(pairs)
                oauth = dict(
                    (k, v)
                    for k, v in re.findall(
                        r'(oauth_[a-z_]+)="([^"]*)"', self.headers.get("Authorization", "")
                    )
                )
                from urllib.parse import unquote

                oauth = {k: unquote(v) for k, v in oauth.items()}
                actual = oauth.pop("oauth_signature", "")
                encoded = sorted(
                    (quote(k, safe="~"), quote(v, safe="~")) for k, v in [*pairs, *oauth.items()]
                )
                normalized = "&".join(k + "=" + v for k, v in encoded)
                base = "&".join(
                    quote(x, safe="~")
                    for x in (self.command, "https://www.flickr.com/services/rest/", normalized)
                )
                expected = base64.b64encode(
                    hmac.new(
                        b"matrix-secret&matrix-token-secret", base.encode(), hashlib.sha1
                    ).digest()
                ).decode()
                endpoint = urlsplit(self.path).path
                if endpoint.startswith("/services/oauth/"):
                    self.peer_endpoint = endpoint
                    token_secret = (
                        "" if endpoint.endswith("request_token") else "matrix-request-secret"
                    )
                    oauth_base = "&".join(
                        quote(x, safe="~")
                        for x in (self.command, "https://www.flickr.com" + endpoint, normalized)
                    )
                    expected = base64.b64encode(
                        hmac.new(
                            ("matrix-secret&" + token_secret).encode(),
                            oauth_base.encode(),
                            hashlib.sha1,
                        ).digest()
                    ).decode()
                    if endpoint.endswith("request_token"):
                        peer.oauth_callback = oauth.get("oauth_callback", "")
                method, photo, group = (
                    params.get("method"),
                    params.get("photo_id"),
                    params.get("group_id"),
                )
                with peer.lock:
                    peer.calls.append(
                        {
                            "method": method,
                            "photo": photo,
                            "group": group,
                            "signatureValid": hmac.compare_digest(actual, expected),
                            "sequence": len(peer.calls),
                            "receivedUs": time.monotonic_ns() // 1000,
                        }
                    )
                    entry = peer.calls[-1]
                status = 200
                mode = peer.mode
                if endpoint.endswith("/request_token"):
                    value = (
                        "oauth_token=matrix-request&oauth_token_secret=matrix-"
                        "request-secret&oauth_callback_confirmed=true"
                    )
                    content_type = "application/x-www-form-urlencoded"
                    entry["method"] = "oauth.request_token"
                elif endpoint.endswith("/access_token"):
                    value = "oauth_token=matrix-token&oauth_token_secret=matrix-token-secret"
                    content_type = "application/x-www-form-urlencoded"
                    entry["method"] = "oauth.access_token"
                elif method == "flickr.auth.oauth.checkToken":
                    value = {
                        "stat": "ok",
                        "oauth": {
                            "token": {"_content": "matrix-token"},
                            "perms": {"_content": "write"},
                            "user": {"nsid": "matrix-owner"},
                        },
                    }
                    content_type = "application/json"
                elif method == "flickr.photos.getInfo":
                    value = {
                        "stat": "ok",
                        "photo": {
                            "id": photo,
                            "owner": {"nsid": "matrix-owner"},
                            "visibility": {"ispublic": 1},
                            "media": "photo",
                        },
                    }
                    content_type = "application/json"
                elif method == "flickr.photos.getAllContexts":
                    value = mode.get("membership", {"stat": "ok", "pool": []})
                    content_type = mode.get("membershipType", "application/json")
                elif method == "flickr.groups.getInfo":
                    value = mode.get(
                        "preflight", {"stat": "ok", "group": {"id": group, "ispoolmoderated": "0"}}
                    )
                    content_type = mode.get("preflightType", "application/json")
                elif method == "flickr.groups.pools.add":
                    marker = peer.marker(photo, group)
                    with peer.lock:
                        entry["markerVisible"] = marker
                    if group in peer.hold_add:
                        peer.hold_add[group].wait(timeout=180)
                    value = mode.get("add", {"stat": "fail", "code": 6})
                    content_type = mode.get("addType", "application/json")
                else:
                    status, value, content_type = 400, {"stat": "fail"}, "application/json"
                phase = (
                    "membership"
                    if method == "flickr.photos.getAllContexts"
                    else "preflight"
                    if method == "flickr.groups.getInfo"
                    else "add"
                )
                if phase == "preflight" and peer.barrier:
                    peer.barrier.wait(timeout=10)
                if mode.get(phase + "Drop"):
                    self.close_connection = True
                    return
                status = mode.get(phase + "Status", status)
                raw = (
                    value
                    if isinstance(value, bytes)
                    else value.encode()
                    if isinstance(value, str)
                    else json.dumps(value).encode()
                )
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except BrokenPipeError, ConnectionResetError:
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class SelectedCaseComplete(Exception):
    """The requested positive control reached its assertion."""


class Matrix:
    def __init__(self, environment: str, native: bool = False):
        self.proof = Proof() if environment == "hosted-db" else None
        # Isolated mutation source copies can otherwise exceed Windows path limits
        # inside native storage. State stays in the enclosing private run root.
        parent = Path(
            os.environ.get("FGA_MATRIX_RUN_PARENT", ROOT / ".coordination-runs")
        ).resolve()
        if parent.name != ".coordination-runs" or not ROOT.resolve().is_relative_to(parent.parent):
            raise ValueError("matrix_run_parent_outside_private_workspace")
        self.directory = (
            self.proof.directory if self.proof else parent / ("matrix-" + secrets.token_hex(12))
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        self.native_bridge = NativeFixtures(self.proof) if native and self.proof else None
        if native and not self.proof:
            raise ValueError("native_matrix_requires_hosted_database")
        self.token = secrets.token_urlsafe(32)
        self.peer = Peer(self.directory)
        self.process: subprocess.Popen[str] | None = None
        self.log = (self.directory / "runtime.private.log").open("w", encoding="utf-8")
        self.counter = 0
        self.records: list[dict[str, Any]] = []
        self.environment = environment
        self.stop_after: str | None = None
        self.url = ""

    def start(self):
        config = self.directory / "production-wrangler.json"
        bootstrap.save(
            config,
            {
                "name": "fga-matrix",
                "main": str(ROOT / "src/worker.ts"),
                "compatibility_date": "2026-09-11",
                "compatibility_flags": ["nodejs_compat"],
                "workers_dev": False,
            },
        )
        run = runtime.Run(self.directory, {})
        runtime.command(
            run,
            "typescript",
            [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"],
        )
        runtime.wrangler(
            run,
            "artifact",
            "deploy",
            "--dry-run",
            "--minify",
            "--config",
            str(config),
            "--outdir",
            str(self.directory / "bundle"),
        )
        self.artifact = self.directory / "bundle/worker.js"
        settings: dict[str, Any] = {
            "directory": str(self.directory),
            "assetDirectory": str(ROOT / "assets"),
            "artifact": str(self.artifact),
            "driver": str(ROOT / "probes/release/matrix-driver.mjs"),
            "certificate": str(self.peer.cert),
            "peerPort": self.peer.server.server_port,
            "remote": self.proof is not None,
            "resume": False,
            "bindings": {
                "FGA_DISPATCH_ENABLED": "1",
                "FGA_ADMIN_ENABLED": "0",
                "FGA_READ_ENABLED": "1",
                "FGA_INTAKE_ENABLED": "1",
                "FGA_MAX_GROUP_IDS_PER_BATCH": "60",
                "CF_ACCOUNT_ID": "a" * 32,
                "CF_SECRET_STORE_ID": "b" * 32,
                "CF_GRANT_SLOT_ID": "c" * 31 + "0",
                "CF_OAUTH_SLOT_IDS": json.dumps(["c" * 31 + str(i) for i in range(1, 6)]),
                "FGA_ARTIFACT_SHA2_256": gate.digest(self.artifact),
            },
            "migrations": [
                probe.statements(p.read_text()) for p in sorted((ROOT / "migrations").glob("*.sql"))
            ],
        }
        environment = {
            **os.environ,
            "FGA_MATRIX_TOKEN": self.token,
            "CI": "true",
            "WRANGLER_SEND_METRICS": "false",
            "WRANGLER_WRITE_LOGS": "false",
        }
        if self.proof:
            database = self.proof.create("matrix")
            self.proof.migrate(database)
            remote = self.directory / "remote.json"
            bootstrap.save(
                remote,
                {
                    "name": self.proof.name,
                    "account_id": self.proof.operator.account_id,
                    "compatibility_date": "2026-09-11",
                    "d1_databases": [
                        {
                            "binding": "DB",
                            "database_id": database,
                            "database_name": self.proof.name + "-matrix",
                            "remote": True,
                        }
                    ],
                },
            )
            settings.update(wrangler=str(remote), databaseId=database)
            environment.update(
                CLOUDFLARE_API_TOKEN=self.proof.operator.operator,
                CLOUDFLARE_ACCOUNT_ID=self.proof.operator.account_id,
            )
        if self.native_bridge:
            self.native_bridge.prepare()
            native = self.native_bridge.configuration()
            remote_config = json.loads(Path(settings["wrangler"]).read_text())
            remote_config["services"] = native["services"]
            bootstrap.save(Path(settings["wrangler"]), remote_config)
            settings["native"] = native
            settings["bindings"].update(native["variables"])
            settings["bindings"]["MATRIX_NATIVE_PROXY"] = "1"
        # Freeze driver/runtime bytes across process restarts in this run.
        frozen_driver = self.directory / "driver-source.mjs"
        frozen_runtime = self.directory / "runtime-source.mjs"
        frozen_driver.write_bytes((ROOT / "probes/release/matrix-driver.mjs").read_bytes())
        frozen_runtime.write_bytes((ROOT / "probes/release/matrix-runtime.mjs").read_bytes())
        settings["driver"] = str(frozen_driver)
        self.runtime_source = frozen_runtime
        self.settings = settings
        self.child_environment = environment
        self.launch(resume=False)
        self.peer.marker = lambda photo, group: (
            self.sql(
                "SELECT COUNT(*) n FROM attempt_dispatches d JOIN submission_attempts a ON "
                "a.attempt_id=d.attempt_id JOIN submission_intents i ON "
                "i.intent_id=a.intent_id WHERE i.photo_id=? AND i.group_id=?",
                [photo, group],
            )[0]["n"]
            > 0
        )
        self.sql("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1)")

    def launch(self, *, resume: bool):
        path = self.directory / "matrix.json"
        bootstrap.save(path, {**self.settings, "resume": resume})
        self.process = subprocess.Popen(
            [runtime.NODE, str(self.runtime_source), str(path)],
            cwd=ROOT,
            env=self.child_environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )
        output = self.process.stdout
        assert output is not None
        lines: queue.Queue[str] = queue.Queue()

        def read_ready():
            for line in output:
                if line.startswith("MATRIX_READY "):
                    lines.put(line.removeprefix("MATRIX_READY "))
                    return
                self.log.write(line)
                self.log.flush()
            lines.put("")

        threading.Thread(target=read_ready, daemon=True).start()
        status = json.loads(lines.get(timeout=60))
        if status["pid"] != self.process.pid:
            raise RuntimeError("matrix_child_identity_mismatch")
        self.url = status["url"].rstrip("/")

    def stop_process(self, *, force: bool = False):
        if self.process is None or self.process.poll() is not None:
            return
        if not force:
            assert self.process.stdin is not None
            self.process.stdin.close()
            try:
                self.process.wait(timeout=30)
                return
            except subprocess.TimeoutExpired:
                pass
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            import signal

            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=15)

    def restart(self):
        old = self.process
        self.stop_process(force=True)
        self.launch(resume=True)
        return old is not None and old.poll() is not None and self.process is not None

    def request(
        self, path: str, value=None, code: str | None = None, method="POST"
    ) -> tuple[int, Any]:
        target = urlsplit(self.url)
        if target.hostname != "127.0.0.1":
            raise RuntimeError("matrix_control_must_use_loopback")
        connection = http.client.HTTPConnection(
            target.hostname,
            target.port,
            timeout=180 if isinstance(value, dict) and value.get("action") == "run" else 40,
        )
        try:
            body = None if value is None else json.dumps(value).encode()
            connection.request(
                method,
                path,
                body,
                {
                    "Authorization": "Bearer " + (code or self.token),
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
        finally:
            connection.close()

    def control(self, **value) -> Any:
        status, data = self.request("/__matrix", value)
        if status not in (200, 409):
            raise RuntimeError("matrix_control_unavailable")
        return data

    def sql(self, sql: str, params=None):
        result = self.control(action="sql", statements=[{"sql": sql, "params": params or []}])
        return result[0]["results"]

    def batch(self, statements):
        return self.control(
            action="sql", statements=[{"sql": sql, "params": params} for sql, params in statements]
        )

    def seed(self, label: str, *, admit_initial: bool = True) -> Case:
        self.counter += 1
        if self.native_bridge:
            self.native_bridge.reset_grant()
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if self.control(action="grant-ready")["ready"]:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("native_fixture_generation_not_observed")
        else:
            if not self.control(action="fixture-reset-grant")["reset"]:
                raise RuntimeError("local_grant_fixture_not_reset")
        uid = label.lower() + "-" + secrets.token_hex(4)
        photo = "p-" + uid
        group = "g-" + uid
        binding = "b-" + uid
        raw = f"{self.counter:012d}" + "0" * 40
        code = "-".join(raw[n : n + 4] for n in range(0, 52, 4))
        digest = hashlib.sha256(code.encode()).hexdigest()
        self.batch(
            [
                (
                    (
                        "UPDATE flickr_write_gates SET enabled=0,revision=revision+1 "
                        "WHERE scope='user' AND enabled=1"
                    ),
                    [],
                ),
                ("INSERT INTO fga_users VALUES(?)", [uid]),
                ("INSERT INTO flickr_links VALUES(?,'matrix-owner',1,'linked')", [uid]),
                (
                    "INSERT INTO "
                    "flickr_connection_state(user_id,state,local_state,verified_permission,"
                    "verified_at_us) VALUES(?,'linked','available','write',1)",
                    [uid],
                ),
                (
                    "INSERT INTO flickr_native_credentials "
                    "VALUES(?,'matrix-generation',1,'matrix-owner','write',NULL)",
                    [uid],
                ),
                ("INSERT INTO flickr_write_gates VALUES('user',?,1,1)", [uid]),
                (
                    "UPDATE flickr_write_gates SET enabled=1,revision=revision+1 WHERE "
                    "scope='deployment'",
                    [],
                ),
                ("UPDATE flickr_rate_window SET expires_at_us=0", []),
                (
                    "INSERT INTO "
                    "installations(installation_id,user_id,credential_class,state,revision,"
                    "current_version_id) VALUES(?,?,'lrc_plugin','active',1,?)",
                    [uid, uid, "v-" + uid],
                ),
                (
                    "INSERT INTO "
                    "installation_credential_versions(version_id,installation_id,"
                    "credential_digest,state,ordinal) VALUES(?,?,?,'current',1)",
                    ["v-" + uid, uid, digest],
                ),
                (
                    "INSERT INTO "
                    "photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,"
                    "verification_revision,source_kind) VALUES(?,?,?,'matrix-owner',1,1,'upload')",
                    [binding, uid, photo],
                ),
            ]
        )
        self.sql(
            "UPDATE installations SET label='Matrix fixture',rotation_due_at_utc="
            "strftime('%Y-%m-%dT%H:%M:%f',created_at_utc,'+1 year')||'000Z' "
            "WHERE installation_id=?",
            [uid],
        )
        if not admit_initial:
            return Case(uid, photo, group, binding, code, "", "")
        status, _ = self.request(
            "/api/v001/group-submission-batches",
            {
                "schemaVersion": 2,
                "photoBinding": {"fgaPhotoBindingId": binding, "expectedVerificationRevision": 1},
                "flickrGroupIds": [group],
            },
            code,
        )
        if status not in (200, 201, 202):
            raise RuntimeError("production_admission_failed_" + str(status))
        row = self.sql(
            "SELECT intent_id,partition_id FROM submission_intents WHERE photo_id=? AND group_id=?",
            [photo, group],
        )[0]
        return Case(uid, photo, group, binding, code, row["partition_id"], row["intent_id"])

    def admin(self, case: Case):
        if case.admin_token:
            return
        case.admin_token = secrets.token_urlsafe(32)
        case.csrf_token = secrets.token_urlsafe(32)
        case.session_id = "s-" + secrets.token_hex(16)
        now = self.sql(
            "SELECT CAST(strftime('%s','now') AS INTEGER)*1000000+"
            "CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000 now"
        )[0]["now"]
        statements = []
        if not self.sql("SELECT 1 FROM admin_principals WHERE user_id=?", [case.user]):
            statements.append(
                (
                    "INSERT INTO admin_principals VALUES(?,'https://accounts.google.com',?,1)",
                    [case.user, "sub-" + case.user],
                )
            )
        statements.append(
            (
                "INSERT INTO admin_sessions VALUES(?,?,?,?,?,?,?,?,NULL,NULL,1,?)",
                [
                    case.session_id,
                    hashlib.sha256(case.admin_token.encode()).hexdigest(),
                    case.user,
                    case.csrf_token,
                    now,
                    now,
                    now + 86400000000,
                    now,
                    "matrix-" + case.user,
                ],
            )
        )
        self.batch(statements)

    def api(self, case: Case, path: str, method: str = "GET", body: Any = None, extra=None):
        self.admin(case)
        headers = {
            "Cookie": "__Host-fga_admin=" + case.admin_token,
            "CF-Connecting-IP": "192.0.2." + str(self.counter % 250 + 1),
        }
        if method not in ("GET", "HEAD"):
            headers.update(
                Origin="https://flickrgroupaddr.com",
                **{"X-CSRF-Token": case.csrf_token, "Content-Type": "application/json"},
            )
        if extra:
            headers.update(extra)
        data = {
            "action": "api",
            "ownerSub": "sub-" + case.user,
            "path": path,
            "method": method,
            "headers": headers,
        }
        if body is not None:
            data["body"] = body
        return self.control(**data)

    def submit(self, case: Case, *, binding: str | None = None, **settings):
        return self.control(
            action="api",
            path="/api/v001/group-submission-batches",
            method="POST",
            ownerSub="sub-" + case.user,
            headers={"Authorization": "Bearer " + case.code, "Content-Type": "application/json"},
            body={
                "schemaVersion": 2,
                "photoBinding": {
                    "fgaPhotoBindingId": binding or case.binding,
                    "expectedVerificationRevision": case.binding_revision,
                },
                "flickrGroupIds": [case.group],
            },
            suppressHint=True,
            **settings,
        )

    def locate(self, case: Case):
        row = self.sql(
            "SELECT intent_id,partition_id FROM submission_intents WHERE photo_id=? AND group_id=?",
            [case.photo, case.group],
        )[0]
        case.intent, case.partition = row["intent_id"], row["partition_id"]

    def wait_terminal(self, case: Case, timeout: float = 30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.state(case)["state"]
            if state not in ("queued", "attempting", "retrying", "throttled"):
                return state
            time.sleep(0.1)
        raise RuntimeError("native_dispatch_did_not_settle")

    def wake(self, case: Case, revision: str | None = None, source: str = "admission"):
        if revision is None:
            revision = self.sql(
                (
                    "SELECT CAST(wake_revision AS TEXT) revision FROM "
                    "group_partitions WHERE partition_id=?"
                ),
                [case.partition],
            )[0]["revision"]
        return self.control(
            action="native-wake", partitionId=case.partition, revision=revision, source=source
        )

    def run(self, case: Case, **settings):
        return self.control(action="run", partitionId=case.partition, **settings)

    def state(self, case: Case):
        return self.sql(
            "SELECT state,active_fifo_member,add_dispatch_count FROM submission_intents "
            "WHERE intent_id=?",
            [case.intent],
        )[0]

    def check(self, case_id: str, condition: bool, **detail):
        condition = condition and all(call["signatureValid"] for call in self.peer.calls)
        self.records.append(
            {
                "id": case_id,
                "status": "passed" if condition else "failed",
                "skipped": False,
                **detail,
            }
        )
        bootstrap.save(
            self.directory / "matrix-report.json",
            {
                "scope": "partial-production-matrix",
                "fullConformancePassed": False,
                "environment": self.environment,
                "cases": self.records,
                "artifactSha2_256": gate.digest(self.artifact),
                "driverSha2_256": gate.digest(self.directory / "driver-source.mjs"),
                "runtimeAdapterSha2_256": gate.digest(self.runtime_source),
                "localCompatibilityDate": "2026-07-30",
                "nativeSecretsStore": self.native_bridge is not None,
            },
        )
        print(case_id + (": passed" if condition else ": FAILED"), flush=True)
        if not condition:
            raise RuntimeError("matrix_assertion_failed_" + case_id)
        if self.stop_after == case_id:
            raise SelectedCaseComplete()

    def close(self):
        try:
            self.stop_process()
        finally:
            for event in self.peer.hold_add.values():
                event.set()
            self.log.close()
            self.peer.close()
            try:
                if self.native_bridge:
                    self.native_bridge.cleanup()
            finally:
                if self.proof:
                    self.proof.cleanup()


def core_cases(matrix: Matrix) -> None:
    def trace(case):
        return [
            x for x in matrix.peer.calls if x["photo"] == case.photo or x["group"] == case.group
        ]

    def count(case, table):
        if table == "submission_blocks":
            return matrix.sql(
                "SELECT COUNT(*) n FROM submission_blocks WHERE photo_id=? AND group_id=?",
                [case.photo, case.group],
            )[0]["n"]
        return matrix.sql(
            "SELECT COUNT(*) n FROM "
            + table
            + " WHERE attempt_id IN (SELECT attempt_id FROM submission_attempts WHERE intent_id=?)",
            [case.intent],
        )[0]["n"]

    def execute(label, mode=None, **settings):
        case = matrix.seed(label)
        matrix.peer.calls = []
        matrix.peer.mode = mode or {}
        result = matrix.run(case, **settings)
        return case, result, matrix.state(case), trace(case)

    def no_post(case, calls):
        return (
            not any(x["method"] == "flickr.groups.pools.add" for x in calls)
            and count(case, "attempt_dispatches") == 0
        )

    def due(case):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            row = matrix.sql(
                (
                    "SELECT next_attempt_not_before_us<=CAST(strftime('%s','now')"
                    " AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) "
                    "AS INTEGER)*1000 due FROM submission_intents WHERE "
                    "intent_id=?"
                ),
                [case.intent],
            )[0]
            if row["due"]:
                return
            time.sleep(0.1)
        raise RuntimeError("retry_due_timeout")

    case, result, state, calls = execute("FP-MEM-001")
    matrix.check(
        "FP-MEM-001",
        state["state"] == "moderation_submitted"
        and [x["method"] for x in calls]
        == ["flickr.photos.getAllContexts", "flickr.groups.getInfo", "flickr.groups.pools.add"]
        and all(x["signatureValid"] for x in calls)
        and calls[-1]["markerVisible"],
    )

    for label in ("FP-MEM-002", "FP-MEM-007"):
        case = matrix.seed(label)
        matrix.peer.calls = []
        matrix.peer.mode = {
            "membership": {"stat": "ok", "pool": [{"id": case.group, "title": "Synthetic group"}]}
        }
        matrix.run(case)
        calls = trace(case)
        rates = matrix.sql(
            (
                "SELECT consumed_slots,released FROM flickr_rate_reservations"
                " WHERE attempt_id IN (SELECT attempt_id FROM "
                "submission_attempts WHERE intent_id=?)"
            ),
            [case.intent],
        )
        matrix.check(
            label,
            matrix.state(case)["state"] == "added"
            and len(calls) == 1
            and no_post(case, calls)
            and rates == [{"consumed_slots": 1, "released": 1}],
        )

    ok = True
    for mode in (
        {"membershipDrop": True},
        {"membership": {"stat": "fail", "code": 105}},
        {"membershipStatus": 503},
    ):
        case, _, state, calls = execute("FP-MEM-003", mode)
        ok = (
            ok
            and state["state"] == "retrying"
            and len(calls) == 1
            and no_post(case, calls)
            and count(case, "attempt_membership") == 0
        )
    matrix.check("FP-MEM-003", ok)

    ok = True
    bodies = [
        {},
        {"stat": "ok"},
        {"stat": "ok", "pool": None},
        {"stat": "ok", "pool": {}},
        {"stat": "ok", "pool": 3},
        {"stat": "ok", "pool": [None]},
        {"stat": "ok", "pool": [{"id": "same", "title": "t"}, {"id": "same", "title": "t"}]},
        {"stat": "ok", "pool": [{"id": "bad space", "title": "t"}]},
        {"stat": "ok", "pool": [{"id": "valid", "title": None}]},
        {"stat": "ok", "pool": [{"id": str(i), "title": "t"} for i in range(257)]},
        [],
        '{"stat":"ok",',
        b"\xff",
        '{"padding":"' + "x" * 600000 + '"}',
    ]
    for body in bodies:
        case, _, state, calls = execute("FP-MEM-004", {"membership": body})
        ok = (
            ok
            and state["state"] == "retrying"
            and len(calls) == 1
            and no_post(case, calls)
            and count(case, "attempt_membership") == 0
        )
    case, _, state, calls = execute("FP-MEM-004", {"membershipType": "text/plain"})
    matrix.check("FP-MEM-004", ok and state["state"] == "retrying" and no_post(case, calls))

    case, _, state, calls = execute("FP-MEM-005", {"add": {"stat": "fail", "code": 105}})
    due(case)
    matrix.peer.calls = []
    matrix.peer.mode = {
        "membership": {"stat": "ok", "pool": [{"id": case.group, "title": "now present"}]}
    }
    matrix.run(case)
    matrix.check(
        "FP-MEM-005",
        matrix.state(case)["state"] == "added"
        and len(trace(case)) == 1
        and count(case, "attempt_membership") == 2,
    )

    case = matrix.seed("FP-MEM-006")
    matrix.peer.calls = []
    matrix.peer.mode = {}
    matrix.sql(
        "UPDATE flickr_rate_window SET "
        "expires_at_us=CAST(strftime('%s','now') AS "
        "INTEGER)*1000000+60000000,reserved_slots=58"
    )
    matrix.run(case)
    matrix.check(
        "FP-MEM-006",
        not trace(case)
        and matrix.sql("SELECT reserved_slots FROM flickr_rate_window")[0]["reserved_slots"] == 58
        and count(case, "flickr_rate_reservations") == 0,
    )

    case, _, state, calls = execute("FP-MEM-008", {"add": {"stat": "fail", "code": 3}})
    matrix.check(
        "FP-MEM-008",
        state["state"] == "added" and len(calls) == 3 and count(case, "submission_blocks") == 0,
    )

    case, result, state, calls = execute("FP-PRE-001")
    matrix.check(
        "FP-PRE-001",
        state["state"] == "moderation_submitted"
        and calls[-2]["group"] == case.group
        and calls[-1]["markerVisible"]
        and count(case, "attempt_preflights") == 1
        and result.get("postMarkerAuthorityReads") == 0,
    )

    ok = True
    for mode in (
        {"preflightDrop": True},
        {"preflight": {"stat": "fail", "code": 105}},
        {"preflight": "malformed"},
        {"preflight": {"stat": "ok", "group": {}}},
        {"preflightType": "text/plain"},
    ):
        case, _, state, calls = execute("FP-PRE-002", mode)
        ok = ok and state["state"] == "retrying" and no_post(case, calls) and len(calls) == 2
    case = matrix.seed("FP-PRE-002-missing-field")
    matrix.peer.calls = []
    matrix.peer.mode = {"preflight": {"stat": "ok", "group": {"id": case.group}}}
    matrix.run(case)
    matrix.check(
        "FP-PRE-002",
        ok and matrix.state(case)["state"] == "retrying" and no_post(case, trace(case)),
    )

    case, _, _, _ = execute("FP-PRE-003", {"add": {"stat": "fail", "code": 105}})
    due(case)
    matrix.peer.calls = []
    matrix.peer.mode = {
        "preflight": {"stat": "ok", "group": {"id": case.group, "ispoolmoderated": "1"}}
    }
    matrix.run(case)
    observations = matrix.sql(
        (
            "SELECT moderated FROM attempt_preflights WHERE attempt_id IN"
            " (SELECT attempt_id FROM submission_attempts WHERE "
            "intent_id=?) ORDER BY observed_at_us"
        ),
        [case.intent],
    )
    matrix.check(
        "FP-PRE-003",
        matrix.state(case)["state"] == "moderation_submitted"
        and observations == [{"moderated": 0}, {"moderated": 1}]
        and len(trace(case)) == 3,
    )

    case, _, state, calls = execute("FP-PRE-004", intervene=True)
    ok = state["state"] == "retrying" and no_post(case, calls) and len(calls) == 2
    due(case)
    matrix.peer.calls = []
    matrix.peer.mode = {}
    matrix.run(case)
    matrix.check(
        "FP-PRE-004",
        ok and matrix.state(case)["state"] == "moderation_submitted" and len(trace(case)) == 3,
    )

    case, _, state, calls = execute("FP-PRE-006", scopeMismatch=True)
    matrix.check(
        "FP-PRE-006",
        state["state"] == "retrying"
        and len(calls) == 1
        and no_post(case, calls)
        and count(case, "attempt_membership") == 1,
    )

    first = matrix.seed("FP-PRE-005-a")
    second = matrix.seed("FP-PRE-005-b")
    matrix.sql(
        (
            "UPDATE flickr_write_gates SET enabled=1,revision=revision+1 "
            "WHERE scope='user' AND scope_id=?"
        ),
        [first.user],
    )
    matrix.peer.calls = []
    matrix.peer.mode = {}
    matrix.peer.barrier = threading.Barrier(2)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(matrix.run, [first, second]))
    finally:
        matrix.peer.barrier = None
    matrix.check(
        "FP-PRE-005",
        all(
            matrix.state(c)["state"] == "moderation_submitted"
            and [x["method"] for x in trace(c)]
            == ["flickr.photos.getAllContexts", "flickr.groups.getInfo", "flickr.groups.pools.add"]
            and trace(c)[-1]["markerVisible"]
            for c in [first, second]
        ),
    )

    case, _, state, calls = execute("FP-PRE-007", beforeAge=1000000)
    rates = matrix.sql(
        (
            "SELECT consumed_slots,released FROM flickr_rate_reservations"
            " WHERE attempt_id IN (SELECT attempt_id FROM "
            "submission_attempts WHERE intent_id=?)"
        ),
        [case.intent],
    )
    matrix.check(
        "FP-PRE-007", no_post(case, calls) and rates == [{"consumed_slots": 2, "released": 1}]
    )

    case, _, state, calls = execute("FP-PRE-008", beforeAge=999999, afterAge=999999)
    matrix.check(
        "FP-PRE-008", state["state"] == "moderation_submitted" and calls[-1]["markerVisible"]
    )
    ok = True
    for age in (1000000, 1000001):
        case, _, state, calls = execute("FP-PRE-009", beforeAge=age)
        ok = ok and state["state"] == "retrying" and no_post(case, calls)
    matrix.check("FP-PRE-009", ok)
    case, _, state, calls = execute("FP-PRE-010", beforeAge=999999, afterAge=1000000)
    reason = matrix.sql(
        (
            "SELECT reason FROM attempt_resolutions WHERE attempt_id IN "
            "(SELECT attempt_id FROM submission_attempts WHERE "
            "intent_id=?)"
        ),
        [case.intent],
    )[0]["reason"]
    matrix.check(
        "FP-PRE-010",
        state["state"] == "retrying"
        and state["add_dispatch_count"] == 0
        and reason == "not_dispatched_preflight_expired"
        and not any(x["method"] == "flickr.groups.pools.add" for x in calls)
        and count(case, "submission_blocks") == 0,
    )
    ok = True
    for age in (-1, "NaN", "Infinity"):
        case, _, state, calls = execute("FP-PRE-011", beforeAge=age)
        ok = ok and state["state"] == "retrying" and no_post(case, calls)
    matrix.check("FP-PRE-011", ok)
    case, _, state, calls = execute("FP-PRE-012", gateChange="preflight_committed")
    matrix.check("FP-PRE-012", no_post(case, calls) and state["state"] == "attempting")

    for label, code in (
        ("FP-RES-001", 6),
        ("FP-RES-002", 7),
        ("FP-RES-003", 6),
        ("FP-RES-004", 9999),
    ):
        case, _, state, calls = execute(label, {"add": {"stat": "fail", "code": code}})
        expected = "delivery_uncertain" if code == 9999 else "moderation_submitted"
        ok = (
            state["state"] == expected
            and count(case, "submission_blocks") == 1
            and count(case, "attempt_resolutions") == 1
            and calls[-1]["markerVisible"]
        )
        if label == "FP-RES-003":
            ok = ok and bool(
                matrix.sql(
                    (
                        "SELECT 1 FROM submission_intent_events WHERE intent_id=? AND"
                        " kind='moderation_changed_or_inconsistent'"
                    ),
                    [case.intent],
                )
            )
        matrix.check(label, ok)

    ok = True
    for mode in (
        {"add": "truncated"},
        {"add": b"\xff"},
        {"addType": "text/plain"},
        {"add": {}},
        {"add": {"stat": "ok", "padding": "x" * 300000}},
    ):
        case, _, state, calls = execute("FP-RES-005", mode)
        ok = (
            ok
            and state["state"] == "delivery_uncertain"
            and count(case, "submission_blocks") == 1
            and len(calls) == 3
        )
    matrix.check("FP-RES-005", ok)
    case, _, state, calls = execute("FP-RES-006", {"addDrop": True})
    matrix.check(
        "FP-RES-006",
        state["state"] == "delivery_uncertain"
        and count(case, "submission_blocks") == 1
        and len(calls) == 3,
    )

    ok = True
    for code in (105, 106):
        case, _, state, calls = execute("FP-RES-007", {"add": {"stat": "fail", "code": code}})
        ok = ok and state["state"] == "retrying" and count(case, "submission_blocks") == 0
        due(case)
        matrix.peer.calls = []
        matrix.peer.mode = {}
        matrix.run(case)
        ok = (
            ok
            and matrix.state(case)["state"] == "moderation_submitted"
            and len(trace(case)) == 3
            and count(case, "attempt_preflights") == 2
        )
    matrix.check("FP-RES-007", ok)

    case, _, state, calls = execute("FP-RES-008", proveNotSent=True)
    resolution = matrix.sql(
        (
            "SELECT reason FROM attempt_resolutions WHERE attempt_id IN "
            "(SELECT attempt_id FROM submission_attempts WHERE "
            "intent_id=?)"
        ),
        [case.intent],
    )[0]
    rates = matrix.sql(
        (
            "SELECT consumed_slots,released FROM flickr_rate_reservations"
            " WHERE attempt_id IN (SELECT attempt_id FROM "
            "submission_attempts WHERE intent_id=?)"
        ),
        [case.intent],
    )
    matrix.check(
        "FP-RES-008",
        state["state"] == "retrying"
        and state["add_dispatch_count"] == 0
        and count(case, "submission_blocks") == 0
        and resolution["reason"] == "not_dispatched_transport_aborted"
        and rates == [{"consumed_slots": 2, "released": 1}]
        and len(calls) == 2,
    )

    case, _, state, calls = execute("FP-RES-009", rollbackResult=True)
    ok = (
        state["state"] == "attempting"
        and count(case, "submission_blocks") == 0
        and count(case, "attempt_resolutions") == 0
        and count(case, "attempt_dispatches") == 1
    )
    # Storage-fault case: move only the disposable lease deadline into the past,
    # then exercise the real claim/recovery path. Process-loss tests wait expiry.
    matrix.sql(
        (
            "UPDATE group_partitions SET "
            "lease_expires_at_us=1,invocation_deadline_at_us=1 WHERE "
            "partition_id=?"
        ),
        [case.partition],
    )
    matrix.peer.calls = []
    matrix.run(case)
    matrix.check(
        "FP-RES-009",
        ok
        and matrix.state(case)["state"] == "delivery_uncertain"
        and count(case, "submission_blocks") == 1
        and not trace(case),
    )

    case, _, state, calls = execute("FP-RES-010")
    before = matrix.sql(
        "SELECT COUNT(*) n FROM submission_attempts WHERE intent_id=?", [case.intent]
    )[0]["n"]
    matrix.peer.calls = []
    status, _ = matrix.request(
        "/api/v001/group-submission-batches",
        {
            "schemaVersion": 2,
            "photoBinding": {"fgaPhotoBindingId": case.binding, "expectedVerificationRevision": 1},
            "flickrGroupIds": [case.group],
        },
        case.code,
    )
    matrix.run(case)
    matrix.check(
        "FP-RES-010",
        status == 202
        and not trace(case)
        and before
        == matrix.sql(
            "SELECT COUNT(*) n FROM submission_attempts WHERE intent_id=?", [case.intent]
        )[0]["n"]
        and count(case, "submission_blocks") == 1,
    )


def crash_cases(matrix: Matrix) -> None:
    points = [
        ("001", "before_preflight"),
        ("002", "after_preflight"),
        ("003", "preflight_committed"),
        ("004", "marker_committed"),
        ("005", "handoff"),
        ("006", "response_received"),
        ("007", "result_rolled_back"),
        ("008", "result_committed"),
        ("009", "after_membership"),
        ("010", "membership_committed"),
    ]
    results: dict[str, list[dict[str, Any]]] = {number: [] for number, _ in points}
    for source in ("hint", "sweep"):
        for offset in (0, 5):
            selected = points[offset : offset + 5]
            cases = [matrix.seed("FP-CRASH-" + number + "-" + source) for number, _ in selected]
            for case in cases:
                matrix.sql(
                    (
                        "UPDATE flickr_write_gates SET enabled=1,revision=revision+1 "
                        "WHERE scope='user' AND scope_id=?"
                    ),
                    [case.user],
                )
            matrix.peer.calls = []
            matrix.peer.mode = {}
            for case, (_, point) in zip(cases, selected, strict=True):
                if point == "handoff":
                    matrix.peer.hold_add[case.group] = threading.Event()
            pool = ThreadPoolExecutor(max_workers=5)
            futures = []
            try:
                for case, (_, point) in zip(cases, selected, strict=True):
                    options: dict[str, Any] = {
                        "source": "admission" if source == "hint" else "sweep"
                    }
                    if point == "result_rolled_back":
                        options.update(rollbackResult=True, holdRollback=True)
                    elif point != "handoff":
                        options["hold"] = point
                    futures.append(pool.submit(matrix.run, case, **options))
                deadline = time.monotonic() + 35
                while time.monotonic() < deadline:
                    phases = matrix.control(action="phases")["phases"]
                    ready = []
                    for case, (_, point) in zip(cases, selected, strict=True):
                        ready.append(
                            any(
                                call.get("markerVisible") and call["photo"] == case.photo
                                for call in matrix.peer.calls
                            )
                            if point == "handoff"
                            else phases.get(case.partition) == point
                        )
                    if all(ready):
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("crash_targets_not_reached")
                before = {case.intent: matrix.state(case) for case in cases}
                prior_posts = {
                    case.intent: sum(
                        x["method"] == "flickr.groups.pools.add" and x["photo"] == case.photo
                        for x in matrix.peer.calls
                    )
                    for case in cases
                }
                restarted = matrix.restart()
                for event in matrix.peer.hold_add.values():
                    event.set()
                matrix.peer.hold_add.clear()
                for pending in futures:
                    try:
                        pending.result(timeout=10)
                    except OSError, http.client.HTTPException, ValueError, RuntimeError:
                        pass
                deadline = time.monotonic() + 65
                print("Waiting for real production lease expiry after process loss", flush=True)
                while time.monotonic() < deadline:
                    live = [
                        matrix.sql(
                            (
                                "SELECT lease_id IS NOT NULL AND "
                                "lease_expires_at_us>CAST(strftime('%s','now') AS "
                                "INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS "
                                "INTEGER)*1000 live FROM group_partitions WHERE "
                                "partition_id=?"
                            ),
                            [case.partition],
                        )[0]["live"]
                        for case in cases
                    ]
                    if not any(live):
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("crash_lease_expiry_timeout")
                matrix.peer.calls = []
                for case, (number, _point) in zip(cases, selected, strict=True):
                    matrix.run(case, source="admission" if source == "hint" else "sweep")
                    state = matrix.state(case)
                    blocks = matrix.sql(
                        "SELECT COUNT(*) n FROM submission_blocks WHERE photo_id=? AND group_id=?",
                        [case.photo, case.group],
                    )[0]["n"]
                    ambiguous = number in {"004", "005", "006", "007"}
                    committed = number == "008"
                    expected = (
                        "delivery_uncertain"
                        if ambiguous
                        else "moderation_submitted"
                        if committed
                        else "retrying"
                    )
                    ok = (
                        restarted
                        and state["state"] == expected
                        and blocks == int(ambiguous or committed)
                        and not any(x["photo"] == case.photo for x in matrix.peer.calls)
                    )
                    ok = ok and prior_posts[case.intent] == int(
                        number in {"005", "006", "007", "008"}
                    )
                    if not ambiguous and not committed:
                        deadline = time.monotonic() + 8
                        while time.monotonic() < deadline:
                            result = matrix.run(case)
                            if result["result"] != "no_claim":
                                break
                            time.sleep(0.1)
                        ok = (
                            ok
                            and matrix.state(case)["state"] == "moderation_submitted"
                            and sum(
                                x["method"] == "flickr.groups.pools.add"
                                and x["photo"] == case.photo
                                for x in matrix.peer.calls
                            )
                            == 1
                        )
                    results[number].append(
                        {
                            "entryPath": source,
                            "passed": ok,
                            "actualProcessStopped": restarted,
                            "recoveredState": state["state"],
                            "priorPosts": prior_posts[case.intent],
                            "initialState": before[case.intent]["state"],
                        }
                    )
                    print(
                        "FP-CRASH-" + number + "." + source + (": passed" if ok else ": FAILED"),
                        flush=True,
                    )
                    if not ok:
                        raise RuntimeError("crash_recovery_assertion_failed")
            finally:
                for event in matrix.peer.hold_add.values():
                    event.set()
                matrix.peer.hold_add.clear()
                if any(not f.done() for f in futures):
                    matrix.stop_process(force=True)
                pool.shutdown(wait=True, cancel_futures=True)
    for number, _ in points:
        matrix.check(
            "FP-CRASH-" + number,
            len(results[number]) == 2 and all(row["passed"] for row in results[number]),
            entryPaths=["hint", "sweep"],
            witnesses=results[number],
        )


def queue_cases(matrix: Matrix):
    def new(label):
        case = matrix.seed(label, admit_initial=False)
        matrix.peer.calls = []
        matrix.peer.mode = {}
        return case

    case = new("FP-QUEUE-001")
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: matrix.submit(case), range(2)))
    matrix.locate(case)
    matrix.wake(case)
    matrix.wait_terminal(case)
    rows = matrix.sql(
        (
            "SELECT CAST(enqueue_ordinal AS TEXT) ordinal FROM "
            "submission_intents WHERE photo_id=? AND group_id=?"
        ),
        [case.photo, case.group],
    )
    matrix.check(
        "FP-QUEUE-001",
        all(r["status"] == 202 for r in responses)
        and rows == [{"ordinal": "1"}]
        and matrix.sql(
            (
                "SELECT COUNT(*) n FROM submission_attempts WHERE intent_id=?"
                " AND NOT EXISTS(SELECT 1 FROM attempt_resolutions r WHERE "
                "r.attempt_id=submission_attempts.attempt_id)"
            ),
            [case.intent],
        )[0]["n"]
        <= 1
        and sum(x["method"] == "flickr.groups.pools.add" for x in matrix.peer.calls) == 1,
    )

    case = new("FP-QUEUE-002")
    failed = matrix.submit(case, rollbackAdmission=True)
    clean = (
        matrix.sql("SELECT COUNT(*) n FROM submission_intents WHERE user_id=?", [case.user])[0]["n"]
        == 0
    )
    bindings = [case.binding, case.binding + "-two"]
    matrix.sql(
        (
            "INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner"
            "_nsid,link_revision,verification_revision,source_kind) "
            "VALUES(?,?,?,'matrix-owner',1,1,'upload')"
        ),
        [bindings[1], case.user, case.photo + "-two"],
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda b: matrix.submit(case, binding=b), bindings))
    matrix.check(
        "FP-QUEUE-002",
        failed["status"] >= 400
        and clean
        and all(r["status"] == 202 for r in responses)
        and matrix.sql(
            (
                "SELECT CAST(enqueue_ordinal AS TEXT) ordinal FROM "
                "submission_intents WHERE user_id=? ORDER BY enqueue_ordinal"
            ),
            [case.user],
        )
        == [{"ordinal": "1"}, {"ordinal": "2"}],
    )

    case = new("FP-QUEUE-003")
    matrix.submit(case)
    matrix.locate(case)
    revision = matrix.sql(
        "SELECT CAST(wake_revision AS TEXT) revision FROM group_partitions WHERE partition_id=?",
        [case.partition],
    )[0]["revision"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda n: matrix.wake(
                    case, "0" if n == 0 else revision, "sweep" if n % 2 else "admission"
                ),
                range(4),
            )
        )
    matrix.wait_terminal(case)
    matrix.check(
        "FP-QUEUE-003",
        sum(x["method"] == "flickr.groups.pools.add" for x in matrix.peer.calls) == 1
        and matrix.sql(
            "SELECT COUNT(*) n FROM submission_attempts WHERE intent_id=?", [case.intent]
        )[0]["n"]
        == 1,
    )

    case = new("FP-QUEUE-004")
    matrix.submit(case)
    matrix.locate(case)
    before = matrix.sql(
        "SELECT CAST(enqueue_ordinal AS TEXT) ordinal FROM submission_intents WHERE intent_id=?",
        [case.intent],
    )
    matrix.control(action="scheduled")
    matrix.wait_terminal(case)
    matrix.check(
        "FP-QUEUE-004",
        before
        == matrix.sql(
            (
                "SELECT CAST(enqueue_ordinal AS TEXT) ordinal FROM "
                "submission_intents WHERE intent_id=?"
            ),
            [case.intent],
        )
        and sum(x["method"] == "flickr.groups.pools.add" for x in matrix.peer.calls) == 1,
    )

    case = new("FP-QUEUE-005")
    matrix.submit(case)
    matrix.locate(case)
    matrix.sql(
        (
            "UPDATE flickr_write_gates SET enabled=0,revision=revision+1 "
            "WHERE scope='user' AND scope_id=?"
        ),
        [case.user],
    )
    revision = matrix.sql(
        "SELECT revision FROM flickr_write_gates WHERE scope='user' AND scope_id=?", [case.user]
    )[0]["revision"]
    response = matrix.api(
        case,
        "/api/v001/admin/flickr-write-gates/user/resume",
        "POST",
        {"schemaVersion": 1, "expectedRevision": revision},
    )
    status = matrix.api(case, "/api/v001/admin/group-submission-intents?view=active")
    no_claim = (
        matrix.sql("SELECT COUNT(*) n FROM submission_attempts WHERE intent_id=?", [case.intent])[
            0
        ]["n"]
        == 0
    )
    matrix.run(case, stop="marker_committed")
    matrix.sql(
        (
            "UPDATE group_partitions SET "
            "lease_expires_at_us=1,invocation_deadline_at_us=1 WHERE "
            "partition_id=?"
        ),
        [case.partition],
    )
    matrix.wake(case, source="sweep")
    matrix.wait_terminal(case)
    matrix.check(
        "FP-QUEUE-005",
        response["status"] == 200
        and status["status"] == 200
        and no_claim
        and matrix.state(case)["state"] == "delivery_uncertain"
        and not any(x["method"] == "flickr.groups.pools.add" for x in matrix.peer.calls),
    )

    case = new("FP-QUEUE-006")
    matrix.submit(case)
    matrix.locate(case)
    binding = case.binding + "-next"
    photo = case.photo + "-next"
    matrix.sql(
        (
            "INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner"
            "_nsid,link_revision,verification_revision,source_kind) "
            "VALUES(?,?,?,'matrix-owner',1,1,'upload')"
        ),
        [binding, case.user, photo],
    )
    matrix.submit(case, binding=binding)
    before = matrix.sql(
        "SELECT wake_revision FROM group_partitions WHERE partition_id=?", [case.partition]
    )[0]["wake_revision"]
    matrix.run(case)
    rows = matrix.sql(
        (
            "SELECT "
            "photo_id,state,active_fifo_member,CAST(enqueue_ordinal AS "
            "TEXT) ordinal FROM submission_intents WHERE partition_id=? "
            "ORDER BY enqueue_ordinal"
        ),
        [case.partition],
    )
    partition = matrix.sql(
        "SELECT next_work_not_before_us,wake_revision FROM group_partitions WHERE partition_id=?",
        [case.partition],
    )[0]
    ok = (
        rows[0]["state"] == "moderation_submitted"
        and rows[0]["active_fifo_member"] == 0
        and rows[1]["state"] == "queued"
        and rows[1]["ordinal"] == "2"
        and partition["next_work_not_before_us"] is not None
        and partition["wake_revision"] > before
    )
    matrix.wake(case)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if (
            matrix.sql("SELECT state FROM submission_intents WHERE photo_id=?", [photo])[0]["state"]
            == "moderation_submitted"
        ):
            break
        time.sleep(0.1)
    matrix.check(
        "FP-QUEUE-006",
        ok
        and matrix.sql("SELECT state FROM submission_intents WHERE photo_id=?", [photo])[0]["state"]
        == "moderation_submitted",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["local", "hosted-db"], required=True)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--block-ids", nargs="*")
    parser.add_argument("--stop-after")
    parser.add_argument(
        "--section",
        choices=["core", "crash", "queue", "blocks", "smoke", "hosted-runtime", "all"],
        default="all",
    )
    args = parser.parse_args()
    if args.token_file:
        os.environ["CLOUDFLARE_API_TOKEN"] = bootstrap.file_token(str(args.token_file))
    matrix = Matrix(args.environment, args.native)
    matrix.stop_after = args.stop_after
    print("Private matrix run: " + str(matrix.directory), flush=True)
    try:
        matrix.start()
        if args.section == "hosted-runtime":
            from scripts.hosted_matrix_runtime import hosted_runtime

            hosted_runtime(matrix)
        if args.section == "smoke":
            case = matrix.seed("native-smoke")
            result = matrix.run(case)
            bootstrap.save(
                matrix.directory / "native-smoke-witness.json",
                {"result": result, "state": matrix.state(case), "calls": matrix.peer.calls},
            )
            matrix.check(
                "native-smoke",
                result["result"] == "moderation_submitted"
                and matrix.state(case)["state"] == "moderation_submitted",
            )
        if args.section in ("core", "all"):
            core_cases(matrix)
        if args.section in ("crash", "all"):
            crash_cases(matrix)
        if args.section in ("queue", "all"):
            queue_cases(matrix)
        if args.section in ("blocks", "all"):
            from scripts.production_matrix_blocks import block_cases

            block_cases(matrix, args.block_ids)
    except SelectedCaseComplete:
        pass
    except Exception as error:
        try:
            bootstrap.save(
                matrix.directory / "failure-state.json",
                {
                    "failureType": type(error).__name__,
                    "connections": matrix.sql(
                        "SELECT user_id,state,local_state,operation_id FROM flickr_connection_state"
                    ),
                    "operations": matrix.sql(
                        "SELECT kind,phase,generation,operation_id FROM flickr_lifecycle_operations"
                    ),
                    "oauth": matrix.sql(
                        "SELECT phase,operation_id,slot FROM flickr_oauth_transactions"
                    ),
                    "grant": matrix.control(action="grant-status"),
                    "calls": matrix.peer.calls,
                },
            )
        except Exception:
            pass
        raise
    finally:
        matrix.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
