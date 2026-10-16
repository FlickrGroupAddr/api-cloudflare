"""Offline safety and disclosure checks for current-production metadata collection."""

import base64
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
        if "/deployments?" in path:
            value = {"deployments": [{"versions": [{"version_id": VERSION, "percentage": 100}]}]}
            if self.drift and len(self.calls) > 1:
                value = {"deployments": []}
        elif path.startswith("/zones?"):
            value = [{"id": ZONE, "name": inventory.HOST, "account": {"id": ACCOUNT}}]
        elif "/workers/domains?" in path:
            value = [{"hostname": inventory.HOST, "service": inventory.WORKER, "enabled": True}]
        elif path.endswith("?include=modules"):
            value = {
                "id": VERSION,
                "main_module": "index.js",
                "modules": [
                    {
                        "name": "index.js",
                        "content_type": "application/javascript+module",
                        "content_base64": base64.b64encode(PRIVATE.encode()).decode(),
                    }
                ],
            }
        elif (
            "/rulesets?" in path
            or path.endswith(("/pagerules", "/workers/routes", "/settings"))
            and path.startswith("/zones/")
        ):
            value = []
        else:
            value = {"private": PRIVATE, "id": ZONE}
        return 200, json.dumps(
            {
                "success": True,
                "result": value,
                "result_info": {
                    "page": 1,
                    "per_page": 100,
                    "count": len(value) if isinstance(value, list) else 1,
                    "total_count": len(value) if isinstance(value, list) else 1,
                    "total_pages": 1,
                    "cursors": {},
                },
            }
        ).encode()


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
            self.assertTrue(receipt["metadataInputsComplete"])
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
            if "/deployments?" in path:
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
        self.assertEqual(sum("/versions/" in path for path in reader.calls), 2)
        self.assertTrue(receipt["artifactBoundToEveryActiveVersion"])

    def test_request_and_version_caps(self):
        reader = FakeReader()
        original = reader.get

        def get(path):
            status, raw = original(path)
            if "/deployments?" in path:
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

    def collect_override(self, override):
        reader = FakeReader()
        original = reader.get

        def get(path):
            status, raw = original(path)
            if not path.endswith("content/v2"):
                value = json.loads(raw)
                changed = override(path, value)
                if changed is not None:
                    status, value = changed
                raw = json.dumps(value).encode()
            return status, raw

        with patch.object(reader, "get", side_effect=get):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(reader, Path(temp) / "run")
        return receipt, reader

    def test_modules_fail_closed_for_identity_names_base64_and_main(self):
        for alteration in ("id", "name", "content", "duplicate", "main", "type"):

            def override(path, envelope, alteration=alteration):
                if not path.endswith("?include=modules"):
                    return None
                value = envelope["result"]
                if alteration == "id":
                    value["id"] = "22222222-2222-4222-8222-222222222222"
                elif alteration == "name":
                    value["modules"][0]["name"] = "../escape.js"
                elif alteration == "content":
                    value["modules"][0]["content_base64"] = "%%%"
                elif alteration == "duplicate":
                    value["modules"] *= 2
                elif alteration == "main":
                    value["main_module"] = "missing.js"
                else:
                    value["modules"][0]["content_type"] = None
                return None

            receipt, _ = self.collect_override(override)
            self.assertFalse(receipt["artifactBoundToEveryActiveVersion"], alteration)
            self.assertFalse(receipt["metadataInputsComplete"])
            self.assertNotIn(PRIVATE, json.dumps(receipt))

    def test_domains_counts_and_page_rules_without_pagination(self):
        def override(path, envelope):
            if "/workers/domains?" in path:
                envelope["result_info"] = {"count": 1, "total_count": 1}
            if path.endswith("/pagerules"):
                envelope.pop("result_info")
            return None

        receipt, reader = self.collect_override(override)
        self.assertTrue(receipt["metadataInputsComplete"])
        self.assertFalse(receipt["observations"]["custom_domains"]["paginationUnresolved"])
        self.assertTrue(any(path.endswith("/pagerules") for path in reader.calls))

    def test_disabled_domain_and_conflicting_counts_are_incomplete(self):
        for disabled in (True, False):

            def override(path, envelope, disabled=disabled):
                if "/workers/domains?" in path:
                    if disabled:
                        envelope["result"][0]["enabled"] = False
                    else:
                        envelope["result_info"]["total_count"] = 2
                return None

            receipt, _ = self.collect_override(override)
            self.assertFalse(receipt["metadataInputsComplete"])

    def test_ruleset_cursor_graph_account_managed_and_latest(self):
        root, managed = "c" * 32, "d" * 32

        def override(path, envelope):
            if path.startswith(f"/zones/{ZONE}/rulesets?"):
                envelope["result"] = [
                    {"id": root, "kind": "zone", "phase": "http_config_settings", "version": "3"}
                ]
                envelope["result_info"] = {"cursors": {}}
            elif path.startswith(f"/accounts/{ACCOUNT}/rulesets?"):
                if "cursor=" not in path:
                    envelope["result"] = [
                        {
                            "id": managed,
                            "kind": "managed",
                            "phase": "http_request_firewall_managed",
                            "version": "4",
                        }
                    ]
                    envelope["result_info"] = {"cursors": {"after": "next_cursor"}}
                else:
                    envelope["result"] = []
                    envelope["result_info"] = {"cursors": {}}
            elif f"/rulesets/{root}" in path:
                envelope["result"] = {
                    "id": root,
                    "version": "3",
                    "rules": [
                        {
                            "action": "execute",
                            "action_parameters": {"id": managed, "version": "latest"},
                        }
                    ],
                }
            elif f"/rulesets/{managed}" in path:
                envelope["result"] = {"id": managed, "version": "4", "rules": []}
            return None

        receipt, reader = self.collect_override(override)
        self.assertTrue(receipt["rulesetGraphComplete"])
        self.assertTrue(receipt["metadataInputsComplete"])
        self.assertIn(f"/accounts/{ACCOUNT}/rulesets/{managed}", reader.calls)
        self.assertNotIn(root, json.dumps(receipt))

    def test_ruleset_denial_or_null_cursor_envelope_never_means_none(self):
        for status in (400, 404, 200):

            def override(path, envelope, status=status):
                if "/rulesets?" in path:
                    envelope["result_info"] = None
                    if status != 200:
                        return status, {"success": False, "errors": [PRIVATE]}
                return None

            receipt, _ = self.collect_override(override)
            self.assertFalse(receipt["rulesetGraphComplete"])
            self.assertFalse(receipt["metadataInputsComplete"])
            self.assertNotIn(PRIVATE, json.dumps(receipt))

    def test_ruleset_repeated_cursor_is_bounded(self):
        def override(path, envelope):
            if "/rulesets?" in path:
                envelope["result_info"] = {"cursors": {"after": "repeat"}}
            return None

        receipt, reader = self.collect_override(override)
        self.assertFalse(receipt["rulesetGraphComplete"])
        self.assertLessEqual(sum("/rulesets?" in path for path in reader.calls), 4)

    def test_response_and_total_byte_limits_apply_to_fake_transport(self):
        with patch.object(inventory, "LIMIT", 8):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(FakeReader(), Path(temp) / "run")
        self.assertFalse(receipt["metadataInputsComplete"])
        self.assertNotIn(PRIVATE, json.dumps(receipt))
        with patch.object(inventory, "MAX_TOTAL_BYTES", 8):
            with tempfile.TemporaryDirectory() as temp:
                receipt = inventory.collect(FakeReader(), Path(temp) / "run")
        self.assertFalse(receipt["metadataInputsComplete"])

    def test_watchdog_passes_token_path_never_token_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            token_path = Path(temp) / "token.txt"
            token_path.write_text(PRIVATE)
            argv = ["inventory", "--output-directory", "unused", "--token-file", str(token_path)]
            with patch.object(inventory.sys, "argv", argv):
                with patch.object(inventory.subprocess, "run") as run:
                    run.return_value.returncode = 0
                    with patch("builtins.print"):
                        self.assertEqual(inventory.main(), 0)
            command = run.call_args.args[0]
            self.assertIn(str(token_path), command)
            self.assertNotIn(PRIVATE, str(command))

    def test_ruleset_page_and_node_budgets_fail_closed(self):
        def pages(path, envelope):
            if "/rulesets?" in path:
                envelope["result_info"] = {"cursors": {"after": str(len(path))}}
            return None

        with patch.object(inventory, "MAX_PAGES", 1):
            receipt, reader = self.collect_override(pages)
        self.assertFalse(receipt["rulesetGraphComplete"])
        self.assertEqual(sum("/rulesets?" in path for path in reader.calls), 2)

        def nodes(path, envelope):
            if "/rulesets?" in path:
                envelope["result"] = [
                    {
                        "id": "c" * 32,
                        "kind": "root",
                        "phase": "http_config_settings",
                        "version": "1",
                    }
                ]
            return None

        with patch.object(inventory, "MAX_RULESETS", 0):
            receipt, reader = self.collect_override(nodes)
        self.assertFalse(receipt["rulesetGraphComplete"])
        self.assertFalse(any("/rulesets/" in path for path in reader.calls))

    def test_bounded_child_reads_token_file_without_argv_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            token_path = Path(temp) / "token.txt"
            token_path.write_text(PRIVATE)
            argv = [
                "inventory",
                "--output-directory",
                "unused",
                "--bounded-child",
                "--token-file",
                str(token_path),
            ]
            with patch.object(inventory.sys, "argv", argv):
                with patch.object(inventory, "Reader") as reader:
                    with patch.object(inventory, "collect") as collect:
                        with patch("builtins.print"):
                            self.assertEqual(inventory.main(), 0)
            self.assertEqual(reader.call_args.args[1], PRIVATE)
            collect.assert_called_once()

    def test_exact_modules_allowlist_rejects_prefix_and_extra_query(self):
        reader = inventory.Reader(ACCOUNT, "private-token")
        prefix = f"/accounts/{ACCOUNT}/workers/workers/fga-api/versions/"
        with patch.object(inventory.urllib.request, "build_opener") as opener:
            for suffix in (
                "latest?include=modules",
                VERSION[:8] + "?include=modules",
                VERSION + "?include=modules&extra=true",
            ):
                with self.assertRaisesRegex(ValueError, "path_rejected"):
                    reader.get(prefix + suffix)
            opener.assert_not_called()

    def test_missing_null_or_wrong_required_result_shapes_fail_closed(self):
        for suffix in ("/settings", "/script-settings", "/workers/routes"):
            for result in (None, "invalid", 5):

                def override(path, envelope, suffix=suffix, result=result):
                    if path.endswith(suffix):
                        envelope["result"] = result
                    return None

                receipt, _ = self.collect_override(override)
                self.assertFalse(receipt["metadataInputsComplete"], (suffix, result))

            def missing(path, envelope, suffix=suffix):
                if path.endswith(suffix):
                    envelope.pop("result")
                return None

            receipt, _ = self.collect_override(missing)
            self.assertFalse(receipt["metadataInputsComplete"], suffix)

    def test_malformed_ruleset_cursor_envelopes_fail_closed(self):
        for cursors in (None, [], "bad", 3, {"after": False}, {"after": []}, {"after": None}):

            def override(path, envelope, cursors=cursors):
                if "/rulesets?" in path:
                    envelope["result_info"] = {"cursors": cursors}
                return None

            receipt, _ = self.collect_override(override)
            self.assertFalse(receipt["rulesetGraphComplete"], cursors)
            self.assertFalse(receipt["metadataInputsComplete"])

    def test_malformed_ruleset_list_entries_fail_closed(self):
        valid = {
            "id": "c" * 32,
            "kind": "managed",
            "phase": "http_request_firewall_managed",
            "version": "1",
        }
        for field in ("id", "kind", "phase", "version"):
            for missing in (True, False):
                entry: dict[str, object] = dict(valid)
                if missing:
                    entry.pop(field)
                else:
                    entry[field] = "unknown" if field == "kind" else None

                def override(path, envelope, entry=entry):
                    if "/rulesets?" in path:
                        envelope["result"] = [entry]
                    return None

                receipt, _ = self.collect_override(override)
                self.assertFalse(receipt["rulesetGraphComplete"], (field, missing))
                self.assertFalse(receipt["metadataInputsComplete"])

    def test_zone_lookup_must_match_fixed_hostname_and_account(self):
        for mismatch in ("name", "account"):

            def override(path, envelope, mismatch=mismatch):
                if path.startswith("/zones?"):
                    envelope["result"][0][mismatch] = "unrelated"
                return None

            receipt, reader = self.collect_override(override)
            self.assertFalse(receipt["metadataInputsComplete"])
            self.assertFalse(any(path.startswith(f"/zones/{ZONE}/") for path in reader.calls))

    def test_ruleset_cycle_is_explicit_incomplete(self):
        identity = "c" * 32

        def override(path, envelope):
            if path.startswith(f"/accounts/{ACCOUNT}/rulesets?"):
                envelope["result"] = [
                    {
                        "id": identity,
                        "kind": "root",
                        "phase": "http_config_settings",
                        "version": "1",
                    }
                ]
            elif f"/rulesets/{identity}" in path:
                envelope["result"] = {
                    "id": identity,
                    "version": "1",
                    "rules": [
                        {"action": "execute", "action_parameters": {"id": identity, "version": "1"}}
                    ],
                }
            return None

        receipt, _ = self.collect_override(override)
        self.assertFalse(receipt["rulesetGraphComplete"])
        self.assertEqual(receipt["observations"]["ruleset_cycle"]["reason"], "cyclic_input")

    def test_transport_reads_only_remaining_aggregate_byte_budget(self):
        reader = inventory.Reader(ACCOUNT, "private-token")
        reader.total_bytes = inventory.MAX_TOTAL_BYTES - 3
        with patch.object(inventory.urllib.request, "build_opener") as factory:
            response = factory.return_value.open.return_value
            response.status = 200
            response.read.return_value = b"1234"
            with self.assertRaisesRegex(ValueError, "response_limit"):
                reader.get(f"/accounts/{ACCOUNT}/workers/scripts/fga-api/settings")
            response.read.assert_called_once_with(4)
            with self.assertRaisesRegex(ValueError, "budget_exhausted"):
                reader.get(f"/accounts/{ACCOUNT}/workers/scripts/fga-api/settings")
            self.assertEqual(factory.return_value.open.call_count, 1)

    def test_ruleset_absent_optional_info_is_terminal_with_valid_entries(self):
        identity = "c" * 32
        for empty in (True, False):

            def override(path, envelope, empty=empty):
                if "/rulesets?" in path:
                    envelope.pop("result_info")
                    envelope["result"] = (
                        []
                        if empty
                        else [
                            {
                                "id": identity,
                                "kind": "root",
                                "phase": "http_config_settings",
                                "version": "1",
                            }
                        ]
                    )
                elif f"/rulesets/{identity}" in path:
                    envelope["result"] = {"id": identity, "version": "1", "rules": []}
                return None

            receipt, _ = self.collect_override(override)
            self.assertTrue(receipt["rulesetGraphComplete"])
            self.assertTrue(receipt["metadataInputsComplete"])

    def test_ruleset_empty_optional_info_is_terminal(self):
        for info in ({}, {"cursors": {}}):

            def override(path, envelope, info=info):
                if "/rulesets?" in path:
                    envelope["result_info"] = info
                return None

            receipt, _ = self.collect_override(override)
            self.assertTrue(receipt["rulesetGraphComplete"])

    def test_ruleset_singular_cursor_and_conflicting_forms(self):
        def singular(path, envelope):
            if "/rulesets?" in path:
                envelope["result_info"] = {"cursor": "next"} if "cursor=" not in path else {}
            return None

        receipt, reader = self.collect_override(singular)
        self.assertTrue(receipt["rulesetGraphComplete"])
        self.assertEqual(sum("cursor=next" in path for path in reader.calls), 2)
        for info in (
            {"cursor": "a", "cursors": {"after": "b"}},
            {"cursor": None},
            {"cursor": ""},
            {"cursor": 3},
            {"cursor": [], "cursors": {}},
        ):

            def malformed(path, envelope, info=info):
                if "/rulesets?" in path:
                    envelope["result_info"] = info
                return None

            receipt, _ = self.collect_override(malformed)
            self.assertFalse(receipt["rulesetGraphComplete"])
            self.assertFalse(receipt["metadataInputsComplete"])

    def test_documented_digit_bearing_managed_phase_is_valid_catalog_input(self):
        def override(path, envelope):
            if path.startswith(f"/zones/{ZONE}/rulesets?"):
                envelope["result"] = [
                    {
                        "id": "c" * 32,
                        "kind": "managed",
                        "phase": "http_request_sanitize",
                        "version": "1",
                    },
                    {
                        "id": "d" * 32,
                        "kind": "managed",
                        "phase": "http_request_firewall_managed",
                        "version": "2",
                    },
                    {"id": "e" * 32, "kind": "managed", "phase": "ddos_l7", "version": "3"},
                ]
                envelope.pop("result_info")
            return None

        receipt, _ = self.collect_override(override)
        self.assertTrue(receipt["rulesetGraphComplete"])
        self.assertTrue(receipt["metadataInputsComplete"])
        self.assertEqual(receipt["observations"]["zone_rulesets"]["configuredEntrypoints"], 0)

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
