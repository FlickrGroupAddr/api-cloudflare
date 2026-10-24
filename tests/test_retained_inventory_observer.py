"""Invented in-memory records; never opens files or invokes native APIs."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts import retained_inventory_observer as subject


def encode(value):
    return json.dumps(value, separators=(",", ":")).encode()


def invented_records():
    restoration = encode(
        {
            "accountId": "a" * 32,
            "worker": "invented-sensitive-worker",
            "captured": {"invented": {"path": "/invented", "SHA2-256": "b" * 64}},
            "pinnedActiveVersionWeights": {"invented-version": 100},
            "exactVersionModules": {
                "invented-version": {
                    "main_module": "invented.js",
                    "modules": [
                        {
                            "name": "invented.js",
                            "bytes": 42,
                            "content_type": "application/javascript",
                            "SHA2-256": "c" * 64,
                        }
                    ],
                }
            },
            "deploymentStable": True,
            "artifactBoundToEveryActiveVersion": True,
            "restorationReady": False,
        }
    )
    rows = [
        {
            "name": "restoration-inputs.json",
            "bytes": len(restoration),
            "sha256": subject.digest(restoration),
        }
    ]
    rows.extend({"name": f"invented-{n}.json", "bytes": 1, "sha256": "d" * 64} for n in range(14))
    rows[-1]["bytes"] += 1083133 - sum(row["bytes"] for row in rows)
    return encode({"files": rows}), restoration


class MemoryAdapter:
    def __init__(self, spec, index, restoration):
        self.records = {Path(spec["index"]): index, Path(spec["restoration"]): restoration}
        self.calls = []
        self.drift = False
        self.snapshot_count = 0

    def snapshot(self, path):
        self.calls.append(("snapshot", path))
        self.snapshot_count += 1
        return (str(path), self.snapshot_count if self.drift else 0)

    def privacy(self, path, *, directory=False):
        self.calls.append(("privacy", path, directory))

    def stable_bytes(self, path, maximum, privacy):
        self.calls.append(("read", path, maximum))
        privacy(path.parent, directory=True)
        privacy(path)
        raw = self.records[path]
        privacy(path.parent, directory=True)
        privacy(path)
        return raw


class RetainedInventoryTests(unittest.TestCase):
    def setUp(self):
        self.index, self.restoration = invented_records()
        self.spec = {
            "index": "invented-capture/index.json",
            "restoration": "invented-capture/private/restoration-inputs.json",
            "indexSha2_256": subject.digest(self.index),
            "scopeSha2_256": "e" * 64,
        }
        self.adapter = MemoryAdapter(self.spec, self.index, self.restoration)
        self.observer = subject.Observer(self.spec, self.adapter)
        self.now = datetime(2026, 1, 1, tzinfo=UTC)
        self.options: dict[str, Any] = {
            "execute": True,
            "admission": lambda *_: True,
            "starts_at": self.now,
            "ends_at": self.now + timedelta(seconds=30),
            "wall_clock": lambda: self.now,
            "monotonic": lambda: 10.0,
        }

    def run_observer(self):
        return self.observer.run(**self.options)

    def reads(self):
        return [call for call in self.adapter.calls if call[0] == "read"]

    def test_default_and_denied_admission_never_reach_adapter(self):
        self.assertEqual(self.observer.run().report["status"], "DISABLED")
        self.assertEqual(self.adapter.calls, [])
        self.options["admission"] = lambda *_: False
        self.assertIsNone(self.run_observer().held)
        self.assertEqual(self.adapter.calls, [])

    def test_two_exact_reads_held_only_and_closed_report(self):
        outcome = self.run_observer()
        assert outcome.held is not None
        self.assertEqual(
            [(str(row[1]), row[2]) for row in self.reads()],
            [
                (str(Path(self.spec["index"])), 65536),
                (str(Path(self.spec["restoration"])), 262144),
            ],
        )
        self.assertEqual(outcome.held.index, self.index)
        self.assertEqual(outcome.held.restoration, self.restoration)
        self.assertEqual(
            outcome.report["validatedBytesReturned"], len(self.index) + len(self.restoration)
        )
        self.assertEqual(outcome.report["currentFactQualification"], "NO_GO")
        self.assertFalse(outcome.held.projection["currentProviderFactsEstablished"])
        self.assertFalse(outcome.held.projection["permissionOrQualificationEstablished"])
        self.assertEqual(
            set(outcome.report),
            {
                "status",
                "contentCallsAttempted",
                "contentCallsCompleted",
                "validatedBytesReturned",
                "privacyCallsAttempted",
                "privacyCallsCompleted",
                "outerSnapshotsAttempted",
                "outerSnapshotsCompleted",
                "failedReadMaximumBytes",
                "failureEffects",
                "currentFactQualification",
                "privateWrites",
                "providerCalls",
                "credentialReads",
            },
        )
        self.assertNotIn("invented-sensitive-worker", json.dumps(outcome.report))
        self.assertNotIn("invented-sensitive-worker", repr(outcome))

    def test_bad_pinned_index_prevents_second_read(self):
        self.observer = subject.Observer(dict(self.spec, indexSha2_256="0" * 64), self.adapter)
        self.assertIsNone(self.run_observer().held)
        self.assertEqual(len(self.reads()), 1)

    def test_duplicate_selected_row_never_opens_restoration(self):
        changed = self.index.replace(b"invented-0.json", b"restoration-inputs.json")
        self.adapter.records[Path(self.spec["index"])] = changed
        self.observer = subject.Observer(
            dict(self.spec, indexSha2_256=subject.digest(changed)), self.adapter
        )
        self.assertIsNone(self.run_observer().held)
        self.assertEqual(len(self.reads()), 1)

    def test_duplicate_json_keys_and_malformed_inventory_refused(self):
        for raw in (
            b'{"files":[],"files":[]}',
            b'{"files":null}',
            self.index.replace(b'"sha256":"', b'"sha256":"invalid', 1),
        ):
            with self.assertRaises((ValueError, TypeError)):
                subject.selected_row(raw)

    def test_second_digest_failure_and_metadata_drift_discard_held_bytes(self):
        self.adapter.records[Path(self.spec["restoration"])] = b'{"wrong":true}'
        self.assertIsNone(self.run_observer().held)
        self.assertEqual(len(self.reads()), 2)
        self.setUp()
        self.adapter.drift = True
        self.assertIsNone(self.run_observer().held)
        self.assertEqual(len(self.reads()), 1)

    def test_failed_read_extent_and_same_instance_no_retry(self):
        def failed(path, maximum, privacy):
            raise OSError("invented-sensitive-diagnostic")

        self.adapter.stable_bytes = failed
        outcome = self.run_observer()
        self.assertIsNone(outcome.held)
        self.assertEqual(outcome.report["contentCallsAttempted"], 1)
        self.assertEqual(outcome.report["contentCallsCompleted"], 0)
        self.assertEqual(outcome.report["failedReadMaximumBytes"], 65536)
        self.assertEqual(outcome.report["failureEffects"], "READ_MAY_HAVE_OCCURRED")
        self.assertNotIn("sensitive", json.dumps(outcome.report))
        self.assertEqual(self.run_observer().report["contentCallsAttempted"], 0)

    def test_content_limits_refuse_oversize_at_each_boundary(self):
        self.adapter.records[Path(self.spec["index"])] = b"x" * 65537
        outcome = self.run_observer()
        self.assertIsNone(outcome.held)
        self.assertEqual(len(self.reads()), 1)
        self.assertEqual(outcome.report["failedReadMaximumBytes"], 65536)
        self.setUp()
        self.adapter.records[Path(self.spec["restoration"])] = b"x" * 262145
        outcome = self.run_observer()
        self.assertIsNone(outcome.held)
        self.assertEqual(len(self.reads()), 2)
        self.assertEqual(outcome.report["failedReadMaximumBytes"], 262144)

    def test_privacy_failure_stops_before_content_and_sanitizes_diagnostic(self):
        def refused(path, *, directory=False):
            raise PermissionError("invented-sensitive-ACL")

        self.adapter.privacy = refused
        outcome = self.run_observer()
        self.assertIsNone(outcome.held)
        self.assertEqual(self.reads(), [])
        self.assertNotIn("sensitive", json.dumps(outcome.report))

    def test_external_admission_prevents_replay_after_new_instance(self):
        consumed = set()

        def admission(pin, start, end):
            key = (pin, start, end)
            if key in consumed:
                return False
            consumed.add(key)
            return True

        self.options["admission"] = admission
        self.assertIsNotNone(self.run_observer().held)
        count = len(self.adapter.calls)
        self.observer = subject.Observer(self.spec, self.adapter)
        self.assertIsNone(self.run_observer().held)
        self.assertEqual(len(self.adapter.calls), count)

    def test_nonfinite_or_regressing_monotonic_clock_stops_before_metadata(self):
        for values in ([float("nan")], [10.0, 9.0], [10.0, float("inf")]):
            ticks = iter(values)
            self.options["monotonic"] = lambda ticks=ticks: next(ticks)
            self.observer = subject.Observer(self.spec, self.adapter)
            self.assertIsNone(self.run_observer().held)
        self.assertEqual(self.adapter.calls, [])

    def test_cooperative_deadline_discards_late_helper_return(self):
        elapsed = [0]
        original = self.adapter.stable_bytes

        def late(path, maximum, privacy):
            result = original(path, maximum, privacy)
            elapsed[0] = 31
            return result

        self.adapter.stable_bytes = late
        self.options["wall_clock"] = lambda: self.now + timedelta(seconds=elapsed[0])
        outcome = self.run_observer()
        self.assertIsNone(outcome.held)
        self.assertEqual(outcome.report["contentCallsCompleted"], 1)
        self.assertEqual(len(self.reads()), 1)


if __name__ == "__main__":
    unittest.main()
