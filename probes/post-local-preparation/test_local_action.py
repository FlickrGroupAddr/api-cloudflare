"""Deferred factory tests: injected synthetic identity, handles and APIs only."""

from __future__ import annotations

import contextlib
import ctypes
import io
import json
import unittest
from dataclasses import replace
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest.mock import patch

import bounded_local_delivery_path_proof as proof
from binding import FIXED_PACKET, ProcessIdentity
from local_action import (
    NATIVE_MARKER_NAMES,
    REVIEWED,
    Admission,
    AdmittedLibrary,
    BoundFacade,
    HeldParents,
    LocalPacket,
    ParentChain,
    current_source_pins,
    live_factory,
    main,
    packet_fingerprint,
    prepare_local,
    role_chains,
    windows_identity,
)
from role_policy import RolePolicy, role_path
from test_0161_local_preparation_candidate import Clock, FixtureFacade


def parent_chain(parent: str, private_from: int | None = 2) -> ParentChain:
    windows = PureWindowsPath(parent)
    return ParentChain(tuple(str(p) for p in reversed(windows.parents)) + (parent,), private_from)


def packet() -> LocalPacket:
    source = r"C:\synthetic\retained\credential-delivery"
    destination = r"C:\synthetic\.coordination-runs\post\private"
    native = r"C:\Temp\FGA-group-post-v1"
    records = source + r"\draft"
    return LocalPacket(
        run_identity=FIXED_PACKET.run_identity,
        process=ProcessIdentity(),
        source_parents=parent_chain(source),
        destination_parents=parent_chain(destination),
        native_parents=(parent_chain(native),) * 7,
        claim_parents=parent_chain(records),
        receipt_parents=parent_chain(records),
        source=source + r"\operator-token.txt",
        destination=destination + r"\operator-token.txt",
        source_sha2_256=FIXED_PACKET.source_sha2_256,
        markers=tuple(native + "\\" + name for name in NATIVE_MARKER_NAMES),
        claim=records + r"\local.claim",
        receipt=records + r"\local.receipt",
        start=FIXED_PACKET.start,
        deadline=FIXED_PACKET.deadline,
        source_not_after=2000.0,
        integration_pins=current_source_pins(),
        localConsent=True,
    )


class LocalFacade(FixtureFacade):
    def __init__(self, clock: Clock):
        super().__init__(clock)
        self.existing: set[str] = set()
        self.contents: dict[str, bytes] = {}
        self.cleanup_confirmed = True
        self.failed_path: str | None = None
        self.short_path: str | None = None
        self.admission = lambda: None
        self.directory_changes: dict[str, dict] = {}
        self.unknown_markers: set[str] = set()
        self.expire_path: str | None = None
        self.duplicate_directory: str | None = None

    def open_directory(self, path, access, share, flags):
        node = super().open_directory(path, access, share, flags)
        changes = self.directory_changes.get(path, {})
        if path == self.duplicate_directory:
            changes = {**changes, "handle_id": (1, 11)}
        modified = replace(node, **changes)
        # Keep the fixture's owner ledger even for an injected bad observation.
        if path == self.expire_path:
            self.clock.expired = True
        return modified

    def open_source(self, path, access, share, flags):
        self.record("source", path, access, share, flags)
        self.next_identity += 1
        node = replace(
            proof.Node(
                path,
                self.current_user_sid,
                (),
                directory=False,
                desired_access=access,
                share_mode=share,
                flags=flags,
                handle_id=(1, self.next_identity + 1000),
                protected_dacl=True,
            ),
            **self.bad_source,
        )
        self.nodes[node.handle_id] = node
        return node

    def marker_absent(self, path: str) -> bool:
        self.record("marker", path)
        if path in self.unknown_markers:
            raise OSError("synthetic marker observation unknown")
        return path not in self.existing

    def create_new(self, path: str, security: object, access: int, share: int, flags: int):
        self.record("create", path)
        self.admission()
        if path in self.existing:
            raise OSError("synthetic existing output")
        self.existing.add(path)
        self.next_identity += 1
        node = proof.Node(
            path,
            self.current_user_sid,
            (),
            directory=False,
            desired_access=access,
            share_mode=share,
            flags=flags,
            protected_dacl=True,
            disposition=proof.CREATE_NEW,
            creation_security_at_open=True,
            handle_id=(1, self.next_identity + 100),
        )
        self.nodes[node.handle_id] = node
        return replace(node, **self.bad_output)

    def write(self, handle_id: tuple[int, int], raw: bytes) -> int:
        path = self.nodes[handle_id].path
        self.record("write", path)
        self.admission()
        self.contents[path] = raw
        if path == self.failed_path:
            raise OSError("synthetic unknown write")
        return len(raw) - 1 if path == self.short_path else len(raw)

    def close_all(self):
        for node in reversed(tuple(self.nodes.values())):
            try:
                self.close(node.handle_id)
            except Exception:
                self.cleanup_confirmed = False
            finally:
                self.nodes.pop(node.handle_id, None)


