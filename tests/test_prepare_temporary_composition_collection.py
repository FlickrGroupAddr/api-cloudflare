"""Adversarial offline collection checks using only original synthetic metadata."""

from __future__ import annotations

import copy
import hashlib
import io
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import prepare_temporary_composition_collection as collection
from scripts.build_temporary_composition import CANDIDATE
from scripts.fixed_origin_restore import FIXTURE_MANIFEST_SHA256, MODULE_SHA256
from scripts.temporary_composition_delta import CONFIG_KEYS
from tests.test_temporary_composition_delta import composition_inputs

NOW = datetime(2026, 10, 18, 14, 30, tzinfo=UTC)


def request_inputs():
    baseline, additions = composition_inputs()
    baseline["moduleSha256"] = MODULE_SHA256
    additions.pop("moduleSha256")
    additions["receiver"].pop("moduleSha256")
    scope = additions.pop("scope")
    values = {
        "target": copy.deepcopy(baseline["target"]),
        "baseline": baseline,
        "additions": additions,
        "scope": scope,
        "fixture": {
            "candidateCommit": CANDIDATE,
            "capturedModuleSha256": MODULE_SHA256,
            "manifestSha256": FIXTURE_MANIFEST_SHA256,
        },
    }
    request = {
        "schemaVersion": 1,
        "kind": "temporary_composition_collection_request",
        "authority": {
            "decisionRef": "synthetic-reviewed-scope",
            "approved": True,
            "startsAt": "2026-10-18T14:00:00Z",
            "expiresAt": "2026-10-18T15:00:00Z",
            "credentialDelivery": "synthetic-out-of-band-delivery",
            "credentialRevocation": "synthetic-revoke-at-deadline",
            "privacy": {
                "secretValues": False,
                "photoData": False,
                "responseBodiesInLogs": False,
                "publicAccountValues": False,
            },
            "grants": [],
        },
        "inputs": {},
    }
    for name, value in values.items():
        request["inputs"][name] = {
            "available": True,
            "value": value,
            "provenance": {
                "sourceRef": "synthetic-independent-" + name,
                "sourceType": "owner_export",
                "capturedAt": "2026-10-18T14:15:00Z",
                "target": copy.deepcopy(baseline["target"]),
                "contentSha256": hashlib.sha256(collection.canonical(value)).hexdigest(),
                "independentlySourced": True,
                "completeness": "complete",
                "components": {},
            },
        }
    refresh_baseline_components(request)
    refresh_grants(request)
    return request


def refresh_grants(request):
    request["authority"]["grants"] = [
        dict(row, effect="read", permissionRef="synthetic-effective-read-grant")
        for row in collection.required_reads(request)
    ]


def refresh_content_pin(request, name):
    row = request["inputs"][name]
    row["provenance"]["contentSha256"] = hashlib.sha256(
        collection.canonical(row["value"])
    ).hexdigest()


def refresh_baseline_components(request):
    envelope = request["inputs"]["baseline"]
    baseline = envelope["value"]
    components = {"configuration." + key: value for key, value in baseline["configuration"].items()}
    components.update(
        {key: baseline[key] for key in ("productionState", "deploymentWeights", "retainedVersion")}
    )
    envelope["provenance"]["components"] = {
        key: {
            **{k: v for k, v in envelope["provenance"].items() if k != "components"},
            "sourceRef": "synthetic-section-" + key,
            "contentSha256": hashlib.sha256(collection.canonical(value)).hexdigest(),
        }
        for key, value in components.items()
    }


