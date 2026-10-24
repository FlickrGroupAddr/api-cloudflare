"""Inert SOURCE PMB-1 orchestration. MIT License; copyright 2026 Terry Ott.

There is deliberately no provider client, credential loader or execution CLI.
Adapters supplied to this source harness must be synthetic. The external journal
is outside all compared stores; it is never a maintenance control authority.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

PROFILE = "pmb1-private-application-no-real-v1"
OBJECT_PROFILE = "pmb1-private-object-kv-interface-v1"
REQUIRED_STAGES = (
    "settle",
    "close",
    "closure_readback",
    "baseline",
    "challenge",
    "challenge_readback",
    "temporary_install",
    "preflight",
    "admission_off",
    "restore",
    "restore_readback",
    "restored",
    "cleanup",
    "cleanup_readback",
)
CASE_OBLIGATIONS = (
    "happy_path",
    "admitted_before_close",
    "stale_callback_guarded_upsert_replace_cascade",
    "lost_close_ack",
    "restart_stale_generation_malformed_control",
    "deadline_or_credential_expiry",
    "restore_with_both_delayed_generations",
    "scheduled_session_audit_auth_failure_status",
    "service_queue_hint_alarm_separate_store",
    "operator_schema_guard_bypass_bookkeeping",
    "mutate_revert_broken_guard",
    "declared_interruption",
)
INTERRUPTIONS = (
    "timeout",
    "partial_output",
    "malformed",
    "truncated",
    "unsupported",
    "unknown_restore",
    "unknown_cleanup",
)


class Refusal(ValueError):
    """Sanitized source refusal, without private adapter exception text."""


class _CampaignAlreadyReserved(Refusal):
    """The authoritative latch definitively inserted no new reservation."""


@dataclass(frozen=True)
class Cost:
    requests: int = 0
    reader_queries: int = 0
    receipt_reads: int = 0
    metadata_reads: int = 0
    authenticated_checks: int = 0
    mutations: int = 0
    creates: int = 0
    deletes: int = 0
    sql_statements: int = 0
    effects: int = 0
    outbound_bytes: int = 0
    inbound_bytes: int = 0
    artifact_bytes: int = 0
    challenges: int = 0
    captures: int = 0

    def validate(self) -> None:
        if any(type(v) is not int or v < 0 for v in dataclasses.asdict(self).values()):
            raise Refusal("invalid_cost")

    def plus(self, other: Cost) -> Cost:
        return Cost(
            **{
                f.name: getattr(self, f.name) + getattr(other, f.name)
                for f in dataclasses.fields(self)
            }
        )

    def within(self, limit: Cost) -> bool:
        self.validate()
        limit.validate()
        return all(
            getattr(self, f.name) <= getattr(limit, f.name) for f in dataclasses.fields(self)
        )


RUN_LIMIT = Cost(
    160, 96, 20, 4, 4, 32, 2, 2, 256, 2048, 4 * 1024**2, 16 * 1024**2, 8 * 1024**2, 12, 3
)
CAMPAIGN_LIMIT = dataclasses.replace(
    Cost(**{f.name: getattr(RUN_LIMIT, f.name) * 12 for f in dataclasses.fields(Cost)}),
    creates=2,
    deletes=2,
)


@dataclass(frozen=True)
class Operation:
    name: str
    stage: str
    cost: Cost
    channel: str
    action: str
    capture: str | None = None
    resource: str | None = None


@dataclass(frozen=True)
class Case:
    number: int
    operations: tuple[Operation, ...]
    interruption: str | None = None


@dataclass(frozen=True)
class Packet:
    key: str
    source_pin: str
    profile: str
    object_profile: str
    cases: tuple[Case, ...]
    starts: float
    deadline: float
    baseline_freshness: float = 60
    context: SourceContext | None = None
    selected_case: int = 1


@dataclass(frozen=True)
class SourceContext:
    """Exact source-owned context, not a request-derived qualification record.

    The independent packet preparer must reconcile every resource/store/writer
    and freeze the actual operation tree. The inherited full candidate has 65
    domain tables; it cannot fit PMB-1's unchanged eight-table miniature ceiling.
    Supplying fewer tables to fit would change the selected candidate and refuses.
    """

    candidate: str
    artifact: str
    configuration: str
    schema: str
    guards: str
    oracle: str
    population: tuple[str, ...]
    generations: tuple[str, ...]
    table_count: int
    schema_objects: int
    program_pin: str


@dataclass(frozen=True)
class Snapshot:
    canonical: bytes
    source_pin: str
    identity: str
    complete: bool


@dataclass(frozen=True)
class Receipt:
    status: str
    actual_cost: Cost
    evidence: bytes
    snapshot: Snapshot | None = None


@dataclass(frozen=True)
class Result:
    status: str
    completed_cases: int
    reason: str
    scope: str = "SOURCE_SYNTHETIC_ONLY"
    qualification: str = "NO_GO"


class Adapter(Protocol):
    """One fixed low-level invocation, never an aggregate upload/control endpoint.

    An adapter must not retry, poll, resolve new identities or perform hidden I/O.
    It reports all wire bytes including headers/framing, SQL and affected events.
    Snapshot bytes come from an independent complete oracle, not target claims.
    SOURCE adapters cannot claim actual native or provider qualification.
    """

    def invoke(self, operation: Operation, deadline: float) -> Receipt: ...


class DisabledAdapter:
    def invoke(self, operation: Operation, deadline: float) -> Receipt:
        raise Refusal("provider_dispatch_disabled")


class Oracle(Protocol):
    """Separately reviewed SOURCE oracle, independently initialized from fixture.

    It must verify durable control/guard/custody/retained-target/cleanup evidence
    from each authoritative read, including negative challenges. Writer-returned
    flags and matching end snapshots are insufficient. Missing coverage refuses.
    Native source truth is not established by constructing this trusted port.
    """

    def verify_receipt(self, operation: Operation, receipt: Receipt) -> None: ...
    def verify(self, snapshot: Snapshot) -> None: ...


class DisabledOracle:
    def verify_receipt(self, operation: Operation, receipt: Receipt) -> None:
        raise Refusal("independent_operation_oracle_unavailable")

    def verify(self, snapshot: Snapshot) -> None:
        raise Refusal("independent_complete_oracle_unavailable")


class Journal(Protocol):
    """Durable atomic external latch. Reservations survive every terminal state.

    A lost reserve/finish ACK is unknown, never permission to retry. No method
    resets, releases, repairs, renews, reopens or starts a successor campaign.
    Counters reserve the full declared upper bound before dispatch and never
    refund failed/denied/short operations. The source harness does not supply
    actual campaign headroom, ownership, custody or restore qualification.
    """

    def latch(self, packet: Packet, digest: str) -> None: ...
    def reserve(self, case: int, operation: Operation) -> None: ...
    def finish(self, case: int, operation: Operation, receipt: Receipt) -> None: ...
    def terminal(self, status: str, reason: str) -> None: ...


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def packet_digest(packet: Packet) -> str:
    return hashlib.sha256(_json(dataclasses.asdict(packet)).encode()).hexdigest()


def validate_packet(packet: Packet) -> None:
    if (
        not packet.key
        or len(packet.key) > 128
        or len(packet.source_pin) != 64
        or any(c not in "0123456789abcdef" for c in packet.source_pin)
        or packet.profile != PROFILE
        or packet.object_profile != OBJECT_PROFILE
    ):
        raise Refusal("packet_binding")
    context = packet.context
    if context is None:
        raise Refusal("complete_source_population_context_required")
    if type(packet.selected_case) is not int or not 1 <= packet.selected_case <= 12:
        raise Refusal("source_rehearsal_case_selection")
    digests = (
        context.candidate,
        context.artifact,
        context.configuration,
        context.schema,
        context.guards,
        context.oracle,
        context.program_pin,
    )
    if (
        any(
            type(p) is not str or len(p) != 64 or any(c not in "0123456789abcdef" for c in p)
            for p in digests
        )
        or not context.population
        or type(context.population) is not tuple
        or len(context.population) != len(set(context.population))
        or len(context.generations) != len(context.population)
        or any(
            not g.isascii()
            or not g.isdecimal()
            or g.startswith("0")
            or int(g) > 9223372036854775807
            for g in context.generations
        )
    ):
        raise Refusal("source_population_binding")
    if (
        type(context.table_count) is not int
        or type(context.schema_objects) is not int
        or not 1 <= context.table_count <= 8
        or not 1 <= context.schema_objects <= 64
    ):
        raise Refusal("selected_candidate_exceeds_accepted_miniature_allocation")
    if (
        any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in (packet.starts, packet.deadline, packet.baseline_freshness)
        )
        or not 0 <= packet.starts < packet.deadline
        or packet.deadline - packet.starts > 14400
        or not 0 < packet.baseline_freshness <= 60
    ):
        raise Refusal("packet_window")
    if len(_json(dataclasses.asdict(packet)).encode()) > 1024**2:
        raise Refusal("plan_byte_bound")
    if type(packet.cases) is not tuple:
        raise Refusal("immutable_case_inventory")
    if tuple(c.number for c in packet.cases) != tuple(range(1, 13)):
        raise Refusal("exact_twelve_case_inventory")
    campaign = Cost()
    resource_actions: set[tuple[str, str]] = set()
    names: set[str] = set()
    for case in packet.cases:
        if (
            type(case.operations) is not tuple
            or not case.operations
            or (case.interruption is not None and case.number != 12)
        ):
            raise Refusal("case_operations")
        if case.number == 12 and case.interruption not in INTERRUPTIONS:
            raise Refusal("case12_reachable_interruption_required")
        stages = tuple(dict.fromkeys(o.stage for o in case.operations))
        terminal_stage = (
            "restore"
            if case.interruption == "unknown_restore"
            else "cleanup"
            if case.interruption == "unknown_cleanup"
            else "challenge"
        )
        expected = (
            REQUIRED_STAGES
            if case.number != 12
            else (*REQUIRED_STAGES[: REQUIRED_STAGES.index(terminal_stage)], "interruption")
        )
        if stages != expected:
            raise Refusal("fixed_case_stage_order")
        if case.number != 12 and not any(
            o.stage == "challenge"
            and o.action == CASE_OBLIGATIONS[case.number - 1]
            and o.cost.challenges == 1
            for o in case.operations
        ):
            raise Refusal("exact_case_obligation_missing")
        if case.number == 12 and not any(
            o.stage == "interruption" and o.action == case.interruption and o.cost.challenges == 1
            for o in case.operations
        ):
            raise Refusal("exact_terminal_sequence_missing")
        # dict.fromkeys alone would permit a later return to an earlier stage.
        if any(
            stages.index(a.stage) > stages.index(b.stage)
            for a, b in zip(case.operations, case.operations[1:], strict=False)
        ):
            raise Refusal("stage_reentry")
        run = Cost()
        captures: list[str] = []
        capture_queries = 0
        capture_wire = 0
        for op in case.operations:
            op.cost.validate()
            if (
                not op.name
                or op.name in names
                or not op.action
                or not op.channel
                or op.cost.requests > 1
                or op.cost.sql_statements > 8
                or op.cost.outbound_bytes > 65536
                or op.cost.inbound_bytes > 262144
                or op.cost.captures > 1
            ):
                raise Refusal("operation_bound_or_identity")
            names.add(op.name)
            categories = (
                op.cost.reader_queries
                + op.cost.receipt_reads
                + op.cost.metadata_reads
                + op.cost.authenticated_checks
                + op.cost.mutations
                + op.cost.creates
                + op.cost.deletes
            )
            if categories != op.cost.requests:
                raise Refusal("one_real_request_per_operation")
            if op.cost.reader_queries and (
                op.stage not in ("baseline", "preflight", "restored")
                or op.cost.outbound_bytes > 32768
            ):
                raise Refusal("reader_request_bound")
            if op.stage in ("baseline", "preflight", "restored"):
                capture_queries += op.cost.reader_queries
                capture_wire += op.cost.inbound_bytes
            if op.capture is not None:
                if (
                    op.capture != op.stage
                    or op.cost.captures != 1
                    or op.capture not in ("baseline", "preflight", "restored")
                    or not 1 <= capture_queries <= 32
                    or capture_wire > 4 * 1024**2
                ):
                    raise Refusal("capture_order_or_query_bound")
                captures.append(op.capture)
                capture_queries = 0
                capture_wire = 0
            elif op.cost.captures:
                raise Refusal("undeclared_capture")
            if op.cost.creates or op.cost.deletes:
                if (
                    not op.resource
                    or (op.resource, "create" if op.cost.creates else "delete") in resource_actions
                ):
                    raise Refusal("resource_latch")
                resource_actions.add((op.resource, "create" if op.cost.creates else "delete"))
            run = run.plus(op.cost)
        if captures != (
            ["baseline", "preflight", "restored"] if case.number != 12 else ["baseline"]
        ):
            raise Refusal("exact_captures_no_replacement")
        if not run.within(RUN_LIMIT):
            raise Refusal("run_budget")
        campaign = campaign.plus(run)
    if not campaign.within(CAMPAIGN_LIMIT):
        raise Refusal("campaign_budget")


class SQLiteJournal:
    """Concrete cold-restart latch for synthetic source rehearsal.

    Supply an absolute fresh external path, never a compared D1/object database.
    FULL synchronous transactions persist counters and dispatching before I/O.
    A single immutable campaign reservation survives terminal, crash and new keys.
    SQLite/FS durability is a source mechanism, not managed-service proof.
    """

    def __init__(self, path: Path):
        if not path.is_absolute() or path.is_symlink():
            raise Refusal("external_journal_path")
        self.path = path
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS campaign (
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                  packet TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL,
                  reason TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (
                  name TEXT PRIMARY KEY, case_number INTEGER NOT NULL,
                  operation TEXT NOT NULL, status TEXT NOT NULL,
                  actual TEXT, evidence_digest TEXT, evidence BLOB, snapshot BLOB);
            """)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=0, isolation_level="IMMEDIATE")
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def latch(self, packet: Packet, digest: str) -> None:
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO campaign VALUES(1,?,?, 'running', '')",
                    (_json(dataclasses.asdict(packet)), digest),
                )
            except sqlite3.IntegrityError as exc:
                raise _CampaignAlreadyReserved("campaign_already_reserved_no_replay") from exc

    def reserve(self, case: int, operation: Operation) -> None:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute("SELECT status FROM campaign WHERE singleton=1").fetchone()
            unknown = db.execute("SELECT 1 FROM operations WHERE status='dispatching'").fetchone()
            if state != ("running",) or unknown:
                raise Refusal("journal_terminal_or_unknown")
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,'dispatching',NULL,NULL,NULL,NULL)",
                (operation.name, case, _json(dataclasses.asdict(operation))),
            )

    def finish(self, case: int, operation: Operation, receipt: Receipt) -> None:
        with self._db() as db:
            updated = db.execute(
                "UPDATE operations SET status=?,actual=?,evidence_digest=?,evidence=?,snapshot=? "
                "WHERE name=? AND case_number=? AND operation=? AND status='dispatching'",
                (
                    receipt.status,
                    _json(dataclasses.asdict(receipt.actual_cost)),
                    hashlib.sha256(receipt.evidence).hexdigest(),
                    receipt.evidence,
                    receipt.snapshot.canonical if receipt.snapshot is not None else None,
                    operation.name,
                    case,
                    _json(dataclasses.asdict(operation)),
                ),
            ).rowcount
            if updated != 1:
                raise Refusal("journal_finish_not_exact")

    def terminal(self, status: str, reason: str) -> None:
        with self._db() as db:
            # A terminal ACK may return after its deadline/source fence. The
            # sole permitted terminal transition is conservative downgrade to
            # unknown; it never releases the campaign or re-enables dispatch.
            predicate = (
                "status IN ('running','mechanism_complete','closed_refusal')"
                if status == "unknown"
                else "status='running'"
            )
            changed = db.execute(
                "UPDATE campaign SET status=?,reason=? WHERE singleton=1 AND " + predicate,
                (status, reason),
            ).rowcount
            if changed != 1:
                raise Refusal("journal_terminal_not_exact")


