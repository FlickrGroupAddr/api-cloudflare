"""Finite public synthetic generator, closed writer, persisted read-only reopen."""

from __future__ import annotations

import hashlib
import sqlite3
import struct
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from full_state_oracle import Reference, read_reference, require

# Fixed source manifest: expected schema is not copied from a candidate capture.
DDL = (
    "CREATE TABLE cells(label TEXT UNIQUE, x)",
    "CREATE TABLE duplicates(value TEXT)",
    "CREATE TABLE keys(a TEXT,b INTEGER,value BLOB,PRIMARY KEY(b,a)) WITHOUT ROWID",
    "CREATE TABLE aliases(rowid TEXT, n INTEGER PRIMARY KEY, value TEXT)",
    "CREATE TABLE generated(n INTEGER, doubled INTEGER GENERATED ALWAYS AS (n*2) VIRTUAL)",
    "CREATE TABLE sequence_test(id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)",
    "CREATE TABLE d1_migrations(id INTEGER PRIMARY KEY, name TEXT)",
    "CREATE TABLE _cf_KV(key TEXT PRIMARY KEY, value BLOB)",
    "CREATE TABLE affinity_zeros(x REAL)",
    "CREATE INDEX cells_kind ON cells(label,x)",
    "CREATE VIEW cell_labels AS SELECT label FROM cells",
    "CREATE TRIGGER inert AFTER DELETE ON duplicates WHEN 0 BEGIN SELECT 1; END",
)
REAL_BITS = (
    0x0000000000000001,
    0x000FFFFFFFFFFFFF,
    0x0010000000000000,
    0x0010000000000001,
    0x3FEFFFFFFFFFFFFF,
    0x3FF0000000000000,
    0x3FF0000000000001,
    0x3FB999999999999A,
    0x7FEFFFFFFFFFFFFF,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Fixture:
    path: Path
    persisted_sha256: str
    generator_sha256: str
    oracle_sha256: str
    sqlite_version: str
    expected_row_count: int


def create_fixture(directory: Path) -> Fixture:
    """Create one exclusive fixed-name file, never read or overwrite an input DB."""
    path = directory / "synthetic-full-state.sqlite3"
    # O_EXCL through pathlib prevents silently adopting a preexisting database.
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(path)) as writer:
        for ddl in DDL:
            writer.execute(ddl)
        values = [
            ("null", None),
            ("int-min", -(2**63)),
            ("int-max", 2**63 - 1),
            ("int-over-js", 2**53 + 1),
            ("int-zero", 0),
            ("text-integer", "1"),
            ("text-empty", ""),
            ("text-nul", "before\0after\U0001f41f"),
            ("blob-empty", b""),
            ("blob-nul", b"\x00\xff\x80\x01"),
            ("real-positive-zero", 0.0),
            ("real-negative-zero-input", -0.0),
        ]
        for bits in REAL_BITS:
            for sign in (0, 1 << 63):
                raw = struct.pack(">Q", bits | sign)
                values.append((f"real-{bits | sign:016x}", struct.unpack(">d", raw)[0]))
        writer.executemany("INSERT INTO cells(label,x) VALUES(?,?)", values)
        writer.executemany(
            "INSERT INTO duplicates(oid,value) VALUES(?,?)",
            [(-(2**63), "same"), (2**63 - 1, "same"), (0, "different")],
        )
        writer.executemany(
            "INSERT INTO keys VALUES(?,?,?)", [("z", 2, b"\xff"), ("a\0b", 1, b"\0"), ("a", 2, b"")]
        )
        writer.execute("INSERT INTO aliases VALUES('declared',17,'hidden is n')")
        writer.execute("INSERT INTO generated(n) VALUES(7)")
        writer.execute("INSERT INTO sequence_test(value) VALUES('sequence')")
        writer.execute("INSERT INTO d1_migrations VALUES(1,'synthetic-only')")
        writer.execute("INSERT INTO _cf_KV VALUES('synthetic',x'00ff')")
        writer.executemany("INSERT INTO affinity_zeros VALUES(?)", [(0.0,), (-0.0,)])
        writer.commit()
    # Writer is closed before any reference connection is opened.
    source = Path(__file__)
    return Fixture(
        path,
        digest(path),
        digest(source),
        digest(source.with_name("full_state_oracle.py")),
        sqlite3.sqlite_version,
        len(values) + 14,
    )


def reopen_reference(fixture: Fixture) -> Reference:
    """Bind independently read expected state to exact reopened synthetic bytes."""
    require(digest(fixture.path) == fixture.persisted_sha256, "fixture_changed_before_reopen")
    source = Path(__file__)
    require(
        digest(source) == fixture.generator_sha256
        and digest(source.with_name("full_state_oracle.py")) == fixture.oracle_sha256,
        "fixture_source_changed",
    )
    with closing(sqlite3.connect(fixture.path.as_uri() + "?mode=ro", uri=True)) as reader:
        reference = read_reference(reader)
    require(digest(fixture.path) == fixture.persisted_sha256, "fixture_changed_during_read")
    require(
        sum(len(t.rows) for t in reference.tables.values()) == fixture.expected_row_count,
        "fixture_row_manifest",
    )
    schema = {(r[0], r[1]): r[3] for r in reference.schema}
    expected_schema = {}
    for ddl in DDL:
        words = ddl.split()
        kind = words[1].lower()
        name = words[2].split("(")[0]
        expected_schema[kind, name] = ddl
    expected_schema.update(
        {
            ("table", "sqlite_sequence"): "CREATE TABLE sqlite_sequence(name,seq)",
            ("index", "sqlite_autoindex_cells_1"): None,
            ("index", "sqlite_autoindex__cf_KV_1"): None,
        }
    )
    require(schema == expected_schema, "fixture_schema_manifest")
    cells = {row[1][0][1]: row[1][1] for row in reference.tables["cells"].rows}
    for bits in REAL_BITS:
        for sign in (0, 1 << 63):
            raw = struct.pack(">Q", bits | sign)
            require(cells[f"real-{bits | sign:016x}"] == ("real", raw), "fixture_real_bits")
    require(
        cells["int-min"] == ("integer", -(2**63))
        and cells["int-max"] == ("integer", 2**63 - 1)
        and cells["int-over-js"] == ("integer", 2**53 + 1),
        "fixture_int64",
    )
    require(
        cells["text-nul"] == ("text", "before\0after\U0001f41f")
        and cells["blob-nul"] == ("blob", b"\x00\xff\x80\x01"),
        "fixture_bytes",
    )
    # The no-affinity column preserves both signs in this local persisted read;
    # REAL affinity instead normalizes the inserted negative zero. Neither is a
    # managed-runtime claim. Verify both observed profiles after closing/reopen.
    require(
        cells["real-positive-zero"] == ("real", bytes(8))
        and cells["real-negative-zero-input"] == ("real", b"\x80" + bytes(7)),
        "fixture_local_zero_profile_changed",
    )
    require(
        all(row[1] == (("real", bytes(8)),) for row in reference.tables["affinity_zeros"].rows),
        "fixture_affinity_zero",
    )
    return reference