class LocalActionCase(unittest.TestCase):
    def setUp(self):
        self.packet = packet()
        self.clock = Clock()
        self.facade = LocalFacade(self.clock)
        self.identity = self.packet.process
        self.factories = 0

    def factory(self, exact, admit):
        self.assertEqual(exact, self.packet)
        self.factories += 1
        self.facade.admission = admit
        return self.facade

    def run_local(self, exact=None, pin=None):
        exact = exact or self.packet
        return prepare_local(
            exact, pin or packet_fingerprint(exact), lambda: self.identity, self.factory, self.clock
        )


class LocalActionTests(LocalActionCase):
    def test_complete_exact_custody_source_and_private_receipt(self):
        result = self.run_local()
        self.assertEqual(result.outcome, "local_preparation_complete_no_run_authority")
        self.assertTrue(result.claim_confirmed and result.delivered and result.receipt_confirmed)
        self.assertEqual(result.credential_reads, 1)
        self.assertFalse(result.actionReady or result.nativeConsent)
        self.assertEqual(self.facade.contents[self.packet.destination], REVIEWED.SYNTHETIC_BYTES)
        saved = json.loads(self.facade.contents[self.packet.receipt])
        self.assertFalse(saved["cleanup_confirmed"])
        self.assertEqual(len(self.facade.effects("marker")), 10)

    def test_false_consent_closed_scope_and_bad_pin_do_not_construct_facade(self):
        for changes in (
            {"localConsent": False},
            {"nativeConsent": True},
            {"actionReady": True},
            {"run_identity": "bad"},
            {"source_parents": replace(self.packet.source_parents, private_from=True)},
            {"source_sha2_256": "bad"},
            {"markers": self.packet.markers[:-1]},
            {"destination": self.packet.source},
            {"receipt": self.packet.claim},
            {"deadline": 2000.0},
            {"source_not_after": 1900.0},
            {"integration_pins": ()},
            {
                "source_parents": replace(
                    self.packet.source_parents, roots=("C:\\", self.packet.source_parents.roots[-1])
                )
            },
        ):
            with self.subTest(changes=changes):
                result = self.run_local(replace(self.packet, **changes))
                self.assertEqual(result.credential_reads, 0)
                self.assertEqual(self.factories, 0)
        self.assertEqual(self.run_local(pin="0" * 64).outcome, "exact_packet_refused")

    def test_actual_process_generation_sid_pid_and_image_pin_are_bound(self):
        for changes in (
            {"started": "other"},
            {"process_id": 999},
            {"user_sid": "S-1-5-21-1-2-3-4"},
            {"executable_sha2_256": "0" * 64},
        ):
            with self.subTest(changes=changes):
                self.identity = replace(self.packet.process, **changes)
                self.assertEqual(self.run_local().outcome, "process_identity_refused")
                self.assertEqual(self.factories, 0)

    def test_initial_expiry_precedes_identity_and_factory(self):
        self.clock.expired = True
        self.assertEqual(self.run_local().outcome, "window_closed")
        self.assertEqual(self.factories, 0)

    def test_any_spent_marker_prevents_claim_and_read(self):
        for marker in self.packet.markers:
            with self.subTest(marker=marker):
                self.setUp()
                self.facade.existing.add(marker)
                result = self.run_local()
                self.assertEqual(result.outcome, "marker_not_fresh")
                self.assertFalse(result.claim_attempted)
                self.assertEqual(result.credential_reads, 0)

    def test_claim_short_or_unknown_never_reads_and_stays_present(self):
        for kind in ("short_path", "failed_path"):
            with self.subTest(kind=kind):
                self.setUp()
                setattr(self.facade, kind, self.packet.claim)
                result = self.run_local()
                self.assertTrue(result.claim_attempted)
                self.assertFalse(result.claim_confirmed)
                self.assertEqual(result.credential_reads, 0)
                self.assertIn(self.packet.claim, self.facade.existing)
                self.assertEqual(self.run_local().outcome, "marker_not_fresh")

    def test_existing_destination_refuses_before_source_read(self):
        self.facade.existing.add(self.packet.destination)
        result = self.run_local()
        self.assertFalse(result.claim_attempted or result.destination_attempted)
        self.assertEqual(result.credential_reads, 0)

    def test_source_mismatch_and_read_failure_never_write_destination(self):
        for kind in ("fingerprint", "read"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == "fingerprint":
                    self.facade.read_value = b"wrong synthetic input"
                else:
                    self.facade.fail_at = "read"
                result = self.run_local()
                self.assertEqual(result.credential_reads, 1)
                self.assertFalse(result.delivered)
                self.assertNotIn(self.packet.destination, self.facade.contents)

    def test_handle_identity_or_security_change_refuses_before_delivery(self):
        for change in ({"handle_id": (1, 999)}, {"reparse": True}, {"aces": None}):
            with self.subTest(change=change):
                self.setUp()
                self.facade.bad_inspection = change
                result = self.run_local()
                self.assertFalse(result.delivered)
                self.assertEqual(result.credential_reads, 0)

    def test_receipt_failure_retains_actual_delivery_observation_without_replay(self):
        self.facade.failed_path = self.packet.receipt
        result = self.run_local()
        self.assertTrue(result.delivered and result.receipt_attempted)
        self.assertFalse(result.receipt_confirmed)
        self.assertEqual(self.run_local().outcome, "marker_not_fresh")

    def test_cleanup_uncertainty_does_not_claim_success(self):
        self.facade.fail_at = "close"
        result = self.run_local()
        self.assertFalse(result.cleanup_confirmed or result.delivered)
        self.assertTrue(result.destination_attempted)
        self.assertEqual(result.outcome, "cleanup_unconfirmed_no_replay")

    def test_deadline_after_claim_create_prevents_source_read(self):
        self.facade.expire_after = "create"
        result = self.run_local()
        self.assertTrue(result.claim_attempted)
        self.assertEqual(result.credential_reads, 0)
        self.assertFalse(result.claim_confirmed)

    def test_default_entry_never_loads_dll_and_invalid_factory_packet_does_not_load(self):
        with patch("local_action.ctypes.WinDLL", side_effect=AssertionError("no DLL load")):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 2)
            self.assertFalse(json.loads(output.getvalue())["actionReady"])
            with self.assertRaises(ValueError):
                denied = replace(self.packet, localConsent=False)
                live_factory(denied, packet_fingerprint(denied), self.clock)

    def test_factory_route_uses_only_injected_libraries_and_actual_identity_provider(self):
        class Function:
            argtypes = None
            restype = None

        class Library:
            def __getattr__(self, name):
                function = Function()
                setattr(self, name, function)
                return function

        def construct(kernel, advapi, exact, admission):
            self.facade.admission = admission
            return self.facade

        with (
            patch("local_action.ctypes.WinDLL", side_effect=lambda *a, **k: Library()) as dll,
            patch("local_action.BoundFacade", side_effect=construct),
            patch("local_action.windows_identity", return_value=self.packet.process) as identity,
        ):
            result = live_factory(self.packet, packet_fingerprint(self.packet), self.clock)
        self.assertTrue(result.delivered)
        self.assertEqual(dll.call_count, 2)
        identity.assert_called_once()
        with patch("local_action.ctypes.WinDLL", side_effect=AssertionError("no replay load")):
            repeated = live_factory(self.packet, packet_fingerprint(self.packet), self.clock)
        self.assertEqual(repeated.outcome, "no_replay")

    def test_expired_live_factory_does_not_load_and_consumes_the_invocation(self):
        expired = replace(self.packet, run_identity="synthetic0161-expired-only")
        self.clock.expired = True
        with patch("local_action.ctypes.WinDLL", side_effect=AssertionError("no expired load")):
            with self.assertRaisesRegex(ValueError, "window_closed"):
                live_factory(expired, packet_fingerprint(expired), self.clock)
            self.assertEqual(
                live_factory(expired, packet_fingerprint(expired), self.clock).outcome, "no_replay"
            )


