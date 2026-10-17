"""Exact private-plan boundary tests using synthetic files, never retained captures."""

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts import hosted_publisher_operator_plan as plan
from scripts import prepare_hosted_publisher_qualification as packet


def fixture():
    return {
        "schema_version": 1,
        "account_id": "a" * 32,
        "owner": "Synthetic Owner",
        "cleanup_owner": "Synthetic Cleanup",
        "revocation_owner": "Synthetic Revocation",
        "starts_at": "2026-10-17T12:00:00Z",
        "expires_at": "2026-10-17T12:30:00Z",
        "cleanup_deadline": "2026-10-17T13:00:00Z",
        "pins": dict(plan.CANDIDATE_PINS),
        "budgets": dict(plan.BUDGET_CEILINGS),
        "source_files": dict.fromkeys(plan.REQUIRED_OPERATOR_FILES, "a" * 64),
        "cases": [
            {
                "scenario": scenario,
                "worker_name": f"fga-publisher-case-{i}",
                "d1_name": f"fga-publisher-db-{i}",
                "endpoint": f"https://fga-publisher-case-{i}.synthetic.workers.dev",
                "run_id": str(i + 1) * 64,
                "starts_at": "2026-10-17T12:00:00Z",
                "expires_at": "2026-10-17T12:30:00Z",
            }
            for i, scenario in enumerate(plan.SCENARIOS)
        ],
    }


def loaded(value=None):
    return plan.load_plan(json.dumps(value or fixture()).encode())


def receipts(value):
    return [
        plan.CreationReceipt(
            c.scenario,
            c.worker_name,
            c.d1_name,
            f"0000000{i + 1}-1111-4111-8111-111111111111",
            "2026-10-17T12:01:00Z",
            True,
            value.digest,
        )
        for i, c in enumerate(value.cases)
    ]


