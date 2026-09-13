"""Deployment boundaries: closed flags, resource ownership, and non-mutating planning."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import bootstrap_deployment as b


class BootstrapBoundaryTests(unittest.TestCase):
    def test_every_feature_enable_is_rejected(self):
        for flag in b.FLAGS:
            with self.subTest(flag=flag):
                config = b.template()
                config["vars"][flag] = "1"
                with self.assertRaisesRegex(RuntimeError, "all_features_disabled"):
                    b.require_disabled(config)

    def test_public_alternate_host_is_rejected(self):
        for key, value in [
            ("workers_dev", True),
            ("routes", [{"pattern": "example.com", "custom_domain": True}]),
        ]:
            config = b.template()
            config[key] = value
            with self.assertRaises(RuntimeError):
                b.require_disabled(config)

    def make_bootstrap(self, inventory=None, state=None):
        instance = b.Bootstrap.__new__(b.Bootstrap)
        instance.inputs = {
            "flickrCredentialFile": "unused",
            "writerTokenFile": "unused",
            "zoneReadTokenFile": "unused",
        }
        instance.google = {
            "GOOGLE_OWNER_SUB": "123456789012",
            "GOOGLE_CLIENT_ID": "synthetic.apps.googleusercontent.com",
        }
        instance.zone = {"id": "0" * 32}
        instance.state = state or {}
        instance.rows = lambda suffix: (inventory or {}).get(suffix, [])
        return instance

    def run_plan(self, instance, dns=None):
        with (
            patch.object(b, "file_token", return_value="synthetic"),
            patch.object(b, "application_credentials", return_value={}),
            patch.object(
                b.readiness, "get", return_value=(200, {"success": True, "result": dns or []})
            ),
            patch.object(
                instance, "call", side_effect=AssertionError("Plan must not mutate cloud resources")
            ),
            patch.object(
                instance, "checkpoint", side_effect=AssertionError("Plan must not write a journal")
            ),
        ):
            return instance.plan()

    def test_empty_account_plan_is_non_mutating(self):
        self.assertTrue(self.run_plan(self.make_bootstrap())["ready"])

    def test_existing_unowned_worker_database_and_store_are_rejected(self):
        for inventory in [
            {"workers/scripts": [{"id": b.WORKER}]},
            {"d1/database": [{"name": b.DATABASE}]},
            {"secrets_store/stores": [{"name": "unrelated-store"}]},
        ]:
            with self.subTest(inventory=inventory), self.assertRaises(RuntimeError):
                self.run_plan(self.make_bootstrap(inventory))

    def test_preexisting_dns_cannot_be_overwritten_by_first_run(self):
        with self.assertRaisesRegex(RuntimeError, "existing_dns"):
            self.run_plan(self.make_bootstrap(), [{"type": "CNAME", "name": b.readiness.DOMAIN}])

    def test_owned_interrupted_bootstrap_can_be_planned_again(self):
        inventory = {
            "workers/scripts": [{"id": b.WORKER}],
            "d1/database": [{"name": b.DATABASE}],
            "secrets_store/stores": [{"name": b.STORE}],
        }
        state = {"workerAttempted": True, "databaseAttempted": True, "storeAttempted": True}
        self.assertTrue(
            self.run_plan(self.make_bootstrap(inventory, state), [{"type": "CNAME"}])["ready"]
        )


if __name__ == "__main__":
    unittest.main()
