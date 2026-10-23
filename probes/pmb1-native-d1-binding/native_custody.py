"""External native invocation custody and exact protected credential delivery.

Construction/import are inert. The trusted operator supplies independently
reviewed pins, paths and facts; this software does not manufacture qualification.
The native controller is separate from the historical and synthetic controllers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

import adapter
import native_sender
import positional_receipt_successor as positional


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require(value, reason):
    if not value:
        raise adapter.Refusal(reason)


def _read_manifest(sql):
    return {
        "protocol": "independent_primary_read",
        "statementCount": 1,
        "requestBodySha2_256": hashlib.sha256(
            (_encode({"sql": sql, "params": []}) + "\n").encode()
        ).hexdigest(),
        "statements": [{"sql": sql, "params": []}],
    }


def _pin(path, expected, limit):
    path = Path(path)
    _require(
        path.is_absolute() and not path.is_symlink() and path.is_file(),
        "native_custody_exact_path",
    )
    _require(
        type(expected) is str and re.fullmatch(r"[a-f0-9]{64}", expected), "native_custody_pin"
    )
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    _require(
        len(raw) <= limit and hashlib.sha256(raw).hexdigest() == expected,
        "native_custody_retained_pin",
    )
    return raw


class ProtectedCredential:
    """One-use exact delivery, never environment/search/discovery or refresh.

    review_path/review_pin are trusted independent operator inputs, not an
    action's self-attested proof. The reviewed record binds the exact protected
    token file, fingerprint, packet, target, source graph, grant and custody.
    Pin equality proves identity only; actual grant/ACL/custody remain facts.
    """

    def __init__(self, review_path, review_pin, packet_pin, target, source_pins, clock, deadline):
        self.review_path, self.review_pin = review_path, review_pin
        self.packet_pin, self.target, self.source_pins = packet_pin, target, dict(source_pins)
        self.clock, self.deadline = clock, deadline
        self.used = False
        self._consume_lock = threading.Lock()
        self.last_time = -1.0

    def _guard(self):
        now = self.clock()
        _require(
            type(now) in (int, float)
            and math.isfinite(now)
            and type(self.deadline) in (int, float)
            and math.isfinite(self.deadline)
            and 0 <= now < self.deadline
            and now >= self.last_time,
            "native_credential_deadline",
        )
        self.last_time = now

    def __call__(self):
        # Atomically consume before any evidence or protected read. A competing
        # caller never waits/retries and cannot pass the check during a race.
        if not self._consume_lock.acquire(blocking=False):
            raise adapter.Refusal("native_credential_delivery_spent")
        try:
            _require(not self.used, "native_credential_delivery_spent")
        finally:
            # Even an interruption of the consume check strands this delivery.
            self.used = True
            self._consume_lock.release()
        self._guard()
        raw = _pin(self.review_path, self.review_pin, 2 * 1024 * 1024)
        record: dict[str, Any] = json.loads(raw)
        _require(
            type(record) is dict
            and set(record)
            == {
                "kind",
                "packetSha2_256",
                "target",
                "sourcePins",
                "credential",
                "grant",
                "custody",
            },
            "native_credential_review_shape",
        )
        _require(
            record["kind"] == "pmb1-reviewed-protected-delivery-v1"
            and record["packetSha2_256"] == self.packet_pin
            and record["target"] == self.target
            and record["sourcePins"] == self.source_pins,
            "native_credential_review_binding",
        )
        for name in ("credential", "grant", "custody"):
            item = record[name]
            _require(
                type(item) is dict and set(item) == {"path", "sha2_256"},
                "native_credential_review_record",
            )
        # Check all non-secret provenance before touching the credential file.
        for name in ("grant", "custody"):
            item = record[name]
            _pin(item["path"], item["sha2_256"], 2 * 1024 * 1024)
        self._guard()
        item = record["credential"]
        token_bytes = _pin(item["path"], item["sha2_256"], 4096)
        _require(
            re.fullmatch(rb"[A-Za-z0-9_.-]{16,4096}", token_bytes), "native_credential_exact_bytes"
        )
        # Recheck the review and evidence after the protected read; no trimming.
        _pin(self.review_path, self.review_pin, 2 * 1024 * 1024)
        for name in ("grant", "custody"):
            item = record[name]
            _pin(item["path"], item["sha2_256"], 2 * 1024 * 1024)
        self._guard()
        return token_bytes.decode("ascii")

    def validate_binding(self, packet_pin, target, source_pins, credential_pin, grant, custody):
        """Sender's non-secret admission cross-check, before any token access."""
        self._guard()
        _require(
            self.packet_pin == packet_pin
            and self.target == target
            and self.source_pins == source_pins,
            "native_credential_admission_binding",
        )
        record: dict[str, Any] = json.loads(
            _pin(self.review_path, self.review_pin, 2 * 1024 * 1024)
        )
        _require(
            type(record) is dict
            and type(record.get("credential")) is dict
            and record["credential"].get("sha2_256") == credential_pin
            and record.get("grant") == grant
            and record.get("custody") == custody,
            "native_credential_admission_evidence",
        )


