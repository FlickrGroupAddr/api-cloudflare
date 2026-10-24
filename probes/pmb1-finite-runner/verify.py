"""Read-only frozen SOURCE closure verification; no execution or re-freezing.

MIT License; copyright 2026 Terry Ott.
"""

import hashlib
import json
from pathlib import Path


def verify_source(root: Path, expected_manifest_pin: str) -> dict:
    """The expected pin must come from the independently retained review."""
    if (
        not root.is_absolute()
        or len(expected_manifest_pin) != 64
        or any(c not in "0123456789abcdef" for c in expected_manifest_pin)
    ):
        raise ValueError("invalid_frozen_source_reference")
    manifest = root / "probes/pmb1-finite-runner/source-pins.json"
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_manifest_pin:
        raise ValueError("finite_runner_manifest_drift")
    value = json.loads(raw)
    if (
        value["schema"] != "pmb1-finite-runner-source-v1"
        or value["actualQualification"] is not False
    ):
        raise ValueError("finite_runner_manifest_contract")
    for name, record in value["sourceInputs"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("finite_runner_source_path")
        source = path.read_bytes()
        if (
            len(source) != record["bytes"]
            or hashlib.sha256(source).hexdigest() != record["sha2_256"]
        ):
            raise ValueError("finite_runner_source_drift")
    return {
        "source": "PASS",
        "qualification": "NO_GO",
        "dispatchEnabled": False,
        "files": len(value["sourceInputs"]),
    }
