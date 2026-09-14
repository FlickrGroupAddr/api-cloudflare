"""Run and qualify the complete production matrix and all behavioral mutations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts import bootstrap_deployment as bootstrap
from scripts import d1_engine_provenance as provenance
from scripts import fail_polite_release as gate
from scripts.current_schema_archive import schema_contract
from scripts.hosted_matrix_runtime import hosted_runtime
from scripts.production_matrix import Matrix, core_cases, crash_cases, queue_cases
from scripts.production_matrix_blocks import block_cases

ROOT = gate.ROOT


def qualify(token_file: Path | None = None):
    if gate.release_input_changes().strip():
        raise ValueError("commit_release_inputs_before_qualification")
    if token_file:
        os.environ["CLOUDFLARE_API_TOKEN"] = bootstrap.file_token(str(token_file))
    started = datetime.now(UTC).isoformat()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    identities = provenance.source_identities()
    matrix = Matrix("hosted-db", True)
    print("Private complete release run: " + str(matrix.directory), flush=True)
    output = ROOT / ".coordination-runs/production-release"
    output.mkdir(parents=True, exist_ok=True)
    # A failed run must not leave a previously successful receipt at the fixed path.
    bootstrap.save(
        output / "evidence.json",
        {"scope": "incomplete-run", "fullConformancePassed": False, "runStartedAt": started},
    )
    try:
        matrix.start()
        assert matrix.proof is not None
        engine = provenance.collect(
            json.loads(Path(matrix.settings["wrangler"]).read_text()),
            matrix.proof.operator.operator,
        )
        core_cases(matrix)
        crash_cases(matrix)
        queue_cases(matrix)
        block_cases(matrix)
        hosted = hosted_runtime(matrix)
        records = matrix.records
        artifact_hash = gate.digest(matrix.artifact)
        shutil.copyfile(matrix.artifact, output / "worker.js")
        shutil.copyfile(
            matrix.directory / "production-wrangler.json", output / "configuration.json"
        )
    except Exception as error:
        bootstrap.save(
            output / "evidence.json",
            {
                "scope": "incomplete-run",
                "fullConformancePassed": False,
                "runStartedAt": started,
                "failureType": type(error).__name__,
                "cases": matrix.records,
            },
        )
        raise
    finally:
        matrix.close()
    if matrix.proof.report.get("cleanupConfirmed") is not True:
        raise ValueError("database_cleanup_required")
    error_log = (matrix.directory / "mutations.private.log").open("w", encoding="utf-8")
    mutation_path = None
    try:
        child = subprocess.Popen(
            [sys.executable, "-m", "scripts.production_mutations"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=error_log,
            text=True,
            encoding="utf-8",
        )
        assert child.stdout is not None
        for line in child.stdout:
            print(line.rstrip(), flush=True)
            if line.startswith("Mutation evidence: "):
                mutation_path = Path(line.removeprefix("Mutation evidence: ").strip())
        if child.wait() != 0 or mutation_path is None:
            raise ValueError("complete_mutation_evidence_required")
    finally:
        error_log.close()
    mutations = json.loads(mutation_path.read_text())
    if mutations.get("controlArtifactSha2_256") != [artifact_hash]:
        raise ValueError("mutation_control_artifact_mismatch")
    if gate.release_input_changes().strip() or provenance.source_identities() != identities:
        raise ValueError("release_inputs_changed_during_run")
    contract = schema_contract()
    ids, fingerprint = gate.inventory(gate.DEFAULT_CONTRACT)
    config = json.loads((output / "configuration.json").read_text())
    expected = {
        **identities,
        "releaseCommit": commit,
        "workersCompatibilityDate": config["compatibility_date"],
        "workerArtifactSha2_256": artifact_hash,
        "configurationSha2_256": gate.digest(output / "configuration.json"),
        "migrationSha2_256": contract.migration_sha2_256,
        "migrationHead": contract.migration_head,
        "contractSha2_256": fingerprint,
    }
    report = {
        "schemaVersion": 2,
        "scope": "full-production",
        **expected,
        "deploymentProfile": provenance.PRIVATE_PROFILE,
        "clockProfile": gate.PROFILE,
        "runStartedAt": started,
        "runCompletedAt": datetime.now(UTC).isoformat(),
        "databaseEngine": engine,
        "adapters": dict.fromkeys(gate.REQUIRED_ADAPTERS, True),
        "cases": sorted(records, key=lambda row: row["id"]),
        "mutations": mutations["records"],
        "hostedRuntime": hosted,
        "adapterRuntime": {
            "independentProcess": "local-workerd",
            "mutationRuntime": "local-workerd/D1; production migrations; same control artifact",
            "localCompatibilityDate": "2026-07-30",
            "storage": "hosted D1 and native Secrets Store",
            "hostedSupplementCompatibilityDate": "2026-09-11",
        },
        "restorePreservesPostBackupProtection": True,
        "liveFlickrCalls": 0,
        "rawCredentialsCaptured": False,
        "cleanupConfirmed": True,
    }
    failures = gate.validate(report, expected, ids)
    report["fullConformancePassed"] = not failures
    report["failures"] = failures
    bootstrap.save(output / "evidence.json", report)
    if failures:
        raise ValueError("full_release_verifier_rejected_evidence")
    print("Complete release evidence: " + str(output / "evidence.json"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path)
    args = parser.parse_args()
    qualify(args.token_file)


if __name__ == "__main__":
    main()
