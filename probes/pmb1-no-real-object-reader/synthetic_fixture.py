"""Regenerate only the committed synthetic manifest compatibility fixture.

Run from repository root with pinned uv run --frozen --no-sync python
probes/pmb1-no-real-object-reader/synthetic_fixture.py. No provider or path reader.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.private_no_real_guards import build_guard_manifest, manifest_sha256

DDL = """CREATE TABLE payload (rowid TEXT, value, note TEXT,
 generated TEXT GENERATED ALWAYS AS (note || '😀') STORED);
CREATE TABLE composite (a INTEGER, b TEXT COLLATE NOCASE, value BLOB,
 PRIMARY KEY (a,b)) WITHOUT ROWID;
CREATE TABLE "__cf_kv" (key TEXT PRIMARY KEY, value);
CREATE TABLE bookkeeping (sequence INTEGER NOT NULL);
CREATE VIEW utf8_view AS SELECT note || 'é' FROM payload;
CREATE INDEX payload_note ON payload(note);
CREATE TRIGGER payload_history AFTER INSERT ON payload BEGIN
 INSERT INTO bookkeeping VALUES(1); END;"""


def main() -> None:
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.executescript(DDL)
        schema = [
            dict(r)
            for r in db.execute(
                "SELECT type,name,tbl_name,sql FROM main.sqlite_schema ORDER BY type,name,tbl_name"
            )
        ]
        tables = [
            dict(r)
            for r in db.execute(
                'SELECT schema,name,type,ncol,wr,"strict" FROM pragma_table_list '
                "WHERE schema='main' ORDER BY name"
            )
        ]
        columns = {
            r["name"]: [
                dict(c)
                for c in db.execute(
                    'SELECT cid,name,type,"notnull",dflt_value,pk,hidden '
                    "FROM pragma_table_xinfo(?) ORDER BY cid",
                    (r["name"],),
                )
            ]
            for r in schema
            if r["type"] == "table"
        }
        manifest = build_guard_manifest(schema, tables, columns)
    result = {"ddl": DDL, "manifest": manifest, "manifestSha256": manifest_sha256(manifest)}
    target = Path(__file__).with_name("synthetic-fixture.json")
    target.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
