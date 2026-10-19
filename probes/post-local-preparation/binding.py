"""#0161 fixed synthetic source/action coordinator. NO APPLY; no DLL or live paths.

Trusted injected stores model durable exclusive claims and receipts. This test
seam is not physical custody qualification or a sandbox against Python code.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Protocol

ADAPTER_SHA2_256 = "dda739925d0a3d55aecad3c914f7690f15c5d7518f4927d3980d351e0d5ba3d9"
GUARD_SHA2_256 = "856d98523a82722bc1bedbdd6a47a95be6011a524472a3620559995964ff0c6a"
ROOT = "C:\\synthetic\\0183\\private"
MARKERS = tuple(
    ROOT + "\\" + name
    for name in (
        "prior-attempt.claim",
        "prior-attempt.receipt",
        "post.claim",
        "post.receipt",
        "local.claim",
        "local.receipt",
        "local.stop",
    )
)


class Refused(ValueError):
    pass


@dataclass(frozen=True)
class ProcessIdentity:
    user_sid: str = "S-1-5-21-100-200-300-1001"
    process_id: int = 161
    started: str = "synthetic-process-generation-1"
    executable_sha2_256: str = hashlib.sha256(b"synthetic-python").hexdigest()


@dataclass(frozen=True)
class Packet:
    schema: str = "0161-synthetic-local-binding-v1"
    run_identity: str = "synthetic0161-fresh-local-only"
    process: ProcessIdentity = ProcessIdentity()
    source: str = ROOT + "\\input.bin"
    destination: str = ROOT + "\\output.bin"
    source_sha2_256: str = hashlib.sha256(b"fixture0183_bounded_source").hexdigest()
    adapter_sha2_256: str = ADAPTER_SHA2_256
    guard_sha2_256: str = GUARD_SHA2_256
    markers: tuple[str, ...] = MARKERS
    claim: str = ROOT + "\\local.claim"
    receipt: str = ROOT + "\\local.receipt"
    start: float = 1000.0
    deadline: float = 1900.0
    ownerConsent: bool = False
    nativeConsent: bool = False
    actionReady: bool = False


FIXED_PACKET = Packet()


def fingerprint(packet: Packet) -> str:
    """Exact canonical JSON UTF-8 fingerprint. Fixtures contain no private data."""
    raw = json.dumps(asdict(packet), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AdapterResult:
    outcome: str
    credential_reads: int
    writes: int
    flushes: int
    delivered: bool
    cleanup_confirmed: bool
    ownerConsent: bool = False
    nativeConsent: bool = False
    actionReady: bool = False


@dataclass(frozen=True)
class Receipt:
    packet_sha2_256: str
    outcome: str = "source_binding_refused"
    claim_attempted: bool = False
    claim_confirmed: bool = False
    adapter_attempted: bool = False
    adapter_result: AdapterResult | None = None
    receipt_attempted: bool = False
    receipt_confirmed: bool = False
    actionReady: bool = False
    ownerConsent: bool = False
    nativeConsent: bool = False


class Store(Protocol):
    synthetic_only: bool

    def markers_absent(self, exact_paths: tuple[str, ...]) -> bool: ...
    def create_claim(self, exact_path: str, packet_sha2_256: str) -> bool: ...
    def create_receipt(self, exact_path: str, receipt: Receipt) -> bool: ...


class Adapter(Protocol):
    synthetic_only: bool
    process: ProcessIdentity
    adapter_sha2_256: str
    guard_sha2_256: str

    def run(self, clock: Callable[[], tuple[float, float]]) -> AdapterResult: ...


class Attempt:
    """One shot, including refusals and uncertain effects.

    Store.create_claim means durable exclusive CREATE_NEW, with no overwrite,
    delete or retry. An exception may leave a claim. Across processes the durable
    claim owns no-replay, not this in-memory latch. No real store is supplied.
    """

    def __init__(self) -> None:
        self._attempted = False

    def run(
        self,
        packet: Packet,
        reviewed_fingerprint: str,
        adapter: Adapter,
        store: Store,
        clock: Callable[[], tuple[float, float]],
    ) -> Receipt:
        result = Receipt(fingerprint(FIXED_PACKET))
        if self._attempted:
            return replace(result, outcome="no_replay")
        self._attempted = True
        previous_utc = FIXED_PACKET.start
        previous_monotonic: float | None = None
        started_monotonic: float | None = None

        def admit() -> None:
            nonlocal previous_utc, previous_monotonic, started_monotonic
            utc, monotonic = clock()
            if (
                any(type(v) not in {int, float} or not math.isfinite(v) for v in (utc, monotonic))
                or not previous_utc <= utc < FIXED_PACKET.deadline
                or (previous_monotonic is not None and monotonic < previous_monotonic)
            ):
                raise Refused("window_closed")
            if started_monotonic is None:
                started_monotonic = monotonic
            if monotonic - started_monotonic >= FIXED_PACKET.deadline - FIXED_PACKET.start:
                raise Refused("window_closed")
            previous_utc, previous_monotonic = utc, monotonic

        try:
            # Canonical bytes also distinguish bool/int and integer/float equality.
            if (
                packet != FIXED_PACKET
                or fingerprint(packet) != fingerprint(FIXED_PACKET)
                or reviewed_fingerprint != fingerprint(FIXED_PACKET)
                or adapter.synthetic_only is not True
                or store.synthetic_only is not True
                or adapter.process != FIXED_PACKET.process
                or type(adapter.process.process_id) is not int
                or adapter.adapter_sha2_256 != ADAPTER_SHA2_256
                or adapter.guard_sha2_256 != GUARD_SHA2_256
            ):
                raise Refused("fixed_binding_refused")
            admit()
            if store.markers_absent(packet.markers) is not True:
                raise Refused("marker_freshness_refused")
            admit()
            result = replace(result, claim_attempted=True)
            if store.create_claim(packet.claim, result.packet_sha2_256) is not True:
                raise Refused("claim_unconfirmed_no_replay")
            result = replace(result, claim_confirmed=True)
            admit()
            result = replace(result, adapter_attempted=True)
            observed = adapter.run(clock)
            result = replace(result, adapter_result=observed)
            if (
                observed.outcome != "synthetic_preparation_complete_no_run_authority"
                or type(observed.credential_reads) is not int
                or observed.credential_reads != 1
                or type(observed.writes) is not int
                or observed.writes != 1
                or type(observed.flushes) is not int
                or observed.flushes != 1
                or observed.delivered is not True
                or observed.cleanup_confirmed is not True
                or observed.ownerConsent is not False
                or observed.nativeConsent is not False
                or observed.actionReady is not False
            ):
                raise Refused("adapter_result_refused_no_replay")
            admit()
            result = replace(result, outcome="synthetic_binding_complete_no_run_authority")
        except Refused as error:
            result = replace(result, outcome=str(error))
        except Exception:
            result = replace(result, outcome="binding_unknown_failure_no_replay")
        if result.claim_confirmed:
            try:
                admit()
                result = replace(result, receipt_attempted=True)
                if store.create_receipt(packet.receipt, result) is not True:
                    raise Refused("receipt_unconfirmed_no_replay")
                result = replace(result, receipt_confirmed=True)
            except Exception:
                result = replace(result, outcome="receipt_unconfirmed_no_replay")
        return result


def main() -> int:
    print(json.dumps(asdict(Receipt(fingerprint(FIXED_PACKET), outcome="NO_APPLY_source_only"))))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
