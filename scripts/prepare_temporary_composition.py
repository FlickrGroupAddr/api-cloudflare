"""Pin the exact offline composition closure without reading a private capture.

This source-safe packet has no deployment config, executable provider adapter or
captured module bytes. It cannot claim an assembled deployable candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.fixed_origin_restore import INDEX_SHA256, MODULE_SHA256

FILES = (
    "probes/fixed-origin-composition/entrypoint.mjs",
    "probes/fixed-origin-lifecycle/composition.mjs",
    "probes/fixed-origin-lifecycle/quota_receiver.mjs",
    "probes/fixed-origin-lifecycle/handler_cases.mjs",
    "probes/fixed-origin-isolation/wrapper.mjs",
    "probes/fixed-origin-isolation/edge_faults.mjs",
    "probes/fixed-origin-isolation/edge_png.mjs",
)
MAX_BYTES = 2 * 1024 * 1024
MISSING_PROOFS = (
    "independently_verified_capture_bytes_and_retained_version_identity",
    "immutable_candidate_module_and_migration_closure",
    "exact_captured_binding_names_ids_and_runtime_settings",
    "complete_temporary_configuration_delta_and_receiver_target",
    "current_gate_scope_and_background_quiescence",
    "effective_client_path_method_authority",
    "ordered_execution_program_authority",
    "independent_restore_and_production_preservation_receipts",
)


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise ValueError(category)


def _plain(path: Path) -> None:
    for node in (path, *path.parents):
        _require(not node.is_symlink() and not node.is_junction(), "link_not_allowed")


def _read(path: Path) -> bytes:
    _plain(path)
    _require(path.is_file(), "source_file_required")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    _require(len(raw) <= MAX_BYTES, "source_size_limit")
    return raw


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _manifest(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "offline_source_safe_temporary_composition",
        "entrypoint": FILES[0],
        "export": "createTemporaryComposition",
        "defaultWorkerExport": False,
        "files": rows,
        "captured": {
            "mainModule": "worker.js",
            "moduleSha256": MODULE_SHA256,
            "captureIndexSha256": INDEX_SHA256,
            "retainedVersionIdentity": None,
            "retainedVersionWeight": 100,
            "ordinaryDispatch": "captured.default.fetch(request, productionEnv)",
            "requestIdentityPreserved": True,
            "environmentIdentityPreserved": True,
        },
        "configuration": {
            "source": "constructor_injection_only",
            "receiverInterface": "receiverBinding.fetch(Request)",
            "receiverBindingKey": None,
            "providerTarget": None,
            "capturedBindingDeltaVerified": False,
            "intakeEnabled": False,
            "dispatchEnabled": False,
        },
        "existingLimits": {"fga": 96, "receiver": 16, "lifetimeMs": 1200000},
        "authority": "offline_preparation_only_no_proposed_amendment_assumed",
        "missingProofs": list(MISSING_PROOFS),
        "deployReady": False,
        "deploymentAllowed": False,
        "providerRestorationVerified": False,
        "productionStateVerified": False,
    }


def prepare(repository: Path, output: Path) -> dict[str, Any]:
    """Copy reviewed public source only; a private assembled candidate is absent."""
    _plain(repository)
    _plain(output)
    _require(not output.exists(), "fresh_destination_required")
    _require(
        repository.resolve() not in output.resolve().parents,
        "destination_outside_repository_required",
    )
    contents = {name: _read(repository / name) for name in FILES}
    for name, raw in contents.items():
        _require(_digest(raw) == SOURCE_SHA256[name], "source_pin_mismatch")
    rows = {name: {"sha256": _digest(raw), "bytes": len(raw)} for name, raw in contents.items()}
    manifest = _manifest(rows)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in contents.items():
        target = output / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return verify(output)


def verify(output: Path) -> dict[str, Any]:
    """Verify a bounded exact inventory against source pins, never self-attestation."""
    _plain(output)
    expected_files = {"manifest.json", *("source/" + name for name in FILES)}
    expected_dirs = set()
    for name in expected_files:
        expected_dirs.update(
            str(parent).replace("\\", "/") for parent in Path(name).parents if str(parent) != "."
        )
    observed_files, observed_dirs = set(), set()
    for path in output.rglob("*"):
        _plain(path)
        relative = path.relative_to(output).as_posix()
        if path.is_dir():
            observed_dirs.add(relative)
        else:
            observed_files.add(relative)
    _require(
        observed_files == expected_files and observed_dirs == expected_dirs,
        "packet_inventory_mismatch",
    )
    rows = {}
    for name in FILES:
        raw = _read(output / "source" / name)
        _require(_digest(raw) == SOURCE_SHA256[name], "source_pin_mismatch")
        rows[name] = {"sha256": _digest(raw), "bytes": len(raw)}
    expected = _manifest(rows)
    try:
        manifest = json.loads(_read(output / "manifest.json"))
    except ValueError, UnicodeError:
        raise ValueError("manifest_invalid") from None
    # Canonical equality distinguishes booleans from integers and rejects extras.
    _require(
        json.dumps(manifest, sort_keys=True, allow_nan=False)
        == json.dumps(expected, sort_keys=True),
        "manifest_mismatch",
    )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "verify"))
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            _require(args.repository is not None, "repository_required")
            prepare(args.repository, args.output)
        else:
            verify(args.output)
    except ValueError, OSError:
        print("NO-GO: offline composition preparation refused")
        return 2
    print("NO-GO: exact offline source closure verified; assembled candidate absent")
    return 0


# Public source hashes are fixed at review; input manifests cannot replace them.
SOURCE_SHA256: dict[str, str] = {
    "probes/fixed-origin-composition/entrypoint.mjs": (
        "1f2c5750dafb2c9953e3d40dffe6f0eb3523dd20517bc357b45e2345ae1522c8"
    ),
    "probes/fixed-origin-lifecycle/composition.mjs": (
        "95f476064fc41ada338a8ce80d2a8fe7b135f4a9174248fa697b3fdb33e55cf8"
    ),
    "probes/fixed-origin-lifecycle/quota_receiver.mjs": (
        "6293ff60e22300cf1082d9c7243d541f7079348735f7fe16f77fbcd087dcf583"
    ),
    "probes/fixed-origin-lifecycle/handler_cases.mjs": (
        "cb41173c4fa6b1fcbfb7f8fa2a98b4669568ef9c89d10586438f5796cf916ebb"
    ),
    "probes/fixed-origin-isolation/wrapper.mjs": (
        "a894a7f94a3c18dc094057109eab80319cc3b9ceaaef430270ab89d939617ba9"
    ),
    "probes/fixed-origin-isolation/edge_faults.mjs": (
        "a48e008298cd3b68329bb6577a638657baf84f2f78b886eacab2c1b281d4ffa1"
    ),
    "probes/fixed-origin-isolation/edge_png.mjs": (
        "414c4accb8b726af709e6fbd0d5e754469a76e58c44b91942292398d423ca49e"
    ),
}

if __name__ == "__main__":
    raise SystemExit(main())
