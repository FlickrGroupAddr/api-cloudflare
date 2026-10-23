"""ADR0064 boundary tests use in-memory synthetic SQLite and fake transport only."""

from __future__ import annotations

import copy
import json
import sqlite3
import unittest
from unittest.mock import patch

from scripts import fixed_origin_preservation as preservation
from scripts import private_d1_snapshot_codec as codec
from scripts import private_d1_snapshot_profile as profile
from scripts import private_d1_snapshot_reader as reader
from scripts import private_no_real_guards as guards
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


def install_no_real_manifest(db, query):
    """Synthetic fixture installation only; production source never installs DDL."""
    schema, storage = profile.included_census(query(codec.SCHEMA_SQL), query(codec.TABLE_LIST_SQL))
    columns = {
        row["name"]: query(codec.columns_sql(row["name"]))
        for row in schema
        if row["type"] == "table"
    }
    guard = guards.build_guard_manifest(schema, storage, columns)
    for entry in guard["guards"]:
        db.execute(entry["sql"])
    manifest = manifest_for(query)
    manifest.update(
        profile=profile.NO_REAL_PROFILE,
        contractRevision=profile.NO_REAL_CONTRACT,
        guardManifest=guard,
        guardManifestSha256=guards.manifest_sha256(guard),
    )
    return manifest


class NoRealProfileTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID;
            INSERT INTO _cf_KV VALUES ('provider',1.25);
            CREATE TABLE flickr_write_gates(scope,scope_id,enabled,revision);
            INSERT INTO flickr_write_gates VALUES ('deployment','*',0,7),
                ('user','synthetic-user',0,11);
            CREATE TABLE history(value,generated AS (length(value)));
            CREATE INDEX history_index ON history(value);
            CREATE VIEW history_view AS SELECT value FROM history;
            CREATE TRIGGER history_keep BEFORE DELETE ON history
                BEGIN SELECT RAISE(ABORT,'keep'); END;
            CREATE TABLE d1_migrations(version INTEGER PRIMARY KEY,name TEXT);
            INSERT INTO d1_migrations VALUES (1,'synthetic');
            CREATE TABLE keyed(a,b,value,PRIMARY KEY(a,b)) WITHOUT ROWID;
            INSERT INTO keyed VALUES ('x',1,X'00'),('x',2,NULL);
        """)
        values = [None, -(2**63), 2**63 - 1, 2**53 - 1, 2**53, 2**53 + 1, "", "雪\0tail", b"\0\xff"]
        self.db.executemany("INSERT INTO history(value) VALUES (?)", [(v,) for v in values])
        self.db.execute("INSERT INTO history(value) VALUES ('same'),('same')")
        self.manifest = install_no_real_manifest(self.db, self.query)
        self.db.commit()
        self.calls = []

    def query(self, sql):
        cursor = self.db.execute(sql)
        return [dict(zip((c[0] for c in cursor.description), row, strict=True)) for row in cursor]

    def read(self, sql):
        self.calls.append(sql)
        if (
            sql not in (codec.SCHEMA_SQL, codec.TABLE_LIST_SQL, codec.ENCODING_SQL)
            and "_cf_KV" in sql
        ):
            raise RuntimeError("synthetic provider denial")
        return self.query(sql)

    def snapshot(self, query=None):
        return codec.collect_snapshot(
            query or self.read, page_size=2, profile_manifest=self.manifest
        )

    def test_complete_exact_typed_source_and_full_manifest_binding(self):
        actual = self.snapshot()
        local = preservation.capture_sqlite(
            self.db, run="a" * 32, database="synthetic-no-real", observed_at_ms=1
        )
        local["tables"].pop("_cf_KV")
        self.assertEqual(actual["schema"], local["schema"])
        self.assertEqual(actual["tables"], local["tables"])
        self.assertEqual(actual["profileBinding"]["profile"], profile.NO_REAL_PROFILE)
        self.assertEqual(actual["profileBinding"]["excludedContents"], profile.CONTENTS)
        self.assertIn("private_no_real_guards.py", actual["provenance"]["sourceSha256"])
        self.assertEqual(actual["provenance"]["queries"], self.calls)
        self.assertTrue(all(sql in self.calls for sql in profile.guard_queries(self.manifest)))
        self.assertFalse(any("_cf_KV" in sql for sql in self.calls))
        self.assertEqual(len(actual["tables"]["history"]["rows"]), 11)

    def test_independent_real_refusal_outside_quotas_even_when_guards_bypassed(self):
        for value in (1.25, 1.0, float("inf")):
            with self.subTest(value=value):
                self.db.execute("SAVEPOINT corruption")
                for entry in self.manifest["guardManifest"]["guards"]:
                    if entry["table"] == "history":
                        self.db.execute('DROP TRIGGER "' + entry["name"] + '"')
                self.db.execute("UPDATE history SET value=? WHERE rowid=1", (value,))
                # Restore the exact guard definitions after introducing bad state.
                for entry in self.manifest["guardManifest"]["guards"]:
                    if entry["table"] == "history":
                        self.db.execute(entry["sql"])
                with self.assertRaisesRegex(
                    preservation.Refused, "lossless_real_transport_unqualified"
                ):
                    self.snapshot()
                self.db.execute("ROLLBACK TO corruption")
                self.db.execute("RELEASE corruption")

    def test_schema_guard_column_or_exclusion_drift_refuses(self):
        for sql in (
            "CREATE TABLE unexpected(value)",
            "CREATE VIRTUAL TABLE search USING fts5(value)",
            "ALTER TABLE _cf_KV ADD COLUMN changed",
            'DROP TRIGGER "' + self.manifest["guardManifest"]["guards"][0]["name"] + '"',
        ):
            with self.subTest(sql=sql):
                self.db.execute("SAVEPOINT drift")
                self.db.execute(sql)
                with self.assertRaises(preservation.Refused):
                    self.snapshot()
                self.db.execute("ROLLBACK TO drift")
                self.db.execute("RELEASE drift")
        original = copy.deepcopy(self.manifest)
        for change in (
            lambda m: m.pop("guardManifestSha256"),
            lambda m: m.update(guardManifestSha256="a" * 64),
            lambda m: m["guardManifest"]["cells"]["history"].pop(),
            lambda m: m["guardManifest"]["columns"]["history"][0].update(hidden=1),
            lambda m: m["guardManifest"]["guards"][0].update(sql="SELECT 1"),
        ):
            self.manifest = copy.deepcopy(original)
            change(self.manifest)
            with self.assertRaises(preservation.Refused):
                self.snapshot()
        self.manifest = original

    def test_corrupt_cells_missing_pages_duplicate_identities_and_probes_refuse(self):
        for mutation in (
            lambda rows: rows.clear(),
            lambda rows: rows[0].update(c0_type="integer", c0_value=2**53 + 1),
            lambda rows: rows[0].update(c0_type="integer", c0_value="01"),
            lambda rows: rows[0].update(c0_type="integer", c0_value="-0"),
            lambda rows: rows[0].update(c0_type="integer", c0_value=str(2**63)),
            lambda rows: rows[0].update(c0_type="real", c0_value="1"),
            lambda rows: rows[0].update(c0_type="blob", c0_value="ff"),
            lambda rows: rows[0].update(c0_type="text", c0_value="FF"),
            lambda rows: rows[0].update(c0_type="null", c0_value=""),
            lambda rows: rows[1].update(row_identity=rows[0]["row_identity"]),
        ):

            def corrupt(sql, mutation=mutation):
                rows = self.read(sql)
                if 'FROM main."history"' in sql and rows and "c0_type" in rows[0]:
                    mutation(rows)
                return rows

            with self.subTest(mutation=mutation), self.assertRaises(preservation.Refused):
                self.snapshot(corrupt)

        def bad_probe(sql):
            return [{}] if sql.endswith(" LIMIT 0") else self.read(sql)

        with self.assertRaises(preservation.Refused):
            self.snapshot(bad_probe)

    def test_supplied_snapshot_cannot_smuggle_real_or_identity_drift(self):
        snapshot = self.snapshot()
        for change in (
            lambda s: s["tables"]["history"]["rows"][0].__setitem__(
                0, ["real", "3ff0000000000000"]
            ),
            lambda s: s["tables"]["history"]["rowids"].__setitem__(0, True),
            lambda s: s["tables"]["history"]["rowids"].__setitem__(
                0, s["tables"]["history"]["rowids"][1]
            ),
            lambda s: s["tables"]["keyed"]["rows"].append(
                copy.deepcopy(s["tables"]["keyed"]["rows"][0])
            ),
            lambda s: s["provenance"]["columns"]["history"][0].update(type="REAL"),
        ):
            changed = copy.deepcopy(snapshot)
            change(changed)
            with self.assertRaises(preservation.Refused):
                profile.validate_snapshot(changed, self.manifest)

    def test_equal_count_cell_and_hidden_rowid_changes_fail_preservation(self):
        baseline = self.snapshot()
        packet = preservation.synthetic_example()
        for envelope in packet[:3]:
            metadata = envelope["database"]
            envelope["database"] = {
                **{
                    key: metadata[key]
                    for key in ("mode", "run", "database", "observedAtMs", "consistency")
                },
                **copy.deepcopy(baseline),
            }
            envelope["profileBinding"] = copy.deepcopy(baseline["profileBinding"])
        packet[3]["profileBinding"] = copy.deepcopy(baseline["profileBinding"])
        receipt = preservation.validate_preservation(
            *packet, now_ms=1_000_700, profile_manifest=self.manifest
        )
        self.assertTrue(receipt["comparisonPassed"])
        self.assertFalse(receipt["deploymentAllowed"])
        for sql in (
            "UPDATE history SET value='changed' WHERE rowid=1",
            "UPDATE history SET rowid=100 WHERE rowid=1",
            "UPDATE d1_migrations SET name='changed'",
        ):
            self.db.execute("SAVEPOINT changed_fact")
            self.db.execute(sql)
            changed = copy.deepcopy(packet)
            changed[1]["database"].update(self.snapshot())
            with self.assertRaises(preservation.Refused):
                preservation.validate_preservation(
                    *changed, now_ms=1_000_700, profile_manifest=self.manifest
                )
            self.db.execute("ROLLBACK TO changed_fact")
            self.db.execute("RELEASE changed_fact")

    def test_external_table_validation_rejects_duplicate_and_null_primary_keys(self):
        snapshot = self.snapshot()
        table = codec.TablePlan("keyed", ("a", "b", "value"), None, (0, 1))
        for null_key in (False, True):
            changed = copy.deepcopy(snapshot)
            rows = changed["tables"]["keyed"]["rows"]
            if null_key:
                rows[0][0] = ["null", None]
                category = "invalid_without_rowid_key"
            else:
                rows[1][:2] = copy.deepcopy(rows[0][:2])
                category = "duplicate_without_rowid_key"
            rows.sort(key=codec._json)
            with self.assertRaisesRegex(preservation.Refused, category):
                profile.validate_no_real_table(table, changed["tables"]["keyed"])
            with self.assertRaisesRegex(preservation.Refused, category):
                profile.validate_snapshot(changed, self.manifest)

    def test_external_table_shapes_refuse_before_row_count_aggregation(self):
        snapshot = self.snapshot()
        for invalid in (None, [], {}, {"columns": [], "rows": None, "rowids": []}):
            changed = copy.deepcopy(snapshot)
            changed["tables"]["history"] = invalid
            with self.assertRaises(preservation.Refused):
                profile.validate_snapshot(changed, self.manifest)

    def test_unknown_hidden_and_ambiguous_identity_schemas_refuse(self):
        for ddl in (
            "CREATE TABLE inaccessible(rowid,_rowid_,oid)",
            "CREATE VIRTUAL TABLE search USING fts5(value)",
        ):
            self.db.execute("SAVEPOINT unsupported")
            self.db.execute(ddl)
            with self.assertRaises(preservation.Refused):
                install_no_real_manifest(self.db, self.query)
            self.db.execute("ROLLBACK TO unsupported")
            self.db.execute("RELEASE unsupported")

    def test_finite_bounds_and_unguardable_bookkeeping_remain_refusals(self):
        from unittest.mock import patch

        for name, bound in (("MAX_QUERIES", 3), ("MAX_BYTES", 1), ("MAX_ROWS", 1)):
            with patch.object(codec, name, bound), self.assertRaises(preservation.Refused):
                self.snapshot()
        self.db.execute("CREATE TABLE sequenced(id INTEGER PRIMARY KEY AUTOINCREMENT)")
        with self.assertRaisesRegex(preservation.Refused, "no_real_unguardable_table"):
            install_no_real_manifest(self.db, self.query)


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

    def test_no_real_finite_source_input_boundaries_and_cli_parser_parity(self):
        for selected, cap in (
            (None, reader.MAX_INPUT_BYTES),
            (profile.PROFILE, reader.MAX_INPUT_BYTES),
            (profile.NO_REAL_PROFILE, reader.NO_REAL_MAX_INPUT_BYTES),
        ):
            with self.subTest(profile=selected):
                value = {"padding": ""}
                if selected is not None:
                    value["profile"] = selected
                value["padding"] = "x" * (cap - len(reader.canonical(value)))
                self.assertEqual(len(reader.canonical(value)), cap)
                reader._bounded_inputs(value, {})
                path = self.root / "source-boundary.json"
                path.write_bytes(reader.canonical(value))
                self.assertEqual(reader._read_json(path), value)
                value["padding"] += "x"
                path.write_bytes(reader.canonical(value))
                with self.assertRaisesRegex(reader.SnapshotError, "snapshot_input_limit"):
                    reader._read_json(path)
                with self.assertRaisesRegex(reader.SnapshotError, "snapshot_input_limit"):
                    reader._bounded_inputs(value, {})
                # Consent shares the PLAN's finite profile-bound allowance.
                plan = {} if selected is None else {"profile": selected}
                with self.assertRaisesRegex(reader.SnapshotError, "snapshot_input_limit"):
                    reader._bounded_inputs(plan, value)
        self.credential.assert_not_called()
        self.transport.assert_not_called()

    def test_oversized_plan_or_consent_refuses_before_credentials_and_transport(self):
        for selected, cap in (
            (None, reader.MAX_INPUT_BYTES),
            (profile.NO_REAL_PROFILE, reader.NO_REAL_MAX_INPUT_BYTES),
        ):
            for consent_oversized in (False, True):
                plan, consent = self.inputs()
                if selected is not None:
                    plan["profile"] = selected
                target = consent if consent_oversized else plan
                target["padding"] = "x" * cap
                self.refuse(lambda plan=plan, consent=consent: self.collect(plan, consent))
                self.credential.assert_not_called()
                self.transport.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.journal.exists())

    def test_no_real_response_bound_is_explicit_finite_and_not_a_runtime_grant(self):
        self.db.execute("CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID")
        manifest = install_no_real_manifest(self.db, self.rows)
        self.queries.clear()

        def discovery(sql):
            self.queries.append(sql)
            return self.rows(sql)

        codec.collect_snapshot(discovery, page_size=2, profile_manifest=manifest)
        plan, _ = self.inputs()
        plan.update(
            profile=profile.NO_REAL_PROFILE,
            profileManifest=manifest,
            maxResponseBytes=reader.NO_REAL_MAX_RESPONSE_BYTES,
        )
        consent = self.consent(plan)
        consent.update(profile=plan["profile"], profileManifest=manifest)
        # Pure admission only. No credential/transport can be supplied by a limit.
        reader._prepare(plan, reader.digest(plan), consent, reader_tests.NOW)
        self.refuse(lambda: self.collect(plan, consent, transport=None))
        self.credential.assert_not_called()
        self.transport.assert_not_called()
        for field, too_large in (
            ("maxResponseBytes", reader.NO_REAL_MAX_RESPONSE_BYTES + 1),
            ("maxTotalBytes", reader.MAX_TOTAL_BYTES + 1),
        ):
            changed = {**plan, field: too_large}
            current = self.consent(changed)
            current.update(profile=plan["profile"], profileManifest=manifest)
            self.refuse(lambda changed=changed, current=current: self.collect(changed, current))
            self.credential.assert_not_called()
            self.transport.assert_not_called()
        legacy, _ = self.inputs()
        legacy["maxResponseBytes"] = reader.MAX_RESPONSE_BYTES + 1
        self.refuse(lambda: self.collect(legacy, self.consent(legacy)))
        self.credential.assert_not_called()
        self.transport.assert_not_called()

    def test_no_real_cli_bounded_parse_uses_same_collect_gate_without_token_read(self):
        # Source-parser parity at the expanded bound, before ordinary manifest
        # admission. Unknown fields still refuse inside collect before delivery.
        plan = {"profile": profile.NO_REAL_PROFILE, "padding": "x" * reader.MAX_INPUT_BYTES}
        consent = {"profile": profile.NO_REAL_PROFILE}
        plan_path, consent_path = self.root / "plan.json", self.root / "consent.json"
        plan_path.write_bytes(reader.canonical(plan))
        consent_path.write_bytes(reader.canonical(consent))
        with patch.object(reader, "collect", wraps=reader.collect) as collected:
            result = reader.main(
                [
                    "--plan",
                    str(plan_path),
                    "--consent",
                    str(consent_path),
                    "--expected-plan-sha256",
                    reader.digest(plan),
                    "--token-file",
                    str(self.root / "MUST-NOT-BE-READ"),
                    "--output",
                    str(self.output),
                    "--journal",
                    str(self.journal),
                ]
            )
        self.assertEqual(result, 1)
        self.assertEqual(collected.call_count, 1)
        self.assertEqual(collected.call_args.args[0], plan)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.journal.exists())

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

    def test_no_real_plan_consent_guard_queries_and_no_replay(self):
        self.db.execute("CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID")
        manifest = install_no_real_manifest(self.db, self.rows)
        self.queries.clear()

        def discovery(sql):
            self.queries.append(sql)
            return self.rows(sql)

        expected = codec.collect_snapshot(discovery, page_size=2, profile_manifest=manifest)
        plan, _ = self.inputs()
        plan.update(profile=profile.NO_REAL_PROFILE, profileManifest=manifest)
        consent = self.consent(plan)
        consent.update(profile=profile.NO_REAL_PROFILE, profileManifest=copy.deepcopy(manifest))
        summary = self.collect(plan, consent)
        self.assertEqual(json.loads(self.output.read_text())["snapshot"], expected)
        self.assertEqual(summary["profileBinding"]["profile"], profile.NO_REAL_PROFILE)
        delivered = self.credential.call_count
        self.refuse(lambda: self.collect(plan, consent))
        self.assertEqual(self.credential.call_count, delivered)

    def test_profile_identity_confusion_refuses_before_credential_or_transport(self):
        self.db.execute("CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID")
        manifest = install_no_real_manifest(self.db, self.rows)
        for selected in (profile.PROFILE, "unknown"):
            plan, _ = self.inputs()
            plan.update(profile=selected, profileManifest=manifest)
            consent = self.consent(plan)
            consent.update(profile=selected, profileManifest=copy.deepcopy(manifest))
            self.refuse(lambda plan=plan, consent=consent: self.collect(plan, consent))
            self.credential.assert_not_called()
            self.transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
