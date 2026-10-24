"""Invented complete retained captures; no actual retained corpus is opened."""

import base64
import contextlib
import io
import json
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from scripts import existing_photo_inventory as inventory
from scripts import retained_capture_reconciliation as reconciliation

ACCOUNT = "a" * 32
ZONE = "b" * 32
ROOT = "c" * 32
CHILD = "d" * 32
VERSIONS = ["11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"]
CANARY = "PRIVATE_CANARY_DO_NOT_PUBLISH"
SOURCE = b"throw new Error('PRIVATE_CANARY_DO_NOT_PUBLISH'); fetch('https://invalid.invalid');"


def raw(value):
    return json.dumps(value).encode()


class Reader:
    account = ACCOUNT

    def __init__(self, mutate=None):
        self.mutate = mutate

    def get(self, path):
        if path.endswith("/content/v2"):
            return 200, SOURCE
        if "/deployments?" in path:
            value = {
                "deployments": [
                    {
                        "versions": [
                            {"version_id": identity, "percentage": 50} for identity in VERSIONS
                        ]
                    }
                ]
            }
        elif path.startswith("/zones?"):
            value = [{"id": ZONE, "name": inventory.HOST, "account": {"id": ACCOUNT}}]
        elif "/workers/domains?" in path:
            value = [{"hostname": inventory.HOST, "service": inventory.WORKER, "enabled": True}]
        elif path.endswith("?include=modules"):
            value = {
                "id": path.split("/")[-1].split("?")[0],
                "main_module": "worker.js",
                "modules": [
                    {
                        "name": name,
                        "content_type": "application/javascript+module",
                        "content_base64": base64.b64encode(SOURCE).decode(),
                    }
                    for name in ("worker.js", "lib/helper.js")
                ],
            }
        elif "/workers/scripts/" in path and "/versions/" in path:
            value = {
                "id": path.split("/")[-1],
                "resources": {"bindings": [{"type": "secret_text", "name": CANARY}]},
            }
        elif "/rulesets?" in path:
            value = (
                [{"id": ROOT, "kind": "zone", "phase": "http_request_transform", "version": "1"}]
                if path.startswith("/zones/")
                else []
            )
        elif "/rulesets/" in path:
            identity = ROOT if ROOT in path else CHILD
            value = {
                "id": identity,
                "version": "1",
                "rules": (
                    [{"action": "execute", "action_parameters": {"id": CHILD, "version": "1"}}]
                    if identity == ROOT
                    else [{"action": "skip", "expression": CANARY}]
                ),
            }
        elif path.startswith("/zones/"):
            value = []
        else:
            value = {"opaque": CANARY, "embedded_url": "file:///do-not-follow"}
        if self.mutate:
            self.mutate(path, value)
        envelope = {
            "success": True,
            "result": value,
            "result_info": {
                "page": 1,
                "per_page": 100,
                "count": len(value) if isinstance(value, list) else 1,
                "total_count": len(value) if isinstance(value, list) else 1,
                "total_pages": 1,
            },
        }
        return 200, raw(envelope)


def corpus(mutate=None):
    outputs = {}
    inventory.collect(
        Reader(mutate),
        cast(Path, reconciliation._MemoryPath(outputs)),
        monotonic=lambda: 0,
        captured_at="2026-01-01T00:00:00+00:00",
    )
    files = {
        name.removeprefix("/private/"): value
        for name, value in outputs.items()
        if name.startswith("/private/")
    }
    return files, outputs["/existing-photo-inventory-receipt.json"]


def invoke(files, receipt, *, index=None, pin=None, entries=None):
    if index is None:
        index = raw(
            {
                "files": [
                    {"name": name, "bytes": len(value), "sha256": inventory.digest(value)}
                    for name, value in files.items()
                ]
            }
        )
    return reconciliation.reconcile(
        index,
        receipt,
        tuple(files.items()) if entries is None else entries,
        expected_index_sha2_256=pin or inventory.digest(index),
    )


