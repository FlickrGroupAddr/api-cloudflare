"""GET-only provider inventory for the existing fixed-origin Worker; never deploys.

Only the allowlisted receipt is suitable for publication. The private directory
contains provider identities, configuration and downloaded source, and must stay private.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

API = "https://api.cloudflare.com/client/v4"
HOST = "flickrgroupaddr.com"
WORKER = "fga-api"
LIMIT = 16 * 1024 * 1024
MAX_REQUESTS = 32
MAX_VERSIONS = 8
TOTAL_SECONDS = 180
PHASES = (
    "http_request_dynamic_redirect",
    "http_request_redirect",
    "http_request_transform",
    "http_request_late_transform",
    "http_response_headers_transform",
    "http_request_cache_settings",
    "http_request_firewall_custom",
    "http_request_firewall_managed",
    "http_ratelimit",
    "http_request_sbfm",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class Reader:
    """No caller-selectable URL, method, headers, request body or redirect destination."""

    def __init__(self, account: str, token: str):
        if not re.fullmatch(r"[a-f0-9]{32}", account) or not token.strip():
            raise ValueError("existing_inventory_credentials_unavailable")
        self.account = account
        self.token = token
        self.calls = 0
        self.deadline = time.monotonic() + TOTAL_SECONDS

    def get(self, path: str) -> tuple[int, bytes]:
        account = re.escape(self.account)
        allowed = (
            rf"/accounts/{account}/workers/scripts/fga-api/(?:settings|script-settings|"
            rf"content/v2|deployments|versions/[a-f0-9-]{{36}})",
            rf"/accounts/{account}/workers/domains\?page=1&per_page=100",
            rf"/zones\?name=flickrgroupaddr\.com&account\.id={account}&per_page=50",
            r"/zones/[a-f0-9]{32}/(?:workers/routes|settings|pagerules\?per_page=100|"
            r"rulesets/phases/(?:" + "|".join(PHASES) + r")/entrypoint)",
        )
        if not any(re.fullmatch(pattern, path) for pattern in allowed):
            raise ValueError("existing_inventory_path_rejected")
        remaining = self.deadline - time.monotonic()
        if self.calls >= MAX_REQUESTS or remaining <= 0:
            raise ValueError("existing_inventory_budget_exhausted")
        self.calls += 1
        request = urllib.request.Request(
            API + path, method="GET", headers={"Authorization": "Bearer " + self.token}
        )
        try:
            response = urllib.request.build_opener(NoRedirect).open(
                request, timeout=min(30, remaining)
            )
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(LIMIT + 1)
            if not isinstance(response.status, int) or not isinstance(raw, bytes):
                raise ValueError("existing_inventory_invalid_transport")
            if len(raw) > LIMIT:
                raise ValueError("existing_inventory_response_limit")
            return response.status, raw


class InventoryReader(Protocol):
    account: str

    def get(self, path: str) -> tuple[int, bytes]: ...


def collect(reader: InventoryReader, directory: Path) -> dict[str, Any]:
    # Refuse reuse: each run owns its exact private capture and cannot overwrite it.
    directory.mkdir(parents=True, exist_ok=False)
    private = directory / "private"
    private.mkdir()
    rows: dict[str, Any] = {}
    captured: dict[str, Any] = {}
    deadline = time.monotonic() + TOTAL_SECONDS
    requests = 0

    def capture(label: str, path: str, *, binary: bool = False, paginated: bool = False):
        nonlocal requests
        try:
            if requests >= MAX_REQUESTS or time.monotonic() >= deadline:
                rows[label] = {"state": "unavailable", "reason": "budget_exhausted"}
                return None
            requests += 1
            status, raw = reader.get(path)
            value = None if binary else json.loads(raw)
            ok = 200 <= status < 300 and (
                binary or isinstance(value, dict) and value.get("success") is True
            )
            if not ok:
                rows[label] = {"state": "unavailable", "httpStatus": status}
                return None
            (private / (label + ".bin" if binary else label + ".json")).write_bytes(raw)
            info = value.get("result_info") if isinstance(value, dict) else None
            pagination_known = isinstance(info, dict) and all(
                type(info.get(key)) is int and info[key] >= 1
                for key in ("page", "per_page", "total_pages")
            )
            complete_page = (
                isinstance(info, dict)
                and pagination_known
                and info["page"] == 1
                and info["total_pages"] == 1
            )
            rows[label] = {
                "state": "captured",
                "SHA2-256": digest(raw),
                "bytes": len(raw),
                "paginationUnresolved": paginated and not complete_page,
            }
            captured[label] = {"path": path, "SHA2-256": digest(raw)}
            return value.get("result") if isinstance(value, dict) else None
        except OSError, ValueError, TypeError, AttributeError, http.client.HTTPException:
            rows[label] = {"state": "unavailable", "reason": "bounded_read_failed"}
            return None

    prefix = f"/accounts/{reader.account}/workers/scripts/{WORKER}"
    deployments = capture("deployments_before", prefix + "/deployments", paginated=True)
    capture("worker_settings", prefix + "/settings")
    capture("script_settings", prefix + "/script-settings")
    capture("unversioned_artifact", prefix + "/content/v2", binary=True)
    domains = capture(
        "custom_domains",
        f"/accounts/{reader.account}/workers/domains?page=1&per_page=100",
        paginated=True,
    )
    deployment_rows = (
        deployments.get("deployments") if isinstance(deployments, dict) else deployments
    )
    current = deployment_rows[0] if isinstance(deployment_rows, list) and deployment_rows else None
    weighted: dict[str, float] = {}
    versions = current.get("versions") if isinstance(current, dict) else None
    valid_versions = isinstance(versions, list) and 0 < len(versions) <= MAX_VERSIONS
    if isinstance(versions, list) and valid_versions:
        for version in versions:
            identity = version.get("version_id") if isinstance(version, dict) else None
            weight = version.get("percentage") if isinstance(version, dict) else None
            if (
                not isinstance(identity, str)
                or not re.fullmatch(r"[a-f0-9-]{36}", identity)
                or not isinstance(weight, (int, float))
                or isinstance(weight, bool)
                or not 0 < weight <= 100
            ):
                valid_versions = False
                break
            weighted[identity] = weighted.get(identity, 0) + weight
        valid_versions = valid_versions and abs(sum(weighted.values()) - 100) < 0.000001
    if valid_versions:
        for index, identity in enumerate(sorted(weighted)):
            capture(f"active_version_{index}", prefix + "/versions/" + identity)
    zones = capture(
        "zone_lookup", f"/zones?name={HOST}&account.id={reader.account}&per_page=50", paginated=True
    )
    zone = zones[0].get("id") if isinstance(zones, list) and len(zones) == 1 else None
    if isinstance(zone, str) and re.fullmatch(r"[a-f0-9]{32}", zone):
        capture("routes", f"/zones/{zone}/workers/routes")
        capture("zone_settings", f"/zones/{zone}/settings")
        capture("page_rules", f"/zones/{zone}/pagerules?per_page=100", paginated=True)
        for phase in PHASES:
            capture(phase, f"/zones/{zone}/rulesets/phases/{phase}/entrypoint")
    after = capture("deployments_after", prefix + "/deployments", paginated=True)
    stable = deployments is not None and deployments == after
    attached = isinstance(domains, list) and any(
        isinstance(item, dict) and item.get("hostname") == HOST and item.get("service") == WORKER
        for item in domains
    )
    save(
        private / "restoration-inputs.json",
        {
            "accountId": reader.account,
            "worker": WORKER,
            "hostname": HOST,
            "captured": captured,
            "deploymentStable": stable,
            "pinnedActiveVersionWeights": weighted if valid_versions else None,
            "artifactBoundToEveryActiveVersion": False,
            "secretTextValuesReadback": "unavailable; source/plaintext config may be sensitive",
            "restorationReady": False,
            "note": "Inputs only; unavailable secret values and exact restoration need review.",
        },
    )
    receipt = {
        "schemaVersion": 1,
        "capturedAt": datetime.now(UTC).isoformat(),
        "worker": WORKER,
        "hostname": HOST,
        "method": "GET-only Cloudflare API",
        "deploymentStableAcrossCapture": stable,
        "customDomainAttachmentObserved": attached,
        "activeWeightedVersionsValid": valid_versions,
        "artifactBoundToEveryActiveVersion": False,
        "requestCount": requests,
        "limits": {
            "requests": MAX_REQUESTS,
            "versions": MAX_VERSIONS,
            "responseBytes": LIMIT,
            "wallSeconds": TOTAL_SECONDS,
        },
        "observations": rows,
        "inventoryComplete": False,
        "restorationReady": False,
        "privateCaptureDurablyRetained": False,
        "unknowns": [
            "Account-level and recursively executed managed rules are not captured.",
            "Unversioned content is not bound to each weighted active version; rollback unknown.",
            "Provider errors/challenges on actual paths are not exercised by metadata reads.",
            "Nondeployment config changes during capture are not atomically fenced.",
            "Secret values cannot be read back; exact restoration is not established.",
            "Private runner capture needs approved private retention before runner deletion.",
            "A failed or paginated endpoint is unavailable/incomplete, never proof of absence.",
        ],
    }
    save(directory / "existing-photo-inventory-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--bounded-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.bounded_child:
        # A process watchdog bounds the whole operation, including slow-drip reads,
        # DNS/TLS and platform calls that socket timeouts do not bound globally.
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.existing_photo_inventory",
                    "--output-directory",
                    str(args.output_directory),
                    "--bounded-child",
                ],
                timeout=TOTAL_SECONDS,
                capture_output=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print("existing_inventory_total_deadline_exceeded")
            return 1
        print(
            "existing_inventory_capture_finished"
            if result.returncode == 0
            else "existing_inventory_unavailable"
        )
        return 0 if result.returncode == 0 else 1
    try:
        collect(
            Reader(
                os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
                os.environ.get("CLOUDFLARE_API_TOKEN", ""),
            ),
            args.output_directory,
        )
    except OSError, ValueError, http.client.HTTPException:
        print("existing_inventory_unavailable")
        return 1
    print("existing_inventory_capture_finished_with_explicit_unknowns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
