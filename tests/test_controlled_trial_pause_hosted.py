"""CI credential/configuration checks; all provider operations are mocked."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.controlled_trial_pause_hosted as hosted


class HostedConfigurationTests(unittest.TestCase):
    def test_environment_auth_reads_no_ignored_manifest_or_token_file(self):
        environment = {"CLOUDFLARE_ACCOUNT_ID": "a" * 32, "CLOUDFLARE_API_TOKEN": "T" * 40}
        with (
            patch.dict(hosted.os.environ, environment, clear=True),
            patch.object(Path, "read_text", side_effect=AssertionError("unexpected file read")),
            patch.object(hosted, "file_token", side_effect=AssertionError("unexpected token file")),
        ):
            self.assertEqual(hosted.credentials(None, from_env=True), ("a" * 32, "T" * 40))

    def test_missing_environment_auth_never_requests_or_creates_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            output = Path(directory) / "output"
            (root / "migrations").mkdir(parents=True)
            (root / "migrations/0014_photo_memberships.sql").write_text("SELECT 1;\n")
            (root / "pyproject.toml").write_text("[project]\nname='synthetic'\n")
            (root / "uv.lock").write_text("version=1\n")
            stream = io.StringIO()
            with (
                patch.object(hosted, "ROOT", root),
                patch.dict(hosted.os.environ, {}, clear=True),
                patch.object(hosted, "control", side_effect=AssertionError("provider call")) as api,
                patch.object(
                    hosted.pause, "request", side_effect=AssertionError("D1 call")
                ) as query,
                contextlib.redirect_stdout(stream),
            ):
                self.assertEqual(hosted.run(None, output, from_env=True), 1)
            api.assert_not_called()
            query.assert_not_called()
            receipt = json.loads(
                (output / "docs/evidence/controlled-trial-pause-hosted-2026-10-15.json").read_text()
            )
            self.assertFalse(receipt["passed"])
            self.assertFalse(receipt["resourceCreationAttempted"])
            self.assertTrue(receipt["cleanupConfirmed"])
            self.assertEqual(receipt["unavailableReason"], "operator_env_unavailable")
            self.assertEqual(json.loads(stream.getvalue())["resourceCreationAttempted"], False)

    def test_environment_cli_forwards_only_declared_mode_and_output(self):
        with (
            patch("sys.argv", ["proof", "--from-env", "--output-directory", "synthetic-output"]),
            patch.object(hosted, "run", return_value=0) as run,
        ):
            self.assertEqual(hosted.main(), 0)
        run.assert_called_once_with(None, Path("synthetic-output").resolve(), from_env=True)

    def test_environment_and_file_auth_are_mutually_exclusive(self):
        with (
            patch(
                "sys.argv",
                ["proof", "--from-env", "--token-file", "synthetic", "--output-directory", "."],
            ),
            patch.object(hosted, "run") as run,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            hosted.main()
        self.assertEqual(error.exception.code, 2)
        run.assert_not_called()

    def test_environment_rejects_invalid_account_or_token_without_fallback(self):
        for account, token in (("invalid", "T" * 40), ("a" * 32, "")):
            with (
                self.subTest(account_valid=len(account) == 32, token_present=bool(token)),
                patch.dict(
                    hosted.os.environ,
                    {"CLOUDFLARE_ACCOUNT_ID": account, "CLOUDFLARE_API_TOKEN": token},
                    clear=True,
                ),
                patch.object(
                    hosted, "file_token", side_effect=AssertionError("fallback forbidden")
                ),
                self.assertRaisesRegex(RuntimeError, "operator_env_unavailable"),
            ):
                hosted.credentials(None, from_env=True)


if __name__ == "__main__":
    unittest.main()
