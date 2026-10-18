"""Synthetic adversarial tests for the intentionally incomplete metadata projection."""

from __future__ import annotations

import copy
import json
import unittest

from scripts import temporary_composition_metadata_projection as projection

ACCOUNT = "a" * 32
ZONE = "b" * 32
UUID = "12345678-1234-1234-1234-123456789abc"
SENTINEL = "synthetic-private-value-sentinel"


def target_for(scope):
    target = {"accountId": ACCOUNT, "scriptName": "synthetic-worker"}
    if scope == "d1_database":
        target["databaseId"] = UUID
    if scope == "zone_routes":
        target["zoneId"] = ZONE
    return target


def payload_for(scope):
    results = {
        "deployments": {
            "deployments": [
                {
                    "id": UUID,
                    "created_on": "2026-10-18T14:00:00Z",
                    "source": "api",
                    "strategy": "percentage",
                    "versions": [{"version_id": UUID, "percentage": 100}],
                }
            ]
        },
        "versions": {"items": [{"id": UUID, "number": 1}]},
        "schedules": {"schedules": [{"cron": "*/5 * * * *"}]},
        "script_subdomain": {"enabled": False, "previews_enabled": False},
        "d1_database": {"uuid": UUID},
        "zone_routes": [{"id": "c" * 32, "pattern": "synthetic.example/*", "script": None}],
    }
    return {"success": True, "errors": [], "messages": [], "result": results[scope]}


class MetadataProjectionTests(unittest.TestCase):
    def project(self, scope, payload=None, target=None):
        return projection.project_metadata(
            scope,
            payload if payload is not None else payload_for(scope),
            target if target is not None else target_for(scope),
        )

    def refused(self, scope, payload=None, target=None):
        with self.assertRaises(projection.ProjectionError) as raised:
            self.project(scope, payload, target)
        self.assertNotIn(SENTINEL, str(raised.exception))

    def test_supported_endpoints_are_exact_and_only_d1_selects_server_fields(self):
        base = f"/client/v4/accounts/{ACCOUNT}/workers/scripts/synthetic-worker"
        expected = {
            "deployments": base + "/deployments",
            "versions": base + "/versions?page=1&per_page=100",
            "schedules": base + "/schedules",
            "script_subdomain": base + "/subdomain",
            "d1_database": f"/client/v4/accounts/{ACCOUNT}/d1/database/{UUID}?fields=uuid",
            "zone_routes": f"/client/v4/zones/{ZONE}/workers/routes",
        }
        self.assertEqual(set(expected), set(projection.SAFE_SCOPES))
        for scope, endpoint in expected.items():
            self.assertEqual(projection.endpoint_for(scope, target_for(scope)), endpoint)

    def test_secret_settings_content_version_detail_and_unknown_scopes_are_refused(self):
        for scope in ("settings", "content", "secrets", "version_detail", "query", SENTINEL):
            with self.subTest(scope=scope):
                self.refused(scope, {}, target_for("versions"))

    def test_all_outputs_are_detached_explicitly_incomplete_and_have_closed_fields(self):
        for scope in projection.SAFE_SCOPES:
            payload, target = payload_for(scope), target_for(scope)
            original = copy.deepcopy((payload, target))
            result = self.project(scope, payload, target)
            self.assertEqual(
                set(result),
                {
                    "scope",
                    "target",
                    "metadata",
                    "baselineComplete",
                    "gaps",
                    "omittedFields",
                },
            )
            self.assertIs(result["baselineComplete"], False)
            self.assertEqual(result["gaps"], list(projection.GAPS))
            self.assertEqual((payload, target), original)
            result["target"]["scriptName"] = "changed"
            self.assertEqual(target["scriptName"], "synthetic-worker")
            result["metadata"].clear()
            self.assertEqual((payload, target), original)

    def test_known_author_annotations_and_source_fields_are_never_retained(self):
        for scope in ("deployments", "versions"):
            payload = payload_for(scope)
            row = payload["result"]["deployments" if scope == "deployments" else "items"][0]
            row["annotations"] = {"note": SENTINEL}
            if scope == "deployments":
                row.update(source=SENTINEL, author_email=SENTINEL)
            else:
                row["metadata"] = {"author_email": SENTINEL, "source": SENTINEL}
            result = self.project(scope, payload)
            self.assertNotIn(SENTINEL, json.dumps(result))
            self.assertTrue(result["omittedFields"])

    def test_unknown_envelope_result_and_nested_row_fields_are_not_silently_redacted(self):
        for scope in projection.SAFE_SCOPES:
            payload = payload_for(scope)
            payload["secret"] = SENTINEL
            self.refused(scope, payload)
            payload = payload_for(scope)
            result = payload["result"]
            if isinstance(result, list):
                result[0]["secret"] = SENTINEL
            else:
                result["secret"] = SENTINEL
            self.refused(scope, payload)
        for scope, container in (
            ("deployments", "deployments"),
            ("versions", "items"),
            ("schedules", "schedules"),
        ):
            payload = payload_for(scope)
            payload["result"][container][0]["secret"] = SENTINEL
            self.refused(scope, payload)

    def test_d1_projection_refuses_raw_database_rows_and_wrong_database_identity(self):
        for result in (
            {"uuid": UUID, "rows": [{"photo": SENTINEL}]},
            {"uuid": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
        ):
            payload = payload_for("d1_database")
            payload["result"] = result
            self.refused("d1_database", payload)

    def test_pagination_cannot_hide_continuation_inconsistent_counts_or_boolean_counts(self):
        for scope in projection.SAFE_SCOPES:
            for info in (
                {"total_pages": 2},
                {"page": 2},
                {"total_count": 2},
                {"count": True},
                {"cursor": SENTINEL},
                {"per_page": 101},
            ):
                payload = payload_for(scope)
                payload["result_info"] = info
                self.refused(scope, payload)
            payload = payload_for(scope)
            payload["result_info"] = {
                "page": 1,
                "total_pages": 1,
                "count": 1,
                "total_count": 1,
                "per_page": 100,
            }
            self.assertIs(self.project(scope, payload)["baselineComplete"], False)

    def test_provider_errors_messages_and_non_boolean_success_have_static_failures(self):
        for scope in projection.SAFE_SCOPES:
            for field, value in (
                ("success", 1),
                ("errors", [{"message": SENTINEL}]),
                ("messages", [SENTINEL]),
            ):
                payload = payload_for(scope)
                payload[field] = value
                self.refused(scope, payload)

    def test_target_is_closed_and_cannot_inject_paths_or_change_shape(self):
        for scope in projection.SAFE_SCOPES:
            for field, value in (
                ("scriptName", "../../" + SENTINEL),
                ("accountId", SENTINEL),
                ("extra", SENTINEL),
            ):
                target = target_for(scope)
                target[field] = value
                self.refused(scope, target=target)
            target = target_for(scope)
            del target["scriptName"]
            self.refused(scope, target=target)

    def test_list_bound_types_and_nested_version_weights_are_validated(self):
        for scope, container in (
            ("deployments", "deployments"),
            ("versions", "items"),
            ("schedules", "schedules"),
        ):
            payload = payload_for(scope)
            payload["result"][container] *= 101
            self.refused(scope, payload)
            payload["result"][container] = None
            self.refused(scope, payload)
        for percentage in (True, -1, 101, float("nan"), float("inf"), SENTINEL):
            payload = payload_for("deployments")
            payload["result"]["deployments"][0]["versions"][0]["percentage"] = percentage
            self.refused("deployments", payload)


if __name__ == "__main__":
    unittest.main()
