"""Prepare ungranted fresh POST dispatch inputs; never read credentials or execute source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "88603c8c3262426397a5bb67"
BASE_MANIFEST = "probes/group-post-characterization/manifest.json"
BASE_SHA256 = "87e52649df09518ed372e5482ca3c61be7c3ac4f7e8c6bd07c7cdc09206805ed"
MANIFEST = "probes/group-post-characterization/dispatch-manifest.json"
RUN_ROOT = (
    Path("C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/.coordination-runs/group-post-dispatch")
    / RUN_ID
)
NATIVE_ROOT = Path("C:/Temp/FGA-group-post-v1")
NEW_SOURCES = {
    "scripts/group_post_dispatch.py",
    "scripts/group_post_dispatch.mjs",
    "scripts/prepare_group_post_dispatch.py",
    "docs/operations/group-post-dispatch-packet-2026-10-18.md",
    "docs/operations/group-post-dispatch-rehearsal-2026-10-18.md",
}
BASE_SOURCES = {
    "probes/group-post-characterization/worker.mjs",
    "probes/group-post-characterization/schema.sql",
    "scripts/group_post_characterization.py",
    "probes/lightroom/FGA-GroupPost-v1.lrplugin/Info.lua",
    "probes/lightroom/FGA-GroupPost-v1.lrplugin/Post.lua",
    "probes/lightroom/FGA-GroupPost-v1.lrplugin/Run.lua",
    "clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua",
    "clients/lightroom/FGA-LrC15.lrplugin/GroupSubmissionClient.lua",
    "clients/lightroom/FGA-LrC15.lrplugin/dkjson.lua",
}
SOURCES = BASE_SOURCES | NEW_SOURCES | {BASE_MANIFEST}


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_field")
        value[key] = item
    return value


def snapshot(path: Path, maximum: int = 65536):
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("packet_byte_limit")
    return hashlib.sha256(raw).hexdigest(), json.loads(raw, object_pairs_hook=_object)


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding():
    return {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "coordinationRoot": str(RUN_ROOT / "handshake"),
        "nativeRoot": str(NATIVE_ROOT),
        "tokenFile": str(RUN_ROOT / "private/operator-token.txt"),
    }


def validate_manifest(*, root: Path = ROOT):
    manifest_digest, value = snapshot(root / MANIFEST)
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "kind", "binding", "sources", "productionQualified"}
        or type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "offline_post_dispatch_preparation"
        or not isinstance(value["binding"], dict)
        or type(value["binding"].get("schemaVersion")) is not int
        or value["binding"] != binding()
        or value["productionQualified"] is not False
        or not isinstance(value["sources"], dict)
        or set(value["sources"]) != SOURCES
    ):
        raise ValueError("dispatch_manifest_invalid")
    if digest(root / BASE_MANIFEST) != BASE_SHA256:
        raise ValueError("base_manifest_changed")
    _, base = snapshot(root / BASE_MANIFEST)
    if set(base["sha2_256"]) != BASE_SOURCES:
        raise ValueError("base_closure_changed")
    for name, pin in value["sources"].items():
        if (
            not isinstance(pin, str)
            or not re.fullmatch(r"[a-f0-9]{64}", pin)
            or digest(root / name) != pin
            or (name in BASE_SOURCES and pin != base["sha2_256"][name])
        ):
            raise ValueError("dispatch_source_changed")
    return manifest_digest


def validate_packet(packet_path: Path, approved_sha2_256: str, *, root: Path = ROOT):
    """Approval digest is supplied out of band after applicable owner confirmation.

    Returns bounded config only. Token, retained account sources and native files
    are never opened here. Integrity records cannot establish human consent.
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
        or approval["ownerConsent"] is not True
        or approval["nativeConsent"] is not True
        or type(approval["schemaVersion"]) is not int
    ):
        raise ValueError("consent_or_packet_invalid")
    if (
        not isinstance(config, dict)
        or set(config) != {*binding(), "accountId", "subdomain"}
        or any(config[key] != item for key, item in binding().items())
        or type(config["schemaVersion"]) is not int
        or not isinstance(config["accountId"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", config["accountId"])
        or not isinstance(config["subdomain"], str)
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", config["subdomain"])
    ):
        raise ValueError("private_config_invalid")
    return config


def prepare(*, root: Path = ROOT):
    """Write a new private template directory only; never grant consent."""
    manifest_digest = validate_manifest(root=root)
    # Exact proposed root is non-secret, new, and distinct from the closed attempt.
    RUN_ROOT.mkdir(parents=True, exist_ok=False)
    directory = RUN_ROOT / "private"
    directory.mkdir()
    config = {**binding(), "accountId": "", "subdomain": ""}
    config_path = directory / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    approval = {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "manifestSha256": manifest_digest,
        "configSha256": digest(config_path),
        "ownerConsent": False,
        "nativeConsent": False,
    }
    (directory / "approved-packet.json").write_text(
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
