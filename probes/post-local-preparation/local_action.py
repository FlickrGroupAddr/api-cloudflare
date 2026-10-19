"""Deferred exact local preparation factory; main remains unconditional NO APPLY.

This module defines real Win32 dispatch but never calls its live factory on
import or CLI entry. Tests inject APIs/identity/clock. No POST/native authority.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import re
import threading
from collections.abc import Callable
from ctypes import wintypes as w
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PureWindowsPath
from typing import Any

import bounded_local_delivery_path_proof as proof
from binding import ADAPTER_SHA2_256, GUARD_SHA2_256, ProcessIdentity, Refused
from reviewed_adapter import load_reviewed

REVIEWED = load_reviewed()
_ATTEMPTS: set[str] = set()
_ATTEMPTS_LOCK = threading.Lock()


class CleanupUnconfirmed(Refused):
    pass


@dataclass(frozen=True)
class LocalPacket:
    run_identity: str
    process: ProcessIdentity
    roots: tuple[str, ...]
    private_from: int
    source: str
    destination: str
    source_sha2_256: str
    markers: tuple[str, ...]
    claim: str
    receipt: str
    start: float
    deadline: float
    source_not_after: float
    integration_pins: tuple[tuple[str, str], ...]
    localConsent: bool = False
    nativeConsent: bool = False
    actionReady: bool = False
    adapter_sha2_256: str = ADAPTER_SHA2_256
    guard_sha2_256: str = GUARD_SHA2_256


def packet_fingerprint(packet: LocalPacket) -> str:
    raw = json.dumps(asdict(packet), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def current_source_pins() -> tuple[tuple[str, str], ...]:
    """Only public fixed source files; use before independent exact-packet review."""
    root = Path(__file__).resolve().parent
    return tuple(
        (name, hashlib.sha256((root / name).read_bytes()).hexdigest())
        for name in ("binding.py", "reviewed_adapter.py", "local_action.py")
    )


def validate_packet(packet: LocalPacket, reviewed_fingerprint: str) -> None:
    if (
        packet_fingerprint(packet) != reviewed_fingerprint
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{15,95}", packet.run_identity)
        or packet.localConsent is not True
        or packet.nativeConsent is not False
        or packet.actionReady is not False
        or packet.adapter_sha2_256 != ADAPTER_SHA2_256
        or packet.guard_sha2_256 != GUARD_SHA2_256
        or packet.integration_pins != current_source_pins()
        or type(packet.private_from) is not int
        or not 1 <= packet.private_from < len(packet.roots)
        or packet.roots[0] != "C:\\"
        or len(packet.markers) != 7
        or len({p.casefold() for p in packet.markers}) != 7
        or packet.claim not in packet.markers
        or packet.receipt not in packet.markers
        or packet.claim == packet.receipt
        or len({p.casefold() for p in (packet.source, packet.destination, *packet.markers)}) != 9
        or not re.fullmatch(r"[a-f0-9]{64}", packet.source_sha2_256)
        or not re.fullmatch(r"[a-f0-9]{64}", packet.process.executable_sha2_256)
        or type(packet.process.process_id) is not int
        or packet.process.process_id <= 0
        or not packet.process.started
    ):
        raise Refused("exact_packet_refused")
    _ = proof.Policy(packet.process.user_sid, proof.TRUSTEDINSTALLER).trusted
    for index, root in enumerate(packet.roots):
        path = proof.fixed_path(root)
        if index and path.parent != PureWindowsPath(packet.roots[index - 1]):
            raise Refused("full_parent_chain_required")
    for path in (packet.source, packet.destination, *packet.markers):
        if proof.fixed_path(path).parent != PureWindowsPath(packet.roots[-1]):
            raise Refused("exact_private_parent_required")
    # Validate finite numeric start/deadline and the maximum fifteen-minute bound.
    proof.Window(packet.start, packet.deadline, 0.0, packet.start, 0.0).before_dispatch(
        packet.start, 0.0
    )
    if (
        type(packet.source_not_after) not in {int, float}
        or not math.isfinite(packet.source_not_after)
        or packet.source_not_after <= packet.deadline
    ):
        raise Refused("credential_lifetime_refused")


class BoundFacade(REVIEWED.NativeFacade):
    """Reuse reviewed handle/security plumbing; override fixed fixture boundaries.

    The ordinary trusted-local-host premises of #0183 still apply. This subclass
    adds exact packet paths, never changing the reviewed module's constants.
    """

    fixture_only = False

    def __init__(
        self, kernel: Any, advapi: Any, packet: LocalPacket, admission: Callable[[], None]
    ):
        self.packet = packet
        self.k, self.a = kernel, advapi
        self.current_user_sid = packet.process.user_sid
        self._handles: dict[tuple[int, int], tuple[Any, Any]] = {}
        self._sizes: dict[tuple[int, int], int] = {}
        self._read_attempted = False
        self.cleanup_confirmed = True
        self._dispatch_guard = admission
        self._bind()

    def _allowed(self, path: str):
        if path not in {
            *self.packet.roots,
            self.packet.source,
            self.packet.destination,
            *self.packet.markers,
        }:
            raise Refused("exact_path_refused")

    def create_directory(self, path: str, security: Any):
        raise Refused("existing_qualified_parent_chain_required")

    def open_directory(self, path: str, access: int, share: int, flags: int):
        if (
            path not in self.packet.roots
            or access != proof.DIRECTORY_ACCESS
            or share != proof.FILE_SHARE_READ
            or flags != proof.DIRECTORY_FLAGS
        ):
            raise Refused("directory_path_refused")
        return self._open(path, access, share, flags, proof.OPEN_EXISTING)

    def open_source(self, path: str, access: int, share: int, flags: int):
        if (
            path != self.packet.source
            or access != proof.GENERIC_READ
            or share != 0
            or flags != proof.FILE_FLAG_OPEN_REPARSE_POINT
        ):
            raise Refused("source_path_refused")
        node = self._open(path, access, share, flags, proof.OPEN_EXISTING)
        if not 0 < self._sizes[node.handle_id] <= REVIEWED.MAXIMUM:
            self.close(node.handle_id)
            raise Refused("source_size_refused")
        return node

    def create_new(self, path: str, security: Any, access: int, share: int, flags: int):
        if (
            path not in {self.packet.destination, self.packet.claim, self.packet.receipt}
            or access != proof.GENERIC_WRITE | proof.READ_CONTROL | proof.FILE_READ_ATTRIBUTES
            or share != 0
            or flags != proof.FILE_FLAG_OPEN_REPARSE_POINT
        ):
            raise Refused("output_path_refused")
        return self._open(path, access, share, flags, proof.CREATE_NEW, security)

    def read(self, handle_id: tuple[int, int], maximum: int) -> bytes:
        handle, node = self._handles[handle_id]
        if node.path != self.packet.source or maximum != REVIEWED.MAXIMUM or self._read_attempted:
            raise Refused("single_bounded_read_required")
        self._read_attempted = True
        before = self._info(handle)
        size = (int(before.size_high) << 32) | int(before.size_low)
        if not 0 < size <= maximum:
            raise Refused("source_size_refused")
        data, count = ctypes.create_string_buffer(maximum), w.DWORD()
        self._admit()
        if not self.k.ReadFile(handle, data, maximum, ctypes.byref(count), None):
            raise Refused("read_unconfirmed")
        after = self._info(handle)
        if count.value != size or bytes(before) != bytes(after):
            raise Refused("read_identity_or_size_changed")
        return bytes(data.raw[: count.value])

    def write(self, handle_id: tuple[int, int], raw: bytes) -> int:
        handle, node = self._handles[handle_id]
        if (
            node.path not in {self.packet.destination, self.packet.claim, self.packet.receipt}
            or type(raw) is not bytes
            or not 0 < len(raw) <= REVIEWED.MAXIMUM
        ):
            raise Refused("bounded_write_required")
        count = w.DWORD()
        self._admit()
        if not self.k.WriteFile(handle, raw, len(raw), ctypes.byref(count), None):
            raise Refused("write_unconfirmed")
        return count.value

    def flush(self, handle_id: tuple[int, int]):
        handle, node = self._handles[handle_id]
        if node.path not in {self.packet.destination, self.packet.claim, self.packet.receipt}:
            raise Refused("flush_path_refused")
        self._admit()
        if not self.k.FlushFileBuffers(handle):
            raise Refused("flush_unconfirmed")

    def marker_absent(self, path: str) -> bool:
        if path not in self.packet.markers:
            raise Refused("marker_path_refused")
        self._admit()
        handle = self.k.CreateFileW(
            path,
            proof.READ_CONTROL | proof.FILE_READ_ATTRIBUTES,
            proof.FILE_SHARE_READ,
            None,
            proof.OPEN_EXISTING,
            proof.FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle is None or handle == ctypes.c_void_p(-1).value:
            # Missing leaf only. Missing parent, sharing/security and unknown
            # failures never count as freshness. Last-error comes from WinDLL.
            if ctypes.get_last_error() == 2:
                return True
            raise Refused("marker_observation_unknown")
        try:
            return False
        finally:
            try:
                closed = self.k.CloseHandle(handle)
            except Exception:
                closed = False
            if not closed:
                self.cleanup_confirmed = False
                raise Refused("marker_close_unconfirmed")

    def close_all(self):
        for identity in reversed(tuple(self._handles)):
            try:
                self.close(identity)
            except Exception:
                self.cleanup_confirmed = False


@dataclass(frozen=True)
class LocalReceipt:
    packet_sha2_256: str
    outcome: str = "local_preparation_refused"
    claim_attempted: bool = False
    claim_confirmed: bool = False
    credential_reads: int = 0
    destination_attempted: bool = False
    delivered: bool = False
    receipt_attempted: bool = False
    receipt_confirmed: bool = False
    cleanup_confirmed: bool = True
    nativeConsent: bool = False
    actionReady: bool = False


class Admission:
    """One continuous clock history from setup through the final effect."""

    def __init__(self, packet: LocalPacket, clock: Callable[[], tuple[float, float]]):
        self.packet_sha2_256 = packet_fingerprint(packet)
        self.clock = clock
        utc, monotonic = clock()
        self.window = proof.Window(packet.start, packet.deadline, monotonic, utc, monotonic)
        self.window = self.window.before_dispatch(utc, monotonic)

    def __call__(self):
        self.window = self.window.before_dispatch(*self.clock())


class AdmittedFunction:
    """Keep ctypes signatures while admitting each native API dispatch."""

    def __init__(self, function: Any, admission: Callable[[], None], cleanup: bool):
        self.function, self.admission, self.cleanup = function, admission, cleanup

    @property
    def argtypes(self):
        return self.function.argtypes

    @argtypes.setter
    def argtypes(self, value):
        self.function.argtypes = value

    @property
    def restype(self):
        return self.function.restype

    @restype.setter
    def restype(self, value):
        self.function.restype = value

    def __call__(self, *arguments):
        if not self.cleanup:
            self.admission()
        return self.function(*arguments)


class AdmittedLibrary:
    def __init__(self, library: Any, admission: Callable[[], None]):
        self.library, self.admission = library, admission
        self.functions: dict[str, AdmittedFunction] = {}

    def __getattr__(self, name: str):
        if name not in self.functions:
            if name not in {"CloseHandle", "LocalFree"}:
                self.admission()
            self.functions[name] = AdmittedFunction(
                getattr(self.library, name),
                self.admission,
                cleanup=name in {"CloseHandle", "LocalFree"},
            )
        return self.functions[name]


def prepare_local(
    packet: LocalPacket,
    reviewed_fingerprint: str,
    identity: Callable[[], ProcessIdentity],
    facade_factory: Callable[[LocalPacket, Callable[[], None]], Any],
    clock: Callable[[], tuple[float, float]],
    admission: Admission | None = None,
) -> LocalReceipt:
    """One finite call. Claims are never removed; retry needs a fresh exact packet.

    The sole receipt is a pre-close observation, so its cleanup status is always
    false/unknown. The returned receipt includes final close outcomes. A durable
    receipt does not retroactively prove cleanup or grant native/POST authority.
    """
    result = LocalReceipt(reviewed_fingerprint)
    facade = None
    try:
        validate_packet(packet, reviewed_fingerprint)
        admit = admission if admission is not None else Admission(packet, clock)
        if admit.packet_sha2_256 != reviewed_fingerprint:
            raise Refused("admission_packet_refused")

        admit()
        if identity() != packet.process:
            raise Refused("process_identity_refused")
        admit()
        facade = facade_factory(packet, admit)
        policy = proof.Policy(packet.process.user_sid, proof.TRUSTEDINSTALLER)
        chain: list[Any] = []
        for path in packet.roots:
            admit()
            node = facade.open_directory(
                path, proof.DIRECTORY_ACCESS, proof.FILE_SHARE_READ, proof.DIRECTORY_FLAGS
            )
            if node.path != path:
                raise Refused("exact_parent_refused")
            chain.append(node)
            policy.qualify_chain(
                tuple(chain),
                private_from=(packet.private_from if len(chain) > packet.private_from else None),
            )
        for path in packet.markers:
            admit()
            if facade.marker_absent(path) is not True:
                raise Refused("marker_not_fresh")
        security = REVIEWED.CreationSecurity(
            policy.current_user_sid,
            tuple(
                proof.Ace("allow", sid, 0x001F01FF)
                for sid in (policy.current_user_sid, proof.SYSTEM, proof.ADMINISTRATORS)
            ),
        )
        _ = security.sddl

        def create(path: str):
            admit()
            node = facade.create_new(
                path,
                security,
                proof.GENERIC_WRITE | proof.READ_CONTROL | proof.FILE_READ_ATTRIBUTES,
                0,
                proof.FILE_FLAG_OPEN_REPARSE_POINT,
            )
            if node.path != path:
                raise Refused("exact_output_refused")
            policy.qualify_new_file(node, tuple(chain))
            return node

        def write_record(node: Any, raw: bytes):
            admit()
            if facade.write(node.handle_id, raw) != len(raw):
                raise Refused("write_unconfirmed")
            admit()
            facade.flush(node.handle_id)
            admit()
            after = facade.inspect(node.handle_id)
            policy.qualify_new_file(after, tuple(chain))
            REVIEWED._same_file(node, after)

        result = replace(result, claim_attempted=True)
        claim = create(packet.claim)
        write_record(
            claim,
            json.dumps(
                {"run_identity": packet.run_identity, "packet_sha2_256": reviewed_fingerprint}
            ).encode(),
        )
        result = replace(result, claim_confirmed=True)
        admit()
        source = facade.open_source(
            packet.source, proof.GENERIC_READ, 0, proof.FILE_FLAG_OPEN_REPARSE_POINT
        )
        if source.path != packet.source:
            raise Refused("exact_source_refused")
        policy.qualify_source(source, tuple(chain))
        result = replace(result, destination_attempted=True)
        destination = create(packet.destination)
        if destination.handle_id == source.handle_id:
            raise Refused("distinct_source_destination_required")
        admit()
        result = replace(result, credential_reads=1)
        raw = facade.read(source.handle_id, REVIEWED.MAXIMUM)
        if type(raw) is not bytes or not 0 < len(raw) <= REVIEWED.MAXIMUM:
            raise Refused("bounded_read_refused")
        admit()
        source_after = facade.inspect(source.handle_id)
        policy.qualify_source(source_after, tuple(chain))
        REVIEWED._same_file(source, source_after)
        if hashlib.sha256(raw).hexdigest() != packet.source_sha2_256:
            raise Refused("source_fingerprint_refused")
        write_record(destination, raw)
        del raw
        admit()
        result = replace(
            result, delivered=True, outcome="local_preparation_complete_no_run_authority"
        )
        result = replace(result, receipt_attempted=True)
        receipt = create(packet.receipt)
        write_record(receipt, json.dumps(asdict(replace(result, cleanup_confirmed=False))).encode())
        result = replace(result, receipt_confirmed=True)
    except CleanupUnconfirmed as error:
        result = replace(result, cleanup_confirmed=False, outcome=str(error))
    except (Refused, proof.Refused) as error:
        result = replace(result, outcome=str(error))
    except Exception:
        result = replace(result, outcome="local_preparation_unknown_no_replay")
    finally:
        if facade is not None:
            try:
                facade.close_all()
            except Exception:
                facade.cleanup_confirmed = False
            if facade.cleanup_confirmed is not True:
                result = replace(
                    result,
                    cleanup_confirmed=False,
                    delivered=False,
                    outcome="cleanup_unconfirmed_no_replay",
                )
    return result


def windows_identity(kernel: Any, advapi: Any, admission: Callable[[], None]) -> ProcessIdentity:
    """Read current process identity; called only by a separately approved action.

    An executable byte pin is provenance under the ordinary trusted-host premise,
    not proof against privileged in-memory code replacement.
    """
    admission()
    process = kernel.GetCurrentProcess()
    token = w.HANDLE()
    admission()
    if not advapi.OpenProcessToken(process, 8, ctypes.byref(token)):
        raise Refused("process_token_unavailable")
    try:
        needed = w.DWORD()
        admission()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if not ctypes.sizeof(ctypes.c_void_p) + ctypes.sizeof(w.DWORD) <= needed.value <= 65536:
            raise Refused("process_token_bound_refused")
        data = ctypes.create_string_buffer(needed.value)
        admission()
        if not advapi.GetTokenInformation(token, 1, data, needed.value, ctypes.byref(needed)):
            raise Refused("process_identity_unavailable")
        sid_pointer = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        sid_text = ctypes.c_void_p()
        admission()
        if not advapi.ConvertSidToStringSidW(sid_pointer, ctypes.byref(sid_text)):
            raise Refused("process_sid_unavailable")
        try:
            admission()
            sid = ctypes.wstring_at(sid_text)
        finally:
            try:
                released = kernel.LocalFree(sid_text) in (None, 0)
            except Exception:
                released = False
            if not released:
                raise CleanupUnconfirmed("process_sid_cleanup_unconfirmed")
        times = [w.FILETIME() for _ in range(4)]
        admission()
        if not kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in times)):
            raise Refused("process_start_unavailable")
        image = ctypes.create_unicode_buffer(32768)
        admission()
        length = kernel.GetModuleFileNameW(None, image, len(image))
        if not 0 < length < len(image):
            raise Refused("process_image_unavailable")
        generation = (int(times[0].dwHighDateTime) << 32) | int(times[0].dwLowDateTime)
        admission()
        executable = Path(image.value).open("rb")
        try:
            admission()
            raw = executable.read(64 * 1024 * 1024 + 1)
        finally:
            # Cleanup is mandatory even if admission/read failed after expiry.
            try:
                executable.close()
                closed = executable.closed is True
            except Exception:
                closed = False
            if not closed:
                raise CleanupUnconfirmed("process_image_cleanup_unconfirmed")
        if not 0 < len(raw) <= 64 * 1024 * 1024:
            raise Refused("process_image_bound_refused")
        admission()
        process_id = int(kernel.GetCurrentProcessId())
        admission()
        return ProcessIdentity(sid, process_id, str(generation), hashlib.sha256(raw).hexdigest())
    finally:
        try:
            closed = kernel.CloseHandle(token)
        except Exception:
            closed = False
        if not closed:
            raise CleanupUnconfirmed("process_token_close_unconfirmed")


def live_factory(
    packet: LocalPacket, reviewed_fingerprint: str, clock: Callable[[], tuple[float, float]]
) -> LocalReceipt:
    """Deferred callable only. No caller/CLI registration exists in this candidate."""
    validate_packet(packet, reviewed_fingerprint)
    # Consume before DLL setup. A pre-claim failure cannot be retried in this
    # exact process; another process fails the exact creation-generation check.
    with _ATTEMPTS_LOCK:
        if reviewed_fingerprint in _ATTEMPTS:
            return LocalReceipt(reviewed_fingerprint, outcome="no_replay")
        _ATTEMPTS.add(reviewed_fingerprint)
    admission = Admission(packet, clock)
    # No DLL load occurs until the explicit approved packet has passed validation.
    admission()
    kernel = AdmittedLibrary(ctypes.WinDLL("kernel32", use_last_error=True), admission)
    admission()
    advapi = AdmittedLibrary(ctypes.WinDLL("advapi32", use_last_error=True), admission)
    # Declare the additional identity APIs; reviewed facade declares all file APIs.
    specs = (
        (kernel, "GetCurrentProcess", [], w.HANDLE),
        (kernel, "GetCurrentProcessId", [], w.DWORD),
        (kernel, "GetProcessTimes", [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)], w.BOOL),
        (kernel, "GetModuleFileNameW", [w.HMODULE, w.LPWSTR, w.DWORD], w.DWORD),
        (advapi, "OpenProcessToken", [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL),
        (
            advapi,
            "GetTokenInformation",
            [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)],
            w.BOOL,
        ),
    )
    for library, name, arguments, result in specs:
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result

    # Configure common APIs before identity, without opening any path.
    def factory(exact: LocalPacket, admission: Callable[[], None]):
        return BoundFacade(kernel, advapi, exact, admission)

    def identity():
        # Identity needs SID/free/close API declarations before its first call.
        admission()
        setup = BoundFacade(kernel, advapi, packet, admission)
        _ = setup
        return windows_identity(kernel, advapi, admission)

    return prepare_local(packet, reviewed_fingerprint, identity, factory, clock, admission)


def main() -> int:
    print(
        json.dumps(
            {
                "outcome": "NO_APPLY_source_only",
                "actionReady": False,
                "ownerConsent": False,
                "nativeConsent": False,
                "credential_reads": 0,
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
