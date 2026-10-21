"""Offline preparation for a fresh, ungranted screenshot POST successor.

No default identity exists. Preparation does not read tokens or native state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import stat
import time
from pathlib import Path

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_group_post_dispatch as sealed
from scripts import provision_work_plan_token as issuer
from scripts.hosted_publisher_execution import _assert_private, _document

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "probes/group-post-characterization/screenshot-successor-manifest.json"
SCOPE = "docs/operations/post-screenshot-successor-2026-10-21.md"
RUNS = Path("C:/Temp/FGA-post-screenshot-successor")
SPENT = {"0" * 24, "c01ba6d2c2754597aa311c9f", sealed.RUN_ID, "0a8b92d40ed1466fa7de82c1"}
SOURCES = (
    sealed.SOURCES
    | set(issuer.SOURCE_FILES)
    | {
        "probes/group-post-characterization/worker.test.mjs",
        ".node-version",
        "docs/operations/cloudflare-management-response-policy-2026-10-18.md",
        "docs/operations/group-post-action-approval-2026-10-16.md",
        "docs/operations/group-post-characterization-2026-10-16.md",
        "docs/operations/post-screenshot-lifecycle-2026-10-21.md",
        "docs/operations/screenshot-post-dispatch-contract-2026-10-21.md",
        "docs/operations/screenshot-post-rehearsal-2026-10-21.md",
        "docs/operations/synthetic-d1-disposal-policy-2026-10-19.md",
        "tests/test_collect_publisher_grant_metadata.py",
        "tests/test_group_post_characterization.py",
        "tests/test_group_post_characterization_runner.py",
        "tests/test_group_post_dispatch.py",
        "tests/test_hosted_publisher_execution_transport.py",
        "tests/test_hosted_publisher_windows_private.py",
        "tests/test_hosted_publisher_finite_client.py",
        "tests/test_hosted_publisher_operator_plan.py",
        "tests/test_hosted_publisher_provider.py",
        "tests/test_hosted_publisher_worker_deployment.py",
        "tests/test_hosted_publisher_worker_identity.py",
        "tests/test_prepare_group_post_dispatch.py",
        "tests/test_provision_work_plan_token.py",
        "scripts/post_screenshot_admission.py",
        "tests/test_post_screenshot_admission.py",
        "docs/operations/post-screenshot-admission-2026-10-21.md",
        "scripts/post_screenshot_bootstrap.py",
        "tests/test_post_screenshot_bootstrap.py",
        "docs/operations/post-screenshot-bootstrap-2026-10-21.md",
        "scripts/prepare_post_screenshot_successor.py",
        "scripts/post_screenshot_successor.py",
        "scripts/post_screenshot_lifecycle.py",
        "scripts/group_post_native_dispatch.mjs",
        "scripts/group_post_screenshot_dispatch.mjs",
        "tests/test_post_screenshot_successor.py",
        "tests/test_prepare_post_screenshot_successor.py",
        "tests/test_post_screenshot_lifecycle.py",
        "tests/group_post_screenshot_dispatch.test.mjs",
        "tests/group_post_native_dispatch.test.mjs",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "package.json",
        "package-lock.json",
        SCOPE,
    }
)
snapshot = sealed.snapshot  # Offline preparation/test reads only.


def public_bytes(path, maximum=16_777_216):
    """Bound public source bytes without requiring private-file ACLs."""
    path = Path(path)
    boundary._refuse_links(path)
    before = path.stat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 <= before.st_size <= maximum
    ):
        raise ValueError("public_regular_single_link_bounded_file_required")

    def identity(info):
        return (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_nlink,
        )

    fd = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOINHERIT", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
    )
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or identity(opened) != identity(before):
            raise ValueError("public_input_changed_before_read")
        raw = os.read(fd, maximum + 1)
        after = os.fstat(fd)
        if (
            len(raw) != before.st_size
            or identity(after) != identity(opened)
            or after.st_ctime_ns != opened.st_ctime_ns
        ):
            raise ValueError("public_input_changed_during_read")
    finally:
        os.close(fd)
    boundary._refuse_links(path)
    final = path.stat()
    if identity(final) != identity(before) or final.st_ctime_ns != before.st_ctime_ns:
        raise ValueError("public_input_changed_after_read")
    return raw


def digest(path):
    return hashlib.sha256(public_bytes(path)).hexdigest()


def identity(run_id, *, spent_run_ids=()):
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{24}", run_id) or run_id in SPENT:
        raise ValueError("fresh_identity_required")
    if run_id in spent_run_ids:
        raise ValueError("spent_identity_refused")
    return run_id


def validate_spent_history(run_id, spent_run_ids):
    """Public exclusions are partial; protected reviewed history owns completeness."""
    if (
        not isinstance(spent_run_ids, list)
        or not 1 <= len(spent_run_ids) <= 256
        or any(
            not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{24}", item)
            for item in spent_run_ids
        )
        or len(set(spent_run_ids)) != len(spent_run_ids)
    ):
        raise ValueError("bounded_private_spent_history_required")
    identity(run_id, spent_run_ids=spent_run_ids)


def binding(run_id, *, runs=RUNS):
    directory = Path(runs) / identity(run_id)
    if not directory.is_absolute():
        raise ValueError("absolute_run_root_required")
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "runRoot": str(directory),
        "coordinationRoot": str(directory / "handshake"),
        "outputRoot": str(directory / "output"),
        "nativeRoot": str(sealed.NATIVE_ROOT),
        "tokenFile": str(directory / "private/operator-token.txt"),
        "evidencePath": str(directory / "private/action-evidence.json"),
    }


def validate_manifest(*, root=ROOT):
    raw = public_bytes(Path(root) / MANIFEST, 65536)
    pin, value = hashlib.sha256(raw).hexdigest(), json.loads(raw, object_pairs_hook=sealed._object)
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "kind", "sources", "productionQualified"}
        or type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "ungranted_screenshot_post_successor"
        or value["productionQualified"] is not False
        or not isinstance(value["sources"], dict)
        or set(value["sources"]) != SOURCES
    ):
        raise ValueError("successor_manifest_invalid")
    for name, expected in value["sources"].items():
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("source_pin_invalid")
        if digest(Path(root) / name) != expected:
            raise ValueError("successor_source_changed")
    return pin


def prepare(*, root=ROOT, runs=RUNS, run_id=None):
    manifest = validate_manifest(root=root)
    run_id = identity(run_id if run_id is not None else secrets.token_hex(12))
    bound = binding(run_id, runs=runs)
    directory = Path(bound["runRoot"])
    # Explicit root creation applies 0700 to this leaf too. Never create its
    # ancestors or repair the permissions of an existing unrelated path.
    boundary._refuse_links(Path(runs))
    Path(runs).mkdir(mode=0o700, exist_ok=True)
    _assert_private(Path(runs), directory=True)
    directory.mkdir(mode=0o700, exist_ok=False)
    _assert_private(directory, directory=True)
    private = directory / "private"
    private.mkdir(mode=0o700)
    _assert_private(private, directory=True)
    config = {
        **bound,
        "accountId": "",
        "subdomain": "",
        "actionDeadlineUnix": None,
        "windowId": None,
        "runtimeCellsSha2_256": "",
        "scopeSha2_256": "",
        "nativePreflightSha2_256": "",
        "credentialGrantSha2_256": "",
        "custodyReviewSha2_256": "",
        "credentialExpiryUnix": None,
        "credentialSha2_256": "",
        "parserProfile": "bounded-stateless-cookie-discard-v1",
        "evidenceSha2_256": "",
        "spentRunIds": [],
        "spentHistorySha2_256": "",
        "parentTokenFile": "",
    }
    config_path = private / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    approval = {
        "schemaVersion": 1,
        "runId": run_id,
        "manifestSha2_256": manifest,
        "configSha2_256": digest(config_path),
        "ownerConsent": False,
        "nativeConsent": False,
        "caseCancelConsent": False,
    }
    (private / "approved-packet.json").write_text(
        json.dumps(approval, indent=2) + "\n", encoding="utf-8"
    )
    return {"mode": "ungranted_preparation", "runId": run_id, "actionReady": False}


def validate_packet(packet_path, approved_pin, *, root=ROOT, runs=RUNS, clock=time.time):
    path = Path(packet_path)
    bound = binding(path.parent.parent.name, runs=runs)
    if path != Path(bound["runRoot"]) / "private/approved-packet.json":
        raise ValueError("approval_path_invalid")
    if not isinstance(approved_pin, str) or not re.fullmatch(r"[a-f0-9]{64}", approved_pin):
        raise ValueError("approval_digest_required")
    # Action inputs use the established metadata/ACL/no-link/single-link and
    # same-byte descriptor checks BEFORE any approval or config content read.
    # Offline ungranted preparation intentionally retains its separate reader.
    approval = _document(path, approved_pin)
    if not isinstance(approval, dict) or not isinstance(approval.get("configSha2_256"), str):
        raise ValueError("exact_consent_required")
    config_pin = approval["configSha2_256"]
    config = _document(path.with_name("config.json"), config_pin)
    expected = {
        "schemaVersion": 1,
        "runId": bound["runId"],
        "manifestSha2_256": validate_manifest(root=root),
        "configSha2_256": config_pin,
        "ownerConsent": True,
        "nativeConsent": True,
        "caseCancelConsent": True,
    }
    if approval != expected or any(type(approval[k]) is not type(v) for k, v in expected.items()):
        raise ValueError("exact_consent_required")
    extras = {
        "accountId",
        "subdomain",
        "actionDeadlineUnix",
        "windowId",
        "runtimeCellsSha2_256",
        "scopeSha2_256",
        "nativePreflightSha2_256",
        "credentialGrantSha2_256",
        "custodyReviewSha2_256",
        "credentialExpiryUnix",
        "credentialSha2_256",
        "parserProfile",
        "evidenceSha2_256",
        "spentRunIds",
        "spentHistorySha2_256",
        "parentTokenFile",
    }
    if not isinstance(config, dict) or set(config) != set(bound) | extras:
        raise ValueError("config_shape_invalid")
    if any(type(config[k]) is not type(v) or config[k] != v for k, v in bound.items()):
        raise ValueError("config_binding_changed")
    validate_spent_history(config["runId"], config["spentRunIds"])
    parent_value = config["parentTokenFile"]
    if not isinstance(parent_value, str):
        raise ValueError("parent_credential_metadata_path_required")
    parent = Path(parent_value)
    if (
        not parent.is_absolute()
        or parent_value.startswith(("\\\\", "//"))
        or ".." in parent.parts
        or str(parent) != parent_value
        or parent != parent.resolve(strict=True)
        or parent == Path(config["tokenFile"])
    ):
        raise ValueError("parent_credential_metadata_path_required")
    _assert_private(parent)  # Metadata and custody only; NEVER open parent bytes.
    for key in extras:
        if key.endswith("Sha2_256") and (
            not isinstance(config[key], str) or not re.fullmatch(r"[a-f0-9]{64}", config[key])
        ):
            raise ValueError("current_evidence_pin_required")
    now = clock()
    deadline, expiry = config["actionDeadlineUnix"], config["credentialExpiryUnix"]
    if (
        type(deadline) not in (int, float)
        or not math.isfinite(deadline)
        or not math.isfinite(now)
        or not now + 1230 <= deadline <= now + 1800
        or type(expiry) not in (int, float)
        or not math.isfinite(expiry)
        or expiry < deadline
        or type(config["windowId"]) is not int
        or config["windowId"] <= 0
        or config["scopeSha2_256"] != digest(Path(root) / SCOPE)
        or not isinstance(config["accountId"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", config["accountId"])
        or not isinstance(config["subdomain"], str)
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", config["subdomain"])
        or config["parserProfile"] != "bounded-stateless-cookie-discard-v1"
    ):
        raise ValueError("current_config_required")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare()))
    else:
        print(json.dumps({"mode": "offline", "actionReady": False, "productionQualified": False}))


if __name__ == "__main__":
    main()
