"""Separately approved read-only metadata evidence; never a hosted-run grant.

Import and the disabled CLI perform no I/O. The trusted parent must independently
retain genuine human approval before invoking ``run``. JSON bindings preserve
that decision's scope; they cannot authenticate who made it. Injected adapters
are trusted synthetic test code, not an alternative approval boundary.
"""

from __future__ import annotations

import calendar
import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_execution as offline
from scripts import prepare_hosted_publisher_runtime as packet
from scripts.hosted_publisher_execution import _assert_private, _private_bytes
from scripts.hosted_publisher_execution_provider import _address, _pinned_https
from scripts.hosted_publisher_finite_client import Request, Response, UnknownOutcome
from scripts.hosted_publisher_operator import DurableJournal, OperatorRefused
from scripts.hosted_publisher_provider import ProviderError

SOURCE_FILES = tuple(
    sorted(set(packet.SOURCE_FILES) | {"scripts/collect_publisher_grant_metadata.py"})
)
ACTIONS = (
    "verify_test_credential",
    "verify_metadata_reader",
    "read_test_token_details_once",
)
ORIGIN = "https://api.cloudflare.com"
VERIFY_PATH = "/client/v4/user/tokens/verify"
MAX_RESPONSE_BYTES = 65536
MAX_TOTAL_RESPONSE_BYTES = 3 * MAX_RESPONSE_BYTES
MAX_WINDOW_SECONDS = 1200
_TIME_SCALE = 10**18
_HASH = r"[0-9a-f]{64}"
_ID = r"[0-9a-f]{32}"
_TIME = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d{1,18})?Z\Z")

# Exception messages are untrusted, including those raised by injected adapters.
# Only these exact existing refusal codes may cross the diagnostic boundary.
_DIAGNOSTIC_REFUSALS = frozenset(
    """
    metadata_closed_shape_required metadata_text_refused metadata_provider_text_refused
    metadata_timestamp_refused metadata_clock_refused metadata_json_refused
    metadata_document_changed metadata_running_source_mismatch
    metadata_collector_uncommitted_or_changed metadata_source_digest_mismatch
    metadata_reviewed_python_required metadata_absolute_path_required metadata_exact_plan_required
    metadata_window_closed metadata_canonical_global_pin_required
    metadata_independent_approval_required metadata_owner_provisioned_required
    metadata_human_evidence_mismatch metadata_approval_expired_or_unrecorded
    metadata_paths_must_be_distinct metadata_private_storage_outside_source_required
    metadata_credential_custody_refused metadata_fresh_sinks_required metadata_policy_depth_refused
    metadata_policy_width_refused metadata_policy_type_refused metadata_details_identity_mismatch
    metadata_details_time_mismatch metadata_issue_expiry_refused metadata_details_time_refused
    metadata_complete_policies_required metadata_policy_refused metadata_permission_groups_required
    metadata_permission_meta_refused metadata_ip_condition_refused metadata_provider_nonsuccess
    metadata_response_headers_or_private_material_refused metadata_private_material_refused
    metadata_success_envelope_required metadata_messages_refused metadata_message_refused
    metadata_active_verify_required metadata_monotonic_clock_refused
    metadata_remaining_budget_exhausted metadata_authority_changed metadata_replay_forbidden
    metadata_raw_ascii_credential_required metadata_distinct_credentials_required
    metadata_verified_identity_required metadata_request_budget_exhausted
    metadata_wire_accounting_refused metadata_late_response metadata_distinct_provider_ids_required
    metadata_evidence_size_refused metadata_evidence_sink_changed
    private_file_security_unavailable private_file_owner_or_acl_refused
    private_file_acl_form_refused private_file_broad_access_refused private_input_not_regular
    private_input_hardlink_refused private_input_permissions_refused private_input_size_refused
    private_input_changed
    invalid_plan_digest journal_link_refused journal_owner_busy journal_plan_mismatch
    journal_closed journal_invalid_key journal_intent_bound journal_terminal_or_missing
    journal_invalid_reason journal_metadata_depth journal_metadata_width
    journal_private_material_refused journal_metadata_type journal_metadata_encoding
    journal_metadata_size
    execution_numeric_address_required execution_public_address_required
    execution_request_limits_invalid execution_admission_deadline execution_dispatch_deadline
    execution_response_deadline execution_response_wire_limit execution_response_stream_mode
    execution_header_syntax_invalid execution_status_or_interim_refused
    execution_bodyless_status_refused execution_header_limit execution_duplicate_response_header
    execution_duplicate_response_header_framing execution_duplicate_response_header_content
    execution_duplicate_response_header_auth execution_duplicate_response_header_other
    execution_trailer_limit execution_trailer_field_refused execution_chunk_separator_invalid
    execution_chunk_size_invalid execution_response_framing_or_redirect
    execution_response_framing_missing execution_response_body_limit execution_response_incomplete
    """.split()
)
_DIAGNOSTIC_BOUNDARY_REFUSALS = {
    "Linked private input root or ancestor refused": "private_input_link_refused",
    "Bounded execution packet file required": "source_file_bound_refused",
    "Execution packet file changed during bounded read": "source_file_changed",
    "Exact separately reviewed committed source required": "source_commit_refused",
    "Only committed regular source is allowed": "source_regular_commit_required",
    "Incomplete execution-source closure": "source_closure_incomplete",
    "Execution source differs from reviewed commit": "source_commit_mismatch",
}
_DIAGNOSTIC_STAGES = frozenset(
    {
        "inputs",
        "clock",
        "claim",
        "journal",
        "evidence_create",
        "credentials",
        "address",
        "evidence_write",
        "collection_receipt",
        "unknown",
    }
    | {
        f"request{index}_{step}"
        for index in (1, 2, 3)
        for step in ("fence", "prepare", "transport", "validate", "receipt")
    }
)


