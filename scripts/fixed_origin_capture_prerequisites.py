"""Inspect one private captured module without importing or publishing its source."""

import base64
import binascii
import hashlib
import json
import sys
import uuid
from pathlib import Path

MAX_CAPTURE_BYTES = 16 * 1024 * 1024
MAX_MODULE_BYTES = 8 * 1024 * 1024
MARKERS = {
    "currentInstallationPath": "/api/v001/installations/current",
    "existingPublicPhotosPath": "/api/v001/existing-public-photos",
    "thumbnailHandlerText": "thumbnail",
    "existingPhotosFeatureGate": "FGA_EXISTING_PHOTOS_ENABLED",
    "thumbnailsFeatureGate": "FGA_PHOTO_THUMBNAILS_ENABLED",
}


def inspect_capture(path: Path) -> dict:
    """Return closed metadata; reject unsupported input without source diagnostics."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_CAPTURE_BYTES + 1)
    if len(raw) > MAX_CAPTURE_BYTES:
        raise ValueError("capture_size")
    document = json.loads(raw)
    if not isinstance(document, dict) or not isinstance(document.get("result"), dict):
        raise ValueError("capture_shape")
    result = document["result"]
    identity = result.get("id")
    if not isinstance(identity, str) or str(uuid.UUID(identity)) != identity:
        raise ValueError("capture_identity")
    modules = result.get("modules")
    if (
        result.get("main_module") != "worker.js"
        or not isinstance(modules, list)
        or len(modules) != 1
        or not isinstance(modules[0], dict)
    ):
        raise ValueError("module_shape")
    module = modules[0]
    encoded = module.get("content_base64")
    if (
        module.get("name") != result["main_module"]
        or module.get("content_type") != "application/javascript+module"
        or not isinstance(encoded, str)
        or len(encoded) > 4 * ((MAX_MODULE_BYTES + 2) // 3)
    ):
        raise ValueError("module_shape")
    decoded = base64.b64decode(encoded, validate=True)
    if (
        not 0 < len(decoded) <= MAX_MODULE_BYTES
        or base64.b64encode(decoded).decode("ascii") != encoded
    ):
        raise ValueError("module_encoding")
    source = decoded.decode("utf-8", errors="strict")
    findings = {label: marker in source for label, marker in MARKERS.items()}
    return {
        "schemaVersion": 1,
        "kind": "offline_capture_prerequisite",
        "moduleBytes": len(decoded),
        "moduleSha2_256": hashlib.sha256(decoded).hexdigest(),
        "findings": findings,
        "prerequisitesPresent": all(findings.values()),
        "wrapperIsolationProved": False,
        "hostedQualified": False,
    }


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print(
            "usage: fixed_origin_capture_prerequisites.py <private-version-modules-json>",
            file=sys.stderr,
        )
        return 2
    try:
        receipt = inspect_capture(Path(arguments[0]))
    except OSError, ValueError, TypeError, UnicodeError, binascii.Error, RecursionError:
        print("capture_inspection_refused", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["prerequisitesPresent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
