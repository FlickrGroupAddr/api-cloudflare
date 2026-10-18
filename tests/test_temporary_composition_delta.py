"""Full-baseline delta regressions using original synthetic metadata only."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from scripts.temporary_composition_delta import build_delta, load_json, validate_delta

RUN = "a" * 32


def composition_inputs():
    """All sections supplied explicitly; no private/provider fixture is discovered."""
    baseline = {
        "schemaVersion": 1,
        "kind": "temporary_composition_baseline",
        "target": {"accountId": "synthetic-account", "scriptName": "ordinary-worker"},
        "retainedVersion": "original-version",
        "deploymentWeights": {"original-version": 100},
        "moduleSha256": "1" * 64,
        "configuration": {
            "bindings": [
                {"name": "PRODUCTION_DB", "type": "d1", "database_id": "ordinary-db"},
                {"name": "EXISTING_TEXT", "type": "plain_text", "text": "retain-exactly"},
                {
                    "name": "EXISTING_CLASS",
                    "type": "durable_object_namespace",
                    "class_name": "RetainedClass",
                    "namespace_id": "ordinary-namespace",
                },
            ],
            "resources": [{"kind": "d1", "identity": "ordinary-db", "readOnly": False}],
            "runtime": {"compatibility_date": "2026-10-15", "flags": ["nodejs_compat"]},
            "assets": {"directory": "ordinary-assets", "run_worker_first": ["/api/*"]},
            "classLifecycle": {"migrations": [{"tag": "v1", "new_classes": ["RetainedClass"]}]},
            "secretReferences": {"INSTALLATION_SECRET": {"reference": "opaque-generation-7"}},
            "attachment": {"logpush": False, "tail_consumers": [{"service": "ordinary-tail"}]},
            "routes": [{"pattern": "example.invalid/*", "zone_id": "ordinary-zone"}],
            "domains": [{"hostname": "api.example.invalid", "zone_id": "ordinary-zone"}],
            "effectiveEdge": {"rules": [{"action": "skip", "id": "ordinary-rule"}]},
            "capabilities": {"intake": False, "dispatch": False, "thumbnail": False},
        },
        "productionState": {
            "schema": "ordinary-v1",
            "rows": [["typed-value", 1, True, None]],
            "credentialGeneration": "opaque-generation-7",
        },
    }
    resources = [
        {"kind": "d1", "identity": "synthetic-application-db", "run": RUN},
        {"kind": "d1", "identity": "synthetic-quota-db", "run": RUN},
        {"kind": "worker", "identity": "synthetic-receiver", "run": RUN},
    ]
    additions = {
        "run": RUN,
        "temporaryVersion": "temporary-version",
        "moduleSha256": "2" * 64,
        "bindings": [
            {"name": "QUALIFICATION_DB", "type": "d1", "database_id": resources[0]["identity"]},
            {"name": "QUALIFICATION_QUOTA", "type": "d1", "database_id": resources[1]["identity"]},
            {
                "name": "QUALIFICATION_RECEIVER",
                "type": "service",
                "service": resources[2]["identity"],
            },
            {"name": "QUALIFICATION_CAPABILITY", "type": "plain_text", "text": "b" * 64},
        ],
        "resources": resources,
        "receiver": {
            "binding": "QUALIFICATION_RECEIVER",
            "identity": "synthetic-receiver",
            "run": RUN,
        },
    }
    receiver_config = {
        "bindings": [],
        "resources": [],
        "runtime": {"compatibility_date": "2026-10-15"},
        "assets": {},
        "classLifecycle": {},
        "secretReferences": {},
        "attachment": {},
        "routes": [],
        "domains": [],
        "effectiveEdge": {},
        "capabilities": {"intake": False, "dispatch": False, "thumbnail": False},
    }
    receiver_config["bindings"] = copy.deepcopy(
        [additions["bindings"][1], additions["bindings"][3]]
    )
    receiver_config["resources"] = copy.deepcopy([additions["resources"][1]])
    receiver_config["routes"] = []
    receiver_config["domains"] = []
    additions["receiver"].update(
        target={"accountId": baseline["target"]["accountId"], "scriptName": "synthetic-receiver"},
        configuration=receiver_config,
        moduleSha256="3" * 64,
    )
    additions["scope"] = {
        "run": RUN,
        "startsAt": 1000,
        "expiresAt": 601000,
        "canary": "c" * 64,
        "bindingKeys": {
            "syntheticDb": "QUALIFICATION_DB",
            "quotaDb": "QUALIFICATION_QUOTA",
            "receiver": "QUALIFICATION_RECEIVER",
            "capability": "QUALIFICATION_CAPABILITY",
        },
    }
    return baseline, additions


class TemporaryCompositionDeltaTests(unittest.TestCase):
    def test_only_explicit_isolated_additions_change_full_baseline(self):
        baseline, additions = composition_inputs()
        original_baseline, original_additions = copy.deepcopy((baseline, additions))
        delta = build_delta(baseline, additions)
        validate_delta(delta)
        self.assertEqual(baseline, original_baseline)
        self.assertEqual(additions, original_additions)
        temporary = delta["temporary"]
        self.assertEqual(temporary["target"], baseline["target"])
        self.assertEqual(temporary["productionState"], baseline["productionState"])
        config = temporary["configuration"]
        for key, value in baseline["configuration"].items():
            with self.subTest(section=key):
                self.assertEqual(
                    config[key][: len(value)] if key in ("bindings", "resources") else config[key],
                    value,
                )
        self.assertEqual(config["bindings"][3:], additions["bindings"])
        self.assertEqual(config["resources"][1:], additions["resources"])
        self.assertEqual(
            delta["restore"]["versions"], [{"version_id": "original-version", "percentage": 100}]
        )
        temporary["productionState"]["rows"][0][1] = "mutated"
        self.assertEqual(baseline, original_baseline)
        self.assertEqual(delta["baseline"], original_baseline)

    def test_missing_full_sections_or_target_never_get_invented(self):
        baseline, additions = composition_inputs()
        for key in baseline["configuration"]:
            changed = copy.deepcopy(baseline)
            del changed["configuration"][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                build_delta(changed, additions)
        for key in ("accountId", "scriptName"):
            changed = copy.deepcopy(baseline)
            del changed["target"][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                build_delta(changed, additions)

    def test_collisions_owner_mismatch_and_partial_resources_refuse(self):
        baseline, additions = composition_inputs()
        mutations = [
            lambda a: a["bindings"][0].update(name="PRODUCTION_DB"),
            lambda a: a["resources"][0].update(identity="ordinary-db"),
            lambda a: a["resources"][0].update(run="c" * 32),
            lambda a: a["receiver"].update(identity="ordinary-worker"),
            lambda a: a["bindings"][0].update(database_id="unknown-db"),
            lambda a: a["resources"].pop(),
            lambda a: a["bindings"].pop(),
        ]
        for number, mutate in enumerate(mutations):
            changed = copy.deepcopy(additions)
            mutate(changed)
            with self.subTest(case=number), self.assertRaises(ValueError):
                build_delta(baseline, changed)

    def test_receiver_requires_full_exact_target_config_module_and_owned_bindings(self):
        baseline, additions = composition_inputs()
        for mutate in (
            lambda a: a["receiver"].pop("moduleSha256"),
            lambda a: a["receiver"]["configuration"].pop("attachment"),
            lambda a: a["receiver"]["target"].update(accountId="foreign-account"),
            lambda a: a["receiver"]["configuration"]["bindings"][0].update(
                database_id="ordinary-db"
            ),
            lambda a: a["receiver"]["configuration"]["capabilities"].update(dispatch=True),
        ):
            changed = copy.deepcopy(additions)
            mutate(changed)
            with self.assertRaises(ValueError):
                build_delta(baseline, changed)

    def test_receiver_cannot_attach_production_routes_assets_or_secret_relationships(self):
        baseline, additions = composition_inputs()
        forbidden = {
            "routes": [{"pattern": "production.invalid/*", "zone_id": "production-zone"}],
            "domains": [{"hostname": "production.invalid", "zone_id": "production-zone"}],
            "assets": {"directory": "production-assets"},
            "classLifecycle": {"migrations": [{"tag": "prod", "new_classes": ["ProductionClass"]}]},
            "secretReferences": {"PRODUCTION_SECRET": {"reference": "production-generation"}},
            "attachment": {"tail_consumers": [{"service": "production-observer"}]},
            "effectiveEdge": {"rules": [{"id": "production-rule", "action": "skip"}]},
        }
        original = copy.deepcopy((baseline, additions))
        for section, relationship in forbidden.items():
            changed = copy.deepcopy(additions)
            changed["receiver"]["configuration"][section] = relationship
            with self.subTest(section=section), self.assertRaises(ValueError):
                build_delta(baseline, changed)
        self.assertEqual((baseline, additions), original)

    def test_unlisted_production_binding_reference_cannot_alias_synthetic_resource(self):
        baseline, additions = composition_inputs()
        for number, kind, field in (
            (0, "d1", "database_id"),
            (1, "d1", "database_id"),
            (2, "service", "service"),
        ):
            changed = copy.deepcopy(baseline)
            alias = additions["resources"][number]["identity"]
            changed["configuration"]["bindings"].append(
                {"name": "ORDINARY_ALIAS", "type": kind, field: alias}
            )
            # The resource inventory deliberately omits the known binding reference.
            self.assertNotIn(
                alias, [row["identity"] for row in changed["configuration"]["resources"]]
            )
            with self.subTest(resource=number), self.assertRaises(ValueError):
                build_delta(changed, additions)

    def test_unsupported_secrets_floats_or_unpaused_production_refuse(self):
        baseline, additions = composition_inputs()
        for mutation in (
            lambda b: b["configuration"]["bindings"][1].update(type="secret_text"),
            lambda b: b["productionState"].update(unsupported=0.5),
            lambda b: b["configuration"]["capabilities"].update(dispatch=True),
            lambda b: b.update(productionState={}),
        ):
            changed = copy.deepcopy(baseline)
            mutation(changed)
            with self.assertRaises(ValueError):
                build_delta(changed, additions)

    def test_tampered_restore_configuration_and_typed_rows_refuse(self):
        baseline, additions = composition_inputs()
        delta = build_delta(baseline, additions)
        for mutate in (
            lambda d: d["restore"].update(force=True),
            lambda d: d["restore"]["versions"][0].update(version_id="guessed-version"),
            lambda d: d["temporary"]["configuration"]["runtime"].update(flags=[]),
            lambda d: d["temporary"]["productionState"]["rows"][0].__setitem__(1, "1"),
            lambda d: d.update(temporarySha256="0" * 64),
        ):
            changed = copy.deepcopy(delta)
            mutate(changed)
            with self.assertRaises(ValueError):
                validate_delta(changed)

    def test_scope_cannot_retarget_bindings_or_extend_embedded_lifetime(self):
        baseline, additions = composition_inputs()
        for mutate in (
            lambda a: a["scope"].update(run="b" * 32),
            lambda a: a["scope"].update(expiresAt=601001),
            lambda a: a["scope"]["bindingKeys"].update(quotaDb="PRODUCTION_DB"),
            lambda a: a["scope"]["bindingKeys"].update(quotaDb="QUALIFICATION_DB"),
        ):
            changed = copy.deepcopy(additions)
            mutate(changed)
            with self.assertRaises(ValueError):
                build_delta(baseline, changed)

    def test_duplicate_json_fields_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplied.json"
            path.write_bytes(b'{"target":"original","target":"replacement"}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
