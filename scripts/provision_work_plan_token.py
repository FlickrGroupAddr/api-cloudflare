"""Finite, local-only bootstrap issuer. Import/CLI never read credentials or connect.

The trusted primary must retain the real owner decision and independently review
the exact packet before calling run. Hash-bound JSON cannot authenticate a human.
Injected adapters are trusted synthetic test seams, never authority substitutes.
"""

from __future__ import annotations

import hashlib
import ipaddress
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from scripts import collect_publisher_grant_metadata as metadata
from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_execution as offline
from scripts import prepare_hosted_publisher_runtime as packet
from scripts.hosted_publisher_execution import _assert_private, _private_bytes
from scripts.hosted_publisher_execution_provider import _address, _pinned_https
from scripts.hosted_publisher_finite_client import Request
from scripts.hosted_publisher_operator import DurableJournal, OperatorRefused

DECISION = "call_8562d3b067e14c66ba2f351e1ea50eb2"
PROFILE = "publisher-d1-workers-account"
BASE = "/client/v4/user/tokens"
SOURCE_FILES = tuple(sorted(set(metadata.SOURCE_FILES) | {"scripts/provision_work_plan_token.py"}))
MAX_WINDOW = 600
MAX_REQUESTS = 5
MAX_REQUEST_BYTES = 5 * 8192
MAX_RESPONSE_BYTES = 262144
MAX_TOTAL_RESPONSE_BYTES = 5 * MAX_RESPONSE_BYTES
PARENT_DEADLINE = "2026-10-26T12:00:00Z"
GROUP_SCOPES = {
    "API Tokens Write": "com.cloudflare.api.user",
    "D1 Write": "com.cloudflare.api.account",
    "Workers Scripts Write": "com.cloudflare.api.account",
}
_closed = metadata._closed
_timestamp = metadata._timestamp
_text = metadata._text
_SCALE = metadata._TIME_SCALE


@dataclass(frozen=True)
class RuntimeInputs:
    plan: Path
    plan_digest: str
    approval: Path
    approval_digest: str
    human_evidence: Path
    source_root: Path


class ProvisioningRefused(OperatorRefused):
    """Closed diagnostic; never retain an adapter exception or provider body."""

    def __init__(self, requests=0, response_bytes=0):
        super().__init__("issuer_stopped_no_replay")
        self.requests = requests
        self.response_bytes = response_bytes


def _validate_source(root, plan):
    metadata._validate_source(
        root,
        plan
        | {
            "source_sha2_256": {
                name: plan["source_sha2_256"][name] for name in metadata.SOURCE_FILES
            }
        },
    )
    name = "scripts/provision_work_plan_token.py"
    raw = packet.bounded_read(root, name, 16777216)
    identity = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    lines = offline._git(root, "ls-tree", plan["source_commit"], "--", name).splitlines()
    if lines not in ([f"100644 blob {identity}\t{name}"], [f"100755 blob {identity}\t{name}"]):
        raise OperatorRefused("issuer_committed_source_required")
    if boundary.sha2_256(raw) != plan["source_sha2_256"][name]:
        raise OperatorRefused("issuer_source_changed")


def _condition(value):
    _closed(value, set(), {"request_ip"})
    if value:
        rules = _closed(value["request_ip"], {"in"})["in"]
        if type(rules) is not list or len(rules) != 1:
            raise OperatorRefused("issuer_single_source_network_required")
        network = ipaddress.ip_network(_text(rules[0], 128), strict=True)
        if str(network) != rules[0] or not network.is_global or network.prefixlen == 0:
            raise OperatorRefused("issuer_source_network_refused")
    return value


