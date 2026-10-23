"""Accepted #0250 positional source variant; no native dispatch or qualification.

Only the two historical named parameter tokens become the same ?1 slot.
The named successor, original SQL files and single_fixed_update stay distinct.
"""

import hashlib
from dataclasses import dataclass
from typing import Literal

import adapter
import exact_receipt_successor as named

from scripts.temporary_composition_metadata_collector import canonical

BOUNDARY = "fixed_update_with_exact_count_positional_v1"
COUNT_SQL = named.COUNT_SQL


def source_sql(operation):
    if operation not in ("close", "reopen"):
        raise adapter.Refusal("positional_fixed_operation")
    original = adapter.verify_source()[operation + ".sql"]
    token = b":expected_generation"
    if original.count(token) != 2 or b"?1" in original:
        raise adapter.Refusal("positional_source_token_inventory")
    variant = original.replace(token, b"?1")
    if variant.replace(b"?1", token) != original:
        raise adapter.Refusal("positional_nonparameter_source_delta")
    return variant.decode()


@dataclass(frozen=True)
class FixedPositionalBatch:
    intent: adapter.Intent
    update_sql: str
    boundary: Literal["fixed_update_with_exact_count_positional_v1"] = BOUNDARY


@dataclass(frozen=True)
class DecodedPositionalCount:
    count: Literal[0, 1]
    boundary: Literal["fixed_update_with_exact_count_positional_v1"] = BOUNDARY


def build(intent):
    named.build(intent)  # canonical TEXT, one increment and immutable intent shape
    return FixedPositionalBatch(intent, source_sql(intent.operation))


def build_root(intent):
    named.build_root(intent)
    return build(intent)


def request_body(batch):
    if type(batch) is not FixedPositionalBatch or batch != build(batch.intent):
        raise adapter.Refusal("positional_exact_batch_boundary")
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
        "statements": [
            {"sql": batch.update_sql, "params": [batch.intent.expected]},
            {"sql": COUNT_SQL, "params": []},
        ],
    }


def decode_ordered_body(body):
    # Same strict primary/completion/count grammar, distinct evidence type.
    return DecodedPositionalCount(named.decode_ordered_body(body).count)


def receipt_manifest(batch, body):
    decoded = decode_ordered_body(body)
    return {
        "protocol": BOUNDARY,
        "request": manifest(batch),
        "responseBodySha2_256": hashlib.sha256(body).hexdigest(),
        "exactChangeCountText": str(decoded.count),
    }