class MetadataCollectionRefused(OperatorRefused):
    """Counts and closed diagnostics only; never retain the original exception."""

    def __init__(self, stage, error, requests=0, response_wire_bytes=0):
        self.stage = stage if stage in _DIAGNOSTIC_STAGES else "unknown"
        self.category, self.cause = _failure_cause(error, self.stage)
        self.diagnostic = f"metadata_failed:{self.stage}:{self.category}:{self.cause}"
        self.requests = requests
        self.response_wire_bytes = response_wire_bytes
        super().__init__("metadata_collection_failed_no_replay_manual_revocation_required")


def _failure_cause(error, stage):
    error_type = type(error)
    if error_type is ValueError:
        args = error.args
        if len(args) == 1 and type(args[0]) is str:
            cause = _DIAGNOSTIC_BOUNDARY_REFUSALS.get(args[0])
            if cause is not None:
                return "refusal", cause
    if any(error_type is kind for kind in (OperatorRefused, ProviderError, UnknownOutcome)):
        args = error.args
        if len(args) == 1 and type(args[0]) is str and args[0] in _DIAGNOSTIC_REFUSALS:
            return "refusal", args[0]
        return "refusal", "unrecognized"
    if issubclass(error_type, ssl.SSLCertVerificationError):
        return "tls", "certificate_verification"
    if issubclass(error_type, ssl.SSLError):
        return "tls", "handshake_or_protocol"
    if issubclass(error_type, TimeoutError):
        return "timeout", "deadline_or_socket"
    for kind, cause in (
        (ConnectionRefusedError, "connection_refused"),
        (ConnectionResetError, "connection_reset"),
        (ConnectionAbortedError, "connection_aborted"),
        (BrokenPipeError, "broken_pipe"),
    ):
        if issubclass(error_type, kind):
            return "network", cause
    if issubclass(error_type, http.client.HTTPException):
        return "http", "protocol_or_incomplete"
    if issubclass(error_type, OSError):
        if stage.endswith("_transport"):
            return "network", "io_error"
        for kind, cause in (
            (PermissionError, "permission_denied"),
            (FileNotFoundError, "not_found"),
            (FileExistsError, "already_exists"),
        ):
            if issubclass(error_type, kind):
                return "storage", cause
        return "storage", "io_error"
    if issubclass(error_type, (KeyboardInterrupt, SystemExit)):
        return "interrupted", "process_interrupted"
    return "unexpected", "unclassified"