def validate_inputs(inputs, *, now, initial=True):
    plan = _closed(
        metadata._document(inputs.plan, inputs.plan_digest),
        {
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
        },
    )
    if (
        type(plan["schema_version"]) is not int
        or plan["schema_version"] != 1
        or plan["purpose"] != "work_plan_local_token_admin"
        or plan["profile"] != PROFILE
        or plan["operation"] not in ("issue", "revoke", "revoke_expired")
        or (plan["request_limit"], plan["request_byte_limit"], plan["response_byte_limit"])
        != (MAX_REQUESTS, MAX_REQUEST_BYTES, MAX_TOTAL_RESPONSE_BYTES)
        or any(
            type(plan[k]) is not int
            for k in ("request_limit", "request_byte_limit", "response_byte_limit")
        )
    ):
        raise OperatorRefused("issuer_exact_plan_required")
    _text(plan["account_id"], 32, metadata._ID)
    if plan["parent_id"] is not None or plan["operation"] != "issue":
        _text(plan["parent_id"], 32, metadata._ID)
    _text(plan["parent_sha2_256"], 64, metadata._HASH)
    _text(plan["source_commit"], 40, r"[0-9a-f]{40}")
    _closed(plan["source_sha2_256"], set(SOURCE_FILES))
    _validate_source(inputs.source_root, plan)
    for key in ("owner", "revoker", "child_name"):
        _text(plan[key], 128)
    _condition(plan["child_condition"])
    _condition(plan["parent_condition"])
    start, end = _timestamp(plan["starts_at"]), _timestamp(plan["expires_at"])
    if not start <= now < end or not 0 < end - start <= MAX_WINDOW * _SCALE:
        raise OperatorRefused("issuer_window_closed")
    child_end = _timestamp(plan["child_expires_at"])
    if plan["operation"] == "revoke_expired" and child_end > now:
        raise OperatorRefused("issuer_expired_child_required")
    cleanup = _timestamp(plan["cleanup_at"])
    if not child_end <= cleanup or not cleanup <= start + 4 * 3600 * _SCALE:
        raise OperatorRefused("issuer_child_cleanup_bound_required")
    if plan["operation"] == "issue" and child_end <= end:
        raise OperatorRefused("issuer_child_remaining_lifetime_required")
    if not cleanup <= _timestamp(plan["retention_until"]) <= _timestamp(PARENT_DEADLINE):
        raise OperatorRefused("issuer_finite_retention_required")
    if str(_address(plan["api_address"])) != plan["api_address"]:
        raise OperatorRefused("issuer_canonical_pin_required")
    approval = _closed(
        metadata._document(inputs.approval, inputs.approval_digest),
        {
            "schema_version",
            "decision_id",
            "plan_digest",
            "source_commit",
            "owner",
            "provisioning",
            "bootstrap_role",
            "human_evidence_sha2_256",
            "recorded_at",
            "expires_at",
        },
    )
    if (
        type(approval["schema_version"]) is not int
        or approval["schema_version"] != 1
        or approval["decision_id"] != DECISION
        or approval["owner"] != plan["owner"]
        or approval["plan_digest"] != inputs.plan_digest
        or approval["source_commit"] != plan["source_commit"]
        or approval["provisioning"] != "authorized_automated_local_issuance"
        or approval["bootstrap_role"] != "user_wide_token_management_write_local_only"
        or boundary.sha2_256(_private_bytes(inputs.human_evidence))
        != approval["human_evidence_sha2_256"]
        or not _timestamp(approval["recorded_at"])
        <= now
        < _timestamp(approval["expires_at"])
        <= end
    ):
        raise OperatorRefused("issuer_real_decision_binding_required")
    paths = {
        key: metadata._path(plan[key])
        for key in ("parent_credential", "child_credential", "claim", "journal", "evidence")
    }
    paths["journal_owner"] = Path(plan["journal"] + ".owner")
    paths["journal_sidecar"] = Path(plan["journal"] + "-journal")
    if plan["operation"] == "issue":
        if plan["issuance"] is not None:
            raise OperatorRefused("issuer_no_adoption")
    else:
        ref_fields = {"journal", "plan_digest", "child_id"}
        if plan["operation"] == "revoke_expired":
            ref_fields |= {"child_details", "historical_validation_at"}
        ref = _closed(plan["issuance"], ref_fields)
        paths["issuance_journal"] = metadata._path(ref["journal"])
        paths["issuance_owner"] = Path(ref["journal"] + ".owner")
        paths["issuance_sidecar"] = Path(ref["journal"] + "-journal")
        _text(ref["plan_digest"], 64, metadata._HASH)
        _text(ref["child_id"], 32, metadata._ID)
        if ref["child_id"] == plan["parent_id"]:
            raise OperatorRefused("issuer_parent_not_child")
        if plan["operation"] == "revoke_expired":
            historical = ref["child_details"]
            verified = {
                key: historical[key] for key in ("id", "status", "expires_on", "not_before")
            }
            metadata._validate_details(
                historical, verified, _timestamp(ref["historical_validation_at"])
            )
            if historical["id"] != ref["child_id"] or historical["status"] != "active":
                raise OperatorRefused("issuer_historical_child_required")
    all_paths = [*paths.values(), inputs.plan, inputs.approval, inputs.human_evidence]
    names = [os.path.normcase(str(path.resolve())) for path in all_paths]
    if len(set(names)) != len(names):
        raise OperatorRefused("issuer_distinct_paths_required")
    for path in (inputs.plan, inputs.approval, inputs.human_evidence):
        _assert_private(path.parent, directory=True)
        if path.resolve().is_relative_to(inputs.source_root.resolve(strict=True)):
            raise OperatorRefused("issuer_private_storage_outside_source_required")
    for key, path in paths.items():
        boundary._refuse_links(path)
        _assert_private(path.parent, directory=True)
        if path.resolve().is_relative_to(inputs.source_root.resolve(strict=True)):
            raise OperatorRefused("issuer_private_storage_outside_source_required")
        if path.exists():
            _assert_private(path)
            if initial and key in (
                "claim",
                "journal",
                "journal_owner",
                "journal_sidecar",
                "evidence",
            ):
                raise OperatorRefused("issuer_fresh_sinks_required")
    _assert_private(paths["parent_credential"])
    if plan["operation"] != "issue":
        _assert_private(paths["issuance_journal"])
        _assert_private(paths["issuance_owner"])
    if initial and plan["operation"] == "issue" and paths["child_credential"].exists():
        raise OperatorRefused("issuer_fresh_secret_delivery_required")
    return plan, approval