class Runner:
    def __init__(
        self,
        packet: Packet,
        journal: Journal,
        adapters: Mapping[str, Adapter],
        clock: Callable[[], float],
        source_check: Callable[[], str],
        oracle: Oracle | None = None,
    ):
        self.packet, self.journal, self.adapters = packet, journal, dict(adapters)
        self.clock, self.source_check = clock, source_check
        self.oracle = oracle if oracle is not None else DisabledOracle()
        self._last_time = packet.starts
        self._packet_identity: str | None = None
        self._oracle_identity = id(self.oracle)
        self._adapter_identities = {name: id(value) for name, value in self.adapters.items()}

    def _check(self, end: float) -> float:
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise Refusal("invalid_monotonic_clock")
        if not self.packet.starts <= now < min(end, self.packet.deadline):
            raise Refusal("deadline_or_not_started")
        if now < self._last_time:
            raise Refusal("monotonic_clock_rewound")
        self._last_time = now
        if self.source_check() != self.packet.source_pin:
            raise Refusal("source_binding_drift")
        if (
            packet_digest(self.packet) != self._packet_identity
            or id(self.oracle) != self._oracle_identity
            or {name: id(value) for name, value in self.adapters.items()}
            != self._adapter_identities
        ):
            raise Refusal("source_program_identity_drift")
        # Source checking may itself block; include that time in this boundary.
        after = self.clock()
        if type(after) not in (int, float) or not math.isfinite(after) or after < now:
            raise Refusal("monotonic_clock_rewound")
        if not self.packet.starts <= after < min(end, self.packet.deadline):
            raise Refusal("deadline_or_not_started")
        self._last_time = after
        return after

    def run(self) -> Result:
        completed = 0
        latched = False
        try:
            validate_packet(self.packet)
            self._packet_identity = packet_digest(self.packet)
            self._check(self.packet.deadline)
            assert self.packet.context is not None
            # SOURCE dispatch is limited to this reviewed concrete miniature.
            # Arbitrary callbacks cannot authenticate themselves with a pin or
            # manufacture completion from matching end-state bytes.
            from mechanism import MechanismAdapter, MechanismOracle, make_packet

            expected = make_packet(
                self.packet.selected_case,
                interruption=self.packet.cases[11].interruption or "partial_output",
            )
            if (
                self.packet.cases != expected.cases
                or self.packet.context != expected.context
                or self.packet.source_pin != expected.source_pin
                or type(self.oracle) is not MechanismOracle
                or set(self.adapters) != {"mechanism"}
                or type(self.adapters["mechanism"]) is not MechanismAdapter
            ):
                raise Refusal("source_owned_program_or_driver_required")
            for adapter in self.adapters.values():
                if getattr(adapter, "program_pin", None) != self.packet.context.program_pin:
                    raise Refusal("source_owned_adapter_program_binding_required")
            # An attempted durable reservation may commit before its ACK is
            # lost. Treat that boundary as spent before calling the journal.
            latched = True
            try:
                self.journal.latch(self.packet, packet_digest(self.packet))
            except _CampaignAlreadyReserved:
                # This precise refusal is emitted by the authoritative INSERT
                # failure; it did not create or acquire another reservation.
                latched = False
                raise
            run_end = self.packet.deadline
            call_end = self.packet.deadline
            for case in self.packet.cases:
                if case.number != self.packet.selected_case:
                    continue
                run_end = min(self.clock() + 1200, self.packet.deadline)
                snapshots: dict[str, Snapshot] = {}
                baseline_at: float | None = None
                restored_at: float | None = None
                for op in case.operations:
                    now = self._check(run_end)
                    if op.stage == "preflight" and baseline_at is not None:
                        if now - baseline_at >= self.packet.baseline_freshness:
                            raise Refusal("baseline_freshness")
                    if op.stage == "restored" and restored_at is not None:
                        if now - restored_at >= self.packet.baseline_freshness:
                            raise Refusal("restored_freshness")
                    # Reservation is durable BEFORE invoking even local fault work.
                    self.journal.reserve(case.number, op)
                    call_end = min(
                        now + 60,
                        run_end,
                        self.packet.deadline,
                        baseline_at + self.packet.baseline_freshness
                        if op.stage == "preflight" and baseline_at is not None
                        else self.packet.deadline,
                        restored_at + self.packet.baseline_freshness
                        if op.stage == "restored" and restored_at is not None
                        else self.packet.deadline,
                    )
                    self._check(call_end)
                    receipt = self.adapters.get(op.channel, DisabledAdapter()).invoke(op, call_end)
                    self._check(call_end)
                    if (
                        receipt.status not in ("confirmed", "refused", "unknown")
                        or type(receipt.evidence) is not bytes
                        or not receipt.evidence
                        or not receipt.actual_cost.within(op.cost)
                    ):
                        raise Refusal("invalid_or_unmeasurable_receipt")
                    retained_bytes = (
                        len(receipt.evidence) + len(receipt.snapshot.canonical)
                        if receipt.snapshot is not None
                        else len(receipt.evidence)
                    )
                    retained_bytes += len(_json(dataclasses.asdict(op)).encode())
                    retained_bytes += len(_json(dataclasses.asdict(receipt.actual_cost)).encode())
                    if receipt.actual_cost.artifact_bytes < retained_bytes:
                        raise Refusal("unaccounted_retained_artifact_bytes")
                    self.journal.finish(case.number, op, receipt)
                    self._check(call_end)
                    if receipt.status == "unknown":
                        raise Refusal("operation_outcome_unknown")
                    self.oracle.verify_receipt(op, receipt)
                    self._check(call_end)
                    if op.stage == "interruption":
                        if receipt.status != "refused":
                            raise Refusal("interruption_did_not_refuse")
                        self._check(call_end)
                        self.journal.terminal("closed_refusal", case.interruption or "interruption")
                        self._check(call_end)
                        return Result(
                            "closed_refusal", completed, case.interruption or "interruption"
                        )
                    if receipt.status != "confirmed":
                        raise Refusal("operation_refused_shared_reuse_stopped")
                    if op.stage == "restore_readback":
                        restored_at = self._check(call_end)
                    if op.capture is not None:
                        snap = receipt.snapshot
                        if (
                            snap is None
                            or not snap.complete
                            or not snap.canonical
                            or len(snap.canonical) > 512 * 1024
                            or snap.source_pin != self.packet.source_pin
                            or not snap.identity
                        ):
                            raise Refusal("incomplete_or_unbound_snapshot")
                        if snapshots:
                            first = snapshots["baseline"]
                            if snap.identity != first.identity or snap.canonical != first.canonical:
                                raise Refusal("complete_typed_equality_failed")
                        self.oracle.verify(snap)
                        self._check(call_end)
                        snapshots[op.capture] = snap
                        if op.capture == "baseline":
                            baseline_at = now
                    # Every synchronous callback/journal/oracle return is a yield
                    # boundary too: no later action inherits a stale check.
                    self._check(call_end)
                completed += 1
            self._check(call_end)
            self.journal.terminal("mechanism_complete", "selected_source_case_complete")
            self._check(call_end)
            return Result("mechanism_complete", completed, "selected_source_case_complete")
        except Exception as exc:
            reason = str(exc) if isinstance(exc, Refusal) else "external_ack_or_adapter_unknown"
            if latched:
                try:
                    self.journal.terminal("unknown", reason)
                except Exception:
                    reason = "terminal_ack_unknown"
            return Result("unknown" if latched else "refused", completed, reason)
