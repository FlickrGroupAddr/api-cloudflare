"""Disposable current-schema D1 export/restore and stale-backup refusal proof.

No Worker is bound to these databases. Only synthetic rows are seeded. This is
one infrastructure proof, never a full fail-polite release pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from scripts import bootstrap_deployment as bootstrap
from scripts import current_schema_archive as archive
from scripts import d1_engine_provenance as provenance
from scripts import deployment_readiness as readiness
from scripts import runtime_permissions_probe as runtime

ROOT = runtime.ROOT

SEED = """
INSERT INTO fga_users VALUES('restore-owner');
INSERT INTO flickr_links VALUES('restore-owner','synthetic-nsid',1,'paused');
INSERT INTO flickr_connection_state(user_id,state,local_state)
 VALUES('restore-owner','unlinked','absent');
INSERT INTO flickr_write_gates VALUES('deployment','*',0,1),('user','restore-owner',0,1);
INSERT INTO admin_principals VALUES('restore-owner','https://accounts.google.com','synthetic-sub',1);
INSERT INTO admin_sessions VALUES('restore-session',printf('%064d',1),'restore-owner',
 printf('%043d',2),1000,1000,86400001000,1000,NULL,NULL,1,'synthetic-correlation');
PRAGMA defer_foreign_keys=ON;
INSERT INTO installations(installation_id,user_id,credential_class,
 state,revision,current_version_id)
 VALUES('restore-installation','restore-owner','lrc_plugin','active',1,'restore-version');
INSERT INTO installation_credential_versions(version_id,installation_id,
 credential_digest,state,ordinal)
 VALUES('restore-version','restore-installation',printf('%064d',3),'current',1);
"""
LATER = """
UPDATE admin_sessions SET revoked_at_us=2000,revocation_reason='owner_revoked',revision=2;
PRAGMA defer_foreign_keys=ON;
UPDATE installations SET state='revoked',current_version_id=NULL,revision=2,
 revoked_at_utc='2026-09-14T00:00:00.000000Z';
UPDATE installation_credential_versions SET state='revoked';
INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason)
 VALUES('restore-audit','restore-owner','restore.fixture','synthetic-request','succeeded','synthetic');
INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES
 ('photo-six','group','flickr_code_6','attempt-six'),
 ('photo-seven','group','flickr_code_7','attempt-seven'),
 ('photo-unknown','group','delivery_uncertain','attempt-unknown'),
 ('photo-unresolved','group','delivery_uncertain','attempt-unresolved');