def permission_ids(response):
    """One bounded permission-catalog lookup, never a list of tokens."""
    value = _envelope(response, catalog=True)
    groups = value["result"]
    if type(groups) is not list or not 0 < len(groups) <= 1024:
        raise OperatorRefused("issuer_permission_catalog_refused")
    found = {}
    seen = set()
    for group in groups:
        _closed(group, {"id", "name", "scopes"}, {"category", "is_selectable", "description"})
        _text(group["id"], 32, metadata._ID)
        _text(group["name"], 128)
        if "category" in group and group["category"] is not None:
            metadata._provider_text(group["category"], 4096, allow_empty=True)
        if "description" in group:
            description = group["description"]
            # Catalog prose may contain LF; retain the original byte bound and
            # reject every other nonprintable character. It grants no access.
            metadata._provider_text(
                description.replace("\n", " ") if type(description) is str else description,
                4096,
                allow_empty=True,
            )
        if "is_selectable" in group and type(group["is_selectable"]) is not bool:
            raise OperatorRefused("issuer_permission_selectability_refused")
        if group["id"] in seen:
            raise OperatorRefused("issuer_duplicate_permission_id")
        seen.add(group["id"])
        if type(group["scopes"]) is not list or not 0 < len(group["scopes"]) <= 8:
            raise OperatorRefused("issuer_permission_scope_required")
        for scope in group["scopes"]:
            _text(scope, 128)
        if group["name"] in GROUP_SCOPES:
            if (
                group["name"] in found
                or group["scopes"] != [GROUP_SCOPES[group["name"]]]
                or (
                    group["name"] != "API Tokens Write"
                    and group.get("is_selectable", True) is not True
                )
            ):
                raise OperatorRefused("issuer_ambiguous_permission_mapping")
            found[group["name"]] = group["id"]
    if set(found) != set(GROUP_SCOPES):
        raise OperatorRefused("issuer_permission_mapping_incomplete")
    if "result_info" in value:
        info = _closed(
            value["result_info"], set(), {"page", "per_page", "count", "total_count", "total_pages"}
        )
        if any(type(v) is not int or not 0 <= v <= 100000 for v in info.values()):
            raise OperatorRefused("issuer_catalog_pagination_refused")
        if "count" in info and info["count"] != len(groups):
            raise OperatorRefused("issuer_catalog_count_mismatch")
    return found


