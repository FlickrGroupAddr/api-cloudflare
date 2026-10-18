"""Closed, deliberately incomplete provider configuration metadata projections.

Settings, content, secrets and version detail are refused before dispatch: their
documented response contracts do not meet this collection's no-secret-values
boundary. A projection after receipt cannot repair an unsafe request. Only the
six documented metadata operations below are supported; this is not a baseline
builder or evidence that provider results are complete.
"""

from __future__ import annotations

import copy
import math
import re
from typing import Any

SAFE_SCOPES = (
    "deployments",
    "versions",
    "schedules",
    "script_subdomain",
    "d1_database",
    "zone_routes",
)
GAPS = (
    "full_configuration_unavailable",
    "production_state_and_writers_unproved",
    "isolated_resources_and_receiver_unproved",
    "temporary_version_identity_unproved",
    "provider_completeness_unproved",
)


class ProjectionError(ValueError):
    """Static-code failure; never include any supplied response value."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ProjectionError(code)


def _object(value: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    _require(type(value) is dict, "metadata_object_required")
    _require(set(value) <= allowed, "metadata_unknown_fields")
    _require(required <= set(value), "metadata_missing_fields")
    return value


def _text(value: Any, pattern: str, limit: int = 256) -> str:
    _require(
        type(value) is str and len(value) <= limit and re.fullmatch(pattern, value) is not None,
        "metadata_field_invalid",
    )
    return value


def _identity(value: Any) -> str:
    return _text(value, r"[A-Za-z0-9_-]+", 128)


def _uuid(value: Any) -> str:
    return _text(value, r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}")


def _time(value: Any) -> str:
    return _text(value, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z", 40)


def _number(value: Any, maximum: float) -> int | float:
    _require(
        type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value),
        "metadata_field_invalid",
    )
    return value


def endpoint_for(scope: str, target: Any) -> str:
    """Return an exact bounded GET path; unsupported scopes fail before I/O.

    Only D1 documents server-side field selection. No such option is invented
    for Worker settings or any other operation. List pages are finite first
    pages; their contents never constitute a complete configuration baseline.
    """
    _require(type(scope) is str and scope in SAFE_SCOPES, "metadata_scope_unsafe")
    extra = (
        {"databaseId"}
        if scope == "d1_database"
        else {"zoneId"}
        if scope == "zone_routes"
        else set()
    )
    _object(target, {"accountId", "scriptName"} | extra, {"accountId", "scriptName"} | extra)
    account = _text(target["accountId"], r"[a-fA-F0-9]{32}")
    script = _text(target["scriptName"], r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}")
    base = f"/client/v4/accounts/{account}/workers/scripts/{script}"
    if scope == "d1_database":
        database = _uuid(target["databaseId"])
        return f"/client/v4/accounts/{account}/d1/database/{database}?fields=uuid"
    if scope == "zone_routes":
        zone = _text(target["zoneId"], r"[a-fA-F0-9]{32}")
        return f"/client/v4/zones/{zone}/workers/routes"
    suffix = {
        "deployments": "/deployments",
        "versions": "/versions?page=1&per_page=100",
        "schedules": "/schedules",
        "script_subdomain": "/subdomain",
    }[scope]
    return base + suffix


def _items(value: Any) -> list[Any]:
    _require(type(value) is list and len(value) <= 100, "metadata_list_bound")
    return value


def _pagination(value: Any, count: int) -> None:
    """Reject continuation or inconsistent pagination; absence proves nothing."""
    if value is None:
        return
    info = _object(value, {"count", "page", "per_page", "total_count", "total_pages"}, set())
    for field, number in info.items():
        _require(type(number) is int and number >= 0, "metadata_pagination_invalid")
        if field in ("page", "total_pages"):
            _require(number == 1, "metadata_pagination_incomplete")
        elif field in ("count", "total_count"):
            _require(number == count, "metadata_pagination_incomplete")
        elif field == "per_page":
            _require(number >= count and number <= 100, "metadata_pagination_invalid")


def project_metadata(scope: str, payload: Any, target: Any) -> dict[str, Any]:
    """Copy allowlisted fields into a new private, explicitly incomplete object.

    Known excluded fields (for example author addresses/annotations) are never
    copied. Unknown fields fail closed. Raw payloads, errors and diagnostic
    messages must never be retained or logged by callers, including on failure.
    """
    endpoint_for(scope, target)
    envelope = _object(
        payload,
        {"success", "errors", "messages", "result", "result_info"},
        {"success", "errors", "result"},
    )
    _require(envelope["success"] is True and envelope["errors"] == [], "metadata_provider_failure")
    _require(envelope.get("messages", []) == [], "metadata_provider_messages")
    result = envelope["result"]
    omitted: list[str] = []
    rows: list[dict[str, Any]] = []
    count = 1
    if scope == "deployments":
        result = _object(result, {"deployments"}, {"deployments"})
        for item in _items(result["deployments"]):
            item = _object(
                item,
                {
                    "id",
                    "created_on",
                    "source",
                    "strategy",
                    "versions",
                    "annotations",
                    "author_email",
                },
                {"id", "created_on", "source", "strategy", "versions"},
            )
            _require(item["strategy"] == "percentage", "metadata_strategy_invalid")
            versions = []
            for version in _items(item["versions"]):
                version = _object(
                    version, {"version_id", "percentage"}, {"version_id", "percentage"}
                )
                versions.append(
                    {
                        "version_id": _uuid(version["version_id"]),
                        "percentage": _number(version["percentage"], 100),
                    }
                )
            rows.append(
                {
                    "id": _uuid(item["id"]),
                    "created_on": _time(item["created_on"]),
                    "strategy": "percentage",
                    "versions": versions,
                }
            )
            omitted.extend(
                "deployments." + field
                for field in ("source", "annotations", "author_email")
                if field in item
            )
        metadata: Any = {"deployments": rows}
        count = len(rows)
    elif scope == "versions":
        result = _object(result, {"items"}, {"items"})
        for item in _items(result["items"]):
            item = _object(item, {"id", "number", "metadata", "annotations"}, {"id"})
            row: dict[str, Any] = {"id": _uuid(item["id"])}
            if "number" in item:
                _require(
                    type(item["number"]) is int and item["number"] >= 0, "metadata_field_invalid"
                )
                row["number"] = item["number"]
            if "metadata" in item:
                _object(
                    item["metadata"],
                    {
                        "created_on",
                        "modified_on",
                        "source",
                        "hasPreview",
                        "author_email",
                        "author_id",
                    },
                    set(),
                )
                omitted.append("versions.metadata")
            if "annotations" in item:
                omitted.append("versions.annotations")
            rows.append(row)
        metadata = {"items": rows}
        count = len(rows)
    elif scope == "schedules":
        result = _object(result, {"schedules"}, {"schedules"})
        for item in _items(result["schedules"]):
            item = _object(item, {"cron", "created_on", "modified_on"}, {"cron"})
            row = {"cron": _text(item["cron"], r"[0-9A-Z*/?,#LW -]+", 128)}
            for field in ("created_on", "modified_on"):
                if field in item:
                    row[field] = _time(item[field])
            rows.append(row)
        metadata = {"schedules": rows}
        count = len(rows)
    elif scope == "script_subdomain":
        result = _object(result, {"enabled", "previews_enabled"}, {"enabled", "previews_enabled"})
        _require(all(type(v) is bool for v in result.values()), "metadata_field_invalid")
        metadata = dict(result)
    elif scope == "d1_database":
        result = _object(result, {"uuid"}, {"uuid"})
        _require(_uuid(result["uuid"]) == target["databaseId"], "metadata_target_mismatch")
        metadata = {"uuid": result["uuid"]}
    else:
        for item in _items(result):
            item = _object(item, {"id", "pattern", "script"}, {"id", "pattern"})
            row = {
                "id": _text(item["id"], r"[a-fA-F0-9]{32}"),
                "pattern": _text(item["pattern"], r"[A-Za-z0-9*_.:/%-]+", 512),
            }
            if "script" in item:
                row["script"] = None if item["script"] is None else _identity(item["script"])
            rows.append(row)
        metadata = {"routes": rows}
        count = len(rows)
    _pagination(envelope.get("result_info"), count)
    return {
        "scope": scope,
        "target": copy.deepcopy(target),
        "metadata": metadata,
        "baselineComplete": False,
        "gaps": list(GAPS),
        "omittedFields": sorted(set(omitted)),
    }
