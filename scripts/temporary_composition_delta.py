"""Exact private-input configuration delta; no discovery, transport or credential reader.

The envelope retains supplied full sections rather than reconstructing provider
settings. Validation proves bounded offline consistency, not capture completeness
or provider preservation. Only three owned resources and four bindings are added.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, cast

from scripts.synthetic_restoration_packet import canonical, digest

MAX_BYTES = 4_000_000
CONFIG_KEYS = frozenset(
    "bindings resources runtime assets classLifecycle secretReferences attachment routes domains "
    "effectiveEdge capabilities".split()
)
BASELINE_KEYS = frozenset(
    "schemaVersion kind target retainedVersion deploymentWeights moduleSha256 "
    "configuration productionState".split()
)
ADDITION_KEYS = frozenset(
    "run temporaryVersion moduleSha256 bindings resources receiver scope".split()
)
DELTA_KEYS = frozenset(
    "schemaVersion kind baselineSha256 temporarySha256 baseline temporary additions restore".split()
)


def _require(test: bool, reason: str) -> None:
    if not test:
        raise ValueError(reason)


def _keys(value: Any, keys: set[str] | frozenset[str], reason: str) -> None:
    _require(type(value) is dict and set(value) == keys, reason)


def _identity(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None


def _hash(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _json(value: Any, depth: int = 0) -> None:
    _require(depth <= 32, "configuration_depth")
    if type(value) is dict:
        _require(all(type(key) is str for key in value), "configuration_key")
        for item in value.values():
            _json(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _json(item, depth + 1)
    else:
        _require(value is None or type(value) in (str, int, bool), "configuration_json_type")


def _bounded(value: Any) -> None:
    _json(value)
    _require(len(canonical(value).encode()) <= MAX_BYTES, "configuration_size")


def _bindings(value: Any) -> set[str]:
    _require(type(value) is list and len(value) <= 128, "binding_inventory")
    names = set()
    for binding in cast(list[dict[str, Any]], value):
        _require(
            type(binding) is dict
            and _identity(binding.get("name"))
            and _identity(binding.get("type")),
            "binding_identity",
        )
        _require(binding["name"] not in names, "duplicate_binding")
        # No secret values are part of this private configuration/reference packet.
        _require(binding["type"] != "secret_text", "secret_value_not_supported")
        names.add(binding["name"])
    return names


def _resources(value: Any, *, owned_run: str | None = None) -> set[str]:
    _require(type(value) is list and len(value) <= 128, "resource_inventory")
    identities = set()
    for resource in cast(list[dict[str, Any]], value):
        _require(
            type(resource) is dict
            and _identity(resource.get("kind"))
            and _identity(resource.get("identity")),
            "resource_identity",
        )
        if owned_run is not None:
            _keys(resource, {"kind", "identity", "run"}, "owned_resource_fields")
            _require(resource["run"] == owned_run, "resource_owner")
        _require(resource["identity"] not in identities, "duplicate_resource")
        identities.add(resource["identity"])
    return identities


def _reference_strings(value: Any) -> set[str]:
    """Reserve explicit relationship strings without guessing omitted provider identities."""
    if type(value) is str:
        return {value}
    references: set[str] = set()
    children = value.values() if type(value) is dict else value if type(value) is list else ()
    for child in children:
        references.update(_reference_strings(child))
    return references


def _production_references(configuration: dict[str, Any]) -> set[str]:
    # A separate resource ledger cannot overrule references already supplied in
    # ordinary bindings. Reserve opaque nonliteral fields conservatively: this
    # also handles unfamiliar binding formats without inventing an ID mapping.
    references = _resources(configuration["resources"])
    for binding in configuration["bindings"]:
        references.update(
            _reference_strings(
                {
                    key: value
                    for key, value in binding.items()
                    if key not in {"name", "type"}
                    and not (binding["type"] == "plain_text" and key == "text")
                }
            )
        )
    for key in (
        "assets",
        "classLifecycle",
        "secretReferences",
        "attachment",
        "routes",
        "domains",
        "effectiveEdge",
    ):
        references.update(_reference_strings(configuration[key]))
    return references


def validate_baseline(baseline: Any) -> None:
    """Require explicit full sections; their independently verified source is external."""
    _bounded(baseline)
    _keys(baseline, BASELINE_KEYS, "baseline_fields")
    _require(
        type(baseline["schemaVersion"]) is int
        and baseline["schemaVersion"] == 1
        and baseline["kind"] == "temporary_composition_baseline",
        "baseline_schema",
    )
    _keys(baseline["target"], {"accountId", "scriptName"}, "target_fields")
    _require(all(_identity(item) for item in baseline["target"].values()), "target_identity")
    _require(_identity(baseline["retainedVersion"]), "retained_version")
    weights = baseline["deploymentWeights"]
    _require(
        type(weights) is dict
        and set(weights) == {baseline["retainedVersion"]}
        and type(weights[baseline["retainedVersion"]]) is int
        and weights[baseline["retainedVersion"]] == 100,
        "retained_weights",
    )
    _require(_hash(baseline["moduleSha256"]), "module_digest")
    config = baseline["configuration"]
    _keys(config, CONFIG_KEYS, "complete_configuration_required")
    _bindings(config["bindings"])
    _resources(config["resources"])
    for key in CONFIG_KEYS - {"bindings", "resources", "routes", "domains"}:
        _require(type(config[key]) is dict, "configuration_section_type")
    for key in ("routes", "domains"):
        _require(type(config[key]) is list, "configuration_section_type")
    _keys(config["capabilities"], {"intake", "dispatch", "thumbnail"}, "capability_fields")
    _require(
        all(item is False for item in config["capabilities"].values()), "production_not_paused"
    )
    _require(
        type(baseline["productionState"]) is dict and bool(baseline["productionState"]),
        "complete_production_state_required",
    )


def build_delta(baseline: dict[str, Any], additions: dict[str, Any]) -> dict[str, Any]:
    """Append a fixed isolated D1/D1/service/capability set, preserving every baseline field."""
    validate_baseline(baseline)
    _bounded(additions)
    _keys(additions, ADDITION_KEYS, "addition_fields")
    run = additions["run"]
    _require(type(run) is str and re.fullmatch(r"[a-f0-9]{32}", run) is not None, "run_identity")
    _require(
        _identity(additions["temporaryVersion"])
        and additions["temporaryVersion"] != baseline["retainedVersion"],
        "temporary_version",
    )
    _require(_hash(additions["moduleSha256"]), "module_digest")
    names = _bindings(additions["bindings"])
    _require(len(names) == 4, "fixed_binding_inventory")
    config = baseline["configuration"]
    _require(not names.intersection(_bindings(config["bindings"])), "binding_collision")
    resources = additions["resources"]
    identities = _resources(resources, owned_run=run)
    _require(
        len(resources) == 3 and [item["kind"] for item in resources] == ["d1", "d1", "worker"],
        "fixed_resource_inventory",
    )
    _require(
        not identities.intersection(_production_references(config))
        and baseline["target"]["scriptName"] not in identities,
        "production_resource_collision",
    )
    bindings = additions["bindings"]
    _require(
        [item["type"] for item in bindings] == ["d1", "d1", "service", "plain_text"],
        "fixed_binding_types",
    )
    for binding, resource in zip(bindings[:3], resources, strict=True):
        field = "database_id" if binding["type"] == "d1" else "service"
        _keys(binding, {"name", "type", field}, "synthetic_binding_fields")
        _require(binding[field] == resource["identity"], "binding_resource_mismatch")
    scope = additions["scope"]
    _keys(scope, {"run", "startsAt", "expiresAt", "canary", "bindingKeys"}, "scope_fields")
    _require(
        scope["run"] == run
        and type(scope["startsAt"]) is int
        and 0 <= scope["startsAt"] <= 2**53 - 1_200_000
        and type(scope["expiresAt"]) is int
        and scope["expiresAt"] == scope["startsAt"] + 600_000
        and _hash(scope["canary"]),
        "scope_lifetime",
    )
    _require(
        scope["bindingKeys"]
        == dict(
            zip(
                ("syntheticDb", "quotaDb", "receiver", "capability"),
                [binding["name"] for binding in bindings],
                strict=True,
            )
        ),
        "scope_binding_keys",
    )
    _keys(bindings[3], {"name", "type", "text"}, "capability_binding_fields")
    _require(
        type(bindings[3]["text"]) is str
        and re.fullmatch(r"[a-f0-9]{64}", bindings[3]["text"]) is not None,
        "synthetic_capability",
    )
    receiver = additions["receiver"]
    _keys(
        receiver,
        {"binding", "identity", "run", "target", "configuration", "moduleSha256"},
        "receiver_fields",
    )
    _require(
        receiver["binding"] == bindings[2]["name"]
        and receiver["identity"] == resources[2]["identity"]
        and receiver["run"] == run
        and _hash(receiver["moduleSha256"]),
        "receiver_scope",
    )
    _keys(receiver["target"], {"accountId", "scriptName"}, "receiver_target_fields")
    _require(
        receiver["target"]
        == {"accountId": baseline["target"]["accountId"], "scriptName": resources[2]["identity"]},
        "receiver_target_scope",
    )
    receiver_baseline = copy.deepcopy(baseline)
    receiver_baseline["configuration"] = copy.deepcopy(receiver["configuration"])
    validate_baseline(receiver_baseline)
    _require(
        canonical(receiver["configuration"]["bindings"]) == canonical([bindings[1], bindings[3]])
        and canonical(receiver["configuration"]["resources"]) == canonical([resources[1]]),
        "receiver_isolation",
    )
    # This receiver has only its quota D1 and synthetic capability. No route,
    # asset, class, secret, tail, or edge relationship is supported by this packet.
    for section in ("assets", "classLifecycle", "secretReferences", "attachment", "effectiveEdge"):
        _require(receiver["configuration"][section] == {}, "receiver_relationship_not_supported")
    for section in ("routes", "domains"):
        _require(receiver["configuration"][section] == [], "receiver_relationship_not_supported")
    temporary = copy.deepcopy(baseline)
    temporary["retainedVersion"] = additions["temporaryVersion"]
    temporary["moduleSha256"] = additions["moduleSha256"]
    temporary["deploymentWeights"] = {additions["temporaryVersion"]: 100}
    temporary["configuration"]["bindings"].extend(copy.deepcopy(bindings))
    temporary["configuration"]["resources"].extend(copy.deepcopy(resources))
    return {
        "schemaVersion": 1,
        "kind": "offline_temporary_composition_delta",
        "baselineSha256": digest(baseline),
        "temporarySha256": digest(temporary),
        "baseline": copy.deepcopy(baseline),
        "temporary": temporary,
        "additions": copy.deepcopy(additions),
        "restore": {
            "strategy": "percentage",
            "force": False,
            "versions": [{"version_id": baseline["retainedVersion"], "percentage": 100}],
        },
    }


def validate_delta(delta: Any) -> None:
    _bounded(delta)
    _keys(delta, DELTA_KEYS, "delta_fields")
    expected = build_delta(delta["baseline"], delta["additions"])
    _require(canonical(delta) == canonical(expected), "configuration_delta_mismatch")


def load_json(path: Any) -> dict[str, Any]:
    """Explicit path only; reject duplicate keys and nonfinite/float configuration values."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    _require(len(raw) <= MAX_BYTES, "configuration_size")
    result = json.loads(raw, object_pairs_hook=pairs)
    _bounded(result)
    _require(type(result) is dict, "configuration_object_required")
    return result
