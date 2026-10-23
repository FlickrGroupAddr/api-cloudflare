"""Executable synthetic successor lifecycle, deliberately no production capability.

The model uses the accepted distinct two-statement protocol. Its result and
returned-receipt wrappers are not native/production qualification or receipts.
Python is required here by the existing external operator/journal runtime.
"""

import json
import math
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import adapter


@dataclass(frozen=True)
class SyntheticBatchReceipt:
    batch: Any
    count: int
    evidence: bytes


@dataclass(frozen=True)
class SyntheticOutcome:
    result: adapter.Result
    scope: str = "SYNTHETIC_QUALIFICATION_ONLY"


@dataclass(frozen=True)
class SyntheticReturnedReceipt:
    reference: str
    predecessor: adapter.Intent
    outcome: SyntheticOutcome


class _ReceiptBridge:
    def __init__(self, custodian):
        self.custodian = custodian

    def read(self, reference, deadline):
        model = self.custodian.read(reference, deadline)
        return adapter.ConfirmedReceipt(model.reference, model.predecessor, model.outcome.result)


class _Control(adapter.Adapter):
    """Internal model control; never fed to the historical single UPDATE port."""

    writer: Any

    def _dispatch_reserved(self, intent):
        claimed = False
        self.evidence = None
        read_start = len(self.writer.read_evidence)
        try:
            self.check(intent)
            before = self.observe(intent)
            if before != (intent.expected, "open" if intent.operation == "close" else "closed"):
                raise adapter.Refusal("stale_or_wrong_state")
            claimed = True
            if self.journal.claim_dispatch(intent.key, self.check(intent)) is not True:
                raise adapter.Refusal("dispatch_claim_unconfirmed")
            batch = self.writer.build_batch(intent)
            receipt = self.writer.dispatch_batch(batch, self.check(intent))
            self.check(intent)
            if type(receipt) is not SyntheticBatchReceipt or receipt.batch != batch:
                raise adapter.Refusal("distinct_exact_batch_receipt_required")
            if type(receipt.count) is not int or receipt.count not in (0, 1):
                raise adapter.Refusal("exact_batch_count")
            if receipt.count == 0:
                self.journal.settle(intent.key, "refused", self.check(intent))
                self.check(intent)
                return adapter.Result("refused", "zero_affected_rows")
            observed = self.observe(intent)
            if observed != (intent.next_generation, intent.target):
                raise adapter.Refusal("transition_readback_mismatch")
            self.journal.settle(intent.key, "confirmed", self.check(intent))
            self.check(intent)
            # An actual returned model result, after final journal ACK and checks.
            self.evidence = json.dumps(
                {
                    "batch": json.loads(receipt.evidence),
                    "independentPrimaryRequests": self.writer.read_evidence[read_start:],
                    "finalJournalAcknowledged": True,
                    "returnedAt": self.last_time,
                },
                sort_keys=True,
            ).encode()
            return adapter.Result(
                "confirmed", "one_row_and_independent_readback", *observed, self.last_time
            )
        except Exception:
            try:
                self.journal.settle(
                    intent.key,
                    "unknown" if claimed else "refused",
                    self.check(intent, reconciliation=True),
                )
            except Exception:
                pass
            return adapter.Result("unknown" if claimed else "refused", "operation_unconfirmed")


class _Clock:
    def __init__(self, now):
        self.now = now


class Qualification:
    """Synthetic integration only; source-bound binding supplies all three ports.

    Constructor is inert. This interface does not accept production qualification
    flags, credential loaders, native capabilities or caller-created receipts.
    """

    def __init__(self, binding):
        self.binding = binding
        self._control = _Control(
            binding,
            _Observer(binding),
            binding.journal,
            _Clock(binding.clock),
            target_id=binding.source_target,
            source=binding.source,
        )

    def execute(self, intent):
        if (
            type(intent) is not adapter.Intent
            or asdict(intent) != self.binding.allocation["intents"][0]
        ):
            return SyntheticOutcome(adapter.Result("refused", "synthetic_unretained_root_intent"))
        return SyntheticOutcome(self._control.execute(intent))

    def reconcile(self, intent):
        return SyntheticOutcome(self._control.reconcile(intent))

    def advance(self, predecessor, successor, reference, custodian):
        # Only this independent synthetic invocation producer may supply a model
        # predecessor receipt. FileConfirmations/native Results are not accepted.
        if type(custodian) is not ReturnedInvocations:
            return SyntheticOutcome(adapter.Result("refused", "synthetic_custodian_required"))
        if (
            type(successor) is not adapter.Intent
            or asdict(successor) not in self.binding.allocation["intents"]
        ):
            return SyntheticOutcome(adapter.Result("refused", "synthetic_unretained_successor"))
        self._control.confirmations = _ReceiptBridge(custodian)
        return SyntheticOutcome(self._control.advance(predecessor, successor, reference))


