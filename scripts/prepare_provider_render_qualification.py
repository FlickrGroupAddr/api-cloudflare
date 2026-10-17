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
BUNDLE = "FGA-ProviderRender-Qualification.lrplugin"
FIXTURE = f"probes/lightroom/{BUNDLE}"
VERSION = "0.0.1.2"
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
CASES = (
    "selection_absent",
    "selection_none",
    "selection_groups",
    "selection_edit_after_freeze",
    "photo_failure_isolation",
    "target_rejected",
    "catalog_changed",
    "activation_changed",
    "cancelled",
    "render_failed",
    "missing_file",
    "oversized_file",
    "file_changed",
    "cleanup_revocation",
)
SOURCES = {
    **{
        f"{name}.lua": f"{FIXTURE}/{name}.lua"
        for name in (
            "Info",
            "Config",
            "Run",
            "Qualification",
            "SyntheticTransport",
            "Package",
            "Native",
            "NativeAssets",
            "QualificationProvider",
        )
    },
    **{f"{name}.lua": f"clients/lightroom/publisher/{name}.lua" for name in PUBLISHER},
    **{f"{name}.lua": f"clients/lightroom/FGA-LrC15.lrplugin/{name}.lua" for name in CLIENT},
}
REQUIRE = re.compile(rb"\brequire\s*\(?\s*['\"]([A-Za-z][A-Za-z0-9_]*)['\"]")


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
    for name, data in files.items():
        for required in REQUIRE.findall(data):
            if name == "dkjson.lua" and required in (b"debug", b"lpeg"):
                continue  # Vendored optional imports; no SDK or external module is copied.
            if required.decode() + ".lua" not in files:
                raise ValueError("Qualification module dependency is not in the closed allowlist")
    config = files["Config.lua"]
    case_block = re.search(rb"CASES\s*=\s*\{([^}]*)\}", config)
    if (
        case_block is None
        or tuple(value.decode() for value in re.findall(rb"['\"]([^'\"]+)['\"]", case_block[1]))
        != CASES
    ):
        raise ValueError("Fixture finite cases differ from the pinned run plan")
    for field, value in (("VERSION", VERSION), ("SDK", "15.3")):
        if not re.search(rf"\b{field}\s*=\s*['\"]{re.escape(value)}['\"]".encode(), config):
            raise ValueError("Fixture version differs from the pinned package")
    if not re.search(rb"EXPECTED_HOST\s*=\s*\{major\s*=\s*15,minor\s*=\s*6\}", config):
        raise ValueError("Fixture host target differs from the pinned package")
    declarations = {
        "Info.lua": {
            "LrMetadataProvider": "'MetadataDefinition.lua'",
            "LrSdkVersion": "15.3",
            "LrSdkMinimumVersion": "15.3",
            "LrToolkitIdentifier": "'com.sixbuckssolutions.fga.providerrender.qualification.lrc15'",
        },
        "Package.lua": {
            "schemaVersion": "1",
            "version": "'0.0.1.2'",
            "hostMajor": "15",
            "hostVersion": "'15.6'",
            "sdkVersion": "'15.3'",
        },
    }
    for name, fields in declarations.items():
        for key, literal in fields.items():
            # Require the complete literal and delimiter, rejecting e.g. 15.30.
            pattern = rf"\b{key}\s*=\s*{re.escape(literal)}\s*[,}}]".encode()
            if len(re.findall(pattern, files[name])) != 1:
                raise ValueError("Fixture metadata differs from the pinned package")
    version = rb"VERSION\s*=\s*\{\s*major\s*=\s*0\s*,\s*minor\s*=\s*0\s*,"
    version += rb"\s*revision\s*=\s*1\s*,\s*build\s*=\s*2\s*\}"
    if not re.search(version, files["Info.lua"]):
        raise ValueError("Fixture Info version differs from the pinned package")
    return files


def manifest(files: dict[str, bytes]) -> dict[str, object]:
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
    }
    return {**identity, "artifactSha2_256": digest(encoded(identity))}


def consent_template(artifact: dict[str, object]) -> dict[str, object]:
    """An invalid, ungranted template; owner must supply actual action-time consent."""
    return {
        "schemaVersion": 1,
        "owner": None,
        "artifactSha2_256": artifact["artifactSha2_256"],
        "manifestSha2_256": digest(encoded(artifact)),
        "catalogPath": None,
        "grantedAt": None,
        "expiresAt": None,
        "allowQualificationProvider": False,
        "allowSyntheticCatalogWrites": False,
        "allow200000001ByteScratch": False,
        "allowCleanup": False,
    }


def run_plan(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "artifactSha2_256": artifact["artifactSha2_256"],
        "status": "prepared_source_only_not_executed",
        "nativeQualification": "unmeasured",
        "manifestSha2_256": digest(encoded(artifact)),
        "maximumRunSeconds": 1800,
        "futureScope": {
            "qualificationOnlyProviderRegistration": True,
            "disposableCatalogBasename": "FGA-ProviderRender-Disposable.lrcat",
            "initialPhotoCount": 0,
            "qualificationServiceCount": 1,
            "generatedTiffPhotoCount": 15,
            "createdOrdinaryAlbumCount": 1,
            "maximumFaultScratchBytes": 200000001,
            "manualCatalogDisposalAfterHostCloses": True,
        },
        "cases": list(CASES),
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
            "pre_start_freeze_before_native_render",
            "actual_render_settings_and_file",
            "finite_case_terminal_results",
            "zero_network_and_production_registration",
            "cleanup_and_revocation",
        ],
    }


def verify(destination: Path, expected_digest: str | None = None) -> dict[str, object]:
    """Verify a staged tree; extra, linked, missing, and modified files all refuse."""
    destination = destination.resolve(strict=True)
    expected = {"manifest.json", "run-plan.json", "consent-template.json"} | {
        f"{BUNDLE}/{n}" for n in SOURCES
    }
    actual = set()
    for path in destination.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Staged links are not supported")
        if path.is_file():
            actual.add(path.relative_to(destination).as_posix())
    if actual != expected:
        raise ValueError("Staged artifact must have the exact closed file set")
    files = {name: (destination / BUNDLE / name).read_bytes() for name in SOURCES}
    result = manifest(files)
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
    result = manifest(files)
    (destination / BUNDLE).mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (destination / BUNDLE / name).write_bytes(data)
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
