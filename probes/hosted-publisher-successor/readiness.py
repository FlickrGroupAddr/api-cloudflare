"""Verify public successor bindings only; never produce execution authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_runtime as runtime_packet

RECIPE_FILES = (
    "docs/operations/cloudflare-management-response-policy-2026-10-18.md",
    "docs/operations/hosted-publisher-private-packet-preparation-2026-10-18.md",
    "docs/operations/hosted-publisher-execution-caller-2026-10-18.md",
    "docs/operations/hosted-publisher-beta-integration-2026-10-18.md",
    "tests/test_cloudflare_management_response_policy.py",
    "tests/test_hosted_publisher_execution_transport.py",
    "tests/test_hosted_publisher_execution.py",
    "tests/test_hosted_publisher_token_expiry_amendment.py",
)
PUBLIC_FILES = tuple(sorted(set(runtime_packet.SOURCE_FILES) | set(RECIPE_FILES)))
FALSE_FIELDS = (
    "consent_granted",
    "live_execution_allowed",
    "native_execution_allowed",
    "provider_qualified",
)
FIELDS = {"schema_version", "status", "source_commit", "files", *FALSE_FIELDS}


def verify(root: Path, raw: bytes, expected_digest: str, expected_source: str) -> dict:
    """Read only a fixed public allowlist; successful verification remains NO-GO.

    Expected digest/revision must be independently retained by the reviewer.
    Neither this recipe nor those caller assertions authenticate human consent.
    No private scope, grant, credential, ACL, marker or provider state is accepted.
    """
    boundary._text(expected_digest, r"[0-9a-f]{64}", "independent successor digest")
    boundary._text(expected_source, r"[0-9a-f]{40}", "reviewed public source revision")
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError("Successor recipe digest mismatch")
    value = json.loads(raw, object_pairs_hook=boundary._no_duplicates)
    boundary._closed(value, FIELDS)
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["status"] != "NO-GO"
        or value["source_commit"] != expected_source
        or any(value[name] is not False for name in FALSE_FIELDS)
    ):
        raise ValueError("Successor source/false-consent boundary changed")
    files = value["files"]
    if type(files) is not dict or set(files) != set(PUBLIC_FILES):
        raise ValueError("Exact public successor closure required")
    for name in PUBLIC_FILES:
        boundary._text(files[name], r"[0-9a-f]{64}", "public source digest")
        data = runtime_packet.bounded_read(root, name, 16_777_216)
        if hashlib.sha256(data).hexdigest() != files[name]:
            raise ValueError("Stale public successor source or recipe")
    return {
        "status": "NO-GO",
        **dict.fromkeys(FALSE_FIELDS, False),
        "source_commit": expected_source,
        "public_files_verified": len(PUBLIC_FILES),
        "private_packet_prepared": False,
    }
