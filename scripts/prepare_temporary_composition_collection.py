"""Prepare a finite private read-only collection plan offline; never contact a provider.

Assertions in supplied provenance are checked for consistency, not authenticated.
A reviewable plan is neither collection permission nor a materialization receipt.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from scripts.build_temporary_composition import CANDIDATE, validate_scope
from scripts.fixed_origin_restore import FIXTURE_MANIFEST_SHA256, MODULE_SHA256
from scripts.prepare_temporary_composition import _plain
from scripts.temporary_composition_delta import (
    CONFIG_KEYS,
    _bounded,
    build_delta,
    load_json,
    validate_baseline,
)

INPUTS = ("target", "baseline", "additions", "scope", "fixture")
PROVENANCE_KEYS = frozenset(
    "sourceRef sourceType capturedAt target contentSha256 independentlySourced completeness".split()
)
PRIVACY = {
    "secretValues": False,
    "photoData": False,
    "responseBodiesInLogs": False,
    "publicAccountValues": False,
}
MAX_WINDOW = timedelta(hours=1)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False, indent=2) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _keys(value: Any, keys: set[str] | frozenset[str], reason: str) -> None:
    _require(type(value) is dict and set(value) == keys, reason)


def _text(value: Any) -> bool:
    return type(value) is str and 0 < len(value) <= 512 and not any(ord(c) < 32 for c in value)


def _time(value: Any) -> datetime:
    _require(type(value) is str and value.endswith("Z"), "timestamp_required")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ValueError("timestamp_required") from None
    _require(result.utcoffset() == timedelta(0), "timestamp_required")
    return result


def _target(value: Any) -> None:
    _keys(value, {"accountId", "scriptName"}, "exact_target_required")
    _require(
        all(type(v) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", v) for v in value.values()),
        "exact_target_required",
    )


def _components(baseline: dict[str, Any]) -> dict[str, Any]:
    values = {"configuration." + k: baseline["configuration"][k] for k in sorted(CONFIG_KEYS)}
    values.update(
        {k: baseline[k] for k in ("productionState", "deploymentWeights", "retainedVersion")}
    )
    return values


def required_reads(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Logical operation inventory; no URLs, paging guesses, token or network access.

    A collector must refuse incomplete, paginated or inconsistent results. This
    does not implement a provider reader or assert an HTTP request budget.
    """
    inputs = request["inputs"]
    if not all(inputs[k]["available"] for k in ("target", "baseline", "additions")):
        return []
    target = inputs["target"]["value"]
    baseline = inputs["baseline"]["value"]
    additions = inputs["additions"]["value"]
    reads = [
        {"readId": "baseline." + key, "target": copy.deepcopy(target)}
        for key in _components(baseline)
    ]
    for index, resource in enumerate(additions["resources"]):
        reads.append(
            {
                "readId": "isolated.resources." + str(index),
                "target": {
                    "accountId": target["accountId"],
                    "kind": resource["kind"],
                    "identity": resource["identity"],
                },
            }
        )
    reads.append(
        {
            "readId": "receiver.configuration",
            "target": copy.deepcopy(additions["receiver"]["target"]),
        }
    )
    _require(len(reads) == 18, "finite_read_inventory")
    return reads


def _provenance(
    provenance: Any,
    value: Any,
    target: Any,
    start: datetime,
    end: datetime,
    now: datetime,
    *,
    components: dict[str, Any] | None = None,
) -> None:
    expected = PROVENANCE_KEYS | ({"components"} if components is not None else set())
    _keys(provenance, expected, "provenance_fields")
    _require(_text(provenance["sourceRef"]), "provenance_source")
    _require(
        provenance["sourceType"] in ("owner_export", "provider_read", "retained_fixture"),
        "provenance_source_type",
    )
    captured = _time(provenance["capturedAt"])
    # Historical retained fixture descriptors keep their original capture time;
    # current baseline evidence must fall inside this exact collection window.
    if provenance["sourceType"] == "retained_fixture":
        _require(captured <= now, "provenance_time")
    else:
        _require(start <= captured <= min(end, now), "provenance_time")
    _require(provenance["target"] == target, "provenance_target")
    _require(provenance["contentSha256"] == _digest(value), "provenance_digest")
    _require(provenance["independentlySourced"] is True, "independent_source_required")
    _require(provenance["completeness"] == "complete", "provenance_incomplete")
    if components is not None:
        _keys(provenance["components"], set(components), "provenance_components")
        for key, child in components.items():
            item = provenance["components"][key]
            _require(type(item) is dict, "provenance_fields")
            _require(item.get("sourceType") != "retained_fixture", "current_source_required")
            _provenance(item, child, target, start, end, now)


