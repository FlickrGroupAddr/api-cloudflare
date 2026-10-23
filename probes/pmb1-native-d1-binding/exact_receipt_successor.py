"""Accepted source-only exact-count successor; no credential or transport code.

Decoding is not native same-connection/transaction/commit proof. These helpers
cannot supply the original single_fixed_update receipt or enable its Provider.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Literal, cast

import adapter

from scripts.temporary_composition_metadata_collector import _json, canonical

BOUNDARY = "fixed_update_with_exact_count_v1"
COUNT_SQL = "SELECT CAST(changes() AS TEXT) AS exact_change_count"


@dataclass(frozen=True)
class FixedExactChangeBatch:
    intent: adapter.Intent
    update_sql: str
    boundary: Literal["fixed_update_with_exact_count_v1"] = BOUNDARY


@dataclass(frozen=True)
class DecodedExactCount:
    """Decoded source evidence ONLY, never a qualified committed outcome."""

    count: Literal[0, 1]
    boundary: Literal["fixed_update_with_exact_count_v1"] = BOUNDARY


def build(intent):
    """Consume one trusted immutable intent; no independent SQL/state/generation input."""
    if type(intent) is not adapter.Intent or intent.operation not in ("close", "reopen"):
        raise adapter.Refusal("exact_count_successor_intent")
    intent.window.validate()
    adapter.generation(intent.expected, increment=True)
    if type(intent.transition_limit) is not int or intent.transition_limit not in (1, 2, 3):
        raise adapter.Refusal("exact_count_successor_headroom")
    return FixedExactChangeBatch(
        intent, adapter.verify_source()[intent.operation + ".sql"].decode()
    )


def build_root(intent):
    """Reserve whole-campaign headroom only for its immutable initial intent.

    build() validates a single transition; the journal owns a successor's root,
    durable ordinal and remaining capacity, which are not inputs to this codec.
    """
    batch = build(intent)
    if int(intent.expected) + intent.transition_limit > adapter.MAX_GENERATION:
        raise adapter.Refusal("exact_count_successor_root_headroom")
    return batch


def request_body(batch):
    """Pure bounded proposal bytes, preserving the original named UPDATE parameter.

    Exactly one following SELECT, no third statement/ordinary work/resource.
    REST support for that named parameter and TEXT array binding must still be
    independently established. This serializer grants no dispatch authority.
    """
    if type(batch) is not FixedExactChangeBatch or batch.boundary != BOUNDARY:
        raise adapter.Refusal("exact_count_successor_boundary")
    if batch != build(batch.intent):
        raise adapter.Refusal("exact_count_successor_fixed_source")
    return canonical(
        {
            "batch": [
                {"sql": batch.update_sql, "params": [batch.intent.expected]},
                {"sql": COUNT_SQL, "params": []},
            ]
        }
    )


def manifest(batch):
    body = request_body(batch)
    return {
        "protocol": BOUNDARY,
        "statementCount": 2,
        "requestBodySha2_256": hashlib.sha256(body).hexdigest(),
        "statements": _json(body)["batch"],
    }


def decode_ordered_body(body):
    """Strict two-result/decimal decoding without commit attestation or normalization.

    Qualified finite transport must separately establish HTTP exhaustion, exact
    target/source, same ordered connection/transaction and actual commit. The
    original durable intent/one-dispatch/unknown/budgets and independently issued
    complete PRIMARY schema/row readback remain mandatory and unimplemented here.
    """
    if type(body) is not bytes or not 0 < len(body) <= 512 * 1024:
        raise adapter.Refusal("exact_count_successor_body_bound")
    payload = _json(body)
    if (
        type(payload) is not dict
        or set(payload) != {"success", "errors", "messages", "result"}
        or payload["success"] is not True
        or payload["errors"] != []
        or payload["messages"] != []
        or type(payload["result"]) is not list
        or len(payload["result"]) != 2
    ):
        raise adapter.Refusal("exact_count_successor_ordered_results")
    payload = cast(dict[str, Any], payload)
    for result in payload["result"]:
        if (
            type(result) is not dict
            or set(result) != {"success", "results", "meta"}
            or result["success"] is not True
            or type(result["results"]) is not list
            or type(result["meta"]) is not dict
            or result["meta"].get("served_by_primary") is not True
            or any(
                key in result["meta"]
                for key in ("next", "next_page", "cursor", "truncated", "has_more")
            )
        ):
            raise adapter.Refusal("exact_count_successor_incomplete_or_nonprimary")
    if payload["result"][0]["results"] != []:
        raise adapter.Refusal("exact_count_successor_update_result")
    rows = payload["result"][1]["results"]
    if (
        len(rows) != 1
        or type(rows[0]) is not dict
        or set(rows[0]) != {"exact_change_count"}
        or type(rows[0]["exact_change_count"]) is not str
        or rows[0]["exact_change_count"] not in ("0", "1")
    ):
        raise adapter.Refusal("exact_count_successor_count")
    return DecodedExactCount(cast(Literal[0, 1], int(rows[0]["exact_change_count"])))


def receipt_manifest(batch, body):
    """Bind decoded bytes to both exact request statements, without attestation."""
    request = manifest(batch)
    decoded = decode_ordered_body(body)
    return {
        "protocol": BOUNDARY,
        "request": request,
        "responseBodySha2_256": hashlib.sha256(body).hexdigest(),
        "exactChangeCountText": str(decoded.count),
    }
