"""Exercise the actual closed comparator with synthetic SQLite and receipt failures.

These tests establish an offline evidence contract only; they perform no provider,
native, credential, deployment or cleanup operations.
"""

import contextlib
import copy
import io
import sqlite3
import unittest
from typing import Any
from unittest.mock import patch

from scripts import fixed_origin_preservation as preservation

NOW = 1_000_700
RUN = "a" * 32
OTHER_RUN = "b" * 32


def leaves(value, prefix=()):
    """Yield field paths so every required boolean receipt gets a refusal case."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (*prefix, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, (*prefix, index))
    else:
        yield prefix, value


def replace(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.packet = preservation.synthetic_example()

    def validate(self, packet=None, now: Any = NOW):
        return preservation.validate_preservation(*(packet or self.packet), now_ms=now)

    def assert_refused(self, mutation, *, index=2):
        packet = copy.deepcopy(self.packet)
        mutation(packet[index])
        with self.assertRaises(preservation.Refused):
            self.validate(packet)

    def test_complete_synthetic_contract_retains_every_live_gate_closed(self):
        before = copy.deepcopy(self.packet)
        result = self.validate()
        self.assertTrue(result["comparisonPassed"])
        self.assertTrue(result["cleanupEvidenceComplete"])
        for key in (
            "currentProductionStateVerified",
            "providerRestorationVerified",
            "changedSecretSemanticsVerified",
            "authenticatedOrdinaryRoutesVerified",
            "deploymentAllowed",
        ):
            self.assertIs(result[key], False, key)
        self.assertTrue(result["missingSourceSeams"])
        self.assertEqual(self.packet, before)

    def test_any_failed_unknown_or_truthy_read_observation_refuses(self):
        for index in range(3):
            for path, value in leaves(self.packet[index]["ordinaryReads"]):
                if value is True:
                    for unknown in (False, None, "true", 1):
                        with self.subTest(envelope=index, path=path, value=unknown):
                            self.assert_refused(
                                lambda item, p=path, v=unknown: replace(
                                    item["ordinaryReads"], p, v
                                ),
                                index=index,
                            )
        for index in range(3):
            for key in ("ordinaryReads", "gates", "database", "continuity", "inventory"):
                with self.subTest(envelope=index, missing=key):
                    self.assert_refused(lambda item, k=key: item.pop(k), index=index)

    def test_any_failed_unknown_or_truthy_cleanup_observation_refuses(self):
        for path, value in leaves(self.packet[3]):
            if value is True:
                for unknown in (False, None, "true", 1):
                    with self.subTest(path=path, value=unknown):
                        self.assert_refused(
                            lambda item, p=path, v=unknown: replace(item, p, v),
                            index=3,
                        )
        for key in ("stop", "restore", "resources", "local"):
            for absent in (None, [], {}):
                with self.subTest(key=key, absent=absent):
                    self.assert_refused(lambda item, k=key, v=absent: item.update({k: v}), index=3)
            self.assert_refused(lambda item, k=key: item.pop(k), index=3)

    def test_real_labels_and_unknown_schema_fields_cannot_be_promoted(self):
        for index in range(4):
            for mode in ("hosted", "production", None, True):
                with self.subTest(index=index, mode=mode):
                    self.assert_refused(lambda item, v=mode: item.update(mode=v), index=index)
            self.assert_refused(lambda item: item.update(deploymentAllowed=True), index=index)
        self.assert_refused(lambda item: item["database"].update(mode="hosted"))

    def test_capture_digest_alone_cannot_replace_finite_inventory_or_data(self):
        for inventory in ({}, {"sha256": "a" * 64}, dict.fromkeys(preservation.FILES, None)):
            self.assert_refused(lambda item, v=inventory: item.update(inventory=v))
        for field in preservation.FILES:
            with self.subTest(missing_capture=field):
                self.assert_refused(lambda item, k=field: item["inventory"].pop(k))
        self.assert_refused(lambda item: item["inventory"].update(extra="a" * 64))
        for key in ("captureIndexSha256", "moduleSha256"):
            self.assert_refused(lambda item, k=key: item.update({k: "0" * 64}))
        self.assert_refused(lambda item: item.update(database={"sha256": "a" * 64}))
        self.assert_refused(lambda item: item["database"].update(tables={"rowCount": 3}))

    def test_paused_environment_flags_do_not_substitute_for_exact_durable_gates(self):
        for index in range(3):
            for gate_index in range(2):
                for field, bad in (
                    ("enabled", 1),
                    ("enabled", False),
                    ("enabled", None),
                    ("revision", 0),
                    ("revision", True),
                    ("revision", None),
                    ("scope", "unknown"),
                    ("scope_id", "synthetic-foreign-user"),
                ):
                    with self.subTest(index=index, gate=gate_index, field=field, bad=bad):
                        self.assert_refused(
                            lambda item, g=gate_index, f=field, v=bad: item["gates"][g].update(
                                {f: v}
                            ),
                            index=index,
                        )
            self.assert_refused(lambda item: item["gates"].pop(), index=index)
            self.assert_refused(
                lambda item: item["gates"].append(copy.deepcopy(item["gates"][0])), index=index
            )

    def test_self_consistent_stale_gate_revision_is_still_drift(self):
        packet = copy.deepcopy(self.packet)
        restored = packet[2]
        restored["gates"][0]["revision"] -= 1
        rows = restored["database"]["tables"]["flickr_write_gates"]["rows"]
        rows[0][3][1] -= 1
        with self.assertRaises(preservation.Refused):
            self.validate(packet)

    def test_census_schema_and_explicit_gates_must_agree(self):
        mutations = [
            lambda item: item["database"]["tables"].pop("synthetic_facts"),
            lambda item: item["database"]["schema"].pop(),
            lambda item: item["database"]["schema"].append(item["database"]["schema"][0]),
            lambda item: item["database"]["tables"]["synthetic_facts"].update(
                rows=[[["integer", 1]]]
            ),
            lambda item: item["database"]["tables"]["flickr_write_gates"]["rows"][0][3].__setitem__(
                1, 99
            ),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.assert_refused(mutation)

    def test_every_continuity_identity_and_background_drift_refuses(self):
        continuity = self.packet[2]["continuity"]
        for key in continuity:
            if key.endswith("Sha256"):
                with self.subTest(field=key):
                    self.assert_refused(
                        lambda item, k=key: item["continuity"].update({k: "0" * 64})
                    )
        for key in ("intake", "dispatch", "thumbnail"):
            self.assert_refused(
                lambda item, k=key: item["continuity"]["capabilities"].update({k: True})
            )
        self.assert_refused(
            lambda item: item["continuity"].update(d1Identity="synthetic-foreign-db")
        )
        self.assert_refused(
            lambda item: item["continuity"].update(weights={"synthetic-retained-version": 99})
        )
        self.assert_refused(
            lambda item: item["continuity"].update(retainedVersion="synthetic-new-target")
        )
        self.assert_refused(lambda item: item["database"].update(run=OTHER_RUN))
        self.assert_refused(lambda item: item["ordinaryReads"][0].update(run=OTHER_RUN))
        self.assert_refused(lambda item: item["ownedResources"][0].update(run=OTHER_RUN))

    def test_matching_run_cleanup_requires_exact_owned_identities_and_all_receipts(self):
        for section in ("resources", "local"):
            for index in range(len(self.packet[3][section])):
                for key, value in (("run", OTHER_RUN), ("identity", "synthetic-foreign-resource")):
                    with self.subTest(section=section, index=index, field=key):
                        self.assert_refused(
                            lambda item, s=section, i=index, k=key, v=value: item[s][i].update(
                                {k: v}
                            ),
                            index=3,
                        )
                self.assert_refused(lambda item, s=section, i=index: item[s].pop(i), index=3)
                for receipt_key in self.packet[3][section][index]:
                    self.assert_refused(
                        lambda item, s=section, i=index, k=receipt_key: item[s][i].pop(k),
                        index=3,
                    )
        self.assert_refused(
            lambda item: item["resources"][0].update(identity="synthetic-production-db"), index=3
        )

    def test_restore_target_force_latch_and_admission_revision_are_exact(self):
        for key, value in (
            ("target", "synthetic-alternate-version"),
            ("force", True),
            ("run", OTHER_RUN),
            ("latched", None),
        ):
            self.assert_refused(
                lambda item, k=key, v=value: item["restore"].update({k: v}), index=3
            )
        for revision in (1, 3, True, None):
            self.assert_refused(lambda item, v=revision: item["stop"].update(revision=v), index=3)
        for key in self.packet[3]["restore"]:
            self.assert_refused(lambda item, k=key: item["restore"].pop(k), index=3)

    def test_expired_stale_reordered_or_boolean_timestamps_refuse(self):
        for now in (True, None, 999_999, 1_060_401, 2_200_000):
            with self.subTest(now=now), self.assertRaises(preservation.Refused):
                self.validate(now=now)
        for index in range(3):
            self.assert_refused(lambda item: item.update(expiresAtMs=2_200_001), index=index)
        for section in ("stop", "restore"):
            self.assert_refused(lambda item, s=section: item[s].update(observedAtMs=NOW), index=3)
        self.assert_refused(lambda item: item.update(completedAtMs=NOW + 1), index=3)
        self.assert_refused(
            lambda item: item["resources"][0].update(observedAtMs=1_000_399), index=3
        )

    def test_claimed_real_cells_require_finite_canonical_roundtrip_in_every_snapshot(self):
        invalid = (
            "0x1.0p+999999",
            "-0x1.0p+999999",
            "0x1.0p+0",
            "0x1.0000000000000p+00",
            "0x1.0000000000000p-999999",
            "0X1.0000000000000P+0",
            "inf",
            "nan",
        )
        for claimed in invalid:
            packet = copy.deepcopy(self.packet)
            for envelope in packet[:3]:
                snapshot = envelope["database"]
                snapshot["tables"]["synthetic_facts"]["rows"][0][1] = ["real", claimed]
                with self.subTest(claimed=claimed, observed=envelope["observedAtMs"]):
                    with self.assertRaises(preservation.Refused):
                        preservation._database(
                            snapshot,
                            envelope["run"],
                            envelope["continuity"]["d1Identity"],
                            envelope["observedAtMs"],
                        )
            with self.subTest(claimed=claimed, all_envelopes=True):
                with self.assertRaises(preservation.Refused):
                    self.validate(packet)

    def test_canonical_finite_real_cells_include_subnormal_maximum_and_signed_zero(self):
        for value in (
            0.0,
            -0.0,
            1.0,
            -1.25,
            float.fromhex("0x0.0000000000001p-1022"),
            float.fromhex("0x1.fffffffffffffp+1023"),
        ):
            packet = copy.deepcopy(self.packet)
            for envelope in packet[:3]:
                snapshot = envelope["database"]
                snapshot["tables"]["synthetic_facts"]["rows"][0][1] = ["real", value.hex()]
                preservation._database(
                    snapshot,
                    envelope["run"],
                    envelope["continuity"]["d1Identity"],
                    envelope["observedAtMs"],
                )
            with self.subTest(canonical=value.hex()):
                self.assertTrue(self.validate(packet)["comparisonPassed"])

    def test_cli_remains_disabled(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = preservation.main()
        self.assertEqual(code, 2)
        self.assertIn("synthetic offline", output.getvalue())


class SQLiteCaptureTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript(
            "CREATE TABLE flickr_write_gates(scope TEXT,scope_id TEXT,"
            "enabled INTEGER,revision INTEGER);"
            "INSERT INTO flickr_write_gates VALUES('deployment','*',0,7),"
            "('user','synthetic-user',0,11);"
            "CREATE TABLE facts(id INTEGER PRIMARY KEY AUTOINCREMENT, datum);"
            "INSERT INTO facts(datum) VALUES(NULL),(1),(1.25),('one'),(X'0011');"
            "CREATE TABLE migration_identity(version TEXT);"
            "INSERT INTO migration_identity VALUES('v1');"
        )

    def capture(self, at=1_000_000):
        return preservation.capture_sqlite(
            self.db,
            run=RUN,
            database="synthetic-production-db",
            observed_at_ms=at,
        )

    def packet_with_real_snapshots(self):
        packet = preservation.synthetic_example()
        for envelope in packet[:3]:
            envelope["database"] = self.capture(envelope["observedAtMs"])
        return packet

    def test_actual_read_transaction_captures_typed_rows_schema_and_sequence_without_mutation(self):
        before = self.db.iterdump()
        before = list(before)
        self.db.row_factory = sqlite3.Row
        snapshot = self.capture()
        self.assertIs(self.db.row_factory, sqlite3.Row)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(list(self.db.iterdump()), before)
        self.assertEqual(
            set(snapshot["tables"]),
            {"facts", "flickr_write_gates", "migration_identity", "sqlite_sequence"},
        )
        tags = {row[1][0] for row in snapshot["tables"]["facts"]["rows"]}
        self.assertEqual(tags, {"null", "integer", "real", "text", "blob"})
        self.assertTrue(
            preservation.validate_preservation(*self.packet_with_real_snapshots(), now_ms=NOW)[
                "comparisonPassed"
            ]
        )

    def test_same_row_counts_cannot_hide_changed_fact_migration_sequence_or_schema(self):
        for statement in (
            "UPDATE facts SET datum='changed' WHERE id=4",
            "UPDATE migration_identity SET version='v2'",
            "UPDATE sqlite_sequence SET seq=99 WHERE name='facts'",
            "CREATE INDEX facts_index ON facts(datum)",
        ):
            with self.subTest(statement=statement):
                packet = self.packet_with_real_snapshots()
                self.db.execute("BEGIN")
                self.db.execute(statement)
                self.db.commit()
                packet[2]["database"] = self.capture(packet[2]["observedAtMs"])
                before = packet[0]["database"]["tables"]
                after = packet[2]["database"]["tables"]
                self.assertEqual(
                    {k: len(v["rows"]) for k, v in before.items()},
                    {k: len(v["rows"]) for k, v in after.items()},
                )
                with self.assertRaises(preservation.Refused):
                    preservation.validate_preservation(*packet, now_ms=NOW)

    def test_caller_transaction_and_failed_reader_never_commit(self):
        self.db.execute("UPDATE facts SET datum='uncommitted' WHERE id=1")
        with self.assertRaises(preservation.Refused):
            self.capture()
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.db.set_authorizer(lambda *_: sqlite3.SQLITE_DENY)
        with self.assertRaises(preservation.Refused):
            self.capture()
        self.assertFalse(self.db.in_transaction)
        self.db.set_authorizer(None)
        self.assertEqual(self.db.execute("SELECT datum FROM facts WHERE id=1").fetchone()[0], None)

    def test_bounded_reader_refuses_rows_tables_schema_and_bytes(self):
        for constant, limit in (
            ("MAX_ROWS", 1),
            ("MAX_TABLES", 1),
            ("MAX_SCHEMA", 1),
            ("MAX_BYTES", 1),
        ):
            with self.subTest(bound=constant), patch.object(preservation, constant, limit):
                with self.assertRaises(preservation.Refused):
                    self.capture()
                self.assertFalse(self.db.in_transaction)

    def test_hidden_rowid_changes_are_preservation_drift_even_with_identical_columns_and_rows(self):
        self.db.executescript(
            "CREATE TABLE hidden_facts(body TEXT);INSERT INTO hidden_facts VALUES('unchanged');"
        )
        packet = self.packet_with_real_snapshots()
        self.db.execute("UPDATE hidden_facts SET rowid=99")
        self.db.commit()
        packet[2]["database"] = self.capture(packet[2]["observedAtMs"])
        before = packet[0]["database"]["tables"]["hidden_facts"]
        after = packet[2]["database"]["tables"]["hidden_facts"]
        self.assertEqual(before["columns"], after["columns"])
        self.assertEqual(before["rows"], after["rows"])
        self.assertNotEqual(before["rowids"], after["rowids"])
        with self.assertRaises(preservation.Refused):
            preservation.validate_preservation(*packet, now_ms=NOW)

    def test_unshadowed_rowid_alias_is_captured_and_stays_aligned_with_sorted_rows(self):
        self.db.executescript(
            "CREATE TABLE shadowed(rowid TEXT,body TEXT);"
            "INSERT INTO shadowed VALUES('z','last'),('a','first');"
        )
        before = self.capture()["tables"]["shadowed"]
        self.assertEqual(before["rowids"], [2, 1])
        self.assertEqual([row[0][1] for row in before["rows"]], ["a", "z"])
        self.db.execute("UPDATE shadowed SET _rowid_=42 WHERE rowid='z'")
        self.db.commit()
        after = self.capture()["tables"]["shadowed"]
        self.assertEqual(after["rows"], before["rows"])
        self.assertEqual(after["rowids"], [2, 42])

    def test_without_rowid_table_has_explicit_absence_and_can_be_compared(self):
        self.db.executescript(
            "CREATE TABLE keyed(id TEXT PRIMARY KEY,body TEXT) WITHOUT ROWID;"
            "INSERT INTO keyed VALUES('synthetic-key','unchanged');"
        )
        snapshot = self.capture()
        self.assertIsNone(snapshot["tables"]["keyed"]["rowids"])
        result = preservation.validate_preservation(*self.packet_with_real_snapshots(), now_ms=NOW)
        self.assertTrue(result["comparisonPassed"])

    def test_all_rowid_aliases_shadowed_refuses_instead_of_guessing_identity(self):
        self.db.executescript(
            "CREATE TABLE inaccessible(rowid TEXT,_rowid_ TEXT,oid TEXT);"
            "INSERT INTO inaccessible VALUES('one','two','three');"
        )
        with self.assertRaises(preservation.Refused):
            self.capture()
        self.assertFalse(self.db.in_transaction)

    def test_nonfinite_real_values_refuse_before_returning_a_snapshot(self):
        for value in (float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.db.execute("UPDATE facts SET datum=? WHERE id=3", (value,))
                self.db.commit()
                with self.assertRaises(preservation.Refused) as caught:
                    self.capture()
                self.assertNotIn("inf", str(caught.exception))
                self.assertFalse(self.db.in_transaction)

    def test_denied_rollback_refuses_safely_and_restores_connection_configuration(self):
        def authorizer(action, operation, *_):
            if action == sqlite3.SQLITE_TRANSACTION and operation == "ROLLBACK":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        for row_limit in (preservation.MAX_ROWS, 1):
            with self.subTest(snapshot_read_succeeds=row_limit > 1):
                self.db.row_factory = sqlite3.Row
                self.db.text_factory = bytes
                previous_limit = self.db.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
                self.db.set_authorizer(authorizer)
                try:
                    with patch.object(preservation, "MAX_ROWS", row_limit):
                        with self.assertRaises(preservation.Refused) as caught:
                            self.capture()
                    self.assertNotIn("not authorized", str(caught.exception))
                    self.assertIs(self.db.row_factory, sqlite3.Row)
                    self.assertIs(self.db.text_factory, bytes)
                    self.assertEqual(self.db.getlimit(sqlite3.SQLITE_LIMIT_LENGTH), previous_limit)
                    self.assertTrue(self.db.in_transaction)
                finally:
                    self.db.set_authorizer(None)
                    self.db.rollback()
                    self.db.row_factory = None
                    self.db.text_factory = str

    def test_reader_refuses_foreign_scope_and_invalid_observation_time(self):
        for changes in (
            {"database": "production-id"},
            {"run": "not-a-run"},
            {"observed_at_ms": True},
            {"observed_at_ms": -1},
        ):
            args = {"run": RUN, "database": "synthetic-production-db", "observed_at_ms": 1_000_000}
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(preservation.Refused):
                preservation.capture_sqlite(self.db, **args)


if __name__ == "__main__":
    unittest.main()
