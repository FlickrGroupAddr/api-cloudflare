"""Credential-free literal transport tests using a benign native Python child."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import run_reviewed_manifest as launcher


class ReviewedManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="literal manifest ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.manifest = self.root / "manifest.json"
        self.document = {
            "executable": sys.executable,
            "cwd": str(self.root),
            "environmentOverrides": {"LITERAL_TEST_VALUE": 'spaces "quote" \\tail\\'},
            "argv": ["-c", "pass"],
        }

    def write(self, raw: bytes | None = None) -> list[str]:
        if raw is None:
            raw = json.dumps(self.document, ensure_ascii=True).encode()
        self.manifest.write_bytes(raw)
        return ["--manifest", str(self.manifest), "--sha2-256", hashlib.sha256(raw).hexdigest()]

    def invoke(self, args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return launcher.main(args)

    def test_default_is_inert_before_read(self) -> None:
        with (
            patch.object(launcher, "read_manifest") as read,
            patch.object(launcher.subprocess, "run") as run,
        ):
            self.assertEqual(self.invoke([]), 0)
        read.assert_not_called()
        run.assert_not_called()

    def test_check_is_inert_and_execution_uses_actual_cwd_environment_once(self) -> None:
        args = self.write()
        with patch.object(launcher.subprocess, "run") as run:
            self.assertEqual(self.invoke(["--check", *args]), 0)
            run.assert_not_called()
            run.return_value.returncode = 17
            self.assertEqual(self.invoke(["--execute", *args]), 17)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], [sys.executable, "-c", "pass"])
            self.assertEqual(run.call_args.kwargs["cwd"], str(self.root))
            self.assertEqual(
                run.call_args.kwargs["env"]["LITERAL_TEST_VALUE"],
                self.document["environmentOverrides"]["LITERAL_TEST_VALUE"],
            )
            self.assertEqual(run.call_args.kwargs["env"]["PATH"], os.environ["PATH"])
            self.assertIs(run.call_args.kwargs["shell"], False)

    def test_native_complete_synthetic_28_50_62_argument_vectors(self) -> None:
        receiver = self.root / "benign uv dummy.py"
        receiver.write_text(
            "import datetime,json,os,pathlib,sys\n"
            "values=sys.argv[1:]\n"
            "for value in values:\n"
            " if value.startswith('2030-'):\n"
            "  datetime.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ')\n"
            "pathlib.Path('received.json').write_text(json.dumps({"
            "'argv':values,'cwd':os.getcwd(),'env':os.environ['LITERAL_TEST_VALUE']}))\n",
            encoding="utf-8",
        )
        for width in (28, 50, 62):
            with self.subTest(width=width):
                # The dummy treats these as data; it invokes no UV or provider protocol.
                values = [
                    "run",
                    "--frozen",
                    "--offline",
                    "--no-sync",
                    "--project",
                    "synthetic project",
                    "python",
                    "-B",
                    "synthetic stage.py",
                    "--starts-at",
                    "2030-01-02T03:04:05Z",
                    "--expires-at",
                    "2030-01-02T03:05:05Z",
                    "",
                    "two words",
                    'embedded"quote',
                    "C:\\synthetic path\\tail\\",
                    "\\",
                    "trailing\\\\",
                    "雪",
                ]
                values.extend(f"literal-{i}" for i in range(width - 1 - len(values)))
                self.document["argv"] = [str(receiver), *values]
                self.assertEqual(len(self.document["argv"]), width)
                self.assertEqual(self.invoke(["--execute", *self.write()]), 0)
                result = json.loads((self.root / "received.json").read_text())
                self.assertEqual(result["argv"], values)
                self.assertEqual(result["cwd"], str(self.root))
                self.assertEqual(
                    result["env"], self.document["environmentOverrides"]["LITERAL_TEST_VALUE"]
                )

    def test_nonstring_argv_refuses_before_launch(self) -> None:
        for invalid in (None, True, 1, 1.5, {}, [], {"date": "2030-01-02T03:04:05Z"}):
            with self.subTest(invalid=invalid), patch.object(launcher.subprocess, "run") as run:
                self.document["argv"] = [invalid]
                self.assertEqual(self.invoke(["--execute", *self.write()]), 2)
                run.assert_not_called()

    def test_parsed_date_and_path_objects_are_not_coerced(self) -> None:
        for value in (datetime(2030, 1, 2, tzinfo=UTC), Path("synthetic")):
            with self.subTest(value_type=type(value)), self.assertRaises(launcher.Refusal):
                launcher.literal(value)

    @unittest.skipUnless(os.name == "nt", "Windows native dispatch boundary")
    def test_batch_refusal_and_case_insensitive_environment_override(self) -> None:
        self.document["environmentOverrides"] = {"Path": "synthetic-only"}
        _, _, environment = launcher.command(json.dumps(self.document).encode())
        self.assertEqual([key for key in environment if key.upper() == "PATH"], ["Path"])
        self.assertEqual(environment["Path"], "synthetic-only")
        batch = self.root / "never execute.cmd"
        batch.write_text("@exit /b 99\n")
        self.document["executable"] = str(batch)
        with patch.object(launcher.subprocess, "run") as run:
            self.assertEqual(self.invoke(["--execute", *self.write()]), 2)
            run.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows UTF-16 native limits")
    def test_native_limits_count_utf16_units(self) -> None:
        self.assertEqual(launcher.windows_units("😀"), 2)
        self.document["argv"] = ["😀" * 16400]
        with self.assertRaisesRegex(launcher.Refusal, "command line too long"):
            launcher.command(json.dumps(self.document).encode())
        self.document["argv"] = ["-c", "pass"]
        self.document["environmentOverrides"] = {"SYNTHETIC": "😀" * 16400}
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(launcher.Refusal, "environment too long"),
        ):
            launcher.command(json.dumps(self.document).encode())

    def test_hardlinked_manifest_refuses_before_child_launch(self) -> None:
        args = self.write()
        original = self.manifest.lstat()
        linked = SimpleNamespace(st_mode=original.st_mode, st_size=original.st_size, st_nlink=2)
        with (
            patch.object(Path, "lstat", return_value=linked),
            patch.object(launcher.subprocess, "run") as run,
        ):
            self.assertEqual(self.invoke(["--execute", *args]), 2)
            run.assert_not_called()

    def test_bad_manifests_refuse_before_launch(self) -> None:
        valid = json.dumps(self.document)
        variants = [
            b"{",
            b"\xff",
            b"[]",
            valid.replace('"argv":', '"extra":0,"argv":').encode(),
            valid.replace('"argv":', '"cwd":"duplicate","argv":').encode(),
            valid.replace('"LITERAL_TEST_VALUE":', '"a":"1","a":').encode(),
        ]
        for raw in variants:
            with self.subTest(raw=raw), patch.object(launcher.subprocess, "run") as run:
                self.assertEqual(self.invoke(["--execute", *self.write(raw)]), 2)
                run.assert_not_called()

    def test_pin_path_and_size_refusals(self) -> None:
        args = self.write()
        for pin in ("0" * 64, "A" * 64, "a" * 63):
            with self.subTest(pin=pin), patch.object(launcher.subprocess, "run") as run:
                self.assertEqual(self.invoke(["--execute", *args[:-1], pin]), 2)
                run.assert_not_called()
        with patch.object(launcher.subprocess, "run") as run:
            self.assertEqual(
                self.invoke(["--execute", *self.write(b"x" * (launcher.MAX_MANIFEST_BYTES + 1))]), 2
            )
            run.assert_not_called()
        with self.assertRaises(launcher.Refusal):
            launcher.absolute_path("relative.json")
        with self.assertRaises(launcher.Refusal):
            launcher.absolute_path("C:\0invalid")

    def test_invalid_fields_refuse_before_launch(self) -> None:
        mutations = (
            ("executable", "relative.exe"),
            ("cwd", "relative"),
            ("cwd", True),
            ("environmentOverrides", {"A=B": "bad"}),
            ("environmentOverrides", {"A": "one", "a": "two"}),
            ("environmentOverrides", {"A": None}),
            ("argv", ["NUL\0"]),
            ("argv", ["\ud800"]),
            ("argv", ["x" * (launcher.MAX_STRING_CHARS + 1)]),
            ("argv", [""] * (launcher.MAX_ARGV + 1)),
        )
        original = self.document.copy()
        for field, value in mutations:
            with (
                self.subTest(field=field, value_type=type(value)),
                patch.object(launcher.subprocess, "run") as run,
            ):
                self.document = {**original, field: value}
                self.assertEqual(self.invoke(["--execute", *self.write()]), 2)
                run.assert_not_called()

    def test_failed_launch_has_no_automatic_retry(self) -> None:
        with patch.object(launcher.subprocess, "run", side_effect=OSError) as run:
            self.assertEqual(self.invoke(["--execute", *self.write()]), 3)
            run.assert_called_once()

    def test_nonregular_linked_and_changing_manifest_refuse(self) -> None:
        with self.assertRaises(launcher.Refusal):
            launcher.read_manifest(self.root, "a" * 64)
        args = self.write()
        with patch.object(launcher, "no_links", side_effect=launcher.Refusal("linked")):
            self.assertEqual(self.invoke(["--execute", *args]), 2)
        original = launcher.fingerprint
        calls = 0

        def changed(info: os.stat_result) -> tuple[int, int, int, int, int]:
            nonlocal calls
            calls += 1
            result = original(info)
            return (*result[:3], result[3] + (calls == 2), result[4])

        with (
            patch.object(launcher, "fingerprint", side_effect=changed),
            patch.object(launcher.subprocess, "run") as run,
        ):
            self.assertEqual(self.invoke(["--execute", *args]), 2)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