class RoleTopologyTests(LocalActionCase):
    def test_documented_public_topology_passes_with_invented_observations(self):
        workspace = r"C:\Users\TDO-XPS15-2024\Documents\ChatGPT\FGA"
        source = workspace + (
            r"\private-evidence\0134\publisher-expiry-oct18-staging"
            r"\credential-delivery"
        )
        caller = workspace + (
            r"\.coordination-runs\renewed-group-post"
            r"\0a8b92d40ed1466fa7de82c1\private"
        )
        records = source + r"\0161-private-draft"
        # Strings are public topology evidence only. No path resolver, lookup,
        # native facade or actual process identity is called by this fixture.
        self.packet = replace(
            packet(),
            source=source + r"\operator-token.txt",
            destination=caller + r"\operator-token.txt",
            source_parents=parent_chain(source, 7),
            destination_parents=parent_chain(caller, 7),
            claim=records + r"\new-invented.claim",
            receipt=records + r"\new-invented.receipt",
            claim_parents=parent_chain(records, 7),
            receipt_parents=parent_chain(records, 7),
        )
        result = self.run_local()
        self.assertTrue(result.delivered and result.cleanup_confirmed)
        opened = [args[0] for args in self.facade.effects("directory")]
        expected = {p for _, chain, _ in role_chains(self.packet) for p in chain.roots}
        self.assertEqual(set(opened), expected)
        self.assertEqual(len(opened), len(expected))
        closed = [args[0] for args in self.facade.effects("close")]
        self.assertEqual(len(closed), len(set(closed)))
        self.assertEqual(len(closed), len(expected) + 4)
        self.assertFalse(result.actionReady or result.nativeConsent)

    def test_cached_shared_prefix_retains_identity_and_balances_references(self):
        facade = LocalFacade(Clock())
        held = HeldParents(
            facade, RolePolicy(ProcessIdentity().user_sid, proof.TRUSTEDINSTALLER), lambda: None
        )
        for leaf, parents, _ in role_chains(self.packet):
            held.acquire(leaf, parents)
        self.assertEqual(held.references["C:\\"], 11)
        self.assertEqual(len(facade.effects("directory")), len(held.nodes))
        self.assertEqual(held.chains[self.packet.source][0].handle_id, held.nodes["C:\\"].handle_id)
        held.release()
        self.assertEqual(held.references, {})
        self.assertEqual(facade.effects("close"), [])
        facade.close_all()
        closed = [args[0] for args in facade.effects("close")]
        self.assertEqual(len(closed), len(set(closed)))

    def test_wrong_role_chains_and_file_directory_collisions_precede_callbacks(self):
        for changes in (
            {"destination_parents": self.packet.source_parents},
            {"claim_parents": self.packet.destination_parents},
            {"receipt_parents": self.packet.source_parents},
            {"native_parents": (self.packet.source_parents,) * 7},
            {
                "source": self.packet.destination_parents.roots[-1],
                "source_parents": parent_chain(self.packet.destination_parents.roots[-2]),
            },
            {"native_parents": (replace(self.packet.native_parents[0], private_from=None),) * 7},
        ):
            with self.subTest(changes=changes):
                self.setUp()
                result = self.run_local(replace(self.packet, **changes))
                self.assertEqual(self.factories, 0)
                self.assertEqual(result.credential_reads, 0)

    def test_all_native_names_required_and_records_cannot_substitute(self):
        for markers in (
            self.packet.markers[:-1],
            (*self.packet.markers[:-1], self.packet.markers[0]),
            (*self.packet.markers[:-1], self.packet.claim),
            (*self.packet.markers[:-1], self.packet.markers[-1] + ".other"),
            tuple(reversed(self.packet.markers)),
        ):
            with self.subTest(markers=markers):
                result = self.run_local(replace(self.packet, markers=markers))
                self.assertEqual(self.factories, 0)
                self.assertEqual(result.credential_reads, 0)
        for name in ("claim", "receipt", "destination", "source"):
            result = self.run_local(replace(self.packet, **{name: self.packet.markers[0]}))
            self.assertEqual(self.factories, 0)
            self.assertFalse(result.claim_attempted)

    def test_shared_prefix_case_alias_and_cross_branch_object_alias_refuse(self):
        renamed = replace(
            self.packet.destination_parents,
            roots=tuple(
                p.replace("synthetic", "Synthetic") for p in self.packet.destination_parents.roots
            ),
        )
        exact = replace(
            self.packet,
            destination_parents=renamed,
            destination=self.packet.destination.replace("synthetic", "Synthetic"),
        )
        self.assertEqual(self.run_local(exact).outcome, "shared_parent_spelling_refused")
        self.assertEqual(self.factories, 0)
        self.facade.duplicate_directory = self.packet.destination_parents.roots[-1]
        result = self.run_local()
        self.assertEqual(result.outcome, "cross_role_object_alias_refused")
        self.assertFalse(result.claim_attempted)
        self.assertEqual(result.credential_reads, 0)

    def test_each_role_branch_reparse_acl_share_volume_or_unknown_refuses(self):
        branches = (
            self.packet.source_parents,
            self.packet.destination_parents,
            self.packet.native_parents[0],
            self.packet.claim_parents,
        )
        for parents in branches:
            for change in (
                {"reparse": True},
                {"aces": None},
                {"protected_dacl": False},
                {"share_mode": 3},
                {"owner": "S-1-1-0"},
                {"handle_id": (2, 1000)},
                {"held": False},
                {"aces": (proof.Ace("allow", "S-1-1-0", 1),)},
            ):
                with self.subTest(branch=parents.roots[-1], change=change):
                    self.setUp()
                    self.facade.directory_changes[parents.roots[-1]] = change
                    result = self.run_local()
                    self.assertFalse(result.claim_attempted or result.delivered)
                    self.assertEqual(result.credential_reads, 0)
                    self.assertNotEqual(
                        result.outcome, "local_preparation_complete_no_run_authority"
                    )

    def test_marker_and_output_present_or_unknown_prevents_all_effects(self):
        for path in (
            *self.packet.markers,
            self.packet.claim,
            self.packet.receipt,
            self.packet.destination,
        ):
            for unknown in (False, True):
                with self.subTest(path=path, unknown=unknown):
                    self.setUp()
                    (self.facade.unknown_markers if unknown else self.facade.existing).add(path)
                    result = self.run_local()
                    self.assertFalse(result.claim_attempted or result.destination_attempted)
                    self.assertEqual(result.credential_reads, 0)
                    self.assertEqual(self.facade.effects("create"), [])

    def test_deadline_across_every_branch_still_closes_each_owned_handle_once(self):
        paths = {
            self.packet.source_parents.roots[-1],
            self.packet.destination_parents.roots[-1],
            self.packet.native_parents[0].roots[-1],
            self.packet.claim_parents.roots[-1],
        }
        for path in paths:
            with self.subTest(path=path):
                self.setUp()
                self.facade.expire_path = path
                result = self.run_local()
                self.assertEqual(result.outcome, "window_closed")
                self.assertFalse(result.claim_attempted)
                self.assertEqual(result.credential_reads, 0)
                closed = [args[0] for args in self.facade.effects("close")]
                self.assertEqual(len(closed), len(set(closed)))
                self.assertEqual(self.facade.nodes, {})

    def test_partial_chain_failure_and_shared_prefix_change_cleanup_without_read(self):
        for change in (
            {"path": r"C:\substituted"},
            {"handle_id": (1, 999)},
            {"owner": "S-1-1-0"},
            {"protected_dacl": False},
        ):
            with self.subTest(change=change):
                self.setUp()
                # Every branch revisits C: through its same retained handle.
                self.facade.bad_inspection = change
                result = self.run_local()
                self.assertFalse(result.claim_attempted)
                self.assertEqual(result.credential_reads, 0)
                self.assertEqual(self.facade.nodes, {})
        self.setUp()
        self.facade.fail_at = "directory"
        self.assertFalse(self.run_local().delivered)

    def test_destination_and_receipt_partial_writes_preserve_claim_and_never_reread(self):
        for field in ("destination", "receipt"):
            for failure in ("short_path", "failed_path"):
                with self.subTest(field=field, failure=failure):
                    self.setUp()
                    path = getattr(self.packet, field)
                    setattr(self.facade, failure, path)
                    result = self.run_local()
                    self.assertEqual(result.credential_reads, 1)
                    self.assertTrue(result.claim_confirmed)
                    self.assertIn(self.packet.claim, self.facade.existing)
                    self.assertIn(path, self.facade.existing)
                    self.assertFalse(result.receipt_confirmed)
                    if field == "destination":
                        self.assertFalse(result.delivered)
                    self.assertEqual(self.run_local().outcome, "marker_not_fresh")
                    self.assertEqual(len(self.facade.effects("read")), 1)

    def test_role_private_boundaries_are_requalified_when_shared(self):
        # A source-role ancestor can allow an untrusted read above its private
        # boundary. The SAME cached node must refuse a stricter records role.
        shared = self.packet.source_parents.roots[-2]
        source_parents = replace(self.packet.source_parents, private_from=3)
        self.packet = replace(self.packet, source_parents=source_parents)
        self.facade.directory_changes[shared] = {"aces": (proof.Ace("allow", "S-1-1-0", 1),)}
        original = self.facade.open_directory

        def retain(path, access, share, flags):
            node = original(path, access, share, flags)
            self.facade.nodes[node.handle_id] = node
            return node

        self.facade.open_directory = retain
        result = self.run_local()
        self.assertFalse(result.claim_attempted)
        self.assertEqual(result.outcome, "private_access_refused")
        self.assertEqual(result.credential_reads, 0)

    def test_local_policy_has_exact_hidden_component_delta_only(self):
        good = r"C:\invented\.coordination-runs\post\private"
        self.assertEqual(str(role_path(good)), good)
        for bad in (
            r"C:\invented\.other\post",
            r"C:\invented\.\post",
            r"C:\invented\..\post",
            good + ".",
            good + " ",
            good.replace(".coordination-runs", ".Coordination-runs"),
            good.replace(".coordination-runs", "..coordination-runs"),
            good.replace(".coordination-runs", ".coordination-runs."),
            good.replace(".coordination-runs", ".coordination-runs "),
            good.replace(".coordination-runs", ".coordination-runs:ads"),
            r"\\?\C:\invented\.coordination-runs",
            r"\\host\share\file",
            r"C:\invented\CON",
            r"C:\invented\\post",
            "C:/invented/post",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                role_path(bad)


class BoundNativeTests(unittest.TestCase):
    def facade(self):
        native = BoundFacade.__new__(BoundFacade)
        native.packet = packet()
        native.k, native.a = SimpleNamespace(), SimpleNamespace()
        native.current_user_sid = ProcessIdentity().user_sid
        native._handles, native._sizes = {}, {}
        native._read_attempted = False
        native._dispatch_guard = lambda: None
        native.cleanup_confirmed = True
        return native

    def test_marker_only_missing_leaf_is_fresh(self):
        native = self.facade()
        native.k.CreateFileW = lambda *args: ctypes.c_void_p(-1).value
        for error in (2, 3, 5, 32):
            with patch("local_action.ctypes.get_last_error", return_value=error):
                if error == 2:
                    self.assertTrue(native.marker_absent(packet().claim))
                else:
                    with self.assertRaises(ValueError):
                        native.marker_absent(packet().claim)

    def test_marker_handle_close_uncertainty_is_not_fresh(self):
        native = self.facade()
        native.k.CreateFileW = lambda *args: 101
        native.k.CloseHandle = lambda _: False
        with self.assertRaisesRegex(ValueError, "marker_close_unconfirmed"):
            native.marker_absent(packet().claim)
        self.assertFalse(native.cleanup_confirmed)

    def test_exact_paths_and_create_new_are_enforced(self):
        native = self.facade()
        with self.assertRaises(ValueError):
            native._allowed("C:\\outside\\input.bin")
        calls = []
        native._open = lambda *args: calls.append(args)
        native.create_new(packet().claim, "synthetic security", 0x40020080, 0, 0x200000)
        self.assertEqual(calls[0][4], proof.CREATE_NEW)
        self.assertEqual(calls[0][0], packet().claim)
        with self.assertRaises(ValueError):
            native.create_new(packet().source, "synthetic security", 0x40020080, 0, 0x200000)

    def test_single_read_uses_held_source_and_checks_metadata(self):
        native = self.facade()
        source = proof.Node(
            packet().source, ProcessIdentity().user_sid, (), directory=False, handle_id=(1, 20)
        )
        native._handles[source.handle_id] = (101, source)
        info = REVIEWED.FILE_INFORMATION()
        info.size_low = len(REVIEWED.SYNTHETIC_BYTES)
        native._info = lambda _: info

        def read(handle, output, maximum, count, overlap):
            ctypes.memmove(output, REVIEWED.SYNTHETIC_BYTES, len(REVIEWED.SYNTHETIC_BYTES))
            count._obj.value = len(REVIEWED.SYNTHETIC_BYTES)
            return True

        native.k.ReadFile = read
        self.assertEqual(native.read(source.handle_id, 8192), REVIEWED.SYNTHETIC_BYTES)
        with self.assertRaises(ValueError):
            native.read(source.handle_id, 8192)

    def test_process_token_failure_closes_owned_handle(self):
        calls = []
        kernel = SimpleNamespace(
            GetCurrentProcess=lambda: 101, CloseHandle=lambda h: calls.append("close") or True
        )

        def open_token(process, access, output):
            output._obj.value = 102
            return True

        advapi = SimpleNamespace(
            OpenProcessToken=open_token, GetTokenInformation=lambda *args: False
        )
        with self.assertRaisesRegex(ValueError, "process_token_bound_refused"):
            windows_identity(kernel, advapi, lambda: None)
        self.assertEqual(calls, ["close"])

    def test_process_identity_uses_owned_token_sid_generation_and_executable_pin(self):
        sid = ctypes.create_unicode_buffer(ProcessIdentity().user_sid)
        sid_memory = ctypes.create_string_buffer(32)
        calls = []

        def open_token(process, access, output):
            self.assertEqual((process, access), (101, 8))
            output._obj.value = 102
            return True

        def token_info(token, kind, output, size, needed):
            needed._obj.value = 32
            if output is None:
                return False
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(sid_memory)
            return True

        def convert(pointer, output):
            self.assertEqual(pointer, ctypes.addressof(sid_memory))
            output._obj.value = ctypes.addressof(sid)
            return True

        def times(process, created, exited, kernel, user):
            created._obj.dwLowDateTime = 123
            return True

        def image(module, output, maximum):
            output.value = "C:\\synthetic\\python.exe"
            return len(output.value)

        kernel = SimpleNamespace(
            GetCurrentProcess=lambda: 101,
            GetCurrentProcessId=lambda: 161,
            GetProcessTimes=times,
            GetModuleFileNameW=image,
            LocalFree=lambda p: calls.append("free"),
            CloseHandle=lambda h: calls.append("close") or True,
        )
        advapi = SimpleNamespace(
            OpenProcessToken=open_token,
            GetTokenInformation=token_info,
            ConvertSidToStringSidW=convert,
        )
        with patch("local_action.Path.open", return_value=io.BytesIO(b"synthetic-python")):
            result = windows_identity(kernel, advapi, lambda: None)
        self.assertEqual(result, replace(ProcessIdentity(), started="123"))
        self.assertEqual(calls, ["free", "close"])


class DeadlineContinuityTests(unittest.TestCase):
    def test_expired_identity_token_cleanup_uncertainty_is_reported(self):
        for throws in (False, True):
            with self.subTest(throws=throws):
                self.check_expired_cleanup(throws)

    def check_expired_cleanup(self, throws):
        exact = packet()
        expired = False
        cleanup = []

        def clock():
            return (1900.0, 901.0) if expired else (1000.0, 1.0)

        admission = Admission(exact, clock)

        def open_token(process, access, output):
            nonlocal expired
            output._obj.value = 102
            expired = True
            return True

        def close(token):
            cleanup.append("close")
            if throws:
                raise OSError("synthetic unknown close")
            return False

        kernel = SimpleNamespace(GetCurrentProcess=lambda: 101, CloseHandle=close)
        advapi = SimpleNamespace(OpenProcessToken=open_token)
        result = prepare_local(
            exact,
            packet_fingerprint(exact),
            lambda: windows_identity(kernel, advapi, admission),
            lambda *args: self.fail("no facade after expired identity"),
            clock,
            admission,
        )
        self.assertEqual(cleanup, ["close"])
        self.assertFalse(result.cleanup_confirmed)
        self.assertEqual(result.outcome, "process_token_close_unconfirmed")

    def test_initial_monotonic_history_is_not_reset_before_setup(self):
        exact = replace(packet(), run_identity="synthetic0161-clock-rollback")
        observations = iter(((1000.0, 100.0),))

        def clock():
            return next(observations, (1000.0, 10.0))

        with patch("local_action.ctypes.WinDLL", side_effect=AssertionError("no DLL")):
            with self.assertRaisesRegex(ValueError, "window_closed"):
                live_factory(exact, packet_fingerprint(exact), clock)

    def test_expiry_or_monotonic_rollback_during_dll_setup_stops_next_dispatch(self):
        for case in ("utc", "elapsed", "rollback"):
            with self.subTest(case=case):
                exact = replace(packet(), run_identity="synthetic0161-setup-" + case)
                observation = [1000.0, 100.0]

                def load(*args, observed=observation, stage=case, **kwargs):
                    observed[:] = {
                        "utc": [1900.0, 101.0],
                        "elapsed": [1001.0, 1000.0],
                        "rollback": [1000.0, 10.0],
                    }[stage]
                    return SimpleNamespace()

                with patch("local_action.ctypes.WinDLL", side_effect=load) as libraries:
                    with self.assertRaisesRegex(ValueError, "window_closed"):
                        live_factory(
                            exact,
                            packet_fingerprint(exact),
                            lambda observed=observation: (observed[0], observed[1]),
                        )
                self.assertEqual(libraries.call_count, 1)

    def test_prepare_uses_existing_admission_history(self):
        exact = packet()
        observation = [1000.0, 100.0]

        def clock():
            return observation[0], observation[1]

        admission = Admission(exact, clock)
        observation[1] = 10.0
        result = prepare_local(
            exact,
            packet_fingerprint(exact),
            lambda: self.fail("no identity after rollback"),
            lambda *args: self.fail("no facade after rollback"),
            clock,
            admission,
        )
        self.assertEqual(result.outcome, "window_closed")

    def test_identity_expiry_stops_every_later_dispatch_but_releases_resources(self):
        stages = (
            "current",
            "token_open",
            "token_size",
            "token_data",
            "sid",
            "times",
            "image",
            "file_open",
            "file_read",
            "pid",
        )
        for expiry_stage in stages:
            with self.subTest(expiry_stage=expiry_stage):
                self.check_identity_expiry(expiry_stage)

    def test_executable_close_throw_or_still_open_reports_cleanup_uncertainty(self):
        for mode in ("throws", "still_open"):
            with self.subTest(mode=mode):
                self.check_identity_expiry(None, close_failure=mode)

    def check_identity_expiry(self, expiry_stage, close_failure=None):
        exact = packet()
        expired = False
        events = []
        sid = ctypes.create_unicode_buffer(exact.process.user_sid)
        sid_memory = ctypes.create_string_buffer(32)

        def clock():
            return (1900.0, 901.0) if expired else (1000.0, 1.0)

        admission = Admission(exact, clock)

        def dispatch(stage):
            nonlocal expired
            self.assertFalse(expired, "new dispatch after expiry: " + stage)
            events.append(stage)
            if stage == expiry_stage:
                expired = True

        def current():
            dispatch("current")
            return 101

        def open_token(process, access, output):
            dispatch("token_open")
            output._obj.value = 102
            return True

        def token_info(token, kind, output, size, needed):
            dispatch("token_size" if output is None else "token_data")
            needed._obj.value = 32
            if output is None:
                return False
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(sid_memory)
            return True

        def convert(pointer, output):
            dispatch("sid")
            output._obj.value = ctypes.addressof(sid)
            return True

        def times(process, created, exited, kernel, user):
            dispatch("times")
            created._obj.dwLowDateTime = 123
            return True

        def image(module, output, maximum):
            dispatch("image")
            output.value = "C:\\synthetic\\python.exe"
            return len(output.value)

        class OwnedFile:
            def __init__(self, raw):
                self.raw = raw
                self.closed = False

            def read(self, *args):
                dispatch("file_read")
                return self.raw[: args[0]]

            def close(self):
                events.append("file_close")
                if close_failure == "throws":
                    raise OSError("synthetic unknown executable close")
                if close_failure == "still_open":
                    return
                self.closed = True

        original_open = Path.open

        def image_open(path, *args, **kwargs):
            if str(path) != "C:\\synthetic\\python.exe":
                return original_open(path, *args, **kwargs)
            dispatch("file_open")
            return OwnedFile(b"synthetic-python")

        def process_id():
            dispatch("pid")
            return 161

        kernel = SimpleNamespace(
            GetCurrentProcess=current,
            GetCurrentProcessId=process_id,
            GetProcessTimes=times,
            GetModuleFileNameW=image,
            LocalFree=lambda _: events.append("free"),
            CloseHandle=lambda _: events.append("token_close") or True,
        )
        advapi = SimpleNamespace(
            OpenProcessToken=open_token,
            GetTokenInformation=token_info,
            ConvertSidToStringSidW=convert,
        )
        with patch("local_action.Path.open", new=image_open):
            if close_failure is not None:
                result = prepare_local(
                    exact,
                    packet_fingerprint(exact),
                    lambda: windows_identity(kernel, advapi, admission),
                    lambda *args: self.fail("no facade after uncertain image cleanup"),
                    clock,
                    admission,
                )
                self.assertFalse(result.cleanup_confirmed or result.delivered)
                self.assertEqual(result.outcome, "process_image_cleanup_unconfirmed")
            else:
                with self.assertRaisesRegex(ValueError, "window_closed"):
                    windows_identity(kernel, advapi, admission)
        self.assertEqual(events.count("token_close"), 0 if expiry_stage == "current" else 1)
        if expiry_stage in ("sid", "times", "image", "file_open", "file_read", "pid"):
            self.assertIn("free", events)
        if expiry_stage in ("file_open", "file_read", "pid"):
            self.assertIn("file_close", events)
        if close_failure is not None:
            self.assertIn("file_close", events)
            self.assertIn("token_close", events)

    def test_native_wrappers_keep_signatures_and_allow_cleanup_after_expiry(self):
        exact = packet()
        observation = [1000.0, 1.0]
        admission = Admission(exact, lambda: (observation[0], observation[1]))
        effects = []

        class Function:
            argtypes = None
            restype = None

            def __init__(self, name):
                self.name = name

            def __call__(self, *args):
                effects.append(self.name)
                return True

        library = AdmittedLibrary(
            SimpleNamespace(
                ReadFile=Function("read"),
                WriteFile=Function("write"),
                CloseHandle=Function("close"),
                LocalFree=Function("free"),
            ),
            admission,
        )
        library.ReadFile.argtypes = [ctypes.c_void_p]
        library.ReadFile.restype = ctypes.c_int
        self.assertEqual(library.ReadFile.argtypes, [ctypes.c_void_p])
        self.assertIs(library.ReadFile.restype, ctypes.c_int)
        library.ReadFile()
        observation[:] = [1900.0, 901.0]
        with self.assertRaisesRegex(ValueError, "window_closed"):
            library.ReadFile()
        with self.assertRaisesRegex(ValueError, "window_closed"):
            library.WriteFile()
        library.CloseHandle()
        library.LocalFree()
        self.assertEqual(effects, ["read", "close", "free"])


if __name__ == "__main__":
    unittest.main()
