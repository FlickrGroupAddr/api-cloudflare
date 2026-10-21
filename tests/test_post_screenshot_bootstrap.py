"""Fake metadata/clock/apply tests: no native, credential or provider access."""

import contextlib
import io
import json
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import post_screenshot_bootstrap as bootstrap

RUN = "1234567890abcdef12345678"
MANIFEST, SOURCE, APPROVAL = "a" * 64, "b" * 64, "c" * 64


class Harness:
    def __init__(self):
        files = {}
        self.identities = {}
        self.canonical = {}
        harness = self

        class FakePath(str):
            def __truediv__(self, value):
                return FakePath(str(self) + "/" + str(value))

            @property
            def name(self):
                return str(self).rsplit("/", 1)[-1]

            def exists(self):
                return str(self) in files

            def write_text(self, text):
                files[str(self)] = text

            def read_text(self):
                return files[str(self)]

            @property
            def parents(self):
                parts = str(self).split("/")
                return tuple(FakePath("/".join(parts[:i])) for i in range(len(parts) - 1, 0, -1))

            def with_name(self, name):
                return FakePath(str(self).rsplit("/", 1)[0]) / name

            def resolve(self, *, strict=True):
                return FakePath(harness.canonical.get(str(self), str(self)))

            def stat(self):
                return SimpleNamespace(
                    st_dev=1, st_ino=harness.identities.get(str(self), str(self))
                )

        self.base = FakePath("C:/fake-bootstrap-test")
        self.root = self.base / "private/bootstrap"
        self.parent_token = FakePath("C:/fake-parent-token.txt")
        self.child_token = self.base / "private/operator-token.txt"
        self.wall, self.mono = 1000.0, 0.0
        self.effect: Callable[[], None] | None = self.release
        self.sleeps = 0
        self.events = []
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(patch.object(bootstrap, "Path", FakePath))

        def path(value):
            if (
                not isinstance(value, str)
                or not value.startswith("C:/")
                or ".." in value
                or FakePath(value).resolve() != value
            ):
                raise ValueError("fake_canonical_path_refused")
            return FakePath(value)

        self.stack.enter_context(patch.object(bootstrap, "_path", side_effect=path))
        self.stack.enter_context(
            patch.object(bootstrap.prepared, "ROOT", FakePath("C:/fake-source"))
        )
        self.stack.enter_context(patch.object(bootstrap.prepared, "SOURCES", {"source.py"}))

        def create(path, value):
            if path.exists():
                raise FileExistsError("fake_exclusive_file_exists")
            path.write_text(json.dumps(value))

        self.writer = self.stack.enter_context(
            patch.object(bootstrap, "create_json", side_effect=create)
        )

        def public(path, maximum):
            raw = path.read_text().encode()
            if len(raw) > maximum:
                raise ValueError("fake_byte_limit")
            return raw

        self.stack.enter_context(
            patch.object(
                bootstrap.prepared,
                "binding",
                return_value={"runRoot": str(self.base), "tokenFile": str(self.child_token)},
            )
        )
        self.manifest = self.stack.enter_context(
            patch.object(bootstrap.prepared, "validate_manifest", return_value=MANIFEST)
        )
        self.digest = self.stack.enter_context(
            patch.object(bootstrap.prepared, "digest", return_value=SOURCE)
        )
        self.private = self.stack.enter_context(
            patch.object(bootstrap, "_assert_private", side_effect=self.check_private)
        )
        self.links = self.stack.enter_context(patch.object(bootstrap.boundary, "_refuse_links"))
        self.reader = self.stack.enter_context(
            patch.object(bootstrap, "_private_bytes", side_effect=public)
        )
        self.config = self.stack.enter_context(
            patch.object(
                bootstrap.prepared,
                "validate_packet",
                return_value={"parentTokenFile": str(self.parent_token)},
            )
        )
        self.stack.enter_context(
            patch.object(bootstrap.time, "time", side_effect=lambda: self.wall)
        )
        self.stack.enter_context(
            patch.object(bootstrap.time, "monotonic", side_effect=lambda: self.mono)
        )
        self.stack.enter_context(patch.object(bootstrap.time, "sleep", side_effect=self.sleep))
        self.apply = self.stack.enter_context(
            patch.object(
                bootstrap, "apply", return_value={"outcome": "stopped", "cleanupConfirmed": True}
            )
        )

    def check_private(self, path, **kw):
        self.events.append(("private", Path(path).name))

    def sleep(self, seconds):
        self.sleeps += 1
        self.wall += seconds
        self.mono += seconds
        if self.effect:
            self.effect()

    def release(self, change=None):
        self.assert_no_apply()
        boot = json.loads((self.root / "bootstrap.json").read_text())
        value = {key: boot[key] for key in ("schemaVersion", "runId", "owner", "nonce")}
        value["approvalSha2_256"] = APPROVAL
        if change:
            change(value)
        (self.root / "release.json").write_text(json.dumps(value))
        self.effect = None

    def assert_no_apply(self):
        self.apply.assert_not_called()

    def closed(self):
        return json.loads((self.root / "bootstrap-closed.json").read_text())

    def run(self):
        return bootstrap.run(RUN, MANIFEST, str(self.parent_token))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stack.close()


