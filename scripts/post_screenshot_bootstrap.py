"""Explicit same-process POST admission rendezvous; default CLI is inert.

Only public source and exclusive protected metadata are accessed before release.
The fixed caller owns credential/config admission, provider work and teardown.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import time
from pathlib import Path

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_execution as offline
from scripts import prepare_post_screenshot_successor as prepared
from scripts.group_post_dispatch import create_json
from scripts.hosted_publisher_execution import _assert_private, _private_bytes
from scripts.post_screenshot_admission import _path
from scripts.post_screenshot_successor import apply

WAIT_SECONDS = 600
NAMES = ("bootstrap.json", "release.json", "bootstrap-closed.json", "bootstrap-stop.json")


def _private_root(root):
    boundary._refuse_links(root)
    _assert_private(root, directory=True)


def _release(path):
    # Exactly one protected bounded same-byte read, then strict duplicate-free JSON.
    return offline._read_json(_private_bytes(path, 4096))


def _credentials(root, bound, parent_token_file):
    parent = _path(parent_token_file)
    if str(parent) != parent_token_file:
        raise ValueError("bootstrap_canonical_parent_required")
    paths = {parent, _path(bound["tokenFile"])}
    if len(paths) != 2 or any(path == root or root in path.parents for path in paths):
        raise ValueError("bootstrap_credential_role_path_refused")
    identities = set()
    for path in paths:
        _assert_private(path)
        info = path.stat()
        identities.add((info.st_dev, info.st_ino))
    if len(identities) != 2:
        raise ValueError("bootstrap_credential_role_identity_refused")
    return paths, identities


def _exclude(path, credentials, *, private=False):
    boundary._refuse_links(path)
    if private:
        _assert_private(path)
    info = path.stat()
    if path.resolve(strict=True) in credentials[0] or (info.st_dev, info.st_ino) in credentials[1]:
        raise ValueError("bootstrap_credential_alias_refused")


def _source_preflight(credentials):
    # Complete declared public read inventory BEFORE any manifest/source bytes.
    inventory = {prepared.ROOT / prepared.MANIFEST, Path(__file__)}
    inventory.update(prepared.ROOT / name for name in prepared.SOURCES)
    for path in inventory:
        _exclude(path, credentials)


def run(run_id, manifest_sha2_256, parent_token_file):
    """Invoke the fixed admitted caller once in this process after Root release.

    Root first creates the exact private/bootstrap directory and independently
    binds this helper's bytes through the final manifest and private cells.
    This function creates no directories and accepts no executable callbacks.
    """
    prepared.identity(run_id)
    if not isinstance(manifest_sha2_256, str) or not re.fullmatch(
        r"[a-f0-9]{64}", manifest_sha2_256
    ):
        raise ValueError("bootstrap_manifest_pin_required")
    bound = prepared.binding(run_id)
    root = Path(bound["runRoot"]) / "private/bootstrap"
    _private_root(root)
    credentials = _credentials(root, bound, parent_token_file)
    _source_preflight(credentials)
    if prepared.validate_manifest() != manifest_sha2_256:
        raise ValueError("bootstrap_manifest_changed")
    paths = {name: root / name for name in NAMES}
    if any(path.exists() for path in paths.values()):
        raise ValueError("bootstrap_not_fresh")
    pid, nonce = str(os.getpid()), secrets.token_hex(16)
    started, previous = time.monotonic(), time.time()
    if not math.isfinite(started) or not math.isfinite(previous):
        raise ValueError("bootstrap_clock_invalid")
    deadline = previous + WAIT_SECONDS
    source_pin = prepared.digest(Path(__file__))
    identity = {"schemaVersion": 1, "runId": run_id, "owner": pid, "nonce": nonce}
    create_json(
        paths["bootstrap.json"],
        {
            **identity,
            "manifestSha2_256": manifest_sha2_256,
            "callerSha2_256": source_pin,
            "deadlineUnix": deadline,
        },
    )
    approval_pin = None
    apply_started = apply_returned = False
    outcome = "stopped_or_unknown"
    previous_elapsed = 0
    failure = None
    try:
        _assert_private(paths["bootstrap.json"])
        while True:
            now, elapsed = time.time(), time.monotonic() - started
            if (
                not math.isfinite(now)
                or not math.isfinite(elapsed)
                or now < previous
                or elapsed < previous_elapsed
                or now >= deadline
                or elapsed >= WAIT_SECONDS
            ):
                raise ValueError("bootstrap_clock_or_cutoff")
            previous = now
            previous_elapsed = elapsed
            _private_root(root)
            if _credentials(root, bound, parent_token_file) != credentials:
                raise ValueError("bootstrap_credential_metadata_changed")
            for path in paths.values():
                if path.exists():
                    _exclude(path, credentials, private=True)
            if paths["bootstrap-stop.json"].exists():
                raise ValueError("bootstrap_stopped")
            if paths["release.json"].exists():
                value = _release(paths["release.json"])
                if (
                    not isinstance(value, dict)
                    or set(value) != {*identity, "approvalSha2_256"}
                    or any(
                        type(value[k]) is not type(v) or value[k] != v for k, v in identity.items()
                    )
                    or not isinstance(value["approvalSha2_256"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", value["approvalSha2_256"])
                ):
                    raise ValueError("bootstrap_exact_release_required")
                # Potentially slow source reads precede the last clock/stop guard.
                _source_preflight(credentials)
                if (
                    prepared.validate_manifest() != manifest_sha2_256
                    or prepared.digest(Path(__file__)) != source_pin
                ):
                    raise ValueError("bootstrap_source_changed")
                approval_pin = value["approvalSha2_256"]
                packet_path = Path(bound["runRoot"]) / "private/approved-packet.json"
                for path in (packet_path, packet_path.with_name("config.json")):
                    _exclude(path, credentials, private=True)
                config = prepared.validate_packet(packet_path, approval_pin)
                if config["parentTokenFile"] != parent_token_file:
                    raise ValueError("bootstrap_declared_parent_changed")
                _private_root(root)
                stopped = paths["bootstrap-stop.json"].exists()
                now, elapsed = time.time(), time.monotonic() - started
                if (
                    stopped
                    or not math.isfinite(now)
                    or not math.isfinite(elapsed)
                    or now < previous
                    or elapsed < previous_elapsed
                    or now >= deadline
                    or elapsed >= WAIT_SECONDS
                ):
                    raise ValueError("bootstrap_release_expired_or_stopped")
                apply_started = True
                # The released digest authorizes only this fixed original path.
                # apply rechecks its original source, authority and action clocks.
                result = apply(packet_path, approval_pin)
                apply_returned = True
                outcome = result.get("outcome")
                if outcome not in ("characterized", "failed", "stopped"):
                    outcome = "unknown"
                return {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "owner": pid,
                    "outcome": outcome,
                    "applyReturned": True,
                    "cleanupConfirmed": result.get("cleanupConfirmed") is True,
                    "methodSpecificPostQualified": False,
                }
            time.sleep(0.1)
    except BaseException as error:
        failure = error
        raise
    finally:
        # Exclusive durable closure is NOT process-exit or native-task evidence.
        # A failed/unknown closure preserves the claim and never permits replay.
        try:
            _private_root(root)
            if _credentials(root, bound, parent_token_file) != credentials:
                raise ValueError("bootstrap_credential_metadata_changed")
            create_json(
                paths["bootstrap-closed.json"],
                {
                    **identity,
                    "callerSha2_256": source_pin,
                    "approvalSha2_256": approval_pin,
                    "state": "closed",
                    "applyStarted": apply_started,
                    "applyReturned": apply_returned,
                    "outcome": outcome,
                },
            )
            _assert_private(paths["bootstrap-closed.json"])
        except BaseException:
            if failure is not None:
                failure.add_note("bootstrap_closure_unconfirmed")
            else:
                raise ValueError("bootstrap_closure_unconfirmed") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--manifest-sha2-256")
    parser.add_argument("--parent-token-file")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"mode": "offline", "actionReady": False, "productionQualified": False}))
        return
    try:
        print(json.dumps(run(args.run_id, args.manifest_sha2_256, args.parent_token_file)))
    except Exception:
        # Never print tracebacks, tokens, private config or provider exception text.
        print(json.dumps({"stage": "bootstrap_stopped_or_unknown", "actionReady": False}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
