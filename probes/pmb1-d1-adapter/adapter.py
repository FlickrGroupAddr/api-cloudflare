"""Inert fixed D1 operator seam. No provider client, target selector or action CLI."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

SOURCE = Path(__file__).resolve().parent.parent / "pmb1-d1"
MAX_GENERATION = 9223372036854775807
PINS = {
    "bootstrap.sql": "5961b61bcb612bd8e2b569d9848955bcb8d346c7aa9f003b4cb5a9a3a7f0b82b",
    "close.sql": "98623876d1121459b100f001e655d4e632fc1ffe7da756e48a1dccc4a40c1e9f",
    "control.py": "d8c1cfa9fecf22b24635810438bbc508f17dc146ebcce67c3137d5ae0c4d1857",
    "fixture.py": "3b7461876f80ca66e2f0e2ada979e70d1cf6e2480aa7d023b88e47d4e5716059",
    "guards.sql": "14e8a7a1aa6aae07e35066b24b6cd41f5530c215f68aef1969965ad62642571e",
    "manifest.json": "3a6b0d8fda2b07a3e4999ece220eee84c28c7d906ca4a87ed67faf693e009e50",
    "readback.sql": "4927c060bab3de5312ce843c916f89d5ef5f4bb5b0ece500cec8263dc9de8222",
    "README.md": "592ca18ffcace44004e4d67197222eff63005c97d7a7f04f1b855055957af2a7",
    "reopen.sql": "33b96dacc532444803d94d7ded2512d313e492d1873520c058746103f2f9bfd8",
    "schema.sql": "449fbbf112513c0204a5155b055c9c3b7ab8f51db43811f31290d8e8c2794baa",
    "test_control.py": "a7ffa89b38602592d7ecf5e83b25f78e860765e007dd71c9d5aaee5cd0395827",
}
CANDIDATE = PINS["manifest.json"]
Operation = Literal["close", "reopen"]
Phase = Literal["latched", "dispatching", "refused", "unknown", "confirmed"]


class Refusal(ValueError):
    """Invalid or exhausted finite source operation."""


def generation(value: object, *, increment: bool = False) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 19
        or not value.isascii()
        or not value.isdecimal()
        or value[0] == "0"
        or int(value) > MAX_GENERATION - int(increment)
    ):
        raise Refusal("invalid_or_exhausted_generation")
    return value


@dataclass(frozen=True)
class Window:
    """Exact packet's monotonic bounds; no automatic extension on recovery."""

    starts: float
    dispatch_until: float
    reconcile_until: float

    def validate(self) -> None:
        values = (self.starts, self.dispatch_until, self.reconcile_until)
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in values):
            raise Refusal("invalid_window")
        if not 0 <= self.starts < self.dispatch_until <= self.reconcile_until:
            raise Refusal("invalid_window")
        if self.reconcile_until - self.starts > 300:
            raise Refusal("window_exceeds_five_minute_source_ceiling")


@dataclass(frozen=True)
class Intent:
    key: str
    operation: Operation
    expected: str
    window: Window
    candidate: str = CANDIDATE

    @property
    def next_generation(self) -> str:
        return str(int(self.expected) + 1)

    @property
    def target(self) -> str:
        return "closed" if self.operation == "close" else "open"


@dataclass(frozen=True)
class JournalEntry:
    intent: Intent
    phase: Phase
    dispatch_claimed: bool = False


class Journal(Protocol):
    """EXTERNAL durable atomic port, outside every compared store.

    All methods must honor deadline. The journal is bound to the SAME singleton
    target as writer/observer. latch is an atomic insert-if-absent AND reservation
    of that target: refuse while ANY intent exists, irrespective of outcome,
    even under a new key. Persist the whole intent and zero counters before
    returning True. Reservation and recorded outcome are independent: settle
    MUST NOT release, expire or transfer the target reservation, including when
    it persists confirmed/refused and its acknowledgment is lost or late.
    This seam performs at most one transition per bound target reservation.
    spend_read durably increments a shared total counter only below 8.
    claim_dispatch atomically changes latched -> dispatching and permanently
    records dispatch_claimed=True once. claim_reconcile consumes one of at most
    2 durable attempts only after dispatch_claimed, independent of outcome phase
    (the final outcome acknowledgment may itself have been lost).
    No release or successor operation exists. Return bools
    exactly; ambiguous acknowledgments consume authority and refuse dispatch.
    The service must serialize these operations across processes and crashes.
    """

    def latch(self, intent: Intent, deadline: float) -> bool: ...
    def get(self, key: str, deadline: float) -> JournalEntry: ...
    def spend_read(self, key: str, deadline: float) -> bool: ...
    def claim_dispatch(self, key: str, deadline: float) -> bool: ...
    def claim_reconcile(self, key: str, deadline: float) -> bool: ...
    def settle(self, key: str, phase: Phase, deadline: float) -> None: ...


