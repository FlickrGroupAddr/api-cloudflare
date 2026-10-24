"""Source-owned finite miniature programs, never full-candidate qualification.

MIT License; copyright 2026 Terry Ott. SQLite is the SOURCE model, not D1 or
Durable Object API emulation. Each execute below is one manifested SQL attempt.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

from runner import (
    CASE_OBLIGATIONS,
    OBJECT_PROFILE,
    PROFILE,
    REQUIRED_STAGES,
    Case,
    Cost,
    Operation,
    Packet,
    Receipt,
    Refusal,
    Snapshot,
    SourceContext,
)

TABLES = (
    "control",
    "application",
    "audit",
    "session",
    "quota",
    "object_kv",
    "alarm",
    "cascade_parent",
)
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE control(id INTEGER PRIMARY KEY, state TEXT NOT NULL, generation INTEGER NOT NULL);
INSERT INTO control VALUES(1,'open',1);
CREATE TABLE application(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO application VALUES(1,'synthetic');
CREATE TABLE audit(id INTEGER PRIMARY KEY, event TEXT NOT NULL);
CREATE TABLE cascade_parent(id INTEGER PRIMARY KEY);
INSERT INTO cascade_parent VALUES(1);
CREATE TABLE session(id INTEGER PRIMARY KEY, value TEXT NOT NULL,
 parent_id INTEGER NOT NULL DEFAULT 1 REFERENCES cascade_parent(id) ON DELETE CASCADE);
INSERT INTO session(id,value) VALUES(1,'synthetic');
CREATE TABLE quota(id INTEGER PRIMARY KEY, credit INTEGER NOT NULL);
INSERT INTO quota VALUES(1,100);
CREATE TABLE object_kv(id TEXT PRIMARY KEY, value BLOB NOT NULL);
INSERT INTO object_kv VALUES('binary',x'00ff');
CREATE TABLE alarm(id INTEGER PRIMARY KEY, instant INTEGER);
INSERT INTO alarm VALUES(1,NULL);
"""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def source_pin() -> str:
    """Stable source identity; independently retained expected pin stays external."""
    here = Path(__file__).resolve().parent
    oracle = here.parent / "pmb1-full-state-oracle/full_state_oracle.py"
    return _sha(
        b"".join(path.read_bytes() for path in (here / "mechanism.py", here / "runner.py", oracle))
    )


def initialize(db: sqlite3.Connection) -> None:
    for sql in setup_sql():
        db.executescript(sql)
    db.commit()


def setup_sql() -> tuple[str, ...]:
    statements = [v.strip() + ";" for v in SCHEMA.split(";") if v.strip()]
    for table in TABLES[1:]:
        for action in ("INSERT", "UPDATE", "DELETE"):
            cascade = (
                " AND NOT EXISTS(SELECT 1 FROM session WHERE parent_id=OLD.id)"
                if table == "cascade_parent" and action == "DELETE"
                else ""
            )
            statements.append(f"""CREATE TRIGGER guard_{table}_{action.lower()}
            BEFORE {action} ON {table}
            WHEN COALESCE((SELECT state='open' AND generation=1
                          FROM control WHERE id=1),0)=0{cascade}
            BEGIN SELECT RAISE(ABORT,'closed'); END;""")
    return tuple("\n".join(statements[n : n + 8]) for n in range(0, len(statements), 8))


CHALLENGES = {
    1: ("UPDATE application SET value='forbidden' WHERE id=1",),
    2: ("UPDATE application SET value='late-admitted' WHERE id=1",),
    3: (
        "INSERT INTO application VALUES(1,'stale') ON CONFLICT(id) DO UPDATE SET value='stale'",
        "INSERT OR REPLACE INTO application VALUES(1,'stale')",
        "DELETE FROM cascade_parent WHERE id=1",
    ),
    7: (
        "UPDATE application SET value='original-delayed' WHERE id=1",
        "UPDATE application SET value='temporary-delayed' WHERE id=1",
    ),
    8: (
        "INSERT INTO audit VALUES(1,'scheduled-maintenance')",
        "INSERT INTO session(id,value) VALUES(2,'session-write')",
        "INSERT INTO audit VALUES(2,'authentication-failure')",
        "UPDATE quota SET credit=credit-1 WHERE id=1",
    ),
    9: (
        "INSERT INTO audit VALUES(1,'service-entry')",
        "INSERT INTO audit VALUES(2,'queue-entry')",
        "INSERT INTO audit VALUES(3,'hint-entry')",
        "UPDATE alarm SET instant=999 WHERE id=1",
        "UPDATE object_kv SET value=x'ff00' WHERE id='binary'",
    ),
}


