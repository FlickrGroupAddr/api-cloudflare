"""Native SOURCE composition/full65 test; invented authority, blocked socket/DNS.

Returned fixtures and a SQLite oracle establish no actual native qualification.
"""

import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import binding
import test_binding as fixtures
import test_native_sender as sender_fixtures

custody = binding.native_custody


class NativeFull65Tests(unittest.TestCase):
    def setUp(self):
        self.helper = sender_fixtures.NativeSenderTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.addCleanup(self.helper.tearDown)

    def test_native_close_custody_and_full65_share_one_unchanged_allocation(self):
        f = self.helper.fixture
        source_pins = binding.source_pins()
        f.db.execute(fixtures.FIXED["reopen.sql"].decode(), {"expected_generation": "1"})
        f.db.execute("INSERT INTO fga_users(rowid,user_id) VALUES(?,?)", (-(2**63), "min-π雪"))
        f.db.execute("INSERT INTO fga_users(rowid,user_id) VALUES(?,?)", (2**63 - 1, "max-🦋"))
        intent = f.intent(operation="close", expected="2", limit=1)
        statements = []
        # Independent MODEL connection: no expected rows come from sender output.
        with closing(sqlite3.connect(":memory:", isolation_level=None)) as oracle_db:
            f.db.backup(oracle_db)
            oracle_db.execute(fixtures.FIXED["close.sql"].decode(), {"expected_generation": "2"})

            def oracle(sql):
                statements.append(sql)
                cursor = oracle_db.execute(sql)
                return [
                    dict(zip([column[0] for column in cursor.description], row, strict=True))
                    for row in cursor.fetchall()
                ]

            expected = binding.collect_snapshot(
                oracle, page_size=2, profile_manifest=f.fixture["manifest"]
            )
        original_plan = f.plan

        def full_plan(queries):
            # Finalize both inventories BEFORE the single journal provision and
            # packet/admission binding. No activated allocation is extended.
            queries.extend(f.query("snapshot", sql) for sql in statements)
            record = f.packet["independentEvidence"]["allocation"]
            allocation_path = Path(record["path"])
            allocation = json.loads(allocation_path.read_bytes())
            allocation["requests"].extend(
                {
                    "protocol": "independent_primary_read",
                    "statementCount": 1,
                    "requestBodySha2_256": binding.sha2_256(
                        binding.canonical({"sql": sql, "params": []})
                    ),
                    "statements": [{"sql": sql, "params": []}],
                }
                for sql in statements
            )
            allocation["limits"].update(requests=len(queries), statements=len(queries) + 1)
            allocation_path.write_bytes(binding.canonical(allocation))
            record["sha2_256"] = binding.sha2_256(allocation_path.read_bytes())
            return original_plan(queries)

        with (
            patch.object(f, "intent", return_value=intent),
            patch.object(f, "plan", side_effect=full_plan),
        ):
            sender, journal, planned, admission, delivery = self.helper.plan()
        core = sender.core
        self.assertIs(type(core), binding.NativePositionalBinding)
        self.assertIs(core.sender, sender)
        self.assertEqual(planned, intent)
        packet_before = core.packet_path.read_bytes()
        allocation_path = Path(f.packet["independentEvidence"]["allocation"]["path"])
        allocation_before = allocation_path.read_bytes()
        core.activate(delivery, admission=admission)
        self.assertEqual(
            sender.allocation["limits"],
            {
                "requests": len(statements) + 5,
                "statements": len(statements) + 6,
                "requestBytes": 1024 * 1024,
                "responseBytes": 16 * 1024 * 1024,
            },
        )
        self.assertEqual(journal.remaining(16 * 1024 * 1024, 100), (0, 16 * 1024 * 1024))
        retained = custody.ReturnedInvocations(
            f.directory / "native-full65-returned.sqlite",
            core.packet_sha2_256,
            intent.target_id,
            intent.candidate,
            core.clock,
        )
        retained.provision(100)
        response_wire_bytes = []

        def transport(*args, **kwargs):
            response = f.batch_transport(*args, **kwargs)
            response_wire_bytes.append(response.wire_bytes)
            return response

        with fixtures.patched_transport(side_effect=transport) as wire:
            controller = custody.NativeController(core.sender)
            result = retained.invoke(controller, intent, "native:full65-source-only")
            self.assertEqual(result.status, "confirmed")
            self.assertEqual(wire.call_count, 5)
            self.assertEqual(journal.remaining(16 * 1024 * 1024, 100)[0], 5)
            actual = binding.CompleteReader(core).collect(
                f.profile_path, f.profile_pin, 100, page_size=2
            )
            self.assertEqual(actual, expected)
            self.assertEqual(len(actual["tables"]), 65)
            self.assertEqual(sorted(actual["tables"]["fga_users"]["rowids"]), [-(2**63), 2**63 - 1])
            self.assertTrue(any(row[1] == "_cf_KV" for row in actual["schema"]))
            self.assertTrue(any(row["name"] == "_cf_KV" for row in actual["tableList"]))
            self.assertTrue(any(row[0] == "trigger" for row in actual["schema"]))
            restart = custody.ReturnedInvocations(
                retained.path,
                core.packet_sha2_256,
                intent.target_id,
                intent.candidate,
                core.clock,
            )
            self.assertEqual(
                restart.read("native:full65-source-only", 100),
                binding.adapter.ConfirmedReceipt("native:full65-source-only", intent, result),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                restart.invoke(controller, intent, "native:full65-source-only")
            self.assertEqual(controller.execute(intent).status, "refused")
            with self.assertRaises(binding.adapter.Refusal):
                core.query("snapshot", statements[0], [], 100)
            self.assertEqual(wire.call_count, len(statements) + 5)
        with closing(sqlite3.connect(journal.path)) as db:
            request_count, received, reserved, unacknowledged = db.execute(
                "SELECT COUNT(*),SUM(received),SUM(reserved),SUM(received IS NULL) FROM requests"
            ).fetchone()
            statement_count, request_bytes = db.execute(
                "SELECT SUM(statements),SUM(request_bytes) FROM statement_allocations"
            ).fetchone()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batch_dispatches").fetchone()[0], 1)
            self.assertEqual(
                db.execute("SELECT ordinal,response_bytes FROM binding").fetchone(),
                (request_count, received),
            )
        self.assertEqual(request_count, len(statements) + 5)
        self.assertEqual(statement_count, request_count + 1)
        self.assertLessEqual(statement_count, 2048)
        self.assertEqual(request_bytes, sum(len(request.wire) for request in f.network_calls))
        self.assertEqual(received, sum(response_wire_bytes))
        self.assertEqual(unacknowledged, 0)
        self.assertEqual(reserved, request_count * f.packet["maxResponseBytes"])
        self.assertGreater(reserved, 16 * 1024 * 1024)
        self.assertLess(request_bytes, 1024 * 1024)
        self.assertLess(received, 16 * 1024 * 1024)
        self.assertEqual(
            journal.remaining(16 * 1024 * 1024, 100), (request_count, 16 * 1024 * 1024 - received)
        )
        self.assertEqual(journal.get(intent.key, 100).phase, "confirmed")
        self.assertEqual(core.packet_path.read_bytes(), packet_before)
        self.assertEqual(allocation_path.read_bytes(), allocation_before)
        self.assertEqual(binding.source_pins(), source_pins)
        self.assertEqual(f.socket_blocker.call_count, 0)
        self.assertEqual(f.dns_blocker.call_count, 0)
        print(
            "SOURCE ONLY native control/full65:",
            f"requests={request_count} statements={statement_count}",
            f"requestWireBytes={request_bytes} receivedWireBytes={received}",
            f"reserved={reserved} refunded={reserved - received}",
            "actualQualification=NO-GO socket=0 dns=0",
        )


if __name__ == "__main__":
    unittest.main()
