"""Injected synthetic-facade tests; never import or run the prior delivery helper."""

from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import io
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import bounded_local_delivery_path_proof as proof

SPEC = importlib.util.spec_from_file_location(
    "preparation_candidate0183", Path(__file__).with_name("0161_local_preparation_candidate.py")
)
assert SPEC is not None and SPEC.loader is not None
candidate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = candidate
SPEC.loader.exec_module(candidate)

USER = "S-1-5-21-100-200-300-1001"


class Clock:
    def __init__(self) -> None:
        self.expired = False

    def __call__(self) -> tuple[float, float]:
        return (1900.0, 900.0) if self.expired else (1001.0, 1.0)


class FixtureFacade:
    """Records abstract effects only; all paths, handles and data are invented."""

    fixture_only = True
    current_user_sid = USER
    trustedinstaller_sid = proof.TRUSTEDINSTALLER

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.calls: list[tuple[str, tuple]] = []
        self.fail_at: str | None = None
        self.expire_after: str | None = None
        self.bad_directory: dict = {}
        self.bad_source: dict = {}
        self.bad_output: dict = {}
        self.read_value = b"fixture0183_bounded_source"
        self.short_write = False
        self.next_identity = 10
        self.nodes: dict[tuple[int, int], proof.Node] = {}
        self.bad_inspection: dict = {}

    def record(self, name: str, *args: object) -> None:
        self.calls.append((name, args))
        if self.expire_after == name:
            self.clock.expired = True
        if self.fail_at == name:
            raise OSError("synthetic failure")

    def open_directory(self, path: str, access: int, share: int, flags: int) -> proof.Node:
        self.record("directory", path, access, share, flags)
        self.next_identity += 1
        node = replace(
            proof.Node(
                path,
                USER,
                (),
                desired_access=access,
                share_mode=share,
                flags=flags,
                handle_id=(1, self.next_identity),
                protected_dacl=True,
            ),
            **self.bad_directory,
        )
        self.nodes[node.handle_id] = node
        return node

    def open_source(self, path: str, access: int, share: int, flags: int) -> proof.Node:
        self.record("source", path, access, share, flags)
        node = replace(
            proof.Node(
                path,
                USER,
                (),
                directory=False,
                desired_access=access,
                share_mode=share,
                flags=flags,
                handle_id=(1, 20),
                protected_dacl=True,
            ),
            **self.bad_source,
        )
        self.nodes[node.handle_id] = node
        return node

    def create_new(
        self, path: str, security: object, access: int, share: int, flags: int
    ) -> proof.Node:
        self.record("create", path, security, access, share, flags)
        node = replace(
            proof.Node(
                path,
                USER,
                (),
                directory=False,
                desired_access=access,
                share_mode=share,
                flags=flags,
                handle_id=(1, 21),
                protected_dacl=True,
                disposition=proof.CREATE_NEW,
                creation_security_at_open=True,
            ),
            **self.bad_output,
        )
        self.nodes[node.handle_id] = node
        return node

    def inspect(self, handle_id: tuple[int, int]) -> proof.Node:
        self.record("inspect", handle_id)
        return replace(self.nodes[handle_id], **self.bad_inspection)

    def read(self, handle_id: tuple[int, int], maximum: int) -> bytes:
        self.record("read", handle_id, maximum)
        return self.read_value

    def write(self, handle_id: tuple[int, int], raw: bytes) -> int:
        self.record("write", handle_id, len(raw))
        return len(raw) - 1 if self.short_write else len(raw)

    def flush(self, handle_id: tuple[int, int]) -> None:
        self.record("flush", handle_id)

    def close(self, handle_id: tuple[int, int]) -> None:
        self.record("close", handle_id)

    def effects(self, name: str) -> list[tuple]:
        return [args for operation, args in self.calls if operation == name]


class PreparationCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.facade = FixtureFacade(self.clock)

    def run_candidate(self):
        return candidate.run_preparation(self.facade, self.clock)

    def test_fixture_run_uses_held_guards_exclusive_creation_and_one_bounded_read(self) -> None:
        receipt = self.run_candidate()
        self.assertIs(receipt.delivered, True)
        self.assertEqual(receipt.outcome, "synthetic_preparation_complete_no_run_authority")
        self.assertEqual(receipt.credential_reads, 1)
        self.assertEqual((receipt.writes, receipt.flushes), (1, 1))
        for field in ("ownerConsent", "nativeConsent", "actionReady"):
            self.assertIs(getattr(receipt, field), False)
        directories = self.facade.effects("directory")
        self.assertEqual([args[0] for args in directories], list(candidate.ROOTS))
        for _, access, share, flags in directories:
            self.assertEqual(access, 0x20081)
            self.assertEqual(share, 1)
            self.assertEqual(flags, 0x2200000)
        self.assertEqual(
            self.facade.effects("source"), [(candidate.SOURCE, 0x80000000, 0, 0x200000)]
        )
        self.assertEqual(self.facade.effects("read"), [((1, 20), 8192)])
        creation = self.facade.effects("create")
        self.assertEqual(len(creation), 1)
        path, security, access, share, flags = creation[0]
        self.assertEqual(path, candidate.DESTINATION)
        self.assertEqual((access, share, flags), (0x40020080, 0, 0x200000))
        self.assertIs(security.protected, True)
        self.assertIn("D:P", security.sddl)
        self.assertEqual(
            [ace.sid for ace in security.aces], [USER, proof.SYSTEM, proof.ADMINISTRATORS]
        )
        self.assertEqual(
            self.facade.effects("close"),
            [((1, 21),), ((1, 20),), ((1, 14),), ((1, 13),), ((1, 12),), ((1, 11),)],
        )

    def test_read_attempt_and_effect_bounds_on_injected_failures(self) -> None:
        for stage, expected_reads in (
            ("source", 0),
            ("create", 0),
            ("read", 1),
            ("write", 1),
            ("flush", 1),
        ):
            with self.subTest(stage=stage):
                facade = FixtureFacade(Clock())
                facade.fail_at = stage
                receipt = candidate.run_preparation(facade, facade.clock)
                self.assertEqual(receipt.credential_reads, expected_reads)
                self.assertIs(receipt.delivered, False)
                self.assertLessEqual(len(facade.effects("read")), 1)

    def test_expiry_is_resampled_before_each_effect(self) -> None:
        for preceding, forbidden in (
            ("source", "create"),
            ("create", "read"),
            ("read", "write"),
            ("write", "flush"),
            ("flush", "inspect"),
        ):
            with self.subTest(preceding=preceding):
                facade = FixtureFacade(Clock())
                facade.expire_after = preceding
                receipt = candidate.run_preparation(facade, facade.clock)
                expected_prior_inspections = 1 if preceding == "flush" else 0
                self.assertEqual(len(facade.effects(forbidden)), expected_prior_inspections)
                self.assertIs(receipt.delivered, False)

    def test_unknown_or_weak_directory_observation_prevents_read(self) -> None:
        for field, value in (
            ("desired_access", 0x20080),
            ("share_mode", 3),
            ("reparse", True),
            ("held", False),
            ("security_by_handle", False),
            ("handle_id", (0, 1)),
            ("aces", (proof.Ace("allow", "S-1-1-0", 0x100),)),
        ):
            with self.subTest(field=field):
                facade = FixtureFacade(Clock())
                facade.bad_directory = {field: value}
                receipt = candidate.run_preparation(facade, facade.clock)
                self.assertEqual(receipt.credential_reads, 0)
                self.assertEqual(facade.effects("read"), [])
                self.assertIs(receipt.delivered, False)

    def test_unqualified_source_or_created_file_prevents_read(self) -> None:
        for kind in ("bad_source", "bad_output"):
            for field, value in (
                ("links", 2),
                ("reparse", True),
                ("share_mode", 1),
                ("protected_dacl", False),
                ("metadata_by_handle", False),
                ("path", "C:\\synthetic\\elsewhere.bin"),
            ):
                with self.subTest(kind=kind, field=field):
                    facade = FixtureFacade(Clock())
                    setattr(facade, kind, {field: value})
                    receipt = candidate.run_preparation(facade, facade.clock)
                    self.assertEqual(receipt.credential_reads, 0)
                    self.assertEqual(facade.effects("read"), [])
                    self.assertIs(receipt.delivered, False)

    def test_malformed_oversized_or_short_delivery_cannot_succeed(self) -> None:
        for raw in (b"", b"x" * 8193, b"unrecognized fixture bytes"):
            with self.subTest(length=len(raw)):
                facade = FixtureFacade(Clock())
                facade.read_value = raw
                receipt = candidate.run_preparation(facade, facade.clock)
                self.assertEqual(receipt.credential_reads, 1)
                self.assertEqual(facade.effects("write"), [])
                self.assertIs(receipt.delivered, False)
        self.facade.short_write = True
        receipt = self.run_candidate()
        self.assertIs(receipt.delivered, False)
        self.assertEqual(self.facade.effects("flush"), [])

    def test_nonfixture_facade_refuses_before_effects(self) -> None:
        self.facade.fixture_only = False
        receipt = self.run_candidate()
        self.assertIs(receipt.delivered, False)
        self.assertEqual(receipt.credential_reads, 0)
        self.assertEqual(self.facade.calls, [])

    def test_initial_expiry_prevents_all_dispatches_and_read_attempts(self) -> None:
        self.clock.expired = True
        receipt = self.run_candidate()
        self.assertEqual(receipt.credential_reads, 0)
        self.assertEqual(self.facade.calls, [])
        self.assertIs(receipt.delivered, False)

    def test_main_is_inert_and_cannot_issue_action_or_consent(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = candidate.main()
        receipt = json.loads(stream.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(receipt["outcome"], "NO_APPLY_source_candidate_only")
        self.assertEqual(receipt["credential_reads"], 0)
        for key in ("credential_delivered", "ownerConsent", "nativeConsent", "actionReady"):
            self.assertIs(receipt[key], False)

    def test_existing_output_failure_has_no_read_write_flush_or_overwrite_fallback(self) -> None:
        self.facade.fail_at = "create"
        receipt = self.run_candidate()
        self.assertEqual(receipt.credential_reads, 0)
        self.assertEqual(len(self.facade.effects("create")), 1)
        for name in ("read", "write", "flush"):
            self.assertEqual(self.facade.effects(name), [])
        self.assertIs(receipt.delivered, False)

    def test_output_alias_or_create_then_tighten_representation_refuses_before_read(self) -> None:
        for fields in (
            {"handle_id": (1, 20)},
            {"creation_security_at_open": False},
            {"disposition": proof.OPEN_EXISTING},
        ):
            with self.subTest(fields=fields):
                facade = FixtureFacade(Clock())
                facade.bad_output = fields
                receipt = candidate.run_preparation(facade, facade.clock)
                self.assertEqual(receipt.credential_reads, 0)
                self.assertEqual(facade.effects("read"), [])
                self.assertIs(receipt.delivered, False)

    def test_inspection_change_or_unknown_completion_never_reports_delivery(self) -> None:
        for field, value in (
            ("owner", "S-1-5-21-100-200-300-1002"),
            ("handle_id", (1, 999)),
            ("aces", None),
            ("reparse", True),
        ):
            with self.subTest(field=field):
                facade = FixtureFacade(Clock())
                facade.bad_inspection = {field: value}
                receipt = candidate.run_preparation(facade, facade.clock)
                self.assertIs(receipt.delivered, False)
                self.assertEqual(facade.effects("write"), [])
        for stage in ("inspect", "close"):
            with self.subTest(stage=stage):
                facade = FixtureFacade(Clock())
                facade.fail_at = stage
                receipt = candidate.run_preparation(facade, facade.clock)
                self.assertIs(receipt.delivered, False)


class NativeAdapterContractTests(unittest.TestCase):
    """Focused real adapter methods with synthetic functions and owned buffers.

    These assert native call arguments and sequencing, not kernel semantics.
    Only owned synthetic pointer buffers are decoded; OS behavior is unproved.
    """

    def adapter(self):
        native = candidate.NativeFacade.__new__(candidate.NativeFacade)
        native.current_user_sid = USER
        native._handles = {}
        native._sizes = {}
        native._read_attempted = False
        native.cleanup_confirmed = True
        native._dispatch_guard = lambda: None
        native.k = SimpleNamespace()
        native.a = SimpleNamespace()
        return native

    def cleanup_failure_case(self, *, partial_open: bool) -> None:
        native = self.adapter()
        native.k.CreateFileW = lambda *args: 101
        native.k.ReadFile = lambda *args: self.fail("unexpected native read")
        native.k.WriteFile = lambda *args: self.fail("unexpected native write")

        def close(handle):
            raise OSError("synthetic close exception details must not escape")

        def inspect(handle, template):
            if partial_open:
                raise proof.Refused("synthetic_inspection_refused")
            native._sizes[(1, 20)] = 8193
            return replace(template, directory=False, handle_id=(1, 20), protected_dacl=True)

        native.k.CloseHandle = close
        native._inspect = inspect

        class Bridge(FixtureFacade):
            @property
            def cleanup_confirmed(self):
                return native.cleanup_confirmed

        facade = Bridge(Clock())
        facade.open_source = native.open_source
        facade.set_dispatch_guard = native.set_dispatch_guard
        receipt = candidate.run_preparation(facade, facade.clock)
        self.assertIs(native.cleanup_confirmed, False)
        self.assertIs(receipt.cleanup_confirmed, False)
        self.assertIs(receipt.delivered, False)
        self.assertEqual(receipt.outcome, "source_candidate_cleanup_unconfirmed")
        self.assertEqual((receipt.credential_reads, receipt.writes, receipt.flushes), (0, 0, 0))
        self.assertEqual(facade.effects("read"), [])
        self.assertEqual(facade.effects("write"), [])
        self.assertEqual(native._handles, {})
        self.assertNotIn(((1, 20),), facade.effects("close"))

    def test_partial_open_throwing_close_propagates_cleanup_uncertainty(self) -> None:
        self.cleanup_failure_case(partial_open=True)

    def test_internal_oversize_source_throwing_close_prevents_executor_success(self) -> None:
        self.cleanup_failure_case(partial_open=False)

    def test_ordinary_bindings_and_real_paths_refuse_before_native_dispatch(self) -> None:
        with self.assertRaises(proof.Refused):
            candidate.NativeFacade(object(), object(), USER)
        native = self.adapter()
        with self.assertRaises(proof.Refused):
            native._open("C:\\outside_fixture\\input.bin", 1, 1, 1, 3)

    def test_creation_forwards_protected_descriptor_and_exclusive_native_parameters(self) -> None:
        native = self.adapter()
        descriptor = ctypes.create_string_buffer(64)
        calls = []

        def convert(sddl, revision, output, size):
            self.assertIn("D:P", sddl)
            output._obj.value = ctypes.addressof(descriptor)
            return 1

        def create(path, access, share, security, disposition, flags, template):
            attrs = security._obj
            calls.append((path, access, share, disposition, flags))
            self.assertEqual(attrs.lpSecurityDescriptor, ctypes.addressof(descriptor))
            self.assertEqual(attrs.bInheritHandle, 0)
            return 101

        native.a.ConvertStringSecurityDescriptorToSecurityDescriptorW = convert
        native.k.CreateFileW = create
        native.k.LocalFree = lambda pointer: None
        native.k.CloseHandle = lambda handle: 1
        native._inspect = lambda handle, template: replace(
            template, directory=False, protected_dacl=True, handle_id=(1, 100)
        )
        security = candidate.CreationSecurity(
            USER,
            tuple(
                proof.Ace("allow", sid, 0x001F01FF)
                for sid in (USER, proof.SYSTEM, proof.ADMINISTRATORS)
            ),
        )
        result = native.create_new(candidate.DESTINATION, security, 0x40020080, 0, 0x200000)
        self.assertEqual(calls, [(candidate.DESTINATION, 0x40020080, 0, 1, 0x200000)])
        self.assertIs(result.creation_security_at_open, True)
        self.assertEqual(native._handles[result.handle_id][0], 101)

    def test_native_read_admits_after_metadata_and_attempt_is_never_retried(self) -> None:
        native = self.adapter()
        node = proof.Node(candidate.SOURCE, USER, (), directory=False, handle_id=(1, 20))
        native._handles[node.handle_id] = (101, node)
        events = []
        info = candidate.FILE_INFORMATION()
        info.size_low = len(candidate.SYNTHETIC_BYTES)

        def inspect(handle):
            events.append("metadata")
            return info

        def read(handle, data, maximum, count, overlapped):
            events.append("read")
            self.assertEqual((handle, maximum, overlapped), (101, 8192, None))
            ctypes.memmove(data, candidate.SYNTHETIC_BYTES, len(candidate.SYNTHETIC_BYTES))
            count._obj.value = len(candidate.SYNTHETIC_BYTES)
            return 1

        native._info = inspect
        native._dispatch_guard = lambda: events.append("admit")
        native.k.ReadFile = read
        self.assertEqual(native.read(node.handle_id, 8192), candidate.SYNTHETIC_BYTES)
        self.assertEqual(events, ["metadata", "admit", "read", "metadata"])
        with self.assertRaises(proof.Refused):
            native.read(node.handle_id, 8192)
        self.assertEqual(events.count("read"), 1)

    def test_security_is_queried_by_handle_and_unknown_ace_form_refuses(self) -> None:
        native = self.adapter()
        owner = ctypes.create_string_buffer(32)
        descriptor = ctypes.create_string_buffer(32)
        dacl = ctypes.create_string_buffer(8)
        sid_text = ctypes.create_unicode_buffer(USER)
        ace = ctypes.create_string_buffer(16)
        ace[0] = b"\x02"  # unsupported ACE type, never interpreted as an allow
        calls = []

        def security(handle, kind, requested, owner_out, group, dacl_out, sacl, sd_out):
            calls.append((handle, kind, requested))
            owner_out._obj.value = ctypes.addressof(owner)
            dacl_out._obj.value = ctypes.addressof(dacl)
            sd_out._obj.value = ctypes.addressof(descriptor)
            return 0

        def sid(pointer, output):
            output._obj.value = ctypes.addressof(sid_text)
            return 1

        def control(pointer, flags, revision):
            flags._obj.value = 0x1000
            return 1

        def getace(pointer, index, output):
            output._obj.value = ctypes.addressof(ace)
            return 1

        native.a.GetSecurityInfo = security
        native.a.ConvertSidToStringSidW = sid
        native.a.GetSecurityDescriptorControl = control
        native.a.GetAce = getace
        native.k.LocalFree = lambda pointer: None
        self.assertEqual(native._security(101), (USER, (), True))
        self.assertEqual(calls, [(101, 1, 5)])
        ctypes.c_ushort.from_buffer(dacl, 4).value = 1
        with self.assertRaises(proof.Refused):
            native._security(101)

    def test_descriptor_conversion_expiry_prevents_createfile(self) -> None:
        native = self.adapter()
        events = []
        descriptor = ctypes.create_string_buffer(32)

        def convert(text, revision, output, size):
            events.append("descriptor")
            output._obj.value = ctypes.addressof(descriptor)
            return 1

        def guard():
            events.append("admit")
            raise proof.Refused("window_closed")

        native.a.ConvertStringSecurityDescriptorToSecurityDescriptorW = convert
        native.k.LocalFree = lambda pointer: None
        native.k.CreateFileW = lambda *args: self.fail("CreateFileW dispatched after expiry")
        native._dispatch_guard = guard
        security = candidate.CreationSecurity(
            USER,
            tuple(
                proof.Ace("allow", sid, 0x001F01FF)
                for sid in (USER, proof.SYSTEM, proof.ADMINISTRATORS)
            ),
        )
        with self.assertRaises(proof.Refused):
            native.create_new(candidate.DESTINATION, security, 0x40020080, 0, 0x200000)
        self.assertEqual(events, ["descriptor", "admit"])

    def test_native_internal_metadata_expiry_prevents_readfile(self) -> None:
        native = self.adapter()
        node = proof.Node(candidate.SOURCE, USER, (), directory=False, handle_id=(1, 20))
        native._handles[node.handle_id] = (101, node)
        info = candidate.FILE_INFORMATION()
        info.size_low = 10
        self.clock = Clock()

        def inspect(handle):
            self.clock.expired = True
            return info

        def guard():
            proof.Window(1000, 1900, 0, 1000, 0).before_dispatch(*self.clock())

        native._info = inspect
        native._dispatch_guard = guard
        native.k.ReadFile = lambda *args: self.fail("ReadFile dispatched after expiry")
        with self.assertRaises(proof.Refused):
            native.read(node.handle_id, 8192)
        self.assertIs(native._read_attempted, True)

    def test_native_write_and_flush_guard_before_dispatch_and_refuse_failed_completion(
        self,
    ) -> None:
        native = self.adapter()
        node = proof.Node(candidate.DESTINATION, USER, (), directory=False, handle_id=(1, 21))
        native._handles[node.handle_id] = (102, node)
        events = []
        native._dispatch_guard = lambda: events.append("admit")
        native.k.WriteFile = lambda *args: events.append("write") or 0
        native.k.FlushFileBuffers = lambda *args: events.append("flush") or 0
        with self.assertRaises(proof.Refused):
            native.write(node.handle_id, b"fixture")
        with self.assertRaises(proof.Refused):
            native.flush(node.handle_id)
        self.assertEqual(events, ["admit", "write", "admit", "flush"])


if __name__ == "__main__":
    unittest.main()
