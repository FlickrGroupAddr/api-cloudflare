"""Assemble explicit private verified inputs offline; never upload or select targets."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

from scripts.fixed_origin_restore import FIXTURE_MANIFEST_SHA256, MODULE_SHA256
from scripts.prepare_temporary_composition import FILES, SOURCE_SHA256, _plain
from scripts.temporary_composition_delta import build_delta, load_json, validate_delta

CANDIDATE = "b599ca828d2a645b686aca0354d6c8ee2c2a0250"
CANDIDATE_SHA256 = "c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36"
ENTRY = "probes/fixed-origin-composition/deploy_entrypoint.mjs"
ENTRY_SHA256 = "a1a37fde5cfbb0e1f8ed61baf1e5c15694696dd1c4ca82899d5636de56c80965"
RECEIVER_ENTRY = "probes/fixed-origin-composition/deploy_receiver_entrypoint.mjs"
RECEIVER_ENTRY_SHA256 = "1ffa040f98ba9d814459cb7094c0b17bed344afebaff491fac079c592d6e3b3e"
MAX_BYTES = 32 * 1024 * 1024
BUNDLE = r"""
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
if(process.version!=='v24.22.0')throw Error('unexpected_node');
const [repository,source,outfile,receiverOutfile]=process.argv.slice(1);
const bundler=resolve(repository,'node_modules/esbuild/lib/main.js');
const {build,version}=await import(pathToFileURL(bundler));
if(version!=='0.28.1')throw Error('unexpected_bundler');
const common={bundle:true,platform:'neutral',format:'esm',target:'es2024',
 external:['node:*','cloudflare:*'],minify:false,keepNames:true,sourcemap:false,
 logLevel:'silent',absWorkingDir:source};
await build({...common,outfile,
 entryPoints:[resolve(source,'probes/fixed-origin-composition/deploy_entrypoint.mjs')]});
await build({...common,outfile:receiverOutfile,
 entryPoints:[resolve(source,'probes/fixed-origin-composition/deploy_receiver_entrypoint.mjs')]});
