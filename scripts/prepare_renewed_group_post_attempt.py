"""Prepare a new ungranted POST attempt; later action requires a fresh exact approved packet."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path

from scripts import prepare_group_post_dispatch as sealed

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "0a8b92d40ed1466fa7de82c1"
BASE_MANIFEST = sealed.MANIFEST
BASE_SHA256 = "f00a330f03dd562a9203905a4c20903e4a542f94a8b0ba9e565a7c52f678ac1b"
MANIFEST = "probes/group-post-characterization/renewed-manifest.json"
RUN_ROOT = (
    Path("C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/.coordination-runs/renewed-group-post")
    / RUN_ID
)
NATIVE_ROOT = sealed.NATIVE_ROOT
PACKET = "docs/operations/renewed-group-post-attempt-2026-10-18.md"
NEW_SOURCES = {
    "scripts/prepare_renewed_group_post_attempt.py",
    "scripts/group_post_native_dispatch.mjs",
    "scripts/renewed_group_post_attempt.py",
    PACKET,
}
SOURCES = NEW_SOURCES | {BASE_MANIFEST}
snapshot = sealed.snapshot
digest = sealed.digest


def binding():
    return {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "coordinationRoot": str(RUN_ROOT / "handshake"),
        "nativeRoot": str(NATIVE_ROOT),
        "tokenFile": str(RUN_ROOT / "private/operator-token.txt"),
    }


def validate_manifest(*, root: Path = ROOT):
    """Pin the sealed 0160 closure separately; never rewrite its source or manifest."""
    manifest_digest, value = snapshot(root / MANIFEST)
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "kind", "binding", "sources", "productionQualified"}
        or type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "ungranted_renewed_post_attempt"
        or value["binding"] != binding()
        or not isinstance(value["binding"], dict)
        or type(value["binding"].get("schemaVersion")) is not int
        or value["productionQualified"] is not False
        or not isinstance(value["sources"], dict)
        or set(value["sources"]) != SOURCES
    ):
        raise ValueError("renewed_manifest_invalid")
    if digest(root / BASE_MANIFEST) != BASE_SHA256:
        raise ValueError("sealed_dispatch_manifest_changed")
    sealed.validate_manifest(root=root)
    for name, pin in value["sources"].items():
        if (
            not isinstance(pin, str)
            or not re.fullmatch(r"[a-f0-9]{64}", pin)
            or digest(root / name) != pin
        ):
            raise ValueError("renewed_source_changed")
    return manifest_digest


def validate_packet(packet_path: Path, approved_sha2_256: str, *, root: Path = ROOT):
    """Check bounded exact bindings before the new caller may read its token.

    True flags bind a reviewed decision; they cannot establish human permission.
    This function opens no token, account provenance, native file or provider.
    """
    if packet_path != RUN_ROOT / "private/approved-packet.json":
        raise ValueError("approval_path_invalid")
    if not isinstance(approved_sha2_256, str) or not re.fullmatch(
        r"[a-f0-9]{64}", approved_sha2_256
    ):
        raise ValueError("approval_digest_required")
    approval_digest, approval = snapshot(packet_path)
    if approval_digest != approved_sha2_256:
        raise ValueError("approval_digest_changed")
    manifest_digest = validate_manifest(root=root)
    config_digest, config = snapshot(packet_path.with_name("config.json"))
    expected = {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "manifestSha256": manifest_digest,
        "configSha256": config_digest,
        "ownerConsent": True,
        "nativeConsent": True,
    }
    if (
        not isinstance(approval, dict)
        or set(approval) != set(expected)
        or approval != expected
        or type(approval["schemaVersion"]) is not int
        or approval["ownerConsent"] is not True
        or approval["nativeConsent"] is not True
    ):
        raise ValueError("consent_or_packet_invalid")
    if (
        not isinstance(config, dict)
        or set(config)
        != {
            *binding(),
            "accountId",
            "subdomain",
            "actionDeadlineUnix",
            "tokenRequirementsConfirmed",
            "actionScopeSha256",
        }
        or any(type(config[k]) is not type(v) or config[k] != v for k, v in binding().items())
        or not isinstance(config["accountId"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", config["accountId"])
        or not isinstance(config["subdomain"], str)
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", config["subdomain"])
        or type(config["actionDeadlineUnix"]) not in (int, float)
        or not math.isfinite(config["actionDeadlineUnix"])
        or not time.time() + 1230 <= config["actionDeadlineUnix"] <= time.time() + 1800
        or config["tokenRequirementsConfirmed"] is not True
        or config["actionScopeSha256"] != digest(root / PACKET)
    ):
        raise ValueError("private_config_invalid")
    return config


def prepare(*, root: Path = ROOT):
    """Exclusively write ungranted templates, without creating runtime/native state."""
    manifest_digest = validate_manifest(root=root)
    RUN_ROOT.mkdir(parents=True, exist_ok=False)
    private = RUN_ROOT / "private"
    private.mkdir()
    config = {
        **binding(),
        "accountId": "",
        "subdomain": "",
        "actionDeadlineUnix": None,
        "tokenRequirementsConfirmed": False,
        "actionScopeSha256": "",
    }
    config_path = private / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    approval = {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "manifestSha256": manifest_digest,
        "configSha256": digest(config_path),
        "ownerConsent": False,
        "nativeConsent": False,
    }
    (private / "approved-packet.json").write_text(
        json.dumps(approval, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return {"runId": RUN_ID, "mode": "ungranted_preparation", "productionQualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            prepare()
            if args.prepare
            else {
                **binding(),
                "manifestSha256": validate_manifest(),
                "mode": "offline_preparation",
                "nativeRouteReady": False,
                "actionReady": False,
                "productionQualified": False,
            }
        )
        print(json.dumps(result, indent=2))
        return 0
    except Exception:
        print('{"outcome":"refused","productionQualified":false}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