class BootstrapTests(unittest.TestCase):
    def test_one_same_process_fixed_apply_after_exact_release(self):
        with Harness() as h:
            value = h.run()
            h.apply.assert_called_once_with(h.base / "private/approved-packet.json", APPROVAL)
            boot = json.loads((h.root / "bootstrap.json").read_text())
            self.assertEqual(boot["deadlineUnix"], 1600)
            self.assertEqual(boot["callerSha2_256"], SOURCE)
            self.assertEqual(boot["owner"], value["owner"])
            self.assertEqual(h.closed()["owner"], value["owner"])
            self.assertTrue(h.closed()["applyStarted"])
            self.assertTrue(h.closed()["applyReturned"])
            self.assertFalse(value["methodSpecificPostQualified"])
            self.assertTrue((h.root / "release.json").exists())
            self.assertEqual(h.reader.call_args.args[0], h.root / "release.json")
            self.assertEqual(h.reader.call_count, 1)

    def test_wrong_release_identity_or_commands_never_apply(self):
        for change in (
            lambda v: v.update(owner="1"),
            lambda v: v.update(nonce="0" * 32),
            lambda v: v.update(schemaVersion=True),
            lambda v: v.update(command="run"),
            lambda v: v.update(approvalSha2_256="not-a-pin"),
        ):
            with self.subTest(change=change), Harness() as h:
                h.effect = lambda change=change: h.release(change)
                with self.assertRaisesRegex(ValueError, "exact_release"):
                    h.run()
                h.assert_no_apply()
                self.assertFalse(h.closed()["applyStarted"])

    def test_timeout_does_not_renew_or_apply(self):
        with Harness() as h:

            def expire():
                h.wall += 600
                h.mono += 600

            h.effect = expire
            with self.assertRaisesRegex(ValueError, "clock_or_cutoff"):
                h.run()
            h.assert_no_apply()
            self.assertEqual(h.sleeps, 1)
            self.assertEqual(h.closed()["outcome"], "stopped_or_unknown")

    def test_stop_before_release_preserves_claim(self):
        with Harness() as h:
            h.effect = lambda: (h.root / "bootstrap-stop.json").write_text("unknown")
            with self.assertRaisesRegex(ValueError, "bootstrap_stopped"):
                h.run()
            h.assert_no_apply()
            self.assertTrue((h.root / "bootstrap.json").exists())

    def test_source_changes_refuse_after_release(self):
        with Harness() as h:
            h.manifest.side_effect = [MANIFEST, "d" * 64]
            with self.assertRaisesRegex(ValueError, "source_changed"):
                h.run()
            h.assert_no_apply()

    def test_slow_final_source_check_cannot_extend_wait(self):
        with Harness() as h:

            def verify():
                if h.manifest.call_count > 1:
                    h.wall += 600
                    h.mono += 600
                return MANIFEST

            h.manifest.side_effect = verify
            with self.assertRaisesRegex(ValueError, "release_expired"):
                h.run()
            h.assert_no_apply()

    def test_backward_wall_clock_refuses(self):
        with Harness() as h:
            h.effect = lambda: setattr(h, "wall", 999)
            with self.assertRaisesRegex(ValueError, "clock_or_cutoff"):
                h.run()
            h.assert_no_apply()

    def test_final_monotonic_reversal_refuses(self):
        with Harness() as h:

            def verify():
                if h.manifest.call_count > 1:
                    h.mono = 0.05
                return MANIFEST

            h.manifest.side_effect = verify
            with self.assertRaisesRegex(ValueError, "release_expired"):
                h.run()
            h.assert_no_apply()

    def test_oversize_release_refuses_before_protected_parse(self):
        with Harness() as h:
            h.effect = lambda: (h.root / "release.json").write_text(" " * 4097)
            with self.assertRaisesRegex(ValueError, "byte_limit"):
                h.run()
            h.reader.assert_called_once_with(h.root / "release.json", 4096)
            h.assert_no_apply()

    def test_changed_helper_bytes_refuse(self):
        with Harness() as h:
            h.digest.side_effect = [SOURCE, "d" * 64]
            with self.assertRaisesRegex(ValueError, "source_changed"):
                h.run()
            h.assert_no_apply()

    def test_unknown_apply_retains_started_not_returned_and_never_retries(self):
        with Harness() as h:
            h.apply.side_effect = RuntimeError("fake private error")
            with self.assertRaises(RuntimeError):
                h.run()
            self.assertEqual(h.apply.call_count, 1)
            self.assertTrue(h.closed()["applyStarted"])
            self.assertFalse(h.closed()["applyReturned"])
            with self.assertRaisesRegex(ValueError, "not_fresh"):
                h.run()
            self.assertEqual(h.apply.call_count, 1)

    def test_stale_receipt_refuses_without_apply(self):
        with Harness() as h:
            (h.root / "bootstrap.json").write_text("spent")
            with self.assertRaisesRegex(ValueError, "not_fresh"):
                h.run()
            h.assert_no_apply()
            self.assertEqual((h.root / "bootstrap.json").read_text(), "spent")

    def test_release_metadata_refusal_precedes_content(self):
        with Harness() as h:

            def private(path, **kw):
                if Path(path).name == "release.json":
                    raise ValueError("fake_acl_refused")

            h.private.side_effect = private
            with patch.object(bootstrap.prepared, "public_bytes") as read:
                with self.assertRaisesRegex(ValueError, "acl_refused"):
                    h.run()
                read.assert_not_called()
            h.assert_no_apply()

    def test_default_cli_is_inert(self):
        with patch("sys.argv", ["bootstrap"]), patch.object(bootstrap, "run") as run:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bootstrap.main()
            run.assert_not_called()
            self.assertFalse(json.loads(output.getvalue())["actionReady"])

    def test_original_error_survives_closure_write_failure(self):
        with Harness() as h:
            original = RuntimeError("fake_original")
            h.apply.side_effect = original
            writer = h.writer.side_effect

            def fail(path, value):
                if path.name == "bootstrap-closed.json":
                    raise OSError("fake_closure")
                return writer(path, value)

            h.writer.side_effect = fail
            with self.assertRaises(RuntimeError) as caught:
                h.run()
            self.assertIs(caught.exception, original)
            self.assertIn("bootstrap_closure_unconfirmed", original.__notes__)

    def test_closure_failure_after_normal_apply_is_explicit(self):
        with Harness() as h:
            writer = h.writer.side_effect

            def fail(path, value):
                if path.name == "bootstrap-closed.json":
                    raise OSError("fake_closure")
                return writer(path, value)

            h.writer.side_effect = fail
            with self.assertRaisesRegex(ValueError, "closure_unconfirmed"):
                h.run()
            self.assertEqual(h.apply.call_count, 1)

    def test_parent_in_bootstrap_subtree_refuses_before_claim_or_bytes(self):
        with Harness() as h:
            h.parent_token = h.root / "release.json"
            with self.assertRaisesRegex(ValueError, "role_path"):
                h.run()
            h.reader.assert_not_called()
            h.manifest.assert_not_called()
            h.writer.assert_not_called()

    def test_public_source_parent_path_or_identity_alias_precedes_hashing(self):
        for use_identity in (False, True):
            with self.subTest(identity=use_identity), Harness() as h:
                source = "C:/fake-source/source.py"
                if use_identity:
                    h.identities[source] = str(h.parent_token)
                else:
                    h.parent_token = type(h.parent_token)(source)
                with self.assertRaisesRegex(ValueError, "credential_alias"):
                    h.run()
                h.manifest.assert_not_called()
                h.reader.assert_not_called()
                h.writer.assert_not_called()

    def test_release_credential_identity_alias_precedes_read(self):
        for credential in ("parent_token", "child_token"):
            with self.subTest(credential=credential), Harness() as h:
                h.identities[str(h.root / "release.json")] = str(getattr(h, credential))
                with self.assertRaisesRegex(ValueError, "credential_alias"):
                    h.run()
                h.reader.assert_not_called()
                h.assert_no_apply()

    def test_parent_binding_and_slow_config_validation_refuse(self):
        for slow in (False, True):
            with self.subTest(slow=slow), Harness() as h:
                if slow:

                    def config(path, pin):
                        h.wall += 601
                        h.mono += 601
                        return {"parentTokenFile": str(h.parent_token)}

                    h.config.side_effect = config
                else:
                    h.config.return_value = {"parentTokenFile": "C:/other-parent.txt"}
                with self.assertRaisesRegex(ValueError, "expired|declared_parent"):
                    h.run()
                h.assert_no_apply()

    def test_release_read_once_and_duplicate_json_refused(self):
        with Harness() as h:

            def malformed():
                h.release()
                path = h.root / "release.json"
                path.write_text(path.read_text().replace("{", '{"schemaVersion":1,', 1))

            h.effect = malformed
            with self.assertRaises(ValueError):
                h.run()
            h.reader.assert_called_once_with(h.root / "release.json", 4096)
            h.assert_no_apply()


if __name__ == "__main__":
    unittest.main()