"""


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise ValueError(category)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False, indent=2) + "\n").encode()


def _read(path: Path) -> bytes:
    _plain(path)
    _require(path.is_file(), "file_required")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    _require(len(raw) <= MAX_BYTES, "file_size_limit")
    return raw


def _relative(name: str) -> str:
    _require(
        type(name) is str
        and bool(name)
        and "\\" not in name
        and ":" not in name
        and not name.startswith("/")
        and all(p not in ("", ".", "..") for p in name.split("/")),
        "relative_path_required",
    )
    return name


def _private(path: Path, repository: Path) -> None:
    _plain(path)
    _require(not path.resolve().is_relative_to(repository.resolve()), "private_path_required")
    _require(
        "private-evidence" in [p.name for p in path.resolve().parents], "private_path_required"
    )


def validate_scope(scope: Any, additions: dict[str, Any]) -> None:
    _require(
        type(scope) is dict
        and set(scope)
        == {
            "run",
            "startsAt",
            "expiresAt",
            "bindingKeys",
            "canary",
        },
        "scope_fields",
    )
    scope = cast(dict[str, Any], scope)
    _require(
        type(scope["canary"]) is str and bool(re.fullmatch("[a-f0-9]{64}", scope["canary"])),
        "scope_canary",
    )
    _require(
        type(scope["run"]) is str
        and bool(re.fullmatch("[a-f0-9]{32}", scope["run"]))
        and scope["run"] == additions["run"],
        "scope_run",
    )
    _require(
        type(scope["startsAt"]) is int
        and type(scope["expiresAt"]) is int
        and 0 <= scope["startsAt"] < scope["expiresAt"] <= 2**53 - 1
        and scope["expiresAt"] - scope["startsAt"] == 600_000,
        "scope_lifetime",
    )
    keys: Any = scope["bindingKeys"]
    _require(
        type(keys) is dict
        and set(keys)
        == {
            "syntheticDb",
            "quotaDb",
            "receiver",
            "capability",
        }
        and all(type(v) is str and v for v in keys.values())
        and len(set(keys.values())) == 4,
        "scope_binding_keys",
    )
    keys = cast(dict[str, str], keys)
    rows = {row["name"]: row for row in additions["bindings"]}
    _require(set(rows) == set(keys.values()), "scope_binding_inventory")
    for role, kind in (
        ("syntheticDb", "d1"),
        ("quotaDb", "d1"),
        ("receiver", "service"),
        ("capability", "plain_text"),
    ):
        _require(rows[keys[role]]["type"] == kind, "scope_binding_type")
    _require(additions["receiver"]["binding"] == keys["receiver"], "scope_receiver")
    _require(
        bool(re.fullmatch("[a-f0-9]{64}", rows[keys["capability"]].get("text", ""))),
        "scope_capability",
    )


def _fixture(fixture: Path) -> dict[str, bytes]:
    manifest_raw = _read(fixture / "manifest.json")
    _require(digest(manifest_raw) == FIXTURE_MANIFEST_SHA256, "fixture_manifest_pin")
    manifest = json.loads(manifest_raw)
    _require(manifest["candidateCommit"] == CANDIDATE, "candidate_commit_pin")
    contents = {
        "captured.mjs": _read(fixture / "captured.mjs"),
        "candidate.mjs": _read(fixture / "candidate.mjs"),
        "fixture-manifest.json": manifest_raw,
    }
    _require(digest(contents["captured.mjs"]) == MODULE_SHA256, "captured_module_pin")
    _require(digest(contents["candidate.mjs"]) == CANDIDATE_SHA256, "candidate_module_pin")
    rows = manifest["candidateSourceFiles"]
    _require(type(rows) is dict and bool(rows), "candidate_sources_required")
    rows = cast(dict[str, str], rows)
    _require(any(name.startswith("migrations/") for name in rows), "candidate_migrations_required")
    for name, expected in rows.items():
        raw = _read(fixture / "candidate" / _relative(name))
        _require(digest(raw) == expected, "candidate_source_pin")
        contents["candidate/" + name] = raw
    return contents


def build(
    repository: Path,
    fixture: Path,
    baseline: dict[str, Any],
    additions: dict[str, Any],
    scope: dict[str, Any],
    output: Path,
    node: Path,
) -> dict[str, Any]:
    """Build a fresh private Worker and exact preservation delta from supplied inputs."""
    _plain(repository)
    _private(fixture, repository)
    _private(output, repository)
    _require(not output.exists(), "fresh_destination_required")
    _require("moduleSha256" not in additions, "computed_module_digest_required")
    _require("scope" not in additions, "separate_scope_required")
    _require("moduleSha256" not in additions["receiver"], "computed_receiver_digest_required")
    _require(baseline.get("moduleSha256") == MODULE_SHA256, "baseline_module_pin")
    contents = _fixture(fixture)
    for name in FILES:
        raw = _read(repository / name)
        _require(digest(raw) == SOURCE_SHA256[name], "composition_source_pin")
        contents[name] = raw
    contents[ENTRY] = _read(repository / ENTRY)
    _require(digest(contents[ENTRY]) == ENTRY_SHA256, "deployment_entrypoint_pin")
    contents[RECEIVER_ENTRY] = _read(repository / RECEIVER_ENTRY)
    _require(digest(contents[RECEIVER_ENTRY]) == RECEIVER_ENTRY_SHA256, "receiver_entrypoint_pin")
    validate_scope(scope, additions)
    contents["scope.json"] = canonical(scope)
    # Validate all configuration input before writing or invoking the local bundler.
    complete = copy.deepcopy(additions)
    complete["scope"] = copy.deepcopy(scope)
    complete["moduleSha256"] = "0" * 64
    complete["receiver"]["moduleSha256"] = "0" * 64
    build_delta(baseline, complete)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in contents.items():
        target = output / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    result = subprocess.run(
        [
            str(node),
            "--input-type=module",
            "-e",
            BUNDLE,
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
    module = _read(output / "worker.mjs")
    receiver_module = _read(output / "receiver.mjs")
    complete["moduleSha256"] = digest(module)
    complete["receiver"]["moduleSha256"] = digest(receiver_module)
    delta = build_delta(baseline, complete)
    (output / "configuration-delta.json").write_bytes(canonical(delta))
    (output / "temporary-configuration.json").write_bytes(canonical(delta["temporary"]))
    (output / "restore.json").write_bytes(canonical(delta["restore"]))
    (output / "receiver-configuration.json").write_bytes(canonical(delta["additions"]["receiver"]))
    files = {
        p.relative_to(output).as_posix(): digest(_read(p)) for p in output.rglob("*") if p.is_file()
    }
    manifest = {
        "schemaVersion": 1,
        "kind": "offline_assembled_temporary_composition",
        "candidateCommit": CANDIDATE,
        "capturedModuleSha256": MODULE_SHA256,
        "candidateModuleSha256": CANDIDATE_SHA256,
        "moduleSha256": digest(module),
        "receiverModuleSha256": digest(receiver_module),
        "scope": copy.deepcopy(scope),
        "files": files,
        "configurationDeltaSha256": files["configuration-delta.json"],
        "ordinaryRequestIdentityPreserved": True,
        "ordinaryEnvironmentIdentityPreserved": True,
        "namedExportsPreserved": True,
        "assembled": True,
        "deploymentAllowed": False,
        "providerRestorationVerified": False,
        "productionStateVerified": False,
        "nativeQualified": False,
        "transportQualified": False,
        "tools": {"node": "24.22.0", "esbuild": "0.28.1"},
    }
    raw_manifest = canonical(manifest)
    (output / "manifest.json").write_bytes(raw_manifest)
    verify(output, digest(raw_manifest))
    return manifest


def verify(output: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    """Verify against the caller-retained manifest pin, not mutable self-attestation."""
    _plain(output)
    raw = _read(output / "manifest.json")
    _require(digest(raw) == expected_manifest_sha256, "manifest_pin")
    manifest = json.loads(raw)
    files = manifest["files"]
    _require(type(files) is dict, "manifest_inventory")
    observed = set()
    for path in output.rglob("*"):
        _plain(path)
        if path.is_file():
            observed.add(path.relative_to(output).as_posix())
    _require(observed == set(files) | {"manifest.json"}, "packet_inventory")
    for name, expected in files.items():
        _require(digest(_read(output / _relative(name))) == expected, "packet_file_pin")
    delta = json.loads(_read(output / "configuration-delta.json"))
    validate_delta(delta)
    _require(
        _read(output / "temporary-configuration.json") == canonical(delta["temporary"])
        and _read(output / "restore.json") == canonical(delta["restore"]),
        "config_projection",
    )
    _require(
        _read(output / "receiver-configuration.json") == canonical(delta["additions"]["receiver"]),
        "receiver_config_projection",
    )
    _require(
        digest(_read(output / "receiver.mjs"))
        == delta["additions"]["receiver"]["moduleSha256"]
        == manifest["receiverModuleSha256"],
        "receiver_module_delta_pin",
    )
    _require(
        digest(_read(output / "worker.mjs"))
        == delta["additions"]["moduleSha256"]
        == manifest["moduleSha256"],
        "module_delta_pin",
    )
    scope = json.loads(_read(output / "source/scope.json"))
    validate_scope(scope, delta["additions"])
    _require(canonical(scope) == canonical(manifest["scope"]), "scope_manifest_pin")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-sha256")
    for name in ("repository", "fixture", "baseline", "additions", "scope", "node"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "verify":
            _require(args.manifest_sha256 is not None, "manifest_pin_required")
            verify(args.output, args.manifest_sha256)
        else:
            _require(
                all(
                    getattr(args, key) is not None
                    for key in ("repository", "fixture", "baseline", "additions", "scope", "node")
                ),
                "build_inputs",
            )
            for path in (args.baseline, args.additions, args.scope):
                _private(path, args.repository)
            build(
                args.repository,
                args.fixture,
                load_json(args.baseline),
                load_json(args.additions),
                load_json(args.scope),
                args.output,
                args.node,
            )
    except ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired:
        print("NO-GO: offline assembly refused")
        return 2
    print(
        "Offline assembled packet verified; live qualification and deployment remain unauthorized"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