class TemporaryCompositionCollectionTests(unittest.TestCase):
    def prepare(self, request, *, now=NOW, expected=None):
        expected = expected or hashlib.sha256(collection.canonical(request)).hexdigest()
        return collection.prepare(request, expected, now)

    def assert_refused(self, request):
        with self.assertRaises(ValueError):
            self.prepare(request)

    def test_complete_inputs_are_reviewable_but_never_materialized_or_authorized(self):
        request = request_inputs()
        original = copy.deepcopy(request)
        receipt = self.prepare(request)
        self.assertEqual(receipt, self.prepare(request))
        self.assertEqual(request, original)
        self.assertEqual(receipt["status"], "reviewable")
        self.assertEqual(receipt["requiredReadCount"], 18)
        self.assertEqual(receipt["blockers"], [])
        for key in (
            "providerExecuted",
            "nativeExecuted",
            "activationAuthorized",
            "materializationReady",
        ):
            self.assertIs(receipt[key], False)
        self.assertEqual(
            receipt["requestSha256"], hashlib.sha256(collection.canonical(request)).hexdigest()
        )
        self.assertEqual(set(receipt["inputAvailability"]), set(request["inputs"]))
        serialized = collection.canonical(receipt).decode()
        for value in (
            "synthetic-account",
            "ordinary-worker",
            "original-version",
            "ordinary-db",
            "opaque-generation-7",
            "synthetic-independent",
            "b" * 64,
            MODULE_SHA256,
        ):
            self.assertNotIn(value, serialized)
        for artifact in ("worker.mjs", "receiver.mjs", "configuration-delta", "moduleSha256"):
            self.assertNotIn(artifact, serialized)

    def test_missing_target_and_inputs_produce_blockers_without_invented_values(self):
        request = request_inputs()
        for name in request["inputs"]:
            request["inputs"][name] = {"available": False, "value": None, "provenance": None}
        request["authority"]["grants"] = []
        receipt = self.prepare(request)
        self.assertEqual(receipt["status"], "blocked")
        self.assertTrue(receipt["blockers"])
        self.assertTrue(all(value is False for value in receipt["inputAvailability"].values()))
        self.assertIs(receipt["materializationReady"], False)
        self.assertEqual(request["inputs"]["baseline"]["value"], None)

    def test_plan_rechecks_receipt_authority_and_deadline_before_exposing_exact_targets(self):
        request = request_inputs()
        receipt = self.prepare(request)
        plan = collection.collection_plan(request, receipt, NOW)
        self.assertEqual(plan["reads"], collection.required_reads(request))
        self.assertEqual(plan["maxLogicalReads"], 18)
        self.assertEqual(plan["onIncompleteOrUnknown"], "refuse_and_re_review")
        for key in (
            "providerExecuted",
            "nativeExecuted",
            "activationAuthorized",
            "materializationReady",
        ):
            self.assertIs(plan[key], False)
        forged = dict(receipt, activationAuthorized=True)
        with self.assertRaises(ValueError):
            collection.collection_plan(request, forged, NOW)
        with self.assertRaises(ValueError):
            collection.collection_plan(request, receipt, datetime(2026, 10, 18, 15, 0, tzinfo=UTC))
        request["authority"]["approved"] = False
        blocked = self.prepare(request)
        blocked["status"] = "reviewable"
        blocked["blockers"] = []
        with self.assertRaises(ValueError):
            collection.collection_plan(request, blocked, NOW)

    def test_unavailable_envelope_must_not_hide_a_value_or_provenance(self):
        for field in ("value", "provenance"):
            request = request_inputs()
            request["inputs"]["baseline"]["available"] = False
            request["inputs"]["baseline"]["value"] = None
            request["inputs"]["baseline"]["provenance"] = None
            request["inputs"]["baseline"][field] = {"untrusted": "synthetic-secret-sentinel"}
            with self.subTest(field=field):
                self.assert_refused(request)

    def test_unapproved_or_outside_authority_is_blocked(self):
        request = request_inputs()
        request["authority"]["approved"] = False
        self.assertEqual(self.prepare(request)["status"], "blocked")
        for now in (
            datetime(2026, 10, 18, 13, 59, tzinfo=UTC),
            datetime(2026, 10, 18, 15, 0, tzinfo=UTC),
        ):
            request = request_inputs()
            request["inputs"] = {
                name: {"available": False, "value": None, "provenance": None}
                for name in request["inputs"]
            }
            request["authority"]["grants"] = []
            with self.subTest(now=now):
                self.assertEqual(self.prepare(request, now=now)["status"], "blocked")

    def test_oversized_or_reversed_authority_and_naive_clock_refused(self):
        for start, end in (
            ("2026-10-18T14:00:00Z", "2026-10-18T15:00:01Z"),
            ("2026-10-18T15:00:00Z", "2026-10-18T14:00:00Z"),
        ):
            request = request_inputs()
            request["authority"].update(startsAt=start, expiresAt=end)
            with self.subTest(start=start, end=end):
                self.assert_refused(request)
        with self.assertRaises(ValueError):
            self.prepare(request_inputs(), now=NOW.replace(tzinfo=None))

    def test_independent_request_digest_cannot_be_replaced_by_input_attestation(self):
        request = request_inputs()
        with self.assertRaises(ValueError):
            self.prepare(request, expected="0" * 64)
        request["expectedRequestSha256"] = "0" * 64
        self.assert_refused(request)

    def test_each_provenance_hash_target_source_and_timestamp_is_required(self):
        changes = (
            ("contentSha256", "0" * 64),
            ("target", {"accountId": "foreign", "scriptName": "ordinary-worker"}),
            ("sourceRef", ""),
            ("sourceType", "invented"),
            ("completeness", "partial"),
            ("independentlySourced", False),
            ("independentlySourced", 1),
            ("capturedAt", "2026-10-18T13:59:59Z"),
            ("capturedAt", "2026-10-18T14:31:00Z"),
        )
        for name in request_inputs()["inputs"]:
            for field, value in changes:
                request = request_inputs()
                request["inputs"][name]["provenance"][field] = value
                with self.subTest(input=name, field=field, value=value):
                    self.assert_refused(request)

    def test_each_full_baseline_section_is_required_even_with_rehashed_provenance(self):
        for section in CONFIG_KEYS:
            request = request_inputs()
            del request["inputs"]["baseline"]["value"]["configuration"][section]
            refresh_content_pin(request, "baseline")
            with self.subTest(section=section):
                self.assert_refused(request)

    def test_each_baseline_component_needs_its_own_independent_provenance(self):
        baseline_provenance = request_inputs()["inputs"]["baseline"]["provenance"]
        self.assertEqual(len(baseline_provenance["components"]), 14)
        for name in baseline_provenance["components"]:
            for mutation in ("missing", "hash", "target", "incomplete", "future"):
                request = request_inputs()
                components = request["inputs"]["baseline"]["provenance"]["components"]
                if mutation == "missing":
                    components.pop(name)
                elif mutation == "hash":
                    components[name]["contentSha256"] = "0" * 64
                elif mutation == "target":
                    components[name]["target"] = {"accountId": "foreign", "scriptName": "other"}
                elif mutation == "incomplete":
                    components[name]["completeness"] = "partial"
                else:
                    components[name]["capturedAt"] = "2026-10-18T14:31:00Z"
                with self.subTest(component=name, mutation=mutation):
                    self.assert_refused(request)

    def test_exact_targets_ownership_receiver_and_scope_cannot_drift(self):
        for name, mutate in (
            ("baseline", lambda v: v["target"].update(scriptName="foreign-worker")),
            ("baseline", lambda v: v.update(moduleSha256="0" * 64)),
            ("additions", lambda v: v["resources"][0].update(run="f" * 32)),
            ("additions", lambda v: v["receiver"]["target"].update(accountId="foreign")),
            ("scope", lambda v: v.update(expiresAt=v["expiresAt"] + 1)),
            ("scope", lambda v: v["bindingKeys"].update(receiver="PRODUCTION_DB")),
            ("fixture", lambda v: v.update(manifestSha256="0" * 64)),
            ("fixture", lambda v: v.update(candidateCommit="f" * 40)),
        ):
            request = request_inputs()
            mutate(request["inputs"][name]["value"])
            refresh_content_pin(request, name)
            with self.subTest(input=name, mutation=mutate):
                self.assert_refused(request)

    def test_precomputed_modules_or_scope_inside_additions_cannot_claim_artifact_provenance(self):
        for mutate in (
            lambda a: a.update(moduleSha256="0" * 64),
            lambda a: a["receiver"].update(moduleSha256="0" * 64),
            lambda a: a.update(scope={"unreviewed": True}),
        ):
            request = request_inputs()
            mutate(request["inputs"]["additions"]["value"])
            refresh_content_pin(request, "additions")
            self.assert_refused(request)

    def test_missing_selected_target_never_reuses_another_input_target(self):
        request = request_inputs()
        request["inputs"]["target"] = {"available": False, "value": None, "provenance": None}
        request["authority"]["grants"] = []
        self.assert_refused(request)

    def test_grants_are_exact_reads_for_the_exact_target(self):
        request = request_inputs()
        ids = {row["readId"] for row in request["authority"]["grants"]}
        self.assertTrue({"baseline.configuration." + k for k in CONFIG_KEYS}.issubset(ids))
        self.assertIn("receiver.configuration", ids)
        for mutation in ("missing", "duplicate", "write", "foreign", "permission"):
            request = request_inputs()
            grants = request["authority"]["grants"]
            if mutation == "missing":
                grants.pop()
            elif mutation == "duplicate":
                grants.append(copy.deepcopy(grants[0]))
            elif mutation == "write":
                grants[0]["effect"] = "write"
            elif mutation == "foreign":
                grants[0]["target"]["accountId"] = "foreign"
            else:
                grants[0]["permissionRef"] = ""
            with self.subTest(mutation=mutation):
                self.assert_refused(request)

    def test_privacy_delivery_and_revocation_limits_are_mandatory(self):
        for field in request_inputs()["authority"]["privacy"]:
            for value in (True, 0, None):
                request = request_inputs()
                request["authority"]["privacy"][field] = value
                with self.subTest(field=field, value=value):
                    self.assert_refused(request)
        for field in ("credentialDelivery", "credentialRevocation", "decisionRef"):
            request = request_inputs()
            request["authority"][field] = ""
            with self.subTest(field=field):
                self.assert_refused(request)

    def test_schema_extras_and_boolean_integer_confusion_refused(self):
        for mutate in (
            lambda r: r.update(schemaVersion=True),
            lambda r: r.update(kind="deploy-ready"),
            lambda r: r.update(token="synthetic-token-sentinel"),
            lambda r: r["authority"].update(approved=1),
            lambda r: r["inputs"]["target"].update(available=1),
            lambda r: r["inputs"]["target"].update(extra="ignored"),
        ):
            request = request_inputs()
            mutate(request)
            self.assert_refused(request)

    def test_prepare_reads_no_credentials_files_environment_or_network_and_builds_nothing(self):
        request = request_inputs()
        expected = hashlib.sha256(collection.canonical(request)).hexdigest()
        forbidden = AssertionError("offline collection attempted external access")
        environment = MagicMock()
        for method in ("get", "__getitem__", "__iter__", "__contains__", "keys", "items"):
            getattr(environment, method).side_effect = forbidden
        with (
            patch.object(Path, "open", side_effect=forbidden),
            patch.object(Path, "read_bytes", side_effect=forbidden),
            patch.object(Path, "read_text", side_effect=forbidden),
            patch.object(Path, "write_bytes", side_effect=forbidden),
            patch.object(Path, "write_text", side_effect=forbidden),
            patch.object(Path, "mkdir", side_effect=forbidden),
            patch.object(os, "getenv", side_effect=forbidden),
            patch.object(os, "environ", environment),
            patch.object(socket, "socket", side_effect=forbidden),
            patch.object(socket, "create_connection", side_effect=forbidden),
            patch.object(subprocess, "run", side_effect=forbidden),
            patch.object(subprocess, "Popen", side_effect=forbidden),
        ):
            receipt = collection.prepare(request, expected, NOW)
        self.assertEqual(receipt["status"], "reviewable")
        self.assertIs(receipt["materializationReady"], False)

    def test_cli_malformed_input_never_logs_private_values_or_creates_receipts(self):
        with tempfile.TemporaryDirectory(prefix="fga-collection-cli-") as temporary:
            root = Path(temporary)
            source, receipt = root / "request.json", root / "receipt.json"
            for raw in (
                b'{"schemaVersion":1,"schemaVersion":1,"token":"synthetic-private-sentinel"}',
                b'{"token":"synthetic-private-sentinel"}',
            ):
                source.write_bytes(raw)
                output = io.StringIO()
                with (
                    patch.object(
                        sys,
                        "argv",
                        [
                            "collection",
                            "--request",
                            str(source),
                            "--receipt",
                            str(receipt),
                            "--expected-request-sha256",
                            "0" * 64,
                        ],
                    ),
                    redirect_stdout(output),
                    patch.object(socket, "socket", side_effect=AssertionError("network forbidden")),
                    patch.object(subprocess, "run", side_effect=AssertionError("spawn forbidden")),
                ):
                    self.assertEqual(collection.main(), 2)
                self.assertNotIn("synthetic-private-sentinel", output.getvalue())
                self.assertNotIn(str(source), output.getvalue())
                self.assertFalse(receipt.exists())

    def test_cli_existing_receipt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="fga-collection-cli-") as temporary:
            root = Path(temporary)
            source, receipt = root / "request.json", root / "receipt.json"
            request = request_inputs()
            source.write_bytes(collection.canonical(request))
            receipt.write_bytes(b"preserve-synthetic-existing-receipt")
            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "collection",
                        "--request",
                        str(source),
                        "--receipt",
                        str(receipt),
                        "--expected-request-sha256",
                        hashlib.sha256(collection.canonical(request)).hexdigest(),
                    ],
                ),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(collection.main(), 2)
            self.assertEqual(receipt.read_bytes(), b"preserve-synthetic-existing-receipt")


if __name__ == "__main__":
    unittest.main()
