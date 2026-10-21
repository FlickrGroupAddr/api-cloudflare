"""Physical socket budgets for both concrete finite HTTPS readers."""

import ipaddress
import ssl
import unittest
from typing import cast
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution_provider as execution
from scripts import hosted_publisher_finite_client as client


class BudgetSocket:
    def __init__(self, wire, cap, fragment, *, fail=False):
        self.pending, self.cap, self.fragment = wire, cap, fragment
        self.fail = fail
        self.reads = []
        self.received = 0
        self.sent = []
        self.closed = False

    def recv(self, count):
        remaining = self.cap - self.received
        if not 0 < count <= remaining:
            raise AssertionError("socket read exceeds remaining physical capacity")
        if self.fail:
            self.reads.append((remaining, count, 0))
            raise TimeoutError("synthetic timeout")
        data, self.pending = (
            self.pending[: min(count, self.fragment)],
            self.pending[min(count, self.fragment) :],
        )
        self.reads.append((remaining, count, len(data)))
        self.received += len(data)
        return data

    def settimeout(self, timeout):
        if timeout <= 0:
            raise AssertionError("nonpositive timeout")

    def connect(self, address):
        pass

    def sendall(self, wire):
        self.sent.append(wire)

    def close(self):
        self.closed = True


class PhysicalWireCapacityTests(unittest.TestCase):
    def request(self, cap):
        return client.Request("https://synthetic.invalid/probe", {}, 5, cap, 105, b"request")

    def call(self, kind, sock, *, clock=lambda: 100):
        context = Mock()
        context.wrap_socket.return_value = sock
        with (
            patch.object(execution.socket, "socket", return_value=sock),
            patch.object(execution.ssl, "create_default_context", return_value=context),
        ):
            if kind == "execution":
                return execution._pinned_https(
                    self.request(sock.cap), ipaddress.ip_address("1.1.1.1"), clock
                )
            return client.HttpsTransport("1.1.1.1", enabled=True, clock=clock)(
                self.request(sock.cap)
            )

    def assert_budget(self, sock):
        self.assertTrue(sock.reads)
        self.assertLessEqual(sock.received, sock.cap)
        self.assertTrue(all(0 < count <= remaining for remaining, count, _ in sock.reads))
        self.assertTrue(all(size <= count for _, count, size in sock.reads))
        self.assertEqual(len(sock.sent), 1)
        self.assertTrue(sock.closed)

    def test_complete_fixed_and_chunked_frames_at_exact_boundary(self):
        for wire in (
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"2\r\n{}\r\n0\r\nX-Check: yes\r\n\r\n",
        ):
            for kind in ("execution", "finite"):
                for fragment in (1, 11, 4096):
                    with self.subTest(kind=kind, fragment=fragment, wire=wire[:30]):
                        sock = BudgetSocket(wire, len(wire), fragment)
                        response = self.call(kind, sock)
                        self.assertEqual(response.body, b"{}")
                        self.assertEqual(response.wire_bytes, len(wire))
                        self.assert_budget(sock)

    def test_one_byte_over_limit_at_each_framing_stage_is_never_received(self):
        cases = (
            b"HTTP/1.1 200 OK\r\n",
            b"HTTP/1.1 200 OK\r\nX-Check: yes\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"2\r\n{}\r\n0\r\nX-Check: yes\r\n\r\n",
        )
        for wire in cases:
            for kind in ("execution", "finite"):
                for fragment in (1, 11, 4096):
                    with self.subTest(kind=kind, fragment=fragment, length=len(wire)):
                        sock = BudgetSocket(wire, len(wire) - 1, fragment)
                        with self.assertRaises(client.UnknownOutcome):
                            self.call(kind, sock)
                        self.assertEqual(sock.received, sock.cap)
                        self.assertEqual(len(sock.pending), 1)
                        self.assert_budget(sock)

    def test_reader_exhaustion_refuses_eof_probe_without_recv_zero(self):
        for reader_type in (execution._WireReader, client._DeadlineReader):
            for suffix in (b"", b"x"):
                with self.subTest(reader=reader_type.__name__, suffix=suffix):
                    sock = BudgetSocket(b"abcd" + suffix, 4, 4096)
                    reader = reader_type(cast(ssl.SSLSocket, sock), self.request(4), lambda: 100)
                    self.assertEqual(reader.readinto(bytearray()), 0)
                    self.assertEqual(sock.reads, [])
                    self.assertEqual(reader.readinto(bytearray(32)), 4)
                    reads = len(sock.reads)
                    with self.assertRaises(client.UnknownOutcome):
                        reader.readinto(bytearray(32))
                    self.assertEqual(len(sock.reads), reads)
                    self.assertEqual(reader.received, 4)
                    with self.assertRaises(client.UnknownOutcome):
                        reader.readinto(bytearray())
                    self.assertEqual(len(sock.reads), reads)

    def test_full_client_ceiling_has_no_extra_detection_byte(self):
        for reader_type in (execution._WireReader, client._DeadlineReader):
            for fragment in (1, 4096, 100_000):
                with self.subTest(reader=reader_type.__name__, fragment=fragment):
                    cap = 65_536
                    sock = BudgetSocket(b"x" * (cap + 1), cap, fragment)
                    reader = reader_type(cast(ssl.SSLSocket, sock), self.request(cap), lambda: 100)
                    while sock.received < cap:
                        reader.readinto(bytearray(100_000))
                    with self.assertRaises(client.UnknownOutcome):
                        reader.readinto(bytearray(100_000))
                    self.assertEqual(reader.received, cap)
                    self.assertEqual(sock.pending, b"x")

    def test_real_eof_below_limit_is_distinct_from_capacity_exhaustion(self):
        for reader_type in (execution._WireReader, client._DeadlineReader):
            sock = BudgetSocket(b"abc", 4, 4096)
            reader = reader_type(cast(ssl.SSLSocket, sock), self.request(4), lambda: 100)
            self.assertEqual(reader.readinto(bytearray(32)), 3)
            self.assertEqual(reader.readinto(bytearray(32)), 0)
            self.assertEqual(sock.reads[-1], (1, 1, 0))

    def test_eof_framed_finite_response_at_boundary_is_unknown(self):
        wire = b"HTTP/1.1 200 OK\r\n\r\n{}"
        sock = BudgetSocket(wire, len(wire), 1)
        with self.assertRaises(client.UnknownOutcome):
            self.call("finite", sock)
        self.assertEqual(sock.received, len(wire))
        self.assert_budget(sock)

    def test_timeouts_preserve_budget_without_retry(self):
        for kind in ("execution", "finite"):
            sock = BudgetSocket(b"", 4, 4096, fail=True)
            with self.assertRaises(TimeoutError):
                self.call(kind, sock)
            self.assert_budget(sock)
            self.assertEqual(len(sock.reads), 1)
        for reader_type in (execution._WireReader, client._DeadlineReader):
            sock = BudgetSocket(b"data", 4, 4096)
            reader = reader_type(cast(ssl.SSLSocket, sock), self.request(4), lambda: 106)
            with self.assertRaises((client.UnknownOutcome, TimeoutError)):
                reader.readinto(bytearray(32))
            self.assertEqual(sock.reads, [])


if __name__ == "__main__":
    unittest.main()
