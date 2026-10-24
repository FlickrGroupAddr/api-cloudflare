"""Exact inherited SOURCE interface/capability inventory. No actual dispatch.

MIT License; copyright 2026 Terry Ott. Reading these public source files is not
an actual population census, custody receipt or a new campaign allocation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from runner import Refusal

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = {
    "D1.Provider.dispatch": "probes/pmb1-d1-adapter/adapter.py",
    "D1.Observer.read": "probes/pmb1-d1-adapter/adapter.py",
    "D1.Binding.query": "probes/pmb1-native-d1-binding/binding.py",
    "D1.Binding.dispatch_batch": "probes/pmb1-native-d1-binding/binding.py",
    "PrivateMainRuntime.currentMain": "probes/pmb1-fresh-native-capture/main-private-core.ts",
    "PrivateMainRuntime.stopAdmission": "probes/pmb1-fresh-native-capture/main-private-core.ts",
    "PrivateMainRuntime.assessStopped": "probes/pmb1-fresh-native-capture/main-private-core.ts",
    "PartitionWorker.maintenanceStop": "probes/pmb1-fresh-native-capture/owning-partition.ts",
    "PartitionWorker.maintenanceClose": "probes/pmb1-fresh-native-capture/owning-partition.ts",
    "PartitionWorker.maintenanceReconcile": "probes/pmb1-fresh-native-capture/owning-partition.ts",
    "PartitionWorker.maintenanceReopen": "probes/pmb1-fresh-native-capture/owning-partition.ts",
    "PartitionWorker.acquireFresh": "probes/pmb1-fresh-native-capture/owning-partition.ts",
    "createFreshNativeSource": "probes/pmb1-fresh-native-capture/source.ts",
    "publishReviewedEvidence": "probes/pmb1-runtime-evidence/operator.ts",
    "preparePublication": "probes/pmb1-runtime-evidence/publication-plan.ts",
    "publicationReadback": "probes/pmb1-runtime-evidence/publication-plan.ts",
    "RuntimeEvidenceLedger": "probes/pmb1-runtime-evidence/ledger.ts",
    "captureSupportedBoundary": "probes/pmb1-native-object-reader/object-kv-interface.ts",
}


@dataclass(frozen=True)
class AtomicAttempt:
    method: str
    source_pin: str
    resource: str
    ordinal: int
    requests: int
    statements: int
    effect_events: int | None
    outbound_wire_bytes: int | None
    inbound_wire_bytes: int | None


def verify_attempt(attempt: AtomicAttempt, retained_source_pins: dict[str, str]) -> None:
    """Unknown counters/origins/methods refuse rather than supplying fake zero.

    Composite SDK calls require expanded leaves. The method name alone never
    licenses charging its nested work as one operation. This function checks a
    concrete already-emitted leaf, not a cost estimate or a qualification oracle.
    """
    path = CONTRACTS.get(attempt.method)
    if path is None or path not in retained_source_pins:
        raise Refusal("unsupported_or_unbound_inherited_method")
    current = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if attempt.source_pin != retained_source_pins[path] or current != attempt.source_pin:
        raise Refusal("inherited_method_source_drift")
    # These methods are SOURCE catalogue entries, not authenticated atomic
    # leaves. Even query() lacks its exact SQL/arguments/route/response identity
    # here. No caller-supplied counters can refine that missing operation tree.
    raise Refusal("expanded_native_leaf_required")


def inherited_fit() -> dict:
    """Precise inert source fit report; source schema is not actual inventory."""
    plan = json.loads((ROOT / "probes/pmb1-native-disposition/domain-plan.json").read_bytes())
    schema = plan["schema"]
    tables = sum(row["type"] == "table" for row in schema)
    objects = len(schema)
    return {
        "scope": "SOURCE_ONLY",
        "domain_tables": tables,
        "included_application_tables": len(plan["tables"]),
        "observable_schema_tables": tables,
        "excluded_raw_table": plan["excluded"]["name"],
        "domain_schema_objects": objects,
        "accepted_miniature_tables": 8,
        "accepted_miniature_schema_objects": 64,
        "fits": tables <= 8 and objects <= 64,
        "reason": "selected_candidate_exceeds_accepted_miniature_allocation",
        "qualification": "NO_GO",
        "actual_campaign_headroom": "UNKNOWN",
        "outer_run_ceiling": 24,
        "outer_capture_ceiling": 72,
        "native_gaps": ["exact___cf_kv_vs_pinned__cf_KV", "D1__cf_METADATA_SQLITE_AUTH"],
        "dispatch_enabled": False,
    }