class HostedPublisherOperatorPlanTests(unittest.TestCase):
    def test_plan_maps_are_immutable_and_detached_from_constructor_aliases(self):
        value = loaded()
        pins, sources = dict(value.pins), dict(value.source_files)
        copied = replace(value, pins=pins, source_files=sources)
        original_digest = copied.digest
        pins["worker"] = "0" * 64
        sources.clear()
        self.assertEqual(copied.digest, original_digest)
        for mapping in (copied.pins, copied.source_files):
            with self.assertRaises(TypeError):
                cast(Any, mapping)["synthetic"] = "changed"

    def test_input_root_and_ancestor_links_refused_before_reading(self):
        with tempfile.TemporaryDirectory(prefix="fga-linked-input-") as directory:
            root = Path(directory) / "synthetic-root"
            root.mkdir()
            for linked in (root, root.parent):
                with (
                    patch.object(
                        Path,
                        "is_symlink",
                        autospec=True,
                        side_effect=lambda path, linked=linked: path == linked,
                    ),
                    patch.object(Path, "is_junction", return_value=False),
                    patch.object(Path, "read_bytes") as read,
                ):
                    with self.subTest(linked=linked), self.assertRaises(ValueError):
                        plan.validate_current_inputs(loaded(), root)
                    read.assert_not_called()

    def test_source_closure_refuses_missing_operator_or_escaping_paths(self):
        for invalid in (
            "../outside.py",
            "scripts/../outside.py",
            "C:/outside.py",
            "scripts\\outside.py",
            "/scripts/outside.py",
            "private-secret.json",
        ):
            value = fixture()
            value["source_files"][invalid] = "a" * 64
            with self.subTest(path=invalid), self.assertRaises(ValueError):
                loaded(value)
        value = fixture()
        del value["source_files"][plan.REQUIRED_OPERATOR_FILES[0]]
        with self.assertRaises(ValueError):
            loaded(value)

    def test_fresh_private_tokens_are_distinct_absent_from_plan_and_locally_revocable(self):
        value = loaded()
        private = plan.PrivateInputs.fresh(value)
        tokens = [private.token(scenario) for scenario in plan.SCENARIOS]
        self.assertEqual(len(set(tokens)), 4)
        for token in tokens:
            self.assertRegex(token, r"^[0-9a-f]{64}$")
            self.assertNotIn(token, repr(private))
            self.assertNotIn(token, repr(value))
        private.revoke_local()
        for scenario in plan.SCENARIOS:
            with self.assertRaises(ValueError):
                private.token(scenario)

    def test_closed_schema_and_duplicate_json_fields(self):
        loaded()
        for raw in (
            b'{"schema_version":1,"schema_version":1}',
            json.dumps({**fixture(), "access_token": "synthetic"}).encode(),
            b" " * 262145,
        ):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                plan.load_plan(raw)

    def test_operator_grant_is_account_limited_current_and_has_exact_permissions(self):
        value = loaded()
        now = datetime(2026, 10, 17, 12, 1, tzinfo=UTC)
        grant = {
            "grant_id": "synthetic-grant",
            "account_id": value.account_id,
            "permissions": ["D1:Edit", "Workers Scripts:Edit"],
            "issued_at": "2026-10-17T12:00:00Z",
            "expires_at": "2026-10-17T13:00:00Z",
            "revocation_owner": value.revocation_owner,
            "resource_scope": "exact-account-only",
            "metadata_verified": True,
        }
        plan.validate_operator_grant(value, grant, now)
        for key, invalid in (
            ("account_id", "b" * 32),
            ("resource_scope", "all-accounts"),
            ("permissions", [*grant["permissions"], "Account:Edit"]),
            ("expires_at", "2026-10-17T13:00:01Z"),
            ("metadata_verified", False),
            ("revocation_owner", "Other Owner"),
        ):
            with self.subTest(field=key), self.assertRaises(ValueError):
                plan.validate_operator_grant(value, {**grant, key: invalid}, now)
        with self.assertRaises(ValueError):
            plan.validate_operator_grant(value, grant, datetime(2026, 10, 17, 13, tzinfo=UTC))

    def test_every_candidate_pin_and_scenario_order_is_independent_and_exact(self):
        for key in plan.CANDIDATE_PINS:
            value = fixture()
            value["pins"][key] = "0" * len(value["pins"][key])
            with self.subTest(pin=key), self.assertRaises(ValueError):
                loaded(value)
        value = fixture()
        value["cases"].reverse()
        with self.assertRaises(ValueError):
            loaded(value)

    def test_boolean_nonfinite_and_over_ceiling_budgets_refused(self):
        for key, maximum in plan.BUDGET_CEILINGS.items():
            for invalid in (True, 0, -1, maximum + 1, float("inf")):
                value = fixture()
                value["budgets"][key] = invalid
                with self.subTest(budget=key, invalid=invalid), self.assertRaises(ValueError):
                    loaded(value)

    def test_four_pairs_are_unique_and_origins_cannot_smuggle_paths_or_credentials(self):
        for key in ("worker_name", "d1_name", "endpoint", "run_id"):
            value = fixture()
            value["cases"][1][key] = value["cases"][0][key]
            with self.subTest(duplicate=key), self.assertRaises(ValueError):
                loaded(value)
        origin = fixture()["cases"][0]["endpoint"]
        for invalid in (
            origin + "/",
            origin + "?secret=synthetic",
            origin + "#fragment",
            origin.replace("https://", "https://user@"),
            origin.replace("https://", "http://"),
            origin + ":443",
        ):
            value = fixture()
            value["cases"][0]["endpoint"] = invalid
            with self.subTest(origin=invalid), self.assertRaises(ValueError):
                loaded(value)

    def test_utc_and_lifecycle_windows_are_finite(self):
        for key, invalid in (
            ("starts_at", "2026-10-17T12:00:00+00:00"),
            ("cleanup_deadline", "2026-10-17T16:00:01Z"),
            ("expires_at", "2026-10-17T12:00:00Z"),
        ):
            value = fixture()
            value[key] = invalid
            with self.subTest(field=key), self.assertRaises(ValueError):
                loaded(value)
        value = fixture()
        value["cases"][0]["expires_at"] = "2026-10-17T12:30:01Z"
        with self.assertRaises(ValueError):
            loaded(value)

    def test_consent_binds_exact_digest_owner_actions_and_current_window(self):
        value = loaded()
        consent = {
            "schema_version": 1,
            "granted": True,
            "plan_digest": value.digest,
            "owner": value.owner,
            "actions": list(plan.OWNER_ACTIONS),
            "decision_id": "synthetic-decision",
        }
        now = datetime(2026, 10, 17, 12, 1, tzinfo=UTC)
        plan.validate_consent(value, consent, now)
        for key, invalid in (
            ("granted", 1),
            ("plan_digest", "0" * 64),
            ("owner", "Other Owner"),
            ("actions", list(plan.OWNER_ACTIONS[:-1])),
        ):
            with self.subTest(field=key), self.assertRaises(ValueError):
                plan.validate_consent(value, {**consent, key: invalid}, now)
        with self.assertRaises(ValueError):
            plan.validate_consent(value, consent, datetime(2026, 10, 17, 13, tzinfo=UTC))

    def test_creation_receipts_are_not_self_asserted_resource_labels(self):
        value = loaded()
        original = receipts(value)
        bound = plan.bind_resources(value, original)
        self.assertEqual(len(bound), 4)
        for changes in (
            {"empty_verified": False},
            {"plan_digest": "0" * 64},
            {"d1_uuid": original[1].d1_uuid},
            {"d1_name": "production"},
            {"created_at": "2026-10-17T11:59:59Z"},
        ):
            changed = original.copy()
            changed[0] = replace(changed[0], **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                plan.bind_resources(value, changed)

    def test_actual_overlay_binding_and_all_configuration_fields_must_match(self):
        value = loaded()
        receipt = receipts(value)[0]
        projection = plan.deployment_projection(value, value.cases[0], receipt.d1_uuid)
        database = next(b for b in projection["bindings"] if b["name"] == "DB")
        self.assertEqual(database, {"name": "DB", "type": "d1", "id": receipt.d1_uuid})
        reordered = copy.deepcopy(projection)
        reordered["bindings"].reverse()
        plan.validate_deployed_projection(projection, reordered)
        changed_values = []
        for binding in projection["bindings"]:
            altered = copy.deepcopy(projection)
            target = next(b for b in altered["bindings"] if b["name"] == binding["name"])
            target["id" if binding["name"] == "DB" else "text"] = "synthetic-drift"
            changed_values.append(altered)
        changed_values += [
            {**projection, "main_module": "other.js"},
            {**projection, "observability": {"enabled": True}},
            {**projection, "self_asserted_overlay": receipt.d1_uuid},
        ]
        for changed in changed_values:
            with self.assertRaises(ValueError):
                plan.validate_deployed_projection(projection, changed)

    def test_current_source_and_migration_bytes_are_rehashed(self):
        with tempfile.TemporaryDirectory(prefix="fga-plan-synthetic-") as directory:
            root = Path(directory)
            raw = fixture()
            names = [*plan.REQUIRED_OPERATOR_FILES, "migrations/0026_album_local_removal.sql"]
            raw["source_files"] = {}
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic reviewed bytes")
                raw["source_files"][name] = plan.sha2_256(path.read_bytes())
            value = loaded(raw)
            synthetic_config_pins = {
                name: raw["source_files"][name] for name in plan.CURRENT_CONFIG_PINS
            }
            with patch.object(plan, "CURRENT_CONFIG_PINS", synthetic_config_pins):
                plan.validate_current_inputs(value, root)
                for name in names:
                    path = root / name
                    original = path.read_bytes()
                    path.write_bytes(original + b"changed")
                    with self.subTest(file=name), self.assertRaises(ValueError):
                        plan.validate_current_inputs(value, root)
                    path.write_bytes(original)
                # Updating a reviewed source hash cannot waive immutable configuration pins.
                for name in synthetic_config_pins:
                    path = root / name
                    original = path.read_bytes()
                    path.write_bytes(original + b"changed")
                    changed = copy.deepcopy(raw)
                    changed["source_files"][name] = plan.sha2_256(path.read_bytes())
                    with self.subTest(config=name), self.assertRaises(ValueError):
                        plan.validate_current_inputs(loaded(changed), root)
                    path.write_bytes(original)

    def test_retained_artifact_validator_rehashes_all_migrations_and_optimized_module(self):
        with tempfile.TemporaryDirectory(prefix="fga-artifact-synthetic-") as directory:
            root = Path(directory)
            files = {}
            for name in packet.SOURCES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("synthetic:" + name).encode())
                files[name] = path.read_bytes()
            # Synthetic manifest has the same closed format, without using private captures.
            manifest = {
                "sourceHead": "1" * 40,
                "sourceCommitExact": True,
                "files": [
                    {"path": name, "bytes": len(data), "sha2_256": plan.sha2_256(data)}
                    for name, data in files.items()
                ],
            }
            manifest["artifactSha2_256"] = plan.sha2_256(packet.encoded(manifest))
            manifest_raw = packet.encoded(manifest)
            (root / "manifest.json").write_bytes(manifest_raw)
            bundle = root / "worker.js"
            bundle.write_bytes(b"s" * 652967)
            pins = {
                **plan.CANDIDATE_PINS,
                "source_commit": "1" * 40,
                "source_artifact": manifest["artifactSha2_256"],
                "manifest": plan.sha2_256(manifest_raw),
                "worker": plan.sha2_256(bundle.read_bytes()),
            }
            with patch.object(plan, "CANDIDATE_PINS", pins):
                plan.validate_artifact(root, bundle)
                migration = root / "migrations/0026_album_local_removal.sql"
                original = migration.read_bytes()
                migration.write_bytes(original + b"drift")
                with self.assertRaises(ValueError):
                    plan.validate_artifact(root, bundle)
                migration.write_bytes(original)
                bundle.write_bytes(b"x" * 652967)
                with self.assertRaises(ValueError):
                    plan.validate_artifact(root, bundle)


if __name__ == "__main__":
    unittest.main()
