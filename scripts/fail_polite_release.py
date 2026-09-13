"""Refuse release without complete, exact-artifact production conformance evidence.

This is the promotion verifier, not an alternative test runner. Historical
bounded probes and local tests cannot satisfy its production evidence schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.current_schema_archive import ROOT, schema_contract

DEFAULT_CONTRACT = (
    ROOT.parent / "architecture-design/docs/testing/fail-polite-worker-database-conformance.md"
)
DEFAULT_EVIDENCE = ROOT / ".coordination-runs/production-release/evidence.json"
MUTATIONS = (
    "cached_preflight",
    "cached_membership",
    "continue_after_membership_failure",
    "filter_invalid_membership",
    "default_membership_to_empty",
    "separate_rate_reservations",
    "missing_moderation_unmoderated",
    "inclusive_freshness",
    "wrong_clock_profile",
    "invalid_age_accepted",
    "negative_age_accepted",
    "deferred_preparation",
    "intervening_flickr_operation",
    "post_before_marker",
    "code_6_retryable",
    "code_7_retryable",
    "unknown_retryable",
    "non_atomic_block_terminal",
    "retry_unresolved_dispatch",
    "clear_on_unmoderated",
    "clear_on_retention",
    "clear_on_relink",
    "clear_on_guessed_retry",
    "clear_on_positive_membership",
    "clear_on_negative_membership",
    "allow_force_flag",
    "allow_block_deletion",
    "missing_sql_guard",
)
MUTATION_CONTRACT_SHA2_256 = "8b0f65212f10f3e29ac310abdd62a81d93af45438d1fbaa901e40aaed6b3b7f6"
PROFILE = "adr-0056-private-workers-observed-time"
REQUIRED_ADAPTERS = (
    "production_worker",
    "production_migrations",
    "production_oauth_transport",
    "production_rate_allocator",
    "production_retry_policy",
    "authenticated_admission",
    "status_routes",
    "administrative_gate_repair",
    "native_lifecycle",
    "independent_process_stop",
    "deployment_restart",
    "current_schema_restore",
    "controlled_https_peer",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(contract: Path) -> tuple[list[str], str]:
    source = contract.read_text(encoding="utf-8")
    if "Status: Accepted required production test contract" not in source:
        raise ValueError("Conformance inventory is not the accepted contract")
    ids = re.findall(r"^\| `(FP-[A-Z]+-\d{3})` \|", source, re.MULTILINE)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Accepted contract has missing or duplicate case IDs")
    runtime_pin = re.findall(
        r'FGA_FAIL_POLITE_CONTRACT_SHA2_256 = "([a-f0-9]{64})"',
        (ROOT / "src/release_contract.ts").read_text(encoding="utf-8"),
    )
    if runtime_pin != [MUTATION_CONTRACT_SHA2_256]:
        raise ValueError("Runtime repair evidence and release verifier contract identities differ")
    contract_digest = digest(contract)
    if contract_digest != MUTATION_CONTRACT_SHA2_256:
        raise ValueError("Mutation inventory requires review after accepted contract changes")
    return sorted(ids), contract_digest


def validate(report: dict[str, Any], expected: dict[str, Any], ids: list[str]) -> list[str]:
    failures = []
    if (
        type(report.get("schemaVersion")) is not int
        or report.get("schemaVersion") != 1
        or report.get("scope") != "full-production"
    ):
        failures.append("full_production_evidence_required")
    for field, value in expected.items():
        if report.get(field) != value:
            failures.append("identity_mismatch:" + field)
    if report.get("clockProfile") != PROFILE:
        failures.append("accepted_clock_profile_required")
    engine = report.get("databaseEngine")
    if (
        not isinstance(engine, dict)
        or engine.get("provider") != "cloudflare-d1"
        or not all(
            isinstance(engine.get(key), str) and engine[key] not in {"", "unknown", "unavailable"}
            for key in ("version", "runtime", "migrationHead")
        )
    ):
        failures.append("real_database_provenance_required")
    if isinstance(engine, dict) and engine.get("migrationHead") != expected.get("migrationHead"):
        failures.append("database_migration_head_mismatch")
    adapters = report.get("adapters")
    if not isinstance(adapters, dict) or any(
        adapters.get(name) is not True for name in REQUIRED_ADAPTERS
    ):
        failures.append("required_infrastructure_missing")
    cases = report.get("cases", [])
    if not isinstance(cases, list) or any(not isinstance(row, dict) for row in cases):
        failures.append("invalid_cases")
        cases = []
    if Counter(row.get("id") for row in cases) != Counter(ids):
        failures.append("missing_extra_or_duplicate_case_ids")
    for row in cases:
        name = str(row.get("id", "unknown"))
        if row.get("status") != "passed" or row.get("skipped") is not False:
            failures.append("case_not_passed:" + name)
        if name.startswith("FP-CRASH-") and set(row.get("entryPaths", [])) != {"hint", "sweep"}:
            failures.append("crash_entry_paths_missing:" + name)
        if name.startswith("FP-BLOCK-") and set(row.get("seedReasons", [])) != {
            "code_6",
            "code_7",
            "unknown",
            "unresolved_dispatch",
        }:
            failures.append("block_seed_matrix_missing:" + name)
    mutations = report.get("mutations", [])
    if not isinstance(mutations, list) or any(not isinstance(row, dict) for row in mutations):
        failures.append("invalid_mutations")
        mutations = []
    if Counter(row.get("id") for row in mutations) != Counter(MUTATIONS):
        failures.append("missing_extra_or_duplicate_mutations")
    for row in mutations:
        detected = row.get("detectedBy")
        if (
            row.get("controlPassed") is not True
            or row.get("mutantFailed") is not True
            or row.get("failureKind") not in {"behavioral", "database"}
            or not isinstance(detected, list)
            or not detected
            or any(name not in ids for name in detected)
        ):
            failures.append("mutation_not_behaviorally_detected:" + str(row.get("id")))
    if (
        type(report.get("liveFlickrCalls")) is not int
        or report.get("liveFlickrCalls") != 0
        or report.get("rawCredentialsCaptured") is not False
    ):
        failures.append("synthetic_redacted_execution_required")
    if report.get("restorePreservesPostBackupProtection") is not True:
        failures.append("post_backup_protection_reconciliation_missing")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    try:
        ids, contract_digest = inventory(args.contract)
        if args.inventory:
            print(
                json.dumps(
                    {
                        "caseIds": ids,
                        "requiredMutations": MUTATIONS,
                        "contractSha2_256": contract_digest,
                    },
                    indent=2,
                )
            )
            return 0
        if not args.evidence.is_file() or args.artifact is None or args.config is None:
            raise ValueError(
                "Production evidence, optimized artifact and configuration are required"
            )
        source = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--",
                "src",
                "migrations",
                "package.json",
                "package-lock.json",
                "tsconfig.json",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if dirty.strip():
            raise ValueError("Production inputs must be committed before release verification")
        contract = schema_contract()
        expected = {
            "releaseCommit": source,
            "workerArtifactSha2_256": digest(args.artifact),
            "configurationSha2_256": digest(args.config),
            "migrationSha2_256": contract.migration_sha2_256,
            "migrationHead": contract.migration_head,
            "contractSha2_256": contract_digest,
        }
        report = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("Production evidence is not an object")
        failures = validate(report, expected, ids)
        print(
            json.dumps(
                {
                    "releaseEligible": not failures,
                    "failures": failures,
                    "requiredCaseCount": len(ids),
                    "requiredMutationCount": len(MUTATIONS),
                },
                indent=2,
            )
        )
        return int(bool(failures))
    except OSError, ValueError, TypeError, subprocess.SubprocessError:
        # Do not print raw config/report/command output that might contain secrets.
        print(
            json.dumps(
                {
                    "releaseEligible": False,
                    "failures": ["production_evidence_or_infrastructure_unavailable"],
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