class ReconciliationTests(unittest.TestCase):
    def assert_unresolved(self, result):
        self.assertEqual(result, reconciliation._result(False))

    def test_complete_two_versions_two_modules_and_execute_graph(self):
        files, receipt = corpus()
        self.assertIn("ruleset_1.json", files)
        self.assertEqual(invoke(files, receipt), reconciliation._result(True))

    def test_no_resource_access_execution_clock_or_private_output(self):
        files, receipt = corpus()
        with (
            contextlib.redirect_stdout(io.StringIO()) as out,
            contextlib.redirect_stderr(io.StringIO()) as err,
            patch("pathlib.Path.open", side_effect=AssertionError("filesystem")),
            patch("urllib.request.build_opener", side_effect=AssertionError("network")),
            patch.object(inventory.time, "monotonic", side_effect=AssertionError("clock")),
        ):
            result = invoke(files, receipt)
        self.assertEqual(result, reconciliation._result(True))
        self.assertEqual(out.getvalue() + err.getvalue(), "")
        for secret in (CANARY, ACCOUNT, ZONE, *VERSIONS, SOURCE.decode()):
            self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["secretState"], "unknown")
        self.assertFalse(result["currentDeploymentQualified"])
        self.assertFalse(result["prospectiveAttributionQualified"])

    def test_integrity_pin_and_digest_mismatches(self):
        files, receipt = corpus()
        self.assert_unresolved(invoke(files, receipt, pin="0" * 64))
        index = raw(
            {
                "files": [
                    {"name": name, "bytes": len(value), "sha256": "0" * 64}
                    for name, value in files.items()
                ]
            }
        )
        self.assert_unresolved(invoke(files, receipt, index=index))

    def test_duplicate_omitted_extra_files_and_index_rows(self):
        files, receipt = corpus()
        entries = tuple(files.items())
        self.assert_unresolved(invoke(files, receipt, entries=entries + entries[:1]))
        for name in files:
            changed = dict(files)
            del changed[name]
            self.assert_unresolved(invoke(changed, receipt))
        self.assert_unresolved(invoke({**files, "../unexpected.json": b"{}"}, receipt))
        rows = [
            {"name": name, "bytes": len(value), "sha256": inventory.digest(value)}
            for name, value in files.items()
        ]
        rows[-1] = rows[0]
        self.assert_unresolved(invoke(files, receipt, index=raw({"files": rows})))

    def test_rehashed_payload_and_restoration_drift(self):
        files, receipt = corpus()
        for name in (
            "worker_settings.json",
            "ruleset_0.json",
            "active_version_0_modules.json",
            "restoration-inputs.json",
        ):
            changed = dict(files)
            payload = json.loads(changed[name])
            payload["private_drift"] = CANARY
            changed[name] = raw(payload)
            self.assert_unresolved(invoke(changed, receipt))

    def test_semantic_version_module_weight_and_graph_errors(self):
        def duplicate_versions(path, value):
            if "/deployments?" in path:
                value["deployments"][0]["versions"][1]["version_id"] = VERSIONS[0]

        def metadata_id(path, value):
            if "/scripts/" in path and "/versions/" in path:
                value["id"] = VERSIONS[1]

        def duplicate_module(path, value):
            if path.endswith("?include=modules"):
                value["modules"][1]["name"] = "WORKER.JS"

        def invalid_module(path, value):
            if path.endswith("?include=modules"):
                value["modules"][0]["content_base64"] = CANARY

        def invalid_weights(path, value):
            if "/deployments?" in path:
                value["deployments"][0]["versions"][0]["percentage"] = 49

        def graph_cycle(path, value):
            if "/rulesets/" in path and ROOT in path:
                value["rules"][0]["action_parameters"]["id"] = ROOT

        for mutation in (
            duplicate_versions,
            metadata_id,
            duplicate_module,
            invalid_module,
            invalid_weights,
            graph_cycle,
        ):
            with self.subTest(mutation=mutation.__name__):
                files, receipt = corpus(mutation)
                self.assert_unresolved(invoke(files, receipt))

    def test_duplicate_json_keys_malformed_and_bounded_inputs(self):
        files, receipt = corpus()
        self.assert_unresolved(invoke(files, receipt, index=b'{"files":[],"files":[]}'))
        for invalid in (b"[]", b"null", b"{", b'"' + CANARY.encode() + b'"', b"\xff"):
            self.assert_unresolved(invoke(files, invalid))
        changed = dict(files)
        changed["worker_settings.json"] = b'{"success":true,"result":{},"result":{}}'
        self.assert_unresolved(invoke(changed, receipt))
        changed["worker_settings.json"] = b'{"success":true,"result":{"value":1e999}}'
        self.assert_unresolved(invoke(changed, receipt))
        self.assert_unresolved(invoke(files, receipt, entries=tuple(files.items()) * 7))
        self.assert_unresolved(
            invoke(files, receipt, index=b" " * (reconciliation.INDEX_LIMIT + 1))
        )

    def test_receipt_claims_cannot_upgrade_and_must_match(self):
        files, receipt = corpus()
        for field in (
            "metadataInputsComplete",
            "privateCaptureDurablyRetained",
            "restorationReady",
            "edgeBehaviorQualified",
            "requestCount",
            "capturedAt",
        ):
            changed = json.loads(receipt)
            changed[field] = "PRIVATE_CANARY_DO_NOT_PUBLISH"
            self.assert_unresolved(invoke(files, raw(changed)))
        changed = json.loads(receipt)
        changed["inventoryComplete"] = 1
        self.assert_unresolved(invoke(files, raw(changed)))

    def test_selector_identity_and_before_after_drift(self):
        files, receipt = corpus()
        changed = dict(files)
        restoration = json.loads(changed["restoration-inputs.json"])
        restoration["captured"]["worker_settings"]["path"] = "https://invalid.invalid/secret"
        changed["restoration-inputs.json"] = raw(restoration)
        self.assert_unresolved(invoke(changed, receipt))
        changed = dict(files)
        payload = json.loads(changed["deployments_after.json"])
        payload["result"]["deployments"][0]["versions"][0]["percentage"] = 99
        changed["deployments_after.json"] = raw(payload)
        restoration = json.loads(changed["restoration-inputs.json"])
        restoration["captured"]["deployments_after"]["SHA2-256"] = inventory.digest(
            changed["deployments_after.json"]
        )
        changed["restoration-inputs.json"] = raw(restoration)
        self.assert_unresolved(invoke(changed, receipt))


if __name__ == "__main__":
    unittest.main()
