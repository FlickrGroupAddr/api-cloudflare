"""Offline safety and disclosure checks for current-production metadata collection."""

import http.client
import io
import json
import tempfile
import unittest
from http.client import HTTPMessage
from pathlib import Path
from unittest.mock import patch

from scripts import existing_photo_inventory as inventory

ACCOUNT = "a" * 32
ZONE = "b" * 32
VERSION = "11111111-1111-4111-8111-111111111111"
PRIVATE = "PRIVATE_PROVIDER_CANARY"


class FakeReader:
    account = ACCOUNT

    def __init__(self, denied=False, drift=False):
        self.calls = []
        self.denied = denied
        self.drift = drift

    def get(self, path):
        self.calls.append(path)
        if self.denied:
            return 403, json.dumps({"success": False, "errors": [PRIVATE]}).encode()
        if path.endswith("content/v2"):
            return 200, PRIVATE.encode()
        if path.endswith("/deployments"):
            value = {"deployments": [{"versions": [{"version_id": VERSION, "percentage": 100}]}]}
            if self.drift and len(self.calls) > 1:
                value = {"deployments": []}
        elif path.startswith("/zones?"):
            value = [{"id": ZONE}]
        elif "/workers/domains?" in path:
            value = [{"hostname": inventory.HOST, "service": inventory.WORKER}]
        else:
            value = {"private": PRIVATE, "id": ZONE}
        return 200, json.dumps({"success": True, "result": value}).encode()


