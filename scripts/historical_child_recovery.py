"""Explicitly injected historical-child recovery boundary; CLI/import are inert.

No concrete evidence reader, source importer, credential loader or transport is
provided here. A trusted operator supplies independently reviewed adapters.
Hash-bound statements do not authenticate present facts or an owner decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Protocol

PARENT_CUTOFF = "2026-10-26T12:00:00Z"
DECISION = "call_8562d3b067e14c66ba2f351e1ea50eb2"
CONTRACT = "call_85ff42c39e6343dcbd60e8d1d7ee6c32"
PRODUCER_PIN = "1761e3c8b91bc9846eb2b332f0c4a275c9aba07f9cdb903374035231465aa286"
SOURCE_MANIFEST = "probes/group-post-characterization/screenshot-successor-manifest.json"
MAX_REQUESTS = 5
MAX_REQUEST_BYTES = 40960
MAX_RESPONSE_BYTES = 262144
MAX_TOTAL_RESPONSE_BYTES = 1310720
MAX_CALL_SECONDS = 20
MAX_WINDOW_SECONDS = 600
HISTORY = frozenset(
    {
        "terminal",
        "stop",
        "closure",
        "session",
        "issuerPlan",
        "issuerApproval",
        "issuerEvidence",
        "issuerJournalSnapshot",
        "issuerReview",
        "issuerAuthority",
        "sourceManifest",
        "sourceReview",
    }
)
CURRENT = frozenset({"witness", "authority", "judgment"})
OUTPUTS = {
    "plan": "plan.json",
    "approval": "approval.json",
    "binding": "binding.json",
    "packetReview": "packet-review.json",
    "claim": "claim.json",
    "journal": "journal.sqlite",
    "journalOwner": "journal.sqlite.owner",
    "journalRollback": "journal.sqlite-journal",
    "journalWal": "journal.sqlite-wal",
    "journalShm": "journal.sqlite-shm",
    "evidence": "evidence.jsonl",
}
ROLES = (
    HISTORY
    | CURRENT
    | set(OUTPUTS)
    | {
        "parentCredential",
        "childCredential",
        "issuerJournal",
        "issuerOwner",
        "issuerRollback",
        "issuerWal",
        "issuerShm",
    }
)
REQUEST_FIELDS = {
    "schemaVersion",
    "contract",
    "recoveryId",
    "originalRunId",
    "childId",
    "parentId",
    "startsAt",
    "endsAt",
    "namespace",
    "oldNamespace",
    "roles",
    "pins",
    "sourcePins",
    "sourceRoot",
    "controllerSource",
}
ISSUE_FIELDS = {
    "schema_version",
    "purpose",
    "owner",
    "operation",
    "profile",
    "account_id",
    "source_commit",
    "source_sha2_256",
    "starts_at",
    "expires_at",
    "cleanup_at",
    "child_expires_at",
    "child_name",
    "child_condition",
    "parent_condition",
    "parent_id",
    "parent_sha2_256",
    "api_address",
    "parent_credential",
    "child_credential",
    "claim",
    "journal",
    "evidence",
    "retention_until",
    "revoker",
    "issuance",
    "request_limit",
    "request_byte_limit",
    "response_byte_limit",
}


class Refused(ValueError):
    """Stable diagnostics; no caller/provider exception text is retained."""


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _closed(value: Any, keys: set[str] | frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise Refused("closed_record_required")
    return value


def document(raw: bytes) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refused("duplicate_field")
            result[key] = value
        return result

    if type(raw) is not bytes or not 0 < len(raw) <= 16777216:
        raise Refused("bounded_metadata_bytes_required")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        encoded(value)
    except ValueError, UnicodeError, TypeError:
        raise Refused("strict_json_required") from None
    if type(value) is not dict:
        raise Refused("object_required")
    return value


def _text(value: Any, pattern: str = r"[^\x00-\x1f\x7f]{1,256}") -> str:
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise Refused("exact_text_required")
    return value


def stamp(value: Any) -> datetime:
    _text(value, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        raise Refused("utc_timestamp_required") from None


def _path(value: Any) -> PureWindowsPath:
    _text(value, r"[A-Z]:/[^\x00-\x1f\x7f\\:]{1,2048}")
    path = PureWindowsPath(value)
    if (
        path.as_posix() != value
        or ".." in path.parts
        or not path.is_absolute()
        or any(part.endswith((".", " ")) or "~" in part for part in path.parts[1:])
        or any(
            re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?", part)
            for part in path.parts[1:]
        )
    ):
        raise Refused("canonical_local_path_required")
    return path


@dataclass(frozen=True)
class RoleState:
    """Trusted, current, exact-role inventory result; never a directory listing."""

    exists: bool
    identity: str | None
    private: bool
    regular: bool
    links: int
    reparse: bool


class EvidenceVerifier(Protocol):
    def inventory(self, roles: dict[str, str], namespace: str) -> dict[str, RoleState]: ...

    def source_closure(self, pins: dict[str, str]) -> None:
        """Check all reviewed source/import bytes before any protected read/import."""
        ...

    def read_metadata(self, role: str, path: str, limit: int) -> bytes: ...

    def authenticate(self, kind: str, context: bytes, records: dict[str, bytes]) -> None:
        """Authenticate original ownership/history or genuine present evidence.

        Historical: original seven-event issuance, acknowledged child/security
        fields, snapshot/review/source/terminal/stop/closure/session pins.
        Current: identity/custody, full consumer AND cleanup-caller termination,
        permanent no-readmission, preserved unknown resources, actual parent
        lifetime and genuine authority/independent judgment. A flag is no proof.
        """
        ...

    def original_latch(self, journal: str, plan_digest: str, child_id: str) -> dict: ...


class NamespaceWriter(Protocol):
    def reserve_exclusive(self, path: str) -> None: ...

    def create_exclusive(self, path: str, raw: bytes) -> int:
        """Durably flush exact private bytes; retain namespace/partial bytes on error."""
        ...


@dataclass(frozen=True)
class Prepared:
    request: bytes
    plan: bytes
    approval: bytes
    binding: bytes


def _request(raw: bytes, expected_digest: str) -> dict[str, Any]:
    if digest(raw) != _text(expected_digest, r"[a-f0-9]{64}"):
        raise Refused("independently_bound_request_required")
    req = _closed(document(raw), REQUEST_FIELDS)
    if type(req["schemaVersion"]) is not int or req["schemaVersion"] != 1:
        raise Refused("schema_version_required")
    if req["contract"] != CONTRACT:
        raise Refused("accepted_contract_required")
    for key in ("recoveryId", "originalRunId"):
        _text(req[key], r"[a-f0-9]{24}")
        if req[key] == "0" * 24:
            raise Refused("distinct_recovery_identity_required")
    for key in ("childId", "parentId"):
        _text(req[key], r"[a-f0-9]{32}")
    if req["recoveryId"] == req["originalRunId"] or req["childId"] == req["parentId"]:
        raise Refused("distinct_recovery_identity_required")
    _closed(req["roles"], ROLES)
    _closed(req["pins"], HISTORY | CURRENT)
    for pin in req["pins"].values():
        _text(pin, r"[a-f0-9]{64}")
    if type(req["sourcePins"]) is not dict or not req["sourcePins"]:
        raise Refused("complete_source_pins_required")
    for path, pin in req["sourcePins"].items():
        _path(path)
        _text(pin, r"[a-f0-9]{64}")
    source_root = _path(req["sourceRoot"])
    producer_path = (source_root / "scripts/provision_work_plan_token.py").as_posix()
    if req["sourcePins"].get(producer_path) != PRODUCER_PIN:
        raise Refused("unchanged_producer_required")
    controller = _path(req["controllerSource"])
    if (
        controller.name != "historical_child_recovery.py"
        or controller.as_posix() not in req["sourcePins"]
        or controller != _path(str(__file__).replace("\\", "/"))
    ):
        raise Refused("recovery_controller_source_pin_required")
    namespace, old = _path(req["namespace"]), _path(req["oldNamespace"])
    if (
        namespace == old
        or namespace.is_relative_to(old)
        or old.is_relative_to(namespace)
        or namespace.name != "recovery-" + req["recoveryId"]
    ):
        raise Refused("exclusive_recovery_namespace_required")
    paths = {key: _path(value) for key, value in req["roles"].items()}
    manifest = (source_root / SOURCE_MANIFEST).as_posix()
    if req["roles"]["sourceManifest"] != manifest:
        raise Refused("exact_original_source_manifest_required")
    if (
        namespace.is_relative_to(source_root)
        or old.is_relative_to(source_root)
        or any(
            path.is_relative_to(source_root)
            for role, path in paths.items()
            if role != "sourceManifest"
        )
    ):
        raise Refused("private_roles_outside_source_required")
    names = [str(p).casefold() for p in (*paths.values(), namespace, old)]
    if (
        manifest in req["sourcePins"]
        and req["sourcePins"][manifest] != req["pins"]["sourceManifest"]
    ):
        raise Refused("source_manifest_dual_pin_mismatch")
    names += [str(_path(p)).casefold() for p in req["sourcePins"] if p != manifest]
    if len(names) != len(set(names)):
        raise Refused("role_source_alias_refused")
    for role, name in OUTPUTS.items():
        if paths[role] != namespace / name:
            raise Refused("exact_recovery_output_required")
    for role in ROLES - set(OUTPUTS):
        if paths[role].is_relative_to(namespace):
            raise Refused("input_output_alias_refused")
    journal = req["roles"]["issuerJournal"]
    for role, suffix in (
        ("issuerOwner", ".owner"),
        ("issuerRollback", "-journal"),
        ("issuerWal", "-wal"),
        ("issuerShm", "-shm"),
    ):
        if req["roles"][role] != journal + suffix:
            raise Refused("exact_issuer_sidecars_required")
    return req


def _inventory(req: dict, verifier: EvidenceVerifier, *, prepared: bool) -> None:
    states = verifier.inventory(req["roles"], req["namespace"])
    _closed(states, ROLES | {"namespace"})
    identities = []
    absent = {"issuerRollback", "issuerWal", "issuerShm"} | set(OUTPUTS)
    if prepared:
        absent -= {"plan", "approval", "binding", "packetReview"}
    else:
        absent.add("namespace")
    for role, state in states.items():
        if type(state) is not RoleState or type(state.exists) is not bool:
            raise Refused("exact_inventory_required")
        if (
            type(state.private) is not bool
            or type(state.regular) is not bool
            or type(state.reparse) is not bool
            or type(state.links) is not int
        ):
            raise Refused("exact_inventory_required")
        if role in absent:
            if state.exists or state.identity is not None:
                raise Refused("occupied_role_or_sidecar_refused")
        elif (
            not state.exists
            or state.private != (role != "sourceManifest")
            or state.reparse
            or (role != "namespace" and (not state.regular or state.links != 1))
        ):
            raise Refused("private_unlinked_role_required")
        if state.exists:
            identities.append(_text(state.identity))
    if len(identities) != len(set(identities)):
        raise Refused("file_identity_alias_refused")


def source_manifest(raw: bytes) -> dict:
    """Validate fixed original public descriptor schema, never follow its paths."""
    value = _closed(document(raw), {"schemaVersion", "kind", "sources", "productionQualified"})
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "ungranted_screenshot_post_successor"
        or value["productionQualified"] is not False
        or type(value["sources"]) is not dict
        or not 0 < len(value["sources"]) <= 100
    ):
        raise Refused("original_source_manifest_schema_required")
    for name, pin in value["sources"].items():
        _text(name, r"[^\\:\x00-\x1f\x7f]{1,2048}")
        canonical = _path("C:/source/" + name)
        if canonical.as_posix() != "C:/source/" + name or not canonical.is_relative_to(
            _path("C:/source")
        ):
            raise Refused("original_source_manifest_map_required")
        _text(pin, r"[a-f0-9]{64}")
    if len({name.casefold() for name in value["sources"]}) != len(value["sources"]):
        raise Refused("original_source_manifest_map_required")
    return value


def _latch(req: dict, verifier: EvidenceVerifier) -> None:
    state = _closed(
        verifier.original_latch(
            req["roles"]["issuerJournal"], req["pins"]["issuerPlan"], req["childId"]
        ),
        {"key", "planDigest", "childId", "state"},
    )
    if state != {
        "key": "issuer:retire",
        "planDigest": req["pins"]["issuerPlan"],
        "childId": req["childId"],
        "state": "unused",
    }:
        raise Refused("original_retirement_latch_not_unused")


def _window(req: dict, records: dict[str, bytes], now: datetime) -> None:
    if type(now) is not datetime or now.tzinfo != UTC:
        raise Refused("explicit_current_utc_clock_required")
    start, end = stamp(req["startsAt"]), stamp(req["endsAt"])
    if not (
        0 < (end - start).total_seconds() <= MAX_WINDOW_SECONDS
        and start <= now < end <= stamp(PARENT_CUTOFF)
    ):
        raise Refused("finite_current_recovery_window_required")
    witness = _closed(
        document(records["witness"]),
        {
            "observedAt",
            "observer",
            "evidenceReference",
            "parentExpiresAt",
            "providerStatus",
        },
    )
    authority = _closed(
        document(records["authority"]),
        {
            "recordedAt",
            "owner",
            "decisionReference",
            "scopeReference",
        },
    )
    judgment = _closed(
        document(records["judgment"]),
        {
            "recordedAt",
            "author",
            "reviewer",
            "verdict",
            "subjects",
        },
    )
    for value in (
        witness["observer"],
        witness["evidenceReference"],
        authority["owner"],
        authority["decisionReference"],
        authority["scopeReference"],
        judgment["author"],
        judgment["reviewer"],
    ):
        _text(value)
    if (
        witness["providerStatus"] != "UNKNOWN"
        or stamp(witness["parentExpiresAt"]) <= end
        or stamp(witness["parentExpiresAt"]) > stamp(PARENT_CUTOFF)
        or judgment["verdict"] != "pass"
        or judgment["author"].strip().casefold() == judgment["reviewer"].strip().casefold()
    ):
        raise Refused("genuine_independent_current_evidence_required")
    for value in (witness["observedAt"], authority["recordedAt"], judgment["recordedAt"]):
        if not start <= stamp(value) <= now < end:
            raise Refused("current_evidence_outside_interval")
    subjects = {key: value for key, value in req.items() if key != "pins"}
    subjects["pins"] = {k: v for k, v in req["pins"].items() if k != "judgment"}
    if judgment["subjects"] != subjects:
        raise Refused("exact_current_judgment_subjects_required")


def _prepare(
    raw: bytes,
    *,
    expected_digest: str,
    verifier: EvidenceVerifier | None,
    now: datetime,
    prepared: bool,
) -> Prepared:
    """Read metadata only through an explicit trusted seam; return producer bytes.

    Caller-supplied expected_digest must come from independent actual packet
    review, not from the untrusted request itself. No current time defaults.
    """
    if verifier is None:
        raise Refused("trusted_evidence_verifier_required")
    req = _request(raw, expected_digest)
    _inventory(req, verifier, prepared=prepared)
    verifier.source_closure(req["sourcePins"])
    # This check precedes every metadata read, any producer import or bearer read.
    _latch(req, verifier)
    records = {}
    for role in sorted(HISTORY | CURRENT):
        data = verifier.read_metadata(role, req["roles"][role], 16777216)
        if type(data) is not bytes or not 0 < len(data) <= 16777216:
            raise Refused("bounded_metadata_bytes_required")
        if digest(data) != req["pins"][role]:
            raise Refused("metadata_pin_mismatch")
        records[role] = data
    _window(req, records, now)
    verifier.authenticate("historical", raw, {k: records[k] for k in HISTORY})
    verifier.authenticate("current", raw, records)
    issue = _closed(document(records["issuerPlan"]), ISSUE_FIELDS)
    manifest = source_manifest(records["sourceManifest"])
    if any(
        manifest["sources"].get(name) != pin for name, pin in issue["source_sha2_256"].items()
    ) or {
        path: pin
        for path, pin in req["sourcePins"].items()
        if _path(path).is_relative_to(_path(req["sourceRoot"]))
        and path != req["roles"]["sourceManifest"]
    } != {
        (_path(req["sourceRoot"]) / name).as_posix(): pin
        for name, pin in issue["source_sha2_256"].items()
    }:
        raise Refused("original_source_manifest_producer_map_mismatch")
    # Full original issue/approval/evidence/journal validation belongs to the
    # pinned verifier closure; the unchanged producer validates the final plan.
    if (
        issue.get("operation") != "issue"
        or issue.get("issuance") is not None
        or issue.get("parent_id") != req["parentId"]
        or issue.get("parent_credential") != req["roles"]["parentCredential"]
        or issue.get("child_credential") != req["roles"]["childCredential"]
        or issue.get("journal") != req["roles"]["issuerJournal"]
        or issue.get("request_limit") != MAX_REQUESTS
        or issue.get("request_byte_limit") != MAX_REQUEST_BYTES
        or issue.get("response_byte_limit") != MAX_TOTAL_RESPONSE_BYTES
        or stamp(issue["child_expires_at"]) > stamp(req["startsAt"])
        or stamp(issue["retention_until"]) > stamp(PARENT_CUTOFF)
    ):
        raise Refused("exact_original_issue_binding_required")
    rows = [document(line) for line in records["issuerEvidence"].splitlines()]
    details = [row for row in rows if row.get("phase") == "child_details"]
    if len(details) != 1:
        raise Refused("one_historical_child_details_required")
    historical = details[0]["response"]["result"]
    if type(historical) is not dict or historical.get("id") != req["childId"]:
        raise Refused("exact_historical_child_required")
    plan = dict(issue)
    plan.update(
        operation="revoke_expired",
        starts_at=req["startsAt"],
        expires_at=req["endsAt"],
        claim=req["roles"]["claim"],
        journal=req["roles"]["journal"],
        evidence=req["roles"]["evidence"],
        issuance={
            "journal": issue["journal"],
            "plan_digest": req["pins"]["issuerPlan"],
            "child_id": req["childId"],
            "child_details": historical,
            "historical_validation_at": issue["expires_at"],
        },
    )
    plan_bytes = encoded(plan)
    authority = document(records["authority"])
    approval = {
        "schema_version": 1,
        "decision_id": DECISION,
        "plan_digest": digest(plan_bytes),
        "source_commit": issue["source_commit"],
        "owner": issue["owner"],
        "provisioning": "authorized_automated_local_issuance",
        "bootstrap_role": "user_wide_token_management_write_local_only",
        "human_evidence_sha2_256": req["pins"]["authority"],
        "recorded_at": authority["recordedAt"],
        "expires_at": req["endsAt"],
    }
    approval_bytes = encoded(approval)
    binding = encoded(
        {
            "request": digest(raw),
            "plan": digest(plan_bytes),
            "approval": digest(approval_bytes),
            "providerStatus": "UNKNOWN",
            "operation": "revoke_expired",
        }
    )
    return Prepared(raw, plan_bytes, approval_bytes, binding)


def prepare(
    raw: bytes, *, expected_digest: str, verifier: EvidenceVerifier | None = None, now: datetime
) -> Prepared:
    """Prepare only: default has no verifier, no clock, no writes or dispatch."""
    return _prepare(
        raw, expected_digest=expected_digest, verifier=verifier, now=now, prepared=False
    )


def write_preparation(
    packet: Prepared,
    *,
    verifier: EvidenceVerifier,
    writer: NamespaceWriter,
    expected_digest: str,
    now: datetime,
) -> None:
    """Exclusive writes only; a partial attempt is retained and never retried."""
    rebuilt = prepare(packet.request, expected_digest=expected_digest, verifier=verifier, now=now)
    if rebuilt != packet:
        raise Refused("final_packet_drift")
    req = document(packet.request)
    writer.reserve_exclusive(req["namespace"])
    for role, data in (
        ("plan", packet.plan),
        ("approval", packet.approval),
        ("binding", packet.binding),
    ):
        written = writer.create_exclusive(req["roles"][role], data)
        if type(written) is not int or written != len(data):
            raise Refused("partial_preparation_preserved_no_retry")


def dispatch(
    packet: Prepared,
    *,
    expected_digest: str,
    verifier: EvidenceVerifier,
    producer: Any,
    packet_review: bytes,
    clock: Callable[[], datetime],
    monotonic: Callable[[], float],
    transport: Callable | None,
    credential_loader: Callable,
    execute: bool = False,
) -> Any:
    """Explicit trusted handoff only; no default execution adapter or retry.

    All adapter arguments are required. A qualified operator may explicitly pass
    None to select the verified producer's original TLS branch and its private
    send-stage fence; no argument default or ambient module is supplied here.
    The unchanged producer independently
    fences actual calls and reserves the original journal's atomic latch.
    """
    if execute is not True:
        raise Refused("inert_default")
    req = _request(packet.request, expected_digest)
    now = clock()
    rebuilt = _prepare(
        packet.request, expected_digest=expected_digest, verifier=verifier, now=now, prepared=True
    )
    if rebuilt != packet:
        raise Refused("final_packet_drift")
    for role, data in (
        ("plan", packet.plan),
        ("approval", packet.approval),
        ("binding", packet.binding),
        ("packetReview", packet_review),
    ):
        if verifier.read_metadata(role, req["roles"][role], 16777216) != data:
            raise Refused("final_packet_drift")
    current = {role: verifier.read_metadata(role, req["roles"][role], 16777216) for role in CURRENT}
    if any(digest(value) != req["pins"][role] for role, value in current.items()):
        raise Refused("current_pin_drift")
    _window(req, current, now)
    review = _closed(
        document(packet_review),
        {
            "author",
            "reviewer",
            "recordedAt",
            "verdict",
            "subjects",
        },
    )
    for field in ("author", "reviewer"):
        _text(review[field])
    if (
        review["verdict"] != "pass"
        or review["author"].strip().casefold() == review["reviewer"].strip().casefold()
        or not stamp(req["startsAt"]) <= stamp(review["recordedAt"]) <= now
        or review["subjects"]
        != {
            "request": digest(packet.request),
            "plan": digest(packet.plan),
            "approval": digest(packet.approval),
            "binding": digest(packet.binding),
        }
    ):
        raise Refused("independent_actual_packet_review_required")
    verifier.authenticate("dispatch", packet.request, current | {"packetReview": packet_review})
    # Recheck after potentially lengthy evidence authentication. A concurrent
    # competitor is still fenced by the producer's original atomic reservation.
    _latch(req, verifier)
    _window(req, current, clock())
    source_root = _path(req["sourceRoot"])
    origin = (source_root / "scripts/provision_work_plan_token.py").as_posix()
    if _path(str(producer.__file__).replace("\\", "/")) != _path(origin) or (
        producer.MAX_REQUESTS,
        producer.MAX_REQUEST_BYTES,
        producer.MAX_RESPONSE_BYTES,
        producer.MAX_TOTAL_RESPONSE_BYTES,
        producer.MAX_WINDOW,
        producer.PARENT_DEADLINE,
    ) != (
        MAX_REQUESTS,
        MAX_REQUEST_BYTES,
        MAX_RESPONSE_BYTES,
        MAX_TOTAL_RESPONSE_BYTES,
        MAX_WINDOW_SECONDS,
        PARENT_CUTOFF,
    ):
        raise Refused("exact_unchanged_producer_boundary_required")
    plan = document(packet.plan)
    if plan["source_sha2_256"] != {
        name: req["sourcePins"].get((source_root / name).as_posix())
        for name in producer.SOURCE_FILES
    }:
        raise Refused("complete_original_producer_source_pins_required")
    inputs = producer.RuntimeInputs(
        plan=Path(req["roles"]["plan"]),
        plan_digest=digest(packet.plan),
        approval=Path(req["roles"]["approval"]),
        approval_digest=digest(packet.approval),
        human_evidence=Path(req["roles"]["authority"]),
        source_root=Path(req["sourceRoot"]),
    )
    # Exactly one call, no catch/retry/fallback, and no ambient loader/transport.
    return producer.run(
        inputs,
        wall_clock=lambda: clock().timestamp(),
        monotonic=monotonic,
        transport=transport,
        credential_loader=credential_loader,
    )


def main() -> None:
    raise SystemExit("NO-GO: no evidence adapter or executable packet is installed.")


if __name__ == "__main__":
    main()