"""


def require_current_restore(actual: archive.Archive, required: archive.Archive) -> None:
    """Conservative operator barrier: unknown/newer facts cannot be silently lost.

    A complete frozen recovery snapshot is required. This does not guess or merge
    individual rows from an older snapshot and cannot authorize application writes.
    """
    if (
        actual.migration_sha2_256 != required.migration_sha2_256
        or actual.rows != required.rows
        or archive.object_map(actual.objects) != archive.object_map(required.objects)
    ):
        raise ValueError("restore_does_not_preserve_current_recovery_snapshot")


class QueryFailure(RuntimeError):
    def __init__(self, status: int, errors: Any):
        super().__init__("disposable_database_query_failed")
        self.status, self.errors = status, errors

    def is_guard(self, marker: str) -> bool:
        return (
            self.status == 400
            and isinstance(self.errors, list)
            and len(self.errors) == 1
            and isinstance(self.errors[0], dict)
            and self.errors[0].get("code") == 7500
            and str(self.errors[0].get("message", "")).startswith(marker + ": SQLITE_CONSTRAINT")
        )


class D1Operator:
    """Small account-scoped D1 client usable with local login or a dedicated CI token."""

    def __init__(self) -> None:
        self.account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        self.operator = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        if not self.account_id and not os.environ.get("CI"):
            inputs = json.loads((ROOT / ".coordination-runs/fga-runtime-inputs.json").read_text())
            self.account_id = inputs["accountId"]
        if not self.operator and not os.environ.get("CI"):
            self.operator = readiness.token()
        if not re.fullmatch(r"[a-f0-9]{32}", self.account_id) or not self.operator:
            raise ValueError("dedicated_ci_credentials_required")

    def call(self, method: str, suffix: str, body: Any = None) -> dict[str, Any]:
        if not re.fullmatch(
            r"d1/database(?:/[a-f0-9-]{36})?(?:\?page=[0-9]+&per_page=100)?", suffix
        ):
            raise ValueError("non_d1_control_request_forbidden")
        request = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/" + self.account_id + "/" + suffix,
            method=method,
            headers={
                "Authorization": "Bearer " + self.operator,
                "Content-Type": "application/json",
                "User-Agent": "FGA-RestoreProof/1",
            },
            data=None if body is None else json.dumps(body).encode(),
        )
        try:
            response = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(2_097_153)
            if len(raw) > 2_097_152:
                raise RuntimeError("control_response_over_budget")
            payload = json.loads(raw)
            if (
                response.status != 200
                or not isinstance(payload, dict)
                or payload.get("success") is not True
            ):
                raise RuntimeError("d1_control_request_failed")
            return payload

    def rows(self, suffix: str) -> list[dict[str, Any]]:
        rows = []
        for page in range(1, 11):
            batch = self.call("GET", suffix + f"?page={page}&per_page=100")["result"]
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise RuntimeError("database_inventory_over_budget")


class Proof:
    def __init__(self) -> None:
        self.operator = D1Operator()
        self.name = "fga-restore-" + secrets.token_hex(12)
        self.directory = ROOT / ".coordination-runs" / self.name
        self.directory.mkdir(parents=True)
        self.owned: dict[str, str] = {}
        self.report: dict[str, Any] = {
            "schemaVersion": 1,
            "scope": "hosted-current-schema-restore",
            "startedAt": datetime.now(UTC).isoformat(),
            "fullConformancePassed": False,
            "liveFlickrCalls": 0,
            "workerEverBound": False,
            "integrityCheck": "quick_check",
            "cases": [],
        }
        self.contract = archive.schema_contract()

    def save(self) -> None:
        bootstrap.save(self.directory / "ownership.json", self.owned)
        bootstrap.save(self.directory / "report.json", self.report)

    def check(self, name: str, condition: bool) -> None:
        self.report["cases"].append({"id": name, "passed": condition})
        self.save()
        print(name + (": passed" if condition else ": FAILED"), flush=True)
        if not condition:
            raise ValueError("restore_assertion_failed")

    def create(self, suffix: str) -> str:
        name = self.name + "-" + suffix
        # Persist intended name before create; cleanup can recover an ambiguous response.
        self.owned[name] = ""
        self.save()
        row = self.operator.call("POST", "d1/database", {"name": name})["result"]
        if row.get("name") != name:
            raise ValueError("created_database_name_mismatch")
        self.owned[name] = row["uuid"]
        self.save()
        return row["uuid"]

    def query(self, database: str, sql: str) -> list[dict[str, Any]]:
        if database not in self.owned.values() or not database:
            raise ValueError("database_not_owned_by_this_run")
        status, value = provenance.request(
            self.operator.account_id,
            database,
            self.operator.operator,
            sql,
            max_response_bytes=4 * 1024 * 1024,
        )
        if status != 200 or value.get("success") is not True:
            bootstrap.save(
                self.directory / "query-failure.json",
                {
                    "httpStatus": status,
                    "errors": value.get("errors", []),
                    "statementStart": sql.strip()[:100],
                },
            )
            raise QueryFailure(status, value.get("errors", []))
        result = value["result"]
        if not isinstance(result, list) or any(row.get("success") is not True for row in result):
            raise ValueError("database_statement_failed")
        return [item for row in result for item in row.get("results", [])]

    def migrate(self, database: str) -> None:
        config = self.directory / "wrangler.json"
        bootstrap.save(
            config,
            {
                "name": self.name,
                "account_id": self.operator.account_id,
                "d1_databases": [
                    {
                        "binding": "DB",
                        "database_name": next(
                            name for name, owned in self.owned.items() if owned == database
                        ),
                        "database_id": database,
                        "migrations_dir": str(ROOT / "migrations"),
                    }
                ],
            },
        )
        run = runtime.Run(self.directory, {"accountId": self.operator.account_id})
        runtime.wrangler(
            run,
            "production-migrations",
            "d1",
            "migrations",
            "apply",
            "DB",
            "--remote",
            "--config",
            str(config),
        )

    def capture(self, database: str) -> archive.Archive:
        return archive.capture(
            lambda sql: self.query(database, sql), self.contract, source_stopped=True
        )

    def restore(self, database: str, saved: archive.Archive) -> None:
        # Reconfirm the server-side identity immediately before importing. Only
        # newly created test databases from this run can reach the empty check.
        names = [name for name, value in self.owned.items() if value == database]
        if len(names) != 1 or not names[0].startswith(self.name + "-"):
            raise ValueError("restore_target_not_owned")
        metadata = self.operator.call("GET", "d1/database/" + database)["result"]
        if metadata.get("name") != names[0] or metadata.get("uuid") != database:
            raise ValueError("restore_target_identity_changed")
        # Always a fresh, unbound target; never issue DROP against an existing database.
        objects = self.query(database, archive.SCHEMA_SQL)
        if any(row["tbl_name"] != "_cf_KV" for row in objects):
            raise ValueError("restore_target_not_empty")
        print("Verified empty, owned restore target: " + names[0], flush=True)
        self.query(database, saved.sql())
        archive.verify_restored(
            lambda sql: self.query(database, sql),
            saved,
            self.contract,
            integrity_pragma="quick_check",
        )

    def cleanup(self) -> None:
        rows = self.operator.rows("d1/database")
        for name, database in list(self.owned.items()):
            if not name.startswith(self.name + "-"):
                raise ValueError("cleanup_name_boundary")
            matches = [row for row in rows if row.get("name") == name]
            if not matches:
                continue
            if len(matches) != 1 or (database and matches[0]["uuid"] != database):
                raise ValueError("cleanup_identity_mismatch")
            self.operator.call("DELETE", "d1/database/" + matches[0]["uuid"])
        remaining = self.operator.rows("d1/database")
        self.report["cleanupConfirmed"] = not any(
            row.get("name") in self.owned for row in remaining
        )
        self.save()
        if not self.report["cleanupConfirmed"]:
            raise ValueError("cleanup_not_confirmed")

    def run(self) -> None:
        try:
            source = self.create("source")
            self.migrate(source)
            self.query(source, SEED)
            old = self.capture(source)
            self.query(source, LATER)
            current = self.capture(source)
            self.report["archive"] = current.summary()
            self.check(
                "current-schema-all-tables", len(current.rows) == len(self.contract.tables) + 1
            )
            stale = self.create("stale")
            self.restore(stale, old)
            try:
                require_current_restore(self.capture(stale), current)
            except ValueError:
                rejected = True
            else:
                rejected = False
            self.check("old-backup-refused-before-resume", rejected)
            self.check(
                "old-backup-lacks-later-blocks",
                self.query(stale, "SELECT COUNT(*) n FROM submission_blocks")[0]["n"] == 0,
            )
            self.check(
                "old-backup-resurrected-session-detected",
                self.query(stale, "SELECT revoked_at_us FROM admin_sessions")[0]["revoked_at_us"]
                is None,
            )
            self.check(
                "old-backup-still-paused",
                self.query(stale, "SELECT SUM(enabled) n FROM flickr_write_gates")[0]["n"] == 0,
            )
            target = self.create("current")
            self.restore(target, current)
            require_current_restore(self.capture(target), current)
            self.check("hosted-exact-current-schema-roundtrip", True)
            self.check(
                "all-four-block-seeds-preserved",
                self.query(target, "SELECT COUNT(*) n FROM submission_blocks")[0]["n"] == 4,
            )
            self.check(
                "session-revocation-preserved",
                self.query(target, "SELECT revoked_at_us FROM admin_sessions")[0]["revoked_at_us"]
                == 2000,
            )
            self.check(
                "installation-revocation-preserved",
                self.query(target, "SELECT state FROM installations")[0]["state"] == "revoked",
            )
            for table in ("submission_blocks", "audit_events"):
                before = self.capture(target)
                try:
                    self.query(target, "DELETE FROM " + table)
                except QueryFailure as error:
                    denied = error.is_guard(
                        "block_immutable" if table == "submission_blocks" else "audit_immutable"
                    )
                else:
                    denied = False
                self.check(
                    "restored-guard-" + table, denied and self.capture(target).rows == before.rows
                )
            self.check(
                "restored-write-gates-paused",
                self.query(target, "SELECT SUM(enabled) n FROM flickr_write_gates")[0]["n"] == 0,
            )
        finally:
            self.cleanup()
            self.report["completedAt"] = datetime.now(UTC).isoformat()
            self.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="Create and remove synthetic D1 databases"
    )
    args = parser.parse_args()
    if not args.run:
        parser.print_help()
        return 0
    proof = Proof()
    try:
        proof.run()
    except OSError, ValueError, RuntimeError, KeyError, IndexError:
        print(json.dumps({"passed": False, "report": str(proof.directory / "report.json")}))
        return 1
    print(
        json.dumps(
            {
                "passed": True,
                "fullConformancePassed": False,
                "report": str(proof.directory / "report.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
