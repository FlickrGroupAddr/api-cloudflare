"""Synthetic successor and existing authority refusals; no private inputs or I/O."""

import copy
import hashlib
import json
import socket
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import readiness

from scripts import hosted_publisher_operator_plan as boundary
from tests.test_hosted_publisher_operator_plan import fixture, loaded
from tests.test_hosted_publisher_token_expiry_amendment import grant


class SuccessorBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-successor-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.recipe = {
            "schema_version": 1,
            "status": "NO-GO",
            "source_commit": "a" * 40,
            **dict.fromkeys(readiness.FALSE_FIELDS, False),
            "files": {},
        }
        for name in readiness.PUBLIC_FILES:
            raw = ("synthetic-public-source:" + name).encode()
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.recipe["files"][name] = hashlib.sha256(raw).hexdigest()
        self.network = patch.object(socket, "create_connection", side_effect=AssertionError).start()
        self.addCleanup(patch.stopall)

    def verify(self, value=None, expected_source="a" * 40):
        raw = json.dumps(self.recipe if value is None else value).encode()
        return readiness.verify(self.root, raw, hashlib.sha256(raw).hexdigest(), expected_source)

    def test_valid_public_bindings_always_retain_false_consent(self):
        result = self.verify()
        self.assertEqual(result["status"], "NO-GO")
        for name in readiness.FALSE_FIELDS:
            self.assertIs(result[name], False)
        self.assertIs(result["private_packet_prepared"], False)
        self.network.assert_not_called()

    def test_stale_source_or_recipe_bytes_refuse(self):
        for name in (
            "scripts/hosted_publisher_execution_provider.py",
            readiness.RECIPE_FILES[0],
        ):
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(b"synthetic-changed")
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify()
            path.write_bytes(original)

    def test_old_source_revision_refuses(self):
        with self.assertRaises(ValueError):
            self.verify(expected_source="b" * 40)

    def test_independent_recipe_digest_refuses_tampering(self):
        with self.assertRaises(ValueError):
            readiness.verify(self.root, json.dumps(self.recipe).encode(), "0" * 64, "a" * 40)

    def test_false_fields_cannot_be_promoted_or_integer_coerced(self):
        for name in readiness.FALSE_FIELDS:
            for promoted in (True, 0, 1, None):
                with self.subTest(name=name, value=promoted), self.assertRaises(ValueError):
                    self.verify({**self.recipe, name: promoted})

    def test_arbitrary_private_paths_are_rejected_before_file_read(self):
        value = copy.deepcopy(self.recipe)
        value["files"]["private/credential.txt"] = "0" * 64
        with patch.object(readiness.runtime_packet, "bounded_read") as read:
            with self.assertRaises(ValueError):
                self.verify(value)
            read.assert_not_called()

    def test_missing_closure_entry_refuses(self):
        value = copy.deepcopy(self.recipe)
        del value["files"][readiness.PUBLIC_FILES[0]]
        with self.assertRaises(ValueError):
            self.verify(value)


class ExistingAuthorityBoundaryTests(unittest.TestCase):
    def setUp(self):
        value = fixture()
        for name in ("starts_at", "expires_at", "cleanup_deadline"):
            value[name] = value[name].replace("2026-10-17", "2026-10-18")
        for case in value["cases"]:
            for name in ("starts_at", "expires_at"):
                case[name] = case[name].replace("2026-10-17", "2026-10-18")
        value["revocation_owner"] = "Terry Ott"
        self.plan = loaded(value)
        self.grant = grant(self.plan)
        self.then = datetime(2026, 10, 18, 12, 1, tzinfo=UTC)
        self.today = datetime(2026, 10, 19, 12, tzinfo=UTC)

    def test_historical_grant_refuses_today_even_with_exact_amendment(self):
        boundary.validate_operator_grant(self.plan, self.grant, self.then)
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(self.plan, self.grant, self.today)

    def test_historical_run_window_refuses_today(self):
        boundary.validate_plan(self.plan, self.then)
        with self.assertRaises(ValueError):
            boundary.validate_plan(self.plan, self.today)

    def test_old_amendment_cannot_be_rolled_forward(self):
        value = {**self.grant, "expires_at": "2026-10-19T13:00:00Z"}
        with self.assertRaises(ValueError):
            boundary.validate_operator_grant(self.plan, value, self.today)

    def test_false_consent_refuses_during_otherwise_valid_window(self):
        consent = {
            "schema_version": 1,
            "granted": False,
            "plan_digest": self.plan.digest,
            "owner": self.plan.owner,
            "actions": list(boundary.OWNER_ACTIONS),
            "decision_id": "synthetic-not-a-human-decision",
        }
        with self.assertRaises(ValueError):
            boundary.validate_consent(self.plan, consent, self.then)
