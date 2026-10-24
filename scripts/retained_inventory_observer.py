"""Memory-only historical inventory observation. Import and CLI are inert.

The trusted Primary supplies independently authenticated, consumable admission.
This module cannot authenticate a human from JSON, a boolean, or a source pin.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast


class Refused(ValueError):
    pass


def require(value):
    if not value:
        raise Refused("HISTORICAL_OBSERVATION_STOP")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def document(raw: bytes) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result

    result = json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda _: require(False),
    )
    require(type(result) is dict)
    return cast(dict[str, Any], result)


def selected_row(raw):
    """Only source-defined /files name/bytes/sha256 meanings; no closed shape invented."""
    rows: list[dict[str, Any]] = document(raw)["files"]
    require(type(rows) is list and len(rows) == 15)
    require(all(type(row) is dict and type(row.get("name")) is str for row in rows))
    require(len({row["name"] for row in rows}) == 15)
    require(
        all(
            type(row.get("bytes")) is int
            and 0 < row["bytes"] <= 16777216
            and type(row.get("sha256")) is str
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
            for row in rows
        )
    )
    require(sum(row["bytes"] for row in rows) == 1083133)
    selected = [row for row in rows if row["name"] == "restoration-inputs.json"]
    require(len(selected) == 1)
    row = selected[0]
    require(type(row.get("bytes")) is int and 0 < row["bytes"] <= 262144)
    require(type(row.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]))
    return row["bytes"], row["sha256"]


def historical_projection(raw):
    """Validate only public producer fields; values and locators remain held."""
    value = document(raw)
    require(type(value["accountId"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["accountId"]))
    require(type(value["worker"]) is str and 0 < len(value["worker"]) <= 256)
    captured = value["captured"]
    require(type(captured) is dict and 0 < len(captured) <= 128)
    for name, row in captured.items():
        require(type(name) is str and type(row) is dict)
        row = cast(dict[str, Any], row)
        require(type(row["path"]) is str and 0 < len(row["path"]) <= 4096)
        require(type(row["SHA2-256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["SHA2-256"]))
    weights, modules = value["pinnedActiveVersionWeights"], value["exactVersionModules"]
    require(type(weights) is dict and 0 < len(weights) <= 128)
    require(
        all(
            type(k) is str
            and type(v) in (int, float)
            and math.isfinite(cast(float, v))
            and 0 < cast(float, v) <= 100
            for k, v in weights.items()
        )
    )
    require(sum(weights.values()) == 100)
    require(type(modules) is dict and set(modules) == set(weights))
    for row in modules.values():
        row = cast(dict[str, Any], row)
        require(type(row) is dict and type(row["main_module"]) is str)
        require(type(row["modules"]) is list and 0 < len(row["modules"]) <= 128)
        for module in row["modules"]:
            module = cast(dict[str, Any], module)
            require(type(module) is dict and type(module["name"]) is str)
            require(type(module["bytes"]) is int and module["bytes"] >= 0)
            require(type(module["content_type"]) is str)
            require(
                type(module["SHA2-256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", module["SHA2-256"])
            )
        require(
            row["main_module"]
            in [cast(dict[str, Any], module)["name"] for module in row["modules"]]
        )
    require(
        all(
            type(value[k]) is bool
            for k in ("deploymentStable", "artifactBoundToEveryActiveVersion", "restorationReady")
        )
    )
    return {
        "kind": "HISTORICAL_RECORD_SHAPE_ONLY",
        "selectedInventoryDigestMatched": True,
        "identityAndModuleMetadataHeld": True,
        "referencedPayloadsVerified": False,
        "currentProviderFactsEstablished": False,
        "custodyContinuityEstablished": False,
        "permissionOrQualificationEstablished": False,
    }


@dataclass(frozen=True, repr=False)
class HeldObservation:
    index: bytes
    restoration: bytes
    projection: dict

    def __repr__(self):
        return "<HeldHistoricalInventoryObservation>"


@dataclass(frozen=True, repr=False)
class Outcome:
    report: dict
    held: HeldObservation | None

    def __repr__(self):
        return "<HistoricalInventoryOutcome>"


class Observer:
    """One in-process attempt; Primary's admission must also be globally spent.

    backend is the separately pinned mature stable-reader/privacy adapter.
    Admission is a trusted callable, consuming Primary-held authority for this
    exact scope fingerprint. A fake callback is ONLY appropriate in tests.
    """

    def __init__(self, spec, backend):
        self.spec, self.backend, self.spent = MappingProxyType(dict(spec)), backend, False

    def run(
        self,
        *,
        execute=False,
        admission: Any = None,
        starts_at: Any = None,
        ends_at: Any = None,
        wall_clock: Any = None,
        monotonic: Any = None,
    ):
        report = {
            "status": "DISABLED",
            "phase": "DISABLED",
            "category": "NONE",
            "failedCallbackKind": "NONE",
            "failedCallbackEffects": "NONE",
            "contentCallsAttempted": 0,
            "contentCallsCompleted": 0,
            "validatedBytesReturned": 0,
            "privacyCallsAttempted": 0,
            "privacyCallsCompleted": 0,
            "outerSnapshotsAttempted": 0,
            "outerSnapshotsCompleted": 0,
            "failedReadMaximumBytes": 0,
            "failureEffects": "NONE",
            "currentFactQualification": "NO_GO",
            "privateWrites": 0,
            "providerCalls": 0,
            "credentialReads": 0,
        }
        if execute is not True:
            return Outcome(report, None)
        try:
            report.update(phase="ATTEMPT_GATE", category="ATTEMPT_GATE")
            require(not self.spent)
            self.spent = True
            report.update(phase="PRIMARY_ADMISSION", category="PRIMARY_ADMISSION")
            require(callable(admission))
            report.update(phase="CLOCK_GATE", category="CLOCK")
            require(callable(wall_clock) and callable(monotonic))
            require(
                all(
                    type(t) is datetime and t.tzinfo == UTC and t.microsecond == 0
                    for t in (starts_at, ends_at)
                )
            )
            require(timedelta(0) < ends_at - starts_at <= timedelta(seconds=30))
            initial = monotonic()
            require(type(initial) in (int, float) and math.isfinite(cast(float, initial)))
            initial = cast(float, initial)
            last_wall, last_mono = starts_at, initial

            def fence():
                nonlocal last_wall, last_mono
                try:
                    now, tick = wall_clock(), monotonic()
                    require(
                        type(now) is datetime
                        and now.tzinfo == UTC
                        and starts_at <= now < ends_at
                        and now >= last_wall
                    )
                    require(
                        type(tick) in (int, float)
                        and math.isfinite(cast(float, tick))
                        and last_mono <= cast(float, tick)
                        and 0 <= cast(float, tick) - initial < 30
                    )
                except BaseException:
                    report["category"] = "CLOCK"
                    raise
                last_wall, last_mono = now, tick

            fence()
            # Called before even private metadata. Must consume a genuine scope-
            # bound Primary admission, including global no-retry across restarts.
            report.update(phase="PRIMARY_ADMISSION", category="PRIMARY_ADMISSION")
            require(admission(self.spec["scopeSha2_256"], starts_at, ends_at) is True)
            fence()

            def privacy(path, *, directory=False):
                require(
                    (str(path), directory)
                    in {
                        (str(Path(self.spec["index"]).parent), True),
                        (str(Path(self.spec["restoration"]).parent), True),
                        (str(Path(self.spec["index"])), False),
                        (str(Path(self.spec["restoration"])), False),
                    }
                )
                fence()
                report["privacyCallsAttempted"] += 1
                try:
                    self.backend.privacy(path, directory=directory)
                except BaseException:
                    report.update(
                        category="PRIVACY",
                        failedCallbackKind="PRIVACY",
                        failedCallbackEffects="UNKNOWN",
                    )
                    raise
                report["privacyCallsCompleted"] += 1
                fence()

            def snapshot(path):
                fence()
                report["outerSnapshotsAttempted"] += 1
                try:
                    result = self.backend.snapshot(path)
                except BaseException:
                    report.update(
                        category="METADATA",
                        failedCallbackKind="OUTER_SNAPSHOT",
                        failedCallbackEffects="UNKNOWN",
                    )
                    raise
                report["outerSnapshotsCompleted"] += 1
                fence()
                return result

            def read(path, maximum, role):
                report.update(phase=role + "_METADATA_BEFORE", category="METADATA")
                before = snapshot(path)
                report.update(phase=role + "_PRIVACY_PREFLIGHT", category="PRIVACY")
                privacy(path.parent, directory=True)
                privacy(path)
                fence()
                report.update(phase=role + "_CONTENT_READ", category="CONTENT_READ")
                report["contentCallsAttempted"] += 1
                report["failedReadMaximumBytes"] = maximum
                report["failureEffects"] = "READ_MAY_HAVE_OCCURRED"
                try:
                    raw = self.backend.stable_bytes(path, maximum, privacy)
                except BaseException:
                    if report["failedCallbackKind"] == "NONE":
                        report.update(
                            failedCallbackKind="CONTENT_READ", failedCallbackEffects="UNKNOWN"
                        )
                    raise
                report["contentCallsCompleted"] += 1
                report.update(phase=role + "_CONTENT_SIZE", category="CONTENT_SIZE")
                require(type(raw) is bytes and 0 < len(raw) <= maximum)
                report["validatedBytesReturned"] += len(raw)
                report["failedReadMaximumBytes"] = 0
                report["failureEffects"] = "NONE"
                fence()
                report.update(phase=role + "_METADATA_AFTER", category="METADATA")
                require(snapshot(path) == before)
                return raw

            index = read(Path(self.spec["index"]), 65536, "INDEX")
            report.update(phase="INDEX_DIGEST", category="INDEX_DIGEST")
            require(digest(index) == self.spec["indexSha2_256"])
            report.update(phase="INDEX_ROWS", category="INDEX_ROWS")
            count, pin = selected_row(index)
            restoration = read(Path(self.spec["restoration"]), 262144, "RESTORATION")
            report.update(phase="RESTORATION_DIGEST", category="RESTORATION_DIGEST")
            require(len(restoration) == count and digest(restoration) == pin)
            report.update(phase="RESTORATION_SHAPE", category="RESTORATION_SHAPE")
            projection = historical_projection(restoration)
            fence()
            report.update(phase="COMPLETE", category="NONE")
            report["status"] = "HISTORICAL_RECORDS_HELD_NO_FACT_VERDICT"
            return Outcome(report, HeldObservation(index, restoration, projection))
        except BaseException:
            report["status"] = "STOP_NO_RETRY"
            return Outcome(report, None)


def main():
    # No execute flag, argument parsing, filesystem or adapter construction.
    print('{"status":"DISABLED","currentFactQualification":"NO_GO"}')


if __name__ == "__main__":
    main()
