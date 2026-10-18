"""One approved POST attempt with a prewarmed, bounded Node file handshake.

The original runner and bridge remain sealed. This owner accepts no commands or
native paths from handshake files and never initializes computer-use itself.
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

from scripts import group_post_characterization as post

ACTION = "invoke_characterize_synthetic_post_v1_once"
OLD_RUN_ID = "c01ba6d2c2754597aa311c9f"
NAMES = (
    "owner.json",
    "ready.json",
    "invoke.json",
    "attempted.json",
    "ack.json",
    "operator-stop.json",
    "challenge-prewarm.json",
    "response-prewarm.json",
    "challenge-dispatch.json",
    "response-dispatch.json",
)


def create_json(path, value):
    """Exclusive, flushed publication; a partial/failed publication fails closed."""
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class NativeFiles:
    """Single owner/request. Any uncertain, stopped or lost owner stays stopped."""

    def __init__(
        self,
        *,
        coordination_root,
        run_id,
        clock=time.time,
        monotonic=time.monotonic,
        sleep=time.sleep,
    ):
        self.root = Path(coordination_root)
        if (
            not self.root.is_absolute()
            or not re.fullmatch(r"[a-f0-9]{24}", run_id)
            or run_id in (OLD_RUN_ID, "0" * 24)
        ):
            raise ValueError("dispatch_binding_invalid")
        if self.root == post.NATIVE_ROOT or post.NATIVE_ROOT in self.root.parents:
            raise ValueError("coordination_root_must_be_separate")
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        self.started, self.previous = monotonic(), clock()
        if not math.isfinite(self.started) or not math.isfinite(self.previous):
            raise ValueError("dispatch_clock_invalid")
        self.deadline = self.previous + 960
        self.identity = {
            "schemaVersion": 1,
            "planVersion": post.VERSION,
            "runId": run_id,
            "owner": str(os.getpid()),
            "generation": secrets.token_hex(16),
        }
        self.paths = {name: self.root / name for name in NAMES}
        self.latched = self.attempted = self.request_published = False
        self.acknowledged = False
        self.actual_input_count = 0
        self.resource_expiry = 0
        self.checkpoints = set()

    def claim(self):
        self.root.mkdir(parents=True, exist_ok=False)
        create_json(self.paths["owner.json"], self.owner_value("active"))

    def owner_value(self, state):
        return {**self.identity, "state": state, "deadlineUnix": self.deadline}

    def correlated(self, value, extra):
        return (
            isinstance(value, dict)
            and set(value) == {*self.identity, *extra}
            and all(type(value[k]) is type(v) and value[k] == v for k, v in self.identity.items())
        )

    def stop_requested(self):
        if self.latched:
            return True
        try:
            now, elapsed = self.clock(), self.monotonic() - self.started
            owner = post.bounded_json(self.paths["owner.json"], 4096)
            if (
                not self.correlated(owner, {"state", "deadlineUnix"})
                or owner != self.owner_value("active")
                or type(owner["deadlineUnix"]) not in (int, float)
                or str(os.getpid()) != self.identity["owner"]
                or not math.isfinite(now)
                or not math.isfinite(elapsed)
                or now < self.previous
                or elapsed < 0
                or now >= self.deadline
                or elapsed >= 960
                or self.paths["operator-stop.json"].exists()
                or (self.root / "operator-stop.json.tmp").exists()
                or (post.NATIVE_ROOT / "stop.json").exists()
                or (post.NATIVE_ROOT / "stop.json.tmp").exists()
            ):
                self.latched = True
            self.previous = now
        except Exception:
            self.latched = True
        return self.latched

    def wait_ready(self):
        """Node proves its actual writer before the first provider operation."""
        started = self.monotonic()
        for _ in range(31):
            if self.stop_requested() or self.monotonic() - started >= 30:
                break
            self.service_checkpoint("prewarm")
            if self.paths["ready.json"].exists():
                try:
                    value = post.bounded_json(self.paths["ready.json"], 4096)
                except Exception:
                    self.latched = True
                    raise ValueError("dispatch_ready_invalid") from None
                if (
                    self.correlated(value, {"state"})
                    and value["state"] == "ready"
                    and "prewarm" in self.checkpoints
                ):
                    return
                break
            self.sleep(1)
        self.latched = True
        raise ValueError("dispatch_not_prewarmed")

    def service_checkpoint(self, phase, request=None):
        """Answer one fresh bounded owner challenge, without an OS PID probe.

        This proves this Python owner serviced a fresh checkpoint. It does not
        claim an atomic OS-lifecycle check across the later native input.
        """
        challenge_path = self.paths[f"challenge-{phase}.json"]
        if not challenge_path.exists():
            return
        try:
            challenge = post.bounded_json(challenge_path, 4096)
            now = self.clock()
            if (
                self.stop_requested()
                or not self.correlated(challenge, {"phase", "nonce", "deadlineUnix"})
                or challenge["phase"] != phase
                or not isinstance(challenge["nonce"], str)
                or not re.fullmatch(r"[a-f0-9]{32}", challenge["nonce"])
                or type(challenge["deadlineUnix"]) not in (int, float)
                or not math.isfinite(challenge["deadlineUnix"])
                or not now < challenge["deadlineUnix"] <= min(now + 10, self.deadline)
            ):
                raise ValueError("owner_challenge_invalid")
            if phase == "dispatch":
                marker = post.bounded_json(self.paths["attempted.json"], 4096)
                published = post.bounded_json(self.paths["invoke.json"], 4096)
                if (
                    request is None
                    or challenge["deadlineUnix"] > request["deadlineUnix"]
                    or published != request
                    or marker != request
                    or any(
                        not self.correlated(
                            value, {"action", "deadlineUnix", "requestedInputCount"}
                        )
                        or type(value["requestedInputCount"]) is not int
                        or type(value["deadlineUnix"]) not in (int, float)
                        for value in (published, marker)
                    )
                ):
                    raise ValueError("owner_dispatch_challenge_invalid")
            response_path = self.paths[f"response-{phase}.json"]
            if phase in self.checkpoints:
                response = post.bounded_json(response_path, 4096)
                if (
                    not self.correlated(response, {"phase", "nonce", "deadlineUnix"})
                    or type(response["deadlineUnix"]) not in (int, float)
                    or response != challenge
                ):
                    raise ValueError("owner_challenge_changed")
                return
            if (
                response_path.exists()
                or self.stop_requested()
                or self.clock() >= challenge["deadlineUnix"]
                or any(
                    (post.NATIVE_ROOT / name).exists()
                    for name in ("status.json", "status.json.tmp")
                )
            ):
                raise ValueError("owner_response_not_fresh")
            create_json(response_path, challenge)
            self.checkpoints.add(phase)
        except Exception:
            self.latched = True
            raise ValueError("owner_challenge_refused") from None

    def invoke_native(self, target, status):
        if self.attempted or self.stop_requested():
            self.latched = True
            raise ValueError("native_dispatch_stopped")
        self.attempted = True
        if target != post.NATIVE_ROOT / "target.json" or status != post.NATIVE_ROOT / "status.json":
            self.latched = True
            raise ValueError("native_paths_invalid")
        target_value = post.bounded_json(target)
        if target_value.get("runId") != self.identity["runId"]:
            self.latched = True
            raise ValueError("native_target_identity_invalid")
        self.resource_expiry = target_value["expiresAtUnix"]
        if (
            any(self.paths[name].exists() for name in ("invoke.json", "ack.json", "attempted.json"))
            or self.stop_requested()
        ):
            self.latched = True
            raise ValueError("dispatch_not_fresh")
        request = {
            **self.identity,
            "action": ACTION,
            "deadlineUnix": min(self.clock() + 30, self.deadline),
            "requestedInputCount": 1,
        }
        # A reader can act as soon as publication becomes visible, even if the
        # subsequent flush/fsync raises. Record intent and possible input first.
        self.request_published = True
        self.actual_input_count = None
        try:
            if self.publish_and_wait(request):
                return
        except Exception:
            # Publication/read/time failures cannot establish that no input ran.
            pass
        self.latched = True
        self.stop_and_grace(status)
        raise ValueError("native_dispatch_unconfirmed")

    def publish_and_wait(self, request):
        create_json(self.paths["invoke.json"], request)
        started = self.monotonic()
        for _ in range(31):
            if (
                self.stop_requested()
                or self.clock() >= request["deadlineUnix"]
                or self.monotonic() - started >= 30
            ):
                break
            self.service_checkpoint("dispatch", request)
            if self.paths["ack.json"].exists():
                try:
                    ack = post.bounded_json(self.paths["ack.json"], 4096)
                    marker = post.bounded_json(self.paths["attempted.json"], 4096)
                    if (
                        not self.correlated(
                            ack, {"outcome", "requestedInputCount", "actualInputCount"}
                        )
                        or "dispatch" not in self.checkpoints
                        or type(ack["requestedInputCount"]) is not int
                        or ack["requestedInputCount"] != 1
                        or ack["outcome"] not in ("dispatched", "stopped", "unknown")
                        or (ack["outcome"] == "dispatched" and ack["actualInputCount"] != 1)
                        or (ack["outcome"] == "stopped" and ack["actualInputCount"] != 0)
                        or (
                            ack["outcome"] == "unknown" and ack["actualInputCount"] not in (None, 1)
                        )
                        or (
                            ack["actualInputCount"] is not None
                            and (
                                type(ack["actualInputCount"]) is not int
                                or ack["actualInputCount"] not in (0, 1)
                            )
                        )
                        or marker != request
                        or not self.correlated(
                            marker, {"action", "deadlineUnix", "requestedInputCount"}
                        )
                        or type(marker["requestedInputCount"]) is not int
                        or type(marker["deadlineUnix"]) not in (int, float)
                    ):
                        break
                    self.acknowledged = True
                    self.actual_input_count = ack["actualInputCount"]
                    if ack["outcome"] == "dispatched" and self.actual_input_count == 1:
                        return True
                    break
                except Exception:
                    break
            self.sleep(1)
        return False

    def publish_stop(self):
        path = post.NATIVE_ROOT / "stop.json"
        if not path.exists():
            create_json(
                path,
                {
                    "schemaVersion": 1,
                    "planVersion": post.VERSION,
                    "runId": self.identity["runId"],
                    "owner": self.identity["owner"],
                    "stop": True,
                },
            )

    def stop_and_grace(self, status):
        try:
            self.publish_stop()
        except Exception:
            # A failed stop publication must not skip the bounded in-flight
            # return period before the runner starts remote teardown.
            pass
        started = self.monotonic()
        until = min(self.clock() + 20, self.resource_expiry - 200)
        for _ in range(21):
            now, elapsed = self.clock(), self.monotonic() - started
            if (
                not math.isfinite(now)
                or not math.isfinite(elapsed)
                or now >= until
                or elapsed >= 20
            ):
                break
            if status.exists():
                try:
                    post.native_terminal(post.bounded_json(status), self.identity["runId"])
                    break
                except Exception:
                    pass
            self.sleep(1)

    def close(self):
        self.latched = True
        post.atomic_json(self.paths["owner.json"], self.owner_value("closed"))


def execute(
    api, inputs, *, coordination_root, clock=time.time, monotonic=time.monotonic, sleep=time.sleep
):
    """Concrete provider→reviewed runner→prewarmed Node owner composition."""
    if (
        set(inputs) != {"runId", "accountId", "subdomain"}
        or api.account != inputs["accountId"]
        or not re.fullmatch(r"[a-f0-9]{32}", inputs["accountId"])
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", inputs["subdomain"])
    ):
        raise ValueError("provider_config_mismatch")
    native = NativeFiles(
        coordination_root=coordination_root,
        run_id=inputs["runId"],
        clock=clock,
        monotonic=monotonic,
        sleep=sleep,
    )
    native.claim()
    try:
        native.wait_ready()
        result = post.run_once(
            api,
            run_id=inputs["runId"],
            owner=str(os.getpid()),
            subdomain=inputs["subdomain"],
            access=secrets.token_hex(32),
            canary="SYNTHETIC-" + secrets.token_hex(16),
            invoke_native=native.invoke_native,
            stop_requested=native.stop_requested,
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
    """Open a token only after exact source, consent and private config binding."""
    from scripts.prepare_group_post_dispatch import validate_packet

    config = validate_packet(Path(packet_path), approved_sha2_256)
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
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", type=Path)
    parser.add_argument("--approved-sha2-256")
    args = parser.parse_args()
    if args.apply is None:
        print(
            json.dumps(
                {
                    "mode": "offline_preparation",
                    "productionQualified": False,
                    "action": ACTION,
                    "requestLifetimeSeconds": 30,
                    "nativeRoot": str(post.NATIVE_ROOT),
                }
            )
        )
        return 0
    try:
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
        print(
            '{"outcome":"failed","reasonCode":"dispatch_refused_or_failed","productionQualified":false}'
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
