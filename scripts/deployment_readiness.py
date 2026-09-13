"""Read-only account/DNS preflight; no provisioning, DNS edits, or Flickr calls."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import runtime_permissions_probe as runtime
from scripts.secret_store_probe import private_process

ROOT = runtime.ROOT
DOMAIN = "flickrgroupaddr.com"
DEFAULT_PROFILE_DIRECTORY = Path(r"C:\Users\TDO-XPS15-2024\Documents\ChatGPT\FGA")


def token(default_profile: bool = False) -> str:
    args = [runtime.NODE, str(runtime.WRANGLER), "auth", "token", "--json"]
    if default_profile:
        args += ["--cwd", str(DEFAULT_PROFILE_DIRECTORY)]
    result = private_process(args)
    if result.returncode:
        raise RuntimeError("operator_auth_unavailable")
    value = json.loads(result.stdout)
    if value.get("type") not in {"oauth", "api_token"} or not value.get("token"):
        raise RuntimeError("operator_auth_unavailable")
    return value["token"]


def get(path: str, credential: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/" + path,
        headers={
            "Authorization": "Bearer " + credential,
            "User-Agent": "FlickrGroupAddr-DeploymentReadiness/1",
        },
    )
    try:
        response = urllib.request.build_opener(runtime.NoRedirect).open(request, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read(2_097_153)
        if len(payload) > 2_097_152:
            raise RuntimeError("control_response_over_budget")
        status = response.status
        value = json.loads(payload)
        if not isinstance(status, int) or not isinstance(value, dict):
            raise RuntimeError("control_response_invalid")
        return status, value


def zone(account: str, credential: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"[a-f0-9]{32}", account):
        raise RuntimeError("account_configuration_invalid")
    status, value = get(
        "zones?" + urllib.parse.urlencode({"account.id": account, "name": DOMAIN}), credential
    )
    if status != 200 or value.get("success") is not True:
        raise RuntimeError("zone_inventory_unavailable")
    rows = value.get("result", [])
    if len(rows) > 1:
        raise RuntimeError("zone_inventory_ambiguous")
    return rows[0] if rows else None


def main() -> int:
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "domain": DOMAIN,
        "checkedAt": datetime.now(UTC).isoformat(),
        "readOnly": True,
        "productionReady": False,
    }
    try:
        inputs = json.loads(
            (ROOT / ".coordination-runs/fga-runtime-inputs.json").read_text(encoding="utf-8")
        )
        target = zone(inputs["accountId"], token())
        report["targetZonePresent"] = target is not None
        report["targetZoneStatus"] = target.get("status") if target else None
        report["targetNameServers"] = target.get("name_servers", []) if target else []
        blockers = []
        if target is None:
            blockers.append("target_zone_missing")
        elif target.get("status") != "active":
            blockers.append("target_zone_not_active")
        if target is None and inputs.get("previousAccountId"):
            previous_token = token(default_profile=True)
            previous = zone(inputs["previousAccountId"], previous_token)
            report["sourceZonePresent"] = previous is not None
            if previous:
                report["sourceNameServers"] = previous.get("name_servers", [])
                status, value = get(
                    "zones/" + previous["id"] + "/dns_records?per_page=1", previous_token
                )
                report["sourceDnsReadHttpStatus"] = status
                if status != 200 or value.get("success") is not True:
                    blockers.append("source_dns_export_unavailable")
                status, value = get("zones/" + previous["id"] + "/dnssec", previous_token)
                report["sourceDnssecReadHttpStatus"] = status
                if status != 200 or value.get("success") is not True:
                    blockers.append("source_dnssec_unverified")
        report["blockers"] = blockers
        # This checks infrastructure prerequisites, not code/release conformance.
        report["dnsAccountPrerequisiteReady"] = not blockers
    except OSError, ValueError, KeyError, RuntimeError:
        report["blockers"] = ["readiness_check_unavailable"]
    destination = ROOT / ".coordination-runs/deployment-readiness.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("dnsAccountPrerequisiteReady") else 1


if __name__ == "__main__":
    raise SystemExit(main())