class _Clock:
    def __init__(self, now):
        self.now = now


class _Observer:
    def __init__(self, sender):
        self.sender = sender
        self.returned = []

    def read(self, sql, deadline):
        start = len(self.sender.read_evidence)
        rows, _meta = self.sender.query("observer", sql, [], deadline)
        evidence = self.sender.read_evidence[start:]
        _require(len(evidence) == 1, "native_primary_receipt_missing")
        item = evidence[0]
        _require(
            type(item) is dict
            and item.get("primary") is True
            and item.get("complete") is True
            and item.get("request") == _read_manifest(sql),
            "native_primary_receipt_binding",
        )
        # Copy full returned rows, not just a success/complete assertion or hash.
        self.returned.append(json.loads(_encode({"receipt": item, "rows": rows})))
        return adapter.CompleteRows(rows, True)


class NativeController(adapter.Adapter):
    """Native-only producer; no caller Result or arbitrary producer callback.

    Final ACK is the timely actual return of journal.settle(), followed by the
    source/clock checks. A phase later read from storage cannot substitute for it.
    """

    writer: Any

    def __init__(self, sender):
        _require(
            type(sender) is native_sender.NativePositionalSender, "native_exact_sender_required"
        )
        core = sender.binding
        self.binding = core
        self.reader = _Observer(sender)
        self.evidence = None
        super().__init__(
            sender,
            self.reader,
            core.journal,
            _Clock(core.clock),
            target_id=core.packet["targetId"],
            source=core.source,
        )

    def execute(self, intent):
        _require(
            type(intent) is adapter.Intent
            and asdict(intent) == self.writer.allocation["intents"][0],
            "native_unretained_root",
        )
        return super().execute(intent)

    def advance(self, predecessor, successor, reference, custodian=None):
        _require(type(custodian) is ReturnedInvocations, "native_exact_custodian_required")
        _require(
            type(successor) is adapter.Intent
            and asdict(successor) in self.writer.allocation["intents"],
            "native_unretained_successor",
        )
        self.confirmations = custodian
        return super().advance(predecessor, successor, reference)

    def _dispatch_reserved(self, intent):
        claimed = False
        self.evidence = None
        start = len(self.reader.returned)
        try:
            self.check(intent)
            before = self.observe(intent)
            _require(
                before == (intent.expected, "open" if intent.operation == "close" else "closed"),
                "native_stale_or_wrong_state",
            )
            claimed = True
            _require(
                self.journal.claim_dispatch(intent.key, self.check(intent)) is True,
                "native_dispatch_claim_unconfirmed",
            )
            batch = self.writer.build_batch(intent)
            _require(
                type(batch) is positional.FixedPositionalBatch
                and batch == positional.build(intent),
                "native_exact_positional_batch_required",
            )
            receipt = self.writer.dispatch_batch(batch, self.check(intent))
            self.check(intent)
            _require(
                type(receipt) is native_sender.NativeBatchReceipt
                and receipt.batch == batch
                and type(receipt.count) is int
                and receipt.count in (0, 1)
                and type(receipt.evidence) is bytes
                and bool(receipt.evidence),
                "native_exact_returned_batch_required",
            )
            if receipt.count == 0:
                self.journal.settle(intent.key, "refused", self.check(intent))
                self.check(intent)
                return adapter.Result("refused", "zero_affected_rows")
            observed = self.observe(intent)
            _require(
                observed == (intent.next_generation, intent.target),
                "native_transition_readback_mismatch",
            )
            reads = self.reader.returned[start:]
            _require(len(reads) == 4, "native_four_complete_primary_reads_required")
            self.journal.settle(intent.key, "confirmed", self.check(intent))
            self.check(intent)
            self.writer.guard(intent.window.dispatch_until)
            self.check(intent)
            self.evidence = _encode(
                {
                    "kind": "pmb1-native-returned-invocation-v1",
                    "packetSha2_256": self.binding.packet_sha2_256,
                    "target": intent.target_id,
                    "intent": asdict(intent),
                    "sourceManifest": json.loads(self.binding.source.manifest),
                    "batch": json.loads(receipt.evidence),
                    "independentPrimaryReads": reads,
                    "finalJournalAcknowledgedAt": self.last_time,
                }
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


_DDL = """
CREATE TABLE binding(packet TEXT NOT NULL,target TEXT NOT NULL,candidate TEXT NOT NULL);
CREATE TABLE clock(singleton INTEGER PRIMARY KEY CHECK(singleton=1),watermark REAL NOT NULL);
CREATE TABLE invocations(reference TEXT PRIMARY KEY,intent_key TEXT NOT NULL UNIQUE,
 intent TEXT NOT NULL,invoked_at REAL NOT NULL);
CREATE TABLE returned(reference TEXT PRIMARY KEY REFERENCES invocations(reference),
 result TEXT NOT NULL,evidence BLOB NOT NULL,returned_at REAL NOT NULL);
CREATE TRIGGER no_invocation_update BEFORE UPDATE ON invocations
 BEGIN SELECT RAISE(ABORT,'append_only'); END;
CREATE TRIGGER no_invocation_delete BEFORE DELETE ON invocations
 BEGIN SELECT RAISE(ABORT,'append_only'); END;
CREATE TRIGGER no_return_update BEFORE UPDATE ON returned
 BEGIN SELECT RAISE(ABORT,'append_only'); END;
CREATE TRIGGER no_return_delete BEFORE DELETE ON returned
 BEGIN SELECT RAISE(ABORT,'append_only'); END;
"""


class ReturnedInvocations:
    """Independent external append-only custodian that calls the native producer.

    Unique pending invocation claims are committed before dispatch. Crashes,
    missing ACKs and unknowns strand those claims permanently; no reconstruction,
    replay, upsert, auto-provisioning or retain(caller_result) API exists.
    Filesystem/clock/power-loss/ACL independence needs actual operator qualification.
    """

    def __init__(self, path, packet_pin, target, candidate, clock):
        self.path, self.packet_pin = Path(path), packet_pin
        self.target, self.candidate, self.clock = target, candidate, clock
        self.last_time = -1.0

    def _guard(self, deadline):
        now = self.clock()
        _require(
            type(now) in (int, float)
            and math.isfinite(now)
            and type(deadline) in (int, float)
            and math.isfinite(deadline)
            and 0 <= now < deadline
            and now >= self.last_time,
            "native_custodian_deadline",
        )
        self.last_time = now
        return now

    def provision(self, deadline):
        now = self._guard(deadline)
        _require(self.path.is_absolute() and not self.path.is_symlink(), "native_custodian_path")
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(self.path, isolation_level=None, timeout=0)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.executescript(_DDL)
            db.execute(
                "INSERT INTO binding VALUES(?,?,?)", (self.packet_pin, self.target, self.candidate)
            )
            db.execute("INSERT INTO clock VALUES(1,?)", (now,))
        self._guard(deadline)

    @contextmanager
    def _transaction(self, deadline):
        now = self._guard(deadline)
        _require(
            self.path.is_absolute() and not self.path.is_symlink() and self.path.is_file(),
            "native_custodian_missing",
        )
        with closing(
            sqlite3.connect(
                self.path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=0
            )
        ) as db:
            try:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("BEGIN IMMEDIATE")
                _require(
                    db.execute("SELECT * FROM binding").fetchall()
                    == [(self.packet_pin, self.target, self.candidate)],
                    "native_custodian_binding",
                )
                watermark = db.execute("SELECT watermark FROM clock WHERE singleton=1").fetchall()
                _require(
                    len(watermark) == 1 and now >= watermark[0][0],
                    "native_custodian_clock_rollback",
                )
                yield db
                now = self._guard(deadline)
                db.execute("UPDATE clock SET watermark=? WHERE singleton=1", (now,))
                db.commit()
                self._guard(deadline)
            except BaseException:
                db.rollback()
                raise

    def invoke(self, controller, intent, reference, *, predecessor=None, previous=None):
        end = intent.window.dispatch_until
        self._guard(end)
        _require(
            type(controller) is NativeController
            and type(intent) is adapter.Intent
            and intent.target_id == self.target
            and intent.candidate == self.candidate
            and controller.binding.packet_sha2_256 == self.packet_pin
            and type(reference) is str
            and re.fullmatch(r"native:[A-Za-z0-9_.:-]{1,120}", reference),
            "native_invocation_binding",
        )
        controller.writer.guard(end)
        # A duplicate/unknown reference OR intent is refused before any producer call.
        with self._transaction(end) as db:
            db.execute(
                "INSERT INTO invocations VALUES(?,?,?,?)",
                (reference, intent.key, _encode(asdict(intent)), self.last_time),
            )
        result = (
            controller.execute(intent)
            if predecessor is None
            else controller.advance(predecessor, intent, previous, self)
        )
        self._guard(end)
        controller.writer.guard(end)
        _require(type(result) is adapter.Result, "native_returned_result_required")
        if result.status == "confirmed":
            _require(
                type(controller.evidence) is bytes and controller.evidence,
                "native_returned_evidence_missing",
            )
            _validate_returned(intent, result, controller.evidence, self.packet_pin)
            with self._transaction(end) as db:
                db.execute(
                    "INSERT INTO returned VALUES(?,?,?,?)",
                    (reference, _encode(asdict(result)), controller.evidence, self.last_time),
                )
            controller.writer.guard(end)
        return result

    def read(self, reference, deadline):
        with self._transaction(deadline) as db:
            row = db.execute(
                "SELECT i.intent,r.result,r.evidence FROM invocations i "
                "JOIN returned r USING(reference) WHERE i.reference=?",
                (reference,),
            ).fetchone()
        _require(row is not None, "native_returned_confirmation_missing")
        value = json.loads(row[0])
        value["window"] = adapter.Window(**value["window"])
        intent = adapter.Intent(**value)
        result = adapter.Result(**json.loads(row[1]))
        _validate_returned(intent, result, row[2], self.packet_pin)
        _require(
            intent.target_id == self.target
            and intent.candidate == self.candidate
            and result.confirmed_at is not None
            and result.confirmed_at <= self.last_time,
            "native_returned_binding",
        )
        return adapter.ConfirmedReceipt(reference, intent, result)


def _validate_returned(intent, result, raw, packet_pin):
    _require(
        type(raw) is bytes and 0 < len(raw) <= 4 * 1024 * 1024, "native_retained_evidence_bound"
    )
    evidence: dict[str, Any] = json.loads(raw)
    _require(
        type(evidence) is dict
        and set(evidence)
        == {
            "kind",
            "packetSha2_256",
            "target",
            "intent",
            "batch",
            "sourceManifest",
            "independentPrimaryReads",
            "finalJournalAcknowledgedAt",
        },
        "native_retained_evidence_shape",
    )
    _require(
        evidence["kind"] == "pmb1-native-returned-invocation-v1"
        and evidence["packetSha2_256"] == packet_pin
        and evidence["target"] == intent.target_id
        and evidence["intent"] == asdict(intent)
        and result.status == "confirmed"
        and result.reason == "one_row_and_independent_readback"
        and result.observed_generation == intent.next_generation
        and result.observed_state == intent.target
        and type(result.confirmed_at) in (int, float)
        and math.isfinite(result.confirmed_at)
        and intent.window.starts <= result.confirmed_at < intent.window.dispatch_until
        and evidence["finalJournalAcknowledgedAt"] == result.confirmed_at,
        "native_retained_confirmation_binding",
    )
    reads: list[dict[str, Any]] = evidence["independentPrimaryReads"]
    _require(type(reads) is list and len(reads) == 4, "native_retained_primary_reads")
    files = adapter.verify_source()
    files["manifest.json"] = _encode(evidence["sourceManifest"]).encode()
    batch: dict[str, Any] = evidence["batch"]
    _require(
        type(batch) is dict
        and batch.get("scope") == "NATIVE_RETURNED_HTTP_EVIDENCE"
        and batch.get("target") == intent.target_id
        and batch.get("packet") == packet_pin
        and batch.get("intent") == asdict(intent),
        "native_retained_batch_binding",
    )
    manifest: dict[str, Any] = batch["receipt"]
    _require(
        type(manifest) is dict
        and manifest.get("protocol") == positional.BOUNDARY
        and manifest.get("request") == positional.manifest(positional.build(intent))
        and manifest.get("exactChangeCountText") == "1"
        and type(manifest.get("responseBodySha2_256")) is str
        and re.fullmatch(r"[a-f0-9]{64}", manifest["responseBodySha2_256"]),
        "native_retained_batch_receipt",
    )
    ordinals = []
    for index, item in enumerate(reads):
        name = "readback.sql" if index % 2 == 0 else "schema.sql"
        _require(
            type(item) is dict and set(item) == {"receipt", "rows"}, "native_retained_read_shape"
        )
        receipt: dict[str, Any] = item["receipt"]
        _require(
            type(receipt) is dict
            and receipt.get("primary") is True
            and receipt.get("complete") is True
            and receipt.get("request") == _read_manifest(files[name].decode()),
            "native_retained_read_request",
        )
        _require(
            type(receipt.get("requestOrdinal")) is int
            and receipt["requestOrdinal"] >= 0
            and type(receipt.get("wireBytes")) is int
            and receipt["wireBytes"] > 0
            and type(receipt.get("responseBodySha2_256")) is str
            and re.fullmatch(r"[a-f0-9]{64}", receipt["responseBodySha2_256"]),
            "native_retained_read_receipt",
        )
        ordinals.append(receipt["requestOrdinal"])
        if index % 2 == 0:
            expected = (
                (intent.expected, "open" if intent.operation == "close" else "closed")
                if index == 0
                else (intent.next_generation, intent.target)
            )
            _require(
                adapter.validate_control(adapter.CompleteRows(item["rows"], True)) == expected,
                "native_retained_readback",
            )
        else:
            adapter.validate_schema(adapter.CompleteRows(item["rows"], True), files)
    _require(ordinals == sorted(set(ordinals)), "native_retained_independent_read_order")
