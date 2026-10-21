"""Fresh POST fixture lifecycle over the shared bounded Beta management stack.

No CLI, discovery, credential reads or effects at import. Provider construction
is inert; Lifecycle persists its journal. The caller owns current source,
consent, custody, sole-owner and finite execution admission.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from scripts.group_post_characterization import (
    PACKET,
    VERSION,
    bounded_json,
    digest,
    native_terminal,
)
from scripts.group_post_characterization import Lifecycle as ObservationValidator
from scripts.hosted_publisher_execution_provider import ExecutionBetaPublisherProvider
from scripts.hosted_publisher_provider import Limits, ProviderError, _digest
from scripts.hosted_publisher_worker_deployment import _exclusive

MANAGEMENT_PROFILE = "bounded-stateless-cookie-discard-v1"
CLEANUP_OBSERVATION_REQUEST_RESERVE = 10


class Provider(ExecutionBetaPublisherProvider):
    """Exact two-Worker/one-D1 POST scope; inherited transport and unknown latch."""

    module_name = "worker.mjs"
    selected_strategy = "post-screenshot-returned-id-v1"

    def __init__(self, account, token, run_id, *, management_profile, **kwargs):
        if not re.fullmatch(r"[a-f0-9]{24}", run_id) or run_id == "0" * 24:
            raise ProviderError("run_identity_invalid")
        if management_profile != MANAGEMENT_PROFILE:
            raise ProviderError("post_management_profile_required")
        self.run_id = run_id
        self._lifecycle_dispatch_check: Callable[[], None] | None = None
        super().__init__(
            account,
            token,
            {f"fga-post-{role}-{run_id}" for role in ("src", "recv")},
            {"fga-post-db-" + run_id},
            limits=Limits(
                calls=120,
                response_bytes=65536,
                total_response_bytes=120 * 65536,
                socket_seconds=20,
                request_seconds=20,
                total_seconds=1200,
            ),
            **kwargs,
        )
        transport = self._transport

        def guarded_transport(method, path, data, headers, timeout, cap):
            self._dispatch_guard()
            return transport(method, path, data, headers, timeout, cap)

        self._transport = guarded_transport

    def _dispatch_guard(self):
        super()._dispatch_guard()
        if self._lifecycle_dispatch_check is None:
            raise ProviderError("post_lifecycle_dispatch_guard_required")
        self._lifecycle_dispatch_check()

    def _request_locked(self, method, path, body, *, key, media, raw):
        value = super()._request_locked(method, path, body, key=key, media=media, raw=raw)
        try:
            self._dispatch_guard()
        except Exception:
            self._unknown("post_late_completion")
        return value

    def preflight_worker_absence(self, name, *, key):
        result = self._request("GET", self._worker(name) + "/settings", key=key)
        if result is not None or self.last_status != 404:
            raise ProviderError("post_worker_absence_unconfirmed")
        return True

    def _validate_names(self):
        if self.worker_names != frozenset(
            f"fga-post-{role}-{self.run_id}" for role in ("src", "recv")
        ) or self.database_names != frozenset({"fga-post-db-" + self.run_id}):
            raise ProviderError("post_scope_invalid")

    def _validate_projection(self, module, sha2, metadata, access_token):
        if module != (PACKET / "worker.mjs").read_bytes() or _digest(module) != sha2:
            raise ProviderError("post_module_invalid")
        if (
            not isinstance(metadata, dict)
            or set(metadata)
            != {
                "main_module",
                "compatibility_date",
                "compatibility_flags",
                "bindings",
                "observability",
                "logpush",
            }
            or any(
                metadata[k] != v
                for k, v in {
                    "main_module": "worker.mjs",
                    "compatibility_date": "2026-10-16",
                    "compatibility_flags": [],
                    "observability": {"enabled": False},
                    "logpush": False,
                }.items()
            )
        ):
            raise ProviderError("post_projection_invalid")
        bindings = metadata["bindings"]
        expected = {"DB", "RUN_ID", "ROLE", "SUBDOMAIN", "EXPIRES", "ACCESS", "CANARY"}
        if not isinstance(bindings, list) or len(bindings) != len(expected):
            raise ProviderError("post_bindings_invalid")
        values = {b.get("name"): b for b in bindings if isinstance(b, dict)}
        if set(values) != expected:
            raise ProviderError("post_bindings_invalid")
        db = values["DB"]
        if (
            db != {"type": "d1", "name": "DB", "id": db.get("id")}
            or db["id"] not in self._databases
        ):
            raise ProviderError("post_database_binding_invalid")
        for name in expected - {"DB"}:
            binding = values[name]
            kind = "secret_text" if name in {"ACCESS", "CANARY"} else "plain_text"
            if (
                set(binding) != {"name", "type", "text"}
                or binding["type"] != kind
                or not isinstance(binding["text"], str)
            ):
                raise ProviderError("post_binding_invalid")
        texts = {k: v["text"] for k, v in values.items() if k != "DB"}
        if (
            texts["RUN_ID"] != self.run_id
            or texts["ROLE"] not in {"source", "receiver"}
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", texts["SUBDOMAIN"])
            or not re.fullmatch(r"[0-9]{1,12}", texts["EXPIRES"])
            or not re.fullmatch(r"[a-f0-9]{64}", texts["ACCESS"])
            or texts["ACCESS"] != access_token
            or not re.fullmatch(r"SYNTHETIC-[a-f0-9]{32}", texts["CANARY"])
        ):
            raise ProviderError("post_binding_value_invalid")
        return copy.deepcopy(metadata)

    def _upload_bindings(self, private, configuration, access_token):
        # The POST fixture has two distinct secrets; do not use the publisher's
        # single-secret overlay convention.
        return self._bindings_with_secrets(private["bindings"])

    @staticmethod
    def _bindings_with_secrets(bindings):
        return [
            {("database_id" if k == "id" and b["type"] == "d1" else k): v for k, v in b.items()}
            for b in bindings
        ]

    def restore_owned_resources(self, *args, **kwargs):
        raise ProviderError("post_session_resume_forbidden")

    @_exclusive
    def delete_worker(self, identity, *, key):
        # Original POST teardown accepts an enabled owned Worker. The returned-ID
        # GET/DELETE/absence sequence uses three calls, preserving the ten-call
        # observation/teardown reserve. This is identity checking, never CAS.
        with self.identity._operation():
            path = self.identity._path(identity)
            if self.identity._read(identity, key=key + ":identity", allow_enabled=True) is None:
                return {"absent": True}
            self.identity._call("DELETE", path, key=key)
            if self.last_status == 404:
                return {"absent": True, "deletionAcknowledged": False}
            return {"deletionAcknowledged": True, "absenceVerified": False}

    @_exclusive
    def delete_database(self, identity, *, key):
        if self.inspect_database(identity, key=key + ":identity") is None:
            return {"absent": True, "deletionAcknowledged": False}
        self._request("DELETE", self._database(identity), key=key)
        if self.last_status == 404:
            return {"absent": True, "deletionAcknowledged": False}
        return {"deletionAcknowledged": True, "absenceVerified": False}

    def query(self, identity, sql, params, *, key):
        result = self._request(
            "POST", self._database(identity) + "/query", {"sql": sql, "params": params}, key=key
        )
        if (
            not isinstance(result, list)
            or not result
            or any(not isinstance(row, dict) or row.get("success") is not True for row in result)
        ):
            self._unknown("post_query_unknown")
        return result


class Lifecycle(ObservationValidator):
    """One owner and durable all-path request intents; never resume or retry.

    Observation export reuses the sealed 46-row schema validator. D1 disposal
    remains withheld unless independently supplied caller-terminal evidence is
    present; neither Worker deletion nor source inspection supplies that fact.
    """

    def __init__(self, api, directory: Path, run_id: str, owner: str, clock=time.time):
        if (
            not isinstance(api, Provider)
            or api.run_id != run_id
            or api.calls
            or api.before_request is not None
            or api.after_request is not None
        ):
            raise ProviderError("post_clean_provider_required")
        if not isinstance(owner, str) or not re.fullmatch(r"[0-9]+", owner):
            raise ProviderError("same_job_owner_required")
        self.api, self.directory, self.clock = api, directory, clock
        self.preparation_deadline = clock() + 240
        self.path = directory / "private/journal.json"
        if self.path.exists():
            raise ProviderError("journal_already_exists")
        self.journal = {
            "schemaVersion": 1,
            "planVersion": VERSION,
            "runId": run_id,
            "owner": owner,
            "accountId": api.account,
            "expiresAtUnix": int(clock()) + 1200,
            "stage": "planned",
            "calls": 0,
            "resources": [],
            "operations": [],
            "artifactSha2_256": digest(PACKET / "worker.mjs"),
        }
        self._cleanup = False
        self._target = None
        self._last_clock = clock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with (self.path.parent / "owner.json").open("x", encoding="utf-8") as stream:
            json.dump({"runId": run_id, "owner": owner, "accountId": api.account}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        self.save()
        api.before_request, api.after_request = self._before, self._after
        api._lifecycle_dispatch_check = self._dispatch_check

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(self.journal, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def _dispatch_check(self):
        now = self.clock()
        if not math.isfinite(now) or now < self._last_clock:
            raise ProviderError("post_clock_invalid")
        self._last_clock = now
        cutoff = self.journal["expiresAtUnix"]
        if not self._cleanup:
            cutoff -= 240
            if self.journal["stage"] != "ready":
                cutoff = min(cutoff, self.preparation_deadline)
        if self.api.account != self.journal["accountId"] or now + 20 >= cutoff:
            raise ProviderError("post_provider_admission_refused")
        if self.journal["calls"] <= 1 and self.api._permit.remaining_seconds() < 1200:
            raise ProviderError("post_first_effect_window_unavailable")

    def _before(self, key, mutation, metadata):
        self._dispatch_check()
        if self.journal["calls"] >= 120:
            raise ProviderError("post_provider_admission_refused")
        if not self._cleanup and self.journal["calls"] >= 120 - CLEANUP_OBSERVATION_REQUEST_RESERVE:
            raise ProviderError("post_cleanup_call_reserve_required")
        if any(operation["key"] == key for operation in self.journal["operations"]):
            raise ProviderError("post_operation_replay_refused")
        self.journal["operations"].append(
            {
                "key": key,
                "method": metadata["method"],
                "path": metadata["path"],
                "mutation": mutation,
                "terminal": False,
            }
        )
        self.journal["calls"] += 1
        self.save()
        self._dispatch_check()

    def _after(self, key, metadata):
        operation = next(row for row in self.journal["operations"] if row["key"] == key)
        operation.update(terminal=True, status=metadata["status"])
        self.save()

    def _intent(self, kind, name, **extra):
        resource = {"kind": kind, "name": name, "acknowledged": False, **extra}
        self.journal["resources"].append(resource)
        self.save()
        return resource

    def prepare(self, subdomain, access, canary):
        if self.journal["stage"] != "planned" or self.journal["resources"]:
            raise ProviderError("post_preparation_replay_refused")
        if (
            not isinstance(subdomain, str)
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain)
            or not isinstance(access, str)
            or not re.fullmatch(r"[a-f0-9]{64}", access)
            or not isinstance(canary, str)
            or not re.fullmatch(r"SYNTHETIC-[a-f0-9]{32}", canary)
        ):
            raise ProviderError("post_target_invalid")
        run = self.journal["runId"]
        for short in ("src", "recv"):
            self.api.preflight_worker_absence(
                f"fga-post-{short}-{run}", key=short + ":absence-preflight"
            )
        db = self._intent("database", "fga-post-db-" + run)
        db["identity"] = self.api.create_database(db["name"], key="database:create")
        db["acknowledged"] = True
        self.save()
        schema = (PACKET / "schema.sql").read_bytes()
        self.api.migrate(db["identity"], schema, _digest(schema), key="database:schema")
        for role in ("source", "receiver"):
            self.api.query(
                db["identity"],
                "INSERT INTO post_budget(run_id,role,expires_at) VALUES(?,?,?)",
                [run, role, self.journal["expiresAtUnix"]],
                key="database:seed:" + role,
            )
        for role, short in (("source", "src"), ("receiver", "recv")):
            worker = self._intent("worker", f"fga-post-{short}-{run}", role=role)
            identity = self.api.create_worker(worker["name"], key=role + ":create")
            worker.update(identity=identity, acknowledged=True)
            self.save()
            values = {
                "RUN_ID": run,
                "ROLE": role,
                "SUBDOMAIN": subdomain,
                "EXPIRES": str(self.journal["expiresAtUnix"]),
                "ACCESS": access,
                "CANARY": canary,
            }
            metadata = {
                "main_module": "worker.mjs",
                "compatibility_date": "2026-10-16",
                "compatibility_flags": [],
                "observability": {"enabled": False},
                "logpush": False,
                "bindings": [{"name": "DB", "type": "d1", "id": db["identity"]["uuid"]}]
                + [
                    {
                        "name": k,
                        "type": "secret_text" if k in {"ACCESS", "CANARY"} else "plain_text",
                        "text": v,
                    }
                    for k, v in values.items()
                ],
            }
            module = (PACKET / "worker.mjs").read_bytes()
            version = self.api.create_version(
                identity, module, _digest(module), metadata, access, key=role + ":version"
            )
            worker["version"] = version
            self.save()
            deployment = self.api.deploy_version(identity, version, key=role + ":deploy")
            worker["deployment"] = deployment
            self.save()
            self.api.inspect_deployment(identity, version, deployment, key=role + ":deployed")
            self.api.enable_worker(identity, key=role + ":enable")
            self.api.assert_endpoint(
                identity,
                "https://" + worker["name"] + "." + subdomain + ".workers.dev",
                key=role + ":endpoint",
            )
        self.save()
        self._dispatch_check()
        self.journal["stage"] = "ready"
        self.save()
        if self.clock() + 20 >= self.preparation_deadline:
            raise ProviderError("post_preparation_deadline")
        self._dispatch_check()
        self._target = {
            "schemaVersion": 1,
            "planVersion": VERSION,
            "runId": run,
            "subdomain": subdomain,
            "access": access,
            "canary": canary,
            "expiresAtUnix": self.journal["expiresAtUnix"],
        }
        return self._target.copy()

    def _callers_terminal(self):
        if self.journal.get("nativeInvocations") == 0 and not self.journal.get("targetPublished"):
            return True
        if (
            self.journal.get("nativeInvocations") != 1
            or self.journal.get("nativeTerminal") is not True
            or self._target is None
        ):
            return False
        try:
            paths = self.journal["nativePaths"]
            status, used = Path(paths["status"]), Path(paths["used"])
            value = bounded_json(status)
            native_terminal(value, self.journal["runId"])
            if (
                value.get("responseReferencesCleared") is not True
                or bounded_json(used) != self._target
            ):
                return False
            self.journal["callerTerminalEvidence"] = {
                "runId": self.journal["runId"],
                "owner": self.journal["owner"],
                "statusSha2_256": digest(status),
                "usedTargetSha2_256": digest(used),
                "remoteSqlSettlementProven": False,
            }
            self.save()
            return True
        except OSError, ValueError, KeyError, TypeError:
            return False

    def call(self, method, path, body=None, *, cleanup=False):
        # This narrow compatibility seam feeds the unchanged observation validator.
        db = next(row for row in self.journal["resources"] if row["kind"] == "database")
        if (
            not db["acknowledged"]
            or method != "POST"
            or path != db["path"] + "/query"
            or not isinstance(body, dict)
            or set(body) != {"sql", "params"}
        ):
            raise ProviderError("post_observation_scope_invalid")
        old_cleanup, self._cleanup = self._cleanup, cleanup
        try:
            return 200, {
                "success": True,
                "result": self.api.query(
                    db["identity"], body["sql"], body["params"], key="database:observations"
                ),
            }
        finally:
            self._cleanup = old_cleanup

    def observe(self):
        self.api._permit.begin_cleanup()
        db = next(row for row in self.journal["resources"] if row["kind"] == "database")
        if not db.get("acknowledged"):
            raise ProviderError("post_database_unacknowledged")
        db["path"] = "/d1/database/" + db["identity"]["uuid"]
        return super().observe()

    def cleanup(self):
        self.api._permit.begin_cleanup()
        self._cleanup = True
        self.journal["stage"] = "cleanup"
        self.save()
        for resource in reversed(self.journal["resources"]):
            if resource.get("deleted") or not resource.get("acknowledged"):
                continue
            try:
                identity = resource["identity"]
                if resource["kind"] == "worker":
                    prefix = resource["role"] + ":cleanup"
                    resource["delete"] = self.api.delete_worker(identity, key=prefix + ":delete")
                    self.save()
                    resource["deleted"] = (
                        self.api.inspect_worker(identity, key=prefix + ":absence") is None
                    )
                else:
                    workers = [row for row in self.journal["resources"] if row["kind"] == "worker"]
                    if (
                        not self._callers_terminal()
                        or any(
                            not row.get("deleted")
                            or row.get("delete", {}).get("deletionAcknowledged") is not True
                            for row in workers
                        )
                        or any(not row["terminal"] for row in self.journal["operations"])
                        or any(
                            row["method"] == "DELETE"
                            and row["path"] == "/d1/database/" + identity["uuid"]
                            for row in self.journal["operations"]
                        )
                    ):
                        resource["retainedUnknown"] = True
                        continue
                    resource["delete"] = self.api.delete_database(
                        identity, key="database:cleanup:delete"
                    )
                    self.save()
                    if resource["delete"].get("deletionAcknowledged") is not True:
                        resource["retainedUnknown"] = True
                        continue
                    resource["deleted"] = (
                        self.api.inspect_database(identity, key="database:cleanup:absence") is None
                    )
            except Exception:
                resource["cleanupError"] = True
            finally:
                self.save()
        confirmed = all(row.get("deleted", False) for row in self.journal["resources"])
        self.journal["stage"] = "cleanup_complete" if confirmed else "cleanup_unconfirmed"
        self.save()
        receipt = {
            "schemaVersion": 1,
            "planVersion": VERSION,
            "stage": self.journal["stage"],
            "cleanupConfirmed": confirmed,
            "observationsConfirmed": self.journal.get("observationsConfirmed", False),
            "stopReason": self.journal.get("stopReason", "preparation_failed"),
            "providerCalls": self.journal["calls"],
            "productionQualified": False,
            "resources": [
                {
                    "kind": row["kind"],
                    "acknowledged": row.get("acknowledged", False),
                    "deleted": row.get("deleted", False),
                }
                for row in self.journal["resources"]
            ],
        }
        (self.directory / "cleanup.json").write_text(json.dumps(receipt), encoding="utf-8")
        return receipt
