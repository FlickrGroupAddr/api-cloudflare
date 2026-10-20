"""Offline-selected Beta/Scripts publisher composition; concrete execution disabled.

Official API contracts reviewed 2026-10-18:
https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/subresources/versions/methods/create/
https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/subresources/versions/methods/get/
https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/

Versions use immutable Worker IDs. Deployment uses a name under the explicit
exclusive-owner assumption, bracketed by immutable identity observations. These
reads are drift checks, not CAS or exclusion of an external management writer.
All requests share the inherited budget, deadline, hooks and unknown latch.
"""

from __future__ import annotations

import base64
import copy
import re
import threading
from datetime import datetime
from functools import wraps

from scripts.hosted_publisher_provider import (
    CloudflareProvider,
    ProviderError,
    _digest,
    _uuid,
    validate_worker_projection,
)
from scripts.hosted_publisher_worker_identity import BetaWorkerProvider


def _date(value):
    try:
        return isinstance(value, str) and datetime.fromisoformat(value).utcoffset() is not None
    except ValueError:
        return False


def deployment_diagnostic(value):
    """Return only closed metadata; no provider values or exception prose."""
    if (
        type(value) is not dict
        or any(type(key) is not str for key in value)
        or set(value) != {"stage", "field", "status"}
        or type(value["stage"]) is not str
        or value["stage"]
        not in {
            "preflight",
            "version_readback",
            "before_identity",
            "deployment_admission",
            "deployment_response",
            "response_validation",
            "receipt_registration",
            "post_identity_admission",
            "post_identity_response",
            "post_identity_validation",
        }
        or type(value["field"]) is not str
        or value["field"] not in {"none", "result", "id", "created_on", "strategy", "versions"}
        or type(value["status"]) is not str
        or value["status"] not in {"not_checked", "missing", "invalid"}
    ):
        return None
    return value.copy()


_DEPLOYMENT_SHAPE_FIELDS = (
    "result",
    "id",
    "created_on",
    "strategy",
    "versions",
    "metadata",
    "metadata.created_on",
)
_SHAPE_TYPES = {"null", "boolean", "number", "string", "array", "object", "other"}


def deployment_response_shape(value):
    """Validate a separate closed supplement; never retain values or arbitrary keys."""
    if (
        type(value) is not dict
        or any(type(key) is not str for key in value)
        or set(value) != set(_DEPLOYMENT_SHAPE_FIELDS)
    ):
        return None
    for field in _DEPLOYMENT_SHAPE_FIELDS:
        allowed = _SHAPE_TYPES if field == "result" else _SHAPE_TYPES | {"missing", "unavailable"}
        if type(value[field]) is not str or value[field] not in allowed:
            return None
    if value["result"] != "object":
        if any(value[field] != "unavailable" for field in _DEPLOYMENT_SHAPE_FIELDS[1:]):
            return None
    else:
        if any(value[field] == "unavailable" for field in _DEPLOYMENT_SHAPE_FIELDS[1:-1]):
            return None
        nested = value["metadata.created_on"]
        if value["metadata"] == "object" and nested == "unavailable":
            return None
        if value["metadata"] != "object" and nested != "unavailable":
            return None
    return value.copy()


def _response_shape(result):
    def classify(value):
        return {
            type(None): "null",
            bool: "boolean",
            int: "number",
            float: "number",
            str: "string",
            list: "array",
            dict: "object",
        }.get(type(value), "other")

    def field_shape(container, field):
        if type(container) is not dict:
            return "unavailable"
        return classify(container[field]) if field in container else "missing"

    shape = {"result": classify(result)}
    for field in _DEPLOYMENT_SHAPE_FIELDS[1:-1]:
        shape[field] = field_shape(result, field)
    metadata = result.get("metadata") if type(result) is dict else None
    shape["metadata.created_on"] = field_shape(metadata, "created_on")
    return shape


