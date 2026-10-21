"""Fresh screenshot POST caller; CLI action remains explicitly disabled."""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import time
from pathlib import Path

from scripts import group_post_characterization as post
from scripts import group_post_dispatch as dispatch
from scripts import prepare_post_screenshot_successor as packet

VERSION = post.VERSION
atomic_json = post.atomic_json
bounded_json = post.bounded_json
native_terminal = post.native_terminal

CASES = (
    "proof",
    "batch-one",
    "batch-sixty",
    "status-400",
    "status-401",
    "status-409",
    "status-429",
    "status-503",
    "oversize-success",
    "oversize-error",
    "timeout",
    "lost-response",
    "same-301",
    "cross-301",
    "same-302",
    "cross-302",
    "same-303",
    "cross-303",
    "same-307",
    "cross-307",
    "same-308",
    "cross-308",
    "cancel",
)


def classify(value, run_id):
    """Inventory observations without turning SDK fixture completion into qualification."""
    terminal = native_terminal(value, run_id)
    cases = value.get("cases", [])
    if not isinstance(cases, list) or len(cases) != terminal["postCalls"]:
        raise ValueError("native_case_inventory_invalid")
    if any(not isinstance(v, dict) or v.get("caseId") != CASES[i] for i, v in enumerate(cases)):
        raise ValueError("native_case_order_invalid")
    return {
        **terminal,
        "postCases": [
            {
                "caseId": case,
                "classification": "observed_pending_review" if i < len(cases) else "unmeasured",
            }
            for i, case in enumerate(CASES)
        ],
        "diagnosticGet": "observed_pending_review" if terminal["getCalls"] else "unmeasured",
        "receiverClassification": "pending_independent_receipt_review",
        "methodSpecificPostQualified": False,
    }


class DeadlineAdmission:
    def __init__(self, api, account, deadline, clock):
        self.api, self.expected_account, self.deadline, self.source_clock = (
            api,
            account,
            deadline,
            clock,
        )
        self.admitted = False

    @property
    def account(self):
        if self.api.account != self.expected_account:
            raise ValueError("provider_account_changed")
        return self.expected_account

    def clock(self):
        now = self.source_clock()
        if not math.isfinite(now) or (not self.admitted and now + 1200 > self.deadline):
            raise ValueError("action_deadline_insufficient")
        return now

    def call(self, method, path, body=None, *, timeout=20):
        self.clock()
        _ = self.account
        self.admitted = True
        return self.api.call(method, path, body, timeout=timeout)


