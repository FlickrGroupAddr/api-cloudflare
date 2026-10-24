"""Inert, exact SOURCE composition of the existing finite publisher provider.

MIT License; copyright 2026 Terry Ott.

This module reads public source bytes and supplies an explicitly invented,
in-memory rehearsal. It never reads credentials or selects a live transport.
The request graph is executable SOURCE inspection, not provider qualification,
resource ownership, consent, drain proof, actual wire cost or committed effects.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from scripts import hosted_publisher_worker_deployment as source_provider
from scripts.hosted_publisher_provider import (
    ProviderError,
    ProviderUnknown,
    validate_worker_projection,
)
from scripts.hosted_publisher_worker_deployment import BetaPublisherProvider

ROOT = Path(source_provider.__file__).resolve().parents[1]
PROVIDER = "scripts/hosted_publisher_worker_deployment.py"
IDENTITY = "scripts/hosted_publisher_worker_identity.py"
BOUNDARY = "scripts/hosted_publisher_provider.py"
ORDINARY = "probes/pmb1-retained-integration/ordinary.ts"
OPERATOR = "probes/pmb1-finite-runner/native_operator.py"
PLAN = "scripts/hosted_publisher_operator_plan.py"
# Complete project-local Python import closure, plus the ordinary SOURCE
# reference. scripts is a namespace package; no scripts/__init__.py is present.
SOURCES = (PROVIDER, IDENTITY, BOUNDARY, PLAN, ORDINARY, OPERATOR)
DISPATCH_ENABLED = False


def _loaded_python_sources() -> tuple[tuple[str, str], ...]:
    """Snapshot loaded project code bytes, including package initializers."""
    sources = {OPERATOR: Path(__file__).resolve()}
    for name, module in tuple(sys.modules.items()):
        if name != "scripts" and not name.startswith("scripts."):
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:  # The current scripts namespace has no initializer.
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(ROOT) or path.suffix != ".py":
            raise ValueError("operator_loaded_project_dependency_outside_source_root")
        sources[path.relative_to(ROOT).as_posix()] = path
    return tuple(
        sorted(
            (name, hashlib.sha256(path.read_bytes()).hexdigest()) for name, path in sources.items()
        )
    )


_LOADED_SOURCE_PINS = _loaded_python_sources()


class OperatorRefused(ValueError):
    """A closed SOURCE boundary rejected work before its next request."""


def loaded_source_pins() -> tuple[tuple[str, str], ...]:
    """Return pins captured at import; reject drift or newly loaded project code.

    Current bytes cannot silently replace the loaded bytes. The enclosing runner
    must also compare these pins against its independently retained manifest.
    This method does not authenticate its own output as Root authority.
    """
    if _loaded_python_sources() != _LOADED_SOURCE_PINS:
        raise OperatorRefused("operator_loaded_python_source_or_closure_drift")
    return _LOADED_SOURCE_PINS


@dataclass(frozen=True)
class OperatorInputs:
    worker_id: str
    worker_name: str
    temporary_version_id: str
    retained_version_id: str
    endpoint: str
    source_pins: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RequestLeaf:
    key: str
    method: str
    path: str
    source_path: str
    source_pin: str
    mutation: bool
    resource: str
    version: str | None = None
    # Provider statements/committed effects and HTTP framing cannot be inferred
    # from one management request. None is deliberately different from zero.
    statements: int | None = None
    effects: int | None = None
    wire_bytes: int | None = None


@dataclass(frozen=True)
class OperatorStep:
    name: str
    method: str
    source_path: str
    source_pin: str
    leaves: tuple[RequestLeaf, ...]
    missing_facts: tuple[str, ...] = ()


def retained_source_pins(root: Path = ROOT) -> tuple[tuple[str, str], ...]:
    """Read public bytes only; these pins are not independent acceptance."""
    loaded_source_pins()
    paths = tuple(dict.fromkeys((*SOURCES, *(path for path, _ in _LOADED_SOURCE_PINS))))
    return tuple(
        (
            path,
            hashlib.sha256(
                (Path(__file__) if path == OPERATOR else root / path).read_bytes()
            ).hexdigest(),
        )
        for path in paths
    )


def fixture_inputs(root: Path = ROOT) -> OperatorInputs:
    """Invented resource identities; no runtime input or retained fact is read."""
    return OperatorInputs(
        "1" * 32,
        "fga-publisher-invented-0200",
        "00000001-2222-4222-8222-222222222222",
        "00000002-2222-4222-8222-222222222222",
        "https://fga-publisher-invented-0200.synthetic.workers.dev",
        retained_source_pins(root),
    )


def _validate(inputs: OperatorInputs, root: Path) -> dict[str, str]:
    if (root / "scripts/__init__.py").exists():
        raise OperatorRefused("operator_namespace_initializer_not_in_reviewed_closure")
    uuid = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
    if (
        type(inputs) is not OperatorInputs
        or any(
            type(value) is not str
            for value in (
                inputs.worker_id,
                inputs.worker_name,
                inputs.temporary_version_id,
                inputs.retained_version_id,
                inputs.endpoint,
            )
        )
        or not re.fullmatch(r"[a-f0-9]{32}", inputs.worker_id)
        or inputs.worker_id == "0" * 32
        or not re.fullmatch(r"fga-publisher-[a-z0-9-]{1,48}", inputs.worker_name)
        or not re.fullmatch(uuid, inputs.temporary_version_id)
        or not re.fullmatch(uuid, inputs.retained_version_id)
        or inputs.temporary_version_id == "00000000-0000-0000-0000-000000000000"
        or inputs.retained_version_id == "00000000-0000-0000-0000-000000000000"
        or inputs.temporary_version_id == inputs.retained_version_id
        or not re.fullmatch(
            r"https://" + re.escape(inputs.worker_name) + r"\.[a-z0-9-]+\.workers\.dev",
            inputs.endpoint,
        )
    ):
        raise OperatorRefused("operator_exact_identity_required")
    actual = retained_source_pins(root)
    if type(inputs.source_pins) is not tuple or inputs.source_pins != actual:
        raise OperatorRefused("operator_source_drift")
    return dict(actual)


def build_operator_steps(inputs: OperatorInputs, *, root: Path = ROOT) -> tuple[OperatorStep, ...]:
    """Expand the actual inherited invocations, including every nested request.

    The deployment's name-addressed POST is bracketed by immutable-ID reads.
    This is the inherited exclusive-owner assumption, not a CAS guarantee.
    The prospective restore has its own one-shot intent in this SOURCE helper;
    actual custody, provider effects and transport qualification remain unknown.
    """
    pins = _validate(inputs, root)
    worker = "/workers/workers/" + inputs.worker_id
    deployments = "/workers/scripts/" + inputs.worker_name + "/deployments"

    def leaf(key: str, method: str, path: str, source: str, version: str | None = None):
        return RequestLeaf(
            key, method, path, source, pins[source], method != "GET", inputs.worker_id, version
        )

    def step(name: str, method: str, leaves: tuple[RequestLeaf, ...], gaps=(), source=PROVIDER):
        return OperatorStep(name, method, source, pins[source], leaves, tuple(gaps))

    def inspect_version(key: str, version: str):
        return leaf(
            key, "GET", worker + "/versions/" + version + "?include=modules", PROVIDER, version
        )

    def deploy(key: str, version: str):
        return (
            inspect_version(key + ":version", version),
            leaf(key + ":before", "GET", worker, IDENTITY),
            leaf(key, "POST", deployments, PROVIDER, version),
            leaf(key + ":after", "GET", worker, IDENTITY),
        )

    def deployment_read(key: str, version: str):
        return (
            leaf(key + ":before", "GET", worker, IDENTITY),
            leaf(key + ":current", "GET", deployments + "?page=1&per_page=1", PROVIDER, version),
            leaf(key + ":after", "GET", worker, IDENTITY),
        )

    temporary, retained = inputs.temporary_version_id, inputs.retained_version_id
    return (
        step(
            "retained.capture",
            "ProspectiveSourceProvider.capture_retained_version",
            (inspect_version("retained:capture", retained),),
            source=OPERATOR,
        ),
        step(
            "temporary.create",
            "BetaPublisherProvider.create_version",
            (leaf("temporary:create", "POST", worker + "/versions?deploy=false", PROVIDER),),
        ),
        step(
            "temporary.version",
            "BetaPublisherProvider.inspect_version",
            (inspect_version("temporary:version", temporary),),
        ),
        step(
            "temporary.deploy",
            "BetaPublisherProvider.deploy_version",
            deploy("temporary:deploy", temporary),
        ),
        step(
            "temporary.deployment",
            "BetaPublisherProvider.inspect_deployment",
            deployment_read("temporary:deployment", temporary),
        ),
        step(
            "stop.disable",
            "BetaPublisherProvider.disable_worker",
            (
                leaf("stop:disable:identity", "GET", worker, IDENTITY),
                leaf("stop:disable", "PATCH", worker, IDENTITY),
            ),
            ("disable_acknowledgement_is_not_inflight_drain",),
        ),
        step(
            "stop.endpoint",
            "BetaPublisherProvider.inspect_endpoint",
            (leaf("stop:endpoint", "GET", worker, PROVIDER),),
        ),
        step(
            "restore.deploy",
            "ProspectiveRestoreProgram.restore_retained_version",
            deploy("restore:deploy", retained),
            ("genuine_current_closed_preflight_and_custody_not_qualified",),
            source=OPERATOR,
        ),
        step(
            "restore.version",
            "BetaPublisherProvider.inspect_version",
            (inspect_version("restore:version", retained),),
        ),
        step(
            "restore.deployment",
            "BetaPublisherProvider.inspect_deployment",
            deployment_read("restore:deployment", retained),
        ),
        step(
            "restore.endpoint",
            "BetaPublisherProvider.inspect_endpoint",
            (leaf("restore:endpoint", "GET", worker, PROVIDER),),
        ),
        step(
            "restore.origin",
            "BetaPublisherProvider.assert_endpoint",
            (
                leaf("restore:origin:identity", "GET", worker, PROVIDER),
                leaf("restore:origin:subdomain", "GET", "/workers/subdomain", PROVIDER),
            ),
        ),
        step(
            "restore.ordinary",
            "closedRestorationCheck",
            (),
            ("ordinary_closed_authenticated_edge_transport_not_qualified",),
            source=ORDINARY,
        ),
        step(
            "cleanup.delete",
            "BetaPublisherProvider.delete_worker",
            (
                leaf("cleanup:delete:identity", "GET", worker, IDENTITY),
                leaf("cleanup:delete", "DELETE", worker, IDENTITY),
            ),
            ("cleanup_requires_authenticated_exact_creation_receipt_and_disabled_worker",),
        ),
        step(
            "cleanup.absence",
            "BetaPublisherProvider.inspect_worker",
            (leaf("cleanup:absence", "GET", worker, IDENTITY),),
        ),
    )


def source_gap_report(inputs: OperatorInputs, *, root: Path = ROOT) -> dict[str, Any]:
    steps = build_operator_steps(inputs, root=root)
    return {
        "dispatchEnabled": False,
        "sourceBlockers": tuple((step.name, gap) for step in steps for gap in step.missing_facts),
        "missingActualFacts": (
            "current_authority_and_window",
            "exclusive_owner_and_resource_ownership",
            "complete_source_and_population_binding",
            "inflight_drain_and_callback_settlement",
            "provider_and_authenticated_transport_qualification",
            "wire_bytes_and_committed_effects",
        ),
        "actualWireBytes": None,
        "actualEffects": None,
    }


def execute_native(inputs: OperatorInputs, *, root: Path = ROOT) -> None:
    """No argument, JSON attestation or transport flag can enable dispatch."""
    build_operator_steps(inputs, root=root)
    raise OperatorRefused("native_operator_dispatch_disabled_and_source_gaps")


@dataclass(frozen=True)
class SyntheticReceipt:
    fragment: str
    requests: int
    mutation_requests: int
    request_body_bytes: int
    response_body_bytes: int
    keys: tuple[str, ...]
    outcome: str
    actual_wire_bytes: None = None
    actual_effects: None = None
    dispatch_enabled: bool = False


class InventedProviderIO:
    """Closed in-memory provider fixture, never a caller supplied callback.

    The real inherited provider serializes, validates and accounts for each
    request/receipt. Only this fake wire owns fixture state. Fault selection is
    a closed invented test input and grants no authority or qualification.
    """

    def __init__(self, inputs: OperatorInputs, fault: str | None = None):
        if fault not in (None, "lost_deployment", "lost_restore", "wrong_version", "wrong_worker"):
            raise OperatorRefused("synthetic_fault_not_supported")
        self.inputs, self.fault = inputs, fault
        self.workers: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, dict[str, Any]] = {}
        self.deployments: dict[str, Any] = {}
        self.database: dict[str, Any] | None = None
        self.requests = 0
        self.now = 10.0
        self.deployment_posts = 0

    def seed_retained_fixture(self, module: bytes, projection: dict[str, Any]):
        """Fixture setup only; never evidence of actual retained ownership."""
        private = validate_worker_projection(
            module, hashlib.sha256(module).hexdigest(), projection, "d" * 64
        )
        self.versions[self.inputs.retained_version_id] = {
            **{
                key: copy.deepcopy(private[key])
                for key in ("main_module", "compatibility_date", "compatibility_flags", "bindings")
            },
            "modules": [
                {
                    "name": "worker.js",
                    "content_type": "application/javascript+module",
                    "content_base64": base64.b64encode(module).decode("ascii"),
                }
            ],
            "id": self.inputs.retained_version_id,
            "created_on": "2026-10-24T00:00:00Z",
            "cache_options": {"enabled": False, "cross_version_cache": False},
        }

    def __call__(self, method, path, raw, _headers, _timeout, _cap):
        prefix = "/client/v4/accounts/" + "a" * 32
        if not path.startswith(prefix):
            raise AssertionError("invented_account_mismatch")
        path = path[len(prefix) :]
        body = json.loads(raw) if raw else None
        self.requests += 1
        result, status = self._request(method, path, body)
        if self.fault == "lost_deployment" and method == "POST" and path.endswith("/deployments"):
            # Effect occurs in invented memory, then acknowledgement disappears.
            raise OSError("invented_lost_acknowledgement")
        if (
            self.fault == "lost_restore"
            and method == "POST"
            and path.endswith("/deployments")
            and self.deployment_posts == 2
        ):
            raise OSError("invented_lost_restore_acknowledgement")
        return status, {}, json.dumps({"success": status != 404, "result": result}).encode()

    def _request(self, method: str, path: str, body: Any) -> tuple[Any, int]:
        stamp = "2026-10-24T00:00:00Z"
        worker_path = "/workers/workers/" + self.inputs.worker_id
        if method == "POST" and path == "/d1/database":
            self.database = {
                "uuid": "00000001-1111-4111-8111-111111111111",
                "name": body["name"],
                "created_at": stamp,
            }
            return copy.deepcopy(self.database), 200
        if method == "POST" and path == "/workers/workers":
            value = {
                **body,
                "id": self.inputs.worker_id,
                "created_on": stamp,
                "references": {
                    key: []
                    for key in (
                        "dispatch_namespace_outbounds",
                        "domains",
                        "durable_objects",
                        "queues",
                        "workers",
                    )
                },
            }
            value["subdomain"]["url"] = self.inputs.endpoint
            self.workers[self.inputs.worker_id] = copy.deepcopy(value)
            return value, 200
        if path.startswith(worker_path + "/versions"):
            if method == "POST" and path == worker_path + "/versions?deploy=false":
                value = {**body, "id": self.inputs.temporary_version_id, "created_on": stamp}
                if self.fault == "wrong_version":
                    value["id"] = self.inputs.retained_version_id
                self.versions[value["id"]] = copy.deepcopy(value)
                return value, 200
            if method == "GET":
                version = path.split("/")[-1].split("?")[0]
                return copy.deepcopy(self.versions[version]), 200
        if path == worker_path:
            if method == "DELETE":
                self.workers.pop(self.inputs.worker_id, None)
                return {}, 200
            if self.inputs.worker_id not in self.workers:
                return None, 404
            if method == "PATCH":
                self.workers[self.inputs.worker_id].update(copy.deepcopy(body))
                self.workers[self.inputs.worker_id]["subdomain"]["url"] = self.inputs.endpoint
            result = copy.deepcopy(self.workers[self.inputs.worker_id])
            if method == "GET" and self.fault == "wrong_worker":
                result["id"] = "f" * 32
            return result, 200
        deployment_path = "/workers/scripts/" + self.inputs.worker_name + "/deployments"
        if method == "POST" and path == deployment_path:
            self.deployment_posts += 1
            value = {
                **body,
                "id": f"{self.deployment_posts:08}-3333-4333-8333-333333333333",
                "created_on": stamp,
            }
            self.deployments = copy.deepcopy(value)
            return value, 200
        if method == "GET" and path == deployment_path + "?page=1&per_page=1":
            return {"deployments": [copy.deepcopy(self.deployments)]}, 200
        if method == "GET" and path == "/workers/subdomain":
            return {"subdomain": "synthetic"}, 200
        raise AssertionError("invented_request_outside_exact_fixture")


@dataclass(frozen=True)
class SourceClosedPreflight:
    """Synthetic readback binding, explicitly incapable of actual authority.

    The adapter also requires object identity with its own retained receipt.
    Constructing this dataclass, or copying its JSON, grants nothing. Real native
    all-writer settlement/custody remains UNKNOWN until separately qualified.
    """

    worker_id: str
    temporary_version_id: str
    retained_version_id: str
    retained_module_sha2_256: str
    retained_configuration_sha2_256: str
    provider_readback: bytes
    source_pins: tuple[tuple[str, str], ...]
    observed_at: float
    expires_at: float
    actual_authority: None = None


class ProspectiveSourceProvider(BetaPublisherProvider):
    """Two distinct named deployment intents for the inert PMB-1 SOURCE proof.

    The inherited initial deployment is unchanged. The one retained restore has
    a separate consumed-before-request intent; it does not reset inherited state,
    retry a request, reopen admission or create another provider session. Its
    exact immutable readback/POST/readback use the inherited request boundary.

    Accepted PMB-1 allocates both temporary installation and one retained restore
    (prospective-maintenance-baseline-design-2026-10-18.md:350-359). The earlier
    publisher's one-deployment guard is an implementation constraint, not a PMB-1
    prohibition. This source subclass accepts only its own invented wire. Actual
    dispatch remains unavailable, including through direct construction.
    """

    def __init__(self, inputs: OperatorInputs, io: InventedProviderIO, fence: _RequestFence):
        if type(io) is not InventedProviderIO or io.inputs is not inputs:
            raise OperatorRefused("prospective_source_invented_wire_only")
        self._source_inputs = inputs
        self._source_fence = fence
        self._source_retained: dict[str, Any] | None = None
        self._source_preflight: SourceClosedPreflight | None = None
        self._source_restore_spent = False
        super().__init__(
            "a" * 32,
            "invented-token-never-read-from-runtime",
            [inputs.worker_name],
            [inputs.worker_name + "-db"],
            exclusive_owner=True,
            transport=io,
            monotonic=lambda: io.now,
            before_request=fence.before,
            after_request=fence.after,
        )

    def _request(self, method, path, body=None, *, key, media="application/json", raw=False):
        """Fence exact nested method/path/version before the existing boundary."""
        self._source_fence.check()
        position = self._source_fence.position
        leaves = self._source_fence.leaves
        if position >= len(leaves):
            raise OperatorRefused("source_nested_request_not_in_program")
        expected = leaves[position]
        if (
            key != expected.key
            or method != expected.method
            or path != expected.path
            or media != "application/json"
            or raw is not False
            or (method == "GET" and body is not None)
        ):
            raise OperatorRefused("source_nested_request_differs_from_program")
        if method == "POST" and path.endswith("/deployments"):
            if body != {
                "strategy": "percentage",
                "versions": [{"version_id": expected.version, "percentage": 100}],
            }:
                raise OperatorRefused("source_deployment_payload_target_mismatch")
        return super()._request(method, path, body, key=key, media=media, raw=raw)

    def capture_retained_version(self, identity, module, sha2, projection, *, key):
        """Verify the exact fixture-retained module/configuration before install.

        The immutable worker must already have its own acknowledged creation
        receipt in this session. No discovery, name adoption, latest-version
        selection or unauthenticated cleanup registration is involved.
        """
        with self._session_lock:
            self._source_fence.check()
            if self._source_retained is not None or self._deployment_intents:
                raise OperatorRefused("source_retained_capture_must_precede_install")
            private = validate_worker_projection(module, sha2, projection, "d" * 64)
            configuration = {
                key: copy.deepcopy(private[key])
                for key in ("main_module", "compatibility_date", "compatibility_flags", "bindings")
            }
            configuration["bindings"] = self._bindings(configuration["bindings"])
            receipt = {
                "id": self._source_inputs.retained_version_id,
                "workerId": identity["id"],
                "moduleSha2_256": sha2,
            }
            expected = {"id": receipt["id"], "configuration": configuration, "receipt": receipt}
            result = self._request(
                "GET",
                self.identity._path(identity) + "/versions/" + receipt["id"] + "?include=modules",
                key=key,
            )
            self._validate_version(result, expected, include_modules=True)
            self._source_fence.check()
            self._versions[receipt["id"]] = copy.deepcopy(expected)
            self._source_retained = {
                "identity": copy.deepcopy(identity),
                "version": receipt.copy(),
                "configuration": hashlib.sha256(
                    json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            }
            return receipt.copy()

    def source_closed_preflight(self, identity, temporary_version, *, key):
        """Read the fake provider closure; actual native custody stays UNKNOWN."""
        with self._session_lock:
            self._source_fence.check()
            retained = self._source_retained
            if (
                retained is None
                or identity != retained["identity"]
                or temporary_version["id"] != self._source_inputs.temporary_version_id
                or identity["id"] not in self._deployment_intents
                or self._source_preflight is not None
                or self._source_restore_spent
            ):
                raise OperatorRefused("source_closed_preflight_binding")
            endpoint = self.inspect_endpoint(identity, key=key)
            if endpoint != {"enabled": False, "previews_enabled": False}:
                raise OperatorRefused("source_endpoint_not_closed")
            self._source_fence.check()
            observed = self._clock()
            receipt = SourceClosedPreflight(
                identity["id"],
                temporary_version["id"],
                retained["version"]["id"],
                retained["version"]["moduleSha2_256"],
                retained["configuration"],
                json.dumps(endpoint, sort_keys=True).encode(),
                self._source_inputs.source_pins,
                observed,
                min(observed + 60, self._source_fence.deadline),
            )
            self._source_preflight = receipt
            return receipt

    def restore_retained_version(self, identity, version, preflight, *, key):
        return SourceHarnessFactory.restore(self, identity, version, preflight, key=key)


class RootOperatorContext(Protocol):
    """Trusted Root composition seam; no implementation here grants authority.

    The genuine Root owner must authenticate retained inputs, native closed
    generation/custody receipts and the exact current packet, and install its
    request fence on the existing provider. JSON labels or a callback returning
    True cannot enable the public program: its dispatch gate remains disabled.
    """

    inputs: OperatorInputs
    retained: dict[str, Any] | None
    preflight: SourceClosedPreflight | None
    fence: Any

    @property
    def restore_spent(self) -> bool: ...

    @restore_spent.setter
    def restore_spent(self, value: bool) -> None: ...

    def require_authenticated_root_context(self, provider, preflight) -> None: ...


class ProspectiveRestoreProgram:
    """Concrete real-provider restore algorithm with a default-inert Root seam.

    Construction accepts explicit existing provider/context references and
    performs no provider construction, credential access or request. The actual
    Root admission/qualification capability is deliberately not supplied by this
    SOURCE package. The separate fixture factory exercises the SAME algorithm.
    """

    def __init__(
        self,
        provider: BetaPublisherProvider | None = None,
        context: RootOperatorContext | None = None,
    ):
        self.provider, self.context = provider, context

    def restore_retained_version(self, identity, version, preflight, *, key):
        if not DISPATCH_ENABLED:
            raise OperatorRefused("prospective_restore_dispatch_disabled")
        provider, context = self.provider, self.context
        if not isinstance(provider, BetaPublisherProvider) or context is None:
            raise OperatorRefused("genuine_root_provider_and_context_required")
        context.require_authenticated_root_context(provider, preflight)
        if (
            provider.before_request != context.fence.before
            or provider.after_request != context.fence.after
        ):
            raise OperatorRefused("root_exact_request_boundary_not_installed")
        return _restore_algorithm(provider, context, identity, version, preflight, key=key)


class _InventedRestoreContext:
    """Source fixture state only; never implements a genuine Root grant."""

    def __init__(self, provider: ProspectiveSourceProvider):
        self.provider = provider
        self.inputs = provider._source_inputs
        self.retained = provider._source_retained
        self.preflight = provider._source_preflight
        self.fence = provider._source_fence

    @property
    def restore_spent(self):
        return self.provider._source_restore_spent

    @restore_spent.setter
    def restore_spent(self, value):
        self.provider._source_restore_spent = value

    def require_authenticated_root_context(self, provider, preflight):
        raise OperatorRefused("invented_fixture_has_no_actual_root_authority")


class SourceHarnessFactory:
    """The only supported fake-wire construction and algorithm rehearsal seam."""

    @staticmethod
    def create(inputs, io, fence):
        return ProspectiveSourceProvider(inputs, io, fence)

    @staticmethod
    def restore(provider, identity, version, preflight, *, key):
        if (
            type(provider) is not ProspectiveSourceProvider
            or type(provider._transport) is not InventedProviderIO
        ):
            raise OperatorRefused("source_harness_exact_invented_provider_required")
        return _restore_algorithm(
            provider, _InventedRestoreContext(provider), identity, version, preflight, key=key
        )


def _restore_algorithm(
    provider, context: RootOperatorContext, identity, version, preflight, *, key
):
    """One nonforced retained restore through the real inherited primitives."""
    if not provider._session_lock.acquire(blocking=False):
        raise OperatorRefused("source_concurrent_restore_refused")
    try:
        context.fence.check()
        retained = context.retained
        if (
            retained is None
            or context.restore_spent
            or provider._closed
            or type(preflight) is not SourceClosedPreflight
            or preflight is not context.preflight
            or identity != retained["identity"]
            or version != retained["version"]
            or preflight.source_pins != context.inputs.source_pins
            or preflight.worker_id != identity["id"]
            or preflight.retained_version_id != version["id"]
            or preflight.retained_module_sha2_256 != version["moduleSha2_256"]
            or preflight.retained_configuration_sha2_256 != retained["configuration"]
            or provider._clock() < preflight.observed_at
            or provider._clock() >= preflight.expires_at
            or key != "restore:deploy"
        ):
            raise OperatorRefused("source_exact_retained_closed_restore_refused")
        provider._version(identity, version)
        # One source-owned intent is spent before any nested request. A lost
        # read or POST cannot acquire another attempt or recreate old receipts.
        context.restore_spent = True
        context.fence.deadline = min(context.fence.deadline, preflight.expires_at)
        provider.inspect_version(identity, version, key=key + ":version")
        provider._observe(identity, key=key + ":before")
        context.fence.check()
        if provider._clock() >= preflight.expires_at:
            raise OperatorRefused("source_restore_preflight_expired")
        result = provider._request(
            "POST",
            provider._worker(identity["name"]) + "/deployments",
            {
                "strategy": "percentage",
                "versions": [{"version_id": version["id"], "percentage": 100}],
            },
            key=key,
        )
        deployment = provider._deployment(result, identity, version)
        provider._deployments[deployment["id"]] = deployment.copy()
        provider._observe(identity, key=key + ":after")
        context.fence.check()
        return deployment.copy()
    finally:
        provider._session_lock.release()


class _RequestFence:
    """Match each inherited _request admission against the full SOURCE leaves."""

    def __init__(self, inputs, leaves, io, root, max_requests, deadline, expire_after):
        self.inputs, self.leaves, self.io, self.root = inputs, leaves, io, root
        self.max_requests, self.deadline, self.expire_after = max_requests, deadline, expire_after
        self.position = 0
        self.keys: list[str] = []
        self.mutations = 0
        self.pending = False
        self.closed = False
        self.last_clock = io.now

    def check(self):
        _validate(self.inputs, self.root)
        now = self.io.now
        if not math.isfinite(now) or now < self.last_clock or now >= self.deadline or self.closed:
            raise OperatorRefused("synthetic_current_window_or_latch")
        self.last_clock = now

    def before(self, key, mutation, metadata):
        self.check()
        if self.pending or self.position >= len(self.leaves) or self.position >= self.max_requests:
            raise OperatorRefused("synthetic_exact_leaf_budget_or_replay")
        expected = self.leaves[self.position]
        if (
            key != expected.key
            or mutation != expected.mutation
            or metadata["method"] != expected.method
            or metadata["path"] != expected.path
        ):
            raise OperatorRefused("synthetic_nested_request_identity_mismatch")
        # Reserve before dispatch. An unknown acknowledgement leaves this leaf
        # spent and pending, with no replay, restore or cleanup in this session.
        self.position += 1
        self.keys.append(key)
        self.mutations += int(mutation)
        self.pending = True
        self.check()

    def after(self, key, _receipt):
        if not self.pending or key != self.keys[-1]:
            self.closed = True
            raise OperatorRefused("synthetic_receipt_identity_mismatch")
        if self.expire_after == self.position:
            self.io.now = self.deadline
        self.check()
        self.pending = False


def exercise_synthetic(
    fragment: str = "temporary",
    *,
    inputs: OperatorInputs | None = None,
    root: Path = ROOT,
    fault: str | None = None,
    max_requests: int = 32,
    deadline: float = 100,
    expire_after: int | None = None,
) -> SyntheticReceipt:
    """Invoke inherited provider code against source-owned invented memory only.

    This is a finite test harness, not an adapter factory. No transport, provider,
    credential or authority callback is accepted. Unknown results stop the whole
    fragment; an ordinary closed authenticated check has no fake substitute.
    """
    if fragment not in ("temporary", "stop", "cleanup", "restore", "restore_refusal"):
        raise OperatorRefused("synthetic_fragment_not_supported")
    if (
        type(max_requests) is not int
        or not 1 <= max_requests <= 32
        or type(deadline) not in (int, float)
        or not math.isfinite(deadline)
        or deadline <= 10
        or (expire_after is not None and (type(expire_after) is not int or expire_after < 1))
    ):
        raise OperatorRefused("synthetic_finite_budget_required")
    inputs = fixture_inputs(root) if inputs is None else inputs
    steps = build_operator_steps(inputs, root=root)
    by_name = {step.name: step for step in steps}
    pins = dict(inputs.source_pins)
    leaves = [
        RequestLeaf(
            "fixture:database",
            "POST",
            "/d1/database",
            BOUNDARY,
            pins[BOUNDARY],
            True,
            "invented-database",
        ),
        RequestLeaf(
            "fixture:worker",
            "POST",
            "/workers/workers",
            IDENTITY,
            pins[IDENTITY],
            True,
            inputs.worker_id,
        ),
    ]
    names = [
        "retained.capture",
        "temporary.create",
        "temporary.version",
        "temporary.deploy",
        "temporary.deployment",
    ]
    if fragment in ("stop", "cleanup", "restore"):
        names += ["stop.disable", "stop.endpoint"]
    if fragment == "restore":
        names += [
            "restore.deploy",
            "restore.version",
            "restore.deployment",
            "restore.endpoint",
            "restore.origin",
        ]
    if fragment == "cleanup":
        names += ["cleanup.delete", "cleanup.absence"]
    for name in names:
        leaves.extend(by_name[name].leaves)
    io = InventedProviderIO(inputs, fault)
    fence = _RequestFence(inputs, tuple(leaves), io, root, max_requests, deadline, expire_after)
    provider = SourceHarnessFactory.create(inputs, io, fence)
    outcome = "synthetic_complete"
    preflight: SourceClosedPreflight | None = None
    try:
        database = provider.create_database(inputs.worker_name + "-db", key="fixture:database")
        identity = provider.create_worker(inputs.worker_name, key="fixture:worker")
        module = b"invented immutable module; never provider bundled"
        digest = hashlib.sha256(module).hexdigest()
        variables = {
            "PROBE_ENABLED": "1",
            "PROBE_SCOPE": "publisher-disposable-v1",
            "PROBE_ARTIFACT_SHA2_256": digest,
            "PROBE_RUN_ID": "e" * 64,
            "PROBE_RESOURCE_ID": database["uuid"],
            "PROBE_EXPIRES_AT": "2026-10-24T00:01:00Z",
            "PROBE_SCENARIO": "happy",
        }
        projection = {
            "main_module": "worker.js",
            "compatibility_date": "2026-10-16",
            "compatibility_flags": ["nodejs_compat"],
            "observability": {"enabled": False},
            "logpush": False,
            "bindings": [
                {"name": "DB", "type": "d1", "id": database["uuid"]},
                {"name": "PROBE_ACCESS_TOKEN", "type": "secret_text"},
                *[
                    {"name": name, "type": "plain_text", "text": value}
                    for name, value in sorted(variables.items())
                ],
            ],
        }
        retained_module = b"invented exact retained module; not temporary"
        io.seed_retained_fixture(retained_module, projection)
        retained = provider.capture_retained_version(
            identity,
            retained_module,
            hashlib.sha256(retained_module).hexdigest(),
            projection,
            key="retained:capture",
        )
        version = provider.create_version(
            identity, module, digest, projection, "d" * 64, key="temporary:create"
        )
        if version["id"] != inputs.temporary_version_id:
            raise OperatorRefused("synthetic_returned_version_differs_from_bound_graph")
        provider.inspect_version(identity, version, key="temporary:version")
        deployment = provider.deploy_version(identity, version, key="temporary:deploy")
        provider.inspect_deployment(identity, version, deployment, key="temporary:deployment")
        if fragment == "restore_refusal":
            # An attempted second deployment is rejected by the inherited source
            # before any nested request. This does not pretend the temporary
            # version is a retained version or create retained ownership facts.
            before = provider.calls
            try:
                provider.deploy_version(identity, version, key="restore:deploy")
            except ProviderError as error:
                if str(error) != "worker_deployment_replay_refused" or provider.calls != before:
                    raise
                outcome = "synthetic_existing_provider_restore_gap"
            else:
                raise AssertionError("second_deployment_unexpectedly_admitted")
        if fragment in ("stop", "cleanup", "restore"):
            receipt = provider.disable_worker(identity, key="stop:disable")
            if (
                receipt.get("disableAcknowledged") is not True
                or receipt.get("drainProven") is not False
            ):
                raise OperatorRefused("synthetic_disable_does_not_establish_drain")
            preflight = provider.source_closed_preflight(identity, version, key="stop:endpoint")
        if fragment == "restore":
            if preflight is None:
                raise OperatorRefused("synthetic_source_preflight_absent")
            restored = provider.restore_retained_version(
                identity, retained, preflight, key="restore:deploy"
            )
            provider.inspect_version(identity, retained, key="restore:version")
            provider.inspect_deployment(identity, retained, restored, key="restore:deployment")
            if provider.inspect_endpoint(identity, key="restore:endpoint")["enabled"] is not False:
                raise OperatorRefused("synthetic_restore_endpoint_drift")
            provider.assert_endpoint(identity, inputs.endpoint, key="restore:origin")
        if fragment == "cleanup":
            provider.delete_worker(identity, key="cleanup:delete")
            if provider.inspect_worker(identity, key="cleanup:absence") is not None:
                raise OperatorRefused("synthetic_exact_absence_unverified")
        fence.check()
        if fence.pending or fence.position != len(leaves):
            raise OperatorRefused("synthetic_incomplete_exact_leaf_sequence")
    except (ProviderError, OperatorRefused) as error:
        fence.closed = True
        outcome = (
            "synthetic_unknown_no_replay"
            if isinstance(error, ProviderUnknown)
            else "synthetic_refused"
        )
    return SyntheticReceipt(
        fragment,
        provider.calls,
        fence.mutations,
        provider.request_bytes,
        provider.response_bytes,
        tuple(fence.keys),
        outcome,
    )
