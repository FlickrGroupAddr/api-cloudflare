"""Native proof cleanup must never widen its recorded disposable scope."""

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import native_secret_probe as probe


class NativeProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(probe, "RUNS", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        run_id = "rp-" + "a" * 24
        directory = self.root / run_id
        directory.mkdir()
        self.probe_run = probe.Run(
            directory,
            {
                "runId": run_id,
                "environment": "cloudflare",
                "workerName": "fga-" + run_id,
                "databaseName": "fga-" + run_id + "-db",
                "secretName": "fga-native-" + "a" * 24,
                "accountId": "a" * 32,
                "storeId": "b" * 32,
                "secretId": "c" * 32,
                "generations": [str(uuid.uuid4()) for _ in range(3)],
            },
        )

    def api(self, rows):
        api = Mock()
        api.call.return_value = (
            200,
            {"success": True, "result": {"name": self.probe_run.state["workerName"]}},
        )
        api.rows.return_value = rows
        return api

    def test_wrong_run_or_provider_identity_is_refused(self):
        for key, value in (
            ("accountId", "bad"),
            ("workerName", "production"),
            ("secretName", "real-secret"),
        ):
            with self.subTest(key=key):
                state = {**self.probe_run.state, key: value}
                with self.assertRaises(probe.ProbeError):
                    probe.validate(probe.Run(self.probe_run.directory, state))

    def test_api_does_not_accept_an_external_endpoint(self):
        api = object.__new__(probe.NativeAPI)
        api.run, api.token = self.probe_run, "synthetic-token"
        with patch.object(probe.urllib.request, "build_opener") as opener:
            with self.assertRaises(probe.ProbeError):
                api.call("GET", "https://attacker.example/")
            opener.assert_not_called()

    def test_empty_preflight_has_no_provider_cleanup(self):
        with patch.object(probe, "NativeAPI") as api:
            probe.cleanup(self.probe_run)
            api.assert_not_called()
        self.assertTrue(self.probe_run.state["cleanupConfirmed"])

    def test_shared_store_is_never_deleted(self):
        self.probe_run.state.update(secretAttempted=True, storeOwned=False)
        api = self.api([])
        with patch.object(probe, "NativeAPI", return_value=api):
            probe.cleanup(self.probe_run)
        self.assertTrue(self.probe_run.state["cleanupConfirmed"])
        self.assertFalse(any(call.args[0] == "DELETE" for call in api.call.call_args_list))

    def test_nonempty_owned_store_is_not_deleted(self):
        self.probe_run.state.update(storeAttempted=True, storeOwned=True)
        api = self.api([{"name": "unrelated", "id": "d" * 32}])
        with patch.object(probe, "NativeAPI", return_value=api):
            with self.assertRaises(probe.ProbeError):
                probe.cleanup(self.probe_run)
        self.assertFalse(self.probe_run.state["cleanupConfirmed"])
        self.assertFalse(any(call.args[0] == "DELETE" for call in api.call.call_args_list))

    def test_changed_same_name_secret_is_not_deleted(self):
        self.probe_run.state.update(secretAttempted=True, storeOwned=False)
        api = self.api([{"name": self.probe_run.state["secretName"], "id": "d" * 32}])
        with patch.object(probe, "NativeAPI", return_value=api):
            with self.assertRaises(probe.ProbeError):
                probe.cleanup(self.probe_run)
        self.assertFalse(any(call.args[0] == "DELETE" for call in api.call.call_args_list))

    def test_worker_failure_prevents_bound_secret_deletion(self):
        self.probe_run.state.update(workerAttempted=True, secretAttempted=True)
        api = self.api(
            [{"name": self.probe_run.state["secretName"], "id": self.probe_run.state["secretId"]}]
        )
        with (
            patch.object(probe, "NativeAPI", return_value=api),
            patch.object(probe.runtime, "cleanup", side_effect=probe.ProbeError("failure")),
        ):
            with self.assertRaises(probe.ProbeError):
                probe.cleanup(self.probe_run)
        self.assertFalse(any(call.args[0] == "DELETE" for call in api.call.call_args_list))

    def test_denied_metadata_does_not_prove_cleanup(self):
        self.probe_run.state.update(secretAttempted=True)
        api = self.api([])
        api.call.return_value = (403, {"success": False})
        with patch.object(probe, "NativeAPI", return_value=api):
            with self.assertRaises(probe.ProbeError):
                probe.cleanup(self.probe_run)
        self.assertFalse(self.probe_run.state["cleanupConfirmed"])

    def test_only_one_controller_can_hold_a_run(self):
        with probe.run_lock(self.probe_run):
            with self.assertRaises(probe.ProbeError):
                with probe.run_lock(self.probe_run):
                    self.fail("overlapping run lock acquired")
        with probe.run_lock(self.probe_run):
            pass

    def test_deployment_secret_input_is_removed_after_failure(self):
        observed = []

        def deploy(*args):
            path = Path(args[-1])
            observed.append(path)
            self.assertIn("synthetic-proof-bearer", path.read_text())
            raise probe.ProbeError("deployment failed")

        with patch.object(probe.runtime, "wrangler", side_effect=deploy):
            with self.assertRaises(probe.ProbeError):
                probe.deploy_with_bearer(
                    self.probe_run,
                    self.probe_run.directory / "wrangler.json",
                    "synthetic-proof-bearer",
                )
        self.assertFalse(observed[0].exists())

    def test_transition_reconciliation_requires_the_exact_revision_and_generation(self):
        state = {"revision": 2, "state": "linked", "generation": "b", "operation": None}
        self.assertTrue(probe.transition_committed("activate", state, 1, "b"))
        self.assertFalse(probe.transition_committed("activate", state, 0, "b"))
        self.assertFalse(probe.transition_committed("activate", state, 1, "a"))