def _policies(plan, ids, *, parent=False):
    names = ["API Tokens Write"] if parent else ["D1 Write", "Workers Scripts Write"]
    resource = (
        "com.cloudflare.api.user.*"
        if parent
        else "com.cloudflare.api.account." + plan["account_id"]
    )
    return [
        {
            "effect": "allow",
            "resources": {resource: "*"},
            "permission_groups": [{"id": ids[name]} for name in names],
        }
    ]


def _match_details(result, plan, ids, now, *, parent=False):
    verified = {key: result[key] for key in ("id", "status", "expires_on", "not_before")}
    expired = not parent and plan["operation"] == "revoke_expired"
    metadata._validate_details(result, verified, now, expired=expired)
    if expired:
        original = plan["issuance"]["child_details"]
        fields = ("id", "name", "issued_on", "expires_on", "not_before", "policies")
        if any(result[key] != original[key] for key in fields) or result.get(
            "condition", {}
        ) != original.get("condition", {}):
            raise OperatorRefused("issuer_expired_child_changed")
    normalized = []
    for policy in result["policies"]:
        normalized.append(
            {
                "effect": policy["effect"],
                "resources": policy["resources"],
                "permission_groups": [{"id": group["id"]} for group in policy["permission_groups"]],
            }
        )
    expected = _policies(plan, ids, parent=parent)
    if parent and len(normalized) == 1:
        resources = normalized[0]["resources"]
        if len(resources) == 1:
            resource = next(iter(resources))
            # Verify-self bound parent details can use a concrete user selector.
            # It is not the token ID or the execution child's account selector.
            if re.fullmatch(r"com\.cloudflare\.api\.user\.[a-f0-9]{32}", resource):
                expected[0]["resources"] = {resource: "*"}
    if normalized != expected:
        raise OperatorRefused("issuer_exact_provider_policy_required")
    if result.get("condition", {}) != plan["parent_condition" if parent else "child_condition"]:
        raise OperatorRefused("issuer_provider_condition_mismatch")
    issued, expiry = _timestamp(result["issued_on"]), _timestamp(result["expires_on"])
    if parent:
        if (
            (plan["parent_id"] is not None and result["id"] != plan["parent_id"])
            or expiry > _timestamp(PARENT_DEADLINE)
            or expiry - issued > 7 * 86400 * _SCALE
            or expiry <= _timestamp(plan["expires_at"])
        ):
            raise OperatorRefused("issuer_parent_identity_or_lifetime_refused")
    elif expiry != _timestamp(plan["child_expires_at"]):
        raise OperatorRefused("issuer_child_expiry_mismatch")
    elif issued < _timestamp(plan["starts_at"]) and plan["operation"] == "issue":
        raise OperatorRefused("issuer_child_actual_issue_time_required")


def _envelope(response, *, credentials=(), catalog=False):
    headers = {key.lower(): value for key, value in response.headers.items()}
    if (
        response.status != 200
        or type(response.status) is not int
        or len(headers) != len(response.headers)
        or headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"
        or headers.get("content-encoding", "identity").lower() != "identity"
        or "location" in headers
        or len(response.body) > MAX_RESPONSE_BYTES
    ):
        raise OperatorRefused("issuer_response_refused")
    value = _closed(
        metadata._json(response.body),
        {"success", "errors", "messages", "result"},
        {"result_info"} if catalog else set(),
    )
    if value["success"] is not True or value["errors"] != [] or value["messages"] != []:
        raise OperatorRefused("issuer_success_envelope_required")
    if any(secret.encode() in boundary.encoded(value) for secret in credentials):
        raise OperatorRefused("issuer_secret_echo_refused")
    return value


