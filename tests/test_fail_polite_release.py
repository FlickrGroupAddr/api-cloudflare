"""Promotion rejects partial probes, omitted cases, weak mutations and stale artifacts."""

import copy
import unittest

from scripts import fail_polite_release as gate


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.ids, contract = gate.inventory(gate.DEFAULT_CONTRACT)
        self.expected = {
            "releaseCommit": "a" * 40,
            "workerArtifactSha2_256": "b" * 64,
            "configurationSha2_256": "c" * 64,
            "migrationSha2_256": "d" * 64,
            "migrationHead": "migration.sql",
            "contractSha2_256": contract,
        }
        self.report = {
            "schemaVersion": 1,
            "scope": "full-production",
            **self.expected,
            "clockProfile": gate.PROFILE,
            "databaseEngine": {
                "provider": "cloudflare-d1",
                "version": "test-version",
                "runtime": "test-runtime",
                "migrationHead": "migration.sql",
            },
            "adapters": dict.fromkeys(gate.REQUIRED_ADAPTERS, True),
            "cases": [
                {
                    "id": name,
                    "status": "passed",
                    "skipped": False,
                    "entryPaths": ["hint", "sweep"],
                    "seedReasons": ["code_6", "code_7", "unknown", "unresolved_dispatch"],
                }
                for name in self.ids
            ],
            "mutations": [
                {
                    "id": name,
                    "controlPassed": True,
                    "mutantFailed": True,
                    "failureKind": "behavioral",
                    "detectedBy": [self.ids[0]],
                }
                for name in gate.MUTATIONS
            ],
            "liveFlickrCalls": 0,
            "rawCredentialsCaptured": False,
            "restorePreservesPostBackupProtection": True,
        }

    def check(self, report):
        return gate.validate(report, self.expected, self.ids)

    def test_complete_shape_and_each_identity_field(self):
        self.assertEqual(self.check(self.report), [])
        for field in self.expected:
            report = copy.deepcopy(self.report)
            report[field] = "stale"
            self.assertIn("identity_mismatch:" + field, self.check(report))

    def test_historical_probe_and_missing_infrastructure_cannot_pass(self):
        for change in (
            {"scope": "bounded-native"},
            {"adapters": {}},
            {"databaseEngine": {}},
            {"clockProfile": "monotonic-claim"},
            {"restorePreservesPostBackupProtection": False},
        ):
            self.assertTrue(self.check({**self.report, **change}))

    def test_missing_duplicate_skipped_extra_and_failed_cases(self):
        for cases in (
            self.report["cases"][:-1],
            self.report["cases"] * 2,
            [*self.report["cases"], {"id": "FP-UNKNOWN-001"}],
        ):
            self.assertTrue(self.check({**self.report, "cases": cases}))
        for change in ({"status": "failed"}, {"status": "skipped"}, {"skipped": True}):
            report = copy.deepcopy(self.report)
            report["cases"][0].update(change)
            self.assertTrue(self.check(report))

    def test_every_mutation_and_both_crash_entry_paths_are_required(self):
        for name in gate.MUTATIONS:
            report = copy.deepcopy(self.report)
            report["mutations"] = [row for row in report["mutations"] if row["id"] != name]
            self.assertTrue(self.check(report))
        for prefix, field in (("FP-CRASH-", "entryPaths"), ("FP-BLOCK-", "seedReasons")):
            report = copy.deepcopy(self.report)
            row = next(row for row in report["cases"] if row["id"].startswith(prefix))
            row[field] = row[field][:-1]
            self.assertTrue(self.check(report))

    def test_snapshot_or_compiler_failures_are_not_mutation_evidence(self):
        for change in (
            {"failureKind": "snapshot"},
            {"failureKind": "compiler"},
            {"controlPassed": False},
            {"detectedBy": []},
            {"mutantFailed": False},
        ):
            report = copy.deepcopy(self.report)
            report["mutations"][0].update(change)
            self.assertTrue(self.check(report))


if __name__ == "__main__":
    unittest.main()
