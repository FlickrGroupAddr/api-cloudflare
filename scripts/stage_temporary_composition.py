"""Stage immutable composition bytes, then bind supplied receipts offline; no provider I/O.

Receipt digests are independently retained inputs, not authentication. Neither phase
establishes current production preservation, provider provenance or live authority.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from scripts import build_temporary_composition as builder
from scripts.synthetic_restoration_packet import digest as object_digest
from scripts.temporary_composition_delta import build_delta, load_json, validate_delta

CLAIM = "finalization-claim.json"
GATES = {
    "deploymentAllowed": False,
    "providerProvenanceVerified": False,
    "productionStateVerified": False,
    "currentBaselineVerified": False,
    "nativeQualified": False,
    "transportQualified": False,
}


def _require(test: bool, reason: str) -> None:
    builder._require(test, reason)


def _keys(value: Any, keys: set[str], reason: str) -> None:
    _require(type(value) is dict and set(value) == keys, reason)


def _hash(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def validate_scope(scope: Any) -> None:
    _keys(scope, {"run", "startsAt", "expiresAt", "bindingKeys", "canary"}, "scope_fields")
    _require(
        type(scope["run"]) is str and re.fullmatch(r"[a-f0-9]{32}", scope["run"]) is not None,
        "scope_run",
    )
    _require(_hash(scope["canary"]), "scope_canary")
    _require(
        type(scope["startsAt"]) is int
        and type(scope["expiresAt"]) is int
        and 0 <= scope["startsAt"] <= 2**53 - 1_200_000
        and scope["expiresAt"] == scope["startsAt"] + 600_000,
        "scope_lifetime",
    )
    _keys(scope["bindingKeys"], {"syntheticDb", "quotaDb", "receiver", "capability"}, "scope_roles")
    names = list(scope["bindingKeys"].values())
    _require(
        all(
            type(v) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", v) is not None for v in names
        )
        and len(set(names)) == 4,
        "scope_names",
    )


def _inventory(output: Path, *, allow_claim: bool = False) -> dict[str, str]:
    rows = {}
    for path in output.rglob("*"):
        builder._plain(path)
        if path.is_file():
            name = path.relative_to(output).as_posix()
            if name != "manifest.json" and not (allow_claim and name == CLAIM):
                rows[name] = builder.digest(builder._read(path))
    return rows


def _write_manifest(output: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["files"] = _inventory(output)
    (output / "manifest.json").write_bytes(builder.canonical(manifest))
    return manifest


def stage(
    repository: Path, fixture: Path, scope: dict[str, Any], output: Path, node: Path
) -> dict[str, Any]:
    """Compile from pinned original/candidate sources and scope, without provider IDs."""
    builder._plain(repository)
    builder._private(fixture, repository)
    builder._private(output, repository)
    _require(not output.exists(), "fresh_destination_required")
    _require(
        not output.resolve().is_relative_to(fixture.resolve())
        and not fixture.resolve().is_relative_to(output.resolve()),
        "fixture_output_overlap",
    )
    validate_scope(scope)
    contents = builder._fixture(fixture)
    for name in builder.FILES:
        raw = builder._read(repository / name)
        _require(builder.digest(raw) == builder.SOURCE_SHA256[name], "composition_source_pin")
        contents[name] = raw
    for name, pin in (
        (builder.ENTRY, builder.ENTRY_SHA256),
        (builder.RECEIVER_ENTRY, builder.RECEIVER_ENTRY_SHA256),
    ):
        raw = builder._read(repository / name)
        _require(builder.digest(raw) == pin, "entrypoint_pin")
        contents[name] = raw
    contents["scope.json"] = builder.canonical(scope)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in contents.items():
        path = output / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    result = subprocess.run(
        [
            str(node),
            "--input-type=module",
            "-e",
            builder.BUNDLE,
            str(repository.resolve()),
            str((output / "source").resolve()),
            str((output / "worker.mjs").resolve()),
            str((output / "receiver.mjs").resolve()),
        ],
        cwd=repository,
        capture_output=True,
        timeout=120,
        check=False,
    )
    _require(result.returncode == 0, "local_bundle_refused")
    manifest = {
        "schemaVersion": 1,
        "kind": "offline_unbound_temporary_composition",
        "scope": copy.deepcopy(scope),
        "candidateCommit": builder.CANDIDATE,
        "capturedModuleSha256": builder.digest(contents["captured.mjs"]),
        "candidateModuleSha256": builder.digest(contents["candidate.mjs"]),
        "moduleSha256": builder.digest(builder._read(output / "worker.mjs")),
        "receiverModuleSha256": builder.digest(builder._read(output / "receiver.mjs")),
        "tools": {"node": "24.22.0", "esbuild": "0.28.1"},
        "identityBound": False,
        **GATES,
    }
    _write_manifest(output, manifest)
    verify_stage(output, builder.digest(builder._read(output / "manifest.json")))
    return manifest


def _verify_inventory(output: Path, pin: str, *, allow_claim: bool = False) -> dict[str, Any]:
    builder._plain(output)
    raw = builder._read(output / "manifest.json")
    _require(_hash(pin) and builder.digest(raw) == pin, "manifest_pin")
    manifest = load_json(output / "manifest.json")
    _require(
        manifest["files"] == _inventory(output, allow_claim=allow_claim),
        "packet_inventory_or_file_pin",
    )
    for key, value in GATES.items():
        _require(manifest[key] is value, "live_gate")
    return manifest


def verify_stage(output: Path, manifest_sha256: str) -> dict[str, Any]:
    manifest = _verify_inventory(output, manifest_sha256, allow_claim=True)
    _require(
        manifest["schemaVersion"] == 1
        and manifest["kind"] == "offline_unbound_temporary_composition"
        and manifest["identityBound"] is False,
        "stage_kind",
    )
    validate_scope(manifest["scope"])
    _require(
        builder._read(output / "source/scope.json") == builder.canonical(manifest["scope"]),
        "scope_pin",
    )
    for name, field in (
        ("worker.mjs", "moduleSha256"),
        ("receiver.mjs", "receiverModuleSha256"),
        ("source/captured.mjs", "capturedModuleSha256"),
        ("source/candidate.mjs", "candidateModuleSha256"),
    ):
        _require(builder.digest(builder._read(output / name)) == manifest[field], "module_pin")
    return manifest


def validate_evidence(
    evidence: Any, pin: str, stage_pin: str, manifest: dict[str, Any], delta: dict[str, Any]
) -> None:
    """Check supplied evidence relationships; a digest cannot authenticate its author."""
    _require(_hash(pin) and object_digest(evidence) == pin, "independent_evidence_pin")
    _keys(
        evidence,
        {
            "schemaVersion",
            "kind",
            "stageManifestSha256",
            "baseline",
            "resources",
            "receiver",
            "upload",
            "readback",
        },
        "evidence_fields",
    )
    _require(
        type(evidence["schemaVersion"]) is int
        and evidence["schemaVersion"] == 1
        and evidence["kind"] == "supplied_offline_composition_evidence"
        and evidence["stageManifestSha256"] == stage_pin,
        "evidence_stage",
    )
    baseline, additions = delta["baseline"], delta["additions"]
    proof = evidence["baseline"]
    _keys(
        proof,
        {
            "baselineSha256",
            "productionStateSha256",
            "captureReceiptSha256",
            "consistencyReceiptSha256",
            "pausedGatesReceiptSha256",
            "writerReceiptSha256",
        },
        "baseline_evidence_fields",
    )
    _require(
        proof["baselineSha256"] == object_digest(baseline)
        and proof["productionStateSha256"] == object_digest(baseline["productionState"])
        and all(_hash(v) for v in proof.values()),
        "baseline_evidence_pin",
    )
    resources = evidence["resources"]
    _require(type(resources) is list and len(resources) == 3, "resource_evidence_inventory")
    for row, resource in zip(resources, additions["resources"], strict=True):
        _keys(
            row,
            {
                "resource",
                "creationReceiptSha256",
                "initializationReceiptSha256",
                "cleanupAuthoritySha256",
            },
            "resource_evidence_fields",
        )
        _require(
            row["resource"] == resource and all(_hash(row[k]) for k in row if k != "resource"),
            "resource_evidence_pin",
        )
    receiver = evidence["receiver"]
    _keys(
        receiver,
        {
            "target",
            "run",
            "moduleSha256",
            "configurationSha256",
            "versionId",
            "deploymentReceiptSha256",
            "readbackReceiptSha256",
        },
        "receiver_evidence_fields",
    )
    _require(
        receiver["target"] == additions["receiver"]["target"]
        and receiver["run"] == additions["run"]
        and receiver["moduleSha256"] == manifest["receiverModuleSha256"]
        and receiver["configurationSha256"] == object_digest(additions["receiver"]["configuration"])
        and type(receiver["versionId"]) is str
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", receiver["versionId"]) is not None
        and _hash(receiver["deploymentReceiptSha256"])
        and _hash(receiver["readbackReceiptSha256"]),
        "receiver_evidence_pin",
    )
    operations = []
    for role in ("upload", "readback"):
        row = evidence[role]
        _keys(
            row,
            {
                "operationId",
                "status",
                "target",
                "run",
                "versionId",
                "moduleSha256",
                "configurationSha256",
                "stageManifestSha256",
                "receiptSha256",
            },
            "version_evidence_fields",
        )
        _require(
            row["status"] == "acknowledged"
            and row["target"] == baseline["target"]
            and row["run"] == additions["run"]
            and row["versionId"] == additions["temporaryVersion"]
            and row["moduleSha256"] == manifest["moduleSha256"]
            and row["configurationSha256"] == object_digest(delta["temporary"]["configuration"])
            and row["stageManifestSha256"] == stage_pin
            and _hash(row["receiptSha256"])
            and type(row["operationId"]) is str
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", row["operationId"]) is not None,
            "version_evidence_pin",
        )
        operations.append(row["operationId"])
    _require(
        len(set(operations)) == 2
        and evidence["upload"]["receiptSha256"] != evidence["readback"]["receiptSha256"],
        "independent_readback_required",
    )


def finalize(
    repository: Path,
    staged: Path,
    stage_manifest_sha256: str,
    baseline: dict[str, Any],
    additions: dict[str, Any],
    evidence: dict[str, Any],
    evidence_sha256: str,
    output: Path,
) -> dict[str, Any]:
    """Bind acknowledged supplied identities once; copy exact bytes without bundling."""
    builder._private(staged, repository)
    builder._private(output, repository)
    _require(
        not output.exists()
        and not output.resolve().is_relative_to(staged.resolve())
        and not staged.resolve().is_relative_to(output.resolve()),
        "fresh_separate_destination_required",
    )
    manifest = verify_stage(staged, stage_manifest_sha256)
    _require(
        baseline.get("moduleSha256") == manifest["capturedModuleSha256"], "baseline_module_pin"
    )
    _require(
        "moduleSha256" not in additions
        and "scope" not in additions
        and "moduleSha256" not in additions["receiver"],
        "computed_fields_required",
    )
    complete = copy.deepcopy(additions)
    complete.update(scope=copy.deepcopy(manifest["scope"]), moduleSha256=manifest["moduleSha256"])
    complete["receiver"]["moduleSha256"] = manifest["receiverModuleSha256"]
    builder.validate_scope(manifest["scope"], complete)
    delta = build_delta(baseline, complete)
    validate_evidence(evidence, evidence_sha256, stage_manifest_sha256, manifest, delta)
    # Local one-shot latch only: no claim of distributed/provider replay prevention.
    claim = {
        "stageManifestSha256": stage_manifest_sha256,
        "evidenceSha256": evidence_sha256,
        "output": str(output.resolve()),
    }
    with (staged / CLAIM).open("xb") as stream:
        stream.write(builder.canonical(claim))
    output.mkdir(parents=True, exist_ok=False)
    for name in manifest["files"]:
        target = output / builder._relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(builder._read(staged / builder._relative(name)))
    for name, value in (
        ("configuration-delta.json", delta),
        ("temporary-configuration.json", delta["temporary"]),
        ("restore.json", delta["restore"]),
        ("receiver-configuration.json", delta["additions"]["receiver"]),
        ("supplied-evidence.json", evidence),
        ("stage-manifest.json", manifest),
    ):
        (output / name).write_bytes(builder.canonical(value))
    final = {
        "schemaVersion": 1,
        "kind": "offline_bound_temporary_composition",
        "identityBound": True,
        "stageManifestSha256": stage_manifest_sha256,
        "evidenceSha256": evidence_sha256,
        "moduleSha256": manifest["moduleSha256"],
        "receiverModuleSha256": manifest["receiverModuleSha256"],
        "suppliedEvidenceConsistencyVerified": True,
        **GATES,
    }
    _write_manifest(output, final)
    verify_final(output, builder.digest(builder._read(output / "manifest.json")))
    return final


def verify_final(output: Path, manifest_sha256: str) -> dict[str, Any]:
    final = _verify_inventory(output, manifest_sha256)
    _require(
        final["schemaVersion"] == 1
        and final["kind"] == "offline_bound_temporary_composition"
        and final["identityBound"] is True
        and final["suppliedEvidenceConsistencyVerified"] is True,
        "final_kind",
    )
    staged = load_json(output / "stage-manifest.json")
    _require(
        builder.digest(builder._read(output / "stage-manifest.json"))
        == final["stageManifestSha256"],
        "stage_manifest_pin",
    )
    for name, pin in staged["files"].items():
        _require(
            builder.digest(builder._read(output / builder._relative(name))) == pin,
            "staged_bytes_changed",
        )
    delta = load_json(output / "configuration-delta.json")
    validate_delta(delta)
    for name, value in (
        ("temporary-configuration.json", delta["temporary"]),
        ("restore.json", delta["restore"]),
        ("receiver-configuration.json", delta["additions"]["receiver"]),
    ):
        _require(
            builder._read(output / name) == builder.canonical(value), "configuration_projection"
        )
    _require(
        delta["additions"]["moduleSha256"] == staged["moduleSha256"] == final["moduleSha256"]
        and delta["additions"]["receiver"]["moduleSha256"]
        == staged["receiverModuleSha256"]
        == final["receiverModuleSha256"]
        and delta["additions"]["scope"] == staged["scope"]
        and delta["baseline"]["moduleSha256"] == staged["capturedModuleSha256"],
        "final_stage_binding",
    )
    validate_evidence(
        load_json(output / "supplied-evidence.json"),
        final["evidenceSha256"],
        final["stageManifestSha256"],
        staged,
        delta,
    )
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("stage", "finalize", "verify-stage", "verify-final"))
    parser.add_argument("--output", type=Path, required=True)
    for name in (
        "repository",
        "fixture",
        "scope",
        "node",
        "staged",
        "baseline",
        "additions",
        "evidence",
    ):
        parser.add_argument("--" + name, type=Path)
    for name in ("manifest-sha256", "stage-manifest-sha256", "evidence-sha256"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    try:
        if args.operation.startswith("verify-"):
            _require(args.manifest_sha256 is not None, "manifest_pin_required")
            (verify_stage if args.operation == "verify-stage" else verify_final)(
                args.output, args.manifest_sha256
            )
        elif args.operation == "stage":
            _require(
                all(
                    getattr(args, name) is not None
                    for name in ("repository", "fixture", "scope", "node")
                ),
                "stage_inputs",
            )
            builder._private(args.scope, args.repository)
            stage(args.repository, args.fixture, load_json(args.scope), args.output, args.node)
        else:
            _require(
                all(
                    getattr(args, name) is not None
                    for name in (
                        "repository",
                        "staged",
                        "baseline",
                        "additions",
                        "evidence",
                        "stage_manifest_sha256",
                        "evidence_sha256",
                    )
                ),
                "finalize_inputs",
            )
            for path in (args.baseline, args.additions, args.evidence):
                builder._private(path, args.repository)
            finalize(
                args.repository,
                args.staged,
                args.stage_manifest_sha256,
                load_json(args.baseline),
                load_json(args.additions),
                load_json(args.evidence),
                args.evidence_sha256,
                args.output,
            )
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ):
        print("NO-GO: offline staging/binding refused")
        return 2
    print("Offline packet consistent; live/current/provider qualification remains NO-GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
