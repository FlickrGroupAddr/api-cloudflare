"""Synthetic wire/socket and durable-budget checks. No network or real tokens."""

import hashlib
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import transport
from population import HttpsGet
from test_population import ACCOUNT, EXPECTED, NAMESPACE, NS, namespace_page, object_page
from transport import Refused

TOKEN = "synthetic-token-never-used-remotely"


class Socket:
    def __init__(self, wire, writes):
        self.wire, self.writes = bytearray(wire), writes

    def settimeout(self, _value):
        pass

    def connect(self, address):
        self.writes.append(("address", address))

    def sendall(self, wire):
        self.writes.append(("request", wire))

    def recv(self, maximum):
        out = bytes(self.wire[:maximum])
        del self.wire[:maximum]
        return out

    def close(self):
        pass


class Context:
    def wrap_socket(self, raw, server_hostname):
        if server_hostname != "api.cloudflare.com":
            raise AssertionError("wrong TLS hostname")
        return raw


def response(body, extra=b"", status=b"200 OK"):
    return (
        b"HTTP/1.1 "
        + status
        + b"\r\nContent-Type: application/json\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n"
        + extra
        + b"\r\n"
        + body
    )


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        evidence = self.directory / "synthetic-evidence.txt"
        evidence.write_bytes(b"SYNTHETIC ONLY; no qualification or authority\n")
        record = {
            "path": str(evidence),
            "sha2_256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        }
        expected = {"accountId": ACCOUNT, "accountNamespaces": [NS], "objects": EXPECTED}
        self.packet = {
            "schema": "pmb1-finite-native-census-packet-v1",
            "accountId": ACCOUNT,
            "selectedNamespaces": [NAMESPACE],
            "address": "1.1.1.1",
            "starts": 100.0,
            "ends": 125.0,
            "timeoutSeconds": 20.0,
            "maxCalls": 4,
            "maxResponseBytes": 262144,
            "maxTotalBytes": 1048576,
            "credentialSha2_256": hashlib.sha256(TOKEN.encode()).hexdigest(),
            "sourcePins": transport.source_pins(),
            "independentEvidence": {
                name: record
                for name in (
                    "review",
                    "grant",
                    "custody",
                    "inventory",
                    "sourceOracle",
                    "allWriterInterval",
                    "allocation",
                )
            },
            "expectedPopulationSha2_256": hashlib.sha256(
                transport._canonical(expected)
            ).hexdigest(),
        }
        self.packet_path, self.journal_path = (
            self.directory / "packet.json",
            self.directory / "journal.sqlite",
        )
        self.writes = []
        self._write_packet()

    def _write_packet(self):
        raw = json.dumps(self.packet, sort_keys=True, separators=(",", ":")).encode()
        self.packet_path.write_bytes(raw)
        self.pin = hashlib.sha256(raw).hexdigest()

    def make(self):
        return transport.FiniteHttpsGet(
            self.packet_path, self.pin, self.journal_path, clock=lambda: 100.0
        )

    def active(self):
        client = self.make()
        client.prepare_journal()
        client.activate(lambda: TOKEN)
        return client

    def sockets(self, wires):
        sockets = [Socket(wire, self.writes) for wire in wires]
        stack = self.enterContext(patch("socket.socket", side_effect=sockets))
        self.enterContext(patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")))
        self.enterContext(patch("ssl.create_default_context", return_value=Context()))
        return stack

    def test_explicit_concrete_census_uses_fixed_get_tls_hostname_and_durable_wire_budget(self):
        client = self.active()
        ns, objects = namespace_page(), object_page()
        self.sockets([response(ns, b"Set-Cookie: a=1\r\nSet-Cookie: b=2\r\n"), response(objects)])
        result = client.collect([NS], EXPECTED)
        self.assertEqual(result["accountId"], ACCOUNT)
        self.assertEqual(result["objects"], EXPECTED)
        self.assertFalse(result["completeSnapshot"])
        self.assertFalse(result["actualQualification"])
        with self.assertRaisesRegex(Refused, "native_census_attempt_spent"):
            client.collect([NS], EXPECTED)
        requests = [wire for kind, wire in self.writes if kind == "request"]
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(wire.startswith(b"GET /client/v4/accounts/") for wire in requests))
        self.assertTrue(all(b"Cookie:" not in wire for wire in requests))
        self.assertEqual(
            [address for kind, address in self.writes if kind == "address"], [("1.1.1.1", 443)] * 2
        )
        with closing(sqlite3.connect(self.journal_path)) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM requests WHERE received IS NOT NULL").fetchone()[
                    0
                ],
                2,
            )
        with self.assertRaisesRegex(Refused, "native_census_attempt_spent"):
            self.make().activate(lambda: TOKEN)

    def test_default_and_missing_journal_refuse_before_socket_or_credential(self):
        client = self.make()
        with patch("socket.socket", side_effect=AssertionError("no socket")):
            with self.assertRaisesRegex(ValueError, "native_census_transport_unqualified"):
                HttpsGet(TOKEN)("/", 10, 1)
            with self.assertRaisesRegex(ValueError, "external_journal_missing"):
                client.activate(lambda: self.fail("must not load a credential"))
        self.assertFalse(self.journal_path.exists())

    def test_fixed_graph_ignores_ambient_modules_and_rejects_method_substitution(
        self,
    ):
        client = self.active()
        self.sockets([response(namespace_page()), response(object_page())])
        fake = types.ModuleType("population")
        with patch.dict(
            sys.modules, {"population": fake, "scripts.hosted_publisher_execution_provider": fake}
        ):
            self.assertEqual(client.collect([NS], EXPECTED)["objects"], EXPECTED)
        actual = transport._population()
        with patch.object(
            actual.Census, "collect", lambda *_args: self.fail("substituted implementation")
        ):
            with self.assertRaisesRegex(Refused, "native_census_population_drift"):
                transport.source_pins()

    def test_unknown_response_spends_reservation_and_cannot_replay_in_new_instance(self):
        client = self.active()
        self.sockets(
            [b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nContent-Type: application/json\r\n\r\n{}"]
        )
        path = (
            f"/client/v4/accounts/{ACCOUNT}/workers/durable_objects/namespaces?page=1&per_page=10"
        )
        with self.assertRaisesRegex(Refused, "native_census_refused_or_unknown_no_replay"):
            client(path, 262144, 10)
        with self.assertRaisesRegex(Refused, "native_census_refused_or_unknown_no_replay"):
            client(path, 262144, 10)
        with self.assertRaisesRegex(Refused, "native_census_attempt_spent"):
            self.make().activate(lambda: self.fail("spent attempt must not load credential"))
        self.assertEqual(len([x for x in self.writes if x[0] == "request"]), 1)
        with closing(sqlite3.connect(self.journal_path)) as db:
            self.assertEqual(
                db.execute("SELECT reserved,received FROM requests").fetchone(), (262144, None)
            )

    def test_mismatched_inventory_source_grant_packet_paths_and_limits_fail_closed(self):
        client = self.active()
        with patch("socket.socket", side_effect=AssertionError("no socket")):
            with self.assertRaisesRegex(Refused, "native_census_expected_inventory_pin"):
                client.collect([NS], {NAMESPACE: []})
            wrong = (
                f"/client/v4/accounts/{'f' * 32}/workers/durable_objects/"
                "namespaces?page=1&per_page=10"
            )
            with self.assertRaisesRegex(Refused, "native_census_refused_or_unknown_no_replay"):
                client(wrong, 262144, 10)
        self.assertEqual(self.writes, [])

    def test_redirect_duplicate_framing_oversize_and_cookie_budget_are_refused(self):
        wires = [
            response(b"{}", b"Location: https://elsewhere.invalid/\r\n", b"302 Found"),
            response(b"{}", b"Content-Length: 2\r\n"),
            response(b"{}", b"Set-Cookie: " + b"x" * 300000 + b"\r\n"),
        ]
        for index, wire in enumerate(wires):
            self.journal_path = self.directory / f"wire-{index}.sqlite"
            client = self.active()
            with (
                patch("socket.socket", return_value=Socket(wire, self.writes)),
                patch("ssl.create_default_context", return_value=Context()),
            ):
                with self.assertRaisesRegex(Refused, "native_census_refused_or_unknown_no_replay"):
                    client(
                        f"/client/v4/accounts/{ACCOUNT}/workers/durable_objects/namespaces?page=1&per_page=10",
                        262144,
                        10,
                    )


if __name__ == "__main__":
    unittest.main()