def _record_failure(journal, key, failure):
    # Failure to write a terminal receipt must not erase the original bounded
    # cause. The existing claim and intent remain spent, including on this path.
    try:
        journal.unknown(key, failure.diagnostic)
    except BaseException:
        pass


@dataclass(frozen=True)
class RuntimeInputs:
    plan: Path
    plan_digest: str
    approval: Path
    approval_digest: str
    human_evidence: Path
    source_root: Path


def _closed(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() <= set(required) | set(
        optional
    ):
        raise OperatorRefused("metadata_closed_shape_required")
    return value


def _text(value, maximum=1024, pattern=None):
    if (
        type(value) is not str
        or not 0 < len(value) <= maximum
        or not value.isascii()
        or any(ord(char) < 32 or ord(char) > 126 for char in value)
        or (pattern is not None and re.fullmatch(pattern, value) is None)
    ):
        raise OperatorRefused("metadata_text_refused")
    return value


def _provider_text(value, maximum=4096, *, allow_empty=False):
    """Retain bounded printable Unicode; private provider names need not be ASCII."""
    if type(value) is not str or (not value and not allow_empty):
        raise OperatorRefused("metadata_provider_text_refused")
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeError:
        raise OperatorRefused("metadata_provider_text_refused") from None
    if size > maximum or (value and not value.isprintable()):
        raise OperatorRefused("metadata_provider_text_refused")
    return value


def _timestamp(value):
    """Compare exact bounded RFC3339 fractions without datetime truncation."""
    match = _TIME.fullmatch(value) if type(value) is str else None
    if match is None:
        raise OperatorRefused("metadata_timestamp_refused")
    try:
        whole = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S")
        fraction = (match[2] or ".")[1:].ljust(18, "0")
        return calendar.timegm(whole.timetuple()) * _TIME_SCALE + int(fraction)
    except ValueError, OverflowError:
        raise OperatorRefused("metadata_timestamp_refused") from None


def _now(clock):
    value = clock()
    if type(value) not in (int, float) or not math.isfinite(value):
        raise OperatorRefused("metadata_clock_refused")
    numerator, denominator = Decimal(str(value)).as_integer_ratio()
    return numerator * _TIME_SCALE // denominator


def _json(raw):
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=boundary._no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except ValueError, UnicodeError, RecursionError:
        raise OperatorRefused("metadata_json_refused") from None


def _document(path, digest):
    _text(digest, 64, _HASH)
    raw = _private_bytes(path, 262144)
    if boundary.sha2_256(raw) != digest:
        raise OperatorRefused("metadata_document_changed")
    return _json(raw)


def _validate_source(root, plan):
    """Byte-bind the running source and its complete existing runtime closure."""
    if root.resolve(strict=True) != Path(__file__).resolve().parents[1]:
        raise OperatorRefused("metadata_running_source_mismatch")
    expected = _closed(plan["source_sha2_256"], set(SOURCE_FILES))
    files = {name: packet.bounded_read(root, name, 16777216) for name in SOURCE_FILES}
    packet.source_identity(
        root, plan["source_commit"], {name: files[name] for name in packet.SOURCE_FILES}
    )
    name = "scripts/collect_publisher_grant_metadata.py"
    line = offline._git(root, "ls-tree", plan["source_commit"], "--", name).splitlines()
    identity = hashlib.sha1(
        b"blob " + str(len(files[name])).encode() + b"\0" + files[name]
    ).hexdigest()
    if line not in ([f"100644 blob {identity}\t{name}"], [f"100755 blob {identity}\t{name}"]):
        raise OperatorRefused("metadata_collector_uncommitted_or_changed")
    if any(boundary.sha2_256(raw) != expected[name] for name, raw in files.items()):
        raise OperatorRefused("metadata_source_digest_mismatch")
    if (
        files[".python-version"].decode("ascii").strip() != ".".join(map(str, sys.version_info[:3]))
        or sys.implementation.name != "cpython"
    ):
        raise OperatorRefused("metadata_reviewed_python_required")


def _path(value):
    path = Path(_text(value, 1024))
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise OperatorRefused("metadata_absolute_path_required")
    boundary._refuse_links(path)
    return path


def validate_inputs(inputs, *, now=None, initial=True):
    """Only nonsecret documents, source and credential security metadata are read."""
    now = _now(time.time) if now is None else now
    plan = _closed(
        _document(inputs.plan, inputs.plan_digest),
        {
            "schema_version",
            "purpose",
            "owner",
            "source_commit",
            "source_sha2_256",
            "starts_at",
            "expires_at",
            "api_address",
            "test_credential",
            "reader_credential",
            "evidence",
            "journal",
            "claim",
            "discovery",
            "actions",
        },
    )
    if (
        type(plan["schema_version"]) is not int
        or plan["schema_version"] != 1
        or plan["purpose"] != "publisher_grant_metadata_evidence"
        or plan["discovery"] != "test_verify_id_only"
        or plan["actions"] != list(ACTIONS)
    ):
        raise OperatorRefused("metadata_exact_plan_required")
    _text(plan["owner"], 128)
    _text(plan["source_commit"], 40, r"[0-9a-f]{40}")
    start, end = _timestamp(plan["starts_at"]), _timestamp(plan["expires_at"])
    if not start <= now < end or not 0 < end - start <= MAX_WINDOW_SECONDS * _TIME_SCALE:
        raise OperatorRefused("metadata_window_closed")
    address = _address(plan["api_address"])
    if str(address) != plan["api_address"] or address.is_multicast:
        raise OperatorRefused("metadata_canonical_global_pin_required")
    _validate_source(inputs.source_root, plan)
    approval = _closed(
        _document(inputs.approval, inputs.approval_digest),
        {
            "schema_version",
            "granted",
            "owner",
            "decision_id",
            "plan_digest",
            "source_commit",
            "human_approval",
            "owner_provisioned",
            "reader_policy_limitation_acknowledged",
            "revocation_acknowledged",
            "actions",
            "expires_at",
        },
    )
    if (
        type(approval["schema_version"]) is not int
        or approval["schema_version"] != 1
        or approval["granted"] is not True
        or approval["owner"] != plan["owner"]
        or approval["plan_digest"] != inputs.plan_digest
        or approval["source_commit"] != plan["source_commit"]
        or approval["actions"] != list(ACTIONS)
        or approval["reader_policy_limitation_acknowledged"] is not True
        or approval["revocation_acknowledged"] is not True
    ):
        raise OperatorRefused("metadata_independent_approval_required")
    _text(approval["decision_id"], 128, r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
    provisioned = _closed(approval["owner_provisioned"], {"test", "reader"})
    if any(value is not True for value in provisioned.values()):
        raise OperatorRefused("metadata_owner_provisioned_required")
    human = _closed(approval["human_approval"], {"reference", "evidence_sha2_256", "recorded_at"})
    _text(human["reference"], 256)
    _text(human["evidence_sha2_256"], 64, _HASH)
    if (
        boundary.sha2_256(_private_bytes(inputs.human_evidence, 262144))
        != human["evidence_sha2_256"]
    ):
        raise OperatorRefused("metadata_human_evidence_mismatch")
    if not _timestamp(human["recorded_at"]) <= now < _timestamp(approval["expires_at"]) <= end:
        raise OperatorRefused("metadata_approval_expired_or_unrecorded")
    paths = {
        name: _path(plan[name])
        for name in ("test_credential", "reader_credential", "evidence", "journal", "claim")
    }
    paths["journal_owner"] = Path(str(paths["journal"]) + ".owner")
    paths["journal_sidecar"] = Path(str(paths["journal"]) + "-journal")
    # Authority and credential/output paths must never alias, including lexical aliases.
    all_paths = [*paths.values(), inputs.plan, inputs.approval, inputs.human_evidence]
    names = [os.path.normcase(str(path.resolve())) for path in all_paths]
    if len(names) != len(set(names)):
        raise OperatorRefused("metadata_paths_must_be_distinct")
    source = inputs.source_root.resolve(strict=True)
    for path in paths.values():
        boundary._refuse_links(path)
        _assert_private(path.parent, directory=True)
        if path.resolve().is_relative_to(source):
            raise OperatorRefused("metadata_private_storage_outside_source_required")
    for role in ("test_credential", "reader_credential"):
        _assert_private(paths[role])
        if not 20 <= paths[role].stat().st_size <= 2048:
            raise OperatorRefused("metadata_credential_custody_refused")
    for role in ("evidence", "journal", "claim", "journal_owner", "journal_sidecar"):
        if paths[role].exists():
            if initial:
                raise OperatorRefused("metadata_fresh_sinks_required")
            _assert_private(paths[role])
    return plan, approval


def _bounded_tree(value, depth=0, *, allow_empty=False):
    """Preserve provider resource expressions without projecting or truncating them."""
    if depth > 6:
        raise OperatorRefused("metadata_policy_depth_refused")
    if type(value) is dict:
        if not (0 if allow_empty else 1) <= len(value) <= 64:
            raise OperatorRefused("metadata_policy_width_refused")
        for key, child in value.items():
            _provider_text(key)
            _bounded_tree(child, depth + 1, allow_empty=allow_empty)
    elif type(value) is list:
        if not (0 if allow_empty else 1) <= len(value) <= 64:
            raise OperatorRefused("metadata_policy_width_refused")
        for child in value:
            _bounded_tree(child, depth + 1, allow_empty=allow_empty)
    elif type(value) is str:
        _provider_text(value, allow_empty=allow_empty)
    else:
        raise OperatorRefused("metadata_policy_type_refused")


def _validate_details(result, verified, now):
    _closed(
        result,
        {"id", "name", "status", "issued_on", "expires_on", "not_before", "policies"},
        {"modified_on", "last_used_on", "condition"},
    )
    _provider_text(result["name"], 480)
    if result["id"] != verified["id"] or result["status"] != "active":
        raise OperatorRefused("metadata_details_identity_mismatch")
    for field in ("expires_on", "not_before"):
        if _timestamp(result[field]) != _timestamp(verified[field]):
            raise OperatorRefused("metadata_details_time_mismatch")
    issued, expiry = _timestamp(result["issued_on"]), _timestamp(result["expires_on"])
    if not issued <= now < expiry or _timestamp(result["not_before"]) > now:
        raise OperatorRefused("metadata_issue_expiry_refused")
    for field in ("modified_on", "last_used_on"):
        if field in result and result[field] is not None:
            if not issued <= _timestamp(result[field]) <= now:
                raise OperatorRefused("metadata_details_time_refused")
    policies = result["policies"]
    if type(policies) is not list or not 0 < len(policies) <= 16:
        raise OperatorRefused("metadata_complete_policies_required")
    for policy in policies:
        _closed(policy, {"effect", "permission_groups", "resources"}, {"id"})
        if "id" in policy:
            _text(policy["id"], 32, _ID)
        if policy["effect"] not in ("allow", "deny") or type(policy["resources"]) is not dict:
            raise OperatorRefused("metadata_policy_refused")
        _bounded_tree(policy["resources"])
        groups = policy["permission_groups"]
        if type(groups) is not list or not 0 < len(groups) <= 64:
            raise OperatorRefused("metadata_permission_groups_required")
        for group in groups:
            _closed(group, {"id"}, {"name", "meta"})
            _text(group["id"], 32, _ID)
            if "name" in group:
                _provider_text(group["name"], 480, allow_empty=True)
            if "meta" in group:
                if type(group["meta"]) is not dict:
                    raise OperatorRefused("metadata_permission_meta_refused")
                _bounded_tree(group["meta"], allow_empty=True)
    if "condition" in result:
        condition = _closed(result["condition"], set(), {"request_ip"})
        if "request_ip" in condition:
            ip_rules = _closed(condition["request_ip"], set(), {"in", "not_in"})
            for rules in ip_rules.values():
                if type(rules) is not list or not 0 <= len(rules) <= 64:
                    raise OperatorRefused("metadata_ip_condition_refused")
                for network in rules:
                    _text(network, 128)
                    try:
                        ipaddress.ip_network(network, strict=False)
                    except ValueError:
                        raise OperatorRefused("metadata_ip_condition_refused") from None


def validate_response(response: Response, *, details=False, verified=None, now, credentials=()):
    if type(response.status) is not int or response.status != 200:
        raise OperatorRefused("metadata_provider_nonsuccess")
    headers = {key.lower(): value for key, value in response.headers.items()}
    if (
        len(headers) != len(response.headers)
        or headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"
        or headers.get("content-encoding", "identity").lower() != "identity"
        or "location" in headers
        or any(secret.encode("ascii") in response.body for secret in credentials)
    ):
        raise OperatorRefused("metadata_response_headers_or_private_material_refused")
    value = _closed(_json(response.body), {"success", "errors", "messages", "result"})
    # Check decoded strings too: JSON escapes must not smuggle a credential into
    # otherwise valid provider names/messages/resource expressions in evidence.
    if any(secret.encode("ascii") in boundary.encoded(value) for secret in credentials):
        raise OperatorRefused("metadata_private_material_refused")
    if value["success"] is not True or value["errors"] != []:
        raise OperatorRefused("metadata_success_envelope_required")
    messages = value["messages"]
    if type(messages) is not list or len(messages) > 16:
        raise OperatorRefused("metadata_messages_refused")
    for message in messages:
        _closed(message, {"code", "message"}, {"type", "documentation_url", "source"})
        if type(message["code"]) is not int or not 1000 <= message["code"] <= 999999:
            raise OperatorRefused("metadata_message_refused")
        _provider_text(message["message"])
        for key in ("type", "documentation_url"):
            if key in message and message[key] is not None:
                _provider_text(message[key], allow_empty=True)
        if "source" in message:
            source = _closed(message["source"], set(), {"pointer"})
            if "pointer" in source:
                _provider_text(source["pointer"], allow_empty=True)
    result = value["result"]
    if details:
        _validate_details(result, verified, now)
    else:
        _closed(result, {"id", "status", "expires_on", "not_before"})
        _text(result["id"], 32, _ID)
        if result["status"] != "active" or not (
            _timestamp(result["not_before"]) <= now < _timestamp(result["expires_on"])
        ):
            raise OperatorRefused("metadata_active_verify_required")
    return value


def _create_private(path, raw=b""):
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOINHERIT", 0),
        0o600,
    )
    try:
        _assert_private(path)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _run_context(inputs, wall_clock, monotonic):
    stage = "inputs"
    try:
        plan, approval = validate_inputs(inputs, now=_now(wall_clock))
        stage = "clock"
        started = monotonic()
        if type(started) not in (int, float) or not math.isfinite(started):
            raise OperatorRefused("metadata_monotonic_clock_refused")
        deadline = started + min(
            MAX_WINDOW_SECONDS,
            (
                min(_timestamp(plan["expires_at"]), _timestamp(approval["expires_at"]))
                - _now(wall_clock)
            )
            / _TIME_SCALE,
        )
        return plan, approval, started, deadline
    except BaseException as error:
        failure = MetadataCollectionRefused(stage, error)
    raise failure from None


def run(
    inputs,
    *,
    wall_clock=time.time,
    monotonic=time.monotonic,
    transport=None,
    credential_loader=None,
):
    """Consume one fresh private claim and collect at most three GET responses.

    Return counts only. Exact provider evidence and fingerprints remain in the
    approved private evidence file. Failures expose closed diagnostics and counts
    only. Any failure after claiming spends the claim and journal; the caller
    handles revocation and must never automatically replay this run.
    """
    plan, approval, started, deadline = _run_context(inputs, wall_clock, monotonic)
    stage = "claim"
    credentials = []
    requests = response_bytes = 0
    evidence_path = Path(plan["evidence"])
    fingerprints = {}
    provider_expiries = []

    def fence():
        current = monotonic()
        if not math.isfinite(current) or current < started or current >= deadline:
            raise OperatorRefused("metadata_remaining_budget_exhausted")
        if validate_inputs(inputs, now=_now(wall_clock), initial=False) != (plan, approval):
            raise OperatorRefused("metadata_authority_changed")
        remaining = min(
            deadline - monotonic(),
            (
                min(_timestamp(plan["expires_at"]), _timestamp(approval["expires_at"]))
                - _now(wall_clock)
            )
            / _TIME_SCALE,
        )
        if provider_expiries:
            remaining = min(remaining, (min(provider_expiries) - _now(wall_clock)) / _TIME_SCALE)
        if remaining <= 0:
            raise OperatorRefused("metadata_remaining_budget_exhausted")
        return min(20.0, remaining)

    try:
        # Exclusive persistent claim is never removed, including on partial setup failure.
        stage = "claim"
        _create_private(Path(plan["claim"]), (inputs.plan_digest + "\n").encode("ascii"))
        stage = "journal"
        with DurableJournal(Path(plan["journal"]), inputs.plan_digest) as journal:
            _assert_private(Path(plan["journal"]))
            _assert_private(Path(plan["journal"] + ".owner"))
            if journal.snapshot() or not journal.reserve(
                "metadata:started", {"planDigest": inputs.plan_digest}
            ):
                raise OperatorRefused("metadata_replay_forbidden")
            try:
                stage = "evidence_create"
                _create_private(evidence_path)
                stage = "credentials"
                fence()
                for role in ("test", "reader"):
                    raw = (credential_loader or _private_bytes)(
                        Path(plan[role + "_credential"]), 2048
                    )
                    if (
                        type(raw) is not bytes
                        or re.fullmatch(rb"[A-Za-z0-9_-]{20,2048}", raw) is None
                    ):
                        raise OperatorRefused("metadata_raw_ascii_credential_required")
                    fingerprints[role] = boundary.sha2_256(raw)
                    credentials.append(raw.decode("ascii"))
                    raw = None
                if credentials[0] == credentials[1]:
                    raise OperatorRefused("metadata_distinct_credentials_required")
                responses = {}
                verified = None
                stage = "address"
                address = _address(plan["api_address"])
                for index, phase in enumerate(ACTIONS):
                    stage = f"request{index + 1}_fence"
                    timeout = fence()
                    if index < 2:
                        path = VERIFY_PATH
                    else:
                        if verified is None:
                            raise OperatorRefused("metadata_verified_identity_required")
                        path = "/client/v4/user/tokens/" + verified["id"]
                    key = "metadata:request:" + str(index + 1)
                    if not journal.reserve(key, {"phase": phase}):
                        raise OperatorRefused("metadata_replay_forbidden")
                    try:
                        stage = f"request{index + 1}_prepare"
                        timeout = min(timeout, fence())
                        headers = {
                            "Host": "api.cloudflare.com",
                            "Connection": "close",
                            "Content-Length": "0",
                            "Accept": "application/json",
                            "Accept-Encoding": "identity",
                            "Authorization": "Bearer " + credentials[0 if index == 0 else 1],
                        }
                        wire = (
                            "GET "
                            + path
                            + " HTTP/1.1\r\n"
                            + "".join(f"{name}: {value}\r\n" for name, value in headers.items())
                            + "\r\n"
                        ).encode("ascii")
                        limit = min(MAX_RESPONSE_BYTES, MAX_TOTAL_RESPONSE_BYTES - response_bytes)
                        if requests >= 3 or limit <= 0 or len(wire) > 4096:
                            raise OperatorRefused("metadata_request_budget_exhausted")
                        request = Request(
                            ORIGIN + path,
                            headers,
                            timeout,
                            limit,
                            min(deadline, monotonic() + timeout),
                            wire,
                        )
                        requests += 1
                        stage = f"request{index + 1}_transport"
                        response = (
                            transport(request)
                            if transport is not None
                            # Proposed metadata-only stateless compatibility;
                            # owner acceptance and a fresh exact-source approval
                            # are required before any later live attempt.
                            else _pinned_https(
                                request, address, monotonic, fence, discard_set_cookie=True
                            )
                        )
                        stage = f"request{index + 1}_validate"
                        used = response.wire_bytes
                        if type(used) is not int or not len(response.body) <= used <= limit:
                            raise OperatorRefused("metadata_wire_accounting_refused")
                        response_bytes += used
                        fence()
                        if monotonic() >= request.deadline:
                            raise OperatorRefused("metadata_late_response")
                        checked = validate_response(
                            response,
                            details=index == 2,
                            verified=verified,
                            now=_now(wall_clock),
                            credentials=credentials,
                        )
                        if index == 0:
                            verified = checked["result"]
                        elif index == 1 and (
                            verified is None or checked["result"]["id"] == verified["id"]
                        ):
                            raise OperatorRefused("metadata_distinct_provider_ids_required")
                        if index < 2:
                            provider_expiries.append(_timestamp(checked["result"]["expires_on"]))
                        responses[phase] = checked
                        stage = f"request{index + 1}_receipt"
                        journal.complete(key, {"status": "response_retained_privately"})
                    except BaseException as error:
                        _record_failure(
                            journal,
                            key,
                            MetadataCollectionRefused(stage, error, requests, response_bytes),
                        )
                        raise
                stage = "evidence_write"
                fence()
                evidence = {
                    "schema_version": 1,
                    "purpose": "provider_metadata_evidence_only",
                    "plan_digest": inputs.plan_digest,
                    "approval_digest": inputs.approval_digest,
                    "source_commit": plan["source_commit"],
                    "responses": responses,
                    "credential_sha2_256": fingerprints,
                    "limitations": [
                        "reader_full_policy_not_observed",
                        "not_execution_authority",
                        "human_provenance_external",
                        "manual_revocation_required",
                    ],
                }
                raw_evidence = boundary.encoded(evidence)
                if len(raw_evidence) > 262144:
                    raise OperatorRefused("metadata_evidence_size_refused")
                _assert_private(evidence_path)
                before = evidence_path.stat()
                if before.st_size != 0:
                    raise OperatorRefused("metadata_evidence_sink_changed")
                with evidence_path.open("r+b") as stream:
                    opened = os.fstat(stream.fileno())
                    if (opened.st_dev, opened.st_ino, opened.st_size) != (
                        before.st_dev,
                        before.st_ino,
                        0,
                    ):
                        raise OperatorRefused("metadata_evidence_sink_changed")
                    stream.write(raw_evidence)
                    stream.flush()
                    os.fsync(stream.fileno())
                _assert_private(evidence_path)
                stage = "collection_receipt"
                journal.complete(
                    "metadata:started",
                    {
                        "status": "evidence_collected",
                        "requests": requests,
                        "responseWireBytes": response_bytes,
                    },
                )
                return {
                    "status": "evidence_collected",
                    "requests": requests,
                    "response_wire_bytes": response_bytes,
                }
            except BaseException as error:
                _record_failure(
                    journal,
                    "metadata:started",
                    MetadataCollectionRefused(stage, error, requests, response_bytes),
                )
                raise
    except BaseException as error:
        failure = MetadataCollectionRefused(stage, error, requests, response_bytes)
    finally:
        credentials.clear()
        fingerprints.clear()
    # Raise outside the handler, so the sanitized exception does not retain the
    # original exception (or its potentially private text) as __context__.
    raise failure from None


def main():
    raise SystemExit("NO-GO: metadata collection requires separately retained human approval.")


if __name__ == "__main__":
    main()
