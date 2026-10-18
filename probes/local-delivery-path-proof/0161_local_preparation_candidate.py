"""#0183 integrated source-only successor: synthetic fixtures only, NO APPLY.

The old helper is neither imported nor executed. The fixed synthetic plan cannot
select credential/runtime paths. There is no live Windows binding in this file.
The Win32 adapter accepts explicitly injected synthetic APIs for tests; ordinary
WinDLL objects are refused. main() always refuses action before any API setup.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
from collections.abc import Callable
from ctypes import wintypes as w
from dataclasses import dataclass
from typing import Any, Protocol

import bounded_local_delivery_path_proof as proof

ROOTS = ("C:\\", "C:\\synthetic", "C:\\synthetic\\0183", "C:\\synthetic\\0183\\private")
SOURCE = ROOTS[-1] + "\\input.bin"
DESTINATION = ROOTS[-1] + "\\output.bin"
SYNTHETIC_BYTES = b"fixture0183_bounded_source"
EXPECTED_SHA2_256 = hashlib.sha256(SYNTHETIC_BYTES).hexdigest()
START = 1000.0
END = 1900.0
MAXIMUM = 8192


@dataclass(frozen=True)
class CreationSecurity:
    owner_sid: str
    aces: tuple[proof.Ace, ...]
    protected: bool = True

    @property
    def sddl(self) -> str:
        policy = proof.Policy(self.owner_sid, proof.TRUSTEDINSTALLER)
        expected = tuple(
            proof.Ace("allow", sid, 0x001F01FF)
            for sid in (self.owner_sid, proof.SYSTEM, proof.ADMINISTRATORS)
        )
        if self.protected is not True or self.aces != expected:
            raise proof.Refused("creation_descriptor_refused")
        _ = policy.trusted
        return f"O:{self.owner_sid}D:P(A;;FA;;;{self.owner_sid})(A;;FA;;;SY)(A;;FA;;;BA)"


@dataclass
class Receipt:
    outcome: str = "source_candidate_refused"
    credential_reads: int = 0
    delivered: bool = False
    writes: int = 0
    flushes: int = 0
    cleanup_confirmed: bool = True
    ownerConsent: bool = False
    nativeConsent: bool = False
    actionReady: bool = False


class Facade(Protocol):
    fixture_only: bool
    current_user_sid: str
    trustedinstaller_sid: str

    def open_directory(self, path: str, access: int, share: int, flags: int) -> proof.Node: ...
    def open_source(self, path: str, access: int, share: int, flags: int) -> proof.Node: ...
    def create_new(
        self, path: str, security: CreationSecurity, access: int, share: int, flags: int
    ) -> proof.Node: ...
    def inspect(self, handle_id: tuple[int, int]) -> proof.Node: ...
    def read(self, handle_id: tuple[int, int], maximum: int) -> bytes: ...
    def write(self, handle_id: tuple[int, int], raw: bytes) -> int: ...
    def flush(self, handle_id: tuple[int, int]) -> None: ...
    def close(self, handle_id: tuple[int, int]) -> None: ...


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", w.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", w.BOOL),
    ]


class FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("attributes", w.DWORD),
        ("creation", w.FILETIME),
        ("access", w.FILETIME),
        ("write", w.FILETIME),
        ("volume", w.DWORD),
        ("size_high", w.DWORD),
        ("size_low", w.DWORD),
        ("links", w.DWORD),
        ("index_high", w.DWORD),
        ("index_low", w.DWORD),
    ]


class NativeFacade:
    """Concrete Win32 adapter, usable here ONLY with explicitly synthetic APIs.

    No WinDLL loading or live factory is present. Injected libraries must declare
    synthetic_only=True. An ordinary native library is refused before setup.
    The fixed synthetic paths cannot be replaced by real packet/runtime paths.
    These restrictions are permanent in this reviewed snapshot; future binding
    is a separate source change/review, never a switch or new consent flag here.
    """

    fixture_only = True
    trustedinstaller_sid = proof.TRUSTEDINSTALLER

    def __init__(self, kernel: Any, advapi: Any, current_user_sid: str):
        if (
            getattr(kernel, "synthetic_only", False) is not True
            or getattr(advapi, "synthetic_only", False) is not True
        ):
            raise proof.Refused("live_entry_disabled")
        self.k = kernel
        self.a = advapi
        self.current_user_sid = current_user_sid
        _ = proof.Policy(current_user_sid, self.trustedinstaller_sid).trusted
        self._handles: dict[tuple[int, int], tuple[Any, proof.Node]] = {}
        self._sizes: dict[tuple[int, int], int] = {}
        self._read_attempted = False
        self.cleanup_confirmed = True
        self._dispatch_guard: Callable[[], None] | None = None
        # No process/account query or machine security change is needed by a
        # synthetic binding. A future live binding must obtain the real process
        # user SID, not assume a name/SID supplied by a packet.
        self._bind()

    def set_dispatch_guard(self, guard: Callable[[], None]):
        self._dispatch_guard = guard

    def _admit(self):
        if self._dispatch_guard is None:
            raise proof.Refused("dispatch_guard_required")
        self._dispatch_guard()

    def _bind(self):
        specs = (
            (
                self.k,
                "CreateFileW",
                [
                    w.LPCWSTR,
                    w.DWORD,
                    w.DWORD,
                    ctypes.POINTER(SECURITY_ATTRIBUTES),
                    w.DWORD,
                    w.DWORD,
                    w.HANDLE,
                ],
                w.HANDLE,
            ),
            (self.k, "CloseHandle", [w.HANDLE], w.BOOL),
            (self.k, "GetFileType", [w.HANDLE], w.DWORD),
            (
                self.k,
                "GetFileInformationByHandle",
                [w.HANDLE, ctypes.POINTER(FILE_INFORMATION)],
                w.BOOL,
            ),
            (self.k, "GetFinalPathNameByHandleW", [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD], w.DWORD),
            (self.k, "GetDriveTypeW", [w.LPCWSTR], w.UINT),
            (
                self.k,
                "GetVolumeInformationByHandleW",
                [
                    w.HANDLE,
                    w.LPWSTR,
                    w.DWORD,
                    ctypes.POINTER(w.DWORD),
                    ctypes.POINTER(w.DWORD),
                    ctypes.POINTER(w.DWORD),
                    w.LPWSTR,
                    w.DWORD,
                ],
                w.BOOL,
            ),
            (
                self.k,
                "ReadFile",
                [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p],
                w.BOOL,
            ),
            (
                self.k,
                "WriteFile",
                [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p],
                w.BOOL,
            ),
            (self.k, "FlushFileBuffers", [w.HANDLE], w.BOOL),
            (self.k, "CreateDirectoryW", [w.LPCWSTR, ctypes.POINTER(SECURITY_ATTRIBUTES)], w.BOOL),
            (self.k, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p),
            (
                self.a,
                "GetSecurityInfo",
                [
                    w.HANDLE,
                    w.DWORD,
                    w.DWORD,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                ],
                w.DWORD,
            ),
            (
                self.a,
                "GetSecurityDescriptorControl",
                [ctypes.c_void_p, ctypes.POINTER(w.WORD), ctypes.POINTER(w.DWORD)],
                w.BOOL,
            ),
            (self.a, "GetAce", [ctypes.c_void_p, w.DWORD, ctypes.POINTER(ctypes.c_void_p)], w.BOOL),
            (
                self.a,
                "ConvertSidToStringSidW",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                w.BOOL,
            ),
            (
                self.a,
                "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                [w.LPCWSTR, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p],
                w.BOOL,
            ),
        )
        for library, name, arguments, result in specs:
            function = getattr(library, name)
            function.argtypes = arguments
            function.restype = result

    @staticmethod
    def _allowed(path: str):
        if path not in {*ROOTS, SOURCE, DESTINATION}:
            raise proof.Refused("live_or_nonfixture_path_refused")

    def _sid(self, pointer: int) -> str:
        if not pointer:
            raise proof.Refused("sid_unavailable")
        output = ctypes.c_void_p()
        if not self.a.ConvertSidToStringSidW(pointer, ctypes.byref(output)):
            raise proof.Refused("sid_unavailable")
        try:
            value = ctypes.wstring_at(output)
            if not proof._sid(value):
                raise proof.Refused("sid_form_refused")
            return value
        finally:
            self.k.LocalFree(output)

    def _security(self, handle: Any) -> tuple[str, tuple[proof.Ace, ...], bool]:
        owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        if self.a.GetSecurityInfo(
            handle,
            1,
            5,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        ):
            raise proof.Refused("handle_security_unavailable")
        try:
            if not owner.value or not dacl.value or not descriptor.value:
                raise proof.Refused("owner_or_dacl_refused")
            owner_sid = self._sid(owner.value)
            control, revision = w.WORD(), w.DWORD()
            if not self.a.GetSecurityDescriptorControl(
                descriptor, ctypes.byref(control), ctypes.byref(revision)
            ):
                raise proof.Refused("handle_security_unavailable")
            count = ctypes.c_ushort.from_address(dacl.value + 4).value
            if count > 4096:
                raise proof.Refused("acl_bound_refused")
            aces = []
            for index in range(count):
                ace = ctypes.c_void_p()
                if not self.a.GetAce(dacl, index, ctypes.byref(ace)) or not ace.value:
                    raise proof.Refused("acl_unavailable")
                kind = ctypes.c_ubyte.from_address(ace.value).value
                flags = ctypes.c_ubyte.from_address(ace.value + 1).value
                size = ctypes.c_ushort.from_address(ace.value + 2).value
                if kind not in {0, 1} or flags & ~0x1F or size < 16:
                    raise proof.Refused("acl_form_refused")
                subauthorities = ctypes.c_ubyte.from_address(ace.value + 9).value
                if subauthorities > 15 or 8 + 4 * subauthorities > size - 8:
                    raise proof.Refused("acl_form_refused")
                mask = ctypes.c_uint32.from_address(ace.value + 4).value
                aces.append(
                    proof.Ace(
                        "allow" if kind == 0 else "deny",
                        self._sid(ace.value + 8),
                        mask,
                        bool(flags & 8),
                    )
                )
            return owner_sid, tuple(aces), bool(control.value & 0x1000)
        finally:
            if descriptor.value:
                self.k.LocalFree(descriptor)

    def _info(self, handle: Any) -> FILE_INFORMATION:
        info = FILE_INFORMATION()
        if self.k.GetFileType(handle) != 1 or not self.k.GetFileInformationByHandle(
            handle, ctypes.byref(info)
        ):
            raise proof.Refused("handle_metadata_unavailable")
        if info.attributes & 0x400:
            raise proof.Refused("ordinary_disk_object_required")
        return info

    def _inspect(self, handle: Any, template: proof.Node) -> proof.Node:
        info = self._info(handle)
        final_path = ctypes.create_unicode_buffer(32768)
        length = self.k.GetFinalPathNameByHandleW(handle, final_path, len(final_path), 0)
        if (
            not 0 < length < len(final_path)
            or final_path.value.casefold() != ("\\\\?\\" + template.path).casefold()
        ):
            raise proof.Refused("handle_path_binding_refused")
        owner, aces, protected = self._security(handle)
        identity = (int(info.volume), (int(info.index_high) << 32) | int(info.index_low))
        self._sizes[identity] = (int(info.size_high) << 32) | int(info.size_low)
        return proof.Node(
            template.path,
            owner,
            aces,
            directory=bool(info.attributes & 0x10),
            reparse=False,
            disk=True,
            links=int(info.links),
            desired_access=template.desired_access,
            share_mode=template.share_mode,
            protected_dacl=protected,
            handle_id=identity,
            flags=template.flags,
            disposition=template.disposition,
            creation_security_at_open=template.creation_security_at_open,
        )

    def _volume(self, handle: Any, node: proof.Node):
        name = ctypes.create_unicode_buffer(64)
        serial, component, flags = w.DWORD(), w.DWORD(), w.DWORD()
        if (
            self.k.GetDriveTypeW("C:\\") != 3
            or not self.k.GetVolumeInformationByHandleW(
                handle,
                None,
                0,
                ctypes.byref(serial),
                ctypes.byref(component),
                ctypes.byref(flags),
                name,
                len(name),
            )
            or name.value != "NTFS"
            or not flags.value & 8
            or serial.value != node.handle_id[0]
        ):
            raise proof.Refused("local_acl_volume_required")

    def _open(
        self,
        path: str,
        access: int,
        share: int,
        flags: int,
        disposition: int,
        security: CreationSecurity | None = None,
    ) -> proof.Node:
        self._allowed(path)
        descriptor = ctypes.c_void_p()
        attributes = None
        if security is not None:
            if not self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                security.sddl, 1, ctypes.byref(descriptor), None
            ):
                raise proof.Refused("creation_descriptor_unavailable")
            attributes = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
        handle = None
        try:
            self._admit()
            handle = self.k.CreateFileW(
                path,
                access,
                share,
                ctypes.byref(attributes) if attributes is not None else None,
                disposition,
                flags,
                None,
            )
            if handle is None or handle == ctypes.c_void_p(-1).value:
                handle = None
                raise proof.Refused(
                    "exclusive_creation_refused"
                    if disposition == proof.CREATE_NEW
                    else "open_refused"
                )
            template = proof.Node(
                path,
                self.current_user_sid,
                (),
                desired_access=access,
                share_mode=share,
                flags=flags,
                disposition=disposition,
                creation_security_at_open=security is not None,
            )
            node = self._inspect(handle, template)
            if path == ROOTS[0]:
                self._volume(handle, node)
            if node.handle_id in self._handles:
                raise proof.Refused("duplicate_object_identity_refused")
            self._handles[node.handle_id] = (handle, node)
            handle = None  # Ownership transfers to the retained-handle ledger.
            return node
        finally:
            if handle is not None:
                try:
                    closed = self.k.CloseHandle(handle)
                except Exception:
                    closed = False
                if not closed:
                    self.cleanup_confirmed = False
            if descriptor.value:
                self.k.LocalFree(descriptor)

    def open_directory(self, path: str, access: int, share: int, flags: int) -> proof.Node:
        if (
            path not in ROOTS
            or access != proof.DIRECTORY_ACCESS
            or share != proof.FILE_SHARE_READ
            or flags != proof.DIRECTORY_FLAGS
        ):
            raise proof.Refused("directory_path_refused")
        return self._open(path, access, share, flags, proof.OPEN_EXISTING)

    def open_source(self, path: str, access: int, share: int, flags: int) -> proof.Node:
        if (
            path != SOURCE
            or access != proof.GENERIC_READ
            or share != 0
            or flags != proof.FILE_FLAG_OPEN_REPARSE_POINT
        ):
            raise proof.Refused("source_path_refused")
        node = self._open(path, access, share, flags, proof.OPEN_EXISTING)
        # Size is checked before the bounded native read dispatch.
        if not 0 < self._sizes[node.handle_id] <= MAXIMUM:
            self.close(node.handle_id)
            raise proof.Refused("source_size_refused")
        return node

    def create_new(
        self, path: str, security: CreationSecurity, access: int, share: int, flags: int
    ) -> proof.Node:
        if (
            path != DESTINATION
            or access != (proof.GENERIC_WRITE | proof.READ_CONTROL | proof.FILE_READ_ATTRIBUTES)
            or share != 0
            or flags != proof.FILE_FLAG_OPEN_REPARSE_POINT
        ):
            raise proof.Refused("destination_path_refused")
        return self._open(path, access, share, flags, proof.CREATE_NEW, security)

    def create_directory(self, path: str, security: CreationSecurity):
        # Bounded optional primitive for future reviewed missing-tail integration;
        # current orchestrator requires the existing qualified private chain.
        if path != ROOTS[-1]:
            raise proof.Refused("directory_path_refused")
        descriptor = ctypes.c_void_p()
        if not self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            security.sddl, 1, ctypes.byref(descriptor), None
        ):
            raise proof.Refused("creation_descriptor_unavailable")
        try:
            attributes = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
            self._admit()
            if not self.k.CreateDirectoryW(path, ctypes.byref(attributes)):
                raise proof.Refused("exclusive_directory_creation_refused")
        finally:
            self.k.LocalFree(descriptor)

    def inspect(self, handle_id: tuple[int, int]) -> proof.Node:
        handle, template = self._handles[handle_id]
        node = self._inspect(handle, template)
        if node.handle_id != handle_id:
            raise proof.Refused("file_identity_or_security_changed")
        return node

    def read(self, handle_id: tuple[int, int], maximum: int) -> bytes:
        handle, node = self._handles[handle_id]
        if node.path != SOURCE or maximum != MAXIMUM or self._read_attempted:
            raise proof.Refused("bounded_single_source_read_required")
        self._read_attempted = True
        before = self._info(handle)
        size = (int(before.size_high) << 32) | int(before.size_low)
        if not 0 < size <= MAXIMUM:
            raise proof.Refused("source_size_refused")
        data = ctypes.create_string_buffer(MAXIMUM)
        count = w.DWORD()
        self._admit()
        if not self.k.ReadFile(handle, data, MAXIMUM, ctypes.byref(count), None):
            raise proof.Refused("read_unconfirmed")
        after = self._info(handle)
        if count.value != size or bytes(before) != bytes(after):
            raise proof.Refused("read_identity_or_size_changed")
        return bytes(data.raw[: count.value])

    def write(self, handle_id: tuple[int, int], raw: bytes) -> int:
        handle, node = self._handles[handle_id]
        if node.path != DESTINATION or type(raw) is not bytes or not 0 < len(raw) <= MAXIMUM:
            raise proof.Refused("bounded_destination_write_required")
        count = w.DWORD()
        self._admit()
        if not self.k.WriteFile(handle, raw, len(raw), ctypes.byref(count), None):
            raise proof.Refused("write_unconfirmed")
        return count.value

    def flush(self, handle_id: tuple[int, int]):
        handle, node = self._handles[handle_id]
        if node.path != DESTINATION:
            raise proof.Refused("flush_unconfirmed")
        self._admit()
        if not self.k.FlushFileBuffers(handle):
            raise proof.Refused("flush_unconfirmed")

    def close(self, handle_id: tuple[int, int]):
        handle, _ = self._handles.pop(handle_id)
        self._sizes.pop(handle_id, None)
        try:
            closed = self.k.CloseHandle(handle)
        except Exception:
            self.cleanup_confirmed = False
            raise proof.Refused("close_unconfirmed") from None
        if not closed:
            self.cleanup_confirmed = False
            raise proof.Refused("close_unconfirmed")


def _same_file(before: proof.Node, after: proof.Node):
    if (
        before.path,
        before.handle_id,
        before.directory,
        before.reparse,
        before.links,
        before.owner,
        before.aces,
        before.protected_dacl,
    ) != (
        after.path,
        after.handle_id,
        after.directory,
        after.reparse,
        after.links,
        after.owner,
        after.aces,
        after.protected_dacl,
    ):
        raise proof.Refused("file_identity_or_security_changed")


def run_preparation(facade: Facade, clock: Callable[[], tuple[float, float]]) -> Receipt:
    """Run the integrated algorithm against injected SYNTHETIC observations only.

    Synthetic read attempts are counted before dispatch, including an exception.
    No consent, time, path or source-byte parameter can select a real operation.
    Native API completion after admission is not a hard realtime cancellation.
    """
    receipt = Receipt()
    held: list[tuple[int, int]] = []
    try:
        if facade.fixture_only is not True:
            raise proof.Refused("live_entry_disabled")
        policy = proof.Policy(facade.current_user_sid, facade.trustedinstaller_sid)
        initial_utc, initial_monotonic = clock()
        window = proof.Window(START, END, initial_monotonic, initial_utc, initial_monotonic)

        def admission():
            nonlocal window
            window = window.before_dispatch(*clock())

        native_guard = getattr(facade, "set_dispatch_guard", None)
        if native_guard is not None:
            native_guard(admission)

        parents: list[proof.Node] = []
        for path in ROOTS:
            admission()
            node = facade.open_directory(
                path, proof.DIRECTORY_ACCESS, proof.FILE_SHARE_READ, proof.DIRECTORY_FLAGS
            )
            held.append(node.handle_id)
            if node.path != path:
                raise proof.Refused("fixed_path_binding_refused")
            parents.append(node)
            policy.qualify_chain(tuple(parents), private_from=3 if len(parents) == 4 else None)
        chain = tuple(parents)
        admission()
        source = facade.open_source(
            SOURCE, proof.GENERIC_READ, 0, proof.FILE_FLAG_OPEN_REPARSE_POINT
        )
        held.append(source.handle_id)
        if source.path != SOURCE:
            raise proof.Refused("fixed_path_binding_refused")
        policy.qualify_source(source, chain)
        security = CreationSecurity(
            policy.current_user_sid,
            tuple(
                proof.Ace("allow", sid, 0x001F01FF)
                for sid in (policy.current_user_sid, proof.SYSTEM, proof.ADMINISTRATORS)
            ),
        )
        _ = security.sddl  # Validate exact creation descriptor before native dispatch.
        admission()
        destination = facade.create_new(
            DESTINATION,
            security,
            proof.GENERIC_WRITE | proof.READ_CONTROL | proof.FILE_READ_ATTRIBUTES,
            0,
            proof.FILE_FLAG_OPEN_REPARSE_POINT,
        )
        held.append(destination.handle_id)
        if destination.path != DESTINATION or destination.handle_id == source.handle_id:
            raise proof.Refused("fixed_path_binding_refused")
        policy.qualify_new_file(destination, chain)
        admission()
        receipt.credential_reads += 1
        raw = facade.read(source.handle_id, MAXIMUM)
        if type(raw) is not bytes or not 0 < len(raw) <= MAXIMUM:
            raise proof.Refused("bounded_read_refused")
        admission()
        source_after = facade.inspect(source.handle_id)
        policy.qualify_source(source_after, chain)
        _same_file(source, source_after)
        if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA2_256:
            raise proof.Refused("synthetic_source_identity_refused")
        admission()
        receipt.writes += 1
        written = facade.write(destination.handle_id, raw)
        if type(written) is not int or written != len(raw):
            raise proof.Refused("write_unconfirmed")
        del raw
        admission()
        receipt.flushes += 1
        facade.flush(destination.handle_id)
        admission()
        destination_after = facade.inspect(destination.handle_id)
        policy.qualify_new_file(destination_after, chain)
        _same_file(destination, destination_after)
        admission()
        receipt.delivered = True
        receipt.outcome = "synthetic_preparation_complete_no_run_authority"
    except proof.Refused as error:
        receipt.outcome = error.code
    except Exception:
        receipt.outcome = "source_candidate_unknown_failure"
    finally:
        for handle_id in reversed(held):
            try:
                facade.close(handle_id)
            except Exception:
                receipt.cleanup_confirmed = False
        if getattr(facade, "cleanup_confirmed", True) is not True:
            receipt.cleanup_confirmed = False
        if not receipt.cleanup_confirmed:
            receipt.outcome = "source_candidate_cleanup_unconfirmed"
            receipt.delivered = False
    return receipt


def main() -> int:
    print(
        json.dumps(
            {
                "outcome": "NO_APPLY_source_candidate_only",
                "credential_reads": 0,
                "credential_delivered": False,
                "ownerConsent": False,
                "nativeConsent": False,
                "actionReady": False,
            },
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
