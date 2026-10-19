"""Explicit finite execution boundary. Import/readiness never load credentials.

Source acceptance and packet verification are not action permission. The parent
operator must independently retain the approval digest after actual human action
approval. JSON cannot authenticate its human author; this is an explicit trusted
caller boundary, never an approval inferred from a CLI switch or source ticket.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import re
import stat
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_execution as offline
from scripts import prepare_hosted_publisher_runtime as packet
from scripts.hosted_publisher_operator import (
    DurableJournal,
    HostedPublisherOperator,
    OperatorRefused,
)


@dataclass(frozen=True)
class RuntimeInputs:
    packet: Path
    packet_digest: str
    consent: Path
    consent_digest: str
    grant: Path
    grant_digest: str
    credential: Path
    journal: Path
    source_root: Path
    bundle: Path
    current_root: Path
    approval: Path
    approval_digest: str
    grant_evidence: Path
    cleanup: Path | None = None
    cleanup_digest: str | None = None
    stop_file: Path | None = None


@dataclass(frozen=True)
class ValidatedInputs:
    plan: boundary.OperatorPlan
    manifest: dict
    consent: dict
    grant: dict
    approval: dict
    cleanup: dict | None


def _windows_private(path: Path) -> None:
    """Refuse credentials readable by identities beyond owner/System/Admins.

    Inspect native security metadata only. No shell, credential discovery or
    external process receives the path or file contents.
    """
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    advapi.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(pointer),
        pointer,
        ctypes.POINTER(pointer),
        pointer,
        ctypes.POINTER(pointer),
    ]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(pointer)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi.GetAce.argtypes = [pointer, wintypes.DWORD, ctypes.POINTER(pointer)]
    advapi.GetAce.restype = wintypes.BOOL
    advapi.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        pointer,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.LocalFree.argtypes = [pointer]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    def sid_text(sid):
        output = pointer()
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(output)):
            raise OperatorRefused("private_file_security_unavailable")
        try:
            return ctypes.wstring_at(output)
        finally:
            kernel.LocalFree(output)

    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise OperatorRefused("private_file_security_unavailable")
    try:
        needed = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        info = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 1, info, needed, ctypes.byref(needed)):
            raise OperatorRefused("private_file_security_unavailable")
        current = sid_text(ctypes.cast(info, ctypes.POINTER(pointer))[0])
    finally:
        kernel.CloseHandle(token)
    owner, dacl, descriptor = pointer(), pointer(), pointer()
    error = advapi.GetNamedSecurityInfoW(
        str(path),
        1,
        5,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if error:
        raise OperatorRefused("private_file_security_unavailable")
    try:
        if dacl.value is None or sid_text(owner) != current:
            raise OperatorRefused("private_file_owner_or_acl_refused")
        # ACL header: revision/reserved/size followed by 16-bit ACE count.
        count = ctypes.c_ushort.from_address(dacl.value + 4).value
        trusted = {current, "S-1-5-18", "S-1-5-32-544"}
        for index in range(count):
            ace = pointer()
            if not advapi.GetAce(dacl, index, ctypes.byref(ace)) or ace.value is None:
                raise OperatorRefused("private_file_security_unavailable")
            ace_type = ctypes.c_ubyte.from_address(ace.value).value
            flags = ctypes.c_ubyte.from_address(ace.value + 1).value
            if flags & 8:  # INHERIT_ONLY_ACE has no access on this object.
                continue
            if ace_type == 1:  # Ordinary deny ACE grants no read access.
                continue
            if ace_type != 0:
                raise OperatorRefused("private_file_acl_form_refused")
            mask = ctypes.c_uint32.from_address(ace.value + 4).value
            if mask & 0xF01F01FF and sid_text(ace.value + 8) not in trusted:
                raise OperatorRefused("private_file_broad_access_refused")
    finally:
        kernel.LocalFree(descriptor)


def _assert_private(path: Path, *, directory=False) -> None:
    boundary._refuse_links(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode):
        raise OperatorRefused("private_input_not_regular")
    if not directory and info.st_nlink != 1:
        raise OperatorRefused("private_input_hardlink_refused")
    if os.name == "nt":
        _windows_private(path)
    elif info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise OperatorRefused("private_input_permissions_refused")


def _private_bytes(path: Path, maximum=262144) -> bytes:
    _assert_private(path)
    before = path.stat()
    if not 0 < before.st_size <= maximum:
        raise OperatorRefused("private_input_size_refused")
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOINHERIT", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
    )
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
        ):
            raise OperatorRefused("private_input_changed")
        raw = os.read(descriptor, maximum + 1)
        after = os.fstat(descriptor)
        if (
            len(raw) != before.st_size
            or len(raw) > maximum
            or (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        ):
            raise OperatorRefused("private_input_changed")
    finally:
        os.close(descriptor)
    _assert_private(path)
    final = path.stat()
    if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ):
        raise OperatorRefused("private_input_changed")
    return raw


def _document(path, digest):
    boundary._text(digest, r"[0-9a-f]{64}", "independent private input digest")
    raw = _private_bytes(path)
    if boundary.sha2_256(raw) != digest:
        raise OperatorRefused("private_input_digest_mismatch")
    return offline._read_json(raw)


def _running_root():
    return Path(__file__).resolve().parents[1]


def validate_cleanup(plan, authority, now):
    boundary._closed(
        authority,
        {
            "schema_version",
            "granted",
            "plan_digest",
            "owner",
            "decision_id",
            "expires_at",
            "actions",
        },
    )
    if (
        type(authority["schema_version"]) is not int
        or authority["schema_version"] != 1
        or authority["granted"] is not True
        or authority["plan_digest"] != plan.digest
        or authority["owner"] != plan.cleanup_owner
        or authority["actions"]
        != ["fence_dispatch", "disable_access", "delete_owned_worker", "dispose_exact_synthetic_d1"]
        or not now
        < boundary.utc_time(authority["expires_at"])
        <= boundary.utc_time(plan.cleanup_deadline)
    ):
        raise OperatorRefused("separate_cleanup_authority_required")
    boundary._text(
        authority["decision_id"], r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", "cleanup decision"
    )


def _concrete_case_windows(plan: boundary.OperatorPlan) -> None:
    """Concrete TLS permits support one common window, never narrower cases.

    The final post-connect admission callback fences the plan window. Refuse
    more expressive offline case schedules rather than imply it fences them.
    """
    if any(
        (case.starts_at, case.expires_at) != (plan.starts_at, plan.expires_at)
        for case in plan.cases
    ):
        raise OperatorRefused("concrete_common_case_window_required")


def validate_inputs(inputs: RuntimeInputs, *, cleanup_only=False, now=None):
    now = datetime.now(UTC) if now is None else now
    manifest = packet.verify(inputs.packet, inputs.packet_digest)
    plan = boundary.load_plan(packet.bounded_read(inputs.packet, "plan.json", 262144))
    _concrete_case_windows(plan)
    if inputs.current_root.resolve(strict=True) != _running_root().resolve(strict=True):
        raise OperatorRefused("caller_running_source_root_mismatch")
    files = {
        name: packet.bounded_read(inputs.current_root, name, 16_777_216)
        for name in packet.SOURCE_FILES
    }
    packet.source_identity(inputs.current_root, manifest["source_commit"], files)
    if (
        files[".python-version"].decode("ascii").strip() != ".".join(map(str, sys.version_info[:3]))
        or sys.implementation.name != "cpython"
    ):
        raise OperatorRefused("reviewed_python_runtime_required")
    for name, raw in files.items():
        if boundary.sha2_256(raw) != manifest["files"]["source/" + name]["sha2_256"]:
            raise OperatorRefused("caller_source_packet_mismatch")
    boundary.validate_current_inputs(plan, inputs.current_root)
    boundary.validate_artifact(inputs.source_root, inputs.bundle)
    consent = _document(inputs.consent, inputs.consent_digest)
    grant = _document(inputs.grant, inputs.grant_digest)
    approval = _document(inputs.approval, inputs.approval_digest)
    boundary.validate_consent(
        plan, consent, boundary.utc_time(plan.starts_at) if cleanup_only else now
    )
    boundary.validate_operator_grant(plan, grant, now)
    boundary._closed(
        approval,
        {
            "schema_version",
            "granted",
            "owner",
            "decision_id",
            "packet_digest",
            "plan_digest",
            "consent_digest",
            "grant_digest",
            "grant_evidence_digest",
            "credential_sha2_256",
            "source_commit",
            "human_approval",
            "isolation",
            "expires_at",
            "actions",
        },
    )
    if (
        type(approval["schema_version"]) is not int
        or approval["schema_version"] != 1
        or approval["granted"] is not True
        or approval["owner"] != plan.owner
        or approval["packet_digest"] != inputs.packet_digest
        or approval["plan_digest"] != plan.digest
        or approval["consent_digest"] != inputs.consent_digest
        or approval["grant_digest"] != inputs.grant_digest
        or approval["source_commit"] != manifest["source_commit"]
        or approval["actions"] != list(boundary.OWNER_ACTIONS)
    ):
        raise OperatorRefused("independent_action_approval_required")
    boundary._text(approval["decision_id"], r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", "action decision")
    human = boundary._closed(
        approval["human_approval"], {"reference", "evidence_sha2_256", "recorded_at"}
    )
    boundary._text(
        human["reference"], r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", "actual human decision reference"
    )
    boundary._text(human["evidence_sha2_256"], r"[0-9a-f]{64}", "actual human decision digest")
    approval_end = boundary.utc_time(approval["expires_at"])
    if (
        not boundary.utc_time(human["recorded_at"]) <= now
        or not boundary.utc_time(plan.starts_at)
        < approval_end
        <= boundary.utc_time(plan.expires_at)
        or (not cleanup_only and now >= approval_end)
    ):
        raise OperatorRefused("action_approval_expired_or_unrecorded")
    isolation = boundary._closed(
        approval["isolation"],
        {
            "exclusive_owner",
            "synthetic_only",
            "no_production_references",
            "journal_outside_resources",
        },
    )
    if any(value is not True for value in isolation.values()):
        raise OperatorRefused("independent_isolation_review_required")
    boundary._text(
        approval["grant_evidence_digest"], r"[0-9a-f]{64}", "independent grant evidence digest"
    )
    if (
        boundary.sha2_256(_private_bytes(inputs.grant_evidence))
        != approval["grant_evidence_digest"]
    ):
        raise OperatorRefused("independent_grant_evidence_mismatch")
    cleanup = None
    if cleanup_only:
        if inputs.cleanup is None or inputs.cleanup_digest is None:
            raise OperatorRefused("separate_cleanup_authority_required")
        cleanup = _document(inputs.cleanup, inputs.cleanup_digest)
        validate_cleanup(plan, cleanup, now)
        if not boundary.utc_time(plan.starts_at) <= now < boundary.utc_time(plan.cleanup_deadline):
            raise OperatorRefused("cleanup_window_closed")
    elif inputs.cleanup is not None or inputs.cleanup_digest is not None:
        raise OperatorRefused("cleanup_is_separate_invocation")
    _assert_private(inputs.credential)
    if not 20 <= inputs.credential.stat().st_size <= 4096:
        raise OperatorRefused("management_credential_custody_refused")
    _assert_private(inputs.journal.parent, directory=True)
    boundary._refuse_links(inputs.journal)
    for root in (inputs.packet, inputs.current_root, inputs.source_root, inputs.bundle.parent):
        if inputs.journal.absolute().is_relative_to(root.resolve(strict=True)):
            raise OperatorRefused("journal_must_be_separate_private_storage")
    if inputs.journal.exists():
        _assert_private(inputs.journal)
    owner_latch = Path(str(inputs.journal) + ".owner")
    boundary._refuse_links(owner_latch)
    if owner_latch.exists():
        _assert_private(owner_latch)
    if inputs.stop_file is not None:
        boundary._refuse_links(inputs.stop_file)
        if not inputs.stop_file.parent.resolve(strict=True).is_relative_to(
            inputs.journal.parent.resolve(strict=True)
        ):
            raise OperatorRefused("stop_file_outside_private_runtime")
        if not cleanup_only and inputs.stop_file.exists():
            raise OperatorRefused("dispatch_already_stopped")
    return ValidatedInputs(plan, manifest, consent, grant, approval, cleanup)


class ExecutionPermit:
    """Non-secret authority rechecked at every real transport admission."""

    def __init__(
        self, inputs, validated, *, cleanup_only, wall_clock=time.time, monotonic=time.monotonic
    ):
        _concrete_case_windows(validated.plan)
        self.inputs, self.validated = inputs, validated
        self.cleanup_only = cleanup_only
        self.wall_clock, self.monotonic = wall_clock, monotonic
        self.started = monotonic()
        self.closed = False
        self.operator: HostedPublisherOperator | None = None
        self.stopped = False
        self.adapter_deadline = wall_clock() + 7200
        self.lifecycle_deadline = wall_clock() + validated.plan.budgets.lifecycle_seconds

    def remaining_seconds(self):
        plan = self.validated.plan
        expiry = (
            self.validated.cleanup["expires_at"]
            if self.cleanup_only
            else self.validated.approval["expires_at"]
        )
        return min(
            boundary.utc_time(self.validated.grant["expires_at"]).timestamp() - self.wall_clock(),
            self.adapter_deadline - self.wall_clock(),
            self.lifecycle_deadline - self.wall_clock(),
            boundary.utc_time(expiry).timestamp() - self.wall_clock(),
            plan.budgets.lifecycle_seconds - (self.monotonic() - self.started),
        )

    def authorize(self):
        # Also enforced by the existing final post-connect TLS callback.
        _concrete_case_windows(self.validated.plan)
        if not self.cleanup_only:
            if (self.inputs.stop_file is not None and self.inputs.stop_file.exists()) or getattr(
                self.operator, "_stopped", False
            ):
                self.stopped = True
            if self.stopped and not getattr(self.operator, "_stopping", False):
                raise OperatorRefused("execution_dispatch_stopped")
        if self.closed or self.remaining_seconds() <= 0:
            raise OperatorRefused("execution_permit_expired")
        value = self.validated
        now = datetime.fromtimestamp(self.wall_clock(), UTC)
        boundary.validate_operator_grant(value.plan, value.grant, now)
        boundary.validate_current_inputs(value.plan, self.inputs.current_root)
        # Private authority files are byte-bound; changing them cannot extend a run.
        if (
            _document(self.inputs.approval, self.inputs.approval_digest) != value.approval
            or _document(self.inputs.consent, self.inputs.consent_digest) != value.consent
            or _document(self.inputs.grant, self.inputs.grant_digest) != value.grant
        ):
            raise OperatorRefused("execution_authority_changed")
        if self.cleanup_only:
            if _document(self.inputs.cleanup, self.inputs.cleanup_digest) != value.cleanup:
                raise OperatorRefused("cleanup_authority_changed")
            validate_cleanup(value.plan, value.cleanup, now)
        elif (
            not boundary.utc_time(value.plan.starts_at)
            <= now
            < boundary.utc_time(value.plan.expires_at)
        ):
            raise OperatorRefused("operation_window_closed")


def _provider(plan, token, manifest, permit):
    from scripts.hosted_publisher_execution_provider import ExecutionBetaPublisherProvider

    return ExecutionBetaPublisherProvider(
        plan.account_id,
        token,
        [c.worker_name for c in plan.cases],
        [c.d1_name for c in plan.cases],
        permit=permit,
        management_address=manifest["network"]["management_address"],
        exclusive_owner=True,
    )


def _clients(plan, manifest, permit):
    from scripts.hosted_publisher_execution_provider import ExecutionClientTransport

    clients = {
        c.endpoint: ExecutionClientTransport(
            c.endpoint, manifest["network"]["client_addresses"][c.endpoint], permit=permit
        )
        for c in plan.cases
    }

    def dispatch(request):
        from urllib.parse import urlsplit

        url = urlsplit(request.url)
        endpoint = f"{url.scheme}://{url.netloc}"
        if endpoint not in clients:
            raise OperatorRefused("client_outside_plan")
        return clients[endpoint](request)

    return dispatch


def _remaining_provider_capacity(snapshot, plan):
    events = [event for key, event in snapshot.items() if key.startswith("provider:")]
    calls = len(events)
    mutations = sum(event["payload"].get("mutation") is True for event in events)
    request_bytes = sum(event["payload"]["requestBytes"] for event in events)
    response_bytes = sum(
        event["receipt"]["responseBytes"]
        if event["state"] == "complete"
        else event["payload"]["reservedResponseBytes"]
        for event in events
    )
    if (
        calls >= plan.budgets.provider_calls
        or mutations >= plan.budgets.provider_mutations
        or request_bytes >= 16_777_216
        or response_bytes + 2_097_152 > 33_554_432
    ):
        raise OperatorRefused("original_provider_capacity_exhausted")


def run(
    inputs: RuntimeInputs,
    *,
    cleanup_only=False,
    wall_clock=time.time,
    monotonic=time.monotonic,
    provider_factory=None,
    client_factory=None,
):
    """One run or cleanup-only continuation. Injected factories are trusted tests.

    This does not itself authenticate a human decision. The authorized parent
    supplies independently reviewed and retained private approval evidence.
    """
    value = validate_inputs(
        inputs, cleanup_only=cleanup_only, now=datetime.fromtimestamp(wall_clock(), UTC)
    )
    permit = ExecutionPermit(
        inputs, value, cleanup_only=cleanup_only, wall_clock=wall_clock, monotonic=monotonic
    )
    marker = {
        "packetDigest": inputs.packet_digest,
        "approvalDigest": inputs.approval_digest,
        "owner": value.plan.owner,
    }
    provider = private = None
    credential = credential_raw = None
    with DurableJournal(inputs.journal, value.plan.digest) as journal:
        snapshot = journal.snapshot()
        original = snapshot.get("execution:authority")
        if cleanup_only:
            if (
                original is None
                or original["state"] != "complete"
                or set(original["receipt"])
                != set(marker) | {"startedAt", "adapterDeadline", "lifecycleDeadline"}
                or any(
                    original["receipt"].get(name) != expected for name, expected in marker.items()
                )
                or "execution:started" not in snapshot
            ):
                raise OperatorRefused("original_execution_authority_missing")
            receipt = original["receipt"]
            for name in ("startedAt", "adapterDeadline", "lifecycleDeadline"):
                if type(receipt[name]) not in (int, float) or not math.isfinite(receipt[name]):
                    raise OperatorRefused("original_execution_deadline_invalid")
            if (
                receipt["adapterDeadline"] != receipt["startedAt"] + 7200
                or receipt["lifecycleDeadline"]
                != receipt["startedAt"] + value.plan.budgets.lifecycle_seconds
                or receipt["startedAt"] > wall_clock()
            ):
                raise OperatorRefused("original_execution_deadline_invalid")
            permit.adapter_deadline = receipt["adapterDeadline"]
            permit.lifecycle_deadline = receipt["lifecycleDeadline"]
        else:
            if snapshot or not journal.reserve(
                "execution:authority", {"planDigest": value.plan.digest}
            ):
                raise OperatorRefused("execution_replay_forbidden")
            started_at = wall_clock()
            permit.adapter_deadline = started_at + 7200
            permit.lifecycle_deadline = started_at + value.plan.budgets.lifecycle_seconds
            journal.complete(
                "execution:authority",
                {
                    **marker,
                    "startedAt": started_at,
                    "adapterDeadline": permit.adapter_deadline,
                    "lifecycleDeadline": permit.lifecycle_deadline,
                },
            )
        _remaining_provider_capacity(snapshot, value.plan)
        permit.authorize()
        if cleanup_only and (inputs.cleanup_digest is None or value.cleanup is None):
            raise OperatorRefused("separate_cleanup_authority_required")
        key = (
            "execution:cleanup:" + boundary.sha2_256(str(inputs.cleanup_digest).encode())[:16]
            if cleanup_only
            else "execution:started"
        )
        if not journal.reserve(key, {"planDigest": value.plan.digest}):
            raise OperatorRefused("execution_replay_forbidden")
        journal.complete(key, {"status": "admitted_once"})
        result_key = key + ":result"
        try:
            permit.authorize()
            # The first credential read is strictly after every non-secret gate,
            # independently retained approval, and durable once-only reservation.
            credential_raw = _private_bytes(inputs.credential, 4096)
            if boundary.sha2_256(credential_raw) != value.approval["credential_sha2_256"]:
                raise OperatorRefused("management_credential_grant_binding_mismatch")
            credential = credential_raw.decode("ascii")
            credential_raw = None
            if re.fullmatch(r"[A-Za-z0-9_-]{20,2048}", credential) is None:
                raise OperatorRefused("management_credential_format_refused")
            permit.authorize()
            provider = (provider_factory or _provider)(
                value.plan, credential, value.manifest, permit
            )
            private = (
                boundary.PrivateInputs({})
                if cleanup_only
                else boundary.PrivateInputs.fresh(value.plan)
            )
            client = (client_factory or _clients)(value.plan, value.manifest, permit)
            operator = HostedPublisherOperator(
                value.plan,
                value.consent,
                provider,
                client,
                journal,
                private,
                inputs.source_root,
                inputs.bundle,
                inputs.current_root,
                operator_grant=value.grant,
                wall_clock=wall_clock,
                monotonic=monotonic,
                stop_check=lambda: inputs.stop_file is not None and inputs.stop_file.exists(),
            )
            permit.operator = operator
            if cleanup_only:
                assert value.cleanup is not None
                result = operator.cleanup_only(value.cleanup)
            else:
                result = operator.run()
            if not journal.reserve(result_key, {"planDigest": value.plan.digest}):
                raise OperatorRefused("execution_result_already_present")
            journal.complete(result_key, {"status": result["status"]})
            return result
        except BaseException:
            if journal.reserve(result_key, {"planDigest": value.plan.digest}):
                journal.unknown(result_key, "execution_interrupted_or_refused")
            raise OperatorRefused("execution_interrupted_or_refused") from None
        finally:
            permit.closed = True
            if private is not None:
                private.revoke_local()
            if provider is not None:
                provider._closed = True
                provider._token = ""
            credential = credential_raw = None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", nargs="?", choices=("readiness", "execute", "cleanup"), default="readiness"
    )
    for name in (
        "packet",
        "consent",
        "grant",
        "credential-file",
        "journal",
        "candidate-root",
        "bundle",
        "current-root",
        "approval",
        "grant-evidence",
        "cleanup-authority",
        "stop-file",
    ):
        parser.add_argument("--" + name, type=Path)
    for name in (
        "packet-digest",
        "consent-digest",
        "grant-digest",
        "approval-digest",
        "cleanup-digest",
    ):
        parser.add_argument("--" + name)
    args = parser.parse_args(argv)
    required = (
        "packet",
        "packet_digest",
        "consent",
        "consent_digest",
        "grant",
        "grant_digest",
        "credential_file",
        "journal",
        "candidate_root",
        "bundle",
        "current_root",
        "approval",
        "approval_digest",
        "grant_evidence",
    )
    if any(getattr(args, name) is None for name in required):
        parser.exit(
            2, "NO-GO: exact independent packet, action authority and private paths required\n"
        )
    inputs = RuntimeInputs(
        packet=args.packet,
        packet_digest=args.packet_digest,
        consent=args.consent,
        consent_digest=args.consent_digest,
        grant=args.grant,
        grant_digest=args.grant_digest,
        credential=args.credential_file,
        journal=args.journal,
        source_root=args.candidate_root,
        bundle=args.bundle,
        current_root=args.current_root,
        approval=args.approval,
        approval_digest=args.approval_digest,
        grant_evidence=args.grant_evidence,
        cleanup=args.cleanup_authority,
        cleanup_digest=args.cleanup_digest,
        stop_file=args.stop_file,
    )
    try:
        if args.action == "readiness":
            validate_inputs(inputs)
            parser.exit(2, "NO-GO: inputs verified; readiness grants no execution permission\n")
        result = run(inputs, cleanup_only=args.action == "cleanup")
    except ValueError, OSError, UnicodeError, KeyError, TypeError:
        parser.exit(2, "NO-GO: execution refused; provider success is not established\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "qualification": "not_established",
                "querySettlement": "unproved",
                "revocation": "external_owner_required",
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] in {"phases_complete_cleanup_pending", "resources_disposed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
