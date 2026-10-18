"""Fresh exact-packet caller for the renewed finite synthetic POST attempt.

The sealed 0160 protocol/lifecycle is reused without rewriting its closure.
This caller never initializes native control or obtains authorization itself.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import time
from pathlib import Path

from scripts import group_post_dispatch as sealed
from scripts import prepare_renewed_group_post_attempt as packet

post = sealed.post


class DeadlineAdmission:
    """Fence lifecycle initialization and the first provider effect after source I/O.

    Once admitted, the unchanged lifecycle owns its original relative expiry and
    cleanup budget. This wrapper does not cancel or shorten cleanup requests.
    """

    def __init__(self, api, expected_account, deadline, clock):
        self.api, self.deadline, self.source_clock = api, deadline, clock
        self.expected_account = expected_account
        self.admitted = False

    @property
    def account(self):
        if self.api.account != self.expected_account:
            raise ValueError("provider_config_mismatch")
        return self.expected_account

    def clock(self):
        now = self.source_clock()
        if not self.admitted and (not math.isfinite(now) or now + 1200 > self.deadline):
            raise ValueError("action_deadline_insufficient")
        return now

    def call(self, method, path, body=None, *, timeout=20):
        self.clock()
        if self.account != self.expected_account:
            raise ValueError("provider_config_mismatch")
        self.admitted = True
        return self.api.call(method, path, body, timeout=timeout)


def execute(
    api,
    inputs,
    *,
    coordination_root,
    action_deadline,
    clock=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    """Compose the provider, reviewed runner and prewarmed Node owner."""
    if (
        set(inputs) != {"runId", "accountId", "subdomain"}
        or inputs["runId"] != packet.RUN_ID
        or Path(coordination_root) != packet.RUN_ROOT / "handshake"
        or api.account != inputs["accountId"]
        or not re.fullmatch(r"[a-f0-9]{32}", inputs["accountId"])
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", inputs["subdomain"])
    ):
        raise ValueError("provider_config_mismatch")
    native = sealed.NativeFiles(
        coordination_root=coordination_root,
        run_id=inputs["runId"],
        clock=clock,
        monotonic=monotonic,
        sleep=sleep,
    )
    if (
        type(action_deadline) not in (int, float)
        or not math.isfinite(action_deadline)
        or not clock() + 1230 <= action_deadline <= clock() + 1800
    ):
        raise ValueError("action_deadline_invalid")
    native.deadline = min(native.deadline, action_deadline - 240)
    native.claim()
    try:
        native.wait_ready()
        if clock() + 1200 > action_deadline:
            raise ValueError("action_deadline_insufficient")
        admission = DeadlineAdmission(api, inputs["accountId"], action_deadline, clock)
        result = post.run_once(
            admission,
            run_id=inputs["runId"],
            owner=str(os.getpid()),
            subdomain=inputs["subdomain"],
            access=secrets.token_hex(32),
            canary="SYNTHETIC-" + secrets.token_hex(16),
            invoke_native=native.invoke_native,
            stop_requested=native.stop_requested,
            clock=admission.clock,
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
            requestedInputCount=int(native.request_published),
            dispatchAttempted=native.paths["attempted.json"].exists(),
            dispatchAcknowledged=native.acknowledged,
            actualInputCount=native.actual_input_count,
        )
        directory = post.OUT / inputs["runId"]
        journal_path = directory / "private/journal.json"
        journal = post.bounded_json(journal_path)
        journal.update(
            {
                k: result[k]
                for k in (
                    "stopPreserved",
                    "requestPublished",
                    "requestedInputCount",
                    "dispatchAttempted",
                    "dispatchAcknowledged",
                    "actualInputCount",
                    "actionFailed",
                )
            }
        )
        if "stopReason" in result:
            journal["stopReason"] = result["stopReason"]
        post.atomic_json(journal_path, journal)
        post.atomic_json(directory / "action.json", result)
        return result
    finally:
        native.close()


def apply(packet_path, approved_sha2_256):
    """Read the fresh token only after exact current approval/config/source checks.

    Invocation is reserved for a later separately approved live run. Source
    implementation/test approval does not authorize this credential read.
    """
    config = packet.validate_packet(Path(packet_path), approved_sha2_256)
    if Path(config["nativeRoot"]) != post.NATIVE_ROOT:
        raise ValueError("native_root_changed")
    with Path(config["tokenFile"]).open("rb") as stream:
        token = stream.read(4097)
    if len(token) > 4096 or not re.fullmatch(rb"[A-Za-z0-9_-]{20,4096}", token):
        raise ValueError("provider_token_invalid")
    api = post.Provider(config["accountId"], token.decode("ascii"), config["runId"])
    return execute(
        api,
        {k: config[k] for k in ("runId", "accountId", "subdomain")},
        coordination_root=Path(config["coordinationRoot"]),
        action_deadline=config["actionDeadlineUnix"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", type=Path)
    parser.add_argument("--approved-sha2-256")
    args = parser.parse_args()
    try:
        if args.apply is None:
            packet.validate_manifest()
            print(
                json.dumps(
                    {
                        "mode": "offline_preparation",
                        "runId": packet.RUN_ID,
                        "actionReady": False,
                        "productionQualified": False,
                    }
                )
            )
            return 0
        result = apply(args.apply, args.approved_sha2_256)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "outcome",
                        "cleanupConfirmed",
                        "requestedInputCount",
                        "actualInputCount",
                        "dispatchAcknowledged",
                    )
                }
            )
        )
        return 0 if result["outcome"] == "characterized" else 1
    except Exception:
        print('{"outcome":"refused_or_failed","productionQualified":false}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
