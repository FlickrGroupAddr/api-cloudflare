"""Synthetic offline preparation tests; no private artifact or provider effects."""

import copy
import hashlib
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import hosted_publisher_operator_plan as boundary
from scripts import prepare_hosted_publisher_execution as execution
from scripts import prepare_hosted_publisher_qualification as retained
from tests.test_hosted_publisher_operator_plan import fixture

HEAD = "1" * 40


class ExecutionPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-execution-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.current = self.root / "current"
        self.candidate = self.root / "candidate"
        self.bundle = self.candidate / "worker.js"
        self.destination = self.root / "packet"
        self.current.mkdir()
        self.candidate.mkdir()
        self.files = {}
        for name in execution.SOURCE_FILES:
            data = ("synthetic-current:" + name).encode()
            self.files[name] = data
            path = self.current / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        source = {}
        for name in retained.SOURCES:
            data = ("synthetic-retained:" + name).encode()
            source[name] = data
            path = self.candidate / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        manifest = {
            "sourceHead": HEAD,
            "sourceCommitExact": True,
            "files": [
                {"path": name, "bytes": len(data), "sha2_256": boundary.sha2_256(data)}
                for name, data in source.items()
            ],
        }
        manifest["artifactSha2_256"] = boundary.sha2_256(retained.encoded(manifest))
        manifest_raw = retained.encoded(manifest)
        (self.candidate / "manifest.json").write_bytes(manifest_raw)
        self.bundle.write_bytes(b"s" * 652967)
        self.pins = {
            **boundary.CANDIDATE_PINS,
            "source_commit": HEAD,
            "source_artifact": manifest["artifactSha2_256"],
            "manifest": boundary.sha2_256(manifest_raw),
            "worker": boundary.sha2_256(self.bundle.read_bytes()),
        }
        self.addCleanup(patch.stopall)
        patch.object(boundary, "CANDIDATE_PINS", self.pins).start()
        patch.object(
            boundary,
            "CURRENT_CONFIG_PINS",
            {name: boundary.sha2_256(self.files[name]) for name in boundary.CURRENT_CONFIG_PINS},
        ).start()
        self.git = patch.object(execution, "_git", side_effect=self.git_response).start()
        # Any accidental networking, entropy/credential creation or shell launch fails the test.
        self.network = patch.object(socket, "create_connection", side_effect=AssertionError).start()
        self.entropy = patch.object(
            boundary.secrets, "token_hex", side_effect=AssertionError
        ).start()
        self.process = patch.object(
            execution.subprocess, "Popen", side_effect=AssertionError
        ).start()
        self.scope = {k: v for k, v in fixture().items() if k in execution.SCOPE_FIELDS}

    def git_response(self, root, *arguments):
        self.assertEqual(root, self.current)
        if arguments == ("rev-parse", "HEAD"):
            return HEAD
        self.assertEqual(arguments, ("ls-tree", "-r", HEAD, "--", *execution.SOURCE_FILES))
        return "\n".join(
            "100644 blob "
            + hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            + "\t"
            + name
            for name, data in self.files.items()
        )

    def prepare(self, scope=None):
        return execution.prepare(
            self.destination,
            json.dumps(self.scope if scope is None else scope).encode(),
            self.candidate,
            self.bundle,
            self.current,
            HEAD,
        )

    def rewrite_manifest(self, manifest):
        identity = {k: v for k, v in manifest.items() if k != "packet_sha2_256"}
        manifest["packet_sha2_256"] = boundary.sha2_256(execution._encoded(identity))
        (self.destination / "manifest.json").write_bytes(execution._encoded(manifest))
        return manifest["packet_sha2_256"]

    def test_roundtrip_binds_all_supplied_scope_and_source_without_authority_or_effects(self):
        manifest = self.prepare()
        self.assertEqual(execution.verify(self.destination, manifest["packet_sha2_256"]), manifest)
        self.assertEqual(manifest["candidate_pins"], self.pins)
        self.assertEqual(manifest["source_commit"], HEAD)
        self.assertEqual(manifest["blockers"], list(execution.BLOCKERS))
        self.assertEqual(manifest["status"], "NO-GO")
        for flag in ("live_execution_allowed", "native_execution_allowed", "provider_qualified"):
            self.assertIs(manifest[flag], False)
        self.assertEqual(set(manifest["files"]), execution.PACKET_FILES - {"manifest.json"})
        loaded = boundary.load_plan((self.destination / "plan.json").read_bytes())
        self.assertEqual(loaded.account_id, self.scope["account_id"])
        self.assertEqual(loaded.digest, manifest["plan_digest"])
        self.assertEqual(set(loaded.source_files), set(execution.PLAN_FILES))
        for name, data in self.files.items():
            self.assertEqual((self.destination / "source" / name).read_bytes(), data)
        self.network.assert_not_called()
        self.entropy.assert_not_called()
        self.process.assert_not_called()

    def test_every_scope_field_is_mandatory_and_cannot_supply_authority_or_pins(self):
        for name in execution.SCOPE_FIELDS:
            scope = copy.deepcopy(self.scope)
            del scope[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                self.prepare(scope)
        for name, value in (
            ("pins", self.pins),
            ("source_files", {}),
            ("granted", True),
            ("consent", {"granted": True}),
            ("operator_grant", {}),
            ("token", "synthetic-private-token"),
            ("native_execution_allowed", True),
        ):
            with self.subTest(extra=name), self.assertRaises(ValueError):
                self.prepare({**self.scope, name: value})
        self.assertFalse(self.destination.exists())

    def test_duplicate_fields_or_oversized_scope_are_refused(self):
        raw = json.dumps(self.scope).encode()
        for invalid in (b'{"schema_version":2,' + raw[1:], b" " * 262145):
            with self.assertRaises(ValueError):
                execution.build_plan(invalid, self.current, HEAD)
        self.assertFalse(self.destination.exists())

    def test_independent_source_head_and_every_committed_byte_are_required(self):
        raw = json.dumps(self.scope).encode()
        for head in ("", "main", "2" * 40, "A" * 40):
            with self.subTest(head=head), self.assertRaises(ValueError):
                execution.build_plan(raw, self.current, head)
        for name in execution.SOURCE_FILES:
            path = self.current / name
            original = path.read_bytes()
            path.write_bytes(original + b"drift")
            with self.subTest(source=name), self.assertRaises(ValueError):
                self.prepare()
            path.write_bytes(original)
        with patch.object(execution, "_git", side_effect=[HEAD, ""]), self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_missing_or_changed_retained_module_manifest_and_migration_refused_before_output(self):
        for name in ("worker.js", "manifest.json", "migrations/0026_album_local_removal.sql"):
            path = self.candidate / name
            original = path.read_bytes()
            path.write_bytes(original + b"drift")
            with self.subTest(candidate=name), self.assertRaises(ValueError):
                self.prepare()
            path.write_bytes(original)
            self.assertFalse(self.destination.exists())
        self.bundle.unlink()
        with self.assertRaises((ValueError, OSError)):
            self.prepare()

    def test_committed_source_cannot_override_pinned_default_off_config(self):
        for name in boundary.CURRENT_CONFIG_PINS:
            original = self.files[name]
            self.files[name] = original + b"reviewed-but-different-config"
            (self.current / name).write_bytes(self.files[name])
            with self.subTest(config=name), self.assertRaises(ValueError):
                self.prepare()
            self.files[name] = original
            (self.current / name).write_bytes(original)
        self.assertFalse(self.destination.exists())

    def test_current_source_changed_during_candidate_validation_is_not_staged(self):
        name = "scripts/hosted_publisher_operator.py"
        original_validator = boundary.validate_artifact

        def validate_then_drift(*args):
            original_validator(*args)
            (self.current / name).write_bytes(self.files[name] + b"late-change")

        with (
            patch.object(boundary, "validate_artifact", side_effect=validate_then_drift),
            self.assertRaises(ValueError),
        ):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_provider_name_mismatch_and_reused_pairs_are_refused(self):
        for key, value in (
            ("worker_name", "outside-provider-boundary"),
            ("d1_name", "fga-publisher-under_score"),
            ("run_id", "0" * 64),
        ):
            scope = copy.deepcopy(self.scope)
            scope["cases"][0][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.prepare(scope)
        for key in ("worker_name", "d1_name", "run_id", "endpoint"):
            scope = copy.deepcopy(self.scope)
            scope["cases"][1][key] = scope["cases"][0][key]
            with self.subTest(duplicate=key), self.assertRaises(ValueError):
                self.prepare(scope)
        self.assertFalse(self.destination.exists())

    def test_placeholder_authority_hostile_origins_deadlines_and_budgets_are_refused(self):
        mutations = (
            ("account_id", "0" * 32),
            ("owner", ""),
            ("cleanup_owner", ""),
            ("revocation_owner", ""),
            ("starts_at", ""),
            ("cleanup_deadline", "2026-10-18T13:00:00Z"),
        )
        for name, value in mutations:
            with self.subTest(field=name), self.assertRaises(ValueError):
                self.prepare({**self.scope, name: value})
        for origin in (
            "http://fga-publisher-case-0.synthetic.workers.dev",
            "https://user@fga-publisher-case-0.synthetic.workers.dev",
            "https://fga-publisher-case-0.synthetic.workers.dev/path",
            "https://fga-publisher-case-0.synthetic.workers.dev?token=synthetic",
        ):
            scope = copy.deepcopy(self.scope)
            scope["cases"][0]["endpoint"] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                self.prepare(scope)
        for budget in (True, 0, float("inf"), boundary.BUDGET_CEILINGS["provider_calls"] + 1):
            scope = copy.deepcopy(self.scope)
            scope["budgets"]["provider_calls"] = budget
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                self.prepare(scope)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_never_replays_or_overwrites_packet(self):
        manifest = self.prepare()
        original = (self.destination / "manifest.json").read_bytes()
        self.git.reset_mock()
        with self.assertRaises(ValueError):
            self.prepare()
        self.git.assert_not_called()
        self.assertEqual((self.destination / "manifest.json").read_bytes(), original)
        execution.verify(self.destination, manifest["packet_sha2_256"])

    def test_staged_tampering_and_missing_or_extra_files_are_refused(self):
        manifest = self.prepare()
        digest = manifest["packet_sha2_256"]
        for name in manifest["files"]:
            path = self.destination / name
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(changed=name), self.assertRaises(ValueError):
                execution.verify(self.destination, digest)
            path.unlink()
            with self.subTest(missing=name), self.assertRaises(ValueError):
                execution.verify(self.destination, digest)
            path.write_bytes(original)
        (self.destination / "unreviewed.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            execution.verify(self.destination, digest)

    def test_rewritten_hash_cannot_override_independent_digest_or_promote_authority(self):
        manifest = self.prepare()
        original = copy.deepcopy(manifest)
        for field, value in (
            ("schema_version", True),
            ("granted", True),
            ("status", "GO"),
            ("live_execution_allowed", True),
            ("native_execution_allowed", True),
            ("provider_qualified", True),
            ("blockers", []),
            ("source_commit_exact", False),
            ("candidate_pins", {}),
        ):
            changed = {**original, field: value}
            rewritten = self.rewrite_manifest(changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                execution.verify(self.destination, original["packet_sha2_256"])
            with self.subTest(self_asserted_digest=field), self.assertRaises(ValueError):
                execution.verify(self.destination, rewritten)
        for digest in ("", "a" * 63, "A" * 64, "f" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                execution.verify(self.destination, digest)


if __name__ == "__main__":
    unittest.main()
