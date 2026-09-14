"""Promotion rejects partial probes, omitted cases, weak mutations and stale artifacts."""

import copy
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import d1_engine_provenance as provenance
from scripts import fail_polite_release as gate


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.ids, contract = gate.inventory(gate.DEFAULT_CONTRACT)
        self.expected = {
            "releaseCommit": "a" * 40,
            "workersCompatibilityDate": "2026-09-11",
            "tooling": {"wrangler": "test-pinned"},
            "testAdapterSha2_256": "e" * 64,
            "workerArtifactSha2_256": "b" * 64,
            "configurationSha2_256": "c" * 64,
            "migrationSha2_256": "d" * 64,
            "migrationHead": "migration.sql",
            "contractSha2_256": contract,
        }
        self.report = {
            "schemaVersion": 2,
            "deploymentProfile": provenance.PRIVATE_PROFILE,
            "runStartedAt": "2026-09-14T11:00:00Z",
            "runCompletedAt": "2026-09-14T11:01:00Z",
            "scope": "full-production",
            **self.expected,
            "clockProfile": gate.PROFILE,
            "databaseEngine": {
                "provider": "cloudflare-d1",
                "version": "3.50.0",
                "versionKind": "sqlite-library",
                "runtime": "cloudflare-d1",
                "providerGeneration": "production",
                "versionSource": "remote-sqlite-version-query",
                "versionDisclosure": "disclosed",
                "observation": {
                    "query": provenance.QUERY,
                    "checkedAt": "2026-09-14T11:00:30Z",
                    "httpStatus": 200,
                },
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

    def test_committed_contract_mirror_matches_canonical_inventory(self):
        mirrored = gate.inventory(gate.MIRRORED_CONTRACT)
        self.assertEqual(mirrored, (self.ids, self.expected["contractSha2_256"]))
        if gate.CANONICAL_CONTRACT.is_file():
            self.assertEqual(mirrored, gate.inventory(gate.CANONICAL_CONTRACT))

    def test_complete_shape_and_each_identity_field(self):
        self.assertEqual(self.check(self.report), [])
        for field in self.expected:
            report = copy.deepcopy(self.report)
            report[field] = "stale"
            self.assertIn("identity_mismatch:" + field, self.check(report))

    def test_historical_probe_and_missing_infrastructure_cannot_pass(self):
        for change in (
            {"scope": "bounded-native"},
            {"scope": "provenance-only"},
            {"adapters": {}},
            {"databaseEngine": {}},
            {"clockProfile": "monotonic-claim"},
            {"restorePreservesPostBackupProtection": False},
        ):
            self.assertTrue(self.check({**self.report, **change}))

    def test_provider_generation_and_tool_versions_are_not_engine_provenance(self):
        for patch in (
            {"version": "production"},
            {"version": "alpha"},
            {"version": "unavailable"},
            {"versionKind": "wrangler"},
            {"versionKind": "miniflare"},
            {"versionKind": None},
        ):
            report = copy.deepcopy(self.report)
            report["databaseEngine"].update(patch)
            self.assertIn("real_database_provenance_required", self.check(report))

    def undisclosed_report(self):
        report = copy.deepcopy(self.report)
        report["databaseEngine"].update(
            provenance.query_observation(
                400,
                {"success": False, "errors": [{"code": 7500, "message": provenance.DENIAL}]},
                "2026-09-14T11:00:30Z",
            )
        )
        return report

    def test_approved_undisclosed_engine_keeps_behavioral_gates(self):
        report = self.undisclosed_report()
        self.assertEqual(self.check(report), [])
        for patch in (
            {"cases": []},
            {"mutations": []},
            {"adapters": {}},
            {"restorePreservesPostBackupProtection": False},
            {"liveFlickrCalls": 1},
            {"rawCredentialsCaptured": True},
            {"schemaVersion": 1},
            {"deploymentProfile": "public"},
        ):
            self.assertTrue(self.check({**report, **patch}))

    def test_undisclosed_is_explicit_and_requires_exact_refusal(self):
        for key, value in (
            ("version", "production"),
            ("version", ""),
            ("versionDisclosure", "unknown"),
            ("runtime", "miniflare"),
            ("provider", "other"),
            ("versionSource", "local-query"),
            ("providerGeneration", None),
            ("rawResponse", "must not be accepted"),
        ):
            report = self.undisclosed_report()
            report["databaseEngine"][key] = value
            self.assertIn("real_database_provenance_required", self.check(report))
        report = self.undisclosed_report()
        del report["databaseEngine"]["version"]
        self.assertIn("real_database_provenance_required", self.check(report))
        for patch in (
            {"httpStatus": 403},
            {"httpStatus": 200},
            {"errorCode": 10000},
            {"message": "unauthorized"},
            {"rawResponse": "private data"},
            {"query": "local version"},
        ):
            report = self.undisclosed_report()
            report["databaseEngine"]["observation"].update(patch)
            self.assertIn("real_database_provenance_required", self.check(report))

    def test_both_engine_states_require_observation_during_run(self):
        for baseline in (self.report, self.undisclosed_report()):
            for instant in (
                None,
                "",
                "invalid",
                "2026-09-14T11:00:30",
                "2026-09-13T11:00:30Z",
                "2026-09-15T11:00:30Z",
            ):
                report = copy.deepcopy(baseline)
                report["databaseEngine"]["observation"]["checkedAt"] = instant
                self.assertIn("real_database_provenance_required", self.check(report))
            for field in ("runStartedAt", "runCompletedAt"):
                report = copy.deepcopy(baseline)
                del report[field]
                self.assertIn("real_database_provenance_required", self.check(report))

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


class ReleaseInputTests(unittest.TestCase):
    def test_real_git_detects_uncommitted_assets_harness_and_workflow(self):
        with tempfile.TemporaryDirectory(prefix="fga-release-input-") as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True
                )

            git("init")
            hooks = root / "empty-hooks"
            hooks.mkdir()
            files = [
                "src/worker.ts",
                "assets/app.mjs",
                "tests/case.mjs",
                "scripts/runner.py",
                ".github/workflows/release.yml",
            ]
            for name in files:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("baseline\n", encoding="utf-8")
            git("add", ".")
            git(
                "-c",
                "user.name=FGA Test",
                "-c",
                "user.email=test@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=" + str(hooks),
                "commit",
                "-m",
                "test baseline",
            )
            self.assertEqual(gate.release_input_changes(root), "")
            for name in files[1:]:
                (root / name).write_text("changed\n", encoding="utf-8")
                self.assertIn(name, gate.release_input_changes(root))
            extra = root / "tests/new-case.mjs"
            extra.write_text("new\n", encoding="utf-8")
            self.assertIn("tests/new-case.mjs", gate.release_input_changes(root))


if __name__ == "__main__":
    unittest.main()