class _Evidence:
    """Exclusive-new private JSONL; each acknowledged fact is flushed durably."""

    def __init__(self, path):
        self.path = path
        self.fd = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOINHERIT", 0),
            0o600,
        )
        self.size = 0
        self.identity = os.fstat(self.fd)
        try:
            _assert_private(path)
        except BaseException:
            os.close(self.fd)
            raise

    def append(self, value):
        _assert_private(self.path)
        current = self.path.stat()
        opened = os.fstat(self.fd)
        if (current.st_dev, current.st_ino, current.st_size) != (
            opened.st_dev,
            opened.st_ino,
            self.size,
        ) or (opened.st_dev, opened.st_ino) != (self.identity.st_dev, self.identity.st_ino):
            raise OperatorRefused("issuer_evidence_changed")
        raw = boundary.encoded(value) + b"\n"
        if self.size + len(raw) > MAX_TOTAL_RESPONSE_BYTES + 65536:
            raise OperatorRefused("issuer_evidence_bound")
        if os.write(self.fd, raw) != len(raw):
            raise OperatorRefused("issuer_evidence_partial")
        os.fsync(self.fd)
        self.size += len(raw)

    def close(self):
        os.close(self.fd)


def run(
    inputs,
    *,
    wall_clock=time.time,
    monotonic=time.monotonic,
    transport=None,
    credential_loader=None,
):
    """One attempt: four GETs plus one POST/DELETE; no CLI/ambient credentials.

    Acknowledged creation is recorded before follow-up metadata or secret delivery.
    Any unknown mutation/delivery consumes this invocation permanently. Only a
    separate reviewed revoke packet can retire the exact acknowledged child ID.
    """
    requests = response_bytes = request_bytes = 0
    evidence = None
    secret = ""
    try:
        plan, approval = validate_inputs(inputs, now=metadata._now(wall_clock))
        started = monotonic()
        if type(started) not in (int, float) or not math.isfinite(started):
            raise OperatorRefused("issuer_clock_refused")
        deadline = started + min(
            MAX_WINDOW, (_timestamp(plan["expires_at"]) - metadata._now(wall_clock)) / _SCALE
        )
        parent_expiry = None

        def fence():
            tick = monotonic()
            if (
                type(tick) not in (int, float)
                or not math.isfinite(tick)
                or not started <= tick < deadline
                or validate_inputs(inputs, now=metadata._now(wall_clock), initial=False)
                != (plan, approval)
            ):
                raise OperatorRefused("issuer_fence_closed")
            remaining = min(
                deadline - tick,
                (_timestamp(plan["expires_at"]) - metadata._now(wall_clock)) / _SCALE,
            )
            if parent_expiry is not None:
                remaining = min(remaining, (parent_expiry - metadata._now(wall_clock)) / _SCALE)
            if remaining <= 0:
                raise OperatorRefused("issuer_expired")
            return min(20.0, remaining)

        metadata._create_private(Path(plan["claim"]), inputs.plan_digest.encode())
        with DurableJournal(Path(plan["journal"]), inputs.plan_digest) as journal:
            _assert_private(Path(plan["journal"]))
            _assert_private(Path(plan["journal"] + ".owner"))
            if journal.snapshot() or not journal.reserve(
                "issuer:started", {"operation": plan["operation"]}
            ):
                raise OperatorRefused("issuer_replay_forbidden")
            evidence = _Evidence(Path(plan["evidence"]))
            evidence.append(
                {
                    "plan_digest": inputs.plan_digest,
                    "approval_digest": inputs.approval_digest,
                    "decision_id": DECISION,
                    "source_commit": plan["source_commit"],
                    "provisioning": approval["provisioning"],
                    "retention_until": plan["retention_until"],
                }
            )
            raw = (credential_loader or _private_bytes)(Path(plan["parent_credential"]), 2048)
            if (
                type(raw) is not bytes
                or re.fullmatch(rb"[A-Za-z0-9_-]{20,2048}", raw) is None
                or boundary.sha2_256(raw) != plan["parent_sha2_256"]
            ):
                raise OperatorRefused("issuer_parent_fingerprint_required")
            secret = raw.decode("ascii")
            raw = None
            address = _address(plan["api_address"])

            def dispatch(method, path, *, body=None, mutation=False):
                nonlocal requests, response_bytes, request_bytes
                timeout = fence()
                data = b"" if body is None else boundary.encoded(body)
                headers = {
                    "Host": "api.cloudflare.com",
                    "Connection": "close",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "Content-Length": str(len(data)),
                    "Authorization": "Bearer " + secret,
                }
                if body is not None:
                    headers["Content-Type"] = "application/json"
                wire = (
                    method
                    + " "
                    + path
                    + " HTTP/1.1\r\n"
                    + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                    + "\r\n"
                ).encode() + data
                limit = min(MAX_RESPONSE_BYTES, MAX_TOTAL_RESPONSE_BYTES - response_bytes)
                if (
                    requests >= MAX_REQUESTS
                    or len(wire) > 8192
                    or limit <= 0
                    or request_bytes + len(wire) > MAX_REQUEST_BYTES
                ):
                    raise OperatorRefused("issuer_budget_exhausted")
                key = "issuer:mutation" if mutation else "issuer:read:" + str(requests + 1)
                # This FULL-synchronous intent precedes even transport preparation.
                if not journal.reserve(
                    key, {"method": method, "path": path, "requestDigest": boundary.sha2_256(data)}
                ):
                    raise OperatorRefused("issuer_replay_forbidden")
                request = Request(
                    metadata.ORIGIN + path,
                    headers,
                    timeout,
                    limit,
                    min(deadline, monotonic() + timeout),
                    wire,
                )
                requests += 1
                request_bytes += len(wire)
                try:
                    response = (
                        transport(request)
                        if transport is not None
                        else _pinned_https(
                            request, address, monotonic, fence, discard_set_cookie=True
                        )
                    )
                    used = response.wire_bytes
                    if type(used) is not int or not len(response.body) <= used <= limit:
                        raise OperatorRefused("issuer_wire_accounting_refused")
                    response_bytes += used
                    if monotonic() >= request.deadline:
                        raise OperatorRefused("issuer_late_response")
                    fence()
                    return response, key
                except BaseException:
                    journal.unknown(key, "issuer_unknown_no_replay")
                    raise

            response, key = dispatch("GET", BASE + "/verify")
            verified = metadata.validate_response(
                response, now=metadata._now(wall_clock), credentials=(secret,)
            )
            parent_id = verified["result"]["id"]
            if plan["parent_id"] is not None and parent_id != plan["parent_id"]:
                raise OperatorRefused("issuer_parent_id_mismatch")
            evidence.append({"phase": "parent_verify", "response": verified})
            journal.complete(key, {"status": "retained"})
            response, key = dispatch("GET", BASE + "/permission_groups")
            ids = permission_ids(response)
            catalog = _envelope(response, credentials=(secret,), catalog=True)
            evidence.append({"phase": "permission_catalog", "response": catalog})
            journal.complete(key, {"status": "retained"})
            response, key = dispatch("GET", BASE + "/" + parent_id)
            parent = metadata.validate_response(
                response,
                details=True,
                verified=verified["result"],
                now=metadata._now(wall_clock),
                credentials=(secret,),
            )
            _match_details(parent["result"], plan, ids, metadata._now(wall_clock), parent=True)
            parent_expiry = _timestamp(parent["result"]["expires_on"])
            if _timestamp(plan["child_expires_at"]) > parent_expiry:
                raise OperatorRefused("issuer_child_outlives_parent")
            evidence.append({"phase": "parent_details", "response": parent})
            journal.complete(key, {"status": "retained"})
            if plan["operation"] == "issue":
                body = {
                    "name": plan["child_name"],
                    "policies": _policies(plan, ids),
                    "expires_on": plan["child_expires_at"],
                    "not_before": plan["starts_at"],
                }
                if plan["child_condition"]:
                    body["condition"] = plan["child_condition"]
                response, key = dispatch("POST", BASE, body=body, mutation=True)
                created = _envelope(response, credentials=(secret,))
                result = _closed(
                    created["result"],
                    {"id", "value"},
                    {
                        "name",
                        "status",
                        "issued_on",
                        "expires_on",
                        "not_before",
                        "policies",
                        "condition",
                        "modified_on",
                        "last_used_on",
                    },
                )
                child_id = _text(result["id"], 32, metadata._ID)
                if child_id == parent_id:
                    raise OperatorRefused("issuer_distinct_child_required")
                owned = {
                    "childId": child_id,
                    "parentId": parent_id,
                    "parentFingerprint": plan["parent_sha2_256"],
                    "accountId": plan["account_id"],
                    "profile": PROFILE,
                    "childExpiry": plan["child_expires_at"],
                    "childName": plan["child_name"],
                    "childCondition": plan["child_condition"],
                }
                journal.complete(key, owned)
                child_secret = _text(result["value"], 2048, r"[A-Za-z0-9_-]{20,2048}")
                if child_secret == secret:
                    raise OperatorRefused("issuer_distinct_child_required")
                redacted = {k: v for k, v in result.items() if k != "value"}
                if any(s.encode() in boundary.encoded(redacted) for s in (secret, child_secret)):
                    raise OperatorRefused("issuer_secret_echo_refused")
                evidence.append(
                    {
                        "phase": "create_acknowledged",
                        "response": created | {"result": redacted},
                        "ownership": owned,
                        "child_sha2_256": boundary.sha2_256(child_secret.encode()),
                    }
                )
                response, key = dispatch("GET", BASE + "/" + child_id)
                details = _envelope(response, credentials=(secret, child_secret))
                if (
                    details["result"]["id"] != child_id
                    or details["result"]["name"] != plan["child_name"]
                ):
                    raise OperatorRefused("issuer_child_identity_mismatch")
                _match_details(details["result"], plan, ids, metadata._now(wall_clock))
                evidence.append({"phase": "child_details", "response": details})
                journal.complete(key, {"status": "retained"})
                fence()
                metadata._create_private(Path(plan["child_credential"]), child_secret.encode())
                evidence.append(
                    {"phase": "delivery", "status": "exclusive_new_private_file_written"}
                )
                child_secret = ""
            else:
                ref = plan["issuance"]
                with DurableJournal(Path(ref["journal"]), ref["plan_digest"]) as original:
                    state = original.snapshot().get("issuer:mutation", {})
                    owned = state.get("receipt", {})
                    expected = {
                        "childId": ref["child_id"],
                        "parentId": plan["parent_id"],
                        "parentFingerprint": plan["parent_sha2_256"],
                        "accountId": plan["account_id"],
                        "profile": PROFILE,
                        "childExpiry": plan["child_expires_at"],
                        "childName": plan["child_name"],
                        "childCondition": plan["child_condition"],
                    }
                    if state.get("state") != "complete" or owned != expected:
                        raise OperatorRefused("issuer_known_owned_child_required")
                    if not original.reserve(
                        "issuer:retire", {"revocationPlan": inputs.plan_digest}
                    ):
                        raise OperatorRefused("issuer_revoke_replay_forbidden")
                    response, key = dispatch("GET", BASE + "/" + ref["child_id"])
                    details = _envelope(response, credentials=(secret,))
                    if (
                        details["result"]["id"] != ref["child_id"]
                        or details["result"]["name"] != plan["child_name"]
                    ):
                        raise OperatorRefused("issuer_revoke_identity_mismatch")
                    _match_details(details["result"], plan, ids, metadata._now(wall_clock))
                    evidence.append(
                        {"phase": "revoke_child_details", "response": details, "ownership": owned}
                    )
                    journal.complete(key, {"status": "retained"})
                    response, key = dispatch("DELETE", BASE + "/" + ref["child_id"], mutation=True)
                    deleted = _envelope(response, credentials=(secret,))
                    _closed(deleted["result"], {"id"})
                    if deleted["result"]["id"] != ref["child_id"]:
                        raise OperatorRefused("issuer_delete_ack_id_mismatch")
                    evidence.append({"phase": "delete_acknowledged", "response": deleted})
                    journal.complete(
                        key, {"childId": ref["child_id"], "status": "delete_acknowledged"}
                    )
                    original.complete("issuer:retire", {"status": "delete_acknowledged"})
            journal.complete(
                "issuer:started",
                {"status": "finished", "requests": requests, "responseWireBytes": response_bytes},
            )
            return {
                "status": "finished",
                "requests": requests,
                "response_wire_bytes": response_bytes,
            }
    except BaseException:
        failure = ProvisioningRefused(requests, response_bytes)
    finally:
        secret = ""
        if evidence is not None:
            evidence.close()
    raise failure from None


def main():
    raise SystemExit("NO-GO: trusted primary requires an independently reviewed private packet.")


if __name__ == "__main__":
    main()
