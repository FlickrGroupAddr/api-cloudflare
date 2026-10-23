"""External operator SQLite journal; never a Worker or a compared-store binding."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

import adapter


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def intent_from(value):
    value = dict(value)
    value["window"] = adapter.Window(**value["window"])
    return adapter.Intent(**value)


DDL = """
CREATE TABLE binding(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 target TEXT NOT NULL, packet TEXT NOT NULL, active TEXT,
 ordinal INTEGER NOT NULL DEFAULT 0, response_bytes INTEGER NOT NULL DEFAULT 0);
CREATE TABLE entries(key TEXT PRIMARY KEY, intent TEXT NOT NULL,
 phase TEXT NOT NULL, dispatched INTEGER NOT NULL DEFAULT 0,
 root TEXT NOT NULL, ordinal INTEGER NOT NULL, successor TEXT,
 confirmation TEXT UNIQUE, reads INTEGER NOT NULL DEFAULT 0,
 reconciliations INTEGER NOT NULL DEFAULT 0);
CREATE TABLE requests(ordinal INTEGER PRIMARY KEY, query TEXT NOT NULL,
 reserved INTEGER NOT NULL, received INTEGER);
"""


class SQLiteJournal:
    """Explicitly provisioned durable file, FULL synchronous, no busy retries.

    The operator must independently qualify filesystem durability, ACLs, stable
    monotonic clock domain, journal path exclusion from every compared store,
    custody and single retained path across restarts. This source does not infer
    any of those facts from a pathname. Missing state is never auto-provisioned.
    Construction performs no file access. Lost/late commit acknowledgments leave
    the committed reservation spent, including requests with unknown responses.
    """

    def __init__(self, path, target_id, packet_sha2_256, clock):
        self.path = Path(path)
        self.target_id, self.packet_sha2_256, self.clock = target_id, packet_sha2_256, clock

    def guard(self, deadline):
        now = self.clock()
        if (
            type(now) not in (int, float)
            or type(deadline) not in (int, float)
            or not math.isfinite(now)
            or not math.isfinite(deadline)
            or not 0 <= now < deadline
        ):
            raise adapter.Refusal("external_journal_deadline")

    def provision(self, deadline):
        """Explicit later private preparation, never constructor/default CLI."""
        self.guard(deadline)
        if not self.path.is_absolute() or self.path.is_symlink():
            raise adapter.Refusal("external_journal_path")
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        # Even failed initialization leaves a tombstone. No cleanup/retry here.
        with closing(sqlite3.connect(self.path, isolation_level=None, timeout=0)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.executescript(DDL)
            db.execute(
                "INSERT INTO binding(singleton,target,packet) VALUES(1,?,?)",
                (self.target_id, self.packet_sha2_256),
            )
        self.guard(deadline)

    @contextmanager
    def transaction(self, deadline):
        self.guard(deadline)
        if self.path.is_symlink() or not self.path.is_file():
            raise adapter.Refusal("external_journal_missing")
        # mode=rw prevents a renamed/missing journal being silently recreated.
        db = sqlite3.connect(
            self.path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None
        )
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM binding").fetchall()
            if (
                len(row) != 1
                or row[0]["target"] != self.target_id
                or row[0]["packet"] != self.packet_sha2_256
            ):
                raise adapter.Refusal("external_journal_binding")
            self.guard(deadline)
            yield db
            self.guard(deadline)
            db.commit()
            self.guard(deadline)
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _entry(self, db, key):
        row = db.execute("SELECT * FROM entries WHERE key=?", (key,)).fetchone()
        if row is None:
            raise adapter.Refusal("external_journal_unknown_key")
        return row

    def _valid_intent(self, intent):
        if (
            type(intent) is not adapter.Intent
            or intent.target_id != self.target_id
            or type(intent.window) is not adapter.Window
        ):
            raise adapter.Refusal("external_journal_intent")
        intent.window.validate()
        adapter.generation(intent.expected, increment=True)
        if (
            intent.operation not in ("close", "reopen")
            or type(intent.key) is not str
            or not 1 <= len(intent.key) <= 128
            or not intent.key.isascii()
            or type(intent.candidate) is not str
            or len(intent.candidate) != 64
            or any(character not in "0123456789abcdef" for character in intent.candidate)
            or type(intent.transition_limit) is not int
            or intent.transition_limit not in (1, 2, 3)
            or int(intent.expected) + intent.transition_limit > adapter.MAX_GENERATION
        ):
            raise adapter.Refusal("external_journal_intent")

    def latch(self, intent, deadline):
        self._valid_intent(intent)
        with self.transaction(deadline) as db:
            if db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]:
                return False
            db.execute(
                "INSERT INTO entries(key,intent,phase,root,ordinal) VALUES(?,?,?, ?,1)",
                (intent.key, encode(asdict(intent)), "latched", intent.key),
            )
            db.execute("UPDATE binding SET active=?", (intent.key,))
        return True

    def get(self, key, deadline):
        with self.transaction(deadline) as db:
            row = self._entry(db, key)
            result = adapter.JournalEntry(
                intent_from(json.loads(row["intent"])),
                row["phase"],
                bool(row["dispatched"]),
                row["root"],
                row["ordinal"],
                row["successor"],
                row["confirmation"],
            )
        return result

    def advance(self, predecessor, successor, receipt, deadline):
        self._valid_intent(successor)
        with self.transaction(deadline) as db:
            row = self._entry(db, predecessor.key)
            root = intent_from(json.loads(self._entry(db, row["root"])["intent"]))
            active = db.execute("SELECT active FROM binding").fetchone()[0]
            if (
                active != predecessor.key
                or row["intent"] != encode(asdict(predecessor))
                or row["phase"] != "confirmed"
                or row["dispatched"] != 1
                or row["successor"] is not None
                or row["ordinal"] >= root.transition_limit
                or successor.key == predecessor.key
                or successor.candidate != predecessor.candidate
                or successor.window != root.window
                or successor.transition_limit != root.transition_limit
                or successor.operation == predecessor.operation
                or successor.expected != predecessor.next_generation
                or type(receipt) is not adapter.ConfirmedReceipt
                or receipt.predecessor != predecessor
                or receipt.status != "CONFIRMED"
                or receipt.result.status != "confirmed"
                or receipt.result.reason != "one_row_and_independent_readback"
                or receipt.result.observed_generation != predecessor.next_generation
                or receipt.result.observed_state != predecessor.target
                or db.execute(
                    "SELECT 1 FROM entries WHERE key=? OR confirmation=?",
                    (successor.key, receipt.reference),
                ).fetchone()
            ):
                return False
            db.execute(
                "UPDATE entries SET successor=?,confirmation=? WHERE key=?",
                (successor.key, receipt.reference, predecessor.key),
            )
            db.execute(
                "INSERT INTO entries(key,intent,phase,root,ordinal) VALUES(?,?,?,?,?)",
                (
                    successor.key,
                    encode(asdict(successor)),
                    "latched",
                    row["root"],
                    row["ordinal"] + 1,
                ),
            )
            db.execute("UPDATE binding SET active=?", (successor.key,))
        return True

    def spend_read(self, key, deadline):
        with self.transaction(deadline) as db:
            row = self._entry(db, key)
            root = self._entry(db, row["root"])
            limit = intent_from(json.loads(root["intent"])).read_limit
            if root["reads"] >= limit:
                return False
            db.execute("UPDATE entries SET reads=reads+1 WHERE key=?", (row["root"],))
        return True

    def claim_dispatch(self, key, deadline):
        with self.transaction(deadline) as db:
            row = self._entry(db, key)
            if (
                row["phase"] != "latched"
                or row["dispatched"]
                or db.execute("SELECT active FROM binding").fetchone()[0] != key
            ):
                return False
            db.execute("UPDATE entries SET phase='dispatching',dispatched=1 WHERE key=?", (key,))
        return True

    def claim_reconcile(self, key, deadline):
        with self.transaction(deadline) as db:
            row = self._entry(db, key)
            root = self._entry(db, row["root"])
            if not row["dispatched"] or root["reconciliations"] >= 2:
                return False
            db.execute(
                "UPDATE entries SET reconciliations=reconciliations+1 WHERE key=?", (row["root"],)
            )
        return True

    def settle(self, key, phase, deadline):
        if phase not in ("refused", "unknown", "confirmed"):
            raise adapter.Refusal("external_journal_phase")
        with self.transaction(deadline) as db:
            row = self._entry(db, key)
            if row["successor"] is not None:
                raise adapter.Refusal("external_journal_consumed")
            if phase == "confirmed" and row["dispatched"] != 1:
                raise adapter.Refusal("external_journal_unclaimed_confirmation")
            db.execute("UPDATE entries SET phase=? WHERE key=?", (phase, key))

    def reserve_request(self, query, allowance, max_total, max_queries, deadline):
        """Persist query ordinal and worst-case wire allowance BEFORE dispatch."""
        if (
            type(query) is not str
            or not 1 <= len(query.encode()) <= 256 * 1024
            or type(allowance) is not int
            or not 1 <= allowance <= 512 * 1024
            or type(max_total) is not int
            or not 1 <= max_total <= 16 * 1024 * 1024
            or type(max_queries) is not int
            or not 1 <= max_queries <= 2048
        ):
            raise adapter.Refusal("native_d1_request_budget_shape")
        with self.transaction(deadline) as db:
            row = db.execute("SELECT * FROM binding").fetchone()
            ordinal = row["ordinal"]
            if ordinal >= max_queries or row["response_bytes"] + allowance > max_total:
                raise adapter.Refusal("native_d1_budget_exhausted")
            db.execute("INSERT INTO requests VALUES(?,?,?,NULL)", (ordinal, query, allowance))
            db.execute(
                "UPDATE binding SET ordinal=ordinal+1,response_bytes=response_bytes+?", (allowance,)
            )
        return ordinal

    def remaining(self, max_total, deadline):
        with self.transaction(deadline) as db:
            row = db.execute("SELECT ordinal,response_bytes FROM binding").fetchone()
            result = row["ordinal"], max_total - row["response_bytes"]
        return result

    def received(self, ordinal, count, deadline):
        with self.transaction(deadline) as db:
            row = db.execute("SELECT * FROM requests WHERE ordinal=?", (ordinal,)).fetchone()
            if (
                row is None
                or row["received"] is not None
                or type(count) is not int
                or not 0 <= count <= row["reserved"]
            ):
                raise adapter.Refusal("native_d1_accounting")
            db.execute("UPDATE requests SET received=? WHERE ordinal=?", (count, ordinal))
            db.execute(
                "UPDATE binding SET response_bytes=response_bytes-?", (row["reserved"] - count,)
            )