def _rows(db: sqlite3.Connection, sql: str) -> list:
    return [
        [{"blob": value.hex()} if type(value) is bytes else value for value in row]
        for row in db.execute(sql).fetchall()
    ]


def _schema_sql() -> str:
    return "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name"


def _table_sql(table: str) -> str:
    return f'SELECT rowid,* FROM "{table}" ORDER BY rowid'


COLUMNS = {
    "control": ("id", "state", "generation"),
    "application": ("id", "value"),
    "audit": ("id", "event"),
    "session": ("id", "value", "parent_id"),
    "quota": ("id", "credit"),
    "object_kv": ("id", "value"),
    "alarm": ("id", "instant"),
    "cascade_parent": ("id",),
}


def _cell(value):
    if value is None:
        return ["null", None]
    if type(value) is int and -(2**63) <= value < 2**63:
        return ["integer", value]
    if type(value) is str:
        value.encode("utf-8", errors="strict")
        return ["text", value]
    if type(value) is bytes:
        return ["blob", value.hex()]
    raise Refusal("actual_REAL_or_unsupported_cell")


def programs(interruption: str = "partial_output") -> tuple[Case, ...]:
    """Twelve distinct source programs; selection cannot rewrite fault position.

    Negative cases intentionally terminate before restoration/reuse. Source
    tests select each reachable program on a fresh synthetic fixture/journal.
    That is not permission for twelve fresh hosted resources or extra real runs.
    """
    if interruption != "partial_output":
        raise Refusal("uncovered_interruption_variant_no_allocation")
    result = []
    for number in range(1, 13):
        terminal = (
            "restore"
            if interruption == "unknown_restore"
            else "cleanup"
            if interruption == "unknown_cleanup"
            else "challenge"
        )
        stages = (
            REQUIRED_STAGES
            if number != 12
            else (*REQUIRED_STAGES[: REQUIRED_STAGES.index(terminal)], "interruption")
        )
        operations = []
        for stage in stages:
            if stage == "settle":
                for index, _ in enumerate(setup_sql()):
                    operations.append(
                        Operation(
                            f"case{number}_setup_{index}",
                            stage,
                            Cost(
                                requests=1,
                                mutations=1,
                                sql_statements=8,
                                effects=8,
                                artifact_bytes=16384,
                            ),
                            "mechanism",
                            f"sqlite.setup.{index}",
                        )
                    )
            if stage in ("baseline", "preflight", "restored"):
                for page in range(len(TABLES) + 1):
                    last = page == len(TABLES)
                    operations.append(
                        Operation(
                            f"case{number}_{stage}_{page}",
                            stage,
                            Cost(
                                requests=1,
                                reader_queries=1,
                                sql_statements=1,
                                captures=int(last),
                                artifact_bytes=16384,
                            ),
                            "mechanism",
                            f"sqlite.capture.{page}",
                            stage if last else None,
                        )
                    )
                continue
            action = (
                CASE_OBLIGATIONS[number - 1]
                if stage == "challenge"
                else (interruption if stage == "interruption" else f"case{number}.{stage}")
            )
            # Every actual query/write is one adapter invocation. Trigger attempts
            # have one fixed RAISE effect and no row mutation; reserve eight SQL
            # statements conservatively, including the guarded statement tree.
            mutation = stage in (
                "settle",
                "close",
                "challenge",
                "temporary_install",
                "admission_off",
                "restore",
            )
            local = stage in ("cleanup", "interruption")
            cost = Cost(
                requests=0 if local else 1,
                mutations=int(mutation and not local),
                receipt_reads=int(not mutation and not local),
                sql_statements=0 if local else 8 if stage == "challenge" else 1,
                effects=8 if stage == "challenge" else int(mutation and not local),
                artifact_bytes=16384,
                challenges=int(stage in ("challenge", "interruption")),
            )
            operations.append(Operation(f"case{number}_{stage}", stage, cost, "mechanism", action))
            if stage == "challenge" and number in CHALLENGES:
                for index in range(1, len(CHALLENGES[number])):
                    operations.append(
                        Operation(
                            f"case{number}_challenge_{index}",
                            stage,
                            dataclasses.replace(cost, challenges=0),
                            "mechanism",
                            f"sqlite.challenge.{index}",
                        )
                    )
            if stage == "restore_readback" and number == 7:
                for index in range(2):
                    operations.append(
                        Operation(
                            f"case7_delayed_after_restore_{index}",
                            stage,
                            Cost(
                                requests=1,
                                mutations=1,
                                sql_statements=8,
                                effects=1,
                                artifact_bytes=16384,
                            ),
                            "mechanism",
                            f"sqlite.restored-delayed.{index}",
                        )
                    )
        result.append(Case(number, tuple(operations), interruption if number == 12 else None))
    return tuple(result)


