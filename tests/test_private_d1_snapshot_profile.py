"""ADR0064 boundary tests use in-memory synthetic SQLite and fake transport only."""

from __future__ import annotations

import copy
import json
import sqlite3
import unittest

from scripts import fixed_origin_preservation as preservation
from scripts import private_d1_snapshot_codec as codec
from scripts import private_d1_snapshot_profile as profile
from tests import test_private_d1_snapshot_reader as reader_tests


def manifest_for(query):
    schema, storage = query(codec.SCHEMA_SQL), query(codec.TABLE_LIST_SQL)
    return {
        "profile": profile.PROFILE,
        "contractRevision": profile.CONTRACT,
        "providerDocumentation": profile.DOCUMENTATION,
        "schema": schema,
        "tableList": storage,
        "includedTables": sorted(
            row["name"]
            for row in schema
            if row["type"] == "table" and row["name"] != profile.EXCLUDED
        ),
        "excluded": {
            "schema": "main",
            "name": profile.EXCLUDED,
            "kind": "table",
            "contents": dict(profile.CONTENTS),
        },
        "dependencyReview": {
            "applicationDependsOnExcludedContents": False,
            "sourceSha256": {"synthetic-application.py": "a" * 64},
            "migrationsSha256": "b" * 64,
            "observableSchemaSha256": profile.sha256(schema),
        },
    }


class ApplicationProfileTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE _cf_KV(key TEXT PRIMARY KEY, value BLOB) WITHOUT ROWID;
            INSERT INTO _cf_KV VALUES ('synthetic-private-provider', X'0001');
            CREATE TABLE flickr_write_gates(scope,scope_id,enabled,revision);
            INSERT INTO flickr_write_gates VALUES ('deployment','*',0,7),
                ('user','synthetic-user',0,11);
            CREATE TABLE authentication(id INTEGER PRIMARY KEY AUTOINCREMENT, secret);
            INSERT INTO authentication(secret) VALUES ('synthetic-private-auth');
            CREATE TABLE history(value); INSERT INTO history VALUES ('permanent');
            CREATE TABLE suppression(photo,grp,PRIMARY KEY(photo,grp)) WITHOUT ROWID;
            INSERT INTO suppression VALUES ('synthetic-photo','synthetic-group');
            CREATE TRIGGER history_guard BEFORE DELETE ON history
                BEGIN SELECT RAISE(ABORT,'guard'); END;
            CREATE TABLE d1_migrations(value); INSERT INTO d1_migrations VALUES ('one');
            ANALYZE;
        """)
        self.calls = []
        self.manifest = manifest_for(self.query)
        self.calls.clear()

    def query(self, sql):
        self.calls.append(sql)
        cursor = self.db.execute(sql)
        return [
            dict(zip((column[0] for column in cursor.description), row, strict=True))
            for row in cursor
        ]

    def denied_query(self, sql):
        if (
            sql not in (codec.SCHEMA_SQL, codec.TABLE_LIST_SQL, codec.ENCODING_SQL)
            and "_cf_KV" in sql
        ):
            raise RuntimeError("synthetic reserved table denial")
        return self.query(sql)

    def snapshot(self):
        return codec.collect_snapshot(
            self.denied_query, page_size=2, profile_manifest=self.manifest
        )

    def packet(self):
        packet = preservation.synthetic_example()
        snapshot = self.snapshot()
        for envelope in packet[:3]:
            database = envelope["database"]
            envelope["database"] = {
                **{
                    key: database[key]
                    for key in ("mode", "run", "database", "observedAtMs", "consistency")
                },
                **copy.deepcopy(snapshot),
            }
            envelope["profileBinding"] = copy.deepcopy(snapshot["profileBinding"])
        packet[3]["profileBinding"] = copy.deepcopy(snapshot["profileBinding"])
        return packet

    def compare(self, packet):
        return preservation.validate_preservation(
            *packet, now_ms=1_000_700, profile_manifest=self.manifest
        )

    def test_exact_exclusion_preserves_census_and_no_contents_claim(self):
        snapshot = self.snapshot()
        self.assertNotIn(profile.EXCLUDED, snapshot["tables"])
        self.assertEqual(snapshot["tableList"], self.manifest["tableList"])
        self.assertEqual(snapshot["profileManifest"], self.manifest)
        self.assertIn(profile.EXCLUDED, [row[1] for row in snapshot["schema"]])
        for table in (
            "authentication",
            "history",
            "sqlite_sequence",
            "sqlite_stat1",
            "d1_migrations",
        ):
            self.assertIn(table, snapshot["tables"])
        self.assertFalse(any("_cf_KV" in sql for sql in self.calls))
        receipt = self.compare(self.packet())
        self.assertTrue(receipt["comparisonPassed"])
        self.assertFalse(receipt["wholeProviderContentsEqualityVerified"])
        self.assertEqual(receipt["profileBinding"]["excludedContents"], profile.CONTENTS)
        self.assertFalse(receipt["deploymentAllowed"])
        self.assertNotIn("synthetic-private", json.dumps(receipt))

    def test_strict_profile_denies_and_cannot_consume_scoped_receipt(self):
        with self.assertRaises(preservation.Refused):
            codec.collect_snapshot(self.denied_query)
        packet = self.packet()
        with self.assertRaises(preservation.Refused):
            preservation.validate_preservation(*packet, now_ms=1_000_700)
        with self.assertRaises(preservation.Refused):
            self.compare(preservation.synthetic_example())

    def test_provider_contents_are_explicitly_unobserved_not_manufactured_empty(self):
        before = self.snapshot()
        self.db.execute("UPDATE _cf_KV SET value=X'FFFF'")
        self.db.commit()
        self.assertEqual(before, self.snapshot())
        self.assertNotIn(profile.EXCLUDED, before["tables"])
        self.assertEqual(before["profileBinding"]["excludedContents"], profile.CONTENTS)

    def test_unknown_similar_names_and_changed_reserved_metadata_refuse_before_data(self):
        for sql in (
            "CREATE TABLE _cf_other(value)",
            "CREATE TABLE _cf_KV_copy(value)",
            "ALTER TABLE _cf_KV ADD COLUMN changed",
        ):
            with self.subTest(sql=sql):
                self.db.execute("SAVEPOINT mutation")
                self.db.execute(sql)
                self.calls.clear()
                with self.assertRaises(preservation.Refused):
                    self.snapshot()
                self.assertEqual(
                    self.calls, [codec.SCHEMA_SQL, codec.TABLE_LIST_SQL, codec.ENCODING_SQL]
                )
                self.db.execute("ROLLBACK TO mutation")
                self.db.execute("RELEASE mutation")

    def test_malformed_manifest_and_application_dependency_refuse(self):
        original = copy.deepcopy(self.manifest)
        for change in (
            lambda m: m.update(extra=True),
            lambda m: m.update(profile="strict"),
            lambda m: m.update(contractRevision="unknown"),
            lambda m: m.update(providerDocumentation="https://example.invalid/"),
            lambda m: m["excluded"].update(name="_cf_*"),
            lambda m: m["excluded"]["contents"].update(verified=True),
            lambda m: m["dependencyReview"].update(applicationDependsOnExcludedContents=True),
            lambda m: m["dependencyReview"].update(sourceSha256={}),
            lambda m: m["dependencyReview"].update(observableSchemaSha256="a" * 64),
            lambda m: m["includedTables"].remove("authentication"),
            lambda m: m["tableList"].append(copy.deepcopy(m["tableList"][0])),
        ):
            self.manifest = copy.deepcopy(original)
            change(self.manifest)
            with self.assertRaises(preservation.Refused):
                self.snapshot()
        self.db.execute("CREATE VIEW dependent AS SELECT key FROM _cf_KV")
        self.manifest = manifest_for(self.query)
        with self.assertRaisesRegex(preservation.Refused, "profile_application_dependency"):
            self.snapshot()

    def test_application_auth_history_sequence_guard_rowid_and_census_drift_refuse(self):
        for sql in (
            "UPDATE authentication SET secret='changed'",
            "UPDATE history SET value='lost'",
            "DELETE FROM suppression",
            "UPDATE sqlite_sequence SET seq=30",
            "UPDATE d1_migrations SET value='lost'",
            "UPDATE sqlite_stat1 SET stat='different'",
            "UPDATE history SET rowid=90",
            "DROP TRIGGER history_guard",
            "UPDATE flickr_write_gates SET revision=revision+1",
        ):
            with self.subTest(sql=sql):
                packet = self.packet()
                self.db.execute("SAVEPOINT mutation")
                self.db.execute(sql)
                try:
                    with self.assertRaises(preservation.Refused):
                        changed = self.snapshot()
                        packet[1]["database"].update(changed)
                        self.compare(packet)
                finally:
                    self.db.execute("ROLLBACK TO mutation")
                    self.db.execute("RELEASE mutation")

    def test_profile_provenance_envelope_cleanup_confusion_and_barriers_refuse(self):
        for change in (
            lambda p: p[1].pop("profileBinding"),
            lambda p: p[1]["database"]["profileBinding"].update(profile="strict"),
            lambda p: p[1]["database"]["profileManifest"]["excluded"].update(name="other"),
            lambda p: p[1]["database"]["provenance"]["queries"].reverse(),
            lambda p: p[1]["database"]["provenance"]["sourceSha256"].clear(),
            lambda p: p[1]["database"]["tableList"][0].update(ncol=200),
            lambda p: p[3].pop("profileBinding"),
            lambda p: p[3]["profileBinding"].update(profile="strict"),
            lambda p: p[3]["resources"][0].update(absentVerified=False),
            lambda p: p[1]["continuity"].update(backgroundQuiescenceSha256="b" * 64),
            lambda p: p[1]["ordinaryReads"][0].update(noMutation=False),
        ):
            packet = self.packet()
            change(packet)
            with self.assertRaises(preservation.Refused):
                self.compare(packet)

    def test_real_remains_unqualified(self):
        self.db.execute("UPDATE history SET value=1.25")
        self.db.commit()
        with self.assertRaisesRegex(preservation.Refused, "lossless_real_transport_unqualified"):
            self.snapshot()


class ApplicationProfileReaderTests(reader_tests.SnapshotReaderTests):
    """Inherited strict tests also guard against accidental compatibility defaults."""

    def test_explicit_profile_plan_consent_and_scoped_private_output(self):
        self.db.executescript("CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID;")
        manifest = manifest_for(self.rows)
        self.queries.clear()

        def discovery(sql):
            self.queries.append(sql)
            return self.rows(sql)

        expected = codec.collect_snapshot(discovery, page_size=2, profile_manifest=manifest)
        plan, _ = self.inputs()
        plan.update(profile=profile.PROFILE, profileManifest=manifest)
        consent = self.consent(plan)
        consent.update(profile=profile.PROFILE, profileManifest=copy.deepcopy(manifest))
        summary = self.collect(plan, consent)
        self.assertEqual(json.loads(self.output.read_text())["snapshot"], expected)
        self.assertEqual(summary["profileBinding"], expected["profileBinding"])
        self.assertFalse(summary["wholeProviderContentsEqualityVerified"])
        self.assertTrue(summary["complete"])
        delivered = self.credential.call_count
        self.refuse(lambda: self.collect(plan, consent))
        self.assertEqual(self.credential.call_count, delivered)

    def test_profile_cannot_be_selected_by_missing_or_mismatched_consent(self):
        self.db.executescript("CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID;")
        plan, consent = self.inputs()
        plan.update(profile=profile.PROFILE, profileManifest=manifest_for(self.rows))
        for current in (
            consent,
            {**self.consent(plan), "profile": "strict", "profileManifest": plan["profileManifest"]},
        ):
            self.refuse(lambda current=current: self.collect(plan, current))
            self.credential.assert_not_called()
            self.transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
