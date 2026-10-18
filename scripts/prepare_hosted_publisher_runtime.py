"""Prepare a separate, committed execution-source packet; never grant permission."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
from pathlib import Path, PurePosixPath

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_execution as offline

PLAN_FILES = tuple(
    sorted(
        set(offline.PLAN_FILES)
        | {
            "scripts/hosted_publisher_execution.py",
            "scripts/hosted_publisher_execution_provider.py",
            "scripts/prepare_hosted_publisher_runtime.py",
        }
    )
)
SOURCE_FILES = tuple(sorted(set(PLAN_FILES) | {"pyproject.toml", "uv.lock", ".python-version"}))
PACKET_FILES = {"manifest.json", "plan.json"} | {"source/" + n for n in SOURCE_FILES}


def bounded_read(root, name, maximum):
    path = boundary._regular_file(root, name)
    before = path.stat()
    if not 0 < before.st_size <= maximum:
        raise ValueError("Bounded execution packet file required")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    after = path.stat()
    if (
        len(raw) != before.st_size
        or len(raw) > maximum
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise ValueError("Execution packet file changed during bounded read")
    boundary._regular_file(root, name)
    return raw


def validate_network(value, plan):
    boundary._closed(value, {"management_address", "client_addresses"})
    if type(value["client_addresses"]) is not dict or set(value["client_addresses"]) != {
        c.endpoint for c in plan.cases
    }:
        raise ValueError("Exact independently supplied endpoint address pins required")
    for address in (value["management_address"], *value["client_addresses"].values()):
        if type(address) is not str:
            raise ValueError("Numeric global TLS address required")
        parsed = ipaddress.ip_address(address)
        if str(parsed) != address or not parsed.is_global or parsed.is_multicast:
            raise ValueError("Numeric global TLS address required")
    return value


def source_identity(root, expected, files):
    if (
        not re.fullmatch(r"[0-9a-f]{40}", expected)
        or offline._git(root, "rev-parse", "HEAD") != expected
    ):
        raise ValueError("Exact separately reviewed committed source required")
    entries = {}
    for line in offline._git(root, "ls-tree", "-r", expected, "--", *SOURCE_FILES).splitlines():
        metadata, name = line.split("\t", 1)
        mode, kind, identity = metadata.split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError("Only committed regular source is allowed")
        entries[name] = identity
    if set(entries) != set(files):
        raise ValueError("Incomplete execution-source closure")
    for name, raw in files.items():
        identity = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if entries[name] != identity:
            raise ValueError("Execution source differs from reviewed commit")


def prepare(
    destination,
    scope_raw,
    source_root,
    bundle_path,
    current_root,
    expected_source_head,
    network_raw,
):
    """Create new public-code/private-scope packet, without credentials or consent."""
    boundary._refuse_links(destination)
    if destination.exists():
        raise ValueError("New packet directory required")
    destination = destination.parent.resolve(strict=True) / destination.name
    for root in (current_root, source_root, bundle_path.parent):
        if destination.is_relative_to(root.resolve(strict=True)):
            raise ValueError("Packet must be outside source/candidate roots")
    files = {n: bounded_read(current_root, n, 16_777_216) for n in SOURCE_FILES}
    source_identity(current_root, expected_source_head, files)
    scope = offline._read_json(scope_raw)
    if set(scope) != offline.SCOPE_FIELDS:
        raise ValueError("Independent exact scope required")
    plan = boundary.load_plan(
        boundary.encoded(
            {
                **scope,
                "pins": dict(boundary.CANDIDATE_PINS),
                "source_files": {n: boundary.sha2_256(files[n]) for n in PLAN_FILES},
            }
        )
    )
    for case in plan.cases:
        if any(
            re.fullmatch(r"fga-publisher-[a-z0-9-]{1,48}", n) is None
            for n in (case.worker_name, case.d1_name)
        ):
            raise ValueError("Exact provider intended-name boundary required")
    network = validate_network(offline._read_json(network_raw), plan)
    boundary.validate_current_inputs(plan, current_root)
    boundary.validate_artifact(source_root, bundle_path)
    payload = {"source/" + n: data for n, data in files.items()}
    payload["plan.json"] = offline._encoded(offline._plan_document(plan))
    identity = {
        "schema_version": 1,
        "status": "NO-GO",
        "live_execution_allowed": False,
        "native_execution_allowed": False,
        "provider_qualified": False,
        "source_commit": expected_source_head,
        "candidate_pins": dict(boundary.CANDIDATE_PINS),
        "plan_digest": plan.digest,
        "network": network,
        "files": {
            n: {"bytes": len(data), "sha2_256": boundary.sha2_256(data)}
            for n, data in sorted(payload.items())
        },
    }
    manifest = {**identity, "packet_sha2_256": boundary.sha2_256(offline._encoded(identity))}
    boundary.validate_current_inputs(plan, current_root)
    destination.mkdir()
    for name, data in payload.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (destination / "manifest.json").write_bytes(offline._encoded(manifest))
    return verify(destination, manifest["packet_sha2_256"])


def verify(destination, expected_digest):
    boundary._text(expected_digest, r"[0-9a-f]{64}", "independent execution packet digest")
    boundary._refuse_links(destination)
    actual = set()
    expected_directories = {
        parent.as_posix()
        for name in PACKET_FILES
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
    for path in destination.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked packet content refused")
        relative = path.relative_to(destination).as_posix()
        if path.is_file():
            if relative not in PACKET_FILES:
                raise ValueError("Unexpected execution packet file")
            actual.add(relative)
        elif path.is_dir() and relative not in expected_directories:
            raise ValueError("Unexpected execution packet directory")
    if actual != PACKET_FILES:
        raise ValueError("Execution packet file set changed")
    manifest = offline._read_json(bounded_read(destination, "manifest.json", 262144))
    boundary._closed(
        manifest,
        {
            "schema_version",
            "status",
            "live_execution_allowed",
            "native_execution_allowed",
            "provider_qualified",
            "source_commit",
            "candidate_pins",
            "plan_digest",
            "network",
            "files",
            "packet_sha2_256",
        },
    )
    identity = {k: v for k, v in manifest.items() if k != "packet_sha2_256"}
    if (
        manifest["packet_sha2_256"] != expected_digest
        or boundary.sha2_256(offline._encoded(identity)) != expected_digest
    ):
        raise ValueError("Independent execution packet digest mismatch")
    if (
        type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != 1
        or manifest["status"] != "NO-GO"
        or any(
            manifest[n] is not False
            for n in ("live_execution_allowed", "native_execution_allowed", "provider_qualified")
        )
    ):
        raise ValueError("Packet cannot grant live permission")
    boundary._text(manifest["source_commit"], r"[0-9a-f]{40}", "source commit")
    if (
        manifest["candidate_pins"] != boundary.CANDIDATE_PINS
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != PACKET_FILES - {"manifest.json"}
    ):
        raise ValueError("Execution closure/pins changed")
    for name, record in manifest["files"].items():
        boundary._closed(record, {"bytes", "sha2_256"})
        if type(record["bytes"]) is not int or not 0 < record["bytes"] <= 16_777_216:
            raise ValueError("Execution source file bound")
        raw = bounded_read(destination, name, record["bytes"])
        if len(raw) != record["bytes"] or boundary.sha2_256(raw) != record["sha2_256"]:
            raise ValueError("Execution packet content changed")
    plan = boundary.load_plan(bounded_read(destination, "plan.json", 262144))
    if plan.digest != manifest["plan_digest"] or set(plan.source_files) != set(PLAN_FILES):
        raise ValueError("Execution plan/closure mismatch")
    for name, digest in plan.source_files.items():
        if digest != manifest["files"]["source/" + name]["sha2_256"]:
            raise ValueError("Execution source/plan mismatch")
    validate_network(manifest["network"], plan)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--packet-digest")
    args = parser.parse_args()
    if args.verify is None or args.packet_digest is None:
        parser.error(
            "Offline verify requires --verify and independent --packet-digest; "
            "prepare() accepts independently supplied scope"
        )
    try:
        verify(args.verify, args.packet_digest)
    except ValueError, OSError:
        parser.exit(2, "Execution packet refused\n")
    print("NO-GO: packet verified; separate current action authority required")


if __name__ == "__main__":
    main()