def prepare(request: Any, expected_request_sha256: str, now: datetime) -> dict[str, Any]:
    """Validate supplied values and return only sanitized status, never private values.

    The independently retained expected digest binds this exact review request.
    It does not establish that its author has captured the provider accurately.
    Missing inputs are explicit blockers; no baseline/state/grant is synthesized.
    """
    _bounded(request)
    _require(type(now) is datetime and now.tzinfo is not None, "aware_now_required")
    _require(
        type(expected_request_sha256) is str
        and re.fullmatch(r"[a-f0-9]{64}", expected_request_sha256) is not None,
        "independent_request_pin_required",
    )
    _require(_digest(request) == expected_request_sha256, "request_pin")
    _keys(request, {"schemaVersion", "kind", "authority", "inputs"}, "request_fields")
    _require(
        type(request["schemaVersion"]) is int
        and request["schemaVersion"] == 1
        and request["kind"] == "temporary_composition_collection_request",
        "request_schema",
    )
    authority = request["authority"]
    _keys(
        authority,
        {
            "decisionRef",
            "approved",
            "startsAt",
            "expiresAt",
            "credentialDelivery",
            "credentialRevocation",
            "privacy",
            "grants",
        },
        "authority_fields",
    )
    _require(
        all(
            _text(authority[k])
            for k in ("decisionRef", "credentialDelivery", "credentialRevocation")
        ),
        "authority_methods",
    )
    _require(type(authority["approved"]) is bool, "authority_approval")
    start, end = _time(authority["startsAt"]), _time(authority["expiresAt"])
    _require(start < end and end - start <= MAX_WINDOW, "collection_deadline")
    _keys(authority["privacy"], set(PRIVACY), "privacy_fields")
    _require(all(authority["privacy"][k] is False for k in PRIVACY), "privacy_limits")
    inputs = request["inputs"]
    _keys(inputs, set(INPUTS), "input_inventory")
    blockers = []
    values: dict[str, Any] = {}
    for key in INPUTS:
        item = inputs[key]
        _keys(item, {"available", "value", "provenance"}, "input_fields")
        _require(type(item["available"]) is bool, "input_availability")
        if not item["available"]:
            _require(
                item["value"] is None and item["provenance"] is None, "unavailable_input_value"
            )
            blockers.append("unavailable_" + key)
        else:
            _require(
                item["value"] is not None and item["provenance"] is not None,
                "available_input_required",
            )
            values[key] = item["value"]
    if "target" in values:
        _target(values["target"])
    elif values:
        raise ValueError("exact_target_required")
    if "baseline" in values:
        validate_baseline(values["baseline"])
        _require(values["baseline"]["target"] == values["target"], "baseline_target")
        _require(values["baseline"]["moduleSha256"] == MODULE_SHA256, "retained_module_pin")
    if "fixture" in values:
        _keys(
            values["fixture"],
            {"candidateCommit", "capturedModuleSha256", "manifestSha256"},
            "fixture_descriptor_fields",
        )
        _require(
            values["fixture"]
            == {
                "candidateCommit": CANDIDATE,
                "capturedModuleSha256": MODULE_SHA256,
                "manifestSha256": FIXTURE_MANIFEST_SHA256,
            },
            "fixture_descriptor_pin",
        )
    if "additions" in values:
        _require("baseline" in values and "scope" in values, "addition_validation_inputs")
        additions = copy.deepcopy(values["additions"])
        _require(
            "moduleSha256" not in additions and "moduleSha256" not in additions["receiver"],
            "computed_module_fields_forbidden",
        )
        # These sentinels are ONLY for existing shape/isolation validation and
        # never returned as modules, digests or materialization evidence.
        _require("scope" not in additions, "separate_scope_required")
        additions["scope"] = copy.deepcopy(values["scope"])
        additions["moduleSha256"] = "0" * 64
        additions["receiver"]["moduleSha256"] = "0" * 64
        build_delta(values["baseline"], additions)
        validate_scope(values["scope"], additions)
    elif "scope" in values:
        raise ValueError("scope_validation_inputs")
    for key, value in values.items():
        provenance = inputs[key]["provenance"]
        _require(type(provenance) is dict, "provenance_fields")
        _require(
            key == "fixture" or provenance.get("sourceType") != "retained_fixture",
            "current_source_required",
        )
        _provenance(
            provenance,
            value,
            values["target"],
            start,
            end,
            now,
            components=_components(value) if key == "baseline" else {},
        )
    reads = required_reads(request)
    grants = authority["grants"]
    _require(type(grants) is list and len(grants) <= 18, "read_grants")
    grants = cast(list[dict[str, Any]], grants)
    seen = set()
    for grant in grants:
        _keys(grant, {"readId", "target", "effect", "permissionRef"}, "grant_fields")
        _require(
            type(grant["readId"]) is str and grant["readId"] not in seen, "duplicate_read_grant"
        )
        seen.add(grant["readId"])
        _require(grant["effect"] == "read" and _text(grant["permissionRef"]), "read_only_grant")
    if reads:
        _require(seen == {read["readId"] for read in reads}, "exact_read_grants")
        by_id = {g["readId"]: g for g in grants}
        _require(all(by_id[r["readId"]]["target"] == r["target"] for r in reads), "grant_target")
    else:
        _require(not grants, "unresolved_read_targets")
    if authority["approved"] is not True:
        blockers.append("authority_not_approved")
    if not start <= now < end:
        blockers.append("collection_window_inactive")
    return {
        "schemaVersion": 1,
        "kind": "temporary_composition_collection_receipt",
        "status": "blocked" if blockers else "reviewable",
        "blockers": blockers,
        "requestSha256": expected_request_sha256,
        "requiredReadCount": len(reads),
        "inputAvailability": {k: inputs[k]["available"] for k in INPUTS},
        "providerExecuted": False,
        "nativeExecuted": False,
        "activationAuthorized": False,
        "materializationReady": False,
    }


