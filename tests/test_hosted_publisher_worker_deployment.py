"""Actual composed provider lifecycle over an in-memory transport; no network I/O."""

import copy
import hashlib
import json
import unittest
from dataclasses import replace
from functools import partial
from unittest.mock import Mock, patch

from scripts import hosted_publisher_operator_plan as plan
from scripts import hosted_publisher_worker_deployment as deployment
from scripts.hosted_publisher_provider import Limits, ProviderError, ProviderUnknown
from tests.test_hosted_publisher_operator_plan import loaded
from tests.test_hosted_publisher_worker_identity import REFERENCES

ACCOUNT = "a" * 32
TOKEN = "synthetic-private-provider-token"
STAMP = "2026-10-17T12:00:00Z"


class StatefulTransport:
    """Persist provider effects before optionally losing their acknowledgement."""

    def __init__(self, fault=None):
        self.fault = fault
        self.calls = []
        self.workers, self.databases, self.versions, self.deployments = {}, {}, {}, {}
        self.returned_versions = []
        self.returned_deployments = []

    @staticmethod
    def envelope(result=None, status=200):
        return status, {}, json.dumps({"success": status != 404, "result": result}).encode()

    def __call__(self, method, path, raw, headers, timeout, cap):
        path = path.split("/accounts/" + ACCOUNT, 1)[1]
        body = json.loads(raw) if raw else None
        self.calls.append((method, path, copy.deepcopy(body)))
        result, status = self.execute(method, path, body)
        if self.fault == "lost_create" and method == "POST" and path == "/d1/database":
            raise OSError(TOKEN)
        if self.fault == "lost_worker_create" and method == "POST" and path == "/workers/workers":
            raise OSError(TOKEN)
        if self.fault == "lost_version" and method == "POST" and "/versions?" in path:
            raise OSError(TOKEN)
        if self.fault == "lost_deployment" and method == "POST" and path.endswith("/deployments"):
            raise OSError(TOKEN)
        if (
            self.fault == "lost_disable"
            and method == "PATCH"
            and body is not None
            and not body["subdomain"]["enabled"]
        ):
            raise OSError(TOKEN)
        if (
            self.fault == "lost_worker_delete"
            and method == "DELETE"
            and "/workers/workers/" in path
        ):
            raise OSError(TOKEN)
        if self.fault == "lost_d1_delete" and method == "DELETE" and "/d1/database/" in path:
            raise OSError(TOKEN)
        return self.envelope(result, status)

    def execute(self, method, path, body):
        if path == "/d1/database" and method == "POST":
            number = len(self.databases) + 1
            uuid = f"{number:08}-1111-4111-8111-111111111111"
            value = {"uuid": uuid, "name": body["name"], "created_at": STAMP}
            self.databases[uuid] = value
            return value, 200
        if path.startswith("/d1/database/"):
            uuid = path.split("/")[3]
            if method == "POST":
                rows = [] if "sqlite_schema" in body["sql"] else None
                return [{"success": True, "results": rows or []}], 200
            if method == "DELETE":
                if self.fault == "database_absence_unverified":
                    return {}, 200
                self.databases.pop(uuid, None)
                return {}, 200
            return self.databases.get(uuid), 200 if uuid in self.databases else 404
        if path == "/workers/workers" and method == "POST":
            worker_id = f"{len(self.workers) + 1:032x}"
            value = {
                **body,
                "id": worker_id,
                "created_on": STAMP,
                "references": copy.deepcopy(REFERENCES),
            }
            value["subdomain"]["url"] = "https://" + body["name"] + ".synthetic.workers.dev"
            self.workers[worker_id] = value
            return value, 200
        if path.startswith("/workers/workers/"):
            worker_id = path.split("/")[3]
            if "/versions" in path:
                if method == "POST":
                    version_id = f"{len(self.versions) + 1:08}-2222-4222-8222-222222222222"
                    value = {**body, "id": version_id, "created_on": STAMP}
                    if self.fault == "cache_enabled_create":
                        value["cache_options"] = {"enabled": True}
                    self.versions[version_id] = copy.deepcopy(value)
                    self.returned_versions.append(version_id)
                    return value, 200
                version_id = path.split("/")[5].split("?")[0]
                value = copy.deepcopy(self.versions[version_id])
                if self.fault == "cache_enabled_read":
                    value["cache_options"] = {"enabled": True}
                if self.fault == "module_drift":
                    value["modules"][0]["content_base64"] = "ZHJpZnQ="
                if self.fault in {"overlay_drift", "private_drift"}:
                    binding = next(b for b in value["bindings"] if b["name"] == "DB")
                    binding["database_id"] = "99999999-9999-4999-8999-999999999999"
                    if self.fault == "private_drift":
                        value["bindings"].append(
                            {
                                "name": "PRIVATE",
                                "type": "plain_text",
                                "text": "SYNTHETIC-PRIVATE-RESPONSE",
                            }
                        )
                return value, 200
            if method == "DELETE":
                if self.fault == "worker_absence_unverified":
                    return {}, 200
                self.workers.pop(worker_id, None)
                return {}, 200
            if worker_id not in self.workers:
                return None, 404
            if method == "PATCH":
                self.workers[worker_id].update(copy.deepcopy(body))
                self.workers[worker_id]["subdomain"]["url"] = (
                    "https://" + body["name"] + ".synthetic.workers.dev"
                )
            value = copy.deepcopy(self.workers[worker_id])
            if self.fault == "worker_identity_drift" and method == "GET":
                value["id"] = "f" * 32
            return value, 200
        if path == "/workers/subdomain":
            return {"subdomain": "synthetic"}, 200
        if path.startswith("/workers/scripts/") and "/deployments" in path:
            name = path.split("/")[3]
            if method == "POST":
                number = len(self.deployments) + 1
                value = {
                    **body,
                    "id": f"{number:08}-3333-4333-8333-333333333333",
                    "created_on": STAMP,
                }
                self.deployments[name] = value
                self.returned_deployments.append(value["id"])
                return value, 200
            value = copy.deepcopy(self.deployments[name])
            if self.fault == "deployment_drift":
                value["versions"][0]["version_id"] = "99999999-9999-4999-8999-999999999999"
            return (
                {"deployments": [value]} if path.split("?")[0].endswith("/deployments") else value
            ), 200
        raise AssertionError((method, path))


class HostedPublisherWorkerDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.plan = loaded()
        self.case = self.plan.cases[0]
        self.module = b"synthetic immutable module"
        self.digest = hashlib.sha256(self.module).hexdigest()
        self.database_uuid = "00000001-1111-4111-8111-111111111111"
        self.projection = plan.deployment_projection(self.plan, self.case, self.database_uuid)

    def provider(self, fault=None, **kwargs):
        self.transport = StatefulTransport(fault)
        return deployment.BetaPublisherProvider(
            ACCOUNT,
            TOKEN,
            [self.case.worker_name],
            [self.case.d1_name],
            exclusive_owner=True,
            transport=self.transport,
            **kwargs,
        )

    def version(self, provider):
        provider.create_database(self.case.d1_name, key="db")
        identity = provider.create_worker(self.case.worker_name, key="create")
        version = provider.create_version(
            identity, self.module, self.digest, self.projection, "d" * 64, key="version"
        )
        return identity, version

    def test_returned_ids_bind_version_deployment_readback_and_exact_delete(self):
        provider = self.provider()
        identity, version = self.version(provider)
        deployed = provider.deploy_version(identity, version, key="deploy")
        self.assertEqual(provider.inspect_version(identity, version, key="read-version"), version)
        self.assertEqual(
            provider.inspect_deployment(identity, version, deployed, key="read-deploy"), deployed
        )
        provider.enable_worker(identity, key="enable")
        self.assertTrue(provider.inspect_endpoint(identity, key="endpoint")["enabled"])
        self.assertTrue(provider.disable_worker(identity, key="disable")["disableAcknowledged"])
        self.assertFalse(provider.inspect_endpoint(identity, key="disabled")["enabled"])
        self.assertTrue(provider.delete_worker(identity, key="delete")["deletionAcknowledged"])
        self.assertIsNone(provider.inspect_worker(identity, key="absence"))
        self.assertEqual(version["id"], self.transport.returned_versions[0])
        self.assertEqual(deployed["id"], self.transport.returned_deployments[0])
        self.assertEqual(deployed["versionId"], version["id"])
        self.assertEqual(deployed["workerId"], identity["id"])
        calls = self.transport.calls
        version_post = next(b for m, p, b in calls if m == "POST" and "/versions?" in p)
        self.assertEqual(
            next(b for b in version_post["bindings"] if b["name"] == "DB"),
            {"name": "DB", "type": "d1", "database_id": self.database_uuid},
        )
        self.assertEqual(sum(m == "DELETE" for m, _, _ in calls), 1)
        for method, path, _ in calls:
            self.assertNotIn("force", path.lower())
            self.assertNotIn("unsafe", path.lower())
            if method == "GET":
                self.assertNotIn(path, ("/workers/workers", "/workers/scripts", "/d1/database"))
            if method == "GET" and path.endswith("/deployments"):
                self.assertIn("/scripts/" + self.case.worker_name + "/", path)
        self.assertFalse(provider.provider_qualified)
        self.assertFalse(provider.live_execution_allowed)

    def test_missing_exclusive_management_and_concrete_transport_refuse(self):
        with self.assertRaises(ProviderError):
            deployment.BetaPublisherProvider(
                ACCOUNT,
                TOKEN,
                [self.case.worker_name],
                [self.case.d1_name],
                transport=StatefulTransport(),
            )
        with patch("scripts.hosted_publisher_provider.https_transport") as transport:
            provider = deployment.BetaPublisherProvider(
                ACCOUNT, TOKEN, [self.case.worker_name], [self.case.d1_name], exclusive_owner=True
            )
            with self.assertRaises(ProviderError):
                provider.create_worker(self.case.worker_name, key="create")
        transport.assert_not_called()
        with patch("scripts.hosted_publisher_provider.https_transport") as transport:
            provider = deployment.BetaPublisherProvider(
                ACCOUNT, TOKEN, [self.case.worker_name], [self.case.d1_name], exclusive_owner=True
            )
            identity = {"uuid": self.database_uuid, "name": self.case.d1_name, "created_at": STAMP}
            for action in (
                partial(provider.create_database, self.case.d1_name, key="db"),
                partial(provider.inspect_database, identity, key="inspect"),
                partial(
                    provider.migrate,
                    identity,
                    b"SELECT 1;",
                    hashlib.sha256(b"SELECT 1;").hexdigest(),
                    key="migration",
                ),
            ):
                with self.assertRaises(ProviderError):
                    action()
        transport.assert_not_called()

    def test_beta_create_hook_crossing_shared_deadline_never_dispatches(self):
        clock = Mock(return_value=0.0)

        def reserve(*_):
            clock.return_value = 1.0

        provider = self.provider(
            monotonic=clock, before_request=reserve, limits=replace(Limits(), total_seconds=1)
        )
        with self.assertRaises(ProviderError):
            provider.create_worker(self.case.worker_name, key="late-worker")
        self.assertEqual(self.transport.calls, [])

    def test_unapproved_cache_storage_refuses_create_and_version_readback(self):
        for fault in ("cache_enabled_create", "cache_enabled_read"):
            with self.subTest(fault=fault):
                provider = self.provider()
                provider.create_database(self.case.d1_name, key="db")
                identity = provider.create_worker(self.case.worker_name, key="create")
                if fault == "cache_enabled_create":
                    self.transport.fault = fault
                    with self.assertRaises(ProviderUnknown):
                        provider.create_version(
                            identity,
                            self.module,
                            self.digest,
                            self.projection,
                            "d" * 64,
                            key="version",
                        )
                else:
                    version = provider.create_version(
                        identity, self.module, self.digest, self.projection, "d" * 64, key="version"
                    )
                    self.transport.fault = fault
                    with self.assertRaises(ProviderUnknown):
                        provider.inspect_version(identity, version, key="inspect")
                self.assertFalse(
                    any(
                        m == "POST" and p.endswith("/deployments")
                        for m, p, _ in self.transport.calls
                    )
                )

    def test_endpoint_requires_matching_beta_url_and_independent_account_suffix(self):
        expected = "https://" + self.case.worker_name + ".synthetic.workers.dev"
        for value in ("https://different.synthetic.workers.dev", None, 42, "missing"):
            with self.subTest(url=value):
                provider = self.provider()
                identity, _ = self.version(provider)
                worker = self.transport.workers[identity["id"]]
                if value == "missing":
                    worker["subdomain"].pop("url")
                else:
                    worker["subdomain"]["url"] = value
                with self.assertRaises(ProviderUnknown):
                    provider.assert_endpoint(identity, expected, key="origin")
        provider = self.provider()
        identity, _ = self.version(provider)
        self.assertIs(provider.assert_endpoint(identity, expected, key="origin-disabled"), True)
        provider.enable_worker(identity, key="enable")
        self.assertIs(provider.assert_endpoint(identity, expected, key="origin-enabled"), True)

    def test_version_and_deployment_cannot_be_replayed_or_adopted(self):
        provider = self.provider()
        identity, version = self.version(provider)
        deployed = provider.deploy_version(identity, version, key="deploy")
        count = len(self.transport.calls)
        for invoke in (
            lambda: provider.create_version(
                identity, self.module, self.digest, self.projection, "d" * 64, key="repeat-version"
            ),
            lambda: provider.deploy_version(identity, version, key="repeat-deploy"),
            lambda: provider.inspect_version(
                identity, {**version, "id": self.database_uuid}, key="adopt-version"
            ),
            lambda: provider.inspect_deployment(
                identity, version, {**deployed, "id": self.database_uuid}, key="adopt-deployment"
            ),
        ):
            with self.assertRaises(ProviderError):
                invoke()
        self.assertEqual(len(self.transport.calls), count)

    def test_readback_rejects_module_binding_and_deployment_drift(self):
        for fault in ("module_drift", "overlay_drift", "deployment_drift"):
            with self.subTest(fault=fault):
                provider = self.provider()
                identity, version = self.version(provider)
                deployed = provider.deploy_version(identity, version, key="deploy")
                self.transport.fault = fault
                with self.assertRaises(ProviderUnknown):
                    if fault == "deployment_drift":
                        provider.inspect_deployment(identity, version, deployed, key="read")
                    else:
                        provider.inspect_version(identity, version, key="read")
                calls = len(self.transport.calls)
                with self.assertRaises(ProviderError):
                    provider.enable_worker(identity, key="after-unknown")
                self.assertEqual(len(self.transport.calls), calls)

    def test_unacknowledged_create_version_deploy_disable_delete_never_replays(self):
        for fault in (
            "lost_worker_create",
            "lost_version",
            "lost_deployment",
            "lost_disable",
            "lost_worker_delete",
        ):
            with self.subTest(fault=fault):
                provider = self.provider()
                if fault == "lost_worker_create":
                    action = partial(provider.create_worker, self.case.worker_name, key="create")
                elif fault == "lost_version":
                    provider.create_database(self.case.d1_name, key="db")
                    identity = provider.create_worker(self.case.worker_name, key="create")
                    action = partial(
                        provider.create_version,
                        identity,
                        self.module,
                        self.digest,
                        self.projection,
                        "d" * 64,
                        key="version",
                    )
                else:
                    identity, version = self.version(provider)
                    if fault == "lost_deployment":
                        action = partial(provider.deploy_version, identity, version, key="deploy")
                    elif fault == "lost_disable":
                        action = partial(provider.disable_worker, identity, key="disable")
                    else:
                        action = partial(provider.delete_worker, identity, key="delete")
                self.transport.fault = fault
                with self.assertRaises(ProviderUnknown):
                    action()
                count = len(self.transport.calls)
                with self.assertRaises(ProviderError):
                    action()
                self.assertEqual(len(self.transport.calls), count)

    def test_d1_beta_version_and_scripts_share_one_call_and_byte_budget(self):
        provider = self.provider(limits=replace(Limits(), calls=2))
        provider.create_database(self.case.d1_name, key="db")
        identity = provider.create_worker(self.case.worker_name, key="worker")
        with self.assertRaises(ProviderError):
            provider.create_version(
                identity, self.module, self.digest, self.projection, "d" * 64, key="version"
            )
        self.assertEqual(provider.calls, 2)
        self.assertEqual(len(self.transport.calls), 2)
        self.assertIs(provider.identity._provider, provider)
        for cap_name in ("total_request_bytes", "total_response_bytes"):
            reference = self.provider()
            reference.create_database(self.case.d1_name, key="db")
            reference.create_worker(self.case.worker_name, key="worker")
            consumed = (
                reference.request_bytes
                if cap_name == "total_request_bytes"
                else reference.response_bytes
            )
            provider = self.provider(limits=replace(Limits(), **{cap_name: consumed}))
            provider.create_database(self.case.d1_name, key="db")
            identity = provider.create_worker(self.case.worker_name, key="worker")
            with self.subTest(cap=cap_name), self.assertRaises(ProviderError):
                provider.create_version(
                    identity, self.module, self.digest, self.projection, "d" * 64, key="version"
                )
            self.assertEqual(len(self.transport.calls), 2)
        provider = self.provider(limits=replace(Limits(), total_response_bytes=1))
        with self.assertRaises(ProviderUnknown):
            provider.create_database(self.case.d1_name, key="db")
        with self.assertRaises(ProviderError):
            provider.create_worker(self.case.worker_name, key="worker")
        self.assertEqual(len(self.transport.calls), 1)


if __name__ == "__main__":
    unittest.main()
