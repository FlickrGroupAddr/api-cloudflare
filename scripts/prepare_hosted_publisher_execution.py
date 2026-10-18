"""Prepare a byte-bound offline publisher packet; never execute a provider action.

Scope must be independently supplied. This tool supplies no account, endpoint,
schedule, authorization, credential, creation receipt or provider-state default.
Its output remains NO-GO because the reviewed concrete runtime caller is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

if __package__:
    from scripts import hosted_publisher_operator_plan as boundary
else:
    import hosted_publisher_operator_plan as boundary

PLAN_FILES = tuple(
    sorted((*boundary.REQUIRED_OPERATOR_FILES, "scripts/prepare_hosted_publisher_execution.py"))
)
SOURCE_FILES = tuple(sorted((*PLAN_FILES, "pyproject.toml", "uv.lock")))
SCOPE_FIELDS = set(boundary.OperatorPlan.__dataclass_fields__) - {"pins", "source_files"}
BLOCKERS = (
    "concrete_beta_transport_refused_by_reviewed_provider",
    "reviewed_runtime_caller_and_private_credential_delivery_absent",
    "independent_private_scope_grant_and_isolation_review_required",
    "exact_human_action_and_cleanup_decisions_absent",
)
PACKET_FILES = {"plan.json", "manifest.json"} | {"source/" + n for n in SOURCE_FILES}


def _encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _read_json(raw: bytes) -> dict[str, Any]:
    if len(raw) > 262144:
        raise ValueError("Input exceeds bounded packet limit")
    value = json.loads(raw, object_pairs_hook=boundary._no_duplicates)
    if type(value) is not dict:
        raise ValueError("Closed JSON object required")
    return value


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "-c",
            "core.excludesFile=.git/info/exclude",
            "-C",
            str(root),
            *arguments,
        ],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _source_identity(root: Path, expected: str, files: dict[str, bytes]) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", expected) or _git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Exact independently reviewed source revision required")
    entries = {}
    for line in _git(root, "ls-tree", "-r", expected, "--", *SOURCE_FILES).splitlines():
        metadata, name = line.split("\t", 1)
        mode, kind, object_id = metadata.split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError("Source closure is not regular committed files")
        entries[name] = object_id
    if set(entries) != set(files):
        raise ValueError("Source closure contains missing or uncommitted files")
    for name, data in files.items():
        # Git's object format requires this library spelling for SHA1-160.
        object_id = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if entries[name] != object_id:
            raise ValueError("Source closure differs from reviewed commit")


def _source_bytes(root: Path) -> dict[str, bytes]:
    return {name: boundary._regular_file(root, name).read_bytes() for name in SOURCE_FILES}


def _plan(scope_raw: bytes, files: dict[str, bytes]) -> boundary.OperatorPlan:
    scope = _read_json(scope_raw)
    if set(scope) != SCOPE_FIELDS:
        raise ValueError("Exact independently supplied scope required; no pins or credentials")
    value = {
        **scope,
        "pins": dict(boundary.CANDIDATE_PINS),
        "source_files": {name: boundary.sha2_256(files[name]) for name in PLAN_FILES},
    }
    plan = boundary.load_plan(boundary.encoded(value))
    # The operator's provider has a narrower intended-name boundary than schema 2.
    for case in plan.cases:
        if any(
            re.fullmatch(r"fga-publisher-[a-z0-9-]{1,48}", name) is None
            for name in (case.worker_name, case.d1_name)
        ):
            raise ValueError("Intended names do not fit the actual provider boundary")
    return plan


def build_plan(
    scope_raw: bytes, current_root: Path, expected_source_head: str
) -> boundary.OperatorPlan:
    """Bind complete supplied scope to committed bytes without reading a secret."""
    files = _source_bytes(current_root)
    _source_identity(current_root, expected_source_head, files)
    plan = _plan(scope_raw, files)
    boundary.validate_current_inputs(plan, current_root)
    return plan


def _plan_document(plan: boundary.OperatorPlan) -> dict[str, Any]:
    # The canonical encoder already used by schema 2 takes ordinary JSON values.
    from dataclasses import asdict

    return {
        **{name: getattr(plan, name) for name in SCOPE_FIELDS - {"cases", "budgets"}},
        "cases": [asdict(case) for case in plan.cases],
        "budgets": asdict(plan.budgets),
        "pins": dict(plan.pins),
        "source_files": dict(plan.source_files),
    }


def prepare(
    destination: Path,
    scope_raw: bytes,
    source_root: Path,
    bundle_path: Path,
    current_root: Path,
    expected_source_head: str,
) -> dict[str, Any]:
    """Write a new private packet only after committed/candidate validation.

    No old candidate bytes are copied or rebuilt. Retained identity validation
    uses the existing 0121 boundary. No consent, grant or token is accepted here.
    """
    boundary._refuse_links(destination)
    if destination.exists():
        raise ValueError("Use a new private packet directory")
    destination = destination.parent.resolve(strict=True) / destination.name
    for protected in (current_root, source_root, bundle_path.parent):
        if destination.is_relative_to(protected.resolve(strict=True)):
            raise ValueError("Packet must be outside source and retained candidate roots")
    files = _source_bytes(current_root)
    _source_identity(current_root, expected_source_head, files)
    plan = _plan(scope_raw, files)
    boundary.validate_current_inputs(plan, current_root)
    boundary.validate_artifact(source_root, bundle_path)
    payload = {"source/" + name: data for name, data in files.items()}
    payload["plan.json"] = _encoded(_plan_document(plan))
    identity = {
        "schema_version": 1,
        "status": "NO-GO",
        "live_execution_allowed": False,
        "provider_qualified": False,
        "native_execution_allowed": False,
        "source_commit": expected_source_head,
        "source_commit_exact": True,
        "candidate_pins": dict(boundary.CANDIDATE_PINS),
        "plan_digest": plan.digest,
        "blockers": list(BLOCKERS),
        "files": {
            name: {"bytes": len(data), "sha2_256": boundary.sha2_256(data)}
            for name, data in sorted(payload.items())
        },
    }
    manifest = {**identity, "packet_sha2_256": boundary.sha2_256(_encoded(identity))}
    # Verify the snapshot, not a second potentially changed source read.
    for name, data in files.items():
        if boundary.sha2_256(data) != boundary.sha2_256(
            boundary._regular_file(current_root, name).read_bytes()
        ):
            raise ValueError("Source changed during preparation")
    destination.mkdir()
    for name, data in payload.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (destination / "manifest.json").write_bytes(_encoded(manifest))
    return verify(destination, manifest["packet_sha2_256"])


def verify(destination: Path, expected_packet_digest: str) -> dict[str, Any]:
    """Rehash an offline packet against a separately retained review digest."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_packet_digest):
        raise ValueError("Independent packet digest required")
    boundary._refuse_links(destination)
    actual = set()
    for path in destination.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked staged content refused")
        if path.is_file():
            actual.add(path.relative_to(destination).as_posix())
    if actual != PACKET_FILES:
        raise ValueError("Packet file set changed")
    raw = boundary._regular_file(destination, "manifest.json").read_bytes()
    manifest = _read_json(raw)
    expected_fields = {
        "schema_version",
        "status",
        "live_execution_allowed",
        "provider_qualified",
        "native_execution_allowed",
        "source_commit",
        "source_commit_exact",
        "candidate_pins",
        "plan_digest",
        "blockers",
        "files",
        "packet_sha2_256",
    }
    if set(manifest) != expected_fields or type(manifest["files"]) is not dict:
        raise ValueError("Closed offline manifest required")
    identity = {k: v for k, v in manifest.items() if k != "packet_sha2_256"}
    if (
        manifest.get("packet_sha2_256") != expected_packet_digest
        or boundary.sha2_256(_encoded(identity)) != expected_packet_digest
        or raw != _encoded(manifest)
    ):
        raise ValueError("Offline packet identity changed")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest.get("schema_version") != 1
        or manifest.get("status") != "NO-GO"
        or manifest.get("live_execution_allowed") is not False
        or manifest.get("provider_qualified") is not False
        or manifest.get("native_execution_allowed") is not False
        or manifest.get("source_commit_exact") is not True
        or not isinstance(manifest.get("source_commit"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"])
        or manifest.get("candidate_pins") != boundary.CANDIDATE_PINS
        or manifest.get("blockers") != list(BLOCKERS)
        or set(manifest.get("files", {})) != PACKET_FILES - {"manifest.json"}
    ):
        raise ValueError("Packet cannot change execution or evidence boundaries")
    for name, record in manifest["files"].items():
        data = boundary._regular_file(destination, name).read_bytes()
        if record != {"bytes": len(data), "sha2_256": boundary.sha2_256(data)}:
            raise ValueError("Staged packet bytes changed")
    plan = boundary.load_plan(boundary._regular_file(destination, "plan.json").read_bytes())
    if set(plan.source_files) != set(PLAN_FILES) or plan.digest != manifest.get("plan_digest"):
        raise ValueError("Plan closure or digest changed")
    boundary.validate_current_inputs(plan, destination / "source")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-packet-digest")
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--bundle-path", type=Path)
    parser.add_argument("--current-root", type=Path)
    parser.add_argument("--expected-source-head")
    args = parser.parse_args()
    try:
        if args.verify:
            if not args.expected_packet_digest or any(
                (
                    args.scope,
                    args.source_root,
                    args.bundle_path,
                    args.current_root,
                    args.expected_source_head,
                )
            ):
                raise ValueError("Verification requires only packet and independent digest")
            manifest = verify(args.destination, args.expected_packet_digest)
        else:
            if args.expected_packet_digest or not all(
                (
                    args.scope,
                    args.source_root,
                    args.bundle_path,
                    args.current_root,
                    args.expected_source_head,
                )
            ):
                raise ValueError("All exact offline preparation inputs required")
            boundary._refuse_links(args.scope)
            with args.scope.open("rb") as stream:
                raw = stream.read(262145)
            manifest = prepare(
                args.destination,
                raw,
                args.source_root,
                args.bundle_path,
                args.current_root,
                args.expected_source_head,
            )
    except OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError:
        parser.exit(1, "Offline publisher packet refused; inspect exact private inputs locally.\n")
    print(f"Offline packet SHA2-256: {manifest['packet_sha2_256']}")
    print("NO-GO: concrete runtime caller, private review and exact decisions remain required.")


if __name__ == "__main__":
    main()
