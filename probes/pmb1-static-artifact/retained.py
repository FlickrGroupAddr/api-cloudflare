"""Read exact separately pinned rollback bytes. No build or provider client."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


def sha2_256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def retained_bytes(directory: Path, expected_manifest_sha2_256: str) -> dict[str, bytes]:
    """Expected manifest pin must come from independent retained custody.

    This verifies bytes only; no actual immutable version/resource/qualification
    is inferred and no restoration dispatch is offered without those facts.
    """
    raw = (directory / "artifact-manifest.json").read_bytes()
    if (
        not re.fullmatch("[a-f0-9]{64}", expected_manifest_sha2_256)
        or sha2_256(raw) != expected_manifest_sha2_256
    ):
        raise ValueError("retained manifest mismatch")
    manifest = json.loads(raw)
    if manifest["schema"] != "pmb1-static-workers-artifact-v1" or manifest["restore"] != {
        "rebuildAllowed": False,
        "force": False,
        "actualImmutableVersion": None,
    }:
        raise ValueError("retained restoration contract")
    result = {}
    for name, pin in manifest["moduleSha2_256"].items():
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or str(path) != name
            or ":" in name
            or "\\" in name
        ):
            raise ValueError("retained module path")
        target = (directory / "modules" / name).resolve()
        if not target.is_relative_to((directory / "modules").resolve()):
            raise ValueError("retained module escape")
        content = target.read_bytes()
        if sha2_256(content) != pin:
            raise ValueError("retained module mismatch")
        result[name] = content
    config = (directory / "configuration.json").read_bytes()
    if sha2_256(config) != manifest["configurationSha2_256"]:
        raise ValueError("retained configuration mismatch")
    result["configuration.json"] = config
    return result
