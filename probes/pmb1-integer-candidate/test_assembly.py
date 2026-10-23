"""Independent local schema/fault checks; no provider/private state adapter."""

import hashlib
import json
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from scripts import fixed_origin_preservation as preservation  # noqa: E402
from scripts import private_d1_snapshot_codec as codec  # noqa: E402
from tests import test_private_d1_snapshot_reader as reader_tests  # noqa: E402


def read(name):
    return (HERE / name).read_text(encoding="utf-8")


def quote(name):
    return '"' + name.replace('"', '""') + '"'


class AssemblyTests(unittest.TestCase):
    def database(self, domain):
        db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(db.close)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA recursive_triggers=ON")
        db.executescript(read(domain + "-schema.sql"))
        db.executescript(read(domain + "-guards.sql"))
        return db

    def test_independent_complete_census_and_every_post_affinity_cell_guard(self):
        for domain, count in [("d1", 65), ("object", 6)]:
            with self.subTest(domain=domain):
                db = self.database(domain)
                manifest = json.loads(read(domain + "-guard-manifest.json"))
                tables = [
                    row[0]
                    for row in db.execute(
                        "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
                    )
                ]
                self.assertEqual(len(tables), count)
                self.assertEqual(sorted(manifest["cells"]), tables)
                for table in tables:
                    columns = [r[1] for r in db.execute("PRAGMA table_xinfo(" + quote(table) + ")")]
                    cells = manifest["cells"][table]
                    self.assertTrue(set(columns).issubset(cells))
                    self.assertTrue(set(cells) - set(columns) <= {"rowid", "oid", "_rowid_"})
                    for event in ["insert", "update"]:
                        name = (
                            "pmb1_no_real_"
                            + hashlib.sha256(table.encode()).hexdigest()
                            + "_"
                            + event
                        )
                        sql = db.execute(
                            "SELECT sql FROM sqlite_schema WHERE name=?", (name,)
                        ).fetchone()[0]
                        self.assertIn(" AFTER " + event.upper() + " ON ", sql)
                        for cell in cells:
                            self.assertIn("typeof(NEW." + quote(cell) + ")='real'", sql)
                    # Direct SQL actual-type observation, independent of reader codec.
                    for cell in cells:
                        self.assertEqual(
                            db.execute(
                                "SELECT count(*) FROM "
                                + quote(table)
                                + " WHERE typeof("
                                + quote(cell)
                                + ")='real'"
                            ).fetchone()[0],
                            0,
                        )

    def test_new_integer_domain_and_complete_late_failure_rollback(self):
        db = self.database("d1")
        db.execute("UPDATE maintenance_control SET generation=2,state='open'")
        self.assertEqual(
            [r[1] for r in db.execute("PRAGMA table_xinfo(auth_source_buckets)")],
            ["source_key", "credit_us", "updated_at_us"],
        )
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("INSERT INTO fga_users VALUES('earlier')")
            db.execute("INSERT INTO quota_credit_clocks VALUES('clock',1.25)")
            self.fail("actual REAL must refuse")
        except sqlite3.IntegrityError:
            db.execute("ROLLBACK")
        self.assertEqual(db.execute("SELECT count(*) FROM fga_users").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT count(*) FROM quota_credit_clocks").fetchone()[0], 0)

    def test_actual_partition_domain_no_real_guard_and_mandatory_closed_control(self):
        db = self.database("object")
        db.execute("UPDATE maintenance_control SET generation=2,state='open'")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "pmb1_no_real"):
            db.execute(
                "INSERT INTO pmb1_partition_invocations(id,generation,entry,dispatch,state) "
                "VALUES('synthetic','2','fetch',1.25,'active')"
            )
        self.assertEqual(
            db.execute("SELECT count(*) FROM pmb1_partition_invocations").fetchone()[0], 0
        )
        db.execute("UPDATE maintenance_control SET generation=3,state='closed'")
        for statement in [
            "INSERT INTO pmb1_partition_binding VALUES(1,'synthetic')",
            "DELETE FROM maintenance_control",
        ]:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(statement)
        self.assertEqual(
            db.execute("SELECT generation,state FROM maintenance_control").fetchall(),
            [(3, "closed")],
        )

    def test_full_public_source_provenance_excludes_unrelated_recovery_work(self):
        manifest = json.loads(read("source-manifest.json"))
        root = HERE.parents[1]
        for name, expected in manifest["inputs"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected, name)
        self.assertFalse(any("historical_child_recovery" in name for name in manifest["inputs"]))
        self.assertEqual(
            len([name for name in manifest["inputs"] if name.startswith("migrations/")]), 26
        )

    def test_full_d1_selected_profile_through_actual_reader_prepare_and_transport(self):
        # Reuse the existing synthetic HTTP transport/protected-delivery harness,
        # replacing its miniature sample with the complete declared D1 domain.
        fixture = reader_tests.SnapshotReaderTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.db.close()
        fixture.db = self.database("d1")
        synthetic = json.loads(read("d1-profile-fixture.json"))
        fixture.db.execute(synthetic["providerMetadataDdl"])
        fixture.db.execute("INSERT INTO _cf_KV VALUES('synthetic-unread-provider-value',1.25)")
        manifest = synthetic["manifest"]
        fixture.queries.clear()

        def discovery(sql):
            fixture.queries.append(sql)
            return fixture.rows(sql)

        expected = codec.collect_snapshot(discovery, page_size=2, profile_manifest=manifest)
        local = preservation.capture_sqlite(
            fixture.db, run="a" * 32, database="synthetic-only", observed_at_ms=1
        )
        local["tables"].pop("_cf_KV")
        self.assertEqual(expected["tables"], local["tables"])
        self.assertEqual(expected["schema"], local["schema"])
        self.assertEqual(len(expected["tables"]), 65)
        plan, _ = fixture.inputs()
        plan.update(profile=manifest["profile"], profileManifest=manifest)
        plan["maxTotalBytes"] = 16 * 1024 * 1024
        plan["maxResponseBytes"] = reader_tests.reader.NO_REAL_MAX_RESPONSE_BYTES
        consent = fixture.consent(plan)
        consent.update(profile=manifest["profile"], profileManifest=manifest)
        summary = fixture.collect(plan, consent)
        self.assertTrue(summary["complete"])
        self.assertFalse(summary["productionQualified"])
        self.assertEqual(json.loads(fixture.output.read_text())["snapshot"], expected)
        self.assertFalse(any("_cf_KV" in sql for sql in fixture.queries))


if __name__ == "__main__":
    unittest.main()
