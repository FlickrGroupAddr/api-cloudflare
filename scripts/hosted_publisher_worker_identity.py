"""Bounded Workers Beta identity adapter, prepared offline and unselected.

Official create/get/edit/delete contracts reviewed 2026-10-17:
https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/

Only an acknowledged creation supplies identity. Unknown creation cannot be
replayed or recovered by name. ID addressing is ordinary documented identity,
not a conditional write or a guarantee about concurrent external modification.
No versions, deployments, routes, discovery or token operations are implemented.
The omitted/direct built-in transport refuses requests pending owner selection.
Injected callables are trusted test code, not a network sandbox or authority gate.
The existing provider owns HTTP byte/time budgets, hooks and unknown latching.
"""

from __future__ import annotations

import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Never

from scripts.hosted_publisher_provider import (
    CloudflareProvider,
    Limits,
    ProviderError,
    ProviderUnknown,
    https_transport,
)

__all__ = ["BetaWorkerProvider", "Limits", "ProviderError", "ProviderUnknown"]


class BetaWorkerProvider:
    """Exact creation-returned identity only; no name fallback or retry.

    Injected transports are an offline test seam, never provider qualification.
    Omitted/direct built-in transport refuses requests; arbitrary callables can
    perform I/O and must remain trusted offline fixtures. This module does not establish
    durable intent, consent, drain, atomic collision behavior or CAS.
    """

    live_execution_allowed = False
    provider_qualified = False

    def __init__(
        self,
        account,
        token,
        worker_names,
        *,
        limits=None,
        transport=None,
        monotonic=time.monotonic,
        before_request=None,
        after_request=None,
    ):
        self._status = None
        self._concrete = transport is None or transport is https_transport

        def record_response(key, metadata):
            self._status = metadata["status"]
            if after_request is not None:
                after_request(key, metadata)

        # Composition deliberately exposes none of the unrelated D1 methods.
        self._provider = CloudflareProvider(
            account,
            token,
            worker_names,
            worker_names,
            limits=limits,
            transport=transport,
            monotonic=monotonic,
            before_request=before_request,
            after_request=record_response,
        )
        self._identities = {}
        self._created_names = set()
        self._lock = threading.Lock()

    @contextmanager
    def _operation(self):
        if self._concrete:
            raise ProviderError("workers_beta_not_selected")
        if not self._lock.acquire(blocking=False):
            raise ProviderError("worker_concurrent_operation_forbidden")
        try:
            yield
        finally:
            self._lock.release()

    def _call(self, method, path, *, key, body=None):
        self._status = None
        return self._provider._request(method, path, body, key=key)

    def _unknown(self) -> Never:
        self._provider._closed = True
        raise ProviderUnknown("worker_identity_or_outcome_unknown")

    def _config(self, name):
        return {
            "name": name,
            "logpush": False,
            "observability": {"enabled": False},
            "subdomain": {"enabled": False, "previews_enabled": False},
            "tags": [],
            "tail_consumers": [],
        }

    def _path(self, identity):
        if (
            not isinstance(identity, dict)
            or set(identity) != {"id", "name", "created_on"}
            or not isinstance(identity.get("id"), str)
            or not re.fullmatch(r"[a-f0-9]{32}", identity["id"])
            or identity["id"] == "0" * 32
            or self._identities.get(identity["id"]) != identity
        ):
            raise ProviderError("worker_outside_created_identity_scope")
        return "/workers/workers/" + identity["id"]

    def _validate(self, result, name, expected=None, *, allow_enabled=False):
        if not isinstance(result, dict):
            self._unknown()
        identity = {k: result.get(k) for k in ("id", "name", "created_on")}
        try:
            if not isinstance(identity["created_on"], str):
                self._unknown()
            created = datetime.fromisoformat(identity["created_on"])
            valid_date = created.utcoffset() is not None
        except TypeError, ValueError:
            valid_date = False
        if (
            not isinstance(identity["id"], str)
            or not re.fullmatch(r"[a-f0-9]{32}", identity["id"])
            or identity["id"] == "0" * 32
            or identity["name"] != name
            or not valid_date
            or (expected is not None and identity != expected)
        ):
            self._unknown()
        config = self._config(name)
        if (
            result.get("logpush") is not False
            or result.get("tags") != []
            or result.get("tail_consumers") != []
            or not isinstance(result.get("observability"), dict)
            or result["observability"].get("enabled") is not False
            or not isinstance(result.get("subdomain"), dict)
            or any(
                not isinstance(result["subdomain"].get(k), bool)
                or (not allow_enabled and result["subdomain"][k] is not v)
                for k, v in config["subdomain"].items()
            )
        ):
            self._unknown()
        references = result.get("references")
        if (
            not isinstance(references, dict)
            or set(references)
            != {"dispatch_namespace_outbounds", "domains", "durable_objects", "queues", "workers"}
            or any(value != [] for value in references.values())
        ):
            self._unknown()
        return identity

    def create_worker(self, name, *, key):
        with self._operation():
            if name not in self._provider.worker_names or name in self._created_names:
                raise ProviderError("worker_creation_refused")
            # Consumed before dispatch: even unknown outcomes never repeat create.
            self._created_names.add(name)
            result = self._call("POST", "/workers/workers", key=key, body=self._config(name))
            identity = self._validate(result, name)
            if identity["id"] in self._identities:
                self._unknown()
            self._identities[identity["id"]] = identity.copy()
            return identity.copy()

    def _read(self, identity, *, key, allow_enabled=False):
        result = self._call("GET", self._path(identity), key=key)
        if result is None:
            if self._status != 404:
                self._unknown()
            return None
        return self._validate(
            result, identity["name"], identity, allow_enabled=allow_enabled
        ).copy()

    def inspect_worker(self, identity, *, key):
        with self._operation():
            return self._read(identity, key=key)

    def disable_worker(self, identity, *, key):
        with self._operation():
            path = self._path(identity)
            if self._read(identity, key=key + ":identity", allow_enabled=True) is None:
                return self._receipt(absent=True)
            result = self._call("PATCH", path, key=key, body=self._config(identity["name"]))
            self._validate(result, identity["name"], identity)
            return self._receipt(disableAcknowledged=True, drainProven=False)

    def delete_worker(self, identity, *, key):
        with self._operation():
            path = self._path(identity)
            if self._read(identity, key=key + ":identity") is None:
                return self._receipt(absent=True)
            # No force flag. This read then delete sequence is not CAS.
            self._call("DELETE", path, key=key)
            if self._status == 404:
                return self._receipt(absent=True)
            return self._receipt(deletionAcknowledged=True, absenceVerified=False)

    @staticmethod
    def _receipt(**values):
        return {**values, "liveExecutionAllowed": False, "providerQualified": False}
