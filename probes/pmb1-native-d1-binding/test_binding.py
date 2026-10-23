"""Synthetic protocol/SQLite tests. No native oracle or live qualification."""

import contextlib
import copy
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock, patch

import binding
from binding import adapter

SQLiteJournal, encode = binding.SQLiteJournal, binding.encode
Response, collect_snapshot = binding.Response, binding.collect_snapshot


@contextlib.contextmanager
def patched_transport(*args, module=binding, **kwargs):
    """Trusted synthetic patch, including its explicit in-memory identity anchor.

    This is test code, not an activation/qualification bypass in the operator.
    Production source has no switch that replaces its frozen transport export.
    """
    with patch.object(module, "_pinned_https", *args, **kwargs) as transport:
        with patch.dict(module._BOUND_EXPORTS, {"_pinned_https": transport}):
            yield transport


HERE = Path(__file__).resolve().parent
CANDIDATE = binding.ROOT / "probes/pmb1-integer-candidate"
FIXED = adapter.verify_source()
TOKEN = "synthetic-not-a-real-token"
TARGET = "a" * 32 + "/" + "b" * 8 + "-" + "b" * 4 + "-" + "b" * 4 + "-" + "b" * 4 + "-" + "b" * 12


class BindingTests(unittest.TestCase):
    def setUp(self):
        # Independent final boundary, shared by all closed graph modules through
        # the trusted standard-library socket object. Even a mistaken HTTP mock
        # must not acquire a real socket or resolve an address. Teardown records
        # ANY attempted lower-boundary call, including exceptions caught by code.
        socket_patch = patch(
            "socket.socket", side_effect=AssertionError("synthetic_socket_forbidden")
        )
        dns_patch = patch(
            "socket.getaddrinfo", side_effect=AssertionError("synthetic_dns_forbidden")
        )
        self.socket_blocker, self.dns_blocker = socket_patch.start(), dns_patch.start()
        self.addCleanup(socket_patch.stop)
        self.addCleanup(dns_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.clock_value = 10.0
        self.fixture = json.loads((CANDIDATE / "d1-profile-fixture.json").read_text())
        self.profile_path = self.directory / "profile.json"
        self.profile_path.write_bytes(binding.canonical(self.fixture["manifest"]))
        self.profile_pin = binding.sha2_256(self.profile_path.read_bytes())
        self.candidate_pin = binding.sha2_256((CANDIDATE / "source-manifest.json").read_bytes())
        self.source = binding.native_source_descriptor(
            self.candidate_pin, self.profile_path, self.profile_pin
        )
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.executescript((CANDIDATE / "d1-schema.sql").read_text())
        self.db.executescript((CANDIDATE / "d1-guards.sql").read_text())
        self.db.execute(self.fixture["providerMetadataDdl"])
        self.evidence = self.directory / "synthetic-independent-fixture-only.txt"
        self.evidence.write_text("SYNTHETIC: not source-oracle/qualification/custody evidence\n")
        record = {
            "path": str(self.evidence),
            "sha2_256": binding.sha2_256(self.evidence.read_bytes()),
        }
        self.packet = {
            "kind": "pmb1-finite-native-d1-operator-v1",
            "accountId": "a" * 32,
            "databaseId": TARGET.split("/")[1],
            "endpointAddress": "1.1.1.1",
            "targetId": TARGET,
            "candidate": self.source.candidate,
            "sourcePins": binding.source_pins(),
            "credentialSha2_256": binding.sha2_256(TOKEN.encode()),
            "starts": 0,
            "ends": 200,
            "clockDomain": "synthetic-frozen-not-real-operator-clock",
            "timeoutSeconds": 30,
            "maxResponseBytes": 512 * 1024,
            "maxTotalBytes": 16 * 1024 * 1024,
            "queries": [],
            "profileSha2_256": self.profile_pin,
            "independentEvidence": {
                name: copy.deepcopy(record)
                for name in (
                    "review",
                    "grant",
                    "custody",
                    "primaryAndCommitSemantics",
                    "sourceOracle",
                    "allWriterInterval",
                    "allocation",
                )
            },
        }
        self.network_calls = []

    def tearDown(self):
        self.assertEqual(self.socket_blocker.call_count, 0, "attempted real socket acquisition")
        self.assertEqual(self.dns_blocker.call_count, 0, "attempted DNS resolution")

    def clock(self):
        return self.clock_value

    def plan(self, queries):
        self.packet["queries"] = queries
        packet_path = self.directory / "packet.json"
        packet_path.write_bytes(binding.canonical(self.packet))
        pin = binding.sha2_256(packet_path.read_bytes())
        journal_path = self.directory / "external-journal.sqlite"
        journal = SQLiteJournal(journal_path, TARGET, pin, self.clock)
        journal.provision(200)
        client = binding.Binding(packet_path, pin, journal_path, self.source, clock=self.clock)
        return client, journal, packet_path

    def client(self, queries):
        client, journal, path = self.plan(queries)
        client.activate(lambda: TOKEN)
        return client, journal, path

    def query(self, role, sql, params=None):
        return {"role": role, "sql": sql, "params": [] if params is None else params}

    def response(self, rows, meta=None):
        body = binding.canonical(
            {
                "success": True,
                "errors": [],
                "messages": [],
                "result": [
                    {
                        "success": True,
                        "results": rows,
                        "meta": {"served_by_primary": True} if meta is None else meta,
                    }
                ],
            }
        )
        return Response(200, {"content-type": "application/json"}, body, len(body) + 128)

    def transport(self, request, address, clock, guard, **kwargs):
        self.network_calls.append(request)
        self.assertEqual(str(address), "1.1.1.1")
        self.assertTrue(kwargs["discard_set_cookie"])
        guard()
        wire_headers, body = request.wire.split(b"\r\n\r\n", 1)
        self.assertIn(b"Host: api.cloudflare.com", wire_headers)
        self.assertTrue(request.url.endswith("/query"))
        payload = json.loads(body)
        self.assertEqual(set(payload), {"sql", "params"})
        cursor = self.db.execute(payload["sql"], payload["params"])
        rows = [
            dict(zip([column[0] for column in cursor.description], row, strict=True))
            for row in cursor.fetchall()
        ]
        return self.response(rows)

    def intent(self, key="first", operation: adapter.Operation = "reopen", expected="1", limit=3):
        return adapter.Intent(
            key,
            operation,
            expected,
            adapter.Window(0, 100, 200),
            TARGET,
            self.source.candidate,
            transition_limit=limit,
        )

    def test_inert_construction_and_cli_no_credential_or_file_io(self):
        with patch.object(Path, "open", side_effect=AssertionError("unexpected file")):
            client = binding.Binding("missing", "x", "missing", self.source)
            journal = SQLiteJournal("missing", TARGET, "x", self.clock)
            custodian = binding.FileConfirmations(
                "missing", "x", "producer", TARGET, self.source.candidate, self.clock
            )
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(binding.main([]), 0)
            self.assertIn("INERT", stream.getvalue())
        self.assertIsNone(client.token)
        self.assertIsNotNone(journal)
        self.assertIsNotNone(custodian)
        with self.assertRaises(adapter.Refusal):
            client.query("snapshot", "SELECT 1", [], 100)

    def test_retained_packet_pin_refuses_before_credential_delivery(self):
        client, _journal, path = self.plan([self.query("snapshot", "SELECT 1")])
        path.write_bytes(path.read_bytes() + b" ")
        loader = Mock(return_value=TOKEN)
        with self.assertRaises(adapter.Refusal):
            client.activate(loader)
        loader.assert_not_called()

    def test_missing_journal_refuses_before_credential_delivery(self):
        client, _journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
        Path(client.journal_path).unlink()
        loader = Mock(return_value=TOKEN)
        with self.assertRaises(adapter.Refusal):
            client.activate(loader)
        loader.assert_not_called()
        self.assertFalse(Path(client.journal_path).exists())

    def test_foreign_preloaded_journal_cannot_replace_exact_sibling_before_loader(self):
        client, _journal, packet_path = self.plan([self.query("snapshot", "SELECT 1")])
        Path(client.journal_path).unlink()
        fake = types.ModuleType("journal")

        class ForeignJournal:
            def __init__(self, *args):
                raise AssertionError("foreign journal must never be constructed")

        fake.__dict__.update(
            SQLiteJournal=ForeignJournal, encode=json.dumps, intent_from=lambda value: value
        )
        spec = importlib.util.spec_from_file_location(
            "binding_collision_regression", binding.__file__
        )
        assert spec is not None and spec.loader is not None
        collided = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"journal": fake}):
            spec.loader.exec_module(collided)
            self.assertIs(sys.modules["journal"], fake)
            self.assertIsNot(collided.SQLiteJournal, ForeignJournal)
            tested = collided.Binding(
                packet_path,
                client.packet_sha2_256,
                client.journal_path,
                self.source,
                clock=self.clock,
            )
            loader = Mock(return_value=TOKEN)
            source = collided.native_source_descriptor(
                self.candidate_pin, self.profile_path, self.profile_pin
            )
            tested.source = source
            with patched_transport(module=collided) as network:
                with self.assertRaises(ValueError):
                    tested.activate(loader)
                loader.assert_not_called()
                network.assert_not_called()
        self.assertFalse(Path(client.journal_path).exists())

    def test_executable_journal_exports_and_frozen_bytes_are_rechecked(self):
        with patch.object(binding, "SQLiteJournal", object()):
            with self.assertRaisesRegex(adapter.Refusal, "executable_project_graph_drift"):
                binding.source_pins()
        with patch.dict(binding._GRAPH_BYTES, {"journal": b"foreign"}):
            with self.assertRaisesRegex(adapter.Refusal, "executable_project_graph_drift"):
                binding.source_pins()
        for module_name, export in (
            ("prospective_control", "source_descriptor"),
            ("scripts.hosted_publisher_execution_provider", "_pinned_https"),
            ("scripts.private_d1_snapshot_codec", "collect_snapshot"),
        ):
            with (
                self.subTest(module=module_name),
                patch.object(binding._GRAPH[module_name], export, object()),
            ):
                with self.assertRaisesRegex(adapter.Refusal, "executable_project_graph_drift"):
                    binding.source_pins()

    def test_preloaded_source_transport_codec_and_package_namesakes_cannot_replace_graph(self):
        client, _journal, packet_path = self.plan([self.query("snapshot", "SELECT 1")])
        Path(client.journal_path).unlink()
        names = (
            "adapter",
            "prospective_control",
            "scripts",
            "scripts.hosted_publisher_execution_provider",
            "scripts.private_d1_snapshot_codec",
            "scripts.private_d1_snapshot_profile",
            "scripts.temporary_composition_metadata_collector",
        )
        fakes = {name: types.ModuleType(name) for name in names}
        foreign_source = Mock(side_effect=AssertionError("foreign source must not execute"))
        fakes["prospective_control"].__dict__["source_descriptor"] = foreign_source
        spec = importlib.util.spec_from_file_location("binding_graph_collision", binding.__file__)
        assert spec is not None and spec.loader is not None
        collided = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, fakes):
            spec.loader.exec_module(collided)
            for name, fake in fakes.items():
                self.assertIs(sys.modules[name], fake)
                if name != "scripts":
                    self.assertIsNot(collided._GRAPH[name], fake)
            with self.assertRaises(ValueError):
                collided.native_source_descriptor("0" * 64, self.profile_path, self.profile_pin)
            foreign_source.assert_not_called()
            source = collided.native_source_descriptor(
                self.candidate_pin, self.profile_path, self.profile_pin
            )
            tested = collided.Binding(
                packet_path, client.packet_sha2_256, client.journal_path, source, clock=self.clock
            )
            loader = Mock(return_value=TOKEN)
            with patched_transport(module=collided) as network:
                with self.assertRaises(ValueError):
                    tested.activate(loader)
                loader.assert_not_called()
                network.assert_not_called()

    def test_hostile_packet_identity_address_limits_and_query_shapes(self):
        for field, value in (
            ("targetId", "wrong"),
            ("accountId", "a" * 31),
            ("endpointAddress", "127.0.0.1"),
            ("endpointAddress", "example.com"),
            ("maxResponseBytes", 512 * 1024 + 1),
            ("maxTotalBytes", True),
            ("ends", 301),
            ("sourcePins", {}),
        ):
            with self.subTest(field=field, value=value):
                saved = self.packet[field]
                self.packet[field] = value
                with tempfile.TemporaryDirectory() as sub:
                    original = self.directory
                    self.directory = Path(sub)
                    client, _journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
                    loader = Mock(return_value=TOKEN)
                    with self.assertRaises(ValueError):
                        client.activate(loader)
                    loader.assert_not_called()
                    self.directory = original
                self.packet[field] = saved
        for sql in (
            "DROP TABLE maintenance_control",
            "SELECT 1; DELETE FROM fga_users",
            "SELECT 1 -- hidden",
            "SELECT 1 /* hidden */",
        ):
            with self.subTest(sql=sql), tempfile.TemporaryDirectory() as sub:
                original = self.directory
                self.directory = Path(sub)
                client, _journal, _path = self.plan([self.query("snapshot", sql)])
                with self.assertRaises(adapter.Refusal):
                    client.activate(lambda: TOKEN)
                self.directory = original

    def test_source_or_evidence_drift_refuses_before_dispatch(self):
        client, _journal, _path = self.client([self.query("snapshot", "SELECT 1")])
        self.evidence.write_text("changed independent evidence")
        with patched_transport() as network:
            with self.assertRaises(adapter.Refusal):
                client.query("snapshot", "SELECT 1", [], 100)
            network.assert_not_called()

    def test_exact_manifest_wrong_role_sql_params_refused_without_spending(self):
        client, journal, _path = self.client([self.query("snapshot", "SELECT 1")])
        for role, sql, params in (
            ("observer", "SELECT 1", []),
            ("snapshot", "SELECT 2", []),
            ("snapshot", "SELECT 1", ["x"]),
        ):
            with self.assertRaises(adapter.Refusal):
                client.query(role, sql, params, 100)
        self.assertEqual(journal.remaining(16 * 1024 * 1024, 100)[0], 0)

    def test_primary_readback_complete_exact_schema_and_generation_text(self):
        queries = [
            self.query("observer", FIXED[name].decode()) for name in ("readback.sql", "schema.sql")
        ]
        client, journal, _path = self.client(queries)
        with patched_transport(self.transport):
            observer = binding.Observer(client)
            control = observer.read(FIXED["readback.sql"].decode(), 100)
            schema = observer.read(FIXED["schema.sql"].decode(), 100)
        self.assertEqual(adapter.validate_control(control), ("1", "closed"))
        adapter.validate_schema(schema, {"manifest.json": self.source.manifest})
        self.assertEqual(journal.remaining(16 * 1024 * 1024, 100)[0], 2)
        self.assertEqual(len(self.network_calls), 2)

    def test_missing_false_primary_pagination_wire_and_boolean_changes_are_unknown(self):
        for meta, wire in (
            ({}, None),
            ({"served_by_primary": False}, None),
            ({"served_by_primary": True, "cursor": "more"}, None),
            ({"served_by_primary": True}, -1),
        ):
            with self.subTest(meta=meta, wire=wire), tempfile.TemporaryDirectory() as sub:
                original = self.directory
                self.directory = Path(sub)
                client, journal, _path = self.client([self.query("snapshot", "SELECT 1")])
                response = self.response([{"1": 1}], meta)
                if wire is not None:
                    response = replace(response, wire_bytes=wire)
                with patched_transport(return_value=response):
                    with self.assertRaises(adapter.Refusal):
                        client.query("snapshot", "SELECT 1", [], 100)
                self.assertEqual(
                    journal.remaining(16 * 1024 * 1024, 100), (1, 16 * 1024 * 1024 - 512 * 1024)
                )
                self.directory = original

    def test_unknown_transport_spends_ordinal_and_restart_never_replays(self):
        client, journal, path = self.client([self.query("snapshot", "SELECT 1")])
        with patched_transport(side_effect=TimeoutError) as network:
            with self.assertRaises(adapter.Refusal):
                client.query("snapshot", "SELECT 1", [], 100)
            restarted = binding.Binding(
                path, client.packet_sha2_256, client.journal_path, self.source, clock=self.clock
            )
            restarted.activate(lambda: TOKEN)
            with self.assertRaises(adapter.Refusal):
                restarted.query("snapshot", "SELECT 1", [], 100)
            self.assertEqual(network.call_count, 1)
        self.assertEqual(journal.remaining(16 * 1024 * 1024, 100)[0], 1)

    def test_production_writer_refuses_documented_rough_receipt_before_any_network(self):
        client, journal, _path = self.client(
            [self.query("writer", FIXED["reopen.sql"].decode(), ["1"])]
        )
        with patched_transport() as network:
            with self.assertRaisesRegex(adapter.Refusal, "exact_commit_receipt_unavailable"):
                binding.Provider(client).dispatch(
                    adapter.FixedUpdate(FIXED["reopen.sql"].decode(), "1"), 100
                )
            with self.assertRaisesRegex(adapter.Refusal, "exact_commit_receipt_unavailable"):
                client.query("writer", FIXED["reopen.sql"].decode(), ["1"], 100)
            network.assert_not_called()
        self.assertEqual(journal.remaining(16 * 1024 * 1024, 100)[0], 0)

    def test_accepted_successor_builds_exact_two_statements_without_changing_old_boundary(self):
        successor = binding.exact_receipt_successor
        batch = successor.build(self.intent())
        body = json.loads(successor.request_body(batch))
        self.assertEqual(batch.boundary, "fixed_update_with_exact_count_v1")
        self.assertEqual(
            body,
            {
                "batch": [
                    {"sql": FIXED["reopen.sql"].decode(), "params": ["1"]},
                    {"sql": "SELECT CAST(changes() AS TEXT) AS exact_change_count", "params": []},
                ]
            },
        )
        self.assertEqual(successor.manifest(batch)["statementCount"], 2)
        self.assertEqual(successor.manifest(batch)["protocol"], batch.boundary)
        self.assertEqual(adapter.FixedUpdate("unused", "1").boundary, "single_fixed_update")
        self.assertFalse(hasattr(successor, "dispatch"))
        with self.assertRaises(ValueError):
            successor.request_body(replace(batch, update_sql="DELETE FROM maintenance_control"))
        with self.assertRaises(ValueError):
            successor.build(replace(self.intent(), expected="9223372036854775807"))

    def test_successor_count_model_zero_and_one_are_not_managed_commit_receipts(self):
        successor = binding.exact_receipt_successor
        batch = successor.build(self.intent())
        self.db.execute(batch.update_sql, {"expected_generation": batch.intent.expected})
        value = self.db.execute(successor.COUNT_SQL).fetchone()[0]
        payload = {
            "success": True,
            "errors": [],
            "messages": [],
            "result": [
                {
                    "success": True,
                    "results": [],
                    "meta": {"served_by_primary": True, "changes": 999},
                },
                {
                    "success": True,
                    "results": [{"exact_change_count": value}],
                    "meta": {"served_by_primary": True},
                },
            ],
        }
        decoded = successor.decode_ordered_body(binding.canonical(payload))
        self.assertEqual(decoded.count, 1)
        self.assertFalse(hasattr(decoded, "status"))
        receipt = successor.receipt_manifest(batch, binding.canonical(payload))
        self.assertEqual(receipt["protocol"], "fixed_update_with_exact_count_v1")
        self.assertEqual(receipt["request"], successor.manifest(batch))
        self.assertEqual(receipt["exactChangeCountText"], "1")
        self.assertEqual(
            receipt["responseBodySha2_256"], binding.sha2_256(binding.canonical(payload))
        )
        self.db.execute(batch.update_sql, {"expected_generation": batch.intent.expected})
        value = self.db.execute(successor.COUNT_SQL).fetchone()[0]
        payload["result"][1]["results"] = [{"exact_change_count": value}]
        self.assertEqual(successor.decode_ordered_body(binding.canonical(payload)).count, 0)

    def test_successor_order_count_primary_and_completion_fail_closed(self):
        successor = binding.exact_receipt_successor
        payload = {
            "success": True,
            "errors": [],
            "messages": [],
            "result": [
                {"success": True, "results": [], "meta": {"served_by_primary": True}},
                {
                    "success": True,
                    "results": [{"exact_change_count": "1"}],
                    "meta": {"served_by_primary": True},
                },
            ],
        }
        variants = []
        for count in (1, True, "01", "-1", "2", "1.0", None):
            bad = copy.deepcopy(payload)
            bad["result"][1]["results"] = [{"exact_change_count": count}]
            variants.append(bad)
        for results in (
            list(reversed(payload["result"])),
            payload["result"][:1],
            payload["result"] * 2,
        ):
            bad = copy.deepcopy(payload)
            bad["result"] = results
            variants.append(bad)
        for meta in (
            {},
            {"served_by_primary": False},
            {"served_by_primary": True, "has_more": False},
        ):
            bad = copy.deepcopy(payload)
            bad["result"][1]["meta"] = meta
            variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                successor.decode_ordered_body(binding.canonical(bad))

    def test_full_65_table_reader_exact_metadata_guards_and_signed_integers(self):
        # Oracle here is explicitly a SYNTHETIC separate fixture query. Native
        # implementation never creates or populates expected profile/source data.
        statements = []
        self.db.execute(FIXED["reopen.sql"].decode(), {"expected_generation": "1"})
        self.db.execute("INSERT INTO fga_users(rowid,user_id) VALUES(?,?)", (-(2**63), "min-π"))
        self.db.execute("INSERT INTO fga_users(rowid,user_id) VALUES(?,?)", (2**63 - 1, "max"))

        def oracle(sql):
            statements.append(sql)
            cursor = self.db.execute(sql)
            return [
                dict(zip([column[0] for column in cursor.description], row, strict=True))
                for row in cursor.fetchall()
            ]

        expected = collect_snapshot(oracle, page_size=2, profile_manifest=self.fixture["manifest"])
        self.assertEqual(len(expected["tables"]), 65)
        self.assertEqual(sorted(expected["tables"]["fga_users"]["rowids"]), [-(2**63), 2**63 - 1])
        client, journal, _path = self.client([self.query("snapshot", sql) for sql in statements])
        with patched_transport(self.transport):
            actual = binding.CompleteReader(client).collect(
                self.profile_path, self.profile_pin, 100, page_size=2
            )
        self.assertEqual(actual, expected)
        self.assertEqual(journal.remaining(16 * 1024 * 1024, 100)[0], len(statements))
        self.assertLess(len(statements), 2048)

    def test_native_descriptor_rejects_wrong_source_oracle_schema(self):
        profile = copy.deepcopy(self.fixture["manifest"])
        profile["schema"][0]["sql"] = "CREATE TABLE fabricated(value)"
        self.profile_path.write_bytes(binding.canonical(profile))
        pin = binding.sha2_256(self.profile_path.read_bytes())
        with self.assertRaises(ValueError):
            binding.native_source_descriptor(self.candidate_pin, self.profile_path, pin)

    def test_journal_global_reservation_restart_counters_and_lost_ack(self):
        _client, journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
        first = self.intent()
        self.assertTrue(journal.latch(first, 100))
        restarted = SQLiteJournal(journal.path, TARGET, journal.packet_sha2_256, self.clock)
        self.assertFalse(restarted.latch(self.intent("different"), 100))
        self.assertTrue(restarted.claim_dispatch(first.key, 100))
        self.assertFalse(journal.claim_dispatch(first.key, 100))
        journal.settle(first.key, "unknown", 100)
        self.assertTrue(restarted.get(first.key, 100).dispatch_claimed)
        self.assertTrue(restarted.claim_reconcile(first.key, 200))
        self.assertTrue(restarted.claim_reconcile(first.key, 200))
        self.assertFalse(restarted.claim_reconcile(first.key, 200))
        for _ in range(16):
            self.assertTrue(journal.spend_read(first.key, 100))
        self.assertFalse(restarted.spend_read(first.key, 100))

    def test_journal_atomic_successor_preserves_root_and_consumed_history(self):
        _client, journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
        first = self.intent()
        self.assertTrue(journal.latch(first, 100))
        self.assertTrue(journal.claim_dispatch(first.key, 100))
        journal.settle(first.key, "confirmed", 100)
        result = adapter.Result("confirmed", "one_row_and_independent_readback", "2", "open", 10)
        receipt = adapter.ConfirmedReceipt("receipt-one", first, result)
        second = self.intent("second", "close", "2")
        self.assertTrue(journal.advance(first, second, receipt, 100))
        self.assertFalse(journal.advance(first, self.intent("racer", "close", "2"), receipt, 100))
        self.assertEqual(journal.get(second.key, 100).root_key, first.key)
        self.assertEqual(journal.get(first.key, 100).confirmation, "receipt-one")
        with self.assertRaises(adapter.Refusal):
            journal.settle(first.key, "unknown", 100)
        self.assertFalse(journal.latch(self.intent("newroot"), 100))

    def test_journal_byte_and_request_limits_are_durable_and_never_reset(self):
        _client, journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
        self.assertEqual(journal.reserve_request("fixed", 10, 10, 1, 100), 0)
        with self.assertRaises(adapter.Refusal):
            journal.reserve_request("fixed", 1, 10, 1, 100)
        restarted = SQLiteJournal(journal.path, TARGET, journal.packet_sha2_256, self.clock)
        self.assertEqual(restarted.remaining(10, 100), (1, 0))
        for allowance in (-1, True, 512 * 1024 + 1):
            with self.assertRaises(adapter.Refusal):
                restarted.reserve_request("fixed", allowance, 10, 1, 100)
        journal.received(0, 4, 100)
        self.assertEqual(restarted.remaining(10, 100), (1, 6))
        with self.assertRaises(adapter.Refusal):
            journal.received(0, 0, 100)

    def test_journal_concurrent_latches_have_at_most_one_owner(self):
        _client, journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
        barrier = threading.Barrier(2)
        outcomes = []

        def worker(key):
            barrier.wait()
            try:
                outcomes.append(journal.latch(self.intent(key), 100))
            except sqlite3.OperationalError:
                outcomes.append(False)  # zero busy timeout deliberately refuses

        threads = [threading.Thread(target=worker, args=(key,)) for key in ("one", "two")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(outcomes), 1)

    def test_committed_latch_late_ack_is_permanently_consumed(self):
        _client, journal, _path = self.plan([self.query("snapshot", "SELECT 1")])
        real_guard = journal.guard
        checks = 0

        def late_after_commit(deadline):
            nonlocal checks
            checks += 1
            if checks == 4:
                raise TimeoutError("synthetic acknowledgment loss after commit")
            real_guard(deadline)

        with patch.object(journal, "guard", late_after_commit):
            with self.assertRaises(TimeoutError):
                journal.latch(self.intent(), 100)
        self.assertFalse(journal.latch(self.intent("replacement"), 100))
        self.assertEqual(journal.get("first", 100).phase, "latched")

    def test_confirmations_require_independent_retained_index_pin_and_complete_inventory(self):
        first = self.intent()
        result = adapter.Result("confirmed", "one_row_and_independent_readback", "2", "open", 10)
        record = {
            "path": str(self.evidence),
            "sha2_256": binding.sha2_256(self.evidence.read_bytes()),
        }
        receipt = {
            "reference": "receipt-one",
            "producer": "synthetic-independent-custodian",
            "intent": asdict(first),
            "returnedResult": asdict(result),
            "evidence": {
                name: copy.deepcopy(record)
                for name in (
                    "oneRowCommit",
                    "completePrimaryReadback",
                    "finalJournalAck",
                    "returnedInvocation",
                )
            },
        }
        path = self.directory / "receipt.json"
        path.write_text(encode(receipt))
        index_path = self.directory / "index.json"
        index = {
            "producer": "synthetic-independent-custodian",
            "receipts": {
                "receipt-one": {"path": str(path), "sha2_256": binding.sha2_256(path.read_bytes())}
            },
        }
        index_path.write_text(encode(index))
        pin = binding.sha2_256(index_path.read_bytes())
        custodian = binding.FileConfirmations(
            index_path, pin, index["producer"], TARGET, self.source.candidate, self.clock
        )
        self.assertEqual(custodian.read("receipt-one", 100).predecessor, first)
        index_path.write_text(encode({"producer": "self-seeded", "receipts": {}}))
        with self.assertRaises(adapter.Refusal):
            custodian.read("receipt-one", 100)
        # No retained pin producer or native oracle is created by this class.
        self.assertFalse(hasattr(custodian, "retain_returned"))


if __name__ == "__main__":
    unittest.main()
