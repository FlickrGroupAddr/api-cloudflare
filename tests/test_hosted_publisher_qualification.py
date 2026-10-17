"""Offline closed-packet integrity tests; no hosted or full-publisher pass claim."""

import copy
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts import prepare_hosted_publisher_qualification as packet

HEAD = "1" * 40


class HostedPublisherQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = packet.source_files(packet.ROOT)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-publisher-packet-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source"
        self.source.mkdir()
        for name, data in self.files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.stage = self.base / "packet"
        self.head_patch = patch.object(packet, "source_head", return_value=HEAD)
        self.head_patch.start()
        self.addCleanup(self.head_patch.stop)

    def prepare(self):
        return cast(
            dict[str, Any], packet.prepare(self.stage, root=self.source, expected_source_head=HEAD)
        )

    def test_exact_closure_manifest_and_repeatable_identity(self):
        artifact = self.prepare()
        self.assertEqual(artifact, packet.verify(self.stage, artifact["artifactSha2_256"], HEAD))
        actual = {
            p.relative_to(self.stage).as_posix() for p in self.stage.rglob("*") if p.is_file()
        }
        self.assertEqual(actual, set(packet.SOURCES) | set(packet.METADATA))
        self.assertEqual(artifact["sourceHead"], HEAD)
        self.assertEqual(artifact["migrationHead"], "0026_album_local_removal.sql")
        for record in artifact["files"]:
            data = (self.stage / record["path"]).read_bytes()
            self.assertEqual(record["bytes"], len(data))
            self.assertEqual(record["sha2_256"], packet.digest(data))
        other = packet.prepare(self.base / "second", root=self.source, expected_source_head=HEAD)
        self.assertEqual(artifact, other)

    def test_manifest_identity_changes_for_source_head_or_bytes(self):
        original = packet.manifest(self.files, HEAD)
        changed = dict(self.files)
        changed["src/worker.ts"] += b"\n// synthetic changed bytes\n"
        self.assertNotEqual(
            original["artifactSha2_256"], packet.manifest(changed, HEAD)["artifactSha2_256"]
        )
        self.assertNotEqual(
            original["artifactSha2_256"], packet.manifest(self.files, "2" * 40)["artifactSha2_256"]
        )

    def test_prepare_refuses_stale_source_head_before_writes(self):
        with self.assertRaises(ValueError):
            packet.prepare(self.stage, root=self.source, expected_source_head="2" * 40)
        self.assertFalse(self.stage.exists())

    def test_verify_requires_matching_independent_digest_and_source_head(self):
        self.prepare()
        for digest, head in (("0" * 64, HEAD), (None, "2" * 40)):
            with self.subTest(digest=digest, head=head), self.assertRaises(ValueError):
                packet.verify(self.stage, digest, head)

    def test_manifest_refuses_unclosed_or_invalid_head(self):
        for head in ("", "main", "1" * 39, "G" * 40, "1" * 41):
            with self.subTest(head=head), self.assertRaises(ValueError):
                packet.manifest(self.files, head)
        for files in ({}, {**self.files, "private.json": b"synthetic"}):
            with self.assertRaises(ValueError):
                packet.manifest(files, HEAD)

    def test_extra_or_missing_stage_file_refused(self):
        self.prepare()
        extra = self.stage / "unlisted-synthetic.json"
        extra.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            packet.verify(self.stage)
        extra.unlink()
        (self.stage / "src/worker.ts").unlink()
        with self.assertRaises(ValueError):
            packet.verify(self.stage)

    def test_changed_source_bytes_refused(self):
        self.prepare()
        path = self.stage / "src/worker.ts"
        path.write_bytes(path.read_bytes() + b"\n// changed synthetic candidate\n")
        with self.assertRaises(ValueError):
            packet.verify(self.stage)

    def test_metadata_byte_and_meaning_changes_refused(self):
        self.prepare()
        for name in packet.METADATA:
            with self.subTest(metadata=name):
                path = self.stage / name
                before = path.read_bytes()
                path.write_bytes(before + b"\n")
                with self.assertRaises(ValueError):
                    packet.verify(self.stage)
                value = json.loads(before)
                value["unexpected"] = "synthetic"
                path.write_bytes(packet.encoded(value))
                with self.assertRaises(ValueError):
                    packet.verify(self.stage)
                path.write_bytes(before)

    def test_missing_source_or_new_unclosed_dependency_refused_before_writes(self):
        source = self.source / "src/worker.ts"
        original = source.read_bytes()
        for mutation in (
            b'import "./missing-qualification-source.ts";\n' + original,
            b'import "unlisted-external-provider";\n' + original,
        ):
            source.write_bytes(mutation)
            with self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.stage.exists())
        source.unlink()
        with self.assertRaises(OSError):
            self.prepare()
        self.assertFalse(self.stage.exists())

    def test_existing_or_inside_source_destination_refused(self):
        self.stage.mkdir()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(self.stage.iterdir()), [])
        with self.assertRaises(ValueError):
            packet.prepare(self.source / "nested", root=self.source)
        self.assertFalse((self.source / "nested").exists())

    def test_unlisted_source_is_not_copied(self):
        (self.source / "synthetic-unlisted-private.json").write_bytes(b"do not stage")
        self.prepare()
        self.assertFalse((self.stage / "synthetic-unlisted-private.json").exists())
        self.assertEqual(
            (self.source / "synthetic-unlisted-private.json").read_bytes(), b"do not stage"
        )

    def test_pinned_tools_migrations_and_no_go_limits(self):
        artifact = self.prepare()
        self.assertEqual(artifact["tools"]["node"], "24.22.0")
        self.assertEqual(artifact["tools"]["npm"], "npm@12.2.0")
        self.assertEqual(artifact["tools"]["devDependencies"]["typescript"], "7.0.2")
        migrations = [name for name in packet.SOURCES if name.startswith("migrations/")]
        self.assertEqual(len(migrations), 26)
        self.assertEqual(
            [Path(name).name[:4] for name in migrations],
            [f"{number:04}" for number in range(1, 27)],
        )
        self.assertEqual(artifact["status"], "NO-GO")
        limits = artifact["template"]
        self.assertEqual(limits["resources"], [])
        self.assertEqual(limits["network"], "forbidden")
        self.assertIs(limits["deployable"], False)
        self.assertIs(limits["syntheticOnly"], True)
        self.assertIs(limits["productionCapabilitiesEnabled"], False)
        self.assertEqual(limits["maximumDiagnosticSeconds"], 30)
        self.assertEqual(limits["maximumRequests"], 64)
        plan = json.loads((self.stage / "run-plan.json").read_bytes())
        self.assertEqual(plan["hostedQualification"], "not_executed")
        self.assertIs(plan["fullPublisherExecutable"], False)
        self.assertIs(plan["isolatedQualificationExecutable"], True)
        self.assertIs(plan["productionSchedulerQualified"], False)
        self.assertIn("exact_hosted_resource_binding_and_cleanup_not_authorized", plan["missing"])

    def test_no_approval_credentials_resources_or_expiry_in_template(self):
        self.prepare()
        authorization = json.loads((self.stage / "authorization-template.json").read_bytes())
        self.assertEqual(
            set(authorization),
            {
                "schemaVersion",
                "artifactSha2_256",
                "granted",
                "owner",
                "expiresAt",
                "resources",
                "allowDeploy",
                "allowProviderRequests",
                "allowProductionCapabilities",
            },
        )
        self.assertIs(authorization["granted"], False)
        self.assertIsNone(authorization["owner"])
        self.assertIsNone(authorization["expiresAt"])
        self.assertEqual(authorization["resources"], [])
        for field in ("allowDeploy", "allowProviderRequests", "allowProductionCapabilities"):
            self.assertIs(authorization[field], False)
        original = copy.deepcopy(authorization)
        for field, value in (
            ("granted", True),
            ("expiresAt", "2099-01-01T00:00:00Z"),
            ("resources", ["synthetic-resource"]),
            ("allowDeploy", True),
        ):
            mutated = {**original, field: value}
            (self.stage / "authorization-template.json").write_bytes(packet.encoded(mutated))
            with self.subTest(field=field), self.assertRaises(ValueError):
                packet.verify(self.stage)

    def test_changed_scope_template_refused_before_writes(self):
        path = self.source / packet.PROBE / "manifest-template.json"
        value = json.loads(path.read_bytes())
        value["maximumRequests"] = 65
        path.write_bytes(packet.encoded(value))
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.stage.exists())

    def test_source_config_enabled_flag_refused_before_writes(self):
        path = self.source / "wrangler.example.jsonc"
        original = path.read_bytes()
        path.write_bytes(
            original.replace(
                b'"FGA_UPLOAD_AUTHORIZATION_ENABLED": "0"',
                b'"FGA_UPLOAD_AUTHORIZATION_ENABLED": "1"',
            )
        )
        self.assertNotEqual(path.read_bytes(), original)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.stage.exists())

    def test_probe_external_dependency_and_toolchain_mutations_refused(self):
        probe = self.source / packet.PROBE / "offline.mjs"
        original = probe.read_bytes()
        probe.write_bytes(b'import "unlisted-external-provider";\n' + original)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.stage.exists())
        probe.write_bytes(original)
        package = self.source / "package.json"
        value = json.loads(package.read_bytes())
        value["devDependencies"]["typescript"] = "7.0.3"
        package.write_bytes(packet.encoded(value))
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.stage.exists())

    def directory_link(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        self.assertTrue(link.is_symlink() or link.is_junction())

    def test_actual_source_directory_link_refused_before_stage_writes(self):
        original = self.source / "src"
        target = self.base / "linked-source-content"
        original.rename(target)
        self.directory_link(original, target)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.stage.exists())

    def test_actual_stage_root_and_content_links_refused(self):
        artifact = self.prepare()
        linked_stage = self.base / "linked-stage"
        self.directory_link(linked_stage, self.stage)
        with self.assertRaises(ValueError):
            packet.verify(linked_stage, artifact["artifactSha2_256"], HEAD)
        original = self.stage / "src"
        target = self.base / "linked-stage-content"
        original.rename(target)
        self.directory_link(original, target)
        with self.assertRaises(ValueError):
            packet.verify(self.stage, artifact["artifactSha2_256"], HEAD)

    def test_self_consistent_tamper_rejected_by_original_external_digest(self):
        original = self.prepare()
        source = self.stage / "src/worker.ts"
        source.write_bytes(source.read_bytes() + b"\n// synthetic replacement bytes\n")
        files = packet.source_files(self.stage)
        rebuilt = packet.manifest(files, HEAD, source_commit_exact=False)
        for name, value in (
            ("manifest.json", rebuilt),
            ("run-plan.json", packet.run_plan(rebuilt)),
            ("authorization-template.json", packet.authorization_template(rebuilt)),
        ):
            (self.stage / name).write_bytes(packet.encoded(value))
        self.assertNotEqual(original["artifactSha2_256"], rebuilt["artifactSha2_256"])
        self.assertEqual(packet.verify(self.stage), rebuilt)
        with self.assertRaises(ValueError):
            packet.verify(self.stage, original["artifactSha2_256"], HEAD)

    def test_uncommitted_closure_is_labeled_and_strict_mode_refuses_before_writes(self):
        with patch.object(packet, "commit_exact", return_value=False):
            artifact = self.prepare()
            self.assertIs(artifact["sourceCommitExact"], False)
            with self.assertRaises(ValueError):
                packet.verify(
                    self.stage, artifact["artifactSha2_256"], HEAD, require_commit_exact=True
                )
            with (
                patch(
                    "sys.argv",
                    [
                        "prepare_hosted_publisher_qualification",
                        str(self.stage),
                        "--verify",
                        "--expected-artifact",
                        artifact["artifactSha2_256"],
                        "--expected-source-head",
                        HEAD,
                        "--require-commit-exact",
                    ],
                ),
                patch("sys.stderr", new=io.StringIO()),
                self.assertRaises(SystemExit) as refusal,
            ):
                packet.main()
            self.assertEqual(refusal.exception.code, 1)
            strict_stage = self.base / "strict-stage"
            with self.assertRaises(ValueError):
                packet.prepare(
                    strict_stage,
                    root=self.source,
                    expected_source_head=HEAD,
                    require_commit_exact=True,
                )
            self.assertFalse(strict_stage.exists())

    def test_git_blob_attestation_rejects_changed_and_untracked_closure(self):
        records = []
        for name, data in sorted(self.files.items()):
            sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            records.append(f"100644 blob {sha}\t{name}")
        with patch.object(packet.subprocess, "check_output", return_value="\n".join(records)):
            self.assertTrue(packet.commit_exact(self.source, self.files, HEAD))
            changed = dict(self.files)
            changed["src/worker.ts"] += b"\n// synthetic uncommitted change\n"
            self.assertFalse(packet.commit_exact(self.source, changed, HEAD))
        with patch.object(packet.subprocess, "check_output", return_value="\n".join(records[:-1])):
            self.assertFalse(packet.commit_exact(self.source, self.files, HEAD))


if __name__ == "__main__":
    unittest.main()