class InventoryTests(unittest.TestCase):
    def test_receipt_has_no_raw_identity_source_or_provider_messages(self):
        reader = FakeReader()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            receipt = inventory.collect(reader, output)
            raw = json.dumps(receipt)
            for forbidden in (ACCOUNT, ZONE, VERSION, PRIVATE):
                self.assertNotIn(forbidden, raw)
            self.assertTrue(receipt["deploymentStableAcrossCapture"])
            self.assertTrue(receipt["customDomainAttachmentObserved"])
            self.assertFalse(receipt["restorationReady"])
            self.assertFalse(receipt["inventoryComplete"])
            self.assertTrue((output / "private/unversioned_artifact.bin").exists())
            self.assertTrue(any("/versions/" in path for path in reader.calls))
            with self.assertRaises(FileExistsError):
                inventory.collect(reader, output)

    def test_denial_does_not_mean_absence_or_publish_provider_error(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt = inventory.collect(FakeReader(denied=True), Path(temp) / "run")
        self.assertFalse(receipt["deploymentStableAcrossCapture"])
        self.assertTrue(
            all(row["state"] == "unavailable" for row in receipt["observations"].values())
        )
        self.assertNotIn(PRIVATE, json.dumps(receipt))

    def test_concurrent_deployment_is_unstable(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt = inventory.collect(FakeReader(drift=True), Path(temp) / "run")
        self.assertFalse(receipt["deploymentStableAcrossCapture"])

    def test_http_exception_is_sanitized(self):
        reader = FakeReader()
        with patch.object(reader, "get", side_effect=http.client.BadStatusLine(PRIVATE)):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(reader, Path(temp) / "run")
        self.assertNotIn(PRIVATE, json.dumps(receipt))
        self.assertTrue(
            all(row["state"] == "unavailable" for row in receipt["observations"].values())
        )

    def test_missing_or_malformed_pagination_is_incomplete(self):
        for info in (
            None,
            {},
            {"total_pages": "1"},
            {"page": 1, "per_page": 100, "total_pages": True},
        ):
            reader = FakeReader()
            original = reader.get

            def get(path, original=original, info=info):
                status, raw = original(path)
                if not path.endswith("content/v2"):
                    value = json.loads(raw)
                    value["result_info"] = info
                    raw = json.dumps(value).encode()
                return status, raw

            with patch.object(reader, "get", side_effect=get):
                with tempfile.TemporaryDirectory() as temp:
                    receipt = inventory.collect(reader, Path(temp) / "run")
            self.assertTrue(receipt["observations"]["custom_domains"]["paginationUnresolved"])

    def test_duplicate_weighted_versions_are_pinned_once(self):
        reader = FakeReader()
        original = reader.get

        def get(path):
            status, raw = original(path)
            if path.endswith("deployments"):
                raw = json.dumps(
                    {
                        "success": True,
                        "result": {
                            "deployments": [
                                {
                                    "versions": [
                                        {"version_id": VERSION, "percentage": 40},
                                        {"version_id": VERSION, "percentage": 60},
                                    ]
                                }
                            ]
                        },
                    }
                ).encode()
            return status, raw

        with patch.object(reader, "get", side_effect=get):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(reader, Path(temp) / "run")
                private = json.loads(
                    (Path(temp) / "run/private/restoration-inputs.json").read_text()
                )
        self.assertEqual(private["pinnedActiveVersionWeights"], {VERSION: 100})
        self.assertEqual(sum("/versions/" in path for path in reader.calls), 1)
        self.assertFalse(receipt["artifactBoundToEveryActiveVersion"])

    def test_request_and_version_caps(self):
        reader = FakeReader()
        original = reader.get

        def get(path):
            status, raw = original(path)
            if path.endswith("deployments"):
                raw = json.dumps(
                    {
                        "success": True,
                        "result": {
                            "deployments": [
                                {
                                    "versions": [{"version_id": VERSION, "percentage": 1}]
                                    * (inventory.MAX_VERSIONS + 1)
                                }
                            ]
                        },
                    }
                ).encode()
            return status, raw

        with patch.object(reader, "get", side_effect=get):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(reader, Path(temp) / "run")
        self.assertFalse(receipt["activeWeightedVersionsValid"])
        self.assertFalse(any("/versions/" in path for path in reader.calls))
        reader = FakeReader()
        with patch.object(inventory, "MAX_REQUESTS", 2):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(reader, Path(temp) / "run")
        self.assertEqual(len(reader.calls), 2)
        self.assertEqual(receipt["requestCount"], 2)

    def test_global_watchdog_sanitizes_timeout_output(self):
        with patch.object(inventory.sys, "argv", ["inventory", "--output-directory", "unused"]):
            with patch.object(
                inventory.subprocess,
                "run",
                side_effect=inventory.subprocess.TimeoutExpired("canary", 180, output=PRIVATE),
            ) as run:
                with patch("builtins.print") as output:
                    self.assertEqual(inventory.main(), 1)
        self.assertEqual(run.call_args.kwargs["timeout"], inventory.TOTAL_SECONDS)
        self.assertNotIn(PRIVATE, str(output.call_args_list))

    def test_allowlist_blocks_arbitrary_resource_before_network(self):
        reader = inventory.Reader(ACCOUNT, "private-token")
        with patch.object(inventory.urllib.request, "build_opener") as opener:
            for path in (
                "https://evil.invalid/",
                "/accounts/" + ACCOUNT + "/d1/database",
                "/accounts/" + ACCOUNT + "/workers/scripts/other/settings",
                "/zones/" + ZONE + "/rulesets/phases/unknown/entrypoint",
            ):
                with self.assertRaisesRegex(ValueError, "path_rejected"):
                    reader.get(path)
            opener.assert_not_called()

    def test_transport_is_get_only_and_does_not_follow_redirect(self):
        reader = inventory.Reader(ACCOUNT, "private-token")
        with patch.object(inventory.urllib.request, "build_opener") as factory:
            response = factory.return_value.open.return_value
            response.status = 200
            response.read.return_value = b"{}"
            reader.get(f"/accounts/{ACCOUNT}/workers/scripts/fga-api/settings")
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertIs(factory.call_args.args[0], inventory.NoRedirect)
            self.assertIsNone(
                inventory.NoRedirect().redirect_request(
                    request, io.BytesIO(), 302, "", HTTPMessage(), "https://evil.invalid/"
                )
            )


if __name__ == "__main__":
    unittest.main()