def execute(
    api,
    config,
    *,
    native_factory=None,
    lifecycle_factory=None,
    clock=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    """Injected trusted composition. No credential acquisition or native initialization."""
    if native_factory is None:
        native_factory = dispatch.NativeFiles
    if lifecycle_factory is None:
        from scripts.post_screenshot_lifecycle import Lifecycle

        lifecycle_factory = Lifecycle
    run_id = packet.identity(config["runId"], spent_run_ids=config.get("spentRunIds", ()))
    bound = packet.binding(run_id, runs=Path(config["runRoot"]).parent)
    if any(config.get(k) != v for k, v in bound.items()) or api.account != config["accountId"]:
        raise ValueError("execution_binding_invalid")
    deadline, now = config["actionDeadlineUnix"], clock()
    if (
        type(deadline) not in (int, float)
        or not math.isfinite(deadline)
        or not math.isfinite(now)
        or not now + 1230 <= deadline <= now + 1800
    ):
        raise ValueError("action_deadline_invalid")
    # This claim is never removed, including failures before native claim or provider effect.
    dispatch.create_json(
        Path(config["runRoot"]) / "attempt-claimed.json",
        {
            "runId": run_id,
            "owner": str(os.getpid()),
            "deadlineUnix": deadline,
        },
    )
    native = native_factory(
        coordination_root=Path(config["coordinationRoot"]),
        run_id=run_id,
        clock=clock,
        monotonic=monotonic,
        sleep=sleep,
    )
    native.deadline = min(native.deadline, deadline - 240)
    # A failed claim must never close/overwrite somebody else's owner.json.
    native.claim()
    try:
        native.wait_ready()
        admission = DeadlineAdmission(api, config["accountId"], deadline, clock)
        admission.clock()
        result = run_once(
            api,
            run_id=run_id,
            owner=str(os.getpid()),
            subdomain=config["subdomain"],
            access=secrets.token_hex(32),
            canary="SYNTHETIC-" + secrets.token_hex(16),
            invoke_native=native.invoke_native,
            stop_requested=native.stop_requested,
            output_root=Path(config["outputRoot"]),
            native_root=Path(config["nativeRoot"]),
            lifecycle_factory=lifecycle_factory,
            clock=clock,
            sleep=sleep,
        )
        if native.stop_requested():
            result.update(stopPreserved=True, stopReason="dispatch_stop_observed")
            if result["outcome"] == "characterized":
                result["outcome"] = "stopped"
            if native.request_published:
                try:
                    native.publish_stop()
                except Exception:
                    result.update(
                        actionFailed=True,
                        outcome="failed",
                        stopReason="dispatch_stop_publication_failed",
                    )
        result.update(
            requestPublished=native.request_published,
            dispatchAcknowledged=native.acknowledged,
            requestedInputCount=int(native.request_published),
            actualInputCount=native.actual_input_count,
        )
        atomic_json(Path(config["outputRoot"]) / "action.json", result)
        return result
    finally:
        native.close()


def apply(
    packet_path,
    approved_sha2_256,
    *,
    admission_factory=None,
    provider_factory=None,
    execute_fn=None,
):
    """Exact separately authorized action; injected factories are trusted test code.

    The admission module owns protected current evidence, repeated authority,
    token custody, and its irreversible one-read claim. The caller owns the
    separate durable native attempt and current provider/lifecycle composition.
    """
    from scripts.post_screenshot_lifecycle import MANAGEMENT_PROFILE, Provider

    if admission_factory is None:
        from scripts.post_screenshot_admission import admit

        admission_factory = admit
    config = packet.validate_packet(packet_path, approved_sha2_256)
    admission = admission_factory(packet_path, approved_sha2_256, config=config)
    try:
        admission.authorize()
        token = admission.read_token_once()
        admission.authorize()
        api = (provider_factory or Provider)(
            config["accountId"],
            token,
            config["runId"],
            permit=admission,
            management_address=admission.management_address,
            management_profile=MANAGEMENT_PROFILE,
            exclusive_owner=True,
        )
        token = None
        return (execute_fn or execute)(api, config)
    finally:
        admission.close()


def run_once(
    api,
    *,
    run_id: str,
    owner: str,
    subdomain: str,
    access: str,
    canary: str,
    invoke_native,
    stop_requested,
    output_root,
    native_root,
    lifecycle_factory,
    clock=time.time,
    sleep=time.sleep,
):
    """Prepared one-attempt action runner; unavailable through the CLI.

    Only an approved caller supplies the adapter, synthetic markers and one native
    invocation callback. Tests inject all effects. This function never installs,
    reads credentials, invokes a shell, or retries a native operation itself.
    """
    if not re.fullmatch(r"[a-f0-9]{24}", run_id) or run_id == "0" * 24:
        raise ValueError("run_identity_invalid")
    preparation_started = clock()
    directory = Path(output_root)
    directory.mkdir(parents=True, exist_ok=False)
    life = lifecycle_factory(api, directory, run_id, owner, clock=clock)
    paths = {
        key: Path(native_root) / filename
        for key, filename in {
            "target": "target.json",
            "used": "target.used.json",
            "status": "status.json",
            "stop": "stop.json",
            "targetTemporary": "target.json.tmp",
            "statusTemporary": "status.json.tmp",
            "stopTemporary": "stop.json.tmp",
        }.items()
    }
    if any(path.exists() for path in paths.values()):
        life.journal.update(stage="native_paths_not_fresh", actionFailed=True)
        life.save()
        raise ValueError("native_paths_not_fresh")
    Path(native_root).mkdir(parents=True, exist_ok=True)
    life.journal.update(
        stage="planned",
        nativeInvocations=0,
        nativeTerminal=False,
        nativePaths={k: str(v) for k, v in paths.items()},
    )
    life.save()
    projection = None
    terminal = False
    sticky_stop = False
    native_invoked = False
    stop_at = None
    previous = clock()
    try:
        if stop_requested():
            sticky_stop = True
            life.journal["stopReason"] = "stop_before_preparation"
        else:
            target = life.prepare(subdomain, access, canary)
            if stop_requested():
                sticky_stop = True
                life.journal["stopReason"] = "stop_before_publication"
            else:
                atomic_json(paths["target"], target)
                life.journal["targetPublished"] = True
                life.save()
                # Record the irreversible attempt before handing control to native.
                life.journal["nativeInvocations"] = 1
                life.save()
                if stop_requested():
                    sticky_stop = True
                    life.journal["nativeInvocations"] = 0
                    life.journal["stopReason"] = "stop_before_invocation"
                    life.save()
                else:
                    # Final admission follows every durable write. The permit
                    # rechecks source/current protected evidence and withdrawal;
                    # native files and time are checked after that potentially
                    # slow I/O. No write or other action intervenes before invoke.
                    permit = getattr(api, "_permit", None)
                    if permit is not None:
                        permit.authorize()
                    if (
                        paths["target"].is_symlink()
                        or bounded_json(paths["target"]) != target
                        or any(
                            p.exists() or p.is_symlink() for k, p in paths.items() if k != "target"
                        )
                    ):
                        raise ValueError("native_preinvoke_paths_changed")
                    stopped_before_invoke = stop_requested()
                    cutoff = min(
                        getattr(life, "preparation_deadline", preparation_started + 240),
                        life.journal["expiresAtUnix"] - 240,
                    )
                    remaining_seconds = getattr(permit, "remaining_seconds", None)
                    if remaining_seconds is not None:
                        remaining_at = clock()
                        remaining = remaining_seconds()
                        if (
                            type(remaining) not in (int, float)
                            or not math.isfinite(remaining)
                            or remaining <= 0
                        ):
                            raise ValueError("native_preinvoke_permit_expired")
                        cutoff = min(cutoff, remaining_at + remaining)
                    # All permit/source/target/stop I/O precedes this final clock.
                    current = clock()
                    if (
                        not math.isfinite(current)
                        or current < previous
                        or current >= cutoff
                        or stopped_before_invoke
                    ):
                        raise ValueError("native_preinvoke_admission_withdrawn")
                    native_invoked = True
                    invoke_native(paths["target"], paths["status"])
                    for _ in range(1221):
                        current = clock()
                        if current < previous or current != current:
                            sticky_stop = True
                            life.journal["stopReason"] = "clock_invalid"
                        previous = current
                        if paths["status"].exists():
                            projection = classify(bounded_json(paths["status"]), run_id)
                            terminal = True
                            life.journal["nativeTerminal"] = True
                            life.journal["stopReason"] = "native_terminal"
                            break
                        if stop_requested() or current >= life.journal["expiresAtUnix"] - 240:
                            sticky_stop = True
                            life.journal["stopReason"] = "stop_or_cleanup_cutoff"
                        if sticky_stop and stop_at is None:
                            atomic_json(
                                paths["stop"],
                                {
                                    "schemaVersion": 1,
                                    "planVersion": VERSION,
                                    "runId": run_id,
                                    "owner": owner,
                                    "stop": True,
                                },
                            )
                            stop_at = current
                        if stop_at is not None and current >= stop_at + 20:
                            break
                        sleep(1)
                    if not terminal and not sticky_stop:
                        life.journal["stopReason"] = "watch_iteration_limit"
                        sticky_stop = True
    except Exception:
        life.journal["nativeInvocations"] = int(native_invoked)
        life.journal["stopReason"] = "action_failure"
        life.journal["actionFailed"] = True
        sticky_stop = True
    finally:
        permit = getattr(api, "_permit", None)
        if permit is not None:
            try:
                permit.begin_cleanup()
            except Exception:
                life.journal["actionFailed"] = True
        try:
            if (
                sticky_stop
                and life.journal.get("targetPublished", False)
                and not terminal
                and not paths["stop"].exists()
            ):
                atomic_json(
                    paths["stop"],
                    {
                        "schemaVersion": 1,
                        "planVersion": VERSION,
                        "runId": run_id,
                        "owner": owner,
                        "stop": True,
                    },
                )
            if projection is not None:
                atomic_json(directory / "native-terminal.json", projection)
        except Exception:
            life.journal["actionFailed"] = True
        try:
            life.observe()
        except Exception:
            life.journal["observationsConfirmed"] = False
        receipt = life.cleanup()
        # Preserve private target/status/journal for exact review and explicit
        # identity-matched local teardown. A second run cannot overwrite them.
        life.journal["targetRetained"] = paths["target"].exists() or paths["used"].exists()
        life.journal["stopPreserved"] = sticky_stop
        life.save()
    result = {
        **receipt,
        "nativeInvocations": life.journal["nativeInvocations"],
        "nativeTerminal": terminal,
        "stopPreserved": sticky_stop,
        "actionFailed": life.journal.get("actionFailed", False),
    }
    result["nativeOutcome"] = projection["outcome"] if projection else "unmeasured"
    result["methodSpecificPostQualified"] = False
    result["receiverClassification"] = (
        "observed_pending_review" if receipt["observationsConfirmed"] else "unconfirmed"
    )
    result["cleanupClassification"] = (
        "confirmed_same_owner" if receipt["cleanupConfirmed"] else "unconfirmed_retained"
    )
    result["caseClassification"] = (
        projection
        if projection
        else {
            "postCases": [{"caseId": case, "classification": "unmeasured"} for case in CASES],
            "diagnosticGet": "unmeasured",
            "receiverClassification": "unmeasured",
        }
    )
    result["outcome"] = (
        "failed"
        if result["actionFailed"]
        else "stopped"
        if sticky_stop or result["nativeOutcome"] == "stopped"
        else "failed"
        if result["nativeOutcome"] == "failed"
        or not terminal
        or not receipt["cleanupConfirmed"]
        or not receipt["observationsConfirmed"]
        else "characterized"
    )
    atomic_json(directory / "action.json", result)
    return result


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "mode": "offline",
                "actionReady": False,
                "productionQualified": False,
                "actionGate": "separate_exact_current_packet_and_admission_required",
            }
        )
    )