def collection_plan(
    request: dict[str, Any], receipt: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Private exact-target plan only after a successful consistency preflight."""
    _require(
        receipt == prepare(request, receipt["requestSha256"], now), "preflight_receipt_required"
    )
    _require(
        receipt["status"] == "reviewable" and receipt["requestSha256"] == _digest(request),
        "reviewable_plan_required",
    )
    return {
        "schemaVersion": 1,
        "kind": "offline_temporary_composition_collection_plan",
        "requestSha256": receipt["requestSha256"],
        "authority": copy.deepcopy(request["authority"]),
        "reads": required_reads(request),
        "maxLogicalReads": 18,
        "onIncompleteOrUnknown": "refuse_and_re_review",
        "providerExecuted": False,
        "nativeExecuted": False,
        "activationAuthorized": False,
        "materializationReady": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--plan-output", type=Path)
    args = parser.parse_args()
    try:
        paths = [args.request, args.receipt] + ([args.plan_output] if args.plan_output else [])
        for path in paths:
            _plain(path)
        _require(len({p.resolve() for p in paths}) == len(paths), "distinct_paths_required")
        _require(
            not args.receipt.exists()
            and (args.plan_output is None or not args.plan_output.exists()),
            "fresh_outputs_required",
        )
        request = load_json(args.request)
        receipt = prepare(request, args.expected_request_sha256, datetime.now(UTC))
        if args.plan_output and receipt["status"] == "reviewable":
            # Exact targets are private; the caller must explicitly select a
            # private-evidence destination outside the repository.
            from scripts.build_temporary_composition import _private

            _private(args.plan_output, Path(__file__).resolve().parents[1])
            args.plan_output.write_bytes(
                canonical(collection_plan(request, receipt, datetime.now(UTC)))
            )
        args.receipt.write_bytes(canonical(receipt))
    except ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError:
        print("NO-GO: offline collection preflight refused")
        return 2
    print("Offline collection preflight: " + receipt["status"] + "; no provider/native action")
    return 0 if receipt["status"] == "reviewable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
