"""Prepare a closed offline publisher packet. This does not authorize a hosted run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = "probes/publisher-qualification"
SOURCE_NAMES = """admin_api admin_registry admission album_attachment_store
album_attachment_transport album_attachment_worker album_binding_store album_bindings
album_create_repair_discovery album_create_repair_store album_create_repair
album_flickr_admission album_local_removal_store album_local_removal
album_materialization_store album_materialization_transport album_materialization_worker
album_obligation_store album_obligations album_title_store album_title_transport
album_title_worker album_title auth_admission browser_sessions dispatch_freshness
dispatch_policy dispatch_transport dispatch_worker existing_photo_discovery fail_polite
flickr_oauth flickr_rate flickr_reads flickr_strict_json google_identity group_discovery
group_registry installations intake_api native_lifecycle native_writer photo_memberships
photo_registry photo_thumbnails plugin_code_registry plugin_codes publish_services registry
release_contract scheduling session_inventory status_registry submission_status
upload_ambiguity_resolution upload_authorization_registry upload_authorization
upload_candidates upload_photo_binding worker""".split()
MIGRATION_NAMES = """foundation audit_component submission_coordination fail_polite_attempts
native_credential_reference native_lifecycle browser_auth flickr_oauth dispatch_policy
plugin_code_lifecycle submission_status protocol_repair_evidence group_discovery
photo_memberships upload_authorizations upload_photo_bindings upload_ambiguity_resolutions
publish_service_identities upload_candidate_authority album_bindings album_obligations
album_materialization album_create_repair album_title_sync album_attachment
album_local_removal""".split()
ASSET_NAMES = """app.mjs connection-polling.mjs index.html login-complete.mjs model.mjs
plugin-code-transfer.mjs plugin-codes-ui.mjs styles.css submission-status-model.mjs
submission-status-ui.mjs""".split()
SOURCES = tuple(
    sorted(
        [f"src/{n}.ts" for n in SOURCE_NAMES]
        + [f"migrations/{i:04}_{n}.sql" for i, n in enumerate(MIGRATION_NAMES, 1)]
        + [f"assets/admin/{n}" for n in ASSET_NAMES]
        + [
            "package.json",
            "package-lock.json",
            "tsconfig.json",
            "wrangler.example.jsonc",
            "docs/operations/hosted-publisher-qualification-packet-2026-10-17.md",
            "scripts/prepare_hosted_publisher_qualification.py",
            "tests/test_hosted_publisher_qualification.py",
            f"{PROBE}/offline.mjs",
            f"{PROBE}/manifest-template.json",
            f"{PROBE}/disabled-boundaries.test.mjs",
            f"{PROBE}/worker.ts",
            f"{PROBE}/wrangler.jsonc",
            f"{PROBE}/tsconfig.json",
            f"{PROBE}/runtime.test.mjs",
        ]
        + [f"{PROBE}/upload_checks.ts", f"{PROBE}/upload_checks.test.mjs"]
        + [f"{PROBE}/repair_checks.ts"]
    )
)
METADATA = ("manifest.json", "run-plan.json", "authorization-template.json")
IMPORT = re.compile(rb"(?:from\s*|import\s*\(|import\s*)['\"]([^'\"]+)['\"]")
GAPS = [
    "production_album_scheduler_not_composed",
    "production_album_credential_transport_adapter_not_composed",
    "exact_hosted_resource_binding_and_cleanup_not_authorized",
    "hosted_evidence_not_executed",
    "owner_exact_run_authorization_not_granted",
]
PINNED_INPUTS = {
    "wrangler.example.jsonc": "98379c9b23a441ea083d2433ef0992616b98465266689011edbf3adbce7fe4df",
    "package.json": "e2f360d067787a6092bccf93c0a54323958cf1c80ef569f09c3d193fee3f635a",
    "package-lock.json": "6894a3dcecffb784baae9751677b0c231250ae9e99a2cb6ddacc6011a0dc0048",
}


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_head(root: Path) -> str:
    value = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Source HEAD is not a full commit identity")
    return value


def commit_exact(root: Path, files: dict[str, bytes], head: str) -> bool:
    """Attest only the copied closure, preserving unrelated worktree changes."""
    try:
        output = subprocess.check_output(
            ["git", "-C", str(root), "ls-tree", "-r", head, "--", *SOURCES],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except OSError, subprocess.SubprocessError:
        return False
    entries = {}
    for line in output.splitlines():
        metadata, name = line.split("\t", 1)
        mode, kind, sha = metadata.split()
        if mode not in {"100644", "100755"} or kind != "blob":
            return False
        entries[name] = sha
    return set(entries) == set(files) and all(
        hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == entries[name]
        for name, data in files.items()
    )


def safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("Source escaped its root")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError("Linked files are not allowed")
    if not path.is_file():
        raise ValueError("Source is not a regular file")
    return path


def source_files(root: Path) -> dict[str, bytes]:
    root = root.resolve(strict=True)
    files = {name: safe_file(root, name).read_bytes() for name in SOURCES}
    if any(digest(files[name]) != expected for name, expected in PINNED_INPUTS.items()):
        raise ValueError("Pinned default-off configuration or toolchain changed")
    for name, data in files.items():
        if not (name.startswith("src/") or name.endswith((".mjs", ".ts"))):
            continue
        for raw in IMPORT.findall(data):
            imported = raw.decode()
            if imported.startswith("."):
                resolved = (root / name).parent.joinpath(imported).resolve()
                if (
                    not resolved.is_relative_to(root)
                    or resolved.relative_to(root).as_posix() not in files
                ):
                    raise ValueError("Unclosed source dependency")
            elif imported not in {
                "cloudflare:workers",
                "node:crypto",
                "node:url",
                "node:test",
                "node:child_process",
                "node:fs/promises",
                "node:os",
                "node:path",
                "miniflare",
                "node:assert/strict",
                "aws4fetch",
                "hono",
                "hono/html",
                "jose",
                "oauth-1.0a",
                "cookie-es",
                "csrf-sync",
                "google-auth-library",
                "ipaddr.js",
                "react-router",
            }:
                raise ValueError("Undeclared external import")
    template = json.loads(files[f"{PROBE}/manifest-template.json"])
    if template != packet_template():
        raise ValueError("Offline scope template changed")
    config = json.loads(files[f"{PROBE}/wrangler.jsonc"])
    if config != probe_config():
        raise ValueError("Disabled isolated configuration changed")
    return files


def packet_template() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "status": "NO-GO",
        "mode": "offline_preparation_only",
        "network": "forbidden",
        "resources": [],
        "deployable": False,
        "maximumDiagnosticSeconds": 30,
        "maximumRequests": 64,
        "maximumRequestsScope": "offline_diagnostic_only",
        "syntheticOnly": True,
        "productionCapabilitiesEnabled": False,
        "qualificationEntrypoint": f"{PROBE}/worker.ts",
        "phases": ["seed", "http", "materialize", "attach", "title", "remove", "finish"],
        "maximumPhaseSeconds": 60,
        "maximumRunSeconds": 1800,
        "maximumSyntheticProviderCallsPerPhase": 16,
        "maximumSyntheticPostsPerPhase": 1,
        "scenarios": ["happy", "create_lost", "attachment_lost", "title_lost"],
        "maximumClientRequestsPerScenario": 32,
        "maximumFreshResourcePairs": 4,
        "resourceReuseAcrossScenarios": False,
    }


def probe_config() -> dict[str, object]:
    return {
        "name": "fga-publisher-qualification-disposable",
        "main": "worker.ts",
        "compatibility_date": "2026-10-16",
        "compatibility_flags": ["nodejs_compat"],
        "workers_dev": False,
        "preview_urls": False,
        "observability": {"enabled": False},
        "vars": {
            "PROBE_ENABLED": "0",
            "PROBE_SCOPE": "publisher-disposable-v1",
            "PROBE_SCENARIO": "happy",
            "PROBE_ACCESS_TOKEN": "",
            "PROBE_ARTIFACT_SHA2_256": "",
            "PROBE_RUN_ID": "",
            "PROBE_RESOURCE_ID": "00000000-0000-0000-0000-000000000000",
            "PROBE_EXPIRES_AT": "",
        },
        "d1_databases": [
            {
                "binding": "DB",
                "database_name": "REPLACE_WITH_DISPOSABLE_PUBLISHER_DATABASE",
                "database_id": "00000000-0000-0000-0000-000000000000",
                "migrations_dir": "../../migrations",
            }
        ],
    }


def manifest(
    files: dict[str, bytes], source_head: str, source_commit_exact: bool = False
) -> dict[str, object]:
    if (
        set(files) != set(SOURCES)
        or not re.fullmatch(r"[0-9a-f]{40}", source_head)
        or type(source_commit_exact) is not bool
    ):
        raise ValueError("Exact closure and full source HEAD required")
    package = json.loads(files["package.json"])
    identity = {
        "schemaVersion": 1,
        "sourceHead": source_head,
        "status": "NO-GO",
        "sourceCommitExact": source_commit_exact,
        "migrationHead": "0026_album_local_removal.sql",
        "hashAlgorithm": "SHA2-256",
        "template": packet_template(),
        "tools": {
            "node": "24.22.0",
            "python": "3.14.7",
            "uv": "0.12.5",
            "npm": package["packageManager"],
            "devDependencies": package["devDependencies"],
        },
        "files": [
            {"path": name, "bytes": len(data), "sha2_256": digest(data)}
            for name, data in sorted(files.items())
        ],
    }
    return {**identity, "artifactSha2_256": digest(encoded(identity))}


def run_plan(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "artifactSha2_256": artifact["artifactSha2_256"],
        "status": "NO-GO",
        "hostedQualification": "not_executed",
        "offlineDiagnostic": "actual_handler_and_disabled_consumer_refusals_only",
        "isolatedQualificationExecutable": True,
        "productionSchedulerQualified": False,
        "fullPublisherExecutable": False,
        "missing": GAPS,
        "futureCases": [
            "normal_upload_origin_proof",
            "ambiguous_upload_no_repost",
            "candidate_advisory_not_binding",
            "publish_service_isolation",
            "first_candidate_fencing",
            "obligation_idempotency",
            "create_unknown_no_replay",
            "attachment_read_add_read",
            "repair_fresh_authority",
            "title_supersession_and_bounds",
            "local_removal_no_remote_delete",
            "stop_restart_restore_reconcile",
        ],
        "requiredReceipts": [
            "exact_optimized_bundle_and_config_hashes",
            "migration_0026",
            "bounded_resource_and_expiry_identity",
            "synthetic_upstream_only",
            "negative_mutations",
            "rollback_and_cleanup",
            "independent_review",
        ],
    }


def authorization_template(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "artifactSha2_256": artifact["artifactSha2_256"],
        "granted": False,
        "owner": None,
        "expiresAt": None,
        "resources": [],
        "allowDeploy": False,
        "allowProviderRequests": False,
        "allowProductionCapabilities": False,
    }


def verify(
    destination: Path,
    expected_digest: str | None = None,
    expected_source_head: str | None = None,
    require_commit_exact: bool = False,
) -> dict[str, object]:
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Linked stage root")
    destination = destination.resolve(strict=True)
    actual = set()
    for path in destination.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked staged content")
        if path.is_file():
            actual.add(path.relative_to(destination).as_posix())
    if actual != set(SOURCES) | set(METADATA):
        raise ValueError("Stage must contain the exact closed file set")
    recorded = json.loads((destination / "manifest.json").read_bytes())
    files = source_files(destination)
    artifact = manifest(files, recorded["sourceHead"], recorded["sourceCommitExact"])
    if require_commit_exact and not artifact["sourceCommitExact"]:
        raise ValueError("Closure is not attested to source commit bytes")
    if expected_source_head is not None and artifact["sourceHead"] != expected_source_head:
        raise ValueError("Stale source HEAD")
    if expected_digest is not None and artifact["artifactSha2_256"] != expected_digest:
        raise ValueError("Independent artifact digest mismatch")
    for name, value in (
        ("manifest.json", artifact),
        ("run-plan.json", run_plan(artifact)),
        ("authorization-template.json", authorization_template(artifact)),
    ):
        if (destination / name).read_bytes() != encoded(value):
            raise ValueError("Packet bytes changed")
    return artifact


def prepare(
    destination: Path,
    root: Path = ROOT,
    expected_source_head: str | None = None,
    require_commit_exact: bool = False,
) -> dict[str, object]:
    root = root.resolve(strict=True)
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise ValueError("Use a new private stage")
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(root):
        raise ValueError("Stage must be outside the checkout")
    head = source_head(root)
    if expected_source_head is not None and head != expected_source_head:
        raise ValueError("Stale source HEAD")
    files = source_files(root)
    exact = commit_exact(root, files, head)
    if require_commit_exact and not exact:
        raise ValueError("Closure differs from source commit or includes untracked files")
    artifact = manifest(files, head, exact)
    artifact_digest = artifact["artifactSha2_256"]
    if not isinstance(artifact_digest, str):
        raise ValueError("Invalid generated manifest digest")
    # All validation precedes the first write. No build, install, Git mutation or network.
    destination.mkdir()
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for name, value in (
        ("manifest.json", artifact),
        ("run-plan.json", run_plan(artifact)),
        ("authorization-template.json", authorization_template(artifact)),
    ):
        (destination / name).write_bytes(encoded(value))
    return verify(destination, artifact_digest, head, require_commit_exact)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-artifact")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--require-commit-exact", action="store_true")
    args = parser.parse_args()
    try:
        if args.expected_artifact and not args.verify:
            raise ValueError("Expected artifact requires verification")
        if args.verify and not args.expected_artifact:
            raise ValueError("Verification requires an independently retained digest")
        artifact = (
            verify(
                args.destination,
                args.expected_artifact,
                args.expected_source_head,
                args.require_commit_exact,
            )
            if args.verify
            else prepare(
                args.destination,
                expected_source_head=args.expected_source_head,
                require_commit_exact=args.require_commit_exact,
            )
        )
    except OSError, ValueError, KeyError, subprocess.SubprocessError:
        parser.exit(
            1, "Publisher packet refused; inspect closure, source HEAD and private stage.\n"
        )
    print(f"Source packet SHA2-256: {artifact['artifactSha2_256']}")
    print("NO-GO: full hosted publisher adapter and qualification remain incomplete.")


if __name__ == "__main__":
    main()
