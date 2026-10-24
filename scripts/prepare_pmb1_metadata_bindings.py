"""Offline target-binding decoder and exact metadata request preparation.

No file/network/process/credential access. Caller supplies bounded nonsecret bytes.
Output is always inert; syntax and matching references authenticate no fact.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

TARGETS = (
    "accountId",
    "retainedWorkerId",
    "temporaryWorkerId",
    "domainDatabaseId",
    "sharedMainJournalEvidenceDatabaseId",
    "oracleDatabaseId",
)
MAX_INPUT_BYTES = 65536
MAX_RECORD_BYTES = 262144
ERRORS = frozenset(
    {
        "TYPE_OR_UNKNOWN_FIELD",
        "DUPLICATE_FACT",
        "INPUT_SIZE",
        "JSON_INVALID",
        "EXACT_ACTUAL_RECORD_UNBOUND",
        "TARGET_MISMATCH",
        "UNSUPPORTED_SELECTOR",
        "WINDOW_INVALID",
    }
)


class BindingError(ValueError):
    """Closed code only; supplied private values never appear in exceptions."""


def require(ok, code):
    if not ok:
        raise BindingError(code)


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys), "TYPE_OR_UNKNOWN_FIELD")


def text(value, pattern, maximum=256):
    require(
        type(value) is str and len(value) <= maximum and re.fullmatch(pattern, value) is not None,
        "TYPE_OR_UNKNOWN_FIELD",
    )


def utc(value):
    text(value, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", 32)
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise BindingError("WINDOW_INVALID") from None


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_FACT")
        result[key] = value
    return result


def reject_constant(_):
    raise BindingError("JSON_INVALID")


def decode_bindings(raw: bytes, *, expected_record_path: str):
    """Decode supplied bytes only. No path is dereferenced or ACL inspected."""
    require(
        type(expected_record_path) is str and 0 < len(expected_record_path) <= 1024,
        "UNSUPPORTED_SELECTOR",
    )
    require(type(raw) is bytes and 0 < len(raw) <= MAX_INPUT_BYTES, "INPUT_SIZE")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except BindingError:
        raise
    except ValueError, UnicodeError, RecursionError:
        raise BindingError("JSON_INVALID") from None
    closed(value, {"schemaVersion", "kind", "targets", "references"})
    require(
        type(value["schemaVersion"]) is int and value["schemaVersion"] == 1, "TYPE_OR_UNKNOWN_FIELD"
    )
    require(value["kind"] == "0201_offline_target_bindings", "TYPE_OR_UNKNOWN_FIELD")
    closed(value["targets"], TARGETS)
    closed(value["references"], TARGETS)
    require(
        all(
            value["targets"][key] is not None and value["references"][key] is not None
            for key in TARGETS
        ),
        "EXACT_ACTUAL_RECORD_UNBOUND",
    )
    for key in TARGETS:
        target = value["targets"][key]
        if key == "accountId":
            text(target, r"[a-fA-F0-9]{32}")
        elif key.endswith("WorkerId"):
            text(target, r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}")
        else:
            text(target, r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}")
        ref = value["references"][key]
        closed(
            ref,
            {
                "recordPath",
                "selector",
                "sha2_256",
                "maximumBytes",
                "acquisitionPrincipalSid",
                "observedAt",
            },
        )
        require(ref["recordPath"] == expected_record_path, "UNSUPPORTED_SELECTOR")
        require(ref["selector"] == "/targets/" + key, "UNSUPPORTED_SELECTOR")
        text(ref["sha2_256"], r"[a-f0-9]{64}")
        require(
            type(ref["maximumBytes"]) is int and 1 <= ref["maximumBytes"] <= MAX_RECORD_BYTES,
            "INPUT_SIZE",
        )
        text(ref["acquisitionPrincipalSid"], r"S-1-5-\d+(?:-\d+){0,14}", 184)
        utc(ref["observedAt"])
    refs = list(value["references"].values())
    require(
        len({r["sha2_256"] for r in refs}) == 1
        and len({r["maximumBytes"] for r in refs}) == 1
        and len({r["acquisitionPrincipalSid"] for r in refs}) == 1
        and len({r["observedAt"] for r in refs}) == 1,
        "TARGET_MISMATCH",
    )
    targets = value["targets"]
    require(targets["retainedWorkerId"] != targets["temporaryWorkerId"], "TARGET_MISMATCH")
    require(
        len({targets[k].lower() for k in TARGETS if k.endswith("DatabaseId")}) == 3,
        "TARGET_MISMATCH",
    )
    return value


def prepare_metadata_requests(raw: bytes, endpoint_for, *, expected_record_path: str):
    """Prepare seven exact safe paths using the pinned existing pure projector.

    endpoint_for is trusted SOURCE code injection for offline use only, not an
    actual authority boundary. No collector or transport is imported here.
    """
    value = decode_bindings(raw, expected_record_path=expected_record_path)
    target = value["targets"]
    requests = []
    for role, database in (
        ("DB", "domainDatabaseId"),
        ("PMB1_MAIN_JOURNAL", "sharedMainJournalEvidenceDatabaseId"),
        ("ORACLE_DB", "oracleDatabaseId"),
    ):
        # Existing endpoint_for requires scriptName even for the D1 URL. It is
        # source API shape, not proof that the supplied Worker owns the database.
        script_key = "temporaryWorkerId" if role == "ORACLE_DB" else "retainedWorkerId"
        item = {
            "accountId": target["accountId"],
            "scriptName": target[script_key],
            "databaseId": target[database],
        }
        requests.append({"role": role, "scope": "d1_database", "target": item})
    for role, key in (("retained", "retainedWorkerId"), ("temporary", "temporaryWorkerId")):
        for scope in ("deployments", "versions"):
            requests.append(
                {
                    "role": role,
                    "scope": scope,
                    "target": {"accountId": target["accountId"], "scriptName": target[key]},
                }
            )
    for item in requests:
        try:
            item["path"] = endpoint_for(item["scope"], item["target"])
        except Exception:
            raise BindingError("UNSUPPORTED_SELECTOR") from None
        item["method"] = "GET"
        item["enabled"] = False
    require(len({item["path"] for item in requests}) == 7, "TARGET_MISMATCH")
    return {
        "kind": "INERT_TARGET_BOUND_REQUEST_CANDIDATE",
        "dispatchEnabled": False,
        "actualQualification": "NO_GO",
        "authenticatesCurrentFacts": False,
        "requests": requests,
        "grantSequence": [
            {
                "order": 1,
                "method": "GET",
                "path": "/client/v4/user/tokens/verify",
                "bearerRole": "test credential",
                "subjectRole": "test credential",
            },
            {
                "order": 2,
                "method": "GET",
                "path": "/client/v4/user/tokens/verify",
                "bearerRole": "metadata reader",
                "subjectRole": "metadata reader",
            },
            {
                "order": 3,
                "method": "GET",
                "path": "/client/v4/user/tokens/{verifiedTestTokenId}",
                "bearerRole": "metadata reader",
                "subjectRole": "test credential",
            },
        ],
        "grantCollector": "scripts/collect_publisher_grant_metadata.py:run (indivisible)",
        "failedGates": [
            "SOURCE_AND_SEMANTIC_REVIEW_REQUIRED",
            "CURRENT_FACTS_UNAUTHENTICATED",
            "GRANTS_AND_CREDENTIALS_UNBOUND",
            "ACL_AND_CUSTODY_UNPROVEN",
            "PHYSICAL_COSTS_UNKNOWN",
            "ACTION_WINDOW_UNBOUND",
        ],
    }
