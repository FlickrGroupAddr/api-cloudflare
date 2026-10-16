"""Offline current-schema proofs; never executes a provider request."""

import io
import json
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import controlled_trial_observations as adapter

ROOT = Path(__file__).resolve().parents[1]


def plan():
    return {
        "schemaVersion": 1,
        "accountId": "a" * 32,
        "databaseId": "11111111-1111-4111-8111-111111111111",
        "fgaUserId": "private-owner",
        "photoId": "private-photo",
        "groupId": "private-group",
    }


def database():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    for migration in sorted((ROOT / "migrations").glob("*.sql")):
        db.executescript(migration.read_text(encoding="utf-8"))
    db.execute("INSERT INTO flickr_write_gates VALUES('deployment','*',0,7)")
    for n in range(103):
        user, partition, photo = f"user-{n:03}", f"partition-{n:03}", f"photo-{n:03}"
        db.execute("INSERT INTO fga_users VALUES(?)", [user])
        db.execute("INSERT INTO flickr_write_gates VALUES('user',?,0,1)", [user])
        db.execute(
            "INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,"
            "link_revision,verification_revision,source_kind) VALUES(?,?,?,'nsid',1,1,'upload')",
            [photo, user, photo],
        )
        db.execute(
            "INSERT INTO group_partitions(partition_id,user_id,group_id) VALUES(?,?,'group')",
            [partition, user],
        )
        for ordinal in (1, 2):
            intent = f"intent-{n:03}-{ordinal}"
            binding_photo = photo
            if ordinal == 2:
                binding_photo += "-second"
                db.execute(
                    "INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,"
                    "link_revision,verification_revision,source_kind) "
                    "VALUES(?,?,?,'nsid',1,1,'upload')",
                    [binding_photo, user, binding_photo],
                )
            db.execute(
                "INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,"
                "partition_id,enqueue_ordinal,state,next_attempt_not_before_us,created_request_id) "
                "VALUES(?,?,?,?,'group',?,?,'retrying',9000000000000000,'request')",
                [intent, binding_photo, user, binding_photo, partition, ordinal],
            )
            db.execute(
                "INSERT INTO submission_attempts(attempt_id,intent_id,ordinal,lease_id,"
                "lease_generation,deployment_revision,user_revision,link_revision) "
                "VALUES(?,?,1,'abandoned-lease',1,7,1,1)",
                [intent, intent],
            )
        db.execute(
            "UPDATE group_partitions SET lease_id='retained',lease_generation=1,"
            "lease_expires_at_us=1,lease_started_at_us=1,invocation_deadline_at_us=1 "
            "WHERE partition_id=?",
            [partition],
        )
    db.commit()
    return db


def local_query(db):
    def query(body):
        return [dict(row) for row in db.execute(body["sql"], body["params"]).fetchall()]

    return query


def seed_pair(db):
    db.execute("INSERT INTO fga_users VALUES('private-owner')")
    db.execute("INSERT INTO flickr_links VALUES('private-owner','owner',1,'linked')")
    db.execute(
        "INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,"
        "link_revision,verification_revision,source_kind) "
        "VALUES('binding','private-owner','private-photo','owner',1,1,'upload')"
    )
    db.execute(
        "INSERT INTO flickr_native_credentials VALUES("
        "'private-owner','private-generation',1,'owner','write',NULL)"
    )
    db.execute(
        "INSERT INTO flickr_connection_state(user_id,state,local_state,"
        "verified_permission,verified_at_us) "
        "VALUES('private-owner','linked','available','write',1)"
    )