def make_packet(number: int, *, interruption: str = "partial_output") -> Packet:
    cases = programs(interruption)
    pin = source_pin()
    program_pin = _sha(_canonical([dataclasses.asdict(c) for c in cases]))
    oracle_pin = _sha(
        (
            Path(__file__).resolve().parent.parent / "pmb1-full-state-oracle/full_state_oracle.py"
        ).read_bytes()
    )
    context = SourceContext(
        pin,
        _sha(b"synthetic-retained-artifact"),
        _sha(_canonical({"tables": TABLES, "closed_generation": 1})),
        _sha(SCHEMA.encode()),
        _sha("\n".join(setup_sql()).encode()),
        oracle_pin,
        ("synthetic-d1", "synthetic-object-kv-alarm"),
        ("1", "1"),
        8,
        29,
        program_pin,
    )
    return Packet(
        "source-case-" + str(number),
        pin,
        PROFILE,
        OBJECT_PROFILE,
        cases,
        0,
        1200,
        context=context,
        selected_case=number,
    )


class MechanismOracle:
    """Independent initialization from reviewed SQL, never target-derived truth."""

    def __init__(self, packet: Packet, repository_root: Path | None = None):
        self.packet = packet
        root = (
            repository_root if repository_root is not None else Path(__file__).resolve().parents[2]
        )
        path = root / "probes/pmb1-full-state-oracle/full_state_oracle.py"
        spec = importlib.util.spec_from_file_location("_finite_pmb1_independent_oracle", path)
        if spec is None or spec.loader is None:
            raise Refusal("independent_reference_source_unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.reference_check = module.check
        db = sqlite3.connect(":memory:")
        try:
            initialize(db)
            db.execute("UPDATE control SET state='closed' WHERE id=1")
            db.commit()
            self.reference = module.read_reference(db)
            if any(
                cell[0] == "real"
                for table in self.reference.tables.values()
                for _, row in table.rows
                for cell in row
            ):
                raise Refusal("independent_reference_REAL")
        finally:
            db.close()

    def verify_receipt(self, operation: Operation, receipt: Receipt) -> None:
        value = json.loads(receipt.evidence)
        expected = {
            "operation": operation.name,
            "source": self.packet.source_pin,
            "fact": "guarded-rejection"
            if operation.stage == "challenge"
            else "closed"
            if operation.stage.endswith("readback")
            else "source-observed",
        }
        if operation.stage == "interruption":
            expected["partial"] = '{"schema":'
        if value != expected:
            raise Refusal("independent_mechanism_receipt_mismatch")

    def verify(self, snapshot: Snapshot) -> None:
        value = json.loads(snapshot.canonical)
        if any(
            cell[0] == "real"
            for table in value["tables"].values()
            for row in table["rows"]
            for cell in row
        ):
            raise Refusal("observed_REAL_refused")
        self.reference_check(self.reference, value)


class MechanismAdapter:
    """Fixed synthetic SQL implementation, no label-to-success callback.

    Failure positions below are concrete and case-owned. Distinct negative
    programs stop immediately: no repair, replay, forced restore or reopen.
    Optional hook is only for adversarial SOURCE tests, never actual dispatch.
    """

    def __init__(self, packet: Packet, clock):
        if packet.cases != programs(packet.cases[11].interruption or "partial_output"):
            raise Refusal("source_owned_program_mismatch")
        self.packet, self.clock = packet, clock
        self.program_pin = packet.context.program_pin if packet.context else ""
        self.db = sqlite3.connect(":memory:")
        self.pages = {}
        self.calls = []
        self.after: Callable[[Operation], None] | None = None
        self.retained = b"synthetic-retained-artifact"
        self.pending_generations = []
        self.observation_expires = packet.deadline

    def close(self):
        self.db.close()

    def invoke(self, operation: Operation, deadline: float) -> Receipt:
        case = self.packet.cases[self.packet.selected_case - 1]
        if (
            operation not in case.operations
            or self.clock() >= deadline
            or self.clock() >= self.observation_expires
        ):
            raise Refusal("fixed_operation_or_deadline")
        self.calls.append(operation.name)
        stage, number = operation.stage, case.number
        fact = "source-observed"
        snapshot = None
        sql_count = 0
        effects = 0

        def execute(sql):
            nonlocal sql_count, effects
            sql_count += 1
            before = self.db.total_changes
            try:
                return self.db.execute(sql)
            finally:
                effects += self.db.total_changes - before

        if operation.action.startswith("sqlite.setup."):
            index = int(operation.action.rsplit(".", 1)[1])
            batch = setup_sql()[index]
            # Trace callback sees trigger bodies as CREATE syntax, not effects.
            traced = []
            before = self.db.total_changes
            self.db.set_trace_callback(traced.append)
            try:
                self.db.executescript(batch)
            finally:
                self.db.set_trace_callback(None)
            sql_count, effects = len(traced), self.db.total_changes - before
        elif stage == "settle":
            if number == 2:
                # Concrete write admitted and committed before close.
                execute("UPDATE application SET value='synthetic' WHERE id=1")
                self.db.commit()
                self.pending_generations.append("admitted-open-1")
            elif number == 5:
                # Malformed precomparison control must never be normalized.
                execute("DELETE FROM control WHERE id=1")
            else:
                execute("SELECT state,generation FROM control WHERE id=1").fetchall()
        elif stage == "close":
            execute(
                "UPDATE control SET state='closed' WHERE id=1 AND state='open' AND generation=1"
            )
            self.db.commit()
            if number == 4:
                raise RuntimeError("source_lost_close_ack_after_commit")
        elif stage == "closure_readback":
            rows = execute("SELECT state,generation FROM control WHERE id=1").fetchall()
            if rows != [("closed", 1)]:
                raise Refusal("malformed_or_missing_control_fail_closed")
            fact = "closed"
        elif stage in ("baseline", "preflight", "restored"):
            if number == 6 and stage == "preflight":
                # The deadline expires BEFORE another SQL observation is sent.
                if self.clock() >= self.observation_expires:
                    raise Refusal("source_observation_credential_expired")
            page = int(operation.action.rsplit(".", 1)[1])
            sql = _schema_sql() if page == 0 else _table_sql(TABLES[page - 1])
            rows = execute(sql).fetchall()
            clean = (
                [list(row) for row in rows]
                if page == 0
                else {
                    "columns": list(COLUMNS[TABLES[page - 1]]),
                    "rows": [[_cell(v) for v in row[1:]] for row in rows],
                    "rowids": [row[0] for row in rows],
                }
            )
            self.pages.setdefault(stage, {})["schema" if page == 0 else TABLES[page - 1]] = clean
            if operation.capture:
                acquired = self.pages[stage]
                snapshot = Snapshot(
                    _canonical(
                        {"schema": acquired["schema"], "tables": {n: acquired[n] for n in TABLES}}
                    ),
                    self.packet.source_pin,
                    "synthetic-complete-seven-table",
                    True,
                )
        elif stage == "challenge":
            if number == 6:
                # Genuine finite source observation interval ends NOW. The
                # following preflight cannot invoke another SQL query.
                execute("SELECT state FROM control WHERE id=1").fetchall()
                self.observation_expires = self.clock()
                fact = "guarded-rejection"
                actual = dataclasses.replace(
                    operation.cost, sql_statements=sql_count, effects=effects
                )
                return Receipt(
                    "confirmed",
                    actual,
                    _canonical(
                        {
                            "operation": operation.name,
                            "source": self.packet.source_pin,
                            "fact": fact,
                        }
                    ),
                )
            if number == 10:
                execute("DROP TRIGGER guard_application_update")
                raise Refusal("trusted_operator_guard_bypass_detected")
            if number == 11:
                execute("DROP TRIGGER guard_application_update")
                execute("UPDATE application SET value='transient' WHERE id=1")
                execute("UPDATE application SET value='synthetic' WHERE id=1")
                raise Refusal("broken_guard_mutate_revert_detected")
            index = (
                int(operation.action.rsplit(".", 1)[1])
                if operation.action.startswith("sqlite.challenge.")
                else 0
            )
            sql = CHALLENGES.get(number, CHALLENGES[1])[index]
            try:
                execute(sql)
            except sqlite3.IntegrityError:
                fact = "guarded-rejection"
            else:
                raise Refusal("guard_failed")
        elif stage == "challenge_readback":
            rows = execute("SELECT value FROM application WHERE id=1").fetchall()
            if rows != [("synthetic",)]:
                raise Refusal("challenge_effect_persisted")
            fact = "closed"
        elif stage == "admission_off":
            execute("SELECT state FROM control WHERE id=1").fetchall()
        elif stage == "temporary_install":
            execute("SELECT state FROM control WHERE id=1").fetchall()
            self.retained = b"synthetic-temporary-artifact"
        elif stage == "restore":
            execute("SELECT state,generation FROM control WHERE id=1").fetchall()
            self.retained = b"synthetic-retained-artifact"
            if number == 7:
                self.pending_generations.extend(("original-delayed", "temporary-delayed"))
        elif operation.action.startswith("sqlite.restored-delayed."):
            index = int(operation.action.rsplit(".", 1)[1])
            try:
                execute(CHALLENGES[7][index])
            except sqlite3.IntegrityError:
                pass
            else:
                raise Refusal("restored_delayed_generation_not_fenced")
            fact = "closed"
        elif stage in ("restore_readback", "cleanup_readback"):
            rows = execute("SELECT state,generation FROM control WHERE id=1").fetchall()
            if rows != [("closed", 1)] or self.retained != b"synthetic-retained-artifact":
                raise Refusal("exact_restore_or_cleanup_readback")
            fact = "closed"
        elif stage == "cleanup":
            # No resource deletion in this source model. Retain exact fixture,
            # partials and journal; cleanup is an explicit local disposition.
            pass
        elif stage == "interruption":
            if case.interruption in ("unknown_restore", "unknown_cleanup"):
                raise RuntimeError("source_unknown_terminal_action")
            return Receipt(
                "refused",
                Cost(challenges=1, artifact_bytes=16384),
                _canonical(
                    {
                        "operation": operation.name,
                        "source": self.packet.source_pin,
                        "fact": "source-observed",
                        "partial": '{"schema":',
                    }
                ),
            )
        else:
            raise Refusal("unsupported_mechanism_method")
        actual = dataclasses.replace(operation.cost, sql_statements=sql_count, effects=effects)
        if self.after is not None:
            self.after(operation)
        return Receipt(
            "confirmed",
            actual,
            _canonical(
                {"operation": operation.name, "source": self.packet.source_pin, "fact": fact}
            ),
            snapshot,
        )
