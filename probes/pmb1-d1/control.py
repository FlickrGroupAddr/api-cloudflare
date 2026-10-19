"""Inert PMB-1 statement/receipt shapes, not a D1 client or action entry point.

Only synthetic SQLite tests dispatch these statements. A future D1 adapter must
bind the returned generation as TEXT and independently qualify its transaction,
primary readback, journal, custody and ordering boundaries before any use.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MAX_GENERATION = 9223372036854775807
HERE = Path(__file__).resolve().parent


class Refusal(ValueError):
    """Invalid source input or unsuccessful fixed operation."""


@dataclass(frozen=True)
class Transition:
    operation: Literal["close", "reopen"]
    expected_generation: str
    next_generation: str
    next_state: Literal["open", "closed"]
    sql: str


@dataclass(frozen=True)
class ControlReadback:
    generation: str
    state: Literal["open", "closed"]


def generation_text(value: object, *, reserve_increment: bool = False) -> str:
    """Reject numeric/coerced/rounded/noncanonical bindings before dispatch."""
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 19
        or not value.isascii()
        or not value.isdecimal()
        or value[0] == "0"
    ):
        raise Refusal("invalid_generation_text")
    if int(value) > MAX_GENERATION - int(reserve_increment):
        raise Refusal("generation_exhausted")
    return value


def close(expected_generation: object) -> Transition:
    expected = generation_text(expected_generation, reserve_increment=True)
    return Transition("close", expected, str(int(expected) + 1), "closed", read_sql("close"))


def reopen(expected_generation: object) -> Transition:
    expected = generation_text(expected_generation, reserve_increment=True)
    return Transition("reopen", expected, str(int(expected) + 1), "open", read_sql("reopen"))


def read_sql(name: Literal["close", "reopen", "readback", "schema", "bootstrap"]) -> str:
    return (HERE / f"{name}.sql").read_text(encoding="utf-8")


def require_one_change(changes: object) -> None:
    # A bool is an int in Python; malformed adapter receipts must still refuse.
    if type(changes) is not int or changes != 1:
        raise Refusal("affected_rows_not_one")


def parse_readback(rows: list[dict[str, object]]) -> ControlReadback:
    """Consume ALL rows of readback.sql, never first()/a SELECT echo."""
    keys = {
        "singleton_type",
        "singleton_text",
        "rowid_type",
        "rowid_text",
        "generation_type",
        "generation_text",
        "state_type",
        "state",
    }
    if len(rows) != 1 or set(rows[0]) != keys:
        raise Refusal("invalid_control_readback")
    row = rows[0]
    if (
        row["singleton_type"] != "integer"
        or row["singleton_text"] != "1"
        or row["rowid_type"] != "integer"
        or row["rowid_text"] != "1"
        or row["generation_type"] != "integer"
        or row["state_type"] != "text"
        or row["state"] not in ("open", "closed")
    ):
        raise Refusal("invalid_control_readback")
    generation = generation_text(row["generation_text"])
    state = row["state"]
    if state == "open":
        return ControlReadback(generation, "open")
    return ControlReadback(generation, "closed")


def confirm_readback(
    transition: Transition,
    rows: list[dict[str, object]],
    schema_rows: list[dict[str, object]],
) -> ControlReadback:
    """Independent authoritative row AND complete schema readback are mandatory.

    Call only after require_one_change. Failure after dispatch means UNKNOWN,
    never permission to retry, infer success, repair, or reopen. These helpers
    intentionally perform no dispatch, automatic retry, or journal operation.
    """
    pinned = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    if schema_pins(schema_rows) != pinned["candidate_schema"]:
        raise Refusal("schema_readback_mismatch")
    observed = parse_readback(rows)
    if observed != ControlReadback(transition.next_generation, transition.next_state):
        raise Refusal("transition_readback_mismatch")
    return observed


def schema_pins(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        if set(row) != {"type", "name", "tbl_name", "sql"}:
            raise Refusal("invalid_schema_readback")
        sql = row["sql"]
        if sql is not None and not isinstance(sql, str):
            raise Refusal("invalid_schema_readback")
        if any(not isinstance(row[key], str) for key in ("type", "name", "tbl_name")):
            raise Refusal("invalid_schema_readback")
        result.append(
            {
                "type": row["type"],
                "name": row["name"],
                "table": row["tbl_name"],
                "sql_sha2_256": None
                if sql is None
                else hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            }
        )
    return result
