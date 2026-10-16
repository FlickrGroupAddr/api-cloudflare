"""GET-only provider inventory for the existing fixed-origin Worker; never deploys.

Only the allowlisted receipt is suitable for publication. The private directory
contains provider identities, configuration and downloaded source, and must stay private.
"""

from __future__ import annotations

import argparse
import base64
import binascii
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
MAX_REQUESTS = 96
MAX_VERSIONS = 8
MAX_PAGES = 8
MAX_RULESETS = 32
MAX_MODULES = 128
MAX_TOTAL_BYTES = 64 * 1024 * 1024
UUID = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
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
        self.total_bytes = 0
        self.deadline = time.monotonic() + TOTAL_SECONDS

    def get(self, path: str) -> tuple[int, bytes]:
        account = re.escape(self.account)
        allowed = (
            rf"/accounts/{account}/workers/scripts/fga-api/(?:settings|script-settings|"
            rf"content/v2|deployments\?page=[1-8]&per_page=100|versions/{UUID})",
            rf"/accounts/{account}/workers/workers/fga-api/versions/{UUID}\?include=modules",
            rf"/accounts/{account}/workers/domains\?hostname=flickrgroupaddr\.com&service=fga-api",
            rf"/zones\?name=flickrgroupaddr\.com&account\.id={account}&per_page=50",
            r"/zones/[a-f0-9]{32}/(?:workers/routes|settings|pagerules|"
            r"rulesets/phases/(?:" + "|".join(PHASES) + r")/entrypoint)",
            rf"/(?:accounts/{account}|zones/[a-f0-9]{{32}})/rulesets"
            r"(?:\?per_page=50(?:&cursor=[A-Za-z0-9_%=-]{1,1024})?|"
            r"/[a-f0-9]{32}(?:/versions/[0-9]{1,12})?)",
        )
        if not any(re.fullmatch(pattern, path) for pattern in allowed):
            raise ValueError("existing_inventory_path_rejected")
        remaining = self.deadline - time.monotonic()
        if self.calls >= MAX_REQUESTS or remaining <= 0 or self.total_bytes >= MAX_TOTAL_BYTES:
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
            read_limit = min(LIMIT, MAX_TOTAL_BYTES - self.total_bytes)
            raw = response.read(read_limit + 1)
            if not isinstance(response.status, int) or not isinstance(raw, bytes):
                raise ValueError("existing_inventory_invalid_transport")
            self.total_bytes += len(raw)
            if len(raw) > read_limit:
                raise ValueError("existing_inventory_response_limit")
            return response.status, raw


class InventoryReader(Protocol):
    account: str

    def get(self, path: str) -> tuple[int, bytes]: ...


