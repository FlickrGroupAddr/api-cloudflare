"""Bounded supported Cloudflare REST census; not a closed snapshot or source oracle.

MIT License; copyright 2026 Terry Ott. No CLI, discovery default, credentials on
disk, SDK auto-pagination, retry, provider mutation, or object invocation.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode


class Refused(ValueError):
    """Sanitized category only; never include provider bodies or credentials."""


@dataclass(frozen=True)
class Bounds:
    calls: int = 64
    pages: int = 32
    namespaces: int = 128
    objects: int = 128
    response_bytes: int = 262144
    total_bytes: int = 4194304
    milliseconds: int = 30000


DEFAULT_BOUNDS = Bounds()


class Get(Protocol):
    def __call__(self, path: str, cap: int, remaining: float) -> bytes: ...


class HttpsGet:
    """Permanently disabled native census transport, pending separate qualification.

    No enable flag, token retention, DNS, socket, TLS, HTTP or retry implementation
    exists here. Census accepts a test/model Get; that port is no actual permit.
    """

    def __init__(self, token: str):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{10,256}", token):
            raise Refused("invalid_token_shape")

    def __call__(self, path: str, cap: int, remaining: float) -> bytes:
        raise Refused("native_census_transport_unqualified")


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise Refused("invalid_census_shape")
    return value


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Refused("duplicate_json_key")
        result[key] = value
    return result


def _non_json_number(_: str) -> Any:
    raise Refused("non_json_number")


def _integer(value: Any, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise Refused("invalid_census_integer")
    return value


def _id(value: Any, width: int) -> str:
    if not isinstance(value, str) or not re.fullmatch(rf"[a-f0-9]{{{width}}}", value):
        raise Refused("invalid_census_identity")
    return value


def _namespace(value: Any) -> dict[str, Any]:
    row = _object(value)
    if set(row) != {"id", "class", "name", "script", "use_sqlite"}:
        raise Refused("unknown_namespace_metadata")
    _id(row["id"], 32)
    if type(row["use_sqlite"]) is not bool or any(
        not isinstance(row[key], str) or not 1 <= len(row[key].encode("utf-8")) <= 4096
        for key in ("class", "name", "script")
    ):
        raise Refused("invalid_namespace_metadata")
    return row.copy()


class Census:
    def __init__(self, account: str, get: Get, bounds: Bounds = DEFAULT_BOUNDS):
        self._account = _id(account, 32)
        for key, ceiling in vars(Bounds()).items():
            value = getattr(bounds, key)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise Refused("invalid_census_bounds")
        self._get, self._bounds = get, bounds
        self._calls = self._bytes = self._pages = 0
        self._deadline = time.monotonic() + bounds.milliseconds / 1000
        self._spent = False

    def _read(self, suffix: str) -> dict[str, Any]:
        self._calls += 1
        self._pages += 1
        if self._calls > self._bounds.calls or self._pages > self._bounds.pages:
            raise Refused("census_call_bound")
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise Refused("census_elapsed_bound")
        cap = min(self._bounds.response_bytes, self._bounds.total_bytes - self._bytes)
        if cap <= 0:
            raise Refused("census_aggregate_byte_bound")
        path = f"/client/v4/accounts/{self._account}/workers/durable_objects/{suffix}"
        try:
            raw = self._get(path, cap, remaining)
        except Refused:
            raise
        except Exception:
            raise Refused("census_read_unknown") from None
        if not isinstance(raw, bytes) or len(raw) > cap:
            raise Refused("response_byte_bound")
        self._bytes += len(raw)
        if time.monotonic() > self._deadline:
            raise Refused("census_elapsed_bound")
        try:
            value = _object(
                json.loads(
                    raw.decode("utf-8"),
                    object_pairs_hook=_unique,
                    parse_constant=_non_json_number,
                )
            )
        except Refused:
            raise
        except UnicodeError, ValueError, RecursionError:
            raise Refused("invalid_census_json") from None
        if set(value) != {"result", "result_info", "success", "errors", "messages"}:
            raise Refused("unknown_census_envelope")
        if value["success"] is not True or value["errors"] != [] or value["messages"] != []:
            raise Refused("census_api_unknown")
        if not isinstance(value["result"], list):
            raise Refused("invalid_census_shape")
        _object(value["result_info"])
        return value

    def collect(
        self,
        expected_account_namespaces: list[dict[str, Any]],
        expected_objects: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Reconcile a separately retained inventory. Never invent expected IDs.

        All account namespace metadata is reconciled, but object enumeration is
        limited to the explicitly selected independently retained namespace IDs.
        hasStoredData=false objects remain included. An equal census is merely
        bounded observation: REST documents no common closed snapshot interval.
        """
        if self._spent:
            raise Refused("census_once_only")
        self._spent = True  # Failure/unknown outcome also spends this instance.
        # Freeze the independent input before the first transport callback.
        try:
            expected_ns = [
                _namespace(row) for row in json.loads(json.dumps(expected_account_namespaces))
            ]
            expected = json.loads(json.dumps(expected_objects))
        except Refused:
            raise
        except ValueError, TypeError, UnicodeError:
            raise Refused("invalid_expected_inventory") from None
        if len(expected_ns) > self._bounds.namespaces or len(
            {row["id"] for row in expected_ns}
        ) != len(expected_ns):
            raise Refused("namespace_bound_or_duplicate")
        selected = _object(expected)
        allowed = {row["id"] for row in expected_ns if row["use_sqlite"]}
        if not selected or not set(selected) <= allowed:
            raise Refused("unknown_selected_namespace")
        total_expected = 0
        for namespace, objects in selected.items():
            _id(namespace, 32)
            if not isinstance(objects, list):
                raise Refused("invalid_expected_inventory")
            ids = set()
            for row in objects:
                if (
                    set(_object(row)) != {"id", "hasStoredData"}
                    or type(row["hasStoredData"]) is not bool
                ):
                    raise Refused("invalid_expected_object")
                if _id(row["id"], 64) in ids:
                    raise Refused("duplicate_expected_object")
                ids.add(row["id"])
            total_expected += len(objects)
        if total_expected > self._bounds.objects:
            raise Refused("object_bound")
        namespaces: list[dict[str, Any]] = []
        page = 1
        total = None
        while True:
            value = self._read("namespaces?" + urlencode({"page": page, "per_page": 10}))
            info = value["result_info"]
            if set(info) != {"page", "per_page", "count", "total_count", "total_pages"}:
                raise Refused("namespace_pagination_unknown")
            for field, maximum in {
                "page": self._bounds.pages,
                "per_page": 10,
                "count": 10,
                "total_count": self._bounds.namespaces,
                "total_pages": self._bounds.pages,
            }.items():
                _integer(info[field], maximum)
            n = _integer(info["total_count"], self._bounds.namespaces)
            if total is not None and n != total:
                raise Refused("namespace_pagination_drift")
            total = n
            pages = max(1, (n + 9) // 10)
            rows = value["result"]
            if (
                info["page"] != page
                or info["per_page"] != 10
                or info["total_pages"] != pages
                or info["count"] != len(rows)
                or len(rows) != min(10, max(0, n - len(namespaces)))
            ):
                raise Refused("namespace_pagination_unknown")
            namespaces.extend(_namespace(row) for row in rows)
            if len({row["id"] for row in namespaces}) != len(namespaces):
                raise Refused("duplicate_namespace")
            if page == pages:
                break
            page += 1
        if sorted(namespaces, key=lambda row: row["id"]) != sorted(
            expected_ns, key=lambda row: row["id"]
        ):
            raise Refused("namespace_population_mismatch")
        observed: dict[str, list[dict[str, Any]]] = {}
        object_count = 0
        for namespace in sorted(selected):
            cursor = None
            cursors: set[str] = set()
            rows = []
            identities: set[str] = set()
            while True:
                params = {"limit": "10"}
                if cursor is not None:
                    params["cursor"] = cursor
                value = self._read(f"namespaces/{namespace}/objects?" + urlencode(params))
                info = value["result_info"]
                # Cursor is the documented continuation. Optional counts cannot
                # prove snapshot consistency; reject unfamiliar metadata.
                if (
                    not set(info)
                    <= {"cursor", "count", "page", "per_page", "total_count", "total_pages"}
                    or "cursor" not in info
                ):
                    raise Refused("object_pagination_unknown")
                for field, maximum in {
                    "count": 10,
                    "page": self._bounds.pages,
                    "per_page": 10,
                    "total_count": self._bounds.objects,
                    "total_pages": self._bounds.pages,
                }.items():
                    if field in info:
                        _integer(info[field], maximum)
                batch = value["result"]
                if len(batch) > 10 or (
                    "count" in info and _integer(info["count"], 10) != len(batch)
                ):
                    raise Refused("object_page_bound")
                for row in batch:
                    if (
                        set(_object(row)) != {"id", "hasStoredData"}
                        or type(row["hasStoredData"]) is not bool
                    ):
                        raise Refused("unknown_object_metadata")
                    identity = _id(row["id"], 64)
                    if identity in identities:
                        raise Refused("duplicate_object")
                    identities.add(identity)
                    rows.append(row.copy())
                    object_count += 1
                    if object_count > self._bounds.objects:
                        raise Refused("object_bound")
                following = info["cursor"]
                if following in (None, ""):
                    break
                if (
                    not isinstance(following, str)
                    or len(following.encode()) > 4096
                    or following in cursors
                    or not batch
                ):
                    raise Refused("object_cursor_unknown")
                cursors.add(following)
                cursor = following
            if sorted(rows, key=lambda row: row["id"]) != sorted(
                selected[namespace], key=lambda row: row["id"]
            ):
                raise Refused("object_population_mismatch")
            observed[namespace] = sorted(rows, key=lambda row: row["id"])
        return {
            "schema": "pmb1-native-census-observation-v1",
            "completeSnapshot": False,
            "actualQualification": False,
            "accountNamespaces": namespaces,
            "objects": observed,
            "calls": self._calls,
            "bytes": self._bytes,
        }
