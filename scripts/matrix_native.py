"""Owned native secret fixtures and an private service adapter for independent-process tests."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from scripts import bootstrap_deployment as bootstrap
from scripts import runtime_permissions_probe as runtime
from scripts.hosted_restore_proof import Proof


class ControlError(RuntimeError):
    def __init__(self, status: int):
        super().__init__("cloudflare_control_http_" + str(status))
        self.status = status


class NativeFixtures:
    def __init__(self, proof: Proof):
        self.proof = proof
        self.name = proof.name + "-ss"
        self.store = ""
        self.ids: dict[str, str] = {}
        self.names = {
            "GRANT": self.name + "-grant",
            "APPLICATION": self.name + "-application",
            "LIMITER": self.name + "-limiter",
            **{f"TEMP_{i}": self.name + f"-temp-{i}" for i in range(5)},
        }
        self.attempted = False
        self.worker_attempted = False
        self.writer: dict[str, Any] = {}

    def call(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
        if path.startswith("/") or ".." in path or ":" in path:
            raise ValueError("invalid_control_path")
        request = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/"
            + self.proof.operator.account_id
            + "/"
            + path,
            method=method,
            headers={
                "Authorization": "Bearer " + self.proof.operator.operator,
                "Content-Type": "application/json",
                "User-Agent": "FGA-NativeMatrix/1",
            },
            data=None if body is None else json.dumps(body).encode(),
        )
        try:
            response = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(2097153)
            if len(raw) > 2097152:
                raise RuntimeError("control_response_over_budget")
            value = json.loads(raw)
            status = response.status
            if type(status) is not int:
                raise RuntimeError("invalid_control_status")
            if status >= 300 or value.get("success") is not True:
                raise ControlError(status)
            return value

    def rows(self, path: str):
        result = []
        for page in range(1, 101):
            batch = self.call("GET", path + f"?page={page}&per_page=10")["result"]
            result.extend(batch)
            if len(batch) < 10:
                return result
        raise RuntimeError("native_inventory_over_budget")

    def save(self):
        bootstrap.save(
            self.proof.directory / "native-ownership.json",
            {
                "name": self.name,
                "store": self.store,
                "ids": self.ids,
                "names": self.names,
                "attempted": self.attempted,
                "workerAttempted": self.worker_attempted,
            },
        )

    def prepare(self):
        # Reuse the existing runtime-only writer through a native binding. The broad
        # CI token stays in the controller and is never injected into application code.
        matches = []
        for store in self.rows("secrets_store/stores"):
            for secret in self.rows("secrets_store/stores/" + store["id"] + "/secrets"):
                if secret["name"] == "fga-native-writer":
                    matches.append((store["id"], secret))
        if len(matches) != 1:
            raise RuntimeError("unique_existing_runtime_writer_required")
        self.store, self.writer = matches[0]
        if not re.fullmatch(r"[a-f0-9]{32}", self.store):
            raise ValueError("invalid_native_store")
        current = self.rows("secrets_store/stores/" + self.store + "/secrets")
        if any(row["name"] in self.names.values() for row in current):
            raise RuntimeError("native_fixture_name_collision")
        self.attempted = True
        self.save()
        payload = []
        for binding, name in self.names.items():
            value = (
                {
                    "schemaVersion": 1,
                    "generation": "matrix-generation",
                    "token": "matrix-token",
                    "tokenSecret": "matrix-token-secret",
                }
                if binding == "GRANT"
                else {"schemaVersion": 1, "generation": "matrix-initial", "retired": True}
            )
            if binding == "APPLICATION":
                value = {
                    "schemaVersion": 1,
                    "consumerKey": "matrix-key",
                    "consumerSecret": "matrix-secret",
                }
            if binding == "LIMITER":
                value = "matrix-auth-limiter-key-with-at-least-32-characters"
            payload.append(
                {
                    "name": name,
                    "value": json.dumps(value),
                    "scopes": ["workers"],
                    "comment": "Owned synthetic FGA conformance fixture",
                }
            )
        created = self.call("POST", "secrets_store/stores/" + self.store + "/secrets", payload)[
            "result"
        ]
        for binding, name in self.names.items():
            found = [x for x in created if x["name"] == name]
            if len(found) != 1:
                raise RuntimeError("ambiguous_created_secret")
            self.ids[binding] = found[0]["id"]
        self.save()
        try:
            self.call("GET", "workers/scripts/" + self.name + "/settings")
        except ControlError as error:
            if error.status != 404:
                raise
        else:
            raise RuntimeError("native_worker_name_collision")
        bindings = [
            {"binding": binding, "store_id": self.store, "secret_name": name}
            for binding, name in self.names.items()
        ]
        bindings.append(
            {"binding": "WRITER", "store_id": self.store, "secret_name": "fga-native-writer"}
        )
        bridge_source = self.proof.directory / "secret-bridge.mjs"
        bridge_source.write_bytes((runtime.ROOT / "probes/release/secret-bridge.mjs").read_bytes())
        config = self.proof.directory / "native-bridge.json"
        bootstrap.save(
            config,
            {
                "name": self.name,
                "account_id": self.proof.operator.account_id,
                "main": str(bridge_source),
                "compatibility_date": "2026-09-11",
                "workers_dev": False,
                "preview_urls": False,
                "observability": {"enabled": False},
                "secrets_store_secrets": bindings,
            },
        )
        self.worker_attempted = True
        self.save()
        runtime.wrangler(
            runtime.Run(self.proof.directory, {"accountId": self.proof.operator.account_id}),
            "native-bridge-deploy",
            "deploy",
            "--minify",
            "--config",
            str(config),
        )

    def configuration(self):
        classes = {
            "FLICKR_GRANT": "Grant",
            "NATIVE_WRITER_TOKEN": "Writer",
            **{f"FLICKR_TEMP_{i}": f"Temp{i}" for i in range(5)},
        }
        services = [
            {"binding": binding, "service": self.name, "entrypoint": entry, "remote": True}
            for binding, entry in classes.items()
        ]
        variables = {
            "CF_ACCOUNT_ID": self.proof.operator.account_id,
            "CF_SECRET_STORE_ID": self.store,
            "CF_GRANT_SLOT_ID": self.ids["GRANT"],
            "CF_OAUTH_SLOT_IDS": json.dumps([self.ids[f"TEMP_{i}"] for i in range(5)]),
        }
        return {"services": services, "variables": variables, "slots": list(self.ids.values())}

    def reset_grant(self):
        self.call(
            "PATCH",
            "secrets_store/stores/" + self.store + "/secrets/" + self.ids["GRANT"],
            {
                "value": json.dumps(
                    {
                        "schemaVersion": 1,
                        "generation": "matrix-generation",
                        "token": "matrix-token",
                        "tokenSecret": "matrix-token-secret",
                    }
                ),
                "scopes": ["workers"],
            },
        )

    def cleanup(self):
        if self.worker_attempted:
            try:
                self.call("DELETE", "workers/scripts/" + self.name)
            except ControlError as error:
                if error.status != 404:
                    raise
        if self.attempted:
            rows = self.rows("secrets_store/stores/" + self.store + "/secrets")
            for row in rows:
                if row["name"] in self.names.values():
                    if not row["name"].startswith(self.name + "-"):
                        raise ValueError("secret_cleanup_boundary")
                    self.call(
                        "DELETE", "secrets_store/stores/" + self.store + "/secrets/" + row["id"]
                    )
            if any(
                row["name"] in self.names.values()
                for row in self.rows("secrets_store/stores/" + self.store + "/secrets")
            ):
                raise RuntimeError("native_secret_cleanup_unconfirmed")
        bootstrap.save(
            self.proof.directory / "native-cleanup.json",
            {"cleanupConfirmed": True, "existingWriterUnchanged": True},
        )