class ObservationTests(unittest.TestCase):
    def test_complete_all_users_fifo_successors_delayed_and_abandoned_with_no_writes(self):
        with closing(database()) as db:
            before = db.total_changes
            db.execute("PRAGMA query_only=ON")
            result = adapter.collect(plan(), local_query(db))
            self.assertEqual(result["counts"]["users"], 103)
            self.assertEqual(result["counts"]["partitions"], 103)
            self.assertEqual(result["counts"]["intents"], 206)
            public = adapter.summary(result)
            self.assertEqual(public["activeFifoMembers"], 206)
            self.assertEqual(public["retainedLeases"], 103)
            self.assertEqual(public["unresolvedAttempts"], 206)
            self.assertEqual(db.total_changes, before)
            self.assertTrue(public["deploymentGateObservedPaused"])
            self.assertNotIn("private-", json.dumps(public))
            self.assertNotIn("photo-", json.dumps(public))
            self.assertNotIn("abandoned-lease", json.dumps(public))

    def test_truncation_refused_even_when_page_is_short(self):
        with closing(database()) as db:
            query = local_query(db)

            def truncated(body):
                rows = query(body)
                return rows[:1] if "AS cursor_key" in body["sql"] else rows

            with self.assertRaisesRegex(ValueError, "inventory_count_mismatch"):
                adapter.collect(plan(), truncated)

    def test_repeated_or_regressing_continuation_refused(self):
        with closing(database()) as db:
            query = local_query(db)

            def repeated(body):
                if "AS cursor_key" in body["sql"]:
                    body = {**body, "params": ["", body["params"][1]]}
                return query(body)

            with self.assertRaisesRegex(ValueError, "invalid_inventory_continuation"):
                adapter.collect(plan(), repeated)

    def test_same_count_changed_row_between_passes_refused(self):
        with closing(database()) as db:
            query = local_query(db)
            calls = 0

            def changed(body):
                nonlocal calls
                if body["sql"].startswith("SELECT (SELECT COUNT(*)"):
                    calls += 1
                    if calls == 3:
                        db.execute("UPDATE flickr_write_gates SET revision=revision+1")
                return query(body)

            with self.assertRaisesRegex(ValueError, "observation_changed"):
                adapter.collect(plan(), changed)

    def test_closed_operations_and_strict_plan(self):
        for operation in ("DELETE", "SELECT * FROM fga_users", "https://attacker.invalid"):
            with self.assertRaises(ValueError):
                adapter.statement(plan(), operation)
        for extra in ({"sql": "SELECT 1"}, {"destination": "https://attacker.invalid"}):
            with self.assertRaises(ValueError):
                adapter.validate({**plan(), **extra})
        with self.assertRaises(ValueError):
            adapter.validate({**plan(), "schemaVersion": True})

    def test_pair_parameters_bound_and_current_cache_never_authorizes(self):
        p = {**plan(), "photoId": "photo:123"}
        body = adapter.statement(p, "pair")
        self.assertNotIn(p["photoId"], body["sql"])
        self.assertEqual(body["params"], [p["fgaUserId"], p["photoId"], p["groupId"]])
        with closing(database()) as db:
            db.execute("INSERT INTO fga_users VALUES('private-owner')")
            db.execute("INSERT INTO flickr_links VALUES('private-owner','owner',1,'linked')")
            db.execute(
                "INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,"
                "link_revision,verification_revision,source_kind) "
                "VALUES('binding','private-owner','private-photo','owner',1,1,'upload')"
            )
            db.execute(
                "INSERT INTO flickr_native_credentials VALUES("
                "'private-owner','generation',1,'owner','write',NULL)"
            )
            db.execute(
                "INSERT INTO flickr_connection_state(user_id,state,local_state,"
                "verified_permission,verified_at_us) "
                "VALUES('private-owner','linked','available','write',1)"
            )
            db.execute(
                "INSERT INTO photo_membership_observations VALUES('binding',1,1,'generation',1,1)"
            )
            row = local_query(db)(adapter.statement(plan(), "pair"))[0]
            self.assertEqual(row["linked_bindings"], 1)
            self.assertEqual(row["current_membership_observations"], 1)
            db.execute("UPDATE photo_membership_observations SET generation='stale'")
            row = local_query(db)(adapter.statement(plan(), "pair"))[0]
            self.assertEqual(row["current_membership_observations"], 0)

    def test_page_budget_refused(self):
        with closing(database()) as db, patch.object(adapter, "MAX_PAGES", 1):
            with self.assertRaisesRegex(ValueError, "inventory_page_budget_exceeded"):
                adapter.collect(plan(), local_query(db))

    def test_pair_authority_metadata_retained_privately_without_membership_cache(self):
        with closing(database()) as db:
            seed_pair(db)
            private = adapter.collect(plan(), local_query(db))
            pair = private["pair"]
            binding = json.loads(pair["binding_metadata"])
            self.assertEqual(binding["binding_id"], "binding")
            self.assertEqual(binding["verification_revision"], "1")
            self.assertEqual(binding["link_revision"], "1")
            self.assertEqual(json.loads(pair["link_metadata"])["link_revision"], "1")
            self.assertEqual(
                json.loads(pair["native_metadata"])["active_generation"], "private-generation"
            )
            self.assertEqual(json.loads(pair["connection_metadata"])["state"], "linked")
            self.assertEqual(pair["current_membership_observations"], 0)
            public = json.dumps(adapter.summary(private))
            for private_value in ("binding_metadata", "private-generation", "private-owner"):
                self.assertNotIn(private_value, public)

    def test_same_count_pair_authority_drift_without_membership_cache_refused(self):
        mutations = (
            "UPDATE photo_bindings SET verification_revision=verification_revision+1 "
            "WHERE binding_id='binding'",
            "UPDATE flickr_native_credentials SET active_generation='private-replacement' "
            "WHERE user_id='private-owner'",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), closing(database()) as db:
                seed_pair(db)
                query = local_query(db)
                calls = 0
                first_counts = {}

                def changed(body, mutation=mutation, query=query, first_counts=first_counts):
                    nonlocal calls
                    if body["sql"] == adapter.PAIR_SQL:
                        calls += 1
                        if calls == 2:
                            db.execute(mutation)
                        row = query(body)[0]
                        counts = {
                            key: row[key]
                            for key in (
                                "photo_bindings",
                                "linked_bindings",
                                "blocks",
                                "intents",
                                "current_membership_observations",
                                "cached_membership_rows",
                            )
                        }
                        if calls == 1:
                            first_counts.update(counts)
                        else:
                            self.assertEqual(counts, first_counts)
                        return [row]
                    return query(body)

                with self.assertRaisesRegex(ValueError, "observation_changed"):
                    adapter.collect(plan(), changed)

    def test_cli_errors_never_print_private_details(self):
        with patch("sys.argv", ["observe", "--plan", "private-photo-secret-file"]):
            with redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(adapter.main(), 1)
            self.assertEqual(json.loads(stream.getvalue()), {"state": "observation_refused"})


if __name__ == "__main__":
    unittest.main()
