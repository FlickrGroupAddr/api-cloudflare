"""Bridge to the unchanged #0183 fixture, with checked public source byte pins.

Launch in an isolated Python process with the reviewed probe on PYTHONPATH.
No import-path or historical-file mutation is used. This is trusted source
execution, not dynamic attestation or a Python sandbox.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import bounded_local_delivery_path_proof as proof
from binding import ADAPTER_SHA2_256, FIXED_PACKET, GUARD_SHA2_256, AdapterResult, Refused

ROOT = Path(__file__).resolve().parents[1] / "local-delivery-path-proof"


def load_reviewed() -> Any:
    if Path(proof.__file__).resolve() != ROOT / "bounded_local_delivery_path_proof.py":
        raise Refused("reviewed_source_import_refused")
    guard_raw = (ROOT / "bounded_local_delivery_path_proof.py").read_bytes()
    source_path = ROOT / "0161_local_preparation_candidate.py"
    source_raw = source_path.read_bytes()
    if (
        hashlib.sha256(guard_raw).hexdigest() != GUARD_SHA2_256
        or hashlib.sha256(source_raw).hexdigest() != ADAPTER_SHA2_256
    ):
        raise Refused("reviewed_source_pin_refused")
    name = "post_local_preparation_reviewed0183"
    spec = importlib.util.spec_from_file_location(name, source_path)
    if spec is None:
        raise Refused("reviewed_source_import_refused")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(source_raw, str(source_path), "exec"), module.__dict__)
    return module


class ReviewedSyntheticAdapter:
    synthetic_only = True
    process = FIXED_PACKET.process
    adapter_sha2_256 = ADAPTER_SHA2_256
    guard_sha2_256 = GUARD_SHA2_256

    def __init__(self, facade: Any):
        if (
            facade.fixture_only is not True
            or facade.current_user_sid != self.process.user_sid
            or Path(proof.__file__).resolve() != ROOT / "bounded_local_delivery_path_proof.py"
        ):
            raise Refused("reviewed_fixture_binding_refused")
        module = load_reviewed()
        if (
            module.SOURCE != FIXED_PACKET.source
            or module.DESTINATION != FIXED_PACKET.destination
            or module.START != FIXED_PACKET.start
            or module.END != FIXED_PACKET.deadline
            or module.EXPECTED_SHA2_256 != FIXED_PACKET.source_sha2_256
        ):
            raise Refused("reviewed_constant_binding_refused")
        self.module = module
        self.facade = facade
        self._attempted = False

    def run(self, clock: Callable[[], tuple[float, float]]) -> AdapterResult:
        if self._attempted:
            raise Refused("adapter_no_replay")
        self._attempted = True
        observed = self.module.run_preparation(self.facade, clock)
        return AdapterResult(
            observed.outcome,
            observed.credential_reads,
            observed.writes,
            observed.flushes,
            observed.delivered,
            observed.cleanup_confirmed,
            observed.ownerConsent,
            observed.nativeConsent,
            observed.actionReady,
        )