@dataclass(frozen=True)
class FixedUpdate:
    sql: str
    expected_generation: str
    # Exactly one fixed statement, never a batch containing ordinary work.
    boundary: Literal["single_fixed_update"] = "single_fixed_update"


class Provider(Protocol):
    """Bound mutation target, qualified single UPDATE commit semantics required.

    Bind expected_generation as TEXT. Return only after the single statement's
    qualified commit boundary, with a transport-normalized receipt of exactly
    {'success': True, 'changes': integer}. Never retry internally, redirect to a
    different target, bundle ordinary work or infer changes from returned rows.
    Honor deadline; timeout/cancellation does not prove rollback.
    """

    def dispatch(self, update: FixedUpdate, deadline: float) -> object: ...


@dataclass(frozen=True)
class CompleteRows:
    rows: list[dict[str, object]]
    complete: bool


class Observer(Protocol):
    """Separately bound authoritative PRIMARY reader, never writer response data.

    Execute each supplied full read query once; consume every page/row without
    filtering, limits or truncation. complete=True requires transport evidence of
    exhaustion. No fallback replica/cache, caller-selected query or repair.
    Actual target identity, independence and consistency need qualification.
    """

    def read(self, sql: str, deadline: float) -> CompleteRows: ...


class Clock(Protocol):
    def now(self) -> float: ...


@dataclass(frozen=True)
class Result:
    status: Literal["refused", "unknown", "confirmed", "observed"]
    reason: str
    observed_generation: str | None = None
    observed_state: str | None = None


def verify_source() -> dict[str, bytes]:
    # Freeze verified bytes for this call, never execute a freshly reread SQL.
    files = {name: (SOURCE / name).read_bytes() for name in PINS}
    if any(hashlib.sha256(value).hexdigest() != PINS[name] for name, value in files.items()):
        raise Refusal("source_pin_mismatch")
    return files


def validate_control(rows: CompleteRows) -> tuple[str, str]:
    if type(rows) is not CompleteRows or rows.complete is not True or type(rows.rows) is not list:
        raise Refusal("incomplete_control")
    expected = {
        "singleton_type",
        "singleton_text",
        "rowid_type",
        "rowid_text",
        "generation_type",
        "generation_text",
        "state_type",
        "state",
    }
    if len(rows.rows) != 1 or type(rows.rows[0]) is not dict or set(rows.rows[0]) != expected:
        raise Refusal("invalid_control")
    row = rows.rows[0]
    if any(
        row[k] != v
        for k, v in {
            "singleton_type": "integer",
            "singleton_text": "1",
            "rowid_type": "integer",
            "rowid_text": "1",
            "generation_type": "integer",
            "state_type": "text",
        }.items()
    ) or row["state"] not in ("open", "closed"):
        raise Refusal("invalid_control")
    return generation(row["generation_text"]), str(row["state"])


def validate_schema(rows: CompleteRows, files: dict[str, bytes]) -> None:
    if type(rows) is not CompleteRows or rows.complete is not True or type(rows.rows) is not list:
        raise Refusal("incomplete_schema")
    actual = []
    for row in rows.rows:
        if type(row) is not dict or set(row) != {"type", "name", "tbl_name", "sql"}:
            raise Refusal("invalid_schema")
        if any(type(row[k]) is not str for k in ("type", "name", "tbl_name")):
            raise Refusal("invalid_schema")
        sql = row["sql"]
        if sql is not None and type(sql) is not str:
            raise Refusal("invalid_schema")
        actual.append(
            {
                "type": row["type"],
                "name": row["name"],
                "table": row["tbl_name"],
                "sql_sha2_256": None if sql is None else hashlib.sha256(sql.encode()).hexdigest(),
            }
        )
    if actual != json.loads(files["manifest.json"])["candidate_schema"]:
        raise Refusal("schema_or_guard_mismatch")


