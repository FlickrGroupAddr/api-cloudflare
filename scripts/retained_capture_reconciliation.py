"""Reconcile caller-supplied retained capture bytes without opening any resource.

The independently retained index digest is a required trust input. A matching
corpus establishes historical correspondence only, never present deployment or
write-only secret equality. Source and embedded locators are inert bytes.
"""

from __future__ import annotations

import base64
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from scripts import existing_photo_inventory as inventory

INDEX_LIMIT = 1024 * 1024
CORPUS_LIMIT = inventory.MAX_TOTAL_BYTES + inventory.LIMIT


def _require(ok: bool) -> None:
    if not ok:
        raise ValueError("retained_capture_rejected")


def _pairs(items):
    value = {}
    for key, item in items:
        _require(key not in value)
        value[key] = item
    return value


def _json(raw: bytes) -> Any:
    def finite_float(value: str):
        parsed = float(value)
        _require(math.isfinite(parsed))
        return parsed

    return json.loads(
        raw,
        object_pairs_hook=_pairs,
        parse_constant=lambda _: _require(False),
        parse_float=finite_float,
    )


def _same_json(left, right):
    # Python equality aliases booleans with integers; the capture format does not.
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


class _MemoryPath:
    """Only collector output operations, deliberately no filesystem methods."""

    def __init__(self, files: dict[str, bytes], name: str = ""):
        self.files, self.name = files, name

    def __truediv__(self, name: str):
        return _MemoryPath(self.files, self.name + "/" + name)

    def mkdir(self, **_kwargs):
        pass

    def write_bytes(self, raw: bytes):
        _require(self.name not in self.files)
        self.files[self.name] = raw

    def write_text(self, value: str, **_kwargs):
        self.write_bytes(value.encode("utf-8"))


class _Replay:
    def __init__(self, account: str, responses: dict[str, bytes]):
        self.account, self.responses = account, responses
        self.consumed: set[str] = set()

    def get(self, path: str) -> tuple[int, bytes]:
        _require(path in self.responses)
        # The two deployment observations intentionally use the same selector.
        self.consumed.add(path)
        return 200, self.responses[path]


def reconcile(
    index_raw: bytes,
    receipt_raw: bytes,
    files: tuple[tuple[str, bytes], ...],
    *,
    expected_index_sha2_256: str,
) -> dict[str, Any]:
    """Return a fixed public-safe result, including on malformed/private input.

    Files are exact private/ basenames from the existing integrity-index consumer;
    the integrity index itself and collector receipt are supplied separately.
    No self-generated digest is a substitute for the independently retained pin.
    """
    try:
        return _reconcile(index_raw, receipt_raw, files, expected_index_sha2_256)
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
        OverflowError,
    ):
        return _result(False)


def _result(matched: bool) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "historicalCaptureCorrespondence": "matched" if matched else "unresolved",
        "secretState": "unknown",
        "currentDeploymentQualified": False,
        "prospectiveAttributionQualified": False,
        "restorationReady": False,
        "edgeBehaviorQualified": False,
        "executionAuthorized": False,
    }


def _reconcile(index_raw: bytes, receipt_raw: bytes, files: Any, pin: str):
    _require(type(index_raw) is bytes and len(index_raw) <= INDEX_LIMIT)
    _require(type(receipt_raw) is bytes and len(receipt_raw) <= INDEX_LIMIT)
    _require(type(pin) is str and re.fullmatch(r"[0-9a-f]{64}", pin) is not None)
    _require(inventory.digest(index_raw) == pin)
    _require(type(files) is tuple and 1 <= len(files) <= inventory.MAX_REQUESTS + 1)
    contents: dict[str, bytes] = {}
    total = 0
    for entry in cast(tuple[tuple[str, bytes], ...], files):
        _require(type(entry) is tuple and len(entry) == 2)
        name, raw = entry
        _require(type(name) is str and type(raw) is bytes and len(raw) <= inventory.LIMIT)
        _require(name not in contents)
        total += len(raw)
        _require(total <= CORPUS_LIMIT)
        contents[name] = raw
    index = _json(index_raw)
    rows = index["files"]
    _require(type(rows) is list and len(rows) == len(contents))
    names = set()
    for row in rows:
        _require(type(row) is dict and set(row) == {"name", "bytes", "sha256"})
        name = row["name"]
        _require(type(name) is str and name not in names and name in contents)
        names.add(name)
        _require(type(row["bytes"]) is int and row["bytes"] == len(contents[name]))
        _require(row["sha256"] == inventory.digest(contents[name]))
    _require(names == set(contents) and "restoration-inputs.json" in contents)
    restoration = _json(contents["restoration-inputs.json"])
    receipt = _json(receipt_raw)
    _require(type(restoration) is dict and type(receipt) is dict)
    timestamp = receipt["capturedAt"]
    _require(type(timestamp) is str and len(timestamp) <= 64)
    _require(datetime.fromisoformat(timestamp).utcoffset() is not None)
    account = restoration["accountId"]
    _require(type(account) is str and re.fullmatch(r"[0-9a-f]{32}", account) is not None)
    captured = restoration["captured"]
    _require(type(captured) is dict and 1 <= len(captured) <= inventory.MAX_REQUESTS)
    responses = {}
    payload_names = set()
    for label, row in captured.items():
        _require(type(label) is str and re.fullmatch(r"[a-z0-9_]{1,64}", label) is not None)
        _require(type(row) is dict and set(row) == {"path", "SHA2-256"})
        filename = label + (".bin" if label == "unversioned_artifact" else ".json")
        _require(filename in contents)
        raw = contents[filename]
        _require(row["SHA2-256"] == inventory.digest(raw))
        path = row["path"]
        _require(type(path) is str and len(path) <= 2048)
        if path in responses:
            _require(label == "deployments_after" and responses[path] == raw)
        responses[path] = raw
        payload_names.add(filename)
        if filename.endswith(".json"):
            _json(raw)  # Reject duplicate keys before the existing collector parses it.
    _require(payload_names | {"restoration-inputs.json"} == set(contents))
    replay = _Replay(account, responses)
    outputs: dict[str, bytes] = {}
    observed = inventory.collect(
        replay, cast(Path, _MemoryPath(outputs)), monotonic=lambda: 0, captured_at=timestamp
    )
    _require(observed["metadataInputsComplete"] is True)
    _require(replay.consumed == set(responses))
    _require(_same_json(_json(outputs["/private/restoration-inputs.json"]), restoration))
    _require(
        set(outputs)
        == {"/private/" + n for n in contents} | {"/existing-photo-inventory-receipt.json"}
    )
    for name, raw in contents.items():
        if name != "restoration-inputs.json":
            _require(outputs["/private/" + name] == raw)
    _require(set(receipt) == set(observed))
    _require(_same_json(receipt, observed))
    before = _json(contents["deployments_before.json"])["result"]
    deployments = before["deployments"] if isinstance(before, dict) else before
    versions = deployments[0]["versions"]
    ids = [v["version_id"] for v in versions]
    _require(len(set(ids)) == len(ids))
    for i, identity in enumerate(sorted(ids)):
        metadata = _json(contents[f"active_version_{i}.json"])["result"]
        _require(metadata["id"] == identity)
        module = _json(contents[f"active_version_{i}_modules.json"])["result"]
        for item in module["modules"]:
            encoded = item["content_base64"]
            _require(base64.b64encode(base64.b64decode(encoded, validate=True)).decode() == encoded)
    return _result(True)