class _Observer:
    def __init__(self, binding):
        self.binding = binding

    def read(self, sql, deadline):
        rows, _meta = self.binding.query("observer", sql, [], deadline)
        return adapter.CompleteRows(rows, True)


class ReturnedInvocations:
    """Append-only external SQLite model custodian that invokes the producer.

    There is no retain(Result) API. Only invoke()'s actual timely returned
    SyntheticOutcome can be retained. Native custody, power-loss, independence
    and protected delivery are explicitly NOT established by this model.
    """

    def __init__(self, path, packet_pin, target, candidate, clock):
        self.path, self.packet_pin = Path(path), packet_pin
        self.target, self.candidate, self.clock = target, candidate, clock
        self.last_time = -1.0

    def _guard(self, deadline):
        now = self.clock()
        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
            or type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or not 0 <= now < deadline
            or now < self.last_time
        ):
            raise adapter.Refusal("synthetic_custodian_deadline")
        self.last_time = now

    def provision(self, deadline):
        self._guard(deadline)
        if not self.path.is_absolute() or self.path.is_symlink():
            raise adapter.Refusal("synthetic_custodian_path")
        # Exclusive creation, no replacement/reset and no automatic provisioning.
        with self.path.open("xb"):
            pass
        with closing(sqlite3.connect(self.path, isolation_level=None, timeout=0)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE binding(packet TEXT,target TEXT,candidate TEXT)")
            db.execute(
                "INSERT INTO binding VALUES(?,?,?)", (self.packet_pin, self.target, self.candidate)
            )
            db.execute(
                "CREATE TABLE receipts(reference TEXT PRIMARY KEY,intent TEXT NOT NULL,"
                "result TEXT NOT NULL,evidence BLOB NOT NULL)"
            )
        self._guard(deadline)

    def _open(self, deadline):
        self._guard(deadline)
        if not self.path.is_absolute() or self.path.is_symlink() or not self.path.is_file():
            raise adapter.Refusal("synthetic_custodian_missing")
        db = sqlite3.connect(
            self.path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=0
        )
        try:
            db.execute("PRAGMA synchronous=FULL")
            if db.execute("SELECT * FROM binding").fetchall() != [
                (self.packet_pin, self.target, self.candidate)
            ]:
                raise adapter.Refusal("synthetic_custodian_binding")
            return db
        except BaseException:
            db.close()
            raise

    def invoke(self, qualification, intent, reference, *, predecessor=None, previous=None):
        end = intent.window.dispatch_until
        self._guard(end)
        if (
            type(qualification) is not Qualification
            or intent.target_id != self.target
            or intent.candidate != self.candidate
            or qualification.binding.packet_sha2_256 != self.packet_pin
            or type(reference) is not str
            or not reference.startswith("synthetic:")
            or not 11 <= len(reference) <= 128
        ):
            raise adapter.Refusal("synthetic_invocation_binding")
        # Check custody BEFORE the invocation; a missing custodian never dispatches.
        with closing(self._open(end)) as db:
            if db.execute("SELECT 1 FROM receipts WHERE reference=?", (reference,)).fetchone():
                raise adapter.Refusal("synthetic_reference_spent")
        outcome = (
            qualification.execute(intent)
            if predecessor is None
            else qualification.advance(predecessor, intent, previous, self)
        )
        self._guard(end)
        qualification.binding.guard(end)
        result = outcome.result
        if result.status == "confirmed":
            evidence = qualification._control.evidence
            if type(evidence) is not bytes or not evidence:
                raise adapter.Refusal("synthetic_invocation_evidence_missing")
            with closing(self._open(end)) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO receipts VALUES(?,?,?,?)",
                    (
                        reference,
                        json.dumps(asdict(intent), sort_keys=True),
                        json.dumps(asdict(result), sort_keys=True),
                        evidence,
                    ),
                )
                self._guard(end)
                db.commit()
                self._guard(end)
            qualification.binding.guard(end)
        return outcome

    def read(self, reference, deadline):
        """Internal model receipt port; never native attestation or public promotion."""
        with closing(self._open(deadline)) as db:
            row = db.execute(
                "SELECT intent,result,evidence FROM receipts WHERE reference=?", (reference,)
            ).fetchone()
        self._guard(deadline)
        if row is None or not row[2]:
            raise adapter.Refusal("synthetic_returned_receipt_missing")
        value = json.loads(row[0])
        value["window"] = adapter.Window(**value["window"])
        return SyntheticReturnedReceipt(
            reference,
            adapter.Intent(**value),
            SyntheticOutcome(adapter.Result(**json.loads(row[1]))),
        )