def collect(reader: InventoryReader, directory: Path) -> dict[str, Any]:
    """Capture bounded metadata inputs. Restoration and live edge gates are separate."""
    directory.mkdir(parents=True, exist_ok=False)
    private = directory / "private"
    private.mkdir()
    rows: dict[str, Any] = {}
    captured: dict[str, Any] = {}
    envelopes: dict[str, Any] = {}
    deadline = time.monotonic() + TOTAL_SECONDS
    requests = 0
    total_bytes = 0

    def capture(label: str, path: str, *, binary: bool = False):
        nonlocal requests, total_bytes
        try:
            if (
                requests >= MAX_REQUESTS
                or total_bytes >= MAX_TOTAL_BYTES
                or time.monotonic() >= deadline
            ):
                rows[label] = {"state": "unavailable", "reason": "budget_exhausted"}
                return None
            requests += 1
            status, raw = reader.get(path)
            if type(status) is not int or not isinstance(raw, bytes):
                raise ValueError("transport")
            total_bytes += len(raw)
            if len(raw) > LIMIT or total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("bytes")
            # Failures are retained privately too; provider text never enters the receipt.
            (private / (label + ".bin" if binary else label + ".json")).write_bytes(raw)
            value = None if binary else json.loads(raw)
            ok = 200 <= status < 300 and (
                binary or isinstance(value, dict) and value.get("success") is True
            )
            if not ok:
                rows[label] = {"state": "unavailable", "httpStatus": status}
                return None
            rows[label] = {"state": "captured", "SHA2-256": digest(raw), "bytes": len(raw)}
            captured[label] = {"path": path, "SHA2-256": digest(raw)}
            envelopes[label] = value
            result = value.get("result") if isinstance(value, dict) else None
            if not binary:
                expected = list if label in ("routes", "zone_settings", "page_rules") else None
                if label in ("worker_settings", "script_settings"):
                    expected = dict
                if result is None or expected is not None and not isinstance(result, expected):
                    rows[label]["inputUnresolved"] = True
                    return None
                if expected is list and not all(isinstance(item, dict) for item in result):
                    rows[label]["inputUnresolved"] = True
                    return None
            return result
        except OSError, ValueError, TypeError, AttributeError, http.client.HTTPException:
            rows[label] = {"state": "unavailable", "reason": "bounded_read_failed"}
            return None

    def incomplete(label: str):
        rows[label]["paginationUnresolved"] = True

    prefix = f"/accounts/{reader.account}/workers/scripts/{WORKER}"

    def deployments_read(label: str):
        result = capture(label, prefix + "/deployments?page=1&per_page=100")
        info = (envelopes.get(label) or {}).get("result_info")
        items = result.get("deployments") if isinstance(result, dict) else result
        if not isinstance(items, list):
            incomplete(label)
            return None
        # Only the first page owns active state; history remains explicitly scoped.
        valid = (
            isinstance(info, dict)
            and all(type(info.get(k)) is int and info[k] >= 1 for k in ("page", "per_page"))
            and info["page"] == 1
            and info["per_page"] == 100
        )
        total = info.get("total_count") if isinstance(info, dict) else None
        pages = info.get("total_pages") if isinstance(info, dict) else None
        complete = valid and (
            type(pages) is int
            and pages == 1
            or type(total) is int
            and total == len(items)
            and len(items) <= 100
        )
        rows[label]["paginationUnresolved"] = not complete
        return items

    deployments = deployments_read("deployments_before")
    capture("worker_settings", prefix + "/settings")
    capture("script_settings", prefix + "/script-settings")
    capture("unversioned_artifact", prefix + "/content/v2", binary=True)
    domains = capture(
        "custom_domains",
        f"/accounts/{reader.account}/workers/domains?hostname={HOST}&service={WORKER}",
    )
    info = (envelopes.get("custom_domains") or {}).get("result_info")
    domains_complete = (
        isinstance(domains, list)
        and isinstance(info, dict)
        and (
            type(info.get("count")) is int
            and type(info.get("total_count")) is int
            and info["count"] == info["total_count"] == len(domains)
            and (
                "total_pages" not in info
                or type(info["total_pages"]) is int
                and info["total_pages"] <= 1
            )
        )
    )
    rows["custom_domains"]["paginationUnresolved"] = not domains_complete
    current = deployments[0] if deployments else None
    weighted: dict[str, float] = {}
    versions = current.get("versions") if isinstance(current, dict) else None
    valid_versions = isinstance(versions, list) and 0 < len(versions) <= MAX_VERSIONS
    if isinstance(versions, list) and valid_versions:
        for version in versions:
            identity = version.get("version_id") if isinstance(version, dict) else None
            weight = version.get("percentage") if isinstance(version, dict) else None
            if (
                not isinstance(identity, str)
                or not re.fullmatch(UUID, identity)
                or not isinstance(weight, (int, float))
                or isinstance(weight, bool)
                or not 0 < weight <= 100
            ):
                valid_versions = False
                break
            weighted[identity] = weighted.get(identity, 0) + weight
        valid_versions = valid_versions and abs(sum(weighted.values()) - 100) < 0.000001
    exact = bool(valid_versions)
    module_index: dict[str, Any] = {}
    if valid_versions:
        for index, identity in enumerate(sorted(weighted)):
            label = f"active_version_{index}"
            capture(label, prefix + "/versions/" + identity)
            module_label = label + "_modules"
            value = capture(
                module_label,
                f"/accounts/{reader.account}/workers/workers/"
                f"{WORKER}/versions/{identity}?include=modules",
            )
            try:
                if not isinstance(value, dict) or value.get("id") != identity:
                    raise ValueError("identity")
                modules = value.get("modules")
                if not isinstance(modules, list) or not 0 < len(modules) <= MAX_MODULES:
                    raise ValueError("modules")
                names: set[str] = set()
                index_rows = []
                for module in modules:
                    name = module.get("name") if isinstance(module, dict) else None
                    if (
                        not isinstance(name, str)
                        or len(name) > 256
                        or not re.fullmatch(r"[A-Za-z0-9_.@/-]+", name)
                        or name.startswith("/")
                        or any(x in ("", ".", "..") for x in name.split("/"))
                        or name.casefold() in names
                    ):
                        raise ValueError("module_name")
                    names.add(name.casefold())
                    content = module.get("content_base64")
                    content_type = module.get("content_type")
                    if (
                        not isinstance(content, str)
                        or not isinstance(content_type, str)
                        or not 0 < len(content_type) <= 256
                        or any(ord(char) < 32 for char in content_type)
                    ):
                        raise ValueError("module_content")
                    decoded = base64.b64decode(content, validate=True)
                    if len(decoded) > LIMIT:
                        raise ValueError("module_bytes")
                    index_rows.append(
                        {
                            "name": name,
                            "bytes": len(decoded),
                            "content_type": content_type,
                            "SHA2-256": digest(decoded),
                        }
                    )
                main = value.get("main_module")
                if not isinstance(main, str) or main not in [m["name"] for m in index_rows]:
                    raise ValueError("main_module")
                module_index[identity] = {"main_module": main, "modules": index_rows}
                rows[module_label]["validated"] = True
            except ValueError, TypeError, binascii.Error:
                exact = False
                rows[module_label]["validated"] = False
    zones = capture("zone_lookup", f"/zones?name={HOST}&account.id={reader.account}&per_page=50")
    zone_row = zones[0] if isinstance(zones, list) and len(zones) == 1 else None
    zone = zone_row.get("id") if isinstance(zone_row, dict) else None
    zone_valid = isinstance(zone, str) and re.fullmatch(r"[a-f0-9]{32}", zone) is not None
    zone_valid = bool(
        zone_valid
        and isinstance(zone_row, dict)
        and zone_row.get("name") == HOST
        and isinstance(zone_row.get("account"), dict)
        and zone_row["account"].get("id") == reader.account
    )
    zone_info = (envelopes.get("zone_lookup") or {}).get("result_info")
    zone_complete = (
        zone_valid
        and isinstance(zone_info, dict)
        and (
            type(zone_info.get("total_pages")) is int
            and zone_info["total_pages"] == 1
            or type(zone_info.get("total_count")) is int
            and zone_info["total_count"] == 1
        )
    )
    rows["zone_lookup"]["paginationUnresolved"] = not zone_complete
    if zone_valid:
        capture("routes", f"/zones/{zone}/workers/routes")
        capture("zone_settings", f"/zones/{zone}/settings")
        page_rules = capture("page_rules", f"/zones/{zone}/pagerules")
        if not isinstance(page_rules, list):
            rows["page_rules"]["inputUnresolved"] = True
    else:
        for label in ("routes", "zone_settings", "page_rules"):
            rows[label] = {"state": "unavailable", "reason": "scope_unavailable"}

    ruleset_nodes = 0
    visited: set[tuple[str, str, str]] = set()
    graph_complete = True
    catalog: dict[str, str] = {}
    roots: list[tuple[str, str, str]] = []

    def ruleset_read(
        scope: str,
        identity: str,
        version: str = "",
        ancestors: frozenset[tuple[str, str]] = frozenset(),
    ):
        nonlocal ruleset_nodes, graph_complete
        node = (scope, identity)
        if node in ancestors:
            graph_complete = False
            rows["ruleset_cycle"] = {"state": "unavailable", "reason": "cyclic_input"}
            return
        key = (scope, identity, version)
        if key in visited:
            return
        visited.add(key)
        if ruleset_nodes >= MAX_RULESETS:
            graph_complete = False
            rows["ruleset_graph_limit"] = {"state": "unavailable", "reason": "budget_exhausted"}
            return
        label = f"ruleset_{ruleset_nodes}"
        ruleset_nodes += 1
        path = scope + "/rulesets/" + identity + ("/versions/" + version if version else "")
        value = capture(label, path)
        if (
            not isinstance(value, dict)
            or value.get("id") != identity
            or not isinstance(value.get("version"), str)
            or not re.fullmatch(r"[0-9]{1,12}", value["version"])
            or version
            and value["version"] != version
            or not isinstance(value.get("rules"), list)
        ):
            graph_complete = False
            rows[label]["inputUnresolved"] = True
            return
        for rule in value["rules"]:
            if not isinstance(rule, dict) or not isinstance(rule.get("action"), str):
                graph_complete = False
                rows[label]["inputUnresolved"] = True
                continue
            if rule.get("action") != "execute":
                continue
            params = rule.get("action_parameters")
            target = params.get("id") if isinstance(params, dict) else None
            target_version = params.get("version", "") if isinstance(params, dict) else None
            if (
                not isinstance(target, str)
                or not re.fullmatch(r"[a-f0-9]{32}", target)
                or not isinstance(target_version, str)
                or target_version
                and target_version != "latest"
                and not re.fullmatch(r"[0-9]{1,12}", target_version)
            ):
                graph_complete = False
                rows[label]["inputUnresolved"] = True
                continue
            # Managed rulesets are account resources even when executed by a zone.
            target_scope = catalog.get(target, f"/accounts/{reader.account}")
            ruleset_read(
                target_scope,
                target,
                "" if target_version == "latest" else target_version,
                ancestors | {node},
            )

    def ruleset_scope(label: str, scope: str):
        nonlocal graph_complete
        cursor = ""
        cursors: set[str] = set()
        entries = []
        complete = False
        for page in range(MAX_PAGES):
            page_label = f"{label}_page_{page}"
            result = capture(
                page_label,
                scope + "/rulesets?per_page=50" + ("&cursor=" + cursor if cursor else ""),
            )
            envelope = envelopes.get(page_label) or {}
            if not isinstance(result, list) or len(result) > 50:
                break
            # The Rulesets API declares result_info optional. Installed Wrangler
            # 4.116.0's CursorPagination also treats its absence as terminal and
            # reads result_info.cursor, never HTTP Link headers. Current docs use
            # result_info.cursors.after; support both and reject conflicting values.
            # https://developers.cloudflare.com/api/resources/rulesets/methods/list/
            after = None
            if "result_info" in envelope:
                info = envelope["result_info"]
                if not isinstance(info, dict):
                    break
                candidates = []
                if "cursor" in info:
                    candidates.append(info["cursor"])
                if "cursors" in info:
                    page_cursors = info["cursors"]
                    if not isinstance(page_cursors, dict):
                        break
                    if "after" in page_cursors:
                        candidates.append(page_cursors["after"])
                if (
                    any(
                        not isinstance(item, str)
                        or not re.fullmatch(r"[A-Za-z0-9_%=-]{1,1024}", item)
                        for item in candidates
                    )
                    or len(set(candidates)) > 1
                ):
                    break
                after = candidates[0] if candidates else None
            entries.extend(result)
            if after is None:
                complete = True
                break
            if (
                not isinstance(after, str)
                or not re.fullmatch(r"[A-Za-z0-9_%=-]{1,1024}", after)
                or after in cursors
            ):
                break
            cursors.add(after)
            cursor = after
        rows[label] = {
            "state": "captured" if complete else "unavailable",
            "paginationUnresolved": not complete,
            "configuredEntrypoints": 0,
        }
        if not complete:
            graph_complete = False
        seen: set[str] = set()
        for entry in entries:
            identity = entry.get("id") if isinstance(entry, dict) else None
            version = entry.get("version") if isinstance(entry, dict) else None
            if (
                not isinstance(entry, dict)
                or entry.get("kind") not in ("root", "zone", "managed", "custom", "schema")
                or not isinstance(identity, str)
                or not re.fullmatch(r"[a-f0-9]{32}", identity)
                or identity in seen
                or not isinstance(entry.get("phase"), str)
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", entry["phase"])
                or not isinstance(version, str)
                or not re.fullmatch(r"[0-9]{1,12}", version)
            ):
                graph_complete = False
                rows[label]["inputUnresolved"] = True
                continue
            seen.add(identity)
            catalog[identity] = scope
            if entry["kind"] not in ("root", "zone"):
                continue
            rows[label]["configuredEntrypoints"] += 1
            roots.append((scope, identity, version))

    ruleset_scope("account_rulesets", f"/accounts/{reader.account}")
    if zone_valid:
        ruleset_scope("zone_rulesets", f"/zones/{zone}")
    else:
        graph_complete = False
        rows["zone_rulesets"] = {"state": "unavailable", "reason": "scope_unavailable"}
    for root in roots:
        ruleset_read(*root)
    after = deployments_read("deployments_after")
    stable = deployments is not None and deployments == after
    attached = isinstance(domains, list) and any(
        isinstance(item, dict)
        and item.get("hostname") == HOST
        and item.get("service") == WORKER
        and item.get("enabled") is True
        for item in domains
    )
    metadata_complete = bool(
        stable
        and attached
        and valid_versions
        and exact
        and domains_complete
        and zone_complete
        and graph_complete
        and all(
            row["state"] == "captured" and not row.get("inputUnresolved", False)
            for row in rows.values()
        )
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
            "exactVersionModules": module_index,
            "artifactBoundToEveryActiveVersion": exact,
            "secretRestoration": "Retained-version preservation needs rehearsal; no secret export.",
            "restorationReady": False,
        },
    )
    receipt = {
        "schemaVersion": 2,
        "capturedAt": datetime.now(UTC).isoformat(),
        "worker": WORKER,
        "hostname": HOST,
        "method": "GET-only Cloudflare API",
        "deploymentStableAcrossCapture": stable,
        "customDomainAttachmentObserved": attached,
        "activeWeightedVersionsValid": valid_versions,
        "artifactBoundToEveryActiveVersion": exact,
        "requestCount": requests,
        "totalResponseBytes": total_bytes,
        "limits": {
            "requests": MAX_REQUESTS,
            "versions": MAX_VERSIONS,
            "pagesPerScope": MAX_PAGES,
            "rulesets": MAX_RULESETS,
            "responseBytes": LIMIT,
            "totalBytes": MAX_TOTAL_BYTES,
            "wallSeconds": TOTAL_SECONDS,
        },
        "observations": rows,
        "metadataInputsComplete": metadata_complete,
        "rulesetGraphComplete": graph_complete,
        "inventoryComplete": metadata_complete,
        "restorationReady": False,
        "edgeBehaviorQualified": False,
        "privateCaptureDurablyRetained": False,
        "unknowns": [
            "Metadata capture does not exercise provider errors/challenges on actual paths.",
            "Nondeployment settings are capture-time observations without an atomic fence.",
            "Retained-version restoration and changed-secret semantics require separate rehearsal.",
            "Durable private retention requires independent local-destination validation.",
            "Incomplete endpoints never establish absence; deployment history is out of scope.",
        ],
    }
    save(directory / "existing-photo-inventory-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument(
        "--token-file", type=Path, help="Private local token file; contents never enter argv"
    )
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
                    *(["--token-file", str(args.token_file)] if args.token_file else []),
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
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        if args.token_file:
            with args.token_file.open("r", encoding="utf-8") as source:
                token = source.read(8193).strip()
            if len(token) > 8192 or "\n" in token or "\r" in token:
                raise ValueError("existing_inventory_credentials_unavailable")
        collect(
            Reader(
                os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
                token,
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
