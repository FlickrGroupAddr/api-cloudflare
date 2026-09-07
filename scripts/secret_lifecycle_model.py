"""Disposable SQLite model of credential activation, not the production database adapter."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Conflict(RuntimeError):
    """The expected revision or candidate state no longer permits this transition."""


class Lifecycle:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS grants (
                    name TEXT PRIMARY KEY, version TEXT NOT NULL, arn TEXT,
                    status TEXT NOT NULL CHECK(status IN ('planned','staged','active','inactive'))
                );
                CREATE TABLE IF NOT EXISTS link (
                    id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL,
                    active TEXT REFERENCES grants(name)
                );
                INSERT OR IGNORE INTO link VALUES(1,0,NULL);
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def plan(self, name: str, version: str) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO grants VALUES(?,?,NULL,'planned')", (name, version))

    def stage(self, name: str, version: str, arn: str) -> None:
        with self.connect() as db:
            changed = db.execute(
                "UPDATE grants SET arn=?,status='staged' "
                "WHERE name=? AND version=? AND status='planned'",
                (arn, name, version),
            ).rowcount
            if changed != 1:
                raise Conflict("Candidate is not planned.")

    def current(self) -> tuple[int, str | None]:
        with self.connect() as db:
            revision, active = db.execute("SELECT revision,active FROM link WHERE id=1").fetchone()
            return revision, active

    def activate(self, name: str, expected: int) -> int:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            revision, active = db.execute("SELECT revision,active FROM link WHERE id=1").fetchone()
            candidate = db.execute("SELECT status FROM grants WHERE name=?", (name,)).fetchone()
            if revision != expected or candidate != ("staged",):
                raise Conflict("Activation revision or candidate changed.")
            db.execute("UPDATE grants SET status='inactive' WHERE name=?", (active,))
            db.execute("UPDATE grants SET status='active' WHERE name=?", (name,))
            db.execute("UPDATE link SET revision=revision+1,active=? WHERE id=1", (name,))
            return revision + 1

    def disconnect(self, expected: int) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT revision FROM link WHERE id=1").fetchone() != (expected,):
                raise Conflict("Disconnect revision changed.")
            db.execute("UPDATE link SET revision=revision+1,active=NULL WHERE id=1")
            db.execute("UPDATE grants SET status='inactive'")

    def cleanup_allowed(self, name: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                "SELECT status FROM grants WHERE name=? AND name NOT IN "
                "(SELECT active FROM link WHERE active IS NOT NULL)",
                (name,),
            ).fetchone()
            return row == ("inactive",)