def _exclusive(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if not self._session_lock.acquire(blocking=False):
            raise ProviderError("worker_concurrent_operation_forbidden")
        try:
            return method(self, *args, **kwargs)
        finally:
            self._session_lock.release()

    return wrapped


class BetaPublisherProvider(CloudflareProvider):
    """One finite provider session; accepted source direction grants no I/O consent."""

    live_execution_allowed = False
    provider_qualified = False
    beta_identity = True
    selected_strategy = "beta-synthetic-disposal-v1"

    def __init__(
        self, account, token, worker_names, database_names, *, exclusive_owner=False, **kwargs
    ):
        super().__init__(account, token, worker_names, database_names, **kwargs)
        if exclusive_owner is not True:
            raise ProviderError("exclusive_worker_management_required")
        self._session_lock = threading.RLock()
        self.identity = BetaWorkerProvider(account, token, self.worker_names, shared_provider=self)
        self._versions = {}
        self._version_intents = set()
        self._deployments = {}
        self._deployment_intents = set()
        self.last_deployment_diagnostic = None
        self.last_deployment_response_shape = None
        self._deployment_diagnostic_active = False
        self._deployment_request_key = None

    def _deployment_stage(self, stage, field="none", status="not_checked"):
        if self._deployment_diagnostic_active:
            self.last_deployment_diagnostic = {"stage": stage, "field": field, "status": status}

    def _deployment_rejection_shape(self, result):
        if self._deployment_diagnostic_active:
            self.last_deployment_response_shape = _response_shape(result)

    def _guard(self):
        if self._concrete:
            raise ProviderError("workers_beta_not_selected")

    def _request(self, method, path, body=None, *, key, media="application/json", raw=False):
        self._guard()
        stage = None
        request_key = self._deployment_request_key
        if self._deployment_diagnostic_active:
            assert request_key is not None
            if key == request_key:
                stage = "deployment"
            elif key == request_key + ":after":
                stage = "post_identity"
        if stage is not None:
            self._deployment_stage(stage + "_admission")
        calls = self.calls
        try:
            result = super()._request(method, path, body, key=key, media=media, raw=raw)
        except Exception:
            if stage is not None and self.calls > calls:
                self._deployment_stage(stage + "_response")
            raise
        if stage == "post_identity":
            self._deployment_stage("post_identity_validation")
        return result

    def set_endpoint(self, name, enabled, *, key):
        raise ProviderError("worker_immutable_identity_required")

    def inspect_module(self, name, sha2, *, key):
        raise ProviderError("worker_version_identity_required")

    @_exclusive
    def create_worker(self, name, *, key):
        return self.identity.create_worker(name, key=key)

    @_exclusive
    def inspect_worker(self, identity, *, key):  # pyright: ignore[reportIncompatibleMethodOverride]
        with self.identity._operation():
            return self.identity._read(identity, key=key, allow_enabled=True)

    @_exclusive
    def disable_worker(self, identity, *, key):
        return self.identity.disable_worker(identity, key=key)

    @_exclusive
    def delete_worker(self, identity, *, key):  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.identity.delete_worker(identity, key=key)

    @_exclusive
    def restore_owned_resources(
        self, database=None, worker=None, version=None, projection=None, deployment=None
    ):
        """Register authenticated durable creation receipts for cleanup only.

        Caller must authenticate journal/source/consent first. No discovery or
        name adoption happens here. Restoration consumes provisioning intents.
        """
        self._guard()
        if database is not None:
            self._database(database)
            known = self._databases.get(database["uuid"])
            if known is not None and known != database:
                raise ProviderError("database_identity_drift")
            self._databases[database["uuid"]] = database.copy()
            self._created_names.add(database["name"])
        if worker is not None:
            self.identity.restore_owned_identity(worker)
            self._version_intents.add(worker["id"])
            self._deployment_intents.add(worker["id"])
        if version is not None:
            if (
                worker is None
                or projection is None
                or not isinstance(version, dict)
                or set(version) != {"id", "workerId", "moduleSha2_256"}
                or not _uuid(version["id"])
                or version["workerId"] != worker["id"]
                or not isinstance(version["moduleSha2_256"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", version["moduleSha2_256"])
            ):
                raise ProviderError("worker_restore_version_invalid")
            validate_worker_projection(b"", _digest(b""), projection, "a" * 64)
            configuration = {
                k: copy.deepcopy(projection[k])
                for k in ("main_module", "compatibility_date", "compatibility_flags", "bindings")
            }
            configuration["bindings"] = self._bindings(configuration["bindings"])
            db = next(b["database_id"] for b in configuration["bindings"] if b["type"] == "d1")
            if db not in self._databases:
                raise ProviderError("worker_database_not_created")
            self._versions[version["id"]] = {
                "configuration": configuration,
                "id": version["id"],
                "receipt": version.copy(),
            }
        if deployment is not None:
            if (
                version is None
                or not isinstance(deployment, dict)
                or set(deployment) != {"id", "workerId", "versionId", "created_on"}
                or not _uuid(deployment["id"])
                or deployment["workerId"] != version["workerId"]
                or deployment["versionId"] != version["id"]
                or not _date(deployment["created_on"])
            ):
                raise ProviderError("worker_restore_deployment_invalid")
            self._deployments[deployment["id"]] = deployment.copy()

    def _observe(self, identity, *, key):
        if self.inspect_worker(identity, key=key) is None:
            self._unknown("owned_worker_absent")

    def _version(self, identity, version):
        self.identity._path(identity)
        if (
            not isinstance(version, dict)
            or set(version) != {"id", "workerId", "moduleSha2_256"}
            or not _uuid(version.get("id"))
            or version.get("workerId") != identity["id"]
            or self._versions.get(version["id"], {}).get("receipt") != version
        ):
            raise ProviderError("worker_version_outside_created_scope")
        return self._versions[version["id"]]

    @staticmethod
    def _bindings(bindings):
        """Canonicalize documented Beta D1 spelling; secrets remain redacted."""
        if not isinstance(bindings, list):
            raise ProviderError("worker_version_bindings_invalid")
        result = []
        for value in bindings:
            if not isinstance(value, dict):
                raise ProviderError("worker_version_bindings_invalid")
            binding = value.copy()
            if binding.get("type") == "secret_text":
                binding.pop("text", None)
            if binding.get("type") == "d1" and "id" in binding:
                if "database_id" in binding and binding["id"] != binding["database_id"]:
                    raise ProviderError("worker_version_database_drift")
                binding["database_id"] = binding.pop("id")
            result.append(binding)
        if any(not isinstance(b.get("name"), str) for b in result):
            raise ProviderError("worker_version_bindings_invalid")
        if len({b["name"] for b in result}) != len(result):
            raise ProviderError("worker_version_bindings_invalid")
        return sorted(result, key=lambda b: b["name"])

    def _validate_version(self, result, expected, *, include_modules):
        if not isinstance(result, dict) or not _uuid(result.get("id")):
            self._unknown("worker_version_identity_unknown")
        if not _date(result.get("created_on")):
            self._unknown("worker_version_identity_unknown")
        if expected.get("id") is not None and result["id"] != expected["id"]:
            self._unknown("worker_version_identity_drift")
        configuration = expected["configuration"]
        if any(result.get(k) != v for k, v in configuration.items() if k != "bindings"):
            self._unknown("worker_version_configuration_drift")
        try:
            bindings_match = self._bindings(result.get("bindings")) == configuration["bindings"]
        except ProviderError:
            bindings_match = False
        if not bindings_match:
            self._unknown("worker_version_binding_drift")
        # No extra capability-bearing configuration may appear by default.
        for field in (
            "assets",
            "containers",
            "exports",
            "migrations",
            "migration_tag",
            "package_dependencies",
            "placement",
            "limits",
        ):
            if result.get(field) not in (None, {}, []):
                self._unknown("worker_version_unexpected_configuration")
        # CacheW can provision a cloudflare.app zone. This finite fixture
        # explicitly disables it; absent optional readback fields add no setting.
        cache = result.get("cache_options")
        if cache is not None and (
            not isinstance(cache, dict)
            or set(cache) - {"enabled", "cross_version_cache"}
            or cache.get("enabled") is not False
            or ("cross_version_cache" in cache and cache["cross_version_cache"] is not False)
        ):
            self._unknown("worker_version_unapproved_cache")
        if result.get("usage_model") not in (None, "standard"):
            self._unknown("worker_version_unexpected_usage_model")
        if include_modules:
            modules = result.get("modules")
            try:
                if (
                    not isinstance(modules, list)
                    or len(modules) != 1
                    or set(modules[0]) != {"name", "content_type", "content_base64"}
                    or modules[0]["name"] != "worker.js"
                    or modules[0]["content_type"] != "application/javascript+module"
                ):
                    raise ValueError
                raw = base64.b64decode(modules[0]["content_base64"], validate=True)
                if _digest(raw) != expected["receipt"]["moduleSha2_256"]:
                    raise ValueError
            except TypeError, ValueError, KeyError:
                self._unknown("worker_version_module_drift")
        return result["id"]

    @_exclusive
    def create_version(self, identity, module, sha2, metadata, access_token, *, key):
        self._guard()
        path = self.identity._path(identity)
        private = validate_worker_projection(module, sha2, metadata, access_token)
        db = next(b["id"] for b in metadata["bindings"] if b["type"] == "d1")
        if db not in self._databases:
            raise ProviderError("worker_database_not_created")
        if identity["id"] in self._version_intents:
            raise ProviderError("worker_version_replay_refused")
        configuration = {
            k: copy.deepcopy(private[k])
            for k in ("main_module", "compatibility_date", "compatibility_flags", "bindings")
        }
        configuration["bindings"] = self._bindings(configuration["bindings"])
        modules = [
            {
                "name": "worker.js",
                "content_type": "application/javascript+module",
                "content_base64": base64.b64encode(module).decode("ascii"),
            }
        ]
        payload = {
            **configuration,
            "modules": modules,
            "cache_options": {"enabled": False, "cross_version_cache": False},
        }
        payload["bindings"] = [
            {**b, "text": access_token} if b["type"] == "secret_text" else b.copy()
            for b in configuration["bindings"]
        ]
        self._version_intents.add(identity["id"])
        result = self._request("POST", path + "/versions?deploy=false", payload, key=key)
        expected = {"configuration": configuration, "modules": modules}
        version_id = self._validate_version(result, expected, include_modules=False)
        if version_id in self._versions:
            self._unknown("worker_version_identity_reused")
        receipt = {"id": version_id, "workerId": identity["id"], "moduleSha2_256": sha2}
        self._versions[version_id] = {**expected, "id": version_id, "receipt": receipt.copy()}
        return receipt

    @_exclusive
    def inspect_version(self, identity, version, *, key):
        self._guard()
        expected = self._version(identity, version)
        result = self._request(
            "GET",
            self.identity._path(identity) + "/versions/" + version["id"] + "?include=modules",
            key=key,
        )
        self._validate_version(result, expected, include_modules=True)
        return version.copy()

    def _deployment(self, result, identity, version, expected=None):
        if not isinstance(result, dict):
            self._deployment_stage("response_validation", "result", "invalid")
            self._deployment_rejection_shape(result)
            self._unknown("worker_deployment_unknown_or_drift")
        for field, valid in (
            ("id", _uuid(result.get("id"))),
            ("created_on", _date(result.get("created_on"))),
            ("strategy", result.get("strategy") == "percentage"),
            (
                "versions",
                result.get("versions") == [{"version_id": version["id"], "percentage": 100}],
            ),
        ):
            if not valid:
                self._deployment_stage(
                    "response_validation", field, "invalid" if field in result else "missing"
                )
                self._deployment_rejection_shape(result)
                self._unknown("worker_deployment_unknown_or_drift")
        receipt = {
            "id": result["id"],
            "workerId": identity["id"],
            "versionId": version["id"],
            "created_on": result["created_on"],
        }
        if expected is not None and receipt != expected:
            self._unknown("worker_deployment_identity_drift")
        return receipt

    @_exclusive
    def deploy_version(self, identity, version, *, key):
        self.last_deployment_diagnostic = None
        self.last_deployment_response_shape = None
        self._deployment_diagnostic_active = True
        self._deployment_request_key = key
        try:
            return self._deploy_version(identity, version, key=key)
        finally:
            self._deployment_diagnostic_active = False
            self._deployment_request_key = None

    def _deploy_version(self, identity, version, *, key):
        self._deployment_stage("preflight")
        self._guard()
        self._version(identity, version)
        if identity["id"] in self._deployment_intents:
            raise ProviderError("worker_deployment_replay_refused")
        self._deployment_stage("version_readback")
        self.inspect_version(identity, version, key=key + ":version")
        self._deployment_stage("before_identity")
        self._observe(identity, key=key + ":before")
        self._deployment_intents.add(identity["id"])
        result = self._request(
            "POST",
            self._worker(identity["name"]) + "/deployments",
            {
                "strategy": "percentage",
                "versions": [{"version_id": version["id"], "percentage": 100}],
            },
            key=key,
        )
        self._deployment_stage("response_validation")
        receipt = self._deployment(result, identity, version)
        self._deployment_stage("receipt_registration")
        self._deployments[receipt["id"]] = receipt.copy()
        self._deployment_stage("post_identity_admission")
        self._observe(identity, key=key + ":after")
        self.last_deployment_diagnostic = None
        self.last_deployment_response_shape = None
        return receipt

    @_exclusive
    def inspect_deployment(self, identity, version, deployment, *, key):
        self._guard()
        self._version(identity, version)
        if (
            not isinstance(deployment, dict)
            or self._deployments.get(deployment.get("id")) != deployment
        ):
            raise ProviderError("worker_deployment_outside_created_scope")
        self._observe(identity, key=key + ":before")
        path = self._worker(identity["name"]) + "/deployments"
        current = self._request("GET", path + "?page=1&per_page=1", key=key + ":current")
        if not isinstance(current, dict) or not isinstance(current.get("deployments"), list):
            self._unknown("worker_current_deployment_unknown")
        deployments = current["deployments"]
        if len(deployments) != 1:
            self._unknown("worker_current_deployment_unknown")
        self._deployment(deployments[0], identity, version, deployment)
        self._observe(identity, key=key + ":after")
        return deployment.copy()

    @_exclusive
    def enable_worker(self, identity, *, key):
        self._guard()
        self._observe(identity, key=key + ":identity")
        config = self.identity._config(identity["name"])
        config["subdomain"] = {"enabled": True, "previews_enabled": False}
        result = self._request("PATCH", self.identity._path(identity), config, key=key)
        self.identity._validate(result, identity["name"], identity, allow_enabled=True)
        if any(result["subdomain"].get(k) is not v for k, v in config["subdomain"].items()):
            self._unknown("worker_endpoint_enable_unknown")
        return config["subdomain"].copy()

    @_exclusive
    def inspect_endpoint(self, identity, *, key):  # pyright: ignore[reportIncompatibleMethodOverride]
        self._guard()
        result = self._request("GET", self.identity._path(identity), key=key)
        self.identity._validate(result, identity["name"], identity, allow_enabled=True)
        if result["subdomain"].get("previews_enabled") is not False:
            self._unknown("worker_preview_endpoint_drift")
        return {k: result["subdomain"][k] for k in ("enabled", "previews_enabled")}

    @_exclusive
    def assert_endpoint(self, identity, endpoint, *, key):
        """Resolve the account suffix explicitly; never guess or adopt a Worker."""
        self._guard()
        worker = self._request("GET", self.identity._path(identity), key=key + ":identity")
        self.identity._validate(worker, identity["name"], identity, allow_enabled=True)
        worker_url = worker["subdomain"].get("url")
        subdomain = self._request("GET", "/workers/subdomain", key=key + ":subdomain")
        if (
            not isinstance(worker_url, str)
            or worker_url != endpoint
            or not isinstance(subdomain, dict)
            or not isinstance(subdomain.get("subdomain"), str)
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain["subdomain"])
            or endpoint
            != "https://" + identity["name"] + "." + subdomain["subdomain"] + ".workers.dev"
        ):
            self._unknown("worker_endpoint_identity_drift")
        return True
