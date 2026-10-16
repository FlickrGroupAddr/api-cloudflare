"""One private local POST owner; CLI is offline unless an exact packet is approved.

The operator uses supported Node REPL / @oai/sky separately. This module never
initializes native automation, starts a process, or accepts commands from files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import time
from pathlib import Path

from scripts import group_post_characterization as post

RUN_ID = "c01ba6d2c2754597aa311c9f"
CONFIG = post.ROOT / ".coordination-runs/group-post-execution-bridge/private/config.json"
TOKEN = Path(r"C:\Temp\fga-post-operator-token.txt")
APPROVAL = CONFIG.with_name("approved-packet.json")
ACCOUNT_SOURCE = Path(
    "C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/private-evidence/0036/"
    "20261016T214740Z/private/restoration-inputs.json"
)
SUBDOMAIN_SOURCE = Path("C:/Temp/FGA-existing-photo-network/ready-38945950488/ready.json")
HANDSHAKE_NAMES = ("owner.json", "invoke.json", "ack.json", "operator-stop.json")


def description(*, manifest_digest=None):
    """Safe offline projection: no private config or token file is opened."""
    return {
        "schemaVersion": 1,
        "mode": "offline_preparation",
        "runId": RUN_ID,
        "productionQualified": False,
        "config": str(CONFIG),
        "tokenFile": str(TOKEN),
        "approval": str(APPROVAL),
        "manifestSha2_256": manifest_digest or post.digest(post.PACKET / "manifest.json"),
        "bridgeSha2_256": post.digest(Path(__file__)),
        "handshakeRoot": str(post.NATIVE_ROOT / "bridge"),
        "nativeRoute": "Node REPL / @oai/sky",
        "attempts": 1,
    }


def snapshot(path, maximum=8192):
    """Hash and parse the very same bounded bytes; never reopen for validation."""
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("private_packet_byte_limit")
    return hashlib.sha256(raw).hexdigest(), json.loads(raw)


def load_inputs(value=None):
    """Read exact private identities and provenance; never open the token."""
    if value is None:
        _, value = snapshot(CONFIG)
    if (
        not isinstance(value, dict)
        or set(value)
        != {"runId", "accountId", "subdomain", "tokenFile", "accountSource", "subdomainSource"}
        or value["runId"] != RUN_ID
        or not isinstance(value["accountId"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", value["accountId"])
        or not isinstance(value["subdomain"], str)
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value["subdomain"])
        or value["tokenFile"] != str(TOKEN)
        or value["accountSource"] != str(ACCOUNT_SOURCE)
        or value["subdomainSource"] != str(SUBDOMAIN_SOURCE)
        or any(
            not isinstance(value[k], str) or not Path(value[k]).is_absolute()
            for k in ("accountSource", "subdomainSource")
        )
    ):
        raise ValueError("private_config_invalid")
    return value


class NativeFiles:
    """Exactly one correlated invoke request and acknowledgement, with sticky stop.

    The root operator owns UI input. Unknown input results are terminal, never
    retryable. Native target/status files retain the reviewed #58 schema.
    """

    def __init__(self, *, clock=time.time, monotonic=time.monotonic, sleep=time.sleep):
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        self.owner = str(os.getpid())
        self.generation = secrets.token_hex(16)
        self.root = post.NATIVE_ROOT / "bridge"
        self.paths = {name: self.root / name for name in HANDSHAKE_NAMES}
        self.latched = False
        self.attempted = False
        self.request_published = False
        self.resource_expiry = 0
        self.started = monotonic()
        self.deadline = clock() + 960
        self.identity = {
            "schemaVersion": 1,
            "planVersion": post.VERSION,
            "runId": RUN_ID,
            "owner": self.owner,
            "generation": self.generation,
        }

    def claim(self):
        # Exclusive directory creation is the one local job claim. Never reuse.
        self.root.mkdir(parents=True, exist_ok=False)
        post.atomic_json(
            self.paths["owner.json"],
            {**self.identity, "state": "active", "deadlineUnix": self.deadline},
        )

    def correlated(self, value):
        return isinstance(value, dict) and all(value.get(k) == v for k, v in self.identity.items())

    def stop_requested(self):
        if self.latched:
            return True
        try:
            owner = post.bounded_json(self.paths["owner.json"], 4096)
            if (
                not self.correlated(owner)
                or owner.get("state") != "active"
                or str(os.getpid()) != self.owner
                or not math.isfinite(self.clock())
                or self.clock() >= self.deadline
                or self.monotonic() - self.started >= 960
            ):
                self.latched = True
            # Any stop file, even stale/malformed, fails closed. Never remove it.
            if (
                self.paths["operator-stop.json"].exists()
                or (post.NATIVE_ROOT / "stop.json").exists()
            ):
                self.latched = True
        except Exception:
            self.latched = True
        return self.latched

    def invoke_native(self, target, status):
        if self.attempted or self.stop_requested():
            self.latched = True
            raise ValueError("native_dispatch_stopped")
        self.attempted = True
        if target != post.NATIVE_ROOT / "target.json" or status != post.NATIVE_ROOT / "status.json":
            self.latched = True
            raise ValueError("native_paths_invalid")
        # Validate publication identity without copying synthetic values to handshake.
        target_value = post.bounded_json(target)
        if target_value.get("runId") != RUN_ID:
            self.latched = True
            raise ValueError("native_target_identity_invalid")
        self.resource_expiry = target_value["expiresAtUnix"]
        if self.paths["ack.json"].exists() or self.stop_requested():
            self.latched = True
            raise ValueError("native_ack_not_fresh")
        post.atomic_json(
            self.paths["invoke.json"],
            {
                **self.identity,
                "action": "invoke_characterize_synthetic_post_v1_once",
                "target": str(target),
                "status": str(status),
                "deadlineUnix": min(self.clock() + 30, self.deadline),
            },
        )
        self.request_published = True
        started = self.monotonic()
        for _ in range(31):
            if self.stop_requested() or self.monotonic() - started >= 30:
                break
            if self.paths["ack.json"].exists():
                try:
                    ack = post.bounded_json(self.paths["ack.json"], 4096)
                    if (
                        set(ack) != {*self.identity, "outcome"}
                        or not self.correlated(ack)
                        or ack["outcome"] != "dispatched"
                    ):
                        break
                    return
                except Exception:
                    break
            self.sleep(1)
        self.latched = True
        self.stop_and_grace(status)
        raise ValueError("native_dispatch_unconfirmed")

    def publish_stop(self):
        path = post.NATIVE_ROOT / "stop.json"
        if not path.exists():
            post.atomic_json(
                path,
                {
                    "schemaVersion": 1,
                    "planVersion": post.VERSION,
                    "runId": RUN_ID,
                    "owner": self.owner,
                    "stop": True,
                },
            )

    def stop_and_grace(self, status):
        """Unknown dispatch may be in flight: publish stop then allow bounded return."""
        self.publish_stop()
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
                    post.native_terminal(post.bounded_json(status), RUN_ID)
                    break
                except Exception:
                    pass
            self.sleep(1)

    def close(self):
        self.latched = True
        post.atomic_json(
            self.paths["owner.json"],
            {**self.identity, "state": "closed", "deadlineUnix": self.deadline},
        )


def execute(api, inputs, *, clock=time.time, monotonic=time.monotonic, sleep=time.sleep):
    """Concrete composition, injectable only at provider/time for offline tests."""
    if api.account != inputs["accountId"] or inputs["runId"] != RUN_ID:
        raise ValueError("provider_config_mismatch")
    native = NativeFiles(clock=clock, monotonic=monotonic, sleep=sleep)
    native.claim()
    try:
        result = post.run_once(
            api,
            run_id=RUN_ID,
            owner=str(os.getpid()),
            subdomain=inputs["subdomain"],
            access=secrets.token_hex(32),
            canary="SYNTHETIC-" + secrets.token_hex(16),
            invoke_native=native.invoke_native,
            stop_requested=native.stop_requested,
            clock=clock,
            sleep=sleep,
        )
        # #58 observes terminal before stop. Preserve a concurrent operator stop
        # in the final bridge verdict and its private action/journal receipts.
        if native.stop_requested():
            result["stopPreserved"] = True
            result["stopReason"] = "bridge_stop_observed"
            if result["outcome"] == "characterized":
                result["outcome"] = "stopped"
            if native.request_published:
                native.publish_stop()
            directory = post.OUT / RUN_ID
            journal_path = directory / "private/journal.json"
            journal = post.bounded_json(journal_path)
            journal.update(stopPreserved=True, stopReason="bridge_stop_observed")
            post.atomic_json(journal_path, journal)
            post.atomic_json(directory / "action.json", result)
        return result
    finally:
        native.close()


def apply(approved_sha2_256):
    """Future #60 action only: exact approved artifact and private config required.

    No token is opened until both digests and every pinned artifact match. An
    approval file is an execution binding, not a substitute for owner authority.
    """
    if not re.fullmatch(r"[a-f0-9]{64}", approved_sha2_256):
        raise ValueError("approval_digest_required")
    approval_digest, approval_value = snapshot(APPROVAL)
    if approval_digest != approved_sha2_256:
        raise ValueError("approval_digest_changed")
    config_digest, config_value = snapshot(CONFIG)
    manifest_digest, manifest_value = snapshot(post.PACKET / "manifest.json", 65536)
    expected = {
        **description(manifest_digest=manifest_digest),
        "configSha2_256": config_digest,
        "mode": "approved_execution",
    }
    if approval_value != expected or manifest_value != post.packet():
        raise ValueError("approved_packet_changed")
    inputs = load_inputs(config_value)
    # Bounded secret read, no exception text/provider text is printed by CLI.
    with TOKEN.open("rb") as source:
        token = source.read(4097)
    if len(token) > 4096 or not re.fullmatch(rb"[A-Za-z0-9_-]{20,4096}", token):
        raise ValueError("provider_token_invalid")
    api = post.Provider(inputs["accountId"], token.decode("ascii"), RUN_ID)
    return execute(api, inputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-sha2-256")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps(description(), indent=2))
        return 0
    try:
        if not args.approved_sha2_256:
            raise ValueError("approval_digest_required")
        result = apply(args.approved_sha2_256)
        # The exact action receipt already exists privately; no arbitrary fields.
        print(
            json.dumps(
                {
                    "outcome": result["outcome"],
                    "cleanupConfirmed": result["cleanupConfirmed"],
                    "productionQualified": False,
                }
            )
        )
        return 0 if result["outcome"] == "characterized" else 1
    except Exception:
        print(
            '{"outcome":"failed","reasonCode":"bridge_refused_or_failed","productionQualified":false}'
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
