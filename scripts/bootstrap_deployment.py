"""Provision the initial, fully disabled FGA deployment in the approved account.

Default is a read-only plan. --apply creates/recovers only resources recorded in
an ignored bootstrap journal. It never enables features or updates a completed
bootstrap. Operator authentication and secret values never reach stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import deployment_readiness as readiness
from scripts import runtime_permissions_probe as runtime
from scripts.secret_store_probe import private_process

ROOT = runtime.ROOT
DIRECTORY = ROOT / ".coordination-runs/production"
FLAGS = ("FGA_READ_ENABLED", "FGA_ADMIN_ENABLED", "FGA_INTAKE_ENABLED", "FGA_DISPATCH_ENABLED")
WORKER = "fga-api"
DATABASE = "fga-production"
STORE = "fga-managed"


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_token(path: str) -> str:
    raw = Path(path).read_text(encoding="utf-8-sig")
    candidates = set(re.findall(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{35,256}(?![A-Za-z0-9_-])", raw))
    if len(candidates) != 1:
        raise RuntimeError("token_file_ambiguous")
    return candidates.pop()


def application_credentials(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8-sig")
    fields = {}
    for label, name in [("Key", "consumerKey"), ("Secret", "consumerSecret")]:
        matches = re.findall(r"(?mi)^\s*" + label + r"\s*:\s*([a-f0-9]{16,64})\s*$", raw)
        if len(matches) != 1:
            raise RuntimeError("flickr_application_file_invalid")
        fields[name] = matches[0]
    return {"schemaVersion": 1, **fields}


def template() -> dict[str, Any]:
    source = (ROOT / "wrangler.example.jsonc").read_text(encoding="utf-8")
    return json.loads(re.sub(r"(?m)^\s*//[^\n]*", "", source))


def require_disabled(config: dict[str, Any]) -> None:
    if any(config.get("vars", {}).get(flag) != "0" for flag in FLAGS):
        raise RuntimeError("bootstrap_requires_all_features_disabled")
    if config.get("name") != WORKER or config.get("workers_dev") is not False:
        raise RuntimeError("bootstrap_worker_boundary_changed")
    if config.get("routes") != [{"pattern": readiness.DOMAIN, "custom_domain": True}]:
        raise RuntimeError("bootstrap_hostname_boundary_changed")


class Bootstrap:
    def __init__(self) -> None:
        self.inputs = json.loads(
            (ROOT / ".coordination-runs/fga-runtime-inputs.json").read_text(encoding="utf-8")
        )
        self.google = json.loads(
            (ROOT / ".coordination-runs/fga-google-config.json").read_text(encoding="utf-8")
        )
        if (
            self.inputs.get("accountMigrationApproved") is not True
            or self.inputs.get("targetAccountDomain") != "sixbuckssolutions.com"
        ):
            raise RuntimeError("approved_account_configuration_required")
        self.operator = readiness.token()
        zone = readiness.zone(self.inputs["accountId"], self.operator)
        if not zone or zone.get("status") != "active":
            raise RuntimeError("active_destination_zone_required")
        self.zone = zone
        self.prefix = "accounts/" + self.inputs["accountId"]
        self.path = DIRECTORY / "bootstrap.json"
        self.state = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.exists()
            else {
                "schemaVersion": 1,
                "bootstrapId": secrets.token_hex(16),
                "accountId": self.inputs["accountId"],
                "domain": readiness.DOMAIN,
                "createdAt": datetime.now(UTC).isoformat(),
            }
        )
        if (
            self.state["accountId"] != self.inputs["accountId"]
            or self.state["domain"] != readiness.DOMAIN
        ):
            raise RuntimeError("bootstrap_journal_identity_mismatch")

    def checkpoint(self, **updates: Any) -> None:
        self.state.update(updates)
        save(self.path, self.state)

    def call(self, method: str, suffix: str, body: Any = None) -> dict[str, Any]:
        request = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/" + self.prefix + "/" + suffix,
            method=method,
            headers={
                "Authorization": "Bearer " + self.operator,
                "Content-Type": "application/json",
            },
            data=None if body is None else json.dumps(body).encode(),
        )
        try:
            response = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(2097153)
            if len(raw) > 2097152:
                raise RuntimeError("control_response_over_budget")
            value = json.loads(raw)
            if (
                not isinstance(response.status, int)
                or response.status >= 300
                or value.get("success") is not True
            ):
                raise RuntimeError(f"cloudflare_{method.lower()}_http_{response.status}")
            return value

    def rows(self, suffix: str) -> list[dict[str, Any]]:
        rows = []
        for page in range(1, 11):
            value = self.call("GET", suffix + f"?page={page}&per_page=100")
            batch = value.get("result", [])
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise RuntimeError("inventory_over_budget")

    def plan(self) -> dict[str, Any]:
        require_disabled(template())
        application_credentials(self.inputs["flickrCredentialFile"])
        file_token(self.inputs["writerTokenFile"])
        if not re.fullmatch(
            r"[0-9]{10,30}", self.google.get("GOOGLE_OWNER_SUB", "")
        ) or not self.google.get("GOOGLE_CLIENT_ID", "").endswith(".apps.googleusercontent.com"):
            raise RuntimeError("google_configuration_invalid")
        read_token = file_token(self.inputs["zoneReadTokenFile"])
        dns_status, dns = readiness.get(
            "zones/" + self.zone["id"] + "/dns_records?per_page=100", read_token
        )
        if dns_status != 200 or dns.get("success") is not True:
            raise RuntimeError("destination_dns_inspection_required")
        if not self.state.get("workerAttempted") and dns.get("result"):
            raise RuntimeError("initial_bootstrap_requires_review_of_existing_dns")
        workers = self.rows("workers/scripts")
        if any(row.get("id") == WORKER for row in workers) and not self.state.get(
            "workerAttempted"
        ):
            raise RuntimeError("unowned_worker_name_collision")
        databases = self.rows("d1/database")
        if any(row.get("name") == DATABASE for row in databases) and not self.state.get(
            "databaseAttempted"
        ):
            raise RuntimeError("unowned_database_name_collision")
        stores = self.rows("secrets_store/stores")
        if stores and not self.state.get("storeAttempted"):
            raise RuntimeError("existing_secret_store_requires_review")
        return {
            "mode": "plan",
            "domain": readiness.DOMAIN,
            "worker": WORKER,
            "database": DATABASE,
            "secretStore": STORE,
            "secretBindingCount": 9,
            "featureFlags": dict.fromkeys(FLAGS, "0"),
            "ready": True,
        }

    def command(self, label: str, args: list[str]) -> str:
        result = private_process(args)
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        (DIRECTORY / (label + ".private.log")).write_text(
            result.stdout + "\n" + result.stderr, encoding="utf-8"
        )
        if result.returncode:
            raise RuntimeError(label + "_failed_see_private_log")
        return result.stdout

    def apply(self) -> dict[str, Any]:
        self.plan()
        if self.state.get("complete"):
            return {
                "mode": "apply",
                "alreadyComplete": True,
                "featureFlags": dict.fromkeys(FLAGS, "0"),
            }
        self.checkpoint()
        stores = self.rows("secrets_store/stores")
        matches = [row for row in stores if row.get("name") == STORE]
        if len(matches) > 1:
            raise RuntimeError("ambiguous_store")
        if not matches:
            self.checkpoint(storeAttempted=True)
            matches = [self.call("POST", "secrets_store/stores", {"name": STORE})["result"]]
        store_id = matches[0]["id"]
        if self.state.get("storeId", store_id) != store_id:
            raise RuntimeError("store_identity_changed")
        self.checkpoint(storeId=store_id)
        names = {row["binding"]: row["secret_name"] for row in template()["secrets_store_secrets"]}
        secret_path = "secrets_store/stores/" + store_id + "/secrets"
        existing = self.rows(secret_path)
        ownership = "FGA initial deployment " + self.state["bootstrapId"]
        owned = {row["name"]: row for row in existing if row["name"] in names.values()}
        if any(row.get("comment") != ownership for row in owned.values()):
            raise RuntimeError("unowned_secret_name_collision")
        values = {
            "FLICKR_APPLICATION": json.dumps(
                application_credentials(self.inputs["flickrCredentialFile"])
            ),
            "AUTH_LIMITER_KEY": secrets.token_hex(32),
            "NATIVE_WRITER_TOKEN": file_token(self.inputs["writerTokenFile"]),
            **{
                binding: json.dumps(
                    {"schemaVersion": 1, "generation": secrets.token_urlsafe(24), "retired": True}
                )
                for binding in ["FLICKR_GRANT", *[f"FLICKR_TEMP_{i}" for i in range(5)]]
            },
        }
        missing = [binding for binding, name in names.items() if name not in owned]
        if missing:
            self.checkpoint(secretCreationAttempted=True)
            self.call(
                "POST",
                secret_path,
                [
                    {
                        "name": names[binding],
                        "value": values[binding],
                        "scopes": ["workers"],
                        "comment": ownership,
                    }
                    for binding in missing
                ],
            )
        values.clear()
        owned = {
            row["name"]: row for row in self.rows(secret_path) if row["name"] in names.values()
        }
        if set(owned) != set(names.values()) or any(
            row.get("comment") != ownership for row in owned.values()
        ):
            raise RuntimeError("secret_creation_unconfirmed")
        secret_ids = {binding: owned[name]["id"] for binding, name in names.items()}
        self.checkpoint(secretIds=secret_ids)
        databases = [row for row in self.rows("d1/database") if row.get("name") == DATABASE]
        if len(databases) > 1:
            raise RuntimeError("ambiguous_database")
        if not databases:
            self.checkpoint(databaseAttempted=True)
            databases = [self.call("POST", "d1/database", {"name": DATABASE})["result"]]
        database_id = databases[0]["uuid"]
        if self.state.get("databaseId", database_id) != database_id:
            raise RuntimeError("database_identity_changed")
        self.checkpoint(databaseId=database_id)
        config = template()
        config.update(account_id=self.inputs["accountId"], main=str(ROOT / "src/worker.ts"))
        config["assets"]["directory"] = str(ROOT / "assets")
        config["vars"].update(self.google)
        config["vars"].update(
            FGA_FLICKR_OWNER_NSID=self.inputs["flickrOwnerNsid"],
            CF_ACCOUNT_ID=self.inputs["accountId"],
            CF_SECRET_STORE_ID=store_id,
            CF_GRANT_SLOT_ID=secret_ids["FLICKR_GRANT"],
            CF_OAUTH_SLOT_IDS=json.dumps([secret_ids[f"FLICKR_TEMP_{i}"] for i in range(5)]),
        )
        config["d1_databases"] = [
            {
                "binding": "DB",
                "database_name": DATABASE,
                "database_id": database_id,
                "migrations_dir": str(ROOT / "migrations"),
            }
        ]
        config["secrets_store_secrets"] = [
            {"binding": binding, "secret_name": name, "store_id": store_id}
            for binding, name in names.items()
        ]
        require_disabled(config)
        path = DIRECTORY / "wrangler.json"
        save(path, config)
        self.command(
            "typescript", [runtime.NODE, str(ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"]
        )
        self.command(
            "migrations",
            [
                runtime.NODE,
                str(runtime.WRANGLER),
                "d1",
                "migrations",
                "apply",
                "DB",
                "--remote",
                "--config",
                str(path),
            ],
        )
        self.checkpoint(migrationsApplied=True)
        self.command(
            "bundle",
            [
                runtime.NODE,
                str(runtime.WRANGLER),
                "deploy",
                "--dry-run",
                "--minify",
                "--config",
                str(path),
                "--outdir",
                str(DIRECTORY / "bundle"),
            ],
        )
        bundle = DIRECTORY / "bundle/worker.js"
        artifact = hashlib.sha256(bundle.read_bytes()).hexdigest()
        config.update(main=str(bundle), no_bundle=True, find_additional_modules=False)
        config["vars"]["FGA_ARTIFACT_SHA2_256"] = artifact
        require_disabled(config)
        save(path, config)
        self.checkpoint(workerAttempted=True, artifactSha2_256=artifact)
        self.command(
            "deploy", [runtime.NODE, str(runtime.WRANGLER), "deploy", "--config", str(path)]
        )
        self.checkpoint(
            complete=True,
            completedAt=datetime.now(UTC).isoformat(),
            featureFlags=dict.fromkeys(FLAGS, "0"),
        )
        return {
            "mode": "apply",
            "complete": True,
            "domain": readiness.DOMAIN,
            "artifactSha2_256": artifact,
            "featureFlags": dict.fromkeys(FLAGS, "0"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        bootstrap = Bootstrap()
        report = bootstrap.apply() if args.apply else bootstrap.plan()
        print(json.dumps(report, indent=2))
        return 0
    except RuntimeError as error:
        print(json.dumps({"complete": False, "error": str(error)}))
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"complete": False, "errorClass": type(error).__name__}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
