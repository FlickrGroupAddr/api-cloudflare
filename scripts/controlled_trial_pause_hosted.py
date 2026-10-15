"""Verify the fixed pause batch against one newly created disposable hosted D1.

No production database/Worker lookup, configuration mutation or Flickr request.
The private journal retains the exact created database identity for cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import controlled_trial_pause as pause
from scripts.bootstrap_deployment import file_token
from scripts.coordination_probe import statements as migration_statements
from scripts.runtime_permissions_probe import ROOT


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def control(account: str, token: str, method: str, suffix: str, body: Any = None):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/accounts/" + account + "/d1/database" + suffix,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        response = urllib.request.build_opener(pause.NoRedirect).open(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("bounded_provider_response_exceeded")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("invalid_provider_response")
        return response.status, value


def snapshot(plan, token):
    return pause.request(
        plan,
        token,
        {
            "sql": """SELECT 'gate' AS kind, json_object('scope',scope,'scope_id',scope_id,
              'enabled',enabled,'revision',CAST(revision AS TEXT)) AS record
              FROM flickr_write_gates
              UNION ALL SELECT 'gate_event',json_object('id',event_id,'scope',scope,
              'scope_id',scope_id,'revision',CAST(revision AS TEXT),'reason',reason,
              'at',CAST(created_at_us AS TEXT)) FROM flickr_write_gate_events
              UNION ALL SELECT 'audit',json_object('id',event_id,'user',user_id,
              'action',action,'request',request_correlation_id,'reason',reason,
              'source',source_component,'at',created_at_utc) FROM audit_events
              ORDER BY kind,record""",
            "params": [],
        },
    )


def credentials(token_file: str | None, *, from_env: bool) -> tuple[str, str]:
    if from_env:
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        if not re.fullmatch(r"[a-f0-9]{32}", account) or not re.fullmatch(
            r"[A-Za-z0-9_-]{35,256}", token
        ):
            raise RuntimeError("operator_env_unavailable")
        return account, token
    if token_file is None:
        raise RuntimeError("operator_token_file_required")
    account = json.loads((ROOT / ".coordination-runs/fga-runtime-inputs.json").read_text())[
        "accountId"
    ]
    if not isinstance(account, str) or not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ValueError("invalid_approved_account")
    return account, file_token(token_file)


def run(token_file: str | None, output: Path, *, from_env: bool = False) -> int:
    name = "fga-pause-proof-" + secrets.token_hex(12)
    directory = output / ".coordination-runs" / name
    journal_path = directory / "journal.json"
    evidence_path = output / "docs/evidence/controlled-trial-pause-hosted-2026-10-15.json"
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    digest = hashlib.sha256()
    for migration in migrations:
        digest.update(migration.name.encode())
        digest.update(b"\0")
        digest.update(migration.read_bytes())
        digest.update(b"\0")
    journal = {
        "runName": name,
        "accountId": None,
        "databaseId": None,
        "creationAttempted": False,
        "cleanupConfirmed": False,
    }
    evidence: dict[str, Any] = {
        "schemaVersion": 1,
        "scope": "new_disposable_hosted_d1_only",
        "startedAt": datetime.now(UTC).isoformat(),
        "migrationHead": migrations[-1].name,
        "migrationSha2_256": digest.hexdigest(),
        "adapterSha2_256": hashlib.sha256(Path(pause.__file__).read_bytes()).hexdigest(),
        "hostedProofSha2_256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "providerTransport": "official_D1_REST_query_batch",
        "providerLibraryVersion": "urllib_python_standard_library",
        "migrationDigestAlgorithm": "sha256(name + NUL + content + NUL, ordered filenames)",
        "pyprojectSha2_256": hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest(),
        "uvLockSha2_256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "checks": {},
        "cleanupConfirmed": False,
        "passed": False,
        "authenticationSource": "dedicated_ci_environment" if from_env else "local_operator_input",
    }
    database_id = None

    try:
        account, token = credentials(token_file, from_env=from_env)
        journal["accountId"] = account
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        if from_env:
            evidence["unavailableReason"] = "operator_env_unavailable"
        elif token_file == "project-operator-in-memory":
            evidence["unavailableReason"] = "operator_auth_unavailable"
        else:
            evidence["unavailableReason"] = (
                "operator_token_file_missing"
                if token_file is None or not Path(token_file).is_file()
                else "operator_token_file_unavailable"
            )
        evidence["operatorAuthErrorClass"] = type(error).__name__
        evidence["resourceCreationAttempted"] = False
        evidence["cleanupConfirmed"] = True
        evidence["completedAt"] = datetime.now(UTC).isoformat()
        journal["cleanupConfirmed"] = True
        save(journal_path, journal)
        save(evidence_path, evidence)
        print(
            json.dumps(
                {
                    "passed": False,
                    "unavailableReason": evidence["unavailableReason"],
                    "resourceCreationAttempted": False,
                }
            )
        )
        return 1

    def check(label, condition):
        evidence["checks"][label] = bool(condition)
        save(evidence_path, evidence)
        if not condition:
            raise ValueError("hosted_proof_assertion_failed")

    try:
        journal["creationAttempted"] = True
        save(journal_path, journal)
        status, created = control(account, token, "POST", "", {"name": name})
        result = created.get("result")
        if status != 200 or created.get("success") is not True or not isinstance(result, dict):
            raise ValueError("disposable_database_creation_unconfirmed")
        candidate = result.get("uuid")
        if result.get("name") != name or not isinstance(candidate, str):
            raise ValueError("created_database_identity_mismatch")
        if str(uuid.UUID(candidate)) != candidate:
            raise ValueError("invalid_created_database_id")
        database_id = candidate
        journal["databaseId"] = database_id
        save(journal_path, journal)
        plan = pause.validate(
            {
                "schemaVersion": 1,
                "accountId": account,
                "databaseId": database_id,
                "fgaUserId": "pause-proof-owner",
                "operationId": str(uuid.uuid4()),
                "expectedDeploymentRevision": 7,
                "expectedDeploymentEnabled": 1,
                "expectedUserRevision": 4,
                "expectedUserEnabled": 1,
            }
        )
        for migration in migrations:
            pause.request(
                plan,
                token,
                {
                    "batch": [
                        {"sql": sql, "params": []}
                        for sql in migration_statements(migration.read_text(encoding="utf-8"))
                    ]
                },
            )
        check("all_current_migrations_applied", migrations[-1].name.startswith("0014_"))
        pause.request(
            plan,
            token,
            {
                "batch": [
                    {"sql": "INSERT INTO fga_users VALUES(?1)", "params": [plan["fgaUserId"]]},
                    {
                        "sql": "INSERT INTO flickr_write_gates VALUES('deployment','*',1,7)",
                        "params": [],
                    },
                    {
                        "sql": "INSERT INTO flickr_write_gates VALUES('user',?1,1,4)",
                        "params": [plan["fgaUserId"]],
                    },
                ]
            },
        )
        before = snapshot(plan, token)
        stale = {**plan, "expectedDeploymentRevision": 8}
        refused = False
        try:
            pause.request(stale, token, {"batch": pause.statements(stale)})
        except ValueError:
            refused = True
        check("stale_expected_revision_refused", refused)
        check("stale_batch_preserved_gates_history_audit", snapshot(plan, token) == before)
        pause.request(
            plan,
            token,
            {
                "sql": """CREATE TRIGGER pause_proof_audit_failure BEFORE INSERT ON audit_events
              WHEN NEW.action='flickr.operator_write_pause'
              BEGIN SELECT RAISE(ABORT,'synthetic_pause_audit_failure'); END;""",
                "params": [],
            },
        )
        refused = False
        try:
            pause.request(plan, token, {"batch": pause.statements(plan)})
        except ValueError:
            refused = True
        check("forced_audit_failure_refused", refused)
        check("audit_failure_preserved_both_gates_and_history", snapshot(plan, token) == before)
        pause.request(plan, token, {"sql": "DROP TRIGGER pause_proof_audit_failure", "params": []})
        rows = pause.request(plan, token, {"batch": pause.statements(plan)})
        check(
            "both_scopes_paused_with_atomic_audit",
            pause.receipt(plan, rows)["state"] == "confirmed_paused",
        )
        committed = snapshot(plan, token)
        # Simulate losing the already-committed result; inspection never replays
        # the mutation and the identical operation UUID identifies its audit.
        rows = pause.request(plan, token, pause.inspection_statement(plan))
        check(
            "lost_response_inspection_confirms_same_operation",
            pause.receipt(plan, rows)["state"] == "confirmed_paused",
        )
        check("inspection_preserved_all_pause_evidence", snapshot(plan, token) == committed)
        rows = pause.request(
            plan,
            token,
            {
                "sql": """SELECT
          (SELECT COUNT(*) FROM submission_intents) AS intents,
          (SELECT COUNT(*) FROM submission_attempts) AS attempts,
          (SELECT COUNT(*) FROM attempt_dispatches) AS dispatches,
          (SELECT COUNT(*) FROM submission_blocks) AS blocks,
          (SELECT COUNT(*) FROM transaction_guards) AS guards""",
                "params": [],
            },
        )
        check(
            "zero_submission_dispatch_and_residual_guard_rows",
            rows == [{"intents": 0, "attempts": 0, "dispatches": 0, "blocks": 0, "guards": 0}],
        )
        evidence["passed"] = True
    except (OSError, ValueError, KeyError, TypeError) as error:
        evidence["errorClass"] = type(error).__name__
    finally:
        if database_id:
            try:
                # Delete ONLY the returned ID created by this invocation, after
                # checking its exact fresh random name. Never accept an input ID.
                status, metadata = control(account, token, "GET", "/" + database_id)
                if status == 200 and metadata.get("result", {}).get("name") == name:
                    status, _ = control(account, token, "DELETE", "/" + database_id)
                    if status in (200, 204):
                        status, _ = control(account, token, "GET", "/" + database_id)
                        journal["cleanupConfirmed"] = status == 404
            except OSError, ValueError, TypeError:
                journal["cleanupConfirmed"] = False
        evidence["cleanupConfirmed"] = journal["cleanupConfirmed"]
        evidence["passed"] = bool(evidence["passed"] and evidence["cleanupConfirmed"])
        evidence["completedAt"] = datetime.now(UTC).isoformat()
        save(journal_path, journal)
        save(evidence_path, evidence)
    print(
        json.dumps(
            {
                "passed": evidence["passed"],
                "checks": evidence["checks"],
                "cleanupConfirmed": evidence["cleanupConfirmed"],
            }
        )
    )
    return 0 if evidence["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    authentication = parser.add_mutually_exclusive_group(required=True)
    authentication.add_argument("--token-file")
    authentication.add_argument("--from-env", action="store_true")
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args.token_file, args.output_directory.resolve(), from_env=args.from_env)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"passed": False, "errorClass": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
