"""Local schema and fake-provider checks; never contacts a provider."""

import io
import json
import os
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from scripts.controlled_trial_pause import (
    inspection_statement,
    receipt,
    request,
    statements,
    validate,
)

ROOT = Path(os.environ.get("FGA_LOCAL_PROOF_REPO", Path(__file__).resolve().parents[1]))


def plan():
    return {
        "schemaVersion": 1,
        "accountId": "a" * 32,
        "databaseId": "11111111-1111-4111-8111-111111111111",
        "operationId": "22222222-2222-4222-8222-222222222222",
        "fgaUserId": "owner",
        "expectedDeploymentRevision": 7,
        "expectedDeploymentEnabled": 1,
        "expectedUserRevision": 4,
        "expectedUserEnabled": 1,
    }


def database():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    for migration in sorted((ROOT / "migrations").glob("*.sql")):
        db.executescript(migration.read_text(encoding="utf-8"))
    db.execute("INSERT INTO fga_users VALUES('owner')")
    db.execute("INSERT INTO flickr_write_gates VALUES('deployment','*',1,7),('user','owner',1,4)")
    db.commit()
    return db


def batch(db, p):
    rows = []
    with db:
        for item in statements(p):
            rows = [dict(row) for row in db.execute(item["sql"], item["params"]).fetchall()]
    return rows


class PauseTests(unittest.TestCase):
    def test_both_scopes_pause_with_atomic_correlated_audit(self):
        with closing(database()) as db:
            rows = batch(db, plan())
            self.assertEqual(receipt(plan(), rows)["state"], "confirmed_paused")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM transaction_guards").fetchone()[0], 0)
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM flickr_write_gate_events WHERE reason='gate_paused'"
                ).fetchone()[0],
                2,
            )
            event = db.execute(
                "SELECT * FROM audit_events WHERE event_id=?", (plan()["operationId"],)
            ).fetchone()
            self.assertEqual(event["reason"], "controlled_trial_stop_d7_8_u4_5")

    def test_stale_either_scope_aborts_entire_pause(self):
        for key in ("expectedDeploymentRevision", "expectedUserRevision"):
            with self.subTest(key=key), closing(database()) as db:
                p = plan()
                p[key] += 1
                before = tuple(db.iterdump())
                with self.assertRaises(sqlite3.IntegrityError):
                    batch(db, p)
                self.assertEqual(tuple(db.iterdump()), before)

    def test_failed_audit_rolls_back_both_gates_and_trigger_events(self):
        with closing(database()) as db:
            db.executescript(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events "
                "BEGIN SELECT RAISE(ABORT,'synthetic'); END;"
            )
            before = tuple(db.iterdump())
            with self.assertRaises(sqlite3.IntegrityError):
                batch(db, plan())
            self.assertEqual(tuple(db.iterdump()), before)

    def test_mixed_and_already_paused_revisions_do_not_churn(self):
        for deployment, user in ((0, 0), (1, 0), (0, 1)):
            with self.subTest(deployment=deployment, user=user), closing(database()) as db:
                db.execute(
                    "UPDATE flickr_write_gates SET enabled=? WHERE scope='deployment'",
                    (deployment,),
                )
                db.execute("UPDATE flickr_write_gates SET enabled=? WHERE scope='user'", (user,))
                db.commit()
                p = plan()
                p.update(expectedDeploymentEnabled=deployment, expectedUserEnabled=user)
                rows = batch(db, p)
                self.assertEqual(receipt(p, rows)["state"], "confirmed_paused")
                self.assertEqual(
                    [r["revision"] for r in rows], [str(7 + deployment), str(4 + user)]
                )

    def test_lost_response_inspects_same_operation_without_replaying(self):
        with closing(database()) as db:
            p = plan()
            batch(db, p)  # Commit happened but pretend response was lost.
            before = tuple(db.iterdump())
            item = inspection_statement(p)
            rows = [dict(row) for row in db.execute(item["sql"], item["params"])]
            self.assertEqual(receipt(p, rows)["state"], "confirmed_paused")
            self.assertEqual(tuple(db.iterdump()), before)
            with self.assertRaises(sqlite3.IntegrityError):
                batch(db, p)  # Accidental replay cannot mutate successor state.
            self.assertEqual(tuple(db.iterdump()), before)

    def test_no_confirmation_for_missing_audit_or_later_revision(self):
        with closing(database()) as db:
            rows = batch(db, plan())
            rows[0]["operation_recorded"] = 0
            self.assertEqual(receipt(plan(), rows)["state"], "unconfirmed_inspect_required")
            rows[0]["operation_recorded"] = 1
            rows[0]["revision"] = "9"
            self.assertEqual(receipt(plan(), rows)["state"], "unconfirmed_inspect_required")

    def test_operator_plan_rejects_arbitrary_sql_url_bad_revision(self):
        for key, value in (
            ("sql", "DELETE FROM submission_blocks"),
            ("accountId", "https://untrusted.invalid"),
            ("expectedUserRevision", True),
            ("expectedUserEnabled", 2),
        ):
            p = plan()
            p[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(p)

    def test_provider_batch_shape_fixed_destination_bounded_response_no_retry(self):
        p = plan()

        class Response(io.BytesIO):
            status = 200

        class Opener:
            calls = 0

            def open(self, req, timeout):
                self.calls += 1
                self.req, self.timeout = req, timeout
                return Response(
                    json.dumps(
                        {
                            "success": True,
                            "result": [{"success": True, "results": []} for _ in range(5)],
                        }
                    ).encode()
                )

        fake = Opener()
        self.assertEqual(request(p, "synthetic", {"batch": statements(p)}, fake), [])
        self.assertEqual(fake.calls, 1)
        self.assertEqual(fake.timeout, 30)
        self.assertEqual(json.loads(fake.req.data), {"batch": statements(p)})
        self.assertEqual(
            fake.req.full_url,
            "https://api.cloudflare.com/client/v4/accounts/"
            + p["accountId"]
            + "/d1/database/"
            + p["databaseId"]
            + "/query",
        )

        class Lost(Opener):
            def open(self, req, timeout):
                self.calls += 1
                raise TimeoutError("synthetic unknown delivery")

        lost = Lost()
        with self.assertRaisesRegex(ValueError, "provider_result_unconfirmed"):
            request(p, "synthetic", {"batch": statements(p)}, lost)
        self.assertEqual(lost.calls, 1)


if __name__ == "__main__":
    unittest.main()
