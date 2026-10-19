"""Closed offline input boundary for the disposable publisher operator.

Parsing a plan never grants authority. Only exact separate owner consent and
provider creation/readback receipts permit the lifecycle to advance. This module
does no network I/O, account discovery, credential reads or command execution.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

SCENARIOS = ("happy", "create_lost", "attachment_lost", "title_lost")
PHASES = ("seed", "http", "materialize", "attach", "title", "remove", "finish")
CANDIDATE_PINS = {
    "source_commit": "aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7",
    "source_artifact": "718b3dd7e1ec669c7e043f4c3a37142ceaad42a5bd3bcbc0639868a2b1e5aed1",
    "manifest": "f3ce7b2ba3cded646c825a6435a7217db742f226927f3633ae6ea61bc52a26c8",
    "worker": "b2241f88c94ec6561b2a902a5561bf9f63459e420fbd111861db1636feb2a26f",
    "disabled_probe_config": "c22298581a4d1586c0861dd8609cde4c219c70f8d1d9244e5fdc7e250ebdfe28",
    "disabled_production_config": (
        "98379c9b23a441ea083d2433ef0992616b98465266689011edbf3adbce7fe4df"
    ),
    "package_lock": "6894a3dcecffb784baae9751677b0c231250ae9e99a2cb6ddacc6011a0dc0048",
}
REQUIRED_OPERATOR_FILES = (
    "scripts/hosted_publisher_operator_plan.py",
    "scripts/hosted_publisher_operator.py",
    "scripts/hosted_publisher_provider.py",
    "scripts/hosted_publisher_worker_identity.py",
    "scripts/hosted_publisher_worker_deployment.py",
    "scripts/hosted_publisher_finite_client.py",
    "scripts/prepare_hosted_publisher_qualification.py",
    "probes/publisher-qualification/wrangler.jsonc",
    "wrangler.example.jsonc",
    "package-lock.json",
)
CURRENT_CONFIG_PINS = {
    "probes/publisher-qualification/wrangler.jsonc": CANDIDATE_PINS["disabled_probe_config"],
    "wrangler.example.jsonc": CANDIDATE_PINS["disabled_production_config"],
    "package-lock.json": CANDIDATE_PINS["package_lock"],
}
BUDGET_CEILINGS = {
    "provider_calls": 256,
    "provider_mutations": 160,
    "client_requests": 128,
    "sql_calls": 8192,
    "sql_statements": 1048576,
    "phase_seconds": 60,
    "lifecycle_seconds": 14400,
}
OWNER_ACTIONS = (
    "create_four_pairs",
    "migrate_0001_0026",
    "deploy_exact_worker",
    "enable_exact_endpoints",
    "seven_phases_once",
    "disable_access",
    "exclusive_operator",
    "synthetic_fixture_only",
    "fence_dispatch",
    "delete_owned_worker",
    "dispose_exact_synthetic_d1",
    "revoke_operator_grant",
)


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha2_256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_projection_digest(value: object) -> str:
    return sha2_256(encoded(value))


def _closed(value: Any, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError("Input object has missing or unrecognized fields")
    return value


def _text(value: Any, pattern: str, label: str) -> str:
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise ValueError(f"Invalid {label}")
    return value


def utc_time(value: str) -> datetime:
    _text(value, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", "UTC timestamp")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def database_time(value: str) -> int:
    """Validate D1/local UTC evidence without discarding fractional precision."""
    _text(value, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,18})?Z", "D1 UTC timestamp")
    whole, _, fraction = value[:-1].partition(".")
    parsed = datetime.strptime(whole, "%Y-%m-%dT%H:%M:%S")
    return calendar.timegm(parsed.timetuple()) * 10**18 + int(fraction.ljust(18, "0"))


def _uuid(value: Any) -> str:
    value = _text(value, r"[0-9a-f-]{36}", "D1 UUID")
    if str(UUID(value)) != value or UUID(value).int == 0:
        raise ValueError("Nonzero canonical D1 UUID required")
    return value


@dataclass(frozen=True)
class Budgets:
    provider_calls: int
    provider_mutations: int
    client_requests: int
    sql_calls: int
    sql_statements: int
    phase_seconds: int
    lifecycle_seconds: int


@dataclass(frozen=True)
class CasePlan:
    scenario: str
    worker_name: str
    d1_name: str
    endpoint: str
    run_id: str
    starts_at: str
    expires_at: str


@dataclass(frozen=True)
class OperatorPlan:
    schema_version: int
    account_id: str
    owner: str
    cleanup_owner: str
    revocation_owner: str
    starts_at: str
    expires_at: str
    cleanup_deadline: str
    cases: tuple[CasePlan, ...]
    budgets: Budgets
    pins: Mapping[str, str]
    source_files: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pins", MappingProxyType(dict(self.pins)))
        object.__setattr__(self, "source_files", MappingProxyType(dict(self.source_files)))

    @property
    def digest(self) -> str:
        document = dict(vars(self))
        document["cases"] = [asdict(case) for case in self.cases]
        document["budgets"] = asdict(self.budgets)
        document["pins"] = dict(self.pins)
        document["source_files"] = dict(self.source_files)
        return config_projection_digest(document)


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def load_plan(raw: bytes) -> OperatorPlan:
    if len(raw) > 262144:
        raise ValueError("Plan exceeds private input size limit")
    value = json.loads(raw, object_pairs_hook=_no_duplicates)
    data = _closed(value, set(OperatorPlan.__dataclass_fields__))
    if type(data["schema_version"]) is not int or data["schema_version"] != 2:
        raise ValueError("Unsupported plan schema")
    if type(data["cases"]) is not list or len(data["cases"]) != 4:
        raise ValueError("Exactly four isolated cases required")
    cases = tuple(CasePlan(**_closed(c, set(CasePlan.__dataclass_fields__))) for c in data["cases"])
    budgets = Budgets(**_closed(data["budgets"], set(BUDGET_CEILINGS)))
    plan = OperatorPlan(**{**data, "cases": cases, "budgets": budgets})
    validate_plan(plan)
    return plan


def validate_plan(plan: OperatorPlan, now: datetime | None = None) -> None:
    if type(plan.schema_version) is not int or plan.schema_version != 2:
        raise ValueError("Selected Beta operator schema required")
    _text(plan.account_id, r"[0-9a-f]{32}", "exact account ID")
    if plan.account_id == "0" * 32:
        raise ValueError("Placeholder account identity refused")
    for owner in (plan.owner, plan.cleanup_owner, plan.revocation_owner):
        _text(owner, r"[A-Za-z0-9][A-Za-z0-9 .@_-]{0,127}", "named owner")
    start, expiry, cleanup = map(utc_time, (plan.starts_at, plan.expires_at, plan.cleanup_deadline))
    if not start < expiry <= cleanup or (cleanup - start).total_seconds() > 14400:
        raise ValueError("Lifecycle must finish within four hours")
    if now is not None and not start <= now <= expiry:
        raise ValueError("Outside owner-authorized operation window")
    if plan.pins != CANDIDATE_PINS:
        raise ValueError("Final 0121 candidate pins changed")
    if not isinstance(plan.source_files, Mapping) or not set(REQUIRED_OPERATOR_FILES) <= set(
        plan.source_files
    ):
        raise ValueError("Current operator source closure is incomplete")
    for name, digest in plan.source_files.items():
        path = PurePosixPath(name)
        if (
            str(path) != name
            or path.is_absolute()
            or ".." in path.parts
            or ":" in name
            or "\\" in name
        ):
            raise ValueError("Unsafe source closure path")
        if not name.startswith(("scripts/", "migrations/", "probes/", "src/")) and name not in {
            "package.json",
            "package-lock.json",
            "wrangler.example.jsonc",
            "tsconfig.json",
        }:
            raise ValueError("Unexpected source closure file")
        _text(digest, r"[0-9a-f]{64}", "current source digest")
    for name, limit in BUDGET_CEILINGS.items():
        value = getattr(plan.budgets, name)
        if type(value) is not int or not 0 < value <= limit:
            raise ValueError("Nonfinite or excessive cumulative budget")
    if (
        plan.budgets.client_requests < 28
        or plan.budgets.provider_mutations > plan.budgets.provider_calls
    ):
        raise ValueError("Inconsistent lifecycle budgets")
    if (cleanup - start).total_seconds() > plan.budgets.lifecycle_seconds:
        raise ValueError("Lifecycle window exceeds time budget")
    if tuple(c.scenario for c in plan.cases) != SCENARIOS:
        raise ValueError("Closed scenario order required")
    for attr in ("worker_name", "d1_name", "endpoint", "run_id"):
        if len({getattr(c, attr) for c in plan.cases}) != 4:
            raise ValueError("Resource pairs and runs must be unique")
    for case in plan.cases:
        _text(case.worker_name, r"[a-z][a-z0-9-]{2,62}", "Worker name")
        _text(case.d1_name, r"[a-z][a-z0-9_-]{2,62}", "new D1 name")
        _text(case.run_id, r"[0-9a-f]{64}", "fresh run ID")
        if case.run_id == "0" * 64:
            raise ValueError("Placeholder run identity refused")
        url = urlsplit(case.endpoint)
        if (
            url.scheme != "https"
            or url.username
            or url.password
            or url.port is not None
            or url.path
            or url.query
            or url.fragment
            or not url.hostname
            or url.hostname != url.netloc
            or not url.hostname.endswith(".workers.dev")
            or url.hostname.split(".")[0] != case.worker_name
            or len(url.hostname.split(".")) != 4
            or not re.fullmatch(
                re.escape(case.worker_name)
                + r"\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.workers\.dev",
                url.hostname,
            )
        ):
            raise ValueError("Exact disposable workers.dev HTTPS origin required")
        case_start, case_expiry = map(utc_time, (case.starts_at, case.expires_at))
        if not start <= case_start < case_expiry <= expiry:
            raise ValueError("Case outside authorized window")
        if (case_expiry - case_start).total_seconds() > 1800:
            raise ValueError("Case access window exceeds thirty minutes")


def validate_consent(plan: OperatorPlan, consent: dict[str, Any], now: datetime) -> None:
    _closed(
        consent, {"schema_version", "granted", "plan_digest", "owner", "actions", "decision_id"}
    )
    validate_plan(plan, now)
    if (
        type(consent["schema_version"]) is not int
        or consent["schema_version"] != 1
        or consent["granted"] is not True
        or consent["plan_digest"] != plan.digest
        or consent["owner"] != plan.owner
        or consent["actions"] != list(OWNER_ACTIONS)
    ):
        raise ValueError("Exact separate owner consent is absent")
    _text(consent["decision_id"], r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", "owner decision reference")


def validate_operator_grant(plan: OperatorPlan, grant: dict[str, Any], now: datetime) -> None:
    """Validate trusted grant metadata; a caller assertion is not provider evidence.

    Account-scoped create authority cannot yet name unassigned D1 IDs. The
    provider adapter must enforce the four exact intended names in this plan.
    This function never receives or reads the management credential itself.
    """
    fields = {
        "grant_id",
        "account_id",
        "permissions",
        "issued_at",
        "expires_at",
        "revocation_owner",
        "resource_scope",
        "metadata_verified",
    }
    if type(grant) is dict and "expiry_policy" in grant:
        fields.add("expiry_policy")
    _closed(grant, fields)
    issued, expiry = map(utc_time, (grant["issued_at"], grant["expires_at"]))
    if "expiry_policy" in grant:
        policy = _closed(grant["expiry_policy"], {"amendment_id", "decision_id", "plan_digest"})
        # These exact bindings select accepted policy, not proof of human approval
        # or provider metadata. Existing independent evidence/approval gates remain.
        if (
            policy
            != {
                "amendment_id": "hosted-publisher-token-expiry-amendment-2026-10-18",
                "decision_id": "call_db0854bafa8748aca10153fc4d4a8a7b",
                "plan_digest": plan.digest,
            }
            or plan.revocation_owner != "Terry Ott"
            or (expiry - issued).total_seconds() > 86400
            or expiry > utc_time("2026-10-19T04:00:00Z")
        ):
            raise ValueError("One-attempt provider expiry amendment is not exact and limited")
    elif expiry > utc_time(plan.cleanup_deadline):
        raise ValueError("Private operator grant is not exact, limited and current")
    if (
        grant["metadata_verified"] is not True
        or grant["account_id"] != plan.account_id
        or grant["permissions"] != ["D1:Edit", "Workers Scripts:Edit"]
        or grant["resource_scope"] != "exact-account-only"
        or grant["revocation_owner"] != plan.revocation_owner
        or not issued <= now < expiry
    ):
        raise ValueError("Private operator grant is not exact, limited and current")
    _text(grant["grant_id"], r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", "grant reference")


def _regular_file(root: Path, name: str) -> Path:
    _refuse_links(root)
    root = root.resolve(strict=True)
    path = root / name
    for entry in (path, *path.parents):
        if entry == root:
            break
        if entry.is_symlink() or entry.is_junction():
            raise ValueError("Linked private inputs are refused")
    if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
        raise ValueError("Input escapes exact artifact root")
    return path


def _refuse_links(path: Path) -> None:
    for entry in (path.absolute(), *path.absolute().parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError("Linked private input root or ancestor refused")


def validate_current_inputs(plan: OperatorPlan, root: Path) -> None:
    validate_plan(plan)
    for name, expected in plan.source_files.items():
        if sha2_256(_regular_file(root, name).read_bytes()) != expected:
            raise ValueError("Reviewed operator/current source drift")
    for name, expected in CURRENT_CONFIG_PINS.items():
        if sha2_256(_regular_file(root, name).read_bytes()) != expected:
            raise ValueError("Current candidate configuration or toolchain drift")


def validate_artifact(source_root: Path, bundle_path: Path) -> None:
    """Rehash all 113 retained inputs, migrations and exact optimized bytes."""
    if __package__:
        from .prepare_hosted_publisher_qualification import SOURCES
    else:
        from prepare_hosted_publisher_qualification import SOURCES

    raw = _regular_file(source_root, "manifest.json").read_bytes()
    if sha2_256(raw) != CANDIDATE_PINS["manifest"]:
        raise ValueError("Final manifest bytes drifted")
    manifest = json.loads(raw, object_pairs_hook=_no_duplicates)
    identity = {k: v for k, v in manifest.items() if k != "artifactSha2_256"}
    legacy_encoded = (
        json.dumps(identity, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode()
    if (
        manifest["artifactSha2_256"] != CANDIDATE_PINS["source_artifact"]
        or sha2_256(legacy_encoded) != CANDIDATE_PINS["source_artifact"]
        or manifest["sourceHead"] != CANDIDATE_PINS["source_commit"]
        or manifest["sourceCommitExact"] is not True
        or len(manifest["files"]) != 113
        or {f["path"] for f in manifest["files"]} != set(SOURCES)
    ):
        raise ValueError("Retained candidate identity changed")
    for record in manifest["files"]:
        data = _regular_file(source_root, record["path"]).read_bytes()
        if len(data) != record["bytes"] or sha2_256(data) != record["sha2_256"]:
            raise ValueError("Retained source/migration bytes drifted")
    _refuse_links(bundle_path)
    data = bundle_path.read_bytes()
    if len(data) != 652967 or sha2_256(data) != CANDIDATE_PINS["worker"]:
        raise ValueError("Final optimized Worker bytes drifted")


@dataclass(frozen=True)
class CreationReceipt:
    scenario: str
    worker_name: str
    d1_name: str
    d1_uuid: str
    created_at: str | None
    empty_verified: bool
    plan_digest: str
    request_started_at: str
    response_received_at: str


@dataclass(frozen=True)
class BoundCase:
    case: CasePlan
    d1_uuid: str
    overlay_digest: str


def bind_resources(plan: OperatorPlan, receipts: list[CreationReceipt]) -> tuple[BoundCase, ...]:
    validate_plan(plan)
    if len(receipts) != 4 or len({r.d1_uuid for r in receipts}) != 4:
        raise ValueError("Four fresh unique creation receipts required")
    result = []
    for case, receipt in zip(plan.cases, receipts, strict=True):
        _uuid(receipt.d1_uuid)
        if (
            (receipt.scenario, receipt.worker_name, receipt.d1_name)
            != (case.scenario, case.worker_name, case.d1_name)
            or receipt.plan_digest != plan.digest
            or receipt.empty_verified is not True
            or not database_time(case.starts_at)
            <= database_time(receipt.request_started_at)
            <= database_time(receipt.response_received_at)
            < database_time(case.expires_at)
            or (
                receipt.created_at is not None
                and not database_time(plan.starts_at)
                <= database_time(receipt.created_at)
                < database_time(case.expires_at)
            )
        ):
            raise ValueError("Creation receipt is not exact fresh authorized identity")
        projection = deployment_projection(plan, case, receipt.d1_uuid)
        result.append(BoundCase(case, receipt.d1_uuid, config_projection_digest(projection)))
    return tuple(result)


def deployment_projection(plan: OperatorPlan, case: CasePlan, d1_uuid: str) -> dict[str, Any]:
    """Provider readback must match this actual binding, never a request header."""
    validate_plan(plan)
    if case not in plan.cases:
        raise ValueError("Case outside exact plan")
    _uuid(d1_uuid)
    variables = {
        "PROBE_ENABLED": "1",
        "PROBE_SCOPE": "publisher-disposable-v1",
        "PROBE_ARTIFACT_SHA2_256": CANDIDATE_PINS["source_artifact"],
        "PROBE_RUN_ID": case.run_id,
        "PROBE_RESOURCE_ID": d1_uuid,
        "PROBE_EXPIRES_AT": case.expires_at,
        "PROBE_SCENARIO": case.scenario,
    }
    return {
        "main_module": "worker.js",
        "compatibility_date": "2026-10-16",
        "compatibility_flags": ["nodejs_compat"],
        "observability": {"enabled": False},
        "logpush": False,
        "bindings": [
            {"name": "DB", "type": "d1", "id": d1_uuid},
            {"name": "PROBE_ACCESS_TOKEN", "type": "secret_text"},
            *[
                {"name": name, "type": "plain_text", "text": text}
                for name, text in sorted(variables.items())
            ],
        ],
    }


def validate_deployed_projection(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    """Adapters may normalize order only; unknown bindings/settings refuse."""

    def normalized(value: dict[str, Any]) -> dict[str, Any]:
        value = dict(value)
        bindings = value.get("bindings")
        if type(bindings) is not list or any(type(b) is not dict for b in bindings):
            raise ValueError("Malformed deployed bindings")
        if len({b.get("name") for b in bindings}) != len(bindings):
            raise ValueError("Duplicate deployed binding")
        value["bindings"] = sorted(bindings, key=lambda b: b["name"])
        return value

    if normalized(expected) != normalized(actual):
        raise ValueError("Actual deployed D1/module configuration drift")


@dataclass(repr=False)
class PrivateInputs:
    """Fresh synthetic access tokens; memory only, never accepted in plan JSON.

    The transport's separately authorized provider credential must be injected
    through a private in-process boundary. This class never discovers or reads it.
    """

    _tokens: dict[str, str] = field(repr=False)
    _revoked: bool = field(default=False, repr=False)

    @classmethod
    def fresh(cls, plan: OperatorPlan) -> PrivateInputs:
        validate_plan(plan)
        return cls({case.scenario: secrets.token_hex(32) for case in plan.cases})

    def token(self, scenario: str) -> str:
        if self._revoked or scenario not in self._tokens:
            raise ValueError("Private synthetic access is unavailable")
        return self._tokens[scenario]

    def revoke_local(self) -> None:
        """Drops local references; provider-side revocation still needs a receipt."""
        self._tokens.clear()
        self._revoked = True
