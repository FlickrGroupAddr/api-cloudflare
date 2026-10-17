"""Stage an exact, source-only native qualification candidate; never execute it.

The destination must be new and outside the source checkout. No catalog, private
configuration, credential, photo, SDK binary, or production bundle is copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "FGA-ProviderRender-Evidence.lrplugin"
FIXTURE = f"probes/lightroom/{BUNDLE}"
VERSION = "0.0.1.1"
PUBLISHER = (
    "OrdinaryAlbumProvider",
    "OrdinaryAlbumProviderSettings",
    "FrozenPublishContext",
    "RenditionPolicy",
    "RenditionAdapter",
    "RenderPreflight",
    "PreflightCore",
)
CLIENT = (
    "FrozenChoiceConsumptionAdapter",
    "GroupSelectionStore",
    "GroupSelectionController",
    "ConnectionCore",
    "UploadAttemptStore",
    "UploadAttemptCodec",
    "dkjson",
    "MetadataDefinition",
)
PHASES = (
    "prepare",
    "default_callback",
    "album_callback",
    "restart_prepare",
    "restart_observe",
)
SOURCES = {
    **{
        f"{name}.lua": f"{FIXTURE}/{name}.lua"
        for name in (
            "Info",
            "Config",
            "Run",
            "Evidence",
            "Package",
            "Native",
            "NativeAssets",
            "EvidenceProvider",
            "Persistence",
        )
    },
    **{f"{name}.lua": f"clients/lightroom/publisher/{name}.lua" for name in PUBLISHER},
    **{f"{name}.lua": f"clients/lightroom/FGA-LrC15.lrplugin/{name}.lua" for name in CLIENT},
}
REQUIRE = re.compile(rb"\brequire\s*\(?\s*['\"]([A-Za-z][A-Za-z0-9_]*)['\"]")
CHECKS = {
    "prepare_native_evidence_checks.py": "scripts/prepare_native_evidence_checks.py",
    "native_profile_evidence.py": "scripts/native_profile_evidence.py",
}
# Independently retained reviewed metadata bytes, not hashes supplied by a stage.
# Deliberate metadata edits require review and an explicit pin update. Comparing
# the whole file rejects duplicate fields, computed values and trailing Lua code
# without evaluating any Lua or pretending a regex is a Lua parser.
METADATA_SHA2_256 = {
    "Config.lua": "d2d29e8ee18431d095f9e526c011d00c1edac39c92e957ed9e32607b08685e6d",
    "Package.lua": "7ff86832731a29992b38436bd3de88994f4ae949b8d34144d0af279f97fee8cf",
    "Info.lua": "3b6d0e4fd5785e2f1f19f05d6660cef5cc29afdfcfb40df5b66e8260c0c18477",
}


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files(root: Path) -> dict[str, bytes]:
    """Read only the closed allowlist and refuse links or unresolved dependencies."""
    root = root.resolve(strict=True)
    files = {}
    for name, relative in sorted(SOURCES.items()):
        source = root / relative
        if not source.resolve(strict=True).is_relative_to(root) or any(
            parent.is_symlink() or parent.is_junction()
            for parent in (source, *source.parents)
            if parent != root and parent.is_relative_to(root)
        ):
            raise ValueError("Source links are not supported")
        files[name] = source.read_bytes()
    return validate_files(files)


def validate_files(files: dict[str, bytes]) -> dict[str, bytes]:
    """Apply the same closure and metadata invariants before and after staging."""
    if set(files) != set(SOURCES):
        raise ValueError("Fixture source closure changed")
    for name, data in files.items():
        for required in REQUIRE.findall(data):
            if name == "dkjson.lua" and required in (b"debug", b"lpeg"):
                continue  # Vendored optional imports; no SDK or external module is copied.
            if required.decode() + ".lua" not in files:
                raise ValueError("Qualification module dependency is not in the closed allowlist")
    for name, expected in METADATA_SHA2_256.items():
        if digest(files[name]) != expected:
            raise ValueError("Fixture metadata differs from independently pinned reviewed bytes")
    return files


def check_files(root: Path) -> dict[str, bytes]:
    """Pin the actual offline checking programs without loading or executing them."""
    root = root.resolve(strict=True)
    result = {}
    for name, relative in CHECKS.items():
        path = root / relative
        if any(
            p.is_symlink() or p.is_junction()
            for p in (path, *path.parents)
            if p.is_relative_to(root) and p != root
        ):
            raise ValueError("Check source links are not supported")
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("Check source escaped the checkout")
        result[name] = path.read_bytes()
    return result


def manifest(files: dict[str, bytes], checks: dict[str, bytes]) -> dict[str, object]:
    records = [
        {"path": name, "source": SOURCES[name], "bytes": len(data), "sha2_256": digest(data)}
        for name, data in sorted(files.items())
    ]
    identity = {
        "schemaVersion": 1,
        "bundle": BUNDLE,
        "version": VERSION,
        "hostMajor": 15,
        "hostVersion": "15.6",
        "sdkVersion": "15.3",
        "hashAlgorithm": "SHA2-256",
        "optionalVendorImports": {"dkjson.lua": ["debug", "lpeg"]},
        "files": records,
        "checks": [
            {
                "path": f"checks/{name}",
                "source": CHECKS[name],
                "bytes": len(data),
                "sha2_256": digest(data),
            }
            for name, data in sorted(checks.items())
        ],
    }
    return {**identity, "artifactSha2_256": digest(encoded(identity))}


def consent_template(artifact: dict[str, object]) -> dict[str, object]:
    """An invalid, ungranted template; owner must supply actual action-time consent."""
    return {
        "schemaVersion": 1,
        "owner": None,
        "artifactSha2_256": artifact["artifactSha2_256"],
        "manifestSha2_256": digest(encoded(artifact)),
        "runId": None,
        "actionId": None,
        "phase": None,
        "catalogPath": None,
        "grantedAt": None,
        "expiresAt": None,
        "allowSyntheticCatalogWrites": False,
        "allowPrivateRenderedBytes": False,
        "allowSyntheticCallback": False,
        "allowCleanup": False,
    }


def run_plan(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "artifactSha2_256": artifact["artifactSha2_256"],
        "status": "prepared_source_only_not_executed",
        "nativeScopeReady": False,
        "profileIdentity": "unmeasured",
        "nativeCallback": "unmeasured",
        "restartPersistence": "unmeasured",
        "productionQualified": False,
        "manifestSha2_256": digest(encoded(artifact)),
        "maximumConsentSeconds": 1800,
        "hostWaitBoundProven": False,
        "filesystemIdentityProven": False,
        "atomicOutputCreationProven": False,
        "nativeActionStillUnavailable": True,
        "futureScope": {
            "evidenceOnlyProviderRegistration": True,
            "disposableCatalogBasename": "FGA-NativeEvidence-Disposable.lrcat",
            "privateEvidenceDirectoryBasename": "FGA-native-evidence-v1",
            "initialPhotoCount": 0,
            "qualificationServiceCount": 1,
            "generatedTiffPhotoCount": 1,
            "createdOrdinaryAlbumCount": 1,
            "maximumPrivatePngBytes": 33554432,
            "sourcePixels": "generated_8x8_rgb_tiff_only",
            "manualCloseAndReopenSameCatalog": True,
            "manualCatalogDisposalAfterHostCloses": True,
        },
        "phases": list(PHASES),
        "phaseReplay": "refused_consumed_once",
        "transport": "synthetic_only_no_network",
        "consent": {
            "status": "not_granted",
            "owner": None,
            "grantedAt": None,
            "expiresAt": None,
            "disposableCatalogIdentity": None,
            "artifactSha2_256": artifact["artifactSha2_256"],
        },
        "requiredReceipts": [
            "catalog_scope_guard",
            "actual_sdk_created_callback_context",
            "album_terminal_renditions_and_separate_default_host_drain_evidence",
            "default_and_ordinary_album_source_ready_no_auth_ordering",
            "private_png_profile_identity_analysis",
            "close_reopen_same_catalog_selection_attempt_readback",
            "zero_network_and_production_registration",
            "phase_scope_revocation_and_separate_manual_disposal",
        ],
    }


def verify(destination: Path, expected_digest: str | None = None) -> dict[str, object]:
    """Verify a staged tree; extra, linked, missing, and modified files all refuse."""
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Staged root links are not supported")
    destination = destination.resolve(strict=True)
    expected = (
        {"manifest.json", "run-plan.json", "consent-template.json"}
        | {f"{BUNDLE}/{n}" for n in SOURCES}
        | {f"checks/{n}" for n in CHECKS}
    )
    actual = set()
    for path in destination.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Staged links are not supported")
        if path.is_file():
            actual.add(path.relative_to(destination).as_posix())
    if actual != expected:
        raise ValueError("Staged artifact must have the exact closed file set")
    files = validate_files({name: (destination / BUNDLE / name).read_bytes() for name in SOURCES})
    checks = {name: (destination / "checks" / name).read_bytes() for name in CHECKS}
    result = manifest(files, checks)
    if expected_digest is not None and result["artifactSha2_256"] != expected_digest:
        raise ValueError("Staged artifact does not match the independently retained digest")
    if (destination / "manifest.json").read_bytes() != encoded(result):
        raise ValueError("Staged artifact manifest or file digest mismatch")
    if (destination / "run-plan.json").read_bytes() != encoded(run_plan(result)):
        raise ValueError("Source-only run plan changed; retain action-time records separately")
    if (destination / "consent-template.json").read_bytes() != encoded(consent_template(result)):
        raise ValueError(
            "Ungrantable preparation template changed; retain actual consent separately"
        )
    return result


def prepare(destination: Path, root: Path = ROOT) -> dict[str, object]:
    root = root.resolve(strict=True)
    # Resolve parent before writing so an existing junction cannot redirect into Git.
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise ValueError("Use a new private staging directory")
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(root):
        raise ValueError("Private artifact staging must be outside the source checkout")
    files = source_files(root)
    checks = check_files(root)
    result = manifest(files, checks)
    (destination / BUNDLE).mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (destination / BUNDLE / name).write_bytes(data)
    (destination / "checks").mkdir()
    for name, data in checks.items():
        (destination / "checks" / name).write_bytes(data)
    (destination / "manifest.json").write_bytes(encoded(result))
    (destination / "run-plan.json").write_bytes(encoded(run_plan(result)))
    (destination / "consent-template.json").write_bytes(encoded(consent_template(result)))
    return verify(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--verify", action="store_true", help="Read and verify an existing stage")
    parser.add_argument(
        "--expected-artifact", help="Compare with the independently retained digest"
    )
    args = parser.parse_args()
    try:
        if args.expected_artifact and not args.verify:
            raise ValueError("Expected artifact is only valid with --verify")
        result = (
            verify(args.destination, args.expected_artifact)
            if args.verify
            else prepare(args.destination)
        )
    except OSError, ValueError:
        parser.exit(
            1, "Qualification preparation refused; check source closure and private stage.\n"
        )
    print(f"Source-only artifact SHA2-256: {result['artifactSha2_256']}")
    print(f"Manifest bytes SHA2-256: {digest(encoded(result))}")
    print("Native qualification remains unmeasured; no fixture was loaded or executed.")


if __name__ == "__main__":
    main()