class Adapter:
    """Source/synthetic only. New sessions cannot replay a latched intent."""

    def __init__(self, writer: Provider, observer: Observer, journal: Journal, clock: Clock):
        if writer is observer:
            raise Refusal("writer_is_not_independent_observer")
        self.writer, self.observer, self.journal, self.clock = writer, observer, journal, clock
        self.last_time = -1.0

    def check(self, intent: Intent, *, reconciliation: bool = False) -> float:
        intent.window.validate()
        if intent.candidate != CANDIDATE or intent.operation not in ("close", "reopen"):
            raise Refusal("invalid_intent")
        generation(intent.expected, increment=True)
        if (
            type(intent.key) is not str
            or not 1 <= len(intent.key) <= 128
            or not intent.key.isascii()
        ):
            raise Refusal("invalid_intent_key")
        now = self.clock.now()
        end = intent.window.reconcile_until if reconciliation else intent.window.dispatch_until
        if type(now) not in (int, float) or not math.isfinite(now) or now < self.last_time:
            raise Refusal("clock_unusable")
        self.last_time = now
        if not intent.window.starts <= now < end:
            raise Refusal("deadline_or_not_started")
        verify_source()
        after = self.clock.now()
        if (
            type(after) not in (int, float)
            or not math.isfinite(after)
            or after < now
            or not intent.window.starts <= after < end
        ):
            raise Refusal("clock_or_deadline_after_source_check")
        self.last_time = after
        return end

    def observe(self, intent: Intent, *, reconciliation: bool = False) -> tuple[str, str]:
        files = verify_source()
        replies = []
        for name in ("readback.sql", "schema.sql"):
            end = self.check(intent, reconciliation=reconciliation)
            if self.journal.spend_read(intent.key, end) is not True:
                raise Refusal("read_budget_exhausted")
            end = self.check(intent, reconciliation=reconciliation)
            replies.append(self.observer.read(files[name].decode(), end))
            self.check(intent, reconciliation=reconciliation)
        validate_schema(replies[1], files)
        return validate_control(replies[0])

    def close(self, key: str, expected: str, window: Window) -> Result:
        return self.execute(Intent(key, "close", expected, window))

    def reopen(self, key: str, expected: str, window: Window) -> Result:
        return self.execute(Intent(key, "reopen", expected, window))

    def execute(self, intent: Intent) -> Result:
        # Intent contains no SQL, target, next state/generation or caller batch.
        claimed = False
        latched = False
        try:
            end = self.check(intent)
            if self.journal.latch(intent, end) is not True:
                return Result("refused", "intent_already_latched_or_unconfirmed")
            latched = True
            self.check(intent)
            before = self.observe(intent)
            expected_state = "open" if intent.operation == "close" else "closed"
            if before != (intent.expected, expected_state):
                raise Refusal("stale_or_wrong_state")
            end = self.check(intent)
            # From this point any ambiguous journal claim may have consumed it.
            claimed = True
            if self.journal.claim_dispatch(intent.key, end) is not True:
                raise Refusal("dispatch_claim_unconfirmed")
            end = self.check(intent)
            files = verify_source()
            update = FixedUpdate(files[f"{intent.operation}.sql"].decode(), intent.expected)
            end = self.check(intent)
            receipt = self.writer.dispatch(update, end)
            self.check(intent)
            if (
                type(receipt) is not dict
                or set(receipt) != {"success", "changes"}
                or receipt["success"] is not True
                or type(receipt["changes"]) is not int
            ):
                raise Refusal("malformed_receipt")
            if receipt["changes"] == 0:
                self.journal.settle(intent.key, "refused", self.check(intent))
                self.check(intent)
                return Result("refused", "zero_affected_rows")
            if receipt["changes"] != 1:
                raise Refusal("affected_rows_not_one")
            observed = self.observe(intent)
            if observed != (intent.next_generation, intent.target):
                raise Refusal("transition_readback_mismatch")
            self.journal.settle(intent.key, "confirmed", self.check(intent))
            self.check(intent)
            return Result("confirmed", "one_row_and_independent_readback", *observed)
        except Exception:
            # No exception message or private payload escapes to the result.
            # Unknown is deliberately sticky; this source supplies no retry.
            if latched:
                try:
                    self.journal.settle(
                        intent.key,
                        "unknown" if claimed else "refused",
                        self.check(intent, reconciliation=True),
                    )
                except Exception:
                    pass
            return Result("unknown" if claimed else "refused", "operation_unconfirmed")

    def reconcile(self, intent: Intent) -> Result:
        """Bounded observations only; cannot manufacture a lost commit receipt."""
        try:
            end = self.check(intent, reconciliation=True)
            entry = self.journal.get(intent.key, end)
            if entry.intent != intent or entry.dispatch_claimed is not True:
                raise Refusal("not_exact_uncertain_intent")
            self.check(intent, reconciliation=True)
            if self.journal.claim_reconcile(intent.key, end) is not True:
                raise Refusal("reconciliation_budget_exhausted")
            observed = self.observe(intent, reconciliation=True)
            if observed != (intent.next_generation, intent.target):
                return Result("unknown", "target_not_observed", *observed)
            return Result("observed", "current_target_only_receipt_remains_unknown", *observed)
        except Exception:
            return Result("unknown", "reconciliation_unconfirmed")
