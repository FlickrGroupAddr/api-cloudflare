"""Offline fixed-origin budget witness. Never sends requests or authorizes a run."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy

HANDLER_CASES = (
    "png",
    "jpeg",
    "exact-limit",
    "declared-excess",
    "undeclared-excess",
    "upstream-error",
    "truncation",
    "wrong-media",
    "wrong-signature",
    "redirect",
    "stall",
    "missing-auth",
    "bad-auth",
    "bad-query",
    "final-installation",
    "final-link",
    "final-grant",
    "foreign-identity",
    "private-photo",
    "foreign-destination",
)
EDGE_CASES = (
    "edge-redirect-301",
    "edge-redirect-302",
    "edge-redirect-303",
    "edge-redirect-307",
    "edge-redirect-308",
    "edge-wrong-media",
    "edge-malformed-png",
    "edge-truncated-png",
    "edge-declared-excess",
    "edge-undeclared-excess",
)
LIMITS = {"fga": 96, "receiver": 16, "inner_ms": 600_000, "outer_ms": 1_200_000}
# These obligations cannot be relabeled offline-only merely to make the sum fit.
UNBUDGETED_LIVE = (
    "native-decoder-png-jpeg-boundary",
    "backend-abort-disconnect",
    "temporary-exact-public-https-conformance",
    "rollback-exact-public-https-conformance",
    "current-provider-capture-and-edge-readback",
    "provider-secret-restoration-cases-a-b",
    "ordinary-authenticated-safe-reads",
    "production-state-and-paused-gates",
    "disable-restore-delete-independent-readbacks",
)
OFFLINE_ONLY = (
    "source-matrix-unit-tests",
    "synthetic-lua-transport-tests",
    "compiled-route-inventory",
    "exact-configuration-projection",
    "development-http-conformance",
    "artifact-digest-binding",
)
REQUIRED_OBSERVATIONS = (
    *("fault:" + case for case in HANDLER_CASES + EDGE_CASES),
    "browser-navigation",
    "cancel-during-get",
    "stale-result",
    "redirect-arrivals",
    "receiver-report",
    *UNBUDGETED_LIVE,
    *OFFLINE_ONLY,
)


def build_schedule(profile: str = "current") -> dict:
    """Return a finite accounting witness, not a runnable native target."""
    if profile not in ("current", "proposed-shared-discovery"):
        raise ValueError("unknown_profile")
    proposed = profile != "current"
    rows = []
    for case in HANDLER_CASES + EDGE_CASES:
        rows.append(
            {
                "id": "fault:" + case,
                "kind": "live",
                "fga": 2 if proposed else 4,
                "receiver": 0,
                "native_invocations": 0 if proposed else 1,
            }
        )
    rows.extend(
        [
            {
                "id": "browser-navigation",
                "kind": "live",
                "fga": 16,
                "receiver": 0,
                "native_invocations": 0 if proposed else 1,
            },
            {
                "id": "cancel-during-get",
                "kind": "live",
                "fga": 4,
                "receiver": 0,
                "native_invocations": 0 if proposed else 1,
            },
            {
                "id": "stale-result",
                "kind": "live",
                "fga": 4,
                "receiver": 0,
                "native_invocations": 0 if proposed else 1,
            },
            {
                "id": "redirect-arrivals",
                "kind": "live",
                "fga": 5,
                "receiver": 5,
                "native_invocations": 0,
            },
            {
                "id": "receiver-report",
                "kind": "live",
                "fga": 1,
                "receiver": 1,
                "native_invocations": 0,
            },
        ]
    )
    rows.extend(
        {
            "id": key,
            "kind": "live"
            if proposed and key in ("native-decoder-png-jpeg-boundary", "backend-abort-disconnect")
            else "live-unbudgeted",
            "fga": (4 if key == "backend-abort-disconnect" else 0)
            if proposed and key in ("native-decoder-png-jpeg-boundary", "backend-abort-disconnect")
            else None,
            "receiver": 0
            if proposed and key in ("native-decoder-png-jpeg-boundary", "backend-abort-disconnect")
            else None,
            "native_invocations": None,
        }
        for key in UNBUDGETED_LIVE
    )
    if proposed:
        decoder = next(row for row in rows if row["id"] == "native-decoder-png-jpeg-boundary")
        decoder["coverage"] = ["fault:png", "fault:jpeg", "fault:exact-limit"]
        decoder["native_invocations"] = 0
        disconnect = next(row for row in rows if row["id"] == "backend-abort-disconnect")
        disconnect["driver"] = "proposed-independent-fixed-path-disconnect"
        disconnect["native_invocations"] = 0
    rows.extend(
        {"id": key, "kind": "offline-only", "fga": 0, "receiver": 0, "native_invocations": 0}
        for key in OFFLINE_ONLY
    )
    return {
        "schema_version": 1,
        "profile": profile,
        "limits": deepcopy(LIMITS),
        "attempts": 1,
        "consumed_targets": 1,
        "retries": 0,
        "namespace_resets": 0,
        "shared_discovery_fga": 2 if proposed else 0,
        "program_native_invocations": 1 if proposed else 0,
        "report_reserved_fga": 1,
        "report_reserved_receiver": 1,
        "stop_before_ms": 600_000,
        "cleanup_reserve_ms": 600_000,
        "hard_native_total_deadline_proven": False,
        "source_supports_program": False,
        "execution_authorized": False,
        "observations": rows,
    }


def _same_closed_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same_closed_value(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_closed_value(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return actual == expected


def validate_schedule(plan: dict) -> dict:
    """Reject drift and expose known minima, unresolved work and timing limits."""
    errors = []
    if not isinstance(plan, dict) or plan.get("profile") not in (
        "current",
        "proposed-shared-discovery",
    ):
        return {"decision": "no-go", "errors": ["invalid_plan"], "accounting": {}}
    expected = build_schedule(plan["profile"])
    # Exact closed input rejects unknown keys, missing obligations, forged costs,
    # relabeling live work, claimed authority, quota changes and target reuse.
    if not _same_closed_value(plan, expected):
        errors.append("closed_plan_mismatch")
    rows = expected["observations"]
    accounting = {
        "known_fga": sum(row["fga"] or 0 for row in rows) + expected["shared_discovery_fga"],
        "known_receiver": sum(row["receiver"] or 0 for row in rows),
        "known_native_invocations": sum(row["native_invocations"] or 0 for row in rows)
        + expected["program_native_invocations"],
        "fault_fga": sum(row["fga"] for row in rows if row["id"].startswith("fault:")),
        "unbudgeted_live": [row["id"] for row in rows if row["kind"] == "live-unbudgeted"],
        "complete_accounting": False,
    }
    if accounting["known_fga"] > LIMITS["fga"]:
        errors.append("fga_budget_exceeded")
    if accounting["known_native_invocations"] > expected["consumed_targets"]:
        errors.append("consumed_target_cannot_cover_invocations")
    if plan["profile"] != "current":
        errors.append("proposed_program_source_unimplemented")
    errors.extend(
        [
            "required_live_observations_unbudgeted",
            "native_total_deadline_unproven",
            "execution_authorization_absent",
        ]
    )
    return {
        "decision": "no-go",
        "errors": errors,
        "accounting": accounting,
        "deployment_allowed": False,
        "hosted_qualified": False,
        "native_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=("current", "proposed-shared-discovery"), default="current"
    )
    args = parser.parse_args()
    print(json.dumps(validate_schedule(build_schedule(args.profile)), sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
