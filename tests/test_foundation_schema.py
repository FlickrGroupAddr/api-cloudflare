"""Exercise real SQLite commit constraints, migration upgrades and protected history."""

import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def statements(source: str) -> list[str]:
    result, pending = [], ""
    for line in source.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            result.append(pending.strip())
            pending = ""
    if pending.strip():
        raise ValueError("Incomplete SQL fixture")
    return result


def migrate(db: sqlite3.Connection, name: str) -> None:
    with db:
        for sql in statements((ROOT / "migrations" / name).read_text(encoding="utf-8")):
            db.execute(sql)


def seed(db: sqlite3.Connection) -> None:
    with db:
        db.execute("INSERT INTO fga_users VALUES ('owner')")
        db.execute(
            "INSERT INTO "
            "installations(installation_id,user_id,credential_class,state,revision,current_version_id)"
            " VALUES('i','owner','lrc_plugin','active',1,'v1')"
        )
        db.execute(
            (
                "INSERT INTO "
                "installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal)"
                " VALUES('v1','i',?,'current',1)"
            ),
            ("a" * 64,),
        )
        db.execute(
            "INSERT INTO "
            "submission_blocks(photo_id,group_id,first_reason,source_attempt_id) "
            "VALUES('p','g','delivery_uncertain','attempt')"
        )
        db.execute(
            "INSERT INTO "
            "audit_events(event_id,user_id,action,request_correlation_id,outcome,reason)"
            " VALUES('e','owner','fixture','request','succeeded','fixture')"
        )


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        migrate(self.db, "0001_foundation.sql")
        seed(self.db)

    def tearDown(self):
        self.db.close()

    def denied(self, sql, parameters=()):
        before = self.db.serialize()
        with self.assertRaises(sqlite3.IntegrityError), self.db:
            self.db.execute(sql, parameters)
        self.assertEqual(self.db.serialize(), before)

    def test_protected_history_mutation_and_replacement(self):
        for table, key, value in [
            ("submission_blocks", "photo_id", "p"),
            ("audit_events", "event_id", "e"),
        ]:
            for operation in [
                f"UPDATE {table} SET {key}={key}",
                f"DELETE FROM {table}",
                f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
                f"INSERT INTO {table} SELECT * FROM {table} WHERE 1 "
                f"ON CONFLICT DO UPDATE SET {key}='{value}'",
            ]:
                with self.subTest(sql=operation):
                    self.denied(operation)
        self.denied("DELETE FROM fga_users WHERE user_id='owner'")
        self.denied("DELETE FROM installations")
        self.denied("DELETE FROM installation_credential_versions")

    def test_missing_wrong_and_duplicate_current_rejected_at_commit(self):
        self.denied("UPDATE installations SET current_version_id='absent',revision=2")
        self.denied("UPDATE installation_credential_versions SET state='replaced'")
        self.denied(
            (
                "INSERT INTO "
                "installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal)"
                " VALUES('v2','i',?,'current',2)"
            ),
            ("b" * 64,),
        )
        self.denied(
            "INSERT INTO "
            "installations(installation_id,user_id,credential_class,state,revision,current_version_id)"
            " VALUES('other','owner','lrc_plugin','active',1,'v1')"
        )

    def test_pending_activation_and_revocation_are_atomic(self):
        with self.db:
            self.db.execute("UPDATE installations SET pending_version_id='v2',revision=2")
            self.db.execute(
                (
                    "INSERT INTO "
                    "installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us)"
                    " VALUES('v2','i',?,'pending_rotation',2,2000000000000000)"
                ),
                ("b" * 64,),
            )
        with self.db:
            self.db.execute(
                "UPDATE installation_credential_versions SET state='replaced' WHERE version_id='v1'"
            )
            self.db.execute(
                "UPDATE installation_credential_versions SET "
                "state='current',expires_at_us=NULL WHERE version_id='v2'"
            )
            self.db.execute(
                "UPDATE installations SET "
                "current_version_id='v2',pending_version_id=NULL,revision=3"
            )
        self.denied("UPDATE installations SET state='revoked',current_version_id=NULL,revision=4")
        with self.db:
            self.db.execute(
                "UPDATE installation_credential_versions SET state='revoked' WHERE version_id='v2'"
            )
            self.db.execute(
                "UPDATE installations SET state='revoked',current_version_id=NULL,revision=4"
            )
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM installation_credential_versions").fetchone(),
            (2,),
        )

    def test_identity_revision_ordinal_and_digest_guards(self):
        for sql in [
            "UPDATE installations SET user_id='another'",
            "UPDATE installations SET revision=0",
            "UPDATE installations SET current_version_id='v2'",
            "UPDATE installation_credential_versions SET ordinal=2",
            "UPDATE installation_credential_versions SET credential_digest='broken'",
            "UPDATE installation_credential_versions SET state='pending_rotation'",
            (
                "INSERT OR REPLACE INTO "
                "installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal)"
                " VALUES('v1','i','"
            )
            + "a" * 64
            + "','current',2)",
        ]:
            with self.subTest(sql=sql):
                self.denied(sql)

    def test_upgrade_and_transaction_failure_preserve_history(self):
        before = self.db.execute("SELECT * FROM audit_events").fetchone()
        migrate(self.db, "0002_audit_component.sql")
        self.assertEqual(
            self.db.execute("SELECT * FROM audit_events").fetchone(), (*before, "fga_api_backend")
        )
        with self.assertRaises(sqlite3.IntegrityError), self.db:
            self.db.execute(
                "INSERT INTO "
                "submission_blocks(photo_id,group_id,first_reason,source_attempt_id) "
                "VALUES('new','g','delivery_uncertain','attempt')"
            )
            self.db.execute("DELETE FROM audit_events")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM submission_blocks").fetchone(), (1,))
        self.denied("DELETE FROM audit_events")


if __name__ == "__main__":
    unittest.main()
