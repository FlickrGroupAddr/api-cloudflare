"""Durable SOURCE leaf bookkeeping. MIT License; copyright 2026 Terry Ott.

This broker is an external, local SQLite mechanism, never an actual grant or
qualification authority. The source-owned caller owns each effect and supplies
its exact measured receipt. Unknown native wire/effect costs cannot be admitted.
Counters describe declared SOURCE boundaries, not SQLite physical I/O or actual
native/provider accounting. No callback, transport, reset or successor exists.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from runner import OBJECT_PROFILE, PROFILE, RUN_LIMIT, Cost, Refusal


@dataclass(frozen=True)
class LeafIntent:
    ordinal: int
    identity: str
    source_path: str
    source_pin: str
    method: str
    resource: str
    request_digest: str
    cost: Cost | None


@dataclass(frozen=True)
class NativeLease:
    key: str
    context_digest: str
    source_pin: str
    profile: str
    object_profile: str
    leaves: tuple[LeafIntent, ...]


@dataclass(frozen=True)
class LeafReceipt:
    ordinal: int
    identity: str
    request_digest: str
    actual_cost: Cost
    evidence: bytes


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _text(value: object, maximum: int) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= maximum
        and value == value.strip()
        and all(32 <= ord(c) < 127 for c in value)
    )


def _cost(cost: Cost | None) -> Cost:
    if type(cost) is not Cost:
        raise Refusal("native_unknown_or_invalid_cost")
    cost.validate()
    categories = (
        cost.reader_queries
        + cost.receipt_reads
        + cost.metadata_reads
        + cost.authenticated_checks
        + cost.mutations
        + cost.creates
        + cost.deletes
    )
    if (
        not cost.within(RUN_LIMIT)
        or cost.requests > 1
        or cost.sql_statements > 8
        or cost.outbound_bytes > 65536
        or cost.inbound_bytes > 262144
        or cost.captures > 1
        or categories != cost.requests
        or (cost.reader_queries and cost.outbound_bytes > 32768)
    ):
        raise Refusal("native_leaf_budget")
    return cost


def _validate(lease: NativeLease, *, admission: bool = True) -> Cost:
    if (
        type(lease) is not NativeLease
        or not _text(lease.key, 128)
        or not _digest(lease.context_digest)
        or not _digest(lease.source_pin)
        or lease.profile != PROFILE
        or lease.object_profile != OBJECT_PROFILE
        or type(lease.leaves) is not tuple
        or not 1 <= len(lease.leaves) <= 2048
    ):
        raise Refusal("native_lease_binding")
    identities: set[str] = set()
    resource_actions: set[tuple[str, str]] = set()
    total = Cost()
    for ordinal, leaf in enumerate(lease.leaves):
        if (
            type(leaf) is not LeafIntent
            or type(leaf.ordinal) is not int
            or leaf.ordinal != ordinal
            or not _text(leaf.identity, 512)
            or leaf.identity in identities
            or not _text(leaf.source_path, 1024)
            or "\\" in leaf.source_path
            or leaf.source_path.startswith("/")
            or ":" in leaf.source_path
            or any(part in ("", ".", "..") for part in leaf.source_path.split("/"))
            or PurePosixPath(leaf.source_path).as_posix() != leaf.source_path
            or not _digest(leaf.source_pin)
            or not _text(leaf.method, 512)
            or not _text(leaf.resource, 2048)
            or not _digest(leaf.request_digest)
        ):
            raise Refusal("native_leaf_binding")
        identities.add(leaf.identity)
        if not admission:
            if leaf.cost is None:
                continue
            if type(leaf.cost) is not Cost:
                raise Refusal("native_unknown_or_invalid_cost")
            leaf.cost.validate()
            continue
        cost = _cost(leaf.cost)
        for action, count in (("create", cost.creates), ("delete", cost.deletes)):
            if count:
                pair = (leaf.resource, action)
                if pair in resource_actions:
                    raise Refusal("native_resource_latch")
                resource_actions.add(pair)
        total = total.plus(cost)
    if not total.within(RUN_LIMIT):
        raise Refusal("native_tree_budget")
    if admission:
        for leaf in lease.leaves:
            declared = _cost(leaf.cost)
            if declared.artifact_bytes < _retained_bytes(lease, leaf.ordinal, declared, total, 0):
                raise Refusal("native_unreserved_artifact_envelope")
    return total


def _retained_bytes(
    lease: NativeLease, ordinal: int, actual: Cost, total: Cost, evidence_length: int
) -> int:
    """Conservative full logical row envelopes, including all column values.

    Persisted JSON is encoded as its actual TEXT value inside another canonical
    envelope, so escaping and field names conservatively exceed raw TEXT bytes.
    BLOB bytes are charged separately, alongside a fixed-width length descriptor.
    Reserve the longest status and any permitted future unknown reason up front;
    later terminal downgrades must not require an unreserved metadata allocation.
    SQLite pages, indexes and transaction files remain unmeasured physical
    storage, separate from these native_attempt/native_leaves logical contents.
    """
    if (
        type(ordinal) is not int
        or not 0 <= ordinal < len(lease.leaves)
        or type(evidence_length) is not int
        or not 0 <= evidence_length <= RUN_LIMIT.artifact_bytes
    ):
        raise Refusal("native_retained_envelope_binding")
    leaf = lease.leaves[ordinal]
    leaf_row = {
        "ordinal": ordinal,
        "identity": leaf.identity,
        "intent": _json(dataclasses.asdict(leaf)),
        "status": "dispatching",  # Longest possible reserved/dispatching/known value.
        "actual": _json(dataclasses.asdict(actual)),
        "evidence_digest": "f" * 64,
        "evidence": {"maximum_byte_length": RUN_LIMIT.artifact_bytes},
    }
    size = len(_json(leaf_row).encode()) + evidence_length
    if ordinal == 0:
        attempt_row = {
            "singleton": 1,
            "lease_digest": lease_digest(lease),
            "lease": _json(dataclasses.asdict(lease)),
            "reserved": _json(dataclasses.asdict(total)),
            "status": "subtree_dispatching",  # Longest possible attempt status.
            "next_ordinal": len(lease.leaves),  # Largest possible numeric representation.
            # A printable ASCII reason is at most 128 characters. Backslash has
            # maximal JSON escaping among permitted characters (two bytes).
            "reason": "\\" * 128,
        }
        size += len(_json(attempt_row).encode())
    return size


def lease_digest(lease: NativeLease) -> str:
    """Exact binding only; a digest does not establish source truth or authority."""
    _validate(lease, admission=False)
    return hashlib.sha256(_json(dataclasses.asdict(lease)).encode()).hexdigest()


class SQLiteNativeBroker:
    """One permanent tree reservation, with before-effect ordered dispatch marks.

    Every write uses FULL synchronous and BEGIN IMMEDIATE. Only the instance
    acknowledging reserve_tree may dispatch; a reopened process cannot reacquire
    a reserved attempt. A lost acknowledgement is never permission to retry.
    Use a fresh absolute external fixture path, outside compared native stores.
    """

    def __init__(self, path: Path):
        if (
            not isinstance(path, Path)
            or not path.is_absolute()
            or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
        ):
            raise Refusal("native_external_journal_path")
        self.path = path
        self._owner: str | None = None
        self._lock = threading.Lock()
        existing = path.exists()
        with self._transaction() as db:
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if not tables:
                if existing:
                    raise Refusal("native_journal_schema_no_repair")
                db.execute(
                    "CREATE TABLE native_attempt ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                    "lease_digest TEXT NOT NULL, lease TEXT NOT NULL, reserved TEXT NOT NULL, "
                    "status TEXT NOT NULL, next_ordinal INTEGER NOT NULL, reason TEXT NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE native_leaves (ordinal INTEGER PRIMARY KEY, "
                    "identity TEXT UNIQUE NOT NULL, intent TEXT NOT NULL, status TEXT NOT NULL, "
                    "actual TEXT, evidence_digest TEXT, evidence BLOB)"
                )
                db.execute("PRAGMA user_version=1")
            elif sorted(row[0] for row in tables) != ["native_attempt", "native_leaves"]:
                raise Refusal("native_journal_schema")
            if db.execute("PRAGMA user_version").fetchone() != (1,):
                raise Refusal("native_journal_schema")
            # Fail closed on damaged or incompatible schemas; never repair them.
            db.execute(
                "SELECT singleton,lease_digest,lease,reserved,status,next_ordinal,reason "
                "FROM native_attempt LIMIT 1"
            )
            db.execute(
                "SELECT ordinal,identity,intent,status,actual,evidence_digest,evidence "
                "FROM native_leaves LIMIT 1"
            )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db: sqlite3.Connection | None = None
        try:
            db = sqlite3.connect(self.path, timeout=0, isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except sqlite3.Error as exc:
            self._owner = None
            if db is not None:
                db.rollback()
            raise Refusal("native_journal_unavailable_or_unknown") from exc
        except BaseException:
            self._owner = None
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    def reserve_tree(self, lease: NativeLease) -> None:
        """Validate and reserve the entire immutable tree in one transaction."""
        total = _validate(lease)
        digest = lease_digest(lease)
        with self._lock:
            with self._transaction() as db:
                if db.execute("SELECT 1 FROM native_attempt").fetchone() is not None:
                    raise Refusal("native_attempt_spent_no_replay")
                db.execute(
                    "INSERT INTO native_attempt VALUES(1,?,?,?,'reserved',0,'')",
                    (digest, _json(dataclasses.asdict(lease)), _json(dataclasses.asdict(total))),
                )
                db.executemany(
                    "INSERT INTO native_leaves VALUES(?,?,?,'reserved',NULL,NULL,NULL)",
                    (
                        (leaf.ordinal, leaf.identity, _json(dataclasses.asdict(leaf)))
                        for leaf in lease.leaves
                    ),
                )
            self._owner = digest

    def _owned(self, lease: NativeLease) -> str:
        digest = lease_digest(lease)
        if self._owner is None or digest != self._owner:
            raise Refusal("native_attempt_not_owned_no_replay")
        return digest

    @staticmethod
    def _spend(db: sqlite3.Connection, digest: str, reason: str) -> None:
        if not _text(reason, 128):
            raise Refusal("native_unknown_reason")
        db.execute(
            "UPDATE native_attempt SET status='unknown',reason=? "
            "WHERE singleton=1 AND lease_digest=?",
            (reason, digest),
        )

    @staticmethod
    def _match(lease: NativeLease, ordinal: int, identity: str, request_digest: str) -> bool:
        return (
            type(ordinal) is int
            and 0 <= ordinal < len(lease.leaves)
            and type(identity) is str
            and type(request_digest) is str
            and lease.leaves[ordinal].identity == identity
            and lease.leaves[ordinal].request_digest == request_digest
        )

    def begin(self, lease: NativeLease, ordinal: int, identity: str, request_digest: str) -> None:
        """Durably mark exactly the next leaf dispatching before its effect."""
        with self._lock:
            digest = self._owned(lease)
            refused = False
            with self._transaction() as db:
                state = db.execute(
                    "SELECT status,next_ordinal FROM native_attempt "
                    "WHERE singleton=1 AND lease_digest=?",
                    (digest,),
                ).fetchone()
                if state != ("reserved", ordinal) or not self._match(
                    lease, ordinal, identity, request_digest
                ):
                    self._spend(db, digest, "leaf_order_or_binding")
                    refused = True
                else:
                    changed = db.execute(
                        "UPDATE native_leaves SET status='dispatching' "
                        "WHERE ordinal=? AND identity=? AND status='reserved'",
                        (ordinal, identity),
                    ).rowcount
                    if changed != 1:
                        self._spend(db, digest, "leaf_dispatch_not_exact")
                        refused = True
                    else:
                        db.execute(
                            "UPDATE native_attempt SET status='dispatching' WHERE singleton=1"
                        )
            if refused:
                raise Refusal("native_leaf_order_or_binding")

    def finish(
        self,
        lease: NativeLease,
        ordinal: int,
        identity: str,
        request_digest: str,
        actual_cost: Cost,
        evidence: bytes,
    ) -> None:
        """Retain one exact known receipt; excess or malformed receipts spend all."""
        with self._lock:
            digest = self._owned(lease)
            refused = False
            valid = self._match(lease, ordinal, identity, request_digest)
            try:
                actual = _cost(actual_cost)
                valid = (
                    valid
                    and actual.within(_cost(lease.leaves[ordinal].cost))
                    and type(evidence) is bytes
                    and _retained_bytes(lease, ordinal, actual, _validate(lease), len(evidence))
                    <= actual.artifact_bytes
                )
            except Refusal, IndexError, TypeError:
                valid = False
            with self._transaction() as db:
                state = db.execute(
                    "SELECT status,next_ordinal FROM native_attempt "
                    "WHERE singleton=1 AND lease_digest=?",
                    (digest,),
                ).fetchone()
                if state != ("dispatching", ordinal) or not valid:
                    self._spend(db, digest, "receipt_unknown_or_overrun")
                    refused = True
                else:
                    changed = db.execute(
                        "UPDATE native_leaves SET status='known',actual=?,"
                        "evidence_digest=?,evidence=? "
                        "WHERE ordinal=? AND identity=? AND status='dispatching'",
                        (
                            _json(dataclasses.asdict(actual_cost)),
                            hashlib.sha256(evidence).hexdigest(),
                            evidence,
                            ordinal,
                            identity,
                        ),
                    ).rowcount
                    if changed != 1:
                        self._spend(db, digest, "receipt_not_exact")
                        refused = True
                    else:
                        status = "complete" if ordinal + 1 == len(lease.leaves) else "reserved"
                        db.execute(
                            "UPDATE native_attempt SET status=?,next_ordinal=? WHERE singleton=1",
                            (status, ordinal + 1),
                        )
            if refused:
                raise Refusal("native_receipt_unknown_or_overrun")

    @staticmethod
    def _interval(lease: NativeLease, first: int, through: int) -> bool:
        return (
            type(first) is int
            and type(through) is int
            and 0 <= first <= through < len(lease.leaves)
        )

    @staticmethod
    def _tree_state(
        db: sqlite3.Connection, lease: NativeLease, first: int, through: int, active: str
    ) -> bool:
        rows = db.execute(
            "SELECT ordinal,identity,intent,status FROM native_leaves ORDER BY ordinal"
        ).fetchall()
        return rows == [
            (
                leaf.ordinal,
                leaf.identity,
                _json(dataclasses.asdict(leaf)),
                "known"
                if leaf.ordinal < first
                else active
                if leaf.ordinal <= through
                else "reserved",
            )
            for leaf in lease.leaves
        ]

    def begin_subtree(
        self, lease: NativeLease, first: int, through: int, identity: str, request_digest: str
    ) -> None:
        """Mark every potentially executed leaf before one opaque source RPC.

        This is a conservative dispatch intent for the full inclusive interval,
        never an assertion that each leaf actually ran. No individual dispatch
        or receipt may intermix with a pending subtree.
        """
        with self._lock:
            digest = self._owned(lease)
            refused = False
            with self._transaction() as db:
                state = db.execute(
                    "SELECT status,next_ordinal FROM native_attempt "
                    "WHERE singleton=1 AND lease_digest=?",
                    (digest,),
                ).fetchone()
                valid = (
                    self._interval(lease, first, through)
                    and self._match(lease, first, identity, request_digest)
                    and state == ("reserved", first)
                    and self._tree_state(db, lease, first, through, "reserved")
                )
                if not valid:
                    self._spend(db, digest, "subtree_order_or_binding")
                    refused = True
                else:
                    changed = db.execute(
                        "UPDATE native_leaves SET status='dispatching' "
                        "WHERE ordinal BETWEEN ? AND ? AND status='reserved'",
                        (first, through),
                    ).rowcount
                    if changed != through - first + 1:
                        self._spend(db, digest, "subtree_dispatch_not_exact")
                        refused = True
                    else:
                        db.execute(
                            "UPDATE native_attempt SET status='subtree_dispatching' "
                            "WHERE singleton=1"
                        )
            if refused:
                raise Refusal("native_subtree_order_or_binding")

    def finish_subtree(
        self,
        lease: NativeLease,
        first: int,
        through: int,
        observations: tuple[LeafReceipt, ...],
    ) -> None:
        """Atomically settle exactly all ordered observations, or spend unknown.

        Missing observations are unknown; the broker never invents receipts for
        potentially executed leaves. All validation precedes any receipt writes.
        """
        with self._lock:
            digest = self._owned(lease)
            refused = False
            valid = (
                self._interval(lease, first, through)
                and type(observations) is tuple
                and len(observations) == through - first + 1
            )
            if valid:
                try:
                    total = _validate(lease)
                    for ordinal, receipt in enumerate(observations, first):
                        if type(receipt) is not LeafReceipt:
                            valid = False
                            break
                        actual = _cost(receipt.actual_cost)
                        if (
                            type(receipt.ordinal) is not int
                            or receipt.ordinal != ordinal
                            or not self._match(
                                lease, ordinal, receipt.identity, receipt.request_digest
                            )
                            or not actual.within(_cost(lease.leaves[ordinal].cost))
                            or type(receipt.evidence) is not bytes
                            or _retained_bytes(lease, ordinal, actual, total, len(receipt.evidence))
                            > actual.artifact_bytes
                        ):
                            valid = False
                            break
                except Refusal, IndexError, TypeError:
                    valid = False
            with self._transaction() as db:
                state = db.execute(
                    "SELECT status,next_ordinal FROM native_attempt "
                    "WHERE singleton=1 AND lease_digest=?",
                    (digest,),
                ).fetchone()
                if (
                    not valid
                    or state != ("subtree_dispatching", first)
                    or not self._tree_state(db, lease, first, through, "dispatching")
                ):
                    self._spend(db, digest, "subtree_receipt_unknown_or_overrun")
                    refused = True
                else:
                    # A savepoint also preserves all-or-nothing settlement on
                    # an unexpected row-count mismatch; no partial known set.
                    db.execute("SAVEPOINT settle_subtree")
                    for receipt in observations:
                        changed = db.execute(
                            "UPDATE native_leaves SET status='known',actual=?,"
                            "evidence_digest=?,evidence=? "
                            "WHERE ordinal=? AND identity=? AND status='dispatching'",
                            (
                                _json(dataclasses.asdict(receipt.actual_cost)),
                                hashlib.sha256(receipt.evidence).hexdigest(),
                                receipt.evidence,
                                receipt.ordinal,
                                receipt.identity,
                            ),
                        ).rowcount
                        if changed != 1:
                            db.execute("ROLLBACK TO settle_subtree")
                            self._spend(db, digest, "subtree_receipt_not_exact")
                            refused = True
                            break
                    db.execute("RELEASE settle_subtree")
                    if not refused:
                        status = "complete" if through + 1 == len(lease.leaves) else "reserved"
                        db.execute(
                            "UPDATE native_attempt SET status=?,next_ordinal=? WHERE singleton=1",
                            (status, through + 1),
                        )
            if refused:
                raise Refusal("native_subtree_receipt_unknown_or_overrun")

    def mark_unknown(self, lease: NativeLease, reason: str) -> None:
        """Conservatively downgrade, including a receipt whose ACK was lost."""
        if not _text(reason, 128):
            raise Refusal("native_unknown_reason")
        with self._lock:
            digest = self._owned(lease)
            with self._transaction() as db:
                self._spend(db, digest, "caller_reported_unknown")

    def observe(self) -> dict[str, object]:
        """Sanitized read-only evidence; never an authority or resume token."""
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0)
            try:
                db.execute("BEGIN")
                row = db.execute(
                    "SELECT status,next_ordinal,reserved FROM native_attempt WHERE singleton=1"
                ).fetchone()
                leaves = db.execute(
                    "SELECT ordinal,identity,status,actual,evidence_digest "
                    "FROM native_leaves ORDER BY ordinal"
                ).fetchall()
                return {
                    "status": row[0] if row else "unreserved",
                    "next_ordinal": row[1] if row else 0,
                    "reserved": json.loads(row[2]) if row else None,
                    "leaves": [
                        {
                            "ordinal": leaf[0],
                            "identity": leaf[1],
                            "status": leaf[2],
                            "actual": json.loads(leaf[3]) if leaf[3] else None,
                            "evidence_digest": leaf[4],
                        }
                        for leaf in leaves
                    ],
                }
            finally:
                db.close()
        except (sqlite3.Error, ValueError) as exc:
            raise Refusal("native_observation_unavailable") from exc

    def close(self) -> None:
        """Relinquish this instance; durable reservations are never released."""
        with self._lock:
            self._owner = None
